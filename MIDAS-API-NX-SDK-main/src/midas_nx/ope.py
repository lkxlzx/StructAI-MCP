"""``/ope/*`` — GUI/preprocessing operations not persisted to the DB.

Source: docs/manual/15_OPE.md, items 1-19. Request bodies are wrapped in an
``"Argument"`` key like doc.py (not ID-keyed ``"Assign"``), but most of these
endpoints have deeply-nested, highly-optional bodies (10+ levels in places),
so each POST function takes one TypedDict ``argument`` parameter instead of
doc.py's style of exploding fields into many kwargs. GET-only endpoints
(PROJECTSTATUS, SECTPROP) take no argument at all.
"""
from __future__ import annotations

from typing import List, Optional, TypedDict, Union

from .client import MidasClient, MidasRequestError
from .client import get_result as _get
from .client import post_argument as _post

# --- 1. /ope/PROJECTSTATUS — Project Status ---------------------------------


def get_project_status(client: Optional[MidasClient] = None) -> dict:
    """docs/manual/15_OPE.md #1 — /ope/PROJECTSTATUS — Project Status.

    GET-only, no request body; returns live counts of model/load data.
    """
    return _get("/ope/PROJECTSTATUS", client)


# --- 2. /ope/DIVIDEELEM — Divide Elements ------------------------------------


class NumberOption(TypedDict, total=False):
    """Shared {NUMBER_OPTION, USER_NUM} shape for DIVIDEELEM's
    START_NUMBER.NODE_NUMBER / START_NUMBER.ELEM_NUMBER."""

    NUMBER_OPTION: str  # "Smallest"/"Largest"/"User", optional
    USER_NUM: int  # user-specified number, required if NUMBER_OPTION="User"


class DivideStartNumber(TypedDict, total=False):
    NODE_NUMBER: NumberOption  # optional
    ELEM_NUMBER: NumberOption  # optional


class DivideEqualOption(TypedDict, total=False):
    """DIV_METHOD="Equal": which axes are required depends on ELEM_TYPE
    (Frame=X only, Planar=X+Y, Wall=X+Z, Solid=X+Y+Z)."""

    NUM_X: int  # division count in X, required
    NUM_Y: int  # division count in Y, required for Planar/Solid
    NUM_Z: int  # division count in Z, required for Wall/Solid


class DivideUnequalOption(TypedDict, total=False):
    """DIV_METHOD="Unequal": distance strings, e.g. "3@2.0" (3 segments of 2.0)."""

    DIST_X: str  # required
    DIST_Y: str  # required
    DIST_Z: str  # required


class DivideParametricOption(TypedDict, total=False):
    """DIV_METHOD="ParametricUnequal": ratio strings, e.g. "3@0.3"."""

    RATIO_X: str  # required
    RATIO_Y: str  # required
    RATIO_Z: str  # required


class DivideParallelOption(TypedDict, total=False):
    """DIV_METHOD="ParallelBracing"."""

    NUM_OF_DIVISIONS: int  # required
    MAIN_POST_ELEM: List[int]  # reference post/column elements, required


class DivideByNodeOption(TypedDict, total=False):
    """DIV_METHOD="DividebyNode"."""

    ELEM_NUM: int  # target element, required
    NODE_NUM: int  # split reference node, required


class DivideOption(TypedDict, total=False):
    """Only the sub-object matching DIVIDE.DIV_METHOD is used."""

    EQUAL_OPTION: DivideEqualOption  # required if DIV_METHOD="Equal"
    UNEQUAL_OPTION: DivideUnequalOption  # required if DIV_METHOD="Unequal"
    PARAMETRIC_OPTION: DivideParametricOption  # required if DIV_METHOD="ParametricUnequal"
    PARALLEL_OPTION: DivideParallelOption  # required if DIV_METHOD="ParallelBracing"
    BY_NODE_OPTION: DivideByNodeOption  # required if DIV_METHOD="DividebyNode"


class MergeDuplicateNodesOption(TypedDict, total=False):
    OPT_CHECK: bool  # optional
    TOLERANCE: float  # merge tolerance, optional


class DivideSettings(TypedDict, total=False):
    ELEM_TYPE: str  # "Frame"/"Wall"/"Planar"/"Solid", required
    DIV_METHOD: str  # "Equal"/"Unequal"/"ParametricUnequal"/"ParallelBracing"/"DividebyNode", required
    OPTION: DivideOption  # required
    SUBDIVIDE_ELEM: bool  # re-subdivide line elements, optional
    MERGE_DUPLICATE_NODES: MergeDuplicateNodesOption  # optional


class DivideElementsArgument(TypedDict, total=False):
    """docs/manual/15_OPE.md #2 — /ope/DIVIDEELEM — Divide Elements.

    DIVIDE.DIV_METHOD selects which single sub-object of DIVIDE.OPTION
    (EQUAL_OPTION/UNEQUAL_OPTION/PARAMETRIC_OPTION/PARALLEL_OPTION/
    BY_NODE_OPTION) is required (mirrors the MaterialParam precedent in
    properties/material.py).
    """

    TARGETS: List[int]  # elements to divide, optional
    START_NUMBER: DivideStartNumber  # starting node/element numbering, optional
    DIVIDE: DivideSettings  # required


def divide_elements(argument: DivideElementsArgument, client: Optional[MidasClient] = None) -> dict:
    """docs/manual/15_OPE.md #2 — /ope/DIVIDEELEM — Divide Elements."""
    return _post("/ope/DIVIDEELEM", argument, client)


# --- 3. /ope/SECTPROP — Section Properties Calculation Results --------------


def get_section_properties(client: Optional[MidasClient] = None) -> dict:
    """docs/manual/15_OPE.md #3 — /ope/SECTPROP — Section Properties Calculation Results.

    GET-only, no request body; response is keyed by section ID.
    """
    return _get("/ope/SECTPROP", client)


# --- 4. /ope/USLC — Using Load Combinations ----------------------------------


class LoadCombinationRef(TypedDict, total=False):
    TYPE: str  # "GEN"/"STEEL"/"CONC"/"SRC"/"STLCOMP"/"SEISMIC", required
    NAME: str  # load combination name, required


class UsingLoadTypes(TypedDict, total=False):
    """Which load categories to include when generating design combinations
    from the LCOM_LIST entries; each defaults to true if omitted."""

    SELF_WEIGHT: bool  # default true, optional
    NODAL_BODY_FROCE: bool  # [sic, matches manual's "FROCE" spelling] Nodal Body Force, default true, optional
    NODAL_LOAD: bool  # default true, optional
    SPECIFIED_DISPLACEMENT: bool  # default true, optional
    BEAM_LOAD: bool  # default true, optional
    FLOOR_LOAD: bool  # default true, optional
    FINISHING_MATERIAL_LOAD: bool  # default true, optional
    PRESSURE_LOAD: bool  # default true, optional
    PLANE_LOAD: bool  # default true, optional
    SYSTEM_TEMPERATURE: bool  # default true, optional
    NODAL_TEMPERATURE: bool  # default true, optional
    ELEMENT_TEMPERATURE: bool  # default true, optional
    TEMPERATURE_GRADIENT: bool  # default true, optional
    BEAM_SECTION_TEMPERATURE: bool  # default true, optional
    PRESTRESS_LOAD: bool  # default true, optional
    PRETENSION_LOAD: bool  # default true, optional
    TENDON_PRESTRESS_LOAD: bool  # default true, optional


