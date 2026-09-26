"""``/view/*`` — model view control (selection, capture, viewpoint, active
target, display options, result graphics); these settings control the
on-screen model view and are not persisted to the DB.

Source: docs/manual/16_VIEW.md, items 1-7. Bodies are wrapped in an
``"Argument"`` key like doc.py (not ID-keyed ``"Assign"`` like db/*.py), but
``/view/DISPLAY`` and ``/view/RESULTGRAPHIC`` have very deeply-nested bodies
(dozens of nested objects/booleans), so — unlike doc.py's few-named-kwargs
style — every endpoint here (except the GET-only ``/view/SELECT``) takes one
TypedDict argument that documents the endpoint's full body shape, with large
sub-groups factored into their own nested TypedDict classes (mirrors
db/pushover.py's Hyper-S nested-object style).

Documentation quirks preserved from the manual (not silently "fixed" — see
inline comments at point of use for details):
- ``/view/DISPLAY``: ``MISC.GRID_MODEL_LOAD_LINE`` is missing from the raw
  JSON Schema but present in the Specifications table and worked example, so
  it is included. The raw schema/example key ``VIEWPPORT_GIZMO`` is a
  documented typo; the real key ``VIEWPORT_GIZMO`` is used.
- ``/view/RESULTGRAPHIC``: ``TYPE_OF_DISPLAY.CONTOUR.COLOR_TYPE``'s enum
  differs between the JSON Schema (``vrgb``/``rgb``/``brg``/``grayscaled``)
  and the Specifications table (``vrgb``/``rgb``/``rbg``/``gray scaled``);
  we type it as ``str`` (not a Literal) so both variants remain usable, and
  document the discrepancy on the field.
- ``/view/CAPTURE``: the Parameters table lists ``PERSPECTIVE``/
  ``ZOOM_LEVEL``/``BGCOLOR_TOP``/``BGCOLOR_BOTTOM`` as top-level ``Argument``
  keys, but the worked example nests them inside ``DISPLAY`` instead — both
  are documented on the field below.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from .client import MidasClient
from .client import get_result as _get
from .client import post_argument as _post

# --- 1. /view/SELECT — Select ------------------------------------------------


def get_selection(client: Optional[MidasClient] = None) -> dict:
    """docs/manual/16_VIEW.md #1 — /view/SELECT — Select.

    GET-only, no request body. Returns the currently selected node/element
    ID lists, e.g. ``{"SELECT": {"NODE_LIST": [...], "ELEM_LIST": [...]}}``.
    """
    return _get("/view/SELECT", client)


# --- 2. /view/CAPTURE — Capture ----------------------------------------------


class RgbColor(TypedDict, total=False):
    """Shared {R, G, B} color triple used by CAPTURE's background colors."""

    R: int  # Red, optional
    G: int  # Green, optional
    B: int  # Blue, optional


class CaptureArgument(TypedDict, total=False):
    """docs/manual/16_VIEW.md #2 — /view/CAPTURE Parameters table.

    Two mutually exclusive modes selected by the table's 그룹(Group) column:
    "Smart Report" (EXPORT_PATH + FIGURE_NAME only) vs "User Setting"
    (EXPORT_PATH plus the rest of the fields below). Flattened onto one
    TypedDict, mirroring the MaterialParam / NonlinearAnalysisControlData
    Payload precedent for mode-dependent field groups elsewhere in this SDK.
    """

    EXPORT_PATH: str  # Image save path + filename, required (both modes)
    FIGURE_NAME: str  # Smart Report image name, required (Smart Report mode)
    STAGE_NAME: str  # Construction stage name, optional (User Setting mode)
    SET_MODE: str  # Pre-Mode="pre"/Post-Mode="post", optional (User Setting mode)
    SET_HIDDEN: bool  # Hidden-line option, default false, optional (User Setting mode)
    HEIGHT: int  # Image height in pixels, optional (User Setting mode)
    WIDTH: int  # Image width in pixels, optional (User Setting mode)
    ANGLE: AngleArgument  # Viewpoint, see view/ANGLE, optional (User Setting mode)
    ACTIVE: ActiveArgument  # Active target, see view/ACTIVE, optional (User Setting mode)
    DISPLAY: DisplayArgument  # Display options, see view/DISPLAY, optional (User Setting mode)
    PERSPECTIVE: bool  # Perspective, default false, optional (User Setting mode; worked example nests this inside DISPLAY instead — see module docstring)
    ZOOM_LEVEL: float  # Zoom: ZoomOut 25<=v<100 / ZoomFit 100 / ZoomIn 100<v<200, default 100, optional (User Setting mode; worked example nests this inside DISPLAY instead)
    BGCOLOR_TOP: RgbColor  # Top background color, optional (User Setting mode; worked example nests this inside DISPLAY instead)
    BGCOLOR_BOTTOM: RgbColor  # Bottom background color, optional (User Setting mode; worked example nests this inside DISPLAY instead)
    RESULT_GRAPHIC: ResultGraphicArgument  # Result display, see view/RESULTGRAPHIC, optional (User Setting mode)


