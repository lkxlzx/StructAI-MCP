"""Minimal HTTP client for the MIDAS NX Open API.

Uses ``http.client`` (not ``urllib``) so an in-flight connection can be closed
from the cancellation path.  Header auth by ``MAPI-Key``, JSON bodies, and a
controlled retry policy: one retry only for idempotent GETs on transient
statuses, never for analysis/delete/import/export/design actions.
"""
from __future__ import annotations

import http.client
import json
import logging
import re
import socket
import threading
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any

from .config import Config
from .guards import RETRYABLE_STATUS

log = logging.getLogger("midas_mcp.http")

#: How long a "family -> existing ids" snapshot stays usable.  The cache exists
#: to keep the crash guard from re-reading NODE/ELEM on every guarded write, but
#: it must expire: the model can also be edited by a human in the MIDAS GUI, and
#: an entry that lives for the whole process makes a freshly created id look
#: missing (a bogus "keys records on NODE ids that do not exist" refusal).
_ID_CACHE_TTL_S = 5.0
#: family -> (ids, time.monotonic() at which they were read)
_id_cache: dict[str, tuple[list[str], float]] = {}
#: Bumped by every invalidation.  A read that started before a write must not
#: store its now-stale list afterwards, or that one invalidation is undone for
#: a whole TTL; the store therefore compares this epoch and drops the result.
_id_epoch = 0
_id_lock = threading.Lock()


@dataclass
class UpstreamResponse:
    status: int
    body: dict | None
    raw: str
    ok_by_status: bool  # 2xx
    duration_ms: float
    #: True if this HTTP method is idempotent and eligible for a retry.
    retryable: bool = False


class _AbortableConnection:
    """Wrapper so a worker thread can force-close the socket on cancel."""

    def __init__(self, host: str, port: int, timeout: float, cancel: threading.Event | None):
        self.cancel = cancel
        self.conn: http.client.HTTPConnection | None = None
        self._build(host, port, timeout)

    def _build(self, host, port, timeout):
        self.conn = http.client.HTTPConnection(host, port, timeout=timeout)
        # periodic check is not needed on the connect path; we check before/after.

    def request(self, method, path, body=None, headers=None):
        return self.conn.request(method, path, body=body, headers=headers or {})

    def abort(self):
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass


class MidasClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        parsed = urllib.parse.urlsplit(cfg.base_url)
        self.host = parsed.hostname or "localhost"
        self.port = parsed.port or (443 if parsed.scheme == "https" else 80)
        self.scheme = parsed.scheme or "http"
        # the base URL may carry a path segment (/gen, /civil) that must be
        # prefixed onto every request path
        self._base_path = re.sub(r"/+$", "", parsed.path or "")
        self._active: dict[str, _AbortableConnection] = {}

    def _url(self, path: str) -> str:
        return f"{self._base_path}{path}"

    def request(self, method: str, path: str, body: dict | None = None, *,
                timeout_s: int | None = None,
                retryable: bool = False,
                cancel: threading.Event | None = None) -> UpstreamResponse:
        timeout = timeout_s or self.cfg.timeouts.get("query", 30)
        final_status = 0
        final_resp: UpstreamResponse | None = None
        attempts = 2 if retryable else 1
        for attempt in range(attempts):
            final_resp = self._one(method, path, body, timeout, cancel)
            final_status = final_resp.status
            if attempt == 0 and retryable and final_status in RETRYABLE_STATUS:
                log.warning("transient HTTP %s on GET %s; retrying", final_status, path)
                time.sleep(0.3 * (attempt + 1))
                continue
            break
        return final_resp

    def _one(self, method: str, path: str, body: dict | None,
             timeout: int, cancel: threading.Event | None) -> UpstreamResponse:
        if cancel is not None and cancel.is_set():
            raise TimeoutError("cancelled before request")
        started = time.time()
        payload = None
        if body is not None:
            #: ``ensure_ascii=False`` keeps the payload readable, so it is a
            #: ``str`` that can hold any character - a Chinese load-case
            #: description, a Korean section name.  http.client encodes a
            #: *str* body as latin-1, which raises on the first such character
            #: (and would have mislabelled Content-Length anyway), so the body
            #: is encoded here, once, and the length is the length of that.
            payload = json.dumps(body, ensure_ascii=False,
                                 separators=(",", ":")).encode("utf-8")
        headers = {
            "MAPI-Key": self.cfg.mapi_key.reveal(),
            "Content-Type": "application/json",
        }
        if payload is not None:
            headers["Content-Length"] = str(len(payload))

        conn = _AbortableConnection(self.host, self.port, timeout, cancel)
        conn_key = f"{threading.get_ident()}:{path}"
        # register for abort (best effort; a cancel uses these too)
        if cancel is not None:
            self._active[conn_key] = conn
        try:
            conn.request(method, self._url(path), body=payload, headers=headers)
            resp = conn.conn.getresponse()
            raw = resp.read().decode("utf-8", "replace")
        except (socket.timeout, http.client.HTTPException, TimeoutError, ConnectionError) as exc:
            duration = (time.time() - started) * 1000
            return UpstreamResponse(0, None, f"transport error: {exc}", False, duration,
                                    retryable=True)
        finally:
            self._active.pop(conn_key, None)
            conn.abort()
        duration = (time.time() - started) * 1000
        body_json = None
        if raw and raw.strip():
            try:
                body_json = json.loads(raw)
            except json.JSONDecodeError:
                body_json = None
        ok = 200 <= resp.status < 300
        up = UpstreamResponse(resp.status, body_json, raw, ok, duration,
                              retryable=True)
        return up

    def cancel_in_flight(self) -> None:
        for conn in list(self._active.values()):
            conn.abort()


