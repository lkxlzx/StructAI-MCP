"""Seed ``tools`` / ``tool_interfaces`` / ``capabilities`` from the API extraction.

Authoritative sources
---------------------
* 《StructAI MCP V2.1 设计框架规范》(**V2.1**) §16.1 (解析表结构：``capabilities``
  + ``capability_interfaces`` + ``tool_interfaces`` + ``tools``), §16.2 (解析失败
  一律 ``CAPABILITY_NOT_SUPPORTED``), §17.2 (``tool_interfaces.resource`` 存 MCP
  单数名), §17.3 (``metadata_json`` 承载 ``outer_key_means``), §17.4
  (``capability_code`` 形态 ``"<resource>.<action>"``，``interface_code`` 形态
  ``{adapter}.{family}.{path…}[.{table_type}].{operation}``), §6.3 (四个 Tool 的
  ``action`` / ``resource`` 词表).
* 《StructAI 架构边界与融合规范 v1.0 总纲》(**总纲**) §0.4 (唯一真源),
  §4.2.11 (三层分类 ``product_scope`` / ``domain`` / ``feature``),
  §4.2.12 (``capabilities.tool_id`` —— 工具是**能力自身**的属性),
  §4.4 (错误码封闭集合：本模块**不新增**任何错误码),
  §4.6.1 (MCP 单数资源名), §4.8.2 (权限码封闭集合 —— 本模块不产生权限码),
  §4.9.2 (四道闸).
* 《MIDAS NX Open API 对接规范 v1.0》(**对接规范**) §2.5.1 (MIDAS 没有任务 API),
  §3.1 (``Assign`` / ``Argument`` 包装), §3.2 (响应根键), §3.5 第 1/5/15 条,
  §4.1 (``Assign`` 外层键语义), §5 (``/info`` 自省), §11.5.6 (``/post/TABLE``).

Why this module exists
----------------------
:mod:`app.mcp.capability_loader` is the bridge *from* the database *to* the
in-memory capability table.  Nothing yet put the extraction's rows **into** the
database, so the two halves of Phase 2 had never been joined: the extraction
produced an **API-level** row (``adapter_code`` / ``interface_code`` / ``method``
/ ``endpoint`` / ``operation`` / ``resource``) while the MCP layer needs a
**capability-level** row (``tool`` / ``resource`` / ``action``).  This seeder is
that join, and it is deliberately a *design* rather than a script: the mapping is
one reviewable table (:data:`TOOL_AND_ACTION_RULES`) plus one explicit endpoint
table for the family whose vocabulary the extraction cannot carry
(:data:`EXECUTE_ENDPOINT_CAPABILITIES`).

The mapping, in one place
-------------------------
Every extracted row is classified by ``(family, operation)``:

======================  ====================  ====================================
family                  operation             ``(tool, action)``
======================  ====================  ====================================
``db`` / ``design``     ``read``              ``midas_query`` + ``get``
``db`` / ``design``     ``create``            ``midas_model`` + ``create``
``db`` / ``design``     ``update``            ``midas_model`` + ``update``
``db`` / ``design``     ``delete``            ``midas_model`` + ``delete``
``db`` / ``design``     ``execute``           ``midas_model`` + ``create`` (POST)
``post``                ``read`` / ``query``  ``midas_query`` + ``get``
``doc``/``ope``/``view`` ``read`` / ``query`` ``midas_query`` + ``get``
``doc``/``ope``/``view`` ``create``/``update``/``delete``/``execute``
                                              ``midas_execute`` + the endpoint
                                              table's ``(resource, action)``
anything else           —                     **skipped and counted**
======================  ====================  ====================================

Three deliberate rulings are recorded here rather than in the report only:

1. **``read`` -> ``get``.**  V2.1 §7.2's ``midas_query`` action vocabulary is
   ``get | list | search | count | inspect``; the extraction's operation
   vocabulary (V2.1-adjacent, but minted by
   ``docs/api-registry/extract_interfaces.py``) is
   ``create | read | update | delete | execute | query``.  ``read`` is not a
   member, and ``get`` is the member that means 「按外层键取一条记录」 — the same
   operation.  Mapping ``read`` to ``get`` is what makes ``/db/NODE`` GET land on
   the **static** ``node.get`` slot, which is the acceptance test.
2. **``db``/``design`` + ``execute`` -> ``midas_model`` + ``create``.**  The
   operation says the POST *does* something; the endpoint says it is a ``/db``
   table write, and ``POST`` is the create verb on a ``/db`` table
   (对接规范 §11.5.3/§11.5.4).  The ``midas_model`` vocabulary has no ``execute``,
   and inventing one would need a new ``DISPATCH_HINTS`` value (总纲 §4.4).
3. **``midas_execute`` is endpoint-keyed.**  ``capability_loader.derive_dispatch``
   rule 9 classifies ``midas_execute`` by the **closed**
   ``EXECUTE_DISPATCH_TABLE`` ``(resource, action)`` pairs, not by the endpoint,
   because that dispatch genuinely is not a function of the endpoint (the loader's
   own docstring).  So an execute row can only be seeded if its endpoint is
   already declared in ``app.mcp.capabilities._EXECUTE_ROWS`` or in this module's
   :data:`EXECUTE_ENDPOINT_CAPABILITIES`; everything else is skipped and counted
   with :data:`SKIP_EXECUTE_UNMAPPED`.  **No** ``constraints_json.dispatch``
   override is used: an override would let this seeder assert a dispatch the
   loader's own rule table cannot derive, which is exactly the guessing
   ``SKIP_UNDERIVABLE_DISPATCH`` exists to prevent.

What the extraction does *not* give the MCP layer
--------------------------------------------------
* **MCP payload schemas.**  ``request_schema_json`` is the **API request body**
  (a manual example 594 times out of 604, per ``EXTRACTION_REPORT.md`` §3), not
  the ``midas_query`` / ``midas_model`` payload the second validation of
  V2.1 §6.2 / §9.3 checks.  Storing a request *example* as ``request_schema_json``
  would make ``ToolDispatcher.validate_payload`` reject every call whose payload
  is not that one example, so this seeder leaves the column NULL and preserves the
  extraction's value under ``metadata_json.extraction_request_schema`` instead.
  The consequence is measured and reported: a seeded row is **more permissive**
  than its static counterpart on ``request_schema``.
* **``midas_execute`` actions for endpoints the static table never declared.**
  See ruling 3 above.
* **A real ``product_scope``.**  Every extracted row ships ``unknown``
  (``meta.product_scope_policy``; 对接规范 §3.5 第 15 条: 47 endpoints declared
  "Civil-only" answer on Gen too), so gate 4 of 总纲 §4.9.2 admits them
  optimistically with an ``unverified`` warning — the shipped behaviour, not a
  regression.
* **The unwrapped ``title`` has no column.**  The extraction emits both ``title``
  (the manual's own title, link removed) and ``description`` (the Chinese
  annotation); only the annotation has a home in this schema
  (``capabilities.description``), so the title stays in the extraction and in
  ``tool_interfaces.metadata_json.annotation_key`` for review.

The Chinese annotation (总纲 §4.2.13)
------------------------------------
The registry is an **API catalogue**, and the manuals' Chinese and English sections
document the *same* endpoints — the section's language says nothing, so what matters
is that every API carries a **Chinese annotation** a Chinese-speaking user and the
LLM can read.  ``capabilities.description`` is that annotation's documented home
(总纲 §4.2.13: ``notes`` has no column of its own), and
:mod:`app.mcp.capability_loader` already maps that column to ``Capability.notes``.
Each extracted row's ``description`` is therefore written there, and its
``metadata_json.annotation_source`` (``manual`` / ``glossary``) is preserved in the
capability's ``constraints_json`` — the only capability-level JSON column — so a
reviewer can tell a name the manual ships from one ``title_zh.json`` supplied.

A ``null`` annotation **never** overwrites a value that is already there: the
extraction is authoritative for what it states and silent about what it does not, so
a curated description (or the annotation an earlier row of the same run wrote)
survives an unannotated refresh.  A non-null annotation refreshes the slot like every
other column of this upsert.

Behaviour contract
------------------
* **Idempotent.**  Every row is matched by its natural key (``tools.name``,
  ``(adapter_code, interface_code)``, ``(adapter_code, capability_code)``) and
  refreshed in place, so a second run inserts nothing and changes nothing.
* **Takes a session factory.**  Like :mod:`app.db.init_db`'s helpers it can be
  handed one, so a test never touches the process-wide engine.
* **Counted, not silent.**  :class:`SeedResult` reports inserted / updated /
  skipped counts, per-reason skip counts and the mapping table's coverage.  A
  seeder that silently drops rows is how the ``requested_by`` gap happened.
* **Never invents** an endpoint, a method or a tool.  ``tool`` / ``action`` come
  from the code's own declarations (``TOOL_NAMES`` and the static rows), and
  ``endpoint`` / ``method`` come from the extraction verbatim.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Final, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import PRODUCT_SCOPE_BY_PRODUCT
from app.db.base import session_scope_for
from app.mcp.capabilities import (
    TOOL_EXECUTE,
    TOOL_MODEL,
    TOOL_NAMES,
    TOOL_QUERY,
    TOOL_TASK,
    capability_rows,
)
from app.mcp.capability_loader import EXECUTE_DISPATCH_TABLE
from app.mcp.tools import TOOL_MODULES
from app.models.midas import Adapter as AdapterRow
from app.models.registry import (
    Capability as CapabilityRow,
    CapabilityInterface as CapabilityInterfaceRow,
    Tool as ToolRow,
    ToolInterface as ToolInterfaceRow,
)

__all__ = [
    # entry points
    "SeedResult",
    "seed_interfaces",
    "default_interfaces_path",
    "load_interfaces",
    # the reviewable derivation
    "TOOL_AND_ACTION_RULES",
    "EXECUTE_ENDPOINT_CAPABILITIES",
    "KNOWN_FAMILIES",
    "MODEL_FAMILIES",
    "EXECUTE_FAMILIES",
    "TABLE_FAMILIES",
    "ADAPTER_CODES",
    "ClassifiedRow",
    "derive_resource_alias",
    "capability_slot",
    "classify_row",
    # the closed vocabularies of the report
    "SKIP_REASONS",
    "SKIP_UNKNOWN_FAMILY",
    "SKIP_UNSUPPORTED_OPERATION",
    "SKIP_UNSUPPORTED_METHOD",
    "SKIP_EXECUTE_UNMAPPED",
    "SKIP_MISSING_REQUIRED_FIELD",
    "SKIP_MALFORMED_ROW",
]


# ---------------------------------------------------------------------------
# The input
# ---------------------------------------------------------------------------
#: ``docs/api-registry/interfaces.json`` — the pipeline's own output
#: (``meta.counts.rows == 2497``).  **Not** ``midas_api_registry.json`` /
#: ``part-*.json``: those are an earlier, unrelated extraction with different
#: field names (no ``adapter_code``), and mixing them would seed a second,
#: contradictory registry.
_INTERFACES_RELATIVE: Final[tuple[str, ...]] = ("docs", "api-registry", "interfaces.json")

#: ``meta.adapter_codes``, copied so this module can validate the extraction
#: without a database.  The three products of 多产品多租户路由框架 §二.
ADAPTER_CODES: Final[tuple[str, ...]] = ("midas_gen", "midas_civil", "midas_cdn")

#: Endpoint families whose first path segment is a documented MIDAS family
#: (``extract_interfaces.ENDPOINT_FAMILIES`` + ``rating``, which the manual
#: documents even though the adapter's family set does not list it).
KNOWN_FAMILIES: Final[frozenset[str]] = frozenset(
    {"db", "doc", "ope", "view", "post", "info", "design", "rating"}
)

#: Families whose shared URIs carry a ``TABLE_TYPE`` discriminator, so
#: ``interface_code`` — not ``endpoint`` — names the logical endpoint
#: (V2.1 §17.4 / 总纲 裁决 B-3 / 对接规范 §11.5.6).
TABLE_FAMILIES: Final[frozenset[str]] = frozenset({"post", "design"})

#: Families that write through ``midas_model`` rather than ``midas_execute``.
#: ``design`` is here because its parameter tables (``/design/RC/…/rebb``) are
#: model data, not software actions; its *perform* endpoints (``…/cdesign``,
#: ``…/wc_anal``) carry the ``query`` operation, are **not** in
#: :data:`EXECUTE_ENDPOINT_CAPABILITIES`, and are therefore skipped and reported
#: rather than guessed at (ruling 3).
MODEL_FAMILIES: Final[frozenset[str]] = frozenset({"db", "design"})

#: Families whose writes are software actions (``midas_execute``).
EXECUTE_FAMILIES: Final[frozenset[str]] = frozenset({"doc", "ope", "view", "rating"})


def default_interfaces_path() -> Path:
    """``<repo>/docs/api-registry/interfaces.json`` (``backend/app/db`` -> root)."""
    return Path(__file__).resolve().parents[3].joinpath(*_INTERFACES_RELATIVE)


def load_interfaces(path: Path | None = None) -> dict[str, Any]:
    """Parse the extraction; ``path=None`` selects :func:`default_interfaces_path`."""
    source = path if path is not None else default_interfaces_path()
    with source.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{source}: 顶层不是 JSON 对象")
    return payload


# ---------------------------------------------------------------------------
# The mapping table (rule 1: one table, reviewable)
# ---------------------------------------------------------------------------
#: ``(family-class, operation) -> (tool, action)``.  A missing key means 「this
#: seeder will not guess」 and the row is skipped with
#: :data:`SKIP_UNSUPPORTED_OPERATION` — never given an invented value.
#:
#: The keys are **not** invented strings: the family classes are the constants
#: above and the operation values are the extraction's closed set
#: (``meta.coverage.by_operation``: ``create | read | update | delete | execute |
#: query``).
TOOL_AND_ACTION_RULES: Final[dict[tuple[str, str], tuple[str, str]]] = {
    # --- /db/* : the model tables (V2.1 §8) ------------------------------
    # ``read`` is the only operation a GET produces, so it is the only one that
    # maps to ``midas_query``; everything else is a table write.  A POST whose
    # operation is ``query`` (``/db/CLWP``, ``/db/GSBG`` …) is deliberately
    # absent: routing it to ``midas_query`` would make the adapter send a **GET**
    # for a documented POST, which is a different call to MIDAS.
    ("model", "read"): (TOOL_QUERY, "get"),
    ("model", "create"): (TOOL_MODEL, "create"),
    ("model", "update"): (TOOL_MODEL, "update"),
    ("model", "delete"): (TOOL_MODEL, "delete"),
    # Ruling 2: a POST that "executes" on a /db table is still that table's
    # create verb (对接规范 §11.5.3/§11.5.4), and `execute` is not a member of
    # the midas_model vocabulary (V2.1 §6.3).  ``/db/BUCK`` POST -> ``buck.create``.
    ("model", "execute"): (TOOL_MODEL, "create"),
    # --- /post/TABLE : the shared result-table URI (对接规范 §11.5.6) -------
    # The endpoint POSTs, but the operation is a *read* of a table, and the static
    # declaration routes that read through ``midas_query`` with
    # ``dispatch=get_table`` (``result.get`` / ``result.list`` …).
    ("table", "read"): (TOOL_QUERY, "get"),
    ("table", "query"): (TOOL_QUERY, "get"),
    # --- /doc/* /ope/* /view/* /rating/* : software actions (V2.1 §9) ----
    # Only the read half is rule-driven; the write half is endpoint-keyed in
    # :data:`EXECUTE_ENDPOINT_CAPABILITIES` (ruling 3).
    ("execute", "read"): (TOOL_QUERY, "get"),
    ("execute", "query"): (TOOL_QUERY, "get"),
}

#: The extraction's write verbs.  ``read`` and ``query`` are absent on purpose:
#: ``/design/**`` uses ``query`` for its *perform* endpoints (``…/cdesign``,
#: ``…/wc_anal``), which are software actions, not reads.
_WRITE_OPERATIONS: Final[frozenset[str]] = frozenset(
    {"create", "update", "delete", "execute"}
)


def _rule_for(family: str, operation: str) -> tuple[str, str] | None:
    """``(tool, action)`` for one extracted ``(family, operation)``, or ``None``.

    The table is :data:`TOOL_AND_ACTION_RULES`; ``None`` is a **real answer**
    (「this seeder will not guess」) and the caller turns it into a counted skip.
    """
    if family == "post":
        return TOOL_AND_ACTION_RULES.get(("table", operation))
    if family in MODEL_FAMILIES:
        return TOOL_AND_ACTION_RULES.get(("model", operation))
    if family in EXECUTE_FAMILIES:
        return TOOL_AND_ACTION_RULES.get(("execute", operation))
    return None


#: ``(family, endpoint-path-slug) -> ((resource, action), …)`` — the
#: ``midas_execute`` half, keyed by **endpoint** because that is what the
#: loader's rule 9 dispatches on.
#:
#: Two rules govern the entries, and both exist so the seeded row cannot silently
#: disagree with the static declaration:
#:
#: 1. every ``(resource, action)`` pair is a key of
#:    ``app.mcp.capability_loader.EXECUTE_DISPATCH_TABLE`` — asserted at import
#:    time below, so a pair the loader cannot derive is a load-time failure here
#:    rather than a silently skipped row there;
#: 2. only endpoints whose ``(resource, action)`` the static declaration **itself**
#:    declares are listed.  ``/doc/OPEN`` is ``project.open_project`` because
#:    ``_EXECUTE_ROWS`` says so; ``/doc/NEW`` is not listed even though it also
#:    opens a project, because listing it would make ``/doc/NEW`` — which the
#:    extraction happens to order first — the primary interface of that
#:    capability, and the row would then dispatch to a **different endpoint** than
#:    the declaration does.  An endpoint this table does not list is skipped with
#:    :data:`SKIP_EXECUTE_UNMAPPED` and reported, never merged by accident.
#:
#: ``/doc/ANAL`` carries two pairs because the static declaration itself gives it
#: two rows (``model.calculate`` and ``analysis.analysis``) — a real
#: many-to-many, which is what ``capability_interfaces`` (裁决 B-3) exists for.
EXECUTE_ENDPOINT_CAPABILITIES: Final[
    dict[tuple[str, str], tuple[tuple[str, str], ...]]
] = {
    ("doc", "anal"): (("model", "calculate"), ("analysis", "analysis")),
    ("doc", "open"): (("project", "open_project"),),
    ("doc", "save"): (("project", "save_project"),),
    ("doc", "close"): (("project", "close_project"),),
    ("doc", "import"): (("file", "import"),),
    ("doc", "export"): (("file", "export"),),
}

#: 总纲 §0.4 —— the mapping above may not claim a dispatch the loader's own rule
#: table cannot derive.  Failing at import beats a silently skipped row.
assert all(
    pair in EXECUTE_DISPATCH_TABLE
    for pairs in EXECUTE_ENDPOINT_CAPABILITIES.values()
    for pair in pairs
), "EXECUTE_ENDPOINT_CAPABILITIES 含 EXECUTE_DISPATCH_TABLE 未声明的 (resource, action)"

#: ``adapter_action`` / ``task_type`` per ``(resource, action)`` of
#: :data:`EXECUTE_ENDPOINT_CAPABILITIES`, transcribed from
#: ``app.mcp.capabilities._EXECUTE_ROWS`` so a seeded execute row is
#: field-for-field the static one.  An absent pair gets no ``adapter_action``.
_EXECUTE_ROW_FIELDS: Final[dict[tuple[str, str], tuple[str | None, str | None]]] = {
    ("model", "calculate"): ("calculate", "calculate"),
    ("analysis", "analysis"): ("analysis", "analysis"),
    ("project", "open_project"): ("open", "model_import"),
    ("project", "save_project"): ("save", "export"),
    ("project", "close_project"): ("close", None),
    ("file", "import"): ("import", "import"),
    ("file", "export"): ("export", "export"),
}


# ---------------------------------------------------------------------------
# Skip reasons — why an extracted row did **not** become a capability
# ---------------------------------------------------------------------------
#: The endpoint's first path segment is not a documented MIDAS family
#: (``/midas``, ``/url``, ``/resource``, ``/db...`` — ``EXTRACTION_REPORT.md`` §8).
SKIP_UNKNOWN_FAMILY: Final[str] = "unknown_family"
#: ``(family, operation)`` has no :data:`TOOL_AND_ACTION_RULES` entry: the
#: extraction's operation is outside the target tool's vocabulary (V2.1 §6.3).
SKIP_UNSUPPORTED_OPERATION: Final[str] = "unsupported_operation"
#: The method is not one of the HTTP verbs the extraction emits
#: (``GET``/``POST``/``PUT``/``DELETE``).
SKIP_UNSUPPORTED_METHOD: Final[str] = "unsupported_method"
#: The endpoint is not declared in :data:`EXECUTE_ENDPOINT_CAPABILITIES`, so no
#: ``(resource, action)`` pair with an ``EXECUTE_DISPATCH_TABLE`` entry exists.
#: **This is the honest answer, not a defect** — see ruling 3 in the module
#: docstring.
SKIP_EXECUTE_UNMAPPED: Final[str] = "execute_endpoint_unmapped"
#: ``adapter_code`` / ``interface_code`` / ``endpoint`` / ``method`` /
#: ``operation`` missing or blank.  The DDL forbids NULL, but an empty string is
#: not a usable key either.
SKIP_MISSING_REQUIRED_FIELD: Final[str] = "missing_required_field"
#: Any other exception while building one row — counted, never raised.
SKIP_MALFORMED_ROW: Final[str] = "malformed_row"

#: Closed vocabulary of :attr:`SeedResult.skipped_by_reason`.
SKIP_REASONS: Final[frozenset[str]] = frozenset(
    {
        SKIP_UNKNOWN_FAMILY,
        SKIP_UNSUPPORTED_OPERATION,
        SKIP_UNSUPPORTED_METHOD,
        SKIP_EXECUTE_UNMAPPED,
        SKIP_MISSING_REQUIRED_FIELD,
        SKIP_MALFORMED_ROW,
    }
)

#: HTTP verbs the extraction emits (``meta.coverage.by_method``).  A row with
#: anything else cannot be dispatched and is counted.
_HTTP_METHODS: Final[frozenset[str]] = frozenset({"GET", "POST", "PUT", "DELETE"})


# ---------------------------------------------------------------------------
# The result
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SeedResult:
    """What one seed did — the report that stops a silent drop.

    ``rows_read == interfaces_inserted + interfaces_updated + skipped``: every
    extracted row either failed classification (a counted skip) or wrote exactly
    one ``tool_interfaces`` row.  A collapse shares the **capability** row, never
    the interface row, so the interface half stays a partition.
    """

    #: Extracted rows the file returned.
    rows_read: int = 0
    #: ``tools`` rows inserted / refreshed.
    tools_inserted: int = 0
    tools_updated: int = 0
    #: ``tool_interfaces`` rows inserted / refreshed.
    interfaces_inserted: int = 0
    interfaces_updated: int = 0
    #: ``capabilities`` rows refreshed in place: a slot that already held a row
    #: **before** this run (a static declaration, or a previous seed).
    capabilities_updated: int = 0
    #: ``capabilities`` rows this run **created**.
    capabilities_inserted: int = 0
    #: Distinct capability slots this run wrote — the number of ``capabilities``
    #: rows the loader will read.  A collapse shares a slot and adds nothing, and
    #: an extra ``(resource, action)`` pair of a shared endpoint adds one, so this
    #: is exact rather than derived.
    slots_written: int = 0
    #: Extracted rows that landed on a slot an **earlier row of this run** created
    #: (``/db/GSBG`` documents both a ``read`` and a ``query``, and both mean
    #: ``gsbg.get``).  The capability row is shared; the interface row is not.
    collapsed_rows: int = 0
    #: ``capability_code -> interface_code`` for every collapse.  The loser's
    #: interface row is still stored and linked; only the capability row is shared.
    collapsed: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: ``capability_interfaces`` links inserted (a capability served by >1 endpoint,
    #: or an endpoint serving >1 capability — 裁决 B-3).
    links_inserted: int = 0
    #: ``adapters`` FK-target rows inserted (only with ``seed_adapters=True``).
    adapters_inserted: int = 0
    #: ``rows_read - (every row that produced an interface)``.
    skipped: int = 0
    #: ``skip reason -> count``; keys are drawn from :data:`SKIP_REASONS`.
    skipped_by_reason: dict[str, int] = field(default_factory=dict)
    #: ``"<tool>.<action>" -> count`` — the mapping table's coverage, so a rule
    #: that matched nothing is visible instead of merely unused.
    mapped_by_tool_action: dict[str, int] = field(default_factory=dict)
    #: ``family -> count`` of the rows that became capabilities.
    mapped_by_family: dict[str, int] = field(default_factory=dict)
    #: Adapter codes that contributed a capability (extraction order).
    adapters: tuple[str, ...] = ()

    @property
    def inserted(self) -> int:
        """Every row this run created, across the four seeded tables."""
        return (
            self.tools_inserted
            + self.interfaces_inserted
            + self.capabilities_inserted
            + self.links_inserted
            + self.adapters_inserted
        )

    @property
    def updated(self) -> int:
        """Every row this run refreshed in place, across the three seeded tables."""
        return self.tools_updated + self.interfaces_updated + self.capabilities_updated

    @property
    def capabilities(self) -> int:
        """Distinct capability rows this run wrote — what the loader will read.

        Counted **once per slot**: a within-run collapse re-upserts a slot an
        earlier row of the same run created, so counting writes instead of slots
        would report one row more than the table holds.
        """
        return self.slots_written

    def to_payload(self) -> dict[str, Any]:
        """JSON-safe projection (dicts sorted, so two runs compare byte for byte)."""
        return {
            "rows_read": self.rows_read,
            "tools_inserted": self.tools_inserted,
            "tools_updated": self.tools_updated,
            "interfaces_inserted": self.interfaces_inserted,
            "interfaces_updated": self.interfaces_updated,
            "capabilities_inserted": self.capabilities_inserted,
            "capabilities_updated": self.capabilities_updated,
            "slots_written": self.slots_written,
            "collapsed_rows": self.collapsed_rows,
            "links_inserted": self.links_inserted,
            "adapters_inserted": self.adapters_inserted,
            "skipped": self.skipped,
            "skipped_by_reason": dict(sorted(self.skipped_by_reason.items())),
            "mapped_by_tool_action": dict(sorted(self.mapped_by_tool_action.items())),
            "mapped_by_family": dict(sorted(self.mapped_by_family.items())),
            "collapsed": {code: list(codes) for code, codes in sorted(self.collapsed.items())},
            "adapters": list(self.adapters),
        }


class _Counters:
    """Mutable tallies for one seed; never leaves this module."""

    def __init__(self) -> None:
        self.skipped: int = 0
        self.skipped_by_reason: dict[str, int] = {}
        self.mapped_by_tool_action: dict[str, int] = {}
        self.mapped_by_family: dict[str, int] = {}
        self.collapsed: dict[str, list[str]] = {}
        #: Slots this run wrote at least one row into, counted once each.
        self.slots_written: set[tuple[str, str]] = set()

    def skip(self, reason: str) -> None:
        """Record one extracted row that did not become a capability."""
        self.skipped += 1
        self.skipped_by_reason[reason] = self.skipped_by_reason.get(reason, 0) + 1

    def mapped(self, family: str, tool: str, action: str) -> None:
        """Record one capability the mapping table produced."""
        key = f"{tool}.{action}"
        self.mapped_by_tool_action[key] = self.mapped_by_tool_action.get(key, 0) + 1
        self.mapped_by_family[family] = self.mapped_by_family.get(family, 0) + 1

    def collapse(self, code: str, interface_code: str) -> None:
        """Record one more extracted row that landed on an occupied slot."""
        self.collapsed.setdefault(code, []).append(interface_code)

    def written(self, slot: tuple[str, str]) -> None:
        """Record that this run wrote ``slot`` (idempotent — a set, not a counter)."""
        self.slots_written.add(slot)


# ---------------------------------------------------------------------------
# Reading the extraction
# ---------------------------------------------------------------------------
def _text(value: Any) -> str | None:
    """Stripped string, or ``None`` when absent / blank / not a string."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _row_annotation(raw: Mapping[str, Any]) -> tuple[str | None, str | None]:
    """``(description, annotation_source)`` of one extracted row (总纲 §4.2.13).

    ``description`` is the extraction's Chinese annotation
    (``name_zh + "：" + description_zh``, or ``name_zh`` alone) and
    ``metadata_json.annotation_source`` says whether the manual shipped that name or
    ``title_zh.json`` supplied it.  Both are copied **verbatim**: this seeder never
    composes an annotation, and an absent one stays ``None`` so the caller can leave
    an existing value alone instead of writing a blank over it.
    """
    annotation = _text(raw.get("description"))
    extraction = raw.get("metadata_json")
    source = (
        _text(extraction.get("annotation_source"))
        if isinstance(extraction, Mapping)
        else None
    )
    return annotation, source


