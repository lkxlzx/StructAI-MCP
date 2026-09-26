"""Source: docs/manual/21_POST_StoryTables.md, items 1-17.

All functions POST to the shared /post/TABLE endpoint — see post/base.py.

The manual declares one common Argument parameter table that applies
uniformly to all 17 story tables (TABLE_NAME, TABLE_TYPE, EXPORT_PATH, UNIT,
STYLES, COMPONENTS, NODE_ELEMS, LOAD_CASE_NAMES, OPT_CS, STAGE_STEP) rather
than documenting a per-table subset like ch18 did, so every wrapper below
exposes the full common kwarg set (mirroring get_table's own signature).

2026-07-24: the manual additionally documented per-table STORY_NAMES/MODES
fields and table-specific "ADDITIONAL" objects (angle/Beta/node-selection/
calculation-method settings) for 10 of the 17 tables — each affected
wrapper below exposes its own typed additional/story_names/modes/
set_calculation_method kwarg; see the TypedDicts declared after the
TABLE_TYPE_* constants for each table's exact shape.

⚠️ Live-tested: on a real analyzed model with valid ``load_case_names``,
these story tables can still return ``{"error": {"message": "[empty]
Cannot generate table data as there is no analysis result."}}`` even
though ``post/result_1.py``'s node/element-level tables (reaction,
displacement, beam force, ...) work fine against the same analysis. The
fix was calling ``ope.calculate_story(...)`` (``/ope/STOR``) *before*
``doc.analyze()`` — story-level aggregates (weight/stiffness centers,
eccentricity, overturning moment, etc.) appear to need that explicit
calculation step baked into the analysis run, not just derivable
after-the-fact from raw nodal results. See
docs/live_verification_notes.md for the full reproduction.
"""
from __future__ import annotations

from typing import List, Optional, TypedDict

from ..client import MidasClient
from .base import NodeElemsSelector, TableStyles, TableUnit, get_table

# 1. Story Drift
TABLE_TYPE_STORY_DRIFT_X = "STORY_DRIFT_X"
TABLE_TYPE_STORY_DRIFT_Y = "STORY_DRIFT_Y"
TABLE_TYPE_STORY_DRIFT_COMB = "STORY_DRIFT_COMB"

# 2. Story Displacement
TABLE_TYPE_STORY_DISPLACEMENT_X = "STORY_DISPLACEMENT_X"
TABLE_TYPE_STORY_DISPLACEMENT_Y = "STORY_DISPLACEMENT_Y"
TABLE_TYPE_STORY_DISPLACEMENT_COMB = "STORY_DISPLACEMENT_COMB"

# 3. Story Shear Force (R.S. Analysis)
TABLE_TYPE_STORY_SHEAR_FOR_RS = "STORY_SHEAR_FOR_RS"

# 4. Story Shear Force Coefficient (R.S. Analysis)
TABLE_TYPE_STORY_SHEAR_FORCE_COEFFICIENT = "STORY_SHEAR_FORCE_COEFFICIENT"

# 5. Story Mode Shape
TABLE_TYPE_STORY_MODE_SHAPE = "STORY_MODE_SHAPE"

# 6. Story Shear Force Ratio
TABLE_TYPE_STORY_SHEAR_FORCE_RATIO = "STORY_SHEAR_FORCE_RATIO"

# 7. Story Eccentricity
# NOTE: the API spec intentionally misspells this value — "Eccentricity"
# becomes "ECNTRICITY" (missing the second "e"). Use the string verbatim;
# it is not a transcription typo (see manual's explicit "철자 유의" callout).
TABLE_TYPE_STORY_ECCENTRICITY = "STORY_ECNTRICITY"

# 8. Overturning Moment
TABLE_TYPE_OVERTURNING_MOMENT = "OVERTURNING_MOMENT"

# 9. Story Axial Force Sum
TABLE_TYPE_STORY_AXIAL_FORCE_SUM = "STORY_AXIAL_FORCE_SUM"

# 10. Story Stability Coefficient
TABLE_TYPE_STORY_STABILITY_COEFFICIENT_X = "STORY_STABILITY_COEFFICIENT_X"
TABLE_TYPE_STORY_STABILITY_COEFFICIENT_Y = "STORY_STABILITY_COEFFICIENT_Y"

# 11. Torsional Irregularity Check
TABLE_TYPE_TORSIONAL_IRREGULARITY_X = "TORSIONAL_IRREGULARITY_X"
TABLE_TYPE_TORSIONAL_IRREGULARITY_Y = "TORSIONAL_IRREGULARITY_Y"

