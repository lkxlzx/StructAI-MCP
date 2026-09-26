from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _checker_module():
    spec = importlib.util.spec_from_file_location(
        "check_verification_lag_under_test",
        ROOT / "scripts" / "check_verification_lag.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_contract(directory: Path, name: str, endpoint: str, record_ref: str) -> None:
    (directory / name).write_text(
        "\n".join([
            f"endpoint: {endpoint}",
            "verification:",
            "  status: verified_both",
            "  records:",
            "    - product: gen",
            f"      ref: {record_ref}",
            "",
        ]),
        encoding="utf-8",
    )


def test_only_a_write_level_endpoint_citing_no_write_record_counts(tmp_path, monkeypatch) -> None:
    """Three contracts, one lagging: the read-citing one at write level.

    A read-level endpoint citing a read sweep is the truthful state, not drift,
    and a write-level endpoint already citing a write is what this check wants
    more of. Only the pair that disagrees is a finding.
    """
    checker = _checker_module()
    contracts = tmp_path / "endpoints"
    contracts.mkdir()
    _write_contract(contracts, "db-a.yaml", "/db/A", "db-read-sweep-2026-07-26")
    _write_contract(contracts, "db-b.yaml", "/db/B", "db-write-sweep-2026-07-29")
    _write_contract(contracts, "db-c.yaml", "/db/C", "db-read-sweep-2026-07-26")

    ledger = tmp_path / "ledger.yaml"
    ledger.write_text(yaml.safe_dump({"schemaVersion": 1, "records": [
        {"id": "w", "endpoints": ["/db/A", "/db/B"], "date": "2026-01-01",
         "level": "write", "products": ["gen"]},
        {"id": "r", "endpoints": ["/db/C"], "date": "2026-01-01",
         "level": "read", "products": ["gen"]},
    ]}, sort_keys=False), encoding="utf-8")

    monkeypatch.setattr(checker, "CONTRACTS", contracts)
    monkeypatch.setattr(checker, "LEDGER", ledger)

    assert [endpoint for endpoint, _ in checker.lagging_contracts()] == ["/db/A"]


def test_the_repository_stays_at_or_below_its_recorded_ceiling() -> None:
    """The count may fall -- that is the point -- but never rise silently."""
    checker = _checker_module()
    assert len(checker.lagging_contracts()) <= checker.LAGGING_AT_MOST


def test_a_lagging_citation_never_hides_a_contract_that_is_actually_wrong() -> None:
    """The 40 are a citation artefact, and this is what keeps that true.

    A ref names the session a contract was promoted from, so a contract whose
    endpoint later took a write still cites the read sweep -- truthfully.
    What would make that worth acting on is the write having revealed
    something the contract does not record, and `check_fixture_contract.scan()`
    measures exactly that: on a `confirmed` case the product accepted that
    payload, so a disagreement is evidence about the contract.

    Audited 2026-09-21: 39 of the 40 have a confirmed fixture case and none of
    the 40 appears on that side of the scan. If one ever does, the lag stops
    being bookkeeping for that endpoint and the contract needs re-promoting
    from a permitted source.
    """
    checker = _checker_module()
    spec = importlib.util.spec_from_file_location(
        "check_fixture_contract_under_test",
        ROOT / "scripts" / "check_fixture_contract.py",
    )
    fixture_check = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(fixture_check)

    _unconfirmed, confirmed, _checked = fixture_check.scan()
    lagging = {endpoint for endpoint, _ in checker.lagging_contracts()}
    assert lagging.isdisjoint(confirmed), sorted(lagging & set(confirmed))
