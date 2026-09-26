"""Targeted live checks requested by the MIDAS-API manual maintainers.

Each probe starts from the published manual example and changes precisely one
field.  This is deliberately separate from the SDK CRUD fixture: the purpose
is to measure documentation contradictions, including a server accepting an
unknown field but silently ignoring it.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import harness_save_path
from live_crud_check import _seed_model

from midas_nx import doc
from midas_nx.client import MidasClient
from midas_nx.design.steel_kds import MemberAssignment


def _raw(client: MidasClient, method: str, endpoint: str,
         body: dict[str, Any] | None = None) -> dict[str, Any]:
    response = client._session.request(  # noqa: SLF001 - evidence needs HTTP status
        method, client.base_url + endpoint,
        headers={"Content-Type": "application/json", "MAPI-Key": client.mapi_key},
        json=body, timeout=client.timeout,
    )
    try:
        parsed = response.json()
    except ValueError:
        parsed = {"text": response.text}
    return {"status": response.status_code, "body": parsed}


def _empty_members(client: MidasClient) -> dict:
    return MemberAssignment.items(client=client)


def memb_selection_typo(client: MidasClient, checkpoint: str) -> dict:
    """Request 20260918 A-1: ``SELETION_TYPE`` vs ``SELECTION_TYPE``.

    Source payload: MIDAS-API 15_OPE.md, /ope/MEMB English Request Body.
    Elements 2 and 3 are the shared scratch model's collinear beams, replacing
    the article's model-specific 640 and 692 ids.
    """
    doc.new_project(client=client)
    _seed_model(client)
    baseline = {
        "ASSIGN_TYPE": "MANUAL", "SELECTION_TYPE": "SELECTION",
        "ELEM_LIST": [2, 3], "ALLOW_SINGLE": False,
    }
    accepted = client.request("POST", "/ope/MEMB", {"Argument": baseline})
    baseline_read = _empty_members(client)

    # A saved disposable model prevents /doc/NEW from raising NX's save dialog.
    doc.save_as(checkpoint, client=client)
    doc.new_project(client=client)
    _seed_model(client)
    typo = dict(baseline)
    typo["SELETION_TYPE"] = typo.pop("SELECTION_TYPE")
    variant = client.request("POST", "/ope/MEMB", {"Argument": typo})
    variant_read = _empty_members(client)
    return {"baseline": accepted, "baselineGet": baseline_read,
            "variant": variant, "variantGet": variant_read}


def sseis_code_space(client: MidasClient, checkpoint: str) -> dict:
    """Request 20260918 A-2, from 06_DB_Static_Loads.md's KDS example."""
    payload = {
        "SEIS_CODE": "KDS(41-17-00:2019)", "DESC": "X seismic",
        "SCALE_FACTOR_X": 1.0, "SCALE_FACTOR_Y": 0.0,
        "ACCIDENT_ECCEN_X": 0, "ACCIDENT_ECCEN_Y": 2,
        "ACCIDENT_TORSION": True,
        "PARAMETERS": {"SEIS_ZONE": 0, "EPA": 0.22, "SITE_CLASS": 1,
                       "FA": 1.0, "FV": 1.4, "SDS": 0.2933, "SD1": 0.1467,
                       "SEIS_USE_GROUP": 1, "IMPORTANCE_FACTOR": 1.5,
                       "PERIOD_METHOD": 1, "PERIOD_APPR_X": 1.2,
                       "PERIOD_APPR_Y": 1.0, "RESPONSE_MOD_FACTOR_X": 5.0,
                       "RESPONSE_MOD_FACTOR_Y": 5.0},
    }
    doc.new_project(client=client)
    _seed_model(client)
    baseline = client.request("POST", "/db/SSEIS", {"Assign": {1: payload}})
    baseline_get = client.request("GET", "/db/SSEIS/1")
    doc.save_as(checkpoint, client=client)
    doc.new_project(client=client)
    _seed_model(client)
    spaced = dict(payload, SEIS_CODE="KDS(41-17-00: 2019)")
    variant = client.request("POST", "/db/SSEIS", {"Assign": {1: spaced}})
    variant_get = client.request("GET", "/db/SSEIS/1")
    return {"baseline": baseline, "baselineGet": baseline_get,
            "variant": variant, "variantGet": variant_get}


def _story_payload() -> dict[str, Any]:
    common = {
        "WIND_FLOOR_WIDTH_X": 36, "WIND_FLOOR_WIDTH_Y": 27.6,
        "WIND_CENTER_X": 18, "WIND_CENTER_Y": 13.8,
        "WIND_ECCENT_X": 5.4, "WIND_ECCENT_Y": 4.14,
        "SEIS_ACC_ECCENT_X": 1.8, "SEIS_ACC_ECCENT_Y": 1.38,
        "SEIS_INHERENT_ECCENT_X": 0, "SEIS_INHERENT_ECCENT_Y": 0,
        "SEIS_TORSIONAL_AMP_FACTOR_X": 1, "SEIS_TORSIONAL_AMP_FACTOR_Y": 1,
    }
    return {"Assign": {
        1: dict(common, STORY_NAME="1F", STORY_LEVEL=0, bFLOOR_DIAPHRAGM=False),
        2: dict(common, STORY_NAME="2F", STORY_LEVEL=5, bFLOOR_DIAPHRAGM=True,
                WIND_FLOOR_WIDTH_Y=29.1, WIND_CENTER_Y=14.55,
                WIND_ECCENT_Y=4.365, SEIS_ACC_ECCENT_Y=1.455),
    }}


def _user_sseis_payload(field: str) -> dict[str, Any]:
    record: dict[str, Any] = {
        "SEIS_CODE": "USER TYPE", "DESC": "", "SCALE_FACTOR_X": 1,
        "SCALE_FACTOR_Y": 1, "ACCIDENT_ECCEN_X": 0,
        "ACCIDENT_ECCEN_Y": 0, "ACCIDENT_TORSION": False,
        "SEISMIC_FORCE": [
            {"STORY_NAME": "2F", "FORCE_X": 1250.5, "FORCE_Y": 1180.75},
        ],
    }
    record[field] = True
    return {"Assign": {1: record}}


