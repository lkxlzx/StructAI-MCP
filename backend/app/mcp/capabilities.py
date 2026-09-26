"""Capability table — the routing heart of the MCP layer.

Authoritative sources
---------------------
* 《StructAI MCP V2.1 设计框架规范》(**V2.1**) §6.3 (action / resource 词表),
  §7–§11 (四个 Tool 的契约与 MCP 信封), §16.1 (解析表结构支撑),
  §17.1–§17.5 (Endpoint Mapping / ``interface_code`` / 端点语义陷阱),
  §25.1–§25.2 (写操作选项与高风险操作), §26.2 (``tasks.type`` 封闭 14 值).
* 《StructAI 管理器 API 接口设计规范 v1.2》(**v1.2**) §37 (MCP endpoint 与 REST
  分离), §38 (Dispatcher 流程).
* 《MIDAS NX Open API 对接规范 v1.0》(**对接规范**) §2.5.1 (MIDAS **没有**任务
  API), §2.5.2 (每实例串行), §3.3 (新文件必需数据只能 GET/PUT), §3.5 (15 条
  危险语义), §4.1 (``Assign`` 外层键语义), §5 (``/info`` 自省), §11.5 (写操作实机
  结论), §11.6 (CNLD 外层键是节点号).
* 《StructAI 架构边界与融合规范 v1.0 总纲》(**总纲**) §0.4 (唯一真源),
  §4.1.3 (ID 前缀封闭集合), §4.2.1 (``tasks.status``), §4.3.2 (MCP 信封),
  §4.4 (错误码封闭集合), §4.6.1 (MCP 单数资源名), §4.8.2 (权限码封闭集合).

Why this table exists
---------------------
总纲 §0.4 「唯一真源原则」 and V2.1 §6.1 forbid the four tool schemas from being
hand-written: their ``action`` / ``resource`` / ``target`` enums are **generated**
from this table (see :func:`resources_for` / :func:`actions_for` and
``app.mcp.tools.*.build_schema``), so a schema can never drift from the router.

The user ruling recorded in V2.1 §6.3 is honoured: the **real MIDAS API is
authoritative** for the resource vocabulary, so the resource enum is *not*
restricted to V2.0's nine model resources.  ``load_case`` / ``structure_type`` /
``unit`` / ``project`` are first-class resources because ``/db/STLD``,
``/db/STYP``, ``/db/UNIT`` and ``/db/PJCF`` are real endpoints
(``docs/api-registry/ENDPOINT_INDEX.md``).

``outer_key_means`` — two readings of 对接规范 §4.1 (documented contradiction)
-----------------------------------------------------------------------------
对接规范 §4.1's table names, per endpoint, what the ``Assign`` **outer key** is::

    /db/NODE  节点号        /db/ELEM  单元号
    /db/CNLD  节点号        /db/CONS  约束组号      /db/STLD  工况号

V2.1 §17.3 asks ``tool_interfaces.metadata_json.outer_key_means`` to record this
with the vocabulary ``node`` / ``element`` / ``load_case`` / ``group`` / ``self``.
Two mutually consistent readings exist:

* :attr:`Capability.outer_key_kind` — the reading used by
  :func:`app.adapters.midas_gen.adapter.outer_key_means`, i.e. the **live-verified
  write guard**: it names the *entity kind* even for self-addressed endpoints
  (``/db/NODE`` -> ``"node"``), so ``validate_assign_outer_key()`` can enforce a
  numeric key on every numbered endpoint.
* :attr:`Capability.outer_key_means` — the reading requested for this layer:
  ``"self"`` when the outer key **is the endpoint's own entity number**
  (``/db/NODE``, ``/db/ELEM``, ``/db/MATL`` …) and the **foreign** entity kind
  otherwise (``/db/CNLD`` -> ``"node"``, ``/db/CONS`` -> ``"group"``).

Both are derived from the adapter (唯一真源): this module never hard-codes the
semantics, it *projects* :func:`~app.adapters.midas_gen.adapter.outer_key_means`
onto the two vocabularies, so the two can never disagree about which endpoints
are foreign-addressed.  The **guard** always runs inside the adapter with
``outer_key_kind``; ``outer_key_means`` is descriptive metadata.
"""

from dataclasses import dataclass, field, replace
from typing import Any, Final, Sequence

from app.adapters.errors import AdapterError
from app.adapters.midas_gen.adapter import outer_key_means as _adapter_outer_key_means
from app.adapters.midas_gen.adapter import resource_of
from app.core.constants import (
    MIDAS_CLIENT_STATUS_VALUES,
    MCP_SERVER_STATUS_VALUES,
    PROJECT_STATUS_VALUES,
    TASK_STATUS_VALUES,
    TASK_TYPE_VALUES,
)
from app.core.errors import ErrorCode

__all__ = [
    # tools
    "TOOL_QUERY",
    "TOOL_MODEL",
    "TOOL_EXECUTE",
    "TOOL_TASK",
    "TOOL_NAMES",
    # dispatch hints (closed set)
    "DISPATCH_QUERY",
    "DISPATCH_INTROSPECT",
    "DISPATCH_MODEL",
    "DISPATCH_DELETE",
    "DISPATCH_GET_TABLE",
    "DISPATCH_EXECUTE",
    "DISPATCH_TASK",
    "DISPATCH_LOCAL_CAPABILITIES",
    "DISPATCH_MODEL_OVERVIEW",
    "DISPATCH_MODEL_SYNC",
    "DISPATCH_NOT_IMPLEMENTED",
    "DISPATCH_HINTS",
    # read / write classification
    "READ_ACTIONS",
    "is_write_action",
    # permissions (总纲 §4.8.2 closed set)
    "required_permission",
    # the table
    "Capability",
    "capability_table",
    "capability_rows",
    "capability_payload",
    "query_filter_schemas",
    "resolve",
    "resources_for",
    "actions_for",
    "is_enabled",
    "DISABLED_CAPABILITIES",
    "register_capability",
    "unregister_capability",
    "reset_capabilities",
    "outer_key_means_for",
    "outer_key_kind_for",
]


# ---------------------------------------------------------------------------
# Tool names (v1.2 §37 — exactly four)
# ---------------------------------------------------------------------------
TOOL_QUERY: Final[str] = "midas_query"
TOOL_MODEL: Final[str] = "midas_model"
TOOL_EXECUTE: Final[str] = "midas_execute"
TOOL_TASK: Final[str] = "midas_task"

#: Declaration order == v1.2 §37's exposure order.
TOOL_NAMES: Final[tuple[str, ...]] = (TOOL_QUERY, TOOL_MODEL, TOOL_EXECUTE, TOOL_TASK)


