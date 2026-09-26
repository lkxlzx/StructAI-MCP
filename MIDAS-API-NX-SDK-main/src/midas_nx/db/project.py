"""Source: docs/manual/02_DB_Project_Structure.md, items 1-15.

STYP-M1 had no chapter section until the manual repo wrote one on 2026-08-30;
its `StructureTypeHyperSPayload` was derived from `GET /info/db/STYP-M1`
server introspection, and the section that now exists agrees with it field for
field. Measured the same day, STYP-M1 and STYP are two spellings of one model
record — writing either changes the other — which is why neither serves POST
or DELETE. See docs/live_verification_notes.md for the value mapping.

UNIT/STYP are GET/PUT-only ("신규 파일의 필수 데이터: GET / PUT만 동작") — new-file
required data doesn't support POST/DELETE. CO_M/CO_S/CO_T/CO_F (visual color
defaults) are likewise GET/PUT-only. GRUP/BNGR (structure/boundary groups) omit
DELETE per the official manual itself: its own methods table (§ overview and
each endpoint's own Methods row) lists GRUP and BNGR as POST/GET/PUT only,
while every other endpoint in this chapter (PJCF, LDGR, TDGR, NPLN, SPAN,
STOR) gets the full POST/GET/PUT/DELETE set. Not an SDK-side restriction —
the API itself never exposes a DELETE route for these two.
"""
from __future__ import annotations

from typing import List, TypedDict

from .base import CIVIL_ONLY, GEN_ONLY, HYPER_S_ONLY, NO_DELETE_METHODS, DbResource

_GET_PUT_ONLY = frozenset({"GET", "PUT"})


class UnitPayload(TypedDict, total=False):
    """docs/manual/02_DB_Project_Structure.md #2 — /db/UNIT Specifications table."""

    FORCE: str  # "N"/"KN"/"KGF"/"TONF"/"LBF"/"KIPS"
    DIST: str  # "M"/"CM"/"MM"/"FT"/"IN"
    HEAT: str  # "CAL"/"KCAL"/"J"/"KJ"/"BTU"
    TEMPER: str  # "C"/"F"


class Unit(DbResource):
    ENDPOINT = "/db/UNIT"
    NAME = "Unit System"
    PRODUCTS = frozenset({"gen", "civil"})
    METHODS = _GET_PUT_ONLY


class StructureTypePayload(TypedDict, total=False):
    """docs/manual/02_DB_Project_Structure.md #3 — /db/STYP Specifications table.

    Defaults below (all five booleans default `false`, `SMASS` defaults `1`)
    come from the manual's 2026-08-25 re-verification against article id
    `35802404495257` -- previously undocumented. Not independently
    live-tested: `/db/STYP` is "new-file required data" (GET/PUT only), so
    its default only applies to a document that has never had the field set,
    and probing that would require `/doc/NEW`, which this project's live
    scripts never call against a session that might hold real work. A live
    GET on the currently open Gen NX document (2026-08-27) reads back
    `bMASSOFFSET: True` -- but that reflects this document's own prior
    setting, not the manual's claimed default for a fresh file.
    """

    STYP: int  # Structure Type, default System (see manual)
    MASS: int  # Mass Type
    bMASSOFFSET: bool  # Consider Offset, default false (manual-sourced, not live-verified)
    bSELFWEIGHT: bool  # Convert Self Weight to Mass, default false (manual-sourced, not live-verified)
    SMASS: int  # Structure Mass Type (when bSELFWEIGHT), default 1 (manual-sourced, not live-verified)
    GRAV: float  # Gravity
    TEMP: float  # Initial Temperature, default 0
    bALIGNBEAM: bool  # Align Top of Beam Section, default false (manual-sourced, not live-verified)
    bALIGNSLAB: bool  # Align Top of Slab (Plate), default false (manual-sourced, not live-verified)
    # Accepted by both products, echoed back only by Gen: Civil takes a PUT
    # carrying it without complaint and then omits it from every GET, though
    # /info/db/STYP lists it identically on both (live 2026-08-30). Read it
    # with a default rather than by subscript.
    bROTRIGID: bool  # Considering Rotational Rigid, default false


class StructureType(DbResource):
    ENDPOINT = "/db/STYP"
    NAME = "Structure Type"
    PRODUCTS = frozenset({"gen", "civil"})
    METHODS = _GET_PUT_ONLY


class MassControlHyperS(TypedDict, total=False):
    """Shape of StructureTypeHyperSPayload's MASS_CONTROL sub-object."""

    MASS_TYPE: str  # Mass type
    MASS_POS: str  # Mass position
    SELFWEIGHT: bool  # Convert Self Weight
    MASS_AXIS: str  # Structure Mass Type