def _normalise_resource(value: str) -> str:
    """Lower-case and ``-`` -> ``_``.

    Mirrors :func:`app.mcp.capabilities._normalise`, which ``resolve()`` applies
    to the caller's resource before building the code — so a resource stored as
    ``actl-m1`` would be looked up as ``actl_m1`` and never found.
    """
    return value.strip().lower().replace("-", "_")


def _family_of(endpoint: str) -> str:
    """First path segment of an endpoint (``/db/NODE`` -> ``db``)."""
    parts = [part for part in endpoint.split("/") if part]
    return parts[0].lower() if parts else ""


def _endpoint_slug(endpoint: str) -> str:
    """Last path segment of an endpoint, normalised (``/doc/ANAL`` -> ``anal``)."""
    parts = [part for part in endpoint.split("/") if part]
    return _normalise_resource(parts[-1]) if parts else ""


def _interface_parts(interface_code: str) -> tuple[str, str, list[str], str] | None:
    """Split ``{adapter}.{family}.{path…}.{operation}`` (V2.1 §17.4).

    Returns ``(adapter, family, path-segments, operation)``, or ``None`` when the
    code does not have the documented shape.  The method is folded into the code
    (``meta.row_identity``), so the operation is always the last segment and the
    path is everything between the family and it.
    """
    parts = [part for part in interface_code.split(".") if part]
    if len(parts) < 4:
        return None
    return parts[0], parts[1].lower(), parts[2:-1], parts[-1].lower()


