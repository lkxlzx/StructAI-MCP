"""Tool ① ``midas_query`` — V2.1 §7.

Reads only.  ``target`` selects what is being read (裁决 C-7: ``capabilities``
is a **target**, never an action); ``action`` is one of
``get | list | search | count | inspect``.

Routing (V2.1 §16 / §17):

============================  =========================================
``capability.dispatch``       适配器调用
============================  =========================================
``query``                     ``adapter.query(QueryRequest)``
``introspect``                ``adapter.introspect(res)`` (§5 自省)
``get_table``                 ``adapter.get_table(...)`` (§11.5.6)
``local_capabilities``        本平台的 Capability 表（不发 MIDAS 请求）
``model_overview``            平台侧模型快照（无单一 MIDAS 端点）
============================  =========================================

The JSON Schema is **generated** from :mod:`app.mcp.capabilities` — the
``target`` / ``action`` enums and the per-target ``query`` filters all come from
that one table (V2.1 §6.1 + 总纲 §0.4), so they cannot drift.

.. note::
   V2.1 §7.2 writes the ``query`` property as ``oneOf`` over the per-resource
   filters.  ``oneOf`` is **unsatisfiable** there: ``{}`` matches every branch
   (and so does any key two resources share, e.g. ``ids`` / ``name``), which
   makes "exactly one" impossible.  This schema uses ``anyOf`` instead and lets
   the dispatcher apply the *single* matching branch through
   ``capability.request_schema`` — which is precisely the second-validation
   mechanism V2.1 §6.2 / §9.3 mandates.  The intent of 裁决 B-4 (no free-form
   object) is preserved; see the module report for the contradiction.
"""

from typing import TYPE_CHECKING, Any, Final, Mapping

from app.adapters.base import AdapterResult, QueryRequest
from app.core.errors import ErrorCode
from app.mcp.capabilities import (
    DISPATCH_GET_TABLE,
    DISPATCH_INTROSPECT,
    DISPATCH_LOCAL_CAPABILITIES,
    DISPATCH_MODEL_OVERVIEW,
    DISPATCH_QUERY,
    TOOL_QUERY,
    actions_for,
    capability_payload,
    capability_rows,
    is_enabled,
    query_filter_schemas,
    resolve,
    resources_for,
)
from app.mcp.context import (
    DispatchContext,
    adapter_method,
    as_dict,
    options_of,
    require_adapter,
    timeout_of,
)

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from app.adapters.base import MidasAdapter

__all__ = [
    "TOOL_NAME",
    "TITLE",
    "DESCRIPTION",
    "SCHEMA",
    "build_schema",
    "handle",
    "model_snapshot",
    "read_result_table",
]

TOOL_NAME: Final[str] = TOOL_QUERY
TITLE: Final[str] = "StructAI MIDAS Query"
DESCRIPTION: Final[str] = (
    "只读查询 MIDAS 软件状态、当前连接、软件能力、模型对象与计算结果。"
    "target 选择查询对象（capabilities 是 target，不是 action —— 裁决 C-7）；"
    "action 取 get / list / search / count / inspect。"
    "inspect 走 GET /info/db/<RES> 自省（对接规范 §5.1：只为 /db/* 提供）。"
    "本工具不写模型；写操作请用 midas_model。"
)

#: V2.1 §7.2's ``result_type`` -> (MIDAS ``TABLE_TYPE``, default ``COMPONENTS``).
#: ``COMPONENTS`` is **mandatory** (对接规范 §11.5.6: omitting it returns
#: ``200 {"message":""}``, which looks like "no results" but is an incomplete
#: request), so a default must always exist.
_RESULT_TABLES: Final[dict[str, tuple[str, tuple[str, ...]]]] = {
    "displacement": (
        "Displacement",
        ("Node", "Load", "DX", "DY", "DZ", "RX", "RY", "RZ"),
    ),
    "reaction": ("Reaction", ("Node", "Load", "FX", "FY", "FZ", "MX", "MY", "MZ")),
    "force": (
        "Beam Force",
        (
            "Elem",
            "Load",
            "Part",
            "Axial",
            "Shear-y",
            "Shear-z",
            "Torsion",
            "Moment-y",
            "Moment-z",
        ),
    ),
    "stress": (
        "Beam Stress",
        ("Elem", "Load", "Part", "Sig-xx", "Sig-yy", "Sig-zz", "Sig-xy", "Sig-yz", "Sig-zx"),
    ),
    "mode": ("Eigenvalue", ("Mode", "Node", "UX", "UY", "UZ", "RX", "RY", "RZ")),
    "story_drift": ("Story Drift", ("Story", "Load", "Drift", "Drift Ratio")),
}

