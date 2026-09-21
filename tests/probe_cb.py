"""Ad-hoc probe: do combination names need the '(CB)' suffix in LOAD_CASE_NAMES?"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from midas_mcp.credentials import ensure_credentials  # noqa: E402

ensure_credentials()

import live_space_grid as L  # noqa: E402

s = L.Session("probe11")
try:
    for suffix in ("", "(CB)"):
        names = [f"ULS-01{suffix}", f"SLS-01{suffix}"]
        t = L._table(s, "TRUSSFORCE", cases=names)
        labels = sorted({r[2] for r in t.get("DATA", [])}) if t.get("HEAD") else []
        print(f"TRUSSFORCE request {names} -> {len(t.get('DATA', []))} rows, labels {labels}")

    # mixed: cases with (ST) plus combos with (CB)
    names = ["DEAD(ST)", "ULS-01(CB)", "SLS-01(CB)"]
    t = L._table(s, "TRUSSFORCE", cases=names)
    labels = sorted({r[2] for r in t.get("DATA", [])}) if t.get("HEAD") else []
    print(f"mixed request -> {len(t.get('DATA', []))} rows, labels {labels}")
finally:
    s.close()
