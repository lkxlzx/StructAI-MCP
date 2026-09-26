"""Source: docs/manual/06_DB_Static_Loads.md, items 1-21."""
from __future__ import annotations

from typing import Any, List, Optional, TypedDict

from ..client import MidasClient, MidasRequestError
from .base import GEN_ONLY, DbResource, ItemGroupFields


class StaticLoadCasePayload(TypedDict, total=False):
    """docs/manual/06_DB_Static_Loads.md #1 — /db/STLD Specifications table.

    TYPE is one of ~67 documented load-type codes (e.g. "D" Dead Load,
    "L" Live Load, "W" Wind Load, "E" Earthquake, "PS" Prestress, ...) —
    see the manual's full Load Type table for the complete list.
    """

    NO: int  # Ordering Index in GUI, read-only (returned by GET, not accepted on write)
    NAME: str  # Load Case Name, required
    TYPE: str  # Load Type code, required
    DESC: str  # Description, default "", optional


class StaticLoadCase(DbResource):
    ENDPOINT = "/db/STLD"
    NAME = "Static Load Cases"
    PRODUCTS = frozenset({"gen", "civil"})


class SelfWeightPayload(TypedDict, total=False):
    """docs/manual/06_DB_Static_Loads.md #2 — /db/BODF Specifications table."""

    LCNAME: str  # Load Case Name, required
    GROUP_NAME: str  # Load Group Name, default "", optional
    FV: List[float]  # Self-Weight Factor [X, Y, Z], required, e.g. [0, 0, -1]


class SelfWeight(DbResource):
    ENDPOINT = "/db/BODF"
    NAME = "Self-Weight"
    PRODUCTS = frozenset({"gen", "civil"})


class NodalLoadItem(ItemGroupFields, total=False):
    """One entry of the /db/CNLD "ITEMS" array."""

    LCNAME: str  # Load Case Name, required
    FX: float
    FY: float
    FZ: float
    MX: float
    MY: float
    MZ: float


class NodalLoadPayload(TypedDict):
    """docs/manual/06_DB_Static_Loads.md #3 — /db/CNLD. Keyed by node id."""

    ITEMS: List[NodalLoadItem]


class NodalLoad(DbResource):
    ENDPOINT = "/db/CNLD"
    NAME = "Nodal Loads"
    PRODUCTS = frozenset({"gen", "civil"})


class BeamLoadItem(ItemGroupFields, total=False):
    """One entry of the /db/BMLD "ITEMS" array.

    D/P are 4-value distance/load arrays; see docs/manual/06_DB_Static_Loads.md
    #4 for the eccentricity-related fields (ECCEN_*, *_END, ADDITIONAL_*),
    not all of which are typed here for v1.
    """

    LCNAME: str  # Load Case Name, required
    CMD: str  # "BEAM" / "LINE" / "TYPICAL", required
    TYPE: str  # "CONLOAD"/"CONMOMENT"/"UNILOAD"/"UNIMOMENT"/"PRESSURE", required
    DIRECTION: str  # "LX"/"LY"/"LZ"/"GX"/"GY"/"GZ", required
    USE_PROJECTION: bool  # default false, optional
    D: List[float]  # Distance [x1,x2,x3,x4], default 0, optional
    P: List[float]  # Load [v1,v2,v3,v4], default 0, optional
    USE_ECCEN: bool  # default false, optional
    VX: float  # Vector X; /info declares it and the manual documents it nowhere (checked across every chapter, 2026-09-04)
    VY: float  # Vector Y; same
    VZ: float  # Vector Z; same. The manual documents nineteen members and a
    # six-name DIRECTION enum, with nothing that takes a vector.


class BeamLoadPayload(TypedDict):
    """docs/manual/06_DB_Static_Loads.md #4 — /db/BMLD. Keyed by element id."""

    ITEMS: List[BeamLoadItem]


class BeamLoad(DbResource):
    ENDPOINT = "/db/BMLD"
    NAME = "Beam Loads"
    PRODUCTS = frozenset({"gen", "civil"})


