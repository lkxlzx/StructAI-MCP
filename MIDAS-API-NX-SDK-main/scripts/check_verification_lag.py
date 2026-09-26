"""Report contracts whose `verification` records lag the live ledger.

A contract's `verification.records[].ref` names the session it was promoted
from. The ledger moves the day a write round trip passes; the ref does not.
Nothing compared the two until this script, and 40 contracts cite only a read
session for an endpoint `contracts/verification/ledger.yaml` holds at write
level.

**This is a ceiling, not a to-do list.** A ref records provenance, so editing
one to cite a session the contract was not promoted from would forge it.
Re-promoting the contract is what moves a ref. The count may shrink and must
not grow: a newly write-level endpoint whose contract still cites only a read
is the drift this catches.

**All 40 were audited on 2026-09-21 and none is a contract defect.** A stale
citation would matter if the later write had revealed something the contract
does not record, and `check_fixture_contract.py` measures that directly: on a
`confirmed` case the product accepted that exact payload, so a disagreement is
evidence about the contract. 39 of the 40 have a confirmed fixture case
(`/ope/MEMB` is the exception, write-confirmed through the 2026-09-18 manual
probes instead), and not one of the 40 appears among that scan's three
confirmed-side findings. So the number is citation bookkeeping today, and
`tests/test_check_verification_lag.py` holds it that way -- if a lagging
endpoint ever turns up in that scan, it has stopped being bookkeeping.

    python scripts/check_verification_lag.py            # list them
    python scripts/check_verification_lag.py --check    # fail if the count grew
"""

from __future__ import annotations

import argparse
import pathlib
import sys

import yaml

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from verification_ledger import load_records, resolve  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts" / "endpoints"
LEDGER = ROOT / "contracts" / "verification" / "ledger.yaml"
VERIFICATION = ROOT / "contracts" / "verification"

#: Measured 2026-09-21 over 384 promoted contracts. It read 48 the day before,
#: when this matched the word "write" in the verification block instead of
#: resolving the ref: eight contracts cite a write session whose id does not
#: spell it. A ceiling: see the module docstring for why it may fall, not rise.
LAGGING_AT_MOST = 40


def _ledger_levels() -> dict[str, str]:
    resolved = resolve(load_records(LEDGER))
    return {endpoint: claim.level for endpoint, claim in resolved.items()}


def _record_levels() -> dict[str, str]:
    """`level` of every session record a contract can cite, by record id.

    Both product files, in one map: a ref names an id, and an id is unique
    across them.
    """
    levels: dict[str, str] = {}
    for product in ("gen", "civil"):
        path = VERIFICATION / f"{product}-nx.yaml"
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for record in document.get("records") or []:
            if isinstance(record.get("id"), str):
                levels[record["id"]] = record.get("level", "")
    return levels


def lagging_contracts() -> list[tuple[str, pathlib.Path]]:
    """Endpoints the ledger records at write level whose contract cites no write.

    A ref is resolved to the record it names and that record's `level` is
    read. Matching the word "write" in the block instead -- which this did
    until 2026-09-21 -- calls a contract lagging whenever the id it cites
    happens not to spell it: `/db/REBW` cites
    `db-rebw-live-shape-2026-07-29`, a write record, and was counted as
    lagging for it.
    """
    levels = _ledger_levels()
    record_levels = _record_levels()
    lagging = []
    for path in sorted(CONTRACTS.glob("*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        endpoint = document.get("endpoint")
        if not isinstance(endpoint, str) or levels.get(endpoint) != "write":
            continue
        refs = [
            record.get("ref")
            for record in (document.get("verification") or {}).get("records") or []
        ]
        if not any(record_levels.get(str(ref)) == "write" for ref in refs):
            lagging.append((endpoint, path))
    return lagging


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true",
        help="exit 1 if more contracts lag than the recorded ceiling",
    )
    args = parser.parse_args()

    lagging = lagging_contracts()
    if args.check:
        if len(lagging) > LAGGING_AT_MOST:
            print(
                f"contracts citing a read sweep for a write-level endpoint grew "
                f"from {LAGGING_AT_MOST} to {len(lagging)}:",
                file=sys.stderr,
            )
            for endpoint, path in lagging:
                print(f"  {endpoint}  ({path.name})", file=sys.stderr)
            print(
                "(Hint: a newly write-level endpoint does not get its contract's "
                "verification block hand-edited - raise the ceiling only with the "
                "measurement that justifies it.)",
                file=sys.stderr,
            )
            return 1
        print(
            f"OK - {len(lagging)} contract(s) lag the ledger, ceiling {LAGGING_AT_MOST}."
        )
        return 0

    print(f"{len(lagging)} contract(s) cite no write record for a write-level endpoint:")
    for endpoint, path in lagging:
        print(f"  {endpoint}  ({path.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
