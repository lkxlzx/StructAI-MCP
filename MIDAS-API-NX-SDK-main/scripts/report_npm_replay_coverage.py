"""Report npm live-replay coverage from the authoritative coverage ledger.

``--check`` enforces two things about every ledger entry carrying the replay
marker: that the endpoint has a shared fixture, and that a session record backs
it. The second exists because the first cannot see a claim that was never run.
Three entries were written on 2026-09-16 citing a notes section that does not
mention them, and every derived number was 3 too high until they were found by
hand -- the ledger is authoritative, so nothing else would have caught it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verification_ledger import load_records  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "schema" / "live-cases.json"
DEFAULT_LEDGER = ROOT / "contracts" / "verification" / "ledger.yaml"
DEFAULT_INVENTORY = ROOT / "docs" / "npm_live_evidence_scratch.md"
REPLAY_MARKER = "npm replayed the same emitted fixture"
#: An inventory row: | `/db/NODE` | 2026-08-31 | Gen, Civil |
INVENTORY_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|([^|]*)\|([^|]*)\|")
PRODUCT = re.compile(r"gen|civil", re.IGNORECASE)


def confirmed_case_endpoints(cases_path: Path) -> set[str]:
    """Return endpoints whose shared fixture has a confirmed Python case."""
    fixture = json.loads(cases_path.read_text(encoding="utf-8"))
    return {
        case["endpoint"]
        for case in fixture["cases"]
        if case.get("confirmed") is True
    }


def npm_replayed_endpoints(ledger_path: Path | None = None) -> set[str]:
    """Return endpoints whose ledger evidence explicitly records npm replay.

    Reads contracts/verification/ledger.yaml, which took over live evidence
    from docs/coverage.json on 2026-09-21.
    """
    replayed: set[str] = set()
    for record in load_records(ledger_path):
        if REPLAY_MARKER in (record.get("method") or ""):
            replayed.update(record.get("endpoints") or [])
    return replayed


def inventoried_products(inventory_path: Path) -> dict[str, set[str]]:
    """Return {endpoint: products} from the npm evidence inventory.

    An endpoint can appear in several rows - different batches, different
    products, different days - so products are unioned across them.
    """
    found: dict[str, set[str]] = {}
    for line in inventory_path.read_text(encoding="utf-8").splitlines():
        match = INVENTORY_ROW.match(line)
        if match is None:
            continue
        found.setdefault(match.group(1), set()).update(
            product.lower() for product in PRODUCT.findall(match.group(3))
        )
    return found


def inventoried_endpoints(inventory_path: Path) -> set[str]:
    """Return every endpoint the npm evidence inventory records a run for.

    The inventory is the session-by-session record; the ledger is the claim.
    A claim the inventory does not carry is one nobody wrote a session down
    for, whether it was never run or only never recorded.
    """
    return set(inventoried_products(inventory_path))


def case_coverage(
    cases_path: Path, inventory_path: Path
) -> tuple[int, dict[str, set[str]], list[str], dict[str, set[str]]]:
    """Return npm coverage measured in confirmed **cases**, not endpoints.

    An endpoint is not the unit the fixture works in: `/db/HHCT` carries a
    confirmed Gen case and an unconfirmed Civil one, so "has npm replayed
    /db/HHCT" has no answer. The case does have one, and the inventory records
    the products each run covered, so the two can be compared directly.

    Returns the number of cases npm covered on every product they declare, the
    ones it covered on only some (endpoint -> the products still missing), the
    ones with no run recorded at all, and any endpoint whose inventory row
    claims a product its confirmed case does not declare.
    """
    fixture = json.loads(cases_path.read_text(encoding="utf-8"))
    recorded = inventoried_products(inventory_path)
    #: Every product any case for the endpoint declares, confirmed or not. A
    #: run against an unconfirmed case is still a real run, so comparing an
    #: inventory row against the confirmed case alone reports false labels -
    #: /db/HHCT's Civil case is unconfirmed and npm ran it.
    any_case: dict[str, set[str]] = {}
    for case in fixture["cases"]:
        any_case.setdefault(case["endpoint"], set()).update(
            product.lower() for product in case["products"]
        )
    complete = 0
    partial: dict[str, set[str]] = {}
    missing: list[str] = []
    mislabelled: dict[str, set[str]] = {}
    for case in fixture["cases"]:
        if case.get("confirmed") is not True:
            continue
        endpoint = case["endpoint"]
        declared = {product.lower() for product in case["products"]}
        covered = recorded.get(endpoint, set())
        if not covered:
            missing.append(endpoint)
            continue
        if declared - covered:
            partial[endpoint] = declared - covered
        else:
            complete += 1
        if covered - any_case.get(endpoint, set()):
            mislabelled[endpoint] = covered - any_case[endpoint]
    return complete, partial, sorted(missing), mislabelled


def report(
    cases_path: Path, ledger_path: Path, inventory_path: Path | None = None
) -> tuple[int, int, int, set[str], set[str]]:
    """Return confirmed, confirmed-replayed, remaining, unknown and unbacked."""
    fixture = json.loads(cases_path.read_text(encoding="utf-8"))
    case_endpoints = {case["endpoint"] for case in fixture["cases"]}
    confirmed = {
        case["endpoint"]
        for case in fixture["cases"]
        if case.get("confirmed") is True
    }
    replayed = npm_replayed_endpoints(ledger_path)
    unknown = replayed - case_endpoints
    unbacked: set[str] = set()
    if inventory_path is not None:
        unbacked = replayed - inventoried_endpoints(inventory_path)
    return (
        len(confirmed),
        len(replayed & confirmed),
        len(confirmed - replayed),
        unknown,
        unbacked,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the ledger marks an endpoint with no shared fixture, or "
             "one the npm evidence inventory records no session for",
    )
    args = parser.parse_args(argv)

    confirmed, replayed, remaining, unknown, unbacked = report(
        args.cases, args.ledger, args.inventory
    )
    total_replayed = len(npm_replayed_endpoints(args.ledger))
    print(f"confirmed Python fixture endpoints: {confirmed}")
    print(f"npm replayed fixture endpoints: {total_replayed} ({replayed} confirmed)")
    print(f"remaining npm replay gap: {remaining}")

    complete, partial, missing, mislabelled = case_coverage(args.cases, args.inventory)
    total_cases = complete + len(partial) + len(missing)
    print()
    print(f"by confirmed case, which is the unit the fixture works in "
          f"({total_cases} cases over {confirmed} endpoints):")
    print(f"  npm ran every declared product: {complete}")
    print(f"  npm ran only some             : {len(partial)}")
    print(f"  npm ran none                  : {len(missing)}")
    for endpoint, products in sorted(partial.items()):
        print(f"    {endpoint} still needs {', '.join(sorted(products))}")
    if mislabelled:
        print("  inventory records a product the confirmed case does not declare:")
        for endpoint, products in sorted(mislabelled.items()):
            print(f"    {endpoint}: {', '.join(sorted(products))}")

    failed = False
    if unknown:
        print("npm replay markers without a shared fixture:")
        for endpoint in sorted(unknown):
            print(f"  {endpoint}")
        failed = True
    if unbacked:
        print(f"npm replay markers the inventory records no session for "
              f"({args.inventory.name}):")
        for endpoint in sorted(unbacked):
            print(f"  {endpoint}")
        print("Record the session that produced each, or drop the claim. Until "
              "then every count above is that many too high.")
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