def capture(argument: CaptureArgument, client: Optional[MidasClient] = None) -> dict:
    """docs/manual/16_VIEW.md #2 — /view/CAPTURE — Capture."""
    return _post("/view/CAPTURE", argument, client)


# --- 3. /view/PRECAPTURE — Dialog Capture ------------------------------------


class PrecaptureOption(TypedDict, total=False):
    ID: int  # Picture Type ID Number, required


class PrecaptureArgument(TypedDict, total=False):
    """docs/manual/16_VIEW.md #3 — /view/PRECAPTURE Parameters table."""

    EXPORT_PATH: str  # Image save path + filename, required
    VIEW_TYPE: str  # Preview picture type: Fiber Division of Section="FIBR", required
    OPTION: PrecaptureOption  # Capture option, required


def precapture(argument: PrecaptureArgument, client: Optional[MidasClient] = None) -> dict:
    """docs/manual/16_VIEW.md #3 — /view/PRECAPTURE — Dialog Capture."""
    return _post("/view/PRECAPTURE", argument, client)


# --- 4. /view/ANGLE — Viewpoint ----------------------------------------------


class AngleArgument(TypedDict, total=False):
    """docs/manual/16_VIEW.md #4 — /view/ANGLE Parameters table."""

    HORIZONTAL: float  # Horizontal viewpoint angle, default 0, optional
    VERTICAL: float  # Vertical viewpoint angle, default 0, optional


def set_angle(argument: AngleArgument, client: Optional[MidasClient] = None) -> dict:
    """docs/manual/16_VIEW.md #4 — /view/ANGLE — Viewpoint."""
    return _post("/view/ANGLE", argument, client)


# --- 5. /view/ACTIVE — Active -------------------------------------------------


class ActiveArgument(TypedDict, total=False):
    """docs/manual/16_VIEW.md #5 — /view/ACTIVE Parameters table.

    ACTIVE_MODE selects the field group: "All" (no other fields required),
    "Active" (N_LIST/E_LIST), or "Identity" (IDENTITY_TYPE/IDENTITY_LIST).
    Flattened onto one TypedDict, mirroring the MaterialParam-style
    precedent for mode-dependent fields elsewhere in this SDK.

    ⚠️ 2026-08-27: added `IDENTITY_TYPE="STORY"` (per-story activation) and
    its companion `STORY_ACTIVE` field. The manual's 2026-08-26
    re-verification (article id `35523395368985`) notes this mode was
    added to the vendor's own Specifications table/Request Example without
    the matching JSON Schema update — reconciled from the table/example
    there. Live-confirmed on Gen NX 2026-08-27: both `{"ACTIVE_MODE":
    "Identity", "IDENTITY_TYPE": "STORY", "IDENTITY_LIST": ["1F"],
    "STORY_ACTIVE": "FLOOR"}` and a plain `{"ACTIVE_MODE": "All"}` both
    answered `"... command complete"`.
    """

    ACTIVE_MODE: str  # "All"/"Active"/"Identity", required
    N_LIST: List[int]  # Node number list, required if ACTIVE_MODE="Active"
    E_LIST: List[int]  # Element number list, required if ACTIVE_MODE="Active"
    IDENTITY_TYPE: str  # "Group"/"NamedPlane"/"LoadGroup"/"BoundaryGroup"/"STORY", required if ACTIVE_MODE="Identity"
    IDENTITY_LIST: List[str]  # Identity name list (story names if IDENTITY_TYPE="STORY"), required if ACTIVE_MODE="Identity"
    STORY_ACTIVE: str  # "FLOOR"/"ABOVE"/"BELOW"/"BOTH", required if IDENTITY_TYPE="STORY"


def set_active(argument: ActiveArgument, client: Optional[MidasClient] = None) -> dict:
    """docs/manual/16_VIEW.md #5 — /view/ACTIVE — Active."""
    return _post("/view/ACTIVE", argument, client)


# --- 6. /view/DISPLAY — Display ----------------------------------------------


class NodeDisplay(TypedDict, total=False):
    """Argument.NODE — node display group."""

    NODE: bool  # Node display, default false, optional
    NODE_NUMBER: bool  # Node number, default false, optional
    NODE_LOCAL_AXIS: bool  # Node local axis, default false, optional
    STORY_NAME: bool  # Story name (MIDAS GEN NX only), default false, optional


