import json

import pytest
import responses

from midas_nx.client import UnsupportedMethodError
from midas_nx.db.analysis_control import (
    AssignBoundaryCombinationHyperS,
    BoundaryChangeAssignment,
    BucklingAnalysisControl,
    ConstructionStageAnalysisControlData,
    ConstructionStageAnalysisControlDataHyperS,
    DefineBoundaryCombinationHyperS,
    EigenvalueAnalysisControl,
    EigenvalueAnalysisControlHyperS,
    HeatOfHydrationAnalysisControl,
    HeatOfHydrationAnalysisControlHyperS,
    MainControlData,
    MainControlDataHyperS,
    MovingLoadAnalysisControl,
    MovingLoadAnalysisControlBS,
    MovingLoadAnalysisControlChina,
    MovingLoadAnalysisControlIndia,
    MovingLoadAnalysisControlTransverse,
    NonlinearAnalysisControlData,
    NonlinearAnalysisControlHyperS,
    PDeltaAnalysisControl,
    SettlementAnalysisControlData,
)


@responses.activate
def test_main_control_data_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/ACTL", json={}, status=200)
    MainControlData.create({1: {"ARDC": True, "ANRC": True, "ITER": 20, "TOL": 0.001}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {"ARDC": True, "ANRC": True, "ITER": 20, "TOL": 0.001}}}


