"""Authentication and RBAC service — 总纲 §4.8, 裁决 C-9 / C-13, 对接规范 §2.5.4.

Authoritative sources
---------------------
* 总纲 §4.8.1 / §4.8.2 — 权限码 ``<module>:<action>``，**封闭集合** 34 条。
  本模块只读 :data:`app.core.constants.PERMISSION_CODES`，绝不新增权限码。
* 总纲 §4.8.3 — 默认角色 → 权限映射（:data:`ROLE_PERMISSION_MAP`），由
  :func:`seed_rbac` 按 ``002_seed.sql`` 的展开方式幂等落库。
* 总纲 §4.8.4 — :data:`SUPER_ADMIN_ONLY_PERMISSIONS` **仅 super_admin**；
  这条约束由 :meth:`AuthService.permissions_for_now` 在**读取时**强制执行：
  即使 ``role_permissions`` 被误授予，非 super_admin 也拿不到这四个码。
* 总纲 §4.4.1 — 认证与授权错误码（``AUTH_REQUIRED`` / ``AUTH_INVALID`` /
  ``AUTH_EXPIRED`` / ``PERMISSION_DENIED``）；§4.4.2 的 ``RATE_LIMITED`` /
  ``VALIDATION_ERROR``。本模块不新增任何错误码（总纲 §0.3 / 裁决 A-3）。
* 总纲 §4.2.5 — ``users.status`` 封闭集合 ``enabled`` / ``disabled`` / ``locked``；
  同节的 ``users.department`` 是「用户所属部门」的落库位置（**一个用户只属于一个
  部门**，与 ``midas_clients.department`` **按值匹配**，不是外键）。它是实例数据
  范围过滤中「主体部门」一侧的来源，由 :meth:`AuthService._department_now` 解析；
  ``NULL`` 表示「未分配」，未分配即 fail closed。
* 总纲 §4.5.1 — 时间一律 UTC 存储；SQLite 读回是 naive（无 offset），统一用
  :func:`_as_utc` 重新贴上 UTC 后再比较。
* 总纲 §4.7.1 — 主密钥 ``STRUCTAI_MASTER_KEY``。JWT 签名密钥由它**派生**（见
  :func:`signing_key`），代码里没有任何硬编码密钥；未配置时显式失败。
* 总纲 裁决 C-9 — ``expires_in`` = ``security_configs.session_timeout_minutes``
  × 60（默认 30 分钟 → 1800 秒），**不是**旧的 7200 秒。``sessions.expires_at``
  与 JWT ``exp`` 都由同一个值派生。
* 总纲 裁决 C-13 — ``security_configs.api_auth_required`` 决定「未认证调用是否
  一律拒绝」；默认 1（开启）。
* 总纲 §4.1.3 — ID 前缀是**封闭集合**，其中没有 ``sessions.session_id`` 的前缀，
  因此会话号是**无前缀**的随机标识：给它加前缀等于新增前缀，会被封闭集合守卫
  拒绝（:func:`app.core.ids.new_id` 只接受 14 个前缀）。
* 《MIDAS API 对接规范》§2.5.4 第 5 条 — ``midas_clients`` 的归属/可见性字段与
  「实例归属校验」；该过滤在 :mod:`app.mcp.auth` 中实现为**既有权限码之上的
  数据范围过滤**，不引入新权限码。
* v1.2 §38 — Dispatcher 流程第一步 Authentication、第二步 RBAC。

Why the ``sessions`` row exists
-------------------------------
A bare JWT cannot be invalidated before its ``exp``.  总纲 §4（V2.1 §4 table
``sessions``）already carries ``session_id`` / ``token_hash`` / ``expires_at`` /
``revoked_at`` precisely so a logout can revoke one token without touching the
others.  :meth:`AuthService.login` therefore always writes one ``sessions`` row
and :meth:`AuthService.logout` sets ``revoked_at``; the JWT's ``jti`` is that
row's ``session_id``, which is what makes the row findable from the token alone.

Only a **hash** of the token is stored (``sessions.token_hash``, NOT NULL):
:func:`app.core.crypto.hash_secret` (PBKDF2-HMAC-SHA256).  The plaintext token
never reaches the database, so a database dump cannot be replayed as a login.

Token verification deliberately does **not** re-run PBKDF2 on every MCP call:
the authenticity check is the JWT signature (HS256 over a key derived from
``STRUCTAI_MASTER_KEY``) and the revocation check is the ``sessions`` row
(``jti`` → ``revoked_at`` / ``expires_at``).  Re-deriving 260 000 PBKDF2
iterations per tool call would cost ~100 ms per call for no additional guarantee.

Sync vs async
-------------
The models are **synchronous** SQLAlchemy 2.x declarative and
:mod:`app.db.session` exposes a sync ``sessionmaker``.  Every method that touches
the database therefore has a ``*_now`` synchronous core (the naming convention
:mod:`app.services.task_store` already uses) plus an ``async`` wrapper that hands
the blocking work to :func:`asyncio.to_thread`.  The ``Session`` is always opened
**inside** the worker thread — a ``Session`` is not thread-safe and is never
shared between calls.
"""

import asyncio
import hashlib
import re
import secrets
import string
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping

import jwt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.errors import AdapterError
from app.core import crypto
from app.core.config import get_settings
from app.core.constants import (
    SUPER_ADMIN_ONLY_PERMISSIONS,
    SUPER_ADMIN_ROLE,
    PERMISSIONS,
    PERMISSION_CODES,
    ROLE_DEFINITIONS,
    ROLE_PERMISSION_MAP,
    UserStatus,
    expand_permission_patterns,
)
from app.core.errors import ErrorCode
from app.db.base import session_scope_for, utcnow
from app.models.identity import (
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
    UserSession,
)
from app.models.midas import MidasClient
from app.models.settings import SecurityConfig

__all__ = [
    # policy defaults (mirror security_configs' DDL defaults)
    "DEFAULT_SESSION_TIMEOUT_MINUTES",
    "DEFAULT_MAX_LOGIN_ATTEMPTS",
    "DEFAULT_LOCK_MINUTES",
    "DEFAULT_PASSWORD_MIN_LENGTH",
    "DEFAULT_PASSWORD_COMPLEXITY",
    "DEFAULT_RATE_LIMIT_ENABLED",
    "DEFAULT_RATE_LIMIT_PER_MINUTE",
    "DEFAULT_RATE_LIMIT_BURST",
    "JWT_ALGORITHM",
    "SUPER_ADMIN_ROLE",
    "BOOTSTRAP_PASSWORD_MARKER",
    # types
    "SecurityPolicy",
    "Principal",
    "AuthResult",
    "InstanceScope",
    # token mechanics
    "signing_key",
    "issue_token",
    "decode_token",
    # password helpers
    "hash_password",
    "verify_password",
    "password_policy_error",
    "generate_password",
    # service
    "AuthService",
    "get_auth_service",
    "reset_auth_service",
    # bootstrap
    "seed_rbac",
    "ensure_bootstrap_admin",
]


# ---------------------------------------------------------------------------
# constants — every default mirrors a column default in 001_schema.sql
# ---------------------------------------------------------------------------
#: 总纲 裁决 C-9: fallback when the ``security_configs`` singleton row is absent.
DEFAULT_SESSION_TIMEOUT_MINUTES: int = 30

#: ``security_configs.max_login_attempts`` default (unit: count).
DEFAULT_MAX_LOGIN_ATTEMPTS: int = 5

