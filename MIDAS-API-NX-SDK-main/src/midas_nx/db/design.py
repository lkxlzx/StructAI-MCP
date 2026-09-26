"""Source: docs/manual/24_DB_Design.md, items 1-13.

Pre-design-calculation input records (both MIDAS Gen NX and Civil NX): RC/
steel design code selection, rebar-check input, unbraced length, design
member assignment, frame definition, slenderness limits, member-type/mark
overrides, and beam/column/wall/brace rebar-data overrides.

Note: this chapter's ``/db/MEMB`` (#5, Design Member Assignment) is a
distinct DB record from ``/ope/MEMB`` (an operation endpoint implemented in
``ope.py``) — the manual has an explicit callout about this; the two share a
URI suffix but are otherwise unrelated.
"""
from __future__ import annotations

from typing import List, TypedDict

from ..post.base import NodeElemsSelector
from .base import CIVIL_ONLY, GEN_ONLY, DbResource

# Shared KEYS/TO/STRUCTURE_GROUP_NAME "pick one" element-selector used when
# CREATE_SUB_SECTION=true (REBR "ELEMS" -- REBB/REBC don't have this field,
# see their own docstrings, 2026-08-27) — identical shape to post/base.py's
# NodeElemsSelector, reused instead of redeclared.
SubSectionElems = NodeElemsSelector


class HoopShearBarSpec(TypedDict, total=False):
    """Shared {NAME, LEG_Y, LEG_Z, DIST} hoop/shear-bar spec used by REBC's
    and REBR's SHEAR_BAR_END/SHEAR_BAR_CEN."""

    NAME: str  # Hoop rebar size, D4~D57, required
    LEG_Y: int  # Number of legs (local Y dir.), required
    LEG_Z: int  # Number of legs (local Z dir.), required
    DIST: float  # Distance between rebars, required


class RebarNameDist(TypedDict, total=False):
    """Shared {NAME, DIST} pair used by REBW's VER_BAR/HOR_BAR/END_BAR/
    BE_HOR_BAR (server-confirmed names — see WallRebarItem's docstring;
    the manual's VERTICAL_REBAR/HORIZONTAL_REBAR/BE_HORIZONTAL_REBAR
    naming does not match what the live server implements)."""

    NAME: str  # Rebar size, D4~D57, required
    DIST: float  # Rebar spacing, required


# --- 1. /db/DCON — RC Design Code -------------------------------------------


class RcDesignCodePayload(TypedDict, total=False):
    """docs/manual/24_DB_Design.md #1 — /db/DCON Specifications table.

    DGNCODE is one of ~64 supported design-code strings (e.g. "KCI-USD12",
    "ACI318-19", "Eurocode2-2:05"); the manual lists only a representative
    subset, not an exhaustive enum.
    """

    DGNCODE: str  # RC Design Code name, required


class RcDesignCode(DbResource):
    ENDPOINT = "/db/DCON"
    NAME = "RC Design Code"


# --- 2. /db/DSTL — Steel Design Code ----------------------------------------


class SteelDesignCodePayload(TypedDict, total=False):
    """docs/manual/24_DB_Design.md #2 — /db/DSTL Specifications table.

    DGNCODE is one of ~66 supported design-code strings (e.g.
    "AISC(16th)-LRFD22", "Eurocode3-2:05"); the manual lists only a
    representative subset, not an exhaustive enum.
    """

    DGNCODE: str  # Steel Design Code name, required


class SteelDesignCode(DbResource):
    ENDPOINT = "/db/DSTL"
    NAME = "Design Steel Code"


# --- 3. /db/RCHK — Rebar Check Input (Beam/Column) --------------------------


class BeamMainRebarLayerEntry(TypedDict, total=False):
    """POS_TOP_LAYERS / POS_BOT_LAYERS entry within a BEAM vMAIN sector."""

    LAYER: int  # Layer number, required
    dD: float  # Surface-to-rebar-center cover distance, required
    BAR_NUM: int  # Rebar count, required
    BAR_NAME1: str  # Rebar size 1, required
    BAR_NAME2: str  # Rebar size 2, default "", optional


