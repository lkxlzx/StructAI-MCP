"""Safety guards applied before any upstream MIDAS request is sent.

These turn the *documented fixtures* of the previous version into hard rules the
connector (and therefore the model) cannot accidentally break.  Each guard is
enforced here, where it can be unit tested, rather than in the tool prompt.

The highest-severity behaviour is the crash guard: several endpoints key their
records on a node/element number, and a missing id crashes the MIDAS process
entirely (every subsequent request 502s).  Those endpoints are flagged in the
registry with ``ref_family`` and are checked here before a write is allowed.
"""
from __future__ import annotations

import re
from typing import Any

from .config import Config
from .errors import GuardError, InputError
from .registry import Endpoint, Registry

#: HTTP statuses eligible for one retry (network jitter from a busy backend).
RETRYABLE_STATUS = {502, 503, 504}

#: Payload paths that are auto-corrected rather than rejected, because the
#: upstream silently drops or misreads them.  Each was confirmed on live Gen NX.
_P_TYPE_PATH = ("MATL", "PARAM")


class Guards:
    def __init__(self, reg: Registry, cfg: Config):
        self.reg = reg
        self.cfg = cfg

    # -- path / key shape -------------------------------------------------
    def validate_endpoint(self, raw: str) -> Endpoint:
        if not isinstance(raw, str) or not raw.strip():
            raise InputError("endpoint is required and must be a string.")
        if raw.startswith(("http://", "https://")) or "/" in raw:
            raise InputError(
                f"endpoint must be a registry key like DB:NODE, not a URL or path: {raw!r}")
        if ".." in raw:
            raise InputError(f"endpoint key may not contain '..': {raw!r}")
        ep = self.reg.lookup(raw)
        if ep is None:
            raise InputError(
                f"unknown MIDAS endpoint {raw!r}. Use midas_db_query search to "
                f"discover valid endpoint keys.")
        return ep

    def validate_ids(self, ep: Endpoint, target_ids: Any) -> list[str]:
        if not isinstance(target_ids, list) or not target_ids:
            raise InputError(
                f"{ep.key}: target_ids must be a non-empty list of ids to "
                "delete. An empty list is never interpreted as 'delete all'.")
        if any(not isinstance(x, (str, int)) or str(x) in ("", "..", "/") for x in target_ids):
            raise InputError(f"{ep.key}: each id must be a plain id string/number.")
        ids = [str(x) for x in target_ids]
        if ep.id_mode == "numeric-string":
            for i in ids:
                if not re.fullmatch(r"[0-9]+", i):
                    raise InputError(f"{ep.key}: id {i!r} is not a valid numeric id.")
        return ids

    def refuse_bulk_delete(self, ep: Endpoint, delete_all: bool) -> None:
        if delete_all and not self.cfg.allow_bulk_delete:
            raise GuardError(
                f"{ep.key}: bare delete-all is refused. Set "
                "MIDAS_MCP_ALLOW_BULK_DELETE=1 explicitly to permit it.",
                endpoint=ep.key)

    # -- crash guard -------------------------------------------------------
    def require_existing_refs(self, ep: Endpoint, data: dict) -> None:
        """Refuse to write when a key-on-node/element endpoint references a
        missing id.  MIDAS crashes, not errors, on this --- so we don't send."""
        if ep.ref_family is None:
            return
        fam = ep.ref_family  # "NODE" or "ELEM"
        ids = [k for k in data.keys()]
        present = {str(x)
                   for x in _existing_ids(self.reg, self.cfg, fam)}
        bad = [i for i in ids if i not in present]
        if bad:
            raise GuardError(
                f"{ep.key} keys records on {fam} ids that do not exist: "
                f"{bad}. Assigning a missing {fam} id crashes MIDAS; the write "
                f"was refused. Verify the model has those {fam}s first.",
                endpoint=ep.key)

    # -- retry policy ------------------------------------------------------
    def is_retryable(self, ep: Endpoint, method: str, status: int) -> bool:
        """GET is idempotent and may retry transient statuses once; nothing
        else is ever auto-retried (analysis, deletes, imports, design)."""
        if method.upper() != "GET":
            return False
        return status in RETRYABLE_STATUS

    # -- model cannot choose the wrapper -----------------------------------
    def strip_wrapper(self, data: dict) -> dict:
        """A model-supplied ``Assign``/``Argument``/``data`` key is stripped."""
        return {k: v for k, v in (data or {}).items()
                if k not in ("Assign", "Argument", "data")}

    # -- payload corrections ------------------------------------------------
    def correct_payload(self, ep: Endpoint, mode: str, data: dict) -> dict:
        """Auto-correct known-losing payload shapes so the right form is the
        only easy form.  Each correction is documented in the registry notes."""
        import copy
        data = copy.deepcopy(data)

        if data.get("EIGV") is not None or ep.key == "DB:EIGV":
            _force_lanczos(data, ep)
        _force_p_type(data)
        _fix_export_paths(data)
        return data

    def warn_saveas(self, command: str) -> str | None:
        if command == "SAVEAS":
            return ("DOC:SAVEAS opens a modal dialog that blocks the whole API "
                    "channel until dismissed in the GUI. Prefer DOC:SAVE.")
        return None

    # -- construction-stage preflight --------------------------------------
    def stage_preflight(self, ep: Endpoint, data: dict) -> str | None:
        """Warn when a construction-stage write cannot lead to a solvable model.

        Verified live on Gen NX 2027: the mere *presence* of DB:STAG switches
        ``/doc/ANAL`` into construction-stage mode, and a stage analysis needs
        the supports addressed as a boundary **group**.  With stages defined but
        no boundary group activated, every later analysis answers HTTP 400
        ``[错误] 边界条件 没有定义。`` - a message that names neither the stage
        nor the missing group, so the cause is very hard to find from the error
        alone.  The write itself succeeds, which is what makes this worth
        flagging at write time rather than at analysis time.
        """
        if ep.key not in ("DB:STAG", "DB:STCT"):
            return None
        if ep.key == "DB:STCT":
            missing = "DB:STAG"
        else:
            missing = "DB:BNGR"
        if self._collection_present(missing):
            return None
        return (f"{ep.key} defined but {missing} is empty. Defining a construction "
                f"stage puts /doc/ANAL into construction-stage mode, which needs "
                f"the supports addressed as a boundary GROUP: create DB:BNGR, set "
                f"each DB:CONS item's GROUP_NAME to it, and list it in the first "
                f"stage's ACT_BNGR. Until then every analysis answers HTTP 400 "
                f"'[错误] 边界条件 没有定义。' Also set DB:STCT (the stage-analysis "
                f"control record) or no stage analysis runs at all.")

    def _collection_present(self, name: str) -> bool:
        """True when ``DB:<name>`` holds at least one record.

        The id snapshot is cached per family, which is right for NODE/ELEM but
        wrong here: this preflight runs immediately before writing the very
        record it is checking for, so a stale empty snapshot would warn on every
        write.  The family is dropped from the cache first.  The ``DB:`` prefix
        must be stripped - ``midas_get_ids`` builds ``/db/<family>``, so a
        prefixed name would read ``/db/DB:BNGR`` and answer 404, i.e. "empty",
        and the warning would fire even when the group exists.
        """
        from .midas_http import midas_get_ids, invalidate_id_cache
        family = name.split(":", 1)[-1]
        try:
            invalidate_id_cache(family)
            return bool(midas_get_ids(self.cfg, family))
        except Exception:
            return True  # never block a write on an introspection failure


