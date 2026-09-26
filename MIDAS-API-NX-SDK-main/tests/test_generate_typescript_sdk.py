"""Shadow-run guards for the contract-first npm resource generator."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_typescript_sdk as generator  # noqa: E402


def test_contracted_resource_surfaces_match_the_legacy_sdk_anchor():
    """A Stage 3 switch is allowed only when it preserves generated output."""
    resources = {resource["endpoint"]: resource for resource in generator._load_resources(generator._source_modules())}
    contracts = generator._contract_resource_surfaces(set(resources))

    assert contracts
    for endpoint, surface in contracts.items():
        resource = resources[endpoint]
        assert resource["name"] == surface["name"]
        assert resource["products"] == surface["products"]
        assert resource["methods"] == surface["methods"]
        assert resource["contractManualChapter"] == surface["manualChapter"]


def test_contract_shadow_gate_covers_db_and_design_resources_only():
    assert generator._is_contract_shadow_resource("/db/NODE")
    assert generator._is_contract_shadow_resource("/DESIGN/RC/KDS-41-20-2022/DCO")
    assert not generator._is_contract_shadow_resource("/view/DISPLAY")


def test_resource_shadow_checks_documented_display_names_but_normalizes_dash_typography():
    resource = {
        "name": "Load Combinations - General",
        "products": ["gen"],
        "methods": ["GET"],
        "manual": [{"chapterFile": "13_DB_Load_Combinations.md"}],
    }
    surface = {
        "name": "Load Combinations – General",
        "products": ["gen"],
        "methods": ["GET"],
        "manualChapter": "13_DB_Load_Combinations.md",
    }
    assert generator._contract_resource_mismatches(resource, surface) == []

    surface["name"] = "/db/LCOM-GEN"
    assert generator._contract_resource_mismatches(resource, surface) == [
        "name: SDK has 'Load Combinations - General', contract has '/db/LCOM-GEN'"
    ]

    surface["methods"] = ["POST"]
    assert generator._contract_resource_mismatches(resource, surface) == [
        "name: SDK has 'Load Combinations - General', contract has '/db/LCOM-GEN'",
        "methods: SDK has ['GET'], contract has ['POST']"
    ]


def _bound_payloads():
    modules = generator._source_modules()
    resources = generator._load_resources(modules)
    resource_keys = {
        (resource["pythonModule"], resource["className"])
        for resource in resources
        if "pythonModule" in resource
    }
    type_keys = generator._collect_type_classes(modules, resource_keys)
    contract_fields = generator._contract_payload_fields()
    contract_types = generator._bind_payload_types(resources, contract_fields, type_keys)
    return modules, resources, type_keys, contract_fields, contract_types


def test_bodf_payload_comes_from_its_manual_contract():
    """The first static-load contract must not silently fall back to Python types."""
    _, resources, _, _, contract_types = _bound_payloads()
    bodf = next(resource for resource in resources if resource["endpoint"] == "/db/BODF")

    assert bodf["payloadTypeName"] == "SelfWeightPayload"
    assert bodf["payloadType"] == "Types.DbStaticLoadsTypes.SelfWeightPayload"
    fields = {
        field["key"]: field
        for field in contract_types[("DbStaticLoadsTypes", "SelfWeightPayload")]["fields"]
    }
    assert fields["LCNAME"]["requirement"] == "required"
    assert fields["GROUP_NAME"]["documentedDefault"] == ""
    assert fields["FV"] == {
        "key": "FV",
        "description": "Self-Weight Factor [X, Y, Z]",
        "type": "array",
        "items": {"type": "number"},
        "minItems": 3,
        "maxItems": 3,
        "requirement": "required",
        "documentedDefault": None,
        "documentedOptional": False,
        "safeToOmit": "unverified",
        "provenance": "manual",
    }


def test_contract_variants_render_as_a_discriminated_union():
    rendered = "\n".join(
        generator._contract_payload_type(
            "VariantPayload",
            {
                "fields": [
                    {
                        "key": "OPT_MODE",
                        "type": "boolean",
                        "requirement": "optional",
                    }
                ],
                "variants": [
                    {
                        "when": [{"path": "OPT_MODE", "equals": False}],
                        "fields": [
                            {"key": "OPT_MODE", "type": "boolean", "requirement": "optional"},
                            {"key": "GENERAL", "type": "number", "requirement": "required"}
                        ],
                    },
                    {
                        "when": [{"path": "OPT_MODE", "equals": True}],
                        "fields": [
                            {"key": "OPTIMIZED", "type": "string", "requirement": "required"}
                        ],
                    },
                ],
            },
        )
    )

    assert "export type VariantPayload" in rendered
    assert "OPT_MODE: false;" in rendered
    assert "OPT_MODE: true;" in rendered
    assert "GENERAL: number;" in rendered
    assert "OPTIMIZED: string;" in rendered
    assert rendered.count("OPT_MODE?: boolean;") == 1


def test_contract_shared_variant_table_folds_into_the_branches_it_covers():
    """A multi-value condition is the manual's shared table, not a third branch.

    /db/FBLA documents one table for ``FLOOR_DIST_TYPE = 1`` and another for
    ``= 2``, then a third for ``= 1 or 2``. Emitting the third as its own union
    member would give two members matching ``FLOOR_DIST_TYPE: 1``. Its fields
    belong to both branches instead, which is what the heading says.
    """
    rendered = "\n".join(
        generator._contract_payload_type(
            "SharedPayload",
            {
                "fields": [{"key": "DIST", "type": "integer", "requirement": "required"}],
                "variants": [
                    {
                        "when": [{"path": "DIST", "equals": 1}],
                        "fields": [{"key": "ONLY_ONE", "type": "number", "requirement": "required"}],
                    },
                    {
                        "when": [{"path": "DIST", "equals": 2}],
                        "fields": [{"key": "ONLY_TWO", "type": "number", "requirement": "required"}],
                    },
                    {
                        "when": [{"path": "DIST", "in": [1, 2]}],
                        "fields": [{"key": "SHARED", "type": "string", "requirement": "required"}],
                    },
                ],
            },
        )
    )

    assert rendered.count("DIST: 1;") == 1
    assert rendered.count("DIST: 2;") == 1
    # The shared table contributes to both branches and forms none of its own.
    assert rendered.count("SHARED: string;") == 2
    assert "DIST: 1 | 2;" not in rendered
    assert rendered.count("ONLY_ONE: number;") == 1
    assert rendered.count("ONLY_TWO: number;") == 1


def test_a_variant_attaches_to_the_object_holding_its_discriminator():
    """A branch's fields are siblings of the field it gates on, at any depth.

    /db/SWIND and /db/SSEIS gate on PARAMETERS.INPUT_METHOD and
    PARAMETERS.PERIOD_METHOD; /db/PRES and /db/MCON on a member of an ITEMS
    element. Attaching those unions at the payload root published WIND_SPEED,
    EXP_CATEGORY and PERIOD_APPR_X as top-level members - where the server does
    not look, the same defect the /db/BTMP nesting fix corrected one level down.
    """
    rendered = "\n".join(
        generator._contract_payload_type(
            "NestedGatePayload",
            {
                "fields": [
                    {
                        "key": "PARAMETERS",
                        "type": "object",
                        "requirement": "required",
                        "properties": [
                            {"key": "INPUT_METHOD", "type": "integer", "requirement": "required"}
                        ],
                    }
                ],
                "variants": [
                    {
                        "when": [{"path": "PARAMETERS.INPUT_METHOD", "equals": 0}],
                        "fields": [
                            {"key": "WIND_SPEED", "type": "number", "requirement": "required"}
                        ],
                    },
                    {
                        "when": [{"path": "PARAMETERS.INPUT_METHOD", "equals": 1}],
                        "fields": [
                            {"key": "EXP_CATEGORY", "type": "integer", "requirement": "required"}
                        ],
                    },
                ],
            },
        )
    )

    # The union sits inside PARAMETERS, so the branch fields are indented past
    # it rather than declared beside it.
    parameters = rendered.index("PARAMETERS:")
    assert rendered.index("WIND_SPEED") > parameters
    assert "    } & (" in rendered, rendered
    # And the payload root is a plain object: nothing was intersected there.
    assert not rendered.rstrip().endswith(");")
    assert rendered.rstrip().endswith("};")


def test_a_variant_gating_inside_an_array_attaches_to_the_element():
    """/db/PRES's FACE_EDGE_TYPE lives in ITEMS[], so FORCES does too.

    The manual numbers the branch rows `(11)`, continuing the ITEMS numbering,
    and the section's own JSON request example sends FORCES inside the array
    entry.
    """
    rendered = "\n".join(
        generator._contract_payload_type(
            "ItemGatePayload",
            {
                "fields": [
                    {
                        "key": "ITEMS",
                        "type": "array",
                        "requirement": "required",
                        "properties": [
                            {"key": "KIND", "type": "string", "requirement": "required"}
                        ],
                    }
                ],
                "variants": [
                    {
                        "when": [{"path": "ITEMS.KIND", "equals": "A"}],
                        "fields": [{"key": "ONLY_A", "type": "number", "requirement": "required"}],
                    },
                    {
                        "when": [{"path": "ITEMS.KIND", "equals": "B"}],
                        "fields": [{"key": "ONLY_B", "type": "number", "requirement": "required"}],
                    },
                ],
            },
        )
    )

    # The intersection has to be parenthesised inside Array<>, or the union
    # would bind to the array rather than to its element type.
    assert "ITEMS: Array<({" in rendered, rendered
    assert "ONLY_A: number;" in rendered
    assert rendered.rstrip().endswith("};")


def test_a_multi_value_table_overlapping_nothing_is_a_branch_not_a_shared_table():
    """Overlap decides it, not the plural.

    /db/PRES states one table for ``FACE_EDGE_TYPE = "FACE" or "PRES"`` and
    another for ``= "EDGE"``. Neither covers the other, so both are branches.
    Reading every multi-value table as the /db/FBLA shared kind folded this one
    into branches it does not cover and then dropped it: /db/PRES lost FORCES,
    /db/MVHL lost the South African VEH_ZA, /db/TDME lost four of six.
    """
    rendered = "\n".join(
        generator._contract_payload_type(
            "DisjointPayload",
            {
                "fields": [
                    {
                        "key": "KIND",
                        "type": "string",
                        "requirement": "required",
                        "enum": ["FACE", "PRES", "EDGE"],
                    }
                ],
                "variants": [
                    {
                        "when": [{"path": "KIND", "in": ["FACE", "PRES"]}],
                        "fields": [{"key": "FORCES", "type": "number", "requirement": "required"}],
                    },
                    {
                        "when": [{"path": "KIND", "equals": "EDGE"}],
                        "fields": [{"key": "EDGES", "type": "number", "requirement": "required"}],
                    },
                ],
            },
        )
    )

    assert '"FACE" | "PRES";' in rendered
    assert "FORCES: number;" in rendered
    assert "EDGES: number;" in rendered
    # Every enum member is covered, so no residual `?: never` member is needed.
    assert "?: never" not in rendered


def test_a_variant_gating_on_a_field_the_contract_never_declares_stays_at_the_root():
    """/db/MVLD's LOAD_MODEL is declared inside a sibling variant, not in fields.

    Where the contract says nothing, the branch is left where it already was
    rather than given an invented home - no permitted source states which
    object holds it.
    """
    rendered = "\n".join(
        generator._contract_payload_type(
            "UndeclaredGatePayload",
            {
                "fields": [{"key": "TYPE", "type": "integer", "requirement": "required"}],
                "variants": [
                    {
                        "when": [{"path": "LOAD_MODEL", "equals": 2}],
                        "fields": [{"key": "EXTRA", "type": "number", "requirement": "required"}],
                    }
                ],
            },
        )
    )

    assert rendered.rstrip().endswith(");")
    assert "LOAD_MODEL: 2;" in rendered

def test_contract_fixed_length_arrays_render_as_tuples():
    rendered = generator._contract_field_type(
        {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
        "  ",
    )

    assert rendered == "[number, number, number]"


def test_contract_applies_when_renders_as_member_jsdoc():
    rendered = "\n".join(
        generator._contract_payload_type(
            "ConditionalPayload",
            {
                "fields": [
                    {"key": "BATCH", "type": "boolean", "requirement": "optional"},
                    {
                        "key": "BATCH_LIST",
                        "type": "array",
                        "items": {"type": "string"},
                        "requirement": "conditional",
                        "description": "Output group names.",
                        "appliesWhen": [{"path": "BATCH", "equals": True}],
                    },
                ]
            },
        )
    )

    assert "/** Output group names. Applies when BATCH = true. */" in rendered
    assert "BATCH_LIST?: Array<string>;" in rendered


def test_conflicting_legacy_payload_aliases_receive_distinct_contract_types():
    """One reused Python TypedDict must not overwrite another endpoint contract.

    /db/DYFG and /db/DYNF once shared a Python TypedDict. Each contract records
    its own published name, so each gets its own type - including DYNF's, which
    has no Python class at all.
    """
    modules, resources, type_keys, contract_fields, contract_types = _bound_payloads()
    by_endpoint = {resource["endpoint"]: resource for resource in resources}
    dynf = by_endpoint["/db/DYNF"]

    assert by_endpoint["/db/DYFG"]["payloadTypeName"] == "RailwayDynamicFactorPayload"
    assert dynf["payloadTypeName"] == "RailwayDynamicFactorByElementPayload"
    namespace = generator._path_namespace(dynf["modulePath"])
    assert contract_types[(namespace, "RailwayDynamicFactorPayload")] == contract_fields["/db/DYFG"]
    assert contract_types[(namespace, "RailwayDynamicFactorByElementPayload")] == contract_fields["/db/DYNF"]

    rendered = generator._render_types(modules, type_keys, contract_types)
    assert "export interface RailwayDynamicFactorPayload" in rendered
    assert "export interface RailwayDynamicFactorByElementPayload" in rendered


def test_two_endpoints_naming_one_payload_must_agree_on_its_shape(monkeypatch):
    """One published name cannot follow two field lists."""
    import pytest

    resources = [
        {"endpoint": "/db/AAA", "className": "Aaa", "modulePath": ["db", "test"]},
        {"endpoint": "/db/BBB", "className": "Bbb", "modulePath": ["db", "test"]},
    ]
    monkeypatch.setattr(
        generator,
        "_contract_surface_blocks",
        lambda: {"/db/AAA": {"payloadTypeName": "Shared"}, "/db/BBB": {"payloadTypeName": "Shared"}},
    )
    same = {"fields": [{"key": "A"}], "variants": []}
    bound = generator._bind_payload_types(
        resources, {"/db/AAA": same, "/db/BBB": dict(same)}, set()
    )
    assert list(bound) == [("DbTestTypes", "Shared")]

    with pytest.raises(ValueError, match="DbTestTypes.Shared"):
        generator._bind_payload_types(
            resources,
            {"/db/AAA": same, "/db/BBB": {"fields": [{"key": "B"}], "variants": []}},
            set(),
        )


def test_a_contract_built_type_needs_no_python_class():
    """Delete every TypedDict a contract has taken over; types.ts must not move.

    Until 2026-09-22 the Python tree decided which types were written and where:
    `types.ts` walked the Python modules, and a contract only replaced the body
    of a class it found there. A contract-owned type whose class was deleted
    would have disappeared from npm, and a moved module would have moved it.
    Twelve of them are also referred to by types still built from Python, and
    those references have to survive the deletion too.
    """
    import ast

    modules, _, type_keys, _, contract_types = _bound_payloads()
    contract_types = {
        **contract_types,
        **generator._contract_nested_types(),
        **generator._contract_argument_types(),
    }
    before = generator._render_types(modules, type_keys, contract_types)
    owned = {
        (module, name)
        for module, name in type_keys
        if (generator._namespace(module), name) in contract_types
    }
    assert len(owned) > 500
    stripped = {
        module: ast.Module(
            body=[
                node
                for node in tree.body
                if not (isinstance(node, ast.ClassDef) and (module, node.name) in owned)
            ],
            type_ignores=[],
        )
        for module, tree in modules.items()
    }
    after = generator._render_types(
        stripped, generator._collect_type_classes(stripped, set()), contract_types
    )
    assert after == before


def test_types_are_written_in_name_order():
    """An order a contract can reproduce, unlike Python's class order."""
    import re

    text = (ROOT / "packages" / "typescript" / "src" / "generated" / "types.ts").read_text(
        encoding="utf-8"
    )
    namespaces = re.findall(r"^export namespace (\w+) \{", text, re.MULTILINE)
    assert namespaces == sorted(namespaces)
    for block in text.split("\nexport namespace ")[1:]:
        names = re.findall(r"^  export (?:interface|type) (\w+)", block, re.MULTILINE)
        assert names == sorted(names), block.split(" ", 1)[0]


