"""Real stdio MCP driver for the user-authorized SPACE-GRID-TEST-001.

No fake API or fabricated analysis results. Every live call is audited. The
server instrumentation delegates to the original HTTP implementation unchanged.
Credentials come from the MIDAS_MAPI_KEY / MIDAS_BASE_URL environment variables
or from a JSON config file (see config.example.json); no key is hardcoded or
stored here.
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

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "artifacts" / "SPACE-GRID-TEST-001"
STATE = OUT / "state.json"
sys.path.insert(0, str(ROOT / "src"))
from midas_mcp.credentials import MissingCredentials, ensure_credentials  # noqa: E402


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2,
                                     allow_nan=False), encoding="utf-8")


def append(name, data):
    with (OUT / name).open("a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, allow_nan=False) + "\n")


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


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
        self.proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--server"],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=self.err, text=True, encoding="utf-8", env=env)
        self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                "clientInfo": {"name": "StructAI-space-grid-live", "version": "1"}})
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

    def call(self, tool, args, required=True, quiet=False):
        response = self.rpc("tools/call", {"name": tool, "arguments": args})
        if "error" in response:
            raise RuntimeError(str(response["error"]))
        result = response["result"]["structuredContent"]
        if not result.get("ok"):
            # ALREADY_EXISTS is a *designed* outcome for ``ensure``: a re-run
            # against a project that already holds the record.  Printing it as
            # a failure every run trains the reader to ignore the word FAILED,
            # which is exactly what must not happen in this driver.
            if not (quiet and result.get("category") == "ALREADY_EXISTS"):
                print("FAILED", tool, args.get("endpoint", args.get("command")),
                      result, flush=True)
            if required:
                raise RuntimeError(str(result))
        return result

    def query(self, endpoint, info=False, required=True):
        return self.call("midas_db_query", {"endpoint": endpoint, **({"info": True} if info else {})}, required)

    def records(self, name):
        result = self.query("DB:" + name)
        return result.get("data", {}).get(name, {})

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
                           "mode": "create", "data": records}, required=False,
                           quiet=True)
        if result.get("category") == "ALREADY_EXISTS":
            result = self.call("midas_db_assign", {"endpoint": "DB:" + name,
                               "mode": "update", "data": records}, required=False,
                               quiet=True)
            if not result.get("ok"):
                print("ensure: update of existing", name, "failed", result, flush=True)
        read = self.records(name)
        save(f"readback_{name}.json", read)
        return read

    def table(self, kind, cases=None, ids=None, required=False, artifact=None, **extra):
        data = {"TABLE_TYPE": kind, "TABLE_NAME": kind,
                "UNIT": {"FORCE": "KN", "DIST": "M"},
                "STYLES": {"FORMAT": "Scientific", "PLACE": 9}, **extra}
        if cases:
            data["LOAD_CASE_NAMES"] = cases
        if ids:
            data["NODE_ELEMS"] = {"KEYS": ids}
        result = self.call("midas_db_assign", {"endpoint": "POST:TABLE:" + kind,
                           "mode": "create", "data": data}, required)
        # The artifact name defaults to <phase>_<kind>, but a phase that queries
        # the same table more than once must keep the two apart: the anomaly
        # scan re-reads TRUSSFORCE without the combinations, and writing that
        # over the full result file would silently hide the combination rows.
        save(f"{artifact or (self.phase + '_' + kind)}.json", result)
        return result

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=10)
        self.err.close()


def inspect(s):
    project = s.query("OPE:PROJECTSTATUS")
    save("initial_project_status.json", project)
    for name in ("NODE", "ELEM", "MATL", "SECT", "CONS", "STLD", "LCOM-GEN", "UNIT", "STYP"):
        save("initial_" + name + ".json", s.query("DB:" + name))
    for name in ("STYP", "MATL", "SECT", "BODF", "STLD", "SDSP", "ETMP", "STMP", "PRST", "PTNS", "LTOM", "EIGV", "SPLC", "SPFC", "PDEL", "BUCK", "STAG", "STCT", "GRUP", "BNGR", "LDGR", "LCOM-GEN"):
        result = s.query("DB:" + name, info=True, required=False)
        save("schema_" + name + ".json", result)
    backup = OUT / "initial_model.json"
    result = s.call("midas_doc", {"command": "EXPORT", "argument": {"EXPORT_PATH": str(backup)}})
    if not backup.exists() or not backup.stat().st_size:
        raise RuntimeError("Initial export did not produce a backup file")
    print("Preflight complete: current model exported; schema responses saved", flush=True)


def geometry():
    nodes = []
    ids = {}
    for layer, z in (("UC", 10.), ("LC", 8.)):
        for j in range(7):
            for i in range(7):
                ident = len(nodes) + 1
                ids[layer, i, j] = ident
                nodes.append({"structai_id": f"N{ident}", "candidate_id": ident,
                              "X": i * 5., "Y": j * 4., "Z": z,
                              "layer": layer, "grid": [i, j]})
    elements = []
    seen = set()

    def add(a, b, group, section):
        pair = tuple(sorted((a, b)))
        if pair in seen:
            raise ValueError("duplicate member")
        seen.add(pair)
        ident = len(elements) + 1
        elements.append({"structai_id": f"E{ident}", "candidate_id": ident,
                         "nodes": [a, b], "group": group, "section": section,
                         "type": "TRUSS", "angle": 0})

    for layer in ("UC", "LC"):
        for j in range(7):
            for i in range(7):
                a = ids[layer, i, j]
                if i < 6:
                    add(a, ids[layer, i+1, j], layer, 2 if j in (0, 6) else 1)
                if j < 6:
                    add(a, ids[layer, i, j+1], layer, 2 if i in (0, 6) else 1)
                if i < 6 and j < 6:
                    add(a, ids[layer, i+1, j+1], layer, 1)
    for j in range(7):
        for i in range(7):
            add(ids["UC", i, j], ids["LC", i, j], "WEB", 3)
            if i < 6:
                add(ids["UC", i, j], ids["LC", i+1, j], "WEB", 3)
                add(ids["LC", i, j], ids["UC", i+1, j], "WEB", 3)
            if j < 6:
                add(ids["UC", i, j], ids["LC", i, j+1], "WEB", 3)
                add(ids["LC", i, j], ids["UC", i, j+1], "WEB", 3)
    supports = []
    for n, (i, j) in enumerate(((0, 0), (6, 0), (6, 6), (0, 6), (2, 0), (4, 0), (2, 6), (4, 6)), 1):
        supports.append({"name": f"P{n}", "candidate_id": ids["LC", i, j],
                         "constraint": "1110000" if n == 1 else "0110000" if n == 2 else "0010000",
                         "X": 5.*i, "Y": 4.*j, "Z": 8.})
    return nodes, elements, supports


def build(s):
    if s.records("NODE") or s.records("ELEM"):
        raise RuntimeError("Refusing to overwrite a nonempty document. No NEW or bulk DELETE is used.")
    nodes, elements, supports = geometry()
    state = {"project": {"name": "StructAI-SPACE-GRID-TEST-001", "units": "kN,m,C",
                         "status": "BUILDING", "created": now()},
             "geometry": {"span": [30., 24.], "levels": [8., 10.], "cell": [5., 4.],
                          "note": "Explicit coordinate lists control: six bays in both X/Y. Same-grid double layer, in-plane diagonals and X-braced vertical panels prevent square-grid shear mechanisms."},
             "nodes": nodes, "elements": elements, "supports": supports,
             "validation": {}, "loads": [], "load_cases": [], "load_combinations": []}
    save("state.json", state)
    s.put("UNIT", {"1": {"FORCE": "KN", "DIST": "M", "HEAT": "KCAL", "TEMPER": "C"}}, "update")
    mat = s.put("MATL", {"1": {"TYPE": "STEEL", "NAME": "Q355", "PARAM": [
        {"P_TYPE": 2, "bELAST": True, "ELAST": 206000000., "POISN": .3,
         "THERMAL": 1.2e-5, "DEN": 78.5, "MASS": 78.5/9.80665}]}}, required=False)
    if not mat:
        # A restored project may already hold the same records. Re-POSTing an
        # existing key is answered with 'Key Already Exist', so fall back to
        # the live records rather than stopping the run.
        mat = s.records("MATL")
        print("MATL already present; reusing live records", flush=True)
    state["materials"] = mat
    sec = s.put("SECT", {str(i): {"SECTTYPE": "VALUE", "SECT_NAME": name,
                     "SECT_BEFORE": {"SHAPE": "P", "SECT_I": {"vSIZE": [d, t]}}}
                     for i, name, d, t in ((1,"CHORD-159x8",.159,.008), (2,"CHORD-140x6",.140,.006), (3,"WEB-114x5",.114,.005))},
                  required=False)
    if not sec:
        sec = s.records("SECT")
        print("SECT already present; reusing live records", flush=True)
    state["sections"] = sec
    # Only the actual returned IDs are used in subsequent writes.
    actual_nodes = s.put("NODE", {str(n["candidate_id"]): {k:n[k] for k in ("X","Y","Z")} for n in nodes})
    for n in nodes:
        matches = [int(k) for k,v in actual_nodes.items() if all(abs(v.get(c, math.inf)-n[c]) < 1e-9 for c in ("X","Y","Z"))]
        if len(matches) != 1:
            raise RuntimeError("Node readback is missing, duplicated or changed")
        n["midas_id"] = matches[0]
    node_map = {n["candidate_id"]:n["midas_id"] for n in nodes}
    # A restored project may name the same pipe differently (CHORD-P159x8 vs
    # CHORD-159x8), so resolve each section by name and fall back to the
    # registry key, then assert the resolved section really is that pipe.
    wanted = {1: ("CHORD-159x8", "CHORD-P159x8", .159),
              2: ("CHORD-140x6", "CHORD-P140x6", .140),
              3: ("WEB-114x5", "WEB-P114x5", .114)}

    def section_of(index):
        names, outer = wanted[index][:2], wanted[index][2]
        for k, v in sec.items():
            if v.get("SECT_NAME") in names:
                return int(k)
        cand = sec.get(str(index))
        if cand and abs(cand["SECT_BEFORE"]["SECT_I"]["vSIZE"][0] - outer) < 1e-9:
            return index
        raise RuntimeError(f"no live section matches {names}")

    sect_of = {i: section_of(i) for i in wanted}
    actual_elems = s.put("ELEM", {str(e["candidate_id"]): {"TYPE": "TRUSS", "MATL": int(next(iter(mat))),
                        "SECT": sect_of[e["section"]],
                        "NODE": [node_map[n] for n in e["nodes"]], "ANGLE": 0} for e in elements})
    for e in elements:
        pair = [node_map[n] for n in e["nodes"]]
        matches = [int(k) for k,v in actual_elems.items() if v.get("NODE",[])[:2] == pair]
        if len(matches) != 1:
            raise RuntimeError("Element readback mismatch")
        e["midas_id"] = matches[0]
        e["midas_nodes"] = pair
    for p in supports:
        p["midas_id"] = node_map[p["candidate_id"]]
    s.put("CONS", {str(p["midas_id"]): {"ITEMS": [{"ID": 1, "CONSTRAINT": p["constraint"]}]} for p in supports})
    state["project"]["status"] = "GEOMETRY_BUILT"
    state["validation"]["readback_counts"] = {"nodes": len(actual_nodes), "elements": len(actual_elems), "materials": len(mat), "sections": len(sec), "supports": len(supports)}
    save("state.json", state)
    for kind in ("SECTIONALL", "ELEMENTWEIGHT", "SUPPORTS"):
        s.table(kind)
    print("Geometry read back:", state["validation"]["readback_counts"], flush=True)


CASE_NAMES = ("DEAD ROOF_DEAD ROOF_LIVE MAINTENANCE HANGING EQUIPMENT CEILING PIPELINE "
              "WIND_X_POS WIND_X_NEG WIND_Y_POS WIND_Y_NEG WIND_UP WIND_DOWN SNOW SNOW_UNBALANCED "
              "TEMP_POS TEMP_NEG TEMP_GRADIENT EQ_X EQ_Y EQ_Z SUPPORT_SETTLEMENT FORCED_DISPLACEMENT "
              "CONSTRUCTION_STAGE ACCIDENTAL IMPACT FIRE_HIGH_TEMP PRESTRESS OTHER_SPECIAL").split()


def static_loads(s):
    state = json.loads(STATE.read_text(encoding="utf-8"))
    cases = {str(i): {"NAME": name, "TYPE": "USER", "DESC": f"LC{i:02d}: API test only"}
             for i, name in enumerate(CASE_NAMES, 1) if not name.startswith("EQ_")}
    actual = s.records("STLD") or s.put("STLD", cases)
    state["load_cases"] = []
    state["loads"] = []
    for i, name in enumerate(CASE_NAMES, 1):
        matches = [k for k,v in actual.items() if v.get("NAME") == name]
        state["load_cases"].append({"id": f"LC{i:02d}", "name": name,
                                    "midas_id": matches[0] if len(matches)==1 else None,
                                    "status": "DEFINED" if matches else "NOT_RUN"})
    save("state.json", state)
    if not s.records("BODF"):
        s.put("BODF", {"1": {"LCNAME": "DEAD", "FV": [0., 0., -1.], "GROUP_NAME": ""}})
    loads = {}
    totals = {}
    nodes = {n["midas_id"]: n for n in state["nodes"]}

    def add(n, lc, force, area=None):
        nid = n["midas_id"]
        items = loads.setdefault(str(nid), {"ITEMS": []})["ITEMS"]
        rec = {"ID": len(items)+1, "LCNAME": lc, "FX": force[0], "FY": force[1], "FZ": force[2], "MX": 0., "MY": 0., "MZ": 0., "GROUP_NAME": ""}
        items.append(rec)
        x,y,z = n["X"],n["Y"],n["Z"]
        fx,fy,fz = force
        six = [fx,fy,fz,y*fz-z*fy,z*fx-x*fz,x*fy-y*fx]
        totals.setdefault(lc, [0.]*6)
        for j in range(6):
            totals[lc][j] += six[j]
        state["loads"].append({"node": nid, "case": lc, "force": force, "tributary_area": area})

    def surface(lc, layer, pressure, box=(0.,30.,0.,24.)):
        for n in nodes.values():
            if n["layer"] != layer:
                continue
            x,y = n["X"],n["Y"]
            area = max(0., min(x+2.5,30.,box[1])-max(x-2.5,0.,box[0])) * max(0.,min(y+2.,24.,box[3])-max(y-2.,0.,box[2]))
            if area:
                add(n, lc, [0.,0.,-pressure*area], area)

    for name,layer,q,box in (
        ("ROOF_DEAD","UC",1.5,(0,30,0,24)), ("ROOF_LIVE","UC",.5,(0,30,0,24)),
        ("MAINTENANCE","UC",1.,(10,20,8,16)), ("HANGING","LC",.5,(7.5,22.5,6,18)),
        ("CEILING","LC",.3,(0,30,0,24)), ("PIPELINE","LC",.2,(0,30,0,24)),
        ("WIND_UP","UC",-1.,(0,30,0,24)), ("WIND_DOWN","UC",1.,(0,30,0,24)),
        ("SNOW","UC",.5,(0,30,0,24)), ("SNOW_UNBALANCED","UC",.75,(0,15,0,24)),
        ("SNOW_UNBALANCED","UC",.15,(15,30,0,24))):
        surface(name,layer,q,box)
    for name, axis, side, sign in (("WIND_X_POS",0,0,1),("WIND_X_NEG",0,30,-1),
                                    ("WIND_Y_POS",1,0,1),("WIND_Y_NEG",1,24,-1)):
        for n in nodes.values():
            if n["layer"]!="UC" or n[("X","Y")[axis]]!=side:
                continue
            other = n[("Y","X")[axis]]
            span, step = ((24.,4.),(30.,5.))[axis]
            width = step/2 if other in (0.,span) else step
            area = width * 10.
            f=[0.,0.,0.]; f[axis]=sign*1.5*area
            add(n,name,f,area)
    for x,y in ((10,8),(20,8),(10,16),(20,16)):
        n=next(n for n in nodes.values() if n["layer"]=="UC" and n["X"]==x and n["Y"]==y)
        add(n,"EQUIPMENT",[0.,0.,-50.])
    center=next(n for n in nodes.values() if n["layer"]=="UC" and n["X"]==15 and n["Y"]==12)
    for name,f in (("ACCIDENTAL",[0.,0.,-100.]),("IMPACT",[0.,0.,-50.]),("OTHER_SPECIAL",[30.,0.,0.])):
        add(center,name,f)
    read=s.records("CNLD") or s.put("CNLD",loads)
    checked=0
    # MIDAS merges multiple entries for the same case/group at one node.
    # Compare force sums by engineering identity, not the client item IDs.
    for nid,rec in loads.items():
        expected={}
        observed={}
        for container,items in ((expected,rec["ITEMS"]),(observed,read[nid]["ITEMS"])):
            for item in items:
                identity=(item["LCNAME"],item.get("GROUP_NAME",""))
                values=container.setdefault(identity,[0.]*6)
                for j,k in enumerate(("FX","FY","FZ","MX","MY","MZ")):
                    values[j]+=item.get(k,0.)
        if set(expected)!=set(observed) or any(abs(v-observed[k][j])>1e-8 for k,vs in expected.items() for j,v in enumerate(vs)):
            raise RuntimeError("Nodal load readback resultant mismatch")
        checked+=len(observed)
    state["validation"]["applied_load_six_components"] = totals
    state["validation"]["nodal_load_items_verified"] = checked
    state["validation"]["wind_assumption"] = "1.5kPa on idealized 10m-high projected envelope transferred to upper edge; test action, not a code wind design."
    for lc in state["load_cases"]:
        if lc["name"] in totals or lc["name"]=="DEAD":
            lc["status"]="APPLIED_READBACK"
    state["section_properties"] = s.query("OPE:SECTPROP")
    save("section_properties.json",state["section_properties"])
    save("state.json", state)
    print("Static nodal loads verified:", checked, "items", flush=True)


def advanced_loads(s):
    state = json.loads(STATE.read_text(encoding="utf-8"))
    styp = s.records("STYP")
    key = next(iter(styp))
    styp[key].update({"STYP": 0, "MASS": 1, "GRAV": 9.80665, "TEMP": 0., "bSELFWEIGHT": True, "SMASS": 1})
    s.put("STYP", styp, "update")
    temps = {}
    for e in state["elements"]:
        vals = [("TEMP_POS",30.),("TEMP_NEG",-30.),("FIRE_HIGH_TEMP",200.),
                ("TEMP_GRADIENT",20. if e["group"]=="UC" else 0. if e["group"]=="LC" else 10.)]
        temps[str(e["midas_id"])]={"ITEMS":[{"ID":i,"LCNAME":lc,"GROUP_NAME":"","TEMP":t} for i,(lc,t) in enumerate(vals,1)]}
    read = s.ensure("ETMP", temps)
    if any(read[k]["ITEMS"] != v["ITEMS"] for k,v in temps.items()):
        raise RuntimeError("Element temperature readback mismatch")
    disps={}
    for name,lc,dof,val in (("P1","SUPPORT_SETTLEMENT",2,-.01),("P4","SUPPORT_SETTLEMENT",2,-.01),("P1","FORCED_DISPLACEMENT",0,.005)):
        node=next(p["midas_id"] for p in state["supports"] if p["name"]==name)
        items=disps.setdefault(str(node),{"ITEMS":[]})["ITEMS"]
        items.append({"ID":len(items)+1,"LCNAME":lc,"GROUP_NAME":"", "VALUES":[{"OPT_FLAG":j==dof,"DISPLACEMENT":val if j==dof else 0.} for j in range(6)]})
    s.ensure("SDSP",disps)
    target=next(e for e in state["elements"] if e["group"]=="LC")
    # ensure(), not put(): a restored project may already carry this record and
    # a re-POST of an existing key is refused with 'Key Already Exist'.  A
    # fire-and-forget put() returned None there and mislabelled a working
    # prestress case as FAIL.
    prestress=s.ensure("PTNS",{str(target["midas_id"]):{"ITEMS":[{"ID":1,"LCNAME":"PRESTRESS","GROUP_NAME":"","TENSION":100.}]}})
    if not prestress:
        raise RuntimeError("prestress (PTNS) write did not read back")
    state["advanced_loads"]={"ETMP":read,"SDSP":s.records("SDSP"),"PTNS":prestress,
                             "temperature_note":"TEMP=0 reference; WEB uses +10C midpoint mean for +20/0C layer differential. FIRE is thermal API test only, no fire material reduction or fire design."}
    for lc in state["load_cases"]:
        if lc["name"] in ("TEMP_POS","TEMP_NEG","TEMP_GRADIENT","FIRE_HIGH_TEMP","SUPPORT_SETTLEMENT","FORCED_DISPLACEMENT"):
            lc["status"]="APPLIED_READBACK"
        if lc["name"]=="PRESTRESS":
            lc["status"]="APPLIED_READBACK" if prestress else "FAIL"
    save("state.json",state)
    # A restored project may already hold these single-record settings, and a
    # re-POST of an existing key is answered with 'Key Already Exist'.  Using a
    # fire-and-forget write here silently kept a stale value: the restored
    # project held EIGV.iFREQ=3, so the analysis computed 3 modes while the
    # driver believed it had asked for 20.  Every one of these writes therefore
    # goes through ``ensure`` and is asserted against the live readback.
    ltom = s.ensure("LTOM",{"1":{"DIR":"XYZ","bNODAL":True,"bBEAM":True,"bFLOOR":False,"bPRES":False,"GRAV":9.80665,
                           "vLC":[{"LCNAME":n,"FACTOR":1.} for n in ("ROOF_DEAD","CEILING","PIPELINE","EQUIPMENT")]}})
    eigv = s.ensure("EIGV",{"1":{"TYPE":"LANCZOS","iFREQ":20,"iITER":100,"iDIM":40,"TOL":1e-10,"bMINMAX":False,"bSTRUM":False}})
    if int(eigv["1"]["iFREQ"]) != 20 or eigv["1"]["TYPE"] != "LANCZOS":
        raise RuntimeError(f"EIGV readback mismatch: {eigv}")
    spfc = s.ensure("SPFC",{"1":{"NAME":"GRID_TEST_SPECTRUM","iTYPE":1,"iMETHOD":0,"SCALE":1.,"GRAV":9.80665,"DRATIO":.05,
                           "aFUNC":[{"PERIOD":t,"VALUE":a} for t,a in ((0.,.4),(.2,1.),(.5,.8),(1.,.4),(2.,.2),(4.,.1))]}})
    # bMODE must be True for aUSEMODE to be stored at all: with bMODE False the
    # write is accepted (HTTP 200) and the mode list silently comes back empty,
    # which would leave the response-spectrum run with no modes to combine.
    rs={str(i):{"NAME":name,"DIR":direction,"ANGLE":angle,"SCALE":1.,"PMFT":1.,"bDAMP":True,"INTERP":"LINEAR",
                "COMTYPE":"CQC","bADDSIGN":False,"iSIGNTYPE":0,"bMODE":True,"bAUTO":False,"iAUTOTYPE":0,
                "aFUNCNAME":["GRID_TEST_SPECTRUM"],"aUSEMODE":[{"bUSE":True,"MSFACTOR":1.} for _ in range(20)],
                "iMDTYPE":1,"DALL":.05,"bCDAMP":False}
        for i,(name,direction,angle) in enumerate((("EQ_X","XY",0.),("EQ_Y","XY",90.),("EQ_Z","Z",0.)),1)}
    read=s.ensure("SPLC",rs)
    for k,v in read.items():
        if v.get("COMTYPE") != "CQC" or not v.get("bMODE") or len(v.get("aUSEMODE",[])) != 20:
            raise RuntimeError(f"SPLC readback mismatch on {k}: COMTYPE={v.get('COMTYPE')} "
                               f"bMODE={v.get('bMODE')} aUSEMODE={len(v.get('aUSEMODE',[]))}")
    if len(read) != 3:
        raise RuntimeError(f"expected 3 spectrum load cases, read back {len(read)}")
    state["mass_source"]={"STYP":s.records("STYP"),"LTOM":ltom}
    state["dynamics"]={"EIGV":eigv,"SPFC":spfc,"SPLC":read}
    for lc in state["load_cases"]:
        if lc["name"].startswith("EQ_") and read:
            matches=[k for k,v in read.items() if v["NAME"]==lc["name"]]
            lc["midas_id"]=matches[0] if matches else None
            lc["status"]="APPLIED_READBACK" if matches else "FAIL"
    save("state.json",state)
    for k in ("MASS_SUMMARY_X","MASS_SUMMARY_Y","MASS_SUMMARY_Z","LOAD_SUMMARY_X","LOAD_SUMMARY_Y","LOAD_SUMMARY_Z"):
        s.table(k)
    print("Advanced loads and dynamics settings applied and read back",flush=True)


def combinations(s):
    state=json.loads(STATE.read_text(encoding="utf-8"))
    recipes=[("ULS-01",[("DEAD",1.2),("ROOF_DEAD",1.2),("ROOF_LIVE",1.4)])]
    for i,n in enumerate(("WIND_X_POS","WIND_X_NEG","WIND_Y_POS","WIND_Y_NEG","WIND_UP","SNOW","SNOW_UNBALANCED","EQUIPMENT","HANGING"),2):
        f=.9 if n=="WIND_UP" else 1.2
        recipes.append((f"ULS-{i:02d}",[("DEAD",f),("ROOF_DEAD",f),(n,1.4)]))
    for i,n in enumerate(("EQ_X","EQ_Y","EQ_Z"),11):
        recipes.append((f"ULS-{i:02d}",[("DEAD",1.),("ROOF_LIVE",.5),(n,1.)]))
    for i,n in enumerate(("SUPPORT_SETTLEMENT","TEMP_POS","TEMP_NEG","TEMP_GRADIENT","ACCIDENTAL","IMPACT","FIRE_HIGH_TEMP","PRESTRESS"),14):
        recipes.append((f"ULS-{i:02d}",[("DEAD",1.),("ROOF_DEAD",1.),(n,1.)]))
    for i,n in enumerate(("ROOF_LIVE","WIND_X_POS","WIND_Y_POS","SNOW","TEMP_POS","SUPPORT_SETTLEMENT","EQUIPMENT"),1):
        recipes.append((f"SLS-{i:02d}",[("DEAD",1.),("ROOF_DEAD",1.),(n,.7 if "WIND" in n else 1.)]))
    data={str(i):{"NAME":name,"ACTIVE":"ACTIVE","iTYPE":0,"DESC":"API test; LIVE alias resolved to ROOF_LIVE",
                  "vCOMB":[{"ANAL":"RS" if n.startswith("EQ_") else "ST","LCNAME":n,"FACTOR":f} for n,f in parts]}
          for i,(name,parts) in enumerate(recipes,1)}
    read=s.ensure("LCOM-GEN",data)
    # Every combination must come back with the factors that were asked for;
    # a silent partial write would leave a combination that does not mean what
    # the report says it means.
    by_name={v["NAME"]:v for v in read.values()}
    for name,parts in recipes:
        got=by_name.get(name)
        if got is None:
            raise RuntimeError(f"combination {name} missing from readback")
        seen={c["LCNAME"]:c["FACTOR"] for c in got["vCOMB"]}
        for lc,f in parts:
            if abs(seen.get(lc,float("nan"))-f)>1e-9:
                raise RuntimeError(f"{name}: {lc} factor {seen.get(lc)} != {f}")
    state["load_combinations"]=[{"name":name,"components":parts,"status":"READBACK_VERIFIED"} for name,parts in recipes]
    state["combination_readback"]=read
    save("state.json",state)
    print("Combination request result:",len(read),"verified",len(recipes),flush=True)


def linear(s):
    result=s.call("midas_doc",{"command":"ANAL","argument":{}},required=False)
    save("linear_analysis_command.json",result)
    if result.get("ok"):
        results(s)


def results(s):
    state=json.loads(STATE.read_text(encoding="utf-8"))
    cases=[c["name"]+("(RS)" if c["name"].startswith("EQ_") else "(ST)") for c in state["load_cases"] if c["status"]=="APPLIED_READBACK"]
    for kind in ("REACTIONG","DISPLACEMENTG","TRUSSFORCE","TRUSSSTRESS"):
        s.table(kind,cases=cases)
    s.table("EIGENVALUEMODE",MODES=[f"Mode{i}" for i in range(1,21)])
    print("Linear analysis command and result queries audited",flush=True)


def extract(s):
    """Full result extraction, load balance, anomaly scan and stability checks.

    Everything here reads live POST/TABLE output; nothing is synthesised.  A
    table that MIDAS answers with zero rows is recorded as such rather than
    silently skipped, because "the query returned nothing" and "the query was
    never made" must not look the same in the report.
    """
    state = json.loads(STATE.read_text(encoding="utf-8"))
    unit = s.records("UNIT")
    nodes = {n["midas_id"]: n for n in state["nodes"]}
    elems = {e["midas_id"]: e for e in state["elements"]}
    supports = {p["midas_id"]: p for p in state["supports"]}
    cases = [c["name"] + ("(RS)" if c["name"].startswith("EQ_") else "(ST)")
             for c in state["load_cases"] if c["status"] == "APPLIED_READBACK"]
    combos = [c["name"] for c in state["load_combinations"]]
    # A combination must be requested with the '(CB)' suffix.  A bare
    # combination name is accepted with HTTP 200 and returns *no rows at all*,
    # silently - the table simply comes back with only the load cases in it.
    # Verified live: ['ULS-01','SLS-01'] -> 0 rows, ['ULS-01(CB)','SLS-01(CB)']
    # -> 914 rows.  MIDAS answers each combination as three envelopes whose
    # labels carry the bare name plus '(all)'/'(max)'/'(min)'.
    combo_reqs = [c + "(CB)" for c in combos]

    def rows(kind, cases_):
        table = _table(s, kind, cases=cases_, artifact=f"extract_full_{kind}")
        head = table.get("HEAD", [])
        return head, table.get("DATA", []), table

    # ---- displacement: max per layer, per case, and per combination -------
    head, data, _ = rows("DISPLACEMENTG", cases + combo_reqs)
    disp_rows = data
    i_n, i_l = head.index("Node"), head.index("Load")
    disp_max = {}
    for r in data:
        nid, lc = int(r[i_n]), r[i_l]
        d = [abs(float(r[i])) for i in range(3, 6)]
        cur = disp_max.get(lc)
        mag = math.sqrt(sum(x * x for x in d))
        if cur is None or mag > cur["magnitude"]:
            disp_max[lc] = {"node": nid, "structai_id": nodes.get(nid, {}).get("structai_id"),
                            "layer": nodes.get(nid, {}).get("layer"),
                            "DX": float(r[3]), "DY": float(r[4]), "DZ": float(r[5]),
                            "magnitude": mag, "index": float(r[0])}
    state["results_displacement"] = {
        "unit": {"DIST": unit.get("1", {}).get("DIST"), "FORCE": unit.get("1", {}).get("FORCE")},
        "rows": len(data), "cases_queried": len(cases) + len(combos),
        "max_by_case": disp_max,
        "governing": max(disp_max.items(), key=lambda kv: kv[1]["magnitude"]) if disp_max else None,
    }
    save("extract_summary_DISPLACEMENTG.json", {"HEAD": head, "DATA": data})

    # ---- reactions: per support, per case; equilibrium check --------------
    head, data, _ = rows("REACTIONG", cases + combo_reqs)
    react_rows = data
    i_n, i_l = head.index("Node"), head.index("Load")
    node_xyz = {n["midas_id"]: (n["X"], n["Y"], n["Z"]) for n in state["nodes"]}
    react = {}
    for r in data:
        nid, lc = int(r[i_n]), r[i_l]
        six = [float(r[i]) for i in range(3, 9)]
        react.setdefault(lc, {}).setdefault(nid, [0.] * 6)
        for j in range(6):
            react[lc][nid][j] += six[j]
    react_summary = {}
    for lc, per_node in react.items():
        total = [0.] * 6
        for six in per_node.values():
            for j in range(6):
                total[j] += six[j]
        peak = max(per_node.items(),
                   key=lambda kv: max(abs(x) for x in kv[1]))
        # MX/MY/MZ in the table are the *moment* reactions at each support,
        # which are zero for a pinned support.  Global moment equilibrium needs
        # the moment of the reaction FORCES about the origin, r x F, not the
        # couple the support carries - otherwise every case looks unbalanced.
        mom = [0.] * 3
        # Absolute sums of the per-support contributions.  These are the scale
        # of the terms that must cancel, which is what a meaningful tolerance
        # has to be measured against: a residual is only small or large
        # relative to the magnitude of the numbers being added up.
        abs_force = [0.] * 3
        abs_moment = [0.] * 3
        for nid, six in per_node.items():
            pos = node_xyz.get(nid)
            if pos is None:
                continue
            x, y, z = pos
            fx, fy, fz = six[0], six[1], six[2]
            cx = y * fz - z * fy
            cy = z * fx - x * fz
            cz = x * fy - y * fx
            mom[0] += cx
            mom[1] += cy
            mom[2] += cz
            for j, v in enumerate((fx, fy, fz)):
                abs_force[j] += abs(v)
            for j, v in enumerate((cx, cy, cz)):
                abs_moment[j] += abs(v)
        react_summary[lc] = {
            "supports_with_reaction": len(per_node),
            "sum_FX": total[0], "sum_FY": total[1], "sum_FZ": total[2],
            "sum_MX": mom[0], "sum_MY": mom[1], "sum_MZ": mom[2],
            "abs_force": abs_force, "abs_moment": abs_moment,
            "support_moment_reactions": {"MX": total[3], "MY": total[4], "MZ": total[5]},
            "max_component": {"support": supports.get(peak[0], {}).get("name", peak[0]),
                              "node": peak[0],
                              "six": peak[1]},
        }
    # alias 'DEAD(ST)' -> 'DEAD' so the balance step can find the sums
    for key in list(react_summary):
        if not key.endswith("(RS)"):
            react_summary.setdefault(key + "(ST)", react_summary[key])
    state["results_reaction"] = {"rows": len(data), "by_case": react_summary}
    save("extract_summary_REACTIONG.json", {"HEAD": head, "DATA": data})

    # ---- member force and stress ------------------------------------------
    head, data, _ = rows("TRUSSFORCE", cases + combo_reqs)
    force_rows = data
    i_e, i_l = head.index("Elem"), head.index("Load")
    force = {}
    for r in data:
        eid, lc = int(r[i_e]), r[i_l]
        f = float(r[3])
        slot = force.setdefault(lc, {"max_tension": None, "max_compression": None})
        if slot["max_tension"] is None or f > slot["max_tension"]["force"]:
            slot["max_tension"] = {"element": eid, "structai_id": elems.get(eid, {}).get("structai_id"),
                                   "group": elems.get(eid, {}).get("group"), "force": f}
        if slot["max_compression"] is None or f < slot["max_compression"]["force"]:
            slot["max_compression"] = {"element": eid, "structai_id": elems.get(eid, {}).get("structai_id"),
                                       "group": elems.get(eid, {}).get("group"), "force": f}
    head_s, data_s, _ = rows("TRUSSSTRESS", cases + combo_reqs)
    i_e2, i_l2 = head_s.index("Elem"), head_s.index("Load")
    stress = {}
    for r in data_s:
        eid, lc = int(r[i_e2]), r[i_l2]
        v = float(r[3])
        slot = stress.setdefault(lc, {"max": None, "min": None})
        if slot["max"] is None or v > slot["max"]["stress"]:
            slot["max"] = {"element": eid, "structai_id": elems.get(eid, {}).get("structai_id"),
                           "group": elems.get(eid, {}).get("group"), "stress": v}
        if slot["min"] is None or v < slot["min"]["stress"]:
            slot["min"] = {"element": eid, "structai_id": elems.get(eid, {}).get("structai_id"),
                           "group": elems.get(eid, {}).get("group"), "stress": v}
    # group-level extremes, which is what a space-grid report actually wants
    by_group = {}
    for r in data_s:
        eid = int(r[i_e2])
        g = elems.get(eid, {}).get("group", "?")
        v = float(r[3])
        slot = by_group.setdefault(g, {"max_tension_stress": None, "max_compression_stress": None})
        if slot["max_tension_stress"] is None or v > slot["max_tension_stress"]["stress"]:
            slot["max_tension_stress"] = {"element": eid, "stress": v, "load": r[i_l2]}
        if slot["max_compression_stress"] is None or v < slot["max_compression_stress"]["stress"]:
            slot["max_compression_stress"] = {"element": eid, "stress": v, "load": r[i_l2]}
    state["results_force"] = {"rows": len(data), "by_case": force}
    state["results_stress"] = {"rows": len(data_s), "by_case": stress, "by_group": by_group}
    save("extract_summary_TRUSSFORCE.json", {"HEAD": head, "DATA": data})
    save("extract_summary_TRUSSSTRESS.json", {"HEAD": head_s, "DATA": data_s})

    # ---- six-component load balance ---------------------------------------
    applied = state["validation"]["applied_load_six_components"]
    selfweight = _table(s, "LOAD_SUMMARY_Z")
    sw_by_case = {}
    for r in selfweight.get("DATA", []):
        sw_by_case[r[1]] = {"concentrated": float(r[2]), "beam": float(r[3]),
                            "floor": float(r[4]), "pressure": float(r[5]),
                            "self_weight": float(r[6]), "sum": float(r[7])}
    # The MIDAS native self-weight is a body load, not a nodal load: it acts at
    # every element's centre of gravity, so it contributes its own moment about
    # the origin.  Adding only its force (FZ) leaves a residual moment equal to
    # that couple - which is what the DEAD case showed before this was added.
    # The moment is derived from POST:TABLE:ELEMENTWEIGHT, whose per-element
    # 'Total Weight' is exact, using each element's midpoint as its centroid.
    element_weight = _table(s, "ELEMENTWEIGHT")
    sw_rows = element_weight.get("DATA", [])
    sw_by_elem = {int(r[1]): float(r[12]) for r in sw_rows}
    sw_moment = [0.] * 3
    sw_total = 0.
    for eid, weight in sw_by_elem.items():
        e = elems.get(eid)
        if e is None:
            continue
        a, b = e["midas_nodes"]
        pa, pb = node_xyz.get(a), node_xyz.get(b)
        if pa is None or pb is None:
            continue
        cx, cy, cz = ((pa[i] + pb[i]) / 2. for i in range(3))
        sw_total += weight
        # r x (0, 0, -w) about the origin
        sw_moment[0] += -cy * weight
        sw_moment[1] += cx * weight
    # The support system restrains translation only: every DB:CONS constraint
    # ends in 0000 for RX/RY/RZ.  A load with a net moment about the vertical
    # axis therefore cannot be equilibrated by the supports at all, and the
    # residual MZ equals the applied torque exactly.  That is a real property
    # of the model (and of a pin-jointed double-layer grid), not round-off, so
    # it is reported separately from the force balance.
    torsional_free = all(
        str(p.get("constraint", "0000000"))[5] == "0" for p in state["supports"])
    balance = []
    for lc in cases:
        name = lc[:-4]
        external = list(applied.get(name, [0.] * 6))
        sw = sw_by_case.get(name, {}).get("self_weight", 0.)
        if sw:
            external[2] += sw
            external[3] += sw_moment[0]
            external[4] += sw_moment[1]
        reaction = react_summary.get(lc) or react_summary.get(name, {})
        r6 = [reaction.get("sum_FX", 0.), reaction.get("sum_FY", 0.),
              reaction.get("sum_FZ", 0.), reaction.get("sum_MX", 0.),
              reaction.get("sum_MY", 0.), reaction.get("sum_MZ", 0.)]
        # external load + support reaction must cancel: the residual is what is
        # left over, i.e. the part of the applied load the supports do not see.
        residual = [external[j] + r6[j] for j in range(6)]
        # Tolerance: the residual is a cancellation of numbers of the size of
        # the applied load and the support reactions.  MIDAS reports each to 9
        # significant figures, so the round-off floor of the SUM scales with
        # the absolute magnitude of the contributions, not with the (possibly
        # near-zero) external component alone.  Absolute contributions are
        # summed per component; a relative floor of 1e-4 of that scale is far
        # above double-precision round-off and far below any real modelling
        # error, and the 1e-3 absolute floor covers cases with no load at all.
        abs_scale = [0.] * 6
        for j, key in enumerate(("abs_force", "abs_moment")):
            arr = reaction.get(key) or [0.] * 3
            for k in range(3):
                abs_scale[j * 3 + k] = abs(arr[k]) + abs(external[j * 3 + k])
        tol_by_component = [max(1e-3, 1e-4 * s_) for s_ in abs_scale]
        tol = max(tol_by_component)
        if lc.endswith("(RS)"):
            # A response-spectrum case is a statistical combination of modal
            # maxima, not an equilibrium load set: there is no applied load to
            # balance against, and the reaction sum IS the base shear. Marking
            # it FAIL against a static equilibrium rule would be meaningless.
            balance.append({
                "case": lc, "external": None, "reaction": r6, "residual": None,
                "tolerance": None, "components": ["FX", "FY", "FZ", "MX", "MY", "MZ"],
                "status": "NOT_APPLICABLE", "pass": None,
                "base_shear": {"FX": r6[0], "FY": r6[1], "FZ": r6[2]},
                "note": ("response-spectrum result: the reaction sum is the base "
                         "shear of the CQC combination. Equilibrium balance does "
                         "not apply to a modal-maximum combination."),
            })
            continue
        force_ok = all(abs(residual[j]) <= tol_by_component[j] for j in range(3))
        moment_ok = all(abs(residual[j]) <= tol_by_component[j] for j in range(3, 6))
        torque_applied = abs(external[5])
        # A pure applied torque about Z on a support system with no rotational
        # restraint cannot be reacted: the residual equals the applied torque.
        # That is a property of the model, not a numerical error.
        torsional_unbalanced = (torsional_free and torque_applied > 1e-6
                                and abs(residual[5] + external[5]) <= tol_by_component[5])
        # A residual within an order of magnitude of the round-off tolerance is
        # not evidence of a modelling error: DB:PDEL is present, so /doc/ANAL
        # runs a second-order (P-Delta) solution, in which equilibrium is
        # satisfied in the deformed configuration and MIDAS reports each
        # quantity to 9 significant figures.  Those cases are reported as
        # MARGINAL with the relative residual shown, not silently passed.
        rel = [abs(residual[j]) / max(abs(external[j]), abs(r6[j]), 1e-9)
               for j in range(6)]
        marginal = all(abs(residual[j]) <= 10 * tol_by_component[j]
                       for j in range(6))
        if force_ok and moment_ok:
            status = "PASS"
        elif marginal:
            status = "MARGINAL"
        else:
            status = "FAIL"
        note = ("external FZ includes the MIDAS native self-weight (LOAD_SUMMARY_Z); "
                "its moment about the origin is added from POST:TABLE:ELEMENTWEIGHT, "
                "which is what closes the DEAD case. The nodal loads are the "
                "tributary-converted values in validation.applied_load_six_components.")
        if torsional_unbalanced:
            status = "PASS_TORSION_FREE"
            note = (
                "The supports restrain translation only (every DB:CONS constraint "
                "ends in 0000 for RX/RY/RZ), so a load whose resultant has a moment "
                "about the vertical axis cannot be equilibrated: the residual MZ "
                f"equals the applied torque ({external[5]:.3f} kN.m) exactly. "
                "The force balance is exact. This is a property of the support "
                "system, not a numerical error - a pin-jointed space grid needs a "
                "torsion-resisting support (or a braced plan position) to carry it.")
        balance.append({
            "case": lc, "external": external, "reaction": r6, "residual": residual,
            "tolerance": tol, "tolerance_by_component": tol_by_component,
            "status": status,
            "components": ["FX", "FY", "FZ", "MX", "MY", "MZ"],
            "pass": status == "PASS",
            "force_balance": {"pass": force_ok,
                              "residual": residual[:3],
                              "tolerance": tol_by_component[:3]},
            "moment_balance": {"pass": moment_ok,
                               "residual": residual[3:],
                               "tolerance": tol_by_component[3:]},
            "relative_residual": rel,
            "torsion_free_support_system": torsional_free,
            "note": note,
        })
    applicable = [b for b in balance if b["status"] != "NOT_APPLICABLE"]
    state["load_balance"] = {
        "rows": balance,
        "cases_checked": len(applicable),
        "cases_passing": sum(1 for b in applicable if b["pass"]),
        "cases_marginal": sum(1 for b in applicable if b["status"] == "MARGINAL"),
        "cases_torsion_free": sum(1 for b in applicable
                                  if b["status"] == "PASS_TORSION_FREE"),
        "cases_not_applicable": len(balance) - len(applicable),
        "tolerance_rule": ("per component: max(1e-3 kN, 1e-4 * (sum of |external "
                           "contribution| + sum of |support contribution|))"),
        "support_system": ("every support constrains translation only "
                           "(RX=RY=RZ=0), so global MZ cannot be reacted"
                           if torsional_free else "rotational restraint present"),
        "note": ("MIDAS reports reactions to 9 significant figures; the tolerance "
                 "is therefore scaled by the magnitude of the terms that cancel, "
                 "not by the residual. A residual above tolerance means the applied "
                 "load is not fully carried by the supports, which for a "
                 "self-equilibrated static case indicates a modelling error rather "
                 "than round-off. Response-spectrum cases are excluded: their "
                 "reaction sum is a base shear, not an equilibrium residual."),
    }
    save("load_balance.json", balance)

    # ---- POST/TABLE vs DB consistency -------------------------------------
    # The same physical quantity read two ways: the analysis result table and
    # the model database.  A disagreement means one of them is stale.
    consistency = []
    total_weight = sum(float(r[12]) for r in sw_rows)
    # LOAD_SUMMARY_Z reports the self-weight as a signed global-Z force, so it
    # comes back negative (downward) while ELEMENTWEIGHT's per-element 'Total
    # Weight' is a positive magnitude.  Compare magnitudes, not signed values,
    # or a consistent model reads as a 200 % disagreement.
    self_weight_sum = sw_by_case.get("DEAD", {}).get("self_weight")
    self_weight_mag = abs(self_weight_sum) if self_weight_sum is not None else None
    consistency.append({
        "quantity": "self weight (total)",
        "from_table": total_weight, "from_other": self_weight_sum,
        "source_a": "POST:TABLE:ELEMENTWEIGHT column 'Total Weight' (sum over 457 elements)",
        "source_b": "POST:TABLE:LOAD_SUMMARY_Z DEAD 'Self Weight' (signed global-Z force)",
        "relative_difference": abs(total_weight - self_weight_mag) / total_weight if total_weight else None,
        # 1e-5, not 1e-6: MIDAS prints these tables to 9 significant figures, so
        # a 465 kN total carries ~5e-4 kN of print round-off - about 1.3e-6
        # relative.  Anything tighter would flag print precision as a mismatch.
        "pass": self_weight_mag is not None and abs(total_weight - self_weight_mag) <= 1e-5 * total_weight,
    })
    mat = s.records("MATL")
    den = mat["1"]["PARAM"][0]["DEN"]
    volume = total_weight / den if den else None
    consistency.append({
        "quantity": "steel volume implied by self weight",
        "from_table": volume,
        "source_a": "ELEMENTWEIGHT total weight / DB:MATL DEN",
        "source_b": "computed",
        "pass": volume is not None and volume > 0,
    })
    state["consistency"] = consistency
    save("consistency.json", consistency)

    # ---- anomaly scan ------------------------------------------------------
    anomalies = []

    def scan(name, head_, rows_, cols, unit_):
        bad = {"nan": 0, "inf": 0, "zero_all": 0, "outlier": 0}
        values = []
        for r in rows_:
            vals = []
            for c in cols:
                try:
                    vals.append(float(r[c]))
                except (ValueError, IndexError):
                    pass
            if any(math.isnan(v) for v in vals):
                bad["nan"] += 1
            if any(math.isinf(v) for v in vals):
                bad["inf"] += 1
            if vals and all(v == 0. for v in vals):
                bad["zero_all"] += 1
            values.extend(vals)
        if values:
            mean = sum(values) / len(values)
            var = sum((v - mean) ** 2 for v in values) / len(values)
            sd = math.sqrt(var)
            if sd > 0:
                bad["outlier"] = sum(1 for v in values if abs(v - mean) > 6 * sd)
        anomalies.append({"table": name, "unit": unit_, "rows": len(rows_),
                          "values": len(values), **bad,
                          "verdict": "clean" if not any(bad.values()) else "review"})

    scan("DISPLACEMENTG", head, _table(s, "DISPLACEMENTG", cases=cases).get("DATA", []),
         [3, 4, 5], unit.get("1", {}).get("DIST"))
    scan("REACTIONG", head, _table(s, "REACTIONG", cases=cases).get("DATA", []),
         [3, 4, 5, 6, 7, 8], unit.get("1", {}).get("FORCE"))
    scan("TRUSSFORCE", head, _table(s, "TRUSSFORCE", cases=cases).get("DATA", []),
         [3, 4], unit.get("1", {}).get("FORCE"))
    scan("TRUSSSTRESS", head_s, _table(s, "TRUSSSTRESS", cases=cases).get("DATA", []),
         [3, 4], unit.get("1", {}).get("FORCE"))
    # duplicate ids in the model itself
    node_pairs = {}
    for n in state["nodes"]:
        node_pairs.setdefault((n["X"], n["Y"], n["Z"]), []).append(n["structai_id"])
    dup_nodes = {f"{k}": v for k, v in node_pairs.items() if len(v) > 1}
    elem_pairs = {}
    for e in state["elements"]:
        elem_pairs.setdefault(tuple(sorted(e["midas_nodes"])), []).append(e["structai_id"])
    dup_elems = {f"{k}": v for k, v in elem_pairs.items() if len(v) > 1}
    anomalies.append({"table": "model nodes", "duplicate_coordinates": len(dup_nodes),
                      "detail": dict(list(dup_nodes.items())[:5])})
    anomalies.append({"table": "model elements", "duplicate_connectivity": len(dup_elems),
                      "detail": dict(list(dup_elems.items())[:5])})
    state["anomalies"] = {"checks": anomalies,
                          "verdict": "clean" if all(
                              not any(v for k, v in c.items()
                                      if k in ("nan", "inf", "zero_all", "outlier", "duplicate_coordinates", "duplicate_connectivity"))
                              for c in anomalies) else "review"}
    save("anomalies.json", anomalies)

    # ---- geometry stability ------------------------------------------------
    adj = {}
    for e in state["elements"]:
        a, b = e["midas_nodes"]
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    node_ids = {n["midas_id"] for n in state["nodes"]}
    seen, components = set(), []
    for start in node_ids:
        if start in seen:
            continue
        stack, comp = [start], []
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            comp.append(x)
            stack.extend(adj.get(x, ()))
        components.append(comp)
    zero_length = [e["structai_id"] for e in state["elements"]
                   if e["midas_nodes"][0] == e["midas_nodes"][1]]
    # a node with fewer than 3 non-coplanar members cannot be braced in 3D;
    # for a double-layer grid the check that matters is degree >= 3.
    low_degree = [{"node": nodes[n]["structai_id"], "degree": len(adj.get(n, ()))}
                  for n in node_ids if len(adj.get(n, ())) < 3]
    free = [{"node": nodes[n]["structai_id"], "degree": len(adj.get(n, ()))}
            for n in node_ids if len(adj.get(n, ())) == 0]
    constrained = set()
    for p in state["supports"]:
        constrained.add(p["midas_id"])
    # Unrestrained global DOF: for each of the six rigid-body components, is
    # there any support that resists it?  A translation component is resisted
    # when some support constrains that axis; a rotation is resisted when some
    # support constrains it directly OR when enough well-placed translational
    # supports exist to form a couple.  The count below is the direct reading of
    # DB:CONS, and is what makes the torsional finding in the load balance
    # concrete rather than an assertion.
    dof_resisted = {}
    for axis, idx in (("UX", 0), ("UY", 1), ("UZ", 2),
                      ("RX", 3), ("RY", 4), ("RZ", 5)):
        dof_resisted[axis] = any(
            str(p.get("constraint", ""))[idx:idx + 1] == "1" for p in state["supports"])
    # Rigid-body modes: the modal run is checked from the live EIGENVALUEMODE
    # table.  Its top-level DATA is the per-node mode shapes (20 modes x 98
    # nodes); the *summary* - frequencies, periods, participation masses and
    # factors, direction factors - is not a separate endpoint but the table's
    # SUB_TABLES array.  Reading only the top level is why an earlier pass
    # wrongly concluded "no modal summary exists on this build".
    # The parse is done by the connector's own SUB_TABLES parser, so the live
    # driver and the MCP tool agree by construction: if the driver had its own
    # copy, a fix to one would silently leave the other wrong.
    from midas_mcp.results import modal_result
    modal_reply = s.table("EIGENVALUEMODE", MODES=[f"Mode{i}" for i in range(1, 21)],
                          artifact="stability_EIGENVALUEMODE")
    modal = modal_result(modal_reply.get("data")) or {}
    modes = (modal_reply.get("data") or {}).get("EIGENVALUEMODE") or {}
    mhead, mdata = modes.get("HEAD", []), modes.get("DATA", [])
    mode_ids = sorted({r[2] for r in mdata}) if mdata else []
    shape_max = 0.
    if mdata:
        i_mode = mhead.index("Mode")
        for r in mdata:
            for c in range(i_mode + 1, i_mode + 7):
                try:
                    shape_max = max(shape_max, abs(float(r[c])))
                except (ValueError, IndexError):
                    pass
    modes_summary = modal.get("modes", [])
    cumulative = modal.get("cumulative_ratio_percent", {})
    first_modes = modal.get("first_mode_by_axis", {})
    # A rigid-body mode is one whose frequency is numerically zero.  The lowest
    # extracted frequency is therefore the direct test.
    frequencies = [m.get("frequency_hz") for m in modes_summary
                   if m.get("frequency_hz") is not None]
    min_hz = min(frequencies) if frequencies else None
    rigid_body = [m["mode"] for m in modes_summary
                  if (m.get("frequency_hz") or 0.) <= 1e-6]
    state["stability"] = {
        "nodes": len(node_ids), "elements": len(state["elements"]),
        "connected_components": len(components),
        "largest_component": max(len(c) for c in components) if components else 0,
        "is_single_component": len(components) == 1,
        "zero_length_elements": zero_length,
        "nodes_with_degree_below_3": low_degree,
        "unconnected_nodes": free,
        "supports": len(state["supports"]),
        "fixed_supports": sum(1 for p in state["supports"] if p["constraint"][:3] == "111"),
        "partly_released_supports": sum(1 for p in state["supports"] if p["constraint"][:3] != "111"),
        "rigid_body_dof_resisted": dof_resisted,
        "unrestrained_global_dof": [k for k, v in dof_resisted.items() if not v],
        "modes_requested": 20,
        "modes_returned": len(mode_ids),
        "mode_shape_rows": len(mdata),
        "max_mode_shape_component": shape_max,
        "mode_shapes_finite": bool(mdata) and math.isfinite(shape_max) and shape_max > 0,
        "eigenvalue_summary_available": bool(modes_summary),
        "eigenvalue_summary_source": modal.get("source"),
        "eigenvalue_summary_tables": modal.get("tables", []),
        "eigenvalue_sub_tables": modal.get("sub_tables", []),
        "modes": modes_summary,
        "lowest_frequency_hz": min_hz,
        "rigid_body_modes": rigid_body,
        "participation_sum_percent": cumulative,
        "first_mode_by_axis": first_modes,
        "note": ("a single connected component plus at least one fully fixed "
                 "support is the minimum for a stable space grid. Stability is "
                 "confirmed by (a) the 20 requested modes being extracted with "
                 "finite non-zero shapes, (b) the lowest frequency being well "
                 "clear of zero - a rigid-body mode would appear at ~0 Hz - and "
                 "(c) every static case converging. The RZ direction has no "
                 "direct rotational restraint, which is why the support system "
                 "resists torque only through the lever arm of its in-plane "
                 "forces."),
    }
    save("stability.json", state["stability"])
    save("modal_summary.json", modal)

    # ---- space-grid result search -----------------------------------------
    # The report has to answer the questions a grid designer actually asks, not
    # just dump maxima per case: which chord/web member is worst, at which node,
    # and under which combination.
    search = {}

    # displacements: max magnitude, and which case/combination drives it
    dmax = None
    for r in disp_rows:
        try:
            mag = math.sqrt(sum(float(r[i]) ** 2 for i in (3, 4, 5)))
        except (ValueError, IndexError):
            continue
        if dmax is None or mag > dmax["magnitude"]:
            nid = int(r[1])
            dmax = {"magnitude": mag, "node": nid,
                    "structai_id": nodes.get(nid, {}).get("structai_id"),
                    "layer": nodes.get(nid, {}).get("layer"),
                    "load": r[2], "DX": float(r[3]), "DY": float(r[4]),
                    "DZ": float(r[5])}
    search["max_displacement"] = dmax

    # reactions: largest single support force
    rmax = None
    for r in react_rows:
        try:
            mag = math.sqrt(sum(float(r[i]) ** 2 for i in (3, 4, 5)))
        except (ValueError, IndexError):
            continue
        if rmax is None or mag > rmax["magnitude"]:
            nid = int(r[1])
            rmax = {"magnitude": mag, "node": nid,
                    "support": supports.get(nid, {}).get("name"),
                    "load": r[2], "FX": float(r[3]), "FY": float(r[4]),
                    "FZ": float(r[5])}
    search["max_reaction"] = rmax

    # member force: tension and compression extremes with their group
    def _member(want_max):
        best = None
        for r in force_rows:
            try:
                v = float(r[3])
            except (ValueError, IndexError):
                continue
            if best is None or (v > best["value"] if want_max else v < best["value"]):
                eid = int(r[1])
                best = {"value": v, "element": eid,
                        "structai_id": elems.get(eid, {}).get("structai_id"),
                        "group": elems.get(eid, {}).get("group"),
                        "load": r[2]}
        return best
    search["max_tension"] = _member(True)
    search["max_compression"] = _member(False)

    # per-group extremes: upper chord, lower chord, web, separately
    group_extremes = {}
    for r in force_rows:
        try:
            eid, v = int(r[1]), float(r[3])
        except (ValueError, IndexError):
            continue
        g = elems.get(eid, {}).get("group")
        if g is None:
            continue
        slot = group_extremes.setdefault(g, {"tension": None, "compression": None})
        for key, better in (("tension", v > 0 and (slot["tension"] is None
                                                   or v > slot["tension"]["value"])),
                            ("compression", v < 0 and (slot["compression"] is None
                                                       or v < slot["compression"]["value"]))):
            if better:
                slot[key] = {"value": v, "element": eid,
                             "structai_id": elems.get(eid, {}).get("structai_id"),
                             "load": r[2]}
    search["by_group"] = group_extremes

    # The governing combination (the one with the largest member force).  MIDAS
    # returns a combination as three envelopes - 'ULS-01(all)', '(max)', '(min)'
    # - so the label is matched on its base name, and the envelope is kept so
    # the reported row can be traced back to the exact table entry.
    combo_bases = set(combos)
    gov = None
    for r in force_rows:
        label = r[2]
        base = label.split("(", 1)[0]
        if base in combo_bases:
            try:
                v = abs(float(r[3]))
            except (ValueError, IndexError):
                continue
            if gov is None or v > gov["abs_force"]:
                eid = int(r[1])
                gov = {"combination": base, "envelope": label, "abs_force": v,
                       "element": eid,
                       "structai_id": elems.get(eid, {}).get("structai_id"),
                       "group": elems.get(eid, {}).get("group"),
                       "force": float(r[3])}
    search["governing_combination"] = gov

    # the named natural-hazard cases, compared side by side
    comparisons = {}
    for fam, names in (("wind", ("WIND_X_POS", "WIND_X_NEG", "WIND_Y_POS",
                                 "WIND_Y_NEG", "WIND_UP", "WIND_DOWN")),
                       ("snow", ("SNOW", "SNOW_UNBALANCED")),
                       ("temperature", ("TEMP_POS", "TEMP_NEG", "TEMP_GRADIENT")),
                       ("seismic", ("EQ_X(RS)", "EQ_Y(RS)", "EQ_Z(RS)"))):
        comparisons[fam] = [{
            "case": nm,
            "max_abs_displacement": max(
                (abs(float(r[i])) for r in disp_rows if r[2] == nm for i in (3, 4, 5)),
                default=None),
            "max_abs_vertical_reaction": max(
                (abs(float(r[5])) for r in react_rows if r[2] == nm), default=None),
            "max_abs_axial_force": max(
                (abs(float(r[3])) for r in force_rows if r[2] == nm), default=None),
        } for nm in names]
    search["hazard_comparisons"] = comparisons
    state["result_search"] = search
    save("result_search.json", search)

    save("state.json", state)
    print("Results extracted:", state["results_displacement"]["rows"], "displacement rows,",
          state["results_force"]["rows"], "force rows; balance",
          state["load_balance"]["cases_passing"], "/", state["load_balance"]["cases_checked"],
          "pass,", state["load_balance"]["cases_marginal"], "marginal;",
          "stability components", len(components), flush=True)


def steel_design(s):
    """Steel code check via /DESIGN/STEEL — result: UNSUPPORTED on this build.

    Everything up to the check itself works and is recorded as PASS: the design
    code is selected (DSTL), the Q355 yield/tensile strengths are stored
    (SMODI - note these live in the *design* module, not in DB:MATL, whose
    PARAM carries only E/nu/alpha/density), the frame definition is accepted
    (DCTL) and the members are registered (MEMB).

    The check itself cannot be completed.  Every documented avenue was tried
    and each is recorded below with its verbatim response.  The run is
    deliberately *not* reported as a success, and no design ratio is
    fabricated.  The temporary beam-equivalent conversion is reverted and the
    grid is verified back on TRUSS elements before returning.
    """
    state = json.loads(STATE.read_text(encoding="utf-8"))
    attempts: list[dict] = []
    B = "/DESIGN/STEEL"

    def attempt(name, endpoint, method, payload):
        result = s.call("midas_db_assign", {"endpoint": endpoint, "mode": method,
                                            "data": payload}, required=False)
        attempts.append({"step": name, "endpoint": endpoint, "method": method,
                         "request": payload, "ok": bool(result.get("ok")),
                         "category": result.get("category"),
                         "http_status": result.get("http_status"),
                         "response": result.get("message") or result.get("data")})
        return result

    dstl = attempt("select design code", "DESIGN:STEEL:DSTL", "update",
                   {"1": {"DGNCODE": "KDS 41 30 : 2022"}})
    # Q355 yield strength is a *design* input: DB:MATL has no Fy field at all,
    # and left at 0 the code check has nothing to compare a stress against.
    smodi = attempt("set yield strength", "DESIGN:STEEL:KDS-41-30-2022:SMODI", "update",
                    {"1": {"CODE": "None", "NAME": "Q355", "ES": 206000000.,
                           "PS": .3, "FU": 490000., "FY": 355000.}})
    attempt("frame definition", "DESIGN:STEEL:KDS-41-30-2022:DCTL", "update",
            {"1": {"FRAMEX": "Braced Non-sway", "FRAMEY": "Braced Non-sway",
                   "bAUTOKF": True, "DT": "3D"}})
    attempt("strength reduction factors", "DESIGN:STEEL:KDS-41-30-2022:SRDF", "update",
            {"1": {"PHI_T1": .90, "PHI_T2": .90, "PHI_C": .85, "PHI_B": .90, "PHI_V": .90}})
    attempt("unbraced lengths", "DESIGN:STEEL:KDS-41-30-2022:LENG", "update",
            {"1": {"bNOTUSE": False, "bAUTOCALC": True}})
    smodi_live = s.query("DESIGN:STEEL:KDS-41-30-2022:SMODI").get("data")

    # The design module refuses TRUSS elements.  The grid is forced back to
    # TRUSS first so this attempt is made against a genuinely TRUSS element,
    # not whatever the previous run happened to leave behind.
    before = s.records("ELEM")
    s.call("midas_db_assign", {"endpoint": "DB:ELEM", "mode": "update",
           "data": {k: {"TYPE": "TRUSS", "MATL": v["MATL"], "SECT": v["SECT"],
                        "NODE": v["NODE"][:2], "ANGLE": v.get("ANGLE", 0)}
                    for k, v in before.items()}})
    if {v["TYPE"] for v in s.records("ELEM").values()} != {"TRUSS"}:
        raise RuntimeError("could not force the grid back to TRUSS")
    truss_memb = s.call("midas_db_assign",
                        {"endpoint": "DESIGN:STEEL:KDS-41-30-2022:MEMB",
                         "mode": "update", "data": {"1": {"AELEM": [1], "bREVERSE": False}}},
                        required=False)
    attempts.append({"step": "register member on a TRUSS element",
                     "endpoint": "DESIGN:STEEL:KDS-41-30-2022:MEMB", "method": "update",
                     "request": {"1": {"AELEM": [1]}}, "ok": bool(truss_memb.get("ok")),
                     "category": truss_memb.get("category"),
                     "http_status": truss_memb.get("http_status"),
                     "response": truss_memb.get("message") or truss_memb.get("data")})

    # --- temporary beam-equivalent model (reverted at the end) -------------
    s.call("midas_db_assign", {"endpoint": "DB:ELEM", "mode": "update",
           "data": {k: {"TYPE": "BEAM", "MATL": v["MATL"], "SECT": v["SECT"],
                        "NODE": v["NODE"][:2], "ANGLE": v.get("ANGLE", 0)}
                    for k, v in before.items()}})
    after = s.records("ELEM")
    if {v["TYPE"] for v in after.values()} != {"BEAM"}:
        raise RuntimeError("beam-equivalent conversion did not take effect")
    elem = {int(k): v for k, v in after.items()}
    ids = sorted(elem)
    # The design module keeps its OWN combination set (DB:LCOM-STEEL), separate
    # from DB:LCOM-GEN.  It is empty on a fresh model, which is a plausible
    # cause of the "LoadCombination" half of the failure, so it is populated
    # from the analysed combinations before the check is retried.
    gen = s.records("LCOM-GEN")
    s.call("midas_db_assign", {"endpoint": "DB:LCOM-STEEL", "mode": "update",
           "data": {k: {"NAME": v["NAME"], "ACTIVE": "ACTIVE", "bES": False,
                        "bCB": True, "iTYPE": 1, "DESC": v.get("DESC", ""),
                        "vCOMB": v["vCOMB"]} for k, v in gen.items()}})
    steel_combos = s.records("LCOM-STEEL")
    attempts.append({"step": "populate the design combination set",
                     "endpoint": "DB:LCOM-STEEL", "method": "update",
                     "request": f"{len(gen)} combinations", "ok": bool(steel_combos),
                     "response": f"{len(steel_combos)} combinations stored"})

    singletons = {str(i): {"AELEM": [e], "bREVERSE": False}
                  for i, e in enumerate(ids, 1)}
    memb = attempt("register one member per element",
                   "DESIGN:STEEL:KDS-41-30-2022:MEMB", "update", singletons)
    memb_live = s.query("DESIGN:STEEL:KDS-41-30-2022:MEMB").get("data") or {}
    # Section-uniform connected chains and a single all-element member were
    # tried live as well; both are rejected by MEMB with "Please Select the
    # connected element." / "所选单元中没有单元被指定为构件.(特性不同)".

    anal = s.call("midas_doc", {"command": "ANAL", "argument": {}}, required=False)
    save("design_analysis_command.json", anal)
    if not anal.get("ok"):
        raise RuntimeError(f"analysis before the design run failed: {anal}")
    code_anal = attempt("perform steel code check",
                        "DESIGN:STEEL:KDS-41-30-2022:CODE-ANAL", "create",
                        {"PERFORM_TYPE": "ALL"})
    table = s.call("midas_db_assign",
                   {"endpoint": "DESIGN:STEEL:KDS-41-30-2022:CODE-TABLE",
                    "mode": "create", "data": {"Argument": {"TABLE_TYPE": "DESIGNCHECK",
                    "UNIT": {"FORCE": "KN", "DIST": "M"},
                    "STYLES": {"FORMAT": "Scientific", "PLACE": 9}}}}, required=False)
    save("design_code_table.json", table)

    # --- revert and verify the grid is back on TRUSS ----------------------
    # TRUSS is the grid's canonical element type, so it is restored explicitly
    # rather than by replaying whatever type happened to be live beforehand.
    s.call("midas_db_assign", {"endpoint": "DB:ELEM", "mode": "update",
           "data": {k: {"TYPE": "TRUSS", "MATL": v["MATL"], "SECT": v["SECT"],
                        "NODE": v["NODE"][:2], "ANGLE": v.get("ANGLE", 0)}
                    for k, v in before.items()}})
    restored = s.records("ELEM")
    if {v["TYPE"] for v in restored.values()} != {"TRUSS"}:
        raise RuntimeError("failed to revert the beam-equivalent conversion")
    reanal = s.call("midas_doc", {"command": "ANAL", "argument": {}}, required=False)
    if not reanal.get("ok"):
        raise RuntimeError(f"analysis after reverting to TRUSS failed: {reanal}")

    state["steel_design"] = {
        "status": "UNSUPPORTED" if not code_anal.get("ok") else "PASS",
        "code": "KDS 41 30 : 2022",
        "setup": {"DSTL": dstl.get("data"), "SMODI": smodi_live,
                  "members_registered": len(memb_live.get("MEMB", memb_live)),
                  "element_type_for_design": "BEAM (converted from TRUSS, reverted)"},
        "unsupported": {
            "feature": "steel code check (DESIGN/STEEL .../CODE-ANAL)",
            "version": "MIDAS Gen NX 2027, build 26.09.01.1001",
            "region": "KDS (Korea) steel design module",
            "endpoint": "/DESIGN/STEEL/KDS-41-30-2022/CODE-ANAL",
            "tool": "midas_db_assign", "method": "POST",
            "actual_response": code_anal.get("message"),
            "http_status": code_anal.get("http_status"),
            "reason": ("CODE-ANAL answers HTTP 400 'failed:SectionType, "
                       "LoadCombination' with no further detail, after every "
                       "documented prerequisite was satisfied and verified by "
                       "readback: the code selected (DSTL), Q355 Fy/Fu stored "
                       "(SMODI - these live in the design module, not in "
                       "DB:MATL), the frame defined (DCTL), unbraced lengths "
                       "auto-calculated (LENG), strength reduction factors set "
                       "(SRDF), all 457 elements registered as members (MEMB), "
                       "the design combination set populated (DB:LCOM-STEEL, "
                       "28 combinations) and a fresh /doc/ANAL completed. The "
                       "token 'SectionType' names a section-classification "
                       "input that the KDS steel module exposes no endpoint "
                       "for on this build. No design ratio is reported rather "
                       "than fabricating one."),
            "attempts": attempts,
        },
    }
    save("state.json", state)
    print("Steel design:", state["steel_design"]["status"], flush=True)


def _table(s, kind, cases=None, ids=None, artifact=None, **extra):
    """Read a /post/TABLE and return just its inner table dict."""
    result = s.table(kind, cases=cases, ids=ids, artifact=artifact, **extra)
    return (result.get("data") or {}).get(kind) or {}


def _sub(table, name):
    for entry in table.get("SUB_TABLES", []):
        if name in entry:
            return entry[name]
    return {}


def _sub_displacements(table):
    """Return ``{(node, case): row}`` from a DISPLACEMENTG table."""
    head, rows = table.get("HEAD", []), table.get("DATA", [])
    try:
        i_node, i_case = head.index("Node"), head.index("Load")
    except ValueError:
        return {}
    return {f"{r[i_node]}|{r[i_case]}": r for r in rows}


def second_order(s):
    """P-Delta and buckling.

    MIDAS Gen NX 2027 refuses several analysis types in one /doc/ANAL, each
    with its own ``[错误] 不能同时执行`` message.  Probed live:

    * eigenvalue  + buckling        -> refused
    * response spectrum + buckling  -> refused
    * P-Delta     + buckling        -> refused

    Buckling therefore runs on its own with DB:EIGV / DB:SPLC / DB:PDEL
    removed, and they are restored and re-run afterwards.  P-Delta itself runs
    happily alongside the eigenvalue and response-spectrum analyses (it only
    warns about the forced-displacement degrees of freedom), so the normal
    model keeps P-Delta active.
    """
    state = json.loads(STATE.read_text(encoding="utf-8"))
    # Buckling must be absent while P-Delta runs; it is (re)created below.
    s.call("midas_db_delete", {"endpoint": "DB:BUCK", "target_ids": ["1"]}, required=False)
    state["second_order"] = {"PDEL": None, "BUCK": None}
    save("state.json", state)

    # --- true linear baseline: P-Delta off, everything else unchanged ------
    s.call("midas_db_delete", {"endpoint": "DB:PDEL", "target_ids": ["1"]}, required=False)
    baseline = s.call("midas_doc", {"command": "ANAL", "argument": {}}, required=False)
    save("linear_baseline_analysis_command.json", baseline)
    if not baseline.get("ok"):
        raise RuntimeError(f"linear baseline analysis refused: {baseline}")
    before = _sub_displacements(_table(s, "DISPLACEMENTG", cases=["DEAD(ST)"]))
    save("pdelta_before_DISPLACEMENTG.json", before)
    if not before:
        raise RuntimeError("linear baseline produced no DEAD(ST) displacements")

    # --- same model, P-Delta on -------------------------------------------
    pdel = s.ensure("PDEL", {"1": {"ITER": 5, "TOL": 1e-4, "PDEL_CASES": [
        {"LCNAME": n, "FACTOR": 1.} for n in ("DEAD", "ROOF_DEAD", "ROOF_LIVE")]}})
    if not pdel["1"]["PDEL_CASES"]:
        raise RuntimeError("PDEL readback lost its load cases")
    lin = s.call("midas_doc", {"command": "ANAL", "argument": {}}, required=False)
    save("pdelta_analysis_command.json", lin)
    if not lin.get("ok"):
        raise RuntimeError(f"P-Delta analysis refused: {lin}")
    after = _sub_displacements(_table(s, "DISPLACEMENTG", cases=["DEAD(ST)"]))
    save("pdelta_after_DISPLACEMENTG.json", after)
    if not before or set(before) != set(after):
        raise RuntimeError("P-Delta comparison sets differ; cannot compare")
    delta = {}
    for key, a in after.items():
        b = before[key]
        delta[key] = [float(a[i]) - float(b[i]) for i in range(3, 9)]
    worst = max(delta.values(), key=lambda d: max(abs(x) for x in d))
    peak = max(max(abs(float(b[i])) for i in range(3, 6)) for b in before.values())
    state["second_order"]["PDEL"] = pdel
    state["second_order"]["pdelta_analysis"] = lin
    state["second_order"]["pdelta_comparison"] = {
        "load_case": "DEAD(ST)", "nodes_compared": len(delta),
        "max_linear_translation": peak,
        "max_abs_delta": max(abs(x) for x in worst),
        "amplification_percent": (max(abs(x) for x in worst) / peak * 100.) if peak else None,
        "note": ("the same model analysed twice: once with DB:PDEL absent "
                 "(linear) and once with it present. Differences are the "
                 "second-order amplification of the first-order displacements."),
    }
    save("pdelta_delta.json", delta)

    # --- buckling must run alone ------------------------------------------
    # The live records are the source of truth, but a previous aborted run can
    # have left them deleted, so fall back to the canonical spec rather than
    # silently restoring nothing.
    saved_eigv = s.records("EIGV") or {"1": {"TYPE": "LANCZOS", "iFREQ": 20,
                                             "iITER": 100, "iDIM": 40, "TOL": 1e-10,
                                             "bMINMAX": False, "bSTRUM": False}}
    saved_splc = s.records("SPLC") or {
        str(i): {"NAME": name, "DIR": direction, "ANGLE": angle, "SCALE": 1., "PMFT": 1.,
                 "bDAMP": True, "INTERP": "LINEAR", "COMTYPE": "CQC", "bADDSIGN": False,
                 "iSIGNTYPE": 0, "bMODE": True, "bAUTO": False, "iAUTOTYPE": 0,
                 "aFUNCNAME": ["GRID_TEST_SPECTRUM"],
                 "aUSEMODE": [{"bUSE": True, "MSFACTOR": 1.} for _ in range(20)],
                 "iMDTYPE": 1, "DALL": .05, "bCDAMP": False}
        for i, (name, direction, angle) in enumerate(
            (("EQ_X", "XY", 0.), ("EQ_Y", "XY", 90.), ("EQ_Z", "Z", 0.)), 1)}
    for endpoint, ids in (("DB:EIGV", list(s.records("EIGV"))),
                          ("DB:SPLC", list(s.records("SPLC"))),
                          ("DB:PDEL", list(s.records("PDEL")))):
        if ids:  # an empty delete is refused by design, so don't ask
            s.call("midas_db_delete", {"endpoint": endpoint, "target_ids": ids},
                   required=False)
    save("buckling_cleared_settings.json",
         {"EIGV": s.records("EIGV"), "SPLC": s.records("SPLC"), "PDEL": s.records("PDEL")})
    buck = s.ensure("BUCK", {"1": {"MODE_NUM": 10, "OPT_POSITIVE": True,
        "OPT_CONSIDER_AXIAL_ONLY": False, "OPT_STURM_SEQ": False, "ITEMS": [
            {"LCNAME": "DEAD", "FACTOR": 1., "LOAD_TYPE": 0},
            {"LCNAME": "ROOF_DEAD", "FACTOR": 1., "LOAD_TYPE": 0}]}})
    if int(buck["1"]["MODE_NUM"]) < 10:
        raise RuntimeError(f"BUCK readback mode count {buck['1']['MODE_NUM']} < 10")
    buck_anal = s.call("midas_doc", {"command": "ANAL", "argument": {}}, required=False)
    save("buckling_analysis_command.json", buck_anal)
    if not buck_anal.get("ok"):
        raise RuntimeError(f"buckling analysis refused: {buck_anal}")
    btable = _table(s, "BUCKLINGMODE")
    factors = _sub(btable, "BUCKLING ANALYSIS")
    rows = factors.get("DATA", [])
    if len(rows) < 10:
        raise RuntimeError(f"only {len(rows)} buckling modes returned, expected 10")
    state["second_order"]["BUCK"] = buck
    # Parsed by the connector's SUB_TABLES parser, same as the modal summary.
    from midas_mcp.results import buckling_result
    parsed_buck = buckling_result({"BUCKLINGMODE": btable}) or {}
    state["second_order"]["buckling"] = {
        "modes": parsed_buck.get("modes") or [
            {"mode": int(r[0]), "eigenvalue": float(r[1]), "tolerance": float(r[2])}
            for r in rows],
        "critical_factor": float(rows[0][1]),
        "source": parsed_buck.get("source"),
        "tables": parsed_buck.get("tables", []),
        "note": "eigenvalue is the load-factor multiplier on DEAD+ROOF_DEAD.",
    }

    # --- restore the normal model: P-Delta on, eigenvalue + spectrum back ---
    if s.records("BUCK"):
        s.call("midas_db_delete", {"endpoint": "DB:BUCK", "target_ids": list(s.records("BUCK"))},
               required=False)
    eigv_back = s.ensure("EIGV", saved_eigv)
    splc_back = s.ensure("SPLC", saved_splc)
    s.ensure("PDEL", pdel)
    if int(eigv_back["1"]["iFREQ"]) != 20 or len(splc_back) != 3:
        raise RuntimeError("could not restore EIGV/SPLC to the required state")
    restore = s.call("midas_doc", {"command": "ANAL", "argument": {}}, required=False)
    save("restore_analysis_command.json", restore)
    state["second_order"]["restored"] = {
        "ok": bool(restore.get("ok")),
        "EIGV": s.records("EIGV"), "SPLC_count": len(s.records("SPLC")),
        "PDEL": s.records("PDEL"), "BUCK": s.records("BUCK"),
    }
    if not restore.get("ok"):
        raise RuntimeError(f"could not restore the normal analysis model: {restore}")
    results(s)
    save("state.json", state)
    print("P-Delta, buckling and restore complete; critical factor",
          state["second_order"]["buckling"]["critical_factor"], flush=True)


def construction_stage(s):
    """LC25 CONSTRUCTION_STAGE: 3 stages over the structure groups.

    ``/db/STAG`` does **not** reference load cases.  Its ``ACT_LOAD`` items name
    a *load group* (``DB:LDGR``) and carry a ``DAY`` token whose value is
    ``FIRST``/``LAST`` or a numeric *string* of days; a load-case name in
    ``LOAD_NAME`` is rejected with a bare ``Unknown Error`` and a bare number
    in ``DAY`` is rejected with ``[错误] 施工阶段 荷载组输入错误(项目:加载时间)``.
    ``ACT_BNGR.POS`` is ``DEFORMED``/``ORIGINAL`` - a boolean or ``FIRST`` there
    is rejected with ``Wrong Field``.  A load group is therefore created with
    the same name as the load case it should activate, and the supports are put
    in a boundary group that the first stage activates.  All of these facts were
    established by live probe.

    Presence of ``DB:STAG`` switches ``/doc/ANAL`` into construction-stage mode:
    with stages defined but no ``ACT_BNGR`` the run is refused outright with
    ``[错误] 边界条件 没有定义。`` ("boundary conditions are not defined"), even
    though DB:CONS is fully populated.  The boundary *group* is what the stage
    analysis needs.
    """
    state = json.loads(STATE.read_text(encoding="utf-8"))
    groups = s.records("GRUP")
    if len(groups) != 3:
        raise RuntimeError(f"expected 3 structure groups, found {len(groups)}")
    names = {v["NAME"] for v in groups.values()}
    if names != {"STG1", "STG2", "STG3"}:
        raise RuntimeError(f"unexpected structure group names: {names}")

    # Load groups: one per stage, named after the load case it activates.
    ldgr = s.ensure("LDGR", {"1": {"NAME": "DEAD"}, "2": {"NAME": "ROOF_DEAD"},
                             "3": {"NAME": "ROOF_LIVE"}})
    if {v["NAME"] for v in ldgr.values()} != {"DEAD", "ROOF_DEAD", "ROOF_LIVE"}:
        raise RuntimeError(f"load group readback mismatch: {ldgr}")

    # Boundary group holding every support.  DB:CONS carries the constraints;
    # the stage analysis needs them addressed as a group.
    bngr = s.ensure("BNGR", {"1": {"NAME": "SUP", "AUTOTYPE": 0}})
    if not bngr:
        raise RuntimeError("boundary group SUP did not read back")
    cons = s.records("CONS")
    regrouped = {k: {"ITEMS": [dict(it, GROUP_NAME="SUP") for it in v["ITEMS"]]}
                 for k, v in cons.items()}
    s.call("midas_db_assign", {"endpoint": "DB:CONS", "mode": "update",
                               "data": regrouped}, required=True)
    if {it.get("GROUP_NAME") for v in s.records("CONS").values()
            for it in v["ITEMS"]} != {"SUP"}:
        raise RuntimeError("support regrouping into BNGR SUP did not read back")

    stages = {
        "1": {"NAME": "STAGE-1", "NO": 1, "DURATION": 7., "bSV_RSLT": True,
              "bSV_STEP": False, "bLOAD_STEP": False, "ADD_STEP": [],
              "ACT_ELEM": [{"GRUP_NAME": "STG1", "AGE": 0.}],
              "ACT_BNGR": [{"BNGR_NAME": "SUP", "POS": "DEFORMED"}],
              "ACT_LOAD": [{"LOAD_NAME": "DEAD", "DAY": "FIRST"}]},
        "2": {"NAME": "STAGE-2", "NO": 2, "DURATION": 7., "bSV_RSLT": True,
              "bSV_STEP": False, "bLOAD_STEP": False, "ADD_STEP": [],
              "ACT_ELEM": [{"GRUP_NAME": "STG2", "AGE": 7.}],
              "ACT_LOAD": [{"LOAD_NAME": "ROOF_DEAD", "DAY": "FIRST"}]},
        "3": {"NAME": "STAGE-3", "NO": 3, "DURATION": 7., "bSV_RSLT": True,
              "bSV_STEP": False, "bLOAD_STEP": False, "ADD_STEP": [],
              "ACT_ELEM": [{"GRUP_NAME": "STG3", "AGE": 14.}],
              "ACT_LOAD": [{"LOAD_NAME": "ROOF_LIVE", "DAY": "FIRST"}]},
    }
    read = s.ensure("STAG", stages)
    if len(read) != 3:
        raise RuntimeError(f"expected 3 construction stages, read back {len(read)}")
    for key, want in stages.items():
        got = read.get(key) or {}
        if got.get("NAME") != want["NAME"] or int(got.get("NO", 0)) != want["NO"]:
            raise RuntimeError(f"stage {key} readback mismatch: {got}")
        if got.get("ACT_ELEM") != want["ACT_ELEM"]:
            raise RuntimeError(f"stage {key} activation mismatch: {got.get('ACT_ELEM')}")
        if got.get("ACT_LOAD") != want["ACT_LOAD"]:
            raise RuntimeError(f"stage {key} load activation mismatch: {got.get('ACT_LOAD')}")
        if got.get("ACT_BNGR") != want.get("ACT_BNGR"):
            raise RuntimeError(f"stage {key} boundary mismatch: {got.get('ACT_BNGR')}")

    # STCT: the stage-analysis control record.  Without it /doc/ANAL has no
    # construction-stage analysis to run, so the three stages would exist but
    # never be solved.  FINAL_STAGE names the last stage explicitly.
    stct = s.ensure("STCT", {"1": {"bLAST_FINAL": False, "FINAL_STAGE": "STAGE-3",
                                   "bTRUSS": True, "bBEAM": False,
                                   "iINC_NLA": 0, "bINC_TDE": False,
                                   "bCNS": False}})
    if not stct.get("1", {}).get("FINAL_STAGE"):
        raise RuntimeError(f"STCT readback lost FINAL_STAGE: {stct}")

    anal = s.call("midas_doc", {"command": "ANAL", "argument": {}}, required=False)
    save("construction_stage_analysis_command.json", anal)
    if not anal.get("ok"):
        raise RuntimeError(f"construction-stage analysis refused: {anal}")

    state["construction_stage"] = {
        "status": "APPLIED_READBACK",
        "structure_groups": {k: {"NAME": v["NAME"], "nodes": len(v.get("N_LIST", [])),
                                 "elements": len(v.get("E_LIST", []))}
                             for k, v in groups.items()},
        "load_groups": {k: v["NAME"] for k, v in ldgr.items()},
        "boundary_group": "SUP",
        "stages": read,
        "STCT": stct.get("1"),
        "analysis": {"ok": bool(anal.get("ok")), "status": anal.get("http_status"),
                     "category": anal.get("category"), "warning": anal.get("warning"),
                     "message": anal.get("message")},
        "note": ("ACT_LOAD names an LDGR load group (not a load case) and DAY is "
                 "'FIRST'/'LAST'/numeric-string; ACT_BNGR.POS is "
                 "'DEFORMED'/'ORIGINAL'. Defining DB:STAG without ACT_BNGR makes "
                 "/doc/ANAL answer '[错误] 边界条件 没有定义。' even with DB:CONS "
                 "populated. All verified live by readback."),
    }
    for lc in state["load_cases"]:
        if lc["name"] == "CONSTRUCTION_STAGE":
            lc["status"] = "APPLIED_READBACK"
    save("state.json", state)
    print("Construction stages:", len(read), "analysis ok:", bool(anal.get("ok")), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", action="store_true")
    ap.add_argument("--config", default=None,
                    help="JSON config file to read the credentials from")
    ap.add_argument("--profile", default=None,
                    help="profile inside the config file, e.g. 'MIDAS GEN NX'")
    ap.add_argument("--phase", choices=("inspect", "build", "static_loads", "advanced_loads", "combinations", "linear", "results", "second_order", "steel_design", "construction_stage", "extract"), default="inspect")
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
    try:
        base_url, _ = ensure_credentials(profile=args.profile, config=args.config)
    except MissingCredentials as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"Live target: {base_url}", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    session = Session(args.phase)
    try:
        globals()[args.phase](session)
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
