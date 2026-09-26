"""MIDAS Gen / Civil NX adapter — the real adapter.

Every guard in this file traces back to a **live-verified** rule.  The rule
index below is the map; each implementation site cites its section inline.

对接规范 = 《MIDAS NX Open API 对接规范 v1.0》
V2.1     = 《StructAI MCP V2.1 设计框架规范》

===============================  ==============================================
规则                              实现位置
===============================  ==============================================
§2.1 本地/中继两种接入、MAPI-Key    ``__init__`` / ``_headers``
§2.2 ``/mapikey/verify`` 在主机根   :meth:`MidasNxAdapter.health_check`
§2.5.2 模态对话框阻塞整条通道       :meth:`MidasNxAdapter.probe_alive` /
                                   :meth:`MidasNxAdapter.check_channel` /
                                   ``_lock``（按客户端串行）
§2.5.2 超时**阶段**判据             :func:`_transport_error` +
                                   ``details["phase"]`` /
                                   :meth:`MidasNxAdapter.diagnose_session`
§11.5.13 会话冻结只能人工恢复        :meth:`MidasNxAdapter.diagnose_session` /
                                   :meth:`MidasNxAdapter._connect_with_diagnosis`
§11.5.14 冻结与网络黑洞不可区分      ``SESSION_STATES["session_unresponsive"]``
                                   （只报观测、列候选，**不断言**原因）
§3.1 两种包装键                     :meth:`MidasNxAdapter.wrap`
§3.2.1 三种响应形态                 :meth:`MidasNxAdapter.unwrap` +
                                   ``errors.normalize_upstream``
§3.3 新文件限制（GET/PUT only）      ``NEW_FILE_GET_PUT_ONLY``
§3.4 ``/doc/EXPORT`` 必须裸字符串    :meth:`MidasNxAdapter.doc_export`
§3.5 第 1 条 DELETE 清表            :meth:`MidasNxAdapter.delete` /
                                   :meth:`MidasNxAdapter.delete_all` /
                                   :meth:`MidasNxAdapter.delete_using_assign_body`
§3.5 第 2 条 200/201 错误体         ``errors.normalize_upstream``
§3.5 第 3 条 ``/db/NMAS`` 崩溃      ``BACKFILL_FIELDS``
§3.5 第 4 条 ``/doc/NEW`` 丢弃工作   :meth:`MidasNxAdapter.doc_new`
§3.5 第 5 条 超时 ≠ 回滚            ``_request(retry_safe=...)``
§3.5 第 6 条 路径在 NX 主机解析      :meth:`MidasNxAdapter.verify_connection`
§3.5 第 7 条 失败不一定带 error      ``errors.ERROR_TEXT_MARKERS``
§3.5 第 8 条 ``/post/TABLE`` 根键    :meth:`MidasNxAdapter.get_table`
§3.5 第 9 条 手册字段名可能错        :meth:`MidasNxAdapter.introspect`
§3.5 第 10 条 ``Wrong Field``        ``errors.ERROR_TEXT_MARKERS``
§3.5 第 11 条 ``/doc/NEW`` 前置条件   :meth:`MidasNxAdapter.doc_new`
§3.5 第 12 条 ``/db/PRES`` DIRECTION ``MANDATORY_WRITE_FIELDS``
§3.5 第 13 条 受保护路径            ``PROTECTED_PATH_PREFIXES``
§3.5 第 14 条 Hyper-S ``-M1``       :func:`is_hyper_s_only`
§3.5 第 15 条 product_scope 不是门控  ``PRODUCT_SCOPE_IS_NOT_A_GATE``
§4.1 ``Assign`` 外层键语义随端点而异  :func:`outer_key_means` /
                                   :func:`build_assign`
§5.0.1 ``/info`` 包装键固定 Argument :meth:`MidasNxAdapter.introspect`
§5.1 ``/info`` 只覆盖 ``/db/*``      :meth:`MidasNxAdapter.introspect`
§11.5.1 DELETE 语义（实机）          :meth:`MidasNxAdapter.delete`
§11.5.3 ``POST`` 仅创建              :meth:`MidasNxAdapter.create_or_update`
§11.5.5 读回形态 ≠ 写入形态          :meth:`MidasNxAdapter._validate_after_write`
§11.5.6 ``/post/TABLE`` 行为         :meth:`MidasNxAdapter.get_table`
§11.5.7 ``/doc/ANAL`` 两种请求体      :meth:`MidasNxAdapter.doc_anal`
§11.5.9 错误信息本地化               ``errors.ERROR_TEXT_MARKERS``
§11.6 CNLD 外层键是节点号            :func:`build_assign`
§17.3 包装/解包                     :meth:`MidasNxAdapter.wrap` /
                                   :meth:`MidasNxAdapter.unwrap`
§17.5 端点语义陷阱 11 条             见上表逐条映射
§26.5 写操作禁止自动重试              ``_request(retry_safe=...)``
===============================  ==============================================

Deliberately **not** here: canonical ⇄ MIDAS *field* mapping.  §23 keeps the
engineering-semantic layer out of the adapter, and §22 puts the mapper in
``midas_gen/mapper.py``.  This module therefore consumes payloads whose field
names are already MIDAS field names.
"""

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Any, Final, NoReturn, Sequence

import httpx

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
from app.adapters.errors import AdapterError, normalize_upstream
from app.core.constants import AdapterStatus, TaskStatus
from app.core.errors import ErrorCode
from app.core.midas_config import MidasConnection, MidasProduct

__all__ = [
    "MidasNxAdapter",
    "MidasGenAdapter",
    "MidasCivilAdapter",
    "WRAPPER_ASSIGN",
    "WRAPPER_ARGUMENT",
    "TRANSPORT_PHASES",
    "TRANSPORT_PHASE_MEANING",
    "TRANSPORT_PHASE_REMEDY",
    "SESSION_STATE_BY_PHASE",
    "SESSION_STATES",
    "DOCUMENTED_OUTER_KEY_MEANS",
    "BACKFILL_FIELDS",
    "MANDATORY_WRITE_FIELDS",
    "HIGH_RISK_ENDPOINTS",
    "PROTECTED_PATH_PREFIXES",
    "NEW_FILE_GET_PUT_ONLY",
    "PRODUCT_SCOPE_IS_NOT_A_GATE",
    "CAPABILITIES",
    "normalise_endpoint",
    "resource_of",
    "outer_key_means",
    "validate_assign_outer_key",
    "build_assign",
    "build_assign_body",
    "coerce_assign_records",
    "wrap_payload",
    "unwrap_response",
    "apply_query",
    "find_table_shape",
    "require_table_components",
    "load_case_suffix_warnings",
    "apply_write_contract",
    "guard_local_path",
    "is_hyper_s_only",
]


# ---------------------------------------------------------------------------
# 包装键与端点族（对接规范 §3.1）
# ---------------------------------------------------------------------------
WRAPPER_ASSIGN: Final[str] = "Assign"
WRAPPER_ARGUMENT: Final[str] = "Argument"

_ENDPOINT_FAMILIES: Final[frozenset[str]] = frozenset(
    {"db", "doc", "ope", "view", "post", "info", "design"}
)

#: Sentinel: "send no request body at all".  Distinct from ``{}`` because
#: ``POST /doc/ANAL`` needs a **bare empty object** while ``/doc/SAVE`` needs
#: ``{"Argument": {}}`` and the docs disagree about which endpoints accept no
#: body (对接规范 §3.4 第一行：``/doc/new`` 传 ``{}``，官方示例中 ``/doc/save``
#: 不传 body).  The caller chooses explicitly; the adapter never guesses.
_OMIT_BODY: Final[object] = object()

#: Read attempts.  §26.5: a write timeout is **not** a rollback, so only
#: ``retry_safe=True`` (reads) may retry.
_READ_ATTEMPTS: Final[int] = 2
_RETRY_BACKOFF_SECONDS: Final[float] = 0.2


# ---------------------------------------------------------------------------
# 传输阶段与会话判定（对接规范 §2.5.2 / §11.5.13；总纲 §4.4 错误码封闭）
# ---------------------------------------------------------------------------
#: ``details["phase"]`` 的**封闭**取值 —— 一次超时/传输失败发生在**哪一段**。
#:
#: 对接规范 §11.5.13 事故记录：会话被 NX 主机上的模态对话框冻结时，
#: ``GET /gen/db/UNIT``、``GET /gen/ope/PROJECTSTATUS``、甚至**不碰文档**的
#: ``GET /mapikey/verify`` 全部超时（``curl 000``）。而「产品没运行」是连接被拒，
#: 「实例里没有打开项目」是 ``400 {"error":{"message":"The project is not opened"}}``
#: （§11.5.12）。三种处境从客户端看**都只是「超时」**，唯一能机械区分的判据是
#: **失败发生在哪一段**（连接从未建立 vs 连接已建立但没有响应），以及
#: ``/mapikey/verify`` 是否**也**失败。这个字段就是那个判据的载体。
#:
#: .. warning::
#:    ``phase="read"`` **不是**「会话被冻结」的证据，只是「请求已发出、没有响应」。
#:    对接规范 §11.5.14（实测）：黑洞目标 ``10.255.255.1`` 抛的同样是
#:    ``httpx.ReadTimeout``（5.19s）而**不是** ``ConnectTimeout``；RFC 5737 的
#:    ``192.0.2.1`` / ``198.51.100.1`` / ``203.0.113.1`` 保证不可路由，TCP 连接却
#:    在 0.00s 就被本机的代理/防火墙/安全产品「接受」了 —— 所以「TCP 连上了 ⇒
#:    对面在监听」在本环境**是假的**，原始 TCP 探测救不了这个区分。阶段只能把
#:    「连接从未建立」和「请求已发出、没有响应」分开；后者**有两种不可区分的来源**。
TRANSPORT_PHASES: Final[tuple[str, ...]] = ("connect", "read", "write", "pool", "unknown")

#: 阶段 -> 一行含义（写进异常消息，让「超时」不再是唯一信息）。
TRANSPORT_PHASE_MEANING: Final[dict[str, str]] = {
    "connect": "连接**从未建立**——请求没有到达服务",
    "read": (
        "连接**已建立**、请求**已发出**，但没有任何响应——模态对话框冻结会话与"
        "网络黑洞/拦截代理**都会**产生这个签名，从服务端**不可区分**（§11.5.14）"
    ),
    "write": "连接已建立，但请求体尚未写完就超时",
    "pool": "连接池里没有空闲连接，请求**从未被发出**",
    "unknown": "超时/传输失败的类型无法归类（兜底分支）",
}

#: 阶段 -> 处置建议。 ``read`` 那一条给出**判别步骤**，而不是断言原因
#: （对接规范 §11.5.14：观测不足以支撑结论时，报告观测并列出候选）。
TRANSPORT_PHASE_REMEDY: Final[dict[str, str]] = {
    "connect": (
        "对接规范 §2.3：连接从未建立，通常是**本地产品未运行**——请启动 MIDAS "
        "Gen/Civil NX；跨机调用还要检查云端中继与防火墙/SSL 拦截（§2.1 / §2.6）。"
        "**这不是会话级阻塞**：请求根本没有到达服务。"
    ),
    "read": (
        "对接规范 §11.5.14 / §11.5.13：连接已建立却没有响应，这个签名有**两个**"
        "已知来源，服务端无法区分：(1) NX 主机上有**模态对话框**冻结了整个会话"
        "（例如从未保存过的文档上 ``POST /doc/SAVE`` 弹出的「另存为」，§11.5.13）；"
        "(2) **网络路径不可达**——被黑洞或被代理/防火墙拦截（实测不可路由目标同样抛 "
        "``httpx.ReadTimeout`` 而不是 ``ConnectTimeout``，§11.5.14）。**重试无效**："
        "两种原因都不会因为重试而改变。判别顺序：先看 NX 主机上有没有对话框，"
        "再从**运行本服务的机器**上确认目标主机是否可达"
        "（``ping`` / ``Test-NetConnection`` / 检查代理）。"
    ),
    "write": (
        "连接已建立、请求体未发完；写操作仍可能在 MIDAS 侧部分落地，"
        "必须先读回模型状态再决定（V2.1 §26.5 / 对接规范 §3.5 第 5 条）。"
    ),
    "pool": (
        "请求从未被发出。对接规范 §2.5.2：同一实例并发恒为 1，连接池里只有一个连接，"
        "池超时说明上一个请求还挂在那里——先确认会话状态，再决定是否重试。"
    ),
    "unknown": (
        "无法归类的超时/传输失败：按 V2.1 §26.5 先读回模型状态，再由人工判定。"
    ),
}

#: 阶段 -> **未证实**的会话状态（用于失败的数据调用：信封里必须能机械取回状态）。
#: 证实要跑 :meth:`MidasNxAdapter.diagnose_session`（它同时探测 ``/mapikey/verify``
#: 与 ``/db/UNIT``）；失败的数据调用**不再补探测** —— 没有响应的会话不得被探测第二次
#: （对接规范 §11.5.13：无论它是被对话框冻结还是网络路径不通，再探一次都只是再赔
#: 一次超时）。
#:
#: ``read`` / ``write`` 都只能推出 :data:`SESSION_STATES` 里那个**未证实**的
#: ``session_unresponsive``：两者都只证明「请求发出去了、没有响应」，而该签名在
#: §11.5.14 下有两种不可区分的来源。它**不再**被命名成 ``session_frozen``——
#: 那等于把观测（无响应）冒充成原因（对话框），会在网络不通时给出错误的处置。
SESSION_STATE_BY_PHASE: Final[dict[str, str]] = {
    "connect": "service_down",
    "read": "session_unresponsive",
    "write": "session_unresponsive",
    "pool": "degraded",
    "unknown": "degraded",
}

