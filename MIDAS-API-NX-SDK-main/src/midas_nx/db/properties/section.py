"""Source: docs/manual/04_DB_Properties.md, items 12, 14-21, 29, 31.

SECT is deeply conditional on SECTTYPE ("DBUSER"/"VALUE"/"SRC"/"COMBINED"/
"PSC"/"TAPERED"/"COMPOSITE"/"SOD") — only the common envelope (SECTTYPE,
SECT_NAME, SECT_BEFORE) is typed here; SECT_I (the SECTTYPE-specific body)
is left as a plain dict, matching the manual's own per-SECTTYPE subsections
(12-A DB/User, 12-B Value, ...) which are not all ported to this v1.
"""
from __future__ import annotations

from typing import Any, List, TypedDict

from ..base import CIVIL_ONLY, DbResource, ItemGroupFields


class SectBefore(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #12 — common "SECT_BEFORE" fields."""

    SHAPE: str  # Section Shape, required
    OFFSET_PT: str  # e.g. "CC", default "CC", optional
    OFFSET_CENTER: int  # 0=Centroid, 1=Center of Section; default 0
    HORZ_OFFSET_OPT: int  # 0=Extreme Fiber, 1=User; default 0
    USERDEF_OFFSET_YI: float  # default 0
    VERT_OFFSET_OPT: int  # default 0
    USERDEF_OFFSET_ZI: float  # default 0
    USER_OFFSET_REF: int  # 0=Centroid, 1=Extreme Fiber; default 0
    USE_SHEAR_DEFORM: bool  # default false
    USE_WARPING_EFFECT: bool  # default false
    DATATYPE: int  # 12-A DB/User only: DB=1, User=2; required for SECTTYPE="DBUSER"
    SECT_I: Any  # SECTTYPE-specific body, e.g. (DBUSER) {"DB_NAME": "KS21", "SECT_NAME": "H300x150x6.5/9"}


class SectionPayload(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #12 — /db/SECT common Specifications table.

    ⚠️ **A PUT never recomputes a VALUE section's stiffness.** Measured live
    2026-09-03 on Gen NX. For ``SECTTYPE: "VALUE"`` the server derives
    ``SECT_BEFORE.SECT_I.STIFF`` (AREA, ASY, ASZ, RXX, ...) and ``.DESIGN``
    from ``vSIZE`` **on POST only**, which is what the manual's ``Create Only``
    marking on ``CALC_OPT`` means. Changing ``vSIZE`` through ``update()``
    stores the new dimensions and leaves the old properties in place — 200,
    no error, and the record reads back looking self-consistent. Sending
    ``CALC_OPT: true`` on the PUT does not help; a 0.3 m section resized to
    0.9 m kept ``AREA`` 0.004533 where a fresh POST at 0.9 m gives 0.008433.
    To resize a VALUE section, delete the record and POST it again.

    A supplied ``STIFF`` always wins over the calculation, under every
    ``CALC_OPT`` value including ``true``. ``CALC_OPT: false`` with no
    ``STIFF`` to fall back on is refused on POST
    (``[Error] Section input data contain errors.``) and silently accepted on
    PUT — that asymmetry is the clearest demonstration of the create-only
    rule. See docs/live_verification_notes.md.
    """

    SECTTYPE: str  # "DBUSER"/"VALUE"/"SRC"/"COMBINED"/"PSC"/"TAPERED"/"COMPOSITE"/"SOD", required
    SECT_NAME: str  # Section Name, required
    CALC_OPT: bool  # 12-B Value only: calculate STIFF/DESIGN from vSIZE; default true, honoured on POST only - see class docstring
    SECT_BEFORE: SectBefore  # required


class Section(DbResource):
    ENDPOINT = "/db/SECT"
    NAME = "Section Properties"
    PRODUCTS = frozenset({"gen", "civil"})


class TaperedGroupPayload(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #14 — /db/TSGR Specifications table.

    ⚠️ 2026-08-27: the Y-axis polynomial fields (YEXP/YFROM/YDIST) were
    missing here — the manual documents them as the Z-axis fields' exact
    mirror (article id `35942955627673`) and this SDK only had the Z side
    typed. Added by symmetry with ZEXP/ZFROM/ZDIST. Manual-sourced, not
    independently live-tested (purely additive, same shape as the
    already-typed Z-axis fields).
    """

    NAME: str  # Tapered Group Name, required
    ELEMLIST: List[int]  # Element No. list, required
    ZVAR: str  # Z-axis Section Shape Variation: "LINEAR" / "POLY", required
    YVAR: str  # Y-axis Section Shape Variation: "LINEAR" / "POLY", required
    ZEXP: float  # ZVAR=POLY only: Z axis Exponent, required
    ZFROM: str  # ZVAR=POLY only: Z axis Symmetric Plane from "i" or "j", default "i", optional
    ZDIST: float  # ZVAR=POLY only: Z axis Symmetric Plane Distance (m), default 0, optional
    YEXP: float  # YVAR=POLY only: Y axis Exponent, required
    YFROM: str  # YVAR=POLY only: Y axis Symmetric Plane from "i" or "j", default "i", optional
    YDIST: float  # YVAR=POLY only: Y axis Symmetric Plane Distance (m), default 0, optional


class TaperedGroup(DbResource):
    ENDPOINT = "/db/TSGR"
    NAME = "Tapered Group"
    PRODUCTS = frozenset({"gen", "civil"})


class SectionStiffnessItem(ItemGroupFields, total=False):
    """⚠️ 2026-08-27: the Tapered-section J-end block (W_SF/IPART/bDiffIJ/
    J1-J8, 11 fields) was entirely missing here — the manual documents it
    as a separate naming scheme from the I-end fields (`J1`-`J8` in
    Area/Asy/Asz/Ixx/Iyy/Izz/Weight/Warping order, not `..._SF_J`; article
    id `35943174833177`). Added per the manual's own field names.
    Manual-sourced, not independently live-tested.
    """

    AREA_SF: float  # Area Scale Factor (I), default 1, optional
    ASY_SF: float  # Asy Scale Factor (I), default 1, optional
    ASZ_SF: float  # Asz Scale Factor (I), default 1, optional
    IXX_SF: float  # Ixx Scale Factor (I), default 1, optional
    IYY_SF: float  # Iyy Scale Factor (I), default 1, optional
    IZZ_SF: float  # Izz Scale Factor (I), default 1, optional
    WGT_SF: float  # Weight Scale Factor, default 1, optional
    W_SF: float  # Warping Scale Factor (I), default 1, optional
    IPART: int  # Composite Section application point: Before=1, After=2, Before+After=3; default 1, optional
    bDiffIJ: bool  # Tapered Section: use separate J-end values, default true, optional
    J1: float  # Tapered Section, J-end: Area Scale Factor, default 1, optional
    J2: float  # Tapered Section, J-end: Asy Scale Factor, default 1, optional
    J3: float  # Tapered Section, J-end: Asz Scale Factor, default 1, optional
    J4: float  # Tapered Section, J-end: Ixx Scale Factor, default 1, optional
    J5: float  # Tapered Section, J-end: Iyy Scale Factor, default 1, optional
    J6: float  # Tapered Section, J-end: Izz Scale Factor, default 1, optional
    J7: float  # Tapered Section, J-end: Weight Scale Factor, default 1, optional
    J8: float  # Tapered Section, J-end: Warping Scale Factor, default 1, optional


class SectionStiffnessPayload(TypedDict):
    """docs/manual/04_DB_Properties.md #15 — /db/SECF. Keyed by **section** id.

    Verified live 2026-07-26 (Civil NX 2026 v2.1): posting this body under an
    element id returns 200 with no error and stores nothing at all, while the
    identical body under a section id round-trips. This docstring said
    "element id" until that run — one of the cases where a wrong comment is
    the whole defect, since these TypedDicts are documentation rather than
    runtime validation.
    """

    ITEMS: List[SectionStiffnessItem]


class SectionStiffness(DbResource):
    ENDPOINT = "/db/SECF"
    NAME = "Section Manager – Stiffness"
    PRODUCTS = frozenset({"gen", "civil"})


class SectionReinforcementShearItem(TypedDict, total=False):
    """⚠️ 2026-08-27: SBW (Steel Bar for Web)/TR (Torsional Reinforcement)/
    SR (Stirrup)/Enclosing-Stirrup fields (16 fields) were entirely missing
    here — only the Diagonal Reinforcement (DR) fields were typed. The
    manual's own field table (article id `35943227821465`) documents all
    four groups as siblings under the same `SBAR_ITEMS[]` entry. Added per
    the manual. Manual-sourced, not independently live-tested.
    """

    OPT_DR: bool  # Diagonal Reinforcement, default false, optional
    DR_PITCH: float  # [DR] Pitch, optional
    DR_THETA: float  # [DR] Angle, optional
    DR_AW: float  # [DR] Area, optional
    OPT_SBW: bool  # Steel Bar for Web, default false, optional
    SBW_PITCH: float  # [SBW] Pitch, optional
    SBW_ANGLE: float  # [SBW] Angle, optional
    SBW_AP: float  # [SBW] Area, optional
    SBW_PS: float  # [SBW] Pre-force, optional
    SBW_FACTOR: float  # [SBW] Shear Reduction Factor, optional
    OPT_TR: bool  # Torsional Reinforcement, default false, optional
    TR_PITCH: float  # [TR] Pitch, optional
    TR_AWT: float  # [TR] Area (Web), optional
    TR_ALT: float  # [TR] Area (Longitudinal), optional
    OPT_SR: bool  # Stirrup Exist, default false, optional
    SR_PITCH: float  # [SR] Pitch, optional
    SR_AW: float  # [SR] Area, optional
    OPT_LBAR_FLG: bool  # Enclosing Stirrup, default false, optional
    LBAR_THICK: float  # (Enclosed area calc) Cover Thickness, optional
    LBAR_INC_FC: int  # Include Flange/Cantilever: Off=0, On=1; optional


class SectionReinforcementLongitudinalItem(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #16 — /db/RPSC "MBAR_ITEMS[]" entry.

    Added 2026-08-27 along with the parent payload's MBAR_ITEMS field — see
    SectionReinforcementPayload's docstring. The members are the manual's,
    unchanged; only where the array hangs was wrong. See MD-40.
    """

    IJ: str  # Section Position: "I" / "J", required
    NAME: str  # Bar Name, required
    REF_Y: int  # Reference Y: Centroid=0, Left=1; required
    Y: float  # Distance from Reference (Y-dir), default 0, optional
    REF_Z: int  # Reference Z: Top=0, Bottom=1; required
    Z: float  # Distance from Reference (Z-dir), default 0, optional
    NUM: int  # Number of Rebar, required
    SPACING: float  # Spacing between Rebars, default 0, optional
    PART: int  # optional, requiredness not specified by the manual


class SectionReinforcementGroup(TypedDict, total=False):
    """One entry of /db/RPSC's `MBARS`, which carries only `MBAR_ITEMS`."""

    MBAR_ITEMS: List[SectionReinforcementLongitudinalItem]


class SectionReinforcementPayload(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #16 — /db/RPSC. Keyed by section id.

    ⚠️ 2026-08-27: `MBAR_ITEMS` (longitudinal reinforcement, required) was
    entirely missing from this payload — the manual's Specifications table
    lists it as a sibling of `SBAR_ITEMS`, both required (article id
    `35943227821465`). Added, plus the shear-item field expansion documented
    on SectionReinforcementShearItem.

    ⚠️ 2026-09-04: and added at the wrong depth. `/info/db/RPSC` declares
    `SBAR_ITEMS` at the root as documented, and `MBAR_ITEMS` one level down
    inside an array named `MBARS` that the manual never mentions. The pair
    really is asymmetric; the section reads as though it tidied that away.
    A live POST of the manual's own worked example has been failing on both
    products since 2026-08-16 and was left unresolved — this is a concrete
    cause to test, not a confirmed one. See MD-40.
    """

    OPT_MBAR_J: bool  # Same Rebar Data at i and j-end (Longitudinal), required
    OPT_SBAR_J: bool  # Same Shear Rebar Data at i and j-end, required
    OPT_CRACKED: bool  # Cracked Section, required
    SBAR_ITEMS: List[SectionReinforcementShearItem]  # [i-section, j-section], required
    MBARS: List[SectionReinforcementGroup]  # required


class SectionReinforcement(DbResource):
    ENDPOINT = "/db/RPSC"
    NAME = "Section Manager – Reinforcements"
    PRODUCTS = frozenset({"gen", "civil"})


class StressPoint(TypedDict, total=False):
    """⚠️ 2026-09-04: the manual's keys are `PY`/`PZ`, in its Specifications
    rows and its Request Example alike. `/info/db/STRPSSM` declares `Y` and
    `Z`, and gives them the descriptions `"PY"` and `"PZ"` — the section
    appears to have read the description as the key. A live POST of the
    manual's own example has been failing since 2026-08-16; this is the
    likeliest cause and has not been confirmed by a round trip. See MD-38.
    """

    Y: float  # Point Y, required
    Z: float  # Point Z, required


class SectionStressPointsPayload(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #17 — /db/STRPSSM. Keyed by section id."""

    OPT_SAME_J: bool  # Same Stress Points at i and j-end, default true, optional
    POINT_SIZE_1: int  # Number of Stress Points (I), required
    POINT_SIZE_2: int  # Number of Stress Points (J), required
    POINT1: List[StressPoint]  # Stress Point Coordinates (I), required
    POINT2: List[StressPoint]  # Stress Point Coordinates (J), required


class SectionStressPoints(DbResource):
    """⚠️ The manual documents this for both products, but three independent
    live sessions (2026-07-22, 2026-07-26, 2026-07-29) all 404 it under Gen
    NX while it answers under Civil NX. See docs/live_verification_notes.md.
    """

    ENDPOINT = "/db/STRPSSM"
    NAME = "Section Manager – Stress Points"
    PRODUCTS = CIVIL_ONLY


class PlateStiffnessScaleFactorItem(ItemGroupFields, total=False):
    AXIAL_X: float  # Axial Fxx Scale Factor, default 1, optional
    AXIAL_Y: float  # Axial Fyy Scale Factor, default 1, optional
    SHEAR: float  # Shear Fxy Scale Factor, default 1, optional
    OUT_BENDING_X: float  # Bending Mxx Scale Factor, default 1, optional
    OUT_BENDING_Y: float  # Bending Myy Scale Factor, default 1, optional
    OUT_TORSION: float  # Bending Mxy Scale Factor, default 1, optional
    OUT_SHEAR_X: float  # Shear Vxx Scale Factor, default 1, optional
    OUT_SHEAR_Y: float  # Shear Vyy Scale Factor, default 1, optional


class PlateStiffnessScaleFactorPayload(TypedDict):
    """docs/manual/04_DB_Properties.md #18 — /db/PSSF. Keyed by element id."""

    ITEMS: List[PlateStiffnessScaleFactorItem]


class PlateStiffnessScaleFactor(DbResource):
    ENDPOINT = "/db/PSSF"
    NAME = "Section Manager – Plate Stiffness Scale Factor"
    PRODUCTS = frozenset({"gen", "civil"})


class VirtualBeamPayload(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #19 — /db/VBEM. Keyed by element id."""

    VSEC1: int  # Virtual Section 1 (/db/VSEC id), required
    VSEC2: int  # Virtual Section 2 (/db/VSEC id), required


class VirtualBeam(DbResource):
    ENDPOINT = "/db/VBEM"
    NAME = "Virtual Beam"
    PRODUCTS = frozenset({"gen", "civil"})


class VirtualSectionPayload(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #20 — /db/VSEC Specifications table."""

    NAME: str  # required
    CENT_CALC_TYPE: int  # Centroid Calculation Type, required
    CEN_PT_X: float  # Centroid X (Global), required
    CEN_PT_Y: float  # Centroid Y (Global), required
    CEN_PT_Z: float  # Centroid Z (Global), required
    NORMAL_X: float  # Direction Normal Vector (X), required
    NORMAL_Y: float  # Direction Normal Vector (Y), required
    NORMAL_Z: float  # Direction Normal Vector (Z), required
    NODE_LIST: List[int]  # required
    ELEM_LIST: List[int]  # required


class VirtualSection(DbResource):
    ENDPOINT = "/db/VSEC"
    NAME = "Virtual Section"
    PRODUCTS = frozenset({"gen", "civil"})


class EffectiveWidthScaleFactorItem(ItemGroupFields, total=False):
    """J-End fields are only meaningful when bJ is true."""

    LYSCALE: float  # ly Scale Factor for Sbz (I-End), default 1, required
    ZTSCALE: float  # z_top Scale Factor (I-End), default 1, required
    ZBSCALE: float  # z_bot Scale Factor (I-End), default 1, required
    bJ: bool  # J-End Option, default false, required
    LYSCALE_J: float  # ly Scale Factor (J-End), default 1, optional
    ZTSCALE_J: float  # z_top Scale Factor (J-End), default 1, optional
    ZBSCALE_J: float  # z_bot Scale Factor (J-End), default 1, optional


class EffectiveWidthScaleFactorPayload(TypedDict):
    """docs/manual/04_DB_Properties.md #21 — /db/EWSF. Keyed by element id."""

    ITEMS: List[EffectiveWidthScaleFactorItem]


class EffectiveWidthScaleFactor(DbResource):
    """⚠️ The manual documents this for both products, but three independent
    live sessions (2026-07-22, 2026-07-26, 2026-07-29) all 404 it under Gen
    NX while it answers under Civil NX. See docs/live_verification_notes.md.
    """

    ENDPOINT = "/db/EWSF"
    NAME = "Effective Width Scale Factor"
    PRODUCTS = CIVIL_ONLY


class ElementStiffnessScaleFactorItem(ItemGroupFields, total=False):
    AREA_SF: float  # Area (Cross-sectional area), default 1.0, optional
    ASY_SF: float  # Asy (Shear area, local y), default 1.0, optional
    ASZ_SF: float  # Asz (Shear area, local z), default 1.0, optional
    IXX_SF: float  # Ixx (Torsional resistance), default 1.0, optional
    IYY_SF: float  # Iyy (Moment of Inertia, y-axis), default 1.0, optional
    IZZ_SF: float  # Izz (Moment of Inertia, z-axis), default 1.0, optional
    WGT_SF: float  # Weight, default 1.0, optional


class ElementStiffnessScaleFactorPayload(TypedDict):
    """docs/manual/04_DB_Properties.md #31 — /db/ESSF. Keyed by element id."""

    ITEMS: List[ElementStiffnessScaleFactorItem]


class ElementStiffnessScaleFactor(DbResource):
    ENDPOINT = "/db/ESSF"
    NAME = "Element Stiffness Scale Factor"
    PRODUCTS = frozenset({"gen", "civil"})


class FiberDivisionColor(TypedDict, total=False):
    R: int  # default 0, optional
    G: int  # default 0, optional
    B: int  # default 0, optional


class FiberDivisionBaseItem(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #29 — /db/FIBR "FIBR_BASE[]" entry.

    ⚠️ 2026-08-27: `FIBR_BASE_KEY` was typed `bool` here; the manual's own
    Specifications table (article id `35944476555801`) and its Request
    Example (`"FIBR_BASE_KEY": 752`) both show it as an **Integer** fiber
    identifier, not a flag. Live-confirmed the same day: `GET
    /info/db/FIBR` on a connected Gen NX session reports
    `FIBR_BASE_KEY`'s JSON-schema type as `"integer"` (see
    `FiberDivision.info()`), matching the manual and contradicting the
    previous `bool` typing. Changed `bool` -> `int`. The other 8 fields
    (REBAR_NAME/AREA/CENTER_Y/CENTER_Z/FIBER_MATL_ID/AREA_CONSIDER_REBAR/
    OPT_IS_REBAR/POINT_Y/POINT_Z) were entirely missing and are added here
    from the same manual table; their presence and types were cross-checked
    against the same live `/info/db/FIBR` response but not round-tripped
    with real fiber data.
    """

    FIBR_BASE_KEY: int  # Fiber Base Key, required. Corrected from bool 2026-08-27 -- see docstring.
    REBAR_NAME: str  # Rebar Name, required (blank string when not a rebar fiber)
    AREA: float  # Area, required
    CENTER_Y: float  # Center Y, required
    CENTER_Z: float  # Center Z, required
    FIBER_MATL_ID: float  # Index into FIMP_NAME/FIMP_COLOR (which of the 6 materials), required
    AREA_CONSIDER_REBAR: float  # Area Consider Rebar, required
    OPT_IS_REBAR: bool  # Is Rebar, required
    POINT_Y: List[float]  # Fiber outline polygon, Point Y list, required
    POINT_Z: List[float]  # Fiber outline polygon, Point Z list, required


class FiberDivisionPayload(TypedDict, total=False):
    """docs/manual/04_DB_Properties.md #29 — /db/FIBR Specifications table.

    ⚠️ 2026-08-27: `OPT_MONITORED_FIBER`/`MONITORED_FIBER` (monitored-fiber
    selection, both required per the manual) were entirely missing here;
    added. See FiberDivisionBaseItem's docstring for the FIBR_BASE_KEY type
    correction and the other FIBR_BASE[] fields added in the same pass.
    """

    NAME: str  # Fiber Division Name, required
    SECT_KEY: int  # Assigned Section ID (/db/SECT id), required
    ASSIGN_TYPE: int  # required
    FIMP_NAME: List[str]  # Inelastic Material Properties Name, 6 entries (/db/FIMP names), required
    FIMP_COLOR: List[FiberDivisionColor]  # 6 entries, optional
    FIBR_BASE: List[FiberDivisionBaseItem]  # Fiber Division Base Data, required
    OPT_MONITORED_FIBER: bool  # Use Monitored Fiber, required
    MONITORED_FIBER: List[int]  # 0/1 flag per FIBR_BASE entry, required


class FiberDivision(DbResource):
    ENDPOINT = "/db/FIBR"
    NAME = "Fiber Division of Section"
    PRODUCTS = frozenset({"gen", "civil"})
