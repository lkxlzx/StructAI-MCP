"""Generic ``/db/*`` CRUD base class.

Source convention: MIDAS-API manual repo, e.g. docs/manual/03_DB_Node_Element.md
#1 (/db/NODE). Every /db/* endpoint is ID-keyed under an "Assign" wrapper for
POST/PUT/DELETE; GET returns the full set (no documented per-ID URL filtering
across the manual, so we don't invent one).

⚠️ DELETE does not work the way the manual documents it. The manual's worked
example is ``DELETE /db/NODE`` with ``{"Assign": {"4": None}}``, and chapters
disagree on ``None`` vs ``{}`` per id. Live testing on 2026-07-26 (Civil NX
2026 v2.1) found **both forms delete the entire table**, ignoring the ids
entirely — deleting one node took the whole node table with it, and the
elements attached to those nodes with it. The undocumented per-id URL,
``DELETE {endpoint}/{id}``, does the right thing: it removes exactly that
record and returns it. Verified across ``/db/NODE``, ``/db/STLD``,
``/db/LDGR`` and ``/db/MATL``; deleting an id that doesn't exist is a
harmless no-op. :meth:`DbResource.delete` uses the per-id URL as of v0.14.0.
The whole-table form is still reachable, deliberately, as
:meth:`DbResource.delete_all`.
"""
from __future__ import annotations

from typing import ClassVar, Optional, TypedDict

from ..client import (
    DestructiveOperationError,
    MidasClient,
    UnsupportedMethodError,
    get_default_client,
)

_ALL_METHODS = frozenset({"POST", "GET", "PUT", "DELETE"})

#: Shared METHODS override for endpoints that support everything but DELETE
#: (e.g. named-group definitions like /db/GRUP, /db/BNGR; single-record
#: settings like /db/PZEF, /db/CLDR) — import instead of redefining locally.
NO_DELETE_METHODS = frozenset({"POST", "GET", "PUT"})

#: Shared METHODS override for singleton Hyper-S-only settings endpoints that
#: don't support POST (e.g. /db/THGC-M1, /db/THOO-M1) — only GET/PUT/DELETE.
GET_PUT_DELETE_METHODS = frozenset({"GET", "PUT", "DELETE"})

#: Shared METHODS override for derived/read-only-input design-code records
#: that support neither POST nor PUT (e.g. ch24-27's LCTB "Load Contribution
#: for Nonlinear Load Case" endpoints) — only GET/DELETE.
GET_DELETE_METHODS = frozenset({"GET", "DELETE"})

#: Shared METHODS override for write-only/no-read design-code records that
#: don't support GET (e.g. ch27's DSRC "SRC Design Code" endpoint) — only
#: PUT/DELETE.
PUT_DELETE_METHODS = frozenset({"PUT", "DELETE"})

#: Shared PRODUCTS override for Civil-NX-only endpoints (e.g. ch17's bridge
#: girder-diagram/camber-control trio, ch08's per-code dynamic-factor and
#: concurrent-group endpoints) — import instead of redefining a local
#: frozenset({"civil"}) per chapter.
#:
#: ⚠️ Most of ch08/ch17 is *not* actually Civil-only. An earlier version of
#: this docstring cited /db/LCOM-CONC as the example — live-checked
#: 2026-07-29 against a real production Gen NX model and found it returns
#: real, populated data there (494 rows), not a 404. The same check found 31
#: more ch08/ch17 endpoints answering on Gen too (route + /info both
#: resolve, usually to an empty table). See GEN_ONLY's docstring below and
#: docs/live_verification_notes.md for the full evidence and the list of
#: what's genuinely still Civil-only in these two chapters.
CIVIL_ONLY = frozenset({"civil"})

#: Shared PRODUCTS override for the Hyper-S (``-M1``) endpoint family.
#:
#: Hyper-S is the solver MIDASIT introduced with Civil NX, so these routes are
#: served by Civil and absent from Gen. Confirmed live on 2026-07-26: all 13
#: implemented ``-M1`` endpoints answered under Civil NX 2026 (v2.1) and all 13
#: returned 404 under Gen NX 2026 (v2.1), on the same account and the same day.
#:
#: Kept separate from :data:`CIVIL_ONLY` deliberately. This is a *product
#: feature* boundary, not the structural Civil/Gen split that ch08/ch17 encode,
#: and MIDASIT is expected to bring Hyper-S to Gen NX at some point. When that
#: happens, widen this one constant rather than hunting down 13 classes — and
#: re-verify with ``scripts/live_readonly_sweep.py --product gen`` first.
HYPER_S_ONLY = frozenset({"civil"})

