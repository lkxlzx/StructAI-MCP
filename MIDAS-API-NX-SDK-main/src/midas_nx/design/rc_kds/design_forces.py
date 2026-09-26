"""Source: docs/manual/26_Design_RC_KDS41202022.md, items 39-53 (of 69 total;
see design/rc_kds/setup.py, rebar.py, checks.py for the rest).

RC design code KDS 41 20:2022 — design-execution/result-table/report
endpoints for beam/column/brace/wall/haunched-beam members (5 member types
x perform/table/report). Endpoint prefix: ``/DESIGN/RC/KDS-41-20-2022/<CODE>``.

All 15 endpoints are POST-only, ``"Argument"``-wrapped (not ID-keyed
``"Assign"``), implemented as plain functions via ``post_argument`` (mirrors
``design/steel_kds.py``'s Group 4 and ``post/design.py``).

Beam (BD)/Column (CD)/Brace (BRD) share one Perform argument shape and one
Table argument shape verbatim across their three manual sections, so those
are each modeled with a single shared TypedDict reused by all three member
types' functions. Their Report argument shapes differ only between Beam
(has DETAIL_POSITIONS, no "PMCurve" mode) and Column/Brace (has "PMCurve",
no DETAIL_POSITIONS) — Column and Brace share one Report TypedDict, Beam
gets its own. Wall (WD) and Haunched Beam (HCD) have genuinely different
field sets in all three actions (wall is selected by WALL_IDS+STORY instead
of ELEMS/SECTIONS, with a different data.COMPONENTS/data.ROWS response
shape for its table; haunched beam has no PERFORM_TYPE/TABLE_TYPE/
REPORT_TYPE/SECTIONS at all), so each keeps its own three TypedDicts.
"""
from __future__ import annotations

from typing import List, Optional, TypedDict

from ...client import MidasClient
from ...client import post_argument as _post
from ...post.base import NodeElemsSelector, TableStyles, TableUnit

_BASE = "/DESIGN/RC/KDS-41-20-2022"


# === Beam / Column / Brace shared shapes (identical across #39/42/45 and #40/43/46) ===


class RcMemberDesignPerformArgument(TypedDict, total=False):
    """Shared Perform Argument for BD-ANAL (#39), CD-ANAL (#42), BRD-ANAL
    (#45) — all three manual sections document the identical PERFORM_TYPE/
    ELEMS/SECTIONS shape. ELEMS reuses post/base.py's NodeElemsSelector
    (identical KEYS/TO/STRUCTURE_GROUP_NAME shape).

    The JSON Schema's ``oneOf`` requires exactly one of ELEMS/SECTIONS even
    though PERFORM_TYPE defaults to "ALL" (which conceptually needs
    neither) — every worked example in the manual (including PERFORM_TYPE=
    "ALL" for CD-ANAL) still supplies ELEMS, so this is followed verbatim
    rather than treated as a documentation error.
    """

    PERFORM_TYPE: str  # Target type: "ALL"=all elements/"ELEMS"=by element no./"SECTIONS"=by section no., default "ALL", optional
    ELEMS: NodeElemsSelector  # Element No. Input, required if not using SECTIONS (oneOf)
    SECTIONS: List[int]  # Section No. (or name) Input, required if not using ELEMS (oneOf)


