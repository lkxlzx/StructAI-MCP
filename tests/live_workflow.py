#!/usr/bin/env python3
"""Live end-to-end workflow against a running MIDAS Gen/Civil instance.

Additive and reversible: it exports a backup, appends a small cantilever in a
free id range, runs an analysis, reads the result tables, captures a view, then
deletes everything it added.  The host model is never replaced (no /doc/NEW) and
never re-saved (no /doc/SAVEAS).

Run::

    python tests/live_workflow.py          # credentials come from config.json

or export them directly::

    set MIDAS_MAPI_KEY=<key>
    set MIDAS_BASE_URL=http://localhost:3030/gen
    python tests/live_workflow.py

This is deliberately NOT part of the unittest suite: it runs an analysis, which
invalidates previously stored results in the live model.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from midas_mcp.config import load_config  # noqa: E402
from midas_mcp.mcp_server import McpServer  # noqa: E402
from midas_mcp.registry import Registry  # noqa: E402

NODE_A, NODE_B = 710001, 710002          # base and tip of the test cantilever
ELEM_ID = 710001
LC_ID = "900"
LC_NAME = "MCPTEST"
# The workflow builds everything it needs, so it runs on an empty document too.
SECT_ID, MATL_ID = 719001, 719001
SPAN = 5.0                                # metres, tip load in kN

failures: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'ok' if cond else 'FAIL'}] {label}" + (f" -- {detail}" if detail else ""))
    if not cond:
        failures.append(label)


def main() -> int:
    cfg = load_config([])
    srv = McpServer(cfg, Registry.load(ROOT / "registry"))

    def call(tool: str, args: dict) -> dict:
        res = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                          "params": {"name": tool, "arguments": args}})["result"]
        return res

    def ok(tool: str, args: dict) -> dict:
        res = call(tool, args)
        if res["isError"]:
            print(f"    !! {tool} {args.get('endpoint', args.get('command', ''))} failed: "
                  f"{res['content'][0]['text'][:200]}")
        return res

    backup = Path(tempfile.gettempdir()) / "midas_mcp_backup.json"
    print(f"1. backup -> {backup}")
    r = ok("midas_doc", {"command": "EXPORT",
                         "argument": {"EXPORT_PATH": str(backup)}})
    check("export backup", not r["isError"], r["content"][0]["text"][:120])
    check("backup file written", backup.exists(),
          f"{backup.stat().st_size if backup.exists() else 0} bytes")

    print("2. build test cantilever")
    # material: P_TYPE 2 (user defined) with every parameter supplied, since
    # P_TYPE 1 is accepted but silently zeroes POISN/THERMAL/DEN/MASS
    r = ok("midas_db_assign", {"endpoint": "DB:MATL", "mode": "create", "data": {
        str(MATL_ID): {"TYPE": "STEEL", "NAME": "MCPSTEEL", "PARAM": [
            {"P_TYPE": 2, "bELAST": True, "ELAST": 205000000, "POISN": 0.3,
             "THERMAL": 1.2e-5, "DEN": 76.97, "MASS": 7.849}]}}})
    check("create material", not r["isError"])
    r = ok("midas_db_assign", {"endpoint": "DB:SECT", "mode": "create", "data": {
        str(SECT_ID): {"SECTTYPE": "VALUE", "SECT_NAME": "MCP-H500x200",
                       "SECT_BEFORE": {"SHAPE": "H",
                                       "SECT_I": {"vSIZE": [0.5, 0.2, 0.01, 0.016]}}}}})
    check("create section", not r["isError"])

    r = ok("midas_db_assign", {"endpoint": "DB:NODE", "mode": "create", "data": {
        str(NODE_A): {"X": 0, "Y": 0, "Z": 100},
        str(NODE_B): {"X": SPAN, "Y": 0, "Z": 100}}})
    check("create nodes", not r["isError"])
    r = ok("midas_db_assign", {"endpoint": "DB:ELEM", "mode": "create", "data": {
        str(ELEM_ID): {"TYPE": "BEAM", "MATL": MATL_ID, "SECT": SECT_ID,
                       "NODE": [NODE_A, NODE_B], "ANGLE": 0}}})
    check("create element", not r["isError"])
    r = ok("midas_db_assign", {"endpoint": "DB:CONS", "mode": "create", "data": {
        str(NODE_A): {"ITEMS": [{"ID": NODE_A, "CONSTRAINT": "1111110"}]}}})
    check("create support", not r["isError"])
    # MIDAS assigns its own STLD record id, so read the id back by name.
    r = ok("midas_db_assign", {"endpoint": "DB:STLD", "mode": "create", "data": {
        LC_ID: {"NAME": LC_NAME, "TYPE": "USER", "DESC": "MCP live test"}}})
    check("create load case", not r["isError"])
    lc_record = None
    rq = ok("midas_db_query", {"endpoint": "DB:STLD"})
    if not rq["isError"]:
        for rid, rec in rq["structuredContent"]["data"].get("STLD", {}).items():
            if isinstance(rec, dict) and rec.get("NAME") == LC_NAME:
                lc_record = rid
                break
    check("load case recorded", lc_record is not None, f"id={lc_record}")
    # CNLD items carry explicit FX/FY/FZ/MX/MY/MZ components (confirmed by
    # GET /info/db/CNLD), not the CMD/FV vector the manual example implies.
    r = ok("midas_db_assign", {"endpoint": "DB:CNLD", "mode": "create", "data": {
        str(NODE_B): {"ITEMS": [{"ID": 1, "LCNAME": LC_NAME,
                                 "FX": 0, "FY": 0, "FZ": -10}]}}})
    check("create nodal load", not r["isError"])

    print("3. analyse")
    r = ok("midas_doc", {"command": "ANAL", "argument": {}})
    check("ANAL accepted", not r["isError"], r["content"][0]["text"][:120])

    print("4. read results")
    r = ok("midas_db_assign", {"endpoint": "POST:TABLE:REACTIONG",
                               "mode": "create", "data": {
                                   "TABLE_TYPE": "REACTIONG",
                                   "TABLE_NAME": "Reaction",
                                   "UNIT": {"FORCE": "KN", "DIST": "M"},
                                   "LOAD_CASE_NAMES": [f"{LC_NAME}(ST)"],
                                   "NODE_ELEMS": {"KEYS": [NODE_A]}}})
    check("reaction table", not r["isError"])
    if not r["isError"]:
        body = r["structuredContent"]["data"]
        rows = list(body.values())[0].get("DATA", []) if body else []
        check("reaction has rows", len(rows) > 0, f"{len(rows)} rows")
        if rows:
            print(f"    reaction row: {rows[0]}")

    r = ok("midas_db_assign", {"endpoint": "POST:TABLE:DISPLACEMENTG",
                               "mode": "create", "data": {
                                   "TABLE_TYPE": "DISPLACEMENTG",
                                   "TABLE_NAME": "Displacement",
                                   "UNIT": {"FORCE": "KN", "DIST": "M"},
                                   "LOAD_CASE_NAMES": [f"{LC_NAME}(ST)"],
                                   "NODE_ELEMS": {"KEYS": [NODE_B]}}})
    check("displacement table", not r["isError"])
    if not r["isError"]:
        body = r["structuredContent"]["data"]
        rows = list(body.values())[0].get("DATA", []) if body else []
        check("displacement has rows", len(rows) > 0, f"{len(rows)} rows")
        if rows:
            print(f"    displacement row: {rows[0]}")

    print("5. capture view")
    shot = Path(tempfile.gettempdir()) / "midas_mcp_view.jpg"
    r = ok("midas_db_assign", {"endpoint": "VIEW:CAPTURE", "mode": "create", "data": {
        "EXPORT_PATH": str(shot), "WIDTH": 1200, "HEIGHT": 900, "SET_MODE": "post"}})
    check("view capture", not r["isError"], r["content"][0]["text"][:120])
    check("capture file written", shot.exists(),
          f"{shot.stat().st_size if shot.exists() else 0} bytes")

    print("6. cleanup (reverse order)")
    for tool, args in [
        ("midas_db_delete", {"endpoint": "DB:CNLD", "target_ids": [str(NODE_B)]}),
        ("midas_db_delete", {"endpoint": "DB:CONS", "target_ids": [str(NODE_A)]}),
        ("midas_db_delete", {"endpoint": "DB:STLD",
                             "target_ids": [lc_record or LC_ID]}),
        ("midas_db_delete", {"endpoint": "DB:ELEM", "target_ids": [str(ELEM_ID)]}),
        ("midas_db_delete", {"endpoint": "DB:NODE",
                             "target_ids": [str(NODE_A), str(NODE_B)]}),
        ("midas_db_delete", {"endpoint": "DB:SECT", "target_ids": [str(SECT_ID)]}),
        ("midas_db_delete", {"endpoint": "DB:MATL", "target_ids": [str(MATL_ID)]}),
    ]:
        r = ok(tool, args)
        check(f"delete {args['endpoint']}", not r["isError"])

    print()
    if failures:
        print(f"FAILURES: {len(failures)} -> {failures}")
        return 1
    print("live workflow complete: all steps passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
