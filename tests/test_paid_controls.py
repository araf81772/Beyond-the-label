"""Synthetic paid authorization accounting; no credentials or provider calls."""
from copy import deepcopy
from decimal import Decimal, localcontext
import hashlib
import json

import pytest

from beyond_label.attempts import (
    AttemptLimit, AttemptLimitError, CappedPaidAttempts, ExecutionSuspended,
    PAID_AUTHORIZATION_ID, PAID_MAX_ATTEMPTS, PaidAttemptLimit,
)
from beyond_label.budget import BudgetLedger
from beyond_label.controls import ControlError, GuardedTransport
from beyond_label.paid_controls import PAID_MAXIMUM_COST, PAID_TOKEN_BOUND, PaidSmokeQuote, paid_observed_cost
from beyond_label.provider import PinnedProvider, ProviderSettings, TransportOutcome
from beyond_label.rate_limit import RateLimiter
from beyond_label.schemas import Request


def payload():
    return {"model": "openai/gpt-4.1-mini", "provider": {
        "only": ["openai"], "allow_fallbacks": False, "require_parameters": True,
        "max_price": {"prompt": 0.4, "completion": 1.6, "request": 0, "image": 0}},
        "max_tokens": 512, "temperature": 0,
        "messages": [{"role": "user", "content": "Synthetic fixture"}]}


def test_paid_journal_requires_explicit_initialization_and_preserves_200_slots(tmp_path):
    path = tmp_path / "attempts.jsonl"
    with pytest.raises(AttemptLimitError, match="missing_paid_attempt_history"):
        PaidAttemptLimit(path)
    assert not path.exists()
    counter = PaidAttemptLimit(path, initialize=True)
    assert PAID_MAX_ATTEMPTS == 200
    assert json.loads(path.read_text().splitlines()[0])["authorization_id"] == PAID_AUTHORIZATION_ID
    for _ in range(200):
        counter.claim()
    before = path.read_bytes()
    reopened = PaidAttemptLimit(path)
    with pytest.raises(AttemptLimitError, match="authorized_attempt_limit_exhausted"):
        reopened.claim()
    assert reopened.snapshot() == {"maximum_attempts": 200, "reserved_attempts": 200,
                                   "remaining_attempts": 0}
    assert path.read_bytes() == before


def test_paid_and_free_authorizations_cannot_share_or_upgrade_a_journal(tmp_path):
    free, paid = tmp_path / "free.jsonl", tmp_path / "paid.jsonl"
    AttemptLimit(free).claim()
    PaidAttemptLimit(paid, initialize=True).claim()
    for constructor, path in [(PaidAttemptLimit, free), (AttemptLimit, paid)]:
        before = path.read_bytes()
        with pytest.raises(AttemptLimitError):
            constructor(path)
        assert path.read_bytes() == before
    assert AttemptLimit(free).snapshot()["maximum_attempts"] == 10


@pytest.mark.parametrize("mutation", ["authorization", "cap", "empty", "torn", "ordinal", "duplicate"])
def test_paid_damaged_or_rehashed_history_fails_closed(tmp_path, mutation):
    path = tmp_path / "attempts.jsonl"
    counter = PaidAttemptLimit(path, initialize=True)
    counter.claim()
    raw = path.read_bytes()
    if mutation == "empty":
        path.write_bytes(b"")
    elif mutation == "torn":
        path.write_bytes(raw[:-1])
    elif mutation == "duplicate":
        path.write_bytes(b'{"version":1,' + raw[1:])
    else:
        events = [json.loads(line) for line in raw.splitlines()]
        if mutation == "authorization":
            events[0]["authorization_id"] = "another-authorization"
        elif mutation == "cap":
            events[0]["maximum_attempts"] = 201
        else:
            events[1]["ordinal"] = True
        previous, lines = "0" * 64, []
        for event in events:
            event.pop("event_hash")
            event["previous_hash"] = previous
            canonical = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
            event["event_hash"] = previous = hashlib.sha256(canonical(event)).hexdigest()
            lines.append(canonical(event) + b"\n")
        path.write_bytes(b"".join(lines))
    broken = path.read_bytes()
    with pytest.raises(AttemptLimitError):
        PaidAttemptLimit(path, initialize=True)
    assert path.read_bytes() == broken