#: Live-verified output unit / style for result tables (tests/live/
#: test_adapter_live.py; 对接规范 §11.5.6).
_RESULT_UNIT: Final[dict[str, str]] = {"FORCE": "kN", "DIST": "mm"}
_RESULT_STYLES: Final[dict[str, Any]] = {"FORMAT": "Fixed", "PLACE": 6}


# ---------------------------------------------------------------------------
# schema
# ---------------------------------------------------------------------------
def build_schema() -> dict[str, Any]:
    """Build the §7.2 schema from the capability table (never hand-written)."""
    filters = query_filter_schemas()
    branches: list[dict[str, Any]] = [{"type": "null"}]
    for target in resources_for(TOOL_QUERY):
        branch = filters.get(target)
        if branch is not None:
            branches.append(branch)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"structai://mcp/v2.1/tools/{TOOL_QUERY}",
        "title": TITLE,
        "description": DESCRIPTION,
        "type": "object",
        "additionalProperties": False,
        "required": ["target", "action"],
        "properties": {
            "target": {
                "type": "string",
                "enum": resources_for(TOOL_QUERY),
                "description": (
                    "查询对象。枚举由 app.mcp.capabilities 生成（V2.1 §6.1）；"
                    "capabilities 只作为 target 取值（裁决 C-7）。"
                ),
            },
            "action": {
                "type": "string",
                "enum": actions_for(TOOL_QUERY),
                "description": "查询动作（V2.1 §6.3）。",
            },
            "id": {
                "type": ["string", "integer", "null"],
                "description": "单条查询的外层键（MIDAS Assign 外层键语义见对接规范 §4.1）。",
            },
            "query": {
                "type": ["object", "null"],
                "anyOf": branches,
                "description": (
                    "过滤条件。V2.1 §7.2 用 oneOf 分资源收紧，但 {} 会命中所有分支、"
                    "任何跨资源同名字段（ids/name）也会命中多支，oneOf 无法满足；"
                    "此处用 anyOf，再由 Capability.request_schema 按 target 做二次校验"
                    "（V2.1 §6.2 / §9.3）。MIDAS 没有服务端过滤（对接规范 §2.5.1），"
                    "过滤在本平台完成。"
                ),
            },
            "fields": {
                "type": ["array", "null"],
                "items": {"type": "string"},
                "description": (
                    "返回列；对 target=result 即 POST /post/TABLE 的 COMPONENTS。"
                    "对接规范 §11.5.6：COMPONENTS 必需，省略时上游返回 200 "
                    '{"message":""}（看似无结果，实为请求不完整）。'
                ),
            },
            "page": {"type": "integer", "minimum": 1, "default": 1},
            "page_size": {
                "type": "integer",
                "minimum": 1,
                "maximum": 500,
                "default": 100,
            },
            "client_id": {
                "type": ["integer", "null"],
                "description": "midas_clients.id（裁决 N-6）。",
            },
            "adapter": {
                "type": ["string", "null"],
                "description": "adapters.code，例如 midas_gen（V2.1 §16 / §21）。",
            },
            "include_metadata": {"type": "boolean", "default": False},
        },
    }


SCHEMA: dict[str, Any] = build_schema()


# ---------------------------------------------------------------------------
# handler
# ---------------------------------------------------------------------------
async def handle(
    arguments: Mapping[str, Any], context: DispatchContext
) -> AdapterResult:
    """Route one validated ``midas_query`` call (V2.1 §7)."""
    capability = context.capability
    dispatch = capability.dispatch

    if dispatch == DISPATCH_LOCAL_CAPABILITIES:
        return _capabilities_result(arguments, context)
    if dispatch == DISPATCH_MODEL_OVERVIEW:
        adapter = require_adapter(context)
        return await model_snapshot(adapter, context=context)

    adapter = require_adapter(context)
    if dispatch == DISPATCH_INTROSPECT:
        return await adapter.introspect(capability.adapter_resource)
    if dispatch == DISPATCH_GET_TABLE:
        return await read_result_table(arguments, context, adapter)
    if dispatch == DISPATCH_QUERY:
        return await _read_records(arguments, context, adapter)
    raise AssertionError(  # pragma: no cover - the table is a closed set
        f"midas_query 收到未知 dispatch={dispatch!r}"
    )


