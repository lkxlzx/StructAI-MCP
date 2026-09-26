"""Offline tests for the database-driven capability loader — V2.1 §16.1 Phase 2.

Plain ``pytest`` only: the ``async`` entry point is driven with ``asyncio.run`` so
the suite does not depend on ``pytest-asyncio`` being configured (matching
``tests/test_mcp_layer.py`` and ``tests/test_task_persistence.py``).

Everything here runs against a **real SQLite file in ``tmp_path``** — the 49-table
schema built once per session by the ``schema_template`` fixture
(``tests/conftest.py``) and copied per test. No live MIDAS, no network, no
process-wide engine.

What is proven, and against which rule:

========================================================  ==========================
claim                                                     依据
========================================================  ==========================
every ``Capability`` field round-trips from the tables      V2.1 §16.1 / §17.3 / §17.4
the same code on two adapters is two rows                  ``ux_capability``, 裁决 B-3
a platform-owned row loads with ``adapter_code is None``    对接规范 §2.5.1
``tool`` comes from ``capabilities.tool_id``               总纲 §4.2.12
``interface_code`` falls back to ``code``                  V2.1 §17.4
a malformed ``request_schema_json`` -> ``{}``, counted      V2.1 §6.2 / §9.3
an underivable ``dispatch`` is skipped **and counted**     总纲 §4.4 (no new codes)
``enabled = 0`` (capability **or** interface) is skipped   V2.1 §16.1
loading twice is idempotent                                V2.1 §16.1
``reset_capabilities()`` restores the static declaration   ``capabilities.py`` seam
``capabilities.description`` is the Chinese annotation,    总纲 §4.2.13
verbatim, and reaches ``notes`` / ``description``
the 155 ``midas_gen`` rows equal the static declaration    **the acceptance test**
========================================================  ==========================
"""

import asyncio
import dataclasses
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Callable

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  (registers all 49 tables on Base.metadata)
from app.mcp import capability_loader
from app.mcp.capabilities import (
    TOOL_EXECUTE,
    TOOL_MODEL,
    TOOL_NAMES,
    TOOL_QUERY,
    TOOL_TASK,
    Capability,
    capability_payload,
    capability_rows,
    capability_table,
    reset_capabilities,
)
from app.mcp.capability_loader import (
    EXECUTE_DISPATCH_TABLE,
    SKIP_CAPABILITY_DISABLED,
    SKIP_DUPLICATE_SLOT,
    SKIP_INTERFACE_DISABLED,
    SKIP_MALFORMED_ROW,
    SKIP_MISSING_REQUIRED_FIELD,
    SKIP_REASONS,
    SKIP_REGISTRATION_REJECTED,
    SKIP_TOOL_ROW_MISSING,
    SKIP_UNDERIVABLE_DISPATCH,
    SKIP_UNKNOWN_TOOL,
    WARN_INTERFACE_ROW_MISSING,
    WARN_INVALID_CONSTRAINTS_JSON,
    WARN_INVALID_DISPATCH_OVERRIDE,
    WARN_INVALID_METADATA_JSON,
    WARN_INVALID_REQUEST_SCHEMA,
    WARNING_REASONS,
    LoadResult,
    derive_dispatch,
    load_capabilities,
    load_capabilities_now,
)
from app.models.midas import Adapter
from app.models.registry import (
    Capability as CapabilityRow,
    CapabilityInterface as CapabilityInterfaceRow,
    Tool as ToolRow,
    ToolInterface as ToolInterfaceRow,
)

#: The adapter every ``Capability`` in the static declaration defaults to.
MIDAS_GEN = "midas_gen"
#: A second adapter, for the composite-key test (裁决 B-3).
MIDAS_CIVIL = "midas_civil"


def run(coro: Any) -> Any:
    """Drive one coroutine to completion (no pytest-asyncio dependency)."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# a real SQLite file, with the same pragmas as app.db.session
# ---------------------------------------------------------------------------
#: One engine per database file, exactly as ``tests/test_task_persistence.py`` does:
#: the loader hands its work to ``asyncio.to_thread``, so a pooled connection can be
#: picked up by a different worker thread than the one that opened it.
_FACTORIES: dict[str, Callable[[], Session]] = {}


def _enable_foreign_keys(dbapi_connection: Any, connection_record: Any) -> None:  # noqa: ANN001
    """``PRAGMA foreign_keys=ON`` — mirrors :mod:`app.db.session`."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def session_factory_for(path: Path) -> Callable[[], Session]:
    """Build (once per file) a sync ``sessionmaker`` over ``path``."""
    key = str(path)
    existing = _FACTORIES.get(key)
    if existing is not None:
        return existing
    engine: Engine = create_engine(
        f"sqlite:///{path}", future=True, connect_args={"check_same_thread": False}
    )
    event.listen(engine, "connect", _enable_foreign_keys)
    factory: Callable[[], Session] = sessionmaker(
        bind=engine, class_=Session, autoflush=False, expire_on_commit=False
    )
    _FACTORIES[key] = factory
    return factory


@pytest.fixture()
def sqlite_path(tmp_path: Path, schema_template: Path) -> Path:
    """A fresh copy of the empty 49-table schema, per test."""
    target = tmp_path / "structai_capabilities.db"
    shutil.copyfile(schema_template, target)
    return target


@pytest.fixture(autouse=True)
def _pristine_capability_table():
    """Every test starts and ends on the static declaration.

    The loader mutates a **module-global** table, so isolation is not optional:
    without this, one test's loaded rows would leak into ``test_mcp_layer.py`` and
    the offline suite would depend on test order.
    """
    reset_capabilities()
    yield
    reset_capabilities()


# ---------------------------------------------------------------------------
# seeding helpers
# ---------------------------------------------------------------------------
def _add_tools(session: Session, names: tuple[str, ...] = TOOL_NAMES) -> dict[str, int]:
    """Insert one ``tools`` row per MCP tool name; return ``name -> id``."""
    ids: dict[str, int] = {}
    for index, name in enumerate(names, start=1):
        row = ToolRow(
            name=name,
            display_name=name,
            input_schema_json="{}",
            sort_order=index,
        )
        session.add(row)
        session.flush()
        ids[name] = int(row.id)
    return ids


