"""Inactive, opt-in operational pacing for the frozen synchronous adapter.

Importing this file installs nothing and authorizes no inference. An explicitly
approved launcher may hold ``paced_openrouter_clients(InferencePacer())`` around
the canonical staged entry point after all independent execution gates pass.

The context changes only the adapter's HTTPX dependency binding, using HTTPX's
public client factory and event-hook API. The global ``httpx.Client`` class,
canonical transport classes, guards, counters and request serialization remain
unchanged. Clients returned by the factory are ordinary HTTPX clients. Keep a
single inference owner; this in-process helper is not a cross-process lock or a
replacement for the frozen rate limiter. Close clients before leaving scope.

The first inference waits until at least 15 seconds after pacer construction;
every subsequent POST start is at least 15 seconds after the previous start.
429 responses, including HTTP 200 error envelopes, delay the next start for at
least 60 seconds after response receipt or longer when Retry-After requires it.
Requests and response bytes are never rewritten, logged or saved. Successful
200 bodies are read and cached by HTTPX to inspect error envelopes, as the
non-streaming frozen adapter already does before returning its response.
"""
from __future__ import annotations

from contextlib import contextmanager
from email.utils import parsedate_to_datetime
import math
import re
from threading import Lock
import time

import httpx


_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
_INSTALL_LOCK = Lock()


class PacingError(RuntimeError):
    """Fixed diagnostics only; never include requests, credentials or headers."""


def _inference(request):
    return request.method == "POST" and str(request.url) == _CHAT_URL


class InferencePacer:
    """Additional conservative pacing; does not retry or alter any allowance."""

    def __init__(self, *, clock=time.monotonic, wall_clock=time.time, sleep=time.sleep):
        self._clock, self._wall_clock, self._sleep = clock, wall_clock, sleep
        self._last_time = None
        self._lock = Lock()
        self._next_start = self._now() + 15.0

    def _now(self):
        value = self._clock()
        if type(value) not in (int, float) or not math.isfinite(value):
            raise PacingError("invalid_monotonic_clock")
        if self._last_time is not None and value < self._last_time:
            raise PacingError("clock_moved_backwards")
        self._last_time = value
        return value

    def before_request(self, request):
        if not _inference(request):
            return
        with self._lock:
            now = self._now()
            while self._next_start is not None and now < self._next_start:
                self._sleep(min(1.0, self._next_start - now))
                later = self._now()
                if later <= now:
                    raise PacingError("clock_did_not_advance")
                now = later
            self._next_start = now + 15.0

    def _retry_delay(self, value):
        if value is None:
            return 0.0
        value = value.strip()
        try:
            if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value):
                delay = float(value)
                if not math.isfinite(delay):
                    raise PacingError("unrepresentable_retry_after")
            else:
                date = parsedate_to_datetime(value)
                if date.tzinfo is None:
                    return 0.0
                wall = self._wall_clock()
                if type(wall) not in (int, float) or not math.isfinite(wall):
                    raise PacingError("invalid_wall_clock")
                delay = date.timestamp() - wall
        except (ValueError, TypeError, OverflowError):
            return 0.0
        return max(0.0, delay) if math.isfinite(delay) else 0.0

    def after_response(self, response):
        if not _inference(response.request):
            return
        limited = response.status_code == 429
        if response.status_code == 200:
            response.read()
            try:
                body = response.json()
            except (ValueError, UnicodeError, RecursionError):
                body = None
            error = body.get("error") if isinstance(body, dict) else None
            code = error.get("code") if isinstance(error, dict) else None
            limited = type(code) is int and code == 429
        delay = max(60.0 if limited else 0.0,
                    self._retry_delay(response.headers.get("Retry-After")))
        if delay:
            with self._lock:
                deadline = self._now() + delay
                if not math.isfinite(deadline):
                    raise PacingError("invalid_cooldown_deadline")
                self._next_start = max(self._next_start or deadline, deadline)


class _HttpxProxy:
    """Delegate HTTPX attributes; add hooks only to newly constructed clients."""

    def __init__(self, original, pacer):
        self._original, self._pacer = original, pacer

    def __getattr__(self, name):
        return getattr(self._original, name)

    def Client(self, *args, **kwargs):
        supplied = kwargs.get("event_hooks") or {}
        hooks = {name: list(callbacks) for name, callbacks in supplied.items()}
        hooks["request"] = [*hooks.get("request", []), self._pacer.before_request]
        hooks["response"] = [self._pacer.after_response, *hooks.get("response", [])]
        return self._original.Client(*args, **{**kwargs, "event_hooks": hooks})


@contextmanager
def paced_openrouter_clients(pacer):
    """Temporarily supply the frozen adapter with HTTPX pacing event hooks.

    This is an explicit launcher seam, not a change to frozen Python files.
    It does not call a provider, clear billing holds or weaken readiness gates.
    Nesting/concurrent installation is rejected rather than stacking factories.
    """
    from beyond_label import openrouter

    if not _INSTALL_LOCK.acquire(blocking=False):
        raise PacingError("pacing_already_installed")
    original = openrouter.httpx
    try:
        if original is not httpx:
            raise PacingError("pacing_already_installed")
        openrouter.httpx = _HttpxProxy(original, pacer)
        yield
    finally:
        openrouter.httpx = original
        _INSTALL_LOCK.release()
