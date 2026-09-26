"""Shared declarative base, mixins and ORM helpers.

Conventions enforced here:

* **Naming** (总纲 §4.6): ``ix_<table>_<column>`` / ``ux_<table>_<column>`` /
  ``ck_<table>_<constraint>`` / ``fk_<table>_<column>`` / ``pk_<table>``.
  SQLAlchemy's convention token for unique constraints is ``uq`` (there is no
  ``ux`` token), so ``uq`` is mapped onto the ``ux_`` prefix required by §4.6.
* **Time** (总纲 §4.5.1): timestamps are stored as UTC and maintained by the
  **ORM** (``default`` / ``onupdate``). No ``CREATE TRIGGER`` anywhere.
  ``server_default=CURRENT_TIMESTAMP`` mirrors the raw-SQL fallback documented
  in V2.1 §3.2 and is never the primary source of truth.
* **Booleans** (V2.1 §3.1): stored as ``INTEGER`` 0/1, never as a native
  ``BOOLEAN`` column.
* **Units** (总纲 §4.5.2): every numeric column carries a unit comment in the
  model module (m / mm / kN / kN/m / MPa / kg / 0-100 / 0.0-1.0).

Note on reads: SQLite has no native ``DATETIME``; values come back naive but
carry UTC wall-clock time. Convert with :func:`to_configured_timezone` at the
API boundary.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Iterator

from sqlalchemy import CheckConstraint, DateTime, Integer, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.core import constants as C

__all__ = [
    "Base",
    "utcnow",
    "to_configured_timezone",
    "session_scope_for",
    "BoolInt",
    "NAMING_CONVENTION",
    "CreatedAtMixin",
    "UpdatedAtMixin",
    "TimestampMixin",
    "SoftDeleteMixin",
    "enum_check",
    "single_row_check",
]


def utcnow() -> datetime:
    """Current instant in UTC (总纲 §4.5.1 — all timestamps are stored as UTC)."""
    return datetime.now(timezone.utc)


@contextmanager
def session_scope_for(session_factory: Callable[[], Session]) -> Iterator[Session]:
    """Transactional scope over an **arbitrary** session factory.

    :func:`app.db.session.session_scope` is bound to the process-wide
    ``SessionLocal``.  A service that must be pointable at another database — the
    Task Engine's durable store, or a test using a ``tmp_path`` SQLite file —
    needs the same contract over a factory it was handed: commit on success, roll
    back on any exception, always close.  There is exactly one implementation, so
    the two forms cannot drift.
    """
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def to_configured_timezone(value: datetime | None) -> datetime | None:
    """Attach UTC to a naive DB value and convert it to the configured zone.

    API output must be ISO 8601 with an offset, default ``+08:00`` (总纲 §4.5.1).
    """
    if value is None:
        return None
    from app.core.config import get_settings  # local import avoids a cycle

    moment = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    try:
        from zoneinfo import ZoneInfo

        return moment.astimezone(ZoneInfo(get_settings().timezone))
    except Exception:  # pragma: no cover - bad tz name / missing tzdata
        return moment


#: V2.1 §3.1 — "布尔：INTEGER 0/1". Use this alias so the intent is visible.
BoolInt = Integer

#: 总纲 §4.6 naming conventions.
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "ux_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for all 49 StructAI tables (V2.1 §4)."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class CreatedAtMixin:
    """``created_at`` only — used by append-only / immutable-row tables."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow,
        server_default=func.current_timestamp(),
    )


class UpdatedAtMixin:
    """``updated_at`` only — used by the singleton configuration tables."""

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.current_timestamp(),
    )


class TimestampMixin(CreatedAtMixin, UpdatedAtMixin):
    """``created_at`` + ``updated_at`` maintained by the ORM (裁决 B-6).

    Append-only tables (``task_events`` / ``system_logs`` / ``audit_logs`` /
    ``user_roles`` / ``role_permissions``) must **not** use this mixin — see
    总纲 §5.3 C-12.
    """


class SoftDeleteMixin:
    """``deleted_at`` for soft deletion (V2.1 §3.1: "删除：优先软删除")."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )


def enum_check(column: str, enum_cls: type[Enum]) -> CheckConstraint:
    """Build a CHECK constraint from a 总纲 §4.2 enum.

    The SQL is generated from the enum values, so a word-list change in
    :mod:`app.core.constants` propagates to the DDL automatically. The
    constraint is named after the column, which the ``ck_`` naming convention
    turns into ``ck_<table>_<column>`` (总纲 §4.6).
    """
    return CheckConstraint(C.check_sql(column, enum_cls), name=column)


def single_row_check(column: str = "id") -> CheckConstraint:
    """CHECK enforcing the ``id = 1`` singleton pattern used by config tables."""
    return CheckConstraint(f"{column} = 1", name="single_row")
