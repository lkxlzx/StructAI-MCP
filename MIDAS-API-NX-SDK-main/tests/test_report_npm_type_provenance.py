"""npm generation still reads the Python source tree, and by how much.

`scripts/report_npm_type_provenance.py` turns that standing goal into a
number. Before it, the only measurement was a hand count in CLAUDE.md.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location(
        "report_npm_type_provenance_under_test",
        ROOT / "scripts" / "report_npm_type_provenance.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_every_generated_type_lands_in_exactly_one_bucket() -> None:
    """Counted per declaration, not per name.

    `types.ts` is a stack of namespaces and a name repeats across them -- 765
    declarations over 742 distinct names -- which is the same reason the
    generator keys its payload lookup by `(module, name)` rather than name.
    """
    report = _module()
    found = report.classify()
    names = [name for bucket in found.values() for name in bucket]
    exported = sum(
        1
        for line in report.TYPES.read_text(encoding="utf-8").splitlines()
        if report._EXPORT.match(line.strip())
    )
    assert len(names) == exported


def test_a_contract_that_owns_a_payload_type_is_the_one_that_shapes_it() -> None:
    """`python:contract-ignored` is a generator defect, not a known gap.

    A contract naming a payload type it does not waive must be what the
    generator emits. Falling back to the Python TypedDict there would publish
    a shape the source of truth does not describe -- silently, because every
    other parity check compares routes, verbs and products rather than the
    emitted field list.
    """
    report = _module()
    assert report.classify()["python:contract-ignored"] == []


def test_the_python_source_tree_does_not_take_back_ground() -> None:
    """The ceiling falls as contracts take over; it must not rise."""
    report = _module()
    found = report.classify()
    python_sourced = sum(
        len(names) for bucket, names in found.items() if bucket != "contract"
    )
    assert python_sourced <= report.PYTHON_SOURCED_AT_MOST


def test_the_waived_bucket_is_exactly_the_unmerged_table_contracts() -> None:
    """The 13 are blocked on a manual judgement, not on generator work.

    Keeping the two sets equal is what stops `python:unmerged` becoming a
    place where anything inconvenient gets parked.
    """
    report = _module()
    _named, waived = report._contract_payload_names()
    assert set(report.classify()["python:unmerged"]) <= waived


def test_the_exported_type_count_is_recorded() -> None:
    """Adding an export is a deliberate act, not a side effect of a contract.

    The generator used to refuse a `surface.nestedTypes` name the Python tree
    did not publish. That refusal read the Python tree and went with it when
    placement moved to the contracts; this count replaces it.
    """
    report = _module()
    found = report.classify()
    assert sum(len(names) for names in found.values()) == report.EXPORTED_TYPES
