"""Adapter registry — V2.1 §21.

``register`` / ``unregister`` / ``get`` / ``list`` / ``resolve`` plus a
module-level singleton, exactly as §21 declares.

Two deviations from the literal §21 text, both documented at the call site:

1. §21 shows ``register(adapter)`` performing ``await adapter.metadata()``, but
   it also declares ``register`` as a **sync** method while §13 declares
   ``metadata()`` as ``async``.  A sync function cannot await, so the async form
   lives in :meth:`AdapterRegistry.register_async`; the sync form accepts a
   pre-resolved :class:`~app.adapters.base.AdapterMetadata`.
2. §21's rule "若 code 未在 adapters 表登记 → 返回 ``ADAPTER_NOT_FOUND``" needs
   a database read.  This registry stays storage-free (the DB write-back belongs
   to the Service layer); it enforces the part it *can* enforce locally —
   ``metadata().code`` must equal ``adapter.code`` (§15) — and documents the rest.
"""

import re
from typing import Any, Iterable, List

from app.adapters.base import AdapterMetadata, MidasAdapter
from app.adapters.errors import AdapterError
from app.core.constants import AdapterStatus
from app.core.errors import ErrorCode

__all__ = [
    "AdapterRegistry",
    "get_registry",
    "reset_registry",
    "version_in_range",
    "version_range_specificity",
    "software_matches",
]


# ---------------------------------------------------------------------------
# version_range helpers
# ---------------------------------------------------------------------------
#: ``adapters.version_range`` is free text (V2.1 §15 落库映射), so this parser is
#: deliberately small: dotted/space separated numeric groups, optional operator,
#: ``||`` for alternatives and ``,`` / ``;`` / ``and`` for conjunctions.
#: A clause that cannot be parsed **never excludes** a candidate — a free-text
#: range must not silently make an adapter unreachable.
_CLAUSE_RE = re.compile(r"^\s*(>=|<=|==|!=|>|<|=|~=)?\s*v?([0-9][0-9A-Za-z.\-+_]*)\s*$")
_CLAUSE_SPLIT_RE = re.compile(r"[,;]|\band\b|&&", re.IGNORECASE)
_ANY_RANGE = frozenset({"", "*", "any", "all", "any version"})


def _parse_version(text: str) -> tuple[int, ...]:
    """``"2024 R1"`` -> ``(2024, 1)``.  Non-numeric text yields ``(0,)``."""
    groups = re.findall(r"\d+", text or "")
    if not groups:
        return (0,)
    return tuple(int(group) for group in groups)


