"""MCP server: the JSON-RPC method surface.

Implements the tools-only subset of the MCP protocol:
initialize, notifications/initialized, ping, tools/list, tools/call,
resources/list, resources/read, notifications/cancelled, logging/setLevel.

Two error shapes are kept strictly separate (mcp/01_PROTOCOL.md & 9):
- protocol errors -> JSON-RPC ``error``
- MIDAS/guard failures -> ``result.isError`` (built by the tool handlers)

Long-running tool calls run on a worker thread so ``ping``/``cancelled`` remain
responsive while an analysis is in flight.
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from . import knowledge
from .config import Config, Secret
from .dispatch import build_tools, tool_db_assign, tool_db_delete, tool_db_query, tool_doc
from .errors import RpcError, ToolError
from .jsonrpc import ok
from .registry import Registry

log = logging.getLogger("midas_mcp.server")

SUPPORTED_VERSIONS = ("2026-07-28", "2025-06-18", "2025-03-26", "2024-11-05")
NEWEST = SUPPORTED_VERSIONS[0]

TOOL_DISPATCH = {
    "midas_doc": tool_doc,
    "midas_db_query": tool_db_query,
    "midas_db_assign": tool_db_assign,
    "midas_db_delete": tool_db_delete,
}

_RESOURCE_NAMES = {
    "midas://knowledge/pitfalls": ("text/markdown", knowledge.pitfalls_markdown),
    "midas://knowledge/routing": ("text/markdown", knowledge.routing_markdown),
    "midas://registry/index": ("text/markdown", None),  # built at request time
    "midas://recipes/modal-rs": ("text/markdown", lambda: knowledge.recipe_markdown("modal-rs")),
    "midas://recipes/steel-frame": ("text/markdown", lambda: knowledge.recipe_markdown("steel-frame")),
    "midas://recipes/rc-section": ("text/markdown", lambda: knowledge.recipe_markdown("rc-section")),
    "midas://recipes/load-balance": ("text/markdown", lambda: knowledge.recipe_markdown("load-balance")),
}


class RequestContext:
    def __init__(self, request_id):
        self.request_id = request_id
        self.cancel = threading.Event()


class McpServer:
    def __init__(self, cfg: Config, registry: Registry, deps=None):
        self.cfg = cfg
        self.registry = registry
        self.executor = ThreadPoolExecutor(max_workers=cfg.max_workers)
        self._ctx: dict[Any, RequestContext] = {}
        self._tools = build_tools()
        self._deps = deps or (lambda: (None, None, registry))

    # -- request entry ----------------------------------------------------
    def handle(self, msg: dict):
        method = msg.get("method")
        msg_id = msg.get("id")
        is_request = "id" in msg

        if method == "initialize":
            return ok(msg_id, self._initialize(msg.get("params", {})))
        if method == "notifications/initialized":
            return None
        if method == "ping":
            return ok(msg_id, {})
        if method == "tools/list":
            return ok(msg_id, self._tools_list())
        if method == "tools/call":
            return self._handle_call(msg_id, msg.get("params", {}))
        if method == "resources/list":
            return ok(msg_id, self._resources_list())
        if method == "resources/read":
            return ok(msg_id, self._resources_read(msg.get("params", {})))
        if method == "notifications/cancelled":
            params = msg.get("params", {})
            req_id = params.get("requestId")
            if req_id in self._ctx:
                self._ctx[req_id].cancel.set()
            return None
        if method == "logging/setLevel":
            return ok(msg_id, {})

        # method not found: only an error for requests, silent for notifications
        if is_request:
            raise RpcError("METHOD_NOT_FOUND", f"method not found: {method!r}")
        return None

    # -- capabilities -----------------------------------------------------
    def _initialize(self, params: dict) -> dict:
        requested = params.get("protocolVersion", "")
        version = requested if requested in SUPPORTED_VERSIONS else NEWEST
        instructions = (
            knowledge.routing_markdown()
            + "Guard rails in force: the crash guard refuses to assign a "
            "boundary/load record to a missing node/element id (that crashes "
            "MIDAS). EIGV.Type is forced to LANCZOS. Deleting requires explicit "
            "target_ids."
        )
        return {
            "protocolVersion": version,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
            },
            "serverInfo": {"name": "midas-mcp", "version": "1.0.0"},
            "instructions": instructions,
        }

    def _tools_list(self) -> dict:
        return {"tools": self._tools}

    def _resources_list(self) -> dict:
        resources = [
            {"uri": uri, "name": uri.rsplit("/", 1)[-1], "mimeType": mt,
             "description": ""} for uri, (mt, _) in _RESOURCE_NAMES.items()
        ]
        return {"resources": resources}

    def _resources_read(self, params: dict) -> dict:
        uri = params.get("uri")
        if uri not in _RESOURCE_NAMES:
            raise RpcError("RESOURCE_NOT_FOUND", f"resource not found: {uri!r}")
        mt, builder = _RESOURCE_NAMES[uri]
        if builder is None:
            content = self._registry_index_markdown()
        else:
            content = builder()
        return {"contents": [{"uri": uri, "mimeType": mt, "text": content}]}

    def _registry_index_markdown(self) -> str:
        lines = ["# MIDAS registry index\n"]
        for ns, keys in self.registry.families().items():
            lines.append(f"## {ns}\n")
            lines.append("`" + "`, `".join(keys) + "`\n")
        return "\n".join(lines)

    # -- tools/call -------------------------------------------------------
    def _handle_call(self, msg_id, params: dict):
        name = params.get("name")
        if name not in TOOL_DISPATCH:
            raise RpcError("INVALID_PARAMS", f"unknown tool {name!r}")
        arguments = params.get("arguments")
        if not isinstance(arguments, dict):
            raise RpcError("INVALID_PARAMS", "tool arguments must be an object")
        ctx = RequestContext(msg_id)
        self._ctx[msg_id] = ctx

        try:
            func = TOOL_DISPATCH[name]
            result = func(arguments, self._deps_conf)
        except ToolError as exc:
            result = {"ok": False, "category": exc.category,
                      "message": str(exc), "endpoint": exc.endpoint,
                      "http_status": exc.http_status}
            if exc.data is not None:
                result["data"] = exc.data
        except RpcError:
            raise
        except Exception as exc:  # defensive: never crash the process
            log.exception("tool %s raised", name)
            result = {"ok": False, "category": "INTERNAL",
                      "message": f"internal error: {type(exc).__name__}: {exc}"}
        finally:
            self._ctx.pop(msg_id, None)

        return ok(msg_id, {"content": [{"type": "text",
                                        "text": _text_of(result)}],
                           "structuredContent": result,
                           "isError": result.get("ok") is not True})

    def _deps_conf(self):
        # guards/client are cheap to construct; registry is shared
        from .guards import Guards
        from .midas_http import MidasClient
        guards = Guards(self.registry, self.cfg)
        client = MidasClient(self.cfg)
        return guards, client, self.registry

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)


def _text_of(result: dict) -> str:
    """Render a result envelope as human/LLM text."""
    import json
    if result.get("ok") is True:
        lines = [f"ok: {result.get('endpoint', '')} ({result.get('method', '')} "
                 f"{result.get('status', '')})"]
        body = result.get("data")
        try:
            lines.append(json.dumps(body, ensure_ascii=False, indent=1)
                         [:4000])
        except (TypeError, ValueError):
            lines.append(str(body)[:4000])
        for key in ("hints", "note", "hint"):
            if result.get(key):
                lines.append(f"[{key}] {result[key]}")
        return "\n".join(lines)
    lines = [f"error: {result.get('category', '')} - {result.get('message', '')}"]
    if result.get("http_status"):
        lines.append(f"http_status: {result['http_status']}")
    return "\n".join(lines)