# 12. Torsional Amplification Factor
TABLE_TYPE_TORSIONAL_AMPLIFICATION_FACTOR_X = "TORSIONAL_AMPLIFICATION_FACTOR_X"
TABLE_TYPE_TORSIONAL_AMPLIFICATION_FACTOR_Y = "TORSIONAL_AMPLIFICATION_FACTOR_Y"

# 13. Stiffness Irregularity Check (Soft Story)
TABLE_TYPE_STIFFNESS_IRREGULARITY_X = "STIFFNESS_IRREGULARITY_X"
TABLE_TYPE_STIFFNESS_IRREGULARITY_Y = "STIFFNESS_IRREGULARITY_Y"

# 14. Capacity Irregularity Check (Weak Story)
TABLE_TYPE_CAPACITY_IRREGULARITY = "CAPACITY_IRREGULARITY"

# 15. Criteria for Regularity in Plan
TABLE_TYPE_CRITERIA_FOR_REGULARITY_IN_PLAN = "CRITERIA_FOR_REGULARITY_IN_PLAN"

# 16. Ultimate Story Shear For Check
TABLE_TYPE_ULTIMATE_STORY_SHEAR_FORCE_CHECK = "ULTIMATE_STORY_SHEAR_FORCE_CHECK"

# 17. Weight Irregularity Check
TABLE_TYPE_WEIGHT_IRREGULARITY_X = "WEIGHT_IRREGULARITY_X"
TABLE_TYPE_WEIGHT_IRREGULARITY_Y = "WEIGHT_IRREGULARITY_Y"


# --- ADDITIONAL/related sub-objects — 2026-07-24 official addition; each
# story table's ADDITIONAL shape is documented independently (no shared
# schema across table types), so each gets its own TypedDict(s) below. ---


class StoryDriftLcomEntry(TypedDict, total=False):
    """Shared {NAME, FACTOR} load-combination entry used by
    SET_STORY_DRIFT_PARAMS.LCOMS (#1) and
    SET_STABILITY_COEFFICIENT_PARAMS.LCOMS (#10)."""

    NAME: str  # Load case name, optional
    FACTOR: float  # Factor, optional


class StoryDriftBeta(TypedDict, total=False):
    """SET_STORY_DRIFT_PARAMS.BETA (#1)."""

    FIX_USER_CHECK: str  # "FIXED" (1.0 fixed, default) or "USER" (per-story input), optional
    NAME_FROM: str  # Start story name, required if FIX_USER_CHECK="USER"
    NAME_TO: str  # End story name, required if FIX_USER_CHECK="USER"
    VALUE: float  # User Beta value, default 0, required if FIX_USER_CHECK="USER"


class StoryDriftParams(TypedDict, total=False):
    """ADDITIONAL.SET_STORY_DRIFT_PARAMS (#1) — story-drift-ratio judgment
    method (Method 1: response modification factor / Method 2: deflection
    amplification factor) and its parameters."""

    RESPONSE_MOD_FACTOR_CHECK: bool  # True=Method 1, False=Method 2 (default), optional
    RESPONSE_MOD_FACTOR_VALUE: float  # Method 1 response modification factor, default 1, used only if RESPONSE_MOD_FACTOR_CHECK=true, optional
    DEFLECTION_AMPL_FACTOR_VALUE: float  # Method 2 deflection amplification factor (Cd), default 1, used only if RESPONSE_MOD_FACTOR_CHECK=false, optional
    IMPORTANCE_FACTOR_VALUE: float  # Method 2 importance factor, default 1.5, optional
    SCALE_FACTOR_VALUE: float  # Scale factor, default 1, optional
    ALLOWABLE_RATIO: float  # Allowable story drift ratio, default 0.015, optional
    LCOMS: List[StoryDriftLcomEntry]  # P-Delta vertical load combination list, optional
    BETA: StoryDriftBeta  # Beta value setting, optional


# Direction-key spelling used to be contradictory in the official docs (the
# Specifications table wrote "X_DIR"/"Y_DIR" while the request example wrote
# "X-DIR"/"Y-DIR"), and the parent field's type disagreed too (table said
# Array[Object], example showed a single object). The vendor's 2026-07-29
# correction unified both on the underscore spelling and confirmed the Object
# shape — see docs/manual/21_POST_StoryTables.md #1 in the MIDAS-API repo.
StoryDriftVerticalLineSelection = TypedDict(
    "StoryDriftVerticalLineSelection",
    {
        "X_DIR": int,
        "Y_DIR": int,
        "COMBINED": int,
    },
    total=False,
)
"""{X_DIR/Y_DIR/COMBINED: node ID} — exactly one key per the manual."""

