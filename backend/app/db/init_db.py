"""Schema bootstrap and idempotent seed data (总纲 §7 Phase 0.1).

``create_schema()``
    Prefers the authoritative raw DDL in ``backend/sql/*.sql`` when it exists
    (SQLite only — those scripts use SQLite syntax such as ``INSERT OR IGNORE``).
    Every ``*.sql`` file is executed in lexical order, which is why the baseline
    is split as ``001_schema.sql`` (49 tables) followed by ``002_seed.sql``
    (reference data). Without the scripts it falls back to
    ``Base.metadata.create_all``.

``seed_data()``
    Idempotent ORM seeding of ``permissions`` / ``roles`` / ``role_permissions``
    (总纲 §4.8.2 / §4.8.3) and the five singleton configuration rows. It is safe
    to run after ``002_seed.sql``: existing rows are matched by natural key and
    refreshed in place, never duplicated.

``ensure_users_department()``
    The one additive catch-up step for a database that predates
    ``users.department`` (总纲 §4.2.5).  ``CREATE TABLE IF NOT EXISTS`` never adds
    a column to an existing table, so re-running the raw DDL is safe but does not
    close that gap.  Idempotent and dialect-portable; see the function docstring.

``init_db()``
    All of the above, in that order. Runnable directly::

        python -m app.db.init_db
"""

import sys
from pathlib import Path

from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core import constants as C
from app.db.base import Base
from app.db.session import engine, session_scope
from app.models import (  # noqa: F401  (import registers all 49 tables on Base.metadata)
    AssistantDrawingSetting,
    BackupConfig,
    CleanupConfig,
    Permission,
    Role,
    RolePermission,
    SecurityConfig,
    ServiceConfig,
)

__all__ = [
    "SQL_DIR",
    "sql_script_paths",
    "create_schema",
    "ensure_users_department",
    "seed_data",
    "init_db",
    "main",
]

#: ``backend/sql/`` — V2.1 §4 DDL plus the reference-data seed script.
SQL_DIR: Path = Path(__file__).resolve().parents[2] / "sql"

#: Singleton tables that must always hold exactly one row with ``id = 1``.
_SINGLETON_MODELS = (
    SecurityConfig,
    ServiceConfig,
    BackupConfig,
    CleanupConfig,
    AssistantDrawingSetting,
)


def sql_script_paths() -> list[Path]:
    """Return the ``backend/sql/*.sql`` scripts in execution order (may be empty)."""
    if not SQL_DIR.is_dir():
        return []
    return sorted(path for path in SQL_DIR.glob("*.sql") if path.is_file())


def _execute_sqlite_script(sql: str) -> None:
    """Run a multi-statement SQLite script through the DBAPI ``executescript``."""
    raw = engine.raw_connection()
    try:
        cursor = raw.cursor()
        try:
            cursor.executescript(sql)
            raw.commit()
        finally:
            cursor.close()
    finally:
        raw.close()


def create_schema() -> str:
    """Create all 49 tables; returns a human-readable description of the path used."""
    scripts = sql_script_paths()
    if engine.dialect.name == "sqlite" and scripts:
        for path in scripts:
            _execute_sqlite_script(path.read_text(encoding="utf-8"))
        return "executed " + ", ".join(path.name for path in scripts)
    # PostgreSQL and any environment without the raw DDL scripts.
    Base.metadata.create_all(bind=engine)
    return "Base.metadata.create_all"


def ensure_users_department(bind: Engine | None = None) -> bool:
    """Add ``users.department`` to a database created before the column existed.

    总纲 §4.2.5 adds ``users.department TEXT`` to the user table (the principal
    half of 《MIDAS API 对接规范》§2.5.4 item 5's department visibility rule).
    ``001_schema.sql`` **is** idempotent — all 49 of its ``CREATE TABLE``
    statements carry ``IF NOT EXISTS`` — but ``CREATE TABLE IF NOT EXISTS`` never
    adds a column to an existing table, so a database created by an earlier build
    would silently lack it.  This is that catch-up step, run by :func:`init_db`
    right after :func:`create_schema`:

    * it **inspects** the live table (``inspect(...).get_columns("users")``) and
      issues ``ALTER TABLE users ADD COLUMN department TEXT`` only when the
      column is absent, so it is a no-op on every later startup and works on both
      SQLite and PostgreSQL;
    * **only** when it just added the column, it backfills each NULL from the
      label of that user's lowest-id ``midas_clients`` row that carries one.  That
      is exactly the derivation ``AuthService._department_now`` used to perform at
      read time; running it once here is what keeps existing deployments working
      now that the read-time fallback is gone.  It must never run again — an
      operator's later assignment is authoritative, and a startup may not
      overwrite it — which is why the backfill is inside the "column was just
      added" branch.

    Deliberately **not** a migration framework: no Alembic, no version table.  A
    real migration tool is a separate decision (and a separate dependency); this
    single additive, idempotent step is all the current gap needs.

    :param bind: engine to operate on; defaults to the process-wide
        :data:`app.db.session.engine`.  Injectable so a test can point it at a
        legacy database without touching the module global.
    :returns: ``True`` when the column was added (and the backfill ran),
        ``False`` when the database already had it.
    """
    target: Engine = bind if bind is not None else engine
    inspector = inspect(target)
    table_names = set(inspector.get_table_names())
    if "users" not in table_names:
        # Nothing to catch up: the schema was never created here.
        return False
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "department" in columns:
        return False

    # ``midas_clients`` is where the pre-column derivation read the label from;
    # on a database that has ``users`` but not it, the column is still added and
    # simply stays NULL (fail closed — 对接规范 §2.5.4 第 5 条: 不得假定).
    has_clients = "midas_clients" in table_names

    with target.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN department TEXT"))
        if has_clients:
            # One correlated subquery, portable across SQLite and PostgreSQL:
            # lowest ``midas_clients.id`` per user that has a non-NULL label.
            connection.execute(
                text(
                    "UPDATE users SET department = ("
                    " SELECT mc.department FROM midas_clients AS mc"
                    " WHERE mc.owner_id = users.id AND mc.department IS NOT NULL"
                    " ORDER BY mc.id LIMIT 1"
                    ")"
                    " WHERE users.department IS NULL"
                )
            )
    return True


