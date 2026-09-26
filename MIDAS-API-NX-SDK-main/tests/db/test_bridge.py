import json

import pytest
import responses

from midas_nx.client import ProductMismatchError
from midas_nx.db.bridge import (
    BridgeGirderDiagram,
    FcmCamberControl,
    GeneralCamberControl,
    UnknownLoadFactorConstraint,
)


@responses.activate
def test_bridge_girder_diagram_create_sends_documented_assign_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/GSBG", json={}, status=200)
    BridgeGirderDiagram.create(
        {
            1: {
                "NAME": "Dgrm Group1",
                "BATCH": True,
                "BODY_ELEM_GRUP_K": 1,
                "ALLSTAGE": False,
                "DGRM_TYPE": 0,
                "BSTRSCOMP": 6,
                "BSTRSCOMP_SUB": 3,
                "_7TH_DOF_TYPE": 0,
                "SCALEFACTOR": 1,
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["_7TH_DOF_TYPE"] == 0


@responses.activate
def test_bridge_girder_diagram_is_civil_only(gen_client):
    with pytest.raises(ProductMismatchError):
        BridgeGirderDiagram.create({1: {"NAME": "x"}}, client=gen_client)
    assert len(responses.calls) == 0


@responses.activate
def test_general_camber_control_create_sends_base_items(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/GCMB", json={}, status=200)
    GeneralCamberControl.create(
        {
            1: {
                "bSTART_PT_ZERO": True,
                "GCMB_BASE_ITEMS": [
                    {"GRUP_NAME": "CS_0", "DIRECTION": "+DX"},
                    {"GRUP_NAME": "CS_1", "DIRECTION": "+DX"},
                ],
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["GCMB_BASE_ITEMS"][1]["GRUP_NAME"] == "CS_1"


@responses.activate
def test_fcm_camber_control_create_sends_documented_assign_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/CAMB", json={}, status=200)
    FcmCamberControl.create(
        {
            1: {
                "BODY_GROUP_NAME": "FSM",
                "SUPP_GROUP_NAME": "PSC-BN",
                "KEYSEG_GROUP_NAME": "Key-SegK1~K5",
            }
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["SUPP_GROUP_NAME"] == "PSC-BN"


@responses.activate
def test_unknown_load_factor_constraint_create_equality_and_inequality(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/ULFC", json={}, status=200)
    UnknownLoadFactorConstraint.create(
        {
            2: {
                "NAME": "Ele-03",
                "TYPE": "BEAM",
                "OBJ_ID": 3,
                "POINT": 1,
                "COMP": 4,
                "EQ": False,
                "bUB": True,
                "UB_VALUE": -220,
                "bLB": True,
                "LB_VALUE": -230,
            },
            3: {
                "NAME": "Node-07",
                "TYPE": "REAC",
                "OBJ_ID": 7,
                "POINT": 4,
                "COMP": 1,
                "EQ": True,
                "bVALUE": True,
                "VALUE": 500,
                "OtherObject": 0,
            },
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]
    assert body["2"]["UB_VALUE"] == -220
    assert body["3"]["VALUE"] == 500


@responses.activate
def test_unknown_load_factor_constraint_delete_uses_per_id_urls(civil_client):
    for item_id in (2, 3):
        responses.add(
            responses.DELETE, f"https://x.test:443/civil/db/ULFC/{item_id}", json={}, status=200
        )

    UnknownLoadFactorConstraint.delete([2, 3], client=civil_client)

    assert [call.request.url for call in responses.calls] == [
        "https://x.test:443/civil/db/ULFC/2",
        "https://x.test:443/civil/db/ULFC/3",
    ]
