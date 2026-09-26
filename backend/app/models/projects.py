"""Projects and reports.

V2.1 §4 tables 31–32 (added by 总纲 裁决 N-7 and B-5).

.. note:: **Documented 总纲 ↔ V2.1 disagreement.**
  裁决 N-6 states that ``project_id`` and ``file_id`` are "一律 INTEGER".
  V2.1 §4 — which 总纲 §3 ownership matrix row #1 makes the *sole owner* of the
  DDL — declares ``projects.project_id TEXT UNIQUE``, ``reports.project_id TEXT``
  (FK to that business ID) and ``reports.file_id TEXT`` (FK to
  ``assistant_files.file_id``). 总纲 §4.1.3 does not define a project prefix at
  all. These models follow V2.1 §4 because it owns the table definitions; the
  conflict is flagged for the owner to reconcile.
"""

from datetime import datetime

from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ProjectStatus, ReportStatus, ReportType
from app.db.base import Base, CreatedAtMixin, SoftDeleteMixin, TimestampMixin, enum_check

__all__ = ["Project", "Report"]


class Project(TimestampMixin, SoftDeleteMixin, Base):
    """Engineering project (V2.1 §4, table ``projects``).

    ``project_id`` is a TEXT business ID per the DDL; see the module docstring
    for the 裁决 N-6 conflict.
    """

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    #: 总纲 §4.2.8: active / archived.
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=ProjectStatus.ACTIVE.value, server_default=text("'active'")
    )
    metadata_json: Mapped[str | None] = mapped_column(Text)

    reports: Mapped[list["Report"]] = relationship(
        "Report", back_populates="project", lazy="selectin"
    )

    __table_args__ = (
        enum_check("status", ProjectStatus),
        Index("ix_projects_owner", "owner_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Project project_id={self.project_id!r} code={self.code!r}>"


class Report(CreatedAtMixin, Base):
    """Generated report entity (V2.1 §4, table ``reports``; 总纲 裁决 B-5).

    ID prefix ``rpt_`` (总纲 §4.1.3). ``file_id`` points at the produced artifact
    in ``assistant_files`` (裁决 N-23: files hold the bytes, outputs/reports hold
    the semantics).
    """

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    task_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("tasks.task_id", ondelete="SET NULL")
    )
    project_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("projects.project_id", ondelete="SET NULL")
    )
    model_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("models.id", ondelete="SET NULL")
    )
    #: 总纲 §4.2.9: calculation / analysis / design / check / custom.
    report_type: Mapped[str] = mapped_column(
        Text, nullable=False, default=ReportType.CALCULATION.value, server_default=text("'calculation'")
    )
    #: Output format, e.g. ``pdf`` / ``docx`` (free text in the DDL, no CHECK).
    format: Mapped[str] = mapped_column(Text, nullable=False, default="pdf", server_default=text("'pdf'"))
    #: JSON array of included sections (裁决 N-14: ``report_type`` + ``include[]``).
    include_json: Mapped[str | None] = mapped_column(Text)
    file_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("assistant_files.file_id", ondelete="SET NULL")
    )
    #: 总纲 §4.2.9: processing / success / failed.
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=ReportStatus.PROCESSING.value, server_default=text("'processing'")
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="reports")

    __table_args__ = (
        enum_check("report_type", ReportType),
        enum_check("status", ReportStatus),
        Index("ix_reports_task", "task_id"),
        Index("ix_reports_project", "project_id"),
        Index("ix_reports_status", "status"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Report report_id={self.report_id!r} type={self.report_type!r} status={self.status!r}>"
