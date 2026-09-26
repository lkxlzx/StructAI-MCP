"""REST + SSE application factory — v1.2 §3.2/§3.3, §5, §20, §21, §22.3, §34–§36.

Authoritative sources
---------------------
* **总纲 §4.3.1** — the REST envelope (``success`` / ``code`` / ``message`` /
  ``data`` / ``request_id`` / ``timestamp``) and its four, and only four,
  exceptions.  §4.3.2's MCP envelope is a *different* envelope and must never
  appear on these routes (「两种信封不得混用」).
* **总纲 §4.4** — the closed error-code registry.  This module defines **no**
  code; it maps the codes it already has onto HTTP statuses via
  :func:`app.core.errors.http_status_for`.
* **总纲 §4.1.3** — the closed ID-prefix set.  Request ids are ``req_``
  (``new_id("req")``), never ``request_``.
* **v1.2 §3.2 / §3.3** — the envelope and the closed list of exceptions.
* **v1.2 §5** — ``/api/v1/auth/{login,me,logout,refresh}``.
* **v1.2 §20** — the minimal task surface (list + detail); §21 the per-task SSE
  stream; §22.3 the log SSE stream; §34–§36 the three health endpoints.
* **v1.2 §51** — pagination is ``data.items`` + ``data.pagination``, max
  ``page_size`` 500, never a bare top-level ``items``.
* **总纲 §4.8.2** — the closed permission-code set.  Every authorization check
  here reuses an existing code (``task:read``); none is invented.

How to launch this service (read this before deploying)
-------------------------------------------------------
Run it as **``python -m app.main``**, or pass **``--no-proxy-headers``** to a
manual ``uvicorn app.main:app``.

uvicorn defaults ``proxy_headers=True`` and installs its
``ProxyHeadersMiddleware`` *outside* this application, where it rewrites
``scope["client"]`` from ``X-Forwarded-For`` before any middleware here runs.
That silently defeats :class:`RateLimitMiddleware`'s key: ``client_key`` refuses
to read the header unless ``trust_proxy_headers`` is on, but by then the forged
address already *is* the client address.  Measured on a live server with
``rate_limit_burst=3`` and six requests each carrying a different forged
``X-Forwarded-For``:

* ``--no-proxy-headers``              -> ``200 200 200 429 429 429``
* uvicorn default (proxy headers on)  -> ``200 200 200 200 200 200``

Same app, config and database — the launch flag was the only variable, and with
the default on each forged address minted its own token bucket.  :func:`main`
pins the flag to :data:`~app.core.config.Settings.trust_proxy_headers`; a manual
uvicorn invocation has to do it by hand.

The four envelope exceptions, enumerated (总纲 §4.3.1 / v1.2 §3.3)
-----------------------------------------------------------------
:class:`EnvelopeMiddleware` wraps every ``application/json`` response.  Exactly
four classes of response are exempt, and this module states each one explicitly
rather than relying on "it happens not to be JSON":

1. **SSE streams** (``*/stream`` — v1.2 §21, §22.3).  ``text/event-stream`` is not
   JSON, and the stream is unbounded: buffering it would hang the connection.
   Detected on the response's own ``content-type``, so the exemption cannot be
   lost by adding a route.
2. **File downloads** (``*/download``, ``/files/{id}`` — v1.2 §30.4, §91).  Binary
   streams; same content-type test.
3. **Health probes** ``/api/v1/health/ready`` and ``/api/v1/health/live``
   (v1.2 §35, §36).  Container orchestrators require a bare status code; listed
   explicitly in :data:`ENVELOPE_EXEMPT_PATHS`.
4. **OpenAPI** ``/openapi.json``, ``/docs``, ``/docs/oauth2-redirect``, ``/redoc``
   (v1.2 §59).  Framework-generated; listed explicitly in
   :data:`ENVELOPE_EXEMPT_PATHS`.

``/api/v1/health`` (the aggregate check, v1.2 §34) is **not** an exception and is
served through the envelope, as §34 and 总纲 §4.3.1 both insist.

Rate limiting is a *different* axis (总纲 §4.4.2 ``RATE_LIMITED`` / §8.6), so its
exemption set is deliberately **not** ``ENVELOPE_EXEMPT_PATHS``: see
:data:`RATE_LIMIT_EXEMPT_PATHS` and :class:`RateLimitMiddleware`.  The two sets
answer two different questions — "may this response skip the envelope?" and "may
this caller be throttled?" — and conflating them would either expose the health
probes to lockout or hand an attacker an unthrottled route.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone, tzinfo
from functools import lru_cache
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    FrozenSet,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Tuple,
    cast,
)

from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session
from sse_starlette import EventSourceResponse, ServerSentEvent

from app.adapters.errors import AdapterError
from app.adapters.registry import AdapterRegistry, get_registry
from app.core.config import get_settings
from app.core.constants import SUPER_ADMIN_ROLE, TaskStatus
from app.core.errors import ErrorCode, http_status_for
from app.core.ids import new_id
from app.core.midas_config import MidasConfigError
from app.core.rate_limit import (
    RateLimitDecision,
    RateLimitLimiter,
    RateLimitPolicy,
    client_key,
)
from app.db.base import session_scope_for
from app.mcp.auth import make_authorizer
from app.mcp.dispatcher import ToolDispatcher
from app.mcp.server import (
    build_server,
    register_configured_adapters,
    register_mock_adapter,
)
from app.models.identity import User
from app.services.auth_service import AuthService, Principal, anonymous_principal
from app.services.event_bus import TASKS_TOPIC, EventBus, Subscription, task_topic
from app.services.task_service import (
    TERMINAL_STATUSES,
    TaskService,
    init_task_service,
    task_owner_scope,
    task_visible_to,
)
from app.services.task_store import SqlAlchemyTaskStore, TaskEventRecord, TaskRecord

__all__ = [
    "API_PREFIX",
    "ENVELOPE_FIELDS",
    "ENVELOPE_EXEMPT_PATHS",
    "RATE_LIMIT_EXEMPT_PATHS",
    "RATE_LIMIT_POLICY_TTL_SECONDS",
    "REQUEST_ID_HEADER",
    "TASK_READ_PERMISSION",
    "TASK_SSE_EVENT_NAMES",
    "MAX_PAGE_SIZE",
    "DEFAULT_PAGE_SIZE",
    "EnvelopeMiddleware",
    "RateLimitMiddleware",
    "LoginRequest",
    "build_envelope",
    "create_app",
    "app",
]

_LOGGER = logging.getLogger("structai.api")

#: v1.2 §37 — the management API lives under ``/api/v1``; ``/mcp`` is separate.
API_PREFIX: str = "/api/v1"

#: 总纲 §4.3.1 — the six mandatory keys, in the documented order.  ``details`` is
#: the documented *extra* on a failure and is added only there.
ENVELOPE_FIELDS: Tuple[str, ...] = (
    "success",
    "code",
    "message",
    "data",
    "request_id",
    "timestamp",
)

#: The request-tracking header, lower-cased as ASGI delivers it.
REQUEST_ID_HEADER: bytes = b"x-request-id"

#: 总纲 §4.3.1 exceptions 3 and 4 — the *path-addressed* half of the closed list.
#: Exceptions 1 and 2 (SSE, downloads) are addressed by response content-type and
#: are therefore not enumerable here; see the module docstring.
ENVELOPE_EXEMPT_PATHS: FrozenSet[str] = frozenset(
    {
        # --- 3. health probes (v1.2 §35, §36) --------------------------- #
        f"{API_PREFIX}/health/ready",
        f"{API_PREFIX}/health/live",
        # --- 4. OpenAPI (v1.2 §59) -------------------------------------- #
        "/openapi.json",
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
    }
)

#: 总纲 §4.8.2 — the only permission this module checks.  It is an existing
#: member of the closed 34-code set; the ownership filter below layers on top of
#: it exactly as :func:`app.mcp.auth.scope_allows` layers on top of ``tool:*``.
TASK_READ_PERMISSION: str = "task:read"

# --- rate limiting (总纲 §4.4.2 RATE_LIMITED / §8.6, 裁决 B-7) ------------- #
#: The **only** paths the limiter never touches.
#:
#: ``/health/ready`` and ``/health/live`` are v1.2 §35/§36: they exist so an
#: orchestrator can decide whether to route traffic to (or kill) this process.  A
#: probe that throttles itself takes the service down **twice** — once because the
#: probe fails, once because the orchestrator acts on that failure — so they are
#: unconditionally exempt and are answered without consulting the limiter at all.
#:
#: Deliberately **not** exempt, with reasons:
#:
#: * ``/api/v1/health`` (v1.2 §34) is the *aggregate* diagnostic, not a probe, and
#:   it opens a database session on every call (``_probe_database``).  Leaving it
#:   unthrottled would hand an unauthenticated caller a cheap way to exhaust the
#:   connection pool.  It stays limited.
#: * ``/openapi.json`` / ``/docs`` / ``/redoc`` (v1.2 §59) are static and cost
#:   nothing to serve, and a legitimate client fetches them once.  They are in
#:   :data:`ENVELOPE_EXEMPT_PATHS` because they are not the §4.3.1 envelope — that
#:   says nothing about whether they may be throttled.  They stay limited.
RATE_LIMIT_EXEMPT_PATHS: FrozenSet[str] = frozenset(
    {
        f"{API_PREFIX}/health/ready",
        f"{API_PREFIX}/health/live",
    }
)

#: How long a resolved :class:`RateLimitPolicy` is reused before the
#: ``security_configs`` singleton is read again.  The read is a database round
#: trip, so doing it on every request would make the limiter more expensive than
#: the work it protects; a few seconds of staleness on a *configuration* value is
#: harmless, and the limiter's own clock drives the TTL so an injected clock
#: controls it too.
RATE_LIMIT_POLICY_TTL_SECONDS: float = 5.0

#: ``X-RateLimit-*`` / ``Retry-After``, lower-cased as ASGI delivers them.
RATE_LIMIT_LIMIT_HEADER: bytes = b"x-ratelimit-limit"
RATE_LIMIT_REMAINING_HEADER: bytes = b"x-ratelimit-remaining"
RATE_LIMIT_RESET_HEADER: bytes = b"x-ratelimit-reset"
RETRY_AFTER_HEADER: bytes = b"retry-after"

#: 总纲 §4.8.3 — ``SUPER_ADMIN_ROLE`` now lives in :mod:`app.core.constants`.
#: It used to be defined here *and* in ``auth_service``, as two independent
#: literals for one rule; the ownership filter and the RBAC filter must agree on
#: which role bypasses them, so there is now exactly one definition.

#: v1.2 §51 — pagination bounds.
MAX_PAGE_SIZE: int = 500
DEFAULT_PAGE_SIZE: int = 20

#: v1.2 §21 — the documented task event names.  The table is the authority: an
#: ``event_type`` outside it is emitted **without** an ``event:`` line, i.e. as
#: the SSE default ``message`` event, rather than under an invented name.
TASK_SSE_EVENT_NAMES: Dict[str, str] = {
    "started": "task.started",
    "progress": "task.progress",
    "finished": "task.completed",
    "failed": "task.completed",
    "cancelled": "task.completed",
    "retrying": "task.retrying",
}

#: ``task_events.event_type`` -> ``tasks.status`` at the moment it was written.
#: Used when a replayed row has to be projected without the live record (a client
#: that reconnects after the task moved on must still see the *historical* status
#: of each event, not today's).
EVENT_TYPE_STATUS: Dict[str, str] = {
    "queued": TaskStatus.QUEUED.value,
    "started": TaskStatus.RUNNING.value,
    "finished": TaskStatus.SUCCESS.value,
    "failed": TaskStatus.FAILED.value,
    "cancelled": TaskStatus.CANCELLED.value,
    "retrying": TaskStatus.RETRYING.value,
}

#: Framework-generated JSON errors (unknown route, method not allowed, body that
#: fails pydantic validation) arrive as ``{"detail": ...}`` and still have to be
#: enveloped.  This maps their HTTP status onto an **existing** 总纲 §4.4 code —
#: no code is defined here — and the framework's status is preserved.
FRAMEWORK_STATUS_CODES: Dict[int, ErrorCode] = {
    400: ErrorCode.VALIDATION_ERROR,
    401: ErrorCode.AUTH_REQUIRED,
    403: ErrorCode.PERMISSION_DENIED,
    404: ErrorCode.RESOURCE_NOT_FOUND,
    405: ErrorCode.VALIDATION_ERROR,
    409: ErrorCode.RESOURCE_CONFLICT,
    413: ErrorCode.VALIDATION_ERROR,
    415: ErrorCode.VALIDATION_ERROR,
    422: ErrorCode.VALIDATION_ERROR,
    429: ErrorCode.RATE_LIMITED,
    500: ErrorCode.INTERNAL_ERROR,
    501: ErrorCode.NOT_IMPLEMENTED,
    502: ErrorCode.MIDAS_API_ERROR,
    503: ErrorCode.ADAPTER_UNAVAILABLE,
    504: ErrorCode.TASK_TIMEOUT,
}


# ---------------------------------------------------------------------------
# 总纲 §4.5.1 — storage UTC, transport ISO 8601 with an offset
# ---------------------------------------------------------------------------
def _output_zone() -> tzinfo:
    """The zone ``timestamp`` is rendered in (``settings.timezone``).

    ``zoneinfo`` needs a tz database; Windows has none of its own and the
    ``tzdata`` wheel is not a dependency of this project, so an unavailable zone
    degrades to UTC rather than raising inside a middleware.  UTC is always a
    correct answer for an ISO-8601 instant (总纲 §4.5.1).

    Memoised because this runs once per response and a missing tz database would
    otherwise repeat a failed lookup every time.
    """
    return _zone_for(get_settings().timezone)


@lru_cache(maxsize=8)
def _zone_for(name: str) -> tzinfo:
    """Resolve an IANA zone name, falling back to UTC (总纲 §4.5.1)."""
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:  # noqa: BLE001 - a missing tz database is not a failure
        _LOGGER.debug("timezone %r unavailable; rendering timestamps in UTC", name)
        return timezone.utc


def _timestamp_now() -> str:
    """The envelope's ``timestamp`` — ISO 8601, offset included (总纲 §4.5.1)."""
    return datetime.now(_output_zone()).isoformat()


