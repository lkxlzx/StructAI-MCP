"""Real stdio MCP driver for the user-authorized PORTAL-FRAME-TEST-001.

End-to-end single-storey double-pitch steel portal frame in the X-Z plane:
model -> material -> sections -> nodes -> elements -> supports -> load cases ->
self weight -> beam loads -> combinations -> checks -> analysis -> results ->
parsed extremes.

No fake API and no fabricated analysis results.  Every live call is audited
into ``mcp_audit.jsonl`` / ``http_audit.jsonl`` and every response that feeds a
number in the report is saved under ``artifacts/PORTAL-FRAME-TEST-001/``.
Credentials come from the MIDAS_MAPI_KEY / MIDAS_BASE_URL environment variables
or from a JSON config file (see config.example.json); no key is stored here.

``DOC:NEW`` is deliberately not called: the registry notes that it destroys the
model held in memory, and the preflight verifies the live document is already
empty before the build starts.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

#: ``src/midas_mcp/frame.py`` -> the repo root is three levels up.  ``OUT`` is
#: redirected by ``--out-dir`` on the CLI or by the spec's ``out_dir``.
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "PORTAL-FRAME-TEST-001"
STATE = OUT / "state.json"
from .credentials import MissingCredentials, ensure_credentials  # noqa: E402
from .results import result_summary  # noqa: E402

# ---------------------------------------------------------------------------
# Model definition (verbatim from the test prompt)
# ---------------------------------------------------------------------------
SPAN = 20.0
EAVE = 6.0
RIDGE = 8.0
SLOPE = (RIDGE - EAVE) / (SPAN / 2.0)          # 1:5

#: (id, X, Y, Z) in metres.  Y is 0: the frame lies in the X-Z plane.
NODES = ((1, 0.0, 0.0, 0.0),
         (2, 0.0, 0.0, EAVE),
         (3, SPAN / 2.0, 0.0, RIDGE),
         (4, SPAN, 0.0, EAVE),
         (5, SPAN, 0.0, 0.0))

#: (id, i_node, j_node, section key)
ELEMS = ((1, 1, 2, "COLUMN"),
         (2, 2, 3, "BEAM"),
         (3, 3, 4, "BEAM"),
         (4, 4, 5, "COLUMN"))

#: Welded H sections.  vSIZE for SHAPE "H" is [H, B, tw, tf, 0, 0, 0, 0] -
#: confirmed live against the computed AREA and RYY/RZZ of the section reply.
SECTIONS = {
    "COLUMN": {"id": 1, "name": "COLUMN_H400X200X8X12",
               "vSIZE": [0.400, 0.200, 0.008, 0.012, 0.0, 0.0, 0.0, 0.0]},
    "BEAM": {"id": 2, "name": "BEAM_H500X220X8X14",
             "vSIZE": [0.500, 0.220, 0.008, 0.014, 0.0, 0.0, 0.0, 0.0]},
}

MATL_NAME = "Q355"
MATL_ELAST = 206000000.0        # kN/m2  (2.06e5 MPa)
MATL_POISN = 0.30
MATL_DEN = 78.5                 # kN/m3  (7850 kg/m3, MIDAS steel weight density)
MATL_MASS = MATL_DEN / 9.80665  # kN s2/m4
GRAV = 9.80665

#: Load cases: (name, MIDAS load type, description)
CASES = (("DEAD", "D", "Dead load: self weight + roof dead load"),
         ("LIVE", "L", "Roof live load"),
         ("WIND_X_POS", "W", "+X wind on the columns"),
         ("WIND_X_NEG", "W", "-X wind on the columns"))

#: Supports: UX/UY/UZ fixed, RX/RY/RZ free -> [DX,DY,DZ,RX,RY,RZ,RW] = 1110000
SUPPORT_CONSTRAINT = "1110000"
SUPPORTS = (1, 5)

#: Structure type 1 = X-Z plane frame.  The prompt builds the frame in the X-Z
#: plane and asks for the restraint mapping to follow the API's own DOF
#: definition rather than the DOF *names*; declaring the plane here is what
#: makes MIDAS's own DOF set line up with the prompt's UX/UY/UZ + RX/RY/RZ
#: table, and the readback is asserted in step 1 rather than trusted.
STYP = 1

#: Beam loads: (element id, load case, direction, kN/m)
ROOF_DEAD_Q = -0.50             # kN/m, global -Z
ROOF_LIVE_Q = -0.50             # kN/m, global -Z
WIND_Q = 2.00                   # kN/m, global +/-X on both columns
BEAM_LOADS = ((2, "DEAD", "GZ", ROOF_DEAD_Q),
              (3, "DEAD", "GZ", ROOF_DEAD_Q),
              (2, "LIVE", "GZ", ROOF_LIVE_Q),
              (3, "LIVE", "GZ", ROOF_LIVE_Q),
              (1, "WIND_X_POS", "GX", WIND_Q),
              (4, "WIND_X_POS", "GX", WIND_Q),
              (1, "WIND_X_NEG", "GX", -WIND_Q),
              (4, "WIND_X_NEG", "GX", -WIND_Q))

#: (name, description, [(case, factor), ...])
COMBOS = (("COMB1", "1.2 DEAD + 1.4 LIVE", (("DEAD", 1.2), ("LIVE", 1.4))),
          ("COMB2", "1.2 DEAD + 1.4 LIVE + 1.4 WIND_X_POS",
           (("DEAD", 1.2), ("LIVE", 1.4), ("WIND_X_POS", 1.4))),
          ("COMB3", "1.2 DEAD + 1.4 LIVE + 1.4 WIND_X_NEG",
           (("DEAD", 1.2), ("LIVE", 1.4), ("WIND_X_NEG", 1.4))),
          ("COMB4", "1.0 DEAD + 1.0 LIVE", (("DEAD", 1.0), ("LIVE", 1.0))))

COMBO_NAMES = tuple(c[0] for c in COMBOS)

# ---------------------------------------------------------------------------
# spec-derived text: every label below is read from the installed model
# ---------------------------------------------------------------------------
#: DOF order of ``CONS.ITEMS[].CONSTRAINT``, as the DB schema prints it.  The
#: restraint is described from this string rather than from the prompt's DOF
#: *names*, so a spec that changes the constraint changes the report with it.
DOF_ORDER = ("DX", "DY", "DZ", "RX", "RY", "RZ", "RW")

#: Chinese label per element role, for readability only.  A role a spec
#: introduces falls back to its own key: an unfamiliar true name beats a
#: familiar wrong one.
ROLE_LABEL = {"COLUMN": "柱", "BEAM": "梁"}

#: Structure-type codes whose plane this driver has verified against the live
#: API.  Any other code is printed as its raw value rather than guessed.
STYP_PLANE = {1: "X-Z 平面"}


def support_nodes():
    """Support node ids as the strings the DB replies are keyed by."""
    return tuple(str(nid) for nid in SUPPORTS)


def support_label():
    """``N1/N5``, built from the spec instead of written into the text."""
    return "/".join(f"N{nid}" for nid in SUPPORTS)


def dof_split(constraint=None):
    """``(fixed, free)`` DOF names, read out of the constraint string itself."""
    text = SUPPORT_CONSTRAINT if constraint is None else str(constraint)
    fixed = [d for d, c in zip(DOF_ORDER, text) if c == "1"]
    free = [d for d, c in zip(DOF_ORDER, text) if c != "1"]
    return fixed, free


def support_kind(constraint=None):
    """``铰支`` when the translations are held and every rotation is released.

    Derived from the constraint string, so a spec that also fixes the rotations
    is not described with the pinned-base wording this driver was built for.
    """
    fixed, free = dof_split(constraint)
    held = set(fixed)
    if {"DX", "DY", "DZ"} <= held:
        if {"RX", "RY", "RZ"} <= set(free):
            return "铰支"
        if {"RX", "RY", "RZ"} <= held:
            return "刚接"
    return "部分约束"


def struct_type_text():
    """STYP plus the plane it selects, when this driver has verified the code."""
    return STYP_PLANE.get(STYP, f"结构类型代码 {STYP}, 本驱动未验证其平面定义")


def section_text(key):
    """``柱 COLUMN_H400X200X8X12 (H400×200×8×12)`` from the installed section."""
    sect = SECTIONS[key]
    dims = "×".join(f"{float(sect['vSIZE'][i]) * 1000.0:g}" for i in range(4))
    return f"{ROLE_LABEL.get(key, key)} {sect['name']} (H{dims})"


def section_list_text():
    """One entry per role, in the order the elements use them."""
    order = []
    for _eid, _i, _j, kind in ELEMS:
        if kind not in order:
            order.append(kind)
    return ", ".join(section_text(k) for k in order)


# ---------------------------------------------------------------------------
# artifact helpers
# ---------------------------------------------------------------------------
def save(name, data):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2,
                                       allow_nan=False), encoding="utf-8")


def append(name, data):
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / name).open("a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, allow_nan=False) + "\n")


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def load_state():
    return json.loads(STATE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# MCP server: same instrumentation pattern as tests/live_space_grid.py
# ---------------------------------------------------------------------------
def serve():
    from midas_mcp.midas_http import MidasClient
    from midas_mcp.mcp_server import McpServer
    from midas_mcp.__main__ import main
    original = MidasClient._one
    handle = McpServer.handle
    context = {}

    def audited_handle(self, msg):
        context.clear()
        context.update({"rpc_id": msg.get("id"),
                        "tool": msg.get("params", {}).get("name"),
                        "endpoint": msg.get("params", {}).get("arguments", {}).get("endpoint")})
        return handle(self, msg)

    def audited_one(self, method, path, body, timeout, cancel):
        stamp = now()
        response = original(self, method, path, body, timeout, cancel)
        append("http_audit.jsonl", {**context, "timestamp": stamp,
               "base_url": self.cfg.base_url, "method": method, "path": path,
               "request_body": body,
               "request_raw": json.dumps(body, ensure_ascii=False, separators=(",", ":")) if body is not None else None,
               "headers": {"Content-Type": "application/json", "MAPI-Key": "[REDACTED]"},
               "status": response.status, "response_raw": response.raw,
               "duration_ms": response.duration_ms})
        return response

    MidasClient._one = audited_one
    McpServer.handle = audited_handle
    return main([])


class Session:
    def __init__(self, phase):
        self.phase = phase
        self.counter = 0
        self.err = (OUT / "server_stderr.log").open("a", encoding="utf-8")
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        #: The child has to be imported as a package module, not run as a script:
        #: this file uses relative imports, and those have no parent package when
        #: the path is handed to the interpreter directly.
        src = str(Path(__file__).resolve().parents[1])
        env["PYTHONPATH"] = os.pathsep.join(
            [src] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "midas_mcp.frame", "--server"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=self.err, text=True, encoding="utf-8", env=env)
        self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                "clientInfo": {"name": "StructAI-portal-frame-live", "version": "1"}})
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        self.proc.stdin.flush()
        tools = self.rpc("tools/list", {})["result"]["tools"]
        save("tools.json", tools)

    def rpc(self, method, params):
        self.counter += 1
        msg = {"jsonrpc": "2.0", "id": f"{self.phase}-{self.counter}",
               "method": method, "params": params}
        start = time.monotonic()
        self.proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("MCP server closed its output; see server_stderr.log")
        response = json.loads(line)
        append("mcp_audit.jsonl", {"timestamp": now(), "phase": self.phase,
               "request": msg, "response": response,
               "duration_ms": (time.monotonic() - start) * 1000})
        return response

    def call(self, tool, args, required=True, quiet=False, announce=True):
        response = self.rpc("tools/call", {"name": tool, "arguments": args})
        if "error" in response:
            raise RuntimeError(str(response["error"]))
        result = response["result"]["structuredContent"]
        if not result.get("ok"):
            # ALREADY_EXISTS is a *designed* outcome for ``ensure``: a re-run
            # against a project that already holds the record.  Printing it as
            # a failure every run trains the reader to ignore the word FAILED,
            # which is exactly what must not happen in this driver.  ``announce``
            # is for callers that judge the outcome themselves.
            if announce and not (quiet and result.get("category") == "ALREADY_EXISTS"):
                print("FAILED", tool, args.get("endpoint", args.get("command")),
                      result, flush=True)
            if required:
                raise RuntimeError(str(result))
        return result

    def query(self, endpoint, info=False, required=True):
        return self.call("midas_db_query", {"endpoint": endpoint, **({"info": True} if info else {})}, required)

    def records(self, name):
        """The live records of ``DB:<name>``.

        The reply is keyed by the collection name, but MIDAS also answers a
        bare ``{}`` and, for a soft-empty state, an error-shaped body.  Both
        must read as "no records" rather than raise: the preflight uses this to
        decide whether the document is a clean slate.
        """
        result = self.query("DB:" + name)
        data = result.get("data") or {}
        inner = data.get(name)
        if isinstance(inner, dict):
            return inner
        holders = [v for v in data.values() if isinstance(v, dict)]
        return holders[0] if len(holders) == 1 else {}

    def put(self, name, records, mode="create", required=True):
        result = self.call("midas_db_assign", {"endpoint": "DB:" + name, "mode": mode, "data": records}, required)
        if result.get("ok"):
            read = self.records(name)
            save(f"readback_{name}.json", read)
            return read
        return None

    def ensure(self, name, records):
        """Write ``records``, then verify by readback.

        MIDAS answers a re-POST of an existing key with 'Key Already Exist'
        rather than overwriting it, so a restored project makes plain create
        writes fail on records that are already correct.  Retry once as an
        update, and fall back to the live records; the caller still asserts on
        the readback, so a reused record is verified exactly like a new one.
        """
        result = self.call("midas_db_assign", {"endpoint": "DB:" + name,
                           "mode": "create", "data": records}, required=False, quiet=True)
        if result.get("category") == "ALREADY_EXISTS":
            result = self.call("midas_db_assign", {"endpoint": "DB:" + name,
                               "mode": "update", "data": records}, required=False, quiet=True)
            if not result.get("ok"):
                print("ensure: update of existing", name, "failed", result, flush=True)
        read = self.records(name)
        save(f"readback_{name}.json", read)
        return read

    def table(self, kind, cases=None, ids=None, required=False, artifact=None, **extra):
        """POST /post/TABLE.  The reply is keyed by TABLE_NAME, which we set to
        ``kind`` so the parsed table can always be found at ``data[kind]``."""
        data = {"TABLE_TYPE": kind, "TABLE_NAME": kind,
                "UNIT": {"FORCE": "KN", "DIST": "M"},
                "STYLES": {"FORMAT": "Fixed", "PLACE": 6}, **extra}
        if cases:
            data["LOAD_CASE_NAMES"] = cases
        if ids:
            data["NODE_ELEMS"] = {"KEYS": list(ids)}
        result = self.call("midas_db_assign", {"endpoint": "POST:TABLE:" + kind,
                           "mode": "create", "data": data}, required)
        save(f"{artifact or (self.phase + '_' + kind)}.json", result)
        return result

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=10)
        self.err.close()


def table_of(result, kind):
    """The inner table dict of a POST:TABLE reply."""
    return (result.get("data") or {}).get(kind) or {}


def rows_of(table):
    """``[{column: value}, ...]`` from a table dict, driven by its own HEAD."""
    head = [str(h) for h in (table.get("HEAD") or [])]
    return [dict(zip(head, row)) for row in (table.get("DATA") or [])]


def num(row, name):
    """Numeric value of ``name`` in ``row`` (None when absent or blank)."""
    for key, value in row.items():
        if key.strip().lower() == name.strip().lower():
            try:
                return float(str(value).strip())
            except (TypeError, ValueError):
                return None
    return None


def base_load(name):
    return str(name).split("(", 1)[0].strip()


# ---------------------------------------------------------------------------
# progress log
# ---------------------------------------------------------------------------
#: One entry per prompt step: {step, name, ok, detail}.
STEPS: list[dict] = []


def step(n, name, ok, detail=""):
    STEPS.append({"step": n, "name": name, "ok": bool(ok), "detail": detail})
    print(f"[{n:02d}] {'PASS' if ok else 'FAIL'}  {name}  -- {detail}", flush=True)
    return bool(ok)


#: Collections whose contents show whether the document is a clean slate.
COLLECTIONS = ("NODE", "ELEM", "MATL", "SECT", "STLD", "CONS", "BODF", "BMLD",
               "CNLD", "LCOM-GEN", "GRUP", "EIGV")


def preflight(s):
    """Prove the live document is empty before the build touches it.

    ``DOC:NEW`` is deliberately *not* sent: the registry records that it
    destroys the model held in memory, which would also discard unsaved work.
    Not calling it means the build has to show the document is a clean slate
    itself, otherwise the numbers in the report would describe a mixture of
    this frame and whatever was loaded before it.
    """
    state = {name: sorted(s.records(name)) for name in COLLECTIONS}
    save("preflight_collections.json", state)
    occupied = {k: v for k, v in state.items() if v}
    print("preflight: occupied collections =", occupied or "(none)", flush=True)
    return occupied


def put_verify(s, name, records):
    """PUT a singleton collection (STYP/UNIT) and read it back."""
    result = s.call("midas_db_assign",
                    {"endpoint": "DB:" + name, "mode": "update", "data": records},
                    required=True)
    read = s.records(name)
    save(f"readback_{name}.json", read)
    return result, read


def create_verify(s, name, records):
    """Create ``records`` and report which requested keys are missing after."""
    read = s.ensure(name, records)
    missing = [str(k) for k in records if str(k) not in read]
    return read, missing


# ---------------------------------------------------------------------------
# the model: prompt steps 1-6
# ---------------------------------------------------------------------------
def build(s):
    """Steps 1-6: document, material, sections, nodes, elements, supports."""
    # -- step 1: structure type + units --------------------------------
    _, read = put_verify(s, "STYP", {"1": {"STYP": STYP, "MASS": 1,
                                           "bMASSOFFSET": False,
                                           "bSELFWEIGHT": True, "SMASS": 1,
                                           "GRAV": GRAV, "TEMP": 0.0,
                                           "bALIGNBEAM": False,
                                           "bALIGNSLAB": False,
                                           "bROTRIGID": False}})
    styp = read.get("1") or {}
    _, read = put_verify(s, "UNIT", {"1": {"FORCE": "KN", "DIST": "M",
                                           "HEAT": "KJ", "TEMPER": "C"}})
    unit = read.get("1") or {}
    step(1, "创建/初始化模型",
         styp.get("STYP") == STYP and unit.get("FORCE") == "KN"
         and unit.get("DIST") == "M",
         f"STYP={styp.get('STYP')} (1=X-Z Plane), bSELFWEIGHT="
         f"{styp.get('bSELFWEIGHT')} (仅质量转换), 单位 FORCE="
         f"{unit.get('FORCE')} DIST={unit.get('DIST')}")

    # -- step 2: material ------------------------------------------------
    #: P_TYPE 2 = user-defined.  P_TYPE 1 is accepted but silently zeroes
    #: POISN/THERMAL/DEN/MASS (registry note, enforced by guards.correct_payload).
    matl = {"1": {"TYPE": "STEEL", "NAME": MATL_NAME, "HE_SPEC": 0.0,
                  "HE_COND": 0.0, "PLMT": 0, "bMASS_DENS": False,
                  "DAMP_RAT": 0.0,
                  "PARAM": [{"P_TYPE": 2, "bELAST": True,
                             "ELAST": MATL_ELAST, "POISN": MATL_POISN,
                             "THERMAL": 1.2e-05, "DEN": MATL_DEN,
                             "MASS": MATL_MASS}]}}
    read, missing = create_verify(s, "MATL", matl)
    got = (read.get("1") or {}).get("PARAM") or [{}]
    got = got[0] if got else {}
    step(2, "定义材料", not missing and got.get("ELAST") == MATL_ELAST,
         f"{MATL_NAME} E={got.get('ELAST')} kN/m2, nu={got.get('POISN')}, "
         f"DEN={got.get('DEN')} kN/m3, P_TYPE={got.get('P_TYPE')}"
         + (f", 缺失={missing}" if missing else ""))

    # -- step 3: sections ------------------------------------------------
    sects = {}
    for key, spec in SECTIONS.items():
        sects[str(spec["id"])] = {
            "SECTTYPE": "VALUE", "SECT_NAME": spec["name"], "CALC_OPT": True,
            "SECT_BEFORE": {"OFFSET_PT": "CC", "OFFSET_CENTER": 0,
                            "USER_OFFSET_REF": 0, "HORZ_OFFSET_OPT": 0,
                            "USERDEF_OFFSET_YI": 0, "USERDEF_OFFSET_YJ": 0,
                            "VERT_OFFSET_OPT": 0, "USERDEF_OFFSET_ZI": 0,
                            "USERDEF_OFFSET_ZJ": 0,
                            "USE_SHEAR_DEFORM": False,
                            "USE_WARPING_EFFECT": False,
                            "SHAPE": "H", "SECT_I": {"SHAPE": "H",
                                                     "vSIZE": spec["vSIZE"]}}}
    read, missing = create_verify(s, "SECT", sects)
    sizes = {}
    for sid, spec in sects.items():
        before = (read.get(sid) or {}).get("SECT_BEFORE") or {}
        sect_i = before.get("SECT_I") or {}
        sizes[spec["SECT_NAME"]] = sect_i.get("vSIZE")
    step(3, "定义钢梁、钢柱截面",
         not missing and all(
             sizes.get(SECTIONS[k]["name"]) == SECTIONS[k]["vSIZE"]
             for k in SECTIONS),
         ", ".join(f"{k} vSIZE={sizes.get(SECTIONS[k]['name'])}"
                   for k in SECTIONS)
         + (f", 缺失={missing}" if missing else ""))

    # -- step 4: nodes ---------------------------------------------------
    nodes = {str(nid): {"X": x, "Y": y, "Z": z} for nid, x, y, z in NODES}
    read, missing = create_verify(s, "NODE", nodes)
    coords_ok = True
    for nid, x, y, z in NODES:
        got = read.get(str(nid)) or {}
        if (abs(float(got.get("X", 1e9)) - x) > 1e-9
                or abs(float(got.get("Y", 1e9)) - y) > 1e-9
                or abs(float(got.get("Z", 1e9)) - z) > 1e-9):
            coords_ok = False
    step(4, "创建节点", not missing and coords_ok,
         "N1..N5 = " + ", ".join(
             f"N{nid}({x},{y},{z})" for nid, x, y, z in NODES)
         + (f", 缺失={missing}" if missing else ""))

    # -- step 5: elements -------------------------------------------------
    elems = {str(eid): {"TYPE": "BEAM", "MATL": 1,
                        "SECT": SECTIONS[kind]["id"], "NODE": [i, j],
                        "ANGLE": 0.0}
             for eid, i, j, kind in ELEMS}
    read, missing = create_verify(s, "ELEM", elems)
    #: A BEAM is *sent* as NODE=[i, j], but the GET reply pads the array to
    #: MIDAS's eight connectivity slots -- [i, j, 0, 0, 0, 0, 0, 0] -- so the
    #: two real nodes are the first two entries and the rest is padding.  The
    #: comparison reads the first two; a whole-array compare against [i, j]
    #: reports a false failure on an element that was created correctly.
    conn_ok = True
    for eid, i, j, kind in ELEMS:
        got = read.get(str(eid)) or {}
        if list(got.get("NODE") or [])[:2] != [i, j] \
                or got.get("SECT") != SECTIONS[kind]["id"]:
            conn_ok = False
    step(5, "创建梁柱单元", not missing and conn_ok,
         "E1..E4 = " + ", ".join(
             f"E{eid}(N{i}-N{j},{kind} SECT={SECTIONS[kind]['id']})"
             for eid, i, j, kind in ELEMS)
         + (f", 缺失={missing}" if missing else ""))

    # -- step 6: supports -------------------------------------------------
    #: CONSTRAINT is read in the API's own DOF order, printed by the CONS
    #: schema as "(DX,DY,DZ,RX,RY,RZ,RW)" and by the SUPPORTS result table as
    #: "Dx,Dy,Dz,Rx,Ry,Rz,Rw".  "1110000" therefore means UX/UY/UZ fixed and
    #: all three rotations free -- the prompt's pinned base -- without guessing
    #: from DOF *names*.
    cons = {str(nid): {"ITEMS": [{"ID": 1, "GROUP_NAME": "",
                                  "CONSTRAINT": SUPPORT_CONSTRAINT}]}
            for nid in SUPPORTS}
    read, missing = create_verify(s, "CONS", cons)
    stored = {}
    for nid in SUPPORTS:
        items = (read.get(str(nid)) or {}).get("ITEMS") or [{}]
        stored[str(nid)] = (items[0] if items else {}).get("CONSTRAINT")
    step(6, "设置节点边界条件",
         not missing and all(v == SUPPORT_CONSTRAINT for v in stored.values()),
         f"{support_label()} {support_kind()} CONSTRAINT={stored} "
         f"({'/'.join(dof_split()[0])} 固定 / {'/'.join(dof_split()[1])} 自由)"
         + (f", 缺失={missing}" if missing else ""))
    return {"nodes": read}


# ---------------------------------------------------------------------------
# loads and combinations: prompt steps 7-11
# ---------------------------------------------------------------------------
def items_of(read, elem_id):
    """The ITEMS list MIDAS stored for one element (its own readback)."""
    return (read.get(str(elem_id)) or {}).get("ITEMS") or []


def stored_load(read, elem_id, case, direction):
    """The uniform load MIDAS stored for one element/case/direction, or None.

    Read out of the readback rather than echoed from what was sent: a write
    that MIDAS silently dropped looks identical to a successful one otherwise.
    """
    for item in items_of(read, elem_id):
        if str(item.get("LCNAME")) == case \
                and str(item.get("DIRECTION")) == direction:
            p = item.get("P") or []
            return float(p[0]) if p else None
    return None


def bmld_records():
    """Every beam load, grouped by element.

    ``DB:BMLD`` is keyed by element and a second POST for the same element is
    answered with "Key Already Exist" rather than merged, so all of one
    element's items have to travel in a single record.  Grouping here is what
    makes it impossible to lose the LIVE load on E2 behind the DEAD one.
    """
    per_elem: dict[int, list] = {}
    for elem_id, case, direction, q in BEAM_LOADS:
        per_elem.setdefault(elem_id, []).append((case, direction, q))
    records = {}
    for elem_id, items in per_elem.items():
        records[str(elem_id)] = {"ITEMS": [
            {"ID": i + 1, "LCNAME": case, "GROUP_NAME": "", "CMD": "BEAM",
             "TYPE": "UNILOAD", "DIRECTION": direction,
             "USE_PROJECTION": False, "USE_ECCEN": False,
             "D": [0, 1, 0, 0], "P": [q, q, 0, 0]}
            for i, (case, direction, q) in enumerate(items)]}
    return records


def same_terms(got, want):
    """Compare a stored (case, factor) list with the requested one."""
    if len(got) != len(want):
        return False
    for (g_case, g_factor), (w_case, w_factor) in zip(got, want):
        if g_case != w_case or g_factor is None:
            return False
        if abs(float(g_factor) - float(w_factor)) > 1e-9:
            return False
    return True


def loads(s):
    """Steps 7-11: load cases, self weight, roof dead, roof live, wind, combos.

    The load cases are written first even though the prompt numbers them 10th:
    a load record names its case, and MIDAS accepts a load for a case that does
    not exist and then never solves it.  The report still uses the prompt's
    numbering.
    """
    # -- step 10: load cases ---------------------------------------------
    cases = {str(i + 1): {"NO": i + 1, "NAME": name, "TYPE": kind,
                          "DESC": desc}
             for i, (name, kind, desc) in enumerate(CASES)}
    read_cases, missing = create_verify(s, "STLD", cases)
    stored_cases = {rec.get("NAME"): rec.get("TYPE")
                    for rec in read_cases.values()}
    step(10, "定义荷载工况",
         not missing and all(stored_cases.get(n) == t for n, t, _ in CASES),
         "STLD = " + ", ".join(f"{k}({v})" for k, v in stored_cases.items())
         + (f", 缺失={missing}" if missing else ""))

    # -- step 7 (part 1): self weight, once, in DEAD ----------------------
    #: bSELFWEIGHT in STYP is self-weight -> *mass* conversion for the modal
    #: run; it is not a static load.  The static self weight is this single
    #: BODF record, so the frame's own weight is applied exactly once.
    bodf = {"1": {"LCNAME": "DEAD", "GROUP_NAME": "",
                  "FV": [0.0, 0.0, -1.0]}}
    read_bodf, bodf_missing = create_verify(s, "BODF", bodf)
    self_weight = (read_bodf.get("1") or {}).get("FV")

    # -- steps 7b/8/9: roof dead, roof live, wind (one POST) --------------
    read_bmld, bmld_missing = create_verify(s, "BMLD", bmld_records())

    roof_dead = [stored_load(read_bmld, e, "DEAD", "GZ") for e in (2, 3)]
    step(7, "定义恒载(自重+屋面恒载)",
         not bodf_missing and not bmld_missing
         and self_weight == [0.0, 0.0, -1.0]
         and roof_dead == [ROOF_DEAD_Q, ROOF_DEAD_Q],
         f"自重 BODF LCNAME=DEAD FV={self_weight} 系数1.0 (仅此一次), "
         f"屋面恒载 E2/E3={roof_dead} kN/m GZ")

    roof_live = [stored_load(read_bmld, e, "LIVE", "GZ") for e in (2, 3)]
    step(8, "定义屋面活载",
         roof_live == [ROOF_LIVE_Q, ROOF_LIVE_Q],
         f"屋面活载 E2/E3={roof_live} kN/m GZ (LC=LIVE)")

    wind_pos = [stored_load(read_bmld, e, "WIND_X_POS", "GX") for e in (1, 4)]
    wind_neg = [stored_load(read_bmld, e, "WIND_X_NEG", "GX") for e in (1, 4)]
    step(9, "定义基本风荷载",
         wind_pos == [WIND_Q, WIND_Q] and wind_neg == [-WIND_Q, -WIND_Q],
         f"E1/E4 水平线荷载 +X={wind_pos} kN/m, -X={wind_neg} kN/m")

    # -- step 11: combinations --------------------------------------------
    combos = {}
    for i, (name, desc, terms) in enumerate(COMBOS):
        combos[str(i + 1)] = {
            "NO": i + 1, "NAME": name, "ACTIVE": "ACTIVE", "bCB": False,
            "iTYPE": 0, "DESC": desc,
            "vCOMB": [{"ANAL": "ST", "LCNAME": case, "FACTOR": factor}
                      for case, factor in terms]}
    read_combo, combo_missing = create_verify(s, "LCOM-GEN", combos)
    stored_combos = {}
    for rec in read_combo.values():
        stored_combos[rec.get("NAME")] = [
            (t.get("LCNAME"), t.get("FACTOR")) for t in (rec.get("vCOMB") or [])]
    combo_ok = not combo_missing and all(
        same_terms(stored_combos.get(name, []), list(terms))
        for name, _, terms in COMBOS)
    step(11, "定义荷载组合", combo_ok,
         "; ".join(f"{n}=" + "+".join(f"{f}{c}" for c, f in stored_combos.get(n, []))
                   for n, _, _ in COMBOS)
         + (f", 缺失={combo_missing}" if combo_missing else ""))
    return {"STLD": read_cases, "BODF": read_bodf, "BMLD": read_bmld,
            "LCOM-GEN": read_combo}


# ---------------------------------------------------------------------------
# pre-analysis checks and the analysis itself: prompt step 12
# ---------------------------------------------------------------------------
def checks(s):
    """The six model checks the prompt requires before solving.

    Each one reads the live model rather than the payload that was sent, so a
    record MIDAS refused to store cannot pass a check by having been requested.
    """
    nodes = s.records("NODE")
    elems = s.records("ELEM")
    matl = s.records("MATL")
    sect = s.records("SECT")
    cons = s.records("CONS")
    findings = []

    #: NODE comes back padded to eight connectivity slots (see step 5), so the
    #: node ids an element actually uses are the non-zero entries; reading the
    #: padding as node ids invents a node "0" and breaks the connectivity walk.
    def elem_nodes(rec):
        return [str(n) for n in (rec.get("NODE") or [])[:2] if int(n or 0)]

    used: set[str] = set()
    for rec in elems.values():
        used.update(elem_nodes(rec))
    orphans = sorted(set(nodes) - used, key=lambda x: int(x) if x.isdigit() else 0)
    findings.append(("孤立节点", not orphans, f"孤立节点={orphans or '无'}"))

    no_matl = sorted(eid for eid, r in elems.items()
                     if str(r.get("MATL")) not in matl)
    findings.append(("未定义材料", not no_matl,
                     f"引用不存在材料的单元={no_matl or '无'}"))

    no_sect = sorted(eid for eid, r in elems.items()
                     if str(r.get("SECT")) not in sect)
    findings.append(("未定义截面", not no_sect,
                     f"引用不存在截面的单元={no_sect or '无'}"))

    # Connectivity + restraint: a frame can be fully connected and still be a
    # mechanism, which only the solver can settle, so this check reports the
    # evidence it can and defers the verdict to the analysis result.
    adjacency: dict[str, set[str]] = {n: set() for n in nodes}
    for rec in elems.values():
        pair = elem_nodes(rec)
        if len(pair) == 2:
            adjacency.setdefault(pair[0], set()).add(pair[1])
            adjacency.setdefault(pair[1], set()).add(pair[0])
    seen, stack = set(), [next(iter(nodes), None)]
    while stack:
        cur = stack.pop()
        if cur is None or cur in seen:
            continue
        seen.add(cur)
        stack.extend(adjacency.get(cur, ()))
    connected = bool(nodes) and seen == set(nodes)
    supports = support_nodes()
    restrained = bool(supports) and all(
        ((cons.get(n) or {}).get("ITEMS") or [{}])[0].get("CONSTRAINT")
        for n in supports)
    findings.append(("机构/稳定性", connected and restrained,
                     f"节点连通={connected}({len(seen)}/{len(nodes)}), "
                     f"约束节点={sorted(cons)}"))

    writes = {"BODF": s.records("BODF"), "BMLD": s.records("BMLD")}
    findings.append(("荷载写入", all(writes.values()),
                     "BODF/BMLD 记录数=" + str({k: len(v) for k, v in writes.items()})))
    findings.append(("边界条件", restrained,
                     "CONS=" + str({k: ((v.get('ITEMS') or [{}])[0].get('CONSTRAINT'))
                                    for k, v in cons.items()})))

    save("checks.json", [{"name": n, "ok": ok, "detail": d}
                         for n, ok, d in findings])
    for name, ok, detail in findings:
        print(f"      check {'OK  ' if ok else 'BAD '} {name}: {detail}", flush=True)
    return findings


def analyze(s, label="anal"):
    """Step 12: run ``/doc/ANAL`` and confirm it by reading a result table.

    A 200 from ``/doc/ANAL`` is not proof that results exist, and Gen NX 2027
    also answers HTTP 400 with a ``[警告]`` warning while running the analysis
    anyway.  The confirmation is therefore a result table with rows in it.
    """
    result = s.call("midas_doc", {"command": "ANAL", "argument": {}}, required=False)
    save(f"{label}_raw.json", result)
    accepted = bool(result.get("ok"))
    note = result.get("note") or result.get("warning") or result.get("message") or ""
    detail = (f"category={result.get('category')} http_status="
              f"{result.get('http_status')} status={result.get('status')}")
    if note:
        detail += f" | {str(note)[:220]}"

    probe = s.table("REACTIONG", cases=["DEAD(ST)"],
                    artifact=f"{label}_probe_reactiong.json", required=False)
    rows = rows_of(table_of(probe, "REACTIONG"))
    confirmed = bool(rows)
    step(12, "执行结构分析", accepted and confirmed,
         detail + f" | 结果表 REACTIONG 行数={len(rows)}")
    return {"anal": result, "rows": rows, "confirmed": confirmed}

# ---------------------------------------------------------------------------
# results: prompt steps 13-17
# ---------------------------------------------------------------------------
NODE_XYZ = {nid: (x, y, z) for nid, x, y, z in NODES}
ELEM_LEN = {eid: math.dist(NODE_XYZ[i], NODE_XYZ[j]) for eid, i, j, _ in ELEMS}

#: (report key, MIDAS column) per table.  The MIDAS column names come from the
#: table's own HEAD (docs/manual/19_POST_AnalysisResult_1.md):
#:   DISPLACEMENTG ["Index","Node","Load","DX","DY","DZ","RX","RY","RZ"]
#:   REACTIONG     ["Index","Node","Load","FX","FY","FZ","MX","MY","MZ","Mb"]
#:   BEAMFORCE     ["Index","Elem","Load","Part","Axial","Shear-y","Shear-z",
#:                  "Torsion","Moment-y","Moment-z",...]
#: They are looked up by name, never by position, and the mapping from the
#: prompt's N/V2/V3/M2/M3/T onto MIDAS's own spellings is stated in the report
#: rather than assumed.
DISP_COLS = (("UX", "DX"), ("UY", "DY"), ("UZ", "DZ"),
             ("RX", "RX"), ("RY", "RY"), ("RZ", "RZ"))
FORCE_COLS = (("N", "Axial"), ("V2", "Shear-y"), ("V3", "Shear-z"),
              ("T", "Torsion"), ("M2", "Moment-y"), ("M3", "Moment-z"))
REACT_COLS = (("FX", "FX"), ("FY", "FY"), ("FZ", "FZ"),
              ("MX", "MX"), ("MY", "MY"), ("MZ", "MZ"))

#: Modes requested of the eigenvalue solver.  This is the number the solver
#: actually computes: widening the MODES list on the table request alone
#: changes nothing (knowledge.PITFALLS), so DB:EIGV.iFREQ is what is verified.
MODES = 6


def load_names():
    """Every load name to ask a POST:TABLE for, in a single request.

    The ``(ST)``/``(CB)`` suffix is mandatory.  MIDAS answers a bare name with
    HTTP 200 and *no rows at all*, so an unsuffixed request is indistinguishable
    from "this load produced no results" - the trap is recorded in
    knowledge.PITFALLS and confirmed live on this build.
    """
    return ([f"{name}(ST)" for name, _, _ in CASES]
            + [f"{name}(CB)" for name in COMBO_NAMES])


def dist_to_mm(table):
    """Millimetre factor for the DIST unit the reply declares, or None.

    The reply states its own unit; a mm/m mix-up scales moments and deflections
    by 1000 (knowledge.PITFALLS), so the factor is read rather than assumed and
    an unknown unit is reported as unknown instead of guessed at.
    """
    unit = str(table.get("DIST") or "").strip().upper()
    return {"M": 1000.0, "MM": 1.0, "CM": 10.0}.get(unit)


def grab(s, kind, cases, ids=None):
    """One POST:TABLE reply, its primary table, and that table's rows."""
    result = s.table(kind, cases=cases, ids=ids, required=True,
                     artifact=f"res_{kind.lower()}.json")
    table = table_of(result, kind)
    return result, table, rows_of(table)


