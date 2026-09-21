"""Parsing of MIDAS ``POST/TABLE`` replies into structured result objects.

A MIDAS table reply is not one table.  The top-level object holds the *primary*
rows (for an eigen-analysis that is the per-node mode shapes) and a
``SUB_TABLES`` array carries the *summary* tables that go with them - for an
eigen-analysis, the frequency/period list, the participation masses, the
participation factors and the direction factors.

Reading only the top level is a trap that has already produced a wrong
conclusion once: because the top-level ``DATA`` for ``EIGENVALUEMODE`` holds
mode shapes and nothing else, a caller that stops there reports "this build has
no modal summary", when the summary is sitting in ``SUB_TABLES``.  The parser
below therefore treats ``SUB_TABLES`` as a first-class result source and never
decides that a result is absent from the top-level table being empty.

Field names are taken from each sub-table's own ``HEAD`` row, never assumed:
MIDAS renames columns between versions (``Frequency(rad/sec)`` vs
``Frequency``, ``TRAN-XMASS`` vs ``TRAN-XMASS(%)``), so a column that is not
present is reported as ``None`` rather than as "no result".
"""
from __future__ import annotations

import json
import re
from typing import Any

#: A sub-table whose name contains any of these is part of a modal/eigen
#: summary.  Matched case-insensitively against the sub-table's own name.
MODAL_SUBTABLE_MARKERS = ("eigenvalue", "modal", "frequency", "period",
                          "participation", "direction factor", "mode shape")

#: Participation/direction axes, as (canonical DOF key, MIDAS column letter,
#: TRAN/ROTN prefix).  MIDAS names the rotation columns with the bare axis
#: letter - ``ROTN-XValue`` is rotation *about* X, not a column called RX - so
#: the canonical RX/RY/RZ keys must not be looked up verbatim in the HEAD row.
#: Canonical keys match the DOF names used elsewhere in the connector; the
#: original MIDAS headers are preserved in the result's ``raw``.
AXES = (("UX", "X", "TRAN"), ("UY", "Y", "TRAN"), ("UZ", "Z", "TRAN"),
        ("RX", "X", "ROTN"), ("RY", "Y", "ROTN"), ("RZ", "Z", "ROTN"))


# --------------------------------------------------------------------------
# generic SUB_TABLES access
# --------------------------------------------------------------------------
def sub_tables(table: Any) -> list[tuple[str, dict]]:
    """``[(name, sub_table), ...]`` from a MIDAS table dict's ``SUB_TABLES``.

    ``SUB_TABLES`` is a list of single-key objects (``{"NAME": {...}}``), so it
    is flattened here once for every caller.
    """
    if not isinstance(table, dict):
        return []
    subs = table.get("SUB_TABLES")
    if not isinstance(subs, list):
        return []
    out: list[tuple[str, dict]] = []
    for entry in subs:
        if not isinstance(entry, dict):
            continue
        for name, body in entry.items():
            if isinstance(body, dict):
                out.append((str(name), body))
    return out


def sub_table(table: Any, name: str) -> dict:
    """The sub-table whose name matches ``name`` (case-insensitive substring)."""
    wanted = name.lower()
    for sub_name, body in sub_tables(table):
        if wanted in sub_name.lower():
            return body
    return {}


def tables_of(parsed: Any) -> list[tuple[str, dict]]:
    """``[(table_name, table), ...]`` from a whole parsed response body."""
    if not isinstance(parsed, dict):
        return []
    out: list[tuple[str, dict]] = []
    for name, body in parsed.items():
        if isinstance(body, dict) and ("HEAD" in body or "DATA" in body
                                       or "SUB_TABLES" in body):
            out.append((str(name), body))
    return out


def parse_body(raw: str | dict | None) -> Any:
    """Parse a raw response body (string or already-decoded) into an object."""
    if isinstance(raw, (dict, list)):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


# --------------------------------------------------------------------------
# column lookup driven by the sub-table's own HEAD
# --------------------------------------------------------------------------
def columns(head: Any) -> dict[str, int]:
    return {str(h): i for i, h in enumerate(head or [])}


def _cell(row: Any, idx: int | None) -> Any:
    if idx is None or not isinstance(row, (list, tuple)) or idx >= len(row):
        return None
    return row[idx]


