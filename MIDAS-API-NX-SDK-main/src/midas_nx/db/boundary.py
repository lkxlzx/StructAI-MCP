"""Source: docs/manual/05_DB_Boundary.md, items 1-24."""
from __future__ import annotations

from typing import Any, List, TypedDict

from .base import GEN_ONLY, HYPER_S_ONLY, NO_DELETE_METHODS, DbResource, ItemGroupFields


class ConstraintItem(ItemGroupFields, total=False):
    """One entry of the /db/CONS "ITEMS" array.

    The 7-character length is enforced, and the two failure modes differ.
    Verified live 2026-07-26 on Civil NX 2026 **v2.1 and v2.2 alike**:
    6 characters is rejected with "[Error] Constraint Condition has(have) been
    incorrectly entered.", while 8 characters is *accepted and silently
    truncated* to the first 7. So a too-long string gives you a support you
    never asked for, with no error to notice.

    Worse than it first looked: the POST **response echoes the 8-character
    string back** while the stored record holds 7, so the immediate response
    cannot be used to detect it either. Only a follow-up GET shows the
    truncation. Check the length yourself before sending.
    """

    CONSTRAINT: str  # [DX,DY,DZ,RX,RY,RZ,RW] 7-char string, "1"=fixed "0"=free, required


class ConstraintPayload(TypedDict):
    """docs/manual/05_DB_Boundary.md #1 — /db/CONS Specifications table.

    Keyed by node id, e.g. {"1": {"ITEMS": [{"ID": 1, "CONSTRAINT": "1111111"}]}}.
    """

    ITEMS: List[ConstraintItem]


class Constraint(DbResource):
    ENDPOINT = "/db/CONS"
    NAME = "Constraint Support"
    PRODUCTS = frozenset({"gen", "civil"})


class PointSpringItem(ItemGroupFields, total=False):
    """One entry of the /db/NSPR "ITEMS" array.

    LINEAR uses SDR/F_S/DAMPING/Cr; COMP/TENS use STIFF/DIR/DV; MULTI uses
    FUNCTION/DIR/DV.

    ⚠️ Corrected 2026-08-27 per the sibling manual repo's re-verification
    (live-confirmed on Gen NX the same day): the previous version of this
    TypedDict conflated all three of COMP/TENS/MULTI into one made-up
    DIR(1-4)/DV/SK shape. Real behavior: `POST /db/NSPR` with
    `{"DIR": 4, "DV": [0,0,0], "SK": [2000.0, 0.0, 0.0]}` (the old shape)
    answers `"[Error] Point Spring value has(have) been incorrectly
    entered."`; `{"DIR": 6, "DV": [0,-1,-1], "STIFF": 2000000.0}` (the
    real shape below) round-trips cleanly. `SK` doesn't exist as a field
    at all -- COMP/TENS use a single `STIFF` number, MULTI uses `FUNCTION`
    (an `/db/MLFC` id) instead. `DIR` is 0-6 (six signed axis directions
    plus Vector), not 1-4; `DV` is only meaningful/required when `DIR=6`,
    confirmed via a clean round-trip with `DIR=0` and no `DV` at all.
    `Cr` (LINEAR's per-DOF damping array) was previously missing entirely
    -- confirmed live via a clean round-trip.
    """

    TYPE: str  # "LINEAR" / "COMP" / "TENS" / "MULTI", required
    FormType: int  # 0=Point spring function, 1=Surface spring function; default 0
    # LINEAR only
    SDR: List[float]  # Spring Stiffness [SDx,SDy,SDz,SRx,SRy,SRz], required
    F_S: List[bool]  # Fixed Option [SDx,SDy,SDz,SRx,SRy,SRz], default false
    DAMPING: bool  # Use Damping Constant, default false, optional
    Cr: List[float]  # Damping [Cx,Cy,Cz,CRx,CRy,CRz], default 0, optional
    # COMP / TENS only
    STIFF: float  # Stiffness, required
    # COMP / TENS / MULTI
    DIR: int  # Dx(+)=0/Dx(-)=1/Dy(+)=2/Dy(-)=3/Dz(+)=4/Dz(-)=5/Vector=6, required
    DV: List[float]  # Normal Vector [x,y,z], required if DIR=6, default 0
    # MULTI only
    FUNCTION: int  # Force-Deformation function id (from /db/MLFC), required


class PointSpringPayload(TypedDict):
    """docs/manual/05_DB_Boundary.md #2 — /db/NSPR. Keyed by node id."""

    ITEMS: List[PointSpringItem]


class PointSpring(DbResource):
    ENDPOINT = "/db/NSPR"
    NAME = "Point Spring"
    PRODUCTS = frozenset({"gen", "civil"})


