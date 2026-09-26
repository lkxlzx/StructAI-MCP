"""Token-bucket rate limiting — 总纲 §4.4.2 ``RATE_LIMITED`` / §8.6, 裁决 B-7.

Authoritative sources
---------------------
* **总纲 §4.4.2** — ``RATE_LIMITED`` → HTTP **429** 「请求过于频繁」.  This module
  defines **no** error code: it uses the one member §4.4.2 already has (read from
  :class:`app.core.errors.ErrorCode`), exactly like ``VALIDATION_ERROR`` and
  ``RESOURCE_CONFLICT``.  总纲 §0.3 / 裁决 A-3 close the registry.
* **总纲 §8.6** — 「JWT / RBAC / TLS / Rate Limit / Audit 全部启用」.  Of those
  five controls, Rate Limit was the only one with no enforcement point anywhere in
  the code base; this module is that enforcement point.
* **总纲 裁决 B-7** — the three ``security_configs`` columns
  ``rate_limit_enabled`` / ``rate_limit_per_minute`` / ``rate_limit_burst``.  Their
  names and units *are* the algorithm: a **token bucket** whose capacity is
  ``burst`` (unit: tokens) refilled at ``per_minute`` tokens per minute.  Nothing
  here hard-codes a limit — :class:`RateLimitPolicy` mirrors the columns, and its
  defaults mirror the DDL defaults (``001_schema.sql``) so an absent row is not an
  error (the same fallback shape 裁决 C-9 fixes for the session TTL).

The algorithm
-------------
For key ``k`` the limiter keeps ``(tokens, updated_at)``:

1. refill — ``tokens = min(capacity, tokens + (now - updated_at) × per_minute/60)``;
2. admit when ``tokens >= 1`` and then ``tokens -= 1``; otherwise refuse;
3. a key seen for the first time starts with a **full** bucket, i.e. it may burst
   up to ``burst`` requests back to back.

``burst`` is therefore the effective limit of a burst and ``per_minute`` the
sustained rate — which is why ``X-RateLimit-Limit`` reports the capacity and not
``per_minute``.

A non-positive ``per_minute`` / ``burst`` is **clamped to 1**, never treated as
"off": ``rate_limit_enabled`` is the switch, and a typo in a limit must not
silently remove the control (fail closed).

The clock
---------
``clock`` is injectable and defaults to :func:`time.monotonic` — deliberately
**not** :func:`time.time`.  A rate limit is an interval measurement, and a wall
clock can step backwards (NTP, DST, an operator setting the date), which would
hand every key a free refill.  ``AuthService`` takes the same injectable-``clock``
shape, so tests advance time instead of sleeping.

Memory
------
Buckets are held in one dict capped at ``max_buckets``.  See
:meth:`RateLimitLimiter._make_room` for the eviction policy.

Single-process caveat
---------------------
This limiter is **in-process**.  N uvicorn workers (``system_configs.workers``
defaults to 2) therefore give N independent buckets, i.e. an effective limit of
``N × burst``.  A multi-process or multi-node deployment needs a shared store
(Redis and friends) — which is deliberately **not** a dependency of this project,
so the honest statement is: today the limiter is exact for a single process and
approximate (per-process) behind a multi-worker one.  Do not paper over it by
pretending the numbers are global.
"""

import math
import time
from dataclasses import dataclass
from typing import Callable

from app.core.config import Settings

__all__ = [
    "DEFAULT_MAX_BUCKETS",
    "UNKNOWN_CLIENT_KEY",
    "RateLimitDecision",
    "RateLimitLimiter",
    "RateLimitPolicy",
    "TokenBucket",
    "client_key",
]

#: Key used when the ASGI scope carries no peer address at all.  All such calls
#: share one bucket, which is the fail-closed direction: an unidentifiable client
#: is limited, not exempt.
UNKNOWN_CLIENT_KEY: str = "-"

#: Hard cap on live buckets.  10 000 distinct keys ≈ a few MB at most, and the
#: cap is what makes the limiter useless as a memory-exhaustion vector.
DEFAULT_MAX_BUCKETS: int = 10_000


