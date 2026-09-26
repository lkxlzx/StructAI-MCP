"""MCP Tool Dispatcher — v1.2 §38.

The documented flow, step for step::

    MCP Request
        ↓
    Authentication          ← documented seam (Authorizer), see below
        ↓
    RBAC                    ← same seam; the required 总纲 §4.8.2 code is on
                              AuthRequest.permission
        ↓
    Tool Validation         ← jsonschema against the tool's own schema
        ↓
    Capability Resolver     ← V2.1 §16
        ↓
    Adapter Registry        ← V2.1 §21
        ↓
    Interface Mapping       ← the Capability row (endpoint / wrapper / root key)
        ↓
    Adapter                 ← the four tool handlers
        ↓
    MIDAS API
        ↓
    Normalize Result        ← AdapterResult.to_llm_payload()
        ↓
    MCP Response            ← 总纲 §4.3.2 MCP envelope

Three rules this module enforces rather than documents:

1. **The envelope is exactly 总纲 §4.3.2** — ``success`` / ``request_id`` /
   ``tool`` / ``status`` / ``data`` / ``task_id`` / ``warnings`` / ``errors``,
   always all eight keys.  The REST envelope (``code`` / ``message`` /
   ``timestamp``) must never appear here (总纲 §4.3.2 「两种信封不得混用」,
   v1.2 §37).
2. **``raw_status`` / ``raw_response`` never reach the LLM** — V2.1 §19 字段约束.
   The only source of envelope content is ``AdapterResult.to_llm_payload()``.
3. **``additionalProperties: false`` is enforced here, not by the SDK.**
   The MCP SDK derives a tool's input schema from the handler's signature, and a
   *flat* signature produces **no** ``additionalProperties`` key at all (i.e.
   permissive).  V2.1 §6.1 / 裁决 B-4 require ``false`` at every layer, so the
   dispatcher validates the incoming arguments against the authoritative schema
   from :mod:`app.mcp.capabilities` before anything else happens.  See
   :func:`validate_arguments`.

Authentication / RBAC seam
--------------------------
``authorizer`` is a callable ``(AuthRequest) -> None | Awaitable[None]``.  It is
``None`` by default, which means **no authentication is performed** — the seam
exists so Phase 2 wires ``mcp_client_credentials`` (裁决 B-1) and the 总纲 §4.8.2
permission codes into exactly one place, without touching the routing.  A
refusal is an :class:`~app.adapters.errors.AdapterError` carrying a 总纲 §4.4
code (``AUTH_REQUIRED`` / ``AUTH_INVALID`` / ``AUTH_EXPIRED`` /
``PERMISSION_DENIED`` / ``CONFIRMATION_INVALID``).
"""

import inspect
from dataclasses import dataclass
from typing import Any, Final, Mapping

from app.adapters.base import AdapterResult
from app.adapters.errors import AdapterError
from app.adapters.registry import AdapterRegistry, get_registry
from app.core.constants import TaskStatus
from app.core.errors import ErrorCode
from app.core.ids import new_id
from app.mcp.capabilities import (
    TOOL_EXECUTE,
    TOOL_MODEL,
    TOOL_NAMES,
    TOOL_QUERY,
    Capability,
    required_permission,
)
from app.mcp.capability import CapabilityResolver
from app.mcp.routing import select_adapter_code
from app.mcp.context import (
    AuthRequest,
    Authorizer,
    DispatchContext,
    client_id_of,
)
from app.mcp.tools import TOOL_HANDLERS, TOOL_SCHEMAS
from app.services.task_service import TaskService, get_task_service

__all__ = [
    "ENVELOPE_FIELDS",
    "ToolDispatcher",
    "ValidationIssue",
    "validate_arguments",
    "validate_payload",
    "build_envelope",
    "error_entry",
    "JSONSCHEMA_AVAILABLE",
    "SCHEMA_WARNINGS",
    "get_dispatcher",
    "reset_dispatcher",
]


#: 总纲 §4.3.2 — the MCP envelope, in order.  Every response carries all eight.
ENVELOPE_FIELDS: Final[tuple[str, ...]] = (
    "success",
    "request_id",
    "tool",
    "status",
    "data",
    "task_id",
    "warnings",
    "errors",
)


# ---------------------------------------------------------------------------
# validation (jsonschema when available, small fallback otherwise)
# ---------------------------------------------------------------------------
try:  # pragma: no cover - the branch taken depends on the environment
    from jsonschema import Draft202012Validator as _Draft202012Validator

    JSONSCHEMA_AVAILABLE: bool = True
