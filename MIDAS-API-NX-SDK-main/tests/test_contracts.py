"""Guards for the language-neutral endpoint contracts under contracts/.

Two things are being protected here.

The first is the contracts themselves: they validate against their JSON Schema,
their cross-references resolve, and nothing declared ``product_crash_risk``
sits there without a rule that does something about it.

The second is the reason the contracts exist. ``/db/NMAS``'s crash workaround
was implemented in Python on 2026-07-29 and the npm package shipped a month
later, on 2026-08-26, without it - not through carelessness but because the
workaround is behaviour inside ``NodalMass.create()``, and the Python-to-npm
generator only ever carried metadata and docstrings across. Any caller reaching
``/db/NMAS`` through the npm SDK could still hang and kill a live NX session.
The rule now lives in ``contracts/endpoints/db-nmas.yaml``, and these tests plus
``scripts/validate_contracts.py`` are what make an implementation that ignores
it fail rather than ship.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from midas_nx.db.static_loads import NodalMass

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"
ENDPOINT_DIR = CONTRACTS / "endpoints"
RISKS_FILE = CONTRACTS / "safety" / "known-product-risks.yaml"
TS_RESOURCES = ROOT / "schema" / "typescript-resources.json"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _contracts() -> dict[str, dict]:
    return {path.stem: _load(path) for path in sorted(ENDPOINT_DIR.glob("*.yaml"))}


def _normalization_values(contract: dict) -> dict:
    values: dict = {}
    for rule in contract.get("sdkRules", []):
        if rule["kind"] == "normalize_defaults":
            values.update(rule["values"])
    return values


@pytest.mark.parametrize(
    "slug,field_key,expected",
    [
        ("db-mvct", "iIGPN", [{"path": "iIGP", "equals": 0}]),
        ("db-mvct", "DIST", [{"path": "iIGP", "equals": 1}]),
        ("db-tdmf", "CTYPE", [{"path": "FTYPE", "equals": "CREEP"}]),
        ("db-tdmf", "RELAXATION", [{"path": "FTYPE", "equals": "RELAX"}]),
        ("db-nlnk-m1", "BETA_ANGLE", [{"path": "REF_SYSTEM", "equals": 0}]),
        ("db-nlnk-m1", "INPUT_METHOD", [{"path": "REF_SYSTEM", "equals": 1}]),
        ("db-nlnk-m1", "ANGLE_VALUES", [
            {"path": "REF_SYSTEM", "equals": 1},
            {"path": "INPUT_METHOD", "equals": 0},
        ]),
    ],
    ids=[
        "mvct-number-mode", "mvct-distance-mode", "tdmf-creep-only",
        "tdmf-relax-only", "nlnk-element-system", "nlnk-global-system",
        "nlnk-global-angle-method",
    ],
)
def test_manual_branch_labels_are_executable_contract_conditions(
    slug: str, field_key: str, expected: list[dict],
) -> None:
    contract = _load(ENDPOINT_DIR / f"{slug}.yaml")
    field = next(item for item in contract["fields"] if item["key"] == field_key)
    assert field["appliesWhen"] == expected


def test_validator_passes():
    """The whole contract suite validates, including SDK parity.

    Run as a subprocess so the test exercises exactly what CI runs.
    """
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_contracts.py")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


_STATED_COUNT = re.compile(r"(\d+)\s*(?:종|개|가지)")


def test_no_contract_carries_an_enum_its_own_description_outsizes():
    """A list the manual itself calls partial must not narrow a payload type.

    `/DESIGN/RC/KDS-41-20-2022/DCRM-BEAM` describes `MAIN_REBAR` as
    "19종 (D4 ~ D57)" and the chapter's JSON Schema lists five of them. Adopted
    as an enum it published `"D4" | "D5" | "D6" | "D7" | "D8"`, making every
    bar size from D10 up untypeable for npm callers. The count the manual
    states about its own list is the evidence the list is a sample.
    """

    def check(fields: list[dict], slug: str, path: tuple[str, ...] = ()) -> None:
        for field in fields or []:
            here = path + (field["key"],)
            stated = _STATED_COUNT.search(field.get("description") or "")
            if stated and field.get("enum") is not None:
                assert int(stated.group(1)) == len(field["enum"]), (
                    f"{slug}: {'.'.join(here)} says {stated.group(1)} values, "
                    f"enum lists {len(field['enum'])}"
                )
            check(field.get("properties"), slug, here)

    for slug, contract in _contracts().items():
        check(contract.get("fields"), slug)
        for variant in contract.get("variants", []):
            check(variant.get("fields"), slug)


def test_no_contract_selects_two_field_sets_with_one_value():
    """A variant discriminator must identify exactly one branch.

    Two variants under the same condition say one wire value selects two
    different field sets, which no caller and no generated union can act on.
    It means the discriminator written down is narrower than the real one -
    the `/db/ELEM` tables headed `STYPE: 1` are a tension-only truss and a
    compression-only truss, told apart by `TYPE`. The honest record for that
    is an unmerged table with a stated resolution, never a repeated variant.
    """

    for slug, contract in _contracts().items():
        seen: set[str] = set()
        for variant in contract.get("variants", []):
            signature = json.dumps(variant["when"], sort_keys=True, ensure_ascii=False)
            assert signature not in seen, f"{slug} repeats the discriminator {signature}"
            seen.add(signature)


def test_every_contract_declares_a_manual_source():
    for name, contract in _contracts().items():
        manual = contract["source"]["manual"]
        if manual["status"] == "documented":
            assert manual.get("chapterFile"), f"{name} claims a manual source with no chapter"
            assert manual.get("section"), f"{name} claims a manual source with no section"
        else:
            # A contract may depart from the manual - the manual has been wrong
            # about field names, defaults and product support - but it must say
            # why, so a later manual re-sync cannot quietly overwrite the
            # correction.
            assert manual.get("justification", "").strip(), (
                f"{name} has manual status {manual['status']!r} without a justification"
            )


def test_crash_risk_operations_carry_a_mitigation_and_a_rule():
    for name, contract in _contracts().items():
        rule_methods = {
            method for rule in contract.get("sdkRules", []) for method in rule["appliesTo"]
        }
        for operation in contract["operations"]:
            if operation["risk"] != "product_crash_risk":
                continue
            assert operation.get("mitigation") not in (None, "none"), (
                f"{name} {operation['method']} is product_crash_risk with no mitigation"
            )
            assert operation["method"] in rule_methods, (
                f"{name} {operation['method']} is product_crash_risk but no sdkRule applies"
            )
            assert contract.get("knownDefects"), (
                f"{name} {operation['method']} is product_crash_risk but references no "
                f"entry in {RISKS_FILE.name}"
            )


def test_unsafe_optional_fields_are_covered_by_a_rule():
    """documentedOptional and safeToOmit must not be allowed to collapse.

    A field the manual calls optional that is not actually safe to omit is the
    single most dangerous shape in this API, because a caller who reads the
    documentation and follows it is the one who gets hurt. Every such field has
    to be covered by a rule that fixes the payload before it is sent.
    """
    for name, contract in _contracts().items():
        covered = {
            field
            for rule in contract.get("sdkRules", [])
            if rule["kind"] in ("normalize_defaults", "reject_request")
            for field in rule.get("fields", [])
        }
        for field in contract.get("fields", []):
            if field["safeToOmit"] or not field["documentedOptional"]:
                continue
            assert field["key"] in covered, (
                f"{name}: {field['key']} is documented optional but is not safe to "
                f"omit, and no sdkRule covers it"
            )
            assert field.get("omissionEffect", "").strip(), (
                f"{name}: {field['key']} is not safe to omit but does not say what happens"
            )


def test_normalized_defaults_match_the_documented_default():
    """A normalization rule may make a default explicit, never invent one."""
    for name, contract in _contracts().items():
        declared = {field["key"]: field for field in contract.get("fields", [])}
        for key, value in _normalization_values(contract).items():
            field = declared[key]
            assert field["documentedDefault"] is not None, (
                f"{name}: {key} is normalized to {value!r} but the manual documents "
                f"no default for it"
            )
            assert float(value) == float(field["documentedDefault"])


def test_applies_when_paths_are_declared_contract_fields():
    """Structured conditions must never silently target a misspelled member."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from validate_contracts import Failures, check_safety  # noqa: PLC0415

    contract = {
        "fields": [
            {
                "key": "MODE",
                "type": "integer",
                "requirement": "required",
                "documentedOptional": False,
                "safeToOmit": "unverified",
                "provenance": "manual",
            },
            {
                "key": "OPTIONS",
                "type": "object",
                "requirement": "optional",
                "documentedOptional": True,
                "safeToOmit": "unverified",
                "provenance": "manual",
                "properties": [
                    {
                        "key": "DETAIL",
                        "type": "number",
                        "requirement": "conditional",
                        "condition": "MODE=1",
                        "appliesWhen": [{"path": "MODE", "equals": 1}],
                        "documentedOptional": False,
                        "safeToOmit": "unverified",
                        "provenance": "manual",
                    }
                ],
            },
        ],
        "operations": [],
    }
    failures = Failures()
    check_safety([(Path("synthetic.yaml"), contract)], failures)
    assert not failures.items

    contract["fields"][1]["properties"][0]["appliesWhen"] = [
        {"path": "MDOE", "equals": 1}
    ]
    failures = Failures()
    check_safety([(Path("synthetic.yaml"), contract)], failures)
    assert failures.items == [
        ("synthetic.yaml", "field 'DETAIL' appliesWhen references undeclared field path 'MDOE'")
    ]