StoryDriftVerticalLinesSelection = TypedDict(
    "StoryDriftVerticalLinesSelection",
    {
        "X_DIR": List[int],
        "Y_DIR": List[int],
        "COMBINED": List[int],
    },
    total=False,
)
"""{X_DIR/Y_DIR/COMBINED: [node IDs]} — exactly one key per the manual, e.g.
{"X_DIR": [262, 260]}."""


class StoryDriftCalculationMethod(TypedDict, total=False):
    """ADDITIONAL.SET_STORY_DRIFT_CALCULATION_METHOD (#1) — TABLE_TYPE_STORY_DRIFT_COMB
    only; selects which drift-basis column(s) are included in the response."""

    DRIFT_AT_THE_CENTER_OF_MASS: bool  # default true, optional
    AVERAGE_DRIFT_OF_VERTICAL_ELEMENTS: bool  # default false, optional
    DRIFT_OF_A_VERTICAL_LINE_ON_SELECTED_NODE: StoryDriftVerticalLineSelection  # required if this basis is used
    AVERAGE_DRIFT_OF_VERTICAL_LINES_ON_SELECTED_NODES: StoryDriftVerticalLinesSelection  # required if this basis is used
    SHEAR_WEIGHTED_AVERAGE_DRIFT_OF_VERTICAL_ELEMENTS: bool  # default false, optional


class StoryDriftAdditional(TypedDict, total=False):
    """docs/manual/21_POST_StoryTables.md #1 — Story Drift ADDITIONAL object."""

    SET_STORY_DRIFT_PARAMS: StoryDriftParams  # optional
    SET_STORY_DRIFT_CALCULATION_METHOD: StoryDriftCalculationMethod  # TABLE_TYPE_STORY_DRIFT_COMB only, optional


class StorySetAngle(TypedDict, total=False):
    """Shared ADDITIONAL.SET_ANGLE {"ANGLE": ...} object — Angle2 is always
    Angle1 + 90° server-side. Used by #6 Story Shear Force Ratio (Required),
    #8 Overturning Moment (Optional, default 0), #14 Capacity Irregularity
    Check (Required), and #16 Ultimate Story Shear Force Check (Optional,
    default 0)."""

    ANGLE: float  # Angle1 input value (deg)


class StoryShearForceRatioAdditional(TypedDict, total=False):
    """docs/manual/21_POST_StoryTables.md #6 — Story Shear Force Ratio
    ADDITIONAL object. SET_ANGLE is Required for this table."""

    SET_ANGLE: StorySetAngle  # required


class OverturningMomentParams(TypedDict, total=False):
    """ADDITIONAL.SET_OVERTURNING_MOMENT_PARAMS (#8)."""

    SF_FOR_RS: float  # Response-spectrum scale factor, default 1, optional
    DEFINE_RF: str  # Reduction-factor method: "FIXED" (1.0 fixed, default) or "AUTO", optional


class OverturningMomentAdditional(TypedDict, total=False):
    """docs/manual/21_POST_StoryTables.md #8 — Overturning Moment
    ADDITIONAL object. Both keys optional here (unlike #6's Required SET_ANGLE)."""

    SET_ANGLE: StorySetAngle  # optional, default ANGLE=0
    SET_OVERTURNING_MOMENT_PARAMS: OverturningMomentParams  # optional


class StoryStabilityBeta(TypedDict, total=False):
    """SET_STABILITY_COEFFICIENT_PARAMS.BETA (#10)."""

    FIX_USER_CHECK: str  # "FIXED" or "USER", default is server-determined ("System"), optional
    NAME_FROM: str  # Start story name, required if FIX_USER_CHECK="USER"
    NAME_TO: str  # End story name, required if FIX_USER_CHECK="USER"
    VALUE: float  # User Beta value, required if FIX_USER_CHECK="USER"