except ImportError:  # pragma: no cover - exercised only without jsonschema
    _Draft202012Validator = None  # type: ignore[assignment]
    JSONSCHEMA_AVAILABLE = False

#: Schemas that failed ``check_schema`` (should stay empty; asserted by tests).
SCHEMA_WARNINGS: list[str] = []

_VALIDATORS: dict[str, Any] = {}


@dataclass(frozen=True)
class ValidationIssue:
    """One rejected argument path, with a message safe to show the model."""

    path: str
    message: str

    def render(self) -> str:
        return f"{self.path}: {self.message}" if self.path else self.message


_JSON_TYPES: Final[dict[str, tuple[type, ...]]] = {
    "object": (dict,),
    "array": (list, tuple),
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "null": (type(None),),
}


def _type_ok(value: Any, allowed: list[str]) -> bool:
    """JSON-type check used by the fallback validator only."""
    for name in allowed:
        if name == "integer" and isinstance(value, bool):
            continue
        if name == "number" and isinstance(value, bool):
            continue
        types = _JSON_TYPES.get(name)
        if types and isinstance(value, types):
            return True
    return False


def _minimal_validate(schema: Mapping[str, Any], instance: Any) -> list[ValidationIssue]:
    """Hand-rolled validator used when ``jsonschema`` is unavailable.

    Deliberately shallow: required keys, ``additionalProperties: false``, and
    top-level ``type`` / ``enum``.  It exists so a missing dependency degrades to
    "weaker validation", never to "no validation" — V2.1 §6.1 makes
    ``additionalProperties: false`` mandatory, and silently skipping it would be
    the worst possible failure mode.
    """
    issues: list[ValidationIssue] = []
    declared_top = schema.get("type")
    top_allowed = (
        [declared_top] if isinstance(declared_top, str) else list(declared_top or [])
    )
    branches = schema.get("anyOf")
    null_ok = "null" in top_allowed or (
        isinstance(branches, list)
        and any(
            isinstance(branch, Mapping) and branch.get("type") == "null"
            for branch in branches
        )
    )

    if instance is None:
        # ``query`` / ``data`` are nullable by contract (V2.1 §7.2 / §8.2).
        return [] if null_ok else [ValidationIssue("", "参数不能为 null")]
    if not isinstance(instance, Mapping):
        if top_allowed and _type_ok(instance, top_allowed):
            return []
        return [
            ValidationIssue("", f"参数类型必须是 {top_allowed or ['object']}")
        ]

    for key in schema.get("required", []) or []:
        if instance.get(key) is None:
            issues.append(ValidationIssue("", f"缺少必填字段 {key!r}"))
    properties = schema.get("properties") or {}
    if schema.get("additionalProperties") is False:
        for key in instance:
            if key not in properties:
                issues.append(ValidationIssue("", f"不允许多余字段 {key!r}"))
    for key, value in instance.items():
        sub = properties.get(key)
        if not isinstance(sub, Mapping) or value is None:
            continue
        enum = sub.get("enum")
        if isinstance(enum, list) and value not in enum:
            issues.append(ValidationIssue(str(key), f"{value!r} 不在枚举 {enum} 中"))
        declared = sub.get("type")
        if declared is None:
            continue
        allowed = [declared] if isinstance(declared, str) else list(declared)
        if not _type_ok(value, allowed):
            issues.append(ValidationIssue(str(key), f"类型必须是 {allowed}"))
    return issues


def _validator_for(tool: str) -> Any | None:
    """Cached Draft 2020-12 validator for a tool's published schema."""
    if not JSONSCHEMA_AVAILABLE:
        return None
    if tool in _VALIDATORS:
        return _VALIDATORS[tool]
    schema = TOOL_SCHEMAS.get(tool)
    if schema is None:
        return None
    try:
        _Draft202012Validator.check_schema(schema)
    except Exception as exc:  # noqa: BLE001 - a bad schema must not 500 a call
        SCHEMA_WARNINGS.append(f"{tool}: check_schema 失败 -> {exc}")
        _VALIDATORS[tool] = None
        return None
    validator = _Draft202012Validator(schema)
    _VALIDATORS[tool] = validator
    return validator


