import json

import pytest
import responses

from midas_nx import ope
from midas_nx.client import MidasRequestError

# --- 1. PROJECTSTATUS --------------------------------------------------------


@responses.activate
def test_get_project_status_sends_get_with_no_body(gen_client):
    responses.add(
        responses.GET, "https://x.test:443/gen/ope/PROJECTSTATUS",
        json={"PROJECTSTATUS": {"HEAD": ["Name", "Count", "LastNo."], "DATA": []}}, status=200,
    )
    result = ope.get_project_status(client=gen_client)
    assert result == {"PROJECTSTATUS": {"HEAD": ["Name", "Count", "LastNo."], "DATA": []}}
    sent = responses.calls[0].request
    assert sent.method == "GET"
    assert sent.body is None


# --- 2. DIVIDEELEM ------------------------------------------------------------


@responses.activate
def test_divide_elements_equal_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/DIVIDEELEM", json={}, status=200)
    ope.divide_elements(
        {
            "TARGETS": [1],
            "DIVIDE": {
                "ELEM_TYPE": "Frame",
                "DIV_METHOD": "Equal",
                "OPTION": {"EQUAL_OPTION": {"NUM_X": 10}},
            },
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {
            "TARGETS": [1],
            "DIVIDE": {
                "ELEM_TYPE": "Frame",
                "DIV_METHOD": "Equal",
                "OPTION": {"EQUAL_OPTION": {"NUM_X": 10}},
            },
        }
    }


@responses.activate
def test_divide_elements_parallel_bracing_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/DIVIDEELEM", json={}, status=200)
    ope.divide_elements(
        {
            "DIVIDE": {
                "ELEM_TYPE": "Frame",
                "DIV_METHOD": "ParallelBracing",
                "OPTION": {"PARALLEL_OPTION": {"NUM_OF_DIVISIONS": 3, "MAIN_POST_ELEM": [1, 3]}},
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["DIVIDE"]["OPTION"]["PARALLEL_OPTION"] == {
        "NUM_OF_DIVISIONS": 3,
        "MAIN_POST_ELEM": [1, 3],
    }


@responses.activate
def test_divide_elements_unequal_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/DIVIDEELEM", json={}, status=200)
    ope.divide_elements(
        {
            "TARGETS": [1],
            "DIVIDE": {
                "ELEM_TYPE": "Planar",
                "DIV_METHOD": "Unequal",
                "OPTION": {"UNEQUAL_OPTION": {"DIST_X": "2@2.5", "DIST_Y": "2@3.0"}},
            },
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["DIVIDE"]["OPTION"]["UNEQUAL_OPTION"] == {
        "DIST_X": "2@2.5",
        "DIST_Y": "2@3.0",
    }


@responses.activate
def test_divide_elements_parametric_unequal_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/DIVIDEELEM", json={}, status=200)
    ope.divide_elements(
        {
            "TARGETS": [1],
            "DIVIDE": {
                "ELEM_TYPE": "Solid",
                "DIV_METHOD": "ParametricUnequal",
                "OPTION": {
                    "PARAMETRIC_OPTION": {"RATIO_X": "3@0.3", "RATIO_Y": "4@0.2", "RATIO_Z": "0.1,0.2,0.3"}
                },
            },
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["DIVIDE"]["OPTION"]["PARAMETRIC_OPTION"]["RATIO_Z"] == "0.1,0.2,0.3"


@responses.activate
def test_divide_elements_divide_by_node_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/DIVIDEELEM", json={}, status=200)
    ope.divide_elements(
        {
            "DIVIDE": {
                "ELEM_TYPE": "Frame",
                "DIV_METHOD": "DividebyNode",
                "OPTION": {"BY_NODE_OPTION": {"ELEM_NUM": 5, "NODE_NUM": 12}},
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["DIVIDE"]["OPTION"]["BY_NODE_OPTION"] == {
        "ELEM_NUM": 5,
        "NODE_NUM": 12,
    }


# --- 3. SECTPROP --------------------------------------------------------------


@responses.activate
def test_get_section_properties_sends_get_with_no_body(gen_client):
    responses.add(
        responses.GET, "https://x.test:443/gen/ope/SECTPROP",
        json={"SECTPROP": {"1": {"HEAD": ["Property", "Value", "Unit"], "DATA": []}}}, status=200,
    )
    result = ope.get_section_properties(client=gen_client)
    assert result == {"SECTPROP": {"1": {"HEAD": ["Property", "Value", "Unit"], "DATA": []}}}
    sent = responses.calls[0].request
    assert sent.method == "GET"
    assert sent.body is None


# --- 4. USLC -------------------------------------------------------------------


@responses.activate
def test_use_load_combinations_sends_argument(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/USLC", json={}, status=200)
    ope.use_load_combinations(
        {
            "LCOM_LIST": [{"TYPE": "STEEL", "NAME": "sLCB1"}],
            "PREFIX": "N",
            "POSITION": "STEEL",
            "LOADS": {"SELF_WEIGHT": True, "NODAL_LOAD": True, "BEAM_LOAD": True, "FLOOR_LOAD": True},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {
            "LCOM_LIST": [{"TYPE": "STEEL", "NAME": "sLCB1"}],
            "PREFIX": "N",
            "POSITION": "STEEL",
            "LOADS": {"SELF_WEIGHT": True, "NODAL_LOAD": True, "BEAM_LOAD": True, "FLOOR_LOAD": True},
        }
    }


# --- 5. LINEBMLD ---------------------------------------------------------------


@responses.activate
def test_create_line_beam_load_conload_with_eccentricity(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/LINEBMLD", json={}, status=200)
    ope.create_line_beam_load(
        {
            "LCNAME": "CONLOAD_14",
            "TYPE": "CONLOAD",
            "TARGET": {"METHOD": 0, "NODE": [56, 66]},
            "ECCEN": {
                "USE": True,
                "TYPE": 0,
                "DIR": "LZ",
                "I_END": -0.15,
                "J_END": 0.15,
                "USE_J_END": True,
            },
            "LOAD": {"DIR": "GZ", "TYPE": 1, "D": [0.75, 1.35, 1.95, 2.55], "P": [-1, -2, -3, -4]},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["ECCEN"]["USE_J_END"] is True


@responses.activate
def test_create_line_beam_load_uniload_with_copy(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/LINEBMLD", json={}, status=200)
    ope.create_line_beam_load(
        {
            "LCNAME": "UNILOAD_17",
            "TYPE": "UNILOAD",
            "TARGET": {"METHOD": 0, "NODE": [78, 88]},
            "LOAD": {"DIR": "GZ", "TYPE": 0, "D": [0.25, 0.85], "P": [-3]},
            "COPY": {"USE": True, "AXIS": "Y", "DIST": "10@3.0"},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["COPY"] == {"USE": True, "AXIS": "Y", "DIST": "10@3.0"}


@responses.activate
def test_create_line_beam_load_trapressure_with_additional_height(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/LINEBMLD", json={}, status=200)
    ope.create_line_beam_load(
        {
            "LCNAME": "TRAPRESSURE_01",
            "TYPE": "TRAPRESSURE",
            "TARGET": {"METHOD": 0, "NODE": [10, 20]},
            "ADD_H": {"USE": True, "I_END": 0.5, "J_END": 0.8, "USE_J_END": True},
            "LOAD": {"DIR": "LZ", "TYPE": 0, "D": [0, 1, 2, 3], "P": [-1, -2, -3, -4]},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["ADD_H"] == {
        "USE": True, "I_END": 0.5, "J_END": 0.8, "USE_J_END": True
    }


@responses.activate
def test_create_line_beam_load_curved(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/LINEBMLD", json={}, status=200)
    ope.create_line_beam_load(
        {
            "LCNAME": "CURVED_01",
            "TYPE": "CURVED",
            "TARGET": {"METHOD": 1, "ELEM": [5, 6, 7]},
            "LOAD": {"DIR": "GZ", "A": 1.0, "B": 2.0, "C": 3.0},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["LOAD"] == {"DIR": "GZ", "A": 1.0, "B": 2.0, "C": 3.0}


# --- 6. AUTOMESH -----------------------------------------------------------------


@responses.activate
def test_auto_mesh_line_elements_basic(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/AUTOMESH", json={}, status=200)
    ope.auto_mesh(
        {
            "MESHER": {"TARGETS": [1400, 1397, 1398, 1399]},
            "MESH_SIZE": {"LENGTH": 1},
            "PROPERTY": {"MATERIAL": 1, "THICKNESS": 1},
            "DOMAIN_NAME": {"NAME": "frame"},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {
            "MESHER": {"TARGETS": [1400, 1397, 1398, 1399]},
            "MESH_SIZE": {"LENGTH": 1},
            "PROPERTY": {"MATERIAL": 1, "THICKNESS": 1},
            "DOMAIN_NAME": {"NAME": "frame"},
        }
    }


@responses.activate
def test_auto_mesh_planar_elements_with_interior_options(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/AUTOMESH", json={}, status=200)
    ope.auto_mesh(
        {
            "MESHER": {
                "METHOD": "PlanarElements",
                "TARGETS": [1402],
                "TYPE": "Quadandtriangle",
                "MESH_INNER_DOMAIN": True,
                "INCLUDE_INTERIOR_NODES": {"OPT_CHECK": True, "OPTION": "User", "VALUE": [1]},
                "INCLUDE_INTERIOR_LINES": {"OPT_CHECK": True, "OPTION": "User", "VALUE": [2]},
                "INCLUDE_BOUNDARY_CONNECTIVITY": True,
            },
            "MESH_SIZE": {"DIV": 3},
            "PROPERTY": {
                "ELEMENT_TYPE": "Plate",
                "ELEMENT_SUB_TYPE": {"TYPE": "Thick", "WITH_DRILLING_DOF": True},
                "MATERIAL": 1,
                "THICKNESS": 1,
            },
            "DOMAIN_NAME": {"NAME": "Plate2"},
            "ADDITIONAL_OPTION": {"DELETE_LINE_ELEM": False, "SUBDIVIDE_LINE_ELEM": True},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)
    assert body["Argument"]["MESHER"]["INCLUDE_INTERIOR_NODES"] == {
        "OPT_CHECK": True, "OPTION": "User", "VALUE": [1]
    }
    assert body["Argument"]["PROPERTY"]["ELEMENT_SUB_TYPE"]["WITH_DRILLING_DOF"] is True


# --- 7. SSPS -----------------------------------------------------------------------


@responses.activate
def test_convert_surface_spring_point_spring_linear(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/SSPS", json={}, status=200)
    ope.convert_surface_spring(
        {
            "CONVERT_TO": "POINT_SPRING",
            "GROUP_NAME": "B1",
            "NODE_ELEMS": {"KEYS": [61, 62, 63]},
            "ELEMENT": {"TYPE": "FRAME", "WIDTH": 10},
            "BOUNDARY": {"TYPE": "LINEAR", "STIFF": [1000, 2000, 3000], "bDAMP": True, "DAMP": [1, 2, 3]},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {
            "CONVERT_TO": "POINT_SPRING",
            "GROUP_NAME": "B1",
            "NODE_ELEMS": {"KEYS": [61, 62, 63]},
            "ELEMENT": {"TYPE": "FRAME", "WIDTH": 10},
            "BOUNDARY": {"TYPE": "LINEAR", "STIFF": [1000, 2000, 3000], "bDAMP": True, "DAMP": [1, 2, 3]},
        }
    }


@responses.activate
def test_convert_surface_spring_elastic_link_tens(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/SSPS", json={}, status=200)
    ope.convert_surface_spring(
        {
            "CONVERT_TO": "ELASTIC_LINK",
            "GROUP_NAME": "B1",
            "NODE_ELEMS": {"KEYS": [71, 72, 73]},
            "ELEMENT": {"TYPE": "SOLID_FACE", "FACE": 1},
            "BOUNDARY": {"TYPE": "TENS", "DIR": 7, "SUBGRADE": 5000, "LENGTH": 0.5},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["BOUNDARY"] == {
        "TYPE": "TENS", "DIR": 7, "SUBGRADE": 5000, "LENGTH": 0.5
    }


@responses.activate
def test_convert_surface_spring_comp(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/SSPS", json={}, status=200)
    ope.convert_surface_spring(
        {
            "CONVERT_TO": "POINT_SPRING",
            "NODE_ELEMS": {"KEYS": [81, 82]},
            "ELEMENT": {"TYPE": "SOLID_NODE"},
            "BOUNDARY": {"TYPE": "COMP", "DIR": 3, "SUBGRADE": 4000},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["BOUNDARY"] == {"TYPE": "COMP", "DIR": 3, "SUBGRADE": 4000}


@responses.activate
def test_convert_surface_spring_multi(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/SSPS", json={}, status=200)
    ope.convert_surface_spring(
        {
            "CONVERT_TO": "ELASTIC_LINK",
            "NODE_ELEMS": {"KEYS": [91, 92]},
            "ELEMENT": {"TYPE": "SOLID_FACE", "FACE": 2},
            "BOUNDARY": {
                "TYPE": "MULTI",
                "STIFF": [1000, 2000, 3000],
                "bDAMP": False,
                "DAMP": [0, 0, 0],
                "PHU": 500,
                "LENGTH": 0.3,
            },
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["BOUNDARY"]["PHU"] == 500


# --- 8. EDMP -----------------------------------------------------------------------


@responses.activate
def test_change_property_nsm_auto(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/EDMP", json={}, status=200)
    ope.change_property(
        {
            "NODE_ELEMS": {"KEYS": [1, 2, 3]},
            "TYPE": "NSM",
            "AUTO": True,
            "CODE": "Korean Standard",
            "PARAMETER": 0.5,
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {
            "NODE_ELEMS": {"KEYS": [1, 2, 3]},
            "TYPE": "NSM",
            "AUTO": True,
            "CODE": "Korean Standard",
            "PARAMETER": 0.5,
        }
    }


@responses.activate
def test_change_property_vsr_manual(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/EDMP", json={}, status=200)
    ope.change_property(
        {"NODE_ELEMS": {"KEYS": [1, 2, 3]}, "TYPE": "VSR", "AUTO": False, "H_VS": 1.0},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {"NODE_ELEMS": {"KEYS": [1, 2, 3]}, "TYPE": "VSR", "AUTO": False, "H_VS": 1.0}
    }


# --- 9. STOR -----------------------------------------------------------------------


@responses.activate
def test_calculate_story_sends_eccentricity_settings(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/STOR", json={}, status=200)
    ope.calculate_story(
        {
            "SEIS_ECC": {"INC_SEIS_ECC": True, "SEIS_ECC_VALUE": 5},
            "WIND_ECC": {"INC_WIND_ECC": True, "WIND_ECC_VALUE": 15},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {
            "SEIS_ECC": {"INC_SEIS_ECC": True, "SEIS_ECC_VALUE": 5},
            "WIND_ECC": {"INC_WIND_ECC": True, "WIND_ECC_VALUE": 15},
        }
    }


# --- 10. STORY_PARAM -----------------------------------------------------------------


@responses.activate
def test_get_story_check_parameter_sends_get_with_no_body(gen_client):
    responses.add(
        responses.GET, "https://x.test:443/gen/ope/STORY_PARAM",
        json={"STORY_PARAM": {"COUNTRY_CODE": "NTC2012"}}, status=200,
    )
    result = ope.get_story_check_parameter(client=gen_client)
    assert result == {"STORY_PARAM": {"COUNTRY_CODE": "NTC2012"}}
    sent = responses.calls[0].request
    assert sent.method == "GET"
    assert sent.body is None


@responses.activate
def test_set_story_check_parameter_sends_country_code(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/STORY_PARAM", json={}, status=200)
    ope.set_story_check_parameter({"COUNTRY_CODE": "KBC2009"}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": {"COUNTRY_CODE": "KBC2009"}}


# --- 11. STORY_IRR_PARAM -------------------------------------------------------------


@responses.activate
def test_get_story_irregularity_check_parameter_sends_get_with_no_body(gen_client):
    responses.add(
        responses.GET, "https://x.test:443/gen/ope/STORY_IRR_PARAM",
        json={"STORY_IRR_PARAM": {"COUNTRY_CODE": "NSR-10"}}, status=200,
    )
    result = ope.get_story_irregularity_check_parameter(client=gen_client)
    assert result == {"STORY_IRR_PARAM": {"COUNTRY_CODE": "NSR-10"}}
    sent = responses.calls[0].request
    assert sent.method == "GET"
    assert sent.body is None


@responses.activate
def test_set_story_irregularity_check_parameter_sends_all_fields(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/STORY_IRR_PARAM", json={}, status=200)
    ope.set_story_irregularity_check_parameter(
        {
            "COUNTRY_CODE": "NTCS2023",
            "STORY_DRIFT_METHOD": "Max. Drift of Outer Extreme Points",
            "STORY_STIFFNESS_METHOD": "1 / Story Drift Ratio",
            "SEISMIC_BEHAVIOR_FACTOR": "3 or below",
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {
            "COUNTRY_CODE": "NTCS2023",
            "STORY_DRIFT_METHOD": "Max. Drift of Outer Extreme Points",
            "STORY_STIFFNESS_METHOD": "1 / Story Drift Ratio",
            "SEISMIC_BEHAVIOR_FACTOR": "3 or below",
        }
    }


# --- 12. STORYPROP ----------------------------------------------------------------------


@responses.activate
def test_get_story_properties_sends_unit_and_format_settings(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/STORYPROP", json={}, status=200)
    ope.get_story_properties(
        {"FORCE_UNIT": "KN", "LENGTH_UNIT": "M", "FORMAT": "Default", "PLACE": 4}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {"FORCE_UNIT": "KN", "LENGTH_UNIT": "M", "FORMAT": "Default", "PLACE": 4}
    }


# --- 13. MEMB --------------------------------------------------------------------------


@responses.activate
def test_assign_members_manual_selection(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/MEMB", json={}, status=200)
    ope.assign_members(
        {
            "ASSIGN_TYPE": "MANUAL",
            "SELECTION_TYPE": "SELECTION",
            "ELEM_LIST": [640, 692],
            "ALLOW_SINGLE": False,
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {
            "ASSIGN_TYPE": "MANUAL",
            "SELECTION_TYPE": "SELECTION",
            "ELEM_LIST": [640, 692],
            "ALLOW_SINGLE": False,
        }
    }


@responses.activate
def test_assign_members_auto_all(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/MEMB", json={}, status=200)
    ope.assign_members(
        {"ASSIGN_TYPE": "AUTO", "SELECTION_TYPE": "ALL", "ALLOW_SINGLE": True}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {"ASSIGN_TYPE": "AUTO", "SELECTION_TYPE": "ALL", "ALLOW_SINGLE": True}
    }


# --- 14. GUSTFACTOR --------------------------------------------------------------------


@responses.activate
def test_calculate_gust_factor_rigid_structure(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/GUSTFACTOR", json={}, status=200)
    ope.calculate_gust_factor(
        {
            "WIND_CODE": "KDS(41-12:2022)",
            "STRUCTURE_TYPE": "RIGID",
            "RIGID_PARAM": {"EXP_CATEGORY": "C", "ROOF_HEIGHT": 30, "BREADTH_X": 20, "BREADTH_Y": 15},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {
            "WIND_CODE": "KDS(41-12:2022)",
            "STRUCTURE_TYPE": "RIGID",
            "RIGID_PARAM": {"EXP_CATEGORY": "C", "ROOF_HEIGHT": 30, "BREADTH_X": 20, "BREADTH_Y": 15},
        }
    }


@responses.activate
def test_calculate_gust_factor_flexible_structure(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/GUSTFACTOR", json={}, status=200)
    ope.calculate_gust_factor(
        {
            "WIND_CODE": "KDS(41-12:2022)",
            "STRUCTURE_TYPE": "FLEXIBLE",
            "FLEXIBLE_PARAM": {
                "EXP_CATEGORY": "B",
                "BASIC_WIND_SPEED": 38,
                "IMPORTANCE_FACTOR": 1,
                "TOPOGRAPHIC_EFFECT": {"OPT_USE": True, "KZT": 1.1},
                "DIRECTION_FACTOR_X": 0.85,
                "DIRECTION_FACTOR_Y": 0.85,
                "BREADTH_X": 32,
                "BREADTH_Y": 24,
                "STORY_HEIGHT_MAX": 72,
                "FREQUENCY_X": 0.42,
                "FREQUENCY_Y": 0.48,
                "DAMPING": 0.03,
                "TOTAL_MASS": 85000,
                "MX": 82000,
                "MY": 80500,
                "VIBRATION": 1,
            },
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)
    assert body["Argument"]["FLEXIBLE_PARAM"]["TOPOGRAPHIC_EFFECT"] == {"OPT_USE": True, "KZT": 1.1}
    assert body["Argument"]["FLEXIBLE_PARAM"]["DAMPING"] == 0.03


# --- 15. LCOM-GEN -----------------------------------------------------------------------


@responses.activate
def test_generate_load_combination_general_kds_concrete(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/LCOM-GEN", json={}, status=200)
    ope.generate_load_combination_general(
        {
            "OPTION": "ADD",
            "ADD_ENVELOPE": True,
            "CODE_SELECTION": "CONCRETE",
            "DGNCODE": "KDS 41 20 : 2022",
            "RS_SCALE_FACTOR": [
                {"LOAD_CASE": "RX(RS)", "FACTOR": 1},
                {"LOAD_CASE": "RY(RS)", "FACTOR": 1},
            ],
            "WIND_LOAD_COMB": {
                "PARAMETERS": [
                    {
                        "BUILDING_TYPE": "HIGH",
                        "WIND_LOAD_CASE": {"ALONG": "WX", "ACROSS": "WX(A)", "TORSION": "WX(T)"},
                        "GUST_FACTOR": 2.2,
                        "KAPPA_FACTOR": 0.55,
                    }
                ],
                "TORSION_DIR": "BOTH",
            },
            "ORTHO_EFFECT": {"OPT_USE": True, "TYPE": "100_30", "LOAD_GROUP": ["RX(RS)", "RY(RS)"]},
            "ADDITIONAL_LOAD": {
                "SPECIAL_LOAD": {
                    "OPT_USE": True,
                    "VERTICAL_LOAD_FACTOR": 0.2,
                    "SDS": 0.5,
                    "OVER_STRENGTH_FACTOR": [
                        {"LOAD_CASE": "RX(RS)", "FACTOR": 2.5},
                        {"LOAD_CASE": "RY(RS)", "FACTOR": 2.5},
                    ],
                },
                "VERTICAL_LOAD": {"OPT_USE": True, "FORCE_FACTOR": 0.2},
            },
            "UNDERGROUND_LOAD": {"OPT_USE": False},
            "CS_ANALYSIS": False,
            "PRESTRESS_LOSS": False,
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)
    assert body["Argument"]["CODE_SELECTION"] == "CONCRETE"
    assert body["Argument"]["DGNCODE"] == "KDS 41 20 : 2022"
    assert body["Argument"]["CS_ANALYSIS"] is False


@responses.activate
def test_generate_load_combination_general_aik_src2k(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/LCOM-GEN", json={}, status=200)
    ope.generate_load_combination_general(
        {
            "OPTION": "ADD",
            "DGNCODE": "AIK-SRC2K",
            "RS_SCALE_FACTOR": [
                {"LOAD_CASE": "RX(RS)", "FACTOR": 1},
                {"LOAD_CASE": "RY(RS)", "FACTOR": 1},
            ],
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {
            "OPTION": "ADD",
            "DGNCODE": "AIK-SRC2K",
            "RS_SCALE_FACTOR": [
                {"LOAD_CASE": "RX(RS)", "FACTOR": 1},
                {"LOAD_CASE": "RY(RS)", "FACTOR": 1},
            ],
        }
    }


# --- 16. LCOM-CONC -----------------------------------------------------------------------


@responses.activate
def test_generate_load_combination_concrete(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/LCOM-CONC", json={}, status=200)
    ope.generate_load_combination_concrete(
        {
            "OPTION": "ADD",
            "DGNCODE": "KDS 41 20 : 2022",
            "RS_SCALE_FACTOR": [{"LOAD_CASE": "RX(RS)", "FACTOR": 1}],
            "UNDERGROUND_LOAD": {"OPT_USE": False},
            "CS_ANALYSIS": False,
            "PRESTRESS_LOSS": False,
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {
            "OPTION": "ADD",
            "DGNCODE": "KDS 41 20 : 2022",
            "RS_SCALE_FACTOR": [{"LOAD_CASE": "RX(RS)", "FACTOR": 1}],
            "UNDERGROUND_LOAD": {"OPT_USE": False},
            "CS_ANALYSIS": False,
            "PRESTRESS_LOSS": False,
        }
    }


# --- 17. LCOM-STEEL -----------------------------------------------------------------------


@responses.activate
def test_generate_load_combination_steel(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/LCOM-STEEL", json={}, status=200)
    ope.generate_load_combination_steel(
        {
            "OPTION": "ADD",
            "DGNCODE": "KDS 41 30 : 2022",
            "RS_SCALE_FACTOR": [{"LOAD_CASE": "RX(RS)", "FACTOR": 1}],
            "UNDERGROUND_LOAD": {"OPT_USE": False},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {
            "OPTION": "ADD",
            "DGNCODE": "KDS 41 30 : 2022",
            "RS_SCALE_FACTOR": [{"LOAD_CASE": "RX(RS)", "FACTOR": 1}],
            "UNDERGROUND_LOAD": {"OPT_USE": False},
        }
    }


# --- 18. LCOM-SRC -----------------------------------------------------------------------


@responses.activate
def test_generate_load_combination_src_kds(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/LCOM-SRC", json={}, status=200)
    ope.generate_load_combination_src(
        {
            "OPTION": "ADD",
            "DGNCODE": "KDS 41 SRC : 2022",
            "RS_SCALE_FACTOR": [{"LOAD_CASE": "RX(RS)", "FACTOR": 1}],
            "UNDERGROUND_LOAD": {"OPT_USE": False},
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["DGNCODE"] == "KDS 41 SRC : 2022"


@responses.activate
def test_generate_load_combination_src_aik_src2k(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/LCOM-SRC", json={}, status=200)
    ope.generate_load_combination_src(
        {
            "OPTION": "ADD",
            "DGNCODE": "AIK-SRC2K",
            "RS_SCALE_FACTOR": [
                {"LOAD_CASE": "RX(RS)", "FACTOR": 1.2},
                {"LOAD_CASE": "RY(RS)", "FACTOR": 1.3},
            ],
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {
            "OPTION": "ADD",
            "DGNCODE": "AIK-SRC2K",
            "RS_SCALE_FACTOR": [
                {"LOAD_CASE": "RX(RS)", "FACTOR": 1.2},
                {"LOAD_CASE": "RY(RS)", "FACTOR": 1.3},
            ],
        }
    }


# --- 19. GSBG -----------------------------------------------------------------------------


@responses.activate
def test_generate_bridge_girder_diagram_stress_batch(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/GSBG", json={}, status=200)
    ope.generate_bridge_girder_diagram(
        {
            "LC_NAME": "LCB_STRENGTH_01",
            "DGRM_TYPE": 0,
            "BATCH": True,
            "X_AXIS_TYPE": 0,
            "STRESS_LINE": {"OPT_USE": True, "COMP": 24000, "TENS": 54000},
            "BATCH_LIST": ["Stress_Left_Girder", "Stress_Right_Girder"],
            "STAGE_LIST": ["CS1", "CS2", "FINAL"],
            "EXPORT_PATH": "C:\\Temp\\GSBG\\StressBatch",
            "EXTENSION": "jpg",
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)
    assert body["Argument"]["BATCH_LIST"][1] == "Stress_Right_Girder"
    assert body["Argument"]["EXTENSION"] == "jpg"


@responses.activate
def test_generate_bridge_girder_diagram_force_single(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/ope/GSBG", json={}, status=200)
    ope.generate_bridge_girder_diagram(
        {
            "LC_NAME": "LCB_SERVICE_01",
            "DGRM_TYPE": 1,
            "BATCH": False,
            "X_AXIS_TYPE": 1,
            "BRDG_GROUP": "BG_MAIN",
            "COMPONENTS": 5,
            "STAGE_LIST": ["CS1", "CS2", "FINAL"],
            "EXPORT_PATH": "C:\\Temp\\GSBG\\ForceSingle",
            "EXTENSION": "jpg",
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)
    assert body["Argument"]["BATCH"] is False
    assert body["Argument"]["BRDG_GROUP"] == "BG_MAIN"


@pytest.mark.parametrize(
    ("argument", "forbidden"),
    [
        pytest.param({"BATCH": True, "BRDG_GROUP": "BG_MAIN"}, "BRDG_GROUP", id="batch-true-group"),
        pytest.param({"COMPONENTS": 2}, "COMPONENTS", id="omitted-batch-defaults-true"),
        pytest.param({"BATCH": False, "BATCH_LIST": ["OUT"]}, "BATCH_LIST", id="batch-false-list"),
    ],
)
def test_generate_bridge_girder_diagram_rejects_manual_mutual_exclusions(argument, forbidden):
    with pytest.raises(MidasRequestError, match=forbidden):
        ope.generate_bridge_girder_diagram(argument)
