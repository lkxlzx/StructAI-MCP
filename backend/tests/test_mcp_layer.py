"""Offline MCP-layer tests — **no live MIDAS required** (V2.1 §22 mock adapter).

Plain ``pytest`` only: async entry points are driven with ``asyncio.run`` so the
suite does not depend on ``pytest-asyncio`` being configured (matching
``tests/test_adapter_offline.py``).

What is proven here, and against which rule:

=================================================  ==============================
claim                                              依据
=================================================  ==============================
the four tool schemas' enums are **generated**      V2.1 §6.1 / 总纲 §0.4
``additionalProperties: false`` is enforced         V2.1 §6.2 裁决 B-4
an unknown ``(tool, action, resource)`` is          V2.1 §16.2
``CAPABILITY_NOT_SUPPORTED``
the MCP envelope is 总纲 §4.3.2 exactly            总纲 §4.3.2 / V2.1 §11
``raw_status`` / ``raw_response`` never leak         V2.1 §19 字段约束
``delete`` is per-id and the ``Assign`` body is     对接规范 §3.5 第 1 条 / §11.5.1
unreachable
``calculate`` returns a ``task_`` id                V2.1 §9.4 / 总纲 §4.1.4
per-``midas_client_id`` serialization = 1           V2.1 §26.5 / 对接规范 §2.5.2
no auto-retry after a write timeout                 V2.1 §26.5 / 对接规范 §3.5 第 5 条
``target=capabilities`` returns the table           裁决 C-7
``product_scope`` filters per instance (闸 4)       总纲 §4.9.2 闸 4 / §4.2.11
``unknown`` is admitted with a warning              总纲 §4.2.11
=================================================  ==============================
"""

import asyncio
import dataclasses
import json
from typing import Any

import pytest

from app.adapters.base import AdapterLifecycle, AdapterResult
from app.adapters.errors import AdapterError
from app.adapters.mock.adapter import MockAdapter
from app.adapters.registry import AdapterRegistry
from app.core.constants import (
    CAPABILITY_DOMAIN_VALUES,
    CAPABILITY_FEATURE_VALUES,
    PRODUCT_SCOPE_BY_PRODUCT,
    MidasProductScope,
    TaskStatus,
    TaskType,
)
from app.core.errors import ErrorCode
from app.core.ids import is_valid_id
from app.core.midas_config import MidasProduct
from app.mcp import capabilities as capabilities_module
from app.mcp import dispatcher as dispatcher_module
from app.mcp import server as server_module
from app.mcp.capabilities import (
    capability_rows,
    DISPATCH_DELETE,
    TOOL_EXECUTE,
    TOOL_MODEL,
    TOOL_NAMES,
    TOOL_QUERY,
    TOOL_TASK,
    Capability,
    actions_for,
    capability_table,
    query_filter_schemas,
    register_capability,
    reset_capabilities,
    resolve,
    resources_for,
)
from app.mcp.capability import CapabilityResolver, instance_product_scope
from app.mcp.context import DispatchContext
from app.mcp.dispatcher import (
    ENVELOPE_FIELDS,
    JSONSCHEMA_AVAILABLE,
    SCHEMA_WARNINGS,
    ToolDispatcher,
    validate_arguments,
)
from app.mcp.tools import execute as execute_tool
from app.mcp.tools import model as model_tool
from app.mcp.tools import query as query_tool
from app.mcp.tools import task as task_tool
from app.services.task_service import TaskService

#: V2.0's nine model resources (V2.1 §8.1).  Kept **only** to prove the published
#: enum is not this list: 裁决 recorded in V2.1 §6.3 makes the real MIDAS API
#: authoritative for the resource vocabulary.
V20_MODEL_RESOURCES = (
    "node",
    "element",
    "material",
    "section",
    "load",
    "boundary",
    "group",
    "coordinate_system",
    "property",
)

#: 对接规范 §4.1 / §11.6 — the live-verified outer-key semantics.
VERIFIED_OUTER_KEYS = {
    "load.create": ("node", "node"),  # /db/CNLD: outer key = 节点号
    "boundary.create": ("group", "group"),  # /db/CONS: outer key = 约束组号
    "node.create": ("self", "node"),  # own entity number
    "element.create": ("self", "element"),
    "load_case.create": ("self", "load_case"),
    "material.create": ("self", "self"),
}


