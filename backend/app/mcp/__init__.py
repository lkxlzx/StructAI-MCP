"""MCP layer — v1.2 §37 (protocol endpoint) and V2.1 §6–§11 (the four tools).

Layout::

    capabilities.py   the static capability table = the routing heart (§16.1/§17)
    capability.py     CapabilityResolver (§16)
    context.py        DispatchContext + the shared request builders
    dispatcher.py     the v1.2 §38 flow, and the 总纲 §4.3.2 MCP envelope
    tools/            one module per tool (query / model / execute / task)
    server.py         the MCP server (stdio + streamable HTTP at /mcp)

Attributes are resolved lazily (PEP 562) so ``import app.mcp`` stays cheap and
cannot take part in an import cycle: the dispatcher imports the tools, and the
tools import this package's submodules.
"""

from typing import Any

__all__ = [
    "capabilities",
    "capability",
    "context",
    "dispatcher",
    "server",
    "tools",
    "Capability",
    "CapabilityResolver",
    "DispatchContext",
    "ToolDispatcher",
    "build_envelope",
    "build_server",
    "capability_table",
    "resolve",
    "resources_for",
    "actions_for",
    "TOOL_NAMES",
]

_LAZY: dict[str, tuple[str, str | None]] = {
    "capabilities": ("app.mcp.capabilities", None),
    "capability": ("app.mcp.capability", None),
    "context": ("app.mcp.context", None),
    "dispatcher": ("app.mcp.dispatcher", None),
    "server": ("app.mcp.server", None),
    "tools": ("app.mcp.tools", None),
    "Capability": ("app.mcp.capabilities", "Capability"),
    "capability_table": ("app.mcp.capabilities", "capability_table"),
    "resolve": ("app.mcp.capabilities", "resolve"),
    "resources_for": ("app.mcp.capabilities", "resources_for"),
    "actions_for": ("app.mcp.capabilities", "actions_for"),
    "TOOL_NAMES": ("app.mcp.capabilities", "TOOL_NAMES"),
    "CapabilityResolver": ("app.mcp.capability", "CapabilityResolver"),
    "DispatchContext": ("app.mcp.context", "DispatchContext"),
    "ToolDispatcher": ("app.mcp.dispatcher", "ToolDispatcher"),
    "build_envelope": ("app.mcp.dispatcher", "build_envelope"),
    "build_server": ("app.mcp.server", "build_server"),
}


def __getattr__(name: str) -> Any:
    """Resolve a public name on first use (PEP 562)."""
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    module = __import__(module_name, fromlist=["_"])
    value = module if attribute is None else getattr(module, attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
