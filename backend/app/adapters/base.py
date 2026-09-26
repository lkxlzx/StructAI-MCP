"""Adapter base types — V2.1 §13 (Protocol), §14 (lifecycle), §15 (metadata),
§18 (request models), §19 (result model).

Only the *shapes* live here; behaviour belongs to a concrete adapter
(``midas_gen/adapter.py``, ``mock/adapter.py``).

Every type below is transcribed from V2.1 so that the framework, the registry
and the tests all agree on one vocabulary.  Deviations are called out inline
with the reason, because V2.1 §18.2 and §13 contain two constructs that cannot
be compiled literally — see :class:`AdapterRequest` and :class:`Capability`.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Final, Protocol, runtime_checkable

from app.adapters.errors import AdapterError
from app.core.constants import AdapterStatus, MidasClientStatus, TaskStatus
from app.core.errors import ErrorCode
from app.core.midas_config import MidasConnection

__all__ = [
    "AdapterLifecycle",
    "LIFECYCLE_DB_STATUS",
    "LIFECYCLE_TRANSITIONS",
    "can_transition",
    "AdapterMetadata",
    "AdapterRequest",
    "QueryRequest",
    "ModelRequest",
    "ExecuteRequest",
    "AdapterResult",
    "Capability",
    "MidasAdapter",
    "MidasClientConfig",
]

#: V2.1 §13 annotates ``connect(self, client: "MidasClientConfig")`` but the
#: document **never defines** ``MidasClientConfig``.  The concrete connection
#: model that exists in this codebase is
#: :class:`app.core.midas_config.MidasConnection`, so the two names are aliased
#: rather than inventing a second model (总纲 §0.4 唯一真源原则).
MidasClientConfig = MidasConnection


# ---------------------------------------------------------------------------
# V2.1 §14 — Adapter 生命周期
# ---------------------------------------------------------------------------
class AdapterLifecycle(str, Enum):
    """In-process state machine of one adapter instance (V2.1 §14).

    These states are **not** persisted; only the two DB status columns in
    :data:`LIFECYCLE_DB_STATUS` are (V2.1 §14 末段).
    """

    REGISTERED = "registered"
    INITIALIZING = "initializing"
    READY = "ready"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    BUSY = "busy"
    DISCONNECTING = "disconnecting"
    ERROR = "error"
    RECONNECTING = "reconnecting"


#: V2.1 §14 mapping table: ``(adapters.status, midas_clients.status)``.
#:
#: **``REGISTERED`` / ``INITIALIZING`` map to ``enabled``, not ``disabled``.**
#: 总纲 §4.2.5 defines ``adapters.status`` as ``enabled / disabled / error`` —
#: an **administrative** flag meaning "an operator turned this adapter off".
#: ``REGISTERED`` is a *lifecycle stage* ("constructed, not yet initialised"),
#: which is a different axis entirely.  Conflating them made a freshly
#: constructed adapter report ``disabled``, so the Capability Resolver refused
#: every call with ``ADAPTER_UNAVAILABLE`` until something explicitly drove it
#: to ``READY`` — i.e. the whole MCP layer was dead on startup.
#: (It hid well: the mock adapter starts at ``READY``, so only the live tests,
#: which build the real adapter, could expose it.)
#: Nothing in the lifecycle maps to ``disabled`` — that value now comes only
#: from an operator setting ``adapters.enabled = 0``.
LIFECYCLE_DB_STATUS: Final[dict[AdapterLifecycle, tuple[str, str]]] = {
    AdapterLifecycle.REGISTERED: (AdapterStatus.ENABLED.value, MidasClientStatus.DISCONNECTED.value),
    AdapterLifecycle.INITIALIZING: (AdapterStatus.ENABLED.value, MidasClientStatus.DISCONNECTED.value),
    AdapterLifecycle.READY: (AdapterStatus.ENABLED.value, MidasClientStatus.DISCONNECTED.value),
    AdapterLifecycle.CONNECTING: (AdapterStatus.ENABLED.value, MidasClientStatus.CONNECTING.value),
    AdapterLifecycle.CONNECTED: (AdapterStatus.ENABLED.value, MidasClientStatus.CONNECTED.value),
    AdapterLifecycle.BUSY: (AdapterStatus.ENABLED.value, MidasClientStatus.CONNECTED.value),
    AdapterLifecycle.DISCONNECTING: (AdapterStatus.ENABLED.value, MidasClientStatus.DISCONNECTED.value),
    AdapterLifecycle.ERROR: (AdapterStatus.ERROR.value, MidasClientStatus.ERROR.value),
    AdapterLifecycle.RECONNECTING: (AdapterStatus.ERROR.value, MidasClientStatus.ERROR.value),
}

#: Legal transitions, transcribed from the two §14 diagrams.
LIFECYCLE_TRANSITIONS: Final[dict[AdapterLifecycle, frozenset[AdapterLifecycle]]] = {
    AdapterLifecycle.REGISTERED: frozenset({AdapterLifecycle.INITIALIZING}),
    AdapterLifecycle.INITIALIZING: frozenset({AdapterLifecycle.READY, AdapterLifecycle.ERROR}),
    AdapterLifecycle.READY: frozenset({AdapterLifecycle.CONNECTING}),
    AdapterLifecycle.CONNECTING: frozenset(
        {AdapterLifecycle.CONNECTED, AdapterLifecycle.ERROR}
    ),
    AdapterLifecycle.CONNECTED: frozenset(
        {
            AdapterLifecycle.BUSY,
            AdapterLifecycle.DISCONNECTING,
            AdapterLifecycle.ERROR,
        }
    ),
    AdapterLifecycle.BUSY: frozenset(
        {AdapterLifecycle.CONNECTED, AdapterLifecycle.ERROR}
    ),
    AdapterLifecycle.DISCONNECTING: frozenset({AdapterLifecycle.READY}),
    AdapterLifecycle.ERROR: frozenset({AdapterLifecycle.RECONNECTING}),
    AdapterLifecycle.RECONNECTING: frozenset(
        {AdapterLifecycle.CONNECTED, AdapterLifecycle.ERROR}
    ),
}


def can_transition(current: AdapterLifecycle, target: AdapterLifecycle) -> bool:
    """True when ``current -> target`` is one of the §14 transitions."""
    return target in LIFECYCLE_TRANSITIONS.get(current, frozenset())


# ---------------------------------------------------------------------------
# V2.1 §15 — Adapter 元数据
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AdapterMetadata:
    """Exactly the ten fields of V2.1 §15 (nine + ``capabilities``)."""

    code: str
    name: str
    software: str
    version_range: str
    protocol: str

    supports_query: bool
    supports_model: bool
    supports_execute: bool
    supports_async_task: bool

    capabilities: list[str]

    def to_db_payload(self) -> dict[str, Any]:
        """Lossless mapping onto ``adapters`` (V2.1 §15 落库映射).

        ``supports_*`` land inside ``capabilities_json`` as boolean bits, and
        ``implementation`` / ``status`` are owned by the caller (§15).
        """
        return {
            "code": self.code,
            "name": self.name,
            "software": self.software,
            "version_range": self.version_range,
            "protocol": self.protocol,
            "capabilities": list(self.capabilities),
            "supports_query": self.supports_query,
            "supports_model": self.supports_model,
            "supports_execute": self.supports_execute,
            "supports_async_task": self.supports_async_task,
        }


# ---------------------------------------------------------------------------
# V2.1 §18 — Adapter 请求模型
# ---------------------------------------------------------------------------
@dataclass(kw_only=True)
class AdapterRequest:
    """V2.1 §18.1 base request (V2.0 原样保留).

    .. note::
       ``kw_only=True`` is a **compile-time necessity**, not a style choice.
       §18.2 re-declares ``options`` **with** a default
       (``field(default_factory=dict)``) in :class:`ModelRequest` while
       ``timeout_seconds`` follows it **without** one; a literal transcription
       raises ``TypeError: non-default argument 'timeout_seconds' follows
       default argument`` at import time.  Making every field keyword-only
       removes the ordering rule entirely, and §18.5's three construction
       examples already pass every field by keyword.
    """

    #: ``req_`` tracking id of the MCP call (总纲 §4.1.3 / §18.4).
    request_id: str
    #: ``midas_clients.id`` (INTEGER, 裁决 N-6).
    client_id: int
    action: str
    resource: str | None
    #: Raw, un-normalized payload; the subclass fields are its parsed form (§18.4).
    payload: dict[str, Any] | list[Any] | None
    options: dict[str, Any]
    #: Adapter-level timeout, from ``tool_interfaces.timeout_seconds`` or the
    #: caller's ``options`` (§18.4).
    timeout_seconds: int


@dataclass(kw_only=True)
class QueryRequest(AdapterRequest):
    """V2.1 §18.2 — ``midas_query`` request."""

    #: ``midas_query.target`` (server / client / capabilities / node / ...).
    target: str
    #: Overrides the base ``action``: get / list / search / count / inspect.
    action: str
    #: Filter already validated by §7.2 ``oneOf``.
    query: dict[str, Any] | None = None
    page: int = 1
    page_size: int = 100


@dataclass(kw_only=True)
class ModelRequest(AdapterRequest):
    """V2.1 §18.2 — ``midas_model`` request."""

    #: MCP singular resource name (§17.2).
    resource: str
    #: create / read / update / delete / upsert / validate.
    action: str
    #: Payload already validated by §8.2 ``oneOf``.
    data: dict[str, Any] | list[Any] | None = None
    #: validate_before_write / validate_after_write / transactional / dry_run.
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(kw_only=True)
class ExecuteRequest(AdapterRequest):
    """V2.1 §18.2 — ``midas_execute`` request."""

    #: connect / import / export / calculate / analysis / ...
    action: str
    resource: str | None = None
    #: Payload already validated against the capability schema (§9.3).
    data: dict[str, Any] | None = None
    #: async / wait / timeout_seconds / dry_run / force.
    options: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# V2.1 §19 — Adapter 返回模型
# ---------------------------------------------------------------------------
@dataclass
class AdapterResult:
    """Exactly the ten fields of V2.1 §19.

    ``status`` values come from the ``tasks.status`` word list (总纲 §4.2.1) and
    ``error_code`` from the 总纲 §4.4 registry — neither may be extended here.
    ``raw_status`` / ``raw_response`` are for logs and troubleshooting only and
    must never be returned to the LLM (§19 字段约束).
    """

    success: bool
    status: str

    data: Any = None

    task_id: str | None = None

    error_code: str | None = None
    error_message: str | None = None

    warnings: list[str] = field(default_factory=list)

    raw_status: int | None = None
    raw_response: Any = None

    latency_ms: int | None = None

    # ------------------------------------------------------------------ #
    @classmethod
    def ok(
        cls,
        data: Any = None,
        *,
        status: str = TaskStatus.SUCCESS.value,
        warnings: list[str] | None = None,
        raw_status: int | None = None,
        raw_response: Any = None,
        latency_ms: int | None = None,
        task_id: str | None = None,
    ) -> "AdapterResult":
        """Build a successful result."""
        return cls(
            success=True,
            status=status,
            data=data,
            task_id=task_id,
            warnings=list(warnings or []),
            raw_status=raw_status,
            raw_response=raw_response,
            latency_ms=latency_ms,
        )

    @classmethod
    def failed(
        cls,
        code: ErrorCode | str,
        message: str = "",
        *,
        details: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
        raw_status: int | None = None,
        raw_response: Any = None,
        latency_ms: int | None = None,
        status: str = TaskStatus.FAILED.value,
    ) -> "AdapterResult":
        """Build a failed result carrying a 总纲 §4.4 code."""
        error = AdapterError(code, message, details, raw_status, raw_response)
        return cls(
            success=False,
            status=status,
            error_code=error.code,
            error_message=error.message,
            warnings=list(warnings or []),
            raw_status=raw_status,
            raw_response=raw_response,
            latency_ms=latency_ms,
        )

    @classmethod
    def from_error(
        cls,
        error: AdapterError,
        *,
        warnings: list[str] | None = None,
        latency_ms: int | None = None,
    ) -> "AdapterResult":
        """Build a failed result from an :class:`AdapterError`."""
        return cls(
            success=False,
            status=TaskStatus.FAILED.value,
            error_code=error.code,
            error_message=error.message,
            warnings=list(warnings or []),
            raw_status=error.raw_status,
            raw_response=error.raw_response,
            latency_ms=latency_ms,
        )

    def to_dict(self) -> dict[str, Any]:
        """Full result for logs (includes the raw upstream payload)."""
        return {
            "success": self.success,
            "status": self.status,
            "data": self.data,
            "task_id": self.task_id,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "warnings": list(self.warnings),
            "raw_status": self.raw_status,
            "raw_response": self.raw_response,
            "latency_ms": self.latency_ms,
        }

    def to_llm_payload(self) -> dict[str, Any]:
        """Result minus ``raw_*`` — the only form safe for the LLM (§19)."""
        return {
            "success": self.success,
            "status": self.status,
            "data": self.data,
            "task_id": self.task_id,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "warnings": list(self.warnings),
            "latency_ms": self.latency_ms,
        }


# ---------------------------------------------------------------------------
# Capability — V2.1 §16.1 / §17 (never defined in V2.1)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Capability:
    """Minimal stand-in for the ``Capability`` type V2.1 §13 references.

    V2.1 §13 declares ``async def capabilities(self) -> list["Capability"]`` but
    **never defines** ``Capability``; §16.1 places the authoritative rows in the
    ``capabilities`` table.  This dataclass therefore mirrors that table's
    identifying columns only (``adapter_code`` / ``capability_code`` /
    ``resource`` / ``action``) plus the interface linkage of §17.1, so the
    Protocol is resolvable without inventing a second source of truth.
    """

    code: str
    resource: str
    action: str
    interface_code: str | None = None
    request_wrapper: str | None = None
    response_root_key: str | None = None


# ---------------------------------------------------------------------------
# V2.1 §13 — Adapter Protocol
# ---------------------------------------------------------------------------
@runtime_checkable
class MidasAdapter(Protocol):
    """The full V2.1 §13 Protocol **plus** the four §13 additions.

    §13 additions (依据对接规范 §7.3): ``metadata()`` / ``introspect()`` /
    ``wrap()`` / ``unwrap()``.

    .. note::
       ``runtime_checkable`` only verifies **attribute presence**; it cannot
       check signatures.  Use it for smoke checks, not for conformance proofs.
    """

    @property
    def code(self) -> str:
        """``adapters.code`` (e.g. ``midas_gen``)."""
        ...

    @property
    def software(self) -> str:
        """``adapters.software`` (e.g. ``MIDAS Gen``)."""
        ...

    @property
    def version(self) -> str:
        """Reported upstream version (``"unknown"`` when the API exposes none)."""
        ...

    async def metadata(self) -> AdapterMetadata:
        """Return §15 metadata.  **Pure local call — no network I/O** (§13)."""
        ...

    async def connect(self, client: MidasClientConfig) -> AdapterResult:
        """Validate the MAPI-Key and confirm the product is running (§8)."""
        ...

    async def disconnect(self) -> AdapterResult:
        """Release the connection and return to ``READY`` (§14)."""
        ...

    async def health_check(self) -> AdapterResult:
        """``GET /mapikey/verify`` — **host root**, no product segment (§2.2).

        Cannot detect a modal-dialog-blocked session (§2.5.2); pair it with
        ``probe_alive()`` (§2.5.4 item 2 / V2.1 §13).
        """
        ...

    async def introspect(self, resource: str) -> AdapterResult:
        """``GET /info/db/<RES>``; only ``/db/*`` is introspectable (§5.1)."""
        ...

    async def capabilities(self) -> list[Capability]:
        """Declared capabilities (authoritative rows live in the DB, §16.1)."""
        ...

    async def query(self, request: QueryRequest) -> AdapterResult:
        """``midas_query`` entry point."""
        ...

    async def model(self, request: ModelRequest) -> AdapterResult:
        """``midas_model`` entry point."""
        ...

    async def execute(self, request: ExecuteRequest) -> AdapterResult:
        """``midas_execute`` entry point."""
        ...

    async def get_task(self, task_id: str) -> AdapterResult:
        """Async task lookup."""
        ...

    async def cancel_task(self, task_id: str) -> AdapterResult:
        """Async task cancellation."""
        ...

    async def retry_task(self, task_id: str) -> AdapterResult:
        """Async task retry."""
        ...

    def wrap(self, payload: Any, wrapper: str | None) -> dict[str, Any]:
        """``request_wrapper`` -> ``{"Assign": ...}`` / ``{"Argument": ...}`` (§17.3)."""
        ...

    def unwrap(self, response: Any, root_key: str | None) -> Any:
        """``response_root_key`` -> inner object, shape-matched (§17.3)."""
        ...
