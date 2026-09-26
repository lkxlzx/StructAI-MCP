"""Source: docs/manual/25_Design_Steel_KDS41302022.md, items 1-27.

Steel design code KDS 41 30:2022 — setup, per-member design parameters,
material overrides, and design-execution/result endpoints. Endpoint prefix:
``/DESIGN/STEEL/KDS-41-30-2022/<CODE>`` (not ``/db/*``).

The manual documents 3 method patterns and 4 endpoint groups (see the
chapter's own intro section):

1. Config-singleton (그룹 1/3 mostly) — no POST; PUT sets/updates the one
   record. Most of these use ``GET_PUT_DELETE_METHODS``; ``LCTB`` is
   GET/DELETE-only (``GET_DELETE_METHODS``).
2. Member-CRUD (그룹 2, plus a few 그룹 1 endpoints) — full POST/GET/PUT/
   DELETE, ID-keyed by element/member (the ``DbResource`` default).
3. POST-action (그룹 4) — design-execution/result-table/report/image
   endpoints; POST only, ``"Argument"``-wrapped (not ID-keyed ``"Assign"``),
   implemented as plain functions via ``post_argument`` (mirrors
   ``post/design.py`` and ``ope.py``/``view.py`` for deeply-nested bodies).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from ..client import MidasClient
from ..client import post_argument as _post
from ..db.base import GEN_ONLY, GET_DELETE_METHODS, GET_PUT_DELETE_METHODS, DbResource
from ..post.base import NodeElemsSelector, TableStyles, TableUnit

_BASE = "/DESIGN/STEEL/KDS-41-30-2022"


# --- 0. DESIGN/STEEL/DSTL — Steel Design Code Selection ---------------------
# Added to the manual 2026-09-06 — the chapter-level "which steel design code
# is active" selector, numbered "## 0." because it sits outside the
# KDS-41-30-2022/<CODE> numbering the other 27 endpoints share. It is the
# steel counterpart of rc_kds.setup.RcDesignCodeSelection.


class SteelDesignCodeSelectionPayload(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #0 — DSTL 파라미터 table.

    Unlike this chapter's other 27 endpoints, the URI carries no
    KDS-41-30-2022 prefix (``/DESIGN/STEEL/DSTL``). The manual's GET response
    is keyed ``"DSTL"``, where the RC counterpart's is ``"DCON"``;
    ``DbResource.items()`` unwraps by shape, so neither needs special-casing.

    Not the same endpoint as ``/db/DSTL`` (``db.design.SteelDesignCode``),
    which shares the name but has a different URI and schema — the manual
    says so explicitly.
    """

    DGNCODE: str  # Design Code, enum currently has one value "KDS 41 30 : 2022", required


class SteelDesignCodeSelection(DbResource):
    ENDPOINT = "/DESIGN/STEEL/DSTL"
    NAME = "Design Code"
    METHODS = GET_PUT_DELETE_METHODS


# === Group 1: 설계 코드·일반 설정 (config-singleton / member-CRUD) ===

# --- 1. DESIGN/STEEL/KDS-41-30-2022/DCO — Design Code Option ----------------


class SteelDesignCodeOptionPayload(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #1 — DCO Specifications table.

    SEIS_SYS's "Buckling-Restrained Braced Frames" value is hyphenated per
    this endpoint's own manual section (both its JSON Schema enum and
    Parameters table); note that SLRS's FRAME_TYPE (#19,
    SeismicLoadResistingSystemByMemberPayload) documents the same seismic
    system WITHOUT the hyphen ("Buckling Restrained Braced Frames") — a
    manual-internal spelling inconsistency between the two endpoints, not a
    transcription error here. Use each endpoint's own spelling verbatim.
    """

    DGNCODE: str  # Design Code, fixed "KDS 41 30 : 2022", required
    LAT_BRACE: bool  # All Beams/Girders are Laterally Braced, default false, optional
    DEFL_CHK: bool  # Check Beam/Column Deflection, default true, optional
    SEISMIC: bool  # Apply Special Provisions for Seismic Design, default false, optional
    COMB_RATIO: int  # Combined Ratio Method for Circular Section: SRSS=0/Linear Sum=1, default 0, optional
    SEIS_SYS: str  # Seismic Load Resisting System (SEISMIC=true): "Special Moment Frames"/"Intermediate Moment Frames"/"Ordinary Moment Frames"/"Special Concentrically Braced Frames"/"Ordinary Concentrically Braced Frames"/"Eccentrically Braced Frames"/"Buckling-Restrained Braced Frames"/"Special Plate Shear Walls", default "Special Moment Frames", conditionally required
    COL_WEAK: bool  # Consider strong column-weak beam on last floor, default true, optional
    UNDGR_LD: bool  # Use Under Ground Load Combination Type for Under Ground Members, default true, optional


class SteelDesignCodeOption(DbResource):
    ENDPOINT = f"{_BASE}/DCO"
    NAME = "Design Code Option"
    METHODS = GET_PUT_DELETE_METHODS


# --- 2. DESIGN/STEEL/KDS-41-30-2022/DCTL — Definition of Frame --------------


class DefinitionOfFramePayload(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #2 — DCTL Specifications table."""

    FRAMEX: str  # X-Direction of Frame: "Unbraced Sway"/"Braced Non-sway", default "Braced Non-sway", optional
    FRAMEY: str  # Y-Direction of Frame: "Unbraced Sway"/"Braced Non-sway", default "Braced Non-sway", optional
    bAUTOKF: bool  # Auto Calculate Effective Length Factor, default false, optional
    DT: str  # Design Type: "3D"/"XZ"/"YZ"/"XY", default "3D", optional


