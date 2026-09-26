"""Source: docs/manual/11_DB_Settlement_Misc_Loads.md, items 1-9."""
from __future__ import annotations

from typing import Any, List, TypedDict

from .base import CIVIL_ONLY, DbResource


class SettlementGroupPayload(TypedDict, total=False):
    """docs/manual/11_DB_Settlement_Misc_Loads.md #1 — /db/SMPT Specifications table."""

    NAME: str  # Settlement Group Name, required
    SETTLE: float  # Settlement Displacement, required
    ITEMS: List[int]  # Node List, required


class SettlementGroup(DbResource):
    ENDPOINT = "/db/SMPT"
    NAME = "Settlement Group"
    PRODUCTS = frozenset({"gen", "civil"})


class SettlementLoadCasePayload(TypedDict, total=False):
    """docs/manual/11_DB_Settlement_Misc_Loads.md #2 — /db/SMLC Specifications table."""

    NAME: str  # Settlement Load Case Name, required
    DESC: str  # required (documented as Required despite typically-optional description fields)
    FACTOR: float  # Settlement Scale Factor, required
    MIN: int  # Settlement - Min. Group Nos., required
    MAX: int  # Settlement - Max. Group Nos., required
    ST_GROUPS: List[str]  # Selected Settlement Group Names (/db/SMPT names), required


class SettlementLoadCase(DbResource):
    ENDPOINT = "/db/SMLC"
    NAME = "Settlement Load Cases"
    PRODUCTS = frozenset({"gen", "civil"})


class PreCompositeSectionPayload(TypedDict, total=False):
    """docs/manual/11_DB_Settlement_Misc_Loads.md #3 — /db/PLCB Specifications table.

    Single global record — Assign key is always "1".
    """

    LCNAME_ITEM: List[str]  # Static Load Case Names, required


class PreCompositeSection(DbResource):
    """⚠️ The manual documents this for both products, but three independent
    live sessions (2026-07-22, 2026-07-26, 2026-07-29) all 404 it under Gen
    NX while it answers under Civil NX. See docs/live_verification_notes.md.
    """

    ENDPOINT = "/db/PLCB"
    NAME = "Pre-composite Section"
    PRODUCTS = CIVIL_ONLY


class LoadSequenceNonlinearPayload(TypedDict, total=False):
    """docs/manual/11_DB_Settlement_Misc_Loads.md #4 — /db/LDSQ. Keyed by
    load sequence set number; LCNAME_ITEM's order is the applied load order.
    """

    LCNAME_ITEM: List[str]  # Load Case Names, in application order, required


class LoadSequenceNonlinear(DbResource):
    ENDPOINT = "/db/LDSQ"
    NAME = "Load Sequence for Nonlinear"
    PRODUCTS = frozenset({"gen", "civil"})


class WaveLoadGrowthItem(TypedDict, total=False):
    Z: float  # Elevation, optional
    T: float  # Thickness, optional


class WaveLoadPayload(TypedDict, total=False):
    """docs/manual/11_DB_Settlement_Misc_Loads.md #5 — /db/WVLD Specifications table.

    COEF (drag/inertia coefficients per structure group), CHAR (wave theory
    parameters), and PROF (current profile) are deeply nested sub-objects —
    left as Any for v1, matching the SECT_I precedent. USERGRID/TRAJ are
    similarly left loosely typed (2D arrays of 9-field grid points).

    2026-08-25 re-verification (article id `35988728179097`) corrected
    `CREST`/`UNIT`: the manual's own Specifications table lists neither
    field's literal values at all, so this SDK's prior `"MAX"`/`"MANUAL"`
    guess for CREST had no textual basis in either version of the manual.
    The only values confirmed anywhere (the manual's own Request Example)
    are `CREST="MXM"` and `UNIT="PHASE"`; corrected to those, flagged as
    example-confirmed rather than a documented exhaustive enum. Not
    independently live-tested: `/db/WVLD` is Civil-only and the Civil NX
    session was unavailable this session (`client does not exist`).
    `VERT_COORD`'s `"GLOBAL_X"` value is also flagged unconfirmed by the
    manual itself (no textual basis found either, kept since X/Y/Z is the
    structurally expected set) -- left as-is, not newly introduced here.
    """

    NAME: str  # Wave Load Name, required
    DESC: str  # optional
    bSTLD: bool  # Use Static Load Generation, default false, optional
    bTHIS: bool  # Use Time History Load Generation, default false, optional
    NAME_THIS: str  # Time History Load Case Name, optional
    VERT_COORD: str  # "GLOBAL_X"(unconfirmed)/"GLOBAL_Y"/"GLOBAL_Z", default "GLOBAL_Z", required
    DENSITY: float  # Water Weight Density, required
    DEPTH: float  # Water Depth, required
    bSELFW: bool  # Use Self Weight, default false, optional
    bBUOYANT: bool  # Use Buoyancy Load, default false, optional
    COEF: Any  # {"TYPE","COEF_S","COEF_R","bOVER","OVER_S","OVER_R"}
    CHAR: Any  # {"THEORY","FUNC","DIR","HEIGHT","CHAR_TYPE","LENGTH","PERIOD",...}
    PROF: Any  # {"CUR_DIR","CUR_FACTOR","GRID_DATA"}
    FLOOD_GRUP: List[str]  # Flood Condition (Structure Group Names), optional
    GROWTH: List[WaveLoadGrowthItem]  # Marine Growth Data, optional
    GRID_X: int  # Grid X Size, optional
    GRID_Z: int  # Grid Y Size (per the manual's own key/description naming, not a typo), optional
    USERGRID: Any  # 2D array of {"X","Z","ELEV","VX","VCX","VT","VZ","AX","AZ"}, optional
    TRAJ: Any  # Trajectory Grid Data, same shape as USERGRID, optional
    CREST: str  # Crest Critical Position, example-confirmed value "MXM"; other literals undocumented, optional
    UNIT: str  # Crest Position Unit, example-confirmed value "PHASE"; other literals undocumented, optional
    INITAL_POS: float  # Initial Position, optional
    STEP: float  # Increase Step, optional
    POS: int  # Number of Positions, optional