def derive_resource_alias() -> dict[str, str]:
    """``/db/<RES>`` -> MCP singular resource name, from the **static declaration**.

    总纲 §0.4: the alias is not a new literal, it is the mapping the capability
    table already carries (``_QUERY_DATA_TARGETS`` / ``_MODEL_RESOURCES``:
    ``/db/ELEM`` -> ``element``, ``/db/CNLD`` -> ``load``, …).  Keyed by
    **endpoint**, not by resource name, so ``/design/SECT`` does not inherit
    ``/db/SECT``'s ``section`` — they are different endpoints.
    """
    alias: dict[str, str] = {}
    for row in capability_rows():
        endpoint = row.endpoint
        if endpoint is None or not endpoint.lower().startswith("/db/"):
            continue
        # ``midas_task``'s rows carry no /db endpoint, but a future platform row
        # might; the resource must come from a MIDAS-facing row.
        if row.tool == TOOL_TASK:
            continue
        alias.setdefault(endpoint, row.resource)
    return alias


def capability_slot(resource: str, action: str) -> str:
    """The ``capabilities.capability_code`` of one row (V2.1 §17.4).

    ``"<resource>.<action>"`` — the MCP-facing code, **not** the extraction's
    ``interface_code``.  ``midas_gen.db.cnld.create`` therefore becomes
    ``load.create``, which is the code ``resolve("midas_model", "create",
    "load")`` looks up.
    """
    return f"{resource}.{action}"


