"""Tests for the derivable npm live-replay coverage report."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location(
        "report_npm_replay_coverage_under_test",
        ROOT / "scripts" / "report_npm_replay_coverage.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _ledger(tmp_path: Path, *records: dict) -> Path:
    """Write a ledger fixture. Live evidence moved here on 2026-09-21."""
    path = tmp_path / "ledger.yaml"
    path.write_text(
        yaml.safe_dump({"schemaVersion": 1, "records": list(records)}, sort_keys=False),
        encoding="utf-8",
    )
    return path


def test_report_counts_only_confirmed_fixture_endpoints(tmp_path: Path) -> None:
    module = _module()
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps({"cases": [
            {"endpoint": "/db/CONFIRMED", "confirmed": True},
            {"endpoint": "/db/UNCONFIRMED", "confirmed": False},
        ]}),
        encoding="utf-8",
    )
    ledger = _ledger(
        tmp_path,
        {"id": "r1", "endpoints": ["/db/CONFIRMED"], "method": module.REPLAY_MARKER},
        {"id": "r2", "endpoints": ["/db/UNCONFIRMED"], "method": "Python only"},
    )

    assert module.report(cases, ledger) == (1, 1, 0, set(), set())


def test_report_rejects_replay_marker_without_confirmed_fixture(tmp_path: Path) -> None:
    module = _module()
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps({"cases": []}), encoding="utf-8")
    ledger = _ledger(
        tmp_path,
        {"id": "r1", "endpoints": ["/db/NO-CASE"], "method": module.REPLAY_MARKER},
    )

    assert module.report(cases, ledger) == (0, 0, 0, {"/db/NO-CASE"}, set())


def test_report_excludes_an_unconfirmed_case_from_the_gap_denominator(tmp_path: Path) -> None:
    module = _module()
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps({"cases": [
            {"endpoint": "/db/CONFIRMED", "confirmed": True},
            {"endpoint": "/db/UNCONFIRMED", "confirmed": False},
        ]}),
        encoding="utf-8",
    )
    ledger = _ledger(
        tmp_path,
        {"id": "r1", "endpoints": ["/db/UNCONFIRMED"], "method": module.REPLAY_MARKER},
    )

    assert module.report(cases, ledger) == (1, 0, 1, set(), set())


def test_report_flags_a_replay_claim_the_inventory_records_no_session_for(
    tmp_path: Path,
) -> None:
    """A ledger claim is not evidence on its own.

    The fixture check cannot see this: /db/RECORDED and /db/CLAIMED both have a
    confirmed case and both carry the marker. Only the session inventory tells
    them apart, which is how three 2026-09-16 claims went unnoticed until they
    were audited by hand.
    """
    module = _module()
    cases = tmp_path / "cases.json"
    inventory = tmp_path / "inventory.md"
    cases.write_text(
        json.dumps({"cases": [
            {"endpoint": "/db/RECORDED", "products": ["gen"], "confirmed": True},
            {"endpoint": "/db/CLAIMED", "products": ["gen"], "confirmed": True},
        ]}),
        encoding="utf-8",
    )
    ledger = _ledger(
        tmp_path,
        {"id": "r1", "endpoints": ["/db/RECORDED", "/db/CLAIMED"],
         "method": module.REPLAY_MARKER},
    )
    inventory.write_text(
        """
| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/RECORDED` | 2026-09-16 | Gen, Civil |
""",
        encoding="utf-8",
    )

    assert module.report(cases, ledger, inventory) == (
        2, 2, 0, set(), {"/db/CLAIMED"},
    )
    assert module.main([
        "--cases", str(cases), "--ledger", str(ledger),
        "--inventory", str(inventory), "--check",
    ]) == 1


def test_report_leaves_the_inventory_out_when_it_is_not_given(tmp_path: Path) -> None:
    """report() without an inventory keeps its old meaning, so the fixture
    check stays usable on its own."""
    module = _module()
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps({"cases": [
            {"endpoint": "/db/CLAIMED", "products": ["gen"], "confirmed": True},
        ]}),
        encoding="utf-8",
    )
    ledger = _ledger(
        tmp_path,
        {"id": "r1", "endpoints": ["/db/CLAIMED"], "method": module.REPLAY_MARKER},
    )

    assert module.report(cases, ledger) == (1, 1, 0, set(), set())

def _inventory(tmp_path: Path, *rows: str) -> Path:
    path = tmp_path / "inventory.md"
    header = ["| Endpoint | Date | Products |",
              "| --- | --- | --- |"]
    path.write_text(chr(10).join([*header, *rows]) + chr(10), encoding="utf-8")
    return path


def test_case_coverage_counts_a_case_complete_only_on_every_declared_product(
    tmp_path: Path,
) -> None:
    """
An endpoint is the wrong unit and this is why: a case declaring two
    products is not covered by a run against one of them.
    """
    module = _module()
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps({"cases": [
            {"endpoint": "/db/BOTH", "products": ["gen", "civil"], "confirmed": True},
            {"endpoint": "/db/ONE", "products": ["gen"], "confirmed": True},
        ]}),
        encoding="utf-8",
    )
    inventory = _inventory(
        tmp_path,
        "| `/db/BOTH` | 2026-09-16 | Civil |",
        "| `/db/ONE` | 2026-09-16 | Gen |",
    )

    complete, partial, missing, mislabelled = module.case_coverage(cases, inventory)

    assert complete == 1
    assert partial == {"/db/BOTH": {"gen"}}
    assert missing == []
    assert mislabelled == {}


def test_case_coverage_does_not_mislabel_a_run_against_an_unconfirmed_case(
    tmp_path: Path,
) -> None:
    """
/db/HHCT's shape: a confirmed Gen case and an unconfirmed Civil one.
    npm running the Civil one is a real run, not a wrong product label.
    """
    module = _module()
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps({"cases": [
            {"endpoint": "/db/SPLIT", "products": ["gen"], "confirmed": True},
            {"endpoint": "/db/SPLIT", "products": ["civil"], "confirmed": False},
        ]}),
        encoding="utf-8",
    )
    inventory = _inventory(
        tmp_path, "| `/db/SPLIT` | 2026-09-16 | Gen, Civil |")

    complete, partial, missing, mislabelled = module.case_coverage(cases, inventory)

    assert (complete, partial, missing, mislabelled) == (1, {}, [], {})
