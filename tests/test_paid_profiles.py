"""Approved profile preparation: synthetic fixtures and mock HTTP only."""
from copy import deepcopy
from decimal import Decimal, localcontext
from pathlib import Path
import json

import httpx
import pytest
import yaml

from beyond_label.capabilities import check_paid_smoke_capabilities, validate_paid_smoke_capabilities
from beyond_label.controls import ControlError
from beyond_label.gates import ExecutionBlocked, require_paid_smoke_configuration
from beyond_label.generate import generate_world, make_case
from beyond_label.openrouter import OpenRouterPaidTransport
from beyond_label.paid_controls import PaidSmokeQuote
from beyond_label.paid_profile import get_paid_profile
from beyond_label.provider import ProviderFailure, ProviderSettings, parse_response, serialize_request
from beyond_label.render import decision_request, readback_request
from beyond_label.run import _assistant
from beyond_label.sandbox import Sandbox
from beyond_label.schemas import ModelReply, ToolCall


MODEL = "deepseek/deepseek-v4.1-flash-1017"


def config():
    return yaml.safe_load((Path(__file__).resolve().parents[1] / "configs/paid_smoke.yaml").read_text())


def settings():
    p = get_paid_profile(MODEL)
    return ProviderSettings(model=p["model"], provider=p["provider"], provider_route=p["provider_route"],
        provider_identity_source="openrouter_metadata", require_parameters=True, reasoning=p["reasoning"],
        max_price=p["max_price"], temperature=0, max_output_tokens=512)


def fixture():
    p = get_paid_profile(MODEL)
    return {"data": {"id": MODEL, "name": p["model_name"], "endpoints": [{
        "model_id": MODEL, "model_name": p["model_name"], "name": p["endpoint_names"][0],
        "provider_name": p["provider"], "tag": p["provider_route"], "status": 0,
        "context_length": 1048576, "max_completion_tokens": 131072,
        "supported_parameters": p["required_parameters"], "supports_tool_choice": {"auto": True},
        "pricing": p["token_prices"],
    }]}}


def test_prepared_configuration_uses_only_the_approved_profile_and_unchanged_caps():
    c = config()
    assert (c["model"], c["provider"], c["provider_route"]) == (MODEL, "PrimeIntellect", "primeintellect")
    assert c["reasoning"] == {"effort": "none"} and c["accepted_returned_models"] == []
    assert (c["authorized_total_testing_cap"], c["authorized_spend_cap"], c["maximum_inference_attempts"]) == (10, 1, 200)
    require_paid_smoke_configuration(c, stage="smoke", account_verified=False)
    with pytest.raises(ExecutionBlocked):
        require_paid_smoke_configuration(c, stage="smoke")
    for stage in ("pilot", "main"):
        with pytest.raises(ExecutionBlocked):
            require_paid_smoke_configuration(c, stage=stage, account_verified=False)


def test_profile_returns_independent_settings_and_rejects_unapproved_pins():
    p = get_paid_profile(MODEL)
    p["max_price"]["prompt"] = 999
    p["reasoning"]["effort"] = "high"
    assert get_paid_profile(MODEL)["max_price"]["prompt"] == .04368
    assert get_paid_profile(MODEL)["reasoning"] == {"effort": "none"}
    for model, route in ((MODEL, "openai"), (MODEL + ":free", "primeintellect"), (None, None)):
        with pytest.raises(ValueError):
            get_paid_profile(model, route)


