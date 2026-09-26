"""Source: docs/manual/12_DB_Analysis_Control.md, items 1-21."""
from __future__ import annotations

from typing import Any, List, TypedDict

from .base import (
    GET_PUT_DELETE_METHODS,
    HYPER_S_ONLY,
    DbResource,
    OptUseToleranceValue,
)


class ErectionLoadItem(TypedDict, total=False):
    """Shared shape for STCT's "vEREC" and STCT-M1's "ERECTION_LOAD" arrays."""

    LTYPECC: str  # Erection Load Case Name, required
    EREC: str  # Load Type for C.S (e.g. "D", "W"), required
    vLCNAME: List[str]  # Load Case Name List, required


# --- 1. /db/ACTL — Main Control Data --------------------------------------


class MainControlDataPayload(TypedDict, total=False):
    """docs/manual/12_DB_Analysis_Control.md #1 — /db/ACTL Specifications table."""

    ARDC: bool  # Auto Rotational DOF Constraint (Truss/Plane Stress/Solid), default false, optional
    ANRC: bool  # Auto Normal Rotation Constraint (Plate), default false, optional
    CSECF: bool  # Consider Section Stiffness Scale Factor for Stress Calc, default false, optional
    TRS: bool  # Transfer Reactions of Slave Node to Master Node, default false, optional
    BMSTRESS: bool  # Calculate Equivalent Beam Stresses (Von-Mises/Max-Shear), default false, optional
    CRBAR: bool  # Consider Reinforcement for Section Stiffness Calc, default false, optional
    CLATS: bool  # Change Local Axis of Tapered Section for Force/Stress Calc, default false, optional. Civil NX only
    ACWC: bool  # Auto Constraint for Wall Elements Connectivity. Gen NX only;
    # /info declares it and the manual documents it nowhere (checked across every chapter, 2026-09-04). MD-46.
    ITER: int  # Number of Iterations / Load Case, required
    TOL: float  # Convergence Tolerance, required


class MainControlData(DbResource):
    ENDPOINT = "/db/ACTL"
    NAME = "Main Control Data"


# --- 2. /db/ACTL-M1 — Main Control Data (Hyper-S) --------------------------


class TensionCompressionTrussConvergence(TypedDict, total=False):
    DISPL: OptUseToleranceValue
    LOAD: OptUseToleranceValue
    WORK: OptUseToleranceValue


class TensionCompressionTrussElement(TypedDict, total=False):
    NUMINC: int  # Number of Increments, default 1, optional
    INTOUT: str  # Intermediate Output Request: "EVERY"/"LAST", default "LAST", optional
    CONVERGENCE: TensionCompressionTrussConvergence  # optional


class MainControlDataHyperSPayload(TypedDict, total=False):
    """docs/manual/12_DB_Analysis_Control.md #2 — /db/ACTL-M1 Specifications table."""

    ARCD: bool  # Auto Rotational DOF Constraint, default true, optional
    ANRC: bool  # Auto Normal Rotation Constraint, default true, optional
    CSECF: bool  # Consider Section Stiffness Scale Factor, default false, optional
    CRBAR: bool  # Consider Reinforcement for Section Stiffness, default false, optional
    TRS: bool  # Transfer Reactions to Master Node, default true, optional
    CLATS: bool  # Change Local Axis of Tapered Section, default false, optional
    BMSTRESS: bool  # Calculate Equivalent Beam Stresses, default false, optional
    CLFORM: bool  # Classical Formula for Solid Element, default false, optional
    BSCHG: str  # Beam Section Property Changes: "CONSTANT"/"CHANGE", default "CHANGE", optional
    CABINIT: bool  # Consider Initial Tension for Cable Element, default true, optional
    TCELEM: TensionCompressionTrussElement  # Tension/Compression Truss Element, optional


class MainControlDataHyperS(DbResource):
    ENDPOINT = "/db/ACTL-M1"
    NAME = "Main Control Data (Hyper-S)"
    PRODUCTS = HYPER_S_ONLY
    METHODS = GET_PUT_DELETE_METHODS


# --- 3. /db/PDEL — P-Delta Analysis Control ---------------------------------


class PDeltaLoadCaseItem(TypedDict, total=False):
    LCNAME: str  # Load Case Name, required
    FACTOR: float  # Scale Factor, required


class PDeltaAnalysisControlPayload(TypedDict, total=False):
    """docs/manual/12_DB_Analysis_Control.md #3 — /db/PDEL Specifications table."""

    ITER: int  # Number of Iterations, required
    TOL: float  # Convergence Tolerance, default 0, optional
    PDEL_CASES: List[PDeltaLoadCaseItem]  # Load Cases, required


class PDeltaAnalysisControl(DbResource):
    ENDPOINT = "/db/PDEL"
    NAME = "P-Delta Analysis Control"


# --- 4. /db/BUCK — Buckling Analysis Control --------------------------------


class BucklingLoadCaseItem(TypedDict, total=False):
    LCNAME: str  # Load Case Name, required
    FACTOR: float  # Scale Factor, default 0, optional
    LOAD_TYPE: int  # Variable=0/Constant=1, default 0, optional


class BucklingAnalysisControlPayload(TypedDict, total=False):
    """docs/manual/12_DB_Analysis_Control.md #4 — /db/BUCK Specifications table."""

    MODE_NUM: int  # Number of Modes, required
    OPT_POSITIVE: bool  # Load Factor Range: Positive Only=true/Search=false, default false, optional
    LOAD_FACTOR_FROM: float  # Search From (when OPT_POSITIVE false), default 0, optional
    LOAD_FACTOR_TO: float  # Search To (when OPT_POSITIVE false), default 0, optional
    OPT_STURM_SEQ: bool  # Check Sturm Sequence, default false, optional
    OPT_CONSIDER_AXIAL_ONLY: bool  # Frame Geometric Stiffness: Consider Axial Only, default false, optional
    ITEMS: List[BucklingLoadCaseItem]  # Load Cases (Buckling Combination), required


class BucklingAnalysisControl(DbResource):
    ENDPOINT = "/db/BUCK"
    NAME = "Buckling Analysis Control"


# --- 5. /db/EIGV — Eigenvalue Analysis Control ------------------------------


class EigenvalueRitzLoadCaseItem(TypedDict, total=False):
    """Doc table lists the load-case-name key as "CASE" for both KIND
    values, but the worked example uses a "GROUND" key when
    KIND="GROUND" — both keys are included since the example is the more
    concrete source (same doc-inconsistency pattern as
    SeismicEarthPressurePayload.SEL_TYPE in static_loads.py)."""

    KIND: str  # Load Case Type: "GROUND"/"CASE", required
    GROUND: str  # Load Case Name when KIND="GROUND": "ACCX"/"ACCY"/"ACCZ", optional
    CASE: str  # Load Case Name when KIND="CASE": a defined load case name, optional
    iNOG: int  # Number of Generations, optional


