import json

import responses

from midas_nx.db.load_combinations import (
    CuttingLine,
    LoadCombinationCompositeSteelGirder,
    LoadCombinationConcrete,
    LoadCombinationGeneral,
    LoadCombinationSeismic,
    LoadCombinationSRC,
    LoadCombinationSteel,
    PlateCuttingLineDiagram,
)


@responses.activate
def test_load_combination_general_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/LCOM-GEN", json={}, status=200)
    LoadCombinationGeneral.create(
        {
            1: {
                "NAME": "LC1",
                "ACTIVE": "ACTIVE",
                "iTYPE": 0,
                "DESC": "1.2D + 1.0L",
                "vCOMB": [
                    {"ANAL": "CS", "LCNAME": "DeadLoad", "FACTOR": 1.2},
                    {"ANAL": "ST", "LCNAME": "LiveLoad", "FACTOR": 1.0},
                ],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["vCOMB"][1]["FACTOR"] == 1.0


@responses.activate
def test_load_combination_concrete_create_sends_documented_assign_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/LCOM-CONC", json={}, status=200)
    LoadCombinationConcrete.create(
        {
            1: {
                "NAME": "cLCB1",
                "ACTIVE": "STRENGTH",
                "bES": False,
                "iTYPE": 0,
                "vCOMB": [{"ANAL": "CS", "LCNAME": "DeadLoad", "FACTOR": 1.25}],
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["bES"] is False


@responses.activate
def test_load_combination_concrete_also_works_on_gen_client(gen_client):
    # Not Civil-only despite the chapter's framing — live-confirmed 2026-07-29
    # against a real production Gen NX model, see LoadCombinationConcrete's
    # docstring.
    responses.add(responses.POST, "https://x.test:443/gen/db/LCOM-CONC", json={}, status=200)
    LoadCombinationConcrete.create({1: {"NAME": "x", "vCOMB": []}}, client=gen_client)
    assert len(responses.calls) == 1


@responses.activate
def test_load_combination_steel_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/LCOM-STEEL", json={}, status=200)
    LoadCombinationSteel.create(
        {1: {"NAME": "sLCB1", "ACTIVE": "STRENGTH", "iTYPE": 0, "vCOMB": [{"ANAL": "CS", "LCNAME": "DL", "FACTOR": 1.2}]}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["ACTIVE"] == "STRENGTH"


@responses.activate
def test_load_combination_src_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/LCOM-SRC", json={}, status=200)
    LoadCombinationSRC.create(
        {1: {"NAME": "rLCB1", "ACTIVE": "STRENGTH", "iTYPE": 0, "vCOMB": [{"ANAL": "CS", "LCNAME": "DL", "FACTOR": 1.4}]}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["vCOMB"][0]["FACTOR"] == 1.4


@responses.activate
def test_load_combination_composite_steel_girder_create_sends_documented_assign_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/LCOM-STLCOMP", json={}, status=200)
    LoadCombinationCompositeSteelGirder.create(
        {
            1: {
                "NAME": "scLCB1",
                "ACTIVE": "STRENGTH",
                "iTYPE": 0,
                "vCOMB": [{"ANAL": "MV", "LCNAME": "LiveLoad", "FACTOR": 1.75}],
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["vCOMB"][0]["ANAL"] == "MV"


@responses.activate
def test_load_combination_composite_steel_girder_also_works_on_gen_client(gen_client):
    # Not Civil-only despite the chapter's bridge-design framing — route +
    # /info both answer on Gen NX too, live-checked 2026-07-29.
    responses.add(responses.POST, "https://x.test:443/gen/db/LCOM-STLCOMP", json={}, status=200)
    LoadCombinationCompositeSteelGirder.create({1: {"NAME": "x", "vCOMB": []}}, client=gen_client)
    assert len(responses.calls) == 1


@responses.activate
def test_load_combination_seismic_create_srss_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/LCOM-SEISMIC", json={}, status=200)
    LoadCombinationSeismic.create(
        {
            1: {
                "NAME": "S2",
                "ACTIVE": "ACTIVE",
                "iTYPE": 3,
                "vCOMB": [
                    {"ANAL": "RS", "LCNAME": "RX", "FACTOR": 1.0},
                    {"ANAL": "RS", "LCNAME": "RY", "FACTOR": 1.0},
                ],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["iTYPE"] == 3


@responses.activate
def test_cutting_line_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/CUTL", json={}, status=200)
    CuttingLine.create(
        {
            1: {
                "NAME": "Cut-Line#1",
                "DIR": "NORMAL",
                "PT1X": 8.95, "PT1Y": 11.0725, "PT1Z": 1.205,
                "PT2X": 8.95, "PT2Y": -1.0725, "PT2Z": 1.205,
                "R": 255, "G": 0, "B": 0, "TYPE": 0,
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["DIR"] == "NORMAL"


@responses.activate
def test_plate_cutting_line_diagram_create_sends_three_points(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/CLWP", json={}, status=200)
    PlateCuttingLineDiagram.create(
        {
            1: {
                "NAME": "CL1",
                "DIR": "PLANE",
                "PT1X": 0, "PT1Y": 10710, "PT1Z": -1000,
                "PT2X": 0, "PT2Y": 10710, "PT2Z": 0,
                "PT3X": 0, "PT3Y": 9945, "PT3Z": 0,
                "R": 0, "G": 0, "B": 0,
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["PT3Y"] == 9945