@dataclass(frozen=True)
class ClassifiedRow:
    """One extracted row, parsed and classified — the seeder's unit of work.

    Every field is either copied from the extraction or derived from the code's
    own declarations; ``extra_capabilities`` carries the additional
    ``(resource, action)`` pairs a shared endpoint serves (``/doc/ANAL`` is both
    ``model.calculate`` and ``analysis.analysis`` in the static declaration), which
    become ``capability_interfaces`` links rather than a second interface row.
    """

    adapter_code: str
    interface_code: str
    endpoint: str
    method: str
    #: The extraction's own operation verb, stored verbatim in
    #: ``tool_interfaces.operation``.
    operation: str
    family: str
    #: The MCP resource the capability is keyed by.
    resource: str
    tool: str
    action: str
    #: ``(resource, action)`` of the static execute declaration, when this row
    #: came from :data:`EXECUTE_ENDPOINT_CAPABILITIES`.
    execute_key: tuple[str, str] | None = None
    #: Further ``(resource, action)`` pairs the same interface serves.
    extra_capabilities: tuple[tuple[str, str], ...] = ()

    @property
    def capability_code(self) -> str:
        """``capabilities.capability_code`` — ``"<resource>.<action>"`` (V2.1 §17.4)."""
        return capability_slot(self.resource, self.action)


