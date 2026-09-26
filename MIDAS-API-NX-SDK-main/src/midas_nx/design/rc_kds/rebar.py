"""Source: docs/manual/26_Design_RC_KDS41202022.md, items 20-38 (of 69 total;
see design/rc_kds/setup.py, design_forces.py, checks.py for the rest).

RC design code KDS 41 20:2022 — moment/torsion/rebar-ratio parameters,
wall/rebar-design-criteria, and beam/column/wall/brace rebar-data
overrides. Endpoint prefix: ``/DESIGN/RC/KDS-41-20-2022/<CODE>``.

Note: items 35-38 (``REBB``/``REBC``/``REBW``/``REBR``) look like — and are
field-for-field nearly identical to — ``db/design.py``'s ch24 ``/db/REBB``/
``/db/REBC``/``/db/REBW``/``/db/REBR`` (a different, generic DB-Design
chapter under a different URI namespace, ``/db/*`` vs
``/DESIGN/RC/KDS-41-20-2022/*``). They are intentionally NOT imported from
``db/design.py`` here — this module declares its own local TypedDicts, per
this chapter's own manual text (verified field-for-field below). Also
note ``REBC`` (#36) here is full POST/GET/PUT/DELETE, unlike ch24's
``/db/REBC`` which is POST-only — do not conflate the two.
"""
from __future__ import annotations

from typing import Dict, List, TypedDict

from ...db.base import GEN_ONLY, GET_PUT_DELETE_METHODS, DbResource
from ...post.base import NodeElemsSelector

_BASE = "/DESIGN/RC/KDS-41-20-2022"


# Shared {NAME, LEG_Y, LEG_Z, DIST} hoop/shear-bar spec used by REBC's and
# REBR's SHEAR_BAR_END/SHEAR_BAR_CEN (#36, #38). Field-for-field identical to
# db/design.py's HoopShearBarSpec, but declared locally per this module's own
# manual section — not imported (different URI namespace/chapter).
class HoopShearBarSpec(TypedDict, total=False):
    NAME: str  # Hoop/stirrup rebar size, D4~D57 (19 total), required
    LEG_Y: int  # Number of legs (local Y dir.), required
    LEG_Z: int  # Number of legs (local Z dir.), required
    DIST: float  # Rebar spacing @, required


# Shared {NAME, DIST} pair used by REBW's VERTICAL_REBAR/HORIZONTAL_REBAR/
# BE_HORIZONTAL_REBAR (#37). Field-for-field identical to db/design.py's
# RebarNameDist, declared locally for the same reason as HoopShearBarSpec.
class RebarNameDist(TypedDict, total=False):
    NAME: str  # Rebar size, D4~D57 (19 total), required
    DIST: float  # Rebar spacing, required


# --- 20. DESIGN/RC/KDS-41-20-2022/MRFT — Moment Redistribution Factor -------


class MomentRedistributionFactorPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #20 — MRFT Specifications
    table. Beam Member Type only."""

    FACTOR: float  # Moment redistribution factor, >0 and <=1, default 1, optional


class MomentRedistributionFactor(DbResource):
    ENDPOINT = f"{_BASE}/MRFT"
    NAME = "Moment Redistribution Factor"


# --- 21. DESIGN/RC/KDS-41-20-2022/TRFT — Torsion Reduction Factor ----------


class TorsionReductionFactorPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #21 — TRFT Specifications
    table. Beam Member Type only."""

    FACTOR: float  # Torsion reduction factor, >0 and <=1, default 1, required


class TorsionReductionFactor(DbResource):
    ENDPOINT = f"{_BASE}/TRFT"
    NAME = "Torsion Reduction Factor"
    #: Gen-only: 404 (route + /info) on Civil NX, confirmed independently
    #: twice on 2026-07-29 — see db/base.py's GEN_ONLY docstring.
    PRODUCTS = GEN_ONLY


# --- 22. DESIGN/RC/KDS-41-20-2022/MCMB — Beam Moment Calculation Method ----


class BeamMomentCalculationMethodPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #22 — MCMB Specifications table."""

    CALC_METHOD: str  # Moment calc method: "EACH"=Each Span/"EQUI"=Equivalent Frame, required


class BeamMomentCalculationMethod(DbResource):
    ENDPOINT = f"{_BASE}/MCMB"
    NAME = "Moment Calculation Method for Beam"