def run(coro: Any) -> Any:
    """Drive one coroutine to completion (no pytest-asyncio dependency)."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# environment helpers
# ---------------------------------------------------------------------------
class Env:
    """One offline MCP stack: mock adapter + registry + tasks + dispatcher."""

    def __init__(
        self,
        *,
        model: dict[str, dict[str, Any]] | None = None,
        strict_put: bool = False,
        max_concurrency: int = 4,
        authorizer: Any = None,
    ) -> None:
        self.registry = AdapterRegistry()
        self.adapter = MockAdapter(
            code="midas_gen",
            software="MIDAS Gen",
            model=model,
            strict_put=strict_put,
        )
        self.registry.register(self.adapter)
        self.tasks = TaskService(max_concurrency=max_concurrency)
        self.resolver = CapabilityResolver(self.registry)
        self.dispatcher = ToolDispatcher(
            registry=self.registry,
            resolver=self.resolver,
            task_service=self.tasks,
            authorizer=authorizer,
        )

    def call(
        self,
        tool: str,
        arguments: dict[str, Any],
        principal: Any = None,
    ) -> dict[str, Any]:
        return run(self.dispatcher.dispatch(tool, arguments, principal=principal))

    def server(self) -> Any:
        return server_module.build_server(
            registry=self.registry,
            dispatcher=self.dispatcher,
            task_service=self.tasks,
        )


def env(**kwargs: Any) -> Env:
    return Env(**kwargs)


def seeded() -> Env:
    """Mock model with two nodes, so per-id delete is observable."""
    return Env(model={"NODE": {"1": {"X": 0.0}, "3": {"X": 6.0}}})


def issue_text(envelope: dict[str, Any]) -> str:
    return json.dumps(envelope["errors"], ensure_ascii=False)


def classified_row(
    adapter_code: str,
    code: str = "node.list",
    *,
    scope: str = "unknown",
    domain: str | None = None,
    feature: str | None = None,
) -> Capability:
    """Register one row with an explicit three-layer classification.

    总纲 §4.2.11 ships every row as ``product_scope='unknown'`` / ``domain=None`` /
    ``feature=None`` — filling them in is the classification loader's job.  A test
    that needs a *known* scope or domain therefore has to write the row it wants;
    ``reset_capabilities()`` puts the static declaration back afterwards.
    """
    row = dataclasses.replace(
        capability_table("midas_gen")[code],
        adapter_code=adapter_code,
        interface_code=f"{adapter_code}.{code}",
        product_scope=scope,
        domain=domain,
        feature=feature,
    )
    return register_capability(row, replace=True)


# ===========================================================================
# 1. the capability table (V2.1 §16.1 / §17)
# ===========================================================================
def test_capability_table_covers_the_live_verified_resources() -> None:
    model_resources = set(resources_for(TOOL_MODEL))
    for resource in (
        "project",
        "unit",
        "structure_type",
        "node",
        "element",
        "material",
        "section",
        "boundary",
        "load_case",
        "load",
        "group",
    ):
        assert resource in model_resources, resource

    query_targets = set(resources_for(TOOL_QUERY))
    for target in (
        "server",
        "client",
        "capabilities",
        "model",
        "node",
        "element",
        "material",
        "section",
        "load",
        "boundary",
        "group",
        "analysis",
        "result",
        "project",
    ):
        assert target in query_targets, target


def test_action_enums_match_v21_section_6_3() -> None:
    assert actions_for(TOOL_QUERY) == ["count", "get", "inspect", "list", "search"]
    assert actions_for(TOOL_MODEL) == [
        "create",
        "delete",
        "read",
        "update",
        "upsert",
        "validate",
    ]
    assert actions_for(TOOL_EXECUTE) == [
        "analysis",
        "calculate",
        "close_project",
        "command",
        "connect",
        "disconnect",
        "export",
        "generate_report",
        "import",
        "open_project",
        "save_project",
        "sync",
        "validate_model",
    ]
    assert actions_for(TOOL_TASK) == [
        "cancel",
        "events",
        "get",
        "list",
        "logs",
        "result",
        "retry",
    ]


def test_capabilities_is_a_target_never_an_action() -> None:
    """裁决 C-7: ``action=capabilities`` was removed from the action enum."""
    assert "capabilities" in resources_for(TOOL_QUERY)
    assert "capabilities" not in actions_for(TOOL_QUERY)
    with pytest.raises(AdapterError) as excinfo:
        resolve(TOOL_QUERY, "capabilities", "capabilities")
    assert excinfo.value.code == ErrorCode.CAPABILITY_NOT_SUPPORTED.value


def test_outer_key_means_is_derived_from_the_live_verified_guard() -> None:
    """对接规范 §4.1 / §11.6 — and the adapter stays the single source of truth."""
    table = capability_table("midas_gen")
    for code, (means, kind) in VERIFIED_OUTER_KEYS.items():
        assert table[code].outer_key_means == means, code
        assert table[code].outer_key_kind == kind, code

    from app.adapters.midas_gen.adapter import outer_key_means as adapter_outer_key_means

    for code in ("node.create", "load.create", "boundary.create", "element.create"):
        assert table[code].outer_key_kind == adapter_outer_key_means(table[code].endpoint)


def test_capability_codes_and_interfaces_are_unique() -> None:
    """Uniqueness is per ``(adapter_code, capability_code)`` — 裁决 B-3.

    The same ``code`` legitimately exists once per adapter (``node.list`` for gen,
    civil and cdn), so the check is on the composite key, not on the code alone.
    That composite key is exactly what the table used to lack, and its absence is
    why a second adapter's row silently overwrote the first.
    """
    rows = capability_rows()
    keys = [(row.adapter_code, row.code) for row in rows]
    assert len(keys) == len(set(keys)), "duplicate (adapter_code, code)"
    for row in rows:
        assert row.interface_code, row.code
        assert row.dispatch in capabilities_module.DISPATCH_HINTS, row.code
        # Every /db/* capability has a root key (V2.1 §17.3) and speaks the
        # ``Assign`` wrapper **when it carries a body**.  A GET carries none, so
        # ``request_wrapper`` is correctly ``None`` there (对接规范 §3.1).
        # /info/* and /doc/* are handled by other dispatches.
        if row.endpoint and row.endpoint.startswith("/db/"):
            expected_wrapper = None if row.method == "GET" else "Assign"
            assert row.request_wrapper == expected_wrapper, row.code
            assert row.response_root_key, row.code


def test_every_delete_capability_uses_the_per_id_dispatch() -> None:
    """对接规范 §3.5 第 1 条: the ``Assign``-body DELETE must not be reachable."""
    for row in capability_rows():
        if row.action == "delete" and row.tool == TOOL_MODEL:
            assert row.dispatch == DISPATCH_DELETE, row.code
            assert row.method == "DELETE", row.code


# ===========================================================================
# 2. schemas are generated from the table (V2.1 §6.1 / 总纲 §0.4)
# ===========================================================================
def test_every_tool_schema_enum_is_generated_from_the_table() -> None:
    for module in (query_tool, model_tool, execute_tool, task_tool):
        schema = module.SCHEMA
        assert schema["additionalProperties"] is False
        assert schema["properties"]["action"]["enum"] == actions_for(module.TOOL_NAME)
        assert schema["$id"] == f"structai://mcp/v2.1/tools/{module.TOOL_NAME}"


def test_model_resource_enum_is_not_the_v20_nine_value_list() -> None:
    """The real MIDAS API is authoritative for the resource vocabulary."""
    enum = model_tool.SCHEMA["properties"]["resource"]["enum"]
    assert enum == resources_for(TOOL_MODEL)
    assert "node" in enum
    assert set(enum) != set(V20_MODEL_RESOURCES)
    # 手册 02 章 has these endpoints; V2.0's nine-value list does not.
    assert {"load_case", "structure_type", "unit", "project"} <= set(enum)
    assert "coordinate_system" not in enum
    assert "property" not in enum


def test_query_target_enum_is_generated_from_the_table() -> None:
    schema = query_tool.SCHEMA
    assert schema["properties"]["target"]["enum"] == resources_for(TOOL_QUERY)
    # V2.1 §7.2 lists 14 targets; unit / structure_type are added because 手册
    # 02 章 has real endpoints for them and the model snapshot reads them.
    assert set(schema["properties"]["target"]["enum"]) >= {
        "server",
        "client",
        "capabilities",
        "model",
        "result",
        "unit",
        "structure_type",
    }


def test_execute_resource_enum_allows_null() -> None:
    """V2.1 §9.2 declares ``resource`` as ``["string","null"]`` with null in the enum."""
    prop = execute_tool.SCHEMA["properties"]["resource"]
    assert prop["type"] == ["string", "null"]
    assert None in prop["enum"]
    assert set(prop["enum"]) - {None} == set(resources_for(TOOL_EXECUTE))


def test_task_schema_uses_the_closed_task_vocabularies() -> None:
    """V2.1 §26.2 (types) / 总纲 §4.2.1 (statuses) — owned by app.core.constants."""
    props = task_tool.SCHEMA["properties"]
    assert set(props["type"]["enum"]) - {None} == {member.value for member in TaskType}
    assert set(props["status"]["enum"]) - {None} == {
        member.value for member in TaskStatus
    }


def test_a_newly_registered_capability_appears_in_the_generated_enum() -> None:
    """Proof that the enums are *generated*: add a row, rebuild, see it."""
    before = model_tool.SCHEMA["properties"]["resource"]["enum"]
    assert "weld" not in before
    register_capability(
        Capability(
            code="weld.create",
            tool=TOOL_MODEL,
            resource="weld",
            action="create",
            endpoint="/db/WELD",
            request_wrapper="Assign",
            response_root_key="WELD",
            dispatch=capabilities_module.DISPATCH_MODEL,
        )
    )
    try:
        rebuilt = model_tool.build_schema()
        assert "weld" in rebuilt["properties"]["resource"]["enum"]
        assert rebuilt["properties"]["resource"]["enum"] == resources_for(TOOL_MODEL)
        # ... and it is routable, without touching any tool code.
        assert (
            resolve(TOOL_MODEL, "create", "weld", adapter_code="midas_gen").code
            == "weld.create"
        )
    finally:
        reset_capabilities()
    assert model_tool.build_schema()["properties"]["resource"]["enum"] == before


def test_register_capability_refuses_a_duplicate_code() -> None:
    with pytest.raises(AdapterError) as excinfo:
        register_capability(capability_table("midas_gen")["node.create"])
    assert excinfo.value.code == ErrorCode.RESOURCE_CONFLICT.value


# ===========================================================================
# 3. the published server surface
# ===========================================================================
def test_server_publishes_exactly_four_tools_with_the_generated_schemas() -> None:
    environment = env()
    tools = run(environment.server().list_tools())
    assert [tool.name for tool in tools] == list(TOOL_NAMES)
    by_name = {tool.name: tool for tool in tools}
    for name in TOOL_NAMES:
        published = by_name[name].input_schema
        assert published["properties"]["action"]["enum"] == actions_for(name), name
        # V2.1 §6.1 / 裁决 B-4.  The SDK derives a schema from the handler
        # signature and omits additionalProperties for a flat signature, so the
        # authoritative schema is installed explicitly (app.mcp.server).
        assert published["additionalProperties"] is False, name
        assert published["type"] == "object"
    model_schema = by_name[TOOL_MODEL].input_schema
    assert model_schema["properties"]["resource"]["enum"] == resources_for(TOOL_MODEL)
    assert "node" in model_schema["properties"]["resource"]["enum"]
    assert model_schema["required"] == ["action", "resource"]


def test_published_schema_validation_is_clean() -> None:
    for name in TOOL_NAMES:
        validate_arguments(name, {})
    assert SCHEMA_WARNINGS == []


def test_server_calls_a_tool_end_to_end() -> None:
    """The real MCP dispatch path, without a transport (mcp 2.x ``call_tool``)."""
    environment = env()
    server = environment.server()
    result = run(
        server.call_tool("midas_query", {"target": "capabilities", "action": "list"})
    )
    assert not result.is_error
    payload = json.loads(result.content[0].text)
    assert payload["success"] is True
    assert payload["tool"] == TOOL_QUERY
    assert payload["data"]["total"] > 0


def test_server_refuses_an_enum_value_the_sdk_can_see() -> None:
    """The SDK-side ``Literal`` enums are the first line (belt and braces)."""
    from mcp.server.mcpserver.exceptions import ToolError

    environment = env()
    server = environment.server()
    with pytest.raises(ToolError):
        run(server.call_tool("midas_model", {"action": "wibble", "resource": "node"}))


# ===========================================================================
# 4. dispatcher-side validation (V2.1 §6.1 裁决 B-4)
# ===========================================================================
def test_extra_keys_are_rejected_even_though_the_sdk_would_allow_them() -> None:
    """总纲 §6 / V2.1 §6.1: ``additionalProperties: false`` at every layer.

    The MCP SDK's derived argument model *ignores* unknown keys, so a client
    could otherwise smuggle fields the router never sees.  The dispatcher
    validates against the authoritative schema, where they are refused.
    """
    environment = env()
    envelope = environment.call(
        TOOL_QUERY, {"target": "node", "action": "list", "bogus": 1}
    )
    assert envelope["success"] is False
    assert envelope["errors"][0]["code"] == ErrorCode.VALIDATION_ERROR.value
    assert "bogus" in issue_text(envelope)
    assert environment.adapter.request_log == []


def test_required_fields_and_enums_are_enforced() -> None:
    environment = env()
    missing = environment.call(TOOL_MODEL, {"action": "create"})
    assert missing["success"] is False
    assert "resource" in issue_text(missing)

    bad_action = environment.call(TOOL_MODEL, {"action": "wibble", "resource": "node"})
    assert bad_action["success"] is False
    assert bad_action["errors"][0]["code"] == ErrorCode.VALIDATION_ERROR.value

    bad_page = environment.call(
        TOOL_QUERY, {"target": "node", "action": "list", "page": 0}
    )
    assert bad_page["success"] is False


def test_the_fallback_validator_also_enforces_additional_properties(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without ``jsonschema`` the checks get weaker, never absent (V2.1 §6.1)."""
    monkeypatch.setattr(dispatcher_module, "JSONSCHEMA_AVAILABLE", False)
    issues = validate_arguments(TOOL_QUERY, {"target": "node", "action": "list", "x": 1})
    assert any("x" in issue.render() for issue in issues)
    assert any("target" in issue.render() for issue in validate_arguments(TOOL_QUERY, {}))

    # The §6.2 payload check must survive the fallback too — including the
    # nullable half of ``{"anyOf": [{"type": "null"}, <filter>]}``.
    capability = capability_table("midas_gen")["node.list"]
    assert dispatcher_module.validate_payload(capability, None) == []
    assert dispatcher_module.validate_payload(capability, {"group": "W2"}) == []
    payload_issues = dispatcher_module.validate_payload(capability, {"nope": 1})
    assert any("nope" in issue.render() for issue in payload_issues)


def test_the_payload_second_validation_narrows_to_the_target() -> None:
    """V2.1 §6.2 裁决 B-4: the resolved Capability owns the field set."""
    capability = capability_table("midas_gen")["node.list"]
    assert dispatcher_module.validate_payload(capability, {"x_min": 0}) == []
    issues = dispatcher_module.validate_payload(capability, {"no_such_filter": 1})
    assert issues, "node filter must reject an undefined field"


@pytest.mark.skipif(not JSONSCHEMA_AVAILABLE, reason="jsonschema not installed")
def test_jsonschema_is_available_and_used() -> None:
    """The brief asked for this to be checked rather than assumed."""
    assert JSONSCHEMA_AVAILABLE is True
    for name in TOOL_NAMES:
        # Every tool has at least one required field, so the empty call must fail.
        assert validate_arguments(name, {}) != [], name
    assert SCHEMA_WARNINGS == []


# ===========================================================================
# 5. capability resolution (V2.1 §16)
# ===========================================================================
def test_unknown_combination_is_capability_not_supported() -> None:
    """V2.1 §16.2 — every value below is a legal *enum* member; only the
    **combination** is unmapped, which is exactly what the resolver must refuse.

    (An illegal enum value never gets this far: the tool schema rejects it first,
    which ``test_required_fields_and_enums_are_enforced`` pins.)
    """
    environment = env()
    cases = (
        (TOOL_MODEL, {"action": "delete", "resource": "unit"}),  # §3.3: no DELETE
        (TOOL_MODEL, {"action": "create", "resource": "unit"}),  # §3.3: POST 不生效
        (TOOL_MODEL, {"action": "delete", "resource": "group"}),  # 手册: no DELETE
        (TOOL_QUERY, {"target": "capabilities", "action": "inspect"}),  # no /info
        (TOOL_QUERY, {"target": "result", "action": "inspect"}),  # /post/TABLE only
        (TOOL_EXECUTE, {"action": "calculate", "resource": "project"}),
        (TOOL_EXECUTE, {"action": "connect", "resource": "project"}),
    )
    for tool, arguments in cases:
        envelope = environment.call(tool, arguments)
        assert envelope["success"] is False, arguments
        assert (
            envelope["errors"][0]["code"] == ErrorCode.CAPABILITY_NOT_SUPPORTED.value
        ), arguments
        assert envelope["errors"][0]["details"]["tool"] == tool
    assert environment.adapter.request_log == []


