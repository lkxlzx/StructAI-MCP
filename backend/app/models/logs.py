"""Operational logs and audit trail.

V2.1 §4 tables 26–27. Both tables are append-only: they carry ``created_at``
(``system_logs`` names it ``timestamp``) and deliberately **no** ``updated_at``
(总纲 §5.3 C-12).

Indexes ``ix_system_logs_task`` / ``ix_system_logs_module_time`` and
``ix_audit_logs_user`` / ``ix_audit_logs_resource`` come from 总纲 裁决 B-12.
``system_logs.adapter_request_id`` closes the §4.1.5 trace chain.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, utcnow

__all__ = ["SystemLog", "AuditLog"]


class SystemLog(Base):
    """Application log line (V2.1 §4, table ``system_logs``).

    Append-only. The timestamp column is named ``timestamp`` (not
    ``created_at``) exactly as in the DDL.
    """

    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, server_default=func.current_timestamp()
    )
    #: Python logging level name, e.g. ``INFO`` / ``ERROR``.
    level: Mapped[str] = mapped_column(Text, nullable=False)
    module: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    task_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("tasks.task_id", ondelete="SET NULL")
    )
    #: Trace chain terminal, ``adapter_`` prefix (总纲 §4.1.5).
    adapter_request_id: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    #: Request-trace ID, ``req_`` prefix (总纲 §4.1.5).
    request_id: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_system_logs_time", "timestamp"),
        Index("ix_system_logs_level", "level"),
        Index("ix_system_logs_module", "module"),
        Index("ix_system_logs_task", "task_id"),
        Index("ix_system_logs_module_time", "module", "timestamp"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<SystemLog id={self.id} level={self.level!r} module={self.module!r}>"


class AuditLog(CreatedAtMixin, Base):
    """Audit trail entry for mutating operations (V2.1 §4, table ``audit_logs``).

    Append-only (总纲 §5.3 C-12). ``before_json`` / ``after_json`` hold the
    change payload; secrets must be masked before they are written here
    (总纲 §4.7.2).
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str | None] = mapped_column(Text)
    resource_id: Mapped[str | None] = mapped_column(Text)
    #: HTTP method of the triggering call.
    method: Mapped[str | None] = mapped_column(Text)
    path: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(Text)
    before_json: Mapped[str | None] = mapped_column(Text)
    after_json: Mapped[str | None] = mapped_column(Text)
    #: Outcome marker, e.g. ``success`` / ``failed``.
    result: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_audit_logs_time", "created_at"),
        Index("ix_audit_logs_user", "user_id"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AuditLog id={self.id} action={self.action!r}>"
