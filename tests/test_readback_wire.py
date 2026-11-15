"""Tool-free readback serialization uses local HTTP mocks only."""
from copy import deepcopy
import json
from pathlib import Path

import httpx
import pytest

from beyond_label.generate import generate_world, make_case
from beyond_label.openrouter import OpenRouterFreeTransport, OpenRouterPaidTransport
from beyond_label.provider import PinnedProvider, ProviderFailure, ProviderSettings, serialize_request
from beyond_label.render import decision_request, readback_request
from beyond_label.schemas import Request


def wire_settings(kind):
    if kind == "paid":
        return ProviderSettings(
            model="openai/gpt-4.1-mini", provider="OpenAI", provider_route="openai",
            provider_identity_source="openrouter_metadata", require_parameters=True,
            reasoning=None, max_price={"prompt": .4, "completion": 1.6, "request": 0, "image": 0},
        )
    return ProviderSettings(
        model="synthetic/model:free", provider="Synthetic", provider_route="synthetic",
        provider_identity_source="openrouter_metadata", require_parameters=True,
        reasoning=None, free_only=True,
    )


def adapter(kind, handler):
    settings = wire_settings(kind)
    cls = OpenRouterPaidTransport if kind == "paid" else OpenRouterFreeTransport
    return cls(settings.model, settings.provider_route, transport=httpx.MockTransport(handler))


@pytest.mark.parametrize("kind", ["free", "paid"])
def test_readback_omits_inapplicable_tool_controls_and_preserves_prefix_and_pin(kind):
    case = make_case(generate_world(1100))
    decision, readback = decision_request(case), readback_request(case)
    decision_payload = serialize_request(decision, wire_settings(kind))
    readback_payload = serialize_request(readback, wire_settings(kind))
    assert not {"tools", "tool_choice", "parallel_tool_calls"} & readback_payload.keys()
    assert readback_payload["messages"] == readback.messages
    assert readback_payload["messages"][:-1] == decision_payload["messages"]
    assert decision_payload["parallel_tool_calls"] is False
    assert decision_payload["tool_choice"] == "auto"
    for field in ("model", "provider", "temperature", "max_tokens"):
        assert readback_payload[field] == decision_payload[field]


@pytest.mark.parametrize("kind", ["free", "paid"])
def test_tool_free_payload_reaches_mock_http_unchanged(kind, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-readback-credential")
    original = serialize_request(readback_request(make_case(generate_world(1100))), wire_settings(kind))
    original.pop("parallel_tool_calls", None)
    expected = deepcopy(original)
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"result": "synthetic fixture"})

    assert adapter(kind, handler)(original) == {"result": "synthetic fixture"}
    assert seen == [expected]
    assert original == expected


@pytest.mark.parametrize("kind", ["free", "paid"])
@pytest.mark.parametrize("value", [False, True, 0, None])
def test_no_tool_request_rejects_parallel_control_before_credentials_or_http(kind, value, monkeypatch):
    payload = serialize_request(readback_request(make_case(generate_world(1100))), wire_settings(kind))
    payload["parallel_tool_calls"] = value
    monkeypatch.setattr("beyond_label.openrouter.load_local_credentials",
                        lambda: pytest.fail("invalid payload must not load credentials"))
    with pytest.raises(ProviderFailure):
        adapter(kind, lambda request: pytest.fail("invalid payload must not send HTTP"))(payload)


@pytest.mark.parametrize("kind", ["free", "paid"])
@pytest.mark.parametrize("value", ["absent", True, 0, None])
def test_tool_decision_still_requires_explicit_false_parallel_control(kind, value, monkeypatch):
    payload = serialize_request(decision_request(make_case(generate_world(1100))), wire_settings(kind))
    if value == "absent":
        payload.pop("parallel_tool_calls")
    else:
        payload["parallel_tool_calls"] = value
    monkeypatch.setattr("beyond_label.openrouter.load_local_credentials",
                        lambda: pytest.fail("invalid payload must not load credentials"))
    with pytest.raises(ProviderFailure):
        adapter(kind, lambda request: pytest.fail("invalid payload must not send HTTP"))(payload)


def test_retained_failed_readback_changes_only_inapplicable_wire_control():
    path = Path(__file__).resolve().parents[1] / "runs/paid_smoke_gpt41mini_20261115/calls.jsonl"
    original_bytes = path.read_bytes()
    events = [json.loads(line) for line in original_bytes.splitlines()]
    definition = next(event for event in events if event["event"] == "phase_defined")
    attempted = next(event for event in events if event["event"] == "attempt_started")
    assert definition["phase"] == attempted["phase"] == "readback"
    expected = deepcopy(attempted["payload"])
    assert expected.pop("parallel_tool_calls") is False
    fixed = serialize_request(Request.model_validate(definition["request"]), wire_settings("paid"))
    assert fixed == expected
    assert path.read_bytes() == original_bytes


@pytest.mark.parametrize("kind", ["free", "paid"])
def test_readback_infrastructure_retries_keep_identical_tool_free_payload(kind, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-readback-credential")
    attempts, events = [], []

    def handler(request):
        attempts.append(json.loads(request.content))
        return httpx.Response(404, json={"error": {"code": 404, "message": "synthetic routing failure"}})

    provider = PinnedProvider(wire_settings(kind), adapter(kind, handler))
    with pytest.raises(ProviderFailure, match="infrastructure_exhausted:http_error"):
        provider.request(readback_request(make_case(generate_world(1100))), log_attempt=events.append)
    assert len(attempts) == 4
    assert all(payload == attempts[0] for payload in attempts)
    assert not {"tools", "tool_choice", "parallel_tool_calls"} & attempts[0].keys()
    assert len({event["request_hash"] for event in events}) == 1


@pytest.mark.parametrize("kind", ["free", "paid"])
def test_post_inspection_continuation_retains_decision_tool_controls(kind):
    from beyond_label.run import _assistant
    from beyond_label.sandbox import Sandbox
    from beyond_label.schemas import ModelReply, ToolCall

    case = make_case(generate_world(1100))
    first = decision_request(case)
    reply = ModelReply(tool_calls=[ToolCall(id="synthetic-inspect", name="inspect",
                                            arguments={"lot_id": case.public.target_ids[0]})])
    tool_result = Sandbox(case).apply_reply(reply)
    continuation = first.model_copy(update={"messages": [*deepcopy(first.messages), _assistant(reply),
        {"role": "tool", "tool_call_id": "synthetic-inspect", "content": json.dumps(tool_result)}]})
    first_payload = serialize_request(first, wire_settings(kind))
    continued_payload = serialize_request(continuation, wire_settings(kind))
    assert continued_payload["parallel_tool_calls"] is False
    assert continued_payload["tool_choice"] == "auto"
    assert {key: value for key, value in continued_payload.items() if key != "messages"} == {
        key: value for key, value in first_payload.items() if key != "messages"}
