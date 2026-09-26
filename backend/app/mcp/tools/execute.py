"""Tool ③ ``midas_execute`` — V2.1 §9.

Executes the explicit software actions that need an adapter mapping: connect /
disconnect / open-save-close project / import / export / calculate / analysis /
generate_report / validate_model / sync / command.

Async by default (V2.1 §9.2: ``options.async`` defaults to ``true``,
``options.wait`` to ``false``) — a long action is handed to the Task Engine
(V2.1 §26) and answered with a ``task_``-prefixed ``task_id`` plus
``status="queued"``, exactly the §9.4 example.  Pass ``wait=true`` (or
``async=false``) to run it inline and get the result in ``data``.

Actions that cannot exceed a few seconds are **always** inline, because V2.1
§26.1 sends 「所有可能超过几秒的操作」 to the task system and nothing else:
``connect`` / ``disconnect`` / ``close_project`` / ``sync`` / ``command`` and the
unmapped ``validate_model``.  ``capability.task_type is None`` is that decision,
recorded as data in the capability table.

``data`` is the only free-form payload in the whole MCP surface (裁决 B-4) and
is **not** a validation bypass: V2.1 §9.3 requires it to be re-validated against
the resolved capability's ``request_schema_json`` before it reaches the adapter,
and the dispatcher does exactly that.
"""

from typing import TYPE_CHECKING, Any, Final, Mapping

from app.adapters.base import AdapterResult, ExecuteRequest
from app.adapters.midas_gen.adapter import guard_local_path
from app.core.constants import TaskStatus
from app.core.errors import ErrorCode
from app.mcp.capabilities import (
    DISPATCH_EXECUTE,
    DISPATCH_GET_TABLE,
    DISPATCH_MODEL_SYNC,
    DISPATCH_NOT_IMPLEMENTED,
    TOOL_EXECUTE,
    actions_for,
    resources_for,
)
from app.mcp.context import (
    DispatchContext,
    as_dict,
    options_of,
    require_adapter,
    timeout_of,
)
from app.mcp.tools.query import model_snapshot, read_result_table

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from app.adapters.base import MidasAdapter

__all__ = ["TOOL_NAME", "TITLE", "DESCRIPTION", "SCHEMA", "build_schema", "handle"]


def _caller_user_id(principal: Any) -> int | None:
    """``users.id`` of the caller, or ``None`` when there is nobody to attribute.

    ``DispatchContext.principal`` carries the **resolved** ``Principal`` — the
    auth seam writes it back after verifying the credential — so this is a real
    user id, not an opaque token.

    ``tasks.requested_by`` was always NULL before this was wired: the column, the
    ORM mapping and the DB foreign key all existed, but nothing ever populated
    them, so a task could not be attributed to its caller and a stream could not
    be filtered to its owner (总纲 §4.1.5).  ``None`` is the honest answer when
    authentication is switched off (裁决 C-13) or the caller is anonymous, which
    is exactly why the column is nullable.
    """
    user_id = getattr(principal, "user_id", None)
    if isinstance(user_id, bool):  # bool is an int subclass; never a user id
        return None
    if not isinstance(user_id, int) or user_id <= 0:
        # ``0`` is :data:`app.services.auth_service.ANONYMOUS_USER_ID` — the
        # stand-in used when authentication is switched off (裁决 C-13).  It is
        # not a real ``users`` row, and ``tasks.requested_by`` is a real foreign
        # key, so attributing a task to it would fail the insert.
        return None
    return user_id

TOOL_NAME: Final[str] = TOOL_EXECUTE
TITLE: Final[str] = "StructAI MIDAS Execute"
DESCRIPTION: Final[str] = (
    "执行需要 Adapter 映射的明确软件动作：connect / disconnect / open_project / "
    "save_project / close_project / import / export / calculate / analysis / "
    "generate_report / validate_model / sync / command。"
    "默认异步（V2.1 §9.2）：返回 status=queued 与 task_id，用 midas_task action=events "
    "轮询（MCP 没有 push，裁决 B-9）；options.wait=true 则同步返回结果。"
    "所有文件路径在运行 MIDAS NX 的那台机器上解析（对接规范 §3.5 第 6 条），"
    "且禁止受保护路径（第 13 条）。"
)