#: ``security_configs.lock_minutes`` default (unit: minutes).
DEFAULT_LOCK_MINUTES: int = 30

#: ``security_configs.password_min_length`` default (unit: count).
DEFAULT_PASSWORD_MIN_LENGTH: int = 8

#: ``security_configs.password_complexity`` default (unit: level, 0–3).
DEFAULT_PASSWORD_COMPLEXITY: int = 1

#: 总纲 裁决 C-13: ``security_configs.api_auth_required`` default.
DEFAULT_API_AUTH_REQUIRED: bool = True

#: 总纲 裁决 B-7 / §8.6 — ``security_configs.rate_limit_enabled`` default.
DEFAULT_RATE_LIMIT_ENABLED: bool = True

#: 总纲 裁决 B-7 — ``security_configs.rate_limit_per_minute`` default (unit: 每分钟).
DEFAULT_RATE_LIMIT_PER_MINUTE: int = 120

#: 总纲 裁决 B-7 — ``security_configs.rate_limit_burst`` default (unit: tokens).
DEFAULT_RATE_LIMIT_BURST: int = 30

#: The only JWT algorithm this platform accepts (symmetric, no key file).
JWT_ALGORITHM: str = "HS256"

#: Domain-separation label for the JWT key.  Deliberately **different** from
#: :data:`app.core.crypto._KEY_DERIVATION_LABEL` so the JWT signing key and the
#: AES-256-GCM field key are two distinct keys derived from one master secret.
JWT_KEY_LABEL: bytes = b"structai-jwt-hs256-v1"

#: 总纲 §4.8.3 — ``SUPER_ADMIN_ROLE`` now lives in :mod:`app.core.constants`
#: (see the note there); it was previously a second literal defined here.

#: Marker used in the bootstrap warning so an operator can copy the generated
#: password out of the returned string (the password is **returned**, never logged).
BOOTSTRAP_PASSWORD_MARKER: str = "初始密码："

#: Length of a generated bootstrap password (unit: characters).
GENERATED_PASSWORD_LENGTH: int = 20

#: 总纲 §4.8.2 — the closed permission set, as a fast membership test.
_PERMISSION_CODE_SET: frozenset[str] = frozenset(PERMISSION_CODES)

#: 总纲 §4.8.4 rows 1–3 — the codes only ``super_admin`` may hold.
#:
#: Deliberately **not** ``HIGH_RISK_PERMISSIONS``: that broader set also contains
#: ``assistant:execute``, which §4.8.4 grants to ``engineer`` and above (gated
#: separately by the §5 confirmation flow).  Filtering on the broader set denied
#: engineers a permission the spec gives them.
_SUPER_ADMIN_ONLY: frozenset[str] = frozenset(SUPER_ADMIN_ONLY_PERMISSIONS)


# ---------------------------------------------------------------------------
# small time helpers (总纲 §4.5.1)
# ---------------------------------------------------------------------------
def _as_utc(value: datetime | None) -> datetime | None:
    """Re-attach UTC to a value SQLite handed back naive (总纲 §4.5.1).

    SQLAlchemy's SQLite ``DATETIME`` stores the wall clock without an offset, so
    a value written as timezone-aware UTC reads back naive-but-UTC.  Normalising
    here is what makes ``expires_at`` / ``locked_until`` comparisons correct.
    """
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _utc(moment: datetime) -> datetime:
    """Coerce any datetime to timezone-aware UTC."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# the signing key — derived, never hard-coded (总纲 §4.7.1)
# ---------------------------------------------------------------------------
def signing_key() -> bytes:
    """Derive the HS256 signing key from ``settings.structai_master_key``.

    ``SHA-256("structai-jwt-hs256-v1" || STRUCTAI_MASTER_KEY)`` — the same shape
    :func:`app.core.crypto._master_key` uses for AES-256-GCM, with a different
    label so the two keys are independent (domain separation).

    :raises RuntimeError: ``STRUCTAI_MASTER_KEY`` is unset or blank.  Failing
        loudly is the point: a default key would silently let anyone mint tokens.
    """
    raw = get_settings().structai_master_key
    if not raw or not raw.strip():
        raise RuntimeError(
            "STRUCTAI_MASTER_KEY is not set. 总纲 §4.7.1 requires a master key "
            "before any credential can be issued or verified: the JWT signing key "
            "is derived from it and this module refuses to fall back to a "
            "hard-coded secret. Export it first, e.g.\n"
            "    set STRUCTAI_MASTER_KEY=<a long random passphrase>   (Windows)\n"
            "    export STRUCTAI_MASTER_KEY=<a long random passphrase>  (POSIX)"
        )
    return hashlib.sha256(JWT_KEY_LABEL + raw.encode("utf-8")).digest()


# ---------------------------------------------------------------------------
# JWT mechanics (PyJWT, HS256)
# ---------------------------------------------------------------------------
def issue_token(
    *,
    user_id: int,
    username: str,
    session_id: str,
    expires_in: int,
    issued_at: datetime | None = None,
    extra_claims: Mapping[str, Any] | None = None,
) -> str:
    """Sign one HS256 bearer token.

    :param user_id: becomes the ``sub`` claim (string, per RFC 7519).
    :param session_id: becomes the ``jti`` claim — the ``sessions.session_id``
        row that :meth:`AuthService.logout` revokes.
    :param expires_in: token lifetime in **seconds**.  Callers derive it from
        ``security_configs.session_timeout_minutes × 60`` (总纲 裁决 C-9);
        :meth:`AuthService.login` is the only production caller.
    :param issued_at: defaults to now (UTC); injected by tests / a fake clock.
    """
    moment = _utc(issued_at) if issued_at is not None else utcnow()
    claims: dict[str, Any] = {
        "sub": str(int(user_id)),
        "username": str(username),
        "jti": str(session_id),
        "iat": int(moment.timestamp()),
        "exp": int(moment.timestamp()) + int(expires_in),
    }
    if extra_claims:
        claims.update(dict(extra_claims))
    token = jwt.encode(claims, signing_key(), algorithm=JWT_ALGORITHM)
    # PyJWT 2.x returns ``str``; the ``bytes`` branch is kept for older builds.
    return token if isinstance(token, str) else token.decode("ascii")


def _decode_claims(token: str, *, verify_exp: bool) -> dict[str, Any]:
    """Verify the signature and return the claims, mapping failures onto §4.4.1.

    ``exp`` / ``sub`` / ``jti`` are **required**: a token missing any of them is
    not one this platform issued, so it is ``AUTH_INVALID`` rather than a
    half-usable credential.
    """
    if not token or not isinstance(token, str):
        raise AdapterError(
            ErrorCode.AUTH_INVALID,
            "凭证为空或不是字符串（总纲 §4.4.1：AUTH_INVALID）。",
            details={"reason": "empty_token"},
        )
    options: dict[str, Any] = {"require": ["exp", "sub", "jti"]}
    if not verify_exp:
        options["verify_exp"] = False
    try:
        claims = jwt.decode(
            token, signing_key(), algorithms=[JWT_ALGORITHM], options=options
        )
    except jwt.ExpiredSignatureError as exc:
        # 总纲 §4.4.1: 凭证过期 -> AUTH_EXPIRED (401).
        raise AdapterError(
            ErrorCode.AUTH_EXPIRED,
            "凭证已过期（JWT exp 已过，总纲 §4.4.1 AUTH_EXPIRED）。",
            details={"reason": "token_expired"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        # 签名不匹配、算法不符、必需声明缺失 —— 一律 AUTH_INVALID。
        raise AdapterError(
            ErrorCode.AUTH_INVALID,
            f"凭证无效：{type(exc).__name__}（签名/算法/必需声明校验未通过，"
            "总纲 §4.4.1 AUTH_INVALID）。",
            details={"reason": "invalid_token", "error": type(exc).__name__},
        ) from exc
    if not isinstance(claims, dict):  # pragma: no cover - defensive
        raise AdapterError(
            ErrorCode.AUTH_INVALID,
            "凭证载荷不是 JSON 对象（总纲 §4.4.1 AUTH_INVALID）。",
            details={"reason": "malformed_claims"},
        )
    return claims


def decode_token(token: str) -> dict[str, Any]:
    """Verify ``token`` and return its claims (总纲 §4.4.1 on failure).

    :raises AdapterError: ``AUTH_EXPIRED`` when ``exp`` has passed,
        ``AUTH_INVALID`` for every other verification failure.
    """
    return _decode_claims(token, verify_exp=True)


# ---------------------------------------------------------------------------
# passwords — thin wrappers over app.core.crypto (总纲 §4.7.1 spirit)
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Hash a password with PBKDF2-HMAC-SHA256 (:func:`app.core.crypto.hash_secret`).

    ``passlib`` / ``bcrypt`` are deliberately **not** used: they are not a
    dependency of this project, and ``verify_secret`` additionally accepts
    ``$2b$`` bcrypt hashes should one ever be imported from elsewhere.
    """
    return crypto.hash_secret(password)


