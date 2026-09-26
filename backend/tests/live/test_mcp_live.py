"""Live end-to-end MCP-layer test against a running MIDAS Gen/Civil NX instance.

**Skipped by default**, with the same gate as ``tests/live/test_adapter_live.py``:

```powershell
$env:STRUCTAI_LIVE_MIDAS_URL = "http://localhost:3030"
$env:STRUCTAI_LIVE_MAPI_KEY = "<key>"
$env:STRUCTAI_LIVE_PRODUCT  = "gen"          # or "civil"
..\\.venv\\Scripts\\python.exe -m pytest tests/live -q
```

What it proves that the offline suite cannot:

* the **whole v1.2 §38 chain** works against the real product — MCP request ->
  validation -> Capability Resolver -> Adapter Registry -> Interface mapping ->
  Adapter -> MIDAS -> 总纲 §4.3.2 envelope;
* ``midas_model action=delete`` really issues ``DELETE {endpoint}/{id}`` and
  leaves the neighbouring record alive (对接规范 §3.5 第 1 条 / §11.5.1: the
  ``Assign``-body form wipes the table);
* ``midas_query target=node action=get`` really reads back what was written
  (对接规范 §11.5.5: the read-back shape differs from the write shape, so only
  key fields are compared);
* ``midas_execute`` really queues a ``task_``-prefixed task that the platform
  Task Engine then runs (V2.1 §9.4 / §26).

**It writes to the open document.** It deletes ``/db/NODE`` keys 1–2 first. Only
point it at a disposable model.
"""

import asyncio
import os

import pytest

from app.adapters.midas_gen.adapter import MidasNxAdapter
from app.adapters.registry import AdapterRegistry
from app.core.constants import TaskStatus
from app.core.errors import ErrorCode
from app.core.ids import is_valid_id
from app.core.midas_config import MidasConnection, MidasProduct
from app.mcp.capabilities import TOOL_EXECUTE, TOOL_MODEL, TOOL_QUERY, TOOL_TASK
from app.mcp.dispatcher import ToolDispatcher
from app.services.task_service import TaskService

_LIVE_URL = os.environ.get("STRUCTAI_LIVE_MIDAS_URL")
_LIVE_KEY = os.environ.get("STRUCTAI_LIVE_MAPI_KEY")
_LIVE_PRODUCT = os.environ.get("STRUCTAI_LIVE_PRODUCT", "gen")

pytestmark = pytest.mark.skipif(
    not (_LIVE_URL and _LIVE_KEY),
    reason=(
        "live MIDAS test — set STRUCTAI_LIVE_MIDAS_URL and STRUCTAI_LIVE_MAPI_KEY "
        "to enable (it writes to the open document)"
    ),
)

_TERMINAL = {
    TaskStatus.SUCCESS.value,
    TaskStatus.FAILED.value,
    TaskStatus.CANCELLED.value,
}


def _connection() -> MidasConnection:
    return MidasConnection(
        name="live-mcp",
        software="MIDAS Gen NX" if _LIVE_PRODUCT == "gen" else "MIDAS Civil NX",
        product=MidasProduct(_LIVE_PRODUCT),
        base_url=_LIVE_URL,
        mapi_key=_LIVE_KEY,
        timeout_seconds=120,
        verify_tls=False,
    )


def _stack() -> tuple[MidasNxAdapter, ToolDispatcher, TaskService]:
    """One adapter + registry + task engine + dispatcher, inside the live loop.

    Built per test because :class:`MidasNxAdapter` binds its ``asyncio.Lock`` to
    the loop it first awaits in (对接规范 §2.5.2: one in-flight request per
    instance).
    """
    adapter = MidasNxAdapter(_connection())
    registry = AdapterRegistry()
    registry.register(adapter)
    tasks = TaskService()
    dispatcher = ToolDispatcher(registry=registry, task_service=tasks)
    return adapter, dispatcher, tasks


def _run(coro):
    return asyncio.run(coro)


def test_live_capabilities_and_introspection() -> None:
    """``target=capabilities`` is ours; ``action=inspect`` is 对接规范 §5."""

    async def body() -> None:
        adapter, dispatcher, _tasks = _stack()
        try:
            caps = await dispatcher.dispatch(
                TOOL_QUERY, {"target": "capabilities", "action": "list"}
            )
            assert caps["success"], caps
            assert caps["data"]["total"] > 0
            # The capability list is the platform's own table (V2.1 §16.1): it must
            # answer even when MIDAS is unreachable, so nothing is asserted about
            # the upstream here beyond the introspection call below.

            inspect = await dispatcher.dispatch(
                TOOL_QUERY, {"target": "node", "action": "inspect"}
            )
            assert inspect["success"], inspect
            # 对接规范 §5.0.1: the schema is wrapped under Argument, never NODE.
            assert set(inspect["data"]["properties"]) == {"X", "Y", "Z"}

            health = await dispatcher.dispatch(TOOL_EXECUTE, {"action": "connect"})
            assert health["success"], health
            assert health["data"]["keyVerified"] is True
        finally:
            await adapter.aclose()

    _run(body())


