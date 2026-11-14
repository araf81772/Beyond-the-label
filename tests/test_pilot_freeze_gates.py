from pathlib import Path
import pytest
import yaml
from beyond_label.gates import ExecutionBlocked, pilot_thresholds, require_real_execution


def test_free_concurrency_must_match_the_single_owner_guard():
    config = necessary_free_config()
    config["concurrency"] = 2
    with pytest.raises(ExecutionBlocked):
        require_real_execution(config,stage="smoke")


@pytest.mark.parametrize("pairs, numeric, load, repeat", [(13,12,2,False),(14,12,8,False),(16,11,None,True),(0,0,None,True),(16,16,8,False)])
def test_exact_pilot_thresholds(pairs,numeric,load,repeat):
    result=pilot_thresholds(pairs,numeric)
    assert result["selected_load"]==load
    assert result["repeat_pilot_with_different_model"]==repeat
    assert result["load8_smoke_required"]==(load==8)
    assert result["actual_pilot_verified"] is False


@pytest.mark.parametrize("kwargs", [{"main_pairs":15},{"numeric_calls":15},{"fully_correct_main_pairs":17},{"optimal_numeric":-1},{"optimal_numeric":True}])
def test_incomplete_or_invalid_pilot_cannot_select_load(kwargs):
    args={"fully_correct_main_pairs":14,"optimal_numeric":12};args.update(kwargs)
    with pytest.raises(ValueError):pilot_thresholds(**args)


@pytest.mark.parametrize("name", ["pilot", "main"])
def test_shipped_configs_cannot_make_real_calls(name):
    root=Path(__file__).resolve().parents[1]
    config=yaml.safe_load((root/f"configs/{name}.yaml").read_text("utf-8"))
    with pytest.raises(ExecutionBlocked,match="offline"):
        require_real_execution(config,stage=name,freeze={"real_pilot_passed":True})
    assert config["model"] is None and config["provider"] is None
    assert config["authorized_spend_cap"] is None
    assert config["freeze_tag"] is None


def test_unauthorized_cap_and_missing_main_freeze_are_blocked():
    with pytest.raises(ExecutionBlocked,match="spending"):
        require_real_execution({"live_execution_enabled":True},stage="pilot")
    config={"live_execution_enabled":True,"authorized_spend_cap":1,"currency":"USD","model":"fixture",
            "provider":"fixture","routing_service":"fixture","reasoning":{},"temperature":0,
            "allow_fallbacks":False,"parallel_tool_calls":False,"provider_docs_verified":True,"provider_rate_limit":1,
            "max_output_tokens":512,"concurrency":1}
    with pytest.raises(ExecutionBlocked,match="Real smoke"):
        require_real_execution(config,stage="main")


def necessary_config():
    """Local gate fixture; neither authorization nor live-delivery evidence."""
    return {"live_execution_enabled": True, "authorized_spend_cap": 1, "currency": "USD",
            "model": "fixture", "provider": "fixture", "routing_service": "fixture",
            "reasoning": {}, "temperature": 0, "max_output_tokens": 512, "concurrency": 1,
            "allow_fallbacks": False, "parallel_tool_calls": False,
            "provider_docs_verified": True, "provider_rate_limit": 60}


def necessary_freeze():
    """Bare metadata cannot establish a real freeze; these test required fields only."""
    return {"real_smoke_passed": True, "real_pilot_passed": True, "hashes_verified": True,
            "commit": "a" * 40, "tag": "fixture-only", "selected_load": 2}


@pytest.mark.parametrize("field,value", [
    ("authorized_spend_cap", float("nan")), ("authorized_spend_cap", float("inf")),
    ("authorized_spend_cap", float("-inf")), ("authorized_spend_cap", True),
    ("currency", " "), ("currency", 1),
    ("model", " "), ("model", 1), ("provider", " "), ("routing_service", []),
    ("temperature", float("nan")), ("temperature", float("inf")),
    ("temperature", -1), ("temperature", True), ("reasoning", "off"),
    ("max_output_tokens", None), ("max_output_tokens", 0), ("max_output_tokens", True),
    ("max_output_tokens", 1.5), ("concurrency", None), ("concurrency", 0),
    ("concurrency", True), ("concurrency", 1.5),
    ("provider_docs_verified", "false"), ("provider_docs_verified", 1),
    ("provider_rate_limit", float("nan")), ("provider_rate_limit", float("inf")),
    ("provider_rate_limit", -1), ("provider_rate_limit", True),
])
def test_malformed_required_settings_fail_closed(field, value):
    config = necessary_config()
    config[field] = value
    with pytest.raises(ExecutionBlocked):
        require_real_execution(config, stage="smoke")