class StoryStabilityCoefficientParams(TypedDict, total=False):
    """ADDITIONAL.SET_STABILITY_COEFFICIENT_PARAMS (#10). Defaults are
    server-determined ("System" in the manual) rather than fixed literals."""

    DEFLECTION_AMPL_FACTOR_VALUE: float  # Deflection amplification factor (Cd), default System, optional
    IMPORTANCE_FACTOR_VALUE: int  # Importance factor, default System, optional
    SCALE_FACTOR_VALUE: int  # Scale factor, default System, optional
    LCOMS: List[StoryDriftLcomEntry]  # P-Delta vertical load combination list, default System, optional
    BETA: StoryStabilityBeta  # optional


class StoryStabilityCalculationMethod(TypedDict, total=False):
    """ADDITIONAL.SET_CALCULATION_METHOD (#10) — story-drift basis used for
    the stability coefficient. NOTE: #13 Stiffness Irregularity also has a
    field named SET_CALCULATION_METHOD under ADDITIONAL, but with a
    different sub-schema (STORY_STIFFNESS_METHOD too) — see
    StiffnessCalculationMethod, not this class.

    This enum's wording has flipped twice — keep the history so it isn't
    flipped a third time on a stale assumption. The official Specifications
    table originally misspelled the first value as "Drfit on the Center of
    Mass"; MIDASIT confirmed 2026-07-30 that only the
    spelling was a typo and the product screen for this table (#10 Story
    Stability Coefficient) genuinely used "on", unlike #13/#17. That has
    since been superseded: a follow-up report noted the API
    actually mixes an ignored `SET_STORY_DRIFT_METHOD` field with the real
    `SET_CALCULATION_METHOD.STORY_DRIFT_METHOD` one, and MIDASIT's developer
    decided 2026-08-10 to unify the product UI and API enum on "at" across
    all three tables; the official article was updated 2026-08-20. Current
    correct value is "Drift at the Center of Mass", matching #13/#17.
    """

    STORY_DRIFT_METHOD: str  # "Drift at the Center of Mass"/"Max. Drift of Outer Extreme Points"/"Max. Drift of All Vertical Elements", optional


class StoryStabilityCoefficientAdditional(TypedDict, total=False):
    """docs/manual/21_POST_StoryTables.md #10 — Story Stability Coefficient
    ADDITIONAL object."""

    SET_STABILITY_COEFFICIENT_PARAMS: StoryStabilityCoefficientParams  # optional
    SET_CALCULATION_METHOD: StoryStabilityCalculationMethod  # optional


class SelectIrregularEnds(TypedDict, total=False):
    """Shared ADDITIONAL.SELECT_IRREGULAR_ENDS object — Required for both
    #11 Torsional Irregularity Check and #12 Torsional Amplification Factor
    (identical shape per the manual)."""

    USER_DEFINE: bool  # False=auto-calculated extreme points, True=user-specified, required
    SELECT_NODES: List[int]  # Exactly 2 node IDs, required if USER_DEFINE=true


class IrregularEndsAdditional(TypedDict, total=False):
    """docs/manual/21_POST_StoryTables.md #11/#12 — Torsional Irregularity
    Check / Torsional Amplification Factor ADDITIONAL object (shared shape)."""

    SELECT_IRREGULAR_ENDS: SelectIrregularEnds  # required


class StiffnessCalculationMethod(TypedDict, total=False):
    """ADDITIONAL.SET_CALCULATION_METHOD (#13) — distinct from
    StoryStabilityCalculationMethod (#10); adds STORY_STIFFNESS_METHOD.

    The official Specifications table for this table misspells the third enum
    value as "Max. Drfit of All Vertical Elements"; #17's article documents
    the same enum correctly, so the normalized form is used here.

    ⚠️ 2026-08-27: both fields' default was documented here as the first
    enum value; the manual's own table (re-checked against article id
    `49513107644057`) literally says `"System"` for both -- a sentinel
    meaning "use the document's current calculation setting", not one of
    the listed enum strings. Corrected the comments; not independently
    live-tested (omitting the field and reading back the resolved value
    would need a real story model with an existing calculation setting).
    """

    STORY_DRIFT_METHOD: str  # "Drift at the Center of Mass"/"Max. Drift of Outer Extreme Points"/"Max. Drift of All Vertical Elements", default "System" (use document's current setting), optional
    STORY_STIFFNESS_METHOD: str  # "1 / Story Drift Ratio"/"Story Shear / Story Drift", default "System" (use document's current setting), optional


class StiffnessIrregularityAdditional(TypedDict, total=False):
    """docs/manual/21_POST_StoryTables.md #13 — Stiffness Irregularity Check
    (Soft Story) ADDITIONAL object. SET_CALCULATION_METHOD is Required."""

    SET_CALCULATION_METHOD: StiffnessCalculationMethod  # required


