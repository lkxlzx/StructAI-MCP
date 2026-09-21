"""Decisive probe: is the support loss caused by the first stage's structure group?

Hypothesis (from the audited log + the GRUP node lists): a construction-stage
analysis activates boundary conditions only at nodes belonging to structure
groups activated in that stage, and it rewrites DB:CONS to match - so supports
at nodes that are not yet active in the FIRST stage are deleted from DB:CONS.

Test: move every support node into STG1, restore all 8 CONS records, re-run
ANAL, and see whether all 8 survive.  GRUP and CONS are restored afterwards.
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from midas_mcp.credentials import ensure_credentials  # noqa: E402

ensure_credentials()

import live_space_grid as L  # noqa: E402

WANT = {"50": "1110000", "52": "0010000", "54": "0010000", "56": "0110000",
        "92": "0010000", "94": "0010000", "96": "0010000", "98": "0010000"}
SUPPORT_NODES = {int(k) for k in WANT}

s = L.Session("probe4")
try:
    grups = s.records("GRUP")
    original_grups = json.loads(json.dumps(grups))
    s.save_original = None

    # union of every node currently listed, so nothing is lost
    all_nodes = sorted({n for v in grups.values() for n in (v.get("N_LIST") or [])})
    print("GRUP original N_LIST sizes:", {k: len(v.get("N_LIST") or []) for k, v in grups.items()})
    print("support nodes:", sorted(SUPPORT_NODES))

    # rebuild: STG1 gets every node; STG2/STG3 keep their elements but empty node lists
    patched = {}
    for k, v in grups.items():
        patched[k] = dict(v)
    first = next(k for k, v in grups.items() if v.get("NAME") == "STG1")
    patched[first]["N_LIST"] = all_nodes
    for k, v in patched.items():
        if k != first:
            v["N_LIST"] = []
    r = s.call("midas_db_assign", {"endpoint": "DB:GRUP", "mode": "update",
                                   "data": patched}, required=False)
    print("GRUP patch:", r.get("ok"), r.get("category"), r.get("message"))
    after = s.records("GRUP")
    print("GRUP now:", {k: len(v.get("N_LIST") or []) for k, v in after.items()})

    # restore all 8 supports
    payload = {k: {"ITEMS": [{"ID": 1, "GROUP_NAME": "SUP", "CONSTRAINT": c}]}
               for k, c in WANT.items()}
    r = s.call("midas_db_assign", {"endpoint": "DB:CONS", "mode": "update",
                                   "data": payload}, required=False)
    print("CONS restore:", r.get("ok"), "->", sorted(s.records("CONS")))

    r = s.call("midas_doc", {"command": "ANAL", "argument": {}}, required=False)
    print("ANAL:", r.get("ok"), r.get("category"), r.get("http_status"))
    after_cons = s.records("CONS")
    print("CONS after ANAL:", sorted(after_cons))
    print(">>> all 8 survived:", sorted(after_cons) == sorted(WANT))

    # restore GRUP to the original partition
    r = s.call("midas_db_assign", {"endpoint": "DB:GRUP", "mode": "update",
                                   "data": original_grups}, required=False)
    print("GRUP restore:", r.get("ok"))
    print("GRUP restored:", {k: len(v.get("N_LIST") or []) for k, v in s.records("GRUP").items()})
    print("CONS now:", sorted(s.records("CONS")))
finally:
    s.close()
