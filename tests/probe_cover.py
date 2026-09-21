"""Ad-hoc probe: which load cases does the current (stage-mode) analysis cover?"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from midas_mcp.credentials import ensure_credentials  # noqa: E402

ensure_credentials()

import live_space_grid as L  # noqa: E402

s = L.Session("probe6")
try:
    t = L._table(s, "DISPLACEMENTG")
    head, data = t.get("HEAD", []), t.get("DATA", [])
    print("DISPLACEMENTG HEAD", head, "rows", len(data))
    if head:
        i_l = head.index("Load")
        loads = sorted({r[i_l] for r in data})
        print("load cases in results:", loads)
    t2 = L._table(s, "REACTIONG")
    h2, d2 = t2.get("HEAD", []), t2.get("DATA", [])
    if h2:
        i_l = h2.index("Load")
        i_n = h2.index("Node")
        per = {}
        for r in d2:
            per.setdefault(r[i_l], set()).add(int(r[i_n]))
        for lc, ns in sorted(per.items()):
            print(f"  {lc}: {len(ns)} supports {sorted(ns)}")
finally:
    s.close()
