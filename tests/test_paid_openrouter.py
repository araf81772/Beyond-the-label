"""Paid smoke HTTP tests: synthetic credentials, mocked HTTP, no inference."""
from copy import deepcopy
import json
from urllib.error import HTTPError

import httpx
import pytest

from beyond_label.generate import generate_world, make_case
from beyond_label.openrouter import OpenRouterPaidTransport, paid_account_preflight
from beyond_label.provider import PinnedProvider, ProviderFailure, ProviderSettings, parse_response, serialize_request
from beyond_label.render import decision_request, readback_request


MODEL = "openai/gpt-4.1-mini"
PRICES = {"prompt": 0.40, "completion": 1.60, "request": 0, "image": 0}
SNAPSHOTS = ("openai/gpt-4.1-mini-2025-04-14", "gpt-4.1-mini-2025-04-14")
SECRET = "synthetic-paid-http-credential"


def settings(**overrides):
    values = dict(model=MODEL, provider="OpenAI", provider_route="openai",
                  provider_identity_source="openrouter_metadata", require_parameters=True,
                  reasoning=None, temperature=0, max_output_tokens=512,
                  max_price=deepcopy(PRICES), accepted_returned_models=SNAPSHOTS)
    values.update(overrides)
    return ProviderSettings(**values)


def payload():
    return serialize_request(decision_request(make_case(generate_world(1100))), settings())


def transport(handler, **kwargs):
    return OpenRouterPaidTransport(MODEL, "openai", transport=httpx.MockTransport(handler), **kwargs)


def account(**changes):
    data = {"limit": 10.0, "limit_remaining": 9.75, "usage": 0.25, "limit_reset": None,
            "include_byok_in_limit": False, "budgets": [], "effective_budget": None,
            "label": SECRET, "hash": SECRET, "unrelated": {"authorization": SECRET}}
    data.update(changes)
    return {"data": data}


def budget(**changes):
    data = {"scope": "key_limit", "limit_usd": 10, "spend_usd": 0.25,
            "remaining_usd": 9.75, "reset_interval": None, "resets_at": None,
            "include_byok": False, "guardrail_id": SECRET, "budget_id": SECRET}
    data.update(changes)
    return data


def test_paid_preflight_is_get_only_and_returns_numeric_evidence_not_identifiers(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    seen = []
    def handler(request):
        seen.append(request)
        assert request.method == "GET"
        assert str(request.url) == "https://openrouter.ai/api/v1/key"
        assert request.content == b""
        return httpx.Response(200, json=account(budgets=[budget()], effective_budget=budget()))
    evidence = paid_account_preflight(transport=httpx.MockTransport(handler))
    assert len(seen) == 1
    assert evidence == {
        "key_hard_limit_usd": 10.0, "key_limit_remaining_usd": 9.75, "key_usage_usd": 0.25,
        "key_limit_reset": None, "include_byok_in_limit": False,
        "budgets": [{key: value for key, value in budget().items()
                     if key not in {"guardrail_id", "budget_id", "resets_at"}}],
        "effective_budget": {key: value for key, value in budget().items()
                             if key not in {"guardrail_id", "budget_id", "resets_at"}},
    }
    assert SECRET not in json.dumps(evidence)
    assert "label" not in evidence and "hash" not in evidence


@pytest.mark.parametrize("changes", [
    {"limit": True}, {"limit": "10"}, {"limit": -1},
    {"limit_remaining": True}, {"limit_remaining": None}, {"limit_remaining": 11},
    {"usage": False}, {"usage": -1},
    {"limit_reset": SECRET}, {"include_byok_in_limit": 1},
    {"budgets": {}}, {"budgets": [budget(scope=SECRET)]},
    {"budgets": [budget(remaining_usd="1")]},
    {"effective_budget": budget(include_byok=0)},
    {"effective_budget": budget(reset_interval=SECRET)},
])
def test_paid_preflight_rejects_malformed_evidence_without_values(monkeypatch, changes):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    with pytest.raises(ProviderFailure, match="openrouter_paid_account_metadata_invalid") as caught:
        paid_account_preflight(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=account(**changes))))
    assert SECRET not in str(caught.value)


@pytest.mark.parametrize("changes", [{"limit": float("inf")}, {"usage": float("nan")}])
def test_paid_preflight_rejects_nonfinite_json_before_account_parsing(monkeypatch, changes):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    # The HTTP fixture must deliver the malformed bytes: httpx's json= encoder
    # correctly refuses NaN/Infinity before the adapter can receive them.
    malformed = json.dumps(account(**changes)).encode("utf-8")
    with pytest.raises(ProviderFailure, match="openrouter_invalid_json"):
        paid_account_preflight(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=malformed)))


@pytest.mark.parametrize("field", ["limit", "limit_remaining", "usage", "limit_reset"])
def test_paid_preflight_requires_key_evidence(monkeypatch, field):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    raw = account()
    del raw["data"][field]
    with pytest.raises(ProviderFailure, match="openrouter_paid_account_metadata_invalid"):
        paid_account_preflight(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=raw)))


