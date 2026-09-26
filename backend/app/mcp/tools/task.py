"""Tool ④ ``midas_task`` — V2.1 §10.

The platform Task Engine's MCP face (V2.1 §26).  MIDAS itself has **no** task
API — 对接规范 §2.5.1 searched the whole ``MIDAS-API-main`` corpus for
``동시 / concurrent / multi-user / queue`` and every one of the 94 hits is a
structural-engineering concept, none is about API concurrency, multi-user access
or call quotas.  So this tool is purely our own bookkeeping, which is why its
capability rows carry ``adapter_code=None``.

Poll-based, never push (裁决 B-9): ``get / list / cancel / retry / result /
events / logs``.  The standard progress dance is::

    midas_execute            -> task_id
    midas_task action=events -> since=<cursor>      (loop)
    midas_task action=result -> final payload       (once terminal)

``tasks.type`` / ``tasks.status`` are **closed** vocabularies — V2.1 §26.2 (14
business types) and 总纲 §4.2.1 — so their enums come from
:mod:`app.core.constants`, not from the capability table.
"""

from typing import TYPE_CHECKING, Any, Final, Mapping

from app.adapters.base import AdapterResult
from app.adapters.errors import AdapterError
from app.core.constants import TASK_STATUS_VALUES, TASK_TYPE_VALUES
from app.core.errors import ErrorCode
from app.mcp.capabilities import TOOL_TASK, actions_for
from app.mcp.context import DispatchContext
from app.services.task_service import task_owner_scope, task_visible_to

if TYPE_CHECKING:  # pragma: no cover - typing only; task_service does not import app.mcp
    from app.services.task_service import TaskService

__all__ = ["TOOL_NAME", "TITLE", "DESCRIPTION", "SCHEMA", "build_schema", "handle"]

TOOL_NAME: Final[str] = TOOL_TASK
TITLE: Final[str] = "StructAI MIDAS Task"
DESCRIPTION: Final[str] = (
    "统一管理异步任务：get / list / cancel / retry / result / events / logs。"
    "本工具是平台自身的 Task Engine（V2.1 §26）—— MIDAS 没有任务端点"
    "（对接规范 §2.5.1）。轮询模型：MCP 没有 push / subscribe（裁决 B-9），"
    "进度用 action=events 带 since 游标增量获取。"
    "持久性取决于注入的 TaskStore：SqlAlchemyTaskStore 落 tasks / task_events 表"
    "（V2.1 §26.3，重启不丢），默认的 InMemoryTaskStore 仅存于进程内。"
)