class UsingLoadCombinationsArgument(TypedDict, total=False):
    """docs/manual/15_OPE.md #4 — /ope/USLC — Using Load Combinations."""

    PREFIX: str  # load case/design combination name prefix, default System, optional
    POSITION: str  # design target: "STEEL"/"CONC"/"SRC", required
    LCOM_LIST: List[LoadCombinationRef]  # selected combinations, required
    LOADS: UsingLoadTypes  # load categories to include, optional


def use_load_combinations(argument: UsingLoadCombinationsArgument, client: Optional[MidasClient] = None) -> dict:
    """docs/manual/15_OPE.md #4 — /ope/USLC — Using Load Combinations."""
    return _post("/ope/USLC", argument, client)


# --- 5. /ope/LINEBMLD — Line Beam Load ---------------------------------------


class LineLoadTarget(TypedDict, total=False):
    """⚠️ Live-tested 2026-07-30 on Gen NX: ``METHOD=0`` (NODE-defined load
    line) works exactly as documented, but ``METHOD=1`` (selected elements)
    consistently answered ``{"error": {"message": "Wrong Field"}}`` across
    3 reproductions varying TYPE (UNILOAD/CONLOAD) and LOAD.D/P shape, with
    ``ELEM`` pointing at a real, existing element each time. Not yet
    isolated further (no extra field discovered that fixes it) — treat
    ``METHOD=1`` as unconfirmed/possibly broken and prefer ``METHOD=0``
    until this is re-tested.
    """

    METHOD: int  # on load line=0 / selected elements=1, required
    ELEM: List[int]  # target elements, required if METHOD=1
    NODE: List[int]  # 2 nodes defining the load line, required if METHOD=0


class LineLoadEccentricity(TypedDict, total=False):
    """Only usable when TYPE is CONLOAD/UNILOAD/TRALOAD/CURVED."""

    USE: bool  # default false
    TYPE: int  # centroid=0 / offset=1
    DIR: str  # "LY"/"LZ"/"GX"/"GY"/"GZ"
    I_END: float  # I-end eccentricity
    J_END: float  # J-end eccentricity, required if USE_J_END true
    USE_J_END: bool


class LineLoadAdditionalHeight(TypedDict, total=False):
    """Only usable when TYPE is UNIPRESSURE/TRAPRESSURE."""

    USE: bool  # default false
    I_END: float  # I-end value
    J_END: float  # J-end value, required if USE_J_END true
    USE_J_END: bool


class LineLoadValue(TypedDict, total=False):
    DIR: str  # local/global direction; UNIPRESSURE/TRAPRESSURE limited to LY/LZ per ADD_H, required
    USE_PROJECTION: bool  # default depends on TARGET.METHOD (0->false, 1->true), optional
    TYPE: int  # relative=0/absolute=1, required except for TYPE="CURVED"
    D: List[float]  # distances [x1,x2,x3,x4], required except for TYPE="CURVED"
    P: List[float]  # magnitudes [P1,P2,P3,P4], required except for TYPE="CURVED"
    A: float  # curve coefficient a, required only for TYPE="CURVED"
    B: float  # curve coefficient b, required only for TYPE="CURVED"
    C: float  # curve coefficient c, required only for TYPE="CURVED"


class LineLoadCopy(TypedDict, total=False):
    USE: bool  # default false
    AXIS: str  # "X"/"Y"/"Z"
    DIST: str  # e.g. "10@3.0"


class LineBeamLoadArgument(TypedDict, total=False):
    """docs/manual/15_OPE.md #5 — /ope/LINEBMLD — Line Beam Load."""

    LCNAME: str  # load case name, required
    GROUP_NAME: str  # load group name, optional
    TYPE: str  # "CONLOAD"/"CONMOMENT"/"UNILOAD"/"UNIMOMENT"/"TRALOAD"/"TRAMOMENT"/"UNIPRESSURE"/"TRAPRESSURE"/"CURVED", required
    TARGET: LineLoadTarget  # required
    ECCEN: LineLoadEccentricity  # eccentricity option, optional (CONLOAD/UNILOAD/TRALOAD/CURVED only)
    ADD_H: LineLoadAdditionalHeight  # additional top height option, optional (UNIPRESSURE/TRAPRESSURE only)
    LOAD: LineLoadValue  # required
    COPY: LineLoadCopy  # copy option, optional


def create_line_beam_load(argument: LineBeamLoadArgument, client: Optional[MidasClient] = None) -> dict:
    """docs/manual/15_OPE.md #5 — /ope/LINEBMLD — Line Beam Load."""
    return _post("/ope/LINEBMLD", argument, client)


# --- 6. /ope/AUTOMESH — Auto-Mesh Planar Area --------------------------------


class InteriorInclusionOption(TypedDict, total=False):
    """Shared shape for MESHER.INCLUDE_INTERIOR_NODES / INCLUDE_INTERIOR_LINES."""

    OPT_CHECK: bool  # default true, optional
    OPTION: str  # "Auto"/"User", default "Auto", optional
    VALUE: List[int]  # included node/line IDs, required if OPTION="User"


class AutoMesher(TypedDict, total=False):
    """⚠️ 2026-08-27: the manual's 2026-08-26 re-verification (article id
    `35736427971225`) claims `METHOD`/`TYPE` (and `AutoMeshProperty.
    ELEMENT_TYPE` below) should be space-stripped (`"LineElements"`,
    `"Quadandtriangle"`, `"PlaneStress"`) rather than the Specifications
    table's human-readable spaced form, reasoning the worked
    Request/Response examples use the stripped form. **Attempted to
    live-test on Gen NX; inconclusive** -- a POST with `METHOD="Nodes"`/
    `TYPE="Quadrilateral"` (both single-word, so this particular attempt
    didn't actually exercise the disputed multi-word values either way)
    failed with a generic `"MIDAS GEN NX second query is wrong"` error not
    obviously about field spelling. Not pursued further this session. Left
    at the table's spaced form -- **not** applying the manual's claim
    unverified, per this project's own precedent
    (StoryIrregularityCheckParameterArgument above, where an identical
    "example uses stripped literals" claim from a different chapter turned
    out to be backwards against real live evidence). Needs a real
    successful `/ope/AUTOMESH` round trip with a multi-word value to
    settle either way.
    """

    METHOD: str  # "Nodes"/"Line Elements"/"Planar Elements", default "Line Elements", optional -- see class docstring, unresolved
    TARGETS: List[int]  # nodes/elements bounding the mesh area, required
    TYPE: str  # "Quadrilateral"/"Quad and Triangle"/"Triangle", default "Quadrilateral", optional -- see class docstring, unresolved
    MESH_INNER_DOMAIN: bool  # default false, optional
    INCLUDE_INTERIOR_NODES: InteriorInclusionOption  # optional
    INCLUDE_INTERIOR_LINES: InteriorInclusionOption  # optional
    INCLUDE_BOUNDARY_CONNECTIVITY: bool  # default true, optional


