"""Source: docs/manual/07_DB_Temperature_Prestress.md, items 1-12."""
from __future__ import annotations

from typing import Any, List, TypedDict

from .base import DbResource, ItemGroupFields


class ElementTemperatureItem(ItemGroupFields, total=False):
    """One entry of the /db/ETMP "ITEMS" array."""

    LCNAME: str  # Load Case Name, required
    TEMP: float  # Temperature, required


class ElementTemperaturePayload(TypedDict):
    """docs/manual/07_DB_Temperature_Prestress.md #1 — /db/ETMP. Keyed by element id."""

    ITEMS: List[ElementTemperatureItem]


class ElementTemperature(DbResource):
    ENDPOINT = "/db/ETMP"
    NAME = "Element Temperature"
    PRODUCTS = frozenset({"gen", "civil"})


class TemperatureGradientItem(ItemGroupFields, total=False):
    """One entry of the /db/GTMP "ITEMS" array.

    TY/USE_HY/HY apply to TYPE=1 (Beam) only; TYPE=2 (Plate) only uses
    TZ/USE_HZ/HZ.
    """

    LCNAME: str  # Load Case Name, required
    TYPE: int  # Element Type: Beam=1, Plate=2; required
    TZ: float  # T2z - T1z, required
    USE_HZ: bool  # Use Section Hz, default false, optional
    HZ: float  # Hz value, used when USE_HZ=false, optional
    TY: float  # T2y - T1y (Beam only), required for Beam
    USE_HY: bool  # Use Section Hy (Beam only), default false, optional
    HY: float  # Hy value, used when USE_HY=false (Beam only), optional


class TemperatureGradientPayload(TypedDict):
    """docs/manual/07_DB_Temperature_Prestress.md #2 — /db/GTMP. Keyed by element id."""

    ITEMS: List[TemperatureGradientItem]


class TemperatureGradient(DbResource):
    ENDPOINT = "/db/GTMP"
    NAME = "Temperature Gradient"
    PRODUCTS = frozenset({"gen", "civil"})


class BeamSectionTemperatureItem(ItemGroupFields, total=False):
    """One entry of the /db/BTMP "ITEMS" array.

    vSECTTMP's shape is deeply conditional on this item's bPSC (General vs
    PSC/Composite) and each vSECTTMP entry's own TYPE ("ELEMENT"/"INPUT") —
    left as Any for v1, matching the SECT_I precedent.
    """

    LCNAME: str  # Load Case Name, required
    DIR: str  # "LY" / "LZ", default "LZ", optional
    REF: str  # "Centroid" / "Top" / "Bot", default "Centroid", optional
    NUM: int  # Number of Section Temperature (vSECTTMP item count), required
    bPSC: bool  # General=false, PSC/Composite=true; default false, optional
    vSECTTMP: List[Any]  # Section Temperature List, required


class BeamSectionTemperaturePayload(TypedDict):
    """docs/manual/07_DB_Temperature_Prestress.md #3 — /db/BTMP. Keyed by element id."""

    ITEMS: List[BeamSectionTemperatureItem]


class BeamSectionTemperature(DbResource):
    ENDPOINT = "/db/BTMP"
    NAME = "Beam Section Temperature"
    PRODUCTS = frozenset({"gen", "civil"})


class SystemTemperaturePayload(TypedDict, total=False):
    """docs/manual/07_DB_Temperature_Prestress.md #4 — /db/STMP Specifications table."""

    LCNAME: str  # Load Case Name, required
    GROUP_NAME: str  # Load Group Name, default "", optional
    TEMPER: float  # System Temperature, default 0, optional


class SystemTemperature(DbResource):
    ENDPOINT = "/db/STMP"
    NAME = "System Temperature"
    PRODUCTS = frozenset({"gen", "civil"})


class NodalTemperatureItem(ItemGroupFields, total=False):
    """One entry of the /db/NTMP "ITEMS" array."""

    LCNAME: str  # Load Case Name, required
    TEMPER: float  # Temperature, required


class NodalTemperaturePayload(TypedDict):
    """docs/manual/07_DB_Temperature_Prestress.md #5 — /db/NTMP. Keyed by node id."""

    ITEMS: List[NodalTemperatureItem]


class NodalTemperature(DbResource):
    ENDPOINT = "/db/NTMP"
    NAME = "Nodal Temperature"
    PRODUCTS = frozenset({"gen", "civil"})


