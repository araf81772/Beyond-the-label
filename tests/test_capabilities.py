"""Pure synthetic capability fixtures; no model/account calls or credentials."""
from copy import deepcopy
import json

import httpx
import pytest

from beyond_label.capabilities import validate_paid_smoke_capabilities


def locked_config():
    return {
        "model": "openai/gpt-4.1-mini", "provider": "OpenAI", "provider_route": "openai",
        "require_parameters": True, "allow_fallbacks": False, "temperature": 0,
        "max_output_tokens": 512, "tool_choice": "auto", "parallel_tool_calls": False,
        "reasoning": None, "max_price": {"prompt": .4, "completion": 1.6, "request": 0, "image": 0},
    }


def catalog_fixture():
    """Reduced local fixture shaped after public metadata; not a live result."""
    return {"data": {"id": "openai/gpt-4.1-mini", "name": "OpenAI: GPT-4.1 Mini", "endpoints": [{
        "name": "OpenAI | openai/gpt-4.1-mini-2025-04-14",
        "model_id": "openai/gpt-4.1-mini", "model_name": "OpenAI: GPT-4.1 Mini",
        "provider_name": "OpenAI", "tag": "openai", "status": 0,
        "supported_parameters": ["seed", "max_tokens", "tools", "tool_choice", "temperature"],
        "supports_tool_choice": {"auto": True}, "max_completion_tokens": 32768, "context_length": 1047576,
        "pricing": {"prompt": "0.0000004", "completion": "0.0000016"},
    }]}}


def complete_fixture():
    """Hypothetical compatible catalog, explicitly distinct from observed data."""
    doc = catalog_fixture()
    endpoint = doc["data"]["endpoints"][0]
    endpoint["supported_parameters"].append("parallel_tool_calls")
    endpoint["pricing"].update(request="0", image="0")
    return doc


def test_missing_false_valued_parameter_is_not_filtered_away_and_absent_prices_are_unknown():
    doc, config = catalog_fixture(), locked_config()
    before = deepcopy((doc, config))
    first = validate_paid_smoke_capabilities(doc, config)
    assert first == validate_paid_smoke_capabilities(doc, config)
    assert (doc, config) == before
    assert first["compatible"] is False
    assert first["required_parameters"] == ["max_tokens", "parallel_tool_calls", "temperature", "tool_choice", "tools"]
    endpoint = first["matching_endpoints"][0]
    assert endpoint["missing_parameters"] == ["parallel_tool_calls"]
    assert endpoint["unknown_fields"] == ["pricing.image", "pricing.request"]
    assert endpoint["price_checks"]["prompt"]["within_ceiling"] is True
    assert endpoint["price_checks"]["request"]["within_ceiling"] is None
    assert first["http_404_cause_established"] is False
    assert first["execution_authorized"] is False


def test_hypothetical_supported_metadata_does_not_authorize_execution_or_prove_http_cause():
    result = validate_paid_smoke_capabilities(complete_fixture(), locked_config())
    assert result["compatible"] is True
    assert result["blockers"] == []
    assert result["matching_endpoints"][0]["blockers"] == []
    assert result["execution_authorized"] is result["http_404_cause_established"] is False


@pytest.mark.parametrize("omitted", [("request",), ("image",), ("request", "image")])
def test_optional_fee_omissions_remain_unknown_with_unchanged_router_ceilings(omitted):
    doc, config = complete_fixture(), locked_config()
    for field in omitted:
        del doc["data"]["endpoints"][0]["pricing"][field]
    before = deepcopy((doc, config))
    result = validate_paid_smoke_capabilities(doc, config)
    endpoint = result["matching_endpoints"][0]
    assert result["compatible"] is True
    assert endpoint["unknown_fields"] == sorted("pricing." + field for field in omitted)
    assert endpoint["blockers"] == []
    for field in omitted:
        check = endpoint["price_checks"][field]
        assert check["observed_usd"] is check["within_ceiling"] is None
        assert check["ceiling_usd"] == "0"
        assert check["enforcement"] == "locked_router_max_price"
        assert check["catalog_field_absent"] is True
    assert result["execution_authorized"] is False
    assert (doc, config) == before


@pytest.mark.parametrize("field", ["prompt", "completion"])
def test_required_token_price_omissions_still_fail_closed(field):
    doc = complete_fixture()
    del doc["data"]["endpoints"][0]["pricing"][field]
    endpoint = validate_paid_smoke_capabilities(doc, locked_config())["matching_endpoints"][0]
    assert endpoint["compatible"] is False
    assert "metadata_incomplete" in endpoint["blockers"]


@pytest.mark.parametrize("field", ["request", "image"])
@pytest.mark.parametrize("value", [None, True, "NaN", "-1", {}])
def test_malformed_optional_fees_are_not_treated_as_omitted(field, value):
    doc = complete_fixture()
    doc["data"]["endpoints"][0]["pricing"][field] = value
    endpoint = validate_paid_smoke_capabilities(doc, locked_config())["matching_endpoints"][0]
    assert endpoint["compatible"] is False
    assert "metadata_incomplete" in endpoint["blockers"]
    assert endpoint["price_checks"][field]["catalog_field_absent"] is False


