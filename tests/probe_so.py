"""Ad-hoc probe: is the current analysis second-order (P-Delta)?

A P-Delta analysis satisfies equilibrium in the DEFORMED configuration, so
summing r x F about the origin with UNDEFORMED coordinates leaves a small
moment residual even though the force sum is exact.  Check DB:PDEL / DB:ACTL.
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

s = L.Session("probe8")
try:
    for fam in ("PDEL", "ACTL", "STYP", "EIGV", "BUCK", "SPLC", "LCOM-GEN"):
        try:
            r = s.records(fam)
            keys = list(r)[:2]
            print(f"{fam}: {len(r)} records")
            for k in keys:
                print("   ", k, json.dumps(r[k], ensure_ascii=False)[:400])
        except Exception as exc:
            print(f"{fam}: ERROR {exc}")
finally:
    s.close()
