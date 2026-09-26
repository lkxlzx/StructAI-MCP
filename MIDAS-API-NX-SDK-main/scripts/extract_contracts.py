"""Draft endpoint contracts from the official manual repo, and check them for drift.

The manual repo (`Dennis5882/MIDAS-API`) is one of the three permitted sources
for `contracts/` - see `contracts/README.md`. Its chapters already carry
machine-readable parameter tables (`Key` / `Value Type` / `Default` /
`Required`), roughly 640 of them, so drafting a contract does not have to mean
retyping a table by hand.

What this script will and will not do matters more than what it parses.

**It drafts, it does not promote.** Output goes to `contracts/drafts/`, which is
git-ignored and which `scripts/validate_contracts.py` ignores. Every draft
carries `draft: true`, which the schema forbids, so no draft can be moved into
`contracts/endpoints/` and pass CI without someone reading it first.

**It never answers `safeToOmit` from the manual.** That field is a claim about
the product, and the manual cannot make it: `/db/NMAS` documents
`rmX`/`rmY`/`rmZ` as optional and omitting them kills the session. A draft
answers `true` only where a payload in `scripts/live_crud_check.py` marked
`confirmed=True` actually omitted the field and the round trip still passed,
citing that case. Everything else is emitted `unverified`, which is the honest
state and not a lesser one.

**It reports what it could not parse rather than quietly dropping it.** A
section with conditional sub-tables (`#### LINEAR 전용`, `#### 1-2-B. Korea
Type`) has its extra tables listed under `extraction.unmergedTables` instead of
being merged or silently ignored. A partial field list presented as complete is
its own kind of wrong answer.

Modes
-----
``--report``     (default) how much of each chapter is parseable
``--emit ...``   write drafts for the named endpoints, or ``--emit-all``
``--check``      compare promoted contracts against the manual; exit 1 on drift

``--check`` compares only what the manual actually asserts: the field set,
types, documented defaults, documented optionality and requiredness. It says
nothing about `safeToOmit`, `sdkRules` or verification status, because those are
not the manual's to claim.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, replace
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import Any, NamedTuple, Optional

ROOT = Path(__file__).resolve().parent.parent
DRAFT_DIR = ROOT / "contracts" / "drafts"
ENDPOINT_DIR = ROOT / "contracts" / "endpoints"
TABLE_DIR = ROOT / "contracts" / "tables"

DEFAULT_MANUAL_REPO = Path(r"E:\AI Study\MIDAS-API")

# Chapters 18-23 document the shared /post/TABLE family: one endpoint selected by
# a TABLE_TYPE string, with response HEAD columns rather than a request payload.
# Those use a two-layer contract (endpoint plus table).  This extractor only
# emits endpoint drafts, so it reports their measured table-contract coverage
# rather than mangling them into endpoint contracts.
TABLE_FAMILY_CHAPTERS = {
    "18_POST_PreProcess.md",
    "19_POST_AnalysisResult_1.md",
    "20_POST_AnalysisResult_2.md",
    "21_POST_StoryTables.md",
    "22_POST_TH_HY_Pushover.md",
    "23_POST_Design.md",
}

_SECTION = re.compile(r"^##\s+(\d+)\.\s*`?(/?[A-Za-z][A-Za-z0-9/_.\-]*/[A-Za-z0-9/_.\-]+)`?\s*(?:[—\-–]\s*(.*))?$")
_BLOCKQUOTE_TITLE = re.compile(r"^>\s+\*\*([^*]+)\*\*(?:\s*[—\-–]\s*.*)?$")
_DIVIDER = re.compile(r"^\|[\s:|-]+\|$")
_SOURCE_URL = re.compile(r"\*\*Source\*\*:\s*\[[^\]]*\]\((https?://[^)]+)\)")
# The chapters declare methods six ways, and each miss is expensive: without one
# the extractor falls back to the /db/* default of all four verbs, which is how
# /db/GRUP's first draft claimed a DELETE the endpoint does not serve.
#
#   - **Methods**: `POST, GET`          label, then the colon inside the bold
#   **Active Methods:** `POST`, `GET`   label, with the colon outside it
#   **Methods:** `POST` · `GET`         ...and a middle dot for a separator
#   | **Method** | `POST` |             a two-column table row, verb singular
#   ### Active Methods                  a heading, verbs on a following line
#   ### HTTP Methods                    a heading, verbs in a Method column
#
# The first three are one regex; the rest need surrounding lines, so
# _section_methods() drives them. Reading only the narrowest form left 276 of
# 386 sections looking like the manual never stated its verbs at all - it does,
# in five of these six ways, and each is worth a promotable contract.
_METHODS = re.compile(
    r"^\s*(?:[-*]\s*)?\*{0,2}(?:Active\s+|HTTP\s+|Supported\s+)?Methods?\s*\*{0,2}\s*[:：]\s*\*{0,2}\s*"
    r"((?:[`\s]*[A-Z]+[,\s·`/]*)+)",
    re.MULTILINE,
)
# Anchored to the end of the row, so only the documented two-column form counts.
# A section body runs to the next heading that names an endpoint, so a chapter's
# trailing summary - whose heading names none - is absorbed into the last
# endpoint's body. 14_DB_Pushover.md ends with
# ``| Active Methods | POST, GET, PUT, DELETE | GET, PUT, DELETE (POST 미지원) |``
# comparing the general and Hyper-S endpoints, and reading its first value column
# gave /db/POLC-M1 the *general* endpoint's verbs: a POST that same chapter twice
# says Hyper-S does not serve. A comparison is not a declaration.
_METHODS_TABLE_ROW = re.compile(
    r"^\s*\|\s*\*{0,2}(?:Active\s+|HTTP\s+|Supported\s+)?Methods?\*{0,2}\s*\|\s*([^|]+)\|\s*$",
    re.MULTILINE,
)
# Some chapters number and localize this heading (for example,
# ``### 1-1. HTTP 메서드 및 URL``).  ``HTTP`` still establishes that the
# following table is an HTTP-method table; the parser below accepts only actual
# HTTP verbs from its first column, so a broader heading match cannot invent a
# method from the surrounding prose.
_METHODS_HEADING = re.compile(
    r"^#{2,4}\s+(?:.*\b(?:Active|Supported)\s+Methods?\b.*|.*\bHTTP\b.*)$",
    re.I,
)

_VERBS = {"GET", "POST", "PUT", "DELETE"}


def _verbs(text: str) -> list[str]:
    return sorted({v for v in re.findall(r"[A-Z]+", text) if v in _VERBS})


# Chapters 24-27 label their sections `English (한글)`; every other chapter is
# English alone. Both halves are the manual's, so neither is wrong - but the
# label reaches PyPI and npm as a package-visible resource name, and INDEX.md
# gives one English name per endpoint for the whole manual. Take the English.
# Only a parenthetical that actually contains Hangul is a translation:
# `Rebar Input for Checking (Beam/Column)` is one label, not two.
_TRANSLATED_SUFFIX = re.compile(r"\s*\((?=[^)]*[가-힣])[^)]*\)\s*$")


def _plain_dashes(text: str) -> str:
    """Fold the dash spellings the manual and the contracts disagree on."""
    return text.replace("—", "-").replace("–", "-").replace("--", "-")


def _english_label(title: str) -> str:
    return _TRANSLATED_SUFFIX.sub("", title).strip()


def _section_methods(lines: list[str]) -> list[str]:
    """Read an endpoint section's HTTP verbs, in whichever form it declares them."""
    text = "\n".join(lines)
    for pattern in (_METHODS, _METHODS_TABLE_ROW):
        match = pattern.search(text)
        if match:
            verbs = _verbs(match.group(1))
            if verbs:
                return verbs

    # `### Active Methods` puts the verbs on a following line; `### HTTP Methods`
    # puts them in the first column of a table. Both end at the next heading.
    #
    # Blockquotes in between are commentary, never the declaration. The manual
    # repo normalizes the official docs' self-contradictions in `> ⚠️` callouts
    # that quote the rejected form in order to overrule it - /db/POLC-M1's says
    # the upstream `POST, GET, PUT, DELETE` table is untrusted and to keep
    # `GET`/`PUT`/`DELETE` until live confirmation. Reading verbs out of such a
    # callout restores exactly the value it exists to reject, so skip them.
    for index, line in enumerate(lines):
        if not _METHODS_HEADING.match(line):
            continue
        verbs: set[str] = set()
        for follow in lines[index + 1 :]:
            if follow.startswith("#"):
                break
            if follow.lstrip().startswith(">"):
                continue
            if follow.startswith("|"):
                cells = _split_row(follow)
                verbs.update(_verbs(cells[0]) if cells else [])
            else:
                verbs.update(_verbs(follow))
        if verbs:
            return sorted(verbs)
    return []

_KEY_COLUMNS = {"key", "키"}
_DESC_COLUMNS = {"description", "설명"}
_TYPE_COLUMNS = {"value type", "타입", "value 타입", "type"}
_DEFAULT_COLUMNS = {"default", "기본값", "기본값/enum"}
_REQUIRED_COLUMNS = {"required", "필수"}
#: A column that sorts a table's rows into modes or groups. See `_parse_tables`.
_GROUP_COLUMNS = {"모드", "그룹", "mode", "group"}
_ENUM_VALUE_COLUMNS = {"value", "값"}

_EMPTY_CELLS = {"", "-", "—", "–", "n/a", "N/A"}
_ENUM_VALUES_ELSEWHERE = "the manual types this as an enum but the values are listed elsewhere in the chapter"

# The chapters draw nesting with a box-drawing marker in the Description column.
_DESC_TREE = re.compile(r"^[└├│─\s]+")

# ...and, far more often, in the No. column: a parent is numbered `4`, its
# children `(1)`/`(2)` or `4-1`/`4-2`, and a grandchild `4-1-1`. 1,257 of the
# manual's 4,731 numbered rows are children this way. Missing it flattened
# /db/RIGD's ITEMS array into four sibling keys no payload actually has - a
# wrong contract that reached contracts/endpoints/ before type generation
# from the same contract exposed it.
#: A child number may carry a label after it: /db/FIBR numbers its colour row
#: `(1) R/G/B` under FIMP_COLOR, and reading that as a top-level row published
#: R, G and B beside FIMP_COLOR instead of inside its elements.
_NUMBER_CHILD = re.compile(r"^\((?:\d+|[ivxlcdm]+)\)(?:\s+\S.*)?$", re.IGNORECASE)

#: A third level the chapters mark without parentheses: a bare letter (`a`,
#: `b`, `c`) or a bare roman numeral (`i`, `ii`, `iii`). `/db/HHCT` numbers
#: `7` > `(1)`-`(3)` > `i`/`ii`, and `/db/SWIND` marks a child of an object
#: row with a letter while the parent's own No. cell is blank. Neither matches
#: `_NUMBER_CHILD`, which requires the parentheses, so 183 rows across 18
#: sections were read as root-level fields of the request.
#:
#: The damage is not only a wrong shape. `/db/SWIND` gives `OPT_USE` to both
#: `TOPOGRAPHIC_EFFECT` and `FORCE_COEF`; flattened to the root the second
#: overwrites the first and one documented field disappears. In `/db/HHCT` the
#: rows after `TOL` were adopted by it, so a `Number` grew children.
#:
#: The list of roman numerals is closed on purpose. A permissive
#: `[ivxlcdm]+` also matches `DB` and other words the No. column really does
#: carry - `/db/SECT` numbers two rows `DB` and `User`.
_ROMAN_SUBITEM = frozenset(
    "i ii iii iv v vi vii viii ix x xi xii".split()
)


def _is_number_subitem(number: str) -> bool:
    """Whether the No. cell marks a level below `(n)` without saying so."""

    token = number.strip()
    if len(token) == 1 and token.isalpha() and token.isascii():
        return True
    return token.lower() in _ROMAN_SUBITEM
# A Project Structure table also uses hybrid segments such as ``2-(1)``.
# They carry the same nesting meaning as ``2-1``: the parent record is row 2
# and the parenthesised segment is one level, not decorative prose.
#: Chapter 24 writes a two-level path with no separator at all: `(2)` is the
#: parent row and `(2)a`, `(2)b`, `(2)c` are its members. The parenthesised
#: number is a path segment here, not a sibling marker, so this is depth 2 -
#: and reading it as anything else is not a cosmetic error. Unmatched, these
#: rows fell to depth 0, which put `/db/REBR`'s `NAME`/`NUM`/`ROW` at the root
#: of the request instead of inside `MAIN_BAR`, and left the `(3)` after them
#: parented on `ROW`, an Integer. The section's own JSON Schema shows the
#: shape those rows describe.
_NUMBER_PAREN_SUBITEM = re.compile(r"^\((?:\d+|[ivxlcdm]+)\)[a-z]$", re.IGNORECASE)
#: The same two-level path with a dash between the segments: /db/SDIS numbers
#: LRB's `DX` row `(8)` and its four members `(8)-i` to `(8)-iv`, and the
#: description of each says "`DX` 하위" as well. Read flat, the four landed
#: beside `DX` inside LRB instead of in it.
_NUMBER_PAREN_DASH_SUBITEM = re.compile(r"^\((?:\d+)\)-(?:[ivx]+|[a-z])$", re.IGNORECASE)

_NUMBER_PATH = re.compile(r"^\d+(?:(?:[-.]\d+)|(?:[-.]\(\d+\)))+$")
_NUMBER_PATH_SEGMENT = re.compile(r"[-.](?:\d+|\(\d+\))")
# A small group of manual tables marks an immediate array-item member with a
# leading dash in the Description cell (for example ITEM followed by
# `- Time` and `- Value`).  This is deliberately narrower than treating an
# em dash in the No. column as structure: that form also appears for ordinary
# root rows in the load-combination manuals.
_DESC_ARRAY_CHILD = re.compile(r"^-\s+")

# Two chapters mark a member by naming its parent in the Description cell and
# leaving the No. column an em dash: `| — | (vCOMB) 해석 타입 | "ANAL" | ...`.
# This is the most explicit nesting form in the whole manual - the parent is
# named, not implied by adjacency or by a number - and it was the one form
# nothing read, so 21 rows across chapters 13 and 14 became root fields. Six
# /db/LCOM-* contracts and /db/POGD published ANAL/LCNAME/FACTOR and
# LC_NAME/LC_TYPE/SF as siblings of the array that contains them.
_DESC_NAMED_PARENT = re.compile(r"^\((?P<parent>[A-Za-z_][A-Za-z0-9_]*)\)\s*")