# ---------------------------------------------------------------------------
# Dispatch hints — how the dispatcher reaches the adapter (v1.2 §38 step
# 「Interface Mapping -> Adapter」).  Closed set; an unknown value is a
# programming error, not a runtime condition.
# ---------------------------------------------------------------------------
#: ``adapter.query(QueryRequest)`` — §7.
DISPATCH_QUERY: Final[str] = "query"
#: ``adapter.introspect(resource)`` — 对接规范 §5 (``GET /info/db/<RES>``).
DISPATCH_INTROSPECT: Final[str] = "introspect"
#: ``adapter.model(ModelRequest)`` — §8.
DISPATCH_MODEL: Final[str] = "model"
#: ``adapter.delete(resource, ids)`` — 对接规范 §3.5 第 1 条: **逐 id 一次
#: ``DELETE {endpoint}/{id}``**; the ``Assign``-body form is never reachable.
DISPATCH_DELETE: Final[str] = "delete"
#: ``adapter.get_table(...)`` — 对接规范 §11.5.6 (``POST /post/TABLE``).
DISPATCH_GET_TABLE: Final[str] = "get_table"
#: ``adapter.execute(ExecuteRequest)`` — §9.
DISPATCH_EXECUTE: Final[str] = "execute"
#: The platform Task Engine (V2.1 §26).  MIDAS has **no** task API
#: (对接规范 §2.5.1), so this is purely our own bookkeeping.
DISPATCH_TASK: Final[str] = "task"
#: The capability table itself (裁决 C-7: ``capabilities`` is a *target*).
DISPATCH_LOCAL_CAPABILITIES: Final[str] = "local_capabilities"
#: Platform-side model snapshot: read ``/db/UNIT`` + ``/db/STYP`` and count the
#: model tables.  No single MIDAS endpoint carries a "model overview".
DISPATCH_MODEL_OVERVIEW: Final[str] = "model_overview"
#: 对接规范 §3.5 第 5 条: after a write timeout the **only** safe next step is to
#: read the model state back.
DISPATCH_MODEL_SYNC: Final[str] = "model_sync"
#: Declared but not mappable to a MIDAS endpoint — answered with the closed-set
#: code ``NOT_IMPLEMENTED`` (总纲 §4.4.9), never with a fabricated success.
DISPATCH_NOT_IMPLEMENTED: Final[str] = "not_implemented"

DISPATCH_HINTS: Final[frozenset[str]] = frozenset(
    {
        DISPATCH_QUERY,
        DISPATCH_INTROSPECT,
        DISPATCH_MODEL,
        DISPATCH_DELETE,
        DISPATCH_GET_TABLE,
        DISPATCH_EXECUTE,
        DISPATCH_TASK,
        DISPATCH_LOCAL_CAPABILITIES,
        DISPATCH_MODEL_OVERVIEW,
        DISPATCH_MODEL_SYNC,
        DISPATCH_NOT_IMPLEMENTED,
    }
)


# ---------------------------------------------------------------------------
# Read / write classification (V2.1 §26.5)
# ---------------------------------------------------------------------------
#: Only these actions may be replayed by the Task Engine.  Everything else —
#: including any action this table does not know — is treated as a **write**,
#: which is the fail-safe direction: V2.1 §26.5 / 对接规范 §3.5 第 5 条 forbid
#: auto-retrying a write after a timeout because 超时 ≠ 回滚.
READ_ACTIONS: Final[frozenset[str]] = frozenset(
    {"get", "list", "search", "count", "inspect", "read", "validate", "validate_model"}
)


def is_write_action(action: str) -> bool:
    """True when ``action`` must never be auto-retried (V2.1 §26.5)."""
    return (action or "").strip().lower() not in READ_ACTIONS


# ---------------------------------------------------------------------------
# Permission mapping — 总纲 §4.8.2 (closed set, 34 codes)
# ---------------------------------------------------------------------------
_ACTION_PERMISSION: Final[dict[str, str]] = {
    "create": "model:create",
    "update": "model:update",
    "upsert": "model:update",
    "delete": "model:delete",
    "read": "model:read",
    "validate": "model:test",
    "get": "task:read",
    "list": "task:read",
    "result": "task:read",
    "events": "task:read",
    "logs": "task:read",
    "cancel": "task:cancel",
    "retry": "task:retry",
}


def required_permission(tool: str, action: str) -> str:
    """Permission code (总纲 §4.8.2) an RBAC layer must check for this call.

    The auth/RBAC hook in :mod:`app.mcp.dispatcher` is a **documented seam**
    (v1.2 §38 「Authentication -> RBAC」); this function gives that seam the
    closed-set code it needs, so the wiring is one line rather than a redesign.
    """
    key = (action or "").strip().lower()
    if tool == TOOL_MODEL:
        return _ACTION_PERMISSION.get(key, "model:update")
    if tool == TOOL_EXECUTE:
        return "tool:execute"
    if tool == TOOL_TASK:
        return _ACTION_PERMISSION.get(key, "task:read")
    return "model:read"  # midas_query


# ---------------------------------------------------------------------------
# 对接规范 §4.1 — outer-key semantics, projected from the adapter
# ---------------------------------------------------------------------------
#: MIDAS resource name -> the entity kind that resource's **own** key denotes.
#: Resources absent from this map are ``"self"`` (their outer key is the
#: endpoint's own entity number).
_OWN_ENTITY_KIND: Final[dict[str, str]] = {
    "NODE": "node",
    "ELEM": "element",
    "STLD": "load_case",
    "GRUP": "group",
}


def outer_key_kind_for(endpoint: str) -> str:
    """The live-verified entity kind of an endpoint's ``Assign`` outer key.

    Delegates to :func:`app.adapters.midas_gen.adapter.outer_key_means` — the
    function ``validate_assign_outer_key()`` actually guards with — so this
    layer can never disagree with the write path (总纲 §0.4).
    """
    return _adapter_outer_key_means(endpoint)


def outer_key_means_for(endpoint: str) -> str:
    """``"self"`` or the **foreign** entity kind of the outer key.

    ``/db/NODE`` -> ``"self"`` (its own node number), ``/db/ELEM`` -> ``"self"``,
    ``/db/STLD`` -> ``"self"``, ``/db/GRUP`` -> ``"self"``,
    ``/db/CNLD`` -> ``"node"`` (对接规范 §4.1 / §11.6), ``/db/CONS`` -> ``"group"``.
    """
    kind = outer_key_kind_for(endpoint)
    if kind == "self":
        return "self"
    own = _OWN_ENTITY_KIND.get(resource_of(endpoint), "self")
    return "self" if kind == own else kind


