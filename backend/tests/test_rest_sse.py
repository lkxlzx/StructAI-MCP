"""Offline REST + SSE layer tests — 总纲 §4.3.1 / §4.4 / §4.8.2, v1.2 §3.2/§3.3,
§5, §20, §21, §22.3, §34–§36, §51.

Plain ``pytest`` only, no network and no live MIDAS: every test runs against a
real SQLite file in ``tmp_path`` (the same convention as
``tests/test_auth_rbac.py`` and ``tests/test_task_persistence.py``) with the
**mock** adapter registered, and the async scenarios are driven with
``asyncio.run`` so the suite needs no ``pytest-asyncio`` configuration.

What is proven, and against which rule:

====================================================================  ==================================
claim                                                                 依据
====================================================================  ==================================
success **and** failure carry the same six envelope keys               总纲 §4.3.1 / v1.2 §3.2
business data lives in ``data``; no top-level bare field               总纲 §4.3.1
a minted ``request_id`` is a valid ``req_`` id                         总纲 §4.1.2 / §4.1.3
an inbound ``X-Request-ID`` is echoed                                  总纲 §4.3.1
``AdapterError`` -> its closed code + the §4.4 HTTP status             总纲 §4.4
an unexpected exception -> ``INTERNAL_ERROR``, traceback not returned  总纲 §4.4.9
``/health`` uses the envelope; ``/health/ready`` / ``/health/live`` do not  v1.2 §34 / §35 / §36
login -> token -> ``/auth/me``; bad token refused; logout revokes       v1.2 §5.1–§5.3, 总纲 §4.4.1
an unauthenticated task stream is refused                              v1.2 §21 + §5.1
an SSE stream replays the task's events and follows live ones          v1.2 §21
``Last-Event-ID`` / ``?since=`` resume without replaying                v1.2 §21 + V2.1 §10.3
a client disconnect releases the bus subscription                      v1.2 §21
the log stream receives global events                                  v1.2 §22.3
the slow-subscriber policy is bounded and reported                     app.services.event_bus
a closed subscription does not disturb its siblings                    app.services.event_bus
pagination is ``data.items`` + ``data.pagination``                     v1.2 §51
the list is ownership-filtered **in the query**, total included        v1.2 §20.1 + §21
``super_admin`` sees every task; unattributed tasks stay visible       总纲 §4.8.3 / 裁决 C-13
refresh rotates the row, hashes the token, follows the policy TTL      v1.2 §5.4 + 裁决 C-9
a flood gets 429 + ``RATE_LIMITED`` + ``Retry-After``                 总纲 §4.4.2 / §8.6
``X-RateLimit-*`` on success too; probes never limited                 总纲 §4.4.2
``X-Forwarded-For`` cannot mint a bucket by default                    总纲 §8.6
an SSE stream is charged once, at connect                              v1.2 §21 + §8.6
====================================================================  ==================================
"""

import asyncio
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  (registers all 49 tables on Base.metadata)
from app.adapters.errors import AdapterError
from app.adapters.registry import AdapterRegistry
from app.core import crypto
from app.core.config import get_settings
from app.core.constants import PERMISSION_CODES, UserStatus
from app.core.errors import ErrorCode, http_status_for
from app.core.ids import is_valid_id
from app.core.rate_limit import RateLimitLimiter
from app.db.base import session_scope_for
from app.main import (
    ENVELOPE_EXEMPT_PATHS,
    ENVELOPE_FIELDS,
    RATE_LIMIT_EXEMPT_PATHS,
    TASK_READ_PERMISSION,
    RateLimitMiddleware,
    create_app,
)
from app.mcp.server import register_mock_adapter
from app.models.identity import Role, User, UserRole, UserSession
from app.models.settings import SecurityConfig
from app.services.auth_service import (
    AuthService,
    Principal,
    decode_token,
    hash_password,
    seed_rbac,
)
from app.services.event_bus import EventBus, task_topic
from app.services.task_service import TaskRecord, TaskService, reset_task_service

#: ``STRUCTAI_MASTER_KEY`` is unset in CI and :func:`signing_key` must fail loudly
#: in that case (asserted in ``tests/test_auth_rbac.py``), so the fixture supplies
#: one explicitly.  Nothing here ever logs it.
MASTER_KEY = "unit-test-master-key-please-change-0123456789"

#: A password that satisfies every documented complexity level.
PASSWORD = "Adm1n-Passw0rd!"

#: 总纲 §4.1.2 — ``<prefix>_<yyyymmdd>_<6 digits>``.
REQUEST_ID_RE = re.compile(r"^req_\d{8}_\d{6}$")

#: An ``X-Request-ID`` the caller chose, echoed verbatim (总纲 §4.3.1).
INBOUND_REQUEST_ID = "req_20260925_000001"


def run(coro: Any) -> Any:
    """Drive one coroutine to completion (no pytest-asyncio dependency)."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# database fixtures — a real SQLite file, per test
# ---------------------------------------------------------------------------
def _enable_foreign_keys(dbapi_connection: Any, connection_record: Any) -> None:  # noqa: ANN001
    """``PRAGMA foreign_keys=ON`` — mandatory, mirrors :mod:`app.db.session`."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


@pytest.fixture(autouse=True)
def master_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide ``STRUCTAI_MASTER_KEY`` for the JWT key derivation (总纲 §4.7.1)."""
    monkeypatch.setenv("STRUCTAI_MASTER_KEY", MASTER_KEY)
    monkeypatch.setattr(get_settings(), "structai_master_key", MASTER_KEY)


@pytest.fixture(autouse=True)
def restore_task_singleton() -> Iterator[None]:
    """Put the process-wide Task Engine singleton back after every test.

    ``create_app``'s lifespan calls ``init_task_service`` (V2.1 §26.1's documented
    bootstrap hook), which publishes the app's service process-wide.  Leaving it
    behind would leak a service bound to a deleted ``tmp_path`` database into the
    other suites.
    """
    yield
    reset_task_service()


@pytest.fixture()
def db_path(tmp_path: Path, schema_template: Path) -> Path:
    """A pristine copy of the empty 49-table schema, per test."""
    target = tmp_path / "structai_rest.db"
    shutil.copyfile(schema_template, target)
    return target


@pytest.fixture()
def factory(db_path: Path) -> Callable[[], Session]:
    """A sync ``sessionmaker`` over this test's own database copy."""
    engine: Engine = create_engine(
        f"sqlite:///{db_path}",
        future=True,
        # ``asyncio.to_thread`` may hand a pooled connection to a different worker
        # thread than the one that opened it — the reason ``app.db.session`` sets
        # this too.
        connect_args={"check_same_thread": False},
    )
    event.listen(engine, "connect", _enable_foreign_keys)
    return sessionmaker(
        bind=engine, class_=Session, autoflush=False, expire_on_commit=False
    )


@pytest.fixture()
def seeded(factory: Callable[[], Session]) -> Callable[[], Session]:
    """The test database with the RBAC seed applied (总纲 §4.8.2 / §4.8.3)."""
    seed_rbac(factory)
    return factory


def add_user(
    factory: Callable[[], Session],
    username: str,
    *,
    password: str = PASSWORD,
    roles: Tuple[str, ...] = ("visitor",),
    status: str = UserStatus.ENABLED.value,
) -> int:
    """Insert one ``users`` row plus its ``user_roles`` links; return its id."""
    with session_scope_for(factory) as session:
        user = User(
            username=username,
            name=f"{username} (display)",
            password_hash=hash_password(password),
            status=status,
            is_online=0,
        )
        session.add(user)
        session.flush()
        for code in roles:
            role = session.scalar(select(Role).where(Role.code == code))
            assert role is not None, f"role {code!r} is not seeded"
            session.add(UserRole(user_id=int(user.id), role_id=int(role.id)))
        return int(user.id)


def set_policy(factory: Callable[[], Session], **values: Any) -> None:
    """Write the ``security_configs`` singleton (裁决 B-7 / C-9 / C-13)."""
    with session_scope_for(factory) as session:
        row = session.get(SecurityConfig, 1)
        if row is None:
            row = SecurityConfig(id=1)
            session.add(row)
        for key, value in values.items():
            setattr(row, key, value)


class FakeClock:
    """A monotonic clock the rate limiter is injected with — never ``sleep``.

    The same shape :class:`AuthService` takes: the limiter asks the clock, so a
    test can advance an hour of refill in one call.
    """

    def __init__(self, start: float = 1_000.0) -> None:
        self.moment: float = float(start)

    def __call__(self) -> float:
        return self.moment

    def advance(self, seconds: float) -> float:
        self.moment += float(seconds)
        return self.moment


# ---------------------------------------------------------------------------
# app fixtures
# ---------------------------------------------------------------------------
def make_app(
    factory: Callable[[], Session],
    *,
    bus: Optional[EventBus] = None,
    tasks: Optional[TaskService] = None,
    auth: Optional[AuthService] = None,
    rate_limiter: Optional[RateLimitLimiter] = None,
) -> Tuple[FastAPI, EventBus, TaskService]:
    """Build the REST app with every collaborator injected (no discovery)."""
    resolved_bus = bus if bus is not None else EventBus()
    resolved_tasks = tasks if tasks is not None else TaskService(event_bus=resolved_bus)
    resolved_auth = auth if auth is not None else AuthService(session_factory=factory)
    registry = AdapterRegistry()
    # The offline suite's adapter (V2.1 §22): answers fabricated data, never a
    # network call.  A private registry keeps ``get_registry()`` untouched.
    register_mock_adapter(registry)
    application = create_app(
        task_service=resolved_tasks,
        auth_service=resolved_auth,
        event_bus=resolved_bus,
        session_factory=factory,
        registry=registry,
        register_adapters=False,
        rate_limiter=rate_limiter,
    )
    return application, resolved_bus, resolved_tasks


