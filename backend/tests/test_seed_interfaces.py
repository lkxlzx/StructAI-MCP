"""Offline tests for the interface seeder — V2.1 §16.1 Phase 2's missing half.

Plain ``pytest`` only, and a **real SQLite file per test** built from the
``schema_template`` fixture in ``tests/conftest.py`` (copied, like
``tests/test_capability_loader.py`` does).  No live MIDAS, no network, no
process-wide engine: :func:`app.db.seed_interfaces.seed_interfaces` takes the
session factory, so a test can point it at a ``tmp_path`` file.

What is proven, and against which rule:

==========================================================  ==========================
claim                                                       依据
==========================================================  ==========================
the mapping table is total over the mappable rows and every   V2.1 §6.3 / §17.4
skip is counted with a reason from the closed set
seeding is idempotent (twice -> same row counts)             总纲 §0.4
``(adapter, interface_code)`` and ``(adapter, capability_code)``
stay unique — the DDL's own keys
the loader loads every seeded capability with **no** skip     V2.1 §16.1
a seeded capability and its static counterpart agree          **the acceptance test**
field for field except a named, reasoned set
``reset_capabilities()`` restores the static declaration     ``capabilities.py`` seam
all three products are present after seeding                 多产品多租户路由框架 §二
a DB-loaded capability dispatches through a real             v1.2 §38
``ToolDispatcher``: resolve -> gate -> handler -> adapter
the extraction's rows are never invented (endpoint/method    总纲 §0.4
come from the file verbatim)
==========================================================  ==========================
"""

import asyncio
import dataclasses
import json
import shutil
from pathlib import Path
from typing import Any, Callable

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  (registers all 49 tables on Base.metadata)
from app.adapters.mock.adapter import MockAdapter
from app.adapters.registry import AdapterRegistry
from app.core.constants import PRODUCT_SCOPE_BY_PRODUCT
from app.db.seed_interfaces import (
    ADAPTER_CODES,
    EXECUTE_ENDPOINT_CAPABILITIES,
    SKIP_EXECUTE_UNMAPPED,
    SKIP_MALFORMED_ROW,
    SKIP_MISSING_REQUIRED_FIELD,
    SKIP_REASONS,
    SKIP_UNKNOWN_FAMILY,
    SKIP_UNSUPPORTED_METHOD,
    SKIP_UNSUPPORTED_OPERATION,
    TOOL_AND_ACTION_RULES,
    ClassifiedRow,
    SeedResult,
    capability_slot,
    classify_row,
    default_interfaces_path,
    derive_resource_alias,
    load_interfaces,
    seed_interfaces,
)
from app.mcp.capabilities import (
    TOOL_EXECUTE,
    TOOL_MODEL,
    TOOL_NAMES,
    TOOL_QUERY,
    Capability,
    actions_for,
    capability_rows,
    capability_table,
    reset_capabilities,
)
from app.mcp.capability import CapabilityResolver
from app.mcp.capability_loader import EXECUTE_DISPATCH_TABLE, load_capabilities_now
from app.mcp.dispatcher import ToolDispatcher
from app.models.midas import Adapter as AdapterRow
from app.models.registry import (
    Capability as CapabilityRow,
    CapabilityInterface as CapabilityInterfaceRow,
    Tool as ToolRow,
    ToolInterface as ToolInterfaceRow,
)
from app.services.task_service import TaskService

MIDAS_GEN = "midas_gen"
MIDAS_CIVIL = "midas_civil"
MIDAS_CDN = "midas_cdn"

#: ``Capability`` fields a **seeded** row is expected to differ on, with the rule
#: that makes each one legitimate.  Every other field must match its static
#: counterpart exactly, which is what makes the acceptance test a proof rather
#: than a spot check:
#:
#: ``domain`` / ``feature``
#:     总纲 §4.2.11's classification layers.  The static declaration ships them
#:     as ``None`` ("the classification loader's job"); the extraction carries
#:     them, so the DB row is strictly richer.
#: ``interface_code``
#:     V2.1 §17.4: the extraction's code is the **API-level**
#:     ``midas_gen.db.node.read``; the declaration's is the MCP-facing
#:     ``node.read``.  The seeder keeps the extraction's verbatim, which is what
#:     makes ``(adapter_code, interface_code)`` unique on the shared table URIs.
#: ``notes``
#:     the declaration's curated 对接规范 notes; the extraction has no equivalent
#:     free-text column, and copying the static ones into the seeder would make
#:     the seeder depend on the table it is meant to replace.
#: ``request_schema``
#:     the extraction's ``request_schema_json`` is an **API request body** (a
#:     manual example 594/604 times, ``EXTRACTION_REPORT.md`` §3), not the MCP
#:     payload V2.1 §6.2 / §9.3 validates.  The seeder therefore leaves it empty
#:     and the seeded row is deliberately **more permissive**.
#: ``request_wrapper``
#:     the declaration leaves it ``None`` on read rows (no body is sent); the
#:     extraction reports the wrapper the manual documents for the URI
#:     (对接规范 §3.1 — ``/db/*`` is ``Assign``, the rest ``Argument``).
#: ``method``
#:     the declaration hard-codes ``POST`` for every ``midas_model`` write except
#:     ``delete``; the extraction carries the manual's own verb, which is ``PUT``
#:     for an update.  The seeded row is the one that matches the manual.
KNOWN_DIFFERENCES: frozenset[str] = frozenset(
    {
        "domain",
        "feature",
        "interface_code",
        "notes",
        "request_schema",
        "request_wrapper",
        "method",
    }
)


