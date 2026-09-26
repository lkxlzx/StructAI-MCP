"""The live-evidence ledger resolves records into per-endpoint claims.

The migration that created `contracts/verification/ledger.yaml` on 2026-09-21
proved it reproduced every `live_verified` block `docs/coverage.json` had
carried. These tests hold the two properties that proof rested on: the
resolver's rules, and the published counts the resolved ledger has to keep
producing.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location(
        "verification_ledger_under_test",
        ROOT / "scripts" / "verification_ledger.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # `@dataclass` resolves annotations through sys.modules, and this module
    # postpones them with `from __future__ import annotations`, so it has to
    # be registered before it executes.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_a_write_anywhere_beats_a_read_everywhere() -> None:
    """One session's successful write is what a write claim rests on."""
    ledger = _module()
    resolved = ledger.resolve([
        {"id": "sweep", "endpoints": ["/db/X"], "date": "2026-07-26",
         "level": "read", "products": ["gen"]},
        {"id": "crud", "endpoints": ["/db/X"], "date": "2026-08-01",
         "level": "write", "products": ["gen", "civil"]},
        {"id": "resweep", "endpoints": ["/db/X"], "date": "2026-09-01",
         "level": "read", "products": ["civil"]},
    ])
    claim = resolved["/db/X"]
    assert claim.level == "write"
    # The date and products come from the session that established the claim,
    # not from the newest record: a later read does not restate a write.
    assert claim.date == "2026-08-01"
    assert claim.products == ("gen", "civil")
    assert claim.records == ("sweep", "crud", "resweep")


def test_the_earliest_record_at_the_resolved_level_supplies_date_and_build() -> None:
    """Re-verification adds a record; it does not move the original claim."""
    ledger = _module()
    resolved = ledger.resolve([
        {"id": "first", "endpoints": ["/db/Y"], "date": "2026-07-29",
         "level": "write", "products": ["gen"],
         "nxVersions": {"gen": "build 07/28/2026"}, "outcome": "success"},
        {"id": "again", "endpoints": ["/db/Y"], "date": "2026-09-18",
         "level": "write", "products": ["gen"],
         "nxVersions": {"gen": "build 09/15/2026"}, "outcome": "success"},
    ])
    claim = resolved["/db/Y"]
    assert (claim.date, claim.nx_versions) == ("2026-07-29", {"gen": "build 07/28/2026"})
    assert claim.records == ("first", "again")


def test_a_record_naming_several_endpoints_claims_each_of_them() -> None:
    ledger = _module()
    resolved = ledger.resolve([
        {"id": "sweep", "endpoints": ["/db/A", "/db/B"], "date": "2026-07-26",
         "level": "read", "products": ["gen", "civil"]},
    ])
    assert sorted(resolved) == ["/db/A", "/db/B"]
    assert all(c.level == "read" for c in resolved.values())


def test_the_committed_ledger_still_produces_the_published_counts() -> None:
    """208 write / 192 read over 400 inventory rows, as ROADMAP.md publishes.

    Counted over the inventory rather than the ledger because three
    /DESIGN/*/TABLE rows share one endpoint URL: the ledger holds 397 claims,
    and the roadmap renders 400 rows.
    """
    ledger = _module()
    resolved = ledger.claims()
    inventory = json.loads(
        (ROOT / "docs" / "coverage.json").read_text(encoding="utf-8")
    )["endpoints"]

    levels = [resolved[e["endpoint"]].level for e in inventory if e["endpoint"] in resolved]
    assert len(levels) == len(inventory), "every inventory row needs a ledger claim"
    assert levels.count("write") == 208
    assert levels.count("read") == 192


def test_every_ledger_record_states_a_level_a_count_can_read() -> None:
    ledger = _module()
    for record in ledger.load_records():
        assert record["level"] in ledger.LEVELS, record["id"]
        assert record.get("endpoints"), record["id"]
        assert record.get("date"), record["id"]
