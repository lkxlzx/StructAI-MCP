"""Source: docs/manual/10_DB_Construction_Stage.md, items 1-14."""
from __future__ import annotations

from typing import Any, List, TypedDict

from .base import CIVIL_ONLY, DbResource, ItemGroupFields, TimeValuePoint


class LoadGroupDayItem(TypedDict, total=False):
    """Shared shape of /db/STAG and /db/HSTG's ACT_LOAD/DACT_LOAD entries."""

    LOAD_NAME: str  # Load Group Name, required
    DAY: str  # "FIRST" / "LAST" / numeric string, default "FIRST", optional


class ActivateElementItem(TypedDict, total=False):
    GRUP_NAME: str  # Structure Group Name to activate, required
    AGE: float  # Material Age (days), default 0, optional


class DeactivateElementItem(TypedDict, total=False):
    GRUP_NAME: str  # Structure Group Name to deactivate, required
    REDIST: float  # Element Force Redistribution (%), default 0, optional


class ActivateBoundaryGroupItem(TypedDict, total=False):
    BNGR_NAME: str  # Boundary Group Name to activate, required
    POS: str  # Support/Spring Position: "DEFORMED" / "ORIGINAL", required


class ConstructionStagePayload(TypedDict, total=False):
    """docs/manual/10_DB_Construction_Stage.md #1 — /db/STAG Specifications table."""

    NAME: str  # Stage Name, required
    NO: int  # Construction Stage No. (sequence order), optional. Confirmed live 2026-07-30 (real cable-stayed bridge model) and in /info/db/STAG — not in the manual's own Specifications table.
    DURATION: float  # Duration (days), required
    bSV_RSLT: bool  # Save Results per Stage, default false, optional
    bSV_STEP: bool  # Save Additional Steps, default false, optional
    bLOAD_STEP: bool  # Use Load Increment Steps for Material Nonlinearity, default false, optional
    INCRE_STEP: int  # Number of Load Increment Steps (bLOAD_STEP=true), required
    ADD_STEP: List[float]  # Additional Step List, default [], optional
    ACT_ELEM: List[ActivateElementItem]  # Activate Structural Groups, default [], optional
    DACT_ELEM: List[DeactivateElementItem]  # Deactivate Structural Groups, default [], optional
    ACT_BNGR: List[ActivateBoundaryGroupItem]  # Activate Boundary Groups, default [], optional
    DACT_BNGR: List[str]  # Deactivate Boundary Groups (names), default [], optional
    ACT_LOAD: List[LoadGroupDayItem]  # Activate Load Groups, default [], optional
    DACT_LOAD: List[LoadGroupDayItem]  # Deactivate Load Groups, default [], optional


class ConstructionStage(DbResource):
    ENDPOINT = "/db/STAG"
    NAME = "Define Construction Stage"
    PRODUCTS = frozenset({"gen", "civil"})


class CompositeSectionPartInfo(TypedDict, total=False):
    PART: int  # Composite Section Part Number, required
    MTYPE: str  # Material Type: "ELEM" / "MATL", required
    MAT: str  # Material ID (MATL: number as string, ELEM: blank), optional
    CSTAGE: str  # Composite Stage (active stage: blank, target stage: stage name), default "", optional
    AGE: float  # Material Age (days), default 0, optional
    PARTINFO_H: Any  # Nominal Member Dimension (h): a number, or the sentinel "AUTO"; default "AUTO", optional
    PARTINFO_VS: float  # Volume/Surface Ratio (v/s), default 0, optional
    PARTINFO_M: float  # Exposed Surface Modulus (M), default 0, optional
    AREA: float  # Area stiffness scale factor, default 1, optional
    ASY: float  # Effective shear area (y-axis) scale factor, default 1, optional
    ASZ: float  # Effective shear area (z-axis) scale factor, default 1, optional
    IXX: float  # Torsional resistance stiffness scale factor, default 1, optional
    IYY: float  # Moment of inertia (y-axis) scale factor, default 1, optional
    IZZ: float  # Moment of inertia (z-axis) scale factor, default 1, optional
    WAREA: float  # Self-weight stiffness scale factor, default 1, optional
    IW: float  # Warping constant stiffness scale factor, default 1, optional


