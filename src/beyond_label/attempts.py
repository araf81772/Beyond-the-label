"""Durable, irrevocable inference-attempt allowance, independent of USD costs."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Callable

from .budget import BudgetError, _canonical, _lock, _unique_object


MAX_ATTEMPTS = 10


class AttemptLimitError(RuntimeError):
    """Fixed operational codes; suspension is not a model observation."""


class AttemptLimit:
    """Reserve before attempt_started; never refund a reservation.

    The live owner holds the project lock and checks prior evidence before
    creating this file. A second file lock serializes individual claims.
    Crashes before dispatch can consume unused slots, never create extra ones.
    This is local safety accounting, not evidence that a model call occurred.
    """

    def __init__(self, path: Path | str):
        self.path = Path(path).resolve()
        self._failed = False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with _lock(self.path):
                if not self.path.exists():
                    self._append([], {"event": "initialized", "version": 1,
                                      "maximum_attempts": MAX_ATTEMPTS})
                self._read()
        except (OSError, ValueError, BudgetError):
            raise AttemptLimitError("attempt_limit_evidence_unavailable") from None

    def _read(self) -> list[dict]:
        raw = self.path.read_bytes()
        if not raw or not raw.endswith(b"\n"):
            raise AttemptLimitError("invalid_attempt_limit_journal")
        events: list[dict] = []
        previous = "0" * 64
        metadata = {"sequence", "previous_hash", "event_hash"}
        for line in raw.splitlines():
            event = json.loads(line, object_pairs_hook=_unique_object)
            if not isinstance(event, dict):
                raise AttemptLimitError("invalid_attempt_limit_journal")
            body = {key: value for key, value in event.items() if key != "event_hash"}
            if (type(event.get("sequence")) is not int or event["sequence"] != len(events) + 1
                    or event.get("previous_hash") != previous
                    or hashlib.sha256(_canonical(body)).hexdigest() != event.get("event_hash")):
                raise AttemptLimitError("invalid_attempt_limit_journal")
            if not events:
                if (set(event) != metadata | {"event", "version", "maximum_attempts"}
                        or event["event"] != "initialized"
                        or type(event["version"]) is not int or event["version"] != 1
                        or type(event["maximum_attempts"]) is not int
                        or event["maximum_attempts"] != MAX_ATTEMPTS):
                    raise AttemptLimitError("invalid_attempt_limit_journal")
            elif (set(event) != metadata | {"event", "ordinal"}
                  or event["event"] != "attempt_reserved"
                  or type(event["ordinal"]) is not int or event["ordinal"] != len(events)
                  or len(events) > MAX_ATTEMPTS):
                raise AttemptLimitError("invalid_attempt_limit_journal")
            events.append(event)
            previous = event["event_hash"]
        return events

    def _append(self, events: list[dict], body: dict) -> None:
        event = {**body, "sequence": len(events) + 1,
                 "previous_hash": events[-1]["event_hash"] if events else "0" * 64}
        event["event_hash"] = hashlib.sha256(_canonical(event)).hexdigest()
        with self.path.open("ab") as stream:
            stream.write(_canonical(event) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())

    def snapshot(self) -> dict[str, int]:
        if self._failed:
            raise AttemptLimitError("attempt_limit_reconciliation_required")
        try:
            with _lock(self.path):
                used = len(self._read()) - 1
                return {"maximum_attempts": MAX_ATTEMPTS, "reserved_attempts": used,
                        "remaining_attempts": MAX_ATTEMPTS - used}
        except (OSError, ValueError, BudgetError, AttemptLimitError):
            self._failed = True
            raise AttemptLimitError("attempt_limit_evidence_unavailable") from None

    def claim(self) -> None:
        if self._failed:
            raise AttemptLimitError("attempt_limit_reconciliation_required")
        try:
            with _lock(self.path):
                events = self._read()
                if len(events) - 1 >= MAX_ATTEMPTS:
                    raise AttemptLimitError("authorized_attempt_limit_exhausted")
                self._append(events, {"event": "attempt_reserved", "ordinal": len(events)})
        except (OSError, ValueError, BudgetError):
            self._failed = True
            raise AttemptLimitError("attempt_limit_evidence_unavailable") from None
        except AttemptLimitError as error:
            if str(error) != "authorized_attempt_limit_exhausted":
                self._failed = True
            raise


class ExecutionSuspended(RuntimeError):
    """Fixed operational reason; no model decision is generated or resampled."""


def _utc_day() -> str:
    return datetime.now(timezone.utc).date().isoformat()


class FreeQuota:
    """Conservative local ceiling from the account's current UTC-day allowance.

    Claim before attempt_started, including retries. Other key users can still
    consume account quota; a provider rejection is retained as infrastructure
    evidence. A new day requires a fresh read-only account preflight.
    """

    def __init__(self, remaining: int, *, utc_day: Callable[[], str] = _utc_day):
        if type(remaining) is not int or remaining < 0:
            raise ExecutionSuspended("invalid_free_quota_evidence")
        self.remaining, self.utc_day, self.day = remaining, utc_day, utc_day()

    def claim(self) -> None:
        if self.utc_day() != self.day:
            raise ExecutionSuspended("free_quota_day_changed")
        if self.remaining <= 0:
            raise ExecutionSuspended("free_daily_quota_exhausted")
        self.remaining -= 1

    def check_dispatch_day(self) -> None:
        from .controls import ControlError
        if self.utc_day() != self.day:
            raise ControlError("free_quota_day_changed_before_dispatch")


class CappedFreeAttempts:
    """Concrete callback required by both supported real execution entry points."""

    def __init__(self, counter: AttemptLimit, quota: FreeQuota):
        if type(counter) is not AttemptLimit or type(quota) is not FreeQuota:
            raise AttemptLimitError("invalid_attempt_policy")
        self.counter, self.quota = counter, quota

    def __call__(self) -> None:
        self.quota.claim()
        self.counter.claim()