# ---------------------------------------------------------------------------
# local capability listing (裁决 C-7)
# ---------------------------------------------------------------------------
def _capabilities_result(
    arguments: Mapping[str, Any], context: DispatchContext
) -> AdapterResult:
    """``target=capabilities`` — the platform's own capability table.

    Answers from :mod:`app.mcp.capabilities` rather than from the adapter, because
    V2.1 §16.1 makes ``capabilities`` + ``tool_interfaces`` the authoritative
    source and the adapter's ``capabilities()`` mirror is only a cross-check.
    """
    query = as_dict(arguments.get("query"))
    wanted_adapter = query.get("adapter") or arguments.get("adapter")
    wanted_resource = query.get("resource")
    wanted_action = query.get("action")
    wanted_enabled = query.get("enabled")

    rows = []
    for row in capability_rows():
        if wanted_adapter is not None and row.adapter_code != wanted_adapter:
            continue
        if wanted_resource is not None and row.resource != wanted_resource:
            continue
        if wanted_action is not None and row.action != wanted_action:
            continue
        if wanted_enabled is not None and is_enabled(row.code) != bool(wanted_enabled):
            continue
        rows.append(capability_payload(row))

    payload: dict[str, Any] = {
        "total": len(rows),
        "items": rows,
        "adapters": sorted({row["adapter_code"] for row in rows if row["adapter_code"]}),
        "tools": sorted({row["tool"] for row in rows}),
    }
    if arguments.get("include_metadata"):
        metadata = context.registry.metadata_of(
            str(wanted_adapter or context.capability.adapter_code or "")
        )
        payload["metadata"] = metadata.to_db_payload() if metadata is not None else None
    return AdapterResult.ok(
        payload,
        warnings=[
            "capability 清单来自平台自身的 capabilities 表（V2.1 §16.1），"
            "不是 MIDAS 的应答；对接规范 §2.5.1 证明 MIDAS 没有能力发现端点。"
        ],
    )


# ---------------------------------------------------------------------------
# /db records
# ---------------------------------------------------------------------------
async def _read_records(
    arguments: Mapping[str, Any],
    context: DispatchContext,
    adapter: "MidasAdapter",
) -> AdapterResult:
    """``GET /db/<RES>`` through ``adapter.query()`` (V2.1 §7.2)."""
    capability = context.capability
    query = as_dict(arguments.get("query"))
    identifier = arguments.get("id")
    if identifier is not None:
        query = {**query, "ids": [identifier]}

    request = QueryRequest(
        request_id=context.request_id,
        client_id=context.midas_client_id or 0,
        action=capability.action,
        resource=None,
        payload=arguments.get("query"),
        options=options_of(arguments),
        timeout_seconds=timeout_of(arguments),
        target=capability.adapter_resource,
        query=query or None,
        page=int(arguments.get("page") or 1),
        page_size=int(arguments.get("page_size") or 100),
    )
    result = await adapter.query(request)
    if not result.success:
        return result

    data = result.data if isinstance(result.data, dict) else {}
    # 总纲 §4.6.1: MCP 层用单数资源名；适配器回的是 MIDAS 资源名（/db/PJCF -> PJCF）。
    data = {**data, "resource": capability.resource}

    # Only a ``/db/*`` table answers in the paginated {total, items} shape; the
    # local targets (server / client) return their own payloads unchanged.
    is_table = bool(
        capability.endpoint and capability.endpoint.lower().startswith("/db/")
    )
    if is_table and capability.action == "count":
        result.data = {
            "resource": capability.resource,
            "count": data.get("total", 0),
            "query": query or None,
        }
        return result

    if is_table and capability.action == "get":
        items = data.get("items") or []
        if not items:
            return AdapterResult.failed(
                ErrorCode.RESOURCE_NOT_FOUND,
                f"{capability.resource} 中找不到 id={identifier!r}"
                "（总纲 §4.4.2）。MIDAS 没有服务端过滤（对接规范 §2.5.1），"
                "本判断在本平台完成；若确认存在，请检查外层键语义（对接规范 §4.1）。",
                warnings=list(result.warnings),
                raw_status=result.raw_status,
                raw_response=result.raw_response,
                latency_ms=result.latency_ms,
            )
        result.data = {
            "resource": capability.resource,
            "endpoint": data.get("endpoint"),
            "item": items[0],
            "total": data.get("total", len(items)),
        }
        return result

    result.data = data
    return result