def test_a_contract_with_unmerged_tables_does_not_become_a_payload_type(tmp_path, monkeypatch):
    """A contract that admits an unmerged table keeps its payload on the fallback.

    Its field list is still worth having in the source of truth, but
    generating a published payload type from it would narrow the payload onto
    fields the manual documents elsewhere, and break callers who set them. An
    entry marked `excluded` is a table review decided is not part of this API,
    and does not hold a contract back.

    Real contracts were this test's example until 2026-09-22 - /db/THIK,
    /db/SPLC, /db/SPFC, /db/THIS, /db/MVHL and last /db/MVLD, each until its
    supplementary tables were merged. No /db contract admits an unmerged table
    now, so the rule is held on contracts written for it.
    """
    body = """\
endpoint: {endpoint}
fields:
  - key: NAME
    type: string
    requirement: required
extraction:
  unmergedTables:
    - heading: A table
      excluded: {excluded}
"""
    _write_contracts(tmp_path, {
        "db-held.yaml": body.format(endpoint="/db/HELD", excluded="false"),
        "db-excluded.yaml": body.format(endpoint="/db/EXCL", excluded="true"),
        "db-plain.yaml": "endpoint: /db/PLAIN\nfields:\n  - key: NAME\n    type: string\n",
    })
    monkeypatch.setattr(generator, "ROOT", tmp_path)
    fields = generator._contract_payload_fields()

    assert "/db/HELD" not in fields
    assert "/db/EXCL" in fields, "an excluded table must not hold the contract back"
    assert "/db/PLAIN" in fields, "an unqualified contract must still supply its payload"


