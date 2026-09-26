"""Source: docs/manual/03_DB_Node_Element.md, items 1-6."""
from __future__ import annotations

from typing import List, TypedDict

from .base import DbResource


class NodePayload(TypedDict, total=False):
    """docs/manual/03_DB_Node_Element.md #1 — /db/NODE Specifications table."""

    X: float  # Coordinates - x, default 0, optional
    Y: float  # Coordinates - y, default 0, optional
    Z: float  # Coordinates - z, default 0, optional


class Node(DbResource):
    ENDPOINT = "/db/NODE"
    NAME = "Node"
    PRODUCTS = frozenset({"gen", "civil"})


class ElementPayload(TypedDict, total=False):
    """docs/manual/03_DB_Node_Element.md #2 — /db/ELEM Specifications table.

    Only the common + Beam/Truss fields are typed here for v1. ELEM has many
    more STYPE-conditional fields (Cable/Compression-only Truss, Wall,
    Plate, Solid, ...) documented in the manual's per-subtype tables —
    pass them as extra dict keys; DbResource does not validate payloads.
    """

    TYPE: str  # Element Type, default "BEAM", optional. e.g. "BEAM","TRUSS","PLATE","WALL","SOLID"
    MATL: int  # Material No., required
    SECT: int  # Section / Thickness No., required
    NODE: List[int]  # Node No. list, required
    ANGLE: float  # Beta Angle (Beam/Truss/Plane Strain/Axisymmetric), default 0, optional
    STYPE: int  # Element Subtype (meaning depends on TYPE), optional


class Element(DbResource):
    ENDPOINT = "/db/ELEM"
    NAME = "Element"
    PRODUCTS = frozenset({"gen", "civil"})


class SkewPayload(TypedDict, total=False):
    """docs/manual/03_DB_Node_Element.md #3 — /db/SKEW Specifications table.

    Shape depends on iMETHOD: 1=Angle (ANGLE_*), 2=3 Points (P0*/P1*/P2*),
    3=Vector (V1*/V2*), 4=Line Vector (LV0*/LV1*/LV2* + REFTYPE/G_DIR/L_DIR).

    `iMETHOD` defaults to `1` (Angle) when omitted -- live-verified 2026-08-27
    on Gen NX: POST `{"ANGLE_X": 15, "ANGLE_Y": 0, "ANGLE_Z": 0}` (iMETHOD
    omitted) against a probe node round-tripped through GET as
    `{"iMETHOD": 1, ...}`. Corrects the manual's own Specifications table,
    which lists `iMETHOD` as Optional with no default shown; the 2026-08-25
    re-verification note (article id `35807178748569`) called out `1` as the
    real default.
    """

    iMETHOD: int  # 1=Angle, 2=3 Points, 3=Vector, 4=Line Vector; optional, default 1 (Angle)
    ANGLE_X: float  # iMETHOD=1, default 0
    ANGLE_Y: float  # iMETHOD=1, default 0
    ANGLE_Z: float  # iMETHOD=1, default 0
    P0X: float  # iMETHOD=2, default 0
    P0Y: float  # iMETHOD=2, default 0
    P0Z: float  # iMETHOD=2, default 0
    P1X: float  # iMETHOD=2, default 0
    P1Y: float  # iMETHOD=2, default 0
    P1Z: float  # iMETHOD=2, default 0
    P2X: float  # iMETHOD=2, default 0
    P2Y: float  # iMETHOD=2, default 0
    P2Z: float  # iMETHOD=2, default 0
    V1X: float  # iMETHOD=3, default 0
    V1Y: float  # iMETHOD=3, default 0
    V1Z: float  # iMETHOD=3, default 0
    V2X: float  # iMETHOD=3, default 0
    V2Y: float  # iMETHOD=3, default 0
    V2Z: float  # iMETHOD=3, default 0
    LV0X: float  # iMETHOD=4, default 0
    LV0Y: float  # iMETHOD=4, default 0
    LV0Z: float  # iMETHOD=4, default 0
    LV1X: float  # iMETHOD=4, default 0
    LV1Y: float  # iMETHOD=4, default 0
    LV1Z: float  # iMETHOD=4, default 0
    LV2X: float  # iMETHOD=4, default 0
    LV2Y: float  # iMETHOD=4, default 0
    LV2Z: float  # iMETHOD=4, default 0
    REFTYPE: int  # iMETHOD=4 only: 1=Ref. Point (P0,P1 required), 2=Global Direction (P0 required); required
    G_DIR: int  # iMETHOD=4 only: Global X=0, Global Y=1, Global Z=2; required
    L_DIR: int  # iMETHOD=4 only: Local x=0, Local y=1, Local z=2; required