class ElementDisplay(TypedDict, total=False):
    """Argument.ELEMENT — element display group."""

    ELEM_NUMBER: bool  # Element number, default false, optional
    ELEM_NUMBER_WITH_BORDER: bool  # Element number with border, default false, optional
    ELEM_TYPE_NUMBER: bool  # Element type number, default false, optional
    ELEM_TYPE_NAME: bool  # Element type name, default false, optional
    WALL_ID: bool  # Wall ID (MIDAS GEN NX only), default false, optional
    GAP: bool  # Gap element, default false, optional
    HOOK: bool  # Hook element, default false, optional
    CABLE: bool  # Cable, default false, optional
    LOCAL_AXIS: bool  # Local axis, default false, optional
    LOCAL_AXIS_LABEL: bool  # Local axis label (when LOCAL_AXIS is true), default false, optional
    LOCAL_DIRECTION: bool  # Local direction, default false, optional
    SUB_DOMAIN_REBAR_DIRECTION: bool  # Sub-domain rebar direction, default false, optional


class PropertyDisplay(TypedDict, total=False):
    """Argument.PROPERTY — property display group."""

    MATERIAL_NUMBER: bool  # Material number (mutually exclusive w/ MATERIAL_NAME), default false, optional
    MATERIAL_NAME: bool  # Material name (mutually exclusive w/ MATERIAL_NUMBER), default false, optional
    PROPERTY_NUMBER: bool  # Property number (mutually exclusive w/ PROPERTY_NAME), default false, optional
    PROPERTY_NAME: bool  # Property name (mutually exclusive w/ PROPERTY_NUMBER), default false, optional
    SECTION_SHAPE: bool  # Section shape, default false, optional
    TAPERED_SECTION_GROUP: bool  # Tapered section group, default false, optional
    TIME_DEPENDENT_MATERIAL_LINK: bool  # Time-dependent material link, default false, optional
    INELASTIC_HINGE_NAME: bool  # Inelastic hinge name (mutually exclusive w/ INELASTIC_HINGE_SYMBOL), default false, optional
    INELASTIC_HINGE_SYMBOL: bool  # Inelastic hinge symbol (mutually exclusive w/ INELASTIC_HINGE_NAME), default false, optional
    REINFORCEMENT_OF_SECTIONS: bool  # Reinforcement of sections, default false, optional
    VIRTUAL_SECTION_LOCAL_AXIS: bool  # Virtual section local axis, default false, optional


class BoundaryDisplay(TypedDict, total=False):
    """Argument.BOUNDARY — boundary condition display group.

    Several fields form mutually-exclusive footnote groups in the manual
    (e.g. point-spring-support variants, general-link variants, beam/plate
    end-release symbol vs digit) — see docs/manual/16_VIEW.md #6 footnotes.
    """

    SUPPORT: bool  # Support, default false, optional
    SUPPORT_BY_DIRECTION: bool  # Support by direction, default false, optional
    POINT_SPRING_SUPPORT: bool  # Point spring support, default false, optional
    POINT_SPRING_SUPPORT_COMP_TENS: bool  # Point spring support (comp/tension), default false, optional
    POINT_SPRING_SUPPORT_MULTI_LINEAR: bool  # Point spring support (multi-linear), default false, optional
    POINT_SPRING_SUPPORT_BY_DIRECTION: bool  # Point spring support by direction, default false, optional
    POINT_SPRING_SUPPORT_BY_DIRECTION_COMP_TENS: bool  # Point spring support by direction (comp/tension), default false, optional
    POINT_SPRING_SUPPORT_BY_DIRECTION_MULTI_LINEAR: bool  # Point spring support by direction (multi-linear), default false, optional
    SURFACE_SPRING_SUPPORT_TYPE: bool  # Surface spring support type, default false, optional
    SURFACE_SPRING_SUPPORT_LINEAR: bool  # Surface spring support (linear), default false, optional
    SURFACE_SPRING_SUPPORT_COMP_TENS: bool  # Surface spring support (comp/tension), default false, optional
    GENERAL_SPRING_SUPPORT: bool  # General spring support, default false, optional
    ELASTIC_LINK: bool  # Elastic link, default false, optional
    ELASTIC_LINK_LOCAL_AXIS: bool  # Elastic link local axis (when ELASTIC_LINK is true), default false, optional
    ELASTIC_LINK_TYPE: bool  # Elastic link type (when ELASTIC_LINK is true), default false, optional
    ELASTIC_LINK_NUMBER: bool  # Elastic link number (when ELASTIC_LINK is true), default false, optional
    GENERAL_LINK: bool  # General link, default false, optional
    GENERAL_LINK_NUMBER: bool  # General link number, default false, optional
    GENERAL_LINK_LOCAL_AXIS: bool  # General link local axis, default false, optional
    GENERAL_LINK_TYPE: bool  # General link type, default false, optional
    CHANGE_GENERAL_LINK_PROPERTIES: bool  # Change general link properties, default false, optional
    BEAM_END_RELEASE_SYMBOL: bool  # Beam end release symbol, default false, optional
    BEAM_END_RELEASE_DIGIT: bool  # Beam end release digit, default false, optional
    BEAM_END_OFFSET_SYMBOL: bool  # Beam end offset symbol, default false, optional
    BEAM_END_OFFSET_DIGIT: bool  # Beam end offset digit, default false, optional
    PLATE_END_RELEASE_SYMBOL: bool  # Plate end release symbol, default false, optional
    PLATE_END_RELEASE_DIGIT: bool  # Plate end release digit, default false, optional
    RIGID_LINK: bool  # Rigid link, default false, optional
    LINEAR_CONSTRAINTS: bool  # Linear constraints, default false, optional
    REACTION_POSITION: bool  # Reaction position, default false, optional
    STORY_DIAPHRAGM: bool  # Story diaphragm (MIDAS GEN NX only), default false, optional
    DIAPHRAGM_DISCONNECT: bool  # Diaphragm disconnect (MIDAS GEN NX only), default false, optional