class CapacityIrregularityAdditional(TypedDict, total=False):
    """docs/manual/21_POST_StoryTables.md #14 — Capacity Irregularity Check
    (Weak Story) ADDITIONAL object. SET_ANGLE is Required for this table."""

    SET_ANGLE: StorySetAngle  # required


class UltimateStoryShearForceAdditional(TypedDict, total=False):
    """docs/manual/21_POST_StoryTables.md #16 — Ultimate Story Shear Force
    Check ADDITIONAL object — 2026-07-30 official addition (previously
    undocumented). Same shape as #14 Capacity Irregularity Check, but
    SET_ANGLE (and its nested ANGLE) is Optional here, not Required."""

    SET_ANGLE: StorySetAngle  # optional, default ANGLE=0


class WeightIrregularityCalculationMethod(TypedDict, total=False):
    """docs/manual/21_POST_StoryTables.md #17 — Weight Irregularity Check's
    "SET_CALCULATION_METHOD" field. Unlike every other story table, the
    manual places this directly under "Argument" rather than nesting it in
    "ADDITIONAL" — see get_table()'s set_calculation_method kwarg."""

    STORY_DRIFT_METHOD: str  # "Drift at the Center of Mass"/"Max. Drift of Outer Extreme Points"/"Max. Drift of All Vertical Elements", default "", optional