class Skew(DbResource):
    ENDPOINT = "/db/SKEW"
    NAME = "Node Local Axis"
    PRODUCTS = frozenset({"gen", "civil"})


class MainDomainPayload(TypedDict, total=False):
    """docs/manual/03_DB_Node_Element.md #4 — /db/MADO Specifications table."""

    NAME: str  # Domain Name, required
    TYPE: int  # Element Type: Plane Stress=3, Plate=4, Plane Strain=6, Axisymmetric=7; required
    MATL: int  # Material ID, required
    PROP: int  # Element Property, required
    SUB_TYPE: int  # Sub Type, required


class MainDomain(DbResource):
    ENDPOINT = "/db/MADO"
    NAME = "Define Domain"
    PRODUCTS = frozenset({"gen", "civil"})


class SubDomainPayload(TypedDict, total=False):
    """docs/manual/03_DB_Node_Element.md #5 — /db/SBDO Specifications table.

    Common keys plus CIVIL NX-only (MEMB_TYPE_CIVIL, REBAR_AXIS_TYPE,
    STR_UCS, AXIS_VECTOR) and GEN NX-only (MEMBER_TYPE, rebar layout,
    bUseMt, THICKNESS) keys — pass only the ones for the active product.
    """

    SUB_DOMAIN_NAME: str  # required
    V1: float  # Rebar Dir.1, required
    V2: float  # Rebar Dir.2, required
    DOMAIN_NAME: str  # required
    # CIVIL NX only
    MEMB_TYPE_CIVIL: int  # None=0, Plate Beam (1D)=1, Plate Column (1D)=2, Shell=3; required
    REBAR_AXIS_TYPE: int  # Local=0, UCS=1, Reference Axis=2; default 0
    STR_UCS: str  # when REBAR_AXIS_TYPE=UCS; default blank
    AXIS_VECTOR: List[float]  # when REBAR_AXIS_TYPE=Reference Axis; default 0
    # GEN NX only
    MEMBER_TYPE: int  # None=0, Slab=1, Mat=2; required
    OPT_BASIC_REBAR: bool  # default false
    TOP_REBAR_NAME_X: str  # default blank
    TOP_REBAR_SPACE_X: float  # default 0
    BOTTOM_REBAR_NAME_X: str  # default blank
    BOTTOM_REBAR_SPACE_X: float  # default 0
    TOP_REBAR_NAME_Y: str  # default blank
    TOP_REBAR_SPACE_Y: float  # default 0
    BOTTOM_REBAR_NAME_Y: str  # default blank
    BOTTOM_REBAR_SPACE_Y: float  # default 0
    OPT_REBAR_MATL: bool  # default false
    REBAR_MATL_KEY: int  # default 0
    bUseMt: bool  # required
    THICKNESS: float  # required


class SubDomain(DbResource):
    ENDPOINT = "/db/SBDO"
    NAME = "Define Sub-Domain"
    PRODUCTS = frozenset({"gen", "civil"})


class DomainElementPayload(TypedDict, total=False):
    """docs/manual/03_DB_Node_Element.md #6 — /db/DOEL Specifications table."""

    TYPE: int  # Domain Type: Main-Domain=0, Sub-Domain=1; required
    KEY_DOMAIN: int  # Key Domain, required
    MAIN_DOMAIN_NAME: str  # Main Domain Name, required


class DomainElement(DbResource):
    ENDPOINT = "/db/DOEL"
    NAME = "Domain-Element"
    PRODUCTS = frozenset({"gen", "civil"})
