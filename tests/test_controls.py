"""Offline attempt-level accounting through real harness retry code and fake transports."""
from decimal import Decimal
import json

import pytest

from beyond_label.budget import BudgetError, BudgetLedger
from beyond_label.controls import AttemptBound, ControlError, GuardedTransport
from beyond_label.provider import PinnedProvider, ProviderFailure, ProviderSettings, parse_response
from beyond_label.rate_limit import RateLimiter
from beyond_label.schemas import Request


class Clock:
    def __init__(self): self.time = 0.0
    def now(self): return self.time
    def sleep(self, delay): self.time += delay


def setup(tmp_path, transport, cap="1", maximum="0.2", rpm=100):
    ledger = BudgetLedger(tmp_path / "budget.jsonl", cap)
    clock = Clock()
    limiter = RateLimiter(rpm, 10000, clock=clock.now, sleep=clock.sleep, cold_start=False)
    guarded = GuardedTransport(transport, ledger, limiter, lambda payload: AttemptBound(maximum, 100))
    return guarded, ledger, clock


def response(cost=0.05):
    return {"model": "fixture", "provider": "fixture", "id": "fixture-response",
            "choices": [{"message": {"role": "assistant", "content": "fixture"}, "finish_reason": "stop"}],
            "usage": {} if cost is None else {"cost": cost}}


def test_reservation_exists_before_dispatch_and_actual_cost_releases_balance(tmp_path):
    def transport(payload):
        snapshot = ledger.snapshot()
        assert snapshot["held"] == "0.2"
        assert len(snapshot["attempts"]) == 1
        return response()
    guarded, ledger, _ = setup(tmp_path, transport)
    raw = guarded({"messages": []})
    snapshot = ledger.snapshot()
    assert raw == response()
    assert snapshot["settled_cost"] == "0.05" and snapshot["available"] == "0.95"
    assert all(len(attempt["request_hash"]) == 64 for attempt in snapshot["attempts"].values())


def test_all_four_infrastructure_attempts_reserve_and_rate_limit(tmp_path):
    calls = []
    def transport(payload):
        calls.append(payload)
        if len(calls) < 4: raise TimeoutError("synthetic timeout")
        return response()
    guarded, ledger, clock = setup(tmp_path, transport, rpm=1)
    result = PinnedProvider(ProviderSettings(model="fixture", provider="fixture"), guarded).request(Request(messages=[]))
    snapshot = ledger.snapshot()
    assert result.reply.content == "fixture" and len(calls) == 4
    assert all(payload == calls[0] for payload in calls)
    assert snapshot["held"] == "0.6" and snapshot["settled_cost"] == "0.05"
    assert snapshot["available"] == "0.35" and len(snapshot["attempts"]) == 4
    assert clock.time >= 180


def test_exhausted_budget_stops_retry_before_another_transport(tmp_path):
    calls = []
    def transport(payload):
        calls.append(payload)
        raise TimeoutError("synthetic timeout")
    guarded, ledger, _ = setup(tmp_path, transport, cap="0.4")
    with pytest.raises(ProviderFailure, match="budget_control_blocked"):
        PinnedProvider(ProviderSettings(model="fixture", provider="fixture"), guarded).request(Request(messages=[]))
    assert len(calls) == 2 and ledger.snapshot()["held"] == "0.4"


def test_overrun_keeps_successful_decision_and_blocks_next_dispatch(tmp_path):
    calls = []
    def transport(payload): calls.append(payload); return response(0.3)
    guarded, ledger, _ = setup(tmp_path, transport)
    provider = PinnedProvider(ProviderSettings(model="fixture", provider="fixture"), guarded)
    result = provider.request(Request(messages=[]))
    assert result.reply.content == "fixture"
    assert ledger.snapshot()["blocked"] is True
    with pytest.raises(ProviderFailure): provider.request(Request(messages=[]))
    assert len(calls) == 1 and ledger.snapshot()["settled_cost"] == "0.3"