@pytest.mark.parametrize("field,value", [
    ("model", "openai/gpt-4.1"), ("provider", "Azure"), ("provider_route", "azure"),
    ("require_parameters", False), ("allow_fallbacks", True), ("parallel_tool_calls", True),
    ("parallel_tool_calls", 0), ("temperature", False), ("temperature", .1),
    ("max_output_tokens", True), ("max_output_tokens", 513), ("tool_choice", "required"),
    ("reasoning", {}), ("max_price", {"prompt": .4, "completion": 1.6}),
])
def test_configuration_change_fails_closed(field, value):
    config = locked_config()
    config[field] = value
    result = validate_paid_smoke_capabilities(complete_fixture(), config)
    assert result["compatible"] is False
    assert result["blockers"] == ["invalid_locked_configuration"]


@pytest.mark.parametrize("document", [None, [], {}, {"data": []}, {"data": {}},
    {"data": {"id": "other", "endpoints": []}}])
def test_malformed_or_wrong_model_document_fails_closed(document):
    result = validate_paid_smoke_capabilities(document, locked_config())
    assert result["compatible"] is False
    assert result["blockers"] == ["invalid_endpoint_document"]


@pytest.mark.parametrize("field,value", [
    ("provider_name", "Azure"), ("tag", "azure"), ("model_id", "another/model"),
    ("model_name", "Other Model"), ("name", "OpenAI | another/model"),
    ("name", []), ("name", {}),
])
def test_unpinned_provider_or_model_is_not_a_candidate(field, value):
    doc = complete_fixture()
    doc["data"]["endpoints"][0][field] = value
    result = validate_paid_smoke_capabilities(doc, locked_config())
    assert result["compatible"] is False
    assert result["matching_endpoints"] == []
    assert result["blockers"] == ["pinned_endpoint_not_listed"]


@pytest.mark.parametrize("status", [None, False, "0", 1, -1])
def test_missing_malformed_or_unavailable_status_cannot_pass(status):
    doc = complete_fixture()
    doc["data"]["endpoints"][0]["status"] = status
    result = validate_paid_smoke_capabilities(doc, locked_config())
    assert result["compatible"] is False


@pytest.mark.parametrize("parameters", [None, {}, "tools", ["tools", 3]])
def test_unknown_supported_parameter_metadata_is_not_asserted_absent(parameters):
    doc = complete_fixture()
    doc["data"]["endpoints"][0]["supported_parameters"] = parameters
    endpoint = validate_paid_smoke_capabilities(doc, locked_config())["matching_endpoints"][0]
    assert endpoint["compatible"] is False
    assert endpoint["missing_parameters"] == []
    assert "supported_parameters" in endpoint["unknown_fields"]


@pytest.mark.parametrize("parameter", ["tools", "tool_choice", "temperature", "max_tokens", "parallel_tool_calls"])
def test_each_required_decision_capability_is_checked(parameter):
    doc = complete_fixture()
    doc["data"]["endpoints"][0]["supported_parameters"].remove(parameter)
    endpoint = validate_paid_smoke_capabilities(doc, locked_config())["matching_endpoints"][0]
    assert endpoint["missing_parameters"] == [parameter]
    assert endpoint["compatible"] is False


@pytest.mark.parametrize("choice", [None, 1, "true", False])
def test_auto_tool_choice_needs_explicit_support(choice):
    doc = complete_fixture()
    doc["data"]["endpoints"][0]["supports_tool_choice"] = {"auto": choice}
    assert validate_paid_smoke_capabilities(doc, locked_config())["compatible"] is False


@pytest.mark.parametrize("limit", [None, False, "32768", 511, 0, -1])
def test_output_allowance_must_be_verified_and_sufficient(limit):
    doc = complete_fixture()
    doc["data"]["endpoints"][0]["max_completion_tokens"] = limit
    assert validate_paid_smoke_capabilities(doc, locked_config())["compatible"] is False


@pytest.mark.parametrize("field,value,known", [
    ("prompt", "0.0000004000000000000000000001", True),
    ("completion", "0.0000017", True), ("request", ".01", True), ("image", "1", True),
    ("prompt", None, False), ("prompt", True, False), ("prompt", "NaN", False),
    ("prompt", "Infinity", False), ("prompt", "-1", False), ("prompt", {}, False),
])
def test_price_evidence_is_exact_and_never_invented(field, value, known):
    doc = complete_fixture()
    doc["data"]["endpoints"][0]["pricing"][field] = value
    endpoint = validate_paid_smoke_capabilities(doc, locked_config())["matching_endpoints"][0]
    assert endpoint["compatible"] is False
    assert endpoint["price_checks"][field]["within_ceiling"] is (False if known else None)