class GeneralSpringTypePayload(TypedDict, total=False):
    """docs/manual/05_DB_Boundary.md #3 — /db/GSTP Specifications table.

    SPRING/MASS/DAMPING are 21-value symmetric 6x6 matrices (each valid
    only when its matching OPT_* flag is true), but **not** in simple
    upper-triangular row order. Live-confirmed 2026-08-27 on Gen NX by
    sending a probe spring with a unique value 11-31 at each of the 21
    indices and reading the values back off the General Spring Type
    dialog's 6x6 grid (SDx/SDy/SDz/SRx/SRy/SRz): the real order is
    **diagonal terms first, then off-diagonal terms row by row**:

    - idx 0-5:   diagonal (1,1)..(6,6) — i.e. Kxx, Kyy, Kzz, Krxrx, Kryry, Krzrz
    - idx 6-10:  row 1 off-diagonal — (1,2), (1,3), (1,4), (1,5), (1,6)
    - idx 11-14: row 2 off-diagonal — (2,3), (2,4), (2,5), (2,6)
    - idx 15-17: row 3 off-diagonal — (3,4), (3,5), (3,6)
    - idx 18-19: row 4 off-diagonal — (4,5), (4,6)
    - idx 20:    row 5 off-diagonal — (5,6)

    This SDK previously documented plain upper-triangular row order (K11,
    K12, K13, K14, K15, K16, K22, K23, ...) — confirmed wrong by the same
    test (index 1 showed up as Kyy on the diagonal, not K12). Anyone who
    filled the array by the old convention put stiffness at the wrong
    degrees of freedom. Only SPRING (OPT_STIFFNESS) was tested directly
    against the GUI; MASS/DAMPING are assumed to share the same layout
    (the manual documents all three identically) but weren't
    independently confirmed.
    """

    NAME: str  # General Spring Name, required
    OPT_STIFFNESS: bool  # default false, optional
    SPRING: List[float]  # Stiffness Matrix (21 values), default 0
    OPT_MASS: bool  # default false, optional
    MASS: List[float]  # Mass Matrix (21 values), default 0
    OPT_DAMPING: bool  # default false, optional
    DAMPING: List[float]  # Damping Matrix (21 values), default 0


class GeneralSpringType(DbResource):
    ENDPOINT = "/db/GSTP"
    NAME = "Define General Spring Type"
    PRODUCTS = frozenset({"gen", "civil"})


class GeneralSpringSupportItem(ItemGroupFields, total=False):
    TYPE_NAME: str  # Defined General Spring Name (from /db/GSTP), required


class GeneralSpringSupportPayload(TypedDict):
    """docs/manual/05_DB_Boundary.md #4 — /db/GSPR. Keyed by node id."""

    ITEMS: List[GeneralSpringSupportItem]


class GeneralSpringSupport(DbResource):
    ENDPOINT = "/db/GSPR"
    NAME = "Assign General Spring Supports"
    PRODUCTS = frozenset({"gen", "civil"})


class SurfaceSpringItem(ItemGroupFields, total=False):
    ELEM_TYPE: str  # "FRAME" / "PLANAR(FACE)" / "PLANAR(EDGE)" / "SOLID", required
    EDGE_FACE: int  # FRAME: Local x=2/y=0/z=1; PLANAR/SOLID: Edge#1-4=0-3; default 0
    WIDTH: float  # FRAME only: tributary width, optional (undocumented in table, seen in example)
    SPRING_TYPE: int  # 0=Linear, 1=Comp.-Only, 2=Tens.-Only; default 0
    MODULUS: float  # Modulus of Subgrade Reaction Ks, required


class SurfaceSpringPayload(TypedDict):
    """docs/manual/05_DB_Boundary.md #5 — /db/SSPS. Keyed by element id."""

    ITEMS: List[SurfaceSpringItem]


class SurfaceSpring(DbResource):
    ENDPOINT = "/db/SSPS"
    NAME = "Surface Spring"
    PRODUCTS = frozenset({"gen", "civil"})


class ElasticLinkPayload(TypedDict, total=False):
    """docs/manual/05_DB_Boundary.md #6 — /db/ELNK Specifications table.

    Extra keys depend on LINK: "GEN" (SDR/R_S/bSHEAR/DR), "RIGID"/"SADDLE"
    (none), "TENS"/"COMP" (SDR, Dx only), "MULTILINEAR" (DIR/MLFC/bSHEAR/
    DRENDI), "RAILINTERACT" (DIR/RLFC/bSHEAR/DRENDI).
    """

    NODE: List[int]  # [i-node, j-node], required
    BNGR_NAME: str  # Boundary Group Name, default "", optional
    ANGLE: float  # Beta Angle, default 0, optional
    LINK: str  # "GEN"/"RIGID"/"SADDLE"/"TENS"/"COMP"/"MULTILINEAR"/"RAILINTERACT", required
    SDR: List[float]  # LINK=GEN/TENS/COMP: Spring Stiffness [SDx,SDy,SDz,SRx,SRy,SRz]
    R_S: List[bool]  # LINK=GEN: Rigid-End Option, default false
    bSHEAR: bool  # LINK=GEN/MULTILINEAR/RAILINTERACT: Consider Shear, optional
    DR: List[float]  # LINK=GEN: [SDy Effective Length ratio, SDz Effective Length ratio]
    DIR: int  # LINK=MULTILINEAR/RAILINTERACT: local direction, required
    MLFC: int  # LINK=MULTILINEAR: Force-Deformation Function id (/db/MLFC), required
    RLFC: int  # LINK=RAILINTERACT: Rail function id, required
    DRENDI: float  # LINK=MULTILINEAR/RAILINTERACT: end-i distance ratio, optional


class ElasticLink(DbResource):
    ENDPOINT = "/db/ELNK"
    NAME = "Elastic Link"
    PRODUCTS = frozenset({"gen", "civil"})


