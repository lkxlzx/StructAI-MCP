"""The four MCP tools — v1.2 §37 / V2.1 §7–§10.

Each module owns one tool and exposes the same four names:

``TOOL_NAME``
    the tool name published over MCP (v1.2 §37 fixes the list).
``SCHEMA``
    the JSON Schema, **generated** from :mod:`app.mcp.capabilities` (V2.1 §6.1 /
    总纲 §0.4) — never hand-written, so the enums cannot drift from the router.
    ``build_schema()`` rebuilds it, which is what lets a test prove the enums
    track the table.
``handle(arguments, context)``
    the async entry point: validated arguments plus the dispatcher context.
``build_schema``
    the generator behind ``SCHEMA``.

:data:`TOOL_SCHEMAS` and :data:`TOOL_HANDLERS` are the dispatcher's routing
tables.  Nothing here imports :mod:`app.mcp.dispatcher` (the dispatcher imports
this package), so the dependency graph stays acyclic.
"""

from typing import Any, Awaitable, Callable, Final, Mapping

from app.mcp.context import DispatchContext
from app.mcp.tools import query, model, execute, task

__all__ = [
    "execute",
    "model",
    "query",
    "task",
    "TOOL_MODULES",
    "TOOL_SCHEMAS",
    "TOOL_HANDLERS",
    "ToolHandler",
    "get_tool",
    "schema_of",
]

#: Declaration order == v1.2 §37's exposure order.
TOOL_MODULES: Final[tuple[Any, ...]] = (query, model, execute, task)

ToolHandler = Callable[[Mapping[str, Any], DispatchContext], Awaitable[Any]]

TOOL_SCHEMAS: Final[dict[str, dict[str, Any]]] = {
    module.TOOL_NAME: module.SCHEMA for module in TOOL_MODULES
}

TOOL_HANDLERS: Final[dict[str, ToolHandler]] = {
    module.TOOL_NAME: module.handle for module in TOOL_MODULES
}


def get_tool(name: str) -> Any | None:
    """The tool module for ``name``, or ``None``."""
    for module in TOOL_MODULES:
        if module.TOOL_NAME == name:
            return module
    return None


def schema_of(name: str) -> dict[str, Any]:
    """The **current** schema for ``name`` (rebuilds from the capability table)."""
    module = get_tool(name)
    if module is None:
        raise KeyError(name)
    return module.build_schema()