# ---------------------------------------------------------------------------
# 总纲 §4.3.1 — the envelope
# ---------------------------------------------------------------------------
def build_envelope(
    *,
    success: bool,
    code: ErrorCode | str,
    message: str,
    data: Any = None,
    request_id: str,
    details: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the 总纲 §4.3.1 REST envelope — the six keys, always.

    ``data`` carries the whole business payload; there are no top-level bare
    fields (总纲 §4.3.1 「业务数据一律放在 data 中，禁止顶层裸字段」).  ``details``
    appears only on a failure, which is where the §4.3.1 example puts it.
    """
    resolved = code.value if isinstance(code, ErrorCode) else str(code)
    envelope: Dict[str, Any] = {
        "success": bool(success),
        "code": resolved,
        "message": message,
        "data": data,
        "request_id": request_id,
        "timestamp": _timestamp_now(),
    }
    if not success and details:
        envelope["details"] = dict(details)
    return envelope


def _envelope_response(envelope: Mapping[str, Any], status_code: int) -> JSONResponse:
    """Serialise an envelope as an ``application/json`` response."""
    return JSONResponse(content=dict(envelope), status_code=int(status_code))


def _failure_response(
    request_id: str, error: AdapterError, *, status_code: Optional[int] = None
) -> JSONResponse:
    """The §4.3.1 failure envelope for one :class:`AdapterError`.

    The HTTP status is the one 总纲 §4.4 declares for the code (``error.http_status``
    via :func:`app.core.errors.http_status_for`), never an ad-hoc one.
    """
    resolved = ErrorCode(error.error_code)
    return _envelope_response(
        build_envelope(
            success=False,
            code=resolved,
            message=error.message,
            data=None,
            request_id=request_id,
            details=error.details,
        ),
        status_code if status_code is not None else http_status_for(resolved),
    )


def _request_id_of(scope: Mapping[str, Any]) -> str:
    """The request id for this call: echo ``X-Request-ID``, else mint ``req_``.

    总纲 §4.1.3 closes the ID-prefix set and §4.1.2 fixes the shape, so a minted
    id goes through :func:`app.core.ids.new_id` with the ``req`` prefix — **not**
    ``request_``, which the closed-set guard rejects outright.
    """
    for name, value in scope.get("headers") or ():
        if bytes(name).lower() == REQUEST_ID_HEADER:
            candidate = bytes(value).decode("latin-1").strip()
            if candidate:
                return candidate
    return new_id("req")


# ---------------------------------------------------------------------------
# raw header helpers (no Starlette wrapper: these run inside a send() callback)
# ---------------------------------------------------------------------------
def _set_header(
    headers: Iterable[Tuple[bytes, bytes]], name: bytes, value: bytes
) -> List[Tuple[bytes, bytes]]:
    """Return ``headers`` with ``name`` set to exactly one ``value``."""
    kept = [(key, item) for key, item in headers if bytes(key).lower() != name]
    kept.append((name, value))
    return kept


def _header_value(headers: Iterable[Tuple[bytes, bytes]], name: bytes) -> str:
    """Return the first ``name`` header's value, decoded, or ``""``."""
    for key, value in headers:
        if bytes(key).lower() == name:
            return bytes(value).decode("latin-1")
    return ""


def _is_json_content_type(headers: Iterable[Tuple[bytes, bytes]]) -> bool:
    """True when the response is ``application/json`` (or a ``+json`` subtype)."""
    raw = _header_value(headers, b"content-type").split(";", 1)[0].strip().lower()
    return raw == "application/json" or raw.endswith("+json")


def _detail_message(payload: Any) -> str:
    """Human-readable message for a framework-generated ``{"detail": ...}`` body."""
    if isinstance(payload, Mapping):
        detail = payload.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail
        if detail is not None:
            return json.dumps(detail, ensure_ascii=False)
        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message
    if isinstance(payload, str) and payload.strip():
        return payload
    return "请求失败"


# ---------------------------------------------------------------------------
# the middleware
# ---------------------------------------------------------------------------
class EnvelopeMiddleware:
    """Pure ASGI middleware: request id + 总纲 §4.3.1 envelope.

    Deliberately **not** ``BaseHTTPMiddleware``.  Starlette's
    ``BaseHTTPMiddleware`` runs the downstream app in its own task group, which
    changes how ``http.disconnect`` reaches a streaming response and is the
    classic way an SSE endpoint starts buffering.  A plain ASGI callable leaves
    the streaming contract untouched — the only thing this class does to a
    ``text/event-stream`` response is add the ``X-Request-ID`` header.

    It sits **outside** ``ExceptionMiddleware`` and **inside**
    ``ServerErrorMiddleware`` (Starlette's documented stack order), which is what
    makes the two error branches below the only place a failure can be turned
    into a response:

    * :class:`~app.adapters.errors.AdapterError` -> its 总纲 §4.4 code and that
      code's HTTP status;
    * anything else -> ``INTERNAL_ERROR`` with the traceback **logged and not
      returned** (总纲 §4.4.9; a leaked traceback is an information disclosure).
    """

    def __init__(self, app: Any, *, exempt_paths: FrozenSet[str]) -> None:
        self.app = app
        self.exempt_paths = frozenset(exempt_paths)

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable[[], Any],
        send: Callable[[MutableMapping[str, Any]], Any],
    ) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path") or "")
        request_id = _request_id_of(scope)
        state = scope.setdefault("state", {})
        if isinstance(state, MutableMapping):
            state["request_id"] = request_id

        exempt = path in self.exempt_paths
        started: Optional[MutableMapping[str, Any]] = None
        buffered: List[bytes] = []
        passthrough = False

        async def send_wrapper(message: MutableMapping[str, Any]) -> None:
            nonlocal started, passthrough
            kind = message.get("type")
            if kind == "http.response.start":
                headers = _set_header(
                    message.get("headers") or (), REQUEST_ID_HEADER, request_id.encode("ascii")
                )
                started = {**message, "headers": headers}
                # Exceptions 1 and 2 of 总纲 §4.3.1 are recognised here, from the
                # response's own content-type, before a single body chunk exists:
                # a stream that is not JSON is forwarded verbatim.
                passthrough = exempt or not _is_json_content_type(headers)
                if passthrough:
                    await send(started)
                return
            if kind == "http.response.body":
                if passthrough:
                    await send(message)
                    return
                buffered.append(bytes(message.get("body") or b""))
                if message.get("more_body", False):
                    return
                await self._complete(send, started, buffered, request_id)
                return
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except AdapterError as exc:
            if started is not None:
                # The response is already on the wire; a second one cannot be
                # sent.  Log it and let the (broken) response end.
                _LOGGER.error(
                    "request_id=%s: AdapterError after response start: %s",
                    request_id,
                    exc.message,
                )
                return
            await _failure_response(request_id, exc)(scope, receive, send)
        except Exception as exc:  # noqa: BLE001 - the outermost REST boundary
            if started is not None:
                _LOGGER.exception(
                    "request_id=%s: unhandled error after response start", request_id
                )
                return
            # 总纲 §4.4.9 INTERNAL_ERROR.  The traceback goes to the log, never to
            # the caller: the message below is deliberately generic.
            _LOGGER.exception(
                "request_id=%s: unhandled exception in %s", request_id, path
            )
            await _failure_response(
                request_id,
                AdapterError(
                    ErrorCode.INTERNAL_ERROR,
                    "服务内部错误（未预期异常；详细信息见服务端日志，总纲 §4.4.9）。",
                    details={"path": path, "exception": type(exc).__name__},
                ),
            )(scope, receive, send)

    async def _complete(
        self,
        send: Callable[[MutableMapping[str, Any]], Any],
        started: Optional[MutableMapping[str, Any]],
        buffered: Sequence[bytes],
        request_id: str,
    ) -> None:
        """Wrap a buffered JSON response body in the §4.3.1 envelope."""
        if started is None:  # pragma: no cover - body without start is a protocol bug
            return
        status_code = int(started.get("status") or 200)
        raw = b"".join(buffered)
        payload: Any = None
        if raw:
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):  # pragma: no cover
                payload = None

        if status_code >= 400:
            code = FRAMEWORK_STATUS_CODES.get(status_code, ErrorCode.INTERNAL_ERROR)
            envelope = build_envelope(
                success=False,
                code=code,
                message=_detail_message(payload),
                data=None,
                request_id=request_id,
                details={"http_status": status_code},
            )
        else:
            envelope = build_envelope(
                success=True,
                code=ErrorCode.OK,
                message="操作成功",
                data=payload,
                request_id=request_id,
            )

        body = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
        headers = _set_header(
            started.get("headers") or (), b"content-length", str(len(body)).encode("ascii")
        )
        await send(
            {"type": "http.response.start", "status": status_code, "headers": headers}
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})


