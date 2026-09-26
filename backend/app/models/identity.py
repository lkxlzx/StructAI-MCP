"""Identity and access: users, roles, permissions, join tables, sessions.

V2.1 §4 tables 1–6 (总纲 §4.8 owns the permission codes).

Append-only tables in this module (no ``updated_at``, 总纲 §5.3 C-12):
``user_roles``, ``role_permissions``.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import UserStatus
from app.db.base import Base, BoolInt, CreatedAtMixin, SoftDeleteMixin, TimestampMixin, enum_check

__all__ = ["User", "Role", "Permission", "UserRole", "RolePermission", "UserSession"]


class User(TimestampMixin, SoftDeleteMixin, Base):
    """Platform account (V2.1 §4, table ``users``)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    #: 总纲 §4.2.5 — the user's **single** department label.  Matches
    #: ``midas_clients.department`` **by value** (《MIDAS API 对接规范》§2.5.4
    #: item 5), so it is a plain label and not a foreign key: one user belongs to
    #: exactly one department, and there is no ``departments`` table.
    #: ``NULL`` means "unassigned" — a real state, and **not** "any department":
    #: an unassigned principal can never use a ``department``-scoped instance
    #: (§2.5.4 fails closed rather than assuming a match).
    department: Mapped[str | None] = mapped_column(Text)
    #: bcrypt / PBKDF2 digest — never a plaintext password.
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    #: 总纲 §4.2.5: enabled / disabled / locked.
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=UserStatus.ENABLED.value, server_default=text("'enabled'")
    )
    #: 0/1 boolean (V2.1 §3.1).
    is_online: Mapped[int] = mapped_column(BoolInt, nullable=False, default=0, server_default=text("0"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_login_ip: Mapped[str | None] = mapped_column(Text)
    #: Count of consecutive failed logins (unit: count).
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)

    # String-based targets keep the module free of forward-reference problems.
    roles: Mapped[list["Role"]] = relationship(
        "Role", secondary="user_roles", lazy="selectin"
    )
    sessions: Mapped[list["UserSession"]] = relationship(
        "UserSession", back_populates="user", lazy="selectin", passive_deletes=True
    )

    __table_args__ = (enum_check("status", UserStatus),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<User id={self.id} username={self.username!r}>"


class Role(TimestampMixin, Base):
    """RBAC role (V2.1 §4, table ``roles``; defaults in 总纲 §4.8.3)."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    #: 0/1 boolean — system roles cannot be deleted.
    is_system: Mapped[int] = mapped_column(BoolInt, nullable=False, default=0, server_default=text("0"))

    permissions: Mapped[list["Permission"]] = relationship(
        "Permission", secondary="role_permissions", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Role id={self.id} code={self.code!r}>"


class Permission(CreatedAtMixin, Base):
    """Permission code ``<module>:<action>`` (总纲 §4.8.1/§4.8.2).

    Append-only in practice: the DDL declares ``created_at`` only.
    """

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    module: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Permission code={self.code!r}>"


class UserRole(Base):
    """User ↔ Role link table (总纲 §5.3 C-12: no ``updated_at``)."""

    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<UserRole user_id={self.user_id} role_id={self.role_id}>"


class RolePermission(Base):
    """Role ↔ Permission link table (总纲 §5.3 C-12: no ``updated_at``)."""

    __tablename__ = "role_permissions"

    role_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<RolePermission role_id={self.role_id} permission_id={self.permission_id}>"


class UserSession(CreatedAtMixin, Base):
    """Login session / API token record (V2.1 §4, table ``sessions``).

    Named ``UserSession`` to avoid colliding with ``sqlalchemy.orm.Session``.
    Only the token *hash* is stored (总纲 §4.7.1 spirit: no plaintext secrets).
    """

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    #: One-way hash of the bearer token.
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped["User"] = relationship("User", back_populates="sessions")

    __table_args__ = (Index("ix_sessions_user", "user_id"),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<UserSession id={self.id} session_id={self.session_id!r}>"
