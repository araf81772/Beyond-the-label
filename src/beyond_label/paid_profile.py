"""Exact documented smoke profiles; selection never authorizes dispatch.

The GPT profile is retained for historical evidence/replay. The user approved
preparing the dated DeepSeek/PrimeIntellect profile without running inference.
Public endpoint/reasoning sources are recorded in smoke_route_readiness.json.
No aliases, fallbacks, arbitrary providers or caller-selected prices are added.
"""
from copy import deepcopy


_PROFILES = {
    "openai/gpt-4.1-mini": {
        "model": "openai/gpt-4.1-mini", "model_name": "OpenAI: GPT-4.1 Mini",
        "provider": "OpenAI", "provider_route": "openai",
        "endpoint_names": ["OpenAI | openai/gpt-4.1-mini", "OpenAI | openai/gpt-4.1-mini-2025-04-14"],
        "accepted_returned_models": ["openai/gpt-4.1-mini-2025-04-14", "gpt-4.1-mini-2025-04-14"],
        "reasoning": None, "reasoning_mode": "not_applicable",
        "max_price": {"prompt": .4, "completion": 1.6, "request": 0, "image": 0},
        "token_prices": {"prompt": "0.0000004", "completion": "0.0000016"},
        "context_tokens": 1_047_576, "max_output_tokens": 512,
        "token_bound": 1_048_088, "maximum_cost": "0.44084208",
    },
    "deepseek/deepseek-v4.1-flash-1017": {
        "model": "deepseek/deepseek-v4.1-flash-1017", "model_name": "DeepSeek: DeepSeek V4.1 Flash 1017",
        "provider": "PrimeIntellect", "provider_route": "primeintellect",
        "endpoint_names": ["PrimeIntellect | deepseek/deepseek-v4.1-flash-20261017"],
        "accepted_returned_models": [],
        "reasoning": {"effort": "none"}, "reasoning_mode": "configured",
        "max_price": {"prompt": .04368, "completion": .70, "request": 0, "image": 0},
        "token_prices": {"prompt": "0.00000004368", "completion": "0.0000007"},
        "context_tokens": 1_048_576, "max_output_tokens": 512,
        # (1,048,576 * 0.00000004368 + 512 * 0.0000007) * 1.05.
        "token_bound": 1_049_088, "maximum_cost": "0.048468209664",
    },
}


def get_paid_profile(model: object, provider_route: object = None) -> dict:
    """Return independent fixed settings, rejecting any unregistered pin."""
    if type(model) is not str or model not in _PROFILES:
        raise ValueError("unverified_paid_profile")
    result = deepcopy(_PROFILES[model])
    if provider_route is not None and provider_route != result["provider_route"]:
        raise ValueError("unverified_paid_profile")
    result["endpoint_url"] = "https://openrouter.ai/api/v1/models/" + model + "/endpoints"
    result["required_parameters"] = ["max_tokens", "parallel_tool_calls", "temperature", "tool_choice", "tools"]
    if result["reasoning"] is not None:
        result["required_parameters"].append("reasoning")
    return result