def validate_arguments(
    tool: str, arguments: Mapping[str, Any]
) -> list[ValidationIssue]:
    """Validate one tool call against its **authoritative** schema.

    This is where ``additionalProperties: false`` actually bites.  The MCP SDK's
    own argument model is derived from the handler signature and, for a flat
    signature, omits ``additionalProperties`` entirely — so an unknown key would
    be silently dropped instead of refused.  V2.1 §6.1 / 裁决 B-4 forbid that, and
    the check therefore runs here, against the schema generated from the
    capability table.
    """
    schema = TOOL_SCHEMAS.get(tool)
    if schema is None:
        return [ValidationIssue("", f"未知的 MCP tool {tool!r}（v1.2 §37）")]
    validator = _validator_for(tool)
    if validator is None:
        return _minimal_validate(schema, arguments)
    issues: list[ValidationIssue] = []
    for error in sorted(
        validator.iter_errors(dict(arguments)),
        key=lambda item: [str(part) for part in item.absolute_path],
    ):
        path = "/".join(str(part) for part in error.absolute_path)
        issues.append(ValidationIssue(path, error.message))
    return issues


def _allows_null(schema: Mapping[str, Any]) -> bool:
    """True when ``schema`` admits ``null`` (top-level ``type`` or an anyOf branch)."""
    declared = schema.get("type")
    if declared == "null" or (isinstance(declared, list) and "null" in declared):
        return True
    branches = schema.get("anyOf")
    return isinstance(branches, list) and any(
        isinstance(branch, Mapping) and branch.get("type") == "null"
        for branch in branches
    )


def _unwrap_nullable(schema: Mapping[str, Any]) -> Mapping[str, Any]:
    """``{"anyOf": [{"type": "null"}, X]}`` -> ``X``.

    The capability rows declare their payload as "null or the real filter"
    (V2.1 §7.2), so the *narrowed* half is what the second validation should
    apply — and it is the half the fallback validator can understand.
    """
    branches = schema.get("anyOf")
    if not isinstance(branches, list) or len(branches) != 2:
        return schema
    nulls = [
        branch
        for branch in branches
        if isinstance(branch, Mapping) and branch.get("type") == "null"
    ]
    others = [branch for branch in branches if branch not in nulls]
    if len(nulls) == 1 and len(others) == 1 and isinstance(others[0], Mapping):
        return others[0]
    return schema


def validate_payload(
    capability: Capability, payload: Any
) -> list[ValidationIssue]:
    """V2.1 §6.2 / §9.3 second validation against ``request_schema_json``.

    ``midas_execute.data`` is the only free-form field in the MCP surface, and
    §9.3 is explicit that it is not a bypass: the resolved Capability's request
    schema is the real gate, and a failure is ``VALIDATION_ERROR`` — never a
    downgrade to ``MIDAS_API_ERROR``, and never a pass-through to MIDAS.
    """
    schema = capability.request_schema
    if not schema:
        return []
    if payload is None:
        return [] if _allows_null(schema) else [ValidationIssue("", "载荷不能为 null")]
    effective = _unwrap_nullable(schema)
    if not JSONSCHEMA_AVAILABLE:
        return _minimal_validate(effective, payload)
    try:
        _Draft202012Validator.check_schema(effective)
        validator = _Draft202012Validator(effective)
    except Exception as exc:  # noqa: BLE001 - see _validator_for
        SCHEMA_WARNINGS.append(f"{capability.code}: payload schema 无效 -> {exc}")
        return []
    return [
        ValidationIssue(
            "/".join(str(part) for part in error.absolute_path),
            error.message,
        )
        for error in validator.iter_errors(payload)
    ]


