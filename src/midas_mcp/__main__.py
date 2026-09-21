"""Entry point for the MIDAS MCP connector.

Run with::

    python -m midas_mcp                             # stdio (default)
    python -m midas_mcp --transport http            # Streamable HTTP on 127.0.0.1
    python -m midas_mcp --profile "MIDAS CIVIL NX"  # pick a product profile
    python -m midas_mcp --list-profiles             # show configured products
    python -m midas_mcp --show-config               # show resolved settings (key redacted)

Credentials come from a JSON config file (see ``config.example.json``), grouped
into per-product profiles.  ``--config`` overrides the auto-discovered path and
``--profile`` overrides ``active_profile``; environment variables override both.
The key is never accepted on the command line.
"""
from __future__ import annotations

import argparse
import logging
import sys

from .config import describe_config, list_profiles, load_config, redact
from .mcp_server import McpServer
from .registry import Registry
from .stdio_transport import StdioTransport


def _print_profiles(args) -> int:
    try:
        rows, meta = list_profiles(args.config)
    except (ValueError, RuntimeError) as exc:
        print(redact(str(exc)), file=sys.stderr)
        return 2
    where = meta["path"] or "(no config file found)"
    print(f"config file: {where} [{meta['source']}]")
    if not rows:
        print("  (no profiles defined)")
        return 0
    width = max((len(str(r["name"])) for r in rows), default=4)
    for row in rows:
        mark = "*" if row["active"] else " "
        name = str(row["name"]) if row["name"] else "(flat config)"
        key = "key set" if row["has_key"] else "NO KEY"
        print(f" {mark} {name.ljust(width)}  {str(row['base_url'] or '-'):<40} {key}")
    print("\n* = active profile; select with --profile \"<name>\" or MIDAS_MCP_PROFILE")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="midas_mcp", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    ap.add_argument("--port", type=int, default=8100)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--config", type=str, default=None,
                    help="path to config.json (default: auto-discovered)")
    ap.add_argument("--profile", type=str, default=None,
                    help='product profile to use, e.g. "MIDAS GEN NX"')
    ap.add_argument("--list-profiles", action="store_true",
                    help="list configured profiles (never prints keys) and exit")
    ap.add_argument("--show-config", action="store_true",
                    help="print the resolved configuration (key redacted) and exit")
    args = ap.parse_args(argv)

    if args.list_profiles:
        return _print_profiles(args)

    cli = []
    if args.config:
        cli += ["--config", args.config]
    if args.profile:
        cli += ["--profile", args.profile]

    try:
        cfg = load_config(cli or None)
    except (RuntimeError, ValueError) as exc:
        print(redact(str(exc)), file=sys.stderr)
        return 2

    if args.show_config:
        print(describe_config(cfg))
        return 0

    logging.basicConfig(
        stream=sys.stderr,
        level=getattr(logging, cfg.log_level.upper(), logging.WARNING),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger(__name__).info(
        "using profile %s -> %s", cfg.profile or "(flat)", cfg.base_url)

    registry = Registry.load(cfg.registry_dir)
    server = McpServer(cfg, registry)

    if args.transport == "http":
        from .http_transport import run_http
        return run_http(server, cfg, host=args.host, port=args.port)

    transport = StdioTransport(server.handle)
    try:
        return transport.run()
    finally:
        server.shutdown()


if __name__ == "__main__":
    sys.exit(main())
