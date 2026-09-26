import json

import responses

from midas_nx.db.temperature_prestress import (
    BeamSectionTemperature,
    ElementTemperature,
    ExternalLoadCaseForPretension,
    NodalTemperature,
    PrestressBeamLoad,
    PretensionLoad,
    SystemTemperature,
    TemperatureGradient,
    TendonLocationCompositeSection,
    TendonPrestress,
    TendonProfile,
    TendonProperty,
)


@responses.activate
def test_element_temperature_create_keyed_by_element_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/ETMP", json={}, status=200)
    ElementTemperature.create(
        {1: {"ITEMS": [{"ID": 1, "LCNAME": "Temp(+)", "TEMP": 35}]}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["ITEMS"][0]["TEMP"] == 35


@responses.activate
def test_temperature_gradient_create_beam_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/GTMP", json={}, status=200)
    TemperatureGradient.create(
        {
            2: {
                "ITEMS": [
                    {"ID": 1, "LCNAME": "Temp(+)", "TYPE": 1, "TZ": 10, "USE_HZ": True, "TY": -10, "USE_HY": True}
                ]
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["2"]["ITEMS"][0]["TYPE"] == 1


@responses.activate
def test_beam_section_temperature_create_general_element_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/BTMP", json={}, status=200)
    BeamSectionTemperature.create(
        {
            51: {
                "ITEMS": [
                    {
                        "ID": 1,
                        "LCNAME": "Temp(+)",
                        "DIR": "LZ",
                        "REF": "Centroid",
                        "NUM": 1,
                        "bPSC": False,
                        "vSECTTMP": [{"TYPE": "ELEMENT", "VAL_B": 0.2, "VAL_H1": 0.1}],
                    }
                ]
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["51"]["ITEMS"][0]["NUM"] == 1


@responses.activate
def test_system_temperature_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/STMP", json={}, status=200)
    SystemTemperature.create({1: {"LCNAME": "Temp(+)", "GROUP_NAME": "LoadGroup1", "TEMPER": 12.5}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {"LCNAME": "Temp(+)", "GROUP_NAME": "LoadGroup1", "TEMPER": 12.5}}}


@responses.activate
def test_nodal_temperature_create_keyed_by_node_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/NTMP", json={}, status=200)
    NodalTemperature.create(
        {190: {"ITEMS": [{"ID": 1, "LCNAME": "Temp(-)", "GROUP_NAME": "LoadGroup2", "TEMPER": -3}]}},
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["190"]["ITEMS"][0]["TEMPER"] == -3


@responses.activate
def test_tendon_property_create_internal_post_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/TDNT", json={}, status=200)
    TendonProperty.create(
        {
            2: {
                "NAME": "In_Post_Magura",
                "TYPE": "INTERNAL",
                "MATL": 1,
                "AREA": 0.00504,
                "D_AREA": 0.1,
                "RM": 0,
                "RV": 45,
                "LT": "POST",
                "bBONDED": True,
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["2"]["LT"] == "POST"


@responses.activate
def test_tendon_profile_create_2d_spline_element_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/TDNA", json={}, status=200)
    TendonProfile.create(
        {
            1: {
                "NAME": "2D/Spline/Element",
                "TDN_PROP": 1,
                "ELEM": [1101, 1102, 1103],
                "CURVE": "SPLINE",
                "INPUT": "2D",
                "LENG_OPT": "AUTO2",
                "SHAPE": "ELEMENT",
                "INS_PT": "END-I",
                "INS_ELEM": 1101,
                "PROFY": [{"PT": [0, -0.5], "bFIX": True, "R": 0}],
                "PROFZ": [{"PT": [0, -0.6], "bFIX": True, "R": 0, "bBOTZ": False}],
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1"]["SHAPE"] == "ELEMENT"


@responses.activate
def test_tendon_location_composite_section_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/TDCS", json={}, status=200)
    TendonLocationCompositeSection.create({1: {"TDNA": 1, "CSCS": 1, "PART_NUM": 1}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {"TDNA": 1, "CSCS": 1, "PART_NUM": 1}}}


@responses.activate
def test_tendon_prestress_create_keyed_by_tendon_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/TDPL", json={}, status=200)
    TendonPrestress.create(
        {
            2: {
                "ITEMS": [
                    {
                        "ID": 1,
                        "LCNAME": "PS",
                        "TENDON_NAME": "2D/Round/Element",
                        "TYPE": "FORCE",
                        "ORDER": "BOTH",
                        "BEGIN": 1360000,
                        "END": 1360000,
                    }
                ]
            }
        },
        client=gen_client,
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["2"]["ITEMS"][0]["TENDON_NAME"] == "2D/Round/Element"


@responses.activate
def test_prestress_beam_load_create_keyed_by_element_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/PRST", json={}, status=200)
    PrestressBeamLoad.create(
        {1101: {"ITEMS": [{"ID": 1, "LCNAME": "PS", "DIR": 1, "TENSION": 1360}]}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["1101"]["ITEMS"][0]["TENSION"] == 1360


@responses.activate
def test_pretension_load_create_keyed_by_element_id(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/PTNS", json={}, status=200)
    PretensionLoad.create(
        {3431: {"ITEMS": [{"ID": 1, "LCNAME": "PrS1", "TENSION": 130}]}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Assign"]["3431"]["ITEMS"][0]["TENSION"] == 130


@responses.activate
def test_external_load_case_for_pretension_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/EXLD", json={}, status=200)
    ExternalLoadCaseForPretension.create({1: {"LCNAME_ITEM": ["PrS1", "PrS2"]}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {"LCNAME_ITEM": ["PrS1", "PrS2"]}}}