def seed_data() -> dict[str, int]:
    """Seed permissions, roles, role-permission links and singleton rows.

    Idempotent: existing rows are matched by their natural key (``code`` /
    ``id = 1``) and refreshed in place. ``"*"`` in
    :data:`app.core.constants.ROLE_PERMISSION_MAP` is expanded to the full
    §4.8.2 permission list here.
    """
    stats = {"permissions": 0, "roles": 0, "role_permissions": 0, "singletons": 0}

    with session_scope() as db:
        stats.update(_seed_permissions(db))
        stats.update(_seed_roles(db))
        stats.update(_seed_role_permissions(db))
        stats.update(_seed_singletons(db))

    return stats


def _seed_permissions(db: Session) -> dict[str, int]:
    """Upsert the 34 permission codes of 总纲 §4.8.2."""
    created = 0
    for code, name, module, action in C.PERMISSIONS:
        permission = db.scalar(select(Permission).where(Permission.code == code))
        if permission is None:
            db.add(Permission(code=code, name=name, module=module, action=action))
            created += 1
        else:
            permission.name = name
            permission.module = module
            permission.action = action
    db.flush()
    return {"permissions": created}


def _seed_roles(db: Session) -> dict[str, int]:
    """Upsert the four default roles of 总纲 §4.8.3."""
    created = 0
    for spec in C.ROLE_DEFINITIONS:
        code = str(spec["code"])
        role = db.scalar(select(Role).where(Role.code == code))
        if role is None:
            db.add(
                Role(
                    code=code,
                    name=str(spec["name"]),
                    description=str(spec["description"]),
                    is_system=1 if spec.get("is_system") else 0,
                )
            )
            created += 1
        else:
            role.name = str(spec["name"])
            role.description = str(spec["description"])
            role.is_system = 1 if spec.get("is_system") else 0
    db.flush()
    return {"roles": created}


def _seed_role_permissions(db: Session) -> dict[str, int]:
    """Link roles to permissions per 总纲 §4.8.3, expanding ``"*"`` and ``"x:*"``."""
    roles = {role.code: role for role in db.scalars(select(Role)).all()}
    permissions = {p.code: p for p in db.scalars(select(Permission)).all()}
    existing = {
        (role_id, permission_id)
        for role_id, permission_id in db.execute(
            select(RolePermission.role_id, RolePermission.permission_id)
        ).all()
    }

    created = 0
    for role_code, patterns in C.ROLE_PERMISSION_MAP.items():
        role = roles.get(role_code)
        if role is None:  # pragma: no cover - roles are seeded immediately before
            continue
        for code in C.expand_permission_patterns(patterns, permissions.keys()):
            permission = permissions.get(code)
            if permission is None:  # pragma: no cover - patterns are validated
                continue
            key = (role.id, permission.id)
            if key in existing:
                continue
            db.add(RolePermission(role_id=role.id, permission_id=permission.id))
            existing.add(key)
            created += 1
    db.flush()
    return {"role_permissions": created}


def _seed_singletons(db: Session) -> dict[str, int]:
    """Ensure each ``id = 1`` configuration row exists (V2.1 §4 19.4)."""
    created = 0
    for model in _SINGLETON_MODELS:
        if db.get(model, 1) is None:
            db.add(model(id=1))
            created += 1
    db.flush()
    return {"singletons": created}


def init_db() -> dict[str, object]:
    """Create the schema, catch an existing database up, then seed it.

    Order matters: the catch-up runs **after** :func:`create_schema` (so a fresh
    database already has the column from ``001_schema.sql`` and the step is a
    no-op) and **before** :func:`seed_data`.
    """
    schema = create_schema()
    users_department_added = ensure_users_department()
    stats = seed_data()
    return {
        "schema": schema,
        "migration": {"users_department_added": users_department_added},
        "seed": stats,
    }


def main() -> int:
    """CLI entry point: ``python -m app.db.init_db``."""
    result = init_db()
    print(f"[structai] schema  : {result['schema']}")
    migration = result["migration"]
    assert isinstance(migration, dict)
    if migration["users_department_added"]:
        print(
            "[structai] migrate : users.department 列不存在，已新增并从 "
            "midas_clients.department 回填一次（总纲 §4.2.5）"
        )
    else:
        print("[structai] migrate : users.department 已存在，未做任何变更")
    seed = result["seed"]
    assert isinstance(seed, dict)
    print(
        "[structai] seeded  : "
        f"{seed['permissions']} permissions, "
        f"{seed['roles']} roles, "
        f"{seed['role_permissions']} role_permissions, "
        f"{seed['singletons']} singleton rows "
        "(counts are newly inserted rows; existing rows are refreshed)"
    )
    print(f"[structai] database: {engine.url.render_as_string(hide_password=True)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
