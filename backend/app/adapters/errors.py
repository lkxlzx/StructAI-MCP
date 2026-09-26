"""Adapter error type and upstream success/failure normalization.

Authoritative sources
---------------------
* 《MIDAS NX Open API 对接规范 v1.0》(下称 **对接规范**)
  §3.2.1 三种响应形态 / §3.5 危险语义 15 条 / §7.4 2xx 错误体 /
  §11.5.3 ``Key Already Exist`` / §11.5.8 模型校验 / §11.5.9 错误信息本地化 /
  §11.5.10 ``Unknown Error``
* 《StructAI MCP V2.1 设计框架规范》(下称 **V2.1**)
  §17.3 请求包装与响应解包 / §20.1 归一化原则 / §20.3 归一化实现要求 /
  §20.4 2xx 错误体识别 / §20.4.1 错误信息本地化且可能被截断
* 错误码封闭集合：**总纲 §4.4** —— 本模块**不新增**任何错误码（总纲 §0.3 / 裁决 A-3）。

三层判据（V2.1 §20.4.1 的优先级表）
-----------------------------------
======  ==========================================  ==========================
优先级   判据                                        语言无关性
======  ==========================================  ==========================
1（主）  结构化信号：``error`` 键 / HTTP 状态码        与语言无关，最可靠
2        ``message`` 是否为空                        区分「成功无数据」与「失败」
3（兜底） ``message`` 文本模式（**中英双语**）        仅作粗归类
======  ==========================================  ==========================

.. warning::
   **文本匹配只是兜底，绝不能作为唯一的成功/失败判据**（V2.1 §20.4 末段）。
   本模块的 :func:`normalize_upstream` 只在第 1、2 层都没有给出信号时
   （例如上游回了裸字符串而非 JSON 对象）才使用文本模式；文本模式**只用于判定失败**，
   从不用于宣告成功——「成功」永远来自「没有结构化失败信号」。
"""

import json
from dataclasses import dataclass
from typing import Any, Final

from app.core.errors import ErrorCode, http_status_for, normalize_legacy_code

__all__ = [
    "AdapterError",
    "ErrorTextMarker",
    "UpstreamVerdict",
    "ERROR_TEXT_MARKERS",
    "AMBIGUOUS_SUCCESS_MARKERS",
    "is_error_body",
    "normalize_upstream",
    "text_of",
]


# ---------------------------------------------------------------------------
# AdapterError — 适配层统一异常
# ---------------------------------------------------------------------------
class AdapterError(Exception):
    """Every failure the adapter layer raises, carrying a 总纲 §4.4 ``code``.

    ``code`` is the **string value** of an :class:`app.core.errors.ErrorCode`
    member (e.g. ``"MIDAS_API_ERROR"``).  ``ErrorCode`` is a ``str``-Enum, so
    ``err.code == ErrorCode.MIDAS_API_ERROR`` is also true; the canonical enum
    member stays available as :attr:`error_code` for ``http_status`` lookups.

    ``raw_status`` / ``raw_response`` mirror V2.1 §19: they exist for logs and
    troubleshooting only and must never be handed to the LLM.
    """

    def __init__(
        self,
        code: ErrorCode | str,
        message: str = "",
        details: dict[str, Any] | None = None,
        raw_status: int | None = None,
        raw_response: Any = None,
    ) -> None:
        resolved: ErrorCode = (
            code if isinstance(code, ErrorCode) else normalize_legacy_code(str(code))
        )
        #: Canonical 总纲 §4.4 member (never a locally invented code).
        self.error_code: ErrorCode = resolved
        #: ``str`` form of the registry code, for ``AdapterResult.error_code``.
        self.code: str = resolved.value
        self.message: str = message or resolved.value
        self.details: dict[str, Any] = dict(details or {})
        self.raw_status: int | None = raw_status
        self.raw_response: Any = raw_response
        super().__init__(self.message)

    @property
    def http_status(self) -> int:
        """HTTP status declared for this code in 总纲 §4.4."""
        return http_status_for(self.code)

    def to_dict(self) -> dict[str, Any]:
        """§4.3.1 failure payload fragment (envelope fields excluded)."""
        return {
            "success": False,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }

    @classmethod
    def from_verdict(cls, verdict: "UpstreamVerdict", *, context: str = "") -> "AdapterError":
        """Build an error from a failed :class:`UpstreamVerdict`."""
        message = verdict.error_message or "upstream reported a failure"
        if context:
            message = f"{context}: {message}"
        return cls(
            verdict.error_code or ErrorCode.MIDAS_API_ERROR.value,
            message,
            details={"layer": verdict.layer, "matched_marker": verdict.matched_marker},
            raw_status=verdict.raw_status,
            raw_response=verdict.raw_response,
        )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"AdapterError(code={self.code!r}, message={self.message!r})"


