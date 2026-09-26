"""The auth / RBAC seam — v1.2 §38 「Authentication → RBAC」, 总纲 §4.4.1 / §4.8.

:mod:`app.mcp.dispatcher` calls its ``Authorizer`` **before anything else**
(before tool validation, before capability resolution, before the adapter):

.. code-block:: text

    MCP Request -> Authentication -> RBAC -> Tool Validation -> Capability ...

This module is the implementation of that seam.  :func:`make_authorizer` returns
a callable matching :data:`app.mcp.context.Authorizer` exactly, so wiring it is
one constructor argument::

    dispatcher = ToolDispatcher(authorizer=make_authorizer(get_auth_service()))

What it checks, in the order the flow diagram implies
----------------------------------------------------
1. **Authentication** — no credential is ``AUTH_REQUIRED``; a malformed,
   tampered or revoked one is ``AUTH_INVALID``; an expired one is
   ``AUTH_EXPIRED`` (总纲 §4.4.1).  ``security_configs.api_auth_required = 0``
   disables this gate entirely (总纲 裁决 C-13) — the flag's documented meaning is
   「未认证调用是否一律拒绝」, so it is a single switch, not a per-code exception.
2. **RBAC** — ``AuthRequest.permission`` (from
   :func:`app.mcp.capabilities.required_permission`) must be held by the
   principal.  The code is looked up in the **closed** 总纲 §4.8.2 set first: a
   code outside it is refused rather than "checked", because an unknown code can
   never be a permission this platform grants.
3. **Instance data scope** — 《MIDAS API 对接规范》§2.5.4 item 5.  When the call
   carries ``client_id``, the principal must additionally be allowed to use that
   ``midas_clients`` row (``owner_id`` / ``visibility``).

Why step 3 needs no new permission code
---------------------------------------
The 对接规范 ruling is explicit: 总纲 §4.8.2's permission list is a **closed
set**, therefore the instance-ownership check 「不得引入新的权限码，必须实现为
既有权限码之上的数据范围过滤（data-scope filter）」.  So this module never
mints a code such as ``client:read``; it layers a boolean predicate
(:func:`scope_allows`) on top of the §4.8.2 check that already ran, and reports a
refusal with the existing ``PERMISSION_DENIED``.  Removing the scope check would
change *which instances* a caller can reach, never *which permission* it holds —
which is exactly the shape the ruling asks for.

No new error codes either: every refusal here is a 总纲 §4.4 member
(``AUTH_REQUIRED`` / ``AUTH_INVALID`` / ``AUTH_EXPIRED`` / ``PERMISSION_DENIED``)
raised as an :class:`~app.adapters.errors.AdapterError`, which the dispatcher
turns into the §4.3.2 MCP envelope.
"""

import inspect
from typing import Any, Callable, Mapping

from app.adapters.errors import AdapterError
from app.core.constants import PERMISSION_CODES, MidasVisibility
from app.core.errors import ErrorCode
from app.mcp.context import AuthRequest, Authorizer, client_id_of
from app.services.auth_service import AuthService, InstanceScope, Principal

__all__ = [
    "Principal",
    "InstanceScope",
    "PrincipalResolver",
    "PERMISSION_CODE_SET",
    "scope_allows",
    "resolve_principal",
    "make_authorizer",
]


#: 总纲 §4.8.2 — the closed permission set.  A code outside it is not a
#: permission this platform can grant, so the RBAC step refuses instead of
#: performing a lookup that can never succeed.
PERMISSION_CODE_SET: frozenset[str] = frozenset(PERMISSION_CODES)


#: How a caller supplies a credential when ``AuthRequest.principal`` is empty —
#: typically a transport adapter reading an ``Authorization`` header.  It may
#: return ``None`` (no credential), a bearer token ``str``, a ``Mapping`` with a
#: ``token`` / ``access_token`` key, or an already-resolved
#: :class:`~app.services.auth_service.Principal`, and it may be ``async``.
PrincipalResolver = Callable[[AuthRequest], Any]


