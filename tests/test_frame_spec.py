"""Offline tests for the one-shot portal-frame driver's spec machinery.

Nothing here talks to MIDAS.  What is being pinned down is the part that has to
be right *before* a live run is worth starting:

* a spec cannot silently describe a different model than the caller asked for
  (unknown keys are refused, not ignored);
* a spec that drops a load cannot leave the previous run's derived scalar
  behind and have the report quote it;
* the shipped ``specs/portal-frame.json`` still describes the frame the driver
  was validated against;
* ``verdict()`` - the value the ``midas_frame_run`` tool turns into its answer -
  cannot report ``ok`` for anything that was not a complete, verified run.
"""
from __future__ import annotations

import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path
from types import SimpleNamespace

from midas_mcp import frame


class SpecMergeTests(unittest.TestCase):
    def test_unknown_key_is_refused_not_ignored(self):
        # 'beam_load' is the typo this exists for: silently ignored, it would
        # analyse a frame without the load the caller described.
        with self.assertRaises(ValueError) as ctx:
            frame._merge({"beam_load": []})
        self.assertIn("unknown spec key", str(ctx.exception))
        self.assertIn("beam_load", str(ctx.exception))

    def test_unknown_key_message_names_the_known_keys(self):
        with self.assertRaises(ValueError) as ctx:
            frame._merge({"nope": 1})
        for key in frame.SPEC_DEFAULT:
            self.assertIn(key, str(ctx.exception))

    def test_meta_keys_are_accepted(self):
        merged = frame._merge({"_comment": "x", "out_dir": "tmp"})
        self.assertEqual(merged["_comment"], "x")
        self.assertEqual(merged["out_dir"], "tmp")

    def test_omitted_keys_keep_the_validated_default(self):
        merged = frame._merge({"span": 24.0})
        self.assertEqual(merged["span"], 24.0)
        self.assertEqual(merged["eave"], frame.SPEC_DEFAULT["eave"])
        self.assertEqual(merged["combos"], frame.SPEC_DEFAULT["combos"])

    def test_merge_does_not_mutate_the_default(self):
        before = json.dumps(frame.SPEC_DEFAULT, sort_keys=True)
        frame._merge({"span": 99.0})
        self.assertEqual(json.dumps(frame.SPEC_DEFAULT, sort_keys=True), before)

    def test_default_spec_is_json_serialisable(self):
        # A spec travels as JSON (a file, or the tool's argument), so a value
        # that cannot round-trip could never be overridden.  Tuples become
        # lists on the way, which configure() normalises away.
        again = json.loads(json.dumps(frame.SPEC_DEFAULT))
        self.assertEqual(json.loads(json.dumps(frame._merge(again))),
                         json.loads(json.dumps(frame.SPEC_DEFAULT)))


class LoadSpecTests(unittest.TestCase):
    def test_none_is_an_empty_spec(self):
        self.assertEqual(frame.load_spec(None), {})

    def test_reads_a_json_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.json"
            path.write_text(json.dumps({"span": 30.0}), encoding="utf-8")
            self.assertEqual(frame.load_spec(str(path)), {"span": 30.0})

    def test_missing_file_raises_oserror(self):
        with self.assertRaises(OSError):
            frame.load_spec(str(Path(tempfile.gettempdir()) / "no-such-spec.json"))

    def test_malformed_file_raises_valueerror(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ValueError):
                frame.load_spec(str(path))


class ShippedSpecTests(unittest.TestCase):
    """The checked-in spec is documentation; it must not drift from the code."""

    SPEC_FILE = frame.ROOT / "specs" / "portal-frame.json"

    def test_the_shipped_spec_exists(self):
        self.assertTrue(self.SPEC_FILE.is_file(), f"{self.SPEC_FILE} is missing")

    def test_the_shipped_spec_describes_the_validated_frame(self):
        """Compared as JSON: the file holds lists where the module holds tuples.

        ``configure`` normalises both, so the list/tuple difference is not a
        difference in the model - comparing the raw dicts would report a drift
        that does not exist, and mask one that does.
        """
        merged = frame._merge(frame.load_spec(str(self.SPEC_FILE)))
        model = {k: v for k, v in merged.items() if k in frame.SPEC_DEFAULT}
        self.assertEqual(json.loads(json.dumps(model)),
                         json.loads(json.dumps(frame.SPEC_DEFAULT)))

    def test_the_shipped_spec_only_uses_known_keys(self):
        spec = frame.load_spec(str(self.SPEC_FILE))
        self.assertEqual(sorted(set(spec) - set(frame.SPEC_DEFAULT)),
                         sorted(frame._SPEC_META))


