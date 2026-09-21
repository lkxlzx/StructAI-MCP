"""Advanced loads for the audited SPACE-GRID-TEST-001 Session.

Importing this module does not contact MIDAS. Callers explicitly select the
settlement supports and prestressed members. Successful writes mean readback
verified, never analysis verified. Payload fields follow the saved /info schemas
and manual chapters 06, 07, 10 and 12.
"""
from __future__ import annotations

from copy import deepcopy
import math


ADVANCED_CASES = (
    "TEMP_POS", "TEMP_NEG", "TEMP_GRADIENT", "SUPPORT_SETTLEMENT",
    "FORCED_DISPLACEMENT", "PRESTRESS",
)
STAGE_NAMES = ("CS1_LOWER", "CS2_CLOSE", "CS3_ROOF")


def _records(s, name):
    result = s.query("DB:" + name)
    if not result.get("ok"):
        raise RuntimeError(f"Cannot inspect {name}: {result}")
    return result.get("data", {}).get(name, {})


def _verify(expected, actual, path):
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            raise RuntimeError(f"Readback is not an object at {path}")
        for key, value in expected.items():
            if key not in actual:
                raise RuntimeError(f"Readback omitted {path}.{key}")
            _verify(value, actual[key], f"{path}.{key}")
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            raise RuntimeError(f"Readback list length differs at {path}")
        if path.endswith(".ITEMS"):
            for wanted in expected:
                identity = ("LCNAME", "GROUP_NAME") if "LCNAME" in wanted else ("GROUP_NAME", "CONSTRAINT")
                matches = [item for item in actual if all(item.get(k, "") == wanted.get(k, "") for k in identity)]
                if len(matches) != 1:
                    raise RuntimeError(f"Readback item identity differs at {path}")
                _verify({k: v for k, v in wanted.items() if k != "ID"}, matches[0], path + "[]")
        else:
            for index, (wanted, observed) in enumerate(zip(expected, actual)):
                _verify(wanted, observed, f"{path}[{index}]")
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isclose(expected, actual, rel_tol=1e-9, abs_tol=1e-10):
            raise RuntimeError(f"Readback numeric value differs at {path}: {expected!r} != {actual!r}")
    elif expected != actual:
        raise RuntimeError(f"Readback value differs at {path}: {expected!r} != {actual!r}")


def _write(s, name, desired, existing=None):
    existing = _records(s, name) if existing is None else existing
    readback = existing
    for mode, is_existing in (("update", True), ("create", False)):
        batch = {key: value for key, value in desired.items() if (key in existing) == is_existing}
        if batch:
            readback = s.put(name, batch, mode)
            if readback is None:
                raise RuntimeError(f"{name} write was rejected")
            _verify(batch, readback, name)
    return readback


def _write_load_items(s, name, desired):
    existing = _records(s, name)
    merged = {}
    for key, record in desired.items():
        items = deepcopy(existing.get(key, {}).get("ITEMS", []))
        for wanted in record["ITEMS"]:
            matches = [i for i, item in enumerate(items)
                       if (item.get("LCNAME"), item.get("GROUP_NAME", "")) ==
                          (wanted["LCNAME"], wanted.get("GROUP_NAME", ""))]
            if len(matches) > 1:
                raise RuntimeError(f"Ambiguous {name} load identity for {key}")
            item = deepcopy(wanted)
            if matches:
                item["ID"] = items[matches[0]]["ID"]
                items[matches[0]] = item
            else:
                item["ID"] = max((int(v["ID"]) for v in items), default=0) + 1
                items.append(item)
        merged[key] = {"ITEMS": items}
    return _write(s, name, merged, existing)


def _check_model(s, state, case_names):
    units = _records(s, "UNIT")
    if len(units) != 1:
        raise RuntimeError("Expected a single UNIT record")
    _verify({"FORCE": "KN", "DIST": "M", "TEMPER": "C"}, next(iter(units.values())), "UNIT")
    load_cases = _records(s, "STLD")
    missing = set(case_names) - {v["NAME"] for v in load_cases.values()}
    if missing:
        raise ValueError(f"Define the static load cases first: {sorted(missing)}")
    nodes = _records(s, "NODE")
    elements = _records(s, "ELEM")
    for node in state["nodes"]:
        _verify({str(node["midas_id"]): {c: node[c] for c in ("X", "Y", "Z")}}, nodes, "NODE")
    for element in state["elements"]:
        key = str(element["midas_id"])
        if key not in elements or elements[key]["TYPE"] != "TRUSS" or elements[key]["NODE"][:2] != element["midas_nodes"]:
            raise RuntimeError(f"Live TRUSS topology differs from state at element {key}")
    return load_cases


