"""Pure pilot thresholds and fail-closed real-run prerequisites.

Evaluating thresholds is not evidence that a pilot or human check occurred.
No function here creates a freeze tag or enables live execution.
"""
from collections.abc import Mapping
import json
import math
import re
from .paid_profile import get_paid_profile


class ExecutionBlocked(RuntimeError):
    pass


def _nonblank_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _finite_number(value: object) -> bool:
    # bool is an int subclass but is never a spending/rate/temperature value.
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _positive_integer(value: object) -> bool:
    return type(value) is int and value > 0


PAID_SMOKE_AUTHORIZATION = "paid-smoke-usd1-200-v1"
PAID_SMOKE_DIRECTORY = "runs/paid_smoke_gpt41mini_20261115"


def require_paid_smoke_configuration(config: Mapping, *, stage: str,
                                      account_verified: bool = True) -> None:
    """The current paid authorization is one fixed smoke, never pilot or main.

    Public documentation does not publish one universal paid-tier rate limit.
    Local throttles are recorded honestly as operator choices. The authenticated
    key ceiling and conservative reservation supply independent spending limits.
    """
    if stage != "smoke" or not isinstance(config, Mapping):
        raise ExecutionBlocked("Paid authorization is smoke only; stop before pilot or main")
    try:
        profile = get_paid_profile(config.get("model"), config.get("provider_route"))
    except ValueError:
        raise ExecutionBlocked("Paid smoke scope or pinned settings changed") from None
    exact = {
        "authorization_id": PAID_SMOKE_AUTHORIZATION, "execution_scope": "smoke_only",
        "authorized_dataset": "smoke", "run_directory": PAID_SMOKE_DIRECTORY,
        "live_execution_enabled": True, "account_preflight_enabled": True,
        "paid_calls_authorized": True, "free_only": False, "currency": "USD",
        "routing_service": "OpenRouter", "model": profile["model"],
        "provider": profile["provider"], "provider_route": profile["provider_route"],
        "provider_identity_source": "openrouter_metadata", "require_parameters": True,
        "reasoning": profile["reasoning"], "reasoning_mode": profile["reasoning_mode"],
        "reasoning_setting_verified": True, "temperature_setting_verified": True,
        "parallel_tool_calls": False, "allow_fallbacks": False, "provider_docs_verified": True,
        "provider_requests_per_minute": None, "provider_request_limit_status": "not_published",
        "provider_tokens_per_minute": None, "provider_token_limit_status": "not_published",
        "total_token_bound_verified": True,
        "tool_choice": "auto", "no_tool_reprompt": "Respond with exactly one tool call.",
    }
    for field, expected in exact.items():
        if field not in config or type(config[field]) is not type(expected) or config[field] != expected:
            raise ExecutionBlocked("Paid smoke scope or pinned settings changed")
    for field, expected in {"authorized_spend_cap": 1, "authorized_total_testing_cap": 10,
                            "temperature": 0}.items():
        if not _finite_number(config.get(field)) or config[field] != expected:
            raise ExecutionBlocked("Paid smoke spending or temperature authorization changed")
    for field, expected in {"maximum_inference_attempts": 200, "max_output_tokens": 512,
                            "concurrency": 1, "load": 2, "schedule_seed": 271828,
                            "operator_requests_per_minute": 10, "operator_tokens_per_minute": profile["token_bound"] * 10,
                            "total_token_bound": profile["token_bound"], "no_tool_reprompts": 1,
                            "infrastructure_retries_after_initial": 3}.items():
        if type(config.get(field)) is not int or config[field] != expected:
            raise ExecutionBlocked("Paid smoke fixed attempt, token, or schedule limit changed")
    prices = config.get("max_price")
    expected_prices = profile["max_price"]
    if (not isinstance(prices, Mapping) or set(prices) != set(expected_prices)
            or any(not _finite_number(prices[key]) or prices[key] != value
                   for key, value in expected_prices.items())):
        raise ExecutionBlocked("Paid smoke routing price ceiling changed")
    if config.get("accepted_returned_models") != profile["accepted_returned_models"]:
        raise ExecutionBlocked("Paid smoke returned model identities changed")
    if account_verified:
        cap = config.get("key_hard_limit_usd")
        if (config.get("key_hard_limit_verified") is not True
                or not _finite_number(cap) or not 0 < cap <= 10):
            raise ExecutionBlocked("Paid smoke requires a verified positive hard key limit at most USD 10")


