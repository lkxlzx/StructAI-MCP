"""Tiny JSON-RPC 2.0 helpers for the MCP transport."""
from __future__ import annotations

import json

from .errors import RpcError


def parse_line(line: bytes) -> dict | list | None:
    """Parse a single NDJSON line into a JSON-RPC message.

    Raises RpcError(PARSE_ERROR) for non-JSON; returns None for ``null``.
    """
    try:
        data = json.loads(line.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise RpcError("PARSE_ERROR", "invalid JSON: parse error") from exc
    if data is None:
        return None
    if not isinstance(data, dict):
        raise RpcError("INVALID_REQUEST", "a request must be a JSON object")
    return data


def ok(id, result) -> dict:
    return {"jsonrpc": "2.0", "id": id, "result": result}


def notify(method: str, params: dict | None = None) -> dict:
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    return msg


def dumps_line(msg: dict) -> bytes:
    """Serialize one message to an NDJSON line (no embedded newline)."""
    return (json.dumps(msg, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def has_id(msg: dict) -> bool:
    return "id" in msg


def is_notification(msg: dict) -> bool:
    return has_id(msg) is False