@pytest.fixture()
def bus() -> EventBus:
    """The application's publish bus (v1.2 §21 / §22.3)."""
    return EventBus()


@pytest.fixture()
def tasks(bus: EventBus) -> TaskService:
    """The Task Engine, wired to the bus — the optional hook under test."""
    return TaskService(event_bus=bus)


@pytest.fixture()
def application(
    factory: Callable[[], Session], seeded: Callable[[], Session], bus: EventBus, tasks: TaskService
) -> FastAPI:
    """The app under test, with the lifespan **not** entered yet."""
    app, _bus, _tasks = make_app(factory, bus=bus, tasks=tasks)
    return app


@pytest.fixture()
def client(application: FastAPI) -> Iterator[TestClient]:
    """``TestClient`` with the lifespan entered (bootstrap runs for real)."""
    with TestClient(application) as test_client:
        yield test_client


@pytest.fixture()
def users(seeded: Callable[[], Session]) -> Dict[str, int]:
    """Two users: ``alice`` holds ``task:read`` (visitor), ``bob`` too."""
    return {
        "alice": add_user(seeded, "alice", roles=("visitor",)),
        "bob": add_user(seeded, "bob", roles=("visitor",)),
    }


@pytest.fixture()
def admin(seeded: Callable[[], Session]) -> int:
    """A ``super_admin`` (总纲 §4.8.3) — the one role that bypasses the data scope."""
    return add_user(seeded, "root", roles=("super_admin",))


# ---------------------------------------------------------------------------
# envelope assertions (总纲 §4.3.1)
# ---------------------------------------------------------------------------
def assert_envelope(payload: Any) -> Dict[str, Any]:
    """Assert the six mandatory §4.3.1 keys and return the envelope."""
    assert isinstance(payload, dict), f"envelope must be a JSON object, got {type(payload)}"
    for field in ENVELOPE_FIELDS:
        assert field in payload, f"envelope is missing {field!r}: {sorted(payload)}"
    assert isinstance(payload["success"], bool)
    assert isinstance(payload["code"], str) and payload["code"]
    assert isinstance(payload["message"], str)
    assert isinstance(payload["request_id"], str)
    assert isinstance(payload["timestamp"], str)
    # 总纲 §4.5.1 — ISO 8601 with an offset, never a naive local clock.
    assert "T" in payload["timestamp"]
    return payload


def assert_no_bare_top_level(payload: Dict[str, Any]) -> None:
    """总纲 §4.3.1 「业务数据一律放在 data 中，禁止顶层裸字段」."""
    allowed = set(ENVELOPE_FIELDS) | {"details"}
    assert set(payload) <= allowed, f"top-level bare field(s): {sorted(set(payload) - allowed)}"