# ---------------------------------------------------------------------------
# instance data scope (对接规范 §2.5.4 item 5)
# ---------------------------------------------------------------------------
def scope_allows(scope: InstanceScope, principal: Principal) -> bool:
    """True when ``principal`` may use the MIDAS instance described by ``scope``.

    《MIDAS API 对接规范》§2.5.4 item 5 — the visibility rule, verbatim:

    ==============  ====================================================
    ``visibility``   usable by
    ==============  ====================================================
    ``private``      the registering user only (``owner_id``)
    ``department``   a principal whose department matches ``department``
    ``public``       anyone who passed the §4.8.2 permission check
    ==============  ====================================================

    Every other case fails **closed**: an unknown ``visibility`` value (the
    column carries a 总纲 §4.2.5 CHECK, so this means corrupted data), a
    ``private`` row with no owner, or a ``department`` row whose label or
    principal department is unknown all return ``False``.  §2.5.4 is explicit
    that cross-tenant access 「必须显式授予，不得假定」, so "unknown" is never
    treated as "same".

    The two sides of the ``department`` rule are ``scope.department``
    (``midas_clients.department``) and ``principal.department``
    (``users.department``, 总纲 §4.2.5); they match **by value**, so the label is
    a shared vocabulary rather than a foreign key.

    This predicate is the whole of the data-scope filter: it grants nothing on
    its own and introduces **no** permission code (总纲 §4.8.2 is closed).
    """
    visibility = (scope.visibility or "").strip().lower()
    if visibility == MidasVisibility.PUBLIC.value:
        return True
    if visibility == MidasVisibility.PRIVATE.value:
        return scope.owner_id is not None and int(scope.owner_id) == int(
            principal.user_id
        )
    if visibility == MidasVisibility.DEPARTMENT.value:
        if scope.department is None or principal.department is None:
            return False
        return scope.department == principal.department
    return False


def _credential_of(candidate: Any) -> Any:
    """Extract a token / principal from a ``Mapping`` credential, else pass through."""
    if isinstance(candidate, Mapping):
        for key in ("token", "access_token", "bearer", "authorization"):
            value = candidate.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return None
    return candidate


def _strip_scheme(token: str) -> str:
    """Drop a ``Bearer`` prefix from an ``Authorization`` header value."""
    text = token.strip()
    if text.lower().startswith("bearer "):
        return text[7:].strip()
    return text


async def resolve_principal(
    auth_service: AuthService,
    request: AuthRequest,
    *,
    principal_resolver: PrincipalResolver | None = None,
) -> Principal:
    """Resolve the request's principal, or raise the right 总纲 §4.4.1 code.

    Accepted inputs, in order: an already-resolved :class:`Principal` (its
    ``expires_at`` is re-checked here, because a principal object may have been
    cached by the caller), a bearer token ``str``, a ``Mapping`` carrying one, or
    whatever ``principal_resolver`` returns when ``request.principal`` is empty.
    """
    candidate = request.principal
    if candidate is None and principal_resolver is not None:
        candidate = principal_resolver(request)
        if inspect.isawaitable(candidate):
            candidate = await candidate

    if isinstance(candidate, Principal):
        if candidate.is_expired():
            raise AdapterError(
                ErrorCode.AUTH_EXPIRED,
                "凭证已过期（Principal.expires_at 已过，总纲 §4.4.1 AUTH_EXPIRED）。",
                details={
                    "reason": "token_expired",
                    "user_id": candidate.user_id,
                    "expires_at": candidate.expires_at.isoformat(),
                },
            )
        return candidate

    credential = _credential_of(candidate)
    if isinstance(credential, str):
        token = _strip_scheme(credential)
        if not token:
            raise AdapterError(
                ErrorCode.AUTH_REQUIRED,
                "未提供凭证（Authorization 头为空，总纲 §4.4.1 AUTH_REQUIRED）。",
                details={"reason": "empty_credential"},
            )
        return await auth_service.verify_token(token)

    if credential is None:
        raise AdapterError(
            ErrorCode.AUTH_REQUIRED,
            "未提供凭证：本调用没有携带 Bearer Token，"
            "且没有 principal_resolver 能从传输层取得它"
            "（总纲 §4.4.1 AUTH_REQUIRED；v1.2 §38 第一步 Authentication）。",
            details={"reason": "missing_credential", "tool": request.tool},
        )

    raise AdapterError(
        ErrorCode.AUTH_INVALID,
        f"无法识别的凭证类型 {type(credential).__name__}；"
        "只接受 Bearer Token 字符串或已解析的 Principal"
        "（总纲 §4.4.1 AUTH_INVALID）。",
        details={"reason": "unusable_credential", "type": type(credential).__name__},
    )