# ---------------------------------------------------------------------------
# /db/NMAS - the rule the npm SDK was missing.
# ---------------------------------------------------------------------------


def test_nmas_contract_marks_rotational_fields_unsafe_to_omit():
    contract = _load(ENDPOINT_DIR / "db-nmas.yaml")
    fields = {field["key"]: field for field in contract["fields"]}

    for key in ("rmX", "rmY", "rmZ"):
        assert fields[key]["documentedOptional"] is True
        assert fields[key]["safeToOmit"] is False

    # mY/mZ are documented optional and nobody has omitted them against a live
    # product - the confirmed live payload sends all three translational masses.
    # `unverified` is the honest answer; claiming `true` here would be reading
    # the manual's "Optional" as evidence, which is the mistake rmX punishes.
    for key in ("mY", "mZ"):
        assert fields[key]["safeToOmit"] == "unverified"

    assert _normalization_values(contract) == {"rmX": 0.0, "rmY": 0.0, "rmZ": 0.0}


def test_no_contract_claims_omission_safety_without_evidence():
    """`safeToOmit: true` is a claim about the product and has to cite one."""
    for name, contract in _contracts().items():
        for field in contract.get("fields", []):
            if field["safeToOmit"] is not True:
                continue
            evidence = field.get("omissionEvidence", "")
            assert evidence.strip(), f"{name}: {field['key']} claims safeToOmit with no evidence"
            assert "manual" not in evidence.lower() or "live" in evidence.lower(), (
                f"{name}: {field['key']} cites the manual as omission evidence; the manual "
                f"saying 'Optional' is what documentedOptional already records"
            )


