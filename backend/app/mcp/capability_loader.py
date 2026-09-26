"""Database-driven capability loader — the Phase 2 bridge of V2.1 §16.1.

Authoritative sources
---------------------
* 《StructAI MCP V2.1 设计框架规范》(**V2.1**) §16.1 (解析表结构: ``capabilities``
  + ``capability_interfaces`` + ``tool_interfaces`` + ``tools``),
  §16.2 (解析失败一律 ``CAPABILITY_NOT_SUPPORTED``，禁止回退直连端点),
  §17.3 (``metadata_json`` 承载 ``outer_key_means``), §17.4 (``interface_code``),
  §6.2 / §9.3 (第二次校验用的 payload schema).
* 《StructAI 架构边界与融合规范 v1.0 总纲》(**总纲**) §0.4 (唯一真源),
  §4.2.12 (``capabilities.tool_id`` —— 工具是**能力自身**的属性),
  §4.4 (错误码封闭集合：本模块**不新增**任何错误码),
  §4.6.1 (MCP 单数资源名), §4.8.2 (权限码封闭集合).
* 《MIDAS NX Open API 对接规范 v1.0》(**对接规范**) §2.5.1 (MIDAS 没有任务
  API —— 7 个 ``midas_task`` 能力是 platform-owned), §3.3 (新文件必需数据),
  §3.5 第 1 条 (DELETE 逐 id), §4.1 (``Assign`` 外层键语义), §5 (``/info``
  自省), §11.5.6 (``/post/TABLE``), §11.5.7 (``/doc/ANAL``).

Why this module exists, and why it is separate
----------------------------------------------
:mod:`app.mcp.capabilities` declares the capability table **in code** and its own
docstring states the seam: 「Phase 2 loads the same rows from the ``capabilities``
/ ``tool_interfaces`` tables and :func:`register_capability` replaces them row by
row.」 This module *is* that seam — the bridge from the database to the in-memory
table.

``capabilities.py`` is deliberately dependency-free: the dispatcher, all four
tool modules and every offline test import it, so it must not drag in the ORM.
This loader is therefore the **only** place that knows both shapes:

* the ORM shape — ``tools`` / ``tool_interfaces`` / ``capabilities`` /
  ``capability_interfaces`` (:mod:`app.models.registry`), and
* the routing shape — :class:`app.mcp.capabilities.Capability`.

Field mapping (capabilities + tool_interfaces + tools -> one ``Capability``)
---------------------------------------------------------------------------
========================  ==============================================================
``Capability`` field      source
========================  ==============================================================
``code``                  ``capabilities.capability_code``
``tool``                  ``tools.name`` via ``capabilities.tool_id`` (总纲 §4.2.12 —
                          it **cannot** come from the interface: the ``/post/TABLE``
                          POST is shared by ``midas_execute`` and ``midas_query``,
                          and platform-owned rows have no interface at all)
``resource``              ``capabilities.resource``
``action``                ``capabilities.action``
``adapter_code``          ``capabilities.adapter_code`` (**nullable** — the 7
                          platform-owned ``midas_task`` rows have none)
``method``                ``tool_interfaces.method`` (via
``endpoint``              ``tool_interfaces.endpoint`` (via
``request_wrapper``       ``tool_interfaces.request_wrapper`` (via
``response_root_key``     ``tool_interfaces.response_root_key`` (via
``interface_code``        ``tool_interfaces.interface_code`` (via
                          ``capabilities.interface_id``); falls back to ``code``
                          when there is no interface row — the rule of
                          ``Capability.__post_init__`` (V2.1 §17.4)
``request_schema``        ``tool_interfaces.request_schema_json``, JSON-parsed;
                          ``{}`` when NULL/unparseable (V2.1 §6.2 / §9.3)
``product_scope``         ``tool_interfaces.product_scope``; default ``unknown``
``domain`` / ``feature``  ``tool_interfaces.domain`` / ``.feature``
``outer_key_means``       ``tool_interfaces.metadata_json.outer_key_means``; when
``outer_key_kind``        absent, **derived** from the endpoint via
                          :func:`app.mcp.capabilities.outer_key_means_for` /
                          ``outer_key_kind_for`` (总纲 §0.4, 对接规范 §4.1)
``dispatch``              **no column** — derived from ``(tool, resource, action,
                          endpoint)`` by :func:`derive_dispatch`; the
                          ``constraints_json.dispatch`` / ``metadata_json.dispatch``
                          keys override it
``adapter_action``        **no column** — JSON extension key, see below
``task_type``             **no column** — JSON extension key, see below
``notes``                 ``capabilities.description`` — the DDL's own free-text
                          capability description, and 总纲 §4.2.13's documented home
                          for the **Chinese annotation** an annotated
                          ``tool_interfaces`` row carries (the loader copies it
                          verbatim; it never composes one); JSON override keys win
========================  ==============================================================

The interface lookup
--------------------
``capabilities.interface_id`` is the **primary** interface (V2.1 §16.1). When it
is NULL the loader falls back to the ``capability_interfaces`` link (裁决 B-3) and
uses that capability's **lowest** ``interface_id`` — the same rule the link table
exists for: one capability may need several endpoints, one endpoint may serve
several capabilities. A dangling ``interface_id`` (no such row) is a warning, not
a crash: the loader then tries the link, and finally falls back to ``code``.

The dispatch rule table (reviewable in one place)
-------------------------------------------------
``dispatch`` is not a column and :func:`register_capability` **validates** it
against :data:`app.mcp.capabilities.DISPATCH_HINTS` and raises ``VALIDATION_ERROR``
otherwise, so it has to be *derived* rather than copied. The rules below are
applied in order and the first match wins; ``None`` means 「cannot be derived」 and
the row is **skipped and counted**, never guessed:

==  ===========================================================  ==============================
#   condition                                                    dispatch
==  ===========================================================  ==============================
0   ``constraints_json.dispatch`` (capability level) or          that value, when it is a
    ``metadata_json.dispatch`` (interface level) present and     member of ``DISPATCH_HINTS``
    valid                                                        (an invalid one is counted,
                                                                 and the rules below run)
1   ``tool == midas_task``                                       ``task``
2   ``midas_query`` and ``resource == capabilities``             ``local_capabilities``
3   ``midas_query`` and ``resource == model``                    ``model_overview``
4   ``endpoint`` is the ``/info`` family (对接规范 §5)            ``introspect``
5   ``endpoint == /post/TABLE`` (对接规范 §11.5.6)                ``get_table``
6   ``tool == midas_query``                                      ``query``
7   ``midas_model`` and ``action == delete``                     ``delete``
8   ``tool == midas_model``                                      ``model``
9   ``midas_execute`` and ``(resource, action)`` in              ``EXECUTE_DISPATCH_TABLE``'s
    :data:`EXECUTE_DISPATCH_TABLE`                               value for that pair
10  otherwise                                                    ``None`` -> skipped + counted
==  ===========================================================  ==============================

Rules 2/3 come **before** rules 4/5 on purpose: ``midas_query``'s ``server`` /
``client`` / ``capabilities`` / ``model`` targets are platform-side and never
reach MIDAS, so a stray endpoint on such a row must not reclassify it as a
network call. Rule 4 precedes rule 6 because ``/info/db/<RES>`` is the §5
introspection family, not a ``/db/*`` table read.

Why ``midas_execute`` is table-driven (rule 9) rather than endpoint-driven: its
dispatch genuinely is **not** a function of the endpoint. ``/post/TABLE`` serves
``result.export`` (``get_table``), ``/doc/ANAL`` serves ``model.calculate``
(``execute``), and ``model.sync`` / ``model.validate_model`` / ``command.command``
have no endpoint at all. A new ``midas_execute`` action therefore needs one line in
:data:`EXECUTE_DISPATCH_TABLE` (or a ``dispatch`` override in the JSON blob) —
until then the loader skips it and **reports the count** instead of inventing a
value.

The two JSON extension blobs
----------------------------
Four ``Capability`` fields have no dedicated column (``dispatch``,
``adapter_action``, ``task_type``, ``notes``), and two more accept an override
(``request_schema``, and the outer-key vocabulary). Their homes, in precedence
order, are the two JSON columns the registry already carries:

=========================  ==================================================
key                        home
=========================  ==================================================
``dispatch``               ``capabilities.constraints_json`` ->
                           ``tool_interfaces.metadata_json`` ->
                           :func:`derive_dispatch`
``adapter_action``         ``constraints_json`` -> ``metadata_json``
``task_type``              ``constraints_json`` -> ``metadata_json``
``notes``                  ``constraints_json`` ->
                           ``capabilities.description`` ->
                           ``metadata_json`` -> ``""``
``request_schema``         ``constraints_json`` -> ``request_schema_json``
``outer_key_means``        ``metadata_json`` -> derived from the endpoint
``outer_key_kind``         ``metadata_json`` -> derived from the endpoint
=========================  ==================================================

``metadata_json.outer_key_means`` is the key V2.1 §17.3 names (and
``app.adapters.midas_gen.adapter`` already documents as the correction channel for
its unverified default), so interface-level semantics stay there.
``capabilities.constraints_json`` is the **only** capability-level JSON column, so
the capability-level keys live there; keys this loader does not recognise are
ignored, which is what keeps the real constraints (V2.1 §16.3) safe.

Behaviour contract
------------------
* :func:`load_capabilities` is the ``async`` entry point (the MCP layer runs on the
  event loop); :func:`load_capabilities_now` is its blocking mirror. Both follow
  :mod:`app.services.task_store`: the session layer is **synchronous**, so the
  blocking work is handed to :func:`asyncio.to_thread` and the ``Session`` is
  opened **inside** the worker thread (a ``Session`` is not thread-safe and is
  never shared between calls). Nothing ORM-bound escapes the session.
* **Never raises for a single bad row.** Every row is built inside a ``try``; a
  failure is counted under a skip reason and the loop continues. Only a failure of
  the *query itself* (no connection, missing table) propagates — that is an
  infrastructure fault, not a bad row, and silently keeping the static table would
  hide it.
* **Idempotent.** ``replace=True`` (the default) makes a second load an in-place
  replacement, never a duplicate and never a ``RESOURCE_CONFLICT``.
* **Counted, not silent.** :class:`LoadResult` reports rows read, loaded, added,
  replaced, skipped, per-reason skip counts and warnings. A loader that silently
  drops rows is how the ``requested_by`` gap happened.
* **Upsert, never prune.** A row the database does not contain keeps its static
  declaration, which is exactly the fallback
  :func:`app.mcp.capabilities.reset_capabilities` documents. The loader therefore
  cannot lose the offline table by accident.
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.errors import AdapterError
from app.db.base import session_scope_for
from app.mcp.capabilities import (
    DISPATCH_DELETE,
    DISPATCH_EXECUTE,
    DISPATCH_GET_TABLE,
    DISPATCH_HINTS,
    DISPATCH_INTROSPECT,
    DISPATCH_LOCAL_CAPABILITIES,
    DISPATCH_MODEL,
    DISPATCH_MODEL_OVERVIEW,
    DISPATCH_MODEL_SYNC,
    DISPATCH_NOT_IMPLEMENTED,
    DISPATCH_QUERY,
    DISPATCH_TASK,
    TOOL_EXECUTE,
    TOOL_MODEL,
    TOOL_NAMES,
    TOOL_QUERY,
    TOOL_TASK,
    Capability,
    capability_rows,
    outer_key_kind_for,
    outer_key_means_for,
    register_capability,
)
from app.models.registry import (
    Capability as CapabilityRow,
    CapabilityInterface as CapabilityInterfaceRow,
    Tool as ToolRow,
    ToolInterface as ToolInterfaceRow,
)

__all__ = [
    # entry points
    "LoadResult",
    "load_capabilities",
    "load_capabilities_now",
    "default_session_factory",
    # the reviewable derivation
    "derive_dispatch",
    "EXECUTE_DISPATCH_TABLE",
    "QUERY_RESOURCE_DISPATCH",
    # the closed vocabularies of the report
    "SKIP_REASONS",
    "WARNING_REASONS",
    "SKIP_CAPABILITY_DISABLED",
    "SKIP_INTERFACE_DISABLED",
    "SKIP_TOOL_ROW_MISSING",
    "SKIP_UNKNOWN_TOOL",
    "SKIP_UNDERIVABLE_DISPATCH",
    "SKIP_MISSING_REQUIRED_FIELD",
    "SKIP_DUPLICATE_SLOT",
    "SKIP_REGISTRATION_REJECTED",
    "SKIP_MALFORMED_ROW",
    "WARN_INVALID_REQUEST_SCHEMA",
    "WARN_NON_OBJECT_REQUEST_SCHEMA",
    "WARN_INVALID_METADATA_JSON",
    "WARN_INVALID_CONSTRAINTS_JSON",
    "WARN_INVALID_DISPATCH_OVERRIDE",
    "WARN_INTERFACE_ROW_MISSING",
    "WARN_OUTER_KEY_DERIVATION_FAILED",
]


# ---------------------------------------------------------------------------
# Skip reasons — why a row did **not** reach the in-memory table
# ---------------------------------------------------------------------------
#: ``capabilities.enabled = 0`` (V2.1 §16.1).
SKIP_CAPABILITY_DISABLED: Final[str] = "capability_disabled"
#: The row's ``tool_interfaces.enabled = 0``: the endpoint is switched off, so the
#: capability cannot be served. Fail closed — do not expose it.
SKIP_INTERFACE_DISABLED: Final[str] = "interface_disabled"
#: ``capabilities.tool_id`` points at no ``tools`` row (a dangling FK — the loader
#: joins with ``LEFT OUTER JOIN`` precisely so this is *counted* rather than
#: silently dropped from the result set).
SKIP_TOOL_ROW_MISSING: Final[str] = "tool_row_missing"
#: ``tools.name`` is not one of the four MCP tools (v1.2 §37).
SKIP_UNKNOWN_TOOL: Final[str] = "unknown_tool"
#: No rule of the dispatch table matched and no valid override was present.
SKIP_UNDERIVABLE_DISPATCH: Final[str] = "underivable_dispatch"
#: Empty ``capability_code`` / ``resource`` / ``action`` (NOT NULL in the DDL, but
#: an empty string is not a usable key).
SKIP_MISSING_REQUIRED_FIELD: Final[str] = "missing_required_field"
#: The same ``(adapter_code, capability_code)`` twice in one load. ``ux_capability``
#: forbids it in a real database; the first row (lowest ``id``) wins.
SKIP_DUPLICATE_SLOT: Final[str] = "duplicate_slot"
#: ``register_capability`` refused the row (for example ``replace=False`` against a
#: slot that is already taken). Counted instead of raised.
SKIP_REGISTRATION_REJECTED: Final[str] = "registration_rejected"
#: Any other exception while building one row — counted, never raised.
SKIP_MALFORMED_ROW: Final[str] = "malformed_row"

#: Closed vocabulary of :attr:`LoadResult.skip_reasons`.
SKIP_REASONS: Final[frozenset[str]] = frozenset(
    {
        SKIP_CAPABILITY_DISABLED,
        SKIP_INTERFACE_DISABLED,
        SKIP_TOOL_ROW_MISSING,
        SKIP_UNKNOWN_TOOL,
        SKIP_UNDERIVABLE_DISPATCH,
        SKIP_MISSING_REQUIRED_FIELD,
        SKIP_DUPLICATE_SLOT,
        SKIP_REGISTRATION_REJECTED,
        SKIP_MALFORMED_ROW,
    }
)


# ---------------------------------------------------------------------------
# Warnings — the row **did** load, but something was degraded or ignored
# ---------------------------------------------------------------------------
#: ``tool_interfaces.request_schema_json`` is not parseable JSON, or not a JSON
#: object. The row loads with ``request_schema = {}`` (V2.1 §6.2).
WARN_INVALID_REQUEST_SCHEMA: Final[str] = "invalid_request_schema_json"
#: ``constraints_json.request_schema`` exists but is neither an object nor a JSON
#: object string; the interface-level schema is used instead.
WARN_NON_OBJECT_REQUEST_SCHEMA: Final[str] = "non_object_request_schema"
#: ``tool_interfaces.metadata_json`` is not parseable JSON / not an object.
WARN_INVALID_METADATA_JSON: Final[str] = "invalid_metadata_json"
#: ``capabilities.constraints_json`` is not parseable JSON / not an object.
WARN_INVALID_CONSTRAINTS_JSON: Final[str] = "invalid_constraints_json"
#: A ``dispatch`` override key is present but outside ``DISPATCH_HINTS``; the
#: derivation ran instead (总纲 §4.4: no new error code, so this is a counter).
WARN_INVALID_DISPATCH_OVERRIDE: Final[str] = "invalid_dispatch_override"
#: ``capabilities.interface_id`` points at no ``tool_interfaces`` row.
WARN_INTERFACE_ROW_MISSING: Final[str] = "interface_row_missing"
#: The adapter refused to derive the outer-key vocabulary for this endpoint; the
#: dataclass default (``"self"``) is used.
WARN_OUTER_KEY_DERIVATION_FAILED: Final[str] = "outer_key_derivation_failed"

#: Closed vocabulary of :attr:`LoadResult.warnings`.
WARNING_REASONS: Final[frozenset[str]] = frozenset(
    {
        WARN_INVALID_REQUEST_SCHEMA,
        WARN_NON_OBJECT_REQUEST_SCHEMA,
        WARN_INVALID_METADATA_JSON,
        WARN_INVALID_CONSTRAINTS_JSON,
        WARN_INVALID_DISPATCH_OVERRIDE,
        WARN_INTERFACE_ROW_MISSING,
        WARN_OUTER_KEY_DERIVATION_FAILED,
    }
)


# ---------------------------------------------------------------------------
# JSON extension keys (see the module docstring for the precedence table)
# ---------------------------------------------------------------------------
_KEY_DISPATCH: Final[str] = "dispatch"
_KEY_ADAPTER_ACTION: Final[str] = "adapter_action"
_KEY_TASK_TYPE: Final[str] = "task_type"
_KEY_NOTES: Final[str] = "notes"
_KEY_REQUEST_SCHEMA: Final[str] = "request_schema"
_KEY_OUTER_KEY_MEANS: Final[str] = "outer_key_means"
_KEY_OUTER_KEY_KIND: Final[str] = "outer_key_kind"


# ---------------------------------------------------------------------------
# The dispatch rule table (rules 2, 3 and 9 of the docstring's table)
# ---------------------------------------------------------------------------
#: ``midas_query`` resources that never touch MIDAS (裁决 C-7 / V2.1 §16). Every
#: other ``midas_query`` resource is a MIDAS read (rule 6).
QUERY_RESOURCE_DISPATCH: Final[dict[str, str]] = {
    "capabilities": DISPATCH_LOCAL_CAPABILITIES,
    "model": DISPATCH_MODEL_OVERVIEW,
}

#: ``midas_execute``'s ``(resource, action) -> dispatch`` classification — the
#: closed table of rule 9, transcribed from ``capabilities._EXECUTE_ROWS``. It is a
#: table rather than a rule because the dispatch of a ``midas_execute`` row is not
#: a function of its endpoint (see the module docstring).
EXECUTE_DISPATCH_TABLE: Final[dict[tuple[str, str], str]] = {
    ("server", "connect"): DISPATCH_EXECUTE,
    ("server", "disconnect"): DISPATCH_EXECUTE,
    ("project", "open_project"): DISPATCH_EXECUTE,
    ("project", "save_project"): DISPATCH_EXECUTE,
    ("project", "close_project"): DISPATCH_EXECUTE,
    ("file", "import"): DISPATCH_EXECUTE,
    ("file", "export"): DISPATCH_EXECUTE,
    ("model", "calculate"): DISPATCH_EXECUTE,
    ("analysis", "analysis"): DISPATCH_EXECUTE,
    # 对接规范 §11.5.6: /post/TABLE is reached through adapter.get_table().
    ("result", "export"): DISPATCH_GET_TABLE,
    # 对接规范 §2.5.1: MIDAS has no report endpoint — declared, not implemented.
    ("report", "generate_report"): DISPATCH_NOT_IMPLEMENTED,
    # 对接规范 §11.5.8: the only endpoint that validates a model is /doc/ANAL.
    ("model", "validate_model"): DISPATCH_NOT_IMPLEMENTED,
    # 对接规范 §3.5 第 5 条: read the model state back after a write timeout.
    ("model", "sync"): DISPATCH_MODEL_SYNC,
    ("command", "command"): DISPATCH_EXECUTE,
}

#: 对接规范 §5 — the introspection family (``GET /info/db/<RES>``).
_INFO_PREFIX: Final[str] = "/info"
#: 对接规范 §11.5.6 — the one URI that carries several logical tables.
_TABLE_ENDPOINT: Final[str] = "/post/table"
#: 对接规范 §4.1 — only ``/db/*`` endpoints carry an ``Assign`` body, so only they
#: have an outer-key vocabulary. ``/info/db/NODE`` is *not* one of them: it is the
#: §5 introspection family and must not inherit the write guard's kind.
_DB_PREFIX: Final[str] = "/db/"


def derive_dispatch(
    tool: str, resource: str, action: str, endpoint: str | None = None
) -> str | None:
    """Dispatch hint of one row, or ``None`` when it cannot be derived.

    Applies the rule table of the module docstring in order. ``None`` is a **real
    answer**: the row is then skipped and counted rather than given a guessed
    dispatch (总纲 §4.4 keeps the error-code set closed, so this module reports a
    count instead of inventing a code).
    """
    tool_name = (tool or "").strip()
    res = (resource or "").strip().lower()
    act = (action or "").strip().lower()
    path = (endpoint or "").strip().lower()

    if tool_name == TOOL_TASK:  # rule 1 — platform-owned (对接规范 §2.5.1)
        return DISPATCH_TASK
    if tool_name == TOOL_QUERY and res in QUERY_RESOURCE_DISPATCH:  # rules 2, 3
        return QUERY_RESOURCE_DISPATCH[res]
    if path == _INFO_PREFIX or path.startswith(_INFO_PREFIX + "/"):  # rule 4
        return DISPATCH_INTROSPECT
    if path.rstrip("/") == _TABLE_ENDPOINT:  # rule 5
        return DISPATCH_GET_TABLE
    if tool_name == TOOL_QUERY:  # rule 6
        return DISPATCH_QUERY
    if tool_name == TOOL_MODEL:  # rules 7, 8
        return DISPATCH_DELETE if act == "delete" else DISPATCH_MODEL
    if tool_name == TOOL_EXECUTE:  # rule 9
        return EXECUTE_DISPATCH_TABLE.get((res, act))
    return None  # rule 10


# ---------------------------------------------------------------------------
# The result
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LoadResult:
    """What one load did — the report that stops a silent drop.

    ``loaded == added + replaced``. The two counters are split because they answer
    different questions: ``added`` is 「the database introduced a slot」 and
    ``replaced`` is 「an existing slot (static declaration or a previous load) was
    overwritten」 — which is how a second, idempotent load is visible
    (``added == 0``).
    """

    #: Rows the ``capabilities`` table returned (enabled and disabled alike).
    rows_read: int = 0
    #: Rows successfully built **and** registered.
    loaded: int = 0
    #: Registered slots that held no row before this load.
    added: int = 0
    #: Registered slots that already held a row (static declaration or earlier load).
    replaced: int = 0
    #: ``rows_read - loaded``.
    skipped: int = 0
    #: ``skip reason -> count``; keys are drawn from :data:`SKIP_REASONS`.
    skip_reasons: dict[str, int] = field(default_factory=dict)
    #: ``warning reason -> count``; keys are drawn from :data:`WARNING_REASONS`.
    warnings: dict[str, int] = field(default_factory=dict)
    #: Adapter codes that actually contributed a row (``None`` == platform-owned).
    adapters: tuple[str | None, ...] = ()

    @property
    def ok(self) -> bool:
        """True when every row read reached the table and nothing was degraded."""
        return self.skipped == 0 and not self.warnings

    def to_payload(self) -> dict[str, Any]:
        """JSON-safe projection (counters sorted, so two runs compare byte for byte)."""
        return {
            "rows_read": self.rows_read,
            "loaded": self.loaded,
            "added": self.added,
            "replaced": self.replaced,
            "skipped": self.skipped,
            "skip_reasons": dict(sorted(self.skip_reasons.items())),
            "warnings": dict(sorted(self.warnings.items())),
            "adapters": list(self.adapters),
        }


class _Counters:
    """Mutable tallies for one load; never leaves this module."""

    def __init__(self) -> None:
        self.skipped: int = 0
        self.skip_reasons: dict[str, int] = {}
        self.warnings: dict[str, int] = {}

    def skip(self, reason: str) -> None:
        """Record one row that did not reach the table."""
        self.skipped += 1
        self.skip_reasons[reason] = self.skip_reasons.get(reason, 0) + 1

    def warn(self, reason: str) -> None:
        """Record one degradation that did not stop the row from loading."""
        self.warnings[reason] = self.warnings.get(reason, 0) + 1


# ---------------------------------------------------------------------------
# Row shapes — plain Python, so nothing ORM-bound escapes the session
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _Interface:
    """The ``tool_interfaces`` columns one ``Capability`` needs, already copied."""

    interface_code: str | None
    method: str | None
    endpoint: str | None
    request_wrapper: str | None
    response_root_key: str | None
    product_scope: str | None
    domain: str | None
    feature: str | None
    request_schema_json: str | None
    metadata_json: str | None
    enabled: int


@dataclass(frozen=True)
class _SourceRow:
    """One ``capabilities`` row joined to its tool and its interface(s)."""

    capability_id: int
    code: str | None
    adapter_code: str | None
    resource: str | None
    action: str | None
    enabled: int
    description: str | None
    constraints_json: str | None
    interface_id: int | None
    tool_name: str | None
    interface: _Interface | None
    linked_interface: _Interface | None


# ---------------------------------------------------------------------------
# small value helpers
# ---------------------------------------------------------------------------
def _text(value: Any) -> str | None:
    """Stripped string, or ``None`` when absent / blank / not a string.

    Returning ``None`` rather than ``""`` keeps the dataclass defaults meaningful:
    ``Capability.interface_code`` is filled from ``code`` by ``__post_init__`` when
    it is empty, and ``Capability.method`` must be ``None`` (not ``""``) when no
    MIDAS call is made.
    """
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _parse_object(raw: Any, counters: _Counters, warning: str) -> dict[str, Any]:
    """Parse a TEXT JSON column into a dict; ``{}`` (counted) when unusable.

    NULL and a blank string are **not** warned about: they are the normal "no
    metadata" state of the column, not a defect.
    """
    if raw is None:
        return {}
    if isinstance(raw, dict):  # already parsed (tolerated for in-process callers)
        return dict(raw)
    if not isinstance(raw, str):
        counters.warn(warning)
        return {}
    text = raw.strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except ValueError:  # includes json.JSONDecodeError
        counters.warn(warning)
        return {}
    if not isinstance(parsed, dict):
        counters.warn(warning)
        return {}
    return parsed


def _schema_object(value: Any, counters: _Counters) -> dict[str, Any] | None:
    """Capability-level ``request_schema`` value as an object, or ``None``."""
    if value is None:
        return None
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        # A JSON object stored as text is accepted; anything else falls through.
        return _parse_object(value, counters, WARN_INVALID_REQUEST_SCHEMA) or None
    counters.warn(WARN_NON_OBJECT_REQUEST_SCHEMA)
    return None


def _dispatch_override(blob: dict[str, Any], counters: _Counters) -> str | None:
    """A valid ``dispatch`` override from one JSON blob, else ``None``.

    A present-but-invalid value is counted (总纲 §4.4 forbids a new error code for
    it) and the derivation runs instead, so one bad blob cannot cost a whole row.
    """
    if _KEY_DISPATCH not in blob:
        return None
    value = _text(blob.get(_KEY_DISPATCH))
    if value is not None and value in DISPATCH_HINTS:
        return value
    counters.warn(WARN_INVALID_DISPATCH_OVERRIDE)
    return None


# ---------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------
def default_session_factory() -> Callable[[], Session]:
    """The process-wide ``SessionLocal``, imported **lazily**.

    :mod:`app.db.session` builds an engine (and creates the SQLite directory) at
    import time. This module is imported by the MCP layer, so that side effect is
    kept inside the function that actually needs a database.
    """
    from app.db.session import SessionLocal

    return SessionLocal


def _interface_view(row: ToolInterfaceRow) -> _Interface:
    """Copy one ``tool_interfaces`` row into a plain value object."""
    return _Interface(
        interface_code=row.interface_code,
        method=row.method,
        endpoint=row.endpoint,
        request_wrapper=row.request_wrapper,
        response_root_key=row.response_root_key,
        product_scope=row.product_scope,
        domain=row.domain,
        feature=row.feature,
        request_schema_json=row.request_schema_json,
        metadata_json=row.metadata_json,
        enabled=int(row.enabled or 0),
    )


def _read_rows(session: Session) -> list[_SourceRow]:
    """Read every ``capabilities`` row with its tool and interface(s).

    ``tools`` and ``tool_interfaces`` are joined with **outer** joins on purpose:
    an inner join would silently drop a row whose tool or interface is missing, and
    a silent drop is the failure mode this loader exists to prevent. Missing halves
    become ``None`` and are counted by :func:`_to_capability`.

    ``interface_id`` is the primary link; ``capability_interfaces`` (裁决 B-3) is
    read as the fallback and contributes each capability's **lowest**
    ``interface_id``.
    """
    interfaces_by_id: dict[int, _Interface] = {
        int(row.id): _interface_view(row)
        for row in session.scalars(select(ToolInterfaceRow)).all()
    }

    linked_interface_id: dict[int, int] = {}
    links = session.execute(
        select(
            CapabilityInterfaceRow.capability_id,
            CapabilityInterfaceRow.interface_id,
        ).order_by(
            CapabilityInterfaceRow.capability_id,
            CapabilityInterfaceRow.interface_id,
        )
    ).all()
    for capability_id, interface_id in links:
        linked_interface_id.setdefault(int(capability_id), int(interface_id))

    statement = (
        select(CapabilityRow, ToolRow.name)
        .select_from(CapabilityRow)
        .outerjoin(ToolRow, CapabilityRow.tool_id == ToolRow.id)
        .order_by(CapabilityRow.id)
    )

    out: list[_SourceRow] = []
    for row, tool_name in session.execute(statement).all():
        capability_id = int(row.id)
        primary_id = int(row.interface_id) if row.interface_id is not None else None
        fallback_id = linked_interface_id.get(capability_id)
        out.append(
            _SourceRow(
                capability_id=capability_id,
                code=row.capability_code,
                adapter_code=row.adapter_code,
                resource=row.resource,
                action=row.action,
                enabled=int(row.enabled or 0),
                description=row.description,
                constraints_json=row.constraints_json,
                interface_id=primary_id,
                tool_name=tool_name,
                interface=interfaces_by_id.get(primary_id) if primary_id is not None else None,
                linked_interface=(
                    interfaces_by_id.get(fallback_id) if fallback_id is not None else None
                ),
            )
        )
    return out


# ---------------------------------------------------------------------------
# building
# ---------------------------------------------------------------------------
def _to_capability(source: _SourceRow, counters: _Counters) -> Capability | None:
    """Build one :class:`Capability`, or ``None`` after counting the reason.

    Every ``return None`` here corresponds to exactly one entry of
    :data:`SKIP_REASONS`; nothing is dropped without a counter.
    """
    if not source.enabled:
        counters.skip(SKIP_CAPABILITY_DISABLED)
        return None

    code = _text(source.code)
    resource = _text(source.resource)
    action = _text(source.action)
    if not code or not resource or not action:
        counters.skip(SKIP_MISSING_REQUIRED_FIELD)
        return None

    if source.tool_name is None:
        counters.skip(SKIP_TOOL_ROW_MISSING)
        return None
    tool = _text(source.tool_name)
    if tool not in TOOL_NAMES:
        counters.skip(SKIP_UNKNOWN_TOOL)
        return None

    interface = source.interface
    if interface is None:
        if source.interface_id is not None:
            # interface_id points at no row: counted, then the B-3 link is tried.
            counters.warn(WARN_INTERFACE_ROW_MISSING)
        interface = source.linked_interface
    if interface is not None and not interface.enabled:
        counters.skip(SKIP_INTERFACE_DISABLED)
        return None

    metadata = (
        _parse_object(interface.metadata_json, counters, WARN_INVALID_METADATA_JSON)
        if interface is not None
        else {}
    )
    constraints = _parse_object(
        source.constraints_json, counters, WARN_INVALID_CONSTRAINTS_JSON
    )

    endpoint = _text(interface.endpoint) if interface is not None else None

    # --- dispatch (no column: override, else the reviewable derivation) -----
    override = _dispatch_override(constraints, counters) or _dispatch_override(
        metadata, counters
    )
    dispatch = override if override is not None else derive_dispatch(
        tool, resource, action, endpoint
    )
    if dispatch is None:
        counters.skip(SKIP_UNDERIVABLE_DISPATCH)
        return None

    # --- request_schema: capability level wins over the interface's ---------
    request_schema = _schema_object(constraints.get(_KEY_REQUEST_SCHEMA), counters)
    if request_schema is None and interface is not None:
        request_schema = _parse_object(
            interface.request_schema_json, counters, WARN_INVALID_REQUEST_SCHEMA
        )

    # --- outer-key vocabularies: metadata_json, else derived (总纲 §0.4) ----
    means = _text(metadata.get(_KEY_OUTER_KEY_MEANS))
    kind = _text(metadata.get(_KEY_OUTER_KEY_KIND))
    if endpoint is not None and endpoint.lower().startswith(_DB_PREFIX):
        if means is None or kind is None:
            try:
                derived_means = outer_key_means_for(endpoint)
                derived_kind = outer_key_kind_for(endpoint)
            except AdapterError:
                counters.warn(WARN_OUTER_KEY_DERIVATION_FAILED)
            else:
                means = means or derived_means
                kind = kind or derived_kind

    return Capability(
        code=code,
        tool=tool,
        resource=resource,
        action=action,
        adapter_code=_text(source.adapter_code),
        method=_text(interface.method) if interface is not None else None,
        endpoint=endpoint,
        request_wrapper=_text(interface.request_wrapper) if interface is not None else None,
        response_root_key=(
            _text(interface.response_root_key) if interface is not None else None
        ),
        outer_key_means=means or "self",
        outer_key_kind=kind or "self",
        request_schema=request_schema or {},
        dispatch=dispatch,
        adapter_action=(
            _text(constraints.get(_KEY_ADAPTER_ACTION))
            or _text(metadata.get(_KEY_ADAPTER_ACTION))
        ),
        task_type=(
            _text(constraints.get(_KEY_TASK_TYPE)) or _text(metadata.get(_KEY_TASK_TYPE))
        ),
        # Empty -> ``Capability.__post_init__`` substitutes ``code`` (V2.1 §17.4).
        interface_code=_text(interface.interface_code) if interface is not None else "",
        product_scope=(
            (_text(interface.product_scope) or "unknown")
            if interface is not None
            else "unknown"
        ),
        domain=_text(interface.domain) if interface is not None else None,
        feature=_text(interface.feature) if interface is not None else None,
        # 总纲 §4.2.13: ``capabilities.description`` is the Chinese annotation's
        # documented home (``notes`` has no column of its own), so a seeded row's
        # ``notes`` **is** that annotation, copied verbatim.  An explicit
        # ``constraints_json.notes`` still wins: an operator's statement outranks a
        # seeded value, and ``metadata_json.notes`` remains the last fallback.
        notes=(
            _text(constraints.get(_KEY_NOTES))
            or _text(source.description)
            or _text(metadata.get(_KEY_NOTES))
            or ""
        ),
    )


# ---------------------------------------------------------------------------
# the entry points
# ---------------------------------------------------------------------------
def load_capabilities_now(
    session_factory: Callable[[], Session] | None = None, *, replace: bool = True
) -> LoadResult:
    """Blocking :func:`load_capabilities` — opens its own session and loads.

    ``session_factory`` is any zero-argument callable returning a
    :class:`~sqlalchemy.orm.Session` (a ``sessionmaker``, or a lambda around one).
    ``None`` selects the process-wide :func:`default_session_factory`. Taking the
    factory instead of reaching for the module global is what lets a test point the
    loader at a ``tmp_path`` SQLite file.

    The read happens inside one :func:`app.db.base.session_scope_for` block and the
    rows are copied into plain value objects there, so nothing ORM-bound outlives
    the session (which is what makes the ``async`` wrapper thread-safe).
    """
    factory = session_factory if session_factory is not None else default_session_factory()
    with session_scope_for(factory) as session:
        sources = _read_rows(session)

    counters = _Counters()
    occupied: set[tuple[str, str]] = {
        (row.adapter_code or "", row.code) for row in capability_rows()
    }
    seen: set[tuple[str, str]] = set()
    added = 0
    replaced = 0
    owners: set[str | None] = set()

    for source in sources:
        try:
            capability = _to_capability(source, counters)
        except Exception:  # noqa: BLE001 — 「Never raise on a single bad row」
            counters.skip(SKIP_MALFORMED_ROW)
            continue
        if capability is None:
            continue

        slot = (capability.adapter_code or "", capability.code)
        if slot in seen:
            counters.skip(SKIP_DUPLICATE_SLOT)
            continue
        seen.add(slot)

        existed = slot in occupied
        try:
            register_capability(capability, replace=replace)
        except AdapterError:
            counters.skip(SKIP_REGISTRATION_REJECTED)
            continue
        occupied.add(slot)
        if existed:
            replaced += 1
        else:
            added += 1
        owners.add(capability.adapter_code)

    loaded = added + replaced
    return LoadResult(
        rows_read=len(sources),
        loaded=loaded,
        added=added,
        replaced=replaced,
        skipped=len(sources) - loaded,
        skip_reasons=dict(sorted(counters.skip_reasons.items())),
        warnings=dict(sorted(counters.warnings.items())),
        adapters=tuple(sorted(owners, key=lambda value: (value is None, value or ""))),
    )


async def load_capabilities(
    session_factory: Callable[[], Session] | None = None, *, replace: bool = True
) -> LoadResult:
    """Load the capability table from the database (V2.1 §16.1 Phase 2).

    ``await``-able entry point for the MCP layer. The models are **synchronous**
    SQLAlchemy 2.x and :mod:`app.db.session` exposes a sync ``sessionmaker``, so the
    blocking work is handed to :func:`asyncio.to_thread` and the ``Session`` is
    opened inside the worker thread — a ``Session`` is not thread-safe and is never
    shared between calls (the pattern of
    :class:`app.services.task_store.SqlAlchemyTaskStore`).

    ``replace=True`` (the default) replaces each row in place, which is what makes
    the load idempotent. Rows the database does not contain keep their static
    declaration (see the module docstring: the loader upserts, it never prunes), and
    :func:`app.mcp.capabilities.reset_capabilities` remains the offline fallback.

    Raises nothing for a bad row — see :class:`LoadResult`. A failure of the query
    itself propagates: that is an infrastructure fault, not a bad row.
    """
    return await asyncio.to_thread(load_capabilities_now, session_factory, replace=replace)