@pytest.mark.parametrize("field", ["real_smoke_passed", "real_pilot_passed", "hashes_verified"])
@pytest.mark.parametrize("value", ["false", 1, False, None])
def test_freeze_requires_boolean_verification_fields(field, value):
    config = {**necessary_config(), "load": 2}
    freeze = necessary_freeze()
    freeze[field] = value
    with pytest.raises(ExecutionBlocked):
        require_real_execution(config, stage="main", freeze=freeze)


@pytest.mark.parametrize("field,value", [("commit", " "), ("commit", 1), ("tag", " "), ("tag", 1)])
def test_freeze_requires_nonblank_string_identity(field, value):
    config = {**necessary_config(), "load": 2}
    freeze = necessary_freeze()
    freeze[field] = value
    with pytest.raises(ExecutionBlocked):
        require_real_execution(config, stage="main", freeze=freeze)


@pytest.mark.parametrize("field", ["load", "selected_load"])
def test_main_load_requires_integer_not_float(field):
    config = {**necessary_config(), "load": 2}
    freeze = necessary_freeze()
    (config if field == "load" else freeze)[field] = 2.0
    with pytest.raises(ExecutionBlocked):
        require_real_execution(config, stage="main", freeze=freeze)


def test_well_typed_necessary_fields_do_not_claim_sufficient_readiness():
    assert require_real_execution(necessary_config(), stage="smoke") is None
    assert require_real_execution(necessary_config(), stage="pilot") is None
    assert require_real_execution({**necessary_config(), "load": 2}, stage="main",
                                  freeze=necessary_freeze()) is None


def necessary_free_config():
    """Synthetic prerequisite metadata, never evidence of a real free endpoint."""
    return {
        **necessary_config(), "free_only": True, "paid_calls_authorized": False,
        "authorized_spend_cap": 0, "currency": "USD", "routing_service": "OpenRouter",
        "model": "fixture/fixed-model:free", "provider": "Fixture Provider",
        "provider_route": "fixture-provider", "provider_identity_source": "openrouter_metadata",
        "reasoning": None, "reasoning_mode": "omitted", "reasoning_setting_verified": True,
        "temperature": 0, "temperature_setting_verified": True,
        "provider_requests_per_minute": 20, "provider_request_limit_verified": True,
        "operator_requests_per_minute": 10, "operator_tokens_per_minute": 12000,
        "provider_tokens_per_minute": None, "provider_token_limit_status": "not_published",
        "key_hard_limit_usd": 0, "key_hard_limit_verified": True,
    }


def test_free_only_prerequisites_accept_zero_cap_without_claiming_paid_authorization():
    config = necessary_free_config()
    config.pop("provider_rate_limit")  # The legacy ambiguous scalar is not a free-run limit.
    assert require_real_execution(config, stage="smoke") is None
    assert require_real_execution(config, stage="pilot") is None
    with pytest.raises(ExecutionBlocked, match="Real smoke"):
        require_real_execution({**config, "load": 2}, stage="main")
    assert require_real_execution({**config, "load": 2}, stage="main", freeze=necessary_freeze()) is None


@pytest.mark.parametrize("field,value", [
    ("free_only", False), ("free_only", "true"), ("free_only", 1),
    ("paid_calls_authorized", True), ("paid_calls_authorized", "false"), ("paid_calls_authorized", 0),
    ("authorized_spend_cap", 0.01), ("authorized_spend_cap", -1),
    ("authorized_spend_cap", "0"), ("authorized_spend_cap", False),
    ("authorized_spend_cap", float("nan")), ("authorized_spend_cap", float("inf")),
    ("currency", "AUD"), ("currency", "usd"),
    ("key_hard_limit_usd", None), ("key_hard_limit_usd", 0.01),
    ("key_hard_limit_usd", -1), ("key_hard_limit_usd", False),
    ("key_hard_limit_usd", float("nan")), ("key_hard_limit_usd", float("inf")),
    ("key_hard_limit_verified", False), ("key_hard_limit_verified", "true"),
    ("routing_service", "fixture"), ("provider_route", " "), ("provider_route", []),
    ("provider_route", "auto"), ("provider_route", "*"), ("provider_route", "provider,other"),
    ("provider_identity_source", "provider"), ("provider", ""),
    ("reasoning_mode", None), ("reasoning_mode", "automatic"),
    ("reasoning", {}), ("reasoning_setting_verified", False),
    ("temperature", 1), ("temperature", None), ("temperature_setting_verified", "true"),
    ("provider_docs_verified", False), ("allow_fallbacks", True), ("parallel_tool_calls", True),
])
def test_free_execution_rejects_mixed_authority_and_unverified_settings(field, value):
    config = necessary_free_config()
    config[field] = value
    with pytest.raises(ExecutionBlocked):
        require_real_execution(config, stage="smoke")