@dataclass(frozen=True)
class RateLimitPolicy:
    """The three ``security_configs`` rate-limit columns (总纲 裁决 B-7).

    Field defaults are the ``001_schema.sql`` column defaults, which are also the
    :class:`app.core.config.Settings` defaults — the two agree on purpose, so
    "the row is absent" and "no database is wired at all" cannot disagree about
    how much traffic is allowed.
    """

    #: Master switch.  ``False`` disables the limiter completely.
    enabled: bool = True
    #: Token-bucket refill rate (unit: tokens per minute).
    per_minute: int = 120
    #: Token-bucket capacity (unit: tokens).
    burst: int = 30

    @classmethod
    def from_settings(cls, settings: Settings) -> "RateLimitPolicy":
        """Build the policy from :class:`Settings` (the no-row / read-failure path)."""
        return cls(
            enabled=bool(settings.rate_limit_enabled),
            per_minute=int(settings.rate_limit_per_minute),
            burst=int(settings.rate_limit_burst),
        )

    @property
    def effective(self) -> bool:
        """True when the limiter should run at all."""
        return bool(self.enabled)

    @property
    def capacity(self) -> int:
        """Bucket capacity — clamped to at least 1 (see the module docstring)."""
        return max(1, int(self.burst))

    @property
    def limit_per_minute(self) -> int:
        """Sustained rate, clamped to at least 1 (unit: tokens per minute)."""
        return max(1, int(self.per_minute))

    @property
    def refill_per_second(self) -> float:
        """Refill rate in tokens per second, clamped to a positive value."""
        return self.limit_per_minute / 60.0

    @property
    def full_refill_seconds(self) -> float:
        """Seconds an empty bucket needs to refill completely."""
        return self.capacity / self.refill_per_second


@dataclass
class TokenBucket:
    """One key's bucket: how many tokens it holds and when that was computed."""

    tokens: float
    updated_at: float


@dataclass(frozen=True)
class RateLimitDecision:
    """The outcome of one :meth:`RateLimitLimiter.check`, ready to be rendered.

    ``limit`` / ``remaining`` / ``reset_after`` are exactly the values of the
    ``X-RateLimit-Limit`` / ``-Remaining`` / ``-Reset`` headers and are reported
    on **every** response the limiter saw, not only on a 429.
    """

    allowed: bool
    key: str
    #: Bucket capacity (总纲 裁决 B-7 ``rate_limit_burst``).
    limit: int
    #: Whole tokens left after this request.
    remaining: int
    #: Whole seconds until the bucket is full again.
    reset_after: int
    #: Whole seconds until one token is available; ``0`` when the call was allowed.
    retry_after: int


