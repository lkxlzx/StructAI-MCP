import json

import responses

from midas_nx.db.construction_stage import (
    AmbientTemperatureFunction,
    AssignHeatSource,
    CamberConstructionStage,
    CompositeSectionConstructionStage,
    ConstructionStage,
    ConstructionStageForHydration,
    ConvectionCoefficientFunction,
    CreepCoefficientConstructionStage,
    ElementConvectionBoundary,
    HeatSourceFunction,
    PipeCooling,
    PrescribedTemperature,
    SetBackLoad,
    TimeLoadConstructionStage,
)


@responses.activate
def test_construction_stage_create_with_activate_and_deactivate(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/STAG", json={}, status=200)
    ConstructionStage.create(
        {
            1: {
                "NAME": "CS01",
                "DURATION": 10,
                "bLOAD_STEP": True,
                "INCRE_STEP": 5,
                "ACT_ELEM": [{"GRUP_NAME": "SG_01", "AGE": 10}],
                "ACT_BNGR": [{"BNGR_NAME": "BG_01", "POS": "DEFORMED"}],
                "ACT_LOAD": [{"LOAD_NAME": "LG_01", "DAY": "5.000000"}],
            },
            3: {
                "NAME": "CS03",
                "DURATION": 10,
                "DACT_ELEM": [{"GRUP_NAME": "SG_02", "REDIST": 100}],
                "DACT_BNGR": ["BG_02"],
                "DACT_LOAD": [{"LOAD_NAME": "LG_02", "DAY": "FIRST"}],
            },
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]
    assert body["1"]["ACT_ELEM"][0]["GRUP_NAME"] == "SG_01"
    assert body["3"]["DACT_BNGR"] == ["BG_02"]


@responses.activate
def test_composite_section_construction_stage_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/CSCS", json={}, status=200)
    CompositeSectionConstructionStage.create(
        {
            1: {
                "SEC": 1,
                "ASTAGE": "CS01",
                "TYPE": "GENERAL",
                "vPARTINFO": [{"PART": 1, "MTYPE": "ELEM", "MAT": "", "AGE": 2}],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["vPARTINFO"][0]["MTYPE"] == "ELEM"


@responses.activate
def test_time_load_construction_stage_create_keyed_by_stage_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/TMLD", json={}, status=200)
    TimeLoadConstructionStage.create(
        {10: {"ITEMS": [{"ID": 1, "GROUP_NAME": "DL_BC_2", "DAY": 35}]}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["10"]["ITEMS"][0]["DAY"] == 35


@responses.activate
def test_set_back_load_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/STBK", json={}, status=200)
    SetBackLoad.create(
        {1: {"NODE1": 39, "NODE2": 22, "DX": 0.1, "DY": 0.2, "DZ": 0.3, "LCNAME": "LiveLoad"}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["NODE2"] == 22


@responses.activate
def test_camber_construction_stage_create_keyed_by_node_id(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/CMCS", json={}, status=200)
    CamberConstructionStage.create({23: {"DEFORM": 0.0, "USER": 0.0}}, client=civil_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"23": {"DEFORM": 0.0, "USER": 0.0}}}


@responses.activate
def test_creep_coefficient_construction_stage_create_keyed_by_stage_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/CRPC", json={}, status=200)
    CreepCoefficientConstructionStage.create(
        {25: {"ITEMS": [{"ID": 1, "GROUP_NAME": "2ndDeadLoad", "CREEP": 1.2}]}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["25"]["ITEMS"][0]["CREEP"] == 1.2


@responses.activate
def test_ambient_temperature_function_create_sine_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/ETFC", json={}, status=200)
    AmbientTemperatureFunction.create(
        {3: {"NAME": "AmbientTemp_Sine", "TYPE": "SINE", "MAX_TEMP": 20, "MEAN_TEMP": 0, "DELAY_TIME": 1}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["3"]["TYPE"] == "SINE"


@responses.activate
def test_convection_coefficient_function_create_user_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/CCFC", json={}, status=200)
    ConvectionCoefficientFunction.create(
        {
            2: {
                "NAME": "CC_User",
                "TYPE": "USER",
                "SCALE_FACTOR": 1.2,
                "ITEM": [{"TIME": 0, "VALUE": 25}, {"TIME": 1, "VALUE": 35}],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["2"]["ITEM"][1]["VALUE"] == 35


@responses.activate
def test_element_convection_boundary_create_keyed_by_stage_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/HECB", json={}, status=200)
    ElementConvectionBoundary.create(
        {
            1: {
                "ITEMS": [
                    {"ID": 1, "FACE_NO": 1, "CCFC_NAME": "CC_Standard", "ETFC_NAME": "AT_Summer"}
                ]
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["ITEMS"][0]["CCFC_NAME"] == "CC_Standard"


@responses.activate
def test_prescribed_temperature_create_keyed_by_stage_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/HSPT", json={}, status=200)
    PrescribedTemperature.create({1: {"ITEMS": [{"ID": 1, "TEMPER": 25}]}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["ITEMS"][0]["TEMPER"] == 25


@responses.activate
def test_heat_source_function_create_code_with_concrete_data_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/HSFC", json={}, status=200)
    HeatSourceFunction.create(
        {
            4: {
                "NAME": "HS_Code_Conc",
                "TYPE": "FUNC",
                "OPT_USE_CONC_DATA": True,
                "CEMENT_TYPE": 0,
                "TEMP_FUNC": 1,
                "CEMENT_CONT": 2400,
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["4"]["CEMENT_CONT"] == 2400


@responses.activate
def test_assign_heat_source_create_keyed_by_element_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/HAHS", json={}, status=200)
    AssignHeatSource.create({358: {"FUNC_NAME": "HSF_Adiabatic"}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"358": {"FUNC_NAME": "HSF_Adiabatic"}}}


@responses.activate
def test_pipe_cooling_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/HPCE", json={}, status=200)
    PipeCooling.create(
        {
            1: {
                "NAME": "PC_Row1",
                "DIAMETER": 0.025,
                "COEF": 850,
                "FLOW_RATE": 20,
                "ITEMS": [1, 2, 3, 4, 5, 6],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["ITEMS"] == [1, 2, 3, 4, 5, 6]


@responses.activate
def test_construction_stage_for_hydration_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/HSTG", json={}, status=200)
    ConstructionStageForHydration.create(
        {
            1: {
                "NAME": "HY_CS01",
                "bINITAL_TEMP": True,
                "INITIAL_TEMP": 25,
                "ADD_STEP": [10, 20, 30],
                "ACT_ELEM": ["GR2", "GR1"],
                "ACT_BNGR": ["BNGR3", "BNGR2", "BNGR1"],
                "DACT_BNGR": ["BNGR4"],
                "ACT_LOAD": [{"LOAD_NAME": "LG01", "DAY": "10.000000"}],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["ACT_ELEM"] == ["GR2", "GR1"]