# ---------------------------------------------------------------------------
# /post/TABLE
# ---------------------------------------------------------------------------
async def read_result_table(
    arguments: Mapping[str, Any],
    context: DispatchContext,
    adapter: "MidasAdapter",
    *,
    export_path: str | None = None,
) -> AdapterResult:
    """``POST /post/TABLE`` through ``adapter.get_table()`` (对接规范 §11.5.6).

    Public because ``midas_execute action=result.export`` (a different tool) ends
    up in the same call; keeping one implementation keeps one set of §11.5.6
    guards.
    """
    query = as_dict(arguments.get("query"))
    result_type = str(query.get("result_type") or "displacement").lower()
    known = _RESULT_TABLES.get(result_type)
    if known is None:
        return AdapterResult.failed(
            ErrorCode.VALIDATION_ERROR,
            f"未知的 result_type={result_type!r}；V2.1 §7.2 的取值："
            f"{sorted(_RESULT_TABLES)}。对接规范 §11.5.6：错误的 TABLE_TYPE 返回 400 "
            "+ 被服务端截断的错误信息，因此这里在发请求前拦下。",
        )
    table_type, default_components = known

    fields = arguments.get("fields")
    if isinstance(fields, (list, tuple)) and fields:
        components = [str(item) for item in fields]
    else:
        components = list(default_components)

    component = query.get("component")
    if component:
        if str(component) not in components:
            components.append(str(component))
            context.warn(
                f"query.component={component!r} 已追加到 COMPONENTS；"
                "对接规范 §11.5.6：COMPONENTS 是必需的，省略时上游返回 200 "
                '{"message":""}，看起来像「无结果」，实则请求不完整。'
            )

    load_case = query.get("load_case") or query.get("load_combination")
    load_case_names = [str(load_case)] if load_case else None
    if query.get("envelope") or query.get("top_n"):
        context.warn(
            "envelope / top_n 需要包络组合与排序语义，Phase 1 未实现；"
            "当前返回该 TABLE_TYPE 的原始表（对接规范 §11.5.6：禁止把「合法空结果」"
            "与「请求缺参数」混为一谈）。"
        )

    get_table = adapter_method(adapter, "get_table")
    return await get_table(
        table_type,
        components,
        load_case_names=load_case_names,
        unit=dict(_RESULT_UNIT),
        styles=dict(_RESULT_STYLES),
        export_path=export_path,
        timeout_seconds=timeout_of(arguments),
    )


# ---------------------------------------------------------------------------
# model snapshot (``target=model`` and ``midas_execute action=sync``)
# ---------------------------------------------------------------------------
#: Counted tables of the platform-side model snapshot.
_SNAPSHOT_COUNTS: Final[tuple[str, ...]] = (
    "node",
    "element",
    "material",
    "section",
    "boundary",
    "load_case",
    "load",
    "group",
)


async def model_snapshot(
    adapter: "MidasAdapter", *, context: DispatchContext
) -> AdapterResult:
    """Read the model state back — the only safe step after a write timeout.

    对接规范 §3.5 第 5 条 / V2.1 §26.5: 「超时 ≠ 回滚 …… 超时后必须先读回模型状态」.
    There is no single MIDAS endpoint that describes "the model", so this reads
    ``/db/UNIT`` and ``/db/STYP`` in full and counts the remaining model tables.
    """
    data: dict[str, Any] = {"unit": None, "structure_type": None, "counts": {}}
    warnings: list[str] = [
        "模型快照由多次 GET 组成：MIDAS 没有「模型概览」端点（对接规范 §2.5.1："
        "官方文档未定义 API 层的查询/聚合能力）。"
    ]

    for name in ("unit", "structure_type"):
        capability = resolve(TOOL_QUERY, "list", name)
        result = await adapter.query(
            QueryRequest(
                request_id=context.request_id,
                client_id=context.midas_client_id or 0,
                action="list",
                resource=None,
                payload=None,
                options={},
                timeout_seconds=timeout_of(context.arguments),
                target=capability.adapter_resource,
                query=None,
                page=1,
                page_size=1,
            )
        )
        if result.success and isinstance(result.data, dict):
            items = result.data.get("items") or []
            data[name] = items[0] if items else None
        else:
            warnings.append(
                f"读取 {name} 失败：{result.error_code} {result.error_message}"
            )

    for name in _SNAPSHOT_COUNTS:
        capability = resolve(TOOL_QUERY, "count", name)
        result = await adapter.query(
            QueryRequest(
                request_id=context.request_id,
                client_id=context.midas_client_id or 0,
                action="count",
                resource=None,
                payload=None,
                options={},
                timeout_seconds=timeout_of(context.arguments),
                target=capability.adapter_resource,
                query=None,
                page=1,
                page_size=1,
            )
        )
        if result.success and isinstance(result.data, dict):
            data["counts"][name] = result.data.get("total", 0)
        else:
            data["counts"][name] = None
            warnings.append(
                f"统计 {name} 失败：{result.error_code} {result.error_message}"
            )

    data["resource"] = "model"
    return AdapterResult.ok(data, warnings=warnings)