class DefinitionOfFrame(DbResource):
    ENDPOINT = f"{_BASE}/DCTL"
    NAME = "Definition of Frame"
    METHODS = GET_PUT_DELETE_METHODS


# --- 3. DESIGN/STEEL/KDS-41-30-2022/LLRF — Live Load Reduction Factor -------


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
    """docs/manual/25_Design_Steel_KDS41302022.md #3 — LLRF Specifications table."""

    CALC_RULE: int  # Calc Rule: by General Design Code=0/by Chinese Standard=1, default 0, optional
    APPLIED_COMP: List[str]  # Applied Components: "ALL"/"AXIAL"/"MOMENTS"/"SHEAR", default ["AXIAL"], optional
    LIVE_LOAD_CASES: List[str]  # Live Load Case Names (user defined list), optional
    REDUCTION_DATA: List[LiveLoadReductionDataItem]  # Live Load Reduction Factor Table Data, required


class LiveLoadReductionFactor(DbResource):
    ENDPOINT = f"{_BASE}/LLRF"
    NAME = "Live Load Reduction Factor"
    METHODS = GET_PUT_DELETE_METHODS


# --- 4. DESIGN/STEEL/KDS-41-30-2022/LCTB — Load Contribution for Nonlinear Load Case ---


class LoadContributionBaseItem(TypedDict, total=False):
    """LCTB's "BASE_ITEM" array entry."""

    FACTOR: float  # Factor, required
    LOAD_CASE_NAME: str  # Load Case Name, required