class EigenvalueAnalysisControlPayload(TypedDict, total=False):
    """docs/manual/12_DB_Analysis_Control.md #5 — /db/EIGV Specifications tables.

    TYPE selects the analysis method (Subspace Iteration/Lanczos/Ritz);
    fields below are flattened onto one payload per variant (mirrors the
    MaterialParam precedent in properties/material.py).
    """

    TYPE: str  # "EIGEN"/"LANCZOS"/"RITZ", required
    # Subspace Iteration (TYPE="EIGEN") / Lanczos (TYPE="LANCZOS")
    iFREQ: int  # Number of Frequencies, required
    iITER: int  # Number of Iterations, required (EIGEN)
    iDIM: int  # Subspace Dimension, default 0, optional (EIGEN)
    TOL: float  # Convergence Tolerance, default 0, optional (EIGEN)
    bMINMAX: bool  # Frequency Range of Interest, default false, optional (LANCZOS)
    FRMIN: float  # Search From [cps] (when bMINMAX true), required (LANCZOS)
    FRMAX: float  # Search To [cps] (when bMINMAX true), required (LANCZOS)
    bSTRUM: bool  # Sturm Sequence Check, default false, optional (LANCZOS)
    # Ritz Vectors (TYPE="RITZ")
    bINCNL: bool  # Include GL-link Force Vectors, default false, optional (RITZ)
    iGNUM: int  # Number of Generations for Each GL-link Force, required (RITZ)
    vRITZ: List[EigenvalueRitzLoadCaseItem]  # Load Cases, required (RITZ)


class EigenvalueAnalysisControl(DbResource):
    ENDPOINT = "/db/EIGV"
    NAME = "Eigenvalue Analysis Control"


# --- 6. /db/EIGV-M1 — Eigenvalue Analysis Control (Hyper-S) -----------------


class EigenvalueFrequencyRangeHyperS(TypedDict, total=False):
    OPT_USE: bool  # required
    FREQ_MIN: float  # required if OPT_USE true
    FREQ_MAX: float  # required if OPT_USE true


class EigenvalueGlinkVectorHyperS(TypedDict, total=False):
    OPT_USE: bool  # required
    GLINK_NUMBER: int  # required if OPT_USE true


class EigenvalueRitzLoadItemHyperS(TypedDict, total=False):
    TYPE: str  # "GROUND"/"LOAD", required
    LOAD_NAME: str  # "ACCX"/"ACCY"/"ACCZ" or a load case name, required
    NUM_OF_GEN: int  # Number of Generations, required


class EigenvalueAnalysisControlHyperSPayload(TypedDict, total=False):
    """docs/manual/12_DB_Analysis_Control.md #6 — /db/EIGV-M1 Specifications tables."""

    ANAL_TYPE: str  # "LANCZOS"/"RITZ", required
    FREQ_NO: int  # Number of Frequencies (1~1000), required (LANCZOS)
    FREQ_RANGE: EigenvalueFrequencyRangeHyperS  # optional (LANCZOS)
    STURM_SEQ: bool  # Sturm Sequence Check, default false, optional (LANCZOS)
    GLINK_VECTOR: EigenvalueGlinkVectorHyperS  # Include GL-link Force Vectors, optional (RITZ)
    RITZ_LOAD: List[EigenvalueRitzLoadItemHyperS]  # Ritz Load Cases, required (RITZ)


class EigenvalueAnalysisControlHyperS(DbResource):
    ENDPOINT = "/db/EIGV-M1"
    NAME = "Eigenvalue Analysis Control (Hyper-S)"
    PRODUCTS = HYPER_S_ONLY
    METHODS = GET_PUT_DELETE_METHODS


# --- 7. /db/HHCT — Heat of Hydration Analysis Control -----------------------


class CreepShrinkageGeneralData(TypedDict, total=False):
    ITER: int  # Number of Iterations, default 0, optional
    TOL: float  # Tolerance, default 0, optional


class CreepShrinkageEffectiveModulusData(TypedDict, total=False):
    PHI1: float  # required
    DAY1: int  # required
    PHI2: float  # required
    DAY2: int  # required


class CreepShrinkageItem(TypedDict, total=False):
    """/db/HHCT's "ITEM" shape.

    Not shared with /db/HHCT-M1, which the docstring here used to claim: the
    Hyper-S endpoint has no ``M_GENERAL``. Both sources agree — the manual
    documents ``M_GENERAL`` in section 7's table (line 726) and nowhere in
    section 8's, and ``GET /info/db/HHCT-M1``'s ``ITEM`` declares only
    ``TYPE``, ``CREEP_CALC_METHOD`` and ``M_EFF_MOD`` where
    ``/info/db/HHCT``'s declares ``M_GENERAL`` too. See
    ``CreepShrinkageItemHyperS``.
    """

    TYPE: str  # "CREEP"/"SHRINK"/"BOTH", default "CREEP", optional
    CREEP_CALC_METHOD: int  # General=0/Effective Modulus=1, default 0, optional
    M_GENERAL: CreepShrinkageGeneralData  # optional, used when method=0
    M_EFF_MOD: CreepShrinkageEffectiveModulusData  # required when method=1


class CreepShrinkageItemHyperS(TypedDict, total=False):
    """/db/HHCT-M1's "ITEM" shape: CreepShrinkageItem without ``M_GENERAL``."""

    TYPE: str  # "CREEP"/"SHRINKAGE"/"BOTH", default "BOTH", optional
    CREEP_CALC_METHOD: int  # General=0/Effective Modulus=1, default 0, optional
    M_EFF_MOD: CreepShrinkageEffectiveModulusData  # required when method=1


class HeatOfHydrationAnalysisControlPayload(TypedDict, total=False):
    """docs/manual/12_DB_Analysis_Control.md #7 — /db/HHCT Specifications table."""

    FINAL_STAGE: bool  # Last Stage=true/Other Stage=false, default false, optional
    STAGE_NAME: str  # Construction Stage for Hydration, required if FINAL_STAGE false
    THETA: float  # Integration Factor, default 0, optional
    INIT_TEMP: float  # Initial Temperature, default 0, optional
    EVAL: str  # Element Stress Evaluation: "CENTER"/"GAUSS"/"NODAL", default "CENTER", optional
    OPT_IS_CREEP_SHRINKAGE: bool  # Creep & Shrinkage Option, default false, optional
    ITEM: CreepShrinkageItem  # Creep & Shrinkage settings, optional
    OPT_USE_EQUI_AGE: bool  # Use Equivalent Age by Time & Temperature, default false, optional
    OPT_INCL_SELF_WEIGHT: bool  # Include Self-weight Load, default false, optional
    SELF_WEIGHT_FACTOR: float  # Self-weight Factor, default 0, optional


class HeatOfHydrationAnalysisControl(DbResource):
    ENDPOINT = "/db/HHCT"
    NAME = "Heat of Hydration Analysis Control"


# --- 8. /db/HHCT-M1 — Heat of Hydration Analysis Control (Hyper-S) ----------