def get_story_drift_table(
    table_type: str = TABLE_TYPE_STORY_DRIFT_COMB,
    table_name: str = "",
    *,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    node_elems: Optional[NodeElemsSelector] = None,
    load_case_names: Optional[List[str]] = None,
    opt_cs: Optional[bool] = None,
    stage_step: Optional[List[str]] = None,
    additional: Optional[StoryDriftAdditional] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/21_POST_StoryTables.md #1 — Story Drift.

    table_type: TABLE_TYPE_STORY_DRIFT_X/_Y (single-direction) or
    TABLE_TYPE_STORY_DRIFT_COMB (combined, adds shear-weighted/selected-node
    detail columns).
    additional: drift-ratio judgment method/parameters, plus (COMB only) which
    drift-basis columns to include — see StoryDriftAdditional.
    """
    return get_table(
        table_type,
        table_name,
        unit=unit,
        styles=styles,
        components=components,
        node_elems=node_elems,
        load_case_names=load_case_names,
        opt_cs=opt_cs,
        stage_step=stage_step,
        additional=additional,
        client=client,
    )


def get_story_displacement_table(
    table_type: str = TABLE_TYPE_STORY_DISPLACEMENT_COMB,
    table_name: str = "",
    *,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    node_elems: Optional[NodeElemsSelector] = None,
    load_case_names: Optional[List[str]] = None,
    opt_cs: Optional[bool] = None,
    stage_step: Optional[List[str]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/21_POST_StoryTables.md #2 — Story Displacement.

    table_type: TABLE_TYPE_STORY_DISPLACEMENT_X/_Y (single-direction) or
    TABLE_TYPE_STORY_DISPLACEMENT_COMB (combined).
    """
    return get_table(
        table_type,
        table_name,
        unit=unit,
        styles=styles,
        components=components,
        node_elems=node_elems,
        load_case_names=load_case_names,
        opt_cs=opt_cs,
        stage_step=stage_step,
        client=client,
    )


def get_story_shear_force_rs_table(
    table_name: str = "",
    *,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    node_elems: Optional[NodeElemsSelector] = None,
    load_case_names: Optional[List[str]] = None,
    opt_cs: Optional[bool] = None,
    stage_step: Optional[List[str]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/21_POST_StoryTables.md #3 — Story Shear Force (R.S. Analysis).

    Requires a defined and analyzed response-spectrum (RS) load case in
    load_case_names — DATA is returned empty otherwise.
    """
    return get_table(
        TABLE_TYPE_STORY_SHEAR_FOR_RS,
        table_name,
        unit=unit,
        styles=styles,
        components=components,
        node_elems=node_elems,
        load_case_names=load_case_names,
        opt_cs=opt_cs,
        stage_step=stage_step,
        client=client,
    )


def get_story_shear_force_coefficient_table(
    table_name: str = "",
    *,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    node_elems: Optional[NodeElemsSelector] = None,
    load_case_names: Optional[List[str]] = None,
    opt_cs: Optional[bool] = None,
    stage_step: Optional[List[str]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/21_POST_StoryTables.md #4 — Story Shear Force Coefficient (R.S. Analysis).

    Requires a defined and analyzed response-spectrum (RS) load case in
    load_case_names — DATA is returned empty otherwise.
    """
    return get_table(
        TABLE_TYPE_STORY_SHEAR_FORCE_COEFFICIENT,
        table_name,
        unit=unit,
        styles=styles,
        components=components,
        node_elems=node_elems,
        load_case_names=load_case_names,
        opt_cs=opt_cs,
        stage_step=stage_step,
        client=client,
    )


def get_story_mode_shape_table(
    table_name: str = "",
    *,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    node_elems: Optional[NodeElemsSelector] = None,
    load_case_names: Optional[List[str]] = None,
    opt_cs: Optional[bool] = None,
    stage_step: Optional[List[str]] = None,
    modes: Optional[List[str]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/21_POST_StoryTables.md #5 — Story Mode Shape.

    Requires mode/response-spectrum analysis results.
    modes: filter to specific modes, e.g. ["Mode1", "Mode2"]; omitting it
    returns all modes.
    """
    return get_table(
        TABLE_TYPE_STORY_MODE_SHAPE,
        table_name,
        unit=unit,
        styles=styles,
        components=components,
        node_elems=node_elems,
        load_case_names=load_case_names,
        opt_cs=opt_cs,
        stage_step=stage_step,
        modes=modes,
        client=client,
    )


def get_story_shear_force_ratio_table(
    table_name: str = "",
    *,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    node_elems: Optional[NodeElemsSelector] = None,
    load_case_names: Optional[List[str]] = None,
    opt_cs: Optional[bool] = None,
    stage_step: Optional[List[str]] = None,
    story_names: Optional[List[str]] = None,
    additional: Optional[StoryShearForceRatioAdditional] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/21_POST_StoryTables.md #6 — Story Shear Force Ratio.

    Per-story shear force and share ratio by vertical-member type
    (Frame/Wall), for two angles (Angle1/Angle2). The response also includes
    a top-level "SUB_TABLES" array (linear/numerical shear-force-by-type
    sums) not modeled here — access it directly off the raw response dict.
    story_names: restrict to specific stories (default: all).
    additional: SET_ANGLE — Required; sets Angle1 (Angle2 = Angle1 + 90°).
    """
    return get_table(
        TABLE_TYPE_STORY_SHEAR_FORCE_RATIO,
        table_name,
        unit=unit,
        styles=styles,
        components=components,
        node_elems=node_elems,
        load_case_names=load_case_names,
        opt_cs=opt_cs,
        stage_step=stage_step,
        story_names=story_names,
        additional=additional,
        client=client,
    )


def get_story_eccentricity_table(
    table_name: str = "",
    *,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    node_elems: Optional[NodeElemsSelector] = None,
    load_case_names: Optional[List[str]] = None,
    opt_cs: Optional[bool] = None,
    stage_step: Optional[List[str]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/21_POST_StoryTables.md #7 — Story Eccentricity.

    Weight/stiffness center coordinates, eccentricity distance, torsional
    stiffness, elastic radius, and eccentricity ratio per story.
    """
    return get_table(
        TABLE_TYPE_STORY_ECCENTRICITY,
        table_name,
        unit=unit,
        styles=styles,
        components=components,
        node_elems=node_elems,
        load_case_names=load_case_names,
        opt_cs=opt_cs,
        stage_step=stage_step,
        client=client,
    )


def get_overturning_moment_table(
    table_name: str = "",
    *,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    node_elems: Optional[NodeElemsSelector] = None,
    load_case_names: Optional[List[str]] = None,
    opt_cs: Optional[bool] = None,
    stage_step: Optional[List[str]] = None,
    additional: Optional[OverturningMomentAdditional] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/21_POST_StoryTables.md #8 — Overturning Moment.

    Per-story overturning moment split by vertical-member type
    (Frame/Wall), for two angles (Angle1/Angle2).
    additional: angle (default 0) and response-spectrum scale/reduction-factor
    settings — both optional, see OverturningMomentAdditional.
    """
    return get_table(
        TABLE_TYPE_OVERTURNING_MOMENT,
        table_name,
        unit=unit,
        styles=styles,
        components=components,
        node_elems=node_elems,
        load_case_names=load_case_names,
        opt_cs=opt_cs,
        stage_step=stage_step,
        additional=additional,
        client=client,
    )


def get_story_axial_force_sum_table(
    table_name: str = "",
    *,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    node_elems: Optional[NodeElemsSelector] = None,
    load_case_names: Optional[List[str]] = None,
    opt_cs: Optional[bool] = None,
    stage_step: Optional[List[str]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/21_POST_StoryTables.md #9 — Story Axial Force Sum.

    Sum of vertical-element axial force per story, plus the axial-force
    centroid (X/Y coordinates).
    """
    return get_table(
        TABLE_TYPE_STORY_AXIAL_FORCE_SUM,
        table_name,
        unit=unit,
        styles=styles,
        components=components,
        node_elems=node_elems,
        load_case_names=load_case_names,
        opt_cs=opt_cs,
        stage_step=stage_step,
        client=client,
    )


def get_story_stability_coefficient_table(
    table_type: str = TABLE_TYPE_STORY_STABILITY_COEFFICIENT_X,
    table_name: str = "",
    *,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    node_elems: Optional[NodeElemsSelector] = None,
    load_case_names: Optional[List[str]] = None,
    opt_cs: Optional[bool] = None,
    stage_step: Optional[List[str]] = None,
    additional: Optional[StoryStabilityCoefficientAdditional] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/21_POST_StoryTables.md #10 — Story Stability Coefficient.

    table_type: TABLE_TYPE_STORY_STABILITY_COEFFICIENT_X or _Y.
    additional: stability-coefficient (θ) parameters and story-drift
    calculation basis — both optional, see StoryStabilityCoefficientAdditional.
    """
    return get_table(
        table_type,
        table_name,
        unit=unit,
        styles=styles,
        components=components,
        node_elems=node_elems,
        load_case_names=load_case_names,
        opt_cs=opt_cs,
        stage_step=stage_step,
        additional=additional,
        client=client,
    )


def get_torsional_irregularity_table(
    table_type: str = TABLE_TYPE_TORSIONAL_IRREGULARITY_X,
    table_name: str = "",
    *,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    node_elems: Optional[NodeElemsSelector] = None,
    load_case_names: Optional[List[str]] = None,
    opt_cs: Optional[bool] = None,
    stage_step: Optional[List[str]] = None,
    additional: Optional[IrregularEndsAdditional] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/21_POST_StoryTables.md #11 — Torsional Irregularity Check.

    table_type: TABLE_TYPE_TORSIONAL_IRREGULARITY_X or _Y.
    additional: SELECT_IRREGULAR_ENDS — Required; extreme-point node
    selection (auto-calculated unless USER_DEFINE=true).
    """
    return get_table(
        table_type,
        table_name,
        unit=unit,
        styles=styles,
        components=components,
        node_elems=node_elems,
        load_case_names=load_case_names,
        opt_cs=opt_cs,
        stage_step=stage_step,
        additional=additional,
        client=client,
    )


def get_torsional_amplification_factor_table(
    table_type: str = TABLE_TYPE_TORSIONAL_AMPLIFICATION_FACTOR_X,
    table_name: str = "",
    *,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    node_elems: Optional[NodeElemsSelector] = None,
    load_case_names: Optional[List[str]] = None,
    opt_cs: Optional[bool] = None,
    stage_step: Optional[List[str]] = None,
    additional: Optional[IrregularEndsAdditional] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/21_POST_StoryTables.md #12 — Torsional Amplification Factor.

    table_type: TABLE_TYPE_TORSIONAL_AMPLIFICATION_FACTOR_X or _Y.
    additional: SELECT_IRREGULAR_ENDS — Required; extreme-point node
    selection (auto-calculated unless USER_DEFINE=true).
    """
    return get_table(
        table_type,
        table_name,
        unit=unit,
        styles=styles,
        components=components,
        node_elems=node_elems,
        load_case_names=load_case_names,
        opt_cs=opt_cs,
        stage_step=stage_step,
        additional=additional,
        client=client,
    )


def get_stiffness_irregularity_table(
    table_type: str = TABLE_TYPE_STIFFNESS_IRREGULARITY_X,
    table_name: str = "",
    *,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    node_elems: Optional[NodeElemsSelector] = None,
    load_case_names: Optional[List[str]] = None,
    opt_cs: Optional[bool] = None,
    stage_step: Optional[List[str]] = None,
    additional: Optional[StiffnessIrregularityAdditional] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/21_POST_StoryTables.md #13 — Stiffness Irregularity Check (Soft Story).

    table_type: TABLE_TYPE_STIFFNESS_IRREGULARITY_X or _Y.
    additional: SET_CALCULATION_METHOD — Required; story-drift and
    story-stiffness calculation basis, see StiffnessCalculationMethod.
    """
    return get_table(
        table_type,
        table_name,
        unit=unit,
        styles=styles,
        components=components,
        node_elems=node_elems,
        load_case_names=load_case_names,
        opt_cs=opt_cs,
        stage_step=stage_step,
        additional=additional,
        client=client,
    )


def get_capacity_irregularity_table(
    table_name: str = "",
    *,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    node_elems: Optional[NodeElemsSelector] = None,
    load_case_names: Optional[List[str]] = None,
    opt_cs: Optional[bool] = None,
    stage_step: Optional[List[str]] = None,
    additional: Optional[CapacityIrregularityAdditional] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/21_POST_StoryTables.md #14 — Capacity Irregularity Check (Weak Story).

    Per-story shear strength vs. upper-story shear strength, for two angles
    (Angle1/Angle2).
    additional: SET_ANGLE — Required; sets Angle1 (Angle2 = Angle1 + 90°).
    """
    return get_table(
        TABLE_TYPE_CAPACITY_IRREGULARITY,
        table_name,
        unit=unit,
        styles=styles,
        components=components,
        node_elems=node_elems,
        load_case_names=load_case_names,
        opt_cs=opt_cs,
        stage_step=stage_step,
        additional=additional,
        client=client,
    )


def get_criteria_for_regularity_in_plan_table(
    table_name: str = "",
    *,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    node_elems: Optional[NodeElemsSelector] = None,
    load_case_names: Optional[List[str]] = None,
    opt_cs: Optional[bool] = None,
    stage_step: Optional[List[str]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/21_POST_StoryTables.md #15 — Criteria for Regularity in Plan."""
    return get_table(
        TABLE_TYPE_CRITERIA_FOR_REGULARITY_IN_PLAN,
        table_name,
        unit=unit,
        styles=styles,
        components=components,
        node_elems=node_elems,
        load_case_names=load_case_names,
        opt_cs=opt_cs,
        stage_step=stage_step,
        client=client,
    )


def get_ultimate_story_shear_force_check_table(
    table_name: str = "",
    *,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    node_elems: Optional[NodeElemsSelector] = None,
    load_case_names: Optional[List[str]] = None,
    opt_cs: Optional[bool] = None,
    stage_step: Optional[List[str]] = None,
    additional: Optional[UltimateStoryShearForceAdditional] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/21_POST_StoryTables.md #16 — Ultimate Story Shear For Check.

    Applied shear force (Ve) vs. clockwise/counter-clockwise ultimate shear
    force (Vp) by column/wall, with a final OK/NG remark.

    additional: SET_ANGLE — Optional, default ANGLE=0 (unlike #14 Capacity
    Irregularity Check's Required SET_ANGLE). 2026-07-30 official addition;
    previously undocumented.
    """
    return get_table(
        TABLE_TYPE_ULTIMATE_STORY_SHEAR_FORCE_CHECK,
        table_name,
        unit=unit,
        styles=styles,
        components=components,
        node_elems=node_elems,
        load_case_names=load_case_names,
        opt_cs=opt_cs,
        stage_step=stage_step,
        additional=additional,
        client=client,
    )


def get_weight_irregularity_table(
    table_type: str = TABLE_TYPE_WEIGHT_IRREGULARITY_X,
    table_name: str = "",
    *,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    node_elems: Optional[NodeElemsSelector] = None,
    load_case_names: Optional[List[str]] = None,
    opt_cs: Optional[bool] = None,
    stage_step: Optional[List[str]] = None,
    set_calculation_method: Optional[WeightIrregularityCalculationMethod] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/21_POST_StoryTables.md #17 — Weight Irregularity Check.

    table_type: TABLE_TYPE_WEIGHT_IRREGULARITY_X or _Y.
    set_calculation_method: story-drift calculation basis — optional. Unlike
    every other story table's per-table setting, this one is NOT wrapped in
    "ADDITIONAL"; it sits directly under "Argument" per the manual.
    """
    return get_table(
        table_type,
        table_name,
        unit=unit,
        styles=styles,
        components=components,
        node_elems=node_elems,
        load_case_names=load_case_names,
        opt_cs=opt_cs,
        stage_step=stage_step,
        set_calculation_method=set_calculation_method,
        client=client,
    )
