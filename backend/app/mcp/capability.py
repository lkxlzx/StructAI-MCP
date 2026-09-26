"""Capability Resolver — V2.1 §16.

``CapabilityResolver.resolve(adapter_code, tool, action, resource)`` is the
**only** door from an MCP tool call to an adapter (V2.1 §16 「MCP 层不能直接调用
Endpoint」).  It answers three questions, in order:

1. does ``(tool, action, resource)`` name a capability at all
   (:mod:`app.mcp.capabilities`)?
2. is that capability **enabled** (``capabilities.enabled``, V2.1 §16.1)?
3. is the owning adapter **registered** and **enabled**
   (``adapters.code`` / ``adapters.status``, V2.1 §16.1)?

Resolution failures map onto the closed set of 总纲 §4.4 exactly as V2.1 §16.2
prescribes:

===============================  ==========================
情形                              错误码
===============================  ==========================
Adapter 未注册                    ``ADAPTER_NOT_FOUND``
Adapter 不可用                    ``ADAPTER_UNAVAILABLE``
MIDAS Client 未连接               ``CLIENT_NOT_CONNECTED``
软件/版本不支持该能力              ``CAPABILITY_NOT_SUPPORTED``
二级 Interface 未映射             ``INTERFACE_NOT_FOUND``
===============================  ==========================

V2.1 §16.2's closing rule is enforced by construction: this module has no code
path that returns an endpoint without a capability, so there is nothing to fall
back to.

Two deliberate deviations, both documented at the call site:

* ``INTERFACE_NOT_FOUND`` is not raised here.  V2.1 §17.4 makes
  ``interface_code`` a derived column of the same row (``node.create`` ->
  ``POST /db/NODE``), so "capability resolved but interface unmapped" cannot
  occur in this table; the code stays reserved for Phase 2, where
  ``capability_interfaces`` may resolve a capability to zero interfaces.
* The ``CLIENT_NOT_CONNECTED`` row is **opt-in** (``require_connected=True``),
  because ``midas_clients.status`` is not persisted yet: both shipped adapters
  start in a non-``CONNECTED`` lifecycle state and the connection registry
  belongs to the Service layer (V2.1 §26.3).  Phase 2 turns it on for
  write-class capabilities.
"""

from typing import Any

from app.adapters.base import AdapterMetadata, MidasAdapter
from app.adapters.errors import AdapterError
from app.adapters.registry import AdapterRegistry, get_registry
from app.core.constants import AdapterStatus, MidasClientStatus
from app.core.errors import ErrorCode
from app.mcp.capabilities import (
    Capability,
    capability_rows,
    capability_table,
    is_enabled,
    resolve as resolve_capability,
)

__all__ = ["CapabilityResolver", "get_resolver", "reset_resolver"]


