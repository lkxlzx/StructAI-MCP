"""Data management: backups, exports and imports.

V2.1 §4 tables 28–30. All three are job records with a shared status word list
(总纲 §4.2.5: processing / success / failed) and the same shape: business ID,
payload location, status, error, ``created_at`` + ``finished_at``.

Business IDs follow 总纲 §4.1.3: ``bk_`` / ``exp_`` / ``imp_``.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import JobStatus
from app.db.base import Base, CreatedAtMixin, enum_check

__all__ = ["Backup", "DataExport", "DataImport"]


class Backup(CreatedAtMixin, Base):
    """Database backup archive (V2.1 §4, table ``backups``).

    ID prefix ``bk_`` (总纲 §4.1.3). ``file_path`` is relative to the process
    working directory (总纲 裁决 C-10).
    """

    __tablename__ = "backups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backup_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    #: ``automatic`` / ``manual`` (free text in the DDL, no CHECK).
    type: Mapped[str] = mapped_column(Text, nullable=False, default="automatic", server_default=text("'automatic'"))
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    #: Archive size (unit: bytes).
    file_size: Mapped[int | None] = mapped_column(Integer)
    checksum: Mapped[str | None] = mapped_column(Text)
    #: 总纲 §4.2.5: processing / success / failed.
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=JobStatus.PROCESSING.value, server_default=text("'processing'")
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (enum_check("status", JobStatus),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Backup backup_id={self.backup_id!r} status={self.status!r}>"


class DataExport(CreatedAtMixin, Base):
    """Data export job (V2.1 §4, table ``data_exports``). ID prefix ``exp_``."""

    __tablename__ = "data_exports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    export_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    #: JSON describing the exported scope (tables / filters).
    scope_json: Mapped[str] = mapped_column(Text, nullable=False)
    #: ``json`` / ``csv`` / ``xlsx`` (free text in the DDL, no CHECK).
    format: Mapped[str] = mapped_column(Text, nullable=False, default="json", server_default=text("'json'"))
    file_path: Mapped[str | None] = mapped_column(Text)
    #: Archive size (unit: bytes).
    file_size: Mapped[int | None] = mapped_column(Integer)
    #: 总纲 §4.2.5: processing / success / failed.
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=JobStatus.PROCESSING.value, server_default=text("'processing'")
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (enum_check("status", JobStatus),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<DataExport export_id={self.export_id!r} status={self.status!r}>"


class DataImport(CreatedAtMixin, Base):
    """Data import job (V2.1 §4, table ``data_imports``). ID prefix ``imp_``."""

    __tablename__ = "data_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    import_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    #: JSON describing the imported scope; NULL means "whole archive".
    scope_json: Mapped[str | None] = mapped_column(Text)
    #: 总纲 §4.2.5: processing / success / failed.
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=JobStatus.PROCESSING.value, server_default=text("'processing'")
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (enum_check("status", JobStatus),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<DataImport import_id={self.import_id!r} status={self.status!r}>"