def test_no_real_db_contract_admits_an_unmerged_table():
    """Every /db payload contract's field list is complete, as of 2026-09-22."""
    fields = generator._contract_payload_fields()

    for merged in ("/db/THIK", "/db/SPLC", "/db/SPFC", "/db/THIS", "/db/MVHL", "/db/MVLD"):
        assert merged in fields, merged


def test_a_contract_surface_outranks_the_python_class():
    """The contract is the source; the Python class answers what it does not.

    Before the generator was inverted it iterated `DbResource` subclasses and
    let a contract correct the facts it owned, so a contract could never do more
    than annotate something Python had already declared. The precedence lives in
    one function now, and this pins which way round it goes.
    """

    surface = {
        "className": "FromContract",
        "exportName": "fromContract",
        "modulePath": ["db", "fromContract"],
        "name": "From the contract",
        "products": ["gen"],
        "methods": ["GET"],
    }
    fallback = {
        "className": "FromPython",
        "exportName": "fromPython",
        "modulePath": ["db", "fromPython"],
        "name": "From Python",
        "products": ["civil", "gen"],
        "methods": ["DELETE", "GET", "POST", "PUT"],
    }

    assert generator._resource_identity(surface, fallback) == surface
    # An endpoint no contract covers keeps every Python fact.
    assert generator._resource_identity(None, fallback) == fallback
    # A partial surface takes over only what it states.
    partial = generator._resource_identity({"name": "Renamed"}, fallback)
    assert partial["name"] == "Renamed"
    assert partial["className"] == "FromPython"


