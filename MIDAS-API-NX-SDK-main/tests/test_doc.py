import json

import pytest
import responses

from midas_nx import doc
from midas_nx.client import MidasClient, MidasResultError, Product


@responses.activate
def test_new_project_sends_empty_argument(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/doc/NEW", json={}, status=200)
    doc.new_project(client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": {}}


@responses.activate
def test_open_project_sends_path_as_argument(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/doc/OPEN", json={}, status=200)
    doc.open_project("C:\\models\\a.mgb", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": "C:\\models\\a.mgb"}


@responses.activate
def test_stage_as_sends_stage_step_and_export_path(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/doc/STAGAS", json={}, status=200)
    doc.stage_as("Fase1", export_path="C:\\MIDAS\\FASE1.mcb", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {
        "Argument": {"STAGE_STEP": "Fase1", "EXPORT_PATH": "C:\\MIDAS\\FASE1.mcb"}
    }


@responses.activate
def test_analyze_without_type_sends_empty_argument(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/doc/ANAL", json={}, status=200)
    doc.analyze(client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": {}}


@responses.activate
def test_analyze_with_type_sends_type(gen_client):
    responses.add(responses.POST, "https://x.test:443/gen/doc/ANAL", json={}, status=200)
    doc.analyze("PUSHOVER", client=gen_client)
    sent = responses.calls[0].request
    assert json.loads(sent.body) == {"Argument": {"TYPE": "PUSHOVER"}}


@responses.activate
def test_analyze_accepts_the_success_message(gen_client):
    responses.add(
        responses.POST, "https://x.test:443/gen/doc/ANAL",
        json={"message": "MIDAS GEN NX command complete"}, status=200,
    )
    assert doc.analyze(client=gen_client) == {"message": "MIDAS GEN NX command complete"}


@responses.activate
def test_analyze_raises_when_the_200_body_says_the_analysis_failed(gen_client):
    """The solver reports failure through the same "message" key it uses for
    success, with no "error" object, so the client's generic check can't see
    it. Observed live on Civil NX 2026-07-26."""
    responses.add(
        responses.POST, "https://x.test:443/gen/doc/ANAL",
        json={"message": "MIDAS CIVIL NX Analysis failed."}, status=200,
    )
    with pytest.raises(MidasResultError) as exc_info:
        doc.analyze(client=gen_client)

    assert "Analysis failed" in str(exc_info.value)
    assert exc_info.value.endpoint == "/doc/ANAL"
    assert exc_info.value.response_body == {"message": "MIDAS CIVIL NX Analysis failed."}


@responses.activate
def test_analyze_respects_the_opt_out():
    client = MidasClient(
        mapi_key="k", base_url="https://x.test:443/gen", product=Product.GEN,
        raise_on_result_error=False,
    )
    responses.add(
        responses.POST, "https://x.test:443/gen/doc/ANAL",
        json={"message": "MIDAS CIVIL NX Analysis failed."}, status=200,
    )
    assert doc.analyze(client=client)["message"].endswith("failed.")