def sseis_torsion_typos(client: MidasClient, checkpoint: str,
                        extension: str) -> dict:
    """Request 20260918 B-1: normal and two documented typo spellings."""
    results: dict[str, Any] = {}
    for index, field in enumerate(("INHERENT_TORSION", "IINHERENT_TORSION",
                                    "NHERENT_TORSION")):
        doc.new_project(client=client)
        _seed_model(client)
        _raw(client, "POST", "/db/STOR", _story_payload())
        results[field] = {
            "post": _raw(client, "POST", "/db/SSEIS", _user_sseis_payload(field)),
            "get": _raw(client, "GET", "/db/SSEIS/1"),
        }
        if index < 2:
            # The extension is the product's own: /doc/SAVEAS rejects the
            # other product's spelling, and a guard save that never lands
            # leaves the next /doc/NEW to raise a save-changes dialog, which
            # blocks the whole API session until a human dismisses it.
            doc.save_as(f"{checkpoint}-{index}.{extension}", client=client)
    return results


def _seed_tendon_element_model(client: MidasClient, element_start: int) -> dict[str, Any]:
    """Build the documented TDNA example's 30 m element chain.

    The geometry and element ids mirror the official online TDNA example.  A
    documented steel material is added as id 2 for the official TDNT Magura
    property; the shared base model already owns material and section id 1.
    """
    _seed_model(client)
    node_start = element_start * 10
    setup = {
        "steelMaterial": _raw(client, "POST", "/db/MATL", {"Assign": {2: {
            "TYPE": "STEEL", "NAME": "SS400", "bMASS_DENS": False,
            "DAMP_RAT": 0.02, "HE_SPEC": 0, "HE_COND": 0, "PLMT": 0,
            "P_NAME": "", "PARAM": [{"P_TYPE": 1, "STANDARD": "KS21(S)",
                                        "CODE": "", "DB": "SS400",
                                        "bELAST": False}],
        }}}),
        "nodes": _raw(client, "POST", "/db/NODE", {"Assign": {
            node_start + index: {"X": index, "Y": 10, "Z": 0}
            for index in range(31)
        }}),
        "elements": _raw(client, "POST", "/db/ELEM", {"Assign": {
            element_start + index: {
                "TYPE": "BEAM", "MATL": 1, "SECT": 1,
                "NODE": [node_start + index, node_start + index + 1],
            }
            for index in range(30)
        }}),
        "tendonGroup": _raw(client, "POST", "/db/TDGR", {
            "Assign": {1: {"NAME": "TGR1"}},
        }),
        "tendonProperty": _raw(client, "POST", "/db/TDNT", {"Assign": {1: {
            "NAME": "In_Pre_Magura", "TYPE": "INTERNAL", "MATL": 2,
            "AREA": 0.00504, "D_AREA": 0.0152, "RM": 0, "RV": 45,
            "US": 1860000, "YS": 1570000, "LT": "PRE",
        }}}),
    }
    return setup


def _tdna_2d_round_payload() -> dict[str, Any]:
    """Official 2D Round/Element example from article 35954555962137."""
    return {
        "NAME": "2D/Round/Element", "TDN_PROP": 1,
        "ELEM": list(range(1201, 1231)), "BELENG": 0, "ELENG": 0,
        "CURVE": "ROUND", "INPUT": "2D", "TDN_GRUP": 1,
        "LENG_OPT": "AUTO2", "bTP": False, "DeBondBLEN": 0.2,
        "DeBondELEN": 0.2, "SHAPE": "ELEMENT", "INS_PT": "END-I",
        "INS_ELEM": 1201, "AXIS_IJ": "I-J", "XAR_ANGLE": 0,
        "bPJ": True, "OFF_YZ": [0, 0],
        "PROFY": [
            {"PT": [0, -0.5], "RADIUS": 0, "OPT": "LEFT", "ANGLE": 1,
             "HEIGHT": 1, "RADIUS2": 20},
            {"PT": [15, -0.5], "RADIUS": 20, "OPT": "NONE"},
            {"PT": [30, -0.5], "RADIUS": 0, "OPT": "RIGHT", "ANGLE": 1,
             "HEIGHT": 1, "RADIUS2": 20},
        ],
        "PROFZ": [
            {"PT": [0, -0.6], "RADIUS": 0, "OPT": "LEFT", "ANGLE": 1,
             "HEIGHT": 1, "RADIUS2": 20, "bBOTZ": False},
            {"PT": [15, -0.6], "RADIUS": 20, "OPT": "NONE",
             "bBOTZ": False},
            {"PT": [30, -0.6], "RADIUS": 0, "OPT": "RIGHT", "ANGLE": 1,
             "HEIGHT": 1, "RADIUS2": 20, "bBOTZ": False},
        ],
    }


def _tdna_3d_round_payload() -> dict[str, Any]:
    """Official 3D Round/Element example from article 35954555962137."""
    return {
        "NAME": "3D/Round/Element", "TDN_PROP": 1,
        "ELEM": list(range(1401, 1431)), "BELENG": 0, "ELENG": 0,
        "CURVE": "ROUND", "INPUT": "3D", "TDN_GRUP": 1,
        "LENG_OPT": "AUTO2", "bTP": True, "CNT": 10,
        "DeBondBLEN": 0.5, "DeBondELEN": 0.5, "SHAPE": "ELEMENT",
        "INS_PT": "END-I", "INS_ELEM": 1401, "AXIS_IJ": "I-J",
        "XAR_ANGLE": 0, "bPJ": True, "OFF_YZ": [0, -0.6],
        "PROF": [
            {"PT": [0, -0.5, 0], "bFIX": False, "RADIUS": 0},
            {"PT": [15, -0.5, 0], "bFIX": False, "RADIUS": 20},
            {"PT": [30, -0.5, 0], "bFIX": False, "RADIUS": 0},
        ],
    }


def _tdna_radius_cases() -> list[tuple[str, int, dict[str, Any]]]:
    """Return two official baselines and their one-field type variants."""
    two_d = _tdna_2d_round_payload()
    two_d_bool = copy.deepcopy(two_d)
    two_d_bool["PROFY"][1]["RADIUS"] = False
    three_d = _tdna_3d_round_payload()
    three_d_array = copy.deepcopy(three_d)
    three_d_array["PROF"][1]["RADIUS"] = [0, 20]
    return [
        ("2d-number", 1201, two_d),
        ("2d-boolean", 1201, two_d_bool),
        ("3d-number", 1401, three_d),
        ("3d-array", 1401, three_d_array),
    ]