#: 会话状态**封闭**集合 + 每个状态的判据/处置（对接规范 §11.5.13 判据表 /
#: §11.5.14 可证明与不可证明的分界）。
#:
#: 每个状态额外声明两件事，好让调用方**不必读散文**就能判断这个判定有多硬：
#:
#: * ``confirmed`` —— 观测是否**正面证明**了这个状态。``True`` 只给那些有正面证据的
#:   行（收到应答、收到 400/401、连接阶段被拒、verify 成功而 unit 读超时）；
#:   ``session_unresponsive`` 与 ``degraded`` 是 ``False``，因为它们的观测不足以
#:   把候选原因区分开（§11.5.14）。
#: * ``candidates`` / ``candidate_evidence`` —— 产生同一签名的候选**原因**，以及每个
#:   候选的证据（§11.5.14：报告观测、列出候选，**不断言**原因）。候选名不是状态：
#:   ``network_unreachable`` 永远不进 :data:`SESSION_STATES`，因为它不是一种能被观测
#:   区分出来的**会话状态**，而是同一种观测的一个**原因**。
#:
#: ``error_code`` 一律取自总纲 §4.4 的既有成员，**不新增错误码**：
#: ``MODEL_UNAVAILABLE``（§4.4.6，无项目）、``TASK_TIMEOUT``（真超时）、
#: ``MIDAS_CONNECTION_FAILED``（没连上）、``MIDAS_AUTH_FAILED``（Key 错）、
#: ``MIDAS_API_ERROR``（上游其它错误，兜底）。
SESSION_STATES: Final[dict[str, dict[str, Any]]] = {
    "healthy": {
        "diagnosis": "会话可用：/mapikey/verify 与 /db/UNIT 都正常应答。",
        "remedy": "无需处置。",
        "error_code": None,
        # 两条探针都**收到应答**（200）—— 正面证据，不是「没有失败」。
        "confirmed": True,
        "candidates": (),
        "candidate_evidence": {},
        "requires_human": False,
        "retry_helps": True,
        "recoverable_via_api": True,
    },
    "no_project": {
        "diagnosis": (
            "实例里**没有打开任何项目**：/mapikey/verify（不碰文档）正常，"
            "但 /db/UNIT 回 400 \"The project is not opened\"（对接规范 §11.5.12）。"
            "它不是连接问题——HTTP 通了、MAPI-Key 有效，缺的是**模型**。"
        ),
        "remedy": (
            "**可在 API 内恢复**：调用 ``POST /doc/NEW {}``（MCP: "
            "midas_execute action=new, data.confirm=true）新建空项目，然后重试原调用。"
            "对接规范 §11.5.12 实机验证：无项目时 /doc/NEW **立即返回**、不会阻塞会话；"
            "但它会丢弃未保存的工作（§3.5 第 4 条），因此只对「没有未保存改动」的场景使用。"
        ),
        "error_code": ErrorCode.MODEL_UNAVAILABLE.value,
        # 上游**回了** 400 且带明确文案：会话在应答，缺的只是项目 —— 已证实。
        "confirmed": True,
        "candidates": (),
        "candidate_evidence": {},
        "requires_human": False,
        "retry_helps": False,
        "recoverable_via_api": True,
    },
    "document_frozen": {
        "diagnosis": (
            "文档级阻塞：/mapikey/verify（不碰文档）正常，但 /db/UNIT **读超时** —— "
            "连接已建立、请求已发出，没有任何响应；阻塞发生在文档那一层"
            "（对接规范 §11.5.13 推论）。"
        ),
        "remedy": (
            "需要人工在运行 MIDAS Gen/Civil NX 的那台机器上关闭文档上的模态对话框"
            "（§2.5.2 / §3.5 第 13 条：受保护路径上的文档连 GET 都会弹窗阻塞）。"
            "**重试无效**：服务端没有在处理请求。"
        ),
        "error_code": ErrorCode.TASK_TIMEOUT.value,
        # 这一个**保持已证实**：``/mapikey/verify`` **成功**是「会话正在应答」的正面
        # 证据（§11.5.14 的判别表：verify 正常即排除整条通道不通），因此同一次探测里
        # 只有 /db/UNIT 读超时，阻塞必定在**文档**那一层 —— 文档层不是网络层，
        # 网络黑洞不会只吞掉 /db/UNIT 而放过 /mapikey/verify。
        "confirmed": True,
        "candidates": (),
        "candidate_evidence": {},
        "requires_human": True,
        "retry_helps": False,
        "recoverable_via_api": False,
    },
    "session_unresponsive": {
        "diagnosis": (
            "**会话无响应**（§11.5.14）：``/mapikey/verify``（不碰文档）与 "
            "``/db/UNIT``（碰文档）**同时读超时** —— 连接已建立、请求已发出，"
            "但整条 API 会话没有任何响应。这不是「没开项目」（那会回 400），"
            "也不是「产品没运行」（那会在连接阶段就被拒）。但**它也不等于「会话被"
            "冻结」**：实测黑洞目标抛的同样是 ``httpx.ReadTimeout``，与模态对话框冻结"
            "的签名**逐字段相同**，服务端无法区分，因此这里只报告观测到的事实"
            "（无响应）并列出候选原因，**不断言**是哪一种。"
        ),
        "remedy": (
            "**两步判别，按顺序做**：(1) 到运行 MIDAS Gen/Civil NX 的**那台机器**上"
            "看有没有模态对话框开着（例如从未保存过的文档上 ``POST /doc/SAVE`` 弹出的"
            "「另存为」，§11.5.13）——有就关掉它；(2) 若没有对话框，从**运行本服务的"
            "机器**上确认目标主机是否真的可达（``ping`` / "
            "``Test-NetConnection <host> -Port <port>`` / 检查代理、防火墙与 SSL 拦截，"
            "§2.1 / §2.6）——网络路径死了的话，MIDAS 侧做什么都无关。"
            "**重试不可能有帮助**：两种候选都不会因为重试而改变（服务端要么没有在处理"
            "请求，要么请求根本没有到达），``/doc/NEW`` 一类的补救调用同样进不去。"
            "恢复后请用 /doc/SAVEAS 带显式路径替代 /doc/SAVE。"
        ),
        "error_code": ErrorCode.TASK_TIMEOUT.value,
        # **未证实**（§11.5.14）：两条探针都读超时只证明「请求已发出、没有响应」。
        # 模态对话框冻结与网络黑洞/拦截代理产生**完全相同**的观测，从服务端不可区分，
        # 所以这里**不能**说 confirmed=True —— 那正是把观测冒充成原因、
        # 在网络不通时给出「去 NX 主机上关对话框」这种错误处置的根源。
        "confirmed": False,
        "candidates": ("session_frozen", "network_unreachable"),
        "candidate_evidence": {
            "session_frozen": (
                "NX 主机上的模态对话框阻塞**整条** API 会话：§11.5.13 事故实测 "
                "/db/UNIT、/ope/PROJECTSTATUS 与不碰文档的 /mapikey/verify 全部 "
                "curl 000；对话框不关，服务端就不处理任何请求。"
            ),
            "network_unreachable": (
                "网络路径被黑洞，或被代理/防火墙/安全产品拦截：§11.5.14 实测 "
                "10.255.255.1 同样抛 ``httpx.ReadTimeout``（5.19s，而不是 "
                "``ConnectTimeout``），且 RFC 5737 的不可路由地址连 TCP 都会被本机"
                "中间层在 0.00s「接受」—— 原始 TCP 探测证明不了对面有东西在监听。"
            ),
        },
        # 两半都保留，因为它们对**两个候选同时成立**：都需要人工介入，
        # 也都不会因为重试而好转（§11.5.14）。
        "requires_human": True,
        "retry_helps": False,
        "recoverable_via_api": False,
    },
    "service_down": {
        "diagnosis": (
            "MIDAS 产品未运行 / 端口不可达：``/mapikey/verify`` 在**连接阶段**就失败"
            "（连接被拒或连接超时），请求从未到达服务。"
        ),
        "remedy": (
            "启动 MIDAS Gen/Civil NX（对接规范 §2.1：本地 3030 与云端中继两种接入"
            "都要求产品已打开）；跨机调用请检查中继、防火墙与 SSL 拦截（§2.1 / §2.6）。"
        ),
        "error_code": ErrorCode.MIDAS_CONNECTION_FAILED.value,
        # 连接阶段失败是**正面证据**：没有任何东西接受连接（§11.5.14 判别表第一行）。
        "confirmed": True,
        "candidates": (),
        "candidate_evidence": {},
        "requires_human": True,
        "retry_helps": False,
        "recoverable_via_api": False,
    },
    "auth_failed": {
        "diagnosis": (
            "认证失败：``/mapikey/verify`` 回了 401 —— MAPI-Key 缺失或错误"
            "（对接规范 §2.3）。"
        ),
        "remedy": (
            "修正 midas_clients 上的 MAPI-Key（认证头是 ``MAPI-Key``，绝不是 "
            "``Authorization: Bearer``，§2.1），然后重连。"
        ),
        "error_code": ErrorCode.MIDAS_AUTH_FAILED.value,
        # 上游**回了** 401：应答本身即证据。
        "confirmed": True,
        "candidates": (),
        "candidate_evidence": {},
        "requires_human": True,
        "retry_helps": False,
        "recoverable_via_api": False,
    },
    "degraded": {
        "diagnosis": (
            "状态不明（degraded）：两条探针的失败方式与 §11.5.13 判据表中的任何一行"
            "都不吻合（例如 /mapikey/verify 正常但 /db/UNIT 回了 5xx，或反过来）。"
        ),
        "remedy": (
            "人工排查：先看 ``probes`` 里两条探针各自的 http_status / latency_ms / "
            "phase，再对照对接规范 §2.5.2 / §11.5.12 / §11.5.13。"
            "**不要**盲目重试（V2.1 §26.5：超时 ≠ 回滚）。"
        ),
        "error_code": ErrorCode.MIDAS_API_ERROR.value,
        # 判据表覆盖不到的形态：观测本身就不足以支撑任何结论（§11.5.14 的一般教训）。
        "confirmed": False,
        "candidates": (),
        "candidate_evidence": {},
        "requires_human": False,
        "retry_helps": False,
        "recoverable_via_api": False,
    },
}


def _transport_error(
    code: ErrorCode,
    method: str,
    url: str,
    exc: Exception,
    *,
    phase: str,
    timeout_seconds: float | None = None,
) -> AdapterError:
    """Build the :class:`AdapterError` for one transport failure, tagged with ``phase``.

    对接规范 §2.5.2 / §11.5.13 / §11.5.14：``httpx.TimeoutException`` 是
    ``ConnectTimeout`` / ``ReadTimeout`` / ``WriteTimeout`` / ``PoolTimeout`` 的
    **共同父类**，所以一个 ``except TimeoutException`` 会把「连接从未建立」和
    「连接已建立但没有响应」压成同一个 ``TASK_TIMEOUT``。后者**不等于**「会话被
    冻结」：黑洞网络路径抛出的是同一个 ``httpx.ReadTimeout``（§11.5.14 实测），
    因此阶段只能给出「请求发出去了、没有响应」这个**观测**，判别步骤见
    :data:`TRANSPORT_PHASE_REMEDY`。这里给每一种都打上 ``details["phase"]``
    （取值见 :data:`TRANSPORT_PHASES`），错误码仍取自总纲 §4.4 的封闭集合，
    **不新增错误码**。

    :param code: ``TASK_TIMEOUT``（真的超时了）或 ``MIDAS_CONNECTION_FAILED``
        （传输层/连接层失败）。调用方决定，因为「阶段」与「错误码」是两个轴。
    """
    resolved = phase if phase in TRANSPORT_PHASES else "unknown"
    head = (
        f"{method} {url} 失败（阶段 {resolved}）：{TRANSPORT_PHASE_MEANING[resolved]}。"
        if timeout_seconds is None
        else f"{method} {url} 超时（{timeout_seconds:g}s，阶段 {resolved}）："
        f"{TRANSPORT_PHASE_MEANING[resolved]}。"
    )
    policy = (
        "超时 ≠ 回滚——写操作可能在 HTTP 放弃后仍然在 MIDAS 侧落地，因此写操作禁止"
        "自动重试（V2.1 §26.5 / 对接规范 §3.5 第 5 条）；超时后必须先读回模型状态。"
        if code == ErrorCode.TASK_TIMEOUT
        else ""
    )
    return AdapterError(
        code,
        f"{head}{TRANSPORT_PHASE_REMEDY[resolved]}{policy}（{exc!r}）",
        details={
            "phase": resolved,
            "method": method,
            "url": url,
            "timeout_seconds": timeout_seconds,
            "exception": type(exc).__name__,
        },
    )


# ---------------------------------------------------------------------------
# 端点级契约（对接规范 §3.5）
# ---------------------------------------------------------------------------
#: 对接规范 §3.5 第 3 条 / §17.5 第 2 条 —— 省略这些字段会让 MIDAS NX **崩溃**
#: （实测：``POST /db/NMAS`` 缺 ``rmX``/``rmY``/``rmZ`` 时服务端崩溃；显式传
#: 哪怕 ``0.0`` 则正常）。 适配器在写之前**强制补全**，不依赖调用方。
BACKFILL_FIELDS: Final[dict[str, dict[str, Any]]] = {
    "NMAS": {"rmX": 0.0, "rmY": 0.0, "rmZ": 0.0},
}

#: 对接规范 §3.5 第 12 条 —— ``/db/PRES`` 的 ``DIRECTION`` 手册标为可选、
#: 默认 ``"NORMAL"``，但同文脚注矩阵显示 ``PLATE``+``FACE`` 下 ``NORMAL`` 不可用：
#: **省略该字段正是错误默认值被套用的方式**。 压力作用方向是工程决策，
#: 适配器**不代为选择**，只强制要求调用方显式提供。
MANDATORY_WRITE_FIELDS: Final[dict[str, tuple[str, ...]]] = {
    "PRES": ("DIRECTION",),
}

#: 对接规范 §3.3 —— 单位、结构类型等「新文件必需数据」只能用 ``GET`` / ``PUT``，
#: ``POST`` 不生效。 这是**端点级**属性；此处列出已确认的端点，其余端点由
#: ``tool_interfaces.metadata_json.new_file_get_put_only`` 提供（§7.1）。
NEW_FILE_GET_PUT_ONLY: Final[frozenset[str]] = frozenset(
    {"/db/UNIT", "/db/STYP", "/db/PJCF"}
)

#: 对接规范 §3.5 第 15 条 —— ``product_scope`` **不得**用作工程可行性门控。
PRODUCT_SCOPE_IS_NOT_A_GATE: Final[bool] = True

#: V2.1 §25.2 + 对接规范 §3.5 第 4 条：``/doc/NEW`` 丢弃未保存的工作
#: （包括与本次调用无关的文档），调用前必须先探测文档已打开。
HIGH_RISK_ENDPOINTS: Final[frozenset[str]] = frozenset({"/doc/NEW"})

#: 对接规范 §3.5 第 13 条 —— 打开的文档若位于标准账户不可写的路径，
#: **连 GET 也会弹「拒绝访问」并阻塞会话**，因此工作文档禁止放在受保护路径。
PROTECTED_PATH_PREFIXES: Final[tuple[str, ...]] = (
    "c:\\program files",
    "c:\\program files (x86)",
    "c:\\windows",
    "%programfiles%",
    "%systemroot%",
)

#: 对接规范 §3.5 第 14 条 —— Hyper-S 端点是 Civil NX 专属，在 Gen NX 下 404。
#: 标记名用 ``HYPER_S_ONLY`` 而非 ``CIVIL_ONLY``：Hyper-S 预期将来会到 Gen。
HYPER_S_SUFFIX: Final[str] = "-M1"


def is_hyper_s_only(resource: str) -> bool:
    """True for the Civil-only Hyper-S (``-M1``) endpoints (对接规范 §3.5 第 14 条)."""
    return resource_of(resource).endswith(HYPER_S_SUFFIX)


# ---------------------------------------------------------------------------
# §4.1 / §11.6 —— ``Assign`` 外层键的语义随端点而异
# ---------------------------------------------------------------------------
#: Only the endpoints whose outer-key meaning is **live-verified** are listed.
#: Everything else defaults to ``"self"`` (the endpoint's own entity number),
#: which is the §4.1 table's implicit default and is flagged as unverified —
#: it must be corrected from ``tool_interfaces.metadata_json.outer_key_means``
#: (对接规范 §4.1 / §7.1) before a new endpoint is written to.
DOCUMENTED_OUTER_KEY_MEANS: Final[dict[str, str]] = {
    "NODE": "node",
    "ELEM": "element",
    #: 🔴 The trap: ``/db/CNLD``'s outer key is the **node number**, while
    #: ``ITEMS[].ID`` is only a **serial number** (对接规范 §4.1 / §11.6).
    "CNLD": "node",
    "CONS": "group",
    "STLD": "load_case",
}

#: Kinds whose outer key must be a number.
_ENTITY_KEY_KINDS: Final[frozenset[str]] = frozenset(
    {"node", "element", "load_case", "group"}
)

OUTER_KEY_KINDS: Final[tuple[str, ...]] = ("node", "element", "load_case", "group", "self")


def normalise_endpoint(resource_or_endpoint: str) -> str:
    """Canonicalise ``NODE`` / ``db/NODE`` / ``/db/NODE`` to ``/db/NODE``.

    Endpoint families are kept as given (``/doc/ANAL``, ``/info/db/NODE``,
    ``/DESIGN/RC/...``); anything else is treated as a bare ``/db/*`` resource.
    """
    text = (resource_or_endpoint or "").strip()
    if not text:
        raise AdapterError(
            ErrorCode.VALIDATION_ERROR, "endpoint/resource 不能为空"
        )
    if not text.startswith("/"):
        text = "/" + text
    segments = text.split("/")
    head = segments[1].lower() if len(segments) > 1 else ""
    if head in _ENDPOINT_FAMILIES:
        return text
    # 对接规范 §3.6: the canonical form is **upper case** for the resource
    # segment (``/db/NODE``, not ``/db/node``).  MIDAS accepts either case —
    # verified live: /db/NODE, /db/node, /db/Node and /db/nOdE all answer 200
    # with identical bodies — but the response root key is *always* the
    # canonical upper-case resource name, so normalising here keeps the
    # registry, the request log and the root key consistent.
    return "/db/" + text.lstrip("/").upper()


def resource_of(resource_or_endpoint: str) -> str:
    """Upper-case MIDAS resource name of an endpoint (``/db/NODE/2`` -> ``NODE``)."""
    parts = [part for part in normalise_endpoint(resource_or_endpoint).split("/") if part]
    if len(parts) >= 2 and parts[0].lower() == "db":
        return parts[1].upper()
    return parts[-1].upper() if parts else ""


def _is_numeric_key(key: Any) -> bool:
    if isinstance(key, bool):
        return False
    if isinstance(key, int):
        return True
    if isinstance(key, str):
        return key.strip().isdigit()
    return False


def outer_key_means(resource: str) -> str:
    """Return ``node`` / ``element`` / ``load_case`` / ``group`` / ``self``.

    对接规范 §4.1 requires this to be **data**, not a comment.  Endpoints absent
    from :data:`DOCUMENTED_OUTER_KEY_MEANS` return ``"self"`` — the unverified
    default, to be corrected from ``tool_interfaces.metadata_json``.
    """
    return DOCUMENTED_OUTER_KEY_MEANS.get(resource_of(resource), "self")


def validate_assign_outer_key(
    resource: str, outer_key: Any, *, kind: str | None = None
) -> str:
    """Check that ``outer_key`` is of the entity kind this endpoint expects.

    Raises ``VALIDATION_ERROR`` when a numbered kind (``node`` / ``element`` /
    ``load_case`` / ``group``) is addressed with a non-numeric key.
    """
    resolved = kind or outer_key_means(resource)
    if resolved not in OUTER_KEY_KINDS:
        raise AdapterError(
            ErrorCode.VALIDATION_ERROR,
            f"未知的 outer_key_means={resolved!r}；合法取值：{', '.join(OUTER_KEY_KINDS)}"
            "（对接规范 §4.1 / §7.1 metadata_json.outer_key_means）",
        )
    if resolved in _ENTITY_KEY_KINDS and not _is_numeric_key(outer_key):
        raise AdapterError(
            ErrorCode.VALIDATION_ERROR,
            f"{normalise_endpoint(resource)} 的 Assign 外层键表示 {resolved} 号，"
            f"必须是数字，收到 {outer_key!r}（对接规范 §4.1）",
        )
    return resolved


def _validate_serial_items(
    resource: str, items: Sequence[Any], serial_field: str
) -> None:
    """Reject the ``/db/CNLD`` trap: a node number smuggled into ``ITEMS[].ID``.

    对接规范 §4.1 / §11.6: the outer key is the **node number** and
    ``ITEMS[].ID`` is only a **serial number** (手册参数表: ``Serial Number /
    Integer / 0 / Optional``).  Writing the node number into ``ID`` puts the load
    on the wrong node *silently* — the analysis still answers ``command
    complete``, reactions look right and every internal force / displacement is
    zero.  The adapter therefore refuses any ``ID`` that is neither the 1-based
    serial nor the documented default ``0``.
    """
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        value = item.get(serial_field, item.get(serial_field.lower()))
        if value is None:
            continue
        if isinstance(value, bool):
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR,
                f"{normalise_endpoint(resource)}: ITEMS[].{serial_field} 不能是布尔值",
            )
        if isinstance(value, str) and value.strip().isdigit():
            value = int(value.strip())
        if not isinstance(value, int):
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR,
                f"{normalise_endpoint(resource)}: ITEMS[].{serial_field} 必须是整数序号"
                f"（对接规范 §4.1：ID 是 Serial Number），收到 {value!r}",
            )
        if value == 0:  # 手册默认值：未指定序号
            continue
        if value != index + 1:
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR,
                f"疑似 CNLD 外层键误用：{normalise_endpoint(resource)} 的 Assign 外层键是"
                f"**节点号**，ITEMS[].{serial_field} 只是**序号**（对接规范 §4.1 / §11.6）。"
                f"第 {index + 1} 项的 {serial_field}={value}，既不是序号 {index + 1} 也不是默认值 0。"
                "这正是本项目踩过的坑：荷载静默加到错误节点（通常是固定端），"
                "分析仍返回 command complete，反力看似正确而内力/位移全零。"
                "正确写法：build_assign(<节点号>, {'ITEMS': [{'ID': 1, ...}]}, resource='CNLD')",
                details={
                    "endpoint": normalise_endpoint(resource),
                    "index": index,
                    "value": value,
                    "expected_serial": index + 1,
                },
            )