class PressureLoadItem(ItemGroupFields, total=False):
    """One entry of the /db/PRES "ITEMS" array.

    FORCES is required when FACE_EDGE_TYPE is "FACE"/"PRES"; EDGE_LOADS is
    required when FACE_EDGE_TYPE is "EDGE" — the two are mutually exclusive
    per docs/manual/06_DB_Static_Loads.md #10, not enforced at runtime here.

    ⚠️ **Do not rely on DIRECTION's documented default.** Verified live
    2026-07-26 (Civil NX 2026 v2.1) on a 4-node PLATE with
    FACE_EDGE_TYPE="FACE": ``"NORMAL"`` is rejected with "[Error] Errors
    detected in Pressure Loads Data.(Item:Load Direction)", and **omitting
    DIRECTION fails identically** — so the default is applied and the default
    is unusable for the commonest case. ``"LZ"`` (element local z, i.e. normal
    to the plate), ``"LX"``, ``"GZ"`` and ``"VECTOR"`` (with VECTORS) all
    succeed. ``"NORMAL"`` is a *recognised* value — misspellings get the
    generic "Wrong Field" instead — so it is presumably valid for some other
    ELEM_TYPE/FACE_EDGE_TYPE combination; pass ``"LZ"`` for plate faces.

    The server also echoes FORCES back with five entries, not the four the
    manual's example sends, and ``/info/db/PRES`` gives its maxItems as 5.
    """

    LCNAME: str  # Load Case Name, required
    CMD: str  # default "PRES", optional
    ELEM_TYPE: str  # "PLATE"/"SOLID"/"PLANE", default "PLATE", optional
    FACE_EDGE_TYPE: str  # "FACE"/"EDGE"/"PRES", required
    DIRECTION: str  # "NORMAL"/"LX"/"LY"/"LZ"/"GX"/"GY"/"GZ"/"VECTOR" — see the class docstring; the documented "NORMAL" default is rejected for PLATE/FACE, pass "LZ"
    VECTORS: List[float]  # [X,Y,Z], required if DIRECTION="VECTOR"
    OPT_PROJECTION: bool  # default false, optional (GX/GY/GZ only)
    EDGE_FACE: int  # Solid: 1-6, Plate/Plane: 1-4, required
    FORCES: List[float]  # required if FACE_EDGE_TYPE is FACE/PRES
    EDGE_LOADS: List[float]  # required if FACE_EDGE_TYPE is EDGE


class PressureLoadPayload(TypedDict):
    """docs/manual/06_DB_Static_Loads.md #10 — /db/PRES. Keyed by element id."""

    ITEMS: List[PressureLoadItem]


class PressureLoad(DbResource):
    """See :class:`PressureLoadItem`.

    :meth:`create`/:meth:`update` require an explicit ``DIRECTION`` on every
    item, because the documented default is one the product refuses.
    """

    ENDPOINT = "/db/PRES"
    NAME = "Assign Pressure Loads"
    PRODUCTS = frozenset({"gen", "civil"})

    @classmethod
    def _require_direction(cls, items: dict, method: str) -> None:
        """Refuse an item that leaves DIRECTION to the documented default.

        Omitting it makes the server apply ``"NORMAL"``, and on a PLATE with
        FACE_EDGE_TYPE ``"FACE"`` it then refuses the record with
        ``[Error] Errors detected in Pressure Loads Data.(Item:Load
        Direction)``. The caller never chose that value - the manual told them
        the field was optional - so requiring it here replaces a default
        nobody typed with a decision somebody made. Sending ``"NORMAL"``
        explicitly is left alone: it is a valid choice for the other three
        documented ELEM_TYPE/FACE_EDGE_TYPE pairs. Contract rule
        db-pres-direction-must-be-explicit.
        """
        for key, item in items.items():
            if not isinstance(item, dict):
                continue
            for index, entry in enumerate(item.get("ITEMS") or []):
                if isinstance(entry, dict) and "DIRECTION" not in entry:
                    raise MidasRequestError(
                        "DIRECTION must be sent explicitly for /db/PRES: the "
                        'documented default "NORMAL" is refused on a PLATE '
                        'with FACE_EDGE_TYPE "FACE" (Hint: "LZ" is the '
                        "element local axis normal to a plate face) "
                        f"(record {key}, ITEMS[{index}])",
                        method=method,
                        endpoint=cls.ENDPOINT,
                    )

    @classmethod
    def create(cls, items: dict, client: Optional[MidasClient] = None) -> dict:
        cls._require_direction(items, "POST")
        return super().create(items, client=client)

    @classmethod
    def update(cls, items: dict, client: Optional[MidasClient] = None) -> dict:
        cls._require_direction(items, "PUT")
        return super().update(items, client=client)


class SpecifiedDisplacementValue(TypedDict, total=False):
    OPT_FLAG: bool  # Usage Flag, default false, optional
    DISPLACEMENT: float  # Displacement Value, default 0, optional


class SpecifiedDisplacementItem(ItemGroupFields, total=False):
    """One entry of the /db/SDSP "ITEMS" array."""

    LCNAME: str  # Load Case Name, required
    VALUES: List[SpecifiedDisplacementValue]  # [Dx,Dy,Dz,Rx,Ry,Rz] (Local), optional