# ---------------------------------------------------------------------------
# 文本兜底标记表（第 3 层）—— 中英双语（对接规范 §11.5.9）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ErrorTextMarker:
    """One bilingual failure phrase and the 总纲 §4.4 code it normalizes to."""

    marker: str
    error_code: ErrorCode
    source: str


#: Ordered, most specific first.  Matching is case-insensitive and applied to a
#: normalized copy of the text (see :func:`_normalise_text`).
#:
#: **These markers are a fallback only** (V2.1 §20.4): they classify a failure
#: that layers 1–2 already reported, or catch a bare-string body that carries no
#: structured signal at all.  They never declare success.
ERROR_TEXT_MARKERS: Final[tuple[ErrorTextMarker, ...]] = (
    # --- 认证（对接规范 §2.3：401 Key 错误/缺失，403 权限不足） --------------
    ErrorTextMarker("invalid key", ErrorCode.MIDAS_AUTH_FAILED, "对接规范 §2.3"),
    ErrorTextMarker("key is not valid", ErrorCode.MIDAS_AUTH_FAILED, "对接规范 §2.3"),
    ErrorTextMarker("key not valid", ErrorCode.MIDAS_AUTH_FAILED, "对接规范 §2.3"),
    ErrorTextMarker("unauthorized", ErrorCode.MIDAS_AUTH_FAILED, "对接规范 §2.3"),
    ErrorTextMarker("authentication failed", ErrorCode.MIDAS_AUTH_FAILED, "对接规范 §2.3"),
    ErrorTextMarker("密钥无效", ErrorCode.MIDAS_AUTH_FAILED, "对接规范 §11.5.9"),
    ErrorTextMarker("认证失败", ErrorCode.MIDAS_AUTH_FAILED, "对接规范 §11.5.9"),
    # --- 写冲突（对接规范 §11.5.3：POST 是「仅创建」） ----------------------
    ErrorTextMarker("key already exist", ErrorCode.RESOURCE_CONFLICT, "对接规范 §11.5.3"),
    # --- 字段/值错误（对接规范 §3.5 第 10 条：通常意味着「值错」） ----------
    ErrorTextMarker("wrong field", ErrorCode.VALIDATION_ERROR, "对接规范 §3.5 第 10 条"),
    # --- 路径与文件（对接规范 §3.5 第 6 条 / §11.5.2） ----------------------
    ErrorTextMarker("path is wrong", ErrorCode.MIDAS_API_ERROR, "对接规范 §11.5.2"),
    ErrorTextMarker("can't open", ErrorCode.MIDAS_API_ERROR, "对接规范 §11.5.2"),
    ErrorTextMarker("cannot open", ErrorCode.MIDAS_API_ERROR, "对接规范 §11.5.2"),
    # --- 分析（对接规范 §7.4 / §3.5 第 7 条 / §11.5.8） --------------------
    ErrorTextMarker("analysis is not allowed", ErrorCode.MIDAS_CALCULATION_ERROR, "对接规范 §7.4"),
    ErrorTextMarker("no analysis result", ErrorCode.MIDAS_CALCULATION_ERROR, "对接规范 §7.4"),
    ErrorTextMarker("analysis failed", ErrorCode.MIDAS_CALCULATION_ERROR, "对接规范 §3.5 第 7 条"),
    # --- 会话/模型状态（对接规范 §11.5.12：实例里没有打开任何项目） ----------
    #: 实测：``400 {"error":{"message":"The project is not opened"}}``。
    #: 客户端**是连着的**（HTTP 通、Key 有效），缺的是「模型」——总纲 §4.4.6 的
    #: ``MODEL_UNAVAILABLE``（503 模型不可用）正是这个语义。泛化的
    #: ``MIDAS_API_ERROR``（502 上游错误）虽然也不算错，但对调用方毫无可操作性：
    #: 前者告诉它「去打开或新建一个模型」，后者只告诉它「上游出错了」。
    ErrorTextMarker("project is not opened", ErrorCode.MODEL_UNAVAILABLE, "对接规范 §11.5.12"),
    ErrorTextMarker("no project", ErrorCode.MODEL_UNAVAILABLE, "对接规范 §11.5.12"),
    ErrorTextMarker("项目未打开", ErrorCode.MODEL_UNAVAILABLE, "对接规范 §11.5.12"),
    ErrorTextMarker("没有打开", ErrorCode.MODEL_UNAVAILABLE, "对接规范 §11.5.12"),
    # --- 中文错误体（对接规范 §11.5.8 / §11.5.9） -------------------------
    #: 实测：``400 {"error":{"message":"[错误] 边界条件 没有定义。"}}``
    #: 更具体的短语排在前面：同一条中文消息里 ``[错误]`` 与 ``没有定义`` 同时出现时，
    #: 取 ``没有定义``（模型校验失败）比取通用的 ``[错误]`` 更有信息量。
    ErrorTextMarker("没有定义", ErrorCode.VALIDATION_ERROR, "对接规范 §11.5.8"),
    ErrorTextMarker("无法", ErrorCode.MIDAS_API_ERROR, "对接规范 §11.5.9"),
    ErrorTextMarker("[错误]", ErrorCode.MIDAS_API_ERROR, "对接规范 §11.5.8"),
    # --- 服务端自截断的兜底错误（对接规范 §11.5.10） ----------------------
    ErrorTextMarker("unknown error", ErrorCode.MIDAS_API_ERROR, "对接规范 §11.5.10"),
)

