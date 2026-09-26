"""Adapter layer — V2.1 §12–§22.

Public surface:

* :class:`~app.adapters.registry.AdapterRegistry` / :func:`~app.adapters.registry.get_registry`
  — §21 registry with the process-wide singleton.
* the base vocabulary — :class:`~app.adapters.base.MidasAdapter` Protocol,
  :class:`~app.adapters.base.AdapterMetadata` (§15),
  :class:`~app.adapters.base.AdapterRequest` + its three §18 subclasses,
  :class:`~app.adapters.base.AdapterResult` (§19),
  :class:`~app.adapters.base.AdapterLifecycle` (§14),
  :class:`~app.adapters.base.Capability`.
* :class:`~app.adapters.errors.AdapterError` and the three-layer
  :func:`~app.adapters.errors.normalize_upstream` (§20.4).
* the two adapters: :class:`~app.adapters.midas_gen.adapter.MidasNxAdapter` (real)
  and :class:`~app.adapters.mock.adapter.MockAdapter` (offline test double, §22).
"""

from app.adapters.base import (
    LIFECYCLE_DB_STATUS,
    LIFECYCLE_TRANSITIONS,
    AdapterLifecycle,
    AdapterMetadata,
    AdapterRequest,
    AdapterResult,
    Capability,
    ExecuteRequest,
    MidasAdapter,
    MidasClientConfig,
    ModelRequest,
    QueryRequest,
    can_transition,
)
from app.adapters.errors import (
    AMBIGUOUS_SUCCESS_MARKERS,
    ERROR_TEXT_MARKERS,
    AdapterError,
    ErrorTextMarker,
    UpstreamVerdict,
    is_error_body,
    normalize_upstream,
)
from app.adapters.midas_gen.adapter import (
    CAPABILITIES,
    DOCUMENTED_OUTER_KEY_MEANS,
    MANDATORY_WRITE_FIELDS,
    MidasCivilAdapter,
    MidasGenAdapter,
    MidasNxAdapter,
    build_assign,
    outer_key_means,
)
from app.adapters.mock.adapter import MockAdapter
from app.adapters.registry import AdapterRegistry, get_registry, reset_registry

__all__ = [
    # registry (§21)
    "AdapterRegistry",
    "get_registry",
    "reset_registry",
    # base types (§13–§19)
    "MidasAdapter",
    "MidasClientConfig",
    "AdapterLifecycle",
    "LIFECYCLE_DB_STATUS",
    "LIFECYCLE_TRANSITIONS",
    "can_transition",
    "AdapterMetadata",
    "AdapterRequest",
    "QueryRequest",
    "ModelRequest",
    "ExecuteRequest",
    "AdapterResult",
    "Capability",
    # errors (§20.4)
    "AdapterError",
    "UpstreamVerdict",
    "ErrorTextMarker",
    "ERROR_TEXT_MARKERS",
    "AMBIGUOUS_SUCCESS_MARKERS",
    "is_error_body",
    "normalize_upstream",
    # adapters
    "MidasNxAdapter",
    "MidasGenAdapter",
    "MidasCivilAdapter",
    "MockAdapter",
    # §4.1 outer-key semantics
    "DOCUMENTED_OUTER_KEY_MEANS",
    "MANDATORY_WRITE_FIELDS",
    "CAPABILITIES",
    "build_assign",
    "outer_key_means",
]
