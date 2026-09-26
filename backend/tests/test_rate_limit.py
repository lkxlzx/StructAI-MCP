"""Offline token-bucket tests — 总纲 §4.4.2 ``RATE_LIMITED`` / §8.6, 裁决 B-7.

Plain ``pytest`` only, no database, no server, no network: :mod:`app.core.rate_limit`
is deliberately dependency-free (a dict plus arithmetic), so everything here runs
against the limiter directly with an **injected clock** — the same
``clock``-parameter shape :class:`app.services.auth_service.AuthService` uses.
Nothing sleeps.

The HTTP half of the limiter (the 429 envelope, the ``X-RateLimit-*`` headers, the
health-probe exemptions, the ``X-Forwarded-For`` bypass test) lives in
``tests/test_rest_sse.py``, where the app fixtures already exist.

What is proven, and against which rule:

====================================================================  ==================================
claim                                                                依据
====================================================================  ==================================
``burst`` is the capacity, ``per_minute`` the refill rate             总纲 裁决 B-7
a new key may burst up to ``burst``, then is refused                  总纲 §4.4.2
the bucket refills with time (injected clock, no ``sleep``)           总纲 裁决 B-7
``tokens`` never exceed the capacity (a long idle period is capped)    裁决 B-7
a non-positive limit is clamped, never "off"                          fail closed (§8.6)
``X-Forwarded-For`` is ignored unless ``trust_proxy_headers``          bypass guard (§8.6)
the right-most hop is taken when it is trusted                        §8.6
idle buckets are reclaimed and the map is hard-bounded                memory bound
====================================================================  ==================================
"""

import pytest

from app.core.config import Settings
from app.core.rate_limit import (
    DEFAULT_MAX_BUCKETS,
    UNKNOWN_CLIENT_KEY,
    RateLimitLimiter,
    RateLimitPolicy,
    client_key,
)
from app.services.auth_service import (
    DEFAULT_RATE_LIMIT_BURST,
    DEFAULT_RATE_LIMIT_ENABLED,
    DEFAULT_RATE_LIMIT_PER_MINUTE,
)


class FakeClock:
    """A monotonic clock the test drives by hand (never ``sleep``)."""

    def __init__(self, start: float = 1_000.0) -> None:
        self.moment: float = float(start)

    def __call__(self) -> float:
        return self.moment

    def advance(self, seconds: float) -> float:
        self.moment += float(seconds)
        return self.moment


def build_limiter(**kwargs: object) -> tuple[RateLimitLimiter, FakeClock]:
    """A limiter over a fresh :class:`FakeClock`, plus that clock."""
    clock = FakeClock()
    limiter = RateLimitLimiter(clock=clock, **kwargs)  # type: ignore[arg-type]
    return limiter, clock


# ---------------------------------------------------------------------------
# 1. the policy mirrors 裁决 B-7's three columns
# ---------------------------------------------------------------------------
def test_policy_defaults_mirror_the_ddl_and_settings() -> None:
    """裁决 B-7: the row's defaults, the DDL defaults and ``Settings`` agree.

    The ``Settings`` half is read off the *class fields* rather than an instance:
    a developer's ``.env`` or an exported variable must not be able to make this
    assertion pass or fail for the wrong reason.
    """
    assert RateLimitPolicy().enabled is DEFAULT_RATE_LIMIT_ENABLED is True
    assert RateLimitPolicy().per_minute == DEFAULT_RATE_LIMIT_PER_MINUTE == 120
    assert RateLimitPolicy().burst == DEFAULT_RATE_LIMIT_BURST == 30

    fields = Settings.model_fields
    assert fields["rate_limit_enabled"].default is True
    assert fields["rate_limit_per_minute"].default == 120
    assert fields["rate_limit_burst"].default == 30
    # The bypass flag is off unless an operator turns it on (总纲 §8.6).
    assert fields["trust_proxy_headers"].default is False


def test_policy_from_settings_reads_every_field() -> None:
    settings = Settings(
        rate_limit_enabled=False,
        rate_limit_per_minute=7,
        rate_limit_burst=3,
    )
    policy = RateLimitPolicy.from_settings(settings)
    assert (policy.enabled, policy.per_minute, policy.burst) == (False, 7, 3)
    assert policy.effective is False


def test_a_non_positive_limit_is_clamped_not_disabled() -> None:
    """``0`` is not a magic "off" — ``rate_limit_enabled`` is.  Fail closed."""
    policy = RateLimitPolicy(enabled=True, per_minute=0, burst=0)
    assert policy.effective is True
    assert policy.capacity == 1
    assert policy.limit_per_minute == 1
    assert policy.refill_per_second == pytest.approx(1 / 60)


def test_full_refill_seconds_is_capacity_over_rate() -> None:
    policy = RateLimitPolicy(per_minute=60, burst=10)
    assert policy.full_refill_seconds == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# 2. the algorithm
