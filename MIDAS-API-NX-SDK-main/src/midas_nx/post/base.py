"""Shared plumbing for ``/post/TABLE`` — extracts pre-process, analysis-result,
and story summary tables. Source: docs/manual/18_POST_PreProcess.md through
21_POST_StoryTables.md.

Every ``/post/TABLE`` call shares one endpoint and one POST-only wrapper
(``"Argument"``, not ID-keyed ``"Assign"`` like ``/db/*``) — a ``TABLE_TYPE``
string selects which table is extracted, so this is one generic function
rather than a DbResource-per-table-type. The response shape
(``{FORCE, DIST, HEAD, DATA}``) is identical across every table type; HEAD's
column names vary per table and are only knowable from TABLE_TYPE, so the
response is returned as a plain dict rather than typed further.
"""
from __future__ import annotations

from typing import Any, List, Mapping, Optional, TypedDict

from ..client import MidasClient, get_default_client


class NodeElemsSelector(TypedDict, total=False):
    """Target-scope selector accepted by a handful of table types (e.g.
    Element Weight) — set exactly one of KEYS/TO/STRUCTURE_GROUP_NAME;
    omitting NODE_ELEMS entirely selects all nodes/elements."""

    KEYS: List[int]  # explicit ID list, e.g. [101, 102, 103]
    TO: str  # ID range, e.g. "101 to 105"
    STRUCTURE_GROUP_NAME: str  # structure group name, e.g. "SG1"


class TableUnit(TypedDict, total=False):
    """Response unit override, accepted by the Story-series table types."""

    FORCE: str  # e.g. "KN"
    DIST: str  # e.g. "M"
    HEAT: str
    TEMP: str


class TableStyles(TypedDict, total=False):
    """Response number-format override, accepted by the Story-series table types."""

    FORMAT: str  # "Default"/"Fixed"/"Scientific"/"General"
    PLACE: int  # decimal places, 0-15


class NodeFlag(TypedDict, total=False):
    """Per-DOF output-location flag accepted by a subset of ch20's plate/plane
    stress-force table types — see get_table()'s node_flag parameter docstring."""

    CENTER: bool  # default false
    NODES: bool  # default false