class StructureTypeHyperSPayload(TypedDict, total=False):
    """Derived from `GET /info/db/STYP-M1` server introspection, and since
    confirmed against the manual.

    There was no Specifications table for this Hyper-S variant when these
    fields were written (confirmed live 2026-07-29, Civil NX Hyper-S — see the
    v1.0.0 Hyper-S-stub decision in PLAN.md). The manual repo wrote the section
    on 2026-08-30 and it matches: same six keys, same four MASS_CONTROL
    members.

    MASS_POS applies only when MASS_TYPE is "LUMPED" and is required there;
    sent under "CONSISTENT" the server accepts the call and discards the
    field. MASS_AXIS applies only when SELFWEIGHT is true, and under
    "CONSISTENT" only "XYZ" is accepted. STYPE is "3D", not "_3D".
    """

    STYPE: str  # Structure Type
    GRAV: float  # Gravity
    TEMP: float  # Initial Temperature
    ALIGNBEAM: bool  # Align Top of Beam Section
    ALIGNSLAB: bool  # Align Top of Slab (Plate)
    MASS_CONTROL: MassControlHyperS  # Mass control parameter


class StructureTypeHyperS(DbResource):
    """GET/PUT only, like the classic /db/STYP - measured, not assumed.

    The official article tags GET, PUT, DELETE under its own activeMethods
    field, and the manual chapter transcribes that faithfully. The server
    disagrees: on Civil NX 2026 v2.2 (2026-08-30) all three DELETE forms
    answer {"message": "error status"} and change nothing, and so does
    POST. A DELETE this server does serve returns the deleted record - see
    /db/NODE - so "error status" is a refusal, not an empty result.

    Reported to the manual repo; see docs/live_verification_notes.md.
    """

    ENDPOINT = "/db/STYP-M1"
    NAME = "Structure Type (Hyper-S)"
    PRODUCTS = HYPER_S_ONLY
    METHODS = _GET_PUT_ONLY


class ProjectInfoPayload(TypedDict, total=False):
    """docs/manual/02_DB_Project_Structure.md #1 — /db/PJCF Specifications table."""

    PROJECT: str  # Project Name, optional
    REVISION: str  # Revision Info, optional
    USER: str  # Username, optional
    EMAIL: str  # E-mail, optional
    ADDRESS: str  # Address, optional
    TEL: str  # Telephone Numbers, optional
    FAX: str  # Fax Numbers, optional
    CLIENT: str  # Client, optional
    TITLE: str  # Title, optional
    ENGINEER: str  # Engineer (Review Name), optional
    EDATE: str  # Engineer Review Date, optional
    CHECK1: str  # Checker 1 Name, optional
    CDATE1: str  # Checker 1 Date, optional
    CHECK2: str  # Checker 2 Name, optional
    CDATE2: str  # Checker 2 Date, optional
    CHECK3: str  # Checker 3 Name, optional
    CDATE3: str  # Checker 3 Date, optional
    APPROVE: str  # Approver Name, optional
    ADATE: str  # Approver Date, optional
    COMMENT: str  # Comments, optional
    # Five properties of the model file itself, returned by this endpoint and
    # documented in no chapter (checked 2026-09-04). Plainly server-computed —
    # a caller cannot set the file's size — but /info states no requiredness
    # and the manual has no Required cell for them to normalize, so they are
    # typed like the rest rather than marked read-only.
    FILE_NAME: str  # Model File Name
    DIR: str  # Model File Directory
    FILE_SIZE: str  # Model File Size
    CREATED: str  # Model File Created Time
    MODIFIED: str  # Model File Modified Time


class ProjectInfo(DbResource):
    ENDPOINT = "/db/PJCF"
    NAME = "Project Information"
    PRODUCTS = frozenset({"gen", "civil"})


class StructureGroupPayload(TypedDict, total=False):
    """docs/manual/02_DB_Project_Structure.md #5 — /db/GRUP Specifications table."""

    NAME: str  # Structure Group Name, required
    P_TYPE: int  # Plane Type, default 0
    N_LIST: List[int]  # Node List, optional
    E_LIST: List[int]  # Element List, optional


class StructureGroup(DbResource):
    ENDPOINT = "/db/GRUP"
    NAME = "Structure Group"
    PRODUCTS = frozenset({"gen", "civil"})
    METHODS = NO_DELETE_METHODS


class BoundaryGroupPayload(TypedDict, total=False):
    """docs/manual/02_DB_Project_Structure.md #6 — /db/BNGR Specifications table."""

    NAME: str  # Boundary Group Name, required
    AUTOTYPE: int  # Auto-generated CR/SH groups for Composite Section: 0=Creep, 1=Shrinkage; default auto-assigned, optional


class BoundaryGroup(DbResource):
    ENDPOINT = "/db/BNGR"
    NAME = "Boundary Group"
    PRODUCTS = frozenset({"gen", "civil"})
    METHODS = NO_DELETE_METHODS


