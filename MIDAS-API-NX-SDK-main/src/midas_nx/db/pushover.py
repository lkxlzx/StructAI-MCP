"""Source: docs/manual/14_DB_Pushover.md, items 1-6."""
from __future__ import annotations

from typing import List, TypedDict

from .base import (
    GET_PUT_DELETE_METHODS,
    HYPER_S_ONLY,
    DbResource,
    InitialLoadCaseItem,
    OptUseToleranceValue,
)

# --- 1. /db/POGD — Pushover Analysis Control Data ---------------------------


class NonlinearAnalysisOptionPOGD(TypedDict, total=False):
    bPERMITFAIL: bool  # Permit Convergence Failure, default false, optional
    SUBSTEP: int  # Max Number of Substeps, optional
    MAXITER: int  # Maximum Iteration, optional
    bDISPLNORM: bool  # Use Convergence Criteria: Displacement Norm, default false, optional
    DISPLNORM: float  # Displacement Norm, default 0, optional
    bFORCENORM: bool  # Use Convergence Criteria: Force Norm, default false, optional
    FORCENORM: float  # Force Norm, default 0, optional
    bENERGYNORM: bool  # Use Convergence Criteria: Energy Norm, default false, optional
    ENERGYNORM: float  # Energy Norm, default 0, optional
    bSHEARYIELDSTOP: bool  # Analysis Stop - Shear Comp. Yield, default false, optional
    BSHEARYIELDSTOPBEAM: bool  # Analysis Stop - Shear Comp. Yield - Beam/Column, default false, optional
    bSHEARYIELDSTOPWALL: bool  # Analysis Stop - Shear Comp. Yield - Wall, default false, optional
    bAXIALYIELDSTOP: bool  # Analysis Stop - Axial Comp. Collapse/Buckling, default false, optional
    bAXIALYIELDSTOPBEAM: bool  # Analysis Stop - Axial Comp. Collapse/Buckling - Beam/Column, default false, optional
    bAXIALYIELDSTOPWALL: bool  # Analysis Stop - Axial Comp. Collapse/Buckling - Wall, default false, optional
    bAXIALYIELDSTOPTRUSS: bool  # Analysis Stop - Axial Comp. Collapse/Buckling - Truss, default false, optional
    bSUPPORTDZDIRSTOP: bool  # Analysis Stop - Support Uplifting/Collapse: Dz-Direction, default false, optional
    bSUPPORTSTOPUPLIFTING: bool  # Analysis Stop - Uplifting: Dz-Direction, default false, optional
    bSUPPORTSTOPCOLLAPSE: bool  # Analysis Stop - Collapse: Dz-Direction, default false, optional


