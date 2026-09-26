"""Source: docs/manual/17_DB_Bridge.md, items 1-4.

MIDAS Civil NX only (bridge specialization results): girder diagrams
(`GSBG`) and camber control (General/FCM: `GCMB`/`CAMB`) — all three
confirmed 404 on Gen NX (route + `/info`), live-checked 2026-07-29.
`UnknownLoadFactorConstraint` (`ULFC`) is the exception: it answers on Gen
too (empty table; route + `/info` both resolve), so it's left at the class
default (gen+civil) rather than `CIVIL_ONLY` — see db/base.py's `GEN_ONLY`
docstring's sibling note.

Item 5 in this chapter as of the manual's 2026-08-10 sync, `/ope/GSBG`
(Bridge Girder Diagram Image Export), is not a new endpoint despite the
new item number — it's the same `/ope/GSBG` this SDK already implements
as `ope.generate_bridge_girder_diagram()`, sourced from and still
documented at `docs/manual/15_OPE.md` #19. The manual now documents it a
second time here too, field-for-field identical; no SDK change needed.
"""
from __future__ import annotations

from typing import List, TypedDict

from .base import CIVIL_ONLY, DbResource

# --- 1. /db/GSBG — Bridge Girder Diagrams ------------------------------------


class BridgeGirderDiagramPayload(TypedDict, total=False):
    """docs/manual/17_DB_Bridge.md #1 — /db/GSBG Specifications table.

    DGRM_TYPE selects between the Beam Stresses field group (BSTRSCOMP,
    BSTRSCOMP_SUB, _7TH_DOF_TYPE) and the Beam Forces/Moments field group
    (MOMENT_COMP); flattened onto one payload (mirrors MaterialParam
    precedent).
    """

    NAME: str  # Group Name, required
    BATCH: bool  # Is Batch, default true, required
    BODY_ELEM_GRUP_K: int  # Bridge Girder Element Group, required
    ALLSTAGE: bool  # current stage-step=false/all stages(last step)=true, default false, optional
    DGRM_TYPE: int  # Beam Stresses=0/Beam Forces-Moments=1, default 0, optional
    BSTRSCOMP: int  # Sax=0/+Sby=1/-Sby=2/+Sbz=3/-Sbz=4/Combined=5/7th DOF=6, default 0, required if DGRM_TYPE=0
    BSTRSCOMP_SUB: int  # Maximum=0/1(-y,+z)=1/2(+y,+z)=2/3(+y,-z)=3/4(-y,-z)=4, default 0, required if DGRM_TYPE=0 and BSTRSCOMP=6
    _7TH_DOF_TYPE: int  # Sax(Warping)=0/Ssy(Mt)=1/Ssy(Mw)=2/Ssz(Mt)=3/Ssz(Mw)=4/Combined(Ssy)=5/Combined(Ssz)=6, default 0, required if DGRM_TYPE=0 and BSTRSCOMP=6
    MOMENT_COMP: int  # Fx=0/Fy=1/Fz=2/Mx=3/My=4/Mz=5/Mb=6/Mt=7/Mw=8, default 0, required if DGRM_TYPE=1
    SCALEFACTOR: float  # default 0, optional


class BridgeGirderDiagram(DbResource):
    ENDPOINT = "/db/GSBG"
    NAME = "Bridge Girder Diagrams"
    PRODUCTS = CIVIL_ONLY


# --- 2. /db/GCMB — General Camber Control ------------------------------------


class GeneralCamberBaseItem(TypedDict, total=False):
    GRUP_NAME: str  # Structure Group Name, required
    DIRECTION: str  # "+DX"/"-DX"/"+DY"/"-DY", required


class GeneralCamberControlPayload(TypedDict, total=False):
    """docs/manual/17_DB_Bridge.md #2 — /db/GCMB Specifications table."""

    bSTART_PT_ZERO: bool  # Set Start Point to Zero, default true, optional
    GCMB_BASE_ITEMS: List[GeneralCamberBaseItem]  # required


class GeneralCamberControl(DbResource):
    ENDPOINT = "/db/GCMB"
    NAME = "General Camber Control"
    PRODUCTS = CIVIL_ONLY


# --- 3. /db/CAMB — FCM Camber Control -----------------------------------------


class FcmCamberControlPayload(TypedDict, total=False):
    """docs/manual/17_DB_Bridge.md #3 — /db/CAMB Specifications table."""

    BODY_GROUP_NAME: str  # Bridge Girder Element Group, required
    SUPP_GROUP_NAME: str  # Support Node Group, required
    KEYSEG_GROUP_NAME: str  # Key Segment Element Group, required


class FcmCamberControl(DbResource):
    ENDPOINT = "/db/CAMB"
    NAME = "FCM Camber Control"
    PRODUCTS = CIVIL_ONLY


# --- 4. /db/ULFC — Cable Control - Unknown Load Factor Constraints ----------


class UnknownLoadFactorConstraintPayload(TypedDict, total=False):
    """docs/manual/17_DB_Bridge.md #4 — /db/ULFC Specifications table.

    EQ selects between the Equality field group (bVALUE, VALUE, OtherObject)
    and the Inequality field group (bUB, UB_VALUE, bLB, LB_VALUE); flattened
    onto one payload (mirrors MaterialParam precedent).
    """

    NAME: str  # Constraint Name, required
    TYPE: str  # Reaction="REAC"/Displacement="DISP"/Truss Force="TRUSS"/Beam Force="BEAM", required
    OBJ_ID: int  # Element/Node ID, required
    # I-end=0/1-4=1/2-4=2/3-4=3/J-end=4. The manual marks this "required if
    # TYPE=BEAM" (it's only semantically meaningful there), but live-confirmed
    # 2026-08-17: it's actually required unconditionally -- a TYPE="REAC"
    # payload without it answers "Wrong Field"; send 0 for non-BEAM types.
    POINT: int
    COMP: int  # FX-DX-Iend=0/FY-DY-Jend=1/FZ-DZ=2/MX-RX=3/MY-RY=4/MZ-RZ=5, required
    EQ: bool  # Equality=true/Inequality=false, default false, optional
    bVALUE: bool  # Check Value, default false, optional (EQ=true)
    VALUE: float  # required if EQ=true
    OtherObject: int  # default 0, optional (EQ=true and bVALUE=false)
    bUB: bool  # Check Upper Bound, default false, optional (EQ=false)
    UB_VALUE: float  # required if EQ=false
    bLB: bool  # Check Lower Bound, default false, optional (EQ=false)
    LB_VALUE: float  # required if EQ=false


class UnknownLoadFactorConstraint(DbResource):
    ENDPOINT = "/db/ULFC"
    NAME = "Cable Control – Unknown Load Factor Constraints"
