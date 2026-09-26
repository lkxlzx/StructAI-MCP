"""Fill a Hyper-S draft's `fields` from the server's own `/info` schema.

Seven ``-M1`` sections in ``04_DB_Properties.md`` are stubs: a URL, a methods
line, a Zendesk link and a one-line GET snippet. ``extract_contracts.py``
reads them correctly and says so - it emits a draft with everything except a
request shape, because the manual states none. Their only permitted source is
live ``/info`` introspection, captured in ``schema/hyper-s-info.json``.

This script does one thing: it takes that draft and writes the ``fields``
block from the captured schema, leaving every other decision the extractor
made alone. The manual still states what the endpoint is and which methods it
serves; ``/info`` states what the request looks like. Splitting it that way
means a manual sync still governs the half the manual owns.

What it will not do
-------------------
Read anything into the schema that the schema does not say.

``/info`` declares no ``required`` array, so every field is ``unstated`` - not
optional, which would be a claim nobody has made. Descriptions carry value
mappings (``Model Type (Tresca:0, VonMises:1, ...)``) that the schema does not
encode as an ``enum`` or a discriminator; those become a review note rather
than a transcription, because turning prose into a variant is a judgment about
the endpoint, not a fact about the capture.

Two defects in the served schemas are registered as MD-12 and are handled
here: apostrophes escaped with a backslash (not a JSON escape) are repaired in
the prose, and ``maxItems`` stated on an array's ``items`` subschema instead of
the array is noted rather than transcribed - the same rule the extractor
already applies to a bound the manual states for the wrong kind of value.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import extract_contracts

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "schema" / "hyper-s-info.json"
DRAFT_DIR = ROOT / "contracts" / "drafts"

#: A description that names values for its own field, e.g.
#: "Model Type (Tresca:0, VonMises:1, MohrCoulomb:2)". The schema does not
#: encode these, so they are reported, never transcribed.
VALUE_MAP = re.compile(
    r"\(\s*[A-Za-z][\w .\-]*\s*:\s*-?\d+\s*(?:,\s*[A-Za-z][\w .\-]*\s*:\s*-?\d+\s*)+\)"
)

FIELDS_PLACEHOLDER = (
    "# No parameter table could be parsed from this section. Transcribe the\n"
    "# fields by hand, or check whether the endpoint takes no payload at all.\n"
    "fields: []\n"
)

JUSTIFICATION = (
    "The chapter section for this endpoint states only a URL, its methods and\n"
    "      a link to the official article - it carries no Specifications table and no\n"
    "      JSON Schema, so the manual describes the endpoint's existence but not its\n"
    "      request. The fields below come from GET /info{endpoint}, captured in\n"
    "      schema/hyper-s-info.json; the methods and the label above are still the\n"
    "      manual's. Registered as MD-12."
)


def _clean(text: str) -> str:
    """Trim the served description and repair MD-12's invalid escape."""

    return text.replace(chr(92) + "'", "'").strip()


def _fold(text: str, indent: str) -> list[str]:
    """Render a description as a YAML folded block, as the extractor does."""

    words, lines, current = text.split(), [], ""
    for word in words:
        if current and len(current) + len(word) + 1 > 72:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return [f"{indent}description: >-"] + [f"{indent}  {line}" for line in lines or [""]]


def _notes_for(key: str, node: dict[str, Any], description: str) -> list[str]:
    notes = []
    mapping = VALUE_MAP.search(description)
    if mapping:
        notes.append(
            f"the served description names values for this field - "
            f"{mapping.group(0)} - but /info declares neither an enum nor any "
            f"conditional structure, so the values live in the description and "
            f"no variant is built from this capture. That is a fact about the "
            f"source, not a reading of this endpoint: an /info schema is flat "
            f"and states no branch anywhere. A gate on these values would have "
            f"to come from the manual or from a live observation, and the "
            f"sibling contracts drafted from identical prose keep the values in "
            f"the description too"
        )
    items = node.get("items")
    if isinstance(items, dict):
        stray = sorted(k for k in ("maxItems", "minItems") if k in items)
        for bound in stray:
            notes.append(
                f"the served schema states {bound}={items[bound]} on this "
                f"array's items subschema rather than on the array, where "
                f"JSON Schema ignores it, so it is not transcribed (MD-12)"
            )
    return notes


