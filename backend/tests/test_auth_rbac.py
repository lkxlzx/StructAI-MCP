"""Offline authentication + RBAC tests — 总纲 §4.4.1 / §4.8, 裁决 C-9 / C-13,
《MIDAS API 对接规范》§2.5.4 item 5, v1.2 §38.

Plain ``pytest`` only: the async entry points are driven with ``asyncio.run`` so
the suite needs no ``pytest-asyncio`` configuration (the same convention as
``tests/test_mcp_layer.py`` and ``tests/test_task_persistence.py``).

Everything runs against a **real SQLite file in ``tmp_path``**: no live MIDAS, no
network, and no process-wide engine — the ``sessionmaker`` is built per test and
handed to :class:`~app.services.auth_service.AuthService`, exactly as
``SqlAlchemyTaskStore`` is handed one in ``test_task_persistence.py``.

What is proven, and against which rule:

====================================================================  ==============================
claim                                                                 依据
====================================================================  ==============================
login success / wrong password / unknown / disabled / locked           总纲 §4.4.1, §4.2.5
``expires_in`` == ``session_timeout_minutes × 60``                     总纲 裁决 C-9
expired token -> ``AUTH_EXPIRED``, revoked -> ``AUTH_INVALID``         总纲 §4.4.1
``permissions_for`` resolves user→role→permission in the database      总纲 §4.8.2 / §4.8.3
the authorizer allows / refuses with the closed-set codes              v1.2 §38
``SUPER_ADMIN_ONLY_PERMISSIONS`` only for ``super_admin``                总纲 §4.8.4
instance data scope (private / department / public)                    对接规范 §2.5.4 item 5
``users.department`` is the principal side of that rule                总纲 §4.2.5
the scope filter invents no permission code                            总纲 §4.8.2（封闭集合）
the missing-department refusal names the reason in ``details``         总纲 §4.4.1 + §4.2.5
the ``users.department`` catch-up step is idempotent and backfills     总纲 §4.2.5
``failed_attempts`` increments, locks, and resets on success           总纲 §4.2.5
the token is never stored in plaintext                                 §4.7.1 spirit / sessions DDL
bootstrap admin is created once, never resets a password               users 表为空才创建
====================================================================  ==============================
"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import pytest
import shutil

from sqlalchemy import create_engine, event, func, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  (registers all 49 tables on Base.metadata)
from app.adapters.errors import AdapterError
from app.adapters.registry import AdapterRegistry
from app.core.config import get_settings
from app.core.constants import (
    HIGH_RISK_PERMISSIONS,
    SUPER_ADMIN_ONLY_PERMISSIONS,
    PERMISSION_CODES,
    ROLE_PERMISSION_MAP,
    UserStatus,
    expand_permission_patterns,
)
from app.core.errors import ErrorCode
from app.db.base import Base, session_scope_for
from app.mcp.auth import InstanceScope, make_authorizer, scope_allows
from app.mcp.capabilities import required_permission
from app.mcp.capability import CapabilityResolver
from app.mcp.context import AuthRequest
from app.mcp.dispatcher import ToolDispatcher
from app.models.identity import (
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
    UserSession,
)
from app.models.midas import Adapter, MidasClient
from app.models.settings import SecurityConfig
from app.services.auth_service import (
    BOOTSTRAP_PASSWORD_MARKER,
    DEFAULT_SESSION_TIMEOUT_MINUTES,
    AuthService,
    Principal,
    decode_token,
    ensure_bootstrap_admin,
    hash_password,
    issue_token,
    seed_rbac,
    signing_key,
    verify_password,
)
from app.services.task_service import TaskService

#: The master key every test uses.  ``STRUCTAI_MASTER_KEY`` is unset in CI, and
#: :func:`signing_key` must fail loudly in that case (asserted below), so the
#: fixture supplies one explicitly.
MASTER_KEY = "unit-test-master-key-please-change-0123456789"

#: A password that satisfies every documented complexity level.
PASSWORD = "Adm1n-Passw0rd!"


def run(coro: Any) -> Any:
    """Drive one coroutine to completion (no pytest-asyncio dependency)."""
    return asyncio.run(coro)


def as_utc(value: datetime | None) -> datetime | None:
    """Re-attach UTC to a naive value read back from SQLite (总纲 §4.5.1)."""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class FakeClock:
    """Injectable clock so lock windows and TTLs need no ``sleep``."""

    def __init__(self, start: datetime | None = None) -> None:
        self.moment: datetime = start or datetime.now(timezone.utc)

    def __call__(self) -> datetime:
        return self.moment

    def advance(self, **kwargs: float) -> datetime:
        self.moment = self.moment + timedelta(**kwargs)
        return self.moment


# ---------------------------------------------------------------------------
# fixtures — a real SQLite file, per test
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


@pytest.fixture()
def db_path(tmp_path: Path, schema_template: Path) -> Path:
    """A pristine copy of the empty schema, per test.

    ``schema_template`` is session-scoped (see ``tests/conftest.py``): the schema
    is built once and copied, because ``create_all()`` per test cost ~2 s and
    dominated the whole suite's runtime.
    """
    target = tmp_path / "structai_auth.db"
    shutil.copyfile(schema_template, target)
    return target


@pytest.fixture()
def factory(db_path: Path) -> Callable[[], Session]:
    """A sync ``sessionmaker`` over this test's own database copy."""
    engine: Engine = create_engine(
        f"sqlite:///{db_path}",
        future=True,
        # ``asyncio.to_thread`` may hand a pooled connection to a different
        # worker thread than the one that opened it — the reason
        # ``app.db.session`` sets this too.
        connect_args={"check_same_thread": False},
    )
    event.listen(engine, "connect", _enable_foreign_keys)
    return sessionmaker(
        bind=engine, class_=Session, autoflush=False, expire_on_commit=False
    )


@pytest.fixture()
def service(factory: Callable[[], Session]) -> AuthService:
    """The service under test, pointed at the test database."""
    return AuthService(session_factory=factory)


@pytest.fixture()
def seeded(factory: Callable[[], Session]) -> Callable[[], Session]:
    """The test database with the RBAC seed applied (34 / 4 / 65)."""
    seed_rbac(factory)
    return factory


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def add_user(
    factory: Callable[[], Session],
    username: str,
    *,
    password: str = PASSWORD,
    roles: tuple[str, ...] = ("visitor",),
    status: str = UserStatus.ENABLED.value,
    deleted: bool = False,
    department: str | None = None,
) -> int:
    """Insert one ``users`` row (plus its ``user_roles`` links) and return its id."""
    with session_scope_for(factory) as session:
        user = User(
            username=username,
            name=username,
            password_hash=hash_password(password),
            status=status,
            is_online=0,
            # 总纲 §4.2.5 — the single department this user belongs to.  ``None``
            # means "unassigned", which is a real state and not "any department".
            department=department,
        )
        if deleted:
            user.deleted_at = datetime.now(timezone.utc)
        session.add(user)
        session.flush()
        for code in roles:
            role = session.scalar(select(Role).where(Role.code == code))
            assert role is not None, f"role {code!r} is not seeded"
            session.add(UserRole(user_id=int(user.id), role_id=int(role.id)))
        return int(user.id)


def set_policy(factory: Callable[[], Session], **values: Any) -> None:
    """Write the ``security_configs`` singleton (creating it when absent)."""
    with session_scope_for(factory) as session:
        row = session.get(SecurityConfig, 1)
        if row is None:
            row = SecurityConfig(id=1)
            session.add(row)
        for key, value in values.items():
            setattr(row, key, value)


def add_instance(
    factory: Callable[[], Session],
    *,
    owner_id: int | None,
    visibility: str,
    department: str | None = None,
    name: str = "instance",
) -> int:
    """Insert one ``midas_clients`` row (with its ``adapters`` FK) and return its id."""
    with session_scope_for(factory) as session:
        adapter = session.scalar(select(Adapter).where(Adapter.code == "midas_gen"))
        if adapter is None:
            adapter = Adapter(
                code="midas_gen",
                name="MIDAS Gen",
                software="midas_gen",
                implementation="app.adapters.midas_gen.adapter.MidasNxAdapter",
            )
            session.add(adapter)
            session.flush()
        row = MidasClient(
            name=name,
            owner_id=owner_id,
            department=department,
            visibility=visibility,
            software="midas_gen",
            adapter_code="midas_gen",
            api_url="https://example.invalid/gen",
        )
        session.add(row)
        session.flush()
        return int(row.id)