class RigidLinkItem(ItemGroupFields, total=False):
    """ID here is the Master Node id (unlike the generic Serial Number
    elsewhere), but the field shape is the same as ItemGroupFields."""

    DOF: int  # 6-digit DOF flag, digit positions DX(6th)..RZ(1st), e.g. 110001; required
    S_NODE: List[int]  # Slave Node id list, required


class RigidLinkPayload(TypedDict):
    """docs/manual/05_DB_Boundary.md #7 — /db/RIGD. Keyed by master node id."""

    ITEMS: List[RigidLinkItem]


class RigidLink(DbResource):
    ENDPOINT = "/db/RIGD"
    NAME = "Rigid Link"
    PRODUCTS = frozenset({"gen", "civil"})


class GeneralLinkPropertyPayload(TypedDict, total=False):
    """docs/manual/05_DB_Boundary.md #8 — /db/NLLP Specifications table.

    Deeply conditional on (APPLICATION_TYPE, APPLICATION_TYPE_D) — e.g.
    "ELEMENT"/"SPG" (spring), "ELEMENT2"/"VI" (references /db/SDVI by name),
    "FORCE"/"LRBI" (lead rubber bearing isolator), etc.; only the common
    envelope is typed for v1, matching the SECT_I precedent. See the
    manual's APPLICATION_TYPE Combination Table for the full list of
    (APPLICATION_TYPE, APPLICATION_TYPE_D) pairs and their extra keys.

    ⚠️ Added 2026-08-27 per the sibling manual repo's re-verification:
    `DIST_RATIO_DY`/`DIST_RATIO_DZ`/`COUPLED_INPUT_METHOD` were missing
    from the common envelope entirely. Confirmed real via `GET
    /info/db/NLLP` schema introspection on Gen NX the same day (their
    types match the manual: two numbers + one integer). Not confirmed via
    a live POST round trip on either product: `/db/NLLP` writes were
    already a known standing failure before this addition (2026-08-16:
    the manual's own unmodified example answers a generic `"Unknown
    Error"` on both Gen and Civil, seeded or fresh document, `level: read`
    since) -- reconfirmed 2026-08-27 on Civil NX specifically (both with
    and without these new fields, same `"Unknown Error"`, so this addition
    isn't what's blocking it). The schema match from `/info/db/NLLP` is
    the strongest signal available for these fields' shape; the endpoint's
    write path itself is unresolved on both products, unrelated to this
    change.
    """

    PROPERTY_NAME: str  # required
    DESC: str  # optional
    APPLICATION_TYPE: str  # "ELEMENT"/"ELEMENT2"/"FORCE", required
    APPLICATION_TYPE_D: str  # e.g. "SPG"/"DSP"/"SLD"/"VI"/"VE"/"ST"/"HY"/"IS"/"VD"/"GAP"/"HOOK"/"HS"/"LRBI"/"FPSI"/"TFPSI", required
    TOTAL_WEIGHT: float  # Self-Weight (Total), optional
    L_WEIGHT_RATIO: float  # Lumped Weight Ratio, optional
    OPT_USE_MASS: bool  # optional
    TOTAL_MASS: float  # optional
    L_MASS_RATIO: float  # Lumped Mass Ratio, optional
    OPT_SHEAR_SPR_LOC: bool  # Shear Spring Location Option, optional
    DIST_RATIO_DY: float  # Distance Ratio from End I (Dy), optional
    DIST_RATIO_DZ: float  # Distance Ratio from End I (Dz), optional
    COUPLED_INPUT_METHOD: int  # Coupled Input Method, optional


class GeneralLinkProperty(DbResource):
    ENDPOINT = "/db/NLLP"
    NAME = "General Link Properties"
    PRODUCTS = frozenset({"gen", "civil"})


class GeneralLinkPayload(TypedDict, total=False):
    """docs/manual/05_DB_Boundary.md #9 — /db/NLNK Specifications table.

    REF_SYSTEM=0 (element CS) uses BETA_ANGLE; REF_SYSTEM=1 (global CS)
    uses INPUT_METHOD (0=Angle -> ANGLE_VALUES, 1=3 Points -> POINT_VALUES,
    2=Vector -> VECTOR_VALUES).
    """

    NODE1: int  # required
    NODE2: int  # required
    GROUP_NAME: str  # Boundary Group Name, default "", optional
    PROP_NAME: str  # General Link Property Name (/db/NLLP name), required
    IEHP_NAME: str  # Inelastic Hinge Property Name, default "", optional
    REF_SYSTEM: int  # 0=Element, 1=Global; required
    BETA_ANGLE: float  # REF_SYSTEM=0, default 0, optional
    INPUT_METHOD: int  # REF_SYSTEM=1: 0=Angle, 1=3 Points, 2=Vector; required
    ANGLE_VALUES: Any  # INPUT_METHOD=0: [{"VALUE": [about X, about y', about z'']}]
    POINT_VALUES: Any  # INPUT_METHOD=1: [P0[3], P1[3], P2[3]]
    VECTOR_VALUES: Any  # INPUT_METHOD=2: [V1[3], V2[3]]


class GeneralLink(DbResource):
    ENDPOINT = "/db/NLNK"
    NAME = "General Link"
    PRODUCTS = frozenset({"gen", "civil"})


