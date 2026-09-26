"""Live-server counterpart to scripts/check_manual_drift.py: for every
DbResource subclass in this SDK, compares its TypedDict's field names
against the field names the live NX server actually reports via
``GET /info/db/...`` (DbResource.info(), added v0.10.0).

Unlike check_manual_drift.py this needs a running MIDAS Gen NX or Civil NX
instance with the Open API connected (see src/midas_nx/README.md Quick
Start) — it is a local dev tool, not something CI can run.

Run with the dev environment active (``pip install -e ".[dev]"``), e.g.:
    python scripts/check_drift.py --product gen
    python scripts/check_drift.py --product civil --resource /db/MATL

Exit code 0 -> no field-name drift found among the resources checked.
Exit code 1 -> at least one resource has a field-name mismatch.
Exit code 2 -> couldn't connect, or the server rejected the connection.
"""
from __future__ import annotations

import argparse
import importlib
import json
import pkgutil
import sys
from functools import cache
from pathlib import Path
from typing import Optional

import yaml

import midas_nx
from midas_nx.client import MidasAPIError, MidasClient
from midas_nx.db.base import DbResource

ROOT = Path(__file__).resolve().parent.parent


def _import_all_submodules() -> None:
    for _, name, _ in pkgutil.walk_packages(midas_nx.__path__, prefix=midas_nx.__name__ + "."):
        importlib.import_module(name)


def _all_resources() -> list[type]:
    """Every concrete DbResource subclass across the whole package (db/*,
    db/properties/*, design/*, design/rc_kds/*), found by walking every
    submodule and then DbResource's subclass tree — there's no central
    registry, so this is the only reliable enumeration."""
    _import_all_submodules()
    seen: set[type] = set()
    stack = list(DbResource.__subclasses__())
    resources = []
    while stack:
        cls = stack.pop()
        if cls in seen:
            continue
        seen.add(cls)
        stack.extend(cls.__subclasses__())
        if "ENDPOINT" in cls.__dict__:
            resources.append(cls)
    return sorted(resources, key=lambda c: c.ENDPOINT)


def _payload_fields(cls: type) -> Optional[set[str]]:
    """Look up the sibling ``{ClassName}Payload`` TypedDict in the resource's
    own module — the naming convention every chapter module follows, since
    DbResource itself has no attribute linking a resource to its TypedDict."""
    module = sys.modules.get(cls.__module__)
    payload = getattr(module, cls.__name__ + "Payload", None)
    annotations = getattr(payload, "__annotations__", None)
    return set(annotations.keys()) if annotations else None


@cache
def _contract_field_products() -> dict[str, dict[str, frozenset[str]]]:
    """Return explicit top-level contract field product gates by endpoint.

    A resource's Python ``TypedDict`` is shared by Civil and Gen, so it
    represents their combined payload surface. Contracts may instead declare
    a field as belonging to only one product. Applying that documented gate
    here prevents a Gen-only field from becoming a false Civil drift report.
    Fields without an explicit contract gate remain checked on both products.
    """
    result: dict[str, dict[str, frozenset[str]]] = {}
    for path in (ROOT / "contracts" / "endpoints").glob("*.yaml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("endpoint"), str):
            continue
        fields = data.get("fields")
        if not isinstance(fields, list):
            continue
        gates: dict[str, frozenset[str]] = {}
        for field in fields:
            if not isinstance(field, dict):
                continue
            key = field.get("key")
            products = field.get("products")
            if isinstance(key, str) and isinstance(products, list) and all(isinstance(p, str) for p in products):
                gates[key] = frozenset(products)
        if gates:
            result[data["endpoint"]] = gates
    return result


def _fields_for_product(sdk_fields: set[str], endpoint: str, product: str) -> set[str]:
    """Remove only contract-declared fields unavailable in ``product``."""
    gates = _contract_field_products().get(endpoint, {})
    return {field for field in sdk_fields if product in gates.get(field, frozenset({"civil", "gen"}))}


def _server_fields(info: object) -> set[str]:
    """Return the field names from either observed ``/info`` envelope.

    Older NX builds returned the resource key directly (``{"NODE": {...}}``).
    Current Civil and Gen builds wrap a JSON Schema below ``"Argument"`` and
    place a ``"$schema"`` string first; its actual wire fields are under
    ``Argument.properties``. Selecting the first top-level value makes the
    schema URI look like an object and crashes before any drift can be
    reported, while selecting ``Argument`` itself compares ``type`` and
    ``properties`` rather than the endpoint's fields. Prefer the current
    envelope, but retain the legacy direct-resource form.
    """
    if not isinstance(info, dict):
        return set()
    argument = info.get("Argument")
    if isinstance(argument, dict):
        properties = argument.get("properties")
        return set(properties) if isinstance(properties, dict) else set(argument)
    for value in info.values():
        if isinstance(value, dict):
            properties = value.get("properties")
            return set(properties) if isinstance(properties, dict) else set(value)
    return set()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", choices=["gen", "civil"], default="gen")
    parser.add_argument("--mapi-key", help="defaults to MIDAS_MAPI_KEY env var")
    parser.add_argument("--base-url", help="defaults to MIDAS_BASE_URL env var")
    parser.add_argument(
        "--resource", help="only check resources whose ENDPOINT contains this substring"
    )
    parser.add_argument("--out", help="path to write the report JSON (optional)")
    args = parser.parse_args()

    client = MidasClient(mapi_key=args.mapi_key, base_url=args.base_url, product=args.product)
    try:
        health = client.verify_connection()
    except MidasAPIError as exc:
        print(f"Could not reach the MIDAS NX Open API server: {exc}", file=sys.stderr)
        sys.exit(2)
    if health.get("status") != "connected":
        print(f"Server reachable but not connected: {health}", file=sys.stderr)
        sys.exit(2)

    resources = _all_resources()
    if args.resource:
        resources = [r for r in resources if args.resource in r.ENDPOINT]

    drift = []
    errors = []
    skipped_no_payload = []
    checked = 0

    for cls in resources:
        if client.product.value not in cls.PRODUCTS:
            continue
        payload_fields = _payload_fields(cls)
        if payload_fields is None:
            skipped_no_payload.append(cls.ENDPOINT)
            continue
        sdk_fields = _fields_for_product(payload_fields, cls.ENDPOINT, client.product.value)
        try:
            info = cls.info(client=client)
        except MidasAPIError as exc:
            errors.append({"endpoint": cls.ENDPOINT, "error": str(exc)})
            continue

        checked += 1
        server_fields = _server_fields(info)

        missing_in_sdk = sorted(server_fields - sdk_fields)
        missing_on_server = sorted(sdk_fields - server_fields)
        if missing_in_sdk or missing_on_server:
            drift.append({
                "endpoint": cls.ENDPOINT,
                "module": cls.__module__,
                "missing_in_sdk": missing_in_sdk,
                "missing_on_server": missing_on_server,
            })

    result = {
        "product": client.product.value,
        "checked": checked,
        "drift_count": len(drift),
        "error_count": len(errors),
        "skipped_no_payload_typeddict": skipped_no_payload,
        "drift": drift,
        "errors": errors,
    }
    output = json.dumps(result, ensure_ascii=False, indent=2)
    print(output)
    if args.out:
        Path(args.out).write_text(output + "\n", encoding="utf-8")

    sys.exit(1 if drift else 0)


if __name__ == "__main__":
    main()
