"""Regression tests for generic plain-function parity discovery."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from function_endpoints import (
    ResourceEndpoint,
    ResourceSurface,
    python_function_surfaces,
    typescript_function_surfaces,
)
from promote_contract import (
    _ambiguous_draft_key,
    _endpoint_name_is_fallback,
    _manual_selection_error,
    _non_db_delete_response_unknown,
    _non_db_resource_is_modelled,
)


def test_from_manual_selection_requires_a_manual_candidate_and_explicit_replacement():
    candidates = {"db-new": "endpoint: /db/NEW\n", "db-existing": "endpoint: /db/EXISTING\n"}

    assert _manual_selection_error(["db-missing"], candidates, set(), False) == (
        "--from-manual found no manual section for: db-missing; refusing draft fallback"
    )
    assert _manual_selection_error(["db-existing"], candidates, {"db-existing"}, False) == (
        "--from-manual refuses to replace existing contract(s): db-existing; pass --replace-existing after review"
    )
    assert _manual_selection_error(["db-existing"], candidates, {"db-existing"}, True) is None


def test_promotion_rejects_a_manual_row_that_still_names_multiple_fields():
    assert _ambiguous_draft_key(
        "fields:\n  - key: FIRST\n    properties:\n      - key: 'SECOND\" / \"THIRD'\n"
    ) == 'SECOND" / "THIRD'
    assert _ambiguous_draft_key("fields:\n  - key: FIRST\n    properties:\n      - key: SECOND_2\n") is None
    assert _ambiguous_draft_key("fields:\n  - key: 7TH_DOF_TYPE\n") is None


def test_promotion_recognizes_an_endpoint_string_as_a_missing_manual_label():
    assert _endpoint_name_is_fallback({"name": "/db/EXAMPLE"}, "/db/EXAMPLE")
    assert not _endpoint_name_is_fallback({"name": "Example Resource"}, "/db/EXAMPLE")


def test_plain_function_discovery_resolves_constant_routes_and_npm_metadata(tmp_path):
    python_root = tmp_path / "midas_nx"
    python_root.mkdir()
    (python_root / "operations.py").write_text(
        '''_BASE = "/DESIGN/TEST"

def read():
    return _get(f"{_BASE}/READ")

def write():
    return _post(f"{_BASE}/WRITE", {})

def table():
    return client.request("POST", "/post/TABLE", {})
''',
        encoding="utf-8",
    )

    typescript_root = tmp_path / "typescript"
    generated = typescript_root / "generated"
    generated.mkdir(parents=True)
    (generated / "operations.ts").write_text(
        'defineGetOperation({"endpoint":"/DESIGN/TEST/READ","method":"GET","products":["gen"]})\n'
        'definePostOperation({"endpoint":"/DESIGN/TEST/WRITE","method":"POST","products":["gen"]})\n',
        encoding="utf-8",
    )
    (typescript_root / "doc.ts").write_text('post("/doc/OPEN", "", options);\n', encoding="utf-8")
    (typescript_root / "post.ts").write_text('getTableAt("/post/TABLE", type, options);\n', encoding="utf-8")

    python = python_function_surfaces(python_root)
    typescript = typescript_function_surfaces(typescript_root)

    assert python["/DESIGN/TEST/READ"].methods == {"GET"}
    assert python["/DESIGN/TEST/WRITE"].methods == {"POST"}
    assert python["/post/TABLE"].methods == {"POST"}
    assert typescript["/DESIGN/TEST/READ"].methods == {"GET"}
    assert typescript["/DESIGN/TEST/READ"].products == {"gen"}
    assert typescript["/DESIGN/TEST/WRITE"].methods == {"POST"}
    assert typescript["/doc/OPEN"].methods == {"POST"}
    assert typescript["/post/TABLE"].methods == {"POST"}


def test_non_db_resource_delete_never_inherits_db_delete_evidence():
    surface = ResourceSurface(
        methods=frozenset({"DELETE", "GET", "POST", "PUT"}),
        products=frozenset({"civil", "gen"}),
        entries=("ExampleResource",),
    )
    reason = _non_db_resource_is_modelled(
        "/DESIGN/EXAMPLE",
        {"DELETE", "GET", "POST", "PUT"},
        {"civil", "gen"},
        {"/DESIGN/EXAMPLE": ResourceEndpoint(surface, surface)},
    )

    assert reason is None

    promoted = _non_db_delete_response_unknown(
        """  - method: DELETE
    risk: destructive
    mitigation: none
    request:
      wrapper: none
    response:
      wrapper: table
      keyStability: stable
"""
    )

    assert "wrapper: unknown" in promoted
    assert "deletion scope or response shape" in promoted
    assert "keyStability" not in promoted