def tdna_radius_types(client: MidasClient, checkpoint: str,
                      extension: str) -> dict[str, Any]:
    """Request 20260918 A-3: numeric, Boolean and array RADIUS values."""
    results: dict[str, Any] = {}
    for label, element_start, payload in _tdna_radius_cases():
        doc.new_project(client=client)
        setup = _seed_tendon_element_model(client, element_start)
        results[label] = {
            "setup": setup,
            "post": _raw(client, "POST", "/db/TDNA", {"Assign": {1: payload}}),
            "get": _raw(client, "GET", "/db/TDNA/1"),
        }
        doc.save_as(f"{checkpoint}-{label}.{extension}", client=client)
    return results


def _matd_payload(**extra: Any) -> dict[str, Any]:
    """Documented MATD PUT shape, adapted to the scratch C24 material."""
    payload: dict[str, Any] = {
        "TYPE": "CONC", "NAME": "C24",
        "DATA1": {"CODENAME": "KS01(RC)", "CODEMATLNAME": "C24"},
        "REBAR_CODENAME": "", "MAINREBAR_REBARNAME": "",
        "SUBREBAR_REBARNAME": "", "MAINREBAR_B_FY": 500000,
        "SUBREBAR_B_FY": 600000,
    }
    payload.update(extra)
    return payload


def _spfc_b2_payload() -> dict[str, Any]:
    """Documented response-spectrum function used by the SPLC example."""
    return {
        "NAME": "SPFC_B2", "iTYPE": 2, "iMETHOD": 0, "SCALE": 1,
        "GRAV": 9.806, "DRATIO": 0.05, "DESC": "",
        "aFUNC": [
            {"PERIOD": 0.1, "VALUE": 0.5},
            {"PERIOD": 0.5, "VALUE": 1},
            {"PERIOD": 1, "VALUE": 0.3},
        ],
    }


def _splc_along_payload(along: float) -> dict[str, Any]:
    """Official SPLC base shape plus its schema-only ALONG member."""
    return {
        "NAME": "SPLC_B2", "DIR": "XY", "ANGLE": 0, "SCALE": 1,
        "PMFT": 1, "bDAMP": False, "INTERP": "LOG", "DESC": "",
        "COMTYPE": "CQC", "bADDSIGN": True, "iSIGNTYPE": 0,
        "bMODE": True, "aFUNCNAME": ["SPFC_B2"],
        "aUSEMODE": [
            {"bUSE": True, "MSFACTOR": 1},
            {"bUSE": True, "MSFACTOR": 1},
            {"bUSE": True, "MSFACTOR": 1},
        ],
        "bACCECC": True, "bACCECC_AUTO": False, "ACCECC_PERCENT": 5,
        "bACCECC_CONSIDER_GL": False,
        "bACCECC_MINIMUM_TORSION": False,
        "aACCECC_ECCEN_LIST": [
            {"STORY": "2F", "CROSS": 1.5, "ALONG": along},
        ],
    }


def missing_specification_fields(client: MidasClient, checkpoint: str,
                                 extension: str, product: str) -> dict[str, Any]:
    """Request 20260918 B-2: prove four schema-only fields by round trip."""
    results: dict[str, Any] = {"MATD": {}}
    matd_cases = (
        ("baseline", {}),
        ("bSERVCHECK", {"bSERVCHECK": True}),
        ("dSHORTTERM", {"dSHORTTERM": 1.25}),
        ("dLONGTERM", {"dLONGTERM": 1.5}),
        ("combined", {"bSERVCHECK": True, "dSHORTTERM": 1.25,
                      "dLONGTERM": 1.5}),
    )
    for label, extra in matd_cases:
        doc.new_project(client=client)
        _seed_model(client)
        results["MATD"][label] = {
            "put": _raw(client, "PUT", "/db/MATD", {
                "Assign": {1: _matd_payload(**extra)},
            }),
            "get": _raw(client, "GET", "/db/MATD/1"),
        }
        doc.save_as(f"{checkpoint}-matd-{label}.{extension}", client=client)

    if product == "gen":
        doc.new_project(client=client)
        _seed_model(client)
        setup = {
            "story": _raw(client, "POST", "/db/STOR", _story_payload()),
            "spectrumFunction": _raw(client, "POST", "/db/SPFC", {
                "Assign": {1: _spfc_b2_payload()},
            }),
        }
        created = _raw(client, "POST", "/db/SPLC", {
            "Assign": {1: _splc_along_payload(2.5)},
        })
        created_get = _raw(client, "GET", "/db/SPLC/1")
        updated = _raw(client, "PUT", "/db/SPLC", {
            "Assign": {1: _splc_along_payload(3.5)},
        })
        updated_get = _raw(client, "GET", "/db/SPLC/1")
        results["SPLC"] = {
            "setup": setup, "post": created, "postGet": created_get,
            "put": updated, "putGet": updated_get,
        }
        doc.save_as(f"{checkpoint}-splc.{extension}", client=client)
    else:
        results["SPLC"] = {
            "skipped": "ALONG belongs to the manual's GEN NX-only accidental-eccentricity block",
        }
    return results


def _splc_example(**extra: Any) -> dict[str, Any]:
    """09_DB_Dynamic_Loads.md section 2's no-damping Request Body.

    ``aFUNCNAME`` names this harness's ``SPFC_B2`` in place of the example's
    ``RS_func``; everything else is the example's, plus ``extra``.
    """
    record: dict[str, Any] = {
        "NAME": "LC_RS_XY", "DIR": "XY", "ANGLE": 0, "SCALE": 1, "PMFT": 1,
        "bDAMP": False, "INTERP": "LOG", "COMTYPE": "CQC", "bADDSIGN": True,
        "iSIGNTYPE": 0, "bMODE": True, "aFUNCNAME": ["SPFC_B2"],
        "aUSEMODE": [
            {"bUSE": True, "MSFACTOR": 1},
            {"bUSE": True, "MSFACTOR": 1},
            {"bUSE": True, "MSFACTOR": 1},
        ],
    }
    record.update(extra)
    return record


