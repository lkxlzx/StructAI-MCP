"""Source: docs/manual/04_DB_Properties.md, items 1, 3, 5-10, 28, 32, plus the
Hyper-S variants MATL-M1, IMFM-M1, EPMT-M1. None of the three have a
Specifications table in the chapter file; their payload TypedDicts below are
derived from live `GET /info/db/...` server introspection instead (confirmed
2026-07-29, Civil NX Hyper-S) — see each Hyper-S class's own docstring. Two
of the three turned out to have a genuinely different wire shape from their
non-Hyper-S sibling, not just a product gate on the same schema: MATL-M1's
PARAM entries nest user-defined fields under USER_DEFINED with 0-indexed
P_TYPE (vs MATL's flat fields with 1-indexed P_TYPE), and IMFM-M1 nests
fields under CONCRETE/STEEL sub-objects with different names entirely
(UN_CONC_NAME/CONF_CONC_NAME vs IMFM's flat CONC_NAME/CONFINED_CONC_NAME).
"""
from __future__ import annotations

from typing import Any, List, TypedDict

from ..base import HYPER_S_ONLY, DbResource


class MaterialParam(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #1 — one entry of MATL's "PARAM" array.

    Shape depends on P_TYPE: 1=Standard/DB (STANDARD/CODE/DB/bELAST),
    2=Isotropic/User (ELAST/POISN/THERMAL/DEN/MASS), 3=Orthotropic/User
    (ELAST_M/POISN_M/THERMAL_M/SHEAR_M/DEN/MASS) — all three variants'
    fields are optional here since only one variant applies per P_TYPE.
    """

    P_TYPE: int  # 1=Standard/DB, 2=Isotropic/User, 3=Orthotropic/User; required
    # P_TYPE = 1
    STANDARD: str
    CODE: str
    DB: str
    bELAST: bool
    # P_TYPE = 2
    ELAST: float
    POISN: float
    THERMAL: float
    DEN: float
    MASS: float
    # P_TYPE = 3
    ELAST_M: List[float]
    POISN_M: List[float]
    THERMAL_M: List[float]
    SHEAR_M: List[float]


class MaterialPayload(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #1 — /db/MATL Specifications table."""

    TYPE: str  # "CONC"/"STEEL"/"SRC"/"ALUMINUM"/"USER", required
    NAME: str  # Material Name, required
    HE_SPEC: float  # Specific Heat, default 0, optional
    HE_COND: float  # Heat Conduction, default 0, optional
    PLMT: int  # Plastic Material No., default 0, optional
    P_NAME: str  # Plastic Material Name, default "", optional
    bMASS_DENS: bool  # Use Mass Density, default false, optional
    DAMP_RAT: float  # Damping Ratio, default 0, optional
    PARAM: List[MaterialParam]  # required


class Material(DbResource):
    ENDPOINT = "/db/MATL"
    NAME = "Material Properties"
    PRODUCTS = frozenset({"gen", "civil"})


class MaterialHyperSUserDefined(TypedDict, total=False):
    """Shape of MaterialHyperSParam's USER_DEFINED sub-object."""

    bELAST: bool  # User Elasticity
    POISN: float  # Poisson's ratio
    THERMAL: float  # Coefficients of linear thermal
    DEN: float  # Weight Density
    ELAST_M: List[float]  # Modulii of elasticity [X, Y, Z]
    THERMAL_M: List[float]  # Coefficients of linear thermal [X, Y, Z]
    SHEAR_M: List[float]  # Shear modulii [xy, xz, yz]
    POISN_M: List[float]  # Poisson's ratio [xy, xz, yz]
    bMASS_DENS: bool  # Use Mass Density
    MASS: float  # Mass Density


class MaterialHyperSThermalTransfer(TypedDict, total=False):
    """Shape of MaterialHyperSParam's THERMAL_TRANS sub-object."""

    HE_SPEC: float  # Specific Heat
    HE_COND: float  # Heat Conduction


class MaterialHyperSParam(TypedDict, total=False):
    """One entry of MaterialHyperSPayload's PARAM array. P_TYPE is 0-indexed
    here (Standard=0, Isotropic=1, Orthotropic=2) — the non-Hyper-S sibling
    MaterialParam is 1-indexed for the same concept, confirmed live.
    """

    P_TYPE: int  # Standard/DB=0, Isotropic/User=1, Orthotropic/User=2
    STANDARD: str  # Standard
    CODE: str  # Code
    DB: str  # DB Name
    USER_DEFINED: MaterialHyperSUserDefined
    PLASTIC_MATL_NAME: str  # Plastic Material Name
    THERMAL_TRANS: MaterialHyperSThermalTransfer


class MaterialHyperSPayload(TypedDict, total=False):
    """No Specifications table exists for this Hyper-S variant of MATL in
    the manual chapter. Field names/types below come from `GET
    /info/db/MATL-M1` server introspection; a live GET on a real Civil NX
    Hyper-S model also confirmed a populated row using the P_TYPE=0
    (Standard/DB) shape (both confirmed 2026-07-29).
    """

    MATL_NAME: str  # Material Name
    MATL_TYPE: str  # Material Type
    DAMP_RAT: float  # Damping Ratio
    PARAM: List[MaterialHyperSParam]  # Material Parameters


class MaterialHyperS(DbResource):
    ENDPOINT = "/db/MATL-M1"
    NAME = "Material Properties (Hyper-S)"
    PRODUCTS = HYPER_S_ONLY


class MaterialModifyConcreteDesign(TypedDict, total=False):
    C_FC: float  # Strength — GET only (computed), see manual
    C_FCI: float  # Strength (initial) — GET only (computed), see manual


class MaterialModifyConcreteData1(TypedDict, total=False):
    CODENAME: str  # Material Code Name, required
    CODEMATLNAME: str  # Material Grade, required
    DESIGN: MaterialModifyConcreteDesign  # required


class MaterialModifyConcretePayload(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #32 — /db/MATD Specifications table.

    GET/PUT only — used to modify design values/rebar grade of an existing
    TYPE="CONC" material created via Material (/db/MATL).
    """

    TYPE: str  # "CONC", required
    NAME: str  # Material Name (matches an existing MATL entry), required
    DATA1: MaterialModifyConcreteData1  # required
    REBAR_CODENAME: str  # required
    MAINREBAR_REBARNAME: str  # required
    SUBREBAR_REBARNAME: str  # default "", optional
    MAINREBAR_B_FY: float  # GET only (computed), default 0
    SUBREBAR_B_FY: float  # GET only (computed), default 0


class MaterialModifyConcrete(DbResource):
    ENDPOINT = "/db/MATD"
    NAME = "Modify Concrete Materials"
    PRODUCTS = frozenset({"gen", "civil"})
    METHODS = frozenset({"GET", "PUT"})


class InelasticFiberMaterialLinkPayload(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #3 — /db/IMFM Specifications table.

    Concrete entries use CONC_NAME/CONFINED_CONC_NAME/REBAR_NAME; Steel
    entries use STEEL_NAME — pass only the fields relevant to the material.
    """

    CONC_NAME: str  # Inelastic Material of Concrete (/db/FIMP name), default "", optional
    CONFINED_CONC_NAME: str  # Confined Concrete for Columns (/db/FIMP name), default "", optional
    REBAR_NAME: str  # Inelastic Material of Rebar (/db/FIMP name), default "", optional
    STEEL_NAME: str  # Inelastic Material of Steel (/db/FIMP name), default "", optional


class InelasticFiberMaterialLink(DbResource):
    ENDPOINT = "/db/IMFM"
    NAME = "Inelastic Material Properties for Fiber Model"
    PRODUCTS = frozenset({"gen", "civil"})


class InelasticFiberMaterialLinkHyperSConcrete(TypedDict, total=False):
    """Shape of InelasticFiberMaterialLinkHyperSPayload's CONCRETE
    sub-object."""

    UN_CONC_NAME: str  # Inelastic Material of Concrete (/db/FIMP name)
    CONF_CONC_NAME: str  # Confined Concrete for Columns (/db/FIMP name)
    REBAR_NAME: str  # Inelastic Material of Rebar (/db/FIMP name)


class InelasticFiberMaterialLinkHyperSSteel(TypedDict, total=False):
    """Shape of InelasticFiberMaterialLinkHyperSPayload's STEEL sub-object."""

    STEEL_NAME: str  # Inelastic Material of Steel (/db/FIMP name)


class InelasticFiberMaterialLinkHyperSPayload(TypedDict, total=False):
    """No Specifications table exists for this Hyper-S variant of IMFM in
    the manual chapter. Field names/types below come from `GET
    /info/db/IMFM-M1` server introspection (confirmed live 2026-07-29,
    Civil NX Hyper-S). Unlike the flat non-Hyper-S IMFM shape, fields here
    nest under CONCRETE/STEEL sub-objects with different names entirely
    (UN_CONC_NAME/CONF_CONC_NAME vs CONC_NAME/CONFINED_CONC_NAME) — not a
    simple product gate on the same schema.
    """

    CONCRETE: InelasticFiberMaterialLinkHyperSConcrete
    STEEL: InelasticFiberMaterialLinkHyperSSteel


class InelasticFiberMaterialLinkHyperS(DbResource):
    ENDPOINT = "/db/IMFM-M1"
    NAME = "Inelastic Material Link for Auto Generation (Hyper-S)"
    PRODUCTS = HYPER_S_ONLY


class TimeDependentMaterialFunctionValue(TypedDict, total=False):
    DAY: float  # Time, required
    VALUE: float  # required


class TimeDependentMaterialFunctionPayload(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #5 — /db/TDMF Specifications table."""

    NAME: str  # Material Function Name, required
    FTYPE: str  # "CREEP" / "SHRINK" / "RELAX", required
    SCALE: float  # Scale Factor, required
    DESC: str  # default "", optional
    vDAY: List[TimeDependentMaterialFunctionValue]  # required
    CTYPE: str  # FTYPE=CREEP only: "SC"=Specific Creep, "CF"=Creep Function, "CC"=Creep Coefficient; required
    RELAXATION: int  # FTYPE=RELAX only: Hour=0, Day=1; required
    ELAST: float  # Elast; /info declares it and the manual documents it nowhere (checked across every chapter, 2026-09-04). The section's
    # Specifications table and its own JSON Schema both list seven properties
    # and stop. A live POST of the manual's own worked example has answered
    # "Wrong Field" on both products since 2026-08-16 and was left unresolved;
    # this is a candidate cause, not a confirmed one.


class TimeDependentMaterialFunction(DbResource):
    ENDPOINT = "/db/TDMF"
    NAME = "Time Dependent Material – User Defined"
    PRODUCTS = frozenset({"gen", "civil"})


class TimeDependentMaterialCreepShrinkagePayload(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #6 — /db/TDMT Specifications table.

    Fields 5-8 are conditional on CODE (CEB-FIP uses MSIZE/TYPEOFAFFR, ACI
    uses VOL/CMETHOD, CODE="EUROPEAN" uses TCODE/bSILICA); pass only the ones
    matching the selected code.

    ⚠️ `GET /info/db/TDMT` (checked 2026-07-30) reveals roughly 70 total
    fields spanning many more design codes (JSCE, GB, JTG, and others) than
    the three branches typed here — this endpoint's Specifications table is
    itself only a subset of what the server actually accepts. Only
    CEB-FIP/ACI/European are typed for v1; treat any other CODE value's
    extra fields as untyped extra dict keys, same as SECT_I's precedent.

    ⚠️ 2026-08-27: the manual's own `CODE` value table (article id
    `35808006330009`) was re-verified 2026-08-25 and gained 5 previously
    undocumented entries: `"INDIA_IRC_112_2020"`, `"AS_2017_AMD_2024"`,
    `"AS_2018_AMD_2021"`, `"NEWZEALAND_2022"`, `"CHJTG_T_D65_2015"`. `CODE`
    is plain `str` here (this SDK never hardcoded a `Literal` of the ~30
    valid values), so these additions need no code change — noted here only
    so the field's accepted-value set stays traceable to its source.
    Manual-sourced, not independently live-tested (purely additive value
    documentation, no live server behavior in question).
    """

    NAME: str  # Time Dependent Material Name, required
    CODE: str  # Code Name, required
    STR: float  # Compression Strength, required
    HU: float  # Relative Humidity, required
    MSIZE: float  # CEB-FIP: Notional Size of Member, required
    CTYPE: str  # Type of Cement, default "RS", optional
    AGE: float  # Concrete Age, required
    TYPEOFAFFR: int  # CEB-FIP 2010: Aggregate type 0=Basalt/dense limestone, 1=Quartzite, 2=Limestone, 3=Sandstone; default 0
    VOL: float  # ACI: Volume/Surface Ratio, required
    CMETHOD: str  # ACI: "MOIST" / "STEAM", default "MOIST", optional
    TCODE: int  # CODE="EUROPEAN": Type of Code, optional. Confirmed live 2026-07-30 (real PSC bridge model, Eurocode) — not in the manual's own Specifications table.
    bSILICA: bool  # CODE="EUROPEAN": Silica Fume, optional. Confirmed live 2026-07-30 — see TCODE.


class TimeDependentMaterialCreepShrinkage(DbResource):
    ENDPOINT = "/db/TDMT"
    NAME = "Time Dependent Material – Creep/Shrinkage"
    PRODUCTS = frozenset({"gen", "civil"})


class TimeDependentMaterialStrengthPayload(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #7 — /db/TDME Specifications table.

    Additional fields are grouped by CODENAME, not by TYPE=CODE/USER as an
    earlier version of this TypedDict implied.

    ⚠️ Corrected 2026-08-27: the previous version grouped `A`/`B` under
    "ACI/KDS", implying `CODENAME="KDS-2016"` (the code Korean users
    reach for most) uses them. Live-confirmed on Gen NX: `CODENAME=
    "KDS-2016"` with `A`/`B` answers `"[Error] Time Dependent
    Material(Comp. Strength) input data contain errors."` (the code name
    is recognized, its own required fields are missing); the same
    material with `iCTYPE`/`DENSITY` instead round-trips cleanly.
    `A`/`B` actually belong to `CODENAME="ACI"` or `"Korean Standard"` (a
    separate, differently-named code from `"KDS-2016"`) — confirmed
    `"Korean Standard"` + `A`/`B` also round-trips cleanly. This matches
    (and finally explains) a 2026-07-2x finding already on record: probing
    `KDS-2016` with `A`/`B` got exactly this "recognized but its own
    fields are missing" error, not "Wrong Field" -- the missing fields
    were iCTYPE/DENSITY, not a naming problem.

    Field groups by CODENAME (Cement Type `iCTYPE` values are shared
    across groups but not enumerated per-group here -- see the manual):
    - `"ACI"`, `"Korean Standard"`: `A`, `B` (both required)
    - `"CEB-FIP(1990)"`, `"Ohzagi"`, `"European"`, `"INDIA(IRC:112-2011)"`,
      `"KCI-USD12"`: `iCTYPE` (required)
    - `"CEB-FIP(2010)"`, `"INDIA(IRC:112-2020)"`: `iCTYPE`, `nAGGRE` (both required)
    - `"Russian"`: `iCTYPE`, `CMETH`, `CTYPE`, `MAXS`, `PZ` (all required;
      `CTYPE` here is unrelated to the top-level `TYPE` field despite the
      similar name)
    - `"GILBERT AND RANZI"`, **`"KDS-2016"`**: `iCTYPE`, `DENSITY` (both
      required) -- confirmed live, see above
    - `"Japan (Hydration)"`: `TENS_STRN_FACTOR` (required), `bUSE` (default
      false); then `A`/`B`/`D` if `bUSE=false`, or `iCTYPE` if `bUSE=true`
    - `"Japan (Elastic)"`: `iECTYPE` (required)
    - Codes needing only the 4 common fields (no group-specific ones):
      `"INDIA(IRC:18-2000)"`, `"CEB-FIP(1978)"`, `"AS 5100.5-2017"`,
      `"AS 5100.5-2016"`, `"AS/RTA 5100.5-2011"`, `"AS 3600-2009"`
    """

    NAME: str  # Material Name, required
    TYPE: str  # "CODE" / "USER", required
    CODENAME: str  # TYPE=CODE, required
    STRENGTH: float  # TYPE=CODE, required
    A: float  # CODENAME in {ACI, Korean Standard, Japan (Hydration) w/ bUSE=false}: Factor a, required
    B: float  # CODENAME in {ACI, Korean Standard, Japan (Hydration) w/ bUSE=false}: Factor b, required
    iCTYPE: int  # CODENAME in {CEB-FIP(1990/2010), Ohzagi, European, INDIA(IRC:112-*), KCI-USD12, Russian, GILBERT AND RANZI, KDS-2016, Japan (Hydration) w/ bUSE=true}: Cement Type, required
    nAGGRE: int  # CODENAME in {CEB-FIP(2010), INDIA(IRC:112-2020)}: Aggregate Type, required
    DENSITY: float  # CODENAME in {GILBERT AND RANZI, KDS-2016}: Weight Density, required
    CMETH: int  # CODENAME=Russian: Curing Method, Natural=0/Steam=1, required
    CTYPE: int  # CODENAME=Russian: Concrete Type (distinct from top-level TYPE), Heavy=0/Fine-Grained=1, required
    MAXS: float  # CODENAME=Russian: Maximum Aggregate Size, required
    PZ: float  # CODENAME=Russian: Specific Content of the Cement Paste, required
    TENS_STRN_FACTOR: float  # CODENAME=Japan (Hydration): Tensile Strength Factor, required
    bUSE: bool  # CODENAME=Japan (Hydration): Use Concrete Data Option, default false, optional
    D: float  # CODENAME=Japan (Hydration), bUSE=false: Factor d, required
    iECTYPE: int  # CODENAME=Japan (Elastic): Normal=0/Rapid=1, required


class TimeDependentMaterialStrength(DbResource):
    ENDPOINT = "/db/TDME"
    NAME = "Time Dependent Material – Compressive Strength"
    PRODUCTS = frozenset({"gen", "civil"})


class ChangePropertyPayload(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #8 — /db/EDMP Specifications table."""

    TYPE: str  # "NSM"=Notional Size, "VSR"=Volume/Surface Ratio; required
    H_VS: float  # h for NSM, v/s for VSR, required


class ChangeProperty(DbResource):
    ENDPOINT = "/db/EDMP"
    NAME = "Change Property"
    PRODUCTS = frozenset({"gen", "civil"})


class TimeDependentMaterialLinkPayload(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #9 — /db/TMAT Specifications table."""

    TDMT_NAME: str  # Creep/Shrinkage Name (/db/TDMT name), required
    TDME_NAME: str  # Comp. Strength Name (/db/TDME name), required


class TimeDependentMaterialLink(DbResource):
    ENDPOINT = "/db/TMAT"
    NAME = "Time Dependent Material Link"
    PRODUCTS = frozenset({"gen", "civil"})


class PlasticMaterialPayload(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #10 — /db/EPMT Specifications table.

    Deeply conditional on MODEL_TYPE ("TR"/"VM"=Tresca/Von-Mises common
    params under TRESCA/VMISES, "MC"=Mohr-Coulomb under MOHRCL, "DP"=
    Drucker-Prager under DRUCKER, "MA"=Masonry under MASONRY, "DM"=Concrete
    Damage under CONCDMG).

    ⚠️ 2026-08-27: the manual's DP/MA/DM branches (`DRUCKER`/`MASONRY`/
    `CONCDMG`) were entirely missing from this repo's copy of the chapter
    until a 2026-08-25 re-verification against the source article (id
    `35808376517913`) added them back; TRESCA/VMISES/MOHRCL were already
    typed here. The same re-verification also corrected `HARDENING_COEF`
    (for all four hardening-capable models — TRESCA/VMISES/MOHRCL/DRUCKER)
    from Optional to **Required whenever `OPT_HARDENING`'s default of `0`
    (Activated) is in effect** — the manual's previous copy of this table
    had marked it Optional. Manual-sourced, not independently live-tested:
    this is additive/corrective documentation only, and none of these
    sub-objects' internal shape is broken out into its own TypedDict here
    (unlike the Hyper-S EPMT-M1 sibling below) since MOHRCL/DRUCKER share
    one shape and TRESCA/VMISES share another — see the inline comments.
    """

    NAME: str  # Plastic Material Name, required
    MODEL_TYPE: str  # "TR"/"VM"/"MC"/"DP"/"MA"/"DM", required
    TRESCA: Any  # MODEL_TYPE=TR: {"INIT_YIELD_STRESS" (required), "OPT_HARDENING" (default 0=Activated), "HARDENING_TYPE" ("ISO"/"KIN"/"MIX", default "ISO", only used when OPT_HARDENING=0), "HARDENING_COEF" (required when OPT_HARDENING=0), "BACK_STRESS_COEF" (required when HARDENING_TYPE="MIX")}
    VMISES: Any  # MODEL_TYPE=VM: same shape as TRESCA
    MOHRCL: Any  # MODEL_TYPE=MC: {"INIT_COHESION" (required), "INIT_FRIC_ANGLE" (required), "OPT_HARDENING" (default 0=Activated), "HARDENING_TYPE" ("ISO"/"KIN"/"MIX", default "ISO"), "HARDENING_COEF" (required when OPT_HARDENING=0), "BACK_STRESS_COEF" (required when HARDENING_TYPE="MIX")}
    DRUCKER: Any  # MODEL_TYPE=DP: same shape as MOHRCL. Added 2026-08-27, manual-sourced only.
    MASONRY: Any  # MODEL_TYPE=MA: {"BM", "BED_JOINT", "HEAD_JOINT": each {"YOUNG_S_MODULUS", "POSSIONS_S_RATIO", "TENSION_STRENGTH", "SOFTENING_PARAMETER" (BM only) / "HARDENING_PARAM" (BED_JOINT/HEAD_JOINT only)}, "GEOM": {"BRICK_LENGTH", "BRICK_HEIGHT", "THICKNESS_BED", "THICKNESS_HEAD", "COORD_TYPE" (Global-Y/Global-X=0, Local-y/Local-z=-1, Global-Z/Angle=-4), "COORD_ANGLE" (required when COORD_TYPE=-4)} — all required}. Added 2026-08-27, manual-sourced only; NOTE the COORD_TYPE enum (-1/-4) and per-layer field naming (SOFTENING_PARAMETER vs HARDENING_PARAM) both differ from the Hyper-S EPMT-M1 sibling's PlasticMaterialHyperSMasonry (0/1/2 enum, single STIFF_REDUCTION name) — do not conflate the two.
    CONCDMG: Any  # MODEL_TYPE=DM: {"DILIATION_ANGLE", "ECCEN", "FBO_FCO", "K", "VISCOSITY_PARAM", "COMP_ITEMS"/"TENSILE_ITEMS": Array[{"INELASTIC_STRAIN", "YIELD_STRESS", "DAMAGE"}] — all required}. Added 2026-08-27, manual-sourced only; same shape as the Hyper-S sibling's PlasticMaterialHyperSConcreteDamage.


class PlasticMaterial(DbResource):
    ENDPOINT = "/db/EPMT"
    NAME = "Plastic Material"
    PRODUCTS = frozenset({"gen", "civil"})


class PlasticMaterialHyperSHardeningModel(TypedDict, total=False):
    """Shared shape of PlasticMaterialHyperSPayload's TRESCA/VMISES bodies."""

    INIT_YIELD_STRESS: float  # Initial Uniaxial Yield Stress
    OPT_HARDENING: bool  # Hardening
    HARDENING_TYPE: int  # Isotropic=0, Kinematic=1, Mixed=2
    HARDENING_COEF: float  # Hardening Coefficient
    BACK_STRESS_COEF: float  # Back Stress Coefficient


class PlasticMaterialHyperSCoulombModel(TypedDict, total=False):
    """Shared shape of PlasticMaterialHyperSPayload's MOHRCL/DRUCKER
    bodies."""

    INIT_COHESION: float  # Initial Cohesion
    INIT_FRIC_ANGLE: float  # Initial Friction Angle (deg)
    OPT_HARDENING: bool  # Hardening
    HARDENING_TYPE: int  # Isotropic=0
    HARDENING_COEF: float  # Hardening Coefficient
    BACK_STRESS_COEF: float  # Back Stress Coefficient


class PlasticMaterialHyperSMasonryLayer(TypedDict, total=False):
    """Shared shape of PlasticMaterialHyperSMasonry's BM/BED_JOINT/
    HEAD_JOINT sub-objects."""

    YOUNG_S_MODULUS: float  # Young's Modulus
    POSSIONS_S_RATIO: float  # Poisson's Ratio (server's own field name spelling)
    TENSION_STRENGTH: float  # Tension Strength
    STIFF_REDUCTION: float  # Stiffness Reduction Factor


class PlasticMaterialHyperSMasonryGeometry(TypedDict, total=False):
    BRICK_LENGTH: float
    BRICK_HEIGHT: float
    THICKNESS_BED: float
    THICKNESS_HEAD: float


class PlasticMaterialHyperSMasonryCoord(TypedDict, total=False):
    COORD_TYPE: int  # Global=0, ElementLocal=1, GlobalZAngle=2
    COORD_ANGLE: float  # Angle from Global X (deg)


class PlasticMaterialHyperSMasonry(TypedDict, total=False):
    """Shape of PlasticMaterialHyperSPayload's MASONRY sub-object."""

    BM: PlasticMaterialHyperSMasonryLayer  # Brick Material Properties
    BED_JOINT: PlasticMaterialHyperSMasonryLayer  # Bed Joint Properties
    HEAD_JOINT: PlasticMaterialHyperSMasonryLayer  # Head Joint Properties
    GEOM: PlasticMaterialHyperSMasonryGeometry  # Geometry of Masonry Panel
    MAT_COORD: PlasticMaterialHyperSMasonryCoord  # Material Coordinate System


class PlasticMaterialHyperSConcreteDamageItem(TypedDict, total=False):
    """Shared shape of PlasticMaterialHyperSConcreteDamage's COMP_ITEMS/
    TENSILE_ITEMS array entries."""

    INELASTIC_STRAIN: float
    YIELD_STRESS: float
    DAMAGE: float


class PlasticMaterialHyperSConcreteDamage(TypedDict, total=False):
    """Shape of PlasticMaterialHyperSPayload's CONCDMG sub-object."""

    DILIATION_ANGLE: float  # Dilation Angle (deg) — server's own field name spelling
    ECCEN: float  # Eccentricity
    FBO_FCO: float  # fbo/fco
    K: float
    VISCOSITY_PARAM: float  # Viscosity Parameter
    COMP_ITEMS: List[PlasticMaterialHyperSConcreteDamageItem]  # Compressive Behavior
    TENSILE_ITEMS: List[PlasticMaterialHyperSConcreteDamageItem]  # Tensile Behavior


class PlasticMaterialHyperSPayload(TypedDict, total=False):
    """No Specifications table exists for this Hyper-S variant of EPMT in
    the manual chapter. Field names/types below come from `GET
    /info/db/EPMT-M1` server introspection (confirmed live 2026-07-29,
    Civil NX Hyper-S). MODEL_TYPE is an int here (Tresca=0, VonMises=1,
    MohrCoulomb=2, DruckerPrager=3, Masonry=4, ConcreteDamage=5) — unlike
    the non-Hyper-S EPMT's string codes ("TR"/"VM"/"MC"/...). Pass only the
    sub-object matching MODEL_TYPE.
    """

    NAME: str  # Name
    MODEL_TYPE: int  # Tresca=0, VonMises=1, MohrCoulomb=2, DruckerPrager=3, Masonry=4, ConcreteDamage=5
    TRESCA: PlasticMaterialHyperSHardeningModel  # MODEL_TYPE=0
    VMISES: PlasticMaterialHyperSHardeningModel  # MODEL_TYPE=1
    MOHRCL: PlasticMaterialHyperSCoulombModel  # MODEL_TYPE=2
    DRUCKER: PlasticMaterialHyperSCoulombModel  # MODEL_TYPE=3
    MASONRY: PlasticMaterialHyperSMasonry  # MODEL_TYPE=4
    CONCDMG: PlasticMaterialHyperSConcreteDamage  # MODEL_TYPE=5


class PlasticMaterialHyperS(DbResource):
    ENDPOINT = "/db/EPMT-M1"
    NAME = "Plastic Material (Hyper-S)"
    PRODUCTS = HYPER_S_ONLY


class InelasticMaterialKentParkParam(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #28 — /db/FIMP "KENPAR" (Kent & Park)
    sub-object.

    ⚠️ 2026-08-27: EC1_METHOD/EC1/Z/STRENGTH_AFTER were missing from this
    class relative to the manual's own Kent & Park field table (article id
    `35944335180569`); added here. Manual-sourced, not independently
    live-tested — this endpoint needs a full nonlinear material definition
    to round-trip meaningfully and wasn't cheap to verify live.
    """

    FC: float  # Concrete Strength (fc'), required
    PARTIAL_FACT: float  # Partial Safety Factor, required
    K: float  # Strength/Strain Factor, required
    EC0: float  # Peak Strain (epsilon_c0), required
    EC1_METHOD: int  # Hardening Strain Method: Manual=0, Calculation=1; required
    EC1: float  # Hardening Strain Manual (epsilon_c1), required (used when EC1_METHOD=0)
    Z: float  # Hardening Strain Calculation (Z), required (used when EC1_METHOD=1)
    ECU: float  # Ultimate Strain (epsilon_cu), required
    STRENGTH_AFTER: int  # Strength After Critical Strain: Zero=0, Keep=1; required


class InelasticMaterialPropertyPayload(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #28 — /db/FIMP Specifications table.

    Deeply conditional on (MATL_TYPE, HYS_MODEL) — only the Concrete
    Kent & Park model ("CONC"/"KPM") is typed for v1; other hysteresis
    models (documented per footnote 1 in the manual) go under the same
    CONC/STEEL keys with a different HYS_MODEL-specific sub-object.
    """

    NAME: str  # Material Name, required
    MATL_TYPE: str  # "CONC" / "STEEL", required
    HYS_MODEL: str  # e.g. "KPM" (Kent & Park), required
    CONC: Any  # MATL_TYPE=CONC, e.g. {"KENPAR": {...InelasticMaterialKentParkParam}}
    STEEL: Any  # MATL_TYPE=STEEL, model-specific body


class InelasticMaterialProperty(DbResource):
    ENDPOINT = "/db/FIMP"
    NAME = "Inelastic Material Properties"
    PRODUCTS = frozenset({"gen", "civil"})