class _RecordingClient:
    """Captures the outgoing body without touching the network."""

    def __init__(self) -> None:
        self.body: dict = {}

    def request(self, method: str, endpoint: str, body=None) -> dict:
        self.body = body
        return {}

    def check_product(self, products, name) -> None:
        return None


@pytest.mark.parametrize("verb", ["create", "update"])
def test_python_nmas_fills_rotational_mass_before_sending(verb):
    """Omitting rmX/rmY/rmZ must never reach the product."""
    client = _RecordingClient()
    getattr(NodalMass, verb)({1: {"mX": 1.0, "mY": 1.0, "mZ": 1.0}}, client=client)

    sent = client.body["Assign"]["1"]
    assert sent == {"mX": 1.0, "mY": 1.0, "mZ": 1.0, "rmX": 0.0, "rmY": 0.0, "rmZ": 0.0}


@pytest.mark.parametrize("verb", ["create", "update"])
def test_python_nmas_keeps_caller_supplied_rotational_mass(verb):
    """Normalizing a default must not overwrite a real value."""
    client = _RecordingClient()
    getattr(NodalMass, verb)({1: {"mX": 1.0, "rmZ": 500.0}}, client=client)

    sent = client.body["Assign"]["1"]
    assert sent["rmZ"] == 500.0
    assert sent["rmX"] == 0.0
    assert sent["rmY"] == 0.0