def grant(factory: Callable[[], Session], role_code: str, permission_code: str) -> None:
    """Insert one ``role_permissions`` link (used to simulate a rogue grant)."""
    with session_scope_for(factory) as session:
        role = session.scalar(select(Role).where(Role.code == role_code))
        permission = session.scalar(
            select(Permission).where(Permission.code == permission_code)
        )
        assert role is not None and permission is not None
        key = (int(role.id), int(permission.id))
        existing = session.scalar(
            select(RolePermission).where(
                RolePermission.role_id == key[0],
                RolePermission.permission_id == key[1],
            )
        )
        if existing is None:
            session.add(RolePermission(role_id=key[0], permission_id=key[1]))


def principal_of(
    *,
    user_id: int = 1,
    department: str | None = None,
    permissions: tuple[str, ...] = ("tool:execute",),
) -> Principal:
    """A hand-built principal, for the pure scope predicate."""
    return Principal(
        user_id=user_id,
        username=f"user{user_id}",
        roles=("engineer",),
        permissions=frozenset(permissions),
        department=department,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )


def request_of(
    *,
    permission: str = "model:read",
    arguments: dict[str, Any] | None = None,
    principal: Any = None,
    tool: str = "midas_query",
    action: str = "list",
    resource: str | None = "node",
) -> AuthRequest:
    """One :class:`AuthRequest` exactly as the dispatcher builds it (v1.2 §38)."""
    return AuthRequest(
        request_id="req_20260925_000001",
        tool=tool,
        action=action,
        resource=resource,
        permission=permission,
        arguments=arguments or {},
        principal=principal,
    )


def error_code(excinfo: Any) -> str:
    """The 总纲 §4.4 code of a raised :class:`AdapterError`.

    Annotated ``Any`` on purpose: ``pytest.ExceptionInfo`` is only subscriptable
    from pytest 7 on, and this module has no ``from __future__ import
    annotations``, so a subscripted annotation would be evaluated at import time.
    """
    return str(excinfo.value.code)


# ===========================================================================
# 1. password wrappers and the derived signing key
# ===========================================================================
def test_password_wrappers_delegate_to_core_crypto() -> None:
    """``hash_password`` / ``verify_password`` are the only hashing entry points."""
    hashed = hash_password(PASSWORD)
    assert hashed != PASSWORD
    assert hashed.startswith("pbkdf2_sha256$")
    assert verify_password(PASSWORD, hashed) is True
    assert verify_password("wrong", hashed) is False
    assert verify_password(PASSWORD, None) is False


def test_signing_key_is_derived_and_fails_loudly_without_the_master_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """总纲 §4.7.1 — no hard-coded secret; an unset master key is a hard error."""
    key = signing_key()
    assert isinstance(key, bytes) and len(key) == 32
    assert key != MASTER_KEY.encode("utf-8")

    monkeypatch.setattr(get_settings(), "structai_master_key", None)
    with pytest.raises(RuntimeError):
        signing_key()
    with pytest.raises(RuntimeError):
        issue_token(
            user_id=1, username="a", session_id="s", expires_in=60
        )


def test_signing_key_is_labeled_not_a_bare_hash_of_the_master_key() -> None:
    """Domain separation: the JWT key is derived with its own label (总纲 §4.7.1)."""
    import hashlib

    assert signing_key() != hashlib.sha256(MASTER_KEY.encode("utf-8")).digest()
    assert signing_key() == signing_key()  # deterministic


# ===========================================================================
# 2. seeding from app.core.constants (002_seed.sql may never have run)
# ===========================================================================
def test_seed_rbac_matches_the_documented_counts(factory: Callable[[], Session]) -> None:
    """总纲 §4.8.2/§4.8.3 — 34 permissions, 4 roles, 65 links (002_seed.sql §1–3)."""
    created = seed_rbac(factory)
    assert created["permissions"] == 34
    assert created["roles"] == 4
    assert created["role_permissions"] == 65
    assert created["security_configs"] == 1

    with session_scope_for(factory) as session:
        assert session.scalar(select(func.count()).select_from(Permission)) == 34
        assert session.scalar(select(func.count()).select_from(Role)) == 4
        assert session.scalar(select(func.count()).select_from(RolePermission)) == 65
        codes = set(session.scalars(select(Permission.code)).all())
    assert codes == set(PERMISSION_CODES)


def test_seed_rbac_is_idempotent(factory: Callable[[], Session]) -> None:
    """Running it twice must add nothing (startup may call it every boot)."""
    seed_rbac(factory)
    again = seed_rbac(factory)
    assert again == {
        "permissions": 0,
        "roles": 0,
        "role_permissions": 0,
        "security_configs": 0,
    }


