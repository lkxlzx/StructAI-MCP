"""In-memory MIDAS adapter — the offline test double (V2.1 §22).

V2.1 §22 requires ``mock/adapter.py`` in Phase 1 so the whole stack can be
verified before a real MIDAS is reachable (对应总纲 §7 Phase 1.10).

Design rule: **the mock must not re-implement the rules.**  ``wrap`` /
``unwrap`` / ``build_assign`` / the DELETE guard / the ``/post/TABLE`` guards
are imported from :mod:`app.adapters.midas_gen.adapter`, so the offline suite
exercises the very code the live adapter runs.  What the mock *does* simulate is
the **upstream product behaviour** that the rules exist to survive:

* the three ``GET /db/*`` response shapes (对接规范 §3.2.1) —
  ``{"<RESOURCE>": {...}}``, ``{"message": ""}`` and ``{"error": {...}}``;
* ``POST`` being create-only (``400 Key Already Exist``, §11.5.3) and answering
  ``201`` on success (§11.5.4);
* the ``DELETE`` trap — the ``Assign``-body form ignores ids and wipes the table
  (§11.5.1);
* ``/post/TABLE`` returning an unstable root key, with ``"empty"`` carrying a
  **complete** table (§3.5 第 8 条);
* ``/doc/*`` answering ``{"message": "... command complete"}`` even when nothing
  happened (§3.5 第 7 条 / §11.5.2);
* ``/info`` wrapping the schema under ``Argument`` (§5.0.1) and 404-ing for
  non-``/db`` resources (§5.1).
"""

from collections import deque
from copy import deepcopy
from typing import Any, Final, Sequence

from app.adapters.base import (
    LIFECYCLE_DB_STATUS,
    AdapterLifecycle,
    AdapterMetadata,
    AdapterResult,
    Capability,
    ExecuteRequest,
    MidasClientConfig,
    ModelRequest,
    QueryRequest,
)
from app.adapters.errors import AdapterError
from app.adapters.midas_gen.adapter import (
    CAPABILITIES,
    WRAPPER_ARGUMENT,
    WRAPPER_ASSIGN,
    apply_query,
    apply_write_contract,
    build_assign,
    build_assign_body,
    coerce_assign_records,
    find_table_shape,
    guard_local_path,
    load_case_suffix_warnings,
    normalise_endpoint,
    require_table_components,
    resource_of,
)
from app.adapters.midas_gen.adapter import outer_key_means as _outer_key_means
from app.core.constants import AdapterStatus, TaskStatus
from app.core.errors import ErrorCode

__all__ = ["MockAdapter", "MockResponse"]

#: Default in-memory model.  ``NODE`` is intentionally **absent** so that
#: ``GET /db/NODE`` returns the empty-table shape ``{"message": ""}`` — the shape
#: the docs call out as the easiest one to get wrong (对接规范 §3.2.1).
DEFAULT_MODEL: Final[dict[str, dict[str, Any]]] = {
    "UNIT": {"1": {"FORCE": "KN", "DIST": "M", "HEAT": "KJ", "TEMPER": "C"}},
    "STYP": {
        "1": {
            "STYP": 0,
            "MASS": 1,
            "GRAV": 9.806,
            "bSELFWEIGHT": False,
        }
    },
}

#: 自省 schema 的小样本（对接规范 §5.0.1 的 ``Argument`` 包装 + §5.2 的不完整）。
DEFAULT_SCHEMAS: Final[dict[str, dict[str, Any]]] = {
    "NODE": {"X": {"type": "number"}, "Y": {"type": "number"}, "Z": {"type": "number"}},
    "ELEM": {"TYPE": {"type": "string"}, "NODE": {"type": "array"}},
    "UNIT": {
        "FORCE": {"type": "string"},
        "DIST": {"type": "string"},
        "HEAT": {"type": "string"},
        "TEMPER": {"type": "string"},
    },
    "CNLD": {"ITEMS": {"type": "array"}},
    "CONS": {"ITEMS": {"type": "array"}},
}


class MockResponse:
    """One scripted upstream exchange (payload + status)."""

    __slots__ = ("payload", "status")

    def __init__(self, payload: Any, status: int = 200) -> None:
        self.payload = payload
        self.status = status


