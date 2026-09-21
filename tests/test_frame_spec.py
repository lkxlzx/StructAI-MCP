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

import io
import json
import tempfile
import threading
import unittest
import unittest.mock
from pathlib import Path
from types import SimpleNamespace

from midas_mcp import dispatch, frame
from midas_mcp.errors import FrameRunError, InputError


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


class _FakeProc:
    """A stand-in for the driver: two readable pipes and an exit code."""

    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = io.StringIO(stdout)
        self.stderr = io.StringIO(stderr)
        self.returncode = returncode
        self.killed = False

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9


class _SlowProc(_FakeProc):
    """A fake driver that stays alive until the test lets it finish.

    Without one, every test would only ever see a job that is already over,
    which is the one case the "running" branch never has to handle.
    """

    def __init__(self, stdout="", stderr=""):
        super().__init__(stdout, stderr)
        self.finish = threading.Event()

    def wait(self, timeout=None):
        self.finish.wait(10)
        self.returncode = 0
        return 0

    def kill(self):
        #: A real kill makes wait() return, so the fake has to do the same or
        #: the watchdog would look like it had not worked.
        super().kill()
        self.finish.set()


def _client():
    return SimpleNamespace(cfg=SimpleNamespace(
        base_url="http://localhost:3030/gen",
        mapi_key=SimpleNamespace(reveal=lambda: "TESTKEY0000000000000")))


def _deps():
    return lambda: (None, _client(), None)


def _verdict(**over):
    base = {"ok": True, "analysis": "SUCCESS", "exit_code": 0,
            "criteria": [{"name": "a", "ok": True, "detail": ""}],
            "verifications": [{"name": "b", "ok": True, "detail": ""}],
            "failed": [], "note": None, "report": "# the report\n"}
    base.update(over)
    return base


def _stdout_for(verdict, steps=()):
    return "".join(steps) + json.dumps(verdict) + "\n"


class FrameRunToolTests(unittest.TestCase):
    """The envelope ``midas_frame_run`` answers with, without a live MIDAS.

    ``subprocess.Popen`` is replaced here and in every test below, because the
    tool starts the driver as a real process: an unmocked Popen does not fail a
    test, it runs a five-minute analysis against whatever is listening on the
    configured port.  That is why the fake is a process rather than a value.
    """

    def setUp(self):
        dispatch._JOBS.clear()

    def _run(self, proc, args=None):
        with unittest.mock.patch.object(dispatch.subprocess, "Popen",
                                        return_value=proc) as popen:
            answer = dispatch.tool_frame_run(args or {"spec": {}}, _deps())
        return answer, popen.call_args

    def test_a_successful_verdict_is_wrapped_not_returned_bare(self):
        answer, _ = self._run(_FakeProc(_stdout_for(_verdict())))
        self.assertIs(answer["ok"], True)
        self.assertEqual(answer["status"], 200)
        self.assertIsNone(answer["category"])
        self.assertEqual(answer["report"], "# the report\n")
        self.assertIs(answer["running"], False)
        self.assertEqual(answer["data"]["analysis"], "SUCCESS")
        self.assertNotIn("report", answer["data"])
        self.assertTrue(answer["job_id"])

    def test_a_refusal_names_the_situation_and_carries_no_report(self):
        answer, _ = self._run(_FakeProc(_stdout_for(
            _verdict(ok=False, analysis="REFUSED", exit_code=3, criteria=[],
                     verifications=[], failed=["preflight"], note="活文档非空",
                     report="")), returncode=3))
        self.assertIs(answer["ok"], False)
        self.assertEqual(answer["category"], "MODEL_NOT_EMPTY")
        self.assertEqual(answer["report"], "")
        self.assertEqual(answer["data"]["analysis"], "REFUSED")
        # the caller has to be able to see the way out of the refusal
        self.assertIn("clear", answer["message"])

    def test_a_failed_self_check_is_not_reported_as_a_model_problem(self):
        answer, _ = self._run(_FakeProc(_stdout_for(_verdict(
            ok=False, exit_code=1, failed=["a"], verifications=[],
            criteria=[{"name": "a", "ok": False, "detail": ""}]))))
        self.assertEqual(answer["category"], "SELF_CHECK_FAILED")

    def test_clear_must_be_a_boolean(self):
        for bad in ("false", "true", 1, 0, []):
            with self.assertRaises(InputError) as ctx:
                dispatch.tool_frame_run({"spec": {}, "clear": bad}, _deps())
            self.assertIn("boolean", str(ctx.exception))

    def test_background_must_be_a_boolean(self):
        for bad in ("false", "true", 1, 0):
            with self.assertRaises(InputError) as ctx:
                dispatch.tool_frame_run({"spec": {}, "background": bad}, _deps())
            self.assertIn("boolean", str(ctx.exception))

    def test_clear_is_a_flag_and_the_key_only_in_the_environment(self):
        answer, call = self._run(_FakeProc(_stdout_for(_verdict())),
                                 {"spec": {}, "clear": True})
        self.assertIs(answer["ok"], True)
        argv = call.args[0]
        env = call.kwargs["env"]
        self.assertIn("--clear", argv)
        self.assertEqual(env["MIDAS_MAPI_KEY"], "TESTKEY0000000000000")
        self.assertEqual(env["MIDAS_BASE_URL"], "http://localhost:3030/gen")
        # the child has to import the package, so src travels in the environment
        self.assertIn(str(Path(frame.__file__).resolve().parents[1]),
                      env["PYTHONPATH"])
        self.assertNotIn("TESTKEY0000000000000", " ".join(argv))

    def test_a_driver_that_printed_no_verdict_is_an_error_not_a_pass(self):
        with self.assertRaises(FrameRunError) as ctx:
            self._run(_FakeProc("", "spec 不可用: x", returncode=3))
        self.assertIn("spec 不可用", str(ctx.exception))