@responses.activate
def test_main_control_data_hyper_s_update_sends_nested_tcelem(civil_client):
    responses.add(responses.PUT, "https://x.test:443/civil/db/ACTL-M1", json={}, status=200)
    MainControlDataHyperS.update(
        {
            1: {
                "BSCHG": "CHANGE",
                "TCELEM": {
                    "NUMINC": 10,
                    "INTOUT": "LAST",
                    "CONVERGENCE": {"DISPL": {"OPT_USE": True, "VALUE": 0.001}, "LOAD": {"OPT_USE": False}},
                },
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["TCELEM"]["CONVERGENCE"]["DISPL"]["VALUE"] == 0.001


@responses.activate
def test_main_control_data_hyper_s_create_raises_before_any_http_call(civil_client):
    with pytest.raises(UnsupportedMethodError):
        MainControlDataHyperS.create({1: {"ARCD": True}}, client=civil_client)
    assert len(responses.calls) == 0


@responses.activate
def test_pdelta_analysis_control_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/PDEL", json={}, status=200)
    PDeltaAnalysisControl.create(
        {1: {"ITER": 5, "TOL": 1e-05, "PDEL_CASES": [{"LCNAME": "A", "FACTOR": 1}]}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["PDEL_CASES"][0]["LCNAME"] == "A"


@responses.activate
def test_buckling_analysis_control_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/BUCK", json={}, status=200)
    BucklingAnalysisControl.create(
        {1: {"MODE_NUM": 12, "OPT_POSITIVE": True, "ITEMS": [{"LCNAME": "A", "FACTOR": 1, "LOAD_TYPE": 0}]}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["MODE_NUM"] == 12


@responses.activate
def test_eigenvalue_analysis_control_create_ritz_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/EIGV", json={}, status=200)
    EigenvalueAnalysisControl.create(
        {
            1: {
                "TYPE": "RITZ",
                "bINCNL": False,
                "iGNUM": 1,
                "vRITZ": [{"KIND": "GROUND", "GROUND": "ACCX", "iNOG": 30}],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["vRITZ"][0]["GROUND"] == "ACCX"


@responses.activate
def test_eigenvalue_analysis_control_hyper_s_update_ritz_variant(civil_client):
    responses.add(responses.PUT, "https://x.test:443/civil/db/EIGV-M1", json={}, status=200)
    EigenvalueAnalysisControlHyperS.update(
        {
            1: {
                "ANAL_TYPE": "RITZ",
                "GLINK_VECTOR": {"OPT_USE": True, "GLINK_NUMBER": 3},
                "RITZ_LOAD": [{"TYPE": "GROUND", "LOAD_NAME": "ACCX", "NUM_OF_GEN": 5}],
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["RITZ_LOAD"][0]["NUM_OF_GEN"] == 5


@responses.activate
def test_eigenvalue_analysis_control_hyper_s_create_raises_before_any_http_call(civil_client):
    with pytest.raises(UnsupportedMethodError):
        EigenvalueAnalysisControlHyperS.create({1: {"ANAL_TYPE": "RITZ"}}, client=civil_client)
    assert len(responses.calls) == 0


@responses.activate
def test_heat_of_hydration_analysis_control_create_effective_modulus_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/HHCT", json={}, status=200)
    HeatOfHydrationAnalysisControl.create(
        {
            1: {
                "FINAL_STAGE": True,
                "OPT_IS_CREEP_SHRINKAGE": True,
                "ITEM": {
                    "TYPE": "BOTH",
                    "CREEP_CALC_METHOD": 1,
                    "M_EFF_MOD": {"PHI1": 0.73, "DAY1": 3, "PHI2": 1, "DAY2": 5},
                },
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["ITEM"]["M_EFF_MOD"]["DAY2"] == 5


@responses.activate
def test_heat_of_hydration_analysis_control_hyper_s_update_sends_convergence(civil_client):
    responses.add(responses.PUT, "https://x.test:443/civil/db/HHCT-M1", json={}, status=200)
    HeatOfHydrationAnalysisControlHyperS.update(
        {
            1: {
                "FINAL_STAGE": False,
                "STAGE_NAME": "Stage 1",
                "ITER": 50,
                "CONVERGENCE": {"DISP": {"OPT_CHECK": True, "VALUE": 0.001}},
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["CONVERGENCE"]["DISP"]["OPT_CHECK"] is True


@responses.activate
def test_heat_of_hydration_analysis_control_hyper_s_create_raises_before_any_http_call(civil_client):
    with pytest.raises(UnsupportedMethodError):
        HeatOfHydrationAnalysisControlHyperS.create({1: {"FINAL_STAGE": True}}, client=civil_client)
    assert len(responses.calls) == 0


@responses.activate
def test_moving_load_analysis_control_create_sends_documented_assign_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVCT", json={}, status=200)
    MovingLoadAnalysisControl.create(
        {1: {"METHOD": "EXACT", "POINT": "INF", "PLATE": "NODAL", "FRAME": "AXIAL"}}, client=civil_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["METHOD"] == "EXACT"


@responses.activate
def test_moving_load_analysis_control_also_works_on_gen_client(gen_client):
    # Not Civil-only despite the chapter's bridge-design framing — route +
    # /info both answer on Gen NX too, live-checked 2026-07-29.
    responses.add(responses.POST, "https://x.test:443/gen/db/MVCT", json={}, status=200)
    MovingLoadAnalysisControl.create({1: {"POINT": "INF"}}, client=gen_client)
    assert len(responses.calls) == 1


@responses.activate
def test_moving_load_analysis_control_china_preserves_conditional_variant_objects(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVCTch", json={}, status=200)
    MovingLoadAnalysisControlChina.create(
        {
            1: {
                "POINT": "INF",
                "UNUMT": 3,
                "PLATE": "NODAL",
                "FRAME": "AXIAL",
                "bIF": True,
                "FREQ": {"USER_F": 0, "SBEM_L": 30},
                # ``BRIDGE2`` is the iCODETYPE=2/3 branch.  Its live schema
                # is object-valued but its BTYPE variants are not one shared
                # TypedDict, so this remains intentionally untyped.
                "BRIDGE2": {"BTYPE": "RAILBRG", "GROUP": "Railway"},
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["FREQ"]["SBEM_L"] == 30
    assert json.loads(sent.body)["Assign"]["1"]["BRIDGE2"]["BTYPE"] == "RAILBRG"


@responses.activate
def test_moving_load_analysis_control_india_create_sends_documented_assign_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVCTid", json={}, status=200)
    MovingLoadAnalysisControlIndia.create(
        {1: {"UNUMT": 3, "PLATE": "NODAL", "FRAME": "AXIAL", "DEPTH": 10, "VHMAX": 10}}, client=civil_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["VHMAX"] == 10


@responses.activate
def test_moving_load_analysis_control_bs_create_sends_documented_assign_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVCTbs", json={}, status=200)
    MovingLoadAnalysisControlBS.create(
        {1: {"UNUMT": 3, "PLATE": "NODAL", "FRAME": "AXIAL", "NUMLANE": 0}}, client=civil_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["NUMLANE"] == 0


@responses.activate
def test_moving_load_analysis_control_transverse_create_sends_documented_assign_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/MVCTtr", json={}, status=200)
    MovingLoadAnalysisControlTransverse.create(
        {1: {"LOAD_POINT_SEL": 1, "NUM_UNIT_LOAD": 3, "ANALYSIS_RESULT": 2}}, client=civil_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["ANALYSIS_RESULT"] == 2


@responses.activate
def test_settlement_analysis_control_data_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/SMCT", json={}, status=200)
    SettlementAnalysisControlData.create(
        {1: {"CONCURRENT_CALC": True, "CONCURRENT_LINK": False}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {"CONCURRENT_CALC": True, "CONCURRENT_LINK": False}}}


@responses.activate
def test_nonlinear_analysis_control_data_create_newton_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/NLCT", json={}, status=200)
    NonlinearAnalysisControlData.create(
        {
            1: {
                "NONLINEAR_TYPE": "GEOM+MATL",
                "ITERATION_METHOD": "NEWTON",
                "NUMBER_STEPS": 1,
                "MAX_ITERATIONS": 30,
                "NEWTON_ITEMS": [
                    {"ITERATION_METHOD": "NEWTON", "LCNAME": "A", "NUMBER_STEPS": 1, "MAX_ITERATIONS": 30}
                ],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["NEWTON_ITEMS"][0]["LCNAME"] == "A"


@responses.activate
def test_nonlinear_analysis_control_hyper_s_update_sends_nested_objects(civil_client):
    responses.add(responses.PUT, "https://x.test:443/civil/db/NLCT-M1", json={}, status=200)
    NonlinearAnalysisControlHyperS.update(
        {
            1: {
                "LC_SCOPE": "ALL",
                "NONLINEAR_TYPE": "GEOM_MATL",
                "ITER_METHOD": "ARC",
                "LOAD_STEPS": {"STEP_MODE": "AUTO", "NUMBER_STEPS": 20, "OUTPUT": "LAST"},
                "CONV_CRITERIA": {"DISP": {"OPT_USE": True, "VALUE": 0.001}},
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["LOAD_STEPS"]["NUMBER_STEPS"] == 20


@responses.activate
def test_nonlinear_analysis_control_hyper_s_create_raises_before_any_http_call(civil_client):
    with pytest.raises(UnsupportedMethodError):
        NonlinearAnalysisControlHyperS.create({1: {"LC_SCOPE": "ALL"}}, client=civil_client)
    assert len(responses.calls) == 0


@responses.activate
def test_construction_stage_analysis_control_data_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/STCT", json={}, status=200)
    ConstructionStageAnalysisControlData.create(
        {
            1: {
                "bLAST_FINAL": False,
                "FINAL_STAGE": "CS1",
                "iINC_NLA": 0,
                "iNLA_TYPE": 0,
                "bINC_PDL": True,
                "bSDLE": True,
                "vSDLE": ["GRID_DL"],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]["1"]
    assert body["FINAL_STAGE"] == "CS1"
    assert body["vSDLE"] == ["GRID_DL"]


@responses.activate
def test_construction_stage_analysis_control_data_hyper_s_update_sends_nested_anal_type(civil_client):
    responses.add(responses.PUT, "https://x.test:443/civil/db/STCT-M1", json={}, status=200)
    ConstructionStageAnalysisControlDataHyperS.update(
        {
            1: {
                "bLAST_FINAL": True,
                "ANAL_TYPE": {"iINC_NLA": 0, "iNLA_TYPE": 1, "bINC_PDL": True, "bINC_TDE": True},
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["ANAL_TYPE"]["iNLA_TYPE"] == 1


@responses.activate
def test_construction_stage_analysis_control_data_hyper_s_create_raises_before_any_http_call(civil_client):
    with pytest.raises(UnsupportedMethodError):
        ConstructionStageAnalysisControlDataHyperS.create({1: {"bLAST_FINAL": True}}, client=civil_client)
    assert len(responses.calls) == 0


@responses.activate
def test_boundary_change_assignment_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/BCCT", json={}, status=200)
    BoundaryChangeAssignment.create(
        {
            1: {
                "bSPT": True,
                "bSPR": True,
                "vBOUNDARY": [{"BGCNAME": "BGL1", "vBG": ["BG1", "BG2"]}],
                "vLOADANAL": [{"TYPE": "ST", "BGCNAME": "BGL1", "LCNAME": "LC1"}],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["vBOUNDARY"][0]["vBG"] == ["BG1", "BG2"]


@responses.activate
def test_define_boundary_combination_hyper_s_create_sends_documented_assign_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/BCGD-M1", json={}, status=200)
    DefineBoundaryCombinationHyperS.create(
        {1: {"BCG_NAME": "Support_BCG", "GROUP_LIST": ["Fixed_Support", "Elastic_Link"]}}, client=civil_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["GROUP_LIST"] == ["Fixed_Support", "Elastic_Link"]


@responses.activate
def test_assign_boundary_combination_hyper_s_create_sends_documented_assign_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/BCGA-M1", json={}, status=200)
    AssignBoundaryCombinationHyperS.create(
        {
            1: {
                "BC_ASSIGN": [
                    {"ANAL_TYPE": "ST", "LCNAME": "DL", "BGCNAME": "Support_BCG"},
                    {"ANAL_TYPE": "EIGV", "BGCNAME": "Stage_BCG"},
                ],
                "BC_SELECT": ["SECF", "NSPR"],
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["BC_SELECT"] == ["SECF", "NSPR"]