class BeamMainRebarSectorItem(TypedDict, total=False):
    """vMAIN entry (one of I/M/J sectors)."""

    SECTOR: str  # "I"/"J"/"M", required
    POS_TOP_LAYERS: List[BeamMainRebarLayerEntry]  # required
    POS_BOT_LAYERS: List[BeamMainRebarLayerEntry]  # required


class BeamSubRebarSectorItem(TypedDict, total=False):
    """vSUB_BAR entry (one of I/M/J sectors) — transverse (shear/torsion)
    reinforcement."""

    SECTOR: str  # "I"/"J"/"M", required
    dSUB_BARNUM: float  # Rebar count, required
    SUB_BARNAME: str  # Rebar size, required
    dSUB_BARDIST: float  # Rebar spacing, required
    dSUB_BARANGLE: float  # Angle to member, required
    bTORSIONAL_BAR: bool  # Use torsional rebar, optional
    sTRTORBARNA: str  # Torsional rebar size, optional
    dTORBAR_SPACING: float  # Torsional rebar spacing, optional
    bBUNDLEDBAR: bool  # Use bundled rebar, optional
    dBUNDLEDBARNUM: float  # Bundled rebar count, optional
    LONGIBARNA: str  # Longitudinal rebar size, optional
    dLONGIBARNUM: float  # Longitudinal rebar count, optional


class BeamCheckRebar(TypedDict, total=False):
    """"BEAM" object, present when MEMBTYPE="BEAM"."""

    vMAIN: List[BeamMainRebarSectorItem]  # Main (longitudinal) rebar, required
    vSUB_BAR: List[BeamSubRebarSectorItem]  # Sub (transverse) rebar, required
    OPTION_IMJSAME: bool  # IMJ Same Option ("it needs only I"); /info declares it and the manual documents it nowhere (checked across every chapter, 2026-09-04)


class ColumnRebarPositionEntry(TypedDict, total=False):
    """vPOSITION entry within a COLUMN vLAYER layer."""

    POSITION: str  # Surface position: circular "P1" / rectangular "P1","P2", required
    BAR_NUM: int  # Rebar count, required
    BAR_NAME1: str  # Rebar size 1, required
    BAR_NAME2: str  # Rebar size 2, default blank, optional


class ColumnRebarLayerEntry(TypedDict, total=False):
    """vLAYER entry."""

    INDEX: int  # Layer index (1~5), required
    dDc: float  # Surface-to-rebar-center cover distance, required
    vPOSITION: List[ColumnRebarPositionEntry]  # required


class ColumnSubBarSpec(TypedDict, total=False):
    """COLUMN "SUB_BAR" object — transverse (hoop) reinforcement."""

    SUBBAR_NAME: str  # Rebar size, required
    SUBBAR_DIST: float  # Rebar spacing, required
    SUBBAR_NUM: int  # Rebar count, required
    SUBBAR_NAME_Y: str  # Y-direction rebar size, required
    SUBBAR_NAME_Z: str  # Z-direction rebar size, required
    SUBBAR_NUM_Y: int  # Y-direction rebar count, required
    SUBBAR_NUM_Z: int  # Z-direction rebar count, required


class ColumnCheckRebar(TypedDict, total=False):
    """"COLM" object, present when MEMBTYPE="COLUMN"."""

    vLAYER: List[ColumnRebarLayerEntry]  # Main (longitudinal) rebar layers, required
    SUB_BAR: ColumnSubBarSpec  # required


class RebarCheckInputPayload(TypedDict, total=False):
    """docs/manual/24_DB_Design.md #3 — /db/RCHK Specifications tables.

    MEMBTYPE selects between the BEAM field group (vMAIN/vSUB_BAR) and the
    COLUMN field group (vLAYER/SUB_BAR); flattened onto one payload (mirrors
    MaterialParam precedent).
    """

    MEMBTYPE: str  # "BEAM"/"COLUMN", required
    ENVTYPE: int  # Crack-check exposure class: Class 1=0/Class 2=1, required
    BEAM: BeamCheckRebar  # required if MEMBTYPE="BEAM"
    COLM: ColumnCheckRebar  # required if MEMBTYPE="COLUMN"