class AutoMeshSize(TypedDict, total=False):
    """LENGTH and DIV are mutually exclusive; exactly one is required."""

    LENGTH: float  # target element edge length, required unless DIV given
    DIV: int  # target division count, required unless LENGTH given


class AutoMeshElementSubType(TypedDict, total=False):
    TYPE: str  # "Thick"/"Thin", used when PROPERTY.ELEMENT_TYPE="Plate", default "Thick", optional
    WITH_DRILLING_DOF: bool  # used when ELEMENT_TYPE is "Plate"/"Plane Stress", default true, optional


class AutoMeshProperty(TypedDict, total=False):
    ELEMENT_TYPE: str  # "Plate"/"Plane Stress"/"Plane Strain"/"Axisymmetric", default "Plate", optional
    ELEMENT_SUB_TYPE: AutoMeshElementSubType  # optional
    MATERIAL: int  # material ID, required
    THICKNESS: int  # thickness ID, optional (Plate/Plane Stress only)


class AutoMeshDomainName(TypedDict, total=False):
    NAME: str  # mesh domain/group name, required


class AutoMeshAdditionalOption(TypedDict, total=False):
    DELETE_LINE_ELEM: bool  # delete original line/boundary elements, default false, optional
    SUBDIVIDE_LINE_ELEM: bool  # re-subdivide original line/boundary elements, default true, optional


class AutoMeshArgument(TypedDict, total=False):
    """docs/manual/15_OPE.md #6 — /ope/AUTOMESH — Auto-Mesh Planar Area."""

    MESHER: AutoMesher  # required
    MESH_SIZE: AutoMeshSize  # required
    PROPERTY: AutoMeshProperty  # required
    DOMAIN_NAME: AutoMeshDomainName  # required
    ADDITIONAL_OPTION: AutoMeshAdditionalOption  # optional


def auto_mesh(argument: AutoMeshArgument, client: Optional[MidasClient] = None) -> dict:
    """docs/manual/15_OPE.md #6 — /ope/AUTOMESH — Auto-Mesh Planar Area."""
    return _post("/ope/AUTOMESH", argument, client)


# --- 7. /ope/SSPS — Surface Spring -------------------------------------------


class TargetKeys(TypedDict, total=False):
    """Shared explicit-ID-list shape, used by SSPS's and EDMP's NODE_ELEMS."""

    KEYS: List[int]  # target node/element numbers, e.g. [101, 102, 103], required


class SurfaceSpringElement(TypedDict, total=False):
    TYPE: str  # "FRAME"/"PLANAR"/"SOLID_FACE"/"SOLID_NODE", required
    FACE: int  # face number 1-6, required if TYPE="SOLID_FACE"
    WIDTH: float  # required if TYPE="FRAME"


class SurfaceSpringBoundary(TypedDict, total=False):
    """Required-ness of each field depends on the CONVERT_TO x TYPE combo —
    see the manual's Parameters table note (mirrors MaterialParam precedent)."""

    TYPE: str  # "LINEAR"/"COMP"/"TENS"/"MULTI", required
    STIFF: List[float]  # [Kx,Ky,Kz], required for LINEAR/MULTI
    bDAMP: bool  # consider damping, required for LINEAR/MULTI
    DAMP: List[float]  # [Cx,Cy,Cz], required for LINEAR/MULTI
    DIR: int  # boundary direction 0-7 (Normal+/-, UCS-x/y/z +/-), required for COMP/TENS and most other cases
    SUBGRADE: float  # subgrade reaction modulus, required for COMP/TENS and all ELASTIC_LINK types
    PHU: float  # ultimate strength, required for MULTI (point spring and elastic link)
    LENGTH: float  # elastic link length, required when CONVERT_TO="ELASTIC_LINK"


class SurfaceSpringArgument(TypedDict, total=False):
    """docs/manual/15_OPE.md #7 — /ope/SSPS — Surface Spring."""

    CONVERT_TO: str  # "POINT_SPRING"/"ELASTIC_LINK", required
    GROUP_NAME: str  # boundary group name, default "", optional
    NODE_ELEMS: TargetKeys  # required
    ELEMENT: SurfaceSpringElement  # required
    BOUNDARY: SurfaceSpringBoundary  # required


def convert_surface_spring(argument: SurfaceSpringArgument, client: Optional[MidasClient] = None) -> dict:
    """docs/manual/15_OPE.md #7 — /ope/SSPS — Surface Spring."""
    return _post("/ope/SSPS", argument, client)


# --- 8. /ope/EDMP — Change Property ------------------------------------------


class ChangePropertyArgument(TypedDict, total=False):
    """docs/manual/15_OPE.md #8 — /ope/EDMP — Change Property.

    Used to set the Notional Size of Member / Volume Surface Ratio needed for
    creep & shrinkage calculations.
    """

    NODE_ELEMS: TargetKeys  # required
    TYPE: str  # "NSM" (notional size)/"VSR" (volume surface ratio), default "NSM", optional
    AUTO: bool  # auto-calculate; VSR only allows false, default false, optional
    CODE: str  # "Korean Standard"/"CEB-FIP(1990)"/"Japanese Standard"/"Chinese Standard"; used when AUTO=true and TYPE="NSM", default "Korean Standard", optional
    PARAMETER: float  # parameter value (a), required if AUTO=false
    H_VS: float  # change value: NSM->h / VSR->v/s, required


def change_property(argument: ChangePropertyArgument, client: Optional[MidasClient] = None) -> dict:
    """docs/manual/15_OPE.md #8 — /ope/EDMP — Change Property."""
    return _post("/ope/EDMP", argument, client)


# --- 9. /ope/STOR — Story Calculation ----------------------------------------


class SeismicAccidentalEccentricity(TypedDict, total=False):
    INC_SEIS_ECC: bool  # include seismic accidental eccentricity, required
    SEIS_ECC_VALUE: float  # eccentricity value (%), required


class WindAccidentalEccentricity(TypedDict, total=False):
    INC_WIND_ECC: bool  # include wind eccentricity, required
    WIND_ECC_VALUE: float  # eccentricity value (%), required


class StoryCalculationArgument(TypedDict, total=False):
    """docs/manual/15_OPE.md #9 — /ope/STOR — Story Calculation."""

    SEIS_ECC: SeismicAccidentalEccentricity  # required
    WIND_ECC: WindAccidentalEccentricity  # required


def calculate_story(argument: StoryCalculationArgument, client: Optional[MidasClient] = None) -> dict:
    """docs/manual/15_OPE.md #9 — /ope/STOR — Story Calculation.

    ⚠️ Confirmed 2026-08-11: 404s on Civil NX (v2.2, build 08/11/2026),
    both `SEIS_ECC`/`WIND_ECC` disabled, on a blank document — first
    direct test of this endpoint against Civil. Matches the same
    Gen-only pattern already confirmed for the rest of the story family
    (`STORY_PARAM`, `STORY_IRR_PARAM`, `STORYPROP`, and the `/post/TABLE`
    story-table types) — the whole story feature set looks to be
    unregistered on Civil, not just this one endpoint.
    """
    return _post("/ope/STOR", argument, client)


