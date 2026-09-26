"""Offline Task Engine **persistence** tests — V2.1 §26 / 总纲 §4.1.5, §4.2.1, §4.5.1.

Plain ``pytest`` only: async entry points are driven with ``asyncio.run`` so the
suite does not depend on ``pytest-asyncio`` being configured (matching
``tests/test_mcp_layer.py`` and ``tests/test_adapter_offline.py``).

Everything here runs against a **real SQLite file in ``tmp_path``** — no live
MIDAS, no network, no process-wide engine.  What is proven, and against which
rule:

========================================================  ==========================
claim                                                     依据
========================================================  ==========================
``TaskService`` survives a process restart                 V2.1 §26.3 落库对应
``request_id`` -> ``task_id`` chain survives               V2.1 §26.4 / 总纲 §4.1.5
``parent_task_id`` survives (sub-task / retry chain)       V2.1 §26.4 / 总纲 §4.1.6
``status`` is never written outside the closed set        总纲 §4.2.1（+ CHECK, 裁决 B-10）
``created_at`` / ``updated_at`` stay ORM-maintained       总纲 §4.5.1（无触发器）
JSON payloads round-trip exactly (nested / unicode / None) V2.1 §26.3（result_json）
the ``since`` event cursor still works after a restart     V2.1 §10.3
orphaned ``queued`` / ``running`` / ``retrying`` -> failed  V2.1 §26.1 + 总纲 §4.4.9
in-memory and SQL stores are interchangeable              V2.1 §26.3
========================================================  ==========================
"""

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any, Callable

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  (registers all 49 tables on Base.metadata)
from app.adapters.base import AdapterResult
from app.adapters.errors import AdapterError
from app.core.constants import TaskStatus, TaskType
from app.core.errors import ErrorCode
from app.db.base import Base
from app.models.identity import User
from app.models.midas import Adapter, MidasClient
from app.models.registry import Tool
from app.services.task_service import (
    ORPHAN_STATUSES,
    TERMINAL_STATUSES,
    TaskService,
    get_task_service,
    init_task_service,
    reset_task_service,
)
from app.services.task_store import (
    InMemoryTaskStore,
    SqlAlchemyTaskStore,
    SyncTaskStore,
    TaskEventRecord,
    TaskRecord,
    TaskStore,
    utcnow,
)

#: 总纲 §4.2.1 — the closed ``tasks.status`` set, written out so a vocabulary
#: change cannot slip through unnoticed.
CLOSED_STATUSES = frozenset(
    {"queued", "running", "success", "failed", "cancelled", "retrying"}
)

#: 总纲 §4.1.5 — the trace chain's request prefix (总纲 §4.1.3 closed set).
REQUEST_ID = "req_20260925_000042"


def run(coro: Any) -> Any:
    """Drive one coroutine to completion (no pytest-asyncio dependency)."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# a real SQLite file, with the same pragmas as app.db.session
# ---------------------------------------------------------------------------
#: One engine per database file.  The *store* and the *service* are rebuilt for
#: every simulated restart; only the file (and its pool) is reused, which is what
#: makes the restart genuine — no ORM identity map survives between sessions.
_FACTORIES: dict[str, Callable[[], Session]] = {}


def _enable_foreign_keys(dbapi_connection: Any, connection_record: Any) -> None:  # noqa: ANN001
    """``PRAGMA foreign_keys=ON`` — mandatory, mirrors :mod:`app.db.session`.

    Without it SQLite silently ignores the ``ON DELETE CASCADE`` on
    ``task_events`` and the whole ``tasks`` foreign-key set (V2.1 §4).
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def session_factory_for(path: Path) -> Callable[[], Session]:
    """Build (once per file) a sync ``sessionmaker`` over ``path``.

    The models are **synchronous** SQLAlchemy 2.x declarative and
    :mod:`app.db.session` exposes a sync ``SessionLocal``, so the store is handed
    a sync factory; no async driver is added (总纲 §4.5.1 keeps one ORM stack).
    """
    key = str(path)
    existing = _FACTORIES.get(key)
    if existing is not None:
        return existing

    engine: Engine = create_engine(
        f"sqlite:///{path}",
        future=True,
        # The store hands every call to ``asyncio.to_thread``, so a pooled
        # connection can be picked up by a different worker thread than the one
        # that opened it.  Exactly the reason ``app.db.session`` sets this.
        connect_args={"check_same_thread": False},
    )
    event.listen(engine, "connect", _enable_foreign_keys)
    # NOTE: no ``Base.metadata.create_all()`` here.  The schema is built once per
    # session by the ``schema_template`` fixture (tests/conftest.py) and the
    # ``sqlite_path`` fixture copies that file, so every test still starts from a
    # pristine 49-table database — it just no longer pays ~2 s to rebuild it.
    factory: Callable[[], Session] = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )
    _FACTORIES[key] = factory
    return factory