#: Shared PRODUCTS override for endpoints that answer under Gen NX but 404
#: (route-level, including ``/info/db/...`` schema introspection) under Civil
#: NX. Confirmed by two independent sessions on 2026-07-29, same day, against
#: freshly patched builds: this SDK's own ``live_readonly_sweep.py`` against
#: Civil NX 2026 v2.2 (07/28/2026), and an independently-run validation sweep
#: (report removed from ``docs/`` 2026-09-17; git history at ``fa1332b``)
#: against the same day's Civil and Gen patches from a
#: different machine/session — both landed on the identical 11 ``/db/*``
#: endpoints (``STOR``, ``SWIND``, ``SSEIS``, ``POSP``, ``EPST``, ``DRLS``,
#: ``SDHY``, ``SDIS``, ``REBB``, ``REBR``, ``REBW``) plus the same 9
#: design-chapter endpoints under ``/DESIGN/RC/KDS-41-20-2022/*``,
#: ``/DESIGN/SRC/AIK-SRC2K/MATD`` and ``/DESIGN/STEEL/KDS-41-30-2022/ULCT``.
#: See ``docs/live_verification_notes.md``'s 2026-07-29 sections for the full
#: evidence. A few adjacent 404s (``/db/REBC``'s schema, ``/ope/STORY_PARAM``,
#: ``/ope/STORY_IRR_PARAM``) look like the same pattern but are not yet
#: independently reproduced twice — left alone pending that.
#:
#: Reconfirmed 2026-08-07 against a freshly patched build (Civil NX 2026
#: v2.2, build 08/06/2026): 20 of the 21 classes currently set to
#: :data:`GEN_ONLY` still 404 on Civil with ``strict_product=False``
#: forcing the call through. The 21st, ``/db/REBC`` (``ColumnRebar``,
#: ``db/design.py``), is POST-only — no ``GET`` to force through this
#: pass — so it was not part of this reconfirmation; its own docstring
#: still cites the separate 2026-07-29 ``/info/db/REBC`` schema check as
#: its evidence. No drift found among the 20 reconfirmed since
#: 2026-07-29.
GEN_ONLY = frozenset({"gen"})

#: Not a constant — a note on the mirror-image finding. On 2026-07-29, a live
#: re-check against real production Civil NX and Gen NX sessions open at once
#: found 32 of 47 endpoints declared :data:`CIVIL_ONLY` (excluding
#: :data:`HYPER_S_ONLY`) also answer under Gen NX — route + ``/info`` schema
#: both resolve there too, one (``/db/LCOM-CONC``) with real, populated data
#: (494 rows), the rest with an empty table. Those 32 are now left at the
#: class default (``gen+civil``) instead of :data:`CIVIL_ONLY`: 23 in
#: ``db/moving_loads.py``, 5 in ``db/analysis_control.py`` (the ``MVCT``
#: family), 2 in ``db/load_combinations.py``, 1 each in ``db/dynamic_loads.py``
#: (``THGC``) and ``db/bridge.py`` (``ULFC``). The remaining 15 genuinely 404
#: on Gen and stay :data:`CIVIL_ONLY`: the Hyper-S family aside, that's
#: ``CAMB``, ``CJFG``, ``CMCS``, ``CRGR``, ``DYFG``, ``DYLA``, ``DYNF``,
#: ``EWSF``, ``GCMB``, ``GSBG``, ``PLCB``, ``RCHK``, ``SPAN``, ``STRPSSM``,
#: ``WVLD``. That the API answers doesn't mean using a bridge/moving-load
#: endpoint from a Gen NX session is a sound engineering choice for a given
#: project — that's the calling engineer's judgment, not something
#: ``PRODUCTS`` should gate. See ``docs/live_verification_notes.md``'s
#: 2026-07-29 sections for the full evidence.


class ItemGroupFields(TypedDict, total=False):
    """Shared ID/GROUP_NAME preamble for a /db/* "ITEMS" array entry — extend
    this instead of re-declaring ID/GROUP_NAME on every new Item TypedDict."""

    ID: int  # Serial Number, default 0, optional
    GROUP_NAME: str  # Group Name (Boundary/Load, depending on endpoint), default "", optional


