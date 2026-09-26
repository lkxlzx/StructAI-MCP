import json

import pytest
import responses

from midas_nx.client import UnsupportedMethodError
from midas_nx.db.boundary import (
    BeamEndOffset,
    BeamEndRelease,
    ChangeGeneralLinkProperty,
    Constraint,
    ConstraintLabelDirection,
    DiaphragmDisconnect,
    ElasticLink,
    ForceDeformationFunction,
    GeneralLink,
    GeneralLinkHyperS,
    GeneralLinkProperty,
    GeneralSpringSupport,
    GeneralSpringType,
    LinearConstraint,
    PanelZoneEffect,
    PlateEndRelease,
    PointSpring,
    RigidLink,
    SeismicDeviceHystereticIsolator,
    SeismicDeviceIsolator,
    SeismicDeviceSteelDamper,
    SeismicDeviceViscoelasticDamper,
    SeismicDeviceViscousDamper,
    SurfaceSpring,
)


@responses.activate
def test_constraint_create_sends_items_array_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/CONS", json={}, status=200)

    Constraint.create(
        {1: {"ITEMS": [{"ID": 1, "GROUP_NAME": "Support", "CONSTRAINT": "1111111"}]}},
        client=gen_client,
    )

    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Assign": {"1": {"ITEMS": [{"ID": 1, "GROUP_NAME": "Support", "CONSTRAINT": "1111111"}]}}
    }