@pytest.fixture()
def sqlite_path(tmp_path: Path, schema_template: Path) -> Path:
    """A fresh copy of the empty 49-table schema, per test.

    ``schema_template`` is session-scoped (see ``tests/conftest.py``): the schema
    is built once and copied, because ``create_all()`` per test cost ~2 s and
    dominated the suite's runtime.
    """
    target = tmp_path / "structai_tasks.db"
    shutil.copyfile(schema_template, target)
    return target


def build_store(kind: str, sqlite_path: Path) -> TaskStore:
    """One store of ``kind`` — ``"memory"`` or ``"sqlalchemy"``."""
    if kind == "memory":
        return InMemoryTaskStore()
    return SqlAlchemyTaskStore(session_factory_for(sqlite_path))


@pytest.fixture(params=["memory", "sqlalchemy"])
def any_store(request: pytest.FixtureRequest, sqlite_path: Path) -> TaskStore:
    """The same behaviour must hold for both implementations (V2.1 §26.3)."""
    return build_store(str(request.param), sqlite_path)


#: ``users.id`` values the ownership tests attribute tasks to.
OWNER_IDS: tuple[int, ...] = (7, 8, 99)


@pytest.fixture()
def seeded_owners(sqlite_path: Path) -> None:
    """Create the ``users`` rows the ownership tests attribute tasks to.

    ``tasks.requested_by`` is a real foreign key (总纲 §4.1.6) and the SQLAlchemy
    store runs with ``PRAGMA foreign_keys=ON``, so a task cannot be attributed to
    a user that does not exist — the insert fails with ``IntegrityError``.
    ``InMemoryTaskStore`` enforces no such constraint, which is precisely why the
    parametrised test must seed for **both**: without it the two stores only
    *appear* to agree, and the SQL-backed one would be the only one that noticed.
    """
    factory = session_factory_for(sqlite_path)
    with factory() as session:
        for user_id in OWNER_IDS:
            if session.get(User, user_id) is None:
                session.add(
                    User(
                        id=user_id,
                        username=f"owner{user_id}",
                        name=f"Owner {user_id}",
                        password_hash="not-a-real-hash",
                    )
                )
        session.commit()


# ---------------------------------------------------------------------------
# 1. the protocol itself
# ---------------------------------------------------------------------------
def test_the_status_vocabulary_is_the_closed_six_of_the_master_spec() -> None:
    """总纲 §4.2.1 — a closed set, not a suggestion."""
    assert {member.value for member in TaskStatus} == CLOSED_STATUSES
    assert TERMINAL_STATUSES == {"success", "failed", "cancelled"}
    assert ORPHAN_STATUSES == {"queued", "running", "retrying"}
    assert TERMINAL_STATUSES.isdisjoint(ORPHAN_STATUSES)


def test_both_stores_satisfy_the_same_protocol(any_store: TaskStore) -> None:
    """``TaskStore`` + its synchronous mirror, implemented by both stores."""
    assert isinstance(any_store, TaskStore)
    assert isinstance(any_store, SyncTaskStore)


def test_the_default_store_is_still_in_memory() -> None:
    """Every pre-existing call site keeps the old, DB-free behaviour."""
    service = TaskService(max_concurrency=2)
    assert isinstance(service.store, InMemoryTaskStore)


