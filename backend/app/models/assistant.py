"""AI engineering assistant cluster — 14 tables.

V2.1 §4 section 16 (added by 总纲 §6.1; ownership split in 总纲 §2.1 L4a:
v1.2 owns the interfaces, V2.1 owns the data and the state words).

Cluster shape (V2.1 §5.2)::

    assistant_sessions
     ├── assistant_messages ── assistant_intents ── assistant_plans
     │                                                ├── assistant_plan_steps
     │                                                └── task_id ── tasks
     ├── assistant_files
     ├── assistant_outputs
     ├── assistant_drawing_tasks ── assistant_drawing_objects
     ├── assistant_history
     └── assistant_plans ── reports

    assistant_drawing_settings   (singleton)
    assistant_templates ── assistant_examples
    assistant_commands           (instruction dictionary)

Business ID prefixes (总纲 §4.1.3): ``asst_`` sessions, ``msg_`` messages,
``intent_`` intents, ``plan_`` plans, ``file_`` files, ``draw_`` drawing tasks.

Encrypted / hashed columns: ``assistant_plans.confirmation_token_hash`` is a
one-way hash of the one-time confirmation token (总纲 §4.7.1, 裁决 N-3).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import (
    DrawingTaskStatus,
    FilePurpose,
    HistoryType,
    MessageRole,
    OutputType,
    PlanStatus,
    PlanStepStatus,
    RiskLevel,
    SessionStatus,
)
from app.db.base import (
    Base,
    BoolInt,
    CreatedAtMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UpdatedAtMixin,
    enum_check,
    single_row_check,
)

__all__ = [
    "AssistantFile",
    "AssistantSession",
    "AssistantMessage",
    "AssistantIntent",
    "AssistantPlan",
    "AssistantPlanStep",
    "AssistantOutput",
    "AssistantDrawingTask",
    "AssistantDrawingObject",
    "AssistantDrawingSetting",
    "AssistantTemplate",
    "AssistantExample",
    "AssistantHistory",
    "AssistantCommand",
]


# ---------------------------------------------------------------------------
# 16.1 文件本体 — 裁决 N-23: files hold the uploaded/produced bytes
# ---------------------------------------------------------------------------
class AssistantFile(CreatedAtMixin, SoftDeleteMixin, Base):
    """Uploaded or produced file body (V2.1 §4, table ``assistant_files``).

    ID prefix ``file_``. Semantic descriptions of artifacts live in
    ``assistant_outputs`` (裁决 N-23).
    """

    __tablename__ = "assistant_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    session_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("assistant_sessions.session_id", ondelete="SET NULL")
    )
    task_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("tasks.task_id", ondelete="SET NULL")
    )
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    #: Logical kind, e.g. ``drawing`` / ``report`` (free text in the DDL).
    file_type: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(Text)
    #: File size (unit: bytes).
    file_size: Mapped[int | None] = mapped_column(Integer)
    #: Relative to the process working directory (总纲 裁决 C-10).
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str | None] = mapped_column(Text)
    #: 总纲 §4.2.9: upload / output / temp.
    purpose: Mapped[str] = mapped_column(
        Text, nullable=False, default=FilePurpose.UPLOAD.value, server_default=text("'upload'")
    )
    #: Provenance marker, e.g. ``user`` / ``assistant`` / ``conversion``.
    source: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        enum_check("purpose", FilePurpose),
        Index("ix_assistant_files_session", "session_id"),
        Index("ix_assistant_files_task", "task_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AssistantFile file_id={self.file_id!r} name={self.file_name!r}>"


# ---------------------------------------------------------------------------
# 16.2 会话 — 裁决 N-25: midas_client_id references midas_clients(id)
# ---------------------------------------------------------------------------
class AssistantSession(TimestampMixin, SoftDeleteMixin, Base):
    """AI conversation session (V2.1 §4, table ``assistant_sessions``).

    ID prefix ``asst_``. ``midas_client_id`` is an INTEGER FK to
    ``midas_clients(id)`` (裁决 N-25).
    """

    __tablename__ = "assistant_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(Text)
    model_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("models.id", ondelete="SET NULL")
    )
    midas_client_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("midas_clients.id", ondelete="SET NULL")
    )
    project_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("projects.project_id", ondelete="SET NULL")
    )
    #: 总纲 §4.2.4: active / archived.
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=SessionStatus.ACTIVE.value, server_default=text("'active'")
    )
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime)
    #: Cached message tally (unit: count).
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    metadata_json: Mapped[str | None] = mapped_column(Text)

    messages: Mapped[list["AssistantMessage"]] = relationship(
        "AssistantMessage",
        back_populates="session",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AssistantMessage.id",
    )
    plans: Mapped[list["AssistantPlan"]] = relationship(
        "AssistantPlan",
        back_populates="session",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AssistantPlan.id",
    )

    __table_args__ = (
        enum_check("status", SessionStatus),
        Index("ix_assistant_sessions_user", "user_id"),
        Index("ix_assistant_sessions_status", "status"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AssistantSession session_id={self.session_id!r} status={self.status!r}>"


# ---------------------------------------------------------------------------
# 16.3 对话消息
# ---------------------------------------------------------------------------
class AssistantMessage(CreatedAtMixin, Base):
    """One chat turn (V2.1 §4, table ``assistant_messages``).

    ID prefix ``msg_``. Append-only in practice: the DDL declares ``created_at``
    only. ``model_code`` is a text code (the integer FK is on the session).
    """

    __tablename__ = "assistant_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    session_id: Mapped[str] = mapped_column(
        Text, ForeignKey("assistant_sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    #: 总纲 §4.2.9: user / assistant / system.
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    #: ``text`` / ``json`` / ``markdown`` (free text in the DDL, no CHECK).
    content_type: Mapped[str] = mapped_column(Text, nullable=False, default="text", server_default=text("'text'"))
    intent_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("assistant_intents.intent_id", ondelete="SET NULL")
    )
    plan_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("assistant_plans.plan_id", ondelete="SET NULL")
    )
    #: Model code used for this turn, e.g. ``<model_code>`` placeholder.
    model_code: Mapped[str | None] = mapped_column(Text)
    #: Prompt tokens consumed (unit: tokens).
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    #: Completion tokens produced (unit: tokens).
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    #: End-to-end latency (unit: milliseconds).
    latency_ms: Mapped[int | None] = mapped_column(Integer)

    session: Mapped["AssistantSession"] = relationship(
        "AssistantSession", back_populates="messages"
    )

    __table_args__ = (
        enum_check("role", MessageRole),
        Index("ix_assistant_messages_session", "session_id", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AssistantMessage message_id={self.message_id!r} role={self.role!r}>"


# ---------------------------------------------------------------------------
# 16.4 工程意图
# ---------------------------------------------------------------------------
class AssistantIntent(CreatedAtMixin, Base):
    """Parsed engineering intent (V2.1 §4, table ``assistant_intents``).

    ID prefix ``intent_``. ``missing_parameters_json`` backs the AI follow-up
    question loop (总纲 裁决 N-22).
    """

    __tablename__ = "assistant_intents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intent_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    session_id: Mapped[str] = mapped_column(
        Text, ForeignKey("assistant_sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("assistant_messages.message_id", ondelete="SET NULL")
    )
    #: Intent code, e.g. ``create_model`` / ``run_analysis``.
    intent: Mapped[str] = mapped_column(Text, nullable=False)
    #: Engineering discipline, e.g. ``steel`` / ``concrete`` / ``bridge``.
    discipline: Mapped[str | None] = mapped_column(Text)
    #: JSON: normalized entities extracted from the utterance.
    entities_json: Mapped[str | None] = mapped_column(Text)
    #: JSON: parameters still required before a plan can be built.
    missing_parameters_json: Mapped[str | None] = mapped_column(Text)
    #: JSON: non-blocking warnings.
    warnings_json: Mapped[str | None] = mapped_column(Text)
    #: Recognition confidence (unit: 0.0–1.0).
    confidence: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (Index("ix_assistant_intents_session", "session_id"),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AssistantIntent intent_id={self.intent_id!r} intent={self.intent!r}>"


# ---------------------------------------------------------------------------
# 16.5 执行计划 — status word list from 总纲 §4.2.2
# ---------------------------------------------------------------------------
class AssistantPlan(TimestampMixin, Base):
    """Executable plan with high-risk confirmation gate (V2.1 §4, 裁决 N-3).

    ID prefix ``plan_``. ``confirmation_token_hash`` stores a one-way hash of the
    one-time token; the token itself is never persisted (总纲 §4.7.1).
    """

    __tablename__ = "assistant_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    session_id: Mapped[str] = mapped_column(
        Text, ForeignKey("assistant_sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    intent_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("assistant_intents.intent_id", ondelete="SET NULL")
    )
    title: Mapped[str | None] = mapped_column(Text)
    #: 总纲 §4.2.2: draft / validating / awaiting_confirmation / approved /
    #: rejected / executing / verifying / completed / failed / cancelled.
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=PlanStatus.DRAFT.value, server_default=text("'draft'")
    )
    #: 总纲 §4.2.9: low / medium / high.
    risk_level: Mapped[str] = mapped_column(
        Text, nullable=False, default=RiskLevel.LOW.value, server_default=text("'low'")
    )
    requires_confirmation: Mapped[int] = mapped_column(BoolInt, nullable=False, default=0, server_default=text("0"))
    #: One-way hash of the one-time confirmation token (总纲 §4.7.1).
    confirmation_token_hash: Mapped[str | None] = mapped_column(Text)
    #: Token lifetime is 10 minutes (总纲 裁决 N-3).
    confirmation_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    confirmed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    task_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("tasks.task_id", ondelete="SET NULL")
    )
    #: Total step count (unit: count).
    steps_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    #: Completed step count (unit: count).
    steps_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    #: Always a 总纲 §4.4 registry code.
    error_code: Mapped[str | None] = mapped_column(Text)

    session: Mapped["AssistantSession"] = relationship(
        "AssistantSession", back_populates="plans"
    )
    steps: Mapped[list["AssistantPlanStep"]] = relationship(
        "AssistantPlanStep",
        back_populates="plan",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AssistantPlanStep.step_no",
    )

    __table_args__ = (
        enum_check("status", PlanStatus),
        enum_check("risk_level", RiskLevel),
        Index("ix_assistant_plans_session", "session_id"),
        Index("ix_assistant_plans_status", "status"),
        Index("ix_assistant_plans_task", "task_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AssistantPlan plan_id={self.plan_id!r} status={self.status!r}>"


# ---------------------------------------------------------------------------
# 16.6 计划步骤 — 裁决 N-1: directly translatable to an MCP call
# ---------------------------------------------------------------------------
class AssistantPlanStep(TimestampMixin, Base):
    """One executable plan step (V2.1 §4, table ``assistant_plan_steps``).

    Shape mandated by 裁决 N-1: ``{step_no, name, tool, action, resource,
    params, depends_on}`` — every step must map 1:1 onto an MCP tool call.
    """

    __tablename__ = "assistant_plan_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[str] = mapped_column(
        Text, ForeignKey("assistant_plans.plan_id", ondelete="CASCADE"), nullable=False
    )
    #: Ordinal inside the plan, 1-based (unit: count).
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    step_id: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text)
    #: ``midas_query`` / ``midas_model`` / ``midas_execute`` / ``midas_task``.
    tool_name: Mapped[str | None] = mapped_column(Text)
    #: MCP action verb, reusing the §6.3 word list.
    action: Mapped[str | None] = mapped_column(Text)
    #: MCP resource name, singular (总纲 §4.6.1).
    resource: Mapped[str | None] = mapped_column(Text)
    params_json: Mapped[str | None] = mapped_column(Text)
    #: JSON array of ``step_no`` values this step waits for.
    depends_on_json: Mapped[str | None] = mapped_column(Text)
    #: 总纲 §4.2.3: pending / running / completed / failed / skipped.
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=PlanStepStatus.PENDING.value, server_default=text("'pending'")
    )
    #: Step completion percentage (unit: 0–100).
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default=text("0"))
    task_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("tasks.task_id", ondelete="SET NULL")
    )
    result_json: Mapped[str | None] = mapped_column(Text)
    #: Always a 总纲 §4.4 registry code.
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    plan: Mapped["AssistantPlan"] = relationship("AssistantPlan", back_populates="steps")

    __table_args__ = (
        enum_check("status", PlanStepStatus),
        UniqueConstraint("plan_id", "step_no", name="ux_assistant_plan_steps_plan_id_step_no"),
        Index("ix_assistant_plan_steps_status", "status"),
        Index("ix_assistant_plan_steps_task", "task_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AssistantPlanStep plan_id={self.plan_id!r} step_no={self.step_no}>"


# ---------------------------------------------------------------------------
# 16.7 产物语义记录 — 裁决 N-23: outputs = file + type + metadata
# ---------------------------------------------------------------------------
class AssistantOutput(CreatedAtMixin, Base):
    """Semantic record of a produced artifact (V2.1 §4, table ``assistant_outputs``).

    ``output_id`` has no dedicated prefix in 总纲 §4.1.3 (the closed set covers
    ``file_`` only), so callers mint it with the ``file_`` prefix of the backing
    :class:`AssistantFile` or with an application-level code; the column is
    simply ``TEXT UNIQUE`` in the DDL.
    """

    __tablename__ = "assistant_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    output_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    session_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("assistant_sessions.session_id", ondelete="CASCADE")
    )
    task_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("tasks.task_id", ondelete="SET NULL")
    )
    plan_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("assistant_plans.plan_id", ondelete="SET NULL")
    )
    #: 总纲 §4.2.9: report / drawing / model_file / result.
    output_type: Mapped[str] = mapped_column(
        Text, nullable=False, default=OutputType.RESULT.value, server_default=text("'result'")
    )
    #: Concrete serialization, e.g. ``pdf`` / ``dxf`` / ``mgt``.
    format: Mapped[str | None] = mapped_column(Text)
    file_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("assistant_files.file_id", ondelete="SET NULL")
    )
    title: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        enum_check("output_type", OutputType),
        Index("ix_assistant_outputs_session", "session_id"),
        Index("ix_assistant_outputs_task", "task_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AssistantOutput output_id={self.output_id!r} type={self.output_type!r}>"


# ---------------------------------------------------------------------------
# 16.8 识图任务
# ---------------------------------------------------------------------------
class AssistantDrawingTask(CreatedAtMixin, Base):
    """Drawing recognition job (V2.1 §4, table ``assistant_drawing_tasks``).

    ID prefix ``draw_``. This row caches the runtime state of a task that also
    exists in ``tasks`` (总纲 §4.2.7).
    """

    __tablename__ = "assistant_drawing_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    drawing_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    task_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("tasks.task_id", ondelete="SET NULL")
    )
    session_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("assistant_sessions.session_id", ondelete="SET NULL")
    )
    file_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("assistant_files.file_id", ondelete="SET NULL")
    )
    #: Engineering discipline of the drawing.
    discipline: Mapped[str | None] = mapped_column(Text)
    #: Named recognition profile used for this run.
    recognition_profile: Mapped[str | None] = mapped_column(Text)
    #: 总纲 §4.2.7: queued / running / success / failed / cancelled.
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=DrawingTaskStatus.QUEUED.value, server_default=text("'queued'")
    )
    #: Recognition progress (unit: 0–100).
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default=text("0"))
    #: Mean object confidence (unit: 0.0–1.0).
    confidence_avg: Mapped[float | None] = mapped_column(Float)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    objects: Mapped[list["AssistantDrawingObject"]] = relationship(
        "AssistantDrawingObject",
        back_populates="drawing",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AssistantDrawingObject.id",
    )

    __table_args__ = (
        enum_check("status", DrawingTaskStatus),
        Index("ix_assistant_drawing_tasks_task", "task_id"),
        Index("ix_assistant_drawing_tasks_status", "status"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AssistantDrawingTask drawing_id={self.drawing_id!r} status={self.status!r}>"


# ---------------------------------------------------------------------------
# 16.9 识图对象
# ---------------------------------------------------------------------------
class AssistantDrawingObject(CreatedAtMixin, Base):
    """Object extracted from a drawing (V2.1 §4, table ``assistant_drawing_objects``).

    ``(drawing_id, object_ref)`` is unique so re-running recognition is
    idempotent per object reference.
    """

    __tablename__ = "assistant_drawing_objects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    drawing_id: Mapped[str] = mapped_column(
        Text, ForeignKey("assistant_drawing_tasks.drawing_id", ondelete="CASCADE"), nullable=False
    )
    #: e.g. ``axis`` / ``dimension`` / ``member`` / ``material`` / ``load``.
    object_type: Mapped[str] = mapped_column(Text, nullable=False)
    #: Stable reference of the object inside the source drawing.
    object_ref: Mapped[str] = mapped_column(Text, nullable=False)
    #: JSON bounding box in source-image pixels (unit: px).
    bbox_json: Mapped[str | None] = mapped_column(Text)
    #: Per-object recognition confidence (unit: 0.0–1.0).
    confidence: Mapped[float | None] = mapped_column(Float)
    properties_json: Mapped[str | None] = mapped_column(Text)
    #: MIDAS node identifier this object was mapped to (string, e.g. ``"12"``).
    mapped_node_id: Mapped[str | None] = mapped_column(Text)
    #: MIDAS element identifier this object was mapped to.
    mapped_element_id: Mapped[str | None] = mapped_column(Text)

    drawing: Mapped["AssistantDrawingTask"] = relationship(
        "AssistantDrawingTask", back_populates="objects"
    )

    __table_args__ = (
        UniqueConstraint("drawing_id", "object_ref", name="ux_assistant_drawing_objects_drawing_id_object_ref"),
        Index("ix_assistant_drawing_objects_type", "object_type"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AssistantDrawingObject id={self.id} type={self.object_type!r} ref={self.object_ref!r}>"


# ---------------------------------------------------------------------------
# 16.10 识图设置（单例表）
# ---------------------------------------------------------------------------
class AssistantDrawingSetting(UpdatedAtMixin, Base):
    """Singleton drawing-recognition settings (V2.1 §4).

    Fills the missing table noted in v1.1 §76. Only ``updated_at`` exists.
    """

    __tablename__ = "assistant_drawing_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    #: 0/1 toggles — which drawing elements are recognized.
    recognize_axis: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))
    recognize_dimensions: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))
    recognize_elevation: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))
    recognize_members: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))
    recognize_materials: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))
    recognize_loads: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))
    #: Minimum accepted recognition confidence (unit: 0.0–1.0).
    confidence_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.85, server_default=text("0.85"))

    __table_args__ = (single_row_check("id"),)


# ---------------------------------------------------------------------------
# 16.11 工程模板
# ---------------------------------------------------------------------------
class AssistantTemplate(TimestampMixin, Base):
    """Reusable engineering template (V2.1 §4, table ``assistant_templates``)."""

    __tablename__ = "assistant_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text)
    discipline: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    #: JSON Schema of the template parameters.
    param_schema_json: Mapped[str | None] = mapped_column(Text)
    #: JSON skeleton of the generated plan steps (裁决 N-1 shape).
    plan_template_json: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[int] = mapped_column(BoolInt, nullable=False, default=0, server_default=text("0"))
    #: Display order (unit: count).
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    enabled: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))

    examples: Mapped[list["AssistantExample"]] = relationship(
        "AssistantExample", back_populates="template", lazy="selectin"
    )

    __table_args__ = (Index("ix_assistant_templates_category", "category", "sort_order"),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AssistantTemplate template_code={self.template_code!r}>"


# ---------------------------------------------------------------------------
# 16.12 示例案例
# ---------------------------------------------------------------------------
class AssistantExample(TimestampMixin, Base):
    """Worked example / benchmark case (V2.1 §4, table ``assistant_examples``)."""

    __tablename__ = "assistant_examples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    example_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    template_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("assistant_templates.id", ondelete="SET NULL")
    )
    #: JSON array of example steps.
    steps_json: Mapped[str | None] = mapped_column(Text)
    #: JSON run configuration, e.g. ``{"analysis_type":"static"}``.
    run_config_json: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[int] = mapped_column(BoolInt, nullable=False, default=0, server_default=text("0"))
    #: Display order (unit: count).
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    enabled: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))

    template: Mapped[Optional["AssistantTemplate"]] = relationship(
        "AssistantTemplate", back_populates="examples"
    )

    __table_args__ = (Index("ix_assistant_examples_category", "category", "sort_order"),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AssistantExample example_code={self.example_code!r}>"


# ---------------------------------------------------------------------------
# 16.13 历史记录（细粒度审计）
# ---------------------------------------------------------------------------
class AssistantHistory(CreatedAtMixin, Base):
    """Fine-grained assistant audit record (V2.1 §4, table ``assistant_history``).

    Append-only: the DDL declares ``created_at`` only. ``history_id`` has no
    prefix in the closed set of 总纲 §4.1.3; the column is ``TEXT UNIQUE``.
    """

    __tablename__ = "assistant_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    history_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    session_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("assistant_sessions.session_id", ondelete="SET NULL")
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    message_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("assistant_messages.message_id", ondelete="SET NULL")
    )
    plan_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("assistant_plans.plan_id", ondelete="SET NULL")
    )
    task_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("tasks.task_id", ondelete="SET NULL")
    )
    #: 总纲 §4.2.9: chat / intent / plan / execute / drawing / report.
    type: Mapped[str] = mapped_column(
        Text, nullable=False, default=HistoryType.CHAT.value, server_default=text("'chat'")
    )
    #: Free-form outcome marker for this record.
    status: Mapped[str | None] = mapped_column(Text)
    input_json: Mapped[str | None] = mapped_column(Text)
    ai_reply_json: Mapped[str | None] = mapped_column(Text)
    intent_json: Mapped[str | None] = mapped_column(Text)
    plan_json: Mapped[str | None] = mapped_column(Text)
    tool_calls_json: Mapped[str | None] = mapped_column(Text)
    adapter_requests_json: Mapped[str | None] = mapped_column(Text)
    midas_responses_json: Mapped[str | None] = mapped_column(Text)
    output_files_json: Mapped[str | None] = mapped_column(Text)
    errors_json: Mapped[str | None] = mapped_column(Text)
    log_json: Mapped[str | None] = mapped_column(Text)
    #: Total wall-clock duration (unit: milliseconds).
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        enum_check("type", HistoryType),
        Index("ix_assistant_history_session", "session_id", "created_at"),
        Index("ix_assistant_history_user", "user_id"),
        Index("ix_assistant_history_task", "task_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AssistantHistory history_id={self.history_id!r} type={self.type!r}>"


# ---------------------------------------------------------------------------
# 16.14 常用工程指令
# ---------------------------------------------------------------------------
class AssistantCommand(TimestampMixin, Base):
    """Canned engineering instruction (V2.1 §4, table ``assistant_commands``)."""

    __tablename__ = "assistant_commands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    command_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text)
    #: Prompt template with ``{{placeholder}}`` slots.
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    #: JSON Schema of the template parameters.
    param_schema_json: Mapped[str | None] = mapped_column(Text)
    #: Display order (unit: count).
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    enabled: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))

    __table_args__ = (Index("ix_assistant_commands_category", "category", "sort_order"),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AssistantCommand command_code={self.command_code!r}>"