@pytest.mark.parametrize("cost", [None, True, "0.05", -1, float("nan"), float("inf")])
def test_missing_or_invalid_cost_is_never_invented_as_zero(tmp_path, cost):
    guarded, ledger, _ = setup(tmp_path, lambda payload: response(cost))
    guarded({"messages": []})
    assert ledger.snapshot()["held"] == "0.2"
    assert ledger.snapshot()["settled_cost"] == "0"
    assert ledger.snapshot()["uncertain"]


def test_reentrant_dispatch_fails_before_second_reservation(tmp_path):
    def transport(payload):
        with pytest.raises(ControlError, match="concurrent"):
            guarded(payload)
        return response()
    guarded, ledger, _ = setup(tmp_path, transport)
    guarded({"messages": []})
    assert len(ledger.snapshot()["attempts"]) == 1


def test_unknown_charge_is_durable_after_interruption(tmp_path):
    def transport(payload): raise KeyboardInterrupt
    guarded, ledger, _ = setup(tmp_path, transport)
    with pytest.raises(KeyboardInterrupt): guarded({"messages": []})
    recovered = BudgetLedger(tmp_path / "budget.jsonl", "1")
    assert recovered.snapshot()["held"] == "0.2"


def test_quote_or_secret_failure_makes_no_dispatch_or_reservation(tmp_path, monkeypatch):
    calls = []
    guarded, ledger, _ = setup(tmp_path, lambda payload: calls.append(payload))
    secret = "synthetic-control-secret"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)
    with pytest.raises(ControlError): guarded({"messages": [{"content": secret}]})
    def bad_quote(payload): raise RuntimeError(secret)
    guarded.quote = bad_quote
    with pytest.raises(ControlError) as error: guarded({"messages": []})
    assert secret not in str(error.value)
    assert calls == [] and not ledger.snapshot()["attempts"]
    assert secret not in ledger.path.read_text("utf-8")


def test_successful_invalid_model_action_is_not_resampled_by_controls(tmp_path):
    calls = []
    def transport(payload):
        calls.append(payload)
        raw = response()
        raw["choices"][0]["message"]["tool_calls"] = [{"function": {"name": "invalid", "arguments": "{}"}}]
        return raw
    guarded, ledger, _ = setup(tmp_path, transport)
    result = PinnedProvider(ProviderSettings(model="fixture", provider="fixture"), guarded).request(Request(messages=[]))
    assert result.reply.tool_calls[0].name == "invalid"
    assert len(calls) == len(ledger.snapshot()["attempts"]) == 1


@pytest.mark.parametrize("error_type", [BudgetError, OSError])
def test_settlement_failure_keeps_observed_response_and_blocks_dispatch(tmp_path, monkeypatch, error_type):
    calls, events = [], []
    def transport(payload):
        calls.append(payload)
        return response()
    guarded, ledger, _ = setup(tmp_path, transport)
    def fail_settlement(*args, **kwargs):
        raise error_type("synthetic-private-accounting-failure")
    monkeypatch.setattr(ledger, "settle", fail_settlement)
    settings = ProviderSettings(model="fixture", provider="fixture")
    provider = PinnedProvider(settings, guarded)
    result = provider.request(Request(messages=[]), log_attempt=events.append)
    assert result.reply.content == "fixture"
    assert result.raw_response == response()
    assert events[-1]["event"] == "attempt_succeeded"
    assert events[-1]["accounting_error"] == "budget_settlement_failed"
    assert "accounting_error" not in result.raw_response
    assert "synthetic-private-accounting-failure" not in json.dumps(events)
    assert parse_response(result.raw_response, result.payload, settings, result.latency_seconds) == result
    assert ledger.snapshot()["held"] == "0.2"
    assert ledger.snapshot()["pending_attempts"] == 1
    with pytest.raises(ProviderFailure, match="budget_control_blocked"):
        provider.request(Request(messages=[]), log_attempt=events.append)
    assert len(calls) == 1
    assert BudgetLedger(ledger.path, "1").snapshot()["held"] == "0.2"


def test_slow_budget_persistence_cannot_expire_rate_reservation_before_dispatch(tmp_path, monkeypatch):
    dispatch_times = []
    def transport(payload):
        dispatch_times.append(clock.time)
        return response()
    guarded, ledger, clock = setup(tmp_path, transport, rpm=1)
    reserve = ledger.reserve
    def delayed_first_reservation(*args, **kwargs):
        reserve(*args, **kwargs)
        if not dispatch_times:
            clock.time += 90
    monkeypatch.setattr(ledger, "reserve", delayed_first_reservation)
    guarded({"messages": []})
    guarded({"messages": []})
    assert dispatch_times == [90, 150]