def test_stores_agree_on_save_load_list_events_and_delete(any_store: TaskStore) -> None:
    """One behavioural contract, asserted once for both implementations."""

    async def scenario() -> None:
        task_id = "task_20260925_000001"
        record = TaskRecord(
            task_id=task_id,
            type=TaskType.CALCULATE.value,
            action="calculate",
            resource="model",
            priority=2,
            status=TaskStatus.RUNNING.value,
            progress=42.5,
            retry_count=1,
            max_retries=3,
            input={"a": [1, None, "中文"]},
        )
        await any_store.save_task(record)

        loaded = await any_store.load_task(task_id)
        assert loaded is not None
        assert loaded.task_id == task_id
        assert loaded.status == TaskStatus.RUNNING.value
        assert loaded.progress == 42.5
        assert loaded.retry_count == 1
        assert loaded.max_retries == 3
        assert loaded.input == {"a": [1, None, "中文"]}
        assert loaded.result is None
        assert await any_store.load_task("task_20260925_000404") is None
        assert [row.task_id for row in await any_store.list_tasks()] == [task_id]

        first = TaskEventRecord(
            id=0,
            task_id=task_id,
            event_type="queued",
            progress=0.0,
            message="q",
            payload={"priority": 2},
            created_at=utcnow(),
        )
        second = TaskEventRecord(
            id=0,
            task_id=task_id,
            event_type="log",
            progress=None,
            message="l",
            payload=None,
            created_at=utcnow(),
        )
        await any_store.save_event(first)
        await any_store.save_event(second)
        # The store owns the id (autoincrement PK / process counter), and it is
        # monotonic — that is what makes the §10.3 ``since`` cursor meaningful.
        assert first.id > 0
        assert second.id > first.id

        all_events = await any_store.load_events(task_id)
        assert [row.event_type for row in all_events] == ["queued", "log"]
        assert all_events[0].payload == {"priority": 2}
        assert all_events[1].payload is None
        assert all_events[0].created_at.tzinfo is not None, "总纲 §4.5.1: stored UTC"

        tail = await any_store.load_events(task_id, since=first.id)
        assert [row.event_type for row in tail] == ["log"]

        assert await any_store.delete_task(task_id) is True
        assert await any_store.load_task(task_id) is None
        assert await any_store.load_events(task_id) == []
        assert await any_store.delete_task(task_id) is False

    run(scenario())


def test_both_stores_filter_by_ownership_the_same_way(
    any_store: TaskStore, seeded_owners: None
) -> None:
    """v1.2 §20.1 / §21 — the ownership scope is a **store-level query filter**.

    ``requested_by`` excludes another user's rows, and it **fails closed** on an
    unattributed one (``requested_by IS NULL``): a row that belongs to nobody is
    matched by nobody, so it stays visible only to an unfiltered caller.  Both
    stores must agree exactly.  The REST list endpoint pushes its scope down to
    this argument precisely so the page and its ``total`` are computed over the
    rows the caller may see; a filter applied to the returned page could not do
    either.
    """

    async def scenario() -> None:
        owned = [
            ("task_20260925_100001", 7),
            ("task_20260925_100002", 8),
            ("task_20260925_100003", None),
        ]
        for task_id, owner in owned:
            await any_store.save_task(
                TaskRecord(
                    task_id=task_id,
                    type=TaskType.CALCULATE.value,
                    action="calculate",
                    requested_by=owner,
                )
            )

        # The default stays "no ownership filter at all" (super_admin / internal),
        # which is also the only way the unattributed row is reachable.
        assert {row.task_id for row in await any_store.list_tasks()} == {
            task_id for task_id, _owner in owned
        }

        mine = await any_store.list_tasks(requested_by=7)
        assert {row.task_id for row in mine} == {"task_20260925_100001"}, (
            "own rows only — the unattributed one must NOT be swept in"
        )

        # A caller who owns nothing sees nothing, not even the orphan.
        stranger = await any_store.list_tasks(requested_by=99)
        assert stranger == []

    run(scenario())


def test_deleting_a_task_cascades_to_its_events(sqlite_path: Path) -> None:
    """``task_events`` is ``ON DELETE CASCADE`` (V2.1 §4) — with FK pragma on."""
    factory = session_factory_for(sqlite_path)
    store = SqlAlchemyTaskStore(factory)
    task_id = "task_20260925_000009"

    async def scenario() -> None:
        await store.save_task(
            TaskRecord(
                task_id=task_id,
                type=TaskType.CALCULATE.value,
                action="calculate",
            )
        )
        await store.save_event(
            TaskEventRecord(
                id=0,
                task_id=task_id,
                event_type="queued",
                progress=0.0,
                message="q",
                payload=None,
                created_at=utcnow(),
            )
        )
        assert await store.delete_task(task_id) is True

    run(scenario())

    with factory() as session:
        assert (
            session.scalar(
                text("SELECT COUNT(*) FROM task_events WHERE task_id = :task_id"),
                {"task_id": task_id},
            )
            == 0
        ), "the DDL cascade must actually run"


