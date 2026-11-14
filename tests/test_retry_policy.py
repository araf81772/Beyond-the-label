"""Infrastructure attempts are bounded and distinct from decision samples."""

from copy import deepcopy
import json
from urllib.error import HTTPError

import pytest

from beyond_label.generate import generate_world, make_case
from beyond_label.provider import PinnedProvider, ProviderFailure, ProviderSettings
from beyond_label.render import decision_request


SETTINGS = ProviderSettings(model="synthetic/model", provider="synthetic-provider")


def success():
    return {"id": "synthetic-request", "model": SETTINGS.model, "provider": SETTINGS.provider,
            "choices": [{"message": {"role": "assistant", "content": "one successful decision"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5, "cost": 0}}


@pytest.mark.parametrize("failure,reason", [(None, "empty_body"), ("", "empty_body"), (TimeoutError, "timeout"), (ConnectionError, "connection_error"), (HTTPError, "http_error")])
def test_three_retries_means_four_identical_attempts(failure, reason):
    seen, events, pauses = [], [], []
    def transport(payload):
        seen.append(deepcopy(payload))
        payload["messages"][0]["content"] = "mutation must not survive"
        if failure is HTTPError:
            raise HTTPError("https://unused.invalid", 429, "unlogged secret text", {}, None)
        if isinstance(failure, type):
            raise failure("unlogged secret text")
        return failure
    provider = PinnedProvider(SETTINGS, transport, sleep=pauses.append)
    with pytest.raises(ProviderFailure) as exc:
        provider.request(decision_request(make_case(generate_world(2000))), log_attempt=events.append)
    assert exc.value.reason == f"infrastructure_exhausted:{reason}"
    assert len(seen) == 4 and all(payload == seen[0] for payload in seen)
    assert [event["attempt"] for event in events if event["event"] == "attempt_started"] == [1, 2, 3, 4]
    assert [event["event"] for event in events] == ["attempt_started", "attempt_failed"] * 4
    assert len({event["request_hash"] for event in events}) == 1
    assert all(event["payload"] == seen[0] for event in events)
    assert pauses == [1.0, 2.0, 4.0]
    assert events[-1]["retryable"] is False
    assert "unlogged secret text" not in str(exc.value) + json.dumps(events)


def test_retry_success_emits_usage_only_for_observed_success():
    events, seen = [], []
    def transport(payload):
        seen.append(payload)
        if len(seen) <= 2:
            raise TimeoutError("synthetic timeout")
        return success()
    result = PinnedProvider(SETTINGS, transport).request(decision_request(make_case(generate_world(2000))), log_attempt=events.append)
    assert len(seen) == 3
    assert events[-1]["event"] == "attempt_succeeded" and events[-1]["attempt"] == 3
    assert result.usage["total_tokens"] == 5
    assert sum(event["usage"].get("total_tokens", 0) for event in events) == 5
    assert events[-1]["result"]["reply"]["content"] == "one successful decision"


def test_resume_retains_the_original_retry_budget():
    attempts = []
    def transport(payload):
        attempts.append(payload)
        return None
    events = []
    with pytest.raises(ProviderFailure, match="infrastructure_exhausted:empty_body"):
        PinnedProvider(SETTINGS, transport).request(decision_request(make_case(generate_world(2000))), start_attempt=3, log_attempt=events.append)
    assert len(attempts) == 2
    assert [event["attempt"] for event in events if event["event"] == "attempt_started"] == [3, 4]
    for invalid in (0, 5, True, 2.5):
        with pytest.raises(ProviderFailure, match="invalid_start_attempt"):
            PinnedProvider(SETTINGS, transport).request(decision_request(make_case(generate_world(2000))), start_attempt=invalid)
    assert len(attempts) == 2


def test_empty_json_object_is_malformed_success_not_an_empty_body_retry():
    events = []
    with pytest.raises(ProviderFailure):
        PinnedProvider(SETTINGS, lambda payload: {}).request(decision_request(make_case(generate_world(2000))), log_attempt=events.append)
    assert len(events) == 2 and events[-1]["infrastructure"] is False


def test_started_event_must_be_durable_before_call_and_success_log_failure_is_not_retried():
    seen = []
    def transport(payload):
        seen.append(payload)
        return success()
    def fail_start(event):
        raise OSError("synthetic log interruption")
    provider = PinnedProvider(SETTINGS, transport)
    with pytest.raises(OSError):
        provider.request(decision_request(make_case(generate_world(2000))), log_attempt=fail_start)
    assert seen == []
    events = []
    def fail_success(event):
        if event["event"] == "attempt_succeeded":
            raise OSError("synthetic log interruption")
        events.append(event)
    with pytest.raises(OSError):
        provider.request(decision_request(make_case(generate_world(2000))), log_attempt=fail_success)
    assert len(seen) == 1 and [event["event"] for event in events] == ["attempt_started"]