def _field_lines(key: str, node: dict[str, Any], indent: str) -> list[str]:
    description = _clean(str(node.get("description", "")))
    declared = str(node.get("type", ""))
    lines = [f"{indent}- key: {key}"]
    body = indent + "  "
    lines += _fold(description or key, body)
    lines.append(f"{body}type: {declared}")

    items = node.get("items")
    if declared == "array" and isinstance(items, dict):
        lines.append(f"{body}items:")
        lines.append(f"{body}  type: {items.get('type', 'object')}")

    lines += [
        f"{body}requirement: unstated",
        f"{body}documentedDefault: null",
        # `unstated` and a documentedOptional of false would disagree: false is a
        # claim the docs say it is not optional, and they say nothing at all.
        f"{body}documentedOptional: null",
        f"{body}safeToOmit: unverified",
        f"{body}provenance: info_schema",
    ]

    for note in _notes_for(key, node, description):
        wrapped = _fold(note, body)[1:]
        marker = extract_contracts._note_marker(note)
        lines.append(f"{body}# {marker}: {wrapped[0].strip()}")
        lines += [f"{body}# {line.strip()}" for line in wrapped[1:]]

    children = node.get("properties")
    if not children and isinstance(items, dict):
        children = items.get("properties")
    if children:
        lines.append(f"{body}properties:")
        for child_key, child in children.items():
            lines += _field_lines(child_key, child, body + "  ")
    return lines


def render_fields(properties: dict[str, Any]) -> str:
    lines = ["fields:"]
    for key, node in properties.items():
        lines += _field_lines(key, node, "  ")
    return "\n".join(lines) + "\n"


def _argument_properties(schema: dict[str, Any]) -> dict[str, Any]:
    """`/info` wraps the request in `Argument`, exactly as the manual does."""

    argument = schema.get("Argument", schema)
    properties = argument.get("properties")
    if not isinstance(properties, dict):
        raise SystemExit("the captured schema has no Argument.properties")
    return properties


def fill(draft: Path, properties: dict[str, Any]) -> str:
    text = draft.read_text(encoding="utf-8")
    if FIELDS_PLACEHOLDER not in text:
        raise SystemExit(f"{draft.name}: expected the extractor's empty-fields block")

    text = text.replace(FIELDS_PLACEHOLDER, render_fields(properties))
    text = text.replace(
        "    status: documented\n",
        f"    status: absent\n    justification: >-\n      {JUSTIFICATION}\n",
        1,
    )
    return text.replace(
        "# Then run: python scripts/validate_contracts.py",
        "# The `fields` block below was written by scripts/contract_from_info.py from\n"
        "# schema/hyper-s-info.json, not from the manual - this section has no table.\n"
        "# Every field is `unstated`: /info declares no `required` array, and\n"
        "# `optional` would be a claim nobody has made.\n"
        "#\n"
        "# Then run: python scripts/validate_contracts.py",
        1,
    )


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("endpoints", nargs="*", help="e.g. /db/MATL-M1; default: all captured")
    parser.add_argument("--artifact", type=Path, default=ARTIFACT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    captured = json.loads(args.artifact.read_text(encoding="utf-8"))["endpoints"]
    wanted = args.endpoints or sorted(captured)

    written = 0
    for endpoint in wanted:
        record = captured.get(endpoint)
        if record is None:
            print(f"  {endpoint}: not in {args.artifact.name}")
            continue
        if record["status"] != 200:
            print(f"  {endpoint}: {record['status']} on /info - no schema to read")
            continue

        slug = endpoint.strip("/").lower().replace("/", "-")
        draft = DRAFT_DIR / f"{slug}.yaml"
        if not draft.exists():
            print(f"  {endpoint}: no draft at {draft.relative_to(ROOT)} - run extract_contracts.py --emit-all")
            continue

        properties = _argument_properties(record["schema"])
        filled = fill(draft, properties)
        if not args.dry_run:
            draft.write_text(filled, encoding="utf-8")
        count = filled.count("- key: ")
        print(f"  {endpoint}: {count} field(s) from /info -> {draft.relative_to(ROOT)}")
        written += 1

    print(f"\nfilled {written} draft(s){' (dry run)' if args.dry_run else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
