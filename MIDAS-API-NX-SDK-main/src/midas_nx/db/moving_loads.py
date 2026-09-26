"""Source: docs/manual/08_DB_Moving_Loads.md, items 1-28.

Framed by the manual as bridge live-load analysis (moving-load / traffic-lane
/ vehicle / dynamic-factor definitions), historically declared Civil NX only
across this whole chapter. Live-checked 2026-07-29 against a real production
Gen NX model: most of these endpoints answer on Gen too (route + `/info`
schema both resolve, if usually to an empty table since a Gen model has no
bridge data) and are left at the class default (gen+civil) — only
`CIVIL_ONLY` remains where Gen genuinely 404s: `ConcurrentReactionGroup`
(CRGR), `ConcurrentJointForceGroup` (CJFG), `DynamicLoadAllowance` (DYLA),
`RailwayDynamicFactor` (DYFG), `RailwayDynamicFactorByElement` (DYNF). That
the API accepts a call doesn't mean using bridge/moving-load features from a
Gen NX session is a sound engineering choice for a given project — that's a
judgment call for the engineer, not something this SDK's `PRODUCTS` should
gate. See db/base.py's `GEN_ONLY` docstring's sibling note and
docs/live_verification_notes.md for the full evidence.
"""
from __future__ import annotations

from typing import Any, List, Optional, TypedDict

from ..client import MidasClient, MidasRequestError
from .base import CIVIL_ONLY, DbResource

# --- 1. /db/MVCD — Moving Load Code ------------------------------------------


class MovingLoadCodePayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #1 — /db/MVCD Specifications table.

    CODE values: "KSCE-LSD15"/"KOREA"/"AASHTO STANDARD"/"AASHTO LRFD"/
    "AASHTO LRFD(PENDOT)"/"CHINA"/"INDIA"/"TAIWAN"/"CANADA"/"BS"/"EUROCODE"/
    "AUSTRALIA"/"POLAND"/"RUSSIA"/"SOUTH AFRICA"/"TRANS".
    """

    CODE: str  # Moving Load Code, required


class MovingLoadCode(DbResource):
    ENDPOINT = "/db/MVCD"
    NAME = "Moving Load Code"


# --- 2. /db/LLAN — Traffic Line Lanes ----------------------------------------


class LineLaneCommon(TypedDict, total=False):
    """Shared "COMMON" object used by LLAN/LLANch/LLANid (identical shape)."""

    LL_NAME: str  # Name of Line Lane, required
    WIDTH: float  # Lane Width, required (valid only for Eurocode/Australia/Poland/BS/Russia/South Africa)
    WHEEL_SPACE: float  # Wheel Spacing, default 0, optional
    OPT_AUTO_LANE: bool  # Transverse Lane Optimization, default false, optional (not available for Taiwan)
    ALLOW_WIDTH: float  # Allow Width for Optimization, optional (not available for Taiwan)
    LOAD_DIST: str  # Load Distribution: "LANE"/"CROSS", required
    GROUP_NAME: str  # Structure Group Name, default "", optional (used when LOAD_DIST="CROSS")
    SKEW_START: float  # Skew Start, default 0, optional (used when LOAD_DIST="CROSS")
    SKEW_END: float  # Skew End, default 0, optional (used when LOAD_DIST="CROSS")
    MOVING: str  # Moving Direction: "FORWARD"/"BACKWARD"/"BOTH", required


class LineLaneItem(TypedDict, total=False):
    """LANE_ITEMS entry for /db/LLAN. Fields beyond ELEM/ECC are code-dependent
    (see 08_DB_Moving_Loads.md #2 "LANE_ITEMS (코드별 추가 필드)" table);
    flattened onto one item (mirrors MaterialParam precedent).

    ⚠️ Live-tested: with MVCD.CODE="AASHTO LRFD", omitting CENT_F (which
    this schema marks merely optional) gets rejected server-side —
    "Centrifugal Force ( 0.0 < Value < 1.0)" — because the omitted field
    defaults to 0.0, which fails the code's own (0, 1) exclusive-range
    validation. Pass a nonzero CENT_F whenever MVCD.CODE is "AASHTO LRFD".
    See docs/live_verification_notes.md for the reproduction.

    ⚠️ CENT_F is documented (and was believed here) to be AASHTO-LRFD-only,
    but two independent real production models contradict that: a
    Eurocode-coded railway bridge (2026-07-30) has the identical populated
    value (CENT_F: 0.5) on every LANE_ITEMS entry, same as the AASHTO LRFD
    arch-bridge model that originally motivated the note above. Whether
    this reflects a genuine cross-code field or is simply always echoed
    back regardless of the selected code (as ECCEN_VERT_LOAD/FACT/WIDTH
    have also been seen to be, populated-but-inert, on codes that don't use
    them) is not yet resolved — treat "AASHTO LRFD only" below as unverified
    rather than corrected.
    """

    ELEM: int  # Element No., required
    ECC: float  # Eccentricity, optional (KSCE-LSD15/Canada/BS/Russia/South Africa/Korea/AASHTO Standard/Taiwan/AASHTO LRFD/PENNDOT/Eurocode/Australia/Poland)
    FACT: float  # Impact Factor, optional (Korea/AASHTO Standard/Taiwan only)
    SPAN_START: bool  # Span Start, optional (Korea/AASHTO Standard/Taiwan/AASHTO LRFD/PENNDOT/Australia/Poland only)
    CENT_F: float  # Centrifugal Force Factor, documented AASHTO-LRFD-only but seen populated on Eurocode too — see class docstring; effectively required and nonzero when MVCD.CODE="AASHTO LRFD"
    ECCEN_VERT_LOAD: float  # Eccentricity Considering Cant (vertical load), optional (Eurocode only)


class TrafficLineLanePayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #2 — /db/LLAN Specifications table."""

    COMMON: LineLaneCommon  # required
    LANE_ITEMS: List[LineLaneItem]  # required


class TrafficLineLanes(DbResource):
    ENDPOINT = "/db/LLAN"
    NAME = "Traffic Line Lanes"


# --- 3. /db/LLANch — Traffic Line Lanes – China ------------------------------


class LineLaneChinaItem(TypedDict, total=False):
    ELEM: int  # Element No., required
    ECC: float  # Eccentricity, default 0, optional
    SPAN: float  # Span Length, default 0, optional
    SPAN_START: bool  # Span Start, default false, optional
    SCALE_FACTOR: float  # Scale Factor, default 0, optional


class TrafficLineLanesChinaPayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #3 — /db/LLANch Specifications table.

    COMMON has the same structure as /db/LLAN's COMMON (LineLaneCommon).
    """

    COMMON: LineLaneCommon  # required
    LANE_ITEMS: List[LineLaneChinaItem]  # required


class TrafficLineLanesChina(DbResource):
    ENDPOINT = "/db/LLANch"
    NAME = "Traffic Line Lanes – China"


# --- 4. /db/LLANid — Traffic Line Lanes – India ------------------------------


class LineLaneIndiaItem(TypedDict, total=False):
    ELEM: int  # Element No., required
    ECC: float  # Eccentricity, default 0, optional
    IMPACT_SPAN: int  # Option: IF/CDA=0, Span Length=1, default 0, optional
    IMPACT_FACTOR: float  # Scale Factor, default 0, optional (when IMPACT_SPAN=0)
    SPAN: float  # Span Length, default 0, optional (when IMPACT_SPAN=1)


class TrafficLineLanesIndiaPayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #4 — /db/LLANid Specifications table.

    COMMON has the same structure as /db/LLAN's COMMON (LineLaneCommon).
    """

    COMMON: LineLaneCommon  # required
    LANE_ITEMS: List[LineLaneIndiaItem]  # required


class TrafficLineLanesIndia(DbResource):
    ENDPOINT = "/db/LLANid"
    NAME = "Traffic Line Lanes – India"


# --- 5. /db/LLANtr — Traffic Line Lanes – Transverse -------------------------


class LineLaneTransverseItem(TypedDict, total=False):
    ELEM: int  # Element ID, required
    FACTOR: float  # Factor, required


class SpecialLineLaneTransverseItem(TypedDict, total=False):
    """One entry of /db/LLANtr's SPECIAL_LANE_ITEMS.

    Undocumented: `GET /info/db/LLANtr` declares the array and describes it
    " Used only when importing", which is the whole of what is known about
    when it applies. MD-45.
    """

    ELEMS: List[int]  # Key Elements
    FACTOR: float  # Factor


class TrafficLineLanesTransversePayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #5 — /db/LLANtr Specifications table."""

    LL_NAME: str  # Name of Line Lane, required
    LANE_ITEMS: List[LineLaneTransverseItem]  # required
    SPECIAL_LANE_ITEMS: List[SpecialLineLaneTransverseItem]  # see above; MD-45


class TrafficLineLanesTransverse(DbResource):
    ENDPOINT = "/db/LLANtr"
    NAME = "Traffic Line Lanes – Transverse"


# --- 6. /db/LLANop — Traffic Line Lanes – Moving Load Optimization ----------


class TrafficLineLanesOptimizationPayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #6 — /db/LLANop Specifications table.

    LANE_ITEMS has the same code-dependent-fields shape as /db/LLAN's
    LANE_ITEMS (LineLaneItem) — the manual describes both as "ELEM, ECC,
    code-dependent additional fields".
    """

    LL_NAME: str  # Name of Line Lane, required
    LOAD_DIST: str  # Load Distribution: "LANE"/"CROSS", required
    GROUP_NAME: str  # Structure Group Name, default "", optional
    SKEW_START: float  # Skew Start, default 0, optional
    SKEW_END: float  # Skew End, default 0, optional
    MOVING: str  # Moving Direction, required
    OPTIM_WIDTH: float  # Optimization Width, required
    LANE_WIDTH: float  # Lane Width, required
    OFFSET_TYPE: int  # Offset Type: Fixed=0/Division=1, required
    DIVIDE_NUM: int  # Number of Division, optional
    ANAL_LANE_OFFSET: float  # Analysis Lane Offset, optional
    WHEEL_SPACE: float  # Wheel Spacing, default 0, optional
    MARGIN: float  # Margin, default 0, optional
    LANE_ITEMS: List[LineLaneItem]  # required


class TrafficLineLanesOptimization(DbResource):
    ENDPOINT = "/db/LLANop"
    NAME = "Traffic Line Lanes – Moving Load Optimization"


# --- 7. /db/SLAN — Traffic Surface Lanes -------------------------------------


class SurfaceLaneItem(TypedDict, total=False):
    """LANE_ITEMS entry for /db/SLAN. Fields beyond NODE/OFFSET are
    code-dependent (see 08_DB_Moving_Loads.md #7 "LANE_ITEMS (코드별 추가
    필드)" table); flattened onto one item (mirrors MaterialParam precedent).
    """

    NODE: int  # Node No., required
    OFFSET: float  # Offset Distance to Lane Center, default 0, optional
    IMPACT_FACTOR: float  # Impact Factor, optional (Korea/AASHTO Standard/Taiwan only)
    bSPAN_START: bool  # Span Start, optional (Korea/AASHTO Standard/Taiwan/AASHTO LRFD/PENNDOT/Australia/Poland only)
    CENTRI_FORCE: float  # Centrifugal Force, optional (AASHTO LRFD only)
    IMPACT_SPAN_TYPE: Any  # Impact method selector, optional (India only; manual does not detail values)
    IMPACT_FACTOR_INDIA: float  # Impact Factor, optional (India only)
    SPAN_LENGTH: float  # Span Length, optional (India only)
    ECCEN_VERT_LOAD: float  # Eccentricity Considering Cant (vertical load), optional (Eurocode only)


class TrafficSurfaceLanePayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #7 — /db/SLAN Specifications table."""

    NAME: str  # Name of Surface Lane, required
    WIDTH: float  # Lane Width, required
    WHEEL_SPACE: float  # Wheel Spacing, default 0, optional
    SKEW_START: float  # Skew Start, default 0, optional
    SKEW_END: float  # Skew End, default 0, optional
    bOPTIMIZE: bool  # Transverse Lane Optimization, default false, optional (not available for India/Taiwan)
    ALLOW_WIDTH: float  # Allow Width for Optimization, default 0, optional (not available for India/Taiwan)
    MV_DIR: str  # Moving Direction: "FORWARD"/"BACKWARD"/"BOTH", required
    SEQ: int  # Sequence Number (unique), default 1, optional
    LANE_ITEMS: List[SurfaceLaneItem]  # required


class TrafficSurfaceLanes(DbResource):
    ENDPOINT = "/db/SLAN"
    NAME = "Traffic Surface Lanes"


# --- 8. /db/SLANch — Traffic Surface Lanes – China ---------------------------


class SurfaceLaneChinaItem(TypedDict, total=False):
    NODE: int  # Node No., required
    OFFSET: float  # Offset Distance to Lane Center, default 0, optional
    SPAN_LENGTH: float  # Span Length, default 0, optional


class TrafficSurfaceLanesChinaPayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #8 — /db/SLANch Specifications table.

    Top-level fields have the same structure as /db/SLAN.
    """

    NAME: str  # Name of Surface Lane, required
    WIDTH: float  # Lane Width, required
    WHEEL_SPACE: float  # Wheel Spacing, default 0, optional
    SKEW_START: float  # Skew Start, default 0, optional
    SKEW_END: float  # Skew End, default 0, optional
    bOPTIMIZE: bool  # Transverse Lane Optimization, default false, optional
    ALLOW_WIDTH: float  # Allow Width for Optimization, default 0, optional
    MV_DIR: str  # Moving Direction, required
    SEQ: int  # Sequence Number (must be unique); /info declares it and the manual documents it nowhere (checked across every chapter, 2026-09-04) for
    # this endpoint. The sibling /db/SLAN tables it as row 9, Integer,
    # default 1, Optional. MD-43.
    LANE_ITEMS: List[SurfaceLaneChinaItem]  # required


class TrafficSurfaceLanesChina(DbResource):
    ENDPOINT = "/db/SLANch"
    NAME = "Traffic Surface Lanes – China"


# --- 9. /db/SLANop — Traffic Surface Lanes – Moving Load Optimization ------


class SurfaceLaneOptimizationItem(TypedDict, total=False):
    NODE_KEY: int  # Node Key, required
    OFFSET: float  # Offset, default 0, optional
    FACTOR: float  # Impact Factor, default 0, optional
    CENT_F: float  # Centrifugal Force, default 0, optional (alternative to FACTOR, code-dependent)
    SPAN_START: bool  # Span Start, default false, optional


class SurfaceLaneOptimizationChinaItem(TypedDict, total=False):
    """One entry of /db/SLANop's CHINA_ITEMS.

    Undocumented: `GET /info/db/SLANop` declares the array with no description
    of its own, only its members'. The name is the only statement of what it is
    for. MD-45.
    """

    NODE_KEY: int  # Node Key
    OFFSET: float  # Offset
    SPAN_LENGTH: float  # Span Length
    SPAN_START: bool  # Span Start


class TrafficSurfaceLanesOptimizationPayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #9 — /db/SLANop Specifications table."""

    LANE_NAME: str  # Lane Name, required
    SKEW_START: float  # Skew Start, default 0, optional
    SKEW_END: float  # Skew End, default 0, optional
    MOVING: str  # Moving Direction, required
    OPTIMIZE_WIDTH: float  # Optimization Width, required
    LANE_WIDTH: float  # Lane Width, required
    WHEEL_SPACE: float  # Wheel Spacing, default 0, optional
    MARGIN: float  # Margin, default 0, optional
    OFFSET_TYPE: int  # Offset Type: Fixed=0/Division=1, required
    DIVIDE_NUM: int  # Number of Division, optional
    ANALYSIS_LANE_OFFSET: float  # Analysis Lane Offset, optional
    ITEMS: List[SurfaceLaneOptimizationItem]  # required
    OPT_STRADD: bool  # BS Straddling Lane; /info declares it and the manual
    # documents it nowhere (checked across every chapter, 2026-09-04). MD-45.
    CHINA_ITEMS: List[SurfaceLaneOptimizationChinaItem]  # see above; MD-45


class TrafficSurfaceLanesOptimization(DbResource):
    ENDPOINT = "/db/SLANop"
    NAME = "Traffic Surface Lanes – Moving Load Optimization"


# --- 10. /db/MVHL — Vehicles --------------------------------------------------


class VehicleDefaultParams(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #10 — /db/MVHL "VEH_DEFAULT" table.

    ⚠️ On Civil NX 2026 **v2.1**, sending this as an empty ``{}`` (every field
    here is individually documented as optional) made ``Vehicles.create``
    silently no-op — response ``{"message": ""}``, and a subsequent ``GET``
    showed nothing had actually been saved, no error raised. Populating at
    least ``DYN_LOAD_ALLOWANCE``/``CENT_F`` (matching the manual's own worked
    example for your ``STANDARD_CODE``) made the same call succeed.

    **This did not reproduce on v2.2 (build 06/18/2026)**, re-checked
    2026-07-26: an empty ``VEH_DEFAULT`` saves correctly and comes back
    populated with ``{"DYN_LOAD_ALLOWANCE": 0, "CENT_F": false}``. Looks fixed.
    Populating it explicitly is still the safer habit if you support v2.1.
    See docs/live_verification_notes.md.
    """

    UNIFORM_LOAD: float  # Uniform Load, optional
    DYN_LOAD_ALLOWANCE: float  # Dynamic Load Allowance (%), optional
    W1: float  # Width 1, optional
    W2: float  # Width 2, optional
    D1: float  # Distance 1, optional
    D2: float  # Distance 2, optional
    PL: float  # Point Load, optional
    PLM: float  # PLM, optional
    PLV: float  # PLV, optional
    CENT_F: bool  # Add Centrifugal Force, default false, optional


class VehicleLoadItem(TypedDict, total=False):
    """LOAD_ITEMS entry for /db/MVHL user-defined vehicles."""

    POINT_LOAD: float  # Point Load, required
    POINT_DIST: float  # Point Distance, required


class VehicleKsceLsd15PointItem(TypedDict, total=False):
    """POINT_ITEMS entry of VEH_KSCE_LSD15."""

    POINT_LOAD: float  # Load, required
    POINT_DIST: float  # Spacing, required
    POINT_DIST2: float  # Distributed-load-equivalent length, only when CONVERT_DIST_LOAD=true, default 0, optional


class VehicleKsceLsd15Params(TypedDict, total=False):
    """VEH_KSCE_LSD15 sub-object of /db/MVHL, used instead of VEH_DEFAULT
    when STANDARD_CODE is "KSCE-LSD15" — documented in a separate official
    article ("Vehicles - KSCE-LSD15") the manual repo picked up 2026-07-30,
    not in this endpoint's own Specifications table, so it was previously
    missing here (only listed as an untyped extra key, see VehiclePayload's
    class docstring history).

    ⚠️ **MVLD_CODE for this shape is 13, not 1.** An older worked example in
    the manual used ``MVLD_CODE: 1`` with VEH_DEFAULT for a KSCE-LSD15
    vehicle; the corrected official example uses ``MVLD_CODE: 13`` with this
    object instead. Use 13 when sending VEH_KSCE_LSD15.

    The official Specifications table marks LENGTH_LANE/UNIFORM_LOAD_W/
    UNIFORM_LOAD_LOAD_LENGTH_L/POINT_ITEMS as unconditionally "Required",
    but the official Standard-vehicle request example omits all three
    UNIFORM_LOAD_* fields (Lane-only) and the official User-Defined
    Truck/Lane example omits LOADED_LENGTH/W1/W2/D1/D2/EXP — so actual
    requiredness depends on USER_LOAD_TYPE ("Truck/Lane" vs a predefined
    Standard vehicle) and LENGTH_LANE, not a fixed set. Build only the
    fields your worked example needs, matching this SDK's convention for
    other conditionally-required payloads.
    """

    LOAD_TYPE: int  # 0=75% of Design Load/1=25% of Design Load, meaningful only for KL-510LNE; default 0, optional
    LOADED_LENGTH: float  # Lane Loaded Length, User Defined Truck/Lane only, default 60, optional
    W1: float  # Distribution Load Not Exceeding Loaded Length, default 12.7, optional
    W2: float  # Distribution Load Exceeding Loaded Length, default 12.7, optional
    D1: float  # Spacing dD1, User Defined Train only, default 0, optional
    D2: float  # Spacing dD2, User Defined Train only, default 0, optional
    EXP: float  # Exponent to calculate distribution load of W2, default 0.1, optional
    DYN_LOAD_ALLOWANCE: float  # Dynamic Load Allowance (%), default 0, optional
    LENGTH_LANE: int  # 0=1st Model/1=2nd Model, conditionally required — see class docstring
    LENGTH_LANE_USER: float  # Length of Lane Load (User), used when LENGTH_LANE=0, default 0, optional
    CONVERT_DIST_LOAD: bool  # Convert point load to distributed load, default false, optional
    UNIFORM_LOAD_NUM: float  # Number of Uniform Load (Lane only) — N items means N-1, default 0, optional
    UNIFORM_LOAD_DIST: float  # Uniform Load Distance, Lane only, default 0, optional
    UNIFORM_LOAD_W: float  # Uniform Load, Lane only, conditionally required — see class docstring
    UNIFORM_LOAD_LOAD_LENGTH_L: float  # Uniform Load Length, Lane only, conditionally required — see class docstring
    POINT_ITEMS: List[VehicleKsceLsd15PointItem]  # axle-load array, conditionally required — see class docstring


class VehicleEurocodeParams(TypedDict, total=False):
    """VEH_EUROCODE sub-object of /db/MVHL, used instead of VEH_DEFAULT for
    Eurocode's predefined load models (Load Model 1/2/3, rail HSLM-A/B, ...).

    Confirmed live 2026-07-30 against a real production Eurocode PSC bridge
    model — not documented in the manual's own Specifications table at all
    (only VEH_DEFAULT is). `GET /info/db/MVHL` shows this object has ~50
    fields covering multiple load-model sub-types selected by SUB_TYPE; only
    the flat scalar ones are typed here, matching the field set actually
    seen live. LOADCASES/VEHICLES/PERMIT_LOAD are deeply nested and
    load-model-specific, so they're left as extra untyped dict keys — pass
    them as-is rather than through this TypedDict, same as SECT_I's
    precedent for shape-conditional structures.
    """

    SUB_TYPE: int  # Load model sub-type selector, required
    SEL_VEHICLE: str  # Select Vehicle, optional
    AMP: float  # Amplification, optional
    AMP2: float  # Amplification2, optional
    AMP_VALUES: List[float]  # Amplification Value Array, optional
    TANDEM_ADJUST_VALUES: List[float]  # Tandem System Adjustment Factor Array, optional
    TANDEM_LOADS: List[float]  # Tandem System Axle Loads Array, optional
    UDL_ADJUST_VALUES: List[float]  # UDL System Adjustment Factor Array, optional
    UDL_LOADS: List[float]  # UDL System Uniformly Dist. Loads Array, optional
    USE_DYNAMIC_FACTOR2_0: bool  # optional
    USE_DYNAMIC_FACTOR2_1: bool  # optional
    USE_POINT_LOAD3_0: bool  # optional
    USE_POINT_LOAD3_1: bool  # optional
    VAR_SPACING: bool  # Use Variable Axle Spacing, optional
    MAX_SPACING: float  # optional
    MIN_SPACING: float  # optional
    WHEEL_SPACING: float  # Wheel Spacing for Static Load, optional
    LM3_LOADCASE1: bool  # optional
    LM3_LOADCASE2: bool  # optional
    ADJUSTMENT: float  # optional
    ADJUSTMENT2: float  # optional
    AXLE_NUM: int  # optional
    FOOTWAY: float  # optional
    INTERVAL: float  # Two Vehicle Interval, optional
    DYNAMIC_FACTOR: bool  # optional
    USER_INPUT: bool  # optional
    DSPACE: float  # optional
    W1: float  # optional
    DD1: float  # optional
    D1: float  # optional
    W2: float  # optional
    DD2: float  # optional
    D2: float  # optional
    PRESSURE_LOAD: float  # optional
    V_LOAD_FACTOR: float  # Eccentricity of Lateral Displacement of Vertical Loads Factor, optional
    LONGI_DIST: bool  # Consider Longitudinal Distribution of Point Loads, optional
    DIST_RAIL_SUPPORT: float  # Distance between Rail Support Points, optional
    ECCEN_VERT_LOAD: bool  # optional
    ECCEN_VERT_LOAD_VALUE: float  # optional
    HSLMA_NUM: int  # optional
    HSLMA_LENGTH: float  # optional
    HSLMA_SPACING: float  # optional
    HSLMA_FORCE: float  # optional
    HSLMB_NUM: int  # optional
    HSLMB_FORCE: float  # optional
    HSLMB_DIST: float  # optional
    PHI_DYN_EFF1: float  # optional
    PHI_DYN_EFF2: float  # optional
    # LOADCASES, VEHICLES, PERMIT_LOAD: deeply nested, load-model-specific —
    # pass as extra untyped dict keys.


class VehiclePayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #10 — /db/MVHL Specifications table.

    STANDARD_CODE values: "AASHTO-STD"/"AASHTO-LRFD"/"KS-RB"/"KS2005"/
    "KSCE-LSD15"/"BS"/"EUROCODE"/"CANADA"/"AUSTRALIA"/"CHINA"/"INDIA"/
    "TAIWAN"/"POLAND"/"RUSSIA"/"SOUTH_AFRICA".

    ⚠️ STANDARD_CODE/VEH_DEFAULT are the manual's only documented shape, but
    `GET /info/db/MVHL` (checked 2026-07-30) shows 11 more country-specific
    sub-objects the manual never mentions: VEH_FR, VEH_CN, VEH_IN, VEH_CA,
    VEH_BS, VEH_EUROCODE, VEH_RU, VEH_KSCE_LSD15, VEH_AU, VEH_PL, VEH_ZA —
    plus a second load-items array, LOAD_ITEMS2. Confirmed live against a
    real Eurocode PSC bridge model: its predefined "Load Model 1" vehicle
    entry has **no STANDARD_CODE key at all** and uses VEH_EUROCODE instead
    of VEH_DEFAULT — so despite the table below marking both "required",
    that's only true for the generic/VEH_DEFAULT shape. VEH_EUROCODE and
    VEH_KSCE_LSD15 are typed here (`VehicleEurocodeParams`,
    `VehicleKsceLsd15Params`); the other 9 country-specific sub-objects are
    confirmed to exist via `/info` but not individually typed — pass them
    as extra untyped dict keys if you need one.
    """

    MVLD_CODE: int  # Moving Load Code, required — e.g. 13 for KSCE-LSD15/VEH_KSCE_LSD15, see VehicleKsceLsd15Params
    VEHICLE_LOAD_NAME: str  # Vehicular Load Name (user-assigned), required
    VEHICLE_LOAD_NUM: int  # Vehicular Load Number, required
    VEHICLE_TYPE_NAME: str  # Vehicular Type Name (predefined vehicle name), required
    STANDARD_CODE: str  # Standard Code, required for the VEH_DEFAULT shape — see class docstring
    USER_LOAD_TYPE: str  # User Load Type (when user-defined), optional
    VEH_DEFAULT: VehicleDefaultParams  # Default Parameters, required for the generic shape — see class docstring
    VEH_EUROCODE: VehicleEurocodeParams  # Eurocode predefined load models, used instead of VEH_DEFAULT — see class docstring
    VEH_KSCE_LSD15: VehicleKsceLsd15Params  # KSCE-LSD15 predefined/user-defined vehicles, used instead of VEH_DEFAULT when STANDARD_CODE="KSCE-LSD15" — see class docstring
    LOAD_ITEMS: List[VehicleLoadItem]  # User-defined axle-load items, optional


class Vehicles(DbResource):
    """See :class:`VehiclePayload`.

    :meth:`create`/:meth:`update` refuse an empty ``VEH_DEFAULT``, which the
    server accepts and then silently saves nothing for.
    """

    ENDPOINT = "/db/MVHL"
    NAME = "Vehicles"

    @classmethod
    def _reject_empty_defaults(cls, items: dict) -> None:
        """Refuse the one payload shape the server accepts and discards.

        ``VEH_DEFAULT: {}`` answers ``{"message": ""}`` with no error object
        and stores nothing - a following GET shows the vehicle was never
        created. Every member of the object is documented Optional, so an empty
        one looks like a reasonable way to say "all defaults", and the response
        gives the caller no reason to think otherwise. Contract rule
        db-mvhl-veh-default-not-empty; see docs/live_verification_notes.md.
        """
        for key, item in items.items():
            if isinstance(item, dict) and item.get("VEH_DEFAULT") == {}:
                raise MidasRequestError(
                    "VEH_DEFAULT must not be empty for /db/MVHL: the server "
                    "accepts the request and saves nothing (Hint: send the "
                    "vehicle's parameters, or omit VEH_DEFAULT and send the "
                    "STANDARD_CODE's own VEH_* object) "
                    f"(record {key})",
                    method="POST",
                    endpoint=cls.ENDPOINT,
                )

    @classmethod
    def create(cls, items: dict, client: Optional[MidasClient] = None) -> dict:
        cls._reject_empty_defaults(items)
        return super().create(items, client=client)

    @classmethod
    def update(cls, items: dict, client: Optional[MidasClient] = None) -> dict:
        cls._reject_empty_defaults(items)
        return super().update(items, client=client)


# --- 11. /db/MVHLtr — Vehicles – Transverse -----------------------------------


class VehicleTransversePayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #11 — /db/MVHLtr Specifications table."""

    NAME: str  # Vehicular Load Name, required
    P: float  # Wheel Load, required
    W: float  # Distribution Width, required
    LW: float  # Longitudinal Width, required
    NUM: int  # Max. Number of Lanes (n), required
    DW: float  # Distance between Wheels (Dw), required
    DV: float  # Min. Distance between Vehicle (Dv), required
    DE: float  # Edge Distance of Wheel Loads (De), default 0, optional
    OPT_MEDIAN_STRIP: bool  # Median Strip Option, default false, optional
    ML: float  # Location (Ml), required if OPT_MEDIAN_STRIP=true
    MW: float  # Width (Mw), required if OPT_MEDIAN_STRIP=true
    LEFT_LANES: int  # Max. Number of Left Lanes (n1), required if OPT_MEDIAN_STRIP=true


class VehiclesTransverse(DbResource):
    ENDPOINT = "/db/MVHLtr"
    NAME = "Vehicles – Transverse"


# --- 12. /db/MVLD — Moving Load Cases -----------------------------------------


class MovingLoadCaseSubLoadDataItem(TypedDict, total=False):
    """SUB_LOAD_DATAS entry of the "DEFAULT" (TYPE=0, General Load) object."""

    VEHICLE_TYPE: str  # "VL"/"VC", required
    VEHICLE_NAME: str  # Vehicle Name, required
    SCALE_FACTOR: float  # Scale Factor, required
    MIN_LOADED_LANE: int  # Min. Number of Loaded Lane, required
    MAX_LOADED_LANE: int  # Max. Number of Loaded Lane, required
    LANE_NAMES: List[str]  # Selected Lanes, required


class MovingLoadCaseDefault(TypedDict, total=False):
    """"DEFAULT" object, required when TYPE=0 (General Load). Korea adds a
    distinct Lane Factor Type plus per-lane-count factors (flattened onto
    this TypedDict, mirrors MaterialParam precedent).
    """

    LANE_FACTOR_TYPE: int  # Multiple Presence Factor=1 (KSCE-LSD15/AASHTO/PENNDOT/Taiwan/Canada); Korea: Multi-Lane KS Rail=0/MPF=1, required
    SCALE_FACTORS: List[float]  # Multiple Presence Factor [L1~L6+], length 6, required
    COMB_OPTION: str  # Loading Effect: "COMBINED"/"INDEPENDENT", required
    SUB_LOAD_DATAS: List[MovingLoadCaseSubLoadDataItem]  # Sub Load Cases, required
    _2_LANE_FACTOR_1: float  # 2-Lane Factor L1, optional (Korea only)
    _2_LANE_FACTOR_2: float  # 2-Lane Factor L2, optional (Korea only)
    _3_LANE_FACTOR_1: float  # 3+ Lane Factor L1, optional (Korea only)
    _3_LANE_FACTOR_2: float  # 3+ Lane Factor L2, optional (Korea only)
    _3_LANE_FACTOR_3: float  # 3+ Lane Factor L3, optional (Korea only)
    _3_LANE_FACTOR_4: float  # 3+ Lane Factor L4, optional (Korea only)


class MovingLoadCasePermitLoad(TypedDict, total=False):
    """"PERMIT_LOAD" object, required when TYPE=1 (Permit Vehicle)."""

    VEHICLE_LOAD_NAME: str  # Vehicle Load Name, required
    REF_LANE: str  # Reference Lane, required
    SCALE_FACTOR: float  # Scale Factor, required


class MovingLoadCaseOptimizeItem(TypedDict, total=False):
    """OPTIMIZE_ITEMS entry of the "AUTO_OPTIMIZE" (TYPE=2) object."""

    VEHICLE_TYPE: str  # "VL"/"VC", required
    VEHICLE_NAME: str  # Vehicle Name, required
    SCALE_FACTOR: float  # Scale Factor, required


class MovingLoadCaseAutoOptimize(TypedDict, total=False):
    """"AUTO_OPTIMIZE" object, required when TYPE=2 (Moving Load Optimization)."""

    LANE_NAME: str  # Loaded Lane Name, required
    SCALE_FACTORS: List[float]  # Multiple Presence Factor, length 6, required
    MIN_VEHL_DIST: float  # Min. Vehicle Distance, required
    MIN_NUM_VEHICLE: int  # Min. Number of Vehicle, required
    MAX_NUM_VEHICLE: int  # Max. Number of Vehicle, required
    OPTIMIZE_ITEMS: List[MovingLoadCaseOptimizeItem]  # required


class MovingLoadCaseAustraliaHeavyLoadLanes(TypedDict, total=False):
    """``ASL.LINE_ITEMS`` for Australia's Heavy Load Platform model."""

    NA_LLAN_NAMES: List[str]  # Selected Lanes, required
    STRAD_LLAN1_NAMES: List[str]  # Heavy Load Lanes Start, required
    STRAD_LLAN2_NAMES: List[str]  # Heavy Load Lanes End, required


class MovingLoadCaseAustraliaHeavyLoadPlatform(TypedDict, total=False):
    """``ASL`` object required with Australia's ``LOAD_MODEL=2``.

    The manual calls this Heavy Load Platform data; the current Civil and Gen
    ``/info/db/MVLD`` schemas both expose it as a top-level payload member.
    """

    MULTIPLE_FACTOR: float  # Unobstructed Lane Scale Factor, required
    VEHICLE_LOAD_NAME: str  # Heavy Load vehicle name, required
    VEHICLE_LOAD_NAME2: str  # M1600/S1600 vehicle name, required
    MIN_LOADED_LANE: int  # required
    MAX_LOADED_LANE: int  # required
    LINE_ITEMS: MovingLoadCaseAustraliaHeavyLoadLanes  # required


class MovingLoadCasePayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #12 — /db/MVLD Specifications tables.

    TYPE selects which of DEFAULT/PERMIT_LOAD/AUTO_OPTIMIZE is required.
    Australia additionally uses ASL with its Heavy Load Platform model.
    (each is a distinct nested object key, per the manual's worked
    examples — flattened onto one payload as three optional keys, mirrors
    MaterialParam precedent).
    """

    LCNAME: str  # Load Case Name, required
    DESC: str  # Description, default "", optional
    TYPE: int  # Load Type: General=0/Permit=1/Optimization=2, required
    DEFAULT: MovingLoadCaseDefault  # required if TYPE=0
    PERMIT_LOAD: MovingLoadCasePermitLoad  # required if TYPE=1
    AUTO_OPTIMIZE: MovingLoadCaseAutoOptimize  # required if TYPE=2
    ASL: MovingLoadCaseAustraliaHeavyLoadPlatform  # required for Australia's LOAD_MODEL=2


class MovingLoadCase(DbResource):
    ENDPOINT = "/db/MVLD"
    NAME = "Moving Load Cases"


# --- 13. /db/MVLDch — Moving Load Cases – China -------------------------------


class MovingLoadCaseChinaSubLoadItem(TypedDict, total=False):
    VEHICLE_CLASS: str  # Vehicle Class Name, required
    VEHICLE_TYPE: str  # "VL"/"VC", required
    SCALE_FACTOR: float  # Scale Factor, required
    MIN_NUM_LOADED_LANES: int  # Min. Number of Loaded Lanes, required
    MAX_NUM_LOADED_LANES: int  # Max. Number of Loaded Lanes, required
    SELECTED_LANES: List[str]  # Selected Lanes, required


class MovingLoadCaseChinaOptimizeItem(TypedDict, total=False):
    """``AUTO_OPTIMIZE_ITEMS`` entry when ``OPT_AUTO_OPTIMIZE`` is true."""

    VEHICLE_TYPE: str  # "VL"/"VC", required
    VEHICLE_NAME: str  # Vehicle Class Name, required
    SCALE_FACTOR: float  # required


class MovingLoadCaseChinaPayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #13 — /db/MVLDch Specifications table."""

    LCNAME: str  # Load Case Name, required
    DESC: str  # Description, default "", optional
    OPT_AUTO_OPTIMIZE: bool  # Moving Load Optimization, default false, optional
    BRIDGE_TYPE: int  # Old Urban=0/Highway-New Urban=1/JTG B01-2014=2, required
    SCALE_FACTOR_O: List[float]  # Scale Factor for Old Urban Bridge [1~7, >=8], length 8, required
    SCALE_FACTOR_N: List[float]  # Scale Factor for Highway/New Urban Bridge, length 8, required
    SCALE_FACTOR_JTG: List[float]  # Scale Factor for JTG B01-2014, length 8, required
    LOADING_EFFECT: int  # Combined=0/Independent=1, required
    SUB_LOAD_ITEMS: List[MovingLoadCaseChinaSubLoadItem]  # required if OPT_AUTO_OPTIMIZE=false
    MIN_VEHICLE_DIST: float  # required if OPT_AUTO_OPTIMIZE=true
    LOADED_LANE_NAME: str  # required if OPT_AUTO_OPTIMIZE=true
    MIN_NUM_VEHICLE: int  # required if OPT_AUTO_OPTIMIZE=true
    MAX_NUM_VEHICLE: int  # required if OPT_AUTO_OPTIMIZE=true
    AUTO_OPTIMIZE_ITEMS: List[MovingLoadCaseChinaOptimizeItem]  # required if OPT_AUTO_OPTIMIZE=true


class MovingLoadCaseChina(DbResource):
    ENDPOINT = "/db/MVLDch"
    NAME = "Moving Load Cases – China"


# --- 14. /db/MVLDid — Moving Load Cases – India -------------------------------


class MovingLoadCaseIndiaSubLoadItem(TypedDict, total=False):
    VEHICLE_CLASS_1: str  # Vehicle Class Name, required (manual's own field name — not "VEHICLE_CLASS" as in MVLDch's sibling item)
    SCALE_FACTOR: float  # Scale Factor, required
    MIN_NUM_LOADED_LANES: int  # Min. Number of Loaded Lanes, required
    MAX_NUM_LOADED_LANES: int  # Max. Number of Loaded Lanes, required
    SELECTED_LANES: List[str]  # Selected Lanes, required


class MovingLoadCaseIndiaPayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #14 — /db/MVLDid Specifications table.

    OPT_LC_FOR_PERMIT_LOAD selects between the General Load field group
    (NUM_LOADED_LANES/SUB_LOAD_ITEMS) and the Permit Vehicle field group
    (PERMIT_VEHICLE/REF_LANE/ECCEN/PERMIT_SCALE_FACTOR); flattened onto
    one payload (mirrors MaterialParam precedent).
    """

    LCNAME: str  # Load Case Name, required
    DESC: str  # Description, default "", optional
    SCALE_FACTOR: List[float]  # Multiple Presence Factor [1-2, 3, 4, >=5], length 4, required
    OPT_AUTO_LL: bool  # Auto Live Load Combinations, default false, optional
    OPT_LC_FOR_PERMIT_LOAD: bool  # Load Cases for Permit Vehicle, default false, optional
    NUM_LOADED_LANES: int  # Number of Loaded Lanes, required if OPT_LC_FOR_PERMIT_LOAD=false
    SUB_LOAD_ITEMS: List[MovingLoadCaseIndiaSubLoadItem]  # Sub-Load Cases, required if OPT_LC_FOR_PERMIT_LOAD=false
    PERMIT_VEHICLE: int  # Permit Vehicle ID, required if OPT_LC_FOR_PERMIT_LOAD=true
    REF_LANE: int  # Reference Lane ID, required if OPT_LC_FOR_PERMIT_LOAD=true
    ECCEN: float  # Eccentricity, required if OPT_LC_FOR_PERMIT_LOAD=true
    PERMIT_SCALE_FACTOR: float  # Scale Factor, required if OPT_LC_FOR_PERMIT_LOAD=true


class MovingLoadCaseIndia(DbResource):
    ENDPOINT = "/db/MVLDid"
    NAME = "Moving Load Cases – India"


# --- 15. /db/MVLDbs — Moving Load Cases – BS ----------------------------------


class MovingLoadCaseBsStraddleLaneItem(TypedDict, total=False):
    STARDD_LANE_1: str  # Straddling Lane 1, required
    STARDD_LANE_2: str  # Straddling Lane 2, required


class MovingLoadCaseBsSubLoadDataItem(TypedDict, total=False):
    SCALEFACTOR: float  # Scale Factor, required
    NUMLOADEDLANE: int  # Number of Loaded Lanes, required
    VEHICLE_NAME: str  # Vehicle Name, required
    SELECTEDLANES: List[str]  # Selected Lanes, required
    STRAD_LANE: List[MovingLoadCaseBsStraddleLaneItem]  # Straddling Lane pairs, optional


class MovingLoadCaseBsStandardData(TypedDict, total=False):
    """"LCDATA_STANDARD" object, required when LOADMODEL="STANDER"."""

    LOADINGEFFECT: str  # "INDEPEND" (or similar), required
    SUBLOADDATA: List[MovingLoadCaseBsSubLoadDataItem]  # required


class MovingLoadCaseBsSpecialData(TypedDict, total=False):
    """"LCDATA_SPECIAL" object, required when LOADMODEL="SPECAIL"."""

    VEHICLE_NAME: str  # Standard vehicle, required
    SPECIAL_VIHICLE_NAME: str  # Special vehicle ([sic] matches the manual's own key spelling), required
    SELECTEDLANES: List[str]  # Selected Lanes, required
    STRAD_LANE: List[MovingLoadCaseBsStraddleLaneItem]  # Straddling Lane pairs, required


class MovingLoadCaseBsAllModeData(TypedDict, total=False):
    """"LCDATA_ALLMODE" object, required when LOADMODEL="ALL_MODE_1"/"ALL_MODE_2"."""

    VEHICLE_NAME: str  # Standard vehicle, required
    SPECIAL_VIHICLE_NAME: str  # Special vehicle, required
    SELECTEDLANES: List[str]  # Selected Lanes, required
    STRAD_LANE: List[MovingLoadCaseBsStraddleLaneItem]  # Straddling Lane pairs, required
    REMAINING_LANE: List[str]  # ALL_MODE_1 only, optional


class MovingLoadCaseBsOptiBase(TypedDict, total=False):
    """Shared "OPTI_BASE" sub-object used by the *_OPTI variants."""

    MINVEHLDIST: float  # Minimum vehicle distance, required
    ASSIGN_LANE: str  # Assign Lane, required
    NUMLOADEDLANES: int  # Number of Loaded Lanes, required


class MovingLoadCaseBsOptiVehicleBaseItem(TypedDict, total=False):
    VEHICLE_TYPE: str  # "VL" (vehicle load) / "VC" (vehicle class), required
    VEHICLE_NAME: str  # required
    SCALE_FACTOR: float  # required


class MovingLoadCaseBsStandardOptiData(TypedDict, total=False):
    """"LCDATA_STANDARD_OPTI" object, required when bAUTOOPTIMIZE=true &
    LOADMODEL="STANDER"."""

    LOADINGEFFECT: str  # required
    OPTI_BASE: MovingLoadCaseBsOptiBase  # required
    OPTI_VEHICLE_BASE: List[MovingLoadCaseBsOptiVehicleBaseItem]  # required


class MovingLoadCaseBsSpecialOptiData(TypedDict, total=False):
    """"LCDATA_SPECIAL_OPTI" object, required when LOADMODEL="SPECAIL"
    (Optimization)."""

    VEHICLE_NAME: str  # required
    SPECIAL_VIHICLE_NAME: str  # required
    OPTI_BASE: MovingLoadCaseBsOptiBase  # required


class MovingLoadCaseBsAllModeOptiData(TypedDict, total=False):
    """"LCDATA_ALLMODE_OPTI" object, required when LOADMODEL="ALL_MODE_1"/
    "ALL_MODE_2" (Optimization)."""

    VEHICLE_NAME: str  # required
    SPECIAL_VIHICLE_NAME: str  # required
    OPTI_BASE: MovingLoadCaseBsOptiBase  # required
    REMAINING_LANE: List[str]  # ALL_MODE_1 only, optional


class MovingLoadCaseBsPayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #15 — /db/MVLDbs Specifications table.

    2026-08-25 re-verification (article id `35961459443737`) added the 4th
    `LOADMODEL` value (`"ALL_MODE_2"`, CS454 ALL Mode2 -- previously
    missing) and filled in the field shapes for `LCDATA_SPECIAL`/
    `LCDATA_ALLMODE` (previously typed as `Any`, genuinely undocumented)
    plus the three Moving Load Optimization-only objects
    (`LCDATA_STANDARD_OPTI`/`LCDATA_SPECIAL_OPTI`/`LCDATA_ALLMODE_OPTI`),
    which were entirely absent from both the manual and this SDK before.
    Additive-only: no previously-typed field changed shape. Not
    independently live-tested this session (BS moving-load setup needs
    vehicle/lane data this session's scratch document doesn't have); manual
    text transcribed directly from the officially cited Specifications
    table and summary table.
    """

    LCNAME: str  # Load Case Name, required
    DESC: str  # Description, default "", optional
    bAUTOOPTIMIZE: bool  # Moving Load Optimization, default false, optional
    LOADMODEL: str  # "STANDER"/"SPECAIL"/"ALL_MODE_1"/"ALL_MODE_2", required
    bAUTOLIVELOADCOMB: bool  # Auto Live Load Combination, default false, optional
    DGNCOMBFACTORTYPE: str  # "ULTIMATE"/"SERVICEABIL", required
    COMBMETHOD: str  # "COMB_1"/"COMB_2_3", required
    LCDATA_STANDARD: MovingLoadCaseBsStandardData  # required if LOADMODEL="STANDER" (General)
    LCDATA_SPECIAL: MovingLoadCaseBsSpecialData  # required if LOADMODEL="SPECAIL" (General)
    LCDATA_ALLMODE: MovingLoadCaseBsAllModeData  # required if LOADMODEL="ALL_MODE_1"/"ALL_MODE_2" (General)
    LCDATA_STANDARD_OPTI: MovingLoadCaseBsStandardOptiData  # required if bAUTOOPTIMIZE=true & LOADMODEL="STANDER"
    LCDATA_SPECIAL_OPTI: MovingLoadCaseBsSpecialOptiData  # required if bAUTOOPTIMIZE=true & LOADMODEL="SPECAIL"
    LCDATA_ALLMODE_OPTI: MovingLoadCaseBsAllModeOptiData  # required if bAUTOOPTIMIZE=true & LOADMODEL="ALL_MODE_1"/"ALL_MODE_2"


class MovingLoadCaseBs(DbResource):
    ENDPOINT = "/db/MVLDbs"
    NAME = "Moving Load Cases – BS"


# --- 16. /db/MVLDeu — Moving Load Cases – Eurocode ----------------------------


class MovingLoadCaseEurocodeStraddlingLaneItem(TypedDict, total=False):
    """STL_LIST entry (TYPE_LOADMODEL=4 only)."""

    NAME1: str  # Start Lane, required
    NAME2: str  # End Lane, required


class MovingLoadCaseEurocodeSubLoadItem(TypedDict, total=False):
    """SUB_LOAD_LIST entry (TYPE_LOADMODEL=2/5, General Load)."""

    TYPE: int  # Vehicle Load Type: Vehicle Class=1 (unused in Eurocode)/Vehicle Load=2 (fixed for Eurocode), required
    NAME: str  # Name, required
    SCALE_FACTOR: float  # Scale Factor, required
    MIN_LOAD_LANE_TYPE: int  # Min. Loaded Lanes, required
    MAX_LOAD_LANE_TYPE: int  # Max. Loaded Lanes, required
    SLN_LIST: List[str]  # Selected Lanes, required


class MovingLoadCaseEurocodeOptimizeItem(TypedDict, total=False):
    """OPTIMIZE_LIST entry (Optimization mode, TYPE_LOADMODEL=2/5)."""

    TYPE: int  # Vehicle Load Type, required
    NAME: str  # Name, required
    SCALE_FACTOR: float  # Scale Factor, required


class MovingLoadCaseEurocodePayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #16 — /db/MVLDeu Specifications table.

    TYPE_LOADMODEL (1=LM1/FLM1/Footbridge, 2=LM2-4/FLM2-4/Footbridge/Permit
    Truck, 3=LM1&3 Multi, 4=LM1&3 Multi Straddling, 5=Railway Bridge)
    combined with OPT_AUTO_OPTIMIZE (General Load=false/Optimization=true)
    selects a large, mutually-exclusive set of field groups; all flattened
    onto one payload (mirrors MaterialParam precedent) with per-field
    applicability noted inline.
    """

    LCNAME: str  # Load Case Name, required
    OPT_AUTO_OPTIMIZE: bool  # Moving Load Optimization: General=false/Optimization=true, default false, optional
    TYPE_LOADMODEL: int  # Load Model Type (1-5, see docstring), required
    DESC: str  # Description, default "", optional
    OPT_LEADING: bool  # Ignore psi(1) factor, required (LM1/3/4, General & Optimization)
    VHLNAME1: str  # Load Case - Vehicle, required (LM1/3/4)
    VHLNAME2: str  # Load Case - Footway, optional (LM1) / required (LM3/4, Optimization)
    SLN_LIST: List[str]  # Selected Lanes, required (LM1/3/4)
    SRA_LIST: List[str]  # Remaining Area, required (LM1/3)
    FLN_LIST: List[str]  # Footway Lanes, required (LM1)
    STL_LIST: List[MovingLoadCaseEurocodeStraddlingLaneItem]  # Straddling Lanes, required (LM4)
    OPT_COMB: int  # Loading Effect: Combined=0/Independent=1, required (LM2/5)
    SUB_LOAD_LIST: List[MovingLoadCaseEurocodeSubLoadItem]  # Sub-Load Cases, required (LM2/5, General)
    OPT_PSI_FACTOR: bool  # Ignore psi1 factor, required (LM5)
    SCALE_FACTOR1: float  # psi1 factor for Lane 1, required (LM5)
    SCALE_FACTOR2: float  # psi1 factor for Lane 2, required (LM5)
    SCALE_FACTOR3: float  # psi1 factor for Lane 3+, required (LM5)
    MULTI_FACTOR1: float  # Multi Presence Factor for Lane 1, required (LM5)
    MULTI_FACTOR2: float  # Multi Presence Factor for Lane 2, required (LM5)
    MULTI_FACTOR3: float  # Multi Presence Factor for Lane 3+, required (LM5)
    MINVHLDIST: float  # Min. Vehicle Distance, required (Optimization)
    OPTIMIZE_LANE_NAME: str  # Assignment Lane, required (Optimization)
    LOADEDLANE: int  # Number of Loaded Lane, required (Optimization, LM1/3/4)
    MIN_NUM_VHL: int  # Min. Number of Vehicle, required (Optimization, LM2/5)
    MAX_NUM_VHL: int  # Max. Number of Vehicle, required (Optimization, LM2/5)
    OPTIMIZE_LIST: List[MovingLoadCaseEurocodeOptimizeItem]  # Sub-Load Cases for Optimization, required (Optimization, LM2/5)


class MovingLoadCaseEurocode(DbResource):
    ENDPOINT = "/db/MVLDeu"
    NAME = "Moving Load Cases – Eurocode"


# --- 17. /db/MVLDpl — Moving Load Cases – Poland ------------------------------


class MovingLoadCasePolandSubLoadDataItem(TypedDict, total=False):
    """SUB_LOAD_DATAS entry. The Parameters table does not detail this
    item's own fields (only its parent "DEFAULT" object's (1)-(3) rows,
    where row (3) documents a top-level "VEHICLE_LOAD_NAME" key instead);
    following the worked example, which uses "VEHICLE_NAME" per item.
    """

    VEHICLE_NAME: str  # Vehicle Name, required
    SCALE_FACTOR: float  # Scale Factor, required
    MIN_LOADED_LANE: int  # Min. Number of Loaded Lane, required
    MAX_LOADED_LANE: int  # Max. Number of Loaded Lane, required
    LANE_NAMES: List[str]  # Selected Lanes, required


class MovingLoadCasePolandDefault(TypedDict, total=False):
    """"DEFAULT" object. COMB_OPTION/SUB_LOAD_DATAS apply to Vehicle
    S/2S/Permit (LOAD_MODEL=1); VEHICLE_LOAD_NAME is used instead, as a
    top-level key of this object, for Vehicle K/Military (LOAD_MODEL=2/3).
    """

    COMB_OPTION: str  # Loading Effect: "COMBINED"/"INDEPENDENT", required (Vehicle S/2S/Permit only)
    SUB_LOAD_DATAS: List[MovingLoadCasePolandSubLoadDataItem]  # required (Vehicle S/2S/Permit only)
    VEHICLE_LOAD_NAME: str  # Vehicle Name, required (Vehicle K/Military only)


class MovingLoadCasePolandOptimizeItem(TypedDict, total=False):
    """``AUTO_OPTIMIZE.OPTIMIZE_ITEMS`` entry for Vehicle S/2S."""

    VEHICLE_TYPE: str  # "VL"/"VC", required
    VEHICLE_NAME: str  # Vehicle Name, required
    SCALE_FACTOR: float  # required


class MovingLoadCasePolandAutoOptimize(TypedDict, total=False):
    """``AUTO_OPTIMIZE`` object for Poland moving-load cases.

    ``LOAD_MODEL`` chooses the Vehicle S/2S members or the Vehicle
    K/Military members documented in the same manual table.
    """

    MIN_VEHL_DIST: float  # required
    LANE_NAME: str  # required
    MIN_NUM_VEHICLE: int  # required for Vehicle S/2S
    MAX_NUM_VEHICLE: int  # required for Vehicle S/2S
    COMB_OPTION: str  # "COMBINED"/"INDEPENDENT", required for Vehicle S/2S
    OPTIMIZE_ITEMS: List[MovingLoadCasePolandOptimizeItem]  # required for Vehicle S/2S
    VEHICLE_LOAD_NAME: str  # required for Vehicle K/Military
    NUM_LOADED_LANES: int  # required for Vehicle K/Military


class MovingLoadCasePolandPermitLoad(TypedDict, total=False):
    """``PERMIT_LOAD`` object when ``bPERMIT_LOAD`` is true."""

    VEHICLE_LOAD_NAME: str  # required
    REF_LANE: str  # required
    ECC: float  # required
    SCALE_FACTOR: float  # required


class MovingLoadCasePolandPayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #17 — /db/MVLDpl Specifications table."""

    LCNAME: str  # Load Case Name, required
    DESC: str  # Description, default "", optional
    LOAD_MODEL: int  # Vehicle S/2S/Permit=1/Vehicle K=2/Military=3, required
    bAUTO_OPTIMIZE: bool  # Moving Load Optimization, default false, optional
    bPERMIT_LOAD: bool  # Load Case for Permit Vehicle, default false, optional
    DEFAULT: MovingLoadCasePolandDefault  # Sub-Load Cases, required
    AUTO_OPTIMIZE: MovingLoadCasePolandAutoOptimize  # required if bAUTO_OPTIMIZE=true
    PERMIT_LOAD: MovingLoadCasePolandPermitLoad  # required if bPERMIT_LOAD=true


class MovingLoadCasePoland(DbResource):
    ENDPOINT = "/db/MVLDpl"
    NAME = "Moving Load Cases – Poland"


# --- 18. /db/MVLDtr — Moving Load Cases – Transverse --------------------------


class MovingLoadCaseTransversePayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #18 — /db/MVLDtr Specifications table."""

    LCNAME: str  # Load Case Name, required
    DESC: str  # Description, default "", optional
    MVHL_NAME: str  # Vehicle Name, required
    SCALEFACTOR: float  # Scale Factor, required
    LLAN_NAME: str  # Line Lane, required
    NUM_LANE: int  # Number of Loaded Lanes, required
    ITEMS: List[float]  # Factors, length NUM_LANE + 1, required


class MovingLoadCaseTransverse(DbResource):
    ENDPOINT = "/db/MVLDtr"
    NAME = "Moving Load Cases – Transverse"


# --- 19. /db/CRGR — Concurrent Reaction Group ---------------------------------
# --- 20. /db/CJFG — Concurrent Joint Force Group ------------------------------


class StructureGroupNamesPayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #19/#20 — /db/CRGR and /db/CJFG
    Specifications tables (identical {"GROUPS": [...]} shape for both).
    """

    GROUPS: List[str]  # Structure Group Names, required


class ConcurrentReactionGroup(DbResource):
    ENDPOINT = "/db/CRGR"
    NAME = "Concurrent Reaction Group"
    PRODUCTS = CIVIL_ONLY


class ConcurrentJointForceGroup(DbResource):
    ENDPOINT = "/db/CJFG"
    NAME = "Concurrent Joint Force Group"
    PRODUCTS = CIVIL_ONLY


# --- 21. /db/MVHC — Vehicle Classes -------------------------------------------


class VehicleClassPayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #21 — /db/MVHC Specifications table.

    Usable moving load codes: AASHTO Standard, AASHTO LRFD, PENNDOT,
    Canada, Australia, Russia, Korea, KSCE-LSD15, China, Taiwan.
    """

    VEHICLE_CLS_NAME: str  # Vehicle Class Name, required
    VEHICLE_LD_NAMES: List[str]  # Selected Vehicle List, required


class VehicleClasses(DbResource):
    ENDPOINT = "/db/MVHC"
    NAME = "Vehicle Classes"


# --- 22. /db/SINF — Plate Element for Influence Surface -----------------------


class PlateElementForInfluenceSurfacePayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #22 — /db/SINF Specifications table.

    Usable codes: AASHTO Standard, AASHTO LRFD, PENNDOT, Canada, BS,
    Eurocode, South Africa, Korea, KSCE-LSD15, China, Taiwan.
    """

    ELEM_LISTS: List[int]  # Assigned Element List, required


class PlateElementForInfluenceSurface(DbResource):
    ENDPOINT = "/db/SINF"
    NAME = "Plate Element for Influence Surface"


# --- 23. /db/MLSP — Lane Support – Negative Moments at Interior Piers --------


class LaneSupportNegativeMomentPayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #23 — /db/MLSP Specifications table.

    TYPE selects between the Auto Input field group (GROUP_NAME, AASHTO
    LRFD only) and the User Input field group (ELEMENT_NO/ELEMENT_TYPE/
    POSITION); flattened onto one payload (mirrors MaterialParam
    precedent). Usable codes: AASHTO Standard, AASHTO LRFD, PENNDOT,
    Korea, Taiwan.
    """

    TYPE: str  # Input Type: "AutoInput"/"UserInput", required
    GROUP_NAME: str  # Structure Group Name, required if TYPE="AutoInput" (AASHTO LRFD only)
    ELEMENT_NO: int  # Element ID, required if TYPE="UserInput"
    ELEMENT_TYPE: str  # "BEAM"/"PLATE", required if TYPE="UserInput"
    POSITION: str  # "Both"/"End-I"/"End-J", required if ELEMENT_TYPE="BEAM"


class LaneSupportNegativeMoment(DbResource):
    ENDPOINT = "/db/MLSP"
    NAME = "Lane Support – Negative Moments at Interior Piers"


# --- 24. /db/MLSR — Lane Support – Reactions at Interior Piers ---------------


class LaneSupportReactionPayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #24 — /db/MLSR Specifications table.

    The Assign key is the supporting Node ID; the value is always the
    fixed object {"NODE": 0}. Usable codes: AASHTO LRFD, PENNDOT.
    """

    NODE: int  # Fixed value 0 (key is the Node ID), required


class LaneSupportReaction(DbResource):
    ENDPOINT = "/db/MLSR"
    NAME = "Lane Support – Reactions at Interior Piers"


# --- 25. /db/DYLA — Dynamic Load Allowance ------------------------------------


class DynamicLoadAllowancePayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #25 — /db/DYLA Specifications table.

    Usable codes: AASHTO LRFD, PENNDOT, KSCE-LSD15.
    """

    FACTOR: float  # Impact Factor (%), required
    ITEMS: List[str]  # Selected Structure Group List, required


class DynamicLoadAllowance(DbResource):
    ENDPOINT = "/db/DYLA"
    NAME = "Dynamic Load Allowance"
    PRODUCTS = CIVIL_ONLY


# --- 26. /db/IMPF — Additional Impact Factor ----------------------------------


class AdditionalImpactFactorItem(TypedDict, total=False):
    """ITEMS entry for /db/IMPF. LANE_TYPE/FACT_TYPE together select which
    field group applies (Impact Factor / Effective Span Length – User
    Input, vs. Effective Span Length – Auto Calculation, Line Lane only);
    flattened onto one item (mirrors MaterialParam precedent).

    The manual's Parameters table documents COMPONENTS as 6 flags for
    ELEMTYPE="BEAM" (My_max/My_min/Mz_max/Mz_min/Fx_max/Fx_min), but its own
    worked BEAM example sends an 8-element array
    (``[true, true, true, true, true, true, false, false]``, i.e. the
    6 Beam flags padded with 2 trailing false values); following the worked
    example.
    """

    ID: int  # Serial Number, required
    LANE_TYPE: str  # "LINE"/"SURFACE", required
    LANE_NAME: str  # Lane Name, required
    FACT_TYPE: str  # "IMPACT_FACT"/"EFF_SPAN_LEN_USER"/"EFF_SPAN_LEN_AUTO", required
    FACTOR: float  # Factor, required (FACT_TYPE="IMPACT_FACT"/"EFF_SPAN_LEN_USER")
    ELEMTYPE: str  # Element Type: "BEAM"/"TRUSS"/"PLATE", required if FACT_TYPE="EFF_SPAN_LEN_AUTO" (LANE_TYPE="LINE" only)
    PARTS: List[bool]  # Parts (Beam: [i,1/4,1/2,3/4,j] / Plate: [cent,i,j,k,l]), required if FACT_TYPE="EFF_SPAN_LEN_AUTO"
    COMPONENTS: List[bool]  # Components (Beam: 6 flags / Truss: 2 flags / Plate: 8 flags per Parameters table; see docstring for the Beam worked-example discrepancy), required if FACT_TYPE="EFF_SPAN_LEN_AUTO"


class AdditionalImpactFactorPayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #26 — /db/IMPF Specifications table.

    Usable codes: Korea.
    """

    ITEMS: List[AdditionalImpactFactorItem]  # required


class AdditionalImpactFactor(DbResource):
    ENDPOINT = "/db/IMPF"
    NAME = "Additional Impact Factor"


# --- 27. /db/DYFG — Railway Dynamic Factor ------------------------------------
# --- 28. /db/DYNF — Railway Dynamic Factor by Element -------------------------


class RailwayDynamicFactorPayload(TypedDict, total=False):
    """docs/manual/08_DB_Moving_Loads.md #27/#28 — /db/DYFG and /db/DYNF
    Specifications tables (identical shape for both; DYNF's Assign key is
    the Element ID instead of a serial number). Usable codes: Eurocode
    (set via /db/MVCD's ``CODE: "EUROCODE"`` first, or every write here
    answers "Wrong Field" regardless of payload).

    ⚠️ Live-confirmed 2026-08-25 on Civil NX: despite the manual marking
    LENGTH/MAINTAIN_TYPE/HEIGHT_COVER/DYN_FACTOR as conditionally required
    (only for their own INPUT_TYPE/OPT_REDUCE_EFF branch), **``/db/DYFG``
    rejects a POST/PUT with "Wrong Field" unless all six fields are sent
    together**, even the ones that don't apply to the chosen mode (send
    them as their zero/false default) — the same class of bug as
    ``/db/NMAS``'s undocumented-unconditional fields, just a clean
    rejection here rather than a crash. ``/db/DYNF`` does **not** share
    this — the documented conditional requiredness works there as
    written; only DYFG needs the all-fields workaround. Send all six
    explicitly on DYFG to avoid the ambiguity.
    """

    INPUT_TYPE: int  # Auto=0/User=1, required
    LENGTH: float  # Determinant Length (L-phi), required if INPUT_TYPE=0
    MAINTAIN_TYPE: int  # Quality of Track Maintenance: Carefully=0/Standard=1, required if INPUT_TYPE=0
    OPT_REDUCE_EFF: bool  # Consider Reduced Dynamic Effect, default false, optional
    HEIGHT_COVER: float  # Height of Cover (h), required if OPT_REDUCE_EFF=true
    DYN_FACTOR: float  # Dynamic Factor (phi), required if INPUT_TYPE=1


class RailwayDynamicFactor(DbResource):
    ENDPOINT = "/db/DYFG"
    NAME = "Railway Dynamic Factor"
    PRODUCTS = CIVIL_ONLY


class RailwayDynamicFactorByElement(DbResource):
    ENDPOINT = "/db/DYNF"
    NAME = "Railway Dynamic Factor by Element"
    PRODUCTS = CIVIL_ONLY