# ---------------------------------------------------------------------------
# The Capability row
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Capability:
    """One ``capabilities`` row joined to its ``tool_interfaces`` row.

    Mirrors V2.1 §16.1's resolution tables (``capabilities`` +
    ``capability_interfaces`` + ``tool_interfaces``) in a single immutable row so
    the MCP layer needs no database round trip in Phase 1.  Phase 2 loads the
    same rows from the ``capabilities`` / ``tool_interfaces`` tables and
    :func:`register_capability` replaces them row by row.
    """

    #: ``capabilities.capability_code`` — ``"<resource>.<action>"`` (V2.1 §17.4).
    code: str
    #: Owning MCP tool (v1.2 §37).
    tool: str
    #: MCP singular resource name (总纲 §4.6.1).  For ``midas_query`` this is the
    #: ``target`` value (裁决 C-7).
    resource: str
    #: MCP action (V2.1 §6.3).
    action: str
    #: ``tool_interfaces.adapter_code``; ``None`` for platform-owned rows
    #: (``midas_task``), because MIDAS has no task API (对接规范 §2.5.1).
    adapter_code: str | None = "midas_gen"
    #: ``tool_interfaces.method``; ``None`` when no MIDAS call is made.
    method: str | None = None
    #: ``tool_interfaces.endpoint`` — real MIDAS endpoint, canonical UPPER case
    #: (对接规范 §3.6 建议).
    endpoint: str | None = None
    #: ``tool_interfaces.request_wrapper`` — ``"Assign"`` / ``"Argument"`` /
    #: ``None`` (V2.1 §17.3).
    request_wrapper: str | None = None
    #: ``tool_interfaces.response_root_key``; ``None`` for shape-matched or
    #: body-less endpoints (V2.1 §17.3).
    response_root_key: str | None = None
    #: ``metadata_json.outer_key_means`` — see the module docstring.
    outer_key_means: str = "self"
    #: ``metadata_json.outer_key_means`` in the adapter's vocabulary (the guard's).
    outer_key_kind: str = "self"
    #: Minimal JSON Schema of the **payload** this capability accepts.  Used for
    #: the mandatory second validation of V2.1 §6.2 / §9.3.
    request_schema: dict[str, Any] = field(default_factory=dict)
    #: How the dispatcher reaches the adapter; one of :data:`DISPATCH_HINTS`.
    dispatch: str = DISPATCH_QUERY
    #: Action name the adapter's ``execute()`` understands, when it differs from
    #: the MCP action (V2.1 §6.3 vs §18.3).
    adapter_action: str | None = None
    #: ``tasks.type`` (V2.1 §26.2, closed 14 values) when this action becomes an
    #: asynchronous task; ``None`` means "finishes in seconds, run it inline"
    #: (V2.1 §26.1).
    task_type: str | None = None
    #: ``tool_interfaces.interface_code``.  Defaults to :attr:`code`; endpoints
    #: that carry several logical operations (``/post/TABLE``) encode the
    #: discriminator (V2.1 §17.4).
    interface_code: str = ""
    #: Free-text provenance / warning shown to callers.
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.interface_code:
            # frozen dataclass -> bypass the setter (V2.1 §17.4: one
            # interface_code per (endpoint, method) pair).
            object.__setattr__(self, "interface_code", self.code)

    # ------------------------------------------------------------------ #
    @property
    def adapter_resource(self) -> str:
        """Resource name to hand the adapter.

        ``/db/PJCF`` -> ``"PJCF"``: the MCP name is ``project`` (V2.1 §17.2) but
        the MIDAS resource is ``PJCF``.  V2.1 §17.2 keeps the singular MCP name
        in ``tool_interfaces.resource`` and lets the mapping happen here.
        """
        if self.endpoint and self.endpoint.lower().startswith("/db/"):
            return resource_of(self.endpoint)
        return self.resource

    @property
    def is_write(self) -> bool:
        """True when a timeout must **not** trigger an automatic retry (§26.5)."""
        return is_write_action(self.action)

    @property
    def effective_adapter_action(self) -> str:
        """Adapter-facing action name (``open_project`` -> ``open``)."""
        return self.adapter_action or self.action


# ---------------------------------------------------------------------------
# request_schema builders
# ---------------------------------------------------------------------------
def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    """``null`` OR ``schema`` — the ``data`` / ``query`` fields may be omitted."""
    return {"anyOf": [{"type": "null"}, schema]}