def verify_password(password: str, hashed: str | None) -> bool:
    """Constant-time verification against ``users.password_hash``."""
    return crypto.verify_secret(password, hashed)


def password_policy_error(
    password: str, policy: "SecurityPolicy | None" = None
) -> str | None:
    """Return the reason ``password`` violates ``security_configs``, else ``None``.

    ``password_complexity`` is a 0–3 *level* in the DDL and the source documents
    do not define it further, so this module fixes the reading: level ``n``
    requires ``n + 1`` character classes out of {lower, upper, digit, symbol}
    (capped at 4).  Level 0 disables the class rule entirely.
    """
    rules = policy if policy is not None else SecurityPolicy()
    minimum = max(1, int(rules.password_min_length))
    if not isinstance(password, str) or len(password) < minimum:
        return (
            f"密码长度不足：至少 {minimum} 位"
            "（security_configs.password_min_length）。"
        )
    level = int(rules.password_complexity)
    if level <= 0:
        return None
    classes = sum(
        1
        for pattern in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]")
        if re.search(pattern, password)
    )
    required = min(4, level + 1)
    if classes < required:
        return (
            f"密码复杂度不足：security_configs.password_complexity={level} "
            f"要求至少 {required} 类字符（小写/大写/数字/符号），当前只有 {classes} 类。"
        )
    return None


def generate_password(length: int = GENERATED_PASSWORD_LENGTH) -> str:
    """Generate a password that satisfies **every** documented complexity level."""
    pools = (
        string.ascii_lowercase,
        string.ascii_uppercase,
        string.digits,
        "!@#$%^&*()-_=+",
    )
    chars = [secrets.choice(pool) for pool in pools]
    alphabet = "".join(pools)
    chars.extend(secrets.choice(alphabet) for _ in range(max(0, length - len(pools))))
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


# ---------------------------------------------------------------------------
# types
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SecurityPolicy:
    """The ``security_configs`` singleton, as the auth layer needs it.

    Every field default is the column default of ``001_schema.sql``, used only
    when the row is missing (裁决 C-9 fixes exactly this fallback for the TTL).
    """

    #: Lock the account after this many consecutive failures (unit: count).
    max_login_attempts: int = DEFAULT_MAX_LOGIN_ATTEMPTS
    #: How long an automatic lock lasts (unit: minutes).
    lock_minutes: int = DEFAULT_LOCK_MINUTES
    #: Token TTL (unit: minutes) — 总纲 裁决 C-9.
    session_timeout_minutes: int = DEFAULT_SESSION_TIMEOUT_MINUTES
    #: Minimum password length (unit: characters).
    password_min_length: int = DEFAULT_PASSWORD_MIN_LENGTH
    #: Complexity level 0–3 (unit: level).
    password_complexity: int = DEFAULT_PASSWORD_COMPLEXITY
    #: 总纲 裁决 C-13: when False, an unauthenticated call is not refused at all.
    api_auth_required: bool = DEFAULT_API_AUTH_REQUIRED
    #: 总纲 裁决 B-7 / §8.6: master switch of the token-bucket limiter.
    rate_limit_enabled: bool = DEFAULT_RATE_LIMIT_ENABLED
    #: 总纲 裁决 B-7: token-bucket refill rate (unit: tokens per minute).
    rate_limit_per_minute: int = DEFAULT_RATE_LIMIT_PER_MINUTE
    #: 总纲 裁决 B-7: token-bucket capacity (unit: tokens).
    rate_limit_burst: int = DEFAULT_RATE_LIMIT_BURST

    @classmethod
    def from_row(cls, row: "SecurityConfig") -> "SecurityPolicy":
        """Project the ``security_configs`` singleton row onto this record.

        One place reads the row, so adding a column cannot leave one of the two
        construction sites (``security_policy_now`` / ``ensure_bootstrap_admin``)
        silently on the old default — the drift that made this a classmethod.
        """
        return cls(
            max_login_attempts=int(row.max_login_attempts),
            lock_minutes=int(row.lock_minutes),
            session_timeout_minutes=int(row.session_timeout_minutes),
            password_min_length=int(row.password_min_length),
            password_complexity=int(row.password_complexity),
            api_auth_required=bool(row.api_auth_required),
            rate_limit_enabled=bool(row.rate_limit_enabled),
            rate_limit_per_minute=int(row.rate_limit_per_minute),
            rate_limit_burst=int(row.rate_limit_burst),
        )

    @property
    def session_ttl_seconds(self) -> int:
        """``expires_in`` in seconds — 总纲 裁决 C-9: ``minutes × 60``.

        A non-positive row value would mint a dead-on-arrival token, so it falls
        back to :data:`DEFAULT_SESSION_TIMEOUT_MINUTES` (the same fallback used
        when the row is absent) instead of producing a 0-second session.
        """
        minutes = int(self.session_timeout_minutes)
        if minutes <= 0:
            minutes = DEFAULT_SESSION_TIMEOUT_MINUTES
        return minutes * 60


@dataclass(frozen=True)
class Principal:
    """The authenticated caller the MCP RBAC seam sees (v1.2 §38).

    ``permissions`` is already resolved **and already narrowed** per 总纲 §4.8.4
    (high-risk codes are dropped unless the principal holds ``super_admin``), so
    a consumer must not re-derive it from ``roles``.
    """

    user_id: int
    username: str
    roles: tuple[str, ...]
    permissions: frozenset[str]
    #: Department label used by the instance data-scope filter (总纲 §4.2.5,
    #: 《MIDAS API 对接规范》§2.5.4 item 5) — resolved from ``users.department``
    #: (or the injected ``department_resolver``).  ``None`` means "unassigned"
    #: and therefore "no department-scoped instance is usable": the filter fails
    #: closed rather than assuming a match.
    department: str | None
    #: The token's expiry (``sessions.expires_at`` / JWT ``exp``).
    expires_at: datetime
    #: ``sessions.session_id`` — the JWT ``jti``.
    session_id: str | None = None
    token_type: str = "Bearer"

    def has_permission(self, code: str) -> bool:
        """True when this principal holds the 总纲 §4.8.2 ``code``."""
        return bool(code) and code in self.permissions

    def is_expired(self, now: datetime | None = None) -> bool:
        """True when the token's expiry has passed."""
        moment = _utc(now) if now is not None else utcnow()
        return _utc(self.expires_at) <= moment


