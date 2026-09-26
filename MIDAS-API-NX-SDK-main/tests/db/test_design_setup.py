import json

import responses

from midas_nx.db.design import (
    BeamRebar,
    BraceRebar,
    ColumnRebar,
    DesignMemberAssignment,
    FrameDefinition,
    LimitingSlendernessRatio,
    ModifyMemberType,
    ModifyWallMark,
    RcDesignCode,
    RebarCheckInput,
    SteelDesignCode,
    UnbracedLength,
    WallRebar,
)


@responses.activate
def test_rc_design_code_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/DCON", json={}, status=200)
    RcDesignCode.create({1: {"DGNCODE": "KCI-USD12"}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {"DGNCODE": "KCI-USD12"}}}


@responses.activate
def test_rc_design_code_get(gen_client):
    responses.add(
        responses.GET,
        "https://x.test:443/gen/db/DCON",
        json={"DCON": {"1": {"DGNCODE": "KCI-USD12"}}},
        status=200,
    )
    result = RcDesignCode.get(client=gen_client)
    assert result["DCON"]["1"]["DGNCODE"] == "KCI-USD12"


@responses.activate
def test_steel_design_code_update_sends_documented_assign_shape(gen_client):
    responses.add(responses.PUT, "https://x.test:443/gen/db/DSTL", json={}, status=200)
    SteelDesignCode.update({1: {"DGNCODE": "Eurocode3-2:05"}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["DGNCODE"] == "Eurocode3-2:05"


@responses.activate
def test_rebar_check_input_create_column_and_beam_mixed(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/RCHK", json={}, status=200)
    RebarCheckInput.create(
        {
            1: {
                "MEMBTYPE": "COLUMN",
                "ENVTYPE": 0,
                "COLM": {
                    "vLAYER": [
                        {
                            "INDEX": 1,
                            "dDc": 0.1,
                            "vPOSITION": [
                                {"POSITION": "P1", "BAR_NUM": 24, "BAR_NAME1": "#4", "BAR_NAME2": ""}
                            ],
                        }
                    ],
                    "SUB_BAR": {
                        "SUBBAR_NAME": "#4",
                        "SUBBAR_DIST": 0.1,
                        "SUBBAR_NUM": 12,
                        "SUBBAR_NAME_Y": "#4",
                        "SUBBAR_NAME_Z": "#4",
                        "SUBBAR_NUM_Y": 12,
                        "SUBBAR_NUM_Z": 12,
                    },
                },
            },
            2: {
                "MEMBTYPE": "BEAM",
                "ENVTYPE": 1,
                "BEAM": {
                    "vMAIN": [
                        {
                            "SECTOR": "I",
                            "POS_TOP_LAYERS": [
                                {"LAYER": 1, "dD": 0.1, "BAR_NUM": 12, "BAR_NAME1": "#5", "BAR_NAME2": ""}
                            ],
                            "POS_BOT_LAYERS": [
                                {"LAYER": 1, "dD": 0.1, "BAR_NUM": 12, "BAR_NAME1": "#7", "BAR_NAME2": ""}
                            ],
                        }
                    ],
                    "vSUB_BAR": [
                        {
                            "SECTOR": "I",
                            "dSUB_BARNUM": 2,
                            "SUB_BARNAME": "#6",
                            "dSUB_BARDIST": 0.1,
                            "dSUB_BARANGLE": 90,
                        }
                    ],
                },
            },
        },
        client=civil_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]
    assert body["1"]["COLM"]["vLAYER"][0]["vPOSITION"][0]["BAR_NUM"] == 24
    assert body["2"]["BEAM"]["vMAIN"][0]["SECTOR"] == "I"


@responses.activate
def test_unbraced_length_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/LENG", json={}, status=200)
    UnbracedLength.create(
        {
            21: {
                "LY": 9.464111,
                "LZ": 4,
                "LB": 4,
                "bNOTUSE": False,
                "bAUTOCALC": False,
                "LT": 9.464111,
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["21"]["LY"] == 9.464111


@responses.activate
def test_design_member_assignment_create_two_members(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/MEMB", json={}, status=200)
    DesignMemberAssignment.create(
        {
            1: {"AELEM": [36, 48, 46, 49, 47]},
            2: {"AELEM": [32, 43], "bREVERSE": True},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]
    assert body["1"]["AELEM"] == [36, 48, 46, 49, 47]
    assert body["2"]["bREVERSE"] is True


@responses.activate
def test_frame_definition_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/DCTL", json={}, status=200)
    FrameDefinition.create(
        {
            1: {
                "FRAMEX": "Braced Non-sway",
                "FRAMEY": "Unbraced Sway",
                "bAUTOKF": True,
                "DT": "3D",
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["FRAMEY"] == "Unbraced Sway"


@responses.activate
def test_limiting_slenderness_ratio_create_multiple_elements(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/LTSR", json={}, status=200)
    LimitingSlendernessRatio.create(
        {
            602: {"bNOTCHECK": False, "COMP": 150, "TENS": 400},
            651: {"bNOTCHECK": False, "COMP": 200, "TENS": 300},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]
    assert body["602"]["COMP"] == 150
    assert body["651"]["TENS"] == 300


@responses.activate
def test_modify_member_type_create_column_beam_brace(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/MBTP", json={}, status=200)
    ModifyMemberType.create(
        {
            160: {"TYPE": "COLUMN"},
            188: {"TYPE": "BEAM"},
            376: {"TYPE": "BRACE"},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]
    assert body["160"]["TYPE"] == "COLUMN"
    assert body["376"]["TYPE"] == "BRACE"


@responses.activate
def test_modify_wall_mark_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/WMAK", json={}, status=200)
    ModifyWallMark.create(
        {1: {"MARKNAME": "W1", "WID_LIST": [1, 5, 8]}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["WID_LIST"] == [1, 5, 8]


@responses.activate
def test_beam_rebar_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/REBB", json={}, status=200)
    sector = {
        "vMAIN_BAR_TOP": [],
        "vMAIN_BAR_BOT": [],
        "SHEAR_BAR": {"NAME": "D10", "LEG": 2, "DIST": 0.1},
        "SKIN_BAR_NAME": "",
        "SKIN_BAR_NUM": 2,
    }
    BeamRebar.create(
        {
            211: {
                "ITEMS": [
                    {
                        "ID": 0,
                        "BAR_SECTOR_I": sector,
                        "BAR_SECTOR_M": sector,
                        "BAR_SECTOR_J": sector,
                        "MAIN_BAR_DC_TOP": 0.07,
                        "MAIN_BAR_DC_BOT": 0.07,
                        "bSAME_SIZE_TOP_BOT": True,
                        "bSAME_SIZE_IMJ": True,
                        "bSAME_SIZE_LAYER": True,
                    }
                ]
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    item = json.loads(sent.body)["Assign"]["211"]["ITEMS"][0]
    assert item["MAIN_BAR_DC_TOP"] == 0.07
    assert item["BAR_SECTOR_I"]["SHEAR_BAR"]["LEG"] == 2


@responses.activate
def test_column_rebar_create_sends_documented_assign_shape(gen_client):
    # Field names confirmed live 2026-08-27 -- the old shape (CREATE_SUB_SECTION/
    # MAIN_BAR/DO/HOOK_TYPE) answered "Wrong Field"; this shape round-tripped a
    # full POST->GET->PUT->DELETE->GET cycle. See ColumnMainBarItem's docstring.
    responses.add(responses.POST, "https://x.test:443/gen/db/REBC", json={}, status=200)
    ColumnRebar.create(
        {
            1: {
                "ITEMS": [
                    {
                        "ID": 0,
                        "vMAIN_BAR": [
                            {
                                "NAME": "D19",
                                "NUM": 8,
                                "ROW": 3,
                                "D0": 0.04,
                                "bUSE_CORNER": False,
                                "NAME_CORNER": "D19",
                            }
                        ],
                        "SHEAR_BAR_END": {"NAME": "D10", "LEG_Y": 2, "LEG_Z": 2, "DIST": 100},
                        "SHEAR_BAR_CEN": {"NAME": "D10", "LEG_Y": 2, "LEG_Z": 2, "DIST": 200},
                        "HOOP_TYPE": 1,
                        "bSAME_SPACE_END_CEN": True,
                        "NUM_BAR_BC_JOINT": 0,
                    }
                ]
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    item = json.loads(sent.body)["Assign"]["1"]["ITEMS"][0]
    assert item["vMAIN_BAR"][0]["NUM"] == 8
    assert item["SHEAR_BAR_END"]["LEG_Y"] == 2


@responses.activate
def test_column_rebar_supports_full_crud(gen_client):
    # Confirmed live 2026-08-27: not POST-only as the manual previously
    # claimed -- full CRUD, including DELETE actually removing the record.
    responses.add(responses.GET, "https://x.test:443/gen/db/REBC", json={}, status=200)
    responses.add(responses.PUT, "https://x.test:443/gen/db/REBC", json={}, status=200)
    responses.add(responses.DELETE, "https://x.test:443/gen/db/REBC/1", json={}, status=200)
    ColumnRebar.get(client=gen_client)
    ColumnRebar.update({1: {"ITEMS": []}}, client=gen_client)
    ColumnRebar.delete([1], client=gen_client)
    assert len(responses.calls) == 3


@responses.activate
def test_wall_rebar_create_sends_documented_assign_shape(gen_client):
    # Field names confirmed live 2026-07-29 against a real production Gen NX
    # model — the manual's own Specifications tables for this endpoint don't
    # match the server; see WallRebarItem's docstring.
    responses.add(responses.POST, "https://x.test:443/gen/db/REBW", json={}, status=200)
    WallRebar.create(
        {
            1: {
                "ITEMS": [
                    {
                        "bUSE_MODEL_THICK": False,
                        "THICK": 1000,
                        "DW": 50,
                        "DE": 50,
                        "VER_BAR": {"NAME": "D19", "DIST": 222},
                        "HOR_BAR": {"NAME": "D16", "DIST": 200},
                        "END_BAR": {"NAME": "D25", "DIST": 150},
                        "NUM_END_BAR": 2,
                        "BE_HOR_BAR": {"NAME": "D19", "DIST": 222},
                        "BE_LENGTH": 222,
                        "vSTORY_NAME": ["2F", "Roof"],
                    }
                ]
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    item = json.loads(sent.body)["Assign"]["1"]["ITEMS"][0]
    assert item["vSTORY_NAME"] == ["2F", "Roof"]
    assert item["DW"] == 50


@responses.activate
def test_wall_rebar_delete_sends_null_assign(gen_client):
    responses.add(responses.DELETE, "https://x.test:443/gen/db/REBW/1", json={}, status=200)
    WallRebar.delete([1], client=gen_client)
    sent = responses.calls[0].request
    assert sent.url.endswith("/1")
    assert sent.body is None


@responses.activate
def test_brace_rebar_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/REBR", json={}, status=200)
    BraceRebar.create(
        {
            1: {
                "ITEMS": [
                    {
                        "CREATE_SUB_SECTION": False,
                        "MAIN_BAR": {"NAME": "D22", "NUM": 4, "ROW": 2},
                        "SHEAR_BAR_END": {"NAME": "D7", "LEG_Y": 2, "LEG_Z": 2, "DIST": 300},
                        "SHEAR_BAR_CEN": {"NAME": "D22", "LEG_Y": 3, "LEG_Z": 3, "DIST": 300},
                        "DO": 0.05,
                        "HOOP_TYPE": "Spirals",
                    }
                ]
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    item = json.loads(sent.body)["Assign"]["1"]["ITEMS"][0]
    assert item["HOOP_TYPE"] == "Spirals"
    assert item["MAIN_BAR"]["NUM"] == 4


@responses.activate
def test_civil_client_can_also_use_design_endpoints(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/DCON", json={}, status=200)
    RcDesignCode.create({1: {"DGNCODE": "AASHTO-LRFD20"}}, client=civil_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["DGNCODE"] == "AASHTO-LRFD20"
