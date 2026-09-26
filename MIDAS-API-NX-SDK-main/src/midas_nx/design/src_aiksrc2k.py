"""Source: docs/manual/27_Design_SRC_AIKSRC2K.md, items 1-27.

SRC (Steel Reinforced Concrete composite member) design code AIK-SRC2K —
setup, per-member design parameters, check-execution/result-table/report
endpoints, optimal design, material/section overrides. Endpoint prefix:
``/DESIGN/SRC/AIK-SRC2K/<CODE>`` (not ``/db/*``).

The manual documents 3 method patterns and 4 endpoint groups (mirrors
``design/steel_kds.py``'s own grouping, since SRC members reuse the same
generic per-member design-parameter concepts as steel design, just under
the AIK-SRC2K code):

1. Config-singleton (그룹 1, items 1-5) — no POST; PUT sets/updates the one
   record. ``DSRC`` is PUT/DELETE-only (``PUT_DELETE_METHODS``, unique to
   this chapter — no GET); ``DCO``/``DCTL``/``LLRF`` are GET/PUT/DELETE
   (``GET_PUT_DELETE_METHODS``); ``LCTB`` is GET/DELETE-only
   (``GET_DELETE_METHODS``).
2. Member-CRUD (그룹 1 items 6-14) — full POST/GET/PUT/DELETE, ID-keyed by
   element/member (the ``DbResource`` default).
3. POST-action (그룹 2, items 15-23) — check-execution/result-table/report/
   optimal-design endpoints; POST only, ``"Argument"``-wrapped (not ID-keyed
   ``"Assign"``), implemented as plain functions via ``post_argument``
   (mirrors ``design/steel_kds.py``'s Group 4 and ``design/rc_kds/checks.py``).
   Items 22/23 (SRC Beam/Column Design Forces) share one physical URI,
   ``DESIGN/SRC/AIK-SRC2K/TABLE``, distinguished only by ``TABLE_TYPE`` —
   implemented as a private ``_get_src_design_forces_table`` helper plus two
   thin public wrappers (mirrors ``design/rc_kds/design_forces.py``'s
   ``_get_rc_design_forces_table`` pattern).
4. Material/section-CRUD (그룹 3, items 24-27) — ``MATD``/``MEMB`` are
   GET/PUT/DELETE (``GET_PUT_DELETE_METHODS``); ``MCRD``/``MRBD`` are full
   POST/GET/PUT/DELETE (the ``DbResource`` default).
"""
from __future__ import annotations

from typing import List, Optional, TypedDict

from ..client import MidasClient
from ..client import post_argument as _post
from ..db.base import (
    GEN_ONLY,
    GET_DELETE_METHODS,
    GET_PUT_DELETE_METHODS,
    PUT_DELETE_METHODS,
    DbResource,
)
from ..post.base import NodeElemsSelector, TableStyles, TableUnit

_BASE = "/DESIGN/SRC/AIK-SRC2K"


# === Group 1: 설계 코드·일반 설정 (config-singleton / member-CRUD, items 1-14) ===

# --- 1. DESIGN/SRC/AIK-SRC2K/DSRC — SRC Design Code -------------------------