# ---------------------------------------------------------------------------
# the limiter (总纲 §4.4.2 RATE_LIMITED / §8.6, 裁决 B-7)
# ---------------------------------------------------------------------------
def _scope_header_values(scope: Mapping[str, Any], name: bytes) -> str:
    """Every occurrence of header ``name``, joined with ``", "``.

    ASGI may deliver one logical header as several ``(name, value)`` pairs, and
    ``X-Forwarded-For`` is additionally a comma-separated list *within* one value.
    Joining both shapes the same way is what lets
    :func:`app.core.rate_limit.client_key` take one consistent "last hop".
    """
    values = [
        bytes(value).decode("latin-1")
        for key, value in (scope.get("headers") or ())
        if bytes(key).lower() == name
    ]
    return ", ".join(values)


def _scope_client_host(scope: Mapping[str, Any]) -> Optional[str]:
    """``scope["client"][0]`` — the socket peer address, or ``None``.

    This is the value the ASGI server itself observed, so unlike any header it
    cannot be chosen by the caller.
    """
    client = scope.get("client")
    if isinstance(client, (tuple, list)) and client:
        host = client[0]
        return str(host) if host else None
    return None


def _rate_limit_headers(decision: RateLimitDecision) -> List[Tuple[bytes, bytes]]:
    """The three ``X-RateLimit-*`` headers for one decision.

    Sent on **every** response the limiter saw, not only on the 429: a client that
    can only learn its budget by being refused cannot back off before it is.
    """
    return [
        (RATE_LIMIT_LIMIT_HEADER, str(decision.limit).encode("ascii")),
        (RATE_LIMIT_REMAINING_HEADER, str(decision.remaining).encode("ascii")),
        (RATE_LIMIT_RESET_HEADER, str(decision.reset_after).encode("ascii")),
    ]