def collect(s):
    """Steps 13-16: read the three static result tables and index them.

    Every number in the report comes out of one of these replies.  Nothing is
    recomputed and nothing is filled in from theory: a row MIDAS did not send
    leaves the corresponding entry absent, and the step that needed it fails.
    """
    names = load_names()
    disp_r, disp_t, disp_rows = grab(s, "DISPLACEMENTG", names)
    force_r, force_t, force_rows = grab(s, "BEAMFORCE", names)
    react_r, react_t, react_rows = grab(s, "REACTIONG", names, ids=SUPPORTS)

    step(13, "查询分析结果",
         bool(disp_rows) and bool(force_rows) and bool(react_rows),
         f"DISPLACEMENTG {len(disp_rows)} 行 / BEAMFORCE {len(force_rows)} 行 / "
         f"REACTIONG {len(react_rows)} 行, HEAD 取自各自响应 "
         f"(DIST={disp_t.get('DIST')}, FORCE={disp_t.get('FORCE')})")

    disp = {}
    for row in disp_rows:
        node = num(row, "Node")
        if node is None:
            continue
        disp[(int(node), base_load(row.get("Load")))] = {
            key: num(row, col) for key, col in DISP_COLS}

    want = [(nid, combo) for nid, _, _, _ in NODES for combo in COMBO_NAMES]
    gaps = [f"N{nid}/{combo}" for nid, combo in want if (nid, combo) not in disp]
    step(14, "查询节点位移", not gaps,
         f"5 节点 x 4 组合 = {len(want)} 组位移, 缺失={gaps or '无'}")

    forces = {}
    for row in force_rows:
        elem = num(row, "Elem")
        if elem is None:
            continue
        forces.setdefault((int(elem), base_load(row.get("Load"))), []).append(
            {"part": str(row.get("Part") or "").strip(),
             **{key: num(row, col) for key, col in FORCE_COLS}})
    fgaps = [f"E{eid}/{combo}" for eid, _, _, _ in ELEMS for combo in COMBO_NAMES
             if (eid, combo) not in forces]
    step(15, "查询构件内力", not fgaps,
         f"E1..E4 x 4 组合 内力, 缺失={fgaps or '无'}, 单元截面位置数="
         + str({f"E{e}": len(v) for e, v in sorted(forces.items())}))

    react = {}
    for row in react_rows:
        node = num(row, "Node")
        if node is None:
            continue
        react[(int(node), base_load(row.get("Load")))] = {
            key: num(row, col) for key, col in REACT_COLS}
    rgaps = [f"N{nid}/{combo}" for nid in SUPPORTS for combo in COMBO_NAMES
             if (nid, combo) not in react]
    step(16, "查询支座反力", not rgaps,
         f"{support_label()} x {len(COMBO_NAMES)} 组合 反力, 缺失={rgaps or '无'}")

    return {"disp": disp, "forces": forces, "react": react,
            "tables": {"DISPLACEMENTG": disp_t, "BEAMFORCE": force_t,
                       "REACTIONG": react_t},
            "replies": {"DISPLACEMENTG": disp_r, "BEAMFORCE": force_r,
                        "REACTIONG": react_r}}