class SrcDesignCodePayload(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #1 — DSRC Specifications table.

    PUT/DELETE only — unlike every other config-singleton in this chapter,
    DSRC has no GET (confirmed by its own "### Active Methods" section).

    Live-tested 2026-07-31 on Civil NX (real production model): PUT then
    DELETE round-tripped cleanly, no lasting mutation. Live-tested
    2026-08-11 on Gen NX (v2.1, build 08/11/2026, blank document): PUT
    alone succeeded, echoed back cleanly, session stayed healthy — DELETE
    not re-tried this pass.
    """

    DGNCODE: str  # Design Code, fixed "AIK-SRC2K", required


class SrcDesignCode(DbResource):
    ENDPOINT = f"{_BASE}/DSRC"
    NAME = "SRC Design Code"
    METHODS = PUT_DELETE_METHODS


# --- 2. DESIGN/SRC/AIK-SRC2K/DCO — Design Code Option ------------------------


class SrcDesignCodeOptionPayload(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #2 — DCO Specifications table.

    Response is nested under top-level key "SRCDCO" (not "DCO") per the
    manual's own worked example — a manual-internal naming inconsistency
    between the Assign-side CODE ("DCO") and response key, not reproduced
    here since response parsing is left to the caller.
    """

    DGNCODE: str  # Design Code, fixed "AIK-SRC2K", default "AIK-SRC2K", required
    SEISMIC: bool  # Whether seismic design is applied, default true, required


class SrcDesignCodeOption(DbResource):
    ENDPOINT = f"{_BASE}/DCO"
    NAME = "Design Code Option"
    METHODS = GET_PUT_DELETE_METHODS


# --- 3. DESIGN/SRC/AIK-SRC2K/DCTL — Definition of Frame ----------------------


class SrcDefinitionOfFramePayload(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #3 — DCTL Specifications table.

    Identical field set to design/steel_kds.py's DefinitionOfFramePayload
    (#2) — not imported from there since design chapters are kept
    self-contained (each is its own single-file module, per this repo's
    existing steel_kds.py/rc_kds/* precedent).
    """

    FRAMEX: str  # X-Direction of Frame: "Unbraced Sway"/"Braced Non-sway", default "Braced Non-sway", optional
    FRAMEY: str  # Y-Direction of Frame: "Unbraced Sway"/"Braced Non-sway", default "Braced Non-sway", optional
    bAUTOKF: bool  # Auto Calculate Effective Length Factor, default false, optional
    DT: str  # Design Type: "3D"/"XZ"/"YZ"/"XY", default "3D", optional


class SrcDefinitionOfFrame(DbResource):
    ENDPOINT = f"{_BASE}/DCTL"
    NAME = "Definition of Frame"
    METHODS = GET_PUT_DELETE_METHODS


# --- 4. DESIGN/SRC/AIK-SRC2K/LLRF — Live Load Reduction Factor ---------------


class SrcLiveLoadReductionDataItem(TypedDict, total=False):
    """LLRF's "REDUCTION_DATA" array entry."""

    STORY: str  # Story Name, required
    XMIN: float  # X Min coordinate, default 0, optional
    XMAX: float  # X Max coordinate, default 0, optional
    YMIN: float  # Y Min coordinate, default 0, optional
    YMAX: float  # Y Max coordinate, default 0, optional
    RANGE_MAX: float  # Range Max value (General Design Code only): one of 1/0.95/0.9/0.85/0.8/0.75/0.7/0.65/0.6/0.55/0.5, default 1, optional
    RANGE_MIN: float  # Range Min value (General Design Code only): same enum as RANGE_MAX, default 0.5, optional


class SrcLiveLoadReductionFactorPayload(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #4 — LLRF Specifications table."""

    CALC_RULE: int  # Calc Rule: by General Design Code=0/by Chinese Standard=1, default 0, optional
    APPLIED_COMP: List[str]  # Applied Components: "ALL"/"AXIAL"/"MOMENTS"/"SHEAR", default ["AXIAL"], optional
    LIVE_LOAD_CASES: List[str]  # Live Load Case Names (user defined list), optional
    REDUCTION_DATA: List[SrcLiveLoadReductionDataItem]  # Live Load Reduction Factor Table Data, required


class SrcLiveLoadReductionFactor(DbResource):
    ENDPOINT = f"{_BASE}/LLRF"
    NAME = "Live Load Reduction Factor"
    METHODS = GET_PUT_DELETE_METHODS


# --- 5. DESIGN/SRC/AIK-SRC2K/LCTB — Load Contribution for Nonlinear Load Case ---


class SrcLoadContributionBaseItem(TypedDict, total=False):
    """LCTB's "BASE_ITEM" array entry."""

    FACTOR: float  # Factor, required
    LOAD_CASE_NAME: str  # Load Case Name, required


class SrcLoadContributionForNonlinearLoadCasePayload(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #5 — LCTB Specifications table.

    GET/DELETE only (derived info; documented here for response-shape parity
    with the rest of this chapter).
    """

    NAME: str  # Load Contribution Name, required
    DESC: str  # Description, default "", optional
    BASE_ITEM: List[SrcLoadContributionBaseItem]  # Load Contribution Items, required


class SrcLoadContributionForNonlinearLoadCase(DbResource):
    ENDPOINT = f"{_BASE}/LCTB"
    NAME = "Load Contribution for Nonlinear Load Case"
    METHODS = GET_DELETE_METHODS


# --- 6. DESIGN/SRC/AIK-SRC2K/LENG — Unbraced Length (L, Lb) ------------------


class SrcUnbracedLengthPayload(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #6 — LENG Specifications table."""

    LY: float  # Unbraced Length Ly, default 0, optional
    LZ: float  # Unbraced Length Lz, default 0, optional
    LB: float  # Laterally Unbraced Length, default 0, optional
    bNOTUSE: bool  # Do not consider of laterally unbraced length, default false, optional
    LT: float  # Torsional Unbraced Length, default 0, optional


class SrcUnbracedLength(DbResource):
    ENDPOINT = f"{_BASE}/LENG"
    NAME = "Unbraced Length (L, Lb)"


# --- 7. DESIGN/SRC/AIK-SRC2K/KFAC — Effective Length Factor (K) -------------


class SrcEffectiveLengthFactorPayload(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #7 — KFAC Specifications table."""

    Ky: float  # Effective Length Factor Ky, default 1, optional
    Kz: float  # Effective Length Factor Kz, default 1, optional
    Kt: float  # Effective Length Factor Kt, default 1, optional


class SrcEffectiveLengthFactor(DbResource):
    ENDPOINT = f"{_BASE}/KFAC"
    NAME = "Effective Length Factor (K)"


# --- 8. DESIGN/SRC/AIK-SRC2K/LTSR — Limiting Slenderness Ratio --------------


class SrcLimitingSlendernessRatioPayload(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #8 — LTSR Specifications table."""

    bNOTCHECK: bool  # Do not check for Slenderness Ratio, default false, optional
    COMP: float  # Limiting Slenderness Ratio for Compression, required
    TENS: float  # Limiting Slenderness Ratio for Tension, required


class SrcLimitingSlendernessRatio(DbResource):
    ENDPOINT = f"{_BASE}/LTSR"
    NAME = "Limiting Slenderness Ratio"


# --- 9. DESIGN/SRC/AIK-SRC2K/CMFT — Equivalent Moment Correction Factor (Cm) ---


class SrcEquivalentMomentCorrectionFactorPayload(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #9 — CMFT Specifications table."""

    OPT_AUTO: bool  # Auto Calculate, default false, optional
    CMY: float  # CMy, default 0, optional
    CMZ: float  # CMz, default 0, optional


class SrcEquivalentMomentCorrectionFactor(DbResource):
    ENDPOINT = f"{_BASE}/CMFT"
    NAME = "Equivalent Moment Correction Factor(Cm)"


# --- 10. DESIGN/SRC/AIK-SRC2K/FMAG — Moment Magnifier (B1/δb, B2/δs) --------


class SrcMomentMagnifierPayload(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #10 — FMAG Specifications table."""

    B1Y_DELTA_BY: float  # B1y - Delta by (First Order Moment Y), default 1, optional
    B1Z_DELTA_BZ: float  # B1z - Delta bz (First Order Moment Z), default 1, optional
    B2Y_DELTA_SY: float  # B2y - Delta sy (Second Order Moment Y), default 1, optional
    B2Z_DELTA_SZ: float  # B2z - Delta sz (Second Order Moment Z), default 1, optional


class SrcMomentMagnifier(DbResource):
    ENDPOINT = f"{_BASE}/FMAG"
    NAME = "Moment Magnifier(B1/Delta_b, B2/Delta_s)"


# --- 11. DESIGN/SRC/AIK-SRC2K/MLLR — Modify Live Load Reduction Factor ------


class SrcLiveLoadReductionComponents(TypedDict, total=False):
    """MLLR's "COMPONENTS" object."""

    AXIAL: bool  # Axial Force, default false, optional
    MOMENT: bool  # Moments, default false, optional
    SHEAR: bool  # Shear Forces, default false, optional


class SrcModifyLiveLoadReductionFactorPayload(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #11 — MLLR Specifications table."""

    FACTOR: float  # Reduction Factor, range 0.3-1.0, default 1, optional
    COMPONENTS: SrcLiveLoadReductionComponents  # Applied Components, optional


class SrcModifyLiveLoadReductionFactor(DbResource):
    ENDPOINT = f"{_BASE}/MLLR"
    NAME = "Modify Live Load Reduction Factor"


# --- 12. DESIGN/SRC/AIK-SRC2K/SUEQ — Scale up Factor for Earthquake --------


class SrcScaleUpFactorForEarthquakePayload(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #12 — SUEQ Specifications table."""

    LC_AXIAL: float  # Load Case - Axial Scale Factor, default 1, optional
    LC_MOMENT: float  # Load Case - Moment Scale Factor, default 1, optional
    LC_SHEAR: float  # Load Case - Shear Scale Factor, default 1, optional
    LCOM_AXIAL: float  # Load Combination - Axial Scale Factor, default 1, optional
    LCOM_MOMENT: float  # Load Combination - Moment Scale Factor, default 1, optional
    LCOM_SHEAR: float  # Load Combination - Shear Scale Factor, default 1, optional


class SrcScaleUpFactorForEarthquake(DbResource):
    ENDPOINT = f"{_BASE}/SUEQ"
    NAME = "Scale up Factor for Earthquake"


# --- 13. DESIGN/SRC/AIK-SRC2K/MBTP — Modify Member Type ---------------------


class SrcModifyMemberTypePayload(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #13 — MBTP Specifications table."""

    TYPE: str  # Member Type: "COLUMN"/"BEAM"/"BRACE", required


class SrcModifyMemberType(DbResource):
    ENDPOINT = f"{_BASE}/MBTP"
    NAME = "Modify Member Type"


# --- 14. DESIGN/SRC/AIK-SRC2K/EQCT — Seismic Load Combination Type ---------


class SrcSeismicLoadCombinationTypePayload(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #14 — EQCT Specifications table."""

    TYPE: str  # Assign Member Type: "Special Seismic Loads"/"Vertical Seismic Forces", required


class SrcSeismicLoadCombinationType(DbResource):
    ENDPOINT = f"{_BASE}/EQCT"
    NAME = "Seismic Load Combination Type"


# === Group 2: 검토 수행/테이블/리포트/최적설계 (POST-action, items 15-23) ===

# --- Beam/Column check triplets (items 15-20) — shared Argument shapes ------


class SrcMemberCheckPerformArgument(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #15/#18 — BC-ANAL/CC-ANAL
    Argument (identical shape across beam/column). Exactly one of ELEMS/
    SECTIONS is used when PERFORM_TYPE is "ELEMS"/"SECTIONS"; PERFORM_TYPE=
    "ALL" needs neither, though the JSON Schema's oneOf still requires one of
    ELEMS/SECTIONS to be present (followed verbatim, mirrors
    design/rc_kds/checks.py's PerformRcMemberCheckArgument precedent).
    ELEMS reuses post/base.py's NodeElemsSelector (identical KEYS/TO/
    STRUCTURE_GROUP_NAME shape).
    """

    PERFORM_TYPE: str  # Target type: "ALL"=all elements/"ELEMS"=by element no./"SECTIONS"=by section no., default "ALL", optional
    ELEMS: NodeElemsSelector  # Element No. Input, required if PERFORM_TYPE="ELEMS" (oneOf with SECTIONS)
    SECTIONS: List[int]  # Section No. Input, required if PERFORM_TYPE="SECTIONS" (oneOf with ELEMS)


class SrcMemberCheckTableArgument(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #16/#19 — BC-TABLE/CC-TABLE
    Argument (identical shape across beam/column; only TABLE_NAME's
    documented default and COMPONENTS' valid values differ — see each
    wrapper's docstring). Exactly one of ELEMS/SECTIONS is required (oneOf/
    anyOf, worded slightly differently per endpoint but functionally the
    same). ELEMS/UNIT/STYLES reuse post/base.py's NodeElemsSelector/
    TableUnit/TableStyles (identical shapes).
    """

    TABLE_TYPE: str  # Result Table Type: "MEMB"=member-based/"PROP"=section-based, required
    ELEMS: NodeElemsSelector  # Element No. Input, required if not using SECTIONS
    SECTIONS: List[int]  # Section No. Input, required if not using ELEMS
    PRI_SORT: int  # Primary sort for member-based output: SECT=0/MEMB=1, default 1, optional
    RESULT: int  # Filter by check status: All=0/OK=1/NG=2, default 0, optional
    TABLE_NAME: str  # Response Table Title, optional (default "SRC Checking Result" for BC-TABLE / "SRC Column Checking Result" for CC-TABLE)
    EXPORT_PATH: str  # Result Table Save Path, optional
    UNIT: TableUnit  # Response Unit Setting (FORCE/DIST/HEAT/TEMP), optional
    STYLES: TableStyles  # Response Number Format (FORMAT/PLACE), optional
    COMPONENTS: List[str]  # Result table components (member-type-specific; see each wrapper's docstring), optional


# --- 15. DESIGN/SRC/AIK-SRC2K/BC-ANAL — SRC Beam Check Perform --------------


def perform_src_beam_check(
    argument: SrcMemberCheckPerformArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/27_Design_SRC_AIKSRC2K.md #15 — BC-ANAL — SRC Beam Check
    Perform. Executes the SRC beam design/check calculation; results are
    stored on the model and later retrieved via BC-TABLE/BC-REPORT.
    Response: ``{"message": "success"}``.

    ⚠️ Never independently tested. The RC equivalent
    (``design.rc_kds.checks.perform_column_check``, CC-ANAL) was confirmed
    to hang Gen NX 2026 (v2.1), build 06/23/2026, then ran clean on that
    same build on 2026-07-25 — the trigger is unidentified, not fixed; see
    docs/live_verification_notes.md. Every test on both sides used the
    **KDS 41 20:2022 RC** code, so nothing is confirmed either way for this
    SRC path. Use a short timeout and read the corresponding ``*-TABLE``
    back regardless of whether this call returns.
    """
    return _post(f"{_BASE}/BC-ANAL", argument, client)


# --- 16. DESIGN/SRC/AIK-SRC2K/BC-TABLE — SRC Beam Check Table ---------------


def get_src_beam_check_table(
    argument: SrcMemberCheckTableArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/27_Design_SRC_AIKSRC2K.md #16 — BC-TABLE — SRC Beam Check
    Table. COMPONENTS accepts: "MEMB"/"SECT"/"Span"/"Section"/"Bc"/"Hc"/
    "Material"/"Fy"/"fc"/"Fyr"/"Fys"/"POS"/"CHK"/"AsTop"/"AsBot"/"N_M"/
    "LCB_N"/"N_Mrs"/"Rat_N"/"P_M"/"LCB_P"/"P_Mrs"/"Rat_P"/"V"/"LCB_V"/"Vrs"/
    "Rat_V" (27 total). Response: ``{table_name_or_"Result Table": {"FORCE":
    ..., "DIST": ..., "HEAD": [...27 columns...], "DATA": [[...], ...]}}``."""
    return _post(f"{_BASE}/BC-TABLE", argument, client)


# --- 17. DESIGN/SRC/AIK-SRC2K/BC-REPORT — SRC Beam Check Report -------------


class SrcReportDetailPositions(TypedDict, total=False):
    """BC-REPORT's "DETAIL_POSITIONS" — output positions for Detail mode,
    {END_I, MID, END_J}. Unlike CC-REPORT (#20), BC-REPORT supports Detail
    mode with these per-position toggles."""

    END_I: bool  # Include end-I position, default true, optional
    MID: bool  # Include mid-span position, default false, optional
    END_J: bool  # Include end-J position, default false, optional


class SrcBeamCheckReportArgument(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #17 — BC-REPORT Argument.

    ELEMS reuses post/base.py's NodeElemsSelector. Exactly one of ELEMS/
    SECTIONS is required (oneOf). Unlike CC-REPORT (#20), adds
    DETAIL_POSITIONS for Detail-mode output positions.
    """

    REPORT_TYPE: str  # Report Table Type: "MEMB"/"PROP", required
    CURRENT_MODE_MEMB: str  # Output mode for REPORT_TYPE="MEMB": "Graphic"=JPG/"Detail"=DOC/"Summary"=TXT, conditionally required (MEMB)
    CURRENT_MODE_PROP: str  # Output mode for REPORT_TYPE="PROP": "Graphic"/"Summary", conditionally required (PROP)
    ELEMS: NodeElemsSelector  # Element No. Input, required if not using SECTIONS (oneOf)
    SECTIONS: List[int]  # Section No. Input, required if not using ELEMS (oneOf)
    DETAIL_POSITIONS: SrcReportDetailPositions  # Output positions when CURRENT_MODE_MEMB="Detail", optional
    EXPORT_PATH: str  # Directory path to save the report files, required
    OUTPUT_NAME: str  # Output file base name (multi-element runs prefix index+element no., e.g. "001_E859_filename.jpg"), required


def export_src_beam_check_report(
    argument: SrcBeamCheckReportArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/27_Design_SRC_AIKSRC2K.md #17 — BC-REPORT — SRC Beam
    Check Report. Response: ``{"SUCCESS": bool, "FILE_PATH": str, "MESSAGE":
    str}``."""
    return _post(f"{_BASE}/BC-REPORT", argument, client)


# --- 18. DESIGN/SRC/AIK-SRC2K/CC-ANAL — SRC Column Check Perform -----------


def perform_src_column_check(
    argument: SrcMemberCheckPerformArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/27_Design_SRC_AIKSRC2K.md #18 — CC-ANAL — SRC Column
    Check Perform. Response: ``{"message": "success"}``.

    ⚠️ Never independently tested. The RC equivalent
    (``design.rc_kds.checks.perform_column_check``, CC-ANAL — same endpoint
    code, different design-code namespace) was confirmed to hang Gen NX
    2026 (v2.1), build 06/23/2026, then ran clean on that same build on
    2026-07-25 — the trigger is unidentified, not fixed; see
    docs/live_verification_notes.md. Every test on both sides used the
    **KDS 41 20:2022 RC** code, so nothing is confirmed either way for this
    SRC path. Use a short timeout and read ``get_src_column_check_table``
    back regardless of whether this call returns.
    """
    return _post(f"{_BASE}/CC-ANAL", argument, client)


# --- 19. DESIGN/SRC/AIK-SRC2K/CC-TABLE — SRC Column Check Table ------------


def get_src_column_check_table(
    argument: SrcMemberCheckTableArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/27_Design_SRC_AIKSRC2K.md #19 — CC-TABLE — SRC Column
    Check Table. COMPONENTS accepts (SSRC79-style; SEL not included):
    "CHK"/"MEMB"/"SECT"/"COM"/"SHR"/"Type"/"Rebar"/"Section"/"Material"/
    "Fys"/"Fyr"/"fc"/"Bc"/"Hc"/"LCB"/"Len"/"Ly"/"Lz"/"Ky"/"Kz"/"Cmy"/"Cmz"/
    "Pa"/"My"/"Mz"/"fa"/"fby"/"fbz"/"Fa"/"FBy"/"FBz" (31 total). Response:
    ``{table_name_or_"Result Table": {"FORCE": ..., "DIST": ..., "HEAD":
    [...31 columns...], "DATA": [[...], ...]}}``."""
    return _post(f"{_BASE}/CC-TABLE", argument, client)


# --- 20. DESIGN/SRC/AIK-SRC2K/CC-REPORT — SRC Column Check Report ----------


class SrcColumnCheckReportArgument(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #20 — CC-REPORT Argument.

    ELEMS reuses post/base.py's NodeElemsSelector. Exactly one of ELEMS/
    SECTIONS is required (oneOf). Unlike BC-REPORT (#17), there is no
    DETAIL_POSITIONS field — CC-REPORT's own JSON Schema omits it entirely.
    """

    REPORT_TYPE: str  # Report Table Type: "MEMB"/"PROP", required
    CURRENT_MODE_MEMB: str  # Output mode for REPORT_TYPE="MEMB": "Graphic"=JPG/"Detail"=DOC/"Summary"=TXT, conditionally required (MEMB)
    CURRENT_MODE_PROP: str  # Output mode for REPORT_TYPE="PROP": "Graphic"/"Summary", conditionally required (PROP)
    ELEMS: NodeElemsSelector  # Element No. Input, required if not using SECTIONS (oneOf)
    SECTIONS: List[int]  # Section No. Input, required if not using ELEMS (oneOf)
    EXPORT_PATH: str  # Directory path to save the report files, required
    OUTPUT_NAME: str  # Output file base name (multi-element runs prefix index+element no.), required


def export_src_column_check_report(
    argument: SrcColumnCheckReportArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/27_Design_SRC_AIKSRC2K.md #20 — CC-REPORT — SRC Column
    Check Report. Response: ``{"SUCCESS": bool, "FILE_PATH": str, "MESSAGE":
    str}``."""
    return _post(f"{_BASE}/CC-REPORT", argument, client)


# --- 21. DESIGN/SRC/AIK-SRC2K/OCHECK — SRC Optimal Design -------------------


class SrcOptimalDesignSectionCriteria(TypedDict, total=False):
    """OCHECK's "SECT_LIST" array entry — one section number + its design
    criteria (POST input only)."""

    SECT_NO: int  # Section Number (input), required
    SECT_DB: str  # Design Criteria - SectDB: "BUILT"=welded sections/"KS21"=Korean Standard rolled sections/"USER"=user-defined sections, required
    ALLOW: float  # Design Criteria - Allow, default 1, optional
    D1: float  # Design Criteria - D1, default 0, optional
    D2: float  # Design Criteria - D2, default 0, optional
    D3: float  # Design Criteria - D3, default 0, optional
    D4: float  # Design Criteria - D4, default 0, optional
    D5: float  # Design Criteria - D5, default 0, optional
    D6: float  # Design Criteria - D6, default 0, optional


class SrcOptimalDesignAnalysisOption(TypedDict, total=False):
    """OCHECK's "ANALYSIS_OPT" — re-analysis iteration control."""

    ANAL_TIME: int  # Number of re-analysis iterations (0-10); 0 = section selection only, no re-analysis, default 1, optional


class SrcOptimalDesignColumnDesign(TypedDict, total=False):
    """OCHECK's "COLUMN_DESIGN" — column-specific optimal design settings."""

    APPLIED_FORCES: int  # Applied forces/moments method for column design: Axial Forces and Moments=0/Axial Forces Only=1, default 0, optional
    JOINT_METHOD: int  # Joint method of built-up column splices: Internal Const (fixed inside, expand outward)=0/External Const (fixed outside, adjust inward)=1, default 1, optional


class SrcOptimalDesignUserSection(TypedDict, total=False):
    """OCHECK's "USER_DEFINED_SECT" array entry — one user-defined section
    (SHAPE + dimensions D1-D6)."""

    NO: int  # Section No., required
    SHAPE: str  # Section shape: "L"/"C"/"H"/"T"/"B"/"P"/"SR"/"SB"/"2L"/"2C", required
    D1: float  # default 0, optional
    D2: float  # default 0, optional
    D3: float  # default 0, optional
    D4: float  # default 0, optional
    D5: float  # default 0, optional
    D6: float  # default 0, optional


class SrcOptimalDesignOutput(TypedDict, total=False):
    """OCHECK's "OUTPUT" — output options for optimal design results
    (multiple selectable simultaneously)."""

    GRAPH_MAX_RATIO: bool  # Output Max. Ratio graph, default true, optional
    GRAPH_AVG_RATIO: bool  # Output Average Ratio graph, default true, optional
    GRAPH_WEIGHT: bool  # Output Weight graph, default true, optional
    GRAPH_WEIGHT_SUM: bool  # Output Weight Sum graph, default true, optional
    GRAPH_WEIGHT_RATIO: bool  # Output Weight Ratio graph, default true, optional
    TEXT_REPORT: bool  # Output results as text report to screen and file, default true, optional
    MODEL_UPDATE: bool  # Apply selected optimal sections to the model, default true, optional
    EXPORT_PATH: str  # File path to save report output, required


class SrcOptimalDesignArgument(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #21 — OCHECK Argument."""

    SECT_LIST: List[SrcOptimalDesignSectionCriteria]  # Section list & design criteria (SRC), required
    ANALYSIS_OPT: SrcOptimalDesignAnalysisOption  # Analysis option - re-analysis iterations, optional
    PLATE_THICKNESS: List[float]  # Plate thickness list for BUILT sections (max 50 entries), optional
    COLUMN_DESIGN: SrcOptimalDesignColumnDesign  # Column design settings for optimal design of column members, optional
    USER_DEFINED_SECT: List[SrcOptimalDesignUserSection]  # User-defined section database, optional
    OUTPUT: SrcOptimalDesignOutput  # Output options for optimal design results, required


def perform_src_optimal_design(
    argument: SrcOptimalDesignArgument, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/27_Design_SRC_AIKSRC2K.md #21 — OCHECK — SRC Optimal
    Design. Response: ``{"ODSR_RUN_RESPONSE": {"FORCE": ..., "DIST": ...,
    "HEAD": ["No", "Name", "SteelSize", "Astl", "COM", "Axial", "Ben-y",
    "Ben-z", "Shear"], "DATA": [[...], ...]}}``.

    🛑 UNOFFICIAL, PAUSED-DEVELOPMENT API — MIDASIT confirmed on
    2026-08-06 that this endpoint was mid-development and shelved,
    with no resume date, and moved its own path from
    ``/DESIGN/SRC/AIK-SRC2K/OCHECK`` to ``/TEMP/DESIGN/SRC/AIK-SRC2K/OCHECK``
    specifically to mark it unofficial. **The path move is not a fix**:
    confirmed live 2026-08-07 that the new ``/TEMP/`` path still reproduces
    the exact same crash as the old one, on the same request shape that
    crashed Civil NX below. Calling this is expected to crash the running
    NX session; only use it if you've accepted that risk.

    ⚠️ Confirmed a genuine crash on Civil NX (2026-07-31, real production
    bridge model with zero SRC-eligible sections/materials): the call
    itself timed out, then a same-session `GET /db/NODE` also timed out —
    a native dialog cascade had taken the whole session down, requiring a
    full Civil NX restart to recover (no data loss). Reported to MIDASIT.
    See docs/live_verification_notes.md's 2026-07-31 "New crash found"
    section for the full dialog sequence.

    ⚠️ Gen NX, 2026-08-01: tried against a session whose open document had
    **zero sections at all** (not the "sections exist but none are
    SRC-eligible" shape that crashed Civil) — a fabricated `SECT_NO` got a
    clean `"Section 1 does not exist."` JSON error, no dialog, session
    stayed alive. This is NOT equivalent to the Civil repro conditions and
    does not clear Gen of the same risk; the crash trigger needs an actual
    non-SRC-eligible section to reference, which this Gen session's model
    didn't have.

    ⚠️ Gen NX, 2026-08-07: re-tested on the new ``/TEMP/`` path against a
    session whose open document has real, non-SRC-eligible sections
    (matching the Civil repro conditions this time) — crashed the same
    way (timeout, then session unresponsive, full restart needed).

    Gen NX and Civil NX, 2026-08-11 (v2.1/v2.2, build 08/11/2026): both
    re-tested against a document with **zero sections** (same shape as
    the 2026-08-01 Gen non-repro above, not the real non-SRC-eligible-
    section shape that actually triggers the crash) — both got the same
    clean ``"Section 1 does not exist."`` error, session stayed healthy
    both times. Reconfirms the precondition finding rather than adding
    new evidence either way; the crash risk on real models with real
    sections stands as documented above.

    ⚠️ Civil NX, 2026-08-13 (v2.2, build 08/12/2026): re-tested with the
    actual trigger shape restored — a dummy model built specifically for
    this test (C24 concrete material, 600×600 ``DBUSER`` section: real,
    existing, and non-SRC-eligible) — and it crashed again, identical
    signature (client-side timeout, then a same-session ``GET /db/NODE``
    returning ``404 client does not exist``, "Failed to disconnect the
    work session" dialog confirmed on screen). Recovered cleanly via the
    dialog's own instructions, no data of value lost (the dummy model was
    disposable). Confirms the crash is not build-dependent — this is not
    a "sometimes" defect like ``NMAS`` briefly was; it reproduces
    reliably given the right precondition, consistent with MIDASIT's
    "not a defect, no fix timeline" stance.
    """
    return _post(f"/TEMP{_BASE}/OCHECK", argument, client)


# === Beam/Column Design Forces (items 22-23) — shared URI "TABLE" ==========

#: 22. SRC Beam Design Forces TABLE_TYPE value.
TABLE_TYPE_BEAM_DESIGN_FORCES = "SRCBEAMDESIGNFORCES"

#: 23. SRC Column Design Forces TABLE_TYPE value.
TABLE_TYPE_COLUMN_DESIGN_FORCES = "SRCCOLUMNDESIGNFORCES"


class SrcDesignForcesArgument(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #22/#23 — TABLE Argument.

    Both items share one physical URI, ``DESIGN/SRC/AIK-SRC2K/TABLE``,
    distinguished only by TABLE_TYPE (confirmed by the manual's own note at
    the top of this chapter and by lines 4441/4780 of the source manual).
    COMPONENTS' valid values differ per TABLE_TYPE: Beam uses "Memb"/"Part"/
    "LComName"/"Type"/"Fz"/"Mx"/"My(+)"/"My(-)" (8 values); Column uses
    "Memb"/"Part"/"LComName"/"Type"/"Fx"/"Fy"/"Fz"/"Mx"/"My"/"Mz" (10
    values). NODE_ELEMS/UNIT/STYLES reuse post/base.py's NodeElemsSelector/
    TableUnit/TableStyles (identical shapes).
    """

    TABLE_NAME: str  # Response Table Title, default "", optional
    TABLE_TYPE: str  # Result Table Type, fixed TABLE_TYPE_BEAM_DESIGN_FORCES or TABLE_TYPE_COLUMN_DESIGN_FORCES, required
    EXPORT_PATH: str  # Result Table Save Path, optional
    UNIT: TableUnit  # Response Unit Setting (FORCE/DIST/HEAT/TEMP), default "System", optional
    STYLES: TableStyles  # Response Number Format (FORMAT/PLACE), default "System", optional
    COMPONENTS: List[str]  # Result table components (TABLE_TYPE-specific; see class docstring), optional
    NODE_ELEMS: NodeElemsSelector  # Node/Element No. Input, optional
    PARTS: List[str]  # Element Part Number: "PartI"/"Part1/4"/"Part2/4"/"Part3/4"/"PartJ", default ["All"], optional


def _get_src_design_forces_table(
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
    argument: SrcDesignForcesArgument = {"TABLE_NAME": table_name, "TABLE_TYPE": table_type}
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


# --- 22. DESIGN/SRC/AIK-SRC2K/TABLE — SRC Beam Design Forces ----------------


def get_src_beam_design_forces_table(
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
    """docs/manual/27_Design_SRC_AIKSRC2K.md #22 — TABLE — SRC Beam Design
    Forces. Shares the ``DESIGN/SRC/AIK-SRC2K/TABLE`` URI with #23 (SRC
    Column Design Forces), distinguished by TABLE_TYPE. Response:
    ``{table_name_or_"empty": {"FORCE": ..., "DIST": ..., "HEAD": ["Index",
    "Memb", "Part", "LComName", "Type", "Fz", "Mx", "My(+)", "My(-)"],
    "DATA": [[...], ...]}}``.

    Shares the ``TABLE_TYPE``-crash pattern seen across the wider
    Design-Forces family — presumed at risk on
    Gen until independently confirmed on real data. Re-tested 2026-08-11
    on Gen NX (v2.1, build 08/11/2026), blank ``/doc/NEW`` document: clean
    empty response, no crash, session stayed healthy. A single clean pass
    is not independent proof the risk is gone — treat as
    reduced-but-not-cleared until a real-model retest.
    """
    return _get_src_design_forces_table(
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


# --- 23. DESIGN/SRC/AIK-SRC2K/TABLE — SRC Column Design Forces --------------


def get_src_column_design_forces_table(
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
    """docs/manual/27_Design_SRC_AIKSRC2K.md #23 — TABLE — SRC Column Design
    Forces. Shares the ``DESIGN/SRC/AIK-SRC2K/TABLE`` URI with #22 (SRC Beam
    Design Forces), distinguished by TABLE_TYPE. Response:
    ``{table_name_or_"empty": {"FORCE": ..., "DIST": ..., "HEAD": ["Index",
    "Memb", "Part", "LComName", "Type", "Fx", "Fy", "Fz", "Mx", "My", "Mz"],
    "DATA": [[...], ...]}}``.

    Shares the ``TABLE_TYPE``-crash pattern seen across the wider
    Design-Forces family — presumed at risk on
    Gen until independently confirmed on real data. Re-tested 2026-08-11
    on Gen NX (v2.1, build 08/11/2026), blank ``/doc/NEW`` document: clean
    empty response, no crash, session stayed healthy. A single clean pass
    is not independent proof the risk is gone — treat as
    reduced-but-not-cleared until a real-model retest.
    """
    return _get_src_design_forces_table(
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


# === Group 3: 재료·단면·부재 (items 24-27) ===

# --- 24. DESIGN/SRC/AIK-SRC2K/MATD — SRC Modify Material --------------------


class SrcMaterialSteel(TypedDict, total=False):
    """MATD's "STEEL" — steel material selection. Full KS22(S) GRADE enum
    (68 values), transcribed from design/steel_kds.py's
    ModifySteelMaterialPayload comment (same standard code; not imported
    since design chapters are kept self-contained per this repo's
    precedent):
      SS235, SS275, SS315, SS410, SS450, SS550,
      SM275, SM355, SM420, SM460,
      SM275TMC, SM355TMC, SM420TMC, SM460TMC,
      SMA275A, SMA275B, SMA275C, SMA355A, SMA355B, SMA355C, SMA460,
      HSM500,
      SN275A, SN275B, SN275C, SN355, SN460,
      SHN275, SHN355, SHN420, SHN460,
      HSB380, HSB460, HSB690, HSA650,
      SGT275, SGT355, SGT410, SGT450, SGT550,
      SRT275, SRT355, SRT410, SRT450, SRT550,
      SNT275, SNT355, SNT460,
      SHT410, SHT460,
      SNRT295E, SNRT390E, SNRT275A, SNRT355A,
      SSC275,
      SWH275, SWH355, SWH420, SWH460,
      SF490, SF540,
      SDP1, SDP2, SDP3,
      SWPC1, SWPD1, SWPC, SWPD
    """

    CODE: str  # Steel material code type: "None"=user-defined/"Standard"=standard code, required
    STANDARD_CODE: str  # Steel standard code (CODE="Standard"); currently only "KS22(S)" is supported, conditionally required
    GRADE: str  # Steel grade (CODE="Standard"); one of the ~68 KS22(S) grades listed above, conditionally required
    NAME: str  # User-defined steel material name (CODE="None"), conditionally required
    ES: float  # Modulus of Elasticity (Es) — user input if CODE="None", auto-filled if CODE="Standard", conditionally required
    FU: float  # Tensile Strength (Fu) — user input if CODE="None", auto-filled if CODE="Standard", conditionally required
    FY: float  # Yield Strength (Fy), required if CODE="None"
    FY1: float  # Yield Strength (Fy1), auto-filled if CODE="Standard", optional
    FY2: float  # Yield Strength (Fy2), auto-filled if CODE="Standard", optional
    FY3: float  # Yield Strength (Fy3), auto-filled if CODE="Standard", optional
    FY4: float  # Yield Strength (Fy4), auto-filled if CODE="Standard", optional
    FY5: float  # Yield Strength (Fy5), auto-filled if CODE="Standard", optional


class SrcMaterialConcrete(TypedDict, total=False):
    """MATD's "CONCRETE" — concrete material selection. Full KS19(RC) GRADE
    enum (20 values): C15, C18, C21, C24, C27, C30, C35, C40, C45, C49, C50,
    C55, C60, C65, C70, C75, C80, C85, C90, C95 (cross-checked against
    docs/manual/26_Design_RC_KDS41202022.md, which documents the same
    KS19(RC) concrete-grade enum in full)."""

    CODE: str  # Concrete material code type: "None"/"Standard", required
    STANDARD_CODE: str  # Concrete standard code (CODE="Standard"); currently only "KS19(RC)" is supported, conditionally required
    NAME: str  # User-defined concrete material name (CODE="None"), conditionally required
    GRADE: str  # Concrete grade (CODE="Standard"); one of the 20 KS19(RC) grades listed above, conditionally required
    FC: float  # Specified Compressive Strength (fc) — user input if CODE="None", auto-filled if CODE="Standard", conditionally required


class SrcMaterialReinforcement(TypedDict, total=False):
    """MATD's "REINFORCEMENT" — reinforcement material selection.
    MAIN_REBAR_GRADE/SUB_REBAR_GRADE share the 8-value KS19(RC) rebar grade
    enum: SD300, SD400, SD500, SD600, SD700, SD400S, SD500S, SD600S."""

    CODE: str  # Reinforcement code type: "None"/"Standard", required
    STANDARD_CODE: str  # Reinforcement standard code (CODE="Standard"); currently only "KS19(RC)" is supported, conditionally required
    MAIN_REBAR_NAME: str  # User-defined main rebar name (CODE="None"), conditionally required
    MAIN_REBAR_GRADE: str  # Main rebar grade (CODE="Standard"); see the 8-value enum above, conditionally required
    FYR: float  # Yield Strength of main rebar — user input if CODE="None", auto-filled if CODE="Standard", conditionally required
    SUB_REBAR_NAME: str  # User-defined sub-rebar name (CODE="None"), conditionally required
    SUB_REBAR_GRADE: str  # Sub-rebar grade (CODE="Standard"); see the 8-value enum above, conditionally required
    FYS: float  # Yield Strength of sub-rebar — user input if CODE="None", auto-filled if CODE="Standard", conditionally required


class SrcModifyMaterialPayload(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #24 — MATD Specifications table.

    Unlike most /Assign-keyed endpoints in this repo, all three of STEEL/
    CONCRETE/REINFORCEMENT are required together (not merely optional
    overrides) — reflects the manual's own top-level "required" array for
    this endpoint's per-ID object.
    """

    STEEL: SrcMaterialSteel  # Steel material selection, required
    CONCRETE: SrcMaterialConcrete  # Concrete material selection, required
    REINFORCEMENT: SrcMaterialReinforcement  # Reinforcement material selection, required


class SrcModifyMaterial(DbResource):
    ENDPOINT = f"{_BASE}/MATD"
    NAME = "Modify SRC Material"
    METHODS = GET_PUT_DELETE_METHODS
    #: Gen-only: 404 (route + /info) on Civil NX, confirmed independently
    #: twice on 2026-07-29 — see db/base.py's GEN_ONLY docstring.
    PRODUCTS = GEN_ONLY


# --- 25. DESIGN/SRC/AIK-SRC2K/MCRD — SRC Column Section Data ----------------


class SrcColumnSectionMainBar(TypedDict, total=False):
    """MCRD's "MAIN_BAR" — main rebar layout for the SRC column's embedded-
    steel section."""

    USE_REBAR_SPACE: bool  # Auto-calculated rebar spacing, default true, optional
    REBAR_SPACE: float  # Main rebar spacing, used when USE_REBAR_SPACE=false, default 0, optional
    NUM: int  # Total number of main rebars; must be a multiple of 4, minimum 4, required
    NAME: str  # Main rebar size, D4~D57 (19 total), required
    ROW: int  # Number of rebar rows for rectangular section; must be a multiple of 2, minimum 2, required
    DO: float  # Concrete cover / center distance d0, minimum 0, required


class SrcColumnSectionShearBar(TypedDict, total=False):
    """MCRD's "SHEAR_BAR" — hoop/tie rebar for the SRC column section."""

    NAME: str  # Hoop/tie rebar size, D4~D57 (19 total), required
    DIST: float  # Hoop/tie rebar spacing, exclusiveMinimum 0, required


class SrcColumnSectionDataPayload(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #25 — MCRD Specifications table."""

    MAIN_BAR: SrcColumnSectionMainBar  # Main rebar data, required
    SHEAR_BAR: SrcColumnSectionShearBar  # Hoop/tie rebar data, required


class SrcColumnSectionData(DbResource):
    ENDPOINT = f"{_BASE}/MCRD"
    NAME = "Modify SRC Column Section Data"


# --- 26. DESIGN/SRC/AIK-SRC2K/MEMB — Member Assignment ----------------------


class SrcMemberAssignmentPayload(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #26 — MEMB Specifications table."""

    AELEM: List[int]  # Element Lists, required
    bREVERSE: bool  # Reverse Local Direction, default false, optional


class SrcMemberAssignment(DbResource):
    ENDPOINT = f"{_BASE}/MEMB"
    NAME = "Member Assignment"
    METHODS = GET_PUT_DELETE_METHODS


# --- 27. DESIGN/SRC/AIK-SRC2K/MRBD — SRC Beam Section Data ------------------


class SrcBeamRebarLayer(TypedDict, total=False):
    """MRBD's TOP/BOT "LAYER1"/"LAYER2" — one rebar layer entry."""

    NAME: str  # Rebar size for this layer, D4~D57 (19 total), required
    NUM: int  # Number of rebars in this layer, minimum 1, required


class SrcBeamRebarFace(TypedDict, total=False):
    """MRBD's "TOP"/"BOT" — rebar layers at one beam face (up to 2 layers)."""

    LAYER1: SrcBeamRebarLayer  # First layer, required
    LAYER2: SrcBeamRebarLayer  # Second layer, optional


class SrcBeamBarSector(TypedDict, total=False):
    """MRBD's "BAR_SECTOR_I"/"BAR_SECTOR_M"/"BAR_SECTOR_J" — rebar
    configuration at one beam cross-section (I/M/J = end-I/mid-span/end-J).
    All three share this identical shape; at least one of the three sectors
    is required (anyOf)."""

    TOP: SrcBeamRebarFace  # Top rebar configuration, required
    BOT: SrcBeamRebarFace  # Bottom rebar configuration, required
    STIRRUP_SPACE: float  # Stirrup spacing at this section, exclusiveMinimum 0, required
    STIRRUP_NUM: int  # Number of stirrup sets at this section, 2-20, default 2, optional


class SrcBeamSectionDataPayload(TypedDict, total=False):
    """docs/manual/27_Design_SRC_AIKSRC2K.md #27 — MRBD Specifications table.

    At least one of BAR_SECTOR_I/BAR_SECTOR_M/BAR_SECTOR_J is required
    (anyOf); DT/DB/SHEAR_BAR are always required.
    """

    BAR_SECTOR_I: SrcBeamBarSector  # Rebar configuration at I-section, conditionally required (anyOf with M/J)
    BAR_SECTOR_M: SrcBeamBarSector  # Rebar configuration at M-section, conditionally required (anyOf with I/J)
    BAR_SECTOR_J: SrcBeamBarSector  # Rebar configuration at J-section, conditionally required (anyOf with I/M)
    DT: float  # Top rebar cover thickness, exclusiveMinimum 0, required
    DB: float  # Bottom rebar cover thickness, exclusiveMinimum 0, required
    SHEAR_BAR: str  # Stirrup rebar size, D4~D57 (19 total), required


class SrcBeamSectionData(DbResource):
    ENDPOINT = f"{_BASE}/MRBD"
    #: The manual's own section label, which this used to shorten. The contract
    #: owns published names now and the drift check compares them to the label.
    NAME = "Modify SRC Beam Section Data"
