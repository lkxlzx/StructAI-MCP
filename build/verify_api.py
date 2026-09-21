#!/usr/bin/env python3
"""Cross-check the registry against the live MIDAS API.

For every registered endpoint this probes:

* **methods** - which HTTP verbs the server actually accepts, versus what the
  documentation claims.  A verb that is not implemented answers ``405``; a verb
  that is implemented evaluates the body and answers ``400`` (bad fields) or
  ``2xx``.  Probes are deliberately no-ops: empty ``Assign``/``Argument``
  bodies, and DELETE against an id that does not exist.
* **schema** - ``GET /info/db/<NAME>`` returns the server's own JSON Schema for
  a DB endpoint.  Comparing its field names against the manual catches
  documented-but-wrong field names (the CNLD ``CMD/FV`` vs ``FX/FY/FZ`` class).
* **error shape** - whether a rejection arrives as a 4xx (honest) or as a
  ``2xx`` carrying an error message (the "silent failure" class).

Output: ``registry/api_verify.json`` (raw) plus a printed summary of every
discrepancy.  Nothing here mutates the model beyond no-op probes.

Usage::

    python build/verify_api.py --namespace db ope view
    python build/verify_api.py --limit 40
    python build/verify_api.py --probe-delete      # also probe DELETE verbs

Credentials come from the JSON config file (see config.example.json) or from
``MIDAS_BASE_URL`` / ``MIDAS_MAPI_KEY``; the environment wins when both are set.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "registry" / "registry.json"
OUT = ROOT / "registry" / "api_verify.json"
sys.path.insert(0, str(ROOT / "src"))

from midas_mcp.credentials import MissingCredentials, resolve  # noqa: E402

#: A node/element id that will not exist, used for harmless DELETE probes.
PROBE_ID = "9999999"

METHODS = ("GET", "POST", "PUT", "DELETE")


def request(base: str, key: str, method: str, path: str,
            body: dict | None = None, timeout: float = 15.0, max_bytes: int = 400):
    """One HTTP call.  ``max_bytes`` bounds the read: small for probe bodies,
    large for schema fetches -- a truncated read silently breaks json.loads and
    was hiding most schemas from an earlier sweep."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"MAPI-Key": key,
                                          "Content-Type": "application/json"})
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(max_bytes).decode("utf-8", "replace"), time.time() - started
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(600).decode("utf-8", "replace"), time.time() - started
    except Exception as exc:
        return 0, f"{type(exc).__name__}: {exc}", time.time() - started


def classify(status: int, body: str) -> str:
    """Reduce a probe response to how the verb is treated by the server.

    Probes target the *collection* URI with an empty body, so a 404 means the
    route itself is not served by this build rather than "the verb is wrong".
    """
    if status == 0:
        return "unreachable"
    if status == 404:
        return "endpoint_absent"
    if status == 405:
        return "method_not_allowed"
    if 200 <= status < 300:
        # a 2xx may still carry a rejection message (the silent-failure class)
        if '"error"' in body or "is wrong" in body or "Wrong Field" in body:
            return "accepted_but_errored"
        return "accepted"
    if status in (400, 500):
        return "supported_rejected"  # the verb exists, the payload did not fit
    return f"http_{status}"


def probe_methods(base: str, key: str, uri: str, methods: list[str],
                  probe_delete: bool) -> dict:
    out: dict = {}
    messages: dict = {}
    for method in METHODS:
        if method not in methods and method != "GET":
            # only probe verbs the docs mention; unlisted verbs are noise
            if method == "DELETE" and not probe_delete:
                continue
            if method in ("POST", "PUT") and method not in methods:
                continue
        if method == "DELETE":
            if not probe_delete:
                out[method] = "skipped"
                continue
            status, resp_body, _ = request(base, key, method, f"{uri}/{PROBE_ID}")
        elif method == "GET":
            status, resp_body, _ = request(base, key, method, uri)
        else:
            wrapper = "Assign" if uri.startswith("/db/") or uri.startswith("/DESIGN/") \
                else "Argument"
            status, resp_body, _ = request(base, key, method, uri, {wrapper: {}})
        out[method] = classify(status, resp_body)
        if out[method] == "accepted_but_errored":
            messages[method] = resp_body.strip().replace("\n", " ")[:140]
    if messages:
        out["_messages"] = messages
    return out