def test_a_contract_only_resource_needs_no_python_class():
    """A surface that states everything stands without a Python class at all.

    This is the capability the migration is for: today every contracted
    endpoint also has a `DbResource` subclass, so nothing exercises it in the
    real tree, and an untested path is how a migration quietly stops being
    possible.
    """

    surface = {
        "className": "ContractOnly",
        "exportName": "contractOnly",
        "modulePath": ["db", "contractOnly"],
        "name": "Contract only",
        "products": ["gen"],
        "methods": ["GET"],
    }
    assert generator._resource_identity(surface, None) == surface


def test_an_identity_nobody_supplies_is_refused_rather_than_guessed():
    """A missing name is a contract defect, not something to invent."""

    import pytest

    with pytest.raises(KeyError, match="className"):
        generator._resource_identity({"name": "No class name"}, None)

def test_a_field_required_only_in_one_branch_is_not_required_of_every_payload():
    """`requirement: required` plus an `appliesWhen` is a branch's requirement.

    Typed unconditionally required it made `/db/CCFC` demand `COEF` (only under
    TYPE="CONST") alongside `SCALE_FACTOR` and `ITEM` (only under TYPE="USER"),
    so no caller could satisfy the type without sending fields their own branch
    does not have. 49 fields across nine contracts were in that state. The
    condition moves into the doc comment, which is where a requiredness
    TypeScript cannot express belongs.
    """

    rendered = "\n".join(
        generator._contract_payload_type(
            "BranchPayload",
            {
                "fields": [
                    {"key": "TYPE", "type": "string", "requirement": "required"},
                    {
                        "key": "COEF",
                        "type": "number",
                        "requirement": "required",
                        "appliesWhen": [{"path": "TYPE", "equals": "CONST"}],
                    },
                    {
                        "key": "DEN",
                        "type": "number",
                        "requirement": "required",
                        "appliesWhen": [{"path": "P_TYPE", "in": [2, 3]}],
                    },
                ]
            },
        )
    )
    assert "TYPE: string;" in rendered
    assert "COEF?: number;" in rendered
    assert 'Required when TYPE = "CONST".' in rendered
    # `in` is the form the schema has for a field two branch tables document.
    assert "DEN?: number;" in rendered
    assert "Required when P_TYPE is 2 or 3." in rendered


