"""Ad-hoc probe: read the modal participation table (periods + mass ratios)."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from midas_mcp.credentials import ensure_credentials  # noqa: E402

ensure_credentials()

import live_space_grid as L  # noqa: E402

s = L.Session("probe10")
try:
    t = L._table(s, "PARTICIPATIONVECTORMODE",
                 MODES=[f"Mode{i}" for i in range(1, 21)])
    print("HEAD", t.get("HEAD"))
    print("rows", len(t.get("DATA", [])))
    for r in t.get("DATA", [])[:8]:
        print("  ", r)
finally:
    s.close()