# ---------------------------------------------------------------------------
# envelope
# ---------------------------------------------------------------------------
def error_entry(
    code: ErrorCode | str,
    message: str = "",
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """One element of the envelope's ``errors`` array (V2.1 §11 failure example)."""
    resolved = code.value if isinstance(code, ErrorCode) else str(code)
    return {
        "code": resolved,
        "message": message or resolved,
        "details": dict(details or {}),
    }


def build_envelope(
    *,
    success: bool,
    request_id: str,
    tool: str,
    status: str,
    data: Any = None,
    task_id: str | None = None,
    warnings: list[str] | None = None,
    errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the 总纲 §4.3.2 MCP envelope — all eight keys, always."""
    return {
        "success": bool(success),
        "request_id": request_id,
        "tool": tool,
        "status": status,
        "data": data,
        "task_id": task_id,
        "warnings": list(warnings or []),
        "errors": list(errors or []),
    }


def _capability_details(capability: Capability | None) -> dict[str, Any]:
    """Context for an ``errors[].details`` entry (V2.1 §11 failure example)."""
    if capability is None:
        return {}
    return {
        "capability": capability.code,
        "adapter": capability.adapter_code,
        "resource": capability.resource,
        "action": capability.action,
        "endpoint": capability.endpoint,
    }


def _attach_latency(data: Any, latency_ms: int | None) -> Any:
    """V2.1 §19: 「``latency_ms`` …… MCP 信封中该值放入 ``data``」."""
    if latency_ms is None or not isinstance(data, dict):
        return data
    if "latency_ms" in data:
        return data
    return {**data, "latency_ms": latency_ms}


# ---------------------------------------------------------------------------
# the dispatcher
# ---------------------------------------------------------------------------
class ToolDispatcher:
    """Implements v1.2 §38 for the four V2.1 tools."""

    def __init__(
        self,
        *,
        registry: AdapterRegistry | None = None,
        resolver: CapabilityResolver | None = None,
        task_service: TaskService | None = None,
        authorizer: Authorizer | None = None,
    ) -> None:
        self._registry: AdapterRegistry = registry if registry is not None else get_registry()
        self._resolver: CapabilityResolver = (
            resolver
            if resolver is not None
            else CapabilityResolver(self._registry)
        )
        self._tasks: TaskService = (
            task_service if task_service is not None else get_task_service()
        )
        self._authorizer: Authorizer | None = authorizer

    # ------------------------------------------------------------------ #
    @property
    def registry(self) -> AdapterRegistry:
        return self._registry

    @property
    def resolver(self) -> CapabilityResolver:
        return self._resolver

    @property
    def tasks(self) -> TaskService:
        return self._tasks

    # ------------------------------------------------------------------ #
    async def dispatch(
        self,
        tool: str,
        arguments: Mapping[str, Any] | None = None,
        *,
        request_id: str | None = None,
        principal: Any = None,
    ) -> dict[str, Any]:
        """Run one MCP tool call and return the 总纲 §4.3.2 envelope."""
        args: dict[str, Any] = dict(arguments or {})
        tool_name = str(tool or "").strip()
        # 总纲 §4.1.3: the request-tracking prefix is ``req_`` — **not** ``request_``.
        # The closed-set guard in app.core.ids rejects anything else, which is
        # exactly how this mistake surfaced (50 tests, one root cause).
        rid = request_id or args.pop("request_id", None) or new_id("req")

        if tool_name not in TOOL_NAMES:
            return build_envelope(
                success=False,
                request_id=rid,
                tool=tool_name,
                status=TaskStatus.FAILED.value,
                errors=[
                    error_entry(
                        ErrorCode.MCP_CLIENT_ERROR,
                        f"未知的 MCP tool {tool_name!r}；v1.2 §37 只暴露 "
                        f"{list(TOOL_NAMES)}。",
                        {"tool": tool_name},
                    )
                ],
            )

        action = str(args.get("action") or "").strip().lower()
        resource = _resource_of(tool_name, args)
        adapter_code = args.get("adapter")
        if adapter_code is not None:
            adapter_code = str(adapter_code)

        # --- Authentication / RBAC (documented seam) ------------------- #
        auth_request = AuthRequest(
            request_id=rid,
            tool=tool_name,
            action=action,
            resource=resource,
            permission=required_permission(tool_name, action),
            arguments=args,
            principal=principal,
        )
        try:
            await self._authorize(auth_request)
        except AdapterError as exc:
            return self._failure(rid, tool_name, exc, None)

        # The authorizer resolves the opaque credential into a concrete
        # ``Principal`` and writes it back onto the request (app/mcp/auth.py).
        # Handlers get that resolved identity, not the raw token — it is what
        # ``tasks.requested_by`` needs so a task can be attributed to its caller
        # and a stream can be filtered to its owner (总纲 §4.1.5).
        resolved_principal = auth_request.principal

        # --- Tool validation (总纲 §4.3.2 / V2.1 §6.1) ------------------ #
        issues = validate_arguments(tool_name, args)
        if issues:
            return build_envelope(
                success=False,
                request_id=rid,
                tool=tool_name,
                status=TaskStatus.FAILED.value,
                errors=[
                    error_entry(
                        ErrorCode.VALIDATION_ERROR,
                        "参数未通过 Tool Schema 校验（V2.1 §6.1："
                        "additionalProperties=false、required、enum 均在 "
                        "app.mcp.capabilities 生成的 Schema 上强制）。",
                        {
                            "issues": [issue.render() for issue in issues],
                            "tool": tool_name,
                        },
                    )
                ],
            )

        # --- Instance / adapter routing (多产品多租户路由框架 §三) ------ #
        # The chain is **instance -> adapter -> capability**, never the reverse.
        # This is the only place that decides *where* the call goes, and it
        # refuses rather than guessing when several products are registered —
        # a wrong guess would be a silent write to the wrong model.
        try:
            target_adapter = select_adapter_code(self._registry, tool_name, adapter_code)
        except AdapterError as exc:
            return self._failure(rid, tool_name, exc, None)

        # --- Capability Resolver (V2.1 §16) ---------------------------- #
        try:
            capability = self._resolver.resolve(
                target_adapter, tool_name, action, resource
            )
        except AdapterError as exc:
            return self._failure(rid, tool_name, exc, None)

        # --- Adapter Registry (V2.1 §21) ------------------------------- #
        try:
            adapter = self._resolver.adapter_for(capability)
        except AdapterError as exc:
            return self._failure(rid, tool_name, exc, capability)

        # --- payload second validation (V2.1 §6.2 / §9.3) -------------- #
        payload = _payload_of(tool_name, args)
        payload_issues = validate_payload(capability, payload)
        if payload_issues:
            return build_envelope(
                success=False,
                request_id=rid,
                tool=tool_name,
                status=TaskStatus.FAILED.value,
                errors=[
                    error_entry(
                        ErrorCode.VALIDATION_ERROR,
                        f"{capability.code} 的载荷未通过 Capability.request_schema "
                        "二次校验（V2.1 §6.2 裁决 B-4 / §9.3：data 是唯一开放字段，"
                        "但绝不是免校验通道；失败一律 VALIDATION_ERROR）。",
                        {
                            **_capability_details(capability),
                            "issues": [issue.render() for issue in payload_issues],
                        },
                    )
                ],
            )

        # --- Adapter / Interface mapping ------------------------------- #
        context = DispatchContext(
            request_id=rid,
            tool=tool_name,
            capability=capability,
            adapter=adapter,
            registry=self._registry,
            tasks=self._tasks,
            resolver=self._resolver,
            midas_client_id=client_id_of(args),
            permission=required_permission(tool_name, action),
            principal=resolved_principal,
            arguments=args,
        )

        # Gate 4's advisory warnings belong to **every** tool, not just
        # ``midas_query``.  The resolver applies the product-scope gate for all
        # four, but it cannot write to the envelope — only a handler can, and the
        # dispatcher builds the context *after* ``resolve()``.  So the warnings
        # are lifted here, once, rather than repeated in each of the four tool
        # modules (总纲 §4.2.11: ``unknown`` is admitted optimistically **with**
        # an ``unverified`` warning, so a tool that drops it is not compliant).
        # ``midas_task`` yields ``[]`` — gate 4 is skipped for platform-owned rows.
        for scope_warning in self._resolver.product_scope_warnings(
            capability, target_adapter
        ):
            context.warn(scope_warning)

        handler = TOOL_HANDLERS.get(tool_name)
        if handler is None:  # pragma: no cover - TOOL_NAMES implies a handler
            return build_envelope(
                success=False,
                request_id=rid,
                tool=tool_name,
                status=TaskStatus.FAILED.value,
                errors=[
                    error_entry(
                        ErrorCode.MCP_SERVER_ERROR,
                        f"tool {tool_name!r} 没有注册 handler",
                        {"tool": tool_name},
                    )
                ],
            )

        try:
            outcome = await handler(args, context)
        except AdapterError as exc:
            envelope = self._failure(rid, tool_name, exc, capability)
            envelope["warnings"] = list(context.warnings)
            return envelope
        except Exception as exc:  # noqa: BLE001 - MCP layer boundary
            return build_envelope(
                success=False,
                request_id=rid,
                tool=tool_name,
                status=TaskStatus.FAILED.value,
                warnings=list(context.warnings),
                errors=[
                    error_entry(
                        ErrorCode.MCP_SERVER_ERROR,
                        f"分发 {tool_name} 时发生未预期异常：{type(exc).__name__}: {exc}",
                        _capability_details(capability),
                    )
                ],
            )

        return self._normalize(rid, tool_name, capability, context, outcome)

    # ------------------------------------------------------------------ #
    async def call(
        self,
        tool: str,
        arguments: Mapping[str, Any] | None = None,
        *,
        request_id: str | None = None,
        principal: Any = None,
    ) -> dict[str, Any]:
        """Alias of :meth:`dispatch` (reads better at some call sites)."""
        return await self.dispatch(
            tool, arguments, request_id=request_id, principal=principal
        )

    # ------------------------------------------------------------------ #
    async def _authorize(self, request: AuthRequest) -> None:
        """Run the auth/RBAC seam, sync or async (v1.2 §38)."""
        if self._authorizer is None:
            return
        outcome = self._authorizer(request)
        if inspect.isawaitable(outcome):
            await outcome

    def _failure(
        self,
        request_id: str,
        tool: str,
        error: AdapterError,
        capability: Capability | None,
    ) -> dict[str, Any]:
        """Envelope for a raised :class:`AdapterError`."""
        return build_envelope(
            success=False,
            request_id=request_id,
            tool=tool,
            status=TaskStatus.FAILED.value,
            errors=[
                error_entry(error.code, error.message, error.details or _capability_details(capability))
            ],
        )

    def _normalize(
        self,
        request_id: str,
        tool: str,
        capability: Capability,
        context: DispatchContext,
        outcome: Any,
    ) -> dict[str, Any]:
        """Turn a handler outcome into the MCP envelope.

        ``AdapterResult`` goes through ``to_llm_payload()`` — the **only** form
        V2.1 §19 allows near the LLM — so ``raw_status`` / ``raw_response`` cannot
        appear in the envelope even by accident.
        """
        if isinstance(outcome, AdapterResult):
            payload = outcome.to_llm_payload()
            warnings = list(payload["warnings"]) + list(context.warnings)
            errors: list[dict[str, Any]] = []
            if not payload["success"]:
                errors.append(
                    error_entry(
                        payload["error_code"] or ErrorCode.INTERNAL_ERROR,
                        payload["error_message"] or "",
                        _capability_details(capability),
                    )
                )
            return build_envelope(
                success=payload["success"],
                request_id=request_id,
                tool=tool,
                status=payload["status"],
                data=_attach_latency(payload["data"], payload["latency_ms"]),
                task_id=payload["task_id"],
                warnings=warnings,
                errors=errors,
            )

        if isinstance(outcome, Mapping):
            return build_envelope(
                success=True,
                request_id=request_id,
                tool=tool,
                status=TaskStatus.SUCCESS.value,
                data=dict(outcome),
                warnings=list(context.warnings),
            )

        return build_envelope(
            success=False,
            request_id=request_id,
            tool=tool,
            status=TaskStatus.FAILED.value,
            warnings=list(context.warnings),
            errors=[
                error_entry(
                    ErrorCode.MCP_SERVER_ERROR,
                    f"{tool} 的 handler 返回了 {type(outcome).__name__}，"
                    "既不是 AdapterResult 也不是 Mapping",
                    _capability_details(capability),
                )
            ],
        )


# ---------------------------------------------------------------------------
# per-tool argument shape
# ---------------------------------------------------------------------------
def _resource_of(tool: str, arguments: Mapping[str, Any]) -> str | None:
    """The MCP resource for this call.

    ``midas_query`` calls it ``target`` (裁决 C-7 keeps ``capabilities`` there and
    out of the action enum); ``midas_model`` / ``midas_execute`` call it
    ``resource``; ``midas_task`` has no resource dimension at all.
    """
    if tool == TOOL_QUERY:
        value = arguments.get("target")
    elif tool in (TOOL_MODEL, TOOL_EXECUTE):
        value = arguments.get("resource")
    else:
        return None
    return str(value) if value is not None else None


def _payload_of(tool: str, arguments: Mapping[str, Any]) -> Any:
    """The payload the capability's ``request_schema`` validates (V2.1 §6.2)."""
    if tool == TOOL_QUERY:
        return arguments.get("query")
    if tool in (TOOL_MODEL, TOOL_EXECUTE):
        return arguments.get("data")
    return None


# ---------------------------------------------------------------------------
# Process-wide singleton
# ---------------------------------------------------------------------------
_dispatcher: ToolDispatcher | None = None


def get_dispatcher() -> ToolDispatcher:
    """Process-wide :class:`ToolDispatcher` (mirrors ``get_registry()``)."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = ToolDispatcher()
    return _dispatcher


def reset_dispatcher(dispatcher: ToolDispatcher | None = None) -> ToolDispatcher:
    """Replace the singleton (tests / reload)."""
    global _dispatcher
    _dispatcher = dispatcher if dispatcher is not None else ToolDispatcher()
    return _dispatcher