# --- 23. DESIGN/RC/KDS-41-20-2022/DFBA — Design Forces for Assigned Beam ---


class DesignForcesForAssignedBeamPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #23 — DFBA Specifications table."""

    FORCE_TYPE: str  # Design force type: "Subdivided Forces"/"Member Forces", required


class DesignForcesForAssignedBeam(DbResource):
    ENDPOINT = f"{_BASE}/DFBA"
    NAME = "Design Force for Beam Assigned as Member"


# --- 24. DESIGN/RC/KDS-41-20-2022/PMDM — P-M Curve Calculation Method ------


class PMCurveCalculationMethodPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #24 — PMDM Specifications table."""

    CALC_METHOD: str  # PM interaction calc method: "P"=fix axial force/"M/P"=fix M/P ratio, required


class PMCurveCalculationMethod(DbResource):
    ENDPOINT = f"{_BASE}/PMDM"
    NAME = "P-M Curve Calculation Method"


# --- 25. DESIGN/RC/KDS-41-20-2022/WMAK — Modify Wall Mark Data -------------


class ModifyWallMarkDataPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #25 — WMAK Specifications table."""

    MARKNAME: str  # Wall mark name, minLength 1, required
    WID_LIST: List[int]  # Target wall IDs, minItems 1, required


class ModifyWallMarkData(DbResource):
    ENDPOINT = f"{_BASE}/WMAK"
    NAME = "Modify Wall Mark Data"


# --- 26. DESIGN/RC/KDS-41-20-2022/BEMW — Boundary Element Method by Wall ID -


class BoundaryElementMethodByWallIdPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #26 — BEMW Specifications table.

    Assign is documented with both minProperties=1 and maxProperties=1 (a
    single global-index record, e.g. key "1") — same single-record pattern
    as LMRR (#28) and DCRE (#33).
    """

    BBNDR_ELEM_METHOD: bool  # Use boundary element method, optional
    NMETHOD_TYPE: str  # Method type (BBNDR_ELEM_METHOD=true): "Displacement Based Method"/"Stress Based Method", optional
    BBOT_STOR: bool  # Use bottom story setting, optional
    STOR_NAME: str  # Story name (BBOT_STOR=true), optional


class BoundaryElementMethodByWallId(DbResource):
    ENDPOINT = f"{_BASE}/BEMW"
    NAME = "Boundary Element Method by Wall ID"


# --- 27. DESIGN/RC/KDS-41-20-2022/REXC — Rebar Exposure Condition ----------


class RebarExposureConditionPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #27 — REXC Specifications table."""

    EXPOSURE: str  # Rebar exposure condition: "Dry"/"Etc", default "Dry", required


class RebarExposureCondition(DbResource):
    ENDPOINT = f"{_BASE}/REXC"
    NAME = "Rebar Exposure Condition"


# --- 28. DESIGN/RC/KDS-41-20-2022/LMRR — Limit Max Rebar Ratio -------------


class LimitMaxRebarRatioPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #28 — LMRR Specifications table.

    Assign is documented with both minProperties=1 and maxProperties=1 (a
    single global-index record, e.g. key "1").
    """

    RHOW: float  # Maximum rebar ratio for Shear Wall Design (Rhow), required
    RHOC: float  # Maximum rebar ratio for Column Design (Rhoc), required
    RHOR: float  # Maximum rebar ratio for Brace Design (Rhor), required


class LimitMaxRebarRatio(DbResource):
    ENDPOINT = f"{_BASE}/LMRR"
    NAME = "Limiting Maximum Rebar Ratio"
    #: Active Methods per this endpoint's own manual section: GET/PUT/DELETE
    #: only — no POST.
    METHODS = GET_PUT_DELETE_METHODS


# --- 29. DESIGN/RC/KDS-41-20-2022/DCRM-BEAM — Rebar Design Criteria by Beam Member ---


class RebarDesignCriteriaByBeamMemberPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #29 — DCRM-BEAM Specifications
    table. Response is nested under top-level key "DCRMB" (not "DCRM-BEAM")."""

    MAIN_REBAR: str  # Main rebar size, D4~D57 (19 total), required
    STIRRUPS: str  # Stirrup (shear rebar) size, D4~D57 (19 total), required
    STIRRUP_ARRANGEMENT: int  # Stirrup leg count, 2~20 (19 total), required
    SIDE_BAR: str  # Side (skin) bar size, D4~D57 (19 total), required
    DT: float  # Top cover distance dT, default 0, optional
    DB: float  # Bottom cover distance dB, default 0, optional
    DOUBLY_REBAR: bool  # Use doubly-reinforced design, default true, optional
    DOUBLY_K: float  # Doubly-reinforced k factor, default 1, optional
    SPACING_LIMIT: bool  # Consider rebar spacing limit, default true, optional
    SPLICED_BARS: str  # Splice option: "None"/"50%"/"100%", default "50%", optional


class RebarDesignCriteriaByBeamMember(DbResource):
    ENDPOINT = f"{_BASE}/DCRM-BEAM"
    NAME = "Design Criteria for Rebars by Beam Member"


# --- 30/31. Shared item — DCRM-COLUMN (#30) / DCRM-BRACE (#31) -------------


class ColumnBraceRebarDesignCriteriaItem(TypedDict, total=False):
    """Shared per-member-ID item for DCRM-COLUMN (#30) and DCRM-BRACE (#31).

    Both sections' own manual text state the field structure is identical
    ("가새 부재별 철근 설계기준을 지정합니다. 필드 구성은 기둥(DCRM-COLUMN)과
    동일합니다") and their JSON Schemas confirm it field-for-field — factored
    out here instead of duplicated (mirrors db/design.py's HoopShearBarSpec/
    RebarNameDist sharing precedent).
    """

    MAIN_REBAR: str  # Main rebar size, D4~D57 (19 total), required
    TIES_SPIRALS: str  # Ties/spiral rebar size, D4~D57 (19 total), required
    ARRANGEMENT_Y: int  # Tie leg count (local Y), 2~20 (19 total), required
    ARRANGEMENT_Z: int  # Tie leg count (local Z), 2~20 (19 total), required
    DO: float  # Cover distance to main rebar center (do), default 0, optional
    SPACING_LIMIT: bool  # Consider rebar spacing limit, default true, optional
    SPLICED_BARS: str  # Splice option: "None"/"50%"/"100%", default "50%", optional


# --- 30. DESIGN/RC/KDS-41-20-2022/DCRM-COLUMN — Rebar Design Criteria by Column Member ---


class RebarDesignCriteriaByColumnMemberPayload(ColumnBraceRebarDesignCriteriaItem):
    """docs/manual/26_Design_RC_KDS41202022.md #30 — DCRM-COLUMN
    Specifications table. Response is nested under top-level key "DCRMC"."""


class RebarDesignCriteriaByColumnMember(DbResource):
    ENDPOINT = f"{_BASE}/DCRM-COLUMN"
    NAME = "Design Criteria for Rebars by Column Member"


# --- 31. DESIGN/RC/KDS-41-20-2022/DCRM-BRACE — Rebar Design Criteria by Brace Member ---


class RebarDesignCriteriaByBraceMemberPayload(ColumnBraceRebarDesignCriteriaItem):
    """docs/manual/26_Design_RC_KDS41202022.md #31 — DCRM-BRACE
    Specifications table (field structure identical to DCRM-COLUMN per the
    manual's own text). Response is nested under top-level key "DCRMR"."""


class RebarDesignCriteriaByBraceMember(DbResource):
    ENDPOINT = f"{_BASE}/DCRM-BRACE"
    NAME = "Design Criteria for Rebars by Brace Member"


# --- 32. DESIGN/RC/KDS-41-20-2022/DCRM-WALL — Rebar Design Criteria by Wall Member ---


class RebarDesignCriteriaByWallMemberItem(TypedDict, total=False):
    """One entry of DCRM-WALL's per-story "ITEMS" array (#32)."""

    STORY: str  # Story name, minLength 1, required
    VERTICAL_REBAR: str  # Vertical rebar size, D4~D57 (19 total), required
    HORIZONTAL_REBAR: str  # Horizontal rebar size, D4~D57 (19 total), required
    END_REBAR: str  # End rebar size, D4~D57 (19 total), required
    BE_HORZ_REBAR: str  # Boundary element horizontal rebar size, D4~D57 (19 total), required
    BE_HORZ_SPACE: float  # Boundary element horizontal rebar spacing, required
    BE_VERT_SPACE: float  # Boundary element vertical rebar spacing, required
    DE: float  # End cover distance de (m), default 0, optional
    DW: float  # Wall-face cover distance dw (m), default 0, optional


class RebarDesignCriteriaByWallMemberPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #32 — DCRM-WALL Specifications
    table. Response is nested under top-level key "DCRMW".

    2026-07-21 schema change: was previously one flat rebar-spec object per
    wall ID; the manual now documents per-story entries under a required
    "ITEMS" array (each item adding a required "STORY" name to the same
    rebar-spec fields) — see RebarDesignCriteriaByWallMemberItem.
    """

    ITEMS: List[RebarDesignCriteriaByWallMemberItem]  # Per-story rebar spec list, minItems 1, required


class RebarDesignCriteriaByWallMember(DbResource):
    ENDPOINT = f"{_BASE}/DCRM-WALL"
    NAME = "Design Criteria for Rebars by Wall Member"


# --- 33. DESIGN/RC/KDS-41-20-2022/DCRE — Rebar Design Criteria -------------


class DcreBeamCriteria(TypedDict, total=False):
    """DCRE's "BEAM" object (#33). Unlike DCRM-BEAM's MAIN_REBAR (a single
    string), DCRE's MAIN_REBAR is an array of up to 5 sizes — the two are NOT
    identical, so this is a distinct TypedDict, not a reuse of
    RebarDesignCriteriaByBeamMemberPayload."""

    MAIN_REBAR: List[str]  # Main rebar sizes (up to 5), items D4~D57 (19 total), default ["D22"], optional
    STIRRUPS: str  # Stirrup size, D4~D57 (19 total), default "D10", optional
    STIRRUP_ARRANGEMENT: int  # Stirrup leg count, 2~20 (19 total), default 2, optional
    SIDE_BAR: str  # Side bar size, D4~D57 (19 total), default "D13", optional
    DT: float  # Top cover distance, default 0, optional
    DB: float  # Bottom cover distance, default 0, optional
    DOUBLY_REBAR: bool  # Use doubly-reinforced design, default true, optional
    DOUBLY_K: float  # Doubly-reinforced k factor, default 1, optional
    SPACING_LIMIT: bool  # Consider rebar spacing limit, default true, optional
    # Documented as a string enum ("None"/"50%"/"100%", default "50%") in the
    # Specifications table, but the manual's own worked DCRE Request/Response
    # example sends an integer (SPLICED_BARS=1) and explicitly recommends
    # following the example's format when sending; typed as str here to stay
    # consistent with the same field on DCRM-BEAM/DCRM-COLUMN/DCRM-BRACE
    # (whose own worked examples DO use the string form) — this repo's
    # TypedDict hints aren't runtime-enforced, so callers following the DCRE
    # example's int form are not blocked.
    SPLICED_BARS: str  # Splice option: "None"/"50%"/"100%", default "50%", optional


class DcreColumnBraceCriteria(TypedDict, total=False):
    """DCRE's "COLUMN"/"BRACE" objects (#33) — identical structure to each
    other per the manual's schema. MAIN_REBAR is an array here (unlike
    DCRM-COLUMN/DCRM-BRACE's single-string MAIN_REBAR), so this is a distinct
    TypedDict, not a reuse of ColumnBraceRebarDesignCriteriaItem."""

    MAIN_REBAR: List[str]  # Main rebar sizes (up to 5), items D4~D57 (19 total), default ["D22"], optional
    TIES_SPIRALS: str  # Ties/spiral rebar size, D4~D57 (19 total), default "D10", optional
    ARRANGEMENT_Y: int  # Tie leg count (local Y), 2~20 (19 total), default 2, optional
    ARRANGEMENT_Z: int  # Tie leg count (local Z), 2~20 (19 total), default 2, optional
    DO: float  # Cover distance to main rebar center, default 0, optional
    SPACING_LIMIT: bool  # Consider rebar spacing limit, default true, optional
    SPLICED_BARS: str  # Splice option: "None"/"50%"/"100%", default "50%", optional


class DcreWallMaterialByDiameterEntry(TypedDict, total=False):
    """DCRE WALL.MATERIAL_BY_DIAMETER_INPUT's VERTICAL_END_REBAR/
    HORIZONTAL_REBAR array item."""

    REBAR_DIAMETER: str  # Rebar diameter, D4~D57 (19 total), optional
    MATERIAL: str  # Material grade: "None"/"SD300"/"SD400"/"SD500"/"SD600"/"SD700"/"SD400S"/"SD500S"/"SD600S", optional


class DcreWallMaterialByDiameterInput(TypedDict, total=False):
    """DCRE WALL's "MATERIAL_BY_DIAMETER_INPUT" object
    (MATERIAL_BY_DIAMETER=true)."""

    VERTICAL_END_REBAR: List[DcreWallMaterialByDiameterEntry]  # Vertical/end rebar material mapping, optional
    HORIZONTAL_REBAR: List[DcreWallMaterialByDiameterEntry]  # Horizontal rebar material mapping (same item shape), optional


class DcreWallAdditionalData(TypedDict, total=False):
    """DCRE WALL's "ADDITIONAL_WALL_DATA" object.

    VERTICAL_REBAR_SPACING is documented in the Specifications table as an
    object {"UNIT": "mm"/"in", "LIST_FOR_DESIGN": [...]}, default
    {"UNIT":"mm","LIST_FOR_DESIGN":[100,150]} — but the manual's own worked
    DCRE Request/Response example sends it as a plain string array (e.g.
    ["@100", "@150", "@200"]) and explicitly recommends following the
    example's format when sending. Per this task's ambiguity-resolution rule
    (follow the worked example), typed as List[str] here.
    """

    OUT_OF_PLANE_BENDING: bool  # Design for out-of-plane bending, default false, optional
    VERTICAL_REBAR_SPACING: List[str]  # Vertical rebar spacing values, e.g. ["@100", "@150"] — see docstring, optional
    HORIZONTAL_REBAR_SPACING_FROM: float  # Horizontal rebar spacing (from), m, default 0.05, optional
    END_REBAR_METHOD: int  # End rebar design method, one of 1/2/3/4, default 1, optional
    DIST1: float  # End rebar spacing for 4-bar arrangement, default 0.3, optional
    DIST2: float  # End rebar spacing for 6-bar arrangement, default 0.15, optional
    DIST3: float  # End rebar spacing for 8+-bar arrangement, default 0.1, optional


class DcreWallCriteria(TypedDict, total=False):
    """DCRE's "WALL" object (#33)."""

    VERTICAL_REBAR: List[str]  # Vertical rebar sizes (multi-select), items D4~D57 (19 total), default ["D13"], optional
    HORIZONTAL_REBAR: str  # Horizontal rebar size, D4~D57 (19 total), default "D10", optional
    END_REBAR: str  # End rebar size, D4~D57 (19 total), default "D10", optional
    BE_HORZ_REBAR: str  # Boundary element horizontal rebar size, D4~D57 (19 total), default "D10", optional
    BE_HORZ_SPACE: float  # Boundary element horizontal spacing, default 0.2, optional
    BE_VERT_SPACE: float  # Boundary element vertical spacing, default 0.1, optional
    DE: float  # Distance to first end vertical rebar, default 0, optional
    DW: float  # Wall-face cover distance, default 0, optional
    MATERIAL_BY_DIAMETER: bool  # Use material-by-diameter mapping, default false, optional
    MATERIAL_BY_DIAMETER_INPUT: DcreWallMaterialByDiameterInput  # Material-by-diameter input, required if MATERIAL_BY_DIAMETER=true
    ADDITIONAL_WALL_DATA: DcreWallAdditionalData  # Additional wall data, optional


class RebarDesignCriteriaPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #33 — DCRE Specifications
    table. Assign is documented with both minProperties=1 and
    maxProperties=1 (a single global-index record, e.g. key "1") — same
    single-record pattern as LMRR (#28) and BEMW (#26). Sets model-wide RC
    rebar design criteria per member type in one call (BEAM/COLUMN/BRACE/
    WALL each optional)."""

    BEAM: DcreBeamCriteria  # Beam rebar design criteria, optional
    COLUMN: DcreColumnBraceCriteria  # Column rebar design criteria, optional
    BRACE: DcreColumnBraceCriteria  # Brace rebar design criteria, optional
    WALL: DcreWallCriteria  # Wall rebar design criteria, optional


class RebarDesignCriteria(DbResource):
    ENDPOINT = f"{_BASE}/DCRE"
    NAME = "Design Criteria for Rebar"


# --- 34. DESIGN/RC/KDS-41-20-2022/DCREM — Equalize Joint Beam Rebar --------


class EqualizeJointBeamRebarSelectedMember(TypedDict, total=False):
    """DCREM's "SELECTED_MEMBERS" map value, keyed by node ID string."""

    ELEM_LIST: List[int]  # Exactly 2 element IDs flanking the node, minItems 2, maxItems 2, required


class EqualizeJointBeamRebarPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #34 — DCREM Specifications
    table. Assign is a global-index map (e.g. key "1"), minProperties 1."""

    SELECT_ALL: bool  # Apply to all eligible members, required
    SELECTED_MEMBERS: Dict[str, EqualizeJointBeamRebarSelectedMember]  # Node-ID-keyed member selection, required if SELECT_ALL=false


class EqualizeJointBeamRebar(DbResource):
    ENDPOINT = f"{_BASE}/DCREM"
    NAME = "Same Beam Rebar at Joints"


# --- 35. DESIGN/RC/KDS-41-20-2022/REBB — Modify Beam Rebar Data ------------


class RcBeamMainBarLayerEntry(TypedDict, total=False):
    """Item shape for BAR_SECTOR_*.vMAIN_BAR_TOP / vMAIN_BAR_BOT.

    The manual's own Specifications table describes MAIN_BAR_TOP/BOT as a
    {LAYER1, LAYER2} object each holding {NAME, NUM}, but the worked
    Request/Response example uses "vMAIN_BAR_TOP"/"vMAIN_BAR_BOT" *arrays*
    (both empty in the example) and explicitly recommends following the
    example's format. Following the manual's own guidance (and mirroring
    db/design.py's identical ch24 REBB precedent), the array-of-layers shape
    is used here, with per-item fields {LAYER, NAME, NUM} inferred from the
    layer-object Parameters table.

    2026-09-04: dropped the inferred ``LAYER`` field, which no statement in
    chapter 26 names as a property. The schema rendering carries the layer in
    the key (``LAYER1``/``LAYER2``) and the array rendering carries it in the
    item's position, so an array item has only the two members the layer rows
    give. The chapter-24 sibling ``db/design.py:BeamMainBarLayerEntry`` dropped
    the same inference on 2026-08-27 against a live ``GET /info/db/REBB``; this
    one was missed then. Recorded as MD-29.
    """

    NAME: str  # Rebar size, D4~D57 (19 total), required
    NUM: int  # Rebar count, required


class RcBeamShearBarSpec(TypedDict, total=False):
    """BAR_SECTOR_*.SHEAR_BAR (stirrup) spec."""

    NAME: str  # Stirrup rebar size, D4~D57 (19 total), required
    LEG: int  # Number of legs, required
    DIST: float  # Stirrup spacing @, required


class RcBeamRebarSector(TypedDict, total=False):
    """BAR_SECTOR_I / BAR_SECTOR_M / BAR_SECTOR_J object — all three
    sections document an identical structure per the manual's own text.

    The Parameters table shows a nested "SKIN_BAR": {NAME, NUM} object, but
    the worked example flattens this to "SKIN_BAR_NAME"/"SKIN_BAR_NUM";
    following the example (matches db/design.py's ch24 REBB precedent).
    """

    vMAIN_BAR_TOP: List[RcBeamMainBarLayerEntry]  # Top main rebar layers, required (2026-07-25: manual now marks required)
    vMAIN_BAR_BOT: List[RcBeamMainBarLayerEntry]  # Bottom main rebar layers, required (2026-07-25: manual now marks required)
    SHEAR_BAR: RcBeamShearBarSpec  # Stirrup data, required (2026-07-25: manual now marks required)
    SKIN_BAR_NAME: str  # Skin bar rebar size, optional
    SKIN_BAR_NUM: int  # Skin bar count, optional


class RcBeamRebarItem(TypedDict, total=False):
    """ITEMS entry.

    The Parameters table names the cover-distance fields "DT"/"DB", but the
    worked example uses "MAIN_BAR_DC_TOP"/"MAIN_BAR_DC_BOT"; following the
    example (matches db/design.py's ch24 REBB precedent).
    """

    CREATE_SUB_SECTION: bool  # Create sub section, default false, optional
    ID: int  # Sub Section ID, read-only, optional
    ELEMS: NodeElemsSelector  # Element No. input (KEYS/TO/STRUCTURE_GROUP_NAME — pick one), required if CREATE_SUB_SECTION=true
    BAR_SECTOR_I: RcBeamRebarSector  # I-end section rebar, required
    BAR_SECTOR_M: RcBeamRebarSector  # Mid-span section rebar, required
    BAR_SECTOR_J: RcBeamRebarSector  # J-end section rebar, required
    MAIN_BAR_DC_TOP: float  # Top cover distance dT, required
    MAIN_BAR_DC_BOT: float  # Bottom cover distance dB, required
    bSAME_SIZE_TOP_BOT: bool  # optional
    bSAME_SIZE_IMJ: bool  # optional
    bSAME_SIZE_LAYER: bool  # optional


class ModifyBeamRebarDataPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #35 — REBB Specifications
    tables. Keyed by section-number string (e.g. "211")."""

    ITEMS: List[RcBeamRebarItem]  # Beam rebar items, minItems 1, required


class ModifyBeamRebarData(DbResource):
    ENDPOINT = f"{_BASE}/REBB"
    NAME = "Modify Beam Rebar Data"
    #: Gen-only: 404 (route + /info) on Civil NX, confirmed independently
    #: twice on 2026-07-29 — see db/base.py's GEN_ONLY docstring.
    PRODUCTS = GEN_ONLY


# --- 36. DESIGN/RC/KDS-41-20-2022/REBC — Modify Column Rebar Data ----------


class RcColumnMainBarSpec(TypedDict, total=False):
    """REBC ITEMS.MAIN_BAR."""

    NAME: str  # Main rebar size, D4~D57 (19 total), required
    NUM: int  # Total rebar count, required
    ROW: int  # Number of rows, required
    USE_CORNER: bool  # Use corner rebar, required
    NAME_CORNER: str  # Corner rebar size, D4~D57 (19 total), required if USE_CORNER=true


class RcColumnRebarItem(TypedDict, total=False):
    """ITEMS entry."""

    CREATE_SUB_SECTION: bool  # Create sub section, default false, optional
    ID: int  # Sub Section ID, read-only, optional
    ELEMS: NodeElemsSelector  # Element No. input (KEYS/TO/STRUCTURE_GROUP_NAME — pick one), required if CREATE_SUB_SECTION=true
    MAIN_BAR: RcColumnMainBarSpec  # Main rebar data, required
    SHEAR_BAR_END: HoopShearBarSpec  # End-region hoop rebar data, required
    SHEAR_BAR_CEN: HoopShearBarSpec  # Central-region hoop rebar data, required
    DO: float  # Concrete-face-to-rebar-center distance (do), required
    HOOP_TYPE: str  # "Ties"/"Spirals", default "Ties", optional
    HOOK_TYPE: int  # Hook type: 90+(135 or 180)=0 / Both(135 or 180)=1, default 0, optional


class ModifyColumnRebarDataPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #36 — REBC Specifications
    tables. Keyed by section-number string (e.g. "1")."""

    ITEMS: List[RcColumnRebarItem]  # Column rebar items, minItems 1, required


class ModifyColumnRebarData(DbResource):
    ENDPOINT = f"{_BASE}/REBC"
    NAME = "Modify Column Rebar Data"
    #: Active Methods per this endpoint's own manual section: full
    #: POST/GET/PUT/DELETE — unlike ch24's /db/REBC, which is POST-only. Do
    #: NOT apply a POST-only METHODS override here.
    #: Gen-only: 404 (route + /info) on Civil NX, confirmed independently
    #: twice on 2026-07-29 — see db/base.py's GEN_ONLY docstring. Distinct
    #: from ch24's db.design.ColumnRebar (/db/REBC), which is a separate,
    #: unconfirmed Gen-only candidate left alone for now.
    PRODUCTS = GEN_ONLY


# --- 37. DESIGN/RC/KDS-41-20-2022/REBW — Modify Wall Rebar Data ------------


class RcWallStoryRange(TypedDict, total=False):
    FROM: str  # Start story, required
    TO: str  # End story, required


class RcWallEndRebarSpec(TypedDict, total=False):
    NAME: str  # End (vertical) rebar size, D4~D57 (19 total), required
    NUM: int  # End rebar count, required
    DIST: float  # End rebar spacing, required


class RcWallConcreteFaceToCenterOfRebar(TypedDict, total=False):
    DW: float  # Concrete-face-to-vertical-rebar-center distance, required
    DE: float  # Concrete-face-to-boundary-element-rebar-center distance, required


class RcWallRebarItem(TypedDict, total=False):
    """ITEMS entry.

    SUB_WALL_ID is labeled both "read only" and "required if
    CREATE_SUB_WALL_ID=true" by the manual's own Parameters table — a
    self-contradiction in the source (same pattern as db/design.py's ch24
    REBW WallRebarItem.SUB_WALL_ID). The worked Request/Response example
    sends it as real client input (SUB_WALL_ID=1), so it is documented here
    as required, matching the example rather than the "read only" label.
    """

    CREATE_SUB_WALL_ID: bool  # Create sub wall ID, default false, optional
    SUB_WALL_ID: int  # Sub Wall ID, "read only" per manual but sent as required input in the worked example, required if CREATE_SUB_WALL_ID=true
    STORY: RcWallStoryRange  # Story range, required if CREATE_SUB_WALL_ID=true
    VERTICAL_REBAR: RebarNameDist  # Vertical rebar data, required
    HORIZONTAL_REBAR: RebarNameDist  # Horizontal rebar data, required
    USE_END_REBAR: bool  # Use end rebar input, default false, optional
    END_REBAR: RcWallEndRebarSpec  # End rebar data, required if USE_END_REBAR=true
    BE_HORIZONTAL_REBAR: RebarNameDist  # Boundary element horizontal rebar data, optional
    BOUNDARY_ELEMENT_LENGTH: float  # Boundary element length, default 0, optional
    CONCRETE_FACE_TO_CENTER_OF_REBAR: RcWallConcreteFaceToCenterOfRebar  # dw/de, required
    USE_MODEL_THICKNESS: bool  # Use model thickness, default true, optional
    THICKNESS: float  # Wall thickness, required if USE_MODEL_THICKNESS=false


class ModifyWallRebarDataPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #37 — REBW Specifications
    tables. Keyed by wall-ID string (e.g. "1")."""

    ITEMS: List[RcWallRebarItem]  # Wall rebar items, minItems 1, required


class ModifyWallRebarData(DbResource):
    ENDPOINT = f"{_BASE}/REBW"
    NAME = "Modify Wall Rebar Data"
    #: Gen-only: 404 (route + /info) on Civil NX, confirmed independently
    #: twice on 2026-07-29 — see db/base.py's GEN_ONLY docstring.
    PRODUCTS = GEN_ONLY


# --- 38. DESIGN/RC/KDS-41-20-2022/REBR — Modify Brace Rebar Data -----------


class RcBraceMainBarSpec(TypedDict, total=False):
    """REBR ITEMS.MAIN_BAR — unlike REBC's MAIN_BAR, no USE_CORNER/NAME_CORNER."""

    NAME: str  # Main rebar size, D4~D57 (19 total), required
    NUM: int  # Total rebar count, min 4 (2026-07-25: manual now documents this constraint), required
    ROW: int  # Number of rows, required


class RcBraceRebarItem(TypedDict, total=False):
    """ITEMS entry. Structure mirrors REBC (#36) except MAIN_BAR has no
    USE_CORNER/NAME_CORNER and there is no HOOK_TYPE (per the manual's own
    description)."""

    CREATE_SUB_SECTION: bool  # Create sub section, default false, optional
    ID: int  # Sub Section ID, read-only, optional
    ELEMS: NodeElemsSelector  # Element No. input (KEYS/TO/STRUCTURE_GROUP_NAME — pick one), required if CREATE_SUB_SECTION=true
    MAIN_BAR: RcBraceMainBarSpec  # Main rebar data, required
    SHEAR_BAR_END: HoopShearBarSpec  # End-region hoop rebar data, required
    SHEAR_BAR_CEN: HoopShearBarSpec  # Central-region hoop rebar data, required
    DO: float  # Concrete-face-to-rebar-center distance, required
    HOOP_TYPE: str  # "Ties"/"Spirals", default "Ties", optional


class ModifyBraceRebarDataPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #38 — REBR Specifications
    tables. Keyed by section-number string (e.g. "1")."""

    ITEMS: List[RcBraceRebarItem]  # Brace rebar items, minItems 1, required


class ModifyBraceRebarData(DbResource):
    ENDPOINT = f"{_BASE}/REBR"
    NAME = "Modify Brace Rebar Data"
    #: Gen-only: 404 (route + /info) on Civil NX, confirmed independently
    #: twice on 2026-07-29 — see db/base.py's GEN_ONLY docstring.
    PRODUCTS = GEN_ONLY
