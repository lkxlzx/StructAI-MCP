"""Live auth + RBAC test against a running MIDAS Gen/Civil NX instance.

**Skipped by default** — same gate as the other live tests:

```powershell
$env:STRUCTAI_LIVE_MIDAS_URL = "http://localhost:3030"
$env:STRUCTAI_LIVE_MAPI_KEY = "<key>"
$env:STRUCTAI_LIVE_PRODUCT  = "gen"
..\\.venv\\Scripts\\python.exe -m pytest tests/live -q
```

What it proves that the offline suite cannot:

* the authorizer is actually wired into the dispatcher's **live** call path, so a
  refused call never reaches MIDAS at all;
* an **allowed** call really does reach the instance (the engineer's node is
  created and deleted through the real API);
* cross-tenant instance isolation holds against a real `midas_clients` row.

The permission model itself is covered offline in ``tests/test_auth_rbac.py``;
this file is about the seam being connected.
"""

from __future__ import annotations

import asyncio
import os

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401 — registers all 49 tables on Base.metadata
from app.adapters.midas_gen.adapter import MidasNxAdapter
from app.adapters.registry import AdapterRegistry
from app.core.crypto import hash_secret
from app.core.midas_config import MidasConnection, MidasProduct
from app.db.base import Base
from app.mcp.auth import make_authorizer
from app.mcp.dispatcher import ToolDispatcher
from app.models.identity import Role, User, UserRole
from app.models.midas import Adapter, MidasClient
from app.services.auth_service import AuthService, ensure_bootstrap_admin
from app.services.task_service import TaskService

_LIVE_URL = os.environ.get("STRUCTAI_LIVE_MIDAS_URL")
_LIVE_KEY = os.environ.get("STRUCTAI_LIVE_MAPI_KEY")
_LIVE_PRODUCT = os.environ.get("STRUCTAI_LIVE_PRODUCT", "gen")

pytestmark = pytest.mark.skipif(
    not (_LIVE_URL and _LIVE_KEY),
    reason="live MIDAS test — set STRUCTAI_LIVE_MIDAS_URL and STRUCTAI_LIVE_MAPI_KEY",
)

_ADMIN_PW = "Bootstrap!Passw0rd"
_USERS = (("eng1", "engineer", "Eng1!Passw0rd"),
          ("ana1", "analyst", "Ana1!Passw0rd"),
          ("vis1", "visitor", "Vis1!Passw0rd"))
#: A private instance owned by eng2 — the cross-tenant target.
_PRIVATE_OWNER = ("eng2", "engineer", "Eng2!Passw0rd")


def _run(coro):
    return asyncio.run(coro)


def _seed(tmp_path):
    """A fresh 49-table database with an admin, four users and one private client."""
    engine = create_engine(f"sqlite:///{tmp_path / 'live_rbac.db'}", future=True,
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, class_=Session, autoflush=False,
                           autocommit=False, expire_on_commit=False)
    with factory() as session:
        session.add(Adapter(code="midas_gen", name="MIDAS Gen",
                            software="MIDAS Gen", implementation="x"))
        session.commit()
    ensure_bootstrap_admin(factory, username="root", password=_ADMIN_PW)

    def add(username, role_code, password, *, private_client=False):
        with factory() as session:
            user = User(username=username, name=username,
                        password_hash=hash_secret(password))
            session.add(user)
            session.flush()
            role = session.scalar(select(Role).where(Role.code == role_code))
            session.add(UserRole(user_id=user.id, role_id=role.id))
            if private_client:
                session.add(MidasClient(
                    name=f"{username}-private", software="MIDAS Gen NX",
                    adapter_code="midas_gen", api_url=f"{_LIVE_URL}/{_LIVE_PRODUCT}",
                    visibility="private", owner_id=user.id, department="DeptB"))
            session.commit()
            return user.id

    for username, role_code, password in _USERS:
        add(username, role_code, password)
    add(*_PRIVATE_OWNER, private_client=True)
    return factory


class RecordingTransport(httpx.AsyncBaseTransport):
    """Records every URL the adapter actually requests, then does the real call.

    ``MidasNxAdapter`` has no request log — that is a ``MockAdapter`` feature — so
    a live test that wants to claim "the refused call never reached MIDAS" has to
    measure it.  Hooking the HTTP transport measures exactly that, at the lowest
    point the adapter can be observed from.
    """

    def __init__(self) -> None:
        self._inner = httpx.AsyncHTTPTransport()
        #: ``"METHOD url"`` per request — the method matters: a permitted GET and
        #: a refused POST both touch ``/db/NODE``, so a URL-only log could not
        #: tell them apart.
        self.calls: list[str] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(f"{request.method} {request.url}")
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()

    def touched(self, needle: str) -> bool:
        """True when any ``"METHOD url"`` entry contains ``needle``."""
        return any(needle in call for call in self.calls)


def _connection() -> MidasConnection:
    return MidasConnection(
        name="live",
        software="MIDAS Gen NX" if _LIVE_PRODUCT == "gen" else "MIDAS Civil NX",
        product=MidasProduct(_LIVE_PRODUCT),
        base_url=_LIVE_URL,
        mapi_key=_LIVE_KEY,
        timeout_seconds=120,
        verify_tls=False,
    )