def advanced_payloads(state, settlement_nodes, displacement_node, prestress_elements):
    """Build only; no I/O. Temperature varies linearly through the grid depth."""
    settlement_nodes = list(settlement_nodes)
    prestress_elements = list(prestress_elements)
    supports = {int(p["midas_id"]): p for p in state["supports"]}
    if len(settlement_nodes) != 2 or len(set(settlement_nodes)) != 2:
        raise ValueError("Select exactly two different settlement supports")
    for node in settlement_nodes:
        if node not in supports or supports[node]["constraint"][2] != "1":
            raise ValueError(f"Settlement node {node} is not a Z-constrained support")
    if displacement_node not in supports or supports[displacement_node]["constraint"][0] != "1":
        raise ValueError("The forced-DX node must have an X restraint")
    elements = {int(e["midas_id"]): e for e in state["elements"]}
    if not prestress_elements or len(set(prestress_elements)) != len(prestress_elements) or not set(prestress_elements) <= elements.keys():
        raise ValueError("Select unique existing TRUSS element IDs for pretension")
    etmp = {}
    for ident, element in elements.items():
        temp = {"UC": 20.0, "LC": 0.0, "WEB": 10.0}[element["group"]]
        etmp[str(ident)] = {"ITEMS": [
            {"ID": 1, "LCNAME": "TEMP_POS", "GROUP_NAME": "", "TEMP": 30.0},
            {"ID": 2, "LCNAME": "TEMP_NEG", "GROUP_NAME": "", "TEMP": -30.0},
            {"ID": 3, "LCNAME": "TEMP_GRADIENT", "GROUP_NAME": "", "TEMP": temp},
        ]}
    sdsp = {}
    for node, case, direction, displacement in [
        *((n, "SUPPORT_SETTLEMENT", 2, -0.01) for n in settlement_nodes),
        (displacement_node, "FORCED_DISPLACEMENT", 0, 0.005),
    ]:
        items = sdsp.setdefault(str(node), {"ITEMS": []})["ITEMS"]
        values = [{"OPT_FLAG": i == direction, "DISPLACEMENT": displacement if i == direction else 0.0}
                  for i in range(6)]
        items.append({"ID": len(items) + 1, "LCNAME": case, "GROUP_NAME": "", "VALUES": values})
    ptns = {str(eid): {"ITEMS": [{"ID": 1, "LCNAME": "PRESTRESS", "GROUP_NAME": "", "TENSION": 100.0}]}
            for eid in prestress_elements}
    return {"ETMP": etmp, "SDSP": sdsp, "PTNS": ptns}


def apply_advanced_loads(s, state, settlement_nodes, displacement_node, prestress_elements):
    payloads = advanced_payloads(state, settlement_nodes, displacement_node, prestress_elements)
    _check_model(s, state, ADVANCED_CASES)
    styp = _records(s, "STYP")
    if len(styp) != 1 or next(iter(styp.values())).get("TEMP") != 0:
        raise ValueError("Set and read back initial temperature STYP.TEMP=0 first")
    cons = _records(s, "CONS")
    for node, dof in [(int(k), i) for k, r in payloads["SDSP"].items()
                      for item in r["ITEMS"] for i, v in enumerate(item["VALUES"]) if v["OPT_FLAG"]]:
        if not any(item["CONSTRAINT"][dof] == "1" for item in cons.get(str(node), {}).get("ITEMS", [])):
            raise ValueError(f"No live support restraint for SDSP node {node}, DOF {dof}")
    # EXLD has no cached schema in the initial inspection; inspect it before writes.
    exld_schema = s.query("DB:EXLD", info=True)
    if "LCNAME_ITEM" not in exld_schema.get("data", {}).get("Argument", {}).get("properties", {}):
        raise RuntimeError("EXLD schema does not expose documented LCNAME_ITEM")
    existing_exld = _records(s, "EXLD")
    if len(existing_exld) > 1:
        raise RuntimeError("Review multiple EXLD records before adding PRESTRESS")
    key = next(iter(existing_exld), "1")
    external_cases = list(existing_exld.get(key, {}).get("LCNAME_ITEM", []))
    if "PRESTRESS" not in external_cases:
        external_cases.append("PRESTRESS")
    counts = {}
    for name, records in payloads.items():
        _write_load_items(s, name, records)
        counts[name] = {"records": len(records), "items": sum(len(v["ITEMS"]) for v in records.values())}
    _write(s, "EXLD", {key: {"LCNAME_ITEM": external_cases}}, existing_exld)
    report = {
        "status": "APPLIED_READBACK", "analysis_status": "NOT_RUN", "endpoints": counts,
        "settlement_nodes": list(settlement_nodes), "displacement_node": displacement_node,
        "prestress_elements": [int(k) for k in payloads["PTNS"]],
        "assumptions": [
            "TEMP_GRADIENT: UC +20 C, LC 0 C, WEB +10 C (mean of a linear height field).",
            "PTNS=100 kN is an external pretension action registered in EXLD, not a verified final 100 kN member force.",
            "Forced DX at the only X support can produce rigid translation rather than member strain.",
        ],
    }
    state.setdefault("validation", {})["advanced_loads"] = report
    for case in state.get("load_cases", []):
        if case["name"] in ADVANCED_CASES:
            case["status"] = "APPLIED_READBACK"
    return report


