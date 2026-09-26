import json

import pytest
import responses

from midas_nx.client import DestructiveOperationError
from midas_nx.db.node_element import (
    DomainElement,
    Element,
    MainDomain,
    Node,
    Skew,
    SubDomain,
)


@responses.activate
def test_node_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/NODE", json={}, status=200)

    Node.create({1: {"X": 0, "Y": 0, "Z": 3.2}}, client=gen_client)

    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Assign": {"1": {"X": 0, "Y": 0, "Z": 3.2}}}


@responses.activate
def test_node_get_returns_full_response(gen_client):
    responses.add(
        responses.GET, "https://x.test:443/gen/db/NODE",
        json={"NODE": {"1": {"X": 0, "Y": 0, "Z": 0}}}, status=200,
    )
    result = Node.get(client=gen_client)
    assert result == {"NODE": {"1": {"X": 0, "Y": 0, "Z": 0}}}


@responses.activate
def test_node_delete_uses_the_per_id_url(gen_client):
    """The manual's ID-keyed "Assign" body was measured deleting the whole
    table on a live server; delete() uses DELETE {endpoint}/{id} instead.
    See db/base.py's module docstring."""
    responses.add(responses.DELETE, "https://x.test:443/gen/db/NODE/4", json={}, status=200)

    Node.delete([4], client=gen_client)

    sent = responses.calls[0].request
    assert sent.url == "https://x.test:443/gen/db/NODE/4"
    assert sent.body is None


@responses.activate
def test_node_delete_issues_one_request_per_id_and_keys_the_result(gen_client):
    for node_id in (4, 5):
        responses.add(
            responses.DELETE, f"https://x.test:443/gen/db/NODE/{node_id}",
            json={"NODE": {str(node_id): {}}}, status=200,
        )

    result = Node.delete([4, 5], client=gen_client)

    assert len(responses.calls) == 2
    assert set(result) == {4, 5}
    assert result[5] == {"NODE": {"5": {}}}


@responses.activate
def test_delete_all_still_sends_the_documented_whole_table_call(gen_client):
    responses.add(responses.DELETE, "https://x.test:443/gen/db/NODE", json={}, status=200)

    Node.delete_all(client=gen_client, confirm=True)

    sent = responses.calls[0].request
    assert sent.url == "https://x.test:443/gen/db/NODE"
    assert json.loads(sent.body) == {"Assign": {}}


@responses.activate
def test_delete_all_without_confirm_raises_and_sends_nothing(gen_client):
    responses.add(responses.DELETE, "https://x.test:443/gen/db/NODE", json={}, status=200)

    with pytest.raises(DestructiveOperationError) as excinfo:
        Node.delete_all(client=gen_client)

    # The guard runs before the request is built, so nothing reached the server.
    assert len(responses.calls) == 0
    message = str(excinfo.value)
    assert "/db/NODE" in message
    assert "confirm=True" in message


@responses.activate
@pytest.mark.parametrize("bad_confirm", [False, None, 0, "", "yes", 1])
def test_delete_all_only_accepts_the_literal_true(gen_client, bad_confirm):
    """A truthy-but-not-True value must not be enough to empty a table."""
    responses.add(responses.DELETE, "https://x.test:443/gen/db/NODE", json={}, status=200)

    with pytest.raises(DestructiveOperationError):
        Node.delete_all(client=gen_client, confirm=bad_confirm)

    assert len(responses.calls) == 0


@responses.activate
def test_element_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/ELEM", json={}, status=200)

    Element.create(
        {1: {"TYPE": "BEAM", "MATL": 1, "SECT": 1, "NODE": [1, 2], "ANGLE": 0}},
        client=gen_client,
    )

    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Assign": {"1": {"TYPE": "BEAM", "MATL": 1, "SECT": 1, "NODE": [1, 2], "ANGLE": 0}}
    }


@responses.activate
def test_skew_create_sends_angle_method_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/SKEW", json={}, status=200)

    Skew.create({1: {"iMETHOD": 1, "ANGLE_X": 45, "ANGLE_Y": 0, "ANGLE_Z": 90}}, client=gen_client)

    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Assign": {"1": {"iMETHOD": 1, "ANGLE_X": 45, "ANGLE_Y": 0, "ANGLE_Z": 90}}
    }


@responses.activate
def test_main_domain_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/MADO", json={}, status=200)

    MainDomain.create(
        {1: {"NAME": "DM1", "TYPE": 4, "MATL": 0, "PROP": 0, "SUB_TYPE": 2}}, client=gen_client
    )

    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Assign": {"1": {"NAME": "DM1", "TYPE": 4, "MATL": 0, "PROP": 0, "SUB_TYPE": 2}}
    }


@responses.activate
def test_sub_domain_create_sends_gen_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/SBDO", json={}, status=200)

    SubDomain.create(
        {
            1: {
                "SUB_DOMAIN_NAME": "SDM1",
                "MEMBER_TYPE": 1,
                "V1": 0,
                "V2": 90,
                "DOMAIN_NAME": "DM1",
                "bUseMt": True,
                "THICKNESS": 0.2,
            }
        },
        client=gen_client,
    )

    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Assign": {
            "1": {
                "SUB_DOMAIN_NAME": "SDM1",
                "MEMBER_TYPE": 1,
                "V1": 0,
                "V2": 90,
                "DOMAIN_NAME": "DM1",
                "bUseMt": True,
                "THICKNESS": 0.2,
            }
        }
    }


@responses.activate
def test_domain_element_create_sends_documented_assign_shape(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/DOEL", json={}, status=200)

    DomainElement.create(
        {163: {"TYPE": 1, "KEY_DOMAIN": 1, "MAIN_DOMAIN_NAME": "DM1"}}, client=gen_client
    )

    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Assign": {"163": {"TYPE": 1, "KEY_DOMAIN": 1, "MAIN_DOMAIN_NAME": "DM1"}}
    }