@pytest.mark.parametrize("model", [
    "fixture/fixed-model", "fixture/fixed-model:free ", "fixture/fixed-model:FREE",
    "openrouter/free", "openrouter/auto", "openrouter/free:free", "openrouter/auto:free",
    "openrouter/router:free", "fixture/*:free", ["fixture/fixed-model:free"], None,
])
def test_free_execution_requires_fixed_free_model_not_router_or_paid_alias(model):
    config = {**necessary_free_config(), "model": model}
    with pytest.raises(ExecutionBlocked):
        require_real_execution(config, stage="smoke")


@pytest.mark.parametrize("field,value", [
    ("provider_requests_per_minute", None), ("provider_requests_per_minute", 0),
    ("provider_requests_per_minute", True), ("provider_requests_per_minute", 1.5),
    ("provider_request_limit_verified", False), ("provider_request_limit_verified", 1),
    ("operator_requests_per_minute", 21), ("operator_requests_per_minute", 0),
    ("operator_requests_per_minute", True), ("operator_tokens_per_minute", None),
    ("operator_tokens_per_minute", 0), ("operator_tokens_per_minute", float("inf")),
    ("provider_tokens_per_minute", 12000), ("provider_token_limit_status", "verified"),
    ("provider_token_limit_status", "unlimited"),
])
def test_free_rates_distinguish_published_limits_from_operator_throttles(field, value):
    config = {**necessary_free_config(), field: value}
    with pytest.raises(ExecutionBlocked):
        require_real_execution(config, stage="smoke")


def test_published_token_limit_bounds_operator_throttle():
    config = {**necessary_free_config(), "provider_tokens_per_minute": 12000,
              "provider_token_limit_status": "verified"}
    assert require_real_execution(config, stage="smoke") is None
    config["operator_tokens_per_minute"] = 12001
    with pytest.raises(ExecutionBlocked):
        require_real_execution(config, stage="smoke")


@pytest.mark.parametrize("mode,reasoning", [("omitted", None), ("not_applicable", None),
                                            ("configured", {"enabled": False}),
                                            ("configured", {"effort": "low"})])
def test_explicit_verified_reasoning_modes_include_omission(mode, reasoning):
    config = {**necessary_free_config(), "reasoning_mode": mode, "reasoning": reasoning}
    assert require_real_execution(config, stage="smoke") is None


@pytest.mark.parametrize("reasoning", [None, {}, "off", {"budget": float("nan")}, {"budget": object()}])
def test_configured_reasoning_must_be_explicit_finite_serializable_mapping(reasoning):
    config = {**necessary_free_config(), "reasoning_mode": "configured", "reasoning": reasoning}
    with pytest.raises(ExecutionBlocked):
        require_real_execution(config, stage="smoke")


def test_recorded_supported_default_temperature_may_be_omitted():
    config = {**necessary_free_config(), "temperature": None, "temperature_mode": "provider_default"}
    assert require_real_execution(config, stage="smoke") is None
    config["temperature_setting_verified"] = False
    with pytest.raises(ExecutionBlocked):
        require_real_execution(config, stage="smoke")


@pytest.mark.parametrize("field", ["free_only", "paid_calls_authorized", "key_hard_limit_usd",
                                   "key_hard_limit_verified", "provider_route", "provider_identity_source",
                                   "reasoning", "reasoning_mode", "reasoning_setting_verified",
                                   "temperature_setting_verified", "provider_requests_per_minute",
                                   "provider_request_limit_verified", "operator_requests_per_minute",
                                   "operator_tokens_per_minute", "provider_tokens_per_minute",
                                   "provider_token_limit_status"])
def test_free_prerequisite_fields_cannot_be_silently_defaulted(field):
    config = necessary_free_config()
    config.pop(field)
    with pytest.raises(ExecutionBlocked):
        require_real_execution(config, stage="smoke")


def test_explicit_denial_of_paid_calls_does_not_enable_legacy_positive_cap():
    config = {**necessary_config(), "free_only": False, "paid_calls_authorized": False}
    with pytest.raises(ExecutionBlocked):
        require_real_execution(config, stage="smoke")


@pytest.mark.parametrize("config,field", [(necessary_config(), "authorized_spend_cap"),
                                         (necessary_config(), "provider_rate_limit"),
                                         (necessary_free_config(), "authorized_spend_cap"),
                                         (necessary_free_config(), "key_hard_limit_usd")])
def test_unrepresentable_numeric_fields_fail_closed_without_conversion_exception(config, field):
    config = {**config, field: 10 ** 1000}
    with pytest.raises(ExecutionBlocked):
        require_real_execution(config, stage="smoke")
