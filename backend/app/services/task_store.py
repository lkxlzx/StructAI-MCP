"""Durable storage for the Task Engine — V2.1 §26 / 总纲 §4.1.5, §4.2.1, §4.5.1.

Authoritative sources
---------------------
* V2.1 §26.1 状态流转 — ``queued -> running -> success | failed -> retrying``,
  ``running -> cancelled``; the six values are verbatim ``tasks.status``
  (总纲 §4.2.1).
* V2.1 §26.2 ``tasks.type`` — closed 14-value business task type (裁决 A-6).
* V2.1 §26.3 职责「落库对应」 — 事件 -> ``task_events``, 结果 ->
  ``tasks.result_json``, 进度 -> ``tasks.progress``, 重试 -> ``tasks.retry_count``
  / ``tasks.max_retries``, 排队 -> ``tasks.status`` / ``tasks.priority``.
* V2.1 §26.4 / 总纲 §4.1.5 — ``request_id -> task_id -> adapter_request_id``;
  ``tasks.request_id`` carries the middle link.
* 总纲 §4.1.3 / §4.1.4 — the only task prefix is ``task_``; no sub-type prefix.
* 总纲 §4.2.1 — ``tasks.status`` is a **closed** set.  This module refuses to
  write anything else *and* the ``tasks`` table carries the matching CHECK
  (裁决 B-10), so the rule holds from both ends.
* 总纲 §4.5.1 — ``created_at`` / ``updated_at`` are maintained by the **ORM**
  (``default`` / ``onupdate``); nothing here writes them by hand and there is no
  ``CREATE TRIGGER`` anywhere.

Why the record types live here
------------------------------
:class:`TaskRecord` / :class:`TaskEventRecord` are the field-for-field Python
mirrors of ``app.models.tasks.Task`` / ``TaskEvent``.  They are defined in this
module — not in :mod:`app.services.task_service` — because the store protocol is
stated in terms of them and ``task_service`` imports the store; keeping them here
is what makes the dependency one-way.  :mod:`app.services.task_service`
re-exports both names, so ``from app.services.task_service import TaskRecord``
(and ``app.services``) keeps working unchanged.

Restart semantics — read this before wiring a durable store
-----------------------------------------------------------
``TaskRecord.runner`` is a live coroutine factory and is **never persisted**, so a
restart leaves every non-terminal row (``queued`` / ``running`` / ``retrying``)
with no way to make progress.  Leaving such a row ``running`` forever would be a
lie and fabricating ``success`` would be worse; therefore
:meth:`app.services.task_service.TaskService.recover_orphans` marks each orphan
``failed`` with ``error_code = INTERNAL_ERROR`` plus a ``task_events`` row that
explains the process restarted.  It is called from the documented startup entry
point :func:`app.services.task_service.init_task_service`, before traffic is
served.

``timeout_seconds`` and ``is_write`` are engine-side too and are not persisted:
a recovered task is already ``failed``, so neither is needed again.

Sync vs async
-------------
The models are **synchronous** SQLAlchemy 2.x declarative and
:mod:`app.db.session` exposes a sync ``sessionmaker`` (``SessionLocal``) — there
is no async engine and this module does not add a second driver.  The protocol is
``async`` because the Task Engine runs on the event loop, and every
:class:`SqlAlchemyTaskStore` method therefore hands the blocking work to
:func:`asyncio.to_thread`, opening its ``Session`` **inside** the worker thread
(a ``Session`` is not thread-safe, so it is never shared between calls).

:class:`SyncTaskStore` is the synchronous mirror used by exactly one pre-existing
call site — :meth:`app.services.task_service.TaskService.emit_log`, which is a
``def`` and cannot await (V2.1 §26.3 「日志」).
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Protocol, runtime_checkable

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.adapters.errors import AdapterError
from app.core.constants import TaskStatus
from app.core.errors import ErrorCode
from app.db.base import session_scope_for
from app.models.tasks import Task, TaskEvent

__all__ = [
    "TaskRecord",
    "TaskEventRecord",
    "TaskStore",
    "SyncTaskStore",
    "InMemoryTaskStore",
    "SqlAlchemyTaskStore",
    "TASK_STATUS_VALUES",
    "DEFAULT_TASK_TIMEOUT_SECONDS",
    "DEFAULT_MAX_RETRIES",
    "utcnow",
    "iso",
]

#: V2.1 §26.3: 超时 -> ``tasks.finished_at`` + ``error_code='TASK_TIMEOUT'``.
DEFAULT_TASK_TIMEOUT_SECONDS: float = 300.0

#: V2.1 §26.3: 重试预算.  Only ever consumed by an **explicit** retry call —
#: the engine never retries on its own (V2.1 §26.5).
DEFAULT_MAX_RETRIES: int = 3

#: 总纲 §4.2.1 — the closed ``tasks.status`` vocabulary, as plain strings.
TASK_STATUS_VALUES: frozenset[str] = frozenset(
    member.value for member in TaskStatus
)


def utcnow() -> datetime:
    """Timezone-aware UTC now (总纲 §4.5.1: 存储 UTC, 传输 ISO 8601 带时区)."""
    return datetime.now(timezone.utc)


def iso(moment: datetime | None) -> str | None:
    """Render an instant as ISO 8601, or ``None`` (总纲 §4.5.1)."""
    return moment.isoformat() if moment is not None else None


def _as_utc(value: datetime | None) -> datetime | None:
    """Re-attach UTC to a value that came back naive from SQLite.

    ``app.db.base`` documents the situation: SQLite has no native ``DATETIME``,
    so a stored UTC wall clock comes back naive.  Normalising here keeps
    ``to_payload()`` byte-identical between the in-memory and the SQL store —
    which is what makes the ``since`` ISO cursor interchangeable.
    """
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _dump(value: Any) -> str | None:
    """Serialise ``input`` / ``result`` / ``payload`` to JSON text (V2.1 §26.3).

    ``None`` is stored as SQL ``NULL`` (not ``"null"``) so the round-trip is
    exact.  ``ensure_ascii=False`` keeps CJK payloads readable in the database and
    still round-trips them exactly.
    """
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _load(raw: str | None) -> Any:
    """Inverse of :func:`_dump`."""
    if raw is None:
        return None
    return json.loads(raw)


def _require_closed_status(status: str) -> str:
    """Refuse to write a ``tasks.status`` outside 总纲 §4.2.1 — loudly.

    The table CHECK (裁决 B-10) is the backstop, but it would surface as an
    opaque ``IntegrityError`` after a round trip to the database; this raises the
    总纲 §4.4 ``VALIDATION_ERROR`` the caller can act on, and never writes.
    """
    if status not in TASK_STATUS_VALUES:
        raise AdapterError(
            ErrorCode.VALIDATION_ERROR,
            f"未知的 tasks.status={status!r}；总纲 §4.2.1 的封闭集合为 "
            f"{sorted(TASK_STATUS_VALUES)}",
            details={"status": status},
        )
    return status


# ---------------------------------------------------------------------------
# Rows — field-for-field mirrors of app.models.tasks
# ---------------------------------------------------------------------------
@dataclass
class TaskEventRecord:
    """One ``task_events`` row (append-only, 总纲 §5.3 C-12 — no ``updated_at``).

    ``id`` is assigned by the store: the SQL store reads it back from the
    autoincrement primary key (总纲 §4.1.1), the in-memory store from one
    process-wide counter.  :meth:`TaskService._emit` therefore builds the record
    with ``id=0`` and lets ``save_event`` fill it in.
    """

    id: int
    task_id: str
    event_type: str
    progress: float | None
    message: str | None
    payload: Any
    created_at: datetime

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "event_type": self.event_type,
            "progress": self.progress,
            "message": self.message,
            "payload": self.payload,
            "created_at": iso(self.created_at),
        }


@dataclass
class TaskRecord:
    """One ``tasks`` row.

    Every field up to ``finished_at`` maps 1:1 onto a column; the three fields
    after it are engine-side and deliberately not persisted (see the module
    docstring).
    """

    task_id: str
    type: str
    action: str
    resource: str | None = None
    tool_name: str | None = None
    adapter_code: str | None = None
    midas_client_id: int | None = None
    model_id: int | None = None
    requested_by: int | None = None
    status: str = TaskStatus.QUEUED.value
    progress: float = 0.0
    priority: int = 5
    input: Any = None
    result: Any = None
    error_code: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    max_retries: int = DEFAULT_MAX_RETRIES
    #: 总纲 §4.1.5 — the ``request_id`` end of the trace chain.
    request_id: str | None = None
    parent_task_id: str | None = None
    queued_at: datetime = field(default_factory=utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    #: Engine-side, not persisted.
    timeout_seconds: float = DEFAULT_TASK_TIMEOUT_SECONDS
    #: True when a timeout must **not** trigger an automatic retry (V2.1 §26.5).
    is_write: bool = True
    #: The replayable body.  **Not persisted** — a restart leaves no runner, which
    #: is exactly what ``recover_orphans()`` reconciles.
    runner: Callable[[], Awaitable[Any]] | None = field(default=None, repr=False)

    def to_payload(self, *, include_result: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "task_id": self.task_id,
            "parent_task_id": self.parent_task_id,
            "type": self.type,
            "action": self.action,
            "resource": self.resource,
            "tool_name": self.tool_name,
            "adapter_code": self.adapter_code,
            "midas_client_id": self.midas_client_id,
            "status": self.status,
            "progress": self.progress,
            "priority": self.priority,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "request_id": self.request_id,
            "queued_at": iso(self.queued_at),
            "started_at": iso(self.started_at),
            "finished_at": iso(self.finished_at),
            "is_write": self.is_write,
        }
        if include_result:
            payload["result"] = self.result
        return payload


# ---------------------------------------------------------------------------
# The protocol
# ---------------------------------------------------------------------------
@runtime_checkable
class TaskStore(Protocol):
    """Durable storage for ``tasks`` / ``task_events`` (V2.1 §26.3).

    ``InMemoryTaskStore`` reproduces the pre-persistence behaviour exactly, so the
    offline suite stays fast and needs no database; ``SqlAlchemyTaskStore`` writes
    the two tables of V2.1 §4.  Both are interchangeable for every caller.
    """

    async def save_task(self, record: TaskRecord) -> None:
        """Insert or update the row for ``record.task_id`` — never a duplicate."""
        ...

    async def load_task(self, task_id: str) -> TaskRecord | None:
        """Return the stored record, or ``None`` when the task is unknown."""
        ...

    async def list_tasks(self, *, requested_by: int | None = None) -> list[TaskRecord]:
        """Return stored tasks (unordered; the service sorts).

        ``requested_by`` is the **ownership scope** of v1.2 §20.1 / §21: when it
        is given, only rows whose ``tasks.requested_by`` is that user **or is
        NULL** are returned.  NULL means the task was created without attribution
        — authentication is off (总纲 裁决 C-13) or the caller was anonymous — so
        there is no owner to filter by and the row stays visible; that is the same
        rule :func:`app.main._task_visible_to` applies per row.  ``None`` (the
        default) applies no ownership filter at all and is reserved for
        ``super_admin`` and for internal callers.

        The filter belongs **here**, in the query, and not in the caller: it is
        the only place that can keep a page and its total consistent.
        """
        ...

    async def save_event(self, event: TaskEventRecord) -> None:
        """Append one event and assign its ``id`` (总纲 §5.3 C-12: append-only)."""
        ...

    async def load_events(
        self, task_id: str, *, since: int | None = None
    ) -> list[TaskEventRecord]:
        """Return the task's events in id order.

        ``since`` is an **event id cursor**: only events with a strictly greater
        ``id`` are returned, which is what ``midas_task action=events`` polls with
        (V2.1 §10.3).
        """
        ...

    async def delete_task(self, task_id: str) -> bool:
        """Delete the task and its events; ``True`` when a row existed."""
        ...


@runtime_checkable
class SyncTaskStore(Protocol):
    """Synchronous mirror of :class:`TaskStore` for the legacy sync call site.

    :meth:`app.services.task_service.TaskService.emit_log` is a plain ``def`` that
    predates the async protocol and is called synchronously by existing code, so
    it cannot await.  Both shipped stores implement this mirror, which keeps that
    one call site working unchanged while every other write goes through the async
    protocol.  The async methods remain the primary interface.
    """

    def load_task_now(self, task_id: str) -> TaskRecord | None:
        """Blocking :meth:`TaskStore.load_task`."""
        ...

    def save_event_now(self, event: TaskEventRecord) -> None:
        """Blocking :meth:`TaskStore.save_event`."""
        ...


# ---------------------------------------------------------------------------
# In-memory store — today's behaviour, unchanged
# ---------------------------------------------------------------------------
class InMemoryTaskStore:
    """Process-memory store: exactly the pre-persistence Task Engine behaviour.

    ``save_task`` keeps the caller's object and ``load_task`` hands the *same*
    object back, so the in-flight mutations of ``TaskService._drive`` and the live
    ``runner`` stay visible to every reader.  Event ids come from one process-wide
    monotonic counter, as before.
    """

    #: False: nothing survives a restart.  Read by ``midas_task`` so its answer can
    #: state the real durability instead of a blanket Phase-2 caveat.
    durable: bool = False

    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}
        self._events: dict[str, list[TaskEventRecord]] = {}
        self._event_sequence: int = 0

    # -- tasks --------------------------------------------------------- #
    async def save_task(self, record: TaskRecord) -> None:
        self.save_task_now(record)

    def save_task_now(self, record: TaskRecord) -> None:
        _require_closed_status(record.status)
        self._tasks[record.task_id] = record

    async def load_task(self, task_id: str) -> TaskRecord | None:
        return self.load_task_now(task_id)

    def load_task_now(self, task_id: str) -> TaskRecord | None:
        return self._tasks.get(task_id)

    async def list_tasks(self, *, requested_by: int | None = None) -> list[TaskRecord]:
        rows = list(self._tasks.values())
        if requested_by is not None:
            scope = int(requested_by)
            # **Fail closed.**  An unattributed row (``requested_by IS NULL``)
            # belongs to nobody, so only an *unfiltered* caller sees it —
            # ``super_admin``, or a deployment with authentication switched off,
            # both of which pass ``requested_by=None`` and never reach this branch.
            #
            # Treating NULL as "public" would silently publish a user's whole task
            # history the moment that user was hard-deleted, because
            # ``tasks.requested_by`` is ``ON DELETE SET NULL`` (V2.1 §4).  A
            # security control must not fail open.
            rows = [record for record in rows if record.requested_by == scope]
        return rows

    # -- events -------------------------------------------------------- #
    async def save_event(self, event: TaskEventRecord) -> None:
        self.save_event_now(event)

    def save_event_now(self, event: TaskEventRecord) -> None:
        self._event_sequence += 1
        event.id = self._event_sequence
        self._events.setdefault(event.task_id, []).append(event)

    async def load_events(
        self, task_id: str, *, since: int | None = None
    ) -> list[TaskEventRecord]:
        rows = list(self._events.get(task_id, []))
        if since is not None:
            rows = [event for event in rows if event.id > since]
        return rows

    # -- removal ------------------------------------------------------- #
    async def delete_task(self, task_id: str) -> bool:
        existed = self._tasks.pop(task_id, None) is not None
        self._events.pop(task_id, None)
        return existed

    def reset(self) -> None:
        """Drop everything (test helper, mirrors ``TaskService.reset``)."""
        self._tasks.clear()
        self._events.clear()
        self._event_sequence = 0


# ---------------------------------------------------------------------------
# SQLAlchemy store — tasks / task_events
# ---------------------------------------------------------------------------
class SqlAlchemyTaskStore:
    """Persist to ``tasks`` / ``task_events`` (V2.1 §4 tables 24–25).

    ``session_factory`` is any zero-argument callable returning a
    :class:`sqlalchemy.orm.Session` — a ``sessionmaker`` (for example
    :data:`app.db.session.SessionLocal`) or a lambda around one.  Taking the
    factory instead of reaching for the module global is what lets a test point
    two services at the same ``tmp_path`` SQLite file.

    The session layer is **synchronous** (see :mod:`app.db.session`); every call
    is therefore wrapped in :func:`asyncio.to_thread` and opens its own session
    inside the worker thread.
    """

    #: True: rows live in ``tasks`` / ``task_events`` and survive a restart.
    durable: bool = True

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # -- tasks --------------------------------------------------------- #
    async def save_task(self, record: TaskRecord) -> None:
        await asyncio.to_thread(self.save_task_now, record)

    def save_task_now(self, record: TaskRecord) -> None:
        """Blocking upsert of one ``tasks`` row, keyed on ``task_id``.

        Idempotent by construction: the row is looked up by its UNIQUE business ID
        (总纲 §4.1.2) and updated in place, so a second save of the same task is an
        ``UPDATE`` and never a duplicate ``INSERT``.
        """
        _require_closed_status(record.status)
        with session_scope_for(self._session_factory) as session:
            row = session.scalar(select(Task).where(Task.task_id == record.task_id))
            if row is None:
                row = Task(task_id=record.task_id)
                session.add(row)
            _apply_record(row, record)
            session.flush()

    async def load_task(self, task_id: str) -> TaskRecord | None:
        return await asyncio.to_thread(self.load_task_now, task_id)

    def load_task_now(self, task_id: str) -> TaskRecord | None:
        with session_scope_for(self._session_factory) as session:
            row = session.scalar(select(Task).where(Task.task_id == task_id))
            return _to_record(row) if row is not None else None

    async def list_tasks(self, *, requested_by: int | None = None) -> list[TaskRecord]:
        return await asyncio.to_thread(self.list_tasks_now, requested_by)

    def list_tasks_now(self, requested_by: int | None = None) -> list[TaskRecord]:
        """Blocking :meth:`TaskStore.list_tasks`, with the ownership filter in SQL.

        ``WHERE requested_by = :scope`` — the filter is **fail closed**: an
        unattributed row is not matched, so it is visible only to an unfiltered
        caller.  See :meth:`InMemoryTaskStore.list_tasks` for why NULL must not
        mean "public", and note the two implementations must agree exactly.
        """
        with session_scope_for(self._session_factory) as session:
            statement = select(Task)
            if requested_by is not None:
                statement = statement.where(Task.requested_by == int(requested_by))
            rows = session.scalars(
                statement.order_by(Task.priority, Task.queued_at, Task.id)
            ).all()
            return [_to_record(row) for row in rows]

    # -- events -------------------------------------------------------- #
    async def save_event(self, event: TaskEventRecord) -> None:
        await asyncio.to_thread(self.save_event_now, event)

    def save_event_now(self, event: TaskEventRecord) -> None:
        """Append one ``task_events`` row and mirror the assigned id back.

        ``created_at`` is left to the ORM (总纲 §4.5.1); the value it picked is
        copied onto the record so the caller's object matches the stored row.
        """
        with session_scope_for(self._session_factory) as session:
            row = TaskEvent(
                task_id=event.task_id,
                event_type=event.event_type,
                progress=event.progress,
                message=event.message,
                payload_json=_dump(event.payload),
            )
            session.add(row)
            session.flush()
            event.id = int(row.id)
            event.created_at = _as_utc(row.created_at) or event.created_at

    async def load_events(
        self, task_id: str, *, since: int | None = None
    ) -> list[TaskEventRecord]:
        return await asyncio.to_thread(self.load_events_now, task_id, since)

    def load_events_now(
        self, task_id: str, since: int | None = None
    ) -> list[TaskEventRecord]:
        with session_scope_for(self._session_factory) as session:
            statement = select(TaskEvent).where(TaskEvent.task_id == task_id)
            if since is not None:
                statement = statement.where(TaskEvent.id > since)
            rows = session.scalars(statement.order_by(TaskEvent.id)).all()
            return [_to_event(row) for row in rows]

    # -- removal ------------------------------------------------------- #
    async def delete_task(self, task_id: str) -> bool:
        return await asyncio.to_thread(self.delete_task_now, task_id)

    def delete_task_now(self, task_id: str) -> bool:
        """Delete one task; ``task_events`` rows go with it.

        Deliberately a **Core** ``DELETE`` against the ``tasks`` table: the cascade
        is declared in the DDL (``ON DELETE CASCADE``, V2.1 §4) and must stay the
        database's work, so nothing here loads the child rows first.  It therefore
        depends on ``PRAGMA foreign_keys=ON`` — which :mod:`app.db.session` sets on
        every connection.
        """
        tasks = Task.__table__
        with session_scope_for(self._session_factory) as session:
            result = session.execute(delete(tasks).where(tasks.c.task_id == task_id))
            return bool(result.rowcount)


# ---------------------------------------------------------------------------
# row <-> record mapping
# ---------------------------------------------------------------------------
def _apply_record(row: Task, record: TaskRecord) -> None:
    """Map a :class:`TaskRecord` onto a ``tasks`` row, field by field.

    ``created_at`` / ``updated_at`` are deliberately absent: 总纲 §4.5.1 requires
    the ORM mixin (``default`` / ``onupdate``) to own them, so writing them here
    would both duplicate and freeze a value the ORM is supposed to refresh.
    ``queued_at`` is a domain column, not an ORM-maintained one, so it is written.
    """
    row.parent_task_id = record.parent_task_id
    row.type = record.type
    row.action = record.action
    row.resource = record.resource
    row.tool_name = record.tool_name
    row.adapter_code = record.adapter_code
    row.midas_client_id = record.midas_client_id
    row.model_id = record.model_id
    row.requested_by = record.requested_by
    row.status = record.status
    row.progress = record.progress
    row.priority = record.priority
    row.input_json = _dump(record.input)
    row.result_json = _dump(record.result)
    row.error_code = record.error_code
    row.error_message = record.error_message
    row.retry_count = record.retry_count
    row.max_retries = record.max_retries
    row.request_id = record.request_id
    row.queued_at = record.queued_at
    row.started_at = record.started_at
    row.finished_at = record.finished_at


def _to_record(row: Task) -> TaskRecord:
    """Map a ``tasks`` row back onto a :class:`TaskRecord`.

    ``timeout_seconds`` / ``is_write`` / ``runner`` take their dataclass defaults:
    they are engine-side and were never stored.
    """
    return TaskRecord(
        task_id=row.task_id,
        type=row.type,
        action=row.action,
        resource=row.resource,
        tool_name=row.tool_name,
        adapter_code=row.adapter_code,
        midas_client_id=row.midas_client_id,
        model_id=row.model_id,
        requested_by=row.requested_by,
        status=row.status,
        progress=row.progress,
        priority=row.priority,
        input=_load(row.input_json),
        result=_load(row.result_json),
        error_code=row.error_code,
        error_message=row.error_message,
        retry_count=row.retry_count,
        max_retries=row.max_retries,
        request_id=row.request_id,
        parent_task_id=row.parent_task_id,
        queued_at=_as_utc(row.queued_at) or utcnow(),
        started_at=_as_utc(row.started_at),
        finished_at=_as_utc(row.finished_at),
    )


def _to_event(row: TaskEvent) -> TaskEventRecord:
    """Map a ``task_events`` row back onto a :class:`TaskEventRecord`."""
    return TaskEventRecord(
        id=int(row.id),
        task_id=row.task_id,
        event_type=row.event_type,
        progress=row.progress,
        message=row.message,
        payload=_load(row.payload_json),
        created_at=_as_utc(row.created_at) or utcnow(),
    )
