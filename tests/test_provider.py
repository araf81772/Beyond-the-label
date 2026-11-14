"""Pinned serialization and offline response accounting, never live API calls."""

from copy import deepcopy
import json

import pytest
from pydantic import ValidationError

from beyond_label.generate import generate_world, generate_worlds, make_case
from beyond_label.provider import (
    PinnedProvider, ProviderFailure, ProviderResult, ProviderSettings,
    canonical_json, credential_presence, live_transport, parse_response, request_hash, serialize_request,
)
from beyond_label.render import decision_request, readback_request
from beyond_label.score import classify_action


def settings():
    return ProviderSettings(model="synthetic/model", provider="synthetic-provider", reasoning={"enabled": False}, max_output_tokens=512)


def response(message=None, **overrides):
    raw = {"model": "synthetic/model", "provider": "synthetic-provider", "id": "offline-request-1",
           "choices": [{"message": message or {"role": "assistant", "content": "Offline fixture"}, "finish_reason": "stop"}],
           "usage": {"prompt_tokens": 101, "completion_tokens": 23, "total_tokens": 124,
                     "cost": 0.004, "completion_tokens_details": {"reasoning_tokens": 7}}}
    raw.update(overrides)
    return raw


def test_pinned_settings_and_exact_provider_payload():
    request = decision_request(make_case(generate_world(2000)))
    payload = serialize_request(request, settings())
    assert payload["model"] == "synthetic/model"
    assert payload["provider"] == {"only": ["synthetic-provider"], "allow_fallbacks": False}
    assert payload["temperature"] == 0
    assert payload["reasoning"] == {"enabled": False}
    assert payload["max_tokens"] == 512
    assert payload["parallel_tool_calls"] is False
    assert payload["tool_choice"] == "auto"
    assert payload["messages"] == request.messages
    assert payload["tools"] == request.tools
    assert set(payload) == {"model", "provider", "temperature", "reasoning", "max_tokens", "parallel_tool_calls", "tool_choice", "messages", "tools"}
    unsupported_temperature = settings().model_copy(update={"temperature": None})
    assert "temperature" not in serialize_request(request, unsupported_temperature)
    with pytest.raises(ValidationError):
        ProviderSettings(model="", provider="provider")
    with pytest.raises(ValidationError):
        ProviderSettings(model="model", provider="", max_output_tokens=0)


def test_response_usage_metadata_and_replay_result_are_complete():
    case = make_case(generate_world(2000))
    message = {"role": "assistant", "content": None, "tool_calls": [{
        "id": "call_inspect", "type": "function",
        "function": {"name": "inspect", "arguments": json.dumps({"lot_id": case.public.target_ids[0]})},
    }]}
    raw = response(message)
    raw["choices"][0]["finish_reason"] = "tool_calls"
    events = []
    provider = PinnedProvider(settings(), lambda payload: raw)
    result = provider.request(decision_request(case), log_attempt=events.append)
    assert result.returned_model == settings().model and result.returned_provider == settings().provider
    assert result.request_id == "offline-request-1" and result.finish_reason == "tool_calls"
    assert result.usage == raw["usage"]
    assert result.raw_response["choices"][0]["message"] == message
    assert result.latency_seconds >= 0
    assert classify_action(case, result.reply) == "INSPECT_1"
    assert [event["event"] for event in events] == ["attempt_started", "attempt_succeeded"]
    assert events[1]["usage"] == result.usage
    assert ProviderResult.model_validate(events[1]["result"]) == result
    assert parse_response(result.raw_response, result.payload, settings(), result.latency_seconds) == result
    assert len({event["request_hash"] for event in events}) == 1


@pytest.mark.parametrize("message,category", [
    ({"content": "No tool response"}, "INVALID_NONE"),
    ({"content": None, "refusal": "I decline"}, "REFUSED"),
    ({"content": "I refuse to perform this request."}, "REFUSED"),
    ({"content": "I cannot comply with this request."}, "REFUSED"),
    ({"content": "I can't comply with this request."}, "REFUSED"),
    ({"content": "I need to think before proceeding."}, "INVALID_NONE"),
    ({"tool_calls": [{"function": {"name": "inspect", "arguments": "{broken"}}]}, "INVALID_ARGS"),
    ({"tool_calls": [{"wrong": "shape"}]}, "INVALID_ARGS"),
    ({"tool_calls": "malformed action"}, "INVALID_ARGS"),
    ({"tool_calls": [{"function": {"name": "unknown_tool", "arguments": "{}"}}]}, "INVALID_ARGS"),
    ({"tool_calls": [{"function": {"name": "inspect", "arguments": "{}"}}, {"function": {"name": "inspect", "arguments": "{}"}}]}, "INVALID_MULTI"),
])
def test_every_successful_invalid_or_refused_decision_is_one_sample(message, category):
    seen = []
    case = make_case(generate_world(2000))
    def transport(payload):
        seen.append(payload)
        return response(message)
    result = PinnedProvider(settings(), transport).request(decision_request(case))
    assert len(seen) == 1
    assert classify_action(case, result.reply) == category