def test_npm_generation_never_imports_midas_nx():
    """The generator reads the Python source tree; it must not import it.

    Until 2026-09-17 `npm run generate` imported `midas_nx` to enumerate
    `DbResource` subclasses, so a broken or missing Python install broke the npm
    build. This runs the resource loader in a fresh interpreter where any
    `midas_nx` import raises, so reintroducing one fails here rather than on a
    machine that happens not to have the package installed.
    """
    script = """
import sys
class Block:
    def find_spec(self, name, path=None, target=None):
        if name == "midas_nx" or name.startswith("midas_nx."):
            raise ImportError("npm generation imported " + name)
        return None
sys.meta_path.insert(0, Block())
sys.path.insert(0, sys.argv[1])
import generate_typescript_sdk as generator
resources = generator._load_resources(generator._source_modules())
print(len(resources))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(ROOT / "scripts")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert int(result.stdout.strip()) > 0


def test_static_resource_reader_matches_the_imported_classes():
    """The source reader must state exactly what Python would.

    `_static_resource_classes` follows a deliberately small subset of Python -
    literals, f-strings, frozensets of strings, module constants, relative
    imports, single inheritance. If the package starts stating a class fact
    some other way, the reader raises; this test covers the quieter failure,
    where it resolves to a different answer than the interpreter does.
    """
    import importlib
    import pkgutil

    import midas_nx
    from midas_nx.db.base import DbResource

    for module in pkgutil.walk_packages(midas_nx.__path__, midas_nx.__name__ + "."):
        importlib.import_module(module.name)

    def subclasses(base: type) -> list[type]:
        found: list[type] = []
        for child in base.__subclasses__():
            found.append(child)
            found.extend(subclasses(child))
        return found

    imported = {
        cls.ENDPOINT: {
            "className": cls.__name__,
            "endpoint": cls.ENDPOINT,
            "name": cls.NAME or cls.__name__,
            "products": sorted(cls.PRODUCTS),
            "methods": sorted(cls.METHODS),
            "pythonModule": cls.__module__,
        }
        for cls in subclasses(DbResource)
    }
    static = generator._static_resource_classes(generator._source_modules())

    assert set(static) == set(imported)
    for endpoint, facts in imported.items():
        for key, expected in facts.items():
            assert static[endpoint][key] == expected, (endpoint, key)



def _write_contracts(root: Path, contracts: dict[str, str]) -> None:
    directory = root / "contracts" / "endpoints"
    directory.mkdir(parents=True)
    for name, text in contracts.items():
        (directory / name).write_text(text, encoding="utf-8")


_ITEMS_CONTRACT = """\
endpoint: {endpoint}
surface:
  nestedTypes:
    - {{path: ITEMS, name: SharedItem, namespace: DbTestTypes}}