class ConfigureTests(unittest.TestCase):
    def tearDown(self):
        # configure() installs into module globals, so every test has to hand
        # the module back in the state it found it.
        frame.configure({})

    def test_geometry_follows_the_span(self):
        frame.configure({"span": 24.0})
        self.assertEqual(frame.SPAN, 24.0)
        self.assertEqual(frame.NODE_XYZ[3][0], 12.0)
        self.assertEqual(frame.SLOPE, (frame.RIDGE - frame.EAVE) / 12.0)
        self.assertEqual(len(frame.NODES), 5)

    def test_element_lengths_follow_the_geometry(self):
        frame.configure({"span": 24.0})
        for _eid, i, j, _role in frame.ELEMS:
            self.assertAlmostEqual(
                frame.ELEM_LEN[_eid],
                ((frame.NODE_XYZ[i][0] - frame.NODE_XYZ[j][0]) ** 2
                 + (frame.NODE_XYZ[i][2] - frame.NODE_XYZ[j][2]) ** 2) ** 0.5,
                places=9)

    def test_a_dropped_load_does_not_leave_its_scalar_behind(self):
        # The wind cases are named WIND_X_POS / WIND_X_NEG, so matching on the
        # bare word "WIND" would keep every one of them and pass vacuously.
        kept = [b for b in frame.SPEC_DEFAULT["beam_loads"]
                if not str(b[1]).startswith("WIND")]
        frame.configure({"beam_loads": kept})
        self.assertEqual(frame.WIND_Q, 0.0)
        # The loads that were kept must still be derived, or the reset would
        # have thrown away more than the spec asked for.
        dead = [b[3] for b in kept if b[1] == "DEAD" and b[2] == "GZ"]
        self.assertTrue(dead, "the fixture no longer keeps a dead load")
        self.assertEqual(frame.ROOF_DEAD_Q, dead[0])

    def test_wind_scalar_is_the_largest_applied_wind_load(self):
        frame.configure({"beam_loads": [
            [1, "WIND", "GX", 6.0], [2, "WIND", "GX", -9.5]]})
        self.assertEqual(frame.WIND_Q, 9.5)

    def test_combo_names_come_from_the_combo_list(self):
        frame.configure({"combos": [["C1", "1.0 DEAD", [["DEAD", 1.0]]]]})
        self.assertEqual(frame.COMBO_NAMES, ("C1",))
        self.assertEqual(frame.COMBOS, (("C1", "1.0 DEAD", (("DEAD", 1.0),)),))

    def test_out_dir_redirects_the_state_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame.configure({"out_dir": tmp})
            self.assertEqual(frame.OUT, Path(tmp).resolve())
            self.assertEqual(frame.STATE, Path(tmp).resolve() / "state.json")

    def test_a_bad_value_is_refused_not_silently_defaulted(self):
        for bad in ({"span": "wide"}, {"modes": None},
                    {"sections": {"COLUMN": {}}}):
            with self.subTest(bad=bad):
                with self.assertRaises((KeyError, TypeError, ValueError)):
                    frame.configure(bad)


