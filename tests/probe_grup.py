"""Ad-hoc probe: can DB:GRUP N_LIST be set exactly, or is it merge-only?

Observed: PUT /db/GRUP with N_LIST=[] on STG2/STG3 did not clear them, and a
PUT restoring STG1's original 42-node list left it at 98.  Determine whether
DELETE + POST gives an exact list, which the builder needs.
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

s = L.Session("probe5")
try:
    before = s.records("GRUP")
    print("before:", {k: (v.get("NAME"), len(v.get("N_LIST") or []), len(v.get("E_LIST") or []))
                      for k, v in before.items()})
    k1 = next(k for k, v in before.items() if v.get("NAME") == "STG1")
    stg1 = before[k1]
    target = sorted(stg1["N_LIST"])[:5]
    print("try to shrink STG1 N_LIST to", target)

    r = s.call("midas_db_assign", {"endpoint": "DB:GRUP", "mode": "update",
                                   "data": {k1: dict(stg1, N_LIST=target)}},
               required=False)
    print("update:", r.get("ok"), r.get("category"))
    now = s.records("GRUP")[k1]
    print("after update N_LIST len:", len(now.get("N_LIST") or []))

    print("\n-- DELETE + POST route --")
    d = s.call("midas_db_delete", {"endpoint": "DB:GRUP", "target_ids": [k1]},
               required=False)
    print("delete:", d.get("ok"), d.get("category"), d.get("message"))
    print("GRUP keys after delete:", sorted(s.records("GRUP")))
    payload = {k1: dict(stg1, N_LIST=target)}
    r = s.call("midas_db_assign", {"endpoint": "DB:GRUP", "mode": "create",
                                   "data": payload}, required=False)
    print("re-POST:", r.get("ok"), r.get("category"), r.get("message"))
    got = s.records("GRUP").get(k1) or {}
    print("after re-POST N_LIST len:", len(got.get("N_LIST") or []),
          "expected", len(target))
    print("exact match:", sorted(got.get("N_LIST") or []) == target)
finally:
    s.close()
