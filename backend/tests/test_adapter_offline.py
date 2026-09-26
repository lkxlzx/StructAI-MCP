"""Offline adapter tests — **no live MIDAS required**.

Two layers are exercised, both offline:

1. the **pure rules** (wrap / unwrap / the three-layer judgement / the ``Assign``
   outer-key guard / the DELETE guard) through the mock adapter, which imports
   the very same functions the live adapter runs;
2. the **live adapter's transport wiring** through ``httpx.MockTransport``, so
   the auth header, the host-root verify URL, the write-contract backfill and the
   "no retry on writes" policy are all asserted without a server.

Plain ``pytest`` only: async entry points are driven with ``asyncio.run`` so the
suite does not depend on ``pytest-asyncio`` (which is not in
``backend/requirements.txt``).
"""

import asyncio
import json
from typing import Any

import httpx
import pytest

from app.adapters.base import (
    LIFECYCLE_DB_STATUS,
    AdapterLifecycle,
    AdapterMetadata,
    AdapterResult,
    ExecuteRequest,
    MidasAdapter,
    ModelRequest,
    QueryRequest,
)
from app.adapters.errors import (
    AMBIGUOUS_SUCCESS_MARKERS,
    ERROR_TEXT_MARKERS,
    AdapterError,
    is_error_body,
    normalize_upstream,
)
from app.adapters.midas_gen.adapter import (
    SESSION_STATE_BY_PHASE,
    SESSION_STATES,
    TRANSPORT_PHASE_MEANING,
    TRANSPORT_PHASE_REMEDY,
    TRANSPORT_PHASES,
    MidasNxAdapter,
    build_assign,
    find_table_shape,
    outer_key_means,
    require_table_components,
)
from app.adapters.mock.adapter import MockAdapter
from app.adapters.registry import AdapterRegistry, get_registry, reset_registry
from app.core.constants import TaskStatus
from app.core.errors import ErrorCode
from app.core.midas_config import MidasConnection
from app.mcp.capabilities import TOOL_EXECUTE, TOOL_MODEL
from app.mcp.capability import CapabilityResolver
from app.mcp.dispatcher import ToolDispatcher
from app.services.task_service import TaskService

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def run(coro: Any) -> Any:
    """Drive one coroutine to completion."""
    return asyncio.run(coro)


def connection(
    *,
    base_url: str = "http://localhost:3030",
    product: str = "gen",
    key: str = "test-mapi-key",
    timeout_seconds: int = 5,
) -> MidasConnection:
    """A valid :class:`MidasConnection` for the offline transport tests."""
    return MidasConnection(
        name="unit-test",
        software="MIDAS Gen",
        product=product,
        base_url=base_url,
        mapi_key=key,
        timeout_seconds=timeout_seconds,
    )


class Recorder:
    """Captures every request and answers with a canned response."""

    def __init__(self, responder: Any) -> None:
        self.requests: list[httpx.Request] = []
        self._responder = responder

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._responder(request)

    @property
    def count(self) -> int:
        return len(self.requests)

    def bodies(self) -> list[Any]:
        return [json.loads(request.content) if request.content else None for request in self.requests]


def transport_for(responder: Any) -> tuple[httpx.MockTransport, Recorder]:
    recorder = Recorder(responder)
    return httpx.MockTransport(recorder), recorder


# ===========================================================================
# 1. §17.3 — wrap
# ===========================================================================
def test_wrap_assign_and_argument() -> None:
    mock = MockAdapter()
    assert mock.wrap({"1": {"X": 0}}, "Assign") == {"Assign": {"1": {"X": 0}}}
    assert mock.wrap({"TYPE": "Pushover"}, "Argument") == {
        "Argument": {"TYPE": "Pushover"}
    }
    # 空参用 {}（对接规范 §3.1）
    assert mock.wrap({}, "Argument") == {"Argument": {}}
    assert mock.wrap(None, "Argument") == {"Argument": {}}


def test_wrap_none_wrapper_means_no_body() -> None:
    """``request_wrapper = NULL`` = 端点不接收请求体（V2.1 §17.3）。"""
    assert MockAdapter().wrap({"1": {"X": 0}}, None) == {}


def test_wrap_accepts_bare_string_for_doc_export() -> None:
    """对接规范 §3.4 末行 / §11.5.2：``/doc/EXPORT`` 必须传裸字符串。"""
    payload = "C:\\out\\model.json"
    assert MockAdapter().wrap(payload, "Argument") == {"Argument": payload}


def test_wrap_rejects_unknown_wrapper() -> None:
    with pytest.raises(AdapterError) as excinfo:
        MockAdapter().wrap({}, "Body")
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR.value


# ===========================================================================
# 2. §3.2.1 / §17.3 — unwrap, all three shapes
# ===========================================================================
def test_unwrap_shape_one_resource_root() -> None:
    mock = MockAdapter()
    response = {"NODE": {"1": {"X": 0.0, "Y": 0.0, "Z": 0.0}}}
    assert mock.unwrap(response, "NODE") == {"1": {"X": 0.0, "Y": 0.0, "Z": 0.0}}


def test_unwrap_shape_two_blank_message_is_success_without_data() -> None:
    """``{"message": ""}`` = 空表 = **成功且无数据**，不是错误（§3.2.1）。"""
    mock = MockAdapter()
    assert mock.unwrap({"message": ""}, "NODE") == {}
    assert mock.unwrap({"message": "   "}, "NODE") == {}


def test_unwrap_shape_two_non_blank_message_raises() -> None:
    """非空 message = 失败（§3.2.1 / §3.5 第 7 条）。"""
    mock = MockAdapter()
    with pytest.raises(AdapterError) as excinfo:
        mock.unwrap({"message": "... Analysis failed."}, "NODE")
    assert excinfo.value.code == ErrorCode.MIDAS_CALCULATION_ERROR.value


def test_unwrap_never_indexes_a_missing_root_key() -> None:
    """空表不是 ``{"NODE": {}}``：直接 ``response[root_key]`` 会 KeyError。"""
    mock = MockAdapter()
    assert mock.unwrap({"message": ""}, "NODE") == {}  # 不抛 KeyError


@pytest.mark.parametrize("status", [200, 201])
def test_unwrap_shape_three_error_body_at_2xx(status: int) -> None:
    """HTTP 200 **与 201** 都可能承载错误体（§3.5 第 2 条 / V2.1 §20.4）。"""
    mock = MockAdapter()
    with pytest.raises(AdapterError) as excinfo:
        mock.unwrap({"error": {"message": "Key Already Exist"}}, "NODE")
    assert excinfo.value.code == ErrorCode.RESOURCE_CONFLICT.value
    assert is_error_body({"error": {"message": "boom"}}, status) is True


def test_unwrap_shape_four_returns_response_as_is() -> None:
    mock = MockAdapter()
    assert mock.unwrap([1, 2, 3], "NODE") == [1, 2, 3]
    assert mock.unwrap({"no_root": 1}, "NODE") == {"no_root": 1}


# ===========================================================================
# 3. V2.1 §20.4 / 对接规范 §11.5.9 — three-layer judgement
# ===========================================================================
def test_layer_one_structured_signal_wins_over_status() -> None:
    for status in (200, 201):
        verdict = normalize_upstream(
            payload={"error": {"message": "boom"}}, raw_status=status
        )
        assert verdict.ok is False
        assert verdict.layer == "structured"
        assert verdict.error_code == ErrorCode.MIDAS_API_ERROR.value


def test_layer_two_blank_message_is_success() -> None:
    verdict = normalize_upstream(payload={"message": ""}, raw_status=200)
    assert verdict.ok is True
    assert verdict.data == {}


def test_layer_http_status_gate() -> None:
    verdict = normalize_upstream(payload={"anything": 1}, raw_status=500)
    assert verdict.ok is False
    assert verdict.error_code == ErrorCode.MIDAS_API_ERROR.value
    assert verdict.layer == "http-status"


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        # 对接规范 §7.4 / §11.5.2 —— 路径与文件
        ("MIDAS GEN NX path is wrong", ErrorCode.MIDAS_API_ERROR.value),
        ("the file can't open", ErrorCode.MIDAS_API_ERROR.value),
        # 对接规范 §7.4 —— 分析
        ("Analysis is not allowed", ErrorCode.MIDAS_CALCULATION_ERROR.value),
        ("no analysis result", ErrorCode.MIDAS_CALCULATION_ERROR.value),
        ("... Analysis failed.", ErrorCode.MIDAS_CALCULATION_ERROR.value),
        # 对接规范 §11.5.3 —— 仅创建
        ("Key Already Exist", ErrorCode.RESOURCE_CONFLICT.value),
        # 对接规范 §3.5 第 10 条 —— 通常意味着值错
        ("Wrong Field", ErrorCode.VALIDATION_ERROR.value),
        # 对接规范 §11.5.8 / §11.5.9 —— 中文（错误信息是本地化的）
        ("[错误] 边界条件 没有定义。", ErrorCode.VALIDATION_ERROR.value),
        ("[错误] 无法完成", ErrorCode.MIDAS_API_ERROR.value),
        # 对接规范 §11.5.10
        ("Unknown Error", ErrorCode.MIDAS_API_ERROR.value),
    ],
)
def test_bilingual_text_markers_classify_message_failures(
    message: str, expected: str
) -> None:
    verdict = normalize_upstream(payload={"message": message}, raw_status=200)
    assert verdict.ok is False
    assert verdict.error_code == expected
    assert verdict.matched_marker is not None


def test_marker_table_covers_the_documented_phrases_bilingually() -> None:
    markers = {marker.marker for marker in ERROR_TEXT_MARKERS}
    for required in (
        "path is wrong",
        "can't open",
        "analysis is not allowed",
        "no analysis result",
        "analysis failed",
        "key already exist",
        "wrong field",
        "[错误]",
        "没有定义",
        "无法",
    ):
        assert required in markers