#: ``users.id`` values are positive, so the anonymous principal (裁决 C-13) can
#: never collide with a real row.
ANONYMOUS_USER_ID: int = 0


def anonymous_principal(now: datetime | None = None) -> Principal:
    """The stand-in principal used when 总纲 裁决 C-13 switches authentication off.

    ``security_configs.api_auth_required = 0`` means "an unauthenticated call is
    not refused at all".  The MCP surface implements that by skipping the whole
    gate in :func:`app.mcp.auth.make_authorizer`; the REST routes resolve the
    principal **themselves** in ``app.main._principal_of``, so without a concrete
    stand-in they still answered ``AUTH_REQUIRED`` — the two surfaces disagreed
    about one config flag, which is measured, not hypothetical:

    ==============================  ==========================
    ``api_auth_required = 0``       result (no credential)
    ==============================  ==========================
    MCP ``midas_task``              allowed
    ``GET /api/v1/tasks``           ``401 AUTH_REQUIRED``
    ``GET /api/v1/auth/me``         ``401 AUTH_REQUIRED``
    ``GET /api/v1/logs/stream``     ``401 AUTH_REQUIRED``
    ==============================  ==========================

    It holds **every** §4.8.2 code, because "the gate is skipped" means the RBAC
    step is skipped too — a permission-less principal would refuse every call one
    line later, which is the opposite of C-13.

    ``user_id`` is :data:`ANONYMOUS_USER_ID` rather than a real id so that nothing
    can be attributed to it: ``tasks.requested_by`` must stay NULL in this mode,
    never point at a user that does not exist (``tasks.requested_by`` is a real
    foreign key, V2.1 §4).
    """
    moment = _utc(now) if now is not None else utcnow()
    return Principal(
        user_id=ANONYMOUS_USER_ID,
        username="anonymous",
        roles=(SUPER_ADMIN_ROLE,),
        permissions=frozenset(PERMISSION_CODES),
        department=None,
        expires_at=moment + timedelta(days=3650),
        session_id=None,
        token_type="None",
    )


@dataclass(frozen=True)
class AuthResult:
    """One successful login: the bearer token plus everything derived from it."""

    token: str
    #: 总纲 裁决 C-9 — ``security_configs.session_timeout_minutes × 60``.
    expires_in: int
    expires_at: datetime
    session_id: str
    principal: Principal
    token_type: str = "Bearer"


@dataclass(frozen=True)
class InstanceScope:
    """The data-scope fields of one ``midas_clients`` row (对接规范 §2.5.4 item 5).

    Deliberately a *plain record*: the decision function lives in
    :func:`app.mcp.auth.scope_allows`, so the MCP layer owns the policy and this
    layer only reads the database.
    """

    client_id: int
    owner_id: int | None
    #: ``private`` / ``department`` / ``public`` (总纲 §4.2.5 CHECK).
    visibility: str
    department: str | None
    name: str | None = None

    @classmethod
    def of(cls, row: "MidasClient") -> "InstanceScope":
        """Project a ``midas_clients`` row onto the scope record."""
        return cls(
            client_id=int(row.id),
            owner_id=int(row.owner_id) if row.owner_id is not None else None,
            visibility=str(row.visibility or ""),
            department=row.department,
            name=row.name,
        )


