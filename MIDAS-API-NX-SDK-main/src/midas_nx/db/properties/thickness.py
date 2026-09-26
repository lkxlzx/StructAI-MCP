"""Source: docs/manual/04_DB_Properties.md, item 13 (/db/THIK).

Only the "VALUE" TYPE subtype is fully typed here; "STIFFENED" (STYPE
"VALUE"/"USER"/"DB") has its own nested SECTION/XZ/YZ shape documented in
the manual's "Specifications — Stiffened DB" subsection, not ported to v1.
"""
from __future__ import annotations

from typing import TypedDict

from ..base import DbResource


class ThicknessPayload(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #13 — /db/THIK Specifications (Value)."""

    NAME: str  # Thickness Name, required
    TYPE: str  # "VALUE" / "STIFFENED", required
    bINOUT: bool  # false=same in/out-of-plane, true=different; default false
    T_IN: float  # In-plane Thickness, required
    T_OUT: float  # Out-of-plane Thickness (when bINOUT is true), required if bINOUT
    OFFSET: int  # 0=None, 1=Thickness Ratio, 2=Value; default 0
    O_VALUE: float  # Local z Direction Offset Value, default 0


class Thickness(DbResource):
    ENDPOINT = "/db/THIK"
    NAME = "Thickness"
    PRODUCTS = frozenset({"gen", "civil"})