def _add_adapter(session: Session, code: str = MIDAS_GEN) -> None:
    """Insert one ``adapters`` row — the FK target of ``adapter_code``."""
    session.add(
        Adapter(code=code, name=code, software="MIDAS Gen", implementation="x")
    )
    session.flush()


def _add_interface(
    session: Session,
    *,
    interface_code: str,
    adapter_code: str = MIDAS_GEN,
    method: str = "GET",
    endpoint: str = "/db/NODE",
    request_wrapper: str | None = None,
    response_root_key: str | None = "NODE",
    operation: str = "get",
    resource: str | None = "node",
    product_scope: str = "unknown",
    domain: str | None = None,
    feature: str | None = None,
    request_schema_json: str | None = None,
    metadata_json: str | None = None,
    enabled: int = 1,
    tool_id: int | None = None,
) -> int:
    """Insert one ``tool_interfaces`` row and return its id.

    ``tool_id`` defaults to ``None`` on purpose: 裁决 B-3 makes the column nullable
    so one endpoint can serve several tools, and leaving it NULL is what proves the
    loaded ``tool`` came from ``capabilities.tool_id`` (总纲 §4.2.12).
    """
    row = ToolInterfaceRow(
        tool_id=tool_id,
        adapter_code=adapter_code,
        interface_code=interface_code,
        method=method,
        endpoint=endpoint,
        request_wrapper=request_wrapper,
        response_root_key=response_root_key,
        operation=operation,
        resource=resource,
        product_scope=product_scope,
        domain=domain,
        feature=feature,
        request_schema_json=request_schema_json,
        enabled=enabled,
        metadata_json=metadata_json,
    )
    session.add(row)
    session.flush()
    return int(row.id)


def _add_capability(
    session: Session,
    *,
    tool_id: int,
    code: str,
    resource: str,
    action: str,
    adapter_code: str | None = MIDAS_GEN,
    enabled: int = 1,
    description: str | None = None,
    constraints_json: str | None = None,
    interface_id: int | None = None,
) -> int:
    """Insert one ``capabilities`` row and return its id."""
    row = CapabilityRow(
        tool_id=tool_id,
        adapter_code=adapter_code,
        capability_code=code,
        resource=resource,
        action=action,
        description=description,
        interface_id=interface_id,
        enabled=enabled,
        constraints_json=constraints_json,
    )
    session.add(row)
    session.flush()
    return int(row.id)


def _link(session: Session, capability_id: int, interface_id: int) -> None:
    """Insert one ``capability_interfaces`` row (裁决 B-3)."""
    session.add(
        CapabilityInterfaceRow(
            capability_id=capability_id, interface_id=interface_id
        )
    )
    session.flush()


def _seed(sqlite_path: Path, build: Callable[[Session], None]) -> Callable[[], Session]:
    """Run ``build`` on a fresh session, commit, and return the factory."""
    factory = session_factory_for(sqlite_path)
    with factory() as session:
        build(session)
        session.commit()
    return factory


def _raw_sql(path: Path, *statements: str) -> None:
    """Run raw SQL with foreign keys **off** (for states the ORM forbids)."""
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        for statement in statements:
            connection.execute(statement)
        connection.commit()
    finally:
        connection.close()


# ---------------------------------------------------------------------------
# comparison helpers — the field-by-field proof
# ---------------------------------------------------------------------------
def _field_diffs(expected: Capability, actual: Capability) -> dict[str, tuple[Any, Any]]:
    """``field -> (expected, actual)`` for every field that differs."""
    return {
        spec.name: (getattr(expected, spec.name), getattr(actual, spec.name))
        for spec in dataclasses.fields(Capability)
        if getattr(expected, spec.name) != getattr(actual, spec.name)
    }


def _assert_same(actual: Capability, expected: Capability) -> None:
    """Assert **every** ``Capability`` field, one by one, so a diff names itself."""
    diffs = _field_diffs(expected, actual)
    assert not diffs, f"{expected.code}: {diffs}"


# ---------------------------------------------------------------------------
# 1. one hand-written row, every field
# ---------------------------------------------------------------------------
def test_a_hand_written_row_round_trips_field_by_field(sqlite_path: Path) -> None:
    """The whole mapping table of the loader, in one row.

    Every value here is deliberately *different* from what the derivation would
    produce, so a field that is silently defaulted cannot pass: the interface code
    is not the capability code, the schema comes from the interface, the outer-key
    vocabulary comes from ``metadata_json``, the notes come from
    ``capabilities.description``, and ``adapter_action`` / ``task_type`` come from
    ``constraints_json``.
    """

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        interface_id = _add_interface(
            session,
            interface_code="node.put",
            method="PUT",
            endpoint="/db/NODE",
            request_wrapper="Assign",
            response_root_key="NODE",
            operation="upsert",
            resource="node",
            product_scope="gen",
            domain="model",
            feature="db_node_element",
            request_schema_json='{"type": "object", "x-introspect": "/info/db/NODE"}',
            metadata_json='{"outer_key_means": "element", "outer_key_kind": "node"}',
        )
        _add_capability(
            session,
            tool_id=tools[TOOL_MODEL],
            code="node.upsert",
            resource="node",
            action="upsert",
            description="hand-written provenance note",
            constraints_json='{"adapter_action": "put_node", "task_type": "model_import"}',
            interface_id=interface_id,
        )

    factory = _seed(sqlite_path, build)
    result = run(load_capabilities(factory))

    assert result.rows_read == 1
    assert result.loaded == 1
    assert result.skipped == 0
    assert result.warnings == {}
    assert result.adapters == (MIDAS_GEN,)

    expected = Capability(
        code="node.upsert",
        tool=TOOL_MODEL,
        resource="node",
        action="upsert",
        adapter_code=MIDAS_GEN,
        method="PUT",
        endpoint="/db/NODE",
        request_wrapper="Assign",
        response_root_key="NODE",
        outer_key_means="element",
        outer_key_kind="node",
        request_schema={"type": "object", "x-introspect": "/info/db/NODE"},
        dispatch="model",  # derived: midas_model + action != delete (rule 8)
        adapter_action="put_node",
        task_type="model_import",
        interface_code="node.put",
        product_scope="gen",
        domain="model",
        feature="db_node_element",
        notes="hand-written provenance note",
    )
    _assert_same(capability_table(MIDAS_GEN)["node.upsert"], expected)


