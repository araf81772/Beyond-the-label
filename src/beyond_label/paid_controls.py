"""Profile-specific paid smoke ceilings; no token heuristic or network.

The pinned OpenAI endpoint advertises a 1,047,576-token context. Reserve that
entire input allowance at USD 0.40/M plus all 512 possible output tokens at USD
1.60/M. Counting output separately deliberately overcounts any shared context.
Add 5% to cover the documented maximum OpenRouter BYOK routing fee. For BYOK,
both OpenRouter usage.cost and separately billed upstream_inference_cost count
against the user's cap. Unknown billing identity or either missing cost retains
the full hold; successful responses are preserved without rewriting evidence.
The historical GPT bound is retained below. The prepared dated DeepSeek profile
reserves 1,048,576 input tokens at USD .04368/M and 512 output tokens at USD .70/M,
also with the 5% margin, yielding USD .048468209664. Each bound applies only to
its exact locked text/tool profile. The live owner must verify endpoint metadata
before enabling inference; this module alone establishes neither live pricing
nor spending authorization. Rejected oversized requests are not assumed free.

Each known successful cost releases unused reservation; unknown costs retain it
and CappedPaidAttempts stops until reconciled. This can conservatively suspend
below USD 1 when less than one worst-case request remains.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .budget import BudgetError, _amount, _sum, _text
from .controls import AttemptBound, ControlError, _observed_cost
from .paid_profile import get_paid_profile


# Historical constants remain stable for collection-version accounting/tests.
# New callers select the exact profile; never reinterpret an existing hold.
PAID_CONTEXT_TOKENS = 1_047_576
PAID_MAX_OUTPUT_TOKENS = 512
PAID_TOKEN_BOUND = PAID_CONTEXT_TOKENS + PAID_MAX_OUTPUT_TOKENS
PAID_PROMPT_USD_PER_TOKEN = "0.0000004"
PAID_COMPLETION_USD_PER_TOKEN = "0.0000016"
# (1,047,576 * 0.0000004 + 512 * 0.0000016) * 1.05, USD.
# Literal audited bound is independent of the caller's Decimal precision.
PAID_MAXIMUM_COST = "0.44084208"
SUPPORTED_MAXIMUM_COSTS = frozenset({PAID_MAXIMUM_COST, "0.048468209664"})


def paid_observed_cost(raw: Any) -> str | None:
    """Complete USD charge across OpenRouter and any separately billed BYOK.

    OpenRouter documents usage.cost as its own charge. With is_byok=true,
    usage.cost_details.upstream_inference_cost is additionally paid upstream.
    A missing/invalid explicit billing identity cannot establish total cost.
    This reads numeric evidence only and never mutates the stored response.
    """
    usage = raw.get("usage") if isinstance(raw, dict) else None
    if not isinstance(usage, dict) or type(usage.get("is_byok")) is not bool:
        return None
    router = _observed_cost(raw)
    if router is None or usage["is_byok"] is False:
        return router
    details = usage.get("cost_details")
    if not isinstance(details, dict):
        return None
    upstream = _observed_cost({"usage": {"cost": details.get("upstream_inference_cost")}})
    if upstream is None:
        return None
    try:
        total = _text(_sum((_amount(router), _amount(upstream))))
        _amount(total)
        return total
    except BudgetError:
        return None


@dataclass(frozen=True)
class PaidSmokeQuote:
    """Whole-context ceiling for the exact paid-smoke request contract."""

    def __call__(self, payload: dict[str, Any]) -> AttemptBound:
        try:
            profile = get_paid_profile(payload.get("model") if type(payload) is dict else None)
        except ValueError:
            raise ControlError("unverified_paid_request_bound") from None
        expected_provider = {
            "only": [profile["provider_route"]], "allow_fallbacks": False, "require_parameters": True,
            "max_price": profile["max_price"],
        }
        required = {"model", "provider", "messages", "max_tokens", "temperature"}
        if profile["reasoning"] is not None:
            required.add("reasoning")
        if (type(payload) is not dict or not required <= set(payload)
                or set(payload) - required - {"tools", "tool_choice", "parallel_tool_calls"}
                or (profile["reasoning"] is not None and payload["reasoning"] != profile["reasoning"])
                or type(payload["provider"]) is not dict
                or payload["provider"] != expected_provider
                or type(payload["provider"].get("allow_fallbacks")) is not bool
                or type(payload["provider"].get("require_parameters")) is not bool
                or any(type(price) not in (int, float) for price in payload["provider"]["max_price"].values())
                or type(payload["max_tokens"]) is not int or payload["max_tokens"] != PAID_MAX_OUTPUT_TOKENS
                or type(payload["temperature"]) not in (int, float) or payload["temperature"] != 0
                # Tool-free readback omits inapplicable tool controls. Tool
                # decisions/continuations still explicitly disable parallelism.
                or ("tools" in payload and payload.get("parallel_tool_calls") is not False)
                or ("tools" not in payload and "parallel_tool_calls" in payload)
                or type(payload["messages"]) is not list
                or any(type(message) is not dict or
                       (message.get("content") is not None and type(message["content"]) is not str)
                       for message in payload["messages"])
                or ("tools" in payload and (type(payload["tools"]) is not list
                                            or payload.get("tool_choice") != "auto"))
                or ("tool_choice" in payload and "tools" not in payload)):
            raise ControlError("unverified_paid_request_bound")
        return AttemptBound(profile["maximum_cost"], profile["token_bound"])
