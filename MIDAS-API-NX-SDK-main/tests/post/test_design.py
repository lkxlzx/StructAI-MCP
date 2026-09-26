import json

import responses

from midas_nx.post import design


@responses.activate
def test_get_pm_interaction_diagram_sends_empty_argument(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/PM", json={}, status=200)
    design.get_pm_interaction_diagram(client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": {}}


@responses.activate
def test_get_steel_code_check_sends_empty_argument(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/STEELCODECHECK", json={}, status=200)
    design.get_steel_code_check(client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": {}}


@responses.activate
def test_get_beam_design_forces_table_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    design.get_beam_design_forces_table(
        node_elems={"KEYS": [1, 2, 3]},
        parts=["PartI", "PartJ"],
        unit={"FORCE": "KN", "DIST": "M"},
        styles={"FORMAT": "Fixed", "PLACE": 3},
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "BEAMDESIGNFORCES"
    assert body["PARTS"] == ["PartI", "PartJ"]
    assert body["NODE_ELEMS"] == {"KEYS": [1, 2, 3]}


@responses.activate
def test_get_column_design_forces_table_selects_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    design.get_column_design_forces_table(node_elems={"KEYS": [56]}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "COLUMNDESIGNFORCES"


@responses.activate
def test_get_brace_design_forces_table_selects_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    design.get_brace_design_forces_table(node_elems={"KEYS": [52]}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "BRACEDESIGNFORCES"


@responses.activate
def test_get_wall_design_forces_table_has_no_parts_param(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    design.get_wall_design_forces_table(node_elems={"KEYS": [1]}, client=gen_client)
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "WALLDESIGNFORCES"
    assert "PARTS" not in body


@responses.activate
def test_get_wall_design_forces_table_sends_story_names(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    design.get_wall_design_forces_table(story_names=["1F", "2F"], client=gen_client)
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "WALLDESIGNFORCES"
    assert body["STORY_NAMES"] == ["1F", "2F"]


@responses.activate
def test_get_steel_member_design_forces_table_selects_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    design.get_steel_member_design_forces_table(parts=["PartI", "PartJ"], client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "STEELMEMBERDESIGNFORCES"


@responses.activate
def test_get_src_beam_design_forces_table_selects_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    design.get_src_beam_design_forces_table(node_elems={"KEYS": [316]}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "SRCBEAMDESIGNFORCES"


@responses.activate
def test_get_src_column_design_forces_table_selects_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    design.get_src_column_design_forces_table(node_elems={"KEYS": [365]}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "SRCCOLUMNDESIGNFORCES"


@responses.activate
def test_get_cold_formed_steel_member_design_forces_table_selects_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    design.get_cold_formed_steel_member_design_forces_table(node_elems={"KEYS": [313]}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "COLDFORMEDSTEELMEMBERDESIGNFORCES"
