"""Check every live CRUD fixture against the contract for its endpoint.

The repository already compares contracts against both SDKs, against `/info`,
and against the manual.  Nothing compared them against the **fixtures**, which
is the fourth thing that claims to know an endpoint's shape -- and the one that
decides what a live run actually sends. Its current baseline has 1 fixture
lead on 1 endpoint and 3 contract gaps on two confirmed endpoints.

The remaining fixture-side lead is on a case nobody has watched pass:
`/db/ACTL` sends `CLATS` on Gen even though the contract tags it Civil-only.
The former GRDP/MVCT/NLNK-M1/TDMF findings were closed from the vendored
manual: one fixture was incomplete and three contracts had failed to encode
the manual's explicit branch conditions.

The confirmed side reads the other way round. The product accepted that exact
payload, so the contract is what is behind: today that is `/db/SPLC` omitting
`NDP`. (`/db/SDIS` was the other until 2026-09-22, when its LRB/NRB/SB objects
gained the `SDIS_DEV_TYPE` condition their rows state.) A
`safeToOmit: true` field is already the record of an accepted call that left
it out, so it is not counted again.

Three things are checked per case, per product it declares:

1. a key the contract tags for the *other* product only;
2. a `required` key the payload omits;
3. a key no contract field records -- unless an `extraction.unmergedTables`
   entry lists it, which is the same per-name waiver `check_field_parity` uses.
   A declared gap is a gap; a name in neither place is a defect.

Only top-level keys are compared. Variant keys count as recorded, and
`appliesWhen` decides whether a root field is required for the selected
payload branch. Most contracts do not itemise nested members, so descending
would report the contract's own known gaps as fixture defects, which is the
opposite of useful.

    python scripts/check_fixture_contract.py            # report
    python scripts/check_fixture_contract.py --check    # exit 1 on a new one

`--check` holds both lists as a recorded baseline.  A finding that goes away
fails too, so a fix has to be recorded rather than absorbed.  Fix the fixture
rather than widening the baseline; and closing a contract gap takes a permitted
source -- the manual, `/info`, or a recorded live observation.  **A fixture is
never a source for a contract**, which is why these are held here and not
merged.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Dict, List, Set, Tuple

import yaml

sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "schema" / "live-cases.json"
CONTRACTS = ROOT / "contracts" / "endpoints"

#: What the first run found, endpoint -> sorted list of "kind: key" strings.
#: These are live-reproduced fixture defects, not exemptions: each one has a
#: failing case behind it and belongs to Task 4's write-coverage push. Removing
#: an entry is the goal; adding one needs the same standard of evidence.
#: What the current tree reports, split the way scan() splits it.
#:
#: KNOWN is the fixture side: cases nobody has watched pass whose payload the
#: contract does not license. Each is a lead for Task 4's write-coverage push,
#: not an exemption -- removing an entry is the goal.
#:
#: KNOWN_CONTRACT_GAPS is the other side, and reads the opposite way: the
#: product accepted these payloads, so the contract is what is behind. Closing
#: one takes a permitted source -- the manual, /info, or a recorded live
#: observation. A fixture is never a source for a contract, which is why these
#: are held here rather than merged.
KNOWN: Dict[str, List[str]] = {
    '/db/ACTL': ['gen: sends CLATS, tagged civil-only'],
}

KNOWN_CONTRACT_GAPS: Dict[str, List[str]] = {}

BOTH = ("civil", "gen")


def _contracts() -> Dict[str, dict]:
    found: Dict[str, dict] = {}
    for path in sorted(CONTRACTS.glob("*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(document, dict) and document.get("endpoint"):
            found[document["endpoint"]] = document
    return found


def _waived_names(document: dict) -> Set[str]:
    """Names an `extraction.unmergedTables` entry accounts for."""
    waived: Set[str] = set()
    extraction = document.get("extraction") or {}
    for table in extraction.get("unmergedTables") or []:
        waived.update(table.get("fieldNames") or [])
    for field in document.get("fields") or []:
        if field.get("sdkOnly"):
            waived.add(field["key"])
    return waived


def _findings(case: dict, document: dict) -> List[str]:
    def matches(conditions: list, payload: dict) -> bool:
        """Whether a structured manual condition is active for a payload."""
        for condition in conditions:
            value = payload
            for part in condition["path"].split("."):
                if not isinstance(value, dict) or part not in value:
                    return False
                value = value[part]
            if "equals" in condition and value != condition["equals"]:
                return False
            if "in" in condition and value not in condition["in"]:
                return False
        return True

    base_fields = document.get("fields") or []
    variants = document.get("variants") or []
    variant_fields = [field for variant in variants for field in variant.get("fields") or []]
    recorded = {field["key"] for field in base_fields + variant_fields}
    waived = _waived_names(document)
    keys = set(case["createPayload"]) | set(case["updatePayload"])
    out: List[str] = []
    # Variant fields may be top-level branches (MVLDch) or rows belonging to
    # an already-declared nested object (MVLDbs). They count as recorded wire
    # names, but this intentionally top-level checker must not guess which
    # variant fields are required at the record root.
    fields = base_fields

    for product in sorted(case["products"]):
        for field in fields:
            products = field.get("products") or list(BOTH)
            if product not in products and field["key"] in keys:
                other = "/".join(sorted(products))
                out.append(f"{product}: sends {field['key']}, tagged {other}-only")
            if (field.get("requirement") == "required"
                    and product in products and field["key"] not in keys
                    and (matches(field.get("appliesWhen") or [], case["createPayload"])
                         or matches(field.get("appliesWhen") or [], case["updatePayload"]))
                    and field.get("safeToOmit") is not True):
                # safeToOmit: true already records that an accepted call left
                # this field out -- extract_contracts.py derives it from these
                # same confirmed payloads. Reporting it again would count a
                # read observation as an unread one, which is the mistake this
                # tool exists to avoid making about fixtures.
                out.append(f"{product}: omits required {field['key']}")
        for key in sorted(keys - recorded - waived):
            out.append(f"{product}: sends {key}, recorded nowhere")
    return sorted(set(out))


def scan() -> Tuple[Dict[str, List[str]], Dict[str, List[str]], int]:
    """Findings split by whether the case has ever passed live.

    The same disagreement means opposite things on the two sides. On a case
    nobody has watched pass, a payload the contract does not license is a lead
    about the **fixture**. On a `confirmed` case, the product accepted that
    exact payload, so the disagreement is evidence about the **contract**: a
    name it records nowhere is a field it is missing, and a `required` field
    the call omitted is a requirement the product does not enforce -- which is
    exactly what `safeToOmit` wants and only 140 of 5,078 fields have.

    Neither list is actionable by itself. A contract is fixed from a permitted
    source, never from a fixture.
    """
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    documents = _contracts()
    unconfirmed: Dict[str, List[str]] = {}
    confirmed: Dict[str, List[str]] = {}
    checked = 0
    for case in fixture["cases"]:
        document = documents.get(case["endpoint"])
        if not document:
            continue
        checked += 1
        found = _findings(case, document)
        if not found:
            continue
        into = confirmed if case["confirmed"] else unconfirmed
        into[case["endpoint"]] = sorted(set(into.get(case["endpoint"], [])) | set(found))
    return unconfirmed, confirmed, checked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if a finding is new or changed")
    args = parser.parse_args()

    findings, confirmed, checked = scan()
    print(f"Checked {checked} live cases against their contracts.\n")

    print("== Never passed live: a lead about the FIXTURE ==")
    for endpoint in sorted(findings):
        print(f"\n{endpoint}")
        for line in findings[endpoint]:
            print(f"  {line}")
    if not findings:
        print("  none")

    print("\n\n== Confirmed live: the product accepted this exact payload, so the")
    print("   disagreement is evidence about the CONTRACT, not the fixture ==")
    for endpoint in sorted(confirmed):
        print(f"\n{endpoint}")
        for line in confirmed[endpoint]:
            print(f"  {line}")
    if not confirmed:
        print("  none")

    if not args.check:
        return 0

    problems: List[str] = []
    for endpoint in sorted(set(findings) | set(KNOWN)):
        now, was = findings.get(endpoint, []), KNOWN.get(endpoint, [])
        problems += [f"NEW      {endpoint}: {line}" for line in sorted(set(now) - set(was))]
        problems += [f"RESOLVED {endpoint}: {line} -- drop it from KNOWN"
                     for line in sorted(set(was) - set(now))]
    for endpoint in sorted(set(confirmed) | set(KNOWN_CONTRACT_GAPS)):
        now, was = confirmed.get(endpoint, []), KNOWN_CONTRACT_GAPS.get(endpoint, [])
        problems += [f"NEW      {endpoint}: {line} (confirmed live)"
                     for line in sorted(set(now) - set(was))]
        problems += [f"RESOLVED {endpoint}: {line} -- drop it from KNOWN_CONTRACT_GAPS"
                     for line in sorted(set(was) - set(now))]
    if problems:
        print("\n\nBaseline moved:")
        for line in problems:
            print(f"  {line}")
        return 1
    print(f"\n\nBaseline holds: {sum(len(v) for v in KNOWN.values())} fixture leads "
          f"across {len(KNOWN)} endpoints, and "
          f"{sum(len(v) for v in KNOWN_CONTRACT_GAPS.values())} live-confirmed "
          f"contract gaps across {len(KNOWN_CONTRACT_GAPS)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