class CompositeSectionConstructionStagePayload(TypedDict, total=False):
    """docs/manual/10_DB_Construction_Stage.md #2 — /db/CSCS Specifications table.

    2026-08-25 re-verification (article id `35987625234201`) added two
    fields the manual's own Specifications table omitted: `WAREA` (self-
    weight stiffness scale factor -- the table jumps straight from IZZ to
    IW, but the JSON Schema and every Request Example show `WAREA` between
    them) and `OPT_UPDATE_ALL_H` (schema-only, never appears in the manual's
    own worked examples either -- kept Optional/untyped-default per the
    manual's own caveat). Additive-only; not independently live-tested (a
    round trip needs a pre-existing `/db/SECT` section and `/db/STAG` stage
    name, not set up this session).
    """

    SEC: int  # Section ID (/db/SECT id), required
    ASTAGE: str  # Active Stage Name, required
    TYPE: str  # Composite Type: "GENERAL" / "USER", required
    bTAP: bool  # Tapered Type, default false, optional
    vPARTINFO: List[CompositeSectionPartInfo]  # Part Info List, required
    OPT_UPDATE_ALL_H: bool  # Auto-calculate nominal dimension (h), schema-only (no manual worked example), optional


class CompositeSectionConstructionStage(DbResource):
    ENDPOINT = "/db/CSCS"
    NAME = "Composite Section for Construction Stage"
    PRODUCTS = frozenset({"gen", "civil"})


class TimeLoadItem(ItemGroupFields, total=False):
    """One entry of the /db/TMLD "ITEMS" array."""

    DAY: float  # Time Load (days), required


class TimeLoadConstructionStagePayload(TypedDict):
    """docs/manual/10_DB_Construction_Stage.md #3 — /db/TMLD. Keyed by construction stage id."""

    ITEMS: List[TimeLoadItem]


class TimeLoadConstructionStage(DbResource):
    ENDPOINT = "/db/TMLD"
    NAME = "Time Loads for Construction Stage"
    PRODUCTS = frozenset({"gen", "civil"})


class SetBackLoadPayload(TypedDict, total=False):
    """docs/manual/10_DB_Construction_Stage.md #4 — /db/STBK Specifications table."""

    NODE1: int  # required
    NODE2: int  # required
    DX: float  # default 0, optional
    DY: float  # default 0, optional
    DZ: float  # default 0, optional
    LCNAME: str  # Load Case Name, required
    GROUP_NAME: str  # Load Group Name, default "", optional


class SetBackLoad(DbResource):
    ENDPOINT = "/db/STBK"
    NAME = "Set-Back Loads for Nonlinear Construction Stage"
    PRODUCTS = frozenset({"gen", "civil"})


class CamberConstructionStagePayload(TypedDict, total=False):
    """docs/manual/10_DB_Construction_Stage.md #5 — /db/CMCS. Keyed by node id."""

    DEFORM: float  # Deformation Camber, required
    USER: float  # User-defined Camber, required


class CamberConstructionStage(DbResource):
    """⚠️ The manual documents this for both products, but three independent
    live sessions (2026-07-22, 2026-07-26, 2026-07-29) all 404 it under Gen
    NX while it answers under Civil NX — the third one a POST, not just a
    GET. See docs/live_verification_notes.md.
    """

    ENDPOINT = "/db/CMCS"
    NAME = "Camber for Construction Stage"
    PRODUCTS = CIVIL_ONLY


class CreepCoefficientItem(ItemGroupFields, total=False):
    """One entry of the /db/CRPC "ITEMS" array."""

    CREEP: float  # Creep Coefficient, required


class CreepCoefficientConstructionStagePayload(TypedDict):
    """docs/manual/10_DB_Construction_Stage.md #6 — /db/CRPC. Keyed by construction stage id."""

    ITEMS: List[CreepCoefficientItem]


class CreepCoefficientConstructionStage(DbResource):
    ENDPOINT = "/db/CRPC"
    NAME = "Creep Coefficient for Construction Stage"
    PRODUCTS = frozenset({"gen", "civil"})