def test_text_fallback_is_used_only_for_bare_bodies() -> None:
    """文本匹配只能兜底，且**只用于判定失败**（V2.1 §20.4）。"""
    failure = normalize_upstream(payload="MIDAS GEN NX path is wrong")
    assert failure.ok is False
    assert failure.layer == "text-pattern"

    # 无结构化失败信号 ≠ 由文本判定成功：成功来自「没有失败信号」这一事实。
    plain = normalize_upstream(payload="nothing to see here")
    assert plain.ok is True
    assert plain.layer != "text-pattern"

    # 结构化载荷根本不走文本兜底。
    structured = normalize_upstream(payload={"NODE": {"1": {}}}, root_key="NODE")
    assert structured.ok is True
    assert structured.layer == "root-key"


def test_is_error_body_checks_the_body_not_only_the_status() -> None:
    assert is_error_body({"message": ""}, 200) is False
    assert is_error_body({"UNIT": {"1": {}}}, 200) is False
    assert is_error_body({"error": {"message": "x"}}, 201) is True
    assert is_error_body({"message": "Analysis failed"}, 200) is True
    assert is_error_body({"message": ""}, 500) is True


def test_ambiguous_command_complete_is_a_failure_by_default() -> None:
    """§3.5 第 7 条：同一文案对「根本没发生的保存」也出现，因此默认判失败。"""
    assert "command complete" in AMBIGUOUS_SUCCESS_MARKERS
    verdict = normalize_upstream(
        payload={"message": "... command complete"}, raw_status=200
    )
    assert verdict.ok is False
    assert verdict.error_code == ErrorCode.MIDAS_API_ERROR.value
    assert any("command complete" in warning for warning in verdict.warnings)


def test_ambiguous_command_complete_opt_in_is_unverified_success() -> None:
    """§11.5.2：导出成功时上游唯一的返回就是这句，调用方可以显式选择采信。"""
    verdict = normalize_upstream(
        payload={"message": "... command complete"},
        raw_status=200,
        allow_ambiguous_message_success=True,
    )
    assert verdict.ok is True
    assert verdict.unverified is True
    assert verdict.layer == "message-ambiguous-success"
    assert verdict.warnings


# ===========================================================================
# 4. §11.5.1 / §3.5 第 1 条 — the DELETE trap
# ===========================================================================
def seeded_mock() -> MockAdapter:
    return MockAdapter(
        model={"NODE": {"1": {"X": 0.0}, "3": {"X": 6.0}}}
    )


def test_assign_body_delete_guard_raises_and_leaves_the_table_intact() -> None:
    mock = seeded_mock()
    with pytest.raises(AdapterError) as excinfo:
        mock.delete_using_assign_body("NODE", {"Assign": {"1": None}})
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR.value
    assert "清空整张表" in excinfo.value.message
    # 守卫拦住了，模拟的上游陷阱从未触发
    assert mock.trap_fired is False
    assert mock.wiped_tables == []
    assert set(mock.model_store["NODE"]) == {"1", "3"}


def test_delete_refuses_a_dict_payload() -> None:
    mock = seeded_mock()
    with pytest.raises(AdapterError) as excinfo:
        run(mock.delete("NODE", {"Assign": {"1": None}}))
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR.value
    assert mock.trap_fired is False
    assert set(mock.model_store["NODE"]) == {"1", "3"}


def test_delete_is_one_call_per_id() -> None:
    mock = seeded_mock()
    result = run(mock.delete("NODE", [1]))
    assert result.success is True
    assert result.data["deleted"] == ["1"]
    assert set(mock.model_store["NODE"]) == {"3"}  # 只删了 1，没动 3
    assert mock.trap_fired is False
    assert [entry["endpoint"] for entry in mock.calls(method="DELETE")] == ["/db/NODE/1"]


def test_delete_all_requires_confirm_and_then_wipes() -> None:
    mock = seeded_mock()
    with pytest.raises(AdapterError):
        run(mock.delete_all("NODE"))  # confirm 缺省为 False
    assert mock.trap_fired is False
    assert set(mock.model_store["NODE"]) == {"1", "3"}

    result = run(mock.delete_all("NODE", confirm=True))
    assert result.success is True
    assert mock.trap_fired is True
    assert mock.model_store["NODE"] == {}


# ===========================================================================
# 5. §4.1 / §11.6 — Assign outer-key semantics (the CNLD trap)
# ===========================================================================
def test_outer_key_means_documents_the_cnld_trap() -> None:
    assert outer_key_means("CNLD") == "node"
    assert outer_key_means("/db/CNLD") == "node"
    assert outer_key_means("CONS") == "group"
    assert outer_key_means("STLD") == "load_case"
    assert outer_key_means("ELEM") == "element"
    assert outer_key_means("NODE") == "node"
    # 未登记端点回落到未经实机确认的默认值
    assert outer_key_means("SECT") == "self"


def test_build_assign_rejects_the_cnld_misuse() -> None:
    """外层键=节点号、``ITEMS[].ID``=序号；把节点号写进 ID 必须被拒。"""
    with pytest.raises(AdapterError) as excinfo:
        build_assign(
            "1",  # 外层键写成了序号
            {"ITEMS": [{"ID": 2, "LCNAME": "LC1", "FX": 10000.0}]},  # ID 写成了节点号
            resource="CNLD",
        )
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR.value
    assert "节点号" in excinfo.value.message
    assert "序号" in excinfo.value.message


def test_build_assign_accepts_the_correct_cnld_form() -> None:
    body = build_assign(
        "2",
        {"ITEMS": [{"ID": 1, "LCNAME": "LC1", "FX": 10000.0}]},
        resource="/db/CNLD",
    )
    assert body == {"Assign": {"2": {"ITEMS": [{"ID": 1, "LCNAME": "LC1", "FX": 10000.0}]}}}
    # 手册参数表：ID 是 Serial Number，默认 0、Optional
    assert build_assign("2", {"ITEMS": [{"LCNAME": "LC1"}]}, resource="CNLD")[
        "Assign"
    ]["2"]["ITEMS"][0]["LCNAME"] == "LC1"
    assert build_assign("2", {"ITEMS": [{"ID": 0}]}, resource="CNLD")


def test_build_assign_requires_a_numeric_key_for_numbered_kinds() -> None:
    with pytest.raises(AdapterError):
        build_assign("N1", {"X": 0.0}, resource="NODE")


def test_cons_items_are_not_serial_numbers() -> None:
    """``/db/CONS`` 的 ``ITEMS[].ID`` **就是**节点号，不能被 CNLD 规则误伤。"""
    body = build_assign(
        "1", {"ITEMS": [{"ID": 7, "CONSTRAINT": "1111111"}]}, resource="CONS"
    )
    assert body["Assign"]["1"]["ITEMS"][0]["ID"] == 7


# ===========================================================================
# 6. §3.2.1 — the three response shapes through the mock's model/query path
# ===========================================================================
def test_empty_table_is_success_not_error() -> None:
    mock = MockAdapter()  # NODE 不在默认模型里 -> {"message": ""}
    result = run(mock.model(ModelRequest(
        request_id="req_test_1", client_id=1, action="list", resource="node",
        payload=None, options={}, timeout_seconds=5,
    )))
    assert result.success is True
    assert result.data["items"] == []
    assert result.data["total"] == 0


def test_resource_root_shape_round_trip() -> None:
    mock = MockAdapter()
    created = run(mock.model(ModelRequest(
        request_id="req_test_2", client_id=1, action="create", resource="node",
        payload=None, options={}, timeout_seconds=5,
        data={"1": {"X": 0.0, "Y": 0.0, "Z": 0.0}},
    )))
    assert created.success is True
    assert created.raw_status == 201  # §11.5.4：POST 成功返回 201

    read = run(mock.query(QueryRequest(
        request_id="req_test_3", client_id=1, action="list", resource=None,
        payload=None, options={}, timeout_seconds=5, target="node",
    )))
    assert read.success is True
    assert read.data["total"] == 1
    assert read.data["items"][0]["id"] == "1"


def test_post_is_create_only_not_upsert() -> None:
    """对接规范 §11.5.3：``POST`` 键已存在 → 400 ``Key Already Exist``。"""
    mock = MockAdapter()
    request = ModelRequest(
        request_id="req_test_4", client_id=1, action="create", resource="node",
        payload=None, options={}, timeout_seconds=5, data={"1": {"X": 0.0}},
    )
    assert run(mock.model(request)).success is True
    again = run(mock.model(request))
    assert again.success is False
    assert again.error_code == ErrorCode.RESOURCE_CONFLICT.value


def test_upsert_put_first_falls_back_to_post() -> None:
    """§11.5.3：``upsert`` 由适配器自行实现次序（本实现 PUT → 失败再 POST）。"""
    mock = MockAdapter(strict_put=True)
    result = run(mock.upsert("node", {"9": {"X": 1.0}}))
    assert result.success is True
    assert [attempt["method"] for attempt in result.data["attempts"]] == ["PUT", "POST"]
    assert [entry["method"] for entry in mock.calls()] == ["PUT", "POST"]


def test_upsert_put_first_single_call_when_the_key_exists() -> None:
    mock = MockAdapter(strict_put=True, model={"NODE": {"1": {"X": 0.0}}})
    result = run(mock.upsert("node", {"1": {"X": 9.0}}))
    assert result.success is True
    assert [attempt["method"] for attempt in result.data["attempts"]] == ["PUT"]


