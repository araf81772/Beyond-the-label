"""Fake-clock rate accounting tests; no real sleep or network requests."""
from concurrent.futures import ThreadPoolExecutor

import pytest

from beyond_label.rate_limit import RateLimitError, RateLimiter


class FakeClock:
    def __init__(self, now=0.0):
        self.now = now
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def limiter(rpm=2, tpm=100, *, cold_start=False):
    clock = FakeClock()
    return RateLimiter(rpm, tpm, clock=clock.clock, sleep=clock.sleep,
                       cold_start=cold_start), clock


@pytest.mark.parametrize("field", ["requests_per_minute", "tokens_per_minute"])
@pytest.mark.parametrize("value", [0, -1, True, 1.5, float("nan"), float("inf"), "60", None])
def test_limits_require_positive_integers(field, value):
    kwargs = {"requests_per_minute": 10, "tokens_per_minute": 100}
    kwargs[field] = value
    with pytest.raises(RateLimitError, match="positive_integers"):
        RateLimiter(**kwargs)


@pytest.mark.parametrize("value", [0, -1, True, 1.5, float("nan"), float("inf"), "1", None])
def test_invalid_token_bound_is_rejected_before_wait(value):
    gate, clock = limiter(cold_start=True)
    with pytest.raises(RateLimitError, match="token_bound"):
        gate.acquire(value)
    assert clock.sleeps == []


def test_single_attempt_cannot_exceed_token_window():
    gate, clock = limiter(cold_start=True)
    with pytest.raises(RateLimitError, match="single_attempt"):
        gate.acquire(101)
    assert clock.sleeps == []


def test_default_cold_start_waits_full_window_in_short_slices():
    clock = FakeClock()
    gate = RateLimiter(1, 100, clock=clock.clock, sleep=clock.sleep)
    gate.acquire(100)
    assert gate.cold_start is True
    assert clock.now == 60
    assert sum(clock.sleeps) == 60
    assert all(0 < delay <= 1 for delay in clock.sleeps)


def test_constructed_limiter_can_use_already_elapsed_cold_start_time():
    gate, clock = limiter(cold_start=True)
    clock.now = 75
    gate.acquire(1)
    assert clock.sleeps == []


def test_exact_token_capacity_then_request_waits_until_expiry():
    gate, clock = limiter()
    gate.acquire(40)
    gate.acquire(60)
    assert clock.sleeps == []
    gate.acquire(1)
    assert clock.now == 60


def test_request_limit_is_enforced_independently_of_tokens():
    gate, clock = limiter(rpm=1, tpm=1000)
    gate.acquire(1)
    clock.now = 30
    gate.acquire(1)
    assert clock.now == 60
    assert sum(clock.sleeps) == 30


@pytest.mark.parametrize("bound,expected_time", [(50, 60), (70, 70)])
def test_waits_for_enough_token_reservations_to_expire(bound, expected_time):
    gate, clock = limiter(rpm=10)
    gate.acquire(60)
    clock.now = 10
    gate.acquire(40)
    clock.now = 20
    gate.acquire(bound)
    assert clock.now == expected_time


def test_failed_attempt_and_its_retry_both_consume_capacity():
    gate, clock = limiter(rpm=1)
    gate.acquire(1)
    # A transport could fail after acquire; no refund exists for that attempt.
    gate.acquire(1)
    assert clock.now == 60


def test_restart_with_default_cold_start_does_not_ignore_recent_usage():
    first, clock = limiter(rpm=1)
    first.acquire(100)
    restarted = RateLimiter(1, 100, clock=clock.clock, sleep=clock.sleep)
    restarted.acquire(100)
    assert clock.now == 60


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), True, "0", None, 10**1000, 1e308])
def test_invalid_clock_rejected(value):
    with pytest.raises(RateLimitError, match="invalid_clock"):
        RateLimiter(1, 1, clock=lambda: value, sleep=lambda _: None)


def test_backwards_clock_cannot_reopen_capacity():
    gate, clock = limiter(rpm=1)
    gate.acquire(1)
    clock.now = -1
    with pytest.raises(RateLimitError, match="backwards"):
        gate.acquire(1)
    clock.now = 0
    gate.acquire(1)
    assert clock.now == 60


def test_nonadvancing_clock_does_not_spin_or_bypass_wait():
    sleeps = []
    gate = RateLimiter(1, 1, clock=lambda: 0, sleep=sleeps.append)
    with pytest.raises(RateLimitError, match="did_not_advance"):
        gate.acquire(1)
    assert sleeps == [1]


def test_cancellation_releases_lock_without_reserving_an_attempt():
    clock = FakeClock()
    cancelled = False

    def sleep(seconds):
        nonlocal cancelled
        if not cancelled:
            cancelled = True
            raise KeyboardInterrupt
        clock.sleep(seconds)

    gate = RateLimiter(1, 100, clock=clock.clock, sleep=sleep)
    with pytest.raises(KeyboardInterrupt):
        gate.acquire(100)
    clock.now = 60
    gate.acquire(100)
    assert clock.sleeps == []
    gate.acquire(100)
    assert clock.now == 120


@pytest.mark.parametrize("which", ["clock", "sleep"])
def test_callback_exception_text_is_not_disclosed(which):
    def failure(*args):
        raise RuntimeError("synthetic-private-callback-value")

    kwargs = {"clock": lambda: 0, "sleep": lambda _: None, which: failure}
    with pytest.raises(RateLimitError) as caught:
        gate = RateLimiter(1, 1, **kwargs)
        gate.acquire(1)
    assert str(caught.value) == f"{which}_failed"
    assert caught.value.__cause__ is None


def test_threaded_callers_cannot_overbook_token_capacity():
    gate, clock = limiter(rpm=10, tpm=100)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(gate.acquire, [60] * 4))
    assert clock.now == 180
    assert all(0 < delay <= 1 for delay in clock.sleeps)


@pytest.mark.parametrize("attribute", ["requests_per_minute", "tokens_per_minute", "cold_start"])
def test_pinned_limit_properties_are_read_only(attribute):
    gate, _ = limiter()
    with pytest.raises(AttributeError):
        setattr(gate, attribute, 999)


@pytest.mark.parametrize("kwargs", [{"cold_start": 1}, {"cold_start": "false"}, {"clock": None}, {"sleep": None}])
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(RateLimitError, match="configuration"):
        RateLimiter(1, 1, **kwargs)