def _slug(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")


def _clean(cell: str) -> str:
    """Strip the markdown the manual decorates cells with, not their content."""
    text = cell.strip()
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = text.replace("`", "").strip()
    # Some tables escape brackets solely to keep Markdown from interpreting an
    # array type as a link.  The backslashes are presentation syntax, not part
    # of the documented wire type (for example ``Array \[Number, 3\]``).
    text = text.replace("\\[", "[").replace("\\]", "]")
    # Footnote markers: superscript digits and the "¹⁾" form the chapters use.
    text = re.sub(r"[\u00b9\u00b2\u00b3\u2070-\u209f]+\)?", "", text)
    return text.strip()


_REQUIRED_WORDS = {"required", "필수"}
_OPTIONAL_WORDS = {"optional", "선택"}


def _normalize_requirement(cell: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (requirement, condition, note). None requirement = the manual did not say.

    Many rows qualify the answer in place - `Required (bEXACTSPAN=true)`,
    `필수 (ADDITIONAL_LOAD 사용 시)`. That is a real condition stated in the
    manual's own words, so it is carried across verbatim rather than flattened
    to "required" (which would overstate it) or dropped (which would lose it).
    """
    raw = _clean(cell)
    text = raw.lower()
    if text in _EMPTY_CELLS:
        # Preserve the absence of a documentation claim. A later JSON Schema
        # in this same manual section may still state requiredness; only the
        # renderer turns an unresolved None into the explicit contract value
        # ``unstated``.
        return None, None, None
    if "read only" in text or "readonly" in text:
        return "read_only", None, None
    if text in {"get only", "get-only"}:
        # The manual's Required column uses this to say the member appears
        # only in a GET response. That is the contract's read_only category,
        # not an optional write claim.
        return "read_only", None, None
    if text in {"create only", "create-only"}:
        # The sibling of "Get Only": the manual claims the server reads the
        # field on POST and ignores it on PUT. It appears in exactly two cells
        # in the whole manual, both a `CALC_OPT`, and on 2026-09-03 the two
        # were measured against a live product and disagreed - /db/SECT
        # behaves as the cell says and /db/SPFC does not (see
        # docs/live_verification_notes.md, and MD-15). So this records the
        # documentation like every other value here, and where a measurement
        # contradicts it, _MANUAL_REQUIREDNESS_CORRECTIONS carries the
        # correction rather than this function quietly picking a side.
        return "create_only", None, None
    if raw == "SRC: \ud544\uc218 / CONCRETE\u00b7STEEL: \uc120\ud0dd":
        # This is a manual condition, not a missing requiredness value. Keep
        # it verbatim because the table does not put the controlling
        # CODE_SELECTION equality in this cell itself.
        return "conditional", raw, None

    mixed = re.fullmatch(
        r"Optional\s*\((.+)\)\s*/\s*Required\s*\((.+)\)",
        raw,
        re.IGNORECASE,
    )
    if mixed:
        # One field can be optional in one documented branch and required in
        # another. Keep the whole branch statement rather than flattening one.
        return "conditional", raw, None

    qualified = re.match(r"^(.*?)\s*[（(]\s*(.+?)\s*[)）]\s*$", raw)
    if qualified:
        base = qualified.group(1).strip().lower()
        condition = qualified.group(2).strip()
        if base in _REQUIRED_WORDS or "조건부" in base:
            return "conditional", condition, None
        if base in _OPTIONAL_WORDS:
            suffix = (
                "; this documents the effect of omission rather than a condition on the field"
                if "생략 시" in condition
                else ""
            )
            return "optional", None, f"the manual qualifies this Optional with {condition!r}{suffix}"

    if "조건부" in text or "conditional" in text:
        return "conditional", None, "the manual marks this conditional but does not state the condition"
    if text in _REQUIRED_WORDS | {"o", "yes", "y"}:
        return "required", None, None
    if text in _OPTIONAL_WORDS | {"x", "no", "n"}:
        return "optional", None, None
    if text in {"불명", "unknown", "미상"}:
        return None, None, None

    # A cell that answers the column and then adds a cross-field rule.
    # /db/POGD-M1 writes four of them - "필수. true이면 BEAM_COLUMN/WALL 중 최소
    # 1개는 true, false이면 둘 다 미기재" - and the rule is about two *other*
    # fields, so it is neither a condition on this one (which is what
    # `qualified` above captures) nor a reason to lose the requiredness the
    # column does state. Take the word, keep the sentence as a note. Anything
    # mentioning 조건부 is already handled above and never reaches here.
    sentence = re.match(r"^([^.。]+)[.。]\s*(\S.*)$", raw.strip())
    if sentence:
        head = sentence.group(1).strip().lower()
        rest = sentence.group(2).strip()
        if head in _REQUIRED_WORDS:
            return "required", None, f"the manual adds a cross-field rule to this Required cell: {rest}"
        if head in _OPTIONAL_WORDS:
            return "optional", None, f"the manual adds a cross-field rule to this Optional cell: {rest}"

    return None, None, f"unrecognised Required value {raw!r}"


_DESCRIPTION_CONDITION_MARKERS = (
    "if ",
    "when ",
    "\uc77c \ub54c",
    "\uacbd\uc6b0",
    "\uc0ac\uc6a9 \uc2dc",
    "\uc804\uc6a9",
)


_DESCRIPTION_LITERAL_CONDITION = re.compile(
    r"`?([A-Za-z_][A-Za-z0-9_.]*)`?\s*=\s*`?([A-Za-z][A-Za-z0-9_-]*)`?"
)


# A description can name the value at which a field applies, or the value at
# which it does *not* - ``(SELECTION_TYPE="ALL"이면 무시됨)`` is the second, and
# reading it as the first inverts the condition into the exact opposite of what
# the manual says.  The equality alone cannot tell them apart, so a phrase
# carrying one of these verbs stops the structured translation and keeps the
# manual's wording as the condition for a reviewer to translate by hand.
_CONDITION_NEGATIONS = (
    "무시",       # 무시 - ignored
    "제외",       # 제외 - excluded
    "사용하지",  # 사용하지 (않음) - not used
    "사용 안",       # 사용 안 (함)
    "해당 없",       # 해당 없(음)
    "불필요",  # 불필요 - unnecessary
    "ignored",
    "not used",
    "not required",
)


def _condition_negates(text: str) -> bool:
    """Whether a condition phrase names the value the field does *not* apply at."""

    lowered = _clean(text).lower()
    return any(marker in lowered for marker in _CONDITION_NEGATIONS)


def _negated_condition_phrase(cell: str) -> Optional[str]:
    """Return the parenthesised phrase that states when the field does not apply.

    Kept verbatim for the same reason ``_condition_from_description`` keeps its
    own: the contract's ``condition`` records the manual's sentence, and only
    the hand-written ``appliesWhen`` turns it around.
    """

    text = _clean(cell)
    parts = [part.strip() for part in re.findall(r"\(([^()]*)\)", text)]
    parts.extend(
        part.strip() for part in re.split(r"\s+[—–]\s+", text)[1:]
    )
    negating = [part for part in parts if part and _condition_negates(part)]
    return negating[0] if len(negating) == 1 else None


def _description_literal_condition(text: str) -> tuple[str, str | int | float | bool] | None:
    """Read one literal selector that a conditional field's description states.

    Markdown tables use both JSON-like ``CODE=\"Standard\"`` and the shorter
    manual spelling ``INPUT_METHOD=KEYS``. The latter is still an explicit
    wire-value equality when it is the sole equality in that field's own
    description. Do not accept prose alternatives, ranges, or more than one
    equality: those need a human review rather than a guessed ``appliesWhen``.
    """

    structured = _variant_condition(text)
    if structured is not None:
        return structured
    matches = _DESCRIPTION_LITERAL_CONDITION.findall(_clean(text))
    distinct = list(dict.fromkeys(matches))
    if len(distinct) != 1:
        return None
    path, value = distinct[0]
    if value.lower() in {"true", "false"}:
        return path, (value.lower() == "true",)
    return path, (value,)


def _condition_from_description(cell: str) -> Optional[str]:
    """Keep one condition phrase the parameter description states verbatim.

    ``Conditional Required`` is often terse in the Required column, while the
    Description says exactly when it applies in a parenthesis or after a dash.
    This deliberately retains the manual phrase rather than inferring a
    selector from a sibling field or an example.
    """

    text = _clean(cell)

    def says_when(value: str) -> bool:
        return any(marker in value.lower() for marker in _DESCRIPTION_CONDITION_MARKERS)

    candidates = [part.strip() for part in re.findall(r"\(([^()]*)\)", text) if says_when(part)]
    dash_parts = re.split(r"\s+[\u2014\u2013]\s+", text)
    if len(dash_parts) > 1:
        candidates.extend(part.strip() for part in dash_parts[1:] if says_when(part))
    distinct = list(dict.fromkeys(candidate for candidate in candidates if candidate))
    return distinct[0] if len(distinct) == 1 else None


def _normalize_type(cell: str) -> tuple[Optional[str], Optional[dict], Optional[str]]:
    """Return (type, items, note)."""
    text = _clean(cell)
    if text in _EMPTY_CELLS:
        # As with Required, leave this open for a same-section JSON Schema
        # hint. If none exists, the contract renderer records ``unstated``
        # rather than fabricating a string type.
        return None, None, None
    compact_array = re.match(r"^(String|Integer|Number|Boolean|Object|Real)\s*,\s*(\d+)$", text, re.IGNORECASE)
    if compact_array:
        inner, _, note = _normalize_type(compact_array.group(1))
        return "array", ({"type": inner} if inner else None), note
    fixed_array = re.match(
        r"^Array\s*\[\s*(String|Integer|Number|Boolean|Object|Real)\s*,\s*(\d+)\s*\]$",
        text,
        re.IGNORECASE,
    )
    if fixed_array:
        # ``Array[Number,21]`` is one 21-value number array, not an array
        # whose elements are themselves 21-value arrays.  The comma-length
        # form also appears without the outer ``Array[...]`` in older tables.
        inner, _, note = _normalize_type(fixed_array.group(1))
        return "array", ({"type": inner} if inner else None), note
    array = re.match(
        r"^Array\s*\[\s*(.+?)\s*\](?:\s*\([^)]*\))?$",
        text,
        re.IGNORECASE,
    )
    if array:
        # ``Array[{PY, PZ}]`` is the manual's compact spelling for an array of
        # objects. Its named members still have to appear in adjacent rows;
        # this only reads the container type the cell itself states.
        if re.fullmatch(r"\{[^{}]+\}", array.group(1).strip()):
            return "array", {"type": "object"}, None
        inner, _, note = _normalize_type(array.group(1))
        return "array", ({"type": inner} if inner else None), note
    base = text.lower()
    note = None
    boolean_default = re.match(r"^boolean\s*\(\s*(?:기본|default)\s+(true|false)\s*\)$", base)
    if boolean_default:
        base = "boolean"
    enum_wrapper = re.match(r"^enum\s*\(\s*(string|integer|number)\s*\)$", base)
    if enum_wrapper:
        base = enum_wrapper.group(1)
        note = _ENUM_VALUES_ELSEWHERE
    if re.match(r"^boolean\s*\(\s*(?:oneof|one of)\s*\)$", base):
        base = "boolean"
    object_shape = re.match(r"^object\s*\(\s*(?:oneof|[^)]*/[^)]*)\s*\)$", base)
    if object_shape:
        return (
            "object",
            None,
            "the manual qualifies this object shape, but does not state a representable property schema",
        )
    if re.fullmatch(r'"[^"\\]+"', text):
        return "string", None, None
    const_type = re.match(r"^(string|integer|number|real)\s*\(\s*const(?:\s+[^)]*)?\s*\)$", base)
    if const_type:
        base = const_type.group(1)
    constraint_base = re.match(
        r"^(string|integer|number|real)\s*\((?:≥\s*-?\d+(?:\.\d+)?|>\s*-?\d+(?:\.\d+)?|"
        r"-?\d+(?:\.\d+)?\s*~\s*-?\d+(?:\.\d+)?|0\s*(?:금지|초과\s*1\s*이하)|\d+)\)$",
        base,
    )
    if constraint_base:
        base = constraint_base.group(1)
    enum_hint = re.match(
        r"^(string|integer|number)\s*(?:\(\s*(enum|oneof|one of)(?:\s*:\s*[^)]*)?\s*\)|\s+(enum|oneof|one of))$",
        base,
    )
    if enum_hint:
        base = enum_hint.group(1)
        note = _ENUM_VALUES_ELSEWHERE
    if base in {"number", "double", "float", "real"}:
        return "number", None, note
    if base in {"integer", "int"}:
        return "integer", None, note
    if base in {"string", "str"}:
        return "string", None, note
    if base in {"boolean", "bool"}:
        return "boolean", None, note
    if base in {"object", "json"}:
        return "object", None, note
    if base.startswith("array"):
        return "array", None, "array element type not stated by the manual"
    return None, None, f"unrecognised Value Type {text!r}"


def _number(text: str) -> int | float:
    number = float(text)
    return int(number) if number.is_integer() else number


def _type_constraints(cell: str) -> dict[str, Any]:
    """Return only range/length constraints spelled out by the manual type cell."""

    text = _clean(cell)
    string_const = re.fullmatch(r'"([^"\\]+)"', text)
    if string_const:
        return {"const": string_const.group(1)}
    const = re.fullmatch(r"(?:Number|Integer|Real)\s*\(\s*const\s+(-?\d+(?:\.\d+)?)\s*\)", text, re.IGNORECASE)
    if const:
        return {"const": _number(const.group(1))}
    compact_array = re.fullmatch(
        r"(?:Array\s*\[\s*)?(?:String|Integer|Number|Boolean|Object|Real)\s*,\s*(\d+)(?:\s*\])?",
        text,
        re.IGNORECASE,
    )
    if compact_array:
        length = int(compact_array.group(1))
        return {"minItems": length, "maxItems": length}
    minimum_array = re.fullmatch(
        r"Array\s*\[[^]]+\]\s*\(\s*≥\s*(\d+)\s*개\s*\)",
        text,
        re.IGNORECASE,
    )
    if minimum_array:
        return {"minItems": int(minimum_array.group(1))}
    string_length = re.fullmatch(r"String\s*\(\s*(\d+)\s*\)", text, re.IGNORECASE)
    if string_length:
        length = int(string_length.group(1))
        return {"minLength": length, "maxLength": length}

    match = re.fullmatch(r"(?:Number|Integer|Real)\s*\((.+)\)", text, re.IGNORECASE)
    if not match:
        return {}
    constraint = re.sub(r"\s+", "", match.group(1))
    if constraint.lower() in {"0금지", "0notallowed"}:
        return {"notEqual": 0}
    if constraint == "0초과1이하":
        return {"exclusiveMinimum": 0, "maximum": 1}
    if match := re.fullmatch(r"≥(-?\d+(?:\.\d+)?)", constraint):
        return {"minimum": _number(match.group(1))}
    if match := re.fullmatch(r">(-?\d+(?:\.\d+)?)", constraint):
        return {"exclusiveMinimum": _number(match.group(1))}
    if match := re.fullmatch(r"(-?\d+(?:\.\d+)?)~(-?\d+(?:\.\d+)?)", constraint):
        return {"minimum": _number(match.group(1)), "maximum": _number(match.group(2))}
    return {}


def _type_default(cell: str) -> Any | None:
    """Read an explicit default only where the type cell itself spells it out."""

    match = re.fullmatch(
        r"Boolean\s*\(\s*(?:기본|default)\s+(true|false)\s*\)", _clean(cell), re.IGNORECASE
    )
    return match.group(1).lower() == "true" if match else None


def _enum_values_from_inline_type(cell: str) -> list[Any]:
    """Read only explicit enum literals from a Value Type cell."""

    text = _clean(cell)
    match = re.search(r"\b(?:enum|oneof|one of)\s*:\s*(.+?)\s*\)?$", text, re.IGNORECASE)
    if not match:
        return []
    return _quoted_enum_values(match.group(1))


def _quoted_enum_values(text: str) -> list[Any]:
    """Return explicit double-quoted enum literals, preserving their order."""

    values: list[Any] = []
    for value in re.findall(r'"([^"\\]+)"', text):
        if value not in values:
            values.append(value)
    return values


def _enum_values_from_description(text: str) -> list[Any]:
    """Read an explicitly enumerated description without treating ranges as enums.

    The manual commonly writes integer alternatives as ``0=Simplified /
    1=General``.  Two or more distinct ``number=label`` pairs are a complete
    finite list; a lone condition such as ``MODE=0`` or a range like ``0~20``
    is not, so neither becomes an enum here.  Later chapters put each numeric
    value in a Markdown code span (``Stress: `0` / Force: `1```); those spans
    are likewise an explicit finite list, unless the text uses a range or an
    ellipsis to leave values unstated.
    """

    # An ellipsis is a shorthand for values the manual did not actually list
    # (for example ``1=Method-1 … 4=Method-4``).  It is not evidence for the
    # intervening values, so preserve the enum review note instead of making a
    # partial claim.
    if "..." in text or "…" in text:
        return []

    # Numeric wire values in the manuals are often written as individual code
    # spans.  Treat only two or more non-range spans as an enum.  A code span
    # adjacent to ``~`` is a documented bound, not an alternative.
    code_numeric: list[int | float] = []
    for match in re.finditer(r"`\s*(-?\d+(?:\.\d+)?)\s*`", text):
        before = text[: match.start()].rstrip()
        after = text[match.end() :].lstrip()
        if (before and before[-1] == "~") or (after and after[0] == "~"):
            continue
        value = _number(match.group(1))
        if value not in code_numeric:
            code_numeric.append(value)
    if len(code_numeric) >= 2:
        return code_numeric

    values: list[int | float] = []
    for literal in re.findall(r"(?<![A-Za-z0-9_.-])(-?\d+(?:\.\d+)?)\s*=", text):
        number = float(literal)
        value = int(number) if number.is_integer() else number
        if value not in values:
            values.append(value)
    if len(values) >= 2:
        return values

    # Some chapters reverse the pair as `Simplified: 0 / General: 1`.
    # A single colon-number can be a prose condition, so accept it only when
    # the field's own enum description names at least two distinct values.
    reverse_numeric: list[int | float] = []
    for literal in re.findall(r":\s*(-?\d+(?:\.\d+)?)(?=\s*(?:[),/·;]|$))", text):
        number = float(literal)
        value = int(number) if number.is_integer() else number
        if value not in reverse_numeric:
            reverse_numeric.append(value)
    if len(reverse_numeric) >= 2:
        return reverse_numeric

    # Design-code chapters also spell a choice as ``Static: STATIC / Stage:
    # STAGE``. The right-hand tokens are the wire values; require two uppercase
    # tokens so a single prose label or ``CODE: Standard`` cannot become an
    # enum by accident.
    reverse_symbolic: list[str] = []
    for value in re.findall(r":\s*([A-Z][A-Z0-9_-]*)(?=\s*(?:[),/·;]|$))", text):
        if value not in reverse_symbolic:
            reverse_symbolic.append(value)
    if len(reverse_symbolic) >= 2:
        return reverse_symbolic

    # A slash-separated number list such as ``(0/1/2)`` is likewise a finite
    # set when the field itself is already typed enum. Do not accept a tilde or
    # dash range here: those are bounds, not alternatives.
    numeric_list = re.search(
        r"(?<![A-Za-z0-9_.-])(-?\d+(?:\.\d+)?(?:\s*/\s*-?\d+(?:\.\d+)?)+)(?![A-Za-z0-9_.-])",
        text,
    )
    if numeric_list:
        listed: list[int | float] = []
        for literal in re.split(r"\s*/\s*", numeric_list.group(1)):
            value = _number(literal)
            if value not in listed:
                listed.append(value)
        if len(listed) >= 2:
            return listed

    # A quoted value on the right side of ``OTHER_FIELD=\"VALUE\"`` is a
    # selector for this field, not one of this field's possible values. The
    # manual expresses string enum alternatives as ``Label: `VALUE``` (often
    # joined by ``/``). Require a label delimiter in the description: this
    # keeps an incidental code-spanned field name such as ``TABLE_TYPE`` out
    # of an otherwise numeric enum description.
    code_symbolic: list[str] = []
    for match in re.finditer(r"`\s*((?=[A-Z0-9_-]*[A-Z])[A-Z0-9_-]+)\s*`", text):
        before = text[: match.start()]
        if ":" not in before:
            continue
        symbolic_value = match.group(1)
        if symbolic_value not in code_symbolic:
            code_symbolic.append(symbolic_value)
    if len(code_symbolic) >= 2:
        return code_symbolic

    # Design-code tables sometimes list symbolic choices as a comma-separated
    # run of individual code spans: ``None``, ``SD300``, ``SD400``.  Unlike a
    # range (``D4 ~ D57``) or an ellipsis, every member is written explicitly.
    # Read only a contiguous run, so unrelated backticked field names elsewhere
    # in the description cannot become this field's enum.
    if match := re.search(
        r"`[A-Za-z0-9_.%/-]+`(?:\s*,\s*`[A-Za-z0-9_.%/-]+`)+", text
    ):
        return re.findall(r"`([A-Za-z0-9_.%/-]+)`", match.group(0))

    quoted = _quoted_enum_values(text)
    if quoted:
        return quoted

    # The same cell form is used for symbolic values, for example
    # ``Equivalent=... / Each=...``.  Requiring two distinct left-hand codes
    # keeps a condition on another field (``CODE=Standard``) out of this
    # field's enum.
    symbolic: list[str] = []
    for value in re.findall(r"(?<![A-Za-z0-9_.-])([A-Za-z][A-Za-z0-9_/-]*)\s*=", text):
        if value not in symbolic:
            symbolic.append(value)
    return symbolic if len(symbolic) >= 2 else []


def _enum_scalar(cell: str) -> Any | None:
    """Parse a complete value-table cell, or leave non-literal prose alone."""

    text = _clean(cell)
    if re.fullmatch(r'"[^"\\]+"', text):
        return text[1:-1]
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"
    if re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        number = float(text)
        return int(number) if number.is_integer() else number
    return None


def _normalize_default(cell: str) -> tuple[Any, Optional[str]]:
    """Return (default, note). None means the manual documents no default."""
    text = _clean(cell)
    if text in _EMPTY_CELLS:
        return None, None
    low = text.lower()
    if low in {"false", "true"}:
        return low == "true", None
    if low in {"blank", "빈 문자열", '""'}:
        return "", None
    # A quoted string is a complete literal default, just like a JSON array or
    # object below. The manual uses this form for values such as ``"FIRST"``
    # and ``"ACTIVE"``; retaining its quotes as part of the value would turn a
    # documented fact into an unnecessary review note.
    if text.startswith('"') and text.endswith('"'):
        try:
            literal = json.loads(text)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(literal, str):
                return literal, None
    # ``[]``, ``{}``, and JSON lists such as ``[\"AXIAL\"]`` are complete,
    # typed defaults stated by the manual. Keeping them as strings makes a
    # documented default look unverified, while interpreting prose such as
    # ``Auto`` or ``System`` would be a guess. Accept only a whole JSON array
    # or object so the distinction stays explicit.
    if text.startswith(("[", "{")):
        try:
            structured = json.loads(text)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(structured, (list, dict)):
                return structured, None
    try:
        number = float(text)
    except ValueError:
        return text, f"non-literal default {text!r} kept verbatim; confirm what the server does"
    return int(number) if number.is_integer() else number, None


@dataclass
class ParsedField:
    key: str
    description: str
    type: Optional[str]
    items: Optional[dict]
    requirement: Optional[str]
    documented_default: Any
    documented_default_note: Optional[str] = None
    enum: list[Any] = dataclass_field(default_factory=list)
    constraints: dict[str, Any] = dataclass_field(default_factory=dict)
    condition: Optional[str] = None
    # (path, values). One value renders as `equals`, several as `in` - the
    # manual's `A = 1 or 2` form, never a guessed alternative.
    applies_when: list[tuple[str, tuple[str | int | float | bool, ...]]] = dataclass_field(
        default_factory=list
    )
    number: str = ""
    notes: list[str] = dataclass_field(default_factory=list)
    properties: list["ParsedField"] = dataclass_field(default_factory=list)
    products: tuple[str, ...] = ()
    shared_number_group: bool = False
    default_column_missing: bool = False


# JSON member names may begin with a digit.  ``7TH_DOF_TYPE`` is an exact,
# quoted wire key in the bridge-operation chapter; rejecting it would turn a
# documented property into an invented ambiguity.  Keep the rest deliberately
# narrow so separators and prose still fail closed.
_PATH_SEGMENT = re.compile(r"^([A-Za-z0-9_]+)(\[\])?$")


def _split_path(key: str) -> Optional[list[tuple[str, bool]]]:
    """Split `PERMIT_LOAD.AXLE_TYPES` or `POINT_ITEMS[].POINT_LOAD` into segments.

    Returns None for anything that is not a clean path, so callers can flag it
    instead of guessing. 121 rows in the manual name two keys at once
    (`"ELEMS" / "SECTIONS"`) and those are genuinely ambiguous - the right
    response is to say so, not to pick one.
    """
    segments: list[tuple[str, bool]] = []
    for part in key.split("."):
        match = _PATH_SEGMENT.match(part)
        if not match:
            return None
        segments.append((match.group(1), bool(match.group(2))))
    return segments


#: Value Types that cannot hold members. When the No. column numbers a row as
#: the child of one of these, the manual is not describing containment - it is
#: pointing at the row above. `/db/SPLC` writes `30 bNDP` (Boolean) then
#: `(1) NDP` (Number, Required), and `NDP` is the value that flag turns on, a
#: sibling rather than a member. Measured across the manual, five rows are
#: numbered under a declared scalar and all five read that way; two of them
#: are independently settled - `/db/SECT`'s `CALC_OPT` was driven live on
#: 2026-09-03 as the boolean the table says it is, and `/db/REBW`'s section is
#: already known wrong field-for-field against a live model.
#:
#: Retyping the parent to `object` is the same shape of invention as reading a
#: gate out of a code name: it resolves a contradiction between two statements
#: by silently discarding one. The row is kept at the parent's own level with a
#: note instead, and which value gates it is left for review - the manual
#: states the pairing, never the trigger.
_SCALAR_TYPES = frozenset({"string", "number", "integer", "boolean"})


def _can_hold_children(field: ParsedField) -> bool:
    # `_nest` runs before the Value Type is normalized in some paths and after
    # it in others, so compare case-insensitively rather than depend on which.
    return (field.type or "").lower() not in _SCALAR_TYPES


def _as_container(field: ParsedField, is_array: bool) -> None:
    """Make a field able to hold children, without discarding what it declared."""
    if is_array:
        if field.type not in {"array"}:
            if field.type not in {None, "object"}:
                field.notes.append(
                    f"the manual types this {field.type!r} but its children are addressed as "
                    f"an array; treated as array of objects"
                )
            field.type = "array"
        field.items = {"type": "object"}
    elif field.type not in {"object", "array"}:
        if field.type is not None:
            field.notes.append(
                f"the manual types this {field.type!r} but it has nested children; treated as object"
            )
        field.type = "object"


def _place_beside_scalar(
    entry: ParsedField,
    parent: ParsedField,
    by_depth: dict[int, ParsedField],
    depth: int,
    roots: list[ParsedField],
) -> None:
    """Put a row the manual numbered under a scalar next to it, not inside it.

    See `_SCALAR_TYPES`. The row keeps the parent's own level, so a payload
    that had `{"bNDP": {"NDP": 1}}` now has `{"bNDP": ..., "NDP": ...}`, which
    is what the manual's own request examples send.
    """
    entry.notes.append(
        f"the manual numbers this {entry.number!r}, under {parent.key!r}, which it "
        f"types {parent.type!r} - a value that cannot hold members. Read as the "
        f"row above pointing at this one rather than containing it, so it is kept "
        f"beside {parent.key!r}. Which value of {parent.key!r} requires it is not "
        f"stated in the table; add appliesWhen if a permitted source says"
    )
    grandparent = by_depth.get(depth - 2)
    if grandparent is not None and _can_hold_children(grandparent):
        grandparent.properties.append(entry)
    else:
        roots.append(entry)
    by_depth[depth - 1] = entry


def _nest(flat: list[ParsedField]) -> list[ParsedField]:
    """Turn the manual's dotted Key paths into real nested fields.

    The chapters address nested payload members four ways: a dotted path in the
    Key column (`DATA1.DESIGN.C_FC`), a bracketed array path
    (`POINT_ITEMS[].POINT_LOAD`), a `└` tree marker that sometimes leaks out of
    the Description column into the Key, and - most often of all - the No.
    column, where a parent is `4` and its children are `(1)`/`(2)`, `4-1`/`4-2`,
    or `4.1`/`4.2`.
    All four describe structure the contract can represent exactly, so they are
    reconstructed rather than flattened into keys no payload actually has.
    """
    roots: list[ParsedField] = []
    by_path: dict[tuple[str, ...], ParsedField] = {}
    last_root: Optional[ParsedField] = None
    by_depth: dict[int, ParsedField] = {}
    by_tree_depth: dict[int, ParsedField] = {}
    last_assigned_depth = 0
    last_was_subitem = False
    last_entry: Optional[ParsedField] = None

    for entry in flat:
        key = entry.key

        # A parent named outright in the Description cell wins over every
        # positional rule below: it is a statement, not an inference from where
        # the row sits. Only an already-seen field can be the target, so a
        # parenthesis that happens to look like a key cannot invent one.
        named_parent = _DESC_NAMED_PARENT.match(entry.description or "")
        if named_parent and "." not in key and not key.startswith("└"):
            wanted = named_parent.group("parent")
            target = next(
                (field for field in _walk(roots) if field.key == wanted and _can_hold_children(field)),
                None,
            )
            if target is not None:
                entry.description = entry.description[named_parent.end():].strip()
                entry.notes.append(
                    f"the manual nests this under {target.key!r} by naming it in the "
                    f"description, with no number of its own"
                )
                _as_container(target, is_array=target.type == "array")
                target.properties.append(entry)
                continue

        # The No. column decides nesting unless the key itself spells out a
        # path, which is unambiguous and wins.
        if (
            _DESC_ARRAY_CHILD.match(entry.description)
            and "." not in key
            and last_root is not None
            and last_root.type == "array"
        ):
            entry.notes.append(
                f"the manual nests this under {last_root.key!r} by a dash description row"
            )
            _as_container(last_root, is_array=True)
            last_root.properties.append(entry)
            continue
        # The row before this one, captured before `last_entry` moves on: the
        # sub-item rule below asks what the *previous* row was.
        previous = last_entry
        last_entry = entry
        depth = 0
        is_subitem = False
        if _NUMBER_CHILD.match(entry.number):
            depth = 1
        elif _NUMBER_PAREN_SUBITEM.match(entry.number) or _NUMBER_PAREN_DASH_SUBITEM.match(entry.number):
            depth = 2
        elif _NUMBER_PATH.match(entry.number):
            depth = len(_NUMBER_PATH_SEGMENT.findall(entry.number))
        elif _is_number_subitem(entry.number):
            is_subitem = True
            # The marker says "another item", never how deep, and the chapters
            # mean two different things by it. Read it against the row before:
            #
            #   after another bare marker -> a sibling of that row. Chapter 26
            #     enumerates a request's own top-level members `a`, `b`, `c`,
            #     `d`, and nesting `b` under `a` would bury MAIN_BAR_BOT inside
            #     MAIN_BAR_TOP.
            #   after a container row marked some other way -> its child. That
            #     is /db/SWIND's blank-celled `TOPOGRAPHIC_EFFECT` and
            #     /db/HHCT's `(3)` `M_GENERAL`.
            #   after anything else -> a sibling, because there is nothing to
            #     be a child of.
            if last_was_subitem:
                depth = last_assigned_depth
            elif previous is not None and previous.type in {"object", "array"}:
                depth = last_assigned_depth + 1
            else:
                depth = last_assigned_depth
        last_was_subitem = is_subitem
        # The No. column says how deep the row is, not only who its parent is.
        # Keep it for the root branch below, where the loop over a dotted key
        # rebinds `depth` to a segment index.
        number_depth = depth
        last_assigned_depth = depth
        if depth and entry.shared_number_group and "." not in key and not key.startswith("└"):
            grouped_parent = by_depth.get(depth - 1)
            if grouped_parent is not None and not _can_hold_children(grouped_parent):
                _place_beside_scalar(entry, grouped_parent, by_depth, depth, roots)
                continue
            if grouped_parent is not None:
                entry.notes.append(
                    f"the manual nests this under {grouped_parent.key!r} by numbering it "
                    f"{entry.number!r}, not by naming a path"
                )
                _as_container(grouped_parent, is_array=grouped_parent.type == "array")
                grouped_parent.properties.append(entry)
                by_depth[depth] = entry
                continue
            # A compact row can give multiple siblings the same child number.
            # Without an already-known numbered parent, the first key cannot
            # become an invented parent for the following literal keys.
            roots.append(entry)
            continue
        if depth and "." not in key and not key.startswith("└"):
            parent = by_depth.get(depth - 1)
            if parent is not None and not _can_hold_children(parent):
                _place_beside_scalar(entry, parent, by_depth, depth, roots)
                continue
            if parent is not None:
                entry.notes.append(
                    f"the manual nests this under {parent.key!r} by numbering it "
                    f"{entry.number!r}, not by naming a path"
                )
                _as_container(parent, is_array=parent.type == "array")
                parent.properties.append(entry)
                by_depth[depth] = entry
                continue
        # The marker repeats once per level: `└ CHILD`, `└ └ GRANDCHILD`,
        # `└ └ └ LEAF`. Glyphs are separated by a space, so counting them is
        # the depth; stripping them as a set collapses every level onto the
        # first and leaves the rest of the row unparseable.
        tree_depth = key.count("└")
        tree_marked = tree_depth > 0
        if tree_marked:
            key = key.lstrip("└ 	").strip()

        segments = _split_path(key)
        if segments is None:
            entry.notes.append(
                f"key {entry.key!r} is not a single field name; the manual names more than one "
                f"key in this row, or decorates it - confirm the wire name by hand"
            )
            roots.append(entry)
            continue

        if tree_marked and len(segments) == 1:
            tree_parent = last_root if tree_depth == 1 else by_tree_depth.get(tree_depth - 1)
            if tree_parent is not None:
                entry.key = segments[0][0]
                entry.notes.append(
                    f"the manual nests this under {tree_parent.key!r} with a tree marker "
                    f"rather than a path"
                )
                _as_container(tree_parent, is_array=False)
                tree_parent.properties.append(entry)
                by_tree_depth[tree_depth] = entry
                continue

        path: tuple[str, ...] = ()
        parent: Optional[ParsedField] = None
        for depth, (name, is_array) in enumerate(segments):
            path = path + (name,)
            leaf = depth == len(segments) - 1
            existing = by_path.get(path)

            if leaf:
                entry.key = name
                if is_array and entry.type is None:
                    entry.type = "array"
                if existing is not None:
                    # The manual listed the container first and is now listing it
                    # again as a leaf; keep the container and its children.
                    existing.notes.append("the manual documents this key twice; kept the first row")
                    break
                by_path[path] = entry
                (parent.properties if parent is not None else roots).append(entry)
                if parent is None:
                    last_root = entry
                    by_tree_depth.clear()
                    # A row the manual numbered `(1)` is a child that never
                    # found its parent - a supplementary table whose rows are
                    # all `(1)`-`(5)`, such as `/db/RCHK`'s layer item
                    # structure, has no parent row of its own. Recording it at
                    # depth 0 made it the parent of its own siblings: `LAYER`
                    # became an object holding `dD`, `BAR_NUM` and the rest,
                    # which the section's schema and its request example both
                    # write beside it. Keep the row at the depth the manual
                    # gave it, so the siblings that follow stay siblings.
                    by_depth[number_depth] = entry
                    for deeper in [level for level in by_depth if level > number_depth]:
                        del by_depth[deeper]
                break

            if existing is None:
                existing = ParsedField(
                    key=name,
                    description="",
                    type=None,
                    items=None,
                    requirement=None,
                    documented_default=None,
                    notes=[
                        "no row of its own in the manual - inferred from the dotted paths of its "
                        "children, so its requiredness and default are unknown"
                    ],
                )
                by_path[path] = existing
                (parent.properties if parent is not None else roots).append(existing)
                if parent is None:
                    last_root = existing
                    by_tree_depth.clear()
            _as_container(existing, is_array)
            parent = existing

    return roots


_ESCAPED_PIPE = "\\|"
_PIPE_PLACEHOLDER = "\x00"


def _split_row(line: str) -> list[str]:
    r"""Split one markdown table row into cells, honouring escaped pipes.

    ``\|`` is GFM's escape for a literal pipe inside a cell, and the manual
    uses it to write alternatives - ``None \| 50% \| 100%``.  Splitting on
    every ``|`` gives such a row more cells than its header has, and every
    caller drops a row whose cell count disagrees, so one escaped pipe
    silently deletes a documented field.  Ten rows across three chapters were
    being lost that way, including ``/ope/LCOM-GEN``'s **required**
    ``CODE_SELECTION`` body discriminator and ``SPLICED_BARS`` on the three
    ``DCRM-*`` endpoints - five of the nine sections MD-10 recorded as a
    Specifications table contradicting its own JSON Schema.

    The escape is dropped from the cell text: ``\|`` means a literal ``|``.
    """

    parts = line.replace(_ESCAPED_PIPE, _PIPE_PLACEHOLDER).strip("|").split("|")
    return [part.replace(_PIPE_PLACEHOLDER, "|").strip() for part in parts]


def _walk(fields: list[ParsedField]) -> list[ParsedField]:
    out: list[ParsedField] = []
    for entry in fields:
        out.append(entry)
        out.extend(_walk(entry.properties))
    return out


@dataclass
class ParsedTable:
    heading: str
    line: int
    fields: list[ParsedField]
    missing_columns: list[str] = dataclass_field(default_factory=list)


@dataclass(frozen=True)
class StructuralTableMerge:
    """A manually transcribed destination for one supplementary table.

    A multi-table section is *not* safe to merge merely because its headings
    look related.  These entries exist only where the official manual names a
    containing object or array path.  They are deliberately keyed by table
    index as well as endpoint: a heading such as ``Parameters`` is repeated
    throughout several chapters and is not a reliable selector on its own.
    """

    table: int
    targets: tuple[tuple[str, ...], ...]
    products: tuple[str, ...] = ()


@dataclass(frozen=True)
class StructuralTableRequirements:
    """Requiredness stated once for a supplementary table and its exceptions."""

    default: Optional[str]
    overrides: tuple[tuple[str, Optional[str]], ...] = ()
    conditions: tuple[
        tuple[
            str,
            str,
            str,
            tuple[str | int | float | bool, ...],
        ],
        ...,
    ] = ()


# The paths below are transcriptions of the parameter headings and surrounding
# prose in docs/manual, recorded in docs/variant_table_survey.md §B (removed
# 2026-09-17; git history at fa1332b).  This is a
# closed allow-list, not a heuristic: any other extra table remains unmerged.
_STRUCTURAL_TABLE_SPLITS: dict[str, tuple[StructuralTableMerge, ...]] = {
    "/db/ACTL-M1": (
        StructuralTableMerge(1, (("TCELEM",),)),
        StructuralTableMerge(2, (("TCELEM", "CONVERGENCE"),)),
    ),
    "/db/BCCT": (
        StructuralTableMerge(1, ((),)),
        StructuralTableMerge(2, ((),)),
    ),
    # The first subtype table adds one record member. The chapter repeats
    # ANGLE in the later subtype tables, while /info declares it at record
    # root; this entry settles placement only and makes no discriminator claim.
    "/db/ELEM": (StructuralTableMerge(1, ((),)),),
    "/db/GRDP": (StructuralTableMerge(1, ((),)),),
    "/db/IEHC": (StructuralTableMerge(1, ((),), ("gen",)),),
    "/db/IMFM": (StructuralTableMerge(1, ((),)),),
    "/db/MCON": (
        StructuralTableMerge(1, (("ITEMS", "SLAVES"),)),
        StructuralTableMerge(2, (("ITEMS", "SLAVES"),)),
    ),
    "/db/MVCTch": (
        StructuralTableMerge(1, ((),)),
        StructuralTableMerge(2, (("FREQ",),)),
        StructuralTableMerge(3, (("BRIDGE1",),)),
        StructuralTableMerge(4, (("BRIDGE2",),)),
    ),
    "/db/POGD": (
        StructuralTableMerge(1, (("NONL_OPT",),)),
        StructuralTableMerge(2, (("PHOP_OPT",),)),
    ),
    "/db/RPSC": (
        StructuralTableMerge(1, (("SBAR_ITEMS",),)),
        StructuralTableMerge(2, (("MBAR_ITEMS",),)),
    ),
    # The chapter-24 counterpart of the chapter-26 `/DESIGN/.../REBR` entry
    # below, and registered for the same reason: one table headed
    # "`SHEAR_BAR_END` / `SHEAR_BAR_CEN` 객체 (공통 구조)" states the structure both
    # objects share, so its four rows belong to both. The section's third table
    # (index 2) is deliberately absent: its `(1)` row is the item's own `ID`
    # while its a/b/c rows are `ELEMS` members, so the table has two
    # destinations and appending its whole field list to either would be wrong.
    # It is resolved by hand in the contract against the section's JSON Schema.
    "/db/REBR": (
        StructuralTableMerge(1, (("Assign", "ITEMS", "SHEAR_BAR_END"), ("Assign", "ITEMS", "SHEAR_BAR_CEN"))),
    ),
    # The main table's rows 7-9 name the three device objects - "LRB Data
    # (SDIS_DEV_TYPE="LRB"일 때)" and so on - and each following table is headed
    # with the object it describes. The third heading reads "`SB` 객체" with a
    # parenthesis the parser drops, so it arrives titled like the second.
    # The prose above the second table says so outright: "`vPARTINFO`의 각
    # 파트에는 이 외에도 ... 아래 필드들이 있다". The table has no Required
    # column, so its rows stay unstated; the chapter itself calls their roles
    # an inference.
    "/db/CSCS": (StructuralTableMerge(1, (("vPARTINFO",),)),),
    "/db/SDIS": (
        StructuralTableMerge(1, (("LRB",),)),
        StructuralTableMerge(2, (("NRB",),)),
        StructuralTableMerge(3, (("SB",),)),
    ),
    "/db/SBDO": (
        StructuralTableMerge(1, ((),), ("civil",)),
        StructuralTableMerge(2, ((),), ("gen",)),
    ),
    # These headings group coexisting analysis controls; they do not state a
    # complete discriminator for the whole table. The manual supplies the
    # rows and GET /info/db/STCT places every member at record root, so merge
    # the tables there without inventing a branch. Tables 5 and 6 remain out:
    # their conditional/multi-key notation needs separate parser work.
    # Table 1 is the erection-load block: vEREC and its numbered item rows,
    # then bSDLE/vSDLE. /info declares all three at record root on both
    # products; "JP 버전 전용" names a product edition, not a payload branch.
    "/db/STCT": (
        StructuralTableMerge(1, ((),)),
        StructuralTableMerge(2, ((),)),
        StructuralTableMerge(3, ((),)),
        StructuralTableMerge(4, ((),)),
    ),
    # The final table is explicitly marked GEN NX only, and /info places both
    # members at record root. It is a product qualification, not a payload
    # discriminator, so retain that scope on the fields without inventing a
    # branch between bNDP and NDP.
    # Table 3 is the accidental-eccentricity block and table 4 the
    # non-dissipative one; both are headed GEN NX only and /info places every
    # member at record root.
    "/db/SPLC": (
        StructuralTableMerge(3, ((),), ("gen",)),
        StructuralTableMerge(4, ((),), ("gen",)),
    ),
    # Each detail table is headed with its own destination -
    # `TYPE_OF_DISPLAY.CONTOUR` and so on - and repeats the parent row table 1
    # already lists under TYPE_OF_DISPLAY. The objects are independently
    # optional, so no discriminator is involved.
    "/view/RESULTGRAPHIC": tuple(
        StructuralTableMerge(index, (("TYPE_OF_DISPLAY",),)) for index in range(1, 11)
    ),
    # Both headings name their destination object. LOAD_STEPS keeps the
    # difference between descriptions that explicitly say "required" and
    # descriptions that only say a field is used under a selector; ADVANCED's
    # heading states table-wide optionality and its first row alone says
    # Required.
    "/db/NLCT-M1": (
        StructuralTableMerge(1, (("LOAD_STEPS",),)),
        StructuralTableMerge(3, (("ADVANCED",),)),
    ),
    # Tables 1-4 each name one destination object in the heading and carry rows
    # that parse to it directly, including TIME_DEP_CONTROL's dotted
    # `CREEP_SHRINKAGE.*` keys and the `"bTTLE_ES"` / `"iTTLE_ES"` cell, both of
    # which the parser already resolves. Table 5 (NONL_CONTROL) and table 6
    # (나머지 객체) are deliberately absent: table 5 states `ADVANCED`'s whole
    # subtree as prose inside one cell and keys three sibling objects
    # `"DISP"/"LOAD"/"WORK"`, and table 6 puts each row's parent in an `Object`
    # column this parser drops, so its twelve rows have six different
    # destinations and no single target could hold them. Both are hand-resolved
    # in the contract against the section's Request Body example.
    "/db/STCT-M1": (
        StructuralTableMerge(1, (("ANAL_TYPE",),)),
        StructuralTableMerge(2, (("RESTART_CS_ANAL",),)),
        StructuralTableMerge(3, (("ERECTION_LOAD",),)),
        StructuralTableMerge(4, (("TIME_DEP_CONTROL",),)),
    ),
    # The manual names BOUNDARY_NL_ANAL in the table heading and types its two
    # members. /info supplies the otherwise unstated nesting beneath
    # NONL_CTRL_PARAM.ITER_CTRL; _STRUCTURAL_CONTAINER_PATHS creates that named
    # container before these rows are appended.
    "/db/THIS-M1": (
        StructuralTableMerge(
            8,
            (("NONL_CTRL_PARAM", "ITER_CTRL", "BOUNDARY_NL_ANAL"),),
        ),
    ),
    # Each heading names the object it belongs to outright - "INCREMENT_STEP
    # 서브 파라미터", "HINGE_OPT 서브 파라미터" - and both tables are flat, so the
    # rows land where the heading says. The section's third sub-table,
    # "ITER_PARAM 서브 파라미터" (index 2), is deliberately absent: its Key column
    # states paths rather than property names (`DISP` -> `{OPT_USE, VALUE}`) and
    # lists LINE_SEARCH's five children as sibling rows, so merging it as parsed
    # would invent a field named '{OPT_USE, VALUE}' and flatten two levels. That
    # one is recorded as a manual defect and resolved by hand in the contract.
    "/db/THGC-M1": (
        StructuralTableMerge(1, (("INCREMENT_STEP",),)),
        StructuralTableMerge(3, (("HINGE_OPT",),)),
    ),
    "/db/WVLD": (
        StructuralTableMerge(1, (("COEF",),)),
        StructuralTableMerge(2, (("COEF", "COEF_S"), ("COEF", "COEF_R"), ("COEF", "OVER_S"), ("COEF", "OVER_R"))),
        StructuralTableMerge(3, (("CHAR",),)),
        StructuralTableMerge(4, (("PROF",),)),
        StructuralTableMerge(5, (("PROF", "GRID_DATA"),)),
        StructuralTableMerge(6, ((),)),
        StructuralTableMerge(7, (("GROWTH",),)),
        StructuralTableMerge(8, (("USERGRID",), ("TRAJ",))),
    ),
    "/DESIGN/RC/KDS-41-20-2022/DCRM-WALL": (
        StructuralTableMerge(1, (("Assign", "ITEMS"),)),
    ),
    "/DESIGN/RC/KDS-41-20-2022/DCRE": (
        StructuralTableMerge(1, (("Assign", "BEAM"),)),
        StructuralTableMerge(2, (("Assign", "COLUMN"), ("Assign", "BRACE"))),
        StructuralTableMerge(3, (("Assign", "WALL"),)),
        StructuralTableMerge(4, (("Assign", "WALL", "MATERIAL_BY_DIAMETER_INPUT", "VERTICAL_END_REBAR"), ("Assign", "WALL", "MATERIAL_BY_DIAMETER_INPUT", "HORIZONTAL_REBAR"))),
        StructuralTableMerge(5, (("Assign", "WALL", "ADDITIONAL_WALL_DATA"),)),
    ),
    # Only the ELEMS table (index 2) is registered. The sector table (index 1)
    # is not mergeable as parsed: three of its rows key more than one property
    # at once - `"LAYER1"` / `"LAYER2"`, `"NAME"` / `"LEG"` / `"DIST"` and
    # `"NAME"` / `"NUM"` - and its two unnumbered rows state the members of
    # LAYER1/LAYER2 rather than of the sector. Merged as parsed it produced ten
    # flat siblings where the schema has a two-level tree. It is hand-resolved
    # in the contract, which follows the section's worked examples rather than
    # this table - on the section's own instruction. See MD-29.
    "/DESIGN/RC/KDS-41-20-2022/REBB": (
        StructuralTableMerge(2, (("Assign", "ITEMS", "ELEMS"),)),
    ),
    "/DESIGN/RC/KDS-41-20-2022/REBC": (
        StructuralTableMerge(1, (("Assign", "ITEMS", "MAIN_BAR"),)),
        StructuralTableMerge(2, (("Assign", "ITEMS", "SHEAR_BAR_END"), ("Assign", "ITEMS", "SHEAR_BAR_CEN"))),
        StructuralTableMerge(3, (("Assign", "ITEMS", "ELEMS"),)),
    ),
    "/DESIGN/RC/KDS-41-20-2022/REBR": (
        StructuralTableMerge(1, (("Assign", "ITEMS", "MAIN_BAR"),)),
        StructuralTableMerge(2, (("Assign", "ITEMS", "SHEAR_BAR_END"), ("Assign", "ITEMS", "SHEAR_BAR_CEN"))),
        StructuralTableMerge(3, (("Assign", "ITEMS", "ELEMS"),)),
    ),
    "/view/DISPLAY": tuple(StructuralTableMerge(index, (("Argument",),)) for index in range(1, 7)),
}


_STRUCTURAL_TABLE_REQUIREMENTS: dict[
    tuple[str, int], StructuralTableRequirements
] = {
    ("/db/NLCT-M1", 3): StructuralTableRequirements(
        "optional",
        (("OPT_USE_DEFAULT", "required"),),
    ),
    ("/db/NLCT-M1", 1): StructuralTableRequirements(
        None,
        (
            ("STEP_MODE", "required"),
            ("NUMBER_STEPS", "conditional"),
            ("OUTPUT", "conditional"),
            ("MAX_DISP", "conditional"),
        ),
        (
            ("NUMBER_STEPS", 'STEP_MODE="AUTO"일 때 필수', "STEP_MODE", ("AUTO",)),
            ("OUTPUT", 'STEP_MODE="AUTO"일 때 필수', "STEP_MODE", ("AUTO",)),
            ("MANUAL_STEPS", 'STEP_MODE="MANUAL"일 때', "STEP_MODE", ("MANUAL",)),
            ("MIN_ARC_RATIO", 'ITER_METHOD="ARC"', "ITER_METHOD", ("ARC",)),
            ("MAX_ARC_RATIO", 'ITER_METHOD="ARC"', "ITER_METHOD", ("ARC",)),
            ("MAX_ARC_INCREMENTS", 'ITER_METHOD="ARC"', "ITER_METHOD", ("ARC",)),
            ("MASTER_NODE", 'ITER_METHOD="DISP"', "ITER_METHOD", ("DISP",)),
            ("MAX_DISP", 'ITER_METHOD="DISP"', "ITER_METHOD", ("DISP",)),
            ("DIRECTION", 'ITER_METHOD="DISP"', "ITER_METHOD", ("DISP",)),
            ("REF_NODE", 'ITER_METHOD="DISP"', "ITER_METHOD", ("DISP",)),
        ),
    ),
}


_STRUCTURAL_ROOT_MOVES: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    # The design endpoints use an ID-keyed Assign map.  The parameter tables
    # describe the value under an Assign key, not sibling root keys.
    "/DESIGN/RC/KDS-41-20-2022/DCRM-WALL": (("ITEMS", ("Assign",)),),
    "/DESIGN/RC/KDS-41-20-2022/DCRE": (
        ("BEAM", ("Assign",)),
        ("COLUMN", ("Assign",)),
        ("BRACE", ("Assign",)),
        ("WALL", ("Assign",)),
    ),
    # Chapter 24 uses the same ID-keyed Assign map for its rebar endpoints, and
    # numbers `"Assign"` and `"ITEMS"` both `1`, so they parse as siblings. The
    # section's JSON Schema places ITEMS inside the Assign value.
    "/db/REBR": (("ITEMS", ("Assign",)),),
    "/DESIGN/RC/KDS-41-20-2022/REBB": (("ITEMS", ("Assign",)),),
    "/DESIGN/RC/KDS-41-20-2022/REBC": (("ITEMS", ("Assign",)),),
    "/DESIGN/RC/KDS-41-20-2022/REBR": (("ITEMS", ("Assign",)),),
    # The table writes these child paths relative to DIVIDE. Its parent rows,
    # JSON Schema and Request Examples all place both objects inside DIVIDE.
    "/ope/DIVIDEELEM": (
        ("OPTION", ("DIVIDE",)),
        ("MERGE_DUPLICATE_NODES", ("DIVIDE",)),
    ),
    # Two objects whose own rows (1-5 and 3-2) name the full path while their
    # member rows drop the parent - MESHER.INCLUDE_INTERIOR_NODES followed by
    # INCLUDE_INTERIOR_NODES.OPT_CHECK, and PROPERTY.ELEMENT_SUB_TYPE followed
    # by ELEMENT_SUB_TYPE.TYPE. The JSON Schema and both Request Examples nest
    # them. Same shape as /ope/GUSTFACTOR below.
    "/ope/AUTOMESH": (
        ("INCLUDE_INTERIOR_NODES", ("MESHER",)),
        ("ELEMENT_SUB_TYPE", ("PROPERTY",)),
    ),
    # The child rows shorten FLEXIBLE_PARAM.TOPOGRAPHIC_EFFECT.* to
    # TOPOGRAPHIC_EFFECT.*; the parent row, schema and examples retain the
    # enclosing FLEXIBLE_PARAM object.
    "/ope/GUSTFACTOR": (("TOPOGRAPHIC_EFFECT", ("FLEXIBLE_PARAM",)),),
}


class ManualTypeCorrection(NamedTuple):
    """One Value Type the manual's table gets wrong, and what says so."""

    type: str
    items: Optional[dict]
    manual_says: str
    actual: str


# A Specifications table's Value Type that the same section's JSON Schema
# contradicts. MD-11 in docs/manual_defects_register.md lists all nine of
# them; this is the closed set whose resolution has been checked against a
# third statement - the section's own Request Example, and the SDK that
# already sends that shape - and it is a transcription of that check, not a
# rule that prefers one rendering over the other.
#
# Width disagreements are deliberately absent. Integer against Number changes
# nothing a caller may send, and picking a side would narrow a field on no
# evidence; those keep the review note instead.
_MANUAL_TYPE_CORRECTIONS: dict[str, dict[tuple[str, ...], ManualTypeCorrection]] = {
    "/db/MATL": {
        ("PARAM",): ManualTypeCorrection(
            type="array",
            items={"type": "object"},
            manual_says="The Specifications table types `PARAM` as `Object`.",
            actual=(
                "The same section's JSON Schema declares `\"PARAM\": {\"description\": "
                "\"Material Data\", \"type\": \"array\"}`, and every Request Example in the "
                "section sends `\"PARAM\": [{...}]` - one entry per material parameter "
                "set. The Python SDK has typed it `List[MaterialParam]` since the "
                "endpoint was added."
            ),
        ),
    },
    "/db/SBDO": {
        ("AXIS_VECTOR",): ManualTypeCorrection(
            type="array",
            items={"type": "number"},
            manual_says="The Specifications table types `AXIS_VECTOR` as `Number` with default 0.",
            actual=(
                "The same section's JSON Schema declares `\"AXIS_VECTOR\": {\"description\": "
                "\"Axis Vector\", \"type\": \"array\", \"items\": {\"type\": \"number\"}}`, and the "
                "section's own Request Example sends `\"AXIS_VECTOR\": [0, 0, 0, 0, 0, 0]`. "
                "The Python SDK's payload has always typed it `List[float]`; only the "
                "contract, and the npm payload generated from it, followed the table."
            ),
        ),
    },
}

class ManualKeyCorrection(NamedTuple):
    """One wire name the manual's table gets wrong, and what says so."""

    key: str
    manual_says: str
    actual: str
    evidence: str


# A Key cell naming a property the server does not have. Unlike a wrong Value
# Type, nothing inside the section can settle this - a name is not derivable
# from a schema that never mentions it - so every entry here rests on live
# `/info` introspection, which is a permitted source and is captured verbatim
# in `schema/info-schemas.json`.
_MANUAL_KEY_CORRECTIONS: dict[str, dict[tuple[str, ...], ManualKeyCorrection]] = {
    "/db/TDME": {
        ("SCALE",): ManualKeyCorrection(
            key="aDATA",
            manual_says=(
                "The Specifications table gives the key `\"SCALE\"` to two different "
                "rows: `5 Scale Factor` (Number) and `6 Function Data (Array of "
                "{TIME, COMP, TENS, ELAST})` (Array[Object]). The vendored chapter "
                "flags the duplicate in its own callout and transcribes both, because "
                "no example in the section sends either row."
            ),
            actual=(
                "`GET /info/db/TDME` lists `\"SCALE\"` as a `number` described "
                "\"Scale Factor\" and a separate `\"aDATA\"` array whose items are "
                "`{TIME, COMP, TENS, ELAST}`. Row 5 is correct; row 6's key is the "
                "typo, and the array is `aDATA`. Civil NX and Gen NX return identical "
                "schemas."
            ),
            evidence=(
                "docs/live_verification_notes.md, \"an /info sweep of the 18 endpoints "
                "no contract could reach\" (2026-09-02), captured verbatim in "
                "schema/info-schemas.json. Registered as MD-13."
            ),
        ),
    },
}


class ManualRequirednessCorrection(NamedTuple):
    """One Required or Default cell a live measurement disproves.

    The third correction kind, and the one that needed a product rather than a
    document. A wrong Value Type is settled by the same section's JSON Schema
    and a wrong Key by `/info`; a wrong *requiredness* is settled by nothing
    but sending the field and not sending it and watching what the server
    does. So every entry here cites a run in
    docs/live_verification_notes.md with the error string it produced.

    `describes` names which cell is wrong, because these two go together more
    often than not: a row that marks a field Optional and names a default is
    making two claims, and /db/PRES gets both of them wrong at once.
    """

    describes: str
    manual_says: str
    actual: str
    evidence: str


# Measured contradictions of a Required or Default cell. Deliberately small:
# a row belongs here only after someone has watched the product accept and
# refuse the field, not after reading a second document about it.
_MANUAL_REQUIREDNESS_CORRECTIONS: dict[str, dict[str, tuple[ManualRequirednessCorrection, ...]]] = {
    "/db/SPFC": {
        "CALC_OPT": (
            ManualRequirednessCorrection(
                describes="requiredness",
                manual_says=(
                    "The KDS(41-17-00:2019) parameter table marks `CALC_OPT` "
                    "`Create Only`, which says the server reads it on POST and "
                    "ignores it on PUT."
                ),
                actual=(
                    "It is honoured on PUT. Sending `CALC_OPT: true` on a PUT "
                    "rebuilt a spectrum that had been hand-set to a flat two-point "
                    "curve into the 103-point curve the code parameters generate; "
                    "sending `false`, or omitting it, left the stale curve in place "
                    "while accepting new parameters. The cell is true of the "
                    "manual's other `Create Only`, /db/SECT's, and not of this one."
                ),
                evidence=(
                    "docs/live_verification_notes.md, \"what the manual's 'Create "
                    "Only' actually means\" (2026-09-03), measured on Gen NX against "
                    "an empty document. Registered as MD-15."
                ),
            ),
            ManualRequirednessCorrection(
                describes="behaviour",
                manual_says=(
                    "The section's KDS(41-17-00:2019) Request Body example omits "
                    "`CALC_OPT` and supplies no `aFUNC`, presenting it as a working "
                    "request."
                ),
                actual=(
                    "That exact body is refused: `[Error] Spectrum Function Data "
                    "(Name:...) contains errors.(Item:Spectrum Data)`. A "
                    "design-spectrum function needs either `CALC_OPT: true`, so the "
                    "server builds the curve from `STR`/`OPT`/`VAL`, or an explicit "
                    "`aFUNC`. The documented default `false` is correct; it is the "
                    "example that cannot run."
                ),
                evidence=(
                    "docs/live_verification_notes.md, \"what the manual's 'Create "
                    "Only' actually means\" (2026-09-03). Registered as MD-15."
                ),
            ),
        ),
    },
    "/db/PRES": {
        "DIRECTION": (
            ManualRequirednessCorrection(
                describes="requiredness",
                manual_says="The Specifications table marks `DIRECTION` `Optional`.",
                actual=(
                    "On the commonest pressure load there is - a 4-node PLATE with "
                    "`FACE_EDGE_TYPE: \"FACE\"` - omitting it is refused with "
                    "`[Error] Errors detected in Pressure Loads Data.(Item:Load "
                    "Direction)`. The official article's own availability matrix "
                    "already implied it: Normal is `-` for PLATE + FACE while the "
                    "local and global axes are `O`, so the matrix and the product "
                    "agree and only this row is out of step."
                ),
                evidence=(
                    "docs/live_verification_notes.md, \"/db/PRES: B-4 measured, with "
                    "the error string\" (2026-09-03), against the plate in "
                    "live_crud_check.py's own seed. Vendor report B-4."
                ),
            ),
            ManualRequirednessCorrection(
                describes="default",
                manual_says="The same row gives `DIRECTION` the default `\"NORMAL\"`.",
                actual=(
                    "`\"NORMAL\"` is the one value that combination refuses, with the "
                    "same error as omitting the field. `\"LZ\"` and `\"GZ\"` are stored. "
                    "So both halves of the row are wrong for PLATE + FACE, not just "
                    "the Required half."
                ),
                evidence=(
                    "docs/live_verification_notes.md, \"/db/PRES: B-4 measured, with "
                    "the error string\" (2026-09-03). Vendor report B-4."
                ),
            ),
        ),
    },
}


def _corrected_key(endpoint: str, key: str, declared: Optional[str]) -> str:
    """A Key cell's reviewed wire name, applied while the row is still a row.

    This has to run before the parser's duplicate-key suppression, which is
    what makes the defect invisible: /db/TDME gives `"SCALE"` to a Number row
    and to an Array[Object] row, both at the top level, so the second row's
    identity collides with the first and it is dropped without a trace. Its
    four documented children then attach to the scalar that remains, and the
    section reads as one field that is a number and also has members.

    Only the row whose own Value Type marks it the container is renamed, so a
    table that repeats a name for some other reason is left alone.
    """

    corrections = _MANUAL_KEY_CORRECTIONS.get(endpoint)
    if not corrections:
        return key
    correction = corrections.get((key,))
    if correction is None or not declared:
        return key
    lowered = declared.lower()
    if "array" in lowered or "object" in lowered:
        return correction.key
    return key


_MANUAL_TYPE_CORRECTION_EVIDENCE = (
    "docs/manual_defects_register.md MD-11, found by comparing every parameter "
    "table's Value Type against the type its own section's JSON Schema declares - "
    "nine disagreements in the whole manual, of which this is one of the two that "
    "change the shape of the value rather than its numeric width."
)


def _apply_manual_type_corrections(endpoint: str, fields: list[ParsedField]) -> None:
    """Write the reviewed resolution of a self-contradicting Value Type.

    The extractor refuses to choose between a table and a schema that disagree,
    because choosing takes the section's Request Example and the SDK that
    already sends the shape - neither of which it reads. This applies the
    choice a person made, on the assembled request, and clears the note that
    said nobody had made one. `render_draft` emits the same entries under
    `manualDefects`, so the contract carries the reason and a manual re-sync
    cannot quietly put the table's claim back.
    """

    corrections = _MANUAL_TYPE_CORRECTIONS.get(endpoint)
    if not corrections:
        return

    def visit(items: list[ParsedField], prefix: tuple[str, ...] = ()) -> None:
        for field in items:
            path = prefix + (field.key,)
            correction = corrections.get(path)
            if correction is not None:
                field.type = correction.type
                field.items = dict(correction.items) if correction.items else None
                field.notes = [
                    note
                    for note in field.notes
                    if "JSON Schema types it" not in note
                ]
            visit(field.properties, path)

    visit(fields)


_REVIEWED_FIELD_CONDITIONS: dict[
    str,
    dict[tuple[str, ...], tuple[str, tuple[str, tuple[str | int | float | bool, ...]] | None]],
] = {
    "/db/STCT": {
        ("bTRUSS",): ("when bCONV true", ("bCONV", (True,))),
        ("bBEAM",): ("when bCONV true", ("bCONV", (True,))),
        ("GROUP",): ('ITD="GROUP"일 때', ("ITD", ("GROUP",))),
        ("LFFGR",): ("bLFFC=true일 때", ("bLFFC", (True,))),
    },
    "/ope/GUSTFACTOR": {
        ("RIGID_PARAM",): ("STRUCTURE_TYPE = RIGID인 경우", ("STRUCTURE_TYPE", ("RIGID",))),
        ("FLEXIBLE_PARAM",): (
            "STRUCTURE_TYPE = FLEXIBLE인 경우",
            ("STRUCTURE_TYPE", ("FLEXIBLE",)),
        ),
    },
}


_REVIEWED_ADDITIONAL_FIELD_CONDITIONS: dict[
    str,
    dict[tuple[str, ...], tuple[str, tuple[str, tuple[str | int | float | bool, ...]]]],
] = {
    "/db/NSPR": {
        ("ITEMS", "DV"): ("DIR=6일 때", ("DIR", (6,))),
    },
    "/db/IMPF": {
        ("ITEMS", "PARTS"): (
            "Beam/Plate만 — ⚠️ Truss 예제에는 PARTS 필드 자체가 없음, 2026-08-25 확인",
            ("ELEMTYPE", ("BEAM", "PLATE")),
        ),
    },
    # /db/SPLC's Mass & Stiffness table states its own gates in a 비고 column
    # the parser does not read ("iCOEF=2 시"), and in the Description for the
    # two direct coefficients ("(iCOEF=1)"). iCOEF's own "Required" is in the
    # same column and is carried by the contract.
    "/db/SPLC": {
        ("MASSC",): ("iCOEF=1", ("iCOEF", (1,))),
        ("STIFFC",): ("iCOEF=1", ("iCOEF", (1,))),
        ("iCALC",): ("iCOEF=2 시", ("iCOEF", (2,))),
        ("FP1",): ("iCOEF=2 시", ("iCOEF", (2,))),
        ("FP2",): ("iCOEF=2 시", ("iCOEF", (2,))),
        ("DR1",): ("iCOEF=2 시", ("iCOEF", (2,))),
        ("DR2",): ("iCOEF=2 시", ("iCOEF", (2,))),
    },
    # /db/THIK's first table is not the whole record: it is headed
    # "Specifications — Value (`"TYPE": "VALUE"`)", and the Stiffened DB
    # example sends none of its rows. Read as the base, it required T_IN and
    # T_OUT of every stiffened plate. T_OUT's own row adds "(when "bINOUT" is
    # true)".
    "/db/THIK": {
        ("bINOUT",): ('TYPE="VALUE"', ("TYPE", ("VALUE",))),
        ("T_IN",): ('TYPE="VALUE"', ("TYPE", ("VALUE",))),
        ("T_OUT",): [
            ('TYPE="VALUE"', ("TYPE", ("VALUE",))),
            ('when "bINOUT" is true', ("bINOUT", (True,))),
        ],
        ("OFFSET",): ('TYPE="VALUE"', ("TYPE", ("VALUE",))),
        ("O_VALUE",): ('TYPE="VALUE"', ("TYPE", ("VALUE",))),
    },
}


def _apply_reviewed_field_conditions(endpoint: str, fields: list[ParsedField]) -> None:
    """Apply only conditions written elsewhere in the same manual section."""

    unresolved = "the manual marks this conditional but does not state the condition"
    for path, (condition, structured) in _REVIEWED_FIELD_CONDITIONS.get(endpoint, {}).items():
        field = _field_at_path(fields, path)
        if field is None:
            continue
        unresolved_condition = field.condition in {None, "조건부"} or unresolved in field.notes
        if not unresolved_condition:
            continue
        field.condition = condition
        if structured is not None:
            field.applies_when = [structured]
        if unresolved in field.notes:
            field.notes.remove(unresolved)
        field.notes.append(
            "the condition is stated elsewhere in the same section and retained without "
            "inventing a stricter selector"
        )


def _apply_reviewed_additional_field_conditions(endpoint: str, fields: list[ParsedField]) -> None:
    """Append a second manual gate to fields already gated by their table."""

    for path, gates in _REVIEWED_ADDITIONAL_FIELD_CONDITIONS.get(endpoint, {}).items():
        field = _field_at_path(fields, path)
        if field is None:
            continue
        for condition, structured in gates if isinstance(gates, list) else [gates]:
            if condition not in (field.condition or ""):
                field.condition = f"{field.condition}; {condition}" if field.condition else condition
            if structured not in field.applies_when:
                field.applies_when.append(structured)


_STRUCTURAL_CONTAINERS: dict[str, tuple[str, ...]] = {
    # These names are headings in the manual's supplementary tables; the
    # table does not repeat a separate parent row in the base table.
    "/db/WVLD": ("COEF", "CHAR", "PROF"),
}


# Containers named by a manual table heading whose full nesting is supplied by
# the committed /info baseline. Unlike _STRUCTURAL_CONTAINERS these may be
# nested. The leaf has no row of its own, so its requiredness and default stay
# unstated; only the table's child rows inherit the manual's claims.
_STRUCTURAL_CONTAINER_PATHS: dict[str, tuple[tuple[str, ...], ...]] = {
    "/db/THIS-M1": (("NONL_CTRL_PARAM", "ITER_CTRL", "BOUNDARY_NL_ANAL"),),
}


def _manual_container(key: str, *, condition: Optional[str] = None) -> ParsedField:
    """Create a container the manual names in a heading rather than a row."""

    return ParsedField(
        key=key,
        description="",
        type="object",
        items=None,
        requirement="conditional" if condition else "optional",
        documented_default=None,
        condition=condition,
    )


def _rchk_structural_fields(section: "Section") -> tuple[list[ParsedField], list[StructuralTableMerge]]:
    """Transcribe the two named BEAM/COLM objects in the RCHK manual section."""

    if len(section.tables) != 5:
        return copy.deepcopy(section.tables[0].fields), []

    def keyed(table: ParsedTable) -> dict[str, ParsedField]:
        return {field.key: copy.deepcopy(field) for field in _walk(table.fields)}

    beam_rows, column_rows, layer_rows, position_rows = (keyed(table) for table in section.tables[1:])
    try:
        beam_main = beam_rows["vMAIN"]
        beam_main.properties = [beam_rows[key] for key in ("SECTOR", "POS_TOP_LAYERS", "POS_BOT_LAYERS")]
        beam_sub = beam_rows["vSUB_BAR"]
        beam_sub.properties = [beam_rows[key] for key in (
            "SECTOR", "dSUB_BARNUM", "SUB_BARNAME", "dSUB_BARDIST", "dSUB_BARANGLE",
            "bTORSIONAL_BAR", "sTRTORBARNA", "dTORBAR_SPACING", "bBUNDLEDBAR",
            "dBUNDLEDBARNUM", "LONGIBARNA", "dLONGIBARNUM",
        )]
        col_layer = column_rows["vLAYER"]
        col_layer.properties = [column_rows[key] for key in ("INDEX", "dDc", "vPOSITION")]
        col_sub = column_rows["SUB_BAR"]
        col_sub.properties = [column_rows[key] for key in (
            "SUBBAR_NAME", "SUBBAR_DIST", "SUBBAR_NUM", "SUBBAR_NAME_Y", "SUBBAR_NAME_Z",
            "SUBBAR_NUM_Y", "SUBBAR_NUM_Z",
        )]
        layer = list(layer_rows.values())
        position = list(position_rows.values())
    except KeyError:
        return copy.deepcopy(section.tables[0].fields), []

    beam = _manual_container("BEAM", condition='MEMBTYPE="BEAM"')
    beam.properties = [beam_main, beam_sub]
    column = _manual_container("COLM", condition='MEMBTYPE="COLUMN"')
    column.properties = [col_layer, col_sub]
    beam_main.properties[1].properties = copy.deepcopy(layer)
    beam_main.properties[2].properties = copy.deepcopy(layer)
    col_layer.properties[2].properties = position
    return copy.deepcopy(section.tables[0].fields) + [beam, column], [
        StructuralTableMerge(index, (("BEAM",) if index in {1, 3} else ("COLM",),))
        for index in range(1, 5)
    ]


def _display_structural_fields(section: "Section") -> tuple[list[ParsedField], list[StructuralTableMerge]]:
    """DISPLAY's seven Argument groups are additive, never a one-of choice."""

    argument = _manual_container("Argument")
    for table in section.tables:
        if not _append_fields(argument.properties, copy.deepcopy(table.fields)):
            return copy.deepcopy(section.tables[0].fields), []
    return [argument], [StructuralTableMerge(index, (("Argument",),)) for index in range(len(section.tables))]


@dataclass(frozen=True)
class ParsedVariant:
    """One manual table selected by an explicitly documented discriminator.

    ``conditions`` preserves every literal selector the manual states for this
    one table. A condition normally has one value and renders as ``equals``;
    a heading such as ``FLOOR_DIST_TYPE = 1 or 2`` has several and renders as
    ``in``. A heading can name independent gates too, for example
    ``INPUT=2D, CURVE="SPLINE"``. Both forms are transcriptions - a value the
    manual does not write down never reaches this tuple.
    """

    conditions: tuple[tuple[str, tuple[str | int | float | bool, ...]], ...]
    table: ParsedTable

    @property
    def field(self) -> str:
        """The one selector field, retained for single-condition callers."""
        if len(self.conditions) != 1:
            raise ValueError("variant has several conditions; use .conditions")
        return self.conditions[0][0]

    @property
    def values(self) -> tuple[str | int | float | bool, ...]:
        """The one selector's values, retained for single-condition callers."""
        if len(self.conditions) != 1:
            raise ValueError("variant has several conditions; use .conditions")
        return self.conditions[0][1]

    @property
    def equals(self) -> str | int | float | bool:
        """The single documented value, for the common one-value case."""
        if len(self.values) != 1:
            raise ValueError(f"{self.field} names {len(self.values)} values; use .values")
        return self.values[0]


_VARIANT_CONDITION = re.compile(
    r'(?P<field>"?[A-Za-z_][A-Za-z0-9_.]*"?)\s*(?:==|=|:)\s*'
    r'(?:"(?P<string>[^"]+)"|(?P<numeric>-?\d+(?:\.\d+)?)(?![A-Za-z0-9_.-])|'
    r'(?P<boolean>true|false)(?![A-Za-z0-9_.-])|(?P<bare>[A-Za-z0-9][A-Za-z0-9_.-]*))',
    re.IGNORECASE,
)
# One table, several documented values of the same field: the manual writes
# ``FLOOR_DIST_TYPE = 1 or 2`` and ``LOAD_MODEL=2/3``. Only the alternatives
# trailing a matched ``FIELD = VALUE`` count - a bare number elsewhere in a
# heading is prose, not a second value.
_VARIANT_ALTERNATIVE = re.compile(
    # `.match(text, position)` already anchors here; Python's re has no \G.
    r'\s*(?:or|,|/)\s*(?!"?[A-Za-z_][A-Za-z0-9_.]*"?\s*(?:==|=|:))'
    r'(?:"(?P<string>[^"]+)"|(?P<numeric>-?\d+(?:\.\d+)?)(?![A-Za-z0-9_.-])|'
    r'(?P<boolean>true|false)(?![A-Za-z0-9_.-]))',
    re.IGNORECASE,
)


def _condition_value(
    string: str | None, numeric: str | None, boolean: str | None, bare: str | None
) -> str | int | float | bool:
    """One matched literal, kept in the type the wire uses."""
    if string:
        return string
    if numeric:
        number = float(numeric)
        return int(number) if number.is_integer() else number
    if boolean:
        return boolean.lower() == "true"
    assert bare is not None
    return bare


def _variant_key(conditions: list[dict]) -> tuple[str | None, tuple]:
    """Identify a declared variant by its single documented discriminator.

    The schema allows several ANDed conditions, but a manual set the extractor
    can transcribe is selected by one field; a hand-written contract using more
    simply will not match a parsed one, which is the honest outcome.
    """
    if len(conditions) != 1:
        return None, ()
    condition = conditions[0]
    values = tuple(condition["in"]) if "in" in condition else (condition.get("equals"),)
    return condition.get("path"), values


def _values_label(values: tuple) -> str:
    return repr(values[0]) if len(values) == 1 else " or ".join(repr(value) for value in values)


def _variant_conditions(
    text: str,
) -> tuple[tuple[str, tuple[str | int | float | bool, ...]], ...] | None:
    """Read the literal discriminator condition without inferring a value.

    Conditions occur both in markdown headings (``TYPE = "FIRST"``) and in
    blank-key divider rows inside a parameter table
    (``OPT_AUTO_OPTIMIZE=false``). The manuals also use quoted keys inside
    backticks, colon notation, and bare string literals such as ``INPUT=2D``.
    Boolean branches are wire values too, not prose labels, so preserve them as
    booleans rather than strings.

    A heading may state several values for the *same* table - the manual writes
    ``FLOOR_DIST_TYPE = 1 or 2`` and ``LOAD_MODEL=2/3``. Those are returned
    together and become an ``in`` condition. Two *different* fields in one
    heading are independent gates, so retain them as an AND condition rather
    than picking one. Repeated mentions of a field form one explicit value
    list. This function never obtains a value from table order or prose.
    """

    matches = list(_VARIANT_CONDITION.finditer(text.replace("`", "")))
    if not matches:
        return None
    conditions: dict[str, list[str | int | float | bool]] = {}
    for match in matches:
        field = match.group("field").strip('"')
        values = conditions.setdefault(field, [])
        values.append(_condition_value(*match.group("string", "numeric", "boolean", "bare")))
        # Consume ``or 2`` / ``/3`` / ``, 4`` immediately following this match.
        position = match.end()
        while (extra := _VARIANT_ALTERNATIVE.match(text, position)) is not None:
            values.append(_condition_value(*extra.group("string", "numeric", "boolean"), None))
            position = extra.end()
    if any(len(set(values)) != len(values) for values in conditions.values()):
        return None
    return tuple((field, tuple(values)) for field, values in conditions.items())


def _variant_condition(text: str) -> tuple[str, tuple[str | int | float | bool, ...]] | None:
    """Return one condition for existing single-selector consumers.

    Field-description parsing deliberately remains narrower than table-heading
    parsing: a description with two equalities is ambiguous to its one field,
    while a table heading can document two ANDed variant gates.
    """
    conditions = _variant_conditions(text)
    return conditions[0] if conditions is not None and len(conditions) == 1 else None


def _explicit_variants(tables: list[ParsedTable]) -> list[ParsedVariant]:
    """Model each supplementary table that explicitly names its wire gates.

    A heading such as ``LINEAR only`` does not say which wire value selects the
    table, so it stays unmerged. A literal condition in a table's own heading
    is sufficient evidence for that one table, even when another table belongs
    to a different selector group. This avoids inferring a common discriminator
    from table order while allowing several independent optional groups.

    A heading can still name only half of the real gate. ``/db/ELEM`` heads
    five tables ``STYPE: 1`` through ``STYPE: 3`` under four different element
    types, so ``STYPE: 1`` heads a tension-only truss and a compression-only
    truss both; the discriminator is the pair with ``TYPE``, whose wire values
    the chapter puts in a footnoted code table rather than in the headings.
    Two headings claiming one value is therefore evidence that the heading is
    not the whole gate. Every table gated on a repeated field stays unmerged -
    a contract must never say that one value selects two different field sets.

    A gate must also name a field this section documents. `FIELD = VALUE` is a
    shape, and a chapter can produce it by accident: `/db/TDME` heads two
    tables with lists of code names, one of which is `INDIA(IRC:112-2011)`, and
    the colon inside that name reads as a discriminator `IRC` on the value
    `112-2011`. There is no `IRC` field anywhere in `/db/TDME`, and the real
    discriminator - `CODENAME` - is never written in the `FIELD = VALUE` form
    at all. Checking the field against the section is the same requirement the
    contract schema already states for `appliesWhen`, and it is what separates
    that accident from `Moving Load Optimization(bAUTO_OPTIMIZE=true)`, where
    the parentheses look identical and the field is real.
    """

    if len(tables) < 2:
        return []
    documented = {field.key for table in tables for field in _walk(table.fields)}
    candidates: list[ParsedVariant] = []
    for table in tables[1:]:
        conditions = _variant_conditions(table.heading)
        if conditions is None:
            continue
        if any(field.split(".")[0] not in documented for field, _ in conditions):
            continue
        candidates.append(ParsedVariant(conditions, table))
    repeated = Counter(candidate.conditions for candidate in candidates)
    ambiguous = {
        field
        for conditions, count in repeated.items()
        if count > 1
        for field, _ in conditions
    }
    return [
        candidate
        for candidate in candidates
        if not any(field in ambiguous for field, _ in candidate.conditions)
    ]
def _field_at_path(fields: list[ParsedField], path: tuple[str, ...]) -> Optional[ParsedField]:
    current = fields
    found: Optional[ParsedField] = None
    for part in path:
        found = next((field for field in current if field.key == part), None)
        if found is None:
            return None
        current = found.properties
    return found


def _append_fields(destination: list[ParsedField], additions: list[ParsedField]) -> bool:
    """Append a table's fields without silently replacing a documented key."""

    existing = {field.key: field for field in destination}
    for addition in additions:
        prior = existing.get(addition.key)
        if prior is None:
            destination.append(addition)
            existing[addition.key] = addition
            continue
        # Repeated NODE_KEY in MCON's two SLAVES layouts is the same field,
        # stated in both tables.  Preserve it once only when its documented
        # type and requirement agree; differing declarations remain blocked.
        if (
            prior.type,
            prior.requirement,
            prior.documented_default,
            prior.documented_default_note,
        ) != (
            addition.type,
            addition.requirement,
            addition.documented_default,
            addition.documented_default_note,
        ):
            return False
        _widen_repeated_condition(prior, addition)
        # A supplementary table headed with its own destination repeats the
        # parent row an earlier table already listed, then gives its members
        # (/view/RESULTGRAPHIC's `TYPE_OF_DISPLAY.CONTOUR` and nine more).
        # The repeat is the same field; its members are what the table adds.
        if addition.properties and not _append_fields(prior.properties, addition.properties):
            return False
    return True


def _widen_repeated_condition(prior: ParsedField, addition: ParsedField) -> None:
    """Let a field two branch tables both document apply under both values.

    `/db/MATL` lists `DEN` and `MASS` under `P_TYPE = 2` and again under
    `P_TYPE = 3`. Keeping only the table that got there first says an
    orthotropic material may not carry a density. `appliesWhen` entries are
    combined with AND, so two entries on the same path would be a
    contradiction rather than a widening: the values merge into the one `in`
    the schema has for exactly this.

    Only a repeat on the same single path widens. Two different selectors
    would mean the field applies under either, which `appliesWhen` cannot say,
    and a prior with no condition at all already applies everywhere.
    """

    if not prior.applies_when or not addition.applies_when:
        return
    if len(prior.applies_when) != 1 or len(addition.applies_when) != 1:
        return
    (prior_path, prior_values), (added_path, added_values) = prior.applies_when[0], addition.applies_when[0]
    if prior_path != added_path:
        return
    widened = prior_values + tuple(value for value in added_values if value not in prior_values)
    if widened == prior_values:
        return
    prior.applies_when[0] = (prior_path, widened)
    if addition.condition and addition.condition != prior.condition:
        prior.condition = f"{prior.condition}; {addition.condition}" if prior.condition else addition.condition


_SAME_OBJECT_SHAPE = re.compile(
    r"(?:구조는\s*(?P<korean>[A-Za-z][A-Za-z0-9_ -]*?)(?:와\s*)?동일|"
    r"same\s+structure\s+as\s+(?P<english>[A-Za-z][A-Za-z0-9_ -]*?)(?=[).,]|$))",
    re.IGNORECASE,
)


def _same_object_shape_reference(description: str) -> str | None:
    """Return the exact sibling object named as having the same structure.

    A table may document one object in full and say that a sibling's structure
    is identical. This is not a guessed shape: the sentence is the manual's
    direct statement. Normalize only spelling separators (``Part A`` to
    ``PART_A``) so it can be matched to the actual sibling key.
    """

    match = _SAME_OBJECT_SHAPE.search(description)
    if match is None:
        return None
    raw = match.group("korean") or match.group("english")
    if raw is None:
        return None
    return re.sub(r"[\s-]+", "_", raw.strip()).upper()


def _inherit_documented_object_shapes(fields: list[ParsedField]) -> None:
    """Clone an explicitly documented sibling object structure once.

    Only empty object siblings with a direct ``same structure`` statement may
    inherit. A source without parsed children leaves the target empty, rather
    than fabricating a shape from a name alone.
    """

    by_key = {field.key: field for field in fields}
    for target in fields:
        source_key = _same_object_shape_reference(target.description)
        source = by_key.get(source_key) if source_key else None
        if (
            source is None
            or source is target
            or source.type != "object"
            or target.type != "object"
            or not source.properties
            or target.properties
        ):
            continue
        target.properties = copy.deepcopy(source.properties)
        # Numbering notes identify how the source table drew its child path;
        # they would be false on an inherited sibling whose shape was stated
        # in prose rather than repeated as numbered rows.
        for child in _walk(target.properties):
            child.notes = [
                note for note in child.notes if not note.startswith("the manual nests this under ")
            ]


def _tag_products(fields: list[ParsedField], products: tuple[str, ...]) -> None:
    for field in fields:
        field.products = products
        _tag_products(field.properties, products)


def _apply_structural_table_requirements(
    endpoint: str,
    table_index: int,
    fields: list[ParsedField],
) -> None:
    """Apply requiredness that the manual states at table or row level.

    Tables registered here have no Required column. Their heading makes one
    exact claim for every row, while named row descriptions override it. This
    is deliberately a closed review map: a missing entry stays unstated.
    """

    claims = _STRUCTURAL_TABLE_REQUIREMENTS.get((endpoint, table_index))
    if claims is None:
        return
    overrides = dict(claims.overrides)
    for field in fields:
        field.requirement = overrides.get(field.key, claims.default)
    by_key = {field.key: field for field in fields}
    for key, condition, path, values in claims.conditions:
        field = by_key.get(key)
        if field is None:
            continue
        field.condition = condition
        field.applies_when = [(path, values)]

    if endpoint == "/db/NLCT-M1" and table_index == 1:
        # REF_NODE's two children are stated inline in its own Description
        # rather than as rows. Preserve exactly those type/required/default
        # claims; the prose does not state NODE's requiredness.
        ref_node = by_key.get("REF_NODE")
        if ref_node is not None:
            ref_node.properties = [
                ParsedField(
                    key="OPT_USE",
                    description="기준(상대) 절점 사용 여부",
                    type="boolean",
                    items=None,
                    requirement="required",
                    documented_default=None,
                ),
                ParsedField(
                    key="NODE",
                    description="기준(상대) 절점 ID",
                    type="integer",
                    items=None,
                    requirement=None,
                    documented_default=0,
                ),
            ]


_SCHEMA_TRANSPORT_WRAPPERS = frozenset({"Argument", "Assign"})


def _structural_fields(section: "Section") -> tuple[list[ParsedField], list[StructuralTableMerge]]:
    """Assemble one manual section's request, then let its schema fill the gaps.

    Placing the supplementary tables is what makes the schema addressable. A
    row in chapter 26's `WALL` table is at `Assign.WALL.HORIZONTAL_REBAR` only
    once that table has been merged; before that it is a root row named
    `HORIZONTAL_REBAR`, which the schema does not have and which collides with
    the `MATERIAL_BY_DIAMETER_INPUT` member of the same name. So the section's
    JSON Schema is read twice: once per table while parsing, for the tables
    that never get merged, and once here against the finished paths.

    It only ever fills what the tables left blank, so the second reading cannot
    overrule the first - it reaches the fields the first could not address.
    """

    fields, resolved = _merged_structural_fields(section)
    hints = section.schema_hints
    # `Assign` and `Argument` are message transport, and the endpoint token is
    # the response's own name. Schema paths start inside them, so the merged
    # tree has to be entered the same way before the two can be compared - but
    # only when the wrapper is the whole root, never when it sits beside real
    # payload members. Curated corrections are keyed the same way.
    roots = fields
    wrappers = _SCHEMA_TRANSPORT_WRAPPERS | {section.endpoint.rsplit("/", 1)[-1]}
    while len(roots) == 1 and roots[0].key in wrappers and roots[0].properties:
        roots = roots[0].properties
    if hints:
        _apply_schema_hints_to_fields(roots, hints)
        _drop_sampled_enums([ParsedTable(heading="", line=0, fields=fields)])
    _apply_manual_type_corrections(section.endpoint, roots)
    _apply_reviewed_field_conditions(section.endpoint, roots)
    return fields, resolved


def _merged_structural_fields(section: "Section") -> tuple[list[ParsedField], list[StructuralTableMerge]]:
    """Apply only pre-audited structural table paths for one manual section.

    The return value lists exactly the table resolutions that succeeded.  A
    missing parent, duplicate key, or unlisted table is intentionally left out;
    render_draft will retain it under ``unmergedTables`` and promotion will
    continue to refuse it.
    """

    if not section.tables:
        return [], []
    if section.endpoint == "/db/RCHK":
        return _rchk_structural_fields(section)
    if section.endpoint == "/view/DISPLAY":
        return _display_structural_fields(section)
    fields = copy.deepcopy(section.tables[0].fields)

    for key in _STRUCTURAL_CONTAINERS.get(section.endpoint, ()):
        if _field_at_path(fields, (key,)) is None:
            fields.append(_manual_container(key))

    for path in _STRUCTURAL_CONTAINER_PATHS.get(section.endpoint, ()):
        if not path or _field_at_path(fields, path) is not None:
            continue
        parent = _field_at_path(fields, path[:-1])
        if parent is None:
            continue
        container = _manual_container(path[-1])
        container.requirement = None
        container.notes.append(
            "the manual names this container in the table heading and the nesting is "
            "declared by /info; no source states its requiredness or default"
        )
        parent.properties.append(container)

    for key, parent_path in _STRUCTURAL_ROOT_MOVES.get(section.endpoint, ()):
        source = next((field for field in fields if field.key == key), None)
        parent = _field_at_path(fields, parent_path)
        if source is None or parent is None or source is parent:
            continue
        prior = next((field for field in parent.properties if field.key == key), None)
        if prior is not None and source.properties and _append_fields(prior.properties, source.properties):
            fields.remove(source)
            continue
        fields.remove(source)
        if not _append_fields(parent.properties, [source]):
            fields.append(source)

    _inherit_documented_object_shapes(fields)

    resolved: list[StructuralTableMerge] = []
    by_table = {merge.table: merge for merge in _STRUCTURAL_TABLE_SPLITS.get(section.endpoint, ())}
    for index, table in enumerate(section.tables[1:], start=1):
        merge = by_table.get(index)
        if merge is None:
            continue
        source_fields = copy.deepcopy(table.fields)
        _apply_structural_table_requirements(section.endpoint, index, source_fields)
        if section.endpoint == "/DESIGN/RC/KDS-41-20-2022/DCRE" and index == 4:
            # The manual says the two arrays share the same item structure.
            # Its one table lists the two array names followed by their shared
            # REBAR_DIAMETER/MATERIAL item rows, so retain that hierarchy for
            # both arrays instead of putting the item rows beside them.
            parent = _field_at_path(fields, ("Assign", "WALL", "MATERIAL_BY_DIAMETER_INPUT"))
            rows = {field.key: copy.deepcopy(field) for field in _walk(source_fields)}
            if parent is not None and {"VERTICAL_END_REBAR", "HORIZONTAL_REBAR", "REBAR_DIAMETER", "MATERIAL"} <= rows.keys():
                children = [rows["REBAR_DIAMETER"], rows["MATERIAL"]]
                vertical = rows["VERTICAL_END_REBAR"]
                horizontal = rows["HORIZONTAL_REBAR"]
                vertical.properties = copy.deepcopy(children)
                horizontal.properties = copy.deepcopy(children)
                if _append_fields(parent.properties, [vertical, horizontal]):
                    resolved.append(merge)
            continue
        destinations: list[list[ParsedField]] = []
        for path in merge.targets:
            parent = _field_at_path(fields, path)
            if path and parent is None:
                destinations = []
                break
            destinations.append(fields if not path else parent.properties)
        if not destinations:
            continue
        # Clone for every target: the manual explicitly states the same item
        # shape for e.g. REBB's I/M/J sectors and REBC's two shear-bar objects.
        # Preflight every destination so a duplicate cannot leave a half-merged
        # draft that looks complete.
        destination_keys = [{field.key: field for field in destination} for destination in destinations]
        compatible = all(
            all(
                field.key not in keys
                or (
                    keys[field.key].type,
                    keys[field.key].requirement,
                    keys[field.key].documented_default,
                    keys[field.key].documented_default_note,
                )
                == (
                    field.type,
                    field.requirement,
                    field.documented_default,
                    field.documented_default_note,
                )
                for field in source_fields
            )
            for keys in destination_keys
        )
        if not compatible:
            continue
        for destination in destinations:
            additions = copy.deepcopy(source_fields)
            if merge.products:
                _tag_products(additions, merge.products)
            if not _append_fields(destination, additions):
                raise AssertionError("preflighted structural table merge became incompatible")
        resolved.append(merge)
    return fields, resolved


def _conditional_fields(section: "Section", fields: list[ParsedField]) -> tuple[list[ParsedField], set[int]]:
    """Merge audited conditional tables without guessing a payload branch."""
    Condition = tuple[str, str | int | float | bool]

    def as_values(condition: Condition) -> tuple[str, tuple]:
        """Curated entries are written (field, scalar); store (field, values)."""
        path, value = condition
        return path, value if isinstance(value, tuple) else (value,)

    audited: dict[str, dict[int, tuple[tuple[Condition, ...], str | None]]] = {
        "/db/CCFC": {
            1: ((("TYPE", "CONST"),), 'Constant 타입 (TYPE="CONST") 추가 파라미터'),
            2: ((("TYPE", "USER"),), 'User 타입 (TYPE="USER") 추가 파라미터'),
        },
        "/db/ETFC": {
            1: ((("TYPE", "CONST"),), 'Constant 타입 (TYPE="CONST") 추가 파라미터'),
            2: ((("TYPE", "SINE"),), 'Sine 타입 (TYPE="SINE") 추가 파라미터'),
            3: ((("TYPE", "USER"),), 'User 타입 (TYPE="USER") 추가 파라미터'),
        },
        "/db/PNLA": {
            1: ((("ELEM_TYPE", "PLATE"),), 'ELEM_TYPE = "PLATE"'),
            2: ((("SELECT_TYPE", "IN_GROUP"),), 'SELECT_TYPE = "IN_GROUP"'),
            3: ((("ELEM_TYPE", "SOLID"),), 'ELEM_TYPE = "SOLID"'),
        },
        "/db/MATL": {
            # The three tables describe one `PARAM` entry, not one request; see
            # conditional_parent_paths below. Passing None keeps the manual's
            # own heading as the condition text.
            1: ((("P_TYPE", 1),), None),
            2: ((("P_TYPE", 2),), None),
            3: ((("P_TYPE", 3),), None),
        },
        # Row 16 names iMDTYPE's values - 1=Modal, 2=Mass&Stiff - under
        # bDAMP=true, the two tables are headed with those names, and the
        # section's Modal and Mass & Stiffness Request Bodies send exactly
        # those pairs.
        "/db/SPLC": {
            1: ((("bDAMP", True), ("iMDTYPE", 1)), "Modal 감쇠 추가 파라미터 (bDAMP=true, iMDTYPE=1)"),
            2: (
                (("bDAMP", True), ("iMDTYPE", 2)),
                "Mass & Stiffness Proportional 감쇠 추가 파라미터 (bDAMP=true, iMDTYPE=2)",
            ),
        },
        "/db/THIK": {
            1: (
                (("TYPE", "STIFFENED"), ("STYPE", "DB")),
                'Stiffened DB (TYPE="STIFFENED", STYPE="DB")',
            ),
        },
        "/db/THFC": {
            1: ((("FUNCTYPE", 1),), "Time Function (FUNCTYPE=1) 추가 파라미터"),
            2: ((("FUNCTYPE", 2),), "Sinusoidal (FUNCTYPE=2) 추가 파라미터"),
        },
        "/db/STCT": {
            5: (
                (("iINC_NLA", (1, 2)),),
                "Parameters — Nonlinear Analysis (`iINC_NLA` = 1 또는 2)",
            ),
            6: (
                (("iNLA_TYPE", 1),),
                "Parameters — Time Dependent Effect (누가 단계, `iNLA_TYPE` = 1)",
            ),
        },
        "/db/NSPR": {
            1: ((("TYPE", "LINEAR"),), "LINEAR 전용"),
            2: ((("TYPE", ("COMP", "TENS")),), "COMP(Compression-Only) / TENS(Tension-Only) 전용"),
            3: ((("TYPE", "MULTI"),), "MULTI(Multi-Linear) 전용"),
            4: (
                (("FormType", 1),),
                "By Surface Spring Function 전용(`FormType`=1일 때 공통 추가)",
            ),
        },
        "/db/IMPF": {
            1: (
                (("FACT_TYPE", ("IMPACT_FACT", "EFF_SPAN_LEN_USER")),),
                "Line Lane / Surface Lane (Impact Factor, Effective Span Length – User Input)",
            ),
            2: (
                (("FACT_TYPE", "EFF_SPAN_LEN_AUTO"),),
                "Line Lane (Effective Span Length – Auto Calculation)",
            ),
        },
        "/db/HSFC": {
            1: ((("TYPE", "CONST"),), 'Constant 타입 (TYPE="CONST") 추가 파라미터'),
            2: (
                (("TYPE", "FUNC"), ("OPT_USE_CONC_DATA", False)),
                'Code 타입 (TYPE="FUNC") - 콘크리트 데이터 미사용 (OPT_USE_CONC_DATA=false)',
            ),
            3: (
                (("TYPE", "FUNC"), ("OPT_USE_CONC_DATA", True)),
                'Code 타입 (TYPE="FUNC") - 콘크리트 데이터 사용 (OPT_USE_CONC_DATA=true)',
            ),
            4: ((("TYPE", "USER"),), 'User 타입 (TYPE="USER") 추가 파라미터'),
        },
        "/db/MVLDid": {
            1: (
                (("OPT_AUTO_LL", True),),
                "Auto Live Load Combinations (OPT_AUTO_LL=true)",
            ),
            2: (
                (("OPT_LC_FOR_PERMIT_LOAD", True),),
                "Permit Vehicle (OPT_LC_FOR_PERMIT_LOAD=true)",
            ),
        },
        # 05_DB_Boundary.md names both gates in every global-coordinate
        # table.  REF_SYSTEM alone is not enough: INPUT_METHOD selects the
        # Angle, 3Points, or Vector payload field.
        "/db/NLNK": {
            1: ((("REF_SYSTEM", 0),), "REF_SYSTEM=0 (요소계)"),
            2: ((("REF_SYSTEM", 1), ("INPUT_METHOD", 0)), "REF_SYSTEM=1 (전역계) – Angle 방식"),
            3: ((("REF_SYSTEM", 1), ("INPUT_METHOD", 1)), "REF_SYSTEM=1 (전역계) – 3Points 방식"),
            4: ((("REF_SYSTEM", 1), ("INPUT_METHOD", 2)), "REF_SYSTEM=1 (전역계) – Vector 방식"),
        },
        "/ope/GSBG": {
            1: ((("BATCH", True),), None),
            2: ((("BATCH", False),), None),
            3: ((("DGRM_TYPE", 0),), None),
        },
    }
    merged = copy.deepcopy(fields)
    resolved: set[int] = set()

    # HSFC documents OPT_USE_CONC_DATA in both FUNC subtables.  Its own
    # applicability is TYPE=FUNC, while its value selects the sibling field
    # set.  Do not assign either false or true branch to the shared selector.
    shared_selector_conditions: dict[tuple[str, int, str], tuple[tuple[Condition, ...], str]] = {
        ("/db/HSFC", 2, "OPT_USE_CONC_DATA"): ((("TYPE", "FUNC"),), 'Code 타입 (TYPE="FUNC")'),
        ("/db/HSFC", 3, "OPT_USE_CONC_DATA"): ((("TYPE", "FUNC"),), 'Code 타입 (TYPE="FUNC")'),
        # STYPE is the Stiffened sub-type selector itself; its own gate is TYPE.
        ("/db/THIK", 1, "STYPE"): ((("TYPE", "STIFFENED"),), 'TYPE="STIFFENED"'),
    }
    # The India moving-load manual repeats SUB_LOAD_ITEMS for the Auto Live
    # Load case and adds item members below it.  The named Array parent already
    # exists in the general-load table, so merge only the documented item
    # members at that path.  Treating them as root fields would recreate the
    # RIGD/OFFS flattening defect.
    conditional_child_paths: dict[tuple[str, int], tuple[str, ...]] = {
        ("/db/MVLDid", 1): ("SUB_LOAD_ITEMS",),
    }
    # A conditional table whose heading names the object it describes -
    # `#### PARAM - P_TYPE = 1 (Standard / DB)` - lists that object's members,
    # not the request's. Merged at the root they become an endpoint-level
    # branch, and the npm generator built `MaterialPayload & {P_TYPE: 1;
    # STANDARD: string; ...}`: `STANDARD` beside `TYPE` and `NAME`, where no
    # payload has ever carried it. The manual's own Request Example, and the
    # Python TypedDict, put every one of them inside a `PARAM` entry. Only
    # headings that name the parent literally are listed here.
    conditional_parent_paths: dict[tuple[str, int], tuple[str, ...]] = {
        ("/db/MATL", 1): ("PARAM",),
        ("/db/MATL", 2): ("PARAM",),
        ("/db/MATL", 3): ("PARAM",),
        ("/db/NSPR", 1): ("ITEMS",),
        ("/db/NSPR", 2): ("ITEMS",),
        ("/db/NSPR", 3): ("ITEMS",),
        ("/db/NSPR", 4): ("ITEMS",),
        ("/db/IMPF", 1): ("ITEMS",),
        ("/db/IMPF", 2): ("ITEMS",),
    }

    def annotate(entries: list[ParsedField], conditions: tuple[Condition, ...], raw: str) -> None:
        normalised = [as_values(condition) for condition in conditions]
        for entry in entries:
            entry.condition = entry.condition or raw
            entry.applies_when.extend(normalised)

    for index, (conditions, raw) in audited.get(section.endpoint, {}).items():
        if index >= len(section.tables):
            continue
        additions = copy.deepcopy(section.tables[index].fields)
        parent_path = conditional_parent_paths.get((section.endpoint, index))
        if parent_path is not None:
            destination = _field_at_path(merged, parent_path)
            if destination is None:
                continue
            annotate(additions, conditions, raw or section.tables[index].heading)
            if _append_fields(destination.properties, additions):
                resolved.add(index)
            continue
        child_path = conditional_child_paths.get((section.endpoint, index))
        if child_path is not None:
            source = next((field for field in additions if field.key == child_path[-1]), None)
            destination = _field_at_path(merged, child_path)
            if source is None or destination is None:
                continue
            annotate(source.properties, conditions, raw or section.tables[index].heading)
            if not _append_fields(destination.properties, source.properties):
                continue
            additions.remove(source)
            # NUM_LOADED_LANES is a repeated scalar whose base declaration
            # already applies to every payload shape.  Its Auto table does not
            # add a distinct field, whereas SUB_LOAD_ITEMS adds item members.
            additions = [field for field in additions if field.key != "NUM_LOADED_LANES"]
        for addition in additions:
            special = shared_selector_conditions.get((section.endpoint, index, addition.key))
            annotate([addition], *(special or (conditions, raw or section.tables[index].heading)))
        if _append_fields(merged, additions):
            resolved.add(index)
    _apply_reviewed_additional_field_conditions(section.endpoint, merged)
    return merged, resolved


def _section_schema_hints(lines: list[str], endpoint: str) -> dict[tuple[str, ...], list[dict[str, Any]]]:
    """Read exact property metadata from a section's own ``JSON Schema`` fence.

    The manual's parameter table remains the primary transcription.  Several
    chapters, however, render Markdown escapes in a table while the same
    section's JSON Schema spells out array items or enum values exactly.  This
    function reads only fenced JSON below a ``JSON Schema`` heading in that
    *same endpoint section*; examples and neighbouring endpoint schemas are
    deliberately excluded.
    """

    hints: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    endpoint_wrapper = endpoint.rsplit("/", 1)[-1]
    for index, line in enumerate(lines):
        if not re.fullmatch(r"#{2,}\s+JSON Schema\s*", line.strip(), re.IGNORECASE):
            continue
        start = next(
            (position for position in range(index + 1, len(lines)) if lines[position].strip() == "```json"),
            None,
        )
        if start is None:
            continue
        end = next(
            (position for position in range(start + 1, len(lines)) if lines[position].strip() == "```"),
            None,
        )
        if end is None:
            continue
        try:
            schema = json.loads("\n".join(lines[start + 1 : end]))
        except json.JSONDecodeError:
            continue
        # Several DB chapters wrap their schema in the endpoint token itself
        # (``{"NPLN": {...}}``), while their parameter table starts directly
        # at the record payload. It is an exact transport wrapper only when it
        # is the sole root member and exactly matches this endpoint.
        if isinstance(schema, dict) and set(schema) == {endpoint_wrapper} and isinstance(schema[endpoint_wrapper], dict):
            schema = schema[endpoint_wrapper]

        def condition_text(node: Any) -> Optional[str]:
            """Render one exact JSON-Schema selector without inventing a rule.

            The design-code chapters put conditional requiredness in ``allOf``
            as a one-property ``if`` plus a ``then.required`` list.  A general
            JSON Schema condition is more expressive than a contract field's
            short ``condition`` string, so accept only the two literal forms
            that can be transcribed losslessly: ``const`` and a finite scalar
            ``enum`` on exactly one named property.
            """

            if not isinstance(node, dict):
                return None
            properties = node.get("properties")
            if not isinstance(properties, dict) or len(properties) != 1:
                return None
            key, constraint = next(iter(properties.items()))
            if not isinstance(key, str) or not isinstance(constraint, dict):
                return None
            if "const" in constraint and isinstance(constraint["const"], (str, int, float, bool)):
                value = constraint["const"]
                rendered = json.dumps(value) if isinstance(value, str) else str(value).lower()
                return f"{key}={rendered}"
            values = constraint.get("enum")
            if (
                isinstance(values, list)
                and values
                and all(isinstance(value, (str, int, float, bool)) for value in values)
            ):
                rendered = [json.dumps(value) if isinstance(value, str) else str(value).lower() for value in values]
                return f"{key} ∈ {{{', '.join(rendered)}}}"
            return None

        def visit(node: Any, prefix: tuple[str, ...] = ()) -> None:
            if not isinstance(node, dict):
                return
            for branch_name in ("allOf", "anyOf", "oneOf"):
                for branch in node.get(branch_name, []):
                    visit(branch, prefix)
                    # A field table that says only "Conditional required" is
                    # completed only when this *same manual schema* names both
                    # the selector and the field that becomes required.  Do
                    # not turn a prose example, or a general JSON-Schema
                    # expression, into a condition claim.
                    if not isinstance(branch, dict):
                        continue
                    condition = condition_text(branch.get("if"))
                    then = branch.get("then")
                    required = then.get("required") if isinstance(then, dict) else None
                    if condition is None or not isinstance(required, list):
                        continue
                    for key in required:
                        if isinstance(key, str):
                            hints.setdefault(prefix + (key,), []).append(
                                {"__conditional": condition}
                            )
            properties = node.get("properties")
            # A few design-table parameter rows compact a mutually exclusive
            # selector pair (for example ``"ELEMS" / "SECTIONS"``).  Preserve
            # the exact one-of requirement only when every branch states one
            # literal required property; broader JSON Schema expressions stay
            # outside the extractor's lossless subset.
            one_of = node.get("oneOf")
            one_of_members: list[str] = []
            if isinstance(one_of, list) and len(one_of) >= 2:
                for branch in one_of:
                    required_names = branch.get("required") if isinstance(branch, dict) else None
                    if not (
                        isinstance(required_names, list)
                        and len(required_names) == 1
                        and isinstance(required_names[0], str)
                    ):
                        one_of_members = []
                        break
                    one_of_members.append(required_names[0])
                if len(set(one_of_members)) != len(one_of_members):
                    one_of_members = []
            if one_of_members:
                for key in one_of_members:
                    hints.setdefault(prefix + (key,), []).append(
                        {"__one_of_required": tuple(one_of_members)}
                    )
            if isinstance(properties, dict):
                required = node.get("required", [])
                required_names = set(required) if isinstance(required, list) and all(isinstance(name, str) for name in required) else set()
                for key, child in properties.items():
                    if not isinstance(key, str) or not isinstance(child, dict):
                        continue
                    # Endpoint wrappers are message transport, not payload
                    # members.  Table paths start immediately inside them.
                    if not prefix and key in {"Argument", "Assign", endpoint_wrapper}:
                        visit(child, prefix)
                        continue
                    path = prefix + (key,)
                    hint = dict(child)
                    hint["__required"] = key in required_names
                    hints.setdefault(path, []).append(hint)
                    visit(child, path)
            # ``Assign`` in the design-code chapters is a dictionary keyed by
            # an ID string.  Its single ``patternProperties`` child is the
            # record schema, not a field named by the regular expression.  At
            # the endpoint root it is therefore safe to unwrap that one layer;
            # doing this below a real field would fabricate a path, so do not.
            pattern_properties = node.get("patternProperties")
            if (
                not prefix
                and isinstance(pattern_properties, dict)
                and len(pattern_properties) == 1
            ):
                child = next(iter(pattern_properties.values()))
                if isinstance(child, dict):
                    visit(child, prefix)
            # Some design schemas use ``additionalProperties`` rather than a
            # numeric ``patternProperties`` for an ID-keyed record map.  When
            # that map has no named siblings, its value schema describes the
            # same table path -- the arbitrary ID is transport structure, not
            # a payload member.  Unwrap only this exact map form; an
            # ``additionalProperties`` schema alongside real properties has
            # different JSON-Schema semantics and must not be flattened.
            additional_properties = node.get("additionalProperties")
            if (
                not isinstance(properties, dict)
                and isinstance(additional_properties, dict)
                and isinstance(additional_properties.get("properties"), dict)
            ):
                visit(additional_properties, prefix)
            if node.get("type") == "array":
                # The extractor models Array[Object] children as properties of
                # the array field, so retain the same path when walking items.
                visit(node.get("items"), prefix)

        visit(schema)
    return hints


def _agreed_schema_value(entries: list[dict[str, Any]], key: str) -> Any | None:
    """Return a value only when concrete same-path properties agree on it.

    ``allOf.if/then`` contributes a small ``{"__conditional": ...}`` hint
    at the field made conditionally required.  That marker records the
    relation, but is not a competing property schema: it must not make an
    otherwise explicit enum, default, or type look absent.  Real property
    schemas remain deliberately strict -- every one that states *key* must
    agree before we transcribe it.
    """

    values = [entry[key] for entry in entries if key in entry]
    if not values:
        return None
    if any(value != values[0] for value in values[1:]):
        return None
    return values[0]


def _schema_enum_values(entry: dict[str, Any]) -> Optional[list[Any]]:
    """Read a complete scalar enum from one manual JSON-Schema property.

    Some design chapters use ``oneOf`` with one ``const`` per documented
    choice rather than JSON Schema's compact ``enum`` keyword. Both forms
    state the same finite wire-value set. A shortened ``oneOf`` (for example
    an ellipsis entry or a branch without ``const``) stays unverified.
    """

    enum = entry.get("enum")
    if isinstance(enum, list) and enum and all(isinstance(value, (str, int, float, bool)) for value in enum):
        return enum
    choices = entry.get("oneOf")
    if not isinstance(choices, list) or not choices:
        return None
    values: list[Any] = []
    for choice in choices:
        if not isinstance(choice, dict) or "const" not in choice:
            return None
        value = choice["const"]
        if not isinstance(value, (str, int, float, bool)) or value in values:
            return None
        values.append(value)
    return values


_AMBIGUOUS_WIRE_KEY_NOTE = "is not a single field name"


def _ambiguous_literal_keys(field: ParsedField) -> Optional[tuple[str, ...]]:
    """Return a compact row's literal keys, never prose or decorated text."""

    if "/" not in field.key:
        return None
    keys = tuple(part.strip().strip('"') for part in re.split(r"\s*/\s*", field.key))
    if len(keys) < 2 or len(set(keys)) != len(keys):
        return None
    if not all(_PATH_SEGMENT.fullmatch(key) for key in keys):
        return None
    return keys


def _range_row_endpoints(field: ParsedField) -> Optional[tuple[str, str, int]]:
    """Read a row that names an interval of keys, with the count it claims.

    `/db/CO_S` writes its nine RGB components as one row: No. ``1-9``, key
    ``"W_R" ~ "HE_B"``. Read as two keys it loses seven documented fields, and
    the endpoints alone do not say which lie between them. The count does not
    come from anywhere but the No. column, and the members do not come from
    anywhere but the section's own JSON Schema, so both have to be present and
    agree before this row can be expanded.
    """

    match = re.fullmatch(r'\s*"?([A-Za-z_][\w]*)"?\s*[~∼]\s*"?([A-Za-z_][\w]*)"?\s*', field.key)
    if match is None or match.group(1) == match.group(2):
        return None
    span = re.fullmatch(r"\s*(\d+)\s*[-–—~]\s*(\d+)\s*", field.number)
    if span is None:
        return None
    count = int(span.group(2)) - int(span.group(1)) + 1
    if count < 2:
        return None
    return match.group(1), match.group(2), count


def _schema_children(hints: dict[tuple[str, ...], list[dict[str, Any]]], parent: tuple[str, ...]) -> set[str]:
    """List direct, concrete manual-schema property names below *parent*."""

    return {
        path[-1]
        for path, entries in hints.items()
        if path[:-1] == parent
        and any(any(not key.startswith("__") for key in entry) for entry in entries)
    }

def _schema_child_order(
    hints: dict[tuple[str, ...], list[dict[str, Any]]], parent: tuple[str, ...]
) -> list[str]:
    """The same children, in the order the manual's JSON Schema declares them.

    A row naming an interval of keys is only expandable because the schema
    states both the members and their sequence; a set would leave the interval
    undefined.
    """

    seen: list[str] = []
    for path, entries in hints.items():
        if path[:-1] != parent or path[-1] in seen:
            continue
        if any(any(not key.startswith("__") for key in entry) for entry in entries):
            seen.append(path[-1])
    return seen


def _expand_range_row(
    field: ParsedField,
    hints: dict[tuple[str, ...], list[dict[str, Any]]],
    parent_paths: set[tuple[str, ...]],
) -> Optional[tuple[str, ...]]:
    """Name every key an interval row covers, or refuse to name any.

    Three independent statements have to line up: the row's two endpoints, the
    No. column's span, and the section's JSON Schema property order. When the
    slice between the endpoints is exactly as long as the span claims, the
    members are transcribed rather than guessed - `/db/CO_S`'s ``1-9`` and
    ``"W_R" ~ "HE_B"`` select nine schema properties and the schema lists nine.
    A mismatch means one of the three is wrong, and the row keeps its note.
    """

    bounds = _range_row_endpoints(field)
    if bounds is None:
        return None
    first, last, count = bounds
    for parent in parent_paths:
        order = _schema_child_order(hints, parent)
        if first not in order or last not in order:
            continue
        start, stop = order.index(first), order.index(last)
        if start >= stop:
            continue
        span = tuple(order[start : stop + 1])
        if len(span) == count:
            return span
    return None


def _reconcile_schema_compact_key_rows(
    tables: list[ParsedTable], hints: dict[tuple[str, ...], list[dict[str, Any]]]
) -> None:
    """Expand a compact multi-key row only when its own schema names every key.

    A table such as ``"ELEMS" / "SECTIONS"`` cannot be split from its cells
    alone: its type and requiredness claims may belong to different members.
    Some manual sections also supply a same-section JSON Schema that names each
    member and the children of the object alternative. In that narrow form the
    schema is exact manual evidence, so repair both the sibling row and any
    numbered compact child row. Every other multi-key spelling remains a
    review note rather than becoming a guessed payload shape.
    """

    parent_paths = {
        path[:-1]
        for path, entries in hints.items()
        if any(any(not key.startswith("__") for key in entry) for entry in entries)
    }

    def candidates(keys: tuple[str, ...]) -> list[tuple[str, ...]]:
        return [path for path in parent_paths if set(keys).issubset(_schema_children(hints, path))]

    def replace(fields: list[ParsedField], index: int, field: ParsedField, keys: tuple[str, ...]) -> list[ParsedField]:
        expanded: list[ParsedField] = []
        for key in keys:
            clone = copy.deepcopy(field)
            clone.key = key
            clone.type = None
            clone.items = None
            clone.properties = []
            clone.shared_number_group = False
            clone.notes = [
                note
                for note in clone.notes
                if _AMBIGUOUS_WIRE_KEY_NOTE not in note
                and not note.startswith("unrecognised Value Type")
                and not note.startswith("array element type not stated")
                and not note.startswith("the manual nests this under ")
            ]
            expanded.append(clone)
        fields[index : index + 1] = expanded
        return expanded

    for table in tables:
        # Revisit the table after each replacement: a root compact row can
        # first make an object alternative addressable, allowing its misplaced
        # numbered compact children to be moved on the next pass.
        for _ in range(len(_walk(table.fields)) + 1):
            locations: list[tuple[list[ParsedField], int, ParsedField]] = []

            def collect(fields: list[ParsedField]) -> None:
                for index, field in enumerate(fields):
                    locations.append((fields, index, field))
                    collect(field.properties)

            collect(table.fields)
            repaired = False
            for fields, index, field in locations:
                keys = _ambiguous_literal_keys(field)
                if keys is None:
                    keys = _expand_range_row(field, hints, parent_paths)
                if keys is None:
                    continue
                matches = candidates(keys)
                if len(matches) != 1:
                    continue
                parent = matches[0]
                destination = _field_at_path(table.fields, parent)
                if parent and destination is None:
                    continue
                expanded = replace(fields, index, field, keys)
                if destination is not None and fields is not destination.properties:
                    _append_fields(destination.properties, expanded)
                    del fields[index : index + len(expanded)]
                repaired = True
                break
            if not repaired:
                break


def _schema_parents(hints: dict[tuple[str, ...], list[dict[str, Any]]]) -> dict[tuple[str, ...], set[str]]:
    """Group a section's schema properties by the object that declares them."""

    parents: dict[tuple[str, ...], set[str]] = {}
    for path, entries in hints.items():
        if path and any(any(not name.startswith("__") for name in entry) for entry in entries):
            parents.setdefault(path[:-1], set()).add(path[-1])
    return parents


def _compact_row_defaults(field: ParsedField, count: int) -> Optional[list[Any]]:
    """Read one documented default per key from a compact row's Default cell.

    The cell is either a single claim shared by every key (``0``) or one claim
    per key in row order (``0.3 / 0.15 / 0.1``). Anything else - prose, or a
    list of the wrong length - is not a per-key statement and refuses.
    """

    if field.documented_default_note is None:
        return [field.documented_default] * count
    parts = re.split(r"\s*/\s*", field.documented_default_note.strip())
    if len(parts) != count:
        return None
    values: list[Any] = []
    for part in parts:
        value, note = _normalize_default(part)
        if note is not None:
            return None
        values.append(value)
    return values


def _expand_schema_named_compact_rows(
    tables: list[ParsedTable], hints: dict[tuple[str, ...], list[dict[str, Any]]]
) -> None:
    """Split a compact key row whose own JSON Schema names each key separately.

    ``"DE" / "DW" | Number | 0 | Optional`` compresses two fields into one row,
    and the row alone cannot say whether the slash means "both keys, one shared
    claim" or "one field the manual names two ways". `/db/THIS-M1` writes the
    second kind - ``FREQ1/PERIOD1``, a frequency when ``COEF_CALC=0`` and a
    period when it is 1 - so splitting every such row would publish fields that
    do not exist.

    The section's own JSON Schema decides which it is. Where the schema
    declares every key in the row as a property of its own, they are distinct
    wire names, and it states each one's type, requiredness and default
    individually - the detail the compressed row had to drop. Where it declares
    none of them, as every `/db/STCT`, `/db/MVLDeu`, `/db/MVHL` and
    `/db/THIS-M1` compact row does, nothing is split and the review note stays.

    Both statements have to agree before either is transcribed. A type or a
    default the row states and the schema contradicts leaves the row whole,
    rather than letting one source silently overrule the other.

    _reconcile_schema_compact_key_rows handles the rows whose object *is* a
    field of the same table, by moving them into it. These are the rows the
    manual writes in a table of their own - a section that heads one table per
    member object, as chapter 26 does - where there is no parent field to move
    into and the row already sits at the right level.
    """

    scalar_types = {"string", "number", "integer", "boolean", "object", "array"}
    children = _schema_parents(hints)
    if not children:
        return

    def split(field: ParsedField) -> Optional[list[ParsedField]]:
        if not any(_AMBIGUOUS_WIRE_KEY_NOTE in note for note in field.notes):
            return None
        keys = _ambiguous_literal_keys(field)
        if keys is None:
            return None
        # Several objects may declare the same key set - chapter 26's COLUMN
        # and BRACE are documented as having identical fields. Which object
        # this table describes does not have to be decided: pooling every
        # candidate's property schemas and requiring them to agree says the
        # keys mean the same thing under all of them, which is the only claim
        # being transcribed.
        parents = [parent for parent, names in children.items() if set(keys) <= names]
        if not parents:
            return None
        defaults = _compact_row_defaults(field, len(keys))
        if defaults is None:
            return None
        clones: list[ParsedField] = []
        for index, key in enumerate(keys):
            entries = [
                entry
                for parent in parents
                for entry in hints.get(parent + (key,), [])
                if any(not name.startswith("__") for name in entry)
            ]
            schema_type = _agreed_schema_value(entries, "type")
            if schema_type not in scalar_types:
                return None
            if field.type is not None and field.type != schema_type:
                return None
            required = _agreed_schema_value(entries, "__required")
            if not isinstance(required, bool):
                return None
            requirement = "required" if required else "optional"
            if field.requirement is not None and field.requirement != requirement:
                return None
            default = _agreed_schema_value(entries, "default")
            if not field.default_column_missing and defaults[index] != default:
                return None
            clone = copy.deepcopy(field)
            clone.key = key
            clone.type = schema_type
            clone.requirement = requirement
            clone.documented_default = default
            clone.documented_default_note = None
            clone.shared_number_group = False
            # The row describes every key at once ("horizontal / end / boundary
            # rebar size"); the schema describes this one. Both are the
            # manual's own words, and only one of them is about this field.
            description = _agreed_schema_value(entries, "description")
            if isinstance(description, str) and description:
                clone.description = description
            enums = [_schema_enum_values(entry) for entry in entries]
            filled_enum = enums[0] if enums and all(value == enums[0] for value in enums) else None
            if not clone.enum and filled_enum:
                clone.enum = filled_enum
            items = _agreed_schema_value(entries, "items")
            if schema_type == "array" and clone.items is None and isinstance(items, dict):
                item_type = items.get("type")
                if item_type in scalar_types:
                    clone.items = {"type": item_type}
            clone.notes = [
                note
                for note in clone.notes
                if _AMBIGUOUS_WIRE_KEY_NOTE not in note
                and not note.startswith("unrecognised Value Type")
                and not note.startswith("unrecognised Required value")
                and not (note == _ENUM_VALUES_ELSEWHERE and filled_enum)
                and not (note == "array element type not stated by the manual" and clone.items)
            ]
            clones.append(clone)
        return clones

    def visit(fields: list[ParsedField]) -> None:
        index = 0
        while index < len(fields):
            field = fields[index]
            visit(field.properties)
            clones = split(field)
            if clones is None:
                index += 1
                continue
            fields[index : index + 1] = clones
            index += len(clones)

    for table in tables:
        visit(table.fields)


_COMPACT_PROSE_CONDITION_PAIR = re.compile(
    r'`(?P<selector>[A-Za-z0-9_]+)\s*=\s*"(?P<first_value>[^"`]+)"`\s*이면\s*'
    r'`(?P<first_target>[A-Za-z0-9_]+)`\s*,\s*`"(?P<second_value>[^"`]+)"`\s*이면\s*'
    r'`(?P<second_target>[A-Za-z0-9_]+)`'
)
_PARALLEL_PROSE_CONDITION_PAIR = re.compile(
    r'`(?P<selector>[A-Za-z0-9_]+)`[^`\n]*\('
    r'(?P<values>(?:`"[^"`]+"`\s*(?:/\s*)?){2,})\)'
    r'[^\n]*각각\s*(?P<targets>(?:`[A-Za-z0-9_]+`\s*(?:/\s*)?){2,})'
)


def _apply_explicit_prose_conditions(tables: list[ParsedTable], lines: list[str]) -> None:
    """Attach only lossless two-branch conditions written in manual prose.

    The RC report sections state a pair of conditional fields below the table
    as ``REPORT_TYPE="MEMB"이면 CURRENT_MODE_MEMB, "PROP"이면
    CURRENT_MODE_PROP``. The table's ``Conditional`` cell alone is incomplete,
    but this exact code-spanned form names both selector values and both target
    keys. Examples and unstructured prose deliberately do not participate.
    """

    text = "\n".join(lines)
    pairs: list[tuple[str, str, str]] = []
    for match in _COMPACT_PROSE_CONDITION_PAIR.finditer(text):
        selector = match.group("selector")
        pairs.extend(
            (
                (selector, match.group("first_value"), match.group("first_target")),
                (selector, match.group("second_value"), match.group("second_target")),
            )
        )
    for match in _PARALLEL_PROSE_CONDITION_PAIR.finditer(text):
        values = re.findall(r'`"([^"`]+)"`', match.group("values"))
        targets = re.findall(r'`([A-Za-z0-9_]+)`', match.group("targets"))
        if len(values) == len(targets) and len(values) >= 2:
            pairs.extend((match.group("selector"), value, target) for value, target in zip(values, targets))
    for table in tables:
        for selector, value, target_name in pairs:
            target = _field_at_path(table.fields, (target_name,))
            if target is None or target.requirement != "conditional" or target.condition is not None:
                continue
            target.condition = f'{selector}="{value}"'
            condition = (selector, (value,))
            if condition not in target.applies_when:
                target.applies_when.append(condition)
            target.notes = [
                note
                for note in target.notes
                if note != "the manual marks this conditional but does not state the condition"
            ]


# Which JSON Schema keyword can bound which kind of value. A bound stated for
# a different kind is the manual contradicting its own type declaration, and
# both halves cannot be right - see the note _apply_schema_hints attaches.
_CONSTRAINT_APPLIES_TO: dict[str, set[str]] = {
    "minimum": {"number", "integer"},
    "maximum": {"number", "integer"},
    "minItems": {"array"},
    "maxItems": {"array"},
    "minLength": {"string"},
    "maxLength": {"string"},
}


def _table_schema_bases(
    table: ParsedTable, children: dict[tuple[str, ...], set[str]]
) -> tuple[tuple[str, ...], ...]:
    """Where in the section's JSON Schema a whole parameter table sits.

    Most sections write one table whose rows are the request's root
    properties, and the root is where their schema hints are looked up.
    Chapter 26 heads one table per member object instead - a `BEAM` table, a
    `COLUMN` / `BRACE` table, a `WALL` table - and those rows are not root
    properties at all, so every hint missed them: `/DESIGN/RC/KDS-41-20-2022`'s
    rebar sections were transcribed without a single enum, default or
    requiredness the schema states, purely because of where the manual put the
    row.

    A table is placed only when it cannot be the root table - no row of it
    names a root property - and some object declares every one of its rows.
    Several objects may qualify, as `COLUMN` and `BRACE` do; the caller pools
    their property schemas and keeps only what they agree on, so the table does
    not have to be assigned to one of them.
    """

    keys = [field.key for field in table.fields]
    if len(keys) < 2 or any(not _PATH_SEGMENT.fullmatch(key) for key in keys):
        return ((),)
    if children.get((), set()) & set(keys):
        return ((),)
    bases = tuple(sorted(path for path, names in children.items() if path and set(keys) <= names))
    return bases or ((),)


def _apply_schema_hints_to_fields(
    fields: list[ParsedField],
    hints: dict[tuple[str, ...], list[dict[str, Any]]],
    bases: tuple[tuple[str, ...], ...] = ((),),
) -> None:
    """Fill only gaps that the same section's JSON Schema states exactly."""

    def visit(fields: list[ParsedField], bases: tuple[tuple[str, ...], ...], prefix: tuple[str, ...] = ()) -> None:
        for field in fields:
            path = prefix + (field.key,)
            entries = [entry for base in bases for entry in hints.get(base + path, [])]
            if entries:
                # ``then.required`` contributes only ``__conditional``.  It
                # describes a relationship between fields and must not act as
                # a second, empty property schema when evaluating the
                # concrete property metadata below.
                property_entries = [
                    entry for entry in entries if any(not key.startswith("__") for key in entry)
                ]
                synthesized_note = (
                    "no row of its own in the manual - inferred from the dotted paths of its "
                    "children, so its requiredness and default are unknown"
                )
                # A parent introduced solely to represent an explicit
                # ``PARENT[].CHILD`` path is no longer inferred when this
                # section's own JSON Schema names that parent: the schema is
                # direct manual evidence that the container exists, which is
                # what this note doubts. Requiredness is a separate question
                # and is not required for the note to go - when the schema
                # states none, `requirement` stays `unstated` just below, which
                # is where that gap is recorded. Retain the note when the
                # schema names no such parent at all.
                if (
                    synthesized_note in field.notes
                    and isinstance(_agreed_schema_value(property_entries, "type"), str)
                ):
                    field.notes.remove(synthesized_note)
                required = _agreed_schema_value(property_entries, "__required")
                if field.requirement is None and isinstance(required, bool):
                    field.requirement = "required" if required else "optional"
                    for note in (
                        "the table has no Required column",
                        "the manual leaves the Required column blank",
                    ):
                        if note in field.notes:
                            field.notes.remove(note)

                schema_type = _agreed_schema_value(property_entries, "type")
                nesting_type_notes = [
                    note
                    for note in field.notes
                    if note.startswith("the manual types this ") and "but it has nested children" in note
                ]
                if (field.type is None or nesting_type_notes) and schema_type in {
                    "string",
                    "number",
                    "integer",
                    "boolean",
                    "object",
                    "array",
                }:
                    field.type = schema_type
                    field.notes = [
                        note
                        for note in field.notes
                        if not note.startswith("unrecognised Value Type") and note not in nesting_type_notes
                    ]
                elif (
                    field.type is not None
                    and isinstance(schema_type, str)
                    and schema_type != field.type
                ):
                    # A section states its request twice, and here the two
                    # statements are not one lossy and one complete - they are
                    # different. `/db/SBDO` types `AXIS_VECTOR` Number in the
                    # table, `{"type": "array", "items": {"type": "number"}}` in
                    # the schema, and sends `[0, 0, 0, 0, 0, 0]` in its own
                    # request example; reading the table alone published an npm
                    # field a caller cannot assign the documented value to.
                    # Which one is right is a judgment with evidence outside
                    # this function, so transcribe neither and say so.
                    disagreement = (
                        f"the manual's Specifications table types this {field.type!r} while the "
                        f"same section's JSON Schema types it {schema_type!r}; the table's type "
                        "is kept unconfirmed and no type is taken from the schema"
                    )
                    if disagreement not in field.notes:
                        field.notes.append(disagreement)

                conditions = [entry["__conditional"] for entry in entries if "__conditional" in entry]
                distinct_conditions = list(dict.fromkeys(conditions))
                if (
                    field.requirement == "conditional"
                    and field.condition is None
                    and len(distinct_conditions) == 1
                ):
                    field.condition = distinct_conditions[0]
                    structured_condition = _variant_condition(field.condition)
                    if structured_condition is not None and structured_condition not in field.applies_when:
                        field.applies_when.append(structured_condition)
                    conditional_note = "the manual marks this conditional but does not state the condition"
                    if conditional_note in field.notes:
                        field.notes.remove(conditional_note)

                one_of_groups = [
                    entry["__one_of_required"] for entry in entries if "__one_of_required" in entry
                ]
                distinct_one_of_groups = list(dict.fromkeys(one_of_groups))
                if (
                    field.requirement == "conditional"
                    and field.condition is None
                    and len(distinct_one_of_groups) == 1
                ):
                    members = distinct_one_of_groups[0]
                    if isinstance(members, tuple) and field.key in members:
                        field.condition = "oneOf: exactly one of " + ", ".join(
                            json.dumps(member) for member in members
                        ) + " is required"
                        conditional_note = "the manual marks this conditional but does not state the condition"
                        if conditional_note in field.notes:
                            field.notes.remove(conditional_note)

                default = _agreed_schema_value(property_entries, "default")
                if default is not None:
                    if field.default_column_missing:
                        field.documented_default = default
                    # A bare string in a Markdown Default cell is ambiguous
                    # by itself (``System`` may be a UI label). The same
                    # section's JSON Schema ``default`` makes it an exact
                    # documented wire value, but only if both sources agree.
                    if field.documented_default_note == default:
                        field.documented_default = default
                        field.documented_default_note = None

                schema_enums = [_schema_enum_values(entry) for entry in property_entries]
                enum = schema_enums[0] if schema_enums and all(value == schema_enums[0] for value in schema_enums) else None
                if not field.enum and _ENUM_VALUES_ELSEWHERE in field.notes and enum:
                    field.enum = enum
                    if _ENUM_VALUES_ELSEWHERE in field.notes:
                        field.notes.remove(_ENUM_VALUES_ELSEWHERE)

                items = _agreed_schema_value(property_entries, "items")
                if field.type == "array" and field.items is None and isinstance(items, dict):
                    item_type = items.get("type")
                    if item_type in {"string", "number", "integer", "boolean", "object", "array"}:
                        field.items = {"type": item_type}
                        if "array element type not stated by the manual" in field.notes:
                            field.notes.remove("array element type not stated by the manual")

                for name in ("minimum", "maximum", "minItems", "maxItems", "minLength", "maxLength", "const"):
                    value = _agreed_schema_value(property_entries, name)
                    # Zero lower bounds are JSON Schema defaults, not a
                    # documented restriction.  Keeping them would manufacture
                    # drift against contracts that correctly omit a no-op.
                    if name in {"minItems", "minLength"} and value == 0:
                        continue
                    # `/DESIGN/RC/KDS-41-20-2022/REBR` declares NUM as an
                    # integer and bounds it with ``minItems: 4``, while its
                    # own table reads "min 4". The bound is real; the keyword
                    # that carries it is not one an integer has. Publishing it
                    # would put a restriction on the field that restricts
                    # nothing, so record the disagreement and transcribe
                    # neither half.
                    applies_to = _CONSTRAINT_APPLIES_TO.get(name)
                    if value is not None and applies_to is not None and field.type not in applies_to:
                        mismatch = (
                            f"the manual's JSON Schema bounds this with {name}={value!r} "
                            f"but types it as {field.type}, which that keyword does not "
                            "apply to; no constraint is transcribed"
                        )
                        if mismatch not in field.notes:
                            field.notes.append(mismatch)
                        continue
                    if value is not None and name not in field.constraints:
                        field.constraints[name] = value
            visit(field.properties, bases, path)

    visit(fields, bases)


def _apply_schema_hints(tables: list[ParsedTable], hints: dict[tuple[str, ...], list[dict[str, Any]]]) -> None:
    """Fill each parameter table from the schema object it describes."""

    children = _schema_parents(hints)
    for table in tables:
        _apply_schema_hints_to_fields(table.fields, hints, _table_schema_bases(table, children))


@dataclass
class Section:
    chapter_file: str
    number: str
    endpoint: str
    title: str
    heading: str
    lines: list[str]
    source_url: Optional[str] = None
    methods: list[str] = dataclass_field(default_factory=list)
    tables: list[ParsedTable] = dataclass_field(default_factory=list)
    variants: list[ParsedVariant] = dataclass_field(default_factory=list)
    # Set when several manual sections documenting one route were folded
    # into this one: (heading, line) for each, in chapter order.
    merged_sections: tuple[tuple[str, int], ...] = ()
    # Root properties this section's own JSON Schema declares that its
    # Specifications table never names, in schema order.
    schema_only_roots: tuple[str, ...] = ()
    # This section's own JSON Schema, keyed by wire path. Parsed once: the
    # merged field tree is built four times per section and each build asks
    # the schema to fill what the tables left out.
    schema_hints: dict[tuple[str, ...], list[dict[str, Any]]] = dataclass_field(default_factory=dict)

    @property
    def id(self) -> str:
        return _slug(self.endpoint)


_ENUM_TABLE_HEADING = re.compile(r"\b(?:enum|oneof|one of)\b", re.IGNORECASE)


def _enum_tables(lines: list[str]) -> dict[str, list[Any]]:
    """Read ``**`PATH` values (enum):**`` tables from one endpoint section."""

    found: dict[str, list[Any]] = {}
    for index, line in enumerate(lines):
        if not _ENUM_TABLE_HEADING.search(line):
            continue
        paths = re.findall(r"`([A-Za-z_][A-Za-z0-9_.]*)`", line)
        if len(paths) != 1:
            continue
        table = index + 1
        while table < len(lines) and not lines[table].startswith("#"):
            if lines[table].startswith("|") and table + 1 < len(lines) and _DIVIDER.match(lines[table + 1]):
                break
            table += 1
        if table >= len(lines) or not lines[table].startswith("|"):
            continue
        header = [_clean(cell).lower() for cell in _split_row(lines[table])]
        value_columns = [i for i, cell in enumerate(header) if cell in _ENUM_VALUE_COLUMNS]
        if not value_columns:
            continue
        values: list[Any] = []
        row = table + 2
        while row < len(lines) and lines[row].startswith("|"):
            cells = _split_row(lines[row])
            row += 1
            if len(cells) != len(header):
                continue
            for column in value_columns:
                value = _enum_scalar(cells[column])
                if value is not None and value not in values:
                    values.append(value)
        if values:
            found[paths[0]] = values
    return found


def _apply_enum_values(tables: list[ParsedTable], values_by_path: dict[str, list[Any]]) -> None:
    """Attach manual enum values to their exact field, including nested paths."""

    by_path: dict[str, ParsedField] = {}

    def walk(fields: list[ParsedField], prefix: str = "") -> None:
        for field in fields:
            path = f"{prefix}.{field.key}" if prefix else field.key
            by_path[path] = field
            walk(field.properties, path)

    for table in tables:
        walk(table.fields)

    for path, values in values_by_path.items():
        field = by_path.get(path)
        if field is None:
            continue
        if field.enum and field.enum != values:
            field.notes.append(
                f"the manual gives conflicting inline and table enum values for {path!r}; review both"
            )
            continue
        field.enum = values
        if _ENUM_VALUES_ELSEWHERE in field.notes:
            field.notes.remove(_ENUM_VALUES_ELSEWHERE)


_RANGE_JOINED_KEYS = re.compile(r'\s*"?[A-Za-z_]\w*"?\s*[~∼]\s*"?[A-Za-z_]\w*"?\s*')


def _parallel_cells(cell: str, count: int, *, key: bool = False) -> Optional[list[str]]:
    """Split a manual row only when it explicitly gives one value per field.

    The manual sometimes compresses independent keys into one row, using
    matching slash-separated Value Type, Default and Required cells. It is safe
    to restore those separate fields only when every column that makes a claim
    has the same cardinality. A singleton such as ``Optional`` beside two keys
    could apply to either key or both, so it deliberately returns ``None``.
    """

    text = _clean(cell)
    if key:
        quoted = re.findall(r'"([^"\\]+)"', text)
        if len(quoted) == count:
            return quoted
    parts = [part.strip().strip('"') for part in re.split(r"\s*/\s*", text)]
    if len(parts) != count or any(not part for part in parts):
        return None
    # ``Array [Number,4]/[Number,3]`` omits the repeated ``Array`` word in
    # the second half, but its brackets make the repeated form explicit.
    if parts[0].lower().startswith("array ["):
        parts = [part if index == 0 or not part.startswith("[") else f"Array {part}" for index, part in enumerate(parts)]
    return parts


def _parallel_field_cells(
    key_cell: str,
    type_cell: Optional[str],
    default_cell: Optional[str],
    required_cell: Optional[str],
    number: str,
    *,
    allow_shared_slash: bool = False,
    allow_shared_default_required: bool = False,
) -> Optional[list[tuple[str, Optional[str], Optional[str], Optional[str]]]]:
    """Return exact parallel field columns, or ``None`` when a row is ambiguous."""

    raw_key = _clean(key_cell)
    # ``"W_R" ~ "HE_B"`` names the two ends of an interval, not two keys.
    # Read as a parallel pair it silently drops the seven `/db/CO_S` colour
    # components between them. Only the section's JSON Schema can say what an
    # interval contains, so leave the row whole for _expand_range_row.
    if _RANGE_JOINED_KEYS.fullmatch(raw_key):
        return None
    braced = re.fullmatch(r"(.+?)\.\{([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)+)\}", raw_key)
    braced_keys = (
        [f"{braced.group(1)}.{name.strip()}" for name in braced.group(2).split(",")]
        if braced
        else []
    )
    quoted = re.findall(r'"([^"\\]+)"', raw_key)
    if len(quoted) < 2:
        # Chapter 14 writes the same compact notation with backticks rather
        # than double quotes - `BEAM_CORE_DIV_Y` / `BEAM_CORE_DIV_Z`. That is a
        # typography difference, not a different claim, and the shared-claim
        # branch below is gated on the key being quoted literally at all, so
        # reading only one form left the `/db/POGD` fibre-model rows and their
        # siblings unparseable - which is what blocked that contract.
        quoted = re.findall("`([^`]+)`", key_cell)
    keys = braced_keys or (quoted if len(quoted) > 1 else _parallel_cells(raw_key, 2, key=True))
    if not keys or len(keys) < 2:
        return None
    columns = [type_cell, default_cell, required_cell]
    if allow_shared_slash:
        return [
            (
                key,
                _clean(type_cell) if type_cell is not None else None,
                _clean(default_cell) if default_cell is not None else None,
                _clean(required_cell) if required_cell is not None else None,
            )
            for key in keys
        ]
    parts: list[Optional[list[str]]] = []
    for column_index, cell in enumerate(columns):
        if cell is None:
            parts.append(None)
            continue
        split = _parallel_cells(cell, len(keys))
        if split is None:
            # `/db/STCT` writes three independently typed stress-decrease
            # controls in one row, while its one Default and Required cells
            # apply to the row as a whole. This opt-in repeats only those two
            # shared claims; the Value Type column must still map one-for-one.
            if allow_shared_default_required and column_index in {1, 2}:
                parts.append([_clean(cell)] * len(keys))
                continue
            # A row such as ``"R" "G" "B" | Integer | 0 | Optional``
            # names several literal wire keys but gives one *shared* claim in
            # every other column. That is different from ``String / Integer |
            # Optional``: there the singleton Required value cannot safely be
            # assigned to either differently typed key. The former is an exact
            # compact table notation for homogeneous vector components, so
            # repeat its complete shared claim for every literal key. A
            # key/description/type-only child table also makes this unambiguous:
            # it has no Default or Required columns that could vary by key.
            may_share = (
                (len(quoted) == len(keys) or bool(braced_keys))
                and (
                    "/" not in raw_key
                    or allow_shared_slash
                    or _NUMBER_CHILD.match(_clean(number)) is not None
                    or (default_cell is None and required_cell is None)
                )
                and (allow_shared_slash or "/" not in _clean(cell))
            )
            if may_share:
                parts.append([_clean(cell)] * len(keys))
                continue
            return None
        parts.append(split)
    return [
        (
            key,
            parts[0][index] if parts[0] else None,
            parts[1][index] if parts[1] else None,
            parts[2][index] if parts[2] else None,
        )
        for index, key in enumerate(keys)
    ]


# These rows name several distinct properties and then state one homogeneous
# claim for all of them. They cannot be inferred from punctuation alone:
# `/db/THIS-M1` uses the same slash form for mutually exclusive alternative
# names. Each entry below was reviewed against the row's own Description in
# the official manual, which maps the names positionally (lane 1/2/3+, or
# minimum/maximum) and never describes them as alternatives.
_REVIEWED_SHARED_COMPACT_KEYS = {
    ("/db/MVLDeu", 'SCALE_FACTOR1"/"SCALE_FACTOR2"/"SCALE_FACTOR3'),
    ("/db/MVLDeu", 'MULTI_FACTOR1"/"MULTI_FACTOR2"/"MULTI_FACTOR3'),
    ("/db/MVLDeu", 'MIN_NUM_VHL"/"MAX_NUM_VHL'),
    ("/db/STCT", 'iT10" / "iT100" / "iT1K" / "iT5K" / "iT10K'),
}


_REVIEWED_SHARED_DEFAULT_REQUIRED_KEYS = {
    ("/db/STCT", 'bSD" / "iSDOPT" / "SDCONST'),
    ("/db/STCT", 'bENEG" / "EV'),
    ("/db/STCT", 'bDISP" / "DV'),
    ("/db/STCT", 'bFORC" / "FV'),
    ("/db/STCT", 'bTTLE_ES" / "iTTLE_ES'),
}


_QUOTED_ARRAY_PROPERTY = re.compile(
    r'^"([A-Za-z_][A-Za-z0-9_]*)"\[\]\.(?:"?)([A-Za-z_][A-Za-z0-9_]*)(?:"?)$'
)
#: A whole-line bold label introducing a parameter table, optionally followed
#: by nothing but a link to the official article it transcribes. The nine
#: country objects in ch08's /db/MVHL section are labelled that way -
#: ``**VEH_AU (Australia, `STANDARD_CODE: "AUSTRALIA"`)** - [원문](...)`` - and
#: requiring the line to end at the closing ``**`` skipped every one of them,
#: so five tables inherited whatever heading came before. Measured across the
#: manual: the trailing-link form occurs five times and is a table label every
#: time. Prose with bold emphasis still fails, because the label must be the
#: whole line up to that link.
_BOLD_TABLE_LABEL = re.compile(
    r"^\*\*(?P<label>.+?)\*\*\s*(?:\*\([^)]*\)\*\s*)?"
    r"(?:[-–—]\s*\[[^\]]*\]\([^)]*\)\s*)?$"
)


def _canonical_wire_property(cell: str) -> str:
    """Transcribe a quoted array-member path into the contract's path syntax.

    The manual writes both ``"POINT"[].ITEM"`` and
    ``"SPAN_BASE_ITEMS"[].ELEM_KEY"``. Quotes decorate literal property
    tokens; they are not wire characters. Preserve every other key spelling so
    an unfamiliar decoration still reaches the review gate.
    """

    text = _clean(cell)
    match = _QUOTED_ARRAY_PROPERTY.fullmatch(text)
    if match:
        return f"{match.group(1)}[].{match.group(2)}"
    return text.strip('"')


def _key_cell_annotation(cell: str) -> tuple[str, str]:
    """Separate a literal Key from values documented in the same cell.

    Chapter 14's supplementary tables sometimes use the Key column as a
    compact ``KEY · choices`` column, for example
    ``RCDGNCODE · "KISTEC2019" / "MOE2019"``.  The text after the middle dot
    describes values of the first property; it is not a list of additional
    wire properties.  Require one literal code span before the separator so
    ordinary prose containing a middle dot is left untouched.
    """

    match = re.fullmatch(r"\s*(`[^`]+`)\s*·\s*(\S.*)", cell)
    if match is None:
        return cell, ""
    return match.group(1), match.group(2).strip()


def _tree_scope(cell: str, scope: dict) -> tuple | None:
    """The running `└`-tree path of a row, or None if it carries no marker.

    Duplicate suppression needs a scope, and a tree-marked table gives it one
    the No. column cannot: the ancestors a row sits under. The marker repeats
    once per level, so counting glyphs is the depth; recording the key at that
    depth and discarding anything deeper keeps `scope` a live path from the
    table's roots down to this row.

    Two rows are the same field only when their whole path matches, which is
    what lets `NAME` recur under LAYER1 and LAYER2, under TOP and BOT, and
    under three bar sectors, without the later ones being read as repeats of
    the first.
    """
    depth = cell.count("└")
    key = _canonical_wire_property(cell)
    if not depth:
        # A root row opens a new path rather than clearing one. It has to stay
        # in the scope: BAR_SECTOR_I, _M and _J each hold the identical
        # TOP/LAYER1/NAME subtree, and a path that started below the sector
        # would make the second and third sectors repeats of the first.
        scope.clear()
        scope[0] = key
        return None
    scope[depth] = key
    for deeper in [level for level in scope if level > depth]:
        del scope[deeper]
    return tuple(scope[level] for level in sorted(scope))


def _number_parent(number: str) -> str:
    """Return the documented parent number for a dotted or dashed child row."""

    text = _clean(number)
    if not _NUMBER_PATH.fullmatch(text):
        return ""
    return re.sub(r"[-.](?:\d+|\(\d+\))$", "", text)


def _parse_tables(lines: list[str], offset: int, endpoint: str = "") -> list[ParsedTable]:
    tables: list[ParsedTable] = []
    heading = ""
    index = 0
    fenced = False
    while index < len(lines):
        line = lines[index]
        # A `#` inside a fenced block is a comment in whatever language the
        # block is, not a Markdown heading. Reading them as headings gave five
        # of ch08's country tables the heading of the *previous* country's
        # Python example - `# Canada 표준 차량 ...` sat above the Australia
        # table - so a contract drafted from it would have cited the wrong
        # source for the right fields.
        if line.lstrip().startswith("```"):
            fenced = not fenced
            index += 1
            continue
        if fenced:
            index += 1
            continue
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
            index += 1
            continue
        # Supplementary parameter tables are sometimes introduced by a bold
        # label rather than a Markdown heading. Only take a *whole* bold line
        # when the next nonblank line is a parameter table. This deliberately
        # ignores prose with bold emphasis (for example ``... **Required**``)
        # and bold Request/Response labels that introduce code blocks.
        label = _BOLD_TABLE_LABEL.fullmatch(line.strip())
        if label:
            # Some manual labels carry an advisory blockquote before their
            # table (TDNA's 2D Round profile is one). Keep that label only
            # when a parameter table follows before another heading, another
            # bold label, or a code fence; this still excludes bold prose that
            # introduces an example rather than a table.
            probe = index + 1
            table_follows = False
            while probe + 1 < len(lines):
                candidate = lines[probe]
                if (
                    candidate.startswith("#")
                    or candidate.lstrip().startswith("```")
                    or _BOLD_TABLE_LABEL.fullmatch(candidate.strip())
                ):
                    break
                if candidate.startswith("|") and _DIVIDER.match(lines[probe + 1]):
                    table_follows = True
                    break
                probe += 1
            if table_follows:
                heading = _clean(label.group("label"))
            index += 1
            continue
        if not (line.startswith("|") and index + 1 < len(lines) and _DIVIDER.match(lines[index + 1])):
            index += 1
            continue

        header = [cell.lower() for cell in _split_row(line)]
        key_column = next((i for i, h in enumerate(header) if h in _KEY_COLUMNS), None)
        if key_column is None:
            index += 1
            continue

        desc_column = next((i for i, h in enumerate(header) if h in _DESC_COLUMNS), None)
        type_column = next((i for i, h in enumerate(header) if h in _TYPE_COLUMNS), None)
        default_column = next((i for i, h in enumerate(header) if h in _DEFAULT_COLUMNS), None)
        required_column = next((i for i, h in enumerate(header) if h in _REQUIRED_COLUMNS), None)
        # Two /view tables put their rows under a mode or group column, and a
        # row's "Required" holds only within its own group: /view/ACTIVE's
        # N_LIST is required in "Active" mode and absent from "All", and
        # /view/CAPTURE's FIGURE_NAME belongs to "Smart Report" only. Read
        # flat, every such row looked required in every mode - which would
        # refuse `{"ACTIVE_MODE": "All"}`.
        group_column = next((i for i, h in enumerate(header) if h in _GROUP_COLUMNS), None)
        key_groups: dict[str, set[str]] = {}

        fields: list[ParsedField] = []
        seen: set[tuple[str, str]] = set()
        # The `└`-tree path of the row last read, per table and per inline
        # variant, so a repeated key is only suppressed under the same parents.
        scope: dict[int, str] = {}
        inline_variants: list[tuple[str, int, list[ParsedField], set[tuple[str, str]]]] = []
        target_fields = fields
        target_seen = seen
        target_scope = scope
        # The plain-numbered row a `(n)` child row sits under. `_number_parent`
        # only understands dotted and dashed numbers, so a `(1)` row used to
        # have no parent at all and shared the table-wide scope with the top
        # level: a nested key that repeated any earlier field's name was taken
        # for a duplicate and dropped. That is how /db/EFCT lost
        # `COMB_LIST[].LCNAME` (a root `LCNAME` sits two rows above) and
        # /db/STAG lost `DACT_ELEM[].GRUP_NAME` (`ACT_ELEM` has one first).
        numbered_parent = ""
        row = index + 2
        while row < len(lines) and lines[row].startswith("|"):
            cells = _split_row(lines[row])
            row += 1
            if len(cells) != len(header):
                continue
            key_cell, key_annotation = _key_cell_annotation(cells[key_column])
            key = _canonical_wire_property(key_cell)
            if not key or key in _EMPTY_CELLS:
                # Some manual tables use a blank-key row as an inline section
                # divider, e.g. ``General Load (OPT_AUTO_OPTIMIZE=false)``.
                # It is a variant only when it names one literal wire
                # discriminator. Keep each branch separate so repeated field
                # names are not flattened or deduplicated together.
                # Chapters put this divider in either the No. or Description
                # column, so inspect every non-key cell rather than assuming
                # one column layout.
                condition_text = next(
                    (
                        cell
                        for cell_index, cell in enumerate(cells)
                        if cell_index != key_column and _variant_condition(_clean(cell)) is not None
                    ),
                    "",
                )
                if _variant_condition(_clean(condition_text)) is not None:
                    target_fields = []
                    target_seen = set()
                    target_scope = {}
                    inline_variants.append(
                        (_clean(condition_text), offset + row, target_fields, target_seen)
                    )
                continue
            parallel = _parallel_field_cells(
                key_cell,
                cells[type_column] if type_column is not None else None,
                cells[default_column] if default_column is not None else None,
                cells[required_column] if required_column is not None else None,
                cells[0] if cells else "",
                allow_shared_slash=(endpoint, _clean(key_cell).strip('"'))
                in _REVIEWED_SHARED_COMPACT_KEYS,
                allow_shared_default_required=(endpoint, _clean(key_cell).strip('"'))
                in _REVIEWED_SHARED_DEFAULT_REQUIRED_KEYS,
            )
            entries = parallel or [
                (
                    key,
                    cells[type_column] if type_column is not None else None,
                    cells[default_column] if default_column is not None else None,
                    cells[required_column] if required_column is not None else None,
                )
            ]
            for entry_key, entry_type, entry_default, entry_required in entries:
                entry_key = _corrected_key(endpoint, entry_key, entry_type)
                # ``CONCRETE.CODE`` and ``REBAR.CODE`` are different wire
                # paths even though they share the last token. Only suppress
                # a duplicate in the same numbered object scope.
                #
                # A table that nests with `└` markers instead of a No. column
                # has no numbered scope at all, so this used to collapse to the
                # bare key and drop every repeat anywhere in the table. That is
                # exactly what a rebar table is: `NAME` and `NUM` recur under
                # LAYER1 and LAYER2, under TOP and BOT, under three bar sectors.
                # 53 rows across ch27 were lost that way, 40 of them from
                # /DESIGN/SRC/AIK-SRC2K/MRBD, which kept 14 of its 54 paths and
                # was held out of the source of truth for it. The running tree
                # path is the scope those rows do have.
                tree_scope = _tree_scope(cells[0] if cells else "", target_scope)
                number = _clean(cells[0]) if cells else ""
                if re.fullmatch(r"\d+", number):
                    numbered_parent = number
                parent = (
                    numbered_parent
                    if re.fullmatch(r"\(\d+\)", number)
                    else _number_parent(number)
                )
                entry_identity = (
                    tree_scope if tree_scope is not None else (parent, entry_key)
                )
                # A child row (`12-1`) leaves the group cell blank and belongs
                # to its parent's group; only a named group counts.
                if group_column is not None and _clean(cells[group_column]):
                    key_groups.setdefault(entry_key, set()).add(_clean(cells[group_column]))
                if entry_identity in target_seen:
                    continue
                target_seen.add(entry_identity)

                notes: list[str] = []
                if entry_required is not None:
                    requirement, condition, note = _normalize_requirement(entry_required)
                else:
                    requirement, condition, note = None, None, None
                # Some chapters put only "conditional required" in the
                # Required column but spell the one literal selector in the
                # Description cell.  Preserve that exact condition when there
                # is precisely one; two selectors or prose-only wording stay
                # unresolved rather than being guessed.
                if requirement == "conditional" and condition is None and desc_column is not None:
                    negated = _condition_negates(cells[desc_column])
                    description_condition = (
                        None if negated else _description_literal_condition(cells[desc_column])
                    )
                    if description_condition is not None:
                        condition_field, condition_values = description_condition
                        rendered_value = " or ".join(
                            json.dumps(value) if isinstance(value, str) else str(value).lower()
                            for value in condition_values
                        )
                        condition = f"{condition_field}={rendered_value}"
                        applies_when = [(condition_field, condition_values)]
                        note = None
                    elif negated:
                        condition = (
                            _negated_condition_phrase(cells[desc_column])
                            or _condition_from_description(cells[desc_column])
                        )
                        if condition is not None:
                            note = (
                                "the manual states this condition negatively - it names the "
                                f"value at which the field does not apply ({condition}), so the "
                                "equality in it must not be read as an appliesWhen. Write the "
                                "appliesWhen by hand, and only where the manual states the "
                                "field's full value set"
                            )
                        applies_when = []
                    else:
                        condition = _condition_from_description(cells[desc_column])
                        if condition is not None:
                            note = None
                        applies_when = []
                else:
                    applies_when = []
                if note:
                    notes.append(note)
                field_type, items, note = _normalize_type(entry_type) if entry_type is not None else (None, None, None)
                if note:
                    notes.append(note)
                enum = _enum_values_from_inline_type(entry_type) if entry_type is not None else []
                if not enum and note == _ENUM_VALUES_ELSEWHERE and desc_column is not None:
                    enum = _enum_values_from_description(cells[desc_column])
                if not enum and key_annotation:
                    enum = _enum_values_from_description(key_annotation)
                if enum and _ENUM_VALUES_ELSEWHERE in notes:
                    notes.remove(_ENUM_VALUES_ELSEWHERE)
                constraints = _type_constraints(entry_type) if entry_type is not None else {}
                default, note = _normalize_default(entry_default) if entry_default is not None else (None, None)
                # A prose Default cell (for example ``System`` or ``Auto``)
                # establishes that the manual names a default, but not that it
                # names a literal wire value. Preserve the exact source text
                # separately instead of treating it as a value or a blocking
                # review note. A same-section JSON Schema default can later
                # confirm the literal and clear this note.
                default_note = default if note and note.startswith("non-literal default ") else None
                if default_note is not None:
                    default = None
                elif note:
                    notes.append(note)
                type_default = _type_default(entry_type) if entry_type is not None else None
                if default is None and type_default is not None:
                    default = type_default
                elif type_default is not None and default != type_default:
                    notes.append(
                        f"the Default column says {default!r}, but the Value Type cell says {type_default!r}"
                    )
                target_fields.append(
                    ParsedField(
                        key=entry_key,
                        description=(
                            " — ".join(
                                part
                                for part in (
                                    _DESC_TREE.sub("", _clean(cells[desc_column])).strip()
                                    if desc_column is not None
                                    else "",
                                    _clean(key_annotation),
                                )
                                if part
                            )
                        ),
                        type=field_type,
                        items=items,
                        requirement=requirement,
                        documented_default=default,
                        documented_default_note=default_note,
                        enum=enum,
                        constraints=constraints,
                        condition=condition,
                        applies_when=applies_when,
                        number=_clean(cells[0]) if cells else "",
                        notes=notes,
                        shared_number_group=parallel is not None,
                        default_column_missing=default_column is None,
                    )
                )

        if group_column is not None:
            every_group = set().union(*key_groups.values()) if key_groups else set()
            label = header[group_column]
            for parsed in fields:
                groups = key_groups.get(parsed.key, every_group)
                if parsed.requirement == "required" and groups != every_group:
                    parsed.requirement = "conditional"
                    parsed.condition = f"{label}: " + " or ".join(sorted(groups))
        if fields:
            tables.append(
                ParsedTable(
                    heading=heading or "(unlabelled table)",
                    line=offset + index + 1,
                    fields=_nest(fields),
                    missing_columns=["Default"] if default_column is None else [],
                )
            )
        for variant_heading, variant_line, variant_fields, _ in inline_variants:
            if variant_fields:
                tables.append(
                    ParsedTable(
                        heading=variant_heading,
                        line=variant_line,
                        fields=_nest(variant_fields),
                        missing_columns=["Default"] if default_column is None else [],
                    )
                )
        index = row
    return tables


_TOC_METHOD_COLUMNS = {"methods", "active methods", "메서드"}
_TOC_NAME_COLUMNS = {"function", "feature", "description", "name", "기능", "설명"}


def _toc_metadata(lines: list[str]) -> dict[str, tuple[list[str], str]]:
    """Read labels and, where present, methods from a chapter's contents table.

    15 chapters state each endpoint's verbs once, in the table of contents,
    rather than in the endpoint's own section. Without this the extractor falls
    back to the /db/* default of all four verbs, which is how /db/GRUP's first
    draft claimed a DELETE the endpoint does not serve.

    The same tables carry the manual's human-readable resource labels in
    chapters whose endpoint headings are deliberately terse. A methods column
    is therefore optional here: several chapters have a label but no verbs.
    """
    found: dict[str, tuple[list[str], str]] = {}
    for index, line in enumerate(lines):
        if not (line.startswith("|") and index + 1 < len(lines) and _DIVIDER.match(lines[index + 1])):
            continue
        header = [cell.lower() for cell in _split_row(line)]
        if "endpoint" not in header:
            continue
        method_column = next((i for i, h in enumerate(header) if h in _TOC_METHOD_COLUMNS), None)
        name_column = next((i for i, h in enumerate(header) if h in _TOC_NAME_COLUMNS), None)
        if method_column is None and name_column is None:
            continue
        endpoint_column = header.index("endpoint")
        row = index + 2
        while row < len(lines) and lines[row].startswith("|"):
            cells = _split_row(lines[row])
            row += 1
            if len(cells) != len(header):
                continue
            endpoint = re.search(r"/?[A-Za-z][A-Za-z0-9/_.\-]*/[A-Za-z0-9/_.\-]+", _clean(cells[endpoint_column]))
            if not endpoint:
                continue
            verbs = (
                sorted(
                    {
                        v
                        for v in re.findall(r"[A-Z]+", cells[method_column])
                        if v in {"GET", "POST", "PUT", "DELETE"}
                    }
                )
                if method_column is not None
                else []
            )
            title = _clean(cells[name_column]) if name_column is not None else ""
            path = endpoint.group(0)
            found[path if path.startswith("/") else "/" + path] = (verbs, title)
    return found


_STATED_MEMBER_COUNT = re.compile(r"(\d+)\s*(?:종|개|가지)")
_STATED_VALUE_RANGE = re.compile(r"([A-Za-z]*\d+(?:\.\d+)?)\s*[~∼]\s*([A-Za-z]*\d+(?:\.\d+)?)")


def _sampled_enum_reason(field: ParsedField) -> Optional[str]:
    """Say why this list is illustrative, or None when it is the whole enum."""

    values = field.enum or []
    description = field.description or ""
    if any(isinstance(value, str) and "..." in value for value in values):
        return (
            "the manual's list ends in an ellipsis, so it is a sample; no enum is "
            "transcribed and the field keeps its declared type"
        )
    stated = _STATED_MEMBER_COUNT.search(description)
    if stated and int(stated.group(1)) != len(values):
        return (
            f"the manual's own description says this has {stated.group(1)} values and lists "
            f"{len(values)}; the list is a sample, so no enum is transcribed"
        )
    spelt = {str(value) for value in values}
    for first, last in _STATED_VALUE_RANGE.findall(description):
        if first not in spelt or last not in spelt:
            return (
                f"the manual's own description spans {first} to {last} and the list omits an "
                f"end of that range; it is a sample, so no enum is transcribed"
            )
    return None


def _enum_signature(values: list[Any]) -> tuple[tuple[str, Any], ...]:
    """Identify one enum list, keeping ``True`` and ``1`` apart."""

    return tuple((type(value).__name__, value) for value in values)


def _drop_sampled_enums(tables: list[ParsedTable]) -> None:
    """Discard an enum the section says is only a sample.

    `/DESIGN/RC/KDS-41-20-2022/DCRM-BEAM` describes `MAIN_REBAR` as
    "19종 (D4 ~ D57)" while the section's JSON Schema lists five values. The
    schema is illustrating, not enumerating, and adopting it published a
    TypeScript union that made every bar size from D10 up untypeable.

    A count the manual states about its own list is the manual contradicting
    itself, so neither half can be trusted as complete: keep the description,
    which says how many there are, and drop the list, which does not have them.
    The field stays its declared scalar type, which is wide enough for all of
    them.

    The sentence that says so is not attached to every copy. Chapter 26 heads
    each section with "아래는 앞 5개만 표기합니다" and then writes the identical
    five rebar sizes on fields with a description that repeats the count and on
    fields, such as REBB's `NAME`, with no description at all. It is one list
    abbreviated once, so a list already proven to be a sample in this section
    is a sample everywhere this section writes it. Reading each field alone
    would publish the abbreviation on exactly the fields the manual forgot to
    annotate.
    """

    fields = [field for table in tables for field in _walk(table.fields) if field.enum]
    reasons = {id(field): _sampled_enum_reason(field) for field in fields}
    witnesses: dict[tuple[tuple[str, Any], ...], str] = {}
    for field in fields:
        if reasons[id(field)] is not None:
            witnesses.setdefault(_enum_signature(field.enum), field.key)
    for field in fields:
        reason = reasons[id(field)]
        if reason is None:
            witness = witnesses.get(_enum_signature(field.enum))
            if witness is None:
                continue
            reason = (
                f"this section writes the same list for {witness!r}, whose own description "
                "says that list is a sample; no enum is transcribed"
            )
        field.enum = None
        field.notes.append(reason)


def _schema_only_roots(
    tables: list[ParsedTable], hints: dict[tuple[str, ...], list[dict[str, Any]]]
) -> tuple[str, ...]:
    """Root properties the section's JSON Schema declares and its table omits.

    A chapter states its request twice - once as a Specifications table and
    once as a JSON Schema - and where they disagree the table is the lossy
    one. `/db/FIMP` is the case that shipped: its schema names `CONC` and
    `STEEL`, its table names neither, and the contract drafted from the table
    declared a three-level object as ten flat top-level fields.

    A root the schema names and the table never mentions is therefore evidence
    that the table is not the whole request, and a contract built from it would
    be incomplete in a way nobody could see. Report it rather than repairing
    it: which rendering is right, and how the two reconcile, is a review
    decision.
    """

    declared = [
        path[0]
        for path, entries in hints.items()
        if len(path) == 1
        and any(any(not key.startswith("__") for key in entry) for entry in entries)
    ]
    named = {field.key for table in tables for field in _walk(table.fields)}
    return tuple(dict.fromkeys(root for root in declared if root not in named))


_TITLE_ONLY_SECTION = re.compile(r"^##\s+(\d+)\.\s+(\S.*?)\s*$")
_INPUT_URI = re.compile(r"^\{base url\}(/[A-Za-z0-9/_.\-]+)\s*$")
SHARED_TABLE_ROUTE = "/post/TABLE"


def _own_route_lines(lines: list[str]) -> tuple[list[str], dict[int, str]]:
    """A table-family chapter, reduced to the sections with a route of their own.

    Chapters 18-23 title a section by what it returns ("## 1. P-M Interaction
    Diagram") and state its route only in an `### Input URI` block. Almost all
    of those routes are the shared `/post/TABLE`, which is a table contract,
    not an endpoint one - but chapter 23 opens with two that are not,
    `/post/PM` and `/post/STEELCODECHECK`, and skipping the whole chapter left
    them with no draft and so no contract.

    Returns the chapter with every other line blanked, so line numbers stay
    true for `extraction.source`, and each kept heading rewritten into the
    `## N. `/route` — Title` form `parse_chapter` reads. The original heading
    text is returned beside it, keyed by line, because that is what a contract
    must cite.
    """
    starts = [index for index, line in enumerate(lines) if line.startswith("## ")]
    kept = [""] * len(lines)
    headings: dict[int, str] = {}
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        match = _TITLE_ONLY_SECTION.match(lines[start])
        if match is None:
            continue
        body = lines[start + 1 : end]
        route = None
        for index, line in enumerate(body):
            if line.startswith("### Input URI"):
                for candidate in body[index + 1 :]:
                    uri = _INPUT_URI.match(candidate.strip())
                    if uri:
                        route = uri.group(1)
                        break
                    if candidate.startswith("###"):
                        break
                break
        if route is None or route == SHARED_TABLE_ROUTE:
            continue
        kept[start] = f"## {match.group(1)}. `{route}` — {match.group(2)}"
        kept[start + 1 : end] = body
        headings[start] = lines[start].lstrip("#").strip()
    return kept, headings


def parse_chapter(path: Path, *, own_routes_only: bool = False) -> list[Section]:
    lines = path.read_text(encoding="utf-8").splitlines()
    original_headings: dict[int, str] = {}
    if own_routes_only:
        lines, original_headings = _own_route_lines(lines)
    toc_metadata = _toc_metadata(lines)
    starts: list[tuple[int, re.Match[str]]] = []
    for index, line in enumerate(lines):
        match = _SECTION.match(line)
        if match:
            starts.append((index, match))

    sections: list[Section] = []
    for position, (index, match) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        body = lines[index + 1 : end]
        endpoint = match.group(2)
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        title = (match.group(3) or "").strip()
        toc_methods, toc_title = toc_metadata.get(endpoint, ([], ""))
        if not title:
            # Name precedence follows the manual's increasingly indirect
            # evidence: section heading, then opening blockquote, then chapter
            # contents table. Each later form only fills a missing label.
            # Only inspect introductory metadata, so a bold note in
            # Specifications cannot become the endpoint name.
            for line in body:
                if line.startswith("###"):
                    break
                blockquote_title = _BLOCKQUOTE_TITLE.match(line)
                if blockquote_title:
                    title = blockquote_title.group(1).strip()
                    break
        if not title:
            title = toc_title

        section = Section(
            chapter_file=path.name,
            number=match.group(1),
            endpoint=endpoint,
            title=title,
            heading=original_headings.get(index, lines[index].lstrip("#").strip()),
            lines=body,
        )
        text = "\n".join(body)
        url = _SOURCE_URL.search(text)
        if url:
            section.source_url = url.group(1)
        section.methods = _section_methods(body)
        if not section.methods:
            section.methods = toc_methods
        section.tables = _parse_tables(body, index, section.endpoint)
        _apply_enum_values(section.tables, _enum_tables(body))
        schema_hints = _section_schema_hints(body, section.endpoint)
        section.schema_hints = schema_hints
        _reconcile_schema_compact_key_rows(section.tables, schema_hints)
        _expand_schema_named_compact_rows(section.tables, schema_hints)
        _apply_schema_hints(section.tables, schema_hints)
        _apply_explicit_prose_conditions(section.tables, body)
        _drop_sampled_enums(section.tables)
        section.schema_only_roots = _schema_only_roots(section.tables, schema_hints)
        section.variants = _explicit_variants(section.tables)
        sections.append(section)
    return sections


def _merge_signature(field: ParsedField, ignore: str) -> tuple:
    """Everything two sections must agree on for one field to be the same field.

    `ignore` excuses the one field a shared route is allowed to differ on: its
    description and its enum, and nothing else about it.
    """
    return (
        field.key,
        "" if field.key == ignore else field.description,
        field.type,
        repr(field.items),
        field.requirement,
        repr(field.documented_default),
        field.documented_default_note,
        () if field.key == ignore else tuple(repr(value) for value in field.enum),
        repr(sorted(field.constraints.items())),
        field.condition,
        tuple(field.applies_when),
        field.number,
        tuple(field.notes),
        field.products,
        field.shared_number_group,
        field.default_column_missing,
        tuple(_merge_signature(child, ignore) for child in field.properties),
    )


def _tables_agree(left: Section, right: Section, ignore: str = "") -> bool:
    """Do two sections describe the same request, excusing one enum field?

    Headings and line numbers are deliberately not compared. The same table in
    two sections sits at two different lines, and that is not a disagreement
    about the endpoint.
    """
    if left.methods != right.methods or len(left.tables) != len(right.tables):
        return False
    for one, other in zip(left.tables, right.tables):
        if tuple(one.missing_columns) != tuple(other.missing_columns):
            return False
        if [_merge_signature(f, ignore) for f in one.fields] != [
            _merge_signature(f, ignore) for f in other.fields
        ]:
            return False
    return True


def _shared_route_discriminator(group: list[Section]) -> Optional[str]:
    """The single field whose documentation is all that tells these sections apart.

    Both chapters that do this state the value differently - the RC chapter
    gives `TABLE_TYPE` a one-value enum column, the SRC chapter writes the
    value into the description as "가능값" prose - so the candidate is any
    top-level field, not only one already carrying an enum. That costs nothing
    in safety: excusing a field that does not differ leaves the real difference
    in place, so at most one key can ever explain a group.

    Searched at the top level only. A nested field could in principle play the
    same role, but nothing in the manual does it, and widening the search would
    make a wrong fold easier to reach than a right one.
    """
    first = group[0]
    candidates = dict.fromkeys(
        field.key for table in first.tables for field in table.fields
    )
    explains = [
        key for key in candidates
        if all(_tables_agree(first, other, key) for other in group[1:])
    ]
    return explains[0] if len(explains) == 1 else None


def _fold_discriminated(group: list[Section], key: str) -> Section:
    """One section for one route, with the discriminator's values unioned.

    Every section states its own value as fixed. The merged field keeps all of
    their descriptions, joined, because "one of three" is a thing the manual
    never says and the contract should not start saying on its behalf.
    """
    values: list[Any] = []
    descriptions: list[str] = []
    for section in group:
        for table in section.tables:
            for field in table.fields:
                if field.key != key:
                    continue
                values += [value for value in field.enum if value not in values]
                if field.description and field.description not in descriptions:
                    descriptions.append(field.description)
    description = " / ".join(descriptions)
    tables = [
        ParsedTable(
            heading=table.heading,
            line=table.line,
            fields=[
                replace(field, enum=list(values), description=description)
                if field.key == key else field
                for field in table.fields
            ],
            missing_columns=list(table.missing_columns),
        )
        for table in group[0].tables
    ]
    return replace(
        group[0],
        # Label each section before joining, so the merged name reads as three
        # English labels rather than two labels and a stray parenthetical.
        title=" / ".join(
            dict.fromkeys(_english_label(s.title) or s.title for s in group if s.title)
        ),
        heading=" / ".join(dict.fromkeys(s.heading for s in group)),
        tables=tables,
        merged_sections=tuple(
            (s.heading, s.tables[0].line if s.tables else 0) for s in group
        ),
    )


def merge_shared_endpoint_sections(sections: list[Section]) -> list[Section]:
    """Fold several manual sections documenting one route into one section.

    The RC and SRC design chapters document `/DESIGN/.../TABLE` once per result
    table, and say outright that those sections share a URI and are told apart
    "only" by `Argument.TABLE_TYPE`. Left alone they render to one draft name
    and silently overwrite each other; split into separate ids they would
    invent routes the manual does not describe.

    So fold, but only on the manual's own terms: either the sections agree
    outright, or they agree everywhere except one enumerated field. Anything
    wider is two documents disagreeing about one endpoint, which is a question
    for a person - run_emit reports those rather than averaging them.
    """
    groups: dict[str, list[Section]] = {}
    for section in sections:
        groups.setdefault(section.id, []).append(section)

    folded: dict[str, Section] = {}
    for key, group in groups.items():
        if len(group) == 1:
            continue
        first = group[0]
        origins = tuple(
            (s.heading, s.tables[0].line if s.tables else 0) for s in group
        )
        if all(_tables_agree(first, other) for other in group[1:]):
            folded[key] = replace(first, merged_sections=origins)
            continue
        discriminator = _shared_route_discriminator(group)
        if discriminator is not None:
            folded[key] = _fold_discriminated(group, discriminator)

    if not folded:
        return sections
    result: list[Section] = []
    seen: set[str] = set()
    for section in sections:
        if section.id not in folded:
            result.append(section)
        elif section.id not in seen:
            seen.add(section.id)
            result.append(folded[section.id])
    return result


def load_manual(manual_repo: Path) -> tuple[list[Section], dict[str, int]]:
    manual_dir = manual_repo / "docs" / "manual"
    if not manual_dir.is_dir():
        raise SystemExit(f"ERROR: no manual chapters at {manual_dir}")
    sections: list[Section] = []
    table_family: dict[str, int] = {}
    for path in sorted(manual_dir.glob("*.md")):
        if path.name == "INDEX.md":
            continue
        if path.name in TABLE_FAMILY_CHAPTERS:
            own = parse_chapter(path, own_routes_only=True)
            sections.extend(own)
            table_family[path.name] = sum(
                1 for line in path.read_text(encoding="utf-8").splitlines() if re.match(r"^##\s+\d+\.", line)
            ) - len(own)
            continue
        sections.extend(parse_chapter(path))
    return merge_shared_endpoint_sections(sections), table_family


# ---------------------------------------------------------------------------
# YAML emission. Written by hand rather than through yaml.dump so a draft can
# carry the review markers that make it a draft.
# ---------------------------------------------------------------------------


def _scalar(value: Any) -> str:
    """Render a YAML scalar that reads back as exactly what was passed in.

    Quoting by character class is not enough here. YAML 1.1 resolves bare `NO`,
    `Y`, `ON` and `OFF` to booleans, and `NO` is a real MIDAS field name - it
    appears as a Key in 7 of the manual's parameter tables. Emitting it unquoted
    silently turns a field name into `false`. So the test is a round trip: if
    the bare form does not parse back to the identical string, quote it.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ": "))

    text = str(value)
    quoted = '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if text == "" or text.strip() != text or re.search(r"[:#{}\[\]&*!|>%@`\"']", text):
        return quoted
    try:
        import yaml  # noqa: PLC0415

        if yaml.safe_load(text) != text:
            return quoted
    except Exception:
        return quoted
    return text


@dataclass
class LiveOmission:
    """A payload that a real product accepted, and what it left out."""

    case: str
    endpoint: str
    sent: frozenset[str]
    products: str
    payload: dict[str, Any] = dataclass_field(default_factory=dict)
    product_names: frozenset[str] = frozenset({"gen", "civil"})


def live_omission_evidence() -> dict[str, LiveOmission]:
    """Which fields a confirmed live write actually omitted, per endpoint.

    `scripts/live_crud_check.py` carries cases marked `confirmed=True`, meaning
    someone watched that exact payload complete its supported write/read/delete
    round trip against a running product. A documented field absent from such a
    payload is omission evidence only for the products and conditional branch
    that payload actually exercised.

    Read statically, through `ast`. Importing the checker would be reading an
    SDK to learn about the API; this reads a record of what a server did.

    It proves the call was accepted, not that the resulting model was what the
    engineer wanted - the emitted evidence string says so.
    """
    import ast  # noqa: PLC0415

    checker = ROOT / "scripts" / "live_crud_check.py"
    if not checker.exists():
        return {}

    endpoints: dict[str, str] = {}
    try:
        sys.path.insert(0, str(ROOT / "src"))
        import importlib  # noqa: PLC0415
        import pkgutil  # noqa: PLC0415

        import midas_nx  # noqa: PLC0415
        from midas_nx.db.base import DbResource  # noqa: PLC0415

        for module in pkgutil.walk_packages(midas_nx.__path__, "midas_nx."):
            importlib.import_module(module.name)

        def walk(base: type) -> None:
            for child in base.__subclasses__():
                if getattr(child, "ENDPOINT", None):
                    endpoints[child.__name__] = child.ENDPOINT
                walk(child)

        walk(DbResource)
    except Exception:
        return {}

    found: dict[str, LiveOmission] = {}
    for node in ast.walk(ast.parse(checker.read_text(encoding="utf-8"))):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Case"):
            continue
        keywords = {k.arg: k.value for k in node.keywords}
        confirmed = keywords.get("confirmed")
        if not (isinstance(confirmed, ast.Constant) and confirmed.value is True):
            continue

        resource = node.args[0] if node.args else keywords.get("resource")
        payload = node.args[1] if len(node.args) > 1 else keywords.get("create_payload")
        if resource is None or payload is None:
            continue
        name = getattr(resource, "id", None) or ast.unparse(resource)
        endpoint = endpoints.get(name)
        if endpoint is None or endpoint in found:
            continue
        try:
            literal_payload = ast.literal_eval(payload)
            sent = frozenset(literal_payload.keys())
        except Exception:
            continue

        # An empty create payload is the checker's marker for a record the
        # product creates itself - UNIT, STYP, STYP-M1 and the four CO_*
        # colour defaults, all GET/PUT-only. The POST leg never runs, so
        # nothing was omitted from an accepted call: reading `sent` as "the
        # product accepted every field's absence" turns a skipped request into
        # blanket proof, and marks the whole payload safeToOmit on no evidence
        # at all. That is the /db/NMAS shape exactly - the field whose omission
        # the manual calls Optional and the server dies on.
        if not sent:
            continue

        products = keywords.get("products")
        product_names = frozenset({"gen", "civil"})
        if products is not None:
            try:
                literal_products = ast.literal_eval(products)
            except Exception:
                literal_products = None
            if isinstance(literal_products, (tuple, list, set, frozenset)):
                names = frozenset(value for value in literal_products if isinstance(value, str))
                if names:
                    product_names = names
        found[endpoint] = LiveOmission(
            case=name,
            endpoint=endpoint,
            sent=sent,
            products=ast.unparse(products) if products is not None else "gen and civil",
            payload=literal_payload,
            product_names=product_names,
        )
    return found


#: A finding the permitted sources cannot reopen: the extractor did not fail
#: to answer a question, it answered one. Five kinds qualify so far - how a
#: structure the manual addressed by numbering or a tree marker was rebuilt;
#: why a list the manual's own description outsizes was not transcribed as an
#: enum; a bound `/info` states about the wrong kind of value (MD-12); a
#: value set that lives in a field's description rather than in an `enum`,
#: where the sibling contract drafted from the same prose does the same; and
#: an observation someone made by running the endpoint. None is waiting on a
#: reader, and no permitted source states more about it. They render as
#: `# RESOLVED:` so promotion, which refuses a draft still carrying
#: `# NOTE:`, does not treat a conclusion as a gap.
#:
#: The live-observation one is the widest and the reason it is safe: a live
#: observation is a fact about the product, and no reading of the manual can
#: overturn it. It is not the same as an *answer* - "omitting this was refused
#: for one of the five values this variant covers" settles what was seen and
#: leaves safeToOmit unverified, which is exactly the distinction the two
#: booleans exist for.
#:
#: The sixth is the narrowest: the vendored manual's own callout has already
#: adjudicated the point, so a reader has nothing left to decide. /db/TDME's
#: Russian branch names a `CTYPE` beside the endpoint's top-level `TYPE`, and
#: the chapter says outright that they are different fields carried across as
#: they stand. Repeating that is a conclusion, not a question.
#:
#: The seventh is the same idea one step over: the section's own Request
#: Example answers it. A worked payload is a statement by the same source, in
#: the wire's own grammar, and it is the only thing that places /db/SECT's four
#: SECTTYPE tables - their No. columns number against a table they are not in,
#: so read literally they nest a section's dimensions inside a boolean flag.
#: Citing the example is not a reading of the table; it is preferring the half
#: of the manual that cannot be ambiguous about structure.
_SETTLED_NOTE_MARKERS = (
    "the manual nests this under ",
    "no enum is transcribed",
    "is not transcribed (MD-12)",
    "the values live in the description",
    "measured against a live product",
    "the manual flags it in its own callout",
    "Request Example",
    # The requiredness word was read and the rule after it kept verbatim.
    # There is nothing left for a reviewer to decide: the column answered, and
    # the sentence is about other fields, which no requiredness value can say.
    "adds a cross-field rule to this",
    # A column left something out that the same section supplies elsewhere - a
    # sibling row's description, the section's own JSON Schema, its Request
    # Example. Settled for the same reason those are: the manual answered it,
    # just not in the cell the parser reads.
    "stated elsewhere in the same section",
    "documents the effect of omission",
    # A table and its own section's JSON Schema disagree on integer versus
    # number and nothing in the section breaks the tie. Both renderings are
    # documentation, and the narrower one names a subset of the wider, so a
    # caller following it cannot send a value the other reading refuses.
    # Settled because the choice and its reason are written down; only a live
    # measurement could change it, and that is a new fact, not a review.
    "the narrower of the two documented types",
    # A section omits what its siblings state about the same field. Weaker
    # evidence than the same-section marker above and easier to abuse, so the
    # phrase demands the sibling sections be listed by name rather than
    # gestured at - MD-24 is what happens otherwise: a condition invented from
    # a description column, wearing a marker that claimed evidence nobody had
    # looked for. If you cannot name the sections, you have not found them.
    "stated in these sibling sections:",
    # The server's own schema declares a property and the manual documents it
    # nowhere. Settled because both halves have been established rather than
    # assumed: /info is the product, and "the manual does not say" is a claim
    # about the whole manual, so the phrase is only honest after a search of
    # every chapter - MD-24 is what happens when one section is read instead.
    # It says nothing about requiredness, which stays `unstated`: an /info
    # schema declares no `required` array and the manual made no claim to
    # normalize.
    "declared by /info and absent from the manual",
    # A manual heading names a container and its member table, but not the
    # container's parent. The committed /info baseline can settle that path
    # without saying anything about requiredness or defaults.
    "the nesting is declared by /info",
    # The manual and the server both name this field, and they do not name it
    # the same. Spelling, depth, or both. Settled for the same reason the
    # marker above is - /info is the product - and held to a higher bar than
    # that one, because dropping or renaming a documented field changes a
    # shipped payload type: the phrase belongs only on a field whose contract
    # also carries the matching `describes: field_name` manualDefect, so the
    # manual's claim survives next to the correction instead of vanishing.
    "/info declares this field differently",
)


def _note_marker(note: str) -> str:
    """`RESOLVED` for a finding nothing can change, `NOTE` for a question."""

    return "RESOLVED" if any(marker in note for marker in _SETTLED_NOTE_MARKERS) else "NOTE"


def _block(text: str, indent: str, prefix: str = "") -> list[str]:
    """Wrap `text` at a readable width.

    `prefix` is repeated on every wrapped line, which matters for comments: a
    `# NOTE:` whose continuation lines lose the `#` stops being a comment and
    becomes a YAML parse error.
    """
    words = " ".join(text.split())
    limit = 74 - len(prefix)
    out: list[str] = []
    line = ""
    for word in words.split(" "):
        if line and len(line) + len(word) + 1 > limit:
            out.append(indent + prefix + line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(indent + prefix + line)
    return out


def _render_fields(
    fields: list[ParsedField],
    indent: str,
    evidence: Optional[LiveOmission] = None,
    prefix: tuple[str, ...] = (),
    field_paths: set[str] | None = None,
) -> list[str]:
    """Render fields with appliesWhen paths rooted at the payload record.

    A condition written beside a nested field normally names its sibling
    (``INPUT_METHOD=KEYS``), while a contract path is absolute
    (``PART_A.INPUT_METHOD``). Prefer that sibling path when it exists; retain
    an explicit root reference when the scoped path does not exist. An unknown
    path is deliberately retained for the contract validator to reject.
    """

    if field_paths is None:
        def paths(entries: list[ParsedField], parent: tuple[str, ...] = ()) -> set[str]:
            found: set[str] = set()
            for entry in entries:
                path = parent + (entry.key,)
                found.add(".".join(path))
                found.update(paths(entry.properties, path))
            return found

        field_paths = paths(fields, prefix)
    lines: list[str] = []
    body = indent + "  "

    def condition_was_exercised(parsed: ParsedField) -> bool:
        if evidence is None:
            return False
        for condition_path, values in parsed.applies_when:
            value: Any = evidence.payload
            for part in condition_path.split("."):
                if not isinstance(value, dict) or part not in value:
                    return False
                value = value[part]
            if value not in values:
                return False
        return True

    for parsed in fields:
        current_path = prefix + (parsed.key,)
        lines.append(f"{indent}- key: {_scalar(parsed.key)}")
        if parsed.description:
            lines.append(f"{body}description: >-")
            lines += _block(parsed.description, body + "  ")
        if parsed.products:
            lines.append(f"{body}products: [{', '.join(parsed.products)}]")
        if parsed.type:
            lines.append(f"{body}type: {parsed.type}")
            if parsed.items and parsed.items.get("type"):
                lines.append(f"{body}items:")
                lines.append(f"{body}  type: {parsed.items['type']}")
                if parsed.type == "array" and parsed.enum:
                    lines.append(f"{body}  enum: [{', '.join(_scalar(value) for value in parsed.enum)}]")
        else:
            lines.append(f"{body}type: unstated")
        for key, value in parsed.constraints.items():
            lines.append(f"{body}{key}: {_scalar(value)}")
        lines.append(
            f"{body}requirement: {parsed.requirement}"
            if parsed.requirement
            else f"{body}requirement: unstated"
        )
        if parsed.condition:
            lines.append(f"{body}condition: {_scalar(parsed.condition)}")
        elif parsed.requirement == "conditional":
            lines.append(f"{body}condition: \"TODO(review): the manual does not state the condition\"")
        if parsed.applies_when:
            lines.append(f"{body}appliesWhen:")
            for condition_path, values in parsed.applies_when:
                # Try the field's own scope first, then each shorter one. A
                # condition beside a nested field usually names a sibling, but
                # /db/POGD-M1 writes `DISP.OPT_USE=true일 때 필수` beside
                # ITER_CTRL.NORM_CTRL.DISP.VALUE - a path rooted one level up,
                # at the object the three norms hang off. Longest scope wins,
                # which keeps the sibling preference this already had, and a
                # path that resolves nowhere is still retained verbatim for the
                # contract validator to reject rather than guessed at.
                parts = tuple(condition_path.split("."))
                rendered_path = condition_path
                for depth in range(len(prefix), -1, -1):
                    scoped = ".".join(prefix[:depth] + parts)
                    if scoped in field_paths:
                        rendered_path = scoped
                        break
                lines.append(f"{body}  - path: {_scalar(rendered_path)}")
                if len(values) == 1:
                    lines.append(f"{body}    equals: {_scalar(values[0])}")
                else:
                    lines.append(f"{body}    in:")
                    lines += [f"{body}      - {_scalar(value)}" for value in values]
        lines.append(f"{body}documentedDefault: {_scalar(parsed.documented_default)}")
        if parsed.documented_default_note is not None:
            lines.append(f"{body}documentedDefaultNote: {_scalar(parsed.documented_default_note)}")
        if parsed.requirement is None:
            lines.append(f"{body}documentedOptional: null")
        else:
            lines.append(f"{body}documentedOptional: {'true' if parsed.requirement == 'optional' else 'false'}")
        if parsed.enum and parsed.type != "array":
            lines.append(f"{body}enum: [{', '.join(_scalar(value) for value in parsed.enum)}]")

        # safeToOmit is a claim about the product, so it is only ever answered
        # `true` here from a payload a product actually accepted without the
        # field. Everything else stays `unverified`, which is the honest state,
        # not a lesser one.
        # `evidence.sent` being empty means the payload it describes sent
        # nothing, so it accepted nothing - see live_omission_evidence(). The
        # source filters those out; this refuses to believe one handed over
        # directly, because "absent from the empty set" is true of every field
        # there has ever been.
        omitted_live = (
            evidence is not None
            and evidence.sent
            and indent == "  "
            and parsed.key not in evidence.sent
            and condition_was_exercised(parsed)
            and (not parsed.products or bool(set(parsed.products) & evidence.product_names))
        )
        if omitted_live:
            assert evidence is not None
            lines.append(f"{body}safeToOmit: true")
            lines.append(f"{body}omissionEvidence: >-")
            lines += _block(
                f"scripts/live_crud_check.py's {evidence.case} case completed a live "
                f"create-read-update-delete round trip on {evidence.products} without this "
                f"field in its payload. That is evidence the call is accepted, not that the "
                f"resulting model is what an engineer wanted.",
                body + "  ",
            )
        else:
            lines.append(f"{body}safeToOmit: unverified")
            lines.append(f"{body}# TODO(review): nobody has omitted this against a live product.")
            lines.append(f"{body}# Leave it unverified, or find out - do not read the manual's")
            lines.append(f"{body}# 'Optional' as an answer; that is what documentedOptional records.")
        lines.append(f"{body}provenance: manual")
        for note in parsed.notes:
            lines += _block(f"{_note_marker(note)}: {note}", body, prefix="# ")
        if parsed.properties:
            lines.append(f"{body}properties:")
            lines += _render_fields(parsed.properties, body + "  ", prefix=current_path, field_paths=field_paths)
    return lines


# `/post/PM`'s JSON Schema spells the key `"argument"` while the same section's
# request example and prose say `"Argument"`; the key's case is not what this
# reads, the declared type is. Measured 2026-09-17: accepting either case
# changes this function's answer for that one section and no other.
_ARGUMENT_SCHEMA = re.compile(
    r'"[Aa]rgument"\s*:\s*\{\s*"type"\s*:\s*"(?P<type>[a-z]+)"(?P<rest>.*?)\n\s*\}',
    re.DOTALL,
)


_EMPTY_PROPERTIES = re.compile(r'"properties"\s*:\s*\{\s*\}')


def _scalar_argument(section: "Section") -> tuple[str, Optional[str]] | None:
    """Read a section's JSON Schema when it documents a non-`fields` argument.

    Nine `/doc/*` sections carry a JSON Schema and no Specifications table, and
    the reason is not that the payload is undocumented: `/doc/OPEN` and
    `/doc/SAVEAS` take a bare path string, and `/doc/NEW`, `/doc/CLOSE` and
    `/doc/SAVE` take an object the manual states is empty. Returns
    ``("scalar", type)`` or ``("empty", None)``; anything else stays unread so
    it cannot be mistaken for a documented shape.
    """

    match = _ARGUMENT_SCHEMA.search("\n".join(section.lines))
    if match is None:
        return None
    argument_type = match.group("type")
    if argument_type in {"string", "number", "integer", "boolean"}:
        return "scalar", argument_type
    if argument_type == "object":
        rest = match.group("rest")
        # `/doc/NEW` writes `"properties": {}` rather than omitting the
        # key. An empty map is the manual saying the object carries
        # nothing; a populated one is a payload not to flatten away.
        if '"properties"' not in rest or _EMPTY_PROPERTIES.search(rest):
            return "empty", None
    return None


def render_draft(section: Section, evidence: Optional[LiveOmission] = None) -> str:
    main = section.tables[0] if section.tables else None
    fields, structural_merges = _structural_fields(section)
    fields, conditional_merges = _conditional_fields(section, fields)
    variant_table_indexes = {
        index for index, table in enumerate(section.tables) if any(variant.table is table for variant in section.variants)
    }
    resolved_tables = {merge.table for merge in structural_merges} | conditional_merges | variant_table_indexes
    # A small reviewed set of historical contracts represents these tables as
    # field-level appliesWhen entries instead of endpoint variants. Keep that
    # settled contract shape while still retaining the bold manual label for
    # measurement; a newly explicit label must not create a false drift claim.
    rendered_variants = (
        [] if variant_table_indexes and variant_table_indexes <= conditional_merges else section.variants
    )
    lines: list[str] = [
        f"# DRAFT contract for {section.endpoint} - extracted, not reviewed.",
        "#",
        "# Generated by scripts/extract_contracts.py from the official manual. It is a",
        "# transcription of what the manual says, nothing more. Before moving this file",
        "# to contracts/endpoints/ you must supply what the manual cannot know:",
        "#",
        "#   1. safeToOmit for every field. Omitted here on purpose - the file will not",
        "#      validate until you answer it. 'Optional' in the manual is a claim about",
        "#      the documentation; safeToOmit is a claim about the product, and /db/NMAS",
        "#      is the case where the two disagree and the session dies.",
        "#   2. verification.status and any records under contracts/verification/.",
        "#   3. sdkRules for anything a caller could reasonably do that breaks the product.",
        "#   4. products - confirm against live evidence, not the manual's framing.",
        "#      32 of 47 endpoints the manual calls Civil-only answer on Gen NX too.",
        "#",
        "# Then run: python scripts/validate_contracts.py",
        "",
        "contractVersion: 1",
        "draft: true   # reviewing this file is what removes this line",
        f"id: {section.id}",
        f"endpoint: {section.endpoint}",
        f"name: {_scalar(_english_label(section.title) or section.endpoint)}",
    ]

    if not section.title:
        lines.append(
            "# NOTE: the manual does not state a human-readable endpoint label; keep this draft unpromoted."
        )

    lines += ["", "# TODO(review): confirm against live evidence, not the manual's framing.", "products: [gen, civil]", ""]

    lines += ["source:", "  manual:", "    status: documented", "    repo: Dennis5882/MIDAS-API"]
    lines.append(f"    chapterFile: {section.chapter_file}")
    lines.append(f"    section: {_scalar(section.heading)}")
    if section.source_url:
        lines.append(f"    url: {section.source_url}")
    lines += ["  liveNotes:", "    - docs/live_verification_notes.md", ""]

    lines += [
        "# TODO(review): manual_only is the honest state for a contract nobody has",
        "# called yet. Raise it only with a record in contracts/verification/.",
        "verification:",
        "  status: manual_only",
        "",
    ]

    methods = section.methods or ["GET", "POST", "PUT", "DELETE"]
    argument = _scalar_argument(section) if not section.tables else None
    if not section.methods:
        lines.append("# TODO(review): the chapter did not state its methods; this is the /db/* default.")
    lines.append("operations:")
    for method in methods:
        risk = "read_only" if method == "GET" else ("destructive" if method == "DELETE" else "write")
        lines.append(f"  - method: {method}")
        lines.append(f"    risk: {risk}   # TODO(review): product_crash_risk if it has ever ended a session")
        if method == "DELETE":
            lines.append("    mitigation: none   # TODO(review): see /db/NODE's contract for the two DELETE forms")
        lines.append("    request:")
        if method in {"GET", "DELETE"}:
            lines.append("      wrapper: none")
        elif argument is not None:
            kind, scalar_type = argument
            lines.append("      wrapper: argument")
            lines.append(f"      itemSchema: {kind}")
            if scalar_type is not None:
                lines.append(f"      scalarType: {scalar_type}")
        else:
            lines.append("      wrapper: assign")
            lines.append("      itemSchema: fields")
        lines.append("    response:")
        lines.append("      wrapper: table")
        lines.append("      keyStability: stable")
    lines.append("")

    if main is None:
        lines += [
            "# No parameter table could be parsed from this section. Transcribe the",
            "# fields by hand, or check whether the endpoint takes no payload at all.",
            "fields: []",
            "",
        ]
    else:
        # `_schema_only_roots` asks what the *tables* name, because that is all
        # it can see. The question the note asks is narrower - whether the
        # contract being written is missing a root the schema declares - and by
        # here that is answerable: a structural merge or a reviewed handler may
        # already have placed one. `/db/RCHK`'s BEAM and COLM appear only as
        # table headings, never as a row, yet both are assembled with their full
        # subtrees. Reporting them anyway asks a reviewer to reconcile two
        # renderings that already agree.
        unplaced = tuple(
            root for root in section.schema_only_roots
            if not any(field.key == root for field in fields)
        )
        if unplaced:
            missing = ", ".join(unplaced)
            lines += [
                f"# NOTE: this section's own JSON Schema declares {missing} and the",
                "# Specifications table below never names them, so the table is not the",
                "# whole request. Reconcile the two renderings before promoting - a",
                "# contract drafted from the table alone is what declared /db/FIMP's",
                "# three-level object as ten flat top-level fields.",
            ]
        lines.append("fields:")
        lines += _render_fields(fields, "  ", evidence)
        lines.append("")

    if rendered_variants:
        lines.append("variants:")
        for variant in rendered_variants:
            lines += ["  - when:"]
            for field, values in variant.conditions:
                if len(values) == 1:
                    lines += [
                        f"      - path: {_scalar(field)}",
                        f"        equals: {_scalar(values[0])}",
                    ]
                else:
                    # The manual states one table for several values of the
                    # same field; `in` says exactly that without duplicating it.
                    lines += [f"      - path: {_scalar(field)}", "        in:"]
                    lines += [f"          - {_scalar(value)}" for value in values]
            lines += [
                "    source:",
                f"      table: {_scalar(variant.table.heading)}",
                f"      line: {variant.table.line}",
                "    fields:",
            ]
            lines += _render_fields(variant.table.fields, "      ")
        lines.append("")

    corrections = _MANUAL_TYPE_CORRECTIONS.get(section.endpoint)
    key_corrections = _MANUAL_KEY_CORRECTIONS.get(section.endpoint)
    measured = _MANUAL_REQUIREDNESS_CORRECTIONS.get(section.endpoint)
    if corrections or key_corrections or measured:
        # The correction lives in the contract as a defect record, not only as
        # a corrected type: a manual re-sync that reinstates the table's claim
        # has to argue with this, rather than silently winning.
        lines.append("manualDefects:")
        for renamed in (key_corrections or {}).values():
            lines.append("  - describes: field_name")
            lines.append("    manualSays: >-")
            lines += _block(renamed.manual_says, "      ")
            lines.append("    actual: >-")
            lines += _block(renamed.actual, "      ")
            lines.append("    evidence: >-")
            lines += _block(renamed.evidence, "      ")
        for correction in (corrections or {}).values():
            lines.append("  - describes: field_value")
            lines.append("    manualSays: >-")
            lines += _block(correction.manual_says, "      ")
            lines.append("    actual: >-")
            lines += _block(correction.actual, "      ")
            lines.append("    evidence: >-")
            lines += _block(_MANUAL_TYPE_CORRECTION_EVIDENCE, "      ")
        for entries in (measured or {}).values():
            for entry in entries:
                lines.append(f"  - describes: {entry.describes}")
                lines.append("    manualSays: >-")
                lines += _block(entry.manual_says, "      ")
                lines.append("    actual: >-")
                lines += _block(entry.actual, "      ")
                lines.append("    evidence: >-")
                lines += _block(entry.evidence, "      ")
        lines.append("")

    lines.append("extraction:")
    lines.append(f"  source: {section.chapter_file} line {main.line if main else '?'}")
    lines.append(f"  table: {_scalar(main.heading if main else 'none found')}")
    if section.merged_sections:
        # Several manual sections describe this one route. Say which, so a
        # reviewer can read each of them rather than trusting the fold.
        lines.append("  mergedSections:")
        for heading, origin in section.merged_sections:
            lines.append(f"    - heading: {_scalar(heading)}")
            lines.append(f"      line: {origin}")
    missing_columns = [table for table in section.tables if table.missing_columns]
    if missing_columns:
        lines.append("  missingColumns:")
        for table in missing_columns:
            lines.append(f"    - heading: {_scalar(table.heading)}")
            lines.append(f"      line: {table.line}")
            lines.append(f"      columns: [{', '.join(_scalar(column) for column in table.missing_columns)}]")
    if structural_merges:
        lines.append("  structuralTables:")
        for merge in structural_merges:
            table = section.tables[merge.table]
            lines.append(f"    - heading: {_scalar(table.heading)}")
            lines.append(f"      line: {table.line}")
            lines.append("      paths:")
            for target in merge.targets:
                lines.append(f"        - {_scalar('.'.join(target) or '<root>')}")
    unresolved = [
        (index, table)
        for index, table in enumerate(section.tables[1:], start=1)
        if index not in resolved_tables
    ]
    if unresolved:
        lines.append("  # Additional parameter tables in this section were NOT merged. They are")
        lines.append("  # usually conditional variants selected by a type/code field. Decide")
        lines.append("  # whether they belong in this contract's fields, as nested `properties`,")
        lines.append("  # or as a separate contract - do not assume the first table is the whole")
        lines.append("  # schema.")
        lines.append("  unmergedTables:")
        for _, table in unresolved:
            lines.append(f"    - heading: {_scalar(table.heading)}")
            lines.append(f"      fields: {len(table.fields)}")
            lines.append(f"      line: {table.line}")
            # Which names, not just how many. validate_contracts.py's
            # field-parity check waives a name this table accounts for and
            # reports one that no table and no contract does; with only a count
            # it had to skip the whole contract, and 214 wire names the SDKs
            # ship went unchecked behind twenty of these entries.
            names = _unmerged_field_names(table)
            if names:
                lines.append(
                    "      fieldNames: [" + ", ".join(_scalar(n) for n in names) + "]"
                )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------


_SELECTOR_NAME = re.compile(r"`?([A-Za-z_][A-Za-z0-9_.]*)`?\s*(?:==|=|:)")
_SELECTOR_ONE_VALUE = re.compile(
    r"`?[A-Za-z_][A-Za-z0-9_.]*`?\s*(?:==|=|:)\s*"
    r"(?:`?\"[^\"]+\"`?|`?-?\d+(?:\.\d+)?`?|`?(?:true|false)`?)",
    re.IGNORECASE,
)
_SELECTOR_VALUE_LIST = re.compile(
    r"`?[A-Za-z_][A-Za-z0-9_.]*`?\s*(?:==|=|:)\s*"
    r"(?:`?\"[^\"]+\"`?|`?-?\d+(?:\.\d+)?`?|`?(?:true|false)`?)"
    r"(?:\s*(?:/|,|\||\bor\b|또는)\s*"
    r"(?:`?[A-Za-z_][A-Za-z0-9_.]*`?\s*(?:==|=|:)\s*)?"
    r"(?:`?\"[^\"]+\"`?|`?-?\d+(?:\.\d+)?`?|`?(?:true|false)`?))+",
    re.IGNORECASE,
)


def _selector_evidence(heading: str) -> str:
    """Classify only the selector fact written in a supplementary-table label.

    This is a report classifier, not a promotion rule.  It deliberately says
    ``no selector stated`` for label-only tables rather than inferring a value
    from a neighbouring enum row, and recognises only explicit literal lists.
    """

    if _SELECTOR_VALUE_LIST.search(heading):
        return "selector with several values"
    if _SELECTOR_ONE_VALUE.search(heading):
        return "selector with one value"
    if _SELECTOR_NAME.search(heading):
        return "selector without a readable literal"
    return "no selector stated"


def _supplementary_table_measurement(sections: list[Section]) -> list[tuple[str, int, str, str, str]]:
    """Return every extra table with its resolution and literal-selector evidence."""

    measured: list[tuple[str, int, str, str, str]] = []
    for section in sections:
        base_fields, structural_merges = _structural_fields(section)
        _, conditional_merges = _conditional_fields(section, base_fields)
        structural_indexes = {merge.table for merge in structural_merges}
        variant_indexes = {
            index
            for index, table in enumerate(section.tables)
            if any(variant.table is table for variant in section.variants)
        }
        for index, table in enumerate(section.tables[1:], start=1):
            resolution = (
                "structural merge"
                if index in structural_indexes
                else "field appliesWhen merge"
                if index in conditional_merges
                else "explicit variant"
                if index in variant_indexes
                else "unmerged"
            )
            measured.append((section.endpoint, table.line, table.heading, resolution, _selector_evidence(table.heading)))
    return measured


def run_report(sections: list[Section], table_family: dict[str, int]) -> int:
    by_chapter: dict[str, list[Section]] = {}
    for section in sections:
        by_chapter.setdefault(section.chapter_file, []).append(section)

    print(f"{'chapter':<40}{'endpoints':>10}{'with fields':>13}{'fields':>9}{'multi-table':>13}")
    total = with_fields = fields = multi = 0
    for chapter, items in sorted(by_chapter.items()):
        parsed = [s for s in items if s.tables]
        count = sum(len(_walk(s.tables[0].fields)) for s in parsed)
        many = sum(1 for s in items if len(s.tables) > 1)
        print(f"{chapter:<40}{len(items):>10}{len(parsed):>13}{count:>9}{many:>13}")
        total += len(items)
        with_fields += len(parsed)
        fields += count
        multi += many
    print(f"{'TOTAL':<40}{total:>10}{with_fields:>13}{fields:>9}{multi:>13}")
    unnamed = [section for section in sections if not section.title]
    print(
        f"\nname extraction: {len(unnamed)} section(s) have no human-readable label in the "
        "heading, opening blockquote, or chapter contents table."
    )

    # How trustworthy is that field count? Anything carrying a note needs a human
    # before it can be believed, and saying so is the difference between a draft
    # and a claim.
    all_fields = [f for section in sections for table in section.tables for f in _walk(table.fields)]
    structured_conditions = 0
    for section in sections:
        rendered_fields, _ = _structural_fields(section)
        rendered_fields, _ = _conditional_fields(section, rendered_fields)
        structured_conditions += sum(len(field.applies_when) for field in _walk(rendered_fields))
    flagged = [f for f in all_fields if f.notes]
    nested = [f for f in all_fields if f.properties]
    print(
        f"\nacross every parsed table: {len(all_fields)} fields, {len(nested)} of them nested, "
        f"{len(flagged)} carrying a review note ({100 * len(flagged) // max(len(all_fields), 1)}%)."
    )
    print(f"structured appliesWhen conditions extracted: {structured_conditions}")
    reasons: dict[str, int] = {}
    for entry in flagged:
        for note in entry.notes:
            head = note.split(";")[0].split(" - ")[0].strip()
            head = re.sub(r"^key '.*?' is", "key is", head)
            head = re.sub(r"^the manual types this '\w+'", "the manual types this", head)
            head = re.sub(r"^unrecognised (\w+) .*", r"unrecognised \1 value", head)
            reasons[head] = reasons.get(head, 0) + 1
    for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1])[:8]:
        print(f"  {count:>5}  {reason}")

    # Stage 2's blockers are intentionally measured here, rather than copied
    # into a planning document by hand.  These are all review notes: a value
    # not counted as parseable stays unverified rather than being guessed.
    enum_missing = sum(_ENUM_VALUES_ELSEWHERE in field.notes for field in all_fields)
    array_element_missing = sum(
        "array element type not stated by the manual" in field.notes for field in all_fields
    )
    unrecognised_types = sum(
        any(note.startswith("unrecognised Value Type") for note in field.notes) for field in all_fields
    )
    unstated_requirements = sum(field.requirement is None for field in all_fields)
    unstated_types = sum(field.type is None for field in all_fields)
    supplementary = _supplementary_table_measurement(sections)
    resolution_counts = Counter(entry[3] for entry in supplementary)
    unmerged = [entry for entry in supplementary if entry[3] == "unmerged"]
    unmerged_evidence = Counter(entry[4] for entry in unmerged)
    print(
        "\nStage 2 fidelity blockers: "
        f"{enum_missing} enum value list(s) unstated, "
        f"{array_element_missing} array element type(s) unstated, "
        f"{unrecognised_types} unrecognised Value Type cell(s)."
    )
    print(
        "  manual columns preserved as explicit contract uncertainty: "
        f"{unstated_requirements} requiredness value(s), {unstated_types} Value Type value(s)."
    )
    # Keep the six recurring promotion notes measurable here.  These are field
    # occurrences across every parsed manual table, deliberately not a
    # hand-counted list of draft refusals: one endpoint can carry several notes
    # and a single note can be repeated in nested rows.
    promotion_note_counts = {
        "conditional requirement has no stated condition": sum(
            "the manual marks this conditional but does not state the condition" in field.notes
            for field in all_fields
        ),
        "Required cell is blank": sum(
            "the manual leaves the Required column blank" in field.notes for field in all_fields
        ),
        "enum values are unstated": enum_missing,
        "array item type is unstated": array_element_missing,
        "table has no Default column": sum(
            "the table has no Default column" in field.notes for field in all_fields
        ),
        "non-literal System default kept verbatim": sum(
            "non-literal default 'System' kept verbatim; confirm what the server does" in field.notes
            for field in all_fields
        ),
    }
    print("  promotion-note forms (field occurrences):")
    for label, count in promotion_note_counts.items():
        print(f"    {count:>5}  {label}")
    print(f"  supplementary tables: {len(supplementary)} total")
    for resolution in ("explicit variant", "field appliesWhen merge", "structural merge", "unmerged"):
        print(f"    {resolution_counts[resolution]:>5}  {resolution}")
    print("  unmerged supplementary tables by manual selector evidence:")
    for evidence in (
        "selector with several values",
        "selector with one value",
        "selector without a readable literal",
        "no selector stated",
    ):
        print(f"    {unmerged_evidence[evidence]:>5}  {evidence}")
    print("  unmerged supplementary table detail:")
    for endpoint, line, heading, _, evidence in unmerged:
        print(f"    {endpoint} line {line}: [{evidence}] {heading}")

    # A section with no stated verbs cannot be promoted, so this is a headline
    # number, not a detail - and it was reported as 276 while the extractor could
    # read only the narrowest of the six forms the chapters use. Print it, so the
    # next person quoting it is quoting a measurement.
    silent = [s for s in sections if not s.methods]
    if silent:
        print(f"\n{len(silent)} of {total} sections state their HTTP methods nowhere the extractor can read:")
        for chapter, count in sorted(Counter(s.chapter_file for s in silent).items()):
            print(f"  {count:>3}  {chapter}")

    if table_family:
        skipped = sum(table_family.values())
        table_contracts = list(TABLE_DIR.glob("*.yaml")) if TABLE_DIR.is_dir() else []
        print(
            f"\n{skipped} sections across {len(table_family)} chapters belong to the shared "
            f"/post/TABLE/table-result family and are not endpoint contracts:"
        )
        for chapter, count in sorted(table_family.items()):
            print(f"  {count:>3}  {chapter}")
        print(
            "  table-contract coverage: "
            f"{len(table_contracts)} contracted result tables."
        )
        print(
            "  Sections in those chapters with a route of their own (chapter 23's "
            "/post/PM and /post/STEELCODECHECK) are read as endpoint sections and "
            "are not counted here."
        )

    promoted = {path.stem for path in ENDPOINT_DIR.glob("*.yaml")} if ENDPOINT_DIR.is_dir() else set()
    drafted = {path.stem for path in DRAFT_DIR.glob("*.yaml")} if DRAFT_DIR.is_dir() else set()
    print(f"\npromoted contracts: {len(promoted)}   drafts awaiting review: {len(drafted - promoted)}")
    resource_inventory = ROOT / "schema" / "typescript-resources.json"
    if resource_inventory.is_file():
        try:
            resources = json.loads(resource_inventory.read_text(encoding="utf-8")).get("resources", [])
            resource_endpoints = {
                item["endpoint"]
                for item in resources
                if isinstance(item, dict) and isinstance(item.get("endpoint"), str)
            }
            contract_endpoints = {
                next(
                    (line.removeprefix("endpoint: ").strip() for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("endpoint: ")),
                    "",
                )
                for path in ENDPOINT_DIR.glob("*.yaml")
            }
        except (json.JSONDecodeError, OSError):
            resource_endpoints = set()
            contract_endpoints = set()
        if resource_endpoints:
            covered = resource_endpoints & contract_endpoints
            print(
                "npm resource contract coverage (committed inventory): "
                f"{len(covered)} of {len(resource_endpoints)} covered; "
                f"{len(resource_endpoints - covered)} without a contract."
            )
            # A missing contract can still be a parser or review problem, but a
            # resource absent from every parsed manual section has no manual
            # payload source at all. Report that separately so it is not
            # mistaken for an ordinary promotable draft.
            manual_endpoints = {section.endpoint for section in sections}
            no_manual_section = sorted(resource_endpoints - manual_endpoints)
            print(
                "npm resource manual-section coverage: "
                f"{len(no_manual_section)} without a parsed manual section."
            )
            if no_manual_section:
                print("  " + ", ".join(no_manual_section))
    return 0


def run_emit(sections: list[Section], targets: list[str], emit_all: bool) -> int:
    wanted = {t.lower().rstrip("/") for t in targets}
    promoted = {path.stem for path in ENDPOINT_DIR.glob("*.yaml")} if ENDPOINT_DIR.is_dir() else set()

    chosen = [
        section
        for section in sections
        if emit_all or section.endpoint.lower() in wanted or section.id in wanted
    ]
    if not chosen:
        print(f"ERROR: nothing matched {sorted(wanted)}", file=sys.stderr)
        return 2

    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    evidence = live_omission_evidence()
    # One endpoint can hold several manual sections - a chapter that deliberately
    # repeats another chapter's endpoint, or one endpoint documented once per
    # result table.  They share a draft name, so the last one silently replaced
    # the rest and only the count gave it away.  Keep last-write-wins, but say so.
    written: dict[str, Section] = {}
    overwritten = 0
    skipped = 0
    for section in chosen:
        if section.id in promoted:
            skipped += 1
            continue
        draft = render_draft(section, evidence.get(section.endpoint))
        if (previous := written.get(section.id)) is not None:
            overwritten += 1
            print(
                f"WARNING: {section.endpoint} has more than one manual section and "
                f"they share the draft name {section.id}.yaml. "
                f"{previous.chapter_file} section {previous.number} was overwritten "
                f"by {section.chapter_file} section {section.number} - only the last "
                "one is reviewable. They disagree by more than one enumerated "
                "field, so they were not folded into a single route.",
                file=sys.stderr,
            )
        (DRAFT_DIR / f"{section.id}.yaml").write_text(draft, encoding="utf-8")
        written[section.id] = section
        if not emit_all:
            print(f"  {section.endpoint:<45} -> contracts/drafts/{section.id}.yaml")
    print(
        f"\nwrote {len(written)} draft(s); skipped {skipped} already promoted "
        "to contracts/endpoints/"
    )
    if overwritten:
        print(
            f"{overwritten} further section(s) reused a draft name and replaced "
            "what was there - see the warnings above before reviewing those drafts."
        )
    print("Every draft needs review before it can validate - see the header of each file.")
    return 0


def _flatten_manual(fields: list[ParsedField], prefix: str = "") -> dict[str, ParsedField]:
    """Address nested fields by dotted path so the comparison is order-free."""
    out: dict[str, ParsedField] = {}
    for entry in fields:
        path = f"{prefix}{entry.key}"
        out[path] = entry
        out.update(_flatten_manual(entry.properties, f"{path}."))
    return out


_KEY_CELL_ANNOTATION = re.compile(r"\((?:OPT|VAL|STR)\)$")
_KEY_CELL_RANGE = re.compile(r'^(?P<stem>\w+?)(?P<first>\d+)"?\s*~\s*"?(?P=stem)(?P<last>\d+)$')


def _unpack_key_cell(key: str) -> list[str]:
    """The wire names one Key cell holds, in cell order.

    A Key cell can name several properties at once, and the table parser hands
    the whole cell back as one key: `"bSD" / "iSDOPT" / "SDCONST"` arrives as a
    single 27-character string that is not a wire name at all. That is
    invisible while the cell only ever feeds a *count*, which is what
    `unmergedTables` recorded until 2026-09-04; the moment the names are
    written down it is the difference between a waiver that accounts for three
    fields and one that accounts for none of them.

    Every form handled here was read in the manual. A slash- or comma-joined
    list maps its names positionally to the Type and Description columns beside
    it (`Boolean / Integer / Number`, `Stress Decrease 사용 / 옵션 / 상수`); a
    `A1 ~ A4` range is written out in full by its own Description ("3+ Lane
    Factors (L1~L4)"); a trailing `(OPT)`/`(VAL)`/`(STR)` is chapter 14's
    column grouping, not part of the name. This is a transcription, not an
    inference, and it is used only for `unmergedTables[].fieldNames` - the
    merged-field path keeps `_REVIEWED_SHARED_COMPACT_KEYS`, which requires a
    named review per row because a merged row becomes a published field.
    """
    text = key.strip().strip('"')
    match = _KEY_CELL_RANGE.fullmatch(text)
    if match:
        stem = match.group("stem")
        first, last = int(match.group("first")), int(match.group("last"))
        if 0 < last - first < 12:
            return [f"{stem}{index}" for index in range(first, last + 1)]
    out: list[str] = []
    for piece in re.split(r'"?\s*[/,]\s*"?', text):
        piece = re.sub(r"\(.*?\)$", "", piece.strip().strip('"')).strip()
        piece = _KEY_CELL_ANNOTATION.sub("", piece).strip().strip('"')
        if piece:
            out.append(piece)
    return out or [text]


def _unmerged_field_names(table: "ParsedTable") -> list[str]:
    """Every wire name an unmerged table holds, table order, nested included."""
    out: list[str] = []

    def walk(fields: list) -> None:
        for entry in fields:
            for piece in _unpack_key_cell(entry.key):
                if piece not in out:
                    out.append(piece)
            walk(entry.properties or [])

    walk(table.fields)
    return out


def _branch_destination_fields(contract: dict) -> dict[str, dict]:
    """Fields a reviewed branch places under a structural table's destination.

    A heading like `TYPE="EX"(Explicit)일 때 SLAVES[]` states a condition and a
    destination at once. Merging it into the parent is one placement; the other
    is a variant that redeclares the destination with the table's rows, and it
    is the right one when two such tables give the destination different
    members - merged, /db/MCON's SLAVES[] demanded all four keys of both, which
    neither TYPE accepts. The members then live in the variants, under the
    destination's parent, and the manual's flattened copy of them would read as
    missing from the base. A `note` on the structuralTables entry is what says
    this placement was chosen rather than forgotten, so only noted entries count.
    """
    found: dict[str, dict] = {}
    for entry in (contract.get("extraction") or {}).get("structuralTables", []):
        if not entry.get("note"):
            continue
        for destination in entry.get("paths", []):
            parent = destination.rsplit(".", 1)[0] + "." if "." in destination else ""
            for variant in contract.get("variants", []):
                for sub, value in _flatten_contract(variant.get("fields", []), parent).items():
                    if sub == destination or sub.startswith(destination + "."):
                        found.setdefault(sub, value)
    return found


_KEY_WITH_OBJECT = re.compile(r"\([A-Z][A-Z0-9_]*\)$")


def _under_structural_destination(
    key: str,
    destinations: set[str],
    manual_fields: dict[str, dict],
    section_names: frozenset[str] = frozenset(),
) -> bool:
    """Whether a contract path is a declared structural destination or inside one.

    `extraction.structuralTables` records that a supplementary table's heading
    named where its rows go - "Parameters - COMMON" puts its ten rows under
    `COMMON`. The parser cannot represent that: it flattens every table in the
    section into one namespace, so it holds `LL_NAME` where the contract holds
    `COMMON.LL_NAME`. Comparing those as strings reports drift on a contract
    that is right and passes one that is wrong, which is exactly what happened
    to the four /db/LLAN* contracts.

    The destination itself is exempt because no table row names it - the
    heading does. Everything under it is exempt only if its own leaf name is a
    field the manual's tables state, so a member the manual never mentions is
    still reported.

    "The manual's tables" means every table in the section, not only the ones
    the draft merged: `/db/MVLDpl` states DEFAULT's and AUTO_OPTIMIZE's members
    in bold-row groups keyed by LOAD_MODEL, which stay separate tables to the
    parser, so their names are in `section_names` and nowhere in
    `manual_fields`.
    """
    if key in destinations:
        return True
    # `<root>` is how a structuralTables entry says its rows go at record root.
    if "<root>" in destinations and all(part in section_names for part in key.split(".")):
        return True
    for destination in destinations:
        if key.startswith(f"{destination}."):
            remainder = key[len(destination) + 1:]
            return remainder in manual_fields or remainder.rsplit(".", 1)[-1] in section_names
    return False


def _flatten_contract(fields: list[dict], prefix: str = "") -> dict[str, dict]:
    out: dict[str, dict] = {}
    for entry in fields:
        path = f"{prefix}{entry['key']}"
        out[path] = entry
        out.update(_flatten_contract(entry.get("properties", []), f"{path}."))
    return out


def _declares_non_field_argument(contract: dict) -> bool:
    """Whether a contract documents a scalar or empty argument.

    Mirrors promote_contract.py's gate of the same name: an empty `fields`
    list is the right transcription when the manual states the argument is
    one primitive or an empty object, so neither promotion nor the drift
    check should read it as a parsing failure.
    """
    for operation in contract.get("operations", []) or []:
        request = operation.get("request") or {}
        if request.get("itemSchema") in {"scalar", "empty"}:
            return True
    return False


def run_check(sections: list[Section]) -> int:
    try:
        import yaml
    except ImportError:
        print('ERROR: PyYAML is not installed. Run: pip install -e ".[dev]"', file=sys.stderr)
        return 2

    by_endpoint = {section.endpoint: section for section in sections}
    problems: list[str] = []
    skipped: list[str] = []
    checked = 0

    for path in sorted(ENDPOINT_DIR.glob("*.yaml")):
        contract = yaml.safe_load(path.read_text(encoding="utf-8"))
        if contract["source"]["manual"]["status"] != "documented":
            continue
        chapter = contract["source"]["manual"].get("chapterFile")
        if chapter in TABLE_FAMILY_CHAPTERS and contract["endpoint"] == SHARED_TABLE_ROUTE:
            # /post/TABLE is documented in those chapters' shared "공통 사항"
            # sections, not in a numbered endpoint section, and this extractor
            # does not model that chapter family. Reporting it as missing would
            # be reporting the extractor's own gap as a contract defect.
            skipped.append(f"{path.name} ({chapter}: /post/TABLE family, not modelled)")
            continue

        section = by_endpoint.get(contract["endpoint"])
        if section is None:
            problems.append(f"{path.name}: claims a documented manual source, but no chapter section describes {contract['endpoint']}")
            continue
        if not section.tables:
            # A section can document its argument without a Specifications
            # table: `/doc/OPEN` sends a bare path string and `/doc/NEW` an
            # empty object, both stated in the section's JSON Schema. A
            # contract that declares that is checked against the schema by
            # the validator, not against a table that does not exist.
            if _declares_non_field_argument(contract):
                continue
            problems.append(f"{path.name}: no parameter table could be parsed from {section.chapter_file}; cannot check")
            continue
        checked += 1

        # Use the same closed structural merge map as draft emission.  Without
        # this, --check would wrongly call a nested supplementary-table field
        # contract drift simply because it only inspected the first table.
        manual_shape, _ = _structural_fields(section)
        manual_shape, conditional_merges = _conditional_fields(section, manual_shape)
        manual_fields = _flatten_manual(manual_shape)
        contract_fields = _flatten_contract(contract.get("fields", []))
        overridden = {
            d.get("describes") for d in contract.get("manualDefects", [])
        }
        # Fields the manual states in prose instead of a table. The parser
        # reads tables, so it cannot see them, and without this every one of
        # them looks like a field the contract invented. A `field_name`
        # manualDefect would silence them, but it would also silence the whole
        # contract and it would be a lie: the manual is not wrong here, it just
        # wrote a paragraph. Each entry names the line and quotes the sentence,
        # so the claim stays checkable against the chapter.
        prose_fields = {
            path
            for entry in (contract.get("extraction") or {}).get("prose", [])
            for path in entry.get("paths", [])
        }
        # Destinations a supplementary table's own heading names. The parser
        # flattens every table it reads into one namespace, so a section whose
        # tables are headed "Parameters - COMMON" and "Parameters - LANE_ITEMS"
        # yields the members and loses where they go. A contract that puts them
        # back where the heading says - and the server agrees - then reads as
        # drift on every single member, which is how the four /db/LLAN*
        # contracts came to publish a flat record: the shape that passed the
        # check was the wrong one. The exemption is narrow on purpose: the leaf
        # still has to be a name the manual's tables state.
        structural_paths = {
            path
            for entry in (contract.get("extraction") or {}).get("structuralTables", [])
            for path in entry.get("paths", [])
        }
        branch_fields = _branch_destination_fields(contract)
        # A Key cell can name its object beside the key - `SFI`(STR),
        # `PERIOD`(VAL) in /db/SPFC's later code tables - which the parser
        # keeps as part of the name. The name is the part before it.
        section_names = frozenset(
            _KEY_WITH_OBJECT.sub("", field.key)
            for table in section.tables
            for field in _walk(table.fields)
        )

        # The section heading, which carries its number. Inserting one endpoint
        # renumbers every section below it - /db/STYP-M1 landing at 02's #4 on
        # 2026-08-30 moved eleven - and a contract that still names the old
        # number sends the next reader to the wrong endpoint's table. Cheap to
        # check because the heading is transcribed verbatim, and the third
        # blind spot of this shape after name and methods.
        # Dash typography is presentation, and 90 contracts spell the manual's
        # em dash as `--`; the npm shadow gate already exempts exactly this, so
        # normalise before comparing or the real drift drowns in it.
        if section.heading and "field_name" not in overridden:
            declared_section = contract["source"]["manual"].get("section")
            if _plain_dashes(declared_section or "") != _plain_dashes(section.heading):
                problems.append(
                    f"{path.name}: source.manual.section {declared_section!r}, "
                    f"the chapter heading is {section.heading!r}"
                )

        # The chapter's own Active Methods, against the verbs the contract serves.
        # Nothing compared these before, which is how /db/POLC-M1 kept a POST the
        # chapter says twice that Hyper-S does not serve: the extractor misread a
        # comparison table, promotion carried the extra verb into the contract,
        # and both SDKs widened to match a contract nobody re-read against the
        # manual. Only a section that states its verbs can contradict anything;
        # where the manual is silent, emission falls back to the /db/* default
        # and there is no manual claim to check against.
        # The label is a manual fact too, and it ships: it is the resource name
        # in both packages. Nothing compared it - not this check, not
        # validate_contracts.py, and the generator's shadow gate only reaches
        # /db/*. So when chapters 24-27 labelled their sections in Korean and
        # promotion copied that into the contracts, 113 of them took a Korean
        # name and `/db/DCTL` carried one into src/midas_nx/ with every gate
        # green: the gates all asked whether the surfaces agreed, and they did.
        manual_label = _english_label(section.title)
        if manual_label and "field_name" not in overridden:
            if contract.get("name") != manual_label:
                problems.append(
                    f"{path.name}: name {contract.get('name')!r}, "
                    f"the manual's section label says {manual_label!r}"
                )

        if section.methods and "method" not in overridden:
            declared_methods = sorted({op["method"] for op in contract.get("operations", [])})
            if declared_methods != sorted(section.methods):
                problems.append(
                    f"{path.name}: operations serve {declared_methods!r}, "
                    f"the manual's Active Methods say {sorted(section.methods)!r}"
                )

        for key, manual in manual_fields.items():
            declared = contract_fields.get(key)
            if declared is None:
                # The same flattening the mirror check works around, seen from
                # the other side: a supplementary table's heading named a
                # destination the parser cannot represent, so the manual holds
                # `ELEM` where the contract holds `LANE_ITEMS.ELEM`. Look under
                # each declared destination before calling the field missing,
                # or a contract gets told to delete the nesting that makes it
                # right.
                declared = next(
                    (
                        contract_fields[f"{destination}.{key}"]
                        for destination in sorted(structural_paths)
                        if f"{destination}.{key}" in contract_fields
                    ),
                    None,
                )
            if declared is None:
                declared = branch_fields.get(key)
            if declared is None:
                # A `field_name` defect relaxes this the same way it relaxes
                # the mirror check below. It has to work in both directions:
                # the defect says the manual's field list is wrong, and a wrong
                # list can name fields the server does not have as easily as it
                # can omit ones it does. /db/REBW is the case that needs both -
                # twelve documented names the server answers to none of.
                if "field_name" not in overridden:
                    problems.append(
                        f"{path.name}: the manual documents {key!r}, the contract does not"
                    )
                continue
            if manual.type and declared["type"] != manual.type and "field_value" not in overridden:
                problems.append(f"{path.name}: {key} typed {declared['type']!r}, manual says {manual.type!r}")
            if (
                manual.requirement
                and declared["requirement"] != manual.requirement
                and "requiredness" not in overridden
            ):
                problems.append(f"{path.name}: {key} requirement {declared['requirement']!r}, manual says {manual.requirement!r}")
            # Deliberately *not* relaxed by a `requiredness` defect. The two
            # fields answer different questions: `requirement` is what the
            # contract asks a caller to do, which a live measurement can
            # overrule, while `documentedOptional` is what the manual's
            # Required column says, which no measurement changes. A defect
            # entry records that the column is wrong about the product; it does
            # not license restating the column itself.
            documented_optional = "unstated" if manual.requirement is None else manual.requirement == "optional"
            expected_documented_optional = None if documented_optional == "unstated" else documented_optional
            if declared["documentedOptional"] != expected_documented_optional:
                problems.append(
                    f"{path.name}: {key} documentedOptional={declared['documentedOptional']}, "
                    f"manual's Required column says "
                    f"{'nothing' if documented_optional == 'unstated' else ('Optional' if documented_optional else 'not Optional')}"
                )
            if declared.get("documentedDefault") != manual.documented_default and "default" not in overridden:
                problems.append(
                    f"{path.name}: {key} documentedDefault={declared.get('documentedDefault')!r}, "
                    f"manual says {manual.documented_default!r}"
                )
            if (
                declared.get("documentedDefaultNote") != manual.documented_default_note
                and "default" not in overridden
            ):
                problems.append(
                    f"{path.name}: {key} documentedDefaultNote={declared.get('documentedDefaultNote')!r}, "
                    f"manual says {manual.documented_default_note!r}"
                )
            if manual.enum and "enum" not in overridden:
                declared_enum = (
                    declared.get("items", {}).get("enum", [])
                    if manual.type == "array"
                    else declared.get("enum", [])
                )
                # A value set can be split across a section's tables: /ope/LCOM-SRC
                # tables its KDS body with DGNCODE "KDS 41 SRC : 2022" and, at the
                # section's end, its AIK-SRC2K body with DGNCODE "AIK-SRC2K" - both
                # the same wire field. What the tables state together is the set.
                section_enum = list(manual.enum)
                for table in section.tables:
                    for other in _walk(table.fields):
                        if other.key == key.split(".")[-1] and other.enum:
                            section_enum += [v for v in other.enum if v not in section_enum]
                if declared_enum != manual.enum and declared_enum != section_enum:
                    problems.append(
                        f"{path.name}: {key} enum={declared_enum!r}, manual says {manual.enum!r}"
                    )
            if manual.constraints and "field_value" not in overridden:
                constraint_keys = {
                    "minimum",
                    "exclusiveMinimum",
                    "maximum",
                    "exclusiveMaximum",
                    "notEqual",
                    "const",
                    "minItems",
                    "maxItems",
                    "minLength",
                    "maxLength",
                }
                declared_constraints = {
                    name: value for name, value in declared.items() if name in constraint_keys
                }
                if declared_constraints != manual.constraints:
                    problems.append(
                        f"{path.name}: {key} constraints={declared_constraints!r}, "
                        f"manual says {manual.constraints!r}"
                    )

        for key in contract_fields:
            if key in prose_fields:
                continue
            if _under_structural_destination(key, structural_paths, manual_fields, section_names):
                continue
            if key not in manual_fields and "field_name" not in overridden:
                problems.append(
                    f"{path.name}: the contract declares {key!r}, which the manual's table does not - "
                    f"record it under manualDefects if the manual is the one that is wrong"
                )

        # An unmergedTables entry that records its table's field names is a
        # waiver validate_contracts.py's field-parity check honours, so the
        # names have to keep matching the table they claim to transcribe. A
        # chapter edit that adds a row to an unmerged table would otherwise
        # widen the waiver silently, which is the one way this mechanism could
        # turn into fiction.
        tables_by_key = {(t.heading, t.line): t for t in section.tables}
        for entry in contract.get("extraction", {}).get("unmergedTables", []):
            declared = entry.get("fieldNames")
            if not declared:
                continue
            table = tables_by_key.get((entry.get("heading"), entry.get("line")))
            if table is None:
                problems.append(
                    f"{path.name}: unmergedTables names a table "
                    f"{entry.get('heading')!r} at line {entry.get('line')} that "
                    f"this section does not have"
                )
                continue
            actual = _unmerged_field_names(table)
            if list(declared) != actual:
                problems.append(
                    f"{path.name}: unmergedTables[{entry.get('heading')!r}] records "
                    f"{list(declared)!r}, the table holds {actual!r}"
                )

        variant_table_indexes = {
            index
            for index, table in enumerate(section.tables)
            if any(variant.table is table for variant in section.variants)
        }
        check_variants = (
            [] if variant_table_indexes and variant_table_indexes <= conditional_merges else section.variants
        )
        if check_variants:
            # A promoted incomplete contract can consciously preserve an
            # unmerged table with a reviewed resolution.  Do not turn a later
            # extractor improvement into a false manual-drift failure for that
            # earlier decision; newly emitted drafts will carry the variant.
            resolved_unmerged = {
                (entry.get("heading"), entry.get("line"))
                for entry in contract.get("extraction", {}).get("unmergedTables", [])
                if entry.get("resolution")
            }
            # A heading can state a condition and a parent object at once, and
            # then the same table is both a branch and a merge - the KDS
            # column-rebar endpoint's `CREATE_SUB_SECTION == true 일 때 - ELEMS`
            # is the case. Merging it is the placement that puts the fields
            # where the server looks, so a structuralTables entry that says in
            # its `note` why it was merged answers this table too. The note is
            # what makes the exemption narrow: an ordinary merge, of a heading
            # that never stated a condition, carries none and is unaffected.
            resolved_unmerged |= {
                (entry.get("heading"), entry.get("line"))
                for entry in contract.get("extraction", {}).get("structuralTables", [])
                if entry.get("note")
            }
            check_variants = [
                variant
                for variant in check_variants
                if (variant.table.heading, variant.table.line) not in resolved_unmerged
            ]
            # A variant gates on a field name, so a `field_name` defect takes
            # its gates with it. /db/REBW's three branch tables all gate on
            # fields the server does not have - CREATE_SUB_WALL_ID,
            # USE_END_REBAR, USE_MODEL_THICKNESS - and a contract cannot
            # declare a branch on a field that does not exist. The defect entry
            # is where that is recorded, in full, once.
            if "field_name" in overridden:
                check_variants = []
            declared_variants: dict[tuple, list[dict]] = {}
            for declared in contract.get("variants", []):
                key = tuple(_variant_key([condition]) for condition in declared.get("when", []))
                declared_variants.setdefault(key, []).append(declared)
            for variant in check_variants:
                key = tuple((field, values) for field, values in variant.conditions)
                label = ", ".join(f"{field}={_values_label(values)}" for field, values in variant.conditions)
                matching_variants = declared_variants.get(key, [])
                if not matching_variants:
                    problems.append(f"{path.name}: manual variant {label} is missing from the contract")
                    continue
                # A manual can document two additive tables under the same
                # literal selector (ELEM's tension and compression tables both
                # say STYPE=1). The source line keeps their order, and the
                # generated contract preserves it; compare each rather than
                # letting a dict silently discard the first table.
                declared_variant = matching_variants.pop(0)
                variant_manual = _flatten_manual(variant.table.fields)
                variant_contract = _flatten_contract(declared_variant.get("fields", []))
                # A `field_name` defect record already says the table's own
                # paths are wrong, and re-nesting changes every path in both
                # directions at once. The base-field comparison above has
                # honoured that override since it was introduced; this loop did
                # not, which made a reviewed correction look like drift.
                # /db/SECT is the case: its four SECTTYPE tables number their
                # rows against the common table's SECT_BEFORE, so read
                # literally they put a section's dimensions inside a boolean.
                # Compare by name rather than by path when that is recorded, so
                # a re-nested field is still checked for type, requiredness and
                # default, and a field that simply vanished is still caught.
                renested = "field_name" in overridden
                if renested:
                    variant_manual = {
                        key.rsplit(".", 1)[-1]: value for key, value in variant_manual.items()
                    }
                    variant_contract = {
                        key.rsplit(".", 1)[-1]: value for key, value in variant_contract.items()
                    }
                for key, manual in variant_manual.items():
                    declared = variant_contract.get(key)
                    if declared is None:
                        problems.append(f"{path.name}: variant {label} omits manual field {key!r}")
                        continue
                    if manual.type and declared["type"] != manual.type:
                        problems.append(
                            f"{path.name}: variant {label} field {key} typed {declared['type']!r}, "
                            f"manual says {manual.type!r}"
                        )
                    if manual.requirement and declared["requirement"] != manual.requirement:
                        problems.append(
                            f"{path.name}: variant {label} field {key} requirement "
                            f"{declared['requirement']!r}, manual says {manual.requirement!r}"
                        )
                    expected_documented_optional = (
                        None if manual.requirement is None else manual.requirement == "optional"
                    )
                    if declared["documentedOptional"] != expected_documented_optional:
                        problems.append(
                            f"{path.name}: variant {label} field {key} documentedOptional="
                            f"{declared['documentedOptional']!r}, manual says "
                            f"{expected_documented_optional!r}"
                        )
                    if declared.get("documentedDefault") != manual.documented_default:
                        problems.append(
                            f"{path.name}: variant {label} field {key} documentedDefault="
                            f"{declared.get('documentedDefault')!r}, manual says {manual.documented_default!r}"
                        )
                    if declared.get("documentedDefaultNote") != manual.documented_default_note:
                        problems.append(
                            f"{path.name}: variant {label} field {key} documentedDefaultNote="
                            f"{declared.get('documentedDefaultNote')!r}, "
                            f"manual says {manual.documented_default_note!r}"
                        )
                # Re-nesting introduces the containers the fields were moved
                # into, and those are documented - just in a different table of
                # the same section. /db/SECT's `SECT_BEFORE` is in the common
                # table and `SECT_I` in 12-A, and the SRC table describes
                # `SECT_I` as an Object without listing the members its own
                # example sends. Widen to the section, not to nothing: a name
                # that appears in no table here is still an invention.
                documented_names = (
                    {
                        field.key
                        for table in section.tables
                        for field in _walk(table.fields)
                    }
                    if renested
                    else set(variant_manual)
                )
                for key in variant_contract:
                    if _under_structural_destination(key, structural_paths, {}, section_names):
                        continue
                    if key not in variant_manual and key not in documented_names:
                        problems.append(
                            f"{path.name}: variant {label} declares {key!r}, which its manual table does not"
                        )

    print(f"checked {checked} promoted contract(s) against the manual")
    for note in skipped:
        print(f"  skipped {note}")
    if problems:
        print(f"\n{len(problems)} disagreement(s):")
        for problem in problems:
            print(f"  {problem}")
        print("\nA disagreement is not automatically the contract's fault. Where a live check")
        print("has disproved the manual, record it under manualDefects and set the field's")
        print("provenance to live_corrected - do not edit the contract back to match a manual")
        print("that has already been measured wrong.")
        return 1
    print("OK - no drift between the manual and the promoted contracts.")
    return 0


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manual-api-repo", type=Path, default=DEFAULT_MANUAL_REPO)
    parser.add_argument("--emit", nargs="+", metavar="ENDPOINT", help="write drafts for these endpoints or ids")
    parser.add_argument("--emit-all", action="store_true", help="write a draft for every parseable section")
    parser.add_argument("--check", action="store_true", help="check promoted contracts against the manual")
    parser.add_argument("--report", action="store_true", help="print extraction coverage and blocker counts (the default mode)")
    args = parser.parse_args(argv)

    sections, table_family = load_manual(args.manual_api_repo)

    if args.check:
        return run_check(sections)
    if args.emit or args.emit_all:
        return run_emit(sections, args.emit or [], args.emit_all)
    return run_report(sections, table_family)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