def probe_schema(base: str, key: str, uri: str) -> dict | None:
    """Fetch the server's own schema for a DB endpoint.

    ``/info/db/<NAME>`` answers 200 for every db endpoint the build serves and
    404 for the ones it does not, so this doubles as a "is it served" signal.
    """
    name = uri.rsplit("/", 1)[-1]
    status, body, _ = request(base, key, "GET", f"/info/db/{name}", max_bytes=1_000_000)
    if status != 200:
        return None
    try:
        parsed = json.loads(body)
    except ValueError:
        return None
    # the schema nests under "Argument" (or, for a few endpoints, "Assign")
    for wrapper in ("Argument", "Assign"):
        props = parsed.get(wrapper, {}).get("properties")
        if isinstance(props, dict):
            return {"fields": sorted(props.keys()), "wrapper": wrapper}
    nested = parsed.get("Argument")
    if isinstance(nested, dict):
        return {"fields": sorted(nested.keys()), "wrapper": "Argument"}
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--namespace", nargs="*", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default=None)
    ap.add_argument("--probe-delete", action="store_true",
                    help="probe DELETE verbs too (uses a nonexistent id)")
    ap.add_argument("--schemas", action="store_true",
                    help="also fetch /info/db schemas for db endpoints")
    ap.add_argument("--config", default=None,
                    help="JSON config file holding the credentials")
    ap.add_argument("--profile", default=None,
                    help="profile inside the config file, e.g. 'MIDAS GEN NX'")
    args = ap.parse_args(argv)

    try:
        base, key = resolve(args.profile, args.config)
    except MissingCredentials as exc:
        print(str(exc), file=sys.stderr)
        return 2
    base = base.rstrip("/")

    endpoints = json.loads(REGISTRY.read_text(encoding="utf-8"))["endpoints"]
    targets = [(k, v) for k, v in endpoints.items()
               if (args.namespace is None or v["namespace"] in args.namespace)
               and (args.only is None or k == args.only)]
    if args.limit:
        targets = targets[: args.limit]

    # Merge with any previous run so a sweep over a subset of namespaces does
    # not drop the findings for the rest (the registry build reads this file).
    previous: dict = {}
    if OUT.exists():
        try:
            previous = json.loads(OUT.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            previous = {}
    report: dict = {"base_url": base,
                    "endpoints": dict(previous.get("endpoints", {})),
                    "method_mismatch": list(previous.get("method_mismatch", [])),
                    "silent_failures": list(previous.get("silent_failures", [])),
                    "schemas": dict(previous.get("schemas", {})),
                    "absent": list(previous.get("absent", []))}
    # drop stale results for the endpoints about to be re-probed
    for k in (k for k in report["endpoints"] if k in {t[0] for t in targets}):
        report["endpoints"].pop(k, None)
        report["schemas"].pop(k, None)
    report["absent"] = [a for a in report["absent"] if a not in {t[0] for t in targets}]
    report["method_mismatch"] = [m for m in report["method_mismatch"]
                                 if m["key"] not in {t[0] for t in targets}]
    report["silent_failures"] = [m for m in report["silent_failures"]
                                 if m["key"] not in {t[0] for t in targets}]
    for i, (k, v) in enumerate(targets, 1):
        observed = probe_methods(base, key, v["uri"], v["methods"], args.probe_delete)
        documented = list(v["methods"])
        supported = [m for m, r in observed.items()
                     if not m.startswith("_")
                     and r in ("accepted", "supported_rejected", "accepted_but_errored")]
        missing = [m for m in supported if m not in documented]
        absent = [m for m in documented if observed.get(m) == "method_not_allowed"]
        entry = {"uri": v["uri"], "documented": documented,
                 "observed": observed, "supported": supported}
        if not supported and observed.get("GET") == "endpoint_absent":
            entry["present"] = False
            report["absent"].append(k)
        else:
            entry["present"] = True
        if missing or absent:
            entry["mismatch"] = {"documented_but_405": absent,
                                 "live_but_undocumented": missing}
            report["method_mismatch"].append({"key": k, **entry["mismatch"]})
        if any(r == "accepted_but_errored" for r in observed.values()):
            report["silent_failures"].append({"key": k, "observed": observed})
        if args.schemas and v["namespace"] in ("db", "design"):
            schema = probe_schema(base, key, v["uri"])
            if schema:
                entry["schema"] = schema
                report["schemas"][k] = schema
        report["endpoints"][k] = entry
        if i % 25 == 0:
            print(f"  ...{i}/{len(targets)}")

    print(f"\nprobed {len(targets)} endpoints on {base}")
    print(f"absent on this build   : {len(report['absent'])}")
    print(f"method mismatches      : {len(report['method_mismatch'])}")
    for m in report["method_mismatch"][:30]:
        print(f"   {m['key']:42s} 405 for {m['documented_but_405']} | "
              f"undocumented {m['live_but_undocumented']}")
    print(f"silent-failure endpoints: {len(report['silent_failures'])}")
    if args.schemas:
        print(f"schemas fetched        : {len(report['schemas'])}")

    if not args.limit and args.only is None:
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