class ConvergenceCriterionCheck(TypedDict, total=False):
    """Shared {OPT_CHECK, VALUE} pair — distinct key name from the
    {OPT_USE, VALUE} pattern used elsewhere (see OptUseToleranceValue)."""

    OPT_CHECK: bool  # required
    VALUE: float  # required if OPT_CHECK true


class HeatOfHydrationConvergenceHyperS(TypedDict, total=False):
    DISP: ConvergenceCriterionCheck
    LOAD: ConvergenceCriterionCheck
    WORK: ConvergenceCriterionCheck


class HeatOfHydrationAnalysisControlHyperSPayload(TypedDict, total=False):
    """docs/manual/12_DB_Analysis_Control.md #8 — /db/HHCT-M1 Specifications table."""

    FINAL_STAGE: bool  # Last=true/Other=false, default true, optional
    STAGE_NAME: str  # required if FINAL_STAGE false
    INIT_TEMP: float  # default 20, optional
    EVAL: str  # "CENTER"/"GAUSS"/"NODAL", default "GAUSS", optional
    OPT_IS_CREEP_SHRINKAGE: bool  # default true, optional
    ITEM: CreepShrinkageItemHyperS  # required if OPT_IS_CREEP_SHRINKAGE true
    OPT_USE_EQUI_AGE: bool  # default true, optional
    OPT_INCL_SELF_WEIGHT: bool  # default false, optional
    SELF_WEIGHT_FACTOR: float  # required if OPT_INCL_SELF_WEIGHT true
    ITER: int  # Max Number of Iterations per Increment, default 50, optional
    CONVERGENCE: HeatOfHydrationConvergenceHyperS  # at least one of DISP/LOAD/WORK required, optional


class HeatOfHydrationAnalysisControlHyperS(DbResource):
    ENDPOINT = "/db/HHCT-M1"
    NAME = "Heat of Hydration Analysis Control (Hyper-S)"
    PRODUCTS = HYPER_S_ONLY
    METHODS = GET_PUT_DELETE_METHODS


# --- 9-13. Moving Load Analysis Control (Civil NX bridge feature) ----------
# Framed by the manual as a Civil NX bridge feature, not offered by Gen NX's
# (buildings) UI. Live-checked 2026-07-29 against a real production Gen NX
# model: all five variants below answer on Gen too (empty table; route +
# /info both resolve) — left at the class default (gen+civil), matching the
# correction made to the ch08 Moving Loads chapter's own convention. See
# db/base.py's GEN_ONLY docstring's sibling note.


class MovingLoadAnalysisControlPayload(TypedDict, total=False):
    """docs/manual/12_DB_Analysis_Control.md #9 — /db/MVCT Specifications table.

    Trailing Russia-code fields (MATTYPE.. MAXSPACE) are only sent when that
    code is active.
    """

    METHOD: str  # Analysis Method (Civil NX only): "EXACT"/"PIVOT"/"QUICK", default "EXACT", optional
    POINT: str  # Load Point Selection: "INF"/"ALL", required
    iIGP: int  # Influence Generating Points: Number/Line=0/Distance=1, default 0, optional
    iIGPN: int  # Number/Line Element (when iIGP=0), required
    DIST: float  # Distance between Points (when iIGP=1), required
    PLATE: str  # Plate Options: "CENTER"/"NODAL", required
    bSTRCALC: bool  # Plate - Stress, default false, optional
    bCONCURRENT: bool  # Plate - Concurrent Force, default false, optional
    FRAME: str  # Frame Options: "NORMAL"/"AXIAL", required
    bCSTRCALC: bool  # Frame - Combined Stress, default false, optional
    bCONCLINK: bool  # Link - Concurrent Force of Elastic/General Links, default false, optional
    bREAC: bool  # Filter - Reactions, default false, optional
    bRG: bool  # Reactions Option: All=false/Structure Group=true, default false, optional
    RGN: str  # Reactions Group Name (when bRG true), required
    bDISP: bool  # Filter - Displacements, default false, optional
    bDG: bool  # Displacements Option: All=false/Structure Group=true, default false, optional
    DGN: str  # Displacements Group Name (when bDG true), required
    bFM: bool  # Filter - Forces/Moments, default false, optional
    bFG: bool  # Forces/Moments Option: All=false/Structure Group=true, default false, optional
    FGN: str  # Forces/Moments Group Name (when bFG true), required
    bL: bool  # Filter - Elastic/General Link, default false, optional
    bLG: bool  # Link Option: All=false/Boundary Group=true, default false, optional
    LGN: str  # Link Group Name (when bLG true), required
    MATTYPE: int  # Russia code only, optional
    BRIDGETYPE: int  # Russia code only, optional
    AKMATTYPE: int  # Russia code only, optional
    AKBRIDGETYPE: int  # Russia code only, optional
    MINFACTS2: float  # Russia code only: minimum factor, optional
    MAXV: int  # Russia code only: maximum successive vehicles, optional
    INCV: int  # Russia code only: vehicle increment, optional
    MAXSPACE: float  # Russia code only: maximum train spacing, optional


class MovingLoadAnalysisControl(DbResource):
    ENDPOINT = "/db/MVCT"
    NAME = "Moving Load Analysis Control"


class MovingLoadAnalysisControlChinaPayload(TypedDict, total=False):
    """docs/manual/12_DB_Analysis_Control.md #10 — /db/MVCTch Specifications tables.

    FREQ/BRIDGE1/BRIDGE2 are deeply nested, bridge-type-dependent objects —
    left as Any for v1, matching the SectBefore.SECT_I precedent.
    """

    POINT: str  # "INF"/"ALL", required
    iIGP: int  # default 0, optional
    UNUMT: int  # Number/Line Element (when iIGP=0), required
    DIST: float  # Distance between Points (when iIGP=1), required
    PLATE: str  # "CENTER"/"NODAL", required
    bSTRCALC: bool  # default false, optional
    FRAME: str  # "NORMAL"/"AXIAL", required
    bCSTRCALC: bool  # default false, optional
    bREAC: bool  # default false, optional
    bRG: bool  # default false, optional
    RGN: str  # required if bRG true
    bDISP: bool  # default false, optional
    bDG: bool  # default false, optional
    DGN: str  # required if bDG true
    bFM: bool  # default false, optional
    bFG: bool  # default false, optional
    FGN: str  # required if bFG true
    bL: bool  # default false, optional
    bLG: bool  # default false, optional
    LGN: str  # required if bLG true
    bIF: bool  # Use Impact Factor, default false, optional
    iCODETYPE: int  # Code Type, optional
    iNFM: int  # Natural Frequency Method, optional
    iSLCM: int  # Span Length Calculation Method, optional
    bBC: bool  # Use Vehicle Load Class, default false, optional
    iBC: int  # Vehicle Load Class Type, optional
    FREQ: Any  # Frequency Data (JTG D60-2015/JTG 04): {"USER_F","SBEM_*","CBEM_*","ARCH_*","CABL_*","SUSP_*",...}
    BRIDGE1: Any  # Bridge Data (other codes): {"BTYPE","RC_*","STL_*","MBRG_*",...}
    BRIDGE2: Any  # Bridge Data (iCODETYPE=2/3): {"BTYPE","RAIL_*","CULV_*",...}