def test_upsert_post_first_falls_back_to_put() -> None:
    mock = MockAdapter(model={"NODE": {"1": {"X": 0.0}}})
    result = run(mock.upsert("node", {"1": {"X": 5.0}}, order="post_first"))
    assert result.success is True
    assert [attempt["method"] for attempt in result.data["attempts"]] == ["POST", "PUT"]


# ===========================================================================
# 7. §11.5.6 / §3.5 第 8 条 — /post/TABLE
# ===========================================================================
def test_require_table_components_is_mandatory() -> None:
    with pytest.raises(AdapterError) as excinfo:
        require_table_components("Reaction", [])
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR.value
    assert "COMPONENTS" in excinfo.value.message
    with pytest.raises(AdapterError):
        require_table_components("", ["Node"])


def test_get_table_requires_components_before_any_call() -> None:
    mock = MockAdapter()
    with pytest.raises(AdapterError):
        run(mock.get_table("Reaction", []))
    assert mock.request_log == []


def test_get_table_matches_by_shape_even_under_the_empty_root() -> None:
    """``"empty"`` 可以承载一张完整的表（§3.5 第 8 条）——禁止按键名取值。"""
    mock = MockAdapter(table_root="empty")
    result = run(mock.get_table("Reaction", ["Node", "Load", "FX"]))
    assert result.success is True
    assert result.data["HEAD"] == ["Node", "Load", "FX"]
    assert result.data["DATA"]
    assert "empty" in result.raw_response


def test_find_table_shape_searches_nested_payloads() -> None:
    payload = {"Result Table": {"FORCE": "KN", "HEAD": ["A"], "DATA": [[1]]}}
    assert find_table_shape(payload) == {"FORCE": "KN", "HEAD": ["A"], "DATA": [[1]]}
    assert find_table_shape({"empty": {"HEAD": [], "DATA": []}}) == {
        "HEAD": [],
        "DATA": [],
    }
    assert find_table_shape({"message": ""}) is None


def test_get_table_warns_about_load_case_suffixes() -> None:
    mock = MockAdapter(table_root="Displacement")
    result = run(mock.get_table("Displacement", ["Node"], load_case_names=["LC1"]))
    assert any("后缀" in warning for warning in result.warnings)


# ===========================================================================
# 8. §5.0.1 / §5.1 — introspection
# ===========================================================================
def test_introspect_returns_properties_from_under_argument() -> None:
    result = run(MockAdapter().introspect("NODE"))
    assert result.success is True
    assert set(result.data["properties"]) == {"X", "Y", "Z"}
    assert result.data["complete"] is False


def test_introspect_rejects_design_code_endpoints() -> None:
    """对接规范 §5.1：``/info`` 对设计代码端点一律 404。"""
    with pytest.raises(AdapterError) as excinfo:
        run(MockAdapter().introspect("/DESIGN/RC/KDS-41-20-2022/DCTL"))
    assert excinfo.value.code == ErrorCode.CAPABILITY_NOT_SUPPORTED.value
    assert "5.1" in excinfo.value.message


# ===========================================================================
# 9. V2.1 §15 / §19 / §21 — metadata, result, registry
# ===========================================================================
def test_metadata_has_exactly_the_section_15_fields() -> None:
    """V2.1 §15 lists ten fields — no more, no fewer."""
    metadata = run(MockAdapter().metadata())
    assert isinstance(metadata, AdapterMetadata)
    payload = metadata.to_db_payload()
    assert set(payload) == {
        "code",
        "name",
        "software",
        "version_range",
        "protocol",
        "supports_query",
        "supports_model",
        "supports_execute",
        "supports_async_task",
        "capabilities",
    }
    assert payload["code"] == metadata.code
    assert isinstance(payload["capabilities"], list)


def test_adapter_result_llm_payload_hides_raw_upstream() -> None:
    """§19 字段约束：``raw_status`` / ``raw_response`` 禁止直接回传 LLM。"""
    result = AdapterResult.failed(
        ErrorCode.MIDAS_API_ERROR, "boom", raw_status=500, raw_response={"error": {}}
    )
    payload = result.to_llm_payload()
    assert "raw_status" not in payload and "raw_response" not in payload
    assert payload["error_code"] == ErrorCode.MIDAS_API_ERROR.value
    assert result.status == TaskStatus.FAILED.value


def test_lifecycle_maps_onto_the_two_db_status_columns() -> None:
    enabled, connected = LIFECYCLE_DB_STATUS[AdapterLifecycle.CONNECTED]
    assert (enabled, connected) == ("enabled", "connected")
    # 总纲 §4.2.5: ``disabled`` is an administrative flag, not a lifecycle stage.
    # A registered-but-not-yet-connected adapter is still *enabled*.
    assert LIFECYCLE_DB_STATUS[AdapterLifecycle.REGISTERED] == ("enabled", "disconnected")
    assert LIFECYCLE_DB_STATUS[AdapterLifecycle.INITIALIZING] == ("enabled", "disconnected")


def test_mock_adapter_satisfies_the_protocol() -> None:
    assert isinstance(MockAdapter(), MidasAdapter)


def test_registry_register_get_list_resolve() -> None:
    registry = AdapterRegistry()
    gen = MockAdapter(code="midas_gen", software="MIDAS Gen", version_range=">=2024")
    civil = MockAdapter(
        code="midas_civil", software="MIDAS Civil", version_range=">=2023"
    )
    run(registry.register_async(gen))
    run(registry.register_async(civil))

    assert registry.get("midas_gen") is gen
    assert [adapter.code for adapter in registry.list()] == ["midas_gen", "midas_civil"]
    assert registry.resolve("gen") is gen
    assert registry.resolve("MIDAS Civil") is civil
    assert registry.resolve("midas_civil", "2024") is civil
    assert registry.metadata_of("midas_gen").version_range == ">=2024"


def test_registry_errors_map_onto_the_closed_error_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = AdapterRegistry()
    with pytest.raises(AdapterError) as missing:
        registry.resolve("ANSYS")
    assert missing.value.code == ErrorCode.ADAPTER_NOT_FOUND.value

    disabled = MockAdapter(code="midas_gen", software="MIDAS Gen")
    run(registry.register_async(disabled))
    # ``disabled`` is an **administrative** state (总纲 §4.2.5) — no lifecycle
    # stage maps to it any more, so simulate an operator turning the adapter off
    # rather than misusing ``REGISTERED`` (which is merely "not yet initialised").
    monkeypatch.setattr(type(disabled), "status", property(lambda self: "disabled"))
    with pytest.raises(AdapterError) as unavailable:
        registry.resolve("MIDAS Gen")
    assert unavailable.value.code == ErrorCode.ADAPTER_UNAVAILABLE.value

    monkeypatch.undo()  # back to enabled, so the version check is what fails
    with pytest.raises(AdapterError) as version:
        registry.resolve("MIDAS Gen", "1999")
    assert version.value.code == ErrorCode.CAPABILITY_NOT_SUPPORTED.value

    with pytest.raises(AdapterError) as duplicate:
        run(registry.register_async(MockAdapter(code="midas_gen", software="MIDAS Gen")))
    assert duplicate.value.code == ErrorCode.RESOURCE_CONFLICT.value


def test_registry_rejects_metadata_code_mismatch() -> None:
    registry = AdapterRegistry()
    metadata = AdapterMetadata(
        code="something_else", name="x", software="y", version_range="*",
        protocol="http", supports_query=True, supports_model=True,
        supports_execute=True, supports_async_task=False, capabilities=[],
    )
    with pytest.raises(AdapterError) as excinfo:
        registry.register(MockAdapter(code="midas_gen"), metadata=metadata)
    assert excinfo.value.code == ErrorCode.ADAPTER_NOT_FOUND.value


def test_get_registry_is_a_singleton() -> None:
    reset_registry()
    assert get_registry() is get_registry()
    reset_registry()


# ===========================================================================
# 10. the live adapter over httpx.MockTransport (still offline)
# ===========================================================================
def test_health_check_uses_the_host_root_and_the_mapi_key_header() -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "user": "",
                "program": "gen",
                "connectionID": "",
                "keyVerified": True,
                "status": "connected",
            },
        )

    transport, recorder = transport_for(responder)
    adapter = MidasNxAdapter(connection(), transport=transport)
    result = run(adapter.health_check())
    run(adapter.aclose())

    assert result.success is True
    assert result.data["keyVerified"] is True
    assert result.data["program"] == "gen"
    # §2.2 / §11.2：/mapikey/verify 在**主机根**，不含产品段
    assert recorder.requests[0].url.path == "/mapikey/verify"
    # §2.1：认证头是 MAPI-Key，绝不是 Authorization: Bearer
    assert recorder.requests[0].headers["MAPI-Key"] == "test-mapi-key"
    assert "authorization" not in {key.lower() for key in recorder.requests[0].headers}


def test_db_calls_are_product_scoped() -> None:
    transport, recorder = transport_for(lambda request: httpx.Response(200, json={"message": ""}))
    adapter = MidasNxAdapter(connection(product="civil"), transport=transport)
    result = run(adapter.query(QueryRequest(
        request_id="req_test_5", client_id=1, action="list", resource=None,
        payload=None, options={}, timeout_seconds=5, target="node",
    )))
    run(adapter.aclose())
    assert result.success is True
    assert result.data["items"] == []  # {"message": ""} 是空表，不是错误
    # MIDAS 路径**大小写不敏感**（实机验证：/db/NODE、/db/node、/db/Node、/db/nOdE
    # 全部 200 且返回相同结果），但**规范形式是大写**（对接规范 §3.6）：
    # 适配器统一发规范大写，使注册表、请求日志与响应根键三者一致。
    assert recorder.requests[0].url.path == "/civil/db/NODE"