def _splc_damping_examples() -> list[tuple[str, dict[str, Any]]]:
    """The same section's three damping Request Bodies, ``aFUNCNAME`` swapped."""
    modal = _splc_example(
        NAME="LC_RS_Modal_Damp", bDAMP=True,
        aUSEMODE=[{"bUSE": True, "MSFACTOR": 1}, {"bUSE": True, "MSFACTOR": 1}],
        bCDAMP=True, iMDTYPE=1, DALL=0.05,
        aDAMPING=[{"iMODE": 1, "DAMPING": 0.06}, {"iMODE": 2, "DAMPING": 0.07}],
    )
    direct = _splc_example(
        NAME="LC_RS_M_S_Direct", bDAMP=True,
        aUSEMODE=[{"bUSE": True, "MSFACTOR": 1}], bCDAMP=False, iMDTYPE=2,
        iCOEF=1, bMASSP=True, MASSC=1.1, bSTIFFP=True, STIFFC=1.2,
    )
    calc = _splc_example(
        NAME="LC_RS_M_S_Calc", DIR="Z", bDAMP=True,
        aUSEMODE=[{"bUSE": True, "MSFACTOR": 1}], bCDAMP=False, iMDTYPE=2,
        iCOEF=2, bMASSP=True, bSTIFFP=True, iCALC=1, FP1=0.6, FP2=0.7,
        DR1=0.05, DR2=0.06,
    )
    return [("modalDamping", modal), ("massStiffDirect", direct),
            ("massStiffCalc", calc)]


def splc_gates(client: MidasClient, checkpoint: str, extension: str,
               product: str) -> dict[str, Any]:
    """Which of /db/SPLC's supplementary rows a request has to carry.

    The accidental-eccentricity table marks rows 25-29 Required and the
    non-dissipative table marks NDP Required, each directly under the Boolean
    that switches the feature on, and neither says "when that Boolean is
    true". A confirmed round trip already omits all of them with the Boolean
    left at its default; this measures the other half - the Boolean on and
    its rows left out - and one field at a time. Both tables are GEN NX only.
    The damping examples are measured on both products: their tables state
    the iMDTYPE/iCOEF selection, and nothing had sent them yet.
    """
    probes: list[tuple[str, dict[str, Any]]] = [("base", _splc_example())]
    if product == "gen":
        probes += [
            ("bACCECC_without_rows", _splc_example(bACCECC=True)),
            ("bNDP_without_NDP", _splc_example(bNDP=True)),
            ("bNDP_with_NDP", _splc_example(bNDP=True, NDP=1.0)),
        ]
    probes += _splc_damping_examples()
    results: dict[str, Any] = {}
    for label, record in probes:
        doc.new_project(client=client)
        _seed_model(client)
        setup = _raw(client, "POST", "/db/SPFC", {"Assign": {1: _spfc_b2_payload()}})
        results[label] = {
            "sent": record,
            "setup": setup,
            "post": _raw(client, "POST", "/db/SPLC", {"Assign": {1: record}}),
            "get": _raw(client, "GET", "/db/SPLC/1"),
        }
        doc.save_as(f"{checkpoint}-{label}.{extension}", client=client)
    return results


_WALL_NODE = {30: {"X": 4.0, "Y": 0, "Z": 0}}


def _elem_examples() -> dict[str, dict[str, Any]]:
    """03_DB_Node_Element.md section 2's Request Bodies, on the seed's nodes.

    Line elements use the seed's free pair 21-22 and area elements the plate
    corners 5-8; ``SECT`` 1 is the seed's section and thickness. A wall has to
    stand vertically, which the plate corners do not, so WALL uses the seed's
    frame nodes 1-3 and node 30 added below node 3 (``_WALL_NODE``). Nothing
    else differs from the printed examples.
    """
    return {
        "TENSTR_cable": {"TYPE": "TENSTR", "MATL": 1, "SECT": 1, "NODE": [21, 22],
                         "ANGLE": 0, "STYPE": 3, "TENS": 0.5, "CABLE": 1},
        "COMPTR_truss": {"TYPE": "COMPTR", "MATL": 1, "SECT": 1, "NODE": [21, 22],
                         "ANGLE": 0, "STYPE": 1, "TENS": 27, "T_LIMIT": -15,
                         "T_bLMT": True},
        "PLATE": {"TYPE": "PLATE", "MATL": 1, "SECT": 1, "NODE": [5, 6, 7, 8],
                  "ANGLE": 0, "STYPE": 1},
        "WALL": {"TYPE": "WALL", "MATL": 1, "SECT": 1, "NODE": [1, 30, 3, 2],
                 "STYPE": 1, "WALL": 1, "W_CON": 0, "W_TYPE": 0},
    }


def elem_subtype_rows(client: MidasClient, checkpoint: str, extension: str) -> dict[str, Any]:
    """Which of /db/ELEM's per-type rows marked Required a request must carry.

    Each supplementary table marks STYPE Required, and the Cable and Wall
    tables mark more; the Cable Request Body itself omits the Required
    NON_LEN, and the harness seed has always posted a PLATE without STYPE.
    Each probe sends one printed example with at most one of those rows
    removed; ``PLSTRS`` is the PLATE example with TYPE changed, because the
    section prints no Plane Stress example.
    """
    examples = _elem_examples()
    probes: list[tuple[str, dict[str, Any]]] = []
    for label, record in examples.items():
        probes.append((f"{label}_as_printed", record))
        required = {"TENSTR_cable": ("STYPE", "CABLE"), "COMPTR_truss": ("STYPE",),
                    "PLATE": ("STYPE",), "WALL": ("STYPE", "WALL", "W_CON")}[label]
        for key in required:
            probes.append((f"{label}_without_{key}",
                           {k: v for k, v in record.items() if k != key}))
    plane = dict(examples["PLATE"], TYPE="PLSTRS")
    probes.append(("PLSTRS_with_STYPE", plane))
    probes.append(("PLSTRS_without_STYPE", {k: v for k, v in plane.items() if k != "STYPE"}))
    results: dict[str, Any] = {}
    for label, record in probes:
        doc.new_project(client=client)
        _seed_model(client)
        setup = (_raw(client, "POST", "/db/NODE", {"Assign": _WALL_NODE})
                 if record["TYPE"] == "WALL" else None)
        results[label] = {
            "sent": record,
            "setup": setup,
            "post": _raw(client, "POST", "/db/ELEM", {"Assign": {10: record}}),
            "get": _raw(client, "GET", "/db/ELEM/10"),
        }
        doc.save_as(f"{checkpoint}-{label}.{extension}", client=client)
    return results