class MovingLoadAnalysisControlChina(DbResource):
    ENDPOINT = "/db/MVCTch"
    NAME = "Moving Load Analysis Control – China"


class MovingLoadAnalysisControlIndiaPayload(TypedDict, total=False):
    """docs/manual/12_DB_Analysis_Control.md #11 — /db/MVCTid Specifications table."""

    iIGP: int  # default 0, optional
    UNUMT: int  # Number/Line Element, required when iIGP=0
    DIST: float  # Distance between Points, required when iIGP=1
    PLATE: str  # "CENTER"/"NODAL", required
    bSTRCALC: bool  # default false, optional
    FRAME: str  # "NORMAL"/"AXIAL", required
    bCSTRCALC: bool  # default false, optional
    bREAC: bool  # default false, optional
    bRGP: bool  # default false, optional
    RGP: str  # required if bRGP true
    bDISP: bool  # default false, optional
    bDGP: bool  # default false, optional
    DGP: str  # required if bDGP true
    bFM: bool  # default false, optional
    bFGP: bool  # default false, optional
    FGP: str  # required if bFGP true
    bL: bool  # default false, optional
    bLG: bool  # default false, optional
    LGP: str  # required if bLG true
    BRIDGE: int  # Bridge Type for Impact/CDA: Steel=0/RC=1, default 0, optional
    TRACKS: int  # Single=0/Double=1/Multiple=2, default 0, optional
    WIDTHTYPE: int  # Sleeper Width Type: Type1=0/Type2=1/User=2, default 0, optional
    WIDTH: float  # Sleeper Width for User, default 0, optional
    DEPTH: float  # Depth of Fill, default 0, optional
    VHMAX: int  # Maximum Successive Vehicles, required


class MovingLoadAnalysisControlIndia(DbResource):
    ENDPOINT = "/db/MVCTid"
    NAME = "Moving Load Analysis Control – India"


class MovingLoadAnalysisControlBSPayload(TypedDict, total=False):
    """docs/manual/12_DB_Analysis_Control.md #12 — /db/MVCTbs Specifications table."""

    iIGP: int  # default 0, optional
    UNUMT: int  # Number/Line Element, required when iIGP=0
    DIST: float  # Distance between Points, required when iIGP=1
    PLATE: str  # "CENTER"/"NODAL", required
    bSTRCALC: bool  # default false, optional
    bCONCURRENT: bool  # Plate - Concurrent Force, default false, optional
    FRAME: str  # "NORMAL"/"AXIAL", required
    bCSTRCALC: bool  # default false, optional
    bREAC: bool  # default false, optional
    bRGP: bool  # default false, optional
    RGP: str  # required if bRGP true
    bDISP: bool  # default false, optional
    bDGP: bool  # default false, optional
    DGP: str  # required if bDGP true
    bFM: bool  # default false, optional
    bFGP: bool  # default false, optional
    FGP: str  # required if bFGP true
    bL: bool  # default false, optional
    bLG: bool  # default false, optional
    LGP: str  # required if bLG true
    NUMLANE: int  # N for HA Lane Factor/ALL Model 2: N<6=0/N>=6=1, default 0, optional


class MovingLoadAnalysisControlBS(DbResource):
    ENDPOINT = "/db/MVCTbs"
    NAME = "Moving Load Analysis Control – BS"


class MovingLoadAnalysisControlTransversePayload(TypedDict, total=False):
    """docs/manual/12_DB_Analysis_Control.md #13 — /db/MVCTtr Specifications table."""

    LOAD_POINT_SEL: int  # Influence Line Dependent=1/All Point=2, required
    INFL_GEN_POINT: int  # Number/Line=0/Distance=1, default 0, optional
    NUM_UNIT_LOAD: int  # Number/Line Element, required when INFL_GEN_POINT=0
    DISTANCE: float  # Distance between Points, required when INFL_GEN_POINT=1
    ANALYSIS_RESULT: int  # Normal=1/Normal+Concurrent Force/Stress=2, required
    OPT_COMBINED_STR: bool  # Combined Stress, default false, optional
    OPT_REACTIONS: bool  # Reactions, default false, optional
    OPT_DISPLACEMENTS: bool  # Displacement, default false, optional
    OPT_FORCE: bool  # Forces/Moments, default false, optional


class MovingLoadAnalysisControlTransverse(DbResource):
    ENDPOINT = "/db/MVCTtr"
    NAME = "Moving Load Analysis Control – Transverse"


# --- 14. /db/SMCT — Settlement Analysis Control Data ------------------------


class SettlementAnalysisControlDataPayload(TypedDict, total=False):
    """docs/manual/12_DB_Analysis_Control.md #14 — /db/SMCT Specifications table."""

    CONCURRENT_CALC: bool  # Plate Concurrent Force, default false, optional
    CONCURRENT_LINK: bool  # Elastic/General Links Concurrent Force, default false, optional


class SettlementAnalysisControlData(DbResource):
    ENDPOINT = "/db/SMCT"
    NAME = "Settlement Analysis Control Data"


# --- 15. /db/NLCT — Nonlinear Analysis Control Data -------------------------


class NonlinearNewtonItem(TypedDict, total=False):
    ITERATION_METHOD: str  # "NEWTON", default "NEWTON", optional
    LCNAME: str  # required
    NUMBER_STEPS: float  # required
    MAX_ITERATIONS: int  # required
    LOAD_FACTORS: List[float]  # default [1], optional


class NonlinearArcLengthItem(TypedDict, total=False):
    ITERATION_METHOD: str  # "ARC", default "ARC", optional
    LCNAME: str  # required
    INITIAL_FORCE_RATIO_ARC_LEN: float  # required
    NUMBER_STEPS: float  # required
    MAX_ITERATIONS: int  # required
    MAXIMUM_DISPLACEMENT: float  # required


class NonlinearDisplacementControlItem(TypedDict, total=False):
    ITERATION_METHOD: str  # "DISP", default "DISP", optional
    LCNAME: str  # required
    NUMBER_STEPS: int  # required
    MAX_ITERATIONS: float  # required
    MASTER_NODE: int  # required
    DIRECTION: int  # Dx=0/Dy=1/Dz=2, default 0, optional
    MAXIMUM_DISPLACEMENT: float  # required
    LOAD_FACTORS: List[float]  # Master Node Displacement (Index: Step), default [1], optional