class LoadGroupPayload(TypedDict, total=False):
    """docs/manual/02_DB_Project_Structure.md #7 — /db/LDGR Specifications table."""

    NAME: str  # Load Group Name, required


class LoadGroup(DbResource):
    ENDPOINT = "/db/LDGR"
    NAME = "Load Group"
    PRODUCTS = frozenset({"gen", "civil"})


class TendonGroupPayload(TypedDict, total=False):
    """docs/manual/02_DB_Project_Structure.md #8 — /db/TDGR Specifications table."""

    NAME: str  # Tendon Group Name, required


class TendonGroup(DbResource):
    ENDPOINT = "/db/TDGR"
    NAME = "Tendon Group"
    PRODUCTS = frozenset({"gen", "civil"})


class NamedPlanePointItem(TypedDict, total=False):
    ITEM: List[float]  # [X, Y, Z] point coordinate


class NamedPlanePayload(TypedDict, total=False):
    """docs/manual/02_DB_Project_Structure.md #9 — /db/NPLN Specifications table.

    2026-08-25 re-verification (article id `35805287066649`) corrected two
    values the SDK previously had wrong: `TOL` defaults to `0` (was
    undocumented), and `COORD` is plain Optional with default `0` -- not
    conditionally Required when TYPE != 1, despite being the field that
    actually matters in that case. Live-verified 2026-08-27 on Gen NX: POST
    `{"NAME": "ProbeNPLN", "TYPE": 2}` (both TOL and COORD omitted) round
    tripped through GET as `{"TOL": 0, "COORD": 0, ...}` -- confirming both
    defaults and that COORD is genuinely optional, not conditionally
    required. Probe record deleted after confirming.
    """

    NAME: str  # Plane Name, required
    TYPE: int  # 1=3 Points, 2=X-Y Plane, 3=X-Z Plane, 4=Y-Z Plane; required
    TOL: float  # Tolerance, default 0, optional
    POINT: List[NamedPlanePointItem]  # required if TYPE=1: 3 points, each {"ITEM": [X, Y, Z]}
    COORD: float  # Z/Y/X position depending on TYPE, default 0, optional (used when TYPE!=1)


class NamedPlane(DbResource):
    ENDPOINT = "/db/NPLN"
    NAME = "Named Plane"
    PRODUCTS = frozenset({"gen", "civil"})


class _ColorPayload(TypedDict, total=False):
    """Shared shape of the CO_M/CO_S/CO_T display-color endpoints."""

    W_R: int  # Wire Frame Red, 0-255, optional
    W_G: int  # Wire Frame Green, 0-255, optional
    W_B: int  # Wire Frame Blue, 0-255, optional
    HF_R: int  # Hidden Fill Red, 0-255, optional
    HF_G: int  # Hidden Fill Green, 0-255, optional
    HF_B: int  # Hidden Fill Blue, 0-255, optional
    HE_R: int  # Hidden Edge Red, 0-255, optional
    HE_G: int  # Hidden Edge Green, 0-255, optional
    HE_B: int  # Hidden Edge Blue, 0-255, optional
    bBLEMD: bool  # Opacity Boolean, optional
    FACT: float  # Opacity Value, 0.0-1.0, optional


class MaterialColorPayload(_ColorPayload):
    """docs/manual/02_DB_Project_Structure.md #10 — /db/CO_M Specifications table."""


class MaterialColor(DbResource):
    ENDPOINT = "/db/CO_M"
    NAME = "Material Color"
    PRODUCTS = frozenset({"gen", "civil"})
    METHODS = _GET_PUT_ONLY


class SectionColorPayload(_ColorPayload):
    """docs/manual/02_DB_Project_Structure.md #11 — /db/CO_S Specifications table."""


class SectionColor(DbResource):
    ENDPOINT = "/db/CO_S"
    NAME = "Section Color"
    PRODUCTS = frozenset({"gen", "civil"})
    METHODS = _GET_PUT_ONLY


class ThicknessColorPayload(_ColorPayload):
    """docs/manual/02_DB_Project_Structure.md #12 — /db/CO_T Specifications table."""


class ThicknessColor(DbResource):
    ENDPOINT = "/db/CO_T"
    NAME = "Thickness Color"
    PRODUCTS = frozenset({"gen", "civil"})
    METHODS = _GET_PUT_ONLY