def _spfc_code_examples() -> dict[str, dict[str, Any]]:
    """09_DB_Dynamic_Loads.md section 1's design-code Request Bodies, as printed.

    The KDS, IBC and EURO bodies print no ``CALC_OPT``, and without it or an
    ``aFUNC`` the server refuses a design spectrum (MD-15), so ``CALC_OPT:
    True`` - the documented way to have the server build the curve - is the
    one field added to those three.
    """
    common = {"iTYPE": 1, "iMETHOD": 0, "SCALE": 1, "GRAV": 9.806, "DRATIO": 0.05}
    return {
        "KDS2019": dict(common, NAME="KDS_2019_func",
                        STR={"SPEC_CODE": "KDS(41-17-00:2019)"},
                        OPT={"SC_": 2, "iSEISZONE": 0},
                        VAL={"aSRA": [0.22, 0.154], "aSCP": [1.0, 1.5], "PERIOD": 4.0,
                             "IE": 1.2, "R_": 5.0, "ZONEFACTOR": 0.22},
                        CALC_OPT=True),
        "IBC2012": dict(common, NAME="IBC2012_func", STR={"SPEC_CODE": "IBC2012"},
                        OPT={"SC_": 2},
                        VAL={"aSRA": [0.5, 0.2], "aSCP": [1.0, 1.5], "PERIOD": 4.0,
                             "IE": 1.0, "R_": 5.0},
                        CALC_OPT=True),
        "EURO2004": dict(common, NAME="EURO2004_func", STR={"SPEC_CODE": "EURO2004"},
                         OPT={"SPECTYPE": 1, "GROUTYPE": 1, "NATIONALANNEX": "EN"},
                         VAL={"ag": 0.25, "PERIOD": 4.0, "IE": 1.0},
                         CALC_OPT=True),
        "CH2010": dict(common, NAME="China(GB50011-10)",
                       STR={"SPEC_CODE": "CH2010", "SFI": "0.10g", "SC_": "II", "EQ_": "MIDDLE"},
                       OPT={"NSC": 1, "nLForce": 0},
                       VAL={"aTG": [0.4, 0, 0], "DP": 0.05, "MaxEQ": 0.23, "PERIOD": 6},
                       CALC_OPT=True),
        "JPN2000": dict(common, NAME="JP2000", STR={"SPEC_CODE": "JPN2000"},
                        OPT={"iSEISZONEFACTOR": 2, "SOILCLASS": 1},
                        VAL={"PERIOD": 6, "CO": 0.2}, CALC_OPT=True),
        "TAIWAN2022": dict(common, NAME="Taiwan(2022)", STR={"SPEC_CODE": "TAIWAN(2022)"},
                           OPT={"SOILCLASS": 0, "iSEISZONE": 1, "iSPECTYPE": 0, "iSPECUSE": 1,
                                "iSUBZONE": 0},
                           VAL={"aSRA": [0.5, 0.3, 0.7, 0.4], "aSRA_T": [0.6, 0.8, 1.6, 1.6],
                                "aNSF": [0.8, 0.45, 1, 0.6], "aSMF": [1, 1, 1, 1],
                                "DP": 5, "PERIOD": 6, "IF": 1, "SMFACTOR": 1, "RMFACTOR": 1.6,
                                "FUNDAMENTAL_PERIOD": 0.09},
                           CALC_OPT=True),
        "IS1893_2016": dict(common, NAME="IS1893(2016)", STR={"SPEC_CODE": "IS1893(2016)"},
                            OPT={"SOILCLASS": 0, "iSEISZONE": 0},
                            VAL={"DP": 5, "PERIOD": 6, "IE": 1, "R_": 3, "DPFAC": 1},
                            CALC_OPT=True),
        "NBC95": dict(common, NAME="NBC1995", STR={"SPEC_CODE": "NBC95"},
                      OPT={"ZA": 2, "ZV": 3}, VAL={"PERIOD": 6, "V": 0.15}, CALC_OPT=True),
    }


_SPFC_USER_CURVE = [
    {"PERIOD": 0, "VALUE": 0.11}, {"PERIOD": 0.06, "VALUE": 0.308},
    {"PERIOD": 0.12, "VALUE": 0.308}, {"PERIOD": 0.3, "VALUE": 0.308},
    {"PERIOD": 0.36, "VALUE": 0.2567}, {"PERIOD": 0.6, "VALUE": 0.154},
    {"PERIOD": 1.2, "VALUE": 0.077},
]


def spfc_code_examples(client: MidasClient, checkpoint: str, extension: str) -> dict[str, Any]:
    """Where /db/SPFC stores each design code's STR/OPT/VAL members.

    The section's EURO2004 table and example put SPECTYPE, GROUTYPE and
    NATIONALANNEX in OPT and send ``VAL.ag``; GET /info declares the three in
    STR, as strings, and spells ``VAL.AG``. Each printed example is sent and
    the stored record read back - the whole table, because this endpoint
    renumbers a POSTed record - with ``aFUNC`` left out of the evidence.

    The first run of this probe sent ``CALC_OPT: true`` and blocked both
    products at the ``/doc/NEW`` after the first example (2026-09-22), most
    likely on a save-changes dialog. So no example sends ``CALC_OPT`` here:
    each carries the section's User Type ``aFUNC`` curve instead - the other
    way the section makes a spectrum valid - and all eight go into one
    document, so no ``/doc/NEW`` follows a code spectrum.
    """
    doc.new_project(client=client)
    _seed_model(client)
    results: dict[str, Any] = {}
    for index, (label, example) in enumerate(_spfc_code_examples().items(), start=1):
        record = {k: v for k, v in example.items() if k != "CALC_OPT"}
        record["aFUNC"] = _SPFC_USER_CURVE
        results[label] = {"sent": record,
                          "post": _raw(client, "POST", "/db/SPFC", {"Assign": {index: record}})}
    table = _raw(client, "GET", "/db/SPFC")
    body = table["body"].get("SPFC") if isinstance(table["body"], dict) else None
    for label, entry in results.items():
        name = entry["sent"]["NAME"]
        entry["stored"] = next(({k: v for k, v in item.items() if k != "aFUNC"}
                                for item in (body or {}).values() if item.get("NAME") == name), None)
    doc.save_as(f"{checkpoint}-examples.{extension}", client=client)
    return results