def test_saving_the_same_task_twice_updates_one_row(any_store: TaskStore) -> None:
    """Idempotent per ``task_id`` — an update, never a duplicate (总纲 §4.1.2)."""

    async def scenario() -> None:
        task_id = "task_20260925_000002"
        await any_store.save_task(
            TaskRecord(
                task_id=task_id,
                type=TaskType.CALCULATE.value,
                action="calculate",
            )
        )
        await any_store.save_task(
            TaskRecord(
                task_id=task_id,
                type=TaskType.CALCULATE.value,
                action="calculate",
                status=TaskStatus.SUCCESS.value,
                progress=100.0,
                result={"items": []},
            )
        )
        rows = await any_store.list_tasks()
        assert [row.task_id for row in rows] == [task_id]
        loaded = await any_store.load_task(task_id)
        assert loaded is not None
        assert loaded.status == TaskStatus.SUCCESS.value
        assert loaded.result == {"items": []}

    run(scenario())


# ---------------------------------------------------------------------------
# 2. a bad status is refused loudly, and the CHECK backs it up
# ---------------------------------------------------------------------------
def test_a_bad_status_is_refused_before_it_is_written(any_store: TaskStore) -> None:
    """总纲 §4.2.1 — fail loudly, do not write.  Both stores agree."""
    record = TaskRecord(
        task_id="task_20260925_000003",
        type=TaskType.CALCULATE.value,
        action="calculate",
        status="bogus",
    )

    async def scenario() -> None:
        with pytest.raises(AdapterError) as excinfo:
            await any_store.save_task(record)
        assert excinfo.value.code == ErrorCode.VALIDATION_ERROR.value
        assert await any_store.load_task(record.task_id) is None, "nothing may be written"

    run(scenario())


