import json

import responses

from midas_nx.design.rc_kds.checks import (
    export_beam_check_report,
    export_brace_check_report,
    export_column_check_report,
    export_comprehensive_design_result_image,
    export_wall_check_report,
    get_beam_check_table,
    get_beam_design_forces_table,
    get_brace_check_table,
    get_brace_design_forces_table,
    get_column_check_table,
    get_column_design_forces_table,
    get_wall_check_table,
    perform_beam_check,
    perform_brace_check,
    perform_column_check,
    perform_wall_check,
)

BASE = "https://x.test:443/gen/DESIGN/RC/KDS-41-20-2022"


# === 54-56. RC Beam Check (BC-ANAL / BC-TABLE / BC-REPORT) ==================


@responses.activate
def test_perform_beam_check_sends_perform_type_all(gen_client):
    responses.add(responses.POST, f"{BASE}/BC-ANAL", json={"message": "success"}, status=200)
    perform_beam_check({"PERFORM_TYPE": "ALL"}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": {"PERFORM_TYPE": "ALL"}}


@responses.activate
def test_perform_beam_check_by_sections(gen_client):
    responses.add(responses.POST, f"{BASE}/BC-ANAL", json={"message": "success"}, status=200)
    perform_beam_check({"PERFORM_TYPE": "SECTIONS", "SECTIONS": [7]}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["SECTIONS"] == [7]


@responses.activate
def test_get_beam_check_table_sends_documented_argument_shape(gen_client):
    responses.add(
        responses.POST,
        f"{BASE}/BC-TABLE",
        json={"RC Beam Checking Result": {"HEAD": [], "DATA": []}},
        status=200,
    )
    get_beam_check_table(
        {
            "PRI_SORT": 1,
            "SECTIONS": [7],
            "RESULT": 0,
            "TABLE_NAME": "RC Beam Checking Result",
            "TABLE_TYPE": "MEMB",
            "COMPONENTS": ["MEMB", "SECT", "CHK_STR", "Rat-V"],
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "MEMB"
    assert body["SECTIONS"] == [7]


@responses.activate
def test_export_beam_check_report_sends_detail_positions(gen_client):
    responses.add(
        responses.POST,
        f"{BASE}/BC-REPORT",
        json={"SUCCESS": True, "FILE_PATH": "C:\\MIDAS\\Result\\detail.txt", "MESSAGE": ""},
        status=200,
    )
    export_beam_check_report(
        {
            "REPORT_TYPE": "MEMB",
            "CURRENT_MODE_MEMB": "Detail",
            "EXPORT_PATH": "C:\\MIDAS\\Result\\",
            "OUTPUT_NAME": "detail.txt",
            "ELEMS": {"KEYS": [1086]},
            "DETAIL_POSITIONS": {"END_I": False, "MID": False, "END_J": True},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["DETAIL_POSITIONS"] == {"END_I": False, "MID": False, "END_J": True}
    assert body["OUTPUT_NAME"] == "detail.txt"


# === 57-59. RC Column Check (CC-ANAL / CC-TABLE / CC-REPORT) ================


@responses.activate
def test_perform_column_check_by_elems(gen_client):
    responses.add(responses.POST, f"{BASE}/CC-ANAL", json={"message": "success"}, status=200)
    perform_column_check(
        {"PERFORM_TYPE": "ALL", "ELEMS": {"KEYS": [1059]}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["ELEMS"] == {"KEYS": [1059]}


@responses.activate
def test_get_column_check_table_sends_documented_argument_shape(gen_client):
    responses.add(
        responses.POST,
        f"{BASE}/CC-TABLE",
        json={"RC Column Checking Result": {"HEAD": [], "DATA": []}},
        status=200,
    )
    get_column_check_table(
        {
            "PRI_SORT": 1,
            "RESULT": 0,
            "TABLE_NAME": "RC Column Checking Result",
            "TABLE_TYPE": "MEMB",
            "COMPONENTS": ["MEMB", "SECT", "Rat_P", "Rat_M"],
            "ELEMS": {"KEYS": [1058]},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["ELEMS"] == {"KEYS": [1058]}
    assert body["COMPONENTS"] == ["MEMB", "SECT", "Rat_P", "Rat_M"]


@responses.activate
def test_export_column_check_report_sends_documented_argument_shape(gen_client):
    responses.add(
        responses.POST,
        f"{BASE}/CC-REPORT",
        json={"SUCCESS": True, "FILE_PATH": "C:\\MIDAS\\Result\\columnresult", "MESSAGE": ""},
        status=200,
    )
    export_column_check_report(
        {
            "REPORT_TYPE": "MEMB",
            "EXPORT_PATH": "C:\\MIDAS\\Result\\",
            "OUTPUT_NAME": "columnresult",
            "CURRENT_MODE_MEMB": "Graphic",
            "ELEMS": {"TO": "1058to1059"},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["ELEMS"] == {"TO": "1058to1059"}
    assert body["CURRENT_MODE_MEMB"] == "Graphic"


# === 60-62. RC Brace Check (BRC-ANAL / BRC-TABLE / BRC-REPORT) ==============


@responses.activate
def test_perform_brace_check_by_elems(gen_client):
    responses.add(responses.POST, f"{BASE}/BRC-ANAL", json={"message": "success"}, status=200)
    perform_brace_check(
        {"PERFORM_TYPE": "ALL", "ELEMS": {"KEYS": [883, 902]}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["ELEMS"]["KEYS"] == [883, 902]


@responses.activate
def test_get_brace_check_table_sends_documented_argument_shape(gen_client):
    responses.add(
        responses.POST,
        f"{BASE}/BRC-TABLE",
        json={"Result Table": {"HEAD": [], "DATA": []}},
        status=200,
    )
    get_brace_check_table(
        {
            "PRI_SORT": 1,
            "RESULT": 0,
            "TABLE_TYPE": "MEMB",
            "COMPONENTS": ["MEMB", "SECT", "CHK_STR", "Rat-V"],
            "ELEMS": {"KEYS": [883]},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "MEMB"
    assert body["ELEMS"] == {"KEYS": [883]}


@responses.activate
def test_export_brace_check_report_sends_documented_argument_shape(gen_client):
    responses.add(
        responses.POST,
        f"{BASE}/BRC-REPORT",
        json={"SUCCESS": True, "FILE_PATH": "C:\\MIDAS\\Result\\Graphic.jpg", "MESSAGE": ""},
        status=200,
    )
    export_brace_check_report(
        {
            "REPORT_TYPE": "MEMB",
            "CURRENT_MODE_MEMB": "Graphic",
            "EXPORT_PATH": "C:\\MIDAS\\Result\\",
            "OUTPUT_NAME": "Graphic.jpg",
            "ELEMS": {"KEYS": [883]},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["OUTPUT_NAME"] == "Graphic.jpg"


# === 63-65. RC Wall Check (WC-ANAL / WC-TABLE / WC-REPORT) — WALL_IDS+STORY =


@responses.activate
def test_perform_wall_check_sends_selections(gen_client):
    responses.add(responses.POST, f"{BASE}/WC-ANAL", json={"message": "success"}, status=200)
    perform_wall_check(
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
    assert body["SELECTIONS"][1]["WALL_IDS"] == {"TO": "10to20"}


@responses.activate
def test_perform_wall_check_with_no_selections_checks_all(gen_client):
    responses.add(responses.POST, f"{BASE}/WC-ANAL", json={"message": "success"}, status=200)
    perform_wall_check({}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": {}}


@responses.activate
def test_get_wall_check_table_sends_documented_argument_shape_and_parses_object_rows(gen_client):
    responses.add(
        responses.POST,
        f"{BASE}/WC-TABLE",
        json={
            "TABLE_NAME": "RC Wall Check Result",
            "TABLE_TYPE": "WID+STORY",
            "COMPONENTS": ["WID", "Story", "Wall Mark", "CHK_STR"],
            "DATA": [
                {"WID": 1, "Story": "3F", "Wall Mark": "W3F-01", "CHK_STR": "OK"},
                {"WID": 3, "Story": "3F", "Wall Mark": "W3F-03", "CHK_STR": "OK"},
            ],
        },
        status=200,
    )
    result = get_wall_check_table(
        {
            "TABLE_TYPE": "WID+STORY",
            "SELECTIONS": [
                {"WALL_IDS": {"KEYS": [1, 3]}, "STORY": ["3F"]},
                {"WALL_IDS": {"TO": "10to12"}, "STORY": ["3F"]},
            ],
            "PRI_SORT": 1,
            "RESULT": 0,
            "TABLE_NAME": "RC Wall Check Result",
            "COMPONENTS": ["WID", "Story", "Wall Mark", "CHK_STR"],
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "WID+STORY"
    assert body["SELECTIONS"][0]["WALL_IDS"] == {"KEYS": [1, 3]}
    # response is COMPONENTS+DATA(object rows), not HEAD/DATA(array rows)
    assert result["DATA"][0]["Wall Mark"] == "W3F-01"


@responses.activate
def test_export_wall_check_report_sends_documented_argument_shape(gen_client):
    responses.add(
        responses.POST,
        f"{BASE}/WC-REPORT",
        json={"SUCCESS": True, "FILE_PATH": "C:\\MIDAS\\Result\\RC_Wall_Report.jpg", "MESSAGE": ""},
        status=200,
    )
    export_wall_check_report(
        {
            "REPORT_TYPE": "WID+STORY",
            "CURRENT_MODE_WID_STORY": "Detail",
            "SELECTIONS": [{"WALL_IDS": {"KEYS": [1, 3]}, "STORY": ["3F"]}],
            "EXPORT_PATH": "C:\\MIDAS\\Report\\",
            "OUTPUT_NAME": "RC_Wall_Report.jpg",
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["CURRENT_MODE_WID_STORY"] == "Detail"
    assert body["REPORT_TYPE"] == "WID+STORY"


# === 66. RC Concrete Comprehensive Design Result (CDESIGN) ==================


@responses.activate
def test_export_comprehensive_design_result_image_sends_nested_result_graphic(gen_client):
    responses.add(responses.POST, f"{BASE}/CDESIGN", json={"message": "success"}, status=200)
    export_comprehensive_design_result_image(
        {
            "EXPORT_PATH": "C:\\MIDAS\\Images\\rc_design.jpg",
            "FIGURE_NAME": "RC Concrete Design Result",
            "WIDTH": 1600,
            "HEIGHT": 1000,
            "SET_HIDDEN": True,
            "RESULT_GRAPHIC": {
                "LOAD_CASE_COMB": {"TYPE": "CBC", "NAME": "cLCB1"},
                "COMPONENTS": "Combined",
                "REINFORCEMENT": True,
                "REINFORCEMENT_TYPE": "REBAR",
                "DISPLAY_MEMBERS": {"BEAM": True, "COLUMN": True, "BRACE": True, "WALL": True},
                "OUTPUT_SECT_LOCATION": {"OPT_MAX": True},
            },
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["RESULT_GRAPHIC"]["LOAD_CASE_COMB"] == {"TYPE": "CBC", "NAME": "cLCB1"}
    assert body["RESULT_GRAPHIC"]["DISPLAY_MEMBERS"]["WALL"] is True


# === 67-69. Column/Brace/Beam Design Forces — share one real endpoint =======


@responses.activate
def test_get_column_design_forces_table_sends_column_table_type(gen_client):
    responses.add(responses.POST, f"{BASE}/TABLE", json={"empty": {"HEAD": [], "DATA": []}}, status=200)
    get_column_design_forces_table(
        parts=["PartI"], node_elems={"KEYS": [915]}, client=gen_client
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "COLUMNDESIGNFORCES"
    assert body["NODE_ELEMS"] == {"KEYS": [915]}
    assert body["PARTS"] == ["PartI"]


@responses.activate
def test_get_brace_design_forces_table_sends_brace_table_type(gen_client):
    responses.add(responses.POST, f"{BASE}/TABLE", json={"empty": {"HEAD": [], "DATA": []}}, status=200)
    get_brace_design_forces_table(
        parts=["PartI"],
        unit={"FORCE": "KN", "DIST": "M"},
        styles={"FORMAT": "Fixed", "PLACE": 3},
        node_elems={"KEYS": [1039]},
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "BRACEDESIGNFORCES"
    assert body["UNIT"] == {"FORCE": "KN", "DIST": "M"}


@responses.activate
def test_get_beam_design_forces_table_sends_beam_table_type_and_components(gen_client):
    responses.add(
        responses.POST,
        f"{BASE}/TABLE",
        json={"C:\\MIDAS\\Result\\Beamresult.json": {"HEAD": [], "DATA": []}},
        status=200,
    )
    get_beam_design_forces_table(
        table_name="C:\\MIDAS\\Result\\Beamresult.json",
        components=["Index", "Memb", "Part", "LComName", "Type", "Fz", "Mx", "My(-)", "My(+)"],
        parts=["PartJ"],
        node_elems={"KEYS": [984]},
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "BEAMDESIGNFORCES"
    assert body["TABLE_NAME"] == "C:\\MIDAS\\Result\\Beamresult.json"
    assert body["COMPONENTS"][-2:] == ["My(-)", "My(+)"]


@responses.activate
def test_column_brace_beam_design_forces_all_hit_the_same_table_endpoint(gen_client):
    responses.add(responses.POST, f"{BASE}/TABLE", json={"empty": {"HEAD": [], "DATA": []}}, status=200)
    responses.add(responses.POST, f"{BASE}/TABLE", json={"empty": {"HEAD": [], "DATA": []}}, status=200)
    responses.add(responses.POST, f"{BASE}/TABLE", json={"empty": {"HEAD": [], "DATA": []}}, status=200)
    get_column_design_forces_table(client=gen_client)
    get_brace_design_forces_table(client=gen_client)
    get_beam_design_forces_table(client=gen_client)
    assert len(responses.calls) == 3
    assert {call.request.url for call in responses.calls} == {f"{BASE}/TABLE"}
    table_types = [json.loads(call.request.body)["Argument"]["TABLE_TYPE"] for call in responses.calls]
    assert table_types == ["COLUMNDESIGNFORCES", "BRACEDESIGNFORCES", "BEAMDESIGNFORCES"]