def spfc_euro_placement(client: MidasClient, checkpoint: str, extension: str) -> dict[str, Any]:
    """The EURO2004 Request Body, refused as printed, one change at a time.

    Printed, it answers ``Unknown Error`` on both products (case c3). The
    section puts SPECTYPE/GROUTYPE/NATIONALANNEX in OPT and sends ``VAL.ag``;
    GET /info spells ``VAL.AG`` and declares the three in STR. Each variant
    changes one of those; all go into one document with the User Type curve,
    as in c3, and no ``CALC_OPT``.
    """
    printed = {k: v for k, v in _spfc_code_examples()["EURO2004"].items() if k != "CALC_OPT"}
    printed["aFUNC"] = _SPFC_USER_CURVE
    upper = dict(printed, VAL={"AG": 0.25, "PERIOD": 4.0, "IE": 1.0})
    variants = {
        "printed": printed,
        "VAL_AG": upper,
        "without_OPT": {k: v for k, v in printed.items() if k != "OPT"},
        "without_OPT_VAL_AG": {k: v for k, v in upper.items() if k != "OPT"},
    }
    doc.new_project(client=client)
    _seed_model(client)
    results: dict[str, Any] = {}
    for index, (label, record) in enumerate(variants.items(), start=1):
        record = dict(record, NAME=f"EURO2004_{label}")
        results[label] = {"sent": record,
                          "post": _raw(client, "POST", "/db/SPFC", {"Assign": {index: record}})}
    table = _raw(client, "GET", "/db/SPFC")
    body = table["body"].get("SPFC") if isinstance(table["body"], dict) else None
    for entry in results.values():
        entry["stored"] = next(({k: v for k, v in item.items() if k != "aFUNC"}
                                for item in (body or {}).values()
                                if item.get("NAME") == entry["sent"]["NAME"]), None)
    doc.save_as(f"{checkpoint}-euro.{extension}", client=client)
    return results


def _this_examples() -> dict[str, dict[str, Any]]:
    """09_DB_Dynamic_Loads.md section 6's four Request Bodies, as printed."""
    return {
        "linear_modal": {
            "COMMON": {"NAME": "TH_Linear_Modal", "DESC": "선형 모달 시간이력", "iATYPE": 1,
                       "iAMETHOD": 1, "iTHTYPE": 1, "ENDTIME": 30.0, "INC": 0.01, "iOUT": 1,
                       "INITMETHOD": "INIT", "INITLOAD": 0, "bDVA": False, "bKEEP": False,
                       "iMDTYPE": 1},
            "DALL": 0.05,
        },
        "nonlinear_direct": {
            "COMMON": {"NAME": "TH_NL_Direct", "DESC": "비선형 직접적분 시간이력", "iATYPE": 2,
                       "iAMETHOD": 2, "iTHTYPE": 1, "ENDTIME": 20.0, "INC": 0.005, "iOUT": 2,
                       "iGEOM": 0, "INITMETHOD": "INIT", "INITLOAD": 0, "bDVA": False,
                       "bKEEP": False, "iMDTYPE": 2},
            "iNMM": 1, "bITER": True, "DMUPDATE": False,
        },
        "nonlinear_static_load": {
            "COMMON": {"NAME": "TH_NL_Static", "DESC": "비선형 정적 시간이력", "iATYPE": 2,
                       "iAMETHOD": 3, "ENDTIME": 10.0, "iISTEP": 100, "iOUT": 1, "iGEOM": 0,
                       "INITMETHOD": "INIT"},
            "bCUMULATE": True, "iINCCTRL": 0, "SCALE": 1, "bITER": True, "bCONV": True,
            "iMSTEP": 10, "iMAXITER": 10, "bDN": True, "DN": 0.001, "bFN": True, "FN": 0.001,
            "bEN": True, "EN": 0.001, "iRKM": 0, "dTOL": 1e-08, "bULSM": True, "ULSM": 5,
        },
        "nonlinear_static_disp": {
            "COMMON": {"NAME": "TH_NL_Static_Disp", "DESC": "", "iATYPE": 2, "iAMETHOD": 3,
                       "iISTEP": 1, "iOUT": 1, "iGEOM": 0, "INITLOAD": 0,
                       "INITMETHOD": "ORDER", "bSUBSEQ": True, "SUBSEQ": 1},
            "bCUMULATE": False, "iINCCTRL": 1, "iCTRL": 1, "TINC": 0.02, "MNODE": 1, "MDIR": 2,
            "bITER": True, "bCONV": True, "iMSTEP": 10, "iMAXITER": 10, "bDN": True,
            "DN": 0.001, "iRKM": 0, "dTOL": 1e-08, "bULSM": False, "ULSM": 5,
        },
    }


def this_examples(client: MidasClient, checkpoint: str, extension: str) -> dict[str, Any]:
    """Where /db/THIS stores each analysis mode's members, and what it needs.

    COMMON marks iTHTYPE Required, and both Nonlinear + Static bodies omit it.
    Each printed body is sent into one document and the table read back by
    NAME, because this endpoint renumbers a POSTed record.
    """
    doc.new_project(client=client)
    _seed_model(client)
    results: dict[str, Any] = {}
    for index, (label, record) in enumerate(_this_examples().items(), start=1):
        results[label] = {"sent": record,
                          "post": _raw(client, "POST", "/db/THIS", {"Assign": {index: record}})}
    table = _raw(client, "GET", "/db/THIS")
    body = table["body"].get("THIS") if isinstance(table["body"], dict) else None
    for entry in results.values():
        name = entry["sent"]["COMMON"]["NAME"]
        entry["stored"] = next((item for item in (body or {}).values()
                                if item.get("COMMON", {}).get("NAME") == name), None)
    doc.save_as(f"{checkpoint}-this.{extension}", client=client)
    return results


