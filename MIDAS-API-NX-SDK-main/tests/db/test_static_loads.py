import json

import pytest
import responses

from midas_nx.client import MidasRequestError
from midas_nx.db.static_loads import (
    BeamLoad,
    FinishingMaterialLoad,
    FloorLoad,
    FloorLoadType,
    LoadsToMass,
    NodalBodyForce,
    NodalLoad,
    NodalMass,
    PlaneLoad,
    PlaneLoadType,
    PressureLoad,
    PressureLoadType,
    SeismicEarthPressure,
    SeismicLoadParam,
    SelfWeight,
    SoilProperty,
    SpecifiedDisplacement,
    StaticEarthPressure,
    StaticLoadCase,
    StaticSeismicLoad,
    StaticWindLoad,
)


@responses.activate
def test_static_load_case_create(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/STLD", json={}, status=200)
    StaticLoadCase.create({1: {"NAME": "DL", "TYPE": "D", "DESC": "Dead Load"}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {"NAME": "DL", "TYPE": "D", "DESC": "Dead Load"}}}


@responses.activate
def test_self_weight_create(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/BODF", json={}, status=200)
    SelfWeight.create({1: {"LCNAME": "DL", "GROUP_NAME": "", "FV": [0, 0, -1]}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {"LCNAME": "DL", "GROUP_NAME": "", "FV": [0, 0, -1]}}}


@responses.activate
def test_nodal_load_create_keyed_by_node_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/CNLD", json={}, status=200)
    NodalLoad.create(
        {8: {"ITEMS": [{"ID": 1, "LCNAME": "LL", "FZ": -50.0}]}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"8": {"ITEMS": [{"ID": 1, "LCNAME": "LL", "FZ": -50.0}]}}}


@responses.activate
def test_beam_load_create_keyed_by_element_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/BMLD", json={}, status=200)
    BeamLoad.create(
        {
            115: {
                "ITEMS": [
                    {
                        "ID": 1,
                        "LCNAME": "L",
                        "CMD": "BEAM",
                        "TYPE": "UNILOAD",
                        "DIRECTION": "GZ",
                        "D": [0, 1, 0, 0],
                        "P": [-50, -50, 0, 0],
                    }
                ]
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["115"]["ITEMS"][0]["TYPE"] == "UNILOAD"


@responses.activate
def test_pressure_load_create_keyed_by_element_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/PRES", json={}, status=200)
    PressureLoad.create(
        {
            116: {
                "ITEMS": [
                    {
                        "ID": 1,
                        "LCNAME": "Element_Type1",
                        "CMD": "PRES",
                        "ELEM_TYPE": "PLATE",
                        "FACE_EDGE_TYPE": "FACE",
                        "DIRECTION": "LZ",
                        "FORCES": [-10, 0, 0, 0, 0],
                    }
                ]
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["116"]["ITEMS"][0]["FORCES"] == [-10, 0, 0, 0, 0]


@responses.activate
def test_pressure_load_refuses_an_item_without_a_direction(gen_client):
    """Omission is what fails, not a wrong value.

    The manual marks DIRECTION Optional with the default "NORMAL". On a PLATE
    with FACE_EDGE_TYPE "FACE" the server applies that default and then refuses
    the record with "[Error] Errors detected in Pressure Loads Data.(Item:Load
    Direction)" - the identical message it gives for "NORMAL" sent explicitly.
    There is no default an SDK could fill in instead, so it asks. Contract rule
    db-pres-direction-must-be-explicit.
    """
    responses.add(responses.POST, "https://x.test:443/gen/db/PRES", json={}, status=200)

    with pytest.raises(MidasRequestError, match=r"ITEMS\[0\]"):
        PressureLoad.create(
            {116: {"ITEMS": [{"LCNAME": "LC", "ELEM_TYPE": "PLATE", "FACE_EDGE_TYPE": "FACE"}]}},
            client=gen_client,
        )

    assert not responses.calls, "the request must not reach the product"


@responses.activate
def test_pressure_load_update_requires_a_direction_too(gen_client):
    """A PUT that drops the field is the same refused request as a POST."""
    responses.add(responses.PUT, "https://x.test:443/gen/db/PRES", json={}, status=200)

    with pytest.raises(MidasRequestError):
        PressureLoad.update({116: {"ITEMS": [{"LCNAME": "LC"}]}}, client=gen_client)

    assert not responses.calls


@responses.activate
def test_pressure_load_still_allows_normal_sent_explicitly(gen_client):
    """The value is legitimate; only leaving it to the default is not.

    The section's own availability matrix marks NORMAL available for
    PLATE+EDGE, SOLID+PRES and PLANE+EDGE. Refusing it outright would break
    three of the four documented combinations to protect the fourth.
    """
    responses.add(responses.POST, "https://x.test:443/gen/db/PRES", json={}, status=200)

    PressureLoad.create(
        {
            116: {
                "ITEMS": [
                    {
                        "LCNAME": "LC",
                        "ELEM_TYPE": "SOLID",
                        "FACE_EDGE_TYPE": "PRES",
                        "DIRECTION": "NORMAL",
                        "EDGE_FACE": 1,
                        "FORCES": [-10, 0, 0, 0, 0],
                    }
                ]
            }
        },
        client=gen_client,
    )

    sent = json.loads(responses.calls[0].request.body)["Assign"]["116"]
    assert sent["ITEMS"][0]["DIRECTION"] == "NORMAL"


@responses.activate
def test_pressure_load_leaves_a_record_without_items_alone(gen_client):
    """No ITEMS means the rule has no field to be missing from.

    ITEMS' own requiredness is a separate row of the same table; inventing a
    check for it here would refuse the DELETE-shaped bodies that carry none.
    """
    responses.add(responses.POST, "https://x.test:443/gen/db/PRES", json={}, status=200)

    PressureLoad.create({116: {}}, client=gen_client)

    assert len(responses.calls) == 1


@responses.activate
def test_specified_displacement_create_keyed_by_node_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/SDSP", json={}, status=200)
    SpecifiedDisplacement.create(
        {10: {"ITEMS": [{"ID": 1, "LCNAME": "LL", "VALUES": [{"OPT_FLAG": True, "DISPLACEMENT": 1.5}]}]}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["10"]["ITEMS"][0]["LCNAME"] == "LL"


@responses.activate
def test_nodal_mass_create_keyed_by_node_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/NMAS", json={}, status=200)
    NodalMass.create({1: {"mX": 1, "mY": 2, "mZ": 3, "rmX": 4, "rmY": 5, "rmZ": 6}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {"mX": 1, "mY": 2, "mZ": 3, "rmX": 4, "rmY": 5, "rmZ": 6}}}


@responses.activate
def test_nodal_mass_create_defaults_omitted_rotational_fields(gen_client):
    """Omitting rmX/rmY/rmZ reproducibly crashes the live server (confirmed
    on both Civil NX and Gen NX, 2026-07-29 - see docs/live_verification_notes.md);
    sending them explicitly as 0.0 does not. create()/update() fill them in
    so callers are protected without needing to know about the defect."""
    responses.add(responses.POST, "https://x.test:443/gen/db/NMAS", json={}, status=200)
    NodalMass.create({1: {"mX": 1, "mY": 2, "mZ": 3}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Assign": {"1": {"mX": 1, "mY": 2, "mZ": 3, "rmX": 0.0, "rmY": 0.0, "rmZ": 0.0}}
    }


@responses.activate
def test_nodal_mass_update_defaults_omitted_rotational_fields(gen_client):
    responses.add(responses.PUT, "https://x.test:443/gen/db/NMAS", json={}, status=200)
    NodalMass.update({1: {"mX": 1, "mY": 2, "mZ": 3, "rmY": 9}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Assign": {"1": {"mX": 1, "mY": 2, "mZ": 3, "rmX": 0.0, "rmY": 9, "rmZ": 0.0}}
    }


@responses.activate
def test_loads_to_mass_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/LTOM", json={}, status=200)
    LoadsToMass.create(
        {1: {"DIR": "XYZ", "bNODAL": True, "GRAV": 9.806, "vLC": [{"LCNAME": "D", "FACTOR": 1.0}]}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["DIR"] == "XYZ"


@responses.activate
def test_nodal_body_force_create_with_group(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/NBOF", json={}, status=200)
    NodalBodyForce.create(
        {2: {"LCNAME": "E", "OPT_USE_GROUP": True, "GROUP_NAME": "CrossBeam", "X": 10, "Y": 0, "Z": 0}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["2"]["GROUP_NAME"] == "CrossBeam"


@responses.activate
def test_pressure_load_type_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/PSLT", json={}, status=200)
    PressureLoadType.create(
        {
            1: {
                "NAME": "PlateUniform",
                "DESC": "Plate/PlaneStress(Face)",
                "ELEM_TYPE": "Plate/PlaneStress(Face)",
                "PRESSURE_LOAD_ITEMS": [{"LOADCASENAME": "DC", "LOADTYPE": "Uniform", "LOAD_P1": -20}],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["PRESSURE_LOAD_ITEMS"][0]["LOADTYPE"] == "Uniform"


@responses.activate
def test_plane_load_type_create_point_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/PNLD", json={}, status=200)
    PlaneLoadType.create(
        {
            1: {
                "NAME": "Point_examples",
                "LTYPE": "POINT",
                "POINTLOAD": [{"X": 0, "Y": 0, "F": -10}],
                "COPY_X": [5, 5, 5],
                "COPY_Y": [3, 3],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["LTYPE"] == "POINT"


@responses.activate
def test_plane_load_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/PNLA", json={}, status=200)
    PlaneLoad.create(
        {
            1: {
                "LCNAME": "AssignPlaneExample",
                "PNLD_KEY": 1,
                "ELEM_TYPE": "PLATE",
                "POINT_ORIGIN": [18, 2, 0],
                "AXIS_X": [19, 2, 0],
                "AXIS_Y": [19, 3, 0],
                "TOL": 0.0009144,
                "SELECT_TYPE": "ON_PLANE",
                "LOAD_DIR": "GLOBAL_Z",
                "PROJECT_TYPE": "NO",
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["ELEM_TYPE"] == "PLATE"


@responses.activate
def test_floor_load_type_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/FBLD", json={}, status=200)
    FloorLoadType.create(
        {1: {"NAME": "Floor_example", "ITEM": [{"LCNAME": "DC", "FLOOR_LOAD": 10, "OPT_SUB_BEAM_WEIGHT": True}]}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["ITEM"][0]["FLOOR_LOAD"] == 10


@responses.activate
def test_floor_load_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/FBLA", json={}, status=200)
    FloorLoad.create(
        {
            1: {
                "FLOOR_LOAD_TYPE_NAME": "Floor_example",
                "FLOOR_DIST_TYPE": 1,
                "DIR": "GZ",
                "NODES": [508, 509, 511, 510],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["FLOOR_DIST_TYPE"] == 1


@responses.activate
def test_finishing_material_load_create_keyed_by_element_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/FMLD", json={}, status=200)
    FinishingMaterialLoad.create(
        {
            448: {
                "ITEMS": [
                    {
                        "ID": 1,
                        "LCNAME": "FMLD_examples",
                        "COVERING_TYPE": "ENVELOP",
                        "COVERING_RANGE": ["HALF", "HALF", "FULL", "FULL"],
                        "THICKNESS": 0.2,
                        "DENSITY": 24.5,
                        "DIR": "GZ",
                        "SCALE_FACTOR": 1.0,
                    }
                ]
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["448"]["ITEMS"][0]["COVERING_TYPE"] == "ENVELOP"


@responses.activate
def test_soil_property_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/POSP", json={}, status=200)
    SoilProperty.create(
        {
            1: {
                "NAME": "Soil-1",
                "GROUND_LEVEL": 6,
                "BEDROCK_LEVEL": -21,
                "FOOTING_LEVEL": -17.5,
                "ITEMS": [{"HEIGHT": 7, "ANGLE_OR_N": 30, "DENSITY": 17, "VS": 160, "KH": 11449, "DISP": 0.001}],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["NAME"] == "Soil-1"


@responses.activate
def test_static_earth_pressure_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/EPST", json={}, status=200)
    StaticEarthPressure.create(
        {
            1: {
                "LOADCASE": "HsX(+)",
                "ANGLE": 0,
                "SF": 1,
                "EP_TYPE": "AT_REST",
                "SURCHARGE_LOAD": 16,
                "WATER_LEVEL": -4.7,
                "SOIL_PROP": "Soil-1",
                "SEL_TYPE": "GRUP",
                "ELEM_TYPE": "FRAME",
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["EP_TYPE"] == "AT_REST"


@responses.activate
def test_seismic_earth_pressure_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/EPSE", json={}, status=200)
    SeismicEarthPressure.create(
        {
            1: {
                "LOADCASE": "HaX(+)",
                "SEIS_LOAD": "KDS(2019)",
                "SOIL_PROP": "Soil-1",
                "SEL_TYPE": "ELEMENT",
                "NODE_LIST": [3461, 3831],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["SEIS_LOAD"] == "KDS(2019)"


@responses.activate
def test_seismic_load_param_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/POSL", json={}, status=200)
    SeismicLoadParam.create(
        {
            1: {
                "NAME": "KDS(2019)",
                "CODE": "KDS(41-17-00:2019)",
                "SZ": "1",
                "EPA": 0.22,
                "SC": "S1",
                "FA": 1.12,
                "FV": 0.84,
                "SDS": 0.41,
                "SD1": 0.12,
                "IF": 1.2,
                "RMF": 3,
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["NAME"] == "KDS(2019)"


@responses.activate
def test_static_wind_load_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/SWIND", json={}, status=200)
    StaticWindLoad.create(
        {
            1: {
                "WIND_CODE": "KDS(41-12: 2022)",
                "SCALE_FACTOR_X": 1.0,
                "SCALE_FACTOR_Y": 1.0,
                "PARAMETERS": {"INPUT_METHOD": 0, "WIND_SPEED": 30.0, "ROOF_HEIGHT": 45.0, "CE": 1.0},
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["PARAMETERS"]["INPUT_METHOD"] == 0


@responses.activate
def test_static_seismic_load_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/SSEIS", json={}, status=200)
    StaticSeismicLoad.create(
        {
            1: {
                "SEIS_CODE": "KDS(41-17-00:2019)",
                "SCALE_FACTOR_X": 1.0,
                "SCALE_FACTOR_Y": 0.0,
                "ACCIDENT_TORSION": True,
                "PARAMETERS": {
                    "SEIS_ZONE": 0,
                    "EPA": 0.22,
                    "SITE_CLASS": 1,
                    "SEIS_USE_GROUP": 1,
                    "IMPORTANCE_FACTOR": 1.5,
                    "PERIOD_METHOD": 1,
                },
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["SEIS_CODE"] == "KDS(41-17-00:2019)"
