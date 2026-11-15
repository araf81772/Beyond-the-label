"""HTTP adapter tests use only MockTransport and synthetic credentials."""
from copy import deepcopy
import json

import httpx
import pytest

from beyond_label.generate import generate_world, make_case
from beyond_label.openrouter import OpenRouterFreeTransport, free_account_preflight
from beyond_label.provider import ProviderFailure, ProviderSettings, serialize_request
from beyond_label.render import decision_request, readback_request


MODEL = "synthetic/model:free"
ROUTE = "synthetic-provider"
SECRET = "synthetic-openrouter-test-credential"


def payload():
    request = decision_request(make_case(generate_world(2000)))
    result = serialize_request(request, ProviderSettings(model=MODEL, provider="Synthetic Provider",
                               provider_route=ROUTE, require_parameters=True, reasoning=None))
    result["provider"]["max_price"] = {"prompt": 0, "completion": 0, "request": 0, "image": 0}
    return result


def adapter(handler, **kwargs):
    return OpenRouterFreeTransport(MODEL, ROUTE, transport=httpx.MockTransport(handler), **kwargs)


def test_fixed_endpoint_metadata_header_exact_payload_and_single_dispatch(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    seen = []
    original = payload()
    expected = deepcopy(original)
    def handler(request):
        assert request.method == "POST"
        assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer " + SECRET
        assert request.headers["X-OpenRouter-Metadata"] == "enabled"
        assert request.extensions["timeout"] == {"connect": 12.0, "read": 12.0, "write": 12.0, "pool": 12.0}
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"model": MODEL, "choices": [], "usage": {"cost": 0}})
    assert adapter(handler, timeout_seconds=12)(original)["usage"]["cost"] == 0
    assert seen == [expected] and original == expected


def test_construction_does_not_load_credentials_and_bad_payload_stops_before_loading(monkeypatch):
    def forbidden():
        raise AssertionError("credential loader was invoked")
    monkeypatch.setattr("beyond_label.openrouter.load_local_credentials", forbidden)
    transport = adapter(lambda request: pytest.fail("HTTP send forbidden"))
    invalid = payload()
    invalid["model"] = "synthetic/paid-model"
    with pytest.raises(ProviderFailure, match="free_request_model_mismatch"):
        transport(invalid)


@pytest.mark.parametrize("field,value", [
    ("model", "synthetic/model"), ("model", "synthetic/model:free:online"),
    ("plugins", [{"id": "web"}]), ("models", ["synthetic/paid"]),
    ("route", "fallback"), ("preset", "paid-preset"), ("stream", True),
    ("web_search_options", {}), ("modalities", ["image"]), ("audio", {}),
    ("transforms", ["middle-out"]), ("headers", {"Authorization": SECRET}),
    ("parallel_tool_calls", 0), ("parallel_tool_calls", True),
    ("max_tokens", 0), ("max_tokens", True), ("max_tokens", float("inf")),
])
def test_disallowed_payloads_never_reach_http_or_credentials(monkeypatch, field, value):
    value_payload = payload()
    value_payload[field] = value
    monkeypatch.setattr("beyond_label.openrouter.load_local_credentials", lambda: pytest.fail("must not load credentials"))
    with pytest.raises(ProviderFailure):
        adapter(lambda request: pytest.fail("must not send"))(value_payload)


@pytest.mark.parametrize("change", [
    {"only": [ROUTE, "other"]}, {"only": ["other"]}, {"allow_fallbacks": True},
    {"allow_fallbacks": 0}, {"require_parameters": False}, {"require_parameters": 1},
    {"order": [ROUTE]}, {"max_price": {}}, {"max_price": None},
    {"max_price": {"prompt": 0, "completion": 0, "request": 0}},
    {"max_price": {"prompt": 0, "completion": 1, "request": 0, "image": 0}},
    {"max_price": {"prompt": False, "completion": 0, "request": 0, "image": 0}},
    {"max_price": {"prompt": "0", "completion": 0, "request": 0, "image": 0}},
])
def test_no_fallback_and_all_four_zero_price_caps_are_mandatory(change):
    value_payload = payload()
    value_payload["provider"].update(change)
    with pytest.raises(ProviderFailure, match="free_request_provider_pin_invalid"):
        adapter(lambda request: pytest.fail("must not send"))(value_payload)