class RateLimitMiddleware:
    """Pure ASGI middleware: the token bucket of 总纲 §4.4.2 / §8.6.

    Deliberately **not** ``BaseHTTPMiddleware``, for the same reason
    :class:`EnvelopeMiddleware` is not: Starlette's ``BaseHTTPMiddleware`` runs the
    downstream app in its own task group and changes how ``http.disconnect``
    reaches a streaming response, which is the classic way an SSE endpoint starts
    buffering.  A plain ASGI callable leaves the streaming contract untouched.

    It is added **after** :class:`EnvelopeMiddleware` and therefore runs
    **outside** it, so a flood is refused before routing, before
    :class:`AuthService` and before the envelope machinery — the whole point of
    "rejected cheaply".  The three ``X-RateLimit-*`` headers are added to
    ``http.response.start`` on the way back out, so they land on enveloped JSON,
    on the 429, and on a ``text/event-stream`` response alike.

    SSE is charged **once, at connect**: this class runs once per HTTP request and
    an SSE stream is exactly one request.  Nothing in the stream generators
    (:func:`_task_event_stream` / :func:`_log_event_stream`) consults the limiter,
    so a stream the client is legitimately reading can never be killed mid-flight
    by a token it did not spend — the deliberate alternative (charging per event)
    would turn a long-running stream into a self-inflicted lockout.

    Keying is **IP-only**.  Authenticating the caller first would mean paying for
    the thing this middleware exists to avoid paying for, and the only cheap
    alternative — decoding the JWT's ``sub`` without verifying it — is *client
    controlled*, i.e. the same bypass as a naive ``X-Forwarded-For`` read: anyone
    could mint a fresh bucket per request by re-signing nothing at all.  So the
    socket peer address is the key, and ``X-Forwarded-For`` is honoured only under
    ``settings.trust_proxy_headers`` (see :func:`app.core.rate_limit.client_key`).
    """

    def __init__(
        self,
        app: Any,
        *,
        limiter: RateLimitLimiter,
        policy_loader: Callable[[], Awaitable[RateLimitPolicy]],
        exempt_paths: FrozenSet[str],
        policy_ttl_seconds: float = RATE_LIMIT_POLICY_TTL_SECONDS,
    ) -> None:
        self.app = app
        self.limiter = limiter
        self.policy_loader = policy_loader
        self.exempt_paths = frozenset(exempt_paths)
        self.policy_ttl_seconds = float(policy_ttl_seconds)
        self._policy: Optional[RateLimitPolicy] = None
        self._policy_read_at: float = float("-inf")

    def forget_policy(self) -> None:
        """Drop the cached policy so the next request re-reads ``security_configs``."""
        self._policy = None
        self._policy_read_at = float("-inf")

    async def _resolve_policy(self) -> RateLimitPolicy:
        """The current policy, re-read from ``security_configs`` at most every TTL.

        A failure to read the row must never become a 500 on a request that would
        otherwise have succeeded, so it degrades to :class:`Settings` — the same
        precedence the rest of the app uses, and the same "the row is optional"
        stance 裁决 C-9 takes for the session TTL.
        """
        moment = self.limiter.now()
        cached = self._policy
        if cached is not None and (moment - self._policy_read_at) < self.policy_ttl_seconds:
            return cached
        try:
            resolved = await self.policy_loader()
        except Exception:  # noqa: BLE001 - a config read must not fail a request
            _LOGGER.warning(
                "rate limit: security_configs read failed; using Settings", exc_info=True
            )
            resolved = RateLimitPolicy.from_settings(get_settings())
        self._policy = resolved
        self._policy_read_at = moment
        return resolved

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable[[], Any],
        send: Callable[[MutableMapping[str, Any]], Any],
    ) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path") or "")
        if path in self.exempt_paths:
            await self.app(scope, receive, send)
            return

        policy = await self._resolve_policy()
        if not policy.effective:
            await self.app(scope, receive, send)
            return

        settings = get_settings()
        key = client_key(
            client_host=_scope_client_host(scope),
            forwarded_for=_scope_header_values(scope, b"x-forwarded-for"),
            real_ip=_scope_header_values(scope, b"x-real-ip"),
            trust_proxy_headers=bool(settings.trust_proxy_headers),
        )
        decision = self.limiter.check(key, policy)
        if not decision.allowed:
            await self._reject(scope, send, decision, policy)
            return

        async def send_wrapper(message: MutableMapping[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                headers = message.get("headers") or ()
                for name, value in _rate_limit_headers(decision):
                    headers = _set_header(headers, name, value)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)

    async def _reject(
        self,
        scope: Mapping[str, Any],
        send: Callable[[MutableMapping[str, Any]], Any],
        decision: RateLimitDecision,
        policy: RateLimitPolicy,
    ) -> None:
        """Answer 总纲 §4.4.2 ``RATE_LIMITED`` (429) without calling the app at all.

        The body is the standard §4.3.1 envelope, built by the *same*
        :func:`build_envelope` the rest of this module uses, so the two envelopes
        cannot drift.  The HTTP status comes from the §4.4 registry via
        :func:`http_status_for`, never from a literal.
        """
        request_id = _request_id_of(scope)
        state = scope.setdefault("state", {})
        if isinstance(state, MutableMapping):
            state["request_id"] = request_id

        body = json.dumps(
            build_envelope(
                success=False,
                code=ErrorCode.RATE_LIMITED,
                message=(
                    "请求过于频繁：已超出令牌桶配额"
                    f"（security_configs.rate_limit_burst={policy.capacity} 次突发，"
                    f"rate_limit_per_minute={policy.limit_per_minute} 次/分钟；"
                    "总纲 §4.4.2 RATE_LIMITED，HTTP 429）。"
                ),
                data=None,
                request_id=request_id,
                details={
                    "reason": "rate_limited",
                    "burst": policy.capacity,
                    "per_minute": policy.limit_per_minute,
                    "retry_after": decision.retry_after,
                    "reset_after": decision.reset_after,
                },
            ),
            ensure_ascii=False,
        ).encode("utf-8")

        headers: List[Tuple[bytes, bytes]] = [
            *_rate_limit_headers(decision),
            (RETRY_AFTER_HEADER, str(decision.retry_after).encode("ascii")),
            (REQUEST_ID_HEADER, request_id.encode("ascii")),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
        ]
        _LOGGER.info(
            "rate limited: request_id=%s path=%s retry_after=%ss",
            request_id,
            scope.get("path"),
            decision.retry_after,
        )
        await send(
            {
                "type": "http.response.start",
                "status": http_status_for(ErrorCode.RATE_LIMITED),
                "headers": headers,
            }
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})


# ---------------------------------------------------------------------------
# request models (v1.2 §5.1)
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    """``POST /api/v1/auth/login`` body (v1.2 §5.1).

    ``extra="forbid"`` mirrors the MCP surface's ``additionalProperties: false``
    (V2.1 §6.1 / 裁决 B-4): an unexpected field is refused with
    ``VALIDATION_ERROR`` instead of being silently ignored.
    """

    model_config = ConfigDict(extra="forbid")

    username: str
    password: str


# ---------------------------------------------------------------------------
# shared request helpers
# ---------------------------------------------------------------------------
def _bearer_token(request: Request) -> Optional[str]:
    """The ``Authorization: Bearer <token>`` credential, or ``None`` (v1.2 §5.1)."""
    raw = request.headers.get("authorization")
    if not raw or not raw.strip():
        return None
    text = raw.strip()
    if text.lower().startswith("bearer "):
        text = text[7:].strip()
    return text or None


def _require_token(request: Request) -> str:
    """The bearer token, or 总纲 §4.4.1 ``AUTH_REQUIRED``."""
    token = _bearer_token(request)
    if token is None:
        raise AdapterError(
            ErrorCode.AUTH_REQUIRED,
            "未提供凭证：请在 Authorization 头中携带 Bearer Token"
            "（总纲 §4.4.1 AUTH_REQUIRED；v1.2 §5.1）。",
            details={"reason": "missing_credential"},
        )
    return token


async def _principal_of(request: Request) -> Principal:
    """Resolve the caller through the existing :class:`AuthService`.

    The service is reused verbatim — this function adds no verification of its
    own (总纲 §4.7.1's key derivation, the ``sessions`` row and the revocation
    check all stay in :meth:`AuthService.verify_token`).

    **总纲 裁决 C-13 is honoured here too.**  ``api_auth_required = 0`` means an
    unauthenticated call is not refused at all.  The MCP surface gets that for
    free from ``make_authorizer`` (it skips the whole gate), but these routes
    resolve the principal themselves — so without the branch below they kept
    answering ``AUTH_REQUIRED`` while MCP allowed the same caller, i.e. one config
    flag with two behaviours.
    """
    service = cast(AuthService, request.app.state.auth_service)
    policy = await service.security_policy()
    if not policy.api_auth_required:
        return anonymous_principal()
    return await service.verify_token(_require_token(request))


def _require_permission(principal: Principal, code: str) -> None:
    """The 总纲 §4.8.2 RBAC step, for the closed-set ``code``.

    No code is defined here: ``code`` is always one of the 34 members of
    :data:`app.core.constants.PERMISSION_CODES`, and a caller that does not hold
    it is refused with the existing ``PERMISSION_DENIED``.
    """
    if principal.has_permission(code):
        return
    raise AdapterError(
        ErrorCode.PERMISSION_DENIED,
        f"权限不足：需要 {code}（总纲 §4.8.2 封闭集合）；"
        f"principal roles={list(principal.roles)} 未持有该权限"
        "（总纲 §4.4.1 PERMISSION_DENIED）。",
        details={
            "reason": "missing_permission",
            "permission": code,
            "roles": list(principal.roles),
            "user_id": principal.user_id,
        },
    )


def _task_owner_scope(principal: Principal) -> Optional[int]:
    """The ``tasks.requested_by`` scope one principal may see (v1.2 §21).

    Returns ``None`` for "no ownership filter at all" — the ``super_admin`` case,
    which 总纲 §4.8.3 lets through to every row — and otherwise the caller's own
    user id.

    It exists as its own function because there are two consumers that must agree:
    the per-row predicate :func:`_task_visible_to` (detail / stream) and the
    *query* filter the list endpoint pushes into the store.  A second, hand-written
    rule at either site is how "three of four endpoints filter, the fourth returns
    everything" happens.

    The rule itself lives in :func:`app.services.task_service.task_owner_scope`,
    because the MCP surface (``midas_task``) needs it too — and when it lived only
    here, ``midas_task action=list`` enumerated every user's tasks while this
    layer refused them.  This is a thin adapter over that one definition.
    """
    return task_owner_scope(int(principal.user_id), tuple(principal.roles))