class SpecifiedDisplacementPayload(TypedDict):
    """docs/manual/06_DB_Static_Loads.md #5 — /db/SDSP. Keyed by node id."""

    ITEMS: List[SpecifiedDisplacementItem]


class SpecifiedDisplacement(DbResource):
    ENDPOINT = "/db/SDSP"
    NAME = "Specified Displacements of Support"
    PRODUCTS = frozenset({"gen", "civil"})


class NodalMassPayload(TypedDict, total=False):
    """docs/manual/06_DB_Static_Loads.md #6 — /db/NMAS. Keyed by node id.

    🛑 **Root cause found 2026-07-29, after 15+ crash reproductions across
    both Civil NX and Gen NX (multiple versions/builds, throwaway and real
    production models, both local and cross-machine callers — see
    docs/live_verification_notes.md for the full history): the server
    crashes when the optional ``rmX``/``rmY``/``rmZ`` fields are omitted
    from the payload, and does not crash when they are sent explicitly
    (even as ``0.0``, their documented default).** Confirmed symmetrically
    on both products in the same session: a call with all six fields
    present succeeds (``201``, echoes the data back, session stays alive),
    and an immediately following call on a different node with only
    ``mX``/``mY``/``mZ`` set kills that same session every time. This reads
    as an uninitialized-value read or missing-default bug server-side for
    these three fields specifically, not a defect in ``/db/NMAS`` writes in
    general. The failure itself is a ~15-60s timeout on the call, every
    following ``/db/*`` call then timing out too, and the "Failed to
    disconnect the work session" license dialog forcing a restart.

    **This class works around it**: :meth:`NodalMass.create` and
    :meth:`NodalMass.update` fill in ``rmX``/``rmY``/``rmZ`` with ``0.0``
    for any item that omits them, before sending — matching the documented
    default exactly, just made explicit because the server can't be trusted
    to apply it itself. Callers don't need to know about this defect to use
    the class safely; pass all six fields yourself only if you need
    non-zero rotational mass.

    ``GET``/``/info/db/NMAS`` were never affected either way. Full
    reproduction history, including the crashes that preceded finding this
    root cause, is in docs/live_verification_notes.md.
    """

    mX: float  # Translational Mass - GCS X, required
    mY: float  # Translational Mass - GCS Y, default 0, optional
    mZ: float  # Translational Mass - GCS Z, default 0, optional
    rmX: float  # Rotational Mass Moment of Inertia - X-axis, default 0, optional
    rmY: float  # Rotational Mass Moment of Inertia - Y-axis, default 0, optional
    rmZ: float  # Rotational Mass Moment of Inertia - Z-axis, default 0, optional


class NodalMass(DbResource):
    """See :class:`NodalMassPayload` — :meth:`create`/:meth:`update` default
    the optional rotational-mass fields to ``0.0`` to work around a server
    crash triggered by omitting them."""

    ENDPOINT = "/db/NMAS"
    NAME = "Nodal Masses"
    PRODUCTS = frozenset({"gen", "civil"})

    _ROTATIONAL_DEFAULTS = {"rmX": 0.0, "rmY": 0.0, "rmZ": 0.0}

    @classmethod
    def _with_rotational_defaults(cls, items: dict) -> dict:
        return {
            k: {**cls._ROTATIONAL_DEFAULTS, **v}
            for k, v in items.items()
        }

    @classmethod
    def create(cls, items: dict, client: Optional[MidasClient] = None) -> dict:
        return super().create(cls._with_rotational_defaults(items), client=client)

    @classmethod
    def update(cls, items: dict, client: Optional[MidasClient] = None) -> dict:
        return super().update(cls._with_rotational_defaults(items), client=client)


class LoadsToMassCase(TypedDict, total=False):
    LCNAME: str  # Load Case Name, required
    FACTOR: float  # Scale Factor, required


class LoadsToMassPayload(TypedDict, total=False):
    """docs/manual/06_DB_Static_Loads.md #7 — /db/LTOM Specifications table."""

    DIR: str  # Mass Direction: "X"/"Y"/"Z"/"XY"/"YZ"/"XZ"/"XYZ", required
    bNODAL: bool  # Nodal Load, default false, optional
    bBEAM: bool  # Beam Load, default false, optional
    bFLOOR: bool  # Floor Load, default false, optional
    bPRES: bool  # Pressure (Hydrostatic), default false, optional
    GRAV: float  # Gravity Acceleration, default 0, optional
    vLC: List[LoadsToMassCase]  # Load Case List, required


class LoadsToMass(DbResource):
    ENDPOINT = "/db/LTOM"
    NAME = "Loads to Masses"
    PRODUCTS = frozenset({"gen", "civil"})


