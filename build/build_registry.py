#!/usr/bin/env python3
"""Build the MIDAS endpoint registry from documentation.

Two documented sources are merged:

* A) ``api_chapters/*.md`` (this repo's v2 dev pack).  Every chapter carries one
  uniform 4-column ``## Endpoint Registry`` table::

      | `NODE` | `POST/GET/PUT/DELETE /db/NODE` | Node coordinates | `Assign` |

  These give us the *endpoint key*, the *namespace* and the *request wrapper*.
  They are condensed: multi-key cells (``TH_DISP / TH_VELOCITY``),
  ``CRUD`` shorthand and ``...``-elided prefixes all appear and are expanded.

* B) ``docs/manual/*.md`` (vendored upstream manual, pinned commit).  505
  endpoint sections in nine declaration formats, including the numbered/grouped
  scheme of chapter 22 and the table-driven POST chapters 18-23.  This is the
  authoritative source for URIs, HTTP methods and the ``TABLE_TYPE`` /
  ``TEXT_TYPE`` enumerations.

Merge precedence: upstream wins URI + methods (live-verified upstream); local
wins key naming + wrapper + description.  Safety flags are computed in code
from the namespace and methods, never parsed from prose.

Usage::

    python build/build_registry.py            # write registry/registry.json
    python build/build_registry.py --check    # build + report, write nothing
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCAL_DIR = ROOT / "api_chapters"
UPSTREAM_DIR = ROOT / "docs" / "manual"
OUT_PATH = ROOT / "registry" / "registry.json"
REPORT_PATH = ROOT / "registry" / "build_report.json"

METHODS = ("POST", "GET", "PUT", "DELETE")

#: Endpoint sections the upstream manual documents, per chapter.  The build
#: reports drift so documentation changes upstream are noticed.
EXPECTED_SECTIONS = {
    "01_DOC": 11, "02_DB_Project_Structure": 15, "03_DB_Node_Element": 6,
    "04_DB_Properties": 32, "05_DB_Boundary": 24, "06_DB_Static_Loads": 21,
    "07_DB_Temperature_Prestress": 12, "08_DB_Moving_Loads": 28,
    "09_DB_Dynamic_Loads": 12, "10_DB_Construction_Stage": 14,
    "11_DB_Settlement_Misc_Loads": 9, "12_DB_Analysis_Control": 21,
    "13_DB_Load_Combinations": 8, "14_DB_Pushover": 6, "15_OPE": 19,
    "16_VIEW": 7, "17_DB_Bridge": 5, "18_POST_PreProcess": 10,
    "19_POST_AnalysisResult_1": 13, "20_POST_AnalysisResult_2": 39,
    "21_POST_StoryTables": 17, "22_POST_TH_HY_Pushover": 28,
    "23_POST_Design": 10, "24_DB_Design": 13,
    "25_Design_Steel_KDS41302022": 28, "26_Design_RC_KDS41202022": 70,
    "27_Design_SRC_AIKSRC2K": 27,
}
EXPECTED_TOTAL = 505

#: Chapters whose endpoints are "POST /post/TABLE with a TABLE_TYPE selector".
POST_TABLE_CHAPTERS = {"18_POST_PreProcess", "19_POST_AnalysisResult_1",
                       "20_POST_AnalysisResult_2", "21_POST_StoryTables",
                       "22_POST_TH_HY_Pushover", "23_POST_Design"}

PATH_RE = re.compile(r"(?:db|doc|ope|view|post|DESIGN)/[A-Za-z0-9_\-/<>*.]+")
URI_TOKEN_RE = re.compile(r"\{base[_ ]?url\}(/[A-Za-z0-9_\-/<>*.{}]+)")
HEADING2_RE = re.compile(r"^##\s+(?!Table of Contents|목차|개요|공통|INTRODUCTION)(.+?)\s*$", re.M)
HEADING3_RE = re.compile(r"^###\s+(?!Input URI|Active Methods|JSON Schema|Parameters|Request|Response|Python|Specifications|ADDITIONAL|SUB_TABLES|SET_|공통|기본 정보|요청|응답|HTTP|메서드|`TABLE_TYPE`$|`TEXT_TYPE`$)(.+?)\s*$", re.M)
NUMBERED_RE = re.compile(r"^(\d+)\.\s*(.+)$")
GROUPED_RE = re.compile(r"^([A-Z])-(\d+)\.\s*(.+)$")
GROUP_HEAD_RE = re.compile(r"^(?:그룹|Group)\s*([A-Z])")

#: Endpoints whose *record key* is a structural id (node/element number).
#: MIDAS crashes the whole process when these reference a missing id.
REF_KEYED = {
    "CONS": "NODE", "CNLD": "NODE", "NSPR": "NODE", "RIGD": "NODE",
    "NTMP": "NODE", "GTMP": "NODE", "BMLD": "ELEM", "SSPS": "ELEM",
    "ELNK": "ELEM", "ETMP": "ELEM", "BTMP": "ELEM", "STMP": "ELEM",
}

#: Endpoints the tested Gen NX build does not serve through the API.
UNAVAILABLE_ON_GEN = {
    "RCHK": "HTTP 404 on Gen NX 2026 v2.1 - rebar layout cannot be defined through the API.",
    "STEELMEMBERDESIGNFORCES": "returns an empty body on Gen NX; read DESIGN:STEEL:*:CODE-TABLE instead.",
    "COLUMNDESIGNFORCES": "returns an empty body on Gen NX even after a successful /doc/ANAL.",
    "BEAMDESIGNFORCES": "returns an empty body on Gen NX even after a successful /doc/ANAL.",
}

#: Endpoints the tested Gen NX build does not serve through the API.
UNAVAILABLE_ON_GEN = {
    "RCHK": "HTTP 404 on Gen NX 2026 v2.1 - rebar layout cannot be defined through the API.",
    "STEELMEMBERDESIGNFORCES": "returns an empty body on Gen NX; read DESIGN:STEEL:*:CODE-TABLE instead.",
    "COLUMNDESIGNFORCES": "returns an empty body on Gen NX even after a successful /doc/ANAL.",
    "BEAMDESIGNFORCES": "returns an empty body on Gen NX even after a successful /doc/ANAL.",
}

#: Endpoints asserted by the v3 official-source audit that are absent from the
#: vendored manual/local chapters.  Injected so callers can reach them.
AUDIT_ENDPOINTS = {
    "DB:HHND": {
        "uri": "/db/HHND", "methods": ["POST", "GET", "PUT", "DELETE"],
        "wrapper": "Assign", "title": "Heat of Hydration Result Graph",
        "source": "v3 audit 2026-09-20",
    },
    "DB:GALD": {
        "uri": "/db/GALD", "methods": ["POST", "GET", "PUT", "DELETE"],
        "wrapper": "Assign", "title": "Grid Analysis Load",
        "variant": ["JP-only"],
        "source": "v3 audit 2026-09-20",
    },
}

#: Documentation under-reports some method sets.  Each correction below was
#: reproduced against the live build with `build/verify_api.py`; the registry
#: carries the *verified* set so a working call is not refused by a guard.
METHOD_CORRECTIONS = {
    # docs (and 24_DB_Design.md's own warning) say POST-only, but GET reads the
    # current column rebar data back successfully.
    "DB:REBC": {"methods": ["POST", "GET"],
                "note": "GET is also served: it reads the current column rebar data. "
                        "The manual documents POST only."},
    # 27_Design_SRC_AIKSRC2K.md documents "PUT, DELETE" only; GET answers 200
    # with the current SRC design-code setting.
    "DESIGN:SRC:AIK-SRC2K:DSRC": {"methods": ["GET", "PUT", "DELETE"],
                                  "note": "GET is also served and returns the current "
                                          "SRC design code. The manual lists PUT/DELETE only."},
}


#: Curated notes for endpoints that demonstrably mislead callers.
NOTES = {
    "DB:EIGV": "TYPE must be LANCZOS: with a rigid diaphragm the mass matrix is non-diagonal and subspace iteration is refused; the bad record then blocks ALL analysis until deleted.",
    "DB:SPLC": "aUSEMODE needs one entry per computed mode; a short array fails with a misleading 'modal coefficient' error. EIGV and SPLC must exist together or /doc/ANAL answers 'Analysis is not allowed.'",
    "DB:MATL": "PARAM.P_TYPE must be 2 (user defined). P_TYPE 1 is accepted but silently zeroes POISN/THERMAL/DEN/MASS. Rebar grades in /db/MATD carry a space ('Class A', not 'ClassB').",
    "DB:DCON": "single record, key must be '1'. Re-POSTing an existing key fails with 'Key Already Exist' - DELETE /db/DCON/1 first when switching design code.",
    "DB:DGNCODE": "only ACI318-14/11/19/99, KCI-USD12/07, GB50010-02, BS8110-97 are accepted here; every EN spelling is rejected.",
    "DB:STOR": "all 15 fields are required; a partial record (e.g. only STORY_NAME/STORY_LEVEL) is rejected with a bare 'Wrong Field'. STORY_AREA_ITEMS is an optional 16th field. Once stories exist, OPE:STORYPROP returns Storey/Weight/Elev./Loaded H/Bx/By.",
    "DB:LCOM-GEN": "DELETE has no path form: DELETE /db/LCOM-GEN/<id> answers 'Unknown Error'. The body form DELETE /db/LCOM-GEN with {'Assign':{'<id>':{}}} returns 200 and CLEARS THE WHOLE COLLECTION regardless of the id named. Verify by read-back and never send a body form delete.",
    "DB:NODE": "unknown field names are silently ignored here: POST {'Assign':{'900':{'__TYPO__':1}}} answers 201 and creates an EMPTY node. The same typo is rejected with 'Wrong Field' on most other endpoints, so read the record back after creating it.",
    "DB:CNLD": "Assign key must equal the node number (one record per node; all load cases share it via ITEMS[].LCNAME). Item fields are the explicit components FX/FY/FZ/MX/MY/MZ - confirmed with GET /info/db/CNLD - not the CMD/FV vector the manual example suggests.",
    "DB:ACTL": "the Assign key must be '0' (not '1' as the manual example shows). The record cannot be read back.",
    "DB:PDEL": "P-Delta lives here, not in ACTL.",
    "DB:RIGD": "Assign key is the master node; DOF '110001' constrains DX/DY/RZ.",
    "DB:LTOM": "mass source: {'DIR':'XYZ','bNODAL':true,'bBEAM':true,'GRAV':9.806,'vLC':[...]}.",
    "DB:SPFC": "aFUNC entries are [{PERIOD, VALUE}] with VALUE as a multiple of g.",
    "DOC:SAVEAS": "avoid: SAVEAS opens a modal dialog that blocks the entire API channel until it is dismissed in the GUI. Use DOC:SAVE.",
    "DOC:NEW": "destroys the model in memory. Prefer clearing the model (delete ELEM/NODE/SECT/MATL/STLD/CNLD/CONS) over repeated NEW calls.",
    "VIEW:CAPTURE": "EXPORT_PATH needs Windows backslashes; ZOOM_LEVEL has no effect; post mode needs an existing analysis result.",
    "VIEW:SELECT": "GET only: it reports the current GUI selection and cannot perform a selection.",
    "OPE:SECTPROP": "GET only.",
}
NOTE_SUFFIXES = {
    "TABLE": "LOAD_CASE_NAMES needs the '(ST)' suffix for load cases and '(CB)' for combinations, otherwise the table comes back empty.",
    "TEXT": "the selector field is TEXT_TYPE (the upstream schema block mislabels it TABLE_TYPE).",
}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _strip(cell: str) -> str:
    return cell.strip().strip("`").strip()


def _dedupe(items):
    seen: OrderedDict = OrderedDict()
    for it in items:
        seen.setdefault(it, None)
    return list(seen)


def expand_key_cell(cell: str) -> list[str]:
    """Expand a local key cell into concrete endpoint keys.

    ``TH_DISP / TH_VELOCITY / TH_ACCEL`` -> three keys.
    ``DISPLACEMENTG/L`` -> ``DISPLACEMENTG``, ``DISPLACEMENTL``.
    ``STORY_DRIFT_X/Y/COMB`` -> ``STORY_DRIFT_X``, ``STORY_DRIFT_Y``,
    ``STORY_DRIFT_COMB``.
    ``BEAMSTRESS*`` -> ``BEAMSTRESS*`` (wildcard token, expanded later against
    the upstream enumeration).
    """
    raw = _strip(cell)
    if not raw:
        return []
    out: list[str] = []
    for part in (p.strip().strip("`").strip() for p in raw.split("/")):
        if not part:
            continue
        if out and _is_bare_tail(part, out[-1]):
            out.append(_splice(out[-1], part))
        else:
            out.append(part)
    return _dedupe(out)


def _is_bare_tail(part: str, prev: str) -> bool:
    """True when ``part`` continues ``prev`` rather than naming its own key.

    ``DISPLACEMENTG/L`` -> ``L`` continues; ``MASS_SUMMARY_X/Y`` -> ``Y``
    continues; ``STORY_DRIFT_X/Y/COMB`` -> ``COMB`` continues;
    ``STORY_MASS / _X`` -> ``_X`` continues.  A token as long as its
    predecessor (``THRE/THRG``) or carrying a full underscore segment
    (``CO_S`` next to ``CO_M``) never continues.
    """
    if part.startswith("_"):
        return bool(re.fullmatch(r"_[A-Z0-9]+", part)) and len(part) * 2 <= len(prev)
    if not re.fullmatch(r"[A-Z0-9]+", part) or "_" in part:
        return False
    if prev.split("_")[-1] == part:
        return False
    return len(part) * 2 <= len(prev)


def _splice(prev: str, tail: str) -> str:
    """Splice a bare tail onto the stem of the previous key.

    ``MASS_SUMMARY_X`` + ``Y`` -> ``MASS_SUMMARY_Y`` (keep through the last
    underscore); ``DISPLACEMENTG`` + ``L`` -> ``DISPLACEMENTL`` (no separator,
    so the tail replaces the final letter).
    """
    if tail.startswith("_"):
        return prev + tail
    if "_" in prev:
        return prev[: prev.rfind("_") + 1] + tail
    return prev[:-1] + tail


def canonical_uri(uri: str) -> str:
    """``/db/ACTL/{id}`` -> ``/db/ACTL``; ``DESIGN/RC/...`` -> ``/DESIGN/RC/...``."""
    uri = "/" + uri.strip("/")
    uri = re.sub(r"/\{[a-z_]+\}$", "", uri)
    return uri


def key_from_uri(uri: str) -> str:
    parts = [p for p in canonical_uri(uri).strip("/").split("/") if p]
    ns = parts[0]
    if ns == "DESIGN":
        return "DESIGN:" + ":".join(parts[1:])
    return f"{ns.upper()}:{parts[-1]}"


def namespace_of(uri: str) -> str:
    return canonical_uri(uri).strip("/").split("/")[0].lower()


# --------------------------------------------------------------------------
# Source A: local chapter tables
# --------------------------------------------------------------------------
@dataclass
class LocalRow:
    chapter: str
    keys: list[str]
    uri_cell: str
    methods: list[str]
    func: str
    wrapper: str
    line: int = 0


def parse_local_tables() -> tuple[list[LocalRow], list[str]]:
    rows: list[LocalRow] = []
    notes: list[str] = []
    for path in sorted(LOCAL_DIR.glob("*.md")):
        chapter = path.stem
        lines = path.read_text(encoding="utf-8").splitlines()
        try:
            start = next(i for i, ln in enumerate(lines)
                         if ln.strip().startswith("## Endpoint Registry"))
        except StopIteration:
            notes.append(f"{chapter}: no Endpoint Registry table")
            continue
        for i in range(start + 1, len(lines)):
            ln = lines[i]
            if not ln.startswith("|"):
                if ln.strip() and i > start + 3:
                    break
                continue
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cells) != 4 or cells[0] == "Endpoint" or set(cells[0]) <= set("-: "):
                continue
            key_cell, uri_cell, func, wrapper = cells
            uri_cell = _strip(uri_cell)
            methods = [m for m in METHODS if m in uri_cell.upper()]
            if "CRUD" in uri_cell.upper():
                methods = list(METHODS)
            rows.append(LocalRow(chapter, expand_key_cell(key_cell), uri_cell,
                                 methods, func, _strip(wrapper), i + 1))
    return rows, notes


# --------------------------------------------------------------------------
# Source B: upstream sections
# --------------------------------------------------------------------------
@dataclass
class Entry:
    namespace: str
    uri: str
    methods: list[str] = field(default_factory=list)
    wrapper: str = ""
    selector_field: str | None = None
    selector_value: str | None = None
    title: str = ""
    source_page: str = ""
    notes: list[str] = field(default_factory=list)
    key: str = ""
    extra: dict = field(default_factory=dict)
    # v3 audit: variant-aware registration
    variants: list[str] = field(default_factory=list)  # e.g. ['JP-only'], ['Hyper-S-only']
    source_url: str = ""
    source_title: str = ""

    def finalize(self) -> None:
        if not self.key:
            self.key = key_from_uri(self.uri) if self.uri else ""
        if not self.wrapper:
            self.wrapper = wrapper_for(self.namespace, self.methods)


#: Endpoints the Gen NX build does not serve because they belong to another
#: product.  They are KEPT in the registry -- Civil NX, Civil Designer or the
#: Hyper-S solver do expose them -- and marked rather than removed, so a Gen
#: caller can tell "wrong product" apart from "wrong call".
PRODUCT_ATTRIBUTION = {
    # bridge / civil specialisations
    "CAMB": "Civil NX - FCM camber control",
    "CMCS": "Civil NX - camber for construction stage",
    "GCMB": "Civil NX - general camber control",
    "GSBG": "Civil NX - bridge girder diagrams",
    "SPAN": "Civil NX - span information",
    "PLCB": "Civil NX - pre-composite section",
    "WVLD": "Civil NX - wave loads",
    "DYLA": "Civil NX - railway dynamic load allowance",
    "DYFG": "Civil NX - railway dynamic factor",
    "DYNF": "Civil NX - railway dynamic factor by element",
    "CJFG": "Civil NX - concurrent joint force group",
    "CRGR": "Civil NX - concurrent reaction group",
    # design / checking
    "RCHK": "Design/checking module - rebar input for checking is not reachable via the Gen NX API",
    "OCHECK": "Design module - SRC overstrength check is not reachable via the Gen NX API",
    # documented property endpoints this build does not expose
    "EWSF": "documented as 'Effective Width Scale Factor' (04_DB_Properties.md) - a section/girder property; not served by this Gen build",
    "STRPSSM": "documented as 'Section Manager - Stress Points' (04_DB_Properties.md); not served by this Gen build",
}


def variant_of_key(key: str, live_probe: int | None = None) -> list[str]:
    """Derive variant markers so callers never assume an endpoint is universal.

    ``-M1`` suffixes mark Hyper-S(MEC)-only endpoints; ``GALD`` is Civil NX
    JP-only; anything that answers 404 on the tested Gen build is attributed to
    the product that does serve it when that is known.
    """
    out: list[str] = []
    short = key.split(":")[-1]
    if key.endswith("-M1"):
        out.append("Hyper-S-only")
    if short == "GALD":
        out.append("JP-only")
    if live_probe == 404:
        if short in PRODUCT_ATTRIBUTION:
            out.append("other-product")
        elif key.endswith("-M1"):
            pass  # already marked as Hyper-S-only
        else:
            out.append("unavailable-on-gen")
    return out


def attribution_note(key: str, live_probe: int | None) -> str | None:
    if live_probe != 404:
        return None
    short = key.split(":")[-1]
    if key.endswith("-M1"):
        return ("not served by the tested Gen NX build: this is a Hyper-S (MEC) "
                "solver endpoint. Kept in the registry for Hyper-S builds.")
    if short in PRODUCT_ATTRIBUTION:
        return (f"not served by the tested Gen NX build (HTTP 404); belongs to "
                f"{PRODUCT_ATTRIBUTION[short]}. Kept in the registry - do not "
                f"remove.")
    return ("not served by the tested Gen NX build (HTTP 404); product "
            "attribution unknown. Kept in the registry - do not remove.")


def wrapper_for(namespace: str, methods: list[str]) -> str:
    """Config-style single records take ``Assign``; actions take ``Argument``.

    Every ``/db`` endpoint is a keyed record collection, so its wrapper is
    ``Assign`` regardless of its method set.  Deriving it from the methods
    produced ``Argument`` for DB collections whose list lacked ``PUT`` and
    that POSTed to the collection URI (LCOM-GEN, LCOM-CONC, LCOM-STEEL,
    LCOM-SRC, STOR, EDMP, SSPS), and MIDAS answers those with HTTP 400
    ``Wrong Field``.  Probed live on Gen NX 2027: ``{"Assign": {...}}`` ->
    HTTP 201, ``{"Argument": {...}}`` -> HTTP 400.

    Design chapters mix both shapes: their config/member endpoints store
    keyed records (``Assign``) while ``*-ANAL`` / ``*-TABLE`` / ``*-REPORT``
    are POST-only actions (``Argument``), per 25_Design_Steel_KDS41302022.md
    line 27-28.
    """
    if namespace == "db":
        return "Assign"
    if namespace == "design":
        return "Assign" if "POST" not in methods or "PUT" in methods else "Argument"
    return "Argument"


def timeout_for(namespace: str, key: str) -> int:
    if key.endswith(":ANAL"):
        return 1800
    if namespace == "post" or "CODE-TABLE" in key or "CODE-ANAL" in key:
        return 180
    if namespace in ("db", "design"):
        return 60
    return 30


def find_uri(body: str) -> str | None:
    """Resolve the endpoint URI of a section, preferring the declared URI."""
    m = re.search(r"\*\*Input URI\*\*\s*\|\s*`?\{base[_ ]?url\}(/[^`|\s]+)", body)
    if m:
        return canonical_uri(m.group(1))
    m = re.search(r"\*\*(?:URL|Endpoint)\*\*:?\s*`?\{base[_ ]?url\}(/[^\s`]+)", body)
    if m:
        return canonical_uri(m.group(1))
    m = re.search(r"###\s+Input URI[^\n]*\n+```[a-z]*\n\{?base[_ ]?url\}?(/[^\s`\n]+)", body)
    if m:
        return canonical_uri(m.group(1))
    m = URI_TOKEN_RE.search(body)
    if m:
        return canonical_uri(m.group(1))
    m = re.search(r"`((?:DESIGN/|/?(?:db|doc|ope|view|post)/)[A-Za-z0-9_\-/<>*]+)`", body)
    if m:
        return canonical_uri(m.group(1))
    return None


def find_methods(body_lines: list[str]) -> list[str]:
    """Read the documented method list in any of the nine upstream formats."""
    for j in range(min(len(body_lines), 30)):
        ln = body_lines[j]
        if re.match(r"^\|\s*(?:메서드|Method)\s*\|", ln):
            found: list[str] = []
            for row in body_lines[j + 1: j + 14]:
                if not row.startswith("|"):
                    break
                found.extend(m for m in _methods_in(row) if m not in found)
            if found:
                return found
        if re.search(r"\*\*(?:Active\s+)?Methods?:?\*\*|\*\*HTTP 메서드:?\*\*", ln, re.I):
            found = _methods_in(ln)
            if not found and j + 1 < len(body_lines):
                found = _methods_in(body_lines[j + 1])
            if found:
                return found
        if re.match(r"^###\s+Active Methods", ln):
            for row in body_lines[j + 1: j + 4]:
                if row.strip():
                    found = _methods_in(row)
                    if found:
                        return found
                    break
    return []


def _methods_in(text: str) -> list[str]:
    found = {m for m in METHODS if re.search(rf"\b{m}\b", text)}
    return [m for m in METHODS if m in found]


def chapter_table_methods(lines: list[str]) -> dict[str, list[str]]:
    """``| 4 | [`/db/STYP-M1`](#..) | Structure Type | GET, PUT, DELETE |`` -> uri -> methods."""
    out: dict[str, list[str]] = {}
    for ln in lines:
        if not ln.startswith("|") or ln.count("|") < 3:
            continue
        found = _methods_in(ln)
        if not found:
            continue
        for m in re.finditer(r"`((?:DESIGN/|/?(?:db|doc|ope|view|post)/)[A-Za-z0-9_\-/<>*]+)`", ln):
            out.setdefault(canonical_uri(m.group(1)), found)
            break
    return out


def parse_chapter(path: Path) -> tuple[list[Entry], dict]:
    """Extract every endpoint declared by one upstream chapter."""
    chapter = path.stem
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    toc_methods = chapter_table_methods(lines)
    entries: list[Entry] = []
    report = {"chapter": chapter, "declared": 0, "methods_from_toc": 0,
              "methods_missing": [], "post_types": 0}

    def make(uri: str | None, methods: list[str], title: str) -> Entry:
        e = Entry(namespace=namespace_of(uri) if uri else "unknown", uri=uri or "",
                  methods=methods, title=title, source_page=chapter)
        e.finalize()
        return e

    h2 = list(HEADING2_RE.finditer(text))
    for i, mk in enumerate(h2):
        end = h2[i + 1].start() if i + 1 < len(h2) else len(text)
        body = text[mk.start():end]
        heading = mk.group(1).strip()
        clean_heading = re.sub(r"[`*]", "", heading)
        head_lines = body.splitlines()

        group = GROUP_HEAD_RE.match(clean_heading)
        numbered = NUMBERED_RE.match(clean_heading)

        if group:
            # "## 그룹 A. ...": children "### A-1. ..." are the endpoints and
            # inherit the group's URI + methods.
            ghead = body.split("###", 1)[0]
            guri = find_uri(ghead) or find_uri(body)
            gmethods = find_methods(ghead.splitlines()) or find_methods(head_lines)
            for ck in HEADING3_RE.finditer(body):
                child = GROUPED_RE.match(re.sub(r"[`*]", "", ck.group(1)))
                if not child:
                    continue
                cend = body.find("\n###", ck.end())
                cbody = body[ck.start(): cend if cend > 0 else len(body)]
                uri = find_uri(cbody) or guri
                methods = find_methods(cbody.splitlines()) or gmethods
                entries.append(make(uri, methods, child.group(3).strip()))
                report["declared"] += 1
            continue

        if not numbered:
            continue

        uri = find_uri(body)
        methods = find_methods(head_lines)
        if not methods and uri and uri in toc_methods:
            methods = toc_methods[uri]
            report["methods_from_toc"] += 1
        title = re.sub(r"[`*]", "", numbered.group(2)).strip()
        if not methods:
            report["methods_missing"].append(f"{chapter}#{numbered.group(1)} {title}")
        e = make(uri, methods, title)
        e.extra["table_types"] = _dedupe(
            re.findall(r"^###\s+`([A-Z][A-Z0-9_]+)`\s*$", body, re.M))
        entries.append(e)
        report["declared"] += 1

    # POST chapters: types come from the chapter list table, the JSON examples
    # and the per-section enum tables.
    if chapter in POST_TABLE_CHAPTERS:
        text_types = _dedupe(re.findall(r'"TEXT_TYPE"\s*:\s*"([A-Z][A-Z0-9_]+)"', text)
                             + re.findall(r"TEXT_TYPE\s*=\s*`?([A-Z][A-Z0-9_]+)`?", text)
                             + _enum_tokens(text, lines, "TEXT_TYPE"))
        table_types = _dedupe(re.findall(r'"TABLE_TYPE"\s*:\s*"([A-Z][A-Z0-9_]+)"', text)
                              + re.findall(r"TABLE_TYPE\s*=\s*`?([A-Z][A-Z0-9_]+)`?", text)
                              + _enum_tokens(text, lines, "TABLE_TYPE")
                              + _list_table_tokens(text, lines))
        report["post_types"] = len(table_types) + len(text_types)
        for t in table_types:
            uri = "/post/TABLE"
            e = Entry(namespace="post", uri=uri, methods=["POST"], wrapper="Argument",
                      selector_field="TABLE_TYPE", selector_value=t, title=t,
                      source_page=chapter, notes=[NOTE_SUFFIXES["TABLE"]])
            e.key = f"POST:TABLE:{t}"
            entries.append(e)
        for t in text_types:
            e = Entry(namespace="post", uri="/post/TEXT", methods=["POST"], wrapper="Argument",
                      selector_field="TEXT_TYPE", selector_value=t, title=t,
                      source_page=chapter, notes=[NOTE_SUFFIXES["TEXT"]])
            e.key = f"POST:TEXT:{t}"
            entries.append(e)
    return entries, report


def _list_table_tokens(text: str, lines: list[str]) -> list[str]:
    """Tokens inside the chapter's "테이블 목록" table, e.g. ``DISPLACEMENTG``.

    Cells such as ``MASS_SUMMARY_X/Y/Z`` list several table types at once and
    are expanded.
    """
    out: list[str] = []
    inside = False
    for ln in lines:
        if re.match(r"^#{2,4}\s+.*(테이블.{0,4}목록|Table List)", ln):
            inside = True
            continue
        if inside:
            if re.match(r"^#{2,4}\s", ln):
                break
            if ln.startswith("|"):
                for cell in re.findall(r"`([A-Z][A-Z0-9_/*]{2,})`", ln):
                    out.extend(expand_key_cell(cell))
    skip = {"TABLE_TYPE", "TEXT_TYPE", "TABLE_NAME", "UNIT", "FORCE", "DIST"}
    return [t for t in _dedupe(out) if t not in skip]


def _enum_tokens(text: str, lines: list[str], field: str) -> list[str]:
    """Enum rows under a ``#### `TEXT_TYPE` `` heading (chapter 22 style).

    Those tables list the allowed selector values for one endpoint, e.g.::

        #### `TEXT_TYPE`
        | `TEXT_TYPE` | 설명 |
        | `"TH_DISP"` | 변위 |
        | `"TH_VELOCITY"` | 속도 |
    """
    out: list[str] = []
    inside = False
    for ln in lines:
        if re.match(rf"^#{{2,4}}\s+`?{field}`?", ln):
            inside = True
            continue
        if inside:
            if ln.startswith("#"):
                inside = False
                continue
            if ln.startswith("|"):
                out.extend(re.findall(r"`\"([A-Z][A-Z0-9_]+)\"`", ln))
    skip = {field, "TABLE_TYPE", "TEXT_TYPE"}
    return [t for t in _dedupe(out) if t not in skip]


# --------------------------------------------------------------------------
# merge
# --------------------------------------------------------------------------
def build() -> tuple[dict, dict]:
    local_rows, local_notes = parse_local_tables()
    report: dict = {"local": {"rows": len(local_rows), "notes": local_notes},
                    "chapters": [], "drift": [], "notes": [], "unavailable": []}

    registry: OrderedDict[str, Entry] = OrderedDict()
    chapter_total = 0
    for path in sorted(UPSTREAM_DIR.glob("*.md")):
        if path.stem == "INDEX":
            continue
        entries, rep = parse_chapter(path)
        chapter_total += rep["declared"]
        rep["expected"] = EXPECTED_SECTIONS.get(path.stem)
        rep["matches"] = rep["expected"] == rep["declared"]
        report["chapters"].append(rep)
        for e in entries:
            if not e.uri or e.key.startswith("@") or not e.key:
                if e.uri:
                    report["notes"].append(f"unkeyed section: {path.stem} {e.uri}")
                continue
            if e.key in registry:
                # One URI can serve several documented pages (e.g. the RC
                # /DESIGN/.../TABLE endpoint covers Column, Brace and Beam).
                # Record the variants instead of dropping them silently.
                kept = registry[e.key]
                if e.title and e.title not in kept.notes:
                    kept.notes.append(f"same URI also serves: {e.title}")
                report["notes"].append(
                    f"shared URI {e.key}: {kept.title!r} + {e.title!r} ({path.stem})")
                continue
            registry[e.key] = e

    # Inject audit-sourced endpoints that the vendored docs do not cover.
    for akey, spec in AUDIT_ENDPOINTS.items():
        if akey in registry:
            continue
        ns = akey.split(":", 1)[0].lower()
        e = Entry(namespace=ns, uri=spec["uri"], methods=list(spec["methods"]),
                  wrapper=spec["wrapper"], title=spec.get("title", ""),
                  source_page=spec.get("source", "v3 audit"),
                  variants=list(spec.get("variant", [])),
                  notes=[f"source: {spec.get('source', 'v3 audit')}"])
        e.key = akey
        registry[e.key] = e

    # v3 audit correction: the story-properties endpoint is STORYPROP (not the
    # old STORPROP spelling); it is POST-only and answers clearly when no storey
    # exists.  Record that so callers stop guessing.
    if "OPE:STORYPROP" in registry:
        registry["OPE:STORYPROP"].notes.insert(
            0, "official name is STORYPROP (STORY+PROP), not STORPROP. "
               "POST-only: returns the storey property result.")

    matched = 0
    for row in local_rows:
        for key in row.keys:
            if key.endswith("*"):
                continue
            target = registry.get(key)
            if target is None:
                # The local row carries its own URI; use it to pick the right
                # namespace.  Falling back to a bare short-name scan let
                # "15_OPE:44 LCOM-GEN  POST /ope/LCOM-GEN" land on DB:LCOM-GEN
                # and overwrite the DB wrapper with the OPE one.  (The
                # key-name test above is also a short-name test, so it has the
                # same ambiguity and must be URI-checked too.)
                m = re.search(r"(/(?:db|doc|ope|view|post|DESIGN)/[A-Za-z0-9_.\-/*]*)",
                              row.uri_cell)
                want = canonical_uri(m.group(1).rstrip("*")) if m else ""
                wild = bool(m) and "*" in m.group(1)
                for cand in registry.values():
                    if cand.key.split(":")[-1] != key.split(":")[-1]:
                        continue
                    if cand.namespace not in ("db", "doc", "ope", "view", "post", "design"):
                        continue
                    if want and (cand.uri.startswith(want) if wild else cand.uri == want):
                        target = cand
                        break
                if target is None and not want:
                    for cand in registry.values():
                        if cand.key.split(":")[-1] == key and cand.namespace in (
                                "db", "doc", "ope", "view", "post", "design"):
                            target = cand
                            break
            if target is None and ":" in key:
                # local rows such as "TABLE:Column" name one page of a shared
                # URI endpoint; attach the page name as a note.
                page, _, variant = key.partition(":")
                for cand in registry.values():
                    if cand.key.split(":")[-1] == page and variant:
                        target = cand
                        note = f"page variant: {variant}"
                        if note not in target.notes:
                            target.notes.append(note)
                        break
            if target is None:
                report["notes"].append(
                    f"local row without upstream match: {row.chapter}:{row.line} {key} ({row.uri_cell})")
                continue
            matched += 1
            if row.func and not target.title:
                target.title = row.func
            if row.wrapper.upper() in ("ASSIGN", "ARGUMENT"):
                target.wrapper = row.wrapper.capitalize()
            if row.methods and target.methods and set(row.methods) != set(target.methods):
                report["drift"].append({"key": target.key, "local": row.methods,
                                        "upstream": target.methods,
                                        "source": f"{row.chapter}:{row.line}"})
    report["local"]["matched"] = matched

    endpoints = {}
    live = _load_live_probe()
    for key, e in registry.items():
        e.methods = e.methods or ["POST"]
        if key in METHOD_CORRECTIONS:
            fix = METHOD_CORRECTIONS[key]
            e.methods = list(fix["methods"])
            e.notes.append(fix["note"])
        e.finalize()
        notes = list(e.notes)
        if key in NOTES:
            notes.insert(0, NOTES[key])
        short = key.split(":")[-1]
        if short in UNAVAILABLE_ON_GEN:
            notes.append(UNAVAILABLE_ON_GEN[short])
            report["unavailable"].append(key)
        if key.startswith("POST:TABLE") and NOTE_SUFFIXES["TABLE"] not in notes:
            notes.append(NOTE_SUFFIXES["TABLE"])
        live_status = live.get(key, {}).get("status")
        if key in live:
            status = live[key]["status"]
            if status == 404:
                notes.append(f"HTTP 404 on the live Gen NX probe ({live[key]['uri']}).")
            elif status != 200:
                notes.append(f"live probe returned HTTP {status}: {live[key]['body_head'][:60]}")
        attribution = attribution_note(key, live_status)
        if attribution:
            notes.append(attribution)
        endpoints[key] = {
            "namespace": e.namespace,
            "uri": e.uri,
            "methods": e.methods,
            "wrapper": e.wrapper,
            "selector_field": e.selector_field,
            "selector_value": e.selector_value,
            "id_mode": "numeric-string" if (
                e.namespace in ("db", "design") and
                {"GET", "PUT", "DELETE"} & set(e.methods)) else "none",
            "ref_family": REF_KEYED.get(short),
            "product": "gen/civil",
            "variant": variant_of_key(key, live_status),
            "title": e.title,
            "source_page": e.source_page,
            "timeout_s": timeout_for(e.namespace, key),
            "destructive": ("DELETE" in e.methods) or key in {
                "DOC:NEW", "DOC:OPEN", "DOC:CLOSE", "DOC:SAVEAS",
                "DOC:IMPORT", "DOC:IMPORTMXT"},
            "requires_analysis": e.namespace == "post" or key == "VIEW:RESULTGRAPHIC",
            "retryable": "GET" in e.methods and "DELETE" not in e.methods,
            "live_probe": live.get(key, {}).get("status"),
            "notes": notes,
        }

    payload = {
        "schema_version": 1,
        "source": {
            "local_chapters": str(LOCAL_DIR.relative_to(ROOT)).replace("\\", "/"),
            "upstream_manual": str(UPSTREAM_DIR.relative_to(ROOT)).replace("\\", "/"),
            "upstream_sections": chapter_total,
        },
        "endpoints": endpoints,
    }
    report["totals"] = {"upstream_sections": chapter_total,
                        "expected_sections": EXPECTED_TOTAL,
                        "registry_entries": len(endpoints),
                        "local_rows": len(local_rows)}
    return payload, report


LIVE_PROBE_PATH = ROOT / "registry" / "live_probe.json"


def _load_live_probe() -> dict:
    """Read the previous live probes.

    ``build/verify_live.py`` stamps ``live_probe.json`` (GET on every read
    endpoint) and ``build/verify_api.py`` stamps ``api_verify.json`` (all verbs,
    including endpoints that only accept writes).  Both are folded in so the
    registry can tell "documented here but not served by this build", and keep
    those endpoints marked instead of removing them.
    """
    merged: dict = {}
    for path in (LIVE_PROBE_PATH, ROOT / "registry" / "api_verify.json"):
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        if "endpoints" in data:  # api_verify.json shape
            for key in data.get("absent", []):
                merged.setdefault(key, {"status": 404, "uri": data["endpoints"].get(key, {}).get("uri", ""),
                                        "body_head": "endpoint absent on this build"})
            for key, entry in data["endpoints"].items():
                merged.setdefault(key, {"status": 200 if entry.get("present") else 404,
                                        "uri": entry.get("uri", ""), "body_head": ""})
        else:  # live_probe.json shape
            for key, entry in data.items():
                merged.setdefault(key, entry)
    return merged


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="build but do not write")
    args = ap.parse_args(argv)

    payload, report = build()
    t = report["totals"]
    print(f"upstream sections : {t['upstream_sections']} (documented {t['expected_sections']})")
    print(f"registry entries  : {t['registry_entries']}")
    print(f"local rows        : {t['local_rows']} matched {report['local'].get('matched')}")

    bad = [c for c in report["chapters"] if not c["matches"]]
    if bad:
        print("\nchapter section-count drift:")
        for c in bad:
            print(f"  {c['chapter']}: parsed {c['declared']} documented {c['expected']}")
    missing = [c for c in report["chapters"] if c["methods_missing"]]
    if missing:
        print(f"\nchapters with sections lacking methods: "
              f"{[(c['chapter'], len(c['methods_missing'])) for c in missing]}")
    if report["drift"]:
        print(f"\nlocal/upstream method drift: {len(report['drift'])} rows "
              f"(upstream wins, see build_report.json)")
    unmatched = [n for n in report["notes"] if "without upstream match" in n]
    print(f"unmatched local rows: {len(unmatched)}; other notes: "
          f"{len(report['notes']) - len(unmatched)}")
    print(f"unavailable on Gen  : {len(report['unavailable'])}")

    if args.check:
        return 1 if bad else 0

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {OUT_PATH.relative_to(ROOT)} and {REPORT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