# ---------------------------------------------------------------------------
# 2. the composite key
# ---------------------------------------------------------------------------
def test_the_same_capability_code_on_two_adapters_loads_as_two_rows(
    sqlite_path: Path,
) -> None:
    """``(adapter_code, capability_code)`` — the key the multi-product need has.

    ``node.list`` is registered for gen and civil. A table keyed by ``code`` alone
    would have silently overwritten the first with the second.
    """

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        _add_adapter(session, MIDAS_CIVIL)
        for adapter, endpoint in ((MIDAS_GEN, "/db/NODE"), (MIDAS_CIVIL, "/db/NODE")):
            interface_id = _add_interface(
                session,
                interface_code=f"{adapter}.node.list",
                adapter_code=adapter,
                endpoint=endpoint,
            )
            _add_capability(
                session,
                tool_id=tools[TOOL_QUERY],
                code="node.list",
                resource="node",
                action="list",
                adapter_code=adapter,
                interface_id=interface_id,
            )

    factory = _seed(sqlite_path, build)
    result = run(load_capabilities(factory))

    assert result.loaded == 2
    # ``node.list`` already exists statically for midas_gen; civil is new.
    assert result.added == 1
    assert result.replaced == 1
    assert capability_table(MIDAS_GEN)["node.list"].adapter_code == MIDAS_GEN
    assert capability_table(MIDAS_CIVIL)["node.list"].adapter_code == MIDAS_CIVIL
    # …and the two rows are distinct objects, not one row registered twice.
    assert (
        capability_table(MIDAS_GEN)["node.list"]
        is not capability_table(MIDAS_CIVIL)["node.list"]
    )


# ---------------------------------------------------------------------------
# 3. platform-owned rows
# ---------------------------------------------------------------------------
def test_a_platform_owned_row_loads_without_adapter_or_interface(sqlite_path: Path) -> None:
    """``adapter_code IS NULL`` + no interface row — 对接规范 §2.5.1.

    MIDAS exposes no task API, so ``midas_task``'s rows are platform-owned. The
    loader must produce ``adapter_code is None``, no endpoint, and
    ``interface_code == code`` (``Capability.__post_init__``'s rule, V2.1 §17.4).
    """

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_capability(
            session,
            tool_id=tools[TOOL_TASK],
            code="task.get",
            resource="task",
            action="get",
            adapter_code=None,
        )

    factory = _seed(sqlite_path, build)
    result = run(load_capabilities(factory))

    assert result.loaded == 1
    assert result.adapters == (None,)
    loaded = capability_table(None)["task.get"]
    assert loaded.adapter_code is None
    assert loaded.method is None
    assert loaded.endpoint is None
    assert loaded.interface_code == "task.get"
    assert loaded.dispatch == "task"
    assert loaded.request_schema == {}
    _assert_same(
        loaded,
        Capability(
            code="task.get",
            tool=TOOL_TASK,
            resource="task",
            action="get",
            adapter_code=None,
            dispatch="task",
        ),
    )


# ---------------------------------------------------------------------------
# 4. the request schema
# ---------------------------------------------------------------------------
def test_a_malformed_request_schema_json_yields_an_empty_schema_and_is_counted(
    sqlite_path: Path,
) -> None:
    """V2.1 §6.2 / §9.3: the schema feeds the mandatory second validation.

    An unparseable value must not raise and must not be silently ignored either:
    the row loads with ``{}`` and the count is reported.
    """

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        broken = _add_interface(
            session,
            interface_code="node.get",
            request_schema_json="{not json at all",
        )
        _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="node.get",
            resource="node",
            action="get",
            interface_id=broken,
        )
        not_an_object = _add_interface(
            session,
            interface_code="element.get",
            endpoint="/db/ELEM",
            response_root_key="ELEM",
            request_schema_json='["not", "an", "object"]',
        )
        _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="element.get",
            resource="element",
            action="get",
            interface_id=not_an_object,
        )
        good = _add_interface(
            session,
            interface_code="material.get",
            endpoint="/db/MATL",
            response_root_key="MATL",
            request_schema_json='{"type": "object", "required": ["ids"]}',
        )
        _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="material.get",
            resource="material",
            action="get",
            interface_id=good,
        )

    factory = _seed(sqlite_path, build)
    result = run(load_capabilities(factory))

    assert result.loaded == 3
    assert result.warnings == {WARN_INVALID_REQUEST_SCHEMA: 2}
    assert capability_table(MIDAS_GEN)["node.get"].request_schema == {}
    assert capability_table(MIDAS_GEN)["element.get"].request_schema == {}
    assert capability_table(MIDAS_GEN)["material.get"].request_schema == {
        "type": "object",
        "required": ["ids"],
    }


# ---------------------------------------------------------------------------
# 5. dispatch — derived, skipped, or overridden
# ---------------------------------------------------------------------------
def test_the_dispatch_rules_reproduce_the_static_declaration() -> None:
    """The rule table, in isolation: no database involved.

    This is the half of the acceptance proof that is pure logic. If it fails, the
    derivation is wrong; if only the SQL round-trip fails, the *mapping* is wrong.
    """
    for row in capability_rows():
        assert (
            derive_dispatch(row.tool, row.resource, row.action, row.endpoint)
            == row.dispatch
        ), row.code