class GeneralLinkHyperSPayload(TypedDict, total=False):
    """docs/manual/05_DB_Boundary.md #10 — /db/NLNK-M1 (Hyper-S solver only).

    ⚠️ Rewritten 2026-08-27 per the sibling manual repo's re-verification.
    The previous version of this TypedDict was a 3-field stub written when
    the manual said no JSON schema example existed for this endpoint; the
    re-verified manual chapter found a full spec (928-line source article)
    that turned out to be almost identical to `/db/NLNK` (this same file's
    `GeneralLinkPayload`, item #9) — same REF_SYSTEM/INPUT_METHOD branching,
    same ANGLE_VALUES/POINT_VALUES/VECTOR_VALUES shapes — with only
    `IEHP_NAME` (Inelastic Hinge Property Name) absent.

    Schema fully confirmed 2026-08-27 on Civil NX: `GET /info/db/NLNK-M1`
    lists exactly these 10 properties (`NODE1`/`NODE2`/`GROUP_NAME`/
    `PROP_NAME`/`REF_SYSTEM`/`BETA_ANGLE`/`INPUT_METHOD`/`VECTOR_VALUES`/
    `ANGLE_VALUES`/`POINT_VALUES`), confirming `IEHP_NAME` really is absent
    server-side too. A live POST round trip was attempted (`REF_SYSTEM=0`,
    against two real nodes) but answered `"Unknown Error"` -- almost
    certainly because `PROP_NAME` couldn't reference a real `/db/NLLP`
    property: `/db/NLLP` writes are themselves a separate, already-known
    standing failure on both products (see `GeneralLinkPropertyPayload`'s
    docstring above), so this endpoint's own write path was never actually
    exercised. Confirmed via a bisection sweep the same day: every
    `/db/NLLP` payload tried, down to a single `{"PROPERTY_NAME": "..."}`
    field, answers the identical `"Unknown Error"` -- it's not something a
    different `NLNK-M1` payload could route around. This isn't a new
    problem either: the legacy `GeneralLinkPayload`'s own docstring
    already recorded (2026-08-16) that its write test was scaffolded but
    never run for the exact same reason. Shape is schema-confirmed; the
    round trip is blocked by that unrelated upstream issue, not evidence
    against this shape.
    """

    PROP_NAME: str  # General Link Property Name (/db/NLLP name), required
    NODE1: int  # required
    NODE2: int  # required
    GROUP_NAME: str  # Boundary Group Name, default "", optional
    REF_SYSTEM: int  # 0=Element, 1=Global; required
    BETA_ANGLE: float  # REF_SYSTEM=0, default 0, required
    INPUT_METHOD: int  # REF_SYSTEM=1: 0=Angle, 1=3 Points, 2=Vector; required
    ANGLE_VALUES: Any  # INPUT_METHOD=0: [{"VALUE": [about X, about y', about z'']}]
    POINT_VALUES: Any  # INPUT_METHOD=1: [P0[3], P1[3], P2[3]]
    VECTOR_VALUES: Any  # INPUT_METHOD=2: [V1[3], V2[3]]


class GeneralLinkHyperS(DbResource):
    ENDPOINT = "/db/NLNK-M1"
    NAME = "General Link (Hyper-S)"
    PRODUCTS = HYPER_S_ONLY


class ChangeGeneralLinkPropertyPayload(TypedDict, total=False):
    """docs/manual/05_DB_Boundary.md #11 — /db/CGLP Specifications table."""

    GLINK_KEY: int  # General Link element id, required
    CHANGE_PROPERTY_NAME: str  # Property name defined in /db/NLLP, required
    GROUP_NAME: str  # Boundary Group Name, default "", optional


class ChangeGeneralLinkProperty(DbResource):
    ENDPOINT = "/db/CGLP"
    NAME = "Change General Link Property"
    PRODUCTS = frozenset({"gen", "civil"})


class BeamEndReleaseItem(ItemGroupFields, total=False):
    bVALUE: bool  # false=Relative, true=Value; default false
    FLAG_I: str  # 7-char release flags [Fx,Fy,Fz,Mx,My,Mz,Mb] for i-node, required
    VALUE_I: List[float]  # Partial Fixity for i-node, default 0
    FLAG_J: str  # 7-char release flags [Fx,Fy,Fz,Mx,My,Mz,Mb] for j-node, required
    VALUE_J: List[float]  # Partial Fixity for j-node, default 0


class BeamEndReleasePayload(TypedDict):
    """docs/manual/05_DB_Boundary.md #12 — /db/FRLS. Keyed by element id."""

    ITEMS: List[BeamEndReleaseItem]


class BeamEndRelease(DbResource):
    ENDPOINT = "/db/FRLS"
    NAME = "Beam End Release"
    PRODUCTS = frozenset({"gen", "civil"})


class BeamEndOffsetItem(ItemGroupFields, total=False):
    """TYPE="GLOBAL" uses RGDXi/RGDYi/RGDZi/RGDXj/RGDYj/RGDZj (GCS);
    TYPE="ELEMENT" reuses RGDYi/RGDZi/RGDYj/RGDZj but in ECS (no X component).
    """

    TYPE: str  # "GLOBAL" / "ELEMENT", required
    RGDXi: float  # TYPE=GLOBAL only, default 0, optional
    RGDYi: float  # default 0, optional
    RGDZi: float  # default 0, optional
    RGDXj: float  # TYPE=GLOBAL only, default 0, optional
    RGDYj: float  # default 0, optional
    RGDZj: float  # default 0, optional