class RebarCheckInput(DbResource):
    """⚠️ The manual documents this for both products, but three independent
    live sessions (2026-07-22, 2026-07-26, 2026-07-29) all 404 it under Gen
    NX while it answers under Civil NX. See docs/live_verification_notes.md.
    """

    ENDPOINT = "/db/RCHK"
    NAME = "Rebar Input for Checking - Beam/Column"
    PRODUCTS = CIVIL_ONLY


# --- 4. /db/LENG — Unbraced Length ------------------------------------------


class UnbracedLengthPayload(TypedDict, total=False):
    """docs/manual/24_DB_Design.md #4 — /db/LENG Specifications table."""

    LY: float  # Unbraced Length Ly (strong axis), default 0, optional
    LZ: float  # Unbraced Length Lz (weak axis), default 0, optional
    LB: float  # Laterally Unbraced Length, default 0, optional
    bNOTUSE: bool  # Do not consider lateral unbraced length, default false, optional
    bAUTOCALC: bool  # Calculate by Code, default false, optional
    LT: float  # Torsional Unbraced Length, default 0, optional


class UnbracedLength(DbResource):
    ENDPOINT = "/db/LENG"
    NAME = "Unbraced Length"


# --- 5. /db/MEMB — Design Member Assignment ---------------------------------


class DesignMemberAssignmentPayload(TypedDict, total=False):
    """docs/manual/24_DB_Design.md #5 — /db/MEMB Specifications table.

    DB record only — distinct from the /ope/MEMB operation endpoint (ch15)
    that actually performs member assignment on elements.
    """

    AELEM: List[int]  # Element IDs to group into this design member, required
    bREVERSE: bool  # Reverse local-axis direction, default false, optional


class DesignMemberAssignment(DbResource):
    ENDPOINT = "/db/MEMB"
    NAME = "Member Assignment"


# --- 6. /db/DCTL — Definition of Frame --------------------------------------


class FrameDefinitionPayload(TypedDict, total=False):
    """docs/manual/24_DB_Design.md #6 — /db/DCTL Specifications table."""

    FRAMEX: str  # X-Direction: "Unbraced Sway"/"Braced Non-sway", default "Braced Non-sway", optional
    FRAMEY: str  # Y-Direction: "Unbraced Sway"/"Braced Non-sway", default "Braced Non-sway", optional
    bAUTOKF: bool  # Auto Calculate Effective Length Factor, default false, optional
    DT: str  # Design Type: "3D"/"XZ"/"YZ"/"XY", default "3D", optional


class FrameDefinition(DbResource):
    ENDPOINT = "/db/DCTL"
    NAME = "Definition of Frame"


# --- 7. /db/LTSR — Limiting Slenderness Ratio -------------------------------


class LimitingSlendernessRatioPayload(TypedDict, total=False):
    """docs/manual/24_DB_Design.md #7 — /db/LTSR Specifications table."""

    bNOTCHECK: bool  # Do not check slenderness, default false, optional
    COMP: float  # Compression limiting slenderness ratio, required
    TENS: float  # Tension limiting slenderness ratio, required


class LimitingSlendernessRatio(DbResource):
    ENDPOINT = "/db/LTSR"
    NAME = "Limiting Slenderness Ratio"


# --- 8. /db/MBTP — Modify Member Type ---------------------------------------


class ModifyMemberTypePayload(TypedDict, total=False):
    """docs/manual/24_DB_Design.md #8 — /db/MBTP Specifications table."""

    TYPE: str  # Member Type: "COLUMN"/"BEAM"/"BRACE", required


class ModifyMemberType(DbResource):
    ENDPOINT = "/db/MBTP"
    NAME = "Modify Member Type"


# --- 9. /db/WMAK — Modify Wall Mark -----------------------------------------


class ModifyWallMarkPayload(TypedDict, total=False):
    """docs/manual/24_DB_Design.md #9 — /db/WMAK Specifications table."""

    MARKNAME: str  # Wall Mark Name, required
    WID_LIST: List[int]  # Wall ID List belonging to this mark, required


class ModifyWallMark(DbResource):
    ENDPOINT = "/db/WMAK"
    NAME = "Modify Wall Mark Design"


# --- 10. /db/REBB — Modify Beam Rebar ---------------------------------------