class NodalBodyForcePayload(TypedDict, total=False):
    """docs/manual/06_DB_Static_Loads.md #8 — /db/NBOF Specifications table.

    OPT_USE_GROUP selects between GROUP_NAME (true) and KEY_NODE_ITEMS (false).
    """

    LCNAME: str  # Load Case Name, required
    OPT_NODAL_MASS: bool  # default false, optional
    OPT_LOAD_TO_MASS: bool  # default false, optional
    OPT_STRUCT_MASS: bool  # default false, optional
    X: float  # X-dir. Force Factor, required
    Y: float  # Y-dir. Force Factor, default 0, optional
    Z: float  # Z-dir. Force Factor, default 0, optional
    OPT_USE_GROUP: bool  # Structure Group Option, default false, optional
    GROUP_NAME: str  # required if OPT_USE_GROUP=true
    KEY_NODE_ITEMS: List[int]  # Node No. list, required if OPT_USE_GROUP=false


class NodalBodyForce(DbResource):
    ENDPOINT = "/db/NBOF"
    NAME = "Nodal Body Force"
    PRODUCTS = frozenset({"gen", "civil"})


class PressureLoadTypeItem(TypedDict, total=False):
    """One entry of the /db/PSLT "PRESSURE_LOAD_ITEMS" array.

    The manual's Specifications table labels the load-case-name key "CMD",
    but its own worked example uses "LOADCASENAME" — we follow the example.
    """

    LOADCASENAME: str  # Load Case Name, required
    LOADTYPE: str  # "Uniform" / "Linear", required
    LOAD_P1: float  # required
    LOAD_P2: float  # default 0, optional (Linear only)
    LOAD_P3: float  # default 0, optional (Linear only, Face types)
    LOAD_P4: float  # default 0, optional (Linear only, Face types)


class PressureLoadTypePayload(TypedDict, total=False):
    """docs/manual/06_DB_Static_Loads.md #9 — /db/PSLT Specifications table.

    ELEM_TYPE is one of "Plate/Plane Stress (Face)", "Plate/Plane Stress
    (Edge)", "Solid (Face)", "Plane Strain (Edge)", "Axisymmetric (Edge)",
    "Wall (Edge)" — see the manual's Element Type Load Support Matrix for
    which of LOAD_P1..P4 apply per (ELEM_TYPE, LOADTYPE) combination.

    The manual writes these with spaces in its Specifications prose and
    without them in its worked example ("Plate/PlaneStress(Face)"). Checked
    live 2026-07-26 (Civil NX 2026 v2.2): **both spellings are accepted**, so
    either is safe.
    """

    NAME: str  # Pressure Load Type Name, required
    DESC: str  # Description, required
    ELEM_TYPE: str  # required
    PRESSURE_LOAD_ITEMS: List[PressureLoadTypeItem]  # required


class PressureLoadType(DbResource):
    ENDPOINT = "/db/PSLT"
    NAME = "Define Pressure Load Type"
    PRODUCTS = frozenset({"gen", "civil"})


class PlaneLoadTypePayload(TypedDict, total=False):
    """docs/manual/06_DB_Static_Loads.md #11 — /db/PNLD Specifications table.

    Shape depends on LTYPE: "POINT" (POINTLOAD array of {X,Y,F}), "LINE"
    (LINELOAD object with bUNIFORM/X/Y/F), "AREA" (AREALOAD object with
    bUNIFORM/b3PNT/X/Y/LOAD) — left as Any for v1, matching SECT_I precedent.
    """

    NAME: str  # Load Type Name, required
    DESC: str  # Description, default "", optional
    LTYPE: str  # "POINT" / "LINE" / "AREA", required
    COPY_X: List[float]  # Copy in X-Direction, required
    COPY_Y: List[float]  # Copy in Y-Direction, required
    SEQ: int  # Sequence Number (unique), default auto, optional
    POINTLOAD: Any  # LTYPE="POINT": [{"X":.., "Y":.., "F":..}, ...]
    LINELOAD: Any  # LTYPE="LINE": {"bUNIFORM":.., "X":[x1,x2], "Y":[y1,y2], "F":[f1,f2]}
    AREALOAD: Any  # LTYPE="AREA": {"bUNIFORM":.., "b3PNT":.., "X":[..], "Y":[..], "LOAD":[..]}


class PlaneLoadType(DbResource):
    ENDPOINT = "/db/PNLD"
    NAME = "Define Plane Load Type"
    PRODUCTS = frozenset({"gen", "civil"})