# ---------------------------------------------------------------------------
# the authorizer
# ---------------------------------------------------------------------------
def _require_permission(principal: Principal, request: AuthRequest) -> None:
    """The 总纲 §4.8.2 check (RBAC step of v1.2 §38)."""
    code = str(request.permission or "").strip()
    if not code:
        # ``required_permission()`` always returns a code, so an empty one means
        # the seam was called by hand with nothing to check; allowing it keeps
        # the hook usable as a pure authentication gate.
        return
    if code not in PERMISSION_CODE_SET:
        raise AdapterError(
            ErrorCode.PERMISSION_DENIED,
            f"权限码 {code!r} 不在总纲 §4.8.2 的封闭集合内，无法授予"
            "（总纲 §0.3 / 裁决 A-3：不得新增权限码）。",
            details={
                "reason": "unknown_permission_code",
                "permission": code,
                "tool": request.tool,
                "action": request.action,
            },
        )
    if not principal.has_permission(code):
        raise AdapterError(
            ErrorCode.PERMISSION_DENIED,
            f"权限不足：需要 {code}（总纲 §4.8.2），"
            f"principal roles={list(principal.roles)} 未持有该权限"
            "（总纲 §4.4.1 PERMISSION_DENIED；v1.2 §38 第二步 RBAC）。",
            details={
                "reason": "missing_permission",
                "permission": code,
                "tool": request.tool,
                "action": request.action,
                "roles": list(principal.roles),
                "user_id": principal.user_id,
            },
        )


async def _require_instance_scope(
    auth_service: AuthService,
    principal: Principal,
    request: AuthRequest,
) -> None:
    """《MIDAS API 对接规范》§2.5.4 item 5 — the instance data-scope filter.

    Runs **after** the §4.8.2 permission check, never instead of it: the two are
    叠加生效 (additive), as §2.5.4 requires.  No permission code is invented; the
    refusal is the existing ``PERMISSION_DENIED``.

    A refusal caused by a **missing department label** is spelled out rather than
    left as a bare denial: when the principal has no ``users.department``
    (总纲 §4.2.5) or the ``department``-scoped instance carries no label, the
    message names which half is missing and what an administrator must set, and
    ``details`` carries ``reason`` / ``client_id`` / ``scope_department`` /
    ``principal_department``.  The code is unchanged (总纲 §4.4 is closed) — a
    caller can only fix what it can see, and an opaque ``PERMISSION_DENIED`` is
    how the missing column stayed invisible.

    A ``client_id`` that is present but not an integer is left alone: the tool
    schema declares it ``integer`` (V2.1 §7.2 / §8.2), so the dispatcher's own
    schema validation rejects it moments later with ``VALIDATION_ERROR``, which
    is the more accurate code than anything this seam could pick.
    """
    arguments = request.arguments if isinstance(request.arguments, Mapping) else {}
    if arguments.get("client_id") is None:
        return
    client_id = client_id_of(arguments)
    if client_id is None:
        return

    scope = await auth_service.instance_scope(client_id)
    if scope is None:
        # Unknown instance: refused as PERMISSION_DENIED rather than
        # RESOURCE_NOT_FOUND so that the seam never confirms or denies the
        # existence of another tenant's registration (对接规范 §2.5.4 item 5).
        raise AdapterError(
            ErrorCode.PERMISSION_DENIED,
            f"client_id={client_id} 不存在或不可见；"
            "实例归属校验失败（对接规范 §2.5.4 第 5 条：数据范围过滤，"
            "不新增权限码）。",
            details={
                "reason": "unknown_instance",
                "client_id": client_id,
                "tool": request.tool,
                "action": request.action,
                "user_id": principal.user_id,
            },
        )
    if scope_allows(scope, principal):
        return

    visibility = (scope.visibility or "").strip().lower()
    details: dict[str, Any] = {
        "reason": "instance_out_of_scope",
        "client_id": client_id,
        "visibility": scope.visibility,
        "owner_id": scope.owner_id,
        "department": scope.department,
        "scope_department": scope.department,
        "principal_department": principal.department,
        "tool": request.tool,
        "action": request.action,
        "user_id": principal.user_id,
    }

    if visibility == MidasVisibility.DEPARTMENT.value:
        # 对接规范 §2.5.4 item 5's department rule needs a label on **both**
        # sides, and a bare PERMISSION_DENIED is exactly what let the missing
        # ``users.department`` column hide for so long: the caller could not tell
        # "wrong department" from "no department at all".  Both halves are named
        # below.  The code stays 总纲 §4.4.1's PERMISSION_DENIED (总纲 §4.8.2 /
        # §4.4 are closed sets); only ``details`` carries the specifics.
        if principal.department is None:
            details["reason"] = "department_unassigned"
            raise AdapterError(
                ErrorCode.PERMISSION_DENIED,
                f"无权使用 MIDAS 实例 client_id={client_id}：该实例是部门实例"
                f"（visibility='department'，department={scope.department!r}），"
                "但当前账号没有分配部门（users.department IS NULL），"
                "无法与实例所属部门匹配。请管理员为该账号设置 users.department"
                "（总纲 §4.2.5）。未分配部门时一律拒绝，绝不假定与实例同部门"
                "（《MIDAS API 对接规范》§2.5.4 第 5 条：跨租户访问必须显式授予，"
                "不得假定）。",
                details=details,
            )
        if scope.department is None:
            details["reason"] = "instance_department_unset"
            raise AdapterError(
                ErrorCode.PERMISSION_DENIED,
                f"无权使用 MIDAS 实例 client_id={client_id}：该实例声明为部门实例"
                "（visibility='department'）却没有登记部门标签"
                "（midas_clients.department IS NULL，"
                f"principal.department={principal.department!r}），"
                "没有任何主体能与它匹配。请管理员补全该实例的 "
                "midas_clients.department（《MIDAS API 对接规范》§2.5.4 第 5 条："
                "不得假定）。",
                details=details,
            )

    raise AdapterError(
        ErrorCode.PERMISSION_DENIED,
        f"无权使用 MIDAS 实例 client_id={client_id}"
        f"（visibility={scope.visibility!r}，owner_id={scope.owner_id}，"
        f"department={scope.department!r}）；"
        "对接规范 §2.5.4 第 5 条要求实例归属校验与 assistant:* / tool:* 权限"
        "叠加生效，且该过滤不引入新权限码（总纲 §4.8.2 封闭集合）。",
        details=details,
    )