def test_fixed_quote_reserves_entire_context_without_prompt_estimation():
    quote = PaidSmokeQuote()
    bound = quote(payload())
    base = Decimal(1047576) * Decimal("0.0000004") + Decimal(512) * Decimal("0.0000016")
    assert Decimal(bound.maximum_cost) == base * Decimal("1.05")
    assert bound.maximum_cost == PAID_MAXIMUM_COST == "0.44084208"
    assert bound.token_bound == PAID_TOKEN_BOUND == 1048088
    large = payload()
    large["messages"][0]["content"] = "\U0001f680" * 100000
    assert quote(large) == bound


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(model="other/model"),
    lambda p: p.update(max_tokens=513),
    lambda p: p.update(max_tokens=True),
    lambda p: p.update(reasoning={"effort": "high"}),
    lambda p: p.update(plugins=[{"id": "web"}]),
    lambda p: p["provider"].update(allow_fallbacks=True),
    lambda p: p["provider"]["max_price"].update(prompt=0.41),
    lambda p: p["provider"]["max_price"].update(request=False),
    lambda p: p["messages"][0].update(content=[{"type": "image_url", "image_url": {"url": "fixture"}}]),
])
def test_quote_rejects_cost_or_routing_changes(mutate):
    request = payload()
    mutate(request)
    with pytest.raises(ControlError):
        PaidSmokeQuote()(request)


def policy(tmp_path):
    counter = PaidAttemptLimit(tmp_path / "attempts.jsonl", initialize=True)
    ledger = BudgetLedger(tmp_path / "budget.jsonl", "1")
    return CappedPaidAttempts(counter, ledger), counter, ledger


def test_pre_attempt_budget_gate_does_not_consume_slots_for_unknown_or_pending_cost(tmp_path):
    callback, counter, ledger = policy(tmp_path)
    attempt = "attempt-" + "a" * 32
    ledger.reserve(attempt, PAID_MAXIMUM_COST)
    for settle in (False, True):
        if settle:
            ledger.settle(attempt, None, currency="USD")
        with pytest.raises(ExecutionSuspended, match="paid_cost_reconciliation_required"):
            callback()
        assert counter.snapshot()["reserved_attempts"] == 0
    ledger.settle(attempt, "0.001", currency="USD")
    callback()
    assert counter.snapshot()["reserved_attempts"] == 1


def test_stricter_smoke_cap_and_known_exhaustion_suspend_before_new_attempt(tmp_path):
    callback, counter, ledger = policy(tmp_path)
    attempt = "attempt-" + "b" * 32
    ledger.reserve(attempt, "0.7")
    ledger.settle(attempt, "0.7", currency="USD")
    with pytest.raises(ExecutionSuspended, match="paid_smoke_budget_exhausted"):
        callback()
    assert counter.snapshot()["reserved_attempts"] == 0
    other = BudgetLedger(tmp_path / "other.jsonl", "10")
    with pytest.raises(AttemptLimitError, match="invalid_paid_attempt_policy"):
        CappedPaidAttempts(counter, other)


def test_known_successes_release_large_hold_but_share_aggregate_attempt_cap(tmp_path):
    callback, counter, ledger = policy(tmp_path)
    clock = [0.0]
    def sleep(value): clock[0] += value
    limiter = RateLimiter(200, PAID_TOKEN_BOUND * 200, clock=lambda: clock[0], sleep=sleep, cold_start=False)
    calls = []
    def synthetic_transport(request):
        calls.append(deepcopy(request))
        assert ledger.snapshot()["held"] == PAID_MAXIMUM_COST
        return {"usage": {"cost": 0.001, "is_byok": False}}
    guarded = GuardedTransport(synthetic_transport, ledger, limiter, PaidSmokeQuote(), cost_reader=paid_observed_cost)
    for _ in range(144):
        callback()
        guarded(payload())
    assert len(calls) == counter.snapshot()["reserved_attempts"] == 144
    assert ledger.snapshot()["settled_cost"] == "0.144"
    assert ledger.snapshot()["held"] == "0"


def test_unknown_transport_charge_blocks_infrastructure_retry_before_dispatch(tmp_path):
    callback, counter, ledger = policy(tmp_path)
    calls, events = [], []
    def timeout(request):
        calls.append(request)
        raise TimeoutError("synthetic private error")
    limiter = RateLimiter(200, PAID_TOKEN_BOUND * 200, cold_start=False)
    guarded = GuardedTransport(timeout, ledger, limiter, PaidSmokeQuote(), cost_reader=paid_observed_cost)
    settings = ProviderSettings(model="openai/gpt-4.1-mini", provider="OpenAI", provider_route="openai",
                                require_parameters=True, reasoning=None,
                                max_price={"prompt": 0.4, "completion": 1.6, "request": 0, "image": 0})
    provider = PinnedProvider(settings, guarded, before_attempt=callback)
    with pytest.raises(ExecutionSuspended, match="paid_cost_reconciliation_required"):
        provider.request(Request(messages=[]), log_attempt=events.append)
    assert len(calls) == counter.snapshot()["reserved_attempts"] == 1
    assert ledger.snapshot()["unknown_cost_attempts"] == 1
    assert [event["event"] for event in events] == ["attempt_started", "attempt_failed"]