class PlaneLoadPayload(TypedDict, total=False):
    """docs/manual/06_DB_Static_Loads.md #12 — /db/PNLA Specifications table.

    ⚠️ Confirmed live 2026-08-16 (Civil NX v2.2, build 08/14/2026):
    despite the manual marking ``LOAD_GROUP`` Required, sending any
    non-empty value answers ``"Wrong Field"``; omitting the key (or
    sending ``""``) succeeds. Left typed as optional here pending
    confirmation of what value it actually expects, if any.
    """

    LCNAME: str  # Load Case Name, required
    LOAD_GROUP: str  # Load Group Name -- confirmed live: any non-empty value is rejected ("Wrong Field"); omit or send ""
    PNLD_KEY: int  # Defined Plane Load Key (/db/PNLD id), required
    ELEM_TYPE: str  # "PLATE" / "SOLID", required
    POINT_ORIGIN: List[float]  # First Point / Origin [x, y, z], required
    AXIS_X: List[float]  # Second Point / on x-Axis [x, y, z], required
    AXIS_Y: List[float]  # Third Point / on x-y Plane [x, y, z], required
    TOL: float  # Tolerance, required
    SELECT_TYPE: str  # "ON_PLANE" / "IN_GROUP", required
    LOAD_DIR: str  # "NORMAL_PLANE"/"NORMAL_ELEM"/"GLOBAL_X"/"GLOBAL_Y"/"GLOBAL_Z", required
    PROJECT_TYPE: str  # "NO" / "LOAD_DIR" / "LOAD_PLANE", required
    DESC: str  # default "", optional
    bDEFINE_NODE: bool  # default false, optional
    CONNECT_NODE: List[int]  # Loading Boundary Connecting Node, optional
    ELEM_GROUP: str  # Element Group Name, optional
    FACE_NO: int  # Solid Face No. (1-6), optional


class PlaneLoad(DbResource):
    ENDPOINT = "/db/PNLA"
    NAME = "Assign Plane Loads"
    PRODUCTS = frozenset({"gen", "civil"})


class FloorLoadTypeItem(TypedDict, total=False):
    LCNAME: str  # Load Case Name, required
    FLOOR_LOAD: float  # required
    OPT_SUB_BEAM_WEIGHT: bool  # default false, optional


class FloorLoadTypePayload(TypedDict, total=False):
    """docs/manual/06_DB_Static_Loads.md #13 — /db/FBLD Specifications table."""

    NAME: str  # Floor Load Type Name, required
    DESC: str  # default "", optional
    ITEM: List[FloorLoadTypeItem]  # required


class FloorLoadType(DbResource):
    ENDPOINT = "/db/FBLD"
    NAME = "Define Floor Load Type"
    PRODUCTS = frozenset({"gen", "civil"})


class FloorLoadPayload(TypedDict, total=False):
    """docs/manual/06_DB_Static_Loads.md #14 — /db/FBLA Specifications table."""

    FLOOR_LOAD_TYPE_NAME: str  # required
    FLOOR_DIST_TYPE: int  # One Way=1, Two Way=2, Polygon-Centroid=3, Polygon-Length=4; required
    DIR: str  # "LX"/"LY"/"LZ"/"GX"/"GY"/"GZ", default "LX", optional
    OPT_PROJECTION: bool  # default false, optional
    DESC: str  # default "", optional
    GROUP_NAME: str  # Load Group Name, default "", optional
    NODES: List[int]  # Nodes defining Loading Area, required
    LOAD_ANGLE: float  # default 0, optional
    OPT_ALLOW_POLYGON_TYPE_UNIT_AREA: bool  # default false, optional
    OPT_EXCLUDE_INNER_ELEM_AREA: bool  # default false, optional
    SUB_BEAM_NUM: int  # default 0, optional
    SUB_BEAM_ANGLE: float  # default 0, optional
    UNIT_SELF_WEIGHT: float  # default 0, optional


class FloorLoad(DbResource):
    ENDPOINT = "/db/FBLA"
    NAME = "Assign Floor Loads"
    PRODUCTS = frozenset({"gen", "civil"})


class FinishingMaterialLoadItem(ItemGroupFields, total=False):
    """One entry of the /db/FMLD "ITEMS" array."""

    LCNAME: str  # Load Case Name, required
    COVERING_TYPE: str  # "ENVELOP"/"FILL"/"SURROUND", default "ENVELOP", optional
    COVERING_RANGE: List[str]  # [+x,-y,-x,+y], each "FULL"/"HALF", required
    THICKNESS: float  # Covering Thickness, default 0, optional
    DENSITY: float  # Filling Property (Density), default 0, optional
    DIR: str  # "GX"/"GY"/"GZ", default "GZ", optional
    SCALE_FACTOR: float  # required