class BeamEndOffsetPayload(TypedDict):
    """docs/manual/05_DB_Boundary.md #13 — /db/OFFS. Keyed by element id."""

    ITEMS: List[BeamEndOffsetItem]


class BeamEndOffset(DbResource):
    ENDPOINT = "/db/OFFS"
    NAME = "Beam End Offsets"
    PRODUCTS = frozenset({"gen", "civil"})


class PlateEndReleaseItem(ItemGroupFields, total=False):
    N1: List[int]  # Position N1 [Fx,Fy,Fz,Mx,My], 1=released, required
    N2: List[int]  # Position N2 [Fx,Fy,Fz,Mx,My], required
    N3: List[int]  # Position N3 [Fx,Fy,Fz,Mx,My], required
    N4: List[int]  # Position N4 [Fx,Fy,Fz,Mx,My], required


class PlateEndReleasePayload(TypedDict):
    """docs/manual/05_DB_Boundary.md #14 — /db/PRLS. Keyed by element id."""

    ITEMS: List[PlateEndReleaseItem]


class PlateEndRelease(DbResource):
    ENDPOINT = "/db/PRLS"
    NAME = "Plate End Release"
    PRODUCTS = frozenset({"gen", "civil"})


class ForceDeformationFunctionItem(TypedDict, total=False):
    X: float  # Displacement (m) or Rotation (rad), required
    Y: float  # Force (kN) or Moment (kN.m), required


class ForceDeformationFunctionPayload(TypedDict, total=False):
    """docs/manual/05_DB_Boundary.md #15 — /db/MLFC Specifications table."""

    NAME: str  # Function Name, required
    TYPE: str  # "FORCE" / "MOMENT", default "MOMENT", optional
    SYMM: bool  # Symmetric, default false, optional
    FUNC_ID: int  # default 0, optional
    ITEMS: List[ForceDeformationFunctionItem]  # required


class ForceDeformationFunction(DbResource):
    ENDPOINT = "/db/MLFC"
    NAME = "Force-Deformation Function"
    PRODUCTS = frozenset({"gen", "civil"})


class SeismicDeviceCommon(TypedDict, total=False):
    """Shared "COMMON" sub-object of the SDVI/SDVE/SDST/SDHY/SDIS seismic
    device endpoints."""

    NAME: str  # required
    DESC: str  # optional
    INPUT_METHOD: int  # 0=User Input, 1=Reference DB; required
    COMPANY: str  # required
    PRODUCT_NAME: str  # required
    TYPE_NUMBER: str  # required


class SeismicDeviceViscousDamperItem(TypedDict, total=False):
    """One entry of `/db/SDVI`'s `ITEM` array (one per DOF, 6 entries).

    ⚠️ Added 2026-08-27 per the sibling manual repo's re-verification
    (live-confirmed via a clean POST/GET/DELETE round trip on Gen NX the
    same day, sent with `DASHPOT_TYPE=2` i.e. Exponential): the six
    `EXFN_*`/`OPT_EXFN_CE` fields below were previously missing entirely.
    Per the manual's own Request Example, **all 12 fields are sent on
    every item regardless of `DASHPOT_TYPE`** — the server didn't reject
    the Exponential-only fields when `DASHPOT_TYPE` was Linear Elastic or
    Bilinear in ad-hoc testing either, so send the full set unconditionally
    rather than branching on `DASHPOT_TYPE` client-side.
    """

    OPT_DOF: bool  # DOF enabled, required
    CE: float  # Initial Damping Coefficient, required
    P1: float  # Max Damping Force, required
    C1: float  # Secondary Damping Coefficient, required
    ALPHA1: float  # Damping Exponent, required
    K0: float  # Initial Stiffness, required
    EXFN_PY: float  # Exponential: Damping Force, required
    EXFN_VY: float  # Exponential: Reference Velocity, required
    EXFN_DE: float  # Exponential: Damping Exponent, required
    EXFN_DC: float  # Exponential: Damping Coefficient, required
    OPT_EXFN_CE: bool  # Exponential: Use Initial Damping Coefficient, required
    EXFN_CE: float  # Exponential: Initial Damping Coefficient value, required


class SeismicDeviceViscousDamperPayload(TypedDict, total=False):
    """docs/manual/05_DB_Boundary.md #16 — /db/SDVI Specifications table.

    ⚠️ `INPUT_TYPE_EXFN` added 2026-08-27 per the sibling manual repo's
    re-verification — live-confirmed via the same round trip as
    :class:`SeismicDeviceViscousDamperItem`'s `EXFN_*` fields.
    """

    COMMON: SeismicDeviceCommon  # required
    DEVICE_TYPE: str  # optional
    DAMPER_TYPE: int  # 0=Single Dashpot, 1=Kelvin(Voigt), 2=Maxwell; required
    DASHPOT_TYPE: int  # 0=Linear Elastic, 1=Bilinear, 2=Exponential; required
    INPUT_TYPE: int  # 0=Damping ratio alpha1, 1=Damping constant C1; required
    INPUT_TYPE_EXFN: int  # Input Type for Exponential Function Type, required
    ITEM: List[SeismicDeviceViscousDamperItem]  # 6 entries, one per DOF; required


