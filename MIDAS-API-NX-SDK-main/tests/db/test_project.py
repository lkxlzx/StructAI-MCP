import json

import pytest
import responses

from midas_nx.client import UnsupportedMethodError
from midas_nx.db.project import (
    BoundaryGroup,
    FloorLoadColor,
    LoadGroup,
    MaterialColor,
    NamedPlane,
    ProjectInfo,
    SectionColor,
    Span,
    Story,
    StructureGroup,
    StructureType,
    StructureTypeHyperS,
    TendonGroup,
    ThicknessColor,
    Unit,
)


@responses.activate
def test_unit_update_sends_documented_assign_shape(gen_client):
    responses.add(responses.PUT, "https://x.test:443/gen/db/UNIT", json={}, status=200)
    Unit.update({1: {"FORCE": "KN", "DIST": "M", "HEAT": "KJ", "TEMPER": "C"}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {"FORCE": "KN", "DIST": "M", "HEAT": "KJ", "TEMPER": "C"}}}


@responses.activate
def test_unit_create_raises_before_any_http_call(gen_client):
    with pytest.raises(UnsupportedMethodError):
        Unit.create({1: {"FORCE": "KN"}}, client=gen_client)
    assert len(responses.calls) == 0


@responses.activate
def test_structure_type_delete_raises_before_any_http_call(gen_client):
    with pytest.raises(UnsupportedMethodError):
        StructureType.delete([1], client=gen_client)
    assert len(responses.calls) == 0


@responses.activate
def test_project_info_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/PJCF", json={}, status=200)
    ProjectInfo.create({1: {"PROJECT": "Cable", "USER": "LJW"}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {"PROJECT": "Cable", "USER": "LJW"}}}


