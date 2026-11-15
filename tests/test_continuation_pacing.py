"""Inactive operational pacing, exercised only through local HTTPX fixtures."""
from datetime import datetime, timezone
from email.utils import format_datetime
import importlib.util
import json
from pathlib import Path

import httpx
import pytest

from beyond_label import openrouter


URL = "https://openrouter.ai/api/v1/chat/completions"
BODY = b'{"model":"fixture","messages":[{"role":"user","content":"unchanged"}]}'


def load_helper():
    path = Path(__file__).resolve().parents[1] / "scripts/continuation_pacing.py"
    assert path.is_file(), "The inactive operational pacing helper is not implemented"
    spec = importlib.util.spec_from_file_location("continuation_pacing_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.epoch = 1800000000.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def wall_time(self):
        return self.epoch + self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def pacer(helper, clock):
    return helper.InferencePacer(clock=clock.monotonic, wall_clock=clock.wall_time,
                                 sleep=clock.sleep)


def test_every_post_is_spaced_across_new_clients_without_changing_bytes():
    helper = load_helper()
    clock, sent = FakeTime(), []
    original = openrouter.httpx
    client_class = httpx.Client

    def handler(request):
        sent.append((clock.now, request.content, str(request.url), request.headers["x-fixture"]))
        return httpx.Response(200, content=b'{"unchanged":true}')

    with helper.paced_openrouter_clients(pacer(helper, clock)):
        for _ in range(4):
            with openrouter.httpx.Client(transport=httpx.MockTransport(handler), trust_env=False) as client:
                assert type(client) is client_class
                assert client.post(URL, content=BODY, headers={"x-fixture": "same"}).content == b'{"unchanged":true}'
    assert sent == [(t, BODY, URL, "same") for t in (15, 30, 45, 60)]
    assert openrouter.httpx is original and httpx.Client is client_class


def test_get_and_other_service_posts_do_not_consume_inference_cadence():
    helper = load_helper()
    clock, sent = FakeTime(), []

    def handler(request):
        sent.append((request.method, str(request.url), clock.now))
        return httpx.Response(200, json={})

    with helper.paced_openrouter_clients(pacer(helper, clock)):
        with openrouter.httpx.Client(transport=httpx.MockTransport(handler)) as client:
            client.get("https://openrouter.ai/api/v1/key")
            client.post(URL, content=BODY)
            client.get("https://openrouter.ai/api/v1/key")
            client.post("https://fixture.invalid/other", content=BODY)
            client.post(URL, content=BODY)
    assert [row[2] for row in sent] == [0, 15, 15, 15, 30]


@pytest.mark.parametrize("status,body,retry_after,expected", [
    (429, b'{}', None, 60),
    (429, b'{}', "90", 90),
    (429, b'{}', "90.5", 90.5),
    (429, b'{}', "1", 60),
    (200, b'{"error":{"code":429}}', "75", 75),
    (200, b'{"error":{"code":429}}', None, 60),
    (200, b'{"error":{"code":"429"}}', None, 15),
    (200, b'not json', None, 15),
    (429, b'{}', "NaN", 60),
    (429, b'{}', "-5", 60),
    (503, b'{}', "90", 90),
    (503, b'{}', "1", 15),
    (200, b'{}', "45", 45),
])
def test_cooldown_honors_rate_error_and_numeric_retry_after(status, body, retry_after, expected):
    helper = load_helper()
    clock, sent = FakeTime(), []

    def handler(request):
        sent.append(clock.now)
        return httpx.Response(status, content=body,
                              headers={} if retry_after is None else {"Retry-After": retry_after})

    with helper.paced_openrouter_clients(pacer(helper, clock)):
        with openrouter.httpx.Client(transport=httpx.MockTransport(handler)) as client:
            first = client.post(URL, content=BODY)
            assert first.status_code == status and first.content == body
            client.post(URL, content=BODY)
    assert sent == [15, 15 + expected]


def test_http_date_cooldown_is_measured_from_response_receipt():
    helper = load_helper()
    clock, sent = FakeTime(), []
    retry_date = format_datetime(datetime.fromtimestamp(clock.epoch + 100, timezone.utc), usegmt=True)

    def handler(request):
        sent.append(clock.now)
        clock.now += 5
        return httpx.Response(429, headers={"Retry-After": retry_date}, content=b'{}')

    with helper.paced_openrouter_clients(pacer(helper, clock)):
        with openrouter.httpx.Client(transport=httpx.MockTransport(handler)) as client:
            client.post(URL, content=BODY)
            client.post(URL, content=BODY)
    assert sent == [15, 100]


def test_existing_hooks_survive_and_scope_restores_after_failure():
    helper = load_helper()
    clock, seen = FakeTime(), []
    original = openrouter.httpx
    hooks = {"request": [lambda request: seen.append("request")],
             "response": [lambda response: seen.append(response.status_code)]}
    with pytest.raises(RuntimeError, match="fixture exit"):
        with helper.paced_openrouter_clients(pacer(helper, clock)):
            with openrouter.httpx.Client(transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, json={})), event_hooks=hooks) as client:
                client.post(URL, content=BODY)
            raise RuntimeError("fixture exit")
    assert seen == ["request", 200]
    assert len(hooks["request"]) == len(hooks["response"]) == 1
    assert openrouter.httpx is original


