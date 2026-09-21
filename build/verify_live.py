#!/usr/bin/env python3
"""Probe every read endpoint in the registry against a live MIDAS instance.

This is the registry's regression test: the URIs and methods come from
documentation, and only a live GET proves they are right.  It is read-only --
only endpoints that advertise GET are touched.

Usage::

    python build/verify_live.py                     # all namespaces
    python build/verify_live.py --namespace db ope  # subset
    python build/verify_live.py --limit 40          # sample

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
OUT = ROOT / "registry" / "live_probe.json"
sys.path.insert(0, str(ROOT / "src"))

from midas_mcp.credentials import MissingCredentials, resolve  # noqa: E402

#: HTTP 404 on this Gen build is expected for Civil-only and Hyper-S endpoints;
#: the probe records them instead of failing the run.
EXPECTED_404 = {
    "IMFM-M1", "IEHG-BEAM-M1", "IEHG-GL-M1", "STRPSSM", "GCMB",
}


def probe(base_url: str, key: str, uri: str, timeout: float = 20.0):
    req = urllib.request.Request(base_url + uri, headers={
        "MAPI-Key": key, "Content-Type": "application/json"})
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(200).decode("utf-8", "replace")
            return resp.status, body, time.time() - started
    except urllib.error.HTTPError as exc:
        body = exc.read(200).decode("utf-8", "replace")
        return exc.code, body, time.time() - started
    except Exception as exc:  # timeouts, connection resets
        return 0, f"{type(exc).__name__}: {exc}", time.time() - started


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--namespace", nargs="*", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default=None, help="single endpoint key")
    ap.add_argument("--config", default=None,
                    help="JSON config file holding the credentials")
    ap.add_argument("--profile", default=None,
                    help="profile inside the config file, e.g. 'MIDAS GEN NX'")
    args = ap.parse_args(argv)

    try:
        base_url, mapi_key = resolve(args.profile, args.config)
    except MissingCredentials as exc:
        print(str(exc), file=sys.stderr)
        return 2
    base_url = base_url.rstrip("/")

    endpoints = json.loads(REGISTRY.read_text(encoding="utf-8"))["endpoints"]
    targets = [(k, v) for k, v in endpoints.items()
               if "GET" in v["methods"]
               and (args.namespace is None or v["namespace"] in args.namespace)
               and (args.only is None or k == args.only)]
    if args.limit:
        targets = targets[: args.limit]

    results: dict[str, dict] = {}
    counts: dict[str, int] = {}
    unexpected: list[str] = []
    for key, entry in targets:
        status, body, seconds = probe(base_url, mapi_key, entry["uri"])
        counts[str(status)] = counts.get(str(status), 0) + 1
        results[key] = {"uri": entry["uri"], "status": status,
                        "ms": round(seconds * 1000), "body_head": body}
        mark = ""
        if status != 200:
            short = key.split(":")[-1]
            if status == 404 and short in EXPECTED_404:
                mark = " (expected on Gen)"
            else:
                unexpected.append(f"{key} {entry['uri']} -> {status} {body[:60]}")
                mark = "  <<< UNEXPECTED"
        print(f"{status:>4} {key:42s} {entry['uri']:46s} {seconds * 1000:6.0f}ms{mark}")

    print(f"\nprobed {len(targets)} GET endpoints on {base_url}")
    print("status histogram:", counts)
    if unexpected:
        print(f"unexpected responses ({len(unexpected)}):")
        for line in unexpected[:40]:
            print("  ", line)
    if not args.limit and args.only is None:
        OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}")
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main())
