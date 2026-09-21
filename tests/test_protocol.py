"""MCP protocol conformance tests (offline).

Two layers:
1. In-process tests of the JSON-RPC method surface (initialize, tools/list,
   tools/call shape, two-tier error model).
2. A subprocess test that drives the real CLI over stdin/stdout with NDJSON and
   asserts that stdout carries pure protocol lines and all logging stays on
   stderr -- the single most important invariant for a stdio MCP server.
"""
from __future__ import annotations

import json
import io
import unittest.mock
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("MIDAS_MAPI_KEY", "test-key")

from midas_mcp import knowledge, mcp_server  # noqa: E402


def _fresh_server():
    from midas_mcp.config import load_config
    from midas_mcp.registry import Registry
    cfg = load_config([])
    reg = Registry.load(ROOT / "registry")
    return mcp_server.McpServer(cfg, reg)


class ProtocolUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = _fresh_server()

    def _call(self, msg):
        return self.srv.handle(msg)

    def test_initialize_negotiates_version(self):
        r = self._call({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2026-07-28",
                                   "capabilities": {"tools": {}},
                                   "clientInfo": {"name": "t", "version": "1"}}})
        self.assertEqual(r["result"]["protocolVersion"], "2026-07-28")
        self.assertEqual(r["result"]["serverInfo"]["name"], "midas-mcp")

    def test_initialize_unknown_version_returns_newest(self):
        r = self._call({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2099-99-99"}})
        self.assertNotEqual(r["result"]["protocolVersion"], "2099-99-99")
        self.assertIn("instructions", r["result"])

    def test_tools_list_matches_the_dispatch_table(self):
        """``tools/list`` must advertise exactly what ``tools/call`` serves.

        Asserting the literal names would go stale the moment a tool is added,
        and a tool that is callable but unlisted is invisible to the client.
        """
        r = self._call({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = [t["name"] for t in r["result"]["tools"]]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(sorted(names), sorted(mcp_server.TOOL_DISPATCH))
        self.assertIn("midas_frame_run", names)

    def test_ping(self):
        self.assertEqual(self._call({"jsonrpc": "2.0", "id": 3,
                                     "method": "ping"})["result"], {})

    def test_unknown_method_is_rpc_error(self):
        with self.assertRaises(mcp_server.RpcError):
            self._call({"jsonrpc": "2.0", "id": 4, "method": "nope"})

    def test_unknown_tool_is_invalid_params(self):
        with self.assertRaises(mcp_server.RpcError):
            self._call({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                        "params": {"name": "nope", "arguments": {}}})

    def test_notification_gets_no_reply(self):
        r = self._call({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertIsNone(r)

    def test_unknown_endpoint_is_tool_error_not_rpc(self):
        r = self._call({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                        "params": {"name": "midas_db_query",
                                   "arguments": {"endpoint": "DB:NOPE"}}})
        result = r["result"]
        self.assertTrue(result["isError"])
        self.assertEqual(result["structuredContent"]["category"], "INVALID_INPUT")
        # the protocol envelope must still be a result, not an error object
        self.assertNotIn("error", r)

    def test_resources_list_and_read(self):
        r = self._call({"jsonrpc": "2.0", "id": 7, "method": "resources/list"})
        uris = {x["uri"] for x in r["result"]["resources"]}
        self.assertIn("midas://knowledge/pitfalls", uris)
        # every recipe in the knowledge base must be reachable as a resource,
        # otherwise the documented procedure is invisible to the model
        for recipe in knowledge.RECIPES:
            self.assertIn(f"midas://recipes/{recipe}", uris)
        rr = self._call({"jsonrpc": "2.0", "id": 8, "method": "resources/read",
                         "params": {"uri": "midas://knowledge/pitfalls"}})
        self.assertIn("MIDAS knowledge", rr["result"]["contents"][0]["text"])
        with self.assertRaises(mcp_server.RpcError):
            self._call({"jsonrpc": "2.0", "id": 9, "method": "resources/read",
                        "params": {"uri": "midas://nope"}})

    def test_every_registered_resource_builds(self):
        """A resource whose builder raises (a mistyped recipe name, say) fails here.

        The recipe resources are built by name, so a rename in knowledge.RECIPES
        that is not mirrored in mcp_server._RESOURCE_NAMES would otherwise only
        surface as a runtime error on the model's resources/read.
        """
        for uri, (_mt, builder) in mcp_server._RESOURCE_NAMES.items():
            if builder is None:
                continue  # built at request time from the registry
            with self.subTest(uri=uri):
                text = builder()
                self.assertIsInstance(text, str)
                self.assertTrue(text.strip(), uri)
        for uri in mcp_server._RESOURCE_NAMES:
            if uri.startswith("midas://recipes/"):
                with self.subTest(recipe=uri):
                    self.assertIn(uri.rsplit("/", 1)[-1], knowledge.RECIPES)

    def test_knowledge_entries_are_complete(self):
        """Every pitfall must carry all three fields, and the traps must be unique."""
        traps = [p["trap"] for p in knowledge.PITFALLS]
        self.assertEqual(len(traps), len(set(traps)), "duplicate pitfall trap text")
        for p in knowledge.PITFALLS:
            for field in ("area", "trap", "symptom", "fix"):
                self.assertTrue(p.get(field), f"{field} missing in {p}")


class SubprocessStdioTests(unittest.TestCase):
    #: A minimal NDJSON dialog that stays offline (no tool call hits MIDAS).
    SCRIPT = """
import os, sys
os.environ.setdefault("MIDAS_MAPI_KEY","test-key")
from pathlib import Path
sys.path.insert(0, r"{src}")
import logging
from midas_mcp.config import load_config
from midas_mcp.registry import Registry
from midas_mcp.mcp_server import McpServer
from midas_mcp.stdio_transport import StdioTransport
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)  # force logs to stderr
cfg = load_config([])
reg = Registry.load(Path(r"{reg}"))
srv = McpServer(cfg, reg)
StdioTransport(srv.handle).run()
"""

    def _drive(self, messages):
        src = str(ROOT / "src")
        reg = str(ROOT / "registry")
        script = self.SCRIPT.format(src=src, reg=reg)
        input_lines = "".join(
            json.dumps(m, ensure_ascii=False) + "\n" for m in messages).encode()
        proc = subprocess.run([sys.executable, "-c", script], input=input_lines,
                              capture_output=True, timeout=60)
        return proc

    def test_stdout_is_pure_ndjson_logs_on_stderr(self):
        proc = self._drive([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2026-07-28", "capabilities": {"tools": {}},
                        "clientInfo": {"name": "t", "version": "1"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "ping"},
        ])
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        out_lines = proc.stdout.decode("utf-8").splitlines()
        # every stdout line must be valid JSON with a "jsonrpc" member
        for ln in out_lines:
            obj = json.loads(ln)
            self.assertEqual(obj["jsonrpc"], "2.0")
        self.assertGreaterEqual(len(out_lines), 3)
        self.assertIn("tools", json.loads(out_lines[1])["result"])
        # logging (DEBUG level was set) must NOT have leaked to stdout
        joined = proc.stdout.decode("utf-8")
        self.assertNotIn("DEBUG", joined)
        self.assertNotIn("roaming", joined)
        # stderr should carry the log lines
        self.assertIn("stdio transport", proc.stderr.decode("utf-8"))

    def test_notifications_do_not_emit_stdout(self):
        proc = self._drive([
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 1, "method": "ping"},
        ])
        lines = proc.stdout.decode("utf-8").splitlines()
        self.assertEqual(len(lines), 1)  # only the ping reply, no notification reply


class ProgressNotificationTests(unittest.TestCase):
    """The progress channel: token in, notifications out, nothing else changed.

    The tool called here is a probe rather than a real one.  What is under test
    is the wiring between a client's ``progressToken``, the notifier the handler
    sees on its own thread, and the line the transport writes.
    """

    def setUp(self):
        from midas_mcp import dispatch
        self.dispatch = dispatch
        self.srv = _fresh_server()
        self.sent = []
        self.srv.notify = lambda method, params: self.sent.append((method, params))
        self.seen = {}
        self._original = mcp_server.TOOL_DISPATCH["midas_frame_run"]

        def probe(args, deps):
            self.seen["token"] = dispatch.CALL.token
            self.seen["has_notify"] = dispatch.CALL.notify is not None
            if dispatch.CALL.notify is not None:
                dispatch.CALL.notify(
                    "notifications/progress",
                    {"progressToken": dispatch.CALL.token, "progress": 1,
                     "message": "step"})
            return {"ok": True, "endpoint": "FRAME:RUN", "method": "RUN"}

        mcp_server.TOOL_DISPATCH["midas_frame_run"] = probe

    def tearDown(self):
        mcp_server.TOOL_DISPATCH["midas_frame_run"] = self._original
        self.dispatch.CALL.token = None
        self.dispatch.CALL.notify = None

    def _call(self, params):
        return self.srv.handle({"jsonrpc": "2.0", "id": 1,
                                "method": "tools/call", "params": params})

    def test_the_progress_token_reaches_the_tool_and_comes_back(self):
        answer = self._call({"name": "midas_frame_run", "arguments": {},
                             "_meta": {"progressToken": "tok-7"}})
        self.assertEqual(self.seen["token"], "tok-7")
        self.assertIs(self.seen["has_notify"], True)
        self.assertEqual(self.sent[0][0], "notifications/progress")
        self.assertEqual(self.sent[0][1]["progressToken"], "tok-7")
        self.assertIs(answer["result"]["structuredContent"]["ok"], True)

    def test_without_a_token_the_tool_gets_no_notifier(self):
        self._call({"name": "midas_frame_run", "arguments": {}})
        self.assertIsNone(self.seen["token"])
        self.assertIs(self.seen["has_notify"], False)
        self.assertEqual(self.sent, [])

    def test_the_channel_is_cleared_once_the_call_is_over(self):
        self._call({"name": "midas_frame_run", "arguments": {},
                    "_meta": {"progressToken": "tok-8"}})
        self.assertIsNone(self.dispatch.CALL.token)
        self.assertIsNone(self.dispatch.CALL.notify)

    def test_a_notification_is_one_ndjson_line_without_an_id(self):
        from midas_mcp.stdio_transport import StdioTransport

        class FakeStdout:
            def __init__(self):
                self.buffer = io.BytesIO()

        fake = FakeStdout()
        transport = StdioTransport(lambda msg: None)
        with unittest.mock.patch.object(sys, "stdout", fake):
            transport.notify("notifications/progress",
                             {"progressToken": "t", "progress": 1,
                              "message": "s"})
        lines = fake.buffer.getvalue().decode("utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        msg = json.loads(lines[0])
        self.assertEqual(msg["jsonrpc"], "2.0")
        self.assertEqual(msg["method"], "notifications/progress")
        # a notification carries no id: a client must not answer it
        self.assertNotIn("id", msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)