@pytest.mark.parametrize("overrides,reason", [
    ({"model": "other/model"}, "model_mismatch"),
    ({"provider": "fallback-provider"}, "provider_mismatch"),
    ({"choices": []}, "protocol_invalid_response"),
    ({"choices": [{"message": "bad shape"}]}, "protocol_invalid_response"),
    ({"choices": [{"message": {"content": ["unsupported"]}}]}, "protocol_invalid_response"),
])
def test_protocol_errors_are_terminal_and_preserve_safe_response_evidence(overrides, reason):
    events = []
    provider = PinnedProvider(settings(), lambda payload: response(**overrides))
    with pytest.raises(ProviderFailure) as exc:
        provider.request(decision_request(make_case(generate_world(2000))), log_attempt=events.append)
    assert exc.value.reason == reason
    assert [e["event"] for e in events] == ["attempt_started", "attempt_failed"]
    assert events[-1]["retryable"] is False and events[-1]["infrastructure"] is False
    assert events[-1]["raw_response"]["model"] == overrides.get("model", "synthetic/model")
    assert events[-1]["usage"]["total_tokens"] == 124


def test_response_headers_credentials_and_exception_messages_never_enter_logs(monkeypatch):
    private_value = "synthetic-private-credential-sentinel"
    monkeypatch.setenv("OPENROUTER_API_KEY", private_value)
    message = {"content": private_value, "headers": {"Authorization": private_value}}
    raw = response(message, headers={"Authorization": private_value}, authorization=private_value)
    raw["usage"]["headers"] = {"Authorization": private_value}
    events = []
    result = PinnedProvider(settings(), lambda payload: raw).request(
        decision_request(make_case(generate_world(2000))), log_attempt=events.append,
    )
    encoded = json.dumps({"result": result.model_dump(), "events": events})
    assert private_value not in encoded and "Authorization" not in encoded and '"headers"' not in encoded
    assert result.reply.content == "[redacted]"
    assert credential_presence()["OPENROUTER_API_KEY"] is True
    assert all(isinstance(value, bool) for value in credential_presence().values())
    def bad_transport(payload):
        raise RuntimeError(private_value)
    errors = []
    with pytest.raises(ProviderFailure) as exc:
        PinnedProvider(settings(), bad_transport).request(decision_request(make_case(generate_world(2000))), log_attempt=errors.append)
    assert exc.value.reason == "transport_failure"
    assert private_value not in str(exc.value) + json.dumps(errors)
    header_text = response({"content": "Authorization: Basic synthetic-header-fixture"})
    cleaned = PinnedProvider(settings(), lambda payload: header_text).request(decision_request(make_case(generate_world(2000))))
    assert "Authorization:" not in cleaned.model_dump_json()
    assert "synthetic-header-fixture" not in cleaned.model_dump_json()


def test_payload_credentials_or_unexpected_research_fields_are_rejected_before_transport(monkeypatch):
    request = decision_request(make_case(generate_world(2000)))
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-secret-in-request")
    request.messages[0]["content"] += " synthetic-secret-in-request"
    called = []
    provider = PinnedProvider(settings(), lambda payload: called.append(payload))
    with pytest.raises(ProviderFailure, match="credential_or_header_in_request"):
        provider.request(request)
    assert called == []
    request = decision_request(make_case(generate_world(2000)))
    request.messages[0]["hidden_states"] = {"private": "FAIL"}
    with pytest.raises(ProviderFailure, match="unexpected_message_field"):
        provider.request(request)
    assert called == []
    with pytest.raises(ProviderFailure, match="offline_only_live_transport_unavailable"):
        live_transport()


