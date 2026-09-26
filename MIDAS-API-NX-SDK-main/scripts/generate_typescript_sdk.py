"""Generate the language-neutral endpoint manifest and TypeScript resources.

The Python implementation currently carries the reviewed endpoint metadata
(`ENDPOINT`, `NAME`, `PRODUCTS`, `METHODS`) while ``docs/coverage.json`` carries
the official-manual provenance and live-verification ledger.  This generator
joins those two sources so the npm SDK cannot silently drift from PyPI.

Generated files are committed.  CI reruns this script and fails if the working
tree changes, making an official-manual/Python update visible to both SDKs.
"""

from __future__ import annotations

import ast
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SRC = ROOT / "src"
TYPESCRIPT_SRC = ROOT / "packages" / "typescript" / "src"
SCHEMA_DIR = ROOT / "schema"

_DOC_ENDPOINTS = {
    "/doc/NEW", "/doc/OPEN", "/doc/CLOSE", "/doc/SAVE", "/doc/SAVEAS",
    "/doc/STAGAS", "/doc/IMPORT", "/doc/IMPORTMXT", "/doc/EXPORT",
    "/doc/EXPORTMXT", "/doc/ANAL",
}
_DESIGN_TABLE_ENDPOINTS = {
    "/DESIGN/RC/KDS-41-20-2022/TABLE",
    "/DESIGN/SRC/AIK-SRC2K/TABLE",
}
_POST_TABLE_LEDGER_ALIASES = {
    "/post/BEAMDESIGNFORCES", "/post/COLUMNDESIGNFORCES",
    "/post/BRACEDESIGNFORCES", "/post/WALLDESIGNFORCES",
    "/post/STEELMEMBERDESIGNFORCES", "/post/SRCBEAMDESIGNFORCES",
    "/post/SRCCOLUMNDESIGNFORCES",
    "/post/COLDFORMEDSTEELMEMBERDESIGNFORCES",
}
_TABLE_OPTION_NAMES = {
    "table_name": "tableName",
    "export_path": "exportPath",
    "node_elems": "nodeElements",
    "unit": "unit",
    "styles": "styles",
    "components": "components",
    "load_case_names": "loadCaseNames",
    "opt_cs": "constructionStage",
    "stage_step": "stageSteps",
    "parts": "parts",
    "story_names": "storyNames",
    "modes": "modes",
    "additional": "additional",
    "set_calculation_method": "calculationMethod",
}


def _camel(value: str) -> str:
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", value) if part]
    if not parts:
        return "resource"
    first, *rest = parts
    return first[:1].lower() + first[1:] + "".join(p[:1].upper() + p[1:] for p in rest)


def _jsdoc(value: str, indent: int) -> list[str]:
    """Render reviewed Python endpoint documentation into TypeScript JSDoc."""
    if not value.strip():
        return []
    pad = "  " * indent
    lines = [f"{pad}/**"]
    for raw_line in value.replace("*/", "* /").splitlines():
        # Some historical Python sources contain mojibake warning glyphs from
        # an older Windows encoding. Keep npm declarations readable and turn
        # a damaged leading marker into an explicit warning label.
        marker = ""
        if "\u26a0" in raw_line or "\U0001f6d1" in raw_line:
            marker = "WARNING: "
        elif "\u2705" in raw_line:
            marker = "VERIFIED: "
        normalized = (
            raw_line.replace("\u2014", " - ")
            .replace("\u2013", " - ")
            .replace("\u2192", " -> ")
            .replace("\u00b0", " degrees ")
        )
        line = re.sub(r"[^\x09\x20-\x7e]", "", normalized).rstrip()
        line = re.sub(r"^(\s*)\?+\s*", r"\1WARNING: ", line)
        line = re.sub(r"\s+\?+\s+", " - ", line)
        if marker:
            line = re.sub(r"^(\s*)", rf"\1{marker}", line, count=1)
        lines.append(f"{pad} * {line}" if line.strip() else f"{pad} *")
    lines.append(f"{pad} */")
    return lines


def _module_parts(module: str) -> list[str]:
    return [_camel(part) for part in module.removeprefix("midas_nx.").split(".")]


def _namespace(module: str) -> str:
    parts = module.removeprefix("midas_nx.").split(".")
    return "".join(part[:1].upper() + _camel(part)[1:] for part in parts) + "Types"


def _path_namespace(module_path: list[str]) -> str:
    """The `types.ts` namespace for an npm module path, e.g. ``DbBoundaryTypes``.

    A contract states `modulePath` (`[db, boundary]`) and never a Python module,
    so this is how a contract-built type finds its namespace. For every module
    that has both it agrees with `_namespace`, which is why moving to it renamed
    nothing.
    """
    return "".join(part[:1].upper() + part[1:] for part in module_path) + "Types"


def _source_modules() -> dict[str, ast.Module]:
    modules: dict[str, ast.Module] = {}
    for path in sorted(PYTHON_SRC.joinpath("midas_nx").rglob("*.py")):
        relative = path.relative_to(PYTHON_SRC).with_suffix("")
        parts = list(relative.parts)
        if parts[-1] == "__init__":
            parts.pop()
        module = ".".join(parts)
        if not module:
            continue
        modules[module] = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return modules


