"""Structured error types for the connector.

Two distinct failure domains exist (see mcp/01_PROTOCOL.md & 9):

* Protocol errors - JSON-RPC level problems (bad framing, unknown method,
  invalid params in the tool call itself).  These become JSON-RPC ``error``
  objects with the codes in ``RpcError``.

* Tool/upstream errors - a MIDAS request failed (HTTP error, refused by a
  guard, empty result).  These are NOT protocol errors: they are returned to
  the model inside ``result.isError=true`` with the structured envelope from
  mcp/04_HTTP.md & 12.  ``MidasError`` carries such an envelope.

The guard that separates the two lives in the tool handlers, never in the MIDAS
client: an upstream 400/404 must never be wrapped as a JSON-RPC error.
"""

from __future__ import annotations

from typing import Any


class ToolError(Exception):
    """A recoverable, model-facing failure inside a tool call.

    ``to_result()`` produces an ``isError=true`` MCP tool result rather than a
    JSON-RPC ``error`` -- this is the right shape for every MIDAS-side problem.
    """

    category: str = "UPSTREAM"

    def __init__(self, message: str, *, endpoint: str | None = None,
                 http_status: int | None = None, data: Any | None = None):
        super().__init__(message)
        self.endpoint = endpoint
        self.http_status = http_status
        self.data = data

    def envelope(self) -> dict:
        env: dict = {"ok": False, "category": self.category,
                     "message": str(self)}
        if self.endpoint is not None:
            env["endpoint"] = self.endpoint
        if self.http_status is not None:
            env["http_status"] = self.http_status
        if self.data is not None:
            env["data"] = self.data
        return env


class AuthError(ToolError):
    category = "AUTH"


class NotFoundError(ToolError):
    category = "NOT_FOUND"


class GuardError(ToolError):
    category = "REFUSED"


class MiddlewareError(ToolError):
    category = "MIDAS_REJECTED"


class AlreadyExistsError(ToolError):
    """A create targeted a key that is already present.

    MIDAS answers a re-POST of an existing key with HTTP 400
    ``{"error":{"message":"Key Already Exist"}}`` rather than overwriting it,
    so the write did **not** happen.  Classified separately from a generic
    rejection because the recovery is specific: re-issue the write as an
    update (``PUT``).  Silently ignoring this is how a stale setting survives
    a "successful" write.
    """

    category = "ALREADY_EXISTS"

    def envelope(self) -> dict:
        env = super().envelope()
        env["note"] = ("the record already exists and was NOT overwritten; "
                       "re-issue the write with mode='update' (PUT) to change it.")
        return env


class InputError(ToolError):
    category = "INVALID_INPUT"


class RpcError(Exception):
    """A JSON-RPC protocol error; ``code``/``message`` map onto the spec."""

    CODES = {"PARSE_ERROR": -32700, "INVALID_REQUEST": -32600,
             "METHOD_NOT_FOUND": -32601, "INVALID_PARAMS": -32602,
             "INTERNAL_ERROR": -32603, "RESOURCE_NOT_FOUND": -32002}

    def __init__(self, code_name: str, message: str, data: Any = None):
        super().__init__(message)
        self.code = self.CODES.get(code_name, -32603)
        self.message = message
        self.data = data

    def to_json(self, rpc_id) -> dict:
        err: dict = {"code": self.code, "message": self.message}
        if self.data is not None:
            err["data"] = self.data
        return {"jsonrpc": "2.0", "id": rpc_id, "error": err}


class FrameRunError(ToolError):
    """The one-shot portal-frame driver could not produce a verdict.

    Distinct from a generic upstream failure because the recovery is specific:
    read the driver's own message (credentials, an unusable spec, or a
    non-empty MIDAS document the preflight refused) rather than retrying the
    call.
    """

    category = "FRAME_RUN_FAILED"