# ---------------------------------------------------------------------------
# a real SQLite file, with the same pragmas as app.db.session
# ---------------------------------------------------------------------------
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
    target = tmp_path / "structai_seed.db"
    shutil.copyfile(schema_template, target)
    return target


@pytest.fixture(autouse=True)
def _pristine_capability_table():
    """Every test starts and ends on the static declaration.

    The seeder and the loader both touch a **module-global** table, so isolation
    is not optional: without this, one test's rows would leak into
    ``test_mcp_layer.py`` and the offline suite would depend on test order.
    """
    reset_capabilities()
    yield
    reset_capabilities()


@pytest.fixture(scope="module")
def extraction() -> dict[str, Any]:
    """The extraction, parsed once for the whole module."""
    return load_interfaces(default_interfaces_path())


@pytest.fixture(scope="module")
def extraction_rows(extraction: dict[str, Any]) -> list[dict[str, Any]]:
    rows = extraction["rows"]
    assert isinstance(rows, list)
    return rows


def run(coro: Any) -> Any:
    """Drive one coroutine to completion (no ``pytest-asyncio`` dependency)."""
    return asyncio.run(coro)


def _seed(sqlite_path: Path, **kwargs: Any) -> tuple[SeedResult, Callable[[], Session]]:
    factory = session_factory_for(sqlite_path)
    return seed_interfaces(factory, **kwargs), factory


def _load(factory: Callable[[], Session]) -> Any:
    return load_capabilities_now(factory)


def _field_diffs(expected: Capability, actual: Capability) -> dict[str, tuple[Any, Any]]:
    """``field -> (expected, actual)`` for every field that differs."""
    return {
        spec.name: (getattr(expected, spec.name), getattr(actual, spec.name))
        for spec in dataclasses.fields(Capability)
        if getattr(expected, spec.name) != getattr(actual, spec.name)
    }


# ---------------------------------------------------------------------------
# 1. the mapping table is total over the mappable rows
# ---------------------------------------------------------------------------
def test_every_extraction_row_is_either_mapped_or_counted_with_a_reason(
    extraction_rows: list[dict[str, Any]],
) -> None:
    """No row may fall through silently — the failure mode this seeder exists for.

    ``classify_row`` either returns a :class:`ClassifiedRow` whose tool/action is
    a member of that tool's **closed** vocabulary (V2.1 §6.3), or raises a reason
    drawn from :data:`SKIP_REASONS`.  Anything else is a bug, not a policy.
    """
    alias = derive_resource_alias()
    mapped = 0
    skipped: dict[str, int] = {}

    for row in extraction_rows:
        try:
            classified = classify_row(row, alias)
        except ValueError as exc:
            reason = str(exc)
            assert reason in SKIP_REASONS, reason
            skipped[reason] = skipped.get(reason, 0) + 1
            continue
        mapped += 1
        assert classified.tool in TOOL_NAMES, classified
        assert classified.action in actions_for(classified.tool), classified
        assert classified.resource, classified
        assert classified.capability_code == f"{classified.resource}.{classified.action}"

    assert mapped + sum(skipped.values()) == len(extraction_rows)
    # The mapping is *total over the mappable rows*: the great majority must map,
    # and every skip must be one of the four documented situations.
    assert mapped > 2000, mapped
    assert set(skipped) <= {
        SKIP_UNKNOWN_FAMILY,
        SKIP_UNSUPPORTED_OPERATION,
        SKIP_EXECUTE_UNMAPPED,
        SKIP_MALFORMED_ROW,
    }, skipped


def test_the_mapping_table_is_closed_over_the_tool_vocabularies() -> None:
    """Every rule in the table names a real tool and one of its real actions.

    This is the rule of V2.1 §6.1 / 总纲 §0.4 applied to the seeder: the action
    vocabulary is **generated** from the capability table, so a rule that invents
    an action is caught here rather than by a ``VALIDATION_ERROR`` at run time.
    """
    for (family_class, operation), (tool, action) in TOOL_AND_ACTION_RULES.items():
        assert family_class in {"model", "table", "execute"}, family_class
        assert tool in TOOL_NAMES, (family_class, operation)
        assert action in actions_for(tool), (family_class, operation, tool, action)


def test_every_execute_endpoint_maps_to_a_derivable_dispatch() -> None:
    """The endpoint table may not claim a dispatch the loader cannot derive.

    ``capability_loader.derive_dispatch`` rule 9 classifies ``midas_execute`` from
    the closed :data:`EXECUTE_DISPATCH_TABLE`, so a pair outside it would be
    skipped by the loader with ``underivable_dispatch`` — exactly the silent loss
    this test refuses to allow.
    """
    assert EXECUTE_ENDPOINT_CAPABILITIES, "the execute half must not be empty"
    for key, pairs in EXECUTE_ENDPOINT_CAPABILITIES.items():
        assert key[0] == "doc", key
        for pair in pairs:
            assert pair in EXECUTE_DISPATCH_TABLE, (key, pair)


def test_an_unknown_family_is_skipped_and_counted() -> None:
    """``/midas`` / ``/url`` / ``/resource`` / ``/db...`` (EXTRACTION_REPORT §8)."""
    row = {
        "adapter_code": MIDAS_GEN,
        "interface_code": "midas_gen.midas.midas.create",
        "method": "POST",
        "endpoint": "/midas",
        "operation": "create",
        "resource": "midas",
    }
    with pytest.raises(ValueError) as info:
        classify_row(row, {})
    assert str(info.value) == SKIP_UNKNOWN_FAMILY


