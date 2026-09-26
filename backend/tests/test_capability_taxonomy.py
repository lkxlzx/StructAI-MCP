"""The three-layer capability classification (总纲 §4.2.12 / 对接规范 §7.1).

`tool_interfaces` carries the classification that lets the platform answer two
questions it could not answer before:

* **which product** an endpoint serves (``product_scope``) — so connecting to Gen
  NX does not advertise Civil-only endpoints and then fail with a MIDAS 404;
* **where it belongs** (``domain`` / ``feature``) — so the frontend can build a
  per-product menu and the LLM can narrow ~683 endpoints in two cheap steps
  instead of choosing among all of them at once.

These tests pin the invariants that make that hierarchy trustworthy.

The last group is the one worth explaining. This project builds its schema by
**two different routes**:

* the **shipped** DDL is ``sql/001_schema.sql`` (that is what ``create_schema()``
  executes on SQLite, and what a deployed database actually looks like);
* the **test fixtures** build their database with
  ``Base.metadata.create_all`` (``tests/conftest.py``), i.e. from the ORM models.

So a constraint that lives **only** in the SQL file is a constraint the test
suite never exercises — production would enforce it and the tests would not. That
is the divergence these tests close, and it is why every enum column in this
project declares ``enum_check`` on the model as well.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, Set

import pytest
from sqlalchemy import create_engine, text

import app.models  # noqa: F401 — registers all 49 tables on Base.metadata
from app.core.constants import (
    CAPABILITY_DOMAIN_VALUES,
    CAPABILITY_FEATURE_DOMAIN,
    CAPABILITY_FEATURE_VALUES,
    MIDAS_PRODUCT_SCOPE_VALUES,
    CapabilityDomain,
    CapabilityFeature,
    MidasProductScope,
)
from app.db.base import Base

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


# ---------------------------------------------------------------------------
# the closed sets
# ---------------------------------------------------------------------------
def test_product_scope_is_the_closed_five_of_the_master_spec() -> None:
    """总纲 §4.2.12 — a closed set, not a suggestion."""
    assert set(MIDAS_PRODUCT_SCOPE_VALUES) == {
        "gen",
        "civil",
        "designer",
        "both",
        "unknown",
    }


def test_unknown_is_the_default_and_is_a_first_class_state() -> None:
    """``unknown`` is not a placeholder — it is the honest answer today.

    对接规范 §3.5 第 15 条 measured that of 47 endpoints the manuals declare
    "Civil-only", **32 answer on Gen NX too**. The labels cannot be trusted, so
    "not yet verified against a live instance" has to be representable. The
    column default must therefore be ``unknown``, not a guess.
    """
    assert MidasProductScope.UNKNOWN.value == "unknown"
    column = Base.metadata.tables["tool_interfaces"].columns["product_scope"]
    assert column.server_default is not None
    assert "unknown" in str(column.server_default.arg)


def test_domain_is_the_closed_eight() -> None:
    assert set(CAPABILITY_DOMAIN_VALUES) == {
        "project",
        "model",
        "load",
        "analysis",
        "result",
        "design",
        "view",
        "operation",
    }


def test_feature_is_the_closed_twenty_seven_manual_chapters() -> None:
    """One feature per chapter of the manual set (``api_chapters/01..27``)."""
    assert len(CAPABILITY_FEATURE_VALUES) == 27
    assert len(set(CAPABILITY_FEATURE_VALUES)) == 27, "no duplicates"


# ---------------------------------------------------------------------------
# the hierarchy
# ---------------------------------------------------------------------------
def test_every_feature_belongs_to_exactly_one_domain() -> None:
    """A strict hierarchy: no orphans, no unions, no guessing.

    If a feature were unmapped, a frontend menu would silently drop it; if a
    feature mapped to a domain outside the closed set, a filter would silently
    return nothing.
    """
    unmapped = [f for f in CAPABILITY_FEATURE_VALUES if f not in CAPABILITY_FEATURE_DOMAIN]
    assert unmapped == [], f"features with no domain: {unmapped}"

    unknown_domains = set(CAPABILITY_FEATURE_DOMAIN.values()) - set(CAPABILITY_DOMAIN_VALUES)
    assert unknown_domains == set(), f"mapped to a domain outside the closed set: {unknown_domains}"

    # Every domain must be reachable, or it is a menu entry that can never fill.
    used = set(CAPABILITY_FEATURE_DOMAIN.values())
    assert used == set(CAPABILITY_DOMAIN_VALUES), (
        f"domains with no feature: {set(CAPABILITY_DOMAIN_VALUES) - used}"
    )


def test_the_mapping_keys_are_the_feature_values() -> None:
    """The mapping is keyed by value, so it lines up with what is stored."""
    assert set(CAPABILITY_FEATURE_DOMAIN) == set(CAPABILITY_FEATURE_VALUES)


# ---------------------------------------------------------------------------
# the two build paths must agree
# ---------------------------------------------------------------------------
def _check_sql(ddl: str) -> Set[str]:
    """Normalised CHECK bodies from one ``CREATE TABLE`` statement.

    The two paths format differently — SQLAlchemy emits ``CHECK (`` with a space
    and ``001_schema.sql`` writes ``CHECK(`` without — so the separator must be
    ``\\s*``. (A regex requiring the space finds zero constraints in the SQL file
    and makes an equivalent pair look divergent.)
    """
    import re

    return {re.sub(r"\s+", "", body) for body in re.findall(r"CHECK\s*\(([^)]*)\)", ddl)}


def _ddl_from_orm(tmp_path: Path) -> str:
    engine = create_engine(f"sqlite:///{tmp_path / 'orm.db'}", future=True)
    try:
        Base.metadata.create_all(bind=engine)
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT sql FROM sqlite_master WHERE name='tool_interfaces'")
            ).scalar()
    finally:
        engine.dispose()


def _ddl_from_sql(tmp_path: Path) -> str:
    db = tmp_path / "sql.db"
    connection = sqlite3.connect(db)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        for script in sorted(SQL_DIR.glob("*.sql")):
            connection.executescript(script.read_text(encoding="utf-8"))
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name='tool_interfaces'"
        ).fetchone()
        return row[0]
    finally:
        connection.close()


def test_the_shipped_ddl_matches_the_orm_schema(tmp_path: Path) -> None:
    """The deployed schema and the schema the tests run against must agree.

    ``create_schema()`` executes ``sql/001_schema.sql``; the test fixtures call
    ``Base.metadata.create_all``. A constraint present on only one of them means
    **production enforces something the suite never checks** — the worst kind of
    gap, because the tests would stay green while the database rejected data.

    (This is not about PostgreSQL. The non-SQLite branch of ``create_schema()``
    also uses ``create_all``, but that path has never been run — no driver is
    even installed. The route that matters today is the test fixture.)
    """
    from_orm = _check_sql(_ddl_from_orm(tmp_path))
    from_sql = _check_sql(_ddl_from_sql(tmp_path))

    assert from_orm, "the ORM emitted no CHECK constraints at all"
    assert from_orm == from_sql, (
        "the shipped DDL and the ORM disagree:\n"
        f"  only ORM (what the tests build): {from_orm - from_sql}\n"
        f"  only SQL (what ships):           {from_sql - from_orm}"
    )


def _insert(ddl_path: Path, *, scope: str, domain: str | None) -> str:
    """Insert one row through the given path; return ``accepted``/``rejected``.

    Re-runnable on the same file: the schema scripts are ``IF NOT EXISTS``
    idempotent, and the FK target is inserted with ``OR IGNORE`` so a second call
    does not trip ``adapters.code``'s UNIQUE constraint.
    """
    connection = sqlite3.connect(ddl_path)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        for script in sorted(SQL_DIR.glob("*.sql")):
            connection.executescript(script.read_text(encoding="utf-8"))
        connection.execute(
            "INSERT OR IGNORE INTO adapters(code,name,software,implementation)"
            " VALUES('midas_gen','G','MIDAS Gen','x')"
        )
        try:
            connection.execute(
                "INSERT INTO tool_interfaces(adapter_code,interface_code,method,"
                "endpoint,operation,product_scope,domain) VALUES(?,?,?,?,?,?,?)",
                (
                    "midas_gen",
                    f"t_{scope}_{domain}_{connection.total_changes}",
                    "GET",
                    "/db/NODE",
                    "read",
                    scope,
                    domain,
                ),
            )
            connection.commit()
            return "accepted"
        except sqlite3.IntegrityError:
            return "rejected"
    finally:
        connection.close()


@pytest.mark.parametrize(
    "scope,domain,expected",
    [
        ("gen", None, "accepted"),
        ("civil", None, "accepted"),
        ("designer", None, "accepted"),
        ("both", None, "accepted"),
        ("unknown", None, "accepted"),
        # not in the closed set
        ("civil_nx", None, "rejected"),
        ("Gen", None, "rejected"),
        ("", None, "rejected"),
        # domain is nullable and a bare CHECK(... IN ...) must let NULL through
        ("gen", "model", "accepted"),
        ("gen", "modelling", "rejected"),
    ],
)
def test_the_closed_sets_are_enforced_by_the_database(
    tmp_path: Path, scope: str, domain: str | None, expected: str
) -> None:
    """The database refuses what the constants refuse — not just the code."""
    assert _insert(tmp_path / f"probe_{abs(hash((scope, domain)))}.db", scope=scope, domain=domain) == expected


def test_a_nullable_check_still_rejects_a_bad_value(tmp_path: Path) -> None:
    """``domain`` is nullable; that must not weaken the constraint.

    Worth its own test because the two facts pull in opposite directions: the
    column accepts NULL, and the CHECK still has to reject a typo. It works
    because a CHECK fails only on FALSE and ``NULL IN (...)`` is NULL — but that
    is exactly the kind of thing a later "simplification" removes.
    """
    path = tmp_path / "nullable.db"
    assert _insert(path, scope="gen", domain=None) == "accepted"
    assert _insert(path, scope="gen", domain="nonsense") == "rejected"


def test_capability_domain_and_feature_enums_are_str_enums() -> None:
    """Stored as TEXT, compared as ``str`` — same as every other 总纲 §4.2 set."""
    assert CapabilityDomain.MODEL == "model"
    assert CapabilityFeature.DB_NODE_ELEMENT == "db_node_element"
    assert MidasProductScope.UNKNOWN == "unknown"


# ---------------------------------------------------------------------------
# the capabilities table: two gaps found while preparing the DB-driven loader
# ---------------------------------------------------------------------------
# `capabilities.py` declares the table in code and says Phase 2 would load the
# same rows from the database. Preparing that loader surfaced two things the
# schema could not express. Both were fixed while the tables were still empty —
# which is the only time such a change is free.
def _seed_registry(connection: sqlite3.Connection) -> None:
    """Seed the FK targets a ``capabilities`` row needs."""
    connection.execute(
        "INSERT INTO tools(name,display_name,version,tool_type,input_schema_json,"
        "enabled,sort_order) VALUES('midas_query','Q','2.1','query','{}',1,1)"
    )
    for code, software in (
        ("midas_gen", "MIDAS Gen"),
        ("midas_civil", "MIDAS Civil"),
        ("midas_designer", "MIDAS Designer"),
    ):
        connection.execute(
            "INSERT INTO adapters(code,name,software,implementation) VALUES(?,?,?,?)",
            (code, code, software, "x"),
        )
    connection.commit()


def _capability_db(tmp_path: Path, name: str) -> sqlite3.Connection:
    path = tmp_path / name
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys=ON")
    for script in sorted(SQL_DIR.glob("*.sql")):
        connection.executescript(script.read_text(encoding="utf-8"))
    _seed_registry(connection)
    return connection


def _add_capability(
    connection: sqlite3.Connection, adapter: str | None, code: str
) -> str:
    resource, _, action = code.partition(".")
    try:
        connection.execute(
            "INSERT INTO capabilities(tool_id,adapter_code,capability_code,resource,action)"
            " VALUES(1,?,?,?,?)",
            (adapter, code, resource, action),
        )
        connection.commit()
        return "accepted"
    except sqlite3.IntegrityError:
        return "rejected"


def test_the_same_capability_code_may_exist_once_per_adapter(tmp_path: Path) -> None:
    """The key the multi-product extension needs.

    ``ux_capability(adapter_code, capability_code)`` is what lets ``node.list``
    exist for gen *and* civil. This is precisely what the in-code ``_TABLE``
    cannot do — it is keyed by ``code`` alone, so a second adapter's row would
    silently overwrite the first. The schema already had the right key; this
    pins it so a later "simplification" to a single-column key is caught.
    """
    connection = _capability_db(tmp_path, "multi_adapter.db")
    try:
        assert _add_capability(connection, "midas_gen", "node.list") == "accepted"
        assert _add_capability(connection, "midas_civil", "node.list") == "accepted"
        assert _add_capability(connection, "midas_designer", "node.list") == "accepted"
        # …but not twice for the same adapter
        assert _add_capability(connection, "midas_gen", "node.list") == "rejected"

        rows = connection.execute(
            "SELECT adapter_code FROM capabilities WHERE capability_code='node.list'"
            " ORDER BY adapter_code"
        ).fetchall()
        assert [r[0] for r in rows] == ["midas_civil", "midas_designer", "midas_gen"]
    finally:
        connection.close()


def test_a_platform_owned_capability_can_be_stored(tmp_path: Path) -> None:
    """``adapter_code`` is nullable so ``midas_task`` can exist at all.

    Its seven capabilities are platform-owned — MIDAS exposes no task API
    (对接规范 §2.5.1) — so there is no adapter to point at. With the column
    ``NOT NULL`` they could not be stored, and a DB-driven table would silently
    lose the whole ``midas_task`` tool.
    """
    connection = _capability_db(tmp_path, "platform_owned.db")
    try:
        assert _add_capability(connection, None, "task.get") == "accepted"
        assert _add_capability(connection, None, "task.list") == "accepted"
    finally:
        connection.close()


def test_a_platform_owned_code_is_still_unique(tmp_path: Path) -> None:
    """…and ``ux_capability`` alone would not catch a duplicate.

    SQL treats NULLs as distinct, so ``(NULL, 'task.get')`` passes the composite
    unique index twice over. ``ux_capability_platform`` is the partial index that
    closes that half — without it the duplicate would go unnoticed, which is the
    same class of silent hole as the ``requested_by`` gap.
    """
    connection = _capability_db(tmp_path, "platform_unique.db")
    try:
        assert _add_capability(connection, None, "task.get") == "accepted"
        assert _add_capability(connection, None, "task.get") == "rejected"
    finally:
        connection.close()


def test_both_paths_agree_on_the_capabilities_indexes(tmp_path: Path) -> None:
    """Same divergence guard as for ``tool_interfaces``, for the same reason."""
    def index_names(connection: sqlite3.Connection) -> list:
        return sorted(
            r[0]
            for r in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='capabilities'"
            )
        )

    from_sql = _capability_db(tmp_path, "cap_sql.db")
    try:
        sql_names = index_names(from_sql)
    finally:
        from_sql.close()

    engine = create_engine(f"sqlite:///{tmp_path / 'cap_orm.db'}", future=True)
    try:
        Base.metadata.create_all(bind=engine)
        with engine.connect() as conn:
            orm_names = sorted(
                r[0]
                for r in conn.execute(
                    text(
                        "SELECT name FROM sqlite_master WHERE type='index'"
                        " AND tbl_name='capabilities'"
                    )
                )
            )
    finally:
        engine.dispose()

    assert "ux_capability_platform" in orm_names, "the ORM lost the partial index"
    assert sql_names == orm_names, (sql_names, orm_names)
