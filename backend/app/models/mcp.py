"""MCP server / client registry and client credentials.

V2.1 §4 tables 12–14. ``mcp_servers.started_at`` comes from 总纲 裁决 A-2,
``mcp_client_credentials`` from 裁决 B-1 (one client may hold several rotating
credentials).
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import McpClientStatus, McpServerStatus
from app.db.base import Base, BoolInt, CreatedAtMixin, TimestampMixin, enum_check

__all__ = ["McpServer", "McpClient", "McpClientCredential"]


class McpServer(TimestampMixin, Base):
    """MCP protocol endpoint exposed by StructAI (V2.1 §4, table ``mcp_servers``)."""

    __tablename__ = "mcp_servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    host: Mapped[str] = mapped_column(Text, nullable=False, default="0.0.0.0", server_default=text("'0.0.0.0'"))
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=8765, server_default=text("8765"))
    protocol_version: Mapped[str] = mapped_column(
        Text, nullable=False, default="2024-11-05", server_default=text("'2024-11-05'")
    )
    #: streamable_http / sse (free text in the DDL, no CHECK).
    transport: Mapped[str] = mapped_column(
        Text, nullable=False, default="streamable_http", server_default=text("'streamable_http'")
    )
    #: 总纲 §4.2.5: stopped / starting / running / stopping / error.
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=McpServerStatus.STOPPED.value, server_default=text("'stopped'")
    )
    enabled: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))
    #: Set when the server last transitioned to ``running`` (总纲 裁决 A-2).
    started_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (enum_check("status", McpServerStatus),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<McpServer id={self.id} name={self.name!r} status={self.status!r}>"


class McpClient(TimestampMixin, Base):
    """External MCP client connected to StructAI (V2.1 §4, table ``mcp_clients``)."""

    __tablename__ = "mcp_clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    client_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    #: Free-text client kind (e.g. ``llm_agent``).
    client_type: Mapped[str | None] = mapped_column(Text)
    remote_addr: Mapped[str | None] = mapped_column(Text)
    protocol_version: Mapped[str | None] = mapped_column(Text)
    #: 总纲 §4.2.5: disconnected / connected.
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=McpClientStatus.DISCONNECTED.value, server_default=text("'disconnected'")
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    metadata_json: Mapped[str | None] = mapped_column(Text)

    credentials: Mapped[list["McpClientCredential"]] = relationship(
        "McpClientCredential",
        back_populates="client",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (enum_check("status", McpClientStatus),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<McpClient id={self.id} client_id={self.client_id!r}>"


class McpClientCredential(CreatedAtMixin, Base):
    """Credential issued to an MCP client (V2.1 §4, 裁决 B-1).

    Only a one-way hash is stored (总纲 §4.7.1); ``secret_prefix`` exists purely
    so the UI can identify a credential without holding the secret body.
    """

    __tablename__ = "mcp_client_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mcp_client_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("mcp_clients.id", ondelete="CASCADE"), nullable=False
    )
    #: PBKDF2 / bcrypt digest — one-way, never reversible.
    secret_hash: Mapped[str] = mapped_column(Text, nullable=False)
    #: Display-only leading characters of the secret.
    secret_prefix: Mapped[str | None] = mapped_column(Text)
    #: JSON array of granted permission codes (总纲 §4.8.2 subset).
    scopes_json: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)

    client: Mapped["McpClient"] = relationship("McpClient", back_populates="credentials")

    __table_args__ = (Index("ix_mcp_client_credentials_client", "mcp_client_id"),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<McpClientCredential id={self.id} client={self.mcp_client_id}>"
