import responses

from midas_nx.post.base import get_table, unwrap_table

TABLE = {
    "FORCE": "kN",
    "DIST": "m",
    "HEAD": ["Node", "FX", "FY"],
    "DATA": [["1", "0", "-10"]],
}


def test_unwrap_table_finds_the_table_under_the_documented_table_name_key():
    assert unwrap_table({"My Table": TABLE}) == TABLE


def test_unwrap_table_finds_the_table_under_the_keys_seen_live():
    # The same call has returned both of these instead of TABLE_NAME.
    assert unwrap_table({"Result Table": TABLE}) == TABLE
    assert unwrap_table({"empty": TABLE}) == TABLE


def test_unwrap_table_accepts_an_already_unwrapped_table():
    assert unwrap_table(TABLE) == TABLE


def test_unwrap_table_returns_empty_dict_when_there_is_no_table():
    assert unwrap_table({"message": ""}) == {}
    assert unwrap_table({}) == {}


def test_unwrap_table_ignores_non_mapping_values():
    assert unwrap_table({"message": "", "Result Table": TABLE}) == TABLE


@responses.activate
def test_unwrap_table_composes_with_get_table(gen_client):
    responses.add(
        responses.POST, "https://x.test:443/gen/post/TABLE",
        json={"empty": TABLE}, status=200,
    )
    raw = get_table("REACTION", client=gen_client)
    assert unwrap_table(raw)["DATA"] == [["1", "0", "-10"]]