#: V2.1 §7.2 — per-``target`` filter schemas.  Transcribed so the tool schema can
#: stay closed (裁决 B-4: ``additionalProperties: false`` at every layer).
_QUERY_FILTERS: Final[dict[str, dict[str, Any]]] = {
    "server": {
        "title": "server filter",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "name": {"type": "string"},
            "status": {"type": "string", "enum": list(MCP_SERVER_STATUS_VALUES)},
            "transport": {"type": "string"},
        },
    },
    "client": {
        "title": "client filter",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "software": {"type": "string"},
            "version": {"type": "string"},
            "adapter": {"type": "string"},
            "status": {"type": "string", "enum": list(MIDAS_CLIENT_STATUS_VALUES)},
            "enabled": {"type": "boolean"},
        },
    },
    "capabilities": {
        "title": "capabilities filter",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "adapter": {"type": "string"},
            "resource": {"type": "string"},
            "action": {"type": "string"},
            "enabled": {"type": "boolean"},
            "software": {"type": "string"},
            "version": {"type": "string"},
        },
    },
    "model": {
        "title": "model filter",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "name": {"type": "string"},
            "path": {"type": "string"},
            "unit_system": {"type": "string"},
            "include_summary": {"type": "boolean", "default": True},
        },
    },
    "node": {
        "title": "node filter",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "ids": {"type": "array", "items": {"type": ["string", "integer"]}},
            "group": {"type": "string"},
            "x_min": {"type": "number"},
            "x_max": {"type": "number"},
            "y_min": {"type": "number"},
            "y_max": {"type": "number"},
            "z_min": {"type": "number"},
            "z_max": {"type": "number"},
            "name_like": {"type": "string"},
        },
    },
    "element": {
        "title": "element filter",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "ids": {"type": "array", "items": {"type": ["string", "integer"]}},
            "group": {"type": "string"},
            "element_type": {
                "type": "string",
                "enum": ["beam", "truss", "cable", "plate", "solid", "wall", "other"],
            },
            "material": {"type": "string"},
            "section": {"type": "string"},
            "node_id": {"type": ["string", "integer"]},
        },
    },
    "material": {
        "title": "material filter",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "ids": {"type": "array", "items": {"type": ["string", "integer"]}},
            "name": {"type": "string"},
            "grade": {"type": "string"},
            "material_type": {
                "type": "string",
                "enum": ["steel", "concrete", "composite", "timber", "other"],
            },
        },
    },
    "section": {
        "title": "section filter",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "ids": {"type": "array", "items": {"type": ["string", "integer"]}},
            "name": {"type": "string"},
            "shape": {
                "type": "string",
                "enum": ["H", "BOX", "PIPE", "T", "L", "C", "RECT", "CIRCLE", "other"],
            },
            "material": {"type": "string"},
        },
    },
    "load": {
        "title": "load filter",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "load_case": {"type": "string"},
            "load_type": {
                "type": "string",
                "enum": [
                    "static",
                    "wind",
                    "snow",
                    "seismic",
                    "temperature",
                    "moving",
                    "other",
                ],
            },
            "group": {"type": "string"},
            "node_id": {"type": ["string", "integer"]},
            "element_id": {"type": ["string", "integer"]},
        },
    },
    "load_case": {
        "title": "load_case filter",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "ids": {"type": "array", "items": {"type": ["string", "integer"]}},
            "name": {"type": "string"},
            "load_type": {"type": "string"},
        },
    },
    "boundary": {
        "title": "boundary filter",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "group": {"type": "string"},
            "boundary_type": {
                "type": "string",
                "enum": ["support", "spring", "constraint", "release", "other"],
            },
            "node_id": {"type": ["string", "integer"]},
        },
    },
    "group": {
        "title": "group filter",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "name": {"type": "string"},
            "group_type": {
                "type": "string",
                "enum": ["node", "element", "load", "boundary", "mixed", "other"],
            },
            "parent": {"type": "string"},
        },
    },
    "analysis": {
        "title": "analysis filter",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "analysis_type": {
                "type": "string",
                "enum": [
                    "static",
                    "modal",
                    "buckling",
                    "response_spectrum",
                    "time_history",
                    "other",
                ],
            },
            "load_case": {"type": "string"},
            "load_combination": {"type": "string"},
            "include_cases": {"type": "boolean", "default": True},
        },
    },
    "result": {
        "title": "result filter",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "result_type": {
                "type": "string",
                "enum": [
                    "displacement",
                    "reaction",
                    "force",
                    "stress",
                    "mode",
                    "story_drift",
                    "other",
                ],
            },
            "load_combination": {"type": "string"},
            "load_case": {"type": "string"},
            "node_ids": {"type": "array", "items": {"type": ["string", "integer"]}},
            "element_ids": {"type": "array", "items": {"type": ["string", "integer"]}},
            "component": {"type": "string"},
            "envelope": {"type": "boolean", "default": False},
            "top_n": {"type": "integer", "minimum": 1, "maximum": 500},
        },
    },
    "project": {
        "title": "project filter",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "name": {"type": "string"},
            "code": {"type": "string"},
            "status": {"type": "string", "enum": list(PROJECT_STATUS_VALUES)},
            "owner_id": {"type": "integer"},
        },
    },
    # V2.1 §7.2 lists neither of these as a ``target``, but both are real
    # ``/db/*`` tables (手册 02 章) and the platform-side model snapshot needs
    # them.  They get the only filter every ``/db`` table shares — its own key.
    "unit": {
        "title": "unit filter",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "ids": {"type": "array", "items": {"type": ["string", "integer"]}},
            "force": {"type": "string"},
            "dist": {"type": "string"},
            "heat": {"type": "string"},
            "temper": {"type": "string"},
        },
    },
    "structure_type": {
        "title": "structure_type filter",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "ids": {"type": "array", "items": {"type": ["string", "integer"]}},
        },
    },
}


def _query_request_schema(target: str) -> dict[str, Any]:
    """Payload schema for ``midas_query`` rows: the ``query`` filter object."""
    filter_schema = _QUERY_FILTERS.get(target)
    if filter_schema is None:
        return {"type": ["object", "null"]}
    return _nullable(filter_schema)


def query_filter_schemas() -> dict[str, dict[str, Any]]:
    """V2.1 §7.2 per-``target`` filter schemas, keyed by target.

    Public accessor so ``app.mcp.tools.query`` can build the tool schema's
    ``query`` property from the same objects this table validates against — one
    source, no drift.
    """
    return {target: dict(schema) for target, schema in _QUERY_FILTERS.items()}


#: MIDAS field names known from 对接规范 / the official manual, per model
#: resource.  Empty means "read them from ``GET /info/db/<RES>``" (对接规范 §5):
#: hand-copying ~270 endpoints' field sets is explicitly declared infeasible by
#: 对接规范 §4's conclusion, so the schema stays open on *fields* while the
#: **envelope** stays closed.
_MODEL_PAYLOAD_FIELDS: Final[dict[str, tuple[str, ...]]] = {
    "project": (),
    "unit": ("FORCE", "DIST", "HEAT", "TEMPER"),
    "structure_type": ("STYP", "MASS", "GRAV", "bSELFWEIGHT"),
    "node": ("X", "Y", "Z"),
    "element": ("TYPE", "MATL", "SECT", "NODE", "ANGLE"),
    "material": ("TYPE", "NAME", "PARAM"),
    "section": ("SECTTYPE", "SECT_NAME", "SECT_BEFORE"),
    "boundary": ("ITEMS",),
    "load_case": ("NAME", "TYPE", "DESC"),
    "load": ("ITEMS",),
    "group": (),
}


def _model_request_schema(resource: str, endpoint: str) -> dict[str, Any]:
    """Payload schema for ``midas_model`` rows.

    The payload speaks **MIDAS field names verbatim**: canonical ⇄ MIDAS field
    mapping belongs to ``midas_gen/mapper.py`` (V2.1 §22 / §23) and is not built
    yet, so this layer must not invent canonical names.
    """
    schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"{resource} payload — MIDAS {endpoint}",
        "type": ["object", "array", "null"],
        "description": (
            f"{resource}: MIDAS 字段名原样传递（V2.1 §22 / §23：canonical ⇄ MIDAS 的"
            "字段映射属于 mapper.py，不在 MCP 层）。载荷形状见对接规范 §4 的四类："
            "A 扁平字段 / B 容器+ITEMS / C 嵌套参数数组 / D 多层嵌套。"
        ),
        "x-midas-fields": list(_MODEL_PAYLOAD_FIELDS.get(resource, ())),
    }
    if endpoint.startswith("/db/"):
        schema["x-introspect"] = f"/info{endpoint}"
    return schema


# ---------------------------------------------------------------------------
# The static table
# ---------------------------------------------------------------------------
_QUERY_DATA_ACTIONS: Final[tuple[str, ...]] = ("get", "list", "search", "count")

#: ``midas_query`` targets backed by a ``GET /db/<RES>`` table, with the real
#: endpoint and its response root key (V2.1 §17.3, 对接规范 §3.2.1).
_QUERY_DATA_TARGETS: Final[tuple[tuple[str, str, str], ...]] = (
    ("node", "/db/NODE", "NODE"),
    ("element", "/db/ELEM", "ELEM"),
    ("material", "/db/MATL", "MATL"),
    ("section", "/db/SECT", "SECT"),
    ("load", "/db/CNLD", "CNLD"),
    ("boundary", "/db/CONS", "CONS"),
    # ``load_case`` was missing here while the platform-side model snapshot
    # (``target=model`` / ``action=sync``) reads it, so those two calls failed
    # with CAPABILITY_NOT_SUPPORTED.  ``/db/STLD`` is a real endpoint and the
    # ``load_case`` model rows already exist above, so it belongs here too.
    ("load_case", "/db/STLD", "STLD"),
    ("group", "/db/GRUP", "GRUP"),
    ("analysis", "/db/ACTL", "ACTL"),
    ("project", "/db/PJCF", "PJCF"),
    # V2.1 §7.2's target list omits these two; 手册 02 章 has both endpoints and
    # the platform-side model snapshot (``target=model`` / ``action=sync``) reads
    # them, so they are first-class query targets rather than a special case.
    ("unit", "/db/UNIT", "UNIT"),
    ("structure_type", "/db/STYP", "STYP"),
)