#: 「看起来像成功」的文案 —— **歧义**，不得单独用于判定成功。
#:
#: 对接规范 §11.5.2 实机证明 ``/doc/EXPORT`` 成功写出文件时上游唯一的返回就是
#: ``{"message":"... command complete"}``；而 §3.5 第 7 条又证明 ``/doc/SAVEAS``
#: 对**根本没发生的保存**也返回同一句 ``... command complete``。
#: 因此默认策略（V2.1 §17.3 / §20.4 第 2 层）把「非空 message」判为失败，
#: 并把歧义事实写进 ``warnings``，由调用方决定是否读回复核。
AMBIGUOUS_SUCCESS_MARKERS: Final[tuple[str, ...]] = (
    "command complete",
    "命令完成",
    "명령 완료",
)

_AMBIGUITY_NOTE: Final[str] = (
    "上游只回了 '... command complete' 一类文案。对接规范 §3.5 第 7 条证明该文案"
    "对『根本没发生的保存』同样出现（/doc/SAVEAS），而 §11.5.2 又证明导出成功时"
    "它是唯一返回；因此它**不能**证明成功。必须读回模型状态或到 NX 主机上核对文件。"
)


def _normalise_text(text: str) -> str:
    """Lower-case and fold the two characters that silently break matching.

    * ``’`` (U+2019) is what a CMS usually emits for ``can't open``.
    * ``\\xa0`` (U+00A0, non-breaking space) is what the official articles use
      between tokens instead of a plain space.
    """
    return text.replace("\u2019", "'").replace("\u00a0", " ").lower()


def text_of(payload: Any) -> str:
    """Best-effort text rendering of any upstream payload (never raises)."""
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, (bytes, bytearray)):
        return bytes(payload).decode("utf-8", errors="replace")
    try:
        return json.dumps(payload, ensure_ascii=False, default=str)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return str(payload)


def _match_marker(text: str) -> ErrorTextMarker | None:
    """Return the first marker contained in ``text``, else ``None``."""
    if not text:
        return None
    haystack = _normalise_text(text)
    for marker in ERROR_TEXT_MARKERS:
        if marker.marker in haystack:
            return marker
    return None


def _is_ambiguous_success(text: str) -> bool:
    """True when the text is one of the known ambiguous success phrases."""
    if not text:
        return False
    haystack = _normalise_text(text)
    return any(marker in haystack for marker in AMBIGUOUS_SUCCESS_MARKERS)


def _extract_message(payload: Any) -> str:
    """Pull the human-readable message out of any of the three response shapes."""
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            inner = error.get("message") or error.get("Message")
            if isinstance(inner, str):
                return inner
            return text_of(error)
        if isinstance(error, str):
            return error
        message = payload.get("message")
        if isinstance(message, str):
            return message
        if message is not None:
            return text_of(message)
        return ""
    return text_of(payload)


