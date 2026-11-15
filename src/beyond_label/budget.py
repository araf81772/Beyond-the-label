"""Offline budget reservations; this ledger never authorizes or sends a request.

Each dispatch needs a verified conservative cost bound and a reservation first.
Provider-side hard limits remain necessary: a ledger cannot prevent a provider
from charging more than its supplied bound. Missing costs are not assumed zero.
"""
from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal, localcontext
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any


class BudgetError(RuntimeError):
    """Fixed reason codes only; never includes request or credential values."""


_AMOUNT = re.compile(r"[0-9]{1,64}(?:\.[0-9]{1,64})?\Z")
_ATTEMPT = re.compile(r"attempt-[0-9a-f]{32}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")


def _amount(value: object) -> Decimal:
    # Plain decimal text avoids accidental float rounding and enormous
    # exponent expansion. 64 digits on each side exceed currency precision.
    if not isinstance(value, str) or not _AMOUNT.fullmatch(value):
        raise BudgetError("invalid_decimal_amount")
    result = Decimal(value)
    if not result.is_finite() or result < 0:
        raise BudgetError("invalid_decimal_amount")
    return result


def _text(value: Decimal) -> str:
    result = format(value, "f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def _sum(values) -> Decimal:
    values = list(values)
    if not values:
        return Decimal(0)
    # Precision follows the operands, rather than the ambient Decimal context.
    exponent = min(value.as_tuple().exponent for value in values)
    integer = max(value.adjusted() + 1 for value in values)
    with localcontext() as context:
        context.prec = max(1, integer - exponent + len(str(len(values))) + 2)
        return sum(values, Decimal(0))


def _currency(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z]{3}", value):
        raise BudgetError("invalid_currency")
    return value


def _attempt(value: object) -> str:
    if not isinstance(value, str) or not _ATTEMPT.fullmatch(value):
        raise BudgetError("invalid_attempt_id")
    return value


def _canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BudgetError("invalid_budget_journal")
        result[key] = value
    return result


@contextmanager
def _lock(path: Path):
    """Nonblocking process lock, kept in place to avoid competing lock inodes."""
    handle = path.with_name("." + path.name + ".writer.lock").open("a+b")
    acquired = False
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            raise BudgetError("budget_ledger_locked") from None
        yield
    finally:
        if acquired:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


class BudgetLedger:
    """Durable accounting for one unchanged cap/currency across related runs.

    Reopening always replays raw evidence under an exclusive lock. Pending and
    unknown-cost attempts retain their full bound. Distinct retries may reserve
    from the remaining cap; deciding whether an attempt can be retried belongs
    to the run harness. A known settlement cannot be overwritten or resampled.
    """

    def __init__(self, path: Path | str, cap: str, currency: str = "USD"):
        self.path = Path(path).resolve()
        self.cap = _amount(cap)
        self.currency = _currency(currency)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _lock(self.path):
            if not self.path.exists():
                self._append([], {"event": "initialized", "version": 1,
                                  "cap": _text(self.cap), "currency": self.currency})
            self._read()

    def _append(self, events: list[dict], body: dict) -> None:
        event = {**body, "sequence": len(events) + 1,
                 "previous_hash": events[-1]["event_hash"] if events else "0" * 64}
        event["event_hash"] = hashlib.sha256(_canonical(event)).hexdigest()
        with self.path.open("ab") as handle:
            handle.write(_canonical(event) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _read(self) -> tuple[list[dict], dict[str, dict]]:
        raw = self.path.read_bytes()
        if not raw:
            raise BudgetError("empty_budget_journal")
        if not raw.endswith(b"\n"):
            raise BudgetError("torn_budget_journal")
        events: list[dict] = []
        attempts: dict[str, dict] = {}
        previous = "0" * 64
        metadata = {"sequence", "previous_hash", "event_hash"}
        # Running totals equal _snapshot() at every prefix. Recomputing the
        # sums for each reservation made replay quadratic in ledger length.
        # Amounts carry at most 128 digits, so this precision keeps them exact.
        with localcontext() as context:
            context.prec = 400
            return self._replay(raw, events, attempts, previous, metadata)

    def _replay(self, raw: bytes, events: list[dict], attempts: dict[str, dict],
                previous: str, metadata: set[str]) -> tuple[list[dict], dict[str, dict]]:
        settled = held = Decimal(0)
        exceeded = False
        for line in raw.splitlines():
            try:
                event = json.loads(line, object_pairs_hook=_unique_object)
                if not isinstance(event, dict):
                    raise BudgetError("invalid_budget_journal")
                digest = event.get("event_hash")
                body = {key: value for key, value in event.items() if key != "event_hash"}
                if (type(event.get("sequence")) is not int or event["sequence"] != len(events) + 1
                        or event.get("previous_hash") != previous
                        or not isinstance(digest, str) or not _HASH.fullmatch(digest)
                        or hashlib.sha256(_canonical(body)).hexdigest() != digest):
                    raise BudgetError("invalid_budget_journal")
                kind = event.get("event")
                if not events:
                    if set(event) != metadata | {"event", "version", "cap", "currency"} or kind != "initialized":
                        raise BudgetError("invalid_budget_journal")
                    if (type(event["version"]) is not int or event["version"] != 1
                            or _amount(event["cap"]) != self.cap or event["currency"] != self.currency):
                        raise BudgetError("budget_configuration_changed")
                elif kind == "reserved":
                    if set(event) != metadata | {"event", "attempt_id", "maximum_cost", "request_hash"}:
                        raise BudgetError("invalid_budget_journal")
                    attempt_id = _attempt(event["attempt_id"])
                    maximum = _amount(event["maximum_cost"])
                    request_hash = event["request_hash"]
                    if request_hash is not None and (not isinstance(request_hash, str) or not _HASH.fullmatch(request_hash)):
                        raise BudgetError("invalid_request_hash")
                    if attempt_id in attempts:
                        raise BudgetError("duplicate_budget_attempt")
                    remaining = self.cap - settled - held
                    if exceeded or remaining < 0 or maximum > max(Decimal(0), remaining):
                        raise BudgetError("inconsistent_budget_reservation")
                    attempts[attempt_id] = {"maximum_cost": _text(maximum), "actual_cost": None,
                                            "status": "pending", "request_hash": request_hash}
                    held += maximum
                elif kind == "settled":
                    if set(event) != metadata | {"event", "attempt_id", "actual_cost", "currency"}:
                        raise BudgetError("invalid_budget_journal")
                    attempt_id = _attempt(event["attempt_id"])
                    if attempt_id not in attempts:
                        raise BudgetError("unknown_budget_attempt")
                    attempt = attempts[attempt_id]
                    actual = None if event["actual_cost"] is None else _text(_amount(event["actual_cost"]))
                    if event["currency"] != self.currency:
                        raise BudgetError("budget_currency_mismatch")
                    if attempt["status"] == "settled" or (attempt["status"] == "unknown" and actual is None):
                        raise BudgetError("duplicate_budget_settlement")
                    if actual is not None:
                        # A receipt releases the hold; an unknown charge keeps it.
                        reserved = _amount(attempt["maximum_cost"])
                        held -= reserved
                        settled += _amount(actual)
                        exceeded = exceeded or _amount(actual) > reserved
                    attempt.update(actual_cost=actual, status="unknown" if actual is None else "settled")
                else:
                    raise BudgetError("invalid_budget_journal")
                events.append(event)
                previous = digest
            except BudgetError:
                raise
            except (ValueError, KeyError, TypeError, UnicodeError):
                raise BudgetError("invalid_budget_journal") from None
        return events, attempts

    def _snapshot(self, attempts: dict[str, dict]) -> dict[str, Any]:
        settled = _sum(_amount(a["actual_cost"]) for a in attempts.values() if a["actual_cost"] is not None)
        held = _sum(_amount(a["maximum_cost"]) for a in attempts.values() if a["actual_cost"] is None)
        remaining = _sum((self.cap, settled.copy_negate(), held.copy_negate()))
        pending = sum(a["status"] == "pending" for a in attempts.values())
        unknown = sum(a["status"] == "unknown" for a in attempts.values())
        exceeded = any(a["actual_cost"] is not None and _amount(a["actual_cost"]) > _amount(a["maximum_cost"])
                       for a in attempts.values())
        reasons = []
        if exceeded:
            reasons.append("reservation_exceeded")
        if remaining < 0:
            reasons.append("cap_exceeded")
        return {"cap": _text(self.cap), "currency": self.currency, "settled_cost": _text(settled),
                "held": _text(held), "available": _text(max(Decimal(0), remaining)),
                "pending_attempts": pending, "unknown_cost_attempts": unknown,
                "uncertain": bool(pending or unknown), "blocked": bool(reasons), "blocked_reasons": reasons,
                "reservation_exceeded": exceeded, "cap_exceeded": remaining < 0,
                "attempts": {key: dict(value) for key, value in attempts.items()}}

    def reserve(self, attempt_id: str, maximum_cost: str, *, request_hash: str | None = None) -> None:
        attempt_id = _attempt(attempt_id)
        maximum = _amount(maximum_cost)
        if request_hash is not None and (not isinstance(request_hash, str) or not _HASH.fullmatch(request_hash)):
            raise BudgetError("invalid_request_hash")
        with _lock(self.path):
            events, attempts = self._read()
            if attempt_id in attempts:
                raise BudgetError("duplicate_budget_attempt")
            state = self._snapshot(attempts)
            if state["blocked"]:
                raise BudgetError("budget_reconciliation_required")
            if maximum > _amount(state["available"]):
                raise BudgetError("budget_cap_would_be_exceeded")
            self._append(events, {"event": "reserved", "attempt_id": attempt_id,
                                  "maximum_cost": _text(maximum), "request_hash": request_hash})

    def settle(self, attempt_id: str, actual_cost: str | None, *, currency: str) -> None:
        attempt_id = _attempt(attempt_id)
        actual = None if actual_cost is None else _text(_amount(actual_cost))
        if _currency(currency) != self.currency:
            raise BudgetError("budget_currency_mismatch")
        with _lock(self.path):
            events, attempts = self._read()
            if attempt_id not in attempts:
                raise BudgetError("unknown_budget_attempt")
            attempt = attempts[attempt_id]
            if attempt["status"] == "settled" or (attempt["status"] == "unknown" and actual is None):
                raise BudgetError("duplicate_budget_settlement")
            # Persist even a quote overrun. Suppressing evidence would fabricate
            # remaining budget; the resulting snapshot blocks future dispatch.
            self._append(events, {"event": "settled", "attempt_id": attempt_id,
                                  "actual_cost": actual, "currency": self.currency})

    def snapshot(self) -> dict[str, Any]:
        with _lock(self.path):
            _, attempts = self._read()
            return self._snapshot(attempts)
