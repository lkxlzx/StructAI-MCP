"""The four MCP tools and their dispatch to the MIDAS client.

Tool surface is fixed at the four from mcp/03_TOOLS.md:
``midas_doc``, ``midas_db_query``, ``midas_db_assign``, ``midas_db_delete``.
Every MIDAS endpoint is reached through the registry, never through a URL the
model supplies.
"""
from __future__ import annotations

import json
import logging
import threading
from typing import Any, Callable

from .errors import InputError, ToolError
from .guards import Guards
from .knowledge import pitfalls_markdown, recipe_markdown, routing_markdown
from .midas_http import MidasClient
from .normalize import (classify_error, is_error_body, is_soft_empty,
                        normalize_success)
from .registry import Endpoint, Registry
from .results import modal_result, result_summary

log = logging.getLogger("midas_mcp.tools")

Deps = Callable[[], tuple[Guards, MidasClient, Registry]]


# --------------------------------------------------------------------------
# tool schemas (mirror mcp/03_TOOLS.md)
# --------------------------------------------------------------------------
def build_tools() -> list[dict]:
    return [
        {
            "name": "midas_doc",
            "description": "MIDAS project/document control: NEW/OPEN/CLOSE/SAVE/STAGAS/IMPORT/IMPORTMXT/EXPORT/EXPORTMXT/ANAL.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "enum": ["NEW", "OPEN", "CLOSE", "SAVE", "SAVEAS", "STAGAS",
                                 "IMPORT", "IMPORTMXT", "EXPORT", "EXPORTMXT", "ANAL"],
                    },
                    "argument": {"type": "object", "default": {}},
                },
                "required": ["command"],
            },
            "outputSchema": {"type": "object"},
            "annotations": {"readOnlyHint": False, "destructiveHint": False,
                            "idempotentHint": False},
        },
        {
            "name": "midas_db_query",
            "description": "Read MIDAS model data. Query by endpoint key (DB:NODE etc.); "
                           "optionally an item_id, a search string to discover endpoints, "
                           "or schema introspection.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "endpoint": {"type": "string"},
                    "item_id": {"type": ["string", "number"]},
                    "search": {"type": "string"},
                    "info": {"type": "boolean", "description": "inspect the endpoint schema via GET /info/db/<X>"},
                },
                "required": ["endpoint"],
            },
            "outputSchema": {"type": "object"},
            "annotations": {"readOnlyHint": True, "destructiveHint": False,
                            "idempotentHint": True, "openWorldHint": False},
        },
        {
            "name": "midas_db_assign",
            "description": "Create or update MIDAS data, or invoke a registered write/action endpoint.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "endpoint": {"type": "string"},
                    "mode": {"type": "string", "enum": ["create", "update"]},
                    "data": {"type": "object"},
                },
                "required": ["endpoint", "mode", "data"],
            },
            "outputSchema": {"type": "object"},
            "annotations": {"readOnlyHint": False, "destructiveHint": False,
                            "idempotentHint": False},
        },
        {
            "name": "midas_db_delete",
            "description": "Delete specific MIDAS data ids. An empty target_ids is refused; "
                           "it never means delete all.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "endpoint": {"type": "string"},
                    "target_ids": {"type": "array", "items": {"type": ["string", "number"]}},
                    "delete_all": {"type": "boolean", "default": False},
                },
                "required": ["endpoint", "target_ids"],
            },
            "outputSchema": {"type": "object"},
            "annotations": {"readOnlyHint": False, "destructiveHint": True,
                            "idempotentHint": False},
        },
    ]


# --------------------------------------------------------------------------
# tool callbacks (return an MCP result dict / raise ToolError)
# --------------------------------------------------------------------------
#: Doc commands that replace or drop the whole model, so every cached id
#: snapshot becomes wrong at once.  ``IMPORTMXT`` and ``CLOSE`` are symmetric
#: with ``IMPORT``: the registry marks both ``destructive``
#: (registry/registry.json) - an MXT import replaces the model and a close
#: drops it.  Neither could be exercised against a live MIDAS, so the evidence
#: is that flag plus the ``DOC:IMPORT`` symmetry.
_MODEL_REPLACING_DOC_COMMANDS = frozenset({"NEW", "IMPORT", "IMPORTMXT",
                                           "OPEN", "CLOSE"})

