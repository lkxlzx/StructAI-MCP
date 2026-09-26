"""Closed enums, ID prefixes and permission codes.

Single source of truth: 《StructAI 架构边界与融合规范 v1.0（总纲）》
  * §4.1.3  ID prefix list (closed set)
  * §4.2    state word lists (closed set) — V2.1 §4 only *references* them
  * §4.8.2  permission code list (closed set, 34 codes)
  * §4.8.3  default role -> permission mapping

V2.1 §26.2 owns ``tasks.type`` (14 business task types) and is reproduced here
because the ORM CHECK constraint must stay in sync with the DDL.

Nothing in this module imports SQLAlchemy: the SQL fragment builders return plain
strings so that the same enums can serve ORM models, Pydantic schemas and
migration scripts alike.
"""

from enum import Enum
from typing import Iterable

__all__ = [
    "TaskStatus",
    "TaskType",
    "PlanStatus",
    "PlanStepStatus",
    "SessionStatus",
    "ProjectStatus",
    "RiskLevel",
    "MessageRole",
    "FilePurpose",
    "OutputType",
    "HistoryType",
    "ReportType",
    "ReportStatus",
    "DrawingTaskStatus",
    "CodeCategory",
    "ClauseSeverity",
    "LoadParameterType",
    "UserStatus",
    "MidasClientStatus",
    "McpServerStatus",
    "McpClientStatus",
    "AdapterStatus",
    "AiModelStatus",
    "JobStatus",
    "ValueType",
    "ID_PREFIXES",
    "PERMISSIONS",
    "ROLE_DEFINITIONS",
    "ROLE_PERMISSION_MAP",
    "enum_values",
    "sql_value_list",
    "check_sql",
    "expand_permission_patterns",
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def enum_values(enum_cls: type[Enum]) -> tuple[str, ...]:
    """Return the member values of a ``str``-Enum as an ordered tuple."""
    return tuple(str(member.value) for member in enum_cls)


def sql_value_list(enum_cls: type[Enum]) -> str:
    """Render the enum values as a SQL literal list: ``'a', 'b', 'c'``."""
    return ", ".join("'%s'" % value for value in enum_values(enum_cls))


def check_sql(column: str, enum_cls: type[Enum]) -> str:
    """Build the CHECK body for a state column, e.g. ``status IN ('queued', ...)``.

    V2.1 §4 requires a CHECK on every state column (裁决 B-10); building the SQL
    from the enum keeps the DDL and the ORM from drifting apart.
    """
    return f"{column} IN ({sql_value_list(enum_cls)})"


def expand_permission_patterns(
    patterns: Iterable[str], available: Iterable[str]
) -> list[str]:
    """Expand the §4.8.3 role patterns against the §4.8.2 permission list.

    ``"*"``      -> every permission
    ``"model:*"``-> every permission whose code starts with ``"model:"``
    ``"x:y"``    -> that exact code (ignored when unknown)
    """
    known = list(available)
    expanded: list[str] = []
    for pattern in patterns:
        if pattern == "*":
            matched = list(known)
        elif pattern.endswith(":*"):
            prefix = pattern[:-1]  # keep the trailing ':'
            matched = [code for code in known if code.startswith(prefix)]
        else:
            matched = [pattern] if pattern in known else []
        for code in matched:
            if code not in expanded:
                expanded.append(code)
    return expanded


# ---------------------------------------------------------------------------
# 总纲 §4.2.1 — tasks.status
# ---------------------------------------------------------------------------
class TaskStatus(str, Enum):
    """Task lifecycle states (总纲 §4.2.1, MCP ``midas_task`` uses the same list)."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


TASK_STATUS_VALUES = enum_values(TaskStatus)


# ---------------------------------------------------------------------------
# V2.1 §26.2 — tasks.type (裁决 A-6), 14 closed values
# ---------------------------------------------------------------------------
class TaskType(str, Enum):
    """Business task type stored in ``tasks.type`` (V2.1 §26.2, 14 values)."""

    CALCULATE = "calculate"
    ANALYSIS = "analysis"
    REPORT = "report"
    EXPORT = "export"
    IMPORT = "import"
    BACKUP = "backup"
    RESTORE = "restore"
    CLEANUP = "cleanup"
    DRAWING_RECOGNIZE = "drawing_recognize"
    MODEL_IMPORT = "model_import"
    OPTIMIZATION = "optimization"
    CODE_CHECK = "code_check"
    LOAD_GENERATE = "load_generate"
    AI_PLAN_EXECUTE = "ai_plan_execute"


TASK_TYPE_VALUES = enum_values(TaskType)


# ---------------------------------------------------------------------------
# 总纲 §4.2.2 — assistant_plans.status
# ---------------------------------------------------------------------------
class PlanStatus(str, Enum):
    """Execution plan states (总纲 §4.2.2, 10 values)."""

    DRAFT = "draft"
    VALIDATING = "validating"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


PLAN_STATUS_VALUES = enum_values(PlanStatus)


# ---------------------------------------------------------------------------
# 总纲 §4.2.3 — assistant_plan_steps.status
# ---------------------------------------------------------------------------
class PlanStepStatus(str, Enum):
    """Plan step states (总纲 §4.2.3)."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


PLAN_STEP_STATUS_VALUES = enum_values(PlanStepStatus)


# ---------------------------------------------------------------------------
# 总纲 §4.2.4 / §4.2.8 — active / archived
# ---------------------------------------------------------------------------
class SessionStatus(str, Enum):
    """``assistant_sessions.status`` (总纲 §4.2.4)."""

    ACTIVE = "active"
    ARCHIVED = "archived"


SESSION_STATUS_VALUES = enum_values(SessionStatus)


class ProjectStatus(str, Enum):
    """``projects.status`` (总纲 §4.2.8, same word list as §4.2.4)."""

    ACTIVE = "active"
    ARCHIVED = "archived"


PROJECT_STATUS_VALUES = enum_values(ProjectStatus)


# ---------------------------------------------------------------------------
# 总纲 §4.2.9 — AI module auxiliary enums
# ---------------------------------------------------------------------------
class RiskLevel(str, Enum):
    """``assistant_plans.risk_level`` (总纲 §4.2.9)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


RISK_LEVEL_VALUES = enum_values(RiskLevel)


class MessageRole(str, Enum):
    """``assistant_messages.role`` (总纲 §4.2.9)."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


MESSAGE_ROLE_VALUES = enum_values(MessageRole)


class FilePurpose(str, Enum):
    """``assistant_files.purpose`` (总纲 §4.2.9)."""

    UPLOAD = "upload"
    OUTPUT = "output"
    TEMP = "temp"


FILE_PURPOSE_VALUES = enum_values(FilePurpose)


class OutputType(str, Enum):
    """``assistant_outputs.output_type`` (总纲 §4.2.9)."""

    REPORT = "report"
    DRAWING = "drawing"
    MODEL_FILE = "model_file"
    RESULT = "result"


OUTPUT_TYPE_VALUES = enum_values(OutputType)


class HistoryType(str, Enum):
    """``assistant_history.type`` (总纲 §4.2.9)."""

    CHAT = "chat"
    INTENT = "intent"
    PLAN = "plan"
    EXECUTE = "execute"
    DRAWING = "drawing"
    REPORT = "report"


HISTORY_TYPE_VALUES = enum_values(HistoryType)


class ReportType(str, Enum):
    """``reports.report_type`` (总纲 §4.2.9)."""

    CALCULATION = "calculation"
    ANALYSIS = "analysis"
    DESIGN = "design"
    CHECK = "check"
    CUSTOM = "custom"


REPORT_TYPE_VALUES = enum_values(ReportType)


class ReportStatus(str, Enum):
    """``reports.status`` (总纲 §4.2.9, aligned with backups/exports/imports)."""

    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


REPORT_STATUS_VALUES = enum_values(ReportStatus)


# ---------------------------------------------------------------------------
# 总纲 §4.2.7 — assistant_drawing_tasks.status
# ---------------------------------------------------------------------------
class DrawingTaskStatus(str, Enum):
    """Drawing recognition task states (总纲 §4.2.7, subset of §4.2.1)."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


DRAWING_TASK_STATUS_VALUES = enum_values(DrawingTaskStatus)


# ---------------------------------------------------------------------------
# 总纲 §4.2.10 — code standard / load parameter enums
# ---------------------------------------------------------------------------
class CodeCategory(str, Enum):
    """``code_standards.category`` (总纲 §4.2.10)."""

    NATIONAL = "national"
    INDUSTRY = "industry"
    LOCAL = "local"
    ENTERPRISE = "enterprise"
    INTERNATIONAL = "international"


CODE_CATEGORY_VALUES = enum_values(CodeCategory)


class ClauseSeverity(str, Enum):
    """``code_clauses.severity`` (总纲 §4.2.10)."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


CLAUSE_SEVERITY_VALUES = enum_values(ClauseSeverity)


class LoadParameterType(str, Enum):
    """``load_parameter_library.parameter_type`` (总纲 §4.2.10)."""

    WIND = "wind"
    SNOW = "snow"
    SEISMIC = "seismic"
    TEMPERATURE = "temperature"
    LIVE = "live"
    DEAD = "dead"
    CRANE = "crane"


LOAD_PARAMETER_TYPE_VALUES = enum_values(LoadParameterType)


# ---------------------------------------------------------------------------
# 总纲 §4.2.5 — other existing state columns
# ---------------------------------------------------------------------------
class UserStatus(str, Enum):
    """``users.status`` (总纲 §4.2.5)."""

    ENABLED = "enabled"
    DISABLED = "disabled"
    LOCKED = "locked"


USER_STATUS_VALUES = enum_values(UserStatus)


class MidasClientStatus(str, Enum):
    """``midas_clients.status`` (总纲 §4.2.5)."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


MIDAS_CLIENT_STATUS_VALUES = enum_values(MidasClientStatus)


class MidasVisibility(str, Enum):
    """``midas_clients.visibility`` — instance-level visibility scope.

    The platform is shared by several departments over a LAN and each registers
    its own MIDAS instance, so a registration needs an owner and a scope
    (《MIDAS API 对接规范》§2.5.4 item 5). This gate applies **in addition to**
    the ``assistant:*`` / ``tool:*`` permission checks, never instead of them.
    """

    PRIVATE = "private"
    DEPARTMENT = "department"
    PUBLIC = "public"


MIDAS_VISIBILITY_VALUES = enum_values(MidasVisibility)


class MidasProductScope(str, Enum):
    """``tool_interfaces.product_scope`` — which MIDAS product an endpoint serves.

    Three-layer classification, layer 1 (总纲 §4.2.12 / 对接规范 §7.1).  The
    frontend filters by it and capability resolution consults it on **every**
    call, which is why it is a column rather than a ``metadata_json`` field.

    ``UNKNOWN`` is the shipped default and is a **first-class state**, not a
    placeholder.  The manuals' product labels cannot be trusted — 对接规范 §3.5
    第 15 条 measured that of 47 endpoints declared "Civil-only", **32 answer on
    Gen NX as well**.  So an endpoint is ``unknown`` until a live instance says
    otherwise, and ``unknown`` capabilities are admitted **optimistically** with
    an ``unverified`` warning rather than hidden.
    """

    GEN = "gen"
    CIVIL = "civil"
    DESIGNER = "designer"
    BOTH = "both"
    UNKNOWN = "unknown"


MIDAS_PRODUCT_SCOPE_VALUES = enum_values(MidasProductScope)


#: ``MidasProduct`` value (the **URL segment**) → ``MidasProductScope`` value.
#:
#: The two enums are not the same axis, which is why this exists rather than a
#: shared enum:
#:
#: * :class:`app.core.midas_config.MidasProduct` is a **wire detail** — the path
#:   segment MIDAS serves the product on, so Civil Designer is ``cdn``.
#: * :class:`MidasProductScope` is a **capability classification** — read by the
#:   frontend to build menus, so Civil Designer is ``designer``.
#:
#: ``gen`` and ``civil`` happen to agree; only Designer differs. Keeping the map
#: explicit means a future product cannot be added on one side and silently
#: missing on the other.
PRODUCT_SCOPE_BY_PRODUCT: dict[str, str] = {
    "gen": MidasProductScope.GEN.value,
    "civil": MidasProductScope.CIVIL.value,
    "cdn": MidasProductScope.DESIGNER.value,
}


class CapabilityDomain(str, Enum):
    """``tool_interfaces.domain`` — business domain, classification layer 2.

    Eight values, merged from the 27 manual chapters.  It is the frontend's
    first-level menu and the LLM's **first** filter: choosing among 8 is trivial
    where choosing among ~683 endpoints is not.
    """

    PROJECT = "project"
    MODEL = "model"
    LOAD = "load"
    ANALYSIS = "analysis"
    RESULT = "result"
    DESIGN = "design"
    VIEW = "view"
    OPERATION = "operation"


CAPABILITY_DOMAIN_VALUES = enum_values(CapabilityDomain)


class CapabilityFeature(str, Enum):
    """``tool_interfaces.feature`` — manual chapter, classification layer 3.

    27 values, one per chapter of the MIDAS API manual set (``G:\\MAPI``'s
    ``api_chapters/01..27``).  The frontend's second-level menu and the LLM's
    **second** filter.
    """

    DOC = "doc"
    DB_PROJECT_STRUCTURE = "db_project_structure"
    DB_NODE_ELEMENT = "db_node_element"
    DB_PROPERTIES = "db_properties"
    DB_BOUNDARY = "db_boundary"
    DB_STATIC_LOADS = "db_static_loads"
    DB_TEMPERATURE_PRESTRESS = "db_temperature_prestress"
    DB_MOVING_LOADS = "db_moving_loads"
    DB_DYNAMIC_LOADS = "db_dynamic_loads"
    DB_CONSTRUCTION_STAGE = "db_construction_stage"
    DB_SETTLEMENT_MISC_LOADS = "db_settlement_misc_loads"
    DB_ANALYSIS_CONTROL = "db_analysis_control"
    DB_LOAD_COMBINATIONS = "db_load_combinations"
    DB_PUSHOVER = "db_pushover"
    OPE = "ope"
    VIEW = "view"
    DB_BRIDGE = "db_bridge"
    POST_PRE_PROCESS = "post_pre_process"
    POST_ANALYSIS_RESULT_1 = "post_analysis_result_1"
    POST_ANALYSIS_RESULT_2 = "post_analysis_result_2"
    POST_STORY_TABLES = "post_story_tables"
    POST_TH_HY_PUSHOVER = "post_th_hy_pushover"
    POST_DESIGN = "post_design"
    DB_DESIGN = "db_design"
    DESIGN_STEEL_KDS41302022 = "design_steel_kds41302022"
    DESIGN_RC_KDS41202022 = "design_rc_kds41202022"
    DESIGN_SRC_AIKSRC2K = "design_src_aiksrc2k"


CAPABILITY_FEATURE_VALUES = enum_values(CapabilityFeature)


#: Which :class:`CapabilityDomain` each :class:`CapabilityFeature` belongs to.
#:
#: Every feature maps to **exactly one** domain — the three layers are a strict
#: hierarchy, so a frontend menu never has to guess and a filter never has to
#: union.  Kept next to the two enums so a new chapter cannot be added without
#: being placed.
CAPABILITY_FEATURE_DOMAIN: dict[str, str] = {
    CapabilityFeature.DOC.value: CapabilityDomain.PROJECT.value,
    CapabilityFeature.DB_PROJECT_STRUCTURE.value: CapabilityDomain.PROJECT.value,
    CapabilityFeature.DB_NODE_ELEMENT.value: CapabilityDomain.MODEL.value,
    CapabilityFeature.DB_PROPERTIES.value: CapabilityDomain.MODEL.value,
    CapabilityFeature.DB_BOUNDARY.value: CapabilityDomain.MODEL.value,
    CapabilityFeature.DB_STATIC_LOADS.value: CapabilityDomain.LOAD.value,
    CapabilityFeature.DB_TEMPERATURE_PRESTRESS.value: CapabilityDomain.LOAD.value,
    CapabilityFeature.DB_MOVING_LOADS.value: CapabilityDomain.LOAD.value,
    CapabilityFeature.DB_DYNAMIC_LOADS.value: CapabilityDomain.LOAD.value,
    CapabilityFeature.DB_CONSTRUCTION_STAGE.value: CapabilityDomain.LOAD.value,
    CapabilityFeature.DB_SETTLEMENT_MISC_LOADS.value: CapabilityDomain.LOAD.value,
    CapabilityFeature.DB_ANALYSIS_CONTROL.value: CapabilityDomain.ANALYSIS.value,
    CapabilityFeature.DB_LOAD_COMBINATIONS.value: CapabilityDomain.ANALYSIS.value,
    CapabilityFeature.DB_PUSHOVER.value: CapabilityDomain.ANALYSIS.value,
    CapabilityFeature.OPE.value: CapabilityDomain.OPERATION.value,
    CapabilityFeature.VIEW.value: CapabilityDomain.VIEW.value,
    CapabilityFeature.DB_BRIDGE.value: CapabilityDomain.MODEL.value,
    CapabilityFeature.POST_PRE_PROCESS.value: CapabilityDomain.RESULT.value,
    CapabilityFeature.POST_ANALYSIS_RESULT_1.value: CapabilityDomain.RESULT.value,
    CapabilityFeature.POST_ANALYSIS_RESULT_2.value: CapabilityDomain.RESULT.value,
    CapabilityFeature.POST_STORY_TABLES.value: CapabilityDomain.RESULT.value,
    CapabilityFeature.POST_TH_HY_PUSHOVER.value: CapabilityDomain.RESULT.value,
    CapabilityFeature.POST_DESIGN.value: CapabilityDomain.DESIGN.value,
    CapabilityFeature.DB_DESIGN.value: CapabilityDomain.DESIGN.value,
    CapabilityFeature.DESIGN_STEEL_KDS41302022.value: CapabilityDomain.DESIGN.value,
    CapabilityFeature.DESIGN_RC_KDS41202022.value: CapabilityDomain.DESIGN.value,
    CapabilityFeature.DESIGN_SRC_AIKSRC2K.value: CapabilityDomain.DESIGN.value,
}


class McpServerStatus(str, Enum):
    """``mcp_servers.status`` (总纲 §4.2.5)."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


MCP_SERVER_STATUS_VALUES = enum_values(McpServerStatus)


class McpClientStatus(str, Enum):
    """``mcp_clients.status`` (总纲 §4.2.5)."""

    DISCONNECTED = "disconnected"
    CONNECTED = "connected"


MCP_CLIENT_STATUS_VALUES = enum_values(McpClientStatus)


class AdapterStatus(str, Enum):
    """``adapters.status`` (总纲 §4.2.5)."""

    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


ADAPTER_STATUS_VALUES = enum_values(AdapterStatus)


class AiModelStatus(str, Enum):
    """``models.status`` (总纲 §4.2.5)."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


AI_MODEL_STATUS_VALUES = enum_values(AiModelStatus)


class JobStatus(str, Enum):
    """Long-running job status shared by backups / data_exports / data_imports."""

    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


JOB_STATUS_VALUES = enum_values(JobStatus)


class ValueType(str, Enum):
    """``system_configs.value_type`` (V2.1 §4, table ``system_configs``)."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    JSON = "json"


VALUE_TYPE_VALUES = enum_values(ValueType)


# ---------------------------------------------------------------------------
# 总纲 §4.1.3 — ID prefix list (closed set)
# ---------------------------------------------------------------------------
#: Logical entity name -> business ID prefix.
#: ``req_`` and ``adapter_`` are never primary keys; they live in
#: ``tasks.request_id`` / ``system_logs.request_id`` / ``audit_logs.request_id``
#: and ``system_logs.adapter_request_id`` (总纲 §4.1.5).
ID_PREFIXES: dict[str, str] = {
    "request": "req_",
    "task": "task_",
    "adapter_request": "adapter_",
    "assistant_session": "asst_",
    "assistant_message": "msg_",
    "assistant_intent": "intent_",
    "assistant_plan": "plan_",
    "confirmation_token": "confirm_",
    "assistant_file": "file_",
    "drawing_task": "draw_",
    "report": "rpt_",
    "backup": "bk_",
    "data_export": "exp_",
    "data_import": "imp_",
}

#: Reverse lookup used by validation helpers.
ID_PREFIX_VALUES: tuple[str, ...] = tuple(ID_PREFIXES.values())


# ---------------------------------------------------------------------------
# 总纲 §4.8.2 — permission codes (closed set, 34 entries)
# ---------------------------------------------------------------------------
#: ``(code, name, module, action)`` — verbatim from 总纲 §4.8.2 / V2.1 §4 19.1.
PERMISSIONS: list[tuple[str, str, str, str]] = [
    # system (3)
    ("system:read", "查看系统设置", "system", "read"),
    ("system:write", "修改系统设置", "system", "write"),
    ("system:audit", "查看审计日志", "system", "audit"),
    # model (5)
    ("model:read", "查看模型", "model", "read"),
    ("model:create", "创建模型", "model", "create"),
    ("model:update", "修改模型", "model", "update"),
    ("model:delete", "删除模型", "model", "delete"),
    ("model:test", "测试模型", "model", "test"),
    # user (4)
    ("user:read", "查看用户", "user", "read"),
    ("user:create", "创建用户", "user", "create"),
    ("user:update", "修改用户", "user", "update"),
    ("user:delete", "删除用户", "user", "delete"),
    # role (2)
    ("role:read", "查看角色", "role", "read"),
    ("role:write", "修改角色权限", "role", "write"),
    # task (3)
    ("task:read", "查看任务", "task", "read"),
    ("task:cancel", "取消任务", "task", "cancel"),
    ("task:retry", "重试任务", "task", "retry"),
    # tool (2)
    ("tool:read", "查看工具", "tool", "read"),
    ("tool:execute", "执行工具", "tool", "execute"),
    # data (6)
    ("data:read", "查看数据", "data", "read"),
    ("data:backup", "备份数据", "data", "backup"),
    ("data:restore", "恢复数据", "data", "restore"),
    ("data:export", "导出数据", "data", "export"),
    ("data:import", "导入数据", "data", "import"),
    ("data:cleanup", "清理数据", "data", "cleanup"),
    # assistant (9)
    ("assistant:read", "查看 AI 助手", "assistant", "read"),
    ("assistant:chat", "与 AI 助手对话", "assistant", "chat"),
    ("assistant:plan", "生成执行计划", "assistant", "plan"),
    ("assistant:confirm", "确认高风险计划", "assistant", "confirm"),
    ("assistant:execute", "执行计划", "assistant", "execute"),
    ("assistant:drawing", "智能识图", "assistant", "drawing"),
    ("assistant:modeling", "智能建模", "assistant", "modeling"),
    ("assistant:optimize", "结构优化", "assistant", "optimize"),
    ("assistant:report", "生成报告", "assistant", "report"),
]

PERMISSION_CODES: tuple[str, ...] = tuple(code for code, _n, _m, _a in PERMISSIONS)


# ---------------------------------------------------------------------------
# 总纲 §4.8.3 — default roles and role -> permission mapping
# ---------------------------------------------------------------------------
#: ``(code, name, description, is_system)`` — verbatim from V2.1 §4 19.2.
ROLE_DEFINITIONS: list[dict[str, object]] = [
    {
        "code": "super_admin",
        "name": "超级管理员",
        "description": "拥有系统全部权限",
        "is_system": True,
    },
    {
        "code": "engineer",
        "name": "工程师",
        "description": "可访问 MIDAS、模型和任务功能",
        "is_system": True,
    },
    {
        "code": "analyst",
        "name": "分析师",
        "description": "可访问模型分析与结果",
        "is_system": True,
    },
    {
        "code": "visitor",
        "name": "访客",
        "description": "只读权限",
        "is_system": True,
    },
]

#: 总纲 §4.8.3. ``"*"`` is the literal super-admin marker and is expanded by the
#: seeder via :func:`expand_permission_patterns` (it is *not* a SQL wildcard).
ROLE_PERMISSION_MAP: dict[str, list[str]] = {
    "super_admin": ["*"],
    "engineer": [
        "model:*",
        "tool:*",
        "task:*",
        "assistant:*",
        "system:read",
        "data:read",
    ],
    "analyst": [
        "model:read",
        "tool:read",
        "task:read",
        "assistant:read",
        "assistant:chat",
        "data:read",
    ],
    "visitor": ["model:read", "tool:read", "task:read", "data:read"],
}

#: 总纲 §4.8.3 — the role that holds every §4.8.2 code.
#:
#: Canonical home.  It used to be defined twice, independently, in ``main.py``
#: and ``auth_service.py``; two literals for one rule is how they drift apart.
SUPER_ADMIN_ROLE: str = "super_admin"

#: 总纲 §4.8.4, rows 1–3 — the permissions **only ``super_admin``** may hold.
#:
#: Note the split.  §4.8.4 lists FOUR high-risk permissions but gives them TWO
#: different constraints: the three below are super-admin-only, while
#: ``assistant:execute`` is granted to ``engineer`` and above and is *additionally*
#: gated by the §5 high-risk confirmation flow.  Flattening all four into one set
#: (as an earlier revision did) silently denied engineers a permission the spec
#: grants them — so the two axes are kept apart here.
SUPER_ADMIN_ONLY_PERMISSIONS: tuple[str, ...] = (
    "data:restore",
    "system:write",
    "user:delete",
)

#: 总纲 §4.8.4 — every permission that must pass the §5 confirmation flow before
#: it takes effect, whoever holds it.  This is **not** a super-admin filter; use
#: :data:`SUPER_ADMIN_ONLY_PERMISSIONS` when that is what you mean.
HIGH_RISK_PERMISSIONS: tuple[str, ...] = (
    *SUPER_ADMIN_ONLY_PERMISSIONS,
    "assistant:execute",
)
