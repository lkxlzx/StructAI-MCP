#!/usr/bin/env python3
"""Extract ``tool_interfaces`` rows from the three normalised MIDAS API manuals.

Inputs
------
``G:\\MAPI\\tools\\inventory.json``
    The endpoint skeleton produced by ``G:\\MAPI\\tools\\extract.py``: for each
    product a list of ``{code, title, line, level, uri, methods, end}``.  ``code``
    is ``None`` for most entries and ``uri`` is ``None`` for a handful.
``G:\\MAPI\\docs\\midas Gen API 专用手册.md`` (410,728 lines)
``G:\\MAPI\\docs\\midas Civil NX API 专用手册.md`` (157,103 lines)
``G:\\MAPI\\docs\\midas Civil Designer API 专用手册.md`` (5,322 lines)
    The manuals.  They are streamed **line by line** — never read whole.

Outputs
-------
``docs/api-registry/interfaces.json``      ``{"meta": {...}, "rows": [...]}``
``docs/api-registry/EXTRACTION_REPORT.md`` the coverage report

Design notes
------------
* **``product_scope`` is always ``"unknown"``.**  The manuals' product labels are
  not trustworthy (《MIDAS API 对接规范》§3.5 第 15 条: of 47 endpoints declared
  "Civil-only", 32 answer on Gen NX too), so "not yet probed live" is emitted as
  itself rather than guessed.
* **The closed sets are imported, never duplicated.**  The ``feature`` values, the
  ``feature -> domain`` total function and the ``product_scope`` values all come
  from :mod:`app.core.constants`, so a word-list change cannot desync this
  pipeline.
* **The judgement calls are tables.**  Chapter -> feature, operation derivation and
  the family rules each live in exactly one place, so a reviewer can diff a table
  instead of reverse-engineering the control flow.
* The manual's own heading tree decides which chapter an entry lives in; the
  chapter decides ``feature``.  ``inventory.json`` supplies the entry *set* and the
  product, but its ``line`` numbers are **stale** (see §7 of the report) and are
  therefore never used to locate anything — matching is by URI.

Usage:  ``python extract_interfaces.py``
No third-party dependencies.  Python 3.12, full annotations.
"""

import bisect
import collections
import json
import os
import re
import sys

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

OUT_JSON = os.path.join(_HERE, "interfaces.json")
OUT_REPORT = os.path.join(_HERE, "EXTRACTION_REPORT.md")

# ---------------------------------------------------------------------------
# closed sets this pipeline may emit
# ---------------------------------------------------------------------------
#: ``inventory.json`` key -> ``adapters.code``.  ``app.core.midas_config`` derives
#: the same two codes as ``f"midas_{product.value}"`` for Gen and Civil
#: (``MidasConnection.to_registry_row``); Designer is the third product and
#: follows the same shape.
ADAPTER_CODES: dict[str, str] = {
    "gen": "midas_gen",
    "civilnx": "midas_civil",
    "designer": "midas_designer",
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

# ---------------------------------------------------------------------------
# endpoint families and request wrappers
# ---------------------------------------------------------------------------
#: Copied from ``app/adapters/midas_gen/adapter.py``'s ``_ENDPOINT_FAMILIES`` so
#: this pipeline and the adapter agree on what a family *is*.
ENDPOINT_FAMILIES: tuple[str, ...] = ("db", "doc", "ope", "view", "post", "info", "design")

WRAPPER_ASSIGN = "Assign"
WRAPPER_ARGUMENT = "Argument"

#: Families whose request body is an ``Argument`` object rather than an ``Assign``
#: map.  ``/RATING/**`` is included even though the adapter's family set does not
#: list it, because the manual documents it and §3.1's rule ("``/db/*`` is
#: ``Assign``, everything else is ``Argument``") covers it.
ARGUMENT_FAMILIES: frozenset[str] = frozenset(
    {"doc", "post", "ope", "view", "info", "design", "rating"}
)

# ---------------------------------------------------------------------------
# manual structural constants (measured by reading the files; see report §9)
# ---------------------------------------------------------------------------
GEN_JSON_SECTION = "JSON数据手册"
GEN_EN_INDEX_SECTION = "英文数据手册（索引接口）"
GEN_EN_UNINDEXED_SECTION = "英文数据手册（未编入索引）"
CIVILNX_JSON_SECTION = "JSON手册"
DESIGNER_JSON_SECTIONS: tuple[str, ...] = (
    "DOC 文档",
    "DB 数据库",
    "OPRT 操作",
    "VIEW 视图",
    "POST 后处理",
)

#: ``##`` sections that hold interface definitions, per manual.  Everything else
#: (preface, 目录, 接口总索引, the tutorial/API-primer chapters) contains headings
#: that look like entries but are prose, so extraction is fenced to these.
JSON_REGIONS: dict[str, tuple[str, ...]] = {
    "gen": (GEN_JSON_SECTION, GEN_EN_INDEX_SECTION, GEN_EN_UNINDEXED_SECTION),
    "civilnx": (CIVILNX_JSON_SECTION,),
    "designer": DESIGNER_JSON_SECTIONS,
}

#: Heading levels that may carry an interface entry, per manual *section*.
#: The Gen manual is the awkward one: its Chinese backbone nests interfaces at
#: ``#####``/``######`` under ``####`` groups, while both English sections put one
#: interface per ``####``.
GEN_ZH_ENTRY_LEVELS: tuple[int, ...] = (4, 5, 6)
GEN_EN_ENTRY_LEVELS: tuple[int, ...] = (4,)
CIVILNX_ENTRY_LEVELS: tuple[int, ...] = (4, 5)
DESIGNER_ENTRY_LEVELS: tuple[int, ...] = (3,)

#: Sub-block headings that are never interface entries.
BLOCK_TITLES: frozenset[str] = frozenset(
    {
        "input uri",
        "input uri (get)",
        "output uri",
        "active methods",
        "active programs",
        "json schema",
        "specifications",
        "examples",
        "example",
        "response examples",
        "request examples",
        "input data form",
        "input data example",
        "input data examples",
        "接口url",
        "支持的方法",
        "请求示例",
        "post请求参数",
        "get请求参数",
        "put请求参数",
        "delete请求参数",
        "get返回值",
        "get 返回值",
        "post 返回值",
        "get 返回值 / put 请求参数",
        "get 返回值 / post 请求参数",
    }
)

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
    "report",
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

# ---------------------------------------------------------------------------
# chapter -> feature
# ---------------------------------------------------------------------------
#: Chapter heading -> canonical feature, for the Gen manual's two English
#: sections.  Keys are normalised with :func:`normalise_heading`.  The tables are
#: exhaustive rather than clever: a heading that is not listed falls through to
#: :data:`FEATURE_FALLBACK` and is reported, never silently guessed.
#:
#: Several chapters have no canonical counterpart (the 27 features are the
#: MIDAS-API-main manual's table of contents, and the Gen manual's English index
#: splits a few topics differently).  Those are mapped to their nearest neighbour
#: and the choice is stated in the comment, because inventing a 28th feature would
#: break the closed set the frontend menu is built from.
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
    # No canonical hydration chapter exists; hydration is a construction-stage
    # load, so it joins that feature.
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
    # --- 英文数据手册（未编入索引） ---
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

#: Same, for the Gen manual's Chinese backbone (``## JSON数据手册``).  Its 13
#: categories are coarser than the 27 chapters, so several collapse onto one
#: feature — a mapping decision, not a loss of data.
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
    # Neither has a canonical chapter: Smart Report is a reporting front-end over
    # result tables (closest is the design-result chapter), and Seismic Perform.
    # is a design check.
    "smart report": "post_design",
    "seismic perform.": "db_design",
}