#: Endpoints whose successful write changes the *id set* of a family, mapped to
#: the families whose snapshot must then be dropped.  A ``DB:<X>`` endpoint
#: writes the ``<X>`` collection itself, which the fallback below covers.  The
#: two ``ope`` actions are the exception: they are not ``DB:`` endpoints yet
#: they mint nodes/elements - ``OPE:AUTOMESH`` ("Auto-Mesh Planar Area") and
#: ``OPE:DIVIDEELEM`` ("Divide Elements", both in registry/registry.json) - so
#: a pre-mesh ELEM snapshot would otherwise refuse a perfectly valid
#: "keys records on ELEM ids that do not exist: [...]" write.
_ENDPOINT_DROPS: dict[str, tuple[str, ...]] = {
    "OPE:AUTOMESH": ("NODE", "ELEM"),
    "OPE:DIVIDEELEM": ("NODE", "ELEM"),
}


def _dropped_families(key: str) -> tuple[str, ...]:
    """The families whose id snapshot a successful write to ``key`` drops."""
    explicit = _ENDPOINT_DROPS.get(key)
    if explicit is not None:
        return explicit
    if key.startswith("DB:"):
        return (key.split(":", 1)[-1],)
    return ()


def _drop_id_snapshot(ep: Endpoint) -> None:
    """Drop the cached id snapshots an endpoint's successful write invalidates.

    The snapshot exists so the crash guard does not re-read NODE/ELEM on every
    guarded write, but a write is exactly the moment it becomes wrong: the id
    that was just created (or just removed) is not in it, so the next ref-keyed
    write is refused with "keys records on NODE ids that do not exist" for a
    node that does exist.  ``DB:NODE`` therefore drops the ``NODE`` family, and
    the meshing actions drop both families.
    """
    families = _dropped_families(ep.key)
    if not families:
        return
    from .midas_http import invalidate_id_cache
    for family in families:
        invalidate_id_cache(family)


def tool_doc(args: dict, deps: Deps) -> dict:
    command = str(args.get("command", "")).upper()
    if command not in {"NEW", "OPEN", "CLOSE", "SAVE", "SAVEAS", "STAGAS",
                       "IMPORT", "IMPORTMXT", "EXPORT", "EXPORTMXT", "ANAL"}:
        raise InputError(f"unknown doc command {command!r}.")
    argument = args.get("argument", {})
    if argument is None:
        argument = {}

    guards, client, reg = deps()
    ep = reg.lookup(f"DOC:{command}")
    if ep is None:
        raise InputError(f"DOC:{command} is not a registered doc endpoint.")

    hint = guards.warn_saveas(command)
    method = "POST"
    # File-taking doc commands want a bare string Argument.  A model that
    # passes {"EXPORT_PATH": "..."} gets "path is wrong" back with HTTP 200,
    # so unwrap the common shapes instead of failing.
    if command in ("OPEN", "SAVEAS", "IMPORT", "IMPORTMXT", "EXPORT", "EXPORTMXT"):
        if isinstance(argument, dict):
            for key in ("EXPORT_PATH", "FILE_PATH", "EXPORT_FILE", "PATH", "path"):
                if isinstance(argument.get(key), str):
                    argument = argument[key]
                    break
            else:
                raise InputError(
                    f"DOC:{command} needs a file path. Pass argument as a plain "
                    f"string, or as {{\"EXPORT_PATH\": \"C:\\\\dir\\\\file.json\"}}.")
        if not isinstance(argument, str) or not argument.strip():
            raise InputError(f"DOC:{command} needs a non-empty file path string.")
        argument = argument.replace("/", "\\")
    body = {"Argument": argument}
    timeout = guards.cfg.timeouts.get("analysis" if command == "ANAL" else "assign", 60)
    resp = client.request(method, ep.uri, body, timeout_s=timeout, retryable=False)
    raw = resp.raw
    result = _finish(ep, method, resp.status, raw, resp.body)
    if result.get("ok") and command in _MODEL_REPLACING_DOC_COMMANDS:
        from .midas_http import invalidate_id_cache
        invalidate_id_cache()  # the whole model was replaced
    if hint and result.get("ok"):
        result["hint"] = hint
    if command == "ANAL":
        _annotate_analysis(ep, result, raw)
    return result