@pytest.mark.parametrize("cost", [None, 0.5])
def test_delivered_response_is_preserved_when_unknown_or_overrun_charge_blocks_next_call(tmp_path, cost):
    callback, counter, ledger = policy(tmp_path)
    raw = {"choices": [{"message": {"content": "Synthetic response"}}],
           "usage": {} if cost is None else {"cost": cost, "is_byok": False}}
    calls = []
    def transport(request):
        calls.append(request)
        return raw
    guarded = GuardedTransport(transport, ledger,
                               RateLimiter(200, PAID_TOKEN_BOUND * 200, cold_start=False), PaidSmokeQuote(),
                               cost_reader=paid_observed_cost)
    callback()
    assert guarded(payload()) is raw
    with pytest.raises(ExecutionSuspended, match="paid_cost_reconciliation_required"):
        callback()
    assert len(calls) == counter.snapshot()["reserved_attempts"] == 1
    assert ledger.snapshot()["uncertain"] if cost is None else ledger.snapshot()["reservation_exceeded"]


@pytest.mark.parametrize("usage,expected", [
    ({"cost": .1, "is_byok": False}, "0.1"),
    ({"cost": 0, "is_byok": False}, "0"),
    ({"cost": .005, "is_byok": True, "cost_details": {"upstream_inference_cost": .1}}, "0.105"),
    ({"cost": 0, "is_byok": True, "cost_details": {"upstream_inference_cost": .1}}, "0.1"),
    ({"cost": .1}, None), ({"cost": .1, "is_byok": 0}, None),
    ({"cost": .1, "is_byok": "false"}, None),
    ({"cost": .1, "is_byok": True}, None),
    ({"cost": .1, "is_byok": True, "cost_details": {"upstream_inference_cost": True}}, None),
    ({"cost": .1, "is_byok": True, "cost_details": {"upstream_inference_cost": "0.1"}}, None),
    ({"cost": .1, "is_byok": True, "cost_details": {"upstream_inference_cost": -1}}, None),
    ({"cost": .1, "is_byok": True, "cost_details": {"upstream_inference_cost": float("inf")}}, None),
    ({"cost": float("nan"), "is_byok": False}, None),
    ({"cost": True, "is_byok": False}, None),
])
def test_paid_cost_requires_explicit_billing_identity_and_complete_numeric_evidence(usage, expected):
    assert paid_observed_cost({"usage": usage}) == expected


def test_byok_cost_addition_preserves_small_upstream_charge_under_low_decimal_precision():
    raw = {"usage": {"is_byok": True, "cost": 123456789,
                     "cost_details": {"upstream_inference_cost": .00000001}}}
    before = deepcopy(raw)
    with localcontext() as context:
        context.prec = 2
        assert paid_observed_cost(raw) == "123456789.00000001"
    assert raw == before


@pytest.mark.parametrize("usage,expected,unknown", [
    ({"cost": .005, "is_byok": True, "cost_details": {"upstream_inference_cost": .1}}, "0.105", False),
    ({"cost": .005}, "0", True),
    ({"cost": .005, "is_byok": True}, "0", True),
])
def test_paid_guard_settles_both_billing_sources_or_preserves_entire_hold(tmp_path, usage, expected, unknown):
    callback, counter, ledger = policy(tmp_path)
    raw = {"usage": usage}
    before = deepcopy(raw)
    guarded = GuardedTransport(lambda request: raw, ledger,
                               RateLimiter(200, PAID_TOKEN_BOUND * 200, cold_start=False), PaidSmokeQuote(),
                               cost_reader=paid_observed_cost)
    callback()
    assert guarded(payload()) is raw
    assert raw == before
    state = ledger.snapshot()
    assert state["settled_cost"] == expected and state["uncertain"] is unknown
    assert state["held"] == (PAID_MAXIMUM_COST if unknown else "0")
    if unknown:
        with pytest.raises(ExecutionSuspended):
            callback()
        assert counter.snapshot()["reserved_attempts"] == 1


