"""Which MIDAS instance does this call go to?  (多产品多租户路由框架 §三)

**This module is the only place that answers that question**, and it is
deliberately the only place allowed to refuse on ambiguity.  Getting it wrong
does not produce an error — it produces a *successful* call against the wrong
product, which corrupts data silently.  That asymmetry is why the rules here are
strict and why none of them falls back to a default.

The routing chain is **instance → adapter → capability**:

1. :func:`select_adapter_code` — which adapter this call must go to;
2. ``CapabilityResolver.resolve(adapter_code, …)`` — does *that* adapter serve
   the requested ``(tool, action, resource)``?

It is deliberately *not* ``capability → adapter``.  The reversed direction was
the original bug: capabilities were hardcoded to ``midas_gen``, so a Civil-only
deployment could not call anything, and with several products registered a call
without an explicit adapter silently went to Gen.
"""

from __future__ import annotations

from typing import Final

from app.adapters.errors import AdapterError
from app.adapters.registry import AdapterRegistry
from app.core.errors import ErrorCode

__all__ = [
    "PLATFORM_OWNED_TOOLS",
    "select_adapter_code",
]


#: Tools that never touch a MIDAS adapter.
#:
#: ``midas_task`` is platform-owned because MIDAS exposes no task API at all
#: (《MIDAS API 对接规范》§2.5.1), so its capabilities carry
#: ``adapter_code = None``.  Selecting an adapter for it would be meaningless —
#: and would fail whenever no instance is registered, which is a legitimate
#: state for a platform that only tracks tasks.
PLATFORM_OWNED_TOOLS: Final[frozenset[str]] = frozenset({"midas_task"})


def select_adapter_code(
    registry: AdapterRegistry,
    tool: str,
    requested: str | None,
) -> str | None:
    """The adapter ``tool`` must run on, or ``None`` for a platform-owned tool.

    The table below is the whole policy.  **``>1`` with nothing requested is a
    refusal, not a default** — that row is the one that prevents a call from
    landing on the wrong product:

    ===================  ==================  ====================================
    registered adapters  ``requested``       result
    ===================  ==================  ====================================
    platform-owned tool  (ignored)           ``None``
    any                  a registered code   that code
    any                  an unknown code     ``ADAPTER_NOT_FOUND``
    exactly 1            ``None``            that one (unambiguous)
    **0**                ``None``            ``CLIENT_NOT_CONNECTED``
    **>1**               ``None``            ``VALIDATION_ERROR`` (ambiguous)
    ===================  ==================  ====================================

    :param registry: the runtime adapter registry (V2.1 §21).
    :param tool: one of the four MCP tool names.
    :param requested: the caller's ``adapter`` argument, if any.
    """
    if tool in PLATFORM_OWNED_TOOLS:
        return None

    codes = sorted(registry.codes())

    if requested is not None:
        wanted = str(requested).strip()
        if wanted not in codes:
            raise AdapterError(
                ErrorCode.ADAPTER_NOT_FOUND,
                f"adapter={wanted!r} 未注册；已注册：{codes}。"
                "（V2.1 §16.2：Adapter 未注册 -> ADAPTER_NOT_FOUND）",
                details={"requested_adapter": wanted, "registered": codes},
            )
        return wanted

    if len(codes) == 1:
        # Unambiguous: there is exactly one place this call could go.
        return codes[0]

    if not codes:
        raise AdapterError(
            ErrorCode.CLIENT_NOT_CONNECTED,
            "没有任何已注册的 MIDAS 实例，无法执行需要 MIDAS 的能力。"
            "请先在 midas_clients 中登记实例（对接规范 §2.5.3）。",
            details={"tool": tool},
        )

    # **The safety row.**  Several products are available and the caller did not
    # say which.  Choosing one would be a guess, and a wrong guess is a silent
    # write to the wrong model — so we refuse and make the caller state its
    # intent.  The message names the choices so the fix is obvious.
    raise AdapterError(
        ErrorCode.VALIDATION_ERROR,
        f"已注册 {len(codes)} 个 MIDAS 实例（{codes}），无法判断本次调用应使用哪一个。"
        "**必须显式指定** adapter 或 client_id —— 平台不会替调用方猜测，"
        "因为操作错误的软件会造成数据混乱（多产品多租户路由框架 §三 闸 1）。",
        details={"tool": tool, "registered": codes, "reason": "ambiguous_instance"},
    )
