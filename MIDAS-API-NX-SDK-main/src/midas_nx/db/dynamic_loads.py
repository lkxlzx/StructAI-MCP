"""Source: docs/manual/09_DB_Dynamic_Loads.md, items 1-12.

Unlike most Hyper-S "-M1" variants elsewhere in the manual (documented as
thin stubs), THGC-M1/THOO-M1/THIS-M1 here have full Specifications tables —
implemented, with deeply-nested control sub-objects left as Any (matching
the SECT_I precedent) given their size. THGC-M1's are the exception as of
2026-09-03: contracts/endpoints/db-thgc-m1.yaml resolves all three of its
sub-parameter tables, so the types below spell them out rather than defer.
"""
from __future__ import annotations

from typing import Any, List, TypedDict

from .base import (
    GET_PUT_DELETE_METHODS,
    HYPER_S_ONLY,
    DbResource,
    InitialLoadCaseItem,
    TimeValuePoint,
)


class ResponseSpectrumFunctionValue(TypedDict, total=False):
    PERIOD: float  # Period (sec), required
    VALUE: float  # required


class ResponseSpectrumFunctionPayload(TypedDict, total=False):
    """docs/manual/09_DB_Dynamic_Loads.md #1 — /db/SPFC Specifications table.

    Deeply conditional on the design-code discriminator (User-defined vs.
    Korea/US/Eurocode/China/... code variants, each with its own extra
    keys) — only the common envelope + the User-defined "aFUNC" shape are
    typed for v1; code-specific extra keys go as extra dict keys.

    ⚠️ **A design-code function needs ``CALC_OPT: True``.** Measured live
    2026-09-03 on Gen NX. A code variant (``STR``/``OPT``/``VAL``) with no
    ``aFUNC`` and no ``CALC_OPT`` is refused with
    ``[Error] Spectrum Function Data (Name:...) contains errors.(Item:Spectrum
    Data)`` — including the manual's own KDS(41-17-00:2019) worked example,
    which is printed without it. ``CALC_OPT: True`` makes the server build the
    curve (103 points for that example) from the code parameters.

    Unlike ``/db/SECT``'s identically documented ``CALC_OPT``, this one is
    honoured on PUT too, despite the manual marking it ``Create Only``. That
    is the fix for the other half of the finding: changing ``VAL``/``OPT``
    without ``CALC_OPT: True`` stores new code parameters against the curve
    the old ones generated. See docs/live_verification_notes.md and MD-15.
    """

    NAME: str  # Response Spectrum Function Name, required
    iTYPE: int  # 1=Normalized Accel, 2=Accel, 3=Velocity, 4=Displacement; required
    iMETHOD: int  # 0=Scale Factor, 1=Max Value; default 0, optional
    SCALE: float  # Scale Value, required
    GRAV: float  # Gravitational Acceleration (iTYPE=1 only), required
    DRATIO: float  # Damping Ratio, default 0.05, optional
    DESC: str  # default "", optional
    aFUNC: List[ResponseSpectrumFunctionValue]  # User-defined function data, required for user-defined
    CALC_OPT: bool  # code variants: build aFUNC from STR/OPT/VAL; default false, and required True when no aFUNC is sent - see class docstring


class ResponseSpectrumFunction(DbResource):
    ENDPOINT = "/db/SPFC"
    NAME = "Response Spectrum Functions"
    PRODUCTS = frozenset({"gen", "civil"})


class ResponseSpectrumUseMode(TypedDict, total=False):
    bUSE: bool  # Mode use flag, optional
    MSFACTOR: float  # Mode shape factor, optional