def test_cost_reader_failure_preserves_received_response_and_blocks_further_dispatch(tmp_path):
    callback, _, ledger = policy(tmp_path)
    raw = {"usage": {"is_byok": False, "cost": .001}}
    calls = []
    def transport(request):
        calls.append(request)
        return raw
    def failed_reader(response):
        raise RuntimeError("synthetic-private-cost-reader-failure")
    guarded = GuardedTransport(transport, ledger,
                               RateLimiter(200, PAID_TOKEN_BOUND * 200, cold_start=False), PaidSmokeQuote(),
                               cost_reader=failed_reader)
    callback()
    delivered = guarded(payload())
    assert isinstance(delivered, TransportOutcome) and delivered.raw_response is raw
    assert delivered.accounting_error == "budget_settlement_failed"
    assert ledger.snapshot()["held"] == PAID_MAXIMUM_COST
    with pytest.raises(ControlError, match="budget_control_blocked"):
        guarded(payload())
    assert len(calls) == 1
    assert "synthetic-private" not in ledger.path.read_text()


def _serialized_paid_request(phase):
    from beyond_label.generate import generate_world, make_case
    from beyond_label.provider import serialize_request
    from beyond_label.render import decision_request, readback_request
    from beyond_label.run import _assistant
    from beyond_label.sandbox import Sandbox
    from beyond_label.schemas import ModelReply, ToolCall

    settings = ProviderSettings(
        model="openai/gpt-4.1-mini", provider="OpenAI", provider_route="openai",
        provider_identity_source="openrouter_metadata", require_parameters=True,
        reasoning=None, max_price={"prompt": .4, "completion": 1.6, "request": 0, "image": 0},
    )
    case = make_case(generate_world(1100))
    request = readback_request(case) if phase == "readback" else decision_request(case)
    if phase == "continuation":
        reply = ModelReply(tool_calls=[ToolCall(id="synthetic-inspect", name="inspect",
            arguments={"lot_id": case.public.target_ids[0]})])
        revealed = Sandbox(case).apply_reply(reply)
        request = request.model_copy(update={"messages": [*deepcopy(request.messages), _assistant(reply),
            {"role": "tool", "tool_call_id": "synthetic-inspect", "content": json.dumps(revealed)}]})
    return serialize_request(request, settings)


def test_serialized_readback_reaches_paid_mock_http_through_unchanged_budget_guard(tmp_path, monkeypatch):
    import httpx
    from beyond_label.openrouter import OpenRouterPaidTransport

    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-guarded-readback-key")
    original = _serialized_paid_request("readback")
    expected = deepcopy(original)
    assert not {"tools", "tool_choice", "parallel_tool_calls"} & original.keys()
    callback, counter, ledger = policy(tmp_path)
    sent = []

    def handler(request):
        sent.append(json.loads(request.content))
        assert ledger.snapshot()["held"] == PAID_MAXIMUM_COST
        return httpx.Response(200, json={"usage": {"is_byok": False, "cost": .001}})

    adapter = OpenRouterPaidTransport("openai/gpt-4.1-mini", "openai", transport=httpx.MockTransport(handler))
    guarded = GuardedTransport(adapter, ledger, RateLimiter(200, PAID_TOKEN_BOUND * 200, cold_start=False),
                               PaidSmokeQuote(), cost_reader=paid_observed_cost)
    callback()
    result = guarded(original)
    assert result == {"usage": {"is_byok": False, "cost": .001}}
    assert original == expected and sent == [expected]
    assert counter.snapshot()["reserved_attempts"] == 1
    state = ledger.snapshot()
    assert state["settled_cost"] == "0.001" and state["held"] == "0"
    assert state["uncertain"] is False


@pytest.mark.parametrize("phase", ["first", "continuation"])
def test_quote_retains_same_bound_for_tool_decisions_and_continuations(phase):
    request = _serialized_paid_request(phase)
    assert request["parallel_tool_calls"] is False and request["tool_choice"] == "auto"
    assert request["tools"]
    bound = PaidSmokeQuote()(request)
    assert bound.maximum_cost == PAID_MAXIMUM_COST
    assert bound.token_bound == PAID_TOKEN_BOUND


@pytest.mark.parametrize("phase", ["first", "continuation"])
@pytest.mark.parametrize("control", ["absent", True, 0, None])
def test_quote_rejects_missing_or_relaxed_parallel_control_for_tools(phase, control):
    request = _serialized_paid_request(phase)
    if control == "absent":
        request.pop("parallel_tool_calls")
    else:
        request["parallel_tool_calls"] = control
    with pytest.raises(ControlError, match="unverified_paid_request_bound"):
        PaidSmokeQuote()(request)


@pytest.mark.parametrize("control", [False, True, 0, None])
def test_quote_rejects_inapplicable_parallel_control_for_readback(control):
    request = _serialized_paid_request("readback")
    request["parallel_tool_calls"] = control
    with pytest.raises(ControlError, match="unverified_paid_request_bound"):
        PaidSmokeQuote()(request)