#: Civil NX chapters.
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
}

#: Designer chapters.
DESIGNER_CHAPTER_FEATURE: dict[str, str] = {
    "doc 文档": "doc",
    "db 数据库": "db_project_structure",
    "oprt 操作": "ope",
    "view 视图": "view",
    "post 后处理": "post_design",
}

#: Last resort when a heading is in none of the tables above.  Ordered
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
# small helpers
# ---------------------------------------------------------------------------
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_URI_WITH_BASE_RE = re.compile(
    r"(?:base\s*url|baseURL|\{base\s*url\})[^\n]*?\+\s*([A-Za-z0-9_/\-\.]+)", re.I
)
_URI_BARE_RE = re.compile(r"([A-Za-z][A-Za-z0-9_\-]*(?:/[A-Za-z0-9_\-\.]+)+)")
_METHOD_RE = re.compile(r"\b(GET|POST|PUT|DELETE|PATCH)\b", re.I)
_CODE_RE = re.compile(r"\[([A-Za-z][A-Za-z0-9_\-]*)\]")
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_BASE_URL_NOISE_RE = re.compile(r"^\{?\s*base\s*url\s*\}?\s*\+?", re.I)

#: Mojibake fingerprints observed in the Gen manual (``鎬荤翰`` where ``总纲`` was
#: meant).  Used for **reporting only** — never for repair.
MOJIBAKE_MARKERS: tuple[str, ...] = ("鎬荤翰", "涓", "鏂", "鐨", "鍜", "锛")


def read_lines(path: str) -> tuple[list[str], int]:
    """Read *path* as UTF-8 with replacement, returning ``(lines, replacements)``.

    ``errors="replace"`` is mandatory: the Gen manual contains mojibake in places,
    so a strict decode would abort on a file that is otherwise usable.  ``\\r`` is
    stripped because some of the sources are CRLF.
    """
    replaced = 0
    lines: list[str] = []
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if line.endswith("\r"):
                line = line[:-1]
            if "\ufffd" in line:
                replaced += 1
            lines.append(line)
    return lines, replaced


