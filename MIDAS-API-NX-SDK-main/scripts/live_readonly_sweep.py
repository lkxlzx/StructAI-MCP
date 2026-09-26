"""Read-only live sweep: GET every DbResource this SDK wraps, against a real
running Gen NX / Civil NX session, and report which endpoints answer.

This is PLAN.md's A1 tool for the *breadth* axis. scripts/live_smoke.py proves
one path end to end (write -> analyze -> read) but only touches ~10 endpoints;
this touches every GET-capable resource and tells you which of the SDK's
transcribed endpoints the server actually recognizes.

SAFE TO RUN AGAINST AN OPEN MODEL. It issues GET only - no /doc/NEW, no
POST/PUT/DELETE, nothing that mutates or discards the document. (live_smoke.py
is the opposite: it calls /doc/NEW and will discard unsaved work.)

Reading a table on a model that has none is not an error: a zero-row response
is a normal, documented answer, so "ok" here means "the endpoint exists and
answered", not "the model has data for it".

Run with the dev environment active (``pip install -e ".[dev]"``), e.g.:
    python scripts/live_readonly_sweep.py --product gen --out sweep.json
    python scripts/live_readonly_sweep.py --product gen --resource /db/MATL

To append the results to contracts/verification/ledger.yaml (PLAN.md's A1),
add --record-coverage and cite the build you ran against::

    python scripts/live_readonly_sweep.py --product gen --record-coverage \
        --nx-version "MIDAS Gen NX 2026 (v2.1), build 06/23/2026"

then re-run scripts/gen_roadmap.py. An endpoint the ledger already claims is
skipped rather than re-recorded: an existing claim came from a full write ->
analyze -> read round trip or an earlier sweep, and a GET repeating it is not
new evidence. Nothing already in the ledger is edited.

Exit code 0 -> every endpoint answered.
Exit code 1 -> at least one endpoint failed (see the report).
Exit code 2 -> couldn't connect, or the server rejected the connection.
"""
from __future__ import annotations

import argparse
import importlib
import json
import pathlib
import pkgutil
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

import midas_nx
from midas_nx.client import MidasAPIError, MidasClient, MidasResultError

sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parent.parent
COVERAGE = ROOT / "docs" / "coverage.json"
LEDGER = ROOT / "contracts" / "verification" / "ledger.yaml"
sys.path.insert(0, str(ROOT / "scripts"))

import yaml  # noqa: E402
from verification_ledger import claims  # noqa: E402


def _import_all_submodules() -> None:
    for _, name, _ in pkgutil.walk_packages(midas_nx.__path__, prefix=midas_nx.__name__ + "."):
        importlib.import_module(name)


def _all_resources() -> List[type]:
    """Every concrete DbResource subclass, found by walking every submodule and
    then DbResource's subclass tree - same enumeration scripts/check_drift.py
    uses, since there is no central registry."""
    from midas_nx.db.base import DbResource

    _import_all_submodules()
    seen = set()
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


def _describe(response: Any) -> Dict[str, Any]:
    """Classify a GET response without assuming a shape.

    Zero-row responses have been seen live in two forms - ``{"<KEY>": {}}`` and
    a bare ``{"message": ""}`` - so the shape itself is evidence worth
    recording, not just the row count. When the response is message-shaped,
    the message text itself (capped) is what distinguishes "no data yet" from
    "rejected: perform analysis first" - a distinction the row count/shape
    alone can't make. Server messages seen so far are generic status text,
    not model content, but this is capped and should still be reviewed before
    any of it lands in a public file (docs/coverage.json shipped unsanitized
    production-model detail once before - see CLAUDE.md).
    """
    if not isinstance(response, dict):
        return {"shape": type(response).__name__, "rows": None}
    table = next((v for v in response.values() if isinstance(v, dict)), None)
    if table is None:
        if "message" in response:
            return {"shape": "message", "rows": 0, "message_text": str(response["message"])[:200]}
        return {"shape": "no-table", "rows": 0}
    return {"shape": "keyed", "key": next(iter(response)), "rows": len(table)}


