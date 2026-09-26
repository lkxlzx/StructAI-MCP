import json

import responses

from midas_nx.post import pre_process


@responses.activate
def test_get_element_weight_table_sends_node_elems_range(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    pre_process.get_element_weight_table("Example", node_elems={"TO": "1to5"}, client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {
            "TABLE_NAME": "Example",
            "TABLE_TYPE": "ELEMENTWEIGHT",
            "NODE_ELEMS": {"TO": "1to5"},
        }
    }


@responses.activate
def test_get_nodal_body_force_table_sends_minimal_argument(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    pre_process.get_nodal_body_force_table("Example", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": {"TABLE_NAME": "Example", "TABLE_TYPE": "NODALBODYFORCE"}}


@responses.activate
def test_get_mass_summary_table_selects_direction(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    pre_process.get_mass_summary_table("X", "Mass_X", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "MASS_SUMMARY_X"


@responses.activate
def test_get_load_summary_table_selects_direction(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    pre_process.get_load_summary_table("Z", "Load_Z", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "LOAD_SUMMARY_Z"


@responses.activate
def test_get_material_table_sends_minimal_argument(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    pre_process.get_material_table("Materials", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "MATERIAL"


@responses.activate
def test_get_section_table_defaults_to_section_all(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    pre_process.get_section_table(table_name="Sections", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "SECTIONALL"


@responses.activate
def test_get_section_table_accepts_specific_variant(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    pre_process.get_section_table(pre_process.TABLE_TYPE_SECTION_PSC, "PSC", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "SECTIONPSC"


@responses.activate
def test_get_supports_table_sends_minimal_argument(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    pre_process.get_supports_table("Supports", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": {"TABLE_NAME": "Supports", "TABLE_TYPE": "SUPPORTS"}}


@responses.activate
def test_get_story_mass_summary_table_sends_unit_styles_components(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    pre_process.get_story_mass_summary_table(
        table_name="Story Mass",
        unit={"FORCE": "KN", "DIST": "M"},
        styles={"FORMAT": "Fixed", "PLACE": 3},
        components=["Story", "Level", "X-DIR", "Y-DIR"],
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "STORY_MASS"
    assert body["UNIT"] == {"FORCE": "KN", "DIST": "M"}
    assert body["STYLES"] == {"FORMAT": "Fixed", "PLACE": 3}
    assert body["COMPONENTS"] == ["Story", "Level", "X-DIR", "Y-DIR"]


@responses.activate
def test_get_story_load_summary_table_selects_direction(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    pre_process.get_story_load_summary_table("Y", "StoryLoad_Y", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body)["Argument"]["TABLE_TYPE"] == "STORY_LOAD_Y"


@responses.activate
def test_get_story_load_summary_table_sends_unit_styles_components_and_load_case_names(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    pre_process.get_story_load_summary_table(
        "Z",
        "StoryLoadZ",
        unit={"FORCE": "KN", "DIST": "M"},
        styles={"FORMAT": "Fixed", "PLACE": 3},
        components=["Load", "Story", "Level", "Sum"],
        load_case_names=["DL (ST)"],
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["TABLE_TYPE"] == "STORY_LOAD_Z"
    assert body["UNIT"] == {"FORCE": "KN", "DIST": "M"}
    assert body["STYLES"] == {"FORMAT": "Fixed", "PLACE": 3}
    assert body["COMPONENTS"] == ["Load", "Story", "Level", "Sum"]
    assert body["LOAD_CASE_NAMES"] == ["DL (ST)"]


@responses.activate
def test_get_story_weight_table_sends_minimal_argument(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    pre_process.get_story_weight_table("StoryWeight", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": {"TABLE_NAME": "StoryWeight", "TABLE_TYPE": "STORYWEIGHT"}}


@responses.activate
def test_get_story_weight_table_sends_unit_styles_and_components(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/post/TABLE", json={}, status=200)
    pre_process.get_story_weight_table(
        unit={"FORCE": "KN", "DIST": "M"},
        styles={"FORMAT": "Fixed", "PLACE": 3},
        components=["Story", "Level", "Sum"],
        client=gen_client,
    )
    sent = responses.calls[0].request
    body = json.loads(sent.body)["Argument"]
    assert body["UNIT"] == {"FORCE": "KN", "DIST": "M"}
    assert body["STYLES"] == {"FORMAT": "Fixed", "PLACE": 3}
    assert body["COMPONENTS"] == ["Story", "Level", "Sum"]