class ResponseSpectrumLoadCasePayload(TypedDict, total=False):
    """docs/manual/09_DB_Dynamic_Loads.md #2 — /db/SPLC Specifications table."""

    NAME: str  # Load Case Name, required
    DESC: str  # default "", optional
    DIR: str  # "XY" / "Z", default "XY", optional
    ANGLE: float  # Excitation Angle, default 0, optional
    SCALE: float  # Scale Coefficient, required
    PMFT: float  # Period Modification Factor, required
    aFUNCNAME: List[str]  # Spectrum Function Name list (/db/SPFC names), required
    INTERP: str  # "LINEAR" / "LOG", default "LINEAR", optional
    COMTYPE: str  # "SRSS"/"CQC"/"ABS"/"Linear", default "CQC", optional
    bADDSIGN: bool  # Add Sign to Results, default false, optional
    iSIGNTYPE: int  # 0=Principal Mode, 1=Absolute Max; default 1, optional
    bMODE: bool  # Mode Shape Selection, optional
    aUSEMODE: List[ResponseSpectrumUseMode]  # optional
    bDAMP: bool  # Apply Damping Method, default false, optional
    bCDAMP: bool  # Damping Ratio Correction, default false, optional
    iMDTYPE: int  # 1=Modal, 2=M&S, 3=StrainEnergy; required if bDAMP=true


class ResponseSpectrumLoadCase(DbResource):
    ENDPOINT = "/db/SPLC"
    NAME = "Response Spectrum Load Cases"
    PRODUCTS = frozenset({"gen", "civil"})


class TimeHistoryInitialLoadItem(TypedDict, total=False):
    SLC: str  # Static Load Case Name, required
    SF: float  # Scale Factor, required
    LCT: int  # Load Case Type: Static=1, Construction=18; required


class TimeHistoryGlobalControlPayload(TypedDict, total=False):
    """docs/manual/09_DB_Dynamic_Loads.md #3 — /db/THGC Specifications table.

    Despite the manual's Civil-only framing, this answers on Gen NX too
    (route + /info both resolve, empty table) — live-checked 2026-07-29,
    left at the class default (gen+civil) rather than CIVIL_ONLY. See
    db/base.py's GEN_ONLY docstring's sibling note.
    """

    GNT: int  # Geometric Nonlinearity Type: None=0, Large Displacement=1, P-Delta=2; required
    ILT: int  # Initial Load Type: Nonlinear static=0, Static/construction stage import=1; default 0, required
    aILL: List[TimeHistoryInitialLoadItem]  # Initial Load List, default [], optional
    IEPI: bool  # Ignore NL Initial Load Element Option, default true, optional
    NSTEP: int  # Number of Increment Steps, default 1, optional
    bROT: bool  # Output Method: false=final step only, true=step increment; default false, optional
    SNIO: int  # Output Step Increment Count, default 1, optional
    bPCF: bool  # Allow Convergence Failure, default true, required
    MAXNS: int  # Maximum Number of Substeps, default 10, required
    MAXIT: int  # Maximum Iteration Count, default 10, required
    bDN: bool  # Use Displacement Norm, default true, optional
    bFN: bool  # Use Force Norm, default false, optional
    bEN: bool  # Use Energy Norm, default false, optional
    DN: float  # Displacement Norm Value, default 0.001, optional
    FN: float  # Force Norm Value, default 0, optional
    EN: float  # Energy Norm Value, default 0, optional
    bULSM: bool  # Apply Line Search Method, default false, optional
    ULSM: int  # Line Search Starting Iteration Count, default 5, optional
    ENERGYRESULT: bool  # Output Time-History Energy Results, default true, optional
    SDVI: bool  # Viscous/Oil Damper Results, default true, optional
    SDVE: bool  # Viscoelastic Damper Results, default true, optional
    SDST: bool  # Steel Damper Results, default true, optional
    SDHY: bool  # Hysteretic Isolation Device Results, default true, optional
    SDIS: bool  # Isolation Device Results, default true, optional
    bMSSSTATUS: bool  # Model Yield Status, default true, optional
    bCONV_WALL_STIFF: bool  # Convert plate-based wall stiffness scale factors
    # to CRB walls. Gen NX only; /info declares it and the manual documents it nowhere (checked across every chapter, 2026-09-04). MD-46.


class TimeHistoryGlobalControl(DbResource):
    ENDPOINT = "/db/THGC"
    NAME = "Time History Global Control"


