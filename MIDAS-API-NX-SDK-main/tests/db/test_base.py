"""Tests for DbResource's cross-cutting .info()/.items() classmethods
(base.py) — uses Node as a representative concrete resource, mirroring
test_client.py's pattern of testing shared client behavior via a stand-in.
"""
import pytest
import responses

from midas_nx.client import ProductMismatchError
from midas_nx.db.node_element import Node


@responses.activate
def test_info_hits_info_db_prefixed_endpoint(gen_client):
    responses.add(
        responses.GET,
        "https://x.test:443/gen/info/db/NODE",
        json={"NODE": {"X": "double", "Y": "double", "Z": "double"}},
        status=200,
    )

    result = Node.info(client=gen_client)

    assert result == {"NODE": {"X": "double", "Y": "double", "Z": "double"}}
    sent = responses.calls[0].request
    assert sent.url == "https://x.test:443/gen/info/db/NODE"


def test_info_still_enforces_product_check(gen_client):
    from midas_nx.db.bridge import BridgeGirderDiagram

    with pytest.raises(ProductMismatchError):
        BridgeGirderDiagram.info(client=gen_client)


@responses.activate
def test_items_unwraps_get_response_with_int_keys(gen_client):
    responses.add(
        responses.GET, "https://x.test:443/gen/db/NODE",
        json={"NODE": {"1": {"X": 0, "Y": 0, "Z": 0}, "2": {"X": 1, "Y": 0, "Z": 0}}},
        status=200,
    )

    result = Node.items(client=gen_client)

    assert result == {1: {"X": 0, "Y": 0, "Z": 0}, 2: {"X": 1, "Y": 0, "Z": 0}}


@responses.activate
def test_items_returns_empty_dict_for_empty_table(gen_client):
    responses.add(responses.GET, "https://x.test:443/gen/db/NODE", json={"NODE": {}}, status=200)

    assert Node.items(client=gen_client) == {}


@responses.activate
def test_items_returns_empty_dict_for_the_message_shaped_empty_response(gen_client):
    """A zero-row response has been observed live as a bare {"message": ""} as
    well as {"<KEY>": {}} — the string value must not reach .items()."""
    responses.add(responses.GET, "https://x.test:443/gen/db/NODE", json={"message": ""}, status=200)

    assert Node.items(client=gen_client) == {}


@responses.activate
def test_items_skips_non_dict_entries_to_find_the_table(gen_client):
    responses.add(
        responses.GET, "https://x.test:443/gen/db/NODE",
        json={"message": "", "NODE": {"1": {"X": 0, "Y": 0, "Z": 0}}}, status=200,
    )

    assert Node.items(client=gen_client) == {1: {"X": 0, "Y": 0, "Z": 0}}