class LoadCaseSelection(TypedDict, total=False):
    """LOAD.CASE_SELECTION — load-case filter for load display."""

    TYPE: str  # Load case type, e.g. static="st", required
    NAME: str  # Load case name, required


class LoadValueFormat(TypedDict, total=False):
    """LOAD.LOAD_VALUE — load value display format."""

    FORMAT: str  # "Default"/"Fixed"/"Scientific", required
    PLACE: int  # Decimal places, required


class LoadDisplay(TypedDict, total=False):
    """Argument.LOAD — load display group."""

    CASE_SELECTION: LoadCaseSelection  # Select loads by load case, default All, optional
    GROUP_SELECTION: List[str]  # Select loads by load group, default All, optional
    LOAD_VALUE: LoadValueFormat  # Load value display format, optional
    NODAL_BODY_FORCE: bool  # Nodal body force, default false, optional
    NODAL_LOAD: bool  # Nodal load, default false, optional
    SPECIFIED_DISPLACEMENT: bool  # Specified displacement, default false, optional
    BEAM_LOAD: bool  # Beam load, default false, optional
    PRESTRESS_LOAD: bool  # Prestress load, default false, optional
    PRETENSION_LOAD: bool  # Pretension load, default false, optional
    FLOOR_LOAD: bool  # Floor load, default false, optional
    FLOOR_LOAD_NAME: bool  # Floor load name, default false, optional
    FLOOR_LOAD_AREA: bool  # Floor load area, default false, optional
    LOADING_AREA_PLANE: bool  # Loading area plane (MIDAS GEN NX only), default false, optional
    FINISHING_MATERIAL_LOAD: bool  # Finishing material load (MIDAS GEN NX only), default false, optional
    PRESSURE_LOAD: bool  # Pressure load, default false, optional
    AREA_PRESSURE_LOADS: bool  # Area pressure loads, default false, optional
    PLANE_LOAD: bool  # Plane load, default false, optional
    PLANE_LOAD_NAME: bool  # Plane load name, default false, optional
    NODAL_TEMPERATURE: bool  # Nodal temperature, default false, optional
    ELEMENT_TEMPERATURE: bool  # Element temperature, default false, optional
    TEMPERATURE_GRADIENT: bool  # Temperature gradient, default false, optional
    BEAM_SECTION_TEMPERATURE: bool  # Beam section temperature, default false, optional
    TENDON_PRESTRESS: bool  # Tendon prestress, default false, optional
    WIND_LOAD: bool  # Wind load (MIDAS GEN NX only), default false, optional
    AREA_WIND_PRESSURE: bool  # Area wind pressure (MIDAS GEN NX only), default false, optional
    AREA_WIND_PRESSURE_NAME: bool  # Area wind pressure name (MIDAS GEN NX only), default false, optional
    BEAM_WIND_PRESSURE: bool  # Beam wind pressure (MIDAS GEN NX only), default false, optional
    NODAL_WIND_PRESSURE: bool  # Nodal wind pressure (MIDAS GEN NX only), default false, optional
    FUNCTION_WIND_PRESSURE: bool  # Function wind pressure (MIDAS GEN NX only), default false, optional
    FUNCTION_WIND_PRESSURE_NAME: bool  # Function wind pressure name (MIDAS GEN NX only), default false, optional
    SEISMIC_EARTH_PRESSURE: bool  # Seismic earth pressure (MIDAS GEN NX only), default false, optional
    STATIC_EARTH_PRESSURE: bool  # Static earth pressure (MIDAS GEN NX only), default false, optional
    SEISMIC_LOAD: bool  # Seismic load (MIDAS GEN NX only), default false, optional
    DYNAMIC_NODAL_LOAD: bool  # Dynamic nodal load, default false, optional
    MULTIPLE_SUPPORT_EXCITATION: bool  # Multiple support excitation, default false, optional
    MULTIPLE_SUPPORT_EXCITATION_FUNCTION_NAME: bool  # Multiple support excitation function name, default false, optional
    DIR_X: bool  # X direction (when excitation function name is true), default false, optional
    DIR_Y: bool  # Y direction (when excitation function name is true), default false, optional
    DIR_Z: bool  # Z direction (when excitation function name is true), default false, optional