class NonlinearAnalysisControlDataPayload(TypedDict, total=False):
    """docs/manual/12_DB_Analysis_Control.md #15 — /db/NLCT Specifications tables.

    ITERATION_METHOD selects which of NEWTON_ITEMS/ARCLEN_ITEMS/DISPCT_ITEMS
    is used; fields flattened onto one payload (mirrors MaterialParam
    precedent in properties/material.py).
    """

    NONLINEAR_TYPE: str  # "GEOM"/"MATL"/"GEOM+MATL", default "GEOM", optional
    ITERATION_METHOD: str  # "NEWTON"/"ARC"/"DISP", default "NEWTON", optional
    OPT_ENERGY_NORM: bool  # default false, optional
    ENERGY_NORM: float  # required if OPT_ENERGY_NORM true
    OPT_DISPLACEMENT_NORM: bool  # default false, optional
    DISPLACEMENT_NORM: float  # required if OPT_DISPLACEMENT_NORM true
    OPT_FORCE_NORM: bool  # default false, optional
    FORCE_NORM: float  # required if OPT_FORCE_NORM true
    NUMBER_STEPS: int  # Number of Load Steps, required (NEWTON/ARC/DISP)
    MAX_ITERATIONS: int  # Maximum Number of Iterations/Load Step, required (NEWTON/ARC/DISP)
    NEWTON_ITEMS: List[NonlinearNewtonItem]  # Load Case Specific Data, required (NEWTON)
    INITIAL_FORCE_RATIO_ARC_LEN: float  # Initial Force Ratio for Unit Arc-Length, required (ARC)
    MAXIMUM_DISPLACEMENT: float  # Maximum Displacement Bound, required (ARC/DISP)
    ARCLEN_ITEMS: List[NonlinearArcLengthItem]  # Load Case Specific Data, required (ARC)
    MASTER_NODE: int  # Master Node ID, required (DISP)
    DIRECTION: int  # Dx=0/Dy=1/Dz=2, default 0, optional (DISP)
    DISPCT_ITEMS: List[NonlinearDisplacementControlItem]  # Load Case Specific Data, required (DISP)


class NonlinearAnalysisControlData(DbResource):
    ENDPOINT = "/db/NLCT"
    NAME = "Nonlinear Analysis Control Data"


# --- 16. /db/NLCT-M1 — Nonlinear Analysis Control (Hyper-S) -----------------


class NonlinearLoadStepsHyperS(TypedDict, total=False):
    STEP_MODE: str  # e.g. "AUTO", required
    NUMBER_STEPS: int  # required
    OUTPUT: str  # "EVERY"/"LAST", required
    MIN_ARC_RATIO: float  # ARC only, optional
    MAX_ARC_RATIO: float  # ARC only, optional
    MAX_ARC_INCREMENTS: int  # ARC only, optional


class NonlinearConvergenceCriteriaHyperS(TypedDict, total=False):
    DISP: OptUseToleranceValue
    LOAD: OptUseToleranceValue
    WORK: OptUseToleranceValue


class NonlinearAnalysisControlHyperSPayload(TypedDict, total=False):
    """docs/manual/12_DB_Analysis_Control.md #16 — /db/NLCT-M1 Specifications tables."""

    LC_SCOPE: str  # Load Case Scope, required
    NONLINEAR_TYPE: str  # "GEOM"/"MATL"/"GEOM_MATL", required
    ITER_METHOD: str  # Force Control="FORCE"/Arc Length="ARC"/Displacement="DISP", required
    LOAD_STEPS: NonlinearLoadStepsHyperS  # required
    CONV_CRITERIA: NonlinearConvergenceCriteriaHyperS  # required


class NonlinearAnalysisControlHyperS(DbResource):
    ENDPOINT = "/db/NLCT-M1"
    NAME = "Nonlinear Analysis Control (Hyper-S)"
    PRODUCTS = HYPER_S_ONLY
    METHODS = GET_PUT_DELETE_METHODS


# --- 17. /db/STCT — Construction Stage Analysis Control Data ----------------


class ConstructionStageAnalysisControlDataPayload(TypedDict, total=False):
    """docs/manual/12_DB_Analysis_Control.md #17 — /db/STCT Specifications tables.

    iINC_NLA (Linear=0/Nonlinear=1/Material Nonlinear=2) and iNLA_TYPE
    (Independent=0/Accumulative=1) together select which field group below
    applies; flattened onto one payload (mirrors MaterialParam precedent).

    2026-08-25 re-verification (article id `35990281053465`) corrected
    `iBSC`'s label: it was previously described as "Bi-Section Control"
    (a nonlinear iteration concept, actually covered by the unrelated
    `BSSTEP`/`ADSTEP` fields below), but the manual's own Specifications
    table names it "Beam Section Property Option" (Constant=0/Change with
    Tendon=1) -- a completely different concept. Not independently
    live-tested (a `/db/STCT` round trip needs a real construction-stage
    model this session's scratch document doesn't have).
    """

    bLAST_FINAL: bool  # Last Stage=true/Other Stage=false, default false, optional
    FINAL_STAGE: str  # Construction Stage Name, required if bLAST_FINAL false
    iINC_NLA: int  # Linear=0/Nonlinear=1/Material Nonlinear=2 (1,2 are Civil NX only), default 0, optional
    iNLA_TYPE: int  # Independent=0/Accumulative=1, default 0, optional
    vEREC: List[ErectionLoadItem]  # Erection Load for Construction Stage, default [], optional
    bSDLE: bool  # Secondary Dead Load Effect for Grid Model, default false, optional
    vSDLE: List[str]  # Grid Analysis Load Case Names, required if bSDLE true
    CPFC: str  # Cable-Pretension Force Type: "INTERNAL"/"EXTERNAL", default "INTERNAL", optional
    bEXT_REPL: bool  # External Force Type replace, default false, optional
    bCONV: bool  # Convert Final Stage Member Forces to Initial Forces for Post C.S, default false, optional
    bTRUSS: bool  # required if bCONV true
    bBEAM: bool  # required if bCONV true
    bCHANGE_CABLE: bool  # Change Cable Element to Equivalent Truss for Post C.S., default false, optional
    bAPPLY_IMF: bool  # Apply Initial Member Force to C.S, default false, optional
    bITD: bool  # Use Initial Tangent Displacement, default false, optional
    ITD: str  # Initial Tangent Displacement Type (e.g. "GROUP"), optional
    GROUP: str  # Structure Group Name, optional
    bLFFC: bool  # Use Lack-of-Fit Force Control, default false, optional
    LFFGR: str  # Lack-of-Fit Group Name, optional
    bCAMBER: bool  # Apply Camber Displacement to C.S., default false, optional
    bCALC_CFF: bool  # Calculate Concurrent Forces of Frame, default false, optional
    bCALC_CSP: bool  # Calculate Output of Each Part of Composite Section, default false, optional
    bSELFCONS: bool  # Self-constrained Forces & Stresses, default false, optional
    bSAVE_OCS: bool  # Save Output of Construction Stage, default false, optional
    bSD: bool  # Use Stress Decrease, optional
    iSDOPT: int  # Stress Decrease Option, optional
    SDCONST: float  # Stress Decrease Constant, optional
    iBSC: int  # Beam Section Property Option: Constant=0/Change with Tendon=1, default 0, optional
    bINC_PDL: bool  # Include P-Delta Effect (Civil NX only), default false, optional
    iITER: int  # Number of Iterations (Linear), optional
    TOL: float  # Convergence Tolerance (Linear), optional
    iLSTEP: int  # Number of Load Steps (Nonlinear), optional
    iMAXITER: int  # Maximum Number of Iterations (Nonlinear), optional
    CF: bool  # Use Convergence Failure (Nonlinear), default false, optional
    BSSTEP: int  # Max Bi-Section Level for a Load Step (Nonlinear), optional
    ADSTEP: int  # Max Allowable Diverged Steps (Nonlinear), optional
    bENEG: bool  # Use Energy Norm (Nonlinear), optional
    EV: float  # Energy Norm Value (Nonlinear), optional
    bDISP: bool  # Use Displacement Norm (Nonlinear), optional
    DV: float  # Displacement Norm Value (Nonlinear), optional
    bFORC: bool  # Use Force Norm (Nonlinear), optional
    FV: float  # Force Norm Value (Nonlinear), optional
    bIEMF: bool  # Include Equilibrium Element Nodal Forces (Nonlinear), default false, optional
    bINC_TDE: bool  # Include Time Dependent Effect (Accumulative), default false, optional
    bCNS: bool  # Use Creep & Shrinkage (Accumulative), default false, optional
    TYPE: str  # Creep & Shrinkage Type: "CREEP"/"SHRINK"/"BOTH" (Accumulative), optional
    iITER_CR: int  # Number of Creep Iterations (Accumulative), optional
    TOL_CR: float  # Creep Tolerance (Accumulative), optional
    bOUCC: bool  # Only User's Creep Coefficient (Accumulative), default false, optional
    bITS: bool  # Use Internal Time Step for Creep (Accumulative), optional
    iITS: int  # Internal Time Step value (Accumulative), optional
    bATS: bool  # Auto Time Step Generation for Large Time Gap (Accumulative), default false, optional
    iT10: int  # Time Gap Steps for T>10 (Accumulative), optional
    iT100: int  # Time Gap Steps for T>100 (Accumulative), optional
    iT1K: int  # Time Gap Steps for T>1000 (Accumulative), optional
    iT5K: int  # Time Gap Steps for T>5000 (Accumulative), optional
    iT10K: int  # Time Gap Steps for T>10000 (Accumulative), optional
    bTTLE_CS: bool  # Tendon Tension Loss Effect: Creep & Shrinkage (Accumulative), default false, optional
    bRCE: bool  # Consider Re-bar Confinement Effect (Accumulative), default false, optional
    bVAR: bool  # Variation of Comp. Strength (Accumulative), default false, optional
    bTTLE_ES: bool  # Tendon Tension Loss Effect: Elastic Shortening (Accumulative), default false, optional
    iTTLE_ES: int  # Tendon Tension Loss Effect: Elastic Shortening Type (Accumulative), optional
    bAPPLY_ELA: bool  # Apply Time Dependent Elastic Modulus to Post C.S (Accumulative), default false, optional