#: ``midas_query`` targets that never touch MIDAS (裁决 C-7 / V2.1 §16).
_QUERY_LOCAL_TARGETS: Final[tuple[tuple[str, str], ...]] = (
    ("server", DISPATCH_QUERY),
    ("client", DISPATCH_QUERY),
    ("capabilities", DISPATCH_LOCAL_CAPABILITIES),
    ("model", DISPATCH_MODEL_OVERVIEW),
)

#: ``midas_model`` resources: ``(resource, endpoint, root_key, actions, note)``.
#: ``/db/UNIT`` / ``/db/STYP`` are 「新文件必需数据」 — ``POST`` 不生效, only
#: ``GET`` / ``PUT`` (对接规范 §3.3), hence no ``create``.  ``/db/GRUP`` has no
#: documented ``DELETE`` (``docs/api-registry/ENDPOINT_INDEX.md`` ch.02).
_MODEL_RESOURCES: Final[tuple[tuple[str, str, str, tuple[str, ...], str], ...]] = (
    (
        "project",
        "/db/PJCF",
        "PJCF",
        ("create", "read", "update", "delete", "upsert", "validate"),
        "Project Information（手册 02 章）：POST/GET/PUT/DELETE 四法齐备。",
    ),
    (
        "unit",
        "/db/UNIT",
        "UNIT",
        ("read", "update", "upsert", "validate"),
        "对接规范 §3.3：单位系属「新文件必需数据」，POST 不生效，只能 GET/PUT —— "
        "故不暴露 create。",
    ),
    (
        "structure_type",
        "/db/STYP",
        "STYP",
        ("read", "update", "upsert", "validate"),
        "对接规范 §3.3：结构类型同属「新文件必需数据」，POST 不生效。",
    ),
    (
        "node",
        "/db/NODE",
        "NODE",
        ("create", "read", "update", "delete", "upsert", "validate"),
        "对接规范 §4.1：Assign 外层键 = 节点号。DELETE 只能逐 id（§3.5 第 1 条）。",
    ),
    (
        "element",
        "/db/ELEM",
        "ELEM",
        ("create", "read", "update", "delete", "upsert", "validate"),
        "对接规范 §4.1：Assign 外层键 = 单元号；§11.5.5：读回会把 NODE 归一化到 8 项。",
    ),
    (
        "material",
        "/db/MATL",
        "MATL",
        ("create", "read", "update", "delete", "upsert", "validate"),
        "对接规范 §11.5.5：读回会追加 6 个字段，禁止用读回反推最小写入载荷。",
    ),
    (
        "section",
        "/db/SECT",
        "SECT",
        ("create", "read", "update", "delete", "upsert", "validate"),
        "载荷形状 D（多层嵌套），见对接规范 §4。",
    ),
    (
        "boundary",
        "/db/CONS",
        "CONS",
        ("create", "read", "update", "delete", "upsert", "validate"),
        "对接规范 §4.1：Assign 外层键 = 约束组号（group）；ITEMS[].ID **就是**节点号，"
        "不受 §11.6 的 CNLD 序号规则约束。",
    ),
    (
        "load_case",
        "/db/STLD",
        "STLD",
        ("create", "read", "update", "delete", "upsert", "validate"),
        "对接规范 §4.1：Assign 外层键 = 工况号；§11.5.5：读回会追加 NO。",
    ),
    (
        "load",
        "/db/CNLD",
        "CNLD",
        ("create", "read", "update", "delete", "upsert", "validate"),
        "🔴 对接规范 §4.1 / §11.6：Assign 外层键是**节点号**，ITEMS[].ID 只是**序号**。"
        "误用会把荷载静默加到错误节点：分析仍回 command complete，而内力/位移全零。",
    ),
    (
        "group",
        "/db/GRUP",
        "GRUP",
        ("create", "read", "update", "upsert", "validate"),
        "手册 02 章只记载 POST/GET/PUT，未记载 DELETE，故不暴露 delete。",
    ),
)