class TimeValuePoint(TypedDict, total=False):
    """Shared {TIME, VALUE} pair used by several time-function "ITEM"/
    "aFUNCDATA" arrays (e.g. /db/THFC, /db/ETFC, /db/CCFC, /db/HSFC) —
    import this instead of re-declaring the same two fields per chapter."""

    TIME: float  # required
    VALUE: float  # required


class OptUseToleranceValue(TypedDict, total=False):
    """Shared {OPT_USE, VALUE} convergence-criterion pair used by several
    Hyper-S nested convergence objects (e.g. /db/ACTL-M1's TCELEM.CONVERGENCE,
    /db/NLCT-M1's CONV_CRITERIA, /db/POGD-M1's ITER_CTRL.NORM_CTRL — each of
    DISPL/LOAD/WORK or DISP/FORCE/ENERGY) — import this instead of
    re-declaring the same two fields per chapter."""

    OPT_USE: bool  # optional
    VALUE: float  # required if OPT_USE is true


class InitialLoadCaseItem(TypedDict, total=False):
    """Shared {LC_NAME, LC_TYPE, SF} pushover/pushover-Hyper-S initial-load
    entry (e.g. /db/POGD's "INITLOAD", /db/POGD-M1's "INIT_LOAD_LIST",
    /db/THGC-M1's "INIT_LOAD_LIST") — import this instead of re-declaring the
    same three fields per chapter."""

    LC_NAME: str  # Load Case Name, required
    LC_TYPE: str  # Load Case Type (e.g. "STATIC"/"STAGE"), required
    SF: float  # Scale Factor, required


