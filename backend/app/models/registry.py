"""MCP tool / interface / schema / capability registry.

V2.1 §4 tables 19–23. Three deliberate deviations from the original V2.0 design,
all mandated by 总纲 §5.2:

* **B-2** ``schemas`` is unique on ``(schema_code, version)``, not on
  ``schema_code`` alone — several versions of one schema must coexist.
* **B-3** ``tool_interfaces`` is unique on ``(adapter_code, interface_code)`` and
  ``tool_id`` is **nullable**, so one endpoint can serve several tools; the
  many-to-many relation lives in ``capability_interfaces``.
* ``tools.version`` defaults to ``'2.1'`` (总纲 裁决 C-5).
"""

from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, BoolInt, TimestampMixin

__all__ = ["Tool", "ToolInterface", "Schema", "Capability", "CapabilityInterface"]


class Tool(TimestampMixin, Base):
    """One of the four stable MCP tools (V2.1 §4, table ``tools``)."""

    __tablename__ = "tools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    #: MCP Tool Schema version axis — independent of the REST ``/api/v1`` axis
    #: (总纲 裁决 C-5).
    version: Mapped[str] = mapped_column(Text, nullable=False, default="2.1", server_default=text("'2.1'"))
    #: e.g. ``generalized`` (free text in the DDL, no CHECK).
    tool_type: Mapped[str] = mapped_column(Text, nullable=False, default="generalized", server_default=text("'generalized'"))
    #: JSON Schema of the tool input (V2.1 §7–§11 are the authoritative bodies).
    input_schema_json: Mapped[str] = mapped_column(Text, nullable=False)
    output_schema_json: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))
    #: Display order (unit: count).
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))

    interfaces: Mapped[list["ToolInterface"]] = relationship(
        "ToolInterface", back_populates="tool", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Tool id={self.id} name={self.name!r}>"


class ToolInterface(TimestampMixin, Base):
    """Secondary MIDAS endpoint mapping (V2.1 §4, table ``tool_interfaces``).

    ``tool_id`` is nullable on purpose (总纲 裁决 B-3): an endpoint may be shared
    by several tools, and the authoritative sharing model is
    ``capabilities`` ↔ ``capability_interfaces``.
    """

    __tablename__ = "tool_interfaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tool_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tools.id", ondelete="SET NULL")
    )
    adapter_code: Mapped[str] = mapped_column(
        Text, ForeignKey("adapters.code"), nullable=False
    )
    interface_code: Mapped[str] = mapped_column(Text, nullable=False)
    #: HTTP method.
    method: Mapped[str] = mapped_column(Text, nullable=False)
    #: URI path. NOTE: the ``/post/*`` family (and ``/DESIGN/**/TABLE``) share one
    #: URI — ``/post/TABLE`` / ``/post/TEXT`` — and select the target with a
    #: ``TABLE_TYPE`` value inside the ``Argument`` object, so ``interface_code``
    #: must discriminate by table type, not by URI
    #: (《MIDAS API 对接规范》§6, §7.2).
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    #: Outer request-body key: ``'Assign'`` for ``/db/*``, ``'Argument'`` for
    #: ``/doc/*`` and most design/post actions, ``None`` when the endpoint takes
    #: no body (对接规范 §3.1).
    request_wrapper: Mapped[str | None] = mapped_column(Text)
    #: Outer key of a GET response, e.g. ``'NODE'``; ``None`` when the source
    #: documents no GET body (对接规范 §3.2).
    response_root_key: Mapped[str | None] = mapped_column(Text)
    #: Operation verb, aligned with the MCP action word list.
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    #: MCP resource name, singular (总纲 §4.6.1).
    resource: Mapped[str | None] = mapped_column(Text)
    request_schema_json: Mapped[str | None] = mapped_column(Text)
    response_schema_json: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))
    #: Upstream call timeout (unit: seconds).
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60, server_default=text("60"))
    async_supported: Mapped[int] = mapped_column(BoolInt, nullable=False, default=0, server_default=text("0"))
    metadata_json: Mapped[str | None] = mapped_column(Text)

    tool: Mapped[Optional["Tool"]] = relationship("Tool", back_populates="interfaces")

    __table_args__ = (
        Index("ux_tool_interface", "adapter_code", "interface_code", unique=True),
        Index("ix_tool_interfaces_tool", "tool_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<ToolInterface id={self.id} code={self.interface_code!r}>"


class Schema(TimestampMixin, Base):
    """Versioned JSON Schema registry (V2.1 §4, table ``schemas``).

    Uniqueness is ``(schema_code, version)`` — 总纲 裁决 B-2.
    """

    __tablename__ = "schemas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schema_code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    #: e.g. ``request`` / ``response`` / ``canonical``.
    schema_type: Mapped[str] = mapped_column(Text, nullable=False)
    schema_json: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("schema_code", "version", name="ux_schemas_code_version"),
        Index("ix_schemas_type", "schema_type"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Schema id={self.id} code={self.schema_code!r} version={self.version!r}>"


class Capability(TimestampMixin, Base):
    """Capability exposed by an adapter (V2.1 §4, table ``capabilities``)."""

    __tablename__ = "capabilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    adapter_code: Mapped[str] = mapped_column(
        Text, ForeignKey("adapters.code"), nullable=False
    )
    capability_code: Mapped[str] = mapped_column(Text, nullable=False)
    #: MCP resource name, singular (总纲 §4.6.1).
    resource: Mapped[str] = mapped_column(Text, nullable=False)
    #: MCP action verb.
    action: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    #: Primary interface; the full set lives in ``capability_interfaces``.
    interface_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tool_interfaces.id")
    )
    enabled: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))
    constraints_json: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ux_capability", "adapter_code", "capability_code", unique=True),
        Index("ix_capabilities_resource_action", "resource", "action"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Capability id={self.id} code={self.capability_code!r}>"


class CapabilityInterface(Base):
    """Capability ↔ Interface many-to-many link (V2.1 §4, 裁决 B-3).

    One capability may need several endpoints; one endpoint may serve several
    capabilities. No timestamps (the DDL declares none).
    """

    __tablename__ = "capability_interfaces"

    capability_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("capabilities.id", ondelete="CASCADE"), primary_key=True
    )
    interface_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tool_interfaces.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (Index("ix_capability_interfaces_interface", "interface_id"),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<CapabilityInterface capability_id={self.capability_id} interface_id={self.interface_id}>"
