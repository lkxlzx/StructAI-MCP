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
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