class FloorLoadColorPayload(TypedDict, total=False):
    """docs/manual/02_DB_Project_Structure.md #13 — /db/CO_F Specifications table."""

    NAME: str  # Floor Load Type Name, required
    WF_R: int  # Wire Frame Red, 0-255, optional
    WF_G: int  # Wire Frame Green, 0-255, optional
    WF_B: int  # Wire Frame Blue, 0-255, optional
    HF_R: int  # Hidden Fill Red, 0-255, optional
    HF_G: int  # Hidden Fill Green, 0-255, optional
    HF_B: int  # Hidden Fill Blue, 0-255, optional
    HE_R: int  # Hidden Edge Red, 0-255, optional
    HE_G: int  # Hidden Edge Green, 0-255, optional
    HE_B: int  # Hidden Edge Blue, 0-255, optional
    OPT_BLEND: bool  # Blending, optional
    BLEND_FACTOR: float  # Blending Factor, 0.0-1.0, optional


class FloorLoadColor(DbResource):
    ENDPOINT = "/db/CO_F"
    NAME = "Floor Load Color"
    PRODUCTS = frozenset({"gen", "civil"})
    METHODS = _GET_PUT_ONLY


class SpanBaseItem(TypedDict, total=False):
    ELEM_KEY: int  # Element No.
    SUPPORT: int  # 0=None, 1=Start, 2=End


class SpanPayload(TypedDict, total=False):
    """docs/manual/02_DB_Project_Structure.md #14 — /db/SPAN Specifications table."""

    NAME: str  # Span Name, required
    bEXACTSPAN: bool  # Exact Span Option, required
    DIRECTION: int  # Inner direction of multiple girders: (-)Local y=0, (+)Local y=1, Both=2, None=3; required
    SECTTYPE: int  # Assign Elements: By Selection=0, Number=1; required
    SPAN_LIST: List[float]  # required if bEXACTSPAN=true
    SPAN_BASE_ITEMS: List[SpanBaseItem]  # required if bEXACTSPAN=true


class Span(DbResource):
    """⚠️ The manual documents this for both products, but three independent
    live sessions (2026-07-22, 2026-07-26, 2026-07-29) all 404 it under Gen
    NX while it answers under Civil NX. See docs/live_verification_notes.md.
    """

    ENDPOINT = "/db/SPAN"
    NAME = "Span Information"
    PRODUCTS = CIVIL_ONLY


class StoryAreaItem(TypedDict, total=False):
    """One entry of /db/STOR's `STORY_AREA_ITEMS`.

    /db/STOR's own section documents fifteen properties and stops. The
    manual does document this sixteenth one — in another chapter:
    `/ope/STOR`'s POST response in 15_OPE.md is the same record field for
    field with this array added, and the prose under it names it outright.
    `/info/db/STOR` agrees, member for member. See MD-39.
    """

    X: float  # X Factor
    Y: float  # Y Factor
    Z: float  # Z Factor


class StoryPayload(TypedDict, total=False):
    """docs/manual/02_DB_Project_Structure.md #15 — /db/STOR Specifications table."""

    STORY_NAME: str  # Story Name, required
    STORY_LEVEL: float  # Story Height (elevation), required
    bFLOOR_DIAPHRAGM: bool  # Rigid Floor Diaphragm assumption, default false, required
    WIND_FLOOR_WIDTH_X: float  # Wind Floor Width X-Dir, required
    WIND_FLOOR_WIDTH_Y: float  # Wind Floor Width Y-Dir, required
    WIND_CENTER_X: float  # Wind Floor Center Xc, required
    WIND_CENTER_Y: float  # Wind Floor Center Yc, required
    WIND_ECCENT_X: float  # Wind Eccentricity X-Dir, required
    WIND_ECCENT_Y: float  # Wind Eccentricity Y-Dir, required
    SEIS_ACC_ECCENT_X: float  # Seismic Accidental Eccentricity X-Dir, required
    SEIS_ACC_ECCENT_Y: float  # Seismic Accidental Eccentricity Y-Dir, required
    SEIS_INHERENT_ECCENT_X: float  # Seismic Inherent Eccentricity X-Dir, required
    SEIS_INHERENT_ECCENT_Y: float  # Seismic Inherent Eccentricity Y-Dir, required
    SEIS_TORSIONAL_AMP_FACTOR_X: float  # Seismic Torsional Amplification Factor X-Dir, required
    SEIS_TORSIONAL_AMP_FACTOR_Y: float  # Seismic Torsional Amplification Factor Y-Dir, required
    STORY_AREA_ITEMS: List[StoryAreaItem]  # Story Area Items; see below


class Story(DbResource):
    ENDPOINT = "/db/STOR"
    NAME = "Story Data"
    #: Gen-only: 404 (route + /info) on Civil NX, confirmed independently
    #: twice on 2026-07-29, and again 2026-08-13 (v2.2, build 08/12/2026)
    #: — see db/base.py's GEN_ONLY docstring. Write round trip confirmed on
    #: Gen NX 2026-08-13 (v2.1, build 08/12/2026): create() with a full,
    #: real 2-story payload succeeded and both stories were readable by
    #: name from /db/SWIND, /db/SSEIS, and the story load/weight tables.
    PRODUCTS = GEN_ONLY
