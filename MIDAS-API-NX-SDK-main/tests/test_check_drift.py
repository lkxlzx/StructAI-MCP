"""Regression tests for the local live ``/info`` drift checker."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

check_drift = importlib.import_module("check_drift")


_server_fields = check_drift._server_fields


def test_server_fields_reads_current_argument_json_schema_after_schema_uri():
    """Civil/Gen NX place the field definitions in ``Argument.properties``."""
    assert _server_fields(
        {
            "$schema": "https://example.invalid/schema",
            "Argument": {
                "type": "object",
                "properties": {"X": {"type": "number"}, "Y": {"type": "number"}},
            },
        }
    ) == {"X", "Y"}


def test_server_fields_keeps_legacy_resource_key_envelope():
    assert _server_fields({"NODE": {"X": "number", "Y": "number"}}) == {"X", "Y"}


def test_server_fields_ignores_non_object_envelope_members():
    assert _server_fields({"$schema": "https://example.invalid/schema"}) == set()


def test_fields_for_product_excludes_only_contract_gated_fields(monkeypatch):
    monkeypatch.setattr(
        check_drift,
        "_contract_field_products",
        lambda: {"/db/IEHC": {"WallConsOut": frozenset({"gen"})}},
    )

    assert check_drift._fields_for_product({"BEAM_LOC", "WallConsOut"}, "/db/IEHC", "civil") == {"BEAM_LOC"}
    assert check_drift._fields_for_product({"BEAM_LOC", "WallConsOut"}, "/db/IEHC", "gen") == {
        "BEAM_LOC",
        "WallConsOut",
    }
