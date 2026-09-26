"""Adapter registry and MIDAS client connections.

V2.1 §4 tables 15–16. ``adapters`` is the FK target for ``midas_clients``,
``capabilities``, ``tool_interfaces`` and ``tasks`` — 总纲 裁决 B-11 added the
``tasks.adapter_code`` foreign key.

Encrypted columns here (总纲 §4.7.1): ``midas_clients.api_key_encrypted`` and
``midas_clients.access_token_encrypted``.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import AdapterStatus, MidasClientStatus, MidasVisibility
from app.db.base import Base, BoolInt, TimestampMixin, enum_check

__all__ = ["Adapter", "MidasClient"]


class Adapter(TimestampMixin, Base):
    """Registered MIDAS software adapter (V2.1 §4, table ``adapters``)."""

    __tablename__ = "adapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    #: Target software family, e.g. ``midas_gen`` / ``midas_civil``.
    software: Mapped[str] = mapped_column(Text, nullable=False)
    #: Supported upstream version range, free text.
    version_range: Mapped[str | None] = mapped_column(Text)
    #: Dotted path of the adapter implementation class.
    implementation: Mapped[str] = mapped_column(Text, nullable=False)
    protocol: Mapped[str | None] = mapped_column(Text)
    #: JSON capability summary (authoritative rows live in ``capabilities``).
    capabilities_json: Mapped[str | None] = mapped_column(Text)
    #: 总纲 §4.2.5: enabled / disabled / error.
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=AdapterStatus.ENABLED.value, server_default=text("'enabled'")
    )

    clients: Mapped[list["MidasClient"]] = relationship(
        "MidasClient", back_populates="adapter", lazy="selectin"
    )

    __table_args__ = (enum_check("status", AdapterStatus),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Adapter id={self.id} code={self.code!r}>"


class MidasClient(TimestampMixin, Base):
    """Connection to one MIDAS installation (V2.1 §4, table ``midas_clients``).

    Multi-tenant: the platform serves several departments over a LAN, and each
    department registers **its own** MIDAS instance. The MAPI-Key belongs to the
    instance, not to a user, so this table doubles as the tenant registry
    (《MIDAS API 对接规范》§2.5.3).
    """

    __tablename__ = "midas_clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)

    # --- multi-tenant ownership (对接规范 §2.5.4 item 5) ------------------
    #: Registering user, and the **owner** the ``visibility='private'`` rule
    #: matches against (``scope.owner_id == principal.user_id``).  ``ON DELETE SET
    #: NULL`` — removing a user must not silently delete a department's MIDAS
    #: registration; the row simply stops being private to anybody.
    owner_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    #: The department that operates this instance — and the **matching key** of
    #: the ``visibility='department'`` rule (对接规范 §2.5.4 item 5).  It is
    #: compared **by value** against ``users.department`` (总纲 §4.2.5 补充), which
    #: is likewise a plain label, so the two share one vocabulary and neither is a
    #: foreign key — there is no ``departments`` table to point at.  This is not
    #: merely a display/grouping label: it decides who may use the instance.
    #:
    #: ``NULL`` means the instance carries no department label, and a
    #: ``department``-scoped instance without one is usable by **nobody** — the
    #: comparison cannot match, and §2.5.4 requires failing closed rather than
    #: assuming "same department".
    department: Mapped[str | None] = mapped_column(Text)
    #: 对接规范 §2.5.4: private / department / public. Default private —
    #: cross-tenant access must be granted explicitly, never assumed.
    visibility: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=MidasVisibility.PRIVATE.value,
        server_default=text("'private'"),
    )

    software: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str | None] = mapped_column(Text)
    adapter_code: Mapped[str] = mapped_column(
        Text, ForeignKey("adapters.code"), nullable=False
    )
    #: Product-scoped base URL, e.g. ``https://moa-engineers.midasit.com:443/gen``.
    #: MIDAS NX is reached through a cloud relay, not a local REST service
    #: (对接规范 §2.1), so this is the relay host plus the product segment.
    api_url: Mapped[str] = mapped_column(Text, nullable=False)
    #: AES-256-GCM ciphertext (总纲 §4.7.1). Holds the ``MAPI-Key``.
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    #: Unused by the MIDAS NX adapter — MIDAS authenticates with ``MAPI-Key``
    #: only and has no token concept (对接规范 §2.1). Kept for future
    #: non-MIDAS adapters (CSI / ANSYS).
    access_token_encrypted: Mapped[str | None] = mapped_column(Text)
    #: Upstream request timeout (unit: seconds).
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60, server_default=text("60"))
    #: Always 1. A MIDAS instance is a single GUI application and any modal
    #: dialog blocks the whole API channel, so calls to one instance must be
    #: serialized (对接规范 §2.5.2 / §2.5.4).
    max_concurrency: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    proxy_enabled: Mapped[int] = mapped_column(BoolInt, nullable=False, default=0, server_default=text("0"))
    proxy_url: Mapped[str | None] = mapped_column(Text)
    verify_tls: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))
    enabled: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))
    #: 总纲 §4.2.5: disconnected / connecting / connected / error.
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=MidasClientStatus.DISCONNECTED.value, server_default=text("'disconnected'")
    )
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[str | None] = mapped_column(Text)

    adapter: Mapped["Adapter"] = relationship("Adapter", back_populates="clients")

    __table_args__ = (
        enum_check("status", MidasClientStatus),
        enum_check("visibility", MidasVisibility),
        CheckConstraint("max_concurrency = 1", name="ck_midas_clients_max_concurrency"),
        Index("ix_midas_clients_adapter", "adapter_code"),
        Index("ix_midas_clients_status", "status"),
        Index("ix_midas_clients_owner", "owner_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<MidasClient id={self.id} name={self.name!r} status={self.status!r}>"