@pytest.mark.parametrize("changes", [
    {"limit": None, "limit_remaining": None},
    {"limit": 0, "limit_remaining": 0},
    {"limit_remaining": -0.01},
    {"limit_reset": "daily"},
])
def test_paid_preflight_preserves_non_authorizing_account_states(monkeypatch, changes):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    result = paid_account_preflight(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=account(**changes))))
    assert result["key_hard_limit_usd"] == changes.get("limit", 10.0)
    assert result["key_limit_remaining_usd"] == changes.get("limit_remaining", 9.75)
    assert "authorized" not in result


def test_paid_serialization_and_single_exact_https_dispatch(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    value = payload()
    assert value["provider"] == {"only": ["openai"], "allow_fallbacks": False,
                                 "require_parameters": True, "max_price": PRICES}
    assert "reasoning" not in value and value["temperature"] == 0
    assert value["max_tokens"] == 512 and value["parallel_tool_calls"] is False
    seen = []
    def handler(request):
        assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
        assert request.method == "POST"
        assert request.headers["X-OpenRouter-Metadata"] == "enabled"
        assert request.headers["Authorization"] == "Bearer " + SECRET
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"synthetic_response": True})
    assert transport(handler)(value) == {"synthetic_response": True}
    assert seen == [value]


@pytest.mark.parametrize("field,value", [
    ("plugins", [{"id": "web"}]), ("models", [MODEL]), ("stream", True),
    ("model", "openai/gpt-4.1"), ("reasoning", None), ("reasoning", {}),
    ("temperature", 0.1), ("temperature", False), ("temperature", None),
    ("max_tokens", 513), ("max_tokens", True), ("parallel_tool_calls", 0),
    ("parallel_tool_calls", True), ("web_search_options", {}),
])
def test_paid_transport_rejects_changed_settings_before_loading_credentials(monkeypatch, field, value):
    original = payload()
    original[field] = value
    monkeypatch.setattr("beyond_label.openrouter.load_local_credentials", lambda: pytest.fail("must not load key"))
    with pytest.raises(ProviderFailure):
        transport(lambda request: pytest.fail("must not send"))(original)


@pytest.mark.parametrize("change", [
    {"only": ["azure"]}, {"only": ["openai", "azure"]}, {"allow_fallbacks": True},
    {"require_parameters": False}, {"allow_fallbacks": 0}, {"require_parameters": 1},
    {"order": ["openai"]}, {"max_price": {}},
    {"max_price": {**PRICES, "completion": 1.61}},
    {"max_price": {**PRICES, "prompt": 0.39}},
    {"max_price": {**PRICES, "request": False}},
    {"max_price": {**PRICES, "image": 0.001}},
])
def test_paid_transport_requires_exact_price_and_provider_caps(change):
    original = payload()
    original["provider"].update(change)
    with pytest.raises(ProviderFailure, match="paid_request_provider_pin_invalid"):
        transport(lambda request: pytest.fail("must not send"))(original)


@pytest.mark.parametrize("mutation", ["image", "server_tool", "unknown_function", "message_extra"])
def test_paid_transport_restricts_content_to_text_and_experiment_tools(mutation):
    original = payload()
    if mutation == "image":
        original["messages"][0]["content"] = [{"type": "image_url", "image_url": {"url": "https://example.invalid/a"}}]
    elif mutation == "server_tool":
        original["tools"] = [{"type": "web_search"}]
    elif mutation == "unknown_function":
        original["tools"][0]["function"]["name"] = "search"
    else:
        original["messages"][0]["cache_control"] = {}
    with pytest.raises(ProviderFailure, match="paid_request_content_forbidden"):
        transport(lambda request: pytest.fail("must not send"))(original)


