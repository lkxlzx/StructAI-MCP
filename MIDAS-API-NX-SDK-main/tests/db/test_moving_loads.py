import json

import pytest
import responses

from midas_nx.client import MidasRequestError
from midas_nx.db.moving_loads import (
    AdditionalImpactFactor,
    ConcurrentJointForceGroup,
    ConcurrentReactionGroup,
    DynamicLoadAllowance,
    LaneSupportNegativeMoment,
    LaneSupportReaction,
    MovingLoadCase,
    MovingLoadCaseBs,
    MovingLoadCaseChina,
    MovingLoadCaseEurocode,
    MovingLoadCaseIndia,
    MovingLoadCasePoland,
    MovingLoadCaseTransverse,
    MovingLoadCode,
    PlateElementForInfluenceSurface,
    RailwayDynamicFactor,
    RailwayDynamicFactorByElement,
    TrafficLineLanes,
    TrafficLineLanesChina,
    TrafficLineLanesIndia,
    TrafficLineLanesOptimization,
    TrafficLineLanesTransverse,
    TrafficSurfaceLanes,
    TrafficSurfaceLanesChina,
    TrafficSurfaceLanesOptimization,
    VehicleClasses,
    Vehicles,
    VehiclesTransverse,
)

# --- 1. /db/MVCD --------------------------------------------------------------


