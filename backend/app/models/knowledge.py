"""Engineering code knowledge base and regional load parameter library.

V2.1 §4 tables 47–49, both added by 总纲 裁决 N-19 / N-20 and promoted to a core
capability (Phase 5).

``load_parameter_library.standard_code`` stores the *string value* of
``code_standards.code`` and deliberately has **no** foreign key, so regional
parameters can be imported before the standards library is populated
(V2.1 §5.4).
"""

from sqlalchemy import ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ClauseSeverity, CodeCategory, LoadParameterType
from app.db.base import Base, BoolInt, CreatedAtMixin, enum_check

__all__ = ["CodeStandard", "CodeClause", "LoadParameterLibrary"]


class CodeStandard(CreatedAtMixin, Base):
    """Design code / standard header (V2.1 §4, table ``code_standards``).

    Append-only: the DDL declares ``created_at`` only.
    """

    __tablename__ = "code_standards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    #: Short code, e.g. ``GB50017``.
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str | None] = mapped_column(Text)
    version: Mapped[str | None] = mapped_column(Text)
    #: 总纲 §4.2.10: national / industry / local / enterprise / international.
    category: Mapped[str] = mapped_column(
        Text, nullable=False, default=CodeCategory.NATIONAL.value, server_default=text("'national'")
    )
    #: ISO 3166-1 alpha-2 country code.
    country: Mapped[str] = mapped_column(Text, nullable=False, default="CN", server_default=text("'CN'"))
    enabled: Mapped[int] = mapped_column(BoolInt, nullable=False, default=1, server_default=text("1"))

    clauses: Mapped[list["CodeClause"]] = relationship(
        "CodeClause",
        back_populates="standard",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CodeClause.clause_no",
    )

    __table_args__ = (
        enum_check("category", CodeCategory),
        Index("ix_code_standards_category", "category"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<CodeStandard code={self.code!r}>"


class CodeClause(CreatedAtMixin, Base):
    """One clause of a design code (V2.1 §4, table ``code_clauses``).

    ``(standard_id, clause_no)`` is unique. ``severity`` drives whether a
    compliance finding is advisory or blocking.
    """

    __tablename__ = "code_clauses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    standard_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_standards.id", ondelete="CASCADE"), nullable=False
    )
    #: Clause number as printed, e.g. ``5.1.1``.
    clause_no: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    #: Optional sub-category, e.g. ``stability``.
    category: Mapped[str | None] = mapped_column(Text)
    #: JSON array of search tags.
    tags_json: Mapped[str | None] = mapped_column(Text)
    #: 总纲 §4.2.10: info / warning / error.
    severity: Mapped[str] = mapped_column(
        Text, nullable=False, default=ClauseSeverity.INFO.value, server_default=text("'info'")
    )

    standard: Mapped["CodeStandard"] = relationship("CodeStandard", back_populates="clauses")

    __table_args__ = (
        enum_check("severity", ClauseSeverity),
        UniqueConstraint("standard_id", "clause_no", name="ux_code_clauses_standard_id_clause_no"),
        Index("ix_code_clauses_standard_clause", "standard_id", "clause_no"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<CodeClause standard_id={self.standard_id} clause_no={self.clause_no!r}>"


class LoadParameterLibrary(CreatedAtMixin, Base):
    """Regional load parameters (V2.1 §4, table ``load_parameter_library``).

    ``standard_code`` intentionally has no FK (V2.1 §5.4): regional parameters may
    be imported before the standards library exists.
    """

    __tablename__ = "load_parameter_library"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    #: String value of ``code_standards.code``; not a foreign key by design.
    standard_code: Mapped[str] = mapped_column(Text, nullable=False)
    region_code: Mapped[str] = mapped_column(Text, nullable=False)
    region_name: Mapped[str | None] = mapped_column(Text)
    #: 总纲 §4.2.10: wind / snow / seismic / temperature / live / dead / crane.
    parameter_type: Mapped[str] = mapped_column(Text, nullable=False)
    #: JSON payload of the regional values (units documented per 总纲 §4.5.2).
    values_json: Mapped[str] = mapped_column(Text, nullable=False)
    #: Provenance, e.g. the table number of the source standard.
    source: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        enum_check("parameter_type", LoadParameterType),
        UniqueConstraint(
            "standard_code",
            "region_code",
            "parameter_type",
            name="ux_load_parameter_library_standard_code_region_code_parameter_type",
        ),
        Index("ix_load_parameter_library_type_region", "parameter_type", "region_code"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<LoadParameterLibrary standard={self.standard_code!r} "
            f"region={self.region_code!r} type={self.parameter_type!r}>"
        )
