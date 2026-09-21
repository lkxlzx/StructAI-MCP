"""Ad-hoc live probe: why does the stage analysis drop 4 of 8 supports?

Candidates: (a) the boundary group DB:BNGR is empty / auto-scoped, (b) the
supports lie outside every activated structure group DB:GRUP.
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

s = L.Session("probe3")
try:
    print("== /info/db/BNGR ==")
    try:
        info = s.query("DB:BNGR", info=True, required=False)
        print(json.dumps(info, ensure_ascii=False)[:2500])
    except Exception as exc:
        print("ERR", exc)

    print("\n== BNGR live ==")
    print(json.dumps(s.records("BNGR"), ensure_ascii=False))

    print("\n== GRUP live ==")
    for k, v in s.records("GRUP").items():
        print(f"  {k} {v.get('NAME')}: N_LIST={v.get('N_LIST')} "
              f"E_LIST={len(v.get('E_LIST') or [])} keys={sorted(v)}")

    print("\n== STAG stage 1 ACT_* ==")
    print(json.dumps(s.records("STAG"), ensure_ascii=False)[:1500])
finally:
    s.close()
