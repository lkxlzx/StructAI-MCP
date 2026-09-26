"""Source: docs/manual/18_POST_PreProcess.md, items 1-10.

All functions POST to the shared /post/TABLE endpoint — see post/base.py.
"""
from __future__ import annotations

from typing import List, Optional

from ..client import MidasClient
from .base import NodeElemsSelector, TableStyles, TableUnit, get_table

# 1. Element Weight Table
TABLE_TYPE_ELEMENT_WEIGHT = "ELEMENTWEIGHT"

# 2. Nodal Body Force Table
TABLE_TYPE_NODAL_BODY_FORCE = "NODALBODYFORCE"

# 5. Material Table
TABLE_TYPE_MATERIAL = "MATERIAL"

# 6. Section Table — 10 section-kind variants
TABLE_TYPE_SECTION_ALL = "SECTIONALL"
TABLE_TYPE_SECTION_COMBINED = "SECTIONCOMBINED"
TABLE_TYPE_SECTION_COMPOSITE = "SECTIONCOMPOSITE"
TABLE_TYPE_SECTION_CONSTRUCTION = "SECTIONCONSTRUCTION"
TABLE_TYPE_SECTION_DB_USER = "SECTIONDB/USER"
TABLE_TYPE_SECTION_PSC = "SECTIONPSC"
TABLE_TYPE_SECTION_SRC = "SECTIONSRC"
TABLE_TYPE_SECTION_STEEL_GIRDER = "SECTIONSTEELGIRDER"
TABLE_TYPE_SECTION_TAPERED = "SECTIONTAPERED"
TABLE_TYPE_SECTION_VALUE = "SECTIONVALUE"

# 7. Restraint Supports Table
TABLE_TYPE_SUPPORTS = "SUPPORTS"

# 8. Story Mass Summary Table
TABLE_TYPE_STORY_MASS = "STORY_MASS"
TABLE_TYPE_STORY_MASS_X = "STORY_MASS_X"
TABLE_TYPE_STORY_MASS_Y = "STORY_MASS_Y"
TABLE_TYPE_STORY_MASS_Z = "STORY_MASS_Z"

# 9. Story Load Summary Table
TABLE_TYPE_STORY_LOAD_X = "STORY_LOAD_X"
TABLE_TYPE_STORY_LOAD_Y = "STORY_LOAD_Y"
TABLE_TYPE_STORY_LOAD_Z = "STORY_LOAD_Z"

# 10. Story Weight Table
TABLE_TYPE_STORY_WEIGHT = "STORYWEIGHT"