class SeismicDeviceViscousDamper(DbResource):
    ENDPOINT = "/db/SDVI"
    NAME = "Seismic Device – Viscous/Oil Damper"
    PRODUCTS = frozenset({"gen", "civil"})


class SeismicDeviceViscoelasticDamperPayload(TypedDict, total=False):
    """docs/manual/05_DB_Boundary.md #17 — /db/SDVE Specifications table.

    ⚠️ Rewritten 2026-08-27 per the sibling manual repo's re-verification
    (live-confirmed via a clean POST/GET/DELETE round trip on Gen NX the
    same day): this TypedDict previously had only `COMMON`/`MATERIAL_TYPE`/
    `SHEAR_AREA`. The manual's Specifications table itself only lists those
    same 3 as "documented", but its own Request Example sends 14 more
    fields alongside them — confirmed real by the round trip, not just by
    the table.
    """

    COMMON: SeismicDeviceCommon  # required
    MATERIAL_TYPE: str  # "GR100"/"GR300"/"SR05"/"GR400"/"CST"/"TRC", required
    SHEAR_AREA: float  # required
    THICKNESS: float  # required
    MULTIPL: float  # Multiplier, required
    DIR: str  # Direction, e.g. "Dx", required
    FREQ: float  # Frequency, required
    STIFF_FACTOR: float  # Stiffness Factor, required
    DAMP_FACTOR: float  # Damping Factor, required
    REF_T: float  # Reference Temperature, required
    LIMIT_DEF: float  # Limit Deformation, required
    EFF_STIFF: float  # Effective Stiffness, required
    EQUI_DAMP: float  # Equivalent Damping, required
    OPT_MOUNT_STIFF: bool  # Use Mount Stiffness, required
    MOUNT_STIFF: float  # Mount Stiffness, required
    OPT_KINETIC_FRIC: bool  # Use Kinetic Friction, required
    KINETIC_FRIC: float  # Kinetic Friction, required


class SeismicDeviceViscoelasticDamper(DbResource):
    ENDPOINT = "/db/SDVE"
    NAME = "Seismic Device – Viscoelastic Damper"
    PRODUCTS = frozenset({"gen", "civil"})


class SeismicDeviceSteelDamperBL2(TypedDict, total=False):
    BETA: float  # Exponent in Unloading Stiffness Calculation, required


class SeismicDeviceSteelDamperLY2(TypedDict, total=False):
    ALPHA2: float  # Stiffness Factor, required
    THETA: float  # Strength Factor, required


class SeismicDeviceSteelDamperLY3(TypedDict, total=False):
    ALPHA2: float  # Stiffness Factor, required
    THETA: float  # Strength Factor, required
    GAMMA: float  # Stiffness Ratio, required


class SeismicDeviceSteelDamperIK2(TypedDict, total=False):
    GAMMA: float  # Isotropic Factor, required


class SeismicDeviceSteelDamperPayload(TypedDict, total=False):
    """docs/manual/05_DB_Boundary.md #18 — /db/SDST Specifications table.

    ⚠️ Rewritten 2026-08-27 per the sibling manual repo's re-verification.
    The manual repo's own re-verification found the *official* SDST
    Specifications table lists `MATERIAL_TYPE` ("GR100" etc.) and
    `MULTIPL` — fields that actually belong to the sibling SDVE
    (Viscoelastic Damper) page, apparently cross-contaminated in the
    vendor's source docs. Neither field appears in this endpoint's JSON
    Schema or Request Example. Confirmed independently here: `GET
    /info/db/SDST` on Gen NX (2026-08-27) returns no `MATERIAL_TYPE`/
    `MULTIPL` properties at all, and lists exactly `K0`/`P1`/`ALPHA1`/`KB`
    plus the four hysteresis-model sub-objects below. `K0`/`P1`/`ALPHA1`/
    `KB` and the `"BL2"` sub-object were additionally confirmed via a
    clean live POST/GET/DELETE round trip the same day; `LY2`/`LY3`/`IK2`
    are schema-confirmed only (not round-tripped with a real POST).
    """

    COMMON: SeismicDeviceCommon  # required
    DIR: str  # Direction, e.g. "Dx", required
    SDST_HYS_MODEL: str  # "BL2"/"LY2"/"LY3"/"IK2", required
    K0: float  # Initial Stiffness, required
    P1: float  # Yield Strength, required
    ALPHA1: float  # Stiffness Factor, required
    KB: float  # Mounting Parts Stiffness, required
    BL2: SeismicDeviceSteelDamperBL2  # present when SDST_HYS_MODEL="BL2"
    LY2: SeismicDeviceSteelDamperLY2  # present when SDST_HYS_MODEL="LY2"
    LY3: SeismicDeviceSteelDamperLY3  # present when SDST_HYS_MODEL="LY3"
    IK2: SeismicDeviceSteelDamperIK2  # present when SDST_HYS_MODEL="IK2"


class SeismicDeviceSteelDamper(DbResource):
    ENDPOINT = "/db/SDST"
    NAME = "Seismic Device – Steel Damper"
    PRODUCTS = frozenset({"gen", "civil"})