def build_assign(
    outer_key: Any,
    inner: Any,
    *,
    resource: str | None = None,
    kind: str | None = None,
    serial_field: str = "ID",
) -> dict[str, dict[str, Any]]:
    """Build ``{"Assign": {<outer_key>: <inner>}}`` **with the §4.1 guard**.

    ``outer_key`` is *not* always the endpoint's own entity number — for
    ``/db/CNLD`` it is the **node number** (对接规范 §4.1).  Pass ``resource``
    (preferred) so the semantic is looked up and validated instead of assumed.
    """
    key = str(outer_key)
    resolved_kind: str | None = None
    if resource is not None:
        resolved_kind = validate_assign_outer_key(resource, key, kind=kind)
    elif kind is not None:
        resolved_kind = validate_assign_outer_key("/db/UNKNOWN", key, kind=kind)
    if resolved_kind == "node" and isinstance(inner, dict):
        items = inner.get("ITEMS")
        if isinstance(items, list):
            _validate_serial_items(resource or "/db/CNLD", items, serial_field)
    return {WRAPPER_ASSIGN: {key: inner}}


def coerce_assign_records(resource: str, data: Any) -> dict[str, Any]:
    """Normalize an MCP ``data`` payload into an ``Assign`` inner mapping.

    Accepts (V2.1 §8.2 / §18.2):

    * ``{"1": {...}}`` — an already-MIDAS inner mapping;
    * ``{"id": 1, ...}`` — one record carrying its own key;
    * ``[{"id": 1, ...}, ...]`` — a list of such records.

    Field **names** are expected to be MIDAS names already; canonical ⇄ MIDAS
    field mapping belongs to ``midas_gen/mapper.py`` (V2.1 §22 / §23).
    """
    endpoint = normalise_endpoint(resource)
    if data is None:
        raise AdapterError(ErrorCode.VALIDATION_ERROR, f"{endpoint}: data 不能为空")
    if isinstance(data, dict):
        key = data.get("id", data.get("ID"))
        if key is not None:
            record = {k: v for k, v in data.items() if k not in ("id", "ID")}
            return {str(key): record}
        if data and all(isinstance(value, dict) for value in data.values()):
            return {str(k): v for k, v in data.items()}
        raise AdapterError(
            ErrorCode.VALIDATION_ERROR,
            f"{endpoint}: 无法确定 Assign 外层键（对接规范 §4.1：外层键语义随端点而异，"
            "不能假设统一）。请传 {'<外层键>': {...}}、或带 'id' 的记录、或记录数组；"
            "也可显式调用 build_assign()。",
            details={"endpoint": endpoint},
        )
    if isinstance(data, list):
        records: dict[str, Any] = {}
        for index, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                raise AdapterError(
                    ErrorCode.VALIDATION_ERROR,
                    f"{endpoint}: data[{index}] 必须是对象，收到 {type(item).__name__}",
                )
            key = item.get("id", item.get("ID"))
            if key is None:
                raise AdapterError(
                    ErrorCode.VALIDATION_ERROR,
                    f"{endpoint}: data[{index}] 缺少 'id'，无法生成 Assign 外层键"
                    "（对接规范 §4.1）",
                )
            records[str(key)] = {k: v for k, v in item.items() if k not in ("id", "ID")}
        if not records:
            raise AdapterError(ErrorCode.VALIDATION_ERROR, f"{endpoint}: data 为空数组")
        return records
    raise AdapterError(
        ErrorCode.VALIDATION_ERROR,
        f"{endpoint}: data 必须是对象或对象数组，收到 {type(data).__name__}",
    )


def build_assign_body(resource: str, records: dict[str, Any]) -> dict[str, Any]:
    """``{id: record}`` -> the full ``Assign`` inner mapping, guarded per record."""
    body: dict[str, Any] = {}
    for key, record in records.items():
        body.update(build_assign(key, record, resource=resource)[WRAPPER_ASSIGN])
    return body


# ---------------------------------------------------------------------------
# §3.5 第 8 条 —— ``/post/TABLE`` 按形状匹配
# ---------------------------------------------------------------------------
def _has_table_keys(node: Any) -> bool:
    return isinstance(node, dict) and {"HEAD", "DATA"} <= {str(k).upper() for k in node}


def find_table_shape(payload: Any, *, max_depth: int = 4) -> dict[str, Any] | None:
    """Find the dict carrying ``HEAD``/``DATA`` anywhere in the response.

    对接规范 §3.5 第 8 条: ``/post/TABLE`` 的顶层响应键**不稳定**——见过
    ``"Result Table"``、``"empty"``，也可能就是传入的 ``TABLE_NAME``；且
    **``"empty"`` 可以承载一张完整的表**。 因此禁止按键名取值，必须按形状匹配。
    """
    if _has_table_keys(payload):
        return payload
    queue: list[tuple[Any, int]] = [(payload, 0)]
    while queue:
        node, depth = queue.pop(0)
        if depth >= max_depth:
            continue
        children = node.values() if isinstance(node, dict) else node if isinstance(node, list) else ()
        for child in children:
            if _has_table_keys(child):
                return child
            if isinstance(child, (dict, list)):
                queue.append((child, depth + 1))
    return None


# ---------------------------------------------------------------------------
# §11.5.3 —— 「键不存在」判据（供 upsert 的 PUT→POST 回退使用）
# ---------------------------------------------------------------------------
_MISSING_MARKERS: Final[tuple[str, ...]] = (
    "not found",
    "does not exist",
    "doesn't exist",
    "not exist",
    "no such",
    "undefined key",
    "不存在",
    "未找到",
    "没有找到",
)

#: 工况名后缀规则（对接规范 §11.5.6 / 手册 19 章）：``LC1(ST)`` 命中，``LC1`` 返回空表。
_LOAD_CASE_SUFFIX_RE: Final[re.Pattern[str]] = re.compile(
    r"\((ST|CB|CS|RS|MV|SM)[^)]*\)$", re.IGNORECASE
)


def _is_missing_failure(result: AdapterResult) -> bool:
    """True when a failed result means「目标键不存在」rather than a real error."""
    if result.error_code == ErrorCode.RESOURCE_NOT_FOUND.value:
        return True
    text = (result.error_message or "").lower()
    return any(marker in text for marker in _MISSING_MARKERS)


# ---------------------------------------------------------------------------
# §11.5.6 / §3.5 第 6/13 条 —— 真实适配器与 mock 适配器共用的守卫
# ---------------------------------------------------------------------------
def require_table_components(
    table_type: str,
    components: Sequence[str] | None,
    table_name: str | None = None,
) -> str:
    """Enforce the two mandatory ``/post/TABLE`` arguments; return ``TABLE_NAME``.

    Shared by the real adapter and the mock so that the offline test suite
    exercises the *same* guard the live path uses.

    * ``TABLE_TYPE`` is Required by the manual (错误取值返回 400 + 被服务端截断的
      错误信息，对接规范 §11.5.6).
    * ``COMPONENTS`` 是必需的：省略时上游返回 ``200 {"message":""}``，看起来像
      「无结果」，实则请求不完整（对接规范 §11.5.6 / V2.1 §17.5 第 11 条）。
    """
    if not table_type:
        raise AdapterError(
            ErrorCode.VALIDATION_ERROR,
            "TABLE_TYPE 是必需的（手册 18/19 章参数表：Required）；"
            "错误取值返回 400 + 错误体，且服务端会自行截断错误信息（对接规范 §11.5.6）。",
        )
    if not components:
        raise AdapterError(
            ErrorCode.VALIDATION_ERROR,
            "COMPONENTS 是必需的：对接规范 §11.5.6 实测——省略时上游返回 "
            "200 {\"message\":\"\"}，看起来像「无结果」，实则请求不完整。"
            "（V2.1 §17.5 第 11 条：/post/* 的 Interface 必须携带默认 COMPONENTS "
            "模板，并把「合法空结果」与「请求缺参数」区分开。）",
            details={"table_type": table_type},
        )
    return table_name or table_type


def load_case_suffix_warnings(load_case_names: Sequence[str] | None) -> list[str]:
    """Warn about load-case names missing their type suffix.

    对接规范 §11.5.6: 结果表里工况名带 ``(ST)`` 后缀 —— ``["LC1(ST)"]`` 命中，
    ``["LC1"]`` 返回**空表**。 后缀规则见手册 19 章：``NAME(ST)`` / ``(CB)`` /
    ``(CS)`` / ``(RS)`` / ``(MV:max)`` / ``(SM:max)``。 缺少后缀不会报错，只会
    静默返回空表，因此必须在发请求前提示。
    """
    if not load_case_names:
        return []
    bad = [name for name in load_case_names if not _LOAD_CASE_SUFFIX_RE.search(name)]
    if not bad:
        return []
    return [
        f"工况名 {bad} 缺少类型后缀：对接规范 §11.5.6 —— 结果表里工况名带 '(ST)' 等后缀，"
        "['LC1(ST)'] 命中而 ['LC1'] 返回空表。后缀规则见手册 19 章："
        "NAME(ST)/(CB)/(CS)/(RS)/(MV:max)/(SM:max)。"
    ]