class HyperSIncrementStep(TypedDict, total=False):
    """THGC-M1's "INCREMENT_STEP" sub-object."""

    NSTEP: int  # Number of Increment Steps, default 1, optional
    OUT_TYPE: int  # Final step only=0, Step increments=1; default 0, optional
    STEP_INC: int  # Step Increment (OUT_TYPE=1), required if OUT_TYPE=1


class HyperSNormCriterion(TypedDict, total=False):
    """One convergence norm inside THGC-M1's "ITER_PARAM"."NORM_CTRL"."""

    OPT_USE: bool  # Use this norm, required
    VALUE: float  # Convergence tolerance, required


class HyperSNormControl(TypedDict, total=False):
    """THGC-M1's "ITER_PARAM"."NORM_CTRL" sub-object.

    The manual's ITER_PARAM table states these three as paths — a row keyed
    ``DISP`` -> ``{OPT_USE, VALUE}`` rather than as keys of their own. The
    section's request example nests them literally, which is what settles it.
    """

    DISP: HyperSNormCriterion  # Displacement norm, optional
    FORCE: HyperSNormCriterion  # Force norm, optional
    ENERGY: HyperSNormCriterion  # Energy norm, optional


class HyperSLineSearch(TypedDict, total=False):
    """THGC-M1's "ITER_PARAM"."LINE_SEARCH" sub-object.

    The manual marks all five Required, while the same section's Python example
    sends ``{"OPT_USE": False}`` and omits the other four. Nobody has put either
    form to a running product — registered as MD-19 in
    docs/manual_defects_register.md. Sending all five is the documented form.
    """

    OPT_USE: bool  # Use line search, default true, required
    LINE_SEARCH_OPT: int  # Auto=0, User-defined=1; default 0, required
    START_ITER_NO: int  # Line-search starting iteration number, required
    MAX_LINE_SEARCH_ITER: int  # Maximum line-search iterations, required
    LINE_SEARCH_TOL: float  # Line-search tolerance, required


class HyperSIterationParameters(TypedDict, total=False):
    """THGC-M1's "ITER_PARAM" sub-object."""

    PERMIT_FAIL: bool  # Allow convergence failure, default true, optional
    MAX_ITER: int  # Maximum iteration count, required
    NORM_CTRL: HyperSNormControl  # Convergence criteria, optional
    STIFF_UPD_SCHEME: int  # Custom=0, FullNR=1, InitStiff=2; default 1, optional
    ITER_BEF_UPDATE: int  # Iterations before update, default 5, required if STIFF_UPD_SCHEME=0
    MAX_BISECT_LEVEL: int  # Maximum bisection level, default 5, optional
    SMART_BISECT: bool  # Smart bisection, default false, optional
    DIVERGENCE_THRESHOLD: float  # Divergence threshold, default 3, optional
    LINE_SEARCH: HyperSLineSearch  # Line-search options, optional


class HyperSHingeOption(TypedDict, total=False):
    """THGC-M1's "HINGE_OPT" sub-object.

    Both members are 0/1 enums deciding whether the nonlinear property is
    applied or the component is treated as linear — not the "P-spring support
    treatment"/"element data" this docstring claimed until 2026-09-03, which
    predated the manual's own 2026-08-25 correction of the same two rows.
    """

    PSPRING_SUP: int  # Point Spring Support: nonlinear=0, linear=1; default 0, optional
    EL: int  # Elastic Link: nonlinear=0, linear=1; default 1, optional