#: ``midas_execute`` actions: ``(resource, action, dispatch, adapter_action,
#: task_type, endpoint, wrapper, note)``.  ``task_type`` is the V2.1 §26.2 closed
#: value; ``None`` means the action finishes in seconds and runs inline (§26.1).
_EXECUTE_ROWS: Final[
    tuple[tuple[str, str, str, str | None, str | None, str | None, str | None, str], ...]
] = (
    (
        "server",
        "connect",
        DISPATCH_EXECUTE,
        "connect",
        None,
        "/mapikey/verify",
        None,
        "对接规范 §2.2：/mapikey/verify 在**主机根**，不含产品段。秒级操作，同步执行。",
    ),
    (
        "server",
        "disconnect",
        DISPATCH_EXECUTE,
        "disconnect",
        None,
        None,
        None,
        "释放本地连接；MIDAS 侧无对应端点。秒级操作，同步执行。",
    ),
    (
        "project",
        "open_project",
        DISPATCH_EXECUTE,
        "open",
        "model_import",
        "/doc/OPEN",
        "Argument",
        "对接规范 §3.4 末行：路径必须是**裸字符串**，对象形式会被拒却仍返回 200。"
        "所有路径在 NX 主机上解析（§3.5 第 6 条），且不得位于受保护路径（第 13 条）。",
    ),
    (
        "project",
        "save_project",
        DISPATCH_EXECUTE,
        "save",
        "export",
        "/doc/SAVE",
        "Argument",
        "对接规范 §11.5.2：/doc/* 成功时上游只回 {\"message\":\"... command complete\"}，"
        "必须读回核对。",
    ),
    (
        "project",
        "close_project",
        DISPATCH_EXECUTE,
        "close",
        None,
        "/doc/CLOSE",
        "Argument",
        "秒级操作，同步执行。",
    ),
    (
        "file",
        "import",
        DISPATCH_EXECUTE,
        "import",
        "import",
        "/doc/IMPORT",
        "Argument",
        "对接规范 §3.4 末行：裸字符串路径。",
    ),
    (
        "file",
        "export",
        DISPATCH_EXECUTE,
        "export",
        "export",
        "/doc/EXPORT",
        "Argument",
        "🔴 对接规范 §11.5.2 实机：{\"Argument\": {\"EXPORT_PATH\": p}} -> 200 但**文件未写出**；"
        "{\"Argument\": p}（裸字符串）才写出 2769 字节。只看状态码必然误判。",
    ),
    (
        "model",
        "calculate",
        DISPATCH_EXECUTE,
        "calculate",
        "calculate",
        "/doc/ANAL",
        None,
        "对接规范 §11.5.7：一般分析用**裸 {}**，带 Argument 包装会走推覆分支。"
        "§11.5.8：/doc/ANAL 会真正校验模型（无边界条件 -> 400 [错误] 边界条件 没有定义。）。",
    ),
    (
        "analysis",
        "analysis",
        DISPATCH_EXECUTE,
        "analysis",
        "analysis",
        "/doc/ANAL",
        "Argument",
        "推覆分析形态：对接规范 §11.5.7 —— {\"Argument\": {\"TYPE\": \"Pushover\"}}。",
    ),
    (
        "result",
        "export",
        DISPATCH_GET_TABLE,
        "table",
        "export",
        "/post/TABLE",
        "Argument",
        "对接规范 §11.5.6：COMPONENTS 必需（省略时返回 200 {\"message\":\"\"}，看似无结果实为"
        "请求不完整）；EXPORT_PATH 让上游把表写到 NX 主机。",
    ),
    (
        "report",
        "generate_report",
        DISPATCH_NOT_IMPLEMENTED,
        None,
        "report",
        None,
        None,
        "对接规范 §2.5.1：MIDAS NX Open API **没有**报告端点（全文检索 동시/concurrent/"
        "queue 的 94 处命中全是结构工程概念）。报告生成由平台报告模块承担（V2.1 §26 / v1.2）。",
    ),
    (
        "model",
        "validate_model",
        DISPATCH_NOT_IMPLEMENTED,
        None,
        None,
        None,
        None,
        "MIDAS 没有独立的模型校验端点；唯一会校验模型的是 /doc/ANAL（对接规范 §11.5.8）。"
        "需要校验请用 action=calculate，或逐资源 action=validate 做写前 dry-run。",
    ),
    (
        "model",
        "sync",
        DISPATCH_MODEL_SYNC,
        None,
        None,
        None,
        None,
        "对接规范 §3.5 第 5 条：写操作超时后**必须先读回模型状态**。本动作只读，不写。",
    ),
    (
        "command",
        "command",
        DISPATCH_EXECUTE,
        "raw",
        None,
        None,
        None,
        "原始通道：调用方直接给 method/endpoint/body，适配器仍强制 DELETE 守卫、"
        "/db/NMAS 必填兜底与 /db/PRES DIRECTION 强制（对接规范 §3.5 第 1/3/12 条）。",
    ),
)


def _outer_key_kwargs(endpoint: str | None) -> dict[str, str]:
    """Derive both outer-key vocabularies from the adapter (总纲 §0.4).

    Empty for endpoints that never carry an ``Assign`` body, so the dataclass
    defaults (``"self"``) apply.
    """
    if not endpoint or not endpoint.lower().startswith("/db/"):
        return {}
    return {
        "outer_key_means": outer_key_means_for(endpoint),
        "outer_key_kind": outer_key_kind_for(endpoint),
    }


def _build_rows() -> tuple[Capability, ...]:
    """Materialise the whole static table (declaration order preserved)."""
    rows: list[Capability] = []

    # --- midas_query: local targets ---------------------------------------
    for target, dispatch in _QUERY_LOCAL_TARGETS:
        endpoint: str | None = "/mapikey/verify" if target == "server" else None
        for action in _QUERY_DATA_ACTIONS:
            rows.append(
                Capability(
                    code=f"{target}.{action}",
                    tool=TOOL_QUERY,
                    resource=target,
                    action=action,
                    method="GET" if endpoint else None,
                    endpoint=endpoint,
                    request_schema=_query_request_schema(target),
                    dispatch=dispatch,
                    notes=(
                        "裁决 C-7：capabilities 只作为 target 取值，"
                        "action=capabilities 已从枚举中移除，统一写作 "
                        '{"target":"capabilities","action":"list"}。'
                        if target == "capabilities"
                        else ""
                    ),
                )
            )

    # --- midas_query: /db table targets ----------------------------------
    for target, endpoint, root in _QUERY_DATA_TARGETS:
        for action in _QUERY_DATA_ACTIONS:
            rows.append(
                Capability(
                    code=f"{target}.{action}",
                    tool=TOOL_QUERY,
                    resource=target,
                    action=action,
                    method="GET",
                    endpoint=endpoint,
                    response_root_key=root,
                    request_schema=_query_request_schema(target),
                    dispatch=DISPATCH_QUERY,
                    **_outer_key_kwargs(endpoint),
                )
            )
        # 对接规范 §5.1：/info 只为 /db/* 提供；设计代码端点一律 404。
        rows.append(
            Capability(
                code=f"{target}.inspect",
                tool=TOOL_QUERY,
                resource=target,
                action="inspect",
                method="GET",
                endpoint=f"/info{endpoint}",
                response_root_key=None,
                request_schema=_query_request_schema(target),
                dispatch=DISPATCH_INTROSPECT,
                notes=(
                    "对接规范 §5.0.1：自省响应固定包在 'Argument' 下（不是资源名）；"
                    "§5.2：schema 扁平且不完整，只适合核对字段名是否存在。"
                ),
            )
        )

    # --- midas_query: results (POST /post/TABLE) -------------------------
    for action in _QUERY_DATA_ACTIONS:
        rows.append(
            Capability(
                code=f"result.{action}",
                tool=TOOL_QUERY,
                resource="result",
                action=action,
                method="POST",
                endpoint="/post/TABLE",
                request_wrapper="Argument",
                response_root_key=None,
                request_schema=_query_request_schema("result"),
                dispatch=DISPATCH_GET_TABLE,
                interface_code="result.table",
                notes=(
                    "V2.1 §17.4：/post/TABLE 承载多个逻辑端点，interface_code 必须编码判别符"
                    "（真正的选择在 Argument.TABLE_TYPE 上）。"
                    "对接规范 §3.5 第 8 条：响应根键不稳定且 'empty' 可承载完整表 -> 按形状匹配。"
                ),
            )
        )

    # --- midas_model ------------------------------------------------------
    for resource, endpoint, root, actions, note in _MODEL_RESOURCES:
        for action in actions:
            rows.append(
                Capability(
                    code=f"{resource}.{action}",
                    tool=TOOL_MODEL,
                    resource=resource,
                    action=action,
                    method="DELETE" if action == "delete" else "POST",
                    endpoint=endpoint,
                    request_wrapper="Assign",
                    response_root_key=root,
                    request_schema=_model_request_schema(resource, endpoint),
                    # 对接规范 §3.5 第 1 条：delete 只允许逐 id 的
                    # DELETE {endpoint}/{id}；Assign 体形式会清空整表。
                    dispatch=DISPATCH_DELETE if action == "delete" else DISPATCH_MODEL,
                    notes=note,
                    **_outer_key_kwargs(endpoint),
                )
            )

    # --- midas_execute ----------------------------------------------------
    for (
        resource,
        action,
        dispatch,
        adapter_action,
        task_type,
        endpoint,
        wrapper,
        note,
    ) in _EXECUTE_ROWS:
        rows.append(
            Capability(
                code=f"{resource}.{action}",
                tool=TOOL_EXECUTE,
                resource=resource,
                action=action,
                method="POST" if endpoint else None,
                endpoint=endpoint,
                request_wrapper=wrapper,
                dispatch=dispatch,
                adapter_action=adapter_action,
                task_type=task_type,
                notes=note,
            )
        )

    # --- midas_task (platform-owned; 对接规范 §2.5.1) ---------------------
    for action in ("get", "list", "cancel", "retry", "result", "events", "logs"):
        rows.append(
            Capability(
                code=f"task.{action}",
                tool=TOOL_TASK,
                resource="task",
                action=action,
                adapter_code=None,
                method=None,
                endpoint=None,
                dispatch=DISPATCH_TASK,
                notes=(
                    "对接规范 §2.5.1：MIDAS NX Open API **没有**任务端点，"
                    "异步语义完全由平台 Task Engine 承担（V2.1 §26）。"
                    "MCP 无 push/subscribe（裁决 B-9），只能轮询。"
                ),
            )
        )

    return tuple(rows)