class RcMemberDesignTableArgument(TypedDict, total=False):
    """Shared Table Argument for BD-TABLE (#40), CD-TABLE (#43), BRD-TABLE
    (#46) — identical field set across all three manual sections. ELEMS/
    UNIT/STYLES reuse post/base.py's NodeElemsSelector/TableUnit/TableStyles
    (identical shapes).

    BD-TABLE's JSON Schema marks ELEMS/SECTIONS mutually exclusive
    (``oneOf`` with ``not``); CD-TABLE/BRD-TABLE's schemas omit that
    constraint even though their own Parameters tables describe the same
    "one of ELEMS/SECTIONS" intent — a manual-internal inconsistency, not
    reproduced here since TypedDict doesn't encode oneOf either way.
    """

    TABLE_TYPE: str  # Result Table Type: "MEMB"=member-based/"PROP"=section-based, required
    ELEMS: NodeElemsSelector  # Element No. Input, optional (mutually exclusive with SECTIONS per BD-TABLE's schema)
    SECTIONS: List[int]  # Section No. Input, optional (mutually exclusive with ELEMS per BD-TABLE's schema)
    PRI_SORT: int  # Primary sort for member-based output: SECT=0/MEMB=1, default 1, optional
    RESULT: int  # Filter by check status: All=0/OK=1/NG=2, default 0, optional
    TABLE_NAME: str  # Response Table Title, default "RC Beam Design Result" for BD-TABLE (no fixed default documented for CD-TABLE/BRD-TABLE), optional
    EXPORT_PATH: str  # Result Table Save Path, optional
    UNIT: TableUnit  # Response Unit Setting (FORCE/DIST/HEAT/TEMP), default System, optional
    STYLES: TableStyles  # Response Number Format (FORMAT/PLACE), default System, optional
    COMPONENTS: List[str]  # Result table components (see each endpoint's HEAD column list in the manual), optional


class RcColumnBraceDesignReportArgument(TypedDict, total=False):
    """Shared Report Argument for CD-REPORT (#44) and BRD-REPORT (#47) —
    identical field set across both manual sections (CURRENT_MODE_MEMB
    includes "PMCurve"; no DETAIL_POSITIONS, unlike BD-REPORT). ELEMS reuses
    post/base.py's NodeElemsSelector.
    """

    REPORT_TYPE: str  # Report Table Type: "MEMB"/"PROP", required
    CURRENT_MODE_MEMB: str  # Output mode for REPORT_TYPE="MEMB": "Graphic"=JPG/"Detail"=DOC/"Summary"=TXT/"PMCurve"=JPG P-M interaction diagram, conditionally required (MEMB)
    CURRENT_MODE_PROP: str  # Output mode for REPORT_TYPE="PROP": "Graphic"/"Summary", conditionally required (PROP)
    ELEMS: NodeElemsSelector  # Element No. Input, required if not using SECTIONS (oneOf)
    SECTIONS: List[int]  # Section No. Input, required if not using ELEMS (oneOf)
    EXPORT_PATH: str  # Directory path to save the report files, required
    OUTPUT_NAME: str  # Output file base name (multi-element runs prefix index+element no.), required


# --- 39. DESIGN/RC/KDS-41-20-2022/BD-ANAL — RC Beam Design Perform ----------