fields:
  - key: ITEMS
    type: array
    requirement: required
    properties:
      - key: NAME
        type: string
        requirement: required
{extra}
"""


def test_a_nested_type_is_built_from_the_contract_subtree_it_names():
    """The named element type comes from the contract, requiredness included.

    Until 2026-09-21 `DbBoundaryTypes.BeamEndOffsetItem` was read out of the
    Python TypedDict, `total=False`, so `TYPE` was optional there while the
    contract - and the inline `ITEMS` element of the payload root beside it -
    required it. The same object was published twice with two shapes.
    """
    nested = generator._contract_nested_types()
    item = nested[("DbBoundaryTypes", "BeamEndOffsetItem")]
    by_key = {field["key"]: field for field in item["fields"]}
    assert by_key["TYPE"]["requirement"] == "required"


def test_a_nested_type_carries_the_union_that_attaches_to_it():
    """/db/PRES branches inside its ITEMS element, so the element type does too."""
    nested = generator._contract_nested_types()
    rendered = "\n".join(
        generator._contract_payload_type(
            "PressureLoadItem", nested[("DbStaticLoadsTypes", "PressureLoadItem")]
        )
    )
    assert "export type PressureLoadItem" in rendered
    assert "FORCES: Array<number>;" in rendered
    assert "EDGE_LOADS: [number, number, number];" in rendered


def test_a_nested_row_sharing_a_key_with_an_earlier_field_is_kept():
    """/db/EFCT's COMB_LIST element holds LCNAME although the root has one too.

    The extractor dropped the nested row because the key had been seen above
    it. Deriving the element type from the contract is what exposed that: the
    type would otherwise have lost a member /info and the manual both declare.
    """
    nested = generator._contract_nested_types()
    item = nested[("DbMiscLoadsTypes", "InitialForceCombinationItem")]
    assert {field["key"] for field in item["fields"]} == {"LCNAME", "FACTOR"}


def test_two_contracts_disagreeing_on_a_shared_nested_type_are_refused(tmp_path, monkeypatch):
    extra = """\
      - key: COUNT
        type: integer
        requirement: optional"""
    _write_contracts(tmp_path, {
        "db-aaa.yaml": _ITEMS_CONTRACT.format(endpoint="/db/AAA", extra=""),
        "db-bbb.yaml": _ITEMS_CONTRACT.format(endpoint="/db/BBB", extra=extra),
    })
    monkeypatch.setattr(generator, "ROOT", tmp_path)
    try:
        generator._contract_nested_types()
    except ValueError as exc:
        assert "DbTestTypes.SharedItem" in str(exc)
    else:
        raise AssertionError("a shared name with two shapes must not publish either")


def test_descriptions_alone_do_not_make_a_shared_nested_type_diverge(tmp_path, monkeypatch):
    """BAR_SECTOR_I and BAR_SECTOR_J describe different ends of one shape."""
    first = _ITEMS_CONTRACT.format(endpoint="/db/AAA", extra="")
    second = _ITEMS_CONTRACT.format(endpoint="/db/BBB", extra="").replace(
        "        type: string\n", "        description: another end\n        type: string\n"
    )
    _write_contracts(tmp_path, {"db-aaa.yaml": first, "db-bbb.yaml": second})
    monkeypatch.setattr(generator, "ROOT", tmp_path)
    assert list(generator._contract_nested_types()) == [("DbTestTypes", "SharedItem")]


def test_a_nested_type_whose_shape_a_branch_above_decides_is_refused(tmp_path, monkeypatch):
    """/db/SECT re-declares SECT_BEFORE in each SECTTYPE branch.

    There is no single subtree at that path, so no one type can stand for it.
    """
    contract = """\
endpoint: /db/AAA
surface:
  nestedTypes:
    - {path: BEFORE, name: Before, namespace: DbTestTypes}
fields:
  - key: KIND
    type: string
    requirement: required
    enum: [A, B]
  - key: BEFORE
    type: object
    requirement: required
    properties:
      - key: SHAPE
        type: string
        requirement: required
variants:
  - when: [{path: KIND, equals: A}]
    fields:
      - key: BEFORE
        type: object
        requirement: required
        properties:
          - key: ONLY_A
            type: number
            requirement: required