# ---------------------------------------------------------------------------
# step 17: extremes, and an independent check that the numbers are consistent
# ---------------------------------------------------------------------------
def peak(pairs):
    """``(item, load, value)`` for the largest absolute value, or ``None``."""
    best = None
    for item, load, value in pairs:
        if value is None:
            continue
        if best is None or abs(value) > abs(best[2]):
            best = (item, load, value)
    return best


def applied_resultants():
    """Applied resultants of the load cases that carry no self weight.

    Only LIVE and WIND are described here, because only those are fully
    determined by the prompt: their UDLs are the whole load on the frame, so the
    reaction sums can be compared with them exactly.  DEAD carries the frame's
    own weight on top, so its residual is *reported* as the self weight rather
    than asserted against a hand formula.
    """
    out = {}
    my = 0.0
    fz = 0.0
    for eid in (2, 3):
        i, j, _ = next((a, b, k) for e, a, b, k in ELEMS if e == eid)
        cx = (NODE_XYZ[i][0] + NODE_XYZ[j][0]) / 2.0
        cz = (NODE_XYZ[i][2] + NODE_XYZ[j][2]) / 2.0
        f = ROOF_LIVE_Q * ELEM_LEN[eid]
        fz += f
        #: MY about the global Y axis for an X-Z plane frame: M = z*FX - x*FZ,
        #: evaluated at each UDL's resultant point (the element midpoint).
        my += cz * 0.0 - cx * f
    out["LIVE"] = {"FX": 0.0, "FZ": fz, "MY": my}
    for name, sign in (("WIND_X_POS", 1.0), ("WIND_X_NEG", -1.0)):
        fx = 0.0
        my = 0.0
        for eid in (1, 4):
            i, j, _ = next((a, b, k) for e, a, b, k in ELEMS if e == eid)
            cx = (NODE_XYZ[i][0] + NODE_XYZ[j][0]) / 2.0
            cz = (NODE_XYZ[i][2] + NODE_XYZ[j][2]) / 2.0
            f = sign * WIND_Q * ELEM_LEN[eid]
            fx += f
            my += cz * f - cx * 0.0
        out[name] = {"FX": fx, "FZ": 0.0, "MY": my}
    return out