def _record_coverage(results: List[Dict[str, Any]], product: str, nx_version: str) -> None:
    """Append this sweep to contracts/verification/ledger.yaml.

    Only endpoints that answered are recorded, and only those the ledger has
    no claim for yet - an existing claim came from a full round trip or an
    earlier sweep, and neither is improved by a GET repeating it. The record
    is appended and nothing already written is edited: a record is what one
    session saw, which a later session cannot change.
    """
    known = set(claims())
    verified = sorted(
        r["endpoint"] for r in results
        if r["outcome"] == "ok" and r["endpoint"] not in known
    )
    kept = sum(1 for r in results if r["outcome"] == "ok" and r["endpoint"] in known)
    if not verified:
        print(f"ledger: nothing new; {kept} endpoint(s) already claimed")
        return

    date = datetime.now(timezone.utc).date().isoformat()
    record = {
        "id": f"ledger-read-{date}-sweep-{product}",
        "endpoints": verified,
        "date": date,
        "level": "read",
        "products": [product],
        "nxVersions": {product: nx_version},
        "outcome": "success",
        "method": "scripts/live_readonly_sweep.py (read-only GET)",
    }
    text = LEDGER.read_text(encoding="utf-8")
    if f"id: {record['id']}\n" in text:
        raise SystemExit(f"{LEDGER.name} already carries a record id {record['id']}.")
    LEDGER.write_text(
        text.rstrip("\n") + "\n" + yaml.safe_dump(
            [record], allow_unicode=True, sort_keys=False, width=88,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )
    print(f"ledger: +1 record covering {len(verified)} endpoint(s); "
          f"{kept} already claimed")
    print("Re-run scripts/gen_roadmap.py to refresh ROADMAP.md.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", choices=["gen", "civil"], default="gen")
    parser.add_argument("--mapi-key", help="defaults to MIDAS_MAPI_KEY env var")
    parser.add_argument("--base-url", help="defaults to MIDAS_BASE_URL env var")
    parser.add_argument(
        "--resource", help="only sweep resources whose ENDPOINT contains this substring"
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--out", help="path to write the report JSON (optional)")
    parser.add_argument(
        "--record-coverage",
        action="store_true",
        help="append successes to contracts/verification/ledger.yaml",
    )
    parser.add_argument(
        "--nx-version",
        help='build string to cite, e.g. "MIDAS Gen NX 2026 (v2.1), build 06/23/2026"; '
        "required with --record-coverage, since the API does not report it",
    )
    args = parser.parse_args()

    if args.record_coverage and not args.nx_version:
        parser.error("--record-coverage needs --nx-version (read it from Help > About)")

    client = MidasClient(
        mapi_key=args.mapi_key,
        base_url=args.base_url,
        product=args.product,
        timeout=args.timeout,
        strict_product=False,
    )
    try:
        health = client.verify_connection()
    except MidasAPIError as exc:
        print(f"Could not reach the MIDAS NX Open API server: {exc}", file=sys.stderr)
        return 2
    if health.get("status") != "connected":
        print(f"Server reachable but not connected: {health}", file=sys.stderr)
        return 2

    resources = [
        cls
        for cls in _all_resources()
        if "GET" in cls.METHODS and client.product.value in cls.PRODUCTS
    ]
    if args.resource:
        resources = [cls for cls in resources if args.resource in cls.ENDPOINT]

    results: List[Dict[str, Any]] = []
    for cls in resources:
        row: Dict[str, Any] = {
            "endpoint": cls.ENDPOINT,
            "name": cls.NAME,
            "module": cls.__module__,
        }
        try:
            row.update(_describe(cls.get(client=client)), outcome="ok")
        except MidasResultError as exc:
            # HTTP 200 carrying an {"error": ...} body. Distinct from an HTTP
            # error: the endpoint exists and answered, but refused this call.
            row.update(outcome="result_error", error=str(exc))
        except MidasAPIError as exc:
            row.update(
                outcome="error",
                error_class=type(exc).__name__,
                status_code=exc.status_code,
                error=str(exc),
            )
        results.append(row)
        print(f"{row['outcome']:13} {cls.ENDPOINT}")

    counts: Dict[str, int] = {}
    for row in results:
        counts[row["outcome"]] = counts.get(row["outcome"], 0) + 1

    report = {
        "product": client.product.value,
        "swept_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "connection": {k: health.get(k) for k in ("user", "program", "connectionID")},
        "total": len(results),
        "counts": counts,
        "results": results,
    }

    print()
    print(f"Swept {len(results)} GET-capable {client.product.value} resources: {counts}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)
        print(f"Report written to {args.out}")

    if args.record_coverage:
        if args.resource:
            print("Refusing to record a filtered sweep into coverage.json.", file=sys.stderr)
            return 1
        _record_coverage(results, client.product.value, args.nx_version)

    return 0 if counts.get("ok", 0) == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