_SESSION_ID = threading.local()


def invalidate_id_cache(family: str | None = None) -> None:
    """Drop one family (or all) from the id snapshot cache.

    Two kinds of caller need this.  A write path drops what it just changed:
    ``dispatch.tool_db_assign`` / ``tool_db_delete`` drop their endpoint's
    family (a partially failed delete included) and the model-replacing doc
    commands clear everything.  A reader that is about to write the very
    collection it is inspecting drops it up front (the construction-stage
    preflight looks at DB:BNGR while writing DB:STAG).  ``_ID_CACHE_TTL_S`` is
    the backstop for everything else, in particular a model edited by hand in
    the GUI.
    """
    global _id_epoch
    with _id_lock:
        _id_epoch += 1
        if family is None:
            _id_cache.clear()
        else:
            _id_cache.pop(family, None)


def midas_get_ids(cfg: Config, family: str) -> list[str]:
    """Snapshot of the ids currently defined for a family (NODE/ELEM).

    Cached per-family for ``_ID_CACHE_TTL_S`` seconds so the crash guard does
    not re-read NODE/ELEM on every guarded write.  The window is short on
    purpose: the model can be edited by a human in the MIDAS GUI as well, so a
    snapshot may never be trusted indefinitely.  A failed read is never cached
    (an empty list would refuse every ref-keyed write for a whole window) and a
    read that races an invalidation does not store at all.  Relied on by the
    crash guard.
    """
    now = time.monotonic()
    with _id_lock:
        cached = _id_cache.get(family)
        if cached is not None and now - cached[1] < _ID_CACHE_TTL_S:
            return cached[0]
        epoch = _id_epoch
    client = MidasClient(cfg)
    resp = client.request("GET", f"/db/{family.upper()}", retryable=True)
    ids: list[str] = []
    if resp.ok_by_status and isinstance(resp.body, dict):
        # response shape: {"NODE": {"1": {...}, "2": {...}}, ...}
        for outer in resp.body.values():
            if isinstance(outer, dict):
                ids.extend(str(k) for k in outer)
                break
    if not resp.ok_by_status:
        # A transport error or a 404 is not evidence that the collection is
        # empty.  Caching the [] would make every ref-keyed write refuse for a
        # whole TTL; one live read per guarded write is the cheaper mistake.
        return ids
    with _id_lock:
        if epoch == _id_epoch:
            _id_cache[family] = (ids, time.monotonic())
    return ids