import json

import responses

from midas_nx.db.misc_loads import (
    IgnoreElementForLoadCase,
    InitialElementForce,
    InitialForceControlData,
    InitialForceGeometricStiffness,
    LoadSequenceNonlinear,
    PreCompositeSection,
    SettlementGroup,
    SettlementLoadCase,
    WaveLoad,
)


@responses.activate
def test_settlement_group_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/SMPT", json={}, status=200)
    SettlementGroup.create({1: {"NAME": "SG1", "SETTLE": 25, "ITEMS": [100, 101]}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {"NAME": "SG1", "SETTLE": 25, "ITEMS": [100, 101]}}}


@responses.activate
def test_settlement_load_case_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/SMLC", json={}, status=200)
    SettlementLoadCase.create(
        {1: {"NAME": "SMLC1", "DESC": "", "FACTOR": 1.2, "MIN": 1, "MAX": 1, "ST_GROUPS": ["SG1", "SG2"]}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["ST_GROUPS"] == ["SG1", "SG2"]


@responses.activate
def test_pre_composite_section_create_sends_documented_assign_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/PLCB", json={}, status=200)
    PreCompositeSection.create({1: {"LCNAME_ITEM": ["DL(BC)1", "DL(BC)3"]}}, client=civil_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {"LCNAME_ITEM": ["DL(BC)1", "DL(BC)3"]}}}


@responses.activate
def test_load_sequence_nonlinear_create_preserves_order(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/LDSQ", json={}, status=200)
    LoadSequenceNonlinear.create({1: {"LCNAME_ITEM": ["DL(BC)4", "DL(AC)"]}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["LCNAME_ITEM"] == ["DL(BC)4", "DL(AC)"]


@responses.activate
def test_wave_load_create_sends_documented_assign_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/WVLD", json={}, status=200)
    WaveLoad.create(
        {
            1: {
                "NAME": "WV_100Y",
                "VERT_COORD": "GLOBAL_Z",
                "DENSITY": 10.05,
                "DEPTH": 30.0,
                "COEF": {"TYPE": "CONST"},
                "CHAR": {"THEORY": "STOKES", "DIR": 0.0, "HEIGHT": 12.5, "CHAR_TYPE": "PERIOD", "PERIOD": 14.0},
                "PROF": {"GRID_DATA": [{"D": 0.0, "V": 0.5}]},
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["CHAR"]["THEORY"] == "STOKES"


@responses.activate
def test_ignore_element_for_load_case_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/IELC", json={}, status=200)
    IgnoreElementForLoadCase.create(
        {1: {"ELEMENT": 5, "LCNAME": "DL", "OPT_IGNORE": True}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {"ELEMENT": 5, "LCNAME": "DL", "OPT_IGNORE": True}}}


@responses.activate
def test_initial_force_geometric_stiffness_create_keyed_by_element_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/IFGS", json={}, status=200)
    InitialForceGeometricStiffness.create({9: {"DIR": "GY", "INIT_FORCE": 200}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"9": {"DIR": "GY", "INIT_FORCE": 200}}}


@responses.activate
def test_initial_force_control_data_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/EFCT", json={}, status=200)
    InitialForceControlData.create(
        {
            1: {
                "LCNAME": "DL",
                "bUSECOMB": True,
                "COMB_LIST": [{"LCNAME": "DL", "FACTOR": 1.2}, {"LCNAME": "LL", "FACTOR": 1.0}],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["COMB_LIST"][1]["FACTOR"] == 1.0


@responses.activate
def test_initial_element_force_create_truss_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/INMF", json={}, status=200)
    InitialElementForce.create(
        {2: {"ELEM_TYPE": "TRUSS", "ELEM_KEY": 112, "ELEMENT_FORCES": [1, 2]}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["2"]["ELEMENT_FORCES"] == [1, 2]