def test_npm_manifest_carries_the_nmas_normalization():
    """The generated npm surface must carry the rule, not just the Python one.

    This is the assertion that would have failed for the whole of the npm
    package's first month.
    """
    manifest = json.loads(TS_RESOURCES.read_text(encoding="utf-8"))
    nmas = next(r for r in manifest["resources"] if r["endpoint"] == "/db/NMAS")

    assert nmas.get("payloadDefaults") == {"rmX": 0.0, "rmY": 0.0, "rmZ": 0.0}


def test_risks_referenced_by_contracts_exist():
    risks = {risk["id"] for risk in _load(RISKS_FILE)["risks"]}
    for name, contract in _contracts().items():
        for defect in contract.get("knownDefects", []):
            assert defect["ref"] in risks, f"{name} references unknown risk {defect['ref']}"
        for rule in contract.get("sdkRules", []):
            if "riskRef" in rule:
                assert rule["riskRef"] in risks, (
                    f"{name}: rule {rule['id']} references unknown risk {rule['riskRef']}"
                )


def test_client_rules_document_timeout_semantics():
    """A timeout stops the SDK waiting; it does not roll the product back.

    Kept as an explicit test because it is the invariant most likely to be
    softened into something reassuring and wrong.
    """
    rules = {rule["id"]: rule for rule in _load(RISKS_FILE)["clientRules"]}

    assert "timeout-is-not-rollback" in rules
    statement = rules["timeout-is-not-rollback"]["statement"].lower()
    assert "does not cancel" in statement
    assert "roll back" in statement or "rollback" in statement


# ---------------------------------------------------------------------------
# The second layer: 89 result tables behind one route.
# ---------------------------------------------------------------------------

TABLE_DIR = CONTRACTS / "tables"


def _tables() -> dict[str, dict]:
    return {path.stem: _load(path) for path in sorted(TABLE_DIR.glob("*.yaml"))}


def test_every_table_routes_through_a_contracted_endpoint():
    """A table cannot describe how it departs from a request shape nobody wrote."""
    endpoints = {contract["endpoint"] for contract in _contracts().values()}

    for name, table in _tables().items():
        assert table["endpoint"] in endpoints, (
            f"{name} routes through {table['endpoint']}, which has no endpoint contract"
        )


