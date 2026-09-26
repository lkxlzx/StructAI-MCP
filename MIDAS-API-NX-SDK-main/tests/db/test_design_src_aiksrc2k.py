import json

import pytest
import responses

from midas_nx.client import UnsupportedMethodError
from midas_nx.design.src_aiksrc2k import (
    SrcBeamSectionData,
    SrcColumnSectionData,
    SrcDefinitionOfFrame,
    SrcDesignCode,
    SrcDesignCodeOption,
    SrcEffectiveLengthFactor,
    SrcEquivalentMomentCorrectionFactor,
    SrcLimitingSlendernessRatio,
    SrcLiveLoadReductionFactor,
    SrcLoadContributionForNonlinearLoadCase,
    SrcMemberAssignment,
    SrcModifyLiveLoadReductionFactor,
    SrcModifyMaterial,
    SrcModifyMemberType,
    SrcMomentMagnifier,
    SrcScaleUpFactorForEarthquake,
    SrcSeismicLoadCombinationType,
    SrcUnbracedLength,
    export_src_beam_check_report,
    export_src_column_check_report,
    get_src_beam_check_table,
    get_src_beam_design_forces_table,
    get_src_column_check_table,
    get_src_column_design_forces_table,
    perform_src_beam_check,
    perform_src_column_check,
    perform_src_optimal_design,
)

BASE = "https://x.test:443/gen/DESIGN/SRC/AIK-SRC2K"


# === Group 1: 설계 코드·일반 설정 ===