def _named_records(s, name, specifications):
    existing = _records(s, name)
    desired = {}
    next_id = max((int(key) for key in existing), default=0) + 1
    for specification in specifications:
        matches = [key for key, record in existing.items() if record.get("NAME") == specification["NAME"]]
        if len(matches) > 1:
            raise RuntimeError(f"Duplicate {name} name: {specification['NAME']}")
        key = matches[0] if matches else str(next_id)
        if not matches:
            next_id += 1
        desired[key] = specification
    return _write(s, name, desired, existing)


def apply_construction_stages(s, state):
    """Configure linear cumulative stages, explicit temporary Z props and groups.

    Stage duration is one nominal day; time-dependent effects are disabled.
    The caller must verify PostCS boundary conditions before other analyses.
    """
    _check_model(s, state, ("DEAD", "ROOF_DEAD"))
    existing_stages = _records(s, "STAG")
    if any(record.get("NAME") not in STAGE_NAMES or key not in ("1", "2", "3")
           for key, record in existing_stages.items()):
        raise ValueError("Refusing to overwrite unrelated construction stages")
    groups = []
    for member_group, group_name in (("LC", "GRID_LOWER"), ("UC", "GRID_UPPER"), ("WEB", "GRID_WEB")):
        members = [e for e in state["elements"] if e["group"] == member_group]
        groups.append({"NAME": group_name, "P_TYPE": 0,
                       "N_LIST": sorted({n for e in members for n in e["midas_nodes"]}),
                       "E_LIST": sorted(e["midas_id"] for e in members)})
    _named_records(s, "GRUP", groups)
    _named_records(s, "BNGR", [{"NAME": "GRID_PERM", "AUTOTYPE": 0}, {"NAME": "GRID_TEMP", "AUTOTYPE": 0}])
    _named_records(s, "LDGR", [{"NAME": "GRID_SW"}, {"NAME": "GRID_ROOF"}])

    supports = {int(p["midas_id"]): p for p in state["supports"]}
    temporary = sorted(int(n["midas_id"]) for n in state["nodes"]
                       if n["layer"] == "LC" and int(n["midas_id"]) not in supports)
    current_cons = _records(s, "CONS")
    desired_cons = {}
    for node, support in supports.items():
        items = deepcopy(current_cons.get(str(node), {}).get("ITEMS", []))
        matches = [item for item in items if item["CONSTRAINT"] == support["constraint"]
                   and item.get("GROUP_NAME", "") in ("", "GRID_PERM")]
        if len(matches) != 1:
            raise RuntimeError(f"Cannot identify original permanent support at node {node}")
        matches[0]["GROUP_NAME"] = "GRID_PERM"
        desired_cons[str(node)] = {"ITEMS": items}
    for node in temporary:
        items = deepcopy(current_cons.get(str(node), {}).get("ITEMS", []))
        matches = [item for item in items if item.get("GROUP_NAME") == "GRID_TEMP"]
        if matches:
            if len(matches) != 1 or matches[0]["CONSTRAINT"] != "0010000":
                raise RuntimeError(f"Unexpected existing temporary support at node {node}")
        else:
            items.append({"ID": max((int(v["ID"]) for v in items), default=0) + 1,
                          "GROUP_NAME": "GRID_TEMP", "CONSTRAINT": "0010000"})
        desired_cons[str(node)] = {"ITEMS": items}
    _write(s, "CONS", desired_cons, current_cons)

    bodf = _records(s, "BODF")
    desired_bodf = {key: {**record, "GROUP_NAME": "GRID_SW"}
                    for key, record in bodf.items() if record.get("LCNAME") == "DEAD"}
    if len(desired_bodf) != 1:
        raise ValueError("Exactly one DEAD selfweight record must exist first")
    _write(s, "BODF", desired_bodf, bodf)
    cnld = _records(s, "CNLD")
    desired_cnld = {}
    roof_count = 0
    for key, record in cnld.items():
        items = deepcopy(record["ITEMS"])
        selected = [item for item in items if item.get("LCNAME") == "ROOF_DEAD"]
        if selected:
            for item in selected:
                item["GROUP_NAME"] = "GRID_ROOF"
            roof_count += len(selected)
            desired_cnld[key] = {"ITEMS": items}
    if not roof_count:
        raise ValueError("Apply ROOF_DEAD nodal loads before configuring stages")
    _write(s, "CNLD", desired_cnld, cnld)

    stages = {}
    for index, name in enumerate(STAGE_NAMES, 1):
        stages[str(index)] = {
            "NAME": name, "DURATION": 1.0, "bSV_RSLT": True, "bSV_STEP": True,
            "bLOAD_STEP": False, "ADD_STEP": [], "ACT_ELEM": [], "DACT_ELEM": [],
            "ACT_BNGR": [], "DACT_BNGR": [], "ACT_LOAD": [], "DACT_LOAD": [],
        }
    stages["1"].update({
        "ACT_ELEM": [{"GRUP_NAME": "GRID_LOWER", "AGE": 0.0}],
        "ACT_BNGR": [{"BNGR_NAME": "GRID_PERM", "POS": "ORIGINAL"}, {"BNGR_NAME": "GRID_TEMP", "POS": "ORIGINAL"}],
        "ACT_LOAD": [{"LOAD_NAME": "GRID_SW", "DAY": "FIRST"}],
    })
    stages["2"].update({
        "ACT_ELEM": [{"GRUP_NAME": "GRID_UPPER", "AGE": 0.0}, {"GRUP_NAME": "GRID_WEB", "AGE": 0.0}],
        "DACT_BNGR": ["GRID_TEMP"],
    })
    stages["3"]["ACT_LOAD"] = [{"LOAD_NAME": "GRID_ROOF", "DAY": "FIRST"}]
    _write(s, "STAG", stages, existing_stages)
    current_control = _records(s, "STCT")
    if len(current_control) > 1:
        raise RuntimeError("Review multiple STCT records before changing stage control")
    control_key = next(iter(current_control), "1")
    control = {
        "bLAST_FINAL": True, "FINAL_STAGE": "CS3_ROOF", "iINC_NLA": 0, "iNLA_TYPE": 1,
        "bSAVE_OCS": True, "bINC_PDL": False, "bINC_TDE": False, "bCNS": False,
        "CPFC": "INTERNAL", "bEXT_REPL": False, "bCONV": False, "bTRUSS": False,
        "bBEAM": False, "bAPPLY_IMF": False, "bCHANGE_CABLE": False,
        "bITD": False, "ITD": "ALL", "bLFFC": False, "bCAMBER": False,
        "bCALC_CFF": False, "bCALC_CSP": False, "bSELFCONS": False, "iBSC": 0,
        "vEREC": [{"LTYPECC": "GRID_DEAD", "EREC": "D", "vLCNAME": ["DEAD", "ROOF_DEAD"]}],
    }
    _write(s, "STCT", {control_key: control}, current_control)
    report = {
        "status": "CONFIGURED_READBACK", "analysis_status": "NOT_RUN",
        "stage_names": list(STAGE_NAMES), "result_case": "Summation(CS)",
        "temporary_support_nodes": temporary, "temporary_constraint": "0010000",
        "member_counts": {g["NAME"]: len(g["E_LIST"]) for g in groups},
        "roof_load_items": roof_count,
        "assumptions": [
            "One nominal day per stage; linear cumulative analysis without creep or shrinkage.",
            "Temporary Z props restrain every unsupported lower-grid node until upper grid and webs are activated.",
            "Temporary props are removed in CS2 before roof dead load is activated in CS3.",
            "Native CS results are not the empty CONSTRUCTION_STAGE static placeholder case.",
        ],
        "pending_checks": [
            "Verify nonempty CS results for all three stages and support-release redistribution.",
            "Verify GRID_TEMP is inactive in PostCS/static/modal boundaries; use explicit BCCT assignment if needed.",
        ],
    }
    state.setdefault("validation", {})["construction_stages"] = report
    for case in state.get("load_cases", []):
        if case["name"] == "CONSTRUCTION_STAGE":
            case["status"] = "STAGES_CONFIGURED_READBACK"
            case["native_result_case"] = "Summation(CS)"
    return report
