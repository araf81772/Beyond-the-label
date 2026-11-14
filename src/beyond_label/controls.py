"""Budget and rate enforcement around an explicitly injected transport.

This wrapper does not enable live execution or establish spending authority.
It requires verified per-attempt cost/token bounds and USD billing semantics.
One owner/guard per dedicated key is required for rate/concurrency accounting;
the durable ledger independently protects its cap across cooperating writers.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
import math
from threading import Lock
from typing import Any, Callable
from uuid import uuid4

from .budget import BudgetError, BudgetLedger, _amount
from .provider import ProviderFailure, TransportOutcome, canonical_json, credential_presence, _sanitized, request_hash
from .rate_limit import RateLimitError, RateLimiter


class ControlError(ProviderFailure):
    """Fixed codes only; never includes callback text or request contents."""


@dataclass(frozen=True)
class AttemptBound:
    maximum_cost: str
    token_bound: int
    currency: str = "USD"

    def __post_init__(self):
        _amount(self.maximum_cost)
        if type(self.token_bound) is not int or self.token_bound <= 0:
            raise ControlError("invalid_token_bound")
        if self.currency != "USD":
            raise ControlError("unsupported_billing_currency")


def _observed_cost(raw: Any) -> str | None:
    """OpenRouter documents credits as USD-denominated; missing is unknown."""
    usage = raw.get("usage") if isinstance(raw, dict) else None
    cost = usage.get("cost") if isinstance(usage, dict) else None
    if type(cost) not in (int, float):
        return None
    try:
        if not math.isfinite(cost) or cost < 0:
            return None
        amount = format(Decimal(str(cost)), "f")
        _amount(amount)
        return amount
    except (OverflowError, BudgetError):
        return None


class GuardedTransport:
    """Reserve before each attempt, including the provider's infrastructure retries.

    Unknown charges keep their entire reservation. A successful response is
    returned even if its evidenced cost overruns the quote, preserving the
    observed decision; the ledger then blocks any further dispatch.

    Settlement I/O failures preserve delivered responses with a separate local
    accounting marker and block this guard permanently. A restart cannot restore
    that in-memory block if the disk failed; surviving ledger/attempt evidence
    must be reconciled before constructing a new live owner. A pending record
    retains its hold; a settlement that reached disk is never rolled back.
    Cancellation during rate waiting retains an undispatched conservative hold,
    not an assertion that the provider charged for that attempt.
    """

    def __init__(self, transport: Callable, ledger: BudgetLedger, limiter: RateLimiter,
                 quote: Callable[[dict[str, Any]], AttemptBound], *, before_dispatch: Callable[[], None] | None = None):
        if not callable(transport) or not callable(quote) or ledger.currency != "USD":
            raise ControlError("invalid_control_configuration")
        self.transport, self.ledger, self.limiter, self.quote = transport, ledger, limiter, quote
        self._dispatch = Lock()
        self._accounting_blocked = False
        if before_dispatch is not None and not callable(before_dispatch):
            raise ControlError("invalid_control_configuration")
        self.before_dispatch = before_dispatch

    def __call__(self, payload: dict[str, Any]) -> Any:
        if not self._dispatch.acquire(blocking=False):
            raise ControlError("concurrent_dispatch_forbidden")
        try:
            if self._accounting_blocked:
                raise ControlError("budget_control_blocked")
            credential_presence()
            encoded = canonical_json(payload)
            if canonical_json(_sanitized(payload)) != encoded:
                raise ControlError("credential_or_header_in_controlled_request")
            digest = request_hash(payload)
            try:
                bound = self.quote(deepcopy(payload))
            except Exception:
                raise ControlError("attempt_bound_unavailable") from None
            if not isinstance(bound, AttemptBound):
                raise ControlError("invalid_attempt_bound")
            state = self.ledger.snapshot()
            if state["blocked"] or Decimal(state["available"]) < Decimal(bound.maximum_cost):
                raise BudgetError("insufficient_or_blocked_budget")
            attempt_id = "attempt-" + uuid4().hex
            self.ledger.reserve(attempt_id, bound.maximum_cost, request_hash=digest)
            # Account rate immediately before dispatch: slow durable budget I/O
            # must not consume a rate window before the provider sees a request.
            # Cancellation here leaves a conservative hold, never a paid claim.
            outbound = deepcopy(payload)
            self.limiter.acquire(bound.token_bound)
            if self.before_dispatch is not None:
                self.before_dispatch()
            try:
                raw = self.transport(outbound)
            except BaseException:
                # Preserve the original exception type for the provider's fixed
                # retry policy; the ledger stores neither it nor its text.
                try:
                    self.ledger.settle(attempt_id, None, currency=bound.currency)
                except Exception:
                    self._accounting_blocked = True
                raise
            try:
                self.ledger.settle(attempt_id, _observed_cost(raw), currency=bound.currency)
            except Exception:
                self._accounting_blocked = True
                return TransportOutcome(raw, "budget_settlement_failed")
            return raw
        except BudgetError:
            raise ControlError("budget_control_blocked") from None
        except RateLimitError:
            raise ControlError("rate_control_blocked") from None
        finally:
            self._dispatch.release()