def test_an_illegal_enum_value_never_reaches_the_resolver() -> None:
    """The published schema is the first gate (V2.1 §6.1)."""
    environment = env()
    for tool, arguments in (
        (TOOL_QUERY, {"target": "wibble", "action": "list"}),
        (TOOL_QUERY, {"target": "node", "action": "create"}),
        (TOOL_TASK, {"action": "subscribe"}),
    ):
        envelope = environment.call(tool, arguments)
        assert envelope["success"] is False, arguments
        assert envelope["errors"][0]["code"] == ErrorCode.VALIDATION_ERROR.value, arguments
    assert environment.adapter.request_log == []


def test_unknown_tool_is_an_mcp_client_error() -> None:
    environment = env()
    envelope = environment.call("midas_magic", {"action": "list"})
    assert envelope["success"] is False
    assert envelope["errors"][0]["code"] == ErrorCode.MCP_CLIENT_ERROR.value


def test_resolver_refuses_an_unregistered_adapter() -> None:
    resolver = CapabilityResolver(AdapterRegistry())
    with pytest.raises(AdapterError) as excinfo:
        resolver.resolve("midas_gen", TOOL_QUERY, "list", "node")
    assert excinfo.value.code == ErrorCode.ADAPTER_NOT_FOUND.value


def test_resolver_refuses_a_disabled_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = AdapterRegistry()
    adapter = MockAdapter(code="midas_gen")
    registry.register(adapter)
    resolver = CapabilityResolver(registry)
    # ``disabled`` is an **administrative** state (总纲 §4.2.5); no lifecycle stage
    # maps to it, so simulate an operator having turned the adapter off.
    monkeypatch.setattr(type(adapter), "status", property(lambda self: "disabled"))
    with pytest.raises(AdapterError) as excinfo:
        resolver.resolve("midas_gen", TOOL_QUERY, "list", "node")
    assert excinfo.value.code == ErrorCode.ADAPTER_UNAVAILABLE.value


