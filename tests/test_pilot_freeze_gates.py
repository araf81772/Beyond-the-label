from pathlib import Path
import pytest
import yaml
from beyond_label.gates import ExecutionBlocked, pilot_thresholds, require_real_execution


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