async def _stack(factory):
    transport = RecordingTransport()
    adapter = MidasNxAdapter(_connection(), transport=transport)
    registry = AdapterRegistry()
    registry.register(adapter)
    service = AuthService(session_factory=factory)
    dispatcher = ToolDispatcher(registry=registry, task_service=TaskService(),
                                authorizer=make_authorizer(service))
    tokens = {}
    for username, _role, password in (*_USERS, _PRIVATE_OWNER):
        tokens[username] = (await service.login(username, password)).token
    return adapter, transport, dispatcher, service, tokens


async def _code(dispatcher, tool, arguments, token=None) -> tuple[bool, str]:
    envelope = await dispatcher.dispatch(tool, arguments, principal=token)
    error = (envelope.get("errors") or [{}])[0].get("code", "")
    return envelope["success"], error


def test_live_authentication_is_enforced_before_midas(tmp_path) -> None:
    """A refused call must never reach the instance."""

    async def body():
        factory = _seed(tmp_path)
        adapter, transport, dispatcher, _service, _tokens = await _stack(factory)
        try:
            ok, code = await _code(dispatcher, "midas_query",
                                   {"target": "node", "action": "list"})
            assert ok is False and code == "AUTH_REQUIRED", (ok, code)

            ok, code = await _code(dispatcher, "midas_query",
                                   {"target": "node", "action": "list"},
                                   token="not.a.jwt")
            assert ok is False and code == "AUTH_INVALID", (ok, code)

            # measured, not assumed: neither refusal issued any data call
            assert not transport.touched("/db/"), transport.calls
        finally:
            await adapter.aclose()

    _run(body())


def test_live_rbac_allows_and_refuses_and_the_allowed_call_reaches_midas(tmp_path) -> None:
    """The seam is connected: a permitted call really drives the live API."""

    async def body():
        factory = _seed(tmp_path)
        adapter, transport, dispatcher, _service, tokens = await _stack(factory)
        node = {"9201": {"X": 1.0, "Y": 2.0, "Z": 3.0}}
        try:
            # visitor holds model:read but not model:create
            ok, code = await _code(dispatcher, "midas_query",
                                   {"target": "node", "action": "list"},
                                   token=tokens["vis1"])
            assert ok is True, code

            for who in ("vis1", "ana1"):
                ok, code = await _code(dispatcher, "midas_model",
                                       {"action": "create", "resource": "node", "data": node},
                                       token=tokens[who])
                assert ok is False and code == "PERMISSION_DENIED", (who, ok, code)

            # the two refusals issued no write at all
            assert not transport.touched("POST") or "/db/NODE" not in " ".join(
                c for c in transport.calls if c.startswith("POST")), transport.calls

            # engineer holds it — and this one must actually land on the instance
            ok, code = await _code(dispatcher, "midas_model",
                                   {"action": "create", "resource": "node", "data": node},
                                   token=tokens["eng1"])
            assert ok is True, code
            assert transport.touched("POST") and any(
                c.startswith("POST") and "/db/NODE" in c for c in transport.calls
            ), transport.calls

            read = await dispatcher.dispatch("midas_model",
                                             {"action": "read", "resource": "node",
                                              "ids": [9201]},
                                             principal=tokens["eng1"])
            assert read["success"] is True, read

            ok, code = await _code(dispatcher, "midas_model",
                                   {"action": "delete", "resource": "node", "ids": [9201]},
                                   token=tokens["eng1"])
            assert ok is True, code
            assert transport.touched("DELETE ") and transport.touched("/db/NODE/9201"), \
                transport.calls
        finally:
            await adapter.aclose()

    _run(body())


def test_live_instance_scope_isolates_tenants(tmp_path) -> None:
    """对接规范 §2.5.4 item 5 — a private instance is usable only by its owner."""

    async def body():
        factory = _seed(tmp_path)
        adapter, transport, dispatcher, _service, tokens = await _stack(factory)
        try:
            ok, code = await _code(dispatcher, "midas_query",
                                   {"target": "node", "action": "list", "client_id": 1},
                                   token=tokens["eng2"])
            assert ok is True, code

            before = len(transport.calls)
            ok, code = await _code(dispatcher, "midas_query",
                                   {"target": "node", "action": "list", "client_id": 1},
                                   token=tokens["eng1"])
            assert ok is False and code == "PERMISSION_DENIED", (ok, code)

            # an unknown instance gives the SAME refusal, so the seam never
            # confirms that another tenant's registration exists
            ok, code = await _code(dispatcher, "midas_query",
                                   {"target": "node", "action": "list", "client_id": 999},
                                   token=tokens["eng1"])
            assert ok is False and code == "PERMISSION_DENIED", (ok, code)

            # neither refusal issued a request — the scope check is local
            assert len(transport.calls) == before, transport.calls[before:]
        finally:
            await adapter.aclose()

    _run(body())


def test_live_token_ttl_comes_from_security_configs(tmp_path) -> None:
    """裁决 C-9: ``expires_in`` derives from ``session_timeout_minutes``."""

    async def body():
        factory = _seed(tmp_path)
        service = AuthService(session_factory=factory)
        result = await service.login("eng1", "Eng1!Passw0rd")
        # the bootstrap seeds security_configs, whose default is 30 minutes
        assert result.expires_in == 30 * 60, result.expires_in
        assert result.token_type.lower() == "bearer"

    _run(body())