class FinishingMaterialLoadPayload(TypedDict):
    """docs/manual/06_DB_Static_Loads.md #15 — /db/FMLD. Keyed by element id."""

    ITEMS: List[FinishingMaterialLoadItem]


class FinishingMaterialLoad(DbResource):
    ENDPOINT = "/db/FMLD"
    NAME = "Finishing Material Loads"
    PRODUCTS = frozenset({"gen", "civil"})


class SoilPropertyItem(TypedDict, total=False):
    HEIGHT: float  # Soil Layer Thickness, required
    ANGLE_OR_N: float  # Internal Friction Angle or N Value, required
    DENSITY: float  # Unit Volume Weight of Soil, required
    VS: float  # Shear Wave Velocity, required
    KH: float  # Coeff. of Horizontal Ground Reaction, required
    DISP: float  # Relative Displacement, required


class SoilPropertyPayload(TypedDict, total=False):
    """docs/manual/06_DB_Static_Loads.md #16 — /db/POSP Specifications table."""

    NAME: str  # Soil Properties Name, required
    DESC: str  # default "", optional
    OPT_USE_N: bool  # true=use N value, false=use internal friction angle; default false
    GROUND_LEVEL: float  # Level of Ground Surface, required
    BEDROCK_LEVEL: float  # Level of Bedrock, required
    FOOTING_LEVEL: float  # Level of Footing Bottom, required
    ITEMS: List[SoilPropertyItem]  # Soil Characteristic items (per layer), required


class SoilProperty(DbResource):
    ENDPOINT = "/db/POSP"
    NAME = "Parameter of Soil Properties"
    #: Gen-only: 404 (route + /info) on Civil NX, confirmed independently
    #: twice on 2026-07-29 — see db/base.py's GEN_ONLY docstring.
    PRODUCTS = GEN_ONLY


class StaticEarthPressureProfileItem(TypedDict, total=False):
    LEVEL: float  # required
    SOIL_PRES: float  # required
    ADD_PRES: float  # required


class StaticEarthPressurePayload(TypedDict, total=False):
    """docs/manual/06_DB_Static_Loads.md #17 — /db/EPST Specifications table."""

    LOADCASE: str  # Load Case Name, required
    DIR: str  # "XY"/"NORMAL", default "XY", optional
    ANGLE: float  # Static Earth Pressure Angle, required
    IN_PT: List[float]  # Inner Point, optional
    SF: float  # Scale Factor, required
    EP_TYPE: str  # "AT_REST"/"ACTIVE", required
    SURCHARGE_LOAD: float  # required
    WATER_LEVEL: float  # required
    SOIL_PROP: str  # Soil Properties Name (/db/POSP name), required
    SEL_TYPE: str  # "GRUP"/"ELEMENT", required
    ELEM_TYPE: str  # "FRAME"/"PLANAR", required
    NODE_LIST: List[int]  # optional
    ELEM_LIST: List[int]  # optional
    LOADING_AREA_GROUP: int  # Loading Area Group Name, optional
    PRES_PROFILE_ITEMS: List[StaticEarthPressureProfileItem]  # optional


class StaticEarthPressure(DbResource):
    ENDPOINT = "/db/EPST"
    NAME = "Static Earth Pressure"
    #: Gen-only: 404 (route + /info) on Civil NX, confirmed independently
    #: twice on 2026-07-29 — see db/base.py's GEN_ONLY docstring.
    PRODUCTS = GEN_ONLY


class SeismicEarthPressureProfileItem(TypedDict, total=False):
    LEVEL: float  # required
    KH: float  # Horizontal Coefficient, required
    REL_DISP: float  # Relative Displacement, required
    SEIS_PRES: float  # Seismic Pressure, required
    ADD_PRES: float  # Additional Pressure, optional


