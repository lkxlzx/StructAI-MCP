import json

import responses

from midas_nx.design.rc_kds.design_forces import (
    export_beam_design_report,
    export_brace_design_report,
    export_column_design_report,
    export_haunched_beam_design_report,
    export_wall_design_report,
    get_beam_design_table,
    get_brace_design_table,
    get_column_design_table,
    get_haunched_beam_design_table,
    get_wall_design_table,
    perform_beam_design,
    perform_brace_design,
    perform_column_design,
    perform_haunched_beam_design,
    perform_wall_design,
)

BASE = "https://x.test:443/gen/DESIGN/RC/KDS-41-20-2022"


# === 39-41. Beam ===


@responses.activate
def test_perform_beam_design_by_elems(gen_client):
    responses.add(responses.POST, f"{BASE}/BD-ANAL", json={"message": "success"}, status=200)
    perform_beam_design(
        {"PERFORM_TYPE": "ELEMS", "ELEMS": {"KEYS": [79, 80, 81]}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {"PERFORM_TYPE": "ELEMS", "ELEMS": {"KEYS": [79, 80, 81]}}
    }


@responses.activate
def test_get_beam_design_table_sends_documented_argument_shape(gen_client):
    responses.add(
        responses.POST, f"{BASE}/BD-TABLE", json={"RC Beam Design Result": {}}, status=200
    )
    get_beam_design_table(
        {
            "TABLE_TYPE": "MEMB",
            "PRI_SORT": 1,
            "RESULT": 0,
            "TABLE_NAME": "RC Beam Design Result",
            "COMPONENTS": [
                "MEMB", "SECT", "Span", "Section", "Bc", "Hc", "bf", "hf",
                "fck", "fy", "fys", "POS", "N(-)/Mu", "LCB_NegMu", "AsTop",
                "Rebar_Top", "P(+)/Mu", "LCB_PosMu", "AsBot", "Rebar_Bot",
                "Vu", "LCB_Vu", "AsV", "Stirrup", "CHK",
            ],
            "ELEMS": {"KEYS": [859, 860]},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "MEMB"
    assert body["ELEMS"] == {"KEYS": [859, 860]}


@responses.activate
def test_export_beam_design_report_sends_detail_positions(gen_client):
    responses.add(
        responses.POST,
        f"{BASE}/BD-REPORT",
        json={"SUCCESS": True, "FILE_PATH": "C:\\MIDAS\\Result\\out.jpg", "MESSAGE": ""},
        status=200,
    )
    export_beam_design_report(
        {
            "REPORT_TYPE": "MEMB",
            "CURRENT_MODE_MEMB": "Detail",
            "EXPORT_PATH": "C:\\MIDAS\\Result\\",
            "OUTPUT_NAME": "out.jpg",
            "ELEMS": {"KEYS": [79]},
            "DETAIL_POSITIONS": {"END_I": True, "MID": True, "END_J": False},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["CURRENT_MODE_MEMB"] == "Detail"
    assert body["DETAIL_POSITIONS"] == {"END_I": True, "MID": True, "END_J": False}


# === 42-44. Column ===


@responses.activate
def test_perform_column_design_all(gen_client):
    responses.add(responses.POST, f"{BASE}/CD-ANAL", json={"message": "success"}, status=200)
    perform_column_design(
        {"PERFORM_TYPE": "ALL", "ELEMS": {"KEYS": [105, 915]}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["PERFORM_TYPE"] == "ALL"


@responses.activate
def test_get_column_design_table_sends_documented_argument_shape(gen_client):
    responses.add(responses.POST, f"{BASE}/CD-TABLE", json={"Result Table": {}}, status=200)
    get_column_design_table(
        {"TABLE_TYPE": "MEMB", "PRI_SORT": 1, "RESULT": 0}, client=gen_client
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "MEMB"
    assert body["RESULT"] == 0


@responses.activate
def test_export_column_design_report_sends_pmcurve_mode(gen_client):
    responses.add(
        responses.POST,
        f"{BASE}/CD-REPORT",
        json={"SUCCESS": True, "FILE_PATH": "C:\\MIDAS\\Resultname", "MESSAGE": ""},
        status=200,
    )
    export_column_design_report(
        {
            "REPORT_TYPE": "MEMB",
            "CURRENT_MODE_MEMB": "PMCurve",
            "EXPORT_PATH": "C:\\MIDAS\\Result\\",
            "OUTPUT_NAME": "pm.jpg",
            "ELEMS": {"KEYS": [291, 292]},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["CURRENT_MODE_MEMB"] == "PMCurve"
    assert body["ELEMS"] == {"KEYS": [291, 292]}


# === 45-47. Brace ===


@responses.activate
def test_perform_brace_design_by_sections(gen_client):
    responses.add(responses.POST, f"{BASE}/BRD-ANAL", json={"message": "success"}, status=200)
    perform_brace_design(
        {"PERFORM_TYPE": "SECTIONS", "SECTIONS": ["G1"]}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["SECTIONS"] == ["G1"]


@responses.activate
def test_get_brace_design_table_sends_documented_argument_shape(gen_client):
    responses.add(
        responses.POST, f"{BASE}/BRD-TABLE", json={"RC Brace Design Result": {}}, status=200
    )
    get_brace_design_table(
        {
            "TABLE_TYPE": "MEMB",
            "SECTIONS": [3],
            "PRI_SORT": 1,
            "RESULT": 0,
            "TABLE_NAME": "RC Brace Design Result",
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["SECTIONS"] == [3]
    assert body["TABLE_NAME"] == "RC Brace Design Result"


@responses.activate
def test_export_brace_design_report_sends_pmcurve_mode(gen_client):
    responses.add(
        responses.POST,
        f"{BASE}/BRD-REPORT",
        json={"SUCCESS": True, "FILE_PATH": "C:\\MIDAS\\Result\\pm.jpg", "MESSAGE": ""},
        status=200,
    )
    export_brace_design_report(
        {
            "REPORT_TYPE": "MEMB",
            "CURRENT_MODE_MEMB": "PMCurve",
            "EXPORT_PATH": "C:\\MIDAS\\Result\\",
            "OUTPUT_NAME": "pm.jpg",
            "ELEMS": {"KEYS": [789]},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["CURRENT_MODE_MEMB"] == "PMCurve"
    assert body["OUTPUT_NAME"] == "pm.jpg"


# === 48-50. Wall ===


@responses.activate
def test_perform_wall_design_sends_wall_ids_and_story_selections(gen_client):
    responses.add(responses.POST, f"{BASE}/WD-ANAL", json={"message": "success"}, status=200)
    perform_wall_design(
        {
            "SELECTIONS": [
                {"WALL_IDS": {"KEYS": [1, 2, 3]}, "STORY": ["B1F", "1F"]},
                {"WALL_IDS": {"TO": "10to20"}, "STORY": ["2F", "3F"]},
            ]
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["SELECTIONS"][0]["WALL_IDS"] == {"KEYS": [1, 2, 3]}
    assert body["SELECTIONS"][1]["STORY"] == ["2F", "3F"]


@responses.activate
def test_get_wall_design_table_sends_selections_and_returns_rows_shape(gen_client):
    responses.add(
        responses.POST,
        f"{BASE}/WD-TABLE",
        json={
            "status": "success",
            "data": {
                "COMPONENTS": ["WID", "Story", "CHK"],
                "ROWS": [{"WID": 1, "Story": "3F", "CHK": "OK"}],
            },
        },
        status=200,
    )
    result = get_wall_design_table(
        {
            "TABLE_TYPE": "WID+STORY",
            "SELECTIONS": [
                {"WALL_IDS": {"KEYS": [1, 3]}, "STORY": ["3F"]},
                {"WALL_IDS": {"TO": "10to12"}, "STORY": ["3F"]},
            ],
            "PRI_SORT": 1,
            "RESULT": 0,
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "WID+STORY"
    assert "EXPORT_PATH" not in body
    assert result["data"]["ROWS"][0]["WID"] == 1


@responses.activate
def test_export_wall_design_report_sends_wid_story_mode(gen_client):
    responses.add(
        responses.POST,
        f"{BASE}/WD-REPORT",
        json={"SUCCESS": True, "FILE_PATH": "C:\\MIDAS\\Result\\result.jpg", "MESSAGE": ""},
        status=200,
    )
    export_wall_design_report(
        {
            "REPORT_TYPE": "WID+STORY",
            "CURRENT_MODE_WID_STORY": "Detail",
            "SELECTIONS": [
                {"WALL_IDS": {"KEYS": [101, 102]}, "STORY": ["1F", "2F"]},
                {"WALL_IDS": {"TO": "201to205"}, "STORY": ["3F"]},
            ],
            "EXPORT_PATH": "C:\\MIDAS\\Report\\",
            "OUTPUT_NAME": "RC_Wall_Report",
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["CURRENT_MODE_WID_STORY"] == "Detail"
    assert body["OUTPUT_NAME"] == "RC_Wall_Report"


# === 51-53. Haunched Beam ===


@responses.activate
def test_perform_haunched_beam_design_by_elems(gen_client):
    responses.add(responses.POST, f"{BASE}/HCD-ANAL", json={"message": "success"}, status=200)
    perform_haunched_beam_design({"ELEMS": {"KEYS": [1065, 1073]}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": {"ELEMS": {"KEYS": [1065, 1073]}}}


@responses.activate
def test_get_haunched_beam_design_table_sends_documented_argument_shape(gen_client):
    responses.add(responses.POST, f"{BASE}/HCD-TABLE", json={"Result Table": {}}, status=200)
    get_haunched_beam_design_table(
        {
            "RESULT": 0,
            "COMPONENTS": [
                "HCBM", "Section", "Bc-I", "Hc-I", "Bc-J", "Hc-J", "POS",
                "N(-)Mu", "LCB_NegMu", "AsTop", "Rebar_Top", "P(+)Mu",
                "LCB_PosMu", "AsBot", "Rebar_Bot", "Vu", "LCB_Vu", "AsV",
                "Stirrup", "CHK",
            ],
            "ELEMS": {"KEYS": [1065, 1073]},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["ELEMS"] == {"KEYS": [1065, 1073]}
    assert "TABLE_TYPE" not in body


@responses.activate
def test_export_haunched_beam_design_report_sends_fixed_graphic_mode(gen_client):
    responses.add(
        responses.POST,
        f"{BASE}/HCD-REPORT",
        json={"SUCCESS": True, "FILE_PATH": "C:\\MIDAS\\Result\\graphic", "MESSAGE": ""},
        status=200,
    )
    export_haunched_beam_design_report(
        {
            "CURRENT_MODE": "Graphic",
            "EXPORT_PATH": "C:\\MIDAS\\Result\\",
            "OUTPUT_NAME": "graphic",
            "ELEMS": {"KEYS": [1073]},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["CURRENT_MODE"] == "Graphic"
    assert "REPORT_TYPE" not in body
