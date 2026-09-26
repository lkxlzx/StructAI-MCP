"""Source: docs/manual/13_DB_Load_Combinations.md, items 1-8."""
from __future__ import annotations

from typing import List, TypedDict

from .base import DbResource


class LoadCombinationItem(TypedDict, total=False):
    """Shared "vCOMB" entry shape used by all six LCOM-* endpoints."""

    ANAL: str  # Analysis Type: "ST"/"CS"/"MV"/"SM"/"RS"/"TH"/"CB", required
    LCNAME: str  # Load Case Name, required
    FACTOR: float  # required


class LoadCombinationPayload(TypedDict, total=False):
    """Shared shape for /db/LCOM-GEN, LCOM-STEEL, LCOM-SRC, LCOM-STLCOMP,
    LCOM-SEISMIC — all five share this schema; only LCOM-CONC adds "bES"
    (see LoadCombinationConcretePayload). ACTIVE's valid values and
    whether iTYPE=2 (ABS) is supported vary per endpoint — see each
    DbResource subclass's docstring.

    The manual's 2026-08-26 re-verification claimed `NO` should be dropped
    from all six LCOM-* endpoints (no textual basis for it in any of the 6
    articles' JSON Schema/Specifications table/examples). Re-tested live
    2026-08-27 on Gen NX before trusting that: POST a real `/db/LCOM-GEN`
    combination (`{"NAME": "ProbeLC1", "iTYPE": 0, "vCOMB": [...]}`, `NO`
    omitted), then GET it back -- the server's own response includes
    `"NO": 1` unprompted. The manual's new claim is wrong; `NO` is real
    (read-only, server-assigned), same pattern as the independently
    confirmed `/db/STLD.NO`/`/db/STAG.NO` fields elsewhere in this SDK.
    Not dropped. Probe combination and its supporting STLD case deleted
    after confirming.
    """

    NO: int  # Combination Number, read-only
    NAME: str  # Combination Name, required
    ACTIVE: str  # Active Type (valid values vary per endpoint), default "ACTIVE", optional
    iTYPE: int  # Sum. Method: Add=0/Envelope=1/ABS=2/SRSS=3, default 0, optional
    DESC: str  # Description, default "", optional
    bCB: bool  # (Read-only) min/max cb type: false=General/true=Min/Max/All
    vCOMB: List[LoadCombinationItem]  # Combination List, required

    # 2026-09-04: four fields the chapter names on none of these endpoints -
    # its "LCOM 타입별 비교 요약" table gives five of the six an em dash under
    # 추가 필드 and gives LCOM-CONC only bES. GET /info/db/LCOM-* declares all
    # four on all six, on both products. Recorded here for the same reason the
    # contracts record them: a caller cannot set a field the type does not have.
    # See MD-35.
    bES: bool  # E (Concrete design only) -- /info only, requiredness unstated
    iSERV_TYPE: int  # EC Serv Type -- /info only, requiredness unstated
    nLCOMTYPE: int  # EC Lcom Type -- /info only, requiredness unstated
    nSEISTYPE: int  # EC Seis Type -- /info only, requiredness unstated


class LoadCombinationConcretePayload(LoadCombinationPayload):
    """docs/manual/13_DB_Load_Combinations.md #2 — /db/LCOM-CONC Specifications table.

    ACTIVE: "INACTIVE"/"STRENGTH"/"SERVICE".

    `bES` moved to the base payload on 2026-09-04: the chapter documents it
    here only, but /info declares it on all six endpoints. This subclass is
    kept because it is a published name and because ACTIVE's value set really
    does differ, which no field list records.
    """


class LoadCombinationGeneral(DbResource):
    """#1 — ACTIVE: "INACTIVE"/"ACTIVE". Supports iTYPE=2 (ABS)."""

    ENDPOINT = "/db/LCOM-GEN"
    NAME = "Load Combinations – General"


