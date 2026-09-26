"""One-time / re-run-on-demand: build docs/coverage.json by parsing the
sibling MIDAS-API repo's docs/manual/INDEX.md endpoint tables.

Usage (from a checkout that sits next to the MIDAS-API repo):
    python scripts/vendor_coverage.py [path-to-MIDAS-API-repo]

This is a static vendoring step, not a live sync — the new repo has no
runtime dependency on the sibling repo. Re-run manually and diff when the
sibling repo's INDEX.md changes meaningfully.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Endpoints implemented in this repo so far (v1). Update as new resources
# are added; see IMPLEMENTED_MODULE for where each one's code/tests live.
IMPLEMENTED = {
    "/doc/NEW", "/doc/OPEN", "/doc/CLOSE", "/doc/SAVE", "/doc/SAVEAS",
    "/doc/STAGAS", "/doc/IMPORT", "/doc/IMPORTMXT", "/doc/EXPORT", "/doc/EXPORTMXT",
    "/doc/ANAL",
    "/db/UNIT", "/db/STYP",
    "/db/NODE", "/db/ELEM",
    "/db/MATL", "/db/MATD", "/db/SECT", "/db/THIK",
    "/db/CONS",
    "/db/STLD", "/db/BODF", "/db/CNLD", "/db/BMLD", "/db/PRES",
}

IMPLEMENTED_MODULE = {
    "/doc/": "midas_nx.doc",
    "/db/UNIT": "midas_nx.db.project", "/db/STYP": "midas_nx.db.project",
    "/db/NODE": "midas_nx.db.node_element", "/db/ELEM": "midas_nx.db.node_element",
    "/db/MATL": "midas_nx.db.properties.material", "/db/MATD": "midas_nx.db.properties.material",
    "/db/SECT": "midas_nx.db.properties.section",
    "/db/THIK": "midas_nx.db.properties.thickness",
    "/db/CONS": "midas_nx.db.boundary",
    "/db/STLD": "midas_nx.db.static_loads", "/db/BODF": "midas_nx.db.static_loads",
    "/db/CNLD": "midas_nx.db.static_loads", "/db/BMLD": "midas_nx.db.static_loads",
    "/db/PRES": "midas_nx.db.static_loads",
}

# Planned module assignment by chapter file, so a future contributor knows
# where a not-yet-implemented endpoint should go without redesigning layout.
PLANNED_MODULE_BY_CHAPTER = {
    "01_DOC.md": "midas_nx.doc",
    "02_DB_Project_Structure.md": "midas_nx.db.project",
    "03_DB_Node_Element.md": "midas_nx.db.node_element",
    "04_DB_Properties.md": "midas_nx.db.properties.*",
    "05_DB_Boundary.md": "midas_nx.db.boundary",
    "06_DB_Static_Loads.md": "midas_nx.db.static_loads",
    "07_DB_Temperature_Prestress.md": "midas_nx.db.temperature_prestress",
    "08_DB_Moving_Loads.md": "midas_nx.db.moving_loads",
    "09_DB_Dynamic_Loads.md": "midas_nx.db.dynamic_loads",
    "10_DB_Construction_Stage.md": "midas_nx.db.construction_stage",
    "11_DB_Settlement_Misc_Loads.md": "midas_nx.db.misc_loads",
    "12_DB_Analysis_Control.md": "midas_nx.db.analysis_control",
    "13_DB_Load_Combinations.md": "midas_nx.db.load_combinations",
    "14_DB_Pushover.md": "midas_nx.db.pushover",
    "15_OPE.md": "midas_nx.ope",
    "16_VIEW.md": "midas_nx.view",
    "17_DB_Bridge.md": "midas_nx.db.bridge",
    "18_POST_PreProcess.md": "midas_nx.post.pre_process",
    "19_POST_AnalysisResult_1.md": "midas_nx.post.result_1",
    "20_POST_AnalysisResult_2.md": "midas_nx.post.result_2",
    "21_POST_StoryTables.md": "midas_nx.post.story",
    "22_POST_TH_HY_Pushover.md": "midas_nx.post.th_hy_pushover",
    "23_POST_Design.md": "midas_nx.post.design",
    "24_DB_Design.md": "midas_nx.db.design",
    "25_Design_Steel_KDS41302022.md": "midas_nx.design.steel_kds",
    "26_Design_RC_KDS41202022.md": "midas_nx.design.rc_kds",
    "27_Design_SRC_AIKSRC2K.md": "midas_nx.design.src_aik",
}

CIVIL_ONLY_CHAPTERS = {"08_DB_Moving_Loads.md", "17_DB_Bridge.md"}

# Explicit h2/h3 heading text (as it literally appears in INDEX.md) -> chapter file.
# Hand-authored rather than inferred, because INDEX.md's heading hierarchy doesn't
# map 1:1 to files (e.g. "## DB" has multiple "### X" subsections spread across
# files 02-14/17/24, and files 07/10/11 each span two "### " subsections).
HEADING_TO_FILE = {
    "DOC": "01_DOC.md",
    "Project": "02_DB_Project_Structure.md",
    "View": "02_DB_Project_Structure.md",
    "Structure": "02_DB_Project_Structure.md",
    "Node / Element": "03_DB_Node_Element.md",
    "Properties": "04_DB_Properties.md",
    "Boundary": "05_DB_Boundary.md",
    "Static Loads": "06_DB_Static_Loads.md",
    "Temperature Loads": "07_DB_Temperature_Prestress.md",
    "Prestress Loads": "07_DB_Temperature_Prestress.md",
    "Moving Loads": "08_DB_Moving_Loads.md",
    "Dynamic Loads": "09_DB_Dynamic_Loads.md",
    "Construction Stage Loads": "10_DB_Construction_Stage.md",
    "Heat of Hydration Loads": "10_DB_Construction_Stage.md",
    "Settlement Loads": "11_DB_Settlement_Misc_Loads.md",
    "Miscellaneous Loads": "11_DB_Settlement_Misc_Loads.md",
    "Analysis Control": "12_DB_Analysis_Control.md",
    "Analysis Results / Load Combinations": "13_DB_Load_Combinations.md",
    "Bridge Specialization Results": "17_DB_Bridge.md",
    "Pushover": "14_DB_Pushover.md",
    "Design (DB)": "24_DB_Design.md",
    "OPE": "15_OPE.md",
    "VIEW": "16_VIEW.md",
    "Design (POST)": "23_POST_Design.md",
}

# Chapters whose internal item numbering INDEX.md doesn't enumerate by URL
# (huge design-code tables, 25-27, keyed by Code not Endpoint; POST's
# Pre-Process/Analysis-Result/Story tables, which are TABLE_TYPE values under
# the single /post/TABLE endpoint, not distinct URLs). Represented as one
# aggregate "planned" line each rather than parsed row-by-row.
AGGREGATE_PLANNED = [
    {"endpoint": "/post/TABLE (Pre-Process Table types)", "name": "10 pre-process table types",
     "chapter_file": "18_POST_PreProcess.md", "module": "midas_nx.post.pre_process"},
    {"endpoint": "/post/TABLE (Analysis Result Table types)", "name": "~24 analysis result table types",
     "chapter_file": "19_POST_AnalysisResult_1.md / 20_POST_AnalysisResult_2.md", "module": "midas_nx.post.result_1"},
    {"endpoint": "/post/TABLE (Analysis Story Table types)", "name": "~16 story table types",
     "chapter_file": "21_POST_StoryTables.md", "module": "midas_nx.post.story"},
    {"endpoint": "Design Code – STEEL KDS 41 30:2022", "name": "27 endpoints (steel design code-check)",
     "chapter_file": "25_Design_Steel_KDS41302022.md", "module": "midas_nx.design.steel_kds"},
    {"endpoint": "Design Code – RC KDS 41 20:2022", "name": "69 endpoints (RC design code-check)",
     "chapter_file": "26_Design_RC_KDS41202022.md", "module": "midas_nx.design.rc_kds"},
    {"endpoint": "Design Code – SRC AIK-SRC2K", "name": "27 endpoints (SRC design code-check)",
     "chapter_file": "27_Design_SRC_AIKSRC2K.md", "module": "midas_nx.design.src_aik"},
]


def parse_index(index_path: Path) -> list[dict]:
    """Walk INDEX.md tracking the current h2/h3 heading, and collect every
    "| No. | `/endpoint` | name |" row under a heading we know how to place."""
    text = index_path.read_text(encoding="utf-8")
    entries: list[dict] = []
    current_file: str | None = None

    for line in text.splitlines():
        heading_match = re.match(r"^#{2,3}\s+(.+)$", line)
        if heading_match:
            current_file = HEADING_TO_FILE.get(heading_match.group(1).strip())
            continue
        row = re.match(r"^\|\s*\d+\s*\|\s*`(/[a-zA-Z0-9_/-]+)`\s*\|\s*(.*?)\s*\|\s*$", line)
        if row and current_file:
            endpoint, name = row.group(1), row.group(2)
            entries.append({"endpoint": endpoint, "name": name, "chapter_file": current_file})
    return entries


def main() -> None:
    repo_arg = sys.argv[1] if len(sys.argv) > 1 else "../MIDAS-API"
    index_path = Path(repo_arg) / "docs" / "manual" / "INDEX.md"
    if not index_path.exists():
        print(f"INDEX.md not found at {index_path}. Pass the MIDAS-API repo path as an argument.")
        sys.exit(1)

    entries = parse_index(index_path)
    if not entries:
        print("No endpoint rows parsed — INDEX.md structure may have changed; "
              "inspect scripts/vendor_coverage.py's heading-matching logic.")
        sys.exit(1)

    registry = []
    for e in entries:
        endpoint, chapter_file = e["endpoint"], e["chapter_file"]
        status = "implemented" if endpoint in IMPLEMENTED else "planned"
        if status == "implemented":
            module = next((m for prefix, m in IMPLEMENTED_MODULE.items() if endpoint.startswith(prefix)
                            or endpoint == prefix), None)
        else:
            module = PLANNED_MODULE_BY_CHAPTER.get(chapter_file, "midas_nx.<tbd>")
        products = ["civil"] if chapter_file in CIVIL_ONLY_CHAPTERS else ["gen", "civil"]
        registry.append({
            "endpoint": endpoint,
            "name": e["name"],
            "chapter_file": chapter_file,
            "products": products,
            "status": status,
            "module": module,
        })

    for agg in AGGREGATE_PLANNED:
        registry.append({
            "endpoint": agg["endpoint"],
            "name": agg["name"],
            "chapter_file": agg["chapter_file"],
            "products": ["gen", "civil"],
            "status": "planned",
            "module": agg["module"],
        })

    out_path = Path(__file__).resolve().parent.parent / "docs" / "coverage.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "vendored_from": "Dennis5882/MIDAS-API docs/manual/INDEX.md",
                "source_note": (
                    "Static snapshot; re-run scripts/vendor_coverage.py to refresh. "
                    "POST result-table types and the three Design Code chapters "
                    "(25-27) are not itemized by URL in INDEX.md and are represented "
                    "as single aggregate rows rather than one row per table/check."
                ),
                "endpoints": registry,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    implemented_count = sum(1 for r in registry if r["status"] == "implemented")
    print(f"Wrote {out_path} - {implemented_count}/{len(registry)} marked implemented.")


if __name__ == "__main__":
    main()