def _annotate_analysis(ep: Endpoint, result: dict, raw: str) -> None:
    """Interpret a ``DOC:ANAL`` reply, which is *not* a plain success/failure.

    Verified live on Gen NX 2027: with a forced displacement (``DB:SDSP``) in
    the model, ``POST /doc/ANAL`` answers **HTTP 400** carrying
    ``{"error":{"message":"[警告] 强制位移在 反应谱分析中设为零。"}}`` - and the
    analysis still runs.  ``POST /post/TABLE`` afterwards returns real
    ``DEAD(ST)`` and ``EQ_X(RS)`` rows, so the 400 is a *warning* about the
    response-spectrum run, not a rejection.

    Reporting that as a failure would be wrong twice over: it tells the caller
    no results exist when they do, and it invites a pointless retry.  The
    connector therefore marks it as a success-with-warning and tells the caller
    to confirm by reading a result table.
    """
    if result.get("ok"):
        result["note"] = ("analysis accepted; read results with midas_db_assign "
                          "on a POST:TABLE endpoint.")
        return
    if result.get("http_status") == 400 and _carries_warning(raw):
        result.update({
            "ok": True,
            "category": "OK_WITH_WARNING",
            "warning": _warning_text(raw),
            "note": ("MIDAS answered HTTP 400 with a [警告] warning, not a "
                     "rejection: the analysis runs anyway. Confirm by reading a "
                     "result table (e.g. POST:TABLE:DISPLACEMENTG with "
                     "'DEAD(ST)'); the response-spectrum cases may be zeroed "
                     "where a forced displacement is present."),
        })


def _carries_warning(raw: str) -> bool:
    """True when a body is MIDAS's ``[警告]`` warning rather than a rejection.

    The body is real UTF-8 (``[警告]``), but JSON may also escape it as
    ``\\u8b66\\u544a``, so both spellings are accepted.
    """
    return "[警告]" in raw or "\\u8b66\\u544a" in raw


def _warning_text(raw: str) -> str:
    try:
        parsed = json.loads(raw)
        msg = parsed.get("error", {}).get("message") or parsed.get("message")
        if isinstance(msg, str):
            return msg
    except ValueError:
        pass
    return raw.strip()[:200]


def tool_db_query(args: dict, deps: Deps) -> dict:
    guards, client, reg = deps()
    ep = guards.validate_endpoint(str(args.get("endpoint", "")))
    search = args.get("search")
    item_id = args.get("item_id")
    info = args.get("info", False)

    # discovery / schema introspection are read-only and don't hit the model
    if search:
        text = str(search)
        hits = reg.search(text)
        out = {"ok": True, "endpoint": ep.key, "method": "REGISTRY",
               "status": 200, "data": {"matches": hits, "count": len(hits)}}
        # A modal/eigen/buckling question is answered by a POST/TABLE reply
        # whose summary sits in SUB_TABLES, not by any NODE/ELEM table.  Say so
        # at the moment of the search rather than leaving it to be discovered.
        route = modal_question(text)
        if route:
            out["route"] = route
            out["hint"] = (
                f"modal/eigen questions are answered by {route}: query it with "
                f"midas_db_assign (mode='create') and read the parsed summary "
                f"from 'result_summary.modal_result'. The frequencies, periods, "
                f"participation masses and direction factors are in that reply's "
                f"SUB_TABLES, not in its top-level DATA.")
        return out
    if info:
        from .midas_http import MidasClient
        schema_client = MidasClient(guards.cfg)
        s_uri = f"/info/db/{ep.uri.rsplit('/', 1)[-1]}"
        s_resp = schema_client.request("GET", s_uri, retryable=True)
        if s_resp.ok_by_status and s_resp.body:
            return normalize_success(ep.key, "GET", s_resp.status, s_resp.raw,
                                     s_resp.body)
        return {"ok": False, "category": "SCHEMA",
                "message": "schema introspection returned nothing for " + ep.key,
                "endpoint": ep.key}

    path = ep.uri
    if item_id is not None:
        ids = guards.validate_ids(ep, [item_id])
        path = f"{ep.uri}/{ids[0]}"
    resp = client.request("GET", path, retryable=True,
                          timeout_s=guards.cfg.timeouts.get("query", 30))
    return _finish(ep, "GET", resp.status, resp.raw, resp.body)