def test_table_types_are_named_in_both_sdks():
    """A TABLE_TYPE only one language names is a table only its users will find."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from validate_contracts import _sdk_names_table_type  # noqa: PLC0415

    python_source = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "src" / "midas_nx" / "post").glob("*.py")
    )
    npm_source = (
        ROOT / "packages" / "typescript" / "src" / "generated" / "tables.ts"
    ).read_text(encoding="utf-8")

    for name, table in _tables().items():
        for entry in table["tableTypes"]:
            value = entry["value"]
            assert _sdk_names_table_type(python_source, value), f"{name}: {value} unnamed in the Python SDK"
            assert _sdk_names_table_type(npm_source, value), f"{name}: {value} unnamed in the npm SDK"


def test_a_table_type_contradiction_is_settled_live_or_left_open():
    """Counting documents cannot settle a wire string. Only the server can.

    Both of /post/TABLE's spelling contradictions were declared by majority -
    two of the manual's three statements against one - and on 2026-09-04 the
    products were finally asked. The majority was right about `BEAMFORCESTP`
    and **wrong** about the surface-spring reaction type: the lone request
    example had it, and both SDKs had been shipping a string the server
    refuses.

    So a `describes: table_type` defect may be resolved only by evidence of a
    live check. Every other kind - a column the docs omit, a field a revision
    dropped - is settled by reading the source, and those stay as they are.
    An unresolved defect of any kind must still say what is unknown.
    """
    defects = [
        (name, defect)
        for name, table in _tables().items()
        for defect in table.get("manualDefects", [])
    ]
    assert defects, "the known /post/TABLE contradictions should be recorded"

    for name, defect in defects:
        evidence = defect["evidence"].strip()
        assert evidence, f"{name}: defect with no evidence"

        if defect.get("resolved") is False:
            assert "not " in defect["actual"].lower() or "unknown" in defect["actual"].lower(), (
                f"{name}: an unresolved contradiction must say what is still unknown"
            )
            continue

        if defect["describes"] == "table_type":
            assert "live" in evidence.lower(), (
                f"{name}: a TABLE_TYPE spelling cannot be settled by counting the "
                f"manual's own statements - resolving one takes a live check"
            )


def test_post_table_response_key_is_declared_unstable():
    """The one thing an SDK must not do to this endpoint is index it by key name."""
    contract = _load(ENDPOINT_DIR / "post-table.yaml")
    response = next(op for op in contract["operations"] if op["method"] == "POST")["response"]
    rule = next(rule for rule in contract["sdkRules"] if rule["id"] == "post-table-unwrap-by-shape")

    assert response["keyStability"] == "unstable"
    assert "empty" in response["keyNote"]
    assert rule["kind"] == "unwrap_table_by_shape"
    assert set(rule["responseCases"]) == {
        "table_name",
        "result_table",
        "empty_with_table",
        "no_table",
    }


def test_a_contracted_surface_matches_the_published_npm_names():
    """A contract's `surface` block owns the names npm actually publishes.

    Before this block existed, `className`, `exportName`, `modulePath` and
    `payloadTypeName` came only from a Python class and the file it sat in, so
    moving a Python module renamed an npm export with nothing to object. The
    generator refuses a disagreement now; this fails first, and says which
    endpoint, without needing the generator to run.
    """

    manifest = json.loads(TS_RESOURCES.read_text(encoding="utf-8"))
    published = {resource["endpoint"]: resource for resource in manifest["resources"]}

    mismatches = []
    for slug, contract in _contracts().items():
        surface = contract.get("surface")
        if not surface:
            continue
        resource = published.get(contract["endpoint"])
        assert resource is not None, (
            f"{slug} declares a surface for {contract['endpoint']}, which the npm "
            "package does not expose"
        )
        for key, value in surface.items():
            if key == "nestedTypes":
                # Names of types, not facts about the resource; the test below
                # checks them against the generated types instead.
                continue
            if resource.get(key) != value:
                mismatches.append(
                    f"{contract['endpoint']} {key}: contract {value!r}, npm "
                    f"{resource.get(key)!r}"
                )
    assert not mismatches, "contract surface differs from the published npm names: " + "; ".join(mismatches)


def test_every_declared_nested_type_is_published_and_built_from_a_contract():
    """`surface.nestedTypes` names types npm already exports, and owns their shape.

    The namespace is part of the public name - the package re-exports every
    namespace at its root - so a name in the wrong namespace is a different
    type. Each declared one must also carry the generator's contract marker:
    a declaration that the generator quietly built from Python instead would
    look recorded while changing nothing.
    """

    types = (ROOT / "packages" / "typescript" / "src" / "generated" / "types.ts").read_text(
        encoding="utf-8"
    )
    published: dict[tuple[str, str], bool] = {}
    namespace = None
    marked = False
    for line in types.splitlines():
        match = re.match(r"^export namespace (\w+) \{", line)
        if match:
            namespace = match.group(1)
        match = re.match(r"^  export (?:interface|type) (\w+)", line)
        if match:
            published[(namespace, match.group(1))] = marked
        marked = line.strip() in (
            "/** Generated from contracts/endpoints/. */",
            "/** Generated from contracts/tables/. */",
        )

    declarations = []
    for slug, contract in _contracts().items():
        surfaces = [contract.get("surface") or {}]
        surfaces += [operation.get("surface") or {} for operation in contract.get("operations") or []]
        declarations += [(slug, entry) for surface in surfaces for entry in surface.get("nestedTypes") or []]
    for slug, table in _tables().items():
        declarations += [(slug, entry) for entry in (table.get("surface") or {}).get("nestedTypes") or []]
    assert declarations

    problems = []
    for slug, entry in declarations:
        key = (entry["namespace"], entry["name"])
        if key not in published:
            problems.append(f"{slug}: {key[0]}.{key[1]} is not published")
        elif not published[key]:
            problems.append(f"{slug}: {key[0]}.{key[1]} is not built from a contract")
    assert not problems, "; ".join(problems)


def test_every_npm_resource_with_a_contract_has_taken_its_names_over():
    """A contracted resource whose names still live only in Python is a gap.

    Not every npm resource has a contract - 31 do not, and they stay on the
    reviewed Python fallback by design. But once an endpoint *is* contracted,
    leaving its names out means the contract is not yet the source for that
    endpoint, and nothing else would say so.
    """

    manifest = json.loads(TS_RESOURCES.read_text(encoding="utf-8"))
    npm_endpoints = {resource["endpoint"] for resource in manifest["resources"]}
    missing = sorted(
        contract["endpoint"]
        for contract in _contracts().values()
        if contract["endpoint"] in npm_endpoints and not contract.get("surface")
    )
    assert not missing, (
        "contracted npm resources with no `surface` block: " + ", ".join(missing)
    )


def test_a_settled_finding_is_marked_settled_in_every_contract():
    """A contract promoted before the marker existed still called it a question.

    ``# NOTE:`` is an open question that blocks promotion; ``# RESOLVED:`` is a
    finding the permitted sources cannot reopen. The distinction shipped in
    2.7.5, so the five contracts promoted with it said ``RESOLVED`` while 95
    older ones said ``NOTE`` about the identical sentence - 592 blocks whose
    marker recorded their promotion date rather than their status. Nothing but
    this test notices, because ``--check`` compares what the manual asserts and
    a comment is not that.
    """

    sys.path.insert(0, str(ROOT / "scripts"))
    import extract_contracts

    marker = re.compile(r"^(\s*)# (NOTE|RESOLVED): (.*)$")
    continuation = re.compile(r"^(\s*)# (?!NOTE:|RESOLVED:)(.*)$")
    wrong: list[str] = []
    for path in sorted(ENDPOINT_DIR.glob("*.yaml")):
        lines = path.read_text(encoding="utf-8").splitlines()
        index = 0
        while index < len(lines):
            head = marker.match(lines[index])
            if not head:
                index += 1
                continue
            indent, written, first = head.groups()
            body, cursor = [first], index + 1
            while cursor < len(lines):
                tail = continuation.match(lines[cursor])
                if not tail or tail.group(1) != indent:
                    break
                body.append(tail.group(2))
                cursor += 1
            expected = extract_contracts._note_marker(" ".join(body).strip())
            if expected != written:
                wrong.append(f"{path.name}:{index + 1} says {written}, renders as {expected}")
            index = cursor

    assert not wrong, (
        "note markers disagree with extract_contracts._note_marker: " + "; ".join(wrong[:10])
    )


def test_field_parity_reads_nested_typed_dicts_and_variants():
    """The join has to see through both sides' nesting, or it lies twice.

    Python models a nested record as a sibling TypedDict named from an
    annotation, and a contract models a branch as a `variants` entry. A
    comparison that reads neither reports a member of `LANE_ITEMS` as missing
    and a variant field as invented - which is how the first draft of this
    check called /db/SKEW twenty-seven fields short of a contract that had
    them all.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    from typing import List, TypedDict  # noqa: PLC0415

    from validate_contracts import (  # noqa: PLC0415
        _contract_leaves,
        _payload_leaves,
    )

    class Item(TypedDict, total=False):
        ELEM: int

    class Payload(TypedDict, total=False):
        Assign: dict
        LANE_ITEMS: List[Item]
        METHOD: str

    assert _payload_leaves(Payload) == {"LANE_ITEMS", "ELEM", "METHOD"}

    contract = {
        "fields": [
            {"key": "METHOD"},
            {"key": "LANE_ITEMS", "properties": [{"key": "ELEM"}]},
        ],
        "variants": [{"fields": [{"key": "ONLY_IN_A_BRANCH"}]}],
    }
    leaves = _contract_leaves(contract)
    assert leaves == {"METHOD", "LANE_ITEMS", "ELEM", "ONLY_IN_A_BRANCH"}
    assert not _payload_leaves(Payload) - leaves