class WaveLoad(DbResource):
    """⚠️ The manual documents this for both products, but three independent
    live sessions (2026-07-22, 2026-07-26, 2026-07-29) all 404 it under Gen
    NX while it answers under Civil NX. See docs/live_verification_notes.md.
    """

    ENDPOINT = "/db/WVLD"
    NAME = "Wave Loads"
    PRODUCTS = CIVIL_ONLY


class IgnoreElementForLoadCasePayload(TypedDict, total=False):
    """docs/manual/11_DB_Settlement_Misc_Loads.md #6 — /db/IELC Specifications table.

    One (element, load case) combination per Assign entry.
    """

    ELEMENT: int  # Element ID, required
    LCNAME: str  # Load Case Name, required
    OPT_IGNORE: bool  # Ignore Option, required


class IgnoreElementForLoadCase(DbResource):
    ENDPOINT = "/db/IELC"
    NAME = "Ignore Elements for Load Cases"
    PRODUCTS = frozenset({"gen", "civil"})


class InitialForceGeometricStiffnessPayload(TypedDict, total=False):
    """docs/manual/11_DB_Settlement_Misc_Loads.md #7 — /db/IFGS. Keyed by element id."""

    DIR: str  # "GX"/"GY"/"GZ"/"AXIAL", required
    INIT_FORCE: float  # Initial Force, required


class InitialForceGeometricStiffness(DbResource):
    ENDPOINT = "/db/IFGS"
    NAME = "Large Displacement – Initial Forces for Geometric Stiffness"
    PRODUCTS = frozenset({"gen", "civil"})


class InitialForceCombinationItem(TypedDict, total=False):
    LCNAME: str  # Load Case Name, required
    FACTOR: float  # Scale Factor, required


class InitialForceControlDataPayload(TypedDict, total=False):
    """docs/manual/11_DB_Settlement_Misc_Loads.md #8 — /db/EFCT Specifications table."""

    bADDLC: bool  # Add Initial Force to Element Force, default false, optional
    LCNAME: str  # Load Case Name, required
    bUSECOMB: bool  # Use Initial Force Combination, default false, optional
    COMB_LIST: List[InitialForceCombinationItem]  # Initial Force Combination Cases, required
    bCHECK_GEOM_STIFF: bool  # Reflect Initial Axial Forces into Geometric Stiffness, default false, optional


class InitialForceControlData(DbResource):
    ENDPOINT = "/db/EFCT"
    NAME = "Small Displacement – Initial Force Control Data"
    PRODUCTS = frozenset({"gen", "civil"})


class InitialElementForcePayload(TypedDict, total=False):
    """docs/manual/11_DB_Settlement_Misc_Loads.md #9 — /db/INMF Specifications table.

    ELEMENT_FORCES size/order depends on ELEM_TYPE: "TRUSS"=2 values
    [Axial-i, Axial-j]; "BEAM"/"E-LINK"/"G-LINK"=12 values [Axial-i, Vy-i,
    Vz-i, Torsion-i, My-i, Mz-i, Axial-j, Vy-j, Vz-j, Torsion-j, My-j, Mz-j].
    """

    ELEM_TYPE: str  # "BEAM"/"TRUSS"/"E-LINK"/"G-LINK", required
    ELEM_KEY: int  # Element ID, required
    ELEMENT_FORCES: List[float]  # required


class InitialElementForce(DbResource):
    ENDPOINT = "/db/INMF"
    NAME = "Small Displacement – Initial Element Force"
    PRODUCTS = frozenset({"gen", "civil"})
