"""Source: docs/manual/26_Design_RC_KDS41202022.md, items 54-69 (of 69 total;
see design/rc_kds/setup.py, rebar.py, design_forces.py for the rest).

RC design code KDS 41 20:2022 — code-check/result-table/report endpoints
for beam/column/brace/wall members, comprehensive design result, and
column/brace/beam design-forces tables (items 67-69 share one real
endpoint, /DESIGN/RC/KDS-41-20-2022/TABLE, selected by a body-level type
discriminant). Endpoint prefix: ``/DESIGN/RC/KDS-41-20-2022/<CODE>``.

All 16 endpoints are POST-only, "Argument"-wrapped (not ID-keyed "Assign"),
implemented as plain functions via ``post_argument`` — mirrors
``post/design.py`` and ``design/steel_kds.py``'s Group 4.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from ...client import MidasClient
from ...client import post_argument as _post
from ...post.base import NodeElemsSelector, TableStyles, TableUnit
from .design_forces import RcReportDetailPositions, RcWallDesignSelection

_BASE = "/DESIGN/RC/KDS-41-20-2022"


# === Beam/Column/Brace check triplets (items 54-62) — shared Argument shapes ===


class PerformRcMemberCheckArgument(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #54/#57/#60 — BC-ANAL/CC-ANAL/
    BRC-ANAL Argument (identical shape across beam/column/brace member
    types). Exactly one of ELEMS/SECTIONS is used when PERFORM_TYPE is
    "ELEMS"/"SECTIONS"; PERFORM_TYPE="ALL" needs neither. ELEMS reuses
    post/base.py's NodeElemsSelector (identical KEYS/TO/STRUCTURE_GROUP_NAME
    shape — use exactly one of its three keys).
    """

    PERFORM_TYPE: str  # Target type: "ALL"=all elements/"ELEMS"=by element no./"SECTIONS"=by section no., default "ALL", optional
    ELEMS: NodeElemsSelector  # Element No. Input, required if PERFORM_TYPE="ELEMS" (oneOf with SECTIONS)
    SECTIONS: List[int]  # Section No. Input, required if PERFORM_TYPE="SECTIONS" (oneOf with ELEMS)


