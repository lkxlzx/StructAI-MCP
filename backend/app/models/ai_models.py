"""AI model providers and models.

V2.1 §4 tables 17–18. Two unique rules are easy to get wrong:

* ``ux_models_provider_code`` — ``(provider_id, model_code)``, not ``model_code``
  alone: the same model code may exist under two providers.
* ``ux_default_model`` — a **partial** unique index on ``is_default`` restricted
  to ``is_default = 1 AND deleted_at IS NULL``, so exactly one live default.

``models.api_key_encrypted`` is encrypted (总纲 §4.7.1).
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import AiModelStatus
from app.db.base import Base, BoolInt, SoftDeleteMixin, TimestampMixin, enum_check

__all__ = ["ModelProvider", "AiModel"]


class ModelProvider(TimestampMixin, Base):
    """LLM provider endpoint (V2.1 §4, table ``model_providers``)."""

    __tablename__ = "model_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    base_url: Mapped[str | None] = mapped_column(Text)
    #: e.g. ``openai_compatible`` (free text in the DDL, no CHECK).
    provider_type: Mapped[str] = mapped_column(
        Text, nullable=False, default="openai_compatible", server_default=text("'openai_compatible'")
    )
    enabled: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))
    metadata_json: Mapped[str | None] = mapped_column(Text)

    models: Mapped[list["AiModel"]] = relationship(
        "AiModel", back_populates="provider", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<ModelProvider id={self.id} code={self.code!r}>"


class AiModel(TimestampMixin, SoftDeleteMixin, Base):
    """Configured AI model (V2.1 §4, table ``models``).

    Named ``AiModel`` so ``models`` (the table) never shadows
    ``pydantic.BaseModel`` or ``app.models``.
    """

    __tablename__ = "models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("model_providers.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    model_code: Mapped[str] = mapped_column(Text, nullable=False)
    #: e.g. ``chat`` / ``embedding`` (free text in the DDL, no CHECK).
    model_type: Mapped[str] = mapped_column(Text, nullable=False, default="chat", server_default=text("'chat'"))
    #: Context window size (unit: tokens).
    context_length: Mapped[int | None] = mapped_column(Integer)
    #: Output cap (unit: tokens).
    max_output_tokens: Mapped[int | None] = mapped_column(Integer)
    api_url: Mapped[str | None] = mapped_column(Text)
    #: AES-256-GCM ciphertext (总纲 §4.7.1).
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    #: Request timeout (unit: seconds).
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60, server_default=text("60"))
    proxy_enabled: Mapped[int] = mapped_column(BoolInt, nullable=False, default=0, server_default=text("0"))
    proxy_url: Mapped[str | None] = mapped_column(Text)
    #: Sampling temperature (unit: 0.0–1.0).
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7, server_default=text("0.7"))
    #: Nucleus sampling threshold (unit: 0.0–1.0).
    top_p: Mapped[float] = mapped_column(Float, nullable=False, default=0.9, server_default=text("0.9"))
    stream_enabled: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))
    tool_calling_enabled: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))
    json_output_enabled: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))
    retry_enabled: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))
    #: Retry budget (unit: count).
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default=text("3"))
    #: 总纲 §4.2.5: available / unavailable / error.
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=AiModelStatus.UNAVAILABLE.value, server_default=text("'unavailable'")
    )
    is_default: Mapped[int] = mapped_column(BoolInt, nullable=False, default=0, server_default=text("0"))
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_test_status: Mapped[str | None] = mapped_column(Text)
    #: Round-trip latency of the last connectivity test (unit: milliseconds).
    last_test_latency_ms: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[str | None] = mapped_column(Text)

    provider: Mapped["ModelProvider"] = relationship("ModelProvider", back_populates="models")

    __table_args__ = (
        enum_check("status", AiModelStatus),
        Index("ux_models_provider_code", "provider_id", "model_code", unique=True),
        Index(
            "ux_default_model",
            "is_default",
            unique=True,
            sqlite_where=text("is_default = 1 AND deleted_at IS NULL"),
            postgresql_where=text("is_default = 1 AND deleted_at IS NULL"),
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AiModel id={self.id} model_code={self.model_code!r}>"
