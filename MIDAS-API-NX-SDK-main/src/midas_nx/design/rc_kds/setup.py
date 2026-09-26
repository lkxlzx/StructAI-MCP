"""Source: docs/manual/26_Design_RC_KDS41202022.md, items 1-19 (of 69 total;
see design/rc_kds/rebar.py, design_forces.py, checks.py for the rest).

RC design code KDS 41 20:2022 — design code/frame/load-combination setup,
seismic parameters, and per-member design parameters. Endpoint prefix:
``/DESIGN/RC/KDS-41-20-2022/<CODE>``.

RC design has its own field set distinct from Steel's KDS-41-30-2022 chapter
(design/steel_kds.py) even where the endpoint code is a near-namesake (e.g.
DCO/MATD/EQCT/SDGN-style member parameters) — every TypedDict here is
transcribed from this chapter's own manual text, not copied from steel_kds.py.
"""
from __future__ import annotations

from typing import List, TypedDict

from ...db.base import GEN_ONLY, GET_DELETE_METHODS, GET_PUT_DELETE_METHODS, DbResource

_BASE = "/DESIGN/RC/KDS-41-20-2022"


# --- 0. DESIGN/RC/DRC — RC Design Code Selection -----------------------------
# Added to the manual 2026-08-06 — a chapter-level "which RC
# design code is active" selector, numbered "## 0." because it predates and
# sits outside the KDS-41-20-2022/<CODE> numbering the other 69 endpoints
# share.


class RcDesignCodeSelectionPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #0 — DRC Specifications table.

    Unlike this chapter's other 69 endpoints, DRC's own URI doesn't carry the
    KDS-41-20-2022 prefix (it's ``/DESIGN/RC/DRC``, not
    ``/DESIGN/RC/KDS-41-20-2022/DRC``). The manual's GET response example is
    also nested under ``"DCON"`` — neither the endpoint name (``DRC``) nor
    the design-code-option endpoint's name (``DCO``) — stated explicitly in
    the manual as intentional, not a typo. ``DbResource.items()``/``.get()``
    already tolerate an unstable top-level key (they take the first
    dict-valued entry rather than indexing by ``ENDPOINT``), so this needed
    no special-casing beyond noting it here.
    """

    DGNCODE: str  # Design Code, enum currently has one value "KDS 41 20 : 2022", required


class RcDesignCodeSelection(DbResource):
    ENDPOINT = "/DESIGN/RC/DRC"
    NAME = "RC Design Code"
    METHODS = GET_PUT_DELETE_METHODS


# --- 1. DESIGN/RC/KDS-41-20-2022/DCO — Design Code Option --------------------


class ConcreteDesignCodeOptionShearWall(TypedDict, total=False):
    """DCO's "SEISMIC.SHEAR_WALL" — only meaningful when SEISMIC.FRAME_TYPE is
    "Special" or "Intermediate" (per the manual's 기능 description)."""

    SPEC_RC_WALL: bool  # Special RC Structural Wall, default true, optional
    BDRY_ELEM_MTHD: str  # Boundary Element Method: "Displacement"=변위기반/"Stress"=응력기반, default "Displacement", optional
    DEFL_AMP_FACT: float  # Deflection Amplification Factor (Cd): one of 1.25/1.5/2/2.5/3/3.25/4/4.5/5/5.5/6/6.5, default 4.5, optional
    IMP_FACT: float  # Important Factor (Ie): one of 1/1.2/1.5, default 1.2, optional


class ConcreteDesignCodeOptionShearDes(TypedDict, total=False):
    """DCO's "SEISMIC.SHEAR_DES" — shear-for-design settings."""

    R: float  # R*Vc(a1*Sum(Mpr)/L) >= max(Ve1,Ve2)/2 factor, special-only, >=0, default 0, optional
    MTHD: str  # Calculation method: "MAX"=MAX(Ve1,Ve2)/"MIN"=MIN(Ve1,Ve2)/"Ve1"/"Ve2", default "MIN", optional
    A1: float  # a1 in Ve1 = Vg + a1*Sum(Mn)/L, default 1, optional
    A2: float  # a2 in Ve2 = Vg + a2*Veq, default 2, optional


class ConcreteDesignCodeOptionJoint(TypedDict, total=False):
    """DCO's "SEISMIC.JOINT" — beam-column joint settings."""

    CHK_POS: str  # Select Check Position: "Top"/"Bottom", default "Bottom", optional
    EXCL_MEM_TYPES: List[str]  # Member Types excluded in Seismic Design: "SUBBEAM"/"CANTIL"/"UGBEAMCOL", default ["SUBBEAM","CANTIL","UGBEAMCOL"], optional


class ConcreteDesignCodeOptionSeismic(TypedDict, total=False):
    """DCO's "SEISMIC" — seismic design parameters, only meaningful when
    SEISMIC_PROV=true."""

    FRAME_TYPE: str  # Select Frame Type: "Special"=특수/"Intermediate"=중간/"Ordinary"=보통 모멘트골조, default "Special", optional
    STRONG_COL_WEAK_LAST: bool  # Consider strong column-weak beam on last floor, default true, optional
    SHEAR_WALL: ConcreteDesignCodeOptionShearWall  # Shear Wall Type configuration (FRAME_TYPE="Special"/"Intermediate"), optional
    SHEAR_DES: ConcreteDesignCodeOptionShearDes  # Shear for Design configuration, optional
    BEAM_COL_JNT_DES: bool  # Beam-Column Joint Design, default false, optional
    JOINT: ConcreteDesignCodeOptionJoint  # Beam-Column Joint configuration, optional


class ConcreteDesignCodeOptionPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #1 — DCO Specifications table."""

    DESIGN_CD: str  # Concrete design code standard, fixed "KDS 41 20 : 2022", required
    SEISMIC_PROV: bool  # Apply Special Provisions for Seismic Design, default false, optional
    TORS_DES: bool  # Torsion Design, default false, optional
    TORS_RDCT_FACT: float  # Torsion Reduction Factor for Beam (>=0, TORS_DES=true), default 1, optional
    MOM_REDIST_FACT: float  # Moment Redistribution Factor for Beam (>0, <=1), default 1, optional
    MOM_CALC_MTHD: str  # Moment Calculation Method for Beam: "Equivalent"=등가철근/"Each"=개별철근, default "Equivalent", optional
    USE_SUBDIV_FORCE: bool  # Use Subdivided Force for Beam Assigned as Member, default false, optional
    EXP_COND: str  # Exposure Condition (kcr): "Dry"/"etc", default "Dry", optional
    PM_CRV_CALC: str  # P-M Curve Calculation Method: "KeepPConstant"=P 고정/"KeepMPConstant"=M/P 고정, default "KeepMPConstant", optional
    UG_LC: bool  # Use Under Ground Load Combination Type for Under Ground Members, default true, optional
    CONC_STRS_STRN: str  # Concrete Stress-Strain Type for Bending: "Equivalent"=등가 사각형/"Parabola"=포물선-사각형 평균, default "Equivalent", optional
    FS_MAIN_BAR: str  # fs of Main bar in Beam Design: "2/3fy"/"ByProgram", default "2/3fy", optional
    SEISMIC: ConcreteDesignCodeOptionSeismic  # Seismic design parameters (SEISMIC_PROV=true), optional


class ConcreteDesignCodeOption(DbResource):
    ENDPOINT = f"{_BASE}/DCO"
    NAME = "Concrete Design Code Option"
    METHODS = GET_PUT_DELETE_METHODS


# --- 2. DESIGN/RC/KDS-41-20-2022/DCTL — Definition of Frame ------------------


class DefinitionOfFramePayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #2 — DCTL Specifications table."""

    FRAMEX: str  # X-Direction of Frame: "Unbraced Sway"/"Braced Non-sway", default "Braced Non-sway", optional
    FRAMEY: str  # Y-Direction of Frame: "Unbraced Sway"/"Braced Non-sway", default "Braced Non-sway", optional
    bAUTOKF: bool  # Auto Calculate Effective Length Factor, default false, optional
    DT: str  # Design Type: "3D"/"XZ"/"YZ"/"XY", default "3D", optional


class DefinitionOfFrame(DbResource):
    ENDPOINT = f"{_BASE}/DCTL"
    NAME = "Definition of Frame"
    METHODS = GET_PUT_DELETE_METHODS


# --- 3. DESIGN/RC/KDS-41-20-2022/LLRF — Live Load Reduction Factor -----------


class LiveLoadReductionDataItem(TypedDict, total=False):
    """LLRF's "REDUCTION_DATA" array entry."""

    STORY: str  # Story Name, required
    XMIN: float  # X Min coordinate, default 0, optional
    XMAX: float  # X Max coordinate, default 0, optional
    YMIN: float  # Y Min coordinate, default 0, optional
    YMAX: float  # Y Max coordinate, default 0, optional
    RANGE_MAX: float  # Range Max value (General Design Code only): one of 1/0.95/0.9/0.85/0.8/0.75/0.7/0.65/0.6/0.55/0.5, default 1, optional
    RANGE_MIN: float  # Range Min value (General Design Code only): same enum as RANGE_MAX, default 0.5, optional


class LiveLoadReductionFactorPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #3 — LLRF Specifications table."""

    CALC_RULE: int  # Calc Rule: by General Design Code=0/by Chinese Standard=1, default 0, optional
    APPLIED_COMP: List[str]  # Applied Components: "ALL"/"AXIAL"/"MOMENTS"/"SHEAR", default ["AXIAL"], optional
    LIVE_LOAD_CASES: List[str]  # Live Load Case Names (user defined list), optional
    REDUCTION_DATA: List[LiveLoadReductionDataItem]  # Live Load Reduction Factor Table Data, required


class LiveLoadReductionFactor(DbResource):
    ENDPOINT = f"{_BASE}/LLRF"
    NAME = "Live Load Reduction Factor"
    METHODS = GET_PUT_DELETE_METHODS


# --- 4. DESIGN/RC/KDS-41-20-2022/LCTB — Load Contribution for Nonlinear Load Case ---


class LoadContributionBaseItem(TypedDict, total=False):
    """LCTB's "BASE_ITEM" array entry."""

    FACTOR: float  # Factor, required
    LOAD_CASE_NAME: str  # Load Case Name, required


class LoadContributionForNonlinearLoadCasePayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #4 — LCTB Specifications table.

    GET/DELETE only (read-only derived info per the manual's own 기능 note).
    """

    NAME: str  # Load Contribution Name, required
    DESC: str  # Description, default "", optional
    BASE_ITEM: List[LoadContributionBaseItem]  # Load Contribution Items, required


class LoadContributionForNonlinearLoadCase(DbResource):
    ENDPOINT = f"{_BASE}/LCTB"
    NAME = "Load Contribution for Nonlinear Load Case"
    METHODS = GET_DELETE_METHODS


# --- 5. DESIGN/RC/KDS-41-20-2022/SRDF — Strength Reduction Factors -----------


class StrengthReductionFactorsPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #5 — SRDF Specifications table."""

    PHI_T: float  # For Tensile Control (phi_t), default 0.85, optional
    PHI_C1: float  # Member with Spiral Reinforcement (phi_c1), default 0.7, optional
    PHI_C2: float  # Other Reinforced Member (phi_c2), default 0.65, optional
    PHI_V: float  # For Shear and Torsion (phi_v), default 0.75, optional


class StrengthReductionFactors(DbResource):
    ENDPOINT = f"{_BASE}/SRDF"
    NAME = "Strength Reduction Factors"
    METHODS = GET_PUT_DELETE_METHODS


# --- 6. DESIGN/RC/KDS-41-20-2022/EQCT — Seismic Load Combination Type --------


class SeismicLoadCombinationTypePayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #6 — EQCT Specifications table."""

    TYPE: str  # Assign Member Type: "Special Seismic Loads"/"Vertical Seismic Forces", required


class SeismicLoadCombinationType(DbResource):
    ENDPOINT = f"{_BASE}/EQCT"
    NAME = "Seismic Load Combination Type"


# --- 7. DESIGN/RC/KDS-41-20-2022/ULCT — Underground Load Combination Type ----


class UndergroundLoadCombinationTypePayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #7 — ULCT Specifications table."""

    bUNDERLOADTYPE: bool  # Assign Member: For Underground Loads=true / For None-underground Loads=false, default false, optional


class UndergroundLoadCombinationType(DbResource):
    ENDPOINT = f"{_BASE}/ULCT"
    NAME = "Underground Load Combination Type"
    #: Gen-only: 404 (route + /info) on Civil NX, confirmed independently
    #: twice on 2026-07-29 — see db/base.py's GEN_ONLY docstring.
    PRODUCTS = GEN_ONLY


# --- 8. DESIGN/RC/KDS-41-20-2022/SUEQ — Scale up Factor for Earthquake -------


class ScaleUpFactorForEarthquakePayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #8 — SUEQ Specifications table."""

    LC_AXIAL: float  # Load Case - Axial Scale Factor, default 1, optional
    LC_MOMENT: float  # Load Case - Moment Scale Factor, default 1, optional
    LC_SHEAR: float  # Load Case - Shear Scale Factor, default 1, optional
    LCOM_AXIAL: float  # Load Combination - Axial Scale Factor, default 1, optional
    LCOM_MOMENT: float  # Load Combination - Moment Scale Factor, default 1, optional
    LCOM_SHEAR: float  # Load Combination - Shear Scale Factor, default 1, optional


class ScaleUpFactorForEarthquake(DbResource):
    ENDPOINT = f"{_BASE}/SUEQ"
    NAME = "Scale up Factor for Earthquake"


# --- 9. DESIGN/RC/KDS-41-20-2022/SDGN — Seismic Design Type ------------------


class SeismicDesignTypePayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #9 — SDGN Specifications table."""

    NTYPE: str  # Seismic design type assigned to the member: "Seismic"/"Non-Seismic"/"Non-Seismic-Force-Resisting", required


class SeismicDesignType(DbResource):
    ENDPOINT = f"{_BASE}/SDGN"
    NAME = "Seismic Design Type"


# --- 10. DESIGN/RC/KDS-41-20-2022/SCOL — Seismic Column Type -----------------


class SeismicColumnTypePayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #10 — SCOL Specifications table."""

    TYPE: str  # Story type classification: "PILOTI"/"SOFT_STORY", required


class SeismicColumnType(DbResource):
    ENDPOINT = f"{_BASE}/SCOL"
    NAME = "Seismic Column Type"


# --- 11. DESIGN/RC/KDS-41-20-2022/MBTP — Modify Member Type ------------------


class ModifyMemberTypePayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #11 — MBTP Specifications table."""

    TYPE: str  # Member Type: "COLUMN"=기둥/"BEAM"=보/"BRACE"=가새, required


class ModifyMemberType(DbResource):
    ENDPOINT = f"{_BASE}/MBTP"
    NAME = "Modify Member Type"


# --- 12. DESIGN/RC/KDS-41-20-2022/MEMB — Member Assignment -------------------


class MemberAssignmentPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #12 — MEMB Specifications table."""

    AELEM: List[int]  # Element Lists, required
    bREVERSE: bool  # Reverse Local Direction, default false, optional


class MemberAssignment(DbResource):
    ENDPOINT = f"{_BASE}/MEMB"
    NAME = "Member Assignment"
    METHODS = GET_PUT_DELETE_METHODS


# --- 13. DESIGN/RC/KDS-41-20-2022/MATD — Modify Concrete Material ------------

# Full concrete GRADE enum (CODE="Standard", STANDARD_CODE="KS19(RC)"),
# transcribed from the manual's own JSON Schema (not typed as a
# Literal/Enum, per this repo's TypedDict-only convention — no runtime
# validation):
#   C15, C18, C21, C24, C27, C30, C35, C40, C45, C49,
#   C50, C55, C60, C65, C70, C75, C80, C85, C90, C95
#
# Full rebar MAIN_REBAR_GRADE/SUB_REBAR_GRADE enum (CODE="Standard",
# STANDARD_CODE="KS19(RC)"):
#   SD300, SD400, SD500, SD600, SD700, SD400S, SD500S, SD600S


class ModifyConcreteMaterialConcrete(TypedDict, total=False):
    """MATD's "CONCRETE" object. CODE selects between the "Standard" field
    group (STANDARD_CODE/GRADE, with FC auto-filled by the server) and the
    "None" (user defined) field group (NAME/FC, all user input);
    LIGHTWEIGHT/LAMBDA are editable in both modes. Flattened onto one
    TypedDict (mirrors steel_kds.py's ModifySteelMaterialPayload precedent)."""

    CODE: str  # Concrete code type: "None"=user-defined/"Standard"=standard code, required
    STANDARD_CODE: str  # Concrete standard code (CODE="Standard"); currently only "KS19(RC)" is supported, conditionally required
    GRADE: str  # Concrete grade (CODE="Standard"); one of the 20 KS19(RC) grades listed above (C15-C95), conditionally required
    NAME: str  # User-defined concrete material name (CODE="None"), conditionally required
    FC: float  # Specified compressive strength (fc|fck) in kN/mm^2 — user input if CODE="None", auto-filled if CODE="Standard", conditionally required
    LIGHTWEIGHT: bool  # Whether the lightweight concrete factor (Lambda) is applied, editable for both CODE values, default false, optional
    LAMBDA: float  # Lambda value, editable for both CODE values, default 1, optional


class ModifyConcreteMaterialRebar(TypedDict, total=False):
    """MATD's "REBAR" object. CODE selects between the "Standard" field group
    (STANDARD_CODE/MAIN_REBAR_GRADE/SUB_REBAR_GRADE, with FY/FYS auto-filled
    by the server) and the "None" (user defined) field group
    (MAIN_REBAR_NAME/SUB_REBAR_NAME/FY/FYS, all user input)."""

    CODE: str  # Rebar code type: "None"=user-defined/"Standard"=standard code, required
    STANDARD_CODE: str  # Rebar standard code (CODE="Standard"); currently only "KS19(RC)" is supported, conditionally required
    MAIN_REBAR_GRADE: str  # Main rebar grade (CODE="Standard"); one of the 8 KS19(RC) grades listed above, conditionally required
    SUB_REBAR_GRADE: str  # Sub-rebar grade (CODE="Standard"); same enum as MAIN_REBAR_GRADE, conditionally required
    MAIN_REBAR_NAME: str  # User-defined main rebar name (CODE="None"), conditionally required
    SUB_REBAR_NAME: str  # User-defined sub-rebar name (CODE="None"), conditionally required
    FY: float  # Yield strength Fy of main rebar in kN/mm^2 — user input if CODE="None", auto-filled if CODE="Standard", conditionally required
    FYS: float  # Yield strength Fys of sub-rebar in kN/mm^2 — user input if CODE="None", auto-filled if CODE="Standard", conditionally required


class ModifyConcreteMaterialPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #13 — MATD Specifications table."""

    CONCRETE: ModifyConcreteMaterialConcrete  # Concrete material selection, required
    REBAR: ModifyConcreteMaterialRebar  # Rebar material selection, required


class ModifyConcreteMaterial(DbResource):
    ENDPOINT = f"{_BASE}/MATD"
    NAME = "Modify Concrete Material"
    METHODS = GET_PUT_DELETE_METHODS
    #: Gen-only: 404 (route + /info) on Civil NX, confirmed independently
    #: twice on 2026-07-29 — see db/base.py's GEN_ONLY docstring.
    PRODUCTS = GEN_ONLY


# --- 14. DESIGN/RC/KDS-41-20-2022/LENG — Unbraced Length (L, Lb) -------------


class UnbracedLengthPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #14 — LENG Specifications table."""

    LY: float  # Unbraced Length Ly, default 0, optional
    LZ: float  # Unbraced Length Lz, default 0, optional
    LB: float  # Laterally Unbraced Length, default 0, optional
    bNOTUSE: bool  # Do not consider of laterally unbraced length, default false, optional
    LT: float  # Torsional Unbraced Length, default 0, optional


class UnbracedLength(DbResource):
    ENDPOINT = f"{_BASE}/LENG"
    NAME = "Unbraced Length (L, Lb)"


# --- 15. DESIGN/RC/KDS-41-20-2022/KFAC — Effective Length Factor -------------


class EffectiveLengthFactorPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #15 — KFAC Specifications table."""

    Ky: float  # Effective Length Factor Ky, default 1, optional
    Kz: float  # Effective Length Factor Kz, default 1, optional
    Kt: float  # Effective Length Factor Kt, default 1, optional


class EffectiveLengthFactor(DbResource):
    ENDPOINT = f"{_BASE}/KFAC"
    NAME = "Effective Length Factor (K)"


# --- 16. DESIGN/RC/KDS-41-20-2022/CMFT — Equivalent Moment Correction Factor ---


class EquivalentMomentCorrectionFactorPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #16 — CMFT Specifications table."""

    OPT_AUTO: bool  # Auto Calculate, default false, optional
    CMY: float  # CMy, default 0, optional
    CMZ: float  # CMz, default 0, optional


class EquivalentMomentCorrectionFactor(DbResource):
    ENDPOINT = f"{_BASE}/CMFT"
    NAME = "Equivalent Moment Correction Factor(Cm)"


# --- 17. DESIGN/RC/KDS-41-20-2022/FMAG — Moment Magnifier --------------------


class MomentMagnifierPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #17 — FMAG Specifications table."""

    B1Y_DELTA_BY: float  # B1y - Delta by (First Order Moment Y), default 1, optional
    B1Z_DELTA_BZ: float  # B1z - Delta bz (First Order Moment Z), default 1, optional
    B2Y_DELTA_SY: float  # B2y - Delta sy (Second Order Moment Y), default 1, optional
    B2Z_DELTA_SZ: float  # B2z - Delta sz (Second Order Moment Z), default 1, optional


class MomentMagnifier(DbResource):
    ENDPOINT = f"{_BASE}/FMAG"
    NAME = "Moment Magnifier(B1/Delta_b, B2/Delta_s)"


# --- 18. DESIGN/RC/KDS-41-20-2022/MLLR — Modify Live Load Reduction Factor ---


class ModifyLiveLoadReductionComponents(TypedDict, total=False):
    """MLLR's "COMPONENTS" object."""

    AXIAL: bool  # Axial Force, default false, optional
    MOMENT: bool  # Moments, default false, optional
    SHEAR: bool  # Shear Forces, default false, optional


class ModifyLiveLoadReductionFactorPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #18 — MLLR Specifications table."""

    FACTOR: float  # Reduction Factor, range 0.3-1.0, default 1, optional
    COMPONENTS: ModifyLiveLoadReductionComponents  # Applied Components, optional


class ModifyLiveLoadReductionFactor(DbResource):
    ENDPOINT = f"{_BASE}/MLLR"
    NAME = "Modify Live Load Reduction Factor"


# --- 19. DESIGN/RC/KDS-41-20-2022/HCBM — Haunched Beam Assignment ------------


class HaunchPartSelector(TypedDict, total=False):
    """Shared element-input shape for HCBM's PART_A/PART_B/PART_C — use
    exactly one of KEYS (INPUT_METHOD="KEYS") or TO (INPUT_METHOD="TO").
    Unlike post/base.py's NodeElemsSelector, this has an explicit
    INPUT_METHOD discriminant and no STRUCTURE_GROUP_NAME option, so it is
    not reused from there (mirrors steel_kds.py's own local HaunchPartSelector,
    which is structurally identical but kept as a separate local copy here per
    this chapter's own manual text)."""

    INPUT_METHOD: str  # "KEYS"=Specify each Element ID / "TO"=Specify ID range, required
    KEYS: List[int]  # Specify each Element ID, minItems 1, required if INPUT_METHOD="KEYS"
    TO: str  # Specify ID range, e.g. "101 to 105", required if INPUT_METHOD="TO"


class HaunchedBeamAssignmentPayload(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #19 — HCBM Specifications table."""

    NAME: str  # Haunch Name, required
    PART_A: HaunchPartSelector  # Element No. Input for Part A (use only one method), required
    PART_B: HaunchPartSelector  # Element No. Input for Part B (structure identical to PART_A), required
    PART_C: HaunchPartSelector  # Element No. Input for Part C (structure identical to PART_A), required
    POS_TYPE: int  # Design Position Type: Part 1/2=0/User=1, required
    L1: float  # User defined L1 distance (POS_TYPE=1), default 1, optional
    L2: float  # User defined L2 distance (POS_TYPE=1), default 1, optional


class HaunchedBeamAssignment(DbResource):
    ENDPOINT = f"{_BASE}/HCBM"
    NAME = "Haunched Beam Assignment"
