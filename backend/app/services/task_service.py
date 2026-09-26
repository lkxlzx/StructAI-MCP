"""Task Engine — V2.1 §26 (state machine, concurrency, retry ban, persistence).

Authoritative sources
---------------------
* V2.1 §26.1 状态流转 — ``queued -> running -> success | failed -> retrying``,
  ``running -> cancelled``; values are verbatim ``tasks.status`` (总纲 §4.2.1).
* V2.1 §26.2 ``tasks.type`` — closed 14-value business task type (裁决 A-6).
* V2.1 §26.3 职责 — 排队 / 并发 / 超时 / 重试 / 取消 / 进度 / 日志 / 结果 / 事件.
* V2.1 §26.4 追溯链 — ``request_id -> task_id -> adapter_request_id``
  (总纲 §4.1.5).
* V2.1 §26.5 并发模型与写操作重试禁令 — **全局工作池并发 N，每个
  ``midas_client_id`` 并发恒为 1**; 写操作超时后**禁止自动重试**
  (对接规范 §2.5.2 / §2.5.4 / §3.5 第 5 条: 超时 ≠ 回滚).
* 总纲 §4.1.4 — 一切异步任务 ID 一律 ``task_`` 前缀，子类型由 ``tasks.type``
  区分；``task_ai_xxx`` / ``analysis_xxx`` 等前缀全部废止.

Storage — a pluggable store, not a hard-wired dict
--------------------------------------------------
The engine keeps no task state of its own beyond the live objects it is driving.
All reads and writes go through :class:`app.services.task_store.TaskStore`:

* :class:`~app.services.task_store.InMemoryTaskStore` is the **default** and is
  byte-for-byte the previous behaviour, so the offline suite stays fast and needs
  no database.
* :class:`~app.services.task_store.SqlAlchemyTaskStore` persists ``tasks`` /
  ``task_events`` (V2.1 §4 tables 24–25) and is constructed with a session
  factory, so a caller can point it at any database without touching the
  process-wide engine.

The interface was already DB-shaped — every attribute name matched the ORM column
one-for-one — so the swap changes no caller: ``TaskService(**kwargs)``,
``get_task_service()`` and ``reset_task_service()`` all behave as before.

Restart semantics
-----------------
``TaskRecord.runner`` is an in-process coroutine factory and is **never stored**.
A restart therefore leaves any row still in ``queued`` / ``running`` /
``retrying`` with no way to make progress.  Silently leaving it ``running``
forever would be a lie and fabricating ``success`` would be worse, so
:meth:`TaskService.recover_orphans` marks each such orphan ``failed`` with
``error_code = INTERNAL_ERROR`` plus an event explaining that the process
restarted.  It is called from :func:`init_task_service`, the documented startup
entry point, which application bootstrap must ``await`` once before serving
traffic.

Concurrency model (V2.1 §26.5)
------------------------------
``asyncio.Semaphore(N)`` is the global worker pool and one ``asyncio.Lock`` per
``midas_client_id`` is the per-instance serial queue.  The global slot is taken
**before** the per-client lock, which is the model §26.5 draws (「全局工作池 +
按 midas_client_id 串行队列」); the cost is that a task queued behind a busy
client can occupy a global slot while it waits.  That is the documented shape of
the rule, not an accident.

One instance is bound to the event loop it first awaits in (``asyncio.Lock`` /
``asyncio.Semaphore`` are loop-bound) — the same caveat as
:class:`app.adapters.midas_gen.adapter.MidasNxAdapter`.  Build it inside the loop
that will use it.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Awaitable, Callable, Iterator, List, Sequence, cast

from app.adapters.errors import AdapterError
from app.core.constants import SUPER_ADMIN_ROLE, TaskStatus, TaskType
from app.core.errors import ErrorCode
from app.core.ids import new_id
from app.services.event_bus import EventBus, TASKS_TOPIC, task_topic
from app.services.task_store import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_TASK_TIMEOUT_SECONDS,
    InMemoryTaskStore,
    SyncTaskStore,
    TaskEventRecord,
    TaskRecord,
    TaskStore,
    iso as _iso,
    utcnow as _utcnow,
)

__all__ = [
    "TaskService",
    "TaskRecord",
    "TaskEventRecord",
    "DEFAULT_GLOBAL_CONCURRENCY",
    "DEFAULT_TASK_TIMEOUT_SECONDS",
    "DEFAULT_MAX_RETRIES",
    "TERMINAL_STATUSES",
    "ORPHAN_STATUSES",
    "get_task_service",
    "reset_task_service",
    "init_task_service",
]

#: Global worker-pool size (V2.1 §26.5 「全局工作池并发 = N」).
DEFAULT_GLOBAL_CONCURRENCY: int = 4

#: 总纲 §4.2.1 — a task in one of these states has stopped moving.
TERMINAL_STATUSES: frozenset[str] = frozenset(
    {
        TaskStatus.SUCCESS.value,
        TaskStatus.FAILED.value,
        TaskStatus.CANCELLED.value,
    }
)

#: 总纲 §4.2.1 — the non-terminal states a restart can orphan.  A ``runner``
#: cannot survive a process boundary, so these are what :meth:`TaskService.
#: recover_orphans` has to reconcile.
ORPHAN_STATUSES: frozenset[str] = frozenset(
    {
        TaskStatus.QUEUED.value,
        TaskStatus.RUNNING.value,
        TaskStatus.RETRYING.value,
    }
)


# ---------------------------------------------------------------------------
# task ownership scope (v1.2 §21) — ONE rule, shared by both surfaces
# ---------------------------------------------------------------------------
def task_owner_scope(user_id: int, roles: Sequence[str]) -> int | None:
    """The ``tasks.requested_by`` scope one caller may see (v1.2 §21).

    ``None`` means "no ownership filter at all" — the ``super_admin`` case, which
    总纲 §4.8.3 lets through to every row — otherwise the caller's own user id.

    It lives here, rather than in either surface, because there are now **three**
    consumers that must agree: the REST per-row predicate, the REST list query
    filter, and the MCP ``midas_task`` handler.  This is not hypothetical — the
    rule previously existed only in the REST layer, and the MCP surface was left
    with no ownership check at all, so ``midas_task action=list`` enumerated every
    user's tasks while ``GET /tasks/{id}`` refused them.  A hand-written second
    copy at any site is exactly how that happens.
    """
    if SUPER_ADMIN_ROLE in roles:
        return None
    return int(user_id)


def task_visible_to(
    requested_by: int | None, *, user_id: int, roles: Sequence[str]
) -> bool:
    """Whether one task row is within a caller's data scope (v1.2 §21).

    Same shape 《MIDAS API 对接规范》§2.5.4 item 5 mandates for MIDAS instances:
    总纲 §4.8.2's permission list is a **closed set**, so "only your own tasks"
    cannot become a new permission code — it is a **data-scope filter layered on
    top of** the ``task:read`` check that already ran.  It changes *which rows* a
    caller reaches, never *which permission* it holds.

    ``requested_by is None`` means the task was created without attribution, and
    the filter **fails closed** on it: a row that belongs to nobody is visible
    only to an unfiltered caller (``super_admin``, or a deployment with
    authentication off, both of which never reach this predicate because they
    pass no scope at all).  It is deliberately **not** treated as "public":

    * ``tasks.requested_by`` is ``ON DELETE SET NULL`` (V2.1 §4), so hard-deleting
      a user would otherwise publish that user's entire task history to every
      remaining caller;
    * a security control that fails open is not a control.

    ``super_admin`` holds every §4.8.2 code and is let through to any task.

    Defined in terms of :func:`task_owner_scope` so a pushed-down query filter and
    this predicate cannot diverge.
    """
    scope = task_owner_scope(user_id, roles)
    if scope is None:
        return True
    return requested_by is not None and int(requested_by) == scope


def _llm_safe(value: Any) -> Any:
    """Strip ``raw_status`` / ``raw_response`` before anything is stored.

    V2.1 §19 字段约束: the two raw fields are 「仅用于日志与排障，**禁止**直接回传
    LLM」.  ``tasks.result_json`` is read back by ``midas_task action=result``, so
    the raw form must never reach it — this is the single choke point.
    """
    to_llm = getattr(value, "to_llm_payload", None)
    if callable(to_llm):
        return to_llm()
    return value


# ---------------------------------------------------------------------------
# TaskService
# ---------------------------------------------------------------------------
class TaskService:
    """Task Engine (V2.1 §26) over a pluggable :class:`TaskStore`.

    ``store`` defaults to :class:`InMemoryTaskStore`, which is what every existing
    call site gets; pass a :class:`SqlAlchemyTaskStore` to make tasks survive a
    restart.
    """

    def __init__(
        self,
        *,
        max_concurrency: int = DEFAULT_GLOBAL_CONCURRENCY,
        default_timeout_seconds: float = DEFAULT_TASK_TIMEOUT_SECONDS,
        store: TaskStore | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        if max_concurrency < 1:
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR,
                f"max_concurrency 必须 >= 1，收到 {max_concurrency!r}",
            )
        self._store: TaskStore = store if store is not None else InMemoryTaskStore()
        #: Live objects this process is driving (or has loaded).  The store is the
        #: source of truth; this keeps the *identity* of an in-flight record so
        #: ``runner`` and ``cancel()`` still work, and it is what the synchronous
        #: introspection helpers below can see.
        self._records: dict[str, TaskRecord] = {}
        self._handles: dict[str, asyncio.Task[None]] = {}
        self._max_concurrency: int = max_concurrency
        self._default_timeout_seconds: float = default_timeout_seconds
        #: v1.2 §21 / §22.3 — the in-process bus every emitted event is mirrored
        #: onto.  **Optional and default-off**: ``None`` (every pre-existing call
        #: site, including the whole offline suite) means ``_emit`` behaves
        #: byte-for-byte as it did before the REST/SSE layer existed.
        self._event_bus: EventBus | None = event_bus
        #: V2.1 §26.5 「全局工作池并发 = N」.
        self._pool: asyncio.Semaphore = asyncio.Semaphore(max_concurrency)
        #: V2.1 §26.5 「每个 midas_client_id 并发 = 1」(硬约束).
        self._client_locks: dict[int, asyncio.Lock] = {}

    # ------------------------------------------------------------------ #
    # introspection helpers
    # ------------------------------------------------------------------ #
    @property
    def max_concurrency(self) -> int:
        """Global worker-pool size N (V2.1 §26.5)."""
        return self._max_concurrency

    @property
    def store(self) -> TaskStore:
        """The store backing this engine (read-only view)."""
        return self._store

    @property
    def event_bus(self) -> EventBus | None:
        """The publish bus this engine mirrors events onto, or ``None`` (v1.2 §21).

        ``None`` is the default and means "no REST/SSE layer attached"; the
        offline suite therefore sees exactly the pre-REST behaviour.
        """
        return self._event_bus

    def __len__(self) -> int:
        """Tasks this process has created or loaded.

        For the default :class:`InMemoryTaskStore` that is every task, exactly as
        before.  A durable store may hold rows this process has never touched;
        those are reachable through ``await list()`` / ``await get()``, not
        through a synchronous dunder.
        """
        return len(self._records)

    def __contains__(self, task_id: object) -> bool:
        """Whether ``task_id`` is one of the records this process holds."""
        return task_id in self._records

    # ------------------------------------------------------------------ #
    # create
    # ------------------------------------------------------------------ #
    async def create(
        self,
        *,
        type: str,
        action: str,
        resource: str | None = None,
        tool_name: str | None = None,
        adapter_code: str | None = None,
        midas_client_id: int | None = None,
        request_id: str | None = None,
        priority: int = 5,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout_seconds: float | None = None,
        payload: Any = None,
        runner: Callable[[], Awaitable[Any]] | None = None,
        is_write: bool | None = None,
        parent_task_id: str | None = None,
        requested_by: int | None = None,
        start: bool = True,
    ) -> str:
        """Register a task and return its ``task_``-prefixed ID (总纲 §4.1.4).

        ``type`` must be one of the 14 closed ``tasks.type`` values (V2.1 §26.2);
        ``action`` reuses the MCP action word list.  ``runner`` is the replayable
        body — ``None`` means "bookkeeping only" (``action=retry`` then answers
        ``NOT_IMPLEMENTED`` rather than silently doing nothing).  It is **not**
        persisted: see the module docstring on restart semantics.

        ``requested_by`` is ``tasks.requested_by`` (V2.1 §4 / 总纲 §4.1.5): the
        ``users.id`` the task is attributed to.  Unlike ``runner`` it **is**
        persisted (``TaskStore.save_task`` maps it both ways), because it is what
        the REST layer filters a task stream on —
        ``GET /api/v1/tasks/{task_id}/stream`` (v1.2 §21) only serves a task to
        its own requester.  That filter is a **data-scope filter layered on top
        of** the closed 总纲 §4.8.2 ``task:read`` code, exactly the shape
        :func:`app.mcp.auth.scope_allows` uses for MIDAS instances; no permission
        code is invented.  ``None`` means "not attributed" — authentication is
        off (总纲 裁决 C-13) or the caller is anonymous — and such a task is
        streamable, since there is no owner to filter by.
        """
        if type not in {member.value for member in TaskType}:
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR,
                f"未知的 tasks.type={type!r}；V2.1 §26.2 的封闭 14 值："
                f"{[member.value for member in TaskType]}",
                details={"type": type},
            )
        # 总纲 §4.1.4: 一切异步任务 ID 一律 task_ 前缀，子类型由 tasks.type 区分。
        task_id = new_id("task")
        record = TaskRecord(
            task_id=task_id,
            type=type,
            action=action,
            resource=resource,
            tool_name=tool_name,
            adapter_code=adapter_code,
            midas_client_id=midas_client_id,
            requested_by=requested_by,
            priority=priority,
            max_retries=max_retries,
            request_id=request_id,
            parent_task_id=parent_task_id,
            input=payload,
            timeout_seconds=(
                float(timeout_seconds)
                if timeout_seconds is not None
                else self._default_timeout_seconds
            ),
            is_write=True if is_write is None else bool(is_write),
            runner=runner,
        )
        # The row must exist before its first event: ``task_events.task_id`` is a
        # real foreign key (V2.1 §4) and FK enforcement is on.
        await self._save(record)
        await self._emit(
            record,
            "queued",
            progress=0.0,
            message=(
                f"任务已入队（V2.1 §26.1 queued）；type={type} action={action} "
                f"resource={resource} midas_client_id={midas_client_id}"
            ),
            payload={
                "priority": priority,
                "timeout_seconds": record.timeout_seconds,
                "is_write": record.is_write,
            },
        )
        if start and runner is not None:
            self._schedule(record)
        return task_id

    def _schedule(self, record: TaskRecord) -> None:
        """Start the worker coroutine for ``record``."""
        runner = record.runner
        if runner is None:  # pragma: no cover - guarded by the caller
            return
        self._handles[record.task_id] = asyncio.ensure_future(
            self._drive(record, runner)
        )

    # ------------------------------------------------------------------ #
    # store plumbing
    # ------------------------------------------------------------------ #
    async def _save(self, record: TaskRecord) -> None:
        """Write the task row through to the store and keep the live object."""
        self._records[record.task_id] = record
        await self._store.save_task(record)

    async def _emit(
        self,
        record: TaskRecord,
        event_type: str,
        *,
        progress: float | None = None,
        message: str | None = None,
        payload: Any = None,
    ) -> TaskEventRecord:
        """Append one ``task_events`` row (V2.1 §26.3 「事件」).

        The store owns event ids: the SQL store reads the autoincrement key back
        (总纲 §4.1.1), the in-memory store allocates from one process-wide
        counter.  Both leave the ``since`` cursor semantics of V2.1 §10.3 intact.

        This is the **single choke point** for the REST/SSE layer (v1.2 §21 /
        §22.3): every status transition in this class — ``queued`` from
        :meth:`create`, ``started`` / ``finished`` / ``failed`` / ``cancelled``
        from :meth:`_drive` and its terminal helpers, ``retrying`` from
        :meth:`retry` — reaches the bus through here, so the per-task topic and
        the global ``tasks`` topic cannot drift from ``task_events``.  The row is
        saved **first**, so a subscriber that reacts to the notification by
        reading the store with the ``since`` cursor always finds the row it was
        told about.
        """
        event = TaskEventRecord(
            id=0,
            task_id=record.task_id,
            event_type=event_type,
            progress=progress,
            message=message,
            payload=payload,
            created_at=_utcnow(),
        )
        await self._store.save_event(event)
        await self._publish(record, event)
        return event

    async def _publish(self, record: TaskRecord, event: TaskEventRecord) -> None:
        """Mirror one saved event onto the in-process bus (v1.2 §21 / §22.3).

        Two topics, on purpose: ``task:<task_id>`` is what the per-task SSE
        endpoint (v1.2 §21) subscribes to, and the global ``tasks`` topic is the
        dashboard / log feed behind ``GET /api/v1/logs/stream`` (v1.2 §22.3).

        Optional and **default-off**: with ``event_bus=None`` — every call site
        that predates the REST layer, and the whole offline suite — this is a
        no-op and nothing observable changes.

        The published mapping is the event row plus the attribution fields the
        stream needs to name the event and to filter it by owner; the row's ``id``
        is carried through unchanged because it is the ``Last-Event-ID`` cursor
        (V2.1 §10.3).

        :meth:`emit_log` deliberately does **not** publish: it is a synchronous
        ``def`` that predates the async store protocol and may be called from a
        worker thread, where touching a loop-bound ``asyncio.Queue`` would be
        unsafe.  Its ``log`` rows are still reachable through
        ``midas_task action=logs`` and the ``task_events`` table.
        """
        bus = self._event_bus
        if bus is None:
            return
        published: dict[str, Any] = {
            **event.to_payload(),
            "status": record.status,
            "type": record.type,
            "action": record.action,
            "retry_count": record.retry_count,
            "requested_by": record.requested_by,
        }
        await bus.publish(task_topic(record.task_id), published)
        await bus.publish(TASKS_TOPIC, published)

    def _sync_store(self) -> SyncTaskStore:
        """Return the store's synchronous mirror, or fail loudly.

        ``emit_log`` is the one pre-existing synchronous entry point; a store that
        does not implement :class:`SyncTaskStore` cannot serve it.
        """
        if not isinstance(self._store, SyncTaskStore):
            raise AdapterError(
                ErrorCode.INTERNAL_ERROR,
                f"{type(self._store).__name__} 未实现 SyncTaskStore；"
                "emit_log 是同步 API（见 task_store.SyncTaskStore）。",
            )
        return cast(SyncTaskStore, self._store)

    # ------------------------------------------------------------------ #
    # the worker
    # ------------------------------------------------------------------ #
    async def _drive(
        self, record: TaskRecord, runner: Callable[[], Awaitable[Any]]
    ) -> None:
        """Run one task under the §26.5 concurrency rules."""
        try:
            async with self._global_slot():
                async with self._client_slot(record.midas_client_id):
                    record.status = TaskStatus.RUNNING.value
                    record.started_at = _utcnow()
                    await self._save(record)
                    await self._emit(
                        record,
                        "started",
                        progress=0.0,
                        message=(
                            "开始执行；V2.1 §26.5 —— 同一 midas_client_id 任何时刻"
                            "只允许一个在途请求（对接规范 §2.5.2：模态对话框会阻塞整条"
                            "API 会话）。"
                        ),
                    )
                    try:
                        result = await asyncio.wait_for(
                            _await_result(runner()), timeout=record.timeout_seconds
                        )
                    except asyncio.TimeoutError:
                        await self._fail_timeout(record)
                        return
                    except asyncio.CancelledError:
                        await self._cancel_record(record)
                        raise
                    except AdapterError as exc:
                        await self._fail(record, exc.code, exc.message)
                        return
                    except Exception as exc:  # noqa: BLE001 - engine boundary
                        await self._fail(
                            record,
                            ErrorCode.INTERNAL_ERROR.value,
                            f"任务执行抛出未预期异常：{exc!r}",
                        )
                        return
                    await self._finish(record, result)
        finally:
            self._handles.pop(record.task_id, None)

    @asynccontextmanager
    async def _global_slot(self) -> AsyncIterator[None]:
        """Global worker-pool slot (V2.1 §26.5 「全局工作池并发 = N」)."""
        async with self._pool:
            yield

    @asynccontextmanager
    async def _client_slot(self, midas_client_id: int | None) -> AsyncIterator[None]:
        """Per-instance serial queue (V2.1 §26.5 「每个 midas_client_id 并发 = 1」).

        ``midas_client_id is None`` (platform-owned work, e.g. a report) has no
        MIDAS instance to serialize against, so only the global slot applies.
        """
        if midas_client_id is None:
            yield
            return
        lock = self._client_locks.get(midas_client_id)
        if lock is None:
            lock = asyncio.Lock()
            self._client_locks[midas_client_id] = lock
        async with lock:
            yield

    # ------------------------------------------------------------------ #
    # terminal transitions
    # ------------------------------------------------------------------ #
    async def _finish(self, record: TaskRecord, result: Any) -> None:
        """``running -> success`` (V2.1 §26.1)."""
        success = getattr(result, "success", None)
        if success is False:
            await self._fail(
                record,
                getattr(result, "error_code", None) or ErrorCode.MIDAS_API_ERROR.value,
                getattr(result, "error_message", None) or "适配器返回失败结果",
                result=result,
            )
            return
        record.status = TaskStatus.SUCCESS.value
        record.progress = 100.0
        record.result = _llm_safe(result)
        record.finished_at = _utcnow()
        await self._save(record)
        await self._emit(
            record,
            "finished",
            progress=100.0,
            message="任务完成（V2.1 §26.1 running -> success）。",
        )

    async def _fail(
        self,
        record: TaskRecord,
        code: str,
        message: str,
        *,
        result: Any = None,
    ) -> None:
        """``running -> failed`` (V2.1 §26.1).  Never re-queues."""
        record.status = TaskStatus.FAILED.value
        record.error_code = code
        record.error_message = message
        record.result = _llm_safe(result)
        record.finished_at = _utcnow()
        await self._save(record)
        await self._emit(
            record,
            "failed",
            progress=record.progress,
            message=message,
            payload={"error_code": code},
        )

    async def _fail_timeout(self, record: TaskRecord) -> None:
        """V2.1 §26.5 / 对接规范 §3.5 第 5 条 — the one place retry is forbidden.

        The task is parked as ``failed`` with ``error_code='TASK_TIMEOUT'`` and
        **nothing is rescheduled**: a timed-out write may still have landed
        upstream, so the only safe next step is to read the model state back
        (``midas_execute action=sync``).
        """
        suffix = (
            "写操作超时后**禁止自动重试**（V2.1 §26.5 / 对接规范 §3.5 第 5 条："
            "超时 ≠ 回滚，写操作可能在 HTTP 放弃后仍然在 MIDAS 侧落地）。"
            "下一步必须先用 midas_execute action=sync 读回模型状态，再由人工判定。"
            if record.is_write
            else "读操作超时；重放是安全的，但仍需显式调用 midas_task action=retry。"
        )
        record.status = TaskStatus.FAILED.value
        record.error_code = ErrorCode.TASK_TIMEOUT.value
        record.error_message = (
            f"任务 {record.task_id} 在 {record.timeout_seconds:g}s 内未完成。{suffix}"
        )
        record.finished_at = _utcnow()
        await self._save(record)
        await self._emit(
            record,
            "failed",
            progress=record.progress,
            message=record.error_message,
            payload={"error_code": ErrorCode.TASK_TIMEOUT.value, "is_write": record.is_write},
        )

    async def _cancel_record(self, record: TaskRecord) -> None:
        """``running -> cancelled`` (V2.1 §26.1)."""
        if record.status in TERMINAL_STATUSES:
            return
        record.status = TaskStatus.CANCELLED.value
        record.finished_at = _utcnow()
        await self._save(record)
        await self._emit(
            record,
            "cancelled",
            progress=record.progress,
            message="任务已取消（V2.1 §26.1 running -> cancelled）。",
        )

    # ------------------------------------------------------------------ #
    # lookup
    # ------------------------------------------------------------------ #
    def _check_identifier(self, task_id: str | None) -> str:
        """Validate the identifier itself, before any store round trip."""
        if not task_id:
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR,
                "task_id 是必需的（V2.1 §10.2）；task_ 前缀见总纲 §4.1.4。",
            )
        return task_id

    def _missing(self, task_id: str) -> AdapterError:
        """``TASK_NOT_FOUND`` (总纲 §4.4.6) for an unknown ``task_id``."""
        return AdapterError(
            ErrorCode.TASK_NOT_FOUND,
            f"任务 {task_id!r} 不存在。",
            details={"task_id": task_id},
        )

    async def _require(self, task_id: str | None) -> TaskRecord:
        """Look up a task, raising ``TASK_NOT_FOUND`` (总纲 §4.4.6) when absent.

        The live record wins over the stored row: while a worker is in flight the
        in-memory object is the one carrying ``runner`` and the newest status.
        """
        identifier = self._check_identifier(task_id)
        record = self._records.get(identifier)
        if record is None:
            record = await self._store.load_task(identifier)
            if record is None:
                raise self._missing(identifier)
            self._records[identifier] = record
        return record

    def _require_now(self, task_id: str | None) -> TaskRecord:
        """Synchronous twin of :meth:`_require` (for ``emit_log`` only)."""
        identifier = self._check_identifier(task_id)
        record = self._records.get(identifier)
        if record is None:
            record = self._sync_store().load_task_now(identifier)
            if record is None:
                raise self._missing(identifier)
            self._records[identifier] = record
        return record

    # ------------------------------------------------------------------ #
    # public API — midas_task §10
    # ------------------------------------------------------------------ #
    async def get(
        self,
        task_id: str,
        *,
        include_result: bool = False,
        include_events: bool = False,
    ) -> dict[str, Any]:
        """``midas_task action=get`` — status / progress snapshot."""
        record = await self._require(task_id)
        data = record.to_payload(include_result=include_result)
        if include_events:
            events = await self._store.load_events(task_id)
            data["events"] = [event.to_payload() for event in events]
        return data

    async def list(
        self,
        *,
        type: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 50,
        requested_by: int | None = None,
    ) -> dict[str, Any]:
        """``midas_task action=list`` — filter by business type and/or status.

        ``requested_by`` is the v1.2 §20.1 / §21 **ownership scope**, forwarded
        verbatim to :meth:`app.services.task_store.TaskStore.list_tasks`: when it
        is given, rows owned by another user are excluded *by the store*, so
        ``total`` counts only what the caller may see and a page is never short.
        Filtering the returned page here instead would leak the platform-wide
        count through ``total`` and mis-number every page after the first.
        ``None`` (the default) means "no ownership filter" and keeps the
        pre-existing behaviour for every other caller.
        """
        if type is not None and type not in {member.value for member in TaskType}:
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR,
                f"未知的 tasks.type={type!r}（V2.1 §26.2 封闭 14 值）",
                details={"type": type},
            )
        if status is not None and status not in {member.value for member in TaskStatus}:
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR,
                f"未知的 tasks.status={status!r}（总纲 §4.2.1 封闭集合）",
                details={"status": status},
            )
        rows = [
            record
            for record in await self._store.list_tasks(requested_by=requested_by)
            if (type is None or record.type == type)
            and (status is None or record.status == status)
        ]
        # Lower priority value = sooner (tasks.priority, V2.1 §4).
        rows.sort(key=lambda record: (record.priority, record.queued_at))
        return _paginate(
            [record.to_payload(include_result=False) for record in rows], page, page_size
        )

    async def cancel(self, task_id: str) -> dict[str, Any]:
        """``midas_task action=cancel`` — 总纲 §4.4.6 ``TASK_CANCEL_FAILED`` on a
        task that already reached a terminal state."""
        record = await self._require(task_id)
        if record.status in TERMINAL_STATUSES:
            raise AdapterError(
                ErrorCode.TASK_CANCEL_FAILED,
                f"任务 {task_id} 已处于终态 {record.status!r}，无法取消"
                "（V2.1 §26.1：只有 running / queued 可以 -> cancelled）。",
                details={"task_id": task_id, "status": record.status},
            )
        handle = self._handles.get(task_id)
        if handle is not None and not handle.done():
            handle.cancel()
        await self._cancel_record(record)
        return record.to_payload(include_result=False)

    async def retry(self, task_id: str) -> dict[str, Any]:
        """``midas_task action=retry`` — **explicit, human-decided** replay.

        V2.1 §26.5 forbids the **engine** from auto-retrying a write after a
        timeout; it does not forbid an operator (or an agent acting on an
        explicit instruction) from doing so.  A write task whose last failure was
        ``TASK_TIMEOUT`` therefore carries a loud warning telling the caller to
        read the model state back first — and ``retry_count`` is consumed, so the
        budget in ``tasks.max_retries`` is real.
        """
        record = await self._require(task_id)
        if record.status in (TaskStatus.QUEUED.value, TaskStatus.RUNNING.value, TaskStatus.RETRYING.value):
            raise AdapterError(
                ErrorCode.TASK_ALREADY_RUNNING,
                f"任务 {task_id} 正在 {record.status!r}，不能重试（总纲 §4.4.6）。",
                details={"task_id": task_id, "status": record.status},
            )
        if record.status not in (TaskStatus.FAILED.value, TaskStatus.CANCELLED.value):
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR,
                f"只有 failed / cancelled 的任务可以重试，任务 {task_id} 处于 {record.status!r}",
                details={"task_id": task_id, "status": record.status},
            )
        if record.retry_count >= record.max_retries:
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR,
                f"任务 {task_id} 的重试预算已用尽"
                f"（retry_count={record.retry_count} / max_retries={record.max_retries}）",
                details={"task_id": task_id},
            )
        if record.runner is None:
            raise AdapterError(
                ErrorCode.NOT_IMPLEMENTED,
                f"任务 {task_id} 没有可重放的 runner。runner 是**进程内**对象、不落库"
                "（tasks.input_json 保存的是输入，不是可执行的处理器）：本进程创建的"
                "任务保留了可重放体，重启后加载的任务没有——Phase 2 由 tasks.input_json "
                "+ 处理器注册表承担。",
                details={"task_id": task_id},
            )
        timed_out_write = (
            record.is_write and record.error_code == ErrorCode.TASK_TIMEOUT.value
        )
        record.retry_count += 1
        record.status = TaskStatus.RETRYING.value
        record.error_code = None
        record.error_message = None
        record.result = None
        record.started_at = None
        record.finished_at = None
        await self._save(record)
        await self._emit(
            record,
            "retrying",
            progress=0.0,
            message=(
                f"显式重试 #{record.retry_count}（V2.1 §26.1 failed -> retrying -> running）。"
                + (
                    "⚠️ 上一次是**写操作超时**：重投前必须已读回模型状态"
                    "（V2.1 §26.5 / 对接规范 §3.5 第 5 条：超时 ≠ 回滚）。"
                    if timed_out_write
                    else ""
                )
            ),
            payload={"timed_out_write": timed_out_write},
        )
        self._schedule(record)
        return record.to_payload(include_result=False)

    async def result(self, task_id: str) -> dict[str, Any]:
        """``midas_task action=result`` — final payload (V2.1 §10.3 step 3)."""
        record = await self._require(task_id)
        terminal = record.status in TERMINAL_STATUSES
        return {
            "task_id": record.task_id,
            "status": record.status,
            "ready": terminal,
            "result": record.result if terminal else None,
            "error_code": record.error_code,
            "error_message": record.error_message,
            "finished_at": _iso(record.finished_at),
        }

    async def events(
        self,
        task_id: str,
        *,
        since: str | None = None,
        page: int = 1,
        page_size: int = 200,
    ) -> dict[str, Any]:
        """``midas_task action=events`` — incremental poll (V2.1 §10.3).

        ``since`` accepts either an event ``id`` (as a string) or an ISO-8601
        ``created_at`` cursor; the response echoes the cursor to pass back.  The
        id form is pushed down to the store (``TaskStore.load_events``'s ``since``
        parameter); the ISO form is filtered here.
        """
        record = await self._require(task_id)
        cursor = since.strip() if since else None
        threshold = int(cursor) if cursor is not None and cursor.isdigit() else None
        rows = await self._store.load_events(task_id, since=threshold)
        if cursor is not None and threshold is None:
            rows = [event for event in rows if event.created_at.isoformat() > cursor]
        page_payload = _paginate([event.to_payload() for event in rows], page, page_size)
        page_payload["task_id"] = record.task_id
        page_payload["status"] = record.status
        last = rows[-1] if rows else None
        page_payload["cursor"] = (
            _iso(last.created_at) if last is not None else since
        )
        return page_payload

    async def logs(self, task_id: str) -> dict[str, Any]:
        """``midas_task action=logs``.

        V2.1 §26.3 maps 日志 onto ``system_logs`` (which this milestone does not
        have), so the engine answers from the ``task_events`` rows it does keep,
        filtered to the log-ish event types.
        """
        await self._require(task_id)
        rows = [
            event
            for event in await self._store.load_events(task_id)
            if event.event_type in ("log", "warning", "error", "failed")
        ]
        return {
            "task_id": task_id,
            "items": [event.to_payload() for event in rows],
            "total": len(rows),
            "source": "task_events",
            "note": (
                "V2.1 §26.3 把日志落在 system_logs（含 task_id / adapter_request_id）；"
                "本里程碑尚未建该表，故此处回退为 task_events 中的日志类事件。"
            ),
        }

    # ------------------------------------------------------------------ #
    # lifecycle helpers
    # ------------------------------------------------------------------ #
    def emit_log(
        self, task_id: str, message: str, *, payload: Any = None
    ) -> TaskEventRecord:
        """Append a ``log`` event (V2.1 §26.3 「日志」).

        Synchronous by contract — this predates the async store protocol and is
        called from synchronous code — so it goes through the store's
        :class:`SyncTaskStore` mirror.  On a durable store that is one blocking
        insert; every other write path is asynchronous.
        """
        record = self._require_now(task_id)
        event = TaskEventRecord(
            id=0,
            task_id=record.task_id,
            event_type="log",
            progress=None,
            message=message,
            payload=payload,
            created_at=_utcnow(),
        )
        self._sync_store().save_event_now(event)
        return event

    async def recover_orphans(self) -> List[str]:
        # NOTE: ``List`` (typing), not the builtin ``list``.  This class defines a
        # ``list()`` method (V2.1 §10 ``midas_task action=list``), which shadows the
        # builtin ``list`` for the rest of the class body — and this annotation is
        # evaluated at class-definition time, so ``list[str]`` here raises
        # ``TypeError: 'function' object is not subscriptable`` at import.
        # The same trap already bit ``AdapterRegistry.codes()`` once; annotations
        # *inside* method bodies (e.g. ``recovered: list[str] = []`` below) are
        # unaffected, because local annotations are never evaluated at runtime.
        """Reconcile tasks a previous process left behind (V2.1 §26.1).

        A ``runner`` is an in-process object and is never stored, so after a
        restart every row still in ``queued`` / ``running`` / ``retrying`` is
        unmovable.  Each one becomes ``failed`` with
        ``error_code = INTERNAL_ERROR`` (总纲 §4.4.9) plus a ``failed`` event that
        says the process restarted — never a fabricated ``success``, never a
        silent ``running`` forever.

        Call this **once, at startup, before serving traffic**: see
        :func:`init_task_service`.  It is not a repair loop — a task that is
        legitimately ``queued`` in the live process (bookkeeping-only, no runner)
        is only ever examined here, when nothing is in flight.  Returns the
        recovered ``task_id`` list.
        """
        recovered: list[str] = []
        for record in await self._store.list_tasks():
            if record.status not in ORPHAN_STATUSES:
                continue
            previous = record.status
            record.status = TaskStatus.FAILED.value
            record.error_code = ErrorCode.INTERNAL_ERROR.value
            record.error_message = (
                f"进程重启：任务 {record.task_id} 在上一进程结束时处于 {previous!r}，"
                "其 runner 是进程内对象、无法跨进程恢复（V2.1 §26.1）。"
                "已置为 failed，且**不会**自动重投（V2.1 §26.5 / 对接规范 §3.5 第 5 条："
                "超时 ≠ 回滚，写操作可能已在上游落地）。如需继续，请人工判定后显式调用 "
                "midas_task action=retry。"
            )
            record.finished_at = _utcnow()
            await self._save(record)
            await self._emit(
                record,
                "failed",
                progress=record.progress,
                message=record.error_message,
                payload={
                    "error_code": ErrorCode.INTERNAL_ERROR.value,
                    "recovered": True,
                    "previous_status": previous,
                },
            )
            recovered.append(record.task_id)
        return recovered

    async def drain(self) -> None:
        """Await every in-flight worker (test / shutdown helper)."""
        while self._handles:
            pending = list(self._handles.values())
            await asyncio.gather(*pending, return_exceptions=True)

    def reset(self) -> None:
        """Drop the in-process state (test helper).  Cancels in-flight workers first.

        The default in-memory store is cleared with it.  A durable store keeps its
        rows: removing them is an explicit ``TaskStore.delete_task`` call, not a
        side effect of a test helper.
        """
        for handle in list(self._handles.values()):
            handle.cancel()
        self._handles.clear()
        self._records.clear()
        if isinstance(self._store, InMemoryTaskStore):
            self._store.reset()

    def __iter__(self) -> Iterator[TaskRecord]:
        return iter(self._records.values())


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
async def _await_result(value: Any) -> Any:
    """Await ``value`` when it is awaitable, else return it unchanged."""
    if hasattr(value, "__await__"):
        return await value
    return value


def _paginate(rows: Sequence[Any], page: int, page_size: int) -> dict[str, Any]:
    """``data.items`` + pagination fields (总纲 §4.3.1 分页统一为 items + pagination)."""
    size = max(1, min(int(page_size or 50), 500))
    current = max(1, int(page or 1))
    start = (current - 1) * size
    return {
        "total": len(rows),
        "page": current,
        "page_size": size,
        "items": list(rows[start : start + size]),
    }


# ---------------------------------------------------------------------------
# Process-wide singleton
# ---------------------------------------------------------------------------
_service: TaskService | None = None


def get_task_service() -> TaskService:
    """Process-wide :class:`TaskService` (mirrors ``get_registry()``)."""
    global _service
    if _service is None:
        _service = TaskService()
    return _service


def reset_task_service(service: TaskService | None = None) -> TaskService:
    """Replace the singleton (tests / reload)."""
    global _service
    _service = service if service is not None else TaskService()
    return _service


async def init_task_service(service: TaskService | None = None) -> TaskService:
    """Startup entry point: publish the singleton and reconcile restart orphans.

    This is the documented place :meth:`TaskService.recover_orphans` is called
    from.  Application bootstrap — the MCP server assembly in
    :mod:`app.mcp.server`, or the FastAPI lifespan in :func:`app.main.create_app`
    (which does wire it) — must ``await`` it once, after the durable store is
    wired and **before** any traffic is served: ``get_task_service()`` is
    synchronous and therefore cannot do it itself.

    Pass a service built on a :class:`SqlAlchemyTaskStore` to make tasks survive a
    restart; the default in-memory service has nothing to reconcile.
    """
    resolved = reset_task_service(service)
    await resolved.recover_orphans()
    return resolved