"""
    _write_contracts(tmp_path, {"db-aaa.yaml": contract})
    monkeypatch.setattr(generator, "ROOT", tmp_path)
    try:
        generator._contract_nested_types()
    except ValueError as exc:
        assert "redeclares" in str(exc)
    else:
        raise AssertionError("a branch-decided shape must not be published as one type")


def _python_operation_specs():
    modules = generator._source_modules()
    resources = generator._load_resources(modules)
    type_keys = generator._collect_type_classes(
        modules,
        {(item["pythonModule"], item["className"]) for item in resources if "pythonModule" in item},
    )
    coverage = __import__("json").loads(
        (ROOT / "docs" / "coverage.json").read_text(encoding="utf-8")
    )
    products = {entry["endpoint"]: sorted(entry["products"]) for entry in coverage["endpoints"]}
    return generator._operation_specs(modules, type_keys, products)


def test_the_operation_list_comes_from_contracts_and_matches_the_python_functions():
    """npm's operations are read from contracts; Python is now only compared.

    The two lists must still name the same operations with the same wire and
    naming facts. Documentation is left out on purpose: since 2026-09-21 the
    npm JSDoc is owned by the contract and the Python docstring by Python.
    """
    facts = ("exportName", "endpoint", "method", "products", "modulePath",
             "argumentType", "noArgument")

    def keyed(specs):
        return {
            (spec["endpoint"], spec["method"]): {fact: spec[fact] for fact in facts}
            for spec in specs
        }

    from_contracts = keyed(generator._contract_operation_specs())
    from_python = keyed(_python_operation_specs())
    assert from_contracts == from_python


def test_the_table_wrappers_come_from_contracts_and_match_the_python_functions():
    """Same arrangement as the operations: contracts are read, Python compared."""
    facts = ("exportName", "tableType", "factory", "modulePath", "optionNames")

    def keyed(specs):
        return {spec["exportName"]: {fact: spec[fact] for fact in facts} for spec in specs}

    from_contracts = keyed(generator._contract_table_specs())
    from_python = keyed(generator._table_specs(generator._source_modules()))
    assert len(from_contracts) == 87
    assert from_contracts == from_python


def test_an_operation_argument_is_built_from_its_contract_without_the_wrapper():
    """`argumentTypeName` names a type the operation contract now supplies.

    The `"Argument"` row is the request envelope; the npm operation adds it, so
    a type demanding it would make every call send it twice.
    """
    arguments = generator._contract_argument_types()
    report = arguments[("DesignRcKdsChecksTypes", "RcMemberCheckReportArgument")]
    keys = {field["key"]: field for field in report["fields"]}
    assert "Argument" not in keys
    assert keys["REPORT_TYPE"]["requirement"] == "required"


def test_a_row_required_in_one_mode_is_not_required_of_every_argument():
    """/view/ACTIVE: `{"ACTIVE_MODE": "All"}` must still type-check."""
    active = generator._contract_argument_types()[("ViewTypes", "ActiveArgument")]
    rendered = "\n".join(generator._contract_payload_type("ActiveArgument", active))
    assert "ACTIVE_MODE: string;" in rendered
    assert "N_LIST?: Array<number>;" in rendered
    assert "IDENTITY_LIST?: Array<string>;" in rendered


def test_arguments_held_back_for_a_reason_stay_on_python():
    arguments = {name for _, name in generator._contract_argument_types()}
    for name, (kind, reason) in generator._ARGUMENT_TYPES_LEFT_ON_PYTHON.items():
        assert kind in {"divergent", "requiredness"}
        assert reason
        assert name not in arguments, f"{name} is listed as left on Python but was built"


def test_a_listed_divergence_that_no_longer_diverges_is_reported_stale(monkeypatch):
    monkeypatch.setitem(
        generator._ARGUMENT_TYPES_LEFT_ON_PYTHON,
        "RcMemberCheckReportArgument",
        ("divergent", "pretend the report trio disagreed"),
    )
    try:
        generator._contract_argument_types()
    except ValueError as exc:
        assert "RcMemberCheckReportArgument" in str(exc)
    else:
        raise AssertionError("a stale divergence entry must be reported")


def test_an_operation_can_declare_the_nested_types_of_its_argument():
    nested = generator._contract_nested_types()
    item = nested[("OpeTypes", "LineLoadValue")]
    by_key = {field["key"]: field for field in item["fields"]}
    # CURVED-only and CURVED-excluded rows carry their condition with them.
    assert by_key["A"]["appliesWhen"] == [{"path": "TYPE", "equals": "CURVED"}]
    assert "CURVED" not in by_key["D"]["appliesWhen"][0]["in"]

def test_a_table_contract_builds_the_request_types_of_its_table():
    """A story table's ADDITIONAL object comes from its table contract.

    These were the last /post types read out of Python: the table contracts
    recorded ADDITIONAL as `type: object` and nothing below it. The manual's
    Required rows now reach the type - SELECT_IRREGULAR_ENDS and USER_DEFINE -
    and a row it scopes with "USER_DEFINE: true일 때만" stays optional with the
    condition in JSDoc.
    """
    nested = generator._contract_nested_types()
    ends = nested[("PostStoryTypes", "SelectIrregularEnds")]
    assert ends["source"] == "contracts/tables/"
    rendered = chr(10).join(generator._contract_payload_type("SelectIrregularEnds", ends))
    assert "/** Generated from contracts/tables/. */" in rendered
    assert "USER_DEFINE: boolean;" in rendered
    assert "SELECT_NODES?: Array<number>;" in rendered
    # Stated from the type's own root, not the table request's.
    assert "Required when USER_DEFINE = true." in rendered
    # Declared by the plate, plane, axisymmetric and solid tables alike.
    assert ("PostBaseTypes", "NodeFlag") in nested


def test_an_operation_surface_without_an_export_only_names_types():
    """/post/TABLE's POST owns UNIT and STYLES but publishes no generated export."""
    assert generator._names_an_export({"exportName": "getTable"})
    assert not generator._names_an_export({"nestedTypes": []})
    assert not generator._names_an_export(None)
    endpoints = {operation["endpoint"] for operation in generator._contract_operation_specs()}
    assert "/post/TABLE" not in endpoints
    assert ("PostBaseTypes", "TableUnit") in generator._contract_nested_types()

def test_a_nested_type_states_its_conditions_from_its_own_root():
    """`PART_A.INPUT_METHOD` is wrong inside a type PART_B and PART_C share.

    HaunchPartSelector is PART_A, PART_B and PART_C of /DESIGN/.../HCBM alike.
    With the condition kept at the contract's root the three looked like three
    shapes and could not be one published type, and the JSDoc named a path the
    reader of `HaunchPartSelector` has no reason to know.
    """
    fields = [{"key": "TO", "requirement": "conditional",
               "appliesWhen": [{"path": "PART_A.INPUT_METHOD", "equals": "TO"}]}]
    assert generator._relative_conditions(fields, "PART_A.")[0]["appliesWhen"] == [
        {"path": "INPUT_METHOD", "equals": "TO"}
    ]
    # A condition on a field outside the object keeps its full path.
    outside = [{"key": "X", "appliesWhen": [{"path": "TYPE", "equals": 1}]}]
    assert generator._relative_conditions(outside, "PART_A.") == outside


