import json

import pytest
import responses

from midas_nx.client import UnsupportedMethodError
from midas_nx.db.dynamic_loads import (
    DynamicNodalLoad,
    GroundAcceleration,
    MultipleSupportExcitation,
    ResponseSpectrumFunction,
    ResponseSpectrumLoadCase,
    TimeHistoryFunction,
    TimeHistoryGlobalControl,
    TimeHistoryGlobalControlHyperS,
    TimeHistoryLoadCase,
    TimeHistoryLoadCaseHyperS,
    TimeHistoryOutputOptionHyperS,
    TimeVaryingStaticLoad,
)


@responses.activate
def test_response_spectrum_function_create_user_defined_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/SPFC", json={}, status=200)
    ResponseSpectrumFunction.create(
        {
            1: {
                "NAME": "RS_func",
                "iTYPE": 1,
                "SCALE": 1,
                "GRAV": 9.806,
                "aFUNC": [{"PERIOD": 0, "VALUE": 0.11}, {"PERIOD": 0.06, "VALUE": 0.308}],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["aFUNC"][0]["VALUE"] == 0.11


@responses.activate
def test_response_spectrum_load_case_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/SPLC", json={}, status=200)
    ResponseSpectrumLoadCase.create(
        {1: {"NAME": "LC_RS_XY", "DIR": "XY", "SCALE": 1, "PMFT": 1, "aFUNCNAME": ["RS_func"]}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["aFUNCNAME"] == ["RS_func"]


@responses.activate
def test_time_history_global_control_create_sends_documented_assign_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/THGC", json={}, status=200)
    TimeHistoryGlobalControl.create(
        {1: {"GNT": 0, "ILT": 0, "bPCF": True, "MAXNS": 10, "MAXIT": 10}}, client=civil_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["GNT"] == 0


@responses.activate
def test_time_history_global_control_also_works_on_gen_client(gen_client):
    # Not Civil-only despite the chapter's bridge-design framing — route +
    # /info both answer on Gen NX too, live-checked 2026-07-29.
    responses.add(responses.POST, "https://x.test:443/gen/db/THGC", json={}, status=200)
    TimeHistoryGlobalControl.create({1: {"GNT": 0}}, client=gen_client)
    assert len(responses.calls) == 1


@responses.activate
def test_time_history_global_control_hyper_s_update_sends_documented_assign_shape(civil_client):
    responses.add(responses.PUT, "https://x.test:443/civil/db/THGC-M1", json={}, status=200)
    TimeHistoryGlobalControlHyperS.update(
        {
            1: {
                "GEO_NONL_TYPE": 1,
                "INIT_LOAD_TYPE": 0,
                "ITER_PARAM": {"PERMIT_FAIL": True, "MAX_ITER": 30},
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["ITER_PARAM"]["MAX_ITER"] == 30


@responses.activate
def test_time_history_global_control_hyper_s_create_raises_before_any_http_call(civil_client):
    with pytest.raises(UnsupportedMethodError):
        TimeHistoryGlobalControlHyperS.create({1: {"GEO_NONL_TYPE": 0}}, client=civil_client)
    assert len(responses.calls) == 0


@responses.activate
def test_time_history_output_option_hyper_s_update_sends_documented_assign_shape(civil_client):
    responses.add(responses.PUT, "https://x.test:443/civil/db/THOO-M1", json={}, status=200)
    TimeHistoryOutputOptionHyperS.update(
        {
            1: {
                "OUT_OPT": {"HINGE_OUT": 1, "COMMON_OPT": False, "FIBER_OUT": 1},
                "RESULT_SELECTION": {"ENERGY_RESULT": True},
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["OUT_OPT"]["HINGE_OUT"] == 1


@responses.activate
def test_time_history_load_case_create_linear_modal_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/THIS", json={}, status=200)
    TimeHistoryLoadCase.create(
        {
            1: {
                "COMMON": {
                    "NAME": "TH_Linear_Modal",
                    "iATYPE": 1,
                    "iAMETHOD": 1,
                    "iTHTYPE": 1,
                    "ENDTIME": 30.0,
                    "INC": 0.01,
                    "iOUT": 1,
                    "INITMETHOD": "INIT",
                    "iMDTYPE": 1,
                },
                "DALL": 0.05,
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["COMMON"]["NAME"] == "TH_Linear_Modal"


@responses.activate
def test_time_history_load_case_hyper_s_create_sends_documented_assign_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/THIS-M1", json={}, status=200)
    TimeHistoryLoadCaseHyperS.create(
        {
            1: {
                "NAME": "LC_NONLINEAR_MODAL_TRANS",
                "ANAL_CASE": {"ANAL_TYPE": 1, "ANAL_METHOD": 0, "TH_TYPE": 0},
                "ENDTIME": 10,
                "TIME_INC": 0.01,
                "OUTPUT_STEP": 1,
                "INIT_METHOD": "INIT",
                "USE_INIT_LOAD": True,
                "DAMPING": {"DAMPING_METHOD": 0, "ALL_DAMPING_RATIO": 0.05},
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["ANAL_CASE"]["ANAL_TYPE"] == 1


@responses.activate
def test_time_history_function_create_sinusoidal_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/THFC", json={}, status=200)
    TimeHistoryFunction.create(
        {
            3: {
                "NAME": "Sinusoidal_1Hz",
                "FUNCTYPE": 2,
                "iTYPE": 1,
                "GRAV": 9.806,
                "CONS_A": 0.05,
                "CONS_C": 0.01,
                "FREQUENCY": 1.0,
                "DAMP_FACTOR": 0.1,
                "PHASE_ANGLE": 0.0,
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["3"]["FUNCTYPE"] == 2


@responses.activate
def test_ground_acceleration_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/THGA", json={}, status=200)
    GroundAcceleration.create(
        {
            1: {
                "NAME": "GA_ElCentro",
                "FUNCX": "ElCentro_EW",
                "SCALEX": 1.0,
                "FUNCY": "ElCentro_NS",
                "SCALEY": 0.85,
                "FUNCZ": "ElCentro_UD",
                "SCALEZ": 0.65,
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["FUNCX"] == "ElCentro_EW"


@responses.activate
def test_dynamic_nodal_load_create_keyed_by_node_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/THNL", json={}, status=200)
    DynamicNodalLoad.create(
        {
            1: {
                "ITEMS": [
                    {
                        "ID": 1,
                        "THLCNAME": "TH01_Linear_Modal",
                        "FUNC_NAME": "SIN_1Hz",
                        "DIR": "Y",
                        "ARRIVAL_TIME": 0.0,
                        "SCALE_FACTOR": 1.0,
                    }
                ]
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["ITEMS"][0]["FUNC_NAME"] == "SIN_1Hz"


@responses.activate
def test_time_varying_static_load_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/THSL", json={}, status=200)
    TimeVaryingStaticLoad.create(
        {
            1: {
                "THIS_LCNAME": "TH01_Linear_Modal",
                "SLOAD": "SW",
                "THIS_FUNCNAME": "NormFunc_SW",
                "SCALE": 1.0,
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["SLOAD"] == "SW"


@responses.activate
def test_multiple_support_excitation_create_keyed_by_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/THMS", json={}, status=200)
    MultipleSupportExcitation.create(
        {
            1: {
                "ITEMS": [
                    {
                        "ID": 1,
                        "LCNAME": "TH01_Linear_Modal",
                        "FUNCX": "ElCentro_EW",
                        "SCALEX": 1.0,
                        "FUNCY": "ElCentro_NS",
                        "SCALEY": 1.0,
                        "FUNCZ": "ElCentro_UD",
                        "SCALEZ": 0.667,
                    }
                ]
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["ITEMS"][0]["FUNCX"] == "ElCentro_EW"