def get_element_weight_table(
    table_name: str = "",
    *,
    node_elems: Optional[NodeElemsSelector] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/18_POST_PreProcess.md #1 — Element Weight Table.

    node_elems: target scope (exactly one of KEYS/TO/STRUCTURE_GROUP_NAME);
    omit for all elements.
    """
    return get_table(TABLE_TYPE_ELEMENT_WEIGHT, table_name, node_elems=node_elems, client=client)


def get_nodal_body_force_table(table_name: str = "", *, client: Optional[MidasClient] = None) -> dict:
    """docs/manual/18_POST_PreProcess.md #2 — Nodal Body Force Table."""
    return get_table(TABLE_TYPE_NODAL_BODY_FORCE, table_name, client=client)


def get_mass_summary_table(
    direction: str, table_name: str = "", *, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/18_POST_PreProcess.md #3 — Mass Summary Table.

    direction: "X"/"Y"/"Z".
    """
    return get_table(f"MASS_SUMMARY_{direction}", table_name, client=client)


def get_load_summary_table(
    direction: str, table_name: str = "", *, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/18_POST_PreProcess.md #4 — Load Summary Table.

    direction: "X"/"Y"/"Z".
    """
    return get_table(f"LOAD_SUMMARY_{direction}", table_name, client=client)


def get_material_table(table_name: str = "", *, client: Optional[MidasClient] = None) -> dict:
    """docs/manual/18_POST_PreProcess.md #5 — Material Table."""
    return get_table(TABLE_TYPE_MATERIAL, table_name, client=client)


def get_section_table(
    table_type: str = TABLE_TYPE_SECTION_ALL, table_name: str = "", *, client: Optional[MidasClient] = None
) -> dict:
    """docs/manual/18_POST_PreProcess.md #6 — Section Table.

    table_type: one of the TABLE_TYPE_SECTION_* constants above.
    """
    return get_table(table_type, table_name, client=client)


def get_supports_table(table_name: str = "", *, client: Optional[MidasClient] = None) -> dict:
    """docs/manual/18_POST_PreProcess.md #7 — Restraint Supports Table."""
    return get_table(TABLE_TYPE_SUPPORTS, table_name, client=client)


def get_story_mass_summary_table(
    table_type: str = TABLE_TYPE_STORY_MASS,
    table_name: str = "",
    *,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/18_POST_PreProcess.md #8 — Story Mass Summary Table.

    table_type: TABLE_TYPE_STORY_MASS (direction-summed) or
    TABLE_TYPE_STORY_MASS_X/_Y/_Z (per-direction).
    """
    return get_table(table_type, table_name, unit=unit, styles=styles, components=components, client=client)


def get_story_load_summary_table(
    direction: str,
    table_name: str = "",
    *,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    load_case_names: Optional[List[str]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/18_POST_PreProcess.md #9 — Story Load Summary Table.

    direction: "X"/"Y"/"Z".
    load_case_names: e.g. ["DL (ST)"] — present in the manual's Request
    example but missing from its own Specifications table (a manual
    self-contradiction; the example wins per this repo's convention).

    2026-08-06 manual update: TABLE_TYPE renamed
    STORY_LOAD_SUMMARY_{dir} -> STORY_LOAD_{dir}, matching STORY_MASS's
    naming (the other half of the same ticket, already reflected below).
    This call also gained unit/styles/components/load_case_names.

    ⚠️ Live-verified 2026-08-13 (Gen NX v2.1, build 08/12/2026): against a
    model with 2 real Stories and one static load case, direction="X"
    with load_case_names=["DL(ST)"] returned real per-story populated
    rows keyed by story name — confirms the renamed TABLE_TYPE and the
    new params both work as documented.

    ⚠️ 2026-08-27: the sibling manual repo's full re-verification pass
    reversed course, claiming this was all a mistake — that the 2026-08-06
    sync had actually copied Story Mass Summary Table's shape by accident,
    and the real params are just TABLE_NAME/TABLE_TYPE(STORY_LOAD_SUMMARY_
    {dir})/EXPORT_PATH. Re-tested live the same day on Gen NX to check:
    `TABLE_TYPE="STORY_LOAD_X"` (this function's value) still answers
    cleanly (`{"message": ""}` on a document with no story data, same
    shape as the known-good sibling `STORY_MASS_X`), while
    `TABLE_TYPE="STORY_LOAD_SUMMARY_X"` (the manual's new claim, tried in
    every case combination and casing) consistently answers `"there was
    an error creating utbl"` — an unrecognized-table-type error, not a
    data-shape error. **The manual's new correction is wrong; this
    function's existing TABLE_TYPE and params are confirmed correct
    again.** Don't flip this back without new live evidence.
    """
    return get_table(
        f"STORY_LOAD_{direction}",
        table_name,
        unit=unit,
        styles=styles,
        components=components,
        load_case_names=load_case_names,
        client=client,
    )


def get_story_weight_table(
    table_name: str = "",
    *,
    unit: Optional[TableUnit] = None,
    styles: Optional[TableStyles] = None,
    components: Optional[List[str]] = None,
    client: Optional[MidasClient] = None,
) -> dict:
    """docs/manual/18_POST_PreProcess.md #10 — Story Weight Table.

    2026-08-06 manual update: gained unit/styles/components (TABLE_TYPE
    itself, "STORYWEIGHT", is unchanged).

    ⚠️ Live-verified 2026-08-13 (Gen NX v2.1, build 08/12/2026): against
    the same 2-story model, returned real per-story populated rows.
    """
    return get_table(TABLE_TYPE_STORY_WEIGHT, table_name, unit=unit, styles=styles, components=components, client=client)