def test_member_order_does_not_make_two_shapes():
    """/db/POGD lists INITLOAD's SF last, /db/THGC-M1 second: one object."""
    a = [{"key": "LC_NAME", "type": "string"}, {"key": "SF", "type": "number"}]
    assert generator._structure(a) == generator._structure(list(reversed(a)))


def test_an_object_only_one_branch_declares_is_still_one_type():
    """/db/NLCT's NEWTON_ITEMS exists only when ITERATION_METHOD is NEWTON."""
    variants = [
        {"when": [{"path": "MODE", "equals": "A"}],
         "fields": [{"key": "A_ITEMS", "type": "array", "properties": [{"key": "X", "type": "number"}]}]},
        {"when": [{"path": "MODE", "equals": "B"}],
         "fields": [{"key": "B_ITEMS", "type": "array", "properties": [{"key": "Y", "type": "number"}]}]},
    ]
    fields = [{"key": "MODE", "type": "string"}]
    entry = {"name": "AItem", "path": "A_ITEMS"}
    assert generator._branch_owned_subtree("t", entry, fields, variants, "A_ITEMS") == [
        {"key": "X", "type": "number"}
    ]


def test_branches_that_disagree_on_an_object_need_a_branch_named():
    """Two shapes under one path: refused unless the entry names its branch.

    /db/MCON's SLAVES[] is {NODE_KEY, COEFF, DOF} under TYPE "EX" and
    {NODE_KEY, WEIGHT} under "WD". Python publishes one name for each, and
    `branch` is how an entry says which one it is.
    """
    import pytest

    variants = [
        {"when": [{"path": "TYPE", "equals": "EX"}],
         "fields": [{"key": "SLAVES", "type": "array", "properties": [{"key": "COEFF", "type": "number"}]}]},
        {"when": [{"path": "TYPE", "equals": "WD"}],
         "fields": [{"key": "SLAVES", "type": "array", "properties": [{"key": "WEIGHT", "type": "number"}]}]},
    ]
    fields = [{"key": "TYPE", "type": "string"}]
    with pytest.raises(ValueError, match="different shapes"):
        generator._branch_owned_subtree("t", {"name": "S", "path": "SLAVES"}, fields, variants, "SLAVES")
    weighted = {"name": "W", "path": "SLAVES", "branch": [{"path": "TYPE", "equals": "WD"}]}
    assert generator._branch_owned_subtree("t", weighted, fields, variants, "SLAVES") == [
        {"key": "WEIGHT", "type": "number"}
    ]

def test_a_table_excluded_with_evidence_does_not_hold_a_payload_back():
    """/db/TDME's iGen tables are out of this API, not missing from the contract."""
    unmerged = {"extraction": {"unmergedTables": [{"heading": "a", "line": 1, "resolution": "r"}]}}
    excluded = {"extraction": {"unmergedTables": [{"heading": "a", "line": 1, "resolution": "r", "excluded": True}]}}
    assert generator._admits_incomplete_fields(unmerged)
    assert not generator._admits_incomplete_fields(excluded)
    assert not generator._admits_incomplete_fields({})
    assert "/db/TDME" in generator._contract_payload_fields()


def test_a_union_argument_part_keeps_only_what_its_discriminator_admits():
    """/ope/LCOM-SRC's KDS part is the field list under DGNCODE's KDS value."""
    fields = [
        {"key": "OPTION", "type": "string", "requirement": "required"},
        {"key": "DGNCODE", "type": "string", "requirement": "required",
         "enum": ["KDS", "AIK"]},
        {"key": "KDS_ONLY", "type": "object", "requirement": "optional",
         "appliesWhen": [{"path": "DGNCODE", "equals": "KDS"}]},
        {"key": "AIK_ONLY", "type": "object", "requirement": "optional",
         "appliesWhen": [{"path": "DGNCODE", "in": ["AIK"]}]},
    ]
    part = generator._argument_part(fields, {"path": "DGNCODE", "equals": "KDS"})

    assert [field["key"] for field in part] == ["OPTION", "DGNCODE", "KDS_ONLY"]
    assert part[1]["enum"] == ["KDS"]
    assert "appliesWhen" not in part[2], "a satisfied condition is not repeated in JSDoc"
    assert generator._argument_part(fields, None) is fields


def test_an_unequal_array_bound_does_not_make_two_shapes_differ():
    """Only an exact bound renders (as a tuple), so only it is compared."""
    open_bound = {"key": "SECTIONS", "type": "array", "minItems": 1}
    no_bound = {"key": "SECTIONS", "type": "array"}
    tuple_bound = {"key": "SECTIONS", "type": "array", "minItems": 2, "maxItems": 2}

    assert generator._structure([open_bound]) == generator._structure([no_bound])
    assert generator._structure([tuple_bound]) != generator._structure([no_bound])


def test_withdrawn_python_types_are_neither_published_nor_lost_from_python():
    """The 14 withdrawn names leave npm only; the Python classes stay."""
    types_ts = (ROOT / "packages" / "typescript" / "src" / "generated" / "types.ts").read_text(
        encoding="utf-8"
    )
    python_src = "".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "src" / "midas_nx").rglob("*.py")
    )
    for name in generator._PYTHON_TYPES_WITHDRAWN:
        assert f"interface {name} " not in types_ts and f"type {name} " not in types_ts, name
        assert f"class {name}(" in python_src, name