class SeismicDeviceHystereticIsolatorPayload(TypedDict, total=False):
    """docs/manual/05_DB_Boundary.md #19 — /db/SDHY Specifications table.

    ⚠️ Rewritten 2026-08-27 per the sibling manual repo's 2026-08-25
    re-verification (article id `35948292269977`): P1/P2/ALPHA1/ALPHA2/
    BETA/Phi/LAMBDA were missing entirely. Live-confirmed via a clean
    POST/GET/DELETE round trip on Gen NX the same day, using the manual's
    own worked example values (SDHY_HYS_MODEL="DegradingBiLinear"). The
    manual's own table also lists a `MULTIPL` field that appears in neither
    its JSON Schema nor Request Example (the same cross-contamination
    pattern found on SDST/SDVE) — deliberately left out here too.
    """

    COMMON: SeismicDeviceCommon  # required
    SDHY_HYS_MODEL: str  # e.g. "DegradingBiLinear", required
    MSS: int  # Number of Shear Springs, required
    K0: float  # Initial Stiffness, required
    P1: float  # Yield Strength, required
    P2: float  # 2nd Yield Strength, required
    ALPHA1: float  # Stiffness Factor, required
    ALPHA2: float  # 2nd Stiffness Factor, required
    BETA: float  # Exponent in Unloading Stiffness Calculation, required
    Phi: float  # required
    LAMBDA: float  # required


class SeismicDeviceHystereticIsolator(DbResource):
    ENDPOINT = "/db/SDHY"
    NAME = "Seismic Device – Hysteretic Isolator (MSS)"
    #: Gen-only: 404 (route + /info) on Civil NX, confirmed independently
    #: twice on 2026-07-29 — see db/base.py's GEN_ONLY docstring.
    PRODUCTS = GEN_ONLY


class SeismicDeviceIsolatorVerticalDX(TypedDict, total=False):
    """LRB/NRB's nested "DX" (Vertical Direction Properties) object. All optional."""

    OPT_CONS_NONL: bool  # Use Consider Vertical Direction Nonlinearity, optional
    BETA: float  # Tensile Stiffness Reduction Factor, optional
    ALPHA: float  # Tensile Stiffness Reduction Ratio, optional
    SIGMA_V: float  # Tensile Limit Strength, optional


class SeismicDeviceIsolatorLRB(TypedDict, total=False):
    """SDIS_DEV_TYPE="LRB" data object."""

    SDIS_HYS_MODEL: str  # Hysteresis Model, required
    KE: float  # Initial Stiffness (Ke), required
    AR: float  # Rubber Cross Section Area, required
    TR: float  # Total Thickness of Rubber, required
    K0: float  # Initial Stiffness (K0, distinct from KE), required
    K2: float  # 2nd Stiffness, required
    QD: float  # Characteristic Strength, required
    DX: SeismicDeviceIsolatorVerticalDX  # optional


class SeismicDeviceIsolatorNRB(TypedDict, total=False):
    """SDIS_DEV_TYPE="NRB" data object."""

    AR: float  # Rubber Cross Section Area, required
    TR: float  # Total Thickness of Rubber, required
    KH: float  # Horizontal Stiffness, required
    DX: SeismicDeviceIsolatorVerticalDX  # optional


class SeismicDeviceIsolatorSB(TypedDict, total=False):
    """SDIS_DEV_TYPE="SLD" data object (keyed "SB")."""

    AS: float  # Area of Sliding Head, required
    K0: float  # Initial Stiffness, required
    QD: int  # Index Qd, required
    Pi_VALUE: float  # Pi, required
    MU0: float  # Frictional Factor, required


class SeismicDeviceIsolatorPayload(TypedDict, total=False):
    """docs/manual/05_DB_Boundary.md #20 — /db/SDIS Specifications table.

    Exactly one of LRB/NRB/SB is present, matching SDIS_DEV_TYPE
    ("LRB"/"NRB"/"SLD") — left as Any for v1, matching SECT_I precedent.

    ⚠️ Rewritten 2026-08-27 per the sibling manual repo's 2026-08-25 full
    rewrite (article id `35948330042649`), which corrected five errors in
    its own previous copy: (1) `SDIS_DEV_TYPE`'s third value is `"SLD"`,
    not `"SB"` — `"SB"` is only the *data object's* key; (2) LRB's
    `OPT_CONS_NONL`/`BETA`/`ALPHA`/`SIGMA_V` are nested one level down
    inside a `DX` sub-object, not siblings of `KE`/`AR`/`TR`; (3) LRB has
    two distinct initial-stiffness fields, `KE` and `K0` — `K0` was missing
    entirely; (4) NRB has `AR`/`TR`/`KH`/`DX` (4 fields + the same nested
    `DX`), not just `KH`; (5) SB's `QD`(Index)/`Pi_VALUE` were missing.
    Live-confirmed 2026-08-27 on Gen NX: `SB` (SDIS_DEV_TYPE="SLD") via a
    clean POST/GET/DELETE round trip with the manual's own worked example.
    `LRB` was schema-confirmed via `GET /info/db/SDIS` (which matches this
    shape exactly, `DX` nesting included) but a POST attempt with the
    manual's own example answered `"Wrong Field"` — per this project's
    established pattern that usually means an unrecognized *value* (here,
    likely `SDIS_HYS_MODEL="BiLinear"`), not a wrong field name/shape; the
    schema match is the stronger signal. `NRB` is manual-sourced only,
    neither round-tripped nor schema-diffed this session.
    """

    COMMON: SeismicDeviceCommon  # required
    SDIS_DEV_TYPE: str  # "LRB" / "NRB" / "SLD" (data still keyed "SB"), required
    MSS: int  # Number of Shear Springs, required
    TAU_K: float  # Adjustment Parameter tau_k, required
    TAU_Q: float  # Adjustment Parameter tau_q, required
    KV: float  # Vertical Stiffness, required
    LRB: SeismicDeviceIsolatorLRB  # required when SDIS_DEV_TYPE="LRB"
    NRB: SeismicDeviceIsolatorNRB  # required when SDIS_DEV_TYPE="NRB"
    SB: SeismicDeviceIsolatorSB  # required when SDIS_DEV_TYPE="SLD"