class SeismicEarthPressurePayload(TypedDict, total=False):
    """docs/manual/06_DB_Static_Loads.md #18 — /db/EPSE Specifications table.

    The manual's own worked example sends ``SEL_TYPE: "ELEM"`` and
    ``ELEM_TYPE`` defaults to ``"ELEM"``, neither of which matches either
    field's own documented enum (SEL_TYPE: "GROUP"/"ELEMENT"; ELEM_TYPE:
    "FRAME"/"PLANAR") — we follow the Specifications table's enum as
    canonical, matching the STATIC (EPST) sibling's SEL_TYPE convention.
    """

    LOADCASE: str  # Load Case Name, required
    DIR: str  # "XY"/"NORMAL", default "XY", optional
    ANGLE: float  # Seismic Earth Pressure Angle, default 0, optional
    IN_PT: List[float]  # Inner Point, optional
    SF: float  # Scale Factor, optional
    CODE: str  # Design Code, optional
    SEIS_LOAD: str  # Seismic Load Name (/db/POSL name), required
    LAYER_PARAM: str  # "SINGLE"/"DOUBLE", default "SINGLE", optional
    LAYER_LV: float  # Soil Second Layer Level (Double Cosine), default 0, optional
    SOIL_PROP: str  # Soil Properties Name (/db/POSP name), required
    SEL_TYPE: str  # "GROUP"/"ELEMENT", required. Gen NX only
    ELEM_TYPE: str  # "FRAME"/"PLANAR", required
    NODE_LIST: List[int]  # optional
    ELEM_LIST: List[int]  # optional
    LOADING_AREA_GROUP: int  # optional. Gen NX only
    LOAD_TYPE: str  # Loading Type. Civil NX only; /info declares it and the manual documents it nowhere (checked across every chapter, 2026-09-04). MD-46.
    WIDTH: float  # Width. Civil NX only; same. MD-46.
    PRES_PROFILE_ITEMS: List[SeismicEarthPressureProfileItem]  # optional


class SeismicEarthPressure(DbResource):
    ENDPOINT = "/db/EPSE"
    NAME = "Seismic Earth Pressure"
    PRODUCTS = frozenset({"gen", "civil"})


class SeismicLoadParamPayload(TypedDict, total=False):
    """docs/manual/06_DB_Static_Loads.md #19 — /db/POSL Specifications table.

    ⚠️ Confirmed live 2026-08-16 (v2.1/v2.2, build 08/14/2026): this
    endpoint's actual accepted field set is product-asymmetric, and only
    Gen NX matches the fields below. **Civil NX's live schema is entirely
    different** — ``SZ``, ``SRF`` (Seismic Risk Factor, not ``EPA``),
    ``SC``, ``FA``, ``FV``, ``DAMP_RATIO`` (Damping Ratio) only. Sending
    ``CODE`` on Civil fails ``"Wrong Field"`` even as an empty string, and
    none of ``METHOD``/``EPA``/``SDS``/``SD1``/``USER_GROUP``/``IF``/
    ``RMF`` are accepted there at all. Gen NX also has two undocumented
    fields beyond the manual: ``EPGAeff``, ``Kae`` (both float, per
    ``GET``/``.info()``). Check the active product before building this
    payload; there is no single shape that works on both.
    """

    NAME: str  # Load Case Name, required
    CODE: str  # Seismic Load Code, optional. Gen NX only -- any value, even "", is rejected on Civil NX
    METHOD: str  # "RES_DISP"/"EQV_STATIC", optional. Gen NX only
    SZ: str  # Seismic Zone, required
    EPA: float  # Effective Peak Ground Acceleration, required. Gen NX only -- see SRF for Civil NX
    SC: str  # Site Class, required
    FA: float  # Short-period Site Coefficient, required
    FV: float  # Long-period Site Coefficient, required
    SDS: float  # Design Spectral Acceleration at Short Period, required. Gen NX only
    SD1: float  # Design Spectral Acceleration at 1-sec Period, required. Gen NX only
    USER_GROUP: str  # Seismic User Group, optional. Gen NX only
    IF: float  # Importance Factor, required. Gen NX only
    RMF: float  # Response Modification Factor, required. Gen NX only
    SRF: float  # Seismic Risk Factor. Civil NX only, undocumented -- Civil's equivalent of EPA
    DAMP_RATIO: float  # Damping Ratio. Civil NX only, undocumented
    EPGAeff: float  # Gen NX only, undocumented. Named in this docstring since
    # 2026-08-16 and never actually typed; /info/db/POSL declares it. MD-46.
    Kae: float  # Gen NX only, undocumented. Same. MD-46.


class SeismicLoadParam(DbResource):
    ENDPOINT = "/db/POSL"
    NAME = "Parameter of Seismic Loads"
    PRODUCTS = frozenset({"gen", "civil"})