def _norm(name):
    """A column name compared case- and separator-insensitively."""
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def element_weights(s):
    """Total self weight MIDAS assigns to each element, in kN.

    ``ELEMENTWEIGHT``'s HEAD repeats ``No``/``Name`` once per foreign key, so
    its columns cannot be addressed by position from the start.  The live HEAD
    is ``['Index', 'No', 'Type', 'No', 'Name', 'No', 'Name', 'No', 'Name',
    'Type', 'Value', 'Unit Weight', 'Total Weight']``.  Both the element id and
    the weight are therefore located by *name*, with separators and case
    removed so ``Total Weight`` matches ``TotalWeight`` - which is what the
    prompt asks for: read the real reply shape, then adapt the parser.  The
    reply declares its own force unit and the value is converted from that
    declaration, not from an assumption.
    """
    result = s.table("ELEMENTWEIGHT", ids=sorted(ELEM_LEN), required=False,
                     artifact="res_elementweight.json")
    table = table_of(result, "ELEMENTWEIGHT")
    head = [str(h) for h in (table.get("HEAD") or [])]
    norm = [_norm(h) for h in head]
    try:
        weight_at = norm.index("totalweight")
    except ValueError:
        return None, None, f"HEAD has no Total Weight column: {head}"
    #: The element number is the first column named ``No``; ``Index`` is the
    #: row counter, which is not the element id on every build, so falling back
    #: to it silently would key the per-element weights on the wrong number.
    id_at = next((i for i, name in enumerate(norm) if name == "no"), None)
    if id_at is None:
        return None, None, f"HEAD has no element 'No' column: {head}"
    unit = str(table.get("FORCE") or "").strip().upper()
    scale = {"N": 1e-3, "KN": 1.0, "KGF": 9.80665e-3, "TONF": 9.80665}.get(unit)
    if scale is None:
        return None, unit, f"unrecognised force unit {unit!r}"
    per = {}
    for row in table.get("DATA") or []:
        if not isinstance(row, list) or len(row) <= weight_at:
            continue
        try:
            per[int(float(str(row[id_at]).strip()))] = \
                float(str(row[weight_at]).strip()) * scale
        except (TypeError, ValueError):
            continue
    return per, unit, ""