class TimeHistoryGlobalControlHyperSPayload(TypedDict, total=False):
    """docs/manual/09_DB_Dynamic_Loads.md #4 — /db/THGC-M1 Specifications table
    (Hyper-S), reconciled with contracts/endpoints/db-thgc-m1.yaml.

    INIT_LOAD_TYPE's second value is 1, not the 0 the manual prints for both of
    its two options — an enum cannot name one literal twice. Corrected against
    GET /info/db/THGC-M1 (Civil NX, 2026-09-03) and registered as MD-18.
    """

    GEO_NONL_TYPE: int  # None=0, Large Disp=1, P-Delta=2; required
    INIT_LOAD_TYPE: int  # Perform NL static=0, Import static/construction stage=1; required (MD-18)
    INIT_LOAD_LIST: List[InitialLoadCaseItem]  # optional
    INCREMENT_STEP: HyperSIncrementStep  # optional
    ITER_PARAM: HyperSIterationParameters  # required
    IGNORE_ELEM: bool  # Ignore NL Initial Load Elements, default false, optional
    SEQ_LOAD_TYPE: int  # Undeformed=0, Deformed=1; default 1, optional
    HINGE_OPT: HyperSHingeOption  # optional


class TimeHistoryGlobalControlHyperS(DbResource):
    ENDPOINT = "/db/THGC-M1"
    NAME = "Time History Global Control (Hyper-S)"
    PRODUCTS = HYPER_S_ONLY
    METHODS = GET_PUT_DELETE_METHODS


class HyperSOutputOption(TypedDict, total=False):
    """THOO-M1's "OUT_OPT" sub-object."""

    HINGE_OUT: int  # All elements=0, Selected elements=1, No output=2; required
    COMMON_OPT: bool  # true=FIBER_OUT matches HINGE_OUT, required
    FIBER_OUT: int  # All elements=0, Selected elements=1, No output=2; required if COMMON_OPT=false


class HyperSResultSelection(TypedDict, total=False):
    """THOO-M1's "RESULT_SELECTION" sub-object."""

    ENERGY_RESULT: bool  # default true, optional
    SDVI: bool  # Viscous/Oil Damper Results, default true, optional
    SDVE: bool  # Viscoelastic Damper Results, default true, optional
    SDST: bool  # Steel Damper Results, default true, optional
    SDHY: bool  # Hysteretic Isolator Results, default true, optional
    SDIS: bool  # Isolator Device Results, default true, optional


class TimeHistoryOutputOptionHyperSPayload(TypedDict, total=False):
    """docs/manual/09_DB_Dynamic_Loads.md #5 — /db/THOO-M1 Specifications table (Hyper-S)."""

    OUT_OPT: HyperSOutputOption  # required
    RESULT_SELECTION: HyperSResultSelection  # required


class TimeHistoryOutputOptionHyperS(DbResource):
    ENDPOINT = "/db/THOO-M1"
    NAME = "Time History Output Option (Hyper-S)"
    PRODUCTS = HYPER_S_ONLY
    METHODS = GET_PUT_DELETE_METHODS


class TimeHistoryLoadCaseCommon(TypedDict, total=False):
    """The /db/THIS "COMMON" sub-object."""

    NAME: str  # Load Case Name, required
    DESC: str  # default "", optional
    iATYPE: int  # Analysis Type: Linear=1, Nonlinear=2; required
    iAMETHOD: int  # Analysis Method: Modal=1, Direct=2, Static=3; required
    iTHTYPE: int  # Time History Type: Transient=1, Periodic=2; required
    ENDTIME: float  # End Time (sec), required
    INC: float  # Time Increment, required
    iOUT: int  # Output Step Increment, required
    INITMETHOD: str  # "INIT" / "ORDER", required
    iMDTYPE: int  # Damping Method: Modal=1, M&S=2, StrainEnergy=3; required


class TimeHistoryLoadCasePayload(TypedDict, total=False):
    """docs/manual/09_DB_Dynamic_Loads.md #6 — /db/THIS Specifications table.

    Deeply conditional on COMMON.iATYPE x COMMON.iAMETHOD (Linear/Nonlinear
    x Modal/Direct Integration/Static) — only the COMMON envelope is typed
    for v1; variant-specific keys (e.g. DALL for modal damping, iNMM for
    Newmark integration, bITER for nonlinear iteration) go as extra dict
    keys alongside COMMON.
    """

    COMMON: TimeHistoryLoadCaseCommon  # required


class TimeHistoryLoadCase(DbResource):
    ENDPOINT = "/db/THIS"
    NAME = "Time History Load Cases"
    PRODUCTS = frozenset({"gen", "civil"})