class StaticWindLoadPayload(TypedDict, total=False):
    """docs/manual/06_DB_Static_Loads.md #20 — /db/SWIND Specifications table.

    PARAMETERS is deeply conditional on its nested INPUT_METHOD (0=Simplified,
    1=General, 2=General + Vortex Shedding) per the KDS 41-12:2022 code; only
    the common envelope is typed for v1, matching the SECT_I precedent.

    WIND_CODE="USER TYPE" (added to the manual 2026-08-10) is a separate
    variant that skips the KDS calculation entirely: PARAMETERS is unused
    and STORY_WIND_PRESSURE/WIND_ECCEN_X/WIND_ECCEN_Y take over instead.
    GET-only fields ELEV/LOAD_H/LOAD_BX/LOAD_BY must not be sent back in a
    request per the manual's own JSON Schema.

    ⚠️ Live-verified 2026-08-13 (Gen NX v2.1, build 08/12/2026): on a model
    with real ``Story`` data (``STORY_NAME`` "1F"/"RF"), a POST with
    ``STORY_WIND_PRESSURE`` keyed to both story names succeeded and GET
    read it back correctly — the server fills in ELEV/LOAD_H/LOAD_BX/
    LOAD_BY on the way out, confirming they're genuinely GET-only.
    """

    WIND_CODE: str  # e.g. "KDS(41-12: 2022)" or "USER TYPE", required
    DESC: str  # default "", optional
    WIND_ECCEN_X: int  # USER TYPE only: 0=Positive/1=Negative/2=None, default 2, optional
    WIND_ECCEN_Y: int  # USER TYPE only: 0=Positive/1=Negative/2=None, default 2, optional
    SCALE_FACTOR_X: float  # required
    SCALE_FACTOR_Y: float  # required
    PARAMETERS: Any  # variant-specific body, keyed by "INPUT_METHOD"; unused when WIND_CODE="USER TYPE"
    STORY_WIND_PRESSURE: Any  # USER TYPE only: array of {STORY_NAME, PRESS_X, PRESS_Y}, required when WIND_CODE="USER TYPE"
    ADDITIONAL_LOAD: Any  # optional per-story overrides; USER TYPE shape: array of {STORY_NAME, ALONG_X, ALONG_Y, TORSIONAL_RZ}


class StaticWindLoad(DbResource):
    ENDPOINT = "/db/SWIND"
    NAME = "Static Wind Load"
    #: Gen-only: 404 (route + /info) on Civil NX, confirmed independently
    #: twice on 2026-07-29 — see db/base.py's GEN_ONLY docstring.
    PRODUCTS = GEN_ONLY


class StaticSeismicLoadPayload(TypedDict, total=False):
    """docs/manual/06_DB_Static_Loads.md #21 — /db/SSEIS Specifications table.

    PARAMETERS holds the nested KDS 41-17-00:2019 code parameters (seismic
    zone, site class, period method, ...); only the common envelope is typed
    for v1, matching the SECT_I precedent.

    SEIS_CODE="USER TYPE" (added to the manual 2026-08-10) is a separate
    variant that skips the KDS calculation entirely: PARAMETERS is unused
    and SEISMIC_FORCE/INHERENT_TORSION take over instead. The manual's own
    Request Example misspells INHERENT_TORSION as "NHERENT_TORSION" (missing
    leading I) — its JSON Schema and Specifications table both agree on
    INHERENT_TORSION, so that's the one to send.

    ⚠️ Live-verified 2026-08-13 (Gen NX v2.1, build 08/12/2026): on the same
    2-story model as ``StaticWindLoadPayload``'s USER TYPE test, a POST with
    ``SEISMIC_FORCE`` keyed to both story names plus ``INHERENT_TORSION``
    succeeded and GET read it back correctly (server fills in per-story
    WEIGHT/ELEV on the way out) — confirms the corrected spelling above is
    the one the server actually accepts.
    """

    SEIS_CODE: str  # e.g. "KDS(41-17-00:2019)" or "USER TYPE", required
    DESC: str  # default "", optional
    SCALE_FACTOR_X: float  # required
    SCALE_FACTOR_Y: float  # required
    ACCIDENT_ECCEN_X: int  # 0=+, 1=-, 2=none; optional
    ACCIDENT_ECCEN_Y: int  # 0=+, 1=-, 2=none; optional
    ACCIDENT_TORSION: bool  # Enable accidental eccentricity, default false, optional
    INHERENT_TORSION: bool  # USER TYPE only: consider inherent torsion, default false, optional
    PARAMETERS: Any  # nested design-code parameters; unused when SEIS_CODE="USER TYPE"
    SEISMIC_FORCE: Any  # USER TYPE only: array of {STORY_NAME, FORCE_X, FORCE_Y}, required when SEIS_CODE="USER TYPE"
    ADDITIONAL_LOAD: Any  # optional story-level load adjustments; USER TYPE shape: {STORY_NAME, ALONG_X, ALONG_Y, TORSIONAL_RZ}


class StaticSeismicLoad(DbResource):
    ENDPOINT = "/db/SSEIS"
    NAME = "Static Seismic Load"
    #: Gen-only: 404 (route + /info) on Civil NX, confirmed independently
    #: twice on 2026-07-29 — see db/base.py's GEN_ONLY docstring.
    PRODUCTS = GEN_ONLY