# --------------------------------------------------------------------------
# result questions: route a natural-language ask to the right table
# --------------------------------------------------------------------------
#: Words a caller uses when it wants a modal/eigen summary.  Matching any of
#: these means the answer is in an EIGENVALUEMODE reply's SUB_TABLES, which is
#: the opposite of the trap this list exists to prevent: searching NODE/ELEM
#: result tables (or giving up because they are empty) finds nothing, while the
#: summary is one endpoint away.
MODAL_QUESTION_MARKERS = (
    "modal", "mode shape", "eigen", "eigenvalue", "frequency", "period",
    "natural period", "participation", "direction factor", "mass ratio",
    "自振周期", "模态", "振型", "频率", "周期", "参与质量", "质量参与",
    "方向因子", "特征值",
)

#: Words that mean the ask is about buckling rather than free vibration.
BUCKLING_QUESTION_MARKERS = (
    "buckling", "critical load", "load factor", "屈曲", "临界荷载", "稳定系数",
)


def modal_question(text: str) -> str | None:
    """The result endpoint a modal/eigen/buckling question should be asked of.

    Returns the registry key to query, or ``None`` when the question is not
    about modal results.  This is a routing helper for the model: it does not
    answer the question, it says where the answer lives.
    """
    lowered = (text or "").lower()
    if any(m in lowered for m in BUCKLING_QUESTION_MARKERS):
        return "POST:TABLE:BUCKLINGMODE"
    if any(m in lowered for m in MODAL_QUESTION_MARKERS):
        return "POST:TABLE:EIGENVALUEMODE"
    return None


def tool_db_assign(args: dict, deps: Deps) -> dict:
    guards, client, reg = deps()
    ep = guards.validate_endpoint(str(args.get("endpoint", "")))
    mode = str(args.get("mode", "create")).lower()
    if mode not in ("create", "update"):
        raise InputError("mode must be 'create' or 'update'.")
    data = args.get("data")
    if not isinstance(data, dict):
        raise InputError("data must be an object of records.")

    data = guards.strip_wrapper(data)
    data = guards.correct_payload(ep, mode, data)

    method = "PUT" if mode == "update" else "POST"
    if method not in ep.methods:
        raise InputError(f"{ep.key} does not accept {method} "
                         f"(methods: {', '.join(ep.methods)}).")

    if ep.wrapper.upper() == "ASSIGN":
        body = {"Assign": data}
    else:
        # action endpoints wrap arguments (no record keys)
        body = {"Argument": data}

    # crash guard: writing a ref-keyed record must reference existing ids
    guards.require_existing_refs(ep, data if ep.wrapper.upper() == "ASSIGN" else {})

    timeout = guards.cfg.timeouts.get("table" if ep.namespace == "post" else "assign", 60)
    if ep.key.startswith(("POST:", "DESIGN:")) and "ANAL" not in ep.key \
            and "CODE-ANAL" not in ep.key and "CODE-TABLE" not in ep.key:
        timeout = guards.cfg.timeouts.get("table", 180)
    resp = client.request(method, ep.uri, body, timeout_s=timeout, retryable=False)
    result = _finish(ep, method, resp.status, resp.raw, resp.body,
                     data_hint=data)
    # A write can succeed and still leave the model unsolvable.  The
    # construction-stage preflight is the one case worth surfacing here: the
    # failure only appears later, as an analysis error that names neither the
    # stage nor the missing boundary group.
    if result.get("ok"):
        _drop_id_snapshot(ep)
        hint = guards.stage_preflight(ep, data)
        if hint:
            result["warning"] = hint
    return result