def test_an_underivable_dispatch_is_skipped_and_the_rest_still_load(
    sqlite_path: Path,
) -> None:
    """A new ``midas_execute`` action is **not** guessed at — it is reported.

    ``midas_execute``'s dispatch is not a function of its endpoint (see the
    loader's docstring), so an unclassified action must be skipped and counted
    rather than given an invented value.
    """

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        unknown = _add_interface(
            session,
            interface_code="project.export_project",
            method="POST",
            endpoint="/doc/EXPORT",
            request_wrapper="Argument",
            response_root_key=None,
            operation="export_project",
            resource="project",
        )
        _add_capability(
            session,
            tool_id=tools[TOOL_EXECUTE],
            code="project.export_project",
            resource="project",
            action="export_project",
            interface_id=unknown,
        )
        known = _add_interface(session, interface_code="node.list")
        _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="node.list",
            resource="node",
            action="list",
            interface_id=known,
        )

    factory = _seed(sqlite_path, build)
    result = run(load_capabilities(factory))

    assert result.loaded == 1
    assert result.skipped == 1
    assert result.skip_reasons == {SKIP_UNDERIVABLE_DISPATCH: 1}
    assert capability_table(MIDAS_GEN)["node.list"].endpoint == "/db/NODE"
    assert "project.export_project" not in capability_table(MIDAS_GEN)


def test_a_dispatch_override_rescues_a_row_the_rules_cannot_classify(
    sqlite_path: Path,
) -> None:
    """``constraints_json.dispatch`` is the documented escape hatch (总纲 §4.4).

    No new error code and no guessed value: the operator classifies the row in the
    database and the loader honours it.
    """

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        interface_id = _add_interface(
            session,
            interface_code="project.export_project",
            method="POST",
            endpoint="/doc/EXPORT",
            request_wrapper="Argument",
            response_root_key=None,
            operation="export_project",
            resource="project",
        )
        _add_capability(
            session,
            tool_id=tools[TOOL_EXECUTE],
            code="project.export_project",
            resource="project",
            action="export_project",
            constraints_json='{"dispatch": "execute"}',
            interface_id=interface_id,
        )

    factory = _seed(sqlite_path, build)
    result = run(load_capabilities(factory))

    assert result.loaded == 1
    assert result.skipped == 0
    assert capability_table(MIDAS_GEN)["project.export_project"].dispatch == "execute"


def test_an_invalid_dispatch_override_is_counted_and_the_derivation_wins(
    sqlite_path: Path,
) -> None:
    """A bad override must cost a counter, not the row — and never a raise.

    ``register_capability`` validates ``dispatch`` against ``DISPATCH_HINTS``, so
    passing the bad value through would raise ``VALIDATION_ERROR``. The loader
    counts it and falls back to the derivation.
    """

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        interface_id = _add_interface(
            session,
            interface_code="node.list",
            metadata_json='{"dispatch": "teleport"}',
        )
        _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="node.list",
            resource="node",
            action="list",
            interface_id=interface_id,
        )

    factory = _seed(sqlite_path, build)
    result = run(load_capabilities(factory))

    assert result.loaded == 1
    assert result.warnings == {WARN_INVALID_DISPATCH_OVERRIDE: 1}
    assert capability_table(MIDAS_GEN)["node.list"].dispatch == "query"


def test_the_execute_table_is_the_only_source_of_midas_execute_dispatches() -> None:
    """The closed table of rule 9, pinned to the static declaration it encodes."""
    static = {
        (row.resource, row.action): row.dispatch
        for row in capability_rows()
        if row.tool == TOOL_EXECUTE
    }
    assert static == EXECUTE_DISPATCH_TABLE


# ---------------------------------------------------------------------------
# 6. enabled = 0
# ---------------------------------------------------------------------------
def test_a_disabled_capability_is_skipped_and_counted(sqlite_path: Path) -> None:
    """``capabilities.enabled = 0`` (V2.1 §16.1) — the DB-shaped disable switch."""

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        interface_id = _add_interface(session, interface_code="node.get")
        _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="node.get",
            resource="node",
            action="get",
            enabled=0,
            interface_id=interface_id,
        )
        _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="node.list",
            resource="node",
            action="list",
            interface_id=interface_id,
        )

    factory = _seed(sqlite_path, build)
    result = run(load_capabilities(factory))

    assert result.rows_read == 2
    assert result.loaded == 1
    assert result.skip_reasons == {SKIP_CAPABILITY_DISABLED: 1}
    # The disabled row keeps its **static** declaration: the loader upserts, it
    # never prunes, so a disabled row falls back to the code table rather than
    # disappearing (which is also why reset_capabilities() still matters).
    assert capability_table(MIDAS_GEN)["node.get"].endpoint == "/db/NODE"


def test_a_disabled_interface_is_skipped_and_counted(sqlite_path: Path) -> None:
    """``tool_interfaces.enabled = 0`` — the endpoint is switched off, so fail closed."""
    state: dict[str, int] = {}

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        state["interface_id"] = _add_interface(
            session, interface_code="node.list", enabled=0
        )
        _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="node.list",
            resource="node",
            action="list",
            interface_id=state["interface_id"],
        )

    factory = _seed(sqlite_path, build)
    result = run(load_capabilities(factory))

    assert result.loaded == 0
    assert result.skipped == 1
    assert result.skip_reasons == {SKIP_INTERFACE_DISABLED: 1}


# ---------------------------------------------------------------------------
# 7. rows the join cannot complete
# ---------------------------------------------------------------------------
def test_a_row_whose_tool_is_missing_or_unknown_is_counted_not_dropped(
    sqlite_path: Path,
) -> None:
    """Both halves of the tool lookup are counted (总纲 §4.2.12).

    A missing ``tools`` row is a dangling foreign key — the loader joins with a
    ``LEFT OUTER JOIN`` precisely so the row is *counted* instead of vanishing from
    the result set. An unknown tool name is a row no MCP tool can ever reach.
    """

    def build(session: Session) -> None:
        _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        _add_adapter(session, MIDAS_CIVIL)
        frobnicate = ToolRow(
            name="midas_frobnicate",
            display_name="frobnicate",
            input_schema_json="{}",
        )
        session.add(frobnicate)
        session.flush()
        interface_id = _add_interface(session, interface_code="node.list")
        _add_capability(
            session,
            tool_id=int(frobnicate.id),
            code="node.list",
            resource="node",
            action="list",
            interface_id=interface_id,
        )

    factory = _seed(sqlite_path, build)
    # The dangling ``tool_id`` cannot be created through the ORM with foreign keys
    # on, so it is inserted with raw SQL and ``PRAGMA foreign_keys=OFF``.
    _raw_sql(
        sqlite_path,
        "INSERT INTO capabilities(tool_id,adapter_code,capability_code,resource,action)"
        " VALUES(4242,'midas_civil','node.list','node','list')",
    )
    result = run(load_capabilities(factory))

    assert result.rows_read == 2
    assert result.loaded == 0
    assert result.skip_reasons == {SKIP_UNKNOWN_TOOL: 1, SKIP_TOOL_ROW_MISSING: 1}