# ---------------------------------------------------------------------------
# the service
# ---------------------------------------------------------------------------
class AuthService:
    """Authentication + RBAC over ``users`` / ``roles`` / ``permissions`` / ``sessions``.

    ``session_factory`` is any zero-argument callable returning a
    :class:`sqlalchemy.orm.Session` (a ``sessionmaker``, or a lambda around one),
    exactly like :class:`app.services.task_store.SqlAlchemyTaskStore`.  When it
    is omitted the process-wide :data:`app.db.session.SessionLocal` is imported
    **lazily**, so importing this module never creates an engine.

    ``department_resolver`` lets the admin layer supply the user's department
    from wherever it eventually lives; it takes precedence over the built-in
    ``users.department`` column.  See :meth:`_department_now` for the full
    resolution order.

    ``clock`` is injectable so the lock window and the session TTL can be tested
    without sleeping.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session] | None = None,
        *,
        department_resolver: Callable[[int], str | None] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory: Callable[[], Session] | None = session_factory
        self._department_resolver = department_resolver
        self._clock = clock

    # ------------------------------------------------------------------ #
    # wiring helpers
    # ------------------------------------------------------------------ #
    @property
    def session_factory(self) -> Callable[[], Session]:
        """The session factory, resolved lazily to ``SessionLocal`` on first use."""
        if self._session_factory is None:
            from app.db.session import SessionLocal  # local: no engine at import time

            self._session_factory = SessionLocal
        return self._session_factory

    def now(self) -> datetime:
        """Current instant in UTC (injectable for tests)."""
        moment = self._clock() if self._clock is not None else utcnow()
        return _utc(moment)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AuthService factory={self._session_factory!r}>"

    # ------------------------------------------------------------------ #
    # security policy — 裁决 C-9 / C-13
    # ------------------------------------------------------------------ #
    def security_policy_now(self) -> SecurityPolicy:
        """Read the ``security_configs`` singleton row, or the DDL defaults.

        The row is optional (``002_seed.sql`` inserts it, a bare
        ``create_all`` database does not), so a missing row is **not** an error:
        裁决 C-9 fixes the defaults to use in that case.
        """
        with session_scope_for(self.session_factory) as session:
            row = session.get(SecurityConfig, 1)
            if row is None:
                return SecurityPolicy()
            return SecurityPolicy.from_row(row)

    async def security_policy(self) -> SecurityPolicy:
        """Async mirror of :meth:`security_policy_now`."""
        return await asyncio.to_thread(self.security_policy_now)

    # ------------------------------------------------------------------ #
    # RBAC resolution — the database is the only source of truth
    # ------------------------------------------------------------------ #
    @staticmethod
    def _grants_now(session: Session, user_id: int) -> tuple[tuple[str, ...], set[str]]:
        """Resolve ``user_roles`` → ``role_permissions`` → ``permissions.code``.

        Two rules are enforced here rather than trusted to the data:

        * 总纲 §4.8.2 — a ``permissions.code`` outside the closed 34-code set is
          dropped (the table is data, the set is the specification).
        * 总纲 §4.8.4 — :data:`SUPER_ADMIN_ONLY_PERMISSIONS` are dropped unless the
          user holds :data:`SUPER_ADMIN_ROLE`, even if ``role_permissions`` grants
          them to another role.  ``assistant:execute`` is **not** in that set:
          §4.8.4 gives it to ``engineer`` and above, gated instead by the §5
          high-risk confirmation flow.
        """
        # Deliberately a single, unambiguous join chain: ``role_ids`` is a
        # subquery of the user's ``user_roles`` rows, so the outer statement has
        # exactly one FROM root (``roles``) and cannot be mis-inferred.
        role_ids = select(UserRole.role_id).where(UserRole.user_id == int(user_id))
        rows = session.execute(
            select(Role.code, Permission.code)
            .select_from(Role)
            .join(RolePermission, RolePermission.role_id == Role.id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(Role.id.in_(role_ids))
        ).all()
        roles = tuple(sorted({str(role_code) for role_code, _ in rows}))
        codes = {str(permission_code) for _, permission_code in rows}
        codes &= _PERMISSION_CODE_SET
        if SUPER_ADMIN_ROLE not in roles:
            codes -= _SUPER_ADMIN_ONLY
        return roles, codes

    def roles_for_now(self, user_id: int) -> list[str]:
        """The role codes of ``user_id``, sorted (empty when it has none)."""
        with session_scope_for(self.session_factory) as session:
            roles, _permissions = self._grants_now(session, user_id)
            return list(roles)

    async def roles_for(self, user_id: int) -> list[str]:
        """Async mirror of :meth:`roles_for_now`."""
        return await asyncio.to_thread(self.roles_for_now, user_id)

    def permissions_for_now(self, user_id: int) -> set[str]:
        """Every 总纲 §4.8.2 permission code ``user_id`` holds, from the database."""
        with session_scope_for(self.session_factory) as session:
            _roles, permissions = self._grants_now(session, user_id)
            return permissions

    async def permissions_for(self, user_id: int) -> set[str]:
        """Async mirror of :meth:`permissions_for_now`."""
        return await asyncio.to_thread(self.permissions_for_now, user_id)

    def _department_now(self, session: Session, user_id: int) -> str | None:
        """The user's department label for the instance data-scope filter.

        Resolution order — **one** source of truth, so two answers can never
        disagree (总纲 §4.2.5; 《MIDAS API 对接规范》§2.5.4 item 5):

        1. the injected ``department_resolver``, when the deployment stores the
           label somewhere other than ``users`` — it wins, and a ``None`` from it
           is final too (it does not fall through to the column, which would be
           the second source of truth this change removed);
        2. ``users.department`` (总纲 §4.2.5);
        3. nothing else.  The answer is ``None``, and ``scope_allows`` then
           refuses every ``visibility='department'`` instance: fail closed, never
           "assume the same department".

        This used to derive the label from the user's **own** ``midas_clients``
        registrations, because ``users`` had no such column.  That derivation was
        **circular** — membership was read off the very registrations membership
        is supposed to grant access to — and it locked every ordinary member out
        of a department instance registered once by an administrator (measured:
        an engineer with no registrations of her own got ``department=None`` and
        was denied ``scope.department='A'``).  ``users.department`` replaced it;
        :func:`app.db.init_db.ensure_users_department` backfills the column once
        for databases that predate it.
        """
        if self._department_resolver is not None:
            resolved = self._department_resolver(int(user_id))
            return str(resolved) if resolved else None
        user = session.get(User, int(user_id))
        if user is None:  # pragma: no cover - callers resolve the user first
            return None
        label = user.department
        return str(label) if label else None

    # ------------------------------------------------------------------ #
    # instance data scope (对接规范 §2.5.4 item 5) — read only
    # ------------------------------------------------------------------ #
    def instance_scope_now(self, client_id: int) -> InstanceScope | None:
        """The scope record of one ``midas_clients`` row, or ``None`` when unknown."""
        with session_scope_for(self.session_factory) as session:
            row = session.get(MidasClient, int(client_id))
            return InstanceScope.of(row) if row is not None else None

    async def instance_scope(self, client_id: int) -> InstanceScope | None:
        """Async mirror of :meth:`instance_scope_now`."""
        return await asyncio.to_thread(self.instance_scope_now, client_id)

    # ------------------------------------------------------------------ #
    # login
    # ------------------------------------------------------------------ #
    @staticmethod
    def _is_locked(user: User, moment: datetime) -> bool:
        """True when ``user`` is locked **now** (总纲 §4.2.5).

        Two shapes share the ``locked`` status: an automatic lock, which carries
        ``locked_until`` and therefore expires, and an administrative lock, which
        carries no deadline and stays until an administrator clears it.
        """
        deadline = _as_utc(user.locked_until)
        if deadline is not None and deadline > moment:
            return True
        if user.status == UserStatus.LOCKED.value:
            return deadline is None
        return False

    @staticmethod
    def _new_session_id() -> str:
        """Mint a ``sessions.session_id``.

        总纲 §4.1.3 lists no prefix for ``sessions``, and the prefix set is
        closed, so this is a **prefix-free** random identifier rather than
        ``new_id(...)`` (which would require inventing a prefix).
        """
        return uuid.uuid4().hex

    def _register_failure(
        self,
        user: User,
        policy: SecurityPolicy,
        moment: datetime,
    ) -> AdapterError:
        """Count one failed attempt and lock the account when the budget is spent."""
        user.failed_attempts = int(user.failed_attempts or 0) + 1
        budget = max(1, int(policy.max_login_attempts))
        if user.failed_attempts >= budget:
            locked_until = moment + timedelta(minutes=max(1, int(policy.lock_minutes)))
            user.status = UserStatus.LOCKED.value
            user.locked_until = locked_until
            # 总纲 §4.4.2 RATE_LIMITED (429) is the closed-set code for "too many
            # attempts, come back later"; §4.4.1 has no ACCOUNT_LOCKED member.
            return AdapterError(
                ErrorCode.RATE_LIMITED,
                f"连续 {user.failed_attempts} 次登录失败，账号已锁定至 "
                f"{locked_until.isoformat()}（security_configs.max_login_attempts="
                f"{budget} / lock_minutes={policy.lock_minutes}）。",
                details={
                    "reason": "account_locked",
                    "failed_attempts": int(user.failed_attempts),
                    "locked_until": locked_until.isoformat(),
                },
            )
        return AdapterError(
            ErrorCode.AUTH_INVALID,
            "用户名或密码错误（总纲 §4.4.1 AUTH_INVALID）。",
            details={
                "reason": "bad_credentials",
                "failed_attempts": int(user.failed_attempts),
                "remaining_attempts": budget - int(user.failed_attempts),
            },
        )

    def login_now(
        self,
        username: str,
        password: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthResult:
        """Verify credentials, write one ``sessions`` row and return the token.

        Every refusal is a 总纲 §4.4 code: ``AUTH_INVALID`` for an unknown,
        soft-deleted, disabled or mis-credentialed account, ``RATE_LIMITED`` for
        a locked one.  The bookkeeping (``failed_attempts`` / ``locked_until``)
        is committed **before** the error is raised — the transaction block is
        exited normally and only then is the failure raised, otherwise the
        rollback would throw the counter away.
        """
        policy = self.security_policy_now()
        moment = self.now()
        failure: AdapterError | None = None
        result: AuthResult | None = None

        with session_scope_for(self.session_factory) as session:
            user = session.scalar(
                select(User).where(User.username == str(username))
            )
            if user is None:
                # Deliberately the same message as a wrong password: whether a
                # username exists is not something an unauthenticated caller
                # gets to learn (总纲 §4.4.1 has no ACCOUNT_NOT_FOUND).
                failure = AdapterError(
                    ErrorCode.AUTH_INVALID,
                    "用户名或密码错误（总纲 §4.4.1 AUTH_INVALID）。",
                    details={"reason": "bad_credentials"},
                )
            elif user.deleted_at is not None:
                # Soft delete (总纲 §4.5.1 / V2.1 §3.1): a removed account is
                # treated exactly like a disabled one and never logs in.
                failure = AdapterError(
                    ErrorCode.AUTH_INVALID,
                    "账号已删除（users.deleted_at 非空），不能登录"
                    "（总纲 §4.4.1 AUTH_INVALID）。",
                    details={"reason": "account_deleted", "user_id": int(user.id)},
                )
            elif user.status == UserStatus.DISABLED.value:
                failure = AdapterError(
                    ErrorCode.AUTH_INVALID,
                    "账号已被禁用（users.status='disabled'），不能登录"
                    "（总纲 §4.4.1 AUTH_INVALID）。",
                    details={"reason": "account_disabled", "user_id": int(user.id)},
                )
            elif self._is_locked(user, moment):
                deadline = _as_utc(user.locked_until)
                failure = AdapterError(
                    ErrorCode.RATE_LIMITED,
                    "账号已锁定"
                    + (f"至 {deadline.isoformat()}" if deadline else "（需管理员解锁）")
                    + "，请稍后再试（总纲 §4.2.5 users.status='locked'）。",
                    details={
                        "reason": "account_locked",
                        "user_id": int(user.id),
                        "locked_until": deadline.isoformat() if deadline else None,
                    },
                )
            elif not verify_password(password, user.password_hash):
                failure = self._register_failure(user, policy, moment)
            else:
                result = self._establish_session(
                    session, user, policy, moment, ip_address, user_agent
                )

        if failure is not None:
            raise failure
        if result is None:  # pragma: no cover - the branches above are exhaustive
            raise AdapterError(
                ErrorCode.INTERNAL_ERROR,
                "登录流程没有产生结果（内部状态异常）。",
            )
        return result

    async def login(
        self,
        username: str,
        password: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthResult:
        """Async mirror of :meth:`login_now`."""
        return await asyncio.to_thread(
            self.login_now,
            username,
            password,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def _establish_session(
        self,
        session: Session,
        user: User,
        policy: SecurityPolicy,
        moment: datetime,
        ip_address: str | None,
        user_agent: str | None,
    ) -> AuthResult:
        """Write the ``sessions`` row and reset the failure counters.

        ``expires_in`` comes from the policy row (裁决 C-9), so ``sessions.
        expires_at`` and the JWT ``exp`` are derived from one number.
        """
        expires_in = policy.session_ttl_seconds
        session_id = self._new_session_id()
        token = issue_token(
            user_id=int(user.id),
            username=str(user.username),
            session_id=session_id,
            expires_in=expires_in,
            issued_at=moment,
        )
        expires_at = moment + timedelta(seconds=expires_in)
        session.add(
            UserSession(
                session_id=session_id,
                user_id=int(user.id),
                # Only the hash is stored (sessions.token_hash is NOT NULL;
                # 总纲 §4.7.1 spirit: no plaintext secret in the database).
                token_hash=crypto.hash_secret(token),
                ip_address=ip_address,
                user_agent=user_agent,
                expires_at=expires_at,
            )
        )
        # A successful login clears the failure counter and any *automatic* lock
        # (an administrative lock can never reach this line: _is_locked refuses
        # it before the password is even checked).
        user.failed_attempts = 0
        user.locked_until = None
        if user.status == UserStatus.LOCKED.value:
            user.status = UserStatus.ENABLED.value
        user.last_login_at = moment
        user.last_login_ip = ip_address
        user.is_online = 1
        session.flush()

        roles, permissions = self._grants_now(session, int(user.id))
        principal = Principal(
            user_id=int(user.id),
            username=str(user.username),
            roles=roles,
            permissions=frozenset(permissions),
            department=self._department_now(session, int(user.id)),
            expires_at=expires_at,
            session_id=session_id,
        )
        return AuthResult(
            token=token,
            expires_in=expires_in,
            expires_at=expires_at,
            session_id=session_id,
            principal=principal,
        )

    # ------------------------------------------------------------------ #
    # verify / logout
    # ------------------------------------------------------------------ #
    def verify_token_now(self, token: str) -> Principal:
        """Verify a bearer token against its ``sessions`` row and the database.

        Three independent things must hold:

        1. the JWT signature and ``exp`` (HS256 over the derived key);
        2. the ``sessions`` row named by ``jti`` exists, is **not revoked** and
           has not expired;
        3. the account is still usable (not soft-deleted, not disabled, not
           locked).

        Mapping (总纲 §4.4.1): an expired token **or** an expired session row is
        ``AUTH_EXPIRED``; a bad signature, an unknown ``jti``, a revoked session,
        a ``sub``/``user_id`` mismatch or an unusable account is ``AUTH_INVALID``
        (a revocation is not an expiry); a locked account is ``RATE_LIMITED``,
        the same code :meth:`login_now` returns for that state.
        """
        claims = decode_token(token)
        moment = self.now()
        session_id = str(claims.get("jti") or "")
        try:
            subject = int(str(claims.get("sub")))
        except (TypeError, ValueError) as exc:
            raise AdapterError(
                ErrorCode.AUTH_INVALID,
                "凭证的 sub 声明不是用户 ID（总纲 §4.4.1 AUTH_INVALID）。",
                details={"reason": "malformed_subject"},
            ) from exc

        with session_scope_for(self.session_factory) as session:
            row = session.scalar(
                select(UserSession).where(UserSession.session_id == session_id)
            )
            if row is None:
                raise AdapterError(
                    ErrorCode.AUTH_INVALID,
                    "凭证对应的会话不存在（sessions.session_id 未找到）"
                    "（总纲 §4.4.1 AUTH_INVALID）。",
                    details={"reason": "unknown_session", "session_id": session_id},
                )
            if row.revoked_at is not None:
                # Logout sets revoked_at; the token is dead even though its exp
                # may still be in the future — that is AUTH_INVALID, not
                # AUTH_EXPIRED.
                revoked_at = _as_utc(row.revoked_at)
                raise AdapterError(
                    ErrorCode.AUTH_INVALID,
                    "凭证已注销（sessions.revoked_at 非空）"
                    "（总纲 §4.4.1 AUTH_INVALID）。",
                    details={
                        "reason": "session_revoked",
                        "session_id": session_id,
                        "revoked_at": revoked_at.isoformat() if revoked_at else None,
                    },
                )
            expires_at = _as_utc(row.expires_at) or moment
            if expires_at <= moment:
                raise AdapterError(
                    ErrorCode.AUTH_EXPIRED,
                    f"会话已过期（sessions.expires_at={expires_at.isoformat()}，"
                    "总纲 裁决 C-9：TTL 由 security_configs.session_timeout_minutes "
                    "派生）（总纲 §4.4.1 AUTH_EXPIRED）。",
                    details={"reason": "session_expired", "session_id": session_id},
                )
            if int(row.user_id) != subject:
                raise AdapterError(
                    ErrorCode.AUTH_INVALID,
                    "凭证与会话的用户不一致（jti 指向的会话不属于 sub）"
                    "（总纲 §4.4.1 AUTH_INVALID）。",
                    details={"reason": "session_user_mismatch", "session_id": session_id},
                )
            user = session.get(User, subject)
            if user is None or user.deleted_at is not None:
                raise AdapterError(
                    ErrorCode.AUTH_INVALID,
                    "账号不存在或已删除（总纲 §4.4.1 AUTH_INVALID）。",
                    details={"reason": "account_missing", "user_id": subject},
                )
            if user.status == UserStatus.DISABLED.value:
                raise AdapterError(
                    ErrorCode.AUTH_INVALID,
                    "账号已被禁用（users.status='disabled'）"
                    "（总纲 §4.4.1 AUTH_INVALID）。",
                    details={"reason": "account_disabled", "user_id": subject},
                )
            if self._is_locked(user, moment):
                deadline = _as_utc(user.locked_until)
                raise AdapterError(
                    ErrorCode.RATE_LIMITED,
                    "账号已锁定，凭证暂不可用"
                    + (f"至 {deadline.isoformat()}" if deadline else "（需管理员解锁）")
                    + "（总纲 §4.2.5）。",
                    details={
                        "reason": "account_locked",
                        "user_id": subject,
                        "locked_until": deadline.isoformat() if deadline else None,
                    },
                )
            roles, permissions = self._grants_now(session, subject)
            return Principal(
                user_id=subject,
                username=str(user.username),
                roles=roles,
                permissions=frozenset(permissions),
                department=self._department_now(session, subject),
                expires_at=expires_at,
                session_id=session_id,
            )

    async def verify_token(self, token: str) -> Principal:
        """Async mirror of :meth:`verify_token_now`."""
        return await asyncio.to_thread(self.verify_token_now, token)

    def issue_token(
        self,
        *,
        user_id: int,
        username: str,
        session_id: str,
        expires_in: int,
        issued_at: datetime | None = None,
    ) -> str:
        """Thin method mirror of the module-level :func:`issue_token`."""
        return issue_token(
            user_id=user_id,
            username=username,
            session_id=session_id,
            expires_in=expires_in,
            issued_at=issued_at if issued_at is not None else self.now(),
        )

    def logout_now(self, token: str) -> bool:
        """Revoke the token's ``sessions`` row; ``True`` when a row was found.

        ``exp`` is **not** enforced here: revoking an already-expired session is
        a no-op that should still succeed, and refusing it would leave
        ``revoked_at`` unset for a token that is merely stale.  The signature is
        still verified, so a caller cannot revoke a session it does not hold.

        ``users.is_online`` is cleared only when no other live session remains.
        """
        claims = _decode_claims(token, verify_exp=False)
        session_id = str(claims.get("jti") or "")
        moment = self.now()
        with session_scope_for(self.session_factory) as session:
            row = session.scalar(
                select(UserSession).where(UserSession.session_id == session_id)
            )
            if row is None:
                return False
            if row.revoked_at is None:
                row.revoked_at = moment
            remaining = session.scalar(
                select(func.count())
                .select_from(UserSession)
                .where(
                    UserSession.user_id == int(row.user_id),
                    UserSession.session_id != session_id,
                    UserSession.revoked_at.is_(None),
                    UserSession.expires_at > moment,
                )
            )
            if not remaining:
                user = session.get(User, int(row.user_id))
                if user is not None:
                    user.is_online = 0
            return True

    async def logout(self, token: str) -> bool:
        """Async mirror of :meth:`logout_now`."""
        return await asyncio.to_thread(self.logout_now, token)

    # ------------------------------------------------------------------ #
    # refresh (v1.2 §5.4) — rotation belongs here, not in the REST layer
    # ------------------------------------------------------------------ #
    def refresh_now(
        self,
        token: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthResult:
        """Rotate the session named by ``token`` and return its replacement.

        **Rotate, not extend** (v1.2 §5.4).  The ``sessions`` row named by the
        presented token's ``jti`` is revoked and a *new* row is written for the
        new token.  Extending the row in place would leave two live tokens for one
        session, because :meth:`verify_token_now` authenticates a token by its JWT
        signature plus the ``sessions`` row it names — deliberately **not** by
        re-hashing the token (see the module docstring) — so revoking the row is
        the only way to retire the old token.

        Revoke and insert happen in **one** transaction: a failure cannot leave
        the caller holding neither token.  The token is verified first, through
        the ordinary :meth:`verify_token_now` path, so every refusal keeps the
        code it already had (``AUTH_EXPIRED`` for an expired token,
        ``AUTH_INVALID`` for a bad signature, a revoked row or a disabled
        account).

        ``expires_in`` is ``security_configs.session_timeout_minutes × 60``
        (总纲 裁决 C-9), never a constant, and it is derived from **one** instant
        so ``sessions.expires_at`` and the JWT ``exp`` agree.  Only a **hash** of
        the new token is stored (总纲 §4.7.1).  总纲 §4.1.3 lists no prefix for
        ``sessions``, so the new id comes from :meth:`_new_session_id` — a
        prefix-free ``uuid4().hex`` — rather than ``new_id(...)``, which would
        invent a prefix the closed set forbids.

        :raises AdapterError: ``AUTH_INVALID`` with ``reason="missing_session_id"``
            when the token carries no ``jti``, and with
            ``reason="unknown_session"`` when the row it names is absent or
            already revoked.
        """
        principal = self.verify_token_now(token)
        previous_session_id = str(principal.session_id or "")
        if not previous_session_id:
            raise AdapterError(
                ErrorCode.AUTH_INVALID,
                "凭证没有会话标识（jti），无法刷新（总纲 §4.4.1 AUTH_INVALID）。",
                details={"reason": "missing_session_id"},
            )

        policy = self.security_policy_now()
        moment = self.now()
        expires_in = policy.session_ttl_seconds
        expires_at = moment + timedelta(seconds=expires_in)
        session_id = self._new_session_id()

        with session_scope_for(self.session_factory) as session:
            row = session.scalar(
                select(UserSession).where(
                    UserSession.session_id == previous_session_id
                )
            )
            if row is None or row.revoked_at is not None:
                raise AdapterError(
                    ErrorCode.AUTH_INVALID,
                    "会话不存在或已被注销，无法刷新（总纲 §4.4.1 AUTH_INVALID）。",
                    details={
                        "reason": "unknown_session",
                        "session_id": previous_session_id,
                    },
                )
            new_token = issue_token(
                user_id=principal.user_id,
                username=principal.username,
                session_id=session_id,
                expires_in=expires_in,
                issued_at=moment,
            )
            row.revoked_at = moment
            session.add(
                UserSession(
                    session_id=session_id,
                    user_id=int(principal.user_id),
                    # Only a hash is stored — ``sessions.token_hash`` is NOT NULL
                    # and 总纲 §4.7.1's spirit is that no plaintext credential is
                    # ever persisted.
                    token_hash=crypto.hash_secret(new_token),
                    ip_address=ip_address,
                    user_agent=user_agent,
                    expires_at=expires_at,
                )
            )
            session.flush()

        rotated = Principal(
            user_id=principal.user_id,
            username=principal.username,
            roles=principal.roles,
            permissions=principal.permissions,
            department=principal.department,
            expires_at=expires_at,
            session_id=session_id,
            token_type=principal.token_type,
        )
        return AuthResult(
            token=new_token,
            expires_in=expires_in,
            expires_at=expires_at,
            session_id=session_id,
            principal=rotated,
            token_type=principal.token_type,
        )

    async def refresh(
        self,
        token: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthResult:
        """Async mirror of :meth:`refresh_now`."""
        return await asyncio.to_thread(
            self.refresh_now,
            token,
            ip_address=ip_address,
            user_agent=user_agent,
        )


# ---------------------------------------------------------------------------
# process-wide singleton (mirrors get_task_service / get_registry)
# ---------------------------------------------------------------------------
_auth_service: AuthService | None = None


def get_auth_service() -> AuthService:
    """Process-wide :class:`AuthService` over the configured database."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


