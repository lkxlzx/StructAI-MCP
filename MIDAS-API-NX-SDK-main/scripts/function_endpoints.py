"""Discover the plain-function endpoint surfaces exposed by both SDKs.

This module deliberately describes *SDK parity*, not API facts.  Endpoint
contracts still take their fields, products, and behaviour from the manual and
live evidence.  Here, the SDK source is only the subject being checked: a
contracted plain function must be reachable with the contracted HTTP method in
both packages.

``/db/*`` routes have ``DbResource`` metadata.  The remaining routes are
top-level functions wrapped in ``Argument`` and do not have one resource class
per endpoint.  Discovering those calls keeps contract promotion and parity
checking generic instead of maintaining a second, hand-written endpoint list.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON_ROOT = ROOT / "src" / "midas_nx"
TYPESCRIPT_ROOT = ROOT / "packages" / "typescript" / "src"
TYPESCRIPT_RESOURCES = ROOT / "schema" / "typescript-resources.json"


@dataclass(frozen=True)
class FunctionSurface:
    """Methods and named SDK entries which reach one endpoint."""

    methods: frozenset[str]
    entries: tuple[str, ...]
    products: frozenset[str] | None = None


@dataclass(frozen=True)
class FunctionEndpoint:
    """The independently discovered Python and npm surfaces for one route."""

    python: FunctionSurface | None
    typescript: FunctionSurface | None


@dataclass(frozen=True)
class ResourceSurface:
    """Resource metadata exposed by one SDK, used only for parity."""

    methods: frozenset[str]
    products: frozenset[str]
    entries: tuple[str, ...]


@dataclass(frozen=True)
class ResourceEndpoint:
    """The independently discovered resource surfaces for one route."""

    python: ResourceSurface | None
    typescript: ResourceSurface | None


def _constant_evaluator(tree: ast.Module):
    """Resolve the string constants used to compose endpoint paths.

    Design modules keep their route family in module constants and use f-strings
    such as ``f"{_BASE}/CMFT"``.  Only deterministic string expressions are
    resolved; anything dynamic is intentionally ignored rather than guessed.
    """

    constants: dict[str, str] = {}

    def evaluate(node: ast.expr) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return constants.get(node.id)
        if isinstance(node, ast.JoinedStr):
            parts: list[str] = []
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    parts.append(value.value)
                elif isinstance(value, ast.FormattedValue):
                    resolved = evaluate(value.value)
                    if resolved is None:
                        return None
                    parts.append(resolved)
                else:
                    return None
            return "".join(parts)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = evaluate(node.left), evaluate(node.right)
            return left + right if left is not None and right is not None else None
        return None

    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if node.value is None:
            continue
        value = evaluate(node.value)
        if value is None:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                constants[target.id] = value
    return evaluate


def _called_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _module_name(path: Path, python_root: Path) -> str:
    relative = path.relative_to(python_root).with_suffix("")
    parts = ("midas_nx", *relative.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def python_function_surfaces(python_root: Path = PYTHON_ROOT) -> dict[str, FunctionSurface]:
    """Return the top-level plain-function routes exposed by the Python SDK."""

    discovered: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for path in sorted(python_root.rglob("*.py")):
        if path.name == "client.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        evaluate = _constant_evaluator(tree)
        module = _module_name(path, python_root)

        def routes_in(function: ast.AST) -> set[tuple[str, str]]:
            """(method, endpoint) pairs this function body issues directly."""
            found: set[tuple[str, str]] = set()
            for call in ast.walk(function):
                if not isinstance(call, ast.Call):
                    continue
                called = _called_name(call.func)
                endpoint_node: ast.expr | None = None
                method: str | None = None
                if called in {"_get", "get_result"} and call.args:
                    method, endpoint_node = "GET", call.args[0]
                elif called in {"_post", "post_argument"} and call.args:
                    method, endpoint_node = "POST", call.args[0]
                elif called == "request" and len(call.args) >= 2:
                    request_method = evaluate(call.args[0])
                    if request_method in {"GET", "POST"}:
                        method, endpoint_node = request_method, call.args[1]
                if method is None or endpoint_node is None:
                    continue
                endpoint = evaluate(endpoint_node)
                if not isinstance(endpoint, str) or not endpoint.startswith("/"):
                    continue
                found.add((method, endpoint))
            return found

        def calls_in(function: ast.AST) -> set[str]:
            return {
                name
                for call in ast.walk(function)
                if isinstance(call, ast.Call)
                and (name := _called_name(call.func)) is not None
                and name.startswith("_")
            }

        # A public function does not always issue its own request. Where one
        # endpoint serves several documented tables, the SDKs put the literal in
        # a module-private helper and give each table a thin wrapper -
        # `get_column_design_forces_table` calls `_get_rc_design_forces_table`,
        # which is where the `_post` is. Reading only the public body missed
        # `/DESIGN/RC/KDS-41-20-2022/TABLE` and `/DESIGN/SRC/AIK-SRC2K/TABLE`
        # entirely, and a contract for either was refused for having no parity
        # surface while both SDKs had shipped one for months. Resolve the
        # private helpers to a fixpoint first, then let a public caller inherit
        # what its helpers reach.
        helpers: dict[str, ast.AST] = {
            node.name: node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("_")
        }
        helper_routes = {name: routes_in(node) for name, node in helpers.items()}
        for _ in range(len(helpers)):
            widened = False
            for name, node in helpers.items():
                reached = set(helper_routes[name])
                for callee in calls_in(node) & helpers.keys():
                    if callee != name:
                        reached |= helper_routes[callee]
                if reached != helper_routes[name]:
                    helper_routes[name] = reached
                    widened = True
            if not widened:
                break

        for function in tree.body:
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)) or function.name.startswith("_"):
                continue
            entry = f"{module}.{function.name}"
            routes = set(routes_in(function))
            for callee in calls_in(function) & helpers.keys():
                routes |= helper_routes[callee]
            for method, endpoint in routes:
                discovered[endpoint][method].add(entry)

    return {
        endpoint: FunctionSurface(
            methods=frozenset(methods),
            entries=tuple(sorted({entry for entries in methods.values() for entry in entries})),
        )
        for endpoint, methods in discovered.items()
    }


_GENERATED_OPERATION = re.compile(
    r'define(?:Get|Post|EmptyPost)Operation(?:<[^>]+>)?\('
    r'\{"endpoint":"(?P<endpoint>/[^"]+)","method":"(?P<method>GET|POST)",'
    r'"products":(?P<products>\[[^]]*\])\}',
)
_DIRECT_POST = re.compile(r'\bpost\(\s*"(?P<endpoint>/[^"]+)"')
_TABLE_POST = re.compile(r'\bgetTableAt\(\s*"(?P<endpoint>/[^"]+)"')
# The npm counterpart of the Python private-helper case above: `design-tables.ts`
# passes the endpoint literal to a local `defineDesignTable` factory, which is
# what calls `getTableAt`. Neither pattern above sees the literal there.
_DESIGN_TABLE = re.compile(r'\bdefineDesignTable\(\s*"(?P<endpoint>/[^"]+)"')


def typescript_function_surfaces(typescript_root: Path = TYPESCRIPT_ROOT) -> dict[str, FunctionSurface]:
    """Return plain-function routes exposed by npm.

    Generated operation metadata covers the ``ope``, ``view`` and ``DESIGN``
    namespaces.  ``doc.ts`` and ``post.ts`` pre-date that metadata, so their
    literal helper calls are read by the same generic endpoint/method collector.
    This consumes only SDK surface metadata; it never feeds contract content.
    """

    discovered: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    products: dict[str, set[str]] = defaultdict(set)

    generated = typescript_root / "generated" / "operations.ts"
    if generated.exists():
        text = generated.read_text(encoding="utf-8")
        for match in _GENERATED_OPERATION.finditer(text):
            endpoint = match["endpoint"]
            discovered[endpoint][match["method"]].add("generated.operations")
            products[endpoint].update(json.loads(match["products"]))

    for filename, pattern, entry in (
        ("doc.ts", _DIRECT_POST, "doc"),
        ("post.ts", _TABLE_POST, "post"),
        ("design-tables.ts", _DESIGN_TABLE, "designTables"),
    ):
        path = typescript_root / filename
        if not path.exists():
            continue
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            discovered[match["endpoint"]]["POST"].add(entry)

    return {
        endpoint: FunctionSurface(
            methods=frozenset(methods),
            entries=tuple(sorted({entry for entries in methods.values() for entry in entries})),
            products=frozenset(products[endpoint]) if endpoint in products else None,
        )
        for endpoint, methods in discovered.items()
    }


def function_endpoints(
    python_root: Path = PYTHON_ROOT,
    typescript_root: Path = TYPESCRIPT_ROOT,
) -> dict[str, FunctionEndpoint]:
    """Map every discovered plain-function endpoint to both SDK surfaces."""

    python = python_function_surfaces(python_root)
    typescript = typescript_function_surfaces(typescript_root)
    return {
        endpoint: FunctionEndpoint(python.get(endpoint), typescript.get(endpoint))
        for endpoint in sorted(python.keys() | typescript.keys())
    }


def python_resource_endpoints(python_root: Path = PYTHON_ROOT) -> dict[str, ResourceSurface]:
    """Discover Python ``DbResource`` metadata without using it as contract input."""

    source_root = python_root.parent
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))

    import importlib
    import pkgutil

    import midas_nx
    from midas_nx.db.base import DbResource

    for module in pkgutil.walk_packages(midas_nx.__path__, "midas_nx."):
        importlib.import_module(module.name)

    found: dict[str, ResourceSurface] = {}

    def walk(base: type) -> None:
        for child in base.__subclasses__():
            endpoint = getattr(child, "ENDPOINT", None)
            if endpoint:
                found[endpoint] = ResourceSurface(
                    methods=frozenset(getattr(child, "METHODS", set())),
                    products=frozenset(getattr(child, "PRODUCTS", set())),
                    entries=(f"{child.__module__}.{child.__name__}",),
                )
            walk(child)

    walk(DbResource)
    return found


def typescript_resource_endpoints(
    manifest_path: Path = TYPESCRIPT_RESOURCES,
) -> dict[str, ResourceSurface]:
    """Read the npm resource metadata emitted by its generator."""

    if not manifest_path.exists():
        return {}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        resource["endpoint"]: ResourceSurface(
            methods=frozenset(resource["methods"]),
            products=frozenset(resource["products"]),
            entries=(resource["exportName"],),
        )
        for resource in manifest.get("resources", [])
    }


def resource_endpoints(
    python_root: Path = PYTHON_ROOT,
    manifest_path: Path = TYPESCRIPT_RESOURCES,
) -> dict[str, ResourceEndpoint]:
    """Map every resource route to the Python and npm parity subjects."""

    python = python_resource_endpoints(python_root)
    typescript = typescript_resource_endpoints(manifest_path)
    return {
        endpoint: ResourceEndpoint(python.get(endpoint), typescript.get(endpoint))
        for endpoint in sorted(python.keys() | typescript.keys())
    }