def _mvhl_country_examples() -> dict[str, tuple[str, dict[str, Any]]]:
    """08_DB_Moving_Loads.md section 10's country Request Bodies, as printed.

    Each is paired with the /db/MVCD CODE its country takes in section 1's
    CODE value table. Section 10's headings name a STANDARD_CODE per VEH_*
    object, but the Australia body sends ``"ROAD TRAFFIC"`` where its heading
    says ``"AUSTRALIA"``, and the KSCE-LSD15 and China user-defined bodies
    send no STANDARD_CODE at all, while every body sends an MVLD_CODE.
    """
    return {
        "ksce_standard": ("KSCE-LSD15", {
            "MVLD_CODE": 13, "VEHICLE_LOAD_NAME": "ST_KL-510TRK", "VEHICLE_LOAD_NUM": 1,
            "VEHICLE_TYPE_NAME": "KL-510TRK", "STANDARD_CODE": "KSCE-LSD15",
            "VEH_KSCE_LSD15": {
                "LOAD_TYPE": 0, "DYN_LOAD_ALLOWANCE": 25, "LENGTH_LANE": 0,
                "LENGTH_LANE_USER": 0, "CONVERT_DIST_LOAD": False,
                "POINT_ITEMS": [{"POINT_LOAD": 48, "POINT_DIST": 3.6},
                                {"POINT_LOAD": 135, "POINT_DIST": 1.2},
                                {"POINT_LOAD": 135, "POINT_DIST": 7.2},
                                {"POINT_LOAD": 192, "POINT_DIST": 0}],
            },
        }),
        "ksce_user": ("KSCE-LSD15", {
            "MVLD_CODE": 13, "VEHICLE_LOAD_NAME": "UD_Truck/Lane1", "VEHICLE_LOAD_NUM": 2,
            "USER_LOAD_TYPE": "Truck/Lane",
            "VEH_KSCE_LSD15": {
                "LOADED_LENGTH": 60, "W1": 12.7, "W2": 12.7, "EXP": 0.1,
                "DYN_LOAD_ALLOWANCE": 25, "LENGTH_LANE": 0, "LENGTH_LANE_USER": 1.5,
                "CONVERT_DIST_LOAD": True,
                "POINT_ITEMS": [{"POINT_LOAD": 100, "POINT_DIST": 0.2, "POINT_DIST2": 0.45}],
            },
        }),
        "canada": ("CANADA", {
            "MVLD_CODE": 8, "VEHICLE_LOAD_NAME": "CA(Auto)_CL-625Truck", "VEHICLE_LOAD_NUM": 1,
            "VEHICLE_TYPE_NAME": "CL-625Truck", "STANDARD_CODE": "CANADA",
            "VEH_CA": {"DYN_LOAD_ALLOWANCE": 0, "DYNA": {"DYNA_FACTOR": 0}},
        }),
        "australia": ("AUSTRALIA", {
            "MVLD_CODE": 14, "VEHICLE_LOAD_NAME": "AU(Road)_M1600", "VEHICLE_LOAD_NUM": 1,
            "VEHICLE_TYPE_NAME": "M1600", "STANDARD_CODE": "ROAD TRAFFIC",
            "VEH_AU": {"DYN_LOAD_ALLOWANCE": 0.3},
        }),
        "south_africa": ("SOUTH AFRICA", {
            "MVLD_CODE": 16, "VEHICLE_LOAD_NAME": "ZA(TMH7)_NA", "VEHICLE_LOAD_NUM": 1,
            "VEHICLE_TYPE_NAME": "TMH7", "STANDARD_CODE": "NA",
            "VEH_ZA": {"INCRE_LENGTH": False},
        }),
        "china": ("CHINA", {
            "MVLD_CODE": 3, "VEHICLE_LOAD_NAME": "CN_UD_Lane1", "VEHICLE_LOAD_NUM": 2,
            "USER_LOAD_TYPE": "Truck/Lane",
            "VEH_CN": {"TRUCK_TYPE": 0, "P_": 130, "QM": 10.5, "QQ": 7},
        }),
        "poland": ("POLAND", {
            "MVLD_CODE": 15, "VEHICLE_LOAD_NAME": "PL_VehicleK", "VEHICLE_LOAD_NUM": 1,
            "VEHICLE_TYPE_NAME": "Vehicle K", "STANDARD_CODE": "PN-85/S-10030 - RoadBridge",
            "VEH_PL": {"SEL_VEHICLE": "Vehicle K", "DYNAMIC_AMP_FACTOR": False},
        }),
    }


def mvhl_country_objects(client: MidasClient, checkpoint: str, extension: str) -> dict[str, Any]:
    """Which field selects a /db/MVHL record's VEH_* object.

    One document per country: select its /db/MVCD CODE, send the printed body,
    then two bodies that each change one field - the Australia body with its
    heading's ``"AUSTRALIA"`` for ``"ROAD TRAFFIC"``, and the China body under
    the Australia code, which asks whether MVLD_CODE or the model's code is
    what is checked. Each table is read back by VEHICLE_LOAD_NAME, because
    this endpoint renumbers a POSTed record.
    """
    examples = _mvhl_country_examples()
    heading_code = dict(examples["australia"][1], STANDARD_CODE="AUSTRALIA",
                        VEHICLE_LOAD_NAME="AU(Road)_M1600_heading")
    china_elsewhere = dict(examples["china"][1], VEHICLE_LOAD_NAME="CN_UD_Lane1_under_AU")
    documents: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for label, (code, record) in examples.items():
        documents.setdefault(code, []).append((label, record))
    documents["AUSTRALIA"] += [("australia_heading_code", heading_code),
                               ("china_under_australia", china_elsewhere)]
    results: dict[str, Any] = {}
    for code, records in documents.items():
        doc.new_project(client=client)
        results[code] = entry = {
            "mvcd": _raw(client, "POST", "/db/MVCD", {"Assign": {1: {"CODE": code}}}),
            "records": {},
        }
        for index, (label, record) in enumerate(records, start=1):
            entry["records"][label] = {
                "sent": record,
                "post": _raw(client, "POST", "/db/MVHL", {"Assign": {index: record}}),
            }
        table = _raw(client, "GET", "/db/MVHL")
        body = table["body"].get("MVHL") if isinstance(table["body"], dict) else None
        for item in entry["records"].values():
            item["stored"] = next((stored for stored in (body or {}).values()
                                   if stored.get("VEHICLE_LOAD_NAME")
                                   == item["sent"]["VEHICLE_LOAD_NAME"]), None)
        doc.save_as(f"{checkpoint}-{code.replace(' ', '_').lower()}.{extension}", client=client)
    return results