def classify_row(row: Mapping[str, Any], alias: Mapping[str, str]) -> ClassifiedRow:
    """Classify one extracted row, or raise :class:`ValueError` with a skip reason.

    The exception's message **is** the reason, and it is always a member of
    :data:`SKIP_REASONS` — so a caller can count it directly.  Nothing here
    invents a tool, an action or an endpoint: an unmappable row fails loudly
    instead of being given a plausible-looking value.
    """
    adapter = _text(row.get("adapter_code"))
    interface_code = _text(row.get("interface_code"))
    endpoint = _text(row.get("endpoint"))
    method = (_text(row.get("method")) or "").upper()
    operation = (_text(row.get("operation")) or "").lower()

    if not adapter or not interface_code or not endpoint or not method or not operation:
        raise ValueError(SKIP_MISSING_REQUIRED_FIELD)
    if method not in _HTTP_METHODS:
        raise ValueError(SKIP_UNSUPPORTED_METHOD)

    parts = _interface_parts(interface_code)
    if parts is None:
        raise ValueError(SKIP_MALFORMED_ROW)
    code_adapter, code_family, path_segments, code_operation = parts
    family = _family_of(endpoint)
    if family not in KNOWN_FAMILIES:
        raise ValueError(SKIP_UNKNOWN_FAMILY)
    if code_adapter != adapter or code_family != family or code_operation != operation:
        # ``interface_code`` and the row's own columns must agree; a mismatch is
        # a malformed extraction row, not something to paper over.
        raise ValueError(SKIP_MALFORMED_ROW)

    # ``/doc/*`` / ``/ope/*`` / ``/view/*`` / ``/rating/*``: a read is still a
    # read, but a write is a software action and is endpoint-keyed (ruling 3).
    if family in EXECUTE_FAMILIES and operation in _WRITE_OPERATIONS:
        return _classify_execute(
            adapter, interface_code, endpoint, method, operation, family, path_segments
        )

    rule = _rule_for(family, operation)
    if rule is None:
        raise ValueError(SKIP_UNSUPPORTED_OPERATION)
    tool, action = rule
    resource = _resource_for(family, path_segments, endpoint, alias)
    if not resource:
        raise ValueError(SKIP_MALFORMED_ROW)
    return ClassifiedRow(
        adapter_code=adapter,
        interface_code=interface_code,
        endpoint=endpoint,
        method=method,
        operation=operation,
        family=family,
        resource=resource,
        tool=tool,
        action=action,
    )