class ConstructionStageAnalysisControlData(DbResource):
    ENDPOINT = "/db/STCT"
    NAME = "Construction Stage Analysis Control Data"


# --- 18. /db/STCT-M1 — Construction Stage Analysis Control Data (Hyper-S) --


class ConstructionStageAnalysisTypeHyperS(TypedDict, total=False):
    """STCT-M1's "ANAL_TYPE" sub-object.

    2026-08-25 re-verification (article id `57053813627673`) added
    `iINC_NLA`'s 4th value (`3`=Geometric+Material Nonlinear -- when
    `iINC_NLA` is 2 or 3, `iNLA_TYPE` only accepts 1/Accumulative) and the
    previously entirely-missing `bIEMF` field.

    **Live-confirmed 2026-08-27 on Civil NX**, both via `POST`-time
    creation rather than `PUT` on an existing record (this object is
    write-once in practice -- a `PUT` fails with `"Wrong Field"` even for
    an already-documented known-good value pair on an existing record, so
    testing new values via `PUT` was a dead end; creating fresh with the
    new value works fine): `{"iINC_NLA": 3, "iNLA_TYPE": 1}` round-tripped
    exactly, and separately `{"iINC_NLA": 1, "iNLA_TYPE": 0, "bIEMF":
    true}` round-tripped exactly too. Both confirmed real.
    """

    iINC_NLA: int  # Linear=0/Nonlinear=1/Material Nonlinear=2/Geometric+Material Nonlinear=3, required
    iNLA_TYPE: int  # Independent=0/Accumulative=1 (only 1 allowed if iINC_NLA in {2,3}), required
    bIEMF: bool  # Include Equilibrium Element Nodal Forces (iINC_NLA=1 & iNLA_TYPE=0 only), optional
    bINC_PDL: bool  # Include P-Delta Effect (iINC_NLA=0 only), optional
    bINC_TDE: bool  # Include Time Dependent Effect (iNLA_TYPE=1 & iINC_NLA in {0,1} only), optional


class ConstructionStageRestartHyperS(TypedDict, total=False):
    OPT_USE: bool  # required
    RESTART_STAGE: List[str]  # required if OPT_USE true


class InternalTimeStepHyperS(TypedDict, total=False):
    OPT_USE: bool  # required
    iITS: int  # required if OPT_USE true


class AutoTimeStepHyperS(TypedDict, total=False):
    OPT_USE: bool  # required
    iT10: int  # optional
    iT100: int  # optional
    iT1K: int  # optional
    iT5K: int  # optional
    iT10K: int  # optional


class CreepShrinkageControlHyperS(TypedDict, total=False):
    """STCT-M1's "TIME_DEP_CONTROL.CREEP_SHRINKAGE" sub-object.

    2026-08-25 re-verification (article id `57053813627673`) corrected
    `TYPE`'s 2nd enum value: STCT-M1 uses `"SHRINKAGE"`, not the legacy
    `/db/STCT`'s `"SHRINK"` -- confirmed consistently in both the manual's
    JSON Schema and its own Specifications table for this endpoint.
    **Live-confirmed 2026-08-27 on Civil NX**: `POST /db/STCT-M1` with
    `{"OPT_USE": true, "TYPE": "SHRINKAGE"}` succeeded and `GET` read it
    back verbatim (a separate creation that omitted `TYPE` entirely
    defaulted to `"BOTH"`, confirming that value too).
    """

    OPT_USE: bool  # required
    TYPE: str  # "CREEP"/"SHRINKAGE"/"BOTH" (NOT "SHRINK" -- that's legacy STCT's spelling), optional
    bOUCC: bool  # Only User's Creep Coefficient, optional
    INTERNAL_STEP: InternalTimeStepHyperS  # optional
    AUTO_TIME_STEP: AutoTimeStepHyperS  # optional
    bTTLE_CS: bool  # Tendon Tension Loss Effect (Creep & Shrinkage), optional
    bRCE: bool  # Re-bar Confinement Effect, optional