class LoadContributionForNonlinearLoadCasePayload(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #4 — LCTB Specifications table.

    GET/DELETE only (derived info; documented here for response-shape parity
    with the rest of this chapter).
    """

    NAME: str  # Load Contribution Name, required
    DESC: str  # Description, default "", optional
    BASE_ITEM: List[LoadContributionBaseItem]  # Load Contribution Items, required


class LoadContributionForNonlinearLoadCase(DbResource):
    ENDPOINT = f"{_BASE}/LCTB"
    NAME = "Load Contribution for Nonlinear Load Case"
    METHODS = GET_DELETE_METHODS


# --- 5. DESIGN/STEEL/KDS-41-30-2022/SRDF — Strength Reduction Factors -------


class StrengthReductionFactorsPayload(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #5 — SRDF Specifications table."""

    PHI_T1: float  # For Yielding in Gross Section (phi_t1), default 0.9, optional
    PHI_T2: float  # For Fracture in Net Section (phi_t2) — read-only fixed value 0.75, default 0.75, optional
    PHI_C: float  # For Compression Members (phi_c), default 0.9, optional
    PHI_B: float  # For Flexural Members (phi_b), default 0.9, optional
    PHI_V: float  # For Shear (phi_v), default 0.9, optional


class StrengthReductionFactors(DbResource):
    ENDPOINT = f"{_BASE}/SRDF"
    NAME = "Strength Reduction Factors"
    METHODS = GET_PUT_DELETE_METHODS


# --- 6. DESIGN/STEEL/KDS-41-30-2022/SERV — Serviceability Parameters --------


class ServiceabilityParametersPayload(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #6 — SERV Specifications table."""

    DEFLECT_CONTROL: float  # Deflection Control (span/n), default 300, optional
    DAF: float  # Deflection Amplification Factor, default 1, optional


class ServiceabilityParameters(DbResource):
    ENDPOINT = f"{_BASE}/SERV"
    NAME = "Serviceability Parameters"


# --- 7. DESIGN/STEEL/KDS-41-30-2022/EQCT — Seismic Load Combination Type ----


class SeismicLoadCombinationTypePayload(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #7 — EQCT Specifications table."""

    TYPE: str  # Assign Member Type: "Special Seismic Loads"/"Vertical Seismic Forces", required


class SeismicLoadCombinationType(DbResource):
    ENDPOINT = f"{_BASE}/EQCT"
    NAME = "Seismic Load Combination Type"


# --- 8. DESIGN/STEEL/KDS-41-30-2022/ULCT — Underground Load Combination Type ---


class UndergroundLoadCombinationTypePayload(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #8 — ULCT Specifications table."""

    bUNDERLOADTYPE: bool  # Assign Member: For Underground Loads=true / For None-underground Loads=false, default false, optional


class UndergroundLoadCombinationType(DbResource):
    ENDPOINT = f"{_BASE}/ULCT"
    NAME = "Underground Load Combination Type"
    #: Gen-only: 404 (route + /info) on Civil NX, confirmed independently
    #: twice on 2026-07-29 — see db/base.py's GEN_ONLY docstring.
    PRODUCTS = GEN_ONLY


# --- 9. DESIGN/STEEL/KDS-41-30-2022/SUEQ — Scale up Factor for Earthquake ---


class ScaleUpFactorForEarthquakePayload(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #9 — SUEQ Specifications table."""

    LC_AXIAL: float  # Load Case - Axial Scale Factor, default 1, optional
    LC_MOMENT: float  # Load Case - Moment Scale Factor, default 1, optional
    LC_SHEAR: float  # Load Case - Shear Scale Factor, default 1, optional
    LCOM_AXIAL: float  # Load Combination - Axial Scale Factor, default 1, optional
    LCOM_MOMENT: float  # Load Combination - Moment Scale Factor, default 1, optional
    LCOM_SHEAR: float  # Load Combination - Shear Scale Factor, default 1, optional


class ScaleUpFactorForEarthquake(DbResource):
    ENDPOINT = f"{_BASE}/SUEQ"
    NAME = "Scale up Factor for Earthquake"


# --- 10. DESIGN/STEEL/KDS-41-30-2022/CRCM — Combined Ratio Calculation Method for Circular Section ---


class CombinedRatioCalculationMethodPayload(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #10 — CRCM Specifications table."""

    METHOD: str  # Combined Strength Method: "SRSS"/"Linear Sum", required


class CombinedRatioCalculationMethodForCircularSection(DbResource):
    ENDPOINT = f"{_BASE}/CRCM"
    NAME = "Combined Ratio Calculation Method for Circular Section"


# === Group 2: 부재별 설계 파라미터 (member-CRUD) ===

# --- 11. DESIGN/STEEL/KDS-41-30-2022/HCBM — Haunched Beam Assignment --------


class HaunchPartSelector(TypedDict, total=False):
    """Shared element-input shape for HCBM's PART_A/PART_B/PART_C — use
    exactly one of KEYS (INPUT_METHOD="KEYS") or TO (INPUT_METHOD="TO").
    Unlike post/base.py's NodeElemsSelector, this has an explicit
    INPUT_METHOD discriminant and no STRUCTURE_GROUP_NAME option, so it is
    not reused from there."""

    INPUT_METHOD: str  # "KEYS"=Specify each Element ID / "TO"=Specify ID range, required
    KEYS: List[int]  # Specify each Element ID, minItems 1, required if INPUT_METHOD="KEYS"
    TO: str  # Specify ID range, e.g. "101 to 105", required if INPUT_METHOD="TO"


class HaunchedBeamAssignmentPayload(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #11 — HCBM Specifications table."""

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


# --- 12. DESIGN/STEEL/KDS-41-30-2022/LENG — Unbraced Length -----------------


class UnbracedLengthPayload(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #12 — LENG Specifications table."""

    LY: float  # Unbraced Length Ly, default 0, optional
    LZ: float  # Unbraced Length Lz, default 0, optional
    LB: float  # Laterally Unbraced Length, default 0, optional
    bNOTUSE: bool  # Do not consider of laterally unbraced length, default false, optional
    LT: float  # Torsional Unbraced Length, default 0, optional


class UnbracedLength(DbResource):
    ENDPOINT = f"{_BASE}/LENG"
    NAME = "Unbraced Length"


# --- 13. DESIGN/STEEL/KDS-41-30-2022/KFAC — Effective Length Factor ---------


class EffectiveLengthFactorPayload(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #13 — KFAC Specifications table."""

    Ky: float  # Effective Length Factor Ky, default 1, optional
    Kz: float  # Effective Length Factor Kz, default 1, optional
    Kt: float  # Effective Length Factor Kt, default 1, optional


class EffectiveLengthFactor(DbResource):
    ENDPOINT = f"{_BASE}/KFAC"
    NAME = "Effective Length Factor"


# --- 14. DESIGN/STEEL/KDS-41-30-2022/LTSR — Limiting Slenderness Ratio ------


class LimitingSlendernessRatioPayload(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #14 — LTSR Specifications table."""

    bNOTCHECK: bool  # Do not check for Slenderness Ratio, default false, optional
    COMP: float  # Limiting Slenderness Ratio for Compression, required
    TENS: float  # Limiting Slenderness Ratio for Tension, required


class LimitingSlendernessRatio(DbResource):
    ENDPOINT = f"{_BASE}/LTSR"
    NAME = "Limiting Slenderness Ratio"


# --- 15. DESIGN/STEEL/KDS-41-30-2022/CMFT — Equivalent Moment Correction Factor ---


class EquivalentMomentCorrectionFactorPayload(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #15 — CMFT Specifications table."""

    OPT_AUTO: bool  # Auto Calculate, default false, optional
    CMY: float  # CMy, default 0, optional
    CMZ: float  # CMz, default 0, optional


class EquivalentMomentCorrectionFactor(DbResource):
    ENDPOINT = f"{_BASE}/CMFT"
    NAME = "Equivalent Moment Correction Factor"


# --- 16. DESIGN/STEEL/KDS-41-30-2022/FMAG — Moment Magnifier ----------------


class MomentMagnifierPayload(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #16 — FMAG Specifications table."""

    B1Y_DELTA_BY: float  # B1y - Delta by (First Order Moment Y), default 1, optional
    B1Z_DELTA_BZ: float  # B1z - Delta bz (First Order Moment Z), default 1, optional
    B2Y_DELTA_SY: float  # B2y - Delta sy (Second Order Moment Y), default 1, optional
    B2Z_DELTA_SZ: float  # B2z - Delta sz (Second Order Moment Z), default 1, optional


class MomentMagnifier(DbResource):
    ENDPOINT = f"{_BASE}/FMAG"
    NAME = "Moment Magnifier"


# --- 17. DESIGN/STEEL/KDS-41-30-2022/CBFT — Bending Coefficient -------------


class BendingCoefficientPayload(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #17 — CBFT Specifications table."""

    AUTO_CAL: bool  # Auto Calculate by Program, default false, optional
    VALUE: float  # Bending Coefficient (Cb) Value (AUTO_CAL=false), default 1, optional


class BendingCoefficient(DbResource):
    ENDPOINT = f"{_BASE}/CBFT"
    NAME = "Bending Coefficient"


# --- 18. DESIGN/STEEL/KDS-41-30-2022/MBTP — Modify Member Type --------------


class ModifyMemberTypePayload(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #18 — MBTP Specifications table."""

    TYPE: str  # Member Type: "COLUMN"/"BEAM"/"BRACE", required


class ModifyMemberType(DbResource):
    ENDPOINT = f"{_BASE}/MBTP"
    NAME = "Modify Member Type"


# --- 19. DESIGN/STEEL/KDS-41-30-2022/SLRS — Seismic Load Resisting System by Member ---


class SeismicLoadResistingSystemByMemberPayload(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #19 — SLRS Specifications table.

    If FRAME_TYPE is "Buckling Restrained Braced Frames" or "Special Plate
    Shear Walls", CHECK_OPTION is forced to false (not supported for those
    two frame types).
    """

    FRAME_TYPE: str  # Seismic Load Resisting System Frame Type: "Special Concentrically Braced Frames"/"Ordinary Concentrically Braced Frames"/"Eccentrically Braced Frames"/"Buckling Restrained Braced Frames"/"Special Plate Shear Walls", required
    CHECK_OPTION: bool  # Check for Brace Slenderness Ratio / Check for Links (forced false for Buckling Restrained Braced Frames and Special Plate Shear Walls), default true, optional


class SeismicLoadResistingSystemByMember(DbResource):
    ENDPOINT = f"{_BASE}/SLRS"
    NAME = "Seismic Load Resisting System by Member"


# --- 20. DESIGN/STEEL/KDS-41-30-2022/MLLR — Modify Live Load Reduction Factor ---


class LiveLoadReductionComponents(TypedDict, total=False):
    """MLLR's "COMPONENTS" object."""

    AXIAL: bool  # Axial Force, default false, optional
    MOMENT: bool  # Moments, default false, optional
    SHEAR: bool  # Shear Forces, default false, optional


class ModifyLiveLoadReductionFactorPayload(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #20 — MLLR Specifications table."""

    FACTOR: float  # Reduction Factor, range 0.3-1.0, default 1, optional
    COMPONENTS: LiveLoadReductionComponents  # Applied Components, optional


class ModifyLiveLoadReductionFactor(DbResource):
    ENDPOINT = f"{_BASE}/MLLR"
    NAME = "Modify Live Load Reduction Factor"


# --- 21. DESIGN/STEEL/KDS-41-30-2022/MEMB — Member Assignment ---------------


class MemberAssignmentPayload(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #21 — MEMB Specifications table."""

    AELEM: List[int]  # Element Lists, required
    bREVERSE: bool  # Reverse Local Direction, default false, optional


class MemberAssignment(DbResource):
    ENDPOINT = f"{_BASE}/MEMB"
    NAME = "Member Assignment"
    METHODS = GET_PUT_DELETE_METHODS


# === Group 3: 재료 ===

# --- 22. DESIGN/STEEL/KDS-41-30-2022/SMODI — Modify Steel Material ----------

# Full KS22(S) GRADE enum (68 values), transcribed from the manual's JSON
# Schema (not typed as a Literal/Enum, per this repo's TypedDict-only
# convention — no runtime validation):
#   SS235, SS275, SS315, SS410, SS450, SS550,
#   SM275, SM355, SM420, SM460,
#   SM275TMC, SM355TMC, SM420TMC, SM460TMC,
#   SMA275A, SMA275B, SMA275C, SMA355A, SMA355B, SMA355C, SMA460,
#   HSM500,
#   SN275A, SN275B, SN275C, SN355, SN460,
#   SHN275, SHN355, SHN420, SHN460,
#   HSB380, HSB460, HSB690, HSA650,
#   SGT275, SGT355, SGT410, SGT450, SGT550,
#   SRT275, SRT355, SRT410, SRT450, SRT550,
#   SNT275, SNT355, SNT460,
#   SHT410, SHT460,
#   SNRT295E, SNRT390E, SNRT275A, SNRT355A,
#   SSC275,
#   SWH275, SWH355, SWH420, SWH460,
#   SF490, SF540,
#   SDP1, SDP2, SDP3,
#   SWPC1, SWPD1, SWPC, SWPD


class ModifySteelMaterialPayload(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #22 — SMODI Specifications table.

    CODE selects between the "Standard" field group (STANDARD_CODE/GRADE,
    with ES/PS/FU/FY1-5 auto-filled by the server) and the "None" (user
    defined) field group (NAME/ES/PS/FU/FY, all user input). Flattened onto
    one TypedDict (mirrors MaterialParam precedent).
    """

    CODE: str  # Steel material code type: "None"=user-defined/"Standard"=standard code, required
    STANDARD_CODE: str  # Steel standard code (CODE="Standard"); currently only "KS22(S)" is supported, conditionally required
    GRADE: str  # Steel grade (CODE="Standard"); one of the ~68 KS22(S) grades listed above, conditionally required
    NAME: str  # User-defined steel material name (CODE="None"), conditionally required
    ES: float  # Modulus of Elasticity (Es) — user input if CODE="None", auto-filled (read-only) if CODE="Standard", conditionally required
    PS: float  # Poisson's Ratio (Ps) — user input if CODE="None", auto-filled (read-only) if CODE="Standard", conditionally required
    FU: float  # Tensile Strength (Fu) — user input if CODE="None", auto-filled (read-only) if CODE="Standard", conditionally required
    FY: float  # Yield Strength (Fy) — required if CODE="None"
    FY1: float  # Yield Strength (Fy1) — auto-filled if CODE="Standard", optional
    FY2: float  # Yield Strength (Fy2) — auto-filled if CODE="Standard", optional
    FY3: float  # Yield Strength (Fy3) — auto-filled if CODE="Standard", optional
    FY4: float  # Yield Strength (Fy4) — auto-filled if CODE="Standard", optional
    FY5: float  # Yield Strength (Fy5) — auto-filled if CODE="Standard", optional


class ModifySteelMaterial(DbResource):
    ENDPOINT = f"{_BASE}/SMODI"
    NAME = "Modify Steel Material"
    METHODS = GET_PUT_DELETE_METHODS


# === Group 4: 설계 수행·결과 (POST-action, "Argument"-wrapped, not ID-keyed) ===

# --- 23. DESIGN/STEEL/KDS-41-30-2022/CODE-ANAL — Steel Code Check Perform ---


class PerformSteelCodeCheckArgument(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #23 — CODE-ANAL Argument.

    Exactly one of ELEMS/SECTIONS is used when PERFORM_TYPE is "ELEMS"/
    "SECTIONS"; PERFORM_TYPE="ALL" needs neither. ELEMS reuses
    post/base.py's NodeElemsSelector (identical KEYS/TO/STRUCTURE_GROUP_NAME
    shape — use exactly one of its three keys).
    """

    PERFORM_TYPE: str  # Target type: "ALL"=all elements/"ELEMS"=by element no./"SECTIONS"=by section no., default "ALL", optional
    ELEMS: NodeElemsSelector  # Element No. Input, required if PERFORM_TYPE="ELEMS"
    SECTIONS: List[int]  # Section No. Input, required if PERFORM_TYPE="SECTIONS"


def perform_steel_code_check(
    argument: PerformSteelCodeCheckArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/25_Design_Steel_KDS41302022.md #23 — CODE-ANAL — Steel Code
    Check Perform. Executes the design calculation; response is
    ``{"message": "success"}`` on success.

    ⚠️ Never independently tested. The RC equivalent
    (``design.rc_kds.checks.perform_column_check``, CC-ANAL) was confirmed
    to hang Gen NX 2026 (v2.1), build 06/23/2026 (stuck at "Converting
    Design Results... 0%", required a forced process kill), then ran clean
    on that same build on 2026-07-25 — the trigger is unidentified, not
    fixed; see docs/live_verification_notes.md. Every test on both sides
    used the **KDS 41 20:2022 RC** code, so nothing is confirmed either way
    for this steel-code path. Use a short timeout and read
    ``get_steel_code_check_table`` regardless of whether this call returns.
    """
    return _post(f"{_BASE}/CODE-ANAL", argument, client)


# --- 24. DESIGN/STEEL/KDS-41-30-2022/CODE-TABLE — Steel Code Check Table ----


class SteelCodeCheckTableArgument(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #24 — CODE-TABLE Argument.

    Exactly one of ELEMS/SECTIONS is required (oneOf). ELEMS/UNIT/STYLES
    reuse post/base.py's NodeElemsSelector/TableUnit/TableStyles (identical
    shapes).
    """

    TABLE_TYPE: str  # Result Table Type: "MEMB"=member-based/"PROP"=section-based, required
    ELEMS: NodeElemsSelector  # Element No. Input, required if not using SECTIONS
    SECTIONS: List[int]  # Section No. Input, required if not using ELEMS
    PRI_SORT: int  # Primary sort for member-based output: SECT=0/MEMB=1, default 1, optional
    RESULT: int  # Filter by check status: All=0/OK=1/NG=2, default 0, optional
    VIEW_RATPC: bool  # Filter to show only members with RatPc > 0.4, default false, optional
    TABLE_NAME: str  # Response Table Title, default "", optional
    EXPORT_PATH: str  # Result Table Save Path, optional
    UNIT: TableUnit  # Response Unit Setting (FORCE/DIST/HEAT/TEMP), optional
    STYLES: TableStyles  # Response Number Format (FORMAT/PLACE), optional
    COMPONENTS: List[str]  # Result table components, e.g. "CHK"/"MEMB"/"COM"/"SECT"/"SHR"/"Section"/"Material"/"Fy"/"LCB"/"Len"/"Lb"/"Ly"/"Lz"/"Cb"/"Ky"/"Kz"/"B1y"/"B1z"/"B2y"/"B2z"/"RatPc"/"Pu"/"pPn"/"Muy"/"pMny"/"Muz"/"pMnz"/"Vuy"/"pVny"/"Vuz"/"pVnz"/"Tu"/"pTn"/"Def"/"Defa", optional


def get_steel_code_check_table(
    argument: SteelCodeCheckTableArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/25_Design_Steel_KDS41302022.md #24 — CODE-TABLE — Steel Code
    Check Table. Response: ``{table_name_or_"Result Table": {"FORCE": ...,
    "DIST": ..., "HEAD": [...], "DATA": [[...], ...]}}``."""
    return _post(f"{_BASE}/CODE-TABLE", argument, client)


# --- 25. DESIGN/STEEL/KDS-41-30-2022/CODE-REPORT — Steel Code Check Report --


class SteelCodeCheckReportArgument(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #25 — CODE-REPORT Argument.

    Exactly one of ELEMS/SECTIONS is required (oneOf). ELEMS reuses
    post/base.py's NodeElemsSelector.
    """

    REPORT_TYPE: str  # Report Table Type: "MEMB"/"PROP", required
    CURRENT_MODE: str  # Report output mode: "Graphic"=JPG image/"Detail"=DOC document/"Summary"=TXT text, required
    ELEMS: NodeElemsSelector  # Element No. Input, required if not using SECTIONS
    SECTIONS: List[int]  # Section No. Input, required if not using ELEMS
    EXPORT_PATH: str  # Directory path to save the report files, required
    OUTPUT_NAME: str  # Output file base name (multi-element runs prefix index+element no., e.g. "001_E859_filename.jpg"), required


def export_steel_code_check_report(
    argument: SteelCodeCheckReportArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/25_Design_Steel_KDS41302022.md #25 — CODE-REPORT — Steel
    Code Check Report. Response: ``{"SUCCESS": bool, "FILE_PATH": str,
    "MESSAGE": str}``."""
    return _post(f"{_BASE}/CODE-REPORT", argument, client)


# --- 26. DESIGN/STEEL/KDS-41-30-2022/DREULT — Steel Design Result -----------


class SteelDesignResultAngle(TypedDict, total=False):
    """RESULT_GRAPHIC-sibling "ANGLE" — view angle settings."""

    HORIZONTAL: float  # Horizontal rotation angle, default 0, optional
    VERTICAL: float  # Vertical rotation angle, default 0, optional


class SteelDesignResultRgbColor(TypedDict, total=False):
    """"BGCOLOR_TOP" — RGB color triple."""

    R: int  # Red component, 0-255, optional
    G: int  # Green component, 0-255, optional
    B: int  # Blue component, 0-255, optional


class SteelDesignResultLoadCaseComb(TypedDict, total=False):
    """RESULT_GRAPHIC's "LOAD_CASE_COMB"."""

    TYPE: str  # Load case type, fixed "CBS"=Steel Design Load Combination, required
    NAME: str  # Load case or combination name, required


class SteelDesignResultComponents(TypedDict, total=False):
    """RESULT_GRAPHIC's "COMPONENTS"."""

    COMP: str  # Design component to display: "Axial"/"Shear-y"/"Shear-z"/"Bend-y"/"Bend-z"/"Combined", default "Combined", optional


class SteelDesignResultContourOptions(TypedDict, total=False):
    """TYPE_OF_DISPLAY.CONTOUR's "OPTIONS"."""

    GRADIENT_FILL: bool  # Use gradient fill, default false, optional
    CONTOUR_FILL: bool  # Use contour fill, default true, optional


class SteelDesignResultContour(TypedDict, total=False):
    """RESULT_GRAPHIC.TYPE_OF_DISPLAY's "CONTOUR"."""

    OPT_CHECK: bool  # Enable contour display, default false, optional
    NUM_OF_COLOR: int  # Number of contour colors, 2-20, default 12, optional
    COLOR_TYPE: str  # Contour color type: "vrgb"/"rgb"/"rbg"/"gray scaled", default "vrgb", optional
    OPTIONS: SteelDesignResultContourOptions  # Contour options, optional


class SteelDesignResultMinMaxOnly(TypedDict, total=False):
    """TYPE_OF_DISPLAY.VALUES's "MINMAX_ONLY"."""

    MAXMIN: str  # Min/max display mode: "Min & Max"/"Abs Max"/"max"/"min", default "Min & Max", optional
    LIMIT_SCALE: int  # Scale limit, default 0, optional


class SteelDesignResultValues(TypedDict, total=False):
    """RESULT_GRAPHIC.TYPE_OF_DISPLAY's "VALUES"."""

    OPT_CHECK: bool  # Enable value display, default false, optional
    DECIMAL_PT: int  # Decimal places, 0-15, default 0, optional
    VALUE_EXP: bool  # Use exponential notation, default false, optional
    MINMAX_ONLY: SteelDesignResultMinMaxOnly  # Min/max display settings, optional
    SET_ORIENT: int  # Value text orientation, default 0, optional


class SteelDesignResultLegend(TypedDict, total=False):
    """RESULT_GRAPHIC.TYPE_OF_DISPLAY's "LEGEND"."""

    OPT_CHECK: bool  # Enable legend display, default false, optional
    POSITION: str  # Legend position: "right"/"left"/"top"/"bottom", default "left", optional
    VALUE_EXP: bool  # Use exponential notation for legend values, default true, optional
    DECIMAL_PT: int  # Decimal places for legend values, 0-15, default 0, optional


class SteelDesignResultDisplayMembers(TypedDict, total=False):
    """TYPE_OF_DISPLAY.CODE_CHECKING_RATIO's "DISPLAY_MEMBERS"."""

    BEAM: bool  # Display beam members, default true, optional
    COLUMN: bool  # Display column members, default true, optional
    BRACE: bool  # Display brace members, default true, optional


class SteelDesignResultColumnSectionSize(TypedDict, total=False):
    """TYPE_OF_DISPLAY.CODE_CHECKING_RATIO's "COLUMN_SECTION_SIZE"."""

    SCALE_FACTOR: float  # Scale factor for column section visualization, 0.1-100, default 1, optional


class SteelDesignResultValueOption(TypedDict, total=False):
    """TYPE_OF_DISPLAY.CODE_CHECKING_RATIO's "VALUE_OPTION"."""

    DECIMAL_PLACES: int  # Number of decimal places, 0-15, default 2, optional
    EXPONENTIAL: bool  # Use exponential notation, default false, optional


class SteelDesignResultCodeCheckingRatio(TypedDict, total=False):
    """RESULT_GRAPHIC.TYPE_OF_DISPLAY's "CODE_CHECKING_RATIO"."""

    CHECK: bool  # Enable code checking ratio display, default true, optional
    DISPLAY_MEMBERS: SteelDesignResultDisplayMembers  # Steel member types to display, optional
    COLUMN_SECTION_SIZE: SteelDesignResultColumnSectionSize  # Column section size display settings, optional
    VALUE_OPTION: SteelDesignResultValueOption  # Value display format settings, optional


class SteelDesignResultTypeOfDisplay(TypedDict, total=False):
    """RESULT_GRAPHIC's "TYPE_OF_DISPLAY"."""

    CONTOUR: SteelDesignResultContour  # Contour display settings, optional
    VALUES: SteelDesignResultValues  # Value display settings, optional
    LEGEND: SteelDesignResultLegend  # Legend display settings, optional
    CODE_CHECKING_RATIO: SteelDesignResultCodeCheckingRatio  # Steel code checking ratio display settings, optional


class SteelDesignResultGraphic(TypedDict, total=False):
    """"RESULT_GRAPHIC" — result graphic display settings."""

    CURRENT_MODE: str  # Current mode, fixed "INFLL_DESIGN_STEEL"=Steel Design, required
    LOAD_CASE_COMB: SteelDesignResultLoadCaseComb  # Load cases and combinations, required
    COMPONENTS: SteelDesignResultComponents  # Component selection for design result display, optional
    TYPE_OF_DISPLAY: SteelDesignResultTypeOfDisplay  # Display options for design result visualization, optional


class SteelDesignResultArgument(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #26 — DREULT Argument.

    ACTIVE/DISPLAY sub-fields are not detailed in this chapter (the manual
    refers to the separate Active/Display documentation), so they are typed
    as free-form dicts here rather than invented nested TypedDicts (mirrors
    view.py's UNDEFORMED/YIELD_POINT/MODE_SHAPE precedent).
    """

    EXPORT_PATH: str  # Image file save path and file name, required
    FIGURE_NAME: str  # Smart report image name, optional
    SET_HIDDEN: bool  # Hidden option, default false, optional
    ACTIVE: Dict[str, Any]  # View/Active settings; sub-fields undocumented in this chapter, optional
    WIDTH: int  # Image width in pixels, 100-10000, default 1000, optional
    HEIGHT: int  # Image height in pixels, 100-10000, default 1000, optional
    STAGE_NAME: str  # Construction stage name, optional
    ANGLE: SteelDesignResultAngle  # View angle settings, optional
    DISPLAY: Dict[str, Any]  # View/Display settings; sub-fields undocumented in this chapter, optional
    PERSPECTIVE: bool  # Enable perspective view, default false, optional
    ZOOM_LEVEL: float  # Zoom level, 25-200, default 100, optional
    BGCOLOR_TOP: SteelDesignResultRgbColor  # Top background color, optional
    RESULT_GRAPHIC: SteelDesignResultGraphic  # Result graphic display settings, required


def export_steel_design_result_image(
    argument: SteelDesignResultArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/25_Design_Steel_KDS41302022.md #26 — DREULT — Steel Design
    Result. Captures/saves the steel design result view as a JPG image.
    Response: ``{"message": "MIDAS GEN NX command complete"}``."""
    return _post(f"{_BASE}/DREULT", argument, client)


# --- 27. DESIGN/STEEL/KDS-41-30-2022/TABLE — Steel Member Design Forces -----


class SteelMemberDesignForcesArgument(TypedDict, total=False):
    """docs/manual/25_Design_Steel_KDS41302022.md #27 — TABLE Argument.

    NODE_ELEMS/UNIT/STYLES reuse post/base.py's NodeElemsSelector/TableUnit/
    TableStyles (identical shapes).
    """

    TABLE_NAME: str  # Response Table Title, default "", optional
    TABLE_TYPE: str  # Result Table Type, fixed "STEELMEMBERDESIGNFORCES", required
    EXPORT_PATH: str  # Result Table Save Path, optional
    UNIT: TableUnit  # Response Unit Setting (FORCE/DIST/HEAT/TEMP), default "System", optional
    STYLES: TableStyles  # Response Number Format (FORMAT/PLACE), default "System", optional
    COMPONENTS: List[str]  # Result table components: "Index"/"Memb"/"Part"/"LComName"/"Type"/"Fx"/"Fy"/"Fz"/"Mx"/"My"/"Mz", optional
    NODE_ELEMS: NodeElemsSelector  # Node/Element No. Input, optional
    PARTS: List[str]  # Element Part Number: "PartI"/"Part1/4"/"Part2/4"/"Part3/4"/"PartJ", default ["All"], optional


def get_steel_member_design_forces_table(
    argument: SteelMemberDesignForcesArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/25_Design_Steel_KDS41302022.md #27 — TABLE — Steel Member
    Design Forces. Response: ``{table_name_or_"empty": {"FORCE": ...,
    "DIST": ..., "HEAD": [...], "DATA": [[...], ...]}}``.

    Shares the ``TABLE_TYPE``-crash pattern seen across this whole
    Design-Forces family — presumed at risk on
    Gen until independently confirmed on real data. Re-tested 2026-08-11
    on Gen NX (v2.1, build 08/11/2026), blank ``/doc/NEW`` document,
    ``{"TABLE_TYPE": "STEELMEMBERDESIGNFORCES"}``: clean empty response,
    no crash, session stayed healthy. A single clean pass is not
    independent proof the risk is gone — treat as reduced-but-not-cleared
    until a real-model retest.
    """
    return _post(f"{_BASE}/TABLE", argument, client)