def _classify_execute(
    adapter: str,
    interface_code: str,
    endpoint: str,
    method: str,
    operation: str,
    family: str,
    path_segments: Sequence[str],
) -> ClassifiedRow:
    """The ``midas_execute`` half — endpoint-keyed (ruling 3 of the docstring)."""
    slug = _endpoint_slug(endpoint)
    pairs = EXECUTE_ENDPOINT_CAPABILITIES.get((family, slug))
    if pairs is not None and method == "POST":
        # The first pair is the primary interface; the rest become
        # ``capability_interfaces`` links (裁决 B-3: one endpoint may serve
        # several capabilities, one capability may need several endpoints).
        resource, action = pairs[0]
        return ClassifiedRow(
            adapter_code=adapter,
            interface_code=interface_code,
            endpoint=endpoint,
            method=method,
            operation=operation,
            family=family,
            resource=resource,
            tool=TOOL_EXECUTE,
            action=action,
            execute_key=(resource, action),
            extra_capabilities=pairs[1:],
        )
    # A GET on a ``/doc/*`` endpoint is a read (``/doc/UNIT``, ``/doc/ACTIVE``):
    # the family rule of the module docstring maps reads to ``midas_query`` even
    # here, because a read is not a software action.
    rule = _rule_for(family, operation)
    if rule is not None and rule[0] == TOOL_QUERY:
        tool, action = rule
        resource = _resource_for(family, path_segments, endpoint, {})
        if not resource:
            raise ValueError(SKIP_MALFORMED_ROW)
        return ClassifiedRow(
            adapter_code=adapter,
            interface_code=interface_code,
            endpoint=endpoint,
            method=method,
            operation=operation,
            family=family,
            resource=resource,
            tool=tool,
            action=action,
        )
    raise ValueError(SKIP_EXECUTE_UNMAPPED)


def _resource_for(
    family: str,
    path_segments: Sequence[str],
    endpoint: str,
    alias: Mapping[str, str],
) -> str:
    """The MCP resource of one row.

    ==================  ====================================================
    case                resource
    ==================  ====================================================
    ``/db/NODE``        ``node`` — the static declaration's own alias
    ``/db/ACTL-M1``     ``actl_m1`` — no alias, so the MIDAS code itself
    ``/post/TABLE``     the ``TABLE_TYPE`` slug (``beam_force`` …), because
                        the URI is shared by hundreds of logical tables
    ``/design/**``      ``<path…>`` joined, so ``/design/RC/…/rebb`` cannot
                        collide with another design code's ``rebb``
    ==================  ====================================================

    The alias is tried **first** for ``/db/*`` only: it is what makes the seeded
    row land on the static slot (``node.get``, ``load.create``, …).
    """
    if family == "db":
        alias_resource = alias.get(endpoint)
        if alias_resource:
            return alias_resource

    if family in TABLE_FAMILIES and endpoint.lower().endswith("/table"):
        # ``path_segments`` already carries the table slug; a bare ``table``
        # segment is the shared-URI marker, not part of the identity.
        segments = [part for part in path_segments if part and part != "table"]
        return _normalise_resource("_".join(segments))
    if family == "design":
        # Keep the design-code prefix: ``didp`` exists under several design codes.
        return _normalise_resource("_".join(part for part in path_segments if part))
    parts = [part for part in endpoint.split("/") if part]
    return _normalise_resource(parts[-1]) if parts else ""


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------
def _upsert_tools(session: Session, counters: dict[str, int]) -> dict[str, int]:
    """Seed the four ``tools`` rows from the code's own declarations.

    ``tools.name`` / ``input_schema_json`` / ``display_name`` / ``description``
    come from :mod:`app.mcp.tools` (总纲 §0.4: V2.1 §7–§11 own the bodies), never
    from a literal here.  ``version`` is 总纲 裁决 C-5's ``'2.1'``, which is also
    the ORM default.
    """
    ids: dict[str, int] = {}
    for order, module in enumerate(TOOL_MODULES, start=1):
        name = str(module.TOOL_NAME)
        existing = session.scalar(select(ToolRow).where(ToolRow.name == name))
        schema_json = json.dumps(module.SCHEMA, ensure_ascii=False, sort_keys=True)
        if existing is None:
            existing = ToolRow(
                name=name,
                display_name=str(module.TITLE),
                description=str(module.DESCRIPTION),
                input_schema_json=schema_json,
                enabled=1,
                sort_order=order,
            )
            session.add(existing)
            session.flush()
            counters["tools_inserted"] += 1
        else:
            existing.display_name = str(module.TITLE)
            existing.description = str(module.DESCRIPTION)
            existing.input_schema_json = schema_json
            existing.sort_order = order
            counters["tools_updated"] += 1
        ids[name] = int(existing.id)
    return ids


def _adapter_scope(adapter_code: str) -> str | None:
    """``product_scope`` implied by an adapter code, or ``None``.

    ``midas_cdn`` -> ``cdn`` -> ``designer`` through
    :data:`app.core.constants.PRODUCT_SCOPE_BY_PRODUCT` — the two axes are not
    the same string, and mapping them by hand is how they drift.
    """
    product = adapter_code.removeprefix("midas_")
    return PRODUCT_SCOPE_BY_PRODUCT.get(product)


def _upsert_adapters(session: Session, codes: Sequence[str], counters: dict[str, int]) -> None:
    """Insert the ``adapters`` rows the ``adapter_code`` foreign keys need.

    ``capabilities.adapter_code`` and ``tool_interfaces.adapter_code`` are both
    foreign keys into ``adapters`` (V2.1 §4), so a seed against an empty database
    cannot succeed without them.  Only missing rows are inserted; an existing
    adapter is left exactly as the operator configured it.
    """
    for code in codes:
        if session.scalar(select(AdapterRow).where(AdapterRow.code == code)) is not None:
            continue
        scope = _adapter_scope(code)
        session.add(
            AdapterRow(
                code=code,
                name=code,
                software=f"MIDAS {scope or code.removeprefix('midas_')}",
                implementation="app.adapters.midas_gen.adapter:MidasNxAdapter",
                capabilities_json=None,
            )
        )
        session.flush()
        counters["adapters_inserted"] += 1


def _link(
    session: Session,
    links: set[tuple[int, int]],
    counts: dict[str, int],
    *,
    capability: CapabilityRow,
    interface: ToolInterfaceRow,
) -> bool:
    """Insert one ``capability_interfaces`` link (裁决 B-3); ``True`` when new."""
    key = (int(capability.id), int(interface.id))
    if key in links:
        return False
    session.add(CapabilityInterfaceRow(capability_id=key[0], interface_id=key[1]))
    links.add(key)
    counts["links_inserted"] += 1
    return True


def _annotation_source_of(row: CapabilityRow) -> str | None:
    """``constraints_json.annotation_source`` of a stored capability row, or ``None``.

    ``capabilities.constraints_json`` is the capability level's **only** JSON column
    (``capability_loader``'s precedence table), so that is where the annotation's
    provenance lives.  An unparseable blob is ignored rather than raised: this reads
    a value this module wrote, and one bad blob must not cost a row.
    """
    raw = row.constraints_json
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(parsed, Mapping):
        return None
    return _text(parsed.get("annotation_source"))


