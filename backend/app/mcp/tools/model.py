"""Tool ② ``midas_model`` — V2.1 §8.

CRUD over the MIDAS model, plus a dry-run ``validate``.

The one rule that is easy to get wrong and expensive to get wrong
---------------------------------------------------------------
对接规范 §3.5 第 1 条 / §11.5.1 (实机复现): ``DELETE {endpoint}`` **with an
``Assign`` body** ignores every id and **wipes the whole table** (on ``/db/NODE``
it also removes the elements hanging off those nodes).  The only per-record form
is the undocumented ``DELETE {endpoint}/{id}``.

Therefore ``action=delete`` here resolves ids and calls the adapter's per-id
``delete()``; the ``Assign``-body form is **unreachable**:

* the capability row for ``delete`` has ``dispatch="delete"`` (V2.1 §17.5 第 1 条:
  「``Assign`` 形式的批量 ``DELETE`` 必须从 Interface 注册表中移除」);
* a payload that looks like ``{"Assign": {...}}`` is refused with
  ``VALIDATION_ERROR`` before any HTTP call;
* the adapter itself refuses a ``dict`` payload a second time
  (``_coerce_ids``), so even a future routing mistake cannot reach the trap.

``/db/UNIT`` / ``/db/STYP`` expose no ``create``: 对接规范 §3.3 — 「新文件必需
数据」 只能用 ``GET`` / ``PUT``，``POST`` 不生效.
"""

from typing import TYPE_CHECKING, Any, Final, Mapping

