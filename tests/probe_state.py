"""Ad-hoc live probe: confirm the model state and re-establish the linear baseline.

Not part of the deliverable. Uses the same audited stdio Session as the driver so
every call it makes is recorded in the same http_audit.jsonl / mcp_audit.jsonl.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from midas_mcp.credentials import ensure_credentials  # noqa: E402

ensure_credentials()

import live_space_grid as L  # noqa: E402

s = L.Session("probe")
try:
    print("== model collections ==")
    for fam in ("STAG", "STCT", "BNGR", "LDGR", "GRUP", "CONS"):
        try:
            r = s.records(fam)
            print(f"  {fam}: {len(r)} records", list(r)[:4])
        except Exception as exc:
            print(f"  {fam}: ERROR {exc}")

    print("\n== re-run baseline ANAL ==")
    r = s.call("midas_doc", {"command": "ANAL", "argument": {}}, required=False)
    print("  ok=", r.get("ok"), "category=", r.get("category"),
          "status=", r.get("http_status"))
    print("  warning=", r.get("warning"))

    print("\n== reactions right after ANAL ==")
    st = json.loads(L.STATE.read_text(encoding="utf-8"))
    xyz = {n["midas_id"]: (n["X"], n["Y"], n["Z"]) for n in st["nodes"]}
    t = L._table(s, "REACTIONG", cases=["ROOF_DEAD(ST)", "DEAD(ST)", "WIND_X_POS(ST)"])
    head, data = t.get("HEAD", []), t.get("DATA", [])
    print("  HEAD", head, "rows", len(data))
    if head:
        i_n, i_l = head.index("Node"), head.index("Load")
        per = defaultdict(dict)
        for row in data:
            nid, lc = int(row[i_n]), row[i_l]
            per[lc].setdefault(nid, [0.0] * 6)
            for j in range(6):
                per[lc][nid][j] += float(row[3 + j])
        for lc, d in per.items():
            M = [0.0] * 3
            F = [0.0] * 3
            for nid, v in d.items():
                x, y, z = xyz[nid]
                F[0] += v[0]; F[1] += v[1]; F[2] += v[2]
                M[0] += y * v[2] - z * v[1]
                M[1] += z * v[0] - x * v[2]
                M[2] += x * v[1] - y * v[0]
            print(f"  {lc}: nsup={len(d)} F={[round(v,4) for v in F]} "
                  f"r x F={[round(v,4) for v in M]}")
finally:
    s.close()