def test_a_row_missing_its_identity_is_skipped_and_counted() -> None:
    """An empty key is not a usable key, even though the DDL only forbids NULL."""
    with pytest.raises(ValueError) as info:
        classify_row({"adapter_code": "", "endpoint": "/db/NODE"}, {})
    assert str(info.value) == SKIP_MISSING_REQUIRED_FIELD

    with pytest.raises(ValueError) as info:
        classify_row(
            {
                "adapter_code": MIDAS_GEN,
                "interface_code": "midas_gen.db.node.read",
                "method": "TRACE",
                "endpoint": "/db/NODE",
                "operation": "read",
            },
            {},
        )
    assert str(info.value) == SKIP_UNSUPPORTED_METHOD


def test_an_operation_outside_the_target_vocabulary_is_skipped() -> None:
    """``/post/*`` + ``create`` is a design-code check, not a result-table read.

    ``midas_query``'s vocabulary is ``get|list|search|count|inspect`` and
    ``midas_execute``'s is the ``EXECUTE_DISPATCH_TABLE`` set; the extraction's
    ``create`` fits neither for this family, so the row is skipped rather than
    given a guessed action.
    """
    row = {
        "adapter_code": MIDAS_GEN,
        "interface_code": "midas_gen.post.steelcodecheck.execute",
        "method": "POST",
        "endpoint": "/post/steelcodecheck",
        "operation": "execute",
        "resource": "steelcodecheck",
    }
    with pytest.raises(ValueError) as info:
        classify_row(row, {})
    assert str(info.value) == SKIP_UNSUPPORTED_OPERATION


# ---------------------------------------------------------------------------
# 2. the resource question
# ---------------------------------------------------------------------------
def test_the_static_declarations_own_db_aliases_are_reused() -> None:
    """``/db/ELEM`` -> ``element``, ``/db/CNLD`` -> ``load`` (总纲 §0.4).

    The alias is **derived** from the static declaration, not written down here:
    it is the mapping the capability table already carries, and duplicating it
    would let the two drift.
    """
    alias = derive_resource_alias()
    assert alias["/db/NODE"] == "node"
    assert alias["/db/ELEM"] == "element"
    assert alias["/db/MATL"] == "material"
    assert alias["/db/SECT"] == "section"
    assert alias["/db/CNLD"] == "load"
    assert alias["/db/CONS"] == "boundary"
    assert alias["/db/STLD"] == "load_case"
    assert alias["/db/GRUP"] == "group"
    assert alias["/db/ACTL"] == "analysis"
    assert alias["/db/PJCF"] == "project"
    assert alias["/db/UNIT"] == "unit"
    assert alias["/db/STYP"] == "structure_type"
    # Keyed by endpoint, not by resource name: ``/design/SECT`` is a different
    # endpoint from ``/db/SECT`` and must not inherit ``section``.
    assert "/design/SECT" not in alias


def test_a_shared_table_uri_gets_the_table_slug_as_its_resource() -> None:
    """``/post/TABLE`` carries hundreds of logical tables (对接规范 §11.5.6).

    Using the URI's own last segment (``table``) would collapse every result
    table onto one capability, so the ``TABLE_TYPE`` slug the extraction minted
    into ``interface_code`` (V2.1 §17.4) is the resource.
    """
    alias = derive_resource_alias()
    row = {
        "adapter_code": MIDAS_GEN,
        "interface_code": (
            "midas_gen.post.table.beam_force_analysis_result_table_beam_force_anal.query"
        ),
        "method": "POST",
        "endpoint": "/post/TABLE",
        "operation": "query",
        "resource": "table",
    }
    classified = classify_row(row, alias)
    assert classified.resource == (
        "beam_force_analysis_result_table_beam_force_anal"
    )
    assert classified.tool == TOOL_QUERY
    assert classified.action == "get"

    other = {**row, "interface_code": "midas_gen.post.table.reaction_analysis_result_table_reaction_analysis.query"}
    assert classify_row(other, alias).resource != classified.resource


def test_a_design_code_path_is_kept_in_the_resource() -> None:
    """``didp`` exists under several design codes, so the path is part of the key."""
    alias = derive_resource_alias()
    base = {
        "adapter_code": MIDAS_GEN,
        "method": "GET",
        "endpoint": "/design/RC/kds-41-20-2022/didp",
        "operation": "read",
        "resource": "didp",
    }
    rc = classify_row(
        {**base, "interface_code": "midas_gen.design.rc.kds_41_20_2022.didp.read"}, alias
    )
    psc = classify_row(
        {
            **base,
            "endpoint": "/design/PSC/aashto-lrfd24/didp",
            "interface_code": "midas_gen.design.psc.aashto_lrfd24.didp.read",
        },
        alias,
    )
    assert rc.resource == "rc_kds_41_20_2022_didp"
    assert psc.resource == "psc_aashto_lrfd24_didp"
    assert rc.resource != psc.resource


# ---------------------------------------------------------------------------
# 3. seeding: counts, idempotence, uniqueness
# ---------------------------------------------------------------------------
def test_seeding_writes_the_four_tools_from_the_code_declarations(
    sqlite_path: Path,
) -> None:
    """``tools`` comes from :mod:`app.mcp.tools`, never from a literal (总纲 §0.4)."""
    from app.mcp.tools import TOOL_MODULES

    result, factory = _seed(sqlite_path)
    assert result.tools_inserted == 4
    assert result.tools_updated == 0

    with factory() as session:
        rows = {row.name: row for row in session.scalars(select(ToolRow)).all()}
    assert set(rows) == set(TOOL_NAMES)
    for module in TOOL_MODULES:
        row = rows[str(module.TOOL_NAME)]
        assert row.display_name == str(module.TITLE)
        assert row.description == str(module.DESCRIPTION)
        assert json.loads(row.input_schema_json) == module.SCHEMA
        assert row.version == "2.1"  # 总纲 裁决 C-5
        assert row.enabled == 1