def perform_beam_design(
    argument: RcMemberDesignPerformArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #39 — BD-ANAL — RC Beam Design
    Perform. Executes the RC beam design calculation; results are stored on
    the model and later retrieved via BD-TABLE/BD-REPORT. Response:
    ``{"message": "success"}``."""
    return _post(f"{_BASE}/BD-ANAL", argument, client)


# --- 40. DESIGN/RC/KDS-41-20-2022/BD-TABLE — RC Beam Design Table ----------


def get_beam_design_table(
    argument: RcMemberDesignTableArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #40 — BD-TABLE — RC Beam
    Design Table. Response: ``{table_name_or_"RC Beam Design Result":
    {"FORCE": ..., "DIST": ..., "HEAD": [...25 columns...], "DATA":
    [[...], ...]}}``."""
    return _post(f"{_BASE}/BD-TABLE", argument, client)


# --- 41. DESIGN/RC/KDS-41-20-2022/BD-REPORT — RC Beam Design Report --------


class RcReportDetailPositions(TypedDict, total=False):
    """"DETAIL_POSITIONS" — output positions for Detail mode, {END_I, MID,
    END_J}. Shared across this chapter's *-REPORT endpoints wherever Detail
    mode is offered: BD-REPORT (#41, this file) and BC-REPORT/CC-REPORT/
    BRC-REPORT (#56/#59/#62, see checks.py, which imports this class rather
    than redeclaring it)."""

    END_I: bool  # Include end-I position, default true, optional
    MID: bool  # Include mid-span position, default false, optional
    END_J: bool  # Include end-J position, default false, optional


class RcBeamDesignReportArgument(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #41 — BD-REPORT Argument.

    ELEMS reuses post/base.py's NodeElemsSelector. Unlike CD-REPORT/
    BRD-REPORT, CURRENT_MODE_MEMB has no "PMCurve" option here (beams have
    no P-M interaction diagram), but adds DETAIL_POSITIONS instead.
    """

    REPORT_TYPE: str  # Report Table Type: "MEMB"/"PROP", required
    CURRENT_MODE_MEMB: str  # Output mode for REPORT_TYPE="MEMB": "Graphic"/"Detail"/"Summary", conditionally required (MEMB)
    CURRENT_MODE_PROP: str  # Output mode for REPORT_TYPE="PROP": "Graphic"/"Summary", conditionally required (PROP)
    ELEMS: NodeElemsSelector  # Element No. Input, required if not using SECTIONS (oneOf)
    SECTIONS: List[int]  # Section No. Input, required if not using ELEMS (oneOf)
    DETAIL_POSITIONS: RcReportDetailPositions  # Output positions when CURRENT_MODE_MEMB="Detail", optional
    EXPORT_PATH: str  # Directory path to save the report files, required
    OUTPUT_NAME: str  # Output file base name (multi-element runs prefix index+element no.), required


def export_beam_design_report(
    argument: RcBeamDesignReportArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #41 — BD-REPORT — RC Beam
    Design Report. Response: ``{"SUCCESS": bool, "FILE_PATH": str,
    "MESSAGE": str}``."""
    return _post(f"{_BASE}/BD-REPORT", argument, client)


# --- 42. DESIGN/RC/KDS-41-20-2022/CD-ANAL — RC Column Design Perform -------


def perform_column_design(
    argument: RcMemberDesignPerformArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #42 — CD-ANAL — RC Column
    Design Perform. Response: ``{"message": "success"}``."""
    return _post(f"{_BASE}/CD-ANAL", argument, client)


# --- 43. DESIGN/RC/KDS-41-20-2022/CD-TABLE — RC Column Design Table --------


def get_column_design_table(
    argument: RcMemberDesignTableArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #43 — CD-TABLE — RC Column
    Design Table. Includes P-M interaction and shear check results. Response:
    ``{table_name_or_"Result Table": {"FORCE": ..., "DIST": ..., "HEAD":
    [...32 columns...], "DATA": [[...], ...]}}``."""
    return _post(f"{_BASE}/CD-TABLE", argument, client)


# --- 44. DESIGN/RC/KDS-41-20-2022/CD-REPORT — RC Column Design Report ------


def export_column_design_report(
    argument: RcColumnBraceDesignReportArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #44 — CD-REPORT — RC Column
    Design Report. Response: ``{"SUCCESS": bool, "FILE_PATH": str,
    "MESSAGE": str}``."""
    return _post(f"{_BASE}/CD-REPORT", argument, client)


# --- 45. DESIGN/RC/KDS-41-20-2022/BRD-ANAL — RC Brace Design Perform -------


def perform_brace_design(
    argument: RcMemberDesignPerformArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #45 — BRD-ANAL — RC Brace
    Design Perform. Response: ``{"message": "success"}``."""
    return _post(f"{_BASE}/BRD-ANAL", argument, client)


# --- 46. DESIGN/RC/KDS-41-20-2022/BRD-TABLE — RC Brace Design Table --------


def get_brace_design_table(
    argument: RcMemberDesignTableArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #46 — BRD-TABLE — RC Brace
    Design Table. Includes P-M interaction and shear check results. Response:
    ``{table_name_or_"Result Table": {"FORCE": ..., "DIST": ..., "HEAD":
    [...28 columns...], "DATA": [[...], ...]}}``."""
    return _post(f"{_BASE}/BRD-TABLE", argument, client)


# --- 47. DESIGN/RC/KDS-41-20-2022/BRD-REPORT — RC Brace Design Report ------


def export_brace_design_report(
    argument: RcColumnBraceDesignReportArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #47 — BRD-REPORT — RC Brace
    Design Report. Response: ``{"SUCCESS": bool, "FILE_PATH": str,
    "MESSAGE": str}``."""
    return _post(f"{_BASE}/BRD-REPORT", argument, client)


# === Wall shapes (#48-50) — selected by WALL_IDS+STORY, not ELEMS/SECTIONS ===


class RcWallIdsSelector(TypedDict, total=False):
    """Wall's "WALL_IDS" — unlike post/base.py's NodeElemsSelector, this has
    only KEYS/TO (no STRUCTURE_GROUP_NAME option), per #48/#49/#50's schemas.
    Identical shape to WC-ANAL/WC-TABLE/WC-REPORT's own "WALL_IDS"
    (#63/#64/#65, see checks.py, which imports this class rather than
    redeclaring it)."""

    KEYS: List[int]  # Wall IDs specified individually, e.g. [1, 2, 3]
    TO: str  # Wall ID range, e.g. "10to20"


class RcWallDesignSelection(TypedDict, total=False):
    """One entry of "SELECTIONS" — a Wall ID set paired with target stories.
    Identical shape to WC-*'s own "SELECTIONS" entry (see checks.py)."""

    WALL_IDS: RcWallIdsSelector  # Wall ID Input (KEYS or TO), required
    STORY: List[str]  # Target story names, e.g. ["B1F", "1F"], required


# --- 48. DESIGN/RC/KDS-41-20-2022/WD-ANAL — RC Wall Design Perform ---------


class RcWallDesignPerformArgument(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #48 — WD-ANAL Argument.

    SELECTIONS is documented as required in the Parameters table, though
    the JSON Schema itself omits a top-level "required" array for
    Argument — followed here per the Parameters table and every worked
    example.
    """

    SELECTIONS: List[RcWallDesignSelection]  # Wall ID + Story combinations to design, required


def perform_wall_design(
    argument: RcWallDesignPerformArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #48 — WD-ANAL — RC Wall
    Design Perform. Walls are selected by WALL_IDS+STORY pairs rather than
    ELEMS/SECTIONS. Response: ``{"message": "success"}``.

    ⚠️ CONFIRMED to hang on **Gen NX 2026 (v2.1), build 06/23/2026**, same as
    ``perform_column_check`` (CC-ANAL) / ``perform_beam_check`` (BC-ANAL):
    the call timed out with no HTTP response even though the app UI looked
    completely normal (no visible stuck dialog). **Note this is despite the
    sibling ``perform_wall_check`` (WC-ANAL) NOT reproducing the stall** —
    so "WID+STORY-targeted = safe" is not a valid rule; this design-perform
    function hung while the check-perform function for the same wall did
    not.

    The 2026-07-25 round in which CC-ANAL/BC-ANAL ran clean covered the
    *check* endpoints only — **this design-perform endpoint was not among
    them** — and it ran on the same build that hung, so it identified no
    fix, only that the stall isn't always triggered. Keep the confirmed
    workaround: ``get_wall_design_table`` for
    the same wall/story returned full, real design results (rebar, ratios,
    ``CHK: "OK"``) immediately after this call timed out, so read it back
    regardless rather than retrying this function. See
    docs/live_verification_notes.md.
    """
    return _post(f"{_BASE}/WD-ANAL", argument, client)


# --- 49. DESIGN/RC/KDS-41-20-2022/WD-TABLE — RC Wall Design Table ----------


class RcWallDesignTableArgument(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #49 — WD-TABLE Argument.

    No EXPORT_PATH field (unlike the Beam/Column/Brace/Haunched-Beam
    tables) — genuinely absent from this endpoint's schema and Parameters
    table.
    """

    TABLE_TYPE: str  # Result Table Type: "WID+STORY"=wall+story-based/"WID"=wall-based, required
    SELECTIONS: List[RcWallDesignSelection]  # Wall ID + Story combinations to filter by, optional
    PRI_SORT: int  # Primary sort, default 1, optional
    RESULT: int  # Filter by check status: All=0/OK=1/NG=2, default 0, optional
    TABLE_NAME: str  # Response Table Title, optional
    UNIT: TableUnit  # Response Unit Setting (FORCE/DIST/HEAT/TEMP), optional
    STYLES: TableStyles  # Response Number Format (FORMAT/PLACE), optional
    COMPONENTS: List[str]  # Result table components: "WID"/"Story"/"Wall Mark"/"Pu"/"Rat-Py"/"Rat-Pz"/"Mcy"/"Mcz"/"Rat-My"/"Rat-Mz"/"Vu"/"Rat-V"/"CHK", optional


def get_wall_design_table(
    argument: RcWallDesignTableArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #49 — WD-TABLE — RC Wall
    Design Table. Unlike the other member types' tables, the response is
    documented as NOT a HEAD/DATA array pair — it's ``{"status": ...,
    "message": ..., "data": {"COMPONENTS": [...column names...], "ROWS":
    [{col: val, ...}, ...], "TOTAL_COUNT": int, ...}}``.

    ⚠️ Live-tested: the actual response observed live did NOT match the
    manual's documented shape above — it came back as the same
    ``{"Result Table": {"FORCE": ..., "DIST": ..., "HEAD": [...], "DATA":
    [[...], ...]}}`` HEAD/DATA shape used by every other member-check
    table in this file (``CC-TABLE``/``BC-TABLE``/``WC-TABLE``). Treat the
    docstring's documented shape as unconfirmed and prefer handling
    whichever shape actually comes back. See
    docs/live_verification_notes.md.

    ⚠️ Live-tested workaround: if ``perform_wall_design`` (WD-ANAL) times
    out, call this afterward before assuming the design failed — it
    returned full real results immediately after a "hung" WD-ANAL call in
    testing.
    """
    return _post(f"{_BASE}/WD-TABLE", argument, client)


# --- 50. DESIGN/RC/KDS-41-20-2022/WD-REPORT — RC Wall Design Report --------


class RcWallDesignReportArgument(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #50 — WD-REPORT Argument."""

    REPORT_TYPE: str  # Report Table Type: "WID+STORY"/"WID", required
    CURRENT_MODE_WID_STORY: str  # Output mode for REPORT_TYPE="WID+STORY": "Graphic"/"Detail"/"Summary"/"PMCurve", conditionally required
    CURRENT_MODE_WID: str  # Output mode for REPORT_TYPE="WID": same enum as CURRENT_MODE_WID_STORY, conditionally required
    SELECTIONS: List[RcWallDesignSelection]  # Wall ID + Story combinations to report, required
    EXPORT_PATH: str  # Directory path to save the report files, required
    OUTPUT_NAME: str  # Output file base name, required


def export_wall_design_report(
    argument: RcWallDesignReportArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #50 — WD-REPORT — RC Wall
    Design Report. Response: ``{"SUCCESS": bool, "FILE_PATH": str,
    "MESSAGE": str}``."""
    return _post(f"{_BASE}/WD-REPORT", argument, client)


# === Haunched Beam shapes (#51-53) — ELEMS-only, no PERFORM_TYPE/TABLE_TYPE/REPORT_TYPE ===


# --- 51. DESIGN/RC/KDS-41-20-2022/HCD-ANAL — RC Haunched Beam Design Perform ---


class RcHaunchedBeamDesignPerformArgument(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #51 — HCD-ANAL Argument.

    Unlike BD/CD/BRD-ANAL, there is no PERFORM_TYPE selector and no
    SECTIONS option — ELEMS is the only (optional) scope selector; omitting
    it presumably designs all haunched-beam elements. ELEMS reuses
    post/base.py's NodeElemsSelector.
    """

    ELEMS: NodeElemsSelector  # Haunched Beam Element No. Input, optional


def perform_haunched_beam_design(
    argument: RcHaunchedBeamDesignPerformArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #51 — HCD-ANAL — RC Haunched
    Beam Design Perform. Response: ``{"message": "success"}``."""
    return _post(f"{_BASE}/HCD-ANAL", argument, client)


# --- 52. DESIGN/RC/KDS-41-20-2022/HCD-TABLE — RC Haunched Beam Design Table ---


class RcHaunchedBeamDesignTableArgument(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #52 — HCD-TABLE Argument.

    No TABLE_TYPE/PRI_SORT/SECTIONS (unlike BD/CD/BRD-TABLE) — haunched
    beams have only one table shape, filterable by ELEMS and RESULT.
    """

    ELEMS: NodeElemsSelector  # Haunched Beam Element No. Input, optional
    RESULT: int  # Filter by check status: All=0/OK=1/NG=2, default 0, optional
    TABLE_NAME: str  # Response Table Title, optional
    EXPORT_PATH: str  # Result Table Save Path, optional
    UNIT: TableUnit  # Response Unit Setting (FORCE/DIST/HEAT/TEMP), optional
    STYLES: TableStyles  # Response Number Format (FORMAT/PLACE), optional
    COMPONENTS: List[str]  # Result table components: "HCBM"/"Section"/"Bc-I"/"Hc-I"/"Bc-J"/"Hc-J"/"POS"/"N(-)Mu"/"LCB_NegMu"/"AsTop"/"Rebar_Top"/"P(+)Mu"/"LCB_PosMu"/"AsBot"/"Rebar_Bot"/"Vu"/"LCB_Vu"/"AsV"/"Stirrup"/"CHK", optional


def get_haunched_beam_design_table(
    argument: RcHaunchedBeamDesignTableArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #52 — HCD-TABLE — RC Haunched
    Beam Design Table. Multiple rows per element (one per haunch
    section/POS). Response: ``{table_name_or_"Result Table": {"FORCE": ...,
    "DIST": ..., "HEAD": [...20 columns...], "DATA": [[...], ...]}}``."""
    return _post(f"{_BASE}/HCD-TABLE", argument, client)


# --- 53. DESIGN/RC/KDS-41-20-2022/HCD-REPORT — RC Haunched Beam Design Report ---


class RcHaunchedBeamDesignReportArgument(TypedDict, total=False):
    """docs/manual/26_Design_RC_KDS41202022.md #53 — HCD-REPORT Argument.

    No REPORT_TYPE/CURRENT_MODE_MEMB/CURRENT_MODE_PROP split (unlike the
    other member types' reports) — just a single fixed CURRENT_MODE
    ("Graphic" only; no Detail/Summary/PMCurve for haunched beams).
    """

    CURRENT_MODE: str  # Output mode, fixed "Graphic"=JPG image, required
    ELEMS: NodeElemsSelector  # Haunched Beam Element No. Input, optional
    EXPORT_PATH: str  # Directory path to save the report files, required
    OUTPUT_NAME: str  # Output file base name, required


def export_haunched_beam_design_report(
    argument: RcHaunchedBeamDesignReportArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/26_Design_RC_KDS41202022.md #53 — HCD-REPORT — RC
    Haunched Beam Design Report. Response: ``{"SUCCESS": bool, "FILE_PATH":
    str, "MESSAGE": str}``."""
    return _post(f"{_BASE}/HCD-REPORT", argument, client)
