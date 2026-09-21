"""Ad-hoc probe: can the model be returned to plain static analysis mode?

The stage analysis covers only the final stage, so the 30 static load cases
need a non-stage run.  Test whether DB:STAG / DB:STCT accept DELETE, and if so
whether removing them restores full static results.
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

s = L.Session("probe7")
try:
    print("== restore supports, run ANAL in stage mode ==")
    s.call("midas_db_assign", {"endpoint": "DB:CONS", "mode": "update",
           "data": {k: {"ITEMS": [{"ID": 1, "GROUP_NAME": "SUP", "CONSTRAINT": c}]}
                    for k, c in WANT.items()}}, required=False)
    r = s.call("midas_doc", {"command": "ANAL", "argument": {}}, required=False)
    print("ANAL:", r.get("ok"), r.get("category"))
    print("CONS after ANAL:", sorted(s.records("CONS")))
    t = L._table(s, "DISPLACEMENTG")
    loads = sorted({x[t["HEAD"].index("Load")] for x in t.get("DATA", [])}) if t.get("HEAD") else []
    print("stage-mode result cases:", loads)

    print("\n== try DELETE DB:STCT and DB:STAG ==")
    for fam in ("STCT", "STAG"):
        d = s.call("midas_db_delete", {"endpoint": "DB:" + fam, "target_ids": ["1"]},
                   required=False)
        print(f"  DELETE DB:{fam}:", d.get("ok"), d.get("category"), d.get("message"))
        if fam == "STAG":
            for k in ("2", "3"):
                d2 = s.call("midas_db_delete", {"endpoint": "DB:STAG", "target_ids": [k]},
                            required=False)
                print(f"  DELETE DB:STAG/{k}:", d2.get("ok"), d2.get("category"))
    print("  STAG now:", sorted(s.records("STAG")), " STCT now:", sorted(s.records("STCT")))

    print("\n== ANAL without stages ==")
    r = s.call("midas_doc", {"command": "ANAL", "argument": {}}, required=False)
    print("ANAL:", r.get("ok"), r.get("category"), r.get("http_status"), r.get("warning"))
    t = L._table(s, "DISPLACEMENTG")
    loads = sorted({x[t["HEAD"].index("Load")] for x in t.get("DATA", [])}) if t.get("HEAD") else []
    print("static-mode result cases:", len(loads), loads)
    print("CONS after static ANAL:", sorted(s.records("CONS")))
finally:
    s.close()
