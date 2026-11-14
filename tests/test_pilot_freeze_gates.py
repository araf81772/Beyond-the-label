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
            "allow_fallbacks":False,"parallel_tool_calls":False,"provider_docs_verified":True,"provider_rate_limit":1}
    with pytest.raises(ExecutionBlocked,match="Real smoke"):
        require_real_execution(config,stage="main")
