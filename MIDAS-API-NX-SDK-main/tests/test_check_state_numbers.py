"""A number a document states about the repository has to be one it can prove.

`scripts/check_state_numbers.py` exists because nothing compared the two: on
2026-09-21 PLAN.md's §2 said `177 of 212 cases confirmed` while the fixture held
183 of 220, and the same file said 183 of 220 four sections above.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location(
        "check_state_numbers_under_test",
        ROOT / "scripts" / "check_state_numbers.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Its dataclasses resolve annotations through sys.modules, and the module
    # postpones them, so it has to be registered before it executes.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_a_dated_history_section_is_not_a_claim_about_now(tmp_path, monkeypatch) -> None:
    """The scanned region stops at the next heading.

    A release row recording `201 write / 199 read` is what was true then.
    Rewriting it to today's numbers would falsify the history, so the checker
    must not read it -- and must still catch the stale line inside the
    current-state section above it.
    """
    checker = _module()
    document = tmp_path / "PLAN.md"
    document.write_text(
        "\n".join([
            "## 2. Current status",
            "",
            "| Live verification | | 400/400 recorded, 999 write / 192 read |",
            "",
            "## 4. Release milestones",
            "",
            "| 2.8.3 | live coverage 201 write / 199 read |",
            "",
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(checker, "REGIONS", (
        checker.Region(document, re.compile(r"^## 2\. "), "under test"),
    ))

    measured = {"write": 208, "read": 192, "inventory": 400}
    found = [s for s in checker.statements(measured) if s.name in ("write", "read")]
    assert [(s.stated, s.agrees) for s in found] == [(999, False), (192, True)]


def test_a_wrapped_sentence_is_still_the_same_claim(tmp_path, monkeypatch) -> None:
    """Both documents wrap, and matching line by line would miss the claim."""
    checker = _module()
    document = tmp_path / "playbook.md"
    document.write_text(
        "## Where things stand\n\n- **Fixture:** 220 cases over 196\n  endpoints.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(checker, "REGIONS", (
        checker.Region(document, re.compile(r"^## Where things stand"), "under test"),
    ))

    found = checker.statements({"cases": 220, "case_endpoints": 196})
    assert [(s.name, s.stated) for s in found] == [
        ("cases", 220), ("case_endpoints", 196),
    ]


def test_every_number_the_repository_states_is_one_it_measures() -> None:
    checker = _module()
    found = checker.statements()
    assert found, "the current-state regions state no checked number at all"
    assert [s for s in found if not s.agrees] == []


def test_a_pattern_no_document_states_any_more_is_a_failure() -> None:
    """Deleting the sentence is not a way to pass the check."""
    checker = _module()
    assert checker.unstated(checker.statements()) == []