class TimeDependentControlHyperS(TypedDict, total=False):
    CREEP_SHRINKAGE: CreepShrinkageControlHyperS  # optional
    bVAR: bool  # Variation of Comp. Strength, optional
    bAPPLY_ELA: bool  # Apply Time Dependent Elastic Modulus to Post C.S, optional
    bTTLE_ES: bool  # Tendon Tension Loss Effect (Elastic Shortening), optional
    iTTLE_ES: int  # Tendon Tension Loss Effect (Elastic Shortening) Type, optional


class CableControlHyperS(TypedDict, total=False):
    CPFC: str  # "INTERNAL"/"EXTERNAL", optional
    bEXT_REPL: bool  # optional


class InitialForceControlHyperS(TypedDict, total=False):
    bCONV: bool  # optional
    bTRUSS: bool  # optional
    bBEAM: bool  # optional
    bCHANGE_CABLE: bool  # optional
    bAPPLY_IMF: bool  # optional


class InitialTangentDisplacementControlHyperS(TypedDict, total=False):
    OPT_USE: bool  # optional
    ITD: str  # optional
    GROUP: str  # optional
    LFFC_OPT_USE: bool  # optional
    LFFGR: str  # optional


class InitialDisplacementHyperS(TypedDict, total=False):
    ITD_CONTROL: InitialTangentDisplacementControlHyperS  # optional
    bCAMBER: bool  # optional


class StressDecreaseHyperS(TypedDict, total=False):
    OPT_USE: bool  # optional
    iSDOPT: int  # optional
    SDCONST: float  # optional


class FrameOutputHyperS(TypedDict, total=False):
    """STCT-M1's "FRAME_OUTPUT" sub-object."""

    bCALC_CFF: bool  # Calculate Concurrent Forces of Frame, optional
    bCALC_CSP: bool  # Calculate Output of Each Part of Composite Section, optional
    bSELFCONS: bool  # Self-constrained Forces & Stresses, optional


class LineSearchHyperSStct(TypedDict, total=False):
    """STCT-M1's "NONL_CONTROL"."ADVANCED"."LINE_SEARCH" sub-object.

    Named apart from NLCT-M1's line-search object on purpose: the manual warns
    that §16's ADVANCED uses different key names and string enums for the same
    concepts, and that the two must not be mixed.
    """

    OPT_USE: bool  # required
    LINE_SEARCH_TYPE: str  # "AUTO"/"USER", default "AUTO"
    MAX_LN_SRCH_ITER: int  # LINE_SEARCH_TYPE="USER" only
    LN_SEARCH_TOL: float  # LINE_SEARCH_TYPE="USER" only


class NonlinearAdvancedHyperSStct(TypedDict, total=False):
    """STCT-M1's "NONL_CONTROL"."ADVANCED" sub-object.

    The manual states this whole subtree as prose inside one Description cell
    (MD-21); the key names below are the section's Request Example, and a live
    GET on 2026-08-27 returned ``{"USE_DEF_SETTINGS": true}`` for a record the
    server filled in itself.
    """

    USE_DEF_SETTINGS: bool  # default true, required
    STIFF_UPD_SCHEME: int  # Custom=0, Full Newton-Raphson=1, Initial Stiffness=2; USE_DEF_SETTINGS=false only
    ITER_BEF_UPDATE: int  # STIFF_UPD_SCHEME=0 only
    TERMINATE_ON_FAIL_CONV: bool
    MAX_ITER_INCREMENT: int
    MAX_BISECT_LEVEL: int
    SMART_BISECT: bool
    DIVERG_THRESH: float
    ENABLE_LINE_SEARCH: bool  # default true
    LINE_SEARCH: LineSearchHyperSStct  # required when ENABLE_LINE_SEARCH=true


class ConvergenceCriterionHyperSStct(TypedDict, total=False):
    """One of STCT-M1's "NONL_CONTROL" DISP/LOAD/WORK convergence criteria.

    The manual keys all three in a single cell as ``"DISP"/"LOAD"/"WORK"``
    (MD-21); the Request Example sends them as three sibling objects.
    """

    OPT_USE: bool  # default false, required
    VALUE: float  # > 0, required when OPT_USE=true


class NonlinearControlHyperSStct(TypedDict, total=False):
    """STCT-M1's "NONL_CONTROL" sub-object, used when ANAL_TYPE.iINC_NLA != 0.

    Typed out as of 2026-09-03 against contracts/endpoints/db-stct-m1.yaml.
    The shape matches what a live GET returned on 2026-08-27 for a record the
    server populated itself -- see this module's payload docstring.
    """

    iLSTEP: int  # >= 1
    INTOUT: str  # "EVERY"/"LAST", default "LAST"
    ADVANCED: NonlinearAdvancedHyperSStct
    DISP: ConvergenceCriterionHyperSStct
    LOAD: ConvergenceCriterionHyperSStct
    WORK: ConvergenceCriterionHyperSStct


class ConstructionStageAnalysisControlDataHyperSPayload(TypedDict, total=False):
    """docs/manual/12_DB_Analysis_Control.md #18 — /db/STCT-M1 Specifications tables.

    2026-08-25 re-verification (article id `57053813627673`) added four
    top-level fields entirely missing before: `iBSC` (same Beam Section
    Property Option concept as legacy STCT's `iBSC`, but a **different
    default** -- STCT-M1 defaults to `1`, STCT defaults to `0`),
    `FRAME_OUTPUT`, `bSAVE_OCS`, and `NONL_CONTROL`. `NONL_CONTROL`'s own
    internal shape (`iLSTEP`/`INTOUT`/`ADVANCED`/`DISP`/`LOAD`/`WORK`) was
    left as `Any` until 2026-09-03 and is now `NonlinearControlHyperSStct`,
    matching contracts/endpoints/db-stct-m1.yaml; note its `ADVANCED`
    sub-object uses different key names/types than the similarly-named one
    under `NLCT-M1` (§16) despite the same underlying concept.

    **Live-confirmed 2026-08-27 on Civil NX**: all four fields are real.
    A plain `POST /db/STCT-M1` (no explicit values for any of them) came
    back on `GET` with `iBSC: 1` (confirming the different-from-legacy
    default), `FRAME_OUTPUT: {"bCALC_CFF": false, "bCALC_CSP": true,
    "bSELFCONS": false}`, `bSAVE_OCS: false`, and a fully-populated
    `NONL_CONTROL: {"iLSTEP": 1, "INTOUT": "EVERY", "ADVANCED":
    {"USE_DEF_SETTINGS": true}, "DISP": {"OPT_USE": false}, "LOAD":
    {"OPT_USE": true, "VALUE": 0.001}, "WORK": {"OPT_USE": true, "VALUE":
    1e-06}}` -- confirming `NONL_CONTROL`'s actual live shape too, for
    whoever next decides it's worth typing out instead of `Any`. Only
    server-assigned defaults were observed, not an explicit write of
    non-default values -- `PUT` on this endpoint turned out to reject
    even known-good field changes (`"Wrong Field"` on `ANAL_TYPE`
    specifically, reproduced with an already-documented value pair), so a
    write of a *non-default* value for these four fields specifically
    wasn't achieved this session.
    """

    bLAST_FINAL: bool  # optional
    FINAL_STAGE: str  # Final Stage Name; undocumented, declared by /info -- see MD-22
    ANAL_TYPE: ConstructionStageAnalysisTypeHyperS  # required
    RESTART_CS_ANAL: ConstructionStageRestartHyperS  # optional
    ERECTION_LOAD: List[ErectionLoadItem]  # optional
    bSDLE: bool  # Use Self-weight Dead Load for Erection, optional
    vSDLE: List[str]  # Self-weight Dead Load list, optional
    TIME_DEP_CONTROL: TimeDependentControlHyperS  # optional
    CABLE_CONTROL: CableControlHyperS  # optional
    INITIAL_CONTROL: InitialForceControlHyperS  # optional
    INITIAL_DISP: InitialDisplacementHyperS  # optional
    STRESS_DECREASE: StressDecreaseHyperS  # optional
    iBSC: int  # Beam Section Property Option: Constant=0/Change with Tendon=1, default 1 (NOT 0 -- differs from legacy STCT), optional
    FRAME_OUTPUT: FrameOutputHyperS  # optional
    bSAVE_OCS: bool  # Save Output of Current Stage (Beam/Truss), default false, optional
    NONL_CONTROL: NonlinearControlHyperSStct  # required if ANAL_TYPE.iINC_NLA != 0


