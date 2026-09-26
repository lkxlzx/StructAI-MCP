import json

import pytest
import responses

from midas_nx.client import UnsupportedMethodError
from midas_nx.db.pushover import (
    AssignPushoverHingeProperties,
    IgnoreElementsForPushoverInitialLoad,
    PushoverAnalysisControlData,
    PushoverAnalysisControlDataHyperS,
    PushoverLoadCase,
    PushoverLoadCaseHyperS,
)


@responses.activate
def test_pushover_analysis_control_data_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/POGD", json={}, status=200)
    PushoverAnalysisControlData.create(
        {
            1: {
                "GEOMNONLINEAR_TYPE": "NONE",
                "INITLOADMETHOD": "PERFORM_ANAL",
                "INITLOAD": [],
                "NONL_OPT": {"bPERMITFAIL": True, "SUBSTEP": 10, "MAXITER": 10},
                "NODECONNECTIVITY": "PINNED",
                "bSHOWGRAPHAFTER": True,
                "bSHOWGRAPGHDURING": False,
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["NONL_OPT"]["MAXITER"] == 10


@responses.activate
def test_pushover_analysis_control_data_hyper_s_update_sends_nested_iter_ctrl(civil_client):
    responses.add(responses.PUT, "https://x.test:443/civil/db/POGD-M1", json={}, status=200)
    PushoverAnalysisControlDataHyperS.update(
        {
            1: {
                "GEO_NONL_TYPE": 0,
                "INIT_LOAD_TYPE": 0,
                "IGNORE_ELEM": True,
                "ITER_CTRL": {
                    "MAX_ITER": 30,
                    "NORM_CTRL": {
                        "DISP": {"OPT_USE": True, "VALUE": 0.001},
                        "FORCE": {"OPT_USE": False},
                        "ENERGY": {"OPT_USE": False},
                    },
                    "STIFF_UPD_SCHEME": 0,
                    "ITER_BEF_UPDATE": 5,
                },
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["ITER_CTRL"]["NORM_CTRL"]["DISP"]["VALUE"] == 0.001


@responses.activate
def test_pushover_analysis_control_data_hyper_s_create_raises_before_any_http_call(civil_client):
    with pytest.raises(UnsupportedMethodError):
        PushoverAnalysisControlDataHyperS.create({1: {"GEO_NONL_TYPE": 0}}, client=civil_client)
    assert len(responses.calls) == 0


@responses.activate
def test_ignore_elements_for_pushover_initial_load_create_keyed_by_element_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/IEPI", json={}, status=200)
    IgnoreElementsForPushoverInitialLoad.create(
        {59: {"B_IGNORE": True}, 60: {"B_IGNORE": True}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"59": {"B_IGNORE": True}, "60": {"B_IGNORE": True}}}


@responses.activate
def test_assign_pushover_hinge_properties_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/PHGE", json={}, status=200)
    AssignPushoverHingeProperties.create(
        {15: {"ID": 1, "TYPE": "BEAM", "HINGE_TYPE": "Myz_15", "FIBER_KEY": 0}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["15"]["HINGE_TYPE"] == "Myz_15"


@responses.activate
def test_pushover_load_case_create_mode_shape_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/POLC", json={}, status=200)
    PushoverLoadCase.create(
        {
            1: {
                "LCNAME": "Mode_X",
                "INCRE_STEP": 10,
                "bCONS_PDELTA": True,
                "INCRE_METHOD": "DISP",
                "STIFF_RATIO": 0,
                "LIMITDEFORMANGLE": 10,
                "DISPCTRLOPTION": "NODE",
                "MASTERNODE": 134,
                "MASTERDIRECTION": "DX",
                "MASTERMAXDISP": 1,
                "LOADPATTERNTYPE": "MODE",
                "LOADPATTERN": [{"MODE": 1, "SF": 1}],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["LOADPATTERN"][0]["MODE"] == 1


@responses.activate
def test_pushover_load_case_hyper_s_update_load_control_variant(civil_client):
    responses.add(responses.PUT, "https://x.test:443/civil/db/POLC-M1", json={}, status=200)
    PushoverLoadCaseHyperS.update(
        {
            1: {
                "LCNAME": "PUSH_LOAD_X",
                "INCRE_STEP": 20,
                "NLTYPE": "PDELTA",
                "bUSEINITIAL": True,
                "bREACOUTPUT": True,
                "INCRE_METHOD": "LOAD",
                "CTRL_OPT": {"STEPCTRLOPTION": "INC_FUNC", "INCFUNC_NAME": "POFC_01", "STIFF_RATIO": 80},
                "LOADPATTERNTYPE": "LOAD",
                "LOADPATTERN": [{"LCNAME": "DEAD", "SF": 1}, {"LCNAME": "LIVE", "SF": 0.5}],
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["CTRL_OPT"]["INCFUNC_NAME"] == "POFC_01"


@responses.activate
def test_pushover_load_case_hyper_s_create_sends_documented_assign_shape(civil_client):
    """This endpoint serves POST, whatever 14_DB_Pushover.md says.

    The chapter normalizes the official article's POST row away as an
    untrimmed copy of another endpoint's template. Live on Civil NX 2026 v2.2
    (2026-08-30) POST created a Pushover Load Case that read back on the
    following GET, so the normalization is the error, not the article.
    """
    responses.add(responses.POST, "https://x.test:443/civil/db/POLC-M1", json={}, status=200)
    PushoverLoadCaseHyperS.create({1: {"LCNAME": "x"}}, client=civil_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {"LCNAME": "x"}}}