class AmbientTemperatureFunctionPayload(TypedDict, total=False):
    """docs/manual/10_DB_Construction_Stage.md #7 — /db/ETFC Specifications table.

    TYPE="CONST" uses TEMP; TYPE="SINE" uses MAX_TEMP/MEAN_TEMP/DELAY_TIME;
    TYPE="USER" uses SCALE_FACTOR/ITEM.
    """

    NAME: str  # Function Name, required
    TYPE: str  # "CONST" / "SINE" / "USER", required
    TEMP: float  # TYPE=CONST, default 0, optional
    MAX_TEMP: float  # TYPE=SINE: Max Temperature (T), default 0, optional
    MEAN_TEMP: float  # TYPE=SINE: Mean Temperature (To), default 0, optional
    DELAY_TIME: float  # TYPE=SINE: Delay Time (to), default 0, optional
    SCALE_FACTOR: float  # TYPE=USER, required
    ITEM: List[TimeValuePoint]  # TYPE=USER, required


class AmbientTemperatureFunction(DbResource):
    ENDPOINT = "/db/ETFC"
    NAME = "Ambient Temperature Functions"
    PRODUCTS = frozenset({"gen", "civil"})


class ConvectionCoefficientFunctionPayload(TypedDict, total=False):
    """docs/manual/10_DB_Construction_Stage.md #8 — /db/CCFC Specifications table.

    TYPE="CONST" uses COEF; TYPE="USER" uses SCALE_FACTOR/ITEM.
    """

    NAME: str  # Function Name, required
    TYPE: str  # "CONST" / "USER", required
    COEF: float  # TYPE=CONST: Convection Coefficient, required
    SCALE_FACTOR: float  # TYPE=USER, required
    ITEM: List[TimeValuePoint]  # TYPE=USER, required


class ConvectionCoefficientFunction(DbResource):
    ENDPOINT = "/db/CCFC"
    NAME = "Convection Coefficient Functions"
    PRODUCTS = frozenset({"gen", "civil"})


class ElementConvectionBoundaryItem(ItemGroupFields, total=False):
    """One entry of the /db/HECB "ITEMS" array."""

    FACE_NO: int  # Face Number (Face#1-6), required
    CCFC_NAME: str  # Convection Coefficient Function Name (/db/CCFC name), required
    ETFC_NAME: str  # Ambient Temperature Function Name (/db/ETFC name), required


class ElementConvectionBoundaryPayload(TypedDict):
    """docs/manual/10_DB_Construction_Stage.md #9 — /db/HECB. Keyed by construction stage id."""

    ITEMS: List[ElementConvectionBoundaryItem]


class ElementConvectionBoundary(DbResource):
    ENDPOINT = "/db/HECB"
    NAME = "Element Convection Boundary"
    PRODUCTS = frozenset({"gen", "civil"})


class PrescribedTemperatureItem(ItemGroupFields, total=False):
    """One entry of the /db/HSPT "ITEMS" array."""

    TEMPER: float  # Temperature, required


class PrescribedTemperaturePayload(TypedDict):
    """docs/manual/10_DB_Construction_Stage.md #10 — /db/HSPT. Keyed by construction stage id."""

    ITEMS: List[PrescribedTemperatureItem]


class PrescribedTemperature(DbResource):
    ENDPOINT = "/db/HSPT"
    NAME = "Prescribed Temperature"
    PRODUCTS = frozenset({"gen", "civil"})