class CapabilityResolver:
    """V2.1 §16 resolver over the static capability table + the adapter registry."""

    def __init__(
        self,
        registry: AdapterRegistry | None = None,
        *,
        require_connected: bool = False,
    ) -> None:
        #: V2.1 §21 registry.  Defaults to the process-wide singleton so the
        #: dispatcher and the REST/Service layer share one registration view.
        self._registry: AdapterRegistry = registry if registry is not None else get_registry()
        #: When True, an adapter whose lifecycle is not ``CONNECTED`` is refused
        #: with ``CLIENT_NOT_CONNECTED`` (V2.1 §16.2).  Off by default — see the
        #: module docstring.
        self._require_connected: bool = require_connected

    # ------------------------------------------------------------------ #
    @property
    def registry(self) -> AdapterRegistry:
        """The registry this resolver consults."""
        return self._registry

    # ------------------------------------------------------------------ #
    def resolve(
        self,
        adapter_code: str | None,
        tool: str,
        action: str,
        resource: str | None = None,
    ) -> Capability:
        """Resolve one call to its :class:`Capability`, or raise ``AdapterError``.

        :param adapter_code: ``adapters.code`` the call **must** go to
            (``"midas_gen"`` / ``"midas_civil"`` / ``"midas_cdn"``), normally
            derived from the selected ``midas_clients`` row.  ``None`` means the
            platform-owned rows (``midas_task``), where no MIDAS adapter is
            involved (对接规范 §2.5.1).
        :param tool: one of the four MCP tool names (v1.2 §37).
        :param action: the MCP action (V2.1 §6.3).
        :param resource: the MCP singular resource (总纲 §4.6.1); for
            ``midas_query`` this is the ``target`` (裁决 C-7).

        **Routing runs instance → adapter → capability**, so the lookup is keyed
        by ``adapter_code`` and a returned row is by construction one this
        adapter serves.  There used to be a second guard here comparing
        ``adapter_code`` against ``capability.adapter_code`` and refusing on a
        mismatch — that guard encoded the *reversed* direction (the capability
        decided the adapter) and it is what made a Civil-only deployment unable
        to call anything.  With the key fixed it is not merely redundant, it is
        wrong, so it is gone.
        """
        capability = resolve_capability(tool, action, resource, adapter_code=adapter_code)
        self._require_enabled(capability)

        code = adapter_code or capability.adapter_code
        if code is not None:
            adapter = self._require_registered(code)
            self._require_available(code, adapter)
            if self._require_connected:
                self._require_connected_lifecycle(code, adapter)
        return capability

    # ------------------------------------------------------------------ #
    def adapter_for(self, capability: Capability) -> MidasAdapter | None:
        """The registered adapter instance for ``capability``, or ``None``.

        ``None`` is a legitimate answer: ``midas_task`` is platform-owned
        (对接规范 §2.5.1 — MIDAS exposes no task API), so there is no adapter to
        call.
        """
        if capability.adapter_code is None:
            return None
        return self._registry.get(capability.adapter_code)

    def metadata_for(self, capability: Capability) -> AdapterMetadata | None:
        """Cached §15 metadata of the owning adapter, when registered."""
        if capability.adapter_code is None:
            return None
        return self._registry.metadata_of(capability.adapter_code)

    def capabilities_of(self, adapter_code: str | None = None) -> list[Capability]:
        """Every enabled capability, optionally filtered by ``adapter_code``.

        Backs ``midas_query target=capabilities`` (裁决 C-7).

        ``adapter_code=None`` spans **every** adapter — which is why this uses
        :func:`capability_rows` (a tuple that can hold the same ``code`` several
        times) rather than a code-keyed dict.  The same capability exists once
        per product, so a dict would silently collapse ``node.list`` for gen,
        civil and cdn into one row.
        """
        return [
            row
            for row in capability_rows()
            if is_enabled(row.code)
            and (adapter_code is None or row.adapter_code == adapter_code)
        ]

    # ------------------------------------------------------------------ #
    def _require_enabled(self, capability: Capability) -> None:
        """``capabilities.enabled`` (V2.1 §16.1)."""
        if not is_enabled(capability.code):
            raise AdapterError(
                ErrorCode.CAPABILITY_NOT_SUPPORTED,
                f"capability {capability.code!r} 已在 capabilities 表中禁用"
                "（V2.1 §16.2：软件/版本不支持该能力）。",
                details={"capability": capability.code},
            )

    def _require_registered(self, code: str) -> MidasAdapter:
        """``adapters.code`` must exist (V2.1 §16.2 -> ``ADAPTER_NOT_FOUND``)."""
        return self._registry.get(code)  # raises ADAPTER_NOT_FOUND

    @staticmethod
    def _require_available(code: str, adapter: MidasAdapter) -> None:
        """``adapters.status != 'disabled'`` (V2.1 §16.2 -> ``ADAPTER_UNAVAILABLE``).

        V2.1 §13's Protocol has no status accessor even though §14's mapping
        table requires one, so the optional ``status`` attribute is read and its
        absence means "enabled" — the same rule ``AdapterRegistry.resolve()``
        applies, kept identical on purpose.
        """
        status: Any = getattr(adapter, "status", None)
        value = getattr(status, "value", status)
        if value == AdapterStatus.DISABLED.value:
            raise AdapterError(
                ErrorCode.ADAPTER_UNAVAILABLE,
                f"adapter code={code!r} 已禁用（adapters.status='disabled'）"
                "（V2.1 §16.2 / §21）。",
                details={"adapter": code},
            )

    @staticmethod
    def _require_connected_lifecycle(code: str, adapter: MidasAdapter) -> None:
        """Opt-in ``CLIENT_NOT_CONNECTED`` gate (V2.1 §16.2)."""
        lifecycle: Any = getattr(adapter, "lifecycle", None)
        value = getattr(lifecycle, "value", lifecycle)
        if value in (None, "connected", "busy"):
            return
        raise AdapterError(
            ErrorCode.CLIENT_NOT_CONNECTED,
            f"adapter code={code!r} 尚未连接（lifecycle={value!r}）；"
            f"midas_clients.status 需为 {MidasClientStatus.CONNECTED.value!r}"
            "（V2.1 §16.2）。",
            details={"adapter": code, "lifecycle": value},
        )


# ---------------------------------------------------------------------------
# Process-wide singleton (mirrors ``get_registry()``)
# ---------------------------------------------------------------------------
_resolver: CapabilityResolver | None = None


def get_resolver() -> CapabilityResolver:
    """Process-wide :class:`CapabilityResolver`."""
    global _resolver
    if _resolver is None:
        _resolver = CapabilityResolver()
    return _resolver


def reset_resolver(resolver: CapabilityResolver | None = None) -> CapabilityResolver:
    """Replace the singleton (tests / reload)."""
    global _resolver
    _resolver = resolver if resolver is not None else CapabilityResolver()
    return _resolver
