"""Guards for the `/info`-sourced draft filler.

`scripts/contract_from_info.py` exists because seven Hyper-S sections state no
request at all, which makes live introspection their only permitted source. A
source nobody can cross-check is the one that most needs a rule about what it
may not say, so these tests are mostly about restraint: what the script
refuses to read into a schema that does not state it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import contract_from_info as filler  # noqa: E402

yaml = pytest.importorskip("yaml")


def _fields(properties: dict[str, object]) -> list[dict[str, object]]:
    return yaml.safe_load(filler.render_fields(properties))["fields"]


def test_a_field_info_states_no_requiredness_for_is_unstated_not_optional():
    """`/info` carries no `required` array, and silence is not permission.

    Recording these as `optional` would put a claim in the contract that no
    permitted source makes - the same distinction `documentedOptional` and
    `safeToOmit` are kept separate for.
    """

    field = _fields({"MATL_NAME": {"description": " Material Name", "type": "string"}})[0]

    assert field["requirement"] == "unstated"
    assert field["documentedOptional"] is None
    assert field["safeToOmit"] == "unverified"
    assert field["provenance"] == "info_schema"


def test_a_value_set_named_only_in_the_description_is_not_made_an_enum():
    """The served prose names the values; the schema declares no `enum`.

    `/db/MATL`'s contract, drafted from the manual's identical prose, keeps
    them in the description too. Promoting one to an `enum` here would make
    the two siblings disagree for no reason but which source was read.
    """

    field = _fields(
        {
            "P_TYPE": {
                "description": " Type of Material (Standard:0, Isotropic:1, Orthotropic:2)",
                "type": "integer",
            }
        }
    )[0]

    assert "enum" not in field
    assert "Standard:0" in field["description"]


def test_a_bound_info_states_on_the_wrong_subschema_is_noted_not_transcribed():
    """MD-12: `maxItems` sits on the items schema, where nothing enforces it.

    The array keeps its type and the bound is recorded as a finding. This is
    the rule the extractor already applies to the manual, reaching `/info`.
    """

    rendered = filler.render_fields(
        {
            "ELAST_M": {
                "description": " Modulii of elasticity [X,Y,Z]",
                "type": "array",
                "items": {"type": "number", "maxItems": 3},
            }
        }
    )
    field = yaml.safe_load(rendered)["fields"][0]

    assert field["type"] == "array"
    assert field["items"] == {"type": "number"}
    assert "maxItems" not in rendered.replace("maxItems=3", "")
    assert "MD-12" in rendered


def test_an_apostrophe_info_escapes_invalidly_is_repaired_in_the_prose():
    """MD-12: the server writes `Poisson\\'s`, which is not a JSON escape.

    The stray backslash is the server's, not the field's, so it does not
    belong in a description a caller reads.
    """

    field = _fields(
        {"POISN": {"description": " Poisson" + chr(92) + "'s ratio", "type": "number"}}
    )[0]

    assert field["description"] == "Poisson's ratio"


def test_a_nested_object_keeps_its_shape_rather_than_being_flattened():
    """`/db/FIMP` is the case that made this worth a test.

    A three-level object declared as flat top-level fields replaced a correct
    payload with a wrong one, so nesting is checked rather than assumed.
    """

    field = _fields(
        {
            "CONCRETE": {
                "description": " Concrete Material Setting",
                "type": "object",
                "properties": {
                    "UN_CONC_NAME": {"description": " Inelastic Material", "type": "string"}
                },
            }
        }
    )[0]

    assert field["type"] == "object"
    assert [child["key"] for child in field["properties"]] == ["UN_CONC_NAME"]


def test_the_findings_it_writes_are_marked_by_the_extractors_own_rule():
    """One function decides `# NOTE:` from `# RESOLVED:`, for both writers.

    A second copy of that rule would drift, and the difference is what
    promotion refuses on.
    """

    import extract_contracts

    rendered = filler.render_fields(
        {
            "ELAST_M": {
                "description": " Modulii [X,Y,Z]",
                "type": "array",
                "items": {"type": "number", "maxItems": 3},
            }
        }
    )
    marker = next(line for line in rendered.splitlines() if "MD-12" in line or "RESOLVED" in line)

    assert "# RESOLVED:" in marker
    assert extract_contracts._note_marker("is not transcribed (MD-12)") == "RESOLVED"