def test_seeding_is_idempotent(sqlite_path: Path) -> None:
    """Run twice: the same row counts, no new rows, no duplicates."""
    first, factory = _seed(sqlite_path)
    second = seed_interfaces(factory)

    assert first.rows_read == second.rows_read
    assert second.inserted == 0, second.to_payload()
    assert second.tools_inserted == 0
    assert second.interfaces_inserted == 0
    assert second.capabilities_inserted == 0
    assert second.links_inserted == 0
    assert second.adapters_inserted == 0
    assert second.skipped == first.skipped
    assert second.skipped_by_reason == first.skipped_by_reason
    assert second.mapped_by_tool_action == first.mapped_by_tool_action
    assert second.capabilities == first.capabilities

    with factory() as session:
        interfaces = session.scalars(select(ToolInterfaceRow)).all()
        capabilities = session.scalars(select(CapabilityRow)).all()
    assert len(interfaces) == first.interfaces_inserted
    assert len(capabilities) == first.capabilities_inserted


def test_the_seeded_rows_respect_the_ddl_unique_keys(sqlite_path: Path) -> None:
    """``ux_tool_interface`` and ``ux_capability`` are the database's own guards.

    The seeder must satisfy them, not merely avoid tripping them: a duplicate here
    would mean two extracted rows were merged without being counted.
    """
    result, factory = _seed(sqlite_path)
    with factory() as session:
        interface_keys = [
            (str(row.adapter_code), str(row.interface_code))
            for row in session.scalars(select(ToolInterfaceRow)).all()
        ]
        capability_keys = [
            (str(row.adapter_code or ""), str(row.capability_code))
            for row in session.scalars(select(CapabilityRow)).all()
        ]
        tool_names = [str(row.name) for row in session.scalars(select(ToolRow)).all()]
        links = [
            (int(row.capability_id), int(row.interface_id))
            for row in session.scalars(select(CapabilityInterfaceRow)).all()
        ]

    assert len(interface_keys) == len(set(interface_keys)) == result.interfaces_inserted
    assert len(capability_keys) == len(set(capability_keys)) == result.capabilities_inserted
    assert len(tool_names) == len(set(tool_names)) == 4
    assert len(links) == len(set(links))
    # Every extracted row that became a capability also got its interface stored
    # and linked — the link count is one per stored interface (a shared endpoint
    # adds one more link per extra capability).
    assert result.links_inserted >= result.interfaces_inserted


def test_the_extraction_is_never_invented(sqlite_path: Path) -> None:
    """Every stored endpoint/method pair exists in the file, verbatim (总纲 §0.4).

    A seeder that guessed an endpoint would be indistinguishable from one that
    read the manual correctly — unless the whole set is checked against the source.
    """
    rows = load_interfaces(default_interfaces_path())["rows"]
    expected = {
        (row["adapter_code"], row["interface_code"]): (row["endpoint"], row["method"])
        for row in rows
        if row["endpoint"] is not None
    }

    _, factory = _seed(sqlite_path)
    with factory() as session:
        stored = session.scalars(select(ToolInterfaceRow)).all()

    assert stored
    for row in stored:
        key = (str(row.adapter_code), str(row.interface_code))
        assert key in expected, key
        assert (str(row.endpoint), str(row.method)) == expected[key], key
        assert row.tool_id is None  # 裁决 B-3: the tool is the capability's property


def test_all_three_products_are_seeded(sqlite_path: Path) -> None:
    """多产品多租户路由框架 §二 — gen / civil / cdn, each with its own adapter row."""
    result, factory = _seed(sqlite_path)
    assert result.adapters == (MIDAS_GEN, MIDAS_CIVIL, MIDAS_CDN)

    with factory() as session:
        adapters = {
            row.code: row for row in session.scalars(select(AdapterRow)).all()
        }
        by_adapter: dict[str, int] = {}
        for row in session.scalars(select(CapabilityRow)).all():
            code = str(row.adapter_code)
            by_adapter[code] = by_adapter.get(code, 0) + 1

    assert set(adapters) == set(ADAPTER_CODES)
    for code in ADAPTER_CODES:
        assert by_adapter[code] > 0, code
        # 总纲 §4.2.11: the product scope comes from the code's own map, so
        # ``midas_cdn`` -> ``cdn`` -> ``designer`` cannot drift.
        product = code.removeprefix("midas_")
        assert PRODUCT_SCOPE_BY_PRODUCT[product] in {
            "gen",
            "civil",
            "designer",
        }


def test_seed_adapters_false_without_the_rows_fails_cleanly(sqlite_path: Path) -> None:
    """The FK targets are the caller's business when ``seed_adapters=False``.

    ``capabilities.adapter_code`` and ``tool_interfaces.adapter_code`` are foreign
    keys into ``adapters`` (V2.1 §4), so seeding without them must fail rather
    than silently write rows whose adapter does not exist.  Nothing may be left
    behind: the failed write is rolled back by the session layer.
    """
    factory = session_factory_for(sqlite_path)
    with pytest.raises(Exception):  # IntegrityError, wrapped by the session layer
        seed_interfaces(factory, seed_adapters=False)

    with factory() as session:
        assert session.scalars(select(CapabilityRow)).all() == []
        assert session.scalars(select(ToolInterfaceRow)).all() == []