def test_a_row_with_an_empty_capability_code_is_skipped(sqlite_path: Path) -> None:
    """An empty key is not a usable key, even though the DDL only forbids NULL."""

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="",
            resource="",
            action="",
        )

    factory = _seed(sqlite_path, build)
    result = run(load_capabilities(factory))

    assert result.loaded == 0
    assert result.skip_reasons == {SKIP_MISSING_REQUIRED_FIELD: 1}


def test_a_dangling_interface_id_warns_and_falls_back_to_the_code(
    sqlite_path: Path,
) -> None:
    """``capabilities.interface_id`` pointing nowhere is a warning, not a crash."""

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="node.list",
            resource="node",
            action="list",
        )

    factory = _seed(sqlite_path, build)
    # Point the row at an interface id that does not exist (FK off, raw SQL).
    _raw_sql(sqlite_path, "UPDATE capabilities SET interface_id=9999")
    result = run(load_capabilities(factory))

    assert result.loaded == 1
    assert result.warnings == {WARN_INTERFACE_ROW_MISSING: 1}
    loaded = capability_table(MIDAS_GEN)["node.list"]
    assert loaded.interface_code == "node.list"
    assert loaded.endpoint is None


def test_a_duplicate_slot_is_skipped_and_counted(sqlite_path: Path) -> None:
    """``ux_capability`` forbids this, so the guard is defensive — and still counted.

    The unique index is dropped in the test database to reach the branch: a loader
    that silently let the second row overwrite the first would be exactly the
    silent-drop failure mode this result object exists to prevent.
    """

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        first = _add_interface(session, interface_code="node.get")
        _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="node.get",
            resource="node",
            action="get",
            interface_id=first,
        )
        second = _add_interface(
            session, interface_code="node.get.alt", endpoint="/db/NODE/ALT"
        )
        _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="node.get",
            resource="node",
            action="get",
            interface_id=second,
        )

    _raw_sql(sqlite_path, "DROP INDEX IF EXISTS ux_capability")
    factory = _seed(sqlite_path, build)
    result = run(load_capabilities(factory))

    assert result.rows_read == 2
    assert result.loaded == 1
    assert result.skip_reasons == {SKIP_DUPLICATE_SLOT: 1}
    # The first row (lowest id) wins — deterministic, not dictionary order.
    assert capability_table(MIDAS_GEN)["node.get"].endpoint == "/db/NODE"


def test_a_row_that_raises_while_being_built_is_counted_and_the_rest_load(
    sqlite_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The blanket guard: one broken row must not cost the whole load.

    ``derive_dispatch`` is made to explode for a single row, which is the worst
    case the loader promises to survive — an unexpected exception *while building*
    a row, not merely a missing value.
    """

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        interface_id = _add_interface(session, interface_code="node.list")
        for code, action in (("node.get", "get"), ("node.list", "list")):
            _add_capability(
                session,
                tool_id=tools[TOOL_QUERY],
                code=code,
                resource="node",
                action=action,
                interface_id=interface_id,
            )

    factory = _seed(sqlite_path, build)
    original = capability_loader.derive_dispatch

    def exploding(
        tool: str, resource: str, action: str, endpoint: str | None = None
    ) -> str | None:
        if action == "get":
            raise RuntimeError("boom")
        return original(tool, resource, action, endpoint)

    monkeypatch.setattr(capability_loader, "derive_dispatch", exploding)
    result = run(load_capabilities(factory))

    assert result.rows_read == 2
    assert result.loaded == 1
    assert result.skipped == 1
    assert result.skip_reasons == {SKIP_MALFORMED_ROW: 1}
    assert "node.list" in capability_table(MIDAS_GEN)


# ---------------------------------------------------------------------------
# 8. the tool is the capability's property (总纲 §4.2.12)
# ---------------------------------------------------------------------------
def test_the_tool_comes_from_the_capability_not_from_the_interface(
    sqlite_path: Path,
) -> None:
    """The interface's ``tool_id`` is deliberately a **different** tool.

    ``/post/TABLE`` is genuinely shared by ``midas_execute`` and ``midas_query``
    (裁决 B-3), and the platform-owned rows have no interface at all, so
    ``tool_interfaces.tool_id`` cannot be the source. Reading it would give
    ``midas_query`` here; the correct answer is ``midas_model``.
    """

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        interface_id = _add_interface(
            session,
            interface_code="node.upsert",
            method="PUT",
            tool_id=tools[TOOL_QUERY],  # wrong on purpose
        )
        _add_capability(
            session,
            tool_id=tools[TOOL_MODEL],
            code="node.upsert",
            resource="node",
            action="upsert",
            interface_id=interface_id,
        )

    factory = _seed(sqlite_path, build)
    result = run(load_capabilities(factory))

    assert result.loaded == 1
    loaded = capability_table(MIDAS_GEN)["node.upsert"]
    assert loaded.tool == TOOL_MODEL
    # …and the tool drives the dispatch too (rule 8, not rule 6).
    assert loaded.dispatch == "model"


# ---------------------------------------------------------------------------
# 9. the many-to-many fallback (裁决 B-3)
# ---------------------------------------------------------------------------
def test_the_capability_interfaces_link_is_the_fallback_for_a_null_interface_id(
    sqlite_path: Path,
) -> None:
    """``capabilities.interface_id`` NULL -> the link's lowest ``interface_id``."""
    state: dict[str, int] = {}

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        # ``node.main`` gets the lower id; ``node.alt`` is linked **first**, so the
        # winner cannot come from link insertion order — only from the documented
        # 「lowest interface_id」 rule.
        state["main"] = _add_interface(session, interface_code="node.main")
        state["alt"] = _add_interface(
            session, interface_code="node.alt", endpoint="/db/ALTNODE"
        )
        capability_id = _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="node.list",
            resource="node",
            action="list",
        )
        _link(session, capability_id, state["alt"])
        _link(session, capability_id, state["main"])

    factory = _seed(sqlite_path, build)
    result = run(load_capabilities(factory))

    assert result.loaded == 1
    loaded = capability_table(MIDAS_GEN)["node.list"]
    assert loaded.interface_code == "node.main"
    assert loaded.endpoint == "/db/NODE"


