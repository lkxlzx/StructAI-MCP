"""Documented space-grid analysis requests; only the supplied MCP Session calls MIDAS.

Configuration updates state in memory. The caller saves it, performs ANAL, then
requests results. No analysis, network access, or file writes occur on import.
"""
from __future__ import annotations

from copy import deepcopy
import math

GRAVITY = 9.80665
ADDED_MASS_CASES = ("ROOF_DEAD", "CEILING", "PIPELINE", "EQUIPMENT")
GRAVITY_CASES = ("DEAD",) + ADDED_MASS_CASES
SPECTRUM_NAME = "GRID_TEST_SPECTRUM"
SPECTRUM_POINTS = ((0., .4), (.2, 1.), (.5, .8), (1., .4), (2., .2), (4., .1))


def dynamics_payloads(mode_count=20):
    if type(mode_count) is not int or mode_count < 20:
        raise ValueError("The space-grid test requires at least 20 vibration modes")
    return {
        "STYP": {"STYP": 0, "MASS": 1, "GRAV": GRAVITY,
                 "bSELFWEIGHT": True, "SMASS": 1},
        "LTOM": {"DIR": "XYZ", "bNODAL": True, "bBEAM": False,
                 "bFLOOR": False, "bPRES": False, "GRAV": GRAVITY,
                 "vLC": [{"LCNAME": name, "FACTOR": 1.} for name in ADDED_MASS_CASES]},
        # iITER/iDIM/TOL belong to subspace iteration, not the Lanczos branch.
        "EIGV": {"TYPE": "LANCZOS", "iFREQ": mode_count, "bMINMAX": False,
                 "FRMIN": 0., "FRMAX": 0., "bSTRUM": False},
        "SPFC": {"NAME": SPECTRUM_NAME, "iTYPE": 1, "iMETHOD": 0,
                 "SCALE": 1., "GRAV": GRAVITY, "DRATIO": .05,
                 "DESC": "User spectrum in g; assumed 5 percent damping",
                 "aFUNC": [{"PERIOD": t, "VALUE": a} for t, a in SPECTRUM_POINTS]},
        "SPLC": [
            {"NAME": name, "DIR": direction, "ANGLE": angle,
             "SCALE": 1., "PMFT": 1., "INTERP": "LINEAR", "COMTYPE": "CQC",
             "bADDSIGN": False, "iSIGNTYPE": 0, "bMODE": True,
             "bAUTO": False, "iAUTOTYPE": 0,
             "aFUNCNAME": [SPECTRUM_NAME],
             "aUSEMODE": [{"bUSE": True, "MSFACTOR": 1.} for _ in range(mode_count)],
             "bDAMP": True, "bCDAMP": False, "iMDTYPE": 1,
             "DALL": .05, "aDAMPING": []}
            for name, direction, angle in (("EQ_X", "XY", 0.),
                                           ("EQ_Y", "XY", 90.),
                                           ("EQ_Z", "Z", 0.))
        ],
    }


def buckling_payload(mode_count=10):
    if type(mode_count) is not int or mode_count < 10:
        raise ValueError("The space-grid test requires at least 10 buckling modes")
    return {"MODE_NUM": mode_count, "OPT_POSITIVE": True,
            "LOAD_FACTOR_FROM": 0., "LOAD_FACTOR_TO": 0.,
            "OPT_STURM_SEQ": True, "OPT_CONSIDER_AXIAL_ONLY": True,
            # Variable loads: the eigenvalue scales this entire gravity pattern.
            "ITEMS": [{"LCNAME": name, "FACTOR": 1., "LOAD_TYPE": 0}
                      for name in GRAVITY_CASES]}


def pdelta_payload():
    return {"ITER": 30, "TOL": 1e-5,
            "PDEL_CASES": [{"LCNAME": name, "FACTOR": 1.} for name in GRAVITY_CASES]}


def _matches(expected, actual):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _matches(value, actual[key]) for key, value in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(expected) == len(actual) and all(
            _matches(a, b) for a, b in zip(expected, actual))
    if isinstance(expected, bool):
        return actual is expected
    if isinstance(expected, (int, float)):
        return not isinstance(actual, bool) and isinstance(actual, (int, float)) and math.isclose(
            expected, actual, rel_tol=1e-9, abs_tol=1e-12)
    return expected == actual


def _write_control(s, name, record, *, preserve=False):
    existing = s.records(name)
    if len(existing) > 1:
        raise RuntimeError(f"{name}: expected at most one analysis-control record")
    key = next(iter(existing), "1")
    payload = {**(deepcopy(existing[key]) if preserve and existing else {}), **record}
    readback = s.put(name, {key: payload}, "update" if existing else "create")
    if not readback or not _matches(record, readback.get(key)):
        raise RuntimeError(f"{name}: analysis-control readback does not match the request")
    return readback


def _write_named(s, name, records):
    existing = s.records(name)
    next_id = max((int(key) for key in existing), default=0) + 1
    creates, updates, expected = {}, {}, {}
    for record in records:
        matches = [key for key, value in existing.items() if value.get("NAME") == record["NAME"]]
        if len(matches) > 1:
            raise RuntimeError(f"{name}: multiple records named {record['NAME']}")
        if matches:
            key = matches[0]
            updates[key] = record
        else:
            key = str(next_id)
            next_id += 1
            creates[key] = record
        expected[key] = record
    readback = existing
    if updates:
        readback = s.put(name, updates, "update")
    if creates:
        readback = s.put(name, creates, "create")
    if not _matches(expected, readback):
        raise RuntimeError(f"{name}: spectrum readback does not match the request")
    return {key: readback[key] for key in expected}


