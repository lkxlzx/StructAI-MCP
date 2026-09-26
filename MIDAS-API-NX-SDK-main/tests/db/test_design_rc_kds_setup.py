import json

import pytest
import responses

from midas_nx.client import UnsupportedMethodError
from midas_nx.design.rc_kds.setup import (
    ConcreteDesignCodeOption,
    DefinitionOfFrame,
    EffectiveLengthFactor,
    EquivalentMomentCorrectionFactor,
    HaunchedBeamAssignment,
    LiveLoadReductionFactor,
    LoadContributionForNonlinearLoadCase,
    MemberAssignment,
    ModifyConcreteMaterial,
    ModifyLiveLoadReductionFactor,
    ModifyMemberType,
    MomentMagnifier,
    RcDesignCodeSelection,
    ScaleUpFactorForEarthquake,
    SeismicColumnType,
    SeismicDesignType,
    SeismicLoadCombinationType,
    StrengthReductionFactors,
    UnbracedLength,
    UndergroundLoadCombinationType,
)

BASE = "https://x.test:443/gen/DESIGN/RC/KDS-41-20-2022"


# --- 0. DRC (RC Design Code Selection) -----------------------------------
# Added to the manual 2026-08-06 (MAPI-1365); unlike everything else in this
# file, its URI does not carry the KDS-41-20-2022 prefix.


@responses.activate
def test_rc_design_code_selection_update_sends_documented_assign_shape(gen_client):
    responses.add(responses.PUT, "https://x.test:443/gen/DESIGN/RC/DRC", json={}, status=200)
    RcDesignCodeSelection.update({1: {"DGNCODE": "KDS 41 20 : 2022"}}, client=gen_client)
    sent = responses.calls[0].request
    assert sent.url == "https://x.test:443/gen/DESIGN/RC/DRC"
    assert json.loads(sent.body) == {"Assign": {"1": {"DGNCODE": "KDS 41 20 : 2022"}}}


@responses.activate
def test_rc_design_code_selection_get_returns_response_as_is(gen_client):
    # The manual's own GET example nests the response under "DCON", not
    # "DRC"/"DCO" — DbResource.items() unwraps by shape (first dict-valued
    # entry), not by key name, so this doesn't need special handling here.
    responses.add(
        responses.GET,
        "https://x.test:443/gen/DESIGN/RC/DRC",
        json={"DCON": {"1": {"DGNCODE": "KDS 41 20 : 2022"}}},
        status=200,
    )
    assert RcDesignCodeSelection.items(client=gen_client) == {1: {"DGNCODE": "KDS 41 20 : 2022"}}


@responses.activate
def test_rc_design_code_selection_create_raises_before_any_http_call(gen_client):
    with pytest.raises(UnsupportedMethodError):
        RcDesignCodeSelection.create({1: {"DGNCODE": "KDS 41 20 : 2022"}}, client=gen_client)
    assert len(responses.calls) == 0


# --- 1. DCO -------------------------------------------------------------