def extremes(s, data):
    """Step 17: the eight extremes the prompt asks for, plus a balance check."""
    disp, forces, react = data["disp"], data["forces"], data["react"]
    mm = dist_to_mm(data["tables"]["DISPLACEMENTG"])
    nodes = [nid for nid, _, _, _ in NODES]
    elems = [eid for eid, _, _, _ in ELEMS]
    loads = list(COMBO_NAMES)

    def d(node, load, key):
        value = (disp.get((node, load)) or {}).get(key)
        return None if value is None or mm is None else value * mm

    def force(elem, load, key):
        """Largest absolute value of ``key`` along the element, or None."""
        best = None
        for row in forces.get((elem, load)) or []:
            value = row.get(key)
            if value is not None and (best is None or abs(value) > abs(best)):
                best = value
        return best

    def reaction(node, load, key):
        return (react.get((node, load)) or {}).get(key)

    found = {
        "最大节点 UX": peak([(f"N{n}", l, d(n, l, "UX"))
                          for n in nodes for l in loads]),
        "最大节点 UZ": peak([(f"N{n}", l, d(n, l, "UZ"))
                          for n in nodes for l in loads]),
        "最大绝对节点位移": peak([
            (f"N{n}", l,
             max((abs(v) for v in (d(n, l, k) for k, _ in DISP_COLS[:3])
                  if v is not None), default=None))
            for n in nodes for l in loads]),
        "最大轴力 N": peak([(f"E{e}", l, force(e, l, "N"))
                         for e in elems for l in loads]),
        "最大剪力 V": peak([(f"E{e}", l, v) for e in elems for l in loads
                         for v in (force(e, l, "V3"), force(e, l, "V2"))
                         if v is not None]),
        "最大弯矩 M": peak([(f"E{e}", l, v) for e in elems for l in loads
                         for v in (force(e, l, "M2"), force(e, l, "M3"))
                         if v is not None]),
        "最大支座水平反力": peak([(f"N{n}", l, reaction(n, l, "FX"))
                            for n in SUPPORTS for l in loads]),
        "最大支座竖向反力": peak([(f"N{n}", l, reaction(n, l, "FZ"))
                            for n in SUPPORTS for l in loads]),
    }
    step(17, "汇总最大结果", all(v is not None for v in found.values()),
         "; ".join(f"{k}={v[2]:.3f}@{v[0]}/{v[1]}" if v else f"{k}=无"
                   for k, v in found.items()))

    applied = applied_resultants()
    balance = []
    for case in ("LIVE", "WIND_X_POS", "WIND_X_NEG"):
        want = applied[case]
        got = {k: sum(reaction(n, case, k) or 0.0 for n in SUPPORTS)
               for k in ("FX", "FZ")}
        #: The bases are pinned, so every reaction *moment* component is
        #: released and reads 0.  Summing MY would therefore compare zero
        #: against the applied moment and always leave a bogus residual.  The
        #: reaction side of the moment balance is the moment of the reaction
        #: *forces* about the origin: M_Y = sum(z*FX - x*FZ).
        got["MY"] = sum(
            NODE_XYZ[n][2] * (reaction(n, case, "FX") or 0.0)
            - NODE_XYZ[n][0] * (reaction(n, case, "FZ") or 0.0)
            for n in SUPPORTS)
        balance.append({
            "case": case,
            "sum_FX": got["FX"], "applied_FX": want["FX"],
            "residual_FX": got["FX"] + want["FX"],
            "sum_FZ": got["FZ"], "applied_FZ": want["FZ"],
            "residual_FZ": got["FZ"] + want["FZ"],
            "sum_MY": got["MY"], "applied_MY": want["MY"],
            "residual_MY": got["MY"] + want["MY"]})
    dead_fz = sum(reaction(n, "DEAD", "FZ") or 0.0 for n in SUPPORTS)
    roof_dead = sum(ROOF_DEAD_Q * ELEM_LEN[e] for e in (2, 3))
    per, unit, why = element_weights(s)
    #: Vertical equilibrium: the upward reactions carry the roof dead load
    #: *and* the frame's own weight, so the self weight the solver actually
    #: applied is -(sum_FZ + roof_dead).  The previous form (sum_FZ -
    #: roof_dead) added the roof load instead of removing it, and reported
    #: 43.66 kN where the element weights say 23.26 kN.
    implied_self_weight = -(dead_fz + roof_dead)
    total = None if per is None else sum(per.values())
    balance.append({"case": "DEAD", "sum_FZ": dead_fz,
                    "roof_dead_FZ": roof_dead,
                    "implied_self_weight": implied_self_weight,
                    "elementweight_total": total,
                    #: ``implied_self_weight`` is signed (downward is -Z);
                    #: ``ELEMENTWEIGHT`` states a positive magnitude, so the
                    #: residual compares magnitudes.
                    "selfweight_residual": None if total is None
                    else total - abs(implied_self_weight),
                    "elementweight_unit": unit, "elementweight_error": why,
                    "per_element": per})
    save("balance.json", balance)
    return found, balance


def modal(s):
    """Read the modal summary the connector parsed out of the reply's SUB_TABLES.

    ``POST:TABLE:EIGENVALUEMODE``'s own ``DATA`` holds per-node mode shapes and
    nothing that looks like a frequency; the frequencies, periods, participation
    masses and direction factors are in the same reply's ``SUB_TABLES``, which
    the connector parses into ``result_summary.modal_result``.  Both the raw
    table and the parsed summary are kept so the numbers can be traced back.
    """
    result = s.table("EIGENVALUEMODE", required=False,
                     artifact="res_eigenvaluemode.json",
                     **{"MODES": [f"Mode{i}" for i in range(1, MODES + 1)]})
    table = table_of(result, "EIGENVALUEMODE")
    parsed = (result.get("result_summary") or {}).get("modal_result")
    rows = rows_of(table)
    sub_names = [n for n, _ in sub_tables_of(table)]
    print(f"      EIGENVALUEMODE: {len(rows)} 行主表, SUB_TABLES={sub_names}",
          flush=True)
    return parsed, table, rows, sub_names


def sub_tables_of(table):
    """``[(name, body), ...]`` from a table's ``SUB_TABLES`` array."""
    out = []
    for entry in (table.get("SUB_TABLES") or []):
        if isinstance(entry, dict):
            for name, body in entry.items():
                if isinstance(body, dict):
                    out.append((str(name), body))
    return out


def criteria(steps_by_no, data, peaks, modal_parsed, sub_names):
    """The prompt's thirteen PASS/FAIL rows, each tied to its own evidence."""
    def ok(n):
        return bool(steps_by_no.get(n, {}).get("ok"))

    static_subs = []
    for reply in data["replies"].values():
        static_subs.extend((reply.get("result_summary") or {}).get("sub_tables")
                           or [])
    every_sub = sorted(set(static_subs) | set(sub_names))
    modes = (modal_parsed or {}).get("modes") or []
    first = modes[0] if modes else {}
    return [
        ("模型创建", ok(1), steps_by_no.get(1, {}).get("detail", "")),
        ("材料创建", ok(2), steps_by_no.get(2, {}).get("detail", "")),
        ("截面创建", ok(3), steps_by_no.get(3, {}).get("detail", "")),
        ("节点创建", ok(4), steps_by_no.get(4, {}).get("detail", "")),
        ("单元创建", ok(5), steps_by_no.get(5, {}).get("detail", "")),
        ("边界条件", ok(6), steps_by_no.get(6, {}).get("detail", "")),
        ("荷载工况", ok(10), steps_by_no.get(10, {}).get("detail", "")),
        ("荷载组合", ok(11), steps_by_no.get(11, {}).get("detail", "")),
        ("分析执行", ok(12), steps_by_no.get(12, {}).get("detail", "")),
        ("结果查询", ok(13), steps_by_no.get(13, {}).get("detail", "")),
        ("SUB_TABLES 解析", bool(every_sub),
         f"解析到 {len(every_sub)} 个 SUB_TABLES: {every_sub}"),
        ("modal_result 解析", bool(modes),
         (f"mode_count={(modal_parsed or {}).get('mode_count')}, "
          f"mode1 = {first.get('frequency_hz')} Hz / {first.get('period_s')} s, "
          f"累计参与质量(%)={(modal_parsed or {}).get('cumulative_ratio_percent')}"
          if modes else "无模态数据")),
        ("极值提取", all(v is not None for v in peaks.values()),
         f"{len(peaks)} 项极值提取成功="
         f"{sum(1 for v in peaks.values() if v)}/{len(peaks)}"),
    ]


#: Absolute tolerances for the independent load-balance cross-check, in kN and
#: kN*m.  The residuals this model produced are all below 1e-5, so 1e-3 is a
#: loose bound that still catches a load that is missing, duplicated or applied
#: in the wrong direction.
BALANCE_TOL = 1e-3


def balance_verdict(balance):
    """Assert the load balance, instead of only printing it.

    ``criteria()`` covers the prompt's thirteen rows.  These residuals are a
    self-consistency check the driver adds on top, so they are reported
    separately - but they still gate the exit code, because a run that prints
    "与 ELEMENTWEIGHT 不一致, 需复核" must not also exit 0.
    """
    rows = []
    for entry in balance:
        case = entry["case"]
        if case == "DEAD":
            total = entry.get("elementweight_total")
            residual = entry.get("selfweight_residual")
            implied = entry.get("implied_self_weight")
            #: The gravity load is applied along -Z, so the back-calculated
            #: self weight must be downward; comparing magnitudes alone would
            #: also accept a self weight applied upward.
            good = (not entry.get("elementweight_error") and total is not None
                    and residual is not None and abs(residual) <= BALANCE_TOL
                    and implied is not None and implied < 0)
            rows.append((
                f"{case} 自重只施加一次", good,
                f"反推自重={fmt(implied)} kN vs ELEMENTWEIGHT={fmt(total)} kN, "
                f"残差={fmt(residual, 6)} kN"
                + (f", {entry['elementweight_error']}"
                   if entry.get("elementweight_error") else "")))
            continue
        worst = max(abs(entry["residual_FX"]), abs(entry["residual_FZ"]),
                    abs(entry["residual_MY"]))
        rows.append((
            f"{case} 荷载平衡", worst <= BALANCE_TOL,
            f"残差 FX={fmt(entry['residual_FX'], 6)}, "
            f"FZ={fmt(entry['residual_FZ'], 6)}, "
            f"MY={fmt(entry['residual_MY'], 6)} kN/kN·m (容差 {BALANCE_TOL:g})"))
    return rows

# ---------------------------------------------------------------------------
# the run: prompt step 12 (with remediation) and step 18
# ---------------------------------------------------------------------------
def steps_by_number():
    """Last entry per step number: a retried step reports its final outcome."""
    return {entry["step"]: entry for entry in STEPS}


