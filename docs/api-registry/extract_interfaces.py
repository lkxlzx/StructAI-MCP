#!/usr/bin/env python3
"""Extract ``tool_interfaces`` rows from the three normalised MIDAS API manuals.

Inputs
------
``G:\\MAPI\\tools\\inventory.json``
    The endpoint skeleton produced by ``G:\\MAPI\\tools\\extract.py``: for each
    product a list of ``{code, title, line, level, uri, methods, end}``.  It is
    used for the **entry set reconciliation** and the product key, never to
    locate anything: its ``line`` numbers are stale (see report §7).
``G:\\MAPI\\docs\\midas Gen API 专用手册.md`` (410,728 lines)
``G:\\MAPI\\docs\\midas Civil NX API 专用手册.md`` (157,103 lines)
``G:\\MAPI\\docs\\midas Civil Designer API 专用手册.md`` (5,322 lines)
    The manuals.  They are streamed **line by line** — never read whole.
``MIDAS-API-main/docs/manual/01_DOC.md`` … ``27_Design_SRC_AIKSRC2K.md``
    The 27 chapter files.  They define the ``feature`` vocabulary, and each one
    lists the URIs it owns, so ``feature`` is attributed from the chapter files
    rather than from a hand-written chapter-name table.
``docs/api-registry/title_zh.json``
    The Chinese annotation glossary — ``{unwrapped title: {name_zh,
    description_zh, source}}``.  **Optional on purpose**: a missing or malformed
    file degrades to ``null`` annotations and the run continues
    (:func:`load_title_zh`), because the extraction must not depend on curated data
    that another task owns.

Outputs
-------
``docs/api-registry/interfaces.json``      ``{"meta": {...}, "rows": [...]}``
``docs/api-registry/EXTRACTION_REPORT.md`` the coverage report

Design notes
------------
* **The index tables are the primary source.**  Every manual carries a
  ``| # | 接口代码 | 接口名称 | URL | 方法 | 所在章节 |`` table in which one row
  already carries ``interface_code`` + endpoint + method + chapter — exactly the
  columns ``tool_interfaces`` needs.  The bodies are consulted only for the
  request schema (and for URIs the index table missed).
* **Block markers are matched on their name, never on the raw line.**  The three
  manuals write ``Input URI`` / ``JSON Schema`` / ``Active Methods`` as a bold
  paragraph (``**Input URI**``), as a level-5 heading (``##### Input URI``) and as
  an emphasised level-5 heading (``##### **Input URI**``).  Matching only the bold
  paragraph is what made the Gen manual's two English sections contribute 2 body
  claims against 619 ``JSON Schema`` markers; :func:`marker_key` folds all three
  spellings to one name.
* **One row per ``(endpoint, method)``.**  A URI advertising
  ``GET/POST/PUT/DELETE`` yields four rows, and the method is folded into
  ``interface_code`` (``… .read`` / ``… .create``) so
  ``(adapter_code, interface_code)`` stays unique by construction.  The previous
  revision of this pipeline treated the multi-method expansion as a "collision"
  and appended ``.2`` / ``.3``; that is gone.
* **``product_scope`` is always ``"unknown"``.**  The manuals' product labels are
  not trustworthy (《MIDAS API 对接规范》§3.5 第 15 条: of 47 endpoints declared
  "Civil-only", 32 answer on Gen NX too), so "not yet probed live" is emitted as
  itself rather than guessed.
* **The closed sets are imported, never duplicated.**  ``feature`` values, the
  ``feature -> domain`` total function, the ``product_scope`` values and the
  adapter codes all come from :mod:`app.core.constants` /
  :mod:`app.core.midas_config`.
* **The judgement calls are tables.**  Family rules, operation derivation,
  chapter -> feature and the shared-URI discriminator each live in exactly one
  place, so a reviewer can diff a table instead of reverse-engineering control
  flow.
* **The script re-opens and re-validates its own output** before exiting
  (:func:`verify_output`), and then checks the collection against the manuals'
  own ``JSON Schema`` marker counts (:func:`verify_collection`) — a wrong-but-
  plausible count is worse than a crash.  Either failure is a non-zero exit.
* **Every row carries a Chinese annotation when one exists.**  The registry is an
  **API catalogue**: the manuals' Chinese and English sections document the *same*
  endpoints, so the section a row was read from says nothing about who can use it.
  What matters is that every API can be found and understood by a Chinese-speaking
  user and by the LLM, so each row carries ``title`` (the index cell's markdown
  link, unwrapped) and ``description`` (``name_zh + "：" + description_zh``, or
  ``name_zh`` alone, or ``null``), with the glossary's own ``source`` preserved as
  ``metadata_json.annotation_source``.  Nothing is invented: an absent or
  unmatched title emits ``null``, and :func:`verify_annotations` fails the run when
  a *present, complete* glossary silently matched almost nothing — the same
  silent-zero lesson as ``index_rows=0``.

Usage:  ``.venv\\Scripts\\python.exe docs\\api-registry\\extract_interfaces.py``
No third-party dependencies.  Python 3.12, full annotations.
"""

import bisect
import collections
import json
import os
import re
import sys
from collections.abc import Mapping