def _require_free_prerequisites(config: Mapping) -> None:
    """Necessary zero-spend fields; flags cannot authenticate their evidence.

    Operator throttles are explicit choices, not invented provider limits. An
    unpublished token limit is recorded as unknown, never zero or unlimited.
    Free routing does not waive the design's provider-side hard key ceiling.
    """
    if type(config.get("concurrency")) is not int or config["concurrency"] != 1:
        raise ExecutionBlocked("Free execution requires the single-owner concurrency of one")
    cap = config.get("authorized_spend_cap")
    if (config.get("paid_calls_authorized") is not False or not _finite_number(cap)
            or cap != 0 or config.get("currency") != "USD"):
        raise ExecutionBlocked("Free execution requires zero USD spending and paid calls explicitly disabled")
    hard_limit = config.get("key_hard_limit_usd")
    if (not _finite_number(hard_limit) or hard_limit != 0
            or config.get("key_hard_limit_verified") is not True):
        raise ExecutionBlocked("A verified zero USD hard key limit is required")
    model = config.get("model")
    if (not isinstance(model, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*:free", model)
            or model.split("/", 1)[0].lower() == "openrouter"):
        raise ExecutionBlocked("One fixed free model must be pinned; random routers and paid aliases are forbidden")
    route, provider = config.get("provider_route"), config.get("provider")
    if (config.get("routing_service") != "OpenRouter"
            or not isinstance(route, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", route)
            or route.lower() in {"auto", "free", "random", "router"}
            or not _nonblank_string(provider) or provider != provider.strip()
            or "\n" in provider or "\r" in provider
            or config.get("provider_identity_source") != "openrouter_metadata"):
        raise ExecutionBlocked("The free route and returned provider identity must be pinned")
    reasoning, mode = config.get("reasoning"), config.get("reasoning_mode")
    if "reasoning" not in config or config.get("reasoning_setting_verified") is not True:
        raise ExecutionBlocked("The supported reasoning setting must be fixed and verified")
    if mode in ("omitted", "not_applicable"):
        if reasoning is not None:
            raise ExecutionBlocked("Omitted reasoning must be recorded explicitly as null")
    elif mode == "configured" and isinstance(reasoning, Mapping) and reasoning:
        try:
            json.dumps(dict(reasoning), allow_nan=False)
        except (TypeError, ValueError, OverflowError):
            raise ExecutionBlocked("Configured reasoning must contain finite serializable settings") from None
    else:
        raise ExecutionBlocked("The supported reasoning mode must be explicit")
    temperature = config.get("temperature")
    if config.get("temperature_setting_verified") is not True:
        raise ExecutionBlocked("The supported temperature setting must be verified")
    if temperature is None:
        if "temperature" not in config or config.get("temperature_mode") != "provider_default":
            raise ExecutionBlocked("Omitted temperature requires a recorded supported fixed default")
    elif not _finite_number(temperature) or temperature != 0:
        raise ExecutionBlocked("Use temperature zero where supported, otherwise the recorded fixed default")
    request_limit = config.get("provider_requests_per_minute")
    operator_requests = config.get("operator_requests_per_minute")
    operator_tokens = config.get("operator_tokens_per_minute")
    if (config.get("provider_request_limit_verified") is not True
            or not all(_positive_integer(value) for value in (request_limit, operator_requests, operator_tokens))
            or operator_requests > request_limit):
        raise ExecutionBlocked("Verified request limits and bounded positive operator throttles are required")
    token_limit = config.get("provider_tokens_per_minute")
    token_status = config.get("provider_token_limit_status")
    if "provider_tokens_per_minute" not in config:
        raise ExecutionBlocked("The provider token limit must be recorded without fabrication")
    if token_status == "not_published":
        if token_limit is not None:
            raise ExecutionBlocked("An unpublished provider token limit must remain unknown")
    elif token_status == "verified":
        if not _positive_integer(token_limit) or operator_tokens > token_limit:
            raise ExecutionBlocked("The operator token throttle must respect the verified provider limit")
    else:
        raise ExecutionBlocked("Provider token limit verification status is required")


def pilot_thresholds(fully_correct_main_pairs: int, optimal_numeric: int,
                     main_pairs: int = 16, numeric_calls: int = 16) -> dict:
    values = (fully_correct_main_pairs, optimal_numeric, main_pairs, numeric_calls)
    if any(type(value) is not int for value in values):
        raise ValueError("Pilot counts must be integers")
    if main_pairs != 16 or numeric_calls != 16:
        raise ValueError("Incomplete pilot denominators")
    if not 0 <= fully_correct_main_pairs <= 16 or not 0 <= optimal_numeric <= 16:
        raise ValueError("Invalid pilot numerator")
    if optimal_numeric < 12:
        return {"repeat_pilot_with_different_model": True, "selected_load": None,
                "load8_smoke_required": False, "actual_pilot_verified": False}
    load = 8 if fully_correct_main_pairs >= 14 else 2
    return {"repeat_pilot_with_different_model": False, "selected_load": load,
            "load8_smoke_required": load == 8, "actual_pilot_verified": False}


def require_real_execution(config: Mapping, *, stage: str, freeze: Mapping | None = None) -> None:
    """Validate necessary fields, not authorization or evidence authenticity.

    Actual smoke/pilot evidence, hashes, tag/commit identity and user execution
    authorization must be verified separately. Free mode allows only zero USD
    exposure with paid calls explicitly disabled; it never authorizes paid use.
    """
    if config.get("authorization_id") == PAID_SMOKE_AUTHORIZATION:
        require_paid_smoke_configuration(config, stage=stage)
        if freeze is not None:
            raise ExecutionBlocked("Paid smoke authorization does not include an execution freeze")
        return
    if config.get("live_execution_enabled") is not True:
        raise ExecutionBlocked("Real execution is disabled by the offline instruction")
    free_only = config.get("free_only", False)
    if type(free_only) is not bool:
        raise ExecutionBlocked("Free-only mode must be an explicit boolean")
    if free_only:
        _require_free_prerequisites(config)
    else:
        if "paid_calls_authorized" in config and config["paid_calls_authorized"] is not True:
            raise ExecutionBlocked("Paid execution is not authorized")
        cap = config.get("authorized_spend_cap")
        if not _finite_number(cap) or cap <= 0 or not _nonblank_string(config.get("currency")):
            raise ExecutionBlocked("An explicit authorized spending cap and currency are required")
    if not all(_nonblank_string(config.get(key)) for key in ("model", "provider", "routing_service")):
        raise ExecutionBlocked("A model and named provider must be pinned")
    temperature = config.get("temperature")
    if not free_only and (not isinstance(config.get("reasoning"), Mapping)
                          or not _finite_number(temperature) or temperature < 0):
        raise ExecutionBlocked("Reasoning and supported temperature must be fixed")
    if not all(_positive_integer(config.get(key)) for key in ("max_output_tokens", "concurrency")):
        raise ExecutionBlocked("Maximum output tokens and concurrency must be positive integers")
    if config.get("allow_fallbacks") is not False or config.get("parallel_tool_calls") is not False:
        raise ExecutionBlocked("Fallbacks and parallel tool calls must be disabled")
    rate = config.get("provider_rate_limit")
    if (config.get("provider_docs_verified") is not True
            or (not free_only and (not _finite_number(rate) or rate <= 0))):
        raise ExecutionBlocked("Provider delivery fields and limits require verification")
    if stage == "main":
        if (not isinstance(freeze, Mapping) or freeze.get("real_smoke_passed") is not True
                or freeze.get("real_pilot_passed") is not True):
            raise ExecutionBlocked("Real smoke and pilot gates have not been satisfied")
        if (freeze.get("hashes_verified") is not True or not _nonblank_string(freeze.get("commit"))
                or not _nonblank_string(freeze.get("tag"))):
            raise ExecutionBlocked("Verified execution freeze is required")
        if (type(config.get("load")) is not int or type(freeze.get("selected_load")) is not int
                or config.get("load") not in (2, 8) or config.get("load") != freeze.get("selected_load")):
            raise ExecutionBlocked("Main load must match the pilot and freeze")
    elif stage not in ("pilot", "smoke"):
        raise ValueError("Unknown execution stage")