class MiscDisplay(TypedDict, total=False):
    """Argument.MISC — miscellaneous display group.

    GRID_MODEL_LOAD_LINE is missing from the manual's raw JSON Schema but is
    present in its Specifications table and worked example (MIDAS CIVIL NX
    JP-version only) — included here per the manual's own callout.
    """

    NODAL_MASS: bool  # Nodal mass, default false, optional
    LOAD_TO_MASS: bool  # Load to mass, default false, optional
    TENDON_PROFILE_NAMES: bool  # Tendon profile names, default false, optional
    TENDON_PROFILE_POINT: bool  # Tendon profile point, default false, optional
    INITIAL_FORCES_FOR_GEOMETRIC_STIFFNESS: bool  # Initial forces for geometric stiffness, default false, optional
    SETTLEMENT_GROUP: bool  # Settlement group, default false, optional
    SETTLEMENT_GROUP_VALUE: bool  # Settlement group value (when SETTLEMENT_GROUP is true), default false, optional
    HEAT_OF_HYDRATION_VALUE: bool  # Heat of hydration value, default false, optional
    HEAT_OF_HYDRATION_FUNC_NAME: bool  # Heat of hydration function name, default false, optional
    HEAT_OF_HYDRATION_ELEMENT_CONVECTION_BOUNDARY: bool  # Heat of hydration element convection boundary, default false, optional
    HEAT_OF_HYDRATION_PRESCRIBED_TEMPERATURE: bool  # Heat of hydration prescribed temperature, default false, optional
    HEAT_OF_HYDRATION_HEAT_SOURCE: bool  # Heat of hydration heat source, default false, optional
    HEAT_OF_HYDRATION_PIPE_COOLING_ELEMENT: bool  # Heat of hydration pipe cooling element, default false, optional
    GRID_MODEL_LOAD_LINE: bool  # Grid model load line (MIDAS CIVIL NX JP version only), default false, optional — see class docstring


class ViewDisplay(TypedDict, total=False):
    """Argument.VIEW — view display group.

    VIEWPORT_GIZMO: the manual's raw schema/example spell this
    "VIEWPPORT_GIZMO" (typo); the manual's own callout says the real key is
    "VIEWPORT_GIZMO", which is what's used here.
    """

    UCS_AXIS: bool  # UCS axis, default false, optional
    VIEWPORT_GIZMO: bool  # Viewport gizmo (dynamic view control), default false, optional — see class docstring
    VIEW_POINT: bool  # View point, default false, optional
    DESCRIPTION: str  # Description, default "", optional
    LABEL_ORIENTATION: int  # Label orientation (degrees), default 0, optional


class DisplayArgument(TypedDict, total=False):
    """docs/manual/16_VIEW.md #6 — /view/DISPLAY Parameters table (groups 1-7).

    Only pass the groups you want to change; every group and every field
    within a group is optional.
    """

    NODE: NodeDisplay  # Node display options, optional
    ELEMENT: ElementDisplay  # Element display options, optional
    PROPERTY: PropertyDisplay  # Property display options, optional
    GROUP_SELECTION: List[str]  # Boundary group selection, default All, optional
    BOUNDARY: BoundaryDisplay  # Boundary condition display options, optional
    LOAD: LoadDisplay  # Load display options, optional
    MISC: MiscDisplay  # Miscellaneous display options, optional
    VIEW: ViewDisplay  # View display options, optional


def set_display(argument: DisplayArgument, client: Optional[MidasClient] = None) -> dict:
    """docs/manual/16_VIEW.md #6 — /view/DISPLAY — Display."""
    return _post("/view/DISPLAY", argument, client)


# --- 7. /view/RESULTGRAPHIC — Result Graphic ---------------------------------


class ContourOptions(TypedDict, total=False):
    """TYPE_OF_DISPLAY.CONTOUR.OPTIONS — contour representation options."""

    CONTOUR_FILL: bool  # Fill type: Contour Fill=true / lines only=false, default true, optional
    GRADIENT_FILL: bool  # Gradient fill (when CONTOUR_FILL is true), default false, optional