def normalise_heading(text: str) -> str:
    """Lower-case, markdown-free heading text used as a mapping key."""
    value = text.replace("*", "").replace("`", "").replace("_", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip().lower()


def slugify(text: str, *, limit: int = 48) -> str:
    """``"Beam Stress (7th DOF)"`` -> ``"beam_stress_7th_dof"``."""
    value = _SLUG_RE.sub("_", text.lower()).strip("_")
    if len(value) > limit:
        value = value[:limit].rstrip("_")
    return value or "unnamed"


def canonical_uri(raw: str | None) -> str | None:
    """Normalise a manual/inventory URI to ``/family/rest`` in lower case.

    Handles every spelling the manuals use: ``doc/new``, ``/db/REBB``, ``DB/REBB``,
    ``{base url} + db/NODE``, ``{base url} + /DOC/OPEN``,
    ``/DESIGN/RC/KDS-41-20-2022/TABLE``.  Returns ``None`` when nothing URI-shaped
    survives.
    """
    if not raw:
        return None
    value = raw.strip().strip("*").strip().strip("`").strip()
    match = _URI_WITH_BASE_RE.search(value)
    if match:
        value = match.group(1)
    else:
        match = _URI_BARE_RE.search(value)
        if match:
            value = match.group(1)
    value = _BASE_URL_NOISE_RE.sub("", value)
    value = value.strip().strip("/").strip()
    value = re.sub(r"^info/", "", value, flags=re.I)
    if not value:
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
    ``/DESIGN/RC/KDS-41-20-2022/REBB`` -> ``/DESIGN/RC/KDS-41-20-2022/REBB``.
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
    """``resource`` column: lower-case last path segment.

    ``/db/REBB`` -> ``rebb``; ``/DESIGN/RC/KDS-41-20-2022/REBB`` -> ``rebb``;
    ``/post/TABLE`` -> ``table``.
    """
    parts = [part for part in uri.split("/") if part]
    return parts[-1].lower() if parts else ""


def derive_wrapper(uri: str) -> tuple[str | None, str | None, str | None]:
    """Return ``(request_wrapper, response_root_key, unknown_family)``.

    These are **this project's live-verified findings**, not manual content
    (《MIDAS API 对接规范》§3.1–§3.2):

    * ``/db/*`` -> ``Assign`` + the canonical UPPER-case resource segment.
      Verified: the response root key is *always* upper case even when the path is
      lower case (§3.6).
    * ``/doc/*`` -> ``Argument`` + ``None``.
    * ``/post/*`` and ``/DESIGN/**/TABLE`` -> ``Argument`` + ``None``.  The URI is
      *shared*: ``/post/TABLE`` carries hundreds of result tables selected by
      ``TABLE_TYPE`` inside the ``Argument``, which is why ``interface_code`` has
      to discriminate by table type rather than by URI.
    * ``/ope/*``, ``/view/*``, ``/info/*``, ``/DESIGN/**`` (non-TABLE),
      ``/RATING/**`` -> ``Argument`` + ``None``.
    * anything else -> ``(None, None, family)``; the caller records it.
    """
    family = uri_family(uri)
    if family is None:
        return None, None, "<empty>"
    if family == "db":
        segments = [part for part in uri.split("/") if part]
        root = segments[1].upper() if len(segments) >= 2 else None
        return WRAPPER_ASSIGN, root, None
    if family in ARGUMENT_FAMILIES:
        return WRAPPER_ARGUMENT, None, None
    return None, None, family


def derive_operation(method: str, title: str) -> str:
    """Map ``(method, title)`` to a closed-set operation verb.

    See :data:`METHOD_OPERATION`, :data:`QUERY_TITLE_TOKENS` and
    :data:`EXECUTE_TITLE_TOKENS`.  Query beats execute because "… Result Table"
    would otherwise be read as an execution.
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
    derived from it after stripping the boilerplate suffix the manual appends.
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
        " - Node Results",
    ):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
    value = re.sub(r"^post/TABLE\s*:\s*", "", value)
    value = re.sub(r"^[A-Za-z][A-Za-z0-9/\-\.]*\s*:\s*", "", value)
    return slugify(value)


# ---------------------------------------------------------------------------
# manual parsing
# ---------------------------------------------------------------------------
class ManualIndex:
    """A streamed index of one manual.

    Holds only what extraction needs — heading positions, fence spans, marker
    positions — so an 11.8 MB manual never lands in memory as one string.
    """

    def __init__(self, key: str, path: str) -> None:
        self.key = key
        self.path = path
        self.lines: list[str] = []
        self.headings: list[dict[str, object]] = []
        self.fences: list[dict[str, object]] = []
        self.uri_markers: set[int] = set()
        self.method_markers: set[int] = set()
        self.schema_markers: set[int] = set()
        self.form_markers: set[int] = set()
        self.replacement_lines = 0
        self.mojibake_lines = 0
        self._by_level: dict[int, list[tuple[int, str]]] = {}
        self._section_lines: list[int] = []
        self._section_titles: list[str] = []
        self._chapter_lines: dict[int, list[int]] = {}
        self._chapter_titles: dict[int, list[str]] = {}
        self._load()

    # -- loading ---------------------------------------------------------
    def _load(self) -> None:
        self.lines, self.replacement_lines = read_lines(self.path)
        fence_char: str | None = None
        fence_open = 0
        fence_lang = ""
        for index, line in enumerate(self.lines):
            if "\ufffd" in line or any(marker in line for marker in MOJIBAKE_MARKERS):
                self.mojibake_lines += 1
            match = _FENCE_RE.match(line)
            if match:
                marker = match.group(1)[0]
                if fence_char is None:
                    fence_char = marker
                    fence_open = index
                    fence_lang = line.strip().lstrip("`~").strip().lower()
                elif fence_char == marker:
                    self.fences.append(
                        {"open": fence_open, "close": index, "lang": fence_lang}
                    )
                    fence_char = None
                continue
            if fence_char is not None:
                continue

            heading = _HEADING_RE.match(line)
            if heading:
                title = heading.group(2)
                self.headings.append(
                    {
                        "line": index,
                        "level": len(heading.group(1)),
                        "title": title,
                        "norm": normalise_heading(title),
                    }
                )
                # A marker is a marker whether the scraper rendered it as a
                # heading (``##### **Input URI**``) or as a bold paragraph.  It has
                # to be recorded here too, because the heading branch above has
                # already consumed the line.
                self._record_marker(index, normalise_heading(title))
                continue
            self._record_marker(index, normalise_heading(line))

        if fence_char is not None:  # unterminated final fence
            self.fences.append(
                {"open": fence_open, "close": len(self.lines), "lang": fence_lang}
            )
        self._index_structure()

    def _record_marker(self, index: int, norm: str) -> None:
        """Classify one line as a block marker, if it is one."""
        if norm.startswith("input uri"):
            self.uri_markers.add(index)
        elif norm.startswith("active method") or norm.startswith("支持的方法"):
            self.method_markers.add(index)
        elif norm.startswith("json schema"):
            self.schema_markers.add(index)
        elif norm.startswith("input data form"):
            self.form_markers.add(index)
        elif norm.startswith("input json format"):
            # The Chinese backbone labels the request-body block
            # ``- Input JSON format`` and then shows the body in a fence.
            self.schema_markers.add(index)

    def _index_structure(self) -> None:
        """Pre-sort headings by level and collect the ``##`` section list."""
        by_level: dict[int, list[tuple[int, str]]] = collections.defaultdict(list)
        sections: list[tuple[int, str]] = []
        for heading in self.headings:
            line = int(heading["line"])
            level = int(heading["level"])
            title = str(heading["title"])
            by_level[level].append((line, title))
            if level == 2:
                sections.append((line, title))
        self._by_level = dict(by_level)
        self._section_lines = [line for line, _ in sections]
        self._section_titles = [title for _, title in sections]
        self._chapter_lines = {
            level: [line for line, _ in items] for level, items in by_level.items()
        }
        self._chapter_titles = {
            level: [title for _, title in items] for level, items in by_level.items()
        }

    # -- queries ---------------------------------------------------------
    def section_of(self, line: int) -> str:
        """Nearest preceding ``##`` heading — the manual's top-level section."""
        position = bisect.bisect_left(self._section_lines, line)
        return self._section_titles[position - 1] if position else ""

    def in_json_region(self, line: int) -> bool:
        """True when *line* sits under one of the manual's interface sections."""
        return self.section_of(line) in JSON_REGIONS.get(self.key, ())

    def entry_levels(self, line: int) -> tuple[int, ...]:
        """Heading levels that may carry an entry at *line*, by manual section."""
        if self.key == "gen":
            if self.section_of(line) == GEN_JSON_SECTION:
                return GEN_ZH_ENTRY_LEVELS
            return GEN_EN_ENTRY_LEVELS
        if self.key == "civilnx":
            return CIVILNX_ENTRY_LEVELS
        return DESIGNER_ENTRY_LEVELS

    def chapter_of(self, line: int, chapter_levels: tuple[int, ...]) -> tuple[str, int]:
        """Nearest preceding heading at one of *chapter_levels*.

        Returns ``(title, line)``; ``("", -1)`` when there is none — an entry
        outside every chapter is reported rather than attributed by guesswork.
        """
        best_line = -1
        best_title = ""
        for level in chapter_levels:
            lines = self._chapter_lines.get(level)
            if not lines:
                continue
            position = bisect.bisect_left(lines, line)
            if position == 0:
                continue
            candidate = lines[position - 1]
            if candidate > best_line:
                best_line = candidate
                best_title = self._chapter_titles[level][position - 1]
        return best_title, best_line

    def first_uri(self, start: int, end: int) -> str | None:
        """URI from the first ``Input URI`` marker inside ``[start, end)``.

        The marker is either a heading (``##### **Input URI**``) followed by a table
        row, or a bold paragraph followed by the URL, so the marker and the value
        are searched for separately.  The value line is required to name the base
        URL, which is what makes this a lookup rather than a scan: without that
        guard an unrelated path in a nearby table could be mistaken for the
        endpoint.
        """
        limit = min(end, len(self.lines))
        for index in range(start, limit):
            if index not in self.uri_markers:
                continue
            for probe in range(index, min(index + 8, limit)):
                line = self.lines[probe]
                if "base url" not in line.lower():
                    continue
                uri = canonical_uri(line)
                if uri:
                    return uri
        return None

    def methods(self, start: int, end: int) -> list[str]:
        """Methods under the first ``Active Methods`` / ``支持的方法`` marker."""
        limit = min(end, len(self.lines))
        for index in range(start, limit):
            if index not in self.method_markers:
                continue
            found: list[str] = []
            for probe in range(index + 1, min(index + 10, limit)):
                if probe in self.uri_markers or probe in self.schema_markers:
                    break
                for match in _METHOD_RE.finditer(self.lines[probe]):
                    value = match.group(1).upper()
                    if value not in found:
                        found.append(value)
            if found:
                return found
        return []

    def schema(self, start: int, end: int) -> tuple[str | None, str | None]:
        """Extract the request-body schema from an entry's body.

        Preference order, because the manuals disagree about what a request body
        is documented *as*:

        1. a fenced JSON block under a ``JSON Schema`` marker — a draft-07 schema
           with ``type`` / ``description`` / ``enum`` (both English sections);
        2. a fenced JSON block under an ``Input Data Form`` marker — the Chinese
           backbone's ``__DESC__`` / ``__TYPE__`` form;
        3. the first fenced JSON object in the body (a request-body example).

        Returns ``(schema_text, source_tag)``; ``(None, None)`` when the entry
        documents no body.  The text is returned verbatim — this pipeline does not
        invent fields, and it does not rewrite the manual's schema.
        """
        limit = min(end, len(self.lines))
        for markers, tag in (
            (self.schema_markers, "json_schema"),
            (self.form_markers, "input_data_form"),
        ):
            for index in range(start, limit):
                if index not in markers:
                    continue
                block = self._fenced_after(index, limit)
                if block is None:
                    continue
                text = "\n".join(block)
                if self._is_json_object(text):
                    return text, tag
        block = self._first_json_fence(start, limit)
        if block is not None:
            text = "\n".join(block)
            if self._is_json_object(text):
                return text, "example"
        return None, None

    def _fenced_after(self, index: int, limit: int) -> list[str] | None:
        """Body of the first fence opening after *index* and closing before *limit*."""
        for fence in self.fences:
            opening = int(fence["open"])
            closing = int(fence["close"])
            if index < opening < limit and closing <= limit:
                return self.lines[opening + 1: closing]
        return None

    def _first_json_fence(self, start: int, limit: int) -> list[str] | None:
        for fence in self.fences:
            opening = int(fence["open"])
            closing = int(fence["close"])
            if opening < start or closing > limit:
                continue
            language = str(fence["lang"])
            if language and not language.startswith("json") and language not in (
                "javascript",
                "java",
            ):
                continue
            body = self.lines[opening + 1: closing]
            if "\n".join(body).strip().startswith("{"):
                return body
        return None

    @staticmethod
    def _is_json_object(text: str) -> bool:
        stripped = text.strip()
        if not stripped.startswith("{"):
            return False
        try:
            return isinstance(json.loads(stripped), dict)
        except (ValueError, TypeError):
            return False


# ---------------------------------------------------------------------------
# feature attribution
# ---------------------------------------------------------------------------
def chapter_tables(key: str) -> dict[str, dict[str, str]]:
    """The heading -> feature tables that apply to a manual."""
    if key == "gen":
        return {"en": GEN_EN_CHAPTER_FEATURE, "zh": GEN_ZH_CHAPTER_FEATURE}
    if key == "civilnx":
        return {"civilnx": CIVILNX_CHAPTER_FEATURE}
    return {"designer": DESIGNER_CHAPTER_FEATURE}


def feature_for(key: str, chapter: str) -> tuple[str | None, str]:
    """Resolve a chapter heading to a canonical feature.

    Returns ``(feature, provenance)`` where provenance is ``"table"``,
    ``"fallback"`` or ``"unmapped"``.  ``unmapped`` leaves the column ``None``,
    which the schema permits and the report counts.
    """
    norm = normalise_heading(chapter)
    for table in chapter_tables(key).values():
        if norm in table:
            return table[norm], "table"
    for needle, feature in FEATURE_FALLBACK:
        if needle in norm:
            return feature, "fallback"
    return None, "unmapped"


# ---------------------------------------------------------------------------
# extraction
# ---------------------------------------------------------------------------
def load_inventory() -> dict[str, list[dict[str, object]]]:
    """Read ``inventory.json`` — the endpoint skeleton this pipeline fills in."""
    with open(INVENTORY_PATH, "r", encoding="utf-8", errors="replace") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise SystemExit(f"{INVENTORY_PATH}: top level is not an object")
    return {str(key): list(value) for key, value in data.items()}


def _looks_like_entry(index: ManualIndex, heading: dict[str, object]) -> bool:
    """True when a heading documents a callable interface.

    Two signatures, mirroring ``G:\\MAPI\\tools\\midasdoc.py``'s
    ``civilnx_endpoints``: the heading either carries an interface code in its
    title (``[NODE]``) **or** is immediately followed by an ``Input URI`` marker.
    Without this test, section groupings such as ``#### Results Tables`` would be
    emitted as if they were endpoints.
    """
    line = int(heading["line"])
    if int(heading["level"]) not in index.entry_levels(line):
        return False
    if str(heading["norm"]) in BLOCK_TITLES:
        return False
    if not index.in_json_region(line):
        return False
    if _CODE_RE.search(str(heading["title"])):
        return True
    probe = line + 1
    limit = len(index.lines)
    while probe < limit:
        stripped = index.lines[probe].strip()
        if stripped and not stripped.startswith("!["):
            return probe in index.uri_markers or normalise_heading(stripped).startswith(
                "input uri"
            )
        probe += 1
    return False


def _span_end(index: ManualIndex, position: int) -> int:
    """Line index one past the entry's body (next heading of <= its level)."""
    level = int(index.headings[position]["level"])
    for following in index.headings[position + 1:]:
        if int(following["level"]) <= level:
            return int(following["line"])
    return len(index.lines)


def extract_manual(
    key: str,
    index: ManualIndex,
) -> tuple[list[dict[str, object]], list[str], int]:
    """Turn one manual into raw entry records.

    Returns ``(entries, skipped, candidate_headings)``.  ``skipped`` lists
    entry-shaped headings that document no URI, so the count is auditable rather
    than a silent subtraction.
    """
    entries: list[dict[str, object]] = []
    skipped: list[str] = []
    candidates = 0

    for position, heading in enumerate(index.headings):
        if not _looks_like_entry(index, heading):
            continue
        candidates += 1
        line = int(heading["line"])
        end = _span_end(index, position)
        title = str(heading["title"])
        uri = index.first_uri(line + 1, end)
        if uri is None:
            skipped.append(f"line {line + 1}: {title[:90]}")
            continue

        chapter, chapter_line = index.chapter_of(line, (2, 3))
        feature, provenance = feature_for(key, chapter)
        schema_text, schema_source = index.schema(line + 1, end)
        code_match = _CODE_RE.search(title)

        entries.append(
            {
                "manual": key,
                "title": title,
                "code": code_match.group(1) if code_match else None,
                "uri": uri,
                "methods": index.methods(line + 1, end),
                "line": line + 1,
                "end": end,
                "section": index.section_of(line),
                "chapter": chapter,
                "chapter_line": chapter_line + 1 if chapter_line >= 0 else None,
                "feature": feature,
                "feature_provenance": provenance,
                "schema": schema_text,
                "schema_source": schema_source,
            }
        )

    return entries, skipped, candidates


def build_rows(
    key: str,
    entries: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, int], dict[str, int]]:
    """Expand entries to one row per method and mint the ``interface_code``.

    Returns ``(rows, collisions, unknown_families, feature_provenance)``.
    """
    adapter = ADAPTER_CODES[key]
    rows: list[dict[str, object]] = []
    collisions: list[dict[str, object]] = []
    unknown_families: collections.Counter[str] = collections.Counter()
    provenance_counter: collections.Counter[str] = collections.Counter()
    used: set[str] = set()

    for entry in entries:
        uri = str(entry["uri"])
        family = uri_family(uri) or "unknown"
        wrapper, root_key, unknown = derive_wrapper(uri)
        if unknown is not None:
            unknown_families[unknown] += 1

        endpoint = endpoint_of(uri)
        resource = resource_of(uri)
        feature = entry["feature"]
        domain = CAPABILITY_FEATURE_DOMAIN.get(str(feature)) if feature else None
        provenance = str(entry["feature_provenance"])
        provenance_counter[provenance] += 1

        methods = [str(item).upper() for item in entry["methods"]] or ["GET"]

        # Path slug: the URI without its leading family segment, because the
        # family is already a component of the code (``midas_gen.db.rebb``).
        segments = [part for part in uri.split("/") if part]
        path_slug = ".".join(slugify(part) for part in segments[1:]) or slugify(family)
        base_code = f"{adapter}.{family}.{path_slug}"

        # Shared-URI discrimination: ``/post/TABLE`` and ``/DESIGN/**/TABLE`` need
        # the table type in the code (总纲 裁决 B-3 / V2.1 §17.4).
        needs_table_type = family in ("post", "design") and endpoint.upper().endswith("/TABLE")
        table_slug = table_type_slug(str(entry["title"])) if needs_table_type else ""

        for method in methods:
            code = base_code
            disambiguation = ""
            if needs_table_type:
                code = f"{base_code}.{table_slug}"
                disambiguation = "table_type"
            if code in used:
                suffix = 2
                while f"{code}.{suffix}" in used:
                    suffix += 1
                collisions.append(
                    {
                        "adapter_code": adapter,
                        "base": code,
                        "resolved": f"{code}.{suffix}",
                        "title": entry["title"],
                        "uri": uri,
                        "method": method,
                        "reason": "duplicate (adapter_code, interface_code)",
                    }
                )
                code = f"{code}.{suffix}"
                disambiguation = disambiguation or "numeric_suffix"
            used.add(code)

            carries_body = method in BODY_METHODS
            rows.append(
                {
                    "adapter_code": adapter,
                    "interface_code": code,
                    "method": method,
                    "endpoint": endpoint,
                    "request_wrapper": wrapper,
                    "response_root_key": root_key,
                    "operation": derive_operation(method, str(entry["title"])),
                    "resource": resource,
                    "product_scope": EMITTED_PRODUCT_SCOPE,
                    "domain": domain,
                    "feature": feature,
                    # A request body only exists for body-carrying methods; the
                    # schema is per-URI, so the POST row of the same URI keeps it.
                    "request_schema_json": entry["schema"] if carries_body else None,
                    "metadata_json": {
                        "source_chapter": entry["chapter"],
                        "source_line": entry["line"],
                        "source_title": entry["title"],
                        "source_uri": uri,
                        "source_manual": entry["manual"],
                        "source_section": entry["section"],
                        "source_code": entry["code"],
                        "schema_source": entry["schema_source"] if carries_body else None,
                        "feature_provenance": provenance,
                        "interface_code_disambiguation": disambiguation or None,
                    },
                }
            )

    return rows, collisions, dict(unknown_families), dict(provenance_counter)