class BeamMainBarLayerEntry(TypedDict, total=False):
    """Item shape for BAR_SECTOR_*.vMAIN_BAR_TOP / vMAIN_BAR_BOT.

    ⚠️ 2026-08-27: dropped the inferred `LAYER` field. The sibling manual
    repo's 8/26 "전수 재검증" pass briefly changed this whole endpoint to a
    `{LAYER1, LAYER2}` object shape (matching what its Specifications
    table literally says, and what the official MIDASIT Zendesk article
    also says) — then reverted that change the same day, back to this
    array-of-`{NAME,NUM}` shape, believing REBB had been swept up in a
    batch mistake alongside REBC/REBW. A fresh `GET /info/db/REBB` schema
    pull confirms this endpoint's array items really are just `{NAME,
    NUM}` — no `LAYER` property anywhere in the live schema. The `LAYER`
    field was this SDK's own unconfirmed inference (see the removed
    comment below, from a since-superseded rewrite); dropped now that
    direct schema evidence is available. Not round-tripped with a real
    POST this session (every attempt failed generically before reaching a
    real target section, on both the array and the LAYER1/LAYER2 variant
    — inconclusive either way), so this is schema-confirmed only, not a
    live write confirmation.
    """

    NAME: str  # Rebar size, D4~D57, required
    NUM: int  # Rebar count, required


class BeamShearBarSpec(TypedDict, total=False):
    """BAR_SECTOR_*.SHEAR_BAR (stirrup) spec."""

    NAME: str  # Stirrup rebar size, D4~D57, required
    LEG: int  # Number of legs, required
    DIST: float  # Stirrup spacing, required


class BeamRebarSector(TypedDict, total=False):
    """BAR_SECTOR_I / BAR_SECTOR_M / BAR_SECTOR_J object.

    The Parameters table shows a nested "SKIN_BAR": {NAME, NUM} object, but
    the worked example flattens this to "SKIN_BAR_NAME"/"SKIN_BAR_NUM";
    following the example.
    """

    vMAIN_BAR_TOP: List[BeamMainBarLayerEntry]  # required
    vMAIN_BAR_BOT: List[BeamMainBarLayerEntry]  # required
    SHEAR_BAR: BeamShearBarSpec  # required
    SKIN_BAR_NAME: str  # Skin bar rebar size, optional
    SKIN_BAR_NUM: int  # Skin bar count, optional


class BeamRebarItem(TypedDict, total=False):
    """ITEMS entry.

    The Parameters table names the cover-distance fields "DT"/"DB", but the
    worked example uses "MAIN_BAR_DC_TOP"/"MAIN_BAR_DC_BOT" (matching the
    JSON-Schema's own field names); following the example/schema.

    ⚠️ 2026-08-27: dropped `CREATE_SUB_SECTION`/`ELEMS`. Neither appears in
    a fresh `GET /info/db/REBB` schema pull (which does list `ID`, `BAR_
    SECTOR_I/M/J`, `MAIN_BAR_DC_TOP/BOT`, and the three `bSAME_SIZE_*`
    flags below verbatim) — they were carried over from the shared
    `SubSectionElems`/REBC/REBR "create a sub-section" pattern without
    independent confirmation for this endpoint specifically.

    ⚠️ 2026-08-27 (later): attempted a full live POST round trip on Gen NX
    with a real material + section + beam element set up specifically for
    this test — every variant tried answered `"Wrong Field"` identically:
    this SDK's array shape, the official Zendesk article's own embedded
    JSON Schema block (`LAYER1`/`LAYER2` objects, `DT`/`DB` cover-distance
    names, `additionalProperties: false`), and a literally empty item
    `{}`. The identical failure regardless of content (including an empty
    item) rules out a field-shape problem — this is now believed to be a
    standing write-path failure on this account/session, the same class
    of finding as `/db/NLLP` and `/db/WVLD` elsewhere in this SDK, not
    something the request body can fix. Also newly noteworthy: the
    official article is internally self-contradictory here — its own
    embedded JSON Schema block (`LAYER1`/`LAYER2`, `DT`/`DB`) disagrees
    with its own Request/Response Example (`vMAIN_BAR_TOP`/`BOT` arrays,
    `MAIN_BAR_DC_TOP`/`BOT`) in the same document. This SDK follows the
    example, matching the one other independent signal available (the
    `GET /info/db/REBB` schema, which also uses the array form) — but
    with the write path itself broken, neither can be confirmed live.
    Level stays read.
    """

    ID: int  # Sub Section ID, read-only, optional
    BAR_SECTOR_I: BeamRebarSector  # required
    BAR_SECTOR_M: BeamRebarSector  # required
    BAR_SECTOR_J: BeamRebarSector  # required
    MAIN_BAR_DC_TOP: float  # Top cover distance dT, required
    MAIN_BAR_DC_BOT: float  # Bottom cover distance dB, required
    bSAME_SIZE_TOP_BOT: bool  # optional
    bSAME_SIZE_IMJ: bool  # optional
    bSAME_SIZE_LAYER: bool  # optional