# ---------------------------------------------------------------------------
# 10. the JSON extension keys
# ---------------------------------------------------------------------------
def test_metadata_json_outer_keys_override_the_derivation(sqlite_path: Path) -> None:
    """V2.1 §17.3 — ``metadata_json.outer_key_means`` corrects the unverified default.

    ``/db/NODE``'s live-verified kind is ``node``; the stored value must win, and
    the sibling row without metadata must still be derived.
    """

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        corrected = _add_interface(
            session,
            interface_code="node.get",
            metadata_json='{"outer_key_means": "element", "outer_key_kind": "load_case"}',
        )
        _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="node.get",
            resource="node",
            action="get",
            interface_id=corrected,
        )
        derived = _add_interface(
            session, interface_code="load.get", endpoint="/db/CNLD", response_root_key="CNLD"
        )
        _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="load.get",
            resource="load",
            action="get",
            interface_id=derived,
        )

    factory = _seed(sqlite_path, build)
    result = run(load_capabilities(factory))

    assert result.loaded == 2
    corrected_row = capability_table(MIDAS_GEN)["node.get"]
    assert (corrected_row.outer_key_means, corrected_row.outer_key_kind) == (
        "element",
        "load_case",
    )
    # 对接规范 §4.1 / §11.6: /db/CNLD's outer key is a **node** number.
    derived_row = capability_table(MIDAS_GEN)["load.get"]
    assert (derived_row.outer_key_means, derived_row.outer_key_kind) == ("node", "node")


def test_metadata_json_is_the_fallback_for_the_capability_level_keys(
    sqlite_path: Path,
) -> None:
    """``notes`` / ``adapter_action`` / ``task_type`` / ``dispatch`` at the interface.

    ``capabilities.description`` is NULL here, so the interface-level ``notes`` is
    the only value available; the same blob carries the other three keys.
    """

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        interface_id = _add_interface(
            session,
            interface_code="node.list",
            metadata_json=json.dumps(
                {
                    "notes": "interface-level note",
                    "adapter_action": "list_nodes",
                    "task_type": "model_import",
                    "dispatch": "introspect",
                }
            ),
        )
        _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="node.list",
            resource="node",
            action="list",
            interface_id=interface_id,
        )

    factory = _seed(sqlite_path, build)
    result = run(load_capabilities(factory))

    assert result.loaded == 1
    loaded = capability_table(MIDAS_GEN)["node.list"]
    assert loaded.notes == "interface-level note"
    assert loaded.adapter_action == "list_nodes"
    assert loaded.task_type == "model_import"
    assert loaded.dispatch == "introspect"


def test_a_capability_level_request_schema_wins_over_the_interface(
    sqlite_path: Path,
) -> None:
    """The capability's own payload schema is the more specific statement."""

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        interface_id = _add_interface(
            session,
            interface_code="capabilities.list",
            method="GET",
            endpoint="/mapikey/verify",
            response_root_key=None,
            request_schema_json='{"from": "interface"}',
        )
        _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="capabilities.list",
            resource="capabilities",
            action="list",
            constraints_json='{"request_schema": {"from": "capability"}}',
            interface_id=interface_id,
        )

    factory = _seed(sqlite_path, build)
    result = run(load_capabilities(factory))

    assert result.loaded == 1
    assert capability_table(MIDAS_GEN)["capabilities.list"].request_schema == {
        "from": "capability"
    }


def test_a_malformed_json_blob_is_counted_and_the_row_still_loads(
    sqlite_path: Path,
) -> None:
    """Neither JSON column may cost a row."""

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        interface_id = _add_interface(
            session, interface_code="node.list", metadata_json="{oops"
        )
        _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="node.list",
            resource="node",
            action="list",
            constraints_json="[1, 2, 3]",
            interface_id=interface_id,
        )

    factory = _seed(sqlite_path, build)
    result = run(load_capabilities(factory))

    assert result.loaded == 1
    assert set(result.warnings) == {
        WARN_INVALID_METADATA_JSON,
        WARN_INVALID_CONSTRAINTS_JSON,
    }
    assert set(result.warnings) <= WARNING_REASONS


# ---------------------------------------------------------------------------
# 11. idempotency and the static fallback
# ---------------------------------------------------------------------------
def test_loading_twice_is_idempotent(sqlite_path: Path) -> None:
    """``replace=True``: a second load is an in-place replacement, never a duplicate."""

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        interface_id = _add_interface(session, interface_code="node.list")
        _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="node.list",
            resource="node",
            action="list",
            interface_id=interface_id,
        )

    factory = _seed(sqlite_path, build)
    before = len(capability_rows())
    first = run(load_capabilities(factory))
    after_first = capability_rows()
    second = run(load_capabilities(factory))
    after_second = capability_rows()

    assert first.loaded == 1
    assert second.loaded == 1
    assert second.skipped == 0
    assert second.warnings == {}
    # Nothing was added the second time: the slot already held the row.
    assert second.added == 0
    assert second.replaced == 1
    assert len(after_first) == before == len(after_second)
    assert after_first == after_second


def test_replace_false_reports_the_conflict_instead_of_raising(
    sqlite_path: Path,
) -> None:
    """``register_capability`` raises ``RESOURCE_CONFLICT``; the loader counts it.

    ``node.list`` already occupies its ``midas_gen`` slot (the static declaration),
    so ``replace=False`` cannot take it — while a brand-new adapter slot can.
    """

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        _add_adapter(session, MIDAS_CIVIL)
        for adapter in (MIDAS_GEN, MIDAS_CIVIL):
            interface_id = _add_interface(
                session, interface_code=f"{adapter}.node.list", adapter_code=adapter
            )
            _add_capability(
                session,
                tool_id=tools[TOOL_QUERY],
                code="node.list",
                resource="node",
                action="list",
                adapter_code=adapter,
                interface_id=interface_id,
            )

    factory = _seed(sqlite_path, build)
    result = run(load_capabilities(factory, replace=False))

    assert result.loaded == 1
    assert result.added == 1
    assert result.replaced == 0
    assert result.skip_reasons == {SKIP_REGISTRATION_REJECTED: 1}
    assert "node.list" in capability_table(MIDAS_CIVIL)