def test_resolver_refuses_a_disabled_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``capabilities.enabled`` (V2.1 §16.1 / §16.2)."""
    environment = env()
    monkeypatch.setattr(
        capabilities_module, "DISABLED_CAPABILITIES", frozenset({"node.list"})
    )
    envelope = environment.call(TOOL_QUERY, {"target": "node", "action": "list"})
    assert envelope["success"] is False
    assert envelope["errors"][0]["code"] == ErrorCode.CAPABILITY_NOT_SUPPORTED.value


def test_an_unregistered_adapter_is_refused() -> None:
    """Routing runs **instance -> adapter -> capability** (多产品路由框架 §三).

    ``env()`` registers only ``midas_gen``, so asking for ``midas_civil`` names
    something that does not exist — ``ADAPTER_NOT_FOUND``, not
    ``CAPABILITY_NOT_SUPPORTED``.  The distinction matters: one means "no such
    instance is registered", the other means "that instance cannot do this".
    """
    environment = env()
    envelope = environment.call(
        TOOL_QUERY, {"target": "node", "action": "list", "adapter": "midas_civil"}
    )
    assert envelope["success"] is False
    assert envelope["errors"][0]["code"] == ErrorCode.ADAPTER_NOT_FOUND.value


def test_a_registered_adapter_that_lacks_the_capability_is_refused() -> None:
    """A registered instance that simply does not serve this capability.

    This is the shape the old ``adapter mismatch`` test was reaching for, now
    expressed the right way round: the adapter is selected **first**, and the
    capability is then resolved *within* it.  ``midas_civil`` is registered but
    the declaration holds no civil rows, so the combination does not exist.
    """
    environment = env()
    environment.registry.register(
        MockAdapter(code="midas_civil", software="MIDAS Civil")
    )
    envelope = environment.call(
        TOOL_QUERY, {"target": "node", "action": "list", "adapter": "midas_civil"}
    )
    assert envelope["success"] is False
    assert envelope["errors"][0]["code"] == ErrorCode.CAPABILITY_NOT_SUPPORTED.value


def test_several_adapters_without_a_choice_is_refused() -> None:
    """**The safety row** — ambiguity must never be resolved by guessing.

    With two products registered and no ``adapter`` given, picking one would be a
    guess, and a wrong guess is a *successful* write to the wrong model.  So the
    dispatcher refuses with ``VALIDATION_ERROR`` and names the choices.

    This replaces today's silent fallback to ``midas_gen`` — the path that let a
    caller believe it was driving Civil while it was actually driving Gen.
    """
    environment = env()
    environment.registry.register(
        MockAdapter(code="midas_civil", software="MIDAS Civil")
    )
    envelope = environment.call(TOOL_QUERY, {"target": "node", "action": "list"})
    assert envelope["success"] is False
    error = envelope["errors"][0]
    assert error["code"] == ErrorCode.VALIDATION_ERROR.value
    assert error["details"]["reason"] == "ambiguous_instance"
    assert set(error["details"]["registered"]) == {"midas_gen", "midas_civil"}


def test_each_adapter_reaches_its_own_product_url() -> None:
    """**The anti-cross-contamination guard.**

    Three adapters, three different base URLs, the same capability code declared
    for each.  Every call must reach exactly **its own** URL and touch no other
    adapter.  This is the property that makes "同时连接不同用户的不同产品" safe:
    the routing key is the adapter, so ``node.list`` on civil cannot resolve to
    the gen instance.

    A regression here would not raise — it would return another product's data
    with ``success=True``, which is why the assertion is on the recorded URLs and
    not merely on the envelope.
    """
    import dataclasses

    import httpx

    from app.adapters.midas_gen.adapter import MidasNxAdapter
    from app.core.midas_config import MidasConnection, MidasProduct

    class Recorder(httpx.AsyncBaseTransport):
        """Records the URL and answers from a canned body — no real network.

        The point under test is *which URL* a call reaches, so the transport must
        not depend on an instance being up; a canned ``/db/NODE`` body keeps the
        test offline and deterministic.
        """

        def __init__(self) -> None:
            self.calls: list[str] = []

        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            self.calls.append(str(request.url))
            return httpx.Response(200, json={"NODE": {"1": {"X": 0.0, "Y": 0.0, "Z": 0.0}}})

        async def aclose(self) -> None:
            return None

    products = {
        "gen": (MidasProduct.GEN, "http://localhost:3030"),
        "civil": (MidasProduct.CIVIL, "http://localhost:3030"),
        "cdn": (MidasProduct.DESIGNER, "http://localhost:3030"),
    }
    registry = AdapterRegistry()
    recorders: dict[str, Recorder] = {}
    for name, (product, base) in products.items():
        recorder = Recorder()
        recorders[name] = recorder
        registry.register(
            MidasNxAdapter(
                MidasConnection(
                    name=name,
                    software=f"MIDAS {name}",
                    product=product,
                    base_url=base,
                    mapi_key="k",
                    verify_tls=False,
                ),
                transport=recorder,
            )
        )

    # Declare the same capability for all three adapters — the multi-product
    # shape the extraction pipeline will produce.
    base_row = capability_table("midas_gen")["node.list"]
    for name in ("civil", "cdn"):
        register_capability(
            dataclasses.replace(
                base_row,
                adapter_code=f"midas_{name}",
                interface_code=f"midas_{name}.db.node.list",
            )
        )

    dispatcher = ToolDispatcher(registry=registry, task_service=TaskService())
    try:
        for name, (product, _base) in products.items():
            for recorder in recorders.values():
                recorder.calls.clear()

            envelope = run(
                dispatcher.dispatch(
                    TOOL_QUERY,
                    {"target": "node", "action": "list", "adapter": f"midas_{name}"},
                )
            )
            assert envelope["success"] is True, envelope

            expected = f"/{product.value}/db/NODE"
            assert recorders[name].calls, f"{name}: no request reached its adapter"
            assert all(expected in url for url in recorders[name].calls), (
                name,
                recorders[name].calls,
            )
            # …and no other adapter was touched
            for other, recorder in recorders.items():
                if other != name:
                    assert recorder.calls == [], (name, other, recorder.calls)
    finally:
        reset_capabilities()


# ===========================================================================
# 5b. 闸 4 —— 产品范围过滤（总纲 §4.9.2 闸 4 / §4.2.11）
#
# 两根轴，**不是同一根**：能力的 ``product_scope`` 是 ``gen / civil / designer /
# both / unknown``，实例的产品是 ``MidasProduct``（``gen / civil / cdn``）。
# 两者的连接只有一处 —— ``PRODUCT_SCOPE_BY_PRODUCT``（总纲 §4.2.11 的唯一真源）。
# ===========================================================================
def test_gate4_refuses_a_civil_capability_on_a_gen_instance() -> None:
    """``product_scope='civil'``：在 midas_gen 上拒绝，在 midas_civil 上可用。"""
    registry = AdapterRegistry()
    registry.register(MockAdapter(code="midas_gen", software="MIDAS Gen"))
    registry.register(MockAdapter(code="midas_civil", software="MIDAS Civil"))
    resolver = CapabilityResolver(registry)
    try:
        classified_row("midas_gen", scope="civil")
        classified_row("midas_civil", scope="civil")

        with pytest.raises(AdapterError) as excinfo:
            resolver.resolve("midas_gen", TOOL_QUERY, "list", "node")
        error = excinfo.value
        assert error.code == ErrorCode.CAPABILITY_NOT_SUPPORTED.value
        # 总纲 §4.4：**不新增错误码**，闸 4 复用 CAPABILITY_NOT_SUPPORTED；
        # 具体情况全部落在 details 里。
        assert error.details == {
            "reason": "product_scope_mismatch",
            "capability": "node.list",
            "product_scope": "civil",
            "instance_product": "gen",
            "adapter_code": "midas_gen",
        }

        # …同一个能力在它声明的产品上照常可用。
        allowed = resolver.resolve("midas_civil", TOOL_QUERY, "list", "node")
        assert allowed.product_scope == "civil"
    finally:
        reset_capabilities()


def test_gate4_refusal_reaches_the_envelope_with_the_details() -> None:
    """闸 4 的拒绝经 dispatcher 变成 ``CAPABILITY_NOT_SUPPORTED`` 信封。

    拒绝发生在**发请求之前**：连 Gen 却调 Civil 专属端点，MIDAS 只会回 404，
    而 404 在信封里看起来像「端点不存在」，不是「该能力不适用于本产品」。
    """
    environment = env()
    try:
        classified_row("midas_gen", scope="civil")
        envelope = environment.call(TOOL_QUERY, {"target": "node", "action": "list"})
        assert envelope["success"] is False
        entry = envelope["errors"][0]
        assert entry["code"] == ErrorCode.CAPABILITY_NOT_SUPPORTED.value
        assert entry["details"]["reason"] == "product_scope_mismatch"
        assert entry["details"]["instance_product"] == "gen"
        assert entry["details"]["adapter_code"] == "midas_gen"
        assert environment.adapter.request_log == [], "拒绝必须早于任何 MIDAS 调用"
    finally:
        reset_capabilities()


def test_gate4_both_is_allowed_on_either_product() -> None:
    """``both`` = 两个及以上产品均可用（总纲 §4.2.11 的取值表）。"""
    registry = AdapterRegistry()
    registry.register(MockAdapter(code="midas_gen", software="MIDAS Gen"))
    registry.register(MockAdapter(code="midas_civil", software="MIDAS Civil"))
    resolver = CapabilityResolver(registry)
    try:
        classified_row("midas_gen", scope="both")
        classified_row("midas_civil", scope="both")
        for adapter_code in ("midas_gen", "midas_civil"):
            assert (
                resolver.resolve(adapter_code, TOOL_QUERY, "list", "node").product_scope
                == "both"
            )
    finally:
        reset_capabilities()


def test_gate4_designer_scope_matches_midas_cdn_which_is_not_the_same_string() -> None:
    """**非恒等映射**：``MidasProduct.DESIGNER.value == "cdn"``，scope 却是 ``"designer"``。

    Civil Designer 的 URL 段是 ``cdn``（MIDAS 线上就是这么服务的），而能力分类把它
    记作 ``designer``（给人看的菜单名）。 把两根轴当成同一根（``product_scope ==
    adapter 产品值``）会**拒绝掉 Civil Designer 上的每一个 designer 能力** —— 这正是
    本用例钉住的那条陷阱。
    """
    assert MidasProduct.DESIGNER.value == "cdn"
    assert PRODUCT_SCOPE_BY_PRODUCT["cdn"] == MidasProductScope.DESIGNER.value == "designer"
    assert PRODUCT_SCOPE_BY_PRODUCT["cdn"] != MidasProduct.DESIGNER.value

    registry = AdapterRegistry()
    registry.register(MockAdapter(code="midas_cdn", software="MIDAS Civil Designer"))
    registry.register(MockAdapter(code="midas_gen", software="MIDAS Gen"))
    resolver = CapabilityResolver(registry)
    try:
        classified_row("midas_cdn", scope="designer")
        classified_row("midas_gen", scope="designer")

        assert instance_product_scope("midas_cdn") == "designer"
        allowed = resolver.resolve("midas_cdn", TOOL_QUERY, "list", "node")
        assert allowed.product_scope == "designer"

        with pytest.raises(AdapterError) as excinfo:
            resolver.resolve("midas_gen", TOOL_QUERY, "list", "node")
        assert excinfo.value.details["reason"] == "product_scope_mismatch"
        assert excinfo.value.details["instance_product"] == "gen"
    finally:
        reset_capabilities()


def test_gate4_reads_the_product_from_the_adapter_when_the_code_cannot_be_parsed() -> None:
    """来源 1（适配器的 ``product`` 属性）优先于来源 2（``midas_<product>`` 约定）。"""

    class StubAdapter:
        """一个编码不合约定、但自己知道产品的适配器。"""

        def __init__(self, code: str, product: MidasProduct) -> None:
            self._code = code
            self._product = product

        @property
        def code(self) -> str:
            return self._code

        @property
        def software(self) -> str:
            return "MIDAS Stub"

        @property
        def product(self) -> MidasProduct:
            return self._product

    registry = AdapterRegistry()
    registry.register(StubAdapter("midas_x", MidasProduct.CIVIL))
    resolver = CapabilityResolver(registry)
    try:
        classified_row("midas_x", scope="civil")
        # 代码约定判不出来 …
        assert instance_product_scope("midas_x") is None
        # …但适配器自己说了算。
        assert instance_product_scope("midas_x", registry.get("midas_x")) == "civil"
        assert resolver.resolve("midas_x", TOOL_QUERY, "list", "node").code == "node.list"
    finally:
        reset_capabilities()


def test_gate4_refuses_when_a_decision_is_needed_but_the_product_is_unknown() -> None:
    """判不出实例产品，而闸 4 **有判定要做** -> 拒绝（总纲 §4.9.2 闸 4）。

    ``midas_x`` 既没有 ``product`` 属性，后缀也不是任何 ``MidasProduct`` 值。
    能力声明了具体产品（``gen``），闸 4 必须比对，却无从比对 ——
    **没执行过的安全闸不算通过**，因此 fail closed。
    """
    registry = AdapterRegistry()
    registry.register(MockAdapter(code="midas_x", software="MIDAS X"))
    resolver = CapabilityResolver(registry)
    try:
        classified_row("midas_x", scope="gen")
        with pytest.raises(AdapterError) as excinfo:
            resolver.resolve("midas_x", TOOL_QUERY, "list", "node")
        error = excinfo.value
        assert error.code == ErrorCode.CAPABILITY_NOT_SUPPORTED.value
        assert error.details == {
            "reason": "instance_product_undeterminable",
            "capability": "node.list",
            "product_scope": "gen",
            "instance_product": None,
            "adapter_code": "midas_x",
        }
    finally:
        reset_capabilities()


def test_gate4_allows_when_there_is_no_decision_to_make_and_warns() -> None:
    """判不出实例产品，但闸 4 **没有判定要做** -> 放行 + 警告。

    ``unknown`` 与 ``both`` 容纳一切产品，本就不需要知道实例产品，所以
    「判不出产品」在这里不是拒绝的理由 —— 否则一个 code 不合约定的自定义适配器
    会**全线不可用**，连出厂即为 ``unknown`` 的全部行都调不通。

    但配置缺陷仍须可见，因此改为**警告**：一旦该能力的 ``product_scope`` 收敛为
    具体产品，本适配器将无法调用它。
    """
    registry = AdapterRegistry()
    registry.register(MockAdapter(code="midas_x", software="MIDAS X"))
    resolver = CapabilityResolver(registry)
    try:
        for scope in ("unknown", "both"):
            classified_row("midas_x", scope=scope)
            # 放行：不抛异常
            assert resolver.resolve("midas_x", TOOL_QUERY, "list", "node").code == "node.list"
            warnings = resolver.product_scope_warnings(
                capability_table("midas_x")["node.list"], "midas_x"
            )
            assert any("未经过" in w and "配置缺陷" in w for w in warnings), (
                scope,
                warnings,
            )
    finally:
        reset_capabilities()


def test_gate4_lives_in_the_resolver_so_every_tool_is_gated() -> None:
    """闸 4 在解析器里，因此四个 Tool 一视同仁 —— 不只是 ``midas_query``。"""
    registry = AdapterRegistry()
    registry.register(MockAdapter(code="midas_gen", software="MIDAS Gen"))
    resolver = CapabilityResolver(registry)
    try:
        classified_row("midas_gen", "node.read", scope="civil")
        with pytest.raises(AdapterError) as excinfo:
            resolver.resolve("midas_gen", TOOL_MODEL, "read", "node")
        assert excinfo.value.code == ErrorCode.CAPABILITY_NOT_SUPPORTED.value
        assert excinfo.value.details["product_scope"] == "civil"
    finally:
        reset_capabilities()


def test_gate4_unknown_is_admitted_optimistically_with_an_unverified_warning() -> None:
    """``unknown``（出厂默认）：乐观放行 + 信封 ``unverified`` 警告（总纲 §4.2.11）。

    理由记录在 §4.2.11：1,373 条端点无法一次探测完，而手册的产品标注不可信
    （对接规范 §3.5 第 15 条：声明「Civil 专属」的 47 个端点中 32 个在 Gen 上也能应答）。
    在验证完成前把大量能力隐藏起来，比带警告放行更糟 —— 但警告必须真的到达信封。
    """
    environment = env()
    assert capability_table("midas_gen")["node.list"].product_scope == "unknown"

    envelope = environment.call(TOOL_QUERY, {"target": "node", "action": "list"})
    assert envelope["success"] is True, envelope
    warnings = envelope["warnings"]
    assert any(
        "node.list" in warning
        and "unverified" in warning
        and "§4.2.11" in warning
        and "尚未对实机验证" in warning
        and "该能力在 gen 上并不存在" in warning
        for warning in warnings
    ), warnings


def test_gate4_is_skipped_for_platform_owned_capabilities() -> None:
    """``midas_task`` 没有实例也没有产品：**一个实例都没注册**时也必须可用。"""
    registry = AdapterRegistry()
    assert registry.codes() == []
    dispatcher = ToolDispatcher(registry=registry, task_service=TaskService())
    envelope = run(dispatcher.dispatch(TOOL_TASK, {"action": "list"}))
    assert envelope["success"] is True, envelope
    assert envelope["errors"] == []
    # 闸 4 不适用 -> 连 unverified 警告也不该有。
    assert not any("unverified" in warning for warning in envelope["warnings"])
    assert capability_table(None)["task.list"].adapter_code is None


# ===========================================================================
# 6. the MCP envelope (总纲 §4.3.2 / V2.1 §11)
# ===========================================================================
def test_envelope_shape_on_success() -> None:
    environment = env()
    envelope = environment.call(TOOL_QUERY, {"target": "node", "action": "list"})
    assert tuple(envelope) == ENVELOPE_FIELDS
    assert envelope["success"] is True
    assert envelope["tool"] == TOOL_QUERY
    assert envelope["status"] == TaskStatus.SUCCESS.value
    assert envelope["task_id"] is None
    assert envelope["errors"] == []
    assert isinstance(envelope["warnings"], list)
    # 总纲 §4.1.3: the request-tracking prefix is ``req_`` — not ``request_``.
    assert is_valid_id(envelope["request_id"], "req")


def test_envelope_shape_on_failure() -> None:
    environment = env()
    envelope = environment.call(TOOL_MODEL, {"action": "delete", "resource": "unit"})
    assert tuple(envelope) == ENVELOPE_FIELDS
    assert envelope["success"] is False
    assert envelope["status"] == TaskStatus.FAILED.value
    assert envelope["data"] is None
    assert envelope["task_id"] is None
    assert len(envelope["errors"]) == 1
    entry = envelope["errors"][0]
    assert set(entry) == {"code", "message", "details"}
    assert entry["code"] == ErrorCode.CAPABILITY_NOT_SUPPORTED.value
    assert entry["message"]


def test_envelope_never_uses_the_rest_shape() -> None:
    """总纲 §4.3.2: 两种信封不得混用."""
    environment = env()
    envelope = environment.call(TOOL_QUERY, {"target": "capabilities", "action": "list"})
    for rest_only in ("code", "message", "timestamp"):
        assert rest_only not in envelope


def test_raw_upstream_is_never_exposed() -> None:
    """V2.1 §19 字段约束: ``raw_status`` / ``raw_response`` 禁止直接回传 LLM."""
    environment = seeded()
    environment.adapter.script_response({"error": {"message": "Key Already Exist"}}, 400)
    envelope = environment.call(
        TOOL_MODEL,
        {"action": "create", "resource": "node", "data": {"1": {"X": 0.0}}},
    )
    text = json.dumps(envelope, ensure_ascii=False, default=str)
    assert "raw_response" not in text
    assert "raw_status" not in text
    assert envelope["success"] is False
    assert envelope["errors"][0]["code"] == ErrorCode.RESOURCE_CONFLICT.value


def test_normalization_only_reads_to_llm_payload() -> None:
    """The envelope is built from ``to_llm_payload()`` — the single choke point."""
    environment = env()
    context = DispatchContext(
        request_id="req_20260925_000001",
        tool=TOOL_QUERY,
        capability=capability_table("midas_gen")["node.list"],
        adapter=environment.adapter,
        registry=environment.registry,
        tasks=environment.tasks,
        resolver=environment.resolver,
    )
    result = AdapterResult.ok(
        {"items": []},
        raw_status=200,
        raw_response={"SENTINEL_RAW_RESPONSE": True},
    )
    envelope = environment.dispatcher._normalize(
        "req_20260925_000001", TOOL_QUERY, context.capability, context, result
    )
    text = json.dumps(envelope, ensure_ascii=False, default=str)
    assert "SENTINEL_RAW_RESPONSE" not in text
    assert envelope["success"] is True


def test_latency_goes_into_data() -> None:
    """V2.1 §19: 「``latency_ms`` …… MCP 信封中该值放入 ``data``」."""
    environment = env()

    async def fake_query(request: Any) -> AdapterResult:
        return AdapterResult.ok({"items": [], "total": 0}, latency_ms=42)

    environment.adapter.query = fake_query  # type: ignore[method-assign]
    envelope = environment.call(TOOL_QUERY, {"target": "node", "action": "list"})
    assert envelope["success"] is True
    assert envelope["data"]["latency_ms"] == 42


# ===========================================================================
# 7. midas_model — delete is per-id, the Assign body is unreachable
# ===========================================================================
def test_delete_routes_to_the_per_id_adapter_method() -> None:
    environment = seeded()
    envelope = environment.call(
        TOOL_MODEL, {"action": "delete", "resource": "node", "ids": ["1"]}
    )
    assert envelope["success"] is True
    assert envelope["data"]["mode"] == "per_id"
    assert envelope["data"]["deleted"] == ["1"]
    # 对接规范 §11.5.1: id 3 must survive, and the table-wiping trap must not fire.
    assert set(environment.adapter.model_store["NODE"]) == {"3"}
    assert environment.adapter.trap_fired is False
    assert environment.adapter.wiped_tables == []
    assert [entry["endpoint"] for entry in environment.adapter.calls(method="DELETE")] == [
        "/db/NODE/1"
    ]


def test_delete_accepts_a_single_id_scalar() -> None:
    environment = seeded()
    envelope = environment.call(
        TOOL_MODEL, {"action": "delete", "resource": "node", "id": 3}
    )
    assert envelope["success"] is True
    assert set(environment.adapter.model_store["NODE"]) == {"1"}
    assert environment.adapter.trap_fired is False


def test_the_assign_body_delete_form_is_unreachable() -> None:
    """对接规范 §3.5 第 1 条: ``Assign`` body -> 清空整张表."""
    environment = seeded()
    envelope = environment.call(
        TOOL_MODEL,
        {"action": "delete", "resource": "node", "data": {"Assign": {"1": None}}},
    )
    assert envelope["success"] is False
    assert envelope["errors"][0]["code"] == ErrorCode.VALIDATION_ERROR.value
    assert "清空整张表" in issue_text(envelope)
    # Nothing reached the adapter, and the table is intact.
    assert environment.adapter.request_log == []
    assert environment.adapter.trap_fired is False
    assert set(environment.adapter.model_store["NODE"]) == {"1", "3"}


def test_delete_without_an_id_is_refused_before_any_call() -> None:
    environment = seeded()
    envelope = environment.call(TOOL_MODEL, {"action": "delete", "resource": "node"})
    assert envelope["success"] is False
    assert envelope["errors"][0]["code"] == ErrorCode.VALIDATION_ERROR.value
    assert environment.adapter.request_log == []
    assert environment.adapter.trap_fired is False


def test_delete_all_is_not_reachable_through_the_tool() -> None:
    """``delete_all`` needs ``confirm=True``; the tool has no such action."""
    assert "delete_all" not in actions_for(TOOL_MODEL)
    assert "delete_all" not in model_tool.SCHEMA["properties"]["action"]["enum"]


def test_model_create_read_upsert_validate_round_trip() -> None:
    environment = env()
    created = environment.call(
        TOOL_MODEL,
        {
            "action": "create",
            "resource": "node",
            "data": {"1": {"X": 0.0, "Y": 0.0, "Z": 3.6}},
        },
    )
    assert created["success"] is True
    assert environment.adapter.request_log[-1]["method"] == "POST"
    assert environment.adapter.request_log[-1]["endpoint"] == "/db/NODE"

    read = environment.call(TOOL_QUERY, {"target": "node", "action": "list"})
    assert read["success"] is True
    assert read["data"]["total"] == 1
    assert read["data"]["resource"] == "node"  # 总纲 §4.6.1: MCP 单数名

    upserted = environment.call(
        TOOL_MODEL,
        {"action": "upsert", "resource": "node", "data": {"1": {"X": 1.0}}},
    )
    assert upserted["success"] is True

    validated = environment.call(
        TOOL_MODEL,
        {"action": "validate", "resource": "node", "data": {"2": {"X": 2.0, "Y": 0.0, "Z": 0.0}}},
    )
    assert validated["success"] is True
    assert validated["data"]["dry_run"] is True
    assert validated["data"]["body"]["Assign"]["2"]["X"] == 2.0


def test_model_write_uses_the_real_endpoint_not_the_mcp_name() -> None:
    """V2.1 §17.2: MCP says ``project``, MIDAS says ``/db/PJCF``."""
    environment = env()
    environment.call(TOOL_MODEL, {"action": "read", "resource": "project"})
    assert environment.adapter.request_log[-1]["endpoint"] == "/db/PJCF"


def test_model_cnld_write_warns_about_the_outer_key_trap() -> None:
    """对接规范 §4.1 / §11.6: the outer key is the node number, not a serial."""
    environment = env()
    envelope = environment.call(
        TOOL_MODEL,
        {
            "action": "create",
            "resource": "load",
            "data": {"2": {"ITEMS": [{"ID": 1, "LCNAME": "LC1", "FX": 10.0}]}},
        },
    )
    assert envelope["success"] is True
    assert any("节点号" in warning for warning in envelope["warnings"])


def test_model_validate_rejects_the_cnld_serial_misuse() -> None:
    environment = env()
    envelope = environment.call(
        TOOL_MODEL,
        {
            "action": "validate",
            "resource": "load",
            "data": {"2": {"ITEMS": [{"ID": 2, "LCNAME": "LC1"}]}},
        },
    )
    assert envelope["success"] is False
    assert envelope["errors"][0]["code"] == ErrorCode.VALIDATION_ERROR.value


# ===========================================================================
# 8. midas_query
# ===========================================================================
def test_query_capabilities_returns_the_capability_list() -> None:
    environment = env()
    envelope = environment.call(TOOL_QUERY, {"target": "capabilities", "action": "list"})
    assert envelope["success"] is True
    data = envelope["data"]
    assert data["total"] == len(capability_rows())
    codes = {row["code"] for row in data["items"]}
    assert {"node.create", "node.list", "task.get", "model.calculate"} <= codes
    assert data["adapters"] == ["midas_gen"]
    assert set(data["tools"]) == set(TOOL_NAMES)
    # The capability list is ours, not MIDAS's: no upstream call happened.
    assert environment.adapter.request_log == []


def test_query_capabilities_honours_the_documented_filter() -> None:
    environment = env()
    envelope = environment.call(
        TOOL_QUERY,
        {
            "target": "capabilities",
            "action": "list",
            "query": {"resource": "node", "action": "create"},
        },
    )
    assert envelope["success"] is True
    assert [row["code"] for row in envelope["data"]["items"]] == ["node.create"]


def test_query_capabilities_exposes_the_three_classification_layers() -> None:
    """总纲 §4.2.11：三层分类必须能从 ``target=capabilities`` 读到。"""
    environment = env()
    envelope = environment.call(TOOL_QUERY, {"target": "capabilities", "action": "list"})
    assert envelope["success"] is True
    item = next(
        row for row in envelope["data"]["items"] if row["code"] == "node.list"
    )
    assert item["product_scope"] == "unknown"  # 出厂默认，且是一等状态
    assert item["domain"] is None  # 分类加载器尚未填入
    assert item["feature"] is None


def test_the_published_capabilities_filter_advertises_the_closed_sets() -> None:
    """枚举必须出现在工具 schema 里：LLM 只能读到它被给出的合法取值。"""
    branch = query_filter_schemas()["capabilities"]
    assert branch["properties"]["domain"]["enum"] == list(CAPABILITY_DOMAIN_VALUES)
    assert branch["properties"]["feature"]["enum"] == list(CAPABILITY_FEATURE_VALUES)
    assert len(CAPABILITY_DOMAIN_VALUES) == 8
    assert len(CAPABILITY_FEATURE_VALUES) == 27


def test_query_capabilities_filters_by_domain_and_feature() -> None:
    """两级检索：先 domain（8 选 1）再 feature（27 选 1），而不是在 683 个端点里直接挑。"""
    environment = env()
    try:
        classified_row(
            "midas_gen", "node.list", domain="model", feature="db_node_element"
        )
        classified_row(
            "midas_gen", "load.list", domain="load", feature="db_static_loads"
        )
        classified_row(
            "midas_gen", "load.create", domain="load", feature="db_static_loads"
        )

        by_domain = environment.call(
            TOOL_QUERY,
            {"target": "capabilities", "action": "list", "query": {"domain": "load"}},
        )
        assert by_domain["success"] is True, by_domain
        assert {row["code"] for row in by_domain["data"]["items"]} == {
            "load.list",
            "load.create",
        }

        by_both = environment.call(
            TOOL_QUERY,
            {
                "target": "capabilities",
                "action": "search",
                "query": {"domain": "model", "feature": "db_node_element"},
            },
        )
        assert by_both["success"] is True, by_both
        assert [row["code"] for row in by_both["data"]["items"]] == ["node.list"]

        # 两个条件都合法但组合为空 -> 空列表，不是错误（区别于越界取值）。
        empty = environment.call(
            TOOL_QUERY,
            {
                "target": "capabilities",
                "action": "list",
                "query": {"domain": "load", "feature": "db_node_element"},
            },
        )
        assert empty["success"] is True, empty
        assert empty["data"]["items"] == []
    finally:
        reset_capabilities()


def test_query_capabilities_exposes_the_chinese_annotation_as_description() -> None:
    """总纲 §4.2.13：中文注释必须能从 ``target=capabilities`` 读到。

    The registry is an **API catalogue**: the manuals' Chinese and English sections
    document the *same* endpoints, so what a Chinese-speaking user (and the LLM)
    needs is not the section's language but a Chinese annotation per row.  That
    annotation reaches this projection under ``description`` — the name a reader
    looks for — while ``notes`` keeps the same string under its historical key.  A
    row the extraction could not annotate shows ``""``: nothing is composed here.
    """
    environment = env()
    annotation = "主控数据：分析主控参数：自动约束旋转与法向、收敛容差等全局求解设置。"
    try:
        register_capability(
            dataclasses.replace(
                capability_table("midas_gen")["element.get"],
                notes=annotation,
                interface_code="midas_gen.db.elem.read",
            ),
            replace=True,
        )

        envelope = environment.call(
            TOOL_QUERY, {"target": "capabilities", "action": "list"}
        )
        assert envelope["success"] is True
        items = {row["code"]: row for row in envelope["data"]["items"]}
        assert items["element.get"]["description"] == annotation
        # …and the historical key still carries it, so nothing that reads ``notes``
        # has to change.
        assert items["element.get"]["notes"] == annotation
        # 未注释的行留空，而不是编造一个（``node.list`` 的静态声明就是空注释）。
        assert items["node.list"]["description"] == ""
        assert items["node.list"]["description"] == items["node.list"]["notes"]
    finally:
        reset_capabilities()


def test_query_capabilities_rejects_an_unknown_domain_or_feature() -> None:
    """总纲 §4.2.11 的封闭集合：越界取值 -> ``VALIDATION_ERROR``，不是空列表。"""
    environment = env()
    for query in ({"domain": "modelling"}, {"feature": "db_nonsense"}):
        envelope = environment.call(
            TOOL_QUERY, {"target": "capabilities", "action": "list", "query": query}
        )
        assert envelope["success"] is False, query
        assert envelope["errors"][0]["code"] == ErrorCode.VALIDATION_ERROR.value, query


def test_the_capability_filter_handler_validates_the_closed_sets_itself() -> None:
    """兜底校验器不展开 ``query`` 的 ``anyOf`` 分支，所以处理器必须自己再校验一次。

    ``jsonschema`` 缺失时 :func:`app.mcp.dispatcher.validate_arguments` 退化为浅层
    校验（只到 ``query`` 这一层），此时唯一的防线就是处理器里的那次检查 ——
    没有它，一个拼错的 domain 会静默返回空列表，看起来像「平台没有这个能力」。
    """
    environment = env()
    arguments: dict[str, Any] = {
        "target": "capabilities",
        "action": "list",
        "query": {"domain": "modelling"},
    }
    context = DispatchContext(
        request_id="req_20260925_000002",
        tool=TOOL_QUERY,
        capability=capability_table("midas_gen")["capabilities.list"],
        adapter=environment.adapter,
        registry=environment.registry,
        tasks=environment.tasks,
        resolver=environment.resolver,
        arguments=arguments,
    )
    result = query_tool._capabilities_result(arguments, context)
    assert result.success is False
    assert result.error_code == ErrorCode.VALIDATION_ERROR.value
    assert "封闭集合" in (result.error_message or "")


def test_query_count_and_get() -> None:
    environment = seeded()
    counted = environment.call(TOOL_QUERY, {"target": "node", "action": "count"})
    assert counted["success"] is True
    assert counted["data"]["count"] == 2

    fetched = environment.call(TOOL_QUERY, {"target": "node", "action": "get", "id": 1})
    assert fetched["success"] is True
    assert fetched["data"]["item"]["id"] == "1"

    missing = environment.call(TOOL_QUERY, {"target": "node", "action": "get", "id": 99})
    assert missing["success"] is False
    assert missing["errors"][0]["code"] == ErrorCode.RESOURCE_NOT_FOUND.value


def test_query_inspect_uses_the_info_endpoint() -> None:
    """对接规范 §5.0.1 / §5.1: ``/info/db/<RES>``, schema under ``Argument``."""
    environment = env()
    envelope = environment.call(TOOL_QUERY, {"target": "node", "action": "inspect"})
    assert envelope["success"] is True
    assert set(envelope["data"]["properties"]) == {"X", "Y", "Z"}
    assert environment.adapter.request_log[-1]["endpoint"] == "/info/db/NODE"


def test_query_result_uses_post_table_with_components() -> None:
    """对接规范 §11.5.6: COMPONENTS is mandatory; the root key is unstable."""
    environment = env()
    envelope = environment.call(
        TOOL_QUERY,
        {"target": "result", "action": "list", "query": {"result_type": "displacement"}},
    )
    assert envelope["success"] is True
    assert envelope["data"]["HEAD"]
    assert environment.adapter.request_log[-1]["endpoint"] == "/post/TABLE"
    body = environment.adapter.request_log[-1]["body"]
    assert body["Argument"]["COMPONENTS"]
    assert body["Argument"]["TABLE_TYPE"] == "Displacement"


def test_query_result_rejects_an_unknown_result_type_before_calling() -> None:
    environment = env()
    envelope = environment.call(
        TOOL_QUERY,
        {"target": "result", "action": "list", "query": {"result_type": "other"}},
    )
    assert envelope["success"] is False
    assert envelope["errors"][0]["code"] == ErrorCode.VALIDATION_ERROR.value
    assert environment.adapter.request_log == []


def test_query_model_returns_a_snapshot_without_a_single_endpoint() -> None:
    environment = env()
    envelope = environment.call(TOOL_QUERY, {"target": "model", "action": "list"})
    assert envelope["success"] is True
    assert envelope["data"]["resource"] == "model"
    assert set(envelope["data"]["counts"]) >= {"node", "element", "load"}
    assert envelope["data"]["unit"] is not None  # /db/UNIT 在空模型下也有数据（§11.3）


def test_query_server_and_client_are_local_paths() -> None:
    environment = env()
    server = environment.call(TOOL_QUERY, {"target": "server", "action": "get"})
    assert server["success"] is True
    client = environment.call(TOOL_QUERY, {"target": "client", "action": "get"})
    assert client["success"] is True
    assert client["data"]["max_concurrency"] == 1  # 对接规范 §2.5.2 硬约束


# ===========================================================================
# 9. midas_execute
# ===========================================================================
def test_execute_calculate_returns_a_task_prefixed_id() -> None:
    """V2.1 §9.4: async by default -> ``status=queued`` + ``task_id``."""
    environment = env()
    envelope = environment.call(TOOL_EXECUTE, {"action": "calculate"})
    assert envelope["success"] is True
    assert envelope["status"] == TaskStatus.QUEUED.value
    assert envelope["data"] is None
    task_id = envelope["task_id"]
    assert task_id is not None
    assert task_id.startswith("task_")
    assert is_valid_id(task_id, "task")
    # 总纲 §4.1.4: 子类型前缀（task_ai_xxx / analysis_xxx）全部废止。
    assert not task_id.startswith(("task_ai_", "analysis_", "optimization_"))


def test_execute_async_task_runs_and_is_pollable() -> None:
    environment = env()
    envelope = environment.call(TOOL_EXECUTE, {"action": "calculate"})
    task_id = envelope["task_id"]

    run(environment.tasks.drain())

    snapshot = environment.call(TOOL_TASK, {"action": "get", "task_id": task_id})
    assert snapshot["success"] is True
    assert snapshot["data"]["status"] == TaskStatus.SUCCESS.value
    assert snapshot["data"]["progress"] == 100.0
    assert snapshot["data"]["type"] == TaskType.CALCULATE.value

    result = environment.call(TOOL_TASK, {"action": "result", "task_id": task_id})
    assert result["success"] is True
    assert result["data"]["ready"] is True


def test_execute_wait_true_runs_inline() -> None:
    environment = env()
    envelope = environment.call(
        TOOL_EXECUTE, {"action": "calculate", "options": {"wait": True}}
    )
    assert envelope["success"] is True
    assert envelope["task_id"] is None
    assert envelope["data"] is not None


def test_execute_connect_runs_inline_and_checks_the_channel() -> None:
    environment = env()
    envelope = environment.call(TOOL_EXECUTE, {"action": "connect"})
    assert envelope["success"] is True
    assert envelope["task_id"] is None
    # 对接规范 §2.2: /mapikey/verify 在主机根，返回 keyVerified。
    assert envelope["data"]["keyVerified"] is True
    assert environment.adapter.request_log[-1]["endpoint"] == "/mapikey/verify"


def test_execute_dry_run_touches_nothing() -> None:
    environment = env()
    envelope = environment.call(
        TOOL_EXECUTE, {"action": "export", "data": {"path": "C:\\tmp\\m.json"},
                       "options": {"dry_run": True}}
    )
    assert envelope["success"] is True
    assert envelope["data"]["dry_run"] is True
    assert environment.adapter.request_log == []


def test_execute_export_uses_the_live_guard_when_a_path_is_given() -> None:
    """对接规范 §3.5 第 6 条: the path is resolved on the NX host, so it must be
    supplied explicitly — and §3.5 第 13 条 forbids protected prefixes."""
    environment = env()
    envelope = environment.call(
        TOOL_EXECUTE,
        {
            "action": "export",
            "data": {"path": "C:\\Program Files\\midas\\out.json"},
            "options": {"wait": True},
        },
    )
    assert envelope["success"] is False
    assert envelope["errors"][0]["code"] == ErrorCode.VALIDATION_ERROR.value
    assert environment.adapter.request_log == []


def test_execute_rejects_a_protected_path() -> None:
    """对接规范 §3.5 第 13 条: 受保护路径连 GET 都会弹对话框并阻塞会话."""
    environment = env()
    envelope = environment.call(
        TOOL_EXECUTE,
        {
            "action": "export",
            "data": {"path": "C:\\Windows\\System32\\out.json"},
            "options": {"wait": True},
        },
    )
    assert envelope["success"] is False
    assert envelope["errors"][0]["code"] == ErrorCode.VALIDATION_ERROR.value
    assert environment.adapter.request_log == []


def test_execute_unmapped_actions_answer_not_implemented() -> None:
    """No fabricated success: 总纲 §4.4.9 ``NOT_IMPLEMENTED``."""
    environment = env()
    for action in ("generate_report", "validate_model"):
        envelope = environment.call(TOOL_EXECUTE, {"action": action})
        assert envelope["success"] is False, action
        assert envelope["errors"][0]["code"] == ErrorCode.NOT_IMPLEMENTED.value
    assert environment.adapter.request_log == []


def test_execute_sync_reads_the_model_back() -> None:
    """对接规范 §3.5 第 5 条: 写超时后必须先读回模型状态."""
    environment = seeded()
    envelope = environment.call(TOOL_EXECUTE, {"action": "sync"})
    assert envelope["success"] is True
    assert envelope["data"]["counts"]["node"] == 2
    assert all(entry["method"] == "GET" for entry in environment.adapter.request_log)


def test_execute_command_requires_an_endpoint() -> None:
    environment = env()
    envelope = environment.call(TOOL_EXECUTE, {"action": "command"})
    assert envelope["success"] is False
    assert envelope["errors"][0]["code"] == ErrorCode.VALIDATION_ERROR.value


def test_execute_command_is_routed_to_the_raw_channel() -> None:
    """``command`` maps to the adapter's ``raw`` action (V2.1 §17.5 第 11 条 guards).

    The offline double does not implement ``raw``, so the honest answer is the
    closed-set ``CAPABILITY_NOT_SUPPORTED`` (V2.1 §16.2) — never a fabricated
    success.  The live raw channel, including its DELETE / NMAS / PRES guards, is
    exercised in ``tests/live/test_mcp_live.py``.
    """
    environment = seeded()
    assert capability_table("midas_gen")["command.command"].effective_adapter_action == "raw"
    envelope = environment.call(
        TOOL_EXECUTE,
        {
            "action": "command",
            "options": {"wait": True},
            "data": {"method": "DELETE", "endpoint": "/db/NODE"},
        },
    )
    assert envelope["success"] is False
    assert envelope["errors"][0]["code"] == ErrorCode.CAPABILITY_NOT_SUPPORTED.value
    assert environment.adapter.trap_fired is False
    assert set(environment.adapter.model_store["NODE"]) == {"1", "3"}


def test_execute_result_export_requires_a_path() -> None:
    """对接规范 §3.5 第 13 条: a bad export path pops a modal dialog on the NX
    host that blocks the **entire** API session (§2.5.2), so the MCP layer
    refuses a missing/protected path **before** queueing anything — it must not
    rely on the adapter's ``get_table()`` guard, and it must not enqueue a task
    that is guaranteed to fail.
    """
    environment = env()
    envelope = environment.call(TOOL_EXECUTE, {"action": "export", "resource": "result"})
    assert envelope["success"] is False
    assert envelope["task_id"] is None, "a doomed export must not be queued"
    assert envelope["errors"][0]["code"] == ErrorCode.VALIDATION_ERROR.value
    # nothing reached the adapter, so no modal dialog could have been raised
    assert environment.adapter.trap_fired is False


# ===========================================================================
# 10. the Task Engine (V2.1 §26)
# ===========================================================================
def test_task_ids_use_the_single_task_prefix() -> None:
    environment = env()

    async def body() -> list[str]:
        ids = []
        for _ in range(3):
            ids.append(
                await environment.tasks.create(
                    type=TaskType.CALCULATE.value, action="calculate"
                )
            )
        return ids

    ids = run(body())
    assert len(set(ids)) == 3
    for task_id in ids:
        assert is_valid_id(task_id, "task")


def test_task_create_rejects_an_unknown_business_type() -> None:
    environment = env()
    with pytest.raises(AdapterError) as excinfo:
        run(
            environment.tasks.create(
                type="task_ai_thing", action="calculate"
            )
        )
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR.value


def test_task_engine_serializes_per_midas_client() -> None:
    """V2.1 §26.5: 每个 ``midas_client_id`` 并发恒为 1 (对接规范 §2.5.2)."""
    service = TaskService(max_concurrency=4)
    log: list[str] = []

    def worker(name: str) -> Any:
        async def body() -> None:
            log.append(f"{name}-start")
            await asyncio.sleep(0.02)
            log.append(f"{name}-end")

        return body

    async def scenario() -> None:
        await service.create(
            type=TaskType.CALCULATE.value,
            action="calculate",
            midas_client_id=1,
            runner=worker("a"),
        )
        await asyncio.sleep(0)  # let A take the client lock
        await service.create(
            type=TaskType.CALCULATE.value,
            action="calculate",
            midas_client_id=1,
            runner=worker("b"),
        )
        await service.drain()

    run(scenario())
    assert log == ["a-start", "a-end", "b-start", "b-end"]


def test_task_engine_runs_different_clients_concurrently() -> None:
    """The global pool is N > 1; only the *instance* is serial (§26.5)."""
    service = TaskService(max_concurrency=4)
    log: list[str] = []

    def worker(name: str) -> Any:
        async def body() -> None:
            log.append(f"{name}-start")
            await asyncio.sleep(0.05)
            log.append(f"{name}-end")

        return body

    async def scenario() -> None:
        await service.create(
            type=TaskType.CALCULATE.value, action="calculate",
            midas_client_id=1, runner=worker("a"),
        )
        await service.create(
            type=TaskType.CALCULATE.value, action="calculate",
            midas_client_id=2, runner=worker("b"),
        )
        await service.drain()

    run(scenario())
    assert log[:2] == ["a-start", "b-start"]


def test_no_auto_retry_after_a_write_timeout() -> None:
    """V2.1 §26.5 / 对接规范 §3.5 第 5 条: 超时 ≠ 回滚."""
    service = TaskService(max_concurrency=2)
    invocations: list[int] = []

    async def slow_write() -> AdapterResult:
        invocations.append(1)
        await asyncio.sleep(1.0)
        return AdapterResult.ok({"never": True})

    async def scenario() -> str:
        task_id = await service.create(
            type=TaskType.CALCULATE.value,
            action="calculate",
            is_write=True,
            timeout_seconds=0.02,
            runner=slow_write,
        )
        await service.drain()
        return task_id

    task_id = run(scenario())
    snapshot = run(service.get(task_id, include_result=True))
    assert snapshot["status"] == TaskStatus.FAILED.value
    assert snapshot["error_code"] == ErrorCode.TASK_TIMEOUT.value
    assert snapshot["retry_count"] == 0
    assert invocations == [1], "写任务超时后绝不能被自动重投"
    assert "超时 ≠ 回滚" in snapshot["error_message"]

    events = run(service.events(task_id))
    assert [event["event_type"] for event in events["items"]] == [
        "queued",
        "started",
        "failed",
    ]
    assert events["items"][-1]["payload"]["error_code"] == ErrorCode.TASK_TIMEOUT.value


def test_read_timeout_says_replay_is_safe_but_still_does_not_retry() -> None:
    service = TaskService(max_concurrency=2)
    invocations: list[int] = []

    async def slow_read() -> AdapterResult:
        invocations.append(1)
        await asyncio.sleep(1.0)
        return AdapterResult.ok({})

    async def scenario() -> str:
        task_id = await service.create(
            type=TaskType.CALCULATE.value,
            action="list",
            is_write=False,
            timeout_seconds=0.02,
            runner=slow_read,
        )
        await service.drain()
        return task_id

    task_id = run(scenario())
    snapshot = run(service.get(task_id))
    assert snapshot["error_code"] == ErrorCode.TASK_TIMEOUT.value
    assert invocations == [1]
    assert "读操作超时" in snapshot["error_message"]


def test_task_retry_is_explicit_and_budgeted() -> None:
    service = TaskService(max_concurrency=2)
    attempts: list[int] = []

    async def flaky() -> AdapterResult:
        attempts.append(1)
        return AdapterResult.failed(ErrorCode.MIDAS_API_ERROR, "boom")

    async def scenario() -> str:
        task_id = await service.create(
            type=TaskType.CALCULATE.value,
            action="calculate",
            max_retries=1,
            runner=flaky,
        )
        await service.drain()
        return task_id

    task_id = run(scenario())
    assert run(service.get(task_id))["status"] == TaskStatus.FAILED.value
    assert len(attempts) == 1

    run(service.retry(task_id))
    run(service.drain())
    assert len(attempts) == 2
    assert run(service.get(task_id))["retry_count"] == 1

    with pytest.raises(AdapterError) as excinfo:
        run(service.retry(task_id))
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR.value  # budget exhausted


def test_task_retry_refuses_a_running_task() -> None:
    service = TaskService(max_concurrency=1)
    release = asyncio.Event()

    async def blocked() -> AdapterResult:
        await release.wait()
        return AdapterResult.ok({})

    async def scenario() -> str:
        task_id = await service.create(
            type=TaskType.CALCULATE.value, action="calculate", runner=blocked
        )
        await asyncio.sleep(0)
        with pytest.raises(AdapterError) as excinfo:
            await service.retry(task_id)
        assert excinfo.value.code == ErrorCode.TASK_ALREADY_RUNNING.value
        release.set()
        await service.drain()
        return task_id

    run(scenario())


def test_task_cancel_and_not_found() -> None:
    service = TaskService(max_concurrency=1)

    async def scenario() -> None:
        with pytest.raises(AdapterError) as missing:
            await service.get("task_20200101_000001")
        assert missing.value.code == ErrorCode.TASK_NOT_FOUND.value

        task_id = await service.create(
            type=TaskType.CALCULATE.value, action="calculate"
        )
        cancelled = await service.cancel(task_id)
        assert cancelled["status"] == TaskStatus.CANCELLED.value
        with pytest.raises(AdapterError) as again:
            await service.cancel(task_id)
        assert again.value.code == ErrorCode.TASK_CANCEL_FAILED.value

    run(scenario())


def test_task_events_support_an_incremental_cursor() -> None:
    service = TaskService(max_concurrency=1)

    async def scenario() -> str:
        task_id = await service.create(
            type=TaskType.CALCULATE.value, action="calculate"
        )
        service.emit_log(task_id, "half way")
        return task_id

    task_id = run(scenario())
    first = run(service.events(task_id))
    assert [event["event_type"] for event in first["items"]] == ["queued", "log"]
    assert first["cursor"]

    second = run(service.events(task_id, since=first["cursor"]))
    assert second["items"] == []


def test_task_result_hides_raw_upstream_data() -> None:
    """V2.1 §19 — ``tasks.result_json`` must never carry the raw payload."""
    service = TaskService(max_concurrency=1)

    async def body() -> AdapterResult:
        return AdapterResult.ok(
            {"items": []}, raw_status=200, raw_response={"SENTINEL_RAW": True}
        )

    async def scenario() -> str:
        task_id = await service.create(
            type=TaskType.CALCULATE.value, action="calculate", runner=body
        )
        await service.drain()
        return task_id

    task_id = run(scenario())
    payload = run(service.result(task_id))
    text = json.dumps(payload, ensure_ascii=False, default=str)
    assert "SENTINEL_RAW" not in text
    assert "raw_response" not in text


# ===========================================================================
# 11. midas_task tool
# ===========================================================================
def test_task_tool_get_list_events_logs_and_result() -> None:
    environment = env()

    async def scenario() -> str:
        task_id = await environment.tasks.create(
            type=TaskType.REPORT.value,
            action="generate_report",
            resource="report",
            tool_name=TOOL_EXECUTE,
            midas_client_id=7,
            request_id="req_20260925_000042",
        )
        environment.tasks.emit_log(task_id, "building report")
        return task_id

    task_id = run(scenario())

    fetched = environment.call(
        TOOL_TASK, {"action": "get", "task_id": task_id, "include_events": True}
    )
    assert fetched["success"] is True
    assert fetched["data"]["task_id"] == task_id
    assert fetched["data"]["midas_client_id"] == 7
    assert fetched["data"]["request_id"] == "req_20260925_000042"
    assert len(fetched["data"]["events"]) == 2

    listed = environment.call(TOOL_TASK, {"action": "list", "type": "report"})
    assert listed["success"] is True
    assert listed["data"]["total"] == 1
    assert listed["data"]["items"][0]["task_id"] == task_id

    empty = environment.call(TOOL_TASK, {"action": "list", "status": "running"})
    assert empty["data"]["total"] == 0

    events = environment.call(TOOL_TASK, {"action": "events", "task_id": task_id})
    assert events["success"] is True
    assert events["data"]["task_id"] == task_id
    assert events["data"]["cursor"]

    logs = environment.call(TOOL_TASK, {"action": "logs", "task_id": task_id})
    assert logs["success"] is True
    assert [item["event_type"] for item in logs["data"]["items"]] == ["log"]

    result = environment.call(TOOL_TASK, {"action": "result", "task_id": task_id})
    assert result["success"] is True
    # The task never ran, so it is not terminal yet (V2.1 §10.3 step 3) ...
    assert result["data"]["ready"] is False
    assert result["data"]["status"] == TaskStatus.QUEUED.value
    # ... and the envelope says so rather than pretending otherwise.
    assert any("尚未进入终态" in warning for warning in result["warnings"])


def test_task_tool_rejects_an_unknown_task_id() -> None:
    environment = env()
    envelope = environment.call(
        TOOL_TASK, {"action": "get", "task_id": "task_20200101_000001"}
    )
    assert envelope["success"] is False
    assert envelope["errors"][0]["code"] == ErrorCode.TASK_NOT_FOUND.value


def test_task_tool_requires_a_task_id() -> None:
    environment = env()
    envelope = environment.call(TOOL_TASK, {"action": "result"})
    assert envelope["success"] is False
    assert envelope["errors"][0]["code"] == ErrorCode.VALIDATION_ERROR.value


def test_task_tool_does_not_touch_any_adapter() -> None:
    """对接规范 §2.5.1: MIDAS has no task API."""
    environment = env()
    environment.call(TOOL_TASK, {"action": "list"})
    assert environment.adapter.request_log == []
    assert capability_table(None)["task.get"].adapter_code is None


# ===========================================================================
# 12. the auth / RBAC seam (v1.2 §38)
# ===========================================================================
def test_authorizer_is_consulted_before_anything_else() -> None:
    seen: list[tuple[str, str, str]] = []

    def authorizer(request: Any) -> None:
        seen.append((request.tool, request.action, request.permission))

    environment = env(authorizer=authorizer)
    environment.call(TOOL_QUERY, {"target": "node", "action": "list"})
    assert seen == [(TOOL_QUERY, "list", "model:read")]


def test_authorizer_can_refuse_with_a_closed_set_code() -> None:
    def authorizer(request: Any) -> None:
        raise AdapterError(ErrorCode.PERMISSION_DENIED, "没有 tool:execute 权限")

    environment = env(authorizer=authorizer)
    envelope = environment.call(TOOL_EXECUTE, {"action": "calculate"})
    assert envelope["success"] is False
    assert envelope["errors"][0]["code"] == ErrorCode.PERMISSION_DENIED.value
    assert environment.adapter.request_log == []


def test_authorizer_may_be_async() -> None:
    calls: list[str] = []

    async def authorizer(request: Any) -> None:
        calls.append(request.tool)

    environment = env(authorizer=authorizer)
    environment.call(TOOL_TASK, {"action": "list"})
    assert calls == [TOOL_TASK]


def test_no_error_code_outside_the_closed_set_is_ever_emitted() -> None:
    """总纲 §4.4 is a closed set; nothing here may invent a code."""
    environment = env()
    known = {member.value for member in ErrorCode}
    for tool, arguments in (
        (TOOL_QUERY, {"target": "node", "action": "list"}),
        (TOOL_QUERY, {"target": "node", "action": "wibble"}),
        (TOOL_MODEL, {"action": "delete", "resource": "unit"}),
        (TOOL_EXECUTE, {"action": "generate_report"}),
        (TOOL_TASK, {"action": "get"}),
        ("nope", {"action": "list"}),
    ):
        envelope = environment.call(tool, arguments)
        for entry in envelope["errors"]:
            assert entry["code"] in known, entry


# ===========================================================================
# 12. midas_task ownership scope (v1.2 §21)
# ===========================================================================
class _Who:
    """Minimal stand-in for the resolved ``Principal``.

    The scope rule reads exactly two attributes, so a stub keeps these tests
    independent of ``Principal``'s full field list.
    """

    def __init__(self, user_id: int, roles: tuple[str, ...] = ()) -> None:
        self.user_id = user_id
        self.roles = roles


def _two_owned_tasks(environment: Env) -> tuple[str, str]:
    """One task owned by user 1, one by user 2; both left ``queued``."""

    async def seed() -> tuple[str, str]:
        mine = await environment.tasks.create(
            type="calculate", action="calculate", requested_by=1
        )
        theirs = await environment.tasks.create(
            type="calculate", action="calculate", requested_by=2
        )
        await environment.tasks.drain()
        return mine, theirs

    return run(seed())


def test_mcp_task_get_refuses_another_users_task() -> None:
    """v1.2 §21 — the MCP surface enforces the same scope as the REST surface.

    Regression guard.  ``midas_task`` used to carry **no** ownership check at
    all: ``action=get`` read any task and ``action=list`` enumerated every
    user's, while ``GET /tasks/{id}`` refused the identical request.  One surface
    filtered and the other did not, because the rule lived only in the REST
    layer.  Both now call ``task_service.task_visible_to``.
    """
    environment = env()
    mine, theirs = _two_owned_tasks(environment)

    alice = _Who(1)
    root = _Who(1, ("super_admin",))

    assert environment.call(
        TOOL_TASK, {"action": "get", "task_id": mine}, principal=alice
    )["success"] is True

    denied = environment.call(
        TOOL_TASK, {"action": "get", "task_id": theirs}, principal=alice
    )
    assert denied["success"] is False
    assert denied["errors"][0]["code"] == ErrorCode.PERMISSION_DENIED.value
    assert denied["errors"][0]["details"]["reason"] == "task_out_of_scope"

    # 总纲 §4.8.3 — super_admin reaches every row.
    assert environment.call(
        TOOL_TASK, {"action": "get", "task_id": theirs}, principal=root
    )["success"] is True


def test_mcp_task_list_is_scoped_and_its_total_excludes_other_users() -> None:
    """The scope is pushed into the query, so ``total`` is honest too.

    Filtering the returned page instead would hide the rows and still report how
    many tasks exist platform-wide.
    """
    environment = env()
    mine, theirs = _two_owned_tasks(environment)

    listed = environment.call(TOOL_TASK, {"action": "list"}, principal=_Who(1))
    assert listed["success"] is True
    ids = {item["task_id"] for item in listed["data"]["items"]}
    assert mine in ids
    assert theirs not in ids
    assert listed["data"]["total"] == 1, "total must be computed over visible rows only"

    everything = environment.call(
        TOOL_TASK, {"action": "list"}, principal=_Who(1, ("super_admin",))
    )
    assert everything["data"]["total"] == 2


def test_mcp_task_scope_stands_down_when_there_is_no_principal() -> None:
    """裁决 C-13 — with authentication off there is nobody to filter by.

    The §4.8.2 gate is skipped in that mode, so the data-scope layer must be too;
    otherwise an unattributed deployment would see no tasks at all.
    """
    environment = env()
    mine, theirs = _two_owned_tasks(environment)

    listed = environment.call(TOOL_TASK, {"action": "list"})
    assert listed["success"] is True
    assert {item["task_id"] for item in listed["data"]["items"]} == {mine, theirs}


def test_mcp_task_cancel_and_result_are_scoped_too() -> None:
    """Every single-task action is covered, not only ``get``."""
    environment = env()
    _mine, theirs = _two_owned_tasks(environment)
    alice = _Who(1)

    for action in ("cancel", "retry", "result", "events", "logs"):
        envelope = environment.call(
            TOOL_TASK, {"action": action, "task_id": theirs}, principal=alice
        )
        assert envelope["success"] is False, action
        assert envelope["errors"][0]["code"] == ErrorCode.PERMISSION_DENIED.value, action
