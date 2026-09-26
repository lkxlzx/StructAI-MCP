import json

import pytest
import responses

from midas_nx.client import UnsupportedMethodError
from midas_nx.design.steel_kds import (
    BendingCoefficient,
    CombinedRatioCalculationMethodForCircularSection,
    DefinitionOfFrame,
    EffectiveLengthFactor,
    EquivalentMomentCorrectionFactor,
    HaunchedBeamAssignment,
    LimitingSlendernessRatio,
    LiveLoadReductionFactor,
    LoadContributionForNonlinearLoadCase,
    MemberAssignment,
    ModifyLiveLoadReductionFactor,
    ModifyMemberType,
    ModifySteelMaterial,
    MomentMagnifier,
    ScaleUpFactorForEarthquake,
    SeismicLoadCombinationType,
    SeismicLoadResistingSystemByMember,
    ServiceabilityParameters,
    SteelDesignCodeOption,
    SteelDesignCodeSelection,
    StrengthReductionFactors,
    UnbracedLength,
    UndergroundLoadCombinationType,
    export_steel_code_check_report,
    export_steel_design_result_image,
    get_steel_code_check_table,
    get_steel_member_design_forces_table,
    perform_steel_code_check,
)

BASE = "https://x.test:443/gen/DESIGN/STEEL/KDS-41-30-2022"


# --- 0. DSTL (Steel Design Code Selection) --------------------------------
# Added to the manual 2026-09-06; unlike everything else in this file, its URI
# does not carry the KDS-41-30-2022 prefix.


@responses.activate
def test_steel_design_code_selection_update_sends_documented_assign_shape(gen_client):
    responses.add(responses.PUT, "https://x.test:443/gen/DESIGN/STEEL/DSTL", json={}, status=200)
    SteelDesignCodeSelection.update({1: {"DGNCODE": "KDS 41 30 : 2022"}}, client=gen_client)
    sent = responses.calls[0].request
    assert sent.url == "https://x.test:443/gen/DESIGN/STEEL/DSTL"
    assert json.loads(sent.body) == {"Assign": {"1": {"DGNCODE": "KDS 41 30 : 2022"}}}


@responses.activate
def test_steel_design_code_selection_get_unwraps_the_dstl_key(gen_client):
    # The manual's GET example is keyed "DSTL" - unlike the RC counterpart's
    # "DCON". DbResource.items() unwraps by shape, so both work unchanged.
    responses.add(
        responses.GET,
        "https://x.test:443/gen/DESIGN/STEEL/DSTL",
        json={"DSTL": {"1": {"DGNCODE": "KDS 41 30 : 2022"}}},
        status=200,
    )
    assert SteelDesignCodeSelection.items(client=gen_client) == {1: {"DGNCODE": "KDS 41 30 : 2022"}}


@responses.activate
def test_steel_design_code_selection_create_raises_before_any_http_call(gen_client):
    with pytest.raises(UnsupportedMethodError):
        SteelDesignCodeSelection.create({1: {"DGNCODE": "KDS 41 30 : 2022"}}, client=gen_client)
    assert len(responses.calls) == 0


def test_steel_design_code_selection_is_not_the_db_dstl_resource():
    from midas_nx.db.design import SteelDesignCode

    assert SteelDesignCodeSelection.ENDPOINT == "/DESIGN/STEEL/DSTL"
    assert SteelDesignCode.ENDPOINT == "/db/DSTL"


# === Group 1: 설계 코드·일반 설정 ===