# ---------------------------------------------------------------------------
# schema
# ---------------------------------------------------------------------------
def build_schema() -> dict[str, Any]:
    """Build the §9.2 schema from the capability table (never hand-written)."""
    execute_resources = resources_for(TOOL_EXECUTE)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"structai://mcp/v2.1/tools/{TOOL_EXECUTE}",
        "title": TITLE,
        "description": DESCRIPTION,
        "type": "object",
        "additionalProperties": False,
        "required": ["action"],
        "properties": {
            "action": {
                "type": "string",
                "enum": actions_for(TOOL_EXECUTE),
                "description": "执行动作（V2.1 §6.3）。",
            },
            "resource": {
                "type": ["string", "null"],
                # V2.1 §9.2 permits resource: null; the enum therefore carries null
                # and the dispatcher fills the action's canonical resource.
                "enum": execute_resources + [None],
                "description": (
                    "执行对象；省略时按 action 取该动作的规范资源（V2.1 §9.2 允许 null）。"
                ),
            },
            "data": {
                "type": ["object", "null"],
                # 裁决 B-4: this is the ONLY field allowed to stay open in the MCP
                # schema — and V2.1 §9.3 makes the Capability's request_schema_json
                # the real gate, applied by the dispatcher.
                "additionalProperties": True,
                "description": (
                    "动作参数。裁决 B-4：midas_execute.data 是全平台唯一保留开放形态的"
                    "字段，但绝不是免校验通道 —— V2.1 §9.3 要求在到达 Adapter **之前**"
                    "按 Capability.request_schema_json 二次校验，失败一律 VALIDATION_ERROR。"
                    "路径类动作（open/save/saveas/import/export）用 data.path；"
                    "command 用 data.method / data.endpoint / data.body。"
                ),
            },
            "options": {
                "type": ["object", "null"],
                "additionalProperties": False,
                "properties": {
                    "async": {"type": "boolean", "default": True},
                    "wait": {"type": "boolean", "default": False},
                    "timeout_seconds": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 86400,
                        "default": 300,
                    },
                    "dry_run": {"type": "boolean", "default": False},
                    "force": {"type": "boolean", "default": False},
                },
                "description": (
                    "V2.1 §9.2。dry_run 只构造请求体、不发请求；force 保留给 "
                    "§25.2 的高风险确认（Phase 2 接 confirmation token）。"
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
    """Route one validated ``midas_execute`` call (V2.1 §9)."""
    capability = context.capability
    dispatch = capability.dispatch

    if dispatch == DISPATCH_NOT_IMPLEMENTED:
        return AdapterResult.failed(
            ErrorCode.NOT_IMPLEMENTED,
            capability.notes
            or f"{capability.resource}.{capability.action} 尚未映射到任何 MIDAS 端点。",
            warnings=[
                "本平台**不会**用一个假成功来掩盖未实现的动作"
                "（V2.1 §20.4：文本兜底不得作为唯一判据）。"
            ],
        )

    adapter = require_adapter(context)
    if dispatch == DISPATCH_MODEL_SYNC:
        return await model_snapshot(adapter, context=context)
    if dispatch == DISPATCH_GET_TABLE:
        return await _export_table(arguments, context, adapter)
    if dispatch == DISPATCH_EXECUTE:
        return await _execute(arguments, context, adapter)
    raise AssertionError(  # pragma: no cover - the table is a closed set
        f"midas_execute 收到未知 dispatch={dispatch!r}"
    )


# ---------------------------------------------------------------------------
# the adapter call
# ---------------------------------------------------------------------------
async def _execute(
    arguments: Mapping[str, Any],
    context: DispatchContext,
    adapter: "MidasAdapter",
) -> AdapterResult:
    """Run inline, or hand the action to the Task Engine (V2.1 §9.2 / §26)."""
    capability = context.capability
    options = options_of(arguments)
    timeout = timeout_of(arguments, default=300)

    if capability.action == "command" and not as_dict(arguments.get("data")):
        return AdapterResult.failed(
            ErrorCode.VALIDATION_ERROR,
            "action=command 需要 data.method / data.endpoint（以及可选的 data.body / "
            "data.wrapper）。该通道仍强制执行 DELETE 守卫、/db/NMAS 必填兜底与 "
            "/db/PRES DIRECTION 强制（对接规范 §3.5 第 1/3/12 条）。",
        )

    if options.get("dry_run"):
        return AdapterResult.ok(
            {
                "dry_run": True,
                "action": capability.action,
                "resource": capability.resource,
                "endpoint": capability.endpoint,
                "adapter_action": capability.effective_adapter_action,
                "request_wrapper": capability.request_wrapper,
                "data": arguments.get("data"),
            },
            warnings=[
                "dry_run：只回显将要发出的请求形状，**没有**任何 MIDAS 调用发生。"
            ],
        )

    # V2.1 §9.2: options.async 默认 true、options.wait 默认 false。
    wait = bool(options.get("wait")) or options.get("async") is False
    if wait or capability.task_type is None:
        if wait and capability.task_type is not None:
            context.warn(
                "options.wait=true：已按调用方要求在本次请求内同步执行"
                "（V2.1 §9.2 默认 async=true）。"
            )
        return await run_action(arguments, context, adapter)

    task_id = await context.tasks.create(
        type=capability.task_type,
        action=capability.action,
        resource=capability.resource,
        tool_name=TOOL_EXECUTE,
        adapter_code=capability.adapter_code,
        midas_client_id=context.midas_client_id,
        requested_by=_caller_user_id(context.principal),
        request_id=context.request_id,
        timeout_seconds=timeout,
        payload={
            "action": capability.action,
            "resource": capability.resource,
            "data": arguments.get("data"),
            "options": options,
        },
        is_write=capability.is_write,
        runner=lambda: run_action(arguments, context, adapter),
    )
    return AdapterResult.ok(
        None,
        status=TaskStatus.QUEUED.value,
        task_id=task_id,
        warnings=[
            "任务已入队（V2.1 §26.1 queued）。MCP **没有** push / subscribe 语义"
            "（裁决 B-9）：请轮询 midas_task action=events（带 since 游标），"
            "终态后用 midas_task action=result 取结果。",
            "V2.1 §26.5：全局并发 N，但每个 midas_client_id 并发恒为 1 —— "
            "对接规范 §2.5.2 证明 NX 主机上的模态对话框会阻塞整条 API 会话。",
        ],
    )


async def run_action(
    arguments: Mapping[str, Any],
    context: DispatchContext,
    adapter: "MidasAdapter",
) -> AdapterResult:
    """``adapter.execute(ExecuteRequest)`` — also the Task Engine's replayable body.

    **Session observability (对接规范 §2.5.2 / §11.5.13).**  Two shapes reach the
    caller through ``AdapterResult.data`` and are therefore visible in the
    envelope's ``data`` without any change to the capability table (V2.1 §16.1:
    the table is generated, so no new row is added):

    * ``server.connect`` (``adapter_action="connect"``, ``task_type IS NULL`` →
      inline, V2.1 §9.2) returns ``data.diagnosis``: the structured verdict from
      ``MidasNxAdapter.diagnose_session()`` — ``state`` / ``remedy`` /
      ``requires_human`` / ``retry_helps`` and both probes' status + latency;
    * **any** call that fails in the transport layer returns
      ``data.transport.phase`` (``connect`` / ``read`` / ``write`` / ``pool`` /
      ``unknown``) plus the unconfirmed ``data.session.state`` it implies.

    The adapter attaches both; this layer must **not** re-probe to enrich them —
    a session that is not answering is not processing requests, so a second probe
    would only queue another timeout behind whatever is blocking it.  Note the
    deliberate vagueness: ``read``-phase silence is produced **both** by a modal
    dialog on the NX host (§11.5.13) and by a black-holed network path (§11.5.14),
    and the two are indistinguishable from here, so this layer must not assume
    which one it is.
    """
    capability = context.capability
    data = as_dict(arguments.get("data"))
    request = ExecuteRequest(
        request_id=context.request_id,
        client_id=context.midas_client_id or 0,
        action=capability.effective_adapter_action,
        resource=capability.resource,
        payload=arguments.get("data"),
        options=options_of(arguments),
        timeout_seconds=timeout_of(arguments, default=300),
        data=data,
    )
    return await adapter.execute(request)


# ---------------------------------------------------------------------------
# result.export — POST /post/TABLE with EXPORT_PATH
# ---------------------------------------------------------------------------
async def _export_table(
    arguments: Mapping[str, Any],
    context: DispatchContext,
    adapter: "MidasAdapter",
) -> AdapterResult:
    """``result.export``: write a result table to a file **on the NX host**."""
    data = as_dict(arguments.get("data"))
    export_path = data.get("export_path") or data.get("path")
    if not export_path:
        return AdapterResult.failed(
            ErrorCode.VALIDATION_ERROR,
            "result.export 需要 data.export_path。对接规范 §3.5 第 6 条：所有路径在"
            "运行 MIDAS NX 的那台机器上解析（常常不是跑本平台的那台），"
            "因此必须由调用方显式提供；第 13 条：禁止 Program Files 之类受保护路径。",
        )
    # 对接规范 §3.5 第 6 / 13 条 are MCP-layer-visible rules, so they are checked
    # here as well as inside the adapter's get_table(): a path that is empty or
    # protected makes the NX host pop a modal dialog that blocks the whole API
    # session (对接规范 §2.5.2), which is far too expensive to discover late.
    guard_local_path(str(export_path))
    query: dict[str, Any] = {
        "result_type": data.get("result_type") or "displacement",
    }
    for key in ("load_case", "load_combination", "component", "envelope", "top_n"):
        if data.get(key) is not None:
            query[key] = data[key]
    synthetic: dict[str, Any] = {
        "query": query,
        "fields": data.get("components") or data.get("fields"),
        "options": options_of(arguments),
        "client_id": arguments.get("client_id"),
    }
    return await read_result_table(
        synthetic, context, adapter, export_path=str(export_path)
    )