# ---------------------------------------------------------------------------
def test_a_new_key_may_burst_up_to_the_capacity_then_is_refused() -> None:
    limiter, _clock = build_limiter()
    policy = RateLimitPolicy(enabled=True, per_minute=60, burst=3)

    decisions = [limiter.check("10.0.0.1", policy) for _ in range(4)]
    assert [item.allowed for item in decisions] == [True, True, True, False]
    assert [item.remaining for item in decisions] == [2, 1, 0, 0]
    assert {item.limit for item in decisions} == {3}
    # The refused call reports a whole-second wait, never 0 — a ``Retry-After: 0``
    # invites an immediate retry storm.
    assert decisions[-1].retry_after >= 1
    assert decisions[0].retry_after == 0
    assert decisions[0].reset_after == 1, "one token short of a full bucket"


def test_the_bucket_refills_with_the_injected_clock() -> None:
    """60 tokens/minute == 1 token/second; no ``sleep`` anywhere."""
    limiter, clock = build_limiter()
    policy = RateLimitPolicy(enabled=True, per_minute=60, burst=2)

    assert limiter.check("k", policy).allowed is True
    assert limiter.check("k", policy).allowed is True
    assert limiter.check("k", policy).allowed is False

    clock.advance(1.0)
    assert limiter.check("k", policy).allowed is True
    assert limiter.check("k", policy).allowed is False

    # A partial refill is not enough for a whole token.
    clock.advance(0.5)
    assert limiter.check("k", policy).allowed is False
    clock.advance(0.5)
    assert limiter.check("k", policy).allowed is True


def test_a_long_idle_period_never_exceeds_the_capacity() -> None:
    """Refill is ``min(capacity, …)`` — an hour of quiet is not 3600 requests."""
    limiter, clock = build_limiter()
    policy = RateLimitPolicy(enabled=True, per_minute=60, burst=4)
    for _ in range(4):
        assert limiter.check("k", policy).allowed is True
    assert limiter.check("k", policy).allowed is False

    clock.advance(3600.0)
    decisions = [limiter.check("k", policy) for _ in range(5)]
    assert [item.allowed for item in decisions] == [True, True, True, True, False]
    assert decisions[0].remaining == 3, "capped at the capacity, not at 3600"


def test_reset_after_is_the_time_to_a_full_bucket() -> None:
    """Drained at 60 tokens/minute: 5 tokens back in 5s, the first one in 1s."""
    limiter, _clock = build_limiter()
    policy = RateLimitPolicy(enabled=True, per_minute=60, burst=5)
    for _ in range(5):
        assert limiter.check("k", policy).allowed is True

    decision = limiter.check("k", policy)
    assert decision.allowed is False
    assert decision.remaining == 0
    assert decision.reset_after == 5
    assert decision.retry_after == 1


def test_reset_after_rounds_up_to_whole_seconds() -> None:
    """``X-RateLimit-Reset`` is whole seconds (the header cannot carry 0.5)."""
    limiter, _clock = build_limiter()
    policy = RateLimitPolicy(enabled=True, per_minute=120, burst=3)
    for _ in range(3):
        limiter.check("k", policy)
    decision = limiter.check("k", policy)
    assert decision.allowed is False
    assert decision.reset_after == 2, "3 tokens at 2/s"
    assert decision.retry_after == 1, "1 token at 2/s"


def test_buckets_are_independent_per_key() -> None:
    limiter, _clock = build_limiter()
    policy = RateLimitPolicy(enabled=True, per_minute=60, burst=1)
    assert limiter.check("a", policy).allowed is True
    assert limiter.check("a", policy).allowed is False
    assert limiter.check("b", policy).allowed is True
    assert limiter.bucket_count() == 2


# ---------------------------------------------------------------------------
# 3. memory — the map must not grow without bound
# ---------------------------------------------------------------------------
def test_the_bucket_map_is_hard_bounded_by_max_buckets() -> None:
    """A key flood must not become a memory leak (or a DoS of the limiter's own)."""
    limiter, _clock = build_limiter(max_buckets=8)
    policy = RateLimitPolicy(enabled=True, per_minute=60, burst=1)
    for index in range(500):
        limiter.check(f"10.0.{index // 256}.{index % 256}", policy)
    assert limiter.bucket_count() == 8
    assert limiter.bucket_count() <= limiter.max_buckets


def test_the_least_recently_used_bucket_is_the_one_evicted() -> None:
    limiter, _clock = build_limiter(max_buckets=3)
    policy = RateLimitPolicy(enabled=True, per_minute=60, burst=1)
    for key in ("a", "b", "c"):
        limiter.check(key, policy)
    # Touch "a" so "b" becomes the least recently used.
    limiter.check("a", policy)
    limiter.check("d", policy)
    assert limiter.keys() == ["c", "a", "d"]