class BeamRebarPayload(TypedDict, total=False):
    """docs/manual/24_DB_Design.md #10 — /db/REBB Specifications tables."""

    ITEMS: List[BeamRebarItem]  # min 1, required


class BeamRebar(DbResource):
    ENDPOINT = "/db/REBB"
    NAME = "Modify Beam Rebar"
    #: Gen-only: 404 (route + /info) on Civil NX, confirmed independently
    #: twice on 2026-07-29 — see db/base.py's GEN_ONLY docstring.
    PRODUCTS = GEN_ONLY


# --- 11. /db/REBC — Modify Column Rebar --------------------------------------


class ColumnMainBarItem(TypedDict, total=False):
    """REBC ITEMS.vMAIN_BAR entry.

    ⚠️ Rewritten 2026-08-27: this whole endpoint's previous TypedDicts
    (`ColumnMainBarSpec`, and the old `ColumnRebarItem` below) were
    confused with a different endpoint — `CREATE_SUB_SECTION`/`ELEMS`/
    `HOOK_TYPE` and a single-object `MAIN_BAR`/top-level `DO` don't exist
    in the real schema at all. Confirmed live on Gen NX: the old shape's
    `POST /db/REBC` answers `"Wrong Field"`; the shape below round-trips
    cleanly through a full POST->GET->PUT->DELETE->GET cycle. Also, this
    endpoint is **not** POST-only as previously documented — full CRUD,
    confirmed live (see `ColumnRebar.METHODS` below).
    """

    NAME: str  # Main rebar size, D4~D57, required
    NUM: int  # Total rebar count, required
    ROW: int  # Number of rows, required
    D0: float  # Concrete-face-to-rebar-center distance, required
    bUSE_CORNER: bool  # required
    NAME_CORNER: str  # Corner rebar size, required


class ColumnRebarItem(TypedDict, total=False):
    """ITEMS entry. See ColumnMainBarItem's docstring for the 2026-08-27
    rewrite context.

    ⚠️ 2026-08-27 (later): the sibling manual repo's own 8/26 "전수
    재검증" pass had briefly "corrected" this endpoint to a single-object
    `MAIN_BAR`/top-level `DO`/string `HOOK_TYPE` shape (matching the
    official MIDASIT Zendesk article, id `49513980544793`, fetched and
    read directly) — then reverted that "fix" the same day after finding
    it was itself wrong. Both the reverted manual text and the official
    article agree with each other, and both disagree with this SDK. Re-
    tested live on Gen NX to settle it independently of either source:
    `POST /db/REBC` with the official article's single-`MAIN_BAR`-object
    shape answers `"Wrong Field"` (rejected outright); the array-based
    `vMAIN_BAR` shape below answers a specific domain error instead
    ("Column Rebars has been entered in the section no. N, which has not
    been specified" — recognized, just needs a real target section). A
    fresh `GET /info/db/REBC` schema pull independently confirms every
    field below verbatim, including one this SDK was still missing:
    `HOOK_TYPE`. Conclusion stands: the official article itself is wrong
    for this endpoint, not just the vendored copy.
    """

    ID: int  # Sub Section number, required
    vMAIN_BAR: List[ColumnMainBarItem]  # Main Bar List, required
    SHEAR_BAR_END: HoopShearBarSpec  # required
    SHEAR_BAR_CEN: HoopShearBarSpec  # required
    HOOP_TYPE: int  # 1=Tied, 2=Spiral, required -- Integer, not the string this SDK previously used
    bSAME_SPACE_END_CEN: bool  # required
    NUM_BAR_BC_JOINT: int  # Beam-Column joint rebar count (specific design codes only), required
    HOOK_TYPE: int  # Added 2026-08-27, schema-confirmed via GET /info/db/REBC (no enum meaning given by the schema description); not independently live-tested, optional