class PushoverHingeDataOptionPOGD(TypedDict, total=False):
    bCONSREBARAREA1D: bool  # Fiber Model: Consider Beam/Column Reinforcement Area, optional
    BEAM_CORE_SIZE: str  # Beam-Column Core Area Size Type: "AUTO"/"EQUAL", optional
    BEAM_CORE_DIV_Y: int  # Beam-Column Core Division (y-dir), optional
    BEAM_CORE_DIV_Z: int  # Beam-Column Core Division (z-dir), optional
    BEAM_COVER_SIZE: str  # Beam-Column Cover Area Size Type, optional
    BEAM_COVER_DIV_Y: int  # Beam-Column Cover Division (y-dir), optional
    BEAM_COVER_DIV_Z: int  # Beam-Column Cover Division (z-dir), optional
    bCONSREBARAREAWALL: bool  # Fiber Model: Consider Wall Reinforcement Area, optional
    bWALLCONSOUT: bool  # Wall: Consider Out-of-plane Nonlinearity of Plate Type, optional
    WALL_CORE_SIZE: str  # Wall Core Fiber Area Size Type, optional
    WALL_CORE_DIV_Z: int  # Wall Core Division (z-dir), optional
    WALL_CORE_DIV_Y: int  # Wall Core Division (y-dir), optional
    WALL_COVER_SIZE: str  # Wall Cover Area Size Type, optional
    WALL_COVER_DIV_Z: int  # Wall Cover Division (z-dir), optional
    WALL_COVER_DIV_Y: int  # Wall Cover Division (y-dir), optional
    SHEAR_R: float  # Spring Shear factor, optional
    bASSIGNBYMEMBER: bool  # Assign Hinge Properties to Member only (Moment-Rotation Beam/Column), optional
    bTRI_SYM: bool  # Trilinear Default Stiffness Reduction: Symmetrical, optional
    TRI_TENS_A1: float  # Trilinear - Tens. a1, optional
    TRI_TENS_A2: float  # Trilinear - Tens. a2, optional
    TRI_COMP_A1: float  # Trilinear - Comp. a1, optional
    TRI_COMP_A2: float  # Trilinear - Comp. a2, optional
    bBI_SYM: bool  # Bilinear Default Stiffness Reduction: Symmetrical, optional
    BI_TENS_A1: float  # Bilinear - Tens. a1, optional
    BI_COMP_A1: float  # Bilinear - Comp. a1, optional
    PSPR_APPLY_TYPE: str  # Point Spring Support Apply Type: "APPLY"/"ASSUME", optional
    ELNK_APPLY_TYPE: str  # Elastic Link Apply Type: "APPLY"/"ASSUME", optional
    bUSEAUTOCALCREFERENCE: bool  # Use Reference Code/Manual for Auto-Calculation, optional
    RCDGNCODE: str  # RC Reference Design Code: "KISTEC2019"/"KISTEC2013"/"MOE2019"/"MOE2018"/"AIK-G-001-2021", optional
    LOC_BEAM: str  # Reference Location of Beam/Distributed Hinges: "I"/"J"/"M", optional
    LOC_COLUMN: str  # Reference Location of Column, optional
    SF_WALL: float  # Scale Factor for Ultimate Rotation - Wall, optional
    bSF_BRITTLE: bool  # Use Brittle Scale Factor, optional
    SF_BRITTLE: float  # Brittle Scale Factor, optional
    bSF_EARTHQUAKE: bool  # Use Earthquake Scale Factor, optional
    SF_EARTHQUAKE: float  # Earthquake Scale Factor, optional
    bSF_SMOOTH_BAR: bool  # Use Smooth-bar Scale Factor, optional
    SF_SMOOTH_BAR: float  # Smooth-bar Scale Factor, optional
    SND_SEIS_GRUP: str  # Secondary Seismic Elements Group Name, optional
    CONFIDENCE: float  # Confidence Factor, optional
    bBUCKLING: bool  # Calc Yield Surface of Beam considering Buckling, optional
    bCALCAXIALFORCE: bool  # Calc Mc Considering Axial Force (AIJ), optional


class PushoverAnalysisControlDataPayload(TypedDict, total=False):
    """docs/manual/14_DB_Pushover.md #1 — /db/POGD Specifications tables."""

    GEOMNONLINEAR_TYPE: str  # None="NONE"/Large Displacements="LARGE_DISP", default "NONE", optional
    INITLOADMETHOD: str  # Perform Analysis="PERFORM_ANAL"/Import Result="IMPORT_RESULT", default "PERFORM_ANAL", optional
    INITLOAD: List[InitialLoadCaseItem]  # Initial Load Case List, optional
    bCONSIGNOREELEM: bool  # Consider Ignore Elements for NL Analysis Initial Load, default false, optional
    NONL_OPT: NonlinearAnalysisOptionPOGD  # Nonlinear Analysis Option, required
    PHOP_OPT: PushoverHingeDataOptionPOGD  # Pushover Hinge Data Option, optional
    NODECONNECTIVITY: str  # Wall Node Connectivity: Pinned="PINNED"/Fixed="FIXED", required
    bSHOWGRAPHAFTER: bool  # Show Pushover Curve Result After Analysis, required
    bSHOWGRAPGHDURING: bool  # Show Pushover Curve during Analysis, required


class PushoverAnalysisControlData(DbResource):
    ENDPOINT = "/db/POGD"
    NAME = "Pushover Analysis Control Data"


# --- 2. /db/POGD-M1 — Pushover Global Control (Hyper-S) ---------------------


class ShearYieldStopHyperS(TypedDict, total=False):
    """If OPT_USE is true, at least one of BEAM_COLUMN/WALL must be true;
    if false, neither may be provided."""

    OPT_USE: bool  # required
    BEAM_COLUMN: bool  # optional
    WALL: bool  # optional