def test_seed_adapters_false_with_the_rows_present_seeds_normally(
    sqlite_path: Path,
) -> None:
    """With the FK targets already there, ``seed_adapters=False`` is a full seed."""
    factory = session_factory_for(sqlite_path)
    with factory() as session:
        for code in ADAPTER_CODES:
            session.add(
                AdapterRow(
                    code=code,
                    name=code,
                    software=f"MIDAS {code}",
                    implementation="x",
                )
            )
        session.commit()

    result = seed_interfaces(factory, seed_adapters=False)
    assert result.adapters_inserted == 0
    assert result.capabilities > 0
    assert result.adapters == ADAPTER_CODES
    assert _load(factory).skipped == 0


# ---------------------------------------------------------------------------
# 4. the round trip: the loader loads what the seeder wrote
# ---------------------------------------------------------------------------
def test_the_loader_loads_every_seeded_capability_with_no_skip(
    sqlite_path: Path,
) -> None:
    """The join this task exists to prove: seeded rows load with **no** skips.

    A skip here would mean the seeder wrote a shape the loader refuses — the exact
    gap between the extraction and the MCP layer.
    """
    seeded, factory = _seed(sqlite_path)
    result = _load(factory)

    assert result.rows_read == seeded.capabilities_inserted
    assert result.loaded == seeded.capabilities_inserted
    assert result.skipped == 0
    assert result.skip_reasons == {}
    assert result.warnings == {}
    assert result.adapters == (MIDAS_CDN, MIDAS_CIVIL, MIDAS_GEN)


def test_the_loaded_table_contains_the_seeded_codes(sqlite_path: Path) -> None:
    """Spot-check the capability codes a caller would actually resolve."""
    _, factory = _seed(sqlite_path)
    _load(factory)

    gen = capability_table(MIDAS_GEN)
    for code, tool, resource, action in (
        ("node.get", TOOL_QUERY, "node", "get"),
        ("node.create", TOOL_MODEL, "node", "create"),
        ("node.update", TOOL_MODEL, "node", "update"),
        ("node.delete", TOOL_MODEL, "node", "delete"),
        ("load.create", TOOL_MODEL, "load", "create"),
        ("element.get", TOOL_QUERY, "element", "get"),
        ("unit.update", TOOL_MODEL, "unit", "update"),
        ("model.calculate", TOOL_EXECUTE, "model", "calculate"),
        ("analysis.analysis", TOOL_EXECUTE, "analysis", "analysis"),
        ("project.open_project", TOOL_EXECUTE, "project", "open_project"),
        ("file.import", TOOL_EXECUTE, "file", "import"),
    ):
        row = gen[code]
        assert (row.tool, row.resource, row.action) == (tool, resource, action), code

    # The three products serve the same code as **three rows**, not one
    # overwritten twice (裁决 B-3 / ``ux_capability``).
    for adapter in (MIDAS_CIVIL, MIDAS_CDN):
        assert "node.get" in capability_table(adapter), adapter


def test_the_loaded_table_still_carries_the_platform_owned_rows(sqlite_path: Path) -> None:
    """The loader upserts and never prunes, so ``midas_task`` survives a seed."""
    _, factory = _seed(sqlite_path)
    _load(factory)
    platform = capability_table(None)
    assert len(platform) == 7
    assert all(row.tool == "midas_task" for row in platform.values())
    assert all(row.adapter_code is None for row in platform.values())


# ---------------------------------------------------------------------------
# 5. THE ACCEPTANCE TEST — a seeded row equals its static counterpart
# ---------------------------------------------------------------------------
def test_a_seeded_capability_matches_its_static_counterpart(sqlite_path: Path) -> None:
    """**The acceptance test**: the DB reproduces the declaration field for field.

    Every static ``midas_gen`` row the extraction also produces is compared
    against the loaded row.  Nothing is relaxed except the seven fields of
    :data:`KNOWN_DIFFERENCES`, and each of those is asserted to be *present* where
    it is expected — so a field that silently started differing would fail here.
    """
    static = {row.code: row for row in capability_rows() if row.adapter_code == MIDAS_GEN}
    assert len(static) == 155, "the declaration's midas_gen half changed"

    _, factory = _seed(sqlite_path)
    _load(factory)
    loaded = capability_table(MIDAS_GEN)

    assert set(static) <= set(loaded), sorted(set(static) - set(loaded))
    assert len(loaded) > len(static)

    mismatched: dict[str, dict[str, tuple[Any, Any]]] = {}
    for code, expected in static.items():
        diffs = _field_diffs(expected, loaded[code])
        unexpected = set(diffs) - KNOWN_DIFFERENCES
        if unexpected:
            mismatched[code] = {name: diffs[name] for name in unexpected}
    assert not mismatched, f"{len(mismatched)} rows differ: {sorted(mismatched)[:3]}"

    # The seven known differences must be *exactly* what happens, not merely
    # allowed: the classification layers are filled in, the interface code is the
    # extraction's, and the payload schema is deliberately absent.  Only the rows
    # the extraction actually produced are checked — the declaration also ships
    # platform-side rows (``server.get`` …) that have no interface at all.
    seeded_codes = {
        code
        for code, row in loaded.items()
        if row.interface_code.startswith(f"{MIDAS_GEN}.")
    }
    assert seeded_codes, "no seeded rows found"
    for code in sorted(seeded_codes & set(static)):
        actual = loaded[code]
        assert actual.interface_code.startswith(f"{MIDAS_GEN}."), code
        if static[code].domain is None:
            assert actual.domain is not None, code
        assert actual.request_schema == {}, code

    # The static rows the extraction cannot produce keep their declaration.
    static_only = {
        row.code for row in capability_rows() if row.adapter_code == MIDAS_GEN
    } - set(loaded)
    assert static_only == set()


