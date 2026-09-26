"""Engine, session factory and SQLite pragmas.

``PRAGMA foreign_keys=ON`` is mandatory: V2.1 §4 relies on ``ON DELETE`` actions
and SQLite disables foreign-key enforcement by default. ``journal_mode=WAL``
gives the concurrent reader/writer behaviour the Task Engine needs.

The engine is created at import time from :func:`app.core.config.get_settings`,
so importing this module is enough to obtain a usable database handle.
"""

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import session_scope_for

__all__ = ["engine", "SessionLocal", "get_session", "session_scope"]

_settings = get_settings()


def _ensure_sqlite_directory(url: str) -> None:
    """Create the parent directory of a file-backed SQLite database."""
    if not url.startswith("sqlite"):
        return
    _, _, raw = url.partition(":///")
    if not raw or raw == ":memory:" or raw.startswith("file:"):
        return
    parent = Path(raw).expanduser().parent
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_directory(_settings.database_url)

_connect_args: dict[str, object] = {}
if _settings.is_sqlite:
    # FastAPI/SSE serve requests from a thread pool; SQLite objects are not
    # thread-bound in this configuration.
    _connect_args["check_same_thread"] = False

engine: Engine = create_engine(
    _settings.database_url,
    echo=_settings.sql_echo,
    future=True,
    pool_pre_ping=True,
    connect_args=_connect_args,
)


if _settings.is_sqlite:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record) -> None:  # noqa: ANN001
        """Enable FK enforcement and WAL journaling on every new connection."""
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a session that is always closed."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, roll back on any exception.

    Delegates to :func:`app.db.base.session_scope_for` so the process-wide engine
    and a factory-injected one (the Task Engine's durable store) share a single
    commit/rollback implementation.
    """
    with session_scope_for(SessionLocal) as session:
        yield session