def _num(value: Any) -> float | None:
    """``float`` or ``None``.  A missing/blank cell is None, never 0.0."""
    if value is None:
        return None
    try:
        f = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return f


def _find(cols: dict[str, int], *patterns: str) -> int | None:
    """First column whose header matches any pattern (case-insensitive regex)."""
    for pattern in patterns:
        rx = re.compile(pattern, re.I)
        for header, idx in cols.items():
            if rx.search(header):
                return idx
    return None


# --------------------------------------------------------------------------
# modal / eigen summary
# --------------------------------------------------------------------------
def is_modal_subtable(name: str) -> bool:
    lowered = name.lower()
    return any(m in lowered for m in MODAL_SUBTABLE_MARKERS)


def modal_sub_tables(table: Any) -> list[tuple[str, dict]]:
    return [(n, b) for n, b in sub_tables(table) if is_modal_subtable(n)]


def modal_result(raw: str | dict | None) -> dict | None:
    """Structured modal summary from a MIDAS eigen/modal reply, or ``None``.

    ``None`` means "this reply carries no modal data at all".  A reply that
    *does* carry modal data but is missing some columns still returns a result,
    with the absent fields set to ``None`` - the distinction matters, because
    "MIDAS did not print a period column" must not read as "there is no modal
    analysis".

    Nothing is recomputed: every number here is copied out of a MIDAS
    sub-table, and the originating sub-table name and raw rows are kept so a
    field rename in a future version can be traced.
    """
    parsed = parse_body(raw)
    found: list[tuple[str, str, dict]] = []  # (table_name, sub_name, body)
    for table_name, table in tables_of(parsed):
        for sub_name, body in modal_sub_tables(table):
            found.append((table_name, sub_name, body))
    if not found:
        return None

    modes: dict[int, dict] = {}
    raw_sub: dict[str, Any] = {}
    table_names: list[str] = []

    for table_name, sub_name, body in found:
        if table_name not in table_names:
            table_names.append(table_name)
        raw_sub[f"{table_name} :: {sub_name}"] = body
        cols = columns(body.get("HEAD"))
        lowered = sub_name.lower()
        is_factor = "direction factor" in lowered
        is_participation = "participation" in lowered
        is_eigen = "eigenvalue" in lowered or (
            "frequency" in lowered and "participation" not in lowered)

        for row in body.get("DATA") or []:
            i_mode = _find(cols, r"^\s*mode\s*$", r"^modeno", r"^mode\s*no",
                           r"^mode$", r"^index$")
            mode = _num(_cell(row, i_mode))
            if mode is None:
                continue
            mode = int(mode)
            rec = modes.setdefault(mode, {"mode": mode})

            if is_eigen:
                # Prefer the explicit unit-tagged columns; fall back to the
                # untagged ones only when the tagged column is absent.
                rad = _find(cols, r"frequency.*rad", r"omega", r"angular")
                cyc = _find(cols, r"frequency.*cycle", r"frequency.*hz",
                            r"^frequency$", r"natural frequency")
                if rad is not None:
                    rec["frequency_rad_s"] = _num(_cell(row, rad))
                if cyc is not None:
                    rec["frequency_hz"] = _num(_cell(row, cyc))
                rec["period_s"] = _num(_cell(row, _find(cols, r"period")))
                rec["tolerance"] = _num(_cell(row, _find(cols, r"tolerance")))

            elif is_participation:
                # A '(%)' column is a ratio; an untagged one is an absolute
                # mass.  'SUM' columns are cumulative through the mode list.
                for key, letter, pre in AXES:
                    ratio = _find(cols, rf"{pre}-{letter}MASS\s*\(\s*%")
                    cum = _find(cols, rf"{pre}-{letter}SUM\s*\(\s*%")
                    mass = _find(cols, rf"{pre}-{letter}MASS\s*$")
                    total = _find(cols, rf"{pre}-{letter}SUM\s*$")
                    if ratio is not None:
                        rec.setdefault("participation_mass_ratio", {})[key] = \
                            _num(_cell(row, ratio))
                    if cum is not None:
                        rec.setdefault("cumulative_ratio", {})[key] = \
                            _num(_cell(row, cum))
                    if mass is not None:
                        rec.setdefault("participation_mass", {})[key] = \
                            _num(_cell(row, mass))
                    if total is not None:
                        rec.setdefault("cumulative_mass", {})[key] = \
                            _num(_cell(row, total))

            elif is_factor:
                for key, letter, pre in AXES:
                    idx = _find(cols, rf"{pre}-{letter}Value")
                    if idx is not None:
                        rec.setdefault("direction_factor", {})[key] = \
                            _num(_cell(row, idx))
            else:
                # An unrecognised modal sub-table: keep its columns verbatim
                # rather than dropping the data.
                rec.setdefault("other", {})[sub_name] = {
                    header: _cell(row, idx) for header, idx in cols.items()
                }

    ordered = [modes[m] for m in sorted(modes)]
    for rec in ordered:
        rec.setdefault("frequency_rad_s", None)
        rec.setdefault("frequency_hz", None)
        rec.setdefault("period_s", None)

    # Cumulative participation through the whole extracted mode set, and the
    # mode that governs each direction - both read from the tables, not solved.
    # The last mode's SUM column is the total; an untagged SUM is an absolute
    # mass rather than a percentage.
    cumulative: dict[str, Any] = {}
    for key, _, _ in AXES:
        value = None
        for rec in reversed(ordered):
            value = (rec.get("cumulative_ratio") or {}).get(key)
            if value is None:
                value = (rec.get("cumulative_mass") or {}).get(key)
            if value is not None:
                break
        cumulative[key] = value
    first_mode: dict[str, Any] = {}
    for key, _, _ in AXES:
        best = None
        for rec in ordered:
            value = (rec.get("direction_factor") or {}).get(key)
            if value is None:
                continue
            if best is None or value > best[1]:
                best = (rec["mode"], value)
        if best and best[1] > 0:
            first_mode[key] = {"mode": best[0], "value": best[1]}

    return {
        "analysis_type": "modal",
        "source": "SUB_TABLES",
        "tables": table_names,
        "sub_tables": [name for _, name, _ in found],
        "mode_count": len(ordered),
        "modes": ordered,
        "cumulative_ratio_percent": cumulative,
        "first_mode_by_axis": first_mode,
        "raw": raw_sub,
    }