def test_an_empty_database_leaves_the_static_declaration_untouched(
    sqlite_path: Path,
) -> None:
    """The offline fallback: no rows means no change, not an empty table."""
    factory = session_factory_for(sqlite_path)
    before = capability_rows()
    result = run(load_capabilities(factory))

    assert result == LoadResult(rows_read=0, loaded=0, added=0, replaced=0, skipped=0)
    assert capability_rows() == before
    assert len(before) == 162  # 155 midas_gen + 7 platform-owned


def test_reset_capabilities_restores_the_static_declaration(sqlite_path: Path) -> None:
    """``reset_capabilities()`` is the documented fallback — and it still works."""

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        interface_id = _add_interface(
            session,
            interface_code="node.list",
            method="GET",
            endpoint="/db/NODE/REPLACED",
            request_schema_json='{"replaced": true}',
        )
        _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="node.list",
            resource="node",
            action="list",
            description="replaced note",
            interface_id=interface_id,
        )

    factory = _seed(sqlite_path, build)
    result = run(load_capabilities(factory))
    assert result.replaced == 1
    assert capability_table(MIDAS_GEN)["node.list"].endpoint == "/db/NODE/REPLACED"

    reset_capabilities()
    static = {row.code: row for row in capability_rows() if row.adapter_code == MIDAS_GEN}
    assert capability_table(MIDAS_GEN) == static
    assert capability_table(MIDAS_GEN)["node.list"].endpoint == "/db/NODE"
    assert capability_table(MIDAS_GEN)["node.list"].notes == ""


def test_load_capabilities_now_is_the_blocking_mirror(sqlite_path: Path) -> None:
    """Both entry points exist and agree (``task_store``'s async + ``_now`` shape)."""
    factory = session_factory_for(sqlite_path)
    blocking = load_capabilities_now(factory)
    awaited = run(load_capabilities(factory))
    assert blocking.to_payload() == awaited.to_payload()


# ---------------------------------------------------------------------------
# 12. the report itself
# ---------------------------------------------------------------------------
def test_the_report_vocabularies_are_closed_and_the_payload_is_json_safe(
    sqlite_path: Path,
) -> None:
    """The counters are the contract: closed reason sets, self-consistent totals."""

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        interface_id = _add_interface(
            session,
            interface_code="project.export_project",
            method="POST",
            endpoint="/doc/EXPORT",
            request_wrapper="Argument",
            response_root_key=None,
            operation="export_project",
            resource="project",
        )
        _add_capability(
            session,
            tool_id=tools[TOOL_EXECUTE],
            code="project.export_project",
            resource="project",
            action="export_project",
            interface_id=interface_id,
        )
        _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="node.get",
            resource="node",
            action="get",
            enabled=0,
        )
        _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="node.list",
            resource="node",
            action="list",
        )

    factory = _seed(sqlite_path, build)
    result = run(load_capabilities(factory))

    assert result.rows_read == 3
    assert result.loaded == 1
    assert result.skipped == 2
    assert result.loaded == result.added + result.replaced
    assert result.skipped == sum(result.skip_reasons.values())
    assert set(result.skip_reasons) <= SKIP_REASONS
    assert set(result.warnings) <= WARNING_REASONS
    assert result.ok is False
    payload = result.to_payload()
    assert json.loads(json.dumps(payload)) == payload
    assert payload["adapters"] == [MIDAS_GEN]


def test_a_clean_load_reports_ok(sqlite_path: Path) -> None:
    """``ok`` is the one-glance answer for a startup log line."""
    factory = session_factory_for(sqlite_path)
    result = run(load_capabilities(factory))
    assert result.ok is True
    assert result.to_payload()["skip_reasons"] == {}


# ---------------------------------------------------------------------------
# 13. THE ACCEPTANCE TEST — the DB reproduces the static declaration
# ---------------------------------------------------------------------------
def _seed_static_midas_gen(session: Session) -> list[Capability]:
    """Write every ``midas_gen`` row of the static declaration into the registry.

    Three deliberate omissions make the round-trip a *proof* rather than a
    tautology:

    * ``tool_interfaces.tool_id`` is NULL for every interface (裁决 B-3's nullable
      sharing column), so the loaded ``tool`` can only have come from
      ``capabilities.tool_id`` (总纲 §4.2.12);
    * ``metadata_json`` carries **no** outer-key keys, so the loader must derive
      ``outer_key_means`` / ``outer_key_kind`` from the endpoint (总纲 §0.4);
    * **no** ``dispatch`` key anywhere, so the rule table must reproduce it.
    """
    expected = [row for row in capability_rows() if row.adapter_code == MIDAS_GEN]
    tool_ids = _add_tools(session, TOOL_NAMES)
    _add_adapter(session, MIDAS_GEN)
    interfaces: dict[str, int] = {}

    for row in expected:
        interface_id: int | None = None
        if row.endpoint is not None or row.method is not None:
            interface_id = interfaces.get(row.interface_code)
            if interface_id is None:
                interface_id = _add_interface(
                    session,
                    interface_code=row.interface_code,
                    method=row.method or "GET",
                    endpoint=row.endpoint or "/",
                    request_wrapper=row.request_wrapper,
                    response_root_key=row.response_root_key,
                    operation=row.action,
                    resource=row.resource,
                    product_scope=row.product_scope,
                    domain=row.domain,
                    feature=row.feature,
                    request_schema_json=(
                        json.dumps(row.request_schema) if row.request_schema else None
                    ),
                    metadata_json=None,
                    tool_id=None,
                )
                interfaces[row.interface_code] = interface_id
            else:
                stored = session.get(ToolInterfaceRow, interface_id)
                assert stored is not None
                # A shared interface_code must describe the same endpoint, or the
                # round-trip would be comparing two different things.
                assert (
                    stored.method,
                    stored.endpoint,
                    stored.request_wrapper,
                    stored.response_root_key,
                    stored.request_schema_json,
                ) == (
                    row.method or "GET",
                    row.endpoint or "/",
                    row.request_wrapper,
                    row.response_root_key,
                    json.dumps(row.request_schema) if row.request_schema else None,
                ), row.code

        constraints: dict[str, Any] = {}
        if row.adapter_action is not None:
            constraints["adapter_action"] = row.adapter_action
        if row.task_type is not None:
            constraints["task_type"] = row.task_type
        if interface_id is None and row.request_schema:
            # No interface row -> ``constraints_json`` is the only home.
            constraints["request_schema"] = row.request_schema

        _add_capability(
            session,
            tool_id=tool_ids[row.tool],
            code=row.code,
            resource=row.resource,
            action=row.action,
            description=row.notes or None,
            constraints_json=json.dumps(constraints) if constraints else None,
            interface_id=interface_id,
        )

    return expected


