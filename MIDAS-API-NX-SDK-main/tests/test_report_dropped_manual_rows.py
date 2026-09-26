"""Tests for the extractor-aligned dropped-manual-row measurement."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report_dropped_manual_rows import scan_lines  # noqa: E402


def test_scan_lines_counts_only_rows_the_extractor_drops() -> None:
    rows = scan_lines(
        "99_DB_Synthetic.md",
        [
            "## 1. `/db/SYNTH` — Synthetic",
            "| No. | Key | Value Type |",
            "| --- | --- | --- |",
            "| 1 | `NAME` | String |",
            "| 2 |  | Number |",
            "| 3 | `MODE` | String | extra |",
            "| 4 | - | String |",
        ],
    )

    assert [(row.cause, row.line, row.endpoint) for row in rows] == [
        ("blank key cell", 5, "/db/SYNTH"),
        ("cell count disagrees with header", 6, "/db/SYNTH"),
    ]