class VerdictTests(unittest.TestCase):
    """``verdict()`` is what the MCP tool reports, so it must not overstate."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)
        frame.configure({"out_dir": self.out})

    def tearDown(self):
        frame.configure({})
        self._tmp.cleanup()

    def _state(self, **overrides):
        state = {"timestamp": "t", "analysis": "SUCCESS",
                 "passed": ["a"], "failed": [],
                 "steps": [{"n": 1}],
                 "criteria": [{"name": "a", "ok": True, "detail": ""}],
                 "verifications": [{"name": "v", "ok": True, "detail": ""}]}
        state.update(overrides)
        (self.out / "state.json").write_text(
            json.dumps(state, ensure_ascii=False), encoding="utf-8")

    def test_a_missing_state_is_not_run(self):
        got = frame.verdict()
        self.assertFalse(got["ok"])
        self.assertEqual(got["analysis"], "NOT_RUN")
        self.assertEqual(got["report"], "")

    def test_a_complete_run_is_ok(self):
        self._state()
        (self.out / "report.md").write_text("# 报告\n", encoding="utf-8")
        got = frame.verdict()
        self.assertTrue(got["ok"])
        self.assertEqual(got["report"], "# 报告\n")
        self.assertEqual(len(got["criteria"]), 1)

    def test_a_failed_criterion_is_not_ok(self):
        self._state(failed=["a"],
                    criteria=[{"name": "a", "ok": False, "detail": "x"}])
        self.assertFalse(frame.verdict()["ok"])

    def test_a_failed_analysis_is_not_ok(self):
        # Every criterion can pass on a run whose analysis did not converge;
        # the analysis status is a separate gate.
        self._state(analysis="FAILED")
        self.assertFalse(frame.verdict()["ok"])

    def test_a_run_without_self_checks_is_not_ok(self):
        # all([]) is True - an empty check list must not pass vacuously.
        self._state(verifications=[])
        self.assertFalse(frame.verdict()["ok"])

    def test_a_run_without_criteria_is_not_ok(self):
        self._state(criteria=[])
        self.assertFalse(frame.verdict()["ok"])

    def test_a_failed_verification_is_not_ok(self):
        self._state(verifications=[{"name": "v", "ok": False, "detail": "x"}])
        self.assertFalse(frame.verdict()["ok"])

    def test_a_refusal_is_reported_with_its_reason(self):
        # The preflight writes this shape when the live document is not empty.
        self._state(analysis="REFUSED", failed=["preflight"], criteria=[],
                    verifications=[], note="活文档非空: ['NODE']")
        got = frame.verdict()
        self.assertFalse(got["ok"])
        self.assertEqual(got["analysis"], "REFUSED")
        self.assertEqual(got["note"], "活文档非空: ['NODE']")

    def test_a_refusal_does_not_quote_the_previous_runs_report(self):
        # The refusal returns before a report is rendered, so a leftover
        # report.md from an earlier run must not be handed back as this run's.
        # Verified live: without this the --json verdict of a refused run carried
        # the full report of the run before it.
        self._state(analysis="REFUSED", failed=["preflight"], criteria=[],
                    verifications=[], note="活文档非空")
        (self.out / "report.md").write_text("# 上一轮的报告\n", encoding="utf-8")
        got = frame.verdict()
        self.assertFalse(got["ok"])
        self.assertEqual(got["report"], "")




class ShimTests(unittest.TestCase):
    def test_the_old_entry_point_is_a_shim_over_the_package_module(self):
        """``tests/live_portal_frame.py`` must not be a second implementation."""
        import importlib.util
        path = frame.ROOT / "tests" / "live_portal_frame.py"
        spec = importlib.util.spec_from_file_location("_shim_check", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertIs(module._frame, frame)
        self.assertIs(module.main, frame.main)
        self.assertIs(module.run, frame.run)


class ReportFollowsSpecTests(unittest.TestCase):
    """The report must describe the run that happened.

    Every label in the model table used to be a literal - "20 m", "5", "N1/N5",
    the section names.  The spec can change all of them, so a literal turns the
    report into a description of the frame the driver was *built* against.
    """

    def tearDown(self):
        frame.configure({})

    def _head(self, dist="M", force="KN"):
        # report_head writes through a `w(text="")` callback, so a bare
        # list.append is not a stand-in for it.
        out = []
        frame.report_head(lambda text="": out.append(text),
                          {"DIST": dist, "FORCE": force}, True)
        return "\n".join(out)

    def test_geometry_in_the_report_follows_the_spec(self):
        frame.configure({"span": 24.0, "eave": 7.0, "ridge": 9.5})
        text = self._head()
        self.assertIn("| 跨度 | 24 m |", text)
        self.assertIn("| 柱高 | 7 m |", text)
        self.assertIn("| 屋脊高度 | 9.5 m |", text)
        self.assertNotIn("| 跨度 | 20 m |", text)

    def test_counts_come_from_the_model_not_a_literal(self):
        frame.configure({"span": 24.0})
        text = self._head()
        self.assertIn(f"| 节点数量 | {len(frame.NODES)} |", text)
        self.assertIn(f"| 单元数量 | {len(frame.ELEMS)} |", text)
        self.assertEqual(len(frame.NODES), 5)

    def test_a_renamed_section_is_reported_under_its_own_name(self):
        frame.configure({"sections": {
            "COLUMN": {"id": 1, "name": "CUSTOM_COL",
                       "vsize": [0.5, 0.25, 0.01, 0.016]},
            "BEAM": {"id": 2, "name": "CUSTOM_BEAM",
                     "vsize": [0.6, 0.2, 0.01, 0.02]}}})
        text = self._head()
        self.assertIn("CUSTOM_COL (H500×250×10×16)", text)
        self.assertIn("CUSTOM_BEAM (H600×200×10×20)", text)
        self.assertNotIn("H400X200X8X12", text)

    def test_support_label_follows_the_support_nodes(self):
        frame.configure({"supports": {"nodes": [2, 4], "constraint": "1110000"}})
        self.assertEqual(frame.support_label(), "N2/N4")
        self.assertEqual(frame.support_nodes(), ("2", "4"))
        self.assertIn("| 支座 | N2/N4 铰支", self._head())

    def test_a_fixed_base_is_not_described_as_pinned(self):
        frame.configure({"supports": {"nodes": [1, 5], "constraint": "1111110"}})
        self.assertEqual(frame.support_kind(), "刚接")
        self.assertIn("刚接", self._head())

    def test_the_restraint_description_comes_from_the_constraint_string(self):
        frame.configure({"supports": {"nodes": [1], "constraint": "1100000"}})
        self.assertEqual(frame.dof_split(), (["DX", "DY"],
                                            ["DZ", "RX", "RY", "RZ", "RW"]))
        self.assertEqual(frame.support_kind(), "部分约束")

    def test_an_unverified_structure_code_is_not_given_a_plane(self):
        frame.configure({"styp": 2})
        self.assertNotIn("X-Z 平面", frame.struct_type_text())
        self.assertIn("2", frame.struct_type_text())

    def test_units_in_the_model_table_come_from_the_response(self):
        self.assertIn("FORCE=N, DIST=CM", self._head(dist="CM", force="N"))

    def test_the_extreme_count_is_not_a_literal(self):
        rows = frame.criteria({}, {"replies": {}}, {"a": 1, "b": None}, None, [])
        detail = {name: text for name, _ok, text in rows}["极值提取"]
        self.assertIn("/2", detail)


class FrameRunToolTests(unittest.TestCase):
    """The envelope ``midas_frame_run`` answers with, without a live MIDAS.

    The tool runs the driver as a subprocess, so ``subprocess.run`` is replaced
    by one that returns a canned stdout line.  What is under test is the mapping
    from the driver's verdict to the tool's answer - the shape a client codes
    against, and the reason ``ok``/``report`` sit at the top level while the
    counts live in ``data``.
    """

    class _Done:
        def __init__(self, stdout, returncode=0, stderr=""):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

    @staticmethod
    def _client():
        return SimpleNamespace(cfg=SimpleNamespace(
            base_url="http://localhost:3030/gen",
            mapi_key=SimpleNamespace(reveal=lambda: "TESTKEY0000000000000")))

    def _call(self, verdict, returncode=0, stderr="", spec=None):
        from midas_mcp import dispatch

        stdout = "" if verdict is None else json.dumps(verdict) + "\n"
        with unittest.mock.patch.object(dispatch.subprocess, "run") as run:
            run.return_value = self._Done(stdout, returncode, stderr)
            answer = dispatch.tool_frame_run(
                {"spec": {} if spec is None else spec},
                lambda: (None, self._client(), None))
        return answer, run.call_args

    def test_a_successful_verdict_is_wrapped_not_returned_bare(self):
        answer, _ = self._call(
            {"ok": True, "analysis": "SUCCESS", "exit_code": 0,
             "criteria": [{"name": "a", "ok": True, "detail": ""}],
             "verifications": [{"name": "b", "ok": True, "detail": ""}],
             "failed": [], "note": None, "report": "# the report\n"})
        self.assertIs(answer["ok"], True)
        self.assertEqual(answer["status"], 200)
        self.assertIsNone(answer["category"])
        self.assertEqual(answer["report"], "# the report\n")
        self.assertEqual(answer["data"]["analysis"], "SUCCESS")
        self.assertEqual(len(answer["data"]["criteria"]), 1)
        self.assertNotIn("report", answer["data"])

    def test_a_refusal_names_the_situation_and_carries_no_report(self):
        answer, _ = self._call(
            {"ok": False, "analysis": "REFUSED", "exit_code": 3, "criteria": [],
             "verifications": [], "failed": ["preflight"], "note": "活文档非空",
             "report": ""}, returncode=3)
        self.assertIs(answer["ok"], False)
        self.assertEqual(answer["category"], "MODEL_NOT_EMPTY")
        self.assertEqual(answer["report"], "")
        self.assertEqual(answer["data"]["analysis"], "REFUSED")
        # the caller has to be able to see the way out of the refusal
        self.assertIn("clear", answer["message"])

    def test_a_failed_self_check_is_not_reported_as_a_model_problem(self):
        answer, _ = self._call(
            {"ok": False, "analysis": "SUCCESS", "exit_code": 1,
             "criteria": [{"name": "a", "ok": False, "detail": ""}],
             "verifications": [], "failed": ["a"], "note": None,
             "report": "# the report\n"})
        self.assertEqual(answer["category"], "SELF_CHECK_FAILED")

    def test_clear_must_be_a_boolean(self):
        from midas_mcp import dispatch
        from midas_mcp.errors import InputError

        for bad in ("false", "true", 1, 0, []):
            with self.assertRaises(InputError) as ctx:
                dispatch.tool_frame_run({"spec": {}, "clear": bad},
                                        lambda: (None, None, None))
            self.assertIn("boolean", str(ctx.exception))

    def test_clear_is_passed_as_a_flag_and_the_key_only_in_the_environment(self):
        answer, call = self._call(
            {"ok": True, "analysis": "SUCCESS", "exit_code": 0, "criteria": [1],
             "verifications": [1], "failed": [], "note": None, "report": "r"},
            spec={"span": 24.0})
        self.assertIs(answer["ok"], True)
        self.assertNotIn("--clear", call.args[0])

        from midas_mcp import dispatch

        with unittest.mock.patch.object(dispatch.subprocess, "run") as run:
            run.return_value = self._Done(json.dumps(
                {"ok": True, "analysis": "SUCCESS", "exit_code": 0,
                 "criteria": [1], "verifications": [1], "failed": [],
                 "note": None, "report": "r"}) + "\n")
            dispatch.tool_frame_run({"spec": {}, "clear": True},
                                    lambda: (None, self._client(), None))
            argv = run.call_args.args[0]
            env = run.call_args.kwargs["env"]
        self.assertIn("--clear", argv)
        self.assertEqual(env["MIDAS_MAPI_KEY"], "TESTKEY0000000000000")
        self.assertEqual(env["MIDAS_BASE_URL"], "http://localhost:3030/gen")
        # the child has to import the package, so src travels in the environment
        self.assertIn(str(Path(frame.__file__).resolve().parents[1]),
                      env["PYTHONPATH"])
        self.assertNotIn("TESTKEY0000000000000", " ".join(argv))

    def test_a_driver_that_printed_no_verdict_is_an_error_not_a_pass(self):
        from midas_mcp import dispatch
        from midas_mcp.errors import FrameRunError

        with self.assertRaises(FrameRunError) as ctx:
            self._call(None, returncode=3, stderr="spec 不可用: x")
        self.assertIn("spec 不可用", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
