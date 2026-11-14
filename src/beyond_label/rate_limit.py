"""Conservative in-process request/token rate reservations; no provider calls.

Each acquire reserves one attempted request and a verified upper bound for its
total charged tokens (input plus maximum output/reasoning where applicable).
The caller must supply that bound; this module invents no tokenizer or pricing.
There are no refunds after success, failure or an infrastructure retry. Every
new transport attempt needs a new acquire.

Limits use explicit requests-per-minute and tokens-per-minute units over a
sliding 60-second window. State is not durable or shared between processes.
The default full-window cold-start wait conservatively covers unknown recent
usage before this limiter was constructed, but cannot account for concurrent
use by other processes/accounts. Future live execution must use a dedicated
key and one owner, or a shared limiter. cold_start=False is only appropriate
when the caller can establish that no earlier attempts need accounting.
Reservations are serialized; the caller separately enforces one in-flight
transport operation across the time between acquire and transport completion.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Callable
import math
from threading import Lock
import time


class RateLimitError(ValueError):
    """Fixed validation/error reason only; no callback exception text."""


class RateLimiter:
    WINDOW_SECONDS = 60.0
    MAX_SLEEP_SECONDS = 1.0

    def __init__(self, requests_per_minute: int, tokens_per_minute: int, *,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep,
                 cold_start: bool = True):
        if (type(requests_per_minute) is not int or requests_per_minute <= 0
                or type(tokens_per_minute) is not int or tokens_per_minute <= 0):
            raise RateLimitError("limits_must_be_positive_integers")
        if type(cold_start) is not bool or not callable(clock) or not callable(sleep):
            raise RateLimitError("invalid_limiter_configuration")
        self._requests_per_minute = requests_per_minute
        self._tokens_per_minute = tokens_per_minute
        self._cold_start = cold_start
        self._clock, self._sleep = clock, sleep
        self._last_time: float | None = None
        self._entries: deque[tuple[float, int]] = deque()
        self._tokens = 0
        self._lock = Lock()
        initial = self._now()
        self._not_before = initial + self.WINDOW_SECONDS if cold_start else initial

    @property
    def requests_per_minute(self) -> int:
        return self._requests_per_minute

    @property
    def tokens_per_minute(self) -> int:
        return self._tokens_per_minute

    @property
    def cold_start(self) -> bool:
        return self._cold_start

    def _now(self) -> float:
        try:
            value = self._clock()
        except Exception:
            raise RateLimitError("clock_failed") from None
        if type(value) not in (int, float):
            raise RateLimitError("invalid_clock")
        try:
            now = float(value)
        except (ValueError, OverflowError):
            raise RateLimitError("invalid_clock") from None
        if (not math.isfinite(now) or not math.isfinite(now + self.WINDOW_SECONDS)
                or now + self.WINDOW_SECONDS <= now):
            raise RateLimitError("invalid_clock")
        if self._last_time is not None and now < self._last_time:
            raise RateLimitError("clock_moved_backwards")
        self._last_time = now
        return now

    def _wait(self, now: float, deadline: float) -> float:
        delay = min(self.MAX_SLEEP_SECONDS, deadline - now)
        try:
            self._sleep(delay)
        except Exception:
            raise RateLimitError("sleep_failed") from None
        # KeyboardInterrupt/SystemExit remain cancellation signals. A broken
        # injected clock/sleeper cannot spin forever or silently bypass limits.
        later = self._now()
        if later <= now:
            raise RateLimitError("clock_did_not_advance")
        return later

    def acquire(self, token_bound: int) -> None:
        """Reserve an attempt before dispatch; serialized and never refunded.

        This is rate accounting only, not authorization, budget enforcement,
        empirical evidence or proof of compliance with a provider's limits.
        """
        if type(token_bound) is not int or token_bound <= 0:
            raise RateLimitError("token_bound_must_be_positive_integer")
        if token_bound > self.tokens_per_minute:
            raise RateLimitError("single_attempt_exceeds_token_limit")
        with self._lock:
            now = self._now()
            while True:
                if now < self._not_before:
                    now = self._wait(now, self._not_before)
                    continue
                while self._entries and self._entries[0][0] + self.WINDOW_SECONDS <= now:
                    _, tokens = self._entries.popleft()
                    self._tokens -= tokens
                if (len(self._entries) < self.requests_per_minute
                        and self._tokens + token_bound <= self.tokens_per_minute):
                    self._entries.append((now, token_bound))
                    self._tokens += token_bound
                    return
                now = self._wait(now, self._entries[0][0] + self.WINDOW_SECONDS)
