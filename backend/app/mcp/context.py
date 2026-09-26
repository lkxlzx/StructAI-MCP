"""Dispatch context and the shared request builders used by the four tools.

This module exists so that :mod:`app.mcp.tools` and :mod:`app.mcp.dispatcher` can
share one context type without importing each other (the dispatcher imports the
tools; the tools must not import the dispatcher).

Everything here is *plumbing*: no routing decisions live in this file.
"""

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping

from app.adapters.base import MidasAdapter
from app.adapters.errors import AdapterError
from app.adapters.registry import AdapterRegistry
from app.core.errors import ErrorCode
from app.mcp.capabilities import Capability
from app.mcp.capability import CapabilityResolver
from app.services.task_service import TaskService

__all__ = [
    "AuthRequest",
    "Authorizer",
    "DispatchContext",
    "client_id_of",
    "options_of",
    "timeout_of",
    "require_adapter",
    "adapter_method",
    "as_dict",
]


@dataclass
class AuthRequest:
    """What the auth/RBAC seam sees (v1.2 §38 「Authentication -> RBAC」).

    Deliberately *not* a :class:`DispatchContext`: the hook runs **before** the
    capability is resolved, so it cannot receive one.

    **Not frozen, on purpose.**  The seam's contract is "raise
    :class:`~app.adapters.errors.AdapterError` to refuse, return ``None`` to
    allow" — which leaves no way to hand back what it resolved.  ``principal``
    therefore doubles as a **write-back channel**: it arrives holding whatever
    the caller supplied (a token, a header mapping, or an already-resolved
    ``Principal``) and the authorizer replaces it with the concrete
    ``Principal`` it verified.  The dispatcher reads it after ``_authorize`` and
    passes it to the tool handler.

    Without that channel the resolved identity was discarded, so nothing could
    attribute a call — which is why ``tasks.requested_by`` was always NULL and
    a task stream could not be filtered to its owner (总纲 §4.1.5).
    """

    request_id: str
    tool: str
    action: str
    resource: str | None
    #: 总纲 §4.8.2 permission code, from
    #: :func:`app.mcp.capabilities.required_permission`.
    permission: str
    arguments: Mapping[str, Any]
    principal: Any = None


#: The seam's shape.  Raise :class:`~app.adapters.errors.AdapterError` with a
#: 总纲 §4.4 code to refuse; return ``None`` (or an awaitable) to allow.
Authorizer = Callable[[AuthRequest], Awaitable[None] | None]


@dataclass
class DispatchContext:
    """Everything a tool handler needs, assembled by the dispatcher.

    The dispatcher fills this **after** ``CapabilityResolver.resolve()``
    (V2.1 §16) and the ``AdapterRegistry`` lookup (V2.1 §21), so a handler never
    performs routing of its own.
    """

    #: ``req_`` tracking id of this MCP call (总纲 §4.1.3 / §4.1.5).
    request_id: str
    #: One of the four tool names (v1.2 §37).
    tool: str
    #: The resolved capability row.
    capability: Capability
    #: Registered adapter instance; ``None`` for platform-owned capabilities
    #: (``midas_task`` — 对接规范 §2.5.1: MIDAS has no task API).
    adapter: MidasAdapter | None
    #: V2.1 §21 registry, for handlers that need a second adapter lookup.
    registry: AdapterRegistry
    #: V2.1 §26 Task Engine.
    tasks: TaskService
    #: V2.1 §16 resolver.
    resolver: CapabilityResolver
    #: ``midas_clients.id`` (INTEGER, 裁决 N-6) from the caller's ``client_id``.
    midas_client_id: int | None = None
    #: 总纲 §4.8.2 permission code the RBAC seam should have checked.
    permission: str = ""
    #: Opaque caller identity passed through to the auth seam.
    principal: Any = None
    #: The validated arguments, verbatim.
    arguments: Mapping[str, Any] = field(default_factory=dict)
    #: Handlers append non-fatal notes here; the dispatcher lifts them into the
    #: MCP envelope's ``warnings`` (总纲 §4.3.2 / V2.1 §19).
    warnings: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    def warn(self, message: str) -> None:
        """Append one envelope warning."""
        if message and message not in self.warnings:
            self.warnings.append(message)


# ---------------------------------------------------------------------------
# argument helpers
# ---------------------------------------------------------------------------
def client_id_of(arguments: Mapping[str, Any]) -> int | None:
    """``midas_clients.id`` from the caller's ``client_id`` (V2.1 §7.2 / §8.2)."""
    raw = arguments.get("client_id")
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def options_of(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """The ``options`` object, always a dict."""
    raw = arguments.get("options")
    return dict(raw) if isinstance(raw, Mapping) else {}


def timeout_of(arguments: Mapping[str, Any], *, default: int = 60) -> int:
    """Effective adapter timeout: ``options.timeout_seconds`` wins (§18.4).

    Clamped to 1–86400, the range V2.1 §9.2 declares for the schema field.
    """
    options = options_of(arguments)
    raw = options.get("timeout_seconds")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = int(default)
    return max(1, min(value, 86400))


def as_dict(value: Any) -> dict[str, Any]:
    """``value`` as a plain dict (``{}`` for anything else)."""
    return dict(value) if isinstance(value, Mapping) else {}


# ---------------------------------------------------------------------------
# adapter access
# ---------------------------------------------------------------------------
def require_adapter(context: DispatchContext) -> MidasAdapter:
    """The context's adapter, or ``ADAPTER_NOT_FOUND`` (总纲 §4.4.4).

    ``None`` only happens for platform-owned capabilities, so a handler that
    reaches for the adapter on one of those is a routing bug worth reporting as
    ``CAPABILITY_NOT_SUPPORTED`` rather than as a crash.
    """
    if context.adapter is None:
        raise AdapterError(
            ErrorCode.CAPABILITY_NOT_SUPPORTED,
            f"capability {context.capability.code!r} 不经过任何 Adapter"
            "（对接规范 §2.5.1：MIDAS 没有任务端点，midas_task 由平台 Task Engine 承担）。",
            details={"capability": context.capability.code},
        )
    return context.adapter


def adapter_method(adapter: MidasAdapter, name: str) -> Any:
    """Fetch a **concrete** adapter helper that V2.1 §13's Protocol omits.

    §13 declares ``query`` / ``model`` / ``execute`` only, but 对接规范 §3.5
    第 1 条 and §11.5.6 make two helpers mandatory on any real adapter:
    ``delete()`` (per-id ``DELETE {endpoint}/{id}``) and ``get_table()``
    (shape-matched ``POST /post/TABLE``).  Both shipped adapters provide them, so
    this returns the bound method — and reports a clean
    ``CAPABILITY_NOT_SUPPORTED`` when an adapter genuinely cannot serve it,
    instead of an ``AttributeError``.
    """
    method = getattr(adapter, name, None)
    if not callable(method):
        raise AdapterError(
            ErrorCode.CAPABILITY_NOT_SUPPORTED,
            f"adapter {getattr(adapter, 'code', '?')!r} 未实现 {name}()；"
            "V2.1 §13 的 Protocol 未声明该方法，但对接规范 §3.5 第 1 条 / §11.5.6 "
            "要求每个真实适配器提供它。",
            details={"adapter": getattr(adapter, "code", None), "method": name},
        )
    return method