# --- 10. /ope/STORY_PARAM — Story Check Parameter ----------------------------


class StoryCheckParameterArgument(TypedDict, total=False):
    """docs/manual/15_OPE.md #10 — /ope/STORY_PARAM — Story Check Parameter.

    ⚠️ 2026-08-27: `COUNTRY_CODE`'s value was `"NTCS2020"`; the manual's
    2026-08-26 re-verification (article id `49514705474457`) corrects it
    to `"NTC2020"` (no S) specifically for *this* endpoint, per its own
    Specifications table — the same value has an S (`"NTCS2020"`) on the
    sibling `StoryIrregularityCheckParameterArgument` below, and the
    manual explicitly calls out that the two endpoints use different
    literals for the same code. Not independently live-tested (needs a
    real story/building model this session's scratch document doesn't
    have); table-sourced only, no worked example uses this value either
    way.
    """

    COUNTRY_CODE: str  # "NTC2012"/"NTC2008"/"KBC2009"/"NSR-10"/"NTC2018"/"NTC2020"(no S -- differs from the STORY_IRR_PARAM sibling's "NTCS2020")/"IS1893(2016)"/"IS16700(2023)", required


def get_story_check_parameter(client: Optional[MidasClient] = None) -> dict:
    """docs/manual/15_OPE.md #10 — /ope/STORY_PARAM — Story Check Parameter (GET).

    Live-confirmed Gen NX only (404 on Civil, twice independently, 2026-07-29)
    — see db/base.py's GEN_ONLY docstring. Not enforced here: unlike
    db/*/design/* resources, plain doc/ope/view functions have no PRODUCTS
    gate in this SDK, so a Civil call reaches the server and 404s there
    rather than raising client-side.
    """
    return _get("/ope/STORY_PARAM", client)


def set_story_check_parameter(argument: StoryCheckParameterArgument, client: Optional[MidasClient] = None) -> dict:
    """docs/manual/15_OPE.md #10 — /ope/STORY_PARAM — Story Check Parameter (POST)."""
    return _post("/ope/STORY_PARAM", argument, client)


# --- 11. /ope/STORY_IRR_PARAM — Story Irregularity Check Parameter ----------


class StoryIrregularityCheckParameterArgument(TypedDict, total=False):
    """docs/manual/15_OPE.md #11 — /ope/STORY_IRR_PARAM — Story Irregularity Check Parameter.

    ⚠️ 2026-07-29 correction: an earlier draft of this docstring followed the
    manual's worked POST-request/response JSON example, which sends
    STORY_DRIFT_METHOD/STORY_STIFFNESS_METHOD/SEISMIC_BEHAVIOR_FACTOR
    space-stripped (e.g. "Max.DriftofOuterExtremePoints", "1/StoryDriftRatio",
    "3orbelow"), over the Parameters table's space-containing rendering (e.g.
    "Max. Drift of Outer Extreme Points", "1 / Story Drift Ratio",
    "3 or below") — reasoning the worked example was the more concrete
    source. Live evidence against a real production Gen NX model
    contradicts that: `GET /ope/STORY_IRR_PARAM` returned
    ``{"STORY_DRIFT_METHOD": "Drift at the Center of Mass",
    "STORY_STIFFNESS_METHOD": "1 / Story Drift Ratio"}`` — the
    space-containing form, matching the Parameters table and matching the
    sibling `post/story.py` STORY_DRIFT endpoint's own live-confirmed
    convention. The manual's worked example for this chapter is the outlier;
    space-containing is now documented as canonical. Not enforced at
    runtime either way (TypedDicts here are documentation, not validation).
    """

    COUNTRY_CODE: str  # "NTC2018"/"NTC2012"/"NTC2008"/"KBC2009"/"NSR-10"/"NTCS2020"/"NTCS2023"/"NSCP2015"/"IS1893(2016)"/"IS16700(2023)", required
    STORY_DRIFT_METHOD: str  # "Drift at the Center of Mass"/"Max. Drift of Outer Extreme Points"/"Max. Drift of All Vertical Elements", required
    STORY_STIFFNESS_METHOD: str  # "1 / Story Drift Ratio"/"Story Shear / Story Drift", required
    SEISMIC_BEHAVIOR_FACTOR: str  # "4"/"3 or below", required if COUNTRY_CODE in {"NTCS2023", "NTCS2020"}


def get_story_irregularity_check_parameter(client: Optional[MidasClient] = None) -> dict:
    """docs/manual/15_OPE.md #11 — /ope/STORY_IRR_PARAM — Story Irregularity Check Parameter (GET).

    Live-confirmed Gen NX only (404 on Civil, twice independently, 2026-07-29)
    — see db/base.py's GEN_ONLY docstring. Not enforced here: unlike
    db/*/design/* resources, plain doc/ope/view functions have no PRODUCTS
    gate in this SDK, so a Civil call reaches the server and 404s there
    rather than raising client-side.
    """
    return _get("/ope/STORY_IRR_PARAM", client)


