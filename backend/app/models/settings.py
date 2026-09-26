"""System configuration: key/value configs plus four singleton tables.

V2.1 §4 tables 7–11. All four ``*_configs`` singletons carry ``CHECK(id = 1)``
and only ``updated_at`` (they are created by the seeder, then updated in place).

``system_configs.config_value`` must be encrypted when ``is_secret = 1``
(总纲 §4.7.1) — encryption happens in the service layer, the column stays TEXT.
"""

from sqlalchemy import ForeignKey, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import ValueType
from app.db.base import Base, BoolInt, TimestampMixin, UpdatedAtMixin, enum_check, single_row_check

__all__ = [
    "SystemConfig",
    "SecurityConfig",
    "ServiceConfig",
    "BackupConfig",
    "CleanupConfig",
]


class SystemConfig(TimestampMixin, Base):
    """Key/value system setting (V2.1 §4, table ``system_configs``)."""

    __tablename__ = "system_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    #: AES-256-GCM ciphertext when ``is_secret = 1`` (总纲 §4.7.1).
    config_value: Mapped[str | None] = mapped_column(Text)
    value_type: Mapped[str] = mapped_column(
        Text, nullable=False, default=ValueType.STRING.value, server_default=text("'string'")
    )
    #: 0/1 boolean — 1 means ``config_value`` holds ciphertext.
    is_secret: Mapped[int] = mapped_column(BoolInt, nullable=False, default=0, server_default=text("0"))
    description: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (enum_check("value_type", ValueType),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<SystemConfig key={self.config_key!r}>"


class SecurityConfig(UpdatedAtMixin, Base):
    """Singleton security policy (V2.1 §4, table ``security_configs``).

    The three ``rate_limit_*`` columns come from 总纲 裁决 B-7 / §6.2.
    """

    __tablename__ = "security_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    #: 0/1 booleans (V2.1 §3.1).
    captcha_enabled: Mapped[int] = mapped_column(BoolInt, nullable=False, default=0, server_default=text("0"))
    #: Password length in characters (unit: count).
    password_min_length: Mapped[int] = mapped_column(Integer, nullable=False, default=8, server_default=text("8"))
    #: Complexity level 0–3 (unit: level).
    password_complexity: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    #: Unit: count.
    max_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5, server_default=text("5"))
    #: Unit: minutes.
    lock_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30, server_default=text("30"))
    #: Unit: minutes — drives JWT ``expires_in`` (总纲 裁决 C-9).
    session_timeout_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30, server_default=text("30"))
    login_log_enabled: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))
    #: 总纲 裁决 C-13.
    api_auth_required: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))
    rate_limit_enabled: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))
    #: Requests allowed per minute per client (unit: count/minute).
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=120, server_default=text("120"))
    #: Token-bucket burst size (unit: count).
    rate_limit_burst: Mapped[int] = mapped_column(Integer, nullable=False, default=30, server_default=text("30"))

    __table_args__ = (single_row_check("id"),)


class ServiceConfig(UpdatedAtMixin, Base):
    """Singleton service settings (V2.1 §4, table ``service_configs``).

    ``log_level`` lives here, not on ``mcp_servers`` (总纲 裁决 A-2).
    """

    __tablename__ = "service_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    host: Mapped[str] = mapped_column(Text, nullable=False, default="0.0.0.0", server_default=text("'0.0.0.0'"))
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=8765, server_default=text("8765"))
    #: Uvicorn worker count (unit: count).
    workers: Mapped[int] = mapped_column(Integer, nullable=False, default=2, server_default=text("2"))
    log_level: Mapped[str] = mapped_column(Text, nullable=False, default="INFO", server_default=text("'INFO'"))
    cors_enabled: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))
    auto_start: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))

    __table_args__ = (single_row_check("id"),)


class BackupConfig(UpdatedAtMixin, Base):
    """Singleton backup policy (V2.1 §4, table ``backup_configs``).

    ``storage_path`` is platform-adaptive and relative to the process working
    directory (总纲 裁决 C-10), hence ``'./data/backups'``.
    """

    __tablename__ = "backup_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    enabled: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))
    #: daily / weekly / monthly (free text in the DDL, no CHECK).
    frequency: Mapped[str] = mapped_column(Text, nullable=False, default="daily", server_default=text("'daily'"))
    #: Number of archives to keep (unit: count).
    retention_count: Mapped[int] = mapped_column(Integer, nullable=False, default=7, server_default=text("7"))
    storage_path: Mapped[str] = mapped_column(Text, nullable=False, default="./data/backups", server_default=text("'./data/backups'"))

    __table_args__ = (single_row_check("id"),)


class CleanupConfig(UpdatedAtMixin, Base):
    """Singleton retention/cleanup policy (V2.1 §4, table ``cleanup_configs``)."""

    __tablename__ = "cleanup_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    #: Retention windows in days (unit: days).
    task_retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30, server_default=text("30"))
    log_retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=60, server_default=text("60"))
    audit_retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=180, server_default=text("180"))
    #: 0/1 booleans.
    cleanup_deleted_users: Mapped[int] = mapped_column(BoolInt, nullable=False, default=0, server_default=text("0"))
    cleanup_temp_files: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))

    __table_args__ = (single_row_check("id"),)
