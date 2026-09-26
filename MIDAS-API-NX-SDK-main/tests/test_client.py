import json

import pytest
import requests
import responses

from midas_nx.client import (
    MidasAPI,
    MidasAPIError,
    MidasAuthError,
    MidasClient,
    MidasConnectionError,
    MidasNotFoundError,
    MidasRequestError,
    MidasResultError,
    MidasServerError,
    Product,
    build_base_url,
    configure,
    get_result,
    post_argument,
)


def test_build_base_url():
    assert build_base_url(Product.GEN) == "https://moa-engineers.midasit.com:443/gen"
    assert build_base_url("civil") == "https://moa-engineers.midasit.com:443/civil"


def test_client_defaults_base_url_from_product():
    client = MidasClient(mapi_key="k", product=Product.CIVIL)
    assert client.base_url == "https://moa-engineers.midasit.com:443/civil"


def test_client_reads_env_vars(monkeypatch):
    monkeypatch.setenv("MIDAS_MAPI_KEY", "env-key")
    monkeypatch.setenv("MIDAS_BASE_URL", "https://envhost:443/gen")
    client = MidasClient()
    assert client.mapi_key == "env-key"
    assert client.base_url == "https://envhost:443/gen"


@responses.activate
def test_request_sends_correct_url_headers_and_body(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/NODE", json={"NODE": {}}, status=200)

    result = gen_client.request("POST", "/db/NODE", {"Assign": {"1": {"X": 0, "Y": 0, "Z": 0}}})

    assert result == {"NODE": {}}
    sent = responses.calls[0].request
    assert sent.url == "https://x.test:443/gen/db/NODE"
    assert sent.headers["MAPI-Key"] == "test-key"
    assert sent.headers["Content-Type"] == "application/json"
    assert json.loads(sent.body) == {"Assign": {"1": {"X": 0, "Y": 0, "Z": 0}}}


@responses.activate
def test_request_empty_response_body_returns_empty_dict(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/doc/SAVE", body="", status=200)
    assert gen_client.request("POST", "/doc/SAVE", {"Argument": {}}) == {}


@responses.activate
def test_200_with_error_body_raises_result_error(gen_client):
    """A 200 does not mean success: /post/TABLE and the design-check family
    report refusals with an {"error": ...} body under a 2xx status."""
    responses.add(
        responses.POST, "https://x.test:443/gen/post/TABLE",
        json={"error": {"message": "[empty] Cannot generate table data as there is no analysis result."}},
        status=200,
    )
    with pytest.raises(MidasResultError) as exc_info:
        gen_client.request("POST", "/post/TABLE", {"Argument": {}})

    assert exc_info.value.status_code == 200
    assert "no analysis result" in str(exc_info.value)
    assert "(Hint:" in str(exc_info.value)
    assert exc_info.value.response_body["error"]["message"].startswith("[empty]")


@responses.activate
def test_200_with_error_body_returned_raw_when_opted_out():
    client = MidasClient(
        mapi_key="k", base_url="https://x.test:443/gen", product=Product.GEN,
        raise_on_result_error=False,
    )
    responses.add(
        responses.POST, "https://x.test:443/gen/post/TABLE",
        json={"error": {"message": "nope"}}, status=200,
    )
    assert client.request("POST", "/post/TABLE", {"Argument": {}}) == {"error": {"message": "nope"}}


@responses.activate
def test_200_with_falsy_error_key_is_not_treated_as_a_failure(gen_client):
    responses.add(responses.GET, "https://x.test:443/gen/db/NODE", json={"error": {}}, status=200)
    assert gen_client.request("GET", "/db/NODE") == {"error": {}}


@responses.activate
def test_non_json_body_stays_inside_the_sdk_exception_hierarchy(gen_client):
    """A proxy/SSL-inspection appliance answering with HTML must not leak a
    raw JSONDecodeError past `except MidasAPIError`."""
    responses.add(
        responses.GET, "https://x.test:443/gen/db/NODE",
        body="<html>502 Bad Gateway</html>", status=502, content_type="text/html",
    )
    with pytest.raises(MidasServerError) as exc_info:
        gen_client.request("GET", "/db/NODE")

    assert isinstance(exc_info.value, MidasAPIError)
    assert "not JSON" in str(exc_info.value)
    assert exc_info.value.status_code == 502


@responses.activate
def test_non_json_body_on_200_raises_server_error(gen_client):
    responses.add(
        responses.GET, "https://x.test:443/gen/db/NODE",
        body="<html>login</html>", status=200, content_type="text/html",
    )
    with pytest.raises(MidasServerError):
        gen_client.request("GET", "/db/NODE")


@responses.activate
def test_non_json_body_on_401_still_maps_to_auth_error(gen_client):
    """Status mapping wins over the parse failure, so the MAPI-Key hint
    survives a proxy that returns an HTML login page with a 401."""
    responses.add(
        responses.GET, "https://x.test:443/gen/db/NODE",
        body="<html>sign in</html>", status=401, content_type="text/html",
    )
    with pytest.raises(MidasAuthError) as exc_info:
        gen_client.request("GET", "/db/NODE")

    assert "(Hint:" in str(exc_info.value)


@responses.activate
def test_401_raises_auth_error_not_process_exit(gen_client):
    responses.add(
        responses.GET, "https://x.test:443/gen/db/NODE",
        json={"message": "Invalid MAPI-Key"}, status=401,
    )
    with pytest.raises(MidasAuthError) as exc_info:
        gen_client.request("GET", "/db/NODE")
    assert exc_info.value.status_code == 401
    assert "Invalid MAPI-Key" in str(exc_info.value)
    assert "(Hint:" in str(exc_info.value)


@responses.activate
def test_non_dict_error_body_on_4xx_does_not_crash(gen_client):
    responses.add(
        responses.GET, "https://x.test:443/gen/db/NODE",
        json={"error": "plain string error"}, status=400,
    )
    with pytest.raises(MidasRequestError) as exc_info:
        gen_client.request("GET", "/db/NODE")
    assert "plain string error" in str(exc_info.value)


@responses.activate
def test_other_4xx_message_has_no_hint_suffix(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/NODE", json={"message": "bad"}, status=400)
    with pytest.raises(MidasRequestError) as exc_info:
        gen_client.request("POST", "/db/NODE", {})
    assert "(Hint:" not in str(exc_info.value)


@responses.activate
def test_404_raises_not_found_error(gen_client):
    responses.add(responses.GET, "https://x.test:443/gen/db/NODE", json={}, status=404)
    with pytest.raises(MidasNotFoundError):
        gen_client.request("GET", "/db/NODE")


@responses.activate
def test_other_4xx_raises_request_error(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/db/NODE", json={"message": "bad"}, status=400)
    with pytest.raises(MidasRequestError):
        gen_client.request("POST", "/db/NODE", {})


@responses.activate
def test_5xx_raises_server_error(gen_client):
    responses.add(responses.GET, "https://x.test:443/gen/db/NODE", json={}, status=500)
    with pytest.raises(MidasServerError):
        gen_client.request("GET", "/db/NODE")


@responses.activate
def test_network_failure_raises_connection_error(gen_client):
    responses.add(
        responses.GET, "https://x.test:443/gen/db/NODE",
        body=requests.exceptions.ConnectionError("boom"),
    )
    with pytest.raises(MidasConnectionError):
        gen_client.request("GET", "/db/NODE")


@responses.activate
def test_free_function_delegates_to_configured_default_client():
    configure(mapi_key="configured-key", base_url="https://x.test:443/gen", product=Product.GEN)
    responses.add(responses.POST, "https://x.test:443/gen/doc/NEW", json={}, status=200)

    MidasAPI("POST", "/doc/NEW", {"Argument": {}})

    assert responses.calls[0].request.headers["MAPI-Key"] == "configured-key"


def test_check_product_raises_by_default_when_mismatched(civil_client):
    from midas_nx.client import ProductMismatchError

    with pytest.raises(ProductMismatchError):
        civil_client.check_product(frozenset({"gen"}), "Some Civil-only Resource")


def test_check_product_warns_instead_of_raising_when_not_strict():
    client = MidasClient(mapi_key="k", base_url="https://x.test:443/gen", product=Product.GEN, strict_product=False)
    # Should not raise.
    client.check_product(frozenset({"civil"}), "Some Civil-only Resource")


@responses.activate
def test_verify_connection_strips_product_segment_and_reports_connected(gen_client):
    responses.add(
        responses.GET,
        "https://x.test:443/mapikey/verify",
        json={
            "user": "someone@example.com",
            "program": "gen",
            "connectionID": "EXAMPLECONN",
            "keyVerified": True,
            "status": "connected",
        },
        status=200,
    )

    result = gen_client.verify_connection()

    assert result["status"] == "connected"
    assert result["keyVerified"] is True
    sent = responses.calls[0].request
    assert sent.url == "https://x.test:443/mapikey/verify"
    assert sent.headers["MAPI-Key"] == "test-key"


@responses.activate
def test_verify_connection_returns_disconnected_status_without_raising(gen_client):
    responses.add(
        responses.GET,
        "https://x.test:443/mapikey/verify",
        json={"keyVerified": True, "status": "disconnected"},
        status=200,
    )

    result = gen_client.verify_connection()

    assert result["status"] == "disconnected"


@responses.activate
def test_verify_connection_404_raises_not_found_error(gen_client):
    responses.add(
        responses.GET,
        "https://x.test:443/mapikey/verify",
        json={"message": "client does not exist"},
        status=404,
    )

    with pytest.raises(MidasNotFoundError):
        gen_client.verify_connection()


class _RecordingSession:
    """Minimal stand-in for requests.Session that records the timeout it was
    handed, which `responses` does not expose on its recorded calls."""

    def __init__(self):
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append(kwargs)
        response = requests.Response()
        response.status_code = 200
        response._content = b"{}"
        response.url = url
        return response


def test_request_uses_the_client_timeout_by_default():
    session = _RecordingSession()
    client = MidasClient(
        mapi_key="k", base_url="https://x.test:443/gen", timeout=12.5, session=session
    )

    client.request("GET", "/db/NODE")

    assert session.calls[0]["timeout"] == 12.5


def test_request_timeout_overrides_the_client_default_for_one_call():
    session = _RecordingSession()
    client = MidasClient(
        mapi_key="k", base_url="https://x.test:443/gen", timeout=30.0, session=session
    )

    client.request("POST", "/doc/ANAL", {"Argument": {}}, timeout=2.0)
    client.request("GET", "/db/NODE")

    # The override applies to that call only; the next one is back on the default.
    assert session.calls[0]["timeout"] == 2.0
    assert session.calls[1]["timeout"] == 30.0


def test_request_accepts_a_connect_read_timeout_pair():
    session = _RecordingSession()
    client = MidasClient(mapi_key="k", base_url="https://x.test:443/gen", session=session)

    client.request("GET", "/db/NODE", timeout=(3.05, 60.0))

    assert session.calls[0]["timeout"] == (3.05, 60.0)


def test_post_argument_and_get_result_pass_the_timeout_through():
    session = _RecordingSession()
    client = MidasClient(mapi_key="k", base_url="https://x.test:443/gen", session=session)

    post_argument("/doc/ANAL", {}, client, timeout=1.5)
    get_result("/db/NODE", client, timeout=4.0)

    assert session.calls[0]["timeout"] == 1.5
    assert session.calls[1]["timeout"] == 4.0


def test_verify_connection_accepts_a_timeout_override():
    session = _RecordingSession()
    client = MidasClient(
        mapi_key="k", base_url="https://x.test:443/gen", timeout=30.0, session=session
    )

    client.verify_connection(timeout=1.0)

    assert session.calls[0]["timeout"] == 1.0