def test_root_key_lookup_is_case_insensitive() -> None:
    """响应根键始终是规范的大写资源名，即使请求用小写路径。

    实机验证：请求 `/db/node` 返回 `{"NODE": {...}}`。适配器若按小写根键精确匹配，
    就会失配并落到「无根键」分支，把整个响应当成数据返回。
    """
    transport, _ = transport_for(
        lambda request: httpx.Response(
            200, json={"NODE": {"1": {"X": 1.0, "Y": 2.0, "Z": 3.0}}}
        )
    )
    adapter = MidasNxAdapter(connection(product="gen"), transport=transport)
    result = run(adapter.query(QueryRequest(
        request_id="req_test_case", client_id=1, action="list", resource=None,
        payload=None, options={}, timeout_seconds=5, target="node",
    )))
    run(adapter.aclose())
    assert result.success is True
    assert len(result.data["items"]) == 1, result.data


def test_two_hundred_with_an_error_body_is_a_failure() -> None:
    transport, _ = transport_for(
        lambda request: httpx.Response(200, json={"error": {"message": "Key Already Exist"}})
    )
    adapter = MidasNxAdapter(connection(), transport=transport)
    result = run(adapter.model(ModelRequest(
        request_id="req_test_6", client_id=1, action="create", resource="node",
        payload=None, options={}, timeout_seconds=5, data={"1": {"X": 0.0}},
    )))
    run(adapter.aclose())
    assert result.success is False
    assert result.error_code == ErrorCode.RESOURCE_CONFLICT.value
    assert result.raw_status == 200


def test_two_hundred_and_one_with_an_error_body_is_a_failure() -> None:
    transport, _ = transport_for(
        lambda request: httpx.Response(201, json={"error": {"message": "Wrong Field"}})
    )
    adapter = MidasNxAdapter(connection(), transport=transport)
    result = run(adapter.model(ModelRequest(
        request_id="req_test_7", client_id=1, action="create", resource="node",
        payload=None, options={}, timeout_seconds=5, data={"1": {"X": 0.0}},
    )))
    run(adapter.aclose())
    assert result.success is False
    assert result.error_code == ErrorCode.VALIDATION_ERROR.value


def test_nmas_backfills_the_crash_fields() -> None:
    """对接规范 §3.5 第 3 条：省略 rmX/rmY/rmZ 会杀死 MIDAS NX。"""
    transport, recorder = transport_for(
        lambda request: httpx.Response(201, json={"NMAS": {"1": {"FX": 10.0}}})
    )
    adapter = MidasNxAdapter(connection(), transport=transport)
    result = run(adapter.model(ModelRequest(
        request_id="req_test_8", client_id=1, action="create", resource="NMAS",
        payload=None, options={}, timeout_seconds=5, data={"1": {"FX": 10.0}},
    )))
    run(adapter.aclose())
    assert result.success is True
    sent = recorder.bodies()[0]["Assign"]["1"]
    assert sent["rmX"] == 0.0 and sent["rmY"] == 0.0 and sent["rmZ"] == 0.0
    assert any("rmX" in warning for warning in result.warnings)


def test_pres_requires_an_explicit_direction() -> None:
    """对接规范 §3.5 第 12 条：省略 DIRECTION 即套用错误默认值。"""
    transport, recorder = transport_for(lambda request: httpx.Response(201, json={}))
    adapter = MidasNxAdapter(connection(), transport=transport)
    with pytest.raises(AdapterError) as excinfo:
        run(adapter.model(ModelRequest(
            request_id="req_test_9", client_id=1, action="create", resource="PRES",
            payload=None, options={}, timeout_seconds=5, data={"1": {"ELEM": 1}},
        )))
    run(adapter.aclose())
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR.value
    assert "DIRECTION" in excinfo.value.message
    assert recorder.count == 0  # 在发请求之前就被拦下


def test_writes_are_not_retried_on_timeout() -> None:
    """V2.1 §26.5 / 对接规范 §3.5 第 5 条：超时 ≠ 回滚，写操作禁止自动重试。"""
    def responder(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("boom")

    transport, recorder = transport_for(responder)
    adapter = MidasNxAdapter(connection(), transport=transport)
    result = run(adapter.model(ModelRequest(
        request_id="req_test_10", client_id=1, action="create", resource="node",
        payload=None, options={}, timeout_seconds=5, data={"1": {"X": 0.0}},
    )))
    run(adapter.aclose())
    assert result.success is False
    assert result.error_code == ErrorCode.TASK_TIMEOUT.value
    assert recorder.count == 1


def test_reads_may_retry_once() -> None:
    """Reads retry a **connect** failure — that one can be a transient blip."""

    def responder(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    transport, recorder = transport_for(responder)
    adapter = MidasNxAdapter(connection(), transport=transport)
    result = run(adapter.probe_alive())
    run(adapter.aclose())
    assert result.success is False
    assert result.error_code == ErrorCode.MIDAS_CONNECTION_FAILED.value
    assert recorder.count == 2  # 只有读操作允许重试


def test_a_read_timeout_is_not_retried() -> None:
    """对接规范 §11.5.13 / §11.5.14 — a read-phase failure means "sent, no answer".

    The connection **was** established, the request **was** sent, and the server
    did not answer.  Retrying lands on exactly the same non-answer, for **both**
    causes of that signature: on a session frozen by a modal dialog every retry
    hits the same dialog (which is what made a live incident hang for minutes),
    and on a black-holed network path every retry is dropped just the same — and
    it only doubles the caller's wait.  §11.5.14: the two are indistinguishable
    from here, so the test asserts the retry behaviour, not a cause.

    This is a *different axis* from ``retry_safe``.  ``retry_safe`` answers "may
    this be re-sent without duplicating an effect?" (an idempotent read may);
    this answers "can re-sending possibly succeed?" (after a read timeout, no).
    """

    def responder(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("no response")

    transport, recorder = transport_for(responder)
    adapter = MidasNxAdapter(connection(), transport=transport)
    result = run(adapter.probe_alive())
    run(adapter.aclose())
    assert result.success is False
    assert result.error_code == ErrorCode.TASK_TIMEOUT.value
    assert recorder.count == 1, "a session that is not answering must not be re-probed"


def test_connection_failure_maps_to_midas_connection_failed() -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    transport, _ = transport_for(responder)
    adapter = MidasNxAdapter(connection(), transport=transport)
    result = run(adapter.health_check())
    run(adapter.aclose())
    assert result.error_code == ErrorCode.MIDAS_CONNECTION_FAILED.value
    assert "启动 MIDAS" in (result.error_message or "")


def test_delete_sends_one_bodiless_request_per_id() -> None:
    transport, recorder = transport_for(
        lambda request: httpx.Response(200, json={"NODE": {"3": {}}})
    )
    adapter = MidasNxAdapter(connection(), transport=transport)
    result = run(adapter.delete("/db/NODE", [1, 3]))
    run(adapter.aclose())
    assert result.success is True
    assert [request.url.path for request in recorder.requests] == [
        "/gen/db/NODE/1",
        "/gen/db/NODE/3",
    ]
    assert all(request.method == "DELETE" for request in recorder.requests)
    assert all(not request.content for request in recorder.requests)


def test_live_delete_refuses_the_assign_body() -> None:
    transport, recorder = transport_for(lambda request: httpx.Response(200, json={}))
    adapter = MidasNxAdapter(connection(), transport=transport)
    with pytest.raises(AdapterError) as excinfo:
        adapter.delete_using_assign_body("/db/NODE", {"Assign": {"1": None}})
    with pytest.raises(AdapterError):
        run(adapter.delete("/db/NODE", {"Assign": {"1": None}}))
    run(adapter.aclose())
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR.value
    assert recorder.count == 0


def test_live_get_table_shape_matches_and_posts_an_argument_body() -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"empty": {"HEAD": ["Node", "Load", "DX"], "DATA": [[1, "LC1(ST)", 0.1]]}},
        )

    transport, recorder = transport_for(responder)
    adapter = MidasNxAdapter(connection(), transport=transport)
    result = run(adapter.get_table("D", ["Node", "Load", "DX"], table_name="D"))
    run(adapter.aclose())

    assert result.success is True
    assert result.data["HEAD"] == ["Node", "Load", "DX"]
    assert recorder.requests[0].url.path == "/gen/post/TABLE"
    body = recorder.bodies()[0]
    # 响应根键就是传入的 TABLE_NAME（§11.5.6）
    assert body["Argument"]["TABLE_NAME"] == "D"
    assert body["Argument"]["COMPONENTS"] == ["Node", "Load", "DX"]


def test_live_get_table_requires_components_before_any_call() -> None:
    transport, recorder = transport_for(lambda request: httpx.Response(200, json={}))
    adapter = MidasNxAdapter(connection(), transport=transport)
    with pytest.raises(AdapterError):
        run(adapter.get_table("D", []))
    run(adapter.aclose())
    assert recorder.count == 0


def test_live_introspect_rejects_design_code_endpoints() -> None:
    transport, recorder = transport_for(lambda request: httpx.Response(200, json={}))
    adapter = MidasNxAdapter(connection(), transport=transport)
    with pytest.raises(AdapterError) as excinfo:
        run(adapter.introspect("/DESIGN/RC/KDS-41-20-2022/DCTL"))
    run(adapter.aclose())
    assert excinfo.value.code == ErrorCode.CAPABILITY_NOT_SUPPORTED.value
    assert recorder.count == 0


def test_live_introspect_reads_the_argument_wrapper() -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "$schema": "http://json-schema.org/draft-07/schema#",
                "Argument": {
                    "type": "object",
                    "properties": {"X": {"type": "number"}, "Y": {"type": "number"}},
                },
            },
        )

    transport, recorder = transport_for(responder)
    adapter = MidasNxAdapter(connection(), transport=transport)
    result = run(adapter.introspect("NODE"))
    run(adapter.aclose())
    assert result.success is True
    assert set(result.data["properties"]) == {"X", "Y"}
    assert recorder.requests[0].url.path == "/gen/info/db/NODE"