def set_story_irregularity_check_parameter(
    argument: StoryIrregularityCheckParameterArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/15_OPE.md #11 — /ope/STORY_IRR_PARAM — Story Irregularity Check Parameter (POST)."""
    return _post("/ope/STORY_IRR_PARAM", argument, client)


# --- 12. /ope/STORYPROP — Story Properties ------------------------------------


class StoryPropertiesArgument(TypedDict, total=False):
    """docs/manual/15_OPE.md #12 — /ope/STORYPROP — Story Properties.

    Doc inconsistencies: the Parameters table types FORMAT as an enum of
    "Fixed"/"Scientific", but the worked request example sends "Default"
    (not in that enum) — likely an undocumented third option. The table also
    types PLACE as String, but the worked example sends an integer (4); we
    follow the worked example (int) for PLACE.

    ✅ Root cause found and fixed 2026-08-27: every one of the four 404
    reproductions below (2026-07-30/07-31/08-01) called the misspelled URL
    ``/ope/STORPROP``. The sibling manual repo's full re-verification pass
    against MIDASIT's official pages found the real URL is
    ``/ope/STORYPROP`` (STORY+PROP, not STOR+PROP) — confirmed live the
    same day on Gen NX: ``POST /ope/STORPROP`` still 404s, while
    ``POST /ope/STORYPROP`` routes through cleanly (200, ``"There is no
    valid story information."`` on a document with no Story data — a
    domain error, not a routing error). `get_story_properties()` now posts
    to the corrected URL. The four historical 404s below were never a
    genuinely dead/inactive route; they were hitting a URL that never
    existed.

    Historical 404 reproductions (all against the old, wrong
    ``/ope/STORPROP`` spelling — kept for the record, not evidence of a
    server defect): 2026-07-30 on Gen NX, 3/3 tries, with both
    FORMAT="Fixed" and FORMAT="Default" and with/without populated
    `/db/STOR` records. 2026-07-31 on Civil NX (v2.2 build 07/29/2026)
    against a real production bridge model. 2026-07-31: `GET
    /info/ope/STORPROP` also 404'd on Civil — though this turned out to be
    uninformative too, since `/info/ope/*` routes 404 even for endpoints
    confirmed working via POST (e.g. `/ope/STORY_IRR_PARAM`), so a
    `/info/` 404 says nothing about whether the POST route itself exists.
    2026-08-01: 4th reproduction on a different Gen session/build, still
    404 on the misspelled URL.
    """

    FORCE_UNIT: str  # "N"/"KN"/"KGF"/"TONF"/"LBF"/"KIPS", default System, optional
    LENGTH_UNIT: str  # "M"/"CM"/"MM"/"FT"/"IN", default System, optional
    FORMAT: str  # doc table: "Fixed"/"Scientific"; worked example sends "Default" — see docstring, default System, optional
    PLACE: int  # decimal places 0-15; doc table says String but example sends an int, default System, optional


def get_story_properties(argument: StoryPropertiesArgument, client: Optional[MidasClient] = None) -> dict:
    """docs/manual/15_OPE.md #12 — /ope/STORYPROP — Story Properties.

    POST-only but functions as a query (unit/format-controlled report of
    per-story weight, elevation, loaded height/width). See
    StoryPropertiesArgument's docstring: the URL was ``/ope/STORPROP``
    (missing a Y) until 2026-08-27 -- that was the actual defect behind
    every historical 404, not a dead route.
    """
    return _post("/ope/STORYPROP", argument, client)


# --- 13. /ope/MEMB — Member Assignment ---------------------------------------


class MemberAssignmentArgument(TypedDict, total=False):
    """docs/manual/15_OPE.md #13 — /ope/MEMB — Member Assignment.

    ⚠️ 2026-08-27: the manual's 2026-08-26 re-verification (article id
    `49514964272665`) claimed this field's real key is `"AELEM"`, not
    `"ELEM_LIST"` — reasoning that the worked Request/Response examples
    (and the response body's own key) all use `"AELEM"`, so the
    Specifications table's `"ELEM_LIST"` must be the typo. **Live-tested
    on Gen NX and found the manual's new claim wrong**: with real elements
    in the model, `{"ELEM_LIST": [1, 2], ...}` succeeded and produced a
    member (echoing back `{"AELEM": [1, 2], "bREVERSE": false}` in the
    *response*, matching the manual's response example), while
    `{"AELEM": [1, 2], ...}` in the *request* failed with `"There is no
    valid element information."` — i.e. the server didn't recognize
    `AELEM` as a request field at all. The manual conflated the response
    key with the request key. `ELEM_LIST` is correct and left unchanged;
    documented here so a future manual sync doesn't silently "fix" this
    into a regression.
    """

    ASSIGN_TYPE: str  # "MANUAL"/"AUTO", required
    SELECTION_TYPE: str  # "ALL"/"SELECTION", required
    ELEM_LIST: List[int]  # target elements; ignored if SELECTION_TYPE="ALL", required if "SELECTION". NOT "AELEM" -- see docstring, live-confirmed 2026-08-27
    ALLOW_SINGLE: bool  # allow single-element members, required


def assign_members(argument: MemberAssignmentArgument, client: Optional[MidasClient] = None) -> dict:
    """docs/manual/15_OPE.md #13 — /ope/MEMB — Member Assignment."""
    return _post("/ope/MEMB", argument, client)


# --- 14. /ope/GUSTFACTOR — Gust Factor Calculator ----------------------------


class TopographicEffect(TypedDict, total=False):
    OPT_USE: bool  # default false, optional (omitted = not used)
    KZT: float  # topographic factor Kzt, required if OPT_USE true


class RigidGustFactorParam(TypedDict, total=False):
    EXP_CATEGORY: str  # exposure category, required
    ROOF_HEIGHT: float  # >=0, required
    BREADTH_X: float  # plan breadth in global X, >=0, required
    BREADTH_Y: float  # plan breadth in global Y, >=0, required


class FlexibleGustFactorParam(TypedDict, total=False):
    EXP_CATEGORY: str  # exposure category, required
    BASIC_WIND_SPEED: float  # >=0, required
    IMPORTANCE_FACTOR: float  # >=0, required
    TOPOGRAPHIC_EFFECT: TopographicEffect  # optional, treated as OPT_USE=false if omitted
    DIRECTION_FACTOR_X: float  # >=0, required
    DIRECTION_FACTOR_Y: float  # >=0, required
    BREADTH_X: float  # plan breadth in global X, >=0, required
    BREADTH_Y: float  # plan breadth in global Y, >=0, required
    STORY_HEIGHT_MAX: float  # max story/roof height, >=0, required
    FREQUENCY_X: float  # fundamental frequency X, >=0, required
    FREQUENCY_Y: float  # fundamental frequency Y, >=0, required
    DAMPING: float  # damping ratio, e.g. 0.03, >=0, required
    TOTAL_MASS: float  # >=0, required
    MX: float  # mass term X, >=0, required
    MY: float  # mass term Y, >=0, required
    VIBRATION: float  # vibration-related factor/flag, >=0, required


class GustFactorArgument(TypedDict, total=False):
    """docs/manual/15_OPE.md #14 — /ope/GUSTFACTOR — Gust Factor Calculator.

    STRUCTURE_TYPE selects which of RIGID_PARAM/FLEXIBLE_PARAM is required
    (mirrors the MaterialParam precedent in properties/material.py). Response
    is returned under a distinct "OPE_GUSTFACTOR_RESPONSE" key (not "GUSTFACTOR").
    """

    WIND_CODE: str  # "KDS(41-12:2022)", required
    STRUCTURE_TYPE: str  # "RIGID"/"FLEXIBLE", required
    RIGID_PARAM: RigidGustFactorParam  # required if STRUCTURE_TYPE="RIGID"
    FLEXIBLE_PARAM: FlexibleGustFactorParam  # required if STRUCTURE_TYPE="FLEXIBLE"


def calculate_gust_factor(argument: GustFactorArgument, client: Optional[MidasClient] = None) -> dict:
    """docs/manual/15_OPE.md #14 — /ope/GUSTFACTOR — Gust Factor Calculator."""
    return _post("/ope/GUSTFACTOR", argument, client)


# --- Shared LCOM-* nested shapes (items 15-18) -------------------------------
# /ope/LCOM-GEN, LCOM-CONC, LCOM-STEEL and LCOM-SRC share almost all of their
# request-body structure (only DGNCODE/CS_ANALYSIS/PRESTRESS_LOSS/the
# WIND_LOAD_COMB & UNDERGROUND_LOAD required-ness differ) — factored here
# instead of repeating per endpoint.


class LoadCombScaleFactorItem(TypedDict, total=False):
    """Shared {LOAD_CASE, FACTOR} pair used by RS_SCALE_FACTOR,
    ADDITIONAL_LOAD.SPECIAL_LOAD.OVER_STRENGTH_FACTOR,
    UNDERGROUND_LOAD.SCALE_FACTOR and UNDERGROUND_LOAD.SPECIAL_LOAD.OVER_STRENGTH_FACTOR."""

    LOAD_CASE: str  # load case name (static: "NAME(ST)", response spectrum: "NAME(RS)"), required
    FACTOR: float  # scale factor, required


class WindLoadCase(TypedDict, total=False):
    ALONG: str  # along-wind load case, optional
    ACROSS: str  # across-wind load case, optional
    TORSION: str  # torsional-wind load case, optional


class WindLoadCombParameter(TypedDict, total=False):
    BUILDING_TYPE: str  # "MIDDLE"/"HIGH", required
    WIND_LOAD_CASE: WindLoadCase  # required
    GUST_FACTOR: float  # GD, >=0, optional
    KAPPA_FACTOR: float  # kappa, >=0, optional


class WindLoadComb(TypedDict, total=False):
    PARAMETERS: List[WindLoadCombParameter]  # required
    TORSION_DIR: str  # "BOTH"/"POSITIVE"/"NEGATIVE", default "BOTH", optional


class OrthoEffect(TypedDict, total=False):
    OPT_USE: bool  # consider orthogonal effect, default false, required
    TYPE: str  # "100_30"/"SRSS", required if OPT_USE true
    LOAD_GROUP: List[str]  # [Load Case1, Load Case2], length 2, required if OPT_USE true


class SpecialSeismicLoad(TypedDict, total=False):
    OPT_USE: bool  # required
    VERTICAL_LOAD_FACTOR: float  # >=0, required if OPT_USE true
    SDS: float  # >=0, required if OPT_USE true
    OVER_STRENGTH_FACTOR: List[LoadCombScaleFactorItem]  # required if OPT_USE true


class VerticalSeismicLoad(TypedDict, total=False):
    OPT_USE: bool  # required
    FORCE_FACTOR: float  # >=0, required if OPT_USE true


class AdditionalLoad(TypedDict, total=False):
    SPECIAL_LOAD: SpecialSeismicLoad  # required
    VERTICAL_LOAD: VerticalSeismicLoad  # required


class UndergroundLoadCaseItem(TypedDict, total=False):
    LOAD_CASE: str  # seismic load case name, required
    DIRECTION: str  # "POSITIVE"/"NEGATIVE", required
    LOAD_CASE_SEISMIC: List[str]  # earth-pressure load cases (seismic component), required
    LOAD_CASE_STATIC: List[str]  # earth-pressure load cases (static component), required


class UndergroundLoad(TypedDict, total=False):
    OPT_USE: bool  # required
    SCALE_FACTOR: List[LoadCombScaleFactorItem]  # required if OPT_USE true
    LOAD_CASE_LIST: List[UndergroundLoadCaseItem]  # required if OPT_USE true
    # SPECIAL_LOAD lives inside UNDERGROUND_LOAD and applies special-seismic-load
    # handling to underground load generation specifically — same {OPT_USE,
    # VERTICAL_LOAD_FACTOR, SDS, OVER_STRENGTH_FACTOR} shape as the top-level
    # ADDITIONAL_LOAD.SPECIAL_LOAD, so SpecialSeismicLoad is reused here.
    SPECIAL_LOAD: SpecialSeismicLoad  # optional


# --- 15. /ope/LCOM-GEN — Load Combination (General) – KDS:2022 / AIK-SRC2K --


class LoadCombinationGeneralKdsArgument(TypedDict, total=False):
    """KDS:2022 variant of /ope/LCOM-GEN. CODE_SELECTION selects the design
    body (CONCRETE/STEEL/SRC); fields are flattened onto one payload with
    comments noting which body each applies to (mirrors the MaterialParam
    precedent in properties/material.py)."""

    OPTION: str  # "ADD"/"REPLACE", required
    CODE_SELECTION: str  # "CONCRETE"/"STEEL"/"SRC" — selects the DGNCODE const/required-field set below, required
    DGNCODE: str  # const per CODE_SELECTION: "KDS 41 20 : 2022"(CONCRETE) / "KDS 41 30 : 2022"(STEEL) / "KDS 41 SRC : 2022"(SRC), required
    ADD_ENVELOPE: bool  # default true, optional (CONCRETE/STEEL bodies only; absent from SRC body)
    RS_SCALE_FACTOR: List[LoadCombScaleFactorItem]  # required (all bodies)
    WIND_LOAD_COMB: WindLoadComb  # required for SRC body; optional for CONCRETE/STEEL
    ORTHO_EFFECT: OrthoEffect  # required (all bodies)
    ADDITIONAL_LOAD: AdditionalLoad  # required (all bodies)
    UNDERGROUND_LOAD: UndergroundLoad  # required for SRC body; optional for CONCRETE/STEEL
    CS_ANALYSIS: bool  # reflect construction-stage analysis results, required (CONCRETE body only)
    PRESTRESS_LOSS: bool  # reflect prestress loss, required (CONCRETE body only)


class LoadCombinationAikSrc2kArgument(TypedDict, total=False):
    """AIK-SRC2K simplified schema shared by /ope/LCOM-GEN and /ope/LCOM-SRC
    when DGNCODE="AIK-SRC2K" (manual's "LCOM-GEN/SRC AIK-SRC2K 변형 스키마"
    section) — a completely different, much smaller shape than the KDS:2022
    variants above/below, selected purely by the DGNCODE value."""

    OPTION: str  # "ADD"/"REPLACE", required
    DGNCODE: str  # "AIK-SRC2K", required
    RS_SCALE_FACTOR: List[LoadCombScaleFactorItem]  # required for LCOM-GEN, optional for LCOM-SRC


def generate_load_combination_general(
    argument: Union[LoadCombinationGeneralKdsArgument, LoadCombinationAikSrc2kArgument],
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/15_OPE.md #15 — /ope/LCOM-GEN — Load Combination (General) – KDS:2022 / AIK-SRC2K.

    DGNCODE selects the schema: KDS:2022 (LoadCombinationGeneralKdsArgument,
    CODE_SELECTION-flattened) vs AIK-SRC2K (LoadCombinationAikSrc2kArgument).
    The Union only helps callers running a type checker — TypedDicts aren't
    validated at runtime (matches this SDK's other payload types), so build
    ONLY the fields documented for the DGNCODE you set; mixing fields from
    both schemas (e.g. AIK-SRC2K's DGNCODE with KDS:2022 fields like
    CODE_SELECTION/ADD_ENVELOPE/CS_ANALYSIS) is sent to the API as-is and
    will surface as a server-side error, not a client-side one.

    ⚠️ Live-tested 2026-07-30 on Gen NX: a KDS:2022/CONCRETE payload built
    from every field this TypedDict documents as required for that body
    (RS_SCALE_FACTOR, ORTHO_EFFECT, ADDITIONAL_LOAD with both nested
    OPT_USE flags false, CS_ANALYSIS, PRESTRESS_LOSS) answered "Wrong
    Field". Not root-caused — the sibling endpoint LCOM-CONC succeeded
    with a minimal payload covering the same design body, so this wasn't
    pursued further; treat as unconfirmed.

    ⚠️ Live-tested 2026-07-31 on Civil NX: even the minimal AIK-SRC2K
    schema (``{OPTION, DGNCODE: "AIK-SRC2K", RS_SCALE_FACTOR: []}``) 404'd
    outright — a different failure mode than Gen's "Wrong Field" (which at
    least reaches routing/validation). Confirmed via ``GET
    /info/ope/LCOM-GEN`` also 404ing on Civil (route genuinely not
    registered, not just an execution failure) — same for
    ``/info/ope/LCOM-CONC``. This closes the question left open for
    LCOM-CONC/STEEL/SRC's Civil-404 finding: **the whole `/ope/LCOM-*`
    family is Gen-only**, confirmed at the routing level, not just
    inferred from execution failures.

    ⚠️ Live-tested 2026-08-01 on Gen NX: the minimal AIK-SRC2K schema
    (``{OPTION, DGNCODE: "AIK-SRC2K", RS_SCALE_FACTOR: []}``) also answers
    "Wrong Field" on Gen — same result as the KDS:2022/CONCRETE payload
    tested above on 2026-07-30, so it's not specific to one schema
    variant. Unlike Civil (which 404s at the routing level, see above),
    this one reaches the server and is rejected there, confirming the
    route itself is live on Gen for both schema shapes; still no root
    cause identified.
    """
    return _post("/ope/LCOM-GEN", argument, client)


# --- 16. /ope/LCOM-CONC — Load Combination (Concrete) – KDS 41 20:2022 ------


class LoadCombinationConcreteArgument(TypedDict, total=False):
    """docs/manual/15_OPE.md #16 — /ope/LCOM-CONC — Load Combination (Concrete) – KDS 41 20:2022."""

    OPTION: str  # "ADD"/"REPLACE", required
    DGNCODE: str  # "KDS 41 20 : 2022", required
    RS_SCALE_FACTOR: List[LoadCombScaleFactorItem]  # optional
    WIND_LOAD_COMB: WindLoadComb  # optional
    ORTHO_EFFECT: OrthoEffect  # optional
    ADDITIONAL_LOAD: AdditionalLoad  # optional
    UNDERGROUND_LOAD: UndergroundLoad  # optional
    CS_ANALYSIS: bool  # reflect construction-stage analysis results, default false, optional
    PRESTRESS_LOSS: bool  # reflect prestress loss, default false, optional


def generate_load_combination_concrete(
    argument: LoadCombinationConcreteArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/15_OPE.md #16 — /ope/LCOM-CONC — Load Combination (Concrete) – KDS 41 20:2022.

    ⚠️ Live-tested 2026-07-30: a minimal payload ({OPTION, DGNCODE} only)
    succeeded on Gen NX but 404'd on Civil NX, on the same synthetic frame
    model shape (single reproduction so far, not yet independently
    reconfirmed) — possibly Gen-only despite the manual not saying so. Not
    enforced here: plain ope.py functions have no PRODUCTS gate in this
    SDK, so a Civil call reaches the server and 404s there rather than
    raising client-side.

    ⚠️ Confirmed 2026-07-31: ``GET /info/ope/LCOM-CONC`` (and
    ``/info/ope/LCOM-GEN``) also 404 on Civil NX — the whole `/ope/LCOM-*`
    family's routes aren't registered on Civil at all, not just failing at
    execution. This upgrades the "possibly Gen-only" guess above to a
    routing-level confirmation.
    """
    return _post("/ope/LCOM-CONC", argument, client)


class _LoadCombinationSteelSrcKdsArgument(TypedDict, total=False):
    """Shared schema for LCOM-STEEL and LCOM-SRC's KDS:2022 variant — field-
    for-field identical (same as LCOM-CONC minus CS_ANALYSIS/PRESTRESS_LOSS);
    only DGNCODE's literal value differs per endpoint, so it's redeclared in
    each subclass's docstring rather than duplicating all 7 fields twice."""

    OPTION: str  # "ADD"/"REPLACE", required
    DGNCODE: str  # required (see subclass docstring for the exact literal)
    RS_SCALE_FACTOR: List[LoadCombScaleFactorItem]  # optional
    WIND_LOAD_COMB: WindLoadComb  # optional
    ORTHO_EFFECT: OrthoEffect  # optional
    ADDITIONAL_LOAD: AdditionalLoad  # optional
    UNDERGROUND_LOAD: UndergroundLoad  # optional


# --- 17. /ope/LCOM-STEEL — Load Combination (Steel) – KDS 41 30:2022 -------


class LoadCombinationSteelArgument(_LoadCombinationSteelSrcKdsArgument):
    """docs/manual/15_OPE.md #17 — /ope/LCOM-STEEL — Load Combination (Steel) – KDS 41 30:2022.

    DGNCODE: "KDS 41 30 : 2022".
    """


def generate_load_combination_steel(
    argument: LoadCombinationSteelArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/15_OPE.md #17 — /ope/LCOM-STEEL — Load Combination (Steel) – KDS 41 30:2022.

    ⚠️ Live-tested 2026-07-30: same Civil-404/Gen-ok split as
    generate_load_combination_concrete — see that function's docstring.
    """
    return _post("/ope/LCOM-STEEL", argument, client)


# --- 18. /ope/LCOM-SRC — Load Combination (SRC) – KDS 41 SRC:2022 / AIK-SRC2K


class LoadCombinationSrcKdsArgument(_LoadCombinationSteelSrcKdsArgument):
    """KDS 41 SRC:2022 variant of /ope/LCOM-SRC. DGNCODE: "KDS 41 SRC : 2022"."""


def generate_load_combination_src(
    argument: Union[LoadCombinationSrcKdsArgument, LoadCombinationAikSrc2kArgument],
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/15_OPE.md #18 — /ope/LCOM-SRC — Load Combination (SRC) – KDS 41 SRC:2022 / AIK-SRC2K.

    ⚠️ Live-tested 2026-07-30: same Civil-404/Gen-ok split as
    generate_load_combination_concrete — see that function's docstring.

    DGNCODE selects the schema: KDS 41 SRC:2022 (LoadCombinationSrcKdsArgument)
    vs AIK-SRC2K (LoadCombinationAikSrc2kArgument, RS_SCALE_FACTOR optional here).
    The Union only helps callers running a type checker — TypedDicts aren't
    validated at runtime (matches this SDK's other payload types), so build
    ONLY the fields documented for the DGNCODE you set; a hybrid dict mixing
    both schemas is sent to the API as-is and will surface as a server-side
    error, not a client-side one.
    """
    return _post("/ope/LCOM-SRC", argument, client)


# --- 19. /ope/GSBG — Bridge Girder Diagram Image Generation -----------------


class AllowableStressLine(TypedDict, total=False):
    OPT_USE: bool  # draw allowable stress line, default false, optional
    COMP: int  # allowable compression stress (follows current system unit setting), required if OPT_USE true
    TENS: int  # allowable tension stress (follows current system unit setting), required if OPT_USE true


#: docs/manual/15_OPE.md #19 — /ope/GSBG — Bridge Girder Diagram Image Generation.
#:
#: The manual's official article was updated 2026-07-14 (superseding the
#: 2026-07-12 "확인 필요"/unconfirmed draft this was originally transcribed
#: from). Two breaking schema changes vs. that draft: `LC_TYPE` was dropped
#: entirely (only `LC_NAME` is sent now), and `BATCH_LIST` changed from an
#: array of `{BRDG_GROUP, SF, GROUP}` objects to a plain array of output
#: group-name strings.
#:
#: DGRM_TYPE selects Stress(0)/Force(1) (governs which COMPONENTS values are
#: valid); BATCH selects whether BATCH_LIST or BRDG_GROUP is used. Fields
#: flattened onto one payload with comments noting which mode each applies to
#: (mirrors the MaterialParam precedent). Uses functional TypedDict syntax
#: because "7TH_DOF_TYPE" is not a valid Python identifier (leading digit).
BridgeGirderDiagramArgument = TypedDict(
    "BridgeGirderDiagramArgument",
    {
        "LC_NAME": str,  # load case/combination name, required
        "DGRM_TYPE": int,  # Stress=0/Force=1, required
        "BATCH": bool,  # default true, optional
        "X_AXIS_TYPE": int,  # Distance=0/Node=1, default 0, optional
        "COMPONENTS": int,  # Stress(DGRM_TYPE=0): Sax=0/+Sby=1/-Sby=2/+Sbz=3/-Sbz=4/Combined=5/7thDOF=6; Force(DGRM_TYPE=1): Fx=0/Fy=1/Fz=2/Mx=3/My=4/Mz=5/Mb=6/Mt=7/Mw=8; default 0, optional; not allowed at top level when BATCH=true
        "7TH_DOF_TYPE": int,  # 0-6, used when DGRM_TYPE=0 and COMPONENTS=6 (7th DOF), default 0, optional; not allowed when BATCH=true
        "COMBINED_COMP": int,  # 0-4, used when DGRM_TYPE=0 and COMPONENTS=5 (Combined), default 0, optional; not allowed when BATCH=true
        "STRESS_LINE": AllowableStressLine,  # optional, not allowed when DGRM_TYPE=1 (Force)
        "BATCH_LIST": List[str],  # output group names, required if BATCH=true/omitted; not allowed if BATCH=false
        "BRDG_GROUP": str,  # bridge girder element group, required if BATCH=false; not allowed if BATCH=true
        "STAGE_LIST": List[str],  # construction stages to generate diagrams for (minItems 1), required
        "EXPORT_PATH": str,  # image save path, required
        "EXTENSION": str,  # "bmp"/"jpg"/"emf", required
    },
    total=False,
)


def generate_bridge_girder_diagram(
    argument: BridgeGirderDiagramArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/15_OPE.md #19 — /ope/GSBG — Bridge Girder Diagram Image Generation.

    See BridgeGirderDiagramArgument's docstring re: the 2026-07-14 schema
    update (LC_TYPE removed, BATCH_LIST is now a plain string array).

    As of the manual's 2026-08-10 sync, this same endpoint is also
    documented a second time at docs/manual/17_DB_Bridge.md #5 (cross-
    referenced from db/bridge.py's GSBG module docstring) — field-for-field
    identical to the schema below, not a separate/updated version. This
    function is unaffected; no code change was needed.

    ⚠️ Live-tested 2026-07-31 on Civil NX, on a real FCM (Free Cantilever
    Method) bridge model, 17 construction stages. Partial progress, not
    fully unblocked:

    - `BRDG_GROUP` genuinely is just a `/db/GRUP` (StructureGroup) name —
      creating one via `StructureGroup.create({id: {"NAME": ..., "E_LIST":
      [...]}})` with the girder's beam element IDs and passing that NAME
      here works: the "group not found"-shaped error goes away once the
      group exists. This contradicts an earlier assumption that Bridge
      Groups can only be created via the GUI wizard — a plain element
      group is sufficient.
    - Before that, every call failed with `"post mode is required"`
      (matching `DREULT`'s `"Post Mode is not available"` on a different
      model) — calling `set_result_graphic()` first did NOT clear this;
      only the user manually switching to the "Post" tab in the Civil NX
      GUI did. No API-only way to enter this mode was found.
    - After that, every call instead fails with `"Final/PostCS stage is
      not supported"` — reproduced with `STAGE_LIST` set to `CS1`, `CS2`,
      `CS3`, `CS16`, and `CS17` (the model's actual final stage) and
      `LC_NAME` set to `"Self"`, `"Self(CS)"`, and `"Summation(CS)"`,
      identically every time. Since varying the documented parameters
      didn't change the error, this looked like leftover state from an
      earlier `set_result_graphic()` call made with `LOAD_CASE_COMB:
      {"TYPE": "CS", "NAME": "Summation"}` (Summation is itself a
      "Final/PostCS" aggregate) — not root-caused before the session
      ended.

    ⚠️ Re-tested 2026-08-13 on Civil NX (v2.2, build 08/12/2026), a
    different real construction-stage bridge model (4 stages, CS1-CS4).
    User manually confirmed Post mode active first: **"post mode is
    required" did not recur** — confirms the manual GUI toggle is a
    reproducible fix for that specific gate, not a one-off. But **"Final/
    PostCS stage is not supported" recurred identically**, across
    `STAGE_LIST=["CS1"]` (the model's *first* stage, not "final" by any
    reading) with three different `LC_NAME` values — on a session that
    never called `set_result_graphic()` at all. **This rules out the
    "leftover state from an earlier set_result_graphic() call" theory**
    above — the error reproduces from a clean session with no prior
    `RESULTGRAPHIC` call. A follow-up attempt to explicitly select stage
    CS1 as the active result via `set_result_graphic(CURRENT_MODE=
    "beamdiagrams", LOAD_CASE_COMB={"TYPE": "CS", "NAME": "CS1"})` failed
    differently — `"Can not find load case"` — so `CS1` alone isn't a
    valid `LOAD_CASE_COMB.NAME`; the correct stage-result naming for this
    call is still unknown. Session stayed healthy throughout, no crash.
    Treat GSBG as still blocked; the Bridge Group and Post Mode pieces
    are solved, "Final/PostCS stage is not supported" looks more
    structural than session-state-dependent now, and remains
    unexplained.
    """
    batch = argument.get("BATCH", True)
    if batch:
        forbidden = {"BRDG_GROUP", "COMPONENTS", "COMBINED_COMP", "7TH_DOF_TYPE"} & argument.keys()
        if forbidden:
            raise MidasRequestError(
                "BATCH=true does not allow " + ", ".join(sorted(forbidden)) + " for /ope/GSBG",
                method="POST",
                endpoint="/ope/GSBG",
            )
    elif "BATCH_LIST" in argument:
        raise MidasRequestError(
            "BATCH=false does not allow BATCH_LIST for /ope/GSBG",
            method="POST",
            endpoint="/ope/GSBG",
        )
    return _post("/ope/GSBG", argument, client)