class LoadCombinationConcrete(DbResource):
    """#2 — ACTIVE: "INACTIVE"/"STRENGTH"/"SERVICE". Supports iTYPE=2 (ABS).

    Not Civil-only despite the chapter's framing: live-confirmed 2026-07-29
    against a real production Gen NX model with 494 real, populated rows —
    see db/base.py's GEN_ONLY docstring's sibling finding for the other 31
    ch08/ch17 endpoints that answer on Gen too (most with an empty table,
    this one with real data). PRODUCTS left at the class default
    (gen+civil).
    """

    ENDPOINT = "/db/LCOM-CONC"
    NAME = "Load Combinations – Concrete Design"


class LoadCombinationSteel(DbResource):
    """#3 — ACTIVE: "INACTIVE"/"STRENGTH"/"SERVICE". iTYPE=2 (ABS) not supported."""

    ENDPOINT = "/db/LCOM-STEEL"
    NAME = "Load Combinations – Steel Design"


class LoadCombinationSRC(DbResource):
    """#4 — ACTIVE: "INACTIVE"/"STRENGTH"/"SERVICE". iTYPE=2 (ABS) not supported."""

    ENDPOINT = "/db/LCOM-SRC"
    NAME = "Load Combinations – SRC Design"


class LoadCombinationCompositeSteelGirder(DbResource):
    """#5 — ACTIVE: "INACTIVE"/"STRENGTH"/"SERVICE". iTYPE=2 (ABS) not supported.

    Not Civil-only despite the chapter's bridge-design framing: route + /info
    schema both answer on Gen NX too (empty table, live-checked 2026-07-29)
    — see db/base.py's GEN_ONLY docstring's sibling finding. PRODUCTS left
    at the class default (gen+civil).
    """

    ENDPOINT = "/db/LCOM-STLCOMP"
    NAME = "Load Combinations – Composite Steel Girder Design"


class LoadCombinationSeismic(DbResource):
    """#6 — ACTIVE: "INACTIVE"/"ACTIVE". iTYPE=2 (ABS) not supported."""

    ENDPOINT = "/db/LCOM-SEISMIC"
    NAME = "Load Combinations – Seismic Design"


# --- 7. /db/CUTL — Cutting Line ---------------------------------------------


class CuttingLinePayload(TypedDict, total=False):
    """docs/manual/13_DB_Load_Combinations.md #7 — /db/CUTL Specifications table."""

    NAME: str  # required
    DIR: str  # Direction: "NORMAL" (normal)/"DIR" (in-plane), required
    PT1X: float  # required
    PT1Y: float  # required
    PT1Z: float  # required
    PT2X: float  # required
    PT2Y: float  # required
    PT2Z: float  # required
    R: int  # Line color R (0-255), default 0, optional
    G: int  # Line color G (0-255), default 0, optional
    B: int  # Line color B (0-255), default 0, optional
    TYPE: int  # default 0, optional


class CuttingLine(DbResource):
    ENDPOINT = "/db/CUTL"
    NAME = "Cutting Line"


# --- 8. /db/CLWP — Plate Cutting Line Diagram -------------------------------


class PlateCuttingLineDiagramPayload(TypedDict, total=False):
    """docs/manual/13_DB_Load_Combinations.md #8 — /db/CLWP Specifications table.

    Unlike CUTL (2 points, 1D elements), CLWP defines a plane via 3 points
    for plate elements and has no "TYPE" field.
    """

    NAME: str  # required
    DIR: str  # Direction: "NORMAL"/"DIR"/"PLANE", required
    PT1X: float  # required
    PT1Y: float  # required
    PT1Z: float  # required
    PT2X: float  # required
    PT2Y: float  # required
    PT2Z: float  # required
    PT3X: float  # required
    PT3Y: float  # required
    PT3Z: float  # required
    R: int  # Line color R (0-255), default 0, optional
    G: int  # Line color G (0-255), default 0, optional
    B: int  # Line color B (0-255), default 0, optional


class PlateCuttingLineDiagram(DbResource):
    ENDPOINT = "/db/CLWP"
    NAME = "Plate Cutting Line Diagram"