def test_live_adapter_rejects_a_non_connection_object() -> None:
    with pytest.raises(AdapterError):
        MidasNxAdapter("http://localhost:3030")  # type: ignore[arg-type]


def test_live_adapter_codes_and_metadata() -> None:
    gen = MidasNxAdapter(connection(product="gen"))
    civil = MidasNxAdapter(connection(product="civil"))
    assert gen.code == "midas_gen"
    assert civil.code == "midas_civil"
    metadata = run(gen.metadata())
    assert metadata.code == gen.code
    assert metadata.protocol == "http"
    assert "node.create" in metadata.capabilities
    # 总纲 §4.2.5: REGISTERED is a lifecycle stage, not an administrative state —
    # a registered adapter is *enabled*, it simply has not connected yet.
    assert gen.status == "enabled"
    assert gen.lifecycle is AdapterLifecycle.REGISTERED


def test_live_connect_moves_the_lifecycle_and_the_db_status() -> None:
    transport, _ = transport_for(
        lambda request: httpx.Response(
            200,
            json={
                "user": "",
                "program": "gen",
                "connectionID": "",
                "keyVerified": True,
                "status": "connected",
            },
        )
    )
    adapter = MidasNxAdapter(connection(), transport=transport)
    result = run(adapter.connect())
    run(adapter.aclose())
    assert result.success is True
    assert adapter.lifecycle is AdapterLifecycle.CONNECTED
    assert adapter.status == "enabled"  # §14: CONNECTED -> enabled


def test_a_freshly_registered_adapter_is_not_reported_disabled() -> None:
    """总纲 §4.2.5: ``disabled`` is an **administrative** flag, not a lifecycle stage.

    Regression guard.  ``REGISTERED`` / ``INITIALIZING`` used to map to
    ``disabled``, so a freshly constructed adapter was refused by the Capability
    Resolver with ``ADAPTER_UNAVAILABLE`` until something explicitly drove it to
    ``READY`` — the whole MCP layer was unusable on startup.

    It hid well: the **mock** adapter starts at ``READY``, so the entire offline
    suite passed.  Only the live tests, which build the real adapter, could see
    it.  This test makes the offline suite able to see it too.
    """
    from app.adapters.base import LIFECYCLE_DB_STATUS

    adapter = MidasNxAdapter(connection())  # no I/O happens on construction
    assert adapter.lifecycle is AdapterLifecycle.REGISTERED
    assert adapter.status == "enabled", (
        "a registered adapter is enabled — it simply has not connected yet"
    )

    # Every stage that is not an error must stay administratively usable, so a
    # resolver check on `status` never blocks a call that could otherwise run.
    for stage in (
        AdapterLifecycle.REGISTERED,
        AdapterLifecycle.INITIALIZING,
        AdapterLifecycle.READY,
        AdapterLifecycle.CONNECTING,
        AdapterLifecycle.CONNECTED,
        AdapterLifecycle.BUSY,
        AdapterLifecycle.DISCONNECTING,
    ):
        assert LIFECYCLE_DB_STATUS[stage][0] == "enabled", stage

    # …and the only two stages that are genuinely unusable say so.
    for stage in (AdapterLifecycle.ERROR, AdapterLifecycle.RECONNECTING):
        assert LIFECYCLE_DB_STATUS[stage][0] == "error", stage


def test_execute_dispatch_requires_confirm_for_doc_new() -> None:
    transport, recorder = transport_for(
        lambda request: httpx.Response(200, json={"UNIT": {"1": {}}})
    )
    adapter = MidasNxAdapter(connection(), transport=transport)
    with pytest.raises(AdapterError):
        run(adapter.execute(ExecuteRequest(
            request_id="req_test_11", client_id=1, action="new", resource=None,
            payload=None, options={}, timeout_seconds=5, data={},
        )))
    run(adapter.aclose())
    assert recorder.count == 0


def test_execute_dispatch_requires_confirm_for_doc_save() -> None:
    """``/doc/SAVE`` is guarded because it can block the **whole** session.

    Regression guard for a live incident.  On a document that has never been
    saved, ``/doc/SAVE`` makes NX pop the Save As dialog — it has nowhere to
    write, so it asks the operator.  A modal dialog blocks the entire API
    session: while it was open, ``GET /db/UNIT`` **and** ``GET /mapikey/verify``
    both timed out, and a test run hung for minutes until a human closed it.

    So the call must be refused **before** any HTTP request leaves this process,
    which is what ``recorder.count == 0`` asserts.
    """
    transport, recorder = transport_for(
        lambda request: httpx.Response(200, json={"UNIT": {"1": {}}})
    )
    adapter = MidasNxAdapter(connection(), transport=transport)
    with pytest.raises(AdapterError) as excinfo:
        run(adapter.execute(ExecuteRequest(
            request_id="req_test_12", client_id=1, action="save", resource=None,
            payload=None, options={}, timeout_seconds=5, data={},
        )))
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR.value
    run(adapter.aclose())
    assert recorder.count == 0, "nothing may reach the NX host"

    # …and ``SAVEAS`` with an explicit path is the form that can never ask.
    assert "SAVEAS" in str(excinfo.value)


def test_doc_saveas_with_a_path_still_works() -> None:
    """The safe alternative must not be over-guarded into uselessness."""
    transport, recorder = transport_for(
        lambda request: httpx.Response(
            200, json={"message": "MIDAS GEN NX command complete"}
        )
    )
    adapter = MidasNxAdapter(connection(), transport=transport)
    result = run(adapter.doc_saveas("D:\\work\\model.mgb"))
    run(adapter.aclose())
    assert recorder.count == 1
    assert result.raw_status == 200
    # ``/doc/*`` always wraps in ``Argument``; what must be **bare** is the value
    # inside it.  ``{"Argument": {"EXPORT_PATH": p}}`` is accepted with 200 but
    # writes nothing (§3.4 / §11.5.2), so the wire shape is asserted exactly.
    assert json.loads(recorder.requests[0].content) == {
        "Argument": "D:\\work\\model.mgb"
    }


# ===========================================================================
# 11. 会话**无响应**的可观测性 —— 超时阶段与会话判定
#     对接规范 §2.5.2（模态对话框阻塞整条通道）/ §11.5.12（没有打开项目）/
#     §11.5.13（从未保存过的文档上 /doc/SAVE 弹「另存为」并冻结整条会话）/
#     §11.5.14（**冻结与网络黑洞从服务端不可区分**：黑洞目标同样抛 ReadTimeout
#     而不是 ConnectTimeout，RFC 5737 地址的 TCP 连接还会被本机中间层「接受」，
#     所以判定只报告观测到的事实 + 列出候选原因）。
#     总纲 §4.4：错误码是封闭集合，区分处境靠 ``details["phase"]`` + 判定表。
# ===========================================================================
VERIFY_OK: dict[str, Any] = {
    "user": "",
    "program": "gen",
    "connectionID": "",
    "keyVerified": True,
    "status": "connected",
}
UNIT_OK: dict[str, Any] = {"UNIT": {"1": {"FORCE": "N", "LENGTH": "M"}}}