def tool_db_delete(args: dict, deps: Deps) -> dict:
    guards, client, reg = deps()
    ep = guards.validate_endpoint(str(args.get("endpoint", "")))
    if "DELETE" not in ep.methods:
        raise InputError(f"{ep.key} does not support DELETE.")
    delete_all = bool(args.get("delete_all", False))
    target_ids = args.get("target_ids")
    guards.refuse_bulk_delete(ep, delete_all)
    ids = guards.validate_ids(ep, target_ids)

    if delete_all:
        resp = client.request("DELETE", ep.uri, retryable=False,
                              timeout_s=guards.cfg.timeouts.get("assign", 60))
        result = _finish(ep, "DELETE", resp.status, resp.raw, resp.body)
        if result.get("ok"):
            _drop_id_snapshot(ep)
        return result

    # MIDAS deletes one id per request; deleting only the first and reporting
    # success would silently leave the rest of the model in place.
    # DELETE also answers 200 for an id that never existed, so each delete is
    # verified by reading the id back.
    deleted, failed, unverified = [], [], []
    for one in ids:
        resp = client.request("DELETE", f"{ep.uri}/{one}", retryable=False,
                              timeout_s=guards.cfg.timeouts.get("assign", 60))
        if not (200 <= resp.status < 300) or is_error_body(resp.status, resp.raw):
            failed.append({"id": one, "status": resp.status,
                           "message": resp.raw.strip()[:160]})
            continue
        check = client.request("GET", f"{ep.uri}/{one}", retryable=True,
                               timeout_s=guards.cfg.timeouts.get("query", 30))
        if check.status == 400 or "Not Found Key" in check.raw:
            deleted.append(one)
        elif 200 <= check.status < 300 and check.raw.strip() not in ("", "{}"):
            failed.append({"id": one, "status": resp.status,
                           "message": "MIDAS answered 200 to DELETE but the record is still present."})
        else:
            unverified.append(one)  # endpoint cannot be read back; accept the 200
    if failed:
        # A partial delete still removed ids, so the snapshot holding them must
        # go: leaving them in makes the guard *permit* a later write keyed on a
        # node/element MIDAS no longer has - the crash this cache exists to
        # prevent.  The response shape is unchanged.
        if deleted or unverified:
            _drop_id_snapshot(ep)
        return {"ok": False, "category": "MIDAS_REJECTED", "endpoint": ep.key,
                "http_status": failed[0]["status"],
                "message": (f"{len(failed)} of {len(ids)} delete(s) failed; "
                            f"{len(deleted)} deleted."),
                "deleted": deleted, "failed": failed}
    result = normalize_success(ep.key, "DELETE", 200, "", None,
                               data={"deleted": deleted,
                                     **({"unverified": unverified} if unverified else {})})
    _drop_id_snapshot(ep)
    return result


# --------------------------------------------------------------------------
# finish: classify an upstream response into an envelope
# --------------------------------------------------------------------------
def _finish(ep: Endpoint, method: str, status: int, raw: str,
            body: dict | None, data_hint: dict | None = None) -> dict:
    # soft-empty: MIDAS returns an "error"-shaped body just to say nothing to
    # report yet (e.g. storey properties before any storey exists).  That is a
    # valid empty answer, not a failure.
    if is_soft_empty(raw):
        result = {"ok": True, "endpoint": ep.key, "method": method,
                  "status": status, "data": body or {},
                  "soft_empty": True,
                  "message": "MIDAS reports nothing to show yet (valid empty state)."}
        return _annotate_result(ep, result, raw, data_hint)
    # success (2xx, non-empty, error markers absent)
    if 200 <= status < 300 and not is_error_body(status, raw):
        data = body or {}
        result = normalize_success(ep.key, method, status, raw, body, data=data)
        return _annotate_result(ep, result, raw, data_hint)
    # upstream error -> ToolError -> isError envelope
    try:
        classify_error(status, raw, ep.key)
    except ToolError as exc:
        return {"ok": False, "category": exc.category,
                "message": str(exc), "endpoint": ep.key,
                "http_status": status}