def apply_write_contract(
    endpoint: str, records: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Backfill mandatory defaults and enforce mandatory explicit fields.

    * 对接规范 §3.5 第 3 条: ``/db/NMAS`` 省略 ``rmX``/``rmY``/``rmZ`` 会让
      MIDAS NX **崩溃** -> 适配器强制补全（哪怕 ``0.0``）。
    * 对接规范 §3.5 第 12 条: ``/db/PRES`` 的 ``DIRECTION`` 省略即套用错误
      默认值 -> 适配器**不代为选择**，要求调用方显式提供。

    Module-level so the mock adapter enforces the same contract as the live one.
    """
    name = resource_of(endpoint)
    backfill = BACKFILL_FIELDS.get(name, {})
    mandatory = MANDATORY_WRITE_FIELDS.get(name, ())
    out: dict[str, Any] = {}
    warnings: list[str] = []
    for key, record in records.items():
        if not isinstance(record, dict):
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR,
                f"{endpoint}: 第 {key} 条记录必须是对象，收到 {type(record).__name__}",
            )
        resolved = dict(record)
        for field_name, default in backfill.items():
            if field_name not in resolved:
                resolved[field_name] = default
                warnings.append(
                    f"{endpoint}: 强制补全 {field_name}={default!r} —— 对接规范 §3.5 "
                    "第 3 条：省略 rmX/rmY/rmZ 时服务端会崩溃，显式传（哪怕 0.0）则正常。"
                )
        for field_name in mandatory:
            if field_name not in resolved:
                raise AdapterError(
                    ErrorCode.VALIDATION_ERROR,
                    f"{endpoint}: 必须显式提供 {field_name} —— 对接规范 §3.5 第 12 条："
                    "该字段手册标为可选、默认 'NORMAL'，但 PLATE+FACE 下 NORMAL 不可用，"
                    "**省略该字段正是错误默认值被套用的方式**。压力作用方向是工程决策，"
                    "适配器不代为选择。",
                    details={"endpoint": endpoint, "key": key, "field": field_name},
                )
        out[str(key)] = resolved
    return out, warnings


def guard_local_path(path: Any) -> str:
    """Validate a path that will be resolved **on the NX host**.

    对接规范 §3.5 第 6 条: 所有路径在 NX 所在机器上解析，常常不是跑服务的那台；
    路径不存在会在那边弹模态对话框并阻塞会话。 第 13 条: 工作文档禁止放在受保护
    路径，否则连 GET 都会弹「拒绝访问」并阻塞会话。
    """
    if not isinstance(path, str) or not path.strip():
        raise AdapterError(
            ErrorCode.VALIDATION_ERROR,
            "路径必须由调用方显式提供且非空：对接规范 §3.5 第 6 条禁止从 "
            "verify_connection()['user'] 推导路径（那是 MAPI 账号邮箱，"
            "不是 NX 主机的 Windows 账户）。",
        )
    normalised = path.strip().replace("/", "\\").lower()
    for prefix in PROTECTED_PATH_PREFIXES:
        if normalised.startswith(prefix):
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR,
                f"拒绝使用受保护路径 {path!r}：对接规范 §3.5 第 13 条 —— 文档位于 "
                "Program Files 之类标准账户不可写的路径时，**读取类命令也会弹"
                "「拒绝访问」并阻塞整个会话**。请改用工作目录。",
                details={"path": path, "prefix": prefix},
            )
    return path


# ---------------------------------------------------------------------------
# Capability 清单（§16.1 的权威行在数据库；此处只是镜像）
# ---------------------------------------------------------------------------
_RESOURCE_ACTIONS: Final[dict[str, tuple[str, ...]]] = {
    "node": ("create", "read", "update", "delete", "upsert"),
    "element": ("create", "read", "update", "delete", "upsert"),
    "material": ("create", "read", "update", "delete", "upsert"),
    "section": ("create", "read", "update", "delete", "upsert"),
    "load_case": ("create", "read", "update", "delete", "upsert"),
    "nodal_load": ("create", "read", "update", "delete"),
    "boundary": ("create", "read", "update", "delete"),
    "group": ("create", "read", "update", "delete"),
    "unit": ("read", "update"),
    "structure_type": ("read", "update"),
    "analysis": ("execute",),
    "result": ("read",),
    "document": ("create", "read", "execute"),
}

_ACTION_INTERFACE: Final[dict[str, str]] = {
    "create": "create",
    "read": "read",
    "update": "update",
    "delete": "delete",
    "upsert": "update",
    "execute": "execute",
}

CAPABILITIES: Final[tuple[Capability, ...]] = tuple(
    Capability(
        code=f"{resource}.{action}",
        resource=resource,
        action=action,
        interface_code=f"{resource}.{_ACTION_INTERFACE.get(action, action)}",
    )
    for resource, actions in _RESOURCE_ACTIONS.items()
    for action in actions
)


@dataclass(slots=True)
class _RawCall:
    """One decoded upstream exchange."""

    status: int | None
    payload: Any
    text: str
    latency_ms: int


# ---------------------------------------------------------------------------
# The adapter
# ---------------------------------------------------------------------------
class MidasNxAdapter:
    """MIDAS Gen NX / Civil NX adapter over the NX Open API.

    One instance represents **one** ``midas_clients`` row, i.e. one MIDAS
    installation, and therefore owns one :class:`asyncio.Lock`: 对接规范
    §2.5.2 / §2.5.4 require ``max_concurrency == 1`` per client because any
    modal dialog on the NX host blocks the whole API channel.

    .. note::
       The instance is **bound to the event loop it first runs in**:
       :class:`asyncio.Lock` is loop-bound since Python 3.10, so constructing the
       adapter in one loop and awaiting it in another raises
       ``RuntimeError: ... is bound to a different event loop``.  Build it inside
       the loop that will use it (e.g. inside the FastAPI lifespan), and never
       share one instance across loops.
    """

    def __init__(
        self,
        connection: MidasConnection,
        *,
        version: str | None = None,
        version_range: str = ">=2024",
        http_client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not isinstance(connection, MidasConnection):
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR,
                "MidasNxAdapter 需要一个 app.core.midas_config.MidasConnection",
            )
        self._connection: MidasConnection = connection
        self._version: str = version or "unknown"
        self._version_range: str = version_range
        self._client: httpx.AsyncClient | None = http_client
        self._owns_client: bool = http_client is None
        #: Optional transport override (proxies, ``httpx.MockTransport`` in tests).
        #: The client still gets the adapter's own headers, so the auth wiring is
        #: exercised even when the transport is faked.
        self._transport: httpx.AsyncBaseTransport | None = transport
        #: 对接规范 §2.5.2 / §2.5.4 —— 同一 MIDAS 实例任何时刻只允许一个在途请求。
        self._lock: asyncio.Lock = asyncio.Lock()
        self._lifecycle: AdapterLifecycle = AdapterLifecycle.REGISTERED

    # ------------------------------------------------------------------ #
    # V2.1 §13 properties
    # ------------------------------------------------------------------ #
    @property
    def connection(self) -> MidasConnection:
        """The bound connection config (the MAPI-Key stays wrapped)."""
        return self._connection

    @property
    def code(self) -> str:
        """``midas_gen`` / ``midas_civil`` — matches ``to_registry_row()``."""
        return f"midas_{self._connection.product.value}"

    @property
    def software(self) -> str:
        return self._connection.software

    @property
    def version(self) -> str:
        """Upstream version.  ``"unknown"`` — the API exposes none (对接规范 §10)."""
        return self._version

    @property
    def product(self) -> MidasProduct:
        return self._connection.product

    @property
    def lifecycle(self) -> AdapterLifecycle:
        return self._lifecycle

    @property
    def status(self) -> str:
        """``adapters.status`` value derived from §14's mapping table.

        §13's Protocol has no status accessor even though §14 maps lifecycle to
        the two DB status columns; this property is that missing accessor.
        """
        return LIFECYCLE_DB_STATUS.get(
            self._lifecycle, (AdapterStatus.ENABLED.value, "disconnected")
        )[0]

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<MidasNxAdapter code={self.code!r} base_url={self._connection.base_url!r} "
            f"lifecycle={self._lifecycle.value!r} key={self._connection.masked_key}>"
        )

    # ------------------------------------------------------------------ #
    # V2.1 §13 / §15 — metadata
    # ------------------------------------------------------------------ #
    async def metadata(self) -> AdapterMetadata:
        """§15 metadata.  **No network I/O** (§13: 必须是纯本地返回)."""
        return AdapterMetadata(
            code=self.code,
            name=f"MIDAS {self._connection.product.value.title()} NX Adapter",
            software=self._connection.software,
            version_range=self._version_range,
            protocol="http",
            supports_query=True,
            supports_model=True,
            supports_execute=True,
            # MIDAS itself has no async task API (对接规范 §2.5.1: 官方文档未定义
            # API 层并发/任务能力)；异步由平台 Task Engine 承担（V2.1 §26）。
            supports_async_task=True,
            capabilities=[capability.code for capability in CAPABILITIES],
        )

    async def capabilities(self) -> list[Capability]:
        """Capability mirror (authoritative rows: ``capabilities`` 表, §16.1)."""
        return list(CAPABILITIES)

    # ------------------------------------------------------------------ #
    # V2.1 §13 / §14 — lifecycle
    # ------------------------------------------------------------------ #
    def _set_lifecycle(self, state: AdapterLifecycle) -> None:
        """Record a lifecycle state.

        §14 draws the happy path plus one error path only; strictly rejecting
        every transition it does not draw would block legitimate recovery (e.g.
        ``ERROR -> DISCONNECTING``), so this is a record, not a gate.  The legal
        transition table stays available as
        :data:`app.adapters.base.LIFECYCLE_TRANSITIONS`.
        """
        self._lifecycle = state

    async def connect(self, client: MidasClientConfig | None = None) -> AdapterResult:
        """§13 ``connect``: validate the MAPI-Key and confirm the product runs.

        对接规范 §8: 语义是「校验 MAPI-Key + 确认本地产品在运行」，不是建立 TCP 连接。
        """
        if client is not None:
            self._connection = client
        self._set_lifecycle(AdapterLifecycle.INITIALIZING)
        self._set_lifecycle(AdapterLifecycle.READY)
        self._set_lifecycle(AdapterLifecycle.CONNECTING)
        result = await self.health_check()
        self._set_lifecycle(
            AdapterLifecycle.CONNECTED if result.success else AdapterLifecycle.ERROR
        )
        if not result.success:
            result.warnings.append(
                "connect 失败：对接规范 §2.1 —— MIDAS Gen/Civil NX 必须处于运行状态，"
                "两种接入方式（本地 3030 / 云端中继）都需要产品已打开。"
            )
        return result

    async def disconnect(self) -> AdapterResult:
        """Return to ``READY`` and drop the HTTP client."""
        self._set_lifecycle(AdapterLifecycle.DISCONNECTING)
        await self.aclose()
        self._set_lifecycle(AdapterLifecycle.READY)
        return AdapterResult.ok({"disconnected": True})

    async def aclose(self) -> None:
        """Close the underlying ``httpx.AsyncClient`` when this adapter owns it."""
        client, self._client = self._client, None
        if client is not None and self._owns_client:
            await client.aclose()

    async def __aenter__(self) -> "MidasNxAdapter":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    # ------------------------------------------------------------------ #
    # transport
    # ------------------------------------------------------------------ #
    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=self._connection.headers,  # MAPI-Key，绝不是 Bearer（§2.1）
                verify=self._connection.verify_tls,
                follow_redirects=False,
                transport=self._transport,
            )
        return self._client

    def _url(self, path: str) -> str:
        """Product-scoped URL: ``{base_url}/{product}`` + endpoint (对接规范 §2.1)."""
        return f"{self._connection.db_url}{normalise_endpoint(path)}"

    async def _request(
        self,
        method: str,
        url: str,
        *,
        body: Any = _OMIT_BODY,
        retry_safe: bool = False,
        timeout_seconds: int | None = None,
    ) -> _RawCall:
        """Perform one HTTP call, serialized per client.

        ``retry_safe`` is the whole §26.5 / 对接规范 §3.5 第 5 条 policy in one
        parameter: **only reads may retry**, because 超时 ≠ 回滚 — a write may
        still land after HTTP gave up, and re-sending it would duplicate the
        effect.  Writes therefore always use ``retry_safe=False``.
        """
        attempts = _READ_ATTEMPTS if retry_safe else 1
        timeout = float(timeout_seconds or self._connection.timeout_seconds)
        last_error: AdapterError | None = None
        for attempt in range(1, attempts + 1):
            started = time.perf_counter()
            try:
                client = await self._ensure_client()
                async with self._lock:  # §2.5.2 / §2.5.4：同一实例串行
                    if body is _OMIT_BODY:
                        response = await client.request(method, url, timeout=timeout)
                    else:
                        response = await client.request(
                            method, url, json=body, timeout=timeout
                        )
                return _RawCall(
                    status=response.status_code,
                    payload=self._decode(response),
                    text=response.text,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
            except httpx.ConnectTimeout as exc:
                # TimeoutException 子树：**连接从未建立**（对接规范 §2.3）。
                last_error = _transport_error(
                    ErrorCode.MIDAS_CONNECTION_FAILED,
                    method,
                    url,
                    exc,
                    phase="connect",
                    timeout_seconds=timeout,
                )
            except httpx.ConnectError as exc:
                # NetworkError 子树 —— 与 ConnectTimeout **无继承关系**，但语义完全
                # 相同（端口关闭 / 产品未运行 / DNS / TLS 拒绝），因此同样是
                # phase="connect"。这两个分支合起来才是「从未到达服务」的全集。
                last_error = _transport_error(
                    ErrorCode.MIDAS_CONNECTION_FAILED,
                    method,
                    url,
                    exc,
                    phase="connect",
                )
            except httpx.ReadTimeout as exc:
                # 对接规范 §11.5.13 / §11.5.14：连接**已建立**、请求**已发出**、
                # 没有任何响应。这是**观测**，不是原因 —— 模态对话框冻结整条会话与
                # 网络路径被黑洞/拦截都会产生它（实测黑洞目标抛的同样是
                # ``httpx.ReadTimeout``）。仍是 TASK_TIMEOUT（调用确实超时了），
                # 但阶段与消息必须把「这意味着什么」和「怎么判别」都说清楚。
                last_error = _transport_error(
                    ErrorCode.TASK_TIMEOUT,
                    method,
                    url,
                    exc,
                    phase="read",
                    timeout_seconds=timeout,
                )
            except httpx.ReadError as exc:
                # 读方向上的连接中断（不是超时）：同属「读阶段」失败。
                last_error = _transport_error(
                    ErrorCode.MIDAS_CONNECTION_FAILED,
                    method,
                    url,
                    exc,
                    phase="read",
                )
            except httpx.WriteTimeout as exc:
                # 连接已建立，但请求体没发完。
                last_error = _transport_error(
                    ErrorCode.TASK_TIMEOUT,
                    method,
                    url,
                    exc,
                    phase="write",
                    timeout_seconds=timeout,
                )
            except httpx.WriteError as exc:
                last_error = _transport_error(
                    ErrorCode.MIDAS_CONNECTION_FAILED,
                    method,
                    url,
                    exc,
                    phase="write",
                )
            except httpx.PoolTimeout as exc:
                # 连接池里没有空闲连接：请求**从未被发出**（§2.5.2 每实例并发恒为 1）。
                last_error = _transport_error(
                    ErrorCode.TASK_TIMEOUT,
                    method,
                    url,
                    exc,
                    phase="pool",
                    timeout_seconds=timeout,
                )
            except httpx.TimeoutException as exc:
                # 兜底：四个具体子类都已在上方捕获，这里只剩未知/未来新增的超时类型。
                last_error = _transport_error(
                    ErrorCode.TASK_TIMEOUT,
                    method,
                    url,
                    exc,
                    phase="unknown",
                    timeout_seconds=timeout,
                )
            except httpx.HTTPError as exc:
                last_error = _transport_error(
                    ErrorCode.MIDAS_CONNECTION_FAILED,
                    method,
                    url,
                    exc,
                    phase="unknown",
                )
            # 对接规范 §11.5.13 / §11.5.14 / §2.5.2 — a **read**-phase failure means
            # the connection was established, the request was sent, and the server
            # did not answer.  Retrying lands on exactly the same non-answer: on a
            # frozen session every retry hits the same modal dialog (which is what
            # made a live incident hang for minutes), and on a black-holed network
            # path every retry is dropped just the same.  The two causes are
            # indistinguishable from here, but **both** make the retry useless —
            # it only doubles the caller's wait, so the retry is skipped.
            #
            # Note this is a *different axis* from ``retry_safe``.  ``retry_safe``
            # answers "may this be re-sent without duplicating an effect?" (an
            # idempotent read may); this answers "can re-sending possibly succeed?"
            # (after a read timeout, no).  A **connect** failure is still retried,
            # because that one can be a transient network blip.
            if (last_error.details or {}).get("phase") == "read":
                break
            if attempt < attempts:
                await asyncio.sleep(_RETRY_BACKOFF_SECONDS)
        assert last_error is not None  # pragma: no cover - loop always sets it
        raise last_error

    @staticmethod
    def _decode(response: httpx.Response) -> Any:
        """Decode a body to JSON, falling back to raw text (never raises)."""
        try:
            return response.json()
        except Exception:  # json.JSONDecodeError and friends
            return response.text

    def _result_from_error(
        self, error: AdapterError, *, warnings: Sequence[str] | None = None
    ) -> AdapterResult:
        """``AdapterResult.from_error`` **plus** the transport phase, for the caller.

        V2.1 §19's :class:`AdapterResult` has **no** ``details`` field, so an
        ``AdapterError.details["phase"]`` (the one field that separates 「连接从未
        建立」 from 「连接已建立但没有响应」, 对接规范 §11.5.13) would be dropped
        before it reaches the MCP envelope.  ``data`` is the only structured field the
        envelope keeps (总纲 §4.3.2), so the phase and the **unconfirmed** state it
        implies are written there — together with that state's ``candidates`` and their
        evidence (§11.5.14), so a caller reading only the envelope cannot mistake
        ``session_unresponsive`` for a proven frozen dialog.

        .. warning::
           **No probe is ever run here.**  对接规范 §11.5.13 / §11.5.14: a session
           that answers nothing is not processing requests, so re-probing it inside a
           failing data call would only queue a second timeout behind the same modal
           dialog — or into the same black hole.  The caller confirms the state with
           ``midas_execute action=connect`` (:meth:`diagnose_session`) at a moment of
           its own choosing.
        """
        result = AdapterResult.from_error(error, warnings=list(warnings or []))
        phase = error.details.get("phase")
        if not isinstance(phase, str) or phase not in TRANSPORT_PHASES:
            return result
        state = SESSION_STATE_BY_PHASE.get(phase, "degraded")
        spec = SESSION_STATES.get(state, {})
        result.data = {
            "transport": {
                "phase": phase,
                "method": error.details.get("method"),
                "url": error.details.get("url"),
                "exception": error.details.get("exception"),
            },
            "session": {
                "state": state,
                # 连接阶段的失败**证明**请求没到服务（service_down 的定义）；读阶段的
                # 失败只能证明「没有响应」，而「没有响应」在 §11.5.14 下有两种来源
                # （模态对话框冻结 / 网络黑洞），因此**未证实** —— 要区分它们必须由
                # diagnose_session 同时看 /mapikey/verify，且即便如此也只能得到
                # session_unresponsive（§11.5.14）。
                "confirmed": phase == "connect",
                "usable": False,
                # 候选原因随状态一起给出：只说「无响应」而不说「可能是哪两种」，
                # 调用方就无从下手（§11.5.14：报告观测 + 列出候选）。
                "candidates": list(spec.get("candidates", ())),
                "candidate_evidence": dict(spec.get("candidate_evidence", {})),
                "next_step": "midas_execute action=connect",
            },
        }
        result.warnings.append(
            f"传输阶段 phase={phase}（{TRANSPORT_PHASE_MEANING[phase]}）；"
            f"由它推出的会话状态 {state!r} "
            f"{'已证实' if phase == 'connect' else '**未证实**'}。要拿到证实的状态请调用 "
            "midas_execute action=connect（它按对接规范 §11.5.13 同时探测 "
            "/mapikey/verify 与 /db/UNIT）。本次调用**没有**补探测：没有响应的会话"
            "不得被探测第二次（§11.5.13）—— 无论它是被对话框冻结还是网络路径不通，"
            "再探一次都只是再赔一次超时。"
        )
        return result

    @staticmethod
    def _phase_of(result: AdapterResult) -> str | None:
        """Recover ``details["phase"]`` from a failed result (see :meth:`_result_from_error`)."""
        data = result.data
        if not isinstance(data, dict):
            return None
        transport = data.get("transport")
        if not isinstance(transport, dict):
            return None
        phase = transport.get("phase")
        return phase if isinstance(phase, str) and phase in TRANSPORT_PHASES else None

    @staticmethod
    def _probe_record(endpoint: str, result: AdapterResult) -> dict[str, Any]:
        """One probe's raw outcome: status / latency / code / phase (对接规范 §11.5.13).

        ``raw_response`` is deliberately **not** copied (V2.1 §19 字段约束): the
        diagnosis needs the status code and the latency to be actionable, not the
        upstream body.
        """
        return {
            "endpoint": endpoint,
            "ok": result.success,
            "http_status": result.raw_status,
            "latency_ms": result.latency_ms,
            "error_code": result.error_code,
            "phase": MidasNxAdapter._phase_of(result),
        }

    @staticmethod
    def _verdict(
        state: str,
        *,
        probes: dict[str, Any],
        latency_ms: int | None = None,
        raw_status: int | None = None,
    ) -> AdapterResult:
        """Build the diagnosis record + the :class:`AdapterResult` that carries it."""
        spec = SESSION_STATES[state]
        record: dict[str, Any] = {
            "state": state,
            "diagnosis": spec["diagnosis"],
            "remedy": spec["remedy"],
            "usable": state == "healthy",
            # 这个判定有多硬（§11.5.14 判别表）：True 只给那些被**正面证据**证明的行。
            # 调用方可以据此决定要不要把 remedy 当成事实来执行 —— ``session_unresponsive``
            # 是 False，因为它的 remedy 是**判别步骤**而不是结论。
            "confirmed": spec["confirmed"],
            # 同一签名的候选**原因** + 每个候选的证据（§11.5.14）。除
            # ``session_unresponsive`` 外都为空：其余状态都被正面证据钉死了。
            "candidates": list(spec["candidates"]),
            "candidate_evidence": dict(spec["candidate_evidence"]),
            "requires_human": spec["requires_human"],
            "retry_helps": spec["retry_helps"],
            "recoverable_via_api": spec["recoverable_via_api"],
            "probes": probes,
            "rule": (
                "对接规范 §2.5.2 / §11.5.12 / §11.5.13 / §11.5.14；"
                "总纲 §4.4（错误码封闭）"
            ),
        }
        message = f"{spec['diagnosis']} 处置：{spec['remedy']}"
        if state == "healthy":
            return AdapterResult.ok(
                record,
                warnings=[
                    "会话判定（对接规范 §11.5.13）：/mapikey/verify 与 /db/UNIT 都正常。"
                ],
                raw_status=raw_status,
                latency_ms=latency_ms,
            )
        code = str(spec["error_code"])
        return AdapterResult(
            success=False,
            status=TaskStatus.FAILED.value,
            data=record,
            error_code=code,
            error_message=message,
            warnings=[
                f"会话判定（对接规范 §2.5.2 / §11.5.13 / §11.5.14）：state={state!r}；"
                f"confirmed={spec['confirmed']}，usable=False，"
                f"requires_human={spec['requires_human']}，"
                f"retry_helps={spec['retry_helps']}，"
                f"candidates={list(spec['candidates'])}。"
            ],
            raw_status=raw_status,
            latency_ms=latency_ms,
        )

    # ------------------------------------------------------------------ #
    # V2.1 §17.3 — wrap / unwrap
    # ------------------------------------------------------------------ #
    def wrap(self, payload: Any, wrapper: str | None) -> dict[str, Any]:
        """``request_wrapper`` -> ``{"Assign": ...}`` / ``{"Argument": ...}``.

        Delegates to :func:`wrap_payload` so the mock adapter (and any future
        adapter) executes exactly the same §17.3 transformation.

        * ``None`` wrapper = 端点不接收请求体 (§17.3) -> ``{}``; the caller
          decides whether to send nothing at all or a bare ``{}``
          (``/doc/ANAL`` needs the bare ``{}``, 对接规范 §11.5.7).
        * A **bare string** payload is legal and required by ``/doc/EXPORT``,
          ``/doc/SAVEAS``, ``/doc/OPEN``, ``/doc/IMPORT`` … — passing an object
          there is rejected by upstream while still answering **200**
          (对接规范 §3.4 末行 / §11.5.2).
        """
        return wrap_payload(payload, wrapper)

    def unwrap(self, response: Any, root_key: str | None) -> Any:
        """V2.1 §17.3, branch for branch — delegates to :func:`unwrap_response`.

        ``GET /db/*`` has exactly three shapes (对接规范 §3.2.1) and **the empty
        table is ``{"message": ""}``, not ``{"NODE": {}}``**, so a bare
        ``response[root_key]`` raises ``KeyError`` on an empty model.  That is
        why this function never indexes before shape-matching.

        Text-pattern matching is **not** performed here: it is the third,
        fallback layer of :func:`app.adapters.errors.normalize_upstream` and must
        never be the sole judge (V2.1 §20.4).
        """
        return unwrap_response(response, root_key)

    # ------------------------------------------------------------------ #
    # core call pipeline
    # ------------------------------------------------------------------ #
    async def _execute(
        self,
        method: str,
        path: str,
        *,
        wrapper: str | None = None,
        payload: Any = None,
        root_key: str | None = None,
        retry_safe: bool = False,
        timeout_seconds: int | None = None,
        omit_body: bool = False,
        empty_object_body: bool = False,
        allow_ambiguous_message_success: bool = False,
        warnings: Sequence[str] | None = None,
        not_found_code: str | None = None,
    ) -> AdapterResult:
        """Wrap -> send -> judge -> unwrap, with §20.4 error normalization."""
        endpoint = normalise_endpoint(path)
        url = self._url(endpoint)
        body: Any = _OMIT_BODY
        if not omit_body:
            body = self.wrap(payload, wrapper)
            if wrapper is None and not empty_object_body:
                body = _OMIT_BODY
        if not_found_code is None:
            # 对接规范 §2.3: 404 通常是 Base URL 错；但 /db/XXX/<id> 上的 404 是
            # 「目标键不存在」，两者必须区分，否则 upsert 的 PUT→POST 回退会失效。
            not_found_code = (
                ErrorCode.RESOURCE_NOT_FOUND.value
                if _is_id_addressed(endpoint)
                else ErrorCode.INTERFACE_NOT_FOUND.value
            )
        try:
            raw = await self._request(
                method,
                url,
                body=body,
                retry_safe=retry_safe,
                timeout_seconds=timeout_seconds,
            )
        except AdapterError as exc:
            return self._result_from_error(exc, warnings=warnings)

        verdict = normalize_upstream(
            payload=raw.payload,
            raw_status=raw.status,
            root_key=root_key,
            context=f"{method} {endpoint}",
            not_found_code=not_found_code,
            allow_ambiguous_message_success=allow_ambiguous_message_success,
        )
        collected = list(warnings or []) + list(verdict.warnings)
        if not verdict.ok:
            return AdapterResult(
                success=False,
                status=TaskStatus.FAILED.value,
                error_code=verdict.error_code,
                error_message=verdict.error_message,
                warnings=collected,
                raw_status=raw.status,
                raw_response=raw.payload,
                latency_ms=raw.latency_ms,
            )
        return AdapterResult.ok(
            verdict.data,
            warnings=collected,
            raw_status=raw.status,
            raw_response=raw.payload,
            latency_ms=raw.latency_ms,
        )

    # ------------------------------------------------------------------ #
    # §2.2 / §2.5.2 — health
    # ------------------------------------------------------------------ #
    async def health_check(self) -> AdapterResult:
        """``GET /mapikey/verify`` — **host root, no product segment**.

        对接规范 §2.2 / §11.2: 根路径返回 200，``/gen/mapikey/verify`` 返回 **404**.
        Returns ``status`` / ``keyVerified`` / ``program`` / ``connectionID``.

        .. warning::
           **This cannot detect a modal-dialog-blocked session** (对接规范
           §2.5.2 item 2): 会话被对话框阻塞时 ``/mapikey/verify`` 仍然回答
           ``connected``（中继在应答），而所有 ``/db/*`` 调用超时。
           Pair it with :meth:`probe_alive` / :meth:`check_channel`.
        """
        try:
            raw = await self._request(
                "GET", self._connection.verify_url, retry_safe=True
            )
        except AdapterError as exc:
            # 阶段必须活到调用方（对接规范 §11.5.13 的判据就建立在它上面）。
            return self._result_from_error(exc)
        verdict = normalize_upstream(
            payload=raw.payload,
            raw_status=raw.status,
            context="GET /mapikey/verify",
        )
        if not verdict.ok:
            return AdapterResult(
                success=False,
                status=TaskStatus.FAILED.value,
                error_code=verdict.error_code,
                error_message=verdict.error_message,
                warnings=list(verdict.warnings),
                raw_status=raw.status,
                raw_response=raw.payload,
                latency_ms=raw.latency_ms,
            )
        source = raw.payload if isinstance(raw.payload, dict) else {}
        summary = {
            "status": source.get("status"),
            "keyVerified": source.get("keyVerified"),
            "program": source.get("program"),
            "connectionID": source.get("connectionID"),
            "user": source.get("user"),
        }
        warnings = [
            "对接规范 §11.4：实测 ``user`` / ``connectionID`` 均为空字符串，"
            "**不得依赖 user 字段**；更不得据它推导 NX 主机的 Windows 账户或路径"
            "（§3.5 第 6 条：那是 MAPI 账号邮箱）。",
            "对接规范 §2.5.2 item 2：本检查**无法**发现被模态对话框阻塞的会话，"
            "必须叠加 probe_alive() 的 /db/UNIT 真实数据探针。",
        ]
        if summary["keyVerified"] is False:
            return AdapterResult(
                success=False,
                status=TaskStatus.FAILED.value,
                error_code=ErrorCode.MIDAS_AUTH_FAILED.value,
                error_message="MAPI-Key 校验失败（keyVerified=false）；对接规范 §2.3：401 = Key 错误/缺失",
                warnings=warnings,
                raw_status=raw.status,
                raw_response=raw.payload,
                latency_ms=raw.latency_ms,
            )
        status_text = summary["status"]
        if isinstance(status_text, str) and status_text and status_text.lower() != "connected":
            return AdapterResult(
                success=False,
                status=TaskStatus.FAILED.value,
                error_code=ErrorCode.MIDAS_CONNECTION_FAILED.value,
                error_message=(
                    f"MIDAS 产品未连接（status={status_text!r}）。对接规范 §2.1："
                    "MIDAS Gen/Civil NX 必须处于运行状态，两种接入方式都依赖它。"
                ),
                warnings=warnings,
                raw_status=raw.status,
                raw_response=raw.payload,
                latency_ms=raw.latency_ms,
            )
        return AdapterResult.ok(
            summary,
            warnings=warnings,
            raw_status=raw.status,
            raw_response=raw.payload,
            latency_ms=raw.latency_ms,
        )

    async def verify_connection(self) -> AdapterResult:
        """Alias of :meth:`health_check` using the 对接规范 §3.5 第 6 条 name.

        该条明令**禁止**从 ``verify_connection()["user"]`` 推导路径，因此这里只
        转发结果，不提供任何路径推导。
        """
        return await self.health_check()

    async def probe_alive(self) -> AdapterResult:
        """Lightweight real-data liveness probe: ``GET /db/UNIT``.

        对接规范 §2.5.4 item 2 / V2.1 §13: ``/mapikey/verify`` 看不见阻塞，
        必须增加一次轻量真实数据调用作为活性探针。 ``/db/UNIT`` 在空模型下也有
        数据（§11.3），即使返回 ``{"message":""}`` 也证明通道可达。

        探针发现的是**「没有响应」**，不是**原因**：模态对话框冻结整条会话与网络
        路径被黑洞（§11.5.14）在这里的表现**逐字段相同**，因此这条探针的结论必须
        由 :meth:`diagnose_session` 组装成 ``session_unresponsive`` + 候选原因，
        **不得**直接说成「被对话框阻塞」。
        """
        return await self._execute(
            "GET",
            "/db/UNIT",
            root_key="UNIT",
            retry_safe=True,
            warnings=[
                "活性探针：对接规范 §2.5.4 item 2 —— 只有真实数据调用才能发现"
                "没有响应的会话（模态对话框冻结与网络黑洞不可区分，§11.5.14）。"
            ],
        )

    async def diagnose_session(self) -> AdapterResult:
        """Structured verdict on *why* the session is (or is not) usable.

        **判据（对接规范 §11.5.13 推论 / §11.5.14 判别表 / §2.5.2 item 2）**：
        ``GET /mapikey/verify`` **不碰文档**，``GET /db/UNIT`` **碰文档**。两条探针
        各自失败的方式，区分出下面这些处境 —— 注意**只有一部分是能证明的**：

        * ``verify`` ok + ``unit`` ok -> ``healthy``（已证实：两条都收到了应答）
        * ``verify`` ok + ``unit`` ``400 project is not opened`` -> ``no_project``
          （已证实；对接规范 §11.5.12；**可在 API 内恢复**：``POST /doc/NEW {}``）
        * ``verify`` ok + ``unit`` 读超时 -> ``document_frozen``（**已证实**：verify
          成功即证明会话在应答，故阻塞只能在文档层）
        * ``verify`` 读超时 + ``unit`` 读超时 -> ``session_unresponsive``
          （**未证实**：§11.5.14 —— 模态对话框冻结与网络黑洞产生**逐字段相同**的签名，
          服务端无法区分，因此只报观测 + 列候选）
        * ``verify`` 连接被拒 / 连接超时 -> ``service_down``（已证实，短路，不再探测
          ``unit``）
        * ``verify`` 401 -> ``auth_failed``（已证实，短路）
        * 其它任何组合 -> ``degraded``（未证实：观测本身就不足以支撑结论）

        The record (``result.data``) always carries ``state`` / ``diagnosis`` /
        ``remedy`` / both probes' raw status + latency + phase (``probes.unit`` is
        ``None`` when the verify probe short-circuited), plus the fields the caller
        can branch on without reading prose:

        * ``confirmed`` — the state is **positively proven** by what was observed.
          ``False`` means the remedy is a set of **discriminating steps**, not a
          conclusion (§11.5.14);
        * ``candidates`` / ``candidate_evidence`` — the causes that produce this same
          signature, and the evidence for each (non-empty only for
          ``session_unresponsive``);
        * ``usable`` — data calls can run **right now** (only ``healthy``);
        * ``requires_human`` — someone has to act on the NX host / config;
        * ``recoverable_via_api`` — the API itself can fix it (``no_project``:
          ``POST /doc/NEW {}``);
        * ``retry_helps`` — repeating the failed call as-is could work.

        **Why ``session_unresponsive`` must not be called a frozen session.**  The
        signature (``/mapikey/verify`` **and** ``/db/UNIT`` both read-timeout) has
        two known sources, and they are **indistinguishable from the server side**
        (§11.5.14, measured on this machine):

        1. a **modal dialog** on the NX host blocks the entire API session — while it
           is open the server is *not processing requests at all* (measured:
           ``/gen/db/UNIT``, ``/gen/ope/PROJECTSTATUS`` **and** ``/mapikey/verify``
           all returned ``curl 000``, 对接规范 §11.5.13);
        2. a **black-holed network path** (or an intercepting proxy): ``10.255.255.1``
           raises the very same ``httpx.ReadTimeout`` — **not** ``ConnectTimeout`` —
           and the guaranteed-unroutable RFC 5737 addresses still show a TCP connect
           "succeeding" in 0.00 s, so a raw TCP probe cannot tell "something is
           listening" from "a middlebox accepted everything".

        Naming the second case ``session_frozen`` produced a remedy that told the
        operator to go close a dialog on the NX host while the real problem was the
        network — a wrong remedy, which is worse than no diagnosis.  So the verdict
        names the **observation** (no response) and lists the candidates.

        **The useful half is kept, and it holds for both candidates.**  A retry does
        not take a different path: behind a dialog it queues behind the very same
        dialog and times out identically; into a black hole it is dropped just the
        same.  Even the API-side remedies (``POST /doc/NEW``) cannot get in.  Either
        way a human must act — that is why ``requires_human=True`` /
        ``retry_helps=False`` regardless of which candidate turns out to be true, and
        the remedy gives the discriminating steps in order (dialog first, then network
        reachability).
        ``no_project`` is the opposite case: it is **recoverable through the API**
        (``POST /doc/NEW {}``, 实机验证 §11.5.12), and the remedy says so.

        Probes are reused, never duplicated: this method calls :meth:`health_check`
        and :meth:`probe_alive`, and :meth:`check_channel` calls *this*.  A
        connection-stage failure on ``/mapikey/verify`` short-circuits, so a dead
        product costs one failed connect attempt instead of an extra timeout.
        """
        return await self._diagnose(await self.health_check())

    async def _diagnose(self, verify: AdapterResult) -> AdapterResult:
        """Core of :meth:`diagnose_session`; ``verify`` is an already-run probe.

        Split out so ``midas_execute action=connect`` can hand in the
        ``/mapikey/verify`` result it has **already** paid for (``connect()`` runs
        it) instead of probing the host a second time — 对接规范 §11.5.13 / §11.5.14:
        a session that answers nothing must not be probed twice (whether it is frozen
        or unreachable, a second probe only pays for a second timeout).
        """
        verify_phase = self._phase_of(verify)
        # 固定形状：``unit`` 为 ``None`` 表示「按判据表**故意没探**」（verify 在连接层
        # 就失败了），而不是「探了但没记录」。
        probes: dict[str, Any] = {
            "verify": self._probe_record("/mapikey/verify", verify),
            "unit": None,
        }
        spent = verify.latency_ms or 0

        if not verify.success and verify_phase != "read":
            # 连接层 / 认证层失败：/db/UNIT 不可能给出更多信息，且此时它多半只会
            # 再浪费一次超时（服务端根本收不到请求），因此短路。
            if verify_phase == "connect" or verify.error_code == (
                ErrorCode.MIDAS_CONNECTION_FAILED.value
            ):
                state = "service_down"
            elif verify.error_code == ErrorCode.MIDAS_AUTH_FAILED.value:
                state = "auth_failed"
            else:
                state = "degraded"
            return self._verdict(
                state, probes=probes, latency_ms=spent, raw_status=verify.raw_status
            )

        probe = await self.probe_alive()
        probes["unit"] = self._probe_record("/db/UNIT", probe)
        probe_phase = self._phase_of(probe)
        spent += probe.latency_ms or 0

        if verify.success and probe.success:
            return self._verdict(
                "healthy", probes=probes, latency_ms=spent, raw_status=probe.raw_status
            )

        if verify.success:
            # 通道活着，问题在**文档/模型**这一层（§11.5.12 vs §11.5.13）。
            if probe.error_code == ErrorCode.MODEL_UNAVAILABLE.value:
                state = "no_project"
            elif probe_phase == "read":
                state = "document_frozen"
            elif probe_phase == "connect":
                state = "service_down"
            else:
                state = "degraded"
        # verify 自己就读超时了，而 unit 也没有响应：这是**观测到的事实** —— 整条会话
        # 没有任何响应。它**不是**「会话被冻结」的证据：黑洞网络路径抛出的是同一个
        # ``httpx.ReadTimeout``（对接规范 §11.5.14 实测），因此这里给出的是
        # ``session_unresponsive``（confirmed=False）＋两个候选原因，而不是断言对话框。
        elif probe_phase == "read":
            state = "session_unresponsive"
        else:
            state = "degraded"
        return self._verdict(
            state, probes=probes, latency_ms=spent, raw_status=probe.raw_status
        )

    async def check_channel(self) -> AdapterResult:
        """``health_check()`` **and** ``probe_alive()`` — both must pass (§13).

        实现复用 :meth:`diagnose_session`（同样只跑这两条探针，不复制探针逻辑），
        但把「两者都失败」进一步判成 ``session_unresponsive`` / ``document_frozen`` /
        ``no_project`` / ``service_down`` / ``auth_failed``（对接规范 §11.5.13 /
        §11.5.14），调用方不必再从一句「探针失败」里猜处置 —— 其中
        ``session_unresponsive`` **只报观测并列出候选**，因为模态对话框与网络黑洞
        在服务端不可区分（§11.5.14）。
        """
        return await self.diagnose_session()

    async def _connect_with_diagnosis(self) -> AdapterResult:
        """``connect`` **plus** the structured session diagnosis (对接规范 §11.5.13 / §11.5.14).

        ``midas_execute action=connect`` is the natural home for the verdict: it is
        the only action that already touches the host without needing a document,
        and ``tool_interfaces`` marks ``server.connect`` as an inline (秒级) action
        (``task_type IS NULL``, V2.1 §9.2).  Exposing it here therefore needs **no
        new capability row** — the table is generated, and adding a row would need
        a migration (V2.1 §16.1).

        ``connect()`` has already run ``/mapikey/verify``, so that result is handed
        to :meth:`_diagnose` as-is: the whole action costs **one** extra
        ``/db/UNIT`` request, never a second verify.
        """
        connected = await self.connect()
        diagnosis = await self._diagnose(connected)
        record = diagnosis.data if isinstance(diagnosis.data, dict) else {}
        data: dict[str, Any] = (
            dict(connected.data) if isinstance(connected.data, dict) else {}
        )
        data["diagnosis"] = record
        warnings = list(connected.warnings) + [
            f"会话判定（对接规范 §11.5.13 / §11.5.14）见 data.diagnosis："
            f"state={record.get('state')!r}；"
            f"confirmed={record.get('confirmed')}，usable={record.get('usable')}，"
            f"requires_human={record.get('requires_human')}，"
            f"retry_helps={record.get('retry_helps')}，"
            f"candidates={record.get('candidates')}。"
        ]
        latency = (connected.latency_ms or 0) + (diagnosis.latency_ms or 0)
        if connected.success:
            return AdapterResult.ok(
                data,
                warnings=warnings,
                raw_status=connected.raw_status,
                raw_response=connected.raw_response,
                latency_ms=latency,
            )
        # connect 自己失败了（产品没运行 / Key 错）：保留它的错误码与消息，
        # 只把判定附加上去 —— 错误码仍取自总纲 §4.4 的封闭集合。
        return AdapterResult(
            success=False,
            status=TaskStatus.FAILED.value,
            data=data,
            error_code=connected.error_code,
            error_message=connected.error_message,
            warnings=warnings,
            raw_status=connected.raw_status,
            raw_response=connected.raw_response,
            latency_ms=latency,
        )

    # ------------------------------------------------------------------ #
    # §5 — schema introspection
    # ------------------------------------------------------------------ #
    @staticmethod
    def is_introspectable(resource: str) -> bool:
        """``/info`` exists for ``/db/*`` only (对接规范 §5.1)."""
        return normalise_endpoint(resource).lower().startswith("/db/")

    async def introspect(self, resource: str) -> AdapterResult:
        """``GET /info/db/<RES>`` -> the server-declared field set.

        对接规范 §5.0.1: 自省响应**不以资源名为键**，而是固定包在 ``Argument``
        下（实测 7 个资源顶层键一律 ``['$schema','Argument']``），因此必须取
        ``payload["Argument"]["properties"]``。

        对接规范 §5.1: ``/info`` **只为 ``/db/*`` 提供**，设计代码端点一律 404
        （``/DESIGN/*`` 147 对中 0 对可用），所以非 ``/db`` 资源直接报错，
        调用方必须回退到 ``tool_interfaces.request_schema_json``。
        """
        endpoint = normalise_endpoint(resource)
        if not self.is_introspectable(endpoint):
            raise AdapterError(
                ErrorCode.CAPABILITY_NOT_SUPPORTED,
                f"{endpoint} 不支持自省：对接规范 §5.1 —— /info 只为 /db/* 提供，"
                "设计代码端点（/DESIGN/**）一律 404（147 对中 0 对可用）。"
                "该端点的 schema 必须来自 tool_interfaces.request_schema_json"
                "（手册或实机记录，对接规范 §5.1 末段）。",
                details={"endpoint": endpoint},
            )
        try:
            raw = await self._request(
                "GET", self._url(f"/info{endpoint}"), retry_safe=True
            )
        except AdapterError as exc:
            return self._result_from_error(exc)
        verdict = normalize_upstream(
            payload=raw.payload,
            raw_status=raw.status,
            context=f"GET /info{endpoint}",
        )
        if not verdict.ok:
            return AdapterResult(
                success=False,
                status=TaskStatus.FAILED.value,
                error_code=verdict.error_code,
                error_message=verdict.error_message,
                warnings=list(verdict.warnings),
                raw_status=raw.status,
                raw_response=raw.payload,
                latency_ms=raw.latency_ms,
            )
        payload = raw.payload if isinstance(raw.payload, dict) else {}
        argument = payload.get("Argument")
        if not isinstance(argument, dict):
            return AdapterResult(
                success=False,
                status=TaskStatus.FAILED.value,
                error_code=ErrorCode.MIDAS_API_ERROR.value,
                error_message=(
                    "自省响应缺少固定包装键 'Argument'（对接规范 §5.0.1：实测 7 个"
                    "资源顶层键一律 ['$schema','Argument']，不是资源名）"
                ),
                raw_status=raw.status,
                raw_response=raw.payload,
                latency_ms=raw.latency_ms,
            )
        properties = argument.get("properties")
        return AdapterResult.ok(
            {
                "resource": resource_of(endpoint),
                "endpoint": endpoint,
                "schema_uri": payload.get("$schema"),
                "properties": properties if isinstance(properties, dict) else {},
                "schema": argument,
                "complete": False,
            },
            warnings=[
                "对接规范 §5.0.1 / §5.2 / §11.4：/info 的 schema **扁平且不完整**"
                "（不声明 required、不表达分支；实测 MATL 仅 9 个属性、SECT 11 个、"
                "CONS 只有 1 个 ITEMS、STLD 4 个），只适合校验字段名是否存在，"
                "不足以重建完整载荷；且它既不保证是服务器接受集合的超集也不保证是子集"
                "（§5.2 /db/POSL、/db/STBK 两例）。**与实机冲突时以实机往返为准**"
                "（§3.5 第 9 条）。",
                "对接规范 §5.0.1：应作为离线构建步骤（build_introspect.py）"
                "而非运行时行为。",
            ],
            raw_status=raw.status,
            raw_response=raw.payload,
            latency_ms=raw.latency_ms,
        )

    # ------------------------------------------------------------------ #
    # §11.5.1 — DELETE
    # ------------------------------------------------------------------ #
    @staticmethod
    def _coerce_ids(ids: Any) -> list[str]:
        """Normalize ``ids`` and **refuse the table-wiping Assign form**."""
        if isinstance(ids, dict):
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR,
                "拒绝执行：DELETE 携带 ID 键的 Assign 体会**清空整张表**，完全忽略传入的 id"
                "（对接规范 §11.5.1 实机复现：DELETE /gen/db/NODE {\"Assign\":{\"1\":null}} "
                "的响应回显了两条记录 1 和 3 而请求里只有 id 1，随后整表清空；对 /db/NODE "
                "还会连带删掉挂在其上的单元）。单条删除只能用 delete(resource, [id])；"
                "确实要清空整表请显式调用 delete_all(resource, confirm=True)。"
                "手册 /db/CNLD 的 DELETE 示例正是这种危险写法（§11.6 末段）。",
                details={"received_type": "dict"},
            )
        if ids is None:
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR, "delete 需要至少一个 id（逐 id 单条删除）"
            )
        if isinstance(ids, (str, int)) and not isinstance(ids, bool):
            return [str(ids)]
        if isinstance(ids, (list, tuple, set, frozenset)):
            resolved: list[str] = []
            for item in ids:
                if isinstance(item, bool) or not isinstance(item, (str, int)):
                    raise AdapterError(
                        ErrorCode.VALIDATION_ERROR,
                        f"delete 的 id 必须是字符串或整数，收到 {type(item).__name__}",
                    )
                resolved.append(str(item))
            if not resolved:
                raise AdapterError(
                    ErrorCode.VALIDATION_ERROR, "delete 需要至少一个 id"
                )
            return resolved
        raise AdapterError(
            ErrorCode.VALIDATION_ERROR,
            f"delete 的 ids 必须是标量或数组，收到 {type(ids).__name__}",
        )

    async def delete(
        self,
        resource: str,
        ids: Any,
        *,
        timeout_seconds: int | None = None,
    ) -> AdapterResult:
        """Delete records **one HTTP call per id** via ``DELETE {endpoint}/{id}``.

        对接规范 §3.5 第 1 条 / §11.5.1: 单条删除**只允许**走未文档化的
        ``DELETE {endpoint}/{id}``；带 ``Assign`` 体的形式会清空整表。
        写操作不重试（V2.1 §26.5）。
        """
        endpoint = normalise_endpoint(resource)
        id_list = self._coerce_ids(ids)
        done: list[dict[str, Any]] = []
        for one in id_list:
            result = await self._execute(
                "DELETE",
                f"{endpoint}/{one}",
                omit_body=True,
                retry_safe=False,
                timeout_seconds=timeout_seconds,
                warnings=[
                    "对接规范 §11.5.1：DELETE {endpoint}/{id} 是**未文档化**但实机确认的"
                    "单条删除形式；写操作超时后禁止自动重试（V2.1 §26.5）。"
                ],
            )
            if not result.success:
                result.warnings.append(
                    f"批量删除在第 {len(done) + 1}/{len(id_list)} 个 id（{one}）处失败；"
                    f"已成功删除：{done or '无'}。**不要自动重试**——超时 ≠ 回滚，"
                    "必须先读回模型状态（V2.1 §26.5）。"
                )
                result.data = {
                    "endpoint": endpoint,
                    "deleted": [entry["id"] for entry in done],
                    "failed_id": one,
                }
                return result
            done.append({"id": one, "data": result.data, "latency_ms": result.latency_ms})
        return AdapterResult.ok(
            {
                "endpoint": endpoint,
                "mode": "per_id",
                "deleted": [entry["id"] for entry in done],
                "results": done,
            },
            warnings=[
                "对接规范 §11.5.1：单条删除只走 DELETE {endpoint}/{id}；"
                "带 Assign 体的 DELETE 会清空整表，已被适配器守卫拒绝。"
            ],
            raw_status=200,
            latency_ms=sum(entry["latency_ms"] or 0 for entry in done) or None,
        )

    def delete_using_assign_body(
        self, resource: str, assign_body: Any = None
    ) -> NoReturn:
        """**Always raises.**  The §11.5.1 guard, kept as an explicit sink.

        Kept as a named method so that any call site (or future Interface
        registration) that tries the ``Assign``-body form fails loudly here
        instead of silently wiping a table upstream.
        """
        raise AdapterError(
            ErrorCode.VALIDATION_ERROR,
            f"禁止：{normalise_endpoint(resource)} 的 Assign 体 DELETE 会**清空整张表**。"
            "对接规范 §11.5.1 实机复现：请求里只有 id 1，响应却回显了 1 和 3 两条记录，"
            "随后整表清空 —— 它完全忽略传入的 id；对 /db/NODE 还会连带删掉挂在其上的单元。"
            "单条删除请用 delete(resource, [id])（逐 id 一次 DELETE {endpoint}/{id}）；"
            "确实要清空整表请显式调用 delete_all(resource, confirm=True)。"
            "该形式必须从 Interface 注册表中移除（V2.1 §17.5 第 1 条）。",
            details={"endpoint": normalise_endpoint(resource)},
        )

    async def delete_all(
        self,
        resource: str,
        *,
        confirm: bool = False,
        timeout_seconds: int | None = None,
    ) -> AdapterResult:
        """Wipe a whole table.  **Requires ``confirm=True``.**

        对接规范 §3.5 第 1 条: the ``Assign``-body DELETE ignores every id and
        clears the table, so it is only reachable through this deliberately
        named, explicitly confirmed entry point.
        """
        endpoint = normalise_endpoint(resource)
        if not confirm:
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR,
                f"delete_all({endpoint}) 需要显式 confirm=True：它会**清空整张表**"
                "（对接规范 §3.5 第 1 条 / §11.5.1）。单条删除请用 "
                "delete(resource, [id])。",
                details={"endpoint": endpoint},
            )
        return await self._execute(
            "DELETE",
            endpoint,
            wrapper=WRAPPER_ASSIGN,
            payload={},
            retry_safe=False,
            timeout_seconds=timeout_seconds,
            warnings=[
                f"⚠️ 已按整表清空语义执行 DELETE {endpoint} + Assign 体："
                "对接规范 §11.5.1 证明上游**忽略请求体里的 id**、操作整张表，"
                "因此这里刻意不传任何 id（空映射）。写操作不自动重试（V2.1 §26.5），"
                "且 MIDAS 侧没有事务可回滚（§25.3）。",
            ],
        )

    # ------------------------------------------------------------------ #
    # §11.5.3 — upsert
    # ------------------------------------------------------------------ #
    async def create_or_update(
        self,
        resource: str,
        data: Any,
        *,
        order: str = "put_first",
        timeout_seconds: int | None = None,
        validate_after_write: bool = False,
    ) -> AdapterResult:
        """``upsert`` implemented by the adapter itself (对接规范 §11.5.3).

        **Chosen order: ``PUT`` first, ``POST`` only on a not-found failure.**
        Rationale (all three points are live-verified or documented):

        1. ``POST`` is **create-only**: an existing key answers
           ``400 {"error":{"message":"Key Already Exist"}}`` (对接规范 §11.5.3).
           POST-first would therefore *always* burn a call and *always* provoke a
           spurious error body on the common update path, and that 400 is itself a
           genuine error signal we would have to swallow — the exact kind of
           "looks like failure, is success" noise §20.4 warns about.
        2. ``PUT`` first is safe to fall back from: a rejected ``PUT`` writes
           nothing, so the follow-up ``POST`` cannot duplicate an effect.  The
           reverse order is the dangerous one (a ``POST`` that *did* create,
           followed by a ``PUT`` that fails after landing).
        3. New-file-required data (units, structure type …) is ``GET``/``PUT``
           only — ``POST`` 不生效 (对接规范 §3.3) — so ``PUT``-first is the only
           order that can ever work for those endpoints.

        Set ``order="post_first"`` only for an endpoint known to reject ``PUT``
        on a missing key in a way the not-found detector cannot see.
        """
        if order not in ("put_first", "post_first"):
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR,
                f"order 必须是 'put_first' / 'post_first'，收到 {order!r}",
            )
        endpoint = normalise_endpoint(resource)
        records = coerce_assign_records(endpoint, data)
        records, contract_warnings = self._apply_write_contract(endpoint, records)
        body = build_assign_body(endpoint, records)

        async def put() -> AdapterResult:
            return await self._execute(
                "PUT",
                endpoint,
                wrapper=WRAPPER_ASSIGN,
                payload=body,
                retry_safe=False,
                timeout_seconds=timeout_seconds,
                warnings=contract_warnings,
            )

        async def post() -> AdapterResult:
            return await self._execute(
                "POST",
                endpoint,
                wrapper=WRAPPER_ASSIGN,
                payload=body,
                retry_safe=False,
                timeout_seconds=timeout_seconds,
                warnings=contract_warnings,
            )

        attempts: list[dict[str, Any]] = []
        if order == "put_first":
            first = await put()
            attempts.append(_attempt_summary("PUT", first))
            if first.success:
                return self._finish_upsert(
                    first, endpoint, attempts, order, validate_after_write
                )
            if not _is_missing_failure(first):
                first.data = {"endpoint": endpoint, "order": order, "attempts": attempts}
                return first
            second = await post()
            attempts.append(_attempt_summary("POST", second))
            if not second.success:
                second.data = {"endpoint": endpoint, "order": order, "attempts": attempts}
                second.warnings.append(
                    "PUT→POST 回退也失败：对接规范 §11.5.3 的 upsert 需要自行实现次序，"
                    "上游没有幂等保证。**不要自动重试写操作**（V2.1 §26.5）。"
                )
                return second
            second.warnings.append(
                "PUT 报告目标不存在，已回退到 POST 创建（对接规范 §11.5.3：POST 是"
                "「仅创建」；默认次序为先 PUT 后 POST，理由见 create_or_update 文档）。"
            )
            return self._finish_upsert(
                second, endpoint, attempts, order, validate_after_write
            )

        first = await post()
        attempts.append(_attempt_summary("POST", first))
        if first.success:
            return self._finish_upsert(
                first, endpoint, attempts, order, validate_after_write
            )
        if first.error_code != ErrorCode.RESOURCE_CONFLICT.value:
            first.data = {"endpoint": endpoint, "order": order, "attempts": attempts}
            return first
        second = await put()
        attempts.append(_attempt_summary("PUT", second))
        if not second.success:
            second.data = {"endpoint": endpoint, "order": order, "attempts": attempts}
            return second
        second.warnings.append(
            "POST 报告 'Key Already Exist'，已回退到 PUT 更新（对接规范 §11.5.3）。"
        )
        return self._finish_upsert(second, endpoint, attempts, order, validate_after_write)

    async def upsert(
        self, resource: str, data: Any, **kwargs: Any
    ) -> AdapterResult:
        """``upsert`` action name (§18.3) — delegates to :meth:`create_or_update`."""
        return await self.create_or_update(resource, data, **kwargs)

    def _finish_upsert(
        self,
        result: AdapterResult,
        endpoint: str,
        attempts: list[dict[str, Any]],
        order: str,
        validate_after_write: bool,
    ) -> AdapterResult:
        result.data = {
            "endpoint": endpoint,
            "order": order,
            "attempts": attempts,
            "response": result.data,
        }
        if validate_after_write:
            # 对接规范 §11.5.5: 读回形态 ≠ 写入形态，只能比对关键字段是否存在，
            # 不能整体相等（服务端会补默认值并归一化数组长度）。
            result.warnings.append(
                "对接规范 §11.5.5：读回形态 ≠ 写入形态（服务端补默认值、归一化数组长度），"
                "因此 validate_after_write 只能确认「关键字段存在」，不能断言整体相等；"
                "如需读回核对请另行调用 query()。"
            )
        return result

    async def _validate_after_write(
        self, resource: str, keys: Sequence[str]
    ) -> AdapterResult:
        """Read the table back and confirm the written keys exist.

        对接规范 §17.5 第 10 条 / §11.5.5: **禁止用读回结果反推最小写入载荷**；
        校验写入是否生效时比对关键字段，而非整体相等。
        """
        endpoint = normalise_endpoint(resource)
        read = await self._execute(
            "GET", endpoint, root_key=resource_of(endpoint), retry_safe=True
        )
        if not read.success:
            return read
        present = read.data if isinstance(read.data, dict) else {}
        missing = [key for key in keys if str(key) not in {str(k) for k in present}]
        if missing:
            return AdapterResult(
                success=False,
                status=TaskStatus.FAILED.value,
                error_code=ErrorCode.MIDAS_API_ERROR.value,
                error_message=(
                    f"写入后读回校验失败：{endpoint} 中缺少键 {missing}。"
                    "对接规范 §3.5 第 5 条：写操作可能在 HTTP 放弃后仍未落地，"
                    "读回是唯一可靠的判定方式。"
                ),
                raw_status=read.raw_status,
                raw_response=read.raw_response,
                latency_ms=read.latency_ms,
            )
        return AdapterResult.ok(
            {"endpoint": endpoint, "verified_keys": list(keys)},
            warnings=[
                "对接规范 §11.5.5：只比对了键是否存在（读回形态 ≠ 写入形态）。"
            ],
            latency_ms=read.latency_ms,
        )

    # ------------------------------------------------------------------ #
    # §3.5 第 3 / 12 条 — 写前契约
    # ------------------------------------------------------------------ #
    def _apply_write_contract(
        self, endpoint: str, records: dict[str, Any]
    ) -> tuple[dict[str, Any], list[str]]:
        """Alias of :func:`apply_write_contract` (§3.5 第 3 / 12 条)."""
        return apply_write_contract(endpoint, records)

    # ------------------------------------------------------------------ #
    # §11.5.6 — /post/TABLE
    # ------------------------------------------------------------------ #
    async def get_table(
        self,
        table_type: str,
        components: Sequence[str],
        *,
        load_case_names: Sequence[str] | None = None,
        table_name: str | None = None,
        node_elems: dict[str, Any] | None = None,
        unit: dict[str, Any] | None = None,
        styles: dict[str, Any] | None = None,
        opt_cs: bool | None = None,
        stage_step: Sequence[str] | None = None,
        export_path: str | None = None,
        timeout_seconds: int | None = None,
    ) -> AdapterResult:
        """``POST /post/TABLE`` with the four §11.5.6 guards.

        1. ``COMPONENTS`` is **required**: omitting it returns
           ``200 {"message":""}`` — it looks like "no results" but is an
           incomplete request (对接规范 §11.5.6 / V2.1 §17.5 第 11 条).
        2. ``TABLE_NAME`` is set to the caller's value **because the response
           root key is that echo** (对接规范 §11.5.6).
        3. The response is matched **by shape** (the dict carrying ``HEAD`` /
           ``DATA``), never by key name — the root key has been seen as
           ``"Result Table"``, ``"empty"`` and the echoed ``TABLE_NAME``
           (对接规范 §3.5 第 8 条).
        4. ``"empty"`` **can carry a complete table**, so it is never read as
           "no data".
        """
        # §11.5.6 的两条强制参数（与 mock 适配器共用同一守卫，离线测试因此
        # 覆盖的正是实盘所用的那条判断）。
        resolved_name = require_table_components(table_type, components, table_name)
        argument: dict[str, Any] = {
            "TABLE_NAME": resolved_name,  # 响应根键 = 该回显（§11.5.6）
            "TABLE_TYPE": table_type,
            "COMPONENTS": list(components),
        }
        if load_case_names:
            argument["LOAD_CASE_NAMES"] = list(load_case_names)
        if node_elems:
            argument["NODE_ELEMS"] = dict(node_elems)
        if unit:
            argument["UNIT"] = dict(unit)
        if styles:
            argument["STYLES"] = dict(styles)
        if opt_cs is not None:
            argument["OPT_CS"] = bool(opt_cs)
        if stage_step:
            argument["STAGE_STEP"] = list(stage_step)
        if export_path:
            argument["EXPORT_PATH"] = self._guard_local_path(export_path)

        warnings = [
            "对接规范 §3.5 第 8 条：/post/TABLE 顶层响应键不稳定（见过 'Result Table'、"
            "'empty'、以及传入的 TABLE_NAME），且 **'empty' 可以承载一张完整的表**；"
            "因此本方法按形状匹配（找带 HEAD/DATA 的字典），禁止按键名取值。",
            "对接规范 §11.5.6：错误 TABLE_TYPE 返回 400 + 错误体，且错误信息是"
            "**服务端自己截断**的（'...' 不是本平台的显示截断）。",
        ]
        if load_case_names:
            warnings.extend(load_case_suffix_warnings(load_case_names))

        result = await self._execute(
            "POST",
            "/post/TABLE",
            wrapper=WRAPPER_ARGUMENT,
            payload=argument,
            retry_safe=False,
            timeout_seconds=timeout_seconds,
            warnings=warnings,
        )
        if not result.success:
            return result
        table = find_table_shape(result.raw_response)
        if table is None:
            return AdapterResult(
                success=False,
                status=TaskStatus.FAILED.value,
                error_code=ErrorCode.MIDAS_API_ERROR.value,
                error_message=(
                    "响应里找不到带 HEAD/DATA 的表：对接规范 §3.5 第 8 条要求按形状匹配，"
                    f"而实际响应顶层键为 {sorted(result.raw_response) if isinstance(result.raw_response, dict) else type(result.raw_response).__name__}。"
                    "禁止按键名取值。"
                ),
                warnings=list(result.warnings),
                raw_status=result.raw_status,
                raw_response=result.raw_response,
                latency_ms=result.latency_ms,
            )
        found_keys = (
            sorted(result.raw_response) if isinstance(result.raw_response, dict) else []
        )
        if resolved_name not in found_keys:
            # 注意：_execute 已经对 warnings 做了拷贝，因此必须写回 result.warnings，
            # 不能只 append 到本地列表（否则这条提示会静默丢失）。
            result.warnings.append(
                f"响应根键 {found_keys} 与传入的 TABLE_NAME={resolved_name!r} 不一致 —— "
                "对接规范 §3.5 第 8 条已登记该不稳定行为；已按形状匹配取到表，未按键名取值。"
            )
        return AdapterResult.ok(
            table,
            warnings=list(result.warnings),
            raw_status=result.raw_status,
            raw_response=result.raw_response,
            latency_ms=result.latency_ms,
        )

    # ------------------------------------------------------------------ #
    # §3.5 第 4 / 6 / 11 / 13 条 — /doc/* 操作
    # ------------------------------------------------------------------ #
    @staticmethod
    def _guard_local_path(path: Any) -> str:
        """Alias of :func:`guard_local_path` (§3.5 第 6 / 13 条)."""
        return guard_local_path(path)

    async def _doc_call(
        self,
        endpoint: str,
        payload: Any = None,
        *,
        bare_string: bool = False,
        empty_argument: bool = False,
        timeout_seconds: int | None = None,
        extra_warnings: Sequence[str] | None = None,
    ) -> AdapterResult:
        """``POST`` one ``/doc/*`` endpoint.

        ``/doc/*`` 只支持 ``POST`` 且统一用 ``Argument`` 包装（对接规范 §3.1）,
        但路径类参数必须传**裸字符串**（§3.4 末行 / §11.5.2：对象形式会被拒却
        仍返回 200）。 这里同时打开 ``allow_ambiguous_message_success``，因为
        成功时上游唯一返回就是 ``{"message":"... command complete"}``（§11.5.2），
        结果会带上 ``unverified`` 警告强制读回复核。
        """
        if bare_string and payload is not None:
            self._guard_local_path(payload)
        warnings = list(extra_warnings or [])
        warnings.append(
            "对接规范 §11.5.2：/doc/* 成功时上游只回 "
            "{\"message\":\"... command complete\"}，而 §3.5 第 7 条证明同一文案对"
            "「根本没发生的保存」也会出现（/doc/SAVEAS）。本结果因此标记为"
            "**未证实成功**，必须读回模型状态或到 NX 主机上核对文件。"
        )
        return await self._execute(
            "POST",
            endpoint,
            wrapper=WRAPPER_ARGUMENT,
            payload={} if empty_argument else payload,
            retry_safe=False,
            timeout_seconds=timeout_seconds,
            allow_ambiguous_message_success=True,
            warnings=warnings,
        )

    async def doc_export(
        self, path: str, *, timeout_seconds: int | None = None
    ) -> AdapterResult:
        """``POST /doc/EXPORT`` with the **bare string** ``Argument``.

        对接规范 §11.5.2 实机：
        ``{"Argument": {"EXPORT_PATH": p}}`` -> 200 但文件未写出，错误信息伪装成
        路径问题；``{"Argument": p}`` -> 写出 2769 字节。 **只看状态码必然误判。**
        """
        return await self._doc_call(
            "/doc/EXPORT", path, bare_string=True, timeout_seconds=timeout_seconds
        )

    async def doc_import(
        self, path: str, *, timeout_seconds: int | None = None
    ) -> AdapterResult:
        """``POST /doc/IMPORT`` — bare string path (手册 01 章)."""
        return await self._doc_call(
            "/doc/IMPORT", path, bare_string=True, timeout_seconds=timeout_seconds
        )

    async def doc_open(
        self, path: str, *, timeout_seconds: int | None = None
    ) -> AdapterResult:
        """``POST /doc/OPEN`` — bare string path (手册 01 章)."""
        return await self._doc_call(
            "/doc/OPEN", path, bare_string=True, timeout_seconds=timeout_seconds
        )

    async def doc_saveas(
        self, path: str, *, timeout_seconds: int | None = None
    ) -> AdapterResult:
        """``POST /doc/SAVEAS`` — bare string path (§3.5 第 7 条 的假成功案例)."""
        return await self._doc_call(
            "/doc/SAVEAS", path, bare_string=True, timeout_seconds=timeout_seconds
        )

    async def doc_save(
        self, *, confirm: bool = False, timeout_seconds: int | None = None
    ) -> AdapterResult:
        """``POST /doc/SAVE`` — ``{"Argument": {}}``, guarded because it can block.

        **On a document that has never been saved, ``/doc/SAVE`` pops the Save As
        dialog.**  NX has nowhere to write, so it asks the operator — and a modal
        dialog blocks the **entire** API session, not merely this call
        (对接规范 §3.5 第 6 / 13 条).  Measured during the incident that produced
        this guard: while the dialog was open, ``GET /db/UNIT`` **and**
        ``GET /mapikey/verify`` both timed out (curl exit ``000``), and only a
        human at the NX host could clear it.  A test run hung for minutes.

        It therefore takes the same explicit ``confirm=True`` as :meth:`doc_new`.
        A caller that already knows where the file belongs should prefer
        :meth:`doc_saveas` with an explicit path — that form can never need to ask.
        """
        if not confirm:
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR,
                "/doc/SAVE 需要显式 confirm=True：对接规范 §3.5 第 6 条 —— 对**从未"
                "保存过**的文档，上游会弹出「另存为」模态对话框询问路径，而模态"
                "对话框会阻塞**整条 API 会话**（实测：对话框打开期间连 "
                "/mapikey/verify 都超时，只能人工在 NX 主机上关闭）。已知保存路径时"
                "请改用 /doc/SAVEAS 带显式路径，那种形式永远不会弹窗。",
            )
        return await self._doc_call(
            "/doc/SAVE", empty_argument=True, timeout_seconds=timeout_seconds
        )

    async def doc_close(self, *, timeout_seconds: int | None = None) -> AdapterResult:
        """``POST /doc/CLOSE`` — ``{"Argument": {}}`` (手册 01 章)."""
        return await self._doc_call(
            "/doc/CLOSE", empty_argument=True, timeout_seconds=timeout_seconds
        )

    async def doc_new(
        self, *, confirm: bool = False, timeout_seconds: int | None = None
    ) -> AdapterResult:
        """``POST /doc/NEW`` — high risk, guarded twice.

        * 对接规范 §3.5 第 4 条 / V2.1 §25.2: ``/doc/NEW`` **丢弃未保存的工作**，
          包括与本次调用无关的文档 -> 必须显式 ``confirm=True``。
        * 活性探针保留：即使第 11 条的前置条件已被实测推翻（无项目时 ``/doc/NEW``
          正常返回，见 §11.5.12），一次 ``GET /db/UNIT`` 仍是廉价的会话可用性检查
          —— 会话被模态对话框阻塞时它会立刻失败，而不是让我们再挂一次。
        """
        if not confirm:
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR,
                "/doc/NEW 需要显式 confirm=True：对接规范 §3.5 第 4 条 —— 它会"
                "**丢弃未保存的工作**，包括与本次调用无关的文档（高风险操作，"
                "V2.1 §25.2 要求二次确认）。",
            )
        probe = await self.probe_alive()
        if not probe.success:
            return AdapterResult(
                success=False,
                status=TaskStatus.FAILED.value,
                error_code=ErrorCode.CLIENT_NOT_CONNECTED.value,
                error_message=(
                    "拒绝 /doc/NEW：/db/UNIT 活性探针失败 —— 会话不可用"
                    "（被模态对话框阻塞，或实例里没有打开项目，见对接规范 §11.5.12）。"
                ),
                warnings=list(probe.warnings),
                raw_status=probe.raw_status,
                raw_response=probe.raw_response,
                latency_ms=probe.latency_ms,
            )
        return await self._doc_call(
            "/doc/NEW", empty_argument=True, timeout_seconds=timeout_seconds
        )

    async def doc_anal(
        self,
        *,
        pushover: bool = False,
        argument: dict[str, Any] | None = None,
        timeout_seconds: int | None = None,
    ) -> AdapterResult:
        """``POST /doc/ANAL`` — two request bodies (对接规范 §11.5.7).

        * 一般分析：**裸 ``{}``**（不带 ``Argument`` 包装）。
        * 推覆分析：``{"Argument": {"TYPE": "Pushover", ...}}``。

        §11.5.8: ``/doc/ANAL`` 会**真正校验模型**（无边界条件时返回
        ``400 [错误] 边界条件 没有定义。``），所以 ``command complete`` 确实意味着
        求解成功——但它仍不足以证明**结果已落盘**，故沿用未证实标记。
        """
        if pushover:
            body = {"TYPE": "Pushover"}
            if argument:
                body.update(argument)
            return await self._execute(
                "POST",
                "/doc/ANAL",
                wrapper=WRAPPER_ARGUMENT,
                payload=body,
                retry_safe=False,
                timeout_seconds=timeout_seconds,
                allow_ambiguous_message_success=True,
                warnings=[
                    "推覆分析形态：对接规范 §11.5.7 —— {\"Argument\": {\"TYPE\": \"Pushover\"}}。"
                    "注意 V2.1 §17.5 实机补充写作「{\"Argument\": {}} 是推覆分析形态」，"
                    "与 §11.5.7 的原文不一致（见本模块 doc_anal 说明）。"
                ],
            )
        return await self._execute(
            "POST",
            "/doc/ANAL",
            wrapper=None,
            payload=None,
            empty_object_body=True,  # 裸 {}，不是 {"Argument": {}}（§11.5.7）
            retry_safe=False,
            timeout_seconds=timeout_seconds,
            allow_ambiguous_message_success=True,
            warnings=[
                "一般分析形态：对接规范 §11.5.7 —— POST /doc/ANAL 传**裸空对象** {}；"
                "带 Argument 包装会走推覆分析分支。"
            ],
        )

    # ------------------------------------------------------------------ #
    # §17.5 第 8 条 — 写前校验目标实体存在
    # ------------------------------------------------------------------ #
    async def ensure_entity_exists(
        self, resource: str, outer_key: Any, *, timeout_seconds: int | None = None
    ) -> AdapterResult:
        """Confirm the entity addressed by ``outer_key`` exists.

        V2.1 §17.5 第 8 条 / 对接规范 §4.1: 「写入前**校验目标实体存在**」——
        这是 CNLD 类误用的第二道防线（第一道在 :func:`build_assign`）。
        """
        endpoint = normalise_endpoint(resource)
        kind = validate_assign_outer_key(endpoint, outer_key)
        read = await self._execute(
            "GET",
            endpoint,
            root_key=resource_of(endpoint),
            retry_safe=True,
            timeout_seconds=timeout_seconds,
        )
        if not read.success:
            return read
        present = read.data if isinstance(read.data, dict) else {}
        keys = {str(k) for k in present}
        if str(outer_key) not in keys:
            return AdapterResult(
                success=False,
                status=TaskStatus.FAILED.value,
                error_code=ErrorCode.RESOURCE_NOT_FOUND.value,
                error_message=(
                    f"{endpoint} 中不存在 {kind} {outer_key}（对接规范 §4.1 / "
                    "V2.1 §17.5 第 8 条：写入前必须校验目标实体存在，否则荷载/属性会"
                    "静默落到错误对象上，分析仍返回 command complete）。"
                ),
                raw_status=read.raw_status,
                raw_response=read.raw_response,
                latency_ms=read.latency_ms,
            )
        return AdapterResult.ok(
            {"endpoint": endpoint, "kind": kind, "outer_key": str(outer_key)},
            latency_ms=read.latency_ms,
        )

    # ------------------------------------------------------------------ #
    # V2.1 §13 — query / model / execute
    # ------------------------------------------------------------------ #
    async def query(self, request: QueryRequest) -> AdapterResult:
        """``midas_query`` entry point (§7)."""
        target = (request.target or "").strip()
        lowered = target.lower()
        if lowered in ("server", "health", "connection"):
            return await self.check_channel()
        if lowered in ("client", "client_info"):
            return AdapterResult.ok(
                {
                    "name": self._connection.name,
                    "code": self.code,
                    "software": self._connection.software,
                    "product": self._connection.product.value,
                    "base_url": self._connection.base_url,
                    "db_url": self._connection.db_url,
                    "verify_url": self._connection.verify_url,
                    "api_key": self._connection.masked_key,  # 总纲 §4.7.2 回显规范
                    "timeout_seconds": self._connection.timeout_seconds,
                    "max_concurrency": self._connection.max_concurrency,
                    "lifecycle": self._lifecycle.value,
                }
            )
        if lowered in ("capabilities", "capability"):
            metadata = await self.metadata()
            return AdapterResult.ok(
                {"metadata": metadata.to_db_payload(), "capabilities": [
                    {"code": capability.code, "resource": capability.resource,
                     "action": capability.action}
                    for capability in CAPABILITIES
                ]}
            )
        if request.action == "inspect":
            return await self.introspect(target)
        return await self._read_records(
            target,
            query=request.query,
            page=request.page,
            page_size=request.page_size,
            timeout_seconds=request.timeout_seconds,
        )

    async def _read_records(
        self,
        resource: str,
        *,
        query: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 100,
        timeout_seconds: int | None = None,
    ) -> AdapterResult:
        """``GET /db/<RES>`` -> ``{id: record}`` -> filtered, paginated list.

        MIDAS has no server-side filtering, so filters and pagination run here
        (§17.3 unwrap -> 形态 3/4).  ``{"message": ""}`` is an **empty table**,
        not an error (对接规范 §3.2.1).
        """
        endpoint = normalise_endpoint(resource)
        result = await self._execute(
            "GET",
            endpoint,
            root_key=resource_of(endpoint),
            retry_safe=True,  # 读操作可以重试；写操作不可以（§26.5）
            timeout_seconds=timeout_seconds,
        )
        if not result.success:
            return result
        raw_records = result.data if isinstance(result.data, dict) else {}
        items: list[dict[str, Any]] = []
        for key, value in raw_records.items():
            record = dict(value) if isinstance(value, dict) else {"value": value}
            record.setdefault("id", key)
            items.append(record)
        filtered, filter_warnings = apply_query(items, query)
        warnings = list(result.warnings) + filter_warnings
        size = max(1, min(int(page_size or 100), 500))
        if page_size and size != page_size:
            warnings.append("page_size 已被裁剪到 1–500（V2.1 §18.3）。")
        current = max(1, int(page or 1))
        start = (current - 1) * size
        window = filtered[start : start + size]
        return AdapterResult.ok(
            {
                "resource": resource_of(endpoint),
                "endpoint": endpoint,
                "total": len(filtered),
                "page": current,
                "page_size": size,
                "items": window,
            },
            warnings=warnings,
            raw_status=result.raw_status,
            raw_response=result.raw_response,
            latency_ms=result.latency_ms,
        )

    async def model(self, request: ModelRequest) -> AdapterResult:
        """``midas_model`` entry point (§8 / §25.1)."""
        endpoint = normalise_endpoint(request.resource)
        action = (request.action or "").lower()
        options = dict(request.options or {})
        timeout = options.get("timeout_seconds", request.timeout_seconds)

        if action in ("read", "list", "get"):
            raw_query = options.get("query")
            return await self._read_records(
                endpoint,
                query=raw_query if isinstance(raw_query, dict) else None,
                timeout_seconds=timeout,
            )

        if action == "delete":
            ids: Any = request.data
            if isinstance(request.data, dict):
                ids = request.data.get("ids", request.data)
            return await self.delete(endpoint, ids, timeout_seconds=timeout)

        if action == "validate":
            records = coerce_assign_records(endpoint, request.data)
            resolved, contract_warnings = self._apply_write_contract(endpoint, records)
            body = build_assign_body(endpoint, resolved)
            return AdapterResult.ok(
                {
                    "endpoint": endpoint,
                    "valid": True,
                    "dry_run": True,
                    "body": {WRAPPER_ASSIGN: body},
                },
                warnings=contract_warnings
                + [
                    "对接规范 §3.5 第 12 条：字段值本身无法离线校验（Wrong Field 通常"
                    "意味着值错而不是字段名错，§3.5 第 10 条）；如需字段名核对请调用 "
                    "introspect()。"
                ],
            )

        if action in ("create", "update", "upsert"):
            if action == "upsert":
                return await self.create_or_update(
                    endpoint,
                    request.data,
                    timeout_seconds=timeout,
                    validate_after_write=bool(options.get("validate_after_write")),
                )
            records = coerce_assign_records(endpoint, request.data)
            resolved, contract_warnings = self._apply_write_contract(endpoint, records)
            body = build_assign_body(endpoint, resolved)
            warnings = contract_warnings + [
                "对接规范 §3.5 第 5 条 / V2.1 §26.5：写操作**禁止自动重试**——"
                "超时 ≠ 回滚，超时后必须先读回模型状态。",
            ]
            if options.get("transactional"):
                warnings.append(
                    "对接规范 §3.5 第 5 条 / V2.1 §25.3：MIDAS 侧没有事务，"
                    "transactional 只能由平台用 task_events + system_logs 做补偿追踪，"
                    "适配器不提供回滚语义。"
                )
            if endpoint in NEW_FILE_GET_PUT_ONLY and action == "create":
                warnings.append(
                    f"对接规范 §3.3：{endpoint} 属于「新文件必需数据」，"
                    "**POST 不生效**，只能用 GET/PUT——create 请改用 upsert/PUT。"
                )
            if options.get("dry_run"):
                return AdapterResult.ok(
                    {
                        "endpoint": endpoint,
                        "dry_run": True,
                        "body": {WRAPPER_ASSIGN: body},
                    },
                    warnings=warnings,
                )
            method = "POST" if action == "create" else "PUT"
            result = await self._execute(
                method,
                endpoint,
                wrapper=WRAPPER_ASSIGN,
                payload=body,
                retry_safe=False,
                timeout_seconds=timeout,
                warnings=warnings,
            )
            if result.success and options.get("validate_after_write"):
                check = await self._validate_after_write(endpoint, list(resolved))
                result.warnings.extend(check.warnings)
                if not check.success:
                    result.warnings.append(
                        f"写入后读回校验未通过：{check.error_message}"
                    )
            return result

        raise AdapterError(
            ErrorCode.CAPABILITY_NOT_SUPPORTED,
            f"midas_model action={request.action!r} 不受支持；"
            "合法取值：create / read / update / delete / upsert / validate（V2.1 §18.3）。",
            details={"action": request.action, "endpoint": endpoint},
        )

    async def execute(self, request: ExecuteRequest) -> AdapterResult:
        """``midas_execute`` entry point (§9)."""
        action = (request.action or "").lower()
        options = dict(request.options or {})
        timeout = options.get("timeout_seconds", request.timeout_seconds)
        data = dict(request.data or {})

        if action in ("connect", "verify", "health"):
            # 对接规范 §11.5.13：connect 是唯一「本来就要摸主机、又不碰文档」的秒级
            # 动作（tool_interfaces: server.connect 的 task_type 为 NULL），因此它是
            # 暴露会话判定**零新增能力行**的位置（V2.1 §16.1）。
            return await self._connect_with_diagnosis()
        if action == "disconnect":
            return await self.disconnect()
        if action == "probe":
            return await self.probe_alive()
        if action == "check_channel":
            return await self.check_channel()
        if action == "introspect":
            return await self.introspect(str(data.get("resource") or request.resource or ""))
        if action in ("new", "doc_new"):
            return await self.doc_new(
                confirm=bool(data.get("confirm") or options.get("confirm")),
                timeout_seconds=timeout,
            )
        if action == "open":
            return await self.doc_open(str(data.get("path") or ""), timeout_seconds=timeout)
        if action == "save":
            return await self.doc_save(
                confirm=bool(data.get("confirm") or options.get("confirm")),
                timeout_seconds=timeout,
            )
        if action in ("saveas", "save_as"):
            return await self.doc_saveas(
                str(data.get("path") or ""), timeout_seconds=timeout
            )
        if action == "close":
            return await self.doc_close(timeout_seconds=timeout)
        if action == "import":
            return await self.doc_import(
                str(data.get("path") or ""), timeout_seconds=timeout
            )
        if action == "export":
            return await self.doc_export(
                str(data.get("path") or ""), timeout_seconds=timeout
            )
        if action in ("calculate", "analysis", "anal", "run_analysis"):
            return await self.doc_anal(
                pushover=bool(data.get("pushover") or data.get("TYPE") == "Pushover"),
                argument=data.get("argument") if isinstance(data.get("argument"), dict) else None,
                timeout_seconds=timeout,
            )
        if action in ("table", "result_table", "get_table"):
            return await self.get_table(
                str(data.get("table_type") or ""),
                data.get("components") or [],
                load_case_names=data.get("load_case_names"),
                table_name=data.get("table_name"),
                node_elems=data.get("node_elems"),
                unit=data.get("unit"),
                styles=data.get("styles"),
                opt_cs=data.get("opt_cs"),
                stage_step=data.get("stage_step"),
                export_path=data.get("export_path"),
                timeout_seconds=timeout,
            )
        if action == "raw":
            return await self._raw_call(data, timeout_seconds=timeout)

        raise AdapterError(
            ErrorCode.CAPABILITY_NOT_SUPPORTED,
            f"midas_execute action={request.action!r} 不受支持；"
            "合法取值：connect / disconnect / probe / check_channel / introspect / "
            "new / open / save / saveas / close / import / export / calculate / "
            "table / raw（V2.1 §18.3）。",
            details={"action": request.action},
        )

    async def _raw_call(
        self, data: dict[str, Any], *, timeout_seconds: int | None = None
    ) -> AdapterResult:
        """Escape hatch for an endpoint without a helper — **guards still apply**.

        ``data``: ``{"method", "endpoint", "wrapper", "body", "root_key"}``.
        The §11.5.1 DELETE guard, the ``/db/NMAS`` backfill and the
        ``/db/PRES`` mandate are enforced here too, so this cannot be used to
        bypass them.
        """
        method = str(data.get("method") or "GET").upper()
        endpoint = normalise_endpoint(str(data.get("endpoint") or ""))
        wrapper = data.get("wrapper")
        body = data.get("body")
        warnings: list[str] = [
            "raw 通道：调用方直接指定端点，适配器仍强制执行 DELETE 守卫、"
            "/db/NMAS 必填兜底与 /db/PRES DIRECTION 强制（对接规范 §3.5）。"
        ]
        if method == "DELETE":
            if wrapper == WRAPPER_ASSIGN or isinstance(body, dict):
                # 只允许 /db/XXX/<id> 形式
                self.delete_using_assign_body(endpoint, body)
        if method in ("POST", "PUT") and isinstance(body, dict):
            inner = body.get(WRAPPER_ASSIGN, body)
            if isinstance(inner, dict):
                inner, contract_warnings = self._apply_write_contract(endpoint, inner)
                warnings.extend(contract_warnings)
                body = {WRAPPER_ASSIGN: inner} if wrapper else inner
        if method == "POST" and endpoint in HIGH_RISK_ENDPOINTS and not data.get("confirm"):
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR,
                f"{endpoint} 属于高风险端点，raw 通道也需要 confirm=True"
                "（V2.1 §25.2 / 对接规范 §3.5 第 4 条）。",
            )
        return await self._execute(
            method,
            endpoint,
            wrapper=wrapper,
            payload=body,
            root_key=data.get("root_key"),
            retry_safe=method in ("GET", "HEAD"),
            timeout_seconds=timeout_seconds,
            omit_body=method in ("GET", "HEAD", "DELETE") and body is None,
            allow_ambiguous_message_success=bool(data.get("ambiguous_ok")),
            warnings=warnings,
        )

    # ------------------------------------------------------------------ #
    # V2.1 §13 — task members
    # ------------------------------------------------------------------ #
    async def get_task(self, task_id: str) -> AdapterResult:
        """Not an upstream concept — MIDAS has no task API.

        对接规范 §2.5.1: 对 ``MIDAS-API-main`` 全文检索 ``동시 / concurrent /
        multi-user / queue`` 的 94 处命中全部是结构工程概念，**没有一处是关于 API
        并发、多用户或调用配额的**；因此 MIDAS 不提供任务查询。异步任务由平台
        Task Engine 承担（V2.1 §26）。
        """
        return AdapterResult(
            success=False,
            status=TaskStatus.FAILED.value,
            error_code=ErrorCode.NOT_IMPLEMENTED.value,
            error_message=(
                f"MIDAS NX Open API 没有任务端点，get_task({task_id!r}) 无上游可查"
                "（对接规范 §2.5.1）。异步语义由平台 Task Engine 提供（V2.1 §26），"
                "任务状态请查 tasks 表。"
            ),
        )

    async def cancel_task(self, task_id: str) -> AdapterResult:
        """See :meth:`get_task` — no upstream task API (对接规范 §2.5.1)."""
        return AdapterResult(
            success=False,
            status=TaskStatus.FAILED.value,
            error_code=ErrorCode.NOT_IMPLEMENTED.value,
            error_message=(
                f"MIDAS NX Open API 没有任务端点，cancel_task({task_id!r}) 无上游可调；"
                "取消语义由平台 Task Engine 承担（V2.1 §26 / §26.5：写任务超时一律置 "
                "failed 并等人工判定，不得自动重投）。"
            ),
        )

    async def retry_task(self, task_id: str) -> AdapterResult:
        """See :meth:`get_task` — and §26.5 forbids auto-retrying writes."""
        return AdapterResult(
            success=False,
            status=TaskStatus.FAILED.value,
            error_code=ErrorCode.NOT_IMPLEMENTED.value,
            error_message=(
                f"MIDAS NX Open API 没有任务端点，retry_task({task_id!r}) 无上游可调；"
                "V2.1 §26.5：写类任务超时一律置 failed 并等待人工判定，"
                "**不得**由 Task Engine 自动重投（对接规范 §3.5 第 5 条：超时 ≠ 回滚）。"
            ),
        )

    # ------------------------------------------------------------------ #
    # §4.1 — instance helpers mirroring the module-level guards
    # ------------------------------------------------------------------ #
    def build_assign(
        self,
        outer_key: Any,
        inner: Any,
        *,
        resource: str | None = None,
        kind: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Instance-level alias of :func:`build_assign` (guards included)."""
        return build_assign(outer_key, inner, resource=resource, kind=kind)

    @staticmethod
    def outer_key_means(resource: str) -> str:
        """Instance-level alias of :func:`outer_key_means`."""
        return outer_key_means(resource)


def wrap_payload(payload: Any, wrapper: str | None) -> dict[str, Any]:
    """``request_wrapper`` -> ``{"Assign": ...}`` / ``{"Argument": ...}``.

    * ``None`` wrapper = 端点不接收请求体 (§17.3) -> ``{}``; the caller decides
      whether to send nothing at all or a bare ``{}`` (``/doc/ANAL`` needs the
      bare ``{}``, 对接规范 §11.5.7).
    * A **bare string** payload is legal and required by ``/doc/EXPORT``,
      ``/doc/SAVEAS``, ``/doc/OPEN``, ``/doc/IMPORT`` … — passing an object there
      is rejected by upstream while still answering **200**
      (对接规范 §3.4 末行 / §11.5.2).

    Module-level so the mock adapter runs the *same* code (V2.1 §17.3).
    """
    if wrapper is None:
        return {}
    if wrapper not in (WRAPPER_ASSIGN, WRAPPER_ARGUMENT):
        raise AdapterError(
            ErrorCode.VALIDATION_ERROR,
            f"未知的 request_wrapper={wrapper!r}；合法取值：'Assign' / 'Argument' / None"
            "（V2.1 §17.3 / 对接规范 §3.1）",
        )
    if payload is None:
        return {wrapper: {}}
    if isinstance(payload, (dict, list, str, int, float, bool)):
        return {wrapper: payload}
    raise AdapterError(
        ErrorCode.VALIDATION_ERROR,
        f"payload 必须是 JSON 可序列化的对象/数组/标量，收到 {type(payload).__name__}",
    )


def unwrap_response(response: Any, root_key: str | None) -> Any:
    """V2.1 §17.3, branch for branch.

    ``GET /db/*`` has exactly three shapes (对接规范 §3.2.1) and **the empty
    table is ``{"message": ""}``, not ``{"NODE": {}}``**, so a bare
    ``response[root_key]`` raises ``KeyError`` on an empty model.  That is why
    this function never indexes before shape-matching.

    Text-pattern matching is **not** performed here: it is the third, fallback
    layer of :func:`app.adapters.errors.normalize_upstream` and must never be the
    sole judge (V2.1 §20.4).  Module-level so the mock adapter runs the *same*
    code.
    """
    # 1) 结构化失败信号优先 —— HTTP 可能是 200 **也可能是 201**（§3.5 第 2 条）
    if isinstance(response, dict) and "error" in response:
        raise normalize_upstream(payload=response).as_error()
    # 2) {"message": ""} = 成功且表为空；非空 message = 失败（§3.2.1 / §3.5 第 7 条）
    if isinstance(response, dict) and "message" in response:
        message = response["message"]
        text = message if isinstance(message, str) else str(message)
        if text.strip():
            raise normalize_upstream(payload=response).as_error()
        return {}
    # 3) 正常取数据
    #    根键按**大小写不敏感**匹配。MIDAS 路径大小写不敏感（实机验证：
    #    /db/NODE、/db/node、/db/nOdE 均 200），但响应根键**始终是规范的大写
    #    资源名**；而 tool_interfaces.endpoint 可能是任意大小写，
    #    直接 `root_key in response` 会失配，进而错误地落到分支 4。
    if root_key and isinstance(response, dict):
        if root_key in response:
            return response[root_key]
        wanted = root_key.strip().lower()
        matches = [
            value
            for key, value in response.items()
            if isinstance(key, str) and key.strip().lower() == wanted
        ]
        if len(matches) == 1:
            return matches[0]
    # 4) 无根键端点，原样返回
    return response


def apply_query(
    items: list[dict[str, Any]], query: dict[str, Any] | None
) -> tuple[list[dict[str, Any]], list[str]]:
    """Apply MCP-side filters (MIDAS has no server-side filtering).

    Supported: ``ids`` / ``id`` (membership), ``<field>_min`` / ``<field>_max``
    (numeric range), anything else = case-insensitive equality.  Field names are
    matched case-insensitively because MIDAS returns UPPER-CASE keys while the
    MCP layer speaks lower-case canonical names (V2.1 §17.2).
    """
    warnings: list[str] = []
    if not query:
        return items, warnings
    result = items
    for field_name, expected in query.items():
        if expected is None:
            continue
        key = str(field_name)
        if key in ("ids", "id"):
            wanted = expected if isinstance(expected, (list, tuple, set)) else [expected]
            wanted_set = {str(value) for value in wanted}
            result = [item for item in result if str(item.get("id")) in wanted_set]
            continue
        operator = "eq"
        column = key
        if key.endswith("_min"):
            operator, column = "ge", key[: -len("_min")]
        elif key.endswith("_max"):
            operator, column = "le", key[: -len("_max")]
        upper = column.upper()
        filtered: list[dict[str, Any]] = []
        for item in result:
            lookup = {str(k).upper(): v for k, v in item.items()}
            if upper not in lookup:
                continue
            actual = lookup[upper]
            if operator == "eq":
                if _loose_equal(actual, expected):
                    filtered.append(item)
            elif isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
                if (operator == "ge" and actual >= expected) or (
                    operator == "le" and actual <= expected
                ):
                    filtered.append(item)
        result = filtered
    if not result and items:
        warnings.append(
            f"过滤条件 {sorted(query)} 在 {len(items)} 条记录上得到 0 条 —— MIDAS 没有"
            "服务端过滤（§2.5.1：官方文档未定义 API 层的查询/过滤能力），过滤在本适配器"
            "内完成，因此字段名拼错会**静默过滤掉全部记录**；请先用 query(action='list') "
            "确认字段名（大小写不敏感匹配 MIDAS 的大写键，V2.1 §17.2）。"
        )
    return result, warnings


def _loose_equal(actual: Any, expected: Any) -> bool:
    if isinstance(actual, str) and isinstance(expected, str):
        return actual.strip().lower() == expected.strip().lower()
    if isinstance(actual, bool) or isinstance(expected, bool):
        return bool(actual) is bool(expected)
    return actual == expected or str(actual) == str(expected)


def _is_id_addressed(endpoint: str) -> bool:
    """True for ``/db/RES/<id>`` style endpoints (per-id addressing)."""
    parts = [part for part in endpoint.split("/") if part]
    return len(parts) >= 3 and parts[-1].isdigit()


def _attempt_summary(method: str, result: AdapterResult) -> dict[str, Any]:
    """Compact attempt record for an upsert's ``data.attempts``."""
    return {
        "method": method,
        "success": result.success,
        "error_code": result.error_code,
        "error_message": result.error_message,
        "raw_status": result.raw_status,
        "latency_ms": result.latency_ms,
    }


#: §22 names one adapter per product; the product is a config field, so one class
#: serves both and the aliases exist purely for readability at call sites.
MidasGenAdapter = MidasNxAdapter
MidasCivilAdapter = MidasNxAdapter