from app.adapters.base import AdapterResult, ModelRequest
from app.adapters.errors import AdapterError
from app.core.errors import ErrorCode
from app.mcp.capabilities import (
    DISPATCH_DELETE,
    DISPATCH_MODEL,
    TOOL_MODEL,
    actions_for,
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

__all__ = ["TOOL_NAME", "TITLE", "DESCRIPTION", "SCHEMA", "build_schema", "handle"]

TOOL_NAME: Final[str] = TOOL_MODEL
TITLE: Final[str] = "StructAI MIDAS Model"
DESCRIPTION: Final[str] = (
    "对 MIDAS 模型做统一 CRUD 与校验：create / read / update / delete / upsert / validate。"
    "resource 取 MCP 单数资源名（总纲 §4.6.1），枚举由平台 Capability 表生成（V2.1 §6.1）。"
    "delete **只**逐 id 执行 DELETE {endpoint}/{id}：带 Assign 体的 DELETE 会清空整张表"
    "（对接规范 §3.5 第 1 条 / §11.5.1），因此该形式在本工具中不可达。"
    "data 使用 MIDAS 字段名原样传递；upsert 由适配器自行实现次序（§11.5.3）。"
)

#: 对接规范 §3.5 第 12 条: these resources refuse a write unless the caller
#: supplies every mandatory field explicitly.  Mirrors
#: ``app.adapters.midas_gen.adapter.MANDATORY_WRITE_FIELDS`` for the warning text.
_WRITE_GUARDS: Final[dict[str, str]] = {
    "load": (
        "🔴 对接规范 §4.1 / §11.6：/db/CNLD 的 Assign 外层键是**节点号**，"
        "ITEMS[].ID 只是**序号**。写错不会报错 —— 分析照常返回 command complete，"
        "而反力看似正确、内力与位移全零。"
    ),
}


# ---------------------------------------------------------------------------
# schema
# ---------------------------------------------------------------------------
def build_schema() -> dict[str, Any]:
    """Build the §8.2 schema from the capability table (never hand-written)."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"structai://mcp/v2.1/tools/{TOOL_MODEL}",
        "title": TITLE,
        "description": DESCRIPTION,
        "type": "object",
        "additionalProperties": False,
        "required": ["action", "resource"],
        "properties": {
            "action": {
                "type": "string",
                "enum": actions_for(TOOL_MODEL),
                "description": "模型动作（V2.1 §6.3）。",
            },
            "resource": {
                "type": "string",
                "enum": resources_for(TOOL_MODEL),
                "description": (
                    "MCP 单数资源名（总纲 §4.6.1）。枚举由 app.mcp.capabilities 生成，"
                    "**不是** V2.0 的九个模型资源固定表：真实 MIDAS API 才是权威"
                    "（V2.1 §6.3），因此 load_case / structure_type / unit / project "
                    "都是一等资源。"
                ),
            },
            "id": {
                "type": ["string", "integer", "null"],
                "description": "单条记录的外层键（对接规范 §4.1：语义随端点而异）。",
            },
            "ids": {
                "type": ["array", "null"],
                "items": {"type": ["string", "integer"]},
                "description": (
                    "批量外层键。delete 会**逐 id** 发一次 DELETE {endpoint}/{id}"
                    "（对接规范 §3.5 第 1 条）。"
                ),
            },
            "data": {
                "type": ["object", "array", "null"],
                "description": (
                    "写入载荷，字段名用 MIDAS 名（V2.1 §22 / §23：canonical ⇄ MIDAS "
                    "映射属于 mapper.py）。形状见对接规范 §4 的四类："
                    "A 扁平字段 / B 容器+ITEMS / C 嵌套参数数组 / D 多层嵌套。"
                    "按 resource 的二次校验由 Capability.request_schema 执行"
                    "（V2.1 §6.2 裁决 B-4）。"
                ),
            },
            "options": {
                "type": ["object", "null"],
                "additionalProperties": False,
                "properties": {
                    "validate_before_write": {"type": "boolean", "default": True},
                    "validate_after_write": {"type": "boolean", "default": True},
                    "transactional": {"type": "boolean", "default": True},
                    "dry_run": {"type": "boolean", "default": False},
                    "timeout_seconds": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 86400,
                    },
                },
                "description": (
                    "V2.1 §25.1 写操作选项。transactional 只做补偿追踪："
                    "MIDAS 侧**没有事务**（对接规范 §3.5 第 5 条 / V2.1 §25.3）。"
                ),
            },
            "client_id": {"type": ["integer", "null"]},
            "adapter": {"type": ["string", "null"]},
        },
    }


SCHEMA: dict[str, Any] = build_schema()


# ---------------------------------------------------------------------------
# handler
# ---------------------------------------------------------------------------
async def handle(
    arguments: Mapping[str, Any], context: DispatchContext
) -> AdapterResult:
    """Route one validated ``midas_model`` call (V2.1 §8)."""
    adapter = require_adapter(context)
    if context.capability.dispatch == DISPATCH_DELETE:
        return await _delete(arguments, context, adapter)
    if context.capability.dispatch == DISPATCH_MODEL:
        return await _model(arguments, context, adapter)
    raise AssertionError(  # pragma: no cover - the table is a closed set
        f"midas_model 收到未知 dispatch={context.capability.dispatch!r}"
    )


# ---------------------------------------------------------------------------
# create / read / update / upsert / validate
# ---------------------------------------------------------------------------
async def _model(
    arguments: Mapping[str, Any],
    context: DispatchContext,
    adapter: "MidasAdapter",
) -> AdapterResult:
    """``adapter.model(ModelRequest)`` (V2.1 §8 / §25.1)."""
    capability = context.capability
    options = options_of(arguments)
    action = capability.action

    if action in ("create", "update", "upsert"):
        guard = _WRITE_GUARDS.get(capability.resource)
        if guard:
            context.warn(guard)
        context.warn(
            "对接规范 §3.5 第 5 条 / V2.1 §26.5：写操作**禁止自动重试** —— "
            "超时 ≠ 回滚，超时后必须先读回模型状态（midas_execute action=sync）。"
        )
    elif action == "read":
        context.warn(
            "midas_model action=read 返回整表（适配器内分页，page_size 上限 500）；"
            "需要过滤/分页请用 midas_query（V2.1 §7：MIDAS 没有服务端过滤，"
            "对接规范 §2.5.1）。"
        )

    request = ModelRequest(
        request_id=context.request_id,
        client_id=context.midas_client_id or 0,
        action=action,
        # V2.1 §17.2 存 MCP 单数名，§17.3 的 Interface 映射把它解析成真实端点；
        # 适配器收到端点后再 normalise 回去（midas_gen/adapter.py: model()）。
        resource=capability.endpoint or capability.resource,
        payload=arguments.get("data"),
        options=options,
        timeout_seconds=timeout_of(arguments),
        data=arguments.get("data"),
    )
    return await adapter.model(request)


# ---------------------------------------------------------------------------
# delete — 对接规范 §3.5 第 1 条
# ---------------------------------------------------------------------------
def _resolve_delete_ids(arguments: Mapping[str, Any]) -> list[Any]:
    """Ids for a per-record delete, or ``VALIDATION_ERROR``.

    Refuses the ``Assign``-body form **first and unconditionally**: 对接规范
    §11.5.1 实机复现 shows the upstream ignores the ids in that body and clears
    the table, so a payload carrying ``Assign`` is never something we forward.
    """
    data = arguments.get("data")
    if isinstance(data, Mapping) and "Assign" in data:
        raise AdapterError(
            ErrorCode.VALIDATION_ERROR,
            "拒绝执行：DELETE 携带 Assign 体会**清空整张表**并完全忽略传入的 id"
            "（对接规范 §3.5 第 1 条 / §11.5.1 实机复现：请求里只有 id 1，响应却回显 1 和 3，"
            "随后整表清空；对 /db/NODE 还会连带删掉挂在其上的单元）。"
            "单条删除请用 ids=[<id>]（本工具会逐 id 发 DELETE {endpoint}/{id}）；"
            "整表清空只能显式调用适配器的 delete_all(resource, confirm=True)。",
            details={"endpoint": arguments.get("resource"), "received": "Assign body"},
        )

    ids = arguments.get("ids")
    if isinstance(ids, (list, tuple)) and ids:
        return list(ids)
    identifier = arguments.get("id")
    if identifier is not None:
        return [identifier]
    if isinstance(data, Mapping):
        inner_ids = data.get("ids")
        if isinstance(inner_ids, (list, tuple)) and inner_ids:
            return list(inner_ids)
        inner_id = data.get("id")
        if inner_id is not None:
            return [inner_id]
    if isinstance(data, (list, tuple)) and data:
        collected: list[Any] = []
        for index, item in enumerate(data, start=1):
            if not isinstance(item, Mapping):
                raise AdapterError(
                    ErrorCode.VALIDATION_ERROR,
                    f"data[{index}] 必须是对象，收到 {type(item).__name__}",
                )
            key = item.get("id", item.get("ID"))
            if key is None:
                raise AdapterError(
                    ErrorCode.VALIDATION_ERROR,
                    f"data[{index}] 缺少 'id'，无法确定要删除的外层键"
                    "（对接规范 §4.1：外层键语义随端点而异，不能假设统一）。",
                )
            collected.append(key)
        return collected
    raise AdapterError(
        ErrorCode.VALIDATION_ERROR,
        "delete 需要至少一个 id：请传 ids=[...]、id=... 或 data 中的 id/ids。"
        "注意 **不能**用 Assign 体形式（对接规范 §3.5 第 1 条：它会清空整张表）。",
        details={"resource": arguments.get("resource")},
    )


async def _delete(
    arguments: Mapping[str, Any],
    context: DispatchContext,
    adapter: "MidasAdapter",
) -> AdapterResult:
    """Per-id ``DELETE {endpoint}/{id}`` — the **only** supported delete form."""
    capability = context.capability
    ids = _resolve_delete_ids(arguments)
    delete = adapter_method(adapter, "delete")
    context.warn(
        "对接规范 §3.5 第 1 条 / §11.5.1：单条删除只走**未文档化**的 "
        "DELETE {endpoint}/{id}；带 Assign 体的 DELETE 会清空整表，已被本工具与适配器"
        "双重拦截。写操作不自动重试（V2.1 §26.5）。"
    )
    return await delete(
        capability.endpoint or capability.resource,
        ids,
        timeout_seconds=timeout_of(arguments),
    )