def eigen(s):
    """``DB:EIGV`` -- the eigenvalue control, written *before* the solve.

    ``EIGENVALUEMODE`` reports whatever the solver actually computed, and the
    solver takes its mode count from this record rather than from the table
    request, so writing it is what makes the modal reply non-empty at all
    (knowledge.PITFALLS).  ``TYPE`` is LANCZOS because ``EIGEN`` is refused
    outright on a model with rigid diaphragms and then blocks every later
    analysis until the record is deleted.

    Not one of the prompt's eighteen steps: it is a prerequisite for the
    ``modal_result 解析`` acceptance criterion, and it is reported as such.
    """
    payload = {"1": {"TYPE": "LANCZOS", "iFREQ": MODES, "bMINMAX": False,
                     "bSTRUM": False}}
    read, missing = create_verify(s, "EIGV", payload)
    got = read.get("1") or {}
    try:
        count = int(got.get("iFREQ"))
    except (TypeError, ValueError):
        count = None
    good = (not missing and str(got.get("TYPE") or "").upper() == "LANCZOS"
            and count == MODES)
    print(f"      [--] {'OK  ' if good else 'BAD '} 模态前置 DB:EIGV: "
          f"TYPE={got.get('TYPE')} iFREQ={got.get('iFREQ')}"
          + (f", 缺失={missing}" if missing else ""), flush=True)
    return good


def solve(s):
    """Step 12, wrapped in the remediation loop the prompt requires.

    The prompt forbids ending the run on an analysis failure: the message MIDAS
    returned has to be read, a correction attempted, and the analysis re-run.
    Both retries below correct for a *specific* observed reply -- a 400 that
    still solved, and the one control the solver refuses to share with a later
    analysis when its TYPE is wrong -- and every attempt is recorded, so the
    report can show what was tried instead of implying a clean first-pass solve.
    """
    attempts = []

    def attempt(number, action, label):
        outcome = analyze(s, label=label)
        reply = outcome["anal"] or {}
        attempts.append({
            "attempt": number, "action": action,
            "confirmed": outcome["confirmed"],
            "category": reply.get("category"),
            "http_status": reply.get("http_status"),
            "status": reply.get("status"),
            "message": str(reply.get("message") or reply.get("note")
                           or reply.get("warning") or "")[:600]})
        return outcome

    outcome = attempt(1, "初始 /doc/ANAL", "anal")
    if not outcome["confirmed"]:
        for number, action in enumerate(("等待 3s 后重试 /doc/ANAL",
                                         "删除 DB:EIGV 后重试 /doc/ANAL"),
                                        start=2):
            time.sleep(3.0)
            if action.startswith("删除"):
                s.call("midas_db_delete", {"endpoint": "DB:EIGV",
                                           "target_ids": ["1"]}, required=False)
            outcome = attempt(number, action, f"anal_retry{number}")
            if outcome["confirmed"]:
                if action.startswith("删除"):
                    eigen(s)        # put the control back for the modal step
                break
    save("analysis_attempts.json", attempts)
    if not outcome["confirmed"]:
        print("      分析失败: 逐次尝试的 MIDAS 返回信息", flush=True)
        for entry in attempts:
            print(f"        尝试{entry['attempt']} [{entry['action']}] "
                  f"category={entry['category']} "
                  f"http={entry['http_status']} status={entry['status']} :: "
                  f"{entry['message']}", flush=True)
    return outcome, attempts

# ---------------------------------------------------------------------------
# prompt section 19: the final report
# ---------------------------------------------------------------------------
def fmt(value, digits=3):
    """Fixed-point text, or an em dash when MIDAS sent nothing."""
    return "—" if value is None else f"{value:.{digits}f}"


def report_head(w, disp_table, mm):
    """Prompt section 19 items 1-3: run context, model, loads, combinations."""
    w("# MIDAS MCP 钢门架端到端测试报告")
    w()
    w(f"- 运行时间: {now()}")
    try:
        tools = [t.get("name") for t in
                 json.loads((OUT / "tools.json").read_text(encoding="utf-8"))]
    except (OSError, ValueError, TypeError, AttributeError):
        tools = []
    try:
        shown = OUT.relative_to(ROOT).as_posix()
    except ValueError:
        shown = str(OUT)
    w(f"- MCP 目标: `{os.environ.get('MIDAS_BASE_URL', '(unknown)')}` — stdio MCP, "
      + (f"{len(tools)} 个工具 ({' / '.join(tools)})" if tools
         else "工具清单不可读 (tools.json)"))
    w(f"- 结果单位: 取自 MIDAS 响应自身的声明 — DIST={disp_table.get('DIST')} "
      f"FORCE={disp_table.get('FORCE')}"
      + ("" if mm else " (DIST 未识别, 位移不做换算)"))
    w(f"- 工件目录: `{shown}/` "
      "(res_*.json / readback_*.json / mcp_audit.jsonl / http_audit.jsonl)")
    w()
    w("## 1. 模型信息")
    w()
    w("| 项目 | 参数 |")
    w("| --- | --- |")
    w("| 结构类型 | 单层双坡钢门式刚架 |")
    w(f"| 跨度 | {SPAN:g} m |")
    w(f"| 柱高 | {EAVE:g} m |")
    w(f"| 屋脊高度 | {RIDGE:g} m |")
    w(f"| 材料 | {MATL_NAME} (E={MATL_ELAST / 1000.0:.0f} MPa, ν={MATL_POISN}, "
      f"γ={MATL_DEN} kN/m³, P_TYPE=2 自定义) |")
    w(f"| 节点数量 | {len(NODES)} |")
    w(f"| 单元数量 | {len(ELEMS)} |")
    w(f"| 截面 | {section_list_text()} |")
    w(f"| 支座 | {support_label()} {support_kind()}, CONSTRAINT={SUPPORT_CONSTRAINT} "
      f"({'/'.join(dof_split()[0])} 固定 / {'/'.join(dof_split()[1])} 自由) |")
    w(f"| 结构类型 / 单位 | STYP={STYP} ({struct_type_text()}), "
      f"FORCE={disp_table.get('FORCE')}, DIST={disp_table.get('DIST')} |")
    w()
    w("## 2. 荷载")
    w()
    w("| 工况 | 荷载 |")
    w("| --- | --- |")
    w(f"| DEAD | 自重 (DB:BODF FV=[0,0,-1], 系数 1.0) + "
      f"{abs(ROOF_DEAD_Q):.2f} kN/m 屋面恒载 (E2/E3, 全局 -Z) |")
    w(f"| LIVE | {abs(ROOF_LIVE_Q):.2f} kN/m 屋面活载 (E2/E3, 全局 -Z) |")
    w(f"| WIND_X_POS | +{WIND_Q:.1f} kN/m (E1/E4, 全局 +X) |")
    w(f"| WIND_X_NEG | -{WIND_Q:.1f} kN/m (E1/E4, 全局 -X) |")
    w()
    w("自重只施加一次: `STYP.bSELFWEIGHT=true` 是「自重→质量」转换(供特征值分析), "
      "静力自重仅来自单条 `DB:BODF` 记录; 交叉校验见附录 B。")
    w()
    w("## 3. 荷载组合")
    w()
    w("| 组合 | 说明 | 组合项 |")
    w("| --- | --- | --- |")
    for name, desc, terms in COMBOS:
        w(f"| {name} | {desc} | "
          + " + ".join(f"{factor}{case}" for case, factor in terms) + " |")


def report_analysis(w, steps, attempts, findings, solved):
    """Prompt section 19 item 4: the solve, its attempts, and the pre-checks."""
    w()
    w("## 4. 分析状态")
    w()
    w(f"**ANALYSIS = {'SUCCESS' if solved else 'FAILED'}**")
    w()
    w("确认方式: `/doc/ANAL` 的 HTTP 状态不作为成功依据 — 本版 MIDAS 也会以 HTTP 400 "
      "+ `[警告]` 返回却仍完成分析 — 因此以结果表 `REACTIONG` 有数据行作为分析完成的"
      f"证据。step 12 明细: {steps.get(12, {}).get('detail', '')}")
    w()
    w("| # | 动作 | 确认 | category | http | MIDAS 返回信息 |")
    w("| -: | --- | :-: | --- | -: | --- |")
    for entry in attempts:
        w(f"| {entry['attempt']} | {entry['action']} | "
          f"{'是' if entry['confirmed'] else '否'} | {entry['category']} | "
          f"{entry['http_status']} | {entry['message'] or '—'} |")
    w()
    w("### 分析前模型检查 (提示词 十三 1-6)")
    w()
    w("| 检查 | 结果 | 证据 |")
    w("| --- | :-: | --- |")
    for name, good, detail in findings:
        w(f"| {name} | {'PASS' if good else 'FAIL'} | {detail} |")