@pytest.mark.parametrize("phase", ["readback", "decision", "continuation"])
def test_prepared_profile_wire_and_bound_are_exact_without_network(monkeypatch, phase):
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-profile-only")
    case = make_case(generate_world(1100))
    request = readback_request(case) if phase == "readback" else decision_request(case)
    if phase == "continuation":
        reply = ModelReply(tool_calls=[ToolCall(id="synthetic-inspect", name="inspect",
            arguments={"lot_id": case.public.target_ids[0]})])
        revealed = Sandbox(case).apply_reply(reply)
        request = request.model_copy(update={"messages": [*deepcopy(request.messages), _assistant(reply),
            {"role": "tool", "tool_call_id": "synthetic-inspect", "content": json.dumps(revealed)}]})
    payload = serialize_request(request, settings())
    assert payload["reasoning"] == {"effort": "none"}
    assert payload["provider"] == {"only": ["primeintellect"], "allow_fallbacks": False,
        "require_parameters": True, "max_price": {"prompt": .04368, "completion": .70, "request": 0, "image": 0}}
    if phase == "readback":
        assert not {"tools", "tool_choice", "parallel_tool_calls"} & payload.keys()
    else:
        assert payload["parallel_tool_calls"] is False and payload["tool_choice"] == "auto"
    with localcontext() as ctx:
        ctx.prec = 40
        expected = (Decimal(1048576) * Decimal("0.00000004368") + Decimal(512) * Decimal("0.0000007")) * Decimal("1.05")
    with localcontext() as ctx:
        ctx.prec = 3
        bound = PaidSmokeQuote()(payload)
    assert Decimal(bound.maximum_cost) == expected
    assert bound.maximum_cost == "0.048468209664" and bound.token_bound == 1049088
    seen = []
    def handler(wire):
        seen.append(json.loads(wire.content))
        return httpx.Response(200, json={"synthetic": True})
    transport = OpenRouterPaidTransport(MODEL, "primeintellect", transport=httpx.MockTransport(handler))
    assert transport(payload) == {"synthetic": True}
    assert seen == [payload]


@pytest.mark.parametrize("change", [
    lambda p: p.pop("reasoning"), lambda p: p.update(reasoning=None),
    lambda p: p.update(reasoning={"effort": "high"}), lambda p: p.update(reasoning={"enabled": False}),
    lambda p: p["provider"]["max_price"].update(prompt=.4),
    lambda p: p["provider"].update(only=["openai"]),
    lambda p: p.update(parallel_tool_calls=True),
])
def test_profile_refuses_changed_reasoning_controls_or_prices_before_http(change):
    payload = serialize_request(decision_request(make_case(generate_world(1100))), settings())
    change(payload)
    with pytest.raises(ControlError):
        PaidSmokeQuote()(payload)
    transport = OpenRouterPaidTransport(MODEL, "primeintellect",
        transport=httpx.MockTransport(lambda r: pytest.fail("No HTTP for changed settings")))
    with pytest.raises(ProviderFailure):
        transport(payload)


def test_candidate_metadata_is_compatible_but_never_authorizes_inference():
    result = validate_paid_smoke_capabilities(fixture(), config())
    assert result["compatible"] is True
    assert result["execution_authorized"] is False
    assert result["matching_endpoints"][0]["unknown_fields"] == ["pricing.image", "pricing.request"]


@pytest.mark.parametrize("mutate", [
    lambda e: e["supported_parameters"].remove("reasoning"),
    lambda e: e["supported_parameters"].remove("parallel_tool_calls"),
    lambda e: e.update(context_length=1048577),
    lambda e: e.update(context_length=None),
    lambda e: e["pricing"].update(request="0.01"),
    lambda e: e["pricing"].update(completion="0.0000016"),
    lambda e: e.update(tag="other"),
])
def test_profile_metadata_changes_stay_fail_closed(mutate):
    doc = fixture()
    mutate(doc["data"]["endpoints"][0])
    assert validate_paid_smoke_capabilities(doc, config())["compatible"] is False


def test_profile_public_fetch_uses_only_registered_anonymous_get():
    seen = []
    def handler(request):
        seen.append(request)
        assert request.method == "GET" and request.content == b""
        assert str(request.url) == "https://openrouter.ai/api/v1/models/" + MODEL + "/endpoints"
        assert "authorization" not in request.headers
        return httpx.Response(200, json=fixture())
    result = check_paid_smoke_capabilities(config(), transport=httpx.MockTransport(handler))
    assert result["compatible"] is True and len(seen) == 1


def test_returned_model_provider_and_raw_identity_remain_strict():
    payload = serialize_request(readback_request(make_case(generate_world(1100))), settings())
    raw = {"model": MODEL, "provider": "PrimeIntellect", "id": "synthetic-profile-reply",
        "choices": [{"message": {"content": "synthetic"}, "finish_reason": "stop"}],
        "usage": {"cost": .0001, "is_byok": False},
        "openrouter_metadata": {"endpoints": {"available": [
            {"model": MODEL, "provider": "PrimeIntellect", "selected": True}]}}}
    result = parse_response(raw, payload, settings())
    assert result.returned_model == MODEL and result.raw_response["model"] == MODEL
    assert result.returned_provider == "PrimeIntellect"
    altered = deepcopy(raw)
    altered["model"] = "deepseek/deepseek-v4.1-flash-20261017"
    with pytest.raises(ProviderFailure, match="model_mismatch"):
        parse_response(altered, payload, settings())