def test_field_parity_never_guesses_between_two_payloads_of_one_name():
    """`surface.payloadTypeName` is an npm name, and npm namespaces it.

    Python does not: 21 TypedDict names are defined in more than one module,
    because the RC and steel design chapters both have an SRDF and a LENG and
    their payloads differ. Picking whichever module imported first reported the
    other chapter's fields as missing from this one.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    from validate_contracts import _python_payload_types  # noqa: PLC0415

    types = _python_payload_types()
    collisions = {name: mods for name, mods in types.items() if len(mods) > 1}
    assert "StrengthReductionFactorsPayload" in collisions, (
        "the RC/steel collision is what this check has to survive; if it is "
        "gone, confirm the join is still per-module before deleting this test"
    )
    rc = collisions["StrengthReductionFactorsPayload"]["midas_nx.design.rc_kds.setup"]
    steel = collisions["StrengthReductionFactorsPayload"]["midas_nx.design.steel_kds"]
    assert set(rc.__annotations__) != set(steel.__annotations__)


def test_every_unmerged_table_records_the_names_it_holds():
    """A declared gap has to say what is in it, or it waives everything.

    `fields` counts an unmerged table's rows. A count cannot be a waiver:
    validate_contracts.py used to skip any contract carrying one, which left
    214 wire names the SDKs ship unchecked across twenty contracts. Every entry
    now names them, and scripts/extract_contracts.py --check verifies the list
    still matches the table.
    """
    import yaml  # noqa: PLC0415

    missing = []
    for path in sorted((ROOT / "contracts" / "endpoints").glob("*.yaml")):
        contract = yaml.safe_load(path.read_text(encoding="utf-8"))
        for entry in (contract.get("extraction") or {}).get("unmergedTables", []):
            names = entry.get("fieldNames")
            if not names:
                missing.append(f"{path.name}: {entry.get('heading')!r}")
                continue
            assert len(names) == len(set(names)), f"{path.name}: duplicate names"
    assert not missing, "unmergedTables entries with no fieldNames: " + ", ".join(missing)


def test_a_table_request_field_tree_is_held_to_the_schema():
    """`requestFields.additional` nests now, and the schema must still bite.

    Until 2026-09-22 an entry was one flat row, so the story tables' ADDITIONAL
    objects were recorded as `type: object` and nothing more, and their npm
    types came from Python. A nested entry is checked like any other.
    """
    from jsonschema import Draft202012Validator

    schema = json.loads((CONTRACTS / "schema" / "table-contract.schema.json").read_text(encoding="utf-8"))
    table = _tables()["post-story-shear-force-ratio"]
    assert list(Draft202012Validator(schema).iter_errors(table)) == []

    broken = json.loads(json.dumps(table))
    broken["requestFields"]["additional"][1]["properties"][0]["properties"][0]["requirement"] = "sometimes"
    errors = list(Draft202012Validator(schema).iter_errors(broken))
    assert errors and "sometimes" in errors[0].message