def test_the_static_declaration_is_the_only_thing_that_survives_a_reset(
    sqlite_path: Path,
) -> None:
    """``reset_capabilities()`` restores the declaration — the offline fallback.

    The seeder and the loader both mutate a module global; the offline suite must
    still run with no database at all.
    """
    before = capability_rows()
    _, factory = _seed(sqlite_path)
    _load(factory)
    assert len(capability_rows()) > len(before)

    reset_capabilities()
    assert capability_rows() == before
    assert len(capability_rows()) == 162  # 155 midas_gen + 7 platform-owned
    assert capability_table(MIDAS_GEN)["node.get"].request_schema != {}


def test_a_seeded_update_row_carries_the_manuals_own_verb(sqlite_path: Path) -> None:
    """The extraction is authoritative for ``method`` (总纲 §0.4).

    The declaration hard-codes ``POST`` for every ``midas_model`` write except
    ``delete``; the manual documents ``PUT`` for an update.  The seeded row
    follows the manual, and this test names that difference so it cannot change
    silently — while the fields that decide *routing* stay identical.
    """
    _, factory = _seed(sqlite_path)
    _load(factory)
    static = {row.code: row for row in capability_rows() if row.adapter_code == MIDAS_GEN}
    loaded = capability_table(MIDAS_GEN)

    for code in ("node.update", "element.update", "load.update", "boundary.update"):
        assert loaded[code].method == "PUT", code
        # Routing is unchanged: same tool, same resource, same action, same
        # dispatch, same endpoint.  Only the wire verb follows the manual.
        assert loaded[code].dispatch == static[code].dispatch == "model"
        assert loaded[code].endpoint == static[code].endpoint
        assert loaded[code].resource == static[code].resource
        assert loaded[code].action == static[code].action
        # ``node`` / ``element`` are declared ``POST`` and the manual says ``PUT``;
        # naming the declaration's verb here keeps the difference explicit.
        assert static[code].method in {"POST", "PUT"}, code


# ---------------------------------------------------------------------------
# 6. dispatch: resolve -> gate -> handler -> adapter (v1.2 §38)
# ---------------------------------------------------------------------------
class _Env:
    """One offline MCP stack: a mock adapter + registry + tasks + dispatcher."""

    def __init__(self, model: dict[str, dict[str, Any]] | None = None) -> None:
        self.registry = AdapterRegistry()
        self.adapter = MockAdapter(code=MIDAS_GEN, software="MIDAS Gen", model=model)
        self.registry.register(self.adapter)
        self.tasks = TaskService(max_concurrency=2)
        self.resolver = CapabilityResolver(self.registry)
        self.dispatcher = ToolDispatcher(
            registry=self.registry,
            resolver=self.resolver,
            task_service=self.tasks,
        )

    def call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return run(self.dispatcher.dispatch(tool, arguments))


@pytest.fixture()
def seeded_env(sqlite_path: Path) -> _Env:
    """Seed, load, and stand up a dispatcher over the **DB-loaded** table."""
    _seed(sqlite_path)
    result = _load(session_factory_for(sqlite_path))
    assert result.skipped == 0 and result.warnings == {}
    return _Env(model={"NODE": {"1": {"X": 0.0, "Y": 0.0, "Z": 0.0}}})


def test_a_db_loaded_read_capability_dispatches_to_the_adapter(seeded_env: _Env) -> None:
    """``node.get``: ``midas_query`` -> ``adapter.query()`` -> ``GET /db/NODE``."""
    envelope = seeded_env.call(
        "midas_query", {"target": "node", "action": "list", "adapter": MIDAS_GEN}
    )
    assert envelope["success"] is True, envelope["errors"]
    assert envelope["status"] == "success"
    assert envelope["errors"] == []
    assert envelope["data"]["resource"] == "node"
    assert envelope["data"]["total"] == 1
    assert [entry["method"] for entry in seeded_env.adapter.request_log] == ["GET"]
    assert seeded_env.adapter.request_log[0]["endpoint"] == "/db/NODE"


def test_a_db_loaded_write_capability_dispatches_to_the_adapter(seeded_env: _Env) -> None:
    """``node.create``: ``midas_model`` -> ``adapter.model()`` -> ``POST /db/NODE``.

    The endpoint comes from the **seeded** interface row, so a wrong
    ``interface_id``/``endpoint`` mapping would show up as a call to the wrong URI.
    """
    envelope = seeded_env.call(
        "midas_model",
        {
            "resource": "node",
            "action": "create",
            "adapter": MIDAS_GEN,
            "data": {"2": {"X": 1.0, "Y": 0.0, "Z": 0.0}},
        },
    )
    assert envelope["success"] is True, envelope["errors"]
    writes = seeded_env.adapter.calls(method="POST")
    assert len(writes) == 1
    assert writes[0]["endpoint"] == "/db/NODE"
    assert writes[0]["body"] == {"Assign": {"2": {"X": 1.0, "Y": 0.0, "Z": 0.0}}}