def test_seed_rbac_expands_the_role_patterns_of_the_master_spec(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """总纲 §4.8.3 — each role's grants are the §4.8.3 patterns, expanded."""
    for role, patterns in ROLE_PERMISSION_MAP.items():
        user_id = add_user(seeded, f"seed_{role}", roles=(role,))
        expected = set(expand_permission_patterns(patterns, PERMISSION_CODES))
        if role != "super_admin":
            # 总纲 §4.8.4 rows 1–3: these three are super_admin only, so they are
            # filtered out of every other role's resolved set.  ``assistant:execute``
            # is deliberately NOT filtered — §4.8.4 gives it to engineer and above.
            expected -= set(SUPER_ADMIN_ONLY_PERMISSIONS)
        assert service.permissions_for_now(user_id) == expected


# ===========================================================================
# 3. login
# ===========================================================================
def test_login_success_issues_a_token_and_a_session_row(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    user_id = add_user(seeded, "alice", roles=("visitor",))
    result = run(service.login("alice", PASSWORD, ip_address="10.0.0.9"))

    assert result.token.count(".") == 2
    assert result.token_type == "Bearer"
    assert result.principal.user_id == user_id
    assert result.principal.username == "alice"
    assert result.principal.roles == ("visitor",)
    assert result.principal.permissions == set(
        expand_permission_patterns(ROLE_PERMISSION_MAP["visitor"], PERMISSION_CODES)
    )
    # The token's expiry is carried on the principal (v1.2 §38).
    assert result.principal.expires_at == result.expires_at

    with session_scope_for(seeded) as session:
        row = session.scalar(
            select(UserSession).where(UserSession.session_id == result.session_id)
        )
        assert row is not None
        assert int(row.user_id) == user_id
        assert as_utc(row.expires_at) == result.expires_at
        assert row.revoked_at is None
        user = session.get(User, user_id)
        assert user is not None
        assert user.is_online == 1
        assert user.last_login_ip == "10.0.0.9"
        assert as_utc(user.last_login_at) is not None


def test_login_unknown_user_is_auth_invalid(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    with pytest.raises(AdapterError) as excinfo:
        run(service.login("nobody", PASSWORD))
    assert error_code(excinfo) == ErrorCode.AUTH_INVALID.value
    with session_scope_for(seeded) as session:
        assert session.scalar(select(func.count()).select_from(UserSession)) == 0


def test_login_wrong_password_is_auth_invalid_and_counts_the_failure(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    user_id = add_user(seeded, "alice")
    with pytest.raises(AdapterError) as excinfo:
        run(service.login("alice", "not-the-password"))
    assert error_code(excinfo) == ErrorCode.AUTH_INVALID.value
    assert excinfo.value.details["failed_attempts"] == 1
    with session_scope_for(seeded) as session:
        user = session.get(User, user_id)
        assert user is not None and user.failed_attempts == 1
        assert session.scalar(select(func.count()).select_from(UserSession)) == 0


def test_login_disabled_account_is_auth_invalid(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    add_user(seeded, "alice", status=UserStatus.DISABLED.value)
    with pytest.raises(AdapterError) as excinfo:
        run(service.login("alice", PASSWORD))
    assert error_code(excinfo) == ErrorCode.AUTH_INVALID.value
    assert excinfo.value.details["reason"] == "account_disabled"


def test_login_soft_deleted_account_is_auth_invalid(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """A soft-deleted user (``users.deleted_at``) is treated like a disabled one."""
    add_user(seeded, "alice", deleted=True)
    with pytest.raises(AdapterError) as excinfo:
        run(service.login("alice", PASSWORD))
    assert error_code(excinfo) == ErrorCode.AUTH_INVALID.value
    assert excinfo.value.details["reason"] == "account_deleted"


def test_login_locked_account_is_rate_limited(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """总纲 §4.2.5 ``users.status='locked'`` — refused with the closed-set 429."""
    add_user(seeded, "alice", status=UserStatus.LOCKED.value)
    with pytest.raises(AdapterError) as excinfo:
        run(service.login("alice", PASSWORD))
    assert error_code(excinfo) == ErrorCode.RATE_LIMITED.value
    assert excinfo.value.details["reason"] == "account_locked"


def test_failed_attempts_lock_the_account_and_the_correct_password_still_fails(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """总纲 §4.2.5 + security_configs.max_login_attempts / lock_minutes."""
    set_policy(seeded, max_login_attempts=3, lock_minutes=15)
    user_id = add_user(seeded, "alice")

    for attempt in (1, 2):
        with pytest.raises(AdapterError) as excinfo:
            run(service.login("alice", "wrong"))
        assert error_code(excinfo) == ErrorCode.AUTH_INVALID.value
        assert excinfo.value.details["failed_attempts"] == attempt

    with pytest.raises(AdapterError) as excinfo:
        run(service.login("alice", "wrong"))
    assert error_code(excinfo) == ErrorCode.RATE_LIMITED.value
    assert excinfo.value.details["failed_attempts"] == 3

    with session_scope_for(seeded) as session:
        user = session.get(User, user_id)
        assert user is not None
        assert user.failed_attempts == 3
        assert user.status == UserStatus.LOCKED.value
        deadline = as_utc(user.locked_until)
        assert deadline is not None
        assert deadline > datetime.now(timezone.utc)

    # The lock is checked *before* the password, so the right password is refused.
    with pytest.raises(AdapterError) as excinfo:
        run(service.login("alice", PASSWORD))
    assert error_code(excinfo) == ErrorCode.RATE_LIMITED.value


def test_successful_login_resets_failed_attempts(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    user_id = add_user(seeded, "alice")
    for _ in range(2):
        with pytest.raises(AdapterError):
            run(service.login("alice", "wrong"))

    result = run(service.login("alice", PASSWORD))
    assert result.principal.user_id == user_id
    with session_scope_for(seeded) as session:
        user = session.get(User, user_id)
        assert user is not None
        assert user.failed_attempts == 0
        assert user.locked_until is None
        assert user.status == UserStatus.ENABLED.value


def test_an_expired_automatic_lock_lets_the_user_back_in(
    seeded: Callable[[], Session],
) -> None:
    """An automatic lock carries ``locked_until`` and therefore expires."""
    clock = FakeClock()
    service = AuthService(session_factory=seeded, clock=clock)
    set_policy(seeded, max_login_attempts=1, lock_minutes=10)
    user_id = add_user(seeded, "alice")

    with pytest.raises(AdapterError) as excinfo:
        run(service.login("alice", "wrong"))
    assert error_code(excinfo) == ErrorCode.RATE_LIMITED.value

    clock.advance(minutes=11)
    result = run(service.login("alice", PASSWORD))
    assert result.principal.username == "alice"
    with session_scope_for(seeded) as session:
        user = session.get(User, user_id)
        assert user is not None
        assert user.status == UserStatus.ENABLED.value
        assert user.locked_until is None
        assert user.failed_attempts == 0


def test_an_administrative_lock_never_expires(
    seeded: Callable[[], Session],
) -> None:
    """``status='locked'`` with no ``locked_until`` stays until an admin clears it."""
    clock = FakeClock()
    service = AuthService(session_factory=seeded, clock=clock)
    add_user(seeded, "alice", status=UserStatus.LOCKED.value)

    clock.advance(days=365)
    with pytest.raises(AdapterError) as excinfo:
        run(service.login("alice", PASSWORD))
    assert error_code(excinfo) == ErrorCode.RATE_LIMITED.value
    assert excinfo.value.details["locked_until"] is None


# ===========================================================================
# 4. the token TTL — 总纲 裁决 C-9
# ===========================================================================
def test_expires_in_is_session_timeout_minutes_times_sixty(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """裁决 C-9: ``expires_in = security_configs.session_timeout_minutes × 60``."""
    set_policy(seeded, session_timeout_minutes=45)
    add_user(seeded, "alice")
    result = run(service.login("alice", PASSWORD))

    assert result.expires_in == 45 * 60 == 2700
    claims = decode_token(result.token)
    assert claims["exp"] - claims["iat"] == 2700
    assert result.expires_at - result.principal.expires_at == timedelta(0)

    with session_scope_for(seeded) as session:
        row = session.scalar(
            select(UserSession).where(UserSession.session_id == result.session_id)
        )
        assert row is not None
        # sessions.expires_at is derived from the same number as the JWT exp.
        assert as_utc(row.expires_at) == result.expires_at


def test_expires_in_defaults_when_the_policy_row_is_absent(
    factory: Callable[[], Session], service: AuthService
) -> None:
    """No ``security_configs`` row -> 裁决 C-9's documented 30-minute default."""
    add_user(factory, "alice", roles=())
    result = run(service.login("alice", PASSWORD))
    assert result.expires_in == DEFAULT_SESSION_TIMEOUT_MINUTES * 60 == 1800


def test_a_non_positive_ttl_falls_back_to_the_default(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """A 0-minute row must not mint a dead-on-arrival token."""
    set_policy(seeded, session_timeout_minutes=0)
    add_user(seeded, "alice")
    assert run(service.login("alice", PASSWORD)).expires_in == 1800


# ===========================================================================
# 5. token verification: expired / tampered / revoked / unknown
# ===========================================================================
def test_expired_token_is_auth_expired(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    add_user(seeded, "alice")
    token = issue_token(
        user_id=1, username="alice", session_id="s", expires_in=-60
    )
    with pytest.raises(AdapterError) as excinfo:
        service.verify_token_now(token)
    assert error_code(excinfo) == ErrorCode.AUTH_EXPIRED.value
    assert excinfo.value.details["reason"] == "token_expired"


def test_tampered_signature_is_auth_invalid(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    add_user(seeded, "alice")
    result = run(service.login("alice", PASSWORD))
    header, payload, signature = result.token.split(".")
    flipped = "A" if signature[-1] != "A" else "B"
    tampered = f"{header}.{payload}.{signature[:-1]}{flipped}"

    with pytest.raises(AdapterError) as excinfo:
        service.verify_token_now(tampered)
    assert error_code(excinfo) == ErrorCode.AUTH_INVALID.value
    assert excinfo.value.details["reason"] == "invalid_token"


def test_a_token_signed_with_another_key_is_auth_invalid(
    seeded: Callable[[], Session],
    service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A different master key means a different signing key (总纲 §4.7.1)."""
    add_user(seeded, "alice")
    result = run(service.login("alice", PASSWORD))
    monkeypatch.setattr(get_settings(), "structai_master_key", "another-master-key")
    with pytest.raises(AdapterError) as excinfo:
        service.verify_token_now(result.token)
    assert error_code(excinfo) == ErrorCode.AUTH_INVALID.value


def test_logout_revokes_the_token(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    user_id = add_user(seeded, "alice")
    result = run(service.login("alice", PASSWORD))
    assert run(service.verify_token(result.token)).user_id == user_id

    assert run(service.logout(result.token)) is True

    with pytest.raises(AdapterError) as excinfo:
        run(service.verify_token(result.token))
    # Revoked, not expired: 总纲 §4.4.1 AUTH_INVALID.
    assert error_code(excinfo) == ErrorCode.AUTH_INVALID.value
    assert excinfo.value.details["reason"] == "session_revoked"

    with session_scope_for(seeded) as session:
        row = session.scalar(
            select(UserSession).where(UserSession.session_id == result.session_id)
        )
        assert row is not None and row.revoked_at is not None
        user = session.get(User, user_id)
        assert user is not None and user.is_online == 0


def test_logout_is_idempotent_and_rejects_a_forged_token(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    add_user(seeded, "alice")
    result = run(service.login("alice", PASSWORD))
    assert run(service.logout(result.token)) is True
    assert run(service.logout(result.token)) is True
    header, payload, signature = result.token.split(".")
    flipped = "A" if signature[-1] != "A" else "B"
    with pytest.raises(AdapterError) as excinfo:
        service.logout_now(f"{header}.{payload}.{signature[:-1]}{flipped}")
    assert error_code(excinfo) == ErrorCode.AUTH_INVALID.value


def test_an_unknown_session_is_auth_invalid(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """A well-signed token whose ``jti`` has no row was never issued by us."""
    add_user(seeded, "alice")
    token = issue_token(
        user_id=1, username="alice", session_id="never-stored", expires_in=1800
    )
    with pytest.raises(AdapterError) as excinfo:
        service.verify_token_now(token)
    assert error_code(excinfo) == ErrorCode.AUTH_INVALID.value
    assert excinfo.value.details["reason"] == "unknown_session"


def test_expired_session_row_is_auth_expired(
    seeded: Callable[[], Session],
) -> None:
    """The ``sessions.expires_at`` half of 裁决 C-9 is enforced too."""
    clock = FakeClock()
    service = AuthService(session_factory=seeded, clock=clock)
    add_user(seeded, "alice")
    result = run(service.login("alice", PASSWORD))
    assert run(service.verify_token(result.token)).username == "alice"

    clock.advance(minutes=DEFAULT_SESSION_TIMEOUT_MINUTES + 1)
    with pytest.raises(AdapterError) as excinfo:
        run(service.verify_token(result.token))
    assert error_code(excinfo) == ErrorCode.AUTH_EXPIRED.value
    assert excinfo.value.details["reason"] == "session_expired"


def test_a_token_of_a_disabled_account_is_auth_invalid(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    user_id = add_user(seeded, "alice")
    result = run(service.login("alice", PASSWORD))
    with session_scope_for(seeded) as session:
        user = session.get(User, user_id)
        assert user is not None
        user.status = UserStatus.DISABLED.value

    with pytest.raises(AdapterError) as excinfo:
        service.verify_token_now(result.token)
    assert error_code(excinfo) == ErrorCode.AUTH_INVALID.value
    assert excinfo.value.details["reason"] == "account_disabled"


def test_a_token_of_a_locked_account_is_rate_limited(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    user_id = add_user(seeded, "alice")
    result = run(service.login("alice", PASSWORD))
    with session_scope_for(seeded) as session:
        user = session.get(User, user_id)
        assert user is not None
        user.status = UserStatus.LOCKED.value
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=5)

    with pytest.raises(AdapterError) as excinfo:
        service.verify_token_now(result.token)
    assert error_code(excinfo) == ErrorCode.RATE_LIMITED.value


def test_verify_token_reads_roles_and_permissions_from_the_database(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """Roles are resolved per call, so a grant takes effect without a new token."""
    user_id = add_user(seeded, "alice", roles=("visitor",))
    result = run(service.login("alice", PASSWORD))
    assert run(service.verify_token(result.token)).permissions == set(
        expand_permission_patterns(ROLE_PERMISSION_MAP["visitor"], PERMISSION_CODES)
    )

    with session_scope_for(seeded) as session:
        role = session.scalar(select(Role).where(Role.code == "analyst"))
        assert role is not None
        session.add(UserRole(user_id=user_id, role_id=int(role.id)))

    refreshed = run(service.verify_token(result.token))
    assert set(refreshed.roles) == {"visitor", "analyst"}
    assert "assistant:chat" in refreshed.permissions


# ===========================================================================
# 6. the token is never stored in plaintext
# ===========================================================================
def test_the_token_is_not_stored_in_plaintext(
    seeded: Callable[[], Session], service: AuthService, db_path: Path
) -> None:
    """``sessions.token_hash`` holds a one-way hash; the token itself is absent."""
    add_user(seeded, "alice")
    result = run(service.login("alice", PASSWORD))

    with session_scope_for(seeded) as session:
        row = session.scalar(select(UserSession))
        assert row is not None
        assert row.token_hash != result.token
        assert result.token not in row.token_hash
        assert row.token_hash.startswith("pbkdf2_sha256$")
        # The stored hash still verifies against the token.
        assert verify_password(result.token, row.token_hash) is True

    # The whole database file, not just the row: the token appears nowhere.
    assert result.token.encode("utf-8") not in db_path.read_bytes()


# ===========================================================================
# 7. permissions_for — 总纲 §4.8.2 / §4.8.3 / §4.8.4
# ===========================================================================
@pytest.mark.parametrize(
    "role,expected_count",
    [("super_admin", 34), ("engineer", 21), ("analyst", 6), ("visitor", 4)],
)
def test_permissions_for_resolves_each_seeded_role(
    seeded: Callable[[], Session],
    service: AuthService,
    role: str,
    expected_count: int,
) -> None:
    """user_roles -> role_permissions -> permissions.code, straight from the DB."""
    user_id = add_user(seeded, f"user_{role}", roles=(role,))
    codes = service.permissions_for_now(user_id)

    expected = set(expand_permission_patterns(ROLE_PERMISSION_MAP[role], PERMISSION_CODES))
    if role != "super_admin":
        # 总纲 §4.8.4: the three super-admin-only codes are dropped for every other
        # role.  ``assistant:execute`` survives for engineer — its ``assistant:*``
        # pattern matches it and §4.8.4 grants it to engineer and above.
        expected -= set(SUPER_ADMIN_ONLY_PERMISSIONS)
    assert codes == expected
    assert len(codes) == expected_count
    assert codes <= set(PERMISSION_CODES)


def test_permissions_for_is_empty_without_roles(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    user_id = add_user(seeded, "no_roles", roles=())
    assert service.permissions_for_now(user_id) == set()
    assert service.roles_for_now(user_id) == []


def test_permissions_for_drops_codes_outside_the_closed_set(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """总纲 §4.8.2 is closed: a ``permissions`` row outside it grants nothing."""
    user_id = add_user(seeded, "alice", roles=("visitor",))
    with session_scope_for(seeded) as session:
        session.add(
            Permission(
                code="client:read", name="读取客户端", module="client", action="read"
            )
        )
    grant(seeded, "visitor", "client:read")

    codes = service.permissions_for_now(user_id)
    assert "client:read" not in codes
    assert codes == set(
        expand_permission_patterns(ROLE_PERMISSION_MAP["visitor"], PERMISSION_CODES)
    )


def test_high_risk_permissions_are_reachable_only_by_super_admin(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """总纲 §4.8.4 — enforced while reading, not merely trusted to the seed."""
    ids = {
        role: add_user(seeded, f"hr_{role}", roles=(role,))
        for role in ("super_admin", "engineer", "analyst", "visitor")
    }
    resolved = {role: service.permissions_for_now(uid) for role, uid in ids.items()}

    # The two axes relate as a strict subset: super-admin-only ⊂ high-risk.
    assert set(SUPER_ADMIN_ONLY_PERMISSIONS) < set(HIGH_RISK_PERMISSIONS)

    # 总纲 §4.8.4 rows 1–3 — refused to every other role.
    for code in SUPER_ADMIN_ONLY_PERMISSIONS:
        assert code in resolved["super_admin"], code
        for role in ("engineer", "analyst", "visitor"):
            assert code not in resolved[role], (role, code)

    # …but ``assistant:execute`` is NOT super-admin-only.  §4.8.4 grants it to
    # ``engineer`` and above, gated instead by the §5 confirmation flow, so an
    # engineer MUST hold it — filtering on the broader HIGH_RISK_PERMISSIONS set
    # silently denied them a permission the spec gives them.
    assert "assistant:execute" in resolved["engineer"]
    assert "assistant:execute" not in resolved["analyst"]
    assert "assistant:execute" not in resolved["visitor"]

    # A rogue ``role_permissions`` row cannot hand a super-admin-only code to a
    # non-super_admin role: the filter runs on every read.
    for code in SUPER_ADMIN_ONLY_PERMISSIONS:
        grant(seeded, "engineer", code)
    after = service.permissions_for_now(ids["engineer"])
    assert after == resolved["engineer"]
    assert not (after & set(SUPER_ADMIN_ONLY_PERMISSIONS))


def test_every_seeded_role_resolves_through_the_mcp_permission_mapping(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """The codes ``required_permission`` returns are reachable by the right roles."""
    engineer = add_user(seeded, "eng", roles=("engineer",))
    visitor = add_user(seeded, "vis", roles=("visitor",))
    engineer_codes = service.permissions_for_now(engineer)
    visitor_codes = service.permissions_for_now(visitor)

    assert required_permission("midas_query", "list") == "model:read"
    assert required_permission("midas_model", "delete") == "model:delete"
    assert required_permission("midas_execute", "calculate") == "tool:execute"
    assert required_permission("midas_task", "cancel") == "task:cancel"

    assert "model:read" in visitor_codes
    assert "model:delete" in engineer_codes and "model:delete" not in visitor_codes
    assert "tool:execute" in engineer_codes and "tool:execute" not in visitor_codes
    assert "task:cancel" in engineer_codes and "task:cancel" not in visitor_codes


# ===========================================================================
# 8. the authorizer — the seam itself (v1.2 §38)
# ===========================================================================
def test_authorizer_allows_a_permitted_call(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    add_user(seeded, "alice", roles=("visitor",))
    token = run(service.login("alice", PASSWORD)).token
    authorizer = make_authorizer(service)
    assert run(authorizer(request_of(permission="model:read", principal=token))) is None


def test_authorizer_refuses_a_missing_permission_with_permission_denied(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    add_user(seeded, "alice", roles=("visitor",))
    token = run(service.login("alice", PASSWORD)).token
    authorizer = make_authorizer(service)

    with pytest.raises(AdapterError) as excinfo:
        run(
            authorizer(
                request_of(
                    permission="tool:execute",
                    principal=token,
                    tool="midas_execute",
                    action="calculate",
                )
            )
        )
    assert error_code(excinfo) == ErrorCode.PERMISSION_DENIED.value
    assert excinfo.value.details["reason"] == "missing_permission"
    assert excinfo.value.details["permission"] == "tool:execute"


def test_authorizer_requires_a_principal(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    authorizer = make_authorizer(service)
    with pytest.raises(AdapterError) as excinfo:
        run(authorizer(request_of(principal=None)))
    assert error_code(excinfo) == ErrorCode.AUTH_REQUIRED.value


def test_authorizer_refuses_a_bad_token(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    authorizer = make_authorizer(service)
    with pytest.raises(AdapterError) as excinfo:
        run(authorizer(request_of(principal="not-a-token")))
    assert error_code(excinfo) == ErrorCode.AUTH_INVALID.value


def test_authorizer_refuses_a_revoked_token(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    add_user(seeded, "alice")
    token = run(service.login("alice", PASSWORD)).token
    run(service.logout(token))
    authorizer = make_authorizer(service)
    with pytest.raises(AdapterError) as excinfo:
        run(authorizer(request_of(principal=token)))
    assert error_code(excinfo) == ErrorCode.AUTH_INVALID.value


def test_authorizer_accepts_an_already_resolved_principal(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    add_user(seeded, "alice", roles=("visitor",))
    principal = run(service.verify_token(run(service.login("alice", PASSWORD)).token))
    authorizer = make_authorizer(service)
    assert run(authorizer(request_of(permission="model:read", principal=principal))) is None


def test_authorizer_refuses_an_expired_resolved_principal(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    add_user(seeded, "alice", roles=("visitor",))
    expired = Principal(
        user_id=1,
        username="alice",
        roles=("visitor",),
        permissions=frozenset({"model:read"}),
        department=None,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    authorizer = make_authorizer(service)
    with pytest.raises(AdapterError) as excinfo:
        run(authorizer(request_of(principal=expired)))
    assert error_code(excinfo) == ErrorCode.AUTH_EXPIRED.value


def test_authorizer_uses_a_principal_resolver(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """A transport-level resolver can supply the ``Authorization`` header."""
    add_user(seeded, "alice", roles=("visitor",))
    token = run(service.login("alice", PASSWORD)).token

    def resolver(request: AuthRequest) -> Any:
        assert request.tool == "midas_query"
        return {"authorization": f"Bearer {token}"}

    authorizer = make_authorizer(service, principal_resolver=resolver)
    assert run(authorizer(request_of(permission="model:read", principal=None))) is None


def test_authorizer_accepts_an_async_principal_resolver(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    add_user(seeded, "alice", roles=("visitor",))
    token = run(service.login("alice", PASSWORD)).token

    async def resolver(request: AuthRequest) -> Any:
        return token

    authorizer = make_authorizer(service, principal_resolver=resolver)
    assert run(authorizer(request_of(permission="model:read", principal=None))) is None


def test_authorizer_refuses_a_permission_code_outside_the_closed_set(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """总纲 §4.8.2 is closed — an invented code is refused, never granted."""
    add_user(seeded, "root", roles=("super_admin",))
    token = run(service.login("root", PASSWORD)).token
    authorizer = make_authorizer(service)

    with pytest.raises(AdapterError) as excinfo:
        run(authorizer(request_of(permission="client:read", principal=token)))
    assert error_code(excinfo) == ErrorCode.PERMISSION_DENIED.value
    assert excinfo.value.details["reason"] == "unknown_permission_code"


def test_authorizer_is_disabled_when_api_auth_is_not_required(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """总纲 裁决 C-13: ``security_configs.api_auth_required = 0``."""
    set_policy(seeded, api_auth_required=0)
    authorizer = make_authorizer(service)
    assert run(authorizer(request_of(principal=None))) is None


def test_every_refusal_is_a_closed_set_error_code(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """总纲 §4.4 — the seam may not invent an error code."""
    add_user(seeded, "alice", roles=("visitor",))
    token = run(service.login("alice", PASSWORD)).token
    authorizer = make_authorizer(service)
    known = {member.value for member in ErrorCode}

    for request in (
        request_of(principal=None),
        request_of(principal="garbage"),
        request_of(principal=token, permission="tool:execute"),
        request_of(principal=token, permission="client:read"),
        request_of(principal=token, arguments={"client_id": 424242}),
    ):
        with pytest.raises(AdapterError) as excinfo:
            run(authorizer(request))
        assert error_code(excinfo) in known


# ===========================================================================
# 9. instance data scope — 对接规范 §2.5.4 item 5, no new permission code
# ===========================================================================
def test_scope_allows_private_only_for_the_owner() -> None:
    scope = InstanceScope(
        client_id=7, owner_id=1, visibility="private", department=None
    )
    assert scope_allows(scope, principal_of(user_id=1)) is True
    assert scope_allows(scope, principal_of(user_id=2)) is False
    # No owner at all: nobody, not even a super_admin, is "the owner".
    ownerless = InstanceScope(
        client_id=7, owner_id=None, visibility="private", department=None
    )
    assert scope_allows(ownerless, principal_of(user_id=1)) is False


def test_scope_allows_department_only_for_the_same_department() -> None:
    scope = InstanceScope(
        client_id=7, owner_id=1, visibility="department", department="结构一所"
    )
    assert scope_allows(scope, principal_of(department="结构一所")) is True
    assert scope_allows(scope, principal_of(department="结构二所")) is False
    # Unknown department on either side fails closed (对接规范 §2.5.4: 不得假定).
    assert scope_allows(scope, principal_of(department=None)) is False
    unlabelled = InstanceScope(
        client_id=7, owner_id=1, visibility="department", department=None
    )
    assert scope_allows(unlabelled, principal_of(department="结构一所")) is False


def test_scope_allows_public_for_anyone() -> None:
    scope = InstanceScope(client_id=7, owner_id=1, visibility="public", department=None)
    assert scope_allows(scope, principal_of(user_id=2, department=None)) is True
    assert scope_allows(scope, principal_of(user_id=99, department="任意")) is True


def test_scope_allows_refuses_an_unknown_visibility() -> None:
    """A corrupted ``visibility`` value must not become an allow."""
    scope = InstanceScope(client_id=7, owner_id=1, visibility="", department=None)
    assert scope_allows(scope, principal_of(user_id=1)) is False
    scope = InstanceScope(client_id=7, owner_id=1, visibility="team", department=None)
    assert scope_allows(scope, principal_of(user_id=1)) is False


def test_authorizer_enforces_the_instance_scope(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """private -> owner only; department -> same department; public -> anyone."""
    owner_id = add_user(seeded, "owner", roles=("engineer",))
    other_id = add_user(seeded, "other", roles=("engineer",))
    # 总纲 §4.2.5: department membership is the ``users.department`` column, not a
    # registration the member happens to own.  The old derivation read it off the
    # very ``midas_clients`` rows membership is supposed to grant access to —
    # circular, and it locked every ordinary member out of their own department's
    # instance (registered once, by an administrator).
    mate_id = add_user(seeded, "mate", roles=("engineer",), department="结构一所")
    admin_id = add_user(seeded, "admin", roles=("super_admin",))

    private_id = add_instance(seeded, owner_id=owner_id, visibility="private")
    public_id = add_instance(seeded, owner_id=owner_id, visibility="public")
    # Registered by the administrator, as a department instance is.
    department_id = add_instance(
        seeded, owner_id=admin_id, visibility="department", department="结构一所"
    )
    assert other_id != owner_id and admin_id not in (owner_id, mate_id)

    authorizer = make_authorizer(service)
    tokens = {
        name: run(service.login(name, PASSWORD)).token
        for name in ("owner", "other", "mate")
    }

    def call(token: str, client_id: int) -> Any:
        return run(
            authorizer(
                request_of(
                    permission=required_permission("midas_execute", "calculate"),
                    arguments={"client_id": client_id},
                    principal=token,
                    tool="midas_execute",
                    action="calculate",
                    resource="model",
                )
            )
        )

    # public: everyone who passed the permission check.
    assert call(tokens["owner"], public_id) is None
    assert call(tokens["other"], public_id) is None

    # private: the registering user only.
    assert call(tokens["owner"], private_id) is None
    with pytest.raises(AdapterError) as excinfo:
        call(tokens["other"], private_id)
    assert error_code(excinfo) == ErrorCode.PERMISSION_DENIED.value
    assert excinfo.value.details["reason"] == "instance_out_of_scope"

    # department: only the label on ``users.department`` decides.  ``mate``
    # matches and is allowed; ``owner`` and ``other`` have no department at all,
    # so they are refused (fail closed — 对接规范 §2.5.4 item 5: 不得假定).
    assert call(tokens["mate"], department_id) is None
    for name in ("owner", "other"):
        with pytest.raises(AdapterError) as excinfo:
            call(tokens[name], department_id)
        assert error_code(excinfo) == ErrorCode.PERMISSION_DENIED.value


# ===========================================================================
# 9b. users.department — the principal side of 对接规范 §2.5.4 item 5
#    (总纲 §4.2.5)
# ===========================================================================
def _call_instance(
    service: AuthService, token: Any, client_id: int
) -> Any:
    """Run one ``client_id``-carrying call through the authorizer."""
    return run(
        make_authorizer(service)(
            request_of(
                permission="tool:execute",
                arguments={"client_id": client_id},
                principal=token,
                tool="midas_execute",
                action="calculate",
            )
        )
    )


def test_a_member_may_use_the_departments_instance_registered_by_an_admin(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """总纲 §4.2.5 — the case that failed before the column existed.

    ``alice`` is an engineer with ``users.department='A'``.  The ``department='A'``
    instance was registered by the **administrator**, not by her.  The old
    derivation read her department off her own registrations, so she had none and
    this exact call was refused.
    """
    admin_id = add_user(seeded, "root", roles=("super_admin",))
    alice_id = add_user(seeded, "alice", roles=("engineer",), department="A")
    instance_id = add_instance(
        seeded, owner_id=admin_id, visibility="department", department="A"
    )

    principal = run(service.login("alice", PASSWORD)).principal
    assert principal.user_id == alice_id
    assert principal.department == "A"
    assert _call_instance(service, principal, instance_id) is None


def test_a_department_mismatch_is_refused(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """``department='A'`` may not use a ``department='B'`` instance."""
    admin_id = add_user(seeded, "root", roles=("super_admin",))
    add_user(seeded, "alice", roles=("engineer",), department="A")
    instance_id = add_instance(
        seeded, owner_id=admin_id, visibility="department", department="B"
    )

    token = run(service.login("alice", PASSWORD)).token
    with pytest.raises(AdapterError) as excinfo:
        _call_instance(service, token, instance_id)
    assert error_code(excinfo) == ErrorCode.PERMISSION_DENIED.value
    assert excinfo.value.details["reason"] == "instance_out_of_scope"
    assert excinfo.value.details["scope_department"] == "B"
    assert excinfo.value.details["principal_department"] == "A"


def test_an_unassigned_user_is_refused_and_the_refusal_names_the_reason(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """总纲 §4.2.5 — ``users.department IS NULL`` is a refusal, never a guess.

    The refusal keeps the closed-set ``PERMISSION_DENIED`` (总纲 §4.4.1) but the
    message and ``details`` say *why*: an unassigned principal cannot use a
    ``department``-scoped instance, and an administrator has to set the column.
    """
    admin_id = add_user(seeded, "root", roles=("super_admin",))
    add_user(seeded, "alice", roles=("engineer",))  # no department assigned
    instance_id = add_instance(
        seeded, owner_id=admin_id, visibility="department", department="A"
    )

    token = run(service.login("alice", PASSWORD)).token
    with pytest.raises(AdapterError) as excinfo:
        _call_instance(service, token, instance_id)

    assert error_code(excinfo) == ErrorCode.PERMISSION_DENIED.value
    details = excinfo.value.details
    assert details["reason"] == "department_unassigned"
    assert details["client_id"] == instance_id
    assert details["scope_department"] == "A"
    assert details["principal_department"] is None
    # ... and the message is actionable, not a bare denial.
    message = str(excinfo.value)
    assert "users.department" in message
    assert "未分配部门" in message or "没有分配部门" in message


def test_the_injected_department_resolver_wins_over_the_column(
    seeded: Callable[[], Session],
) -> None:
    """A deployment that keeps the label elsewhere is not overruled by the column."""
    add_user(seeded, "alice", roles=("engineer",), department="A")
    service = AuthService(
        session_factory=seeded, department_resolver=lambda user_id: "B"
    )
    assert run(service.login("alice", PASSWORD)).principal.department == "B"


def test_an_injected_resolver_returning_none_does_not_fall_back_to_the_column(
    seeded: Callable[[], Session],
) -> None:
    """The resolution order is fixed: an injected resolver's ``None`` is final.

    Falling through to ``users.department`` would be the second source of truth
    the column replaced, so a deployment that injects a resolver owns the answer
    entirely.
    """
    add_user(seeded, "alice", roles=("engineer",), department="A")
    service = AuthService(
        session_factory=seeded, department_resolver=lambda user_id: None
    )
    assert run(service.login("alice", PASSWORD)).principal.department is None


def test_private_and_public_instances_ignore_the_department_column(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """A department label neither grants nor revokes ``private`` / ``public``."""
    owner_id = add_user(seeded, "owner", roles=("engineer",), department="A")
    add_user(seeded, "other", roles=("engineer",), department="B")
    private_id = add_instance(seeded, owner_id=owner_id, visibility="private")
    public_id = add_instance(seeded, owner_id=owner_id, visibility="public")

    tokens = {
        name: run(service.login(name, PASSWORD)).token for name in ("owner", "other")
    }

    # public: usable by anyone who passed the permission check, label irrelevant.
    assert _call_instance(service, tokens["owner"], public_id) is None
    assert _call_instance(service, tokens["other"], public_id) is None

    # private: still the registering user only — "other" holds a department, and
    # that must not leak access to somebody else's private instance.
    assert _call_instance(service, tokens["owner"], private_id) is None
    with pytest.raises(AdapterError) as excinfo:
        _call_instance(service, tokens["other"], private_id)
    assert error_code(excinfo) == ErrorCode.PERMISSION_DENIED.value
    assert excinfo.value.details["reason"] == "instance_out_of_scope"


def test_users_department_reaches_the_principal_end_to_end(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """总纲 §4.2.5 — set the column, log in, read ``principal.department``."""
    assigned_id = add_user(
        seeded, "assigned", roles=("engineer",), department="结构一所"
    )
    add_user(seeded, "unassigned", roles=("engineer",))

    assigned = run(service.login("assigned", PASSWORD))
    assert assigned.principal.user_id == assigned_id
    assert assigned.principal.department == "结构一所"
    # Unassigned is ``None`` — a real state, and never "any department".
    assert run(service.login("unassigned", PASSWORD)).principal.department is None

    # ``verify_token`` re-reads the column, so an administrator's later
    # assignment takes effect on the next call without a re-login.
    with session_scope_for(seeded) as session:
        user = session.get(User, assigned_id)
        assert user is not None
        user.department = "结构二所"
    assert run(service.verify_token(assigned.token)).department == "结构二所"


def test_the_instance_scope_filter_invents_no_permission_code(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """对接规范 §2.5.4 item 5: a data-scope filter on the *existing* codes.

    The principal keeps every §4.8.2 code it had; the scope only narrows *which
    instance* it can reach, and the refusal reuses ``PERMISSION_DENIED``.
    """
    owner_id = add_user(seeded, "owner", roles=("engineer",))
    other_id = add_user(seeded, "other", roles=("engineer",))
    private_id = add_instance(seeded, owner_id=owner_id, visibility="private")

    before = service.permissions_for_now(other_id)
    authorizer = make_authorizer(service)
    token = run(service.login("other", PASSWORD)).token

    with pytest.raises(AdapterError) as excinfo:
        run(
            authorizer(
                request_of(
                    permission="tool:execute",
                    arguments={"client_id": private_id},
                    principal=token,
                    tool="midas_execute",
                    action="calculate",
                )
            )
        )
    # The refusal is the pre-existing §4.4.1 code, not a new one.
    assert error_code(excinfo) == ErrorCode.PERMISSION_DENIED.value
    assert error_code(excinfo) in {member.value for member in ErrorCode}
    # ... and the caller's permission set is untouched by the filter.
    assert service.permissions_for_now(other_id) == before
    assert "tool:execute" in before
    assert set(excinfo.value.details) >= {"client_id", "visibility", "owner_id"}
    # No code resembling a new instance permission exists anywhere.
    assert not [code for code in PERMISSION_CODES if "client" in code]


def test_an_unknown_client_id_is_refused_without_revealing_existence(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    add_user(seeded, "alice", roles=("engineer",))
    token = run(service.login("alice", PASSWORD)).token
    authorizer = make_authorizer(service)
    with pytest.raises(AdapterError) as excinfo:
        run(
            authorizer(
                request_of(
                    permission="tool:execute",
                    arguments={"client_id": 987654},
                    principal=token,
                )
            )
        )
    assert error_code(excinfo) == ErrorCode.PERMISSION_DENIED.value
    assert excinfo.value.details["reason"] == "unknown_instance"


def test_an_unparseable_client_id_is_left_to_the_schema_validator(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """``client_id`` is an integer in the schema; the seam does not guess."""
    add_user(seeded, "alice", roles=("engineer",))
    token = run(service.login("alice", PASSWORD)).token
    authorizer = make_authorizer(service)
    assert (
        run(
            authorizer(
                request_of(
                    permission="tool:execute",
                    arguments={"client_id": "not-an-int"},
                    principal=token,
                )
            )
        )
        is None
    )


def test_a_call_without_a_client_id_skips_the_scope_filter(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    add_user(seeded, "alice", roles=("engineer",))
    token = run(service.login("alice", PASSWORD)).token
    authorizer = make_authorizer(service)
    assert run(authorizer(request_of(permission="model:read", principal=token))) is None


# ===========================================================================
# 10. the dispatcher actually consults the authorizer (v1.2 §38)
# ===========================================================================
def _dispatcher(service: AuthService) -> ToolDispatcher:
    """A dispatcher with no adapters: ``midas_task`` is platform-owned."""
    registry = AdapterRegistry()
    return ToolDispatcher(
        registry=registry,
        resolver=CapabilityResolver(registry),
        task_service=TaskService(max_concurrency=1),
        authorizer=make_authorizer(service),
    )


def test_dispatcher_allows_and_refuses_through_the_authorizer(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    add_user(seeded, "reader", roles=("visitor",))
    add_user(seeded, "nobody", roles=())
    dispatcher = _dispatcher(service)
    reader = run(service.login("reader", PASSWORD)).token
    nobody = run(service.login("nobody", PASSWORD)).token

    allowed = run(dispatcher.dispatch("midas_task", {"action": "list"}, principal=reader))
    assert allowed["success"] is True
    assert allowed["errors"] == []

    refused = run(dispatcher.dispatch("midas_task", {"action": "list"}, principal=nobody))
    assert refused["success"] is False
    assert refused["errors"][0]["code"] == ErrorCode.PERMISSION_DENIED.value

    anonymous = run(dispatcher.dispatch("midas_task", {"action": "list"}))
    assert anonymous["success"] is False
    assert anonymous["errors"][0]["code"] == ErrorCode.AUTH_REQUIRED.value


def test_the_authorizer_runs_before_tool_validation_and_routing(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """v1.2 §38: Authentication -> RBAC precede validation and resolution."""
    add_user(seeded, "nobody", roles=())
    dispatcher = _dispatcher(service)
    token = run(service.login("nobody", PASSWORD)).token

    # ``wibble`` is not a valid action, so the *later* steps would answer
    # CAPABILITY_NOT_SUPPORTED / VALIDATION_ERROR; the seam answers first.
    envelope = run(
        dispatcher.dispatch("midas_task", {"action": "wibble"}, principal=token)
    )
    assert envelope["errors"][0]["code"] == ErrorCode.PERMISSION_DENIED.value


def test_dispatcher_enforces_the_instance_scope(
    seeded: Callable[[], Session], service: AuthService
) -> None:
    """``midas_query`` carries ``client_id`` in its schema (V2.1 §7.2)."""
    owner_id = add_user(seeded, "owner", roles=("engineer",))
    add_user(seeded, "other", roles=("engineer",))
    private_id = add_instance(seeded, owner_id=owner_id, visibility="private")
    dispatcher = _dispatcher(service)
    token = run(service.login("other", PASSWORD)).token

    envelope = run(
        dispatcher.dispatch(
            "midas_query",
            {"target": "node", "action": "list", "client_id": private_id},
            principal=token,
        )
    )
    assert envelope["success"] is False
    assert envelope["errors"][0]["code"] == ErrorCode.PERMISSION_DENIED.value
    assert envelope["errors"][0]["details"]["reason"] == "instance_out_of_scope"


# ===========================================================================
# 11. bootstrap: the first super_admin
# ===========================================================================
def test_ensure_bootstrap_admin_creates_the_first_super_admin(
    factory: Callable[[], Session], service: AuthService
) -> None:
    """Without it a fresh database has no account at all (``users`` is empty)."""
    warning = ensure_bootstrap_admin(factory, username="root", password=PASSWORD)
    assert "root" in warning
    assert BOOTSTRAP_PASSWORD_MARKER in warning
    assert PASSWORD in warning

    result = run(service.login("root", PASSWORD))
    assert result.principal.roles == ("super_admin",)
    assert result.principal.permissions == set(PERMISSION_CODES)

    with session_scope_for(factory) as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1
        assert session.scalar(select(func.count()).select_from(Permission)) == 34
        assert session.scalar(select(func.count()).select_from(Role)) == 4
        assert session.scalar(select(func.count()).select_from(RolePermission)) == 65


def test_ensure_bootstrap_admin_is_idempotent_and_never_resets_a_password(
    factory: Callable[[], Session], service: AuthService
) -> None:
    ensure_bootstrap_admin(factory, username="root", password=PASSWORD)
    second = ensure_bootstrap_admin(factory, username="root", password="Other-Passw0rd!")
    assert "跳过" in second

    with session_scope_for(factory) as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1

    # The original password still works; the second call changed nothing.
    assert run(service.login("root", PASSWORD)).principal.username == "root"
    with pytest.raises(AdapterError) as excinfo:
        run(service.login("root", "Other-Passw0rd!"))
    assert error_code(excinfo) == ErrorCode.AUTH_INVALID.value


def test_ensure_bootstrap_admin_generates_a_password_when_none_is_given(
    factory: Callable[[], Session], service: AuthService
) -> None:
    warning = ensure_bootstrap_admin(factory, username="root")
    generated = warning.split(BOOTSTRAP_PASSWORD_MARKER)[1].split()[0]
    assert len(generated) >= 16
    assert run(service.login("root", generated)).principal.roles == ("super_admin",)


def test_ensure_bootstrap_admin_rejects_a_password_that_breaks_the_policy(
    factory: Callable[[], Session],
) -> None:
    """``security_configs.password_min_length`` / ``password_complexity``."""
    with pytest.raises(AdapterError) as excinfo:
        ensure_bootstrap_admin(factory, username="root", password="short")
    assert error_code(excinfo) == ErrorCode.VALIDATION_ERROR.value

    with session_scope_for(factory) as session:
        assert session.scalar(select(func.count()).select_from(User)) == 0


def test_ensure_bootstrap_admin_rejects_an_empty_username(
    factory: Callable[[], Session],
) -> None:
    with pytest.raises(AdapterError) as excinfo:
        ensure_bootstrap_admin(factory, username="   ", password=PASSWORD)
    assert error_code(excinfo) == ErrorCode.VALIDATION_ERROR.value


def test_ensure_bootstrap_admin_seeds_the_rbac_tables(
    factory: Callable[[], Session],
) -> None:
    """``002_seed.sql`` may never have run; the bootstrap must still work."""
    warning = ensure_bootstrap_admin(factory, username="root", password=PASSWORD)
    assert "permissions+34" in warning
    assert "roles+4" in warning
    assert "role_permissions+65" in warning
    with session_scope_for(factory) as session:
        assert session.scalar(select(func.count()).select_from(Permission)) == 34


def test_production_password_hash_cost_is_not_weakened(
    production_pbkdf2_iterations: int,
) -> None:
    """Guard the KDF cost against the test-suite shortcut leaking into production.

    ``tests/conftest.py`` lowers ``crypto._PBKDF2_ITERATIONS`` to 1 for the whole
    session, because at the real 260 000 the auth suite spent ~100 s of its 128 s
    inside PBKDF2.  That shortcut is a *test* concern; the shipped cost is a
    security parameter and must stay expensive.

    This test is the lock on that door: if someone "optimises" the constant in
    ``app/core/crypto.py`` to make tests faster, this fails instead of the
    weakening passing silently.  OWASP's current PBKDF2-HMAC-SHA256 guidance is
    ≥600 000 iterations, so the floor here is deliberately well below that — it
    catches a collapse, not a considered re-tuning.
    """
    assert production_pbkdf2_iterations >= 200_000, (
        "production PBKDF2 iteration count collapsed to "
        f"{production_pbkdf2_iterations}; password hashing must stay expensive "
        "(the test suite lowers it via tests/conftest.py instead)"
    )


# ===========================================================================
# 12. the catch-up step for existing databases — users.department (总纲 §4.2.5)
# ===========================================================================
# ``ensure_users_department`` is imported **inside** these tests on purpose:
# ``app.db.init_db`` imports ``app.db.session``, which builds the process-wide
# engine at import time, and this module deliberately runs on nothing but its own
# per-test SQLite file (see the module docstring).  The function takes an explicit
# ``bind``, so the local import is the only thing that touches that module.
def _legacy_engine(path: Path) -> Engine:
    """A pre-``users.department`` database holding only the two tables involved.

    ``CREATE TABLE`` without the column is exactly what an existing deployment
    has: the schema is otherwise complete, but ``CREATE TABLE IF NOT EXISTS``
    could never add ``department`` to it.
    """
    engine: Engine = create_engine(f"sqlite:///{path}", future=True)
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL)")
        )
        connection.execute(
            text(
                "CREATE TABLE midas_clients ("
                " id INTEGER PRIMARY KEY, owner_id INTEGER, department TEXT)"
            )
        )
    return engine


def test_the_migration_step_adds_users_department_and_backfills_once(
    tmp_path: Path,
) -> None:
    """总纲 §4.2.5 — the column is added, then backfilled from ``midas_clients``."""
    from app.db.init_db import ensure_users_department

    engine = _legacy_engine(tmp_path / "legacy.db")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (id, username) VALUES"
                    " (1, 'alice'), (2, 'bob'), (3, 'carol')"
                )
            )
            # alice has two labelled registrations (lowest id wins), bob has only
            # an unlabelled one, carol has none at all.
            connection.execute(
                text(
                    "INSERT INTO midas_clients (id, owner_id, department) VALUES"
                    " (1, 1, 'A'), (2, 1, 'B'), (3, 2, NULL)"
                )
            )

        # The column is absent before the step ...
        assert "department" not in {
            column["name"] for column in inspect(engine).get_columns("users")
        }

        assert ensure_users_department(bind=engine) is True

        assert "department" in {
            column["name"] for column in inspect(engine).get_columns("users")
        }
        with engine.connect() as connection:
            backfilled = dict(
                connection.execute(text("SELECT id, department FROM users")).all()
            )
        # Deterministic (lowest ``midas_clients.id``), and NULL where there was
        # nothing to backfill — fail closed, never "any department".
        assert backfilled == {1: "A", 2: None, 3: None}

        # Running it again is a no-op: the column is already there.
        assert ensure_users_department(bind=engine) is False
    finally:
        engine.dispose()


def test_the_migration_step_never_overwrites_an_operators_assignment(
    tmp_path: Path,
) -> None:
    """The backfill runs **only** when the column was just added."""
    from app.db.init_db import ensure_users_department

    engine = _legacy_engine(tmp_path / "legacy_ops.db")
    try:
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO users (id, username) VALUES (1, 'alice')")
            )
            connection.execute(
                text(
                    "INSERT INTO midas_clients (id, owner_id, department)"
                    " VALUES (1, 1, 'A')"
                )
            )
        assert ensure_users_department(bind=engine) is True

        # An operator moves alice to another department ...
        with engine.begin() as connection:
            connection.execute(text("UPDATE users SET department = 'B' WHERE id = 1"))

        # ... and a later startup leaves that alone.
        assert ensure_users_department(bind=engine) is False
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT department FROM users WHERE id = 1"))
                == "B"
            )
    finally:
        engine.dispose()


def test_the_migration_step_is_a_no_op_on_a_fresh_schema(db_path: Path) -> None:
    """A database built from the current schema already has the column."""
    from app.db.init_db import ensure_users_department

    engine: Engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        assert "department" in {
            column["name"] for column in inspect(engine).get_columns("users")
        }
        assert ensure_users_department(bind=engine) is False
    finally:
        engine.dispose()


def test_the_migration_step_tolerates_a_database_without_the_tables(
    tmp_path: Path,
) -> None:
    """Nothing to catch up on: the step reports "no change" instead of failing."""
    from app.db.init_db import ensure_users_department

    engine: Engine = create_engine(f"sqlite:///{tmp_path / 'empty.db'}", future=True)
    try:
        assert ensure_users_department(bind=engine) is False
    finally:
        engine.dispose()


def test_the_raw_ddl_creates_users_department(tmp_path: Path) -> None:
    """总纲 §4.2.5 — a fresh database gets the column from ``001_schema.sql``.

    The catch-up step above only exists for databases that predate the column; a
    new one must never need it.  Running the authoritative script itself is what
    proves that (and that the script still executes end to end).
    """
    from app.db.init_db import SQL_DIR

    script = (SQL_DIR / "001_schema.sql").read_text(encoding="utf-8")
    engine: Engine = create_engine(f"sqlite:///{tmp_path / 'ddl.db'}", future=True)
    try:
        raw = engine.raw_connection()
        try:
            cursor = raw.cursor()
            try:
                cursor.executescript(script)
                raw.commit()
            finally:
                cursor.close()
        finally:
            raw.close()

        users_columns = {
            column["name"] for column in inspect(engine).get_columns("users")
        }
        assert "department" in users_columns
        # The label is a plain nullable TEXT with no default — "unassigned" is a
        # real state (总纲 §4.2.5), not a value to be silently filled in.
        department = next(
            column
            for column in inspect(engine).get_columns("users")
            if column["name"] == "department"
        )
        assert department["nullable"] is True
        assert department["default"] is None
    finally:
        engine.dispose()