# ---------------------------------------------------------------------------
# schema
# ---------------------------------------------------------------------------
def build_schema() -> dict[str, Any]:
    """Build the §10.2 schema.  ``type`` / ``status`` come from the closed sets."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"structai://mcp/v2.1/tools/{TOOL_TASK}",
        "title": TITLE,
        "description": DESCRIPTION,
        "type": "object",
        "additionalProperties": False,
        "required": ["action"],
        "properties": {
            "action": {
                "type": "string",
                "enum": actions_for(TOOL_TASK),
                "description": "任务动作（V2.1 §10.2）。",
            },
            "task_id": {
                "type": ["string", "null"],
                "description": "任务 ID，**只允许 task_ 前缀**（总纲 §4.1.4）。",
            },
            "type": {
                "type": ["string", "null"],
                "enum": list(TASK_TYPE_VALUES) + [None],
                "description": "业务任务类型过滤（V2.1 §26.2，封闭 14 值）。",
            },
            "status": {
                "type": ["string", "null"],
                "enum": list(TASK_STATUS_VALUES) + [None],
                "description": "任务状态过滤（总纲 §4.2.1）。",
            },
            "since": {
                "type": ["string", "null"],
                "description": (
                    "action=events 的增量游标（V2.1 §10.2 新增）：事件 id 或 ISO-8601 "
                    "created_at；响应会回显 cursor。"
                ),
            },
            "page": {"type": "integer", "minimum": 1, "default": 1},
            "page_size": {
                "type": "integer",
                "minimum": 1,
                "maximum": 500,
                "default": 50,
            },
            "include_result": {"type": "boolean", "default": False},
            "include_events": {"type": "boolean", "default": False},
        },
    }


SCHEMA: dict[str, Any] = build_schema()


# ---------------------------------------------------------------------------
# handler
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# ownership scope (v1.2 §21) — the rule itself lives in ``task_service``
# ---------------------------------------------------------------------------
def _caller_identity(principal: Any) -> "tuple[int | None, tuple[str, ...]]":
    """``(user_id, roles)`` of the resolved principal, when there is one.

    ``context.principal`` holds the concrete ``Principal`` the auth seam resolved
    (see ``app/mcp/auth.py``).  It is ``None`` — or still the raw credential —
    when authentication is switched off (总纲 裁决 C-13), in which case there is
    nobody to scope by and the §4.8.2 gate stands alone.
    """
    user_id = getattr(principal, "user_id", None)
    if isinstance(user_id, bool) or not isinstance(user_id, int):
        return None, ()
    roles = getattr(principal, "roles", ()) or ()
    return user_id, tuple(str(role) for role in roles)


async def _require_task_scope(tasks: "TaskService", task_id: str, principal: Any) -> None:
    """Refuse a task outside the caller's data scope (v1.2 §21).

    Mirrors the REST layer's ``_require_task_read``.  Without it ``midas_task``
    was the one surface with no ownership check at all: ``action=list``
    enumerated every user's tasks and ``action=get`` read any of them, while
    ``GET /tasks/{id}`` refused the identical request.  Both surfaces now call
    the same :func:`app.services.task_service.task_visible_to`.

    A missing record is left to the engine, so the caller still gets
    ``TASK_NOT_FOUND`` with the engine's own message rather than a scope refusal
    that would hint at which ids exist.
    """
    user_id, roles = _caller_identity(principal)
    if user_id is None:
        return
    record = await tasks.store.load_task(task_id)
    if record is None:
        return
    if task_visible_to(record.requested_by, user_id=user_id, roles=roles):
        return
    raise AdapterError(
        ErrorCode.PERMISSION_DENIED,
        f"任务 {task_id!r} 属于其他用户（tasks.requested_by={record.requested_by}），"
        "不得访问。这是既有 task:read 之上的数据范围过滤，不引入新权限码"
        "（总纲 §4.8.2 封闭集合）。",
        details={
            "reason": "task_out_of_scope",
            "task_id": task_id,
            "requested_by": record.requested_by,
            "user_id": user_id,
        },
    )


async def handle(
    arguments: Mapping[str, Any], context: DispatchContext
) -> AdapterResult:
    """Route one validated ``midas_task`` call to the Task Engine (V2.1 §26)."""
    action = context.capability.action
    tasks = context.tasks
    task_id = arguments.get("task_id")
    identifier = str(task_id) if task_id else None

    # v1.2 §21 data scope: every action but ``list`` addresses exactly one task,
    # so one check covers get / cancel / retry / result / events / logs.  ``list``
    # instead pushes the same scope into the query (below), which is what keeps
    # its ``total`` honest.
    if action != "list":
        await _require_task_scope(tasks, identifier or "", context.principal)

    if action == "get":
        data = await tasks.get(
            identifier or "",
            include_result=bool(arguments.get("include_result")),
            include_events=bool(arguments.get("include_events")),
        )
        return AdapterResult.ok(data, warnings=_persistence_warning(tasks))

    if action == "list":
        user_id, roles = _caller_identity(context.principal)
        data = await tasks.list(
            type=arguments.get("type"),
            status=arguments.get("status"),
            page=int(arguments.get("page") or 1),
            page_size=int(arguments.get("page_size") or 50),
            # ``None`` means "no ownership filter" — super_admin, or no principal
            # at all because authentication is off (裁决 C-13).
            requested_by=(
                None if user_id is None else task_owner_scope(user_id, roles)
            ),
        )
        return AdapterResult.ok(data, warnings=_persistence_warning(tasks))

    if action == "cancel":
        data = await tasks.cancel(identifier or "")
        return AdapterResult.ok(data, warnings=_persistence_warning(tasks))

    if action == "retry":
        data = await tasks.retry(identifier or "")
        return AdapterResult.ok(data, warnings=_persistence_warning(tasks))

    if action == "result":
        data = await tasks.result(identifier or "")
        warnings = _persistence_warning(tasks)
        if not data.get("ready"):
            warnings.append(
                f"任务尚未进入终态（status={data.get('status')!r}）；"
                "V2.1 §10.3 要求终态（success / failed / cancelled）后才取结果。"
            )
        return AdapterResult.ok(data, warnings=warnings)

    if action == "events":
        data = await tasks.events(
            identifier or "",
            since=arguments.get("since"),
            page=int(arguments.get("page") or 1),
            page_size=int(arguments.get("page_size") or 200),
        )
        return AdapterResult.ok(data, warnings=_persistence_warning(tasks))

    if action == "logs":
        data = await tasks.logs(identifier or "")
        return AdapterResult.ok(data, warnings=_persistence_warning(tasks))

    raise AssertionError(  # pragma: no cover - the table is a closed set
        f"midas_task 收到未知 action={action!r}"
    )


def _persistence_warning(tasks: "TaskService") -> list[str]:
    """State the **actual** durability of the Task Engine behind this answer.

    Phase 2 wired persistence, so the old blanket "restart loses everything"
    caveat is only true for the default in-memory store — with a durable store it
    would be actively **wrong**, and a warning that lies is worse than none.  The
    message is therefore derived from ``TaskStore.durable`` rather than hard-coded.
    """
    if getattr(tasks.store, "durable", False):
        return []
    return [
        "任务状态来自本进程内存中的 Task Engine（默认 InMemoryTaskStore），重启即丢失。"
        "生产部署必须注入 SqlAlchemyTaskStore —— 届时本提示消失，且 "
        "request_id -> task_id -> adapter_request_id 追溯链（总纲 §4.1.5）可跨进程查询。"
    ]
