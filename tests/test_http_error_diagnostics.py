"""HTTP diagnostic fixtures never retain provider free text or credentials."""
import json

import httpx
import pytest

from beyond_label.generate import generate_world, make_case
from beyond_label.openrouter import OpenRouterPaidTransport
from beyond_label.provider import (
    PinnedProvider, ProviderFailure, ProviderSettings, _http_status_evidence,
    serialize_request,
)
from beyond_label.render import readback_request


SECRET = "synthetic-private-http-diagnostic-credential"
PRIVATE_TEXT = "synthetic unapproved provider metadata"


def settings():
    return ProviderSettings(
        model="openai/gpt-4.1-mini", provider="OpenAI", provider_route="openai",
        provider_identity_source="openrouter_metadata", require_parameters=True,
        temperature=0, reasoning=None, max_output_tokens=512,
        max_price={"prompt": .4, "completion": 1.6, "request": 0, "image": 0},
    )


def request():
    return readback_request(make_case(generate_world(1100)))


def transport(handler):
    return OpenRouterPaidTransport(
        "openai/gpt-4.1-mini", "openai", transport=httpx.MockTransport(handler))


def safe_exception(error):
    assert error.__context__ is None
    assert error.request.headers.get("Authorization") is None
    assert error.response.headers.get("Authorization") is None
    assert error.response.content == b""
    assert SECRET not in str(error) + repr(error) + repr(error.__dict__)
    assert PRIVATE_TEXT not in str(error) + repr(error) + repr(error.__dict__)


@pytest.mark.parametrize("status", [404, 200])
def test_error_envelopes_retain_only_numeric_code_and_unknown_category(monkeypatch, status):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    body = {"error": {"code": 404, "message": SECRET,
                       "metadata": {"raw": PRIVATE_TEXT, "Authorization": SECRET}}}
    def handler(outbound):
        return httpx.Response(status, headers={"Authorization": SECRET}, json=body)
    with pytest.raises(httpx.HTTPStatusError) as caught:
        transport(handler)(serialize_request(request(), settings()))
    safe_exception(caught.value)
    assert _http_status_evidence(caught.value) == {
        "http_status": 404, "http_diagnostic": "unknown", "api_error_code": 404}


@pytest.mark.parametrize("status", [404, 200])
@pytest.mark.parametrize("prefix,category", [
    ("No endpoints found that can handle the requested parameters.", "unsupported_parameters"),
    ("No endpoints found matching your data policy (Zero data retention).", "data_policy"),
    ("No endpoints found that satisfy the max price for this request", "price_filter"),
    ("No endpoints found supporting your data region.", "data_region"),
])
def test_verified_prefixes_emit_only_fixed_categories_even_with_private_suffix(monkeypatch, status, prefix, category):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    message = prefix + " Authorization: Bearer " + SECRET + " " + PRIVATE_TEXT
    body = {"error": {"code": 404, "message": message,
                       "metadata": {"raw": PRIVATE_TEXT, "provider_name": SECRET}}}
    with pytest.raises(httpx.HTTPStatusError) as caught:
        transport(lambda outbound: httpx.Response(status, json=body))(
            serialize_request(request(), settings()))
    safe_exception(caught.value)
    evidence = _http_status_evidence(caught.value)
    assert evidence == {"http_status": 404, "http_diagnostic": category, "api_error_code": 404}
    assert prefix not in json.dumps(evidence)


@pytest.mark.parametrize("body", [
    {"error": {"code": 404, "message": "An unknown provider error"}},
    {"error": {"code": 404, "message": "No endpoint found for model fixture"}},
    {"error": {"code": 404, "message": "No endpoints found that support the requested parameters."}},
    {"error": {"code": 404, "metadata": {"message": "No endpoints found that can handle the requested parameters."}}},
])
def test_unverified_or_nested_message_variants_are_not_classified(monkeypatch, body):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    with pytest.raises(httpx.HTTPStatusError) as caught:
        transport(lambda outbound: httpx.Response(404, json=body))(
            serialize_request(request(), settings()))
    assert _http_status_evidence(caught.value) == {
        "http_status": 404, "http_diagnostic": "unknown", "api_error_code": 404}


@pytest.mark.parametrize("body", [
    b"not-json", b"[]", b"null", b'{"error":null}',
    b'{"error":"private fixture"}', b'{"error":{"code":404,"message":[]}}',
    b'{"error":{"code":NaN}}', b'{"error":{"code":404,"code":500}}',
    b'{"error":{"code":1e999}}', b'\xff\xfe',
    b'{"error":{"message":' + b'[' * 1200 + b']' * 1200 + b'}}',
])
def test_malformed_http_error_bodies_keep_status_without_unverified_content(monkeypatch, body):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    with pytest.raises(httpx.HTTPStatusError) as caught:
        transport(lambda outbound: httpx.Response(404, content=body))(
            serialize_request(request(), settings()))
    safe_exception(caught.value)
    evidence = _http_status_evidence(caught.value)
    assert evidence["http_status"] == 404
    assert evidence["http_diagnostic"] == "unknown"
    assert set(evidence) <= {"http_status", "http_diagnostic", "api_error_code"}


@pytest.mark.parametrize("code", [True, "404", 0, 399, 600, -1, None])
def test_non_http_api_error_codes_are_not_logged(monkeypatch, code):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    with pytest.raises(httpx.HTTPStatusError) as caught:
        transport(lambda outbound: httpx.Response(404, json={"error": {"code": code}}))(
            serialize_request(request(), settings()))
    assert _http_status_evidence(caught.value) == {
        "http_status": 404, "http_diagnostic": "unknown"}


def test_oversized_error_body_is_not_parsed_or_retained(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    body = json.dumps({"error": {"code": 404, "message": SECRET,
                                  "metadata": PRIVATE_TEXT * 4096}}).encode()
    with pytest.raises(httpx.HTTPStatusError) as caught:
        transport(lambda outbound: httpx.Response(404, content=body))(
            serialize_request(request(), settings()))
    safe_exception(caught.value)
    assert _http_status_evidence(caught.value) == {
        "http_status": 404, "http_diagnostic": "unknown"}


def test_provider_journal_retains_fixed_diagnostics_without_changing_retry_payload(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    seen, events = [], []
    def handler(outbound):
        seen.append(json.loads(outbound.content))
        return httpx.Response(404, json={"error": {"code": 404, "message": SECRET,
                                                    "metadata": PRIVATE_TEXT}})
    with pytest.raises(ProviderFailure, match="infrastructure_exhausted:http_error"):
        PinnedProvider(settings(), transport(handler)).request(request(), log_attempt=events.append)
    failures = [event for event in events if event["event"] == "attempt_failed"]
    assert len(seen) == len(failures) == 4
    assert seen == [seen[0]] * 4
    assert all(event["http_diagnostic"] == "unknown" and event["api_error_code"] == 404
               for event in failures)
    assert all(event["usage"] == {} for event in failures)
    serialized = json.dumps(events)
    assert SECRET not in serialized and PRIVATE_TEXT not in serialized
    assert all("raw_response" not in event and "headers" not in event for event in failures)


def test_untrusted_diagnostic_attributes_cannot_enter_provider_logs():
    outbound = httpx.Request("POST", "https://example.invalid")
    error = httpx.HTTPStatusError("synthetic failure", request=outbound,
                                  response=httpx.Response(404, request=outbound))
    error._btl_http_diagnostic = SECRET
    error._btl_api_error_code = SECRET
    assert _http_status_evidence(error) == {"http_status": 404}
