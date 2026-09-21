"""Live tests against a running MIDAS Gen/Civil instance.

These touch the real GUI model and are NOT part of the offline suite.  Supply the
credentials in the environment or in the JSON config file, then opt in::

    set MIDAS_MCP_LIVE=1                  # read the key from config.json
    python -m unittest tests.test_live_gen -v

    :: ...or without a config file
    set MIDAS_MAPI_KEY=<your key>
    set MIDAS_BASE_URL=http://localhost:3030/gen
    python -m unittest tests.test_live_gen -v

The crash-guard test is the most important safety invariant: assigning a
boundary record to a nonexistent node id must be *refused locally* so the MIDAS
process never crashes.  Throwaway nodes are created and cleaned up.  No analysis
is run here (running one lets the model's stored results expire).
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from midas_mcp.config import load_config  # noqa: E402
from midas_mcp.credentials import unittest_key  # noqa: E402
from midas_mcp.errors import GuardError  # noqa: E402
from midas_mcp.mcp_server import McpServer  # noqa: E402
from midas_mcp.registry import Registry  # noqa: E402

#: An exported ``MIDAS_MAPI_KEY`` always wins; otherwise the key is only pulled
#: from the config file when ``MIDAS_MCP_LIVE=1``, so ``unittest discover`` keeps
#: skipping the live tests (they mutate the live model) just because a
#: config.json happens to exist.
LIVE_KEY = unittest_key()


def _server() -> McpServer:
    cfg = load_config([])
    reg = Registry.load(ROOT / "registry")
    return McpServer(cfg, reg)


@unittest.skipUnless(LIVE_KEY, "live tests need MIDAS_MAPI_KEY or MIDAS_MCP_LIVE=1 -- skipping")
class LiveReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = _server()
        cls.before_nodes = cls._node_count()

    @staticmethod
    def _node_count() -> int:
        r = _server().handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                              "params": {"name": "midas_db_query",
                                         "arguments": {"endpoint": "DB:NODE"}}})
        data = r["result"]["structuredContent"]["data"]
        return len(data.get("NODE", {}))

    def _call(self, name, args):
        return self.srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                "params": {"name": name, "arguments": args}})["result"]

    def test_read_node(self):
        """Reading the node collection works on any document, including an
        empty one (the response then simply carries no NODE key)."""
        r = self._call("midas_db_query", {"endpoint": "DB:NODE"})
        self.assertFalse(r["isError"])
        data = r["structuredContent"]["data"]
        self.assertIsInstance(data, dict)
        if "NODE" in data:
            self.assertIsInstance(data["NODE"], dict)

    def test_read_projectstatus(self):
        r = self._call("midas_db_query", {"endpoint": "OPE:PROJECTSTATUS"})
        self.assertFalse(r["isError"])

    def test_schema_introspection(self):
        r = self._call("midas_db_query", {"endpoint": "DB:NODE", "info": True})
        self.assertFalse(r["isError"])
        self.assertIn("Argument",
                      r["structuredContent"]["data"])

    def test_endpoint_search(self):
        r = self._call("midas_db_query", {"endpoint": "DB:NODE", "search": "beam"})
        self.assertFalse(r["isError"])
        self.assertGreater(r["structuredContent"]["data"]["count"], 0)

    def test_crash_guard_refuses_missing_node(self):
        """The single most important guarantee: a boundary write to a missing
        node id is refused here, so MIDAS never crashes."""
        r = self._call("midas_db_assign", {
            "endpoint": "DB:CONS", "mode": "create",
            "data": {"999999": {"ITEMS": [{"ID": 1, "CONSTRAINT": "1111110"}]}}})
        self.assertTrue(r["isError"])
        self.assertEqual(r["structuredContent"]["category"], "REFUSED")
        # and MIDAS must still be alive
        alive = self._call("midas_db_query", {"endpoint": "DB:NODE"})
        self.assertFalse(alive["isError"])

    def test_throwaway_node_roundtrip(self):
        """Create a throwaway node, read it back, then delete it."""
        r = self._call("midas_db_assign", {
            "endpoint": "DB:NODE", "mode": "create",
            "data": {"700001": {"X": 9, "Y": 9, "Z": 9}}})
        self.assertFalse(r["isError"], r["content"][0]["text"])
        rb = self._call("midas_db_query", {"endpoint": "DB:NODE", "item_id": "700001"})
        self.assertEqual(rb["structuredContent"]["data"]["NODE"]["700001"]["X"], 9)
        d = self._call("midas_db_delete", {"endpoint": "DB:NODE",
                                           "target_ids": ["700001"]})
        self.assertFalse(d["isError"], d["content"][0]["text"])

    def test_bad_endpoint_is_invalid_input(self):
        r = self._call("midas_db_query", {"endpoint": "DB:NOPE"})
        self.assertTrue(r["isError"])
        self.assertEqual(r["structuredContent"]["category"], "INVALID_INPUT")

    @classmethod
    def tearDownClass(cls):
        after = cls._node_count()
        if after != cls.before_nodes:
            print(f"\nWARNING: node count changed during live tests: "
                  f"{cls.before_nodes} -> {after}")


@unittest.skipUnless(LIVE_KEY, "live tests need MIDAS_MAPI_KEY or MIDAS_MCP_LIVE=1 -- skipping")
class LiveModalResultTests(unittest.TestCase):
    """The whole chain, live: MCP tool -> MIDAS POST/TABLE -> SUB_TABLES ->
    parser -> ModalResult.  Reads only; runs no analysis.

    Regression cover for the bug where the modal summary was reported as
    unavailable because the top-level DATA of an EIGENVALUEMODE reply holds
    per-node mode shapes and no frequency or period at all.
    """

    @classmethod
    def setUpClass(cls):
        cls.srv = _server()
        cls.ep = "POST:TABLE:EIGENVALUEMODE"
        r = cls.srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                            "params": {"name": "midas_db_assign", "arguments": {
                                "endpoint": cls.ep, "mode": "create",
                                "data": {"TABLE_TYPE": "EIGENVALUEMODE",
                                         "TABLE_NAME": "EIGENVALUEMODE",
                                         "UNIT": {"FORCE": "KN", "DIST": "M"},
                                         "STYLES": {"FORMAT": "Scientific",
                                                    "PLACE": 9},
                                         "MODES": [f"Mode{i}"
                                                   for i in range(1, 21)]}}}})["result"]
        cls.result = r["structuredContent"]

    def _call(self, name, args):
        return self.srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                "params": {"name": name, "arguments": args}})["result"]

    def test_tool_returns_a_parsed_modal_result(self):
        self.assertTrue(self.result.get("ok"), self.result.get("message"))
        modal = self.result["result_summary"]["modal_result"]
        self.assertEqual(modal["source"], "SUB_TABLES")
        self.assertGreaterEqual(modal["mode_count"], 20)

    def test_top_level_table_alone_has_no_frequency_or_period(self):
        """Documents *why* the parser is needed: the primary table cannot answer
        a frequency question, so its emptiness proves nothing."""
        table = self.result["data"]["EIGENVALUEMODE"]
        self.assertNotIn("Frequency", table["HEAD"])
        self.assertNotIn("Period", table["HEAD"])
        self.assertTrue(table.get("SUB_TABLES"))

    def test_first_mode_frequency_and_period(self):
        modes = self.result["result_summary"]["modal_result"]["modes"]
        self.assertEqual(modes[0]["mode"], 1)
        self.assertIsNotNone(modes[0]["frequency_hz"])
        self.assertIsNotNone(modes[0]["period_s"])
        self.assertGreater(modes[0]["frequency_hz"], 0)
        # f = 1/T must hold on MIDAS's own numbers.
        self.assertAlmostEqual(modes[0]["frequency_hz"],
                               1.0 / modes[0]["period_s"], places=3)

    def test_all_modes_in_midas_order_with_rising_frequency(self):
        modes = self.result["result_summary"]["modal_result"]["modes"]
        self.assertEqual([m["mode"] for m in modes],
                         list(range(1, len(modes) + 1)))
        frequencies = [m["frequency_hz"] for m in modes]
        self.assertEqual(frequencies, sorted(frequencies))

    def test_participation_and_direction_factors_are_present(self):
        first = self.result["result_summary"]["modal_result"]["modes"][0]
        self.assertIn("UZ", first["participation_mass_ratio"])
        self.assertIn("UZ", first["direction_factor"])
        # Rotational columns are ROTN-X/Y/Z in MIDAS, canonical RX/RY/RZ here.
        self.assertIn("RX", first["participation_mass_ratio"])
        cumulative = self.result["result_summary"]["modal_result"][
            "cumulative_ratio_percent"]
        self.assertGreater(cumulative["UX"], 50.0)

    def test_raw_sub_tables_are_kept(self):
        modal = self.result["result_summary"]["modal_result"]
        self.assertTrue(any("EIGENVALUE ANALYSIS" in k for k in modal["raw"]))
        self.assertIn("EIGENVALUEMODE", modal["tables"])

    def test_a_modal_question_routes_to_this_endpoint(self):
        r = self._call("midas_db_query", {"endpoint": "DB:NODE",
                                          "search": "自振周期"})
        self.assertEqual(r["structuredContent"].get("route"), self.ep)


if __name__ == "__main__":
    unittest.main(verbosity=2)