# ---------------------------------------------------------------------------
# inventory <-> manual reconciliation
# ---------------------------------------------------------------------------
def reconcile(
    inventory: dict[str, list[dict[str, object]]],
    entries_by_manual: dict[str, list[dict[str, object]]],
) -> dict[str, dict[str, object]]:
    """Compare the inventory's URIs against what the manuals actually document.

    This is the §7 audit: ``inventory.json`` is the contract, so every inventory
    URI that the current manual no longer carries is a contradiction the loader
    has to know about, and every manual URI absent from the inventory is a gap in
    the skeleton.
    """
    result: dict[str, dict[str, object]] = {}
    for key, entries in inventory.items():
        inventory_uris = {
            uri for uri in (canonical_uri(str(e.get("uri"))) for e in entries) if uri
        }
        manual_uris = {str(entry["uri"]) for entry in entries_by_manual.get(key, [])}
        missing = sorted(inventory_uris - manual_uris)
        extra = sorted(manual_uris - inventory_uris)
        result[key] = {
            "inventory_unique_uris": len(inventory_uris),
            "manual_unique_uris": len(manual_uris),
            "matched": len(inventory_uris & manual_uris),
            "in_inventory_not_in_manual": missing,
            "in_manual_not_in_inventory": extra,
        }
    return result


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------
def coverage(rows: list[dict[str, object]]) -> dict[str, object]:
    """Counts the report needs, computed once from the emitted rows."""
    total = len(rows)
    with_schema = sum(1 for row in rows if row["request_schema_json"])
    body_rows = [row for row in rows if str(row["method"]) in BODY_METHODS]
    return {
        "rows": total,
        "rows_with_schema": with_schema,
        "schema_coverage_pct": round(100.0 * with_schema / total, 2) if total else 0.0,
        "body_rows": len(body_rows),
        "body_rows_with_schema": sum(1 for row in body_rows if row["request_schema_json"]),
        "unique_interface_codes": len({str(row["interface_code"]) for row in rows}),
        "unique_endpoints": len({str(row["endpoint"]) for row in rows}),
        "by_domain": dict(sorted(collections.Counter(str(row["domain"]) for row in rows).items())),
        "by_feature": dict(sorted(collections.Counter(str(row["feature"]) for row in rows).items())),
        "by_operation": dict(sorted(collections.Counter(str(row["operation"]) for row in rows).items())),
        "by_method": dict(sorted(collections.Counter(str(row["method"]) for row in rows).items())),
        "by_wrapper": dict(sorted(collections.Counter(str(row["request_wrapper"]) for row in rows).items())),
        "by_schema_source": dict(
            sorted(
                collections.Counter(
                    str(row["metadata_json"]["schema_source"])  # type: ignore[index]
                    for row in rows
                ).items()
            )
        ),
    }


