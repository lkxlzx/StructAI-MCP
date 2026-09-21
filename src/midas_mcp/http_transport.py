"""Optional Streamable HTTP transport (stdlib http.server).

Serves the MCP endpoints at ``/mcp`` on 127.0.0.1.  Stateless: every POST is
handled independently.  Supports JSON responses and a minimal SSE path.  This
is optional; the primary transport is stdio.
"""
from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .mcp_server import McpServer
from .jsonrpc import dumps_line

log = logging.getLogger("midas_mcp.http_transport")


class McpHttpHandler(BaseHTTPRequestHandler):
    server_version = "midas-mcp/1.0"

    def _mcp_server(self) -> McpServer:
        return self.server.mcp_server  # type: ignore[attr-defined]

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def do_POST(self):
        if urlparse(self.path).path != "/mcp":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error":{"message":"not found"}}')
            return
        body = self._read_body()
        try:
            message = json.loads(body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            self._send_json(400, {"jsonrpc": "2.0", "id": None,
                                  "error": {"code": -32700,
                                            "message": "parse error"}})
            return
        accept = self.headers.get("Accept", "")
        if "text/event-stream" in accept:
            self._send_sse(message)
        else:
            self._send_json(200, self._mcp_server().handle(message) or {})

    def _send_json(self, status: int, obj: dict):
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_sse(self, message: dict):
        response = self._mcp_server().handle(message)
        if response is None:
            self.send_response(202)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            return
        stream = dumps_line(response)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(b"event: message\ndata: " + stream.rstrip(b"\n") + b"\n\n")

    def do_GET(self):
        self.send_response(405)
        self.send_header("Allow", "POST")
        self.end_headers()
        self.wfile.write(b'{"error":{"message":"method not allowed"}}')

    def log_message(self, fmt, *args):
        log.info("%s - %s", self.address_string(), fmt % args)


def run_http(server: McpServer, cfg, *, host: str = "127.0.0.1",
             port: int = 8100) -> int:
    httpd = ThreadingHTTPServer((host, port), McpHttpHandler)
    httpd.mcp_server = server  # type: ignore[attr-defined]
    log.info("Streamable HTTP serving MCP at http://%s:%s/mcp", host, port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        httpd.server_close()
    return 0