# The pipeline runs from ``docs/api-registry``; the backend package root has to be
# importable for ``app.core.constants``.  Importing the constants (rather than
# copying the word lists) is the whole point — see the module docstring.
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
_BACKEND = os.path.join(_REPO, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.core.constants import (  # noqa: E402  (path set above)
    CAPABILITY_DOMAIN_VALUES,
    CAPABILITY_FEATURE_DOMAIN,
    CAPABILITY_FEATURE_VALUES,
    MIDAS_PRODUCT_SCOPE_VALUES,
    MidasProductScope,
)
from app.core.midas_config import MidasProduct  # noqa: E402  (path set above)

# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------
MAPI_ROOT = r"G:\MAPI"
INVENTORY_PATH = os.path.join(MAPI_ROOT, "tools", "inventory.json")
MANUAL_PATHS: dict[str, str] = {
    "gen": os.path.join(MAPI_ROOT, "docs", "midas Gen API 专用手册.md"),
    "civilnx": os.path.join(MAPI_ROOT, "docs", "midas Civil NX API 专用手册.md"),
    "designer": os.path.join(MAPI_ROOT, "docs", "midas Civil Designer API 专用手册.md"),
}
CHAPTER_DIR = os.path.join(_REPO, "MIDAS-API-main", "docs", "manual")

OUT_JSON = os.path.join(_HERE, "interfaces.json")
OUT_REPORT = os.path.join(_HERE, "EXTRACTION_REPORT.md")

#: The Chinese annotation glossary (see the module docstring).  It is **curated
#: data owned by another task**, so it is read if it is there and skipped if it is
#: not — :func:`load_title_zh` never raises and never blocks the run.
TITLE_ZH_PATH = os.path.join(_HERE, "title_zh.json")

# ---------------------------------------------------------------------------
# closed sets this pipeline may emit
# ---------------------------------------------------------------------------
#: ``inventory.json`` key -> MIDAS product.  ``adapter_code`` is derived as
#: ``f"midas_{product.value}"`` (``MidasConnection.to_registry_row``), which is why
#: Civil Designer's adapter code is ``midas_cdn`` — the product's **URL segment**
#: is ``cdn`` even though :class:`app.core.constants.MidasProductScope` labels the
#: product ``designer`` for humans.
INVENTORY_PRODUCT: dict[str, MidasProduct] = {
    "gen": MidasProduct.GEN,
    "civilnx": MidasProduct.CIVIL,
    "designer": MidasProduct.DESIGNER,
}
ADAPTER_CODES: dict[str, str] = {
    key: f"midas_{product.value}" for key, product in INVENTORY_PRODUCT.items()
}

#: Emitted ``product_scope``.  Deliberately a single value: see module docstring.
EMITTED_PRODUCT_SCOPE: str = MidasProductScope.UNKNOWN.value

#: The 27 ``feature`` values, read straight out of ``app/core/constants.py``.
FEATURE_VALUES: tuple[str, ...] = tuple(CAPABILITY_FEATURE_VALUES)
FEATURE_SET: frozenset[str] = frozenset(FEATURE_VALUES)
DOMAIN_SET: frozenset[str] = frozenset(CAPABILITY_DOMAIN_VALUES)

#: The three-layer hierarchy is closed and total.  Failing loudly here beats
#: emitting a ``feature`` the database CHECK would reject one row at a time.
assert len(FEATURE_VALUES) == 27, f"expected 27 features, got {len(FEATURE_VALUES)}"
assert set(CAPABILITY_FEATURE_DOMAIN) == FEATURE_SET, "feature->domain is not total"
assert set(CAPABILITY_FEATURE_DOMAIN.values()) <= DOMAIN_SET, "domain outside the closed set"
assert EMITTED_PRODUCT_SCOPE in MIDAS_PRODUCT_SCOPE_VALUES
assert len(ADAPTER_CODES) == 3

# ---------------------------------------------------------------------------
# endpoint families and request wrappers
# ---------------------------------------------------------------------------
#: Copied from ``app/adapters/midas_gen/adapter.py``'s ``_ENDPOINT_FAMILIES`` so
#: this pipeline and the adapter agree on what a family *is*.
ENDPOINT_FAMILIES: tuple[str, ...] = ("db", "doc", "ope", "view", "post", "info", "design")

WRAPPER_ASSIGN = "Assign"
WRAPPER_ARGUMENT = "Argument"

#: Families whose request body is an ``Argument`` object rather than an ``Assign``
#: map (《MIDAS API 对接规范》§3.1).  ``/RATING/**`` is included even though the
#: adapter's family set does not list it, because the manual documents it.
ARGUMENT_FAMILIES: frozenset[str] = frozenset(
    {"doc", "post", "ope", "view", "info", "design", "rating"}
)

#: Families that are neither ``Assign`` nor ``Argument`` are reported through the
#: ``unknown_families`` counter rather than being given a wrapper.

# ---------------------------------------------------------------------------
# the operation mapping (one table, reviewable)
# ---------------------------------------------------------------------------
#: Title substrings that make a ``POST`` an *execution* rather than a *creation*.
EXECUTE_TITLE_TOKENS: tuple[str, ...] = (
    "perform",
    "check",
    "anal",
    "run",
    "calculate",
    "calc",
    "generate",
    "execute",
    "evaluate",
    "divide",
    "auto-mesh",
    "automesh",
    "optimiz",
    "rating",
    "design",
    "report",
    "capture",
    "screenshot",
    "export",
    "import",
    "update",
)

#: Title substrings that make a ``POST`` a *query* of a result table.  Checked
#: **before** :data:`EXECUTE_TITLE_TOKENS` because the manual has both
#: "RC Beam Design Perform" and "Beam Force - Analysis Result Table", and the
#: table reading is the correct one for the latter.
QUERY_TITLE_TOKENS: tuple[str, ...] = (
    "table",
    "result",
    "graph",
    "diagram",
    "summary",
    "response",
    "return",
    "取值",
    "返回值",
    "表格",
    "结果",
)

#: ``method -> operation`` for everything the title does not override.
METHOD_OPERATION: dict[str, str] = {
    "GET": "read",
    "PUT": "update",
    "DELETE": "delete",
    "POST": "create",
    "PATCH": "update",
}

#: Methods that carry a request body.  ``request_schema_json`` is emitted only for
#: these: a ``GET``/``DELETE`` row pointing at the resource's ``Assign`` body would
#: invite a caller to send one.  The schema is per-URI, so the ``POST`` row of the
#: same URI still carries it.
BODY_METHODS: frozenset[str] = frozenset({"POST", "PUT", "PATCH"})

#: Canonical method order, so a URI's rows come out in a stable, reviewable order.
METHOD_ORDER: dict[str, int] = {"GET": 0, "POST": 1, "PUT": 2, "PATCH": 3, "DELETE": 4}

# ---------------------------------------------------------------------------
# feature attribution: the 27 chapter files own the vocabulary
# ---------------------------------------------------------------------------
#: ``MIDAS-API-main/docs/manual/<stem>`` -> ``feature``, spelled out rather than
#: slugified.
#:
#: The filenames are camelCase (``18_POST_PreProcess``) while the closed set in
#: :mod:`app.core.constants` is word-separated lower case (``post_pre_process``), so
#: a slug rule has to know that a lower-case letter followed by an upper-case one
#: starts a new word — and that a *digit* followed by an upper-case one does **not**
#: (``AIKSRC2K`` must stay ``aiksrc2k``, not become ``aiksrc2_k``).  A rule that
#: happens to be right today is exactly the kind of implicit convention this
#: pipeline should not depend on, so the 27 pairs are written out and the value set
#: is asserted against the closed set below.
CHAPTER_FEATURE: dict[str, str] = {
    "01_DOC": "doc",
    "02_DB_Project_Structure": "db_project_structure",
    "03_DB_Node_Element": "db_node_element",
    "04_DB_Properties": "db_properties",
    "05_DB_Boundary": "db_boundary",
    "06_DB_Static_Loads": "db_static_loads",
    "07_DB_Temperature_Prestress": "db_temperature_prestress",
    "08_DB_Moving_Loads": "db_moving_loads",
    "09_DB_Dynamic_Loads": "db_dynamic_loads",
    "10_DB_Construction_Stage": "db_construction_stage",
    "11_DB_Settlement_Misc_Loads": "db_settlement_misc_loads",
    "12_DB_Analysis_Control": "db_analysis_control",
    "13_DB_Load_Combinations": "db_load_combinations",
    "14_DB_Pushover": "db_pushover",
    "15_OPE": "ope",
    "16_VIEW": "view",
    "17_DB_Bridge": "db_bridge",
    "18_POST_PreProcess": "post_pre_process",
    "19_POST_AnalysisResult_1": "post_analysis_result_1",
    "20_POST_AnalysisResult_2": "post_analysis_result_2",
    "21_POST_StoryTables": "post_story_tables",
    "22_POST_TH_HY_Pushover": "post_th_hy_pushover",
    "23_POST_Design": "post_design",
    "24_DB_Design": "db_design",
    "25_Design_Steel_KDS41302022": "design_steel_kds41302022",
    "26_Design_RC_KDS41202022": "design_rc_kds41202022",
    "27_Design_SRC_AIKSRC2K": "design_src_aiksrc2k",
}

#: A renamed or added chapter must fail here rather than mis-classify silently.
assert set(CHAPTER_FEATURE.values()) == FEATURE_SET, (
    "CHAPTER_FEATURE no longer matches CAPABILITY_FEATURE_VALUES: "
    f"missing={sorted(FEATURE_SET - set(CHAPTER_FEATURE.values()))} "
    f"extra={sorted(set(CHAPTER_FEATURE.values()) - FEATURE_SET)}"
)

#: Fallback chapter-name -> feature, for a manual whose chapter column does not
#: resolve through the URI map.  Keys are :func:`normalise_heading`-normalised.
#:
#: The Gen manual's Chinese backbone files by topic (``JSON数据手册 / Load``) rather
#: than by chapter, so its 13 categories are coarser than the 27 features and
#: several collapse onto one.  Where a category holds more than one topic
#: (``Load`` covers static, temperature, prestress, moving, dynamic, construction
#: stage and settlement), the sub-chapter is mapped explicitly and the bare
#: category is the last resort — a mapping decision, not a loss of data.
GEN_ZH_CHAPTER_FEATURE: dict[str, str] = {
    "doc control": "doc",
    "view": "view",
    "structure": "db_project_structure",
    "node-element": "db_node_element",
    "properties": "db_properties",
    "boundary": "db_boundary",
    "load": "db_static_loads",
    "analysis": "db_analysis_control",
    "pushover": "db_pushover",
    "results": "post_analysis_result_1",
    "design": "db_design",
    # --- the ``Load`` category's sub-chapters, most specific first ---
    "json数据手册 / temperature": "db_temperature_prestress",
    "json数据手册 / prestress": "db_temperature_prestress",
    "json数据手册 / moving": "db_moving_loads",
    "json数据手册 / dynamic": "db_dynamic_loads",
    "json数据手册 / construction": "db_construction_stage",
    "json数据手册 / heat of hydration": "db_construction_stage",
    "json数据手册 / settlement": "db_settlement_misc_loads",
    "json数据手册 / results": "post_analysis_result_1",
    "json数据手册 / seismic perform.": "db_design",
    "json数据手册 / smart report": "post_design",
    # Smart Report is a reporting front-end over result tables; the design-result
    # chapter is the honest neighbour, and inventing a 28th feature would break
    # the closed set the frontend menu is built from.
    "smart report": "post_design",
    "seismic perform.": "db_design",
}

#: Same, for the Gen manual's two English sections (33 + 8 partitions).
GEN_EN_CHAPTER_FEATURE: dict[str, str] = {
    "doc": "doc",
    "project": "db_project_structure",
    "view": "view",
    "structure": "db_project_structure",
    "node/element": "db_node_element",
    "properties": "db_properties",
    "boundary": "db_boundary",
    "static loads": "db_static_loads",
    "temperature loads": "db_temperature_prestress",
    "prestress loads": "db_temperature_prestress",
    "moving loads": "db_moving_loads",
    "dynamic loads": "db_dynamic_loads",
    "construction stage loads": "db_construction_stage",
    # No canonical hydration chapter exists; hydration is a construction-stage load.
    "heat of hydration loads": "db_construction_stage",
    "settlement loads": "db_settlement_misc_loads",
    "miscellaneous loads": "db_settlement_misc_loads",
    "grid model analysis loads": "db_analysis_control",
    "analysis": "db_analysis_control",
    "analysis results": "post_analysis_result_1",
    "bridge specialization results": "db_bridge",
    "time history analysis results": "post_th_hy_pushover",
    "heat of hydration results": "post_th_hy_pushover",
    "pushover": "db_pushover",
    "design": "db_design",
    "ope": "ope",
    "pre-process table": "post_pre_process",
    "analysis result table": "post_analysis_result_2",
    "analysis story table": "post_story_tables",
    "time history result table": "post_th_hy_pushover",
    "heat of hydration result table": "post_th_hy_pushover",
    "time history text": "post_th_hy_pushover",
    "pushover text": "post_th_hy_pushover",
    "design/sect : section for design": "db_design",
    "design/psc/aashto-lrfd24": "db_design",
    "design/rc/drc : rc design code": "design_rc_kds41202022",
    "design/rc/kds-41-20-2022": "design_rc_kds41202022",
    "design/src/aik-src2k": "design_src_aiksrc2k",
    "design/steel/kds-41-30-2022": "design_steel_kds41302022",
    "rating/psc/aashto-lrfr19": "db_design",
    # The manual's catch-all section; its entries are design rebar/material data.
    "其他": "db_design",
}

#: Civil NX chapters.  The bare keys are the ``大类`` segment; the ``大类 / 子分组``
#: keys split the two categories that span several of the 27 chapters.
CIVILNX_CHAPTER_FEATURE: dict[str, str] = {
    "文件documents": "doc",
    "项目project": "db_project_structure",
    "视图view": "view",
    "结构structure": "db_project_structure",
    "节点/单元node/element": "db_node_element",
    "特性properties": "db_properties",
    "边界boundary": "db_boundary",
    "荷载load": "db_static_loads",
    "分析analysis": "db_analysis_control",
    "结果results": "post_analysis_result_1",
    "pushover": "db_pushover",
    "设计design": "db_design",
    # The five Collaboration endpoints are document interchange; no canonical
    # chapter covers them and ``doc`` is the honest neighbour.
    "协同collaboration": "doc",
    "工具apps": "post_design",
    # --- sub-chapters of the two categories that span several features ---
    "边界boundary / 高级advanced": "db_boundary",
    "荷载load / 静力荷载static loads": "db_static_loads",
    "荷载load / 温度temperature": "db_temperature_prestress",
    "荷载load / 预应力prestress": "db_temperature_prestress",
    "荷载load / 移动荷载moving loads": "db_moving_loads",
    "荷载load / 动力荷载dynamic loads": "db_dynamic_loads",
    "荷载load / 施工阶段construction stage": "db_construction_stage",
    "荷载load / 水化热heat of hydration": "db_construction_stage",
    "荷载load / 支座沉降settlement": "db_settlement_misc_loads",
    "荷载load / 荷载组合load combination": "db_load_combinations",
    "结果results / 荷载组合load combination": "db_load_combinations",
    "结果results / 结果表格result table": "post_analysis_result_2",
    "结果results / 详细结果detail result": "post_analysis_result_2",
    "结果results / 层结果story": "post_story_tables",
    "结果results / 时程分析time history": "post_th_hy_pushover",
    "结果results / 水化热heat of hydration": "post_th_hy_pushover",
    "分析analysis / 分析控制analysis control": "db_analysis_control",
    "设计design / rc design": "design_rc_kds41202022",
}

#: Designer chapters.
DESIGNER_CHAPTER_FEATURE: dict[str, str] = {
    "doc 文档": "doc",
    "db 数据库": "db_project_structure",
    "oprt 操作": "ope",
    "view 视图": "view",
    "post 后处理": "post_design",
}

#: Last resort when a chapter is in none of the tables above.  Ordered
#: ``(substring, feature)`` pairs; the first hit wins.  A miss leaves ``feature``
#: ``None`` (the column is nullable) and is reported.
FEATURE_FALLBACK: tuple[tuple[str, str], ...] = (
    ("doc", "doc"),
    ("project", "db_project_structure"),
    ("structure", "db_project_structure"),
    ("node", "db_node_element"),
    ("element", "db_node_element"),
    ("propert", "db_properties"),
    ("material", "db_properties"),
    ("section", "db_properties"),
    ("boundary", "db_boundary"),
    ("support", "db_boundary"),
    ("spring", "db_boundary"),
    ("static load", "db_static_loads"),
    ("temperature", "db_temperature_prestress"),
    ("prestress", "db_temperature_prestress"),
    ("tendon", "db_temperature_prestress"),
    ("moving load", "db_moving_loads"),
    ("dynamic load", "db_dynamic_loads"),
    ("construction", "db_construction_stage"),
    ("settlement", "db_settlement_misc_loads"),
    ("misc", "db_settlement_misc_loads"),
    ("analysis control", "db_analysis_control"),
    ("analysis", "db_analysis_control"),
    ("combination", "db_load_combinations"),
    ("pushover", "db_pushover"),
    ("ope", "ope"),
    ("view", "view"),
    ("bridge", "db_bridge"),
    ("pre-process", "post_pre_process"),
    ("story", "post_story_tables"),
    ("time history", "post_th_hy_pushover"),
    ("result", "post_analysis_result_2"),
    ("design", "post_design"),
)

# ---------------------------------------------------------------------------
# manual structure (measured by reading the files; see report §1)
# ---------------------------------------------------------------------------
#: The index-table header.  All three manuals carry it **verbatim**, which is what
#: makes the tables usable as the primary source.
INDEX_HEADER = "| # | 接口代码 | 接口名称 | URL | 方法 | 所在章节 |"

#: ``##`` sections that hold interface bodies, per manual.  Everything else
#: (preface, 目录, 接口总索引, the tutorial/API-primer chapters) is prose.
JSON_REGIONS: dict[str, tuple[str, ...]] = {
    "gen": ("JSON数据手册", "英文数据手册（索引接口）", "英文数据手册（未编入索引）"),
    "civilnx": (
        "文件Documents",
        "项目Project",
        "视图View",
        "结构Structure",
        "节点/单元Node/Element",
        "特性Properties",
        "边界Boundary",
        "荷载Load",
        "分析Analysis",
        "结果Results",
        "Pushover",
        "设计Design",
        "协同Collaboration",
        "工具Apps",
    ),
    "designer": ("DOC 文档", "DB 数据库", "OPRT 操作", "VIEW 视图", "POST 后处理"),
}

#: ``##`` sections whose index rows describe interfaces but whose *bodies* are not
#: the authoritative ones.  Gen's Chinese backbone and its English indexed section
#: overlap heavily, so a URI claimed by both is attributed to the section listed
#: first here — the more complete English definition.
SECTION_PRIORITY: dict[str, tuple[str, ...]] = {
    "gen": ("英文数据手册（索引接口）", "JSON数据手册", "英文数据手册（未编入索引）"),
    "civilnx": tuple(JSON_REGIONS["civilnx"]),
    "designer": tuple(JSON_REGIONS["designer"]),
}

#: Mojibake fingerprints observed in the Gen manual (``鎬荤翰`` where ``总纲`` was
#: meant).  Used for **reporting only** — never for repair.
MOJIBAKE_MARKERS: tuple[str, ...] = ("鎬荤翰", "涓", "鏂", "鐨", "鍜", "锛")

#: Zero-width space.  The Gen manual writes ``** {base url} + db/CNLD**\u200b``
#: while the same manual's next entry has no space and no ZWSP; both are stripped
#: before any matching happens.
ZWSP = "\u200b"
REPLACEMENT = "\ufffd"

# ---------------------------------------------------------------------------
# regexes
# ---------------------------------------------------------------------------
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_INDEX_ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|")
_CODE_RE = re.compile(r"\[([A-Za-z][A-Za-z0-9_\-]*)\]")
_METHOD_RE = re.compile(r"\b(GET|POST|PUT|DELETE|PATCH)\b", re.I)
_METHOD_SPLIT_RE = re.compile(r"[/,、|]")
_BASE_PREFIX_RE = re.compile(r"^\{?\s*base\s*url\s*\}?\s*\+?", re.I)
_BOLD_URI_RE = re.compile(
    r"^\*\*?\s*(?:\{?\s*base\s*url\s*\}?\s*\+\s*)?/?([A-Za-z0-9_./-]+)", re.I
)
_URI_SHAPE_RE = re.compile(r"([A-Za-z][A-Za-z0-9_-]*(?:/[A-Za-z0-9_.-]+)+)")
#: A one-cell table row used by the Gen English sections to state an ``Input URI``,
#: e.g. ``| **/DESIGN/RC/KDS-41-20-2022/CMFT** |`` or ``| **{base url} +** |``.
_TABLE_CELL_RE = re.compile(r"^\|\s*(.*?)\s*\|\s*$")
#: ``{base url}`` written with or without the braces and with any spacing.
_BASE_TOKEN_RE = re.compile(r"\{?\s*base\s*url\s*\}?", re.I)
_CHAPTER_ENDPOINT_RE = re.compile(r"^##\s+(?:\d+\.\s+)?`?(/[A-Za-z0-9_./-]+)`?")
#: Leading markdown heading hashes and spaces.  :func:`normalise_heading` drops the
#: emphasis (``**``) but not the ``#``s, so a block marker written as a heading
#: normalised to ``"##### json schema"`` — which no ``==`` test matched.  That is
#: exactly why the Gen manual's 619 English ``JSON Schema`` headings were invisible
#: to the collector while its 2 bold-paragraph ones were not.
_HEADING_HASHES_RE = re.compile(r"^[#\s]+")
#: ``"TABLE_TYPE": "BEAMFORCE"`` / ``"TABLE_NAME": "BEAMFORCE"`` — the literal a
#: result-table entry states about itself.
_TABLE_TYPE_LITERAL_RE = re.compile(
    r'"(?:TABLE_TYPE|TABLE_NAME)"\s*:\s*"([A-Za-z][A-Za-z0-9_]*)"'
)
#: ``| 2 | Result Table Type • "BEAMDESIGNFORCES" | "TABLE_TYPE" | … |`` — the
#: English sections' ``Specifications`` table, which names the literal explicitly.
_TABLE_TYPE_SPEC_RE = re.compile(r'Result Table Type\s*•\s*"([A-Za-z][A-Za-z0-9_]*)"')
#: JSON Schema *type* names that sit under a ``TABLE_TYPE`` key but are not table
#: types (``"TABLE_TYPE": "string"`` in the English draft-07 blocks).
_TABLE_TYPE_NON_LITERALS: frozenset[str] = frozenset(
    {"string", "object", "array", "number", "integer", "boolean", "null"}
)

#: The markdown link an index table's ``接口名称`` cell holds —
#: ``[Main Control Data](#main-control-data)``.  This is the **exact** expression
#: ``title_zh.json`` used to key its entries (the glossary's own ``$comment``), so
#: the lookup has to unwrap with it and nothing else: a different rule matches
#: nothing, and it does so silently.
_LINK_TITLE_RE = re.compile(r"\[(.*?)\]\([^)]*\)\s*$")

#: Em-dash family used by the manuals for "no value".
DASHES: frozenset[str] = frozenset({"—", "–", "-", ""})

#: Headings that belong to an entry's *body*, never to the entry's own title.  The
#: Gen manual's English sections and Civil NX write ``##### Input URI`` /
#: ``##### JSON Schema`` as headings, so without this every claim's title resolved
#: to "Input URI" — which is what the previous revision emitted as ``body_title``
#: for 271 Civil NX rows.
BLOCK_MARKER_KEYS: frozenset[str] = frozenset(
    {
        "json schema",
        "input data form",
        "接口url",
        "请求示例",
        "examples",
        "example",
        "specifications",
        "parameters",
        "input json format",
    }
)

#: Source quality order for :meth:`ManualIndex.best_body`.  A draft-07 JSON Schema
#: beats the Chinese backbone's ``Input Data Form`` (``__DESC__``/``__TYPE__``,
#: which is not draft-07), which beats a request-body example, which beats a bare
#: JSON fence found by position alone.
SCHEMA_SOURCE_RANK: dict[str, int] = {
    "json_schema": 0,
    "input_data_form": 1,
    "request_example": 2,
    "example": 3,
}

#: A ``##`` section that states ``JSON Schema`` markers must have most of them
#: attached.  This is the guard for the silent-zero class of failure: the collector
#: once emitted ``index_rows=0`` with ``anomalies=0``, and later attached 2 schemas
#: against the English sections' 619 ``JSON Schema`` markers — a count that is wrong
#: without looking wrong, which is worse than a crash.  The floor is below 1.0
#: because an entry may genuinely state a marker with no ``Input URI`` to attach it
#: to; it still fails loudly when a whole section goes missing.
SCHEMA_ATTACHMENT_FLOOR: float = 0.75
#: Sections with fewer markers than this are checked for "at least one attached"
#: rather than against the floor: two entries without a URI in a three-entry
#: section are not evidence of a broken collector.
SCHEMA_ATTACHMENT_MIN_HEADINGS: int = 8

#: The full-width colon that joins the Chinese name to its description.  A
#: half-width ``:`` would be a different string, and the annotation is meant to be
#: read as one Chinese sentence (``主控数据：分析主控参数……``).
ANNOTATION_JOIN = "："

#: The glossary's own ``source`` vocabulary (``title_zh.json``'s ``$comment``:
#: ``manual`` = the manual ships Chinese, ``glossary`` = this file supplied it).
#: Reported, never validated: the vocabulary belongs to the glossary, and inventing
#: a failure for a value it adds would make this pipeline its gatekeeper.
ANNOTATION_SOURCES: tuple[str, ...] = ("manual", "glossary")

#: Floor for the annotation self-check, as a share of the rows **and** of the
#: distinct titles.  It is deliberately low (half): a complete glossary should
#: match nearly everything, so a shortfall this large means the lookup rule and the
#: glossary disagree — the ``index_rows=0`` failure in a new place, where the count
#: is wrong without looking wrong.  A *draft* glossary (fewer entries than its own
#: ``meta.titles_total``) is reported and exempt: it is incomplete, not broken.
ANNOTATION_COVERAGE_FLOOR: float = 0.5


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def read_lines(path: str) -> tuple[list[str], int, int, int]:
    """Stream *path*, returning ``(lines, replacements, mojibake, zero_width)``.

    ``errors="replace"`` is mandatory: the Gen manual contains mojibake, so a
    strict decode would abort on a file that is otherwise usable.  U+200B is
    stripped from every line (the Gen manual writes it inside ``Input URI``
    lines), and its occurrence count is reported rather than swallowed.
    """
    replaced = 0
    mojibake = 0
    zero_width = 0
    lines: list[str] = []
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            if REPLACEMENT in raw:
                replaced += 1
            if any(marker in raw for marker in MOJIBAKE_MARKERS):
                mojibake += 1
            if ZWSP in raw:
                zero_width += 1
            line = raw.rstrip("\n")
            if line.endswith("\r"):
                line = line[:-1]
            lines.append(line.replace(ZWSP, ""))
    return lines, replaced, mojibake, zero_width


def normalise_heading(text: str) -> str:
    """Lower-case, markdown-free heading text used as a mapping key."""
    value = text.replace("*", "").replace("`", "").replace("_", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip().lower()


def marker_key(text: str) -> str:
    """Block-marker name with **all** markdown syntax removed.

    ``"##### **JSON Schema**"`` -> ``"json schema"``;
    ``"**Input Data Form**"`` -> ``"input data form"``;
    ``"#### 请求示例"`` -> ``"请求示例"``.

    The manuals write the same marker three ways — a bold paragraph, a level-5
    heading, and (Civil NX) a level-5 heading without emphasis — so the comparison
    has to happen on the marker's *name*, never on the raw line.  The Gen manual
    writes ``##### **Input URI**`` 644 times and ``**Input URI**`` 209 times; only
    the second form was recognised before, which is why the English sections
    contributed 2 body claims against 619 ``JSON Schema`` markers.
    """
    value = _HEADING_HASHES_RE.sub("", normalise_heading(text))
    return re.sub(r"\s+", " ", value).strip()


def is_block_marker(text: str) -> bool:
    """True when *text* names an entry's body block rather than an entry title.

    Covers the four spellings the three manuals use for the same blocks: the bold
    paragraph, the plain heading, the emphasised heading, and the Civil Designer
    manual's Chinese ``#### 接口URL`` / ``#### 请求示例`` / ``#### Get请求参数``.
    """
    key = marker_key(text)
    if not key:
        return False
    if key in BLOCK_MARKER_KEYS:
        return True
    if key.endswith("请求参数") or key.endswith("返回值"):
        return True
    return (
        key.startswith("input uri")
        or key.startswith("active method")
        or key.startswith("active program")
        or key.startswith("request example")
        or key.startswith("response example")
        or key.startswith("支持的方法")
    )


def uri_marker_form(line: str) -> str:
    """How an ``Input URI`` marker is written, as ``"<shape> <emphasis>"``.

    The three manuals use three spellings for the same block — ``**Input URI**``
    (a bold paragraph), ``##### Input URI`` (a plain heading, Civil NX) and
    ``##### **Input URI**`` (an emphasised heading, both Gen English sections) —
    and the collector has to read all three.  The report states which ones were
    actually present rather than asserting a count a revised manual could falsify.
    """
    shape = "heading" if _HEADING_RE.match(line) else "bold"
    emphasis = "emphasised" if "*" in line else "plain"
    return f"{shape} {emphasis}"


def title_key(text: str) -> str:
    """Normalised entry title, for matching an index row to a body entry.

    The index table writes a title as a link (``[New Project](#new-project-1)``)
    while the body writes it as a heading (``#### New Project``), and the body
    sometimes prefixes the interface code (``###### [BEAMFORCE]Beam Force``), so
    both spellings have to fold to one key before they can be compared.

    The anchor is cut at the **last** ``](`` rather than with a bracket-matching
    regex: the manuals nest brackets in the link text
    (``[新项目[NEW]New Project](#…)``, ``[[BEAMFORCE]Beam Force](#…)``), which makes
    a naive ``\\[([^\\]]*)\\]\\([^)]*\\)`` match nothing at all and leaves the anchor's
    own words in the key.
    """
    value = text.strip()
    cut = value.rfind("](")
    if cut != -1 and value.endswith(")"):
        value = value[:cut]
    if value.startswith("["):
        value = value[1:]
    value = _CODE_RE.sub(" ", value)
    return _SLUG_RE.sub("_", value.lower()).strip("_")


def slugify(text: str, *, limit: int = 64) -> str:
    """``"KDS-41-20-2022"`` -> ``"kds_41_20_2022"``; ``"co_t"`` -> ``"co_t"``."""
    value = _SLUG_RE.sub("_", text.lower()).strip("_")
    if len(value) > limit:
        value = value[:limit].rstrip("_")
    return value or "unnamed"


def canonical_uri(raw: str | None) -> str | None:
    """Normalise a manual/inventory URI to ``/family/rest`` in lower case.

    Handles every spelling the manuals use: ``doc/new``, ``/db/REBB``,
    ``DB/REBB``, ``{base url} + db/NODE``, ``{base url} + /DOC/OPEN``,
    ``/DESIGN/RC/KDS-41-20-2022/TABLE``.  Returns ``None`` when nothing
    URI-shaped survives.
    """
    if not raw:
        return None
    value = raw.strip().strip("*").strip().strip("`").strip().replace(ZWSP, "").strip()
    if value in DASHES:
        return None
    prefix = _BASE_PREFIX_RE.search(value)
    if prefix:
        value = value[prefix.end():]
    match = _URI_SHAPE_RE.search(value)
    if match:
        value = match.group(1)
    value = value.strip().strip("/").strip()
    value = re.sub(r"^info/", "", value, flags=re.I)
    if not value or value in DASHES:
        return None
    return "/" + value.lower()


def uri_family(uri: str | None) -> str | None:
    """First path segment of a canonical URI (``/db/NODE`` -> ``db``)."""
    if not uri:
        return None
    parts = [part for part in uri.split("/") if part]
    return parts[0].lower() if parts else None


def endpoint_of(uri: str) -> str:
    """Canonical endpoint: the **resource segment upper-cased**.

    ``/db/node`` -> ``/db/NODE``; ``/post/TABLE`` -> ``/post/TABLE``;
    ``/design/rc/kds-41-20-2022/rebb`` -> ``/DESIGN/rc/kds-41-20-2022/rebb``.
    """
    parts = uri.split("/")
    if len(parts) >= 2 and parts[1].lower() in ENDPOINT_FAMILIES:
        head = "/" + parts[1]
        tail = [part for part in parts[2:] if part]
        if not tail:
            return head
        return head + "/" + "/".join([tail[0].upper()] + tail[1:])
    return uri


def resource_of(uri: str) -> str:
    """``resource`` column: lower-case last path segment."""
    parts = [part for part in uri.split("/") if part]
    return parts[-1].lower() if parts else ""


def response_root_key_of(uri: str) -> str | None:
    """``/db/co_t`` -> ``CO_T``: the canonical **UPPER CASE** resource segment.

    《MIDAS API 对接规范》§3.6: the GET response root key is always upper case
    even when the path is not.
    """
    family = uri_family(uri)
    if family != "db":
        return None
    parts = [part for part in uri.split("/") if part]
    if len(parts) < 2:
        return None
    return parts[1].upper().replace("-", "_")


def derive_wrapper(uri: str) -> tuple[str | None, str | None, str | None]:
    """Return ``(request_wrapper, response_root_key, unknown_family)``.

    These are **this project's live-verified findings**, not manual content
    (《MIDAS API 对接规范》§3.1–§3.2):

    * ``/db/*`` -> ``Assign`` + the canonical UPPER-case resource segment.
    * ``/doc/*``, ``/ope/*``, ``/view/*``, ``/info/*``, ``/DESIGN/**``,
      ``/RATING/**`` -> ``Argument`` + ``None``.
    * ``/post/*`` and ``/DESIGN/**/TABLE`` -> ``Argument`` + ``None``.  The URI is
      *shared*: ``/post/TABLE`` carries hundreds of result tables selected by
      ``TABLE_TYPE`` inside the ``Argument``, which is why ``interface_code`` has
      to discriminate by table type rather than by URI.
    * anything else -> ``(None, None, family)``; the caller records it.
    """
    family = uri_family(uri)
    if family is None:
        return None, None, "<empty>"
    if family == "db":
        return WRAPPER_ASSIGN, response_root_key_of(uri), None
    if family in ARGUMENT_FAMILIES:
        return WRAPPER_ARGUMENT, None, None
    return None, None, family


def derive_operation(method: str, title: str) -> str:
    """Map ``(method, title)`` to a closed-set operation verb.

    Query beats execute because "… Result Table" would otherwise be read as an
    execution.
    """
    verb = METHOD_OPERATION.get(method.upper(), "execute")
    if method.upper() != "POST":
        return verb
    lowered = title.lower()
    if any(token in lowered for token in QUERY_TITLE_TOKENS):
        return "query"
    if any(token in lowered for token in EXECUTE_TITLE_TOKENS):
        return "execute"
    return verb


def table_type_slug(title: str) -> str:
    """Discriminator slug for the shared ``/post/TABLE`` and ``/DESIGN/**/TABLE``.

    The title is the manual-side carrier of ``TABLE_TYPE`` (e.g.
    ``Beam Force - Analysis Result Table`` -> ``beam_force``), so the slug is
    derived from it after stripping the boilerplate the manual appends.  Without
    this, every result table on one URI would collapse onto one interface code —
    which is exactly what 总纲 裁决 B-3 forbids.
    """
    value = title
    for suffix in (
        " - Analysis Result Table",
        " - Story Result Table",
        " - TH Result Table",
        " - HY Result Table",
        " - Result Display",
        " - Mode Shapes Display",
        " - Moving Tracer Display",
        " - Heat of Hydration Display",
        " Result Table",
        "Result Table",
        " Table",
    ):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
            break
    # ``[RCHK]Rebar Input for Beam Section`` -> the bracket code is already the
    # interface code, so it is dropped from the table discriminator.
    value = _CODE_RE.sub("", value).strip()
    return slugify(value, limit=48)


def needs_table_type(uri: str) -> bool:
    """True for the shared result-table URIs (裁决 B-3).

    Only ``/post/TABLE`` and ``/DESIGN/**/TABLE`` are shared.  ``/post/PM`` is a
    single resource that happens to sit in the same family, so it is **not** given
    a table discriminator — a discriminator that does not discriminate is noise.
    """
    family = uri_family(uri)
    resource = resource_of(uri)
    if family == "post":
        return resource == "table"
    if family == "design":
        return resource == "table"
    return False


# ---------------------------------------------------------------------------
# the Chinese annotation glossary (title_zh.json)
# ---------------------------------------------------------------------------
def _nonempty(value: object) -> str | None:
    """Stripped string, or ``None`` when absent / blank / not a string."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def title_candidates(text: object) -> tuple[str, ...]:
    """Lookup keys for one manual title, most faithful first.

    The index table writes a title as a markdown link
    (``[Main Control Data](#main-control-data)``) while a body heading writes it
    bare, and ``title_zh.json`` keys its entries by the **unwrapped** form using
    ``re.match(r"\\[(.*?)\\]\\([^)]*\\)\\s*$", t)`` — the glossary's own rule, which
    is why it is the first candidate here and nothing else is.  The second
    candidate only tolerates the manual's occasional padding inside the link text
    (``[ Nodal ](#nodal)``); it cannot turn a different spelling into a match.

    The expression is anchored with ``\\s*$``, so a title that merely *contains* a
    link (``See [Nodal](#nodal) for details``) is not a link title and is looked up
    as it stands.  Returns ``()`` when there is nothing usable.
    """
    if not isinstance(text, str):
        return ()
    value = text.strip()
    if not value:
        return ()
    match = _LINK_TITLE_RE.match(value)
    if match is None:
        return (value,)
    raw = match.group(1)
    stripped = raw.strip()
    return (raw,) if raw == stripped else (raw, stripped)


def unwrap_title(text: object) -> str | None:
    """The row's own ``title``: a manual title with its markdown link removed.

    ``[Main Control Data](#main-control-data)`` -> ``Main Control Data``;
    ``梁荷载(单元）[BMLD]Beam Loads`` (already bare) -> itself.  ``None`` when there
    is nothing usable — an entry whose title cell is empty has no title, and
    inventing one would be worse than the gap.
    """
    candidates = title_candidates(text)
    return candidates[-1] if candidates else None


def _empty_glossary(status: str, detail: str) -> dict[str, object]:
    """A glossary that carries no titles, with the reason it carries none."""
    return {
        "status": status,
        "detail": detail,
        "path": None,
        "titles": {},
        "declared_total": None,
        "complete": False,
        "entries_without_name": 0,
    }


def load_title_zh(path: str = TITLE_ZH_PATH) -> dict[str, object]:
    """Read the Chinese annotation glossary; **never raise**, never block the run.

    Returns ``{"status", "detail", "path", "titles", "declared_total", "complete",
    "entries_without_name"}``.  ``status`` is ``"ok"`` / ``"missing"`` /
    ``"malformed"``, and the last two yield an empty glossary: every row is then
    emitted with ``description: null`` and the pipeline continues.  That is
    deliberate — the glossary is curated data owned by another task, and the
    extraction must produce the same row set with or without it.

    The *reason* is carried rather than swallowed so a malformed file cannot be
    mistaken for 「nothing matched」, which is the silent case
    :func:`verify_annotations` exists for.  An entry without a ``name_zh`` is
    unusable (「都没有时留空，**不得**编造」) and is counted, not matched.

    ``complete`` compares the usable entry count against the glossary's own
    ``meta.titles_total``; a file that declares no total is taken at face value, so
    the coverage floor still applies to it.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        return _empty_glossary("missing", f"{path}: not found")
    except (OSError, ValueError) as error:
        return _empty_glossary("malformed", f"{path}: {error}")
    if not isinstance(payload, dict):
        return _empty_glossary("malformed", f"{path}: top level is not an object")
    titles = payload.get("titles")
    if not isinstance(titles, dict):
        return _empty_glossary("malformed", f"{path}: 'titles' is not an object")

    cleaned: dict[str, dict[str, object]] = {}
    without_name = 0
    for key, entry in titles.items():
        if not isinstance(key, str) or not isinstance(entry, dict):
            without_name += 1
            continue
        if _nonempty(entry.get("name_zh")) is None:
            without_name += 1
            continue
        cleaned[key] = dict(entry)

    meta = payload.get("meta")
    declared: int | None = None
    if isinstance(meta, dict) and isinstance(meta.get("titles_total"), int):
        declared = int(meta["titles_total"])
    detail = f"{path}: {len(cleaned)} usable titles"
    if declared is not None:
        detail += f" of {declared} declared"
    return {
        "status": "ok",
        "detail": detail,
        "path": path,
        "titles": cleaned,
        "declared_total": declared,
        "complete": declared is None or len(cleaned) >= declared,
        "entries_without_name": without_name,
    }


def annotation_for(
    title: object, glossary: Mapping[str, Mapping[str, object]]
) -> tuple[str | None, str | None, str | None]:
    """``(description, source, matched key)`` for one manual title.

    ``description`` is ``name_zh + "：" + description_zh`` when both exist,
    ``name_zh`` alone when only that exists, and ``None`` otherwise — **never
    invented**.  ``source`` is the glossary entry's own value (``manual`` /
    ``glossary``), preserved so a reviewer can tell a name the manual ships from one
    the glossary supplied (总纲 §4.2.13: ``capabilities.description`` is the
    annotation's home).  ``matched key`` is the glossary key that actually matched,
    which is not always the row's own ``title`` — see :func:`build_rows`.
    """
    for key in title_candidates(title):
        entry = glossary.get(key)
        # A glossary entry that is not an object is unusable, not fatal: the file is
        # curated elsewhere, and one bad entry must not stop the whole extraction.
        if not isinstance(entry, Mapping):
            continue
        name_zh = _nonempty(entry.get("name_zh"))
        if name_zh is None:
            return None, None, None
        source = _nonempty(entry.get("source"))
        description_zh = _nonempty(entry.get("description_zh"))
        if description_zh is None:
            return name_zh, source, key
        return f"{name_zh}{ANNOTATION_JOIN}{description_zh}", source, key
    return None, None, None


def annotation_report(
    rows: list[dict[str, object]], glossary: Mapping[str, object]
) -> dict[str, object]:
    """Every annotation number the report prints, computed from the rows.

    Two counts matter, and they are not the same count: **rows** annotated (a
    title shared by GET/POST/PUT/DELETE counts four times) and **distinct titles**
    annotated (a whole product's titles can be missing while the row count still
    looks healthy).  ``entries_never_used`` is the third signal — a complete
    glossary whose entries are never looked up means the keys and the rows disagree
    about how a title is spelled, which is the bug this section must make visible.
    """
    titles = glossary.get("titles")
    entries: Mapping[str, object] = titles if isinstance(titles, dict) else {}

    by_source: collections.Counter[str] = collections.Counter()
    distinct: set[str] = set()
    annotated_titles: set[str] = set()
    matched_keys: set[str] = set()
    for row in rows:
        metadata = row.get("metadata_json")
        meta = metadata if isinstance(metadata, dict) else {}
        source = _nonempty(meta.get("annotation_source"))
        if row.get("description") is None:
            by_source["<none>"] += 1
        else:
            by_source[source or "<source missing>"] += 1
        title = _nonempty(row.get("title"))
        if title is not None:
            distinct.add(title)
            if row.get("description") is not None:
                annotated_titles.add(title)
        key = _nonempty(meta.get("annotation_key"))
        if key is not None:
            matched_keys.add(key)

    total = len(rows)
    annotated = total - by_source.get("<none>", 0)
    #: The number of **distinct** titles, not the number of rows carrying one: the
    #: per-title view is what catches a whole product's titles going missing while
    #: the row count still looks healthy.
    title_total = len(distinct)
    rows_by_source: dict[str, int] = {
        name: by_source.get(name, 0) for name in ANNOTATION_SOURCES
    }
    rows_by_source["<none>"] = by_source.get("<none>", 0)
    for name, count in sorted(by_source.items()):
        rows_by_source.setdefault(name, count)
    unused = sorted(str(key) for key in entries if key not in matched_keys)
    unmatched = sorted(title for title in distinct if title not in annotated_titles)
    return {
        "glossary_status": glossary.get("status"),
        "glossary_detail": glossary.get("detail"),
        "glossary_path": glossary.get("path"),
        "glossary_titles": len(entries),
        "glossary_declared_total": glossary.get("declared_total"),
        "glossary_complete": bool(glossary.get("complete")),
        "glossary_entries_without_name": glossary.get("entries_without_name", 0),
        "rows": total,
        "rows_annotated": annotated,
        "rows_annotated_pct": round(100.0 * annotated / total, 1) if total else 0.0,
        "rows_by_source": rows_by_source,
        "distinct_titles": title_total,
        "titles_annotated": len(annotated_titles),
        "titles_annotated_pct": (
            round(100.0 * len(annotated_titles) / title_total, 1) if title_total else 0.0
        ),
        "unmatched_title_examples": unmatched[:40],
        "entries_never_used": len(unused),
        "entries_never_used_examples": unused[:40],
    }


def verify_annotations(report: Mapping[str, object]) -> list[str]:
    """Fail loudly when a *present, complete* glossary silently matched nothing.

    The previous silent-zero lesson applies verbatim here: a glossary of hundreds of
    curated titles plus an unwrap rule that disagrees with the glossary's own would
    emit thousands of ``null`` annotations, and every count in the file would still
    look plausible — the ``index_rows=0`` / ``anomalies=0`` shape, and the 2-schemas-
    against-619-markers shape, in a new place.  So a match rate below
    :data:`ANNOTATION_COVERAGE_FLOOR` is returned as a problem, which makes
    :func:`main` exit non-zero **instead of** writing the report.

    A missing, malformed or still-being-filled glossary is **not** a problem: the
    pipeline must run without it (the module docstring), and the report names the
    state.  Only a complete glossary that matches almost nothing is evidence of a
    bug in this file.
    """
    problems: list[str] = []
    if report.get("glossary_status") != "ok":
        return problems
    if not report.get("glossary_complete"):
        return problems
    rows = int(report.get("rows") or 0)
    annotated = int(report.get("rows_annotated") or 0)
    if rows and annotated < rows * ANNOTATION_COVERAGE_FLOOR:
        problems.append(
            "annotation: the complete glossary "
            f"({report.get('glossary_titles')} titles) annotated only {annotated} of "
            f"{rows} rows ({report.get('rows_annotated_pct')}% < floor "
            f"{ANNOTATION_COVERAGE_FLOOR:.0%}) — the unwrap rule and the glossary's "
            "keys disagree, which is the silent-zero failure this check exists for"
        )
    title_total = int(report.get("distinct_titles") or 0)
    annotated_titles = int(report.get("titles_annotated") or 0)
    if title_total and annotated_titles < title_total * ANNOTATION_COVERAGE_FLOOR:
        problems.append(
            f"annotation: only {annotated_titles} of {title_total} distinct titles "
            f"matched the glossary ({report.get('titles_annotated_pct')}% < floor "
            f"{ANNOTATION_COVERAGE_FLOOR:.0%}); the first unmatched: "
            + ", ".join(
                f"`{title}`"
                for title in list(report.get("unmatched_title_examples") or [])[:5]
            )
        )
    return problems


# ---------------------------------------------------------------------------
# feature attribution from the 27 chapter files
# ---------------------------------------------------------------------------
def load_chapter_feature_map() -> tuple[dict[str, str], dict[str, str]]:
    """Read the 27 chapter files, returning ``(uri -> feature, stem -> feature)``.

    The chapter files define the ``feature`` vocabulary (:data:`CHAPTER_FEATURE`)
    **and** each one lists the URIs it owns (``## 1. `/db/STLD` — Static Load Cases``
    or a TOC table of ``[/db/STLD](#…)`` links), so a URI's chapter is a fact in the
    sources rather than a hand-maintained table here.  This URI map is the *second*
    source of ``feature``: the manual's own ``所在章节`` column wins when it names a
    chapter, because that is the manual's own filing.
    """
    uri_feature: dict[str, str] = {}
    file_feature: dict[str, str] = {}
    for stem, feature in sorted(CHAPTER_FEATURE.items()):
        name = f"{stem}.md"
        path = os.path.join(CHAPTER_DIR, name)
        if not os.path.exists(path):
            raise SystemExit(f"{path}: chapter file named by CHAPTER_FEATURE is missing")
        file_feature[name] = feature
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                line = raw.replace(ZWSP, "")
                match = _CHAPTER_ENDPOINT_RE.match(line)
                candidate = match.group(1) if match else None
                if candidate is None and line.lstrip().startswith("|"):
                    for cell in line.strip().strip("|").split("|"):
                        link = re.search(r"\[`?\s*(/[A-Za-z0-9_./-]+?)\s*`?\]", cell)
                        if link:
                            candidate = link.group(1)
                            break
                if candidate is None:
                    continue
                uri = canonical_uri(candidate)
                if uri and uri not in uri_feature:
                    uri_feature[uri] = feature
    missing = FEATURE_SET - set(file_feature.values())
    if missing:
        raise SystemExit(f"chapter files do not cover every feature: {sorted(missing)}")
    return uri_feature, file_feature


def chapter_table_for(key: str) -> dict[str, str]:
    """The chapter-name -> feature table that applies to a manual."""
    if key == "gen":
        merged = dict(GEN_ZH_CHAPTER_FEATURE)
        merged.update(GEN_EN_CHAPTER_FEATURE)
        return merged
    if key == "civilnx":
        return CIVILNX_CHAPTER_FEATURE
    return DESIGNER_CHAPTER_FEATURE


def feature_for(
    key: str,
    uri: str,
    chapter: str,
    uri_feature: dict[str, str],
) -> tuple[str | None, str]:
    """Resolve ``feature`` for one index row.

    Preference order, and the reason for it:

    1. **The manual's own ``所在章节`` column.**  That is the manual's own filing of
       the endpoint, so it is the most specific statement available.  It is checked
       on the full ``大类 / 子分组`` string and then on the first segment.
    2. **The 27 chapter files' URI list.**  Used when the manual's chapter string is
       not in the table — which is the normal case for the Gen manual, whose Chinese
       backbone files by topic (``JSON数据手册 / Load``) rather than by chapter.
    3. **A keyword rule**, then ``None``.

    Returns ``(feature, provenance)`` where provenance is ``"chapter_table"``,
    ``"chapter_files"``, ``"fallback"`` or ``"unmapped"``.  ``unmapped`` leaves the
    column ``None``, which the schema permits and the report counts.
    """
    parts = [part.strip() for part in chapter.split("/") if part.strip()]
    table = chapter_table_for(key)
    for candidate in (chapter, parts[0] if parts else "", " / ".join(parts)):
        norm = normalise_heading(candidate)
        if norm and norm in table:
            return table[norm], "chapter_table"
    if uri in uri_feature:
        return uri_feature[uri], "chapter_files"
    norm = normalise_heading(chapter)
    for needle, feature in FEATURE_FALLBACK:
        if needle in norm:
            return feature, "fallback"
    return None, "unmapped"


# ---------------------------------------------------------------------------
# the streamed manual index
# ---------------------------------------------------------------------------
def _uri_in_table_cell(cell: str) -> str | None:
    """The path a one-cell ``Input URI`` table states, or ``None``.

    ``| **/DESIGN/RC/KDS-41-20-2022/CMFT** |`` -> that path;
    ``| **{base url} + DESIGN/RC/KDS-41-20-2022/MEMB** |`` -> that path;
    ``| **{base url} +** |`` -> ``None``, because the manual documents the marker
    and then states **no path**.  Returning ``None`` rather than an empty string is
    what lets the caller record "this entry has no URI" instead of inventing the
    base URL as an endpoint.
    """
    value = cell.strip().strip("*").strip().strip("`").strip()
    token = _BASE_TOKEN_RE.search(value)
    if token:
        value = value[token.end():]
    value = value.lstrip("+").strip()
    if not value:
        return None
    match = _URI_SHAPE_RE.search(value)
    if match:
        return match.group(1)
    return None


def _is_bold_uri_line(stripped: str) -> bool:
    """True when *stripped* is the bold ``** {base url} + db/CNLD**`` URI form.

    That form is how the Gen manual's Chinese backbone and Civil NX state the URI
    of an entry: the ``**Input URI**`` / ``##### Input URI`` marker on one line and
    the path on the next.  It is its own claim (see :meth:`ManualIndex._collect_bodies`),
    which is what lets a marker whose next line is this form stay a pure marker
    instead of becoming a second claim for the same URI.
    """
    if not stripped.startswith("**"):
        return False
    lowered = stripped.lower()
    if "base url" not in lowered and "baseurl" not in lowered:
        return False
    return _BOLD_URI_RE.match(stripped) is not None


def _first_in_range(sorted_lines: list[int], start: int, limit: int) -> int | None:
    """The smallest element of *sorted_lines* in ``[start, limit)``, or ``None``.

    The marker lists are built in file order, so this is a binary search rather
    than a scan — with ~850 markers and ~1,400 claims per manual the naive
    product is ~1.2 M iterations for a single lookup pattern.
    """
    position = bisect.bisect_left(sorted_lines, start)
    if position < len(sorted_lines) and sorted_lines[position] < limit:
        return sorted_lines[position]
    return None


class ManualIndex:
    """One streamed pass over a manual.

    Holds headings, fence spans, the index table and the body URI claims.  The
    11.8 MB Gen manual is never held as a single string.
    """

    def __init__(self, key: str, path: str) -> None:
        self.key = key
        self.path = path
        self.lines: list[str] = []
        self.replacements = 0
        self.mojibake_lines = 0
        self.zero_width_lines = 0
        self.headings: list[dict[str, object]] = []
        self.sections: list[tuple[int, str]] = []
        self.fences: list[dict[str, object]] = []
        self.index_rows: list[dict[str, object]] = []
        self.index_anomalies: list[str] = []
        self.index_header_line: int | None = None
        # Marker line indices (0-based), filled by ``_collect_bodies``.  Declared
        # here so a reader never has to know which method populated them.
        self.uri_markers: list[int] = []
        self.method_markers: list[int] = []
        self.schema_markers: list[int] = []
        self.form_markers: list[int] = []
        self.example_markers: list[int] = []
        self._claims: list[dict[str, object]] = []
        self._claims_by_uri: dict[str, list[dict[str, object]]] = {}
        self._entry_headings: list[dict[str, object]] = []
        self._entry_heading_lines: list[int] = []
        self._section_lines: list[int] = []
        self._load()

    # -- loading ---------------------------------------------------------
    def _load(self) -> None:
        self.lines, self.replacements, self.mojibake_lines, self.zero_width_lines = (
            read_lines(self.path)
        )
        fence_char: str | None = None
        fence_open = 0
        fence_lang = ""
        for index, line in enumerate(self.lines):
            match = _FENCE_RE.match(line)
            if match:
                marker = match.group(1)[0]
                if fence_char is None:
                    fence_char = marker
                    fence_open = index
                    fence_lang = line.strip().lstrip("`~").strip().lower()
                elif fence_char == marker:
                    self.fences.append({"open": fence_open, "close": index, "lang": fence_lang})
                    fence_char = None
                continue
            if fence_char is not None:
                continue
            heading = _HEADING_RE.match(line)
            if heading:
                level = len(heading.group(1))
                title = heading.group(2)
                self.headings.append(
                    {"line": index, "level": level, "title": title,
                     "norm": normalise_heading(title)}
                )
                if level == 2:
                    self.sections.append((index, title))
                continue
            if line.startswith("|") and _INDEX_ROW_RE.match(line) and self.index_header_line is None:
                # The header row is three lines above the first data row.
                for probe in range(index - 1, max(index - 4, -1), -1):
                    if self.lines[probe].strip() == INDEX_HEADER:
                        self.index_header_line = probe + 1
                        break
        if fence_char is not None:
            self.fences.append({"open": fence_open, "close": len(self.lines), "lang": fence_lang})
        self._parse_index_table()
        self._collect_bodies()

    def _parse_index_table(self) -> None:
        """Read the ``| # | 接口代码 | … |`` table into row records."""
        if self.index_header_line is None:
            return
        total = len(self.lines)
        cursor = self.index_header_line - 1  # 0-based index of the header row
        # Skip the header row itself, then the ``| --- | --- |`` separator.
        #
        # The header must be skipped **unconditionally**.  The previous version
        # applied the separator test to the header row instead: a header is
        # ``| # | 接口代码 | … |``, whose character set is not a subset of
        # ``"|-: "``, so the test was False, the cursor never advanced, and the
        # ``while`` loop below broke on its first iteration against the header.
        # Result: ``index_rows = 0`` with ``anomalies = 0`` — a silent zero,
        # which is the worst kind, because nothing looked wrong.
        cursor += 1
        if cursor < total and set(self.lines[cursor].strip()) <= set("|-: "):
            cursor += 1
        while cursor < total:
            line = self.lines[cursor]
            if not _INDEX_ROW_RE.match(line):
                break
            body = line.strip()
            if body.startswith("|"):
                body = body[1:]
            if body.endswith("|"):
                body = body[:-1]
            cells = [cell.strip() for cell in body.split("|")]
            if len(cells) != 6:
                self.index_anomalies.append(f"line {cursor + 1}: {len(cells)} cells: {line[:160]}")
                cursor += 1
                continue
            code = cells[1].strip().strip("`").strip()
            url = cells[3].strip().strip("`").strip()
            self.index_rows.append(
                {
                    "line": cursor + 1,
                    "seq": cells[0],
                    "code": None if code in DASHES else code,
                    "title": cells[2],
                    "url_raw": url,
                    "methods_raw": cells[4],
                    "chapter": cells[5],
                    "section": self.section_of(cursor),
                    "uri": canonical_uri(url),
                    "methods": parse_methods(cells[4]),
                }
            )
            cursor += 1

    def _collect_bodies(self) -> None:
        """Collect every body URI claim and the schema material that follows it.

        The markers are matched on :func:`marker_key`, never on the raw line: the
        manuals write ``**Input URI**`` (a bold paragraph), ``##### Input URI`` (a
        heading, Civil NX) and ``##### **Input URI**`` (a heading with emphasis, the
        Gen English sections) for the same block.  Matching only the bold paragraph
        is what made the English sections invisible — 449 ``JSON Schema`` headings
        and 2 claims.
        """
        total = len(self.lines)
        uri_markers: list[int] = []
        method_markers: list[int] = []
        schema_markers: list[int] = []
        form_markers: list[int] = []
        example_markers: list[int] = []
        for index, line in enumerate(self.lines):
            # A cheap substring gate first: the 410k-line Gen manual is scanned
            # once, and normalising every line with three regex passes is the
            # difference between a two-second pass and a twenty-second one.
            lowered = line.lower()
            if not any(
                token in lowered
                for token in (
                    "input uri",
                    "active method",
                    "json schema",
                    "input data form",
                    "request example",
                    "接口url",
                    "支持的方法",
                    "请求示例",
                )
            ):
                continue
            key = marker_key(line)
            if key.startswith("input uri") or key == "接口url":
                uri_markers.append(index)
            elif key.startswith("active method") or key.startswith("支持的方法"):
                method_markers.append(index)
            elif key == "json schema":
                schema_markers.append(index)
            elif key == "input data form":
                form_markers.append(index)
            elif key.startswith("request example") or key == "请求示例":
                example_markers.append(index)
        self.uri_markers = uri_markers
        self.method_markers = method_markers
        self.schema_markers = schema_markers
        self.form_markers = form_markers
        self.example_markers = example_markers
        uri_marker_set = set(uri_markers)
        # Headings that can be an entry's own title, pre-sorted for the
        # "which entry does this claim belong to" lookup.  A block marker is a
        # heading too (``##### **Input URI**``), and must never be a title.
        self._entry_headings = [
            heading
            for heading in self.headings
            if int(heading["level"]) >= 3 and not is_block_marker(str(heading["title"]))
        ]
        self._entry_heading_lines = [
            int(heading["line"]) for heading in self._entry_headings
        ]

        claims: list[dict[str, object]] = []
        for index, line in enumerate(self.lines):
            stripped = line.strip()
            # Same cheap gate as above: only a bold ``base url`` line or an
            # ``Input URI`` marker can start a claim.
            if _is_bold_uri_line(stripped):
                match = _BOLD_URI_RE.match(stripped)
                if match:
                    claims.append(
                        {
                            "line": index + 1,
                            # The entry's title is resolved from the *marker*, so a
                            # claim records where its marker is, not where its URI
                            # text is.
                            "title_line": index,
                            "form": "bold",
                            "raw": match.group(1),
                            "documents_uri": True,
                        }
                    )
                continue
            if index not in uri_marker_set:
                continue
            # The URI may sit in a one-cell table, a fenced block, or the next
            # plain line — the Gen English sections use the table, the Designer
            # manual the bold line.
            probe = index + 1
            while probe < total and not self.lines[probe].strip():
                probe += 1
            if probe >= total:
                continue
            candidate = self.lines[probe].strip()
            if _HEADING_RE.match(self.lines[index]) and _is_bold_uri_line(candidate):
                # A **heading**-form ``Input URI`` marker whose next non-blank line
                # is the bold ``** {base url} + db/CNLD**`` form adds nothing: that
                # line is already collected as its own claim below, with the same
                # URI, the same line and the entry's heading as its title.  Creating
                # a second claim here would only add a claim whose span is empty —
                # the two sit on the same line and truncate each other — which is
                # how the Chinese backbone's ``Input Data Form`` blocks were being
                # cut away before.  The bold-paragraph marker form is left alone so
                # the Chinese backbone's claim set is bit-for-bit what it was.
                continue
            cell = _TABLE_CELL_RE.match(candidate)
            if cell:
                value = _uri_in_table_cell(cell.group(1))
            elif candidate.startswith("```") or candidate.startswith("~~~"):
                value = None
                inner = probe + 1
                while inner < total and not self.lines[inner].strip().startswith(("```", "~~~")):
                    if self.lines[inner].strip():
                        value = self.lines[inner].strip()
                        break
                    inner += 1
            else:
                value = candidate
            # ``None`` means the block *does* state a URI marker but documents no
            # path (the Gen manual writes ``| **{base url} +** |`` for three
            # entries).  That is a claim with no URI, and it is recorded as such so
            # the report can count it instead of silently losing the entry.
            claims.append(
                {
                    "line": probe + 1,
                    "title_line": index,
                    "form": "marker",
                    "raw": value or "",
                    "documents_uri": value is not None,
                }
            )

        for claim in claims:
            start = int(claim["line"]) - 1
            claim["uri"] = canonical_uri(str(claim["raw"]))
            claim["section"] = self.section_of(start)
            # The entry's own title is the last non-block heading before the
            # **marker**, not before the URI line: the Gen English sections and Civil
            # NX write the marker itself as ``##### **Input URI**``, so resolving
            # from the URI line would name every entry "Input URI".
            enclosing = self._enclosing_heading(int(claim["title_line"]))
            claim["title"] = str(enclosing["title"]) if enclosing else ""
            claim["level"] = int(enclosing["level"]) if enclosing else None
            code_match = _CODE_RE.search(str(claim["title"]))
            claim["code"] = code_match.group(1) if code_match else None
        self._claims = claims
        self._assign_schemas()

    def _enclosing_heading(self, line: int) -> dict[str, object] | None:
        """The last heading of level >= 3 before *line* (the entry's own title)."""
        position = bisect.bisect_left(self._entry_heading_lines, line)
        if position == 0:
            return None
        return self._entry_headings[position - 1]

    def _assign_schemas(self) -> None:
        """Attach ``(schema_text, schema_source)`` to every claim, in one pass.

        The span of a claim runs to the next claim or the next *group* heading,
        whichever comes first — deliberately **not** to the next heading of level
        <= 4, because in the Gen manual's Chinese backbone the entries themselves
        are ``#####`` under ``####`` group headings, and stopping at the entry's own
        heading would cut the ``Input Data Form`` block away.

        Within the span the preference order is: a ``JSON Schema`` marker's fence,
        then an ``Input Data Form`` marker's fence, then a ``请求示例`` fence, then
        any bare JSON fence.  The manual documents one body per URI, so this is
        per-claim, not per-method.
        """
        claims = self._claims
        claim_lines = [int(claim["line"]) for claim in claims]
        group_positions = [int(h["line"]) for h in self.headings if int(h["level"]) <= 3]
        fence_opens = [int(fence["open"]) for fence in self.fences]
        marker_sets = (
            (self.schema_markers, "json_schema"),
            (self.form_markers, "input_data_form"),
            (self.example_markers, "request_example"),
        )

        for position, claim in enumerate(claims):
            start = claim_lines[position] - 1
            limit = len(self.lines)
            if position + 1 < len(claims):
                limit = min(limit, claim_lines[position + 1] - 1)
            spot = bisect.bisect_right(group_positions, start)
            if spot < len(group_positions):
                limit = min(limit, group_positions[spot])
            claim["span_end"] = limit

            schema_text: str | None = None
            schema_source: str | None = None
            for markers, tag in marker_sets:
                marker = _first_in_range(markers, start, limit)
                if marker is None:
                    continue
                text = self._fence_text_after(marker, limit, fence_opens)
                if text is not None:
                    schema_text, schema_source = text, tag
                    break
            if schema_text is None:
                text = self._fence_text_after(start, limit, fence_opens)
                if text is not None:
                    schema_text, schema_source = text, "example"
            claim["schema"] = schema_text
            claim["schema_source"] = schema_source
            # ``/post/TABLE`` and ``/DESIGN/**/TABLE`` carry one table per entry on
            # one URI, so the entry has to say which table its schema describes.
            literals = (
                self._table_type_literals(claim)
                if needs_table_type(str(claim["uri"] or ""))
                else []
            )
            claim["table_types"] = literals
            claim["table_type"] = literals[0] if len(literals) == 1 else None

        by_uri: dict[str, list[dict[str, object]]] = collections.defaultdict(list)
        for claim in claims:
            if claim["uri"]:
                by_uri[str(claim["uri"])].append(claim)
        for uri, bucket in by_uri.items():
            bucket.sort(
                key=lambda claim: (
                    self.section_rank(str(claim["section"])),
                    int(claim["line"]),
                )
            )
        self._claims_by_uri = dict(by_uri)

    def _table_type_literals(self, claim: dict[str, object]) -> list[str]:
        """The literal ``TABLE_TYPE`` values the entry's own text states.

        ``/post/TABLE`` and ``/DESIGN/**/TABLE`` are one URI carrying hundreds of
        result tables, selected by ``TABLE_TYPE`` inside the ``Argument``, so the
        schema on such a URI belongs to exactly one table and the extraction has to
        say which.  The English entries state the literal in three places — the
        ``JSON Schema`` block (as ``TABLE_NAME``), the ``Request Examples`` body
        (``"TABLE_TYPE": "BEAMDESIGNFORCES"``) and the ``Specifications`` row
        (``Result Table Type • "BEAMDESIGNFORCES"``) — where the Chinese entries
        state it in a per-entry example plus one generic lookup table.

        A list, not a value: an article that documents several tables at once (the
        story mass/load summaries do) states several literals, and returning one of
        them would be a discriminator that does not discriminate.
        """
        start = int(claim["line"]) - 1
        limit = int(claim["span_end"])
        found: list[str] = []
        for line in self.lines[start:limit]:
            if (
                "TABLE_TYPE" not in line
                and "TABLE_NAME" not in line
                and "Result Table Type" not in line
            ):
                continue
            for match in _TABLE_TYPE_LITERAL_RE.finditer(line):
                value = match.group(1)
                if value.lower() in _TABLE_TYPE_NON_LITERALS or value in found:
                    continue
                found.append(value)
            for match in _TABLE_TYPE_SPEC_RE.finditer(line):
                value = match.group(1)
                if value not in found:
                    found.append(value)
        return found

    def _fence_text_after(self, start: int, limit: int, opens: list[int]) -> str | None:
        """Body of the first JSON-object fence opening in ``(start, limit)``.

        ``opens`` is the pre-sorted list of fence opening indices, so this is a
        binary search rather than a scan — the Gen manual has 2,665 fences and
        thousands of claims, and the naive product is what makes a "streaming"
        parser feel like it read the file twice.
        """
        position = bisect.bisect_right(opens, start)
        if position >= len(opens):
            return None
        fence = self.fences[position]
        opening = int(fence["open"])
        if opening >= limit or int(fence["close"]) > limit:
            return None
        text = "\n".join(self.lines[opening + 1: int(fence["close"])]).strip()
        if text.startswith("{") and is_json_object(text):
            return text
        return None

    # -- queries ---------------------------------------------------------
    def section_of(self, line: int) -> str:
        """Nearest preceding ``##`` heading — the manual's top-level section."""
        if not self._section_lines:
            self._section_lines = [item[0] for item in self.sections]
        position = bisect.bisect_left(self._section_lines, line)
        return self.sections[position - 1][1] if position else ""

    def in_json_region(self, line: int) -> bool:
        """True when *line* sits under one of the manual's interface sections."""
        return self.section_of(line) in JSON_REGIONS.get(self.key, ())

    def section_rank(self, section: str) -> int:
        """Priority of a body section; lower is more authoritative."""
        order = SECTION_PRIORITY.get(self.key, ())
        return order.index(section) if section in order else len(order)

    def index_uris(self) -> set[str]:
        """Every canonical URI the index table mentions."""
        return {str(row["uri"]) for row in self.index_rows if row["uri"]}

    def claims(self) -> list[dict[str, object]]:
        """Every body URI claim, in file order."""
        return list(self._claims)

    def body_uris(self) -> set[str]:
        """Every canonical URI a body claim mentions."""
        return {str(claim["uri"]) for claim in self._claims if claim["uri"]}

    def best_body(
        self, uri: str, title: str | None = None
    ) -> dict[str, object] | None:
        """The most authoritative body claim for *uri*, or ``None``.

        Gen documents the same URI in its Chinese backbone and again in its English
        indexed section, and one URI can carry several logical interfaces
        (``/db/SECT`` is documented 15 times in the English indexed section, once per
        section category; ``/post/TABLE`` once per result table).  The ordering is:

        1. **Source quality** — :data:`SCHEMA_SOURCE_RANK`: the English draft-07
           ``JSON Schema`` beats the Chinese ``Input Data Form``, which beats a
           request-body example, which beats a bare JSON fence found by position
           alone.  Ordering by section first (the previous rule) let an English entry
           that carried only an example displace a Chinese entry that carried a form.
        2. **Title**, when the index row's own title names exactly **one** of the
           candidates.  That is what says which of a URI's several interfaces this
           row is, and it is the discriminator the shared ``/post/TABLE`` and
           ``/DESIGN/**/TABLE`` rows need.  Only a unique match is used: an ambiguous
           title falls through rather than guessing.
        3. **Section authority** — :data:`SECTION_PRIORITY`; Gen's English indexed
           section is the more complete definition of a URI it shares.
        4. **File order**, so the output stays deterministic.
        """
        candidates = self._claims_by_uri.get(uri)
        if not candidates:
            return None
        pool = [claim for claim in candidates if claim.get("schema") is not None]
        if not pool:
            pool = list(candidates)
        if title:
            wanted = title_key(title)
            hits = [claim for claim in pool if title_key(str(claim["title"])) == wanted]
            if len(hits) == 1:
                return hits[0]
        return min(
            pool,
            key=lambda claim: (
                SCHEMA_SOURCE_RANK.get(
                    str(claim.get("schema_source")), len(SCHEMA_SOURCE_RANK)
                ),
                self.section_rank(str(claim["section"])),
                int(claim["line"]),
            ),
        )

    def body_claims(self, uri: str) -> list[dict[str, object]]:
        """Every body claim for *uri*, best first."""
        return list(self._claims_by_uri.get(uri, ()))

    def index_metadata(self) -> dict[str, object]:
        """The index table's own shape, for the report."""
        first = self.index_rows[0]["line"] if self.index_rows else None
        last = self.index_rows[-1]["line"] if self.index_rows else None
        return {
            "header_line": self.index_header_line,
            "first_row_line": first,
            "last_row_line": last,
            "rows": len(self.index_rows),
            "anomalies": self.index_anomalies[:20],
            "anomaly_count": len(self.index_anomalies),
        }


def parse_methods(raw: str) -> list[str]:
    """``"GET / POST / PUT / DELETE"`` and ``"POST,GET,PUT,DELETE"`` -> list."""
    found: list[str] = []
    for part in _METHOD_SPLIT_RE.split(raw):
        value = part.strip().upper()
        if value in METHOD_ORDER and value not in found:
            found.append(value)
    if not found:
        for match in _METHOD_RE.finditer(raw):
            value = match.group(1).upper()
            if value not in found:
                found.append(value)
    return sorted(found, key=lambda item: METHOD_ORDER[item])


def is_json_object(text: str) -> bool:
    """True when *text* parses as a JSON object (the manual's schema blocks do)."""
    stripped = text.strip()
    if not stripped.startswith("{"):
        return False
    try:
        return isinstance(json.loads(stripped), dict)
    except (ValueError, TypeError):
        return False


#: Leading ``/path/CODE`` or ``PATH/CODE`` in an entry title, used to recover the
#: URI of an index row whose ``URL`` cell is ``—``.
_TITLE_PATH_RE = re.compile(r"^\s*/?([A-Za-z][A-Za-z0-9_-]*(?:/[A-Za-z0-9_.-]+){2,})\s*:")


def recover_uri_from_title(title: str) -> str | None:
    """``"DESIGN/RC/KDS-41-20-2022/CMFT : Equivalent …"`` -> that path.

    The Gen manual's unindexed design section leaves the index table's URL cell
    empty for a dozen rows but writes the full resource path as the entry title's
    prefix.  Recovering it from the title is reading the manual, not guessing.
    """
    match = _TITLE_PATH_RE.match(title)
    if not match:
        return None
    return canonical_uri(match.group(1))


def _title_tail(title: str) -> str | None:
    """``"DESIGN/RC/KDS-41-20-2022/MEMB : Member Assignment"`` -> ``"memb"``."""
    head = title.split(":", 1)[0].strip()
    if "/" not in head:
        return None
    tail = head.rsplit("/", 1)[-1].strip()
    return tail.lower() or None


def attach_recovered_uris(index: ManualIndex) -> list[dict[str, object]]:
    """Fill the URI of index rows the manual left blank; return those rows.

    Three recovery routes, all reading the manual rather than guessing:

    1. the title's leading path (``DESIGN/RC/KDS-41-20-2022/CMFT : …``);
    2. the nearest body URI claim in the **same ``##`` section** whose last
       segment matches the row's interface code — the English unindexed section
       writes the URI in a one-cell table (``| **/DESIGN/RC/KDS-41-20-2022/CMFT** |``)
       under a heading that repeats the path;
    3. the same, matched on the title's own path tail.

    A claim is consumed once, so two blank rows can never claim one URI.  When the
    match would be ambiguous (more than one candidate and no code to discriminate),
    the row is left blank on purpose: a wrong endpoint is worse than no endpoint.
    """
    recovered: list[dict[str, object]] = []
    blanks = [row for row in index.index_rows if row["uri"] is None]
    if not blanks:
        return recovered

    claimed: set[str] = {str(row["uri"]) for row in index.index_rows if row["uri"]}
    free_by_section: dict[str, list[dict[str, object]]] = collections.defaultdict(list)
    for claim in index.claims():
        uri = claim["uri"]
        if not uri or not claim.get("documents_uri", True) or str(uri) in claimed:
            continue
        free_by_section[str(claim["section"])].append(claim)
    for bucket in free_by_section.values():
        bucket.sort(key=lambda claim: int(claim["line"]))

    def take(bucket: list[dict[str, object]], wanted: str | None) -> dict[str, object] | None:
        """Consume a candidate whose last segment is *wanted*; unique fallback."""
        if wanted:
            hits = [claim for claim in bucket if str(claim["uri"]).endswith("/" + wanted)]
            if len(hits) == 1:
                bucket.remove(hits[0])
                return hits[0]
            if len(hits) > 1:
                hits.sort(key=lambda claim: int(claim["line"]))
                bucket.remove(hits[0])
                return hits[0]
        if len(bucket) == 1:
            only = bucket[0]
            bucket.remove(only)
            return only
        return None

    for row in blanks:
        title = str(row["title"])
        code = str(row["code"]).lower() if row["code"] else None
        uri = recover_uri_from_title(title)
        source = "title_path"
        if uri is None:
            section = str(row["section"])
            bucket = free_by_section.get(section, [])
            hit = take(bucket, code) or take(bucket, _title_tail(title))
            if hit is not None:
                uri = str(hit["uri"])
                source = "body_claim"
        if uri is None or uri in claimed:
            continue
        row["uri"] = uri
        row["uri_recovered"] = source
        claimed.add(uri)
        recovered.append(
            {
                "line": row["line"],
                "title": title,
                "code": row["code"],
                "chapter": row["chapter"],
                "uri": uri,
                "recovered_from": source,
                "methods": list(row["methods"]),
            }
        )
    return recovered


# ---------------------------------------------------------------------------
# extraction
# ---------------------------------------------------------------------------
def load_inventory() -> dict[str, list[dict[str, object]]]:
    """Read ``inventory.json`` — the endpoint skeleton this pipeline reconciles."""
    with open(INVENTORY_PATH, "r", encoding="utf-8", errors="replace") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise SystemExit(f"{INVENTORY_PATH}: top level is not an object")
    return {str(key): list(value) for key, value in data.items()}


def entry_records(index: ManualIndex) -> list[dict[str, object]]:
    """Turn one manual's index table into entry records.

    The index table is the entry set; a body that the table misses (the Gen
    manual's unindexed design section) is appended from the body stream so the
    row set stays complete.  A body URI is skipped when the index table already
    carries it, so nothing is counted twice.
    """
    records: list[dict[str, object]] = []
    for row in index.index_rows:
        uri = row["uri"]
        if uri is None:
            records.append(
                {
                    "uri": None,
                    "endpoint": None,
                    "code": row["code"],
                    "title": row["title"],
                    "methods": list(row["methods"]),
                    "line": row["line"],
                    "section": row["section"],
                    "chapter": row["chapter"],
                    "source": "index",
                    "indexed": True,
                    "schema": None,
                    "schema_source": None,
                    "table_type": None,
                }
            )
            continue
        body = index.best_body(str(uri), str(row["title"]))
        records.append(
            {
                "uri": str(uri),
                "endpoint": endpoint_of(str(uri)),
                "code": row["code"] or code_from_uri(str(uri)),
                "title": row["title"],
                "methods": list(row["methods"]),
                "line": row["line"],
                "section": row["section"],
                "chapter": row["chapter"],
                "source": "index",
                "indexed": True,
                "uri_recovered": row.get("uri_recovered"),
                "body_line": body["line"] if body else None,
                "body_title": body["title"] if body else None,
                "body_section": body["section"] if body else None,
                "schema": body["schema"] if body else None,
                "schema_source": body["schema_source"] if body else None,
                "table_type": body.get("table_type") if body else None,
            }
        )

    indexed = {str(record["uri"]) for record in records if record["uri"]}
    for claim in index.claims():
        uri = claim["uri"]
        # A claim whose block states an ``Input URI`` marker but documents no path
        # (``| **{base url} +** |``) has no endpoint.  It is counted in the report,
        # never emitted as a row with an invented endpoint.
        if not uri or not claim.get("documents_uri", True) or str(uri) in indexed:
            continue
        indexed.add(str(uri))
        records.append(
            {
                "uri": str(uri),
                "endpoint": endpoint_of(str(uri)),
                "code": claim["code"] or code_from_uri(str(uri)),
                "title": claim["title"],
                "methods": methods_for_body(index, claim),
                "line": claim["line"],
                "section": claim["section"],
                "chapter": claim["section"],
                "source": "body",
                "indexed": False,
                "body_line": claim["line"],
                "body_title": claim["title"],
                "body_section": claim["section"],
                "schema": claim["schema"],
                "schema_source": claim["schema_source"],
                "table_type": claim.get("table_type"),
            }
        )
    return records


def code_from_uri(uri: str) -> str:
    """Interface code for a row whose index cell was ``—``.

    The last path segment is the code in every manual that leaves the column
    empty (``/DOC/OPEN`` -> ``OPEN``, ``/DB/NODE`` -> ``NODE``); when even that is
    unusable the slugified segment is used.
    """
    resource = resource_of(uri)
    if resource:
        return resource.upper() if resource.isascii() else resource
    return slugify(uri)


def methods_for_body(index: ManualIndex, claim: dict[str, object]) -> list[str]:
    """Methods for a body-only entry: the ``Active Methods`` block in its span.

    The block is a one-cell table in the Gen English sections (``| **POST** |``) and
    a bold paragraph in the Chinese backbone (``** Post**``); ``parse_methods``
    reads both.  The probe stops at the next block marker so a missing method table
    cannot absorb the schema's own text.
    """
    start = int(claim["line"]) - 1
    limit = int(claim["span_end"])
    for marker in index.method_markers:
        if not (start <= marker < limit):
            continue
        for probe in range(marker + 1, min(marker + 12, limit)):
            line = index.lines[probe].strip()
            if not line:
                continue
            if is_block_marker(line):
                break
            found = parse_methods(line)
            if found:
                return found
    return ["POST"]


def build_rows(
    key: str,
    records: list[dict[str, object]],
    index: ManualIndex,
    uri_feature: dict[str, str],
    glossary: Mapping[str, Mapping[str, object]] | None = None,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, int],
    dict[str, int],
    list[dict[str, object]],
]:
    """Expand entry records to one row per ``(endpoint, method)``.

    Returns ``(rows, merges, unknown_families, feature_provenance, qualified)``.

    Three things happen here, in order:

    1. **Records are grouped by endpoint.**  The same URI is often documented more
       than once (Gen's Chinese backbone and its English indexed section overlap
       almost completely).  A group's *primary* record is the one from the most
       authoritative section (:data:`SECTION_PRIORITY`); the rest are kept in
       ``metadata_json.merged_records`` and listed in the report, never dropped.
    2. **The method set is the union over the group.**  Different sections
       advertise slightly different method lists for the same URI, and a method
       documented anywhere is callable, so the union is the honest answer.
    3. **One row per method.**  The method is folded into ``interface_code``, so
       `(adapter_code, interface_code)` is unique by construction rather than by
       a numeric suffix.  A record with no URI cannot be dispatched and is
       returned as a *merge* record instead of a row.

    ``glossary`` is the Chinese annotation table (``title_zh.json`` -> ``titles``);
    it is **optional**, so a missing file yields ``description: null`` on every row
    rather than a failure.  Each row carries the unwrapped ``title`` of its primary
    record and the annotation the glossary has for it, looked up on the record's
    ``source_title`` first and on its ``body_title`` second — the body heading is
    where a body-only entry (the Gen manual's unindexed design section) keeps its
    title, and an index cell that is empty would otherwise lose the annotation the
    body could supply.
    """
    adapter = ADAPTER_CODES[key]
    rows: list[dict[str, object]] = []
    merges: list[dict[str, object]] = []
    unknown_families: collections.Counter[str] = collections.Counter()
    provenance_counter: collections.Counter[str] = collections.Counter()

    groups: dict[tuple[str, str], list[dict[str, object]]] = collections.OrderedDict()
    for record in records:
        uri = record["uri"]
        if uri is None:
            merges.append(
                {
                    "adapter_code": adapter,
                    "reason": "no URI — no endpoint to dispatch",
                    "title": record["title"],
                    "code": record["code"],
                    "line": record["line"],
                    "chapter": record["chapter"],
                    "methods": list(record["methods"]),
                }
            )
            continue
        uri = str(uri)
        # ``/post/TABLE`` and ``/DESIGN/**/TABLE`` are *shared* URIs: one URI
        # carrying hundreds of result tables selected by ``TABLE_TYPE`` inside the
        # Argument.  Grouping them by URI alone would merge every result table into
        # one row, so the table discriminator is part of the group key (总纲 裁决 B-3).
        shared = needs_table_type(uri)
        key_of = (uri, table_type_slug(str(record["title"])) if shared else "")
        groups.setdefault(key_of, []).append(record)

    for (uri, table_slug), bucket in groups.items():
        bucket.sort(
            key=lambda record: (
                index.section_rank(str(record["section"])),
                int(record["line"]),
            )
        )
        primary = bucket[0]
        merged = bucket[1:]
        methods: list[str] = []
        for record in bucket:
            for method in record["methods"]:
                value = str(method).upper()
                if value not in methods:
                    methods.append(value)
        methods.sort(key=lambda item: METHOD_ORDER.get(item, 9))
        if not methods:
            methods = ["POST"]

        family = uri_family(uri) or "unknown"
        wrapper, root_key, unknown = derive_wrapper(uri)
        if unknown is not None:
            unknown_families[unknown] += 1

        endpoint = str(primary["endpoint"])
        resource = resource_of(uri)
        feature, provenance = feature_for(key, uri, str(primary["chapter"]), uri_feature)
        domain = CAPABILITY_FEATURE_DOMAIN.get(str(feature)) if feature else None
        provenance_counter[provenance] += 1

        # The Chinese annotation (总纲 §4.2.13).  ``title`` is the primary record's
        # own title unwrapped with the glossary's own rule; the annotation is looked
        # up on the index cell first and on the body heading second, because a
        # body-only entry (the Gen manual's unindexed design section) keeps its title
        # there.  ``annotation_key`` records which glossary key matched, so the report
        # can name an entry the rows never used.
        title = unwrap_title(primary["title"]) or unwrap_title(primary.get("body_title"))
        annotation, annotation_source, annotation_key = annotation_for(
            primary["title"], glossary or {}
        )
        if annotation is None:
            annotation, annotation_source, annotation_key = annotation_for(
                primary.get("body_title"), glossary or {}
            )

        segments = [part for part in uri.split("/") if part]
        path_slug = ".".join(slugify(part) for part in segments[1:]) or slugify(family)
        base_code = f"{adapter}.{family}.{path_slug}"
        discriminator = "table_type" if table_slug else ""

        merged_records = [
            {
                "source": record["source"],
                "section": record["section"],
                "line": record["line"],
                "title": record["title"],
                "code": record["code"],
                "methods": list(record["methods"]),
            }
            for record in merged
        ]
        for record in merged:
            merges.append(
                {
                    "adapter_code": adapter,
                    "reason": "same URI documented again — folded into the primary row",
                    "endpoint": endpoint,
                    "uri": uri,
                    "kept_line": primary["line"],
                    "kept_section": primary["section"],
                    "merged_line": record["line"],
                    "merged_section": record["section"],
                    "merged_title": record["title"],
                    "methods_union": ", ".join(methods),
                }
            )

        for method in methods:
            operation = derive_operation(method, str(primary["title"]))
            pieces = [base_code]
            if table_slug:
                pieces.append(table_slug)
            pieces.append(operation)
            code = ".".join(pieces)
            carries_body = method in BODY_METHODS
            rows.append(
                {
                    "adapter_code": adapter,
                    "interface_code": code,
                    "method": method,
                    # For the shared table URIs ``endpoint`` is deliberately the bare
                    # URI for every table (``/post/TABLE``): the table is named by
                    # ``interface_code`` and by ``TABLE_TYPE`` inside the Argument,
                    # and folding the slug into ``endpoint`` would invent a path the
                    # API does not serve.
                    "endpoint": endpoint,
                    "request_wrapper": wrapper,
                    "response_root_key": root_key,
                    "operation": operation,
                    "resource": resource,
                    # The Chinese annotation (总纲 §4.2.13): ``title`` is the manual's
                    # own title with its markdown link removed, ``description`` is
                    # ``name_zh + "：" + description_zh`` (or ``name_zh`` alone, or
                    # ``null`` when the glossary has nothing for this title — never an
                    # invented string).
                    "title": title,
                    "description": annotation,
                    "product_scope": EMITTED_PRODUCT_SCOPE,
                    "domain": domain,
                    "feature": feature,
                    # A request body only exists for body-carrying methods; the
                    # schema is per-URI, so the POST row of the same URI keeps it.
                    "request_schema_json": primary["schema"] if carries_body else None,
                    "metadata_json": {
                        "source_manual": key,
                        "source_section": primary["section"],
                        "source_chapter": primary["chapter"],
                        "source_line": primary["line"],
                        "source_title": primary["title"],
                        "source_code": primary["code"],
                        "source_kind": primary["source"],
                        # The Chinese annotation's provenance: ``manual`` (the manual
                        # ships the Chinese) or ``glossary`` (``title_zh.json``
                        # supplied it), plus the glossary key that matched.  ``None``
                        # means the row carries no annotation at all.
                        "annotation_source": annotation_source,
                        "annotation_key": annotation_key,
                        "indexed": primary["indexed"],
                        "uri_recovered": primary.get("uri_recovered"),
                        "body_line": primary.get("body_line"),
                        "body_title": primary.get("body_title"),
                        "body_section": primary.get("body_section"),
                        "schema_source": primary["schema_source"] if carries_body else None,
                        # The literal ``TABLE_TYPE`` the entry's own text states, for
                        # the shared result-table URIs.  Recorded, never used to
                        # re-key ``interface_code``: the code is the published
                        # identity of the row, and renaming it because a second
                        # spelling of the same discriminator was found would move
                        # every consumer's key for no gain.
                        "table_type": primary.get("table_type"),
                        "feature_provenance": provenance,
                        "interface_code_disambiguation": discriminator or None,
                        "documented_methods": methods,
                        "merged_records": merged_records,
                    },
                }
            )

    # ``(adapter_code, interface_code)`` must be unique (总纲 裁决 B-3).  The method
    # and the table discriminator make that true for almost every URI, but a URI can
    # carry two genuinely different interfaces that the title alone does not
    # separate — ``/DESIGN/RC/KDS-41-20-2022/REBB`` is both the rebar-data CRUD and
    # its result table, and the Chinese and English titles are identical.  Rather
    # than append a meaningless ``.2``, the colliding codes are qualified by the
    # manual line the interface is documented at, and every qualification is
    # reported (§6.2) so it can be reviewed.
    counts: collections.Counter[str] = collections.Counter(
        str(row["interface_code"]) for row in rows
    )
    qualified: list[dict[str, object]] = []
    for row in rows:
        code = str(row["interface_code"])
        if counts[code] < 2:
            continue
        metadata = row["metadata_json"]  # type: ignore[assignment]
        line = metadata.get("body_line") or metadata.get("source_line")
        row["interface_code"] = f"{code}.at{line}"
        metadata["interface_code_disambiguation"] = "source_line"
        qualified.append(
            {
                "adapter_code": row["adapter_code"],
                "base_code": code,
                "qualified_code": row["interface_code"],
                "endpoint": row["endpoint"],
                "method": row["method"],
                "source_line": line,
                "title": metadata.get("source_title"),
            }
        )

    rows.sort(
        key=lambda row: (
            str(row["adapter_code"]),
            str(row["endpoint"]),
            METHOD_ORDER.get(str(row["method"]), 9),
            str(row["interface_code"]),
        )
    )
    return rows, merges, dict(unknown_families), dict(provenance_counter), qualified


# ---------------------------------------------------------------------------
# reconciliation and coverage
# ---------------------------------------------------------------------------
def reconcile(
    key: str,
    records: list[dict[str, object]],
    index: ManualIndex,
    inventory_entries: list[dict[str, object]],
) -> dict[str, object]:
    """Compare the index table, the bodies and ``inventory.json``.

    Every number here is measured; nothing is assumed.  ``inventory.json``'s
    ``line`` numbers are stale (the Gen manual has 410,728 lines while the
    inventory's last Gen entry claims 410,979), so entries are matched **by URI**.
    """
    index_uris = index.index_uris()
    body_uris = index.body_uris()
    inventory_uris = {
        str(uri)
        for uri in (canonical_uri(entry.get("uri")) for entry in inventory_entries)
        if uri
    }
    null_uri_entries = [
        {
            "code": entry.get("code"),
            "title": entry.get("title"),
            "line": entry.get("line"),
            "level": entry.get("level"),
            "methods": entry.get("methods"),
        }
        for entry in inventory_entries
        if entry.get("uri") is None
    ]
    return {
        "index_rows": len(index.index_rows),
        "index_uris": len(index_uris),
        "body_claims": len(index.claims()),
        "body_uris": len(body_uris),
        "joined_uris": len(index_uris & body_uris),
        "index_only_uris": len(index_uris - body_uris),
        "index_only_examples": sorted(index_uris - body_uris)[:30],
        "body_only_uris": len(body_uris - index_uris),
        "body_only_examples": sorted(body_uris - index_uris)[:30],
        "inventory_entries": len(inventory_entries),
        "inventory_uris": len(inventory_uris),
        "inventory_null_uri": null_uri_entries,
        "inventory_uris_missing_from_manual": len(inventory_uris - index_uris - body_uris),
        "inventory_missing_examples": sorted(inventory_uris - index_uris - body_uris)[:30],
        "manual_uris_missing_from_inventory": len((index_uris | body_uris) - inventory_uris),
        "manual_missing_examples": sorted((index_uris | body_uris) - inventory_uris)[:30],
        "records": len(records),
    }


def coverage(rows: list[dict[str, object]]) -> dict[str, object]:
    """Every number the report prints, computed from the rows themselves."""
    total = len(rows)
    body_rows = [row for row in rows if str(row["method"]) in BODY_METHODS]
    with_schema = [row for row in rows if row["request_schema_json"]]
    body_with_schema = [row for row in body_rows if row["request_schema_json"]]
    schema_sources = collections.Counter(
        str(row["metadata_json"]["schema_source"])  # type: ignore[index]
        for row in body_with_schema
    )
    return {
        "rows": total,
        "body_rows": len(body_rows),
        "with_schema": len(with_schema),
        "with_schema_pct": round(100.0 * len(with_schema) / total, 1) if total else 0.0,
        "body_with_schema": len(body_with_schema),
        "body_with_schema_pct": (
            round(100.0 * len(body_with_schema) / len(body_rows), 1) if body_rows else 0.0
        ),
        "schema_sources": dict(sorted(schema_sources.items())),
        "by_method": dict(
            sorted(collections.Counter(str(row["method"]) for row in rows).items())
        ),
        "by_operation": dict(
            sorted(collections.Counter(str(row["operation"]) for row in rows).items())
        ),
        "by_adapter": dict(
            sorted(collections.Counter(str(row["adapter_code"]) for row in rows).items())
        ),
        "by_domain": dict(
            sorted(collections.Counter(str(row["domain"]) for row in rows).items())
        ),
        "by_feature": dict(
            sorted(collections.Counter(str(row["feature"]) for row in rows).items())
        ),
        "by_resource": dict(
            sorted(
                collections.Counter(str(row["resource"]) for row in rows).items(),
                key=lambda item: (-item[1], item[0]),
            )
        ),
        "by_wrapper": dict(
            sorted(collections.Counter(str(row["request_wrapper"]) for row in rows).items())
        ),
        "null_root_key": sum(1 for row in rows if row["response_root_key"] is None),
    }


def section_schema_report(index: ManualIndex) -> list[dict[str, object]]:
    """Per ``##`` section: ``JSON Schema`` markers seen, entries found, schemas attached.

    This is the measurement the self-check reads, and the number the previous
    revision had no way to compare against anything: it found 2 body claims in a Gen
    section holding hundreds of ``JSON Schema`` markers and reported no anomaly,
    because nothing counted the markers.  A count that is wrong without looking
    wrong is worse than a crash, so the two are put side by side.

    ``uri_not_in_index`` is the "counted, never silently dropped" half: an entry
    whose URI the index table does not carry still has a claim (and therefore a
    body-only record), and it is listed with its reason rather than discarded.
    """
    headings: collections.Counter[str] = collections.Counter(
        index.section_of(line) for line in index.schema_markers
    )
    claims: collections.Counter[str] = collections.Counter()
    attached: collections.Counter[str] = collections.Counter()
    other: collections.Counter[tuple[str, str]] = collections.Counter()
    unmatched: collections.Counter[str] = collections.Counter()
    unmatched_examples: dict[str, list[str]] = collections.defaultdict(list)
    indexed = index.index_uris()
    for claim in index.claims():
        section = str(claim["section"])
        claims[section] += 1
        source = str(claim.get("schema_source") or "none")
        if source == "json_schema":
            attached[section] += 1
        else:
            other[(section, source)] += 1
        uri = claim["uri"]
        if uri and str(uri) in indexed:
            continue
        unmatched[section] += 1
        if len(unmatched_examples[section]) < 8:
            if not claim.get("documents_uri", True):
                reason = "states the marker and no path"
            else:
                reason = "URI not in the index table"
            unmatched_examples[section].append(
                f"`{uri or '<none>'}` line {claim['line']} — {reason}"
            )
    sections = sorted(set(headings) | set(claims))
    return [
        {
            "section": section,
            "schema_headings": headings.get(section, 0),
            "claims": claims.get(section, 0),
            "json_schema_attached": attached.get(section, 0),
            "uri_not_in_index": unmatched.get(section, 0),
            "unmatched_examples": unmatched_examples.get(section, []),
            "other_sources": {
                source: count
                for (name, source), count in sorted(other.items())
                if name == section
            },
        }
        for section in sections
    ]


def table_type_report(index: ManualIndex) -> dict[str, object]:
    """How well the shared result-table URIs are discriminated, per source section.

    The question this answers: for ``/post/TABLE`` and ``/DESIGN/**/TABLE``, does the
    manual state the literal ``TABLE_TYPE`` the API matches on, or only a title the
    extraction has to paraphrase into a slug?
    """
    per_section: dict[str, dict[str, int]] = collections.defaultdict(
        lambda: {"entries": 0, "literal": 0, "ambiguous": 0, "none": 0}
    )
    for claim in index.claims():
        uri = str(claim["uri"] or "")
        if not needs_table_type(uri):
            continue
        section = str(claim["section"])
        bucket = per_section[section]
        bucket["entries"] += 1
        found = claim.get("table_types")
        count = len(found) if isinstance(found, list) else 0
        if count == 1:
            bucket["literal"] += 1
        elif count > 1:
            bucket["ambiguous"] += 1
        else:
            bucket["none"] += 1
    return {name: dict(counts) for name, counts in sorted(per_section.items())}


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
def _table(add: object, header: tuple[str, ...], body: list[tuple[object, ...]]) -> None:
    add("| " + " | ".join(header) + " |")
    add("| " + " | ".join("---" for _ in header) + " |")
    for item in body:
        add("| " + " | ".join(str(cell) for cell in item) + " |")


def write_report(
    report_data: dict[str, object],
) -> None:
    """Render ``EXTRACTION_REPORT.md`` from the measured run."""
    add = report_data["add"]  # type: ignore[assignment]
    manuals = report_data["manuals"]  # type: ignore[assignment]
    rows = report_data["rows"]  # type: ignore[assignment]
    merges = report_data["merges"]  # type: ignore[assignment]
    stats = report_data["coverage"]  # type: ignore[assignment]
    recon = report_data["reconcile"]  # type: ignore[assignment]
    unknown = report_data["unknown_families"]  # type: ignore[assignment]
    provenance = report_data["provenance"]  # type: ignore[assignment]
    operations = report_data["operation_table"]  # type: ignore[assignment]

    add("# MIDAS API interface extraction — coverage report")
    add("")
    add(
        "Generated by [`extract_interfaces.py`](extract_interfaces.py).  Every number "
        "below is computed from the run, not estimated.  The pipeline takes the "
        "manuals' **index tables** as the primary source and consults the interface "
        "bodies only for the request schema."
    )
    add("")

    # ---- 1. characterisation -------------------------------------------
    add("## 1. Characterisation: the three manuals' shapes")
    add("")
    add("### 1.1 Index tables")
    add("")
    add(
        "All three manuals carry the **same** index-table header, verbatim:"
    )
    add("")
    add("```text")
    add("| # | 接口代码 | 接口名称 | URL | 方法 | 所在章节 |")
    add("| --- | --- | --- | --- | --- | --- |")
    add("| 97 | `CNLD` | [Nodal](#nodal) | `db/CNLD` | GET / POST / PUT / DELETE | JSON数据手册 / Load |")
    add("```")
    add("")
    add(
        "One row therefore already carries `interface_code` + endpoint + method + "
        "chapter — everything `tool_interfaces` needs except the schema.  The table "
        "is the primary source for exactly that reason."
    )
    add("")
    _table(
        add,
        ("manual", "index header line", "first row", "last row", "rows", "cell anomalies"),
        [
            (
                f"`{key}`",
                data["index"]["header_line"],
                data["index"]["first_row_line"],
                data["index"]["last_row_line"],
                data["index"]["rows"],
                data["index"]["anomaly_count"],
            )
            for key, data in manuals.items()
        ],
    )
    add("")
    add("Per-manual detail:")
    add("")
    for key, data in manuals.items():
        add(f"**`{key}`** — {data['lines']:,} lines")
        add("")
        add(
            f"- index rows **{data['index']['rows']}**, of which "
            f"**{data['code_present']}** carry a non-empty `接口代码` and "
            f"**{data['code_absent']}** carry `—`; "
            f"**{data['index_rows_without_url']}** state no URL at all, of which "
            f"**{data['index_rows_without_url'] - data['index_rows_still_without_uri']}** "
            "were recovered from the entry's own title path or body and "
            f"**{data['index_rows_still_without_uri']}** document no path anywhere."
        )
        add(
            f"- index rows per `##` section: "
            + ", ".join(f"`{name}` {count}" for name, count in data["rows_by_section"].items())
        )
        add(
            f"- distinct `方法` spellings: "
            + "; ".join(f"`{name}` ×{count}" for name, count in data["method_strings"].items())
        )
        add(
            f"- distinct `所在章节` values: **{len(data['chapters'])}**; "
            f"sub-chapter values: **{len(data['subchapters'])}**"
        )
        add("")
    add("### 1.2 Body shapes")
    add("")
    add(
        "Each manual states a body URI in a different way, and the difference is "
        "what broke the previous revision:"
    )
    add("")
    _table(
        add,
        ("manual", "entry heading", "body URI form", "schema form"),
        [
            (
                "`gen` (JSON数据手册)",
                "`#####`/`######` under `####` groups, preceded by `接口代码：`CODE``",
                "bold paragraph `** {base url} + db/CNLD**` — a space after `**` and a "
                "trailing U+200B on some entries, neither on others",
                "`**JSON Schema**` (draft-07) or `**Input Data Form**` "
                "(`__DESC__`/`__TYPE__`)",
            ),
            (
                "`gen` (English sections)",
                "`####` per interface",
                "`##### **Input URI**` block, the URI in a one-cell table "
                "`| **/DESIGN/RC/KDS-41-20-2022/CMFT** |` or a fenced block",
                "`##### **JSON Schema**` (draft-07), often with `enum`/`default`",
            ),
            (
                "`civilnx`",
                "`####` per interface",
                "`##### Input URI` block with `**{base url} + doc/new**`, or the bold "
                "paragraph form `**Input URI**`",
                "`##### JSON Schema` (draft-07) for body-carrying interfaces; "
                "`**JSON Schema**` for some in the Results chapter",
            ),
            (
                "`designer`",
                "`###` per interface (`####` are its blocks)",
                "`#### 接口URL` then `**{base url} + /DOC/OPEN**`",
                "**no** JSON Schema at all — only `#### 请求示例` and parameter tables",
            ),
        ],
    )
    add("")
    add("Measured body/schema availability per manual:")
    add("")
    _table(
        add,
        ("manual", "body URI claims", "distinct body URIs", "JSON Schema", "Input Data Form", "example only", "none"),
        [
            (
                f"`{key}`",
                data["body_claims"],
                data["body_uris"],
                data["schema_kinds"].get("json_schema", 0),
                data["schema_kinds"].get("input_data_form", 0),
                data["schema_kinds"].get("request_example", 0)
                + data["schema_kinds"].get("example", 0),
                data["schema_kinds"].get("none", 0),
            )
            for key, data in manuals.items()
        ],
    )
    add("")
    add("### 1.3 Do index rows and bodies join?")
    add("")
    _table(
        add,
        ("manual", "index rows", "index URIs", "body URIs", "joined", "index-only", "body-only"),
        [
            (
                f"`{key}`",
                recon[key]["index_rows"],
                recon[key]["index_uris"],
                recon[key]["body_uris"],
                recon[key]["joined_uris"],
                recon[key]["index_only_uris"],
                recon[key]["body_only_uris"],
            )
            for key in manuals
        ],
    )
    add("")
    add(
        "The join is on the **canonical URI** (lower-cased, `info/` stripped, "
        "`{base url} +` stripped), never on line numbers."
    )
    add("")

    # ---- 2. entries in, rows out --------------------------------------
    add("## 2. Entries in, rows out")
    add("")
    _table(
        add,
        ("manual", "adapter", "index rows", "body-only entries", "entry records", "rows out", "merged"),
        [
            (
                f"`{key}`",
                f"`{ADAPTER_CODES[key]}`",
                data["index"]["rows"],
                recon[key]["records"] - data["index"]["rows"],
                recon[key]["records"],
                data["rows_out"],
                data["merged_out"],
            )
            for key, data in manuals.items()
        ],
    )
    add("")
    total_in = sum(int(data["index"]["rows"]) for data in manuals.values())
    total_records = sum(int(recon[key]["records"]) for key in manuals)
    add(
        f"**{total_in}** index rows + **{total_records - total_in}** body-only entries "
        f"= **{total_records}** entry records, which expand to **{len(rows)}** rows. "
        "Rows differ from entries for three reasons, in this order:"
    )
    add("")
    add(
        "1. **Multi-method expansion** — one row per method.  A URI advertising "
        "`GET / POST / PUT / DELETE` yields four rows, because `method` is part of "
        "the row identity and the adapter dispatches per method.  The method is "
        "folded into `interface_code`, so this is not a collision."
    )
    add(
        "2. **The same `(endpoint, method)` documented twice is merged** — the Gen "
        "manual repeats most of its Chinese-backbone interfaces in its English "
        "sections.  The later record is kept as `metadata_json.merged_records` on "
        f"the surviving row, never dropped: **{len(merges)}** merges, listed in §6."
    )
    add(
        "3. **Entries with no URI are not rows** — a row without an endpoint cannot "
        "be dispatched.  They are listed in §5 instead of being emitted with an "
        "empty endpoint."
    )
    add("")
    add(
        "The count to compare against a URI-level estimate is therefore **not** the "
        "row count.  Measured: "
        + ", ".join(
            f"`{key}` {int(data['index']['rows'])} index rows → "
            f"{int(recon[key]['index_uris'])} distinct URIs"
            for key, data in manuals.items()
        )
        + ".  One row exists per distinct `(endpoint, method)` pair, so a URI "
        "advertising four methods contributes four rows and a URI advertising one "
        "contributes one — which is why the row count lands above the distinct-URI "
        "count rather than below it."
    )
    add("")
    add("Rows per adapter and per method:")
    add("")
    _table(
        add,
        ("adapter", "rows"),
        [(f"`{name}`", count) for name, count in stats["by_adapter"].items()],
    )
    add("")
    _table(
        add,
        ("method", "rows"),
        [(f"`{name}`", count) for name, count in stats["by_method"].items()],
    )
    add("")

    # ---- 3. schema coverage -------------------------------------------
    add("## 3. Schema coverage (the LLM-safety question)")
    add("")
    add(
        f"- rows emitted: **{stats['rows']}**\n"
        f"- rows with a non-null `request_schema_json`: **{stats['with_schema']}** "
        f"(**{stats['with_schema_pct']}%** of all rows)\n"
        f"- rows whose method carries a request body (`POST`/`PUT`/`PATCH`): "
        f"**{stats['body_rows']}**, of which **{stats['body_with_schema']}** have a "
        f"schema (**{stats['body_with_schema_pct']}%**) — **this is the denominator "
        f"that matters**\n"
        f"- rows with `null`: {int(stats['rows']) - int(stats['with_schema'])}"
    )
    add("")
    add(
        "`request_schema_json` is emitted **only for body-carrying methods**.  The "
        "manual documents one body per URI, so attaching it to the `GET`/`DELETE` "
        "rows of the same URI would invite a caller to send a body those verbs do "
        "not take.  A `null` therefore means one of two things, and they are not "
        "the same backlog item:"
    )
    add("")
    add(
        "- the method takes no body (`GET`/`DELETE`) — nothing to validate, and\n"
        "- the method takes a body but the manual documents none — **this** is the "
        "real gap, because such a call cannot be validated before it is sent."
    )
    add("")
    add(
        "Where the schema came from (`json_schema` = the manual's draft-07 JSON "
        "Schema, `input_data_form` = the Chinese backbone's `__DESC__`/`__TYPE__` "
        "form, `request_example` = the manual's own request-example block, `example` "
        "= a JSON fence found by position alone, because the entry states no marker "
        "this pipeline reads).  The counter is the authority on which of them "
        "actually occur: on this manual revision `input_data_form` does not, and §10 "
        "says why."
    )
    add("")
    _table(
        add,
        ("`schema_source`", "body-carrying rows"),
        [
            (f"`{name}`", count)
            for name, count in stats["schema_sources"].items()
        ]
        + [("`None`", int(stats["body_rows"]) - int(stats["body_with_schema"]))],
    )
    add("")
    add(
        "When one URI is documented more than once the winner is chosen by **source "
        "quality first** — `json_schema` > `input_data_form` > `request_example` > "
        "`example` — then by the row's own title, then by section authority "
        "(`SECTION_PRIORITY`), then by file order.  Ordering by section first would "
        "let an English entry that carries only an example displace a Chinese entry "
        "that carries a form; the counter above is what records which source won."
    )
    add("")

    # ---- 3.1 markers vs attached schemas -------------------------------
    add("### 3.1 `JSON Schema` markers seen vs schemas attached")
    add("")
    add(
        "Every manual states its request schema under a `JSON Schema` block marker, "
        "and the marker is written three ways: a bold paragraph (`**JSON Schema**`, "
        "Civil NX's Results chapter and nine Gen English entries), a plain level-5 "
        "heading (`##### JSON Schema`, Civil NX) and an emphasised level-5 heading "
        "(`##### **JSON Schema**`, both Gen English sections).  The collector matches "
        "on the marker's **name**, so all three count.  The two columns below are the "
        "check that matters: a section holding hundreds of markers and returning a "
        "handful of claims is the silent-zero failure mode, and it has to be visible "
        "as a number."
    )
    add("")
    _table(
        add,
        (
            "manual",
            "`##` section",
            "`JSON Schema` markers",
            "body claims",
            "schemas attached",
            "claims whose URI is not in the index",
            "other sources",
        ),
        [
            (
                f"`{key}`",
                f"`{item['section']}`",
                item["schema_headings"],
                item["claims"],
                item["json_schema_attached"],
                item["uri_not_in_index"],
                ", ".join(
                    f"`{name}` {count}"
                    for name, count in item["other_sources"].items()  # type: ignore[union-attr]
                )
                or "—",
            )
            for key, data in manuals.items()
            for item in data["section_schemas"]  # type: ignore[union-attr]
        ],
    )
    add("")
    add("Per-manual totals and the entry shapes measured, not assumed:")
    add("")
    schema_totals: dict[str, tuple[int, int]] = {}
    for key, data in manuals.items():
        marker_sum = 0
        attached_sum = 0
        for item in data["section_schemas"]:  # type: ignore[union-attr]
            marker_sum += int(item["schema_headings"])
            attached_sum += int(item["json_schema_attached"])
        schema_totals[key] = (marker_sum, attached_sum)
    _table(
        add,
        (
            "manual",
            "markers",
            "attached",
            "attached %",
            "body claims",
            "distinct body URIs",
            "`Input URI` marker forms seen",
        ),
        [
            (
                f"`{key}`",
                schema_totals[key][0],
                schema_totals[key][1],
                (
                    "{:.1f}%".format(100.0 * schema_totals[key][1] / schema_totals[key][0])
                    if schema_totals[key][0]
                    else "—"
                ),
                data["body_claims"],
                data["body_uris"],
                ", ".join(
                    f"`{form}` ×{count}"
                    for form, count in data["uri_marker_forms"].items()  # type: ignore[union-attr]
                )
                or "—",
            )
            for key, data in manuals.items()
        ],
    )
    add("")
    add(
        "The Gen manual's English sections are where the previous revision failed: it "
        "recognised the bold `**Input URI**` paragraph, which is how the Chinese "
        "backbone states the marker, but not the `##### **Input URI**` **heading**, "
        "which is how both English sections state it.  Every one of their `JSON Schema` "
        "blocks was therefore unreachable — no entry, no attachment — and the counts "
        "above are what make that visible instead of silent.  The entry shapes actually "
        "found, by reading several sections of each kind:"
    )
    add("")
    _table(
        add,
        ("manual / section", "entry heading", "`Input URI` marker", "URI value", "method", "schema"),
        [
            (
                "`gen` / JSON数据手册",
                "`####` under a `###` group, `接口代码：`CODE`` on its own line",
                "`**Input URI**` bold paragraph, with one exception in the whole "
                "section that writes it as a `##### Input URI` heading",
                "bold paragraph `** {base url} + db/CNLD**` — a space after `**` and a "
                "trailing U+200B on some entries, neither on others",
                "bold paragraph `** Post**`",
                "`**JSON Schema**` or `**Input Data Form**` + an indented fence",
            ),
            (
                "`gen` / 英文数据手册（索引接口）",
                "`####`, with a `- 英文原文： [Title](url)` line under it",
                "`##### **Input URI**` heading (the dominant form) or, for a couple of "
                "entries, the `**Input URI**` bold paragraph",
                "one-cell table `| **{base url} + doc/NEW** |`",
                "one-cell table `| **POST** |`",
                "`##### **JSON Schema**` + a column-0 ```` ```json ```` fence; a few "
                "entries write the marker as the bold `**Json Schema**` paragraph",
            ),
            (
                "`gen` / 英文数据手册（未编入索引）",
                "`####`, titled `PATH : Name`",
                "`##### **Input URI**` heading, every entry",
                "one-cell table `| **{base url} + DESIGN/SECT** |`",
                "one-cell table `| **POST,GET,PUT,DELETE** |`",
                "`##### **JSON Schema**`, every entry",
            ),
            (
                "`civilnx`",
                "`####`, titled `中文[CODE]English`",
                "`##### Input URI` heading (no emphasis)",
                "bold paragraph `**{base url} + doc/new**`",
                "`##### Active Methods` + bold `**Post**`",
                "`##### JSON Schema` heading, or `##### Input Data Form`",
            ),
            (
                "`designer`",
                "`###` per interface (`####` are its blocks)",
                "`#### 接口URL` then `**{base url} + /DOC/OPEN**`",
                "bold paragraph",
                "bold paragraph",
                "**no** JSON Schema — `#### 请求示例` and parameter tables only",
            ),
        ],
    )
    add("")
    unmatched_rows = [
        (key, item["section"], example)
        for key, data in manuals.items()
        for item in data["section_schemas"]  # type: ignore[union-attr]
        for example in item["unmatched_examples"]  # type: ignore[union-attr]
    ]
    unmatched_total = sum(
        int(item["uri_not_in_index"])
        for data in manuals.values()
        for item in data["section_schemas"]  # type: ignore[union-attr]
    )
    add(
        f"**{unmatched_total}** body claims state a URI the index table does not carry, "
        "or state the `Input URI` marker and no path at all.  They are **counted**, not "
        "dropped: a claim with a URI becomes a body-only entry (reported in §2), and a "
        "claim without one is listed in §5.  The first few, with their reason:"
    )
    add("")
    if unmatched_rows:
        _table(
            add,
            ("manual", "`##` section", "claim"),
            [
                (f"`{key}`", f"`{section}`", example)
                for key, section, example in unmatched_rows[:40]
            ],
        )
    else:
        add("_None — every body claim's URI is in its manual's index table._")
    add("")
    add("### 3.2 The shared result-table URIs")
    add("")
    add(
        "`/post/TABLE` and `/DESIGN/**/TABLE` are one URI each, carrying hundreds of "
        "logical tables selected by `TABLE_TYPE` inside the `Argument`.  A schema "
        "found on such a URI therefore describes exactly **one** table, and attaching "
        "it to every row on the URI would be worse than attaching nothing.  Two things "
        "keep it straight:"
    )
    add("")
    add(
        "1. **The row's own title picks the claim.**  `best_body` prefers the claim "
        "whose entry title equals the index row's title when exactly one candidate "
        "matches, so `#### Beam Force - Analysis Result Table` supplies the schema for "
        "the row titled `Beam Force - Analysis Result Table` and not for any of the "
        "other rows sharing `/post/TABLE`.  Only a unique match is used; an ambiguous "
        "title falls back to the URI-level ranking rather than guessing."
    )
    add(
        "2. **The literal `TABLE_TYPE` is read out of the entry and recorded.**  The "
        "value the API actually matches on is stated in the entry's own text, and it "
        "is recorded in `metadata_json.table_type`.  It is deliberately **not** used to "
        "re-key `interface_code`: the code is the row's published identity, and "
        "renaming it because a second spelling of the same discriminator turned up "
        "would move every consumer's key for no gain."
    )
    add("")
    add(
        "**Does the English side discriminate better than the Chinese side?  Yes, and "
        "measurably so.**  An English result-table entry states the literal three "
        "times — in its `JSON Schema` block (`\"TABLE_NAME\": \"BEAMDESIGNFORCES\"`), "
        "in its `Request Examples` body (`\"TABLE_TYPE\": \"BEAMDESIGNFORCES\"`) and "
        "in its `Specifications` row "
        "(`Result Table Type • \"BEAMDESIGNFORCES\" | \"TABLE_TYPE\" | …`) — where the "
        "Chinese entries state it once, in a per-entry example body, plus one generic "
        "`TABLE_TYPE` lookup table shared by all of them.  Measured per section (an "
        "entry that names several tables at once is counted as `ambiguous` and yields "
        "no single literal, because a discriminator that does not discriminate is "
        "worse than none):"
    )
    add("")
    _table(
        add,
        ("manual", "`##` section", "shared-URI entries", "one literal", "ambiguous", "none"),
        [
            (
                f"`{key}`",
                f"`{section}`",
                counts["entries"],
                counts["literal"],
                counts["ambiguous"],
                counts["none"],
            )
            for key, data in manuals.items()
            for section, counts in data["table_types"].items()  # type: ignore[union-attr]
        ],
    )
    add("")
    shared_rows = [
        row
        for row in rows
        if needs_table_type(str(row["endpoint"]))
    ]
    with_literal = [
        row
        for row in shared_rows
        if row["metadata_json"].get("table_type")  # type: ignore[union-attr]
    ]
    add(
        f"Of the **{len(shared_rows)}** emitted rows on a shared result-table URI, "
        f"**{len(with_literal)}** carry a literal `metadata_json.table_type`.  The "
        "`TABLE_TYPE` slug in `interface_code` is still derived from the title for "
        "every one of them, so the codes are unchanged; the literal is the manual's "
        "own statement of the same fact and is what a caller should send."
    )
    add("")

    # ---- 4. operation mapping -----------------------------------------
    add("## 4. The operation mapping")
    add("")
    _table(
        add,
        ("method", "operation", "condition"),
        [(f"`{method}`", f"`{op}`", note) for method, op, note in operations],
    )
    add("")
    add(
        "Query is checked before execute because the manual has titles such as "
        "`RC Beam Design Perform` and `Beam Force - Analysis Result Table`; reading "
        "the second as an execution would mis-file hundreds of result tables."
    )
    add("")
    _table(
        add,
        ("operation", "rows"),
        [(f"`{name}`", count) for name, count in stats["by_operation"].items()],
    )
    add("")

    # ---- 5. null-URI entries ------------------------------------------
    add("## 5. Entries with no URI")
    add("")
    add(
        "`inventory.json` records `uri: null` for a set of Gen entries.  The URIs are "
        "**not** absent from the manual: the Gen index table itself leaves the `URL` "
        "cell as `—` for those rows, and the manual then states the URI either as the "
        "entry title's own path prefix (`DESIGN/RC/KDS-41-20-2022/CMFT : …`) or in a "
        "one-cell table under an `Input URI` marker "
        "(`| **/DESIGN/RC/KDS-41-20-2022/CMFT** |`).  The previous revision looked "
        "only for `**{base url} + …**`, which is why it saw none of them.  This "
        "pipeline reads all three URI forms and recovers the URI, so those entries "
        "*are* emitted as rows; this section keeps the inventory's `null` auditable."
    )
    add("")
    for position, key in enumerate(manuals):
        entries = recon[key]["inventory_null_uri"]
        add(
            f"### 5.{position + 1} `{key}` — {len(entries)} entries with "
            "`uri: null` in `inventory.json`"
        )
        add("")
        if not entries:
            add("_none._")
            add("")
            continue
        _table(
            add,
            ("#", "title", "inventory line", "inventory methods", "URI recovered"),
            [
                (
                    item + 1,
                    f"`{entry['title']}`",
                    entry["line"],
                    ", ".join(str(m) for m in (entry["methods"] or [])),
                    "`{}`".format(
                        next(
                            (
                                rec["uri"]
                                for rec in manuals[key]["uris_recovered"]
                                if rec["title"] == entry["title"]
                            ),
                            "—",
                        )
                    ),
                )
                for item, entry in enumerate(entries)
            ],
        )
        add("")
    add("URIs recovered for index rows whose `URL` cell was `—`:")
    add("")
    _table(
        add,
        ("manual", "index line", "title", "chapter", "URI", "recovered from"),
        [
            (
                f"`{key}`",
                rec["line"],
                f"`{rec['title']}`",
                f"`{rec['chapter']}`",
                f"`{rec['uri']}`",
                f"`{rec['recovered_from']}`",
            )
            for key in manuals
            for rec in manuals[key]["uris_recovered"]
        ],
    )
    add("")
    _table(
        add,
        ("manual", "index rows stating no URL", "recovered", "still no URI", "recovery routes"),
        [
            (
                f"`{key}`",
                data["index_rows_without_url"],
                data["index_rows_without_url"] - data["index_rows_still_without_uri"],
                data["index_rows_still_without_uri"],
                ", ".join(
                    f"`{name}` {count}"
                    for name, count in data["uris_recovered_by_route"].items()
                )
                or "—",
            )
            for key, data in manuals.items()
        ],
    )
    add("")
    add(
        "The three rows that still document no URI are Gen entries whose own body says "
        "`| **{base url} +** |` — the manual names the marker and then states no path.  "
        "Emitting the bare base URL as an endpoint would be an invention, so they are "
        "counted here and not emitted."
    )
    add("")

    # ---- 6. interface_code disambiguation ------------------------------
    add("## 6. `interface_code` construction and disambiguation")
    add("")
    add(
        "`interface_code` is minted as `{adapter}.{family}.{path…}.{operation}`, with "
        "the table discriminator inserted before the operation when the URI is one "
        "of the shared result-table URIs.  Examples:"
    )
    add("")
    add("```text")
    add("midas_gen.db.cnld.read       GET    /db/CNLD")
    add("midas_gen.db.cnld.create     POST   /db/CNLD")
    add("midas_gen.db.cnld.update     PUT    /db/CNLD")
    add("midas_gen.db.cnld.delete     DELETE /db/CNLD")
    add("midas_gen.db.lcom_conc.read  GET    /db/LCOM-CONC")
    add("midas_gen.post.table.beam_force.query   POST /post/TABLE   (TABLE_TYPE=BEAMFORCE)")
    add("midas_cdn.doc.open.create    POST   /doc/open")
    add("```")
    add("")
    add(
        "Two discriminators exist, and neither is a numeric suffix:"
    )
    add("")
    add(
        "1. **Operation** — the method is part of the code, so a four-method URI "
        "produces four distinct codes by construction.  The previous revision "
        "emitted `midas_gen.db.cnld`, `.2`, `.3`, `.4`, which made the code carry no "
        "information."
    )
    add(
        "2. **Table type** — `/post/TABLE` and `/DESIGN/**/TABLE` are one URI each "
        "carrying hundreds of result tables selected by `TABLE_TYPE` inside the "
        "`Argument` (总纲 裁决 B-3).  The title names the table, so the title becomes "
        "the discriminator."
    )
    add("")
    table_rows = sum(
        1
        for row in rows
        if row["metadata_json"]["interface_code_disambiguation"]  # type: ignore[index]
    )
    add(
        f"**{table_rows}** rows carry a table-type discriminator.  Rows per family:"
    )
    add("")
    _table(
        add,
        ("family", "rows"),
        [
            (f"`{name}`", count)
            for name, count in sorted(
                collections.Counter(
                    uri_family(str(row["endpoint"])) or "?" for row in rows
                ).items(),
                key=lambda item: (-item[1], item[0]),
            )
        ],
    )
    add("")
    add(
        "`endpoint` alone is **not** unique, on purpose: the shared table URIs carry "
        "one row per `TABLE_TYPE` on the same URI and method.  "
        f"**{len(report_data['shared_endpoints'])}** `(adapter, endpoint, method)` "
        "triples carry more than one row; the top 20:"
    )
    add("")
    _table(
        add,
        ("adapter", "endpoint", "method", "rows"),
        [
            (f"`{key[0]}`", f"`{key[1]}`", f"`{key[2]}`", count)
            for key, count in sorted(
                report_data["shared_endpoints"].items(), key=lambda item: (-item[1], item[0])
            )[:20]
        ],
    )
    add("")
    add("### 6.1 Records that did not become their own row")
    add("")
    # This list is **not** only merges.  A record that documents no URI never
    # becomes a row either, and it lands here with its own ``reason`` — so the
    # table must tolerate a missing ``endpoint`` and must show the reason,
    # otherwise the merge count silently absorbs the skipped entries.
    by_reason: collections.Counter[str] = collections.Counter(
        str(item.get("reason") or "?") for item in merges
    )
    for reason, count in by_reason.most_common():
        add(f"- `{reason}`: **{count}**")
    add("")
    add(f"**{len(merges)}** records total.  The first 60:")
    add("")
    _table(
        add,
        ("adapter", "endpoint", "method", "reason", "kept line", "merged line", "merged section"),
        [
            (
                f"`{item.get('adapter_code')}`",
                f"`{item.get('endpoint') or item.get('title') or '—'}`",
                f"`{item.get('method') or '—'}`",
                f"`{item.get('reason')}`",
                item.get("kept_line"),
                item.get("merged_line") if item.get("merged_line") is not None else item.get("line"),
                f"`{item.get('merged_section') or item.get('chapter') or '—'}`",
            )
            for item in merges[:60]
        ],
    )
    add("")
    add("### 6.2 Interface codes qualified to stay unique")
    add("")
    qualified = report_data["qualified"]
    if qualified:
        add(
            f"**{len(qualified)}** rows needed more than the method and the table "
            "discriminator to be unique: the URI carries two genuinely different "
            "interfaces whose titles are identical, so the code is qualified with the "
            "manual line the interface is documented at.  Every one is listed so it "
            "can be reviewed:"
        )
        add("")
        _table(
            add,
            ("adapter", "base code", "qualified code", "endpoint", "method", "line", "title"),
            [
                (
                    f"`{item['adapter_code']}`",
                    f"`{item['base_code']}`",
                    f"`{item['qualified_code']}`",
                    f"`{item['endpoint']}`",
                    f"`{item['method']}`",
                    item["source_line"],
                    f"`{item['title']}`",
                )
                for item in qualified[:80]
            ],
        )
    else:
        add(
            "_None._  The method plus the table discriminator made every "
            "`(adapter_code, interface_code)` unique on this run."
        )
    add("")

    # ---- 7. domain / feature ------------------------------------------
    add("## 7. Rows per `domain` and per `feature`")
    add("")
    _table(
        add,
        ("domain", "rows"),
        [
            (f"`{name}`", count)
            for name, count in sorted(
                stats["by_domain"].items(), key=lambda item: (-item[1], item[0])
            )
        ],
    )
    add("")
    _table(
        add,
        ("feature", "domain", "rows"),
        [
            (f"`{name}`", f"`{CAPABILITY_FEATURE_DOMAIN.get(name, '')}`", count)
            for name, count in sorted(
                stats["by_feature"].items(), key=lambda item: (-item[1], item[0])
            )
        ],
    )
    add("")
    add(
        "Feature attribution provenance (`chapter_table` = the manual's own "
        "`所在章节` column resolved through a table, `chapter_files` = the URI is listed "
        "by one of the 27 chapter files in `MIDAS-API-main/docs/manual/`, "
        "`fallback` = keyword rule, `unmapped` = no feature emitted).  The manual's own "
        "filing wins when it names a chapter, because that is the manual's own "
        "statement about where the endpoint belongs:"
    )
    add("")
    _table(
        add,
        ("provenance", "entry records"),
        [(f"`{name}`", count) for name, count in sorted(provenance.items())],
    )
    add("")
    unmapped = [
        row for row in rows if row["feature"] is None
    ]
    if unmapped:
        add(f"**{len(unmapped)}** rows have no `feature` (the column is nullable):")
        add("")
        _table(
            add,
            ("endpoint", "title", "chapter"),
            [
                (
                    f"`{row['endpoint']}`",
                    f"`{row['metadata_json']['source_title']}`",
                    f"`{row['metadata_json']['source_chapter']}`",
                )
                for row in unmapped[:40]
            ],
        )
        add("")
    else:
        add("No row was left without a `feature`.")
        add("")

    # ---- 8. unknown families ------------------------------------------
    add("## 8. The unknown-family branch")
    add("")
    if unknown:
        add(
            "These endpoints' first path segment is not one of "
            "`db`, `doc`, `ope`, `view`, `post`, `info`, `design`, so §3.1's wrapper "
            "rule does not cover them and both `request_wrapper` and "
            "`response_root_key` are left `null`:"
        )
        add("")
        _table(
            add,
            ("family", "entry records"),
            [(f"`{name}`", count) for name, count in sorted(unknown.items())],
        )
    else:
        add(
            "_None._  Every emitted endpoint's first path segment is one of "
            "`db`, `doc`, `ope`, `view`, `post`, `info`, `design`."
        )
    add("")
    add("Wrapper and response-root-key distribution:")
    add("")
    _table(
        add,
        ("`request_wrapper`", "rows"),
        [(f"`{name}`", count) for name, count in stats["by_wrapper"].items()],
    )
    add("")
    add(
        f"`response_root_key` is `null` on **{stats['null_root_key']}** rows — every "
        "non-`/db/*` row, by §3.2."
    )
    add("")

    # ---- 9. contradictions --------------------------------------------
    add("## 9. Where the manuals contradict `inventory.json`")
    add("")
    for position, (key, data) in enumerate(manuals.items()):
        recon_key = recon[key]
        add(f"### 9.{position + 1} `{key}`")
        add("")
        add(
            f"- manual: **{data['lines']:,}** lines; inventory entries: "
            f"**{recon_key['inventory_entries']}**; index rows: "
            f"**{recon_key['index_rows']}**; entry records: **{recon_key['records']}**"
        )
        add(
            f"- inventory entries with `uri: null`: **{len(recon_key['inventory_null_uri'])}**; "
            f"index rows whose `URL` cell is `—`: **{data['index_rows_without_url']}** "
            "(the two sets are not the same: an entry can have a URL in the index table "
            "and `null` in the inventory, or the other way round)"
        )
        add(
            f"- unique URIs — inventory **{recon_key['inventory_uris']}**, "
            f"index table **{recon_key['index_uris']}**, bodies **{recon_key['body_uris']}**, "
            f"joined **{recon_key['joined_uris']}**"
        )
        add(
            f"- URIs in `inventory.json` but in neither the index table nor a body: "
            f"**{recon_key['inventory_uris_missing_from_manual']}**"
        )
        add(
            f"- URIs in the manual but not in `inventory.json`: "
            f"**{recon_key['manual_uris_missing_from_inventory']}**"
        )
        add("")
        if recon_key["inventory_missing_examples"]:
            add("Inventory-only URIs (first 30):")
            add("")
            add("```text")
            for uri in recon_key["inventory_missing_examples"]:
                add(uri)
            add("```")
            add("")
        if recon_key["manual_missing_examples"]:
            add("Manual-only URIs (first 30):")
            add("")
            add("```text")
            for uri in recon_key["manual_missing_examples"]:
                add(uri)
            add("```")
            add("")
    add("### 9.4 Encoding damage")
    add("")
    _table(
        add,
        ("manual", "lines", "lines with U+FFFD", "lines with mojibake", "lines with U+200B"),
        [
            (f"`{key}`", f"{data['lines']:,}", data["fffd_lines"], data["mojibake_lines"], data["zwsp_lines"])
            for key, data in manuals.items()
        ],
    )
    add("")
    add(
        "Read with `errors=\"replace\"`; U+200B is stripped from every line before "
        "matching (the Gen manual writes `** {base url} + db/CNLD**\\u200b` on some "
        "entries and `**{base url} + db/ACTL**` on others), and the occurrence count "
        "is reported rather than swallowed.  Mojibake is reported, never repaired."
    )
    add("")
    add(
        "`inventory.json`'s `line` numbers are **stale** — the Gen manual has "
        f"**{manuals['gen']['lines']:,}** lines while the inventory's last Gen entry "
        "claims 410,979.  This pipeline therefore matches **by URI** and copies the "
        "*current* manual's line into `metadata_json.source_line`."
    )
    add("")

    # ---- 10. not extracted --------------------------------------------
    add("## 10. What could not be extracted, and why")
    add("")
    add(
        "1. **Civil Designer has no JSON Schema anywhere.**  Its 38 interfaces "
        "document `请求示例` and parameter tables (`参数名 | 数据类型 | 必填 | 说明`) "
        "only.  Their `request_schema_json` is therefore the request **example**, "
        "tagged `request_example`, or `null` when even that is absent — a parameter "
        "table is not a schema and is not turned into one here."
    )
    add(
        "2. **The Chinese backbone's `Input Data Form` is not draft-07 — and its "
        "blocks are not always reachable.**  It gives `__DESC__` (description) and "
        "`__TYPE__` (type) per key and nothing else: no `required`, no `enum`, no "
        "`default`.  The marker is recognised, but two things in the manual keep it "
        "from winning.  Either the block is introduced by "
        "`- {base url} + info/db/<code>` followed by a **four-space-indented** fence, "
        "which this pipeline's fence rule (up to three spaces) does not treat as a "
        "fence at all; or it is introduced by `**{base url} + info/db/<code>**`, which "
        "is itself a claim for the same URI and therefore ends the enclosing claim's "
        "span one line early.  Measured: `input_data_form` is 0 both before and after "
        "this revision.  Where a fence *is* reachable the block is attached verbatim "
        "and tagged `example` (it is a JSON object, so it is a usable body), and those "
        "rows are superseded by the English `json_schema` wherever the English section "
        "documents the same URI — which §3 counts."
    )
    add(
        "3. **`/post/*` and `/DESIGN/**/TABLE` share one URI per family.**  The "
        "`TABLE_TYPE` that selects the actual table lives inside the `Argument`.  The "
        "entry title is the discriminator the `interface_code` carries, and the "
        "**literal** the entry's own text states is recorded in "
        "`metadata_json.table_type` (§3.2).  A consumer must send the matching "
        "`TABLE_TYPE`; the code says which, and the metadata now says what the manual "
        "called it."
    )
    add(
        "4. **`product_scope` is `unknown` for every row.**  The manuals' `Active "
        "Programs` / product labels are unreliable (对接规范 §3.5 第 15 条: 32 of 47 "
        "endpoints declared \"Civil-only\" answer on Gen NX too), so real values must "
        "come from live probing.  Emitting a label here would launder a manual claim "
        "into a capability."
    )
    add(
        "5. **Entries with no URI** are recovered from the manual wherever the manual "
        "states the path (§5), including the 13 Gen entries that `inventory.json` "
        "records as `uri: null`.  Gen's index table states no URL for "
        f"**{manuals['gen']['index_rows_without_url']}** rows; "
        f"**{manuals['gen']['index_rows_without_url'] - manuals['gen']['index_rows_still_without_uri']}** "
        "of them were recovered from the entry's own title path or body, and "
        f"**{manuals['gen']['index_rows_still_without_uri']}** document no path "
        "anywhere — their body says `| **{base url} +** |`.  Those are counted and "
        "listed, not emitted with an invented endpoint."
    )
    add(
        "6. **`domain` is never inferred independently.**  It comes from "
        "`CAPABILITY_FEATURE_DOMAIN` once `feature` is known, so the three-layer "
        "hierarchy cannot drift."
    )
    add("")

    # ---- 11. the Chinese annotation ------------------------------------
    add("## 11. The Chinese annotation (`title_zh.json`)")
    add("")
    annotations = report_data["annotations"]  # type: ignore[assignment]
    add(
        "The registry is an **API catalogue**, and the manuals' Chinese and English "
        "sections document the *same* endpoints — so the language of the section a row "
        "was read from says nothing about who can use it.  What matters is that every "
        "API can be found and understood by a Chinese-speaking user and by the LLM "
        "(总纲 §4.2.13: `capabilities.description` is the annotation's documented "
        "home).  Every row therefore carries:"
    )
    add("")
    add(
        "- `title` — the `接口名称` cell's markdown link with the link removed, "
        "unwrapped with the **same** expression the glossary used to key its entries "
        "(`re.match(r\"\\[(.*?)\\]\\([^)]*\\)\\s*$\", t)`);"
    )
    add(
        "- `description` — `name_zh + \"：\" + description_zh` when both exist, "
        "`name_zh` alone when only that exists, and `null` otherwise.  Nothing is "
        "invented: a title the glossary does not carry leaves it `null`;"
    )
    add(
        "- `metadata_json.annotation_source` — `manual` (the manual ships the Chinese) "
        "or `glossary` (`title_zh.json` supplied it), so a reviewer can tell the two "
        "apart, plus `metadata_json.annotation_key`, the glossary key that matched."
    )
    add("")
    _table(
        add,
        ("item", "value"),
        [
            ("glossary file", f"`{annotations['glossary_path'] or TITLE_ZH_PATH}`"),
            (
                "status",
                f"`{annotations['glossary_status']}` — {annotations['glossary_detail']}",
            ),
            (
                "titles usable / declared",
                f"{annotations['glossary_titles']} / "
                f"{annotations['glossary_declared_total']}",
            ),
            ("glossary complete", "yes" if annotations["glossary_complete"] else "no"),
            ("entries without `name_zh`", annotations["glossary_entries_without_name"]),
            (
                "rows annotated",
                f"{annotations['rows_annotated']} / {annotations['rows']} "
                f"({annotations['rows_annotated_pct']}%)",
            ),
            (
                "distinct titles annotated",
                f"{annotations['titles_annotated']} / {annotations['distinct_titles']} "
                f"({annotations['titles_annotated_pct']}%)",
            ),
            ("glossary entries never used", annotations["entries_never_used"]),
        ],
    )
    add("")
    add("Annotated rows per `source`:")
    add("")
    _table(
        add,
        ("source", "rows"),
        [
            (f"`{name}`", count)
            for name, count in annotations["rows_by_source"].items()
        ],
    )
    add("")
    add(
        "`<none>` is the honest answer, not a defect: a title the glossary does not "
        "carry leaves the annotation `null`, and the seeder then leaves "
        "`capabilities.description` alone rather than writing a blank over a curated "
        "value.  A **missing or malformed** glossary produces the same kind of answer — "
        "this pipeline emits the identical row set without it, because the glossary is "
        "curated data that another task owns."
    )
    add("")
    unmatched_examples = annotations["unmatched_title_examples"]
    if unmatched_examples:
        add(
            f"Titles with no glossary entry (**{annotations['distinct_titles'] - annotations['titles_annotated']}** "
            f"distinct titles; first {len(unmatched_examples)}):"
        )
        add("")
        add("```text")
        for title in unmatched_examples:
            add(title)
        add("```")
        add("")
    unused_examples = annotations["entries_never_used_examples"]
    if unused_examples:
        add(
            f"Glossary entries no row ever looked up (**{annotations['entries_never_used']}**; "
            f"first {len(unused_examples)}) — a large number here means the glossary's "
            "keys and the rows' titles are spelled differently:"
        )
        add("")
        add("```text")
        for key in unused_examples:
            add(key)
        add("```")
        add("")

    # ---- 12. validation -----------------------------------------------
    add("## 12. Self-validation")
    add("")
    checks = report_data["verification"]  # type: ignore[assignment]
    if checks:
        add("The pipeline re-opened its own output and found these problems:")
        add("")
        add("```text")
        for problem in checks:
            add(problem)
        add("```")
    else:
        add(
            "The pipeline re-opened `interfaces.json` and re-validated it: every "
            "required field present, `product_scope` in the closed set, every "
            "`feature` in the closed set and consistent with `domain`, "
            "`(adapter_code, interface_code)` unique, every `request_schema_json` "
            "parseable as a JSON object, every row's `method` in the HTTP set, and "
            "`title` / `description` present on every row — with a non-empty "
            "`metadata_json.annotation_source` and a matched `annotation_key` "
            "whenever the row carries an annotation."
        )
        add("")
        add(
            "It then checked the **collection** against the manuals' own marker "
            "counts, because a file can be perfectly well formed and still be missing "
            "most of what the manual states:"
        )
        add("")
        add(
            "- the index table of every manual parsed to a non-zero row count — the "
            "`index_rows=0` / `anomalies=0` silent zero that started this;"
        )
        add(
            "- every `##` section holding `JSON Schema` markers has claims — a "
            "section with markers and no entry is the same silent zero in a smaller "
            "place;"
        )
        add(
            "- for every section holding at least "
            f"**{SCHEMA_ATTACHMENT_MIN_HEADINGS}** `JSON Schema` markers, at least "
            f"**{SCHEMA_ATTACHMENT_FLOOR:.0%}** of them were attached as "
            "`json_schema`; smaller sections must attach at least one;"
        )
        add(
            "- no manual reports `JSON Schema` markers with zero schemas attached."
        )
        add("")
        add(
            "Measured on this run: "
            + ", ".join(
                f"`{key}` {totals[0]} marker(s) / {totals[1]} attached"
                for key, totals in schema_totals.items()
            )
            + ".  A shortfall exits non-zero **instead of** writing this report, so a "
            "wrong count can never be mistaken for a clean run."
        )
        add("")
        add(
            "It also checked the **Chinese annotation** against the glossary: when "
            "`title_zh.json` is present and complete, at least "
            f"**{ANNOTATION_COVERAGE_FLOOR:.0%}** of the rows and of the distinct titles "
            "must carry an annotation.  A complete glossary that matches almost nothing "
            "means the unwrap rule and the glossary's keys disagree — the same "
            "silent-zero shape as `index_rows=0`, in a new place.  A missing, malformed "
            "or still-being-filled glossary is reported in §11 and does **not** fail the "
            "run: this pipeline must emit the same rows without it."
        )
    add("")


def build_operation_table() -> list[tuple[str, str, str]]:
    """The operation mapping as report rows (method, operation, condition)."""
    return [
        ("GET", "read", "always"),
        ("PUT", "update", "always"),
        ("DELETE", "delete", "always"),
        ("PATCH", "update", "always"),
        ("POST", "query", "title contains one of " + ", ".join(f"`{t}`" for t in QUERY_TITLE_TOKENS) + " (checked first)"),
        ("POST", "execute", "title contains one of " + ", ".join(f"`{t}`" for t in EXECUTE_TITLE_TOKENS)),
        ("POST", "create", "otherwise"),
    ]


# ---------------------------------------------------------------------------
# output verification
# ---------------------------------------------------------------------------
REQUIRED_ROW_FIELDS: tuple[str, ...] = (
    "adapter_code",
    "interface_code",
    "method",
    "endpoint",
    "request_wrapper",
    "response_root_key",
    "operation",
    "resource",
    # 总纲 §4.2.13 — the unwrapped title and the Chinese annotation.  Both must be
    # *present* (either may be ``null``): a row that lost them is a regression in
    # this file, and a missing key is exactly the silent gap this list catches.
    "title",
    "description",
    "product_scope",
    "domain",
    "feature",
    "request_schema_json",
    "metadata_json",
)

OPERATIONS: frozenset[str] = frozenset({"create", "read", "update", "delete", "query", "execute"})

#: ``(adapter, endpoint, method)`` triples that carry more than one row.  Filled by
#: :func:`verify_output`; the report prints it so the shared-table exception is
#: visible rather than looking like a duplicate-row bug.
_SHARED_ENDPOINTS: dict[tuple[str, str, str], int] = {}


def verify_collection(manuals: dict[str, dict[str, object]]) -> list[str]:
    """Cross-check the collection against the manuals' own marker counts.

    :func:`verify_output` proves the *file* is well formed; this proves the
    *collector* actually read the manuals.  The previous revision emitted
    ``index_rows=0`` with ``anomalies=0`` — a silent zero — and later found 2 body
    claims in a Gen section holding hundreds of ``JSON Schema`` markers.  Both are
    the same failure: a count that is wrong but not obviously wrong, which is worse
    than a crash because nothing points at it.

    So the markers the collector saw are compared, per ``##`` section, against the
    schemas it attached, and a shortfall is returned as a problem — which makes
    :func:`main` exit non-zero rather than write a plausible-looking report.
    """
    problems: list[str] = []
    for key, data in manuals.items():
        index_meta = data["index"]
        rows = int(index_meta["rows"])  # type: ignore[index]
        if rows == 0:
            problems.append(
                f"{key}: the index table parsed as 0 rows — the silent-zero failure "
                "this check exists for"
            )
        sections = data["section_schemas"]
        headings_total = 0
        attached_total = 0
        for item in sections:  # type: ignore[union-attr]
            headings = int(item["schema_headings"])
            attached = int(item["json_schema_attached"])
            claims = int(item["claims"])
            headings_total += headings
            attached_total += attached
            if headings == 0:
                continue
            if claims == 0:
                problems.append(
                    f"{key}: section {item['section']!r} states {headings} "
                    "`JSON Schema` marker(s) and the collector found no entry at all "
                    "in it"
                )
                continue
            if headings < SCHEMA_ATTACHMENT_MIN_HEADINGS:
                if attached == 0:
                    problems.append(
                        f"{key}: section {item['section']!r} states {headings} "
                        "`JSON Schema` marker(s) and attached none"
                    )
                continue
            if attached < headings * SCHEMA_ATTACHMENT_FLOOR:
                problems.append(
                    f"{key}: section {item['section']!r} states {headings} "
                    f"`JSON Schema` markers but only {attached} schemas were attached "
                    f"(floor {SCHEMA_ATTACHMENT_FLOOR:.0%})"
                )
        if headings_total and attached_total == 0:
            problems.append(
                f"{key}: {headings_total} `JSON Schema` markers seen and 0 attached"
            )
    return problems


def verify_output(path: str) -> list[str]:
    """Re-open *path* and re-validate it; return the list of problems.

    This is the pipeline's own contract check (the task requires a non-zero exit
    on failure), so it re-reads the file from disk rather than trusting the
    in-memory rows.
    """
    problems: list[str] = []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as error:
        return [f"interfaces.json is not readable JSON: {error}"]

    if not isinstance(payload, dict):
        return ["interfaces.json top level is not an object"]
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return ["interfaces.json has no 'rows' list"]

    seen: dict[tuple[str, str], int] = {}
    endpoint_seen: collections.Counter[tuple[str, str, str]] = collections.Counter()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            problems.append(f"row {index}: not an object")
            continue
        for field in REQUIRED_ROW_FIELDS:
            if field not in row:
                problems.append(f"row {index}: missing required field {field!r}")
        adapter = row.get("adapter_code")
        if adapter not in set(ADAPTER_CODES.values()):
            problems.append(f"row {index}: adapter_code {adapter!r}")
        code = row.get("interface_code")
        if not isinstance(code, str) or not code:
            problems.append(f"row {index}: interface_code {code!r}")
        else:
            key = (str(adapter), code)
            if key in seen:
                problems.append(
                    f"row {index}: duplicate (adapter_code, interface_code) {key} "
                    f"(first at row {seen[key]})"
                )
            else:
                seen[key] = index
        method = row.get("method")
        if method not in METHOD_ORDER:
            problems.append(f"row {index}: method {method!r}")
        endpoint = row.get("endpoint")
        if not isinstance(endpoint, str) or not endpoint.startswith("/"):
            problems.append(f"row {index}: endpoint {endpoint!r}")
        elif method in METHOD_ORDER:
            endpoint_seen[(str(adapter), endpoint, str(method))] += 1
        scope = row.get("product_scope")
        if scope not in MIDAS_PRODUCT_SCOPE_VALUES:
            problems.append(f"row {index}: product_scope {scope!r}")
        if scope != EMITTED_PRODUCT_SCOPE:
            problems.append(f"row {index}: product_scope {scope!r} is not the emitted value")
        domain = row.get("domain")
        if domain is not None and domain not in DOMAIN_SET:
            problems.append(f"row {index}: domain {domain!r}")
        feature = row.get("feature")
        if feature is not None:
            if feature not in FEATURE_SET:
                problems.append(f"row {index}: feature {feature!r}")
            elif domain is not None and CAPABILITY_FEATURE_DOMAIN.get(str(feature)) != domain:
                problems.append(
                    f"row {index}: feature {feature!r} -> domain {domain!r} mismatch"
                )
        operation = row.get("operation")
        if operation not in OPERATIONS:
            problems.append(f"row {index}: operation {operation!r}")
        title = row.get("title")
        if title is not None and (not isinstance(title, str) or not title.strip()):
            problems.append(f"row {index}: title {title!r} is neither a string nor null")
        description = row.get("description")
        if description is not None and (
            not isinstance(description, str) or not description.strip()
        ):
            problems.append(
                f"row {index}: description {description!r} is neither a non-empty "
                "string nor null"
            )
        wrapper = row.get("request_wrapper")
        if wrapper not in (None, WRAPPER_ASSIGN, WRAPPER_ARGUMENT):
            problems.append(f"row {index}: request_wrapper {wrapper!r}")
        schema = row.get("request_schema_json")
        if schema is not None:
            if not isinstance(schema, str):
                problems.append(f"row {index}: request_schema_json is not a string")
            else:
                try:
                    parsed = json.loads(schema)
                except ValueError as error:
                    problems.append(f"row {index}: request_schema_json not parseable: {error}")
                else:
                    if not isinstance(parsed, dict):
                        problems.append(f"row {index}: request_schema_json is not an object")
            if method not in BODY_METHODS:
                problems.append(
                    f"row {index}: request_schema_json on a non-body method {method!r}"
                )
        metadata = row.get("metadata_json")
        if not isinstance(metadata, dict):
            problems.append(f"row {index}: metadata_json is not an object")
        else:
            try:
                json.dumps(metadata)
            except (TypeError, ValueError) as error:
                problems.append(f"row {index}: metadata_json not serialisable: {error}")
            # The annotation's provenance (总纲 §4.2.13).  ``description`` and the
            # glossary key that produced it are one fact, so they must agree: a key
            # with no description would mean an annotation was claimed and then lost.
            # The ``source`` *value* is the glossary's vocabulary and is only
            # reported (never validated here): inventing a failure for a value it
            # adds would make this pipeline its gatekeeper.
            annotation_source = metadata.get("annotation_source")
            if annotation_source is not None and (
                not isinstance(annotation_source, str) or not annotation_source.strip()
            ):
                problems.append(
                    f"row {index}: metadata_json.annotation_source "
                    f"{annotation_source!r} is neither a non-empty string nor null"
                )
            annotation_key = metadata.get("annotation_key")
            if annotation_key is not None and not isinstance(annotation_key, str):
                problems.append(
                    f"row {index}: metadata_json.annotation_key {annotation_key!r}"
                )
            if (description is None) != (annotation_key is None):
                problems.append(
                    f"row {index}: description {description!r} and "
                    f"metadata_json.annotation_key {annotation_key!r} disagree about "
                    "whether this row is annotated"
                )
            if description is None and annotation_source is not None:
                problems.append(
                    f"row {index}: metadata_json.annotation_source "
                    f"{annotation_source!r} on a row with no annotation"
                )
    # ``(adapter, endpoint, method)`` is *not* unique on purpose: the shared table
    # URIs legitimately carry one row per ``TABLE_TYPE``.  The count is reported so
    # the exception stays visible instead of looking like a bug.
    _SHARED_ENDPOINTS.clear()
    _SHARED_ENDPOINTS.update(
        {key: count for key, count in endpoint_seen.items() if count > 1}
    )
    return problems


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> int:
    inventory = load_inventory()
    for key in MANUAL_PATHS:
        if key not in inventory:
            raise SystemExit(f"{INVENTORY_PATH}: missing key {key!r}")
    uri_feature, file_feature = load_chapter_feature_map()

    # The Chinese annotation glossary is read **once**, and a missing or malformed
    # file is a degradation rather than a failure (see :func:`load_title_zh`): the
    # row set must be the same with or without it.
    glossary = load_title_zh()
    titles_zh: dict[str, dict[str, object]] = glossary["titles"]  # type: ignore[assignment]
    print(
        f"annotation glossary: {glossary['status']} — {glossary['detail']}",
        file=sys.stderr,
    )

    manuals: dict[str, dict[str, object]] = {}
    recon: dict[str, dict[str, object]] = {}
    all_rows: list[dict[str, object]] = []
    all_merges: list[dict[str, object]] = []
    all_qualified: list[dict[str, object]] = []
    unknown_families: collections.Counter[str] = collections.Counter()
    provenance: collections.Counter[str] = collections.Counter()

    for key, path in MANUAL_PATHS.items():
        index = ManualIndex(key, path)
        recovered = attach_recovered_uris(index)
        records = entry_records(index)
        rows, merges, unknown, prov, qualified = build_rows(
            key, records, index, uri_feature, titles_zh
        )
        all_rows.extend(rows)
        all_merges.extend(merges)
        all_qualified.extend(qualified)
        unknown_families.update(unknown)
        provenance.update(prov)
        recon[key] = reconcile(key, records, index, inventory[key])
        manuals[key] = {
            "path": path,
            "lines": len(index.lines),
            "fffd_lines": index.replacements,
            "mojibake_lines": index.mojibake_lines,
            "zwsp_lines": index.zero_width_lines,
            "index": index.index_metadata(),
            "code_present": sum(1 for row in index.index_rows if row["code"]),
            "code_absent": sum(1 for row in index.index_rows if not row["code"]),
            "index_rows_without_url": sum(
                1 for row in index.index_rows if not row["url_raw"] or row["url_raw"] in DASHES
            ),
            "index_rows_still_without_uri": sum(
                1 for row in index.index_rows if row["uri"] is None
            ),
            "uris_recovered_by_route": dict(
                collections.Counter(
                    str(rec["recovered_from"]) for rec in recovered
                ).most_common()
            ),
            "method_strings": dict(
                collections.Counter(str(row["methods_raw"]) for row in index.index_rows).most_common()
            ),
            "chapters": dict(
                collections.Counter(str(row["chapter"]) for row in index.index_rows).most_common()
            ),
            "subchapters": dict(
                collections.Counter(
                    " / ".join(part.strip() for part in str(row["chapter"]).split("/")[1:])
                    for row in index.index_rows
                    if "/" in str(row["chapter"])
                ).most_common()
            ),
            "rows_by_section": dict(
                collections.Counter(str(row["section"]) for row in index.index_rows).most_common()
            ),
            "sections": [title for _, title in index.sections],
            "body_claims": len(index.claims()),
            "body_uris": len(index.body_uris()),
            "schema_kinds": dict(
                collections.Counter(
                    str(claim["schema_source"] or "none") for claim in index.claims()
                ).most_common()
            ),
            "schema_by_section": [
                {"section": section, "kind": kind, "count": count}
                for (section, kind), count in collections.Counter(
                    (str(claim["section"]), str(claim["schema_source"] or "none"))
                    for claim in index.claims()
                ).most_common()
            ],
            "section_schemas": section_schema_report(index),
            "uri_marker_forms": dict(
                collections.Counter(
                    uri_marker_form(index.lines[line]) for line in index.uri_markers
                ).most_common()
            ),
            "schema_markers_by_section": dict(
                collections.Counter(
                    index.section_of(line) for line in index.schema_markers
                ).most_common()
            ),
            "table_types": table_type_report(index),
            "rows_out": len(rows),
            "merged_out": len(merges),
            "uris_recovered": recovered,
        }
        marker_total = len(index.schema_markers)
        attached_total = sum(
            int(item["json_schema_attached"])
            for item in manuals[key]["section_schemas"]  # type: ignore[union-attr]
        )
        print(
            f"[{key}] lines={len(index.lines):,} index_rows={len(index.index_rows)} "
            f"body_claims={len(index.claims())} records={len(records)} rows={len(rows)} "
            f"merges={len(merges)} schema_markers={marker_total} "
            f"json_schema_attached={attached_total}",
            file=sys.stderr,
        )

    stats = coverage(all_rows)
    annotations = annotation_report(all_rows, glossary)
    print(
        "annotation: rows_annotated={annotated}/{rows} ({rows_pct}%) "
        "titles_annotated={titles}/{distinct} ({titles_pct}%) "
        "by_source={by_source} entries_never_used={unused}".format(
            annotated=annotations["rows_annotated"],
            rows=annotations["rows"],
            rows_pct=annotations["rows_annotated_pct"],
            titles=annotations["titles_annotated"],
            distinct=annotations["distinct_titles"],
            titles_pct=annotations["titles_annotated_pct"],
            by_source=annotations["rows_by_source"],
            unused=annotations["entries_never_used"],
        ),
        file=sys.stderr,
    )
    if annotations["glossary_status"] != "ok" or not annotations["glossary_complete"]:
        print(
            "annotation WARNING: the glossary is not a complete, readable table "
            f"({annotations['glossary_status']}, "
            f"{annotations['glossary_titles']} of "
            f"{annotations['glossary_declared_total']} declared titles) — the rows "
            "carry null annotations and the coverage floor is not enforced.  This is "
            "reported, not fatal: the pipeline must run without the glossary.",
            file=sys.stderr,
        )
    payload = {
        "meta": {
            "generator": "docs/api-registry/extract_interfaces.py",
            "sources": {
                "inventory": INVENTORY_PATH,
                "manuals": MANUAL_PATHS,
                "chapters": CHAPTER_DIR,
            },
            "product_scope_policy": (
                "always 'unknown' — the manuals' product labels are unreliable "
                "(《MIDAS API 对接规范》§3.5 第 15 条); real values come from live probing"
            ),
            "annotation_policy": (
                "总纲 §4.2.13 — every row carries 'title' (the 接口名称 cell's markdown "
                "link, unwrapped with the glossary's own rule) and 'description' "
                "(name_zh + '：' + description_zh, or name_zh alone, or null).  A title "
                "the glossary does not carry leaves 'description' null: nothing is "
                "invented, and 'metadata_json.annotation_source' names the provenance"
            ),
            "title_zh_path": TITLE_ZH_PATH,
            "annotations": annotations,
            "row_identity": "(endpoint, method); interface_code folds the method in",
            "interface_code_shape": (
                "{adapter}.{family}.{path…}[.{table_type}].{operation}"
            ),
            "feature_values": list(FEATURE_VALUES),
            "domain_values": list(CAPABILITY_DOMAIN_VALUES),
            "product_scope_values": list(MIDAS_PRODUCT_SCOPE_VALUES),
            "adapter_codes": ADAPTER_CODES,
            "chapter_files": file_feature,
            "counts": {
                "rows": len(all_rows),
                "merged": len(all_merges),
                "per_adapter": stats["by_adapter"],
                "index_rows": {
                    key: int(data["index"]["rows"]) for key, data in manuals.items()
                },
                "entry_records": {key: int(recon[key]["records"]) for key in manuals},
            },
            "coverage": stats,
            "manuals": manuals,
            "reconciliation": recon,
            "unknown_families": dict(unknown_families),
            "feature_provenance": dict(provenance),
            "merged_records": all_merges,
            "qualified_interface_codes": all_qualified,
        },
        "rows": all_rows,
    }

    with open(OUT_JSON, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1, sort_keys=False)
    print(f"wrote {OUT_JSON}", file=sys.stderr)

    problems = verify_output(OUT_JSON)
    problems.extend(verify_collection(manuals))
    problems.extend(verify_annotations(annotations))
    if problems:
        print(f"OUTPUT VERIFICATION FAILED ({len(problems)} problems):", file=sys.stderr)
        for problem in problems[:60]:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    report_lines: list[str] = []

    def add(text: str = "") -> None:
        report_lines.append(text)

    write_report(
        {
            "add": add,
            "manuals": manuals,
            "rows": all_rows,
            "merges": all_merges,
            "coverage": stats,
            "reconcile": recon,
            "unknown_families": dict(unknown_families),
            "provenance": dict(provenance),
            "operation_table": build_operation_table(),
            "shared_endpoints": dict(_SHARED_ENDPOINTS),
            "qualified": all_qualified,
            "annotations": annotations,
            "verification": problems,
        }
    )
    with open(OUT_REPORT, "w", encoding="utf-8") as handle:
        handle.write("\n".join(report_lines).rstrip() + "\n")
    print(f"wrote {OUT_REPORT}", file=sys.stderr)

    print(
        "coverage: rows={rows} body_rows={body} schema_all={all_s}/{all_pct}% "
        "schema_body={body_s}/{body_pct}%".format(
            rows=stats["rows"],
            body=stats["body_rows"],
            all_s=stats["with_schema"],
            all_pct=stats["with_schema_pct"],
            body_s=stats["body_with_schema"],
            body_pct=stats["body_with_schema_pct"],
        ),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