class TendonPropertyPayload(TypedDict, total=False):
    """docs/manual/07_DB_Temperature_Prestress.md #6 — /db/TDNT Specifications table.

    Relaxation-related fields (RM/RV, WF/W_TYPE/W_ANGLE, TDMFK, FT/LR/bOSRF/
    FPK, TDMFNAME) are conditional on the project's relaxation code — the
    manual documents ~6 mutually-exclusive code variants; all are flattened
    here as optional (flat scalar fields, matching the MaterialParam
    precedent) rather than left as Any (which is reserved for nested-object
    conditional shapes).
    """

    NAME: str  # Tendon Name, required
    TYPE: str  # "INTERNAL" / "EXTERNAL", default "EXTERNAL", optional
    LT: str  # Tensioning Type: "POST" / "PRE" (unused for EXTERNAL), default "PRE", optional
    MATL: int  # Tendon Material No., required
    AREA: float  # Total Tendon Area, required
    D_AREA: float  # Diameter (Post: Duct, Pre: Strand; unused for EXTERNAL), required
    ASB: float  # Anchorage Slip - Begin (Post/External only), default 0, optional
    ASE: float  # Anchorage Slip - End (Post/External only), default 0, optional
    bBONDED: bool  # Bond Type (Post only), default false, optional
    ALPHA: float  # External Cable Moment Magnifier (External only), default 0, optional
    RM: int  # Relaxation Coefficient - Code, required
    RV: int  # Relaxation Coefficient - Factor, required
    US: float  # Ultimate Strength, default 0, optional
    YS: float  # Yield Strength, default 0, optional
    FF: float  # Curvature Friction Factor (Post/External only), default 0, optional
    WF: float  # Wobble Friction Factor, default 0, optional
    W_TYPE: int  # Wobble Type (CEB-FIP/European codes): Fraction=0, Unintentional Angular=1; default 0, optional
    W_ANGLE: float  # Unintentional Angular Disp. (W_TYPE=1), default 0, optional
    TDMFK: int  # Relaxation Coefficient Class (CEB-FIP 2010 only), default 1, optional
    FT: float  # Relaxation Factor xi (TB05/TB10092/Q-CR/AS/JTJ/JTG codes), required for those codes
    LR: bool  # Low Relaxation (TB05/TB10092/Q-CR codes), default false, optional
    bOSRF: bool  # Apply Overstress Reduction Factor (TB05/TB10092/Q-CR/JTG codes), default false, optional
    FPK: float  # Characteristic Strength fpk (TB05/TB10092/Q-CR/JTJ/JTG codes), required for those codes
    bRELAX: bool  # Relaxation Coefficient - Check Box, optional. Confirmed live 2026-07-30 (real PSC bridge model) — missing from the manual's own Specifications table.
    TDMFNAME: str  # Relaxation Function Name (User Defined), required for that mode


class TendonProperty(DbResource):
    ENDPOINT = "/db/TDNT"
    NAME = "Tendon Property"
    PRODUCTS = frozenset({"gen", "civil"})


class TendonProfilePayload(TypedDict, total=False):
    """docs/manual/07_DB_Temperature_Prestress.md #7 — /db/TDNA Specifications table.

    Deeply conditional on SHAPE ("ELEMENT"/"STRAIGHT"/"CURVE", each with its
    own extra keys) and INPUT ("2D" -> PROFY/PROFZ, "3D" -> PROF) — only the
    common envelope is typed for v1; shape/profile-specific keys are left as
    Any, matching the SECT_I precedent.
    """

    NAME: str  # Tendon Name, required
    TDN_GRUP: int  # Tendon Group No. (/db/TDGR id), default 0, optional
    TDN_PROP: int  # Tendon Property No. (/db/TDNT id), required
    ELEM: List[int]  # Assigned Elements No., required
    INPUT: str  # "2D" / "3D", required
    CURVE: str  # "SPLINE" / "ROUND", required
    BELENG: float  # Straight Length - Begin (Spline only), default 0, optional
    ELENG: float  # Straight Length - End (Spline only), default 0, optional
    bTP: bool  # Typical Tendon, default false, optional
    CNT: float  # No. of Tendons (bTP=true), optional
    LENG_OPT: str  # Transfer Length Option: "USER"/"AUTO1"/"AUTO2", required
    BLEN: float  # Transfer Length - Begin, default 0, optional
    ELEN: float  # Transfer Length - End, default 0, optional
    DeBondBLEN: float  # Debonded Length - Begin (Pre-tensioning only), default 0, optional
    DeBondELEN: float  # Debonded Length - End (Pre-tensioning only), default 0, optional
    SHAPE: str  # Reference Axis: "ELEMENT" / "STRAIGHT" / "CURVE", required
    # SHAPE-specific extra keys (INS_PT/INS_ELEM/AXIS_IJ/IP/AXIS/VEC/RC/OFFSET/DIR/
    # XAR_ANGLE/bPJ/OFF_YZ/GR_AXIS/GR_ANGLE) and profile coordinates
    # (PROFY/PROFZ for INPUT=2D, PROF for INPUT=3D) — pass as extra dict keys.


