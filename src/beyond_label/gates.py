"""Pure pilot thresholds and fail-closed real-run prerequisites.

Evaluating thresholds is not evidence that a pilot or human check occurred.
No function here creates a freeze tag or enables live execution.
"""
from collections.abc import Mapping
import math


class ExecutionBlocked(RuntimeError):
    pass


def _nonblank_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _finite_number(value: object) -> bool:
    # bool is an int subclass but is never a spending/rate/temperature value.
    return type(value) in (int, float) and math.isfinite(value)


def _positive_integer(value: object) -> bool:
    return type(value) is int and value > 0


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

    Actual smoke/pilot evidence, hashes, tag/commit identity and user spending
    authorization must be verified separately before any live execution.
    """
    if config.get("live_execution_enabled") is not True:
        raise ExecutionBlocked("Real execution is disabled by the offline instruction")
    cap = config.get("authorized_spend_cap")
    if not _finite_number(cap) or cap <= 0 or not _nonblank_string(config.get("currency")):
        raise ExecutionBlocked("An explicit authorized spending cap and currency are required")
    if not all(_nonblank_string(config.get(key)) for key in ("model", "provider", "routing_service")):
        raise ExecutionBlocked("A model and named provider must be pinned")
    temperature = config.get("temperature")
    if not isinstance(config.get("reasoning"), Mapping) or not _finite_number(temperature) or temperature < 0:
        raise ExecutionBlocked("Reasoning and supported temperature must be fixed")
    if not all(_positive_integer(config.get(key)) for key in ("max_output_tokens", "concurrency")):
        raise ExecutionBlocked("Maximum output tokens and concurrency must be positive integers")
    if config.get("allow_fallbacks") is not False or config.get("parallel_tool_calls") is not False:
        raise ExecutionBlocked("Fallbacks and parallel tool calls must be disabled")
    rate = config.get("provider_rate_limit")
    if config.get("provider_docs_verified") is not True or not _finite_number(rate) or rate <= 0:
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