class ColumnRebarPayload(TypedDict, total=False):
    """docs/manual/24_DB_Design.md #11 — /db/REBC Specifications tables."""

    ITEMS: List[ColumnRebarItem]  # min 1, required


class ColumnRebar(DbResource):
    ENDPOINT = "/db/REBC"
    NAME = "Modify Column Rebar"
    #: Gen-only: `/info/db/REBC` answers on Gen and 404s on Civil,
    #: confirmed independently twice (2026-07-29 sweep, then a live
    #: re-check the same day) — see db/base.py's GEN_ONLY docstring.
    #: Full CRUD confirmed live 2026-08-27 (POST->GET->PUT->DELETE->GET,
    #: DELETE actually removes the record). Distinct from ch26's
    #: design.rc_kds.rebar.ModifyColumnRebarData
    #: (/DESIGN/RC/KDS-41-20-2022/REBC), a separate endpoint with the same
    #: short name.
    PRODUCTS = GEN_ONLY


# --- 12. /db/REBW — Modify Wall Rebar ---------------------------------------


class WallRebarItem(TypedDict, total=False):
    """ITEMS entry.

    ⚠️ 2026-07-29 rewrite: the manual's own JSON Schema for this endpoint
    (`CREATE_SUB_WALL_ID`/`SUB_WALL_ID`/`STORY: {FROM,TO}`/`VERTICAL_REBAR`/
    `HORIZONTAL_REBAR`/`USE_END_REBAR`/`END_REBAR: {NAME,NUM,DIST}`/
    `BE_HORIZONTAL_REBAR`/`BOUNDARY_ELEMENT_LENGTH`/
    `CONCRETE_FACE_TO_CENTER_OF_REBAR: {DW,DE}`/`USE_MODEL_THICKNESS`/
    `THICKNESS`) does not match what the live server actually implements for
    `/db/REBW`, confirmed three ways against a real production Gen NX model
    with real wall rebar data: `GET /db/REBW` echoed the fields below (not
    the manual's), `GET /info/db/REBW` documents the same fields below as
    the server's own schema, and a live `PUT` using the fields below
    round-tripped correctly (verified, then reverted to the original
    value). Every sibling endpoint checked the same session matched its own
    documentation exactly — `/db/REBB` (this chapter) and
    `/DESIGN/RC/KDS-41-20-2022/REBW` (ch26, the KDS-specific sibling) both
    use the manual's long-form names correctly — so this looks like a
    defect specific to `/db/REBW`'s manual section. Checked directly against
    MIDASIT's official Zendesk article (not just the vendored manual copy):
    https://support.midasuser.com/hc/en-us/articles/59359110968345
    documents the same long-form names, ruling out a vendored-repo
    transcription error — the official documentation itself doesn't match
    its own server. See `docs/live_verification_notes.md`'s 2026-07-29
    sections for the full reproduction.

    ⚠️ 2026-08-27: the sibling manual repo's full re-verification pass
    claimed this field is actually `vSTORY_KEY` (an Integer array), not
    `vSTORY_NAME` (String array). Re-checked live the same day, `GET
    /info/db/REBW` on Gen NX: the server's own schema still names the
    field `vSTORY_NAME`, `items.type: "string"` — exactly matching this
    TypedDict, not the manual's new claim. The manual's correction is
    wrong on this field specifically; don't apply it.

    ⚠️ 2026-08-27 (later): the manual repo's own re-verification pass
    also claimed `/db/REBC`'s and `/db/REBB`'s Specifications went stale
    the same way as this endpoint's — see `ColumnRebarItem`'s and
    `BeamMainBarLayerEntry`'s docstrings. `/db/REBW` itself is unaffected:
    re-fetched the **entire** live schema (`GET /info/db/REBW`, every
    field, not just `vSTORY_NAME`) and it matches this TypedDict exactly,
    field for field.
    """

    ID: int  # read-only, optional
    bUSE_MODEL_THICK: bool  # Use Model Thickness, optional
    THICK: float  # Thickness, required if bUSE_MODEL_THICK=false
    DW: float  # Dw (Concrete Face ~ Rebar Center), optional
    DE: float  # De (Concrete Face ~ Rebar Center), optional
    VER_BAR: RebarNameDist  # Vertical Rebar, optional
    HOR_BAR: RebarNameDist  # Horizontal Rebar, optional
    END_BAR: RebarNameDist  # End Rebar, optional
    NUM_END_BAR: int  # End Rebar Num, optional
    BE_HOR_BAR: RebarNameDist  # Boundary Element Horizontal Rebar, optional
    BE_LENGTH: float  # Boundary Element Length, optional
    vSTORY_NAME: List[str]  # Story Key List, optional