class MockAdapter:
    """A Protocol-complete, in-memory MIDAS adapter."""

    def __init__(
        self,
        *,
        code: str = "mock_midas",
        software: str = "MIDAS Gen",
        version: str = "2024",
        version_range: str = ">=2024",
        model: dict[str, dict[str, Any]] | None = None,
        table_root: str | None = None,
        strict_put: bool = False,
    ) -> None:
        self._code = code
        self._software = software
        self._version = version
        self._version_range = version_range
        self._model: dict[str, dict[str, Any]] = deepcopy(model or DEFAULT_MODEL)
        self._schemas: dict[str, dict[str, Any]] = deepcopy(DEFAULT_SCHEMAS)
        self._scripted: deque[MockResponse] = deque()
        self._lifecycle = AdapterLifecycle.READY

        #: Root key used by :meth:`get_table`; ``None`` cycles through the three
        #: observed values so tests can prove nothing indexes by key name.
        self.table_root: str | None = table_root
        #: When True a ``PUT`` on a missing key answers 404, which is what makes
        #: the upsert PUT→POST fallback observable.
        self.strict_put = strict_put

        self.request_log: list[dict[str, Any]] = []
        #: Set when the table-wiping ``Assign`` DELETE actually ran.
        self.trap_fired: bool = False
        self.wiped_tables: list[str] = []
        self._table_roots: deque[str] = deque(["empty", "Result Table", "Displacement"])

    # ------------------------------------------------------------------ #
    # V2.1 §13 properties / metadata
    # ------------------------------------------------------------------ #
    @property
    def code(self) -> str:
        return self._code

    @property
    def software(self) -> str:
        return self._software

    @property
    def version(self) -> str:
        return self._version

    @property
    def lifecycle(self) -> AdapterLifecycle:
        return self._lifecycle

    @property
    def status(self) -> str:
        return LIFECYCLE_DB_STATUS.get(
            self._lifecycle, (AdapterStatus.ENABLED.value, "disconnected")
        )[0]

    @property
    def model_store(self) -> dict[str, dict[str, Any]]:
        """The in-memory model, for assertions."""
        return self._model

    async def metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            code=self._code,
            name="MIDAS Mock Adapter",
            software=self._software,
            version_range=self._version_range,
            protocol="memory",
            supports_query=True,
            supports_model=True,
            supports_execute=True,
            supports_async_task=True,
            capabilities=[capability.code for capability in CAPABILITIES],
        )

    async def capabilities(self) -> list[Capability]:
        return list(CAPABILITIES)

    async def connect(self, client: MidasClientConfig | None = None) -> AdapterResult:
        self._lifecycle = AdapterLifecycle.CONNECTED
        return await self.health_check()

    async def disconnect(self) -> AdapterResult:
        self._lifecycle = AdapterLifecycle.READY
        return AdapterResult.ok({"disconnected": True})

    # ------------------------------------------------------------------ #
    # test affordances
    # ------------------------------------------------------------------ #
    def script_response(self, payload: Any, status: int = 200) -> None:
        """Queue the **next** upstream response verbatim (shape injection)."""
        self._scripted.append(MockResponse(payload, status))

    def seed(self, resource: str, records: dict[str, Any]) -> None:
        """Put records into the in-memory model."""
        self._model[resource_of(resource)] = deepcopy(records)

    def clear_model(self) -> None:
        self._model.clear()

    def calls(self, *, method: str | None = None, endpoint: str | None = None) -> list[dict[str, Any]]:
        """Filtered request log (assertion helper)."""
        out = self.request_log
        if method is not None:
            out = [entry for entry in out if entry["method"] == method.upper()]
        if endpoint is not None:
            wanted = normalise_endpoint(endpoint)
            out = [
                entry
                for entry in out
                if normalise_endpoint(entry["endpoint"]) == wanted
            ]
        return out

    # ------------------------------------------------------------------ #
    # V2.1 §17.3 — the *same* pure functions the live adapter uses
    # ------------------------------------------------------------------ #
    def wrap(self, payload: Any, wrapper: str | None) -> dict[str, Any]:
        from app.adapters.midas_gen.adapter import wrap_payload

        return wrap_payload(payload, wrapper)

    def unwrap(self, response: Any, root_key: str | None) -> Any:
        from app.adapters.midas_gen.adapter import unwrap_response

        return unwrap_response(response, root_key)

    # ------------------------------------------------------------------ #
    # §4.1 helpers (same guards as the live adapter)
    # ------------------------------------------------------------------ #
    def build_assign(
        self,
        outer_key: Any,
        inner: Any,
        *,
        resource: str | None = None,
        kind: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        return build_assign(outer_key, inner, resource=resource, kind=kind)

    @staticmethod
    def outer_key_means(resource: str) -> str:
        return _outer_key_means(resource)

    # ------------------------------------------------------------------ #
    # simulated upstream
    # ------------------------------------------------------------------ #
    def _log_call(self, method: str, endpoint: str, body: Any = None) -> None:
        """Append to :attr:`request_log` without simulating a response."""
        self.request_log.append(
            {
                "method": method.upper(),
                "endpoint": endpoint,  # 原样记录；calls() 里再做规范化比较
                "body": deepcopy(body),
            }
        )

    def _exchange(self, method: str, endpoint: str, body: Any = None) -> MockResponse:
        """Return the simulated upstream response for one call."""
        self._log_call(method, endpoint, body)
        if self._scripted:
            return self._scripted.popleft()
        return self._simulate(method.upper(), normalise_endpoint(endpoint), body)

    def _simulate(self, method: str, endpoint: str, body: Any) -> MockResponse:
        resource = resource_of(endpoint)
        table = self._model.get(resource, {})
        parts = [part for part in endpoint.split("/") if part]
        addressed_id = parts[-1] if len(parts) >= 3 and parts[-1].isdigit() else None

        if method == "GET":
            if endpoint == "/db/UNIT":
                # §11.3：/db/UNIT 即使空模型也有数据；这里保留空表分支由脚本注入。
                return MockResponse({resource: deepcopy(table)} if table else {"message": ""})
            if table:
                # 形态 1：{"<RESOURCE>": {...}}
                return MockResponse({resource: deepcopy(table)})
            # 形态 2：{"message": ""} —— 成功且表为空，**不是** {"NODE": {}}
            return MockResponse({"message": ""})

        if method == "POST":
            inner = (body or {}).get(WRAPPER_ASSIGN, {})
            if not isinstance(inner, dict):
                return MockResponse({"error": {"message": "Wrong Field"}}, 400)
            existing = self._model.setdefault(resource, {})
            clash = [key for key in inner if str(key) in existing]
            if clash:
                # §11.5.3：POST 是「仅创建」，键已存在 → 400 Key Already Exist
                return MockResponse({"error": {"message": "Key Already Exist"}}, 400)
            for key, record in inner.items():
                existing[str(key)] = deepcopy(record)
            # §11.5.4：POST 成功返回 201 并回显创建的记录
            return MockResponse({resource: deepcopy(existing)}, 201)

        if method == "PUT":
            inner = (body or {}).get(WRAPPER_ASSIGN, {})
            if not isinstance(inner, dict):
                return MockResponse({"error": {"message": "Wrong Field"}}, 400)
            existing = self._model.setdefault(resource, {})
            if self.strict_put:
                missing = [key for key in inner if str(key) not in existing]
                if missing:
                    return MockResponse({"error": {"message": "Key does not exist"}}, 404)
            for key, record in inner.items():
                existing[str(key)] = deepcopy(record)
            return MockResponse({resource: deepcopy(existing)}, 200)

        if method == "DELETE":
            if addressed_id is not None:
                # §11.5.1：DELETE {endpoint}/{id} 才是删单条
                self._model.get(resource, {}).pop(addressed_id, None)
                return MockResponse({resource: deepcopy(self._model.get(resource, {}))})
            # 🔴 §11.5.1：带 Assign 体的 DELETE 忽略 id、清空整表
            self.trap_fired = True
            self.wiped_tables.append(resource)
            self._model[resource] = {}
            return MockResponse({resource: {}})

        return MockResponse({"error": {"message": f"Unknown Error {method}"}}, 400)

    # ------------------------------------------------------------------ #
    # health / introspection
    # ------------------------------------------------------------------ #
    async def health_check(self) -> AdapterResult:
        self._log_call("GET", "/mapikey/verify")
        if self._scripted:
            return self._as_result(self._scripted.popleft(), "/mapikey/verify")
        payload = {
            # 对接规范 §11.4：实测 user / connectionID 均为空字符串
            "user": "",
            "program": "gen",
            "connectionID": "",
            "keyVerified": True,
            "status": "connected",
        }
        return AdapterResult.ok(
            payload,
            warnings=["mock: 对接规范 §11.4 —— user / connectionID 实测为空，不得依赖。"],
            raw_status=200,
            raw_response=payload,
        )

    async def probe_alive(self) -> AdapterResult:
        response = self._exchange("GET", "/db/UNIT")
        payload = response.payload
        if response.status >= 400:
            return AdapterResult.failed(
                ErrorCode.MIDAS_API_ERROR, str(payload), raw_status=response.status
            )
        if isinstance(payload, dict) and "message" in payload:
            return AdapterResult.ok({}, raw_status=response.status, raw_response=payload)
        return AdapterResult.ok(
            payload.get("UNIT", {}), raw_status=response.status, raw_response=payload
        )

    async def check_channel(self) -> AdapterResult:
        health = await self.health_check()
        if not health.success:
            return health
        probe = await self.probe_alive()
        if not probe.success:
            return probe
        return AdapterResult.ok({"health": health.data, "probe": probe.data})

    @staticmethod
    def is_introspectable(resource: str) -> bool:
        return normalise_endpoint(resource).lower().startswith("/db/")

    async def introspect(self, resource: str) -> AdapterResult:
        endpoint = normalise_endpoint(resource)
        if not self.is_introspectable(endpoint):
            raise AdapterError(
                ErrorCode.CAPABILITY_NOT_SUPPORTED,
                f"{endpoint} 不支持自省：对接规范 §5.1 —— /info 只为 /db/* 提供，"
                "设计代码端点一律 404。",
                details={"endpoint": endpoint},
            )
        response = self._exchange("GET", f"/info{endpoint}")
        name = resource_of(endpoint)
        payload = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            # §5.0.1：包装键固定为 Argument，不是资源名
            "Argument": {
                "type": "object",
                "properties": deepcopy(self._schemas.get(name, {})),
            },
        }
        return AdapterResult.ok(
            {
                "resource": name,
                "endpoint": endpoint,
                "properties": payload["Argument"]["properties"],
                "schema": payload["Argument"],
                "complete": False,
            },
            raw_status=response.status,
            raw_response=payload,
        )

    # ------------------------------------------------------------------ #
    # query / model
    # ------------------------------------------------------------------ #
    async def query(self, request: QueryRequest) -> AdapterResult:
        target = (request.target or "").strip()
        lowered = target.lower()
        if lowered in ("server", "health", "connection"):
            return await self.check_channel()
        if lowered in ("client", "client_info"):
            return AdapterResult.ok(
                {
                    "code": self._code,
                    "software": self._software,
                    "api_key": "********",
                    "max_concurrency": 1,
                    "lifecycle": self._lifecycle.value,
                }
            )
        if lowered in ("capabilities", "capability"):
            metadata = await self.metadata()
            return AdapterResult.ok({"metadata": metadata.to_db_payload()})
        if request.action == "inspect":
            return await self.introspect(target)
        return await self._read_records(
            target, query=request.query, page=request.page, page_size=request.page_size
        )

    async def _read_records(
        self,
        resource: str,
        *,
        query: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> AdapterResult:
        endpoint = normalise_endpoint(resource)
        response = self._exchange("GET", endpoint)
        payload = response.payload
        if isinstance(payload, dict) and "error" in payload:
            return AdapterResult.failed(
                ErrorCode.MIDAS_API_ERROR,
                str(payload["error"]),
                raw_status=response.status,
                raw_response=payload,
            )
        raw_records = (
            payload.get(resource_of(endpoint), {})
            if isinstance(payload, dict)
            else {}
        )
        items: list[dict[str, Any]] = []
        for key, value in (raw_records or {}).items():
            record = dict(value) if isinstance(value, dict) else {"value": value}
            record.setdefault("id", key)
            items.append(record)
        filtered, warnings = apply_query(items, query)
        size = max(1, min(int(page_size or 100), 500))
        current = max(1, int(page or 1))
        start = (current - 1) * size
        return AdapterResult.ok(
            {
                "resource": resource_of(endpoint),
                "endpoint": endpoint,
                "total": len(filtered),
                "page": current,
                "page_size": size,
                "items": filtered[start : start + size],
            },
            warnings=warnings,
            raw_status=response.status,
            raw_response=payload,
        )

    async def model(self, request: ModelRequest) -> AdapterResult:
        endpoint = normalise_endpoint(request.resource)
        action = (request.action or "").lower()
        options = dict(request.options or {})

        if action in ("read", "list", "get"):
            raw_query = options.get("query")
            return await self._read_records(
                endpoint, query=raw_query if isinstance(raw_query, dict) else None
            )
        if action == "delete":
            ids: Any = request.data
            if isinstance(request.data, dict):
                ids = request.data.get("ids", request.data)
            return await self.delete(endpoint, ids)
        if action == "validate":
            records = coerce_assign_records(endpoint, request.data)
            return AdapterResult.ok(
                {
                    "endpoint": endpoint,
                    "valid": True,
                    "dry_run": True,
                    "body": {WRAPPER_ASSIGN: build_assign_body(endpoint, records)},
                }
            )
        if action in ("create", "update", "upsert"):
            if action == "upsert":
                return await self.create_or_update(endpoint, request.data)
            records = coerce_assign_records(endpoint, request.data)
            # 与实盘同一条契约守卫（§3.5 第 3 / 12 条）
            records, contract_warnings = apply_write_contract(endpoint, records)
            body = {WRAPPER_ASSIGN: build_assign_body(endpoint, records)}
            if options.get("dry_run"):
                return AdapterResult.ok(
                    {"endpoint": endpoint, "dry_run": True, "body": body},
                    warnings=contract_warnings,
                )
            response = self._exchange(
                "POST" if action == "create" else "PUT", endpoint, body
            )
            result = self._as_result(response, endpoint)
            result.warnings.extend(contract_warnings)
            return result
        raise AdapterError(
            ErrorCode.CAPABILITY_NOT_SUPPORTED,
            f"mock: midas_model action={request.action!r} 不受支持",
        )

    async def execute(self, request: ExecuteRequest) -> AdapterResult:
        action = (request.action or "").lower()
        data = dict(request.data or {})
        if action in ("connect", "verify", "health"):
            return await self.connect()
        if action == "disconnect":
            return await self.disconnect()
        if action == "probe":
            return await self.probe_alive()
        if action == "check_channel":
            return await self.check_channel()
        if action == "introspect":
            return await self.introspect(str(data.get("resource") or request.resource or ""))
        if action in ("table", "result_table", "get_table"):
            return await self.get_table(
                str(data.get("table_type") or ""),
                data.get("components") or [],
                load_case_names=data.get("load_case_names"),
                table_name=data.get("table_name"),
            )
        if action in ("new", "doc_new"):
            if not data.get("confirm"):
                raise AdapterError(
                    ErrorCode.VALIDATION_ERROR,
                    "/doc/NEW 需要显式 confirm=True（对接规范 §3.5 第 4 条）。",
                )
            return AdapterResult.ok({"message": "... command complete"})
        if action in ("open", "save", "saveas", "close", "import", "export", "anal",
                      "calculate", "analysis"):
            if action in ("open", "saveas", "import", "export") and data.get("path"):
                guard_local_path(data["path"])
            # §3.5 第 7 条 / §11.5.2：成功与假成功返回同一句文案
            return AdapterResult.ok({"message": "... command complete"})
        raise AdapterError(
            ErrorCode.CAPABILITY_NOT_SUPPORTED,
            f"mock: midas_execute action={request.action!r} 不受支持",
        )

    # ------------------------------------------------------------------ #
    # §11.5.1 DELETE
    # ------------------------------------------------------------------ #
    @staticmethod
    def _coerce_ids(ids: Any) -> list[str]:
        if isinstance(ids, dict):
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR,
                "拒绝执行：DELETE 携带 ID 键的 Assign 体会**清空整张表**，完全忽略传入的 id"
                "（对接规范 §11.5.1）。单条删除只能用 delete(resource, [id])；"
                "确实要清空整表请显式调用 delete_all(resource, confirm=True)。",
                details={"received_type": "dict"},
            )
        if ids is None:
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR, "delete 需要至少一个 id（逐 id 单条删除）"
            )
        if isinstance(ids, (str, int)) and not isinstance(ids, bool):
            return [str(ids)]
        if isinstance(ids, (list, tuple, set, frozenset)):
            resolved = [str(item) for item in ids]
            if not resolved:
                raise AdapterError(ErrorCode.VALIDATION_ERROR, "delete 需要至少一个 id")
            return resolved
        raise AdapterError(
            ErrorCode.VALIDATION_ERROR,
            f"delete 的 ids 必须是标量或数组，收到 {type(ids).__name__}",
        )

    async def delete(self, resource: str, ids: Any, **kwargs: Any) -> AdapterResult:
        endpoint = normalise_endpoint(resource)
        id_list = self._coerce_ids(ids)
        deleted: list[str] = []
        for one in id_list:
            response = self._exchange("DELETE", f"{endpoint}/{one}")
            result = self._as_result(response, endpoint)
            if not result.success:
                return result
            deleted.append(one)
        return AdapterResult.ok(
            {"endpoint": endpoint, "mode": "per_id", "deleted": deleted},
            raw_status=200,
        )

    def delete_using_assign_body(
        self, resource: str, assign_body: Any = None
    ) -> None:
        """**Always raises** — the §11.5.1 guard (identical to the live adapter)."""
        raise AdapterError(
            ErrorCode.VALIDATION_ERROR,
            f"禁止：{normalise_endpoint(resource)} 的 Assign 体 DELETE 会**清空整张表**。"
            "对接规范 §11.5.1 实机复现：请求里只有 id 1，响应却回显了 1 和 3 两条记录，"
            "随后整表清空 —— 它完全忽略传入的 id。单条删除请用 delete(resource, [id])；"
            "确实要清空整表请显式调用 delete_all(resource, confirm=True)。",
            details={"endpoint": normalise_endpoint(resource)},
        )

    async def delete_all(
        self, resource: str, *, confirm: bool = False, **kwargs: Any
    ) -> AdapterResult:
        endpoint = normalise_endpoint(resource)
        if not confirm:
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR,
                f"delete_all({endpoint}) 需要显式 confirm=True：它会**清空整张表**"
                "（对接规范 §3.5 第 1 条 / §11.5.1）。",
                details={"endpoint": endpoint},
            )
        response = self._exchange("DELETE", endpoint, {WRAPPER_ASSIGN: {}})
        result = self._as_result(response, endpoint)
        result.warnings.append(
            "mock: 已模拟 §11.5.1 的整表清空语义（trap_fired=True）——上游忽略请求体里的 id。"
        )
        return result

    # ------------------------------------------------------------------ #
    # §11.5.3 upsert
    # ------------------------------------------------------------------ #
    async def create_or_update(
        self, resource: str, data: Any, *, order: str = "put_first", **kwargs: Any
    ) -> AdapterResult:
        endpoint = normalise_endpoint(resource)
        records = coerce_assign_records(endpoint, data)
        records, contract_warnings = apply_write_contract(endpoint, records)
        body = {WRAPPER_ASSIGN: build_assign_body(endpoint, records)}
        attempts: list[dict[str, Any]] = []
        if order == "put_first":
            first = self._as_result(self._exchange("PUT", endpoint, body), endpoint)
            attempts.append({"method": "PUT", "success": first.success})
            if first.success:
                first.data = {"order": order, "attempts": attempts}
                first.warnings.extend(contract_warnings)
                return first
            missing = first.error_code == ErrorCode.RESOURCE_NOT_FOUND.value or "not exist" in (
                first.error_message or ""
            ).lower()
            if not missing:
                first.data = {"order": order, "attempts": attempts}
                return first
            second = self._as_result(self._exchange("POST", endpoint, body), endpoint)
            attempts.append({"method": "POST", "success": second.success})
            second.data = {"order": order, "attempts": attempts}
            second.warnings.extend(contract_warnings)
            return second
        first = self._as_result(self._exchange("POST", endpoint, body), endpoint)
        attempts.append({"method": "POST", "success": first.success})
        if first.success:
            first.data = {"order": order, "attempts": attempts}
            first.warnings.extend(contract_warnings)
            return first
        if first.error_code != ErrorCode.RESOURCE_CONFLICT.value:
            first.data = {"order": order, "attempts": attempts}
            return first
        second = self._as_result(self._exchange("PUT", endpoint, body), endpoint)
        attempts.append({"method": "PUT", "success": second.success})
        second.data = {"order": order, "attempts": attempts}
        second.warnings.extend(contract_warnings)
        return second

    async def upsert(self, resource: str, data: Any, **kwargs: Any) -> AdapterResult:
        return await self.create_or_update(resource, data, **kwargs)

    # ------------------------------------------------------------------ #
    # §11.5.6 /post/TABLE
    # ------------------------------------------------------------------ #
    async def get_table(
        self,
        table_type: str,
        components: Sequence[str],
        *,
        load_case_names: Sequence[str] | None = None,
        table_name: str | None = None,
        **kwargs: Any,
    ) -> AdapterResult:
        name = require_table_components(table_type, components, table_name)
        root = self.table_root or self._table_roots[0]
        if self.table_root is None:
            self._table_roots.rotate(-1)
        table = {
            "HEAD": list(components),
            "DATA": [[1, (load_case_names or ["LC1(ST)"])[0], 0.0]],
        }
        payload = {root: deepcopy(table), "FORCE": "KN", "DIST": "M"}
        self._log_call(
            "POST",
            "/post/TABLE",
            {
                WRAPPER_ARGUMENT: {
                    "TABLE_NAME": name,
                    "TABLE_TYPE": table_type,
                    "COMPONENTS": list(components),
                }
            },
        )
        found = find_table_shape(payload)
        return AdapterResult.ok(
            found,
            warnings=[
                f"mock: 响应根键为 {root!r}（§3.5 第 8 条：不稳定，'empty' 也能承载完整表）",
            ]
            + load_case_suffix_warnings(load_case_names),
            raw_status=200,
            raw_response=payload,
        )

    # ------------------------------------------------------------------ #
    # V2.1 §13 task members
    # ------------------------------------------------------------------ #
    async def get_task(self, task_id: str) -> AdapterResult:
        return AdapterResult(
            success=False,
            status=TaskStatus.FAILED.value,
            error_code=ErrorCode.NOT_IMPLEMENTED.value,
            error_message="mock: MIDAS 没有任务端点（对接规范 §2.5.1）",
        )

    async def cancel_task(self, task_id: str) -> AdapterResult:
        return AdapterResult(
            success=False,
            status=TaskStatus.FAILED.value,
            error_code=ErrorCode.NOT_IMPLEMENTED.value,
            error_message="mock: MIDAS 没有任务端点（对接规范 §2.5.1）",
        )

    async def retry_task(self, task_id: str) -> AdapterResult:
        return AdapterResult(
            success=False,
            status=TaskStatus.FAILED.value,
            error_code=ErrorCode.NOT_IMPLEMENTED.value,
            error_message="mock: MIDAS 没有任务端点（对接规范 §2.5.1）",
        )

    # ------------------------------------------------------------------ #
    @staticmethod
    def _as_result(response: MockResponse, endpoint: str) -> AdapterResult:
        """Turn a simulated exchange into an :class:`AdapterResult`."""
        from app.adapters.errors import normalize_upstream

        verdict = normalize_upstream(
            payload=response.payload,
            raw_status=response.status,
            context=endpoint,
        )
        if not verdict.ok:
            return AdapterResult(
                success=False,
                status=TaskStatus.FAILED.value,
                error_code=verdict.error_code,
                error_message=verdict.error_message,
                warnings=list(verdict.warnings),
                raw_status=response.status,
                raw_response=response.payload,
            )
        return AdapterResult.ok(
            verdict.data,
            warnings=list(verdict.warnings),
            raw_status=response.status,
            raw_response=response.payload,
        )
