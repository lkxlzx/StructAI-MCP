"""stdio transport for MCP.

Framing is newline-delimited JSON (NDJSON) on stdout — the MCP wire format, not
LSP's Content-Length framing.  stdout carries protocol only; all logging goes to
stderr.  Writes are UTF-8 on ``sys.stdout.buffer`` so Chinese MIDAS messages are
not mangled by the Windows console codepage.
"""
from __future__ import annotations

import logging
import sys
import threading
from typing import Callable

from .errors import RpcError
from .jsonrpc import dumps_line, parse_line

log = logging.getLogger("midas_mcp.stdio")

RequestHandler = Callable[[dict], dict | None]  # returns a response or None (notification)


class StdioTransport:
    def __init__(self, handle: RequestHandler, *, max_workers: int = 8):
        self.handle = handle
        self._write_lock = threading.Lock()

    def _write(self, payload: bytes) -> None:
        with self._write_lock:
            sys.stdout.buffer.write(payload)
            sys.stdout.buffer.flush()

    def _send(self, msg: dict) -> None:
        self._write(dumps_line(msg))

    def run(self) -> int:
        log.info("stdio transport start")
        for line in sys.stdin.buffer:
            if not line.strip():
                continue
            try:
                message = parse_line(line)
            except RpcError as exc:
                self._send(exc.to_json(None))
                continue
            if message is None:
                continue
            response = self.handle(message)
            # a request with an id expects a reply
            if "id" in message and response is not None:
                self._send(response)
        log.info("stdio transport end")
        return 0