class AxialYieldStopHyperS(TypedDict, total=False):
    """If OPT_USE is true, at least one of BEAM/WALL/TRUSS must be true;
    if false, none may be provided."""

    OPT_USE: bool  # required
    BEAM_COLUMN: bool  # optional. Manual says BEAM here and BEAM_COLUMN in the
    # sibling SHEAR_YIELD group; /info/db/POGD-M1 says BEAM_COLUMN in both. MD-37.
    WALL: bool  # optional. Not declared by /info in either ANALYSIS_STOP group;
    # kept because /info listing a property is not the same as the server
    # accepting only those — /db/STBK's LCNAME is in no /info schema and its
    # confirmed live round trip sends it on both products. MD-37.
    TRUSS: bool  # optional


class SupportDzDirStopHyperS(TypedDict, total=False):
    """If OPT_USE is true, at least one of UPLIFTING/COLLAPSE must be true;
    if false, neither may be provided.

    The manual spells the first field `UPLIFT` in six places — its JSON
    Schema, both allOf rules, the Specifications table, both examples and
    the Python sample. `/info/db/POGD-M1` declares `UPLIFTING`. MD-37.
    """

    OPT_USE: bool  # required
    UPLIFTING: bool  # optional
    COLLAPSE: bool  # optional


class AnalysisStopHyperS(TypedDict, total=False):
    SHEAR_YIELD: ShearYieldStopHyperS  # optional
    AXIAL_YIELD: AxialYieldStopHyperS  # optional
    SUPPORT_DZ_DIR: SupportDzDirStopHyperS  # optional


class NormControlHyperS(TypedDict, total=False):
    """At least one of DISP/FORCE/ENERGY must have OPT_USE=true; each
    VALUE must be > 0 when its OPT_USE is true."""

    DISP: OptUseToleranceValue  # required
    FORCE: OptUseToleranceValue  # required
    ENERGY: OptUseToleranceValue  # required


class LineSearchHyperS(TypedDict, total=False):
    """OPT_USE=false forbids the detail fields; OPT_USE=true requires
    LINE_SEARCH_OPT; LINE_SEARCH_OPT="USER" requires the remaining three."""

    OPT_USE: bool  # required
    LINE_SEARCH_OPT: str  # "AUTO"/"USER", required if OPT_USE true
    START_ITER_NO: int  # required if LINE_SEARCH_OPT="USER"
    MAX_LINE_SEARCH_ITER: int  # required if LINE_SEARCH_OPT="USER"
    LINE_SEARCH_TOL: float  # required if LINE_SEARCH_OPT="USER"


class IterationControlHyperS(TypedDict, total=False):
    """ITER_BEF_UPDATE is required when STIFF_UPD_SCHEME=0 (Custom) and
    forbidden when 1 or 2 (Full Newton-Raphson/Initial Stiffness)."""

    PERMIT_FAIL: bool  # Permit Convergence Failure, optional
    MAX_ITER: int  # Maximum Iteration (>=1), required
    NORM_CTRL: NormControlHyperS  # Convergence Criteria, required
    STIFF_UPD_SCHEME: int  # Custom=0/Full Newton-Raphson=1/Initial Stiffness=2, required
    ITER_BEF_UPDATE: int  # Iterations before Stiffness Update, required if STIFF_UPD_SCHEME=0
    MAX_BISECT_LEVEL: int  # default 5, optional
    SMART_BISECT: bool  # default false, optional
    DIVERGENCE_THRESHOLD: float  # default 3, optional
    LINE_SEARCH: LineSearchHyperS  # optional


class NonlinearTypeHyperSPOGD(TypedDict, total=False):
    PSPRING_SUP: int  # Point Spring Support: Apply Nonlinear=0/Linear=1, required
    EL: int  # Elastic Link: Apply Nonlinear=0/Linear=1, required


class TrilinearStiffnessReductionHyperS(TypedDict, total=False):
    TENS_A1: float  # required
    TENS_A2: float  # required
    COMP_A1: float  # required
    COMP_A2: float  # required
    SYMMETRIC: bool  # required. Not declared by /info; kept, because dropping a
    # documented-required field on an omission from a schema already shown
    # incomplete would break every caller following the manual. MD-37.