def configure_dynamics(s, state, mode_count=20):
    payloads = dynamics_payloads(mode_count)
    state["dynamics"] = {"status": "CONFIGURING", "mode_count": mode_count,
                         "damping_ratio_assumption": .05, "requests": payloads}
    styp = _write_control(s, "STYP", payloads["STYP"], preserve=True)
    ltom = _write_control(s, "LTOM", payloads["LTOM"])
    state["mass_source"] = {"status": "CONFIGURED_READBACK", "STYP": styp, "LTOM": ltom,
                            "gravity": GRAVITY, "added_load_cases": list(ADDED_MASS_CASES),
                            "self_weight_source": "STYP only; no duplicate DEAD in LTOM"}
    for name in ("EIGV", "SPFC", "SPLC"):
        if name == "EIGV":
            result = _write_control(s, name, payloads[name])
        else:
            result = _write_named(s, name, payloads[name] if name == "SPLC" else [payloads[name]])
        state["dynamics"][name] = result
    state["dynamics"]["status"] = "CONFIGURED_READBACK_NOT_ANALYZED"
    for case in state["load_cases"]:
        for key, record in state["dynamics"]["SPLC"].items():
            if case["name"] == record["NAME"]:
                case.update({"midas_id": key, "status": "APPLIED_READBACK"})
    return state["dynamics"]


def configure_buckling(s, state, mode_count=10):
    payload = buckling_payload(mode_count)
    state["buckling"] = {"status": "CONFIGURING", "mode_count": mode_count, "request": payload}
    state["buckling"]["BUCK"] = _write_control(s, "BUCK", payload)
    state["buckling"].update({
        "status": "CONFIGURED_READBACK_NOT_ANALYZED",
        "interpretation": "Global truss-grid eigenvalue buckling; not individual member flexural buckling",
    })
    return state["buckling"]


def configure_pdelta(s, state):
    payload = pdelta_payload()
    state["pdelta"] = {"status": "CONFIGURING", "request": payload}
    state["pdelta"]["PDEL"] = _write_control(s, "PDEL", payload)
    state["pdelta"].update({
        "status": "CONFIGURED_READBACK_NOT_ANALYZED",
        "comparison": "Compare identical gravity cases before and after PDEL; preserve first-order results first",
    })
    return state["pdelta"]


def _request_table(s, state, phase, kind, data):
    result = s.call("midas_db_assign", {"endpoint": "POST:TABLE:" + kind,
                                      "mode": "create", "data": data}, required=False)
    state.setdefault("analysis_results", {}).setdefault(phase, {})[kind] = result
    return result


def request_mass_tables(s, state):
    return {"MASS_SUMMARY_" + axis: _request_table(
        s, state, "mass", "MASS_SUMMARY_" + axis,
        {"TABLE_TYPE": "MASS_SUMMARY_" + axis, "TABLE_NAME": "MASS_SUMMARY_" + axis})
        for axis in "XYZ"}


def _mode_request(state, kind, count):
    return {"TABLE_TYPE": kind, "TABLE_NAME": kind,
            "UNIT": {"FORCE": "KN", "DIST": "M"},
            "STYLES": {"FORMAT": "Scientific", "PLACE": 12},
            "COMPONENTS": ["Node", "Mode", "UX", "UY", "UZ", "RX", "RY", "RZ"],
            "NODE_ELEMS": {"KEYS": [n["midas_id"] for n in state["nodes"]]},
            "MODES": [f"Mode{i}" for i in range(1, count + 1)]}


def request_modal_results(s, state, phase="linear"):
    count = state["dynamics"]["mode_count"]
    return _request_table(s, state, phase, "EIGENVALUEMODE",
                          _mode_request(state, "EIGENVALUEMODE", count))


def request_buckling_results(s, state, phase="linear"):
    count = state["buckling"]["mode_count"]
    return _request_table(s, state, phase, "BUCKLINGMODE",
                          _mode_request(state, "BUCKLINGMODE", count))


def request_static_results(s, state, phase, cases):
    if not cases or any(not case.endswith(("(ST)", "(RS)", "(CB)", "(CB:max)", "(CB:min)"))
                        for case in cases):
        raise ValueError("Explicit suffixed result load cases are required")
    results = {}
    for kind in ("REACTIONG", "DISPLACEMENTG", "TRUSSFORCE", "TRUSSSTRESS"):
        ids = [item["midas_id"] for item in state["elements" if kind.startswith("TRUSS") else "nodes"]]
        data = {"TABLE_TYPE": kind, "TABLE_NAME": kind,
                "UNIT": {"FORCE": "KN", "DIST": "M"},
                "STYLES": {"FORMAT": "Scientific", "PLACE": 12},
                "NODE_ELEMS": {"KEYS": ids}, "LOAD_CASE_NAMES": list(cases)}
        results[kind] = _request_table(s, state, phase, kind, data)
    return results


def result_subtables(result, table_name):
    """Return native mode-summary tables, without inventing missing result rows."""
    if not result.get("ok"):
        return {}
    table = result.get("data", {}).get(table_name, {})
    return {name: value for group in table.get("SUB_TABLES", []) for name, value in group.items()}