def make_authorizer(
    auth_service: AuthService,
    *,
    principal_resolver: PrincipalResolver | None = None,
) -> Authorizer:
    """Build the :data:`app.mcp.context.Authorizer` for ``auth_service``.

    The returned callable is ``async``: every step after the first needs a
    database round trip (the ``sessions`` row, the RBAC join, the
    ``midas_clients`` row), and :class:`~app.services.auth_service.AuthService`
    hands each of those to a worker thread.  ``ToolDispatcher._authorize`` awaits
    an awaitable result, so this is exactly the shape the seam documents.

    Returning ``None`` allows the call to continue to tool validation; raising
    :class:`~app.adapters.errors.AdapterError` refuses it with a 总纲 §4.4 code.

    One failure is deliberately **not** mapped onto a §4.4 code: an unset
    ``STRUCTAI_MASTER_KEY``.  :func:`app.services.auth_service.signing_key`
    raises :class:`RuntimeError` there, and that propagates — a missing master
    key is a deployment fault (总纲 §4.7.1), not a bad credential, and answering
    ``AUTH_INVALID`` would disguise it as a user error.
    """

    async def authorizer(request: AuthRequest) -> None:
        policy = await auth_service.security_policy()
        if not policy.api_auth_required:
            # 总纲 裁决 C-13: api_auth_required = 0 means an unauthenticated call
            # is not refused at all.  It is a single switch, so the whole gate
            # (authentication + RBAC + data scope) is skipped rather than only
            # the credential check — checking permissions against a principal
            # that was never resolved would refuse every call anyway.
            return

        principal = await resolve_principal(
            auth_service, request, principal_resolver=principal_resolver
        )
        _require_permission(principal, request)
        await _require_instance_scope(auth_service, principal, request)
        # Write the resolved identity back onto the request.  The seam's return
        # type is ``None`` (raise to refuse, return to allow), so without this the
        # concrete ``Principal`` would be discarded and no downstream handler
        # could attribute the call — which is why ``tasks.requested_by`` was
        # always NULL and the audit chain (总纲 §4.1.5) had a hole in it.
        # ``AuthRequest`` is a plain mutable dataclass, so this is the seam's
        # documented way of handing the caller back what it resolved.
        request.principal = principal

    return authorizer