class ContourDisplay(TypedDict, total=False):
    """TYPE_OF_DISPLAY.CONTOUR — contour details.

    COLOR_TYPE: the manual's raw JSON Schema enum is
    ["vrgb","rgb","brg","grayscaled"], while its Specifications table lists
    "vrgb"/"rgb"/"rbg"/"gray scaled" instead — a documented discrepancy. We
    type this as ``str`` (not a Literal) so callers can use either variant;
    we favor the JSON Schema's compact/code-like spellings ("grayscaled",
    "brg") as the more concrete source, since the Specifications table's
    prose-style "gray scaled" (with a space) and "rbg" read like transcription
    slips of the schema values.
    """

    OPT_CHECK: bool  # Show/hide this display type, default false, optional
    NUM_OF_COLOR: int  # Number of contour colors: 6/12/18/24, default 12, optional
    COLOR_TYPE: str  # "vrgb"/"rgb"/"brg"/"grayscaled" (see class docstring), default "vrgb", optional
    OPTIONS: ContourOptions  # Contour representation options, optional


class MinMaxOnly(TypedDict, total=False):
    """TYPE_OF_DISPLAY.VALUES.MINMAX_ONLY — "Min/Max Only" value filter."""

    MAXMIN: str  # "Min & Max"/"Abs Max"/"Max"/"Min", default "Min & Max", optional
    LIMIT_SCALE: int  # Limit scale (0-100), default 0, optional


class ValuesDisplay(TypedDict, total=False):
    """TYPE_OF_DISPLAY.VALUES — values output details."""

    OPT_CHECK: bool  # Show/hide this display type, default false, optional
    VALUE_EXP: bool  # Exponential=true / fixed=false notation, default false, optional
    DECIMAL_PT: int  # Decimal places, default 0, optional
    SET_ORIENT: int  # Value orientation, 0-180 in 15-degree steps, default 0, optional
    MINMAX_ONLY: MinMaxOnly  # Enable "Min/Max Only", optional


class LegendDisplay(TypedDict, total=False):
    """TYPE_OF_DISPLAY.LEGEND — legend details."""

    OPT_CHECK: bool  # Show/hide this display type, default false, optional
    POSITION: str  # "right"/"left", default "left", optional
    VALUE_EXP: bool  # Exponential=true / fixed=false notation, default true, optional
    DECIMAL_PT: int  # Decimal places (when VALUE_EXP is false), default 0, optional


class DeformDisplay(TypedDict, total=False):
    """TYPE_OF_DISPLAY.DEFORM — deformation details."""

    OPT_CHECK: bool  # Show/hide this display type, default false, optional
    SCALE_FACTOR: float  # Deformation scale factor, default 0, optional
    REAL_DEFORM: bool  # Deformation type: Real Deform.=true / Nodal Deform=false, default false, optional
    REL_DISP: bool  # Relative deformation, default false, optional
    REAL_DISP: bool  # Real structural deformation: no auto-scale=true / auto-scale=false, default false, optional


class DispOptDisplay(TypedDict, total=False):
    """TYPE_OF_DISPLAY.DISP_OPT — display option details."""

    OPT_CHECK: bool  # Show/hide this display type, default false, optional
    ELEMENT_CENTER: bool  # Place contour at element center, default false, optional
    VALUE_MAX: bool  # Show maximum value=true / element-center value=false, default false, optional


class MirrorBy(TypedDict, total=False):
    """Shared {DIRECTION, OFFSET} mirror-plane pair used by MIRROR_BY_1/2."""

    DIRECTION: str  # "XY"/"YZ"/"XZ", required
    OFFSET: float  # Mirror offset distance, required


class MirroredDisplay(TypedDict, total=False):
    """TYPE_OF_DISPLAY.MIRRORED — symmetric model mirror details."""

    OPT_CHECK: bool  # Show/hide this display type, default false, optional
    MIRROR_BY_1: MirrorBy  # Mirror by half model, required
    MIRROR_BY_2: MirrorBy  # Mirror by quarter model, optional


class CuttingDiagramDisplay(TypedDict, total=False):
    """TYPE_OF_DISPLAY.CUTTING_DIAGRAM — cutting diagram details."""

    OPT_CHECK: bool  # Show/hide this display type, default false, optional
    CUTTING_MODE: str  # "line"/"plane", default "line", optional
    CUTTING_NAME: List[str]  # Cutting line/plane names (db/CUTL, "XY"/"XZ"/"YZ", or db/NPLN key), required
    NORMAL_TO_PLANE: bool  # Plate element graph direction: normal=true / in-plane=false, default true, optional
    SCALE_FACTOR: float  # Diagram output ratio scale factor, default 0, optional
    REVERSE: bool  # Reverse the diagram direction, default false, optional
    VALUE_OUTPUT: bool  # Output as values, default false, optional
    MINMAX_ONLY: bool  # Show only max/min values (when VALUE_OUTPUT is true), default false, optional