class SeismicDeviceIsolator(DbResource):
    ENDPOINT = "/db/SDIS"
    NAME = "Seismic Device – Isolator (MSS)"
    #: Gen-only: 404 (route + /info) on Civil NX, confirmed independently
    #: twice on 2026-07-29 — see db/base.py's GEN_ONLY docstring.
    PRODUCTS = GEN_ONLY


class LinearConstraintSlaveExplicit(TypedDict, total=False):
    """SLAVES[] entry when the owning LinearConstraintItem.TYPE == "EX"."""

    NODE_KEY: int  # required
    COEFF: float  # Coefficient, required
    DOF: int  # Degree of Freedom: DX=0/DY=1/DZ=2/RX=3/RY=4/RZ=5, required


class LinearConstraintSlaveWeighted(TypedDict, total=False):
    """SLAVES[] entry when the owning LinearConstraintItem.TYPE == "WD"."""

    NODE_KEY: int  # required
    WEIGHT: float  # required


class LinearConstraintItem(ItemGroupFields, total=False):
    """docs/manual/05_DB_Boundary.md #21 — /db/MCON ITEMS[] entry.

    ⚠️ 2026-08-27: the manual's own 2026-08-25 re-verification (article id
    `35948507217689`) corrected SLAVES[]'s shape: it previously documented
    both TYPE values as using COEFF, but they don't share a shape — "EX"
    (Explicit) uses NODE_KEY+COEFF+DOF (one DOF per slave entry), "WD"
    (Weighted Displacement) uses NODE_KEY+WEIGHT only. Live-confirmed
    2026-08-27 via two separate POST/GET/DELETE round trips on Gen NX
    (one per TYPE), using the manual's own worked example values.
    """

    SLAVE_TYPE: str  # 6-char DOF flag (DX..RZ) of the constrained node, required
    TYPE: str  # "EX"=Explicit, "WD"=Weighted Displacement; required
    SLAVES: List[Any]  # List[LinearConstraintSlaveExplicit] if TYPE="EX", List[LinearConstraintSlaveWeighted] if TYPE="WD"; required


class LinearConstraintPayload(TypedDict):
    """docs/manual/05_DB_Boundary.md #21 — /db/MCON. Keyed by (slave) node id."""

    ITEMS: List[LinearConstraintItem]


class LinearConstraint(DbResource):
    ENDPOINT = "/db/MCON"
    NAME = "Linear Constraints"
    PRODUCTS = frozenset({"gen", "civil"})


class PanelZoneEffectPayload(TypedDict, total=False):
    """docs/manual/05_DB_Boundary.md #22 — /db/PZEF Specifications table."""

    OPT_OFFSET: bool  # Auto Calculate Panel Zone Offset Distances, required
    OFFS_FACTOR: float  # Offset Factor, required
    OUTPUT_POSITION: int  # required


class PanelZoneEffect(DbResource):
    ENDPOINT = "/db/PZEF"
    NAME = "Panel Zone Effects"
    PRODUCTS = frozenset({"gen", "civil"})
    METHODS = NO_DELETE_METHODS


class ConstraintLabelDirectionPayload(TypedDict, total=False):
    """docs/manual/05_DB_Boundary.md #23 — /db/CLDR. Keyed by node id.

    DIR: Local x(+)=0, Local x(-)=1, Local y(+)=2, Local y(-)=3,
    Local z(+)=4, Local z(-)=5.
    """

    DIR: int  # required


class ConstraintLabelDirection(DbResource):
    ENDPOINT = "/db/CLDR"
    NAME = "Define Constraints Label Direction"
    PRODUCTS = frozenset({"gen", "civil"})
    METHODS = NO_DELETE_METHODS


class DiaphragmDisconnect(DbResource):
    """docs/manual/05_DB_Boundary.md #24 — /db/DRLS.

    Excludes nodes from an active diaphragm constraint; payload is an empty
    object per node id, e.g. ``DiaphragmDisconnect.create({1: {}, 2: {}})``.
    """

    ENDPOINT = "/db/DRLS"
    NAME = "Diaphragm Disconnect"
    #: Gen-only: 404 (route + /info) on Civil NX, confirmed independently
    #: twice on 2026-07-29 — see db/base.py's GEN_ONLY docstring.
    PRODUCTS = GEN_ONLY
