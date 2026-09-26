"""Report keyed manual-table rows the contract extractor cannot turn into fields.

This is a measurement tool, not a parser.  It deliberately imports the
extractor's Markdown-cell and wire-key helpers, so the report cannot claim a
row is preserved when the extractor drops it (or vice versa).
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import extract_contracts as extractor

EXPECTED_COUNTS = {
    "blank key cell": 71,
    "cell count disagrees with header": 20,
    "second key column ignored": 3,
}


@dataclass(frozen=True)
class DroppedRow:
    cause: str
    chapter: str
    endpoint: str
    line: int
    key: str
    cells: tuple[str, ...]


def scan_lines(chapter: str, lines: list[str]) -> list[DroppedRow]:
    """Find rows that the extractor skips in tables with a recognised key.

    A literal empty key is a blank-key row.  ``-`` is an intentional manual
    placeholder rather than an empty cell, so it is not part of the established
    blank-key measurement.  It remains handled by the extractor as before.
    """

    rows: list[DroppedRow] = []
    endpoint = ""
    index = 0
    while index + 1 < len(lines):
        section = extractor._SECTION.match(lines[index])
        if section:
            endpoint = section.group(2)
            if not endpoint.startswith("/"):
                endpoint = "/" + endpoint
            index += 1
            continue
        if not endpoint or not (
            lines[index].startswith("|") and extractor._DIVIDER.match(lines[index + 1])
        ):
            index += 1
            continue

        header = [cell.lower() for cell in extractor._split_row(lines[index])]
        key_columns = [
            column for column, name in enumerate(header) if name in extractor._KEY_COLUMNS
        ]
        key_column = key_columns[0] if key_columns else None
        if key_column is None:
            index += 1
            continue

        row = index + 2
        while row < len(lines) and lines[row].startswith("|"):
            cells = extractor._split_row(lines[row])
            if len(cells) != len(header):
                rows.append(
                    DroppedRow(
                        "cell count disagrees with header",
                        chapter,
                        endpoint,
                        row + 1,
                        "",
                        tuple(cells),
                    )
                )
            else:
                key = extractor._canonical_wire_property(cells[key_column])
                if not key:
                    rows.append(DroppedRow("blank key cell", chapter, endpoint, row + 1, key, tuple(cells)))
                # A table can carry two Key/설명 column pairs side by side, which
                # is how a 25-key object fits on a page. The extractor reads the
                # first pair and the second is lost whole - not a dropped row but
                # a dropped half-table, which is why /db/MVCTch's FREQ object was
                # missing seven documented keys until the /info sweep said so.
                # See MD-50.
                for column in key_columns[1:]:
                    if extractor._canonical_wire_property(cells[column]):
                        rows.append(
                            DroppedRow(
                                "second key column ignored",
                                chapter,
                                endpoint,
                                row + 1,
                                cells[column],
                                tuple(cells),
                            )
                        )
            row += 1
        index = row
    return rows


def scan_manual(manual_repo: Path) -> list[DroppedRow]:
    manual_dir = manual_repo / "docs" / "manual"
    return [
        row
        for path in sorted(manual_dir.glob("*.md"))
        for row in scan_lines(path.name, path.read_text(encoding="utf-8").splitlines())
    ]


def report(rows: list[DroppedRow]) -> Counter[str]:
    counts = Counter(row.cause for row in rows)
    print("Dropped keyed manual-table rows:")
    for cause, count in sorted(counts.items()):
        print(f"  {cause}: {count}")
    for cause in sorted(counts):
        if cause == "blank key cell":
            continue
        print(f"\n{cause}:")
        for row in (item for item in rows if item.cause == cause):
            print(f"  {row.chapter}:{row.line} {row.endpoint} | {' | '.join(row.cells)}")
    return counts


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manual-api-repo", type=Path, default=extractor.DEFAULT_MANUAL_REPO)
    parser.add_argument("--check", action="store_true", help="fail if the established cause counts change")
    args = parser.parse_args(argv)

    counts = report(scan_manual(args.manual_api_repo))
    if not args.check:
        return 0

    drift = {
        cause: (EXPECTED_COUNTS.get(cause, 0), counts.get(cause, 0))
        for cause in set(EXPECTED_COUNTS) | set(counts)
        if EXPECTED_COUNTS.get(cause, 0) != counts.get(cause, 0)
    }
    if not drift:
        return 0

    for cause, (expected, found) in sorted(drift.items()):
        direction = "more" if found > expected else "fewer"
        print(
            f"\n{cause}: expected {expected}, found {found} "
            f"({abs(found - expected)} {direction}).",
            file=sys.stderr,
        )
    print(
        "\nRows growing means the manual or the extractor started dropping more "
        "of them; rows shrinking means something now reads them. Either way the "
        "new count belongs in EXPECTED_COUNTS, in the commit that explains it.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