class CuttingPlaneDisplay(TypedDict, total=False):
    """TYPE_OF_DISPLAY.CUTTING_PLANE — cutting plane detail dialog."""

    OPT_CHECK: bool  # Show/hide this display type, default false, optional
    PLANE_NAME: List[str]  # Cutting plane names ("XY"/"XZ"/"YZ" or db/NPLN key), required
    FREE_EDGE: bool  # Draw outline: Free Edge=true / Free Face=false, default true, optional


class AppliedLoadsDisplay(TypedDict, total=False):
    """TYPE_OF_DISPLAY.APPLIED_LOADS — applied loads (moving load tracer) details."""

    OPT_CHECK: bool  # Show/hide this display type, default false, optional
    SCALE_FACTOR: float  # Load scale factor, default 0, optional
    OPT_LOAD_VALUES: bool  # Show load values, default false, optional
    VALUE_TYPE: str  # "Exponential"/"Fixed" (when OPT_LOAD_VALUES is true), default "Exponential", optional
    VALUE_DECIMAL_PT: int  # Value output decimal places (when OPT_LOAD_VALUES is true, >=0), default 0, optional


class IsoSurfaceValueMode(TypedDict, total=False):
    """TYPE_OF_DISPLAY.ISO_SURFACE.VALUE_MODE — stress value selection."""

    VALUE_TYPE: str  # "relative"/"values", default "relative", optional
    VALUE: List[float]  # IsoSurface values (relative type: max 1 / min 0), required


class IsoSurfaceDisplay(TypedDict, total=False):
    """TYPE_OF_DISPLAY.ISO_SURFACE — isosurface detail dialog."""

    OPT_CHECK: bool  # Show/hide this display type, default false, optional
    DRAW_POLYLINE: bool  # Draw polygon outline, default false, optional
    TRANSPARENCY: float  # Transparency, screen only (0-255), default 255, optional
    FREE_EDGE: bool  # Solid element outline: Free Face=true / Free Edge=false, default true, optional
    VALUE_MODE: IsoSurfaceValueMode  # Stress value selection, optional


class TypeOfDisplayArgument(TypedDict, total=False):
    """Argument.TYPE_OF_DISPLAY — the result-graphic display-type group.

    Available sub-keys differ per CURRENT_MODE (see the manual for each
    result item's own page). UNDEFORMED/YIELD_POINT/MODE_SHAPE are
    documented in the Parameters table only as "Object" with no sub-field
    breakdown anywhere in this manual chapter, so they are typed as
    free-form dicts here rather than invented nested TypedDicts.
    """

    CONTOUR: ContourDisplay  # Contour details, optional
    VALUES: ValuesDisplay  # Values output details, optional
    LEGEND: LegendDisplay  # Legend details, optional
    DEFORM: DeformDisplay  # Deformation details, optional
    DISP_OPT: DispOptDisplay  # Display option details, optional
    MIRRORED: MirroredDisplay  # Symmetric model mirror details, optional
    CUTTING_DIAGRAM: CuttingDiagramDisplay  # Cutting diagram, optional
    CUTTING_PLANE: CuttingPlaneDisplay  # Cutting plane detail dialog, optional
    APPLIED_LOADS: AppliedLoadsDisplay  # Applied loads (moving load tracer), optional
    ISO_SURFACE: IsoSurfaceDisplay  # IsoSurface detail dialog, optional
    UNDEFORMED: Dict[str, Any]  # Display undeformed shape; sub-fields undocumented in manual, optional
    ARROW_SCALE_FACTOR: float  # Arrow scale factor, default 1, optional
    OPT_CUR_STEP_DISPLACEMENT: bool  # Current step displacement, default false, optional
    OPT_STAGE_STEP_REAL_DISPLACEMENT: bool  # Stage/step real displacement, default false, optional
    OPT_INCLUDING_CAMBER_DISPLACEMENT: bool  # Include camber displacement, default false, optional
    OPT_CUR_STEP_FORCE: bool  # Current step force, default false, optional
    YIELD_POINT: Dict[str, Any]  # Yield point; sub-fields undocumented in manual, optional
    OPT_INCLUDE_IMPACT_FACTOR: bool  # Include impact factor, default false, optional
    MODE_SHAPE: Dict[str, Any]  # Mode shape; sub-fields undocumented in manual, optional
    SCALE_FACTOR: float  # Scale factor, default 1, optional
    OPT_CUBIC_INTERPOLATION: bool  # Cubic interpolation, default false, optional
    CUBIC_INTERPOLATION_FACTOR: float  # Cubic interpolation factor, default 0.5, optional


