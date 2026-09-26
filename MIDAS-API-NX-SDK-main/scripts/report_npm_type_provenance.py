"""Where each generated npm payload type's shape comes from, counted.

`npm run generate` no longer imports `midas_nx`, but it still reads the Python
**source tree** for every type no contract builds. Since 2026-09-22 that is the
only thing it reads it for: which types exist and in which namespace is decided
by the contracts for the types they own, and deleting a TypedDict a contract has
taken over changes nothing in `types.ts`. What is left is the types counted
here, which reached zero on 2026-09-22. Deleting `src/midas_nx/` still breaks
generation even so, because the IEHG trio's resource identity is read from the
same tree and has no permitted source to move to. `npm publish` is not
unaffected either, whatever this docstring said before 2026-09-23: it runs
`prepack`, which re-runs this generator through Python. An already-built
`dist/` still runs; publishing rebuilds it.

Until this script, the only measurement of it was a hand count in CLAUDE.md
-- the same kind of number `check_state_numbers.py` exists to stop trusting.

This counts it from the generated file. `_render_types` marks every interface
it builds from a contract with a one-line JSDoc, so the split is readable
without re-running the generator:

    contract        the contract supplied the field list
    python:nested   a named object *inside* a payload or an argument that no
                    contract's `surface.nestedTypes` claims, so its field list
                    is still Python's. What those are is broken down below.
    python:unmerged the contract declares `extraction.unmergedTables`, so
                    `_contract_payload_fields` skips it on purpose: narrowing a
                    published type onto an admittedly partial field list would
                    delete fields the manual documents in the table nobody
                    could merge. Merging those tables is a judgement task --
                    see docs/unmerged_tables_against_info.md.
    python:uncontracted  no contract names the type at all.
    python:contract-ignored  a contract names it, does not waive it, and the
                    generator built it from Python anyway. Always empty; a hit
                    is a generator defect, not a known gap.

One caveat on how the buckets are attributed: a payload name is matched
against the contracts by name alone, while the generator keys its lookup by
`(namespace, name)` -- `types.ts` is a stack of namespaces and 751
declarations carry 728 distinct names. That is only a risk for the two
contract-aware buckets, and today it is not one: `python:contract-ignored` is
empty and `python:unmerged` is exactly the waived contracts (an entry marked
`excluded` does not waive: see generate_typescript_sdk._admits_incomplete_fields).

Measured 2026-09-21 and 2026-09-22 across four generator changes: 478
Python-sourced types, then 250 once contracts could own a payload's **nested**
types (`surface.nestedTypes`), then 162 once an operation's **argument** type
and its nested types were built from the operation contract as well, then 138
once a table contract could describe its own request objects
(`requestFields.additional`), then 90 once a nested type could live inside a
single branch (or name the branch it is), conditions inside it were stated
from its own root, and the contracts' objects declared without members were
filled from each manual section's own JSON Schema, table rows or /info, then
85 and 83 once /db/SDIS's device tables and /db/CSCS's part table were
merged, then 82 once /db/TDME's two iGen-only tables could be marked
`excluded`, then 81 once /db/THIK's first table was read as the Value
branch it is headed as, then 80 once /db/EPMT's model tables were merged
into the six model objects, then 78 once /db/SPLC's four supplementary
tables were, two of them after a live measurement, and its aUSEMODE element
with them, then 77 once /db/STCT's erection-load table was,
then 76 once /db/ELEM's per-type tables became (TYPE, STYPE) variants,
then 70 once /db/MVLDpl's LOAD_MODEL groups were, with its five nested
types, then 68 once /db/SPFC's design-code tables were merged into STR, OPT
and VAL, then 66 once /db/THIS's mode tables were, with its COMMON, then
60 once /db/MVHL's country tables were, gated on MVLD_CODE after a live
measurement, with its five nested types, then 52 once /db/MVLD's national
DEFAULT tables were and its seven, which left no unmergedTables root, then
30 once /view/RESULTGRAPHIC's ten TYPE_OF_DISPLAY tables were merged as the
structural tables their headings say they are, with the section's top-level
keys, and its argument's 22 types came from the contract, then 16 once the
arguments held on Python were not: /ope/DIVIDEELEM's after a live measurement
of which axes each element type needs, the load-combination unions' KDS parts
through `argumentParts`, and SrcMemberCheckTableArgument once only a rendered
array bound counted as a shape difference, then 15 once /db/FIBR's colour
row was nested in FIMP_COLOR where it belongs and FiberDivisionColor named
there, then 14 once /ope/LCOM-SRC's contract, where the shared AIK-SRC2K
table lives, owned LoadCombinationAikSrc2kArgument, then 0 when the 12
nested and 2 uncontracted names left - every one an export the generated SDK
itself never referenced - were withdrawn from npm at the author's request.
`_PYTHON_TYPES_WITHDRAWN` in the generator lists them with their reasons;
the Python classes remain the Python package's own. What they were:

     1  /ope: _LoadCombinationSteelSrcKdsArgument, a Python base class
        nothing references now
     3  design: the two *DesignForcesArgument union parts and
        ColumnBraceRebarDesignCriteriaItem, a Python base class with no wire
        object of its own
     6  /db names whose contracts disagree - InitialLoadCaseItem (POGD-M1
        conditional, the others required), OptUseToleranceValue (ACTL-M1
        unstated), LoadGroupDayItem (STAG requires LOAD_NAME, HSTG does not);
        SectBefore, whose shape each SECTTYPE branch redeclares;
        InelasticMaterialKentParkParam, whose EC1 and Z the manual marks both
        Required though EC1_METHOD picks one, and whose example the product
        refuses (MD-54); and ItemGroupFields, a Python base class
     1  OpeTypes.AllowableStressLine, which nothing references
     1  /post: `PostStoryTypes.StorySetAngle`, the SET_ANGLE object four
        story tables share while the manual makes ANGLE required in two and
        optional in two, so no one declaration fits all four. Each table's
        own ADDITIONAL type inlines its version.

(Until 2026-09-22 this list called the /post types "table result types".
They were never results: all 25 were request objects - ADDITIONAL, UNIT,
STYLES, NODE_FLAG.)

`--check` also holds the number of exported types. The generator used to
refuse a `surface.nestedTypes` name the Python tree did not already publish, so
recording a name could never add an export. That refusal read the Python tree,
and went with the rest of it; this count is its replacement. Changing it is
changing the package surface, which the npm changelog has to say.

    python scripts/report_npm_type_provenance.py           # the breakdown
    python scripts/report_npm_type_provenance.py --check   # fail if it grows
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
from collections import Counter

import yaml

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

ROOT = pathlib.Path(__file__).resolve().parent.parent
TYPES = ROOT / "packages" / "typescript" / "src" / "generated" / "types.ts"
CONTRACTS = ROOT / "contracts" / "endpoints"

#: Measured 2026-09-22 over 751 generated types, after branch-owned nested types. A ceiling: it falls as
#: contracts take over more of the emitted shape, and a rise means a type that
#: used to come from a contract is being read out of the Python tree again.
PYTHON_SOURCED_AT_MOST = 0

#: Every exported type in `types.ts`. Not a ceiling: adding or removing an
#: export is a change to the published surface, so it has to be made here on
#: purpose, together with the changelog entry that says so.
EXPORTED_TYPES = 751

#: A table contract builds the request-option types of one result table
#: (`requestFields.additional`), and marks them with where they came from.
CONTRACT_MARKERS = (
    "/** Generated from contracts/endpoints/. */",
    "/** Generated from contracts/tables/. */",
)
_EXPORT = re.compile(r"^export (?:interface|type) (\w+)")


def _contract_payload_names() -> tuple[set[str], set[str]]:
    """Payload type names a contract claims, split by the unmergedTables waiver."""
    named: set[str] = set()
    waived: set[str] = set()
    for path in sorted(CONTRACTS.glob("*.yaml")):
        contract = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        name = (contract.get("surface") or {}).get("payloadTypeName")
        if not isinstance(name, str):
            continue
        named.add(name)
        if any(
            not entry.get("excluded")
            for entry in (contract.get("extraction") or {}).get("unmergedTables") or []
        ):
            waived.add(name)
    return named, waived


def classify() -> dict[str, list[str]]:
    """Every exported type in the generated file, by where its shape came from."""
    named, waived = _contract_payload_names()
    found: dict[str, list[str]] = {
        "contract": [],
        "python:nested": [],
        "python:unmerged": [],
        "python:uncontracted": [],
        "python:contract-ignored": [],
    }
    previous_line_marked = False
    for line in TYPES.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        match = _EXPORT.match(stripped)
        if match:
            name = match.group(1)
            if previous_line_marked:
                bucket = "contract"
            elif not name.endswith("Payload"):
                # A nested object. The generator emits the payload root from
                # the contract and leaves everything under it to Python.
                bucket = "python:nested"
            elif name in waived:
                bucket = "python:unmerged"
            elif name in named:
                bucket = "python:contract-ignored"
            else:
                bucket = "python:uncontracted"
            found[bucket].append(name)
        previous_line_marked = stripped in CONTRACT_MARKERS
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true",
        help="exit 1 if more types come from the Python tree than the ceiling",
    )
    args = parser.parse_args()

    found = classify()
    counts = Counter({bucket: len(names) for bucket, names in found.items()})
    python_sourced = sum(count for bucket, count in counts.items() if bucket != "contract")
    total = sum(counts.values())

    if args.check:
        if total != EXPORTED_TYPES:
            print(
                f"types.ts exports {total} types, {EXPORTED_TYPES} expected. Adding or "
                "removing an export changes the npm package surface: update "
                "EXPORTED_TYPES and say so in packages/typescript/CHANGELOG.md.",
                file=sys.stderr,
            )
            return 1
        if python_sourced > PYTHON_SOURCED_AT_MOST:
            print(
                f"npm payload types read out of the Python source tree grew from "
                f"{PYTHON_SOURCED_AT_MOST} to {python_sourced}:",
                file=sys.stderr,
            )
            for bucket in (
                "python:contract-ignored", "python:uncontracted",
                "python:unmerged", "python:nested",
            ):
                print(f"  {bucket}: {counts[bucket]}", file=sys.stderr)
            print(
                "(Hint: a contract taking over a type lowers this. A rise means "
                "generation fell back to Python for something a contract had.)",
                file=sys.stderr,
            )
            return 1
        print(
            f"OK - {python_sourced} of {total} generated types come from the Python "
            f"source tree, ceiling {PYTHON_SOURCED_AT_MOST}; {total} exported, as recorded."
        )
        return 0

    print(f"{total} generated npm types:")
    for bucket in (
        "contract", "python:nested", "python:unmerged", "python:uncontracted",
        "python:contract-ignored",
    ):
        print(f"  {bucket:22} {counts[bucket]:>4}")
    print(f"\n  {'python total':22} {python_sourced:>4}  (ceiling {PYTHON_SOURCED_AT_MOST})")
    for bucket in ("python:unmerged", "python:uncontracted", "python:contract-ignored"):
        if found[bucket]:
            print(f"\n{bucket}:")
            for name in sorted(found[bucket]):
                print(f"  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