@responses.activate
def test_point_spring_create_linear_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/NSPR", json={}, status=200)
    PointSpring.create(
        {2: {"ITEMS": [{"ID": 1, "TYPE": "LINEAR", "GROUP_NAME": "Service", "SDR": [1000, 500, 500, 0, 0, 0]}]}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["2"]["ITEMS"][0]["TYPE"] == "LINEAR"


@responses.activate
def test_general_spring_type_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/GSTP", json={}, status=200)
    GeneralSpringType.create(
        {3: {"NAME": "GS_Damping", "OPT_STIFFNESS": True, "SPRING": [1000] + [0] * 20}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["3"]["NAME"] == "GS_Damping"


@responses.activate
def test_general_spring_support_create_keyed_by_node_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/GSPR", json={}, status=200)
    GeneralSpringSupport.create(
        {14: {"ITEMS": [{"ID": 14, "GROUP_NAME": "Service", "TYPE_NAME": "Foundation_GS"}]}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["14"]["ITEMS"][0]["TYPE_NAME"] == "Foundation_GS"


@responses.activate
def test_surface_spring_create_keyed_by_element_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/SSPS", json={}, status=200)
    SurfaceSpring.create(
        {1: {"ITEMS": [{"ID": 1, "GROUP_NAME": "Soil", "ELEM_TYPE": "FRAME", "SPRING_TYPE": 0, "MODULUS": 500}]}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["ITEMS"][0]["MODULUS"] == 500


@responses.activate
def test_elastic_link_create_gen_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/ELNK", json={}, status=200)
    ElasticLink.create(
        {
            1: {
                "NODE": [1, 2],
                "LINK": "GEN",
                "ANGLE": 0,
                "SDR": [1000, 500, 500, 0, 0, 0],
                "R_S": [False] * 6,
                "bSHEAR": False,
                "DR": [0, 0],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["LINK"] == "GEN"


@responses.activate
def test_rigid_link_create_keyed_by_master_node_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/RIGD", json={}, status=200)
    RigidLink.create(
        {1: {"ITEMS": [{"ID": 1, "GROUP_NAME": "Diaphragm", "DOF": 110001, "S_NODE": [2, 3, 4]}]}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["ITEMS"][0]["DOF"] == 110001


@responses.activate
def test_general_link_property_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/NLLP", json={}, status=200)
    GeneralLinkProperty.create(
        {1: {"PROPERTY_NAME": "GL_Spring01", "APPLICATION_TYPE": "ELEMENT", "APPLICATION_TYPE_D": "SPG"}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["APPLICATION_TYPE_D"] == "SPG"


@responses.activate
def test_general_link_create_element_ref_system(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/NLNK", json={}, status=200)
    GeneralLink.create(
        {1: {"NODE1": 10, "NODE2": 11, "PROP_NAME": "GL_LRB_01", "REF_SYSTEM": 0, "BETA_ANGLE": 0}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["PROP_NAME"] == "GL_LRB_01"


@responses.activate
def test_general_link_hyper_s_create_sends_documented_assign_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/NLNK-M1", json={}, status=200)
    GeneralLinkHyperS.create({1: {"PROP_NAME": "GL_HyperS_Prop", "NODE1": 20, "NODE2": 21}}, client=civil_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {"PROP_NAME": "GL_HyperS_Prop", "NODE1": 20, "NODE2": 21}}}


@responses.activate
def test_change_general_link_property_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/CGLP", json={}, status=200)
    ChangeGeneralLinkProperty.create(
        {1: {"GLINK_KEY": 1, "CHANGE_PROPERTY_NAME": "GL_LRB_02", "GROUP_NAME": "Stage2"}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["CHANGE_PROPERTY_NAME"] == "GL_LRB_02"


@responses.activate
def test_beam_end_release_create_keyed_by_element_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/FRLS", json={}, status=200)
    BeamEndRelease.create(
        {9: {"ITEMS": [{"ID": 9, "GROUP_NAME": "Service", "FLAG_I": "0000100", "FLAG_J": "0000100"}]}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["9"]["ITEMS"][0]["FLAG_I"] == "0000100"


@responses.activate
def test_beam_end_offset_create_global_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/OFFS", json={}, status=200)
    BeamEndOffset.create(
        {8: {"ITEMS": [{"ID": 1, "GROUP_NAME": "Service", "TYPE": "GLOBAL", "RGDXi": 0.11}]}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["8"]["ITEMS"][0]["TYPE"] == "GLOBAL"


@responses.activate
def test_plate_end_release_create_keyed_by_element_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/PRLS", json={}, status=200)
    PlateEndRelease.create(
        {
            21: {
                "ITEMS": [
                    {"ID": 21, "GROUP_NAME": "Service", "N1": [1, 0, 1, 0, 1], "N2": [1, 0, 1, 0, 1],
                     "N3": [1, 0, 1, 0, 1], "N4": [1, 0, 1, 0, 1]}
                ]
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["21"]["ITEMS"][0]["N1"] == [1, 0, 1, 0, 1]


@responses.activate
def test_force_deformation_function_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/MLFC", json={}, status=200)
    ForceDeformationFunction.create(
        {
            1: {
                "NAME": "Force_Deform_Isolator",
                "TYPE": "FORCE",
                "SYMM": False,
                "ITEMS": [{"X": -0.2, "Y": -1200}, {"X": 0.0, "Y": 0}],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["NAME"] == "Force_Deform_Isolator"


@responses.activate
def test_seismic_device_viscous_damper_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/SDVI", json={}, status=200)
    SeismicDeviceViscousDamper.create(
        {
            1: {
                "COMMON": {"NAME": "ViscousDamper_D01", "INPUT_METHOD": 0},
                "DAMPER_TYPE": 0,
                "DASHPOT_TYPE": 0,
                "INPUT_TYPE": 0,
                "ITEM": [{"OPT_DOF": True, "CE": 500, "P1": 1000, "C1": 200, "ALPHA1": 0.5, "K0": 0}],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["COMMON"]["NAME"] == "ViscousDamper_D01"


@responses.activate
def test_seismic_device_viscoelastic_damper_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/SDVE", json={}, status=200)
    SeismicDeviceViscoelasticDamper.create(
        {1: {"COMMON": {"NAME": "Viscoelastic01"}, "MATERIAL_TYPE": "GR100", "SHEAR_AREA": 0.05}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["MATERIAL_TYPE"] == "GR100"


@responses.activate
def test_seismic_device_steel_damper_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/SDST", json={}, status=200)
    SeismicDeviceSteelDamper.create(
        {1: {"COMMON": {"NAME": "SteelDamper01"}, "DIR": "Dx", "SDST_HYS_MODEL": "BL2"}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["SDST_HYS_MODEL"] == "BL2"


@responses.activate
def test_seismic_device_hysteretic_isolator_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/SDHY", json={}, status=200)
    SeismicDeviceHystereticIsolator.create(
        {1: {"COMMON": {"NAME": "HystereticIsolator01"}, "SDHY_HYS_MODEL": "DegradingBiLinear", "MSS": 8, "K0": 5000}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["MSS"] == 8


@responses.activate
def test_seismic_device_isolator_create_lrb_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/SDIS", json={}, status=200)
    SeismicDeviceIsolator.create(
        {
            1: {
                "COMMON": {"NAME": "LRB_Isolator_01"},
                "SDIS_DEV_TYPE": "LRB",
                "MSS": 8,
                "TAU_K": 1.0,
                "TAU_Q": 1.0,
                "KV": 150000,
                "LRB": {"SDIS_HYS_MODEL": "BiLinear", "AR": 0.196, "TR": 0.15, "KE": 20000, "K2": 2000, "QD": 80},
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["SDIS_DEV_TYPE"] == "LRB"


@responses.activate
def test_linear_constraint_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/MCON", json={}, status=200)
    LinearConstraint.create(
        {
            21: {
                "ITEMS": [
                    {
                        "ID": 1,
                        "GROUP_NAME": "Service",
                        "SLAVE_TYPE": "100000",
                        "TYPE": "EX",
                        "SLAVES": [{"NODE_KEY": 10, "COEFF": 1.0}, {"NODE_KEY": 11, "COEFF": -1.0}],
                    }
                ]
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["21"]["ITEMS"][0]["TYPE"] == "EX"


@responses.activate
def test_panel_zone_effect_update_sends_documented_assign_shape(gen_client):
    responses.add(responses.PUT, "https://x.test:443/gen/db/PZEF", json={}, status=200)
    PanelZoneEffect.update({1: {"OPT_OFFSET": True, "OFFS_FACTOR": 1.0, "OUTPUT_POSITION": 1}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {"OPT_OFFSET": True, "OFFS_FACTOR": 1.0, "OUTPUT_POSITION": 1}}}


@responses.activate
def test_panel_zone_effect_delete_raises_before_any_http_call(gen_client):
    with pytest.raises(UnsupportedMethodError):
        PanelZoneEffect.delete([1], client=gen_client)
    assert len(responses.calls) == 0


@responses.activate
def test_constraint_label_direction_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/CLDR", json={}, status=200)
    ConstraintLabelDirection.create({53: {"DIR": 0}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"53": {"DIR": 0}}}


@responses.activate
def test_diaphragm_disconnect_create_sends_empty_objects(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/DRLS", json={}, status=200)
    DiaphragmDisconnect.create({1: {}, 2: {}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {}, "2": {}}}