def mvhl_code_pairing(client: MidasClient, checkpoint: str, extension: str) -> dict[str, Any]:
    """The two c6 bodies that stored nothing, one field at a time.

    Poland's printed body answered ``""`` and stored nothing, the same answer
    c6's China body gave under the Australia code, which reads as an
    MVLD_CODE the model's /db/MVCD code does not own. So the Poland body is
    sent once per MVLD_CODE from 1 to 20, each under its own name. South
    Africa's answered ``Wrong Field``, which c6 got for a STANDARD_CODE value
    the server does not recognise, so that body is sent without STANDARD_CODE
    - a field it stores without, measured 2026-09-03.
    """
    examples = _mvhl_country_examples()
    plans = {
        "POLAND": [(f"poland_mvld_{code}", dict(examples["poland"][1], MVLD_CODE=code,
                                                 VEHICLE_LOAD_NAME=f"PL_VehicleK_{code}"))
                   for code in range(1, 21)],
        "SOUTH AFRICA": [("south_africa_without_standard_code",
                          {k: v for k, v in examples["south_africa"][1].items()
                           if k != "STANDARD_CODE"})],
    }
    results: dict[str, Any] = {}
    for code, records in plans.items():
        doc.new_project(client=client)
        results[code] = entry = {
            "mvcd": _raw(client, "POST", "/db/MVCD", {"Assign": {1: {"CODE": code}}}),
            "records": {},
        }
        for index, (label, record) in enumerate(records, start=1):
            entry["records"][label] = {
                "sent": record,
                "post": _raw(client, "POST", "/db/MVHL", {"Assign": {index: record}}),
            }
        table = _raw(client, "GET", "/db/MVHL")
        body = table["body"].get("MVHL") if isinstance(table["body"], dict) else None
        for item in entry["records"].values():
            item["stored"] = next((stored for stored in (body or {}).values()
                                   if stored.get("VEHICLE_LOAD_NAME")
                                   == item["sent"]["VEHICLE_LOAD_NAME"]), None)
        doc.save_as(f"{checkpoint}-{code.replace(' ', '_').lower()}.{extension}", client=client)
    return results


def _divideelem_bodies() -> dict[str, dict[str, Any]]:
    """15_OPE.md section 2's bodies, and one axis set at a time around them.

    The Equal row says which axes each element type divides along (Frame=X,
    Planar=X,Y, Wall=X,Z, Solid=X,Y,Z); the Unequal and ParametricUnequal rows
    mark all three axes Required with no condition, while the section's own
    Planar Unequal body sends X and Y only. The seed model's element 1 is a
    3.2 m beam and element 4 a 4 m square plate, so the Frame Unequal body
    uses "2@1.0" where the printed Planar one's "2@2.5" would not fit.
    """
    def body(targets, elem_type, method, option):
        return {"TARGETS": targets, "DIVIDE": {"ELEM_TYPE": elem_type, "DIV_METHOD": method,
                                               "OPTION": option}}
    return {
        "frame_equal_printed": body([1], "Frame", "Equal", {"EQUAL_OPTION": {"NUM_X": 10}}),
        "frame_unequal_x": body([1], "Frame", "Unequal", {"UNEQUAL_OPTION": {"DIST_X": "2@1.0"}}),
        "frame_parametric_x": body([1], "Frame", "ParametricUnequal",
                                   {"PARAMETRIC_OPTION": {"RATIO_X": "3@0.3"}}),
        "planar_parametric_xy": body([4], "Planar", "ParametricUnequal",
                                     {"PARAMETRIC_OPTION": {"RATIO_X": "3@0.3", "RATIO_Y": "4@0.2"}}),
        "planar_parametric_x": body([4], "Planar", "ParametricUnequal",
                                    {"PARAMETRIC_OPTION": {"RATIO_X": "3@0.3"}}),
        "planar_unequal_printed": body([4], "Planar", "Unequal",
                                       {"UNEQUAL_OPTION": {"DIST_X": "2@2.5", "DIST_Y": "2@3.0"}}),
    }


def divideelem_axes(client: MidasClient, checkpoint: str, extension: str) -> dict[str, Any]:
    """Which axes /ope/DIVIDEELEM needs per element type, one document each.

    The element table is read before and after, because a division that did
    nothing and one that worked can answer alike.
    """
    results: dict[str, Any] = {}
    for label, argument in _divideelem_bodies().items():
        doc.new_project(client=client)
        _seed_model(client)
        before = _raw(client, "GET", "/db/ELEM")["body"].get("ELEM") or {}
        answer = _raw(client, "POST", "/ope/DIVIDEELEM", {"Argument": argument})
        after = _raw(client, "GET", "/db/ELEM")["body"].get("ELEM") or {}
        results[label] = {"sent": argument, "post": answer,
                          "elementsBefore": len(before), "elementsAfter": len(after)}
    doc.save_as(f"{checkpoint}-divide.{extension}", client=client)
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", choices=("gen", "civil"), required=True)
    parser.add_argument("--case", choices=("a1", "a2", "a3", "b1", "b2", "c1", "c2", "c3", "c4", "c5",
                                            "c6", "c7", "c8"),
                        default="a1")
    parser.add_argument("--out", required=True)
    harness_save_path.add_arguments(parser, waivable=False)
    args = parser.parse_args()
    harness_save_path.require(parser, args)
    client = MidasClient(product=args.product, timeout=60)
    extension = harness_save_path.PRODUCT_EXTENSION[args.product]
    # The stem rather than a finished path: this harness writes a checkpoint
    # per probe, each with its own suffix, and those files are the evidence.
    checkpoint = harness_save_path.checkpoint_prefix(
        args.save_dir, f"manual-feedback-{args.case}", args.product,
    )
    doc.save_as(f"{checkpoint}-before.{extension}", client=client)
    if args.case == "a1":
        result = memb_selection_typo(client, f"{checkpoint}-baseline.{extension}")
    elif args.case == "a2":
        result = sseis_code_space(client, f"{checkpoint}-baseline.{extension}")
    elif args.case == "a3":
        result = tdna_radius_types(client, checkpoint, extension)
    elif args.case == "b1":
        result = sseis_torsion_typos(client, checkpoint, extension)
    elif args.case == "c1":
        result = splc_gates(client, checkpoint, extension, args.product)
    elif args.case == "c2":
        result = elem_subtype_rows(client, checkpoint, extension)
    elif args.case == "c3":
        result = spfc_code_examples(client, checkpoint, extension)
    elif args.case == "c4":
        result = spfc_euro_placement(client, checkpoint, extension)
    elif args.case == "c5":
        result = this_examples(client, checkpoint, extension)
    elif args.case == "c6":
        result = mvhl_country_objects(client, checkpoint, extension)
    elif args.case == "c7":
        result = mvhl_code_pairing(client, checkpoint, extension)
    elif args.case == "c8":
        result = divideelem_axes(client, checkpoint, extension)
    else:
        result = missing_specification_fields(
            client, checkpoint, extension, args.product,
        )
    doc.save_as(f"{checkpoint}-after.{extension}", client=client)
    doc.new_project(client=client)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