class FrameJobTests(unittest.TestCase):
    """Start a run in the background, poll it, get the report out of the poll.

    Nothing here starts a process either.  The "still running" case is a job
    registered with its done-event unset, which is exactly what a live job looks
    like from the status tool's side - and it is the only way to test that
    branch without waiting five minutes for a real one.
    """

    STEPS = ("[01] PASS  创建/初始化模型  -- STYP=1\n"
             "[02] PASS  定义材料  -- Q355\n"
             "[03] FAIL  定义截面  -- nope\n")

    def setUp(self):
        dispatch._JOBS.clear()

    def _job(self, text="", done=False, returncode=0, job_id="job123"):
        if not isinstance(text, str):
            text = "".join(text)
        proc = _FakeProc(text, returncode=returncode)
        job = dispatch.FrameJob(job_id, proc,
                                ["python", "-m", "midas_mcp.frame", "--json"])
        #: A job built by hand has no reader thread, so its collected output is
        #: seeded directly.  That output is all the status tool and _answer
        #: read, so this is the same state a live job reaches.
        job.lines = text.splitlines(keepends=True)
        if done:
            job.done.set()
        with dispatch._JOBS_LOCK:
            dispatch._JOBS[job_id] = job
        return job

    def test_background_answers_at_once_with_a_handle(self):
        proc = _SlowProc()
        with unittest.mock.patch.object(dispatch.subprocess, "Popen",
                                        return_value=proc):
            answer = dispatch.tool_frame_run({"spec": {}, "background": True},
                                             _deps())
        try:
            self.assertIs(answer["ok"], True)
            self.assertEqual(answer["status"], 202)
            self.assertIs(answer["running"], True)
            self.assertEqual(answer["report"], "")
            self.assertIn("midas_frame_status", answer["message"])
            self.assertIn(answer["job_id"], dispatch._JOBS)
        finally:
            proc.finish.set()
            dispatch._JOBS[answer["job_id"]].done.wait(timeout=5)

    def test_status_reports_the_steps_the_driver_has_printed(self):
        self._job(self.STEPS)
        answer = dispatch.tool_frame_status({"job_id": "job123"}, _deps())
        self.assertIs(answer["ok"], True)
        self.assertIs(answer["running"], True)
        self.assertEqual(answer["status"], 202)
        self.assertEqual(answer["report"], "")
        progress = answer["data"]["progress"]
        self.assertEqual(progress["steps_done"], 3)
        self.assertEqual(progress["last"]["text"], "定义截面  -- nope")
        self.assertIs(progress["last"]["ok"], False)

    def test_a_finished_poll_returns_the_report_the_blocking_call_would(self):
        lines = [self.STEPS, json.dumps(_verdict()) + "\n"]
        self._job(lines, done=True)
        polled = dispatch.tool_frame_status({"job_id": "job123"}, _deps())
        self.assertIs(polled["running"], False)
        self.assertIs(polled["ok"], True)
        self.assertEqual(polled["report"], "# the report\n")

        with unittest.mock.patch.object(dispatch.subprocess, "Popen",
                                        return_value=_FakeProc("".join(lines))):
            blocking = dispatch.tool_frame_run({"spec": {}}, _deps())
        self.assertEqual(polled["report"], blocking["report"])
        self.assertEqual(polled["data"], blocking["data"])
        self.assertEqual(polled["category"], blocking["category"])

    def test_an_unknown_job_id_says_what_the_server_knows(self):
        self._job(job_id="abc")
        with self.assertRaises(InputError) as ctx:
            dispatch.tool_frame_status({"job_id": "nope"}, _deps())
        self.assertIn("nope", str(ctx.exception))
        self.assertIn("abc", str(ctx.exception))

    def test_a_missing_or_non_string_job_id_is_refused(self):
        for bad in (None, "", 7, []):
            with self.assertRaises(InputError) as ctx:
                dispatch.tool_frame_status({"job_id": bad}, _deps())
            self.assertIn("job_id", str(ctx.exception))

    def test_the_driver_steps_become_progress_notifications(self):
        seen = []
        dispatch.CALL.token = "tok-1"
        dispatch.CALL.notify = lambda method, params: seen.append((method, params))
        try:
            with unittest.mock.patch.object(
                    dispatch.subprocess, "Popen",
                    return_value=_FakeProc(_stdout_for(_verdict(), self.STEPS))):
                dispatch.tool_frame_run({"spec": {}}, _deps())
        finally:
            dispatch.CALL.token = None
            dispatch.CALL.notify = None
        self.assertEqual(len(seen), 3)
        self.assertTrue(all(m == "notifications/progress" for m, _ in seen))
        self.assertTrue(all(p["progressToken"] == "tok-1" for _, p in seen))
        self.assertEqual([p["progress"] for _, p in seen], [1, 2, 3])
        self.assertIn("定义截面", seen[2][1]["message"])

    def test_no_token_means_no_notifications(self):
        seen = []
        dispatch.CALL.token = None
        dispatch.CALL.notify = lambda method, params: seen.append(method)
        try:
            with unittest.mock.patch.object(
                    dispatch.subprocess, "Popen",
                    return_value=_FakeProc(_stdout_for(_verdict(), self.STEPS))):
                dispatch.tool_frame_run({"spec": {}}, _deps())
        finally:
            dispatch.CALL.notify = None
        self.assertEqual(seen, [])

    def test_a_background_call_gets_no_progress_notifications(self):
        seen = []
        proc = _SlowProc()
        dispatch.CALL.token = "tok-3"
        dispatch.CALL.notify = lambda method, params: seen.append(method)
        try:
            with unittest.mock.patch.object(dispatch.subprocess, "Popen",
                                            return_value=proc):
                answer = dispatch.tool_frame_run(
                    {"spec": {}, "background": True}, _deps())
            self.assertIs(answer["running"], True)
            #: MCP progress belongs to a request that is still in flight, and
            #: this one was answered at once - so nothing may be emitted.
            self.assertEqual(seen, [])
            proc.finish.set()
            self.assertTrue(dispatch._JOBS[answer["job_id"]].done.wait(timeout=5))
        finally:
            dispatch.CALL.token = None
            dispatch.CALL.notify = None


    def test_a_notifier_that_raises_cannot_fail_the_run(self):
        seen = []

        def broken(method, params):
            seen.append(method)
            raise RuntimeError("the client went away")

        dispatch.CALL.token = "tok-2"
        dispatch.CALL.notify = broken
        try:
            with unittest.mock.patch.object(
                    dispatch.subprocess, "Popen",
                    return_value=_FakeProc(_stdout_for(_verdict(), self.STEPS))):
                answer = dispatch.tool_frame_run({"spec": {}}, _deps())
        finally:
            dispatch.CALL.token = None
            dispatch.CALL.notify = None
        # the notifier has to have been tried for the assertion below to mean
        # anything: a run that never called it would pass either way
        self.assertEqual(len(seen), 3)
        self.assertIs(answer["ok"], True)
        self.assertEqual(answer["report"], "# the report\n")


    def test_a_finished_job_answers_with_its_report_not_a_job_id(self):
        job = self._job(json.dumps(_verdict()) + "\n", done=True)
        answer = dispatch._started(job)
        self.assertIs(answer["running"], False)
        self.assertEqual(answer["report"], "# the report\n")
        self.assertEqual(answer["status"], 200)

    def test_a_second_run_is_refused_while_one_is_live(self):
        self._job(job_id="live1")
        with self.assertRaises(InputError) as ctx:
            dispatch.tool_frame_run({"spec": {}}, _deps())
        self.assertIn("live1", str(ctx.exception))
        self.assertIn("already in flight", str(ctx.exception))

    def test_other_writers_are_refused_while_a_run_is_live(self):
        self._job(job_id="live1")
        for tool in (dispatch.tool_doc, dispatch.tool_db_assign,
                     dispatch.tool_db_delete):
            with self.assertRaises(InputError) as ctx:
                tool({"command": "SAVE", "endpoint": "DB:NODE", "mode": "create",
                      "data": {}, "target_ids": ["1"]}, _deps())
            self.assertIn("already in flight", str(ctx.exception))

    def test_watching_a_run_is_still_allowed_while_it_is_live(self):
        self._job(job_id="live1")
        answer = dispatch.tool_frame_status({"job_id": "live1"}, _deps())
        self.assertIs(answer["running"], True)

    def test_finished_jobs_are_evicted_and_live_ones_are_not(self):
        for i in range(dispatch._MAX_KEPT_JOBS + 5):
            self._job(done=True, job_id=f"old{i}")
        self._job(job_id="live1")
        self._job(done=True, job_id="newest")
        with dispatch._JOBS_LOCK:
            dispatch._evict_jobs()
        self.assertEqual(len(dispatch._JOBS), dispatch._MAX_KEPT_JOBS)
        self.assertIn("live1", dispatch._JOBS)
        self.assertIn("newest", dispatch._JOBS)
        self.assertNotIn("old0", dispatch._JOBS)

    def test_a_report_with_a_line_separator_still_yields_a_verdict(self):
        #: json.dumps(..., ensure_ascii=False) leaves U+2028 literal inside the
        #: report, and str.splitlines() treats it as a line break - which would
        #: cut the verdict line in half and lose a perfectly good run.
        verdict = _verdict(report="# report\u2028second line\n")
        job = self._job(json.dumps(verdict, ensure_ascii=False) + "\n", done=True)
        answer = dispatch._answer(job)
        self.assertEqual(answer["report"], "# report\u2028second line\n")
        self.assertIs(answer["ok"], True)

    def test_the_status_tool_never_kills_a_running_job(self):
        proc = _SlowProc()
        with unittest.mock.patch.object(dispatch.subprocess, "Popen",
                                        return_value=proc):
            job = dispatch._start_frame(["python"], {}, ".", "{}")
        try:
            answer = dispatch.tool_frame_status({"job_id": job.id}, _deps())
            self.assertIs(answer["running"], True)
            self.assertIs(proc.killed, False)
        finally:
            proc.finish.set()
            job.done.wait(timeout=5)

    def test_the_watchdog_kills_a_job_that_never_finishes(self):
        proc = _SlowProc()
        with unittest.mock.patch.object(dispatch.subprocess, "Popen",
                                        return_value=proc), \
                unittest.mock.patch.object(dispatch, "_FRAME_RUN_TIMEOUT_S", 0.3):
            job = dispatch._start_frame(["python"], {}, ".", "{}")
        self.assertTrue(job.done.wait(timeout=5))
        self.assertTrue(proc.killed)
        self.assertFalse(job.watchdog.is_alive())

    def test_the_job_is_closed_even_when_the_wait_fails(self):
        proc = _SlowProc()
        proc.finish.set()
        #: assertLogs both silences the traceback the reader logs and pins the
        #: fact that it was logged: a drain that fails silently would be worse
        #: than one that fails loudly.
        with self.assertLogs("midas_mcp.tools", level="ERROR"), \
                unittest.mock.patch.object(dispatch.subprocess, "Popen",
                                           return_value=proc), \
                unittest.mock.patch.object(proc, "wait",
                                           side_effect=RuntimeError("boom")):
            job = dispatch._start_frame(["python"], {}, ".", "{}")
            #: The patch has to stay open until the reader has used it: it runs
            #: on its own thread, and closing the context first would let the
            #: real wait() through and prove nothing.
            self.assertTrue(job.done.wait(timeout=5))
        self.assertTrue(proc.killed)


if __name__ == "__main__":
    unittest.main()