def _compare(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    width = max(len(left), len(right))
    a = left + (0,) * (width - len(left))
    b = right + (0,) * (width - len(right))
    if a == b:
        return 0
    return -1 if a < b else 1


def _clause_holds(version: str, clause: str) -> bool:
    match = _CLAUSE_RE.match(clause)
    if match is None:
        return True
    operator = match.group(1) or ">="  # a bare version reads as a floor
    target = _parse_version(match.group(2))
    order = _compare(_parse_version(version), target)
    if operator == ">=":
        return order >= 0
    if operator == "<=":
        return order <= 0
    if operator == ">":
        return order > 0
    if operator == "<":
        return order < 0
    if operator == "!=":
        return order != 0
    if operator in ("=", "=="):
        return order == 0
    if operator == "~=":  # compatible release — approximated as a floor
        return order >= 0
    return True


def version_in_range(version: str | None, version_range: str | None) -> bool:
    """True when ``version`` satisfies ``version_range`` (see module docstring)."""
    if version is None:
        return True
    text = (version_range or "").strip()
    if text.lower() in _ANY_RANGE:
        return True
    alternatives = [part for part in text.split("||") if part.strip()]
    if not alternatives:
        return True
    for alternative in alternatives:
        clauses = [part for part in _CLAUSE_SPLIT_RE.split(alternative) if part.strip()]
        if clauses and all(_clause_holds(version, clause) for clause in clauses):
            return True
    return False


def version_range_specificity(version_range: str | None) -> int:
    """Higher = more precise.  §21: prefer the most precise candidate."""
    text = (version_range or "").strip()
    if text.lower() in _ANY_RANGE:
        return 0
    score = 0
    for alternative in text.split("||"):
        clauses = [part for part in _CLAUSE_SPLIT_RE.split(alternative) if part.strip()]
        score += len(clauses)
        if any(part.strip().startswith(("=", "==")) for part in clauses):
            score += 1  # an exact pin beats a floor of the same length
    return score


def _normalise_software(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def software_matches(registered: str, query: str) -> bool:
    """Token-set match so ``midas_gen`` / ``MIDAS Gen`` / ``gen`` all resolve."""
    wanted = _normalise_software(query)
    if not wanted:
        return True
    have = _normalise_software(registered)
    if have == wanted:
        return True
    have_tokens = set(have.split())
    wanted_tokens = set(wanted.split())
    if not have_tokens or not wanted_tokens:
        return False
    return wanted_tokens <= have_tokens or have_tokens <= wanted_tokens


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class AdapterRegistry:
    """In-process registry of :class:`~app.adapters.base.MidasAdapter` instances."""

    def __init__(self) -> None:
        self._adapters: dict[str, MidasAdapter] = {}
        self._metadata: dict[str, AdapterMetadata] = {}

    # ------------------------------------------------------------------ #
    def register(
        self,
        adapter: MidasAdapter,
        *,
        metadata: AdapterMetadata | None = None,
        replace: bool = False,
    ) -> AdapterMetadata:
        """Register ``adapter`` and cache its §15 metadata.

        ``metadata`` should be the value of ``await adapter.metadata()``.  When
        omitted, a metadata shell is synthesised from the adapter's ``code`` /
        ``software`` / ``version`` properties — enough for ``resolve()``, but
        ``capabilities`` will be empty until :meth:`register_async` is used.

        Raises ``ADAPTER_NOT_FOUND`` when ``metadata.code != adapter.code``
        (§15: 不一致则注册失败) and ``RESOURCE_CONFLICT`` on a duplicate code
        unless ``replace=True``.
        """
        code = getattr(adapter, "code", None)
        if not code or not isinstance(code, str):
            raise AdapterError(
                ErrorCode.VALIDATION_ERROR,
                "adapter.code 缺失或不是字符串，无法注册（V2.1 §15 落库映射要求 code 非空）",
            )
        if code in self._adapters and not replace:
            raise AdapterError(
                ErrorCode.RESOURCE_CONFLICT,
                f"adapter code={code!r} 已注册；重复注册需显式 replace=True",
                details={"code": code},
            )
        resolved = metadata or self._fallback_metadata(adapter)
        if resolved.code != code:
            raise AdapterError(
                ErrorCode.ADAPTER_NOT_FOUND,
                f"metadata().code={resolved.code!r} 与 adapter.code={code!r} 不一致，"
                "拒绝注册（V2.1 §15：若不一致则注册失败）",
                details={"metadata_code": resolved.code, "adapter_code": code},
            )
        self._adapters[code] = adapter
        self._metadata[code] = resolved
        return resolved

    async def register_async(
        self,
        adapter: MidasAdapter,
        *,
        replace: bool = False,
    ) -> AdapterMetadata:
        """§21's ``register``: read ``await adapter.metadata()`` once, then cache."""
        metadata = await adapter.metadata()
        return self.register(adapter, metadata=metadata, replace=replace)

    def unregister(self, code: str) -> None:
        """Remove ``code``.  Raises ``ADAPTER_NOT_FOUND`` when absent."""
        if code not in self._adapters:
            raise AdapterError(
                ErrorCode.ADAPTER_NOT_FOUND,
                f"adapter code={code!r} 未注册",
                details={"code": code, "registered": sorted(self._adapters)},
            )
        del self._adapters[code]
        self._metadata.pop(code, None)

    def get(self, code: str) -> MidasAdapter:
        """Look up one adapter.  Raises ``ADAPTER_NOT_FOUND`` when absent."""
        try:
            return self._adapters[code]
        except KeyError as exc:
            raise AdapterError(
                ErrorCode.ADAPTER_NOT_FOUND,
                f"adapter code={code!r} 未注册",
                details={"code": code, "registered": sorted(self._adapters)},
            ) from exc

    def list(self) -> list[MidasAdapter]:
        """Every registered adapter, in registration order."""
        return list(self._adapters.values())

    def resolve(self, software: str, version: str | None = None) -> MidasAdapter:
        """§21 resolution: software (+ optional version), enabled, most precise.

        * no candidate at all → ``ADAPTER_NOT_FOUND``
        * candidates exist but all disabled → ``ADAPTER_UNAVAILABLE``
        * version given and no candidate's ``version_range`` accepts it →
          ``CAPABILITY_NOT_SUPPORTED`` (§16.2: 软件/版本不支持该能力)
        """
        matched: list[tuple[MidasAdapter, AdapterMetadata]] = []
        for adapter in self._adapters.values():
            meta = self._metadata_for(adapter)
            if software_matches(meta.software, software):
                matched.append((adapter, meta))
        if not matched:
            raise AdapterError(
                ErrorCode.ADAPTER_NOT_FOUND,
                f"没有匹配 software={software!r} 的 adapter",
                details={"software": software, "registered": sorted(self._adapters)},
            )
        enabled = [(adapter, meta) for adapter, meta in matched if self._is_enabled(adapter)]
        if not enabled:
            raise AdapterError(
                ErrorCode.ADAPTER_UNAVAILABLE,
                f"software={software!r} 的 adapter 均已禁用（status='disabled'）",
                details={"software": software, "codes": [meta.code for _a, meta in matched]},
            )
        if version is not None:
            in_range = [
                (adapter, meta)
                for adapter, meta in enabled
                if version_in_range(version, meta.version_range)
            ]
            if not in_range:
                raise AdapterError(
                    ErrorCode.CAPABILITY_NOT_SUPPORTED,
                    f"version={version!r} 不在任何候选 adapter 的 version_range 内",
                    details={
                        "software": software,
                        "version": version,
                        "ranges": {meta.code: meta.version_range for _a, meta in enabled},
                    },
                )
            enabled = in_range
        enabled.sort(
            key=lambda pair: (
                -version_range_specificity(pair[1].version_range),
                pair[1].code,
            )
        )
        return enabled[0][0]

    # ------------------------------------------------------------------ #
    def metadata_of(self, code: str) -> AdapterMetadata | None:
        """Cached §15 metadata, or ``None`` when unknown."""
        return self._metadata.get(code)

    def codes(self) -> List[str]:
        # NOTE: ``List`` (typing), not the builtin ``list``.  V2.1 §21 requires a
        # method named ``list`` on this class, and that method shadows the builtin
        # ``list`` for the remainder of the class body.  This annotation is
        # evaluated at class-definition time, so ``list[str]`` here raises
        # ``TypeError: 'function' object is not subscriptable``.
        # Annotations *inside* method bodies are unaffected — they resolve through
        # globals/builtins, not the class namespace.
        """Registered adapter codes, in registration order."""
        return list(self._adapters)

    def clear(self) -> None:
        """Drop everything (test/teardown helper)."""
        self._adapters.clear()
        self._metadata.clear()

    def __len__(self) -> int:
        return len(self._adapters)

    def __contains__(self, code: object) -> bool:
        return code in self._adapters

    def __iter__(self) -> Iterable[MidasAdapter]:
        return iter(self._adapters.values())

    # ------------------------------------------------------------------ #
    def _metadata_for(self, adapter: MidasAdapter) -> AdapterMetadata:
        code = adapter.code
        return self._metadata.get(code) or self._fallback_metadata(adapter)

    @staticmethod
    def _fallback_metadata(adapter: MidasAdapter) -> AdapterMetadata:
        """Synthesise a metadata shell from the three §13 properties."""
        return AdapterMetadata(
            code=adapter.code,
            name=adapter.code,
            software=getattr(adapter, "software", adapter.code),
            version_range="*",
            protocol="http",
            supports_query=True,
            supports_model=True,
            supports_execute=True,
            supports_async_task=False,
            capabilities=[],
        )

    @staticmethod
    def _is_enabled(adapter: MidasAdapter) -> bool:
        """§21: ``status='disabled'`` makes a candidate unavailable.

        §13's Protocol has **no** status accessor even though §14's mapping table
        requires one, so this reads an optional ``status`` attribute and treats
        its absence as "enabled" rather than failing the lookup.
        """
        status: Any = getattr(adapter, "status", None)
        if status is None:
            return True
        value = getattr(status, "value", status)
        return value != AdapterStatus.DISABLED.value


# ---------------------------------------------------------------------------
# module-level singleton (§21)
# ---------------------------------------------------------------------------
_registry: AdapterRegistry | None = None


def get_registry() -> AdapterRegistry:
    """Process-wide :class:`AdapterRegistry` singleton."""
    global _registry
    if _registry is None:
        _registry = AdapterRegistry()
    return _registry


def reset_registry() -> AdapterRegistry:
    """Replace the singleton with a fresh registry (tests / reload)."""
    global _registry
    _registry = AdapterRegistry()
    return _registry