class LoadCaseCombSelection(TypedDict, total=False):
    """Argument.LOAD_CASE_COMB — load case/combination selection, used
    across most result modes (exact sub-fields available can depend on
    CURRENT_MODE; STEP_INDEX appears only in stage-dependent worked
    examples)."""

    TYPE: str  # Load case/combination type, e.g. static="ST"/combination="CB", required
    NAME: str  # Load case/combination name, required
    STEP_INDEX: int  # Construction-stage step index, optional (stage-dependent result modes)


class OutputSectLocation(TypedDict, total=False):
    """Argument.OUTPUT_SECT_LOCATION — beam output section location
    (beam-diagram-family result modes)."""

    OPT_I: bool  # I-end, optional
    OPT_CENTER_MID: bool  # Center/mid, optional
    OPT_J: bool  # J-end, optional


class DisplayOptionsSelection(TypedDict, total=False):
    """Argument.DISPLAY_OPTIONS — beam-diagram-family fidelity/fill/scale
    (not detailed in the manual's Parameters tables; derived from the
    worked examples)."""

    FIDELITY: str  # e.g. "Exact", optional
    FILL: str  # e.g. "line"/"line fill", optional
    SCALE: float  # Diagram scale, optional


class LocalUcsOption(TypedDict, total=False):
    """Argument.OPTIONS.LOCAL_UCS — local UCS selection for plane/solid
    stress result modes."""

    TYPE: str  # e.g. "UCS", optional
    UCS_NAME: str  # UCS name, e.g. "CurrentUCS", optional


class AverageNodalOption(TypedDict, total=False):
    """Argument.OPTIONS.AVERAGE_NODAL — nodal averaging selection for
    plane/solid stress result modes."""

    TYPE: str  # e.g. "Avg.Nodal", optional


class ResultOptionsSelection(TypedDict, total=False):
    """Argument.OPTIONS — plane/plate & solid stress result option group
    (not detailed in the manual's Parameters tables; derived from the
    worked examples)."""

    LOCAL_UCS: LocalUcsOption  # optional
    AVERAGE_NODAL: AverageNodalOption  # optional
    SURFACE: str  # e.g. "Top"/"Bottom" (plane/plate stress modes), optional


class ResultGraphicArgument(TypedDict, total=False):
    """docs/manual/16_VIEW.md #7 — /view/RESULTGRAPHIC Argument body.

    Only TYPE_OF_DISPLAY is formally broken down by the manual's Parameters
    tables; CURRENT_MODE/LOAD_CASE_COMB/COMPONENTS/DISPLAY_OPTIONS/OPTIONS/
    OUTPUT_SECT_LOCATION are documented only via the manual's worked
    examples — the manual explicitly notes the available top-level keys
    differ per result mode (CURRENT_MODE) and refers readers to each result
    item's own manual page, which this chapter does not include. The nested
    TypedDicts here are derived from the worked examples and may not cover
    every result mode.
    """

    CURRENT_MODE: str  # Result mode, e.g. "beamdiagrams"/"reactionforces/moments"/"Plane-Stress/PlateStresses"/"solidstresses", required
    LOAD_CASE_COMB: LoadCaseCombSelection  # Load case/combination selection, optional
    COMPONENTS: Dict[str, Any]  # Result component selection; fields vary per CURRENT_MODE (e.g. PART/COMP/OPT_LOCAL_CHECK), optional
    DISPLAY_OPTIONS: DisplayOptionsSelection  # Beam-diagram-family display options, optional
    OPTIONS: ResultOptionsSelection  # Plane/solid stress result options, optional
    OUTPUT_SECT_LOCATION: OutputSectLocation  # Beam output section location, optional
    TYPE_OF_DISPLAY: TypeOfDisplayArgument  # Result graphic display-type group, optional


def set_result_graphic(argument: ResultGraphicArgument, client: Optional[MidasClient] = None) -> dict:
    """docs/manual/16_VIEW.md #7 — /view/RESULTGRAPHIC — Result Graphic.

    ⚠️ Confirmed 2026-08-11: unlike the story family, this route IS
    registered on Civil NX (v2.2, build 08/11/2026) — `CURRENT_MODE:
    "reactionforces/moments"` against a blank document (no analysis run)
    got a clean `MidasResultError`, `"MIDAS CIVIL NX Empty Load Case
    Type"`, and the session stayed alive. Same shape as Gen's own
    07/30 result (no analysis run yet), just a Civil-flavored message.
    """
    return _post("/view/RESULTGRAPHIC", argument, client)