@pytest.mark.parametrize("mutation", ["image", "server_tool", "unknown_function", "message_extra", "call_server_tool"])
def test_only_text_messages_and_local_experiment_functions_are_allowed(mutation):
    value_payload = payload()
    if mutation == "image":
        value_payload["messages"][1]["content"] = [{"type": "image_url", "image_url": {"url": "https://example.invalid/test.png"}}]
    elif mutation == "server_tool":
        value_payload["tools"] = [{"type": "web_search"}]
    elif mutation == "unknown_function":
        value_payload["tools"][0]["function"]["name"] = "server_side_search"
    elif mutation == "message_extra":
        value_payload["messages"][1]["audio"] = {}
    else:
        value_payload["messages"][2]["tool_calls"][0]["type"] = "web_search"
    with pytest.raises(ProviderFailure):
        adapter(lambda request: pytest.fail("must not send"))(value_payload)


def test_readback_without_tools_is_accepted(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    value_payload = payload()
    value_payload["messages"] = readback_request(make_case(generate_world(2000))).messages
    del value_payload["tools"], value_payload["tool_choice"], value_payload["parallel_tool_calls"]
    assert adapter(lambda request: httpx.Response(200, json={"result": "fixture"}))(value_payload) == {"result": "fixture"}


@pytest.mark.parametrize("status", [301, 302, 307, 401, 402, 429, 500, 503])
def test_http_errors_are_single_attempt_safe_and_keep_status_without_credentials(monkeypatch, status):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    seen = []
    def handler(request):
        seen.append(request.url.path)
        return httpx.Response(status, headers={"Location": "https://example.invalid/redirect", "Authorization": SECRET},
                              json={"error": {"message": SECRET}})
    with pytest.raises(httpx.HTTPStatusError) as caught:
        adapter(handler)(payload())
    error = caught.value
    assert error.response.status_code == status
    assert seen == ["/api/v1/chat/completions"]
    assert not error.request.headers.get("Authorization")
    assert not error.response.headers.get("Authorization")
    assert error.response.content == b""
    assert SECRET not in str(error) + repr(error)


@pytest.mark.parametrize("kind", ["timeout", "connection", "other"])
def test_transport_exceptions_are_sanitized_and_never_retried_here(monkeypatch, kind):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    seen = []
    def handler(request):
        seen.append(1)
        if kind == "timeout":
            raise httpx.ReadTimeout(SECRET, request=request)
        if kind == "connection":
            raise httpx.ConnectError(SECRET, request=request)
        raise RuntimeError(SECRET)
    expected = httpx.TimeoutException if kind == "timeout" else httpx.TransportError if kind == "connection" else ProviderFailure
    with pytest.raises(expected) as caught:
        adapter(handler)(payload())
    assert len(seen) == 1
    assert SECRET not in str(caught.value) + repr(caught.value)
    assert caught.value.__context__ is None


@pytest.mark.parametrize("body", [b"invalid json", b"[]", b"true", b"NaN", b'{"cost":NaN}', b'{"cost":1e999}', b'{"x":1,"x":2}'])
def test_invalid_json_fails_with_fixed_code(monkeypatch, body):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    with pytest.raises(ProviderFailure, match="openrouter_invalid_json"):
        adapter(lambda request: httpx.Response(200, content=body))(payload())


def test_empty_response_is_left_for_outer_retry_policy(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    assert adapter(lambda request: httpx.Response(200, content=b""))(payload()) is None


def test_embedded_api_error_keeps_safe_status(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    with pytest.raises(httpx.HTTPStatusError) as caught:
        adapter(lambda request: httpx.Response(200, json={"error": {"code": 429, "message": SECRET}}))(payload())
    assert caught.value.response.status_code == 429 and SECRET not in str(caught.value)


@pytest.mark.parametrize("bad", [None, "", "  ", "invalid\nkey", "non-ascii-å"])
def test_missing_or_invalid_key_never_dispatches(monkeypatch, bad):
    if bad is not None:
        monkeypatch.setenv("OPENROUTER_API_KEY", bad)
    with pytest.raises(ProviderFailure, match="openrouter_credential_unavailable"):
        adapter(lambda request: pytest.fail("must not send"))(payload())


@pytest.mark.parametrize("bad", [0, -1, True, float("nan"), float("inf"), "10"])
def test_timeout_must_be_positive_finite_numeric(bad):
    with pytest.raises(ProviderFailure, match="invalid_http_timeout"):
        adapter(lambda request: pytest.fail("must not send"), timeout_seconds=bad)


def account_data(limit=0):
    return {"data": {"limit": limit, "label": SECRET, "hash": SECRET, "is_free_tier": False,
                     "free_model_daily_requests": {"used": 12, "limit": 50, "remaining": 38}}}


@pytest.mark.parametrize("limit,zero", [(0, True), (0.0, True), (5, False), (None, False)])
def test_account_preflight_is_get_only_and_returns_minimal_validated_evidence(monkeypatch, limit, zero):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    seen = []
    def handler(request):
        assert request.method == "GET" and str(request.url) == "https://openrouter.ai/api/v1/key"
        assert request.content == b""
        seen.append(1)
        return httpx.Response(200, json=account_data(limit))
    result = free_account_preflight(transport=httpx.MockTransport(handler))
    assert result == {"zero_hard_limit": zero, "free_model_daily_requests": {"used": 12, "limit": 50, "remaining": 38}}
    assert SECRET not in json.dumps(result) and seen == [1]


@pytest.mark.parametrize("change", [
    {"limit": False}, {"limit": "0"}, {"limit": -1}, {"free_model_daily_requests": None},
    {"free_model_daily_requests": {"used": True, "limit": 50, "remaining": 49}},
    {"free_model_daily_requests": {"used": 1.0, "limit": 50, "remaining": 49}},
    {"free_model_daily_requests": {"used": 12, "limit": 50, "remaining": 39}},
    {"free_model_daily_requests": {"used": 0, "limit": 50, "remaining": -1}},
])
def test_account_preflight_missing_or_inconsistent_limits_fail_closed(monkeypatch, change):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    body = account_data()
    body["data"].update(change)
    with pytest.raises(ProviderFailure, match="invalid_free_account_evidence"):
        free_account_preflight(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)))


@pytest.mark.parametrize("location", ["role", "tool_name", "call_name", "reasoning_effort"])
def test_unhashable_malformed_request_values_fail_with_safe_codes(location):
    value_payload = payload()
    if location == "role":
        value_payload["messages"][0]["role"] = []
    elif location == "tool_name":
        value_payload["tools"][0]["function"]["name"] = []
    elif location == "call_name":
        value_payload["messages"][2]["tool_calls"][0]["function"]["name"] = []
    else:
        value_payload["reasoning"] = {"effort": []}
    with pytest.raises(ProviderFailure):
        adapter(lambda request: pytest.fail("must not send"))(value_payload)


def test_http_client_always_verifies_tls_and_disables_environment_proxies_and_redirects(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    actual_client = httpx.Client
    options = []
    def checked_client(*args, **kwargs):
        options.append(kwargs.copy())
        return actual_client(*args, **kwargs)
    monkeypatch.setattr("beyond_label.openrouter.httpx.Client", checked_client)
    adapter(lambda request: httpx.Response(200, json={"ok": True}))(payload())
    assert len(options) == 1
    assert options[0]["verify"] is True and options[0]["trust_env"] is False
    assert options[0]["follow_redirects"] is False
    assert "headers" not in options[0]
