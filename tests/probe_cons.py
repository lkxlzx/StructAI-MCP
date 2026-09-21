"""Ad-hoc live probe: does /doc/ANAL in construction-stage mode drop constraints?

The audited log shows DB:CONS holding all 8 supports, then holding only 4 after
the STCT write + ANAL, with no other write in between.  This probe restores the
missing 4 and re-runs ANAL to see whether the drop reproduces.
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

s = L.Session("probe2")
try:
    print("before:", sorted(s.records("CONS")))
    payload = {k: {"ITEMS": [{"ID": 1, "GROUP_NAME": "SUP", "CONSTRAINT": c}]}
               for k, c in WANT.items()}
    r = s.call("midas_db_assign", {"endpoint": "DB:CONS", "mode": "update",
                                   "data": payload}, required=False)
    print("restore ok:", r.get("ok"), r.get("category"), r.get("message"))
    print("after restore:", sorted(s.records("CONS")))

    r = s.call("midas_doc", {"command": "ANAL", "argument": {}}, required=False)
    print("ANAL:", r.get("ok"), r.get("category"), r.get("http_status"))
    after = s.records("CONS")
    print("after ANAL:", sorted(after))
    print("lost:", sorted(set(WANT) - set(after)))
finally:
    s.close()
