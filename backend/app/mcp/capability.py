"""Capability Resolver — V2.1 §16.

``CapabilityResolver.resolve(adapter_code, tool, action, resource)`` is the
**only** door from an MCP tool call to an adapter (V2.1 §16 「MCP 层不能直接调用
Endpoint」).  It answers four questions, in order:

1. does ``(tool, action, resource)`` name a capability at all
   (:mod:`app.mcp.capabilities`)?
2. is that capability **enabled** (``capabilities.enabled``, V2.1 §16.1)?
3. is the owning adapter **registered** and **enabled**
   (``adapters.code`` / ``adapters.status``, V2.1 §16.1)?
4. does the capability's ``product_scope`` admit **this instance's product**
   (总纲 §4.9.2 闸 4 / §4.2.11)?

Questions 1–3 are gates 1–3 of the routing framework (instance → adapter →
capability); question 4 is gate 4 and it is the last thing this module does, so a
returned row has passed **all four**.  ``product_scope='unknown'`` is admitted
optimistically — the ruling of 总纲 §4.2.11 — carrying an ``unverified`` warning
(see :func:`product_scope_warnings`).  Platform-owned capabilities
(``adapter_code is None``: the seven ``midas_task`` rows) have no instance and no
product, so gate 4 is **skipped** for them (总纲 §4.9.2 末段).

Resolution failures map onto the closed set of 总纲 §4.4 exactly as V2.1 §16.2
prescribes:

===============================  ==========================
情形                              错误码
===============================  ==========================
Adapter 未注册                    ``ADAPTER_NOT_FOUND``
Adapter 不可用                    ``ADAPTER_UNAVAILABLE``
MIDAS Client 未连接               ``CLIENT_NOT_CONNECTED``
软件/版本不支持该能力              ``CAPABILITY_NOT_SUPPORTED``
产品范围不允许（闸 4）             ``CAPABILITY_NOT_SUPPORTED``
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

from typing import Any, Final

from app.adapters.base import AdapterMetadata, MidasAdapter
from app.adapters.errors import AdapterError
from app.adapters.registry import AdapterRegistry, get_registry
from app.core.constants import (
    AdapterStatus,
    MidasClientStatus,
    MidasProductScope,
    PRODUCT_SCOPE_BY_PRODUCT,
)
from app.core.errors import ErrorCode
from app.mcp.capabilities import (
    Capability,
    capability_rows,
    capability_table,
    is_enabled,
    resolve as resolve_capability,
)

__all__ = [
    "ADAPTER_CODE_PREFIX",
    "PRODUCT_SCOPE_UNVERIFIED_WARNING",
    "CapabilityResolver",
    "get_resolver",
    "reset_resolver",
    "instance_product",
    "instance_product_scope",
    "unverified_scope_warning",
]


# ---------------------------------------------------------------------------
# 闸 4 —— 产品范围过滤（总纲 §4.9.2 闸 4 / §4.2.11）
# ---------------------------------------------------------------------------
#: ``adapter_code`` 的命名约定前缀。
#:
#: ``f"midas_{product.value}"`` 是**文档化的**约定而非猜测：
#: :meth:`app.core.midas_config.MidasConnection.to_registry_row` 与
#: :attr:`app.adapters.midas_gen.adapter.MidasNxAdapter.code` 都按此生成，
#: 所以它是「实例 → 适配器」这一步留下的、可复算的痕迹。
ADAPTER_CODE_PREFIX: Final[str] = "midas_"

#: ``product_scope='unknown'`` 被乐观放行时随信封给出的警告（总纲 §4.2.11）。
#:
#: ``unknown`` 是**出厂默认值**，不是占位符：手册的产品标注不可信
#: （《对接规范》§3.5 第 15 条实测：手册声明「Civil 专属」的 47 个端点中，
#: **32 个在 Gen NX 上同样应答**），而 1,373 条端点无法一次探测完。
#: 裁决是「**乐观放行 + unverified 警告**」—— 在验证完成前把大量能力隐藏起来，
#: 比带警告放行更糟。  ``{code}`` / ``{product}`` 由
#: :func:`unverified_scope_warning` 填入。
PRODUCT_SCOPE_UNVERIFIED_WARNING: Final[str] = (
    "能力 {code} 的产品适用范围尚未对实机验证（product_scope='unknown'）："
    "按《总纲》§4.2.11 的裁决**乐观放行**（unverified 警告）；"
    "若本次调用失败，可能表示该能力在 {product} 上并不存在 —— "
    "手册的产品标注不可信（《对接规范》§3.5 第 15 条："
    "手册声明「Civil 专属」的 47 个端点中，32 个在 Gen NX 上同样应答）。"
)


def instance_product(
    adapter_code: str | None, adapter: MidasAdapter | None = None
) -> str | None:
    """``adapter_code`` 所属产品的 :class:`~app.core.midas_config.MidasProduct` 值。

    两个来源，按可靠性排序；都判不出时返回 ``None``：

    1. **适配器实例的 ``product`` 属性**（首选）。  V2.1 §13 的 Protocol 没有声明
       它（与 ``status`` / ``lifecycle`` 同样只存在于具体适配器上），因此按**可选
       属性**读取：存在即权威 —— :class:`MidasNxAdapter` 的 ``product`` 直接给出
       ``MidasProduct``，而它的 ``code`` 本来就是从同一个字段推导的。
    2. **``adapter_code`` 的命名约定** ``f"midas_{product.value}"``
       （:data:`ADAPTER_CODE_PREFIX`）：去掉前缀即 ``MidasProduct`` 的值。

    返回值**必须**是 :data:`PRODUCT_SCOPE_BY_PRODUCT` 的键之一 —— 该映射的键集合
    就是 ``MidasProduct`` 的封闭取值，所以「产品名拼错」与「判不出来」是同一件事，
    都返回 ``None`` 让调用方 fail closed（总纲 §4.9.2 闸 4）。
    本函数**不做** product → scope 的映射，那是 :func:`instance_product_scope`
    的职责：``MidasProduct.DESIGNER.value == "cdn"`` 而对应的 scope 是 ``"designer"``，
    两个轴不同名。
    """
    if adapter is not None:
        raw: Any = getattr(adapter, "product", None)
        value = getattr(raw, "value", raw)  # MidasProduct -> "cdn"
        if isinstance(value, str):
            candidate = value.strip().lower()
            if candidate in PRODUCT_SCOPE_BY_PRODUCT:
                return candidate
    if adapter_code and adapter_code.lower().startswith(ADAPTER_CODE_PREFIX):
        candidate = adapter_code[len(ADAPTER_CODE_PREFIX) :].strip().lower()
        if candidate in PRODUCT_SCOPE_BY_PRODUCT:
            return candidate
    return None


def instance_product_scope(
    adapter_code: str | None, adapter: MidasAdapter | None = None
) -> str | None:
    """该实例对应的 ``product_scope`` 值，判不出则 ``None``。

    ``midas_cdn`` -> ``"cdn"`` -> ``"designer"``：映射一律走
    :data:`app.core.constants.PRODUCT_SCOPE_BY_PRODUCT`（总纲 §4.2.11 的唯一真源），
    **不写字面量、不做恒等映射**。
    """
    product = instance_product(adapter_code, adapter)
    if product is None:
        return None
    return PRODUCT_SCOPE_BY_PRODUCT.get(product)


def unverified_scope_warning(
    capability: Capability,
    adapter_code: str | None,
    adapter: MidasAdapter | None = None,
) -> str | None:
    """``product_scope='unknown'`` 的信封警告，否则 ``None``。

    总纲 §4.2.11：``unknown`` 可见、可调用，但信封 ``warnings`` 中必须带一条
    「该端点的产品适用范围尚未实机验证」。 平台拥有的能力
    （``adapter_code`` 为空：``None`` 与 ``""`` 是同一个槽位）没有实例也没有产品，
    闸 4 整个不适用，因此没有警告。
    """
    if not adapter_code:
        return None
    if capability.product_scope != MidasProductScope.UNKNOWN.value:
        return None
    product = instance_product(adapter_code, adapter) or adapter_code
    return PRODUCT_SCOPE_UNVERIFIED_WARNING.format(
        code=capability.code, product=product
    )


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

        **Gate 4** (总纲 §4.9.2 闸 4) runs last: the capability's
        ``product_scope`` must admit this instance's product (§4.2.11).  It is the
        final check precisely because it needs the *selected instance*, which only
        exists after gates 1–3.  ``adapter_code=None`` (platform-owned rows) skips
        it — there is no instance to compare against.
        """
        capability = resolve_capability(tool, action, resource, adapter_code=adapter_code)
        self._require_enabled(capability)

        code = adapter_code or capability.adapter_code
        adapter: MidasAdapter | None = None
        if code is not None:
            adapter = self._require_registered(code)
            self._require_available(code, adapter)
            if self._require_connected:
                self._require_connected_lifecycle(code, adapter)
        self._require_product_scope(capability, adapter_code, adapter)
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
    def product_scope_warnings(
        self, capability: Capability, adapter_code: str | None = None
    ) -> list[str]:
        """Envelope warnings this capability earned at gate 4 (总纲 §4.2.11).

        Today exactly one case produces a warning: ``product_scope='unknown'`` was
        admitted **optimistically**, and the caller must be told that the endpoint's
        product applicability is unverified (see
        :data:`PRODUCT_SCOPE_UNVERIFIED_WARNING`).  A capability that passed gate 4
        with a *known* scope earns nothing — it was actually checked.

        The list is envelope-ready: ``DispatchContext.warnings`` (which the
        dispatcher merges into the MCP envelope's ``warnings``, 总纲 §4.3.2) takes
        exactly this shape.  ``adapter_code`` defaults to the row's own
        ``adapter_code``, which is the adapter the call was routed to, because
        resolution is keyed by it.

        Platform-owned rows (empty ``adapter_code``) return ``[]``: gate 4 does not
        apply to them (总纲 §4.9.2 末段).
        """
        code = capability.adapter_code if adapter_code is None else adapter_code
        if not code:
            return []
        adapter = self._registry.get(code) if code in self._registry else None

        warnings: list[str] = []

        # A scope that admits every product was **not** checked against the
        # instance, so an undeterminable product is not a refusal (see
        # `_require_product_scope`) — but it is still a configuration defect
        # worth surfacing, because the gate that *would* have applied to a
        # product-specific capability cannot be evaluated for this adapter.
        if capability.product_scope in (
            MidasProductScope.UNKNOWN.value,
            MidasProductScope.BOTH.value,
        ) and instance_product(code, adapter) is None:
            warnings.append(
                f"无法判定 adapter={code!r} 所属的 MIDAS 产品，因此本次调用**未经过**"
                "产品范围过滤（总纲 §4.9.2 闸 4）。能力 "
                f"{capability.code!r} 的 product_scope="
                f"{capability.product_scope!r} 容纳一切产品，故予以放行；"
                "但适配器 code 不合约定且未提供 product 属性属于**配置缺陷**，"
                "一旦该能力的 product_scope 收敛为具体产品，本适配器将无法调用它。"
            )

        warning = unverified_scope_warning(capability, code, adapter)
        if warning is not None:
            warnings.append(warning)
        return warnings

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

    def _require_product_scope(
        self,
        capability: Capability,
        adapter_code: str | None,
        adapter: MidasAdapter | None,
    ) -> None:
        """**闸 4** — ``product_scope`` 必须容纳该实例的产品（总纲 §4.9.2 闸 4）。

        ==================  ==============================================
        ``product_scope``   本实例（产品）上可用
        ==================  ==============================================
        ``gen``/``civil``/``designer``  仅当它等于本实例的 scope
        ``both``            任意（两个及以上产品均可用）
        ``unknown``         **乐观放行** + ``unverified`` 警告（§4.2.11 裁决）
        ==================  ==============================================

        与 §4.8.2 的权限检查**叠加**生效，而非替代：产品过滤是数据范围过滤，
        因此**不新增权限码、不新增错误码** —— 一律 ``CAPABILITY_NOT_SUPPORTED``
        （总纲 §4.2.11 末段 / §4.9.4）。

        **判不出实例产品时的处理，取决于这道闸有没有判定要做。**

        * ``gen`` / ``civil`` / ``designer`` —— 必须知道实例产品才能判定，
          判不出就**拒绝**（fail closed）：没执行过的安全闸不算通过。
        * ``both`` / ``unknown`` —— 容纳一切产品，**本就没有判定要做**，
          因此不因「判不出产品」而拒绝，改为**发出警告**。

        这个区分是有意的：判不出产品通常是**配置缺陷**（适配器 code 不合约定
        且无 ``product`` 属性），而把整个能力表——包括出厂即为 ``unknown`` 的
        全部行——一并拒掉，会让一个自定义适配器**全线不可用**。让缺陷以警告的
        形式可见，比让它以「什么都调不通」的形式可见更可用，同时不放松任何
        真正需要判定的场合。

        ``adapter_code`` 为空（``None`` / ``""`` —— 能力表把两者当作同一个槽位，
        见 :func:`app.mcp.capabilities._key`）时是平台拥有的 7 条 ``midas_task``，
        **整个跳过**：它们没有实例、没有产品（对接规范 §2.5.1：MIDAS 没有任务端点），
        在没有注册任何实例时也必须照常可用（总纲 §4.9.2 末段）。
        """
        if not adapter_code:
            return  # 平台拥有：无实例、无产品，闸 4 不适用

        scope = capability.product_scope
        if scope in (
            MidasProductScope.UNKNOWN.value,  # 乐观放行（§4.2.11 裁决）
            MidasProductScope.BOTH.value,  # 两个及以上产品均可用
        ):
            # Checked **before** the product lookup on purpose: these two admit
            # every product, so there is no decision to make and no need to know
            # the instance's product.  `product_scope_warnings` still reports an
            # undeterminable product as a warning.
            return

        product = instance_product(adapter_code, adapter)
        instance_scope = instance_product_scope(adapter_code, adapter)
        if product is None or instance_scope is None:
            raise AdapterError(
                ErrorCode.CAPABILITY_NOT_SUPPORTED,
                f"无法判定 adapter={adapter_code!r} 所属的 MIDAS 产品，"
                f"而能力 {capability.code!r} 的 product_scope="
                f"{capability.product_scope!r} 需要按产品判定，"
                "因此无法执行产品范围过滤（总纲 §4.9.2 闸 4）。"
                "adapter_code 的约定是 f'midas_{product.value}'"
                "（app/core/midas_config.py 的 to_registry_row / "
                "MidasNxAdapter.code），或由适配器实例的 product 属性给出；"
                "两者都判不出时拒绝（fail closed）——"
                "「实例无法识别」不是跳过**需要判定**的安全闸的理由。",
                details={
                    "reason": "instance_product_undeterminable",
                    "capability": capability.code,
                    "product_scope": capability.product_scope,
                    "instance_product": product,
                    "adapter_code": adapter_code,
                },
            )

        if scope == instance_scope:
            return

        # 已知的某个具体产品（gen / civil / designer）与本实例不符；
        # 任何其它取值都不是 §4.2.11 封闭集合的成员，同样 fail closed ——
        # 一个无法识别的 scope 值绝不能悄悄把闸门打开。
        reason = (
            "product_scope_mismatch"
            if scope in PRODUCT_SCOPE_BY_PRODUCT.values()
            else "product_scope_unrecognised"
        )
        raise AdapterError(
            ErrorCode.CAPABILITY_NOT_SUPPORTED,
            f"能力 {capability.code!r} 的 product_scope={scope!r} 不允许在 "
            f"{adapter_code!r}（产品 {product!r} -> scope {instance_scope!r}）上执行："
            "总纲 §4.9.2 闸 4 / §4.2.11 —— 该能力只在 "
            f"{scope!r} 上可用。MIDAS 侧不会替我们拦住这一点："
            "连 Gen 却调 Civil 专属端点只会得到 404，而正确行为是"
            "「该能力不适用于本产品」。",
            details={
                "reason": reason,
                "capability": capability.code,
                "product_scope": scope,
                "instance_product": product,
                "adapter_code": adapter_code,
            },
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