def reset_auth_service(service: AuthService | None = None) -> AuthService:
    """Replace the singleton (tests / reload)."""
    global _auth_service
    _auth_service = service if service is not None else AuthService()
    return _auth_service


# ---------------------------------------------------------------------------
# bootstrap: seed RBAC + the first super_admin
# ---------------------------------------------------------------------------
def _seed_rbac_in_session(session: Session) -> dict[str, int]:
    """Idempotently seed ``permissions`` / ``roles`` / ``role_permissions``.

    Mirrors ``sql/002_seed.sql`` sections 1–3 (and the ``security_configs``
    singleton of section 4.1, whose absence would otherwise force every caller
    onto the 裁决 C-9 defaults).  Only *missing* rows are inserted: an existing
    role→permission edit is never overwritten, which is what makes this safe to
    call on every startup.
    """
    created = {
        "permissions": 0,
        "roles": 0,
        "role_permissions": 0,
        "security_configs": 0,
    }

    known_permissions: dict[str, Permission] = {
        str(row.code): row for row in session.scalars(select(Permission)).all()
    }
    for code, name, module, action in PERMISSIONS:
        if code in known_permissions:
            continue
        row = Permission(code=code, name=name, module=module, action=action)
        session.add(row)
        known_permissions[code] = row
        created["permissions"] += 1
    session.flush()

    known_roles: dict[str, Role] = {
        str(row.code): row for row in session.scalars(select(Role)).all()
    }
    for definition in ROLE_DEFINITIONS:
        code = str(definition["code"])
        if code in known_roles:
            continue
        row = Role(
            code=code,
            name=str(definition["name"]),
            description=str(definition["description"]),
            is_system=1 if definition.get("is_system") else 0,
        )
        session.add(row)
        known_roles[code] = row
        created["roles"] += 1
    session.flush()

    existing_links = {
        (int(link.role_id), int(link.permission_id))
        for link in session.scalars(select(RolePermission)).all()
    }
    for role_code, patterns in ROLE_PERMISSION_MAP.items():
        role = known_roles.get(role_code)
        if role is None:  # pragma: no cover - ROLE_DEFINITIONS covers every key
            continue
        for code in expand_permission_patterns(patterns, PERMISSION_CODES):
            permission = known_permissions.get(code)
            if permission is None:  # pragma: no cover - expansion filters unknowns
                continue
            key = (int(role.id), int(permission.id))
            if key in existing_links:
                continue
            session.add(RolePermission(role_id=key[0], permission_id=key[1]))
            existing_links.add(key)
            created["role_permissions"] += 1

    if session.get(SecurityConfig, 1) is None:
        session.add(SecurityConfig(id=1))
        created["security_configs"] = 1

    session.flush()
    return created