class BilinearStiffnessReductionHyperS(TypedDict, total=False):
    TENS_A1: float  # required
    COMP_A1: float  # required
    SYMMETRIC: bool  # required. Same as Trilinear's. MD-37.


class PushoverHingeOptionHyperS(TypedDict, total=False):
    ASSIGN_BY_MEMBER: bool  # required
    NONL_TYPE: NonlinearTypeHyperSPOGD  # required
    TRILINEAR: TrilinearStiffnessReductionHyperS  # Skeleton Curve default stiffness reduction, required
    BILINEAR: BilinearStiffnessReductionHyperS  # Hinge property default stiffness reduction, required
    LOC_BEAM: int  # Distributed hinge reference location: I-End=0/Mid-span=1/J-End=2, required
    CALC_YIELDS: bool  # Calc Beam yield surface considering buckling, required


class PushoverMiscOptionHyperS(TypedDict, total=False):
    SHOW_GRAPH_AFTER: bool  # required
    SHOW_GRAPH_DURING: bool  # required


class PushoverAnalysisControlDataHyperSPayload(TypedDict, total=False):
    """docs/manual/14_DB_Pushover.md #2 — /db/POGD-M1 Specifications tables.

    If GEO_NONL_TYPE is 1 or 2 (Large Displacements/P-Delta), INIT_LOAD_TYPE
    must be 0. If INIT_LOAD_TYPE is 1 (import results), IGNORE_ELEM must not
    be provided.

    2026-08-26 re-verification (article id `56511008007705`) corrected
    `GEO_NONL_TYPE`'s enum order: this SDK had it as None=0/P-Delta=1/Large
    Displacements=2 (following the JSON Schema description's word order --
    "None / P-Delta / Large Displacements"), but the manual's own
    Specifications table numbers it None=0/**Large Displacements=1**/
    **P-Delta=2** instead -- the schema description text and the table
    contradict each other there, and the table wins. Cross-checked against
    this same-named field elsewhere in this SDK: `db/dynamic_loads.py`'s
    `TimeHistoryGlobalControlPayload.GNT` and
    `TimeHistoryGlobalControlHyperSPayload.GEO_NONL_TYPE` (from
    docs/manual/09_DB_Dynamic_Loads.md) both already had the corrected
    order (None=0/Large Displacement=1/P-Delta=2) -- this file was the
    inconsistent one. Not independently live-tested this session.
    """

    GEO_NONL_TYPE: int  # None=0/Large Displacements=1/P-Delta=2, required
    INIT_LOAD_TYPE: int  # Perform Nonlinear Static Analysis=0/Import Analysis Results=1, required
    INIT_LOAD_LIST: List[InitialLoadCaseItem]  # LC_NAME min length 1, SF != 0; optional
    IGNORE_ELEM: bool  # Consider "Ignore Elements for Initial Load", optional (forbidden if INIT_LOAD_TYPE=1)
    ANALYSIS_STOP: AnalysisStopHyperS  # optional
    ITER_CTRL: IterationControlHyperS  # required
    PO_HINGE_OPT: PushoverHingeOptionHyperS  # optional
    MISC: PushoverMiscOptionHyperS  # optional


class PushoverAnalysisControlDataHyperS(DbResource):
    ENDPOINT = "/db/POGD-M1"
    NAME = "Pushover Global Control (Hyper-S)"
    PRODUCTS = HYPER_S_ONLY
    METHODS = GET_PUT_DELETE_METHODS


# --- 3. /db/IEPI — Ignore Elements for Pushover Initial Load ----------------


class IgnoreElementsForPushoverInitialLoadPayload(TypedDict, total=False):
    """docs/manual/14_DB_Pushover.md #3 — /db/IEPI Specifications table.

    Assign Key is the Element ID (not a serial number).
    """

    B_IGNORE: bool  # Ignore Elements for NL Analysis Initial Load, default false, optional


class IgnoreElementsForPushoverInitialLoad(DbResource):
    ENDPOINT = "/db/IEPI"
    NAME = "Ignore Elements for Pushover Initial Load"


# --- 4. /db/PHGE — Assign Pushover Hinge Properties -------------------------