def write_report(
    *,
    inventory_counts: dict[str, int],
    manual_stats: dict[str, dict[str, int]],
    rows_by_adapter: dict[str, int],
    coverage_stats: dict[str, object],
    collisions: list[dict[str, object]],
    unknown_families: dict[str, int],
    null_uris: list[str],
    skipped: list[str],
    feature_provenance: dict[str, int],
    contradictions: list[str],
    reconciliation: dict[str, dict[str, object]],
) -> None:
    """Render ``EXTRACTION_REPORT.md`` — the questions the design cannot answer."""
    lines: list[str] = []
    add = lines.append
    add("# MIDAS API interface extraction — coverage report")
    add("")
    add("Generated by [`extract_interfaces.py`](extract_interfaces.py).  Every number")
    add("below is computed from the run, not estimated.")
    add("")

    # --- 1 ---------------------------------------------------------------
    add("## 1. Entries in, rows out")
    add("")
    add("| product | inventory entries | entry headings found | entries with a URI | rows out |")
    add("| --- | --- | --- | --- | --- |")
    for key in ("gen", "civilnx", "designer"):
        stats = manual_stats.get(key, {})
        add(
            f"| `{key}` (`{ADAPTER_CODES[key]}`) | {inventory_counts.get(key, 0)} "
            f"| {stats.get('candidate_headings', 0)} "
            f"| {stats.get('entries_with_uri', 0)} "
            f"| {rows_by_adapter.get(ADAPTER_CODES[key], 0)} |"
        )
    add(
        f"| **total** | **{sum(inventory_counts.values())}** | "
        f"**{sum(s.get('candidate_headings', 0) for s in manual_stats.values())}** | "
        f"**{sum(s.get('entries_with_uri', 0) for s in manual_stats.values())}** | "
        f"**{coverage_stats['rows']}** |"
    )
    add("")
    add("Rows differ from entries for three reasons, in this order:")
    add("")
    add("1. **Multi-method expansion** — one row per method.  A URI advertising")
    add("   `POST, GET, PUT, DELETE` yields four rows, because `method` is part of")
    add("   the row identity and the adapter dispatches per method.")
    add("2. **Null URIs dropped** — an entry with `uri: null` cannot be called, so it")
    add("   is listed in §3 instead of being emitted with an empty endpoint.")
    add("3. **Interface-code collisions disambiguated** — never dropped; each one is")
    add("   listed in §4.")
    add("")
    add("The \"entry headings found\" column is this run's own count from the manual's")
    add("heading tree, so it does not track the inventory's entry count one-for-one:")
    add("the inventory was built from an earlier revision of the sources (§7).")
    add("")

    # --- 2 ---------------------------------------------------------------
    add("## 2. Schema coverage (the LLM-safety question)")
    add("")
    add(f"- rows emitted: **{coverage_stats['rows']}**")
    add(
        f"- rows with a non-null `request_schema_json`: "
        f"**{coverage_stats['rows_with_schema']}** "
        f"(**{coverage_stats['schema_coverage_pct']}%**)"
    )
    add(
        f"- rows whose method carries a request body (`POST`/`PUT`/`PATCH`): "
        f"**{coverage_stats['body_rows']}**, of which "
        f"**{coverage_stats['body_rows_with_schema']}** have a schema"
    )
    add(
        f"- rows with `null`: "
        f"{coverage_stats['rows'] - coverage_stats['rows_with_schema']}"
    )
    add("")
    add("`request_schema_json` is emitted **only for body-carrying methods**.  The")
    add("manual documents one body per URI, so attaching it to the `GET`/`DELETE` rows")
    add("of the same URI would invite a caller to send a body those verbs do not take.")
    add("A `null` therefore means one of two things, and they are not the same backlog")
    add("item:")
    add("")
    add("- the method takes no body (`GET`/`DELETE`) — nothing to validate, and")
    add("- the method takes a body but the manual documents none — **this** is the real")
    add("  gap, because such a call cannot be validated before it is sent.")
    add("")
    add("Where the schema came from (`json_schema` = the manual's draft-07 JSON Schema,")
    add("`input_data_form` = the Chinese backbone's `__DESC__`/`__TYPE__` form,")
    add("`example` = a request-body example only):")
    add("")
    add("| `schema_source` | rows |")
    add("| --- | --- |")
    for source, count in sorted(coverage_stats["by_schema_source"].items()):
        add(f"| `{source}` | {count} |")
    add("")

    # --- 3 ---------------------------------------------------------------
    add("## 3. Null-URI entries")
    add("")
    add(f"{len(null_uris)} inventory entries carry `uri: null`.  They are **not**")
    add("emitted as rows — a row without an endpoint cannot be dispatched — and each one")
    add("is listed here so it can be chased back to the manual.")
    add("")
    if null_uris:
        add("| # | entry |")
        add("| --- | --- |")
        for position, item in enumerate(null_uris, 1):
            add(f"| {position} | {item} |")
    else:
        add("_None._")
    add("")
    add("Separately, entry-shaped headings that document no `Input URI` at all (index")
    add("rows in the manual's unindexed-design section, section groupings):")
    add("")
    add(f"**{len(skipped)}** such headings.")
    if skipped:
        add("")
        add("| # | heading |")
        add("| --- | --- |")
        for position, item in enumerate(skipped[:200], 1):
            add(f"| {position} | {item} |")
        if len(skipped) > 200:
            add(f"| … | and {len(skipped) - 200} more |")
    add("")

    # --- 4 ---------------------------------------------------------------
    add("## 4. Interface-code collisions disambiguated")
    add("")
    add(f"**{len(collisions)}** collisions.")
    add("")
    if collisions:
        add("| adapter | code before | code after | URI | method | title |")
        add("| --- | --- | --- | --- | --- | --- |")
        for item in collisions:
            add(
                f"| `{item['adapter_code']}` | `{item['base']}` | `{item['resolved']}` "
                f"| `{item['uri']}` | {item['method']} | {str(item['title'])[:70]} |"
            )
    else:
        add("_None._  The unique constraint is `(adapter_code, interface_code)`")
        add("(总纲 裁决 B-3); it holds on this run without a numeric suffix.")
    add("")

    # --- 5 ---------------------------------------------------------------
    add("## 5. Rows per domain and per feature")
    add("")
    add("| domain | rows |")
    add("| --- | --- |")
    for domain, count in sorted(
        coverage_stats["by_domain"].items(), key=lambda kv: (-kv[1], kv[0])
    ):
        add(f"| `{domain}` | {count} |")
    add("")
    add("| feature | domain | rows |")
    add("| --- | --- | --- |")
    for feature, count in sorted(
        coverage_stats["by_feature"].items(), key=lambda kv: (-kv[1], kv[0])
    ):
        domain = CAPABILITY_FEATURE_DOMAIN.get(feature, "")
        add(f"| `{feature}` | `{domain}` | {count} |")
    add("")
    add("Feature attribution provenance (`table` = explicit chapter mapping,")
    add("`fallback` = keyword rule, `unmapped` = no feature emitted):")
    add("")
    add("| provenance | rows |")
    add("| --- | --- |")
    for source, count in sorted(feature_provenance.items()):
        add(f"| `{source}` | {count} |")
    add("")

    # --- 6 ---------------------------------------------------------------
    add("## 6. The unknown-family branch")
    add("")
    if unknown_families:
        add("| family | rows |")
        add("| --- | --- |")
        for family, count in sorted(unknown_families.items()):
            add(f"| `{family}` | {count} |")
    else:
        add("_None._  Every emitted endpoint's first path segment is one of")
        add("`" + "`, `".join(ENDPOINT_FAMILIES) + "`.")
    add("")

    # --- 7 ---------------------------------------------------------------
    add("## 7. Where the manuals contradict `inventory.json`")
    add("")
    if contradictions:
        for item in contradictions:
            add(f"- {item}")
    else:
        add("_No contradictions detected._")
    add("")
    add("### 7.1 URI reconciliation per product")
    add("")
    add("| product | unique URIs in inventory | unique URIs in manual | matched | inventory-only | manual-only |")
    add("| --- | --- | --- | --- | --- | --- |")
    for key, stats in reconciliation.items():
        add(
            f"| `{key}` | {stats['inventory_unique_uris']} | {stats['manual_unique_uris']} "
            f"| {stats['matched']} | {len(stats['in_inventory_not_in_manual'])} "
            f"| {len(stats['in_manual_not_in_inventory'])} |"
        )
    add("")
    for key, stats in reconciliation.items():
        missing = stats["in_inventory_not_in_manual"]
        extra = stats["in_manual_not_in_inventory"]
        if missing:
            add(f"**`{key}` — in the inventory but not in the current manual "
                f"({len(missing)}):**")
            add("")
            add("```text")
            for uri in missing[:80]:
                add(str(uri))
            if len(missing) > 80:
                add(f"… and {len(missing) - 80} more")
            add("```")
            add("")
        if extra:
            add(f"**`{key}` — in the current manual but not in the inventory "
                f"({len(extra)}):**")
            add("")
            add("```text")
            for uri in extra[:80]:
                add(str(uri))
            if len(extra) > 80:
                add(f"… and {len(extra) - 80} more")
            add("```")
            add("")

    # --- 8 ---------------------------------------------------------------
    add("## 8. The operation mapping")
    add("")
    add("| method | operation | condition |")
    add("| --- | --- | --- |")
    add("| `GET` | `read` | always |")
    add("| `PUT` | `update` | always |")
    add("| `DELETE` | `delete` | always |")
    add("| `PATCH` | `update` | always |")
    add(
        "| `POST` | `query` | title contains one of "
        + ", ".join(f"`{token}`" for token in QUERY_TITLE_TOKENS)
        + " (checked first) |"
    )
    add(
        "| `POST` | `execute` | else, title contains one of "
        + ", ".join(f"`{token}`" for token in EXECUTE_TITLE_TOKENS)
        + " |"
    )
    add("| `POST` | `create` | otherwise |")
    add("")
    add("Query is checked before execute because the manual has titles such as")
    add("`RC Beam Design Perform` and `Beam Force - Analysis Result Table`; reading the")
    add("second as an execution would mis-file hundreds of result tables.")
    add("")
    add("Rows per operation on this run:")
    add("")
    add("| operation | rows |")
    add("| --- | --- |")
    for operation, count in sorted(
        coverage_stats["by_operation"].items(), key=lambda kv: (-kv[1], kv[0])
    ):
        add(f"| `{operation}` | {count} |")
    add("")

    # --- 9 ---------------------------------------------------------------
    add("## 9. Structural facts measured while building this")
    add("")
    add("| manual | lines | headings | entry-level headings | with a URI | fences |")
    add("| --- | --- | --- | --- | --- | --- |")
    for key, stats in manual_stats.items():
        add(
            f"| `{key}` | {stats['lines']} | {stats['headings']} "
            f"| {stats['candidate_headings']} | {stats['entries_with_uri']} "
            f"| {stats['fences']} |"
        )
    add("")
    add(
        "| manual | `Input URI` | `JSON Schema` | `Input Data Form` "
        "| U+FFFD lines | mojibake lines |"
    )
    add("| --- | --- | --- | --- | --- | --- |")
    for key, stats in manual_stats.items():
        add(
            f"| `{key}` | {stats['uri_markers']} | {stats['schema_markers']} "
            f"| {stats['form_markers']} | {stats['replacement_lines']} "
            f"| {stats['mojibake_lines']} |"
        )
    add("")

    with open(OUT_REPORT, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# inventory vs manual
# ---------------------------------------------------------------------------
def check_line_numbers(
    inventory: dict[str, list[dict[str, object]]],
    manual_paths: dict[str, str],
) -> list[str]:
    """Compare the inventory's ``line`` numbers against the manuals on disk.

    ``inventory.json`` was extracted from an earlier revision of the sources, so a
    stale ``line`` is expected.  Measuring the drift matters because this pipeline
    deliberately does **not** use those numbers to locate anything — it matches by
    URI instead.  Reporting it stops the next reader from trusting them.
    """
    notes: list[str] = []
    for key, entries in inventory.items():
        path = manual_paths.get(key)
        if not path or not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            total = sum(1 for _ in handle)
        claimed = max((int(entry.get("line") or 0) for entry in entries), default=0)
        if claimed > total:
            notes.append(
                f"`{key}`: `inventory.json` references line **{claimed}** but "
                f"`{os.path.basename(path)}` has only **{total}** lines.  The "
                "inventory was built from an earlier revision of the manual, so its "
                "`line` numbers are **stale**; this pipeline locates entries by URI "
                "and copies the *current* manual's line into `metadata_json`."
            )
    return notes


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> int:
    inventory = load_inventory()
    inventory_counts = {key: len(value) for key, value in inventory.items()}

    all_rows: list[dict[str, object]] = []
    entries_by_manual: dict[str, list[dict[str, object]]] = {}
    manual_stats: dict[str, dict[str, int]] = {}
    collisions: list[dict[str, object]] = []
    unknown_families: collections.Counter[str] = collections.Counter()
    feature_provenance: collections.Counter[str] = collections.Counter()
    null_uris: list[str] = []
    skipped: list[str] = []
    contradictions: list[str] = []

    for key in ("gen", "civilnx", "designer"):
        path = MANUAL_PATHS[key]
        if not os.path.exists(path):
            contradictions.append(f"manual missing for `{key}`: `{path}`")
            continue
        index = ManualIndex(key, path)
        entries, skipped_here, candidates = extract_manual(key, index)
        entries_by_manual[key] = entries
        rows, collisions_here, unknown_here, provenance_here = build_rows(key, entries)

        manual_stats[key] = {
            "lines": len(index.lines),
            "headings": len(index.headings),
            "candidate_headings": candidates,
            "entries_with_uri": len(entries),
            "fences": len(index.fences),
            "uri_markers": len(index.uri_markers),
            "schema_markers": len(index.schema_markers),
            "form_markers": len(index.form_markers),
            "replacement_lines": index.replacement_lines,
            "mojibake_lines": index.mojibake_lines,
        }
        all_rows.extend(rows)
        collisions.extend(collisions_here)
        unknown_families.update(unknown_here)
        feature_provenance.update(provenance_here)
        skipped.extend(f"`{key}` {item}" for item in skipped_here)

        # Null URIs come straight from the inventory, so the list stays complete
        # even for entries the current manual no longer contains.
        for entry in inventory.get(key, []):
            if entry.get("uri") is None:
                null_uris.append(
                    f"`{key}` line {entry.get('line')} (level {entry.get('level')}): "
                    f"{entry.get('title')}"
                )

        if index.replacement_lines:
            contradictions.append(
                f"`{key}` manual contains **{index.replacement_lines}** lines with "
                'U+FFFD replacement characters (read with `errors="replace"`).'
            )
        if index.mojibake_lines:
            contradictions.append(
                f"`{key}` manual contains **{index.mojibake_lines}** lines matching a "
                "mojibake fingerprint (e.g. `鎬荤翰` where `总纲` was meant)."
            )

    contradictions.extend(check_line_numbers(inventory, MANUAL_PATHS))
    reconciliation = reconcile(inventory, entries_by_manual)
    for key, stats in reconciliation.items():
        missing = len(stats["in_inventory_not_in_manual"])
        extra = len(stats["in_manual_not_in_inventory"])
        if missing:
            contradictions.append(
                f"`{key}`: **{missing}** URIs in `inventory.json` are not present in "
                "the current manual (see §7.1)."
            )
        if extra:
            contradictions.append(
                f"`{key}`: **{extra}** URIs in the current manual are absent from "
                "`inventory.json` (see §7.1)."
            )

    # --- duplicate (adapter_code, interface_code) sanity ------------------
    seen_codes: set[tuple[str, str]] = set()
    duplicates: list[tuple[str, str]] = []
    for row in all_rows:
        pair = (str(row["adapter_code"]), str(row["interface_code"]))
        if pair in seen_codes:
            duplicates.append(pair)
        seen_codes.add(pair)
    if duplicates:
        contradictions.append(
            f"INTERNAL: {len(duplicates)} duplicate `(adapter_code, interface_code)` "
            "pairs survived disambiguation — a bug in this script."
        )

    # --- closed-set validation -------------------------------------------
    problems: list[str] = []
    for row in all_rows:
        if row["product_scope"] not in MIDAS_PRODUCT_SCOPE_VALUES:
            problems.append(f"product_scope {row['product_scope']!r}")
        if row["domain"] is not None and row["domain"] not in DOMAIN_SET:
            problems.append(f"domain {row['domain']!r}")
        if row["feature"] is not None and row["feature"] not in FEATURE_SET:
            problems.append(f"feature {row['feature']!r}")
        if row["domain"] is not None and row["feature"] is not None:
            if CAPABILITY_FEATURE_DOMAIN.get(str(row["feature"])) != row["domain"]:
                problems.append(
                    f"feature/domain mismatch {row['feature']!r} -> {row['domain']!r}"
                )
    if problems:
        contradictions.append(
            "INTERNAL: closed-set violations: " + ", ".join(sorted(set(problems))[:20])
        )

    all_rows.sort(
        key=lambda row: (
            str(row["adapter_code"]),
            str(row["interface_code"]),
            str(row["method"]),
        )
    )
    coverage_stats = coverage(all_rows)
    rows_by_adapter: dict[str, int] = dict(
        collections.Counter(str(row["adapter_code"]) for row in all_rows)
    )

    meta: dict[str, object] = {
        "generated_by": "docs/api-registry/extract_interfaces.py",
        "sources": {"inventory": INVENTORY_PATH, "manuals": MANUAL_PATHS},
        "inventory_counts": inventory_counts,
        "manual_stats": manual_stats,
        "row_count": len(all_rows),
        "rows_by_adapter": rows_by_adapter,
        "coverage": coverage_stats,
        "collision_count": len(collisions),
        "unknown_families": dict(unknown_families),
        "null_uri_count": len(null_uris),
        "feature_provenance": dict(feature_provenance),
        "feature_values": list(FEATURE_VALUES),
        "reconciliation": reconciliation,
        "product_scope_policy": (
            "always 'unknown' — the manuals' product labels are not trustworthy "
            "(《MIDAS API 对接规范》§3.5 第 15 条), so real values come from live "
            "probing in a separate task"
        ),
        "operation_mapping": {
            "GET": "read",
            "PUT": "update",
            "DELETE": "delete",
            "PATCH": "update",
            "POST": (
                "query if the title matches QUERY_TITLE_TOKENS, else execute if it "
                "matches EXECUTE_TITLE_TOKENS, else create"
            ),
        },
        "request_schema_policy": (
            "emitted only for POST/PUT/PATCH rows; null on GET/DELETE rows because "
            "the manual documents one body per URI and those verbs take none"
        ),
    }

    with open(OUT_JSON, "w", encoding="utf-8") as handle:
        json.dump({"meta": meta, "rows": all_rows}, handle, ensure_ascii=False, indent=1)

    write_report(
        inventory_counts=inventory_counts,
        manual_stats=manual_stats,
        rows_by_adapter=rows_by_adapter,
        coverage_stats=coverage_stats,
        collisions=collisions,
        unknown_families=dict(unknown_families),
        null_uris=null_uris,
        skipped=skipped,
        feature_provenance=dict(feature_provenance),
        contradictions=contradictions,
        reconciliation=reconciliation,
    )

    print(f"inventory entries : {inventory_counts}")
    print(f"rows              : {len(all_rows)}  by adapter {rows_by_adapter}")
    print(
        f"schema coverage   : {coverage_stats['rows_with_schema']}/{len(all_rows)} "
        f"({coverage_stats['schema_coverage_pct']}%)"
    )
    print(
        f"  body-carrying   : {coverage_stats['body_rows_with_schema']}"
        f"/{coverage_stats['body_rows']}"
    )
    print(f"collisions        : {len(collisions)}")
    print(f"null URIs         : {len(null_uris)}")
    print(f"skipped headings  : {len(skipped)}")
    print(f"unknown families  : {dict(unknown_families) or 'none'}")
    print(f"by domain         : {coverage_stats['by_domain']}")
    print(f"wrote             : {OUT_JSON}")
    print(f"wrote             : {OUT_REPORT}")

    failures = verify_output()
    if failures:
        print(f"\nSELF-VERIFICATION FAILED ({len(failures)}):")
        for item in failures:
            print("  -", item)
        return 2

    if contradictions:
        print(f"\nCONTRADICTIONS / NOTES ({len(contradictions)}):")
        for item in contradictions:
            print("  -", item)
    print("self-verification : ok")
    return 0


def verify_output() -> list[str]:
    """Re-open the written JSON and re-check the invariants a loader depends on.

    A pipeline that reports success while writing something the database would
    reject is worse than one that fails.  These checks are deliberately about the
    *file*, not the in-memory rows, so a serialisation mistake is caught too.
    """
    failures: list[str] = []
    try:
        with open(OUT_JSON, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        return [f"{OUT_JSON} is not readable JSON: {exc!r}"]

    if not isinstance(payload, dict) or "rows" not in payload or "meta" not in payload:
        return [f"{OUT_JSON}: expected an object with 'meta' and 'rows'"]

    rows = payload["rows"]
    if not isinstance(rows, list) or not rows:
        return [f"{OUT_JSON}: 'rows' is empty or not a list"]

    required = (
        "adapter_code",
        "interface_code",
        "method",
        "endpoint",
        "request_wrapper",
        "response_root_key",
        "operation",
        "resource",
        "product_scope",
        "domain",
        "feature",
        "request_schema_json",
        "metadata_json",
    )
    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            failures.append(f"row {index}: not an object")
            continue
        for field in required:
            if field not in row:
                failures.append(f"row {index}: missing field {field!r}")
        if row.get("product_scope") != EMITTED_PRODUCT_SCOPE:
            failures.append(f"row {index}: product_scope {row.get('product_scope')!r}")
        if row.get("domain") is not None and row.get("domain") not in DOMAIN_SET:
            failures.append(f"row {index}: domain {row.get('domain')!r}")
        if row.get("feature") is not None and row.get("feature") not in FEATURE_SET:
            failures.append(f"row {index}: feature {row.get('feature')!r}")
        pair = (str(row.get("adapter_code")), str(row.get("interface_code")))
        if pair in seen:
            failures.append(f"row {index}: duplicate (adapter_code, interface_code) {pair}")
        seen.add(pair)
        schema = row.get("request_schema_json")
        if schema is not None:
            if not isinstance(schema, str):
                failures.append(f"row {index}: request_schema_json is not a string")
            else:
                try:
                    json.loads(schema)
                except ValueError as exc:
                    failures.append(
                        f"row {index}: request_schema_json is not valid JSON: {exc!r}"
                    )
        metadata = row.get("metadata_json")
        if metadata is not None and not isinstance(metadata, dict):
            failures.append(f"row {index}: metadata_json is not an object")
    return failures


if __name__ == "__main__":
    sys.exit(main())