class ConstructionStageAnalysisControlDataHyperS(DbResource):
    ENDPOINT = "/db/STCT-M1"
    NAME = "Construction Stage Analysis Control Data (Hyper-S)"
    PRODUCTS = HYPER_S_ONLY
    METHODS = GET_PUT_DELETE_METHODS


# --- 19. /db/BCCT — Boundary Change Assignment ------------------------------


class BoundaryGroupCombinationItem(TypedDict, total=False):
    BGCNAME: str  # Boundary Group Combination Name, required
    vBG: List[str]  # Boundary Group List, required


class LoadCaseAnalysisAssignmentItem(TypedDict, total=False):
    TYPE: str  # "ST"/"ULAT"/"THRSEV"/"THNS"/"PO"/"MV"/"SM", required
    BGCNAME: str  # Boundary Group Combination Name, required
    LCNAME: str  # Static Load Case, required


class BoundaryChangeAssignmentPayload(TypedDict, total=False):
    """docs/manual/12_DB_Analysis_Control.md #19 — /db/BCCT Specifications tables."""

    bSPT: bool  # Support, default false, optional
    bSPR: bool  # Point Spring Support, default false, optional
    bGSPR: bool  # General Spring Support, default false, optional
    bCGLINK: bool  # Change General Link Property, default false, optional
    bSSSF: bool  # Section Stiffness Scale Factor, default false, optional
    bPSSF: bool  # Plate Stiffness Scale Factor, default false, optional
    bRLS: bool  # Beam End Release, default false, optional
    bWSSF: bool  # Wall Stiffness Scale Factor (product-specific), default false, optional
    bESSF: bool  # Element Stiffness Scale Factor (product-specific), default false, optional
    bCDOF: bool  # Constrain DOF by boundary group combinations, default false, optional
    vBOUNDARY: List[BoundaryGroupCombinationItem]  # Boundary List, required
    vLOADANAL: List[LoadCaseAnalysisAssignmentItem]  # Load Cases & Analysis List, optional


class BoundaryChangeAssignment(DbResource):
    ENDPOINT = "/db/BCCT"
    NAME = "Boundary Change Assignment"


# --- 20. /db/BCGD-M1 — Define Boundary Combination (Hyper-S) ----------------


class DefineBoundaryCombinationHyperSPayload(TypedDict, total=False):
    """docs/manual/12_DB_Analysis_Control.md #20 — /db/BCGD-M1 Specifications table."""

    BCG_NAME: str  # Boundary Combination Name (1-20 chars, unique in model), required
    GROUP_LIST: List[str]  # Boundary Group List, required


class DefineBoundaryCombinationHyperS(DbResource):
    ENDPOINT = "/db/BCGD-M1"
    NAME = "Define Boundary Combination (Hyper-S)"
    PRODUCTS = HYPER_S_ONLY


# --- 21. /db/BCGA-M1 — Assign Boundary Combination (Hyper-S) ----------------


class BoundaryCombinationAssignItem(TypedDict, total=False):
    ANAL_TYPE: str  # "ST"/"MV"/"SM"/"EIGV"/"RS"/"LTH"/"NLTH"/"PO", required
    LCNAME: str  # required if ANAL_TYPE in {"ST", "NLTH", "PO"}
    BGCNAME: str  # Boundary Group Combination Name; "" = no change, default "", optional


class AssignBoundaryCombinationHyperSPayload(TypedDict, total=False):
    """docs/manual/12_DB_Analysis_Control.md #21 — /db/BCGA-M1 Specifications tables.

    ⚠️ Live-confirmed 2026-08-25 on Civil NX: the manual's own `BC_SELECT`
    enum table (below, for reference/traceability only) is entirely wrong
    — every value in it answers "Wrong Field". `GET /info/db/BCGA-M1`
    gives the server's real enum, listed on `BC_SELECT`'s own comment;
    use those instead. Cross-referencing meaning by position, the manual's
    table looks like an editing artifact from a *different*, longer
    abbreviation scheme (SECF/ESSF/EWSF/... vs the live SSSF/ES/EW/...)
    rather than a simple typo -- don't try to "fix the spelling" of the
    manual's values, they don't correspond 1:1 to the live ones.
    """

    BC_ASSIGN: List[BoundaryCombinationAssignItem]  # required
    # manual's documented (WRONG, live-rejected) enum values: "SECF"/"ESSF"/
    # "EWSF"/"PSSF"/"WSSF"/"CONS"/"NSPR"/"GSPR"/"SSPS"/"ELNK"/"RIGD"/"NLNK"/
    # "CGLP"/"FRLS"/"OFFS"/"PRLS"/"MCON" -- do not use these.
    # Live-confirmed real enum values (GET /info/db/BCGA-M1, 2026-08-25):
    # "SSSF" Section Stiffness Scale Factor / "ES" Element Stiffness Scale
    # Factor / "EW" Effective Width Scale Factor / "PS" Plate Stiffness
    # Scale Factor / "SP" Support / "PSS" Point Spring Support / "GSS"
    # General Spring Support / "SSS" Surface Spring Support / "EL" Elastic
    # Link / "RL" Rigid Link / "GL" General Link / "CGL" Change General
    # Link Property / "BER" Beam End Release / "BEO" Beam End Offset /
    # "PER" Plate End Release / "LC" Linear Constraints
    BC_SELECT: List[str]  # Apply to Boundary Change, required


class AssignBoundaryCombinationHyperS(DbResource):
    ENDPOINT = "/db/BCGA-M1"
    NAME = "Assign Boundary Combination (Hyper-S)"
    PRODUCTS = HYPER_S_ONLY