@pytest.mark.parametrize("as_json", [False, True])
def test_sensitive_argument_redaction_never_repairs_an_invalid_decision(as_json):
    case = make_case(generate_world(2000))
    arguments = {"lot_id": case.public.target_ids[0], "authorization": "synthetic-extra-header"}
    message = {"content": None, "tool_calls": [{"id": "invalid-sensitive-call", "type": "function",
               "function": {"name": "inspect", "arguments": json.dumps(arguments) if as_json else arguments}}]}
    seen = []
    def transport(payload):
        seen.append(payload)
        return response(message)
    result = PinnedProvider(settings(), transport).request(decision_request(case))
    assert len(seen) == 1
    assert classify_action(case, result.reply) == "INVALID_ARGS"
    assert "synthetic-extra-header" not in result.model_dump_json()
    assert parse_response(result.raw_response, result.payload, settings(), result.latency_seconds) == result


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("field", ["prompt_tokens", "cost", "completion_tokens_details"])
def test_malformed_numeric_usage_is_terminal_and_every_log_remains_json_safe(bad, field):
    raw = response()
    raw["usage"][field] = {"reasoning_tokens": bad} if field == "completion_tokens_details" else bad
    events, seen = [], []
    def transport(payload):
        seen.append(payload)
        return raw
    with pytest.raises(ProviderFailure, match="protocol_invalid_usage"):
        PinnedProvider(settings(), transport).request(decision_request(make_case(generate_world(2000))), log_attempt=events.append)
    assert len(seen) == 1
    assert events[-1]["infrastructure"] is False and events[-1]["retryable"] is False
    assert events[-1]["raw_response"]["choices"][0]["message"]["content"] == "Offline fixture"
    for event in events:
        canonical_json(event)
    assert events[-1]["usage"].get(field) in (None, {})


@pytest.mark.parametrize("end", [9.0, float("nan"), float("inf")])
def test_invalid_latency_measurement_does_not_retry_a_successful_decision(monkeypatch, end):
    clock = iter([10.0, end])
    monkeypatch.setattr("beyond_label.provider.time.perf_counter", lambda: next(clock))
    events, seen = [], []
    def transport(payload):
        seen.append(payload)
        return response()
    with pytest.raises(ProviderFailure, match="invalid_latency_measurement"):
        PinnedProvider(settings(), transport).request(decision_request(make_case(generate_world(2000))), log_attempt=events.append)
    assert len(seen) == 1
    assert events[-1]["latency_seconds"] is None
    for event in events:
        canonical_json(event)


def test_canonical_hash_and_transport_mutation_cannot_change_request():
    request = decision_request(make_case(generate_world(2000)))
    expected = serialize_request(request, settings())
    assert request_hash(expected) == request_hash(dict(reversed(list(expected.items()))))
    seen, events = [], []
    def mutate(payload):
        seen.append(deepcopy(payload))
        payload["messages"][0]["content"] = "transport mutation"
        return response()
    result = PinnedProvider(settings(), mutate).request(request, log_attempt=events.append)
    assert seen == [expected]
    assert result.payload == expected
    assert all(e["payload"] == expected for e in events)
    assert request.messages == expected["messages"]


@pytest.mark.parametrize("dataset", ["pilot", "smoke", "main"])
@pytest.mark.parametrize("condition", ["MAIN", "HIGH-FEE", "HIGH-STAKES", "MASKED", "NUMERIC"])
def test_serialization_preserves_mapping_readback_prefix_and_hidden_state_barrier(dataset, condition):
    for world in generate_worlds(dataset):
        for load in (2, 8):
            for layout in ("separate", "inline"):
                for twin in ("a", "b"):
                    case = make_case(world, twin=twin, load=load, layout=layout, condition=condition)
                    request = decision_request(case)
                    payload = serialize_request(request, settings())
                    assert payload["messages"] == request.messages
                    changed = case.model_copy(update={"hidden_states": {"private": "secret"}, "world_id": "private-world", "seed": -1})
                    assert serialize_request(decision_request(changed), settings()) == payload
                    for record in case.public.records:
                        assert f"{record.record_id} | {record.lot_id} | result: {record.result}" in payload["messages"][3]["content"]
                    probe = serialize_request(readback_request(case), settings())
                    assert probe["messages"][:-1] == payload["messages"]
                    assert "tools" not in probe and "tool_choice" not in probe
                    assert "private-world" not in json.dumps(payload)


def test_full_provider_payload_twins_differ_only_in_two_scope_fields():
    for world in generate_worlds("main"):
        for condition in ("MAIN", "HIGH-FEE", "HIGH-STAKES"):
            for load in (2, 8):
                for layout in ("separate", "inline"):
                    a = serialize_request(decision_request(make_case(world, twin="a", condition=condition, load=load, layout=layout)), settings())
                    b = serialize_request(decision_request(make_case(world, twin="b", condition=condition, load=load, layout=layout)), settings())
                    lines_a, lines_b = a["messages"][3]["content"].splitlines(), b["messages"][3]["content"].splitlines()
                    differences = [(i, left, right) for i, (left, right) in enumerate(zip(lines_a, lines_b)) if left != right]
                    assert len(differences) == 2
                    for index, left, right in differences:
                        assert left.rsplit("tested_configuration: ", 1)[0] == right.rsplit("tested_configuration: ", 1)[0]
                        lines_b[index] = left
                    b["messages"][3]["content"] = "\n".join(lines_b)
                    assert json.dumps(a, sort_keys=True).encode() == json.dumps(b, sort_keys=True).encode()