def _force_lanczos(data: dict, ep: Endpoint) -> None:
    """EIGV.TYPE must be LANCZOS: with a rigid diaphragm the mass matrix is
    non-diagonal and MIDAS refuses the subspace method."""
    def _fix(rec: dict) -> None:
        if rec.get("TYPE") not in (None, "LANCZOS"):
            rec["TYPE"] = "LANCZOS"
    recs = _records(data)
    for rec in recs:
        _fix(rec)


def _force_p_type(data: dict) -> None:
    """MATL PARAM.P_TYPE must be 2 (user-defined): P_TYPE 1 is accepted but
    silently zeroes POISN/THERMAL/DEN/MASS."""
    def _fix(rec: dict) -> None:
        params = rec.get("PARAM")
        if isinstance(params, list):
            for p in params:
                if isinstance(p, dict):
                    p["P_TYPE"] = 2
        elif isinstance(params, dict):
            for p in params.values():
                if isinstance(p, dict):
                    p["P_TYPE"] = 2

    for rec in _records(data):
        _fix(rec)


def _fix_export_paths(data: dict) -> None:
    """EXPORT_PATH / file paths must use Windows backslashes; forward slashes
    yield 'second query is wrong' or a read timeout when reading results."""
    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in list(node.items()):
                if k in ("EXPORT_PATH", "FILE_PATH", "EXPORT_FILE") \
                        and isinstance(v, str):
                    node[k] = v.replace("/", "\\")
                else:
                    _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)
    _walk(data)


def _records(data: dict) -> list[dict]:
    """Flatten the ``Assign`` map values for correction."""
    out: list[dict] = []
    if "Assign" in data and isinstance(data["Assign"], dict):
        for v in data["Assign"].values():
            if isinstance(v, dict):
                out.append(v)
    else:
        for v in data.values():
            if isinstance(v, dict):
                out.append(v)
    return out


def _existing_ids(reg: Registry, cfg: Config, family: str) -> list[str]:
    """Best-effort list of live ids for a family.

    The snapshot is cached per family inside ``midas_http`` (for
    ``_ID_CACHE_TTL_S``, a few seconds) and is dropped by every write to that
    family, so it is not cached on this caller.  Returns a non-empty list or
    the empty list (a missing id is refused)."""
    from .midas_http import midas_get_ids
    return midas_get_ids(cfg, family)