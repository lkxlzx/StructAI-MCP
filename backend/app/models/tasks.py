"""Task engine persistence: ``tasks`` and ``task_events``.

V2.1 §4 tables 24–25 (semantics in V2.1 §26).

* ``tasks.type``   = business task type, closed 14-value enum (V2.1 §26.2, 裁决 A-6)
* ``tasks.action`` = concrete action, reuses the MCP action word list
* ``tasks.request_id`` carries the 总纲 §4.1.5 trace chain
  ``request_id → task_id → adapter_request_id``
* Foreign keys to ``tools(name)`` / ``adapters(code)`` come from 总纲 裁决 B-11
* ``task_events`` is append-only: no ``updated_at`` (总纲 §5.3 C-12)
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import TaskStatus, TaskType
from app.db.base import Base, CreatedAtMixin, TimestampMixin, enum_check, utcnow

__all__ = ["Task", "TaskEvent"]


class Task(TimestampMixin, Base):
    """One asynchronous task (V2.1 §4, table ``tasks``).

    Every operation that may exceed a few seconds enters this table and gets a
    ``task_`` prefixed ID (总纲 §4.1.4).
    """

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    #: Business ID, ``task_<yyyymmdd>_<6 digits>`` (总纲 §4.1.2).
    task_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    #: Parent ``task_id`` for sub-tasks / retries.
    parent_task_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("tasks.task_id", ondelete="SET NULL")
    )
    #: Business task type (V2.1 §26.2).
    type: Mapped[str] = mapped_column(Text, nullable=False)
    #: Concrete action, reuses the MCP action word list.
    action: Mapped[str] = mapped_column(Text, nullable=False)
    #: MCP resource name, singular (总纲 §4.6.1).
    resource: Mapped[str | None] = mapped_column(Text)
    tool_name: Mapped[str | None] = mapped_column(
        Text, ForeignKey("tools.name", ondelete="SET NULL")
    )
    adapter_code: Mapped[str | None] = mapped_column(
        Text, ForeignKey("adapters.code", ondelete="SET NULL")
    )
    midas_client_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("midas_clients.id", ondelete="SET NULL")
    )
    model_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("models.id", ondelete="SET NULL")
    )
    requested_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    #: 总纲 §4.2.1: queued / running / success / failed / cancelled / retrying.
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=TaskStatus.QUEUED.value, server_default=text("'queued'")
    )
    #: Completion percentage (unit: 0–100).
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default=text("0"))
    #: Scheduler priority, lower value = sooner (unit: level 1–9).
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5, server_default=text("5"))
    input_json: Mapped[str | None] = mapped_column(Text)
    result_json: Mapped[str | None] = mapped_column(Text)
    #: Always a 总纲 §4.4 registry code, e.g. ``TASK_TIMEOUT``.
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    #: Attempts already made (unit: count).
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    #: Retry budget (unit: count).
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default=text("3"))
    #: Request-trace ID, ``req_`` prefix (总纲 §4.1.5).
    request_id: Mapped[str | None] = mapped_column(Text)
    queued_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, server_default=func.current_timestamp()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    events: Mapped[list["TaskEvent"]] = relationship(
        "TaskEvent",
        back_populates="task",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TaskEvent.id",
    )

    __table_args__ = (
        enum_check("type", TaskType),
        enum_check("status", TaskStatus),
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_created_at", "created_at"),
        Index("ix_tasks_adapter", "adapter_code"),
        Index("ix_tasks_type", "type"),
        Index("ix_tasks_tool", "tool_name"),
        Index("ix_tasks_request_id", "request_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Task task_id={self.task_id!r} type={self.type!r} status={self.status!r}>"


class TaskEvent(CreatedAtMixin, Base):
    """Append-only task progress event (V2.1 §4, table ``task_events``).

    Polled by ``midas_task action=events`` — MCP has no push channel
    (总纲 裁决 B-9). No ``updated_at`` (总纲 §5.3 C-12).
    """

    __tablename__ = "task_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        Text, ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    #: Progress snapshot at event time (unit: 0–100).
    progress: Mapped[float | None] = mapped_column(Float)
    message: Mapped[str | None] = mapped_column(Text)
    payload_json: Mapped[str | None] = mapped_column(Text)

    task: Mapped["Task"] = relationship("Task", back_populates="events")

    __table_args__ = (Index("ix_task_events_task", "task_id", "created_at"),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<TaskEvent id={self.id} task_id={self.task_id!r} type={self.event_type!r}>"
