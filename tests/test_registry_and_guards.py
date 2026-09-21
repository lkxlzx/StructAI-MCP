"""Offline unit tests for the MIDAS MCP connector core.

These run without any network: they exercise registry construction, the guards,
response normalization, and the payload-correction helpers.  Run with::

    python -m unittest discover -s tests -p 'test_*.py'
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("MIDAS_MAPI_KEY", "test-key")

from midas_mcp import (config, errors, guards, normalize,  # noqa: E402
                       registry, results)


class RegistryBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rel = json.loads((ROOT / "registry" / "registry.json")
                             .read_text(encoding="utf-8"))
        reporter = json.loads((ROOT / "registry" / "build_report.json")
                              .read_text(encoding="utf-8"))
        cls.report = reporter

    def test_upstream_section_count(self):
        self.assertEqual(self.report["totals"]["upstream_sections"], 505,
                         "upstream manual section count changed")

    def test_every_chapter_count_matches(self):
        for ch in self.report["chapters"]:
            self.assertTrue(ch["matches"],
                            f"{ch['chapter']}: parsed {ch['declared']} expected {ch['expected']}")

    def test_no_unmatched_local_rows(self):
        unmatched = [n for n in self.report["notes"] if "without upstream match" in n]
        self.assertEqual(unmatched, [], f"unmatched local rows: {unmatched[:5]}")

    def test_key_uniqueness(self):
        eps = self.rel["endpoints"]
        self.assertEqual(len(eps), len(set(eps)))

    def test_every_endpoint_is_well_formed(self):
        eps = self.rel["endpoints"]
        for key, v in eps.items():
            self.assertTrue(v["uri"], key)
            self.assertTrue(v["methods"], key)
            self.assertIn(v["wrapper"], ("Assign", "Argument"), key)
            self.assertTrue(v["namespace"], key)

    def test_db_collections_use_assign(self):
        """Every /db endpoint stores keyed records, so every DB wrapper must be
        ``Assign``.  Deriving the wrapper from the method set made LCOM-GEN and
        friends ``Argument``; MIDAS answers that with HTTP 400 "Wrong Field"
        while the ``Assign`` form returns 201 (verified live on Gen NX 2027).
        """
        eps = self.rel["endpoints"]
        wrong = [k for k, v in eps.items()
                 if v["namespace"] == "db" and v["wrapper"] != "Assign"]
        self.assertEqual(wrong, [], f"DB endpoints with a non-Assign wrapper: {wrong}")

    def test_local_rows_do_not_cross_namespaces(self):
        """A local row's URI decides which endpoint it annotates.  Matching on
        the bare short name let "15_OPE:44  POST /ope/LCOM-GEN" land on
        DB:LCOM-GEN and overwrite the DB wrapper with the OPE one."""
        eps = self.rel["endpoints"]
        for key in ("DB:LCOM-GEN", "DB:LCOM-CONC", "DB:LCOM-STEEL", "DB:LCOM-SRC"):
            self.assertEqual(eps[key]["wrapper"], "Assign", key)
        for key in ("OPE:LCOM-GEN", "OPE:LCOM-CONC", "OPE:LCOM-STEEL", "OPE:LCOM-SRC"):
            self.assertEqual(eps[key]["wrapper"], "Argument", key)
            self.assertEqual(eps[key]["uri"], "/ope/" + key.split(":")[-1], key)

    def test_method_corrections_present(self):
        """Doc-under-reported verbs that the live build does serve.  Losing
        these would make the connector refuse a call that actually works."""
        eps = self.rel["endpoints"]
        self.assertIn("GET", eps["DB:REBC"]["methods"],
                      "DB:REBC GET was verified live but is missing from the registry")
        self.assertIn("GET", eps["DESIGN:SRC:AIK-SRC2K:DSRC"]["methods"],
                      "DSRC GET was verified live but is missing from the registry")

    def test_endpoints_are_marked_not_removed(self):
        """Endpoints absent on Gen NX belong to other products (Civil NX,
        Civil Designer, Hyper-S).  They must stay in the registry, marked."""
        eps = self.rel["endpoints"]
        for key in ("DB:GSBG", "DB:CAMB", "DB:RCHK", "DB:EIGV-M1",
                    "OPE:GSBG", "DESIGN:SRC:AIK-SRC2K:OCHECK"):
            with self.subTest(key=key):
                self.assertIn(key, eps, f"{key} was dropped instead of marked")
                self.assertTrue(eps[key]["variant"],
                                f"{key} carries no product/variant marker")
                self.assertTrue(any("Kept in the registry" in n or "Hyper-S" in n
                                    for n in eps[key]["notes"]),
                                f"{key} has no explanatory note")

    def test_destructive_delete_semantics_are_recorded(self):
        """Verified live: the body-form delete on LCOM-GEN wipes the whole
        collection, so the danger must stay documented in the registry."""
        note = " ".join(self.rel["endpoints"]["DB:LCOM-GEN"]["notes"])
        self.assertIn("CLEARS THE WHOLE COLLECTION", note)
        self.assertIn("no path form", note)

    def test_story_definition_notes_are_correct(self):
        """Earlier this was believed to be a no-op stub; a live test with all
        15 fields disproved that, so the registry must not claim otherwise."""
        note = " ".join(self.rel["endpoints"]["DB:STOR"]["notes"])
        self.assertIn("15 fields are required", note)
        self.assertNotIn("no-op stub", note)

    def test_node_unknown_field_hazard_recorded(self):
        note = " ".join(self.rel["endpoints"]["DB:NODE"]["notes"])
        self.assertIn("silently ignored", note)
        self.assertIn("EMPTY node", note)

    def test_reference_keyed_endpoints_declare_their_family(self):
        """The crash guard keys off this field; losing it disarms the guard."""
        eps = self.rel["endpoints"]
        self.assertEqual(eps["DB:CONS"]["ref_family"], "NODE")
        self.assertEqual(eps["DB:CNLD"]["ref_family"], "NODE")
        self.assertEqual(eps["DB:BMLD"]["ref_family"], "ELEM")

    def test_registry_paths_pass_guard(self):
        reg = registry.Registry.load(ROOT / "registry")
        per = {k: v for k, v in reg._by_key.items()}
        for k, e in per.items():
            self.assertRegex(e.uri, r"^/(db|doc|ope|view|post|DESIGN)(/[A-Za-z0-9_.\-]+)*$", k)


class GuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = config.load_config([])
        cls.reg = registry.Registry.load(ROOT / "registry")
        cls.g = guards.Guards(cls.reg, cls.cfg)

    def test_reject_url_and_path_endpoints(self):
        for bad in ("http://x/db/NODE", "/db/NODE", "DB:../NODE", ""):
            with self.assertRaises(errors.InputError):
                self.g.validate_endpoint(bad)
        with self.assertRaises(errors.InputError):
            self.g.validate_endpoint("DB:NOPE")

    def test_alias_resolution(self):
        ep = self.g.validate_endpoint("NODE")
        self.assertEqual(ep.key, "DB:NODE")

    def test_empty_delete_refused(self):
        ep = self.g.validate_endpoint("DB:NODE")
        with self.assertRaises(errors.InputError):
            self.g.validate_ids(ep, [])

    def test_bulk_delete_requires_env(self):
        ep = self.g.validate_endpoint("DB:NODE")
        with self.assertRaises(errors.GuardError):
            self.g.refuse_bulk_delete(ep, True)

    def test_retry_policy(self):
        ep = self.g.validate_endpoint("DB:NODE")
        self.assertTrue(self.g.is_retryable(ep, "GET", 502))
        self.assertTrue(self.g.is_retryable(ep, "GET", 504))
        self.assertFalse(self.g.is_retryable(ep, "GET", 404))
        self.assertFalse(self.g.is_retryable(ep, "POST", 502))
        anal = self.g.validate_endpoint("DOC:ANAL")
        self.assertFalse(self.g.is_retryable(anal, "POST", 502))

    def test_stage_preflight_warns_when_no_boundary_group(self):
        """Defining DB:STAG with no DB:BNGR leaves the model unsolvable, and the
        later failure ('[错误] 边界条件 没有定义。') names neither the stage nor
        the missing group.  The write itself succeeds, so the only place the
        cause can be surfaced is at write time."""
        self.g._collection_present = lambda name: False
        ep = self.g.validate_endpoint("DB:STAG")
        hint = self.g.stage_preflight(ep, {"1": {"NAME": "S1", "NO": 1}})
        self.assertIsNotNone(hint)
        self.assertIn("DB:BNGR", hint)
        self.assertIn("ACT_BNGR", hint)
        self.assertIn("DB:STCT", hint)

    def test_stage_preflight_silent_once_the_group_exists(self):
        self.g._collection_present = lambda name: True
        ep = self.g.validate_endpoint("DB:STAG")
        self.assertIsNone(self.g.stage_preflight(ep, {"1": {}}))

    def test_stage_preflight_ignores_unrelated_endpoints(self):
        self.g._collection_present = lambda name: False
        for key in ("DB:NODE", "DB:CONS", "DB:LCOM-GEN"):
            self.assertIsNone(self.g.stage_preflight(self.g.validate_endpoint(key), {}))

    def test_stage_preflight_points_at_stag_when_stct_is_written(self):
        self.g._collection_present = lambda name: False
        ep = self.g.validate_endpoint("DB:STCT")
        self.assertIn("DB:STAG", self.g.stage_preflight(ep, {"1": {}}))

    def test_crash_guard_refuses_missing(self):
        # CONS/CNLD key on NODE. With no live ids resolvable (offline), the
        # guard is conservative and refuses rather than guessing.
        for ep_name in ("DB:CONS", "DB:CNLD", "DB:BMLD"):
            ep = self.g.validate_endpoint(ep_name)
            self.assertIn(ep.ref_family, ("NODE", "ELEM"), ep_name)
        # a ref-keyed write with a data record is refused when the id is unknown
        ep = self.g.validate_endpoint("DB:CONS")
        try:
            self.g.require_existing_refs(ep, {"9": {"ITEMS": []}})
            # if live ids happened to be resolvable and node 9 absent, refused;
            # offline the id list is empty so it refuses too
            self.fail("expected GuardError for missing node id")
        except errors.GuardError:
            pass
        except Exception as exc:  # offline: midas_get_ids may fail cleanly
            self.assertIsInstance(exc, errors.GuardError)

    def test_payload_corrections(self):
        # EIGV TYPE forced to LANCZOS
        data = {"1": {"TYPE": "EIGEN", "iFREQ": 3}}
        fixed = self.g.correct_payload(self.g.validate_endpoint("DB:EIGV"), "create", data)
        rec = fixed["1"]
        self.assertEqual(rec["TYPE"], "LANCZOS")
        # P_TYPE forced to 2
        data = {"1": {"TYPE": "STEEL", "PARAM": [{"P_TYPE": 1, "DB": "S355"}]}}
        fixed = self.g.correct_payload(self.g.validate_endpoint("DB:MATL"), "create", data)
        self.assertEqual(fixed["1"]["PARAM"][0]["P_TYPE"], 2)
        # export path backslashes
        data = {"x": {"EXPORT_PATH": "C:/MIDAS/a.json"}}
        self.g.correct_payload(self.g.validate_endpoint("VIEW:CAPTURE"), "create", data)
        import copy
        fxd = self.g.correct_payload(self.g.validate_endpoint("VIEW:CAPTURE"), "create",
                                     copy.deepcopy({"x": {"EXPORT_PATH": "C:/MIDAS/a.json"}}))
        self.assertIn("\\", fxd["x"]["EXPORT_PATH"])
        self.assertNotIn("C:/", fxd["x"]["EXPORT_PATH"])

    def test_wrapper_strip(self):
        cleaned = self.g.strip_wrapper({"Assign": {"1": {}}, "data": {}})
        self.assertNotIn("Assign", cleaned)
        self.assertNotIn("data", cleaned)


class _FakeResponse:
    def __init__(self, status, raw='{"message":""}'):
        self.status = status
        self.raw = raw
        self.body = json.loads(raw) if raw.strip().startswith("{") else None
        self.ok_by_status = 200 <= status < 300


class _FakeClient:
    """Records requests and replays scripted responses (offline dispatch tests)."""

    def __init__(self, responses=None):
        self.calls: list[tuple] = []
        self.responses = responses or {}

    def request(self, method, path, body=None, **kw):
        self.calls.append((method, path, body))
        for (m, p), resp in self.responses.items():
            if m == method and p == path:
                return _FakeResponse(*resp) if isinstance(resp, tuple) else resp
        return _FakeResponse(200)

    def cancel_in_flight(self):
        pass


class DispatchTests(unittest.TestCase):
    """Regression cover for silent-failure bugs found on the live build."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("MIDAS_MCP_ALLOW_BULK_DELETE", "0")
        cls.reg = registry.Registry.load(ROOT / "registry")
        cls.cfg = config.load_config([])

    def _deps(self, client):
        g = guards.Guards(self.reg, self.cfg)
        return lambda: (g, client, self.reg)

    def test_delete_issues_one_request_per_id(self):
        """Deleting [a, b] must not silently delete only a."""
        from midas_mcp import dispatch
        client = _FakeClient()
        dispatch.tool_db_delete(
            {"endpoint": "DB:NODE", "target_ids": ["710001", "710002"]},
            self._deps(client))
        paths = [p for (m, p, _b) in client.calls if m == "DELETE"]
        self.assertEqual(paths, ["/db/NODE/710001", "/db/NODE/710002"])

    def test_delete_verifies_the_record_is_gone(self):
        """MIDAS answers 200 to DELETE for an id that never existed, so a bare
        200 must not be reported as success."""
        from midas_mcp import dispatch
        client = _FakeClient(responses={
            ("DELETE", "/db/NODE/710001"): (200, '{"message":""}'),
            ("GET", "/db/NODE/710001"): (200, '{"NODE":{"710001":{"X":1}}}'),
        })
        result = dispatch.tool_db_delete(
            {"endpoint": "DB:NODE", "target_ids": ["710001"]}, self._deps(client))
        self.assertFalse(result["ok"], "a still-present record was reported as deleted")
        self.assertIn("still present", json.dumps(result))

    def test_delete_reports_success_when_readback_is_empty(self):
        from midas_mcp import dispatch
        client = _FakeClient(responses={
            ("DELETE", "/db/NODE/710001"): (200, '{"message":""}'),
            ("GET", "/db/NODE/710001"): (400, '{"error":{"message":"Not Found Key"}}'),
        })
        result = dispatch.tool_db_delete(
            {"endpoint": "DB:NODE", "target_ids": ["710001"]}, self._deps(client))
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["deleted"], ["710001"])

    def test_doc_file_command_unwraps_object_argument(self):
        """`{"EXPORT_PATH": ...}` must be sent as the bare string the API wants;
        the object form is answered with a 200 carrying 'path is wrong'."""
        from midas_mcp import dispatch
        client = _FakeClient()
        dispatch.tool_doc({"command": "EXPORT",
                           "argument": {"EXPORT_PATH": "C:/tmp/a.json"}},
                          self._deps(client))
        _m, path, body = client.calls[-1]
        self.assertEqual(path, "/doc/EXPORT")
        self.assertIsInstance(body["Argument"], str)
        self.assertEqual(body["Argument"], "C:\\tmp\\a.json")

    def test_doc_file_command_requires_a_path(self):
        from midas_mcp import dispatch
        with self.assertRaises(errors.InputError):
            dispatch.tool_doc({"command": "EXPORT", "argument": {}},
                              self._deps(_FakeClient()))

    def test_anal_400_warning_is_not_reported_as_failure(self):
        """Live Gen NX 2027: with a forced displacement (DB:SDSP) present,
        POST /doc/ANAL answers HTTP 400 carrying
        '{"error":{"message":"[警告] 强制位移在 反应谱分析中设为零。"}}' - and the
        analysis still runs (POST/TABLE then returns real DEAD(ST) and
        EQ_X(RS) rows).  Reporting that as a failure tells the caller no
        results exist when they do."""
        from midas_mcp import dispatch
        body = json.dumps({"error": {"message": "[警告] 强制位移在 反应谱分析中设为零。"}})
        client = _FakeClient(responses={("POST", "/doc/ANAL"): (400, body)})
        result = dispatch.tool_doc({"command": "ANAL", "argument": {}},
                                   self._deps(client))
        self.assertTrue(result["ok"], "a [警告] warning was reported as a failure")
        self.assertEqual(result["category"], "OK_WITH_WARNING")
        self.assertIn("\u8b66\u544a", result["warning"])
        self.assertIn("warning", json.dumps(result, ensure_ascii=False))

    def test_anal_plain_400_is_still_a_failure(self):
        """Only a [警告] body is a warning; any other 400 stays a failure."""
        from midas_mcp import dispatch
        client = _FakeClient(responses={
            ("POST", "/doc/ANAL"): (400, '{"error":{"message":"Wrong Field"}}'),
        })
        result = dispatch.tool_doc({"command": "ANAL", "argument": {}},
                                   self._deps(client))
        self.assertFalse(result["ok"])
        self.assertNotEqual(result.get("category"), "OK_WITH_WARNING")

    def test_anal_success_keeps_its_note(self):
        from midas_mcp import dispatch
        client = _FakeClient(responses={
            ("POST", "/doc/ANAL"): (200, '{"message":""}'),
        })
        result = dispatch.tool_doc({"command": "ANAL", "argument": {}},
                                   self._deps(client))
        self.assertTrue(result["ok"])
        self.assertIn("POST:TABLE", result["note"])

    def test_the_anal_body_is_the_documented_empty_object(self):
        """``/doc/ANAL`` documents the ordinary analysis as a bare ``{}``.

        Sending ``{"Argument": {}}`` instead is tolerated by Gen NX 2027 but
        crashed CIVIL NX 2026, so the documented shape is the one that goes out.
        Every other doc command keeps the Argument wrapper its registry entry
        declares - NEW is checked here because that is the wrapper CIVIL NX
        accepted on the same run.
        """
        from midas_mcp import dispatch
        client = _FakeClient(responses={
            ("POST", "/doc/ANAL"): (200, '{"message":""}'),
            ("POST", "/doc/NEW"): (200, '{"message":""}'),
        })
        dispatch.tool_doc({"command": "ANAL", "argument": {}}, self._deps(client))
        self.assertEqual(client.calls[-1][2], {})
        dispatch.tool_doc({"command": "ANAL", "argument": {"TYPE": "Pushover"}},
                          self._deps(client))
        self.assertEqual(client.calls[-1][2], {"Argument": {"TYPE": "Pushover"}})
        dispatch.tool_doc({"command": "NEW", "argument": {}}, self._deps(client))
        self.assertEqual(client.calls[-1][2], {"Argument": {}})

    def test_stag_write_carries_the_preflight_warning(self):
        """A successful DB:STAG write with no boundary group is reported ok but
        annotated, because the consequence (an unexplained analysis refusal)
        shows up much later."""
        from midas_mcp import dispatch
        deps = self._deps(_FakeClient(responses={
            ("POST", "/db/STAG"): (201, '{"STAG":{"1":{"NAME":"S1","NO":1}}}'),
        }))
        deps()[0]._collection_present = lambda name: False
        result = dispatch.tool_db_assign(
            {"endpoint": "DB:STAG", "mode": "create",
             "data": {"1": {"NAME": "S1", "NO": 1}}}, deps)
        self.assertTrue(result["ok"])
        self.assertIn("DB:BNGR", result["warning"])

    def test_ordinary_write_has_no_stage_warning(self):
        from midas_mcp import dispatch
        deps = self._deps(_FakeClient(responses={
            ("POST", "/db/STLD"): (201, '{"STLD":{"1":{"NAME":"DEAD"}}}'),
        }))
        deps()[0]._collection_present = lambda name: False
        result = dispatch.tool_db_assign(
            {"endpoint": "DB:STLD", "mode": "create",
             "data": {"1": {"NAME": "DEAD", "TYPE": "USER"}}}, deps)
        self.assertTrue(result["ok"])
        self.assertNotIn("warning", result)

    def test_table_reports_load_names_that_produced_no_rows(self):
        """MIDAS answers HTTP 200 and silently omits an unrecognised load name,
        so a combination asked for without '(CB)' looks exactly like a
        combination that has no results.  The two must be told apart."""
        from midas_mcp import dispatch
        body = json.dumps({"TRUSSFORCE": {
            "HEAD": ["Index", "Elem", "Load", "Force-I", "Force-J"],
            "DATA": [["1", "1", "DEAD", "1.0", "-1.0"]]}})
        ep = self.reg.lookup("POST:TABLE:TRUSSFORCE")
        result = dispatch._annotate_result(
            ep, {"ok": True},
            body, data_hint={"LOAD_CASE_NAMES": ["DEAD(ST)", "ULS-01"]})
        joined = " ".join(result["hints"])
        self.assertIn("ULS-01", joined)
        self.assertNotIn("'DEAD'", joined)

    def test_table_stays_quiet_when_every_requested_name_returned(self):
        from midas_mcp import dispatch
        body = json.dumps({"TRUSSFORCE": {
            "HEAD": ["Index", "Elem", "Load", "Force-I", "Force-J"],
            "DATA": [["1", "1", "DEAD", "1.0", "-1.0"],
                     ["2", "1", "ULS-01", "2.0", "-2.0"]]}})
        ep = self.reg.lookup("POST:TABLE:TRUSSFORCE")
        result = dispatch._annotate_result(
            ep, {"ok": True},
            body, data_hint={"LOAD_CASE_NAMES": ["DEAD(ST)", "ULS-01(CB)"]})
        self.assertNotIn("no rows", " ".join(result["hints"]))

    def test_table_load_name_check_survives_an_unparseable_body(self):
        from midas_mcp import dispatch
        ep = self.reg.lookup("POST:TABLE:TRUSSFORCE")
        result = dispatch._annotate_result(
            ep, {"ok": True}, "not json",
            data_hint={"LOAD_CASE_NAMES": ["DEAD(ST)"]})
        self.assertNotIn("no rows", " ".join(result["hints"]))


