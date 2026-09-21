#!/usr/bin/env python3
"""Probe how MIDAS reports rejections, to test the 2xx-error-body classifier.

The connector judges success from the body, not the status code, because MIDAS
answers some rejections with HTTP 2xx.  That classification used to rest on a
hand-written message whitelist.  This script deliberately sends malformed
payloads across many endpoints and collects every distinct body so the
classifier can be checked against real evidence instead of guesswork.

For each DB endpoint it sends, under a high record id reserved for fuzzing:

* a bogus field name            -> the field validator must reject it
* a wrong-typed known field     -> the type validator must reject it

Every response is recorded with its status, and the script reports any body the
current classifier would call a *success* that actually carries a rejection
message.  Fuzz records are deleted afterwards.

Usage::

    python build/fuzz_error_shapes.py --limit 80
    python build/fuzz_error_shapes.py --namespace ope view

Credentials come from the JSON config file (see config.example.json) or from
``MIDAS_BASE_URL`` / ``MIDAS_MAPI_KEY``; the environment wins when both are set.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from midas_mcp.credentials import MissingCredentials, resolve  # noqa: E402

REGISTRY = ROOT / "registry" / "registry.json"
OUT = ROOT / "registry" / "error_shapes.json"

FUZZ_ID = "995001"          # reserved record id for fuzzing; deleted afterwards
BOGUS_FIELD = "__MCP_BOGUS__"


def request(base: str, key: str, method: str, path: str, body: dict | None = None,
            timeout: float = 15.0):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"MAPI-Key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(2000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(2000).decode("utf-8", "replace")
    except Exception as exc:
        return 0, f"{type(exc).__name__}: {exc}"


def wrapper_for(entry: dict) -> str:
    return "Assign" if entry["wrapper"].upper() == "ASSIGN" else "Argument"


def message_of(body: str) -> str | None:
    try:
        parsed = json.loads(body)
    except ValueError:
        return None
    if not isinstance(parsed, dict):
        return None
    if isinstance(parsed.get("error"), dict):
        return str(parsed["error"].get("message", ""))
    if isinstance(parsed.get("error"), str):
        return parsed["error"]
    msg = parsed.get("message")
    return msg if isinstance(msg, str) and msg.strip() else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--namespace", nargs="*", default=["db"])
    ap.add_argument("--limit", type=int, default=80)
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

    from midas_mcp.normalize import is_error_body  # the classifier under test

    endpoints = json.loads(REGISTRY.read_text(encoding="utf-8"))["endpoints"]
    targets = [(k, v) for k, v in endpoints.items()
               if v["namespace"] in args.namespace and "POST" in v["methods"]]
    targets = targets[: args.limit]

    observed: dict[str, dict] = {}
    misses: list[dict] = []
    for k, v in targets:
        wrapper = wrapper_for(v)
        for label, payload in (
            ("bogus_field", {wrapper: {FUZZ_ID: {BOGUS_FIELD: 1}}}),
            ("wrong_type", {wrapper: {FUZZ_ID: {"NAME": {"nested": "object"}}}}),
        ):
            status, body = request(base, key, "POST", v["uri"], payload)
            msg = message_of(body)
            key_id = f"{k}|{label}"
            observed[key_id] = {"uri": v["uri"], "status": status, "message": msg,
                                "body": body[:200]}
            if 200 <= status < 300 and msg and not is_error_body(status, body):
                # the classifier called a rejection a success
                misses.append({"endpoint": k, "label": label, "status": status,
                               "message": msg, "body": body[:200]})
        # fuzz may have created a record; remove it
        request(base, key, "DELETE", f"{v['uri']}/{FUZZ_ID}")

    distinct = sorted({o["message"] for o in observed.values() if o["message"]})
    print(f"probed {len(targets)} endpoints x2 payloads")
    print(f"distinct rejection messages: {len(distinct)}")
    for m in distinct:
        print(f"   {m[:100]!r}")
    print(f"\nclassified-as-success-but-rejected: {len(misses)}")
    for m in misses[:25]:
        print(f"   {m['endpoint']:24s} {m['label']:12s} {m['status']} {m['message'][:80]!r}")

    OUT.write_text(json.dumps({"observed": observed, "misses": misses},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 1 if misses else 0


if __name__ == "__main__":
    sys.exit(main())