class HeatSourceFunctionPayload(TypedDict, total=False):
    """docs/manual/10_DB_Construction_Stage.md #11 — /db/HSFC Specifications table.

    TYPE="CONST" uses TEMP_CONST; TYPE="FUNC" uses OPT_USE_CONC_DATA plus
    either K/ALPHA (false) or CEMENT_TYPE/TEMP_FUNC/CEMENT_CONT (true);
    TYPE="USER" uses IS_ADIABATIC_TEMP/SCALE_FACTOR/ITEM.
    """

    NAME: str  # Function Name, required
    TYPE: str  # "CONST" / "FUNC" / "USER", required
    TEMP_CONST: float  # TYPE=CONST: Heat Source Temperature, default 0, optional
    OPT_USE_CONC_DATA: bool  # TYPE=FUNC, default false, optional
    K: float  # TYPE=FUNC, OPT_USE_CONC_DATA=false: Max Adiabatic Temp Rise (K), default 0, optional
    ALPHA: float  # TYPE=FUNC, OPT_USE_CONC_DATA=false: Reaction Rate Coefficient, default 0, optional
    CEMENT_TYPE: int  # TYPE=FUNC, OPT_USE_CONC_DATA=true: 0=Normal,1=Moderate Heat,2=High Early,3=Blast Furnace,4=Fly Ash; default 0, optional
    TEMP_FUNC: int  # TYPE=FUNC, OPT_USE_CONC_DATA=true: 0=10C,1=20C,2=30C; default 0, optional
    CEMENT_CONT: float  # TYPE=FUNC, OPT_USE_CONC_DATA=true: Cement Content, default 0, optional
    IS_ADIABATIC_TEMP: bool  # TYPE=USER: false=Heat Source, true=Temperature; default true, optional
    SCALE_FACTOR: float  # TYPE=USER, required
    ITEM: List[TimeValuePoint]  # TYPE=USER, required


class HeatSourceFunction(DbResource):
    ENDPOINT = "/db/HSFC"
    NAME = "Heat Source Functions"
    PRODUCTS = frozenset({"gen", "civil"})


class AssignHeatSourcePayload(TypedDict, total=False):
    """docs/manual/10_DB_Construction_Stage.md #12 — /db/HAHS. Keyed by element id."""

    FUNC_NAME: str  # Heat Source Function Name (/db/HSFC name), required


class AssignHeatSource(DbResource):
    ENDPOINT = "/db/HAHS"
    NAME = "Assign Heat Source"
    PRODUCTS = frozenset({"gen", "civil"})


class PipeCoolingPayload(TypedDict, total=False):
    """docs/manual/10_DB_Construction_Stage.md #13 — /db/HPCE Specifications table."""

    NAME: str  # Pipe Cooling System Name, required
    DIAMETER: float  # Pipe Diameter, default 0, optional
    COEF: float  # Convection Coefficient, default 0, optional
    HEAT: float  # Specific Heat, default 0, optional
    DENSITY: float  # Unit Weight Density, default 0, optional
    TEMPER: float  # Inlet Temperature, default 0, optional
    FLOW_RATE: float  # Flow Rate, default 0, optional
    START_TIME: int  # Inflow Start Time, default 0, optional
    END_TIME: int  # Inflow End Time, default 0, optional
    ITEMS: List[int]  # Node List, required
    START_STAGE: str  # Start Stage; /info declares it and the manual documents it nowhere (checked across every chapter, 2026-09-04)
    END_STAGE: str  # End Stage; same. Both were found via /info on 2026-08-17
    # while root-causing this endpoint's still-open live write failure, and
    # sending them empty and omitting them both left the error unchanged.


class PipeCooling(DbResource):
    ENDPOINT = "/db/HPCE"
    NAME = "Pipe Cooling"
    PRODUCTS = frozenset({"gen", "civil"})


class ConstructionStageForHydrationPayload(TypedDict, total=False):
    """docs/manual/10_DB_Construction_Stage.md #14 — /db/HSTG Specifications table."""

    NAME: str  # Hydration Stage Name, required
    bINITAL_TEMP: bool  # Use Initial Temperature, default false, optional
    INITIAL_TEMP: float  # Initial Temperature Value, optional
    ADD_STEP: List[float]  # Additional Steps List, required
    ACT_ELEM: List[str]  # Active Structural Groups (names), required
    ACT_BNGR: List[str]  # Active Boundary Groups (names), required
    DACT_BNGR: List[str]  # Inactive Boundary Groups (names), required
    ACT_LOAD: List[LoadGroupDayItem]  # Active Load Groups, default [], optional
    DACT_LOAD: List[LoadGroupDayItem]  # Inactive Load Groups, default [], optional


class ConstructionStageForHydration(DbResource):
    ENDPOINT = "/db/HSTG"
    NAME = "Define Construction Stage for Hydration"
    PRODUCTS = frozenset({"gen", "civil"})