@responses.activate
def test_design_code_option_update_sends_documented_assign_shape(gen_client):
    responses.add(responses.PUT, f"{BASE}/DCO", json={}, status=200)
    SteelDesignCodeOption.update(
        {
            1: {
                "DGNCODE": "KDS 41 30 : 2022",
                "LAT_BRACE": False,
                "DEFL_CHK": True,
                "SEISMIC": True,
                "COMB_RATIO": 1,
                "SEIS_SYS": "Special Moment Frames",
                "COL_WEAK": True,
                "UNDGR_LD": True,
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["SEIS_SYS"] == "Special Moment Frames"


@responses.activate
def test_design_code_option_create_raises_before_any_http_call(gen_client):
    with pytest.raises(UnsupportedMethodError):
        SteelDesignCodeOption.create({1: {"DGNCODE": "KDS 41 30 : 2022"}}, client=gen_client)
    assert len(responses.calls) == 0


@responses.activate
def test_definition_of_frame_update_sends_documented_assign_shape(gen_client):
    responses.add(responses.PUT, f"{BASE}/DCTL", json={}, status=200)
    DefinitionOfFrame.update(
        {1: {"FRAMEX": "Braced Non-sway", "FRAMEY": "Braced Non-sway", "bAUTOKF": True, "DT": "XZ"}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["DT"] == "XZ"


@responses.activate
def test_live_load_reduction_factor_update_sends_reduction_data(gen_client):
    responses.add(responses.PUT, f"{BASE}/LLRF", json={}, status=200)
    LiveLoadReductionFactor.update(
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
        LoadContributionForNonlinearLoadCase.create({2: {"NAME": "NgLCB6"}}, client=gen_client)
    with pytest.raises(UnsupportedMethodError):
        LoadContributionForNonlinearLoadCase.update({2: {"NAME": "NgLCB6"}}, client=gen_client)
    assert len(responses.calls) == 0


@responses.activate
def test_load_contribution_delete_uses_per_id_urls(gen_client):
    for item_id in (2, 3):
        responses.add(responses.DELETE, f"{BASE}/LCTB/{item_id}", json={}, status=200)

    LoadContributionForNonlinearLoadCase.delete([2, 3], client=gen_client)

    assert [call.request.url for call in responses.calls] == [
        f"{BASE}/LCTB/2", f"{BASE}/LCTB/3",
    ]


@responses.activate
def test_strength_reduction_factors_update_sends_documented_assign_shape(gen_client):
    responses.add(responses.PUT, f"{BASE}/SRDF", json={}, status=200)
    StrengthReductionFactors.update(
        {1: {"PHI_T1": 0.75, "PHI_T2": 0.75, "PHI_C": 0.25, "PHI_B": 0.45, "PHI_V": 0.85}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["PHI_C"] == 0.25


@responses.activate
def test_serviceability_parameters_create_partial_fields(gen_client):
    responses.add(responses.POST, f"{BASE}/SERV", json={}, status=200)
    ServiceabilityParameters.create(
        {915: {"DEFLECT_CONTROL": 400, "DAF": 2}, 934: {"DAF": 2}, 1057: {"DEFLECT_CONTROL": 500}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]
    assert body["934"] == {"DAF": 2}


@responses.activate
def test_seismic_load_combination_type_create(gen_client):
    responses.add(responses.POST, f"{BASE}/EQCT", json={}, status=200)
    SeismicLoadCombinationType.create(
        {1066: {"TYPE": "Special Seismic Loads"}, 1068: {"TYPE": "Vertical Seismic Forces"}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1068"]["TYPE"] == "Vertical Seismic Forces"


@responses.activate
def test_underground_load_combination_type_create(gen_client):
    responses.add(responses.POST, f"{BASE}/ULCT", json={}, status=200)
    UndergroundLoadCombinationType.create(
        {885: {"bUNDERLOADTYPE": True}, 888: {"bUNDERLOADTYPE": False}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["885"]["bUNDERLOADTYPE"] is True


@responses.activate
def test_scale_up_factor_for_earthquake_create(gen_client):
    responses.add(responses.POST, f"{BASE}/SUEQ", json={}, status=200)
    ScaleUpFactorForEarthquake.create(
        {
            915: {
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
    assert json.loads(sent.body)["Assign"]["915"]["LC_SHEAR"] == 1.2


@responses.activate
def test_combined_ratio_calculation_method_create(gen_client):
    responses.add(responses.POST, f"{BASE}/CRCM", json={}, status=200)
    CombinedRatioCalculationMethodForCircularSection.create(
        {1058: {"METHOD": "Linear Sum"}, 1059: {"METHOD": "SRSS"}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1058"]["METHOD"] == "Linear Sum"


# === Group 2: 부재별 설계 파라미터 ===


@responses.activate
def test_haunched_beam_assignment_create_sends_part_selectors(gen_client):
    responses.add(responses.POST, f"{BASE}/HCBM", json={}, status=200)
    HaunchedBeamAssignment.create(
        {
            1: {
                "NAME": "h1",
                "POS_TYPE": 0,
                "L1": 0.5,
                "L2": 0.5,
                "PART_A": {"INPUT_METHOD": "KEYS", "KEYS": [1065]},
                "PART_B": {"INPUT_METHOD": "TO", "TO": "1066to1071"},
                "PART_C": {"INPUT_METHOD": "KEYS", "KEYS": [1072]},
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]["1"]
    assert body["PART_B"] == {"INPUT_METHOD": "TO", "TO": "1066to1071"}


@responses.activate
def test_unbraced_length_create_partial_fields(gen_client):
    responses.add(responses.POST, f"{BASE}/LENG", json={}, status=200)
    UnbracedLength.create(
        {888: {"LY": 1, "LZ": 1, "LB": 1, "bNOTUSE": True, "LT": 1}, 891: {"LY": 1, "LZ": 1, "LB": 2}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["888"]["bNOTUSE"] is True


@responses.activate
def test_effective_length_factor_create(gen_client):
    responses.add(responses.POST, f"{BASE}/KFAC", json={}, status=200)
    EffectiveLengthFactor.create(
        {859: {"Ky": 1}, 860: {"Ky": 2, "Kz": 2}, 902: {"Kz": 3, "Kt": 3}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["902"]["Kt"] == 3


@responses.activate
def test_limiting_slenderness_ratio_create(gen_client):
    responses.add(responses.POST, f"{BASE}/LTSR", json={}, status=200)
    LimitingSlendernessRatio.create(
        {1067: {"COMP": 300, "TENS": 200}, 1068: {"COMP": 300, "TENS": 200}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1067"]["COMP"] == 300


@responses.activate
def test_equivalent_moment_correction_factor_create(gen_client):
    responses.add(responses.POST, f"{BASE}/CMFT", json={}, status=200)
    EquivalentMomentCorrectionFactor.create(
        {1067: {"OPT_AUTO": True}, 1069: {"CMY": 0.7, "CMZ": 0.6}}, client=gen_client
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]
    assert body["1067"] == {"OPT_AUTO": True}
    assert body["1069"]["CMZ"] == 0.6


@responses.activate
def test_moment_magnifier_create(gen_client):
    responses.add(responses.POST, f"{BASE}/FMAG", json={}, status=200)
    MomentMagnifier.create(
        {915: {"B1Y_DELTA_BY": 1.1, "B1Z_DELTA_BZ": 1.2}, 1058: {"B2Y_DELTA_SY": 1.3, "B2Z_DELTA_SZ": 1.4}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1058"]["B2Z_DELTA_SZ"] == 1.4


@responses.activate
def test_bending_coefficient_create(gen_client):
    responses.add(responses.POST, f"{BASE}/CBFT", json={}, status=200)
    BendingCoefficient.create(
        {915: {"AUTO_CAL": True}, 1058: {"AUTO_CAL": False, "VALUE": 1.2}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1058"]["VALUE"] == 1.2


@responses.activate
def test_modify_member_type_create(gen_client):
    responses.add(responses.POST, f"{BASE}/MBTP", json={}, status=200)
    ModifyMemberType.create(
        {934: {"TYPE": "BRACE"}, 1058: {"TYPE": "COLUMN"}, 1066: {"TYPE": "BEAM"}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1066"]["TYPE"] == "BEAM"


@responses.activate
def test_seismic_load_resisting_system_by_member_create(gen_client):
    responses.add(responses.POST, f"{BASE}/SLRS", json={}, status=200)
    SeismicLoadResistingSystemByMember.create(
        {
            915: {"FRAME_TYPE": "Special Concentrically Braced Frames", "CHECK_OPTION": True},
            1058: {"FRAME_TYPE": "Buckling Restrained Braced Frames"},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]
    assert body["1058"] == {"FRAME_TYPE": "Buckling Restrained Braced Frames"}


@responses.activate
def test_modify_live_load_reduction_factor_create(gen_client):
    responses.add(responses.POST, f"{BASE}/MLLR", json={}, status=200)
    ModifyLiveLoadReductionFactor.create(
        {
            922: {"COMPONENTS": {"AXIAL": False, "MOMENT": True, "SHEAR": False}},
            934: {"FACTOR": 0.9, "COMPONENTS": {"AXIAL": True, "SHEAR": False}},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["934"]["FACTOR"] == 0.9


@responses.activate
def test_member_assignment_update_sends_documented_assign_shape(gen_client):
    responses.add(responses.PUT, f"{BASE}/MEMB", json={}, status=200)
    MemberAssignment.update(
        {
            1: {"AELEM": [933, 934], "bREVERSE": False},
            2: {"AELEM": [906, 891], "bREVERSE": True},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["2"]["bREVERSE"] is True


@responses.activate
def test_member_assignment_create_raises_before_any_http_call(gen_client):
    with pytest.raises(UnsupportedMethodError):
        MemberAssignment.create({1: {"AELEM": [1]}}, client=gen_client)
    assert len(responses.calls) == 0


# === Group 3: 재료 ===


@responses.activate
def test_modify_steel_material_update_standard_and_none_variants(gen_client):
    responses.add(responses.PUT, f"{BASE}/SMODI", json={}, status=200)
    ModifySteelMaterial.update(
        {
            100: {"CODE": "Standard", "STANDARD_CODE": "KS22(S)", "GRADE": "SM355"},
            101: {"CODE": "None", "ES": 40000000, "PS": 0, "FU": 0, "NAME": "test", "FY": 0},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]
    assert body["100"]["GRADE"] == "SM355"
    assert body["101"]["NAME"] == "test"


@responses.activate
def test_modify_steel_material_create_raises_before_any_http_call(gen_client):
    with pytest.raises(UnsupportedMethodError):
        ModifySteelMaterial.create({100: {"CODE": "Standard"}}, client=gen_client)
    assert len(responses.calls) == 0


# === Group 4: 설계 수행·결과 (POST-action) ===


@responses.activate
def test_perform_steel_code_check_sends_perform_type_all(gen_client):
    responses.add(responses.POST, f"{BASE}/CODE-ANAL", json={"message": "success"}, status=200)
    perform_steel_code_check({"PERFORM_TYPE": "ALL"}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": {"PERFORM_TYPE": "ALL"}}


@responses.activate
def test_perform_steel_code_check_by_elems(gen_client):
    responses.add(responses.POST, f"{BASE}/CODE-ANAL", json={"message": "success"}, status=200)
    perform_steel_code_check(
        {"PERFORM_TYPE": "ELEMS", "ELEMS": {"KEYS": [888, 1058]}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["ELEMS"] == {"KEYS": [888, 1058]}


@responses.activate
def test_get_steel_code_check_table_sends_documented_argument_shape(gen_client):
    responses.add(responses.POST, f"{BASE}/CODE-TABLE", json={"Result Table": {}}, status=200)
    get_steel_code_check_table(
        {
            "TABLE_TYPE": "PROP",
            "PRI_SORT": 1,
            "RESULT": 0,
            "COMPONENTS": ["CHK", "MEMB", "COM", "SECT"],
            "ELEMS": {"KEYS": [888]},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "PROP"
    assert body["ELEMS"] == {"KEYS": [888]}


@responses.activate
def test_export_steel_code_check_report_sends_documented_argument_shape(gen_client):
    responses.add(
        responses.POST,
        f"{BASE}/CODE-REPORT",
        json={"SUCCESS": True, "FILE_PATH": "C:\\MIDAS\\Result\\out.jpg", "MESSAGE": ""},
        status=200,
    )
    export_steel_code_check_report(
        {
            "REPORT_TYPE": "MEMB",
            "CURRENT_MODE": "Graphic",
            "EXPORT_PATH": "C:\\MIDAS\\Result\\",
            "OUTPUT_NAME": "out.jpg",
            "ELEMS": {"KEYS": [888, 1058]},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["CURRENT_MODE"] == "Graphic"
    assert body["OUTPUT_NAME"] == "out.jpg"


@responses.activate
def test_export_steel_design_result_image_sends_nested_result_graphic(gen_client):
    responses.add(
        responses.POST, f"{BASE}/DREULT", json={"message": "MIDAS GEN NX command complete"}, status=200
    )
    export_steel_design_result_image(
        {
            "EXPORT_PATH": "C:\\MIDAS\\result\\steel design result.jpg",
            "SET_HIDDEN": True,
            "WIDTH": 1000,
            "HEIGHT": 1000,
            "RESULT_GRAPHIC": {
                "CURRENT_MODE": "INFLL_DESIGN_STEEL",
                "LOAD_CASE_COMB": {"TYPE": "CBS", "NAME": "STEEL_gLCB5"},
                "COMPONENTS": {"COMP": "Combined"},
                "TYPE_OF_DISPLAY": {
                    "LEGEND": {"OPT_CHECK": True, "VALUE_EXP": False, "DECIMAL_PT": 3},
                    "CONTOUR": {"OPT_CHECK": True, "OPTIONS": {"GRADIENT_FILL": True}},
                },
            },
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["RESULT_GRAPHIC"]["LOAD_CASE_COMB"]["NAME"] == "STEEL_gLCB5"
    assert body["RESULT_GRAPHIC"]["TYPE_OF_DISPLAY"]["CONTOUR"]["OPTIONS"]["GRADIENT_FILL"] is True


@responses.activate
def test_get_steel_member_design_forces_table_sends_documented_argument_shape(gen_client):
    responses.add(responses.POST, f"{BASE}/TABLE", json={"empty": {}}, status=200)
    get_steel_member_design_forces_table(
        {
            "TABLE_TYPE": "STEELMEMBERDESIGNFORCES",
            "COMPONENTS": ["Index", "Memb", "Part", "LComName", "Type", "Fx", "Fy", "Fz", "Mx", "My", "Mz"],
            "PARTS": ["All", "PartI", "Part1/4", "Part2/4", "Part3/4", "PartJ"],
            "NODE_ELEMS": {"KEYS": [1072]},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "STEELMEMBERDESIGNFORCES"
    assert body["NODE_ELEMS"] == {"KEYS": [1072]}