class WallRebarPayload(TypedDict, total=False):
    """docs/manual/24_DB_Design.md #12 — /db/REBW. See `WallRebarItem`'s
    docstring: the manual's own Specifications tables for this endpoint
    don't match the live server; this payload documents the server-confirmed
    shape instead."""

    ITEMS: List[WallRebarItem]  # min 1, required


class WallRebar(DbResource):
    ENDPOINT = "/db/REBW"
    NAME = "Modify Wall Rebar"
    #: Gen-only: 404 (route + /info) on Civil NX, confirmed independently
    #: twice on 2026-07-29 — see db/base.py's GEN_ONLY docstring.
    PRODUCTS = GEN_ONLY


# --- 13. /db/REBR — Modify Brace Rebar --------------------------------------


class BraceMainBarItem(TypedDict, total=False):
    """REBR ITEMS.vMAIN_BAR entry.

    ⚠️ Rewritten 2026-09-04, the same way `ColumnMainBarItem` above was on
    2026-08-27 and for the same reason. The manual gives this endpoint a
    single `MAIN_BAR` object with a top-level `DO`, plus
    `CREATE_SUB_SECTION`/`ELEMS`. `GET /info/db/REBR` declares none of that:
    it takes `vMAIN_BAR`, an array whose entries each carry their own `D0`
    (a zero, not the letter), and has no `CREATE_SUB_SECTION` or `ELEMS` at
    all - field for field, the shape `/db/REBC` was found to have.

    No POST comparison has been run against `/db/REBR` itself, so this rests
    on the `/info` schema plus that precedent rather than on a round trip of
    its own. What `/db/REBC` established is what happens to a caller who
    follows the documented shape there: `"Wrong Field"`, refused outright.
    Recorded as MD-34.
    """

    NAME: str  # Main rebar size, D4~D57, required
    NUM: int  # Total rebar count (min 4), required
    ROW: int  # Number of rows, required
    D0: float  # Concrete-face-to-rebar-center distance, required


class BraceRebarItem(TypedDict, total=False):
    """ITEMS entry. See BraceMainBarItem's docstring for the 2026-09-04
    rewrite context."""

    ID: int  # Sub Section number, read-only
    vMAIN_BAR: List[BraceMainBarItem]  # Main Bar List, required
    SHEAR_BAR_END: HoopShearBarSpec  # required
    SHEAR_BAR_CEN: HoopShearBarSpec  # required
    HOOP_TYPE: int  # 1=Tied, 2=Spiral -- Integer, not the string the manual gives


class BraceRebarPayload(TypedDict, total=False):
    """docs/manual/24_DB_Design.md #13 — /db/REBR Specifications tables."""

    ITEMS: List[BraceRebarItem]  # min 1, required


class BraceRebar(DbResource):
    ENDPOINT = "/db/REBR"
    NAME = "Modify Brace Rebar Data"
    #: Gen-only: 404 (route + /info) on Civil NX, confirmed independently
    #: twice on 2026-07-29 — see db/base.py's GEN_ONLY docstring.
    PRODUCTS = GEN_ONLY