def test_the_tasks_status_check_really_rejects_a_bad_value(sqlite_path: Path) -> None:
    """裁决 B-10 — the constraint lives in the data, not only in Python."""
    factory = session_factory_for(sqlite_path)
    insert = text(
        "INSERT INTO tasks "
        "(task_id, type, action, status, progress, priority, retry_count, max_retries,"
        " queued_at, created_at, updated_at) "
        "VALUES (:task_id, 'calculate', 'calculate', :status, 0, 5, 0, 3,"
        " CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )

    with pytest.raises(IntegrityError):
        with factory() as session:
            session.execute(insert, {"task_id": "task_20260925_000900", "status": "bogus"})
            session.commit()

    # Control: the very same statement with a closed-set value is accepted, so the
    # failure above is the CHECK and not some unrelated NOT NULL / FK accident.
    with factory() as session:
        session.execute(
            insert, {"task_id": "task_20260925_000901", "status": "queued"}
        )
        session.commit()


# ---------------------------------------------------------------------------
# 3. field-by-field mapping
# ---------------------------------------------------------------------------
def test_json_payloads_round_trip_exactly(any_store: TaskStore) -> None:
    """``input_json`` / ``result_json`` — nested, unicode, and ``None``."""
    payload: dict[str, Any] = {
        "nested": {"list": [1, 2.5, True, False, None], "deep": {"值": "弯矩 kN·m"}},
        "unicode": "温度 ±20℃ — 截面 🏗",
        "empty_dict": {},
        "empty_list": [],
        "zero": 0,
        "null": None,
    }

    async def scenario() -> None:
        task_id = "task_20260925_000004"
        await any_store.save_task(
            TaskRecord(
                task_id=task_id,
                type=TaskType.REPORT.value,
                action="generate_report",
                input=payload,
                result=payload,
            )
        )
        loaded = await any_store.load_task(task_id)
        assert loaded is not None
        assert loaded.input == payload
        assert loaded.result == payload
        assert json.dumps(loaded.input, ensure_ascii=False, sort_keys=True) == json.dumps(
            payload, ensure_ascii=False, sort_keys=True
        )

        # ``None`` is stored as SQL NULL, so it comes back as ``None`` (not "null").
        bare_id = "task_20260925_000005"
        await any_store.save_task(
            TaskRecord(
                task_id=bare_id,
                type=TaskType.REPORT.value,
                action="generate_report",
                input=None,
                result=None,
            )
        )
        bare = await any_store.load_task(bare_id)
        assert bare is not None
        assert bare.input is None
        assert bare.result is None

    run(scenario())


def test_every_column_of_a_task_survives_a_round_trip(any_store: TaskStore) -> None:
    """Map ``TaskRecord`` <-> ``tasks`` field by field (总纲 §4.1.5, §4.1.6)."""

    async def scenario() -> None:
        task_id = "task_20260925_000006"
        parent_id = "task_20260925_000007"
        await any_store.save_task(
            TaskRecord(
                task_id=parent_id,
                type=TaskType.CALCULATE.value,
                action="calculate",
            )
        )
        queued_at = utcnow()
        record = TaskRecord(
            task_id=task_id,
            type=TaskType.EXPORT.value,
            action="export",
            resource="result",
            status=TaskStatus.FAILED.value,
            progress=75.0,
            priority=1,
            input={"format": "csv"},
            result={"rows": 0},
            error_code=ErrorCode.TASK_TIMEOUT.value,
            error_message="boom",
            retry_count=2,
            max_retries=4,
            request_id=REQUEST_ID,
            parent_task_id=parent_id,
            queued_at=queued_at,
            started_at=queued_at,
            finished_at=queued_at,
        )
        await any_store.save_task(record)

        loaded = await any_store.load_task(task_id)
        assert loaded is not None
        for field in (
            "task_id",
            "type",
            "action",
            "resource",
            "status",
            "progress",
            "priority",
            "input",
            "result",
            "error_code",
            "error_message",
            "retry_count",
            "max_retries",
            "request_id",
            "parent_task_id",
        ):
            assert getattr(loaded, field) == getattr(record, field), field
        assert loaded.queued_at == queued_at
        assert loaded.started_at == queued_at
        assert loaded.finished_at == queued_at

        # Engine-side fields are deliberately *not* persisted (see the store
        # docstring): a reloaded record has no runner and falls back to defaults.
        assert loaded.runner is None
        assert loaded.timeout_seconds > 0

    run(scenario())


def test_foreign_key_columns_map_field_by_field(sqlite_path: Path) -> None:
    """``tool_name`` / ``adapter_code`` / ``midas_client_id`` (总纲 §4.1.6).

    These are real foreign keys (``tools(name)``, ``adapters(code)``,
    ``midas_clients(id)``) and ``PRAGMA foreign_keys=ON`` is live, so the
    referenced rows have to exist before the task row can.
    """
    factory = session_factory_for(sqlite_path)
    with factory() as session:
        session.add(
            Adapter(
                code="midas_gen",
                name="MIDAS Gen Adapter",
                software="MIDAS Gen",
                implementation="app.adapters.midas_gen.adapter",
            )
        )
        session.add(
            Tool(
                name="midas_execute",
                display_name="MIDAS Execute",
                input_schema_json="{}",
            )
        )
        session.flush()
        session.add(
            MidasClient(
                name="dept-a",
                software="MIDAS Gen NX",
                adapter_code="midas_gen",
                api_url="https://relay.example/gen",
            )
        )
        session.commit()

    store = SqlAlchemyTaskStore(factory)

    async def scenario() -> None:
        task_id = "task_20260925_000008"
        await store.save_task(
            TaskRecord(
                task_id=task_id,
                type=TaskType.CALCULATE.value,
                action="calculate",
                resource="model",
                tool_name="midas_execute",
                adapter_code="midas_gen",
                midas_client_id=1,
            )
        )
        loaded = await store.load_task(task_id)
        assert loaded is not None
        assert loaded.tool_name == "midas_execute"
        assert loaded.adapter_code == "midas_gen"
        assert loaded.midas_client_id == 1

    run(scenario())


# ---------------------------------------------------------------------------
# 4. round-trip across a restart
# ---------------------------------------------------------------------------
def _new_service(sqlite_path: Path) -> TaskService:
    """A brand-new service on the same file — i.e. a restarted process."""
    return TaskService(store=SqlAlchemyTaskStore(session_factory_for(sqlite_path)))


async def _ok_runner() -> AdapterResult:
    return AdapterResult.ok({"节点": [1, 2], "unit": "kN·m"})


def test_tasks_survive_a_restart(sqlite_path: Path) -> None:
    """The headline claim: a new process still answers get / list / events / result."""
    parent_payload: dict[str, Any] = {
        "nested": {"levels": [1, 2, {"三": "级"}]},
        "unicode": "弯矩 kN·m",
        "empty": None,
    }

    async def first_process() -> dict[str, str]:
        service = _new_service(sqlite_path)
        parent = await service.create(
            type=TaskType.REPORT.value,
            action="generate_report",
            resource="report",
            request_id=REQUEST_ID,
            priority=2,
            payload=parent_payload,
        )
        child = await service.create(
            type=TaskType.CALCULATE.value,
            action="calculate",
            request_id="req_20260925_000043",
            parent_task_id=parent,
            payload=[1, 2.5, True, None, {"k": ["v"]}],
        )
        done = await service.create(
            type=TaskType.CALCULATE.value,
            action="calculate",
            request_id="req_20260925_000044",
            runner=_ok_runner,
        )
        await service.drain()
        return {"parent": parent, "child": child, "done": done}

    ids = run(first_process())

    async def second_process() -> None:
        service = _new_service(sqlite_path)

        parent = await service.get(ids["parent"], include_result=True)
        assert parent["task_id"] == ids["parent"]
        assert parent["status"] == TaskStatus.QUEUED.value
        assert parent["request_id"] == REQUEST_ID
        assert parent["type"] == TaskType.REPORT.value
        assert parent["resource"] == "report"
        assert parent["priority"] == 2

        child = await service.get(ids["child"])
        assert child["task_id"] == ids["child"]
        assert child["parent_task_id"] == ids["parent"]
        assert child["request_id"] == "req_20260925_000043"

        listed = await service.list()
        assert {row["task_id"] for row in listed["items"]} == set(ids.values())
        assert listed["total"] == 3

        events = await service.events(ids["done"])
        assert [row["event_type"] for row in events["items"]] == [
            "queued",
            "started",
            "finished",
        ]
        assert events["task_id"] == ids["done"]
        assert events["status"] == TaskStatus.SUCCESS.value

        final = await service.result(ids["done"])
        assert final["task_id"] == ids["done"]
        assert final["status"] == TaskStatus.SUCCESS.value
        assert final["ready"] is True
        assert final["error_code"] is None
        assert final["result"] is not None
        assert final["result"]["success"] is True
        assert final["result"]["data"] == {"节点": [1, 2], "unit": "kN·m"}
        assert final["finished_at"] is not None

        # A queued task is not terminal, so its result is still withheld (§10.3).
        pending = await service.result(ids["parent"])
        assert pending["ready"] is False
        assert pending["result"] is None

    run(second_process())


def test_the_since_cursor_still_works_after_a_restart(sqlite_path: Path) -> None:
    """V2.1 §10.3 — the incremental poll cursor is durable, in both forms."""

    async def first_process() -> str:
        service = _new_service(sqlite_path)
        task_id = await service.create(
            type=TaskType.CALCULATE.value, action="calculate"
        )
        service.emit_log(task_id, "logged in the first process")
        return task_id

    task_id = run(first_process())

    async def poll() -> dict[str, Any]:
        service = _new_service(sqlite_path)
        return await service.events(task_id)

    page = run(poll())
    assert [row["event_type"] for row in page["items"]] == ["queued", "log"]
    assert page["cursor"]

    async def poll_since_iso() -> dict[str, Any]:
        service = _new_service(sqlite_path)
        return await service.events(task_id, since=page["cursor"])

    after = run(poll_since_iso())
    assert after["items"] == []
    assert after["cursor"] == page["cursor"], "the cursor is echoed back unchanged"

    async def poll_since_id() -> dict[str, Any]:
        service = _new_service(sqlite_path)
        first_id = int(page["items"][0]["id"])
        return await service.events(task_id, since=str(first_id))

    tail = run(poll_since_id())
    assert [row["event_type"] for row in tail["items"]] == ["log"]


# ---------------------------------------------------------------------------
# 5. restart reconciliation
# ---------------------------------------------------------------------------
def _seed_statuses(sqlite_path: Path) -> dict[str, str]:
    """Write one row per closed status directly through the store."""
    store = SqlAlchemyTaskStore(session_factory_for(sqlite_path))
    ids: dict[str, str] = {}
    for index, status in enumerate(sorted(CLOSED_STATUSES), start=1):
        task_id = f"task_20260925_{index:06d}"
        ids[status] = task_id
        run(
            store.save_task(
                TaskRecord(
                    task_id=task_id,
                    type=TaskType.CALCULATE.value,
                    action="calculate",
                    status=status,
                )
            )
        )
    return ids


def test_recover_orphans_fails_orphans_and_spares_terminal_rows(
    sqlite_path: Path,
) -> None:
    """V2.1 §26.1 — a restart leaves no runner, so nothing may stay ``running``."""
    ids = _seed_statuses(sqlite_path)
    service = _new_service(sqlite_path)

    recovered = run(service.recover_orphans())
    assert sorted(recovered) == sorted(ids[status] for status in ORPHAN_STATUSES)

    async def inspect() -> None:
        for status in ORPHAN_STATUSES:
            snapshot = await service.get(ids[status], include_result=True)
            assert snapshot["status"] == TaskStatus.FAILED.value, status
            assert snapshot["error_code"] == ErrorCode.INTERNAL_ERROR.value
            assert snapshot["finished_at"] is not None
            assert "进程重启" in snapshot["error_message"]

            events = await service.events(ids[status])
            assert events["items"][-1]["event_type"] == "failed"
            payload = events["items"][-1]["payload"]
            assert payload["error_code"] == ErrorCode.INTERNAL_ERROR.value
            assert payload["recovered"] is True
            assert payload["previous_status"] == status

        for status in TERMINAL_STATUSES:
            snapshot = await service.get(ids[status], include_result=True)
            assert snapshot["status"] == status, status
            assert snapshot["error_code"] is None, "a terminal row is left alone"
            events = await service.events(ids[status])
            assert [row["event_type"] for row in events["items"]] == []

    run(inspect())

    # Running it a second time is a no-op: the orphans are terminal now.
    assert run(service.recover_orphans()) == []


def test_recover_orphans_keeps_the_trace_chain_and_does_not_retry(
    sqlite_path: Path,
) -> None:
    """Recovery fails the task; it never re-queues it (V2.1 §26.5)."""
    factory = session_factory_for(sqlite_path)
    store = SqlAlchemyTaskStore(factory)
    task_id = "task_20260925_000100"
    run(
        store.save_task(
            TaskRecord(
                task_id=task_id,
                type=TaskType.CALCULATE.value,
                action="calculate",
                status=TaskStatus.RUNNING.value,
                request_id=REQUEST_ID,
                retry_count=0,
                max_retries=3,
            )
        )
    )

    service = _new_service(sqlite_path)

    async def scenario() -> None:
        assert await service.recover_orphans() == [task_id]
        snapshot = await service.get(task_id)
        assert snapshot["status"] == TaskStatus.FAILED.value
        assert snapshot["request_id"] == REQUEST_ID
        assert snapshot["retry_count"] == 0, "recovery is not a retry"
        assert snapshot["status"] not in ORPHAN_STATUSES

    run(scenario())


def test_init_task_service_is_the_documented_startup_hook(sqlite_path: Path) -> None:
    """``init_task_service`` publishes the singleton *and* reconciles orphans."""
    store = SqlAlchemyTaskStore(session_factory_for(sqlite_path))
    task_id = "task_20260925_000101"
    run(
        store.save_task(
            TaskRecord(
                task_id=task_id,
                type=TaskType.CALCULATE.value,
                action="calculate",
                status=TaskStatus.RUNNING.value,
            )
        )
    )

    async def boot() -> tuple[TaskService, dict[str, Any]]:
        service = await init_task_service(_new_service(sqlite_path))
        return service, await service.get(task_id)

    try:
        service, snapshot = run(boot())
        assert get_task_service() is service
        assert snapshot["status"] == TaskStatus.FAILED.value
        assert snapshot["error_code"] == ErrorCode.INTERNAL_ERROR.value
    finally:
        # Do not leak the singleton into the other tests.
        reset_task_service()