def test_report_never_echoes_arbitrary_catalog_text():
    doc = complete_fixture()
    secret_marker = "arbitrary-external-message-must-not-enter-report"
    doc["message"] = secret_marker
    doc["data"]["endpoints"][0]["description"] = secret_marker
    doc["data"]["endpoints"].append({"name": secret_marker})
    result = validate_paid_smoke_capabilities(doc, locked_config())
    assert secret_marker not in str(result)


def test_public_fetch_is_anonymous_fixed_get_and_does_not_load_credentials(monkeypatch):
    from beyond_label import capabilities, environment, openrouter
    marker = "synthetic-secret-never-used-by-public-fetch"
    monkeypatch.setenv("OPENROUTER_API_KEY", marker)
    def forbidden():
        pytest.fail("Public metadata must not load credentials")
    monkeypatch.setattr(environment, "load_local_credentials", forbidden)
    monkeypatch.setattr(openrouter, "_credential", forbidden)
    seen = []
    def handler(request):
        seen.append(request)
        assert request.method == "GET"
        assert str(request.url) == "https://openrouter.ai/api/v1/models/openai/gpt-4.1-mini/endpoints"
        assert request.content == b""
        assert not any(name in request.headers for name in (
            "authorization", "proxy-authorization", "cookie", "x-openrouter-metadata"))
        assert marker not in str(request.headers)
        return httpx.Response(200, json=complete_fixture())
    report = capabilities.check_paid_smoke_capabilities(
        locked_config(), transport=httpx.MockTransport(handler))
    assert report["compatible"] is True and len(seen) == 1
    assert report["fetch"]["status"] == "received"
    assert report["fetch"]["credentials_used"] is False
    assert marker not in json.dumps(report)


@pytest.mark.parametrize("response", [
    httpx.Response(302, headers={"Location": "https://example.invalid/secret"}),
    httpx.Response(401, text="must-not-echo-this-body"),
    httpx.Response(500, json={"error": "must-not-echo-this-body"}),
])
def test_public_fetch_never_follows_redirect_or_logs_error_body(response):
    from beyond_label.capabilities import check_paid_smoke_capabilities
    seen = []
    def handler(request):
        seen.append(request)
        return response
    report = check_paid_smoke_capabilities(locked_config(), transport=httpx.MockTransport(handler))
    assert report["compatible"] is False and len(seen) == 1
    assert report["fetch"]["status"] == "http_error"
    assert "must-not-echo" not in json.dumps(report)
    assert "example.invalid" not in json.dumps(report)


@pytest.mark.parametrize("body", [b"", b"not-json", b'{"data":{},"data":{}}', b'{"bad":NaN}',
                                  b'{"bad":1e10000}', b"\xff"])
def test_public_fetch_rejects_malformed_or_ambiguous_json(body):
    from beyond_label.capabilities import check_paid_smoke_capabilities
    report = check_paid_smoke_capabilities(locked_config(),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=body)))
    assert report["compatible"] is False
    assert report["fetch"]["status"] == "invalid_json"


def test_public_fetch_bounds_the_decoded_response_body(monkeypatch):
    from beyond_label import capabilities
    monkeypatch.setattr(capabilities, "MAX_METADATA_BYTES", 32)
    report = capabilities.check_paid_smoke_capabilities(locked_config(),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b" " * 33)))
    assert report["compatible"] is False
    assert report["fetch"]["status"] == "response_too_large"


@pytest.mark.parametrize("exception", [httpx.ConnectError("untrusted-error-body"),
                                       httpx.ReadTimeout("untrusted-error-body")])
def test_public_fetch_reports_fixed_transport_failure_only(exception):
    from beyond_label.capabilities import check_paid_smoke_capabilities
    def handler(request):
        raise exception
    report = check_paid_smoke_capabilities(locked_config(), transport=httpx.MockTransport(handler))
    assert report["compatible"] is False
    assert report["fetch"]["status"] == "transport_error"
    assert "untrusted-error" not in json.dumps(report)


def test_public_fetch_rejects_changed_config_before_http():
    from beyond_label.capabilities import check_paid_smoke_capabilities
    config = locked_config()
    config["parallel_tool_calls"] = True
    report = check_paid_smoke_capabilities(config,
        transport=httpx.MockTransport(lambda request: pytest.fail("No HTTP for invalid settings")))
    assert report["blockers"] == ["invalid_locked_configuration"]


@pytest.mark.parametrize("timeout", [0, -1, True, float("nan"), float("inf"), 61, "20"])
def test_public_fetch_rejects_invalid_timeout_before_http(timeout):
    from beyond_label.capabilities import check_paid_smoke_capabilities
    report = check_paid_smoke_capabilities(locked_config(), timeout_seconds=timeout,
        transport=httpx.MockTransport(lambda request: pytest.fail("No HTTP for invalid timeout")))
    assert report["compatible"] is False
    assert report["fetch"]["status"] == "invalid_timeout"