def _raises(exc: Exception) -> Any:
    """A MockTransport handler that raises ``exc`` (same object on every retry)."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    return handler


def _two_probe_responder(verify: Any, unit: Any) -> Any:
    """Branch on the two probe endpoints; each side is a response **or** a handler."""
    def responder(request: httpx.Request) -> httpx.Response:
        chosen = verify if request.url.path == "/mapikey/verify" else unit
        return chosen(request) if callable(chosen) else chosen

    return responder


def _diagnose(verify: Any, unit: Any) -> tuple[AdapterResult, Recorder]:
    """Run ``diagnose_session()`` over a faked transport; return it plus the recorder."""
    transport, recorder = transport_for(_two_probe_responder(verify, unit))
    adapter = MidasNxAdapter(connection(), transport=transport)
    result = run(adapter.diagnose_session())
    run(adapter.aclose())
    return result, recorder


def _paths(recorder: Recorder) -> list[str]:
    return [request.url.path for request in recorder.requests]


class _MysteryTimeout(httpx.TimeoutException):
    """A timeout type the adapter has no specific branch for -> ``phase="unknown"``."""


class _MysteryTransportError(httpx.HTTPError):
    """A transport failure that is neither a timeout nor a known subclass."""


@pytest.mark.parametrize(
    ("exc", "code", "phase"),
    [
        # 「从未到达服务」有**两条互不相关的分支**：NetworkError 的 ConnectError
        # 与 TimeoutException 的 ConnectTimeout。两者都必须是 phase="connect"，
        # 否则最常见的「产品没运行」会在最需要它的时候没有阶段。
        (httpx.ConnectError("refused"), ErrorCode.MIDAS_CONNECTION_FAILED, "connect"),
        (httpx.ConnectTimeout("connect timed out"), ErrorCode.MIDAS_CONNECTION_FAILED, "connect"),
        (httpx.ReadTimeout("no response"), ErrorCode.TASK_TIMEOUT, "read"),
        (httpx.ReadError("dropped"), ErrorCode.MIDAS_CONNECTION_FAILED, "read"),
        (httpx.WriteTimeout("write timed out"), ErrorCode.TASK_TIMEOUT, "write"),
        (httpx.WriteError("dropped"), ErrorCode.MIDAS_CONNECTION_FAILED, "write"),
        (httpx.PoolTimeout("no free connection"), ErrorCode.TASK_TIMEOUT, "pool"),
        (_MysteryTimeout("mystery"), ErrorCode.TASK_TIMEOUT, "unknown"),
        (_MysteryTransportError("mystery"), ErrorCode.MIDAS_CONNECTION_FAILED, "unknown"),
    ],
)
def test_every_timeout_and_transport_failure_carries_its_phase(
    exc: Exception, code: ErrorCode, phase: str
) -> None:
    """对接规范 §11.5.13：错误码复用总纲 §4.4，区分靠 ``details["phase"]``。"""
    transport, _ = transport_for(_raises(exc))
    adapter = MidasNxAdapter(connection(), transport=transport)
    with pytest.raises(AdapterError) as excinfo:
        run(adapter._request("GET", adapter._url("/db/UNIT")))
    run(adapter.aclose())
    error = excinfo.value
    assert error.code == code.value
    assert error.details["phase"] == phase
    assert error.details["phase"] in TRANSPORT_PHASES
    assert error.details["exception"] == type(exc).__name__


def test_connect_failures_are_never_reported_as_a_freeze() -> None:
    """连接从未建立 = 「产品没运行」，**不是**会话冻结（对接规范 §2.3 / §11.5.13）。

    ``ConnectError``（端口关闭）与 ``ConnectTimeout``（主机不可达）是两种类型、
    同一个含义，因此都被断言。
    """
    for exc in (httpx.ConnectError("refused"), httpx.ConnectTimeout("connect timed out")):
        transport, _ = transport_for(_raises(exc))
        adapter = MidasNxAdapter(connection(), transport=transport)
        result = run(adapter.health_check())
        run(adapter.aclose())
        assert result.success is False
        assert result.error_code == ErrorCode.MIDAS_CONNECTION_FAILED.value
        assert result.data["transport"]["phase"] == "connect"
        assert result.data["session"]["state"] == "service_down"
        assert result.data["session"]["confirmed"] is True
        message = result.error_message or ""
        assert "启动 MIDAS" in message
        assert "冻结" not in message, "连接失败不得使用冻结的措辞"


def test_read_timeout_names_both_candidates_and_keeps_task_timeout() -> None:
    """连接**已建立**、请求**已发出**、没有任何响应 —— 这是观测，不是原因（§11.5.14）。

    错误码仍是 ``TASK_TIMEOUT``（这次调用确实超时了），但阶段与消息必须说清楚
    「这意味着什么」**以及「怎么判别」**：消息里可以说模态对话框是**一个**已知原因，
    但不得把它当成**唯一**原因 —— 黑洞网络路径抛出的是同一个 ``ReadTimeout``。
    """
    transport, _ = transport_for(_raises(httpx.ReadTimeout("no response")))
    adapter = MidasNxAdapter(connection(), transport=transport)
    with pytest.raises(AdapterError) as excinfo:
        run(adapter._request("POST", adapter._url("/doc/SAVE")))
    result = run(adapter.model(ModelRequest(
        request_id="req_test_freeze_1", client_id=1, action="create", resource="node",
        payload=None, options={}, timeout_seconds=5, data={"1": {"X": 0.0}},
    )))
    run(adapter.aclose())

    error = excinfo.value
    assert error.code == ErrorCode.TASK_TIMEOUT.value
    assert error.details["phase"] == "read"
    assert "重试" in error.message
    # 两个候选原因都必须被点名：只提对话框就是这次的假阳性。
    assert "模态对话框" in error.message
    assert "网络" in error.message
    assert "Test-NetConnection" in error.message
    # 旧的排他性断言（「只有人工在 NX 主机上关对话框才能恢复」）不得回归。
    assert "关闭对话框才能恢复" not in error.message
    assert "是「会话被 NX 主机上的**模态对话框冻结**」的特征" not in error.message

    # 失败的数据调用同样能**机械地**取回阶段、状态与候选，而且没有补探测。
    assert result.data["transport"]["phase"] == "read"
    assert result.data["session"]["state"] == "session_unresponsive"
    assert result.data["session"]["confirmed"] is False
    assert list(result.data["session"]["candidates"]) == [
        "session_frozen",
        "network_unreachable",
    ]
    assert "network_unreachable" in result.data["session"]["candidate_evidence"]


def test_a_failing_data_call_does_not_probe_again() -> None:
    """§11.5.13 / §11.5.14：没有响应的会话不得被探测第二次 —— 只报告阶段，不追加请求。"""
    transport, recorder = transport_for(_raises(httpx.ReadTimeout("no response")))
    adapter = MidasNxAdapter(connection(), transport=transport)
    result = run(adapter.model(ModelRequest(
        request_id="req_test_freeze_2", client_id=1, action="create", resource="node",
        payload=None, options={}, timeout_seconds=5, data={"1": {"X": 0.0}},
    )))
    run(adapter.aclose())
    assert result.success is False
    assert result.error_code == ErrorCode.TASK_TIMEOUT.value
    assert result.data["session"]["state"] == "session_unresponsive"
    assert result.data["session"]["next_step"] == "midas_execute action=connect"
    assert recorder.count == 1, "写操作不重试，也**不得**补探测"
    assert _paths(recorder) == ["/gen/db/NODE"]


def test_diagnose_session_healthy() -> None:
    result, recorder = _diagnose(
        httpx.Response(200, json=VERIFY_OK), httpx.Response(200, json=UNIT_OK)
    )
    assert result.success is True
    assert result.data["state"] == "healthy"
    assert result.data["usable"] is True
    assert result.data["requires_human"] is False
    # 两条探针都**收到了应答**：正面证据，所以已证实，且没有候选。
    assert result.data["confirmed"] is True
    assert result.data["candidates"] == []
    assert result.data["probes"]["verify"]["ok"] is True
    assert result.data["probes"]["unit"]["ok"] is True
    assert result.data["probes"]["verify"]["endpoint"] == "/mapikey/verify"
    assert result.data["probes"]["unit"]["endpoint"] == "/db/UNIT"
    assert _paths(recorder) == ["/mapikey/verify", "/gen/db/UNIT"]


def test_diagnose_session_no_project_remedy_is_doc_new() -> None:
    """对接规范 §11.5.12：400 ``The project is not opened`` —— **可在 API 内恢复**。"""
    result, _ = _diagnose(
        httpx.Response(200, json=VERIFY_OK),
        httpx.Response(400, json={"error": {"message": "The project is not opened"}}),
    )
    assert result.success is False
    assert result.data["state"] == "no_project"
    assert result.error_code == ErrorCode.MODEL_UNAVAILABLE.value
    assert "POST /doc/NEW" in result.data["remedy"]
    assert result.data["recoverable_via_api"] is True
    assert result.data["requires_human"] is False
    assert result.data["usable"] is False
    # 上游**回了** 400 且文案明确：会话在应答 —— 已证实，无候选。
    assert result.data["confirmed"] is True
    assert result.data["candidates"] == []
    assert result.data["probes"]["unit"]["http_status"] == 400


def test_diagnose_session_document_frozen() -> None:
    """verify 正常、``/db/UNIT`` 读超时 —— 阻塞在**文档**那一层（§11.5.13 推论）。

    这个状态**保持已证实**：``/mapikey/verify`` **成功**是「会话正在应答」的正面
    证据（§11.5.14 判别表），网络黑洞不可能只吞掉 ``/db/UNIT`` 而放过
    ``/mapikey/verify``，所以阻塞只能在文档层 —— 这里**有**资格说 confirmed=True。
    """
    result, _ = _diagnose(
        httpx.Response(200, json=VERIFY_OK), _raises(httpx.ReadTimeout("no response"))
    )
    assert result.success is False
    assert result.data["state"] == "document_frozen"
    assert result.error_code == ErrorCode.TASK_TIMEOUT.value
    assert result.data["requires_human"] is True
    assert result.data["retry_helps"] is False
    assert result.data["confirmed"] is True
    assert result.data["candidates"] == []
    assert result.data["probes"]["verify"]["ok"] is True
    assert result.data["probes"]["unit"]["phase"] == "read"


def test_diagnose_session_unresponsive_needs_a_human_and_retrying_cannot_help() -> None:
    """§11.5.13 / §11.5.14：连**不碰文档**的 ``/mapikey/verify`` 都读超时。

    观测到的是「整条会话没有任何响应」；**不能**由此断言是被对话框冻结 ——
    黑洞网络路径给出逐字段相同的签名（§11.5.14）。有用的两半必须保留：
    两种候选都需要人工，且都不会因为重试而好转。
    """
    result, recorder = _diagnose(
        _raises(httpx.ReadTimeout("no response")),
        _raises(httpx.ReadTimeout("no response")),
    )
    assert result.success is False
    assert result.data["state"] == "session_unresponsive"
    assert result.error_code == ErrorCode.TASK_TIMEOUT.value
    assert result.data["usable"] is False
    assert result.data["requires_human"] is True
    assert result.data["retry_helps"] is False
    assert result.data["recoverable_via_api"] is False
    remedy = result.data["remedy"]
    # The remedy must give the **discriminating steps**, in order, and must not
    # assert a cause.  ``人工`` is deliberately absent: it was the old wording,
    # which implied the dialog *was* the answer (§11.5.14).
    assert "对话框" in remedy, "step 1: look for a modal dialog on the NX host"
    assert "可达" in remedy, "step 2: check the network path from the service host"
    assert remedy.index("对话框") < remedy.index("可达"), "the steps are ordered"
    assert "重试" in remedy
    assert result.data["candidates"] == ["session_frozen", "network_unreachable"]
    assert result.data["probes"]["verify"]["phase"] == "read"
    assert result.data["probes"]["unit"]["phase"] == "read"
    assert set(_paths(recorder)) == {"/mapikey/verify", "/gen/db/UNIT"}


def test_both_probes_read_timeout_reports_both_candidates_and_claims_nothing() -> None:
    """**回归守卫**（§11.5.14）：假阳性就是在这里产生的。

    对**真正不可达**的主机跑诊断，得到的是与「会话被冻结」**完全相同**的签名：
    ``/mapikey/verify`` 与 ``/db/UNIT`` 都读超时（实测黑洞目标抛的同样是
    ``httpx.ReadTimeout``）。旧代码因此判成 ``session_frozen`` 并让人去 NX 主机上
    关对话框 —— **而真实原因是网络**。补救措施是错的，这比没有诊断更糟。

    所以这里断言：状态名是**观测**（``session_unresponsive``），``confirmed`` 是
    ``False``，并且**两个**候选原因都带证据被列出。断言「它没有声称是对话框」
    用可机械检查的方式表达：``session_frozen`` 只作为**候选**出现，绝不作为状态。
    """
    result, _ = _diagnose(
        _raises(httpx.ReadTimeout("no response")),
        _raises(httpx.ReadTimeout("no response")),
    )
    assert result.success is False
    assert result.data["state"] == "session_unresponsive"
    assert result.data["confirmed"] is False, "不可区分的情形不得声称已证实"
    assert tuple(result.data["candidates"]) == ("session_frozen", "network_unreachable")
    evidence = result.data["candidate_evidence"]
    assert set(evidence) == {"session_frozen", "network_unreachable"}
    # 每个候选都要有自己的证据，而且证据要能对上「模态对话框」/「网络」两条路径。
    assert "模态对话框" in evidence["session_frozen"]
    assert "§11.5.13" in evidence["session_frozen"]
    assert "ReadTimeout" in evidence["network_unreachable"]
    assert "§11.5.14" in evidence["network_unreachable"]
    # 判定本身不得把对话框写成原因。
    assert "冻结" not in result.data["state"]
    assert "不等于" in result.data["diagnosis"], "判定必须明确否认「就是冻结」"
    assert "无法区分" in result.data["diagnosis"] or "不可区分" in result.data["diagnosis"]


def test_the_two_read_timeout_states_are_distinguishable_from_each_other() -> None:
    """``document_frozen`` 与 ``session_unresponsive`` **必须能互相区分**。

    §11.5.14 把「不可证明」的那一行单独拆出来，前提就是它与可证明的那一行
    **不同**：``document_frozen`` 有 ``/mapikey/verify`` 成功的正面证据，
    ``session_unresponsive`` 没有。只断言「两者各自能被产生出来」是不够的 ——
    那正是旧代码把两者混成一个「冻结」的方式。
    """
    document, _ = _diagnose(
        httpx.Response(200, json=VERIFY_OK), _raises(httpx.ReadTimeout("no response"))
    )
    unresponsive, _ = _diagnose(
        _raises(httpx.ReadTimeout("no response")),
        _raises(httpx.ReadTimeout("no response")),
    )
    # 两次探测的 **unit 探针完全一样**（都是 read 阶段超时），唯一的差别是 verify。
    assert document.data["probes"]["unit"]["phase"] == "read"
    assert unresponsive.data["probes"]["unit"]["phase"] == "read"
    assert document.data["probes"]["verify"]["ok"] is True
    assert unresponsive.data["probes"]["verify"]["ok"] is False

    assert document.data["state"] != unresponsive.data["state"]
    assert document.data["confirmed"] is True
    assert unresponsive.data["confirmed"] is False
    assert document.data["remedy"] != unresponsive.data["remedy"]
    # 只有不可证明的那一个才列候选。
    assert document.data["candidates"] == []
    assert list(unresponsive.data["candidates"]) == [
        "session_frozen",
        "network_unreachable",
    ]


def test_diagnose_session_service_down_short_circuits() -> None:
    """连接被拒时短路：不再为一条注定超时的 ``/db/UNIT`` 再等一次（§2.5.2）。"""
    result, recorder = _diagnose(
        _raises(httpx.ConnectError("refused")), httpx.Response(200, json=UNIT_OK)
    )
    assert result.data["state"] == "service_down"
    assert result.error_code == ErrorCode.MIDAS_CONNECTION_FAILED.value
    assert result.data["requires_human"] is True
    # 连接阶段失败**证明**请求没到服务（§11.5.14 判别表第一行）。
    assert result.data["confirmed"] is True
    assert result.data["candidates"] == []
    # 判据表里这一行的 /db/UNIT 是「—」：故意不探，形状上记为 None。
    assert result.data["probes"]["unit"] is None
    assert set(_paths(recorder)) == {"/mapikey/verify"}


def test_diagnose_session_auth_failed() -> None:
    result, recorder = _diagnose(
        httpx.Response(401, json={"error": {"message": "invalid key"}}),
        httpx.Response(200, json=UNIT_OK),
    )
    assert result.data["state"] == "auth_failed"
    assert result.error_code == ErrorCode.MIDAS_AUTH_FAILED.value
    assert "MAPI-Key" in result.data["remedy"]
    # 上游**回了** 401：应答本身即证据。
    assert result.data["confirmed"] is True
    assert result.data["candidates"] == []
    assert set(_paths(recorder)) == {"/mapikey/verify"}


def test_diagnose_session_degraded() -> None:
    """判据表覆盖不到的形态（verify 正常、``/db/UNIT`` 5xx）=> ``degraded``。"""
    result, _ = _diagnose(
        httpx.Response(200, json=VERIFY_OK),
        httpx.Response(500, json={"error": {"message": "boom"}}),
    )
    assert result.data["state"] == "degraded"
    assert result.error_code == ErrorCode.MIDAS_API_ERROR.value
    # 观测本身不足以支撑任何结论 —— 与 session_unresponsive 一样是未证实。
    assert result.data["confirmed"] is False
    assert result.data["probes"]["unit"]["http_status"] == 500


def test_service_down_and_session_unresponsive_differ_inside_one_exception_family() -> None:
    """**回归守卫**：两种处境都从 ``httpx.TimeoutException`` 家族里出来。

    旧代码用 ``except httpx.TimeoutException`` 一把抓住，于是「连接从未建立」与
    「连接已建立但没有响应」得到**同一个** ``TASK_TIMEOUT`` 和几乎一样的消息 ——
    而它们的处置完全不同（一个去启动产品，一个要先判别对话框/网络，§11.5.14）。
    所以这里断言两者**不同**，而不只是各自能被产生出来。
    """
    connect_timeout = httpx.ConnectTimeout("connect timed out")
    read_timeout = httpx.ReadTimeout("no response")
    assert isinstance(connect_timeout, httpx.TimeoutException)
    assert isinstance(read_timeout, httpx.TimeoutException)
    assert not isinstance(connect_timeout, httpx.ReadTimeout)
    assert not isinstance(read_timeout, httpx.ConnectTimeout)

    down, _ = _diagnose(_raises(connect_timeout), _raises(read_timeout))
    unresponsive, _ = _diagnose(_raises(read_timeout), _raises(read_timeout))

    assert down.data["state"] == "service_down"
    assert unresponsive.data["state"] == "session_unresponsive"
    assert down.data["state"] != unresponsive.data["state"]
    assert down.error_code == ErrorCode.MIDAS_CONNECTION_FAILED.value
    assert unresponsive.error_code == ErrorCode.TASK_TIMEOUT.value
    assert down.data["remedy"] != unresponsive.data["remedy"]
    assert "启动 MIDAS" in down.data["remedy"]
    # 「连接从未建立」是**可证明**的；「没有响应」不是（§11.5.14）。
    assert down.data["confirmed"] is True
    assert unresponsive.data["confirmed"] is False
    assert "对话框" in unresponsive.data["remedy"]
    assert "Test-NetConnection" in unresponsive.data["remedy"]


def test_unresponsive_remedy_gives_the_network_check_not_only_the_dialog() -> None:
    """§11.5.14：``session_unresponsive`` 的 remedy 是**判别步骤**，不是结论。

    顺序必须是这个顺序：(1) 先看 NX 主机上有没有对话框（那是 §11.5.13 的已知原因，
    能就地排除）；(2) 没有对话框时，从**运行本服务的机器**上确认主机是否可达 ——
    网络路径死了的话，MIDAS 侧做什么都无关。只提对话框就是这次要修掉的错误处置。
    """
    result, _ = _diagnose(
        _raises(httpx.ReadTimeout("no response")),
        _raises(httpx.ReadTimeout("no response")),
    )
    remedy = result.data["remedy"]
    assert "模态对话框" in remedy
    # 判别步骤 (2)：网络可达性检查必须存在，且点出可执行的命令。
    assert "可达" in remedy
    assert "ping" in remedy
    assert "Test-NetConnection" in remedy
    # 顺序：先对话框，后网络 —— remedy 自己说的「两步判别，按顺序做」。
    assert remedy.index("模态对话框") < remedy.index("Test-NetConnection")
    # 旧的排他性处置不得回归（它就是假阳性的 remedy）。
    assert "必须由人工在 NX 主机上关闭模态对话框" not in remedy
    assert "关闭对话框才能恢复" not in remedy
    # 有用的两半仍在。
    assert result.data["requires_human"] is True
    assert result.data["retry_helps"] is False


def test_read_phase_names_both_candidates_in_the_tables() -> None:
    """§11.5.14：``read`` 阶段**不是**「会话被冻结」的同义词。

    ``TRANSPORT_PHASE_MEANING["read"]`` 必须点名两个候选；``SESSION_STATE_BY_PHASE``
    由 ``read`` 推出的状态必须是**观测**（``session_unresponsive``）而不是
    ``session_frozen`` —— 后者是候选**原因**，不是状态。
    """
    meaning = TRANSPORT_PHASE_MEANING["read"]
    assert "对话框" in meaning
    assert "网络" in meaning
    assert "不可区分" in meaning
    assert SESSION_STATE_BY_PHASE["read"] == "session_unresponsive"
    assert SESSION_STATE_BY_PHASE["write"] == "session_unresponsive"
    assert "session_frozen" not in SESSION_STATE_BY_PHASE.values()
    # 候选名不得被提升成状态：两者都不是「能被观测区分出来的会话状态」。
    assert "session_frozen" not in SESSION_STATES
    assert "network_unreachable" not in SESSION_STATES


def test_check_channel_reuses_the_diagnosis() -> None:
    """``check_channel()`` 不再复制探针逻辑，也不再用一句「探针失败」代替判定。"""
    transport, recorder = transport_for(
        _two_probe_responder(
            httpx.Response(200, json=VERIFY_OK), _raises(httpx.ReadTimeout("no response"))
        )
    )
    adapter = MidasNxAdapter(connection(), transport=transport)
    result = run(adapter.check_channel())
    run(adapter.aclose())
    assert result.success is False
    assert result.data["state"] == "document_frozen"
    assert _paths(recorder) == ["/mapikey/verify", "/gen/db/UNIT"]


def test_execute_connect_returns_the_structured_diagnosis() -> None:
    """``midas_execute action=connect`` 暴露判定，且**不新增能力行**（V2.1 §16.1）。"""
    transport, recorder = transport_for(
        _two_probe_responder(
            httpx.Response(200, json=VERIFY_OK), httpx.Response(200, json=UNIT_OK)
        )
    )
    adapter = MidasNxAdapter(connection(), transport=transport)
    result = run(adapter.execute(ExecuteRequest(
        request_id="req_test_freeze_3", client_id=1, action="connect", resource="server",
        payload=None, options={}, timeout_seconds=5, data={},
    )))
    run(adapter.aclose())
    assert result.success is True
    assert result.data["keyVerified"] is True  # 原有字段原样保留
    assert result.data["diagnosis"]["state"] == "healthy"
    assert result.data["diagnosis"]["usable"] is True
    # /mapikey/verify **只跑一次**：connect() 的那一次被判定复用（§11.5.13）。
    assert _paths(recorder) == ["/mapikey/verify", "/gen/db/UNIT"]


def test_execute_connect_surfaces_service_down_without_a_second_probe() -> None:
    transport, recorder = transport_for(_raises(httpx.ConnectError("refused")))
    adapter = MidasNxAdapter(connection(), transport=transport)
    result = run(adapter.execute(ExecuteRequest(
        request_id="req_test_freeze_4", client_id=1, action="connect", resource="server",
        payload=None, options={}, timeout_seconds=5, data={},
    )))
    run(adapter.aclose())
    assert result.success is False
    assert result.error_code == ErrorCode.MIDAS_CONNECTION_FAILED.value
    assert result.data["diagnosis"]["state"] == "service_down"
    assert set(_paths(recorder)) == {"/mapikey/verify"}
    assert recorder.count == 2  # 读操作允许的一次重试，不是补探测


def test_execute_connect_reports_an_unresponsive_session() -> None:
    transport, recorder = transport_for(_raises(httpx.ReadTimeout("no response")))
    adapter = MidasNxAdapter(connection(), transport=transport)
    result = run(adapter.execute(ExecuteRequest(
        request_id="req_test_freeze_5", client_id=1, action="connect", resource="server",
        payload=None, options={}, timeout_seconds=5, data={},
    )))
    run(adapter.aclose())
    assert result.success is False
    assert result.error_code == ErrorCode.TASK_TIMEOUT.value
    assert result.data["diagnosis"]["state"] == "session_unresponsive"
    assert result.data["diagnosis"]["requires_human"] is True
    assert result.data["diagnosis"]["retry_helps"] is False
    # connect 这条路径同样不得声称原因（§11.5.14）。
    assert result.data["diagnosis"]["confirmed"] is False
    assert tuple(result.data["diagnosis"]["candidates"]) == (
        "session_frozen",
        "network_unreachable",
    )
    assert set(_paths(recorder)) == {"/mapikey/verify", "/gen/db/UNIT"}


def test_the_diagnosis_never_invents_an_error_code_or_a_state() -> None:
    """总纲 §4.4 是封闭集合：判定表只能复用既有错误码（§11.5.14 同理约束状态）。"""
    allowed = {
        None,
        ErrorCode.MODEL_UNAVAILABLE.value,
        ErrorCode.TASK_TIMEOUT.value,
        ErrorCode.MIDAS_CONNECTION_FAILED.value,
        ErrorCode.MIDAS_AUTH_FAILED.value,
        ErrorCode.MIDAS_API_ERROR.value,
    }
    for state, spec in SESSION_STATES.items():
        assert spec["error_code"] in allowed, state
        assert spec["diagnosis"] and spec["remedy"], state
        # 每个状态都必须声明「这个判定有多硬」，以及它的候选原因（可为空）。
        assert isinstance(spec["confirmed"], bool), state
        assert isinstance(spec["candidates"], tuple), state
        assert isinstance(spec["candidate_evidence"], dict), state
        # 候选名只能来自**已知**的名字：真实状态，或那两个已登记的候选原因。
        assert set(spec["candidates"]) <= set(SESSION_STATES) | {
            "session_frozen",
            "network_unreachable",
        }, state
        assert set(spec["candidate_evidence"]) == set(spec["candidates"]), state
        # 有候选就必须是未证实的；已证实的状态不得列候选。
        if spec["candidates"]:
            assert spec["confirmed"] is False, state
    # 三个映射表必须覆盖同一个封闭阶段集合
    assert tuple(SESSION_STATE_BY_PHASE) == TRANSPORT_PHASES
    assert set(TRANSPORT_PHASE_MEANING) == set(TRANSPORT_PHASES)
    assert set(TRANSPORT_PHASE_REMEDY) == set(TRANSPORT_PHASES)
    assert set(SESSION_STATE_BY_PHASE.values()) <= set(SESSION_STATES)


# ===========================================================================
# 12. 信封层 —— 调用方必须能从 MCP 信封里机械地取回状态
#     （总纲 §4.3.2：data 是信封里唯一保留的结构化字段）
# ===========================================================================
def _dispatcher_for(adapter: MidasNxAdapter) -> ToolDispatcher:
    """A minimal offline MCP stack around the **real** adapter (no DB, no server)."""
    registry = AdapterRegistry()
    registry.register(adapter)
    return ToolDispatcher(
        registry=registry,
        resolver=CapabilityResolver(registry),
        task_service=TaskService(),
    )


def test_envelope_of_an_unresponsive_data_call_carries_phase_and_state() -> None:
    """§11.5.13 / §11.5.14：超时的数据调用必须在信封里给出阶段、状态**与候选**，
    且**不补探测** —— 调用方只读信封也能看出这不是一个已证实的原因。"""
    transport, recorder = transport_for(_raises(httpx.ReadTimeout("no response")))
    adapter = MidasNxAdapter(connection(), transport=transport)
    dispatcher = _dispatcher_for(adapter)
    envelope = run(dispatcher.dispatch(TOOL_MODEL, {
        "action": "create", "resource": "node", "data": {"1": {"X": 0.0}},
    }))
    run(adapter.aclose())
    assert envelope["success"] is False
    assert envelope["errors"][0]["code"] == ErrorCode.TASK_TIMEOUT.value
    assert envelope["data"]["transport"]["phase"] == "read"
    assert envelope["data"]["session"]["state"] == "session_unresponsive"
    assert envelope["data"]["session"]["confirmed"] is False
    assert list(envelope["data"]["session"]["candidates"]) == [
        "session_frozen",
        "network_unreachable",
    ]
    assert envelope["data"]["session"]["next_step"] == "midas_execute action=connect"
    assert recorder.count == 1, "不得在失败的数据调用里追加探针请求"


def test_envelope_of_action_connect_carries_the_diagnosis() -> None:
    transport, recorder = transport_for(
        _two_probe_responder(
            httpx.Response(200, json=VERIFY_OK), httpx.Response(200, json=UNIT_OK)
        )
    )
    adapter = MidasNxAdapter(connection(), transport=transport)
    dispatcher = _dispatcher_for(adapter)
    envelope = run(dispatcher.dispatch(TOOL_EXECUTE, {"action": "connect"}))
    run(adapter.aclose())
    assert envelope["success"] is True
    assert envelope["data"]["keyVerified"] is True  # 原有字段不变
    assert envelope["data"]["diagnosis"]["state"] == "healthy"
    assert _paths(recorder) == ["/mapikey/verify", "/gen/db/UNIT"]


def test_envelope_of_action_connect_reports_an_unresponsive_session() -> None:
    transport, _ = transport_for(_raises(httpx.ReadTimeout("no response")))
    adapter = MidasNxAdapter(connection(), transport=transport)
    dispatcher = _dispatcher_for(adapter)
    envelope = run(dispatcher.dispatch(TOOL_EXECUTE, {"action": "connect"}))
    run(adapter.aclose())
    assert envelope["success"] is False
    assert envelope["errors"][0]["code"] == ErrorCode.TASK_TIMEOUT.value
    assert envelope["data"]["diagnosis"]["state"] == "session_unresponsive"
    assert envelope["data"]["diagnosis"]["requires_human"] is True
    assert envelope["data"]["diagnosis"]["retry_helps"] is False
    assert envelope["data"]["diagnosis"]["confirmed"] is False
    assert list(envelope["data"]["diagnosis"]["candidates"]) == [
        "session_frozen",
        "network_unreachable",
    ]