def seed_rbac(session_factory: Callable[[], Session] | None = None) -> dict[str, int]:
    """Seed the RBAC tables from :mod:`app.core.constants` (idempotent).

    Exists because ``sql/002_seed.sql`` may never have run (a database created
    by ``Base.metadata.create_all`` has the tables but no rows), in which case
    no user could hold any permission at all.
    """
    service = AuthService(session_factory)
    with session_scope_for(service.session_factory) as session:
        return _seed_rbac_in_session(session)


def ensure_bootstrap_admin(
    session_factory: Callable[[], Session] | None = None,
    *,
    username: str = "admin",
    password: str | None = None,
    name: str | None = None,
) -> str:
    """Create the first ``super_admin`` — only on an empty ``users`` table.

    Without this call a fresh database is **unusable**: ``002_seed.sql`` seeds
    ``permissions`` / ``roles`` / ``role_permissions`` but no account at all
    (verified: ``users`` has 0 rows), so there is nobody to log in as.  The RBAC
    tables are therefore seeded here too, from
    :data:`app.core.constants.ROLE_PERMISSION_MAP` / ``PERMISSIONS``, so the
    bootstrap works whether or not the SQL seed ran.

    Idempotent and non-destructive: as soon as **any** user exists this returns
    a warning and changes nothing — it never resets an existing password.

    :param password: when omitted, a strong password is generated and the
        returned warning carries it after :data:`BOOTSTRAP_PASSWORD_MARKER`.
    :returns: a warning string for the operator.  The password appears in this
        **return value only** — this function never logs it and never writes it
        anywhere, so the caller must show it once and then discard it.
    """
    factory = (
        session_factory if session_factory is not None
        else AuthService().session_factory
    )
    target = str(username or "").strip()
    if not target:
        raise AdapterError(
            ErrorCode.VALIDATION_ERROR,
            "引导管理员的 username 不能为空（总纲 §4.4.2 VALIDATION_ERROR）。",
        )

    with session_scope_for(factory) as session:
        seeded = _seed_rbac_in_session(session)
        existing = int(
            session.scalar(select(func.count()).select_from(User)) or 0
        )
        if existing:
            return (
                f"users 表已有 {existing} 个账号，跳过引导管理员创建"
                f"（不重置任何密码；请求的 username={target!r} 未创建）。"
                f"本次幂等补种：permissions+{seeded['permissions']}、"
                f"roles+{seeded['roles']}、"
                f"role_permissions+{seeded['role_permissions']}。"
            )

        # Read the policy in the same transaction: _seed_rbac_in_session just
        # ensured the singleton row, so it is present unless the caller's schema
        # lacks the table.
        policy = SecurityPolicy()
        row = session.get(SecurityConfig, 1)
        if row is not None:
            policy = SecurityPolicy.from_row(row)

        generated = password is None
        secret = generate_password() if generated else str(password)
        violation = password_policy_error(secret, policy)
        if violation:
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR,
                f"引导管理员密码不符合安全策略：{violation}",
                details={"reason": "weak_password"},
            )

        admin = User(
            username=target,
            name=str(name or target),
            password_hash=hash_password(secret),
            status=UserStatus.ENABLED.value,
            is_online=0,
        )
        session.add(admin)
        session.flush()

        super_admin = session.scalar(
            select(Role).where(Role.code == SUPER_ADMIN_ROLE)
        )
        if super_admin is None:  # pragma: no cover - _seed_rbac_in_session creates it
            raise AdapterError(
                ErrorCode.INTERNAL_ERROR,
                f"角色 {SUPER_ADMIN_ROLE!r} 缺失，引导管理员无法授权"
                "（总纲 §4.8.3）。",
            )
        session.add(
            UserRole(user_id=int(admin.id), role_id=int(super_admin.id))
        )

    origin = "自动生成" if generated else "调用方提供"
    return (
        f"已在空库上创建引导管理员 username={target!r}（角色 "
        f"{SUPER_ADMIN_ROLE}），密码来源：{origin}。"
        f"{BOOTSTRAP_PASSWORD_MARKER}{secret}\n"
        "请立即登录并修改该密码。该密码只出现在本返回值中，本函数不会把它写入"
        "任何日志或文件；请打印一次后丢弃。"
        f"本次同时补种：permissions+{seeded['permissions']}、"
        f"roles+{seeded['roles']}、"
        f"role_permissions+{seeded['role_permissions']}、"
        f"security_configs+{seeded['security_configs']}。"
    )
