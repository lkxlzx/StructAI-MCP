"""The four MCP tools and their dispatch to the MIDAS client.

Tool surface is fixed at the four from mcp/03_TOOLS.md:
``midas_doc``, ``midas_db_query``, ``midas_db_assign``, ``midas_db_delete``.
Every MIDAS endpoint is reached through the registry, never through a URL the
model supplies.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Callable
import uuid

from .errors import FrameRunError, InputError, ToolError
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
        {
            "name": "midas_frame_run",
            "description": "One-shot steel portal frame: build the model from a spec, "
                           "run the analysis, verify the results against load "
                           "equilibrium, and return the finished report. Use this "
                           "instead of driving midas_db_assign step by step.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "spec": {
                        "type": "object",
                        "description": "Model spec. Omitted keys keep the validated "
                                       "20 m span / 6 m eave / 8 m ridge frame; an "
                                       "unknown key is refused, never ignored.",
                    },
                    "spec_path": {
                        "type": "string",
                        "description": "JSON spec file, e.g. specs/portal-frame.json",
                    },
                    "out_dir": {
                        "type": "string",
                        "description": "Where report.md / state.json and the audit "
                                       "trail are written.",
                    },
                    "clear": {
                        "type": "boolean",
                        "default": False,
                        "description": "Delete this driver's own DB collections first; "
                                       "only needed after an interrupted run.",
                    },
                    "background": {
                        "type": "boolean",
                        "default": False,
                        "description": "Return a job id straight away instead of "
                                       "waiting for the whole run (~5 min); poll "
                                       "midas_frame_status. Use this when the "
                                       "client's own timeout is shorter than a run.",
                    },
                },
            },
            "outputSchema": {"type": "object"},
            "annotations": {"readOnlyHint": False, "destructiveHint": True,
                            "idempotentHint": False},
        },
        {
            "name": "midas_frame_status",
            "description": "Progress of a midas_frame_run job: the driver steps "
                           "reported so far while it runs, and the finished report "
                           "once it is done.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string",
                               "description": "from the midas_frame_run answer"},
                },
                "required": ["job_id"],
            },
            "outputSchema": {"type": "object"},
            "annotations": {"readOnlyHint": True, "destructiveHint": False,
                            "idempotentHint": True},
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
    _require_no_live_run()
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
    _require_no_live_run()
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
    _require_no_live_run()
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


# --------------------------------------------------------------------------
# midas_frame_run: the one-shot portal-frame pipeline
# --------------------------------------------------------------------------
#: Wall-clock backstop for the one-shot run.  It has to clear the driver's own
#: worst case rather than one analysis: ``solve()`` may issue up to three
#: ``DOC:ANAL`` calls, each allowed ``timeouts.analysis`` (1800 s by default).
#: A 3600 s budget killed a slow-but-successful run, leaving the live document
#: fully built with no verdict at all.
_FRAME_RUN_TIMEOUT_S = 7200.0


def tool_frame_run(args: dict, deps: Deps) -> dict:
    """Build, analyse, self-verify and report a steel portal frame in one call.

    A wrapper around ``python -m midas_mcp.frame --json``, not a second
    implementation, so the tool and the command an operator runs cannot drift
    apart.  It has to be a *subprocess*: the driver prints its report to
    stdout, and inside this server stdout is the JSON-RPC stream, so an
    in-process run would corrupt the protocol.
    """
    _guards, client, _registry = deps()
    #: A non-boolean has to be refused rather than read as truthy, for the same
    #: reason ``clear`` is: {"background": "false"} means "wait for it".  It is
    #: checked before the command is assembled, so a refused argument costs
    #: nothing - not even a temporary directory.
    background = args.get("background")
    if background is not None and not isinstance(background, bool):
        raise InputError("background must be a boolean.")
    _require_no_live_run()
    argv, env, cwd, spec_text = _frame_command(args, client)
    if background:
        #: No progress channel here on purpose: an MCP progress notification
        #: belongs to a request that is still in flight, and this one is
        #: answered at once.  The caller polls instead.
        return _started(_start_frame(argv, env, cwd, spec_text))
    #: The notifier and the progress token are read HERE, on the thread that
    #: owns the call: the reader thread that emits the notifications is a
    #: different thread, and a thread-local would not follow it there.
    job = _start_frame(argv, env, cwd, spec_text, notify=_call_notify(),
                       token=_call_token())
    if not job.done.wait(timeout=_FRAME_RUN_TIMEOUT_S):
        job.kill()
        raise FrameRunError(
            f"the frame run exceeded {_FRAME_RUN_TIMEOUT_S:.0f} s and was killed; "
            "check whether MIDAS is still busy or wedged")
    return _answer(job)

# --------------------------------------------------------------------------
# the frame run as a job
# --------------------------------------------------------------------------
#: Per-call channel back to the client.  A tool handler runs on the thread that
#: owns the request, so a thread-local is the right scope for it.  The notifier
#: and the token are read on that thread and handed to the reader thread
#: explicitly, because a thread-local does not follow them there.
CALL = threading.local()

#: ``[NN] PASS  name  -- detail``: one line per prompt step, flushed by the
#: driver as it happens.  This is what makes both progress channels work
#: without the driver knowing anything about them.
_STEP_RE = re.compile(r"^\[(\d{2})\]\s+(PASS|FAIL)\s+(.*)$")

#: Jobs live for the life of the server process: a background run has to
#: outlive the ``tools/call`` that started it, and there is nowhere else to put
#: it.  A server restart therefore forgets its jobs, which the status tool says
#: plainly rather than pretending the id was never valid.
_JOBS: dict[str, "FrameJob"] = {}
_JOBS_LOCK = threading.Lock()

#: Finished jobs are kept so a late poll can still read the report, but only the
#: most recent few: each holds the child's whole stdout, report included, and a
#: server runs for days.
_MAX_KEPT_JOBS = 20


def _live_jobs() -> list[str]:
    with _JOBS_LOCK:
        return sorted(j.id for j in _JOBS.values() if not j.done.is_set())


def _evict_jobs():
    """Drop the oldest finished jobs.  Call with ``_JOBS_LOCK`` held."""
    if len(_JOBS) <= _MAX_KEPT_JOBS:
        return
    finished = sorted((j for j in _JOBS.values() if j.done.is_set()),
                      key=lambda j: j.started)
    for job in finished[:len(_JOBS) - _MAX_KEPT_JOBS]:
        _JOBS.pop(job.id, None)


def _require_no_live_run():
    """Refuse a second writer while a frame run is building in the document.

    The driver clears collections and builds over them in the LIVE MIDAS
    document, so a run interleaved with another run - or with any other write -
    leaves both models half-built and the report describing neither.  Before
    background jobs existed the transport's single thread enforced this by
    accident; now it has to be said out loud.  Reads stay allowed, which is how
    a caller watches a run instead of colliding with it.
    """
    live = _live_jobs()
    if live:
        raise InputError(
            f"a frame run is already in flight ({', '.join(live)}) and it writes "
            "to the live MIDAS document. Poll midas_frame_status until it "
            "finishes, then retry - two writers at once build over each other.")


def _call_token():
    return getattr(CALL, "token", None)


def _call_notify():
    return getattr(CALL, "notify", None)


class FrameJob:
    """One driver subprocess, and everything it has said so far."""

    def __init__(self, job_id, proc, command):
        self.id = job_id
        self.proc = proc
        self.command = command
        self.started = time.monotonic()
        self.lines: list[str] = []
        self.stderr: list[str] = []
        self.done = threading.Event()
        self.holder = None
        self.watchdog = None

    def kill(self):
        try:
            self.proc.kill()
        except OSError:
            pass

    def elapsed(self) -> float:
        return round(time.monotonic() - self.started, 1)

    def steps(self) -> list[dict]:
        """The driver's own step lines, in the order it printed them.

        No total is claimed: the driver prints one line per step and never
        announces how many it will print, so the number of lines seen is the
        only honest count.  (The validated run prints 18.)
        """
        out = []
        for line in list(self.lines):
            match = _STEP_RE.match(line.strip())
            if match:
                out.append({"step": int(match.group(1)),
                            "ok": match.group(2) == "PASS",
                            "text": match.group(3).strip()})
        return out

    def progress(self) -> dict:
        steps = self.steps()
        return {"steps_done": len(steps),
                "last": steps[-1] if steps else None,
                "steps": steps}


def _frame_command(args: dict, client) -> tuple[list[str], dict, str, str]:
    """The driver's argv, environment, cwd and spec JSON for one call.

    The target and the key travel in the environment, never argv: a key on a
    command line is readable from the process table.
    """
    inline = args.get("spec") or {}
    if not isinstance(inline, dict):
        raise InputError("spec must be an object of model keys.")
    spec_path = args.get("spec_path")
    if spec_path is not None and not isinstance(spec_path, str):
        raise InputError("spec_path must be a string.")

    from .frame import load_spec
    try:
        base = load_spec(spec_path) if spec_path else {}
    except (OSError, ValueError) as exc:
        raise InputError(f"spec_path is not usable: {exc}") from exc
    if not isinstance(base, dict):
        raise InputError("spec_path must contain a JSON object.")

    #: The inline spec is the more specific instruction, so it wins over the file.
    merged = {**base, **inline}
    if args.get("out_dir"):
        merged["out_dir"] = str(args["out_dir"])

    argv = [sys.executable, "-m", "midas_mcp.frame", "--json"]
    #: ``--clear`` deletes this driver's collections from the LIVE document, so a
    #: non-boolean has to be refused rather than read as truthy: a client sending
    #: {"clear": "false"} means "do not delete", and Python would run the deletes.
    clear = args.get("clear")
    if clear is not None and not isinstance(clear, bool):
        raise InputError("clear must be a boolean.")
    if clear:
        argv.append("--clear")

    env = dict(os.environ)
    #: The session's own target and key, so the child talks to the same MIDAS
    #: this server is bound to - otherwise a config profile the child does not
    #: rediscover from its own cwd silently retargets the run.
    env["MIDAS_MAPI_KEY"] = client.cfg.mapi_key.reveal()
    env["MIDAS_BASE_URL"] = client.cfg.base_url
    env["PYTHONIOENCODING"] = "utf-8"
    #: ``python -m midas_mcp.frame`` has to import the package, and a source
    #: checkout is not on the child's path by itself.
    src = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = os.pathsep.join(
        [src] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))

    #: The spec travels as text rather than as a file: the file is written only
    #: when a run is actually about to start, so nothing exists to clean up if
    #: the call is refused first.
    spec_text = json.dumps(merged, ensure_ascii=False)
    return argv, env, str(Path(__file__).resolve().parents[2]), spec_text


def _start_frame(argv, env, cwd, spec_text, notify=None, token=None) -> FrameJob:
    """Write the spec, start the driver, hand back its job.

    The spec file is created here rather than where the command was assembled:
    an argument that gets refused must not leave a temporary directory behind,
    and neither must a run that never starts.
    """
    holder = tempfile.TemporaryDirectory(prefix="midas-frame-")
    try:
        path = Path(holder.name) / "spec.json"
        path.write_text(spec_text, encoding="utf-8")
        argv = argv + ["--spec", str(path)]
        proc = subprocess.Popen(
            argv, env=env, cwd=cwd, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8",
            errors="replace", bufsize=1)
    except OSError as exc:
        #: Writing the spec is as much a part of starting as spawning is: either
        #: way there is nothing to run, so nothing should be left on disk.
        holder.cleanup()
        raise FrameRunError(f"could not start the driver: {exc}") from exc
    job = FrameJob(uuid.uuid4().hex[:12], proc, argv)
    job.holder = holder
    #: The wall-clock backstop belongs to the job rather than to whoever polls
    #: it, or a background run nobody polls would never be bounded at all.
    job.watchdog = threading.Timer(_FRAME_RUN_TIMEOUT_S, job.kill)
    job.watchdog.daemon = True
    job.watchdog.start()
    with _JOBS_LOCK:
        _JOBS[job.id] = job
        _evict_jobs()
    threading.Thread(target=_reader, args=(job, notify, token), daemon=True,
                     name=f"frame-{job.id}").start()
    return job


def _reader(job, notify, token):
    """Drain both pipes, forward the step lines, then close the job.

    Each pipe needs its own reader: the driver writes little to stderr, but a
    traceback there is exactly the case where nobody is watching, and a full
    pipe buffer blocks the child instead of failing it.

    ``done`` is set in a ``finally`` deliberately.  The child is already running
    by the time this starts, so any way out of here that skipped it - a thread
    that cannot be created, a wait that raises - would leave a live process
    nobody is draining, blocked on a full pipe, reported as running forever.
    """
    try:
        out = threading.Thread(target=_drain,
                               args=(job, job.proc.stdout, job.lines, notify,
                                     token), daemon=True)
        err = threading.Thread(target=_drain,
                               args=(job, job.proc.stderr, job.stderr, None,
                                     None), daemon=True)
        out.start()
        err.start()
        out.join()
        err.join()
        job.proc.wait()
    except Exception:  # noqa: BLE001 - the job has to be closed either way
        log.exception("frame job %s could not be drained", job.id)
        job.kill()
    finally:
        if job.watchdog is not None:
            job.watchdog.cancel()
        if job.holder is not None:
            try:
                job.holder.cleanup()
            except OSError:
                pass
        job.done.set()


def _drain(job, stream, sink, notify, token):
    try:
        for line in stream:
            sink.append(line)
            if notify is not None and token is not None:
                match = _STEP_RE.match(line.strip())
                if match:
                    _emit_progress(notify, token, job, match)
    except (OSError, ValueError):
        pass
    finally:
        try:
            stream.close()
        except OSError:
            pass


def _emit_progress(notify, token, job, match):
    """Forward one driver step to the client as an MCP progress notification.

    Best effort by design: progress is a courtesy, and a client that has gone
    away must not be able to fail a five-minute analysis.
    """
    try:
        notify("notifications/progress",
               {"progressToken": token,
                "progress": len(job.steps()),
                "message": f"[{match.group(1)}] {match.group(2)}  "
                           f"{match.group(3).strip()}"})
    except Exception:  # noqa: BLE001 - see the docstring
        log.debug("progress notification dropped", exc_info=True)


def _started(job) -> dict:
    """The answer to a ``background: true`` call: a handle, or the result.

    A child that dies at once - an unusable spec exits in about 100 ms - is
    already finished by the time this is built.  Handing back a job id and
    "poll until running is false" would send the caller looking for a report it
    already has, so a finished job answers with its real envelope instead.
    """
    if job.done.is_set():
        return _answer(job)
    return {
        "ok": True,
        "endpoint": "FRAME:RUN",
        "method": "RUN",
        "status": 202,
        "category": None,
        "message": (f"started job {job.id}; poll midas_frame_status with this "
                    "job_id until running is false, then read report"),
        "job_id": job.id,
        "running": True,
        "report": "",
        "data": {"job_id": job.id, "progress": job.progress()},
    }


def _answer(job) -> dict:
    """The tool's answer for a finished job.

    One place, used by the blocking call and by the status poll alike, so the
    two cannot end up describing the same run differently.
    """
    verdict = None
    #: split("\n") rather than splitlines(): a report can legitimately contain
    #: U+2028/U+2029, which json.dumps leaves literal, and splitlines() would
    #: cut the verdict line in two and report a good run as having no verdict.
    for line in reversed("".join(job.lines).split("\n")):
        line = line.strip()
        if line.startswith("{"):
            try:
                verdict = json.loads(line)
            except ValueError:
                continue
            break
    if not isinstance(verdict, dict):
        # 2 = missing credentials or an unusable spec, 3 = the preflight refused
        # a non-empty MIDAS document; neither prints a verdict.  The tail of the
        # child's own message is what makes this actionable.
        detail = ("".join(job.stderr) or "".join(job.lines)).strip()[-600:]
        raise FrameRunError(
            f"the driver exited {job.proc.returncode} without a verdict: {detail}")

    report = verdict.pop("report", "")
    good = bool(verdict.get("ok"))
    analysis = verdict.get("analysis")
    note = verdict.get("note")
    if good:
        category = None
    elif analysis == "REFUSED":
        # The preflight declined to build on a non-empty document.  Retrying
        # the identical call changes nothing, so the category has to name the
        # situation rather than the generic failure.
        category = "MODEL_NOT_EMPTY"
    elif analysis in (None, "NOT_RUN"):
        category = "FRAME_RUN_FAILED"
    else:
        category = "SELF_CHECK_FAILED"
    message = (f"analysis={analysis} "
               f"criteria={len(verdict.get('criteria') or [])} "
               f"failed={len(verdict.get('failed') or [])} "
               f"exit={verdict.get('exit_code')}")
    if note:
        message += f" - {note}"
    if category == "MODEL_NOT_EMPTY":
        #: A client that reads only the category cannot tell a dead end from a
        #: retry it can make itself, so the remedy belongs in the answer rather
        #: than in a transcript.  Deleting a model the caller may still want is
        #: not something to do silently, which is why this stays a refusal.
        message += (" - retry with {\"clear\": true} to delete this driver's own "
                    "collections first, or empty the MIDAS document by hand")
    return {
        "ok": good,
        "endpoint": "FRAME:RUN",
        "method": "RUN",
        "status": 200 if good else 500,
        "category": category,
        "message": message,
        "report": report,
        "job_id": job.id,
        "running": False,
        "data": verdict,
    }


def tool_frame_status(args: dict, deps: Deps) -> dict:
    """Progress of a job started with ``midas_frame_run {"background": true}``.

    While the run is in flight this reports the steps the driver has printed so
    far - the driver's own lines, not an estimate of how far along it is.  Once
    it is done the answer is the same envelope the blocking call returns, report
    and all, so a caller that polled gets exactly what it would have waited for.
    """
    job_id = args.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise InputError("job_id must be a non-empty string.")
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        known = sorted(_JOBS)
    if job is None:
        raise InputError(
            f"unknown job_id {job_id!r}. This server has started "
            f"{len(known)} job(s): {known or 'none'}. Jobs do not survive a "
            "server restart, and every midas_frame_run call makes a new one.")
    if not job.done.is_set():
        #: No kill here any more: the job carries its own watchdog, so a
        #: background run nobody polls is still bounded, and this stays a read.
        return {
            "ok": True,
            "endpoint": "FRAME:STATUS",
            "method": "STATUS",
            "status": 202,
            "category": None,
            "message": f"{job.id} is still running ({job.elapsed():.0f} s)",
            "job_id": job.id,
            "running": True,
            "report": "",
            "data": {"job_id": job.id, "progress": job.progress(),
                     "elapsed_s": job.elapsed()},
        }
    return _answer(job)