@responses.activate
def test_design_code_option_update_sends_documented_assign_shape(gen_client):
    responses.add(responses.PUT, f"{BASE}/DCO", json={}, status=200)
    ConcreteDesignCodeOption.update(
        {
            1: {
                "DESIGN_CD": "KDS 41 20 : 2022",
                "SEISMIC_PROV": True,
                "TORS_DES": True,
                "TORS_RDCT_FACT": 1,
                "MOM_REDIST_FACT": 1,
                "MOM_CALC_MTHD": "Equivalent",
                "USE_SUBDIV_FORCE": True,
                "UG_LC": True,
                "SEISMIC": {
                    "FRAME_TYPE": "Special",
                    "STRONG_COL_WEAK_LAST": True,
                    "BEAM_COL_JNT_DES": True,
                    "JOINT": {
                        "CHK_POS": "Top",
                        "EXCL_MEM_TYPES": ["SUBBEAM", "CANTIL", "UGBEAMCOL"],
                    },
                    "SHEAR_WALL": {
                        "SPEC_RC_WALL": True,
                        "BDRY_ELEM_MTHD": "Displacement",
                        "DEFL_AMP_FACT": 4,
                        "IMP_FACT": 1.2,
                    },
                    "SHEAR_DES": {"R": 0.5, "MTHD": "Ve1", "A1": 1.1, "A2": 1.2},
                },
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]["1"]
    assert body["SEISMIC"]["SHEAR_WALL"]["BDRY_ELEM_MTHD"] == "Displacement"
    assert body["SEISMIC"]["SHEAR_DES"]["MTHD"] == "Ve1"


@responses.activate
def test_design_code_option_create_raises_before_any_http_call(gen_client):
    with pytest.raises(UnsupportedMethodError):
        ConcreteDesignCodeOption.create({1: {"DESIGN_CD": "KDS 41 20 : 2022"}}, client=gen_client)
    assert len(responses.calls) == 0


# --- 2. DCTL --------------------------------------------------------------


@responses.activate
def test_definition_of_frame_update_sends_documented_assign_shape(gen_client):
    responses.add(responses.PUT, f"{BASE}/DCTL", json={}, status=200)
    DefinitionOfFrame.update(
        {1: {"FRAMEX": "Braced Non-sway", "FRAMEY": "Braced Non-sway", "bAUTOKF": True, "DT": "XZ"}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["DT"] == "XZ"


# --- 3. LLRF ----------------------------------------------------------------


@responses.activate
def test_live_load_reduction_factor_update_sends_reduction_data(gen_client):
    responses.add(responses.PUT, f"{BASE}/LLRF", json={}, status=200)
    LiveLoadReductionFactor.update(
        {
            1: {
                "CALC_RULE": 0,
                "APPLIED_COMP": ["AXIAL", "MOMENTS"],
                "LIVE_LOAD_CASES": ["LL"],
                "REDUCTION_DATA": [
                    {
                        "STORY": "2F",
                        "XMIN": 0,
                        "XMAX": 30,
                        "YMIN": 0,
                        "YMAX": 20,
                        "RANGE_MAX": 1,
                        "RANGE_MIN": 0.5,
                    },
                    {"STORY": "3F", "XMIN": 0, "XMAX": 30, "YMIN": 0, "YMAX": 20},
                ],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    data = json.loads(sent.body)["Assign"]["1"]["REDUCTION_DATA"]
    assert data[0]["RANGE_MAX"] == 1
    assert "RANGE_MAX" not in data[1]


# --- 4. LCTB ------------------------------------------------------------


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


# --- 5. SRDF ------------------------------------------------------------


@responses.activate
def test_strength_reduction_factors_update_sends_documented_assign_shape(gen_client):
    responses.add(responses.PUT, f"{BASE}/SRDF", json={}, status=200)
    StrengthReductionFactors.update(
        {1: {"PHI_T": 0.8, "PHI_C1": 0.65, "PHI_C2": 0.6, "PHI_V": 0.6}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["PHI_C2"] == 0.6


@responses.activate
def test_strength_reduction_factors_create_raises_before_any_http_call(gen_client):
    with pytest.raises(UnsupportedMethodError):
        StrengthReductionFactors.create({1: {"PHI_T": 0.8}}, client=gen_client)
    assert len(responses.calls) == 0


# --- 6. EQCT ------------------------------------------------------------


@responses.activate
def test_seismic_load_combination_type_create(gen_client):
    responses.add(responses.POST, f"{BASE}/EQCT", json={}, status=200)
    SeismicLoadCombinationType.create(
        {1066: {"TYPE": "Special Seismic Loads"}, 1068: {"TYPE": "Vertical Seismic Forces"}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1068"]["TYPE"] == "Vertical Seismic Forces"


# --- 7. ULCT ------------------------------------------------------------


@responses.activate
def test_underground_load_combination_type_create(gen_client):
    responses.add(responses.POST, f"{BASE}/ULCT", json={}, status=200)
    UndergroundLoadCombinationType.create(
        {885: {"bUNDERLOADTYPE": True}, 888: {"bUNDERLOADTYPE": False}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["885"]["bUNDERLOADTYPE"] is True


# --- 8. SUEQ ------------------------------------------------------------


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
            },
            934: {"LC_SHEAR": 1.2, "LCOM_AXIAL": 1.2},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]
    assert body["915"]["LC_SHEAR"] == 1.2
    assert "LC_AXIAL" not in body["934"]


# --- 9. SDGN ------------------------------------------------------------


@responses.activate
def test_seismic_design_type_create(gen_client):
    responses.add(responses.POST, f"{BASE}/SDGN", json={}, status=200)
    SeismicDesignType.create(
        {
            1: {"NTYPE": "Seismic"},
            2: {"NTYPE": "Non-Seismic"},
            3: {"NTYPE": "Non-Seismic-Force-Resisting"},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["3"]["NTYPE"] == "Non-Seismic-Force-Resisting"


# --- 10. SCOL -----------------------------------------------------------


@responses.activate
def test_seismic_column_type_create(gen_client):
    responses.add(responses.POST, f"{BASE}/SCOL", json={}, status=200)
    SeismicColumnType.create(
        {915: {"TYPE": "PILOTI"}, 916: {"TYPE": "SOFT_STORY"}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["916"]["TYPE"] == "SOFT_STORY"


# --- 11. MBTP -----------------------------------------------------------


@responses.activate
def test_modify_member_type_create(gen_client):
    responses.add(responses.POST, f"{BASE}/MBTP", json={}, status=200)
    ModifyMemberType.create(
        {934: {"TYPE": "BRACE"}, 1058: {"TYPE": "COLUMN"}, 1066: {"TYPE": "BEAM"}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1066"]["TYPE"] == "BEAM"


# --- 12. MEMB -----------------------------------------------------------


@responses.activate
def test_member_assignment_update_sends_documented_assign_shape(gen_client):
    responses.add(responses.PUT, f"{BASE}/MEMB", json={}, status=200)
    MemberAssignment.update(
        {1: {"AELEM": [885, 888, 891], "bREVERSE": True}, 2: {"AELEM": [919]}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["bREVERSE"] is True


@responses.activate
def test_member_assignment_create_raises_before_any_http_call(gen_client):
    with pytest.raises(UnsupportedMethodError):
        MemberAssignment.create({1: {"AELEM": [1]}}, client=gen_client)
    assert len(responses.calls) == 0


# --- 13. MATD -----------------------------------------------------------


@responses.activate
def test_modify_concrete_material_update_standard_and_none_variants(gen_client):
    responses.add(responses.PUT, f"{BASE}/MATD", json={}, status=200)
    ModifyConcreteMaterial.update(
        {
            1: {
                "CONCRETE": {
                    "CODE": "Standard",
                    "STANDARD_CODE": "KS19(RC)",
                    "GRADE": "C24",
                    "LIGHTWEIGHT": False,
                    "LAMBDA": 1,
                },
                "REBAR": {
                    "CODE": "Standard",
                    "STANDARD_CODE": "KS19(RC)",
                    "MAIN_REBAR_GRADE": "SD400",
                    "SUB_REBAR_GRADE": "SD400",
                },
            },
            2: {
                "CONCRETE": {"CODE": "None", "NAME": "myConc", "FC": 0.024},
                "REBAR": {
                    "CODE": "None",
                    "MAIN_REBAR_NAME": "myMain",
                    "SUB_REBAR_NAME": "mySub",
                    "FY": 0.0004,
                    "FYS": 0.0004,
                },
            },
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]
    assert body["1"]["CONCRETE"]["GRADE"] == "C24"
    assert body["2"]["REBAR"]["MAIN_REBAR_NAME"] == "myMain"


@responses.activate
def test_modify_concrete_material_create_raises_before_any_http_call(gen_client):
    with pytest.raises(UnsupportedMethodError):
        ModifyConcreteMaterial.create({1: {"CONCRETE": {"CODE": "Standard"}}}, client=gen_client)
    assert len(responses.calls) == 0


# --- 14. LENG -----------------------------------------------------------


@responses.activate
def test_unbraced_length_create_partial_fields(gen_client):
    responses.add(responses.POST, f"{BASE}/LENG", json={}, status=200)
    UnbracedLength.create(
        {888: {"LY": 1, "LZ": 1, "LB": 1, "bNOTUSE": True, "LT": 1}, 891: {"LY": 1, "LZ": 1, "LB": 2}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["888"]["bNOTUSE"] is True


# --- 15. KFAC -----------------------------------------------------------


@responses.activate
def test_effective_length_factor_create(gen_client):
    responses.add(responses.POST, f"{BASE}/KFAC", json={}, status=200)
    EffectiveLengthFactor.create(
        {859: {"Ky": 1}, 860: {"Ky": 2, "Kz": 2}, 902: {"Kz": 3, "Kt": 3}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["902"]["Kt"] == 3


# --- 16. CMFT -----------------------------------------------------------


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


# --- 17. FMAG -----------------------------------------------------------


@responses.activate
def test_moment_magnifier_create(gen_client):
    responses.add(responses.POST, f"{BASE}/FMAG", json={}, status=200)
    MomentMagnifier.create(
        {915: {"B1Y_DELTA_BY": 1.1, "B1Z_DELTA_BZ": 1.2}, 1058: {"B2Y_DELTA_SY": 1.3, "B2Z_DELTA_SZ": 1.4}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1058"]["B2Z_DELTA_SZ"] == 1.4


# --- 18. MLLR -----------------------------------------------------------


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


# --- 19. HCBM -----------------------------------------------------------


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


# --- civil-product smoke test (PRODUCTS default: gen + civil) -----------


@responses.activate
def test_member_assignment_works_on_civil_client(civil_client):
    civil_base = "https://x.test:443/civil/DESIGN/RC/KDS-41-20-2022"
    responses.add(responses.GET, f"{civil_base}/MEMB", json={"MEMB": {}}, status=200)
    MemberAssignment.get(client=civil_client)
    assert len(responses.calls) == 1