@responses.activate
def test_structure_group_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/GRUP", json={}, status=200)
    StructureGroup.create(
        {1: {"NAME": "CENTER_", "P_TYPE": 0, "N_LIST": [1, 2], "E_LIST": [1, 2]}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Assign": {"1": {"NAME": "CENTER_", "P_TYPE": 0, "N_LIST": [1, 2], "E_LIST": [1, 2]}}
    }


@responses.activate
def test_structure_group_delete_raises_before_any_http_call(gen_client):
    with pytest.raises(UnsupportedMethodError):
        StructureGroup.delete([1], client=gen_client)
    assert len(responses.calls) == 0


@responses.activate
def test_boundary_group_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/BNGR", json={}, status=200)
    BoundaryGroup.create({1: {"NAME": "fix1", "AUTOTYPE": 0}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {"NAME": "fix1", "AUTOTYPE": 0}}}


@responses.activate
def test_load_group_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/LDGR", json={}, status=200)
    LoadGroup.create({1: {"NAME": "SW"}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {"NAME": "SW"}}}


@responses.activate
def test_tendon_group_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/TDGR", json={}, status=200)
    TendonGroup.create({1: {"NAME": "TGR1"}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {"NAME": "TGR1"}}}


@responses.activate
def test_named_plane_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/NPLN", json={}, status=200)
    NamedPlane.create(
        {2: {"NAME": "NP12", "TYPE": 2, "TOL": 1, "COORD": -12000}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Assign": {"2": {"NAME": "NP12", "TYPE": 2, "TOL": 1, "COORD": -12000}}
    }


@responses.activate
def test_material_color_update_sends_documented_assign_shape(gen_client):
    responses.add(responses.PUT, "https://x.test:443/gen/db/CO_M", json={}, status=200)
    MaterialColor.update({1: {"W_R": 131, "W_G": 131, "W_B": 131, "bBLEMD": False, "FACT": 0.5}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Assign": {"1": {"W_R": 131, "W_G": 131, "W_B": 131, "bBLEMD": False, "FACT": 0.5}}
    }


@responses.activate
def test_material_color_create_raises_before_any_http_call(gen_client):
    with pytest.raises(UnsupportedMethodError):
        MaterialColor.create({1: {"W_R": 0}}, client=gen_client)
    assert len(responses.calls) == 0


@responses.activate
def test_section_color_update_sends_documented_assign_shape(gen_client):
    responses.add(responses.PUT, "https://x.test:443/gen/db/CO_S", json={}, status=200)
    SectionColor.update({2: {"W_R": 111, "W_G": 142, "W_B": 91, "bBLEMD": False, "FACT": 0.5}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Assign": {"2": {"W_R": 111, "W_G": 142, "W_B": 91, "bBLEMD": False, "FACT": 0.5}}
    }


@responses.activate
def test_section_color_create_raises_before_any_http_call(gen_client):
    with pytest.raises(UnsupportedMethodError):
        SectionColor.create({1: {"W_R": 0}}, client=gen_client)
    assert len(responses.calls) == 0


@responses.activate
def test_thickness_color_update_sends_documented_assign_shape(gen_client):
    responses.add(responses.PUT, "https://x.test:443/gen/db/CO_T", json={}, status=200)
    ThicknessColor.update({1: {"W_R": 111, "W_G": 142, "W_B": 91, "bBLEMD": False, "FACT": 0.5}}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Assign": {"1": {"W_R": 111, "W_G": 142, "W_B": 91, "bBLEMD": False, "FACT": 0.5}}
    }


@responses.activate
def test_thickness_color_delete_raises_before_any_http_call(gen_client):
    with pytest.raises(UnsupportedMethodError):
        ThicknessColor.delete([1], client=gen_client)
    assert len(responses.calls) == 0


@responses.activate
def test_floor_load_color_update_sends_documented_assign_shape(gen_client):
    responses.add(responses.PUT, "https://x.test:443/gen/db/CO_F", json={}, status=200)
    FloorLoadColor.update(
        {1: {"NAME": "FL", "WF_R": 166, "OPT_BLEND": True, "BLEND_FACTOR": 0.25}}, client=gen_client
    )
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Assign": {"1": {"NAME": "FL", "WF_R": 166, "OPT_BLEND": True, "BLEND_FACTOR": 0.25}}
    }


@responses.activate
def test_span_create_sends_documented_assign_shape(civil_client):
    responses.add(responses.POST, "https://x.test:443/civil/db/SPAN", json={}, status=200)
    SpanPayload = {
        "NAME": "s1",
        "bEXACTSPAN": True,
        "DIRECTION": 0,
        "SECTTYPE": 0,
        "SPAN_LIST": [2.5, 5, 32.5],
        "SPAN_BASE_ITEMS": [
            {"ELEM_KEY": 1, "SUPPORT": 1},
            {"ELEM_KEY": 2, "SUPPORT": 1},
        ],
    }
    Span.create({1: SpanPayload}, client=civil_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": SpanPayload}}


@responses.activate
def test_story_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/STOR", json={}, status=200)
    story = {
        "STORY_NAME": "1F",
        "STORY_LEVEL": 0,
        "bFLOOR_DIAPHRAGM": False,
        "WIND_FLOOR_WIDTH_X": 36,
        "WIND_FLOOR_WIDTH_Y": 27.6,
        "WIND_CENTER_X": 18,
        "WIND_CENTER_Y": 13.8,
        "WIND_ECCENT_X": 5.4,
        "WIND_ECCENT_Y": 4.14,
        "SEIS_ACC_ECCENT_X": 1.8,
        "SEIS_ACC_ECCENT_Y": 1.38,
        "SEIS_INHERENT_ECCENT_X": 0,
        "SEIS_INHERENT_ECCENT_Y": 0,
        "SEIS_TORSIONAL_AMP_FACTOR_X": 1,
        "SEIS_TORSIONAL_AMP_FACTOR_Y": 1,
    }
    Story.create({1: story}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": story}}


@responses.activate
def test_structure_type_hyper_s_update_sends_info_derived_shape(civil_client):
    responses.add(responses.PUT, "https://x.test:443/civil/db/STYP-M1", json={}, status=200)
    styp = {
        "STYPE": "3D",
        "GRAV": 9.806,
        "TEMP": 0,
        "ALIGNBEAM": False,
        "ALIGNSLAB": False,
        "MASS_CONTROL": {"MASS_TYPE": "LUMPED", "MASS_POS": "CENTROID", "SELFWEIGHT": False},
    }
    StructureTypeHyperS.update({1: styp}, client=civil_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": styp}}


@responses.activate
def test_structure_type_hyper_s_create_raises_before_any_http_call(civil_client):
    with pytest.raises(UnsupportedMethodError):
        StructureTypeHyperS.create({1: {"STYPE": "3D"}}, client=civil_client)
    assert len(responses.calls) == 0