class HyperSAnalysisCase(TypedDict, total=False):
    """THIS-M1's "ANAL_CASE" sub-object.

    `ANAL_METHOD`'s 3rd value (`2`=Static) was missing from the manual's own
    Specifications table until its 2026-08-25 re-verification (article id
    `56538335819673`) -- added here to match. The manual also notes the
    Linear+Static (`ANAL_TYPE=0` + `ANAL_METHOD=2`) combination is rejected
    server-side. **Live-confirmed 2026-08-27 on Civil NX**: a full
    Static-mode `POST /db/THIS-M1` (`ANAL_TYPE=1`, `ANAL_METHOD=2`, plus
    `INC_STEP`/`INC_CTRL` -- see `TimeHistoryLoadCaseHyperSPayload`'s
    docstring for the full payload and what it revealed) round-tripped
    cleanly through `GET`.
    """

    ANAL_TYPE: int  # Linear=0, Nonlinear=1; required
    ANAL_METHOD: int  # Modal=0, Direct Integration=1, Static=2 (rejected if ANAL_TYPE=Linear); required
    TH_TYPE: int  # Transient=0, Periodic=1; required


class HyperSSubsequentLoad(TypedDict, total=False):
    """THIS-M1's "SUBSEQ" sub-object, used when INIT_METHOD="ORDER".

    Typed as of 2026-09-03 against contracts/endpoints/db-this-m1.yaml. Unlike
    this payload's other sub-objects it carries no branch: the manual states
    all four members in the common table, so narrowing it hides nothing.
    """

    OPT_USE: bool  # optional
    SUBSEQ_LOAD: int  # required
    LCTYPE: str  # required
    CASE: str  # required