def _upsert_capability(
    session: Session,
    capabilities: dict[tuple[str, str], CapabilityRow],
    counts: dict[str, int],
    counters: _Counters,
    *,
    classified: ClassifiedRow,
    interface: ToolInterfaceRow,
    tool_ids: Mapping[str, int],
    resource: str,
    action: str,
    execute_key: tuple[str, str] | None,
    first_of_slot: bool,
    preexisting: frozenset[tuple[str, str]],
    raw: Mapping[str, Any],
) -> CapabilityRow:
    """Insert or refresh one ``capabilities`` row (V2.1 §16.1).

    ``tool_id`` comes from the code's own ``TOOL_NAMES`` -> ``tools`` mapping
    (总纲 §4.2.12), never from ``tool_interfaces.tool_id`` (which is NULL).
    ``constraints_json`` carries only the fields ``Capability`` has no column for
    — ``adapter_action`` and ``task_type`` (for the execute rows the static
    declaration already classifies) and the annotation's ``annotation_source``
    (总纲 §4.2.13; the loader ignores keys it does not know).

    The three counters are separated by *when* the slot was occupied, decided
    before this call writes anything: a slot that already held a row when the run
    began is a refresh (``capabilities_updated``), a slot this run has already
    written is a collapse (``collapsed_rows``), and anything else is an insert.
    Without that split, ``inserted + updated`` would exceed the rows the database
    actually holds.
    """
    code = capability_slot(resource, action)
    key = (classified.adapter_code, code)
    existing = capabilities.get(key)

    # --- the Chinese annotation (总纲 §4.2.13) ------------------------------
    # ``capabilities.description`` is the annotation's documented home (the loader
    # maps it to ``Capability.notes``, which ``capability_payload`` exposes to the
    # LLM).  Two rules, and both are order-independent so a second run cannot flip
    # the value:
    #
    # 1. a ``null`` annotation **never** clobbers a value that is already there —
    #    the extraction is authoritative for what it states and silent about what it
    #    does not, so a curated description survives an unannotated refresh;
    # 2. the row that owns the slot's primary interface owns its annotation, exactly
    #    as it owns ``interface_id``.  A row that collapsed onto the slot keeps what
    #    is there (or fills a gap), so the primary's annotation wins whichever order
    #    the extracted rows arrive in — and on a re-run the owner still recognises
    #    itself through ``interface_id``, which is why the file can refresh the value
    #    instead of freezing the first run's.
    annotation, annotation_source = _row_annotation(raw)
    previous_source = _annotation_source_of(existing) if existing is not None else None
    owns_annotation = existing is None or existing.description is None or (
        existing.interface_id is not None
        and int(existing.interface_id) == int(interface.id)
    )
    if annotation is None or not owns_annotation:
        description = existing.description if existing is not None else None
        annotation_source = previous_source
    else:
        description = annotation
    if description is None:
        # 没有注释就没有来源：两者一起出现，一起缺席（抽取层的自校验也断言这一条）。
        annotation_source = None

    constraints: dict[str, Any] = {}
    if execute_key is not None:
        adapter_action, task_type = _EXECUTE_ROW_FIELDS.get(execute_key, (None, None))
        if adapter_action is not None:
            constraints["adapter_action"] = adapter_action
        if task_type is not None:
            constraints["task_type"] = task_type
    if annotation_source is not None:
        constraints["annotation_source"] = annotation_source
    constraints_json = (
        json.dumps(constraints, ensure_ascii=False, sort_keys=True) if constraints else None
    )

    was_occupied = key in capabilities
    counters.written(key)
    if was_occupied:
        if key in preexisting:
            counts["capabilities_updated"] += 1
        else:
            counts["collapsed_rows"] += 1
    if existing is None:
        existing = CapabilityRow(
            tool_id=tool_ids[classified.tool],
            adapter_code=classified.adapter_code,
            capability_code=code,
            resource=resource,
            action=action,
            description=description,
            interface_id=int(interface.id),
            enabled=1,
            constraints_json=constraints_json,
        )
        session.add(existing)
        session.flush()
        capabilities[key] = existing
        counts["capabilities_inserted"] += 1
        return existing

    # The first extracted row of a slot owns the primary interface link; a later
    # row that collapsed onto it must **not** steal it, or a second run would
    # change which endpoint the capability dispatches to.
    if first_of_slot:
        existing.interface_id = int(interface.id)
    existing.tool_id = tool_ids[classified.tool]
    existing.resource = resource
    existing.action = action
    existing.description = description
    existing.constraints_json = constraints_json
    return existing


def seed_interfaces(
    session_factory: Callable[[], Session] | None = None,
    *,
    path: Path | None = None,
    seed_adapters: bool = True,
) -> SeedResult:
    """Seed ``tools`` / ``tool_interfaces`` / ``capabilities`` from the extraction.

    :param session_factory: zero-argument callable returning a ``Session``
        (a ``sessionmaker``).  ``None`` selects the process-wide
        :func:`app.db.session.SessionLocal`, imported lazily so importing this
        module does not build an engine.
    :param path: the extraction file; ``None`` selects
        :func:`default_interfaces_path`.
    :param seed_adapters: insert the missing ``adapters`` rows the foreign keys
        need.  ``False`` requires the caller to have provided them.

    Idempotent: every row is matched by its natural key and refreshed in place,
    so a second call inserts nothing.  Never raises for a single bad row — a
    malformed row is counted under :data:`SKIP_MALFORMED_ROW` and the seed
    continues; only a failure of the query itself propagates, because that is an
    infrastructure fault rather than a bad row.
    """
    payload = load_interfaces(path)
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("interfaces.json: 'rows' 不是数组")

    alias = derive_resource_alias()
    counters = _Counters()
    counts: dict[str, int] = {
        "tools_inserted": 0,
        "tools_updated": 0,
        "interfaces_inserted": 0,
        "interfaces_updated": 0,
        "capabilities_inserted": 0,
        "capabilities_updated": 0,
        "collapsed_rows": 0,
        "links_inserted": 0,
        "adapters_inserted": 0,
    }
    adapters: list[str] = []

    factory = session_factory if session_factory is not None else _default_session_factory()
    with session_scope_for(factory) as session:
        tool_ids = _upsert_tools(session, counts)

        seen_adapters = sorted(
            {
                adapter
                for adapter in (
                    _text(row.get("adapter_code")) for row in rows if isinstance(row, Mapping)
                )
                if adapter
            }
        )
        if seed_adapters:
            _upsert_adapters(session, seen_adapters, counts)

        #: ``(adapter_code, interface_code) -> row`` for this session.
        interfaces: dict[tuple[str, str], ToolInterfaceRow] = {
            (str(row.adapter_code), str(row.interface_code)): row
            for row in session.scalars(select(ToolInterfaceRow)).all()
        }
        #: ``(adapter_code, capability_code) -> row``.
        capabilities: dict[tuple[str, str], CapabilityRow] = {
            (str(row.adapter_code or ""), str(row.capability_code)): row
            for row in session.scalars(select(CapabilityRow)).all()
        }
        #: The slots that already held a row **before** this run: a write to one of
        #: them is a refresh, a write to any other occupied slot is a collapse.
        preexisting: frozenset[tuple[str, str]] = frozenset(capabilities)
        links: set[tuple[int, int]] = {
            (int(link.capability_id), int(link.interface_id))
            for link in session.scalars(select(CapabilityInterfaceRow)).all()
        }

        for raw in rows:
            if not isinstance(raw, Mapping):
                counters.skip(SKIP_MALFORMED_ROW)
                continue
            try:
                classified = classify_row(raw, alias)
            except ValueError as exc:  # the message **is** the reason
                counters.skip(str(exc) if str(exc) in SKIP_REASONS else SKIP_MALFORMED_ROW)
                continue
            except Exception:  # noqa: BLE001 — 「Never raise on a single bad row」
                counters.skip(SKIP_MALFORMED_ROW)
                continue

            adapter = classified.adapter_code
            slot = (adapter, classified.capability_code)
            first_of_slot = slot not in capabilities
            try:
                interface = _upsert_interface(
                    session,
                    interfaces,
                    counts,
                    adapter_code=adapter,
                    interface_code=classified.interface_code,
                    endpoint=classified.endpoint,
                    method=classified.method,
                    operation=classified.operation,
                    resource=classified.resource,
                    raw=raw,
                )
                capability = _upsert_capability(
                    session,
                    capabilities,
                    counts,
                    counters,
                    classified=classified,
                    interface=interface,
                    tool_ids=tool_ids,
                    resource=classified.resource,
                    action=classified.action,
                    execute_key=classified.execute_key,
                    first_of_slot=first_of_slot,
                    preexisting=preexisting,
                    raw=raw,
                )
                if not first_of_slot:
                    counters.collapse(classified.capability_code, classified.interface_code)
                _link(
                    session,
                    links,
                    counts,
                    capability=capability,
                    interface=interface,
                )
                # A shared endpoint may serve several capabilities (裁决 B-3):
                # ``/doc/ANAL`` is both ``model.calculate`` and ``analysis.analysis``
                # in the static declaration.  The extra rows share the one
                # interface and get a link each, so the loader's B-3 fallback can
                # resolve them.
                for resource, action in classified.extra_capabilities:
                    extra = _upsert_capability(
                        session,
                        capabilities,
                        counts,
                        counters,
                        classified=classified,
                        interface=interface,
                        tool_ids=tool_ids,
                        resource=resource,
                        action=action,
                        execute_key=(resource, action),
                        # An extra pair is a **second capability on one interface**,
                        # not a collapse: it owns its own primary link.
                        first_of_slot=True,
                        preexisting=preexisting,
                        raw=raw,
                    )
                    _link(
                        session,
                        links,
                        counts,
                        capability=extra,
                        interface=interface,
                    )
                    counters.mapped(classified.family, classified.tool, action)
            except Exception:  # noqa: BLE001 — see the docstring
                counters.skip(SKIP_MALFORMED_ROW)
                continue

            counters.mapped(classified.family, classified.tool, classified.action)
            if adapter not in adapters:
                adapters.append(adapter)

    return SeedResult(
        rows_read=len(rows),
        tools_inserted=counts["tools_inserted"],
        tools_updated=counts["tools_updated"],
        interfaces_inserted=counts["interfaces_inserted"],
        interfaces_updated=counts["interfaces_updated"],
        capabilities_inserted=counts["capabilities_inserted"],
        capabilities_updated=counts["capabilities_updated"],
        slots_written=len(counters.slots_written),
        collapsed_rows=counts["collapsed_rows"],
        links_inserted=counts["links_inserted"],
        adapters_inserted=counts["adapters_inserted"],
        skipped=counters.skipped,
        skipped_by_reason=dict(sorted(counters.skipped_by_reason.items())),
        mapped_by_tool_action=dict(sorted(counters.mapped_by_tool_action.items())),
        mapped_by_family=dict(sorted(counters.mapped_by_family.items())),
        collapsed={code: tuple(codes) for code, codes in sorted(counters.collapsed.items())},
        adapters=tuple(adapters),
    )