def test_live_node_create_read_delete_round_trip() -> None:
    """The round trip the brief asks for, through the MCP layer only."""

    async def body() -> None:
        adapter, dispatcher, _tasks = _stack()
        try:
            # 对接规范 §3.5 第 1 条: per-id deletes only.
            for one in ("1", "2"):
                await adapter.delete("NODE", [one])

            created = await dispatcher.dispatch(
                TOOL_MODEL,
                {
                    "action": "create",
                    "resource": "node",
                    "data": {
                        "1": {"X": 0.0, "Y": 0.0, "Z": 3.6},
                        "2": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                    },
                },
            )
            assert created["success"], created
            assert created["tool"] == TOOL_MODEL

            read = await dispatcher.dispatch(
                TOOL_QUERY, {"target": "node", "action": "get", "id": 1}
            )
            assert read["success"], read
            item = read["data"]["item"]
            assert str(item["id"]) == "1"
            # 对接规范 §11.5.5: compare key fields, never the whole payload.
            assert float(item["Z"]) == pytest.approx(3.6)
            assert read["data"]["resource"] == "node"  # 总纲 §4.6.1 单数名

            upserted = await dispatcher.dispatch(
                TOOL_MODEL,
                {
                    "action": "upsert",
                    "resource": "node",
                    "data": {"1": {"X": 1.5, "Y": 0.0, "Z": 3.6}},
                },
            )
            assert upserted["success"], upserted

            again = await dispatcher.dispatch(
                TOOL_QUERY, {"target": "node", "action": "get", "id": 1}
            )
            assert again["success"], again
            assert float(again["data"]["item"]["X"]) == pytest.approx(1.5)

            # dry-run validate: no HTTP call at all.
            validated = await dispatcher.dispatch(
                TOOL_MODEL,
                {
                    "action": "validate",
                    "resource": "node",
                    "data": {"2": {"X": 0.0, "Y": 0.0, "Z": 0.0}},
                },
            )
            assert validated["success"], validated
            assert validated["data"]["body"]["Assign"]["2"]["Z"] == 0.0

            deleted = await dispatcher.dispatch(
                TOOL_MODEL, {"action": "delete", "resource": "node", "ids": ["1"]}
            )
            assert deleted["success"], deleted
            assert deleted["data"]["mode"] == "per_id"
            assert deleted["data"]["deleted"] == ["1"]
            # 对接规范 §11.5.1: node 2 was never touched by that call.
            survived = await dispatcher.dispatch(
                TOOL_QUERY, {"target": "node", "action": "get", "id": 2}
            )
            assert survived["success"], survived
            assert str(survived["data"]["item"]["id"]) == "2"

            gone = await dispatcher.dispatch(
                TOOL_QUERY, {"target": "node", "action": "get", "id": 1}
            )
            assert gone["success"] is False
            assert gone["errors"][0]["code"] == ErrorCode.RESOURCE_NOT_FOUND.value

            # The Assign-body form is refused before any HTTP call
            # (对接规范 §3.5 第 1 条 / §11.5.1: it would wipe the whole table).
            refused = await dispatcher.dispatch(
                TOOL_MODEL,
                {
                    "action": "delete",
                    "resource": "node",
                    "data": {"Assign": {"2": None}},
                },
            )
            assert refused["success"] is False
            assert refused["errors"][0]["code"] == ErrorCode.VALIDATION_ERROR.value
            assert "清空整张表" in refused["errors"][0]["message"]

            for one in ("1", "2"):
                await adapter.delete("NODE", [one])
        finally:
            await adapter.aclose()

    _run(body())


def test_live_execute_queues_a_task_and_sync_reads_the_model_back() -> None:
    """V2.1 §9.4 (async by default) + 对接规范 §3.5 第 5 条 (read back)."""

    async def body() -> None:
        adapter, dispatcher, tasks = _stack()
        try:
            queued = await dispatcher.dispatch(TOOL_EXECUTE, {"action": "calculate"})
            assert queued["success"], queued
            assert queued["status"] == TaskStatus.QUEUED.value
            assert queued["data"] is None
            task_id = queued["task_id"]
            # 总纲 §4.1.4: one task_ prefix, sub-type lives in tasks.type.
            assert task_id and task_id.startswith("task_")
            assert is_valid_id(task_id, "task")

            await tasks.drain()

            snapshot = await dispatcher.dispatch(
                TOOL_TASK, {"action": "get", "task_id": task_id}
            )
            assert snapshot["success"], snapshot
            status = snapshot["data"]["status"]
            assert status in _TERMINAL, snapshot
            if status == TaskStatus.FAILED.value:
                # A model without boundary conditions makes /doc/ANAL answer
                # 400 [错误] 边界条件 没有定义。(对接规范 §11.5.8) — the code must
                # still come from the 总纲 §4.4 closed set.
                assert snapshot["data"]["error_code"] in {
                    ErrorCode.VALIDATION_ERROR.value,
                    ErrorCode.MIDAS_API_ERROR.value,
                    ErrorCode.MIDAS_CALCULATION_ERROR.value,
                    ErrorCode.TASK_TIMEOUT.value,
                }, snapshot

            events = await dispatcher.dispatch(
                TOOL_TASK, {"action": "events", "task_id": task_id}
            )
            assert events["success"], events
            kinds = [event["event_type"] for event in events["data"]["items"]]
            assert kinds[0] == "queued"
            assert "started" in kinds
            assert kinds[-1] in {"finished", "failed", "cancelled"}
            assert events["data"]["cursor"]

            result = await dispatcher.dispatch(
                TOOL_TASK, {"action": "result", "task_id": task_id}
            )
            assert result["success"], result
            assert result["data"]["ready"] is True

            # 对接规范 §3.5 第 5 条: the only safe step after a write is to read
            # the model state back — read-only, so it is always safe to run here.
            synced = await dispatcher.dispatch(TOOL_EXECUTE, {"action": "sync"})
            assert synced["success"], synced
            assert synced["data"]["resource"] == "model"
            assert "node" in synced["data"]["counts"]
        finally:
            await adapter.aclose()

    _run(body())