def get_table(
    table_type: str,
    table_name: str = "",
    *,
    export_path: Optional[str] = None,
    node_elems: Optional[NodeElemsSelector] = None,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    load_case_names: Optional[List[str]] = None,
    opt_cs: Optional[bool] = None,
    stage_step: Optional[List[str]] = None,
    parts: Optional[List[str]] = None,
    story_names: Optional[List[str]] = None,
    modes: Optional[List[str]] = None,
    average_nodal_result: Optional[bool] = None,
    node_flag: Optional[NodeFlag] = None,
    # Mapping, not Dict: every caller passes a TypedDict, and TypedDict is
    # deliberately not assignable to the invariant dict[str, Any].
    additional: Optional[Mapping[str, Any]] = None,
    set_calculation_method: Optional[Mapping[str, Any]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """POST /post/TABLE — extract one result table.

    table_type: the table's TABLE_TYPE value (see pre_process.py/result_1.py/
    story.py/design.py for the documented constants).
    table_name: response table title. The manual documents it as also becoming
    the response's top-level key, e.g.
    {table_name: {"FORCE": ..., "DIST": ..., "HEAD": [...], "DATA": [...]}} —
    but live sessions have returned other keys for the same call ("Result
    Table", "empty"), so don't index the response by name. Use
    :func:`unwrap_table` below, which finds the table by shape instead.
    node_elems/unit/styles/components: only meaningful for the specific table
    types documented as supporting them — see each caller's docstring.
    load_case_names: analysis-result tables (ch19-21) — load/combination
    names with a type suffix, e.g. "DL(ST)", "COMB1(CB)", "CS1(CS)". Also
    accepted by ch18's Story Load Summary Table as of the 2026-08-06 manual
    update, whose own example spells the suffix with a leading space
    ("DL (ST)") rather than ch19-21's "DL(ST)" — a manual-source
    inconsistency, not a call-site-specific requirement to enforce here.
    opt_cs/stage_step: analysis-result tables only (ch19-21) — enable and
    select construction-stage steps, e.g. ["CS1:001(first)", "CS1:002(last)"].
    ``opt_cs`` has three states, and leaving it out is not the same as
    ``False``: per the manual (2026-09-15 sync, quoting the official Reaction
    article), ``True`` switches the view to Construction Stage and returns CS
    results, ``False`` switches it to PostCS (the final stage) and returns Post
    results, and omitting it keeps the current view mode. The default ``None``
    omits it. The manual's own Default column still says ``false``, which that
    description contradicts, and the behaviour has not been checked live.
    parts: design-force tables (ch23) only — member end/location or top/bot
    part selection, e.g. ["PartI", "PartJ"]. Not Wall Force (ch20) — MIDASIT
    confirmed 2026-07-30 that table type never supported
    PARTS or SECT_POSITION; both were removed from the official article, and
    this SDK's own get_wall_force_table() no longer accepts either.
    story_names: Story-series (ch21) and Wall Force (ch20) tables — restrict
    to specific story names; omitting it selects all stories. Also accepted
    by Wall Design Forces (ch23) as of the 2026-08-06 manual update;
    that endpoint's own Specifications table numbers it as
    param 9, alongside the existing member-scope/unit/style/component
    params.
    modes: Story Mode Shape (ch21) only — mode filter, e.g. ["Mode1", "Mode2"];
    omitting it returns all modes.
    average_nodal_result: ch20's plate/plane-stress/strain/axisymmetric result
    tables only (20_POST_AnalysisResult_2.md sections 1-19, 23-25 — not every
    table in that chapter; sections 20-21, Solid Force, never had it). Added
    2026-08-27 per the manual's 2026-08-26 re-verification (this whole
    parameter, and node_flag below, were missing from every affected
    section's docs before that pass, not called out as table-specific until
    then). Live-confirmed accepted (not rejected as an unrecognized field) on
    Gen NX via PLATESTRESSL: without a real analysis result the call still
    fails, but with the *same* "no analysis result" error whether or not this
    field is present, not a shape-rejection error.
    node_flag: a smaller subset of the same ch20 tables (sections 3-7, 10-11,
    14-15, 18-19, 22-25) — element-center (CENTER) vs. per-node (NODES)
    output selection. Same 2026-08-27 addition and live-confirmation as
    average_nodal_result above.
    additional: Story-series tables (ch21) only — the table-type-specific
    "ADDITIONAL" object (angle/Beta/node-selection/... settings); see each
    story.py caller's docstring and TypedDict for its shape.
    set_calculation_method: Weight Irregularity Check (ch21) only — unlike
    every other story table, the manual places this field directly under
    "Argument" rather than nesting it in "ADDITIONAL".
    """
    argument: dict = {"TABLE_NAME": table_name, "TABLE_TYPE": table_type}
    if export_path is not None:
        # Resolved on the machine running NX, which may not be this one - see
        # midas_nx.doc's module docstring. A path that doesn't exist there
        # raises a modal dialog on that machine and blocks the session.
        argument["EXPORT_PATH"] = export_path
    if node_elems is not None:
        argument["NODE_ELEMS"] = node_elems
    if unit is not None:
        argument["UNIT"] = unit
    if styles is not None:
        argument["STYLES"] = styles
    if components is not None:
        argument["COMPONENTS"] = components
    if load_case_names is not None:
        argument["LOAD_CASE_NAMES"] = load_case_names
    if opt_cs is not None:
        argument["OPT_CS"] = opt_cs
    if stage_step is not None:
        argument["STAGE_STEP"] = stage_step
    if parts is not None:
        argument["PARTS"] = parts
    if story_names is not None:
        argument["STORY_NAMES"] = story_names
    if modes is not None:
        argument["MODES"] = modes
    if average_nodal_result is not None:
        argument["AVERAGE_NODAL_RESULT"] = average_nodal_result
    if node_flag is not None:
        argument["NODE_FLAG"] = node_flag
    if additional is not None:
        argument["ADDITIONAL"] = additional
    if set_calculation_method is not None:
        argument["SET_CALCULATION_METHOD"] = set_calculation_method
    client = client or get_default_client()
    return client.request("POST", "/post/TABLE", {"Argument": argument})


#: Keys that identify the actual table object inside a /post/TABLE response.
_TABLE_MARKERS = ("HEAD", "DATA")


def unwrap_table(response: Mapping[str, Any]) -> dict:
    """Pull the ``{FORCE, DIST, HEAD, DATA}`` table out of a ``get_table()``
    response, whatever its top-level key happens to be.

    The DbResource-side counterpart is ``DbResource.items()``. Matching on
    shape rather than on the key name is deliberate: the same call has been
    seen returning ``"Result Table"`` and ``"empty"`` as its top-level key
    across sessions, in addition to the ``TABLE_NAME`` the manual documents,
    so ``response[table_name]`` is not safe. Returns ``{}`` when the response
    carries no table (e.g. a zero-row ``{"message": ""}``).

    Example::

        raw = get_reaction_table(load_case_names=["DL(ST)"])
        table = unwrap_table(raw)
        for row in table.get("DATA", []):
            ...
    """
    if not isinstance(response, Mapping):
        return {}
    if any(marker in response for marker in _TABLE_MARKERS):
        return dict(response)
    for value in response.values():
        if isinstance(value, Mapping) and any(marker in value for marker in _TABLE_MARKERS):
            return dict(value)
    return {}