class RcMemberCheckTableArgument(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #55/#58/#61 — BC-TABLE/
    CC-TABLE/BRC-TABLE Argument (identical shape across beam/column/brace;
    only TABLE_NAME's documented default text and COMPONENTS' valid values
    differ per member type — see each wrapper's docstring for its
    Response HEAD columns). Exactly one of ELEMS/SECTIONS is required
    (oneOf). ELEMS/UNIT/STYLES reuse post/base.py's
    NodeElemsSelector/TableUnit/TableStyles (identical shapes).
    """

    TABLE_TYPE: str  # Result Table Type: "MEMB"=member-based/"PROP"=section-based, required
    ELEMS: NodeElemsSelector  # Element No. Input, required if not using SECTIONS
    SECTIONS: List[int]  # Section No. Input, required if not using ELEMS
    PRI_SORT: int  # Sort: SECT=0/MEMB=1, default 1, optional
    RESULT: int  # Filter by check status: All=0/OK=1/NG=2, default 0, optional
    TABLE_NAME: str  # Response Table Title, optional
    EXPORT_PATH: str  # Result Table Save Path, optional
    UNIT: TableUnit  # Response Unit Setting (FORCE/DIST/HEAT/TEMP), optional
    STYLES: TableStyles  # Response Number Format (FORMAT/PLACE), optional
    COMPONENTS: List[str]  # Result table components (member-type-specific; see manual HEAD table), optional


class RcMemberCheckReportArgument(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #56/#59/#62 — BC-REPORT/
    CC-REPORT/BRC-REPORT Argument (identical shape across beam/column/
    brace). Exactly one of ELEMS/SECTIONS is required (oneOf). ELEMS reuses
    post/base.py's NodeElemsSelector.
    """

    REPORT_TYPE: str  # Report Table Type: "MEMB"/"PROP", required
    CURRENT_MODE_MEMB: str  # MEMB output mode: "Graphic"=JPG/"Detail"=DOC/"Summary"=TXT, conditionally required if REPORT_TYPE="MEMB"
    CURRENT_MODE_PROP: str  # PROP output mode: "Graphic"/"Summary" (no Detail), conditionally required if REPORT_TYPE="PROP"
    ELEMS: NodeElemsSelector  # Element No. Input, required if not using SECTIONS
    SECTIONS: List[int]  # Section No. Input, required if not using ELEMS
    DETAIL_POSITIONS: RcReportDetailPositions  # Detail output positions, valid only when CURRENT_MODE_MEMB="Detail", optional
    EXPORT_PATH: str  # Directory path to save the report files, required
    OUTPUT_NAME: str  # Output file base name, required


# --- 54. DESIGN/RC/KDS-41-20-2022/BC-ANAL — RC Beam Check Perform -----------


def perform_beam_check(
    argument: PerformRcMemberCheckArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #54 — BC-ANAL — RC Beam Check
    Perform. Runs code-checking on RC beam members that already have rebar
    assigned. Response: ``{"message": "success"}``.

    ✅ **Re-verified 2026-07-25: ran clean 4/4 — on the same build that hung.**
    An independent production tool (the QuickRebar NX web app) now ships
    this call behind a user-triggered "recheck" button and ran it — plus
    ``perform_column_check`` including ``PERFORM_TYPE: "ALL"`` — cleanly
    4/4 with the app staying connected; ``PERFORM_TYPE: "ALL"`` re-checks a
    whole model in roughly 2 seconds. This lifts the blanket "never call
    this" rule — but see the caveat below before treating it as fixed.

    ⚠️ CONFIRMED to hang on **Gen NX 2026 (v2.1), build 06/23/2026**,
    reproduced on two independent real models once the full precondition
    chain (member type + rebar + a KDS-recognized load combination +
    confirmed-queryable analysis results) was satisfied. One attempt
    silently locked just that element's check endpoints; another crashed the
    app outright with a **"Failed to disconnect the work session"**
    license-error dialog (unrecoverable — the program always dies once it
    appears).

    ⚠️ **The clean re-verification ran on that exact same build** — this was
    not fixed by a vendor patch, so the real trigger is still unidentified
    (model state, call sequence, and client/transport are all untested
    candidates). Every test on both sides also used the **KDS 41 20:2022**
    code specifically. Treat the defensive pattern as the actual mitigation,
    not as hygiene: use a short timeout (the production tool uses 25s) and —
    because a timed-out check may still have committed its results — read
    ``get_beam_check_table`` regardless of whether this call returned. If
    you only need results the user already computed in Gen NX's own GUI,
    reading ``get_beam_check_table`` alone needs no perform call at all and
    carries none of this risk. See docs/live_verification_notes.md.
    """
    return _post(f"{_BASE}/BC-ANAL", argument, client)


# --- 55. DESIGN/RC/KDS-41-20-2022/BC-TABLE — RC Beam Check Table -----------


def get_beam_check_table(
    argument: RcMemberCheckTableArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #55 — BC-TABLE — RC Beam Check
    Table. Response: ``{table_name_or_"RC Beam Checking Result": {"FORCE":
    ..., "DIST": ..., "HEAD": [...], "DATA": [[...], ...]}}``. HEAD includes
    strength checks (Neg/Pos moment, shear) and rebar-detail checks (main
    rebar, stirrup)."""
    return _post(f"{_BASE}/BC-TABLE", argument, client)


# --- 56. DESIGN/RC/KDS-41-20-2022/BC-REPORT — RC Beam Check Report ---------


def export_beam_check_report(
    argument: RcMemberCheckReportArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #56 — BC-REPORT — RC Beam
    Check Report. Response: ``{"SUCCESS": bool, "FILE_PATH": str, "MESSAGE":
    str}``."""
    return _post(f"{_BASE}/BC-REPORT", argument, client)


# --- 57. DESIGN/RC/KDS-41-20-2022/CC-ANAL — RC Column Check Perform --------


def perform_column_check(
    argument: PerformRcMemberCheckArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #57 — CC-ANAL — RC Column
    Check Perform. Runs P-M interaction/shear code-checking on RC column
    members that already have rebar assigned. Response: ``{"message":
    "success"}``.

    ✅ **Re-verified 2026-07-25: ran clean 4/4 — on the same build that hung.**
    An independent production tool (the QuickRebar NX web app) ran this
    call — including ``PERFORM_TYPE: "ALL"`` — plus ``perform_beam_check``
    cleanly 4/4 with the app staying connected. This lifts the blanket
    "never call this" rule — but see the caveat below before treating it as
    fixed.

    ⚠️ CONFIRMED to stall on **Gen NX 2026 (v2.1), build 06/23/2026**: the
    desktop app's progress dialog got stuck at "Converting Design Results... 0%",
    5 times out of 5 whenever the target had real rebar data, a recognized
    design load combination, and confirmed analysis results — on natively
    KDS-configured production models, not just synthetic setups, and
    independent of admin/elevated privileges. On one occasion the app's own
    message log showed the check had actually finished while the dialog
    stayed frozen at 0%, suggesting a stuck completion-signal bug rather
    than the check itself deadlocking. Consequences varied: a forced process
    kill 3 of 5 times, clean recovery via "Stop Execution" the other 2.
    Every call that didn't hit the precondition combination instead returned
    a clean, correctly-shaped ``{"error": ...}`` response, so the request
    shape itself was never the problem.

    ⚠️ **The clean re-verification ran on that exact same build** — this was
    not fixed by a vendor patch, so the real trigger is still unidentified
    (model state, call sequence, and client/transport are all untested
    candidates). Every test on both sides also used the **KDS 41 20:2022**
    code specifically. Treat the defensive pattern as the actual mitigation:
    use a short timeout, and read ``get_column_check_table`` regardless of
    whether this call returned — a timed-out check very likely still
    committed its results, which is exactly what the original reproductions
    showed (full OK/NG, P-M ratios, and assigned rebar came back immediately
    after a "hung" call, with no retry needed). See
    docs/live_verification_notes.md for the full history.
    """
    return _post(f"{_BASE}/CC-ANAL", argument, client)


# --- 58. DESIGN/RC/KDS-41-20-2022/CC-TABLE — RC Column Check Table ---------


def get_column_check_table(
    argument: RcMemberCheckTableArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #58 — CC-TABLE — RC Column
    Check Table. Response: ``{table_name_or_"RC Column Checking Result":
    {"FORCE": ..., "DIST": ..., "HEAD": [...], "DATA": [[...], ...]}}``.
    HEAD includes P-M interaction ratios, end/mid shear, and main-rebar/hoop
    rebar-detail checks.

    ⚠️ Live-tested workaround: if ``perform_column_check`` (CC-ANAL) times
    out against a live session, call this afterward before assuming the
    check failed — it returned full real results immediately after a
    "hung" CC-ANAL call in testing. See docs/live_verification_notes.md.

    This also reads results the user already computed in Gen NX's own GUI,
    so it is the zero-risk way to get a verdict with no perform call at all.
    """
    return _post(f"{_BASE}/CC-TABLE", argument, client)


# --- 59. DESIGN/RC/KDS-41-20-2022/CC-REPORT — RC Column Check Report -------


def export_column_check_report(
    argument: RcMemberCheckReportArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #59 — CC-REPORT — RC Column
    Check Report. Response: ``{"SUCCESS": bool, "FILE_PATH": str, "MESSAGE":
    str}``."""
    return _post(f"{_BASE}/CC-REPORT", argument, client)


# --- 60. DESIGN/RC/KDS-41-20-2022/BRC-ANAL — RC Brace Check Perform --------


def perform_brace_check(
    argument: PerformRcMemberCheckArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #60 — BRC-ANAL — RC Brace
    Check Perform. Runs P-M interaction/shear code-checking on RC brace
    members that already have rebar assigned. Response: ``{"message":
    "success"}``.

    ⚠️ Never independently tested. Its siblings ``perform_column_check``
    (CC-ANAL) and ``perform_beam_check`` (BC-ANAL) were confirmed to hang
    Gen NX 2026 (v2.1), build 06/23/2026, then ran clean on that same build
    on 2026-07-25 — i.e. the trigger is unidentified rather than fixed; see
    docs/live_verification_notes.md. Assume the same history applies here:
    use a short timeout, and read ``get_brace_check_table`` regardless of
    whether this call returns.
    """
    return _post(f"{_BASE}/BRC-ANAL", argument, client)


# --- 61. DESIGN/RC/KDS-41-20-2022/BRC-TABLE — RC Brace Check Table ---------


def get_brace_check_table(
    argument: RcMemberCheckTableArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #61 — BRC-TABLE — RC Brace
    Check Table. Response: ``{table_name_or_"Result Table": {"FORCE": ...,
    "DIST": ..., "HEAD": [...], "DATA": [[...], ...]}}`` — note the manual's
    own worked example omits TABLE_NAME and shows the response keyed
    "Result Table" (not "RC Brace Checking Result", despite that being
    TABLE_NAME's documented default); structure otherwise mirrors the
    column check table but with a single (non end/mid-split) shear/hoop
    location."""
    return _post(f"{_BASE}/BRC-TABLE", argument, client)


# --- 62. DESIGN/RC/KDS-41-20-2022/BRC-REPORT — RC Brace Check Report -------


def export_brace_check_report(
    argument: RcMemberCheckReportArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #62 — BRC-REPORT — RC Brace
    Check Report. Response: ``{"SUCCESS": bool, "FILE_PATH": str, "MESSAGE":
    str}``."""
    return _post(f"{_BASE}/BRC-REPORT", argument, client)


# === Wall check triplet (items 63-65) — SELECTIONS-based (WALL_IDS+STORY, not element IDs) ===
#
# WC-ANAL/WC-TABLE/WC-REPORT's "SELECTIONS[].WALL_IDS" (KEYS/TO — pick one)
# and "SELECTIONS" array entry ({WALL_IDS, STORY}) are identical in shape to
# WD-ANAL/WD-TABLE/WD-REPORT's own "SELECTIONS" (#48/#49/#50, design_forces.py)
# — reused here as RcWallIdsSelector/RcWallDesignSelection rather than
# redeclared.


# --- 63. DESIGN/RC/KDS-41-20-2022/WC-ANAL — RC Wall Check Perform ----------


class PerformRcWallCheckArgument(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #63 — WC-ANAL Argument.

    Walls are targeted by WALL_IDS+STORY (not element numbers). If
    SELECTIONS is omitted or empty, all wall IDs and all stories are
    checked.
    """

    SELECTIONS: List[RcWallDesignSelection]  # Wall/story selection list; omit or empty for all walls/stories, optional


def perform_wall_check(
    argument: PerformRcWallCheckArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #63 — WC-ANAL — RC Wall Check
    Perform. Response: ``{"message": "success"}``.

    ⚠️ Live-tested and CONFIRMED to NOT reproduce the sibling
    ``perform_column_check`` (CC-ANAL) stall: on a real, wall-heavy
    production model (KDS 41 20:2022 native, real pre-existing wall-check
    data), both a single-wall/story call and a full all-walls call
    (``SELECTIONS`` omitted) returned ``{"message": "success"}`` cleanly
    in under 6 seconds — no stuck "Converting Design Results" dialog. This
    is useful negative evidence that CC-ANAL's stall isn't a blanket
    property of every "perform check" function in this file. Independently
    corroborated 2026-07-25: a production tool (the QuickRebar NX web app)
    ships this call alongside CC-ANAL for live wall verdicts, and neither
    hung. Note the stall was never about the targeting scheme —
    ``perform_wall_design`` (WD-ANAL, design_forces.py) is also
    WID+STORY-targeted and *did* hang on the same build. See
    docs/live_verification_notes.md for the full writeup.
    """
    return _post(f"{_BASE}/WC-ANAL", argument, client)


# --- 64. DESIGN/RC/KDS-41-20-2022/WC-TABLE — RC Wall Check Table -----------


class RcWallCheckTableArgument(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #64 — WC-TABLE Argument."""

    TABLE_TYPE: str  # Output unit: "WID+STORY"=wall ID+story/"WID"=wall ID, required
    SELECTIONS: List[RcWallDesignSelection]  # Wall/story selection list; omit or empty for all walls/stories, optional
    PRI_SORT: int  # WID+STORY sort: Story=0/WID=1, default 1, optional
    PRI_SORT_WID: int  # WID sort: WallMark=0/WID=1, default 1, optional
    RESULT: int  # Filter by check status: All=0/OK=1/NG=2, default 0, optional
    TABLE_NAME: str  # Response Table Title, default "RC Wall Checking Result", optional
    EXPORT_PATH: str  # Result Table Save Path, optional
    UNIT: TableUnit  # Response Unit Setting (FORCE/DIST/HEAT/TEMP), optional
    STYLES: TableStyles  # Response Number Format (FORMAT/PLACE), optional
    COMPONENTS: List[str]  # Result table components, e.g. "WID"/"Story"/"Wall Mark"/"Pu"/"Rat-Py"/"Rat-Pz"/"Mcy"/"Mcz"/"Rat-My"/"Rat-Mz"/"Vu"/"phiVn"/"Rat-V"/"CHK_STR"/"CHK_RBR", optional


def get_wall_check_table(
    argument: RcWallCheckTableArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #64 — WC-TABLE — RC Wall
    Check Table. Unlike the beam/column/brace check tables, the response is
    NOT a HEAD/DATA table: it echoes ``TABLE_NAME``/``TABLE_TYPE``/``UNIT``/
    ``STYLES``/``COMPONENTS`` at the top level plus a ``"DATA"`` array whose
    entries are objects keyed by each requested COMPONENTS name (one object
    per wall-mark/story row), e.g. ``{"TABLE_NAME": ..., "COMPONENTS": [...],
    "DATA": [{"WID": 1, "Story": "3F", ...}, ...]}``."""
    return _post(f"{_BASE}/WC-TABLE", argument, client)


# --- 65. DESIGN/RC/KDS-41-20-2022/WC-REPORT — RC Wall Check Report ---------


class RcWallCheckReportArgument(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #65 — WC-REPORT Argument."""

    REPORT_TYPE: str  # Output unit: "WID+STORY"/"WID", default "WID+STORY", required
    CURRENT_MODE_WID_STORY: str  # WID+STORY output mode: "Graphic"/"Detail"/"Summary"/"PMCurve", conditionally required if REPORT_TYPE="WID+STORY"
    CURRENT_MODE_WID: str  # WID output mode: "Graphic"/"Summary"/"PMCurve" (no Detail), conditionally required if REPORT_TYPE="WID"
    SELECTIONS: List[RcWallDesignSelection]  # Wall/story selection list; omit or empty for all walls/stories, optional
    EXPORT_PATH: str  # Directory path to save the report files, required
    OUTPUT_NAME: str  # Output file base name, required


def export_wall_check_report(
    argument: RcWallCheckReportArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #65 — WC-REPORT — RC Wall
    Check Report. Response: ``{"SUCCESS": bool, "FILE_PATH": str, "MESSAGE":
    str}``."""
    return _post(f"{_BASE}/WC-REPORT", argument, client)


# === 66. DESIGN/RC/KDS-41-20-2022/CDESIGN — RC Concrete Comprehensive Design Result ===


class RcDesignResultRgbColor(TypedDict, total=False):
    """CDESIGN's "BGCOLOR_TOP"/"BGCOLOR_BOTTOM" — RGB color triple."""

    R: int  # Red component, 0-255, optional
    G: int  # Green component, 0-255, optional
    B: int  # Blue component, 0-255, optional


class RcDesignResultLoadCaseComb(TypedDict, total=False):
    """RESULT_GRAPHIC's "LOAD_CASE_COMB"."""

    TYPE: str  # Load case type, fixed "CBC"=Concrete Design Load Combination, required
    NAME: str  # Load combination name, required


class RcDesignResultTypeOfDisplay(TypedDict, total=False):
    """RESULT_GRAPHIC's "TYPE_OF_DISPLAY". CONTOUR/LEGEND/VALUES sub-fields
    are not detailed in this chapter's JSON Schema (plain ``"type": "object"``
    with no nested properties), so they are typed as free-form dicts here
    rather than invented nested TypedDicts (mirrors steel_kds.py's DREULT
    ACTIVE/DISPLAY precedent)."""

    CONTOUR: Dict[str, Any]  # Contour display settings; sub-fields undocumented in this chapter, optional
    LEGEND: Dict[str, Any]  # Legend display settings; sub-fields undocumented in this chapter, optional
    VALUES: Dict[str, Any]  # Value display settings; sub-fields undocumented in this chapter, optional


class RcDesignResultDisplayMembers(TypedDict, total=False):
    """RESULT_GRAPHIC's "DISPLAY_MEMBERS"."""

    BEAM: bool  # Display beam members, default true, optional
    COLUMN: bool  # Display column members, default true, optional
    BRACE: bool  # Display brace members, default true, optional
    WALL: bool  # Display wall members, default true, optional


class RcDesignResultOutputComponent(TypedDict, total=False):
    """RESULT_GRAPHIC's "OUTPUT_COMPONENT"."""

    RATIO_AXIAL_STRESS: bool  # Display strength ratio, default true, optional
    MAIN_REBAR: bool  # Display main rebar, default true, optional
    SHEAR_REINFORCEMENT: bool  # Display shear reinforcement, default true, optional


class RcDesignResultColumnSectionSize(TypedDict, total=False):
    """RESULT_GRAPHIC's "COLUMN_SECTION_SIZE"."""

    SCALE_FACTOR: float  # Scale factor for column section visualization, 0.1-100, default 1, optional


class RcDesignResultValueOption(TypedDict, total=False):
    """RESULT_GRAPHIC's "VALUE_OPTION"."""

    DECIMAL_PLACES: int  # Number of decimal places, 0-15, default 2, optional
    EXPONENTIAL: bool  # Use exponential notation, default false, optional


class RcDesignResultOutputSectLocation(TypedDict, total=False):
    """RESULT_GRAPHIC's "OUTPUT_SECT_LOCATION"."""

    OPT_I: bool  # Show at I-end, default false, optional
    OPT_CENTER_MID: bool  # Show at center/mid, default false, optional
    OPT_J: bool  # Show at J-end, default false, optional
    OPT_MAX: bool  # Show at max-ratio location, default true, optional
    OPT_ALL: bool  # Show at all locations, default false, optional


class RcDesignResultGraphic(TypedDict, total=False):
    """"RESULT_GRAPHIC" — result graphic display settings."""

    LOAD_CASE_COMB: RcDesignResultLoadCaseComb  # Load case/combination selection, required
    COMPONENTS: str  # Ratio component: "Axial"/"Shear-y"/"Shear-z"/"Bend-y"/"Bend-z"/"Combined", default "Combined", optional
    TYPE_OF_DISPLAY: RcDesignResultTypeOfDisplay  # Display options for design result visualization, optional
    REINFORCEMENT: bool  # Display reinforcement, default true, optional
    REINFORCEMENT_TYPE: str  # Reinforcement display type: "REBAR"/"AREA"/"RATIO", default "REBAR", optional
    DISPLAY_MEMBERS: RcDesignResultDisplayMembers  # Member types to display, optional
    OUTPUT_COMPONENT: RcDesignResultOutputComponent  # Output component selection, optional
    COLUMN_SECTION_SIZE: RcDesignResultColumnSectionSize  # Column section size display settings, optional
    VALUE_OPTION: RcDesignResultValueOption  # Value display format settings, optional
    OUTPUT_SECT_LOCATION: RcDesignResultOutputSectLocation  # Output section location settings, optional


class ComprehensiveDesignResultArgument(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #66 — CDESIGN Argument.

    Captures/saves the combined beam/column/brace/wall RC design result
    view as a JPG image. ACTIVE/ANGLE/DISPLAY sub-fields are not detailed
    in this chapter (the manual refers to the separate Active/Angle/Display
    documentation), so they are typed as free-form dicts here rather than
    invented nested TypedDicts (mirrors steel_kds.py's DREULT precedent).
    The manual does not publish a worked Request/Response example for this
    endpoint; the docstring's shape follows the JSON Schema's required
    fields.
    """

    EXPORT_PATH: str  # Image file save path and file name, required
    FIGURE_NAME: str  # Smart report image name, required
    WIDTH: int  # Image width in pixels, 100-10000, default 1000, optional
    HEIGHT: int  # Image height in pixels, 100-10000, default 1000, optional
    STAGE_NAME: str  # Construction stage name, optional
    SET_HIDDEN: bool  # Hidden option, default false, optional
    ACTIVE: Dict[str, Any]  # View/Active settings; sub-fields undocumented in this chapter, optional
    ANGLE: Dict[str, Any]  # View/Angle settings; sub-fields undocumented in this chapter, optional
    DISPLAY: Dict[str, Any]  # View/Display settings; sub-fields undocumented in this chapter, optional
    PERSPECTIVE: bool  # Enable perspective view, default false, optional
    ZOOM_LEVEL: float  # Zoom level, 25-200, default 100, optional
    BGCOLOR_TOP: RcDesignResultRgbColor  # Top background color, optional
    BGCOLOR_BOTTOM: RcDesignResultRgbColor  # Bottom background color, optional
    RESULT_GRAPHIC: RcDesignResultGraphic  # Result graphic display settings, required


def export_comprehensive_design_result_image(
    argument: ComprehensiveDesignResultArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #66 — CDESIGN — RC Concrete
    Comprehensive Design Result. Response: ``{"message": "success"}``."""
    return _post(f"{_BASE}/CDESIGN", argument, client)


# === Items 67-69 — Column/Brace/Beam Design Forces (share one real endpoint) ===
#
# The manual states explicitly (see each item's "공유 URI" note) that items
# 67/68/69 are all `POST DESIGN/RC/KDS-41-20-2022/TABLE`, distinguished only
# by Argument.TABLE_TYPE. Mirrors post/design.py's
# _get_design_forces_table() shared-helper + thin-wrapper pattern.

# 67. Column Design Forces
TABLE_TYPE_COLUMN_DESIGN_FORCES = "COLUMNDESIGNFORCES"

# 68. Brace Design Forces
TABLE_TYPE_BRACE_DESIGN_FORCES = "BRACEDESIGNFORCES"

# 69. Beam Design Forces
TABLE_TYPE_BEAM_DESIGN_FORCES = "BEAMDESIGNFORCES"


class RcDesignForcesArgument(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #67/#68/#69 — TABLE Argument
    (identical shape across column/brace/beam; only TABLE_TYPE's fixed
    value, COMPONENTS' valid values, and PARTS' valid values differ — beam
    COMPONENTS uses "Fz"/"Mx"/"My(-)"/"My(+)" while column/brace use
    "Fx"/"Fy"/"Fz"/"Mx"/"My"/"Mz"; all three share the same PARTS enum
    "PartI"/"Part2/4"/"PartJ"). NODE_ELEMS/UNIT/STYLES reuse
    post/base.py's NodeElemsSelector/TableUnit/TableStyles (identical
    shapes).
    """

    TABLE_NAME: str  # Response Table Title, default "", optional
    TABLE_TYPE: str  # Result Table Type, fixed one of TABLE_TYPE_*_DESIGN_FORCES, required
    EXPORT_PATH: str  # Result Table Save Path, optional
    UNIT: TableUnit  # Response Unit Setting (FORCE/DIST/HEAT/TEMP), default "System", optional
    STYLES: TableStyles  # Response Number Format (FORMAT/PLACE), default "System", optional
    COMPONENTS: List[str]  # Result table components; see class docstring for the per-member-type valid values, optional
    NODE_ELEMS: NodeElemsSelector  # Node/Element No. Input, optional
    PARTS: List[str]  # Element Part Number: "PartI"/"Part2/4"/"PartJ", default ["All"], optional


def _get_rc_design_forces_table(
    table_type: str,
    table_name: str = "",
    *,
    export_path: Optional[str] = None,
    node_elems: Optional[NodeElemsSelector] = None,
    parts: Optional[List[str]] = None,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    argument: RcDesignForcesArgument = {"TABLE_NAME": table_name, "TABLE_TYPE": table_type}
    if export_path is not None:
        argument["EXPORT_PATH"] = export_path
    if node_elems is not None:
        argument["NODE_ELEMS"] = node_elems
    if parts is not None:
        argument["PARTS"] = parts
    if unit is not None:
        argument["UNIT"] = unit
    if styles is not None:
        argument["STYLES"] = styles
    if components is not None:
        argument["COMPONENTS"] = components
    return _post(f"{_BASE}/TABLE", argument, client)


# --- 67. DESIGN/RC/KDS-41-20-2022/TABLE — Column Design Forces -------------


def get_column_design_forces_table(
    table_name: str = "",
    *,
    export_path: Optional[str] = None,
    node_elems: Optional[NodeElemsSelector] = None,
    parts: Optional[List[str]] = None,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #67 — TABLE — Column Design
    Forces. Requires analysis and design to already be complete. Response:
    ``{table_name_or_"empty": {"FORCE": ..., "DIST": ..., "HEAD": ["Index",
    "Memb", "Part", "LComName", "Type", "Fx", "Fy", "Fz", "Mx", "My", "Mz"],
    "DATA": [[...], ...]}}``.

    ⚠️ Live-tested 2026-08-01 on Gen NX: this call killed the session —
    ``verify_connection()`` kept reporting "connected" while every
    subsequent ``/db/*`` call timed out, then the NX process itself died.
    Reproduced twice independently (a real production "apartment" model,
    and again in isolation on a freshly-recovered, completely empty
    model), ruling out model content as the cause. No data loss either
    time after the standard crash-recovery cycle (dismiss dialogs →
    relaunch → New Project → close → reconnect with the same MAPI key).
    Root cause unidentified; reported to MIDASIT. Not yet
    tested on Civil NX. Same endpoint/underlying helper as
    :func:`get_brace_design_forces_table` and
    :func:`get_beam_design_forces_table` — treat those as equally at
    risk until independently tested.

    ⚠️ Re-tested 2026-08-07 on the same patch build that fixed two
    neighbouring crash reports (Gen NX v975, build 08/06/2026) — **not
    fixed**. MIDASIT
    couldn't reproduce it on their side and asked for the test model;
    re-tested two cases instead of sharing one. Against the currently-open
    real model (small, no design run yet): no crash, clean empty response.
    Against a completely blank ``/doc/NEW`` document (0 nodes): crashed
    again, identical signature (``verify_connection()`` → disconnected,
    every ``/db/*`` call → 404). The blank-document repro needs no model
    file at all, so that's what was reported back — real-model crash risk
    is unresolved either way; don't treat the one non-crashing real-model
    test as evidence this is now safe.

    ⚠️ Re-tested 2026-08-11 on Gen NX (v2.1, build 08/11/2026), a fresh
    blank ``/doc/NEW`` document (0 nodes) — same repro shape as the
    crashing case above: this time a clean empty response, no crash,
    session stayed healthy. This is that crash's most reliably-reproducing
    case (crashed twice independently, reconfirmed not-fixed as recently
    as 2026-08-07), so a clean pass here is the strongest single data
    point yet, but the 2026-08-07 note above already shows this call
    isn't even monotonic with data complexity (crashed blank, clean on a
    63-node real model) — treat as reduced-but-not-cleared until an
    independent second re-test.

    ✅ **Fixed, confirmed 2026-08-25.** MIDASIT root-caused it as
    missing guard code for a Design API call made with no analysis run,
    and shipped a fix in the 2026-08-11 patch build. Re-tested on Gen NX
    v2.1, build 08/20/2026 (a different, later build than the 08-11
    patch) against the same blank-document shape: clean, no crash,
    session healthy — the second consecutive clean pass since the patch,
    which clears the "needs an independent second re-test" bar above.
    Treat the crash risk on this endpoint as resolved. This does **not**
    cover the sibling ``/post/TABLE`` code path
    (:mod:`midas_nx.post.design`'s ``get_column_design_forces_table`` and
    friends) — that's a separate, independently-crashing endpoint per its
    own docstring, not addressed by this fix."""
    return _get_rc_design_forces_table(
        TABLE_TYPE_COLUMN_DESIGN_FORCES,
        table_name,
        export_path=export_path,
        node_elems=node_elems,
        parts=parts,
        unit=unit,
        styles=styles,
        components=components,
        client=client,
    )


# --- 68. DESIGN/RC/KDS-41-20-2022/TABLE — Brace Design Forces --------------


def get_brace_design_forces_table(
    table_name: str = "",
    *,
    export_path: Optional[str] = None,
    node_elems: Optional[NodeElemsSelector] = None,
    parts: Optional[List[str]] = None,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #68 — TABLE — Brace Design
    Forces. Response shape/columns match Column Design Forces (see
    :func:`get_column_design_forces_table`).

    ⚠️ Shares the same ``TABLE`` endpoint/helper as
    :func:`get_column_design_forces_table`, which crashed Gen NX
    (reproduced twice, reported to MIDASIT) — not
    independently tested on Gen, but treat as equally at risk until it is.
    Confirmed clean on Civil NX 2026-08-07 (informative ``"there was an
    error creating utbl (ex PostMode ...)"`` error, no crash).

    Re-tested 2026-08-11 on Gen NX (v2.1, build 08/11/2026), blank
    ``/doc/NEW`` document: clean empty response, no crash, session stayed
    healthy. A single clean pass is not independent proof that risk is
    gone — treat as reduced-but-not-cleared until a real-model
    retest.

    ✅ **Fixed, confirmed 2026-08-25**, same as
    :func:`get_column_design_forces_table` — see that docstring for the
    root cause and the two-consecutive-clean-pass evidence. Re-tested
    here too on the same Gen NX v2.1, build 08/20/2026 session: clean,
    no crash. Treat this endpoint's crash risk as resolved; the sibling
    ``/post/TABLE`` code path in :mod:`midas_nx.post.design` is still
    unaddressed."""
    return _get_rc_design_forces_table(
        TABLE_TYPE_BRACE_DESIGN_FORCES,
        table_name,
        export_path=export_path,
        node_elems=node_elems,
        parts=parts,
        unit=unit,
        styles=styles,
        components=components,
        client=client,
    )


# --- 69. DESIGN/RC/KDS-41-20-2022/TABLE — Beam Design Forces ---------------


def get_beam_design_forces_table(
    table_name: str = "",
    *,
    export_path: Optional[str] = None,
    node_elems: Optional[NodeElemsSelector] = None,
    parts: Optional[List[str]] = None,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #69 — TABLE — Beam Design
    Forces. Response: ``{table_name_or_"empty": {"FORCE": ..., "DIST": ...,
    "HEAD": ["Index", "Memb", "Part", "LComName", "Type", "Fz", "Mx",
    "My(-)", "My(+)"], "DATA": [[...], ...]}}`` — column set differs from
    Column/Brace Design Forces (no Fx/Fy/My/Mz; adds signed My(-)/My(+)).

    ⚠️ Shares the same ``TABLE`` endpoint/helper as
    :func:`get_column_design_forces_table`, which crashed Gen NX
    (reproduced twice, reported to MIDASIT) — not
    independently tested on Gen via this exact endpoint, but the sibling
    :func:`midas_nx.post.design.get_beam_design_forces_table` (different
    endpoint, ``/post/TABLE``, same ``TABLE_TYPE``) is independently
    confirmed crashing Gen NX, so treat this one as equally at risk until
    tested. Confirmed clean on Civil NX 2026-08-07 (informative
    ``"there was an error creating utbl (ex PostMode ...)"`` error, no
    crash).

    Re-tested 2026-08-11 on Gen NX (v2.1, build 08/11/2026), blank
    ``/doc/NEW`` document: clean empty response, no crash, session stayed
    healthy. A single clean pass is not independent proof that
    sibling-crash risk is gone — treat as reduced-but-not-cleared until a
    real-model retest.

    ✅ **This ``/DESIGN/RC/KDS-...`` endpoint fixed, confirmed 2026-08-25**
    — see :func:`get_column_design_forces_table` for the root cause and
    the two-consecutive-clean-pass evidence (same Gen NX v2.1, build
    08/20/2026 session). The sibling
    :func:`midas_nx.post.design.get_beam_design_forces_table`
    (``/post/TABLE``, independently confirmed crashing) is a genuinely
    different code path and was **not** retested — don't treat this
    fix as covering it."""
    return _get_rc_design_forces_table(
        TABLE_TYPE_BEAM_DESIGN_FORCES,
        table_name,
        export_path=export_path,
        node_elems=node_elems,
        parts=parts,
        unit=unit,
        styles=styles,
        components=components,
        client=client,
    )