class DbResource:
    """Base class for a single ``/db/*`` endpoint.

    Subclasses set:
        ENDPOINT: e.g. "/db/NODE"
        NAME: human-readable name (manual "기능" column), for error messages
        PRODUCTS: {"gen"}, {"civil"}, or {"gen", "civil"}
        METHODS: subset of {"POST", "GET", "PUT", "DELETE"} the endpoint
            actually supports (defaults to all four; override for
            GET/PUT-only endpoints like MATD).

    Also provides ``.info()`` — a server-side schema introspection GET
    (``/info/db/...``), independent of ``METHODS``/CRUD; see its docstring.
    """

    ENDPOINT: ClassVar[str]
    NAME: ClassVar[str] = ""
    PRODUCTS: ClassVar[frozenset] = frozenset({"gen", "civil"})
    METHODS: ClassVar[frozenset] = _ALL_METHODS

    @classmethod
    def _check(cls, client: MidasClient, method: str) -> None:
        client.check_product(cls.PRODUCTS, cls.NAME or cls.__name__)
        if method not in cls.METHODS:
            raise UnsupportedMethodError(
                f"{cls.NAME or cls.__name__} ({cls.ENDPOINT}) does not support {method}; "
                f"supported methods: {sorted(cls.METHODS)}",
                method=method,
                endpoint=cls.ENDPOINT,
            )

    @classmethod
    def get(cls, client: Optional[MidasClient] = None) -> dict:
        """Fetch all items. Response is nested under the endpoint's key,
        e.g. ``{"NODE": {"1": {...}, "2": {...}}}``."""
        client = client or get_default_client()
        cls._check(client, "GET")
        return client.request("GET", cls.ENDPOINT)

    @classmethod
    def items(cls, client: Optional[MidasClient] = None) -> dict:
        """Fetch all items, unwrapped to ``{id: payload}`` with int ids
        (e.g. ``{1: {"X": 0, "Y": 0, "Z": 0}, ...}`` for ``Node``), instead
        of ``.get()``'s raw ``{ENDPOINT_KEY: {"1": {...}, ...}}`` response.
        ``.get()`` is unchanged; use whichever shape is more convenient.

        Returns ``{}`` for an empty table. A zero-row response has been
        observed live in two shapes — ``{"<KEY>": {}}`` and a bare
        ``{"message": ""}`` (see docs/live_verification_notes.md) — so this
        picks the first dict-valued entry rather than the first entry, which
        would otherwise raise ``AttributeError`` on the string value.
        """
        response = cls.get(client=client)
        if not isinstance(response, dict):
            return {}
        table = next((v for v in response.values() if isinstance(v, dict)), {})
        return {int(k): v for k, v in table.items()}

    @classmethod
    def info(cls, client: Optional[MidasClient] = None) -> dict:
        """GET {base url}/info/db/... — server-returned key/type schema for
        this resource, e.g. ``GET /info/db/NODE``.

        Docs: the MIDAS-API manual repo's docs/AUTHENTICATION.md, "/info/db/...
        — DB 리소스 스키마 인트로스펙션" — undocumented in the per-chapter
        manual pages this repo's TypedDicts are transcribed from, but
        documented in the repo's auth guide as a way to ask the server
        directly for a field's current shape instead of digging through the
        manual (or as a fallback for the endpoints this SDK hasn't wrapped
        yet). Not tracked in docs/coverage.json/ROADMAP.md for that reason.
        Independent of ``METHODS`` (schema info, not a data operation) — this
        is attempted even for GET-less resources (e.g. ch27's ``DSRC``,
        PUT/DELETE only).
        """
        client = client or get_default_client()
        client.check_product(cls.PRODUCTS, cls.NAME or cls.__name__)
        return client.request("GET", "/info" + cls.ENDPOINT)

    @classmethod
    def create(cls, items: dict, client: Optional[MidasClient] = None) -> dict:
        """items: {id: payload_dict}, e.g. {1: {"X": 0, "Y": 0, "Z": 0}}."""
        client = client or get_default_client()
        cls._check(client, "POST")
        return client.request("POST", cls.ENDPOINT, {"Assign": {str(k): v for k, v in items.items()}})

    @classmethod
    def update(cls, items: dict, client: Optional[MidasClient] = None) -> dict:
        """items: {id: payload_dict} — same shape as create()."""
        client = client or get_default_client()
        cls._check(client, "PUT")
        return client.request("PUT", cls.ENDPOINT, {"Assign": {str(k): v for k, v in items.items()}})

    @classmethod
    def delete(cls, ids: list, client: Optional[MidasClient] = None) -> dict:
        """Delete the listed ids, e.g. ``[1, 2, 3]``. Returns ``{id: response}``.

        Issues one ``DELETE {ENDPOINT}/{id}`` per id rather than the manual's
        single ID-keyed ``"Assign"`` body. That is not a stylistic choice: the
        documented body form was measured deleting **the entire table**
        regardless of which ids it names (see this module's docstring), which
        for ``/db/NODE`` also takes out every element attached to those nodes.
        The per-id URL removes exactly the record asked for.

        Deleting an id that isn't there is a no-op, so this is safe to call
        without checking first. If you actually want to empty a table, say so
        with :meth:`delete_all`.
        """
        client = client or get_default_client()
        cls._check(client, "DELETE")
        return {i: client.request("DELETE", f"{cls.ENDPOINT}/{i}") for i in ids}

    @classmethod
    def delete_all(cls, client: Optional[MidasClient] = None, *, confirm: bool = False) -> dict:
        """Empty this table — **every record**, not a selection.

        Requires ``confirm=True``. Without it this raises
        :class:`~midas_nx.client.DestructiveOperationError` before sending
        anything, so a mistaken call costs nothing::

            Node.delete_all(confirm=True)

        This is the manual's documented DELETE call (``{"Assign": {...}}``
        against the bare endpoint). Live testing showed it ignoring the ids in
        that body and clearing the table, so it is exposed under a name that
        says what it does instead of being reachable by accident through
        :meth:`delete`.

        For ``/db/NODE`` this also removes every element attached to the
        deleted nodes. There is no undo through the API, and the products
        raise no confirmation dialog on the API path — the keyword is the
        only thing standing between a typo and an emptied model, which is
        why it is required rather than merely recommended.

        To remove specific records instead, use :meth:`delete`.
        """
        if confirm is not True:
            raise DestructiveOperationError(
                f"{cls.NAME or cls.__name__} ({cls.ENDPOINT}): delete_all() would delete "
                f"every record in this table, not a selection, and cannot be undone. "
                f"Call delete_all(confirm=True) if that is intended.",
                method="DELETE",
                endpoint=cls.ENDPOINT,
            )
        client = client or get_default_client()
        cls._check(client, "DELETE")
        return client.request("DELETE", cls.ENDPOINT, {"Assign": {}})