@responses.activate
def test_design_code_update_sends_documented_assign_shape(gen_client):
    responses.add(responses.PUT, f"{BASE}/DSRC", json={}, status=200)
    SrcDesignCode.update({1: {"DGNCODE": "AIK-SRC2K"}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["DGNCODE"] == "AIK-SRC2K"


@responses.activate
def test_design_code_get_raises_before_any_http_call(gen_client):
    with pytest.raises(UnsupportedMethodError):
        SrcDesignCode.get(client=gen_client)
    assert len(responses.calls) == 0


@responses.activate
def test_design_code_option_update_sends_documented_assign_shape(gen_client):
    responses.add(responses.PUT, f"{BASE}/DCO", json={}, status=200)
    SrcDesignCodeOption.update(
        {1: {"DGNCODE": "AIK-SRC2K", "SEISMIC": True}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["SEISMIC"] is True


@responses.activate
def test_design_code_option_create_raises_before_any_http_call(gen_client):
    with pytest.raises(UnsupportedMethodError):
        SrcDesignCodeOption.create({1: {"DGNCODE": "AIK-SRC2K"}}, client=gen_client)
    assert len(responses.calls) == 0


@responses.activate
def test_definition_of_frame_update_sends_documented_assign_shape(gen_client):
    responses.add(responses.PUT, f"{BASE}/DCTL", json={}, status=200)
    SrcDefinitionOfFrame.update(
        {1: {"FRAMEX": "Braced Non-sway", "FRAMEY": "Braced Non-sway", "bAUTOKF": True, "DT": "XZ"}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["DT"] == "XZ"


@responses.activate
def test_live_load_reduction_factor_update_sends_reduction_data(gen_client):
    responses.add(responses.PUT, f"{BASE}/LLRF", json={}, status=200)
    SrcLiveLoadReductionFactor.update(
        {
            1: {
                "CALC_RULE": 0,
                "APPLIED_COMP": ["AXIAL", "SHEAR", "MOMENTS", "ALL"],
                "LIVE_LOAD_CASES": ["LL2"],
                "REDUCTION_DATA": [
                    {
                        "STORY": "B2",
                        "XMIN": -7.5,
                        "XMAX": 1.15,
                        "YMIN": -7.45,
                        "YMAX": -7.45,
                        "RANGE_MAX": 0.9,
                        "RANGE_MIN": 0.6,
                    },
                    {"STORY": "B2", "XMIN": -7.5, "XMAX": 1.15, "YMIN": -7.45, "YMAX": -7.45},
                ],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    data = json.loads(sent.body)["Assign"]["1"]["REDUCTION_DATA"]
    assert data[0]["RANGE_MAX"] == 0.9
    assert "RANGE_MAX" not in data[1]


@responses.activate
def test_load_contribution_get_only_endpoint_rejects_create(gen_client):
    with pytest.raises(UnsupportedMethodError):
        SrcLoadContributionForNonlinearLoadCase.create({2: {"NAME": "NgLCB6"}}, client=gen_client)
    with pytest.raises(UnsupportedMethodError):
        SrcLoadContributionForNonlinearLoadCase.update({2: {"NAME": "NgLCB6"}}, client=gen_client)
    assert len(responses.calls) == 0


@responses.activate
def test_load_contribution_delete_uses_per_id_urls(gen_client):
    for item_id in (2, 3):
        responses.add(responses.DELETE, f"{BASE}/LCTB/{item_id}", json={}, status=200)

    SrcLoadContributionForNonlinearLoadCase.delete([2, 3], client=gen_client)

    assert [call.request.url for call in responses.calls] == [
        f"{BASE}/LCTB/2", f"{BASE}/LCTB/3",
    ]


@responses.activate
def test_unbraced_length_create_partial_fields(gen_client):
    responses.add(responses.POST, f"{BASE}/LENG", json={}, status=200)
    SrcUnbracedLength.create(
        {868: {"LY": 1, "LZ": 1, "LB": 1, "bNOTUSE": True, "LT": 1}, 874: {"LY": 1, "LZ": 1}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["868"]["bNOTUSE"] is True


@responses.activate
def test_effective_length_factor_create(gen_client):
    responses.add(responses.POST, f"{BASE}/KFAC", json={}, status=200)
    SrcEffectiveLengthFactor.create(
        {868: {"Ky": 1}, 874: {"Ky": 2, "Kz": 2}, 885: {"Kz": 3, "Kt": 3}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["885"]["Kt"] == 3


@responses.activate
def test_limiting_slenderness_ratio_create(gen_client):
    responses.add(responses.POST, f"{BASE}/LTSR", json={}, status=200)
    SrcLimitingSlendernessRatio.create(
        {868: {"COMP": 300, "TENS": 200}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["868"]["COMP"] == 300


@responses.activate
def test_equivalent_moment_correction_factor_create(gen_client):
    responses.add(responses.POST, f"{BASE}/CMFT", json={}, status=200)
    SrcEquivalentMomentCorrectionFactor.create(
        {868: {"OPT_AUTO": True}, 885: {"CMY": 0.7, "CMZ": 0.6}}, client=gen_client
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]
    assert body["868"] == {"OPT_AUTO": True}
    assert body["885"]["CMZ"] == 0.6


@responses.activate
def test_moment_magnifier_create(gen_client):
    responses.add(responses.POST, f"{BASE}/FMAG", json={}, status=200)
    SrcMomentMagnifier.create(
        {868: {"B1Y_DELTA_BY": 1.1, "B1Z_DELTA_BZ": 1.2}, 874: {"B2Y_DELTA_SY": 1.3, "B2Z_DELTA_SZ": 1.4}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["874"]["B2Z_DELTA_SZ"] == 1.4


@responses.activate
def test_modify_live_load_reduction_factor_create(gen_client):
    responses.add(responses.POST, f"{BASE}/MLLR", json={}, status=200)
    SrcModifyLiveLoadReductionFactor.create(
        {
            868: {"COMPONENTS": {"AXIAL": False, "MOMENT": True, "SHEAR": False}},
            874: {"FACTOR": 0.9, "COMPONENTS": {"AXIAL": True, "SHEAR": False}},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["874"]["FACTOR"] == 0.9


@responses.activate
def test_scale_up_factor_for_earthquake_create(gen_client):
    responses.add(responses.POST, f"{BASE}/SUEQ", json={}, status=200)
    SrcScaleUpFactorForEarthquake.create(
        {
            868: {
                "LC_AXIAL": 1.2,
                "LC_MOMENT": 1.2,
                "LC_SHEAR": 1.2,
                "LCOM_AXIAL": 1.2,
                "LCOM_MOMENT": 1.2,
                "LCOM_SHEAR": 1.2,
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["868"]["LC_SHEAR"] == 1.2


@responses.activate
def test_modify_member_type_create(gen_client):
    responses.add(responses.POST, f"{BASE}/MBTP", json={}, status=200)
    SrcModifyMemberType.create(
        {868: {"TYPE": "BRACE"}, 874: {"TYPE": "COLUMN"}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["874"]["TYPE"] == "COLUMN"


@responses.activate
def test_seismic_load_combination_type_create(gen_client):
    responses.add(responses.POST, f"{BASE}/EQCT", json={}, status=200)
    SrcSeismicLoadCombinationType.create(
        {868: {"TYPE": "Special Seismic Loads"}, 874: {"TYPE": "Vertical Seismic Forces"}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["874"]["TYPE"] == "Vertical Seismic Forces"


@responses.activate
def test_member_assignment_update_sends_documented_assign_shape(gen_client):
    responses.add(responses.PUT, f"{BASE}/MEMB", json={}, status=200)
    SrcMemberAssignment.update(
        {1: {"AELEM": [859, 860, 861], "bREVERSE": True}, 2: {"AELEM": [883, 868], "bREVERSE": True}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["2"]["bREVERSE"] is True


@responses.activate
def test_member_assignment_create_raises_before_any_http_call(gen_client):
    with pytest.raises(UnsupportedMethodError):
        SrcMemberAssignment.create({1: {"AELEM": [1]}}, client=gen_client)
    assert len(responses.calls) == 0


# === Group 2: 검토 수행/테이블/리포트/최적설계 (POST-action) ===


@responses.activate
def test_perform_src_beam_check_sends_perform_type_all(gen_client):
    responses.add(responses.POST, f"{BASE}/BC-ANAL", json={"message": "success"}, status=200)
    perform_src_beam_check(
        {"PERFORM_TYPE": "ALL", "ELEMS": {"KEYS": [922]}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": {"PERFORM_TYPE": "ALL", "ELEMS": {"KEYS": [922]}}}


@responses.activate
def test_get_src_beam_check_table_sends_documented_argument_shape(gen_client):
    responses.add(responses.POST, f"{BASE}/BC-TABLE", json={"Result Table": {}}, status=200)
    get_src_beam_check_table(
        {
            "TABLE_TYPE": "MEMB",
            "PRI_SORT": 1,
            "RESULT": 0,
            "COMPONENTS": ["MEMB", "SECT", "Span", "CHK"],
            "ELEMS": {"KEYS": [922]},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "MEMB"
    assert body["ELEMS"] == {"KEYS": [922]}


@responses.activate
def test_export_src_beam_check_report_sends_documented_argument_shape(gen_client):
    responses.add(
        responses.POST,
        f"{BASE}/BC-REPORT",
        json={"SUCCESS": True, "FILE_PATH": "C:\\MIDAS\\Result\\GRAPHIC.jpg", "MESSAGE": ""},
        status=200,
    )
    export_src_beam_check_report(
        {
            "REPORT_TYPE": "MEMB",
            "CURRENT_MODE_MEMB": "Graphic",
            "EXPORT_PATH": "C:\\MIDAS\\Result\\",
            "OUTPUT_NAME": "GRAPHIC.jpg",
            "ELEMS": {"KEYS": [922]},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["CURRENT_MODE_MEMB"] == "Graphic"
    assert body["OUTPUT_NAME"] == "GRAPHIC.jpg"


@responses.activate
def test_perform_src_column_check_by_sections(gen_client):
    responses.add(responses.POST, f"{BASE}/CC-ANAL", json={"message": "success"}, status=200)
    perform_src_column_check(
        {"PERFORM_TYPE": "SECTIONS", "SECTIONS": [4]}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["SECTIONS"] == [4]


@responses.activate
def test_get_src_column_check_table_sends_documented_argument_shape(gen_client):
    responses.add(responses.POST, f"{BASE}/CC-TABLE", json={"Result Table": {}}, status=200)
    get_src_column_check_table(
        {
            "TABLE_TYPE": "MEMB",
            "PRI_SORT": 1,
            "RESULT": 0,
            "COMPONENTS": ["CHK", "MEMB", "SECT", "COM", "SHR"],
            "ELEMS": {"KEYS": [1062]},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "MEMB"
    assert body["COMPONENTS"] == ["CHK", "MEMB", "SECT", "COM", "SHR"]


@responses.activate
def test_export_src_column_check_report_sends_documented_argument_shape(gen_client):
    responses.add(
        responses.POST,
        f"{BASE}/CC-REPORT",
        json={"SUCCESS": True, "FILE_PATH": "C:\\MIDAS\\Result\\Detail.txt", "MESSAGE": ""},
        status=200,
    )
    export_src_column_check_report(
        {
            "REPORT_TYPE": "MEMB",
            "CURRENT_MODE_MEMB": "Detail",
            "EXPORT_PATH": "C:\\MIDAS\\Result\\",
            "OUTPUT_NAME": "Detail.txt",
            "ELEMS": {"KEYS": [1062]},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["CURRENT_MODE_MEMB"] == "Detail"
    assert "DETAIL_POSITIONS" not in body


@responses.activate
def test_perform_src_optimal_design_sends_documented_argument_shape(gen_client):
    responses.add(
        responses.POST,
        "https://x.test:443/gen/TEMP/DESIGN/SRC/AIK-SRC2K/OCHECK",
        json={"ODSR_RUN_RESPONSE": {"HEAD": [], "DATA": []}},
        status=200,
    )
    perform_src_optimal_design(
        {
            "SECT_LIST": [{"SECT_NO": 4, "SECT_DB": "KS21", "ALLOW": 1}],
            "OUTPUT": {
                "GRAPH_MAX_RATIO": True,
                "TEXT_REPORT": True,
                "MODEL_UPDATE": True,
                "EXPORT_PATH": "C:\\MIDAS\\Result\\",
            },
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["SECT_LIST"][0]["SECT_DB"] == "KS21"
    assert body["OUTPUT"]["EXPORT_PATH"] == "C:\\MIDAS\\Result\\"


@responses.activate
def test_get_src_beam_design_forces_table_sends_documented_argument_shape(gen_client):
    responses.add(responses.POST, f"{BASE}/TABLE", json={"empty": {}}, status=200)
    get_src_beam_design_forces_table(
        components=["Memb", "Part", "LComName", "Type", "Fz", "Mx", "My(+)", "My(-)"],
        parts=["PartI", "PartJ"],
        node_elems={"KEYS": [926]},
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "SRCBEAMDESIGNFORCES"
    assert body["NODE_ELEMS"] == {"KEYS": [926]}


@responses.activate
def test_get_src_column_design_forces_table_sends_documented_argument_shape(gen_client):
    responses.add(responses.POST, f"{BASE}/TABLE", json={"empty": {}}, status=200)
    get_src_column_design_forces_table(
        components=[],
        parts=["PartI", "PartJ"],
        node_elems={"KEYS": [1062]},
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "SRCCOLUMNDESIGNFORCES"
    assert body["PARTS"] == ["PartI", "PartJ"]


# === Group 3: 재료·단면·부재 ===


@responses.activate
def test_modify_material_update_standard_variant(gen_client):
    responses.add(responses.PUT, f"{BASE}/MATD", json={}, status=200)
    SrcModifyMaterial.update(
        {
            5: {
                "STEEL": {"CODE": "Standard", "STANDARD_CODE": "KS22(S)", "GRADE": "SM275TMC"},
                "CONCRETE": {"CODE": "Standard", "STANDARD_CODE": "KS19(RC)", "GRADE": "C65"},
                "REINFORCEMENT": {
                    "CODE": "Standard",
                    "STANDARD_CODE": "KS19(RC)",
                    "MAIN_REBAR_GRADE": "SD700",
                    "SUB_REBAR_GRADE": "SD700",
                },
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]["5"]
    assert body["STEEL"]["GRADE"] == "SM275TMC"
    assert body["CONCRETE"]["GRADE"] == "C65"
    assert body["REINFORCEMENT"]["MAIN_REBAR_GRADE"] == "SD700"


@responses.activate
def test_modify_material_create_raises_before_any_http_call(gen_client):
    with pytest.raises(UnsupportedMethodError):
        SrcModifyMaterial.create({5: {"STEEL": {"CODE": "Standard"}}}, client=gen_client)
    assert len(responses.calls) == 0


@responses.activate
def test_column_section_data_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, f"{BASE}/MCRD", json={}, status=200)
    SrcColumnSectionData.create(
        {
            4: {
                "MAIN_BAR": {
                    "USE_REBAR_SPACE": True,
                    "REBAR_SPACE": 0,
                    "NUM": 4,
                    "NAME": "D4",
                    "ROW": 2,
                    "DO": 0.05,
                },
                "SHEAR_BAR": {"NAME": "D4", "DIST": 300},
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]["4"]
    assert body["MAIN_BAR"]["NUM"] == 4
    assert body["SHEAR_BAR"]["DIST"] == 300


@responses.activate
def test_beam_section_data_create_sends_bar_sectors(gen_client):
    responses.add(responses.POST, f"{BASE}/MRBD", json={}, status=200)
    SrcBeamSectionData.create(
        {
            3: {
                "DT": 0.1,
                "DB": 0.1,
                "SHEAR_BAR": "D4",
                "BAR_SECTOR_I": {
                    "STIRRUP_SPACE": 150,
                    "STIRRUP_NUM": 2,
                    "TOP": {"LAYER1": {"NAME": "D32", "NUM": 2}, "LAYER2": {"NAME": "D32", "NUM": 2}},
                    "BOT": {"LAYER1": {"NAME": "D35", "NUM": 1}, "LAYER2": {"NAME": "D35", "NUM": 3}},
                },
                "BAR_SECTOR_M": {
                    "STIRRUP_SPACE": 150,
                    "TOP": {"LAYER1": {"NAME": "D43", "NUM": 1}},
                    "BOT": {"LAYER1": {"NAME": "D43", "NUM": 2}},
                },
                "BAR_SECTOR_J": {
                    "STIRRUP_SPACE": 150,
                    "TOP": {"LAYER1": {"NAME": "D51", "NUM": 2}},
                    "BOT": {"LAYER1": {"NAME": "D43", "NUM": 2}},
                },
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]["3"]
    assert body["BAR_SECTOR_I"]["TOP"]["LAYER1"]["NAME"] == "D32"
    assert body["BAR_SECTOR_M"]["STIRRUP_SPACE"] == 150
    assert body["SHEAR_BAR"] == "D4"