def buckling_result(raw: str | dict | None) -> dict | None:
    """Structured buckling summary (``POST:TABLE:BUCKLINGMODE``), or ``None``."""
    parsed = parse_body(raw)
    for table_name, table in tables_of(parsed):
        subs = [(n, b) for n, b in sub_tables(table)
                if "buckling" in n.lower() or "eigenvalue" in n.lower()]
        if not subs:
            continue
        modes: list[dict] = []
        raw_sub: dict[str, Any] = {}
        for sub_name, body in subs:
            raw_sub[f"{table_name} :: {sub_name}"] = body
            cols = columns(body.get("HEAD"))
            for row in body.get("DATA") or []:
                mode = _num(_cell(row, _find(cols, r"^\s*mode", r"^modeno")))
                eigen = _num(_cell(row, _find(cols, r"eigenvalue", r"buckling.*factor",
                                                r"load factor")))
                if mode is None and eigen is None:
                    continue
                modes.append({
                    "mode": int(mode) if mode is not None else None,
                    "eigenvalue": eigen,
                    "tolerance": _num(_cell(row, _find(cols, r"tolerance"))),
                })
        if modes:
            modes.sort(key=lambda m: (m["mode"] is None, m["mode"]))
            return {"analysis_type": "buckling", "source": "SUB_TABLES",
                    "tables": [table_name], "mode_count": len(modes),
                    "modes": modes, "raw": raw_sub}
    return None


def result_summary(raw: str | dict | None) -> dict:
    """Every structured result the connector can derive from one reply.

    Attached to a POST/TABLE tool result so the model receives the parsed
    summary alongside the raw table, instead of having to notice ``SUB_TABLES``
    itself.
    """
    parsed = parse_body(raw)
    out: dict[str, Any] = {}
    names: list[str] = []
    for table_name, table in tables_of(parsed):
        for sub_name, _ in sub_tables(table):
            names.append(sub_name)
    if names:
        out["sub_tables"] = names
    modal = modal_result(parsed)
    if modal is not None:
        out["modal_result"] = modal
    buckling = buckling_result(parsed)
    if buckling is not None:
        out["buckling_result"] = buckling
    return out