class TimeHistoryLoadCaseHyperSPayload(TypedDict, total=False):
    """docs/manual/09_DB_Dynamic_Loads.md #7 — /db/THIS-M1 Specifications table
    (Hyper-S). DAMPING/NONL_CTRL_PARAM/INC_CTRL/TIME_PARAM stay Any, now for a
    sharper reason than size: contracts/endpoints/db-this-m1.yaml models each
    of them as variant-selected (DAMPING_METHOD, COEF_INPUT, ANAL_METHOD), and
    this TypedDict does not branch, so any single narrowed type would hide the
    members of the branches it does not describe. NONL_CTRL_PARAM has a second
    reason: its BOUNDARY_NL_ANAL child is documented with no parent path at all
    -- see MD-23. SUBSEQ was the one sub-object with no branch, and is typed.

    **`GEOM_NL_TYPE`/`INC_STEP`/`SUBSEQ`/`INC_CTRL`/`TIME_PARAM` added
    2026-08-27**, discovered live rather than from the manual text alone:
    verifying `ANAL_CASE.ANAL_METHOD=2` (Static, added to the manual
    2026-08-25) required constructing a full Static-mode payload from
    scratch (the manual has no worked JSON example for THIS-M1's Static
    case, unlike the legacy `/db/THIS`'s own -- don't confuse the two,
    their key conventions differ entirely, e.g. legacy uses
    `COMMON.iAMETHOD`/`iISTEP`). That payload (`ANAL_TYPE=1`,
    `ANAL_METHOD=2`, `INC_STEP=10`, `INC_CTRL={"INC_METHOD":0,"SF":1}`,
    no `ENDTIME`/`TIME_INC`/`DAMPING`) round-tripped cleanly on Civil NX
    -- confirming `ANAL_METHOD=2` itself, and that `ENDTIME`/`TIME_INC`/
    `DAMPING` are genuinely not required for the Static branch despite
    this class marking them required (they're required for
    Modal/Direct-Integration only; this TypedDict doesn't branch on
    `ANAL_METHOD` the way `PARAM`-style classes elsewhere in this SDK do
    for their own mode-dependent fields -- left as a known imprecision
    rather than restructured this pass). The server auto-filled a full
    `NONL_CTRL_PARAM` (including a nested `BOUNDARY_NL_ANAL`) on GET even
    though it wasn't sent, confirming that sub-object's shape too.
    """

    NAME: str  # required
    DESC: str  # optional
    ANAL_CASE: HyperSAnalysisCase  # required
    ENDTIME: float  # required for ANAL_METHOD=0/1 (Modal/Direct); not required for ANAL_METHOD=2 (Static) -- see class docstring
    TIME_INC: float  # required for ANAL_METHOD=0/1; not required for ANAL_METHOD=2 -- see class docstring
    OUTPUT_STEP: int  # required
    INC_STEP: int  # Increment Steps -- effectively required when ANAL_METHOD=2 (Static), default 1, optional. Live-confirmed 2026-08-27.
    GEOM_NL_TYPE: int  # Geometric Nonlinearity Type, default 0, optional (ANAL_TYPE=1 only). Live-confirmed 2026-08-27 (server default 0).
    INIT_METHOD: str  # "INIT" / "ORDER", required
    USE_INIT_LOAD: bool  # required
    SUBSEQ: HyperSSubsequentLoad  # required when INIT_METHOD="ORDER". Live-discovered 2026-08-27, not independently round-tripped.
    CUM_DVA: bool  # Cumulative Displacement/Velocity/Acceleration, optional
    KEEP_LOAD: bool  # Maintain final-step load state, optional
    KEEP_ACC: bool  # Maintain final-step acceleration, optional
    DAMPING: Any  # {"DAMPING_METHOD","ALL_DAMPING_RATIO","MODAL_DAMPING_RATIO"}, required for ANAL_METHOD=0/1; not required for ANAL_METHOD=2 -- see class docstring
    NONL_CTRL_PARAM: Any  # {"PERFORM_ITER","ITER_CTRL":{...,"BOUNDARY_NL_ANAL":{...}}}, required for ANAL_TYPE=1 (Nonlinear) -- and auto-filled by the server with real defaults even when omitted, per 2026-08-27 live evidence
    INC_CTRL: Any  # {"INC_METHOD","SF"} or {"INC_METHOD","DISP_CTRL":{...}}, ANAL_METHOD=2 (Static) only. Live-confirmed 2026-08-27.
    TIME_PARAM: Any  # {"METHOD","NEWMARK_METHOD","GAMMA","BETA"}, ANAL_METHOD=1 (Direct Integration) only. Manual-sourced, not independently tested.


class TimeHistoryLoadCaseHyperS(DbResource):
    ENDPOINT = "/db/THIS-M1"
    NAME = "Time History Load Cases (Hyper-S)"
    PRODUCTS = HYPER_S_ONLY


class TimeHistoryFunctionPayload(TypedDict, total=False):
    """docs/manual/09_DB_Dynamic_Loads.md #8 — /db/THFC Specifications table.

    FUNCTYPE=1 (Time Function) uses iMETHOD/SCALE/MAXVALUE/aFUNCDATA;
    FUNCTYPE=2 (Sinusoidal) uses CONS_A/CONS_C/FREQUENCY/DAMP_FACTOR/PHASE_ANGLE.
    """

    NAME: str  # required
    DESC: str  # default "", optional
    iTYPE: int  # 1=Normalized Accel, 2=Accel, 3=Force, 4=Moment, 5=Normal; required
    GRAV: float  # required
    FUNCTYPE: int  # 1=Time Function, 2=Sinusoidal; required
    # FUNCTYPE=1 only
    iMETHOD: int  # 0=Scale Factor, 1=Max Value; required
    SCALE: float  # required if iMETHOD=0
    MAXVALUE: float  # default 0, optional, used if iMETHOD=1
    aFUNCDATA: List[TimeValuePoint]  # required
    # FUNCTYPE=2 only
    CONS_A: float  # Constant A, required
    CONS_C: float  # Constant C, required
    FREQUENCY: float  # required
    DAMP_FACTOR: float  # required
    PHASE_ANGLE: float  # required


class TimeHistoryFunction(DbResource):
    ENDPOINT = "/db/THFC"
    NAME = "Time History Functions"
    PRODUCTS = frozenset({"gen", "civil"})