class TendonProfile(DbResource):
    ENDPOINT = "/db/TDNA"
    NAME = "Tendon Profile"
    PRODUCTS = frozenset({"gen", "civil"})


class TendonLocationCompositeSectionPayload(TypedDict, total=False):
    """docs/manual/07_DB_Temperature_Prestress.md #8 — /db/TDCS Specifications table."""

    TDNA: int  # Tendon Profile No. (/db/TDNA id), required
    CSCS: int  # Composite Section for Construction Stage No. (/db/CSCS id), required
    PART_NUM: int  # Part Number, required


class TendonLocationCompositeSection(DbResource):
    ENDPOINT = "/db/TDCS"
    NAME = "Tendon Location for Composite Section"
    PRODUCTS = frozenset({"gen", "civil"})


class TendonPrestressItem(ItemGroupFields, total=False):
    """One entry of the /db/TDPL "ITEMS" array."""

    LCNAME: str  # Load Case Name, required
    GROUP_NAME: str  # Boundary Group Name, optional. Confirmed live 2026-07-30 (real PSC bridge model) — missing from the manual's own Specifications table; server's own /info/db/TDPL confirms it.
    TENDON_NAME: str  # Tendon Profile Name (/db/TDNA name), required
    TYPE: str  # Prestress Load Type: "STRESS" / "FORCE", default "STRESS", optional
    ORDER: str  # Jacking Step: "BEGIN" / "END" / "BOTH", default "BEGIN", optional
    BEGIN: float  # Jacking Force/Stress at Begin, required
    END: float  # Jacking Force/Stress at End, required
    GROUTING: int  # Grouting Stage, default 0, optional


class TendonPrestressPayload(TypedDict):
    """docs/manual/07_DB_Temperature_Prestress.md #9 — /db/TDPL. Keyed by tendon profile id."""

    ITEMS: List[TendonPrestressItem]


class TendonPrestress(DbResource):
    ENDPOINT = "/db/TDPL"
    NAME = "Tendon Prestress"
    PRODUCTS = frozenset({"gen", "civil"})


class PrestressBeamLoadItem(ItemGroupFields, total=False):
    """One entry of the /db/PRST "ITEMS" array."""

    LCNAME: str  # Load Case Name, required
    DIR: int  # Local y=0, Local z=1; default 0, optional
    TENSION: float  # required
    DISTANCE_I: float  # Distance - I (Di), default 0, optional
    DISTANCE_M: float  # Distance - M (Dm), default 0, optional
    DISTANCE_J: float  # Distance - J (Dj), default 0, optional


class PrestressBeamLoadPayload(TypedDict):
    """docs/manual/07_DB_Temperature_Prestress.md #10 — /db/PRST. Keyed by element id."""

    ITEMS: List[PrestressBeamLoadItem]


class PrestressBeamLoad(DbResource):
    ENDPOINT = "/db/PRST"
    NAME = "Prestress Beam Loads"
    PRODUCTS = frozenset({"gen", "civil"})


class PretensionLoadItem(ItemGroupFields, total=False):
    """One entry of the /db/PTNS "ITEMS" array."""

    LCNAME: str  # Load Case Name, required
    TENSION: float  # Pretension Load, required


class PretensionLoadPayload(TypedDict):
    """docs/manual/07_DB_Temperature_Prestress.md #11 — /db/PTNS. Keyed by element id."""

    ITEMS: List[PretensionLoadItem]


class PretensionLoad(DbResource):
    ENDPOINT = "/db/PTNS"
    NAME = "Pretension Loads"
    PRODUCTS = frozenset({"gen", "civil"})


class ExternalLoadCaseForPretensionPayload(TypedDict, total=False):
    """docs/manual/07_DB_Temperature_Prestress.md #12 — /db/EXLD Specifications table."""

    LCNAME_ITEM: List[str]  # Load Case Names with pretension loads, required


class ExternalLoadCaseForPretension(DbResource):
    ENDPOINT = "/db/EXLD"
    NAME = "External Type Load Case for Pretension"
    PRODUCTS = frozenset({"gen", "civil"})
