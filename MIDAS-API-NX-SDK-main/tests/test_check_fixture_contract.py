from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _checker_module():
    spec = importlib.util.spec_from_file_location(
        "check_fixture_contract_under_test",
        ROOT / "scripts" / "check_fixture_contract.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "selector,expected",
    [(0, []), (1, ["civil: omits required DIST"])],
    ids=["inactive-conditional-field-is-not-required", "active-conditional-field-is-required"],
)
def test_fixture_required_checks_respect_applies_when(selector, expected) -> None:
    checker = _checker_module()
    document = {
        "fields": [
            {"key": "MODE", "requirement": "required"},
            {
                "key": "DIST",
                "requirement": "required",
                "appliesWhen": [{"path": "MODE", "equals": 1}],
            },
        ]
    }
    case = {
        "products": ["civil"],
        "createPayload": {"MODE": selector},
        "updatePayload": {"MODE": selector},
    }

    assert checker._findings(case, document) == expected


def test_variant_field_is_a_recorded_wire_name() -> None:
    checker = _checker_module()
    document = {
        "fields": [{"key": "MODE", "requirement": "required"}],
        "variants": [
            {
                "when": [{"path": "MODE", "equals": 0}],
                "fields": [{"key": "BRANCH_DATA", "requirement": "required"}],
            }
        ],
    }
    case = {
        "products": ["gen"],
        "createPayload": {"MODE": 0, "BRANCH_DATA": {}},
        "updatePayload": {"MODE": 0, "BRANCH_DATA": {}},
    }

    assert checker._findings(case, document) == []