class AssignPushoverHingePropertiesPayload(TypedDict, total=False):
    """docs/manual/14_DB_Pushover.md #4 — /db/PHGE Specifications table.

    Assign Key is the assignment sequence number (not the element ID).

    2026-08-26 re-verification (article id `35992838417049`) added the 4th
    `TYPE` value: the manual's own text lists exactly 4 values (Beam/
    Column="BEAM", Wall (Gen NX only)="WALL", Truss="TRUSS", General
    Link="G-LINK") but had previously presented them with an unbounded
    "e.g." phrasing that omitted "G-LINK" entirely. Not independently
    live-tested this session.
    """

    ID: int  # Element ID, required
    TYPE: str  # Element Type: "BEAM"(Beam/Column)/"WALL"(Gen NX only)/"TRUSS"/"G-LINK"(General Link), required
    HINGE_TYPE: str  # Pushover Hinge Type (e.g. "Myz_15"), required
    FIBER_KEY: int  # required


class AssignPushoverHingeProperties(DbResource):
    ENDPOINT = "/db/PHGE"
    NAME = "Assign Pushover Hinge Properties"


# --- 5. /db/POLC — Pushover Load Cases --------------------------------------


class PushoverLoadPatternItem(TypedDict, total=False):
    """Fields used depend on the parent payload's LOADPATTERNTYPE:
    LCNAME/SF for "LOAD", DIR/SF for "ACC", MODE/SF for "MODE"/"NOR_MODE"."""

    LCNAME: str  # Load Case Name (LOADPATTERNTYPE="LOAD"), optional
    DIR: str  # Direction: "DX"/"DY"/"DZ" (LOADPATTERNTYPE="ACC"), optional
    MODE: int  # Mode Number (LOADPATTERNTYPE="MODE"/"NOR_MODE"), optional
    SF: float  # Scale Factor, required


class PushoverLoadCasePayload(TypedDict, total=False):
    """docs/manual/14_DB_Pushover.md #5 — /db/POLC Specifications tables.

    INCRE_METHOD selects between the Load Control (STEPCTRLOPTION/
    INCFUNC_KEY) and Displacement Control (DISPCTRLOPTION/...) field
    groups; flattened onto one payload (mirrors MaterialParam precedent).
    """

    LCNAME: str  # Load Case Name, required
    DESC: str  # default "", optional
    INCRE_STEP: int  # Increment Steps, required
    bCONS_PDELTA: bool  # Consider P-Delta Effect, required
    bUSEINITIAL: bool  # Use Initial Load, default false, optional
    bREACOUTPUT: bool  # Cumulative Reaction/Story Shear by Initial Load, default false, optional
    INCRE_METHOD: str  # Load Control="LOAD"/Displacement Control="DISP", required
    STEPCTRLOPTION: str  # "AUTO"/"EQUAL"/"INC_FUNC", required (INCRE_METHOD="LOAD")
    INCFUNC_KEY: int  # Increment Control Function Key, required (STEPCTRLOPTION="INC_FUNC")
    STIFF_RATIO: float  # Analysis Stop Condition: Current Stiffness Ratio (Cs), required
    DISPCTRLOPTION: str  # "GLOBAL"/"NODE", required (INCRE_METHOD="DISP")
    GLOBAL_MAX_DISP: float  # Global Max Translational Displacement, required (DISPCTRLOPTION="GLOBAL")
    MASTERNODE: int  # Master Node Key, required (DISPCTRLOPTION="NODE")
    MASTERDIRECTION: str  # "DX"/"DY"/"DZ", required (DISPCTRLOPTION="NODE")
    MASTERMAXDISP: float  # Master Node Displacement, required (DISPCTRLOPTION="NODE")
    bLIMITDEFORMANGLE: bool  # Use Limit Inter-Story Deformation Angle, default false, optional
    LIMITDEFORMANGLE: float  # Limit Inter-Story Deformation Angle (1/[rad]), required
    bDRIFTMAX: bool  # Maximum Drift of All Vertical Elements, default false, optional
    bDRIFTCENTER: bool  # Drift at the Center of Floor Diaphragm, default false, optional
    bDRIFTAVER: bool  # Drift calculated by Average Displacement of Story, default false, optional
    LOADPATTERNTYPE: str  # "LOAD"/"ACC"/"MODE"/"NOR_MODE", required
    LOADPATTERN: List[PushoverLoadPatternItem]  # Load Pattern Data List, required