def test_a_db_loaded_execute_capability_dispatches_to_the_adapter(seeded_env: _Env) -> None:
    """``model.calculate``: ``midas_execute`` -> ``adapter.execute()`` inline.

    ``task_type='calculate'`` would normally queue a task (V2.1 §9.2), so
    ``options.wait=true`` runs it inline — which is what makes the adapter call
    observable in one request.
    """
    envelope = seeded_env.call(
        "midas_execute",
        {
            "resource": "model",
            "action": "calculate",
            "adapter": MIDAS_GEN,
            "options": {"wait": True},
        },
    )
    assert envelope["success"] is True, envelope["errors"]
    assert envelope["task_id"] is None
    assert envelope["data"]["message"] == "... command complete"


def test_a_db_loaded_execute_row_that_queues_a_task(seeded_env: _Env) -> None:
    """The same capability without ``wait`` is queued (V2.1 §9.2 / §26.1)."""
    envelope = seeded_env.call(
        "midas_execute",
        {"resource": "model", "action": "calculate", "adapter": MIDAS_GEN},
    )
    assert envelope["success"] is True, envelope["errors"]
    assert envelope["status"] == "queued"
    assert envelope["task_id"].startswith("task_")


def test_a_db_loaded_capability_is_gated_by_the_resolver(seeded_env: _Env) -> None:
    """Gates 1–4 run on the seeded rows too (V2.1 §16.2 / 总纲 §4.9.2).

    An unregistered adapter is ``ADAPTER_NOT_FOUND``; a capability the adapter
    does not serve is ``CAPABILITY_NOT_SUPPORTED``.  Neither may fall back to a
    direct endpoint call (V2.1 §16.2).

    The resolver is called **directly** here, because ``ToolDispatcher`` validates
    the arguments against the published tool schema *first* — so an unknown
    ``target`` never reaches the resolver through the envelope, which is itself
    the §6.1 ``additionalProperties``/``enum`` guarantee in action.
    """
    from app.adapters.errors import AdapterError
    from app.core.errors import ErrorCode

    with pytest.raises(AdapterError) as info:
        seeded_env.resolver.resolve(MIDAS_GEN, TOOL_QUERY, "get", "no_such_resource")
    assert info.value.code == ErrorCode.CAPABILITY_NOT_SUPPORTED.value

    # Gate 1: the capability exists, but no adapter is registered for it.
    with pytest.raises(AdapterError) as info:
        seeded_env.resolver.resolve(MIDAS_CIVIL, TOOL_QUERY, "get", "node")
    assert info.value.code == ErrorCode.ADAPTER_NOT_FOUND.value

    # …and the published schema refuses the unknown target before any of that.
    envelope = seeded_env.call(
        "midas_query",
        {"target": "no_such_resource", "action": "get", "adapter": MIDAS_GEN},
    )
    assert envelope["success"] is False
    assert envelope["errors"][0]["code"] == ErrorCode.VALIDATION_ERROR.value


def test_a_seeded_capability_carries_the_unverified_scope_warning(seeded_env: _Env) -> None:
    """总纲 §4.2.11: ``product_scope='unknown'`` is admitted **with** a warning.

    Every extracted row ships ``unknown`` (``meta.product_scope_policy``), so the
    seeded table exercises the optimistic-admission path the ruling describes.
    """
    envelope = seeded_env.call(
        "midas_query", {"target": "node", "action": "list", "adapter": MIDAS_GEN}
    )
    assert envelope["success"] is True
    assert any("product_scope='unknown'" in warning for warning in envelope["warnings"])


# ---------------------------------------------------------------------------
# 7. the report itself
# ---------------------------------------------------------------------------
def test_the_report_vocabularies_are_closed_and_the_payload_is_json_safe(
    sqlite_path: Path,
) -> None:
    """The counters are the contract: closed reason sets, self-consistent totals.

    The partition is over **rows**, and every classified row writes exactly one
    ``tool_interfaces`` row (a collapse shares the capability row, not the
    interface row), so ``rows_read == interfaces + skipped`` holds exactly.
    """
    result, _ = _seed(sqlite_path)

    assert result.rows_read == (
        result.interfaces_inserted + result.interfaces_updated + result.skipped
    )
    assert result.skipped == sum(result.skipped_by_reason.values())
    assert set(result.skipped_by_reason) <= SKIP_REASONS
    assert result.capabilities == result.capabilities_inserted + result.capabilities_updated
    # ``capabilities_inserted`` is the number of distinct rows the table holds:
    # a collapse adds none, an extra pair of a shared endpoint adds one, and both
    # are counted as they happen.
    assert result.collapsed_rows == sum(len(codes) for codes in result.collapsed.values())
    assert result.capabilities_inserted >= result.interfaces_inserted
    payload = result.to_payload()
    assert json.loads(json.dumps(payload)) == payload
    assert payload["adapters"] == [MIDAS_GEN, MIDAS_CIVIL, MIDAS_CDN]
    assert payload["skipped_by_reason"] == dict(sorted(payload["skipped_by_reason"].items()))


def test_every_extracted_row_that_mapped_is_accounted_for_in_the_report(
    sqlite_path: Path,
) -> None:
    """``rows_read == capabilities_written + skipped``, and the mapping is named.

    The report is what stops a silent drop: a row neither written nor counted is
    the failure this result object exists to make impossible.
    """
    result, _ = _seed(sqlite_path)
    assert result.mapped_by_family
    assert set(result.mapped_by_family) <= {
        "db",
        "design",
        "post",
        "doc",
        "ope",
        "view",
        "rating",
    }
    assert result.mapped_by_tool_action
    for key, count in result.mapped_by_tool_action.items():
        tool, _, action = key.partition(".")
        assert tool in TOOL_NAMES
        assert action in actions_for(tool)
        assert count > 0


