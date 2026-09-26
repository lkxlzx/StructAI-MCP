import json

import pytest
import responses

from midas_nx.client import UnsupportedMethodError
from midas_nx.design.rc_kds.rebar import (
    BeamMomentCalculationMethod,
    BoundaryElementMethodByWallId,
    DesignForcesForAssignedBeam,
    EqualizeJointBeamRebar,
    LimitMaxRebarRatio,
    ModifyBeamRebarData,
    ModifyBraceRebarData,
    ModifyColumnRebarData,
    ModifyWallMarkData,
    ModifyWallRebarData,
    MomentRedistributionFactor,
    PMCurveCalculationMethod,
    RebarDesignCriteria,
    RebarDesignCriteriaByBeamMember,
    RebarDesignCriteriaByBraceMember,
    RebarDesignCriteriaByColumnMember,
    RebarDesignCriteriaByWallMember,
    RebarExposureCondition,
    TorsionReductionFactor,
)

BASE = "https://x.test:443/gen/DESIGN/RC/KDS-41-20-2022"


# --- 20. MRFT ---------------------------------------------------------------


@responses.activate
def test_moment_redistribution_factor_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, f"{BASE}/MRFT", json={}, status=200)
    MomentRedistributionFactor.create(
        {885: {"FACTOR": 1.0}, 888: {"FACTOR": 0.01}}, client=gen_client
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]
    assert body["885"]["FACTOR"] == 1.0
    assert body["888"]["FACTOR"] == 0.01


@responses.activate
def test_moment_redistribution_factor_get(gen_client):
    responses.add(
        responses.GET,
        f"{BASE}/MRFT",
        json={"MRFT": {"885": {"FACTOR": 1}}},
        status=200,
    )
    result = MomentRedistributionFactor.get(client=gen_client)
    assert result["MRFT"]["885"]["FACTOR"] == 1


# --- 21. TRFT ---------------------------------------------------------------


@responses.activate
def test_torsion_reduction_factor_update_sends_documented_assign_shape(gen_client):
    responses.add(responses.PUT, f"{BASE}/TRFT", json={}, status=200)
    TorsionReductionFactor.update({888: {"FACTOR": 1.0}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"888": {"FACTOR": 1.0}}}


@responses.activate
def test_torsion_reduction_factor_delete_uses_the_per_id_url(gen_client):
    responses.add(responses.DELETE, f"{BASE}/TRFT/888", json={}, status=200)
    TorsionReductionFactor.delete([888], client=gen_client)
    sent = responses.calls[0].request
    assert sent.url.endswith("/888")
    assert sent.body is None


# --- 22. MCMB ---------------------------------------------------------------