def test_cancellation_while_waiting_keeps_undispatched_conservative_hold(tmp_path, monkeypatch):
    calls = []
    guarded, ledger, _ = setup(tmp_path, lambda payload: calls.append(payload))
    def cancelled_acquire(token_bound):
        raise KeyboardInterrupt
    monkeypatch.setattr(guarded.limiter, "acquire", cancelled_acquire)
    with pytest.raises(KeyboardInterrupt):
        guarded({"messages": []})
    assert calls == []
    snapshot = ledger.snapshot()
    assert snapshot["held"] == "0.2" and snapshot["settled_cost"] == "0"
    assert snapshot["pending_attempts"] == 1


def test_post_write_fsync_failure_keeps_response_without_claiming_rollback(tmp_path, monkeypatch):
    events, calls = [], []
    def fail_fsync(handle):
        raise OSError("synthetic-private-fsync-failure")
    def transport(payload):
        calls.append(payload)
        monkeypatch.setattr("beyond_label.budget.os.fsync", fail_fsync)
        return response()
    guarded, ledger, _ = setup(tmp_path, transport)
    provider = PinnedProvider(ProviderSettings(model="fixture", provider="fixture"), guarded)
    result = provider.request(Request(messages=[]), log_attempt=events.append)
    assert result.reply.content == "fixture"
    assert events[-1]["accounting_error"] == "budget_settlement_failed"
    assert "synthetic-private-fsync-failure" not in json.dumps(events)
    # The write reached the file before fsync failed; replay keeps that evidence.
    assert ledger.snapshot()["settled_cost"] == "0.05"
    with pytest.raises(ProviderFailure, match="budget_control_blocked"):
        provider.request(Request(messages=[]))
    assert len(calls) == 1


@pytest.mark.parametrize("raw,reason", [(None, "budget_control_blocked"),
                                       ({"model": "wrong", "id": "fixture-malformed"}, "model_mismatch")])
def test_accounting_error_is_separate_evidence_for_unsuccessful_response(tmp_path, monkeypatch, raw, reason):
    calls, events = [], []
    def transport(payload):
        calls.append(payload)
        return raw
    guarded, ledger, _ = setup(tmp_path, transport)
    def fail_settlement(*args, **kwargs):
        raise OSError("synthetic-private-settlement-error")
    monkeypatch.setattr(ledger, "settle", fail_settlement)
    provider = PinnedProvider(ProviderSettings(model="fixture", provider="fixture"), guarded)
    with pytest.raises(ProviderFailure, match=reason):
        provider.request(Request(messages=[]), log_attempt=events.append)
    assert len(calls) == 1
    assert events[-1]["accounting_error"] == "budget_settlement_failed"
    assert events[-1]["retryable"] is False
    assert "synthetic-private-settlement-error" not in json.dumps(events)
    if raw is not None:
        assert events[-1]["raw_response"] == raw


def test_guarded_accounting_failure_is_replayable_by_run_harness(tmp_path, monkeypatch):
    from beyond_label.run import ScriptedPublicPolicy, build_manifest, rebuild_outputs, run_manifest
    policy = ScriptedPublicPolicy()
    guarded, ledger, _ = setup(tmp_path, policy)
    def fail_settlement(*args, **kwargs):
        raise BudgetError("budget_ledger_locked")
    monkeypatch.setattr(ledger, "settle", fail_settlement)
    provider = PinnedProvider(ProviderSettings(model=policy.model, provider=policy.provider), guarded)
    output = tmp_path / "synthetic-run"
    summary = run_manifest(build_manifest("smoke"), output, provider, max_cells=1)
    raw_journal = (output / "calls.jsonl").read_bytes()
    assert b'"accounting_error":"budget_settlement_failed"' in raw_journal
    assert rebuild_outputs(output) == summary
    assert (output / "calls.jsonl").read_bytes() == raw_journal