def _task_visible_to(record: TaskRecord, principal: Principal) -> bool:
    """Ownership filter for ``tasks.requested_by`` (v1.2 §21).

    This is the same shape 《MIDAS API 对接规范》§2.5.4 item 5 mandates for MIDAS
    instances: 总纲 §4.8.2's permission list is a **closed set**, so
    "only your own tasks" cannot become a new permission code — it is a
    **data-scope filter layered on top of** the ``task:read`` check that already
    ran.  Removing it would change *which rows* a caller reaches, never *which
    permission* it holds.

    ``requested_by is None`` means the task was created without attribution —
    authentication is off (总纲 裁决 C-13) or the caller was anonymous — so there
    is no owner to filter by and the §4.8.2 gate stands alone.  ``super_admin``
    holds every §4.8.2 code and is let through to any task.

    Defined in terms of :func:`_task_owner_scope` so the list endpoint's pushed-down
    filter and this predicate cannot diverge — and, like it, delegating to the one
    shared definition in :mod:`app.services.task_service` so the MCP surface cannot
    diverge from this one either.
    """
    return task_visible_to(
        record.requested_by,
        user_id=int(principal.user_id),
        roles=tuple(principal.roles),
    )


async def _load_record(request: Request, task_id: str) -> TaskRecord:
    """Load one ``tasks`` row, or 总纲 §4.4.6 ``TASK_NOT_FOUND``.

    Goes through the store protocol rather than the engine's private helpers, so
    the REST layer stays a caller of the documented interface.
    """
    service = cast(TaskService, request.app.state.task_service)
    record = await service.store.load_task(task_id)
    if record is None:
        raise AdapterError(
            ErrorCode.TASK_NOT_FOUND,
            f"任务 {task_id!r} 不存在（总纲 §4.4.6 TASK_NOT_FOUND）。",
            details={"task_id": task_id},
        )
    return record


async def _require_task_read(request: Request, task_id: str) -> Tuple[Principal, TaskRecord]:
    """Authenticate, check ``task:read`` and apply the ownership filter."""
    principal = await _principal_of(request)
    _require_permission(principal, TASK_READ_PERMISSION)
    record = await _load_record(request, task_id)
    if not _task_visible_to(record, principal):
        raise AdapterError(
            ErrorCode.PERMISSION_DENIED,
            f"任务 {task_id!r} 属于其他用户（tasks.requested_by="
            f"{record.requested_by}），不得访问。这是既有 task:read 之上的"
            "数据范围过滤，不引入新权限码（总纲 §4.8.2 封闭集合）。",
            details={
                "reason": "task_out_of_scope",
                "task_id": task_id,
                "requested_by": record.requested_by,
                "user_id": principal.user_id,
            },
        )
    return principal, record


def _display_name_now(factory: Callable[[], Session], user_id: int) -> Optional[str]:
    """``users.name`` for the §5.1 / §5.2 ``user.name`` field."""
    with session_scope_for(factory) as session:
        row = session.get(User, int(user_id))
        if row is None or not row.name:
            return None
        return str(row.name)


async def _display_name(request: Request, principal: Principal) -> str:
    """Display name, falling back to the username.

    ``Principal`` (v1.2 §38) carries the *login* name only, so the display name is
    read from ``users.name``; a database hiccup must not fail a login that has
    already succeeded.
    """
    factory = cast(Callable[[], Session], request.app.state.session_factory)
    try:
        resolved = await asyncio.to_thread(_display_name_now, factory, principal.user_id)
    except Exception:  # noqa: BLE001 - cosmetic field, never fatal
        _LOGGER.warning("display name lookup failed for user %s", principal.user_id)
        return principal.username
    return resolved or principal.username


def _user_block(principal: Principal, name: str) -> Dict[str, Any]:
    """The ``data.user`` object of v1.2 §5.1."""
    return {
        "id": principal.user_id,
        "username": principal.username,
        "name": name,
        "roles": list(principal.roles),
    }


def _login_payload(
    principal: Principal, name: str, token: str, expires_in: int, token_type: str
) -> Dict[str, Any]:
    """The ``data`` object shared by §5.1 login and §5.4 refresh."""
    return {
        "access_token": token,
        "token_type": token_type,
        "expires_in": expires_in,
        "user": _user_block(principal, name),
    }