def _upsert_interface(
    session: Session,
    interfaces: dict[tuple[str, str], ToolInterfaceRow],
    counts: dict[str, int],
    *,
    adapter_code: str,
    interface_code: str,
    endpoint: str,
    method: str,
    operation: str,
    resource: str,
    raw: Mapping[str, Any],
) -> ToolInterfaceRow:
    """Insert or refresh one ``tool_interfaces`` row (V2.1 §17.1).

    ``tool_id`` is deliberately **NULL**: 裁决 B-3 makes the column nullable so
    one endpoint can serve several tools, and leaving it NULL is what keeps
    ``capabilities.tool_id`` the only source of a capability's tool (总纲 §4.2.12).

    ``request_schema_json`` is deliberately NULL: the extraction's value is an
    **API request body** (a manual example 594/604 times), not the MCP payload the
    second validation of V2.1 §6.2 / §9.3 checks.  It is preserved under
    ``metadata_json.extraction_request_schema`` for traceability — see the module
    docstring.
    """
    key = (adapter_code, interface_code)
    metadata = _interface_metadata(raw, resource)
    existing = interfaces.get(key)
    if existing is None:
        existing = ToolInterfaceRow(
            tool_id=None,
            adapter_code=adapter_code,
            interface_code=interface_code,
            method=method,
            endpoint=endpoint,
            request_wrapper=_text(raw.get("request_wrapper")),
            response_root_key=_text(raw.get("response_root_key")),
            operation=operation,
            resource=resource,
            product_scope=str(_text(raw.get("product_scope")) or "unknown"),
            domain=_text(raw.get("domain")),
            feature=_text(raw.get("feature")),
            request_schema_json=None,
            response_schema_json=None,
            enabled=1,
            async_supported=0,
            metadata_json=metadata,
        )
        session.add(existing)
        session.flush()
        interfaces[key] = existing
        counts["interfaces_inserted"] += 1
        return existing

    existing.tool_id = None
    existing.method = method
    existing.endpoint = endpoint
    existing.request_wrapper = _text(raw.get("request_wrapper"))
    existing.response_root_key = _text(raw.get("response_root_key"))
    existing.operation = operation
    existing.resource = resource
    existing.product_scope = str(_text(raw.get("product_scope")) or "unknown")
    existing.domain = _text(raw.get("domain"))
    existing.feature = _text(raw.get("feature"))
    existing.metadata_json = metadata
    counts["interfaces_updated"] += 1
    return existing


def _interface_metadata(raw: Mapping[str, Any], resource: str) -> str:
    """``tool_interfaces.metadata_json`` — provenance, never a dispatch override.

    The keys are the extraction's own provenance plus the
    ``extraction_request_schema`` this seeder refuses to use as a payload schema,
    and the annotation's provenance (总纲 §4.2.13): ``annotation_source`` and the
    ``annotation_key`` the glossary matched, so the unwrapping is auditable at the
    interface level as well as on the capability row.  **No** ``dispatch`` key is
    written: a dispatch override would assert a value the loader's own rule table
    cannot derive, which is what :data:`SKIP_EXECUTE_UNMAPPED` exists to refuse.
    """
    extraction = raw.get("metadata_json")
    source = extraction if isinstance(extraction, Mapping) else {}
    meta: dict[str, Any] = {
        "seeded_by": "app.db.seed_interfaces",
        "resource": resource,
        "source_manual": source.get("source_manual"),
        "source_section": source.get("source_section"),
        "source_chapter": source.get("source_chapter"),
        "source_line": source.get("source_line"),
        "source_title": source.get("source_title"),
        "source_code": source.get("source_code"),
        "schema_source": source.get("schema_source"),
        "documented_methods": source.get("documented_methods"),
        "merged_records": source.get("merged_records"),
        "interface_code_disambiguation": source.get("interface_code_disambiguation"),
        "annotation_source": source.get("annotation_source"),
        "annotation_key": source.get("annotation_key"),
    }
    request_schema = raw.get("request_schema_json")
    if request_schema is not None:
        meta["extraction_request_schema"] = request_schema
    return json.dumps(meta, ensure_ascii=False, sort_keys=True)


def _default_session_factory() -> Callable[[], Session]:
    """The process-wide ``SessionLocal``, imported **lazily**.

    :mod:`app.db.session` builds an engine at import time; this module is imported
    by tests and by a CLI, so that side effect stays inside the function that
    needs a database.
    """
    from app.db.session import SessionLocal

    return SessionLocal