class _Clock:
    """Stand-in for the ``time`` module so the id-snapshot TTL can be moved by
    hand instead of slept through.  Only ``midas_http.time`` is replaced."""

    def __init__(self):
        self.now = 1000.0

    def monotonic(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds

    def time(self):
        return self.now

    def sleep(self, _seconds):
        pass


class IdCacheTests(unittest.TestCase):
    """The id snapshot the crash guard reads must expire, and a write to a
    collection must drop that collection's snapshot.

    Without this, a NODE created after an earlier snapshot is invisible to
    ``guards.require_existing_refs``, which then refuses a ref-keyed write with
    "keys records on NODE ids that do not exist" for a node that does exist - a
    bogus refusal that reads like a modelling error and cannot be explained
    from the message.
    """

    @classmethod
    def setUpClass(cls):
        cls.reg = registry.Registry.load(ROOT / "registry")
        cls.cfg = config.load_config([])

    def setUp(self):
        from midas_mcp import midas_http
        self.http = midas_http
        self._orig_client = midas_http.MidasClient
        self._orig_time = midas_http.time
        self.clock = _Clock()
        midas_http.time = self.clock
        midas_http.invalidate_id_cache()
        # ``midas_get_ids`` builds a module-level client; give it a recording
        # fake whose NODE collection is empty.
        self.client = _FakeClient(responses={
            ("GET", "/db/NODE"): (200, '{"NODE":{}}'),
        })
        midas_http.MidasClient = lambda cfg: self.client

    def tearDown(self):
        self.http.MidasClient = self._orig_client
        self.http.time = self._orig_time
        self.http.invalidate_id_cache()

    # -- helpers ----------------------------------------------------------
    def _deps(self, client):
        g = guards.Guards(self.reg, self.cfg)
        return lambda: (g, client, self.reg)

    def _reads(self, path="/db/NODE"):
        return [c for c in self.client.calls if c[0] == "GET" and c[1] == path]

    def _snapshot_present(self, family="NODE"):
        return family in self.http._id_cache

    #: Fallback for the window when the module defines none - which is the
    #: defect under test.  The window assertions below must fail on behaviour,
    #: not on a missing name.
    _DEFAULT_TTL_S = 5.0

    def _ttl(self):
        return getattr(self.http, "_ID_CACHE_TTL_S", self._DEFAULT_TTL_S)

    # -- the window -------------------------------------------------------
    def test_the_window_is_finite_and_short(self):
        """A snapshot that never expires is the defect: it must have a window,
        and the window must stay short (the GUI can edit the model too)."""
        ttl = self.http._ID_CACHE_TTL_S
        self.assertGreater(ttl, 0)
        self.assertLessEqual(ttl, 30)

    def test_snapshot_is_reused_within_the_ttl(self):
        """The cache must still exist: a guarded write cannot re-read NODE on
        every call."""
        self.assertEqual(self.http.midas_get_ids(self.cfg, "NODE"), [])
        self.clock.advance(self._ttl() / 2)
        self.assertEqual(self.http.midas_get_ids(self.cfg, "NODE"), [])
        self.assertEqual(len(self._reads()), 1,
                         "a snapshot inside the TTL was re-read instead of reused")

    def test_snapshot_is_not_reused_after_the_ttl(self):
        self.assertEqual(self.http.midas_get_ids(self.cfg, "NODE"), [])
        self.client.responses[("GET", "/db/NODE")] = (
            200, '{"NODE":{"1":{"X":0,"Y":0,"Z":0}}}')
        self.clock.advance(self._ttl() + 0.1)
        self.assertEqual(self.http.midas_get_ids(self.cfg, "NODE"), ["1"],
                         "an expired snapshot was served from the cache")
        self.assertEqual(len(self._reads()), 2)

    # -- invalidation on write --------------------------------------------
    def test_assign_drops_that_familys_snapshot(self):
        from midas_mcp import dispatch
        self.http.midas_get_ids(self.cfg, "NODE")
        self.assertTrue(self._snapshot_present())
        client = _FakeClient(responses={
            ("POST", "/db/NODE"): (201, '{"NODE":{"1":{"X":0,"Y":0,"Z":0}}}'),
        })
        result = dispatch.tool_db_assign(
            {"endpoint": "DB:NODE", "mode": "create",
             "data": {"1": {"X": 0, "Y": 0, "Z": 0}}}, self._deps(client))
        self.assertTrue(result["ok"], result)
        self.assertFalse(self._snapshot_present(),
                         "a successful DB:NODE write kept the stale NODE snapshot")

    def test_delete_drops_that_familys_snapshot(self):
        from midas_mcp import dispatch
        self.http.midas_get_ids(self.cfg, "NODE")
        self.assertTrue(self._snapshot_present())
        client = _FakeClient(responses={
            ("DELETE", "/db/NODE/710001"): (200, '{"message":""}'),
            ("GET", "/db/NODE/710001"): (400, '{"error":{"message":"Not Found Key"}}'),
        })
        result = dispatch.tool_db_delete(
            {"endpoint": "DB:NODE", "target_ids": ["710001"]}, self._deps(client))
        self.assertTrue(result["ok"], result)
        self.assertFalse(self._snapshot_present(),
                         "a successful delete kept the stale NODE snapshot")

    def test_a_partially_failed_delete_still_drops_the_snapshot(self):
        """One id deleted, one refused: the deleted id must not survive in the
        snapshot, or the guard later *permits* a write keyed on it."""
        from midas_mcp import dispatch
        self.http.midas_get_ids(self.cfg, "NODE")
        self.assertTrue(self._snapshot_present())
        client = _FakeClient(responses={
            ("DELETE", "/db/NODE/1"): (200, '{"message":""}'),
            ("GET", "/db/NODE/1"): (400, '{"error":{"message":"Not Found Key"}}'),
            ("DELETE", "/db/NODE/2"): (400, '{"error":{"message":"Wrong Field"}}'),
        })
        result = dispatch.tool_db_delete(
            {"endpoint": "DB:NODE", "target_ids": ["1", "2"]}, self._deps(client))
        self.assertFalse(result["ok"])
        self.assertEqual(result["category"], "MIDAS_REJECTED")
        self.assertEqual(result["deleted"], ["1"])
        self.assertFalse(self._snapshot_present(),
                         "a partial delete kept the just-deleted id in the snapshot")

    def test_model_replacing_doc_command_drops_every_snapshot(self):
        from midas_mcp import dispatch
        for command in ("NEW", "OPEN", "IMPORT", "IMPORTMXT", "CLOSE"):
            with self.subTest(command=command):
                self.http.midas_get_ids(self.cfg, "NODE")
                self.http.midas_get_ids(self.cfg, "ELEM")
                self.assertEqual(sorted(self.http._id_cache), ["ELEM", "NODE"])
                argument = ({"FILE_PATH": "C:/tmp/model.mxt"}
                            if command in ("OPEN", "IMPORT", "IMPORTMXT") else {})
                client = _FakeClient(responses={
                    ("POST", f"/doc/{command}"): (200, '{"message":""}'),
                })
                result = dispatch.tool_doc({"command": command, "argument": argument},
                                           self._deps(client))
                self.assertTrue(result["ok"], result)
                self.assertEqual(self.http._id_cache, {},
                                 f"DOC:{command} replaced the model but kept the "
                                 f"id snapshots")

    def test_ope_actions_that_mint_ids_drop_both_families(self):
        """``OPE:AUTOMESH``/``OPE:DIVIDEELEM`` are not ``DB:`` endpoints, but
        they create nodes/elements: a pre-mesh ELEM snapshot would otherwise
        refuse a valid write keyed on a freshly meshed element."""
        from midas_mcp import dispatch
        for key in ("OPE:AUTOMESH", "OPE:DIVIDEELEM"):
            with self.subTest(endpoint=key):
                self.http.midas_get_ids(self.cfg, "NODE")
                self.http.midas_get_ids(self.cfg, "ELEM")
                self.assertEqual(sorted(self.http._id_cache), ["ELEM", "NODE"])
                client = _FakeClient(responses={
                    ("POST", "/ope/" + key.split(":", 1)[1]): (200, '{"message":""}'),
                })
                result = dispatch.tool_db_assign(
                    {"endpoint": key, "mode": "create",
                     "data": {"1": {"NAME": "A1"}}}, self._deps(client))
                self.assertTrue(result["ok"], result)
                self.assertEqual(self.http._id_cache, {},
                                 f"{key} mints ids but kept the NODE/ELEM snapshots")

    def test_a_failed_read_is_not_cached(self):
        """A transport error or a 404 is not evidence that a collection is
        empty; caching the [] refuses every guarded write for a whole TTL."""
        for status, raw in ((0, "transport error: connection refused"),
                            (404, '{"error":{"message":"Not Found Key"}}')):
            with self.subTest(status=status):
                self.http.invalidate_id_cache()
                self.client.calls.clear()
                self.client.responses[("GET", "/db/NODE")] = (status, raw)
                self.assertEqual(self.http.midas_get_ids(self.cfg, "NODE"), [])
                self.assertFalse(self._snapshot_present(),
                                 "a failed read was cached as an empty collection")
                self.assertEqual(self.http.midas_get_ids(self.cfg, "NODE"), [])
                self.assertEqual(len(self._reads()), 2,
                                 "the second call reused the failed read")

    def test_a_read_racing_an_invalidate_does_not_store(self):
        """A fetch that began before a write must not store its list after the
        write dropped it - that would undo the invalidation for a whole TTL."""
        from midas_mcp import midas_http
        racing = _FakeClient(responses={
            ("GET", "/db/NODE"): (200, '{"NODE":{"1":{"X":0}}}')})

        class _Racing:
            def request(self, method, path, body=None, **kw):
                resp = racing.request(method, path, body, **kw)
                midas_http.invalidate_id_cache("NODE")  # a concurrent write
                return resp

        self.http.MidasClient = lambda cfg: _Racing()
        self.assertEqual(self.http.midas_get_ids(self.cfg, "NODE"), ["1"])
        self.assertFalse(self._snapshot_present(),
                         "a read that raced an invalidation resurrected the snapshot")
        self.assertEqual(self.http.midas_get_ids(self.cfg, "NODE"), ["1"])
        self.assertEqual(len(racing.calls), 2, "the raced read was reused")

    def test_a_plain_doc_command_keeps_the_snapshots(self):
        """Only the model-replacing commands drop everything; SAVE does not
        touch the ids."""
        from midas_mcp import dispatch
        self.http.midas_get_ids(self.cfg, "NODE")
        client = _FakeClient(responses={("POST", "/doc/SAVE"): (200, '{"message":""}')})
        result = dispatch.tool_doc({"command": "SAVE", "argument": {}},
                                   self._deps(client))
        self.assertTrue(result["ok"], result)
        self.assertTrue(self._snapshot_present())

    # -- the symptom this all exists for -----------------------------------
    def test_a_node_created_by_assign_is_visible_to_the_crash_guard(self):
        """Snapshot an empty NODE, create node 1, then write a node-keyed
        record: the guard must not claim node 1 does not exist."""
        from midas_mcp import dispatch
        g = guards.Guards(self.reg, self.cfg)
        cons = g.validate_endpoint("DB:CONS")
        self.assertEqual(cons.ref_family, "NODE")
        # the snapshot is taken while NODE is empty
        self.assertEqual(self.http.midas_get_ids(self.cfg, "NODE"), [])
        with self.assertRaises(errors.GuardError):
            g.require_existing_refs(cons, {"1": {"ITEMS": []}})
        # ... the node is created ...
        client = _FakeClient(responses={
            ("POST", "/db/NODE"): (201, '{"NODE":{"1":{"X":0,"Y":0,"Z":0}}}'),
        })
        result = dispatch.tool_db_assign(
            {"endpoint": "DB:NODE", "mode": "create",
             "data": {"1": {"X": 0, "Y": 0, "Z": 0}}}, self._deps(client))
        self.assertTrue(result["ok"], result)
        # ... so NODE is no longer empty, and the guard must see it even though
        # the TTL has not elapsed.
        self.client.responses[("GET", "/db/NODE")] = (
            200, '{"NODE":{"1":{"X":0,"Y":0,"Z":0}}}')
        try:
            g.require_existing_refs(cons, {"1": {"ITEMS": []}})
        except errors.GuardError as exc:
            self.fail(f"bogus refusal after the node was created: {exc}")

    def test_a_deleted_node_is_not_permitted_by_a_stale_snapshot(self):
        """The mirror of the create case: after a delete the guard must consult
        fresh ids, or it lets through a constraint keyed on a node MIDAS no
        longer has - the crash this guard exists to prevent."""
        from midas_mcp import dispatch
        g = guards.Guards(self.reg, self.cfg)
        cons = g.validate_endpoint("DB:CONS")
        self.client.responses[("GET", "/db/NODE")] = (
            200, '{"NODE":{"1":{"X":0,"Y":0,"Z":0}}}')
        self.assertEqual(self.http.midas_get_ids(self.cfg, "NODE"), ["1"])
        # the snapshot says node 1 exists, so the guard lets the write through
        g.require_existing_refs(cons, {"1": {"ITEMS": []}})
        # node 1 is deleted, and MIDAS no longer has it
        client = _FakeClient(responses={
            ("DELETE", "/db/NODE/1"): (200, '{"message":""}'),
            ("GET", "/db/NODE/1"): (400, '{"error":{"message":"Not Found Key"}}'),
        })
        result = dispatch.tool_db_delete(
            {"endpoint": "DB:NODE", "target_ids": ["1"]}, self._deps(client))
        self.assertTrue(result["ok"], result)
        self.client.responses[("GET", "/db/NODE")] = (200, '{"NODE":{}}')
        with self.assertRaises(errors.GuardError):
            g.require_existing_refs(cons, {"1": {"ITEMS": []}})


class ModalResultTests(unittest.TestCase):
    """The modal/eigen summary lives in SUB_TABLES, not in the top-level DATA.

    The fixture below is a trimmed copy of a real ``POST:TABLE:EIGENVALUEMODE``
    reply from Gen NX 2027: the top level carries per-node mode shapes and no
    frequency or period anywhere, and the summary is in ``SUB_TABLES``.  A
    parser that reads only the top level reports "no modal summary" for this
    exact response.
    """

    HEAD = ["Index", "Node", "Mode", "UX", "UY", "UZ", "RX", "RY", "RZ"]

    @classmethod
    def setUpClass(cls):
        cls.reg = registry.Registry.load(ROOT / "registry")

    def _body(self, sub_tables=None):
        return json.dumps({"EIGENVALUEMODE": {
            "FORCE": "KN", "DIST": "M", "HEAD": self.HEAD,
            "DATA": [["1", "1", "1", "0.0035", "-0.0216", "0.0011", "0", "0", "0"],
                     ["2", "2", "1", "0.0036", "-0.0235", "0.0053", "0", "0", "0"]],
            "SUB_TABLES": sub_tables if sub_tables is not None else [
                {"EIGENVALUE ANALYSIS": {
                    "HEAD": ["ModeNo", "Frequency(rad/sec)", "Frequency(cycle/sec)",
                             "Period(sec)", "Tolerance"],
                    "DATA": [["1.0000", "16.5563", "2.6350", "0.3795", "0.0000e+00"],
                             ["2.0000", "19.0657", "3.0344", "0.3296", "0.0000e+00"],
                             ["3.0000", "22.4064", "3.5661", "0.2804", "0.0000e+00"]]}},
                {"MODAL PARTICIPATION MASSES PRINTOUT (1)": {
                    "HEAD": ["ModeNo", "TRAN-XMASS(%)", "TRAN-XSUM(%)",
                             "TRAN-YMASS(%)", "TRAN-YSUM(%)", "TRAN-ZMASS(%)",
                             "TRAN-ZSUM(%)", "ROTN-XMASS(%)", "ROTN-XSUM(%)",
                             "ROTN-YMASS(%)", "ROTN-YSUM(%)", "ROTN-ZMASS(%)",
                             "ROTN-ZSUM(%)"],
                    "DATA": [["1.0000", "1.6520", "1.6520", "6.8313", "6.8313",
                              "75.0693", "75.0693", "0", "0", "0", "0", "0", "0"],
                             ["2.0000", "60.9800", "62.6320", "3.2000", "10.0313",
                              "5.0000", "80.0693", "0", "0", "0", "0", "0", "0"],
                             ["3.0000", "10.0000", "72.6320", "40.0000", "50.0313",
                              "1.0000", "81.0693", "0", "0", "0", "0", "0", "0"]]}},
                {"MODAL DIRECTION FACTOR PRINTOUT": {
                    "HEAD": ["ModeNo", "TRAN-XValue", "TRAN-YValue", "TRAN-ZValue",
                             "ROTN-XValue", "ROTN-YValue", "ROTN-ZValue"],
                    "DATA": [["1.0000", "1.7871", "7.7728", "90.4402", "0", "0", "0"],
                             ["2.0000", "64.1954", "3.0000", "2.0000", "0", "0", "0"],
                             ["3.0000", "9.0000", "65.0121", "1.0000", "0", "0", "0"]]}},
            ]}})

    def test_modal_summary_is_parsed_from_sub_tables(self):
        modal = results.modal_result(self._body())
        self.assertIsNotNone(modal)
        self.assertEqual(modal["source"], "SUB_TABLES")
        self.assertEqual(modal["mode_count"], 3)
        self.assertEqual([m["mode"] for m in modal["modes"]], [1, 2, 3])
        first = modal["modes"][0]
        self.assertAlmostEqual(first["frequency_hz"], 2.6350)
        self.assertAlmostEqual(first["frequency_rad_s"], 16.5563)
        self.assertAlmostEqual(first["period_s"], 0.3795)

    def test_summary_exists_even_when_the_primary_table_is_empty(self):
        """NODE/ELEM rows being absent says nothing about the summary."""
        body = json.dumps({"EIGENVALUEMODE": {
            "HEAD": self.HEAD, "DATA": [],
            "SUB_TABLES": [{"EIGENVALUE ANALYSIS": {
                "HEAD": ["ModeNo", "Frequency(cycle/sec)", "Period(sec)"],
                "DATA": [["1.0000", "2.6350", "0.3795"]]}}]}})
        modal = results.modal_result(body)
        self.assertIsNotNone(modal)
        self.assertEqual(modal["mode_count"], 1)

    def test_missing_columns_become_none_not_a_failed_result(self):
        """Only Frequency and Period present: still a modal result."""
        body = json.dumps({"EIGENVALUEMODE": {
            "HEAD": self.HEAD, "DATA": [],
            "SUB_TABLES": [{"EIGENVALUE ANALYSIS": {
                "HEAD": ["ModeNo", "Frequency(cycle/sec)", "Period(sec)"],
                "DATA": [["1.0000", "2.6350", "0.3795"]]}}]}})
        modal = results.modal_result(body)
        first = modal["modes"][0]
        self.assertAlmostEqual(first["frequency_hz"], 2.6350)
        self.assertAlmostEqual(first["period_s"], 0.3795)
        self.assertIsNone(first["frequency_rad_s"])
        self.assertIsNone(first["tolerance"])
        self.assertIsNone(first.get("participation_mass_ratio"))

    def test_modes_keep_midas_order_and_all_are_returned(self):
        sub = [{"EIGENVALUE ANALYSIS": {
            "HEAD": ["ModeNo", "Frequency(cycle/sec)", "Period(sec)"],
            "DATA": [[f"{i}.0000", f"{i}.5000", f"{1.0 / i:.4f}"]
                     for i in range(1, 21)]}}]
        modal = results.modal_result(self._body(sub_tables=sub))
        self.assertEqual(modal["mode_count"], 20)
        self.assertEqual([m["mode"] for m in modal["modes"]], list(range(1, 21)))

    def test_participation_and_direction_factors_are_read_not_computed(self):
        modal = results.modal_result(self._body())
        self.assertAlmostEqual(
            modal["modes"][0]["participation_mass_ratio"]["UX"], 1.6520)
        self.assertAlmostEqual(
            modal["modes"][0]["direction_factor"]["UZ"], 90.4402)
        # Rotation columns are ROTN-X/Y/Z in MIDAS but RX/RY/RZ canonically.
        self.assertAlmostEqual(
            modal["modes"][0]["participation_mass_ratio"]["RX"], 0.0)
        # Cumulative is the LAST row's SUM column, not a sum recomputed here.
        self.assertAlmostEqual(modal["cumulative_ratio_percent"]["UX"], 72.6320)
        self.assertAlmostEqual(modal["cumulative_ratio_percent"]["UZ"], 81.0693)
        self.assertEqual(modal["first_mode_by_axis"]["UX"]["mode"], 2)
        self.assertEqual(modal["first_mode_by_axis"]["UZ"]["mode"], 1)

    def test_raw_sub_tables_are_kept_for_traceability(self):
        modal = results.modal_result(self._body())
        self.assertIn("EIGENVALUEMODE :: EIGENVALUE ANALYSIS", modal["raw"])
        self.assertIn("EIGENVALUEMODE", modal["tables"])

    def test_no_modal_data_returns_none(self):
        body = json.dumps({"TRUSSFORCE": {
            "HEAD": ["Index", "Elem", "Load", "Force-I"],
            "DATA": [["1", "1", "DEAD", "1.0"]]}})
        self.assertIsNone(results.modal_result(body))

    def test_modal_result_survives_an_unparseable_body(self):
        self.assertIsNone(results.modal_result("not json"))
        self.assertIsNone(results.modal_result(None))
        self.assertEqual(results.result_summary("not json"), {})

    def test_result_summary_is_attached_to_the_table_tool_result(self):
        from midas_mcp import dispatch
        ep = self.reg.lookup("POST:TABLE:EIGENVALUEMODE")
        result = dispatch._annotate_result(ep, {"ok": True}, self._body())
        summary = result["result_summary"]
        self.assertIn("modal_result", summary)
        self.assertEqual(summary["modal_result"]["mode_count"], 3)
        self.assertTrue(any("SUB_TABLES" in h for h in result["hints"]))

    def test_a_modal_question_routes_to_the_eigen_table(self):
        from midas_mcp import dispatch
        for ask in ("第1阶频率是多少", "modal period", "participation mass",
                    "结构自振周期", "Eigenvalue Summary", "振型方向因子"):
            self.assertEqual(dispatch.modal_question(ask),
                             "POST:TABLE:EIGENVALUEMODE", ask)
        self.assertEqual(dispatch.modal_question("buckling factor"),
                         "POST:TABLE:BUCKLINGMODE")
        self.assertIsNone(dispatch.modal_question("max displacement"))

    def test_buckling_summary_is_parsed_from_sub_tables(self):
        body = json.dumps({"BUCKLINGMODE": {
            "HEAD": ["Index", "Mode"], "DATA": [["1", "1"]],
            "SUB_TABLES": [{"BUCKLING ANALYSIS": {
                "HEAD": ["ModeNo", "Eigenvalue", "Tolerance"],
                "DATA": [["1.0000", "497.6117", "3.3391e-33"],
                         ["2.0000", "525.6576", "9.3586e-29"]]}}]}})
        buck = results.buckling_result(body)
        self.assertIsNotNone(buck)
        self.assertEqual(buck["mode_count"], 2)
        self.assertAlmostEqual(buck["modes"][0]["eigenvalue"], 497.6117)

    def test_rotation_columns_are_rotn_letter_not_rotn_rx(self):
        """MIDAS writes ``ROTN-X``, so a parser looking up ``ROTN-RX`` silently
        returns null for every rotational participation value."""
        body = json.dumps({"EIGENVALUEMODE": {
            "HEAD": self.HEAD, "DATA": [],
            "SUB_TABLES": [
                {"MODAL PARTICIPATION MASSES PRINTOUT (1)": {
                    "HEAD": ["ModeNo", "TRAN-XMASS(%)", "TRAN-XSUM(%)",
                             "ROTN-XMASS(%)", "ROTN-XSUM(%)"],
                    "DATA": [["1.0000", "10.0", "10.0", "2.5", "2.5"]]}},
                {"MODAL DIRECTION FACTOR PRINTOUT": {
                    "HEAD": ["ModeNo", "ROTN-XValue", "ROTN-YValue", "ROTN-ZValue"],
                    "DATA": [["1.0000", "3.0", "4.0", "5.0"]]}}]}})
        modal = results.modal_result(body)
        rec = modal["modes"][0]
        self.assertAlmostEqual(rec["participation_mass_ratio"]["RX"], 2.5)
        self.assertAlmostEqual(rec["cumulative_ratio"]["RX"], 2.5)
        self.assertAlmostEqual(rec["direction_factor"]["RX"], 3.0)
        self.assertAlmostEqual(rec["direction_factor"]["RZ"], 5.0)
        # The canonical keys must not leak the raw MIDAS spelling.
        self.assertNotIn("ROTN-X", rec["direction_factor"])
        self.assertNotIn("ROTN-RX", rec["direction_factor"])

    def test_partial_modal_tables_still_parse(self):
        """Frequency+Period, then +participation, then +direction factor: each
        must parse.  A missing table yields null fields, never a failed result."""
        freq = {"EIGENVALUE ANALYSIS": {
            "HEAD": ["ModeNo", "Frequency(cycle/sec)", "Period(sec)"],
            "DATA": [["1.0000", "2.6350", "0.3795"]]}}
        part = {"MODAL PARTICIPATION MASSES PRINTOUT (1)": {
            "HEAD": ["ModeNo", "TRAN-XMASS(%)", "TRAN-XSUM(%)"],
            "DATA": [["1.0000", "1.65", "1.65"]]}}
        direc = {"MODAL DIRECTION FACTOR PRINTOUT": {
            "HEAD": ["ModeNo", "TRAN-XValue"], "DATA": [["1.0000", "1.79"]]}}

        only_freq = results.modal_result(self._body(sub_tables=[freq]))
        self.assertEqual(only_freq["mode_count"], 1)
        self.assertIsNone(only_freq["modes"][0].get("direction_factor"))
        self.assertEqual(only_freq["first_mode_by_axis"], {})

        with_part = results.modal_result(self._body(sub_tables=[freq, part]))
        self.assertAlmostEqual(
            with_part["modes"][0]["participation_mass_ratio"]["UX"], 1.65)
        self.assertIsNone(with_part["modes"][0].get("direction_factor"))

        with_direc = results.modal_result(self._body(sub_tables=[freq, direc]))
        self.assertAlmostEqual(
            with_direc["modes"][0]["direction_factor"]["UX"], 1.79)
        self.assertIsNone(with_direc["modes"][0].get("participation_mass_ratio"))

    def test_five_modes_parse_with_every_field(self):
        body = self._body()
        modal = results.modal_result(body)
        for rec in modal["modes"]:
            self.assertIsNotNone(rec["frequency_hz"])
            self.assertIsNotNone(rec["period_s"])
            self.assertIsNotNone(rec["participation_mass_ratio"])
            self.assertIsNotNone(rec["direction_factor"])
            self.assertIsNotNone(rec["participation_mass_ratio"]["RZ"])
        self.assertEqual(modal["modes"][0]["frequency_hz"], 2.6350)

    def test_modal_parse_is_identical_from_raw_string_or_dict(self):
        """The dispatch path passes a raw body; the live driver passes a dict.
        Both must produce the same result."""
        from_raw = results.modal_result(self._body())
        from_dict = results.modal_result(json.loads(self._body()))
        self.assertEqual(from_raw, from_dict)


class NormalizeTests(unittest.TestCase):
    def test_2xx_error_body_flagged(self):
        self.assertTrue(normalize.is_error_body(200, '{"error":{"message":"Wrong Field"}}'))
        self.assertTrue(normalize.is_error_body(201, "Unknown Error"))
        self.assertFalse(normalize.is_error_body(200, '{"ELEM":{"1":{}}}'))
        self.assertFalse(normalize.is_error_body(200, ""))

    def test_2xx_error_body_covers_observed_messages(self):
        """Every marker here was seen arriving with HTTP 200 on the live build."""
        for body in (
            "{\"message\":\"MIDAS GEN NX path is wrong (the file can't open)\"}",
            '{"message":"Analysis is not allowed."}',
            '{"message":"no analysis result"}',
            "error creating utbl",
        ):
            with self.subTest(body=body):
                self.assertTrue(normalize.is_error_body(200, body))

    def test_soft_empty_is_not_an_error(self):
        """`no valid story information` means "nothing yet", not a failure."""
        body = '{"error":{"message":"There is no valid story information."}}'
        self.assertTrue(normalize.is_soft_empty(body))
        self.assertFalse(normalize.is_error_body(400, body))

    def test_classifier_is_structural_not_a_whitelist(self):
        """A rejection wording nobody has seen before must still be caught."""
        self.assertTrue(normalize.is_error_body(
            200, '{"message":"Some brand new failure wording"}'))
        self.assertTrue(normalize.is_error_body(201, "[错误] 材料 995001 不存在。"))
        self.assertTrue(normalize.is_error_body(200, "Unknown Error"))

    def test_classifier_still_accepts_real_successes(self):
        for body in ('{"message":""}',
                     '{"message":"MIDAS GEN NX command complete"}',
                     '{"NODE":{"1":{"X":0,"Y":0,"Z":0}}}',
                     '{"PROJECTSTATUS":{"DATA":[]}}',
                     ""):
            with self.subTest(body=body):
                self.assertFalse(normalize.is_error_body(200, body))
        # a 4xx is handled by classify_error, not by this predicate
        self.assertFalse(normalize.is_error_body(400, '{"error":{"message":"Wrong Field"}}'))

    def test_error_classification(self):
        from midas_mcp.errors import AuthError, NotFoundError
        with self.assertRaises(AuthError):
            normalize.classify_error(400, '{"error":{"message":"MAPI Key is invalid."}}', "DB:NODE")
        with self.assertRaises(NotFoundError):
            normalize.classify_error(404, "", "DB:NOPE")
        with self.assertRaises(NotFoundError):
            normalize.classify_error(400, '{"error":{"message":"Not Found Key"}}', "DB:NODE")

    def test_already_exist_is_its_own_category(self):
        """A re-POST of an existing key writes nothing; a caller that reads it
        as a generic rejection misses that the OLD value is still live."""
        from midas_mcp.errors import AlreadyExistsError
        with self.assertRaises(AlreadyExistsError) as ctx:
            normalize.classify_error(
                400, '{"error":{"message":"Key Already Exist"}}', "DB:EIGV")
        env = ctx.exception.envelope()
        self.assertEqual(env["category"], "ALREADY_EXISTS")
        self.assertIn("NOT overwritten", env["note"])
        self.assertIn("update", env["note"])

    def test_success_envelope(self):
        env = normalize.normalize_success("DB:NODE", "GET", 200, '{"NODE":{}}', {"NODE": {}})
        self.assertTrue(env["ok"])
        self.assertEqual(env["endpoint"], "DB:NODE")


class SecretTests(unittest.TestCase):
    def test_secret_redacted(self):
        s = config.Secret("abcdef")
        self.assertNotIn("abcdef", repr(s))
        self.assertNotIn("abcdef", str(s))
        self.assertEqual(s.reveal(), "abcdef")

    def test_redact_function(self):
        cfg = config.load_config([])
        out = config.redact("key is X123", cfg)
        self.assertNotIn(cfg.mapi_key.reveal(), out)


if __name__ == "__main__":
    unittest.main(verbosity=2)