# ---------------------------------------------------------------------------
# v1.2 §51 — pagination
# ---------------------------------------------------------------------------
def _page_bounds(page: int, page_size: int) -> Tuple[int, int]:
    """Clamp ``page`` / ``page_size`` to §51's documented range."""
    size = max(1, min(int(page_size or DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE))
    current = max(1, int(page or 1))
    return current, size


def _pagination(items: Sequence[Any], page: int, page_size: int, total: int) -> Dict[str, Any]:
    """``data.items`` + ``data.pagination`` (v1.2 §51)."""
    size = max(1, int(page_size))
    return {
        "items": list(items),
        "pagination": {
            "page": int(page),
            "page_size": size,
            "total": int(total),
            "total_pages": (int(total) + size - 1) // size if total else 0,
        },
    }


def _matches_task_filters(
    item: Mapping[str, Any],
    *,
    action: Optional[str],
    adapter: Optional[str],
    keyword: Optional[str],
) -> bool:
    """Post-filters for the v1.2 §20.1 parameters the Task Engine does not take."""
    if action is not None and str(item.get("action") or "") != action:
        return False
    if adapter is not None and str(item.get("adapter_code") or "") != adapter:
        return False
    if keyword:
        needle = keyword.strip().lower()
        haystack = " ".join(
            str(item.get(key) or "")
            for key in (
                "task_id",
                "type",
                "action",
                "resource",
                "tool_name",
                "adapter_code",
                "error_message",
            )
        ).lower()
        if needle not in haystack:
            return False
    return True


# ---------------------------------------------------------------------------
# v1.2 §21 — task SSE
# ---------------------------------------------------------------------------
def _resume_cursor(request: Request, since: Optional[str]) -> int:
    """The event-id cursor: ``Last-Event-ID`` header, else ``?since=``.

    V2.1 §10.3 expresses the cursor as the ``task_events.id`` of the last event a
    client saw, and the SSE specification has the browser replay exactly that
    value in ``Last-Event-ID`` on reconnect — the two are the same integer, which
    is why the same cursor serves ``midas_task action=events`` and this stream.

    The header is treated leniently (a browser echo that is not a number is
    ignored, so a stream never fails to open because of a stale header); the
    explicit ``?since=`` parameter is validated, because a caller that typed one
    meant it.
    """
    header = request.headers.get("last-event-id")
    if header and header.strip().isdigit():
        return int(header.strip())
    if since is None or not since.strip():
        return 0
    text = since.strip()
    if not text.isdigit():
        raise AdapterError(
            ErrorCode.VALIDATION_ERROR,
            f"since={text!r} 不是合法的事件游标；v1.2 §21 使用 task_events.id "
            "整数游标（V2.1 §10.3）。",
            details={"since": text},
        )
    return int(text)


def _task_event_data(event_type: str, source: Mapping[str, Any]) -> Dict[str, Any]:
    """Project one event onto the v1.2 §21 payload table.

    The four documented event names carry exactly the fields §21 lists.  Any other
    ``event_type`` (``queued``, ``log``, a future type) is sent with the full
    ``task_events`` payload, because §21's table is the authority for the four it
    names and inventing a fifth name would be a change to a documented interface.
    """
    name = TASK_SSE_EVENT_NAMES.get(event_type)
    task_id = source.get("task_id")
    if name == "task.started":
        return {"task_id": task_id, "type": source.get("type"), "action": source.get("action")}
    if name == "task.progress":
        return {"task_id": task_id, "progress": source.get("progress")}
    if name == "task.completed":
        return {
            "task_id": task_id,
            "status": source.get("status"),
            "progress": source.get("progress"),
        }
    if name == "task.retrying":
        return {"task_id": task_id, "retry_count": source.get("retry_count")}
    return {
        "task_id": task_id,
        "event_type": event_type,
        "status": source.get("status"),
        "progress": source.get("progress"),
        "message": source.get("message"),
        "payload": source.get("payload"),
        "created_at": source.get("created_at"),
    }


def _task_sse(event_id: Optional[int], source: Mapping[str, Any]) -> ServerSentEvent:
    """One ``ServerSentEvent`` for a task event (v1.2 §21).

    ``id`` is the ``task_events.id`` — it is what the browser echoes back in
    ``Last-Event-ID``, so it must be the *store's* id and never a local counter.
    """
    event_type = str(source.get("event_type") or "")
    name = TASK_SSE_EVENT_NAMES.get(event_type)
    return ServerSentEvent(
        data=json.dumps(_task_event_data(event_type, source), ensure_ascii=False),
        event=name,
        id=str(int(event_id)) if event_id else None,
    )


def _event_row_source(record: TaskRecord, event: TaskEventRecord) -> Dict[str, Any]:
    """Project a stored ``task_events`` row for :func:`_task_sse`.

    The row carries no ``status`` of its own, so it is derived from the row's own
    ``event_type`` (``EVENT_TYPE_STATUS``) rather than read off the live record:
    a reconnect after the task moved on must still see each event's historical
    status, and ``failed -> retrying -> finished`` would otherwise be flattened.
    """
    return {
        **event.to_payload(),
        "status": EVENT_TYPE_STATUS.get(event.event_type, record.status),
        "type": record.type,
        "action": record.action,
        "retry_count": record.retry_count,
        "requested_by": record.requested_by,
    }


async def _task_event_stream(
    service: TaskService,
    bus: EventBus,
    record: TaskRecord,
    cursor: int,
    holder: Dict[str, Subscription],
) -> AsyncIterator[ServerSentEvent]:
    """v1.2 §21 — replay from the cursor, then follow the live topic.

    Ordering matters and is deliberate: the subscription is opened **first**, so
    an event emitted while the replay is still running is already buffered and
    cannot fall into the gap.  That makes duplicates possible instead of losses,
    and duplicates are removed by the monotonic ``task_events.id`` — the same
    cursor, used as a high-water mark.

    The stream closes once the task reaches a terminal state (总纲 §4.2.1).  v1.2
    §21's table ends at ``task.completed``, and an ``EventSource`` that is left
    open would otherwise reconnect forever against a task that can never move
    again.
    """
    subscription = bus.subscribe(task_topic(record.task_id))
    holder["subscription"] = subscription
    last_id = int(cursor)
    try:
        stored = await service.store.load_events(record.task_id, since=cursor or None)
        for event in stored:
            if event.id <= last_id:
                continue
            last_id = event.id
            yield _task_sse(event.id, _event_row_source(record, event))
            if EVENT_TYPE_STATUS.get(event.event_type) in TERMINAL_STATUSES:
                return

        if record.status in TERMINAL_STATUSES:
            # The task is done but its terminal event was not among the replayed
            # rows (the cursor is past it, or `_emit` is still writing it).  Close
            # the stream with a terminal projection rather than hanging.
            yield _task_sse(last_id or None, _terminal_source(record))
            return

        seen_dropped = 0
        async for item in subscription:
            if subscription.dropped > seen_dropped:
                seen_dropped = subscription.dropped
                yield ServerSentEvent(
                    comment=(
                        f"dropped {seen_dropped} event(s): 订阅者队列已满，"
                        "按 drop-oldest 策略丢弃了最早的缓冲事件"
                        "（见 app.services.event_bus 的慢订阅者策略）；"
                        "请用 Last-Event-ID 重新拉取。"
                    )
                )
            event_id = int(item.get("id") or 0)
            if event_id and event_id <= last_id:
                continue
            if event_id:
                last_id = event_id
            yield _task_sse(event_id or None, item)
            if str(item.get("status") or "") in TERMINAL_STATUSES:
                return
    finally:
        # Also reached when the client hangs up mid-stream (the task group
        # cancels this generator) — which is why the disconnect callback below is
        # a second, not the only, unsubscribe point.
        await subscription.close()
        holder.pop("subscription", None)


def _terminal_source(record: TaskRecord) -> Dict[str, Any]:
    """A terminal event projected straight from the record (v1.2 §21)."""
    event_type = {
        TaskStatus.SUCCESS.value: "finished",
        TaskStatus.FAILED.value: "failed",
        TaskStatus.CANCELLED.value: "cancelled",
    }.get(record.status, "finished")
    return {
        "task_id": record.task_id,
        "event_type": event_type,
        "status": record.status,
        "progress": record.progress,
        "message": record.error_message,
        "payload": None,
        "created_at": None,
        "type": record.type,
        "action": record.action,
        "retry_count": record.retry_count,
        "requested_by": record.requested_by,
    }


# ---------------------------------------------------------------------------
# v1.2 §22.3 — log SSE
# ---------------------------------------------------------------------------
def _log_level(event_type: str) -> str:
    """Map a task event onto a ``system_logs.level`` name (v1.2 §22.1).

    ``system_logs.level`` is a Python logging level name (INFO / WARNING /
    ERROR), so this is a projection, not a new vocabulary.
    """
    if event_type in ("failed", "error"):
        return "ERROR"
    if event_type in ("cancelled", "warning"):
        return "WARNING"
    return "INFO"


def _log_payload(item: Mapping[str, Any]) -> Dict[str, Any]:
    """The v1.2 §22.3 ``log.appended`` payload."""
    return {
        "id": item.get("id"),
        "timestamp": item.get("created_at"),
        "level": _log_level(str(item.get("event_type") or "")),
        "module": "task",
        "task_id": item.get("task_id"),
        "message": item.get("message"),
    }


async def _log_event_stream(
    bus: EventBus,
    principal: Principal,
    holder: Dict[str, Subscription],
) -> AsyncIterator[ServerSentEvent]:
    """v1.2 §22.3 — the global feed, rendered as ``log.appended``.

    Subscribes to the global ``tasks`` topic (the same topic the Task Engine
    mirrors every event onto for a dashboard feed) and applies the same
    ``requested_by`` data-scope filter as the per-task stream, so the aggregate
    feed cannot become a way around the per-task ownership rule.  Unlike the
    per-task stream it never ends on its own: there is no terminal state for "all
    logs".
    """
    subscription = bus.subscribe(TASKS_TOPIC)
    holder["subscription"] = subscription
    seen_dropped = 0
    try:
        async for item in subscription:
            if subscription.dropped > seen_dropped:
                seen_dropped = subscription.dropped
                yield ServerSentEvent(
                    comment=(
                        f"dropped {seen_dropped} event(s): 订阅者队列已满，"
                        "按 drop-oldest 策略丢弃了最早的缓冲事件。"
                    )
                )
            owner = item.get("requested_by")
            if owner is not None and int(owner) != int(principal.user_id):
                if SUPER_ADMIN_ROLE not in principal.roles:
                    continue
            event_id = item.get("id")
            yield ServerSentEvent(
                data=json.dumps(_log_payload(item), ensure_ascii=False),
                event="log.appended",
                id=str(int(event_id)) if event_id else None,
            )
    finally:
        await subscription.close()
        holder.pop("subscription", None)


def _sse_response(
    content: AsyncIterator[ServerSentEvent], holder: Dict[str, Subscription]
) -> EventSourceResponse:
    """Build the SSE response, wiring the documented unsubscribe seam.

    ``client_close_handler_callable`` is where ``sse_starlette`` reports a client
    disconnect; it is handed the ASGI ``http.disconnect`` message (the parameter
    is a *message*, not the scope — see the note in the report).  The subscription
    is closed there **and** in each generator's ``finally``; ``close()`` is
    idempotent, so whichever fires first wins and the other is a no-op.
    """

    async def _on_client_close(_message: Any) -> None:
        subscription = holder.get("subscription")
        if subscription is not None:
            await subscription.close()

    return EventSourceResponse(
        content,
        media_type="text/event-stream",
        client_close_handler_callable=_on_client_close,
    )


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------
router = APIRouter(prefix=API_PREFIX)


# --- v1.2 §5 — authentication --------------------------------------------- #
@router.post("/auth/login")
async def login(request: Request, body: LoginRequest) -> Dict[str, Any]:
    """v1.2 §5.1 — verify credentials and issue a bearer token.

    ``expires_in`` comes from ``security_configs.session_timeout_minutes × 60``
    (总纲 裁决 C-9) because :meth:`AuthService.login` derives it; nothing here
    hard-codes a TTL.
    """
    service = cast(AuthService, request.app.state.auth_service)
    client = request.client
    result = await service.login(
        body.username,
        body.password,
        ip_address=client.host if client is not None else None,
        user_agent=request.headers.get("user-agent"),
    )
    name = await _display_name(request, result.principal)
    return _login_payload(
        result.principal, name, result.token, result.expires_in, result.token_type
    )


@router.get("/auth/me")
async def me(request: Request) -> Dict[str, Any]:
    """v1.2 §5.2 — the caller's identity and its §4.8.2 permissions."""
    principal = await _principal_of(request)
    name = await _display_name(request, principal)
    return {
        **_user_block(principal, name),
        "permissions": sorted(principal.permissions),
    }


@router.post("/auth/logout")
async def logout(request: Request) -> Dict[str, Any]:
    """v1.2 §5.3 — revoke the caller's ``sessions`` row.

    Revoking is idempotent at the service level and does not enforce ``exp``
    (``AuthService.logout`` documents why), so a second logout still answers
    ``success``.
    """
    service = cast(AuthService, request.app.state.auth_service)
    token = _require_token(request)
    revoked = await service.logout(token)
    return {"revoked": bool(revoked)}


@router.post("/auth/refresh")
async def refresh(request: Request) -> Dict[str, Any]:
    """v1.2 §5.4 — issue a new token for the caller, with a fresh TTL.

    The session is **rotated, not extended**, and the rotation lives in
    :meth:`AuthService.refresh`: ``sessions`` is a table ``AuthService`` owns, so
    this layer no longer writes it (it used to, which is exactly the kind of
    second writer that rots as the session model grows).  All this handler does is
    authenticate, delegate, and map the result onto §5.4's payload — every refusal
    code (``AUTH_REQUIRED`` / ``AUTH_INVALID`` / ``AUTH_EXPIRED``) comes back from
    the service unchanged.
    """
    service = cast(AuthService, request.app.state.auth_service)
    token = _require_token(request)
    client = request.client
    result = await service.refresh(
        token,
        ip_address=client.host if client is not None else None,
        user_agent=request.headers.get("user-agent"),
    )
    name = await _display_name(request, result.principal)
    return _login_payload(
        result.principal, name, result.token, result.expires_in, result.token_type
    )


# --- v1.2 §34–§36 — health ------------------------------------------------ #
def _probe_database_now(factory: Callable[[], Session]) -> bool:
    """One round trip to the database; ``True`` when it answers."""
    with session_scope_for(factory) as session:
        session.execute(sql_text("SELECT 1"))
    return True


async def _probe_database(factory: Callable[[], Session]) -> bool:
    try:
        return await asyncio.to_thread(_probe_database_now, factory)
    except Exception:  # noqa: BLE001 - a failed probe is a health fact, not a 500
        _LOGGER.warning("health: database probe failed", exc_info=True)
        return False


def _probe_disk() -> str:
    """Disk probe for the aggregate check (v1.2 §34).

    A file-backed SQLite deployment is healthy when the database's directory is
    reachable; a non-SQLite (or in-memory) deployment has nothing to check here.
    """
    settings = get_settings()
    path = settings.sqlite_file_path
    if not path:
        return "healthy"
    try:
        from pathlib import Path

        parent = Path(path).expanduser().parent
        return "healthy" if parent.exists() else "degraded"
    except Exception:  # noqa: BLE001
        return "degraded"


@router.get("/health")
async def health(request: Request) -> Dict[str, Any]:
    """v1.2 §34 — aggregate health.  **Enveloped**: §34 is not an exception."""
    factory = cast(Callable[[], Session], request.app.state.session_factory)
    registry = cast(AdapterRegistry, request.app.state.registry)
    database = await _probe_database(factory)
    adapter = "healthy" if registry.codes() else "degraded"
    disk = _probe_disk()
    mcp_server = "running" if request.app.state.mcp_server is not None else "stopped"
    components = {
        "database": "healthy" if database else "unhealthy",
        "mcp_server": mcp_server,
        "adapter": adapter,
        "disk": disk,
    }
    status = "healthy" if all(value == "healthy" or value == "running" for value in components.values()) else "degraded"
    return {"status": status, **components}


@router.get("/health/ready")
async def health_ready(request: Request) -> Response:
    """v1.2 §35 — readiness.  **Exception 3**: a bare status code, no envelope."""
    factory = cast(Callable[[], Session], request.app.state.session_factory)
    if await _probe_database(factory):
        return PlainTextResponse("ready", status_code=200)
    return PlainTextResponse("unavailable", status_code=503)


@router.get("/health/live")
async def health_live() -> Response:
    """v1.2 §36 — liveness.  **Exception 3**: a bare status code, no envelope."""
    return PlainTextResponse("alive", status_code=200)


# --- v1.2 §20 — tasks ------------------------------------------------------ #
@router.get("/tasks")
async def list_tasks(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    status: Optional[str] = Query(default=None),
    type: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    adapter: Optional[str] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """v1.2 §20.1 — the task list, ``data.items`` + ``data.pagination``.

    ``type`` / ``status`` are pushed down to the Task Engine (they are closed
    vocabularies it validates, V2.1 §26.2 / 总纲 §4.2.1).  ``action`` /
    ``adapter`` / ``keyword`` are not engine filters, so they are applied over the
    full matching set here; §51 caps a page at 500 rows, which is the documented
    ceiling of that post-filter.

    The **ownership filter is pushed into the store query**, not applied to the
    returned page: filtering afterwards would leave ``pagination.total`` counting
    other users' tasks (an information leak in its own right) and would return
    short or empty pages while the rows sit on later ones.  ``requested_by`` is
    :func:`_task_owner_scope`'s value — ``None`` for ``super_admin``, the caller's
    id otherwise — and the store keeps unattributed (``requested_by IS NULL``)
    tasks visible to everyone, exactly as :func:`_task_visible_to` does.
    """
    principal = await _principal_of(request)
    _require_permission(principal, TASK_READ_PERMISSION)
    service = cast(TaskService, request.app.state.task_service)
    current, size = _page_bounds(page, page_size)
    scope = _task_owner_scope(principal)

    if action is None and adapter is None and not keyword:
        payload = await service.list(
            type=type, status=status, page=current, page_size=size, requested_by=scope
        )
        return _pagination(
            payload.get("items") or [], current, size, int(payload.get("total") or 0)
        )

    payload = await service.list(
        type=type,
        status=status,
        page=1,
        page_size=MAX_PAGE_SIZE,
        requested_by=scope,
    )
    rows = [
        item
        for item in (payload.get("items") or [])
        if _matches_task_filters(item, action=action, adapter=adapter, keyword=keyword)
    ]
    start = (current - 1) * size
    return _pagination(rows[start : start + size], current, size, len(rows))


@router.get("/tasks/{task_id}")
async def get_task(request: Request, task_id: str) -> Dict[str, Any]:
    """v1.2 §20.2 — one task.  Ownership is enforced (v1.2 §21's data scope)."""
    _principal, record = await _require_task_read(request, task_id)
    return record.to_payload(include_result=False)


@router.get("/tasks/{task_id}/stream")
async def stream_task(
    request: Request,
    task_id: str,
    since: Optional[str] = Query(
        default=None,
        description="task_events.id 游标；等价于 SSE 的 Last-Event-ID 头（v1.2 §21）。",
    ),
) -> Response:
    """v1.2 §21 — the task's event stream.  **Exception 1**: no envelope."""
    _principal, record = await _require_task_read(request, task_id)
    cursor = _resume_cursor(request, since)
    service = cast(TaskService, request.app.state.task_service)
    bus = cast(EventBus, request.app.state.event_bus)
    holder: Dict[str, Subscription] = {}
    return _sse_response(
        _task_event_stream(service, bus, record, cursor, holder), holder
    )


# --- v1.2 §22.3 — log stream ---------------------------------------------- #
@router.get("/logs/stream")
async def stream_logs(request: Request) -> Response:
    """v1.2 §22.3 — the global log stream.  **Exception 1**: no envelope.

    Requires the same closed-set ``task:read`` code as the task stream — §22.3
    names no code of its own, and 总纲 §4.8.2 forbids adding one.
    """
    principal = await _principal_of(request)
    _require_permission(principal, TASK_READ_PERMISSION)
    bus = cast(EventBus, request.app.state.event_bus)
    holder: Dict[str, Subscription] = {}
    return _sse_response(_log_event_stream(bus, principal, holder), holder)


# ---------------------------------------------------------------------------
# adapter registration (V2.1 §15 / §21)
# ---------------------------------------------------------------------------
def _register_adapters(registry: AdapterRegistry, *, allow_mock: bool) -> List[str]:
    """Populate ``registry`` from ``app/core/midas_config.py``, then the mock.

    The configured adapters are the real ones; the mock is only a development
    fallback and is never registered unless explicitly allowed (it answers
    fabricated data — see :func:`app.mcp.server.register_mock_adapter`).  Nothing
    logged here is secret: only adapter codes and the config file's location.
    """
    try:
        codes = register_configured_adapters(registry)
    except MidasConfigError as exc:
        _LOGGER.warning("no MIDAS adapter configured: %s", exc)
        codes = []
    if codes:
        _LOGGER.info("registered MIDAS adapters: %s", ", ".join(codes))
        return codes
    if allow_mock:
        code = register_mock_adapter(registry)
        _LOGGER.warning(
            "registered the in-memory mock adapter %r; every answer is fabricated",
            code,
        )
        return [code]
    _LOGGER.warning(
        "no MIDAS adapter registered; configure backend/config/midas.json "
        "(template: config/midas.example.json)"
    )
    return []


# ---------------------------------------------------------------------------
# the factory
# ---------------------------------------------------------------------------
def create_app(
    *,
    title: str = "StructAI Manager API",
    event_bus: Optional[EventBus] = None,
    task_service: Optional[TaskService] = None,
    auth_service: Optional[AuthService] = None,
    registry: Optional[AdapterRegistry] = None,
    session_factory: Optional[Callable[[], Session]] = None,
    register_adapters: bool = True,
    allow_mock_adapter: bool = False,
    exempt_paths: Optional[FrozenSet[str]] = None,
    rate_limiter: Optional[RateLimitLimiter] = None,
) -> FastAPI:
    """Build the REST/SSE application (v1.2 §3.2, §5, §20–§22.3, §34–§36).

    Every collaborator is injectable, which is what keeps the offline suite
    offline: a test passes its own ``task_service`` (in-memory store), its own
    ``auth_service`` (a ``tmp_path`` SQLite file) and ``register_adapters=False``,
    and the lifespan then does no discovery at all.  ``rate_limiter`` follows the
    same rule — a test can hand in a limiter with an injected clock and a small
    bucket instead of sleeping for a minute.

    The lifespan is the documented bootstrap order:

    1. resolve the session factory (lazily importing :mod:`app.db.session` so that
       merely importing this module never creates an engine);
    2. build the Task Engine over the durable :class:`SqlAlchemyTaskStore` and
       ``await init_task_service(...)`` — the hook the persistence milestone left
       unwired, which is what reconciles tasks orphaned by a restart (V2.1 §26.1);
    3. build the :class:`AuthService`;
    4. register the configured adapters (``app/core/midas_config.py``);
    5. build the dispatcher and the MCP server (v1.2 §37 keeps ``/mcp`` separate
       from ``/api/v1``, so the server object is assembled but not mounted here);
    6. on shutdown, close the bus so open SSE streams end.

    Middleware order is deliberate: ``EnvelopeMiddleware`` is added first and
    ``RateLimitMiddleware`` second, and Starlette prepends each one, so the
    limiter ends up **outermost** — a flood is refused before routing and before
    any authentication work (总纲 §8.6).

    Nothing secret is logged: adapter codes and file paths only.
    """
    bus = event_bus if event_bus is not None else EventBus()
    reg = registry if registry is not None else get_registry()

    application = FastAPI(
        title=title,
        version="1.0",
        description=(
            "StructAI 管理器 REST API（v1.2）。统一信封见《总纲》§4.3.1；"
            "例外仅四类：SSE 流、文件下载、/health/ready 与 /health/live、OpenAPI。"
        ),
        lifespan=_lifespan,
    )

    # --- state the lifespan reads and fills ------------------------------ #
    application.state.event_bus = bus
    application.state.registry = reg
    application.state.session_factory = session_factory
    application.state.task_service = task_service
    application.state.auth_service = auth_service
    application.state.dispatcher = None
    application.state.mcp_server = None
    application.state.register_adapters = bool(register_adapters)
    application.state.allow_mock_adapter = bool(allow_mock_adapter)
    application.state.envelope_exempt_paths = (
        frozenset(exempt_paths) if exempt_paths is not None else ENVELOPE_EXEMPT_PATHS
    )
    limiter = rate_limiter if rate_limiter is not None else RateLimitLimiter()
    application.state.rate_limiter = limiter

    async def _load_rate_limit_policy() -> RateLimitPolicy:
        """Resolve 裁决 B-7's three fields for the limiter.

        Precedence is the documented one: the ``security_configs`` singleton row
        **wins**, and :class:`Settings` is only the fallback for the two cases in
        which the row cannot speak — no :class:`AuthService` is wired at all, or
        the read failed (the middleware catches that and falls back itself).  A
        missing row is not an error: :meth:`AuthService.security_policy_now`
        returns the DDL defaults, which are the same numbers, so "row absent" and
        "no database" cannot disagree.
        """
        service = application.state.auth_service
        if service is None:
            return RateLimitPolicy.from_settings(get_settings())
        policy = await cast(AuthService, service).security_policy()
        return RateLimitPolicy(
            enabled=bool(policy.rate_limit_enabled),
            per_minute=int(policy.rate_limit_per_minute),
            burst=int(policy.rate_limit_burst),
        )

    # Added in this order so that Starlette's prepend-on-add leaves the limiter
    # outermost: a flood is refused before routing, before AuthService, and before
    # the envelope machinery (总纲 §4.4.2 / §8.6).
    application.add_middleware(
        EnvelopeMiddleware, exempt_paths=application.state.envelope_exempt_paths
    )
    application.add_middleware(
        RateLimitMiddleware,
        limiter=limiter,
        policy_loader=_load_rate_limit_policy,
        exempt_paths=RATE_LIMIT_EXEMPT_PATHS,
    )
    application.include_router(router)
    return application


@asynccontextmanager
async def _lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Application bootstrap and teardown (see :func:`create_app`)."""
    bus = cast(EventBus, application.state.event_bus)

    factory = application.state.session_factory
    if factory is None:
        from app.db.session import SessionLocal  # local: no engine at import time

        factory = SessionLocal
        application.state.session_factory = factory

    service = application.state.task_service
    if service is None:
        service = TaskService(store=SqlAlchemyTaskStore(factory), event_bus=bus)
        application.state.task_service = service
    # V2.1 §26.1 — must run once, before traffic, so a restart never leaves a row
    # silently ``running`` forever.  ``init_task_service`` returns the *service*
    # (not the recovered ids), and ``recover_orphans`` writes one ``failed`` event
    # per orphan, so the durable record of what happened is the ``task_events``
    # table rather than a count logged here.
    await init_task_service(service)

    if application.state.auth_service is None:
        application.state.auth_service = AuthService(session_factory=factory)

    if application.state.register_adapters:
        _register_adapters(
            cast(AdapterRegistry, application.state.registry),
            allow_mock=bool(application.state.allow_mock_adapter),
        )

    dispatcher = ToolDispatcher(
        registry=cast(AdapterRegistry, application.state.registry),
        task_service=service,
        authorizer=make_authorizer(cast(AuthService, application.state.auth_service)),
    )
    application.state.dispatcher = dispatcher
    application.state.mcp_server = build_server(
        registry=cast(AdapterRegistry, application.state.registry),
        dispatcher=dispatcher,
        task_service=service,
    )
    _LOGGER.info(
        "StructAI REST API ready: %d adapter(s), %d task(s) tracked",
        len(cast(AdapterRegistry, application.state.registry).codes()),
        len(service),
    )
    try:
        yield
    finally:
        await bus.close()


#: ``uvicorn app.main:app`` — the ASGI entry point.
app: FastAPI = create_app()


def uvicorn_options() -> Dict[str, Any]:
    """uvicorn settings for the supported launcher (:func:`main`).

    **``proxy_headers`` must follow ``settings.trust_proxy_headers``, never
    uvicorn's own default.**  uvicorn defaults it to ``True`` and installs
    ``ProxyHeadersMiddleware`` *outside* the application, where it rewrites
    ``scope["client"]`` from ``X-Forwarded-For`` before any app middleware runs.
    That silently defeats :class:`RateLimitMiddleware`'s key:
    ``app.core.rate_limit.client_key`` refuses to read the header unless
    ``trust_proxy_headers`` is on, but by then the forged address *is* the client
    address — the guard is correct and unreachable.

    Measured against a live server with ``rate_limit_burst=3``, six requests each
    carrying a different forged ``X-Forwarded-For``:

    ==========================================  ==========================
    launch                                      result
    ==========================================  ==========================
    ``--no-proxy-headers``                      ``200 200 200 429 429 429``
    uvicorn default (proxy headers on)          ``200 200 200 200 200 200``
    ==========================================  ==========================

    Identical app, config and database — the launch flag was the only variable,
    and with the default on each forged address minted its own token bucket, so
    the limit was bypassable by a for-loop.
    """
    settings = get_settings()
    return {
        "host": settings.api_host,
        "port": settings.api_port,
        "log_level": settings.log_level.lower(),
        "proxy_headers": bool(settings.trust_proxy_headers),
    }


def main() -> int:
    """``python -m app.main`` — run the REST/SSE service with uvicorn."""
    import uvicorn

    settings = get_settings()
    if not settings.trust_proxy_headers:
        # A security-relevant footgun is worth a line on every start: this only
        # protects callers who launch through here.  ``uvicorn app.main:app``
        # directly gets uvicorn's default and re-opens the bypass.
        _LOGGER.warning(
            "trust_proxy_headers=False -> starting uvicorn with proxy_headers=False. "
            "If you launch uvicorn yourself, pass --no-proxy-headers: uvicorn's "
            "default (on) rewrites the client address from X-Forwarded-For outside "
            "this app, which makes the rate limiter's key client-controlled."
        )
    uvicorn.run("app.main:app", **uvicorn_options())
    return 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