def test_nested_installation_fails_without_removing_outer_pacing():
    helper = load_helper()
    clock, sent = FakeTime(), []
    with helper.paced_openrouter_clients(pacer(helper, clock)):
        with pytest.raises(helper.PacingError, match="already_installed"):
            with helper.paced_openrouter_clients(pacer(helper, clock)):
                pytest.fail("Nested installation was accepted")
        with openrouter.httpx.Client(transport=httpx.MockTransport(
                lambda request: (sent.append(clock.now) or httpx.Response(200, json={})))) as client:
            client.post(URL, content=BODY)
            client.post(URL, content=BODY)
    assert sent == [15, 30]


def test_nonadvancing_clock_cannot_dispatch_a_second_post():
    helper = load_helper()
    sent = []
    clock = FakeTime()
    limiter = helper.InferencePacer(clock=clock.monotonic, wall_clock=clock.wall_time, sleep=lambda _: None)
    clock.now = 15
    with helper.paced_openrouter_clients(limiter):
        with openrouter.httpx.Client(transport=httpx.MockTransport(
                lambda request: (sent.append(request.content) or httpx.Response(200, json={})))) as client:
            client.post(URL, content=BODY)
            with pytest.raises(helper.PacingError, match="clock_did_not_advance"):
                client.post(URL, content=BODY)
    assert sent == [BODY]


def test_separately_imported_helper_cannot_stack_client_factories():
    helper, second = load_helper(), load_helper()
    clock = FakeTime()
    original = openrouter.httpx
    with helper.paced_openrouter_clients(pacer(helper, clock)):
        with pytest.raises(second.PacingError, match="already_installed"):
            with second.paced_openrouter_clients(pacer(second, clock)):
                pytest.fail("A second helper copy replaced the active factory")
    assert openrouter.httpx is original


def test_unrepresentable_numeric_retry_after_fails_closed():
    helper = load_helper()
    clock, sent = FakeTime(), []
    with helper.paced_openrouter_clients(pacer(helper, clock)):
        with openrouter.httpx.Client(transport=httpx.MockTransport(
                lambda request: (sent.append(request.content) or httpx.Response(
                    429, headers={"Retry-After": "9" * 400}, content=b'{}')))) as client:
            with pytest.raises(helper.PacingError, match="unrepresentable_retry_after"):
                client.post(URL, content=BODY)
    assert sent == [BODY]


@pytest.mark.parametrize("purpose", ["readback", "decision"])
def test_original_provider_retry_numbers_and_wire_bytes_survive_pacing(monkeypatch, purpose):
    helper = load_helper()
    from beyond_label.generate import generate_world, make_case
    from beyond_label.provider import PinnedProvider, ProviderSettings, ProviderFailure
    from beyond_label.render import readback_request, decision_request

    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-pacing-credential")
    clock, sent, events = FakeTime(), [], []
    settings = ProviderSettings(
        model="deepseek/deepseek-v4.1-flash-1017", provider="PrimeIntellect",
        provider_route="primeintellect", provider_identity_source="openrouter_metadata",
        require_parameters=True,
        reasoning={"effort": "none"}, max_output_tokens=512,
        max_price={"prompt": .04368, "completion": .70, "request": 0, "image": 0},
        accepted_endpoint_models=("deepseek/deepseek-v4.1-flash-20261017",),
    )

    def handler(request):
        sent.append((clock.now, request.content))
        return httpx.Response(429, json={"error": {"code": 429}})

    adapter = openrouter.OpenRouterPaidTransport(settings.model, settings.provider_route,
                                                  transport=httpx.MockTransport(handler))
    provider = PinnedProvider(settings, adapter, sleep=clock.sleep)
    request = (readback_request if purpose == "readback" else decision_request)(make_case(generate_world(1100)))
    with helper.paced_openrouter_clients(pacer(helper, clock)):
        with pytest.raises(ProviderFailure, match="infrastructure_exhausted:http_error"):
            provider.request(request, start_attempt=3, log_attempt=events.append)
    assert [t for t, _ in sent] == [15, 75]
    assert sent[0][1] == sent[1][1]
    wire = json.loads(sent[0][1])
    assert wire["model"] == settings.model and wire["max_tokens"] == 512
    assert wire["reasoning"] == {"effort": "none"}
    assert wire["provider"]["only"] == ["primeintellect"]
    assert wire["provider"]["allow_fallbacks"] is False
    if purpose == "readback":
        assert not {"tools", "tool_choice", "parallel_tool_calls"} & wire.keys()
    else:
        assert wire["tools"] and wire["tool_choice"] == "auto"
        assert wire["parallel_tool_calls"] is False
    assert [e["attempt"] for e in events if e["event"] == "attempt_started"] == [3, 4]
    assert [e["retryable"] for e in events if e["event"] == "attempt_failed"] == [True, False]
    # The same frozen adapter with the helper inactive sends identical bytes.
    with pytest.raises(httpx.HTTPStatusError):
        adapter(wire)
    assert sent[-1][1] == sent[0][1]