def report_results(w, data, peaks, modal_parsed, sub_names, balance, occupied,
                   previous, passed):
    """Prompt section 19 items 5-8 plus the parsing and balance appendices."""
    disp_table = data["tables"]["DISPLACEMENTG"]
    mm = dist_to_mm(disp_table)

    def extreme(key, unit, digits=3):
        hit = peaks.get(key)
        if not hit:
            return f"| {key} | — | — | — {unit} |"
        item, load, value = hit
        return f"| {key} | {item} | {load} | {value:.{digits}f} {unit} |"

    def force_at(elem, load, key):
        best = None
        for row in data["forces"].get((elem, load)) or []:
            value = row.get(key)
            if value is not None and (best is None or abs(value) > abs(best)):
                best = value
        return best

    w()
    w("## 5. 最大位移")
    w()
    w("| 类型 | 节点 | 组合 | 数值 |")
    w("| --- | -: | -- | ---: |")
    w(extreme("最大节点 UX", "mm"))
    w(extreme("最大节点 UZ", "mm"))
    w(extreme("最大绝对节点位移", "mm"))
    w()
    w("### 全部节点位移 (5 节点 × 4 组合; 平动 mm, 转动 rad)")
    w()
    w("| 节点 | 组合 | UX | UY | UZ | RX | RY | RZ |")
    w("| -: | -- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for nid, _, _, _ in NODES:
        for combo in COMBO_NAMES:
            rec = data["disp"].get((nid, combo)) or {}
            cells = []
            for key, _col in DISP_COLS:
                value = rec.get(key)
                if value is None:
                    cells.append("—")
                elif key in ("UX", "UY", "UZ"):
                    cells.append(fmt(None if mm is None else value * mm, 4))
                else:
                    cells.append(f"{value:.3e}")
            w(f"| N{nid} | {combo} | " + " | ".join(cells) + " |")

    w()
    w("## 6. 最大构件内力")
    w()
    w("| 类型 | 单元 | 组合 | 数值 |")
    w("| --- | -: | -- | ---: |")
    w(extreme("最大轴力 N", "kN"))
    w(extreme("最大剪力 V", "kN"))
    w(extreme("最大弯矩 M", "kN·m"))
    w()
    w("### 各单元内力极值 (沿单元取绝对值最大处)")
    w()
    w("| 单元 | 轴力 N (kN) | 剪力 V (kN) | 弯矩 M (kN·m) | 弯矩控制组合 |")
    w("| -: | ---: | ---: | ---: | -- |")
    for eid, _, _, _ in ELEMS:
        n = peak([(f"E{eid}", load, force_at(eid, load, "N"))
                  for load in COMBO_NAMES])
        v = peak([(f"E{eid}", load, force_at(eid, load, key))
                  for load in COMBO_NAMES for key in ("V2", "V3")])
        m = peak([(f"E{eid}", load, force_at(eid, load, key))
                  for load in COMBO_NAMES for key in ("M2", "M3")])
        #: The governing combination must be picked with the *same* components
        #: the value column uses.  Labelling it from M3 alone was wrong in this
        #: X-Z plane frame: in-plane bending is Moment-y (M2), Moment-z (M3) is
        #: identically zero, so peak() fell through to the first combination and
        #: every element was reported as COMB1.
        gov = peak([(f"E{eid}", load, force_at(eid, load, key))
                    for load in COMBO_NAMES for key in ("M2", "M3")])
        w(f"| E{eid} | {fmt(n[2]) if n else '—'} | {fmt(v[2]) if v else '—'} | "
          f"{fmt(m[2]) if m else '—'} | {gov[1] if gov else '—'} |")
    w()
    w("映射: 提示词的 N→`Axial`, V2→`Shear-y`, V3→`Shear-z`, M2→`Moment-y`, "
      "M3→`Moment-z`, T→`Torsion`; 列名取自 `BEAMFORCE` 响应自身的 `HEAD`, 不按位置猜。")

    w()
    w("## 7. 最大支座反力")
    w()
    w("| 支座 | 组合 | FX (kN) | FZ (kN) | MX (kN·m) | MY (kN·m) | MZ (kN·m) |")
    w("| -: | -- | ---: | ---: | ---: | ---: | ---: |")
    for nid in SUPPORTS:
        for combo in COMBO_NAMES:
            rec = data["react"].get((nid, combo)) or {}
            w(f"| N{nid} | {combo} | {fmt(rec.get('FX'))} | {fmt(rec.get('FZ'))} | "
              f"{fmt(rec.get('MX'))} | {fmt(rec.get('MY'))} | {fmt(rec.get('MZ'))} |")
    w()
    w("| 极值 | 支座 | 组合 | 数值 |")
    w("| --- | -: | -- | ---: |")
    w(extreme("最大支座水平反力", "kN"))
    w(extreme("最大支座竖向反力", "kN"))

    w()
    w("## 8. MCP 测试状态")
    w()
    for name, good, detail in passed:
        w(f"* [{'PASS' if good else 'FAIL'}] {name}"
          + (f" — {detail}" if detail else ""))
    w()
    w(f"合计: {sum(1 for _, good, _ in passed if good)}/{len(passed)} PASS")
    extra = balance_verdict(balance)
    w()
    w("附加自洽校验 (不属提示词 13 项, 但同样决定退出码):")
    w()
    for name, good, detail in extra:
        w(f"* [{'PASS' if good else 'FAIL'}] {name}"
          + (f" — {detail}" if detail else ""))
    w()
    w(f"附加校验合计: {sum(1 for _, good, _ in extra if good)}/{len(extra)} PASS")

    w()
    w("## 附录 A: SUB_TABLES / modal_result 解析 (提示词 十八)")
    w()
    static_subs = []
    for reply in data["replies"].values():
        static_subs.extend((reply.get("result_summary") or {}).get("sub_tables")
                           or [])
    w(f"- 静态结果响应的 `result_summary.sub_tables`: "
      f"{sorted(set(static_subs)) or '无'}")
    w(f"- `EIGENVALUEMODE` 响应的 `SUB_TABLES`: {sub_names or '无'}")
    if modal_parsed:
        w(f"- `result_summary.modal_result`: source={modal_parsed.get('source')}, "
          f"mode_count={modal_parsed.get('mode_count')}, "
          f"tables={modal_parsed.get('tables')}")
        w(f"- 累计参与质量(%): {modal_parsed.get('cumulative_ratio_percent')}")
        w()
        w("| 阶 | 频率 (Hz) | 周期 (s) | 频率 (rad/s) | 参与质量比 |")
        w("| -: | ---: | ---: | ---: | --- |")
        for mode in (modal_parsed.get("modes") or []):
            ratio = mode.get("participation_ratio") or {}
            w(f"| {mode.get('mode')} | {fmt(mode.get('frequency_hz'), 4)} | "
              f"{fmt(mode.get('period_s'), 4)} | "
              f"{fmt(mode.get('frequency_rad_s'), 3)} | {ratio or '—'} |")
    else:
        w("- `modal_result` = None: 该响应不含模态子表 (未解析到频率/周期/参与质量)")

    w()
    w("## 附录 B: 荷载平衡交叉校验 (独立于结果解析器)")
    w()
    w("| 工况 | ΣFX 反力 | 施加 FX | 残差 | ΣFZ 反力 | 施加 FZ | 残差 | "
      "ΣMY(反力力偶) | 施加 MY | 残差 |")
    w("| -- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for entry in balance:
        if entry["case"] == "DEAD":
            continue
        w(f"| {entry['case']} | {fmt(entry['sum_FX'])} | {fmt(entry['applied_FX'])} | "
          f"{fmt(entry['residual_FX'], 4)} | {fmt(entry['sum_FZ'])} | "
          f"{fmt(entry['applied_FZ'])} | {fmt(entry['residual_FZ'], 4)} | "
          f"{fmt(entry['sum_MY'])} | {fmt(entry['applied_MY'])} | "
          f"{fmt(entry['residual_MY'], 4)} |")
    w()
    if support_kind() == "铰支":
        w("说明: 柱脚铰支, 支座反力的弯矩分量 (MX/MY/MZ) 被释放, 恒为 0, 因此 ΣMY 取"
          "反力对原点的力矩 Σ(z·FX − x·FZ); 施加 MY 为外荷载对原点的力矩, 二者相加应为 0。")
    else:
        w(f"说明: 支座为{support_kind()} (CONSTRAINT={SUPPORT_CONSTRAINT}), 支座会传递弯矩, "
          "而本核算的 ΣMY 只取反力对原点的力矩 Σ(z·FX − x·FZ) — 它假定支座弯矩已被释放, "
          "因此该行残差在这个约束下必然不为 0, 这是约束与本核算不匹配, 不是模型错了。")
    dead = next((entry for entry in balance if entry["case"] == "DEAD"), {})
    w()
    w("DEAD 工况自重核算 (自重只应出现一次):")
    w()
    w(f"- ΣFZ 反力 = {fmt(dead.get('sum_FZ'))} kN")
    w(f"- 屋面恒载合计 = {fmt(dead.get('roof_dead_FZ'))} kN")
    w(f"- 反推结构自重 (向下) = -(ΣFZ 反力 + 屋面恒载) = "
      f"{fmt(dead.get('implied_self_weight'))} kN "
      f"(量值 {fmt(None if dead.get('implied_self_weight') is None else abs(dead['implied_self_weight']))} kN)")
    w(f"- `ELEMENTWEIGHT` 单元自重合计 = {fmt(dead.get('elementweight_total'))} kN "
      f"(响应声明单位 {dead.get('elementweight_unit') or '—'}"
      + (f", {dead['elementweight_error']}" if dead.get("elementweight_error") else "")
      + ")")
    self_residual = dead.get("selfweight_residual")
    w(f"- 自重残差 = {fmt(self_residual, 6)} kN "
      + ("→ 自重恰好施加一次, 未重复"
         if self_residual is not None and abs(self_residual) < 1e-3
         else "→ 与 ELEMENTWEIGHT 不一致, 需复核"))
    w(f"- 逐单元自重 = {dead.get('per_element')}")

    w()
    w("## 附录 C: 数据来源与运行上下文")
    w()
    w(f"- 建模前文档状态: {'空 (干净)' if not occupied else occupied}")
    w(f"- 上一次运行: {previous or '无 state.json'}")
    w("- 每次 MCP 调用: `mcp_audit.jsonl`; 每次 HTTP 调用(含请求体与原始响应): "
      "`http_audit.jsonl`")
    w("- 每个数字的原始响应: `res_*.json` / `readback_*.json`")
    w("- 本报告所有数值均直接读出上述响应, 未使用任何理论公式或模拟数据。")


def report(data, peaks, balance, modal_parsed, sub_names, attempts, findings,
           occupied, previous):
    """Assemble the prompt's section 19 summary from read-back values only."""
    steps = steps_by_number()
    passed = criteria(steps, data, peaks, modal_parsed, sub_names)
    disp_table = data["tables"]["DISPLACEMENTG"]
    mm = dist_to_mm(disp_table)
    lines: list[str] = []

    def w(text=""):
        lines.append(text)
    report_head(w, disp_table, mm)
    report_analysis(w, steps, attempts, findings, bool(steps.get(12, {}).get("ok")))
    report_results(w, data, peaks, modal_parsed, sub_names, balance, occupied,
                   previous, passed)
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# the run: prompt steps 1-18, end to end
# ---------------------------------------------------------------------------
#: Deletion order for ``--clear``: dependants before the records they point at,
#: because MIDAS answers a request that references a missing id with a crash
#: rather than an error (knowledge.PITFALLS).
CLEAR_ORDER = ("BMLD", "CNLD", "BODF", "CONS", "LCOM-GEN", "ELEM", "NODE",
               "SECT", "MATL", "STLD", "GRUP", "EIGV")


def clear_document(s, names):
    """Delete the collections this driver writes, so a re-run starts clean.

    Only reached under ``--clear``.  The deletes carry explicit ``target_ids``:
    the connector refuses a bare delete-all unless bulk delete is enabled, and
    a test driver has no business asking for that.

    Returns ``(attempted, leftover)``.  The connector verifies every delete by
    reading the id straight back, and MIDAS can answer 200 to a DELETE that it
    only applies a moment later - a per-id "still present" is therefore not
    proof that the record survived.  What decides is the read-back here, once
    every collection has been asked to empty: the caller's preflight then runs
    on exactly that state, and refuses the build if anything is left.
    """
    attempted = {}
    for name in names:
        ids = sorted(s.records(name))
        if not ids:
            continue
        s.call("midas_db_delete", {"endpoint": "DB:" + name, "target_ids": ids},
               required=False, announce=False)
        attempted[name] = ids
    return attempted, {name: ids for name in names
                       if (ids := sorted(s.records(name)))}


def run(clear=False, quiet=False):
    """The whole eighteen-step run, from the preflight to the summary.

    ``quiet`` suppresses the printed report; the caller then reads it from
    :func:`verdict`.  ``STEPS`` is process-global, so it is cleared here: a
    second run inside one process - an MCP tool call after a CLI run - would
    otherwise accumulate the first run's steps and report them as its own.
    """
    STEPS.clear()
    OUT.mkdir(parents=True, exist_ok=True)
    previous = None
    if STATE.exists():
        try:
            prior = load_state()
            previous = {key: prior.get(key)
                        for key in ("timestamp", "analysis", "passed", "failed")}
        except (OSError, ValueError) as exc:
            previous = {"timestamp": None,
                        "analysis": f"state.json unreadable: {exc}"}
    #: The verdict has to belong to *this* run.  A stale state.json surviving a
    #: failed run is read back by verdict() and quoted as the outcome, so it is
    #: dropped here - after the previous run's summary has been captured above.
    #: report.md goes with it: the refusal below returns before a report is
    #: rendered, so a leftover file would be handed back as this run's answer.
    for stale in (STATE, OUT / "report.md"):
        try:
            stale.unlink()
        except OSError:
            pass

    s = Session("live")
    try:
        if clear:
            attempted, leftover = clear_document(s, CLEAR_ORDER)
            print("clear: 已请求删除", attempted or "(没有需要删除的记录)",
                  flush=True)
            if leftover:
                # Not a warning: the preflight below will refuse the build on
                # this, so say plainly which collection MIDAS would not release.
                print("clear: 清空后仍然残留", leftover,
                      "— MIDAS 未接受这些删除, 需要手工清理", flush=True)
        occupied = preflight(s)
        if occupied:
            step(1, "创建/初始化模型", False,
                 f"MIDAS 文档非空, 拒绝在已有模型上建模: {occupied}")
            print("preflight 失败: 活文档非空, 报告会混合两个模型。请清空后重跑, "
                  "或加 --clear 让本脚本先删除它自己使用的集合。", flush=True)
            #: Record the refusal.  Returning without touching state.json would
            #: leave the *previous* run's verdict on disk, and --json would then
            #: hand the caller a PASS for a model that was never built.
            save("state.json", {
                "timestamp": now(), "base_url": os.environ.get("MIDAS_BASE_URL"),
                "analysis": "REFUSED", "note": f"活文档非空: {occupied}",
                "passed": [], "failed": ["preflight"],
                "steps": STEPS, "criteria": [], "verifications": []})
            return 3
        build(s)
        loads(s)
        findings = checks(s)
        eigen(s)
        outcome, attempts = solve(s)
        data = collect(s)
        peaks, balance = extremes(s, data)
        modal_parsed, _table, _rows, sub_names = modal(s)
        text = report(data, peaks, balance, modal_parsed, sub_names, attempts,
                      findings, occupied, previous)
        step(18, "最终输出结构计算摘要", bool(text.strip()),
             f"报告 {len(text.splitlines())} 行, 已写入 report.md")
    finally:
        s.close()

    (OUT / "report.md").write_text(text + "\n", encoding="utf-8")
    passed = criteria(steps_by_number(), data, peaks, modal_parsed, sub_names)
    verifications = balance_verdict(balance)
    save("state.json", {
        "timestamp": now(), "base_url": os.environ.get("MIDAS_BASE_URL"),
        "analysis": "SUCCESS" if outcome["confirmed"] else "FAILED",
        "passed": [name for name, good, _ in passed if good],
        "failed": [name for name, good, _ in passed if not good],
        "steps": STEPS,
        "criteria": [{"name": n, "ok": g, "detail": d} for n, g, d in passed],
        "verifications": [{"name": n, "ok": g, "detail": d}
                          for n, g, d in verifications]})
    if not quiet:
        print("\n" + text, flush=True)
        print(f"\n报告已写入 {OUT / 'report.md'}", flush=True)
    #: The balance residuals are a self-consistency check, not one of the
    #: prompt's thirteen rows, but a broken balance must still fail the run.
    return 0 if (all(good for _, good, _ in passed)
                 and all(good for _, good, _ in verifications)) else 1


# ---------------------------------------------------------------------------
# spec: the same run, parameterised
# ---------------------------------------------------------------------------
#: The frame this driver was built and validated against.  A caller's spec is
#: merged over this, so a spec only names what it changes.
SPEC_DEFAULT: dict = {
    "span": SPAN,
    "eave": EAVE,
    "ridge": RIDGE,
    "styp": STYP,
    "material": {"name": MATL_NAME, "elast": MATL_ELAST,
                 "poise": MATL_POISN, "density": MATL_DEN},
    "sections": {key: {"id": val["id"], "name": val["name"],
                       "vsize": list(val["vSIZE"])}
                 for key, val in SECTIONS.items()},
    "supports": {"nodes": list(SUPPORTS), "constraint": SUPPORT_CONSTRAINT},
    "cases": [list(c) for c in CASES],
    "beam_loads": [list(b) for b in BEAM_LOADS],
    "combos": [list(c) for c in COMBOS],
    "modes": MODES,
}

_SPEC_KEYS = frozenset(SPEC_DEFAULT)
_SPEC_META = ("out_dir", "_comment")


def _merge(spec: dict) -> dict:
    """Merge ``spec`` over :data:`SPEC_DEFAULT`, rejecting unknown keys.

    A silently ignored key is worse than a refusal: a typo in ``beam_load``
    would analyse a model the caller did not describe and still report PASS.
    """
    unknown = sorted(set(spec) - _SPEC_KEYS - set(_SPEC_META))
    if unknown:
        raise ValueError(
            f"unknown spec key(s): {', '.join(unknown)}; known keys are "
            f"{', '.join(sorted(_SPEC_KEYS | set(_SPEC_META)))}")
    merged = dict(SPEC_DEFAULT)
    merged.update(spec)
    return merged


def load_spec(path) -> dict:
    """Read a spec JSON file, or ``{}`` when ``path`` is None."""
    if path is None:
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def configure(spec: dict | None = None) -> dict:
    """Install a model spec into this module's model definition.

    The pipeline reads the model from module globals, which is what makes it
    readable end to end; a spec therefore installs itself instead of being
    threaded through every function.  One spec per process - a run is a process.
    Returns the merged spec.
    """
    global SPAN, EAVE, RIDGE, SLOPE, NODES, ELEMS, SECTIONS
    global MATL_NAME, MATL_ELAST, MATL_POISN, MATL_DEN, MATL_MASS
    global CASES, SUPPORT_CONSTRAINT, SUPPORTS, STYP, MODES
    global ROOF_DEAD_Q, ROOF_LIVE_Q, WIND_Q, BEAM_LOADS
    global COMBOS, COMBO_NAMES, NODE_XYZ, ELEM_LEN, OUT, STATE

    merged = _merge(spec or {})

    SPAN = float(merged["span"])
    EAVE = float(merged["eave"])
    RIDGE = float(merged["ridge"])
    SLOPE = (RIDGE - EAVE) / (SPAN / 2.0)
    STYP = int(merged["styp"])
    MODES = int(merged["modes"])

    mat = merged["material"]
    MATL_NAME = str(mat["name"])
    MATL_ELAST = float(mat["elast"])
    MATL_POISN = float(mat["poise"])
    MATL_DEN = float(mat["density"])
    MATL_MASS = MATL_DEN / GRAV

    SECTIONS = {key: {"id": int(val["id"]), "name": str(val["name"]),
                      "vSIZE": [float(x) for x in val["vsize"]]}
                for key, val in merged["sections"].items()}

    #: A single-bay pitched portal frame: two pinned-base columns, two rafters
    #: meeting at the ridge.  Y stays 0 - the frame lies in the X-Z plane.
    NODES = ((1, 0.0, 0.0, 0.0),
             (2, 0.0, 0.0, EAVE),
             (3, SPAN / 2.0, 0.0, RIDGE),
             (4, SPAN, 0.0, EAVE),
             (5, SPAN, 0.0, 0.0))
    ELEMS = ((1, 1, 2, "COLUMN"),
             (2, 2, 3, "BEAM"),
             (3, 3, 4, "BEAM"),
             (4, 4, 5, "COLUMN"))
    NODE_XYZ = {nid: (x, y, z) for nid, x, y, z in NODES}
    ELEM_LEN = {eid: math.dist(NODE_XYZ[i], NODE_XYZ[j])
                for eid, i, j, _ in ELEMS}

    CASES = tuple(tuple(c) for c in merged["cases"])
    SUPPORTS = tuple(int(n) for n in merged["supports"]["nodes"])
    SUPPORT_CONSTRAINT = str(merged["supports"]["constraint"])
    BEAM_LOADS = tuple(tuple(b) for b in merged["beam_loads"])
    COMBOS = tuple((str(c[0]), str(c[1]),
                    tuple((str(t[0]), float(t[1])) for t in c[2]))
                   for c in merged["combos"])
    COMBO_NAMES = tuple(c[0] for c in COMBOS)

    #: The legacy per-load scalars are *derived* from the load list, so reset
    #: them first: a spec that drops a load must not leave the previous run's
    #: value behind and quote it in the report.
    ROOF_DEAD_Q = ROOF_LIVE_Q = WIND_Q = 0.0
    for _elem, _case, _dir, _q in BEAM_LOADS:
        if _dir == "GZ" and _case == "DEAD":
            ROOF_DEAD_Q = float(_q)
        elif _dir == "GZ" and _case == "LIVE":
            ROOF_LIVE_Q = float(_q)
    _gx = [abs(float(q)) for _e, _c, d, q in BEAM_LOADS if d == "GX"]
    if _gx:
        WIND_Q = max(_gx)

    if merged.get("out_dir"):
        OUT = Path(merged["out_dir"]).resolve()
        STATE = OUT / "state.json"
    return merged


def verdict() -> dict:
    """The machine-readable outcome of the last :func:`run`.

    Read back from ``state.json``, which :func:`run` already writes, so a tool
    caller does not have to parse the printed report.  ``ok`` is deliberately
    hard to earn: an analysis that did not succeed, a criterion that failed, or
    self-consistency checks that never ran all count as not-ok.  The empty list
    is the trap - ``all([])`` is true, so a run that died before the checks
    existed would otherwise be indistinguishable from a clean one.
    """
    if not STATE.exists():
        return {"ok": False, "analysis": "NOT_RUN", "note": None, "report": "",
                "criteria": [], "verifications": [], "steps": [],
                "passed": [], "failed": []}
    state = load_state()
    #: The report is only this run's if this run got as far as rendering one, and
    #: only the success/failure paths do that - the refusal returns before it.
    #: run() also deletes a stale report.md up front; this is the second lock on
    #: the same door, because handing a refused run the previous run's report is
    #: exactly the lie this verdict exists to prevent.
    report = ""
    if state.get("analysis") in ("SUCCESS", "FAILED"):
        report_path = STATE.parent / "report.md"
        if report_path.exists():
            report = report_path.read_text(encoding="utf-8")
    criteria = state.get("criteria") or []
    verifications = state.get("verifications") or []
    ok = (state.get("analysis") == "SUCCESS"
          and bool(criteria)
          and not state.get("failed")
          and bool(verifications)
          and all(v.get("ok") for v in verifications))
    return {
        "ok": ok,
        "analysis": state.get("analysis"),
        "note": state.get("note"),
        "report": report,
        "criteria": criteria,
        "verifications": verifications,
        "steps": state.get("steps") or [],
        "passed": state.get("passed") or [],
        "failed": state.get("failed") or [],
    }


def main():
    ap = argparse.ArgumentParser(
        description="Portal-frame one-shot: model -> analyse -> verify -> report.")
    ap.add_argument("--spec", default=None,
                    help="JSON spec of the model to run; omitted = the validated "
                         "default frame (see specs/portal-frame.json)")
    ap.add_argument("--out-dir", default=None,
                    help="where report.md / state.json / the audit trail go")
    ap.add_argument("--json", action="store_true",
                    help="print only the machine-readable verdict (the report is "
                         "inside it) so a caller does not parse the printed text")
    ap.add_argument("--server", action="store_true",
                    help="run as the stdio MCP server instead of driving it")
    ap.add_argument("--config", default=None,
                    help="JSON config file to read the credentials from")
    ap.add_argument("--profile", default=None,
                    help="profile inside the config file, e.g. 'MIDAS GEN NX'")
    ap.add_argument("--clear", action="store_true",
                    help="delete this driver's own DB collections before building")
    args = ap.parse_args()
    if args.server:
        # serve() calls load_config(None), which ignores --config/--profile, so
        # without this a standalone `--server --profile X` run would silently
        # use the auto-discovered config.json.  ensure_credentials exports the
        # resolved values into os.environ, which wins over the file.
        try:
            ensure_credentials(profile=args.profile, config=args.config)
        except MissingCredentials as exc:
            print(str(exc), file=sys.stderr)
            return 2
        return serve()
    #: The spec is resolved before the credential: a typo in a spec key must not
    #: cost a live connection, and must never be discovered halfway through a
    #: build that has already written to the MIDAS document.
    try:
        spec = load_spec(args.spec)
    except (OSError, ValueError) as exc:
        print(f"spec 不可用: {exc}", file=sys.stderr)
        return 2
    if args.out_dir:
        spec["out_dir"] = args.out_dir
    try:
        configure(spec)
    except (KeyError, TypeError, ValueError) as exc:
        print(f"spec 无效: {exc}", file=sys.stderr)
        return 2
    try:
        base_url, _ = ensure_credentials(profile=args.profile, config=args.config)
    except MissingCredentials as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not args.json:
        print(f"Live target: {base_url}", flush=True)
        print(f"输出目录: {OUT}", flush=True)
    code = run(clear=args.clear, quiet=args.json)
    if args.json:
        outcome = verdict()
        outcome["exit_code"] = code
        print(json.dumps(outcome, ensure_ascii=False, allow_nan=False), flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