def _annotate_result(ep: Endpoint, result: dict, raw: str,
                     data_hint: dict | None = None) -> dict:
    """Append a situation-aware hint inside a successful result, mirroring the
    knowledge base so the model sees the rule at the moment it matters."""
    hints: list[str] = []
    if ep.requires_analysis:
        pass  # the tip below is about absence of rows, we can't see row data generically
    if ep.key.startswith("POST:TABLE"):
        hints.append("read results only after /doc/ANAL. LOAD_CASE_NAMES needs "
                     "'(ST)' for load cases and '(CB)' for combinations.")
        # The summary tables of a POST/TABLE reply live in SUB_TABLES, not in
        # the top-level DATA.  Parse them here so the model receives the modal
        # frequencies/periods/participation masses as data it can quote, rather
        # than having to notice SUB_TABLES and parse it itself.
        parsed = result_summary(raw)
        if parsed:
            result["result_summary"] = parsed
        subs = parsed.get("sub_tables") if parsed else None
        if subs:
            hints.append(
                f"this reply also carries {len(subs)} SUB_TABLES: {subs}. They "
                f"are NOT in the top-level DATA; the parsed form is in "
                f"'result_summary'.")
        modal = modal_result(raw)
        if modal is not None and not modal.get("mode_count"):
            hints.append(
                "a modal SUB_TABLE is present but no mode rows could be read "
                "from it; check the sub-table's HEAD for a renamed mode column.")
        missing = _unserved_load_names(raw, data_hint)
        if missing:
            hints.append(
                f"the table returned no rows for {missing}. MIDAS answers a "
                f"request for a name it does not recognise with HTTP 200 and "
                f"simply omits it, so the omission is silent: a combination must "
                f"be asked for as '<NAME>(CB)' and a load case as '<NAME>(ST)'; "
                f"a combination that has not been solved since the model last "
                f"changed returns nothing as well.")
    if data_hint and any("EIGV" in k.upper() for k in data_hint):
        hints.append("EIGV.TYPE forced to LANCZOS.")
    if ep.key == "OPE:STORYPROP":
        hints.append("storey-property endpoint is POST (STORYPROP); STORPROP is an old spelling. "
                     "'no valid story information' is the expected answer until storeys exist.")
    if hints:
        result["hints"] = hints
    return result


def _unserved_load_names(raw: str, data_hint: dict | None) -> list[str]:
    """Requested load names that produced no rows in a POST/TABLE reply.

    MIDAS drops an unrecognised ``LOAD_CASE_NAMES`` entry without any error, so
    the only way to notice is to compare what was asked for against the 'Load'
    column of what came back.  Names are compared on their base form because the
    request carries a suffix (``DEAD(ST)``) while the rows carry the bare name
    (``DEAD``).
    """
    if not data_hint:
        return []
    requested = data_hint.get("LOAD_CASE_NAMES")
    if not isinstance(requested, list) or not requested:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, dict):
        return []
    returned: set[str] = set()
    for table in parsed.values():
        if not isinstance(table, dict):
            continue
        head, data = table.get("HEAD"), table.get("DATA")
        if not isinstance(head, list) or not isinstance(data, list):
            continue
        try:
            idx = head.index("Load")
        except ValueError:
            continue
        for row in data:
            if isinstance(row, list) and idx < len(row):
                returned.add(str(row[idx]).split("(", 1)[0])

    def base(name: Any) -> str:
        return str(name).split("(", 1)[0]

    return sorted({str(n) for n in requested if base(n) not in returned})