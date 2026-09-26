"""The live-evidence ledger: session records in, per-endpoint claims out.

`contracts/verification/ledger.yaml` is the single source for what a live
session proved about an endpoint. Everything that counts live coverage --
`gen_roadmap.py`, `report_npm_replay_coverage.py`, `promote_contract.py` --
resolves it through this module rather than reading a per-endpoint field.

Until 2026-09-21 that field lived in `docs/coverage.json` as `live_verified`,
beside the implementation inventory, while `contracts/verification/{gen,civil}
-nx.yaml` carried session findings that contracts cite for provenance. Two
files stating one fact drifted exactly as you would expect: 48 contracts cited
a read sweep for an endpoint the ledger had at write level, and -- worse than
lagging -- the two used `level` to mean different things. A record could say
`level: write, outcome: success` for `/db/NLLP` while its own `finding` said
the write was refused, because there it meant "a write was attempted"; the
ledger meant "a write succeeded". Merging on the wrong one of those would have
promoted endpoints that have never accepted a write.

So `level` has exactly one meaning here, the one every published count
already assumes:

    write   a live call mutated model data, or wrote a file on the NX host
    read    everything else that answered, including a write the product
            refused before it changed anything

A record states what one session achieved for the endpoints it names. An
endpoint's claim is resolved from all of its records: write if any record
achieved a write, and the *earliest* record at that level supplies the date
and build, because that is the session that established the claim. Later
sessions add records rather than editing prose, which is what the old
append-only `method` string made awkward enough to get wrong twice.
"""

from __future__ import annotations

import dataclasses
import functools
import pathlib
from typing import Any, Iterable, Mapping

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
LEDGER = ROOT / "contracts" / "verification" / "ledger.yaml"

PRODUCTS = ("gen", "civil")
#: Only two, and the order is the precedence a resolved claim uses.
LEVELS = ("read", "write")


@dataclasses.dataclass(frozen=True)
class Claim:
    """What the ledger says about one endpoint, resolved from its records."""

    level: str
    date: str
    products: tuple[str, ...]
    nx_versions: Mapping[str, str]
    outcome: str | None
    method: str
    records: tuple[str, ...]

    def as_live_verified(self) -> dict[str, Any]:
        """The shape `docs/coverage.json` published until 2026-09-21.

        Kept because ROADMAP.md, the npm replay report and the contract
        promoter were all written against it, and because the migration
        asserts this reproduces the pre-migration file exactly.
        """
        block: dict[str, Any] = {
            "date": self.date,
            "products": list(self.products),
            "method": self.method,
            "nx_versions": dict(self.nx_versions),
            "level": self.level,
        }
        if self.outcome is not None:
            block["outcome"] = self.outcome
        return block


def _rank(level: str) -> int:
    return LEVELS.index(level) if level in LEVELS else -1


def load_records(path: pathlib.Path | None = None) -> list[dict[str, Any]]:
    document = yaml.safe_load((path or LEDGER).read_text(encoding="utf-8")) or {}
    records = document.get("records") or []
    if not isinstance(records, list):
        raise ValueError(f"{path or LEDGER}: 'records' must be a list.")
    return records


def resolve(records: Iterable[Mapping[str, Any]]) -> dict[str, Claim]:
    """Every endpoint the ledger names, with the claim its records support."""
    by_endpoint: dict[str, list[Mapping[str, Any]]] = {}
    for record in records:
        for endpoint in record.get("endpoints") or []:
            by_endpoint.setdefault(endpoint, []).append(record)

    claims: dict[str, Claim] = {}
    for endpoint, endpoint_records in by_endpoint.items():
        level = max((r["level"] for r in endpoint_records), key=_rank)
        establishing = sorted(
            (r for r in endpoint_records if r["level"] == level),
            key=lambda r: (str(r["date"]), str(r["id"])),
        )
        first = establishing[0]
        products: list[str] = []
        nx_versions: dict[str, str] = {}
        for record in establishing:
            for product in record.get("products") or []:
                if product not in products:
                    products.append(product)
            for product, version in (record.get("nxVersions") or {}).items():
                nx_versions.setdefault(product, version)
        claims[endpoint] = Claim(
            level=level,
            date=str(first["date"]),
            products=tuple(products),
            nx_versions=nx_versions,
            outcome=first.get("outcome"),
            method=str(first.get("method") or ""),
            records=tuple(str(r["id"]) for r in sorted(
                endpoint_records, key=lambda r: (str(r["date"]), str(r["id"])),
            )),
        )
    return claims


@functools.lru_cache(maxsize=1)
def claims() -> Mapping[str, Claim]:
    """The resolved ledger, read once per process."""
    return resolve(load_records())


def claim_for(endpoint: str) -> Claim | None:
    return claims().get(endpoint)


def main() -> int:
    resolved = claims()
    levels = {level: sum(1 for c in resolved.values() if c.level == level) for level in LEVELS}
    print(f"{len(resolved)} endpoints in the ledger: "
          + ", ".join(f"{count} {level}" for level, count in levels.items()))
    for product in PRODUCTS:
        print(f"  verified on {product}: "
              f"{sum(1 for c in resolved.values() if product in c.products)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