_ROWS: Final[tuple[Capability, ...]] = _build_rows()

#: ``capabilities.enabled`` — the DB-shaped disable switch (V2.1 §16.1).  Phase 2
#: loads this set from the ``capabilities`` table; tests monkeypatch it.
DISABLED_CAPABILITIES: frozenset[str] = frozenset()


def _key(adapter_code: str | None, code: str) -> tuple[str, str]:
    """Composite table key.  ``None`` adapter (platform-owned) becomes ``""``.

    Mirrors the SQL: ``ux_capability(adapter_code, capability_code)`` polices the
    non-NULL half and ``ux_capability_platform`` the NULL half.
    """
    return (adapter_code or "", code)


#: The live table: ``(adapter_code or "", code) -> row``.
#:
#: **The key is composite because the same ``code`` legitimately exists once per
#: adapter.**  ``node.list`` is served by gen, civil *and* cdn — that is what
#: ``ux_capability(adapter_code, capability_code)`` is for, and it is what the
#: multi-product requirement needs.
#:
#: This table used to be keyed by ``code`` alone.  The consequence was measured,
#: not theorised: a **Civil-only deployment could not call anything** (every
#: capability looked up ``midas_gen``, which was not registered), and with all
#: three products registered a call without an explicit adapter **silently went
#: to Gen**.  Both are data-corruption paths, so the key is the fix.
_TABLE: dict[tuple[str, str], Capability] = {
    _key(row.adapter_code, row.code): row for row in _ROWS
}

#: V2.1 §16.2: resolution failure -> closed-set code.  An unknown
#: ``(tool, action, resource)`` combination is always this one.
_NOT_SUPPORTED: Final[ErrorCode] = ErrorCode.CAPABILITY_NOT_SUPPORTED


def capability_table(adapter_code: str | None) -> dict[str, Capability]:
    """``code -> Capability`` for **one** adapter (V2.1 §16.1).

    ``adapter_code`` is required.  ``None`` selects the **platform-owned** rows
    (``midas_task``), *not* every adapter — there is deliberately no
    all-adapters form, because a dict keyed by ``code`` alone cannot hold the
    same code twice and that limitation is precisely what this change removes.
    Use :func:`capability_rows` for the whole table.
    """
    owner = adapter_code or ""
    return {code: row for (owner_key, code), row in _TABLE.items() if owner_key == owner}


def capability_rows() -> tuple[Capability, ...]:
    """Every row, declaration order — across **all** adapters.

    The only correct way to enumerate the whole table: the same ``code`` may
    appear several times, once per adapter.
    """
    return tuple(_TABLE.values())


def is_enabled(code: str, adapter_code: str | None = None) -> bool:
    """``capabilities.enabled`` for ``code`` (V2.1 §16.1 / §16.2).

    ``DISABLED_CAPABILITIES`` holds bare codes, so a code disabled here is
    disabled for every adapter that serves it.  That is deliberate: the set is a
    small hardcoded switch, not the DB column, and per-adapter disabling is what
    ``capabilities.enabled`` in the database is for.
    """
    return code not in DISABLED_CAPABILITIES


def register_capability(capability: Capability, *, replace: bool = False) -> Capability:
    """Add or replace one row (Phase 2: the DB loader calls this).

    The slot is ``(capability.adapter_code or "", capability.code)``, so the same
    code may be registered once **per adapter** — ``node.list`` for gen, civil
    and cdn are three rows, not one row overwritten twice.

    Raises ``RESOURCE_CONFLICT`` (总纲 §4.4.2) when that slot is taken, unless
    ``replace=True`` — same contract as ``AdapterRegistry.register``.
    """
    slot = _key(capability.adapter_code, capability.code)
    if slot in _TABLE and not replace:
        raise AdapterError(
            ErrorCode.RESOURCE_CONFLICT,
            f"capability code={capability.code!r} 在 adapter="
            f"{capability.adapter_code!r} 下已存在；重复注册需显式 replace=True"
            "（V2.1 §16.1：ux_capability 唯一键是 (adapter_code, capability_code)）",
            details={"code": capability.code, "adapter_code": capability.adapter_code},
        )
    if capability.dispatch not in DISPATCH_HINTS:
        raise AdapterError(
            ErrorCode.VALIDATION_ERROR,
            f"未知的 dispatch={capability.dispatch!r}；合法取值：{sorted(DISPATCH_HINTS)}",
            details={"code": capability.code},
        )
    _TABLE[slot] = capability
    return capability


def unregister_capability(code: str, adapter_code: str | None = None) -> None:
    """Drop one row for one adapter.  Raises ``RESOURCE_NOT_FOUND`` when absent.

    ``adapter_code`` defaults to ``None`` — the platform-owned slot — so a caller
    that means an adapter-served capability must say which.
    """
    slot = _key(adapter_code, code)
    if slot not in _TABLE:
        raise AdapterError(
            ErrorCode.RESOURCE_NOT_FOUND,
            f"capability code={code!r} 在 adapter={adapter_code!r} 下不存在",
            details={"code": code, "adapter_code": adapter_code},
        )
    del _TABLE[slot]


