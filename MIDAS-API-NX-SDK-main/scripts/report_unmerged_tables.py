"""Measure the field names 15 contracts waive against the /info baseline.

Fifteen contracts declare part of their field list missing through
``extraction.unmergedTables``, and each entry records the ``fieldNames`` that
table holds, so the field-parity waiver is per name rather than per count.
That is 482 names the SDKs may ship without any contract accounting for them
individually, and from outside they are one undifferentiated pile.  It was 602
across nineteen contracts before twenty-one of those tables were merged; re-run
this rather than quoting either number.

This splits the pile.  A table whose names ``schema/info-baseline.json`` also
declares has a **second source** and is a candidate to merge; a table whose
names ``/info`` declares nowhere rests on the manual alone and needs its
section read first.  Both look identical until someone measures them, which is
why the largest of them -- /db/MVHL at 115 names -- has stayed untouched.

This measures and reports.  It merges nothing, edits no contract, and draws no
conclusion about what a table means: deciding that takes reading the manual
section, which is not something a script can do.

    python scripts/report_unmerged_tables.py            # write the docs/ report
    python scripts/report_unmerged_tables.py --stdout   # print it instead
    python scripts/report_unmerged_tables.py --check    # fail if it drifted

Both loaders are borrowed from the tool that owns them -- info_baseline.py for
the baseline, its path walker and its contract reader -- so the report cannot
claim a name those tools disagree about.
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys
from typing import Any, Dict, List, Tuple

sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "unmerged_tables_against_info.md"


def _info_baseline_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "info_baseline_for_report", ROOT / "scripts" / "info_baseline.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _declared_paths(ib: Any, capture: dict, endpoint: str) -> Dict[str, Dict[str, str]]:
    """product -> {dotted path: declared type} for one endpoint."""
    out: Dict[str, Dict[str, str]] = {}
    for (route, product), schema in ib._schemas(capture).items():
        if route == endpoint:
            out[product] = ib._paths(schema, with_types=True)
    return out


def _leaf(path: str) -> str:
    return path.rsplit(".", 1)[-1]


def _parent(path: str) -> str:
    return path.rsplit(".", 1)[0] if "." in path else "(root)"


def _match(name: str, declared: Dict[str, Dict[str, str]]) -> List[Tuple[str, str]]:
    """Every (product, path) whose leaf is this wire name.

    Matching on the leaf rather than a full path is deliberate.  An unmerged
    table records wire names and nothing about nesting; where /info puts the
    name is the answer, not part of the question.
    """
    hits: List[Tuple[str, str]] = []
    for product in sorted(declared):
        for path in declared[product]:
            if _leaf(path) == name:
                hits.append((product, path))
    return hits


def _covering_parents(found: List[str], hits: Dict[str, List[Tuple[str, str]]]) -> List[str]:
    """Parents in /info that hold every one of this table's declared names.

    Counting distinct parents instead would measure how common the table's
    leaf names are, not whether /info has an object shaped like the table:
    ``NAME`` alone repeats across every branch of /db/MVHL.
    """
    if not found:
        return []
    sets = [
        {_parent(path) for _, path in hits[name]}
        for name in found
    ]
    common = set.intersection(*sets)
    return sorted(common)


def _path_under(hits: List[Tuple[str, str]], preferred: str) -> str:
    """The hit under the table's own object where there is one.

    Showing an arbitrary first hit reads as a finding it is not: /db/MVHL's
    VEH_DEFAULT table would appear to live under VEH_AU purely because that
    branch sorts earlier.
    """
    for _, path in hits:
        if _parent(path) == preferred:
            return path
    return hits[0][1]


def _best_parent(found: List[str], hits: Dict[str, List[Tuple[str, str]]]) -> Tuple[str, int]:
    """The /info object holding the most of this table's names, and how many.

    When no single object holds the whole table, this is the measurement that
    says whether it nearly does -- one stray name is a different situation from
    a table /info spreads evenly across a dozen branch objects.
    """
    tally: Dict[str, int] = {}
    for name in found:
        for parent in {_parent(path) for _, path in hits[name]}:
            tally[parent] = tally.get(parent, 0) + 1
    best = max(sorted(tally), key=lambda parent: tally[parent])
    return best, tally[best]


def _contracts_with_unmerged_tables(ib: Any) -> List[Tuple[str, List[dict]]]:
    found: List[Tuple[str, List[dict]]] = []
    for endpoint, document in ib._contract_documents().items():
        tables = (document.get("extraction") or {}).get("unmergedTables") or []
        if tables:
            found.append((endpoint, tables))
    found.sort(key=lambda item: (
        -sum(len(table.get("fieldNames") or []) for table in item[1]), item[0]
    ))
    return found


def _table_heading(table: dict, index: int) -> str:
    for key in ("heading", "title", "name", "table"):
        value = table.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"(unnamed table {index + 1})"


def build() -> str:
    ib = _info_baseline_module()
    capture = ib._load(ib.BASELINE)

    # Written before the walk below so the preamble can state what is actually
    # there. It used to assert two out-of-reach endpoints and their 68 names
    # outright, which stopped being true once the tables were merged: the
    # paragraph survived the thing it described by a day.
    unmerged = _contracts_with_unmerged_tables(ib)
    unreachable = [
        (endpoint, sum(len(t.get("fieldNames") or []) for t in tables))
        for endpoint, tables in unmerged
        if not _declared_paths(ib, capture, endpoint)
    ]

    header: List[str] = [
        "# Unmerged extraction tables, measured against `/info`",
        "",
        "Generated by `scripts/report_unmerged_tables.py`; re-run it rather than",
        "editing this file.  **A measurement, not a decision.** Nothing is merged here",
        "and no contract is touched -- what a table means still takes reading its",
        "manual section, and that is the part a script cannot do.",
        "",
        "Each row is one `extraction.unmergedTables` entry.  The `/info` column counts",
        "how many of that table's `fieldNames` the captured baseline declares",
        "**anywhere on the same endpoint**, matching on the wire name rather than on a",
        "path: an unmerged table records names and says nothing about nesting, so where",
        "`/info` puts a name is the answer rather than part of the question.",
        "",
        "**Read a zero weakly.**  `/info` is neither a superset nor a subset of what the",
        "server accepts -- it declares `/db/POSL`'s `CODE`, which Civil NX refuses live,",
        "and omits `/db/STBK`'s `LCNAME`, which a confirmed round trip sends.  A name it",
        "declares nowhere is a name with **one source**, never a name that is wrong.",
        "",
        "The nesting column answers the second question a merge asks: **is there one",
        "object in `/info` that holds this whole table?** That is what a merged block",
        "would attach to.  It is not a count of distinct parents -- a short leaf like",
        "`NAME` repeats across every branch of `/db/MVHL`, so counting parents would",
        "measure how common the names are rather than the table's shape.",
        "",
    ]
    if unreachable:
        endpoints = ", ".join(f"`{endpoint}`" for endpoint, _ in unreachable)
        header += [
            f"{'Two' if len(unreachable) == 2 else len(unreachable)} endpoints here "
            f"are **outside `/info`'s reach** ({endpoints}): introspection is served",
            "for `/db/*` only, swept from both SDKs 2026-09-01, and a 404 on `/view/*`",
            "or `/ope/*` is an API fact rather than a gap in the capture.  Their "
            f"{sum(count for _, count in unreachable)} names are",
            "excluded from the in-scope share below, because a source that cannot exist is",
            "not the same finding as a source that is absent.",
            "",
        ]

    summary: List[str] = [
        "## Summary",
        "",
        "| endpoint | tables | names | declared by `/info` | share |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    body: List[str] = []
    total_names = total_declared = total_tables = 0
    in_scope_names = in_scope_declared = 0
    out_of_scope_names = out_of_scope_tables = 0
    buckets: Dict[str, int] = {}

    for endpoint, tables in unmerged:
        declared = _declared_paths(ib, capture, endpoint)
        names_here = declared_here = 0
        rows: List[str] = []
        detail: List[str] = []

        for index, table in enumerate(tables):
            names = list(table.get("fieldNames") or [])
            heading = _table_heading(table, index)
            hits = {name: _match(name, declared) for name in names}
            found = [name for name in names if hits[name]]
            missing = [name for name in names if not hits[name]]

            # The useful question is not how many parents the names touch --
            # a short leaf like NAME repeats across every branch object and
            # would report dozens -- but whether ONE object holds the whole
            # table. That is what a merge would attach to.
            covering = _covering_parents(found, hits)
            preferred = covering[0] if len(covering) == 1 else (
                _best_parent(found, hits)[0] if found else ""
            )
            if not declared:
                nesting = "--"
            elif not found:
                nesting = "no name declared"
            elif len(covering) == 1:
                nesting = f"one object: `{covering[0]}`"
            elif covering:
                nesting = f"{len(covering)} objects hold all {len(found)}"
            else:
                best, covered = _best_parent(found, hits)
                nesting = f"scattered; `{best}` covers {covered} of {len(found)}"

            names_here += len(names)
            declared_here += len(found)
            if not declared:
                bucket = "out of reach"
            elif missing:
                bucket = "partly declared"
            elif len(covering) == 1:
                bucket = "whole table, one object"
            elif covering:
                bucket = "whole table, several objects"
            else:
                bucket = "whole table, scattered"
            buckets[bucket] = buckets.get(bucket, 0) + 1
            rows.append(
                f"| {heading} | {len(names)} | {len(found)} | {len(missing)} | {nesting} |"
            )
            if found:
                detail.append(
                    f"- **{heading}** declared: "
                    + ", ".join(
                        f"`{name}` at `{_path_under(hits[name], preferred)}`"
                        for name in found
                    )
                )
            if missing:
                detail.append(
                    f"- **{heading}** not declared: "
                    + ", ".join(f"`{name}`" for name in missing)
                )

        total_names += names_here
        total_declared += declared_here
        total_tables += len(tables)
        anchor = endpoint.lower().replace("/", "").replace("-", "")
        if not declared:
            out_of_scope_names += names_here
            out_of_scope_tables += len(tables)
            share = "n/a"
        else:
            in_scope_names += names_here
            in_scope_declared += declared_here
            share = f"{declared_here * 100 // names_here}%" if names_here else "--"
        summary.append(
            f"| [`{endpoint}`](#{anchor}) | {len(tables)} | {names_here} "
            f"| {declared_here if declared else '--'} | {share} |"
        )

        products = ", ".join(f"`{product}`" for product in sorted(declared))
        body.append(f"## `{endpoint}`")
        body.append("")
        if not declared:
            body.append(
                "**Outside `/info`'s reach.** Introspection is served for `/db/*` only "
                "-- swept from both SDKs 2026-09-01, and a 404 here is an API fact "
                "rather than a missing capture. These names have one source because "
                "no second one exists, not because nobody looked."
            )
        else:
            body.append(
                f"Baseline answers on {products}. {declared_here} of {names_here} "
                f"names declared across {len(tables)} tables."
            )
        body.append("")
        body.append("| table | names | declared | not declared | nesting |")
        body.append("| --- | ---: | ---: | ---: | --- |")
        body.extend(rows)
        body.append("")
        body.extend(detail)
        body.append("")

    summary.append(
        f"| **total** | **{total_tables}** | **{total_names}** | **{total_declared}** "
        f"| **{total_declared * 100 // total_names}%** |"
    )
    summary.append("")
    summary.append(
        f"Of the **{in_scope_names}** names on endpoints `/info` answers for, "
        f"**{in_scope_declared}** are declared "
        f"({in_scope_declared * 100 // in_scope_names}%) and "
        f"**{in_scope_names - in_scope_declared}** "
        f"{'is' if in_scope_names - in_scope_declared == 1 else 'are'} not."
        + (
            f" The remaining **{out_of_scope_names}** names sit on "
            f"{out_of_scope_tables} tables of {len(unreachable)} endpoint"
            f"{'' if len(unreachable) == 1 else 's'} `/info` does not serve at all."
            if unreachable
            else ""
        )
    )
    summary.append("")
    summary.append("### What each table has, as a count")
    summary.append("")
    summary.append("| what the measurement found | tables |")
    summary.append("| --- | ---: |")
    for label in ("whole table, one object", "whole table, several objects",
                  "whole table, scattered", "partly declared", "out of reach"):
        if label in buckets:
            summary.append(f"| {label} | {buckets[label]} |")
    summary.append(f"| **all** | **{sum(buckets.values())}** |")
    summary.append("")
    summary.append(
        "*one object* means `/info` has a single object holding every name in that"
        " table; *scattered* means it declares them all but under no common parent,"
        " so the table's shape is not something the baseline confirms. Neither is a"
        " recommendation -- a table with two sources still needs its manual section"
        " read before anything moves."
    )
    summary.append("")
    return "\n".join(header + summary + body) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--stdout", action="store_true",
                       help="print the report instead of writing it")
    group.add_argument("--check", action="store_true",
                       help="exit 1 if the committed report is out of date")
    args = parser.parse_args()

    text = build()
    if args.stdout:
        print(text)
        return 0
    if args.check:
        current = REPORT.read_text(encoding="utf-8") if REPORT.exists() else ""
        if current != text:
            print("docs/unmerged_tables_against_info.md is out of date; "
                  "re-run scripts/report_unmerged_tables.py")
            return 1
        return 0
    REPORT.write_text(text, encoding="utf-8")
    print(f"Wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