def test_a_fully_refilled_bucket_is_reclaimed_losslessly() -> None:
    """An idle bucket is indistinguishable from a missing one, so it is dropped."""
    limiter, clock = build_limiter(max_buckets=4)
    policy = RateLimitPolicy(enabled=True, per_minute=60, burst=2)

    limiter.check("idle", policy)
    assert limiter.bucket_count() == 1

    # "idle" refills to capacity while nothing else happens...
    clock.advance(2.0)
    limiter.check("fresh", policy)

    # ...and the next insert reclaims it without the LRU cap ever being reached.
    assert limiter.keys() == ["fresh"]
    assert limiter.bucket_count() == 1


def test_a_partially_drained_bucket_is_never_dropped_by_the_sweep() -> None:
    """Only a *full* bucket is lossless to drop; the sweep must stop there."""
    limiter, clock = build_limiter(max_buckets=4)
    policy = RateLimitPolicy(enabled=True, per_minute=60, burst=2)
    limiter.check("busy", policy)
    clock.advance(0.5)  # 1.5 tokens: not full
    limiter.check("other", policy)
    assert "busy" in limiter.keys()


def test_sweep_drops_only_fully_refilled_buckets() -> None:
    limiter, clock = build_limiter()
    policy = RateLimitPolicy(enabled=True, per_minute=60, burst=2)
    limiter.check("drained", policy)
    limiter.check("spent", policy)
    limiter.check("spent", policy)  # now empty
    assert limiter.sweep(policy) == 0, "nothing is idle yet"

    clock.advance(2.0)
    assert limiter.sweep(policy) == 2, "both refilled to capacity"
    assert limiter.bucket_count() == 0


def test_reset_clears_every_bucket() -> None:
    limiter, _clock = build_limiter()
    policy = RateLimitPolicy()
    limiter.check("a", policy)
    limiter.reset()
    assert limiter.bucket_count() == 0


def test_the_default_cap_is_finite() -> None:
    limiter, _clock = build_limiter()
    assert DEFAULT_MAX_BUCKETS > 0
    assert limiter.max_buckets == DEFAULT_MAX_BUCKETS


# ---------------------------------------------------------------------------
# 4. the key — the bypass guard
# ---------------------------------------------------------------------------
def test_the_socket_peer_is_the_key_by_default() -> None:
    key = client_key(
        client_host="203.0.113.7",
        forwarded_for="1.2.3.4",
        real_ip="5.6.7.8",
        trust_proxy_headers=False,
    )
    assert key == "203.0.113.7"


def test_forwarded_headers_are_ignored_when_they_are_not_trusted() -> None:
    """The bypass: a client that mints a new ``X-Forwarded-For`` per request."""
    keys = {
        client_key(
            client_host="203.0.113.7",
            forwarded_for=f"10.0.0.{index}",
            trust_proxy_headers=False,
        )
        for index in range(50)
    }
    assert keys == {"203.0.113.7"}, "one bucket, or the limit does not exist"


def test_the_right_most_hop_is_taken_when_proxy_headers_are_trusted() -> None:
    """With one trusted proxy in front, the last hop is the address it observed."""
    assert (
        client_key(
            client_host="127.0.0.1",
            forwarded_for="9.9.9.9, 203.0.113.7",
            trust_proxy_headers=True,
        )
        == "203.0.113.7"
    )
    # …and the spoofed left-most hop cannot select a bucket.
    assert client_key(
        client_host="127.0.0.1",
        forwarded_for="1.1.1.1, 2.2.2.2, 203.0.113.7",
        trust_proxy_headers=True,
    ) == client_key(
        client_host="127.0.0.1",
        forwarded_for="8.8.8.8, 203.0.113.7",
        trust_proxy_headers=True,
    )


def test_real_ip_is_only_a_fallback_for_a_missing_forwarded_for() -> None:
    assert (
        client_key(
            client_host="127.0.0.1",
            forwarded_for="",
            real_ip="203.0.113.9",
            trust_proxy_headers=True,
        )
        == "203.0.113.9"
    )
    assert (
        client_key(
            client_host="127.0.0.1",
            forwarded_for=" , ",
            real_ip="203.0.113.9",
            trust_proxy_headers=True,
        )
        == "203.0.113.9"
    )
    assert (
        client_key(
            client_host="127.0.0.1",
            forwarded_for="203.0.113.7",
            real_ip="203.0.113.9",
            trust_proxy_headers=True,
        )
        == "203.0.113.7"
    )


def test_an_unidentifiable_client_shares_one_bucket() -> None:
    """Fail closed: no peer address means limited, not exempt."""
    assert client_key(client_host=None) == UNKNOWN_CLIENT_KEY
    assert client_key(client_host="  ") == UNKNOWN_CLIENT_KEY
    assert (
        client_key(client_host=None, forwarded_for="1.2.3.4", trust_proxy_headers=False)
        == UNKNOWN_CLIENT_KEY
    )
