"""Response normalization and success classification.

MIDAS returns error bodies (``Wrong Field``, ``Unknown Error``) with an HTTP
2xx status, so a tool result cannot be judged by the status code alone.  This
module decides success from the *body* and maps failures onto the structured
envelope from mcp/04_HTTP.md & 12.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .errors import AlreadyExistsError, AuthError, MiddlewareError, NotFoundError

#: Fallback markers for bodies that are not JSON (or do not follow the
#: ``message``/``error`` shape).  Every entry was observed returning HTTP 2xx
#: while carrying a failure message.
_UPSTREAM_ERROR_FIELDS = (
    "Wrong Field",
    "error creating utbl",
    "UnKnown",
    "Unknown Error",
    "path is wrong",
    "can't open",
    "Analysis is not allowed",
    "no analysis result",
)

#: A non-empty ``message`` is a rejection unless it says the command finished.
#: Observed successes with a message are only these two shapes.
_SUCCESS_MESSAGE_PATTERNS = ("command complete", "complete")

#: Bare error strings that arrive without a JSON envelope.
_BARE_ERROR_RE = re.compile(
    r"^\s*(\[错误\]|\[Error\]|Wrong Field|Unknown Error|UnKnown)", re.I)


#: Raw-body markers that mean "empty but valid" rather than a real failure.
SOFT_EMPTY_MARKERS = (
    "There is no valid story information",
)


def is_error_body(status: int, raw: str) -> bool:
    """Decide whether a 2xx response is actually a rejection.

    MIDAS signals some failures with a non-2xx status (honest) and others with
    2xx plus a message (silent).  The rule here is structural rather than a
    message whitelist, so unknown wording is still caught:

    * a top-level ``error`` object  -> rejection
    * a non-empty ``message`` that is not a completion notice -> rejection
    * otherwise fall back to the observed marker list
    """
    if not (200 <= status < 300):
        return False
    if not raw.strip():
        return False  # empty 2xx body is treated as success
    if is_soft_empty(raw):
        return False  # a soft-empty answer is not a hard failure

    try:
        parsed = json.loads(raw)
    except ValueError:
        parsed = None

    if isinstance(parsed, dict):
        if "error" in parsed:
            return True
        message = parsed.get("message")
        if isinstance(message, str) and message.strip():
            lowered = message.lower()
            if any(p in lowered for p in _SUCCESS_MESSAGE_PATTERNS):
                return False
            return True

    if _BARE_ERROR_RE.match(raw):
        return True
    for marker in _UPSTREAM_ERROR_FIELDS:
        if marker in raw:
            return True
    return False


def is_soft_empty(raw: str) -> bool:
    """MIDAS uses an error-shaped body to say "nothing to report yet" (e.g.
    storey properties before any storey exists).  This is not a hard failure;
    the caller should surface it as an empty result with a hint, not an error."""
    return any(m in raw for m in SOFT_EMPTY_MARKERS)


def classify_error(status: int, raw: str, endpoint: str) -> Any:
    """Raise the right ToolError for a non-success MIDAS response."""
    if status == 0:
        raise MiddlewareError(
            f"{endpoint}: MIDAS unreachable (transport error). Check that the "
            "Gen/Civil GUI is running and the base URL is correct.",
            endpoint=endpoint, http_status=None)
    if status == 400:
        if "MAPI Key is invalid" in raw or "MAPI-Key" in raw:
            raise AuthError("MIDAS API rejected MAPI-Key.", endpoint=endpoint,
                            http_status=400)
        if "Not Found Key" in raw:
            raise NotFoundError(f"{endpoint}: the requested id does not exist.",
                                endpoint=endpoint, http_status=400)
        if "Already Exist" in raw:
            raise AlreadyExistsError(
                f"{endpoint}: the key already exists; the create was refused "
                f"and nothing was written.", endpoint=endpoint, http_status=400)
        raise MiddlewareError(f"{endpoint}: MIDAS rejected the request. {_head(raw)}",
                              endpoint=endpoint, http_status=400)
    if status == 401:
        raise AuthError("MIDAS API rejected MAPI-Key.", endpoint=endpoint,
                        http_status=401)
    if status == 404:
        raise NotFoundError(
            f"{endpoint} is not served by this MIDAS instance (HTTP 404).",
            endpoint=endpoint, http_status=404)
    if status == 500:
        raise MiddlewareError(f"{endpoint}: MIDAS internal error. {_head(raw)}",
                              endpoint=endpoint, http_status=500)
    raise MiddlewareError(f"{endpoint}: HTTP {status} {_head(raw)}",
                          endpoint=endpoint, http_status=status)


def _head(raw: str, n: int = 120) -> str:
    s = raw.strip().replace("\n", " ")
    return s[:n] + ("..." if len(s) > n else "")


def normalize_success(endpoint: str, method: str, status: int, raw: str,
                      body: dict | None, data: Any = None) -> dict:
    """Build the canonical success envelope from mcp/01_PROTOCOL.md & 8."""
    return {
        "ok": True,
        "endpoint": endpoint,
        "method": method,
        "status": status,
        "data": data if data is not None else (body or {}),
    }