@responses.activate
def test_moving_load_code_create_sends_documented_assign_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVCD", json={}, status=200)
    MovingLoadCode.create({1: {"CODE": "KSCE-LSD15"}}, client=civil_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["CODE"] == "KSCE-LSD15"


@responses.activate
def test_moving_load_code_also_works_on_gen_client(gen_client):
    # Not Civil-only despite the chapter's bridge-design framing — route +
    # /info both answer on Gen NX too, live-checked 2026-07-29.
    responses.add(responses.POST, "https://x.test:443/gen/db/MVCD", json={}, status=200)
    MovingLoadCode.create({1: {"CODE": "KSCE-LSD15"}}, client=gen_client)
    assert len(responses.calls) == 1


# --- 2. /db/LLAN ---------------------------------------------------------------


@responses.activate
def test_traffic_line_lanes_create_sends_common_and_lane_items(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/LLAN", json={}, status=200)
    TrafficLineLanes.create(
        {
            1: {
                "COMMON": {
                    "LL_NAME": "LL_01",
                    "LOAD_DIST": "LANE",
                    "GROUP_NAME": "",
                    "SKEW_START": 0,
                    "SKEW_END": 0,
                    "MOVING": "FORWARD",
                    "WHEEL_SPACE": 1.8,
                    "WIDTH": 3,
                    "OPT_AUTO_LANE": True,
                    "ALLOW_WIDTH": 3,
                },
                "LANE_ITEMS": [
                    {"ELEM": 1, "ECC": -1.5},
                    {"ELEM": 2, "ECC": -1.5},
                ],
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]["1"]
    assert body["COMMON"]["LL_NAME"] == "LL_01"
    assert body["LANE_ITEMS"][1]["ELEM"] == 2


# --- 3. /db/LLANch --------------------------------------------------------------


@responses.activate
def test_traffic_line_lanes_china_create_sends_span_fields(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/LLANch", json={}, status=200)
    TrafficLineLanesChina.create(
        {
            1: {
                "COMMON": {
                    "LL_NAME": "LL_01",
                    "LOAD_DIST": "LANE",
                    "GROUP_NAME": "",
                    "SKEW_START": 0,
                    "SKEW_END": 0,
                    "MOVING": "BOTH",
                    "WHEEL_SPACE": 1.8,
                    "WIDTH": 3,
                    "OPT_AUTO_LANE": True,
                    "ALLOW_WIDTH": 3,
                },
                "LANE_ITEMS": [
                    {"ELEM": 1, "ECC": -1.5, "SPAN": 12, "SPAN_START": True, "SCALE_FACTOR": 1.1},
                ],
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["LANE_ITEMS"][0]["SCALE_FACTOR"] == 1.1


# --- 4. /db/LLANid --------------------------------------------------------------


@responses.activate
def test_traffic_line_lanes_india_create_sends_impact_span_option(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/LLANid", json={}, status=200)
    TrafficLineLanesIndia.create(
        {
            1: {
                "COMMON": {
                    "LL_NAME": "LL_01",
                    "LOAD_DIST": "LANE",
                    "GROUP_NAME": "",
                    "SKEW_START": 0,
                    "SKEW_END": 0,
                    "MOVING": "BOTH",
                    "WHEEL_SPACE": 1.8,
                    "WIDTH": 0,
                    "OPT_AUTO_LANE": False,
                    "ALLOW_WIDTH": 0,
                },
                "LANE_ITEMS": [
                    {"ELEM": 1, "ECC": -1.5, "SPAN": 12, "IMPACT_SPAN": 1, "IMPACT_FACTOR": 0},
                ],
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["LANE_ITEMS"][0]["IMPACT_SPAN"] == 1


# --- 5. /db/LLANtr --------------------------------------------------------------


@responses.activate
def test_traffic_line_lanes_transverse_create_sends_factor_items(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/LLANtr", json={}, status=200)
    TrafficLineLanesTransverse.create(
        {
            1: {
                "LL_NAME": "LL_01",
                "LANE_ITEMS": [
                    {"ELEM": 1, "FACTOR": 1.1},
                    {"ELEM": 2, "FACTOR": 1.1},
                ],
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["LANE_ITEMS"][0]["FACTOR"] == 1.1


# --- 6. /db/LLANop --------------------------------------------------------------


@responses.activate
def test_traffic_line_lanes_optimization_create_sends_documented_assign_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/LLANop", json={}, status=200)
    TrafficLineLanesOptimization.create(
        {
            1: {
                "LL_NAME": "LL_01",
                "LOAD_DIST": "LANE",
                "GROUP_NAME": "",
                "SKEW_START": 0,
                "SKEW_END": 0,
                "MOVING": "BOTH",
                "OPTIM_WIDTH": 5,
                "LANE_WIDTH": 3,
                "OFFSET_TYPE": 0,
                "DIVIDE_NUM": 2,
                "ANAL_LANE_OFFSET": 1,
                "WHEEL_SPACE": 1.8288,
                "MARGIN": 0.1,
                "LANE_ITEMS": [
                    {"ELEM": 1, "ECC": -1.5, "SPAN_START": True, "CENT_F": 0.5},
                    {"ELEM": 2, "ECC": -1.5, "SPAN_START": False, "CENT_F": 0.5},
                ],
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["OFFSET_TYPE"] == 0


# --- 7. /db/SLAN ----------------------------------------------------------------


@responses.activate
def test_traffic_surface_lanes_create_sends_documented_assign_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/SLAN", json={}, status=200)
    TrafficSurfaceLanes.create(
        {
            1: {
                "NAME": "SL_01",
                "WIDTH": 3,
                "WHEEL_SPACE": 1.8,
                "SKEW_START": 0,
                "SKEW_END": 0,
                "bOPTIMIZE": True,
                "ALLOW_WIDTH": 3,
                "MV_DIR": "BOTH",
                "LANE_ITEMS": [
                    {"NODE": 1, "OFFSET": -1.5},
                    {"NODE": 2, "OFFSET": -1.5},
                ],
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["MV_DIR"] == "BOTH"


# --- 8. /db/SLANch --------------------------------------------------------------


@responses.activate
def test_traffic_surface_lanes_china_create_sends_span_length(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/SLANch", json={}, status=200)
    TrafficSurfaceLanesChina.create(
        {
            1: {
                "NAME": "SL_01",
                "WIDTH": 3,
                "WHEEL_SPACE": 1.8,
                "SKEW_START": 0,
                "SKEW_END": 0,
                "bOPTIMIZE": True,
                "ALLOW_WIDTH": 3,
                "MV_DIR": "BOTH",
                "LANE_ITEMS": [
                    {"NODE": 1, "OFFSET": -1.5, "SPAN_LENGTH": 12},
                ],
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["LANE_ITEMS"][0]["SPAN_LENGTH"] == 12


# --- 9. /db/SLANop --------------------------------------------------------------


@responses.activate
def test_traffic_surface_lanes_optimization_create_sends_documented_assign_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/SLANop", json={}, status=200)
    TrafficSurfaceLanesOptimization.create(
        {
            1: {
                "LANE_NAME": "SL_OP_01",
                "SKEW_START": 0,
                "SKEW_END": 0,
                "MOVING": "BOTH",
                "OPTIMIZE_WIDTH": 4,
                "LANE_WIDTH": 3,
                "WHEEL_SPACE": 1.8288,
                "MARGIN": 0.1,
                "OFFSET_TYPE": 0,
                "DIVIDE_NUM": 2,
                "ITEMS": [
                    {"NODE_KEY": 1, "OFFSET": -1.5, "FACTOR": 1.25, "SPAN_START": True},
                    {"NODE_KEY": 2, "OFFSET": -1.5, "FACTOR": 1.25, "SPAN_START": False},
                ],
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["ITEMS"][1]["NODE_KEY"] == 2


# --- 10. /db/MVHL ---------------------------------------------------------------


@responses.activate
def test_vehicles_create_sends_veh_default(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVHL", json={}, status=200)
    Vehicles.create(
        {
            1: {
                "MVLD_CODE": 2,
                "VEHICLE_LOAD_NAME": "US(ALL)_HL-93TRK",
                "VEHICLE_LOAD_NUM": 1,
                "VEHICLE_TYPE_NAME": "HL-93TRK",
                "STANDARD_CODE": "AASHTO-LRFD",
                "VEH_DEFAULT": {"DYN_LOAD_ALLOWANCE": 25, "CENT_F": True},
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["VEH_DEFAULT"]["DYN_LOAD_ALLOWANCE"] == 25


@responses.activate
def test_vehicles_create_sends_veh_eurocode_without_standard_code(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVHL", json={}, status=200)
    Vehicles.create(
        {
            1: {
                "MVLD_CODE": 11,
                "VEHICLE_LOAD_NAME": "Load Model 1",
                "VEHICLE_LOAD_NUM": 1,
                "VEHICLE_TYPE_NAME": "Load Model 1",
                "VEH_EUROCODE": {
                    "SUB_TYPE": 19,
                    "AMP_VALUES": [0.75, 0.4],
                    "TANDEM_ADJUST_VALUES": [1, 1, 1],
                    "UDL_ADJUST_VALUES": [1, 1, 1, 1],
                },
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]["1"]
    assert body["VEH_EUROCODE"]["SUB_TYPE"] == 19
    assert "STANDARD_CODE" not in body


# --- 11. /db/MVHLtr -------------------------------------------------------------


@responses.activate
def test_vehicles_transverse_create_sends_median_strip_fields(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVHLtr", json={}, status=200)
    VehiclesTransverse.create(
        {
            2: {
                "NAME": "Trans_Medians",
                "P": 120,
                "W": 2.3,
                "LW": 10,
                "NUM": 4,
                "DW": 0.3,
                "DV": 0.4,
                "DE": 0.5,
                "OPT_MEDIAN_STRIP": True,
                "ML": 15,
                "MW": 1,
                "LEFT_LANES": 2,
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["2"]["LEFT_LANES"] == 2


# --- 12. /db/MVLD ---------------------------------------------------------------


@responses.activate
def test_moving_load_case_create_general_load_variant(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVLD", json={}, status=200)
    MovingLoadCase.create(
        {
            1: {
                "LCNAME": "MV_Case1",
                "DESC": "",
                "TYPE": 0,
                "DEFAULT": {
                    "SCALE_FACTORS": [1, 0.9, 0.8, 0.7, 0.65, 0.65],
                    "COMB_OPTION": "COMBINED",
                    "LANE_FACTOR_TYPE": 1,
                    "SUB_LOAD_DATAS": [
                        {
                            "VEHICLE_TYPE": "VL",
                            "VEHICLE_NAME": "ST_KL-510FTG",
                            "SCALE_FACTOR": 1,
                            "MIN_LOADED_LANE": 1,
                            "MAX_LOADED_LANE": 2,
                            "LANE_NAMES": ["LL_01", "LL_02"],
                        }
                    ],
                },
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]["1"]
    assert body["DEFAULT"]["SUB_LOAD_DATAS"][0]["VEHICLE_NAME"] == "ST_KL-510FTG"


@responses.activate
def test_moving_load_case_create_permit_vehicle_variant(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVLD", json={}, status=200)
    MovingLoadCase.create(
        {
            1: {
                "LCNAME": "MV_Permit",
                "DESC": "",
                "TYPE": 1,
                "PERMIT_LOAD": {
                    "VEHICLE_LOAD_NAME": "UD_PermitTruck",
                    "REF_LANE": "LL_01",
                    "SCALE_FACTOR": 1,
                },
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["PERMIT_LOAD"]["REF_LANE"] == "LL_01"


@responses.activate
def test_moving_load_case_create_optimization_variant(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVLD", json={}, status=200)
    MovingLoadCase.create(
        {
            1: {
                "LCNAME": "MV_Optimize",
                "DESC": "",
                "TYPE": 2,
                "AUTO_OPTIMIZE": {
                    "LANE_NAME": "LL_01",
                    "SCALE_FACTORS": [1.2, 1, 0.85, 0.65, 0.65, 0.65],
                    "MIN_VEHL_DIST": 1,
                    "MIN_NUM_VEHICLE": 1,
                    "MAX_NUM_VEHICLE": 2,
                    "OPTIMIZE_ITEMS": [
                        {"VEHICLE_TYPE": "VL", "VEHICLE_NAME": "HL-93TRK", "SCALE_FACTOR": 1}
                    ],
                },
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["AUTO_OPTIMIZE"]["MAX_NUM_VEHICLE"] == 2


@responses.activate
def test_moving_load_case_preserves_australia_heavy_load_platform_variant(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVLD", json={}, status=200)
    MovingLoadCase.create(
        {
            1: {
                "LCNAME": "MV_Australia_Heavy",
                "DESC": "",
                "TYPE": 0,
                "ASL": {
                    "MULTIPLE_FACTOR": 0.5,
                    "VEHICLE_LOAD_NAME": "HLP",
                    "VEHICLE_LOAD_NAME2": "M1600",
                    "MIN_LOADED_LANE": 1,
                    "MAX_LOADED_LANE": 2,
                    "LINE_ITEMS": {
                        "NA_LLAN_NAMES": ["LL_01"],
                        "STRAD_LLAN1_NAMES": ["LL_01"],
                        "STRAD_LLAN2_NAMES": ["LL_02"],
                    },
                },
            }
        },
        client=civil_client,
    )
    body = json.loads(responses.calls[0].request.body)["Assign"]["1"]
    assert body["ASL"]["LINE_ITEMS"]["STRAD_LLAN2_NAMES"] == ["LL_02"]


@responses.activate
def test_moving_load_case_delete_uses_per_id_urls(civil_client):
    for item_id in (1, 2):
        responses.add(
            responses.DELETE, f"https://x.test:443/civil/db/MVLD/{item_id}", json={}, status=200
        )

    MovingLoadCase.delete([1, 2], client=civil_client)

    assert [call.request.url for call in responses.calls] == [
        "https://x.test:443/civil/db/MVLD/1",
        "https://x.test:443/civil/db/MVLD/2",
    ]


# --- 13. /db/MVLDch -------------------------------------------------------------


@responses.activate
def test_moving_load_case_china_create_sends_bridge_type_scale_factors(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVLDch", json={}, status=200)
    MovingLoadCaseChina.create(
        {
            1: {
                "LCNAME": "MV_China_1",
                "DESC": "",
                "OPT_AUTO_OPTIMIZE": False,
                "BRIDGE_TYPE": 2,
                "SCALE_FACTOR_O": [1, 1, 0.80, 0.67, 0.60, 0.55, 0.55, 0.55],
                "SCALE_FACTOR_N": [1, 1, 0.78, 0.67, 0.60, 0.55, 0.52, 0.50],
                "SCALE_FACTOR_JTG": [1.2, 1, 0.78, 0.67, 0.60, 0.55, 0.52, 0.50],
                "LOADING_EFFECT": 1,
                "SUB_LOAD_ITEMS": [
                    {
                        "VEHICLE_CLASS": "CH(CJJ11)_C-CD(A/B)",
                        "VEHICLE_TYPE": "VL",
                        "SCALE_FACTOR": 1,
                        "MIN_NUM_LOADED_LANES": 1,
                        "MAX_NUM_LOADED_LANES": 2,
                        "SELECTED_LANES": ["LL_01", "LL_02"],
                    }
                ],
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["BRIDGE_TYPE"] == 2


@responses.activate
def test_moving_load_case_china_preserves_optimization_variant(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVLDch", json={}, status=200)
    MovingLoadCaseChina.create(
        {
            1: {
                "LCNAME": "MV_China_Optimize",
                "DESC": "",
                "OPT_AUTO_OPTIMIZE": True,
                "BRIDGE_TYPE": 2,
                "SCALE_FACTOR_O": [1.0] * 8,
                "SCALE_FACTOR_N": [1.0] * 8,
                "SCALE_FACTOR_JTG": [1.0] * 8,
                "LOADING_EFFECT": 0,
                "MIN_VEHICLE_DIST": 1.0,
                "LOADED_LANE_NAME": "LL_01",
                "MIN_NUM_VEHICLE": 1,
                "MAX_NUM_VEHICLE": 2,
                "AUTO_OPTIMIZE_ITEMS": [
                    {"VEHICLE_TYPE": "VL", "VEHICLE_NAME": "CH_VEHICLE", "SCALE_FACTOR": 1.0}
                ],
            }
        },
        client=civil_client,
    )
    body = json.loads(responses.calls[0].request.body)["Assign"]["1"]
    assert body["AUTO_OPTIMIZE_ITEMS"][0]["VEHICLE_NAME"] == "CH_VEHICLE"


# --- 17. /db/MVLDpl ------------------------------------------------------------


@responses.activate
def test_moving_load_case_poland_preserves_documented_conditional_objects(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVLDpl", json={}, status=200)
    MovingLoadCasePoland.create(
        {
            1: {
                "LCNAME": "MV_PL_Optimize",
                "DESC": "",
                "LOAD_MODEL": 1,
                "bAUTO_OPTIMIZE": True,
                "bPERMIT_LOAD": False,
                "AUTO_OPTIMIZE": {
                    "MIN_VEHL_DIST": 1.0,
                    "LANE_NAME": "L1",
                    "MIN_NUM_VEHICLE": 1,
                    "MAX_NUM_VEHICLE": 2,
                    "COMB_OPTION": "INDEPENDENT",
                    "OPTIMIZE_ITEMS": [
                        {"VEHICLE_TYPE": "VL", "VEHICLE_NAME": "VehicleS", "SCALE_FACTOR": 1.0}
                    ],
                },
            },
            2: {
                "LCNAME": "MV_PL_Permit",
                "DESC": "",
                "LOAD_MODEL": 1,
                "bAUTO_OPTIMIZE": False,
                "bPERMIT_LOAD": True,
                "PERMIT_LOAD": {
                    "VEHICLE_LOAD_NAME": "UD_PermitTruck",
                    "REF_LANE": "L1",
                    "ECC": 1.2,
                    "SCALE_FACTOR": 1.0,
                },
            },
        },
        client=civil_client,
    )
    body = json.loads(responses.calls[0].request.body)["Assign"]
    assert body["1"]["AUTO_OPTIMIZE"]["OPTIMIZE_ITEMS"][0]["VEHICLE_TYPE"] == "VL"
    assert body["2"]["PERMIT_LOAD"]["REF_LANE"] == "L1"


# --- 14. /db/MVLDid -------------------------------------------------------------


@responses.activate
def test_moving_load_case_india_create_general_load_variant(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVLDid", json={}, status=200)
    MovingLoadCaseIndia.create(
        {
            1: {
                "LCNAME": "MV_India_1",
                "DESC": "",
                "SCALE_FACTOR": [1, 0.9, 0.8, 0.8],
                "NUM_LOADED_LANES": 2,
                "SUB_LOAD_ITEMS": [
                    {
                        "VEHICLE_CLASS_1": "IN(IRC6)_ClassA",
                        "SCALE_FACTOR": 1,
                        "MIN_NUM_LOADED_LANES": 1,
                        "MAX_NUM_LOADED_LANES": 2,
                        "SELECTED_LANES": ["LL_01", "LL_02"],
                    }
                ],
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["NUM_LOADED_LANES"] == 2


@responses.activate
def test_moving_load_case_india_create_permit_vehicle_variant(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVLDid", json={}, status=200)
    MovingLoadCaseIndia.create(
        {
            2: {
                "LCNAME": "MV_India_Permit",
                "DESC": "",
                "SCALE_FACTOR": [1, 0.9, 0.8, 0.8],
                "OPT_LC_FOR_PERMIT_LOAD": True,
                "PERMIT_VEHICLE": 1,
                "REF_LANE": 1,
                "ECCEN": 0,
                "PERMIT_SCALE_FACTOR": 1,
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["2"]["PERMIT_VEHICLE"] == 1


# --- 15. /db/MVLDbs -------------------------------------------------------------


@responses.activate
def test_moving_load_case_bs_create_standard_load_model(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVLDbs", json={}, status=200)
    MovingLoadCaseBs.create(
        {
            1: {
                "LCNAME": "MV_BS_Standard",
                "DESC": "",
                "bAUTOOPTIMIZE": False,
                "LOADMODEL": "STANDER",
                "bAUTOLIVELOADCOMB": True,
                "DGNCOMBFACTORTYPE": "ULTIMATE",
                "COMBMETHOD": "COMB_1",
                "LCDATA_STANDARD": {
                    "LOADINGEFFECT": "INDEPEND",
                    "SUBLOADDATA": [
                        {
                            "SCALEFACTOR": 1,
                            "NUMLOADEDLANE": 4,
                            "VEHICLE_NAME": "BS_(BD21)_HA&HB(Auto)",
                            "SELECTEDLANES": ["LL_01", "LL_02", "LL_03", "LL_04"],
                            "STRAD_LANE": [{"STARDD_LANE_1": "LL_03", "STARDD_LANE_2": "LL_04"}],
                        }
                    ],
                },
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]["1"]
    assert body["LCDATA_STANDARD"]["SUBLOADDATA"][0]["STRAD_LANE"][0]["STARDD_LANE_2"] == "LL_04"


# --- 16. /db/MVLDeu -------------------------------------------------------------


@responses.activate
def test_moving_load_case_eurocode_create_lm1_general_load(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVLDeu", json={}, status=200)
    MovingLoadCaseEurocode.create(
        {
            1: {
                "LCNAME": "MV_Case1",
                "OPT_AUTO_OPTIMIZE": False,
                "TYPE_LOADMODEL": 1,
                "DESC": "",
                "VHLNAME1": "EU_(R)_LoadModel1",
                "VHLNAME2": "EU_(FF)_Uniformload(Road)",
                "OPT_LEADING": False,
                "SLN_LIST": ["LL_01", "LL_02"],
                "SRA_LIST": ["LL_04"],
                "FLN_LIST": ["LL_03"],
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["FLN_LIST"] == ["LL_03"]


@responses.activate
def test_moving_load_case_eurocode_create_lm4_straddling_variant(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVLDeu", json={}, status=200)
    MovingLoadCaseEurocode.create(
        {
            4: {
                "LCNAME": "MV_Case4",
                "OPT_AUTO_OPTIMIZE": False,
                "TYPE_LOADMODEL": 4,
                "DESC": "",
                "VHLNAME1": "EU_(R)_LoadModel1",
                "VHLNAME2": "EU_(R)_LoadModel3(UKNA)_SOV250_Auto",
                "OPT_LEADING": False,
                "SLN_LIST": ["LL_01", "LL_03", "LL_04"],
                "SRA_LIST": ["LL_02"],
                "STL_LIST": [{"NAME1": "LL_03", "NAME2": "LL_04"}],
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["4"]["STL_LIST"][0]["NAME2"] == "LL_04"


@responses.activate
def test_moving_load_case_eurocode_create_optimization_variant(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVLDeu", json={}, status=200)
    MovingLoadCaseEurocode.create(
        {
            6: {
                "LCNAME": "MV_Case6",
                "OPT_AUTO_OPTIMIZE": True,
                "TYPE_LOADMODEL": 1,
                "DESC": "",
                "VHLNAME1": "EU_(R)_LoadModel1",
                "VHLNAME2": "EU_(FF)_Uniformload(Road)",
                "OPT_LEADING": False,
                "MINVHLDIST": 1,
                "OPTIMIZE_LANE_NAME": "LL_01",
                "LOADEDLANE": 3,
                "SLN_LIST": ["LL_01", "LL_03", "LL_04"],
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["6"]["OPTIMIZE_LANE_NAME"] == "LL_01"


# --- 17. /db/MVLDpl -------------------------------------------------------------


@responses.activate
def test_moving_load_case_poland_create_vehicle_s_variant(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVLDpl", json={}, status=200)
    MovingLoadCasePoland.create(
        {
            1: {
                "LCNAME": "MV_PL_VehicleS",
                "DESC": "",
                "LOAD_MODEL": 1,
                "bAUTO_OPTIMIZE": False,
                "bPERMIT_LOAD": False,
                "DEFAULT": {
                    "COMB_OPTION": "INDEPENDENT",
                    "SUB_LOAD_DATAS": [
                        {
                            "VEHICLE_NAME": "VehicleS",
                            "SCALE_FACTOR": 1,
                            "MIN_LOADED_LANE": 1,
                            "MAX_LOADED_LANE": 2,
                            "LANE_NAMES": ["L1", "L2"],
                        }
                    ],
                },
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]["1"]
    assert body["DEFAULT"]["SUB_LOAD_DATAS"][0]["VEHICLE_NAME"] == "VehicleS"


# --- 18. /db/MVLDtr -------------------------------------------------------------


@responses.activate
def test_moving_load_case_transverse_create_sends_documented_assign_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVLDtr", json={}, status=200)
    MovingLoadCaseTransverse.create(
        {
            1: {
                "LCNAME": "MV_Trans_1",
                "DESC": "",
                "MVHL_NAME": "Trans",
                "SCALEFACTOR": 1,
                "LLAN_NAME": "LL_01",
                "NUM_LANE": 3,
                "ITEMS": [1, 1, 0.9, 0.75],
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["ITEMS"] == [1, 1, 0.9, 0.75]


# --- 19. /db/CRGR ----------------------------------------------------------------


@responses.activate
def test_concurrent_reaction_group_create_sends_groups(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/CRGR", json={}, status=200)
    ConcurrentReactionGroup.create(
        {1: {"GROUPS": ["Main3", "Main4", "Main5"]}}, client=civil_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["GROUPS"] == ["Main3", "Main4", "Main5"]


# --- 20. /db/CJFG ----------------------------------------------------------------


@responses.activate
def test_concurrent_joint_force_group_create_sends_groups(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/CJFG", json={}, status=200)
    ConcurrentJointForceGroup.create(
        {1: {"GROUPS": ["Main1", "Main2", "Main3", "Main4"]}}, client=civil_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["GROUPS"] == ["Main1", "Main2", "Main3", "Main4"]


# --- 21. /db/MVHC ----------------------------------------------------------------


@responses.activate
def test_vehicle_classes_create_sends_documented_assign_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVHC", json={}, status=200)
    VehicleClasses.create(
        {
            1: {
                "VEHICLE_CLS_NAME": "Heavy_Trucks",
                "VEHICLE_LD_NAMES": ["DB-18", "DB-24", "HL-93TRK"],
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["VEHICLE_LD_NAMES"] == [
        "DB-18",
        "DB-24",
        "HL-93TRK",
    ]


# --- 22. /db/SINF ----------------------------------------------------------------


@responses.activate
def test_plate_element_for_influence_surface_create_sends_elem_lists(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/SINF", json={}, status=200)
    PlateElementForInfluenceSurface.create(
        {1: {"ELEM_LISTS": [438, 439, 440, 441, 442, 443, 444]}}, client=civil_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["ELEM_LISTS"] == [
        438,
        439,
        440,
        441,
        442,
        443,
        444,
    ]


# --- 23. /db/MLSP ----------------------------------------------------------------


@responses.activate
def test_lane_support_negative_moment_create_auto_input_variant(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MLSP", json={}, status=200)
    LaneSupportNegativeMoment.create(
        {1: {"TYPE": "AutoInput", "GROUP_NAME": "CrossBeam"}}, client=civil_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["GROUP_NAME"] == "CrossBeam"


@responses.activate
def test_lane_support_negative_moment_create_user_input_beam_variant(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MLSP", json={}, status=200)
    LaneSupportNegativeMoment.create(
        {
            1: {
                "TYPE": "UserInput",
                "ELEMENT_NO": 179,
                "ELEMENT_TYPE": "BEAM",
                "POSITION": "Both",
            },
            2: {"TYPE": "UserInput", "ELEMENT_NO": 540, "ELEMENT_TYPE": "PLATE"},
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]
    assert body["1"]["POSITION"] == "Both"
    assert "POSITION" not in body["2"]


# --- 24. /db/MLSR ----------------------------------------------------------------


@responses.activate
def test_lane_support_reaction_create_sends_fixed_node_value(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MLSR", json={}, status=200)
    LaneSupportReaction.create(
        {60: {"NODE": 0}, 201: {"NODE": 0}, 202: {"NODE": 0}}, client=civil_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Assign": {"60": {"NODE": 0}, "201": {"NODE": 0}, "202": {"NODE": 0}}
    }


# --- 25. /db/DYLA ----------------------------------------------------------------


@responses.activate
def test_dynamic_load_allowance_create_sends_factor_and_items(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/DYLA", json={}, status=200)
    DynamicLoadAllowance.create(
        {
            1: {"FACTOR": 33, "ITEMS": ["Deck_Joints"]},
            2: {"FACTOR": 25, "ITEMS": ["All_Other_Components"]},
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]
    assert body["1"]["FACTOR"] == 33
    assert body["2"]["ITEMS"] == ["All_Other_Components"]


# --- 26. /db/IMPF ----------------------------------------------------------------


@responses.activate
def test_additional_impact_factor_create_effective_span_length_auto_variant(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/IMPF", json={}, status=200)
    AdditionalImpactFactor.create(
        {
            163: {
                "ITEMS": [
                    {
                        "ID": 1,
                        "LANE_TYPE": "LINE",
                        "LANE_NAME": "LL_01",
                        "ELEMTYPE": "BEAM",
                        "FACT_TYPE": "EFF_SPAN_LEN_AUTO",
                        "FACTOR": 0,
                        "PARTS": [True, True, True, True, True],
                        "COMPONENTS": [True, True, True, True, True, True, False, False],
                    }
                ]
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]["163"]["ITEMS"][0]
    assert body["FACT_TYPE"] == "EFF_SPAN_LEN_AUTO"
    assert body["COMPONENTS"] == [True, True, True, True, True, True, False, False]


@responses.activate
def test_additional_impact_factor_create_impact_factor_variant(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/IMPF", json={}, status=200)
    AdditionalImpactFactor.create(
        {
            82: {
                "ITEMS": [
                    {
                        "ID": 1,
                        "LANE_TYPE": "LINE",
                        "LANE_NAME": "LL_01",
                        "FACT_TYPE": "IMPACT_FACT",
                        "FACTOR": 0.3,
                    }
                ]
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["82"]["ITEMS"][0]["FACTOR"] == 0.3


# --- 27. /db/DYFG ----------------------------------------------------------------


@responses.activate
def test_railway_dynamic_factor_create_auto_input_variant(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/DYFG", json={}, status=200)
    RailwayDynamicFactor.create(
        {
            1: {
                "INPUT_TYPE": 0,
                "LENGTH": 12,
                "MAINTAIN_TYPE": 0,
                "OPT_REDUCE_EFF": True,
                "HEIGHT_COVER": 1,
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["LENGTH"] == 12


@responses.activate
def test_railway_dynamic_factor_create_user_input_variant(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/DYFG", json={}, status=200)
    RailwayDynamicFactor.create(
        {1: {"INPUT_TYPE": 1, "DYN_FACTOR": 1.2611627362707665}}, client=civil_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["DYN_FACTOR"] == 1.2611627362707665


# --- 28. /db/DYNF ----------------------------------------------------------------


@responses.activate
def test_railway_dynamic_factor_by_element_create_keyed_by_element_id(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/DYNF", json={}, status=200)
    RailwayDynamicFactorByElement.create(
        {
            249: {
                "INPUT_TYPE": 0,
                "LENGTH": 12,
                "MAINTAIN_TYPE": 1,
                "OPT_REDUCE_EFF": True,
                "HEIGHT_COVER": 1,
            },
            88: {"INPUT_TYPE": 1, "DYN_FACTOR": 1.3},
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]
    assert body["249"]["MAINTAIN_TYPE"] == 1
    assert body["88"]["DYN_FACTOR"] == 1.3


@responses.activate
def test_vehicles_refuses_an_empty_veh_default(civil_client):
    """The server takes `VEH_DEFAULT: {}` and stores nothing.

    Every member of that object is documented Optional, so an empty one reads
    as "all defaults"; the response is `{"message": ""}` with no error object
    and the vehicle is simply absent from the next GET. Nothing tells the
    caller, which is why the refusal belongs in the SDK rather than in a
    docstring. Contract rule db-mvhl-veh-default-not-empty.
    """
    responses.add(responses.POST, "https://x.test:443/civil/db/MVHL", json={}, status=200)

    with pytest.raises(MidasRequestError):
        Vehicles.create(
            {1: {"MVLD_CODE": 2, "VEHICLE_LOAD_NAME": "UD", "VEH_DEFAULT": {}}},
            client=civil_client,
        )

    assert not responses.calls, "the request must not reach the product"


@responses.activate
def test_vehicles_update_refuses_an_empty_veh_default_too(civil_client):
    """A PUT that empties the object is the same silent loss as a POST."""
    responses.add(responses.PUT, "https://x.test:443/civil/db/MVHL", json={}, status=200)

    with pytest.raises(MidasRequestError):
        Vehicles.update(
            {1: {"MVLD_CODE": 2, "VEHICLE_LOAD_NAME": "UD", "VEH_DEFAULT": {}}},
            client=civil_client,
        )

    assert not responses.calls


@responses.activate
def test_vehicles_still_allows_omitting_veh_default_entirely(civil_client):
    """Omission is a different request and stays the caller's to make.

    Nine of the fourteen documented STANDARD_CODE values carry their own
    VEH_* object instead of VEH_DEFAULT, so refusing the field's absence would
    break every one of them. Only the explicitly empty object is refused.
    """
    responses.add(responses.POST, "https://x.test:443/civil/db/MVHL", json={}, status=200)

    Vehicles.create(
        {
            1: {
                "MVLD_CODE": 8,
                "VEHICLE_LOAD_NAME": "CA(Auto)_CL-625Truck",
                "VEHICLE_LOAD_NUM": 1,
                "VEHICLE_TYPE_NAME": "CL-625Truck",
                "STANDARD_CODE": "CANADA",
                "VEH_CA": {"DYN_LOAD_ALLOWANCE": 0, "DYNA": {"DYNA_FACTOR": 0}},
            }
        },
        client=civil_client,
    )

    sent = json.loads(responses.calls[0].request.body)["Assign"]["1"]
    assert sent["VEH_CA"]["DYNA"]["DYNA_FACTOR"] == 0
    assert "VEH_DEFAULT" not in sent