def test_paid_readback_needs_no_tool_schema(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    original = serialize_request(readback_request(make_case(generate_world(1100))), settings())
    assert "tools" not in original and "tool_choice" not in original
    assert transport(lambda request: httpx.Response(200, json={"synthetic": True}))(original)


@pytest.mark.parametrize("model,route", [("openai/gpt-4.1", "openai"), (MODEL, "azure"),
                                         (MODEL + ":free", "openai")])
def test_paid_constructor_is_inert_and_exactly_pinned(monkeypatch, model, route):
    monkeypatch.setattr("beyond_label.openrouter.load_local_credentials", lambda: pytest.fail("must not load key"))
    with pytest.raises(ProviderFailure, match="paid_transport_pin_invalid"):
        OpenRouterPaidTransport(model, route)


@pytest.mark.parametrize("status", [302, 401, 402, 429, 500])
def test_paid_http_errors_do_not_retry_or_expose_credentials(monkeypatch, status):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    seen = []
    def handler(request):
        seen.append(1)
        return httpx.Response(status, json={"error": {"message": SECRET}})
    with pytest.raises(httpx.HTTPStatusError) as caught:
        transport(handler)(payload())
    assert seen == [1]
    assert SECRET not in str(caught.value) + repr(caught.value)
    assert not caught.value.request.headers.get("Authorization")
    assert caught.value.response.content == b""


@pytest.mark.parametrize("status", [302, 401, 402, 404, 429, 500])
def test_provider_journals_safe_http_status_and_preserves_identical_retry_requests(monkeypatch, status):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    attempts, events = [], []
    def handler(request):
        attempts.append(json.loads(request.content))
        return httpx.Response(status, headers={"Authorization": SECRET},
                              json={"error": {"message": SECRET}})
    provider = PinnedProvider(settings(), transport(handler))
    with pytest.raises(ProviderFailure, match="infrastructure_exhausted:http_error"):
        provider.request(decision_request(make_case(generate_world(1100))), log_attempt=events.append)
    failures = [event for event in events if event["event"] == "attempt_failed"]
    assert len(attempts) == len(failures) == 4
    assert attempts == [attempts[0]] * 4
    assert all(event["http_status"] == status and type(event["http_status"]) is int for event in failures)
    assert all(event["reason"] == "http_error" and event["usage"] == {} for event in failures)
    assert [event["retryable"] for event in failures] == [True, True, True, False]
    assert SECRET not in json.dumps(events)
    assert all("headers" not in event and "raw_response" not in event for event in failures)


def test_non_http_infrastructure_error_has_no_invented_status():
    events = []
    def timeout(request):
        raise TimeoutError("Synthetic private exception text")
    with pytest.raises(ProviderFailure, match="infrastructure_exhausted:timeout"):
        PinnedProvider(settings(), timeout).request(
            decision_request(make_case(generate_world(1100))), log_attempt=events.append)
    assert all("http_status" not in event for event in events)


@pytest.mark.parametrize("status", [True, "401", SECRET, 99, 600, -1, None])
def test_http_status_evidence_rejects_non_integer_or_invalid_status(status):
    from beyond_label.provider import _http_status_evidence
    error = HTTPError("https://example.invalid", status, SECRET, {"Authorization": SECRET}, None)
    assert _http_status_evidence(error) == {}


def test_urllib_http_status_uses_same_safe_numeric_contract():
    from beyond_label.provider import _http_status_evidence
    error = HTTPError("https://example.invalid", 503, SECRET, {"Authorization": SECRET}, None)
    assert _http_status_evidence(error) == {"http_status": 503}


@pytest.mark.parametrize("returned_model", [MODEL, *SNAPSHOTS])
def test_explicit_model_snapshot_alias_is_preserved_and_replays(returned_model):
    raw = {"model": returned_model, "provider": "OpenAI", "id": "synthetic-request",
           "choices": [{"message": {"content": "synthetic reply"}, "finish_reason": "stop"}],
           "usage": {"cost": 0.001},
           "openrouter_metadata": {"endpoints": {"available": [
               {"model": MODEL, "provider": "OpenAI", "selected": True}]}}}
    result = parse_response(raw, payload(), settings())
    assert result.returned_model == returned_model
    assert result.raw_response["model"] == returned_model
    assert parse_response(result.raw_response, result.payload, settings()) == result


def test_snapshot_alias_is_never_enabled_implicitly():
    configured = settings(accepted_returned_models=())
    raw = {"model": SNAPSHOTS[0]}
    with pytest.raises(ProviderFailure, match="model_mismatch"):
        parse_response(raw, serialize_request(decision_request(make_case(generate_world(1100))), configured), configured)


@pytest.mark.parametrize("is_byok", [False, True])
def test_provider_preserves_only_documented_billing_mode_boolean(is_byok):
    raw = {"model": MODEL, "provider": "OpenAI", "id": "synthetic-billing-mode",
           "choices": [{"message": {"content": "synthetic reply"}, "finish_reason": "stop"}],
           "usage": {"cost": 0.001, "is_byok": is_byok, "unrelated_boolean": True,
                     "cost_details": {"upstream_inference_cost": 0.02, "unrelated_boolean": False}},
           "openrouter_metadata": {"endpoints": {"available": [
               {"model": MODEL, "provider": "OpenAI", "selected": True}]}}}
    events = []
    result = PinnedProvider(settings(), lambda request: raw).request(
        decision_request(make_case(generate_world(1100))), log_attempt=events.append)
    assert result.usage == {"cost": 0.001, "is_byok": is_byok,
                            "cost_details": {"upstream_inference_cost": 0.02}}
    assert events[-1]["usage"] == result.usage == result.raw_response["usage"]
    assert parse_response(result.raw_response, result.payload, settings(), result.latency_seconds) == result


@pytest.mark.parametrize("overrides", [
    {"free_only": True}, {"provider": "Azure"}, {"provider_route": "azure"},
    {"provider_identity_source": "provider"}, {"accepted_returned_models": ("openai/gpt-4.1",)},
    {"accepted_returned_models": (SNAPSHOTS[0], SNAPSHOTS[0])},
    {"max_price": {**PRICES, "prompt": True}}, {"max_price": {**PRICES, "image": -1}},
    {"max_price": {**PRICES, "completion": float("inf")}},
    {"max_price": {**PRICES, "completion": 10 ** 400}},
])
def test_paid_settings_reject_nonfinite_caps_or_unapproved_snapshot_pins(overrides):
    with pytest.raises((ProviderFailure, ValueError)):
        configured = settings(**overrides)
        serialize_request(decision_request(make_case(generate_world(1100))), configured)