def _import_map(module: str, tree: ast.Module) -> dict[str, tuple[str, str]]:
    imports: dict[str, tuple[str, str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level:
            base = module.split(".")[: -node.level]
            if node.module:
                base.extend(node.module.split("."))
            origin = ".".join(base)
        else:
            origin = node.module or ""
        for alias in node.names:
            imports[alias.asname or alias.name] = (origin, alias.name)
    return imports


def _collect_type_classes(
    modules: dict[str, ast.Module], resource_keys: set[tuple[str, str]]
) -> set[tuple[str, str]]:
    imports = {module: _import_map(module, tree) for module, tree in modules.items()}
    classes = {
        (module, node.name): node
        for module, tree in modules.items()
        for node in tree.body
        if isinstance(node, ast.ClassDef) and (module, node.name) not in resource_keys
    }
    typed: set[tuple[str, str]] = set()
    for key, node in classes.items():
        if any(ast.unparse(base).split(".")[-1] == "TypedDict" for base in node.bases):
            typed.add(key)

    changed = True
    while changed:
        changed = False
        for key, node in classes.items():
            if key in typed:
                continue
            module, _ = key
            for base in node.bases:
                if not isinstance(base, ast.Name):
                    continue
                resolved = imports[module].get(base.id, (module, base.id))
                if resolved in typed:
                    typed.add(key)
                    changed = True
                    break
    return typed


def _unwrap_required(annotation: ast.expr) -> tuple[ast.expr, bool | None]:
    if isinstance(annotation, ast.Subscript):
        name = ast.unparse(annotation.value).split(".")[-1]
        if name == "NotRequired":
            return annotation.slice, False
        if name == "Required":
            return annotation.slice, True
    return annotation, None


def _type_expression(
    node: ast.expr,
    *,
    module: str,
    local_types: set[str],
    imports: dict[str, tuple[str, str]],
    all_types: set[tuple[str, str]],
) -> str:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            try:
                parsed = ast.parse(node.value, mode="eval").body
            except SyntaxError:
                return "unknown"
            return _type_expression(
                parsed,
                module=module,
                local_types=local_types,
                imports=imports,
                all_types=all_types,
            )
        if node.value is None:
            return "null"
        if isinstance(node.value, (str, int, float, bool)):
            return json.dumps(node.value)
        if node.value is Ellipsis:
            return "unknown"
    if isinstance(node, ast.Name):
        primitives = {
            "str": "string",
            "int": "number",
            "float": "number",
            "bool": "boolean",
            "Any": "unknown",
            "object": "unknown",
            "None": "null",
            "dict": "JsonObject",
            "Mapping": "JsonObject",
        }
        if node.id in primitives:
            return primitives[node.id]
        if node.id in local_types:
            return node.id
        origin = imports.get(node.id)
        if origin in all_types:
            return f"{_namespace(origin[0])}.{origin[1]}"
        return "unknown"
    if isinstance(node, ast.Attribute):
        return _type_expression(
            ast.Name(id=node.attr),
            module=module,
            local_types=local_types,
            imports=imports,
            all_types=all_types,
        )
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left = _type_expression(node.left, module=module, local_types=local_types, imports=imports, all_types=all_types)
        right = _type_expression(node.right, module=module, local_types=local_types, imports=imports, all_types=all_types)
        return f"{left} | {right}"
    if isinstance(node, ast.Subscript):
        name = ast.unparse(node.value).split(".")[-1]
        slice_node = node.slice
        if name in {"Optional"}:
            inner = _type_expression(slice_node, module=module, local_types=local_types, imports=imports, all_types=all_types)
            return f"{inner} | null"
        if name in {"List", "list", "Sequence", "Iterable"}:
            inner = _type_expression(slice_node, module=module, local_types=local_types, imports=imports, all_types=all_types)
            return f"Array<{inner}>"
        if name in {"Dict", "dict", "Mapping", "MutableMapping"}:
            args = slice_node.elts if isinstance(slice_node, ast.Tuple) else [ast.Name(id="str"), slice_node]
            value = _type_expression(args[-1], module=module, local_types=local_types, imports=imports, all_types=all_types)
            return f"Record<string, {value}>"
        if name in {"Union", "Literal"}:
            args = slice_node.elts if isinstance(slice_node, ast.Tuple) else [slice_node]
            rendered = [
                _type_expression(arg, module=module, local_types=local_types, imports=imports, all_types=all_types)
                for arg in args
            ]
            return " | ".join(dict.fromkeys(rendered))
        if name in {"Tuple", "tuple"}:
            args = slice_node.elts if isinstance(slice_node, ast.Tuple) else [slice_node]
            if len(args) == 2 and isinstance(args[1], ast.Constant) and args[1].value is Ellipsis:
                inner = _type_expression(args[0], module=module, local_types=local_types, imports=imports, all_types=all_types)
                return f"Array<{inner}>"
            return "[" + ", ".join(
                _type_expression(arg, module=module, local_types=local_types, imports=imports, all_types=all_types)
                for arg in args
            ) + "]"
        if name in {"Required", "NotRequired", "ClassVar"}:
            return _type_expression(slice_node, module=module, local_types=local_types, imports=imports, all_types=all_types)
    return "unknown"


_CONTRACT_TS_TYPES = {
    "string": "string",
    "number": "number",
    "integer": "number",
    "boolean": "boolean",
    "object": "JsonObject",
}


def _contract_field_type(
    field: dict[str, Any],
    indent: str,
    attach: dict[str, list[str]] | None = None,
    path: str = "",
) -> str:
    """Render one contract field as a TypeScript type.

    ``attach`` carries variant unions down to the fields that hold their
    discriminators, keyed by dotted field path so a gate nested several levels
    down attaches where it belongs rather than at the nearest root. Where one
    lands, the union is intersected with that object - inside the element type
    when the field is an array. See ``_contract_payload_type``.
    """
    kind = field.get("type")
    # `key` is absent when a caller renders a bare type rather than a member.
    key = field.get("key", "")
    here = f"{path}.{key}" if path else key
    branches = (attach or {}).get(here) if here else None
    if field.get("properties"):
        body = _contract_interface_body(field["properties"], indent + "  ", attach, here)
        inner = "{\n" + body + f"\n{indent}}}"
        if branches:
            union = "\n".join(f"{indent}  {line}" for line in branches)
            inner += " & (\n" + union + f"\n{indent})"
            if kind == "array":
                inner = f"({inner})"
        return _array_of(field, inner) if kind == "array" else inner
    if kind == "array":
        item = (field.get("items") or {}).get("type")
        return _array_of(field, _CONTRACT_TS_TYPES.get(item, "unknown"))
    if field.get("enum") and kind == "string":
        return " | ".join(f'"{value}"' for value in field["enum"])
    return _CONTRACT_TS_TYPES.get(kind, "unknown")


def _array_of(field: dict[str, Any], item: str) -> str:
    """`Array<item>`, or a fixed tuple where the contract bounds it exactly.

    A matching pair of bounds is an exact contract fact, not a runtime guess.
    Preserving it as a tuple is what stops a TypeScript caller submitting a
    too-short vector to a field such as /db/BODF's FV.

    This used to live only on the path for arrays of scalars, so an array that
    gained a described item type silently lost its documented length: giving
    /db/NLNK's POINT_VALUES its `{VALUE}` member on 2026-09-04 turned
    `[JsonObject, JsonObject, JsonObject]` into a plain `Array<...>`, dropping
    the manual's "P0[3], P1[3], P2[3]" in the same change that made the item
    describable. Both paths go through here now.
    """

    minimum = field.get("minItems")
    if isinstance(minimum, int) and minimum == field.get("maxItems"):
        return "[" + ", ".join([item] * minimum) + "]"
    return f"Array<{item}>"


def _condition_text(entry: dict[str, Any]) -> str:
    """Render one `appliesWhen` entry, in either form the schema allows."""

    if "in" in entry:
        values = " or ".join(json.dumps(value) for value in entry["in"])
        return f"{entry['path']} is {values}"
    return f"{entry['path']} = {json.dumps(entry['equals'])}"


_PRODUCT_LABELS = {"gen": "Gen NX", "civil": "Civil NX"}


def _contract_interface_body(
    fields: list[dict[str, Any]],
    indent: str,
    attach: dict[str, list[str]] | None = None,
    path: str = "",
) -> str:
    lines: list[str] = []
    for field in fields:
        applies_when = field.get("appliesWhen", [])
        # The contract knows requiredness; the Python TypedDicts are all
        # `total=False`, so every field they produced was optional regardless
        # of what the manual said. This is the reversal paying for itself.
        #
        # A field the manual requires *within one branch* is not one every
        # payload carries, though. Typing it unconditionally required made
        # `/db/CCFC` demand `COEF` (only under TYPE="CONST") alongside
        # `SCALE_FACTOR` and `ITEM` (only under TYPE="USER"): no caller could
        # satisfy the type without sending fields their own branch does not
        # have. 49 fields across nine contracts were in that state, `/db/EPMT`
        # asking for all six plasticity models at once. The condition moves
        # into the doc comment, which is where a requiredness TypeScript
        # cannot express belongs.
        optional = "" if field.get("requirement") == "required" and not applies_when else "?"
        documentation = []
        if field.get("description"):
            documentation.append(" ".join(field["description"].split()))
        if applies_when:
            rendered = " and ".join(_condition_text(entry) for entry in applies_when)
            verb = "Required when" if field.get("requirement") == "required" else "Applies when"
            documentation.append(f"{verb} {rendered}.")
        # `products` on a resource says which products answer the route;
        # `products` on a field says which of them declare this key, and the
        # two are not the same question. 53 fields across eight contracts
        # narrow it, and until 2026-09-04 none of that reached a caller: the
        # generator read the resource-level list and ignored the field-level
        # one, so a Civil NX caller of /db/POGD saw twenty Gen-only fiber-model
        # options offered as if they were theirs.
        products = field.get("products")
        if products and len(products) == 1:
            documentation.append(f"{_PRODUCT_LABELS[products[0]]} only.")
        if documentation:
            lines.append(f"{indent}/** {' '.join(documentation)} */")
        lines.append(
            f"{indent}{field['key']}{optional}: "
            f"{_contract_field_type(field, indent, attach, path)};"
        )
    return "\n".join(lines)


def _contract_payload_type(name: str, contract: dict[str, Any]) -> list[str]:
    """Render a contract payload without flattening conditional branches.

    A contract variant is a manual statement about one wire discriminator.  A
    TypeScript intersection with a discriminated union keeps that fact visible:
    callers must choose one documented branch instead of being offered a
    misleading interface containing every branch's fields at once.

    A variant's fields are siblings of the field it gates on, so each union
    attaches where its own discriminator lives - and only a root-level
    discriminator makes that the payload root. Six contracts gate on a field
    the manual nests: ``/db/SWIND`` and ``/db/SSEIS`` inside ``PARAMETERS``,
    ``/db/PRES``, ``/db/MCON`` and the KDS column-rebar endpoint inside an
    array element. Attaching those at the root published ``WIND_SPEED``,
    ``EXP_CATEGORY`` and ``PERIOD_APPR_X`` as top-level payload members, which
    is where the server does not look - the same defect the ``/db/BTMP``
    nesting fix corrected one level further down.

    Two of them branch on **two** axes at two depths: ``/db/SWIND`` selects a
    ``PARAMETERS`` shape with the root ``WIND_CODE`` and then branches again on
    ``PARAMETERS.INPUT_METHOD``. So the variants are grouped by where they
    attach and each group becomes its own union, rather than one union per
    contract.
    """

    fields = contract["fields"]
    variants = contract.get("variants", [])
    lines = [f"  /** Generated from {contract.get('source', 'contracts/endpoints/')}. */"]
    if not variants:
        lines.append(f"  export interface {name} {{")
        lines.append(_contract_interface_body(fields, "    "))
        lines.append("  }")
        return lines

    groups: dict[str | None, list[dict[str, Any]]] = {}
    for variant in variants:
        groups.setdefault(_variant_attach_key(fields, variant), []).append(variant)

    nested = {
        key: _variant_union(_attach_base(fields, key), group)
        for key, group in groups.items()
        if key is not None
    }
    root = groups.get(None)

    lines.append(f"  export type {name} = {{")
    lines.append(_contract_interface_body(fields, "    ", nested or None))
    if root is None:
        lines.append("  };")
        return lines
    lines.append("  } & (")
    lines.extend(f"    {line}" for line in _variant_union(fields, root))
    lines.append("  );")
    return lines


def _attach_base(fields: list[dict[str, Any]], path: str) -> list[dict[str, Any]]:
    """The declared members of the object a nested union attaches to.

    Exhaustiveness is judged against the discriminator's own declaration, so it
    has to be looked up beside the branch rather than at the payload root.
    """
    for step in path.split("."):
        fields = next(
            (field.get("properties") or [] for field in fields if field["key"] == step), []
        )
    return fields


def _variant_union(base: list[dict[str, Any]], variants: list[dict[str, Any]]) -> list[str]:
    """One discriminated union, rendered without a leading indent.

    The caller decides how far in it sits, which is what lets the same union be
    emitted at the payload root or spliced into a nested object.
    """
    # A multi-value table is the manual's *shared* table only when it overlaps
    # another one: /db/FBLA states a table for ``FLOOR_DIST_TYPE = 1 or 2``
    # alongside its ``= 1`` and ``= 2`` tables, and emitting that as its own
    # union member would make two members match the same discriminator. Fold
    # its fields into every branch it covers instead.
    #
    # Overlap is what decides it, not the plural on its own. A table naming
    # several values that no other table names is an ordinary branch that
    # happens to cover more than one value - /db/PRES's ``FACE_EDGE_TYPE =
    # "FACE" or "PRES"`` against its separate ``= "EDGE"``. Treating every
    # plural table as shared dropped those branches entirely, because folding
    # keeps only the single-value ones: /db/PRES lost FORCES, /db/MVHL lost the
    # South African VEH_ZA, and /db/TDME lost four of its six code branches.
    shared = [
        v
        for v in variants
        if any("in" in c for c in v["when"])
        and any(_shared_covers(v["when"], other["when"]) for other in variants if other is not v)
    ]
    branches = [v for v in variants if v not in shared]
    if shared and branches:
        variants = [
            {**branch, "fields": branch["fields"] + [
                field
                for extra in shared
                if _shared_covers(extra["when"], branch["when"])
                for field in extra["fields"]
            ]}
            for branch in branches
        ]

    # A union of only the documented branches says every other value of the
    # discriminator is illegal, and the manual rarely gives a table for all of
    # them: /db/FBLA documents FLOOR_DIST_TYPE 1 to 4 and supplies tables for 1
    # and 2, so 3 and 4 became untypeable. Exhaustiveness has to be proven, not
    # assumed - a declared enum the branches cover exactly, or both values of a
    # boolean. Otherwise a trailing member carries the remaining values, and
    # denies each branch's own fields so a wrong-branch field is still an
    # error. Widening the enums the extractor cannot yet read is what would
    # narrow these unions again.
    base_by_key = {field["key"]: field for field in base}
    selectors: dict[str, set[str]] = {}
    for variant in variants:
        for condition in variant["when"]:
            if "." in condition["path"]:
                continue
            values = condition["in"] if "in" in condition else [condition["equals"]]
            selectors.setdefault(condition["path"], set()).update(
                json.dumps(value) for value in values
            )
    residual = [
        key
        for key in dict.fromkeys(
            field["key"] for variant in variants for field in variant["fields"]
        )
        if key not in base_by_key and key not in selectors
    ]
    exhaustive = all(
        _selector_is_exhaustive(base_by_key.get(path), values)
        for path, values in selectors.items()
    )

    lines: list[str] = []
    for index, variant in enumerate(variants):
        conditions = variant["when"]
        lines.append("{")
        # A condition path may be nested (``STR.SPEC_CODE``). Only a
        # discriminator declared beside this branch can be narrowed as one of
        # its properties; a deeper one is documentation the branch body already
        # carries, so it is not emitted twice.
        roots = [c for c in conditions if "." not in c["path"]]
        for condition in roots:
            if "in" in condition:
                union = " | ".join(json.dumps(value) for value in condition["in"])
                lines.append(f"  {condition['path']}: {union};")
            else:
                lines.append(f"  {condition['path']}: {json.dumps(condition['equals'])};")
        # A manually transcribed variant table often repeats its discriminator
        # as the first row (for example ``iMETHOD = 2`` followed by an
        # ``iMETHOD`` parameter row). The literal branch discriminator is the
        # more precise declaration; rendering the repeated general field would
        # create an illegal duplicate TypeScript property.
        narrowed = {condition["path"] for condition in roots}
        branch_fields = [field for field in variant["fields"] if field.get("key") not in narrowed]
        # One entry per line, because the caller indents this union line by
        # line to place it - a joined block would keep its own indentation and
        # land at the wrong depth wherever the union is not at the root.
        lines.extend(_contract_interface_body(branch_fields, "  ").splitlines())
        last = index == len(variants) - 1 and exhaustive
        lines.append("}" + ("" if last else " |"))
    if not exhaustive:
        lines.append("{")
        for key in residual:
            lines.append(f"  {key}?: never;")
        lines.append("}")
    return lines


def _variant_attach_key(fields: list[dict[str, Any]], variant: dict[str, Any]) -> str | None:
    """The dotted path of the object whose members this variant's fields join.

    That is the object holding its discriminator, at whatever depth the
    contract declares it - a gate found only at the nearest root would attach
    the branch above the object it belongs to, which is the bug this returns a
    full path to avoid.

    ``None`` means the payload root, either because the gate is a root field or
    because the contract declares it nowhere. The second case is left where it
    already was rather than given an invented home: ``/db/MVLD``'s
    ``LOAD_MODEL`` is declared inside a sibling variant, and no permitted source
    says which object holds it.

    A variant gating on two fields at two depths would have no single place to
    attach. None does, and one appearing is a contract to look at rather than a
    default to pick, so it raises.
    """
    attachments = set()
    for condition in variant["when"]:
        # Gates come in both spellings the corpus uses: a bare field name that
        # may live anywhere (`FACE_EDGE_TYPE`) and a path already rooted at the
        # payload (`PARAMETERS.INPUT_METHOD`). Resolving the last segment
        # against the contract's own tree answers both, and answers with the
        # canonical path rather than trusting the spelling.
        found = _field_path(fields, condition["path"].rsplit(".", 1)[-1])
        # The array marker is a rendering detail; the attach point is the field.
        parent = found.rsplit(".", 1)[0].replace("[]", "") if found and "." in found else None
        attachments.add(parent)
    if len(attachments) != 1:
        raise ValueError(
            "one variant's discriminators sit at different depths, so its branch "
            f"has no single place to attach: {sorted(c['path'] for c in variant['when'])}"
        )
    return attachments.pop()


def _selector_is_exhaustive(field: dict[str, Any] | None, values: set[str]) -> bool:
    """Whether the branches provably cover every value this selector allows.

    Only two things prove it. A declared ``enum`` is the contract's own list of
    legal values, so branches matching it leave nothing out. A boolean has
    exactly two. A prose description that happens to name three values is not
    evidence: reading it would be inferring the enum, which contracts forbid.
    """

    if field is None:
        return False
    if field.get("type") == "boolean":
        return values == {"true", "false"}
    declared = field.get("enum")
    return bool(declared) and {json.dumps(value) for value in declared} == values


def _shared_covers(shared_when: list[dict], branch_when: list[dict]) -> bool:
    """Whether a shared multi-value table applies to this single-value branch.

    True when every condition of the branch is satisfied by the shared table's
    own conditions on the same path - that is, the branch's value is among the
    values the shared table names.
    """
    by_path = {condition["path"]: condition for condition in shared_when}
    for condition in branch_when:
        extra = by_path.get(condition["path"])
        if extra is None:
            return False
        permitted = extra["in"] if "in" in extra else [extra["equals"]]
        if condition.get("equals") not in permitted:
            return False
    return True


def _is_contract_shadow_resource(endpoint: str) -> bool:
    """Whether this resource family is covered by the contract shadow gate."""

    return endpoint.startswith(("/db/", "/DESIGN/"))


def _strip_assign_envelope(
    contract: dict[str, Any], envelope_key: str = "Assign"
) -> tuple[list[dict], list[dict]]:
    """Return the record a caller passes, with the request envelope removed.

    The manual's Parameters tables open with a row for ``"Assign"``, the
    ID-keyed map the request body is wrapped in. That row is documentation of
    the envelope, not of the record - and ``DbResource.create``/``.update``
    build the envelope themselves, from the ``ItemMap`` keys the caller passes.
    Emitting the row into the payload type therefore published 60 interfaces
    demanding a member the SDK adds, so satisfying the type sent
    ``{"Assign": {"1": {"Assign": ...}}}``. Two shapes appear and both mean the
    same thing:

      ``Assign: JsonObject`` beside the real fields - a placeholder row, as in
        ``/DESIGN/RC/KDS-41-20-2022/KFAC``, whose ``Ky``/``Kz``/``Kt`` are the
        record.
      ``Assign`` carrying the record as its own ``properties`` - as in
        ``/db/REBR``, where the table nests ``ITEMS`` beneath it.

    Every caller of this function is a ``DbResource``, and a ``DbResource``
    always addresses one record per ID - so a top-level ``Assign`` is the
    envelope by construction, whatever the methods are. Keying the rule on an
    ``assign`` request wrapper instead left the two ``LCTB`` contracts behind:
    they are GET/DELETE only, so they declare no request wrapper at all, while
    their row still reads "Assign 래퍼 (ID 문자열 키)" and their chapter-27 twin
    - generated from Python, not from a contract - has never had the member.
    """

    fields = contract.get("fields") or []
    variants = contract.get("variants") or []
    # A plain-function endpoint wraps its body in `"Argument"` the same way,
    # and its npm operation adds that wrapper itself; see
    # `_contract_argument_types`.
    envelope = next((field for field in fields if field["key"] == envelope_key), None)
    if envelope is None:
        return fields, variants
    siblings = [field for field in fields if field is not envelope]
    inner = envelope.get("properties") or []
    if inner and siblings:
        # No contract does this today. If one appears, which half is the record
        # is a question for a reviewer, not for a default.
        return fields, variants
    record = inner or siblings

    def rerooted(path: str) -> str:
        prefix = envelope_key + "."
        return path[len(prefix) :] if path.startswith(prefix) else path

    def reroot(node: Any) -> Any:
        if isinstance(node, dict):
            return {
                key: rerooted(value) if key == "path" and isinstance(value, str) else reroot(value)
                for key, value in node.items()
            }
        if isinstance(node, list):
            return [reroot(item) for item in node]
        return node

    return reroot(record), reroot(variants)


def _admits_incomplete_fields(contract: dict[str, Any]) -> bool:
    """Whether a contract says its field list is missing tables it should have.

    An `unmergedTables` entry marked `excluded` is not such a table: review, with
    evidence, decided it is not part of this API's request at all - /db/TDME's
    two Japan code tables belong to iGen, and every spelling of those codes
    answers Wrong Field on both NX products. A field list missing only those is
    complete for this API, so it can be the published payload type.
    """
    entries = (contract.get("extraction") or {}).get("unmergedTables") or []
    return any(not entry.get("excluded") for entry in entries)


def _contract_payload_fields() -> dict[str, dict[str, Any]]:
    """Payload fields for the contract-derived resource shadow path.

    Resource payloads only. A plain-function contract's argument is built by
    `_contract_argument_types`, which removes the `"Argument"` wrapper instead
    of `"Assign"` and keeps its own list of arguments left on Python.
    """
    contract_dir = ROOT / "contracts" / "endpoints"
    if not contract_dir.is_dir():
        return {}
    import yaml  # noqa: PLC0415

    found: dict[str, dict[str, Any]] = {}
    for path in sorted(contract_dir.glob("*.yaml")):
        contract = yaml.safe_load(path.read_text(encoding="utf-8"))
        # A contract carrying unmergedTables knows it is incomplete: the manual
        # names no wire discriminator for one of its tables. Its field list is
        # still worth having in the source of truth, but narrowing a published
        # payload type onto an admittedly partial list would break callers who
        # set a field the manual documents in the table nobody could merge.
        unmerged = _admits_incomplete_fields(contract)
        if (
            _is_contract_shadow_resource(contract.get("endpoint", ""))
            and contract.get("fields")
            and not unmerged
        ):
            fields, variants = _strip_assign_envelope(contract)
            found[contract["endpoint"]] = {"fields": fields, "variants": variants}
    return found


def _python_type_declaration(
    module: str,
    node: ast.ClassDef,
    *,
    tree: ast.Module,
    type_keys: set[tuple[str, str]],
) -> list[str]:
    """Render one TypedDict the contracts have not taken over."""
    module_types = {name for owner, name in type_keys if owner == module}
    imports = _import_map(module, tree)
    total = not any(
        keyword.arg == "total" and isinstance(keyword.value, ast.Constant) and keyword.value.value is False
        for keyword in node.keywords
    )
    bases: list[str] = []
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id != "TypedDict":
            rendered = _type_expression(base, module=module, local_types=module_types, imports=imports, all_types=type_keys)
            if rendered != "unknown":
                bases.append(rendered)
    extends = f" extends {', '.join(bases)}" if bases else ""
    lines = [f"  export interface {node.name}{extends} {{"]
    for field in node.body:
        if not isinstance(field, ast.AnnAssign) or not isinstance(field.target, ast.Name):
            continue
        annotation, explicit_required = _unwrap_required(field.annotation)
        required = total if explicit_required is None else explicit_required
        rendered = _type_expression(
            annotation,
            module=module,
            local_types=module_types,
            imports=imports,
            all_types=type_keys,
        )
        optional = "" if required else "?"
        lines.append(f"    {field.target.id}{optional}: {rendered};")
    lines.append("  }")
    return lines


#: Python TypedDicts npm stopped publishing on 2026-09-22, at the author's
#: request. Each was an exported name nothing in the generated SDK referenced:
#: wherever the object is sent, the payload or argument that carries it is
#: built from its contract and declares the shape inline. What kept them was
#: the rule that an export is never dropped as a side effect - this is the
#: deliberate drop. The Python classes stay; they are the Python package's.
_PYTHON_TYPES_WITHDRAWN: dict[str, str] = {
    "ItemGroupFields": "a Python base class; each item type declares its members",
    "ColumnBraceRebarDesignCriteriaItem": "a Python base class with no wire object",
    "_LoadCombinationSteelSrcKdsArgument": "a Python base class; LCOM-STEEL and LCOM-SRC declare theirs",
    "LoadCombinationPayload": "a shared Python shape; each /db/LCOM-* payload is its own",
    "_ColorPayload": "a shared Python shape; each /db/CO_* payload is its own",
    "InitialLoadCaseItem": "the contracts that carry it disagree on its requiredness",
    "OptUseToleranceValue": "the contracts that carry it disagree on its requiredness",
    "LoadGroupDayItem": "/db/STAG requires LOAD_NAME and /db/HSTG does not",
    "SectBefore": "each /db/SECT SECTTYPE branch declares its own SECT_BEFORE",
    "StorySetAngle": "two story tables require ANGLE and two do not",
    "InelasticMaterialKentParkParam": "/db/FIMP's payload declares KENPAR inline",
    "AllowableStressLine": "referenced by nothing, in Python either",
    "RcDesignForcesArgument": "no operation takes it",
    "SrcDesignForcesArgument": "no operation takes it",
}


def _type_layout(
    modules: dict[str, ast.Module],
    type_keys: set[tuple[str, str]],
    contract_types: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, dict[str, tuple[Any, ...]]]:
    """Every published type, as ``{namespace: {name: source}}``.

    The contract-built types are keyed by the namespace and name their
    contracts state. A Python TypedDict fills a slot only if no contract has
    claimed it. So which types exist, and where, no longer depends on the
    Python tree for anything a contract owns: deleting a TypedDict a contract
    has taken over changes nothing in `types.ts`.

    A Python type that refers to another one does so by the Python module that
    class lives in (`_type_expression`). That still resolves, because a
    contract claims the same ``(namespace, name)`` its class occupied.
    """
    layout: dict[str, dict[str, tuple[Any, ...]]] = defaultdict(dict)
    for (namespace, name), contract in contract_types.items():
        layout[namespace][name] = ("contract", contract)
    withdrawn_seen: set[str] = set()
    for module, tree in modules.items():
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or (module, node.name) not in type_keys:
                continue
            slot = layout[_namespace(module)]
            if node.name in slot:
                continue
            if node.name in _PYTHON_TYPES_WITHDRAWN:
                withdrawn_seen.add(node.name)
                continue
            slot[node.name] = ("python", module, node, tree)
    stale = sorted(set(_PYTHON_TYPES_WITHDRAWN) - withdrawn_seen)
    if stale:
        raise ValueError(
            "listed in _PYTHON_TYPES_WITHDRAWN but no Python type of that name is left "
            f"unclaimed, so the entry is stale: {stale}"
        )
    return layout


def _render_types(
    modules: dict[str, ast.Module],
    type_keys: set[tuple[str, str]],
    contract_types: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> str:
    """Render `types.ts`: namespaces in name order, types in name order.

    Declaration order carries no meaning in TypeScript, and the order used to
    be the order classes appear in the Python source - the one thing a contract
    could never reproduce. Sorting by name is an order both sources can give.
    """
    contract_types = contract_types or {}
    layout = _type_layout(modules, type_keys, contract_types)
    # What a remaining Python type may refer to: the TypedDicts still in the
    # tree, and every slot a contract fills. Twelve contract-built types are
    # referred to from Python-built ones (`OpeTypes.OrthoEffect`, ...), and the
    # reference must not depend on the class the contract replaced still
    # existing.
    namespaces = {_namespace(module): module for module in modules}
    known = type_keys | {
        (namespaces[namespace], name)
        for namespace, name in contract_types
        if namespace in namespaces
    }
    chunks = [
        "// Generated by scripts/generate_typescript_sdk.py. Do not edit by hand.",
        'import type { JsonObject } from "../types";',
        "",
    ]
    for namespace in sorted(layout):
        chunks.append(f"export namespace {namespace} {{")
        for name, source in sorted(layout[namespace].items()):
            if source[0] == "contract":
                chunks.extend(_contract_payload_type(name, source[1]))
            else:
                _, module, node, tree = source
                chunks.extend(
                    _python_type_declaration(module, node, tree=tree, type_keys=known)
                )
        chunks.append("}")
        chunks.append("")
    return "\n".join(chunks)


def _contract_payload_defaults() -> dict[str, dict[str, Any]]:
    """Read ``normalize_defaults`` rules out of contracts/endpoints/*.yaml.

    Payload normalization is *behaviour*, not metadata, which is precisely why
    it never survived the trip from Python to TypeScript: ``/db/NMAS``'s
    rmX/rmY/rmZ workaround lived inside ``NodalMass.create()``, so the npm
    package shipped a month after that fix without it and could still kill a
    live NX session. Reading the rule from the language-neutral contract instead
    means neither SDK can be the one that has it.

    Contracts are optional here on purpose: they are being introduced endpoint by
    endpoint, and an endpoint without one simply gets no defaults.
    ``scripts/validate_contracts.py`` is what fails CI when a contract exists and
    an SDK does not honour it.
    """
    contract_dir = ROOT / "contracts" / "endpoints"
    if not contract_dir.is_dir():
        return {}
    try:
        import yaml  # noqa: PLC0415
    except ImportError:  # pragma: no cover - dev dependency
        raise SystemExit(
            "contracts/ is present but PyYAML is not installed. "
            'Run: pip install -e ".[dev]"'
        ) from None

    defaults: dict[str, dict[str, Any]] = {}
    for path in sorted(contract_dir.glob("*.yaml")):
        contract = yaml.safe_load(path.read_text(encoding="utf-8"))
        merged: dict[str, Any] = {}
        for rule in contract.get("sdkRules", []):
            if rule.get("kind") == "normalize_defaults":
                merged.update(rule.get("values", {}))
        if merged:
            defaults[contract["endpoint"]] = merged
    return defaults


# Metadata keys that change what DbResource does at runtime, as opposed to
# describing the endpoint. Every one is derived from a contract rule.
_RUNTIME_BEHAVIOUR_KEYS = ("payloadDefaults", "rejectEmptyFields", "requiredExplicitFields")


def _field_path(fields: list[dict[str, Any]], key: str, prefix: str = "") -> str | None:
    """Where a contract declares ``key``, written the way a runtime walks it.

    An array field becomes ``ITEMS[].DIRECTION`` and an object field
    ``PARENT.CHILD``, so a rule that names a bare field key still reaches the
    right place when the manual nests it. Returns None when the contract does
    not declare the key at all, which the caller turns into an error rather
    than a silently skipped rule.
    """
    for field in fields or []:
        step = "[]" if field.get("type") == "array" else ""
        here = f"{prefix}{field['key']}"
        if field["key"] == key:
            return here
        found = _field_path(field.get("properties") or [], key, f"{here}{step}.")
        if found is not None:
            return found
    return None


def _contract_reject_rules() -> dict[str, dict[str, list[str]]]:
    """Read ``reject_request`` rules, split by what each one actually refuses.

    The sibling of ``_contract_payload_defaults()`` and there for the same
    reason: a rule written in one language reaches one language's users.

    ``rejects`` is what keeps the two apart, and it is a contract field rather
    than a guess because the kind alone does not say which check to run.
    ``empty_value`` is ``/db/MVHL``'s ``VEH_DEFAULT: {}`` - accepted by the
    server, stored as nothing, answered with a success-shaped body.
    ``omission`` is ``/db/PRES``'s ``DIRECTION`` - absent, so the server
    applies a documented default it then refuses. Running either check on the
    other's fields would be wrong in both directions.
    ``forbidden_combination`` travels to neither: those rules name several
    fields that are individually valid, and no generic runtime check follows
    from a field list alone.

    Field names are resolved against the contract's own field tree, so a rule
    may name the key the manual uses and the runtime still receives the path.
    """
    contract_dir = ROOT / "contracts" / "endpoints"
    if not contract_dir.is_dir():
        return {}
    import yaml  # noqa: PLC0415

    wanted = {"empty_value": "rejectEmptyFields", "omission": "requiredExplicitFields"}
    rules: dict[str, dict[str, list[str]]] = {}
    for path in sorted(contract_dir.glob("*.yaml")):
        contract = yaml.safe_load(path.read_text(encoding="utf-8"))
        for rule in contract.get("sdkRules", []):
            if rule.get("kind") != "reject_request":
                continue
            metadata_key = wanted.get(rule.get("rejects"))
            if metadata_key is None:
                continue
            for name in rule.get("fields", []):
                resolved = _field_path(contract.get("fields", []), name)
                if resolved is None:
                    raise ValueError(
                        f"{path.name}: sdkRule {rule['id']} names the field "
                        f"{name!r}, which the contract does not declare"
                    )
                bucket = rules.setdefault(contract["endpoint"], {}).setdefault(
                    metadata_key, []
                )
                if resolved not in bucket:
                    bucket.append(resolved)
    return rules


def _contract_resource_surfaces(
    resource_endpoints: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Read the contract-owned surface of each contracted resource.

    Class and module names remain compatibility anchors while the public npm
    tree is still organised like the existing SDK.  The endpoint, display
    name, products, methods and manual chapter are contract facts.  Keeping
    those two roles separate lets this Stage 3 shadow run replace only facts
    the contract actually owns, and leaves an uncontracted resource on the
    previous Python fallback path.
    """

    contract_dir = ROOT / "contracts" / "endpoints"
    if not contract_dir.is_dir():
        return {}
    try:
        import yaml  # noqa: PLC0415
    except ImportError:  # pragma: no cover - dev dependency
        raise SystemExit(
            "contracts/ is present but PyYAML is not installed. "
            'Run: pip install -e "[dev]"'
        ) from None

    surfaces: dict[str, dict[str, Any]] = {}
    for path in sorted(contract_dir.glob("*.yaml")):
        contract = yaml.safe_load(path.read_text(encoding="utf-8"))
        endpoint = contract.get("endpoint", "")
        if (
            not _is_contract_shadow_resource(endpoint)
            or (resource_endpoints is not None and endpoint not in resource_endpoints)
            or not contract.get("fields")
        ):
            continue
        if endpoint in surfaces:
            raise ValueError(f"Duplicate resource contract for {endpoint}")
        surfaces[endpoint] = {
            "name": contract["name"],
            "products": sorted(contract["products"]),
            "methods": sorted({operation["method"] for operation in contract["operations"]}),
            "manualChapter": contract["source"]["manual"].get("chapterFile"),
        }
        # The published npm names, where the contract has taken ownership of
        # them. They are seeded from this generator's own committed output, so
        # they rename nothing; recording them is what stops a Python module
        # move from silently renaming an npm export.
        for key, value in (contract.get("surface") or {}).items():
            surfaces[endpoint][key] = value
    return surfaces


def _contract_resource_mismatches(resource: dict[str, Any], surface: dict[str, Any]) -> list[str]:
    """Compare a legacy SDK resource with the facts its contract owns.

    Endpoint labels are manual facts too. The manual and legacy surface use
    different dash typography in a few labels, which is presentation-only, but
    an endpoint string in place of a documented label is still a disagreement.
    """

    chapter = next(
        (manual.get("chapterFile") for manual in resource.get("manual", []) if manual.get("chapterFile")),
        None,
    )
    actual = {
        "name": resource["name"],
        "products": resource["products"],
        "methods": resource["methods"],
        "manualChapter": chapter,
    }
    # `surface` is optional: an endpoint whose contract has not taken the
    # names over stays on the Python fallback, exactly as it does for `name`.
    # Where it is present it is checked, so the two cannot drift apart.
    for key in ("className", "exportName", "modulePath"):
        if key in surface:
            actual[key] = resource.get(key)
    def same_value(key: str) -> bool:
        if key != "name":
            return actual[key] == surface[key]
        return actual[key].replace("\u2013", "-").replace("\u2014", "-") == surface[key].replace(
            "\u2013", "-"
        ).replace("\u2014", "-")

    return [
        f"{key}: SDK has {actual[key]!r}, contract has {surface[key]!r}"
        for key in actual
        if not same_value(key)
    ]


def _contract_surface_blocks() -> dict[str, dict[str, Any]]:
    """Every contract's `surface` block, keyed by endpoint."""

    contract_dir = ROOT / "contracts" / "endpoints"
    if not contract_dir.is_dir():
        return {}
    import yaml  # noqa: PLC0415

    blocks: dict[str, dict[str, Any]] = {}
    for path in sorted(contract_dir.glob("*.yaml")):
        contract = yaml.safe_load(path.read_text(encoding="utf-8"))
        surface = contract.get("surface")
        if surface:
            blocks[contract["endpoint"]] = surface
    return blocks


_RESOURCE_IDENTITY_KEYS = (
    "className",
    "exportName",
    "modulePath",
    "name",
    "products",
    "methods",
)


def _resource_identity(
    surface: dict[str, Any] | None, fallback: dict[str, Any] | None
) -> dict[str, Any]:
    """What npm calls a resource, contract first and Python second.

    The precedence is the whole point of the contract migration, so it lives in
    one function rather than inline in a loop: a fact the contract states is the
    fact, and the Python class answers only what no contract has claimed. A
    `fallback` of ``None`` is an endpoint no Python class declares - the contract
    then has to carry every key, and a missing one is a contract defect rather
    than something to guess.
    """

    surface = surface or {}
    fallback = fallback or {}
    identity: dict[str, Any] = {}
    for key in _RESOURCE_IDENTITY_KEYS:
        if key in surface:
            identity[key] = surface[key]
        elif key in fallback:
            identity[key] = fallback[key]
        else:
            raise KeyError(
                f"neither the contract surface nor a Python class supplies {key!r}"
            )
    return identity


_RESOURCE_SOURCE_COUNTS: dict[str, int] = {}


class _Unresolved(Exception):
    """A class fact the source does not state in a form this reader follows."""


def _static_resource_classes(modules: dict[str, ast.Module]) -> dict[str, dict[str, Any]]:
    """Every `DbResource` subclass, by endpoint, read from source - not imported.

    The same facts the generator used to get by importing `midas_nx` (until
    2026-09-17), read from the syntax tree the generator already parses for
    payload types and operations. It follows exactly what the package uses to
    state them and nothing more: string literals and f-strings, `frozenset`
    literals of strings, module-level constants, relative imports, and single
    inheritance up to `DbResource`'s own defaults. Anything else raises and
    names the class, because a fact this reader guessed would be a fact the npm
    package published without anyone having written it.
    """
    imports = {module: _import_map(module, tree) for module, tree in modules.items()}
    classes: dict[tuple[str, str], ast.ClassDef] = {}
    for module, tree in modules.items():
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                classes[(module, node.name)] = node

    def assigned(tree: ast.Module, name: str) -> ast.expr | None:
        for node in tree.body:
            if isinstance(node, ast.Assign):
                if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                    return node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                if isinstance(node.target, ast.Name) and node.target.id == name:
                    return node.value
        return None

    def locate(module: str, name: str, kind: str) -> tuple[str, str]:
        """Follow imports to the module that defines `name`."""
        start = (module, name)
        seen: set[tuple[str, str]] = set()
        while (module, name) not in seen:
            seen.add((module, name))
            if kind == "class" and (module, name) in classes:
                return module, name
            if kind == "constant" and assigned(modules[module], name) is not None:
                return module, name
            origin = imports.get(module, {}).get(name)
            if origin is None or origin[0] not in modules:
                break
            module, name = origin
        raise _Unresolved(f"{kind} {start[1]!r} as seen from {start[0]}")

    def value(module: str, node: ast.expr) -> Any:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            owner, name = locate(module, node.id, "constant")
            expr = assigned(modules[owner], name)
            assert expr is not None
            return value(owner, expr)
        if isinstance(node, (ast.Set, ast.Tuple, ast.List)):
            items = [value(module, element) for element in node.elts]
            if not all(isinstance(item, str) for item in items):
                raise _Unresolved(f"a collection of non-strings in {module}")
            return frozenset(items)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"frozenset", "set", "tuple"}
            and len(node.args) == 1
            and not node.keywords
        ):
            return value(module, node.args[0])
        if isinstance(node, ast.JoinedStr):
            parts: list[str] = []
            for part in node.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    parts.append(part.value)
                elif isinstance(part, ast.FormattedValue) and part.format_spec is None:
                    resolved = value(module, part.value)
                    if not isinstance(resolved, str):
                        raise _Unresolved(f"a non-string f-string part in {module}")
                    parts.append(resolved)
                else:
                    raise _Unresolved(f"an f-string part this reader does not follow in {module}")
            return "".join(parts)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = value(module, node.left), value(module, node.right)
            if isinstance(left, str) and isinstance(right, str):
                return left + right
        raise _Unresolved(f"{ast.unparse(node)!r} in {module}")

    def bases(key: tuple[str, str]) -> list[tuple[str, str]]:
        module, class_name = key
        found: list[tuple[str, str]] = []
        for base in classes[key].bases:
            if isinstance(base, ast.Name):
                try:
                    found.append(locate(module, base.id, "class"))
                except _Unresolved:
                    continue  # a base outside the package, e.g. `object`
        return found

    def attribute(key: tuple[str, str], name: str) -> Any:
        module, class_name = key
        for node in classes[key].body:
            target: ast.expr | None = None
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                target = node.target
            if isinstance(target, ast.Name) and target.id == name:
                assert node.value is not None
                return value(module, node.value)
        parents = bases(key)
        if len(parents) > 1:
            raise _Unresolved(f"{name} on {class_name}, which has several bases")
        if not parents:
            raise KeyError(name)
        return attribute(parents[0], name)

    root = ("midas_nx.db.base", "DbResource")
    if root not in classes:
        raise _Unresolved("DbResource itself")
    children: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for key in classes:
        for parent in bases(key):
            children[parent].append(key)

    found: dict[str, dict[str, Any]] = {}
    pending = list(children[root])
    visited: set[tuple[str, str]] = set()
    while pending:
        key = pending.pop()
        if key in visited:
            continue
        visited.add(key)
        pending.extend(children[key])
        module, class_name = key
        try:
            endpoint = attribute(key, "ENDPOINT")
        except KeyError:
            continue  # an intermediate base that states no endpoint of its own
        try:
            name = attribute(key, "NAME")
        except KeyError:
            name = ""
        facts = {
            "className": class_name,
            "exportName": _camel(class_name),
            "endpoint": endpoint,
            "name": name or class_name,
            "products": sorted(attribute(key, "PRODUCTS")),
            "methods": sorted(attribute(key, "METHODS")),
            "pythonModule": module,
            "modulePath": _module_parts(module),
        }
        if endpoint in found:
            raise _Unresolved(
                f"{endpoint} is declared by both {found[endpoint]['className']} and {class_name}"
            )
        found[endpoint] = facts
    return found


def _load_resources(modules: dict[str, ast.Module]) -> list[dict[str, Any]]:
    """Build the npm resource list, contracts first and Python second.

    This used to iterate `DbResource` subclasses and let a contract correct the
    facts it owned, which meant a contract could never do more than annotate
    something Python had already declared.  It now iterates contracts that carry
    a `surface` block and takes the endpoint's whole npm identity from there,
    falling back to the Python class only for endpoints no contract covers.

    Python has not stopped mattering, but it is no longer imported: the class
    facts come from `_static_resource_classes`, which reads the same source tree
    the payload-type and operation readers already parse.

    The list itself is the union of both. It used to be the Python classes with
    contracts laid over them, so a contracted endpoint whose class was deleted
    would have vanished from npm. `pythonModule` is kept in the manifest where
    a class exists, as a record, and nothing is placed by it any more.
    """

    python_classes = _static_resource_classes(modules)

    coverage = json.loads((ROOT / "docs" / "coverage.json").read_text(encoding="utf-8"))
    coverage_by_endpoint: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in coverage["endpoints"]:
        coverage_by_endpoint[entry["endpoint"]].append(entry)

    payload_defaults = _contract_payload_defaults()
    reject_rules = _contract_reject_rules()
    surfaces = _contract_resource_surfaces()
    # A contract carries a resource on its own only when its surface names it;
    # the rest of its surface still needs the Python class to say what it is.
    endpoints = set(python_classes) | {
        endpoint for endpoint, surface in surfaces.items() if "className" in surface
    }

    resources: list[dict[str, Any]] = []
    from_contract = 0
    for endpoint in sorted(endpoints):
        fallback = python_classes.get(endpoint)
        manual = [
            {
                "name": match.get("name"),
                "chapterFile": match.get("chapter_file"),
                "status": match.get("status"),
            }
            for match in coverage_by_endpoint.get(endpoint, [])
        ]
        surface = surfaces.get(endpoint)
        if surface is not None:
            if fallback is not None:
                # The chapter comparison reads the ledger entry, so it has to
                # see one: the fallback dict is class facts only.
                mismatches = _contract_resource_mismatches({**fallback, "manual": manual}, surface)
                if mismatches:
                    raise ValueError(
                        f"{endpoint}: contract resource shadow differs from the SDK: "
                        + "; ".join(mismatches)
                    )
            from_contract += 1

        identity = _resource_identity(surface, fallback)
        resource = {
            "className": identity["className"],
            "exportName": identity["exportName"],
            "endpoint": endpoint,
            "name": identity["name"],
            "products": identity["products"],
            "methods": identity["methods"],
            # A record of where the Python class lives, for a resource that has
            # one. No npm output is placed by it: see `_path_namespace`.
            **({"pythonModule": fallback["pythonModule"]} if fallback else {}),
            "modulePath": identity["modulePath"],
            # Present only for endpoints with a contract rule; see
            # _contract_payload_defaults().
            **(
                {"payloadDefaults": payload_defaults[endpoint]}
                if endpoint in payload_defaults
                else {}
            ),
            **reject_rules.get(endpoint, {}),
            "manual": manual,
        }
        if surface is not None:
            # Keep the coverage ledger's richer manual entry in the committed
            # manifest. Runtime npm metadata reads this contract-owned chapter.
            resource["contractManualChapter"] = surface["manualChapter"]
        resources.append(resource)

    _RESOURCE_SOURCE_COUNTS["contract"] = from_contract
    _RESOURCE_SOURCE_COUNTS["python"] = len(resources) - from_contract
    return sorted(resources, key=lambda item: (item["modulePath"], item["className"], item["endpoint"]))


def _render_tree(resources: list[dict[str, Any]]) -> str:
    tree: dict[str, Any] = {}
    for resource in resources:
        node = tree
        for part in resource["modulePath"]:
            node = node.setdefault(part, {})
        name = resource["exportName"]
        if name in node:
            raise ValueError(f"Duplicate TypeScript resource name at {resource['modulePath']}: {name}")
        node[name] = resource

    def render(node: dict[str, Any], indent: int) -> list[str]:
        pad = "  " * indent
        lines = ["{"]
        for key, value in sorted(node.items()):
            if isinstance(value, dict) and "endpoint" not in value:
                nested = render(value, indent + 1)
                lines.append(f"{pad}  {key}: {nested[0]}")
                lines.extend(nested[1:-1])
                lines.append(f"{pad}  }},")
            else:
                metadata = {
                    key: value[key]
                    for key in ("className", "endpoint", "name", "products", "methods")
                }
                # Deliberately not pythonModule. The npm package used to ship
                # "midas_nx.db.static_loads" to JavaScript users, which said
                # nothing they could act on and quietly advertised that one
                # language was generated from the other. The manual chapter is
                # the language-neutral answer to the same question - where is
                # this endpoint documented.
                chapter = value.get("contractManualChapter") or next(
                    (m.get("chapterFile") for m in value.get("manual", []) if m.get("chapterFile")),
                    None,
                )
                if chapter:
                    metadata["manualChapter"] = chapter
                # Contract-derived runtime behaviour, listed in one place: a
                # rule that reaches the manifest and not this dict would be a
                # rule the npm package documents and never runs.
                for behaviour in _RUNTIME_BEHAVIOUR_KEYS:
                    if behaviour in value:
                        metadata[behaviour] = value[behaviour]
                encoded = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
                payload = value.get("payloadType", "JsonObject")
                lines.append(f"{pad}  {key}: defineDbResource<{payload}>({encoded}),")
        lines.append(f"{pad}}}")
        return lines

    return "\n".join(render(tree, 0))


def _constant_evaluator(tree: ast.Module):
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
        value = evaluate(node.value)
        if value is None:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                constants[target.id] = value
    return evaluate


def _names_an_export(surface: Any) -> bool:
    """Whether an operation `surface` publishes a generated npm operation.

    One without `exportName` only names types. /post/TABLE's POST is the case:
    its npm export, `post.getTable`, is written by hand, but the objects in its
    request - `UNIT`, `STYLES` - are published types the contract should own.
    """
    return isinstance(surface, dict) and "exportName" in surface


def _contract_operation_surfaces() -> dict[tuple[str, str], dict[str, Any]]:
    """Return {(endpoint, method): surface} for every contracted operation.

    The top-level `surface` block answers "what do the packages call this
    resource"; a function endpoint publishes one export per method instead, so
    the same question is asked of each operation. /ope/STORY_PARAM is the case
    that forces it: one endpoint, a GET export and a POST export, different
    names and different arguments.
    """
    contract_dir = ROOT / "contracts" / "endpoints"
    if not contract_dir.is_dir():
        return {}
    import yaml  # noqa: PLC0415

    surfaces: dict[tuple[str, str], dict[str, Any]] = {}
    for path in sorted(contract_dir.glob("*.yaml")):
        contract = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(contract, dict):
            continue
        endpoint = contract.get("endpoint")
        for operation in contract.get("operations") or []:
            surface = operation.get("surface")
            if endpoint and _names_an_export(surface):
                surfaces[(endpoint, operation.get("method", ""))] = surface
    return surfaces


def _operation_surface_argument(surface: dict[str, Any]) -> str:
    """Render a contracted operation's argument type the way the AST renders it.

    The namespace is derived from `modulePath` rather than stored, because the
    two cannot disagree: the generator builds both from the same module parts.
    """
    names = surface.get("argumentTypeName")
    if not names:
        return "JsonObject"
    if isinstance(names, str):
        names = [names]
    namespace = "".join(part[:1].upper() + part[1:] for part in surface["modulePath"])
    return " | ".join(f"Types.{namespace}Types.{name}" for name in names)


def _operation_specs(
    modules: dict[str, ast.Module],
    type_keys: set[tuple[str, str]],
    products_by_endpoint: dict[str, list[str]],
) -> list[dict[str, Any]]:
    contract_surfaces = _contract_operation_surfaces()
    operations: list[dict[str, Any]] = []
    for module, tree in sorted(modules.items()):
        if module == "midas_nx.doc" or module.endswith(".post.base"):
            continue
        imports = _import_map(module, tree)
        local_types = {name for owner, name in type_keys if owner == module}
        evaluate = _constant_evaluator(tree)
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
                continue
            call: ast.Call | None = None
            method = ""
            for candidate in ast.walk(node):
                if not isinstance(candidate, ast.Call):
                    continue
                called = ast.unparse(candidate.func).split(".")[-1]
                if called in {"_post", "post_argument"}:
                    call, method = candidate, "POST"
                    break
                if called in {"_get", "get_result"}:
                    call, method = candidate, "GET"
                    break
            if call is None or not call.args:
                continue
            endpoint = evaluate(call.args[0])
            if not isinstance(endpoint, str) or not endpoint.startswith("/"):
                continue
            products = products_by_endpoint.get(endpoint)
            if products is None:
                raise RuntimeError(
                    f"Operation {module}.{node.name} ({endpoint}) has no products in docs/coverage.json"
                )
            argument = next((arg for arg in node.args.args if arg.arg == "argument"), None)
            argument_type = "JsonObject"
            if argument is not None and argument.annotation is not None:
                rendered = _type_expression(
                    argument.annotation,
                    module=module,
                    local_types=local_types,
                    imports=imports,
                    all_types=type_keys,
                )
                if rendered not in {"unknown", "JsonObject"}:
                    for local_name in sorted(local_types, key=len, reverse=True):
                        rendered = re.sub(
                            rf"(?<![.A-Za-z0-9_]){re.escape(local_name)}\b",
                            f"Types.{_namespace(module)}.{local_name}",
                            rendered,
                        )
                    rendered = re.sub(
                        r"(?<![.A-Za-z0-9_])(\w+Types)\.", r"Types.\1.", rendered
                    )
                    argument_type = rendered
            spec = {
                "exportName": _camel(node.name),
                "endpoint": endpoint,
                "method": method,
                "products": products,
                "pythonFunction": node.name,
                "pythonModule": module,
                "modulePath": _module_parts(module),
                "argumentType": argument_type,
                "noArgument": method == "POST" and argument is None,
                "documentation": ast.get_docstring(node) or "",
            }
            surface = contract_surfaces.get((endpoint, method))
            if surface is not None:
                contracted = {
                    "exportName": surface["exportName"],
                    "modulePath": list(surface["modulePath"]),
                    "argumentType": _operation_surface_argument(surface),
                    "noArgument": not surface.get("takesArgument", True),
                }
                disagreements = [
                    f"{key}: contract says {value!r}, {module}.{node.name} says {spec[key]!r}"
                    for key, value in contracted.items()
                    if spec[key] != value
                ]
                if disagreements:
                    raise RuntimeError(
                        f"Contracted operation surface for {endpoint} {method} "
                        f"disagrees with the Python function it is generated "
                        f"beside: " + "; ".join(disagreements)
                    )
                spec.update(contracted)
                spec["contractedSurface"] = True
            operations.append(spec)
    return operations


def _contract_operation_specs() -> list[dict[str, Any]]:
    """Every npm operation, read from the contracts alone.

    Until 2026-09-21 the operations were *found* by walking the Python
    modules for functions that call `_post`/`_get`, and a contract could only
    rename what that walk turned up; products came from `docs/coverage.json`
    and the JSDoc from the Python docstring. Every one of the 70 now has an
    operation `surface` stating its export name, place, argument type and
    documentation, so the contract is the list. `_operation_specs` survives
    as the Python half of a parity test, not as an input.
    """
    contract_dir = ROOT / "contracts" / "endpoints"
    if not contract_dir.is_dir():
        return []
    import yaml  # noqa: PLC0415

    operations: list[dict[str, Any]] = []
    for path in sorted(contract_dir.glob("*.yaml")):
        contract = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(contract, dict):
            continue
        for operation in contract.get("operations") or []:
            surface = operation.get("surface")
            if not _names_an_export(surface):
                continue
            method = operation.get("method", "")
            operations.append(
                {
                    "exportName": surface["exportName"],
                    "endpoint": contract["endpoint"],
                    "method": method,
                    "products": sorted(contract["products"]),
                    "modulePath": list(surface["modulePath"]),
                    "argumentType": _operation_surface_argument(surface),
                    "noArgument": method == "POST" and not surface.get("takesArgument", True),
                    "documentation": surface.get("documentation", ""),
                    "contractedSurface": True,
                }
            )
    return operations


def _render_operations(operations: list[dict[str, Any]]) -> str:
    tree: dict[str, Any] = {}
    for operation in operations:
        node = tree
        for part in operation["modulePath"]:
            node = node.setdefault(part, {})
        node[operation["exportName"]] = operation

    def render(node: dict[str, Any], indent: int) -> list[str]:
        pad = "  " * indent
        lines = ["{"]
        for key, value in sorted(node.items()):
            if isinstance(value, dict) and "endpoint" not in value:
                nested = render(value, indent + 1)
                lines.append(f"{pad}  {key}: {nested[0]}")
                lines.extend(nested[1:-1])
                lines.append(f"{pad}  }},")
                continue
            metadata = json.dumps(
                {field: value[field] for field in ("endpoint", "method", "products")},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            if value["method"] == "GET":
                expression = f"defineGetOperation({metadata})"
            elif value["noArgument"]:
                expression = f"defineEmptyPostOperation({metadata})"
            else:
                expression = f"definePostOperation<{value['argumentType']}>({metadata})"
            lines.extend(_jsdoc(value["documentation"], indent + 1))
            lines.append(f"{pad}  {key}: {expression},")
        lines.append(f"{pad}}}")
        return lines

    return "\n".join(render(tree, 0))


def _table_specs(modules: dict[str, ast.Module]) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for module, tree in sorted(modules.items()):
        if not module.startswith("midas_nx.post.") or module.endswith(".base"):
            continue
        evaluate = _constant_evaluator(tree)
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
                continue
            for candidate in ast.walk(node):
                if not isinstance(candidate, ast.Call) or not candidate.args:
                    continue
                called = ast.unparse(candidate.func).split(".")[-1]
                if called not in {"get_table", "_get_design_forces_table"}:
                    continue
                table_type = evaluate(candidate.args[0])
                factory = "fixed"
                if table_type is None and isinstance(candidate.args[0], ast.Name):
                    parameter_name = candidate.args[0].id
                    positional = node.args.args
                    defaults = [None] * (len(positional) - len(node.args.defaults)) + list(node.args.defaults)
                    default_node = next(
                        (default for parameter, default in zip(positional, defaults) if parameter.arg == parameter_name),
                        None,
                    )
                    table_type = evaluate(default_node) if default_node is not None else None
                    factory = "variable"
                elif table_type is None and isinstance(candidate.args[0], ast.JoinedStr):
                    values = candidate.args[0].values
                    if (
                        len(values) == 2
                        and isinstance(values[0], ast.Constant)
                        and isinstance(values[0].value, str)
                        and isinstance(values[1], ast.FormattedValue)
                    ):
                        table_type = values[0].value
                        factory = "directional"
                if table_type is not None:
                    option_names = {
                        _TABLE_OPTION_NAMES[parameter.arg]
                        for parameter in node.args.args + node.args.kwonlyargs
                        if parameter.arg in _TABLE_OPTION_NAMES
                    }
                    tables.append(
                        {
                            "exportName": _camel(node.name),
                            "tableType": table_type,
                            "factory": factory,
                            "pythonFunction": node.name,
                            "pythonModule": module,
                            "modulePath": _module_parts(module)[1:],
                            "optionNames": sorted(option_names),
                            "documentation": ast.get_docstring(node) or "",
                        }
                    )
                break
    return tables


def _contract_table_specs() -> list[dict[str, Any]]:
    """Every npm table wrapper, read from `contracts/tables/*.yaml` alone.

    The same move `_contract_operation_specs` makes: the wrappers used to be
    discovered by walking the Python `post` modules, and each table contract
    now states its wrapper's name, place, default TABLE_TYPE, kind and options
    in `surface`. `_table_specs` is kept as the Python half of a parity test.
    """
    contract_dir = ROOT / "contracts" / "tables"
    if not contract_dir.is_dir():
        return []
    import yaml  # noqa: PLC0415

    tables: list[dict[str, Any]] = []
    for path in sorted(contract_dir.glob("*.yaml")):
        contract = yaml.safe_load(path.read_text(encoding="utf-8"))
        surface = (contract or {}).get("surface")
        if not isinstance(surface, dict):
            continue
        tables.append(
            {
                "exportName": surface["exportName"],
                "tableType": surface["tableType"],
                "factory": surface["factory"],
                "modulePath": list(surface["modulePath"]),
                "optionNames": sorted(surface["optionNames"]),
                "documentation": surface.get("documentation", ""),
            }
        )
    return tables


def _render_table_types() -> list[str]:
    """Emit every contracted TABLE_TYPE as a named constant.

    89 result tables share one route, selected by a `TABLE_TYPE` string. Both
    SDKs could always *reach* any of them by passing the raw string, but the
    Python package names each value (`TABLE_TYPE_REACTION_LOCAL`) while the npm
    package named only whichever one a wrapper defaulted to - so a variant like
    `REACTIONL` existed for anyone who already knew it existed, and for nobody
    else. Names come from `contracts/tables/*.yaml`, the same place both
    languages now take them from.
    """
    contract_dir = ROOT / "contracts" / "tables"
    if not contract_dir.is_dir():
        return []
    try:
        import yaml  # noqa: PLC0415
    except ImportError:  # pragma: no cover - dev dependency
        raise SystemExit(
            'contracts/ is present but PyYAML is not installed. Run: pip install -e ".[dev]"'
        ) from None

    entries: list[tuple[str, list[tuple[str, str, str]]]] = []
    for path in sorted(contract_dir.glob("*.yaml")):
        contract = yaml.safe_load(path.read_text(encoding="utf-8"))
        variants = [
            (_camel(v.get("description") or v["value"]), v["value"], v.get("description", ""))
            for v in contract.get("tableTypes", [])
        ]
        if variants:
            entries.append((_camel(contract["name"]), variants))
    if not entries:
        return []

    lines = [
        "/**",
        " * TABLE_TYPE values, from contracts/tables/*.yaml.",
        " *",
        " * Pass one as `tableType` to the matching table wrapper to select a variant",
        " * other than its default.",
        " */",
        "export const tableTypes = {",
    ]
    for name, variants in entries:
        lines.append(f"  {name}: {{")
        for key, value, description in variants:
            if description:
                lines.append(f"    /** {description} */")
            lines.append(f'    {key}: "{value}",')
        lines.append("  },")
    lines += ["} as const;", ""]
    return lines


def _render_tables(tables: list[dict[str, Any]]) -> str:
    tree: dict[str, Any] = {}
    for table in tables:
        node = tree
        for part in table["modulePath"]:
            node = node.setdefault(part, {})
        node[table["exportName"]] = table

    def render(node: dict[str, Any], indent: int) -> list[str]:
        pad = "  " * indent
        lines = ["{"]
        for key, value in sorted(node.items()):
            if isinstance(value, dict) and "tableType" not in value:
                nested = render(value, indent + 1)
                lines.append(f"{pad}  {key}: {nested[0]}")
                lines.extend(nested[1:-1])
                lines.append(f"{pad}  }},")
            else:
                factory = {
                    "fixed": "defineTable",
                    "variable": "defineVariableTable",
                    "directional": "defineDirectionalTable",
                }[value["factory"]]
                option_names = " | ".join(json.dumps(name) for name in value["optionNames"])
                option_type = f"Pick<TableOptions, {option_names}>" if option_names else "Record<never, never>"
                lines.extend(_jsdoc(value["documentation"], indent + 1))
                lines.append(
                    f"{pad}  {key}: {factory}<{option_type}>({json.dumps(value['tableType'])}),"
                )
        lines.append(f"{pad}}}")
        return lines

    return "\n".join(render(tree, 0))


_SHARED_PAYLOADS: dict[tuple[str, str], str] = {
    ("midas_nx.db.load_combinations", "LoadCombinationGeneral"): "LoadCombinationPayload",
    ("midas_nx.db.load_combinations", "LoadCombinationConcrete"): "LoadCombinationConcretePayload",
    ("midas_nx.db.load_combinations", "LoadCombinationSteel"): "LoadCombinationPayload",
    ("midas_nx.db.load_combinations", "LoadCombinationSRC"): "LoadCombinationPayload",
    ("midas_nx.db.load_combinations", "LoadCombinationCompositeSteelGirder"): "LoadCombinationPayload",
    ("midas_nx.db.load_combinations", "LoadCombinationSeismic"): "LoadCombinationPayload",
    ("midas_nx.db.moving_loads", "TrafficLineLanes"): "TrafficLineLanePayload",
    ("midas_nx.db.moving_loads", "TrafficSurfaceLanes"): "TrafficSurfaceLanePayload",
    ("midas_nx.db.moving_loads", "Vehicles"): "VehiclePayload",
    ("midas_nx.db.moving_loads", "VehiclesTransverse"): "VehicleTransversePayload",
    ("midas_nx.db.moving_loads", "ConcurrentReactionGroup"): "StructureGroupNamesPayload",
    ("midas_nx.db.moving_loads", "ConcurrentJointForceGroup"): "StructureGroupNamesPayload",
    ("midas_nx.db.moving_loads", "VehicleClasses"): "VehicleClassPayload",
    ("midas_nx.db.moving_loads", "RailwayDynamicFactorByElement"): "RailwayDynamicFactorPayload",
    ("midas_nx.design.steel_kds", "CombinedRatioCalculationMethodForCircularSection"): "CombinedRatioCalculationMethodPayload",
    ("midas_nx.db.properties.hinge", "InelasticHingePropertyHyperSBeam"): "InelasticHingePropertyHyperSPayload",
    ("midas_nx.db.properties.hinge", "InelasticHingePropertyHyperSTruss"): "InelasticHingePropertyHyperSPayload",
    ("midas_nx.db.properties.hinge", "InelasticHingePropertyHyperSGeneralLink"): "InelasticHingePropertyHyperSPayload",
    ("midas_nx.db.properties.hinge", "InelasticHingePropertyHyperSPss"): "InelasticHingePropertyHyperSPayload",
}


def _attach_python_payload_type(
    resource: dict[str, Any], type_keys: set[tuple[str, str]]
) -> None:
    """Name a payload the old way, for a resource whose contract names none.

    Three resources (the IEHG trio, which cannot be contracted) and one
    contract with no `payloadTypeName` still come here.
    """
    module = resource.get("pythonModule")
    if module is None:
        resource["payloadType"] = "JsonObject"
        return
    candidate = resource["className"] + "Payload"
    if (module, candidate) not in type_keys:
        candidate = _SHARED_PAYLOADS.get((module, resource["className"]), "")
    if candidate and (module, candidate) in type_keys:
        resource["payloadTypeName"] = candidate
        resource["payloadType"] = f"Types.{_namespace(module)}.{candidate}"
    else:
        resource["payloadType"] = "JsonObject"


def _bind_payload_types(
    resources: list[dict[str, Any]],
    contracts: dict[str, dict[str, Any]],
    type_keys: set[tuple[str, str]],
) -> dict[tuple[str, str], dict[str, Any]]:
    """Name every resource's npm payload, and return the contract-built ones.

    Returns ``{(namespace, name): contract}``. The name is the contract's
    `surface.payloadTypeName` and the namespace follows its `modulePath`, so a
    contracted payload is placed without asking where a Python TypedDict lives.

    This replaced a pass that found the name through the Python class and then
    renamed it (`...ByElementPayload`) when one legacy TypedDict served several
    endpoints whose contracts differ. Every contract records its final name
    now, so two endpoints naming one type must simply agree on its shape; if
    they do not, one published type cannot follow both and generation stops.

    A contract that declares `unmergedTables` still names its payload, but the
    body stays on Python, so a Python class has to exist in that slot.
    """

    surfaces = _contract_surface_blocks()
    python_slots = {(_namespace(module), name) for module, name in type_keys}
    bound: dict[tuple[str, str], dict[str, Any]] = {}
    origin: dict[tuple[str, str], str] = {}
    for resource in resources:
        endpoint = resource["endpoint"]
        name = surfaces.get(endpoint, {}).get("payloadTypeName")
        if name is None:
            _attach_python_payload_type(resource, type_keys)
            continue
        namespace = _path_namespace(resource["modulePath"])
        resource["payloadTypeName"] = name
        resource["payloadType"] = f"Types.{namespace}.{name}"
        key = (namespace, name)
        contract = contracts.get(endpoint)
        if contract is None:
            if key not in python_slots:
                raise ValueError(
                    f"{endpoint}: payload {namespace}.{name} is not built from the "
                    "contract (unmergedTables) and no Python TypedDict fills that slot"
                )
            continue
        if key in bound and bound[key] != contract:
            raise ValueError(
                f"{namespace}.{name} is the payload of {origin[key]} and {endpoint}, "
                "whose contracts give it different shapes"
            )
        bound[key] = contract
        origin.setdefault(key, endpoint)
    return bound


_STRUCTURAL_KEYS = (
    "key", "type", "requirement", "enum", "items", "appliesWhen", "products",
)


def _tuple_length(field: dict[str, Any]) -> int | None:
    """The array bound a caller is held to: a length only when it is exact.

    `_array_type` renders `minItems`/`maxItems` as a tuple when the two agree
    and as a plain `Array<...>` otherwise, so an unequal bound is documentation
    like a description is. /DESIGN/SRC/AIK-SRC2K's CC-TABLE gives SECTIONS
    `minItems: 1` and BC-TABLE does not; both publish `Array<number>`, and
    comparing the raw bound kept SrcMemberCheckTableArgument on Python until
    2026-09-22 over a difference no caller could see.
    """
    minimum = field.get("minItems")
    return minimum if isinstance(minimum, int) and minimum == field.get("maxItems") else None


def _structure(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A field tree with the prose removed: what a TypeScript caller is held to.

    Two declarations of one published nested type are compared on this, not on
    the rendered text, because descriptions legitimately differ by use - a
    ``BAR_SECTOR_I`` and a ``BAR_SECTOR_J`` say which end they are.
    """
    # Member order is not part of a TypeScript type: /db/POGD lists INITLOAD's
    # SF last and /db/THGC-M1 lists it second, and that is the same object.
    return sorted(
        (
            {key: field.get(key) for key in _STRUCTURAL_KEYS}
            | {"tupleLength": _tuple_length(field)}
            | {"properties": _structure(field.get("properties") or [])}
            for field in fields
        ),
        key=lambda field: str(field.get("key")),
    )


def _relative_conditions(fields: list[dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
    """Re-root `appliesWhen` paths inside a nested type at that type.

    A contract states a condition from its own root - `PART_A.INPUT_METHOD`.
    Published as `HaunchPartSelector`, which `PART_A`, `PART_B` and `PART_C`
    all are, that path is wrong for two of the three and made the three look
    like different shapes. A condition on a field outside the subtree keeps
    its full path; it genuinely points elsewhere.
    """

    def rewrite(node: Any) -> Any:
        if isinstance(node, list):
            return [rewrite(item) for item in node]
        if not isinstance(node, dict):
            return node
        out = {}
        for key, value in node.items():
            if key == "appliesWhen" and isinstance(value, list):
                out[key] = [
                    {**entry, "path": entry["path"].removeprefix(prefix)}
                    if isinstance(entry, dict) and entry.get("path", "").startswith(prefix)
                    else entry
                    for entry in value
                ]
            else:
                out[key] = rewrite(value)
        return out

    return rewrite(fields)


def _nested_fingerprint(pseudo: dict[str, Any]) -> str:
    """What two declarations of one nested type must agree on."""
    return json.dumps(
        {
            "fields": _structure(pseudo["fields"]),
            "variants": [
                {"when": variant["when"], "fields": _structure(variant["fields"])}
                for variant in pseudo["variants"]
            ],
        },
        sort_keys=True,
    )


def _branch_owned_subtree(
    source: str,
    entry: dict[str, Any],
    fields: list[dict[str, Any]],
    variants: list[dict[str, Any]],
    where: str,
) -> list[dict[str, Any]]:
    """The members of an object that only some branches declare.

    `/db/NLCT`'s `NEWTON_ITEMS` exists only when `ITERATION_METHOD` is
    `"NEWTON"`, so it is a field of that variant, not of the payload's base -
    and a lookup in the base finds nothing. The object's shape is still one
    thing, stated once, so it can be published under one name.

    It cannot be when two branches declare the field differently; that is the
    `/db/SECT` `SECT_BEFORE` case, and it raises. Nor when the base declares
    the field too and a branch redeclares it, which the caller already refuses.
    """
    branch = entry.get("branch")
    found = []
    for variant in variants:
        if branch is not None and variant["when"] != branch:
            continue
        attach = _variant_attach_key(fields, variant)
        if attach is None:
            relative = where
        elif where.startswith(attach + "."):
            relative = where[len(attach) + 1:]
        else:
            continue
        base_level = _attach_base(fields, attach) if attach else fields
        if branch is None and any(field["key"] == relative.split(".")[0] for field in base_level):
            # Declared in the base as well: a redeclaration, not a branch-only
            # object - unless the entry names which branch's version it is.
            return []
        members = _attach_base(variant["fields"], relative)
        if members:
            found.append(members)
    shapes = {json.dumps(_structure(members), sort_keys=True) for members in found}
    if len(shapes) > 1:
        raise ValueError(
            f"{source}: surface.nestedTypes names {entry['name']} at {entry['path']!r}, "
            "which several branches declare with different shapes"
        )
    return found[0] if found else []


def _contract_nested_types() -> dict[tuple[str, str], dict[str, Any]]:
    """Return {(namespace, name): pseudo-contract} for each declared nested type.

    A payload's root has had a contract-owned name since 2026-09-02
    (`surface.payloadTypeName`), but the objects *inside* it did not: the root
    was emitted from the contract with every nested object inlined, while the
    named interfaces for those same objects - `DbBoundaryTypes.BeamEndOffsetItem`
    for `/db/OFFS`'s `ITEMS` element - kept being read out of the Python
    TypedDicts, with Python's field list and Python's `total=False`
    requiredness. The same object was published twice with two shapes.

    `surface.nestedTypes` records, per contract field path, the name and
    namespace a type is **already published under** (seeded from the committed
    output, so recording one renames nothing). This builds each one's body
    from the contract subtree at that path - the element type, for an array -
    together with any variant union that attaches there or below.

    A type several contracts declare must come out the same from each of them
    once prose is set aside; one that does not is a real disagreement between
    contracts, and picking one would publish a guess, so it raises.
    """

    contract_dir = ROOT / "contracts" / "endpoints"
    if not contract_dir.is_dir():
        return {}
    import yaml  # noqa: PLC0415

    records = _contract_payload_fields()
    found: dict[tuple[str, str], dict[str, Any]] = {}
    origin: dict[tuple[str, str], str] = {}
    jobs: list[tuple[Any, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]] = []
    for path in sorted(contract_dir.glob("*.yaml")):
        contract = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(contract, dict):
            continue
        unmerged = _admits_incomplete_fields(contract)
        declared = (contract.get("surface") or {}).get("nestedTypes") or []
        if declared:
            record = records.get(contract.get("endpoint", ""))
            if record is None:
                raise ValueError(
                    f"{path.name}: declares surface.nestedTypes but its payload is not "
                    "generated from the contract (unmergedTables, or not a resource), "
                    "so there is no contract subtree to build them from"
                )
            jobs.append((path, declared, record["fields"], record["variants"]))
        # An operation's argument is built from the same field list with the
        # "Argument" wrapper removed (`_contract_argument_types`), so its
        # nested objects are declared on the operation that owns the argument.
        for operation in contract.get("operations") or []:
            declared = (operation.get("surface") or {}).get("nestedTypes") or []
            if not declared:
                continue
            if unmerged or not contract.get("fields"):
                raise ValueError(
                    f"{path.name}: {operation.get('method')} declares nestedTypes but "
                    "its argument is not generated from the contract"
                )
            fields, variants = _strip_assign_envelope(contract, "Argument")
            jobs.append((path, declared, fields, variants))
    # A result table's own request fields - the ADDITIONAL objects the story
    # tables take, NODE_FLAG on the plate and solid tables - live in its table
    # contract under `requestFields.additional`, not in the shared /post/TABLE
    # contract, because each is honoured by some tables only.
    table_dir = ROOT / "contracts" / "tables"
    for path in sorted(table_dir.glob("*.yaml")) if table_dir.is_dir() else []:
        table = yaml.safe_load(path.read_text(encoding="utf-8"))
        declared = ((table or {}).get("surface") or {}).get("nestedTypes") or []
        if declared:
            fields = (table.get("requestFields") or {}).get("additional") or []
            jobs.append((path, declared, fields, []))
    for path, declared, fields, variants in jobs:
        for entry in declared:
            where = entry["path"].removeprefix("Assign.")
            body = [] if entry.get("branch") else _attach_base(fields, where)
            branch_owned = False
            if entry.get("branch") and not any(v["when"] == entry["branch"] for v in variants):
                raise ValueError(
                    f"{path.name}: surface.nestedTypes names {entry['name']} for branch "
                    f"{entry['branch']}, which no variant's `when` matches"
                )
            if not body:
                body = _branch_owned_subtree(path.name, entry, fields, variants, where)
                branch_owned = bool(body)
            if not body:
                raise ValueError(
                    f"{path.name}: surface.nestedTypes names {entry['name']} at "
                    f"{entry['path']!r}, where the contract declares no object"
                )
            prefix = where + "."
            below = []
            for variant in variants:
                attach = _variant_attach_key(fields, variant)
                above = attach or ""
                if branch_owned:
                    # The object exists only inside branches, and those
                    # branches were already required to agree on it.
                    continue
                if above != where and (not above or where.startswith(above + ".")):
                    # A branch attached *above* this path that redeclares the
                    # field on the way to it decides the object's shape per
                    # branch: /db/SECT's SECT_BEFORE is re-declared by each
                    # SECTTYPE variant. There is then no single subtree to
                    # publish under one name.
                    step = where[len(above) + 1:] if above else where
                    if any(f.get("key") == step.split(".")[0] for f in variant["fields"]):
                        raise ValueError(
                            f"{path.name}: surface.nestedTypes names {entry['name']} at "
                            f"{entry['path']!r}, but a variant above it redeclares that "
                            "field, so its shape is not one subtree"
                        )
                if attach == where or (attach or "").startswith(prefix):
                    below.append({
                        **variant,
                        "when": [
                            {**condition, "path": condition["path"].removeprefix(prefix)}
                            for condition in variant["when"]
                        ],
                    })
            pseudo = {"fields": _relative_conditions(body, prefix), "variants": below}
            if path.parent.name == "tables":
                pseudo["source"] = "contracts/tables/"
            key = (entry["namespace"], entry["name"])
            if key in found:
                if _nested_fingerprint(found[key]) != _nested_fingerprint(pseudo):
                    raise ValueError(
                        f"{key[0]}.{key[1]} is declared by {origin[key]} and "
                        f"{path.name} with different shapes"
                    )
                continue
            found[key] = pseudo
            origin[key] = path.name
    return found


#: Operation argument types that stay on their Python TypedDict, each for a
#: recorded reason. Two kinds:
#:
#: ``divergent`` - a name several contracts share, whose contracts disagree.
#:   One published type cannot follow two field lists, and splitting it would
#:   add exports. `_contract_argument_types` fails if one stops disagreeing
#:   (the entry is stale) or if a disagreement appears that is not listed.
#: ``requiredness`` - the contract transcribes the manual faithfully, and the
#:   manual's "Required" is not what a caller must send. Publishing it would
#:   refuse calls the product accepts. Fixing one takes a permitted source for
#:   the real condition, not a guess.
_ARGUMENT_TYPES_LEFT_ON_PYTHON: dict[str, tuple[str, str]] = {
}


def _argument_part(
    fields: list[dict[str, Any]], when: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """One part of a union argument: the fields its discriminator value admits.

    `/ope/LCOM-SRC` takes a KDS 41 SRC:2022 body and an AIK-SRC2K one on the
    same route, told apart by `DGNCODE`. The contract states which fields apply
    to which value with `appliesWhen`; a field whose condition on that path
    excludes the value is not part of this part, a satisfied condition is
    dropped, and the discriminator itself narrows to the one value.
    """
    if not when:
        return fields
    path, value = when["path"], when["equals"]
    part: list[dict[str, Any]] = []
    for field in fields:
        conditions = field.get("appliesWhen") or []
        own = [c for c in conditions if c.get("path") == path]
        if any(
            value not in (c["in"] if "in" in c else [c.get("equals")]) for c in own
        ):
            continue
        field = dict(field)
        rest = [c for c in conditions if c.get("path") != path]
        if rest:
            field["appliesWhen"] = rest
        else:
            field.pop("appliesWhen", None)
        if field["key"] == path:
            field["enum"] = [value]
        part.append(field)
    return part


def _contract_argument_types() -> dict[tuple[str, str], dict[str, Any]]:
    """Return {(namespace, name): pseudo-contract} for each operation argument type.

    The generator had built every `/db/*` payload from its contract since the
    migration began, but an operation's argument - `/ope`, `/view` and the
    design-code `*-ANAL`/`*-TABLE`/`*-REPORT` calls - still came from the
    Python TypedDict, although the contract carried the same field list. The
    operation `surface` already names the type (`argumentTypeName`); this
    builds it from the contract's fields with the `"Argument"` wrapper row
    removed, because the npm operation adds that wrapper itself.

    Left on Python, on purpose: a contract declaring `unmergedTables`, for the
    reason payloads skip them, and any part of a **union** argument that the
    operation's `argumentParts` does not name - the list says which value of
    the discriminator each part is, and a part nobody named is not guessed.
    A name several contracts share (the RC check trio) must come out the same
    from each, prose aside, or generation fails.
    """
    contract_dir = ROOT / "contracts" / "endpoints"
    if not contract_dir.is_dir():
        return {}
    import yaml  # noqa: PLC0415

    found: dict[tuple[str, str], dict[str, Any]] = {}
    origin: dict[tuple[str, str], str] = {}
    diverged: set[str] = set()
    for path in sorted(contract_dir.glob("*.yaml")):
        contract = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(contract, dict) or not contract.get("fields"):
            continue
        if _admits_incomplete_fields(contract):
            continue
        for operation in contract.get("operations") or []:
            surface = operation.get("surface") or {}
            declared = surface.get("argumentTypeName")
            fields, variants = _strip_assign_envelope(contract, "Argument")
            if declared is None:
                parts = []
            elif isinstance(declared, str):
                parts = [(declared, fields)]
            else:
                # A union: only the parts `argumentParts` names come from here.
                parts = [
                    (part["name"], _argument_part(fields, part.get("when")))
                    for part in surface.get("argumentParts") or []
                    if part["name"] in (declared or [])
                ]
            if not parts:
                continue
            namespace = _path_namespace(surface["modulePath"])
            for name, part_fields in parts:
                if _ARGUMENT_TYPES_LEFT_ON_PYTHON.get(name, ("",))[0] == "requiredness":
                    continue
                pseudo = {"fields": part_fields, "variants": variants}
                key = (namespace, name)
                if key in found:
                    if _nested_fingerprint(found[key]) != _nested_fingerprint(pseudo):
                        if name not in _ARGUMENT_TYPES_LEFT_ON_PYTHON:
                            raise ValueError(
                                f"{namespace}.{name} is the argument of {origin[key]} and "
                                f"{path.name}, whose contracts give it different shapes"
                            )
                        diverged.add(name)
                    continue
                found[key] = pseudo
                origin[key] = path.name
    stale = sorted(
        name
        for name, (kind, _) in _ARGUMENT_TYPES_LEFT_ON_PYTHON.items()
        if kind == "divergent" and name not in diverged
    )
    if stale:
        raise ValueError(
            "listed in _ARGUMENT_TYPES_LEFT_ON_PYTHON but no longer diverging, so "
            f"they can come from the contract: {stale}"
        )
    return {key: value for key, value in found.items() if key[1] not in diverged}



def main() -> None:
    modules = _source_modules()
    resources = _load_resources(modules)
    resource_keys = {
        (item["pythonModule"], item["className"]) for item in resources if "pythonModule" in item
    }
    type_keys = _collect_type_classes(modules, resource_keys)
    coverage = json.loads((ROOT / "docs" / "coverage.json").read_text(encoding="utf-8"))
    operations = _contract_operation_specs()
    tables = _contract_table_specs()
    contract_types = _bind_payload_types(resources, _contract_payload_fields(), type_keys)
    for label, extra in (
        ("a nested type", _contract_nested_types()),
        ("an operation argument", _contract_argument_types()),
    ):
        clash = sorted(set(extra) & set(contract_types))
        if clash:
            raise ValueError(f"declared both as a payload and as {label}: {clash}")
        contract_types = {**contract_types, **extra}
    layout = _type_layout(modules, type_keys, contract_types)
    unplaced = sorted(
        resource["payloadType"]
        for resource in resources
        if resource["payloadType"] != "JsonObject"
        and resource["payloadTypeName"]
        not in layout.get(resource["payloadType"].split(".")[1], {})
    )
    if unplaced:
        raise ValueError(f"resource payload types that no declaration provides: {unplaced}")
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    TYPESCRIPT_SRC.joinpath("generated").mkdir(parents=True, exist_ok=True)

    manifest = {
        "$schema": "./typescript-resources.schema.json",
        "source": {
            "pythonPackage": "midas-nx",
            "coverageLedger": "docs/coverage.json",
        },
        "resourceCount": len(resources),
        # `contractManualChapter` is an internal shadow-run input. It affects
        # npm runtime metadata but is deliberately not a new manifest surface.
        "resources": [
            {key: value for key, value in resource.items() if key != "contractManualChapter"}
            for resource in resources
        ],
    }
    (SCHEMA_DIR / "typescript-resources.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    resource_endpoints = {item["endpoint"] for item in resources}
    operation_endpoints = {item["endpoint"] for item in operations}
    coverage_rows: list[dict[str, str]] = []
    missing: list[str] = []
    for entry in coverage["endpoints"]:
        endpoint = entry["endpoint"]
        canonical = (
            "/post/TABLE"
            if endpoint.startswith("/post/TABLE (") or endpoint in _POST_TABLE_LEDGER_ALIASES
            else endpoint
        )
        if canonical in resource_endpoints:
            surface = "resource"
        elif canonical in operation_endpoints:
            surface = "operation"
        elif canonical in _DOC_ENDPOINTS:
            surface = "doc"
        elif canonical in _DESIGN_TABLE_ENDPOINTS:
            surface = "designTable"
        elif canonical == "/post/TABLE":
            surface = "table"
        else:
            surface = "missing"
            missing.append(endpoint)
        coverage_rows.append({"endpoint": endpoint, "canonicalEndpoint": canonical, "surface": surface})
    if missing:
        raise RuntimeError(f"TypeScript SDK is missing coverage for: {', '.join(missing)}")
    coverage_manifest = {
        "source": "docs/coverage.json",
        "coverageRowCount": len(coverage_rows),
        "coveredRowCount": len(coverage_rows) - len(missing),
        "rows": coverage_rows,
    }
    (SCHEMA_DIR / "typescript-coverage.json").write_text(
        json.dumps(coverage_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    generated = "\n".join(
        [
            "// Generated by scripts/generate_typescript_sdk.py. Do not edit by hand.",
            'import { defineDbResource } from "../db-resource";',
            'import type { JsonObject } from "../types";',
            'import type * as Types from "./types";',
            "",
            f"export const resources = {_render_tree(resources)} as const;",
            "",
            f"export const resourceCount = {len(resources)} as const;",
            "",
        ]
    )
    (TYPESCRIPT_SRC / "generated" / "resources.ts").write_text(generated, encoding="utf-8")
    (TYPESCRIPT_SRC / "generated" / "types.ts").write_text(
        _render_types(modules, type_keys, contract_types), encoding="utf-8"
    )
    generated_operations = "\n".join(
        [
            "// Generated by scripts/generate_typescript_sdk.py. Do not edit by hand.",
            'import { defineEmptyPostOperation, defineGetOperation, definePostOperation } from "../operation";',
            'import type { JsonObject } from "../types";',
            'import type * as Types from "./types";',
            "",
            f"export const operations = {_render_operations(operations)} as const;",
            "",
            f"export const operationCount = {len(operations)} as const;",
            "",
        ]
    )
    (TYPESCRIPT_SRC / "generated" / "operations.ts").write_text(
        generated_operations, encoding="utf-8"
    )
    generated_tables = "\n".join(
        [
            "// Generated by scripts/generate_typescript_sdk.py. Do not edit by hand.",
            'import { defineDirectionalTable, defineTable, defineVariableTable } from "../post";',
            'import type { TableOptions } from "../post";',
            "",
            f"export const tables = {_render_tables(tables)} as const;",
            "",
            f"export const tableCount = {len(tables)} as const;",
            "",
            *_render_table_types(),
        ]
    )
    (TYPESCRIPT_SRC / "generated" / "tables.ts").write_text(
        generated_tables, encoding="utf-8"
    )
    contract_type_count = len(contract_types)
    payload_type_count = sum(len(names) for names in layout.values())
    print(
        f"Generated {len(resources)} TypeScript DB resources "
        f"({_RESOURCE_SOURCE_COUNTS['contract']} identified by a contract, "
        f"{_RESOURCE_SOURCE_COUNTS['python']} still by a Python class), "
        f"{len(operations)} operations and {len(tables)} table wrappers "
        f"(both read from contracts), "
        f"and {payload_type_count} payload types "
        f"({contract_type_count} of them from contracts, the rest still from Python)"
    )


if __name__ == "__main__":
    main()