class RateLimitLimiter:
    """In-process token buckets, one per client key.

    Deliberately dependency-free and synchronous: it is a plain data structure
    plus arithmetic, so it can be unit-tested without an event loop, a database or
    a server.  The ASGI middleware in :mod:`app.main` is the only thing that
    knows about HTTP.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], float] | None = None,
        max_buckets: int = DEFAULT_MAX_BUCKETS,
    ) -> None:
        self._clock: Callable[[], float] = clock if clock is not None else time.monotonic
        self._max_buckets: int = max(1, int(max_buckets))
        #: Insertion-ordered on purpose: the dict's order **is** the LRU order.
        #: Every touch re-inserts the key, so ``next(iter(...))`` is the
        #: least-recently-used entry in O(1).
        self._buckets: dict[str, TokenBucket] = {}

    # ------------------------------------------------------------------ #
    # introspection (tests, and an operator console)
    # ------------------------------------------------------------------ #
    @property
    def max_buckets(self) -> int:
        """The hard cap on live buckets."""
        return self._max_buckets

    def now(self) -> float:
        """The limiter's current instant, from the injected clock."""
        return float(self._clock())

    def bucket_count(self) -> int:
        """How many buckets are live right now."""
        return len(self._buckets)

    def keys(self) -> list[str]:
        """The live keys, least-recently-used first."""
        return list(self._buckets)

    def reset(self) -> None:
        """Drop every bucket (tests / configuration reload)."""
        self._buckets.clear()

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<RateLimitLimiter buckets={len(self._buckets)}/{self._max_buckets}>"

    # ------------------------------------------------------------------ #
    # the algorithm
    # ------------------------------------------------------------------ #
    def check(self, key: str, policy: RateLimitPolicy) -> RateLimitDecision:
        """Charge one token to ``key`` and report the resulting budget.

        The bucket is created full, so a caller that has never been seen gets the
        whole ``burst`` — a token bucket, not a sliding window.
        """
        now = self.now()
        capacity = policy.capacity
        rate = policy.refill_per_second

        # ``pop`` + re-insert is what keeps the dict in LRU order in O(1).
        bucket = self._buckets.pop(key, None)
        if bucket is None:
            self._make_room(now, capacity, rate)
            bucket = TokenBucket(tokens=float(capacity), updated_at=now)
        else:
            elapsed = max(0.0, now - bucket.updated_at)
            bucket.tokens = min(float(capacity), bucket.tokens + elapsed * rate)
            bucket.updated_at = now

        allowed = bucket.tokens >= 1.0
        if allowed:
            bucket.tokens -= 1.0
        self._buckets[key] = bucket

        remaining = int(bucket.tokens) if bucket.tokens > 0.0 else 0
        missing = float(capacity) - bucket.tokens
        reset_after = 0 if missing <= 0.0 else max(0, math.ceil(missing / rate))
        retry_after = 0 if allowed else max(1, math.ceil((1.0 - bucket.tokens) / rate))
        return RateLimitDecision(
            allowed=allowed,
            key=key,
            limit=capacity,
            remaining=remaining,
            reset_after=reset_after,
            retry_after=retry_after,
        )

    def sweep(self, policy: RateLimitPolicy) -> int:
        """Drop every fully-refilled bucket; return how many were dropped.

        A bucket that has refilled to ``capacity`` is *indistinguishable from a
        bucket that does not exist* — both mean "the whole burst is available" —
        so dropping one changes no decision.  That is what makes eviction of idle
        clients lossless rather than a security hole.
        """
        now = self.now()
        capacity = float(policy.capacity)
        rate = policy.refill_per_second
        stale = [
            key
            for key, bucket in self._buckets.items()
            if bucket.tokens + max(0.0, now - bucket.updated_at) * rate >= capacity
        ]
        for key in stale:
            self._buckets.pop(key, None)
        return len(stale)

    # ------------------------------------------------------------------ #
    # eviction — the memory bound
    # ------------------------------------------------------------------ #
    def _make_room(self, now: float, capacity: int, rate: float) -> None:
        """Make space for one new key: lossless prefix sweep, then an LRU cap.

        Called **only** when a key is inserted for the first time, so the cost is
        paid by new clients and never by the steady state.

        1. **Prefix sweep (lossless).**  Walk the least-recently-used end of the
           order and drop every bucket that has refilled to ``capacity``; stop at
           the first bucket that has not.  Idle clients are reclaimed for free,
           and the loop is O(1) for a flood of *new* keys (whose oldest bucket is
           never full), so the limiter cannot be turned into a CPU amplifier.
        2. **LRU cap.**  While the map is at ``max_buckets``, drop the
           least-recently-used key.  This is the hard bound: the map can never
           exceed ``max_buckets`` entries, whatever the traffic.
        """
        while self._buckets:
            key = next(iter(self._buckets))
            bucket = self._buckets[key]
            if bucket.tokens + max(0.0, now - bucket.updated_at) * rate < capacity:
                break
            self._buckets.pop(key)
        while len(self._buckets) >= self._max_buckets:
            self._buckets.pop(next(iter(self._buckets)))


def _last_hop(header: str | None) -> str:
    """The **right-most** non-empty element of a comma-separated hop list."""
    if not header:
        return ""
    for hop in reversed(header.split(",")):
        candidate = hop.strip()
        if candidate:
            return candidate
    return ""


def client_key(
    *,
    client_host: str | None,
    forwarded_for: str | None = None,
    real_ip: str | None = None,
    trust_proxy_headers: bool = False,
) -> str:
    """Resolve the bucket key for one request.

    Default: the **socket peer address** (``scope["client"][0]``), which is the
    only value a client cannot forge.

    ``X-Forwarded-For`` / ``X-Real-IP`` are honoured **only** when
    ``trust_proxy_headers`` is on, and even then the hop taken is the
    **right-most** one.  That choice is the whole point of the flag:

    * ``X-Forwarded-For`` is append-only, so with one trusted reverse proxy in
      front the *last* element is the address that proxy actually observed, and
      every earlier element is attacker-supplied text;
    * the *left-most* element is the classic spoof.  Reading it lets any client
      mint a fresh bucket per request (``X-Forwarded-For: 1.2.3.4``,
      ``1.2.3.5``, …) and bypass the limit **entirely** — not a theoretical
      weakness, just a for-loop;
    * so with the flag off the header is not read at all, and with it on a
      deployment that has *two* proxies must be aware that the right-most hop is
      the inner proxy rather than the client.

    ``X-Real-IP`` is consulted only as a fallback when ``X-Forwarded-For`` is
    absent, because it is a single value with no hop semantics.
    """
    if trust_proxy_headers:
        hop = _last_hop(forwarded_for) or (real_ip or "").strip()
        if hop:
            return hop
    host = (client_host or "").strip()
    return host or UNKNOWN_CLIENT_KEY