class PushoverLoadCase(DbResource):
    ENDPOINT = "/db/POLC"
    NAME = "Pushover Load Cases"


# --- 6. /db/POLC-M1 — Pushover Load Case (Hyper-S) --------------------------


class PushoverControlOptionHyperS(TypedDict, total=False):
    """INCRE_METHOD selects the Load-control (STEPCTRLOPTION/INCFUNC_NAME/
    STIFF_RATIO) vs Displacement-control (DISPCTRLOPTION/...) field groups
    — the two groups are mutually exclusive within one payload."""

    STEPCTRLOPTION: str  # "AUTO"/"EQUAL"/"INC_FUNC", required if INCRE_METHOD="LOAD"
    INCFUNC_NAME: str  # required if STEPCTRLOPTION="INC_FUNC"
    STIFF_RATIO: float  # Current Stiffness Ratio (Cs), range [0,100], required if INCRE_METHOD="LOAD"
    DISPCTRLOPTION: str  # "GLOBAL"/"NODE", required if INCRE_METHOD="DISP"
    GLOBAL_MAX_DISP: float  # Max Translational Displacement (>0), required if DISPCTRLOPTION="GLOBAL"
    MASTERNODE: int  # required if DISPCTRLOPTION="NODE"
    MASTERDIRECTION: str  # "DX"/"DY"/"DZ", required if DISPCTRLOPTION="NODE"
    MASTERMAXDISP: float  # Max Displacement (!= 0), required if DISPCTRLOPTION="NODE"


class PushoverLoadPatternItemHyperS(TypedDict, total=False):
    """Fields used depend on the parent payload's LOADPATTERNTYPE:
    LCNAME/SF for "LOAD"; DIR/SF for "ACC" (array limited to 1 item);
    MODE/SF for "MODE"/"NOR_MODE" (array limited to 1 item)."""

    LCNAME: str  # optional
    DIR: str  # "DX"/"DY"/"DZ", optional
    MODE: int  # >0, optional
    SF: float  # Scale Factor (!= 0), required


class PushoverLoadCaseHyperSPayload(TypedDict, total=False):
    """docs/manual/14_DB_Pushover.md #6 — /db/POLC-M1 Specifications tables.

    bUSEINITIAL=true requires bREACOUTPUT; bUSEINITIAL=false forbids it.
    INCRE_METHOD selects which CTRL_OPT sub-fields apply (see
    PushoverControlOptionHyperS). LOADPATTERNTYPE constrains LOADPATTERN
    item shape and count (ACC/MODE/NOR_MODE are limited to exactly 1 item).
    """

    LCNAME: str  # 1-20 chars, unique in model, required
    DESC: str  # <=80 chars, default "", optional
    INCRE_STEP: int  # Increment Steps (>0, UI default 20), required
    NLTYPE: str  # None="NONE"/P-Delta="PDELTA"/Large Displacements="LARGE", required
    bUSEINITIAL: bool  # required
    bREACOUTPUT: bool  # required if bUSEINITIAL true, forbidden if false
    INCRE_METHOD: str  # Load Control="LOAD"/Displacement Control="DISP", required
    CTRL_OPT: PushoverControlOptionHyperS  # required
    LOADPATTERNTYPE: str  # "LOAD"/"ACC"/"MODE"/"NOR_MODE", required
    LOADPATTERN: List[PushoverLoadPatternItemHyperS]  # size >= 1, required


class PushoverLoadCaseHyperS(DbResource):
    """Serves POST, against what the chapter says - measured 2026-08-30.

    14_DB_Pushover.md normalizes this endpoint to GET/PUT/DELETE and warns
    that the official article's POST row is an untrimmed template. Live, on
    Civil NX 2026 v2.2, POST creates a record that reads back on GET. The
    normalization is the thing that is wrong; the article was right.

    Reported to the manual repo; see docs/live_verification_notes.md.
    """

    ENDPOINT = "/db/POLC-M1"
    NAME = "Pushover Load Case (Hyper-S)"
    PRODUCTS = HYPER_S_ONLY