def test_a_collapsed_slot_is_reported_not_hidden(sqlite_path: Path) -> None:
    """Several extracted rows may legitimately share one capability slot.

    A URI with ``GET/POST/PUT/DELETE`` becomes four codes and does **not**
    collapse; what collapses is two *different* endpoints that mean the same
    action (``/doc/SAVE`` and ``/doc/SAVEAS`` are both ``project.save_project``).
    The first row wins, the loser's interface row is still stored and linked, and
    the collapse is reported by capability code.
    """
    result, factory = _seed(sqlite_path)
    assert result.collapsed, "expected at least one shared-slot collapse"
    for code, interface_codes in result.collapsed.items():
        assert "." in code
        assert interface_codes
        assert all(item.startswith("midas_") for item in interface_codes)

    with factory() as session:
        # The loser's interface is stored, so the extraction is not lost even
        # where the capability row is shared.
        stored = {
            str(row.interface_code)
            for row in session.scalars(select(ToolInterfaceRow)).all()
        }
    for interface_codes in result.collapsed.values():
        assert set(interface_codes) <= stored


def test_the_interfaces_of_a_shared_endpoint_are_all_linked(sqlite_path: Path) -> None:
    """裁决 B-3: one endpoint may serve several capabilities, and all are linked.

    ``/doc/ANAL`` is ``model.calculate`` **and** ``analysis.analysis`` in the
    static declaration, so the two capability rows must both point at the one
    interface row — which is what makes the link table, rather than a duplicated
    interface, the right shape.
    """
    _, factory = _seed(sqlite_path)
    with factory() as session:
        rows = {
            str(row.capability_code): row
            for row in session.scalars(
                select(CapabilityRow).where(CapabilityRow.adapter_code == MIDAS_GEN)
            ).all()
        }
        assert {"model.calculate", "analysis.analysis"} <= set(rows)
        interface_ids = {
            int(rows[code].interface_id) for code in ("model.calculate", "analysis.analysis")
        }
        assert len(interface_ids) == 1
        interface = session.get(ToolInterfaceRow, interface_ids.pop())
        assert interface is not None
        assert interface.endpoint == "/doc/ANAL"
        assert interface.method == "POST"

        links = {
            (int(link.capability_id), int(link.interface_id))
            for link in session.scalars(
                select(CapabilityInterfaceRow).where(
                    CapabilityInterfaceRow.interface_id == int(interface.id)
                )
            ).all()
        }
    assert len(links) == 2


def test_a_collapsed_row_still_gets_its_interface_stored(sqlite_path: Path) -> None:
    """A shared capability slot does not cost the extraction its interface row.

    ``/db/GSBG`` documents both a ``read`` (GET) and a ``query`` (POST), and both
    mean "read this table" to the MCP layer — so they share ``gsbg.get``.  The
    capability row is shared; the endpoint each row named is still written and
    linked (裁决 B-3), so nothing the extraction contained is lost.
    """
    result, factory = _seed(sqlite_path)
    assert result.collapsed, "expected at least one shared-slot collapse"
    losers = {code for codes in result.collapsed.values() for code in codes}
    assert losers

    with factory() as session:
        stored = {
            str(row.interface_code)
            for row in session.scalars(select(ToolInterfaceRow)).all()
        }
    assert losers <= stored, sorted(losers - stored)


def test_the_mapped_families_cover_the_whole_extraction(sqlite_path: Path) -> None:
    """Every family the extraction emits is either mapped or counted — never lost."""
    rows = load_interfaces(default_interfaces_path())["rows"]
    families = {
        (row["endpoint"].split("/")[1].lower() if row["endpoint"].startswith("/") else "")
        for row in rows
    }
    result, _ = _seed(sqlite_path)

    # Every family that produced a capability is named in the report…
    assert set(result.mapped_by_family) <= families
    # …and the unmappable family that the extraction does emit is the counted one.
    assert SKIP_UNKNOWN_FAMILY not in result.mapped_by_family
    assert result.skipped_by_reason.get(SKIP_UNKNOWN_FAMILY, 0) > 0
    # ``/oprt/*`` is the family the extraction emits that the seeder has no rule
    # for at all, so it must be counted rather than silently dropped.
    assert "oprt" in families
    assert "oprt" not in result.mapped_by_family


def test_classify_row_is_deterministic_and_side_effect_free() -> None:
    """The classifier is pure: the same row always gives the same answer."""
    row = {
        "adapter_code": MIDAS_GEN,
        "interface_code": "midas_gen.db.node.read",
        "method": "GET",
        "endpoint": "/db/NODE",
        "operation": "read",
        "resource": "node",
    }
    alias = derive_resource_alias()
    first = classify_row(row, alias)
    second = classify_row(row, alias)
    assert first == second
    assert isinstance(first, ClassifiedRow)
    assert capability_slot(first.resource, first.action) == "node.get"


def test_seeding_a_file_with_no_rows_is_an_empty_but_complete_report(
    sqlite_path: Path, tmp_path: Path
) -> None:
    """A structurally valid but empty extraction is a report, not a crash."""
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"meta": {}, "rows": []}), encoding="utf-8")
    result, factory = _seed(sqlite_path, path=empty)
    assert result.rows_read == 0
    assert result.skipped == 0
    assert result.capabilities_inserted == 0
    assert result.tools_inserted == 4  # the tools come from the code, not the file
    assert _load(factory).rows_read == 0