@responses.activate
def test_beam_moment_calculation_method_create(gen_client):
    responses.add(responses.POST, f"{BASE}/MCMB", json={}, status=200)
    BeamMomentCalculationMethod.create({888: {"CALC_METHOD": "EACH"}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["888"]["CALC_METHOD"] == "EACH"


# --- 23. DFBA ---------------------------------------------------------------


@responses.activate
def test_design_forces_for_assigned_beam_create(gen_client):
    responses.add(responses.POST, f"{BASE}/DFBA", json={}, status=200)
    DesignForcesForAssignedBeam.create(
        {
            859: {"FORCE_TYPE": "Subdivided Forces"},
            860: {"FORCE_TYPE": "Member Forces"},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]
    assert body["859"]["FORCE_TYPE"] == "Subdivided Forces"
    assert body["860"]["FORCE_TYPE"] == "Member Forces"


# --- 24. PMDM ---------------------------------------------------------------


@responses.activate
def test_pm_curve_calculation_method_create(gen_client):
    responses.add(responses.POST, f"{BASE}/PMDM", json={}, status=200)
    PMCurveCalculationMethod.create({915: {"CALC_METHOD": "P"}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["915"]["CALC_METHOD"] == "P"


# --- 25. WMAK ---------------------------------------------------------------


@responses.activate
def test_modify_wall_mark_data_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, f"{BASE}/WMAK", json={}, status=200)
    ModifyWallMarkData.create(
        {1: {"MARKNAME": "W200", "WID_LIST": [1, 2]}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Assign": {"1": {"MARKNAME": "W200", "WID_LIST": [1, 2]}}
    }


# --- 26. BEMW ---------------------------------------------------------------


@responses.activate
def test_boundary_element_method_by_wall_id_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, f"{BASE}/BEMW", json={}, status=200)
    BoundaryElementMethodByWallId.create(
        {
            1: {
                "BBNDR_ELEM_METHOD": True,
                "NMETHOD_TYPE": "Displacement Based Method",
                "BBOT_STOR": True,
                "STOR_NAME": "B2",
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]["1"]
    assert body["NMETHOD_TYPE"] == "Displacement Based Method"
    assert body["STOR_NAME"] == "B2"


# --- 27. REXC ---------------------------------------------------------------


@responses.activate
def test_rebar_exposure_condition_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, f"{BASE}/REXC", json={}, status=200)
    RebarExposureCondition.create(
        {17: {"EXPOSURE": "Dry"}, 49: {"EXPOSURE": "Etc"}}, client=gen_client
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]
    assert body["17"]["EXPOSURE"] == "Dry"
    assert body["49"]["EXPOSURE"] == "Etc"


# --- 28. LMRR (GET/PUT/DELETE only) -----------------------------------------


@responses.activate
def test_limit_max_rebar_ratio_update_sends_documented_assign_shape(gen_client):
    responses.add(responses.PUT, f"{BASE}/LMRR", json={}, status=200)
    LimitMaxRebarRatio.update(
        {1: {"RHOW": 0.04, "RHOC": 0.03, "RHOR": 0.03}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Assign": {"1": {"RHOW": 0.04, "RHOC": 0.03, "RHOR": 0.03}}
    }


@responses.activate
def test_limit_max_rebar_ratio_create_raises_before_any_http_call(gen_client):
    with pytest.raises(UnsupportedMethodError):
        LimitMaxRebarRatio.create(
            {1: {"RHOW": 0.04, "RHOC": 0.03, "RHOR": 0.03}}, client=gen_client
        )
    assert len(responses.calls) == 0


# --- 29. DCRM-BEAM -----------------------------------------------------------


@responses.activate
def test_rebar_design_criteria_by_beam_member_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, f"{BASE}/DCRM-BEAM", json={}, status=200)
    RebarDesignCriteriaByBeamMember.create(
        {
            885: {
                "MAIN_REBAR": "D22",
                "STIRRUPS": "D10",
                "STIRRUP_ARRANGEMENT": 4,
                "SIDE_BAR": "D13",
                "DT": 0.05,
                "DB": 0.05,
                "DOUBLY_REBAR": True,
                "DOUBLY_K": 1,
                "SPACING_LIMIT": True,
                "SPLICED_BARS": "50%",
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]["885"]
    assert body["MAIN_REBAR"] == "D22"
    assert body["STIRRUP_ARRANGEMENT"] == 4
    assert body["SPLICED_BARS"] == "50%"


@responses.activate
def test_rebar_design_criteria_by_beam_member_get_response_key_is_dcrmb(gen_client):
    responses.add(
        responses.GET,
        f"{BASE}/DCRM-BEAM",
        json={"DCRMB": {"885": {"MAIN_REBAR": "D4"}}},
        status=200,
    )
    result = RebarDesignCriteriaByBeamMember.get(client=gen_client)
    assert result["DCRMB"]["885"]["MAIN_REBAR"] == "D4"


# --- 30. DCRM-COLUMN ---------------------------------------------------------


@responses.activate
def test_rebar_design_criteria_by_column_member_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, f"{BASE}/DCRM-COLUMN", json={}, status=200)
    RebarDesignCriteriaByColumnMember.create(
        {
            915: {
                "MAIN_REBAR": "D22",
                "TIES_SPIRALS": "D10",
                "ARRANGEMENT_Y": 3,
                "ARRANGEMENT_Z": 3,
                "DO": 0.05,
                "SPACING_LIMIT": True,
                "SPLICED_BARS": "50%",
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]["915"]
    assert body["ARRANGEMENT_Y"] == 3
    assert body["ARRANGEMENT_Z"] == 3


# --- 31. DCRM-BRACE -----------------------------------------------------------


@responses.activate
def test_rebar_design_criteria_by_brace_member_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, f"{BASE}/DCRM-BRACE", json={}, status=200)
    RebarDesignCriteriaByBraceMember.create(
        {
            934: {
                "MAIN_REBAR": "D22",
                "TIES_SPIRALS": "D10",
                "ARRANGEMENT_Y": 2,
                "ARRANGEMENT_Z": 2,
                "DO": 0.05,
                "SPACING_LIMIT": True,
                "SPLICED_BARS": "50%",
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]["934"]
    assert body["MAIN_REBAR"] == "D22"


@responses.activate
def test_rebar_design_criteria_by_brace_member_get_response_key_is_dcrmr(gen_client):
    responses.add(
        responses.GET,
        f"{BASE}/DCRM-BRACE",
        json={"DCRMR": {"934": {"MAIN_REBAR": "D4"}}},
        status=200,
    )
    result = RebarDesignCriteriaByBraceMember.get(client=gen_client)
    assert result["DCRMR"]["934"]["MAIN_REBAR"] == "D4"


# --- 32. DCRM-WALL -----------------------------------------------------------


@responses.activate
def test_rebar_design_criteria_by_wall_member_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, f"{BASE}/DCRM-WALL", json={}, status=200)
    RebarDesignCriteriaByWallMember.create(
        {
            976: {
                "ITEMS": [
                    {
                        "STORY": "1F",
                        "VERTICAL_REBAR": "D13",
                        "HORIZONTAL_REBAR": "D10",
                        "END_REBAR": "D13",
                        "BE_HORZ_REBAR": "D10",
                        "BE_HORZ_SPACE": 0.2,
                        "BE_VERT_SPACE": 0.1,
                        "DE": 0.05,
                        "DW": 0.05,
                    },
                    {
                        "STORY": "B1",
                        "VERTICAL_REBAR": "D4",
                        "HORIZONTAL_REBAR": "D10",
                        "END_REBAR": "D5",
                        "BE_HORZ_REBAR": "D13",
                        "BE_HORZ_SPACE": 0.2,
                        "BE_VERT_SPACE": 0.2,
                        "DE": 0.05,
                        "DW": 0.05,
                    },
                ]
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Assign"]["976"]
    assert body["ITEMS"][0]["STORY"] == "1F"
    assert body["ITEMS"][0]["VERTICAL_REBAR"] == "D13"
    assert body["ITEMS"][1]["STORY"] == "B1"
    assert body["ITEMS"][1]["BE_VERT_SPACE"] == 0.2


# --- 33. DCRE -----------------------------------------------------------------


@responses.activate
def test_rebar_design_criteria_create_sends_beam_column_wall_groups(gen_client):
    responses.add(responses.POST, f"{BASE}/DCRE", json={}, status=200)
    RebarDesignCriteria.create(
        {
            1: {
                "BEAM": {
                    "MAIN_REBAR": ["D22"],
                    "STIRRUPS": "D10",
                    "STIRRUP_ARRANGEMENT": 2,
                    "SIDE_BAR": "D13",
                    "DT": 0,
                    "DB": 0,
                    "DOUBLY_REBAR": True,
                    "DOUBLY_K": 1,
                    "SPACING_LIMIT": True,
                    "SPLICED_BARS": "50%",
                },
                "COLUMN": {
                    "MAIN_REBAR": ["D22"],
                    "TIES_SPIRALS": "D10",
                    "ARRANGEMENT_Y": 2,
                    "ARRANGEMENT_Z": 2,
                    "DO": 0,
                    "SPACING_LIMIT": True,
                    "SPLICED_BARS": "50%",
                },
                "WALL": {
                    "VERTICAL_REBAR": ["D10", "D13"],
                    "HORIZONTAL_REBAR": "D10",
                    "END_REBAR": "D13",
                    "BE_HORZ_REBAR": "D10",
                    "BE_HORZ_SPACE": 0.2,
                    "BE_VERT_SPACE": 0.1,
                    "DE": 0.05,
                    "DW": 0.05,
                    "MATERIAL_BY_DIAMETER": False,
                    "ADDITIONAL_WALL_DATA": {
                        "OUT_OF_PLANE_BENDING": False,
                        "VERTICAL_REBAR_SPACING": ["@100", "@150", "@200"],
                        "HORIZONTAL_REBAR_SPACING_FROM": 0.05,
                        "END_REBAR_METHOD": 3,
                        "DIST1": 0.3,
                        "DIST2": 0.15,
                        "DIST3": 0.1,
                    },
                },
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assign = json.loads(sent.body)["Assign"]["1"]
    assert assign["BEAM"]["MAIN_REBAR"] == ["D22"]
    assert assign["COLUMN"]["ARRANGEMENT_Y"] == 2
    assert assign["WALL"]["ADDITIONAL_WALL_DATA"]["DIST1"] == 0.3
    assert assign["WALL"]["ADDITIONAL_WALL_DATA"]["VERTICAL_REBAR_SPACING"] == [
        "@100",
        "@150",
        "@200",
    ]


# --- 34. DCREM -----------------------------------------------------------------


@responses.activate
def test_equalize_joint_beam_rebar_select_all_true(gen_client):
    responses.add(responses.POST, f"{BASE}/DCREM", json={}, status=200)
    EqualizeJointBeamRebar.create({1: {"SELECT_ALL": True}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {"SELECT_ALL": True}}}


@responses.activate
def test_equalize_joint_beam_rebar_selected_members_by_node(gen_client):
    responses.add(responses.POST, f"{BASE}/DCREM", json={}, status=200)
    EqualizeJointBeamRebar.create(
        {
            1: {
                "SELECT_ALL": False,
                "SELECTED_MEMBERS": {
                    "347": {"ELEM_LIST": [925, 926]},
                    "364": {"ELEM_LIST": [922, 924]},
                },
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    members = json.loads(sent.body)["Assign"]["1"]["SELECTED_MEMBERS"]
    assert members["347"]["ELEM_LIST"] == [925, 926]
    assert len(members["364"]["ELEM_LIST"]) == 2


# --- 35. REBB -------------------------------------------------------------------


@responses.activate
def test_modify_beam_rebar_data_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, f"{BASE}/REBB", json={}, status=200)
    sector = {
        "vMAIN_BAR_TOP": [],
        "vMAIN_BAR_BOT": [],
        "SHEAR_BAR": {"NAME": "D10", "LEG": 2, "DIST": 0.1},
        "SKIN_BAR_NAME": "",
        "SKIN_BAR_NUM": 2,
    }
    ModifyBeamRebarData.create(
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
    items = json.loads(sent.body)["Assign"]["211"]["ITEMS"]
    assert items[0]["BAR_SECTOR_I"]["SHEAR_BAR"]["NAME"] == "D10"
    assert items[0]["MAIN_BAR_DC_TOP"] == 0.07


@responses.activate
def test_modify_beam_rebar_data_create_sub_section_with_elems(gen_client):
    responses.add(responses.POST, f"{BASE}/REBB", json={}, status=200)
    sector = {
        "vMAIN_BAR_TOP": [{"LAYER": 1, "NAME": "D22", "NUM": 4}],
        "vMAIN_BAR_BOT": [{"LAYER": 1, "NAME": "D22", "NUM": 3}],
        "SHEAR_BAR": {"NAME": "D10", "LEG": 2, "DIST": 0.1},
    }
    ModifyBeamRebarData.create(
        {
            211: {
                "ITEMS": [
                    {
                        "CREATE_SUB_SECTION": True,
                        "ELEMS": {"TO": "1to160"},
                        "BAR_SECTOR_I": sector,
                        "BAR_SECTOR_M": sector,
                        "BAR_SECTOR_J": sector,
                        "MAIN_BAR_DC_TOP": 0.07,
                        "MAIN_BAR_DC_BOT": 0.07,
                    }
                ]
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    item = json.loads(sent.body)["Assign"]["211"]["ITEMS"][0]
    assert item["ELEMS"] == {"TO": "1to160"}
    assert item["BAR_SECTOR_I"]["vMAIN_BAR_TOP"][0]["NAME"] == "D22"


# --- 36. REBC (full CRUD — NOT POST-only, unlike ch24's /db/REBC) --------------


@responses.activate
def test_modify_column_rebar_data_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, f"{BASE}/REBC", json={}, status=200)
    ModifyColumnRebarData.create(
        {
            1: {
                "ITEMS": [
                    {
                        "CREATE_SUB_SECTION": False,
                        "MAIN_BAR": {
                            "NAME": "D19",
                            "NUM": 8,
                            "ROW": 3,
                            "USE_CORNER": False,
                        },
                        "SHEAR_BAR_END": {
                            "NAME": "D10",
                            "LEG_Y": 2,
                            "LEG_Z": 2,
                            "DIST": 100,
                        },
                        "SHEAR_BAR_CEN": {
                            "NAME": "D10",
                            "LEG_Y": 2,
                            "LEG_Z": 2,
                            "DIST": 200,
                        },
                        "DO": 40,
                        "HOOP_TYPE": "Ties",
                        "HOOK_TYPE": 0,
                    }
                ]
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    item = json.loads(sent.body)["Assign"]["1"]["ITEMS"][0]
    assert item["MAIN_BAR"]["NUM"] == 8
    assert item["SHEAR_BAR_END"]["DIST"] == 100


@responses.activate
def test_modify_column_rebar_data_supports_get_put_delete(gen_client):
    """Critical regression check: this chapter's REBC (#36) is full CRUD,
    unlike ch24's /db/REBC (POST-only) — GET/PUT/DELETE must not raise."""
    responses.add(
        responses.GET,
        f"{BASE}/REBC",
        json={"REBC": {"1": {"ITEMS": []}}},
        status=200,
    )
    responses.add(responses.PUT, f"{BASE}/REBC", json={}, status=200)
    responses.add(responses.DELETE, f"{BASE}/REBC/1", json={}, status=200)

    get_result = ModifyColumnRebarData.get(client=gen_client)
    assert get_result["REBC"]["1"]["ITEMS"] == []

    ModifyColumnRebarData.update(
        {
            1: {
                "ITEMS": [
                    {
                        "MAIN_BAR": {"NAME": "D19", "NUM": 8, "ROW": 3, "USE_CORNER": False},
                        "SHEAR_BAR_END": {"NAME": "D10", "LEG_Y": 2, "LEG_Z": 2, "DIST": 100},
                        "SHEAR_BAR_CEN": {"NAME": "D10", "LEG_Y": 2, "LEG_Z": 2, "DIST": 200},
                        "DO": 40,
                    }
                ]
            }
        },
        client=gen_client,
    )
    ModifyColumnRebarData.delete([1], client=gen_client)
    assert len(responses.calls) == 3


# --- 37. REBW ---------------------------------------------------------------------


@responses.activate
def test_modify_wall_rebar_data_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, f"{BASE}/REBW", json={}, status=200)
    ModifyWallRebarData.create(
        {
            1: {
                "ITEMS": [
                    {
                        "CREATE_SUB_WALL_ID": True,
                        "SUB_WALL_ID": 1,
                        "STORY": {"FROM": "2F", "TO": "Roof"},
                        "VERTICAL_REBAR": {"NAME": "D19", "DIST": 222},
                        "HORIZONTAL_REBAR": {"NAME": "D16", "DIST": 200},
                        "USE_END_REBAR": True,
                        "END_REBAR": {"NAME": "D25", "NUM": 2, "DIST": 150},
                        "BE_HORIZONTAL_REBAR": {"NAME": "D19", "DIST": 222},
                        "BOUNDARY_ELEMENT_LENGTH": 222,
                        "CONCRETE_FACE_TO_CENTER_OF_REBAR": {"DW": 50, "DE": 50},
                        "USE_MODEL_THICKNESS": False,
                        "THICKNESS": 1000,
                    }
                ]
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    item = json.loads(sent.body)["Assign"]["1"]["ITEMS"][0]
    assert item["SUB_WALL_ID"] == 1
    assert item["STORY"] == {"FROM": "2F", "TO": "Roof"}
    assert item["THICKNESS"] == 1000


# --- 38. REBR -----------------------------------------------------------------------


@responses.activate
def test_modify_brace_rebar_data_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, f"{BASE}/REBR", json={}, status=200)
    ModifyBraceRebarData.create(
        {
            1: {
                "ITEMS": [
                    {
                        "CREATE_SUB_SECTION": False,
                        "MAIN_BAR": {"NAME": "D22", "NUM": 4, "ROW": 2},
                        "SHEAR_BAR_END": {
                            "NAME": "D7",
                            "LEG_Y": 2,
                            "LEG_Z": 2,
                            "DIST": 300,
                        },
                        "SHEAR_BAR_CEN": {
                            "NAME": "D22",
                            "LEG_Y": 3,
                            "LEG_Z": 3,
                            "DIST": 300,
                        },
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
    assert "USE_CORNER" not in item["MAIN_BAR"]
    assert item["HOOP_TYPE"] == "Spirals"


@responses.activate
def test_modify_brace_rebar_data_get_response_key_is_rebr(gen_client):
    responses.add(
        responses.GET,
        f"{BASE}/REBR",
        json={"REBR": {"1": {"ITEMS": []}}},
        status=200,
    )
    result = ModifyBraceRebarData.get(client=gen_client)
    assert result["REBR"]["1"]["ITEMS"] == []
