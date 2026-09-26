"""Scaffold a new endpoint's boilerplate (TypedDict + DbResource subclass +
mirror test) from its section in a MIDAS-API manual chapter file.

New-endpoint additions in this SDK always follow the same three-part
pattern (see e.g. src/midas_nx/db/node_element.py + tests/db/test_node_element.py),
transcribed by hand from the manual's per-endpoint "### Specifications"
table. This script generates a first-draft version of that boilerplate so a
contributor edits/reviews instead of retyping from scratch.

This is deliberately semi-automatic, not a full generator: manual chapters
are hand-written prose and their tables are not fully uniform across
chapters (conditional/nested fields, footnote markers, STYPE-dependent
groups, ...). Always read the generated TypedDict against the manual
section itself before committing — this script gets the common case (flat
Specifications table) right and leaves everything else as `Any` for a
human to fix.

Usage (from a checkout that sits next to the MIDAS-API repo):
    python scripts/gen_endpoint.py <path-to-chapter.md> <endpoint> --class-name <Name>

Example:
    python scripts/gen_endpoint.py ../MIDAS-API/docs/manual/05_DB_Boundary.md \\
        /db/CONS --class-name Constraint

Prints the generated TypedDict, DbResource subclass, and test stub to
stdout; pass --out to also write them to a file.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vendor_coverage import CIVIL_ONLY_CHAPTERS  # noqa: E402

_TYPE_MAP = {
    "number": "float",
    "integer": "int",
    "string": "str",
    "boolean": "bool",
    "object": "dict",
}

# Chapter files aren't uniform in how they mark up a section's heading,
# methods line, and spec-table heading (compare e.g. 03_DB_Node_Element.md's
# "## 1. `/db/NODE`" + "- **Methods**:" + "### Specifications" against
# 08_DB_Moving_Loads.md's "## 1. /db/MVCD – Moving Load Code" + "**Active
# Methods**:" + "### Parameters"). These patterns cover both known styles;
# a chapter using a third style will simply fail to match (see main()'s
# "not found" error) rather than silently produce a wrong result.
_HEADING_RE = re.compile(r"^##\s+\d+\.\s+`(/[^`]+)`\s*$|^##\s+\d+\.\s+(/\S+)\s*[–-]\s*(.+)$")
_NAME_DESC_RE = re.compile(r"^>\s*\*\*(.+?)\*\*\s*—\s*(.+)$")
_METHODS_RE = re.compile(r"^-?\s*\*\*(?:Active )?Methods\*\*:\s*(.+)$")
_SPEC_HEADING_RE = re.compile(r"^###\s+(?:Specifications|Parameters)\s*$")
_SUBSECTION_RE = re.compile(r"^#{2,3}\s+")
_EMPTY_DEFAULT = {"-", "–", ""}


def _map_type(value_type: str) -> str:
    array_match = re.match(r"Array\[(.+)\]$", value_type.strip(), re.IGNORECASE)
    if array_match:
        return f"List[{_map_type(array_match.group(1))}]"
    if value_type.strip().lower() == "array":
        return "List[Any]"
    return _TYPE_MAP.get(value_type.strip().lower(), "Any")


def _field_comment(description: str, default: str, required: bool) -> str:
    comment = description
    if not required and default not in _EMPTY_DEFAULT:
        comment += f", default {default}"
    comment += ", required" if required else ", optional"
    return comment


def _parse_spec_rows(lines: list[str]) -> list[dict]:
    raw = []
    for line in lines:
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 6 or not cells[0].isdigit():
            continue
        _, description, key_cell, value_type, default, required_cell = cells
        key_match = re.search(r'`"(\w+)"`', key_cell)
        if not key_match:
            continue
        raw.append({
            "key": key_match.group(1),
            "description": description,
            "py_type": _map_type(value_type),
            "default": default,
            "required": "required" in required_cell.lower(),
        })

    # Some tables (e.g. /db/ELEM) list the same key once per STYPE-subtype
    # branch. A TypedDict can't have field-level conditions, and a class body
    # with a repeated annotation silently keeps only the last one — so
    # collapse repeats into a single field instead of emitting duplicates.
    by_key: dict[str, dict] = {}
    order = []
    for f in raw:
        if f["key"] not in by_key:
            by_key[f["key"]] = dict(f, occurrences=1)
            order.append(f["key"])
        else:
            by_key[f["key"]]["occurrences"] += 1

    fields = []
    for key in order:
        f = by_key[key]
        if f.pop("occurrences") > 1:
            f["description"] += " (meaning/requiredness varies by subtype — see manual)"
            f["required"] = False
        fields.append(f)
    return fields


def parse_endpoint_section(chapter_path: Path, endpoint: str) -> dict:
    lines = chapter_path.read_text(encoding="utf-8").splitlines()

    start = None
    heading_name = None
    for i, line in enumerate(lines):
        m = _HEADING_RE.match(line)
        if not m:
            continue
        matched_endpoint = m.group(1) or m.group(2)
        if matched_endpoint == endpoint:
            start = i
            heading_name = m.group(3)  # set only for the bare "N. /path – Name" style
            break
    if start is None:
        raise ValueError(f"{endpoint} not found as a '## N. ...' heading in {chapter_path}")

    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    section = lines[start:end]

    name = heading_name or endpoint.rsplit("/", 1)[-1]
    description, methods = "", ["POST", "GET", "PUT", "DELETE"]
    for line in section:
        m = _NAME_DESC_RE.match(line)
        if m:
            name, description = m.group(1), m.group(2)
            continue
        m = _METHODS_RE.match(line)
        if m:
            methods = [tok.strip().strip("`") for tok in m.group(1).split(",")]

    spec_start = None
    for i, line in enumerate(section):
        if _SPEC_HEADING_RE.match(line):
            spec_start = i + 1
            break
    fields = []
    if spec_start is not None:
        spec_end = len(section)
        for i in range(spec_start, len(section)):
            if _SUBSECTION_RE.match(section[i]):
                spec_end = i
                break
        fields = _parse_spec_rows(section[spec_start:spec_end])

    return {
        "endpoint": endpoint,
        "name": name,
        "description": description,
        "methods": methods,
        "fields": fields,
        "civil_only": chapter_path.name in CIVIL_ONLY_CHAPTERS,
    }


def render(info: dict, class_name: str, chapter_path: Path) -> str:
    payload_lines = [f'class {class_name}Payload(TypedDict, total=False):']
    payload_lines.append(f'    """docs/manual/{chapter_path.name} — {info["endpoint"]} Specifications table."""')
    payload_lines.append("")
    if not info["fields"]:
        payload_lines.append(
            "    # NOTE: no '### Specifications' table found/parsed for this endpoint — "
            "add fields by hand from the manual section."
        )
    for f in info["fields"]:
        comment = _field_comment(f["description"], f["default"], f["required"])
        payload_lines.append(f'    {f["key"]}: {f["py_type"]}  # {comment}')
    payload_src = "\n".join(payload_lines)

    methods = set(info["methods"])
    methods_line = ""
    if methods != {"POST", "GET", "PUT", "DELETE"}:
        methods_line = f'\n    METHODS = frozenset({sorted(methods)!r})'
    products = 'frozenset({"civil"})' if info["civil_only"] else 'frozenset({"gen", "civil"})'

    resource_src = (
        f'class {class_name}(DbResource):\n'
        f'    ENDPOINT = "{info["endpoint"]}"\n'
        f'    NAME = "{info["name"]}"\n'
        f'    PRODUCTS = {products}'
        f'{methods_line}'
    )

    required_fields = [f for f in info["fields"] if f["required"]]
    sample_fields = required_fields or info["fields"][:2]
    sample_body = ", ".join(f'"{f["key"]}": None' for f in sample_fields) or "..."
    client_fixture = "civil_client" if info["civil_only"] else "gen_client"
    test_src = (
        f'@responses.activate\n'
        f'def test_{class_name.lower()}_create_sends_documented_assign_shape({client_fixture}):\n'
        f'    responses.add(responses.POST, "https://x.test:443/'
        f'{"civil" if info["civil_only"] else "gen"}{info["endpoint"]}", json={{}}, status=200)\n\n'
        f'    {class_name}.create({{1: {{{sample_body}}}}}, client={client_fixture})\n\n'
        f'    sent = responses.calls[0].request\n'
        f'    assert json.loads(sent.body) == {{"Assign": {{"1": {{{sample_body}}}}}}}\n'
        f'    # TODO: replace None placeholders with values matching the manual\'s example.'
    )

    return (
        f"# --- TypedDict + DbResource (paste into src/midas_nx/...) ---\n\n"
        f"{payload_src}\n\n\n{resource_src}\n\n\n"
        f"# --- mirror test (paste into tests/db/...) ---\n\n{test_src}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("chapter_md", help="path to a MIDAS-API docs/manual/*.md chapter file")
    parser.add_argument("endpoint", help='e.g. "/db/CONS"')
    parser.add_argument("--class-name", required=True, help="e.g. Constraint")
    parser.add_argument("--out", help="path to also write the generated snippet to")
    args = parser.parse_args()

    chapter_path = Path(args.chapter_md)
    try:
        info = parse_endpoint_section(chapter_path, args.endpoint)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    output = render(info, args.class_name, chapter_path)
    sys.stdout.reconfigure(encoding="utf-8")
    print(output)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
    if not info["fields"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