def _classify(
    message: str,
    raw_status: int | None,
    *,
    not_found_code: str,
) -> tuple[str, str | None]:
    """Map a message + status onto a 总纲 §4.4 code (V2.1 §20.3).

    Returns ``(error_code, matched_marker)``.  Anything the table does not cover
    becomes ``MIDAS_API_ERROR`` (upstream failure) — **never** a new code
    (V2.1 §20.3 items 1–2).
    """
    # 上游认证/授权失败（V2.1 §20.3 item 4：MIDAS_AUTH_FAILED，不是 AUTH_INVALID）
    if raw_status in (401, 403):
        return ErrorCode.MIDAS_AUTH_FAILED.value, None
    marker = _match_marker(message)
    if marker is not None:
        return marker.error_code.value, marker.marker
    if raw_status == 404:
        return not_found_code, None
    if raw_status == 429:
        return ErrorCode.RATE_LIMITED.value, None
    if raw_status is not None and raw_status >= 500:
        return ErrorCode.MIDAS_API_ERROR.value, None
    return ErrorCode.MIDAS_API_ERROR.value, None


# ---------------------------------------------------------------------------
# 三层判据
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class UpstreamVerdict:
    """Outcome of the three-layer judgement for one upstream response."""

    #: ``True`` = the response carries no failure signal.
    ok: bool
    #: Which layer produced this verdict: ``http-status`` / ``structured`` /
    #: ``message`` / ``text-pattern`` / ``root-key`` / ``no-root-key``.
    layer: str
    #: 总纲 §4.4 code (string value) when ``ok`` is ``False``.
    error_code: str | None = None
    error_message: str | None = None
    #: The bilingual fallback phrase that matched, if any (对接规范 §11.5.9).
    matched_marker: str | None = None
    #: Extracted inner payload when ``ok`` is ``True`` (§17.3 branch 3/4).
    data: Any = None
    #: Non-fatal notes the caller must surface (V2.1 §19 ``warnings``).
    warnings: tuple[str, ...] = ()
    #: ``True`` when success could not be *proven* (only the ambiguous
    #: ``command complete`` family was seen).
    unverified: bool = False
    raw_status: int | None = None
    raw_response: Any = None

    def __bool__(self) -> bool:
        return self.ok

    def as_error(self, *, context: str = "") -> "AdapterError":
        """Convert a failed verdict into an :class:`AdapterError`."""
        return AdapterError.from_verdict(self, context=context)