def reset_capabilities() -> None:
    """Rebuild the table from the static declaration (test / reload helper)."""
    _TABLE.clear()
    _TABLE.update({_key(row.adapter_code, row.code): row for row in _ROWS})


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------
def _normalise(value: str | None) -> str:
    return (value or "").strip().lower().replace("-", "_")


#: ``midas_execute`` actions whose ``resource`` may be omitted; the dispatcher
#: fills the canonical resource so the lookup is total (V2.1 §9.2 allows
#: ``resource: null``).
def _default_execute_resources() -> dict[str, str]:
    """``action -> canonical resource``, **first declaration wins**.

    ``export`` is declared twice (``file.export`` and ``result.export``), so a
    bare ``action=export`` has to be resolved by a stated rule rather than by
    dictionary ordering: the first row is the default and ``resource=result``
    selects the table export explicitly.  Silently letting the last row win would
    have made ``action=export`` mean "write a result table" — a surprise with a
    filesystem side effect on the NX host.
    """
    defaults: dict[str, str] = {}
    for row in _EXECUTE_ROWS:
        defaults.setdefault(row[1], row[0])
    return defaults


_EXECUTE_DEFAULT_RESOURCE: Final[dict[str, str]] = _default_execute_resources()


def resolve(
    tool: str,
    action: str,
    resource: str | None = None,
    *,
    adapter_code: str | None = None,
) -> Capability:
    """Resolve one ``(tool, action, resource)`` **for one adapter**.

    ``resource`` carries the ``target`` value for ``midas_query`` (裁决 C-7) and
    may be ``None`` for ``midas_execute`` / ``midas_task``.

    ``adapter_code`` is the adapter the **call must go to** — derived from the
    selected ``midas_clients`` row, never from the capability.  Routing runs
    instance → adapter → capability; this function is the third step, so it can
    only answer "does *this* adapter serve that combination?".  ``None`` selects
    the platform-owned rows (``midas_task``).

    Raises ``CAPABILITY_NOT_SUPPORTED`` (总纲 §4.4.4) — V2.1 §16.2 forbids
    falling back to a direct endpoint call or skipping the capability check.
    """
    tool_name = (tool or "").strip()
    act = _normalise(action)
    res = _normalise(resource)

    if tool_name == TOOL_QUERY:
        code = f"{res}.{act}"
    elif tool_name == TOOL_MODEL:
        code = f"{res}.{act}"
    elif tool_name == TOOL_EXECUTE:
        code = f"{res or _EXECUTE_DEFAULT_RESOURCE.get(act, '')}.{act}"
    elif tool_name == TOOL_TASK:
        code = f"task.{act}"
    else:
        raise AdapterError(
            _NOT_SUPPORTED,
            f"未知的 MCP tool={tool!r}；本平台只暴露 {list(TOOL_NAMES)}（v1.2 §37）",
            details={"tool": tool, "action": action, "resource": resource},
        )

    row = _TABLE.get(_key(adapter_code, code))
    if row is None or row.tool != tool_name:
        raise AdapterError(
            _NOT_SUPPORTED,
            f"adapter={adapter_code!r} 下没有 ({tool_name}, action={action!r}, "
            f"resource={resource!r}) 对应的 Capability；"
            "V2.1 §16.2 规定解析失败一律返回 CAPABILITY_NOT_SUPPORTED，"
            "**禁止**回退到「直连 Endpoint」或「跳过能力校验」。"
            f"该 adapter 的合法组合：{resources_for(tool_name, adapter_code=adapter_code)}"
            f" × {actions_for(tool_name, adapter_code=adapter_code)}",
            details={
                "tool": tool_name,
                "action": action,
                "resource": resource,
                "code": code,
                "adapter_code": adapter_code,
            },
        )
    return row


def resources_for(tool: str, *, adapter_code: str | None = None) -> list[str]:
    """Distinct resources of ``tool``, sorted (feeds the schema's resource enum).

    ``adapter_code=None`` spans every adapter — the schema enums describe what
    the *tool* accepts, and the per-adapter narrowing happens at resolution.
    Pass an adapter to see exactly what that instance supports.
    """
    owner = None if adapter_code is None else (adapter_code or "")
    return sorted(
        {
            row.resource
            for (owner_key, _code), row in _TABLE.items()
            if row.tool == tool and (owner is None or owner_key == owner)
        }
    )


def actions_for(
    tool: str, resource: str | None = None, *, adapter_code: str | None = None
) -> list[str]:
    """Distinct actions of ``tool`` (optionally one resource), sorted.

    ``resource=None`` returns the union across resources — exactly the tool's
    ``action`` enum in V2.1 §7.2 / §8.2 / §9.2 / §10.2.
    """
    wanted = _normalise(resource)
    owner = None if adapter_code is None else (adapter_code or "")
    return sorted(
        {
            row.action
            for (owner_key, _code), row in _TABLE.items()
            if row.tool == tool
            and (owner is None or owner_key == owner)
            and (resource is None or row.resource == wanted)
        }
    )


# ---------------------------------------------------------------------------
# Serialisation (``midas_query target=capabilities``)
# ---------------------------------------------------------------------------
def capability_payload(capability: Capability) -> dict[str, Any]:
    """LLM-safe projection of one row.

    ``request_schema`` is deliberately **excluded**: it is a second-validation
    artefact (V2.1 §6.2), not something the model needs in a capability listing.
    """
    return {
        "code": capability.code,
        "tool": capability.tool,
        "resource": capability.resource,
        "action": capability.action,
        "adapter_code": capability.adapter_code,
        "interface_code": capability.interface_code,
        "method": capability.method,
        "endpoint": capability.endpoint,
        "request_wrapper": capability.request_wrapper,
        "response_root_key": capability.response_root_key,
        "outer_key_means": capability.outer_key_means,
        "outer_key_kind": capability.outer_key_kind,
        "enabled": is_enabled(capability.code),
        "notes": capability.notes,
    }


def task_type_values() -> list[str]:
    """``tasks.type`` closed values (V2.1 §26.2) — for the ``midas_task`` schema."""
    return list(TASK_TYPE_VALUES)


def task_status_values() -> list[str]:
    """``tasks.status`` closed values (总纲 §4.2.1)."""
    return list(TASK_STATUS_VALUES)


def with_derived_outer_keys(
    rows: Sequence[Capability] | None = None,
) -> list[Capability]:
    """Re-derive ``outer_key_means`` / ``outer_key_kind`` from the adapter.

    Only needed when the adapter's §4.1 table changes at runtime; the static
    build already applies it, so this is a Phase 2 reload helper.
    """
    source = rows if rows is not None else _TABLE.values()
    out: list[Capability] = []
    for row in source:
        if row.endpoint is None:
            out.append(row)
            continue
        out.append(
            replace(
                row,
                outer_key_means=outer_key_means_for(row.endpoint),
                outer_key_kind=outer_key_kind_for(row.endpoint),
            )
        )
    return out
