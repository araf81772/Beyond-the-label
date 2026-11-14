"""Pure pilot thresholds and fail-closed real-run prerequisites.

Evaluating thresholds is not evidence that a pilot or human check occurred.
No function here creates a freeze tag or enables live execution.
"""
from collections.abc import Mapping


class ExecutionBlocked(RuntimeError):
    pass


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
    """Fail closed. This validates necessary gates, not sufficient live readiness."""
    if config.get("live_execution_enabled") is not True:
        raise ExecutionBlocked("Real execution is disabled by the offline instruction")
    cap = config.get("authorized_spend_cap")
    if type(cap) not in (int, float) or cap <= 0 or not config.get("currency"):
        raise ExecutionBlocked("An explicit authorized spending cap and currency are required")
    if not all(config.get(key) for key in ("model", "provider", "routing_service")):
        raise ExecutionBlocked("A model and named provider must be pinned")
    if config.get("reasoning") is None or config.get("temperature") is None:
        raise ExecutionBlocked("Reasoning and supported temperature must be fixed")
    if config.get("allow_fallbacks") is not False or config.get("parallel_tool_calls") is not False:
        raise ExecutionBlocked("Fallbacks and parallel tool calls must be disabled")
    if not config.get("provider_docs_verified") or not config.get("provider_rate_limit"):
        raise ExecutionBlocked("Provider delivery fields and limits require verification")
    if stage == "main":
        if not freeze or not freeze.get("real_smoke_passed") or not freeze.get("real_pilot_passed"):
            raise ExecutionBlocked("Real smoke and pilot gates have not been satisfied")
        if not freeze.get("hashes_verified") or not freeze.get("commit") or not freeze.get("tag"):
            raise ExecutionBlocked("Verified execution freeze is required")
        if config.get("load") not in (2, 8) or config.get("load") != freeze.get("selected_load"):
            raise ExecutionBlocked("Main load must match the pilot and freeze")
    elif stage not in ("pilot", "smoke"):
        raise ValueError("Unknown execution stage")
