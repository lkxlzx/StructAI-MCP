"""Ad-hoc probe: find the POST/TABLE that reports eigenvalues / periods."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from midas_mcp.credentials import ensure_credentials  # noqa: E402

ensure_credentials()

import live_space_grid as L  # noqa: E402

s = L.Session("probe9")
try:
    # what does the registry know about?
    hits = s.call("midas_db_query", {"endpoint": "POST:TABLE:EIGENVALUEMODE",
                                     "search": "EIGEN"}, required=False)
    print("registry search EIGEN:",
          json.dumps(hits.get("data", {}).get("matches", [])[:40], ensure_ascii=False))

    for kind in ("EIGENVALUE", "MODAL", "MODALPROPERTY", "MODE", "FREQUENCY",
                 "EIGENVALUEMODE"):
        try:
            t = L._table(s, kind, MODES=[f"Mode{i}" for i in range(1, 21)])
            print(f"\n{kind}: HEAD={t.get('HEAD')} rows={len(t.get('DATA', []))}")
            for r in t.get("DATA", [])[:4]:
                print("   ", r)
        except Exception as exc:
            print(f"\n{kind}: ERROR {exc}")
finally:
    s.close()
