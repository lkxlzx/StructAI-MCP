"""Validate contracts/ and check both SDK surfaces against it.

The contracts under ``contracts/`` are the language-neutral source of truth for
this repository: an endpoint's shape comes from the official manual repo, from
live verification records, or from ``/info`` schema introspection - never from
either SDK implementation. This script is what keeps that arrangement honest.

It runs four kinds of check:

1. **Schema** - every contract validates against
   ``contracts/schema/endpoint-contract.schema.json``.
2. **Cross-reference** - every ``riskRef``/``knownDefects[].ref`` resolves in
   ``contracts/safety/known-product-risks.yaml``, and every
   ``verification.records[].ref`` resolves in that product's file under
   ``contracts/verification/``.
3. **Safety** - a ``product_crash_risk`` operation must carry a mitigation, an
   SDK rule and a risk reference; a field that is ``documentedOptional`` but not
   ``safeToOmit`` must be covered by an SDK rule; a contract without a manual
   source must justify itself.
4. **Parity** - the endpoint, products and methods each contract declares must
   match what the Python package and the generated npm resource manifest expose.
   Every declared executable safety-rule kind is also run against the shared
   Python and npm resource implementations.
5. **Field parity** - no contract may omit a wire name its own Python payload
   TypedDict publishes. Check 4 compares routes, verbs, products and rules and
   never once compares a field name, which is why /db/ELNK published four
   fields beside a twelve-key TypedDict for months with every check green.
   Enforced in one direction only: a contract ahead of a TypedDict is the
   intended state, because a TypedDict is documentation and npm generates its
   payload types from the contract.

Parity uses the SDKs as *subjects*, never as sources. A mismatch is reported as
an SDK defect, not as a reason to edit the contract.

Exit codes: 0 clean, 1 validation failures, 2 could not run (missing dependency
or malformed input).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from function_endpoints import function_endpoints

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"
ENDPOINT_DIR = CONTRACTS / "endpoints"
TABLE_DIR = CONTRACTS / "tables"
SCHEMA_FILE = CONTRACTS / "schema" / "endpoint-contract.schema.json"
TABLE_SCHEMA_FILE = CONTRACTS / "schema" / "table-contract.schema.json"
RISKS_FILE = CONTRACTS / "safety" / "known-product-risks.yaml"
VERIFICATION_DIR = CONTRACTS / "verification"
TS_RESOURCES = ROOT / "schema" / "typescript-resources.json"
TS_TABLES = ROOT / "packages" / "typescript" / "src" / "generated" / "tables.ts"
TS_PACKAGE = ROOT / "packages" / "typescript"
PY_POST = ROOT / "src" / "midas_nx" / "post"

_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_EXECUTABLE_RULE_KINDS = (
    "normalize_defaults",
    "reject_request",
    "per_id_request",
    "require_confirmation",
    "unwrap_table_by_shape",
)


@dataclass(frozen=True)
class RuleExecution:
    """The SDK behaviour probes actually run during a parity check."""

    declared: Counter[str]
    python_probes: int
    typescript_probes: int


class Failures:
    """Collects failures so one run reports everything, not just the first."""

    def __init__(self) -> None:
        self.items: list[tuple[str, str]] = []

    def add(self, where: str, message: str) -> None:
        self.items.append((where, message))

    def __bool__(self) -> bool:
        return bool(self.items)


def _load_yaml(path: Path) -> Any:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_contracts() -> list[tuple[Path, dict]]:
    return [(p, _load_yaml(p)) for p in sorted(ENDPOINT_DIR.glob("*.yaml"))]


def _iter_fields(fields: list[dict]) -> list[dict]:
    """Flatten nested `properties` so every declared field is checked once."""
    out: list[dict] = []
    for field in fields or []:
        out.append(field)
        out.extend(_iter_fields(field.get("properties") or []))
    return out


def _field_paths(fields: list[dict], prefix: str = "") -> set[str]:
    """Return declared field paths, including object and array-item members."""
    paths: set[str] = set()
    for field in fields or []:
        path = f"{prefix}.{field['key']}" if prefix else field["key"]
        paths.add(path)
        paths.update(_field_paths(field.get("properties") or [], path))
    return paths


def check_schema(contracts: list[tuple[Path, dict]], failures: Failures) -> None:
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        print(
            "ERROR: jsonschema is not installed. Run: pip install -e \".[dev]\"",
            file=sys.stderr,
        )
        raise SystemExit(2) from None

    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    for path, contract in contracts:
        if contract.get("draft"):
            # The clearest possible message for the most likely mistake: a
            # machine-drafted transcription moved out of contracts/drafts/
            # without anyone reading it.
            failures.add(
                path.name,
                "still carries `draft: true` - this is an unreviewed transcription from "
                "scripts/extract_contracts.py, not a contract. Read it, answer its "
                "TODO(review) markers, then delete that line.",
            )
            continue
        for error in sorted(validator.iter_errors(contract), key=lambda e: list(e.path)):
            location = "/".join(str(part) for part in error.path) or "(root)"
            failures.add(path.name, f"schema: {location}: {error.message}")
        if contract.get("id") != path.stem:
            failures.add(
                path.name,
                f"id {contract.get('id')!r} does not match the file name {path.stem!r}",
            )


def check_cross_references(
    contracts: list[tuple[Path, dict]],
    risks: dict,
    verification: dict[str, dict],
    failures: Failures,
) -> None:
    risk_ids = {r["id"] for r in risks.get("risks", [])}
    record_ids = {
        product: {r["id"] for r in data.get("records", [])}
        for product, data in verification.items()
    }

    for path, contract in contracts:
        for defect in contract.get("knownDefects", []):
            if defect["ref"] not in risk_ids:
                failures.add(
                    path.name,
                    f"knownDefects references unknown risk {defect['ref']!r}",
                )
        for rule in contract.get("sdkRules", []):
            ref = rule.get("riskRef")
            if ref is not None and ref not in risk_ids:
                failures.add(
                    path.name,
                    f"sdkRule {rule['id']!r} references unknown risk {ref!r}",
                )
        for record in contract.get("verification", {}).get("records", []):
            product = record["product"]
            known = record_ids.get(product)
            if known is None:
                failures.add(
                    path.name,
                    f"no verification file for product {product!r}",
                )
            elif record["ref"] not in known:
                failures.add(
                    path.name,
                    f"verification record {record['ref']!r} is not in {product}-nx.yaml",
                )

    # A risk is only useful if something enforces it. Endpoints that have no
    # contract yet are skipped: during migration that is expected, not a defect.
    contracted = {c["endpoint"] for _, c in contracts}
    for risk in risks.get("risks", []):
        if not _ID_RE.match(risk["id"]):
            failures.add(RISKS_FILE.name, f"risk id {risk['id']!r} is not a slug")
        targets = [e for e in risk.get("endpoints", []) if not e.endswith("*")]
        relevant = [e for e in targets if e in contracted]
        if not relevant:
            continue
        referencing = {
            c["endpoint"]
            for _, c in contracts
            if any(d["ref"] == risk["id"] for d in c.get("knownDefects", []))
        }
        for endpoint in relevant:
            if endpoint not in referencing:
                failures.add(
                    RISKS_FILE.name,
                    f"risk {risk['id']!r} names {endpoint}, whose contract does "
                    f"not reference it under knownDefects",
                )


def check_variant_discriminators(
    contracts: list[tuple[Path, dict]], failures: Failures
) -> None:
    """Refuse a contract whose variants claim one selector value twice.

    A variant says "these fields apply when the request carries this value".
    Two variants under the same condition therefore say one value selects two
    different field sets, which no caller and no generated union can act on.
    It means the real discriminator is wider than what was written down - the
    `/db/ELEM` tables headed `STYPE: 1` are a tension-only truss and a
    compression-only truss, separated by `TYPE`. The honest record for that is
    an unmerged table, so this is an error rather than a merge to repair here.
    """

    for path, contract in contracts:
        seen: dict[str, dict] = {}
        for variant in contract.get("variants", []):
            signature = json.dumps(variant.get("when"), sort_keys=True, ensure_ascii=False)
            if signature in seen:
                failures.add(
                    path.name,
                    f"two variants share the discriminator {signature} - one value "
                    f"cannot select two different field sets",
                )
                continue
            seen[signature] = variant


def check_safety(contracts: list[tuple[Path, dict]], failures: Failures) -> None:
    for path, contract in contracts:
        declared_paths = _field_paths(contract.get("fields", []))
        for field in _iter_fields(contract.get("fields", [])):
            for condition in field.get("appliesWhen", []):
                condition_path = condition["path"]
                if condition_path not in declared_paths:
                    failures.add(
                        path.name,
                        f"field {field['key']!r} appliesWhen references undeclared field path "
                        f"{condition_path!r}",
                    )

        rules = contract.get("sdkRules", [])
        rules_by_method: dict[str, list[dict]] = {}
        for rule in rules:
            for method in rule["appliesTo"]:
                rules_by_method.setdefault(method, []).append(rule)

        for operation in contract["operations"]:
            if operation["risk"] != "product_crash_risk":
                continue
            label = f"{operation['method']}{' ' + operation['variant'] if operation.get('variant') else ''}"
            if operation.get("mitigation") in (None, "none"):
                failures.add(
                    path.name,
                    f"{label} is product_crash_risk with no mitigation",
                )
            if not rules_by_method.get(operation["method"]):
                failures.add(
                    path.name,
                    f"{label} is product_crash_risk but no sdkRule applies to it",
                )
            if not contract.get("knownDefects"):
                failures.add(
                    path.name,
                    f"{label} is product_crash_risk but the contract references "
                    f"no entry in {RISKS_FILE.name}",
                )

        for operation in contract["operations"]:
            if operation["risk"] != "destructive":
                continue
            if "mitigation" not in operation:
                failures.add(
                    path.name,
                    f"{operation['method']} is destructive with no mitigation declared",
                )

        covered = {
            field
            for rule in rules
            if rule["kind"] in ("normalize_defaults", "reject_request")
            for field in rule.get("fields", [])
        }
        for field in _iter_fields(contract.get("fields", [])):
            # `unverified` means nobody has omitted this against a running
            # product. That is an honest gap, not a defect, so it is counted in
            # the summary rather than failed here. Only a measured `false` -
            # someone tried it and something broke - demands a rule.
            if field["safeToOmit"] is not False or field["key"] in covered:
                continue
            if field["requirement"] == "required" and not field["documentedOptional"]:
                # A required field the caller must supply; nothing to normalize.
                continue
            failures.add(
                path.name,
                f"field {field['key']!r} is documentedOptional but not safeToOmit, "
                f"and no sdkRule covers it - callers following the manual would "
                f"hit the defect",
            )

        for rule in rules:
            if rule["kind"] != "normalize_defaults":
                continue
            declared = {f["key"]: f for f in _iter_fields(contract.get("fields", []))}
            for key, value in rule["values"].items():
                declared_field = declared.get(key)
                if declared_field is None:
                    failures.add(
                        path.name,
                        f"sdkRule {rule['id']!r} defaults undeclared field {key!r}",
                    )
                elif "documentedDefault" in declared_field and declared_field["documentedDefault"] is not None:
                    if float(value) != float(declared_field["documentedDefault"]):
                        failures.add(
                            path.name,
                            f"sdkRule {rule['id']!r} sets {key}={value!r}, which is "
                            f"not its documented default "
                            f"{declared_field['documentedDefault']!r} - a normalization "
                            f"rule may make a default explicit, not invent one",
                        )


def check_manual_source(contracts: list[tuple[Path, dict]], failures: Failures) -> None:
    for path, contract in contracts:
        manual = contract["source"]["manual"]
        if manual["status"] == "documented":
            continue
        # The schema already requires a justification here; this check exists so
        # the count shows up in the CI log rather than passing silently.
        if not manual.get("justification", "").strip():
            failures.add(
                path.name,
                f"manual status is {manual['status']!r} with no justification",
            )


def _python_resources() -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "src"))
    import importlib
    import pkgutil

    import midas_nx
    from midas_nx.db.base import DbResource

    for module in pkgutil.walk_packages(midas_nx.__path__, "midas_nx."):
        importlib.import_module(module.name)

    found: dict[str, Any] = {}

    def walk(base: type) -> None:
        for child in base.__subclasses__():
            endpoint = getattr(child, "ENDPOINT", None)
            if endpoint:
                found[endpoint] = child
            walk(child)

    walk(DbResource)
    return found


# Not every endpoint is a DbResource.  ``function_endpoints()`` discovers the
# top-level Python calls and npm operation metadata instead of maintaining an
# endpoint-by-endpoint exception list.  This is deliberately parity metadata:
# the SDKs are checked as subjects and never supply contract facts.
_FUNCTION_ENDPOINTS = function_endpoints()


def _rule_counts(contracts: list[tuple[Path, dict]]) -> Counter[str]:
    return Counter(
        rule["kind"]
        for _, contract in contracts
        for rule in contract.get("sdkRules", [])
        if rule["kind"] in _EXECUTABLE_RULE_KINDS
    )


def check_parity(contracts: list[tuple[Path, dict]], failures: Failures) -> RuleExecution:
    try:
        python_resources = _python_resources()
    except Exception as exc:  # pragma: no cover - import failure is a hard stop
        print(f"ERROR: could not import midas_nx: {exc}", file=sys.stderr)
        raise SystemExit(2) from None

    ts_by_endpoint: dict[str, dict] = {}
    if TS_RESOURCES.exists():
        manifest = json.loads(TS_RESOURCES.read_text(encoding="utf-8"))
        for resource in manifest.get("resources", []):
            ts_by_endpoint[resource["endpoint"]] = resource

    for path, contract in contracts:
        endpoint = contract["endpoint"]
        methods = {op["method"] for op in contract["operations"]}
        products = set(contract["products"])

        function_endpoint = _FUNCTION_ENDPOINTS.get(endpoint)
        if function_endpoint is not None:
            python = function_endpoint.python
            if python is None:
                failures.add(path.name, f"no Python plain function exposes {endpoint}")
            elif python.methods != methods:
                failures.add(
                    path.name,
                    f"Python plain functions {list(python.entries)} serve "
                    f"{sorted(python.methods)}, contract declares {sorted(methods)}",
                )

            typescript = function_endpoint.typescript
            if typescript is None:
                failures.add(path.name, f"no npm plain function exposes {endpoint}")
            else:
                if typescript.methods != methods:
                    failures.add(
                        path.name,
                        f"npm plain functions {list(typescript.entries)} serve "
                        f"{sorted(typescript.methods)}, contract declares {sorted(methods)}",
                    )
                # Python plain functions do not carry product metadata to
                # compare.  npm operation metadata does when it is present,
                # so validate that independently rather than inventing Python
                # product support from a function's implementation.
                if typescript.products is not None and typescript.products != products:
                    failures.add(
                        path.name,
                        f"npm plain functions {list(typescript.entries)} declare products "
                        f"{sorted(typescript.products)}, contract declares {sorted(products)}",
                    )
            continue

        resource = python_resources.get(endpoint)
        if resource is None:
            failures.add(
                path.name,
                f"no Python resource exposes {endpoint} - the contract and the "
                f"Python SDK disagree about what exists",
            )
        else:
            py_methods = set(getattr(resource, "METHODS", set()))
            if py_methods != methods:
                failures.add(
                    path.name,
                    f"Python {resource.__name__} serves {sorted(py_methods)}, "
                    f"contract declares {sorted(methods)}",
                )
            py_products = set(getattr(resource, "PRODUCTS", set()))
            if py_products != products:
                failures.add(
                    path.name,
                    f"Python {resource.__name__} declares products "
                    f"{sorted(py_products)}, contract declares {sorted(products)}",
                )
            _check_python_normalization(path, contract, resource, failures)

        ts_resource = ts_by_endpoint.get(endpoint)
        if ts_resource is None:
            if ts_by_endpoint:
                failures.add(
                    path.name,
                    f"no npm resource exposes {endpoint}",
                )
        else:
            if set(ts_resource["methods"]) != methods:
                failures.add(
                    path.name,
                    f"npm {ts_resource['exportName']} serves "
                    f"{sorted(ts_resource['methods'])}, contract declares "
                    f"{sorted(methods)}",
                )
            if set(ts_resource["products"]) != products:
                failures.add(
                    path.name,
                    f"npm {ts_resource['exportName']} declares products "
                    f"{sorted(ts_resource['products'])}, contract declares "
                    f"{sorted(products)}",
                )
            _check_typescript_normalization(path, contract, ts_resource, failures)

    declared = _rule_counts(contracts)
    python_probes = _check_python_base_safety_rules(contracts, declared, failures)
    typescript_probes = _check_typescript_base_safety_rules(contracts, declared, failures)
    return RuleExecution(declared, python_probes, typescript_probes)


_ENVELOPE_KEYS = frozenset({"Assign", "Argument"})


def _contract_leaves(contract: dict) -> set[str]:
    """Every wire name a contract names anywhere, variants included.

    Compared by leaf name rather than by path on purpose. A contract and an
    SDK disagree about nesting often enough that a path mismatch is evidence
    of nothing; a name one of them has never heard of is evidence. This is the
    same reading `scripts/info_baseline.py`'s reverse sweep takes.
    """
    out: set[str] = set()

    def walk(fields: list[dict] | None) -> None:
        for field in fields or []:
            out.add(field["key"])
            walk(field.get("properties"))

    walk(contract.get("fields"))
    for variant in contract.get("variants") or []:
        walk(variant.get("fields"))
    return out - _ENVELOPE_KEYS


def _payload_leaves(payload: type) -> set[str]:
    """Every wire name a payload TypedDict names, nested TypedDicts followed.

    Python models a nested record as a sibling TypedDict referenced from an
    annotation - `LANE_ITEMS: List[LineLaneItem]` - so reading only the payload
    type's own keys sees the array and none of its members. Following the
    annotations is what makes this comparable with a contract's `properties`.
    """
    import typing

    seen: set[type] = set()
    out: set[str] = set()

    def walk(typed_dict: type) -> None:
        if typed_dict in seen:
            return
        seen.add(typed_dict)
        try:
            hints = typing.get_type_hints(typed_dict)
        except Exception:  # noqa: BLE001 - a forward ref that will not resolve
            hints = dict(getattr(typed_dict, "__annotations__", {}))
        for key, annotation in hints.items():
            out.add(key)
            pending = [annotation]
            while pending:
                current = pending.pop()
                pending.extend(typing.get_args(current))
                if isinstance(current, type) and hasattr(current, "__required_keys__"):
                    walk(current)

    walk(payload)
    return out - _ENVELOPE_KEYS



def _python_payload_types() -> dict[str, dict[str, type]]:
    """Every TypedDict the package defines, by class name and then by module.

    `surface.payloadTypeName` is the contract's own record of the published npm
    name, and the Python TypedDict carries the same name for the 280 resources
    that have a surface block. That shared name is the join - but it is not
    unique on the Python side: 21 names are defined in two or three modules,
    because the RC and steel design chapters both have an endpoint called SRDF
    and their payloads are different. npm namespaces those; Python does not.
    Keeping the module lets the caller pick the one belonging to the resource
    it is actually checking, instead of whichever module imported first.
    """
    sys.path.insert(0, str(ROOT / "src"))
    import importlib
    import pkgutil

    import midas_nx

    found: dict[str, dict[str, type]] = {}
    for module in pkgutil.walk_packages(midas_nx.__path__, "midas_nx."):
        imported = importlib.import_module(module.name)
        for name, obj in vars(imported).items():
            if (
                isinstance(obj, type)
                and hasattr(obj, "__required_keys__")
                and obj.__module__ == module.name
            ):
                found.setdefault(name, {})[module.name] = obj
    return found


@dataclass(frozen=True)
class FieldParity:
    """What the field-name comparison actually looked at."""

    compared: int
    partially_declared: int
    no_python_type: int
    ambiguous: int


def check_field_parity(
    contracts: list[tuple[Path, dict]], failures: Failures
) -> FieldParity:
    """Fail when a contract omits a wire name its own Python SDK publishes.

    `check_parity` compares endpoints, methods, products and normalization
    rules, and never compares field names. That gap is why /db/ELNK published
    four fields for months while the TypedDict two directories away published
    twelve, and why /db/SLANch shipped an npm payload type naming nothing the
    record holds: every automated check passed the whole time.

    One direction only. A contract naming more than the TypedDict is the
    expected state - a TypedDict is documentation, npm generates its payload
    types from the contract, and the contract is meant to run ahead. The
    reverse is the defect: a name the SDK ships and the source of truth has
    never recorded.

    This uses the SDK as a subject, exactly as the rest of parity does. A
    failure here says the contract is incomplete, and the fix is to source the
    field from the manual, a live record or /info - never to copy the
    TypedDict, which is not a permitted source.
    """
    payload_types = _python_payload_types()
    resources = _python_resources()
    compared = partially_declared = no_python_type = ambiguous = 0

    for path, contract in contracts:
        name = (contract.get("surface") or {}).get("payloadTypeName")
        if not name:
            continue
        candidates = payload_types.get(name) or {}
        resource = resources.get(contract["endpoint"])
        module = getattr(resource, "__module__", None)
        if module in candidates:
            payload = candidates[module]
        elif len(candidates) == 1:
            payload = next(iter(candidates.values()))
        elif candidates:
            # The name is defined in several modules and none of them is the
            # one this endpoint's resource lives in, so there is no honest way
            # to say which payload belongs to this contract. Comparing a
            # guess is worse than comparing nothing: it reports the other
            # chapter's fields as missing from this one.
            ambiguous += 1
            failures.add(
                path.name,
                f"payloadTypeName {name!r} is defined in "
                f"{', '.join(sorted(candidates))} and in none of them does this "
                f"endpoint's resource live, so field parity cannot tell which "
                f"payload this contract describes",
            )
            continue
        else:
            # A contract may name an npm type with no Python counterpart; the
            # generator builds those from the contract alone.
            no_python_type += 1
            continue
        compared += 1
        waived = {entry["name"] for entry in contract.get("sdkOnly") or []}
        # A contract may declare part of its field list missing, and 20 do.
        # That used to skip the whole contract, which left 214 wire names the
        # SDKs ship unchecked and could not tell a declared gap from an
        # unexamined one. Each unmergedTables entry now records the names its
        # table holds, so the waiver is itemised: a name that table accounts
        # for is a declared gap, and a name in neither the contract nor any of
        # those tables is a defect. That itemisation is what found /db/THIS-M1
        # publishing INC_METHOD at the root of a record whose server-declared
        # shape puts it inside INC_CTRL.
        declared_gaps = {
            name
            for entry in (contract.get("extraction") or {}).get("unmergedTables", [])
            for name in entry.get("fieldNames") or []
        }
        if declared_gaps:
            partially_declared += 1
        waived |= declared_gaps
        missing = sorted(_payload_leaves(payload) - _contract_leaves(contract) - waived)
        if missing:
            failures.add(
                path.name,
                f"Python {name} names {len(missing)} field(s) this contract records "
                f"nowhere: {', '.join(missing)}. Source them from the manual, a live "
                f"record or /info - the TypedDict is not a permitted source",
            )

    return FieldParity(compared, partially_declared, no_python_type, ambiguous)


def _load_tables() -> list[tuple[Path, dict]]:
    if not TABLE_DIR.is_dir():
        return []
    return [(p, _load_yaml(p)) for p in sorted(TABLE_DIR.glob("*.yaml"))]


def _sdk_names_table_type(source: str, value: str) -> bool:
    """Recognise literal table strings and the audited X/Y/Z helper form.

    The two SDKs deliberately expose directional summary tables through one
    helper (``get_mass_summary_table("X")`` / ``defineDirectionalTable``),
    rather than duplicating three wrappers.  A literal-only search wrongly
    calls that public surface absent even though its prefix and direction are
    fixed by the implementation.  Accept only the documented three-axis form;
    every other TABLE_TYPE still has to be named literally.
    """
    if f'"{value}"' in source:
        return True
    prefix, separator, direction = value.rpartition("_")
    if not separator or direction not in {"X", "Y", "Z"}:
        return False
    return f'"{prefix}_{{direction}}"' in source or f'"{prefix}_"' in source


def check_tables(
    tables: list[tuple[Path, dict]],
    endpoints: set[str],
    risks: dict,
    verification: dict[str, dict],
    failures: Failures,
) -> None:
    """Validate the second layer, and check both SDKs know every TABLE_TYPE.

    A table contract's parity question is not whether a class exists - 89 tables
    share one route - but whether the string that selects it is reachable from
    both language surfaces. A TABLE_TYPE only one SDK knows is a table only one
    SDK's users can read.
    """
    if not tables:
        return
    from jsonschema import Draft202012Validator

    schema = json.loads(TABLE_SCHEMA_FILE.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    risk_ids = {r["id"] for r in risks.get("risks", [])}
    record_ids = {
        product: {r["id"] for r in data.get("records", [])}
        for product, data in verification.items()
    }

    python_source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(PY_POST.glob("*.py"))
    ) if PY_POST.is_dir() else ""
    # Design-code tables are routed through their own /DESIGN/.../TABLE modules.
    design_dir = ROOT / "src" / "midas_nx" / "design"
    if design_dir.is_dir():
        python_source += "\n".join(
            path.read_text(encoding="utf-8") for path in sorted(design_dir.rglob("*.py"))
        )
    typescript_source = TS_TABLES.read_text(encoding="utf-8") if TS_TABLES.exists() else ""

    for path, table in tables:
        if table.get("draft"):
            failures.add(
                path.name,
                "still carries `draft: true` - this is an unreviewed transcription from "
                "scripts/extract_contracts.py, not a contract.",
            )
            continue
        for error in sorted(validator.iter_errors(table), key=lambda e: list(e.path)):
            location = "/".join(str(part) for part in error.path) or "(root)"
            failures.add(path.name, f"schema: {location}: {error.message}")
        if table.get("id") != path.stem:
            failures.add(path.name, f"id {table.get('id')!r} does not match file name {path.stem!r}")

        if table["endpoint"] not in endpoints:
            failures.add(
                path.name,
                f"routes through {table['endpoint']}, which has no endpoint contract - "
                f"the shared request shape has to be contracted before a table can "
                f"declare how it departs from it",
            )

        for defect in table.get("knownDefects", []):
            if defect["ref"] not in risk_ids:
                failures.add(path.name, f"knownDefects references unknown risk {defect['ref']!r}")
        for record in table.get("verification", {}).get("records", []):
            known = record_ids.get(record["product"])
            if known is None:
                failures.add(path.name, f"no verification file for product {record['product']!r}")
            elif record["ref"] not in known:
                failures.add(
                    path.name,
                    f"verification record {record['ref']!r} is not in {record['product']}-nx.yaml",
                )

        for entry in table.get("tableTypes", []):
            value = entry["value"]
            # Both SDKs can reach any table by passing the raw string, so this is
            # not about reachability - it is about whether a caller can find the
            # variant without already knowing it exists. A value one language
            # names and the other does not is a table only one language's users
            # will discover.
            if not _sdk_names_table_type(python_source, value):
                failures.add(
                    path.name,
                    f"TABLE_TYPE {value!r} is not named anywhere in the Python SDK",
                )
            if not _sdk_names_table_type(typescript_source, value):
                failures.add(
                    path.name,
                    f"TABLE_TYPE {value!r} is not named anywhere in the npm SDK - a "
                    f"caller can still pass the string, but only if they already know "
                    f"the variant exists",
                )

        # A table's own request fields are held to the endpoint contracts' rule:
        # a condition names a field that exists, and a nested type is recorded
        # at a path that exists.
        additional = (table.get("requestFields") or {}).get("additional") or []
        declared_paths = _field_paths(additional)
        for field in _iter_fields(additional):
            for condition in field.get("appliesWhen", []):
                if condition["path"] not in declared_paths:
                    failures.add(
                        path.name,
                        f"request field {field['key']!r} appliesWhen references undeclared "
                        f"path {condition['path']!r}",
                    )
        for entry in (table.get("surface") or {}).get("nestedTypes", []):
            if entry["path"] not in declared_paths:
                failures.add(
                    path.name,
                    f"surface.nestedTypes names {entry['name']} at {entry['path']!r}, "
                    f"which requestFields.additional does not declare",
                )

        # An unresolved manual contradiction must stay visible rather than being
        # quietly settled in favour of whichever spelling someone typed first.
        for defect in table.get("manualDefects", []):
            if defect.get("resolved") is False and not defect.get("evidence", "").strip():
                failures.add(
                    path.name,
                    f"unresolved manualDefect about {defect['describes']} with no evidence "
                    f"recorded - say what was checked and what is still unknown",
                )


def _normalization_values(contract: dict) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for rule in contract.get("sdkRules", []):
        if rule["kind"] == "normalize_defaults":
            merged.update(rule["values"])
    return merged


def _check_python_normalization(
    path: Path, contract: dict, resource: type, failures: Failures
) -> None:
    expected = _normalization_values(contract)
    if not expected:
        return
    sent: dict[str, Any] = {}

    class _Recorder:
        def request(self, method: str, endpoint: str, body: Any = None) -> dict:
            sent.update(body["Assign"]["1"])
            return {}

        def check_product(self, products: Any, name: str) -> None:
            return None

    for verb in ("create", "update"):
        sent.clear()
        try:
            getattr(resource, verb)({1: {}}, client=_Recorder())
        except Exception as exc:  # pragma: no cover - reported, not raised
            failures.add(path.name, f"Python {resource.__name__}.{verb}() raised: {exc}")
            continue
        for key, value in expected.items():
            if key not in sent:
                failures.add(
                    path.name,
                    f"Python {resource.__name__}.{verb}() sent a payload without "
                    f"{key!r}; the contract requires it be normalized to {value!r}",
                )
            elif float(sent[key]) != float(value):
                failures.add(
                    path.name,
                    f"Python {resource.__name__}.{verb}() sent {key}={sent[key]!r}, "
                    f"contract requires {value!r}",
                )


def _check_typescript_normalization(
    path: Path, contract: dict, ts_resource: dict, failures: Failures
) -> None:
    expected = _normalization_values(contract)
    declared = ts_resource.get("payloadDefaults") or {}
    if not expected:
        if declared:
            failures.add(
                path.name,
                f"npm {ts_resource['exportName']} declares payloadDefaults "
                f"{declared!r} that no contract rule asks for",
            )
        return
    for key, value in expected.items():
        if key not in declared:
            failures.add(
                path.name,
                f"npm {ts_resource['exportName']} does not normalize {key!r}; the "
                f"contract requires it be sent as {value!r}",
            )
        elif float(declared[key]) != float(value):
            failures.add(
                path.name,
                f"npm {ts_resource['exportName']} normalizes {key} to "
                f"{declared[key]!r}, contract requires {value!r}",
            )


def _response_shape_cases(
    contracts: list[tuple[Path, dict]], failures: Failures
) -> list[str]:
    """Read response fixtures from the contract rather than an SDK test."""
    cases: set[str] = set()
    for path, contract in contracts:
        for rule in contract.get("sdkRules", []):
            if rule["kind"] != "unwrap_table_by_shape":
                continue
            declared = rule.get("responseCases", [])
            if len(declared) != 4:
                failures.add(
                    path.name,
                    "unwrap_table_by_shape must declare the four observed response cases",
                )
            cases.update(declared)
    return sorted(cases)


def _table_shape_fixture(case: str) -> tuple[dict[str, Any], dict[str, Any]]:
    table = {"HEAD": ["Node", "FX"], "DATA": [["1", "-10"]]}
    if case == "table_name":
        return {"Requested table": table}, table
    if case == "result_table":
        return {"Result Table": table}, table
    if case == "empty_with_table":
        return {"empty": table}, table
    if case == "no_table":
        return {"message": ""}, {}
    raise ValueError(f"unknown unwrap_table_by_shape response case {case!r}")


def _check_python_base_safety_rules(
    contracts: list[tuple[Path, dict]], declared: Counter[str], failures: Failures
) -> int:
    """Exercise shared destructive safeguards and response decoding once per kind."""
    from midas_nx.client import DestructiveOperationError
    from midas_nx.db.base import DbResource

    class _ProbeResource(DbResource):
        ENDPOINT = "/db/CONTRACT-SAFETY-PROBE"
        NAME = "Contract safety probe"
        METHODS = frozenset({"DELETE"})

    probes = 0
    if declared["normalize_defaults"]:
        # _check_python_normalization() already executes each declared rule
        # against its actual resource above, for create and update.
        probes += 1

    if declared["reject_request"]:
        from midas_nx.client import MidasRequestError
        from midas_nx.ope import generate_bridge_girder_diagram

        try:
            generate_bridge_girder_diagram({"BATCH": True, "BRDG_GROUP": "CONTRACT-PROBE"})
        except MidasRequestError:
            pass
        except Exception as exc:  # pragma: no cover - reported, not raised
            failures.add("sdkRules", f"Python reject_request raised {exc!r}")
        else:
            failures.add(
                "sdkRules",
                "Python reject_request allowed the /ope/GSBG batch-exclusive BRDG_GROUP field",
            )

        # The second reject_request shape, and a different one: a field the
        # server accepts and discards, on a DbResource rather than an
        # operation. /db/MVHL's VEH_DEFAULT answers {"message": ""} for an
        # empty object and stores no vehicle, so the caller's only signal is a
        # later GET. One probe per kind would have left this to whichever
        # language happened to implement it.
        from midas_nx.db.moving_loads import Vehicles

        try:
            Vehicles.create({1: {"MVLD_CODE": 2, "VEH_DEFAULT": {}}})
        except MidasRequestError:
            pass
        except Exception:  # pragma: no cover - reported, not raised
            # Anything else means the call reached the transport, so the rule
            # did not fire. Whatever the transport then said - a 401 without a
            # key, a timeout with one - is not the finding; the finding is that
            # the request was allowed to leave.
            failures.add(
                "sdkRules",
                "Python reject_request let an empty /db/MVHL VEH_DEFAULT reach the "
                "transport; the server accepts it and silently stores nothing",
            )
        else:
            failures.add(
                "sdkRules",
                "Python reject_request allowed an empty /db/MVHL VEH_DEFAULT",
            )

        # The third reject_request shape: not a value the server discards but
        # a value it never sees. /db/PRES's DIRECTION is documented Optional
        # with a default the product refuses, so the omission is what fails.
        # Probed separately because the check is the opposite one - the field
        # has to be absent for the rule to fire - and a runtime that only
        # implemented the empty-object case would pass every probe above.
        from midas_nx.db.static_loads import PressureLoad

        try:
            PressureLoad.create(
                {4: {"ITEMS": [{"LCNAME": "CONTRACT-PROBE", "FACE_EDGE_TYPE": "FACE"}]}}
            )
        except MidasRequestError:
            pass
        except Exception:  # pragma: no cover - reported, not raised
            failures.add(
                "sdkRules",
                "Python reject_request let a /db/PRES item with no DIRECTION reach the "
                "transport; the server applies the documented default and refuses it",
            )
        else:
            failures.add(
                "sdkRules",
                "Python reject_request allowed a /db/PRES item with no DIRECTION",
            )
        probes += 1

    if declared["per_id_request"]:

        class _Recorder:
            def __init__(self, fail_at: str | None = None) -> None:
                self.calls: list[tuple[str, str, Any]] = []
                self.fail_at = fail_at

            def request(self, method: str, endpoint: str, body: Any = None) -> dict:
                self.calls.append((method, endpoint, body))
                if endpoint == self.fail_at:
                    raise RuntimeError("recorded DELETE failure")
                return {}

            def check_product(self, products: Any, name: str) -> None:
                return None

        recorder = _Recorder()
        try:
            _ProbeResource.delete([7, 9], client=recorder)
        except Exception as exc:  # pragma: no cover - reported, not raised
            failures.add("sdkRules", f"Python base per_id_request raised: {exc}")
        else:
            expected = [
                ("DELETE", "/db/CONTRACT-SAFETY-PROBE/7", None),
                ("DELETE", "/db/CONTRACT-SAFETY-PROBE/9", None),
            ]
            if recorder.calls != expected:
                failures.add(
                    "sdkRules",
                    "Python base per_id_request did not send one DELETE per id URL; "
                    f"recorded {recorder.calls!r}",
                )

        failing = _Recorder("/db/CONTRACT-SAFETY-PROBE/7")
        try:
            _ProbeResource.delete([7, 9], client=failing)
        except RuntimeError:
            pass
        except Exception as exc:  # pragma: no cover - reported, not raised
            failures.add("sdkRules", f"Python base per_id_request raised {exc!r} on failure")
        else:
            failures.add("sdkRules", "Python base per_id_request did not propagate a DELETE failure")
        if failing.calls != [("DELETE", "/db/CONTRACT-SAFETY-PROBE/7", None)]:
            failures.add(
                "sdkRules",
                "Python base per_id_request continued after the first DELETE failure; "
                f"recorded {failing.calls!r}",
            )
        probes += 1

    if declared["require_confirmation"]:

        class _Recorder:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str, Any]] = []

            def request(self, method: str, endpoint: str, body: Any = None) -> dict:
                self.calls.append((method, endpoint, body))
                return {}

            def check_product(self, products: Any, name: str) -> None:
                return None

        recorder = _Recorder()
        try:
            _ProbeResource.delete_all(client=recorder)
        except DestructiveOperationError:
            pass
        except Exception as exc:  # pragma: no cover - reported, not raised
            failures.add(
                "sdkRules",
                f"Python base require_confirmation raised {exc!r} instead of DestructiveOperationError",
            )
        else:
            failures.add(
                "sdkRules",
                "Python base require_confirmation allowed whole-table DELETE without confirm=True",
            )
        if recorder.calls:
            failures.add(
                "sdkRules",
                "Python base require_confirmation sent a whole-table DELETE before rejecting it",
            )
        probes += 1

    if declared["unwrap_table_by_shape"]:
        from midas_nx.post.base import unwrap_table

        for case in _response_shape_cases(contracts, failures):
            response, expected = _table_shape_fixture(case)
            if unwrap_table(response) != expected:
                failures.add(
                    "sdkRules",
                    f"Python unwrap_table_by_shape failed contract response case {case!r}",
                )
        probes += 1

    return probes


def _check_typescript_base_safety_rules(
    contracts: list[tuple[Path, dict]], declared: Counter[str], failures: Failures
) -> int:
    """Run one npm implementation probe for every contracted safety kind."""
    required = [kind for kind in _EXECUTABLE_RULE_KINDS if declared[kind]]
    if not required:
        return 0
    command = [
        "npm.cmd" if sys.platform == "win32" else "npm",
        "exec",
        "--",
        "vitest",
        "run",
        "tests/contract-safety.test.ts",
        "--reporter=verbose",
    ]
    environment = os.environ.copy()
    if declared["unwrap_table_by_shape"]:
        environment["MIDAS_UNWRAP_TABLE_RESPONSE_CASES"] = json.dumps(
            _response_shape_cases(contracts, failures)
        )
    try:
        result = subprocess.run(
            command,
            cwd=TS_PACKAGE,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
        )
    except OSError as exc:
        failures.add(
            "sdkRules",
            f"npm base safety probes could not run; install npm dependencies first: {exc}",
        )
        return 0

    output = (result.stdout + result.stderr).strip()
    if result.returncode:
        failures.add(
            "sdkRules",
            f"npm base safety probes failed; this is an SDK implementation defect:\n{output}",
        )
        return 0
    for kind in required:
        if f"{kind}:" not in output:
            failures.add("sdkRules", f"npm base {kind} probe was not executed")
    return len(required)


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    skip_parity = "--no-parity" in argv

    contracts = _load_contracts()
    if not contracts:
        print(f"ERROR: no contracts found under {ENDPOINT_DIR}", file=sys.stderr)
        return 2

    risks = _load_yaml(RISKS_FILE)
    verification = {
        path.stem.removesuffix("-nx"): _load_yaml(path)
        for path in sorted(VERIFICATION_DIR.glob("*.yaml"))
    }

    tables = _load_tables()

    failures = Failures()
    check_schema(contracts, failures)
    check_cross_references(contracts, risks, verification, failures)
    check_variant_discriminators(contracts, failures)
    check_safety(contracts, failures)
    check_manual_source(contracts, failures)
    check_tables(
        tables, {c['endpoint'] for _, c in contracts}, risks, verification, failures
    )
    parity: RuleExecution | None = None
    field_parity: FieldParity | None = None
    if not skip_parity:
        parity = check_parity(contracts, failures)
        field_parity = check_field_parity(contracts, failures)

    crash_risk = sum(
        1
        for _, c in contracts
        for op in c["operations"]
        if op["risk"] == "product_crash_risk"
    )
    fields = [f for _, c in contracts for f in _iter_fields(c.get("fields", []))]
    omission = {state: 0 for state in ("proven safe", "proven unsafe", "unverified")}
    for entry in fields:
        value = entry.get("safeToOmit")
        key = "proven safe" if value is True else "proven unsafe" if value is False else "unverified"
        omission[key] += 1

    print(
        f"contracts: {len(contracts)} endpoints, "
        f"{sum(len(c['operations']) for _, c in contracts)} operations, "
        f"{crash_risk} carrying product_crash_risk, "
        f"{len(risks.get('risks', []))} known risks, "
        f"{sum(len(v.get('records', [])) for v in verification.values())} "
        f"verification records"
    )
    if tables:
        table_types = sum(len(t.get("tableTypes", [])) for _, t in tables)
        unresolved = sum(
            1
            for _, t in tables
            for d in t.get("manualDefects", [])
            if d.get("resolved") is False
        )
        print(
            f"result tables: {len(tables)} contracted, {table_types} TABLE_TYPE values, "
            f"{unresolved} unresolved manual contradiction(s)"
        )
    print(
        f"omission safety of {len(fields)} fields: "
        + ", ".join(f"{count} {label}" for label, count in omission.items())
        + ". `unverified` is an honest gap, not a failure - it says nobody has"
        " omitted that field against a running product."
    )
    if parity is not None:
        declared = ", ".join(
            f"{kind}={parity.declared[kind]}" for kind in _EXECUTABLE_RULE_KINDS
        )
        print(
            "sdk rule execution: "
            f"{sum(parity.declared.values())} declared executable rules ({declared}); "
            f"ran {parity.python_probes} Python and {parity.typescript_probes} npm rule-kind probes"
        )
    if field_parity is not None:
        print(
            f"field parity: {field_parity.compared} contract(s) compared against the "
            f"Python payload type of the same name, "
            f"{field_parity.partially_declared} of them waiving part of the comparison "
            f"through unmergedTables, {field_parity.no_python_type} naming a type Python does "
            f"not define, {field_parity.ambiguous} whose type name Python defines in several "
            f"modules. Only the direction that matters is enforced: a wire name the SDK "
            f"ships and no contract records."
        )

    if failures:
        print(f"\n{len(failures.items)} problem(s):")
        for where, message in failures.items:
            print(f"  {where}: {message}")
        return 1

    if parity is None:
        print("OK - contracts valid; SDK parity and behaviour probes were skipped.")
    else:
        print(
            "OK - contracts valid; endpoint parity and the declared sdkRule kinds "
            "were checked against both SDKs."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