class GroundAccelerationPayload(TypedDict, total=False):
    """docs/manual/09_DB_Dynamic_Loads.md #9 — /db/THGA Specifications table."""

    NAME: str  # Time History Load Case Name, required
    ANGLE: float  # Horizontal Ground Acceleration Angle, default 0, optional
    FUNCX: str  # X-direction Function Name (/db/THFC name), required
    SCALEX: float  # required
    ATIMEX: float  # default 0, optional
    FUNCY: str  # required
    SCALEY: float  # required
    ATIMEY: float  # default 0, optional
    FUNCZ: str  # required
    SCALEZ: float  # required
    ATIMEZ: float  # default 0, optional


class GroundAcceleration(DbResource):
    ENDPOINT = "/db/THGA"
    NAME = "Ground Acceleration"
    PRODUCTS = frozenset({"gen", "civil"})


class DynamicNodalLoadItem(TypedDict, total=False):
    """One entry of the /db/THNL "ITEMS" array. No GROUP_NAME here (unlike
    most "ITEMS" entries) — the manual's fields are ID/THLCNAME/FUNC_NAME/
    DIR/ARRIVAL_TIME/SCALE_FACTOR only."""

    ID: int  # Serial Number, default 0, optional
    THLCNAME: str  # Time History Load Case Name, required
    FUNC_NAME: str  # Time History Function Name (Force/Moment types only), required
    DIR: str  # "X" / "Y" / "Z", required
    ARRIVAL_TIME: float  # required
    SCALE_FACTOR: float  # required


class DynamicNodalLoadPayload(TypedDict):
    """docs/manual/09_DB_Dynamic_Loads.md #10 — /db/THNL. Keyed by node id."""

    ITEMS: List[DynamicNodalLoadItem]


class DynamicNodalLoad(DbResource):
    ENDPOINT = "/db/THNL"
    NAME = "Dynamic Nodal Loads"
    PRODUCTS = frozenset({"gen", "civil"})


class TimeVaryingStaticLoadPayload(TypedDict, total=False):
    """docs/manual/09_DB_Dynamic_Loads.md #11 — /db/THSL Specifications table."""

    THIS_LCNAME: str  # Time History Load Case Name (/db/THIS name), required
    SLOAD: str  # Static Load Case Name (/db/STLD name), required
    THIS_FUNCNAME: str  # Time History Function Name (Normal type only), required
    ATIME: float  # Arrival Time, default 0, optional
    SCALE: float  # required


class TimeVaryingStaticLoad(DbResource):
    ENDPOINT = "/db/THSL"
    NAME = "Time Varying Static Loads"
    PRODUCTS = frozenset({"gen", "civil"})


class MultipleSupportExcitationItem(TypedDict, total=False):
    """One entry of the /db/THMS "ITEMS" array. No GROUP_NAME here (unlike
    most "ITEMS" entries) — the manual's fields are ID/LCNAME/ANGLE/FUNCX...
    /ATIMEZ only."""

    ID: int  # Serial Number, default 0, optional
    LCNAME: str  # Time History Load Case Name, required
    ANGLE: float  # Horizontal Ground Acceleration Angle, default 0, optional
    FUNCX: str  # X-direction Function Name (NormAccel/Acceleration types only), required
    SCALEX: float  # required
    ATIMEX: float  # default 0, optional
    FUNCY: str  # optional
    SCALEY: float  # optional
    ATIMEY: float  # default 0, optional
    FUNCZ: str  # optional
    SCALEZ: float  # optional
    ATIMEZ: float  # default 0, optional


class MultipleSupportExcitationPayload(TypedDict):
    """docs/manual/09_DB_Dynamic_Loads.md #12 — /db/THMS. Keyed by node/group id."""

    ITEMS: List[MultipleSupportExcitationItem]


class MultipleSupportExcitation(DbResource):
    ENDPOINT = "/db/THMS"
    NAME = "Multiple Support Excitation"
    PRODUCTS = frozenset({"gen", "civil"})