def test_the_loaded_table_matches_the_static_declaration_for_midas_gen(
    sqlite_path: Path,
) -> None:
    """**The acceptance test**: the database can replace the code.

    The 155 ``midas_gen`` rows the declaration describes are written into a real
    ``tools`` / ``tool_interfaces`` / ``capabilities`` set, loaded back, and
    compared **field by field** against ``capability_rows()``. Nothing in the
    comparison is relaxed: every field of ``Capability`` must match, so the loaded
    table is behaviourally identical to the static one and
    ``capability_table("midas_gen")`` can be served from the database.
    """
    factory = session_factory_for(sqlite_path)
    with factory() as session:
        expected_rows = _seed_static_midas_gen(session)
        session.commit()

    assert len(expected_rows) == 155, "the declaration's midas_gen half changed"

    result = run(load_capabilities(factory))

    assert result.rows_read == 155
    assert result.loaded == 155
    assert result.skipped == 0
    assert result.skip_reasons == {}
    assert result.warnings == {}
    assert result.adapters == (MIDAS_GEN,)

    expected = {row.code: row for row in expected_rows}
    actual = capability_table(MIDAS_GEN)
    assert set(actual) == set(expected)

    mismatched: dict[str, dict[str, tuple[Any, Any]]] = {}
    for code, row in expected.items():
        diffs = _field_diffs(row, actual[code])
        if diffs:
            mismatched[code] = diffs
    assert not mismatched, f"{len(mismatched)} rows differ: {sorted(mismatched)[:3]}"

    # The whole table, not just the loaded half: the 7 platform-owned rows keep
    # their static declaration (the loader upserts; it never prunes).
    platform = {row.code: row for row in capability_rows() if row.adapter_code is None}
    assert capability_table(None) == platform
    assert len(capability_rows()) == 162


def test_the_static_declaration_survives_a_full_round_trip_byte_for_byte(
    sqlite_path: Path,
) -> None:
    """The same proof, expressed as set equality of the two row tuples.

    ``capability_rows()`` is declaration-ordered; the load replaces each slot in
    place, so the order must be preserved as well as the contents.
    """
    factory = session_factory_for(sqlite_path)
    with factory() as session:
        expected_rows = _seed_static_midas_gen(session)
        session.commit()
    static = tuple(row for row in capability_rows() if row.adapter_code == MIDAS_GEN)
    assert static == tuple(expected_rows)

    run(load_capabilities(factory))

    assert tuple(capability_table(MIDAS_GEN).values()) == static


# ---------------------------------------------------------------------------
# 14. the Chinese annotation (总纲 §4.2.13)
# ---------------------------------------------------------------------------
def test_the_capabilities_description_is_the_annotation_in_notes(
    sqlite_path: Path,
) -> None:
    """``capabilities.description`` -> ``Capability.notes`` -> the LLM payload.

    总纲 §4.2.13 makes ``capabilities.description`` the Chinese annotation's
    documented home (``notes`` has no column of its own), so a DB-loaded row's
    ``notes`` **is** the annotation the seeder wrote — verbatim, with nothing
    composed on the way — and ``capability_payload`` exposes the same string as
    ``description``.  A row the extraction could not annotate keeps ``""`` rather
    than a placeholder, and the interface-level ``metadata_json.annotation_source``
    is inert: the loader must not warn about a key it does not know.
    """
    annotation = "主控数据：分析主控参数：自动约束旋转与法向、收敛容差等全局求解设置。"

    def build(session: Session) -> None:
        tools = _add_tools(session, TOOL_NAMES)
        _add_adapter(session, MIDAS_GEN)
        annotated = _add_interface(
            session,
            interface_code="midas_gen.db.elem.read",
            endpoint="/db/ELEM",
            response_root_key="ELEM",
            metadata_json=json.dumps(
                {"annotation_source": "glossary", "annotation_key": "Main Control Data"}
            ),
        )
        _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="element.get",
            resource="element",
            action="get",
            description=annotation,
            # 总纲 §4.2.13: the capability level's only JSON column carries the
            # annotation's provenance for a reviewer.
            constraints_json=json.dumps({"annotation_source": "glossary"}),
            interface_id=annotated,
        )
        bare = _add_interface(session, interface_code="midas_gen.db.node.read")
        _add_capability(
            session,
            tool_id=tools[TOOL_QUERY],
            code="node.list",
            resource="node",
            action="list",
            interface_id=bare,
        )

    factory = _seed(sqlite_path, build)
    result = run(load_capabilities(factory))

    assert result.loaded == 2
    assert result.skipped == 0
    # ``annotation_source`` is not one of the loader's keys, so it is ignored
    # rather than warned about (总纲 §4.4: no new error code for a foreign key).
    assert result.warnings == {}

    annotated = capability_table(MIDAS_GEN)["element.get"]
    assert annotated.notes == annotation
    assert capability_payload(annotated)["description"] == annotation

    unannotated = capability_table(MIDAS_GEN)["node.list"]
    assert unannotated.notes == ""
    assert capability_payload(unannotated)["description"] == ""