# ---------------------------------------------------------------------------
# 1. the envelope
# ---------------------------------------------------------------------------
def test_success_envelope_carries_every_key_and_the_payload(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200, response.text
    envelope = assert_envelope(response.json())
    assert_no_bare_top_level(envelope)
    assert envelope["success"] is True
    assert envelope["code"] == ErrorCode.OK.value
    # v1.2 §34 — the aggregate check's payload is inside ``data``.
    assert isinstance(envelope["data"], dict)
    assert set(envelope["data"]) >= {"status", "database", "mcp_server", "adapter", "disk"}


def test_failure_envelope_carries_every_key(client: TestClient) -> None:
    response = client.get("/api/v1/tasks/does-not-exist")
    assert response.status_code == 401, response.text
    envelope = assert_envelope(response.json())
    assert_no_bare_top_level(envelope)
    assert envelope["success"] is False
    assert envelope["code"] == ErrorCode.AUTH_REQUIRED.value
    assert envelope["data"] is None


def test_unknown_route_is_enveloped(client: TestClient) -> None:
    """A framework-generated 404 still has to carry the envelope."""
    response = client.get("/api/v1/no-such-endpoint")
    assert response.status_code == 404
    envelope = assert_envelope(response.json())
    assert envelope["success"] is False
    assert envelope["code"] == ErrorCode.RESOURCE_NOT_FOUND.value


def test_request_validation_failure_is_enveloped(client: TestClient) -> None:
    """A pydantic/FastAPI 422 becomes ``VALIDATION_ERROR`` (总纲 §4.4.2)."""
    response = client.get("/api/v1/tasks?page=0")
    assert response.status_code == 422
    envelope = assert_envelope(response.json())
    assert envelope["code"] == ErrorCode.VALIDATION_ERROR.value


def test_request_id_is_minted_and_well_formed(client: TestClient) -> None:
    """总纲 §4.1.2 / §4.1.3 — ``req_<yyyymmdd>_<6 digits>``."""
    first = assert_envelope(client.get("/api/v1/health").json())["request_id"]
    second = assert_envelope(client.get("/api/v1/health").json())["request_id"]
    assert REQUEST_ID_RE.match(first), first
    assert is_valid_id(first, "req")
    assert first != second, "a minted request id must be unique per call"


def test_inbound_request_id_is_echoed(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": INBOUND_REQUEST_ID})
    envelope = assert_envelope(response.json())
    assert envelope["request_id"] == INBOUND_REQUEST_ID
    # …and it is echoed on the response headers too.
    assert response.headers["x-request-id"] == INBOUND_REQUEST_ID


def test_adapter_error_maps_to_its_closed_code_and_status(
    factory: Callable[[], Session], seeded: Callable[[], Session]
) -> None:
    """总纲 §4.4 — the code and the status both come from the registry."""
    application, _bus, _tasks = make_app(factory)

    async def explode() -> Dict[str, Any]:
        raise AdapterError(
            ErrorCode.CAPABILITY_NOT_SUPPORTED,
            "当前 MIDAS Adapter 不支持该操作",
            details={"adapter": "midas_gen", "resource": "node", "action": "create"},
        )

    application.add_api_route("/api/v1/_adapter_error", explode)
    with TestClient(application) as client:
        response = client.get("/api/v1/_adapter_error")

    assert response.status_code == http_status_for(ErrorCode.CAPABILITY_NOT_SUPPORTED) == 422
    envelope = assert_envelope(response.json())
    assert envelope["code"] == ErrorCode.CAPABILITY_NOT_SUPPORTED.value
    assert envelope["message"] == "当前 MIDAS Adapter 不支持该操作"
    assert envelope["data"] is None
    assert envelope["details"]["adapter"] == "midas_gen"


def test_unexpected_exception_becomes_internal_error_without_leaking(
    factory: Callable[[], Session], seeded: Callable[[], Session]
) -> None:
    """总纲 §4.4.9 — ``INTERNAL_ERROR``; the traceback is logged, not returned."""
    secret = "kaboom-secret-token-must-not-leak"
    application, _bus, _tasks = make_app(factory)

    async def explode() -> Dict[str, Any]:
        raise RuntimeError(secret)

    application.add_api_route("/api/v1/_boom", explode)
    with TestClient(application) as client:
        response = client.get("/api/v1/_boom")

    assert response.status_code == 500
    assert secret not in response.text
    assert "Traceback" not in response.text
    envelope = assert_envelope(response.json())
    assert envelope["code"] == ErrorCode.INTERNAL_ERROR.value
    assert envelope["data"] is None
    assert secret not in envelope["message"]


# ---------------------------------------------------------------------------
# 2. the four exceptions (总纲 §4.3.1 / v1.2 §3.3)
# ---------------------------------------------------------------------------
def test_health_probes_are_bare_and_aggregate_health_is_not(client: TestClient) -> None:
    ready = client.get("/api/v1/health/ready")
    live = client.get("/api/v1/health/live")
    aggregate = client.get("/api/v1/health")

    # Exception 3: bare status codes, no envelope.
    assert ready.status_code == 200
    assert live.status_code == 200
    assert not ready.headers["content-type"].startswith("application/json")
    assert not live.headers["content-type"].startswith("application/json")
    assert "success" not in ready.text and "success" not in live.text

    # §34 is explicitly NOT an exception.
    assert aggregate.headers["content-type"].startswith("application/json")
    assert assert_envelope(aggregate.json())["success"] is True


def test_openapi_paths_are_exempt_from_the_envelope(client: TestClient) -> None:
    """Exception 4 — framework-generated OpenAPI (v1.2 §59)."""
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    assert "success" not in schema.json()
    assert "openapi" in schema.json()
    assert "/openapi.json" in ENVELOPE_EXEMPT_PATHS


# ---------------------------------------------------------------------------
# 3. authentication (v1.2 §5)
# ---------------------------------------------------------------------------
def login(client: TestClient, username: str, password: str = PASSWORD) -> str:
    """``POST /api/v1/auth/login`` and return the bearer token (v1.2 §5.1)."""
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    envelope = assert_envelope(response.json())
    data = envelope["data"]
    assert data["token_type"] == "Bearer"
    # 总纲 裁决 C-9 — TTL is derived, never hard-coded.
    assert isinstance(data["expires_in"], int) and data["expires_in"] > 0
    assert set(data["user"]) == {"id", "username", "name", "roles"}
    return str(data["access_token"])


def test_login_then_me_then_logout(
    client: TestClient, users: Dict[str, int]
) -> None:
    token = login(client, "alice")
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    payload = assert_envelope(me.json())["data"]
    assert payload["id"] == users["alice"]
    assert payload["username"] == "alice"
    assert payload["name"] == "alice (display)"
    assert "visitor" in payload["roles"]
    # 总纲 §4.8.2 — every permission is a member of the closed set.
    assert payload["permissions"], "visitor holds task:read / model:read / tool:read / data:read"
    assert set(payload["permissions"]) <= set(PERMISSION_CODES)

    out = client.post("/api/v1/auth/logout", headers=headers)
    assert out.status_code == 200
    assert assert_envelope(out.json())["data"] == {"revoked": True}

    # The session row is revoked -> 总纲 §4.4.1 AUTH_INVALID (not AUTH_EXPIRED).
    after = client.get("/api/v1/auth/me", headers=headers)
    assert after.status_code == 401
    assert assert_envelope(after.json())["code"] == ErrorCode.AUTH_INVALID.value


def test_missing_and_bad_tokens_are_refused(client: TestClient) -> None:
    missing = client.get("/api/v1/auth/me")
    assert missing.status_code == 401
    assert assert_envelope(missing.json())["code"] == ErrorCode.AUTH_REQUIRED.value

    bad = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert bad.status_code == 401
    assert assert_envelope(bad.json())["code"] == ErrorCode.AUTH_INVALID.value


def test_refresh_rotates_the_session(
    client: TestClient, users: Dict[str, int]
) -> None:
    """v1.2 §5.4 — a new token, and the presented one is revoked."""
    token = login(client, "alice")
    refreshed = client.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {token}"})
    assert refreshed.status_code == 200, refreshed.text
    data = assert_envelope(refreshed.json())["data"]
    assert data["access_token"] != token
    assert data["expires_in"] > 0
    assert data["user"]["id"] == users["alice"]

    new_headers = {"Authorization": f"Bearer {data['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=new_headers)
    assert me.status_code == 200
    assert assert_envelope(me.json())["data"]["username"] == "alice"

    # The rotated-away token names a revoked ``sessions`` row.
    old = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert old.status_code == 401
    assert assert_envelope(old.json())["code"] == ErrorCode.AUTH_INVALID.value


def test_login_rejects_a_bad_password(client: TestClient, users: Dict[str, int]) -> None:
    response = client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert assert_envelope(response.json())["code"] == ErrorCode.AUTH_INVALID.value


def test_login_rejects_an_unknown_field(client: TestClient, users: Dict[str, int]) -> None:
    """``extra="forbid"`` — V2.1 §6.1's ``additionalProperties: false`` shape."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": PASSWORD, "is_admin": True},
    )
    assert response.status_code == 422
    assert assert_envelope(response.json())["code"] == ErrorCode.VALIDATION_ERROR.value


def test_task_read_permission_is_from_the_closed_set() -> None:
    """总纲 §4.8.2 — the stream's permission code is not invented."""
    assert TASK_READ_PERMISSION in PERMISSION_CODES


def test_tasks_list_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/tasks")
    assert response.status_code == 401
    assert assert_envelope(response.json())["code"] == ErrorCode.AUTH_REQUIRED.value


# ---------------------------------------------------------------------------
# 4. tasks list / detail (v1.2 §20)
# ---------------------------------------------------------------------------
def test_task_list_pagination_shape(
    client: TestClient, users: Dict[str, int], tasks: TaskService
) -> None:
    """v1.2 §51 — ``data.items`` + ``data.pagination``, never a bare ``items``."""
    token = login(client, "alice")
    headers = {"Authorization": f"Bearer {token}"}

    run(
        tasks.create(
            type="calculate",
            action="analysis",
            requested_by=users["alice"],
            runner=None,
            start=False,
        )
    )
    run(
        tasks.create(
            type="report",
            action="generate",
            requested_by=users["alice"],
            runner=None,
            start=False,
        )
    )

    response = client.get("/api/v1/tasks?page=1&page_size=1", headers=headers)
    assert response.status_code == 200, response.text
    data = assert_envelope(response.json())["data"]
    assert set(data) == {"items", "pagination"}
    assert len(data["items"]) == 1
    assert data["pagination"] == {
        "page": 1,
        "page_size": 1,
        "total": 2,
        "total_pages": 2,
    }

    filtered = client.get("/api/v1/tasks?type=report", headers=headers)
    rows = assert_envelope(filtered.json())["data"]["items"]
    assert [row["type"] for row in rows] == ["report"]

    # The post-filters of §20.1 that the Task Engine does not take.
    keyword = client.get("/api/v1/tasks?keyword=calculate", headers=headers)
    rows = assert_envelope(keyword.json())["data"]["items"]
    assert [row["type"] for row in rows] == ["calculate"]


def test_task_detail_and_not_found(
    client: TestClient, users: Dict[str, int], tasks: TaskService
) -> None:
    token = login(client, "alice")
    headers = {"Authorization": f"Bearer {token}"}
    task_id = run(
        tasks.create(
            type="calculate",
            action="analysis",
            requested_by=users["alice"],
            runner=None,
            start=False,
        )
    )

    response = client.get(f"/api/v1/tasks/{task_id}", headers=headers)
    assert response.status_code == 200
    data = assert_envelope(response.json())["data"]
    assert data["task_id"] == task_id
    assert data["status"] == "queued"

    missing = client.get("/api/v1/tasks/task_20260925_999999", headers=headers)
    assert missing.status_code == 404
    assert assert_envelope(missing.json())["code"] == ErrorCode.TASK_NOT_FOUND.value


# ---------------------------------------------------------------------------
# 5. SSE — an in-process ASGI driver
# ---------------------------------------------------------------------------
# ``starlette.testclient.TestClient`` cannot observe a stream: its transport does
# ``portal.call(self.app, scope, receive, send)`` and only then builds the
# response, and ``httpx.ASGITransport`` likewise ``await self.app(...)`` to
# completion.  Neither ever hands back a partial ``text/event-stream`` body, and
# an SSE response never completes.  Driving the ASGI callable directly is
# therefore the only way to assert on frames *as they arrive*, and it keeps the
# test fully in-process — no server, no socket, no thread.
class AsgiCall:
    """Minimal ASGI driver for one request, with incremental body capture."""

    def __init__(
        self,
        application: Any,
        path: str,
        *,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        query: bytes = b"",
        body: bytes = b"",
    ) -> None:
        self.application = application
        self.status: Optional[int] = None
        self.headers: List[Tuple[bytes, bytes]] = []
        self.chunks: List[bytes] = []
        self.complete = asyncio.Event()
        self._body = body
        self._body_sent = False
        self._disconnected = asyncio.Event()
        self._task: Optional[asyncio.Task[None]] = None
        self._condition = asyncio.Condition()
        raw_headers = [
            (key.lower().encode("latin-1"), value.encode("latin-1"))
            for key, value in (headers or {}).items()
        ]
        if body:
            raw_headers.append((b"content-length", str(len(body)).encode("ascii")))
        self._scope: Dict[str, Any] = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "path": path,
            "raw_path": path.encode("latin-1"),
            "query_string": query,
            "root_path": "",
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "headers": raw_headers,
            "state": {},
        }

    # -- ASGI callables ------------------------------------------------ #
    async def _receive(self) -> Dict[str, Any]:
        if not self._body_sent:
            self._body_sent = True
            return {"type": "http.request", "body": self._body, "more_body": False}
        await self._disconnected.wait()
        return {"type": "http.disconnect"}

    async def _send(self, message: Dict[str, Any]) -> None:
        kind = message["type"]
        if kind == "http.response.start":
            self.status = int(message["status"])
            self.headers = list(message.get("headers") or [])
        elif kind == "http.response.body":
            payload = bytes(message.get("body") or b"")
            if payload:
                self.chunks.append(payload)
            if not message.get("more_body", False):
                self.complete.set()
        async with self._condition:
            self._condition.notify_all()

    # -- lifecycle ----------------------------------------------------- #
    async def start(self) -> "AsgiCall":
        self._task = asyncio.ensure_future(
            self.application(self._scope, self._receive, self._send)
        )
        return self

    async def __aenter__(self) -> "AsgiCall":
        return await self.start()

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.aclose()

    async def wait_until(self, predicate: Callable[["AsgiCall"], bool], timeout: float = 5.0) -> bool:
        """Wait (no polling: the send callback notifies) until ``predicate``."""
        try:
            async with asyncio.timeout(timeout):
                async with self._condition:
                    while not predicate(self):
                        await self._condition.wait()
            return True
        except TimeoutError:
            return predicate(self)

    async def aclose(self, timeout: float = 5.0) -> None:
        """Deliver ``http.disconnect`` and wait for the app to unwind."""
        self._disconnected.set()
        task = self._task
        if task is None or task.done():
            return
        try:
            async with asyncio.timeout(timeout):
                await asyncio.shield(task)
        except (TimeoutError, asyncio.CancelledError):
            task.cancel()
        except Exception:  # noqa: BLE001 - the test asserts on the response, not here
            return

    # -- response accessors -------------------------------------------- #
    @property
    def text(self) -> str:
        return b"".join(self.chunks).decode("utf-8")

    def header(self, name: str) -> Optional[str]:
        wanted = name.lower().encode("latin-1")
        for key, value in self.headers:
            if key.lower() == wanted:
                return value.decode("latin-1")
        return None

    def json(self) -> Any:
        return json.loads(self.text)


def parse_sse(text: str) -> List[Dict[str, Any]]:
    """Parse complete SSE frames out of a partial stream (v1.2 §21's wire form).

    An incomplete trailing frame is ignored, which is exactly what a client sees
    mid-stream: only the ``\\r\\n\\r\\n``-terminated frames are dispatched.
    """
    frames: List[Dict[str, Any]] = []
    if not text.endswith("\r\n\r\n"):
        boundary = text.rfind("\r\n\r\n")
        text = text[: boundary + 4] if boundary >= 0 else ""
    for block in text.split("\r\n\r\n"):
        if not block.strip():
            continue
        frame: Dict[str, Any] = {"id": None, "event": None, "data": None, "comment": None}
        data_lines: List[str] = []
        comments: List[str] = []
        for line in block.split("\r\n"):
            if line.startswith(":"):
                comments.append(line[1:].strip())
            elif line.startswith("id:"):
                frame["id"] = line[3:].strip()
            elif line.startswith("event:"):
                frame["event"] = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
        if data_lines:
            frame["data"] = json.loads("\n".join(data_lines))
        if comments:
            frame["comment"] = "\n".join(comments)
        frames.append(frame)
    return frames


async def login_over_asgi(application: Any, username: str) -> Tuple[str, int]:
    """Log in through the real route and return ``(token, user_id)``."""
    call = AsgiCall(
        application,
        "/api/v1/auth/login",
        method="POST",
        headers={"content-type": "application/json"},
        body=json.dumps({"username": username, "password": PASSWORD}).encode(),
    )
    async with call:
        assert await call.wait_until(lambda item: item.complete.is_set())
    assert call.status == 200, call.text
    data = call.json()["data"]
    return str(data["access_token"]), int(data["user"]["id"])


def auth_headers(token: str, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    headers = {"authorization": f"Bearer {token}"}
    headers.update(extra or {})
    return headers


def test_unauthenticated_task_stream_is_refused(
    client: TestClient, users: Dict[str, int], tasks: TaskService
) -> None:
    """v1.2 §21 — the stream is authenticated before a single frame is written."""
    task_id = run(
        tasks.create(type="calculate", action="analysis", runner=None, start=False)
    )
    response = client.get(f"/api/v1/tasks/{task_id}/stream")
    assert response.status_code == 401
    assert assert_envelope(response.json())["code"] == ErrorCode.AUTH_REQUIRED.value


def test_task_stream_replays_then_follows_live_events(
    factory: Callable[[], Session], seeded: Callable[[], Session], users: Dict[str, int]
) -> None:
    """v1.2 §21 — the task's own events, replayed and then streamed live."""

    async def scenario() -> None:
        bus = EventBus()
        tasks = TaskService(event_bus=bus)
        application, _bus, _tasks = make_app(factory, bus=bus, tasks=tasks)
        async with application.router.lifespan_context(application):
            token, user_id = await login_over_asgi(application, "alice")

            gate = asyncio.Event()

            async def runner() -> Dict[str, Any]:
                await gate.wait()
                return {"ok": True}

            task_id = await tasks.create(
                type="calculate",
                action="analysis",
                requested_by=user_id,
                runner=runner,
            )
            assert bus.subscriber_count(task_topic(task_id)) == 0

            call = AsgiCall(
                application,
                f"/api/v1/tasks/{task_id}/stream",
                headers=auth_headers(token),
            )
            await call.start()
            try:
                assert await call.wait_until(lambda item: item.status is not None)
                assert call.status == 200
                assert call.header("content-type").startswith("text/event-stream")
                # 总纲 §4.3.1 — the X-Request-ID echo survives exception 1.
                assert call.header("x-request-id")

                # queued (replayed from the store) + started (live) have arrived.
                assert await call.wait_until(
                    lambda item: len(parse_sse(item.text)) >= 2, timeout=5.0
                ), call.text
                assert bus.subscriber_count(task_topic(task_id)) == 1

                gate.set()
                assert await call.wait_until(lambda item: item.complete.is_set(), timeout=5.0)

                frames = parse_sse(call.text)
                names = [frame["event"] for frame in frames]
                assert "task.started" in names
                assert names[-1] == "task.completed", frames

                started = next(frame for frame in frames if frame["event"] == "task.started")
                assert started["data"] == {
                    "task_id": task_id,
                    "type": "calculate",
                    "action": "analysis",
                }
                completed = frames[-1]
                assert completed["data"]["task_id"] == task_id
                assert completed["data"]["status"] == "success"
                assert completed["data"]["progress"] == 100.0

                # Every frame carries the task_events.id as its cursor.
                ids = [int(frame["id"]) for frame in frames if frame["id"]]
                assert ids == sorted(ids) and len(set(ids)) == len(ids)
            finally:
                await call.aclose()

            # The generator's ``finally`` released the subscription.
            assert bus.subscriber_count(task_topic(task_id)) == 0

    run(scenario())


def test_task_stream_resumes_from_last_event_id(
    factory: Callable[[], Session], seeded: Callable[[], Session], users: Dict[str, int]
) -> None:
    """v1.2 §21 / V2.1 §10.3 — the cursor is the event id, and it is honoured."""

    async def scenario() -> None:
        bus = EventBus()
        tasks = TaskService(event_bus=bus)
        application, _bus, _tasks = make_app(factory, bus=bus, tasks=tasks)
        async with application.router.lifespan_context(application):
            token, user_id = await login_over_asgi(application, "alice")

            async def runner() -> Dict[str, Any]:
                return {"ok": True}

            task_id = await tasks.create(
                type="calculate", action="analysis", requested_by=user_id, runner=runner
            )
            await tasks.drain()
            stored = await tasks.store.load_events(task_id)
            assert [event.event_type for event in stored] == ["queued", "started", "finished"]
            queued, started, finished = stored

            # --- via the Last-Event-ID header ------------------------- #
            call = AsgiCall(
                application,
                f"/api/v1/tasks/{task_id}/stream",
                headers=auth_headers(token, {"last-event-id": str(started.id)}),
            )
            async with call:
                assert await call.wait_until(lambda item: item.complete.is_set(), timeout=5.0)
                frames = parse_sse(call.text)
            assert [frame["id"] for frame in frames] == [str(finished.id)], frames
            assert frames[0]["event"] == "task.completed"
            assert frames[0]["data"]["status"] == "success"
            # The two earlier events were **not** replayed.
            assert all(frame["id"] != str(queued.id) for frame in frames)
            assert all(frame["event"] != "task.started" for frame in frames)

            # --- and via the ?since= query parameter ------------------ #
            call = AsgiCall(
                application,
                f"/api/v1/tasks/{task_id}/stream",
                headers=auth_headers(token),
                query=f"since={started.id}".encode(),
            )
            async with call:
                assert await call.wait_until(lambda item: item.complete.is_set(), timeout=5.0)
                frames = parse_sse(call.text)
            assert [frame["id"] for frame in frames] == [str(finished.id)]

            # --- a cursor at the end of a finished task --------------- #
            # The stream still closes with a terminal frame projected from the
            # record: a client that reconnects during the ``_save``/``_emit``
            # window of a terminal transition must not be left without a final
            # event, and an EventSource left open would reconnect forever.
            call = AsgiCall(
                application,
                f"/api/v1/tasks/{task_id}/stream",
                headers=auth_headers(token),
                query=f"since={finished.id}".encode(),
            )
            async with call:
                assert await call.wait_until(lambda item: item.complete.is_set(), timeout=5.0)
                frames = parse_sse(call.text)
            assert [frame["event"] for frame in frames] == ["task.completed"]
            assert frames[0]["data"]["status"] == "success"

    run(scenario())


def test_task_stream_rejects_a_non_numeric_cursor(
    factory: Callable[[], Session], seeded: Callable[[], Session], users: Dict[str, int]
) -> None:
    """``?since=`` is an event-id cursor (V2.1 §10.3) — anything else is refused."""

    async def scenario() -> None:
        bus = EventBus()
        tasks = TaskService(event_bus=bus)
        application, _bus, _tasks = make_app(factory, bus=bus, tasks=tasks)
        async with application.router.lifespan_context(application):
            token, user_id = await login_over_asgi(application, "alice")
            task_id = await tasks.create(
                type="calculate", action="analysis", requested_by=user_id, start=False
            )
            call = AsgiCall(
                application,
                f"/api/v1/tasks/{task_id}/stream",
                headers=auth_headers(token),
                query=b"since=2026-09-25T08:41:00Z",
            )
            async with call:
                assert await call.wait_until(lambda item: item.complete.is_set(), timeout=5.0)
            assert call.status == 422
            assert call.json()["code"] == ErrorCode.VALIDATION_ERROR.value

    run(scenario())


def test_client_disconnect_releases_the_subscription(
    factory: Callable[[], Session], seeded: Callable[[], Session], users: Dict[str, int]
) -> None:
    """v1.2 §21 — ``client_close_handler_callable`` is the unsubscribe seam."""

    async def scenario() -> None:
        bus = EventBus()
        tasks = TaskService(event_bus=bus)
        application, _bus, _tasks = make_app(factory, bus=bus, tasks=tasks)
        async with application.router.lifespan_context(application):
            token, user_id = await login_over_asgi(application, "alice")

            gate = asyncio.Event()

            async def runner() -> Dict[str, Any]:
                await gate.wait()
                return {"ok": True}

            task_id = await tasks.create(
                type="calculate", action="analysis", requested_by=user_id, runner=runner
            )
            call = AsgiCall(
                application,
                f"/api/v1/tasks/{task_id}/stream",
                headers=auth_headers(token),
            )
            await call.start()
            assert await call.wait_until(lambda item: item.status is not None)
            assert await call.wait_until(lambda item: len(parse_sse(item.text)) >= 1)
            assert bus.subscriber_count(task_topic(task_id)) == 1

            # Hang up while the task is still running.
            await call.aclose()
            assert bus.subscriber_count(task_topic(task_id)) == 0
            assert bus.topics() == []

            # The engine keeps working; only the stream went away.
            gate.set()
            await tasks.drain()
            assert (await tasks.get(task_id))["status"] == "success"

    run(scenario())


def test_log_stream_receives_global_events(
    factory: Callable[[], Session], seeded: Callable[[], Session], users: Dict[str, int]
) -> None:
    """v1.2 §22.3 — ``log.appended`` over the global ``tasks`` topic."""

    async def scenario() -> None:
        bus = EventBus()
        tasks = TaskService(event_bus=bus)
        application, _bus, _tasks = make_app(factory, bus=bus, tasks=tasks)
        async with application.router.lifespan_context(application):
            token, user_id = await login_over_asgi(application, "alice")

            call = AsgiCall(application, "/api/v1/logs/stream", headers=auth_headers(token))
            await call.start()
            try:
                assert await call.wait_until(lambda item: item.status is not None)
                assert call.status == 200
                assert call.header("content-type").startswith("text/event-stream")
                # The generator subscribes on its first step, before the client
                # can publish anything; assert it rather than assume it.
                await asyncio.sleep(0)
                assert bus.subscriber_count("tasks") == 1

                async def runner() -> Dict[str, Any]:
                    return {"ok": True}

                task_id = await tasks.create(
                    type="calculate", action="analysis", requested_by=user_id, runner=runner
                )
                await tasks.drain()

                assert await call.wait_until(
                    lambda item: len(parse_sse(item.text)) >= 3, timeout=5.0
                ), call.text
                frames = parse_sse(call.text)
                assert all(frame["event"] == "log.appended" for frame in frames)
                assert all(frame["data"]["module"] == "task" for frame in frames)
                assert all(frame["data"]["task_id"] == task_id for frame in frames)
                assert frames[-1]["data"]["level"] == "INFO"
                assert "id" in frames[0]["data"] and "timestamp" in frames[0]["data"]
            finally:
                await call.aclose()
            assert bus.subscriber_count("tasks") == 0

    run(scenario())


def test_log_stream_hides_another_users_events(
    factory: Callable[[], Session], seeded: Callable[[], Session], users: Dict[str, int]
) -> None:
    """The aggregate feed must not become a way around the ownership filter."""

    async def scenario() -> None:
        bus = EventBus()
        tasks = TaskService(event_bus=bus)
        application, _bus, _tasks = make_app(factory, bus=bus, tasks=tasks)
        async with application.router.lifespan_context(application):
            token, _alice = await login_over_asgi(application, "alice")
            call = AsgiCall(application, "/api/v1/logs/stream", headers=auth_headers(token))
            await call.start()
            try:
                assert await call.wait_until(lambda item: item.status is not None)
                await tasks.create(
                    type="calculate", action="analysis", requested_by=users["bob"]
                )
                await tasks.drain()
                await asyncio.sleep(0)
                assert parse_sse(call.text) == []
            finally:
                await call.aclose()

    run(scenario())


def test_task_stream_refuses_another_users_task(
    factory: Callable[[], Session], seeded: Callable[[], Session], users: Dict[str, int]
) -> None:
    """v1.2 §21 — ``tasks.requested_by`` is the data scope (总纲 §4.8.2 is closed)."""

    async def scenario() -> None:
        bus = EventBus()
        tasks = TaskService(event_bus=bus)
        application, _bus, _tasks = make_app(factory, bus=bus, tasks=tasks)
        async with application.router.lifespan_context(application):
            token, _alice = await login_over_asgi(application, "alice")
            task_id = await tasks.create(
                type="calculate",
                action="analysis",
                requested_by=users["bob"],
                start=False,
            )
            call = AsgiCall(
                application,
                f"/api/v1/tasks/{task_id}/stream",
                headers=auth_headers(token),
            )
            async with call:
                assert await call.wait_until(lambda item: item.complete.is_set(), timeout=5.0)
            assert call.status == 403
            assert call.json()["code"] == ErrorCode.PERMISSION_DENIED.value

    run(scenario())


# ---------------------------------------------------------------------------
# 6. the bus itself — bounded memory, independence, idempotent close
# ---------------------------------------------------------------------------
def test_slow_subscriber_is_bounded_and_reported() -> None:
    """The documented slow-subscriber policy: drop-oldest + a ``dropped`` counter."""

    async def scenario() -> None:
        bus = EventBus(queue_size=4)
        subscription = bus.subscribe("topic")
        for index in range(10):
            await bus.publish("topic", {"n": index})

        assert subscription.maxsize == 4
        assert subscription.pending == 4, "an unbounded queue is the bug this prevents"
        assert subscription.dropped == 6
        assert subscription.pending <= subscription.maxsize

        # The survivors are the *newest* four — which is why a terminal event is
        # never the one dropped, and a stream still closes on its own.
        received = [await anext(subscription) for _ in range(subscription.pending)]
        assert [item["n"] for item in received] == [6, 7, 8, 9]

        await subscription.close()
        assert subscription.closed is True
        assert bus.subscriber_count("topic") == 0

    run(scenario())


def test_close_is_idempotent_and_wakes_a_parked_consumer() -> None:
    async def scenario() -> None:
        bus = EventBus()
        subscription = bus.subscribe("topic")

        async def consume() -> List[Dict[str, Any]]:
            return [item async for item in subscription]

        consumer = asyncio.ensure_future(consume())
        await asyncio.sleep(0)
        await subscription.close()
        await subscription.close()  # idempotent
        assert await asyncio.wait_for(consumer, timeout=5.0) == []

        # A closed subscription is not a subscriber any more, and the bus can be
        # closed twice without complaint.
        assert bus.subscriber_count("topic") == 0
        await bus.close()
        await bus.close()
        assert bus.closed is True

    run(scenario())


def test_a_disconnecting_subscriber_does_not_affect_the_others() -> None:
    async def scenario() -> None:
        bus = EventBus()
        first = bus.subscribe("topic")
        second = bus.subscribe("topic")
        assert bus.subscriber_count("topic") == 2

        await first.close()
        delivered = await bus.publish("topic", {"n": 1})
        assert delivered == 1
        assert await anext(second) == {"n": 1}
        assert bus.subscriber_count("topic") == 1

        await second.close()
        assert bus.topics() == []

    run(scenario())


def test_publish_to_an_unknown_topic_is_not_an_error() -> None:
    async def scenario() -> None:
        bus = EventBus()
        assert await bus.publish("nobody-listening", {"n": 1}) == 0

    run(scenario())


def test_task_service_without_a_bus_still_emits_events() -> None:
    """The optional hook is genuinely optional: no bus, no behaviour change."""

    async def scenario() -> None:
        tasks = TaskService()
        assert tasks.event_bus is None

        async def runner() -> Dict[str, Any]:
            return {"ok": True}

        # A runner is required for the lifecycle to advance at all: V2.1 §26.1
        # only schedules a task that has one, so without it the record stays
        # ``queued`` and ``queued`` is the only event that exists.
        task_id = await tasks.create(type="calculate", action="analysis", runner=runner)
        await tasks.drain()
        events = await tasks.store.load_events(task_id)
        assert [event.event_type for event in events] == ["queued", "started", "finished"]

    run(scenario())


def test_task_service_publishes_to_both_topics() -> None:
    """v1.2 §21 (per-task) and §22.3 (global) are fed from one choke point."""

    async def scenario() -> None:
        bus = EventBus()
        tasks = TaskService(event_bus=bus)

        async def runner() -> Dict[str, Any]:
            return {"ok": True}

        # ``_emit`` for ``queued`` runs before ``_drive`` is ever scheduled, so
        # the per-task subscription is opened in time to see ``started``.
        task_id = await tasks.create(
            type="calculate", action="analysis", requested_by=7, runner=runner
        )
        per_task = bus.subscribe(task_topic(task_id))
        global_feed = bus.subscribe("tasks")

        await tasks.drain()
        # A second task, to prove the global topic really is global.
        await tasks.create(type="report", action="generate", requested_by=7)

        task_events = [await anext(per_task) for _ in range(per_task.pending)]
        global_events = [await anext(global_feed) for _ in range(global_feed.pending)]
        assert [item["event_type"] for item in task_events] == ["started", "finished"]
        assert [item["event_type"] for item in global_events] == [
            "started",
            "finished",
            "queued",
        ]
        assert task_events[0]["status"] == "running"
        assert task_events[-1]["status"] == "success"
        assert task_events[0]["id"] < task_events[-1]["id"]
        assert task_events[0]["requested_by"] == 7
        # The published mapping carries what v1.2 §21's payload table needs.
        assert {"task_id", "type", "action", "progress", "created_at"} <= set(task_events[0])

        await per_task.close()
        await global_feed.close()

    run(scenario())


def test_no_new_permission_code_is_referenced() -> None:
    """总纲 §4.8.2 is closed: every code this module names is a member."""
    from app import main as main_module

    referenced = {
        value
        for name, value in vars(main_module).items()
        if name.isupper() and isinstance(value, str) and ":" in value
    }
    assert referenced, "expected at least TASK_READ_PERMISSION"
    assert referenced <= set(PERMISSION_CODES)


# ---------------------------------------------------------------------------
# 7. refresh — the rotation moved into AuthService (v1.2 §5.4)
# ---------------------------------------------------------------------------
def test_refresh_rotates_the_session_row_and_stores_no_plaintext(
    client: TestClient, users: Dict[str, int], seeded: Callable[[], Session]
) -> None:
    """v1.2 §5.4 + 裁决 C-9 + §4.7.1: rotate, re-derive the TTL, store a hash only."""
    set_policy(seeded, session_timeout_minutes=45)
    token = login(client, "alice")

    with session_scope_for(seeded) as session:
        before = session.scalars(
            select(UserSession).where(UserSession.user_id == users["alice"])
        ).all()
    assert len(before) == 1
    old_session_id = before[0].session_id
    old_token_hash = before[0].token_hash
    assert before[0].revoked_at is None

    response = client.post(
        "/api/v1/auth/refresh", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200, response.text
    data = assert_envelope(response.json())["data"]
    new_token = str(data["access_token"])
    assert new_token != token
    # 裁决 C-9 — ``expires_in`` is security_configs.session_timeout_minutes × 60,
    # not a constant and not the previous TTL.
    assert data["expires_in"] == 45 * 60 == 2700

    old_claims = decode_token(token)
    new_claims = decode_token(new_token)
    assert new_claims["exp"] - new_claims["iat"] == 2700
    assert new_claims["jti"] != old_claims["jti"]
    assert new_claims["sub"] == old_claims["sub"]

    with session_scope_for(seeded) as session:
        rows = session.scalars(
            select(UserSession).where(UserSession.user_id == users["alice"])
        ).all()
    assert len(rows) == 2, "rotate, not extend: exactly one replacement row"
    by_id = {row.session_id: row for row in rows}
    assert by_id[old_session_id].revoked_at is not None
    assert by_id[old_session_id].token_hash == old_token_hash, "the old row is not rewritten"
    new_row = next(row for row in rows if row.session_id != old_session_id)
    assert new_row.revoked_at is None
    assert new_row.session_id == new_claims["jti"]
    assert new_row.expires_at is not None
    # 总纲 §4.1.3 — ``sessions`` has no prefix in the closed set, so the id is a
    # bare uuid4 hex and must not look like ``<prefix>_<...>``.
    assert re.fullmatch(r"[0-9a-f]{32}", str(new_row.session_id)), new_row.session_id
    # 总纲 §4.7.1 — only a hash, and the plaintext is in neither row.
    assert token not in (old_token_hash, str(new_row.token_hash))
    assert new_token not in (old_token_hash, str(new_row.token_hash))
    assert crypto.verify_secret(new_token, new_row.token_hash) is True


def test_a_rotated_away_token_cannot_be_refreshed_again(
    client: TestClient, users: Dict[str, int]
) -> None:
    """v1.2 §5.4 — the presented token is dead the moment it is rotated away."""
    token = login(client, "alice")
    first = client.post(
        "/api/v1/auth/refresh", headers={"Authorization": f"Bearer {token}"}
    )
    assert first.status_code == 200, first.text

    again = client.post(
        "/api/v1/auth/refresh", headers={"Authorization": f"Bearer {token}"}
    )
    assert again.status_code == 401
    envelope = assert_envelope(again.json())
    assert envelope["code"] == ErrorCode.AUTH_INVALID.value
    # ``AuthService.refresh_now`` verifies the token first, so a revoked row is
    # refused by ``verify_token_now`` with its own, pre-existing reason — the
    # ``unknown_session`` reason of the rotation step is for the race where the
    # row disappears between the two transactions (see the next test).
    assert envelope["details"]["reason"] == "session_revoked"


def test_refresh_now_refuses_a_session_row_that_is_gone(
    seeded: Callable[[], Session], users: Dict[str, int]
) -> None:
    """总纲 §4.4.1 — ``AUTH_INVALID`` / ``reason="unknown_session"``, from the service.

    The REST route cannot reach this state (verification runs first), which is
    exactly why it is asserted against :meth:`AuthService.refresh_now` directly:
    the branch moved out of ``main.py`` with the rotation and must not have been
    dropped on the way.
    """
    service = AuthService(session_factory=seeded)
    result = run(service.login("alice", PASSWORD))
    with session_scope_for(seeded) as session:
        session.execute(
            delete(UserSession).where(UserSession.session_id == result.session_id)
        )

    with pytest.raises(AdapterError) as excinfo:
        run(service.refresh(result.token))
    assert excinfo.value.code == ErrorCode.AUTH_INVALID
    assert excinfo.value.details["reason"] == "unknown_session"


def test_refresh_requires_a_credential(client: TestClient, users: Dict[str, int]) -> None:
    """总纲 §4.4.1 ``AUTH_REQUIRED`` — unchanged by the move into the service."""
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
    assert assert_envelope(response.json())["code"] == ErrorCode.AUTH_REQUIRED.value


# ---------------------------------------------------------------------------
# 8. the task list is ownership-filtered *in the query* (v1.2 §20.1 / §21)
# ---------------------------------------------------------------------------
def create_task(
    tasks: TaskService,
    *,
    type: str = "calculate",
    action: str = "analysis",
    adapter_code: Optional[str] = None,
    requested_by: Optional[int] = None,
) -> str:
    """Create one bookkeeping-only task and return its id."""
    return str(
        run(
            tasks.create(
                type=type,
                action=action,
                adapter_code=adapter_code,
                requested_by=requested_by,
                runner=None,
                start=False,
            )
        )
    )


def list_task_ids(
    client: TestClient, token: str, query: str = ""
) -> Tuple[List[str], Dict[str, Any]]:
    """``GET /api/v1/tasks`` and return ``(task_ids, pagination)``."""
    response = client.get(
        f"/api/v1/tasks{query}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200, response.text
    data = assert_envelope(response.json())["data"]
    return [str(row["task_id"]) for row in data["items"]], data["pagination"]


def test_the_task_list_shows_only_your_own_tasks(
    client: TestClient, users: Dict[str, int], tasks: TaskService
) -> None:
    """v1.2 §20.1 + §21 — the fourth endpoint filters like the other three.

    Before this, ``GET /api/v1/tasks`` returned **every** row while
    ``GET /tasks/{id}``, ``/tasks/{id}/stream`` and ``/logs/stream`` all applied
    the ``requested_by`` data scope: any ``visitor`` holding ``task:read`` could
    enumerate the platform's tasks.  The scope is the same closed-set
    ``task:read`` plus a data filter — 总纲 §4.8.2 stays closed.
    """
    mine = [create_task(tasks, requested_by=users["alice"]) for _ in range(3)]
    theirs = [create_task(tasks, requested_by=users["bob"]) for _ in range(4)]

    ids, pagination = list_task_ids(client, login(client, "alice"))
    assert set(ids) == set(mine)
    assert not set(ids) & set(theirs), "another user's task must not be listed"
    # The trap: filtering the returned page would keep the platform-wide count.
    assert pagination["total"] == len(mine)
    assert pagination["total_pages"] == 1


def test_a_super_admin_sees_every_task(
    client: TestClient, users: Dict[str, int], admin: int, tasks: TaskService
) -> None:
    """总纲 §4.8.3 — ``super_admin`` is the one role the data scope lets through."""
    mine = [create_task(tasks, requested_by=users["alice"]) for _ in range(2)]
    theirs = [create_task(tasks, requested_by=users["bob"]) for _ in range(3)]
    orphan = create_task(tasks, requested_by=None)

    ids, pagination = list_task_ids(client, login(client, "root"))
    assert set(ids) == set(mine) | set(theirs) | {orphan}
    assert pagination["total"] == 6


def test_an_unattributed_task_is_not_public(
    client: TestClient, users: Dict[str, int], tasks: TaskService
) -> None:
    """The ownership filter **fails closed** on ``requested_by IS NULL``.

    A row that belongs to nobody is matched by nobody.  It is deliberately *not*
    treated as "public", because ``tasks.requested_by`` is ``ON DELETE SET NULL``
    (V2.1 §4): with a fail-open rule, hard-deleting one user would publish that
    user's entire task history to every remaining caller.  An unattributed task
    therefore stays reachable only by an unfiltered caller — ``super_admin``.
    """
    orphan = create_task(tasks, requested_by=None)
    mine = create_task(tasks, requested_by=users["alice"])
    theirs = create_task(tasks, requested_by=users["bob"])

    for username in ("alice", "bob"):
        ids, pagination = list_task_ids(client, login(client, username))
        assert orphan not in ids, "an ownerless task must not be public"
        assert pagination["total"] == 1, "only the caller's own task is counted"

    ids, _pagination = list_task_ids(client, login(client, "alice"))
    assert mine in ids and theirs not in ids and orphan not in ids


def test_paging_is_correct_under_the_ownership_filter(
    client: TestClient, users: Dict[str, int], tasks: TaskService
) -> None:
    """The assertion that catches a handler-side filter: full pages and a true total.

    ``service.list`` applies ``page``/``page_size`` itself, so a filter applied to
    the *returned* page would produce short or empty pages while the rows sit on
    later ones — and a ``total`` that counts other users' tasks.
    """
    mine = [create_task(tasks, requested_by=users["alice"]) for _ in range(5)]
    for _ in range(4):
        create_task(tasks, requested_by=users["bob"])

    token = login(client, "alice")
    seen: List[str] = []
    for page, expected_size in ((1, 2), (2, 2), (3, 1)):
        ids, pagination = list_task_ids(
            client, token, f"?page={page}&page_size=2"
        )
        assert len(ids) == expected_size, f"page {page} is short: {ids}"
        assert pagination == {
            "page": page,
            "page_size": 2,
            "total": 5,
            "total_pages": 3,
        }
        seen.extend(ids)
    assert sorted(seen) == sorted(mine)


def test_the_post_filter_path_honours_the_ownership_filter(
    client: TestClient, users: Dict[str, int], tasks: TaskService
) -> None:
    """``action`` / ``adapter`` / ``keyword`` re-query — and must re-filter too."""
    mine = create_task(
        tasks,
        type="calculate",
        action="analysis",
        adapter_code="midas_gen",
        requested_by=users["alice"],
    )
    create_task(
        tasks,
        type="calculate",
        action="analysis",
        adapter_code="midas_gen",
        requested_by=users["bob"],
    )
    create_task(tasks, type="report", action="generate", requested_by=users["alice"])

    token = login(client, "alice")
    for query in ("?keyword=calculate", "?action=analysis", "?adapter=midas_gen"):
        ids, pagination = list_task_ids(client, token, query)
        assert ids == [mine], query
        assert pagination["total"] == 1, query


def test_the_ownership_scope_is_the_one_the_streams_use() -> None:
    """One rule, two consumers: the query filter and the per-row predicate agree."""
    from app.main import _task_owner_scope, _task_visible_to

    principal = Principal(
        user_id=7,
        username="alice",
        roles=("visitor",),
        permissions=frozenset({TASK_READ_PERMISSION}),
        department=None,
        expires_at=datetime.now(timezone.utc),
        session_id="a" * 32,
    )
    assert _task_owner_scope(principal) == 7
    assert not _task_visible_to(
        TaskRecord(task_id="t", type="calculate", action="a"), principal
    ), "fail closed: an ownerless row is not within a normal caller's scope"
    assert _task_visible_to(
        TaskRecord(task_id="t", type="calculate", action="a", requested_by=7), principal
    )
    assert not _task_visible_to(
        TaskRecord(task_id="t", type="calculate", action="a", requested_by=8), principal
    )

    super_admin = Principal(
        user_id=1,
        username="root",
        roles=("super_admin",),
        permissions=frozenset({TASK_READ_PERMISSION}),
        department=None,
        expires_at=datetime.now(timezone.utc),
        session_id="b" * 32,
    )
    assert _task_owner_scope(super_admin) is None, "None means 'no filter at all'"
    assert _task_visible_to(
        TaskRecord(task_id="t", type="calculate", action="a", requested_by=8), super_admin
    )
    assert _task_visible_to(
        TaskRecord(task_id="t", type="calculate", action="a"), super_admin
    ), "the unfiltered caller is the one path that still reaches an orphan"


# ---------------------------------------------------------------------------
# 9. rate limiting (总纲 §4.4.2 RATE_LIMITED → 429 / §8.6, 裁决 B-7)
# ---------------------------------------------------------------------------
#: A path that is limited and cheap: ``/api/v1/health`` is **not** exempt
#: (see ``RATE_LIMIT_EXEMPT_PATHS``) and answers through the envelope.
LIMITED_PATH = "/api/v1/health"


def test_rate_limit_exemptions_are_the_two_probes_only() -> None:
    """v1.2 §35/§36 are exempt; §34's aggregate check and OpenAPI are not."""
    assert RATE_LIMIT_EXEMPT_PATHS == {
        "/api/v1/health/ready",
        "/api/v1/health/live",
    }
    # The two exemption sets answer different questions and must not be merged.
    assert RATE_LIMIT_EXEMPT_PATHS < ENVELOPE_EXEMPT_PATHS


def test_under_the_limit_succeeds_and_reports_the_budget(
    factory: Callable[[], Session], seeded: Callable[[], Session]
) -> None:
    """总纲 §4.4.2 — the three headers ride on successful responses too."""
    set_policy(seeded, rate_limit_enabled=1, rate_limit_per_minute=60, rate_limit_burst=5)
    application, _bus, _tasks = make_app(
        factory, rate_limiter=RateLimitLimiter(clock=FakeClock())
    )
    with TestClient(application) as client:
        response = client.get(LIMITED_PATH)

    assert response.status_code == 200, response.text
    assert assert_envelope(response.json())["success"] is True
    assert response.headers["x-ratelimit-limit"] == "5"
    assert response.headers["x-ratelimit-remaining"] == "4"
    assert int(response.headers["x-ratelimit-reset"]) >= 0
    assert "retry-after" not in response.headers, "only a 429 carries Retry-After"


def test_over_the_burst_is_429_with_the_envelope_and_retry_after(
    factory: Callable[[], Session], seeded: Callable[[], Session]
) -> None:
    """总纲 §4.4.2 — ``RATE_LIMITED`` → 429, full §4.3.1 envelope, ``Retry-After`` ≥ 1."""
    set_policy(seeded, rate_limit_enabled=1, rate_limit_per_minute=60, rate_limit_burst=3)
    application, _bus, _tasks = make_app(
        factory, rate_limiter=RateLimitLimiter(clock=FakeClock())
    )
    with TestClient(application) as client:
        for index in range(3):
            allowed = client.get(LIMITED_PATH)
            assert allowed.status_code == 200
            assert allowed.headers["x-ratelimit-remaining"] == str(2 - index)
        blocked = client.get(LIMITED_PATH)
        blocked_again = client.get(LIMITED_PATH)

    assert blocked.status_code == 429
    envelope = assert_envelope(blocked.json())
    assert_no_bare_top_level(envelope)
    assert envelope["success"] is False
    assert envelope["code"] == ErrorCode.RATE_LIMITED.value
    assert envelope["data"] is None
    assert envelope["details"]["reason"] == "rate_limited"
    assert envelope["details"]["burst"] == 3
    assert envelope["details"]["per_minute"] == 60
    assert REQUEST_ID_RE.match(envelope["request_id"])
    assert blocked.headers["x-ratelimit-limit"] == "3"
    assert blocked.headers["x-ratelimit-remaining"] == "0"
    assert int(blocked.headers["retry-after"]) >= 1
    assert blocked.headers["retry-after"] == blocked_again.headers["retry-after"]
    # The 429 is not the §4.3.1 exception list: it is enveloped JSON.
    assert blocked.headers["content-type"].startswith("application/json")


def test_rate_limit_enabled_zero_disables_the_limiter_entirely(
    factory: Callable[[], Session], seeded: Callable[[], Session]
) -> None:
    """裁决 B-7 — the master switch is read from ``security_configs``."""
    set_policy(seeded, rate_limit_enabled=0, rate_limit_per_minute=1, rate_limit_burst=1)
    application, _bus, _tasks = make_app(
        factory, rate_limiter=RateLimitLimiter(clock=FakeClock())
    )
    with TestClient(application) as client:
        responses = [client.get(LIMITED_PATH) for _ in range(6)]

    assert [item.status_code for item in responses] == [200] * 6
    # Not merely "allowed": the limiter did not run at all.
    assert "x-ratelimit-limit" not in responses[0].headers
    assert "retry-after" not in responses[-1].headers


def rate_limit_middleware_of(application: FastAPI) -> RateLimitMiddleware:
    """Walk the built ASGI stack and return the limiter middleware."""
    node: Any = application.middleware_stack
    while node is not None:
        if isinstance(node, RateLimitMiddleware):
            return node
        node = getattr(node, "app", None)
    raise AssertionError("RateLimitMiddleware is not in the middleware stack")


def test_the_policy_is_read_from_the_row_and_cached_until_the_ttl(
    factory: Callable[[], Session], seeded: Callable[[], Session]
) -> None:
    """裁决 B-7 — the row wins over ``Settings``, and re-reading is rate-limited.

    The read is a database round trip, so it happens at most once per
    ``RATE_LIMIT_POLICY_TTL_SECONDS``; ``forget_policy`` is the seam an operator
    (or a test) uses to make a just-edited row take effect immediately.
    """
    set_policy(seeded, rate_limit_enabled=1, rate_limit_per_minute=1, rate_limit_burst=1)
    application, _bus, _tasks = make_app(
        factory, rate_limiter=RateLimitLimiter(clock=FakeClock())
    )
    with TestClient(application) as client:
        assert client.get(LIMITED_PATH).status_code == 200
        assert client.get(LIMITED_PATH).status_code == 429

        # The row is edited, but the cached policy is still in force.
        set_policy(seeded, rate_limit_enabled=0)
        assert client.get(LIMITED_PATH).status_code == 429

        rate_limit_middleware_of(application).forget_policy()
        assert client.get(LIMITED_PATH).status_code == 200


def test_the_bucket_refills_with_an_injected_clock(
    factory: Callable[[], Session], seeded: Callable[[], Session]
) -> None:
    """裁决 B-7 — 60 tokens/minute is 1 token/second; the test never sleeps."""
    set_policy(seeded, rate_limit_enabled=1, rate_limit_per_minute=60, rate_limit_burst=2)
    clock = FakeClock()
    application, _bus, _tasks = make_app(
        factory, rate_limiter=RateLimitLimiter(clock=clock)
    )
    with TestClient(application) as client:
        assert client.get(LIMITED_PATH).status_code == 200
        assert client.get(LIMITED_PATH).status_code == 200
        assert client.get(LIMITED_PATH).status_code == 429

        clock.advance(1.0)  # one whole token
        refilled = client.get(LIMITED_PATH)
        assert refilled.status_code == 200, refilled.text
        assert refilled.headers["x-ratelimit-remaining"] == "0"
        assert client.get(LIMITED_PATH).status_code == 429


def test_health_probes_stay_unlimited_while_the_rest_is_saturated(
    factory: Callable[[], Session], seeded: Callable[[], Session]
) -> None:
    """v1.2 §35/§36 — a probe that locks itself out takes the service down twice."""
    set_policy(seeded, rate_limit_enabled=1, rate_limit_per_minute=1, rate_limit_burst=1)
    application, _bus, _tasks = make_app(
        factory, rate_limiter=RateLimitLimiter(clock=FakeClock())
    )
    with TestClient(application) as client:
        assert client.get(LIMITED_PATH).status_code == 200
        assert client.get(LIMITED_PATH).status_code == 429, "the bucket is empty"

        ready = client.get("/api/v1/health/ready")
        live = client.get("/api/v1/health/live")

        # …and the rest of the surface is still saturated.
        assert client.get(LIMITED_PATH).status_code == 429

    assert ready.status_code == 200
    assert live.status_code == 200
    # Exempt means the limiter never ran, so there is no budget to report.
    assert "x-ratelimit-limit" not in ready.headers
    assert "x-ratelimit-limit" not in live.headers


def test_forwarded_for_cannot_mint_a_bucket_by_default(
    factory: Callable[[], Session], seeded: Callable[[], Session]
) -> None:
    """总纲 §8.6 — **the bypass test**: a fresh ``X-Forwarded-For`` per request.

    With the header honoured, every request below would land in its own bucket and
    the limit would simply not exist.  It is off by default and the socket peer
    address is the key.
    """
    set_policy(seeded, rate_limit_enabled=1, rate_limit_per_minute=60, rate_limit_burst=2)
    application, _bus, _tasks = make_app(
        factory, rate_limiter=RateLimitLimiter(clock=FakeClock())
    )
    with TestClient(application) as client:
        statuses = [
            client.get(LIMITED_PATH, headers={"X-Forwarded-For": f"10.0.0.{index}"}).status_code
            for index in range(4)
        ]

    assert statuses == [200, 200, 429, 429], statuses


def test_forwarded_for_is_honoured_only_when_explicitly_trusted(
    factory: Callable[[], Session],
    seeded: Callable[[], Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The flag's positive control, including *which* hop it reads."""
    monkeypatch.setattr(get_settings(), "trust_proxy_headers", True)
    set_policy(seeded, rate_limit_enabled=1, rate_limit_per_minute=60, rate_limit_burst=2)
    application, _bus, _tasks = make_app(
        factory, rate_limiter=RateLimitLimiter(clock=FakeClock())
    )
    with TestClient(application) as client:
        def call(forwarded_for: str) -> int:
            return client.get(
                LIMITED_PATH, headers={"X-Forwarded-For": forwarded_for}
            ).status_code

        assert call("203.0.113.5") == 200
        assert call("203.0.113.6") == 200, "a different client has its own bucket"
        assert call("203.0.113.5") == 200
        assert call("203.0.113.5") == 429
        # The **right-most** hop is the one the trusted proxy appended; the
        # spoofable left-most hop selects nothing.
        assert call("9.9.9.9, 203.0.113.5") == 429
        assert call("203.0.113.7, 9.9.9.9") == 200


def test_an_sse_stream_is_charged_once_at_connect(
    factory: Callable[[], Session], seeded: Callable[[], Session], users: Dict[str, int]
) -> None:
    """v1.2 §21 + §8.6 — one request, one token, however many events flow.

    Charging per event would kill a stream the client is legitimately reading; the
    limiter therefore sits in the ASGI request path (once per HTTP request) and
    nothing in the stream generators consults it.  The proof is arithmetic: with a
    burst of 5, login (1) + connect (1) + one final call (1) must leave 2.
    """
    set_policy(seeded, rate_limit_enabled=1, rate_limit_per_minute=60, rate_limit_burst=5)

    async def scenario() -> None:
        bus = EventBus()
        tasks = TaskService(event_bus=bus)
        application, _bus, _tasks = make_app(
            factory,
            bus=bus,
            tasks=tasks,
            rate_limiter=RateLimitLimiter(clock=FakeClock()),
        )
        async with application.router.lifespan_context(application):
            token, user_id = await login_over_asgi(application, "alice")

            async def runner() -> Dict[str, Any]:
                return {"ok": True}

            task_id = await tasks.create(
                type="calculate", action="analysis", requested_by=user_id, runner=runner
            )
            call = AsgiCall(
                application,
                f"/api/v1/tasks/{task_id}/stream",
                headers=auth_headers(token),
            )
            await call.start()
            try:
                assert await call.wait_until(lambda item: item.status is not None)
                assert call.status == 200
                assert call.header("x-ratelimit-limit") == "5"
                # login (1) + this connect (1) == 2 spent.
                assert call.header("x-ratelimit-remaining") == "3"

                # Every event of the task flows through this one stream.
                assert await call.wait_until(
                    lambda item: item.complete.is_set(), timeout=5.0
                ), call.text
                assert len(parse_sse(call.text)) >= 3
            finally:
                await call.aclose()

            # A single further request must see exactly one more token spent:
            # 5 - login - connect - this call == 2.  If the three streamed events
            # had each been charged, this would be 429.
            after = AsgiCall(application, LIMITED_PATH, headers=auth_headers(token))
            async with after:
                assert await after.wait_until(lambda item: item.complete.is_set())
            assert after.status == 200, after.text
            assert after.header("x-ratelimit-remaining") == "2"

    run(scenario())


def test_the_launcher_pins_proxy_headers_to_our_setting() -> None:
    """The rate limiter's key is only as trustworthy as the launcher.

    Regression guard for a **measured** bypass.  uvicorn defaults
    ``proxy_headers=True`` and installs ``ProxyHeadersMiddleware`` *outside* the
    application, where it rewrites ``scope["client"]`` from ``X-Forwarded-For``
    before any app middleware runs.  ``client_key`` refuses to read that header
    unless ``trust_proxy_headers`` is on, but by then the forged address *is* the
    client address — the guard is correct and unreachable.

    Against a live server with ``rate_limit_burst=3``, six requests each carrying
    a different forged ``X-Forwarded-For`` gave:

    * ``--no-proxy-headers``              -> ``200 200 200 429 429 429``
    * uvicorn default (proxy headers on)  -> ``200 200 200 200 200 200``

    Same app, config and database; the launch flag was the only variable.  So the
    launcher must pin the flag rather than inherit it.
    """
    from app.main import uvicorn_options

    options = uvicorn_options()
    assert "proxy_headers" in options, "must be explicit, never inherited"
    assert options["proxy_headers"] is False, (
        "the shipped default is trust_proxy_headers=False, so the launcher must "
        "disable uvicorn's proxy-header rewriting — otherwise a client can mint a "
        "fresh rate-limit bucket per request by varying X-Forwarded-For"
    )


def test_the_launcher_follows_the_setting_when_a_proxy_is_trusted() -> None:
    """…and flips together with it, so a real proxy deployment still works."""
    from app.core.config import get_settings
    from app.main import uvicorn_options

    settings = get_settings()
    original = settings.trust_proxy_headers
    try:
        settings.trust_proxy_headers = True
        assert uvicorn_options()["proxy_headers"] is True
    finally:
        settings.trust_proxy_headers = original


def test_api_auth_required_zero_is_honoured_on_the_rest_surface_too(
    client: TestClient,
    factory: Callable[[], Session],
    seeded: Callable[[], Session],
) -> None:
    """总纲 裁决 C-13 — one config flag must mean one behaviour on both surfaces.

    Regression guard for a **measured** disagreement.  ``api_auth_required = 0``
    means "an unauthenticated call is not refused at all".  The MCP surface got
    that for free from ``make_authorizer`` (it skips the whole gate), but the REST
    routes resolve the principal themselves, so with the switch off they answered

    * ``GET /api/v1/tasks``       -> ``401 AUTH_REQUIRED``
    * ``GET /api/v1/auth/me``     -> ``401 AUTH_REQUIRED``
    * ``GET /api/v1/logs/stream`` -> ``401 AUTH_REQUIRED``

    while MCP allowed the identical caller.  ``_principal_of`` now returns
    :func:`anonymous_principal` in that mode, which holds every §4.8.2 code
    because skipping the gate skips the RBAC step as well.
    """
    from app.services.auth_service import ANONYMOUS_USER_ID

    set_policy(factory, api_auth_required=0)

    tasks_response = client.get("/api/v1/tasks")
    assert tasks_response.status_code == 200, tasks_response.text
    assert tasks_response.json()["success"] is True

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200, me.text
    body = me.json()["data"]
    assert body["username"] == "anonymous"
    assert body["id"] == ANONYMOUS_USER_ID, (
        "0 is never a real users.id, so nothing can be attributed to it — "
        "tasks.requested_by must stay NULL in this mode"
    )


def test_the_anonymous_principal_cannot_be_attributed_a_task(
    factory: Callable[[], Session], seeded: Callable[[], Session]
) -> None:
    """``requested_by`` must stay NULL under C-13, not point at user 0.

    ``tasks.requested_by`` is a real foreign key (V2.1 §4), so attributing a task
    to :data:`ANONYMOUS_USER_ID` would fail the insert outright.
    """
    from app.mcp.tools.execute import _caller_user_id
    from app.services.auth_service import anonymous_principal

    assert _caller_user_id(anonymous_principal()) is None
    assert _caller_user_id(None) is None