def normalize_upstream(
    *,
    payload: Any,
    raw_status: int | None = None,
    root_key: str | None = None,
    context: str = "",
    not_found_code: str = ErrorCode.INTERFACE_NOT_FOUND.value,
    allow_ambiguous_message_success: bool = False,
) -> UpstreamVerdict:
    """Judge one upstream response with the three layers of V2.1 §20.4.1.

    :param payload: the decoded body, exactly as the upstream returned it.
    :param raw_status: HTTP status.  ``200`` **and** ``201`` may both carry an
        error body (对接规范 §3.5 第 2 条 / V2.1 §20.4), so the body decides.
    :param root_key: ``tool_interfaces.response_root_key``; when present and
        found, its value is returned as :attr:`UpstreamVerdict.data`
        (§17.3 branch 3).
    :param not_found_code: code used for HTTP 404.  Defaults to
        ``INTERFACE_NOT_FOUND`` (Base URL 错, 对接规范 §2.3); the adapter passes
        ``RESOURCE_NOT_FOUND`` for id-addressed ``/{id}`` calls.
    :param allow_ambiguous_message_success: opt-in escape hatch for the
        ``command complete`` family.  **Default ``False``** — i.e. a non-blank
        ``message`` is a failure, verbatim per V2.1 §17.3 / §20.4 layer 2.
        ``/doc/*`` writers may opt in, because 对接规范 §11.5.2 proves that a
        *successful* export returns nothing else; the verdict then carries
        ``unverified=True`` plus a warning so nobody treats it as proof.

    Layer order (never reordered):

    1. HTTP status ``>= 400`` → failure (language independent).
    2. ``error`` key present (at **any** status, including 200/201) → failure.
    3. ``message`` key present → blank means **success with no data**
       (``{"message": ""}`` is an empty table, 对接规范 §3.2.1); non-blank means
       failure, with the code taken from the bilingual marker table.
    4. no structured signal at all **and** the body is a bare string → bilingual
       text fallback, used only to detect *failure*.
    5. ``root_key`` found → that inner object (对接规范 §3.2).
    6. otherwise the response itself (§17.3 branch 4).
    """
    warnings: list[str] = []

    # --- 第 1 层：HTTP 状态（与语言无关） ---------------------------------
    if raw_status is not None and raw_status >= 400:
        message = _extract_message(payload) or f"HTTP {raw_status}"
        code, marker = _classify(message, raw_status, not_found_code=not_found_code)
        if context:
            message = f"{context}: {message}"
        return UpstreamVerdict(
            ok=False,
            layer="http-status",
            error_code=code,
            error_message=message,
            matched_marker=marker,
            warnings=tuple(warnings),
            raw_status=raw_status,
            raw_response=payload,
        )

    # --- 第 2 层之一：结构化失败信号（200 / 201 都可能是错误体） -----------
    if isinstance(payload, dict) and "error" in payload:
        message = _extract_message(payload) or "upstream returned an error body"
        code, marker = _classify(message, raw_status, not_found_code=not_found_code)
        if context:
            message = f"{context}: {message}"
        return UpstreamVerdict(
            ok=False,
            layer="structured",
            error_code=code,
            error_message=message,
            matched_marker=marker,
            raw_status=raw_status,
            raw_response=payload,
        )

    # --- 第 2 层之二：message 是否为空 ------------------------------------
    if isinstance(payload, dict) and "message" in payload:
        raw_message = payload["message"]
        message = raw_message if isinstance(raw_message, str) else text_of(raw_message)
        if message.strip() == "":
            # {"message": ""} = 成功且无数据（对接规范 §3.2.1）
            return UpstreamVerdict(
                ok=True,
                layer="message",
                data={},
                warnings=tuple(warnings),
                raw_status=raw_status,
                raw_response=payload,
            )
        code, marker = _classify(message, raw_status, not_found_code=not_found_code)
        ambiguous = _is_ambiguous_success(message)
        if ambiguous:
            warnings.append(_AMBIGUITY_NOTE)
        text = f"{context}: {message}" if context else message
        if ambiguous and allow_ambiguous_message_success:
            return UpstreamVerdict(
                ok=True,
                layer="message-ambiguous-success",
                data=None,
                matched_marker=marker,
                warnings=tuple(warnings),
                unverified=True,
                raw_status=raw_status,
                raw_response=payload,
            )
        return UpstreamVerdict(
            ok=False,
            layer="message",
            error_code=code,
            error_message=text,
            matched_marker=marker,
            warnings=tuple(warnings),
            raw_status=raw_status,
            raw_response=payload,
        )

    # --- 第 3 层（兜底）：无任何结构化信号时的双语文本模式 -----------------
    if not isinstance(payload, dict):
        text = text_of(payload)
        marker = _match_marker(text)
        if marker is not None:
            message = f"{context}: {text}" if context else text
            return UpstreamVerdict(
                ok=False,
                layer="text-pattern",
                error_code=marker.error_code.value,
                error_message=message,
                matched_marker=marker.marker,
                raw_status=raw_status,
                raw_response=payload,
            )
        warnings.append(
            "上游返回的不是 JSON 对象（而是文本/数组），只能按「无结构化失败信号」"
            "判定；文本兜底匹配不得作为唯一判据（V2.1 §20.4）。"
        )

    # --- 第 4 层：按 response_root_key 取内层数据 -------------------------
    #     大小写不敏感。MIDAS 路径大小写不敏感（实机验证），但响应根键**始终是
    #     规范的大写资源名**；而 tool_interfaces.endpoint 可能是任意大小写，
    #     精确匹配会失配并错误地落到第 5 层（把整个响应当成数据）。
    if root_key and isinstance(payload, dict):
        if root_key in payload:
            inner = payload[root_key]
            matched = True
        else:
            wanted = root_key.strip().lower()
            hits = [
                value
                for key, value in payload.items()
                if isinstance(key, str) and key.strip().lower() == wanted
            ]
            matched = len(hits) == 1
            inner = hits[0] if matched else None
        if matched:
            return UpstreamVerdict(
                ok=True,
                layer="root-key",
                data=inner,
                warnings=tuple(warnings),
                raw_status=raw_status,
                raw_response=payload,
            )

    # --- 第 5 层：无根键端点，原样返回（§17.3 分支 4） --------------------
    return UpstreamVerdict(
        ok=True,
        layer="no-root-key",
        data=payload,
        warnings=tuple(warnings),
        raw_status=raw_status,
        raw_response=payload,
    )


def is_error_body(payload: Any, raw_status: int | None = None) -> bool:
    """V2.1 §7.4 / §20.4 ``is_error_body()``.

    Checks the **body** as well as the status, so ``200``/``201`` error bodies
    are caught (对接规范 §3.5 第 2 条).  ``{"message": ""}`` is *not* an error:
    it is a successful empty table (对接规范 §3.2.1).
    """
    return not normalize_upstream(payload=payload, raw_status=raw_status).ok
