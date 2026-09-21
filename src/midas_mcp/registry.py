"""Endpoint registry loading, lookup, and model-facing discovery.

The registry is generated offline by ``build/build_registry.py`` from the
vendored docs plus live-verified URIs.  This module only *reads* it; the
list of possible endpoints is therefore never under model control.  The model
names an endpoint key (e.g. ``DB:NODE``); ``lookup`` maps that onto the trusted
``uri``/``methods``/``wrapper`` record.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

PATH_RE = re.compile(r"^/(db|doc|ope|view|post|DESIGN)(/[A-Za-z0-9_.\-]+)*$")
SAFE_KEY_RE = re.compile(r"^[A-Za-z0-9_:.\-*]+$")


@dataclass(frozen=True)
class Endpoint:
    key: str
    namespace: str
    uri: str
    methods: tuple = ()
    wrapper: str = "Assign"
    selector_field: str | None = None
    selector_value: str | None = None
    id_mode: str = "none"
    ref_family: str | None = None
    title: str = ""
    source_page: str = ""
    timeout_s: int = 30
    destructive: bool = False
    requires_analysis: bool = False
    retryable: bool = False
    live_probe: int | None = None
    variant: tuple = ()
    notes: tuple = ()

    @property
    def ref_dim(self) -> str | None:
        """Node/ELEM family this endpoint keys on, if any.

        Presence means the connector must verify the referenced id exists before
        writing: MIDAS crashes the whole process when these reference a missing
        node/element id.
        """
        return self.ref_family


class Registry:
    def __init__(self, by_key: dict[str, Endpoint]):
        self._by_key = by_key
        self._alias: dict[str, str] = _build_aliases(by_key)

    @classmethod
    def load(cls, directory: Path) -> "Registry":
        path = directory / "registry.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        by_key: dict[str, Endpoint] = {}
        for key, raw in data["endpoints"].items():
            if not SAFE_KEY_RE.match(key):
                raise ValueError(f"unsafe registry key: {key!r}")
            uri = raw["uri"]
            if not PATH_RE.match(uri):
                raise ValueError(f"registry uri does not pass path guard: {uri!r} ({key})")
            by_key[key] = Endpoint(
                key=key,
                namespace=raw["namespace"],
                uri=uri,
                methods=tuple(raw["methods"]),
                wrapper=raw["wrapper"],
                selector_field=raw.get("selector_field"),
                selector_value=raw.get("selector_value"),
                id_mode=raw.get("id_mode", "none"),
                ref_family=raw.get("ref_family"),
                title=raw.get("title", ""),
                source_page=raw.get("source_page", ""),
                timeout_s=raw.get("timeout_s", 30),
                destructive=raw.get("destructive", False),
                requires_analysis=raw.get("requires_analysis", False),
                retryable=raw.get("retryable", False),
                live_probe=raw.get("live_probe"),
                variant=tuple(raw.get("variant", [])),
                notes=tuple(raw.get("notes", [])),
            )
        return cls(by_key)

    def lookup(self, key: str) -> Endpoint | None:
        """Resolve an endpoint key (exact, alias, or unique human name).

        ``NODE`` -> ``DB:NODE``; ``BEAMFORCE`` -> ``POST:TABLE:BEAMFORCE``.
        The resolution is explicit: never a wildcard guess, never ``../``.
        """
        if key in self._by_key:
            return self._by_key[key]
        full = self._alias.get(key)
        return self._by_key.get(full) if full else None

    def keys(self) -> list[str]:
        return sorted(self._by_key)

    def families(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for k, e in self._by_key.items():
            if e.namespace not in out:
                out[e.namespace] = []
            out[e.namespace].append(k)
        return out

    def by_namespace(self, namespace: str) -> list[Endpoint]:
        return [e for e in self._by_key.values() if e.namespace == namespace]

    def search(self, query: str) -> list[dict]:
        """Model-facing discovery: find endpoints by substring across key/title.

        Returns small records (no internal fields) so the model can discover
        what it can call next without being handed secrets or flag internals.
        """
        q = query.upper().strip()
        hits: list[dict] = []
        for k, e in self._by_key.items():
            if not q or q in k.upper() or q in e.title.upper():
                hits.append({
                    "key": k,
                    "uri": e.uri,
                    "methods": list(e.methods),
                    "wrapper": e.wrapper,
                    "selector": e.selector_value,
                    "title": e.title,
                    "variant": list(e.variant) or "general",
                    "notes": list(e.notes)[:3],
                })
        hits.sort(key=lambda h: h["key"])
        return hits


def _build_aliases(by_key: dict[str, Endpoint]) -> dict[str, str]:
    """Map bare last-segment names to their fully qualified key when unique.

    ``NODE``->``DB:NODE``, ``BEAMFORCE``->``POST:TABLE:BEAMFORCE``.  Keys made
    ambiguous by sharing a last segment (e.g. two ``DCO`` across design routes)
    are omitted so the model must be explicit.
    """
    bucket: dict[str, list[str]] = {}
    for k in by_key:
        bucket.setdefault(k.split(":")[-1], []).append(k)
    alias = {}
    for name, keys in bucket.items():
        if len(keys) == 1:
            alias[name] = keys[0]
    return alias


def iter_endpoints(reg: Registry) -> Iterator[Endpoint]:
    return iter(reg._by_key.values())