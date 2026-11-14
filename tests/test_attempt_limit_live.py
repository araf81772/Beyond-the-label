"""Shared live-owner allowance tests; every response is a temporary local fixture."""
import json
from pathlib import Path
import runpy
import warnings

import pytest
import yaml

from beyond_label.attempts import AttemptLimit, AttemptLimitError
from beyond_label.budget import BudgetLedger
from beyond_label import live, run
from test_free_run import free_fixture


def test_real_transport_without_durable_cap_is_rejected(tmp_path, monkeypatch):
    from beyond_label.controls import GuardedTransport, AttemptBound
    from beyond_label.openrouter import OpenRouterFreeTransport
    from beyond_label.rate_limit import RateLimiter
    monkeypatch.setattr(run, "ROOT", tmp_path)
    config, _, provider = free_fixture()
    ledger = BudgetLedger(tmp_path / "runs/_free_session/budget.jsonl", "0")
    provider.transport = GuardedTransport(
        OpenRouterFreeTransport(config["model"], config["provider_route"]), ledger,
        RateLimiter(10, 10000), lambda payload: AttemptBound("0", 100))
    with pytest.raises(ValueError, match="durable.*attempt"):
        run._validate_live_transport(provider)


def test_direct_real_run_rejects_changed_allowance_before_artifact_creation(tmp_path, monkeypatch):
    config, policy, provider = free_fixture()
    config["maximum_inference_attempts"] = 11
    monkeypatch.setattr(run, "_validate_live_transport", lambda _: None)
    with pytest.raises(ValueError, match="fixed ten-attempt"):
        run.run_manifest(run.build_manifest("smoke"), tmp_path / "absent", provider,
                         synthetic=False, execution_config=config)
    assert policy.calls == 0 and not (tmp_path / "absent").exists()


@pytest.mark.parametrize("change", [None, "callback", "other_counter", "counter_subclass",
                                    "different_day_guard", "no_day_guard", "other_money_ledger"])
def test_real_entry_point_requires_exact_shared_policy(tmp_path, monkeypatch, change):
    from beyond_label.controls import GuardedTransport, AttemptBound
    from beyond_label.openrouter import OpenRouterFreeTransport
    from beyond_label.rate_limit import RateLimiter
    monkeypatch.setattr(run, "ROOT", tmp_path)
    config, _, provider = free_fixture()
    session = tmp_path / "runs/_free_session"
    counter = AttemptLimit(session / "attempts.jsonl")
    quota = live.FreeQuota(50)
    policy = live.CappedFreeAttempts(counter, quota)
    provider.before_attempt = policy
    guard = GuardedTransport(OpenRouterFreeTransport(config["model"], config["provider_route"]),
        BudgetLedger(session / "budget.jsonl", "0"), RateLimiter(10, 10000),
        lambda payload: AttemptBound("0", 100), before_dispatch=quota.check_dispatch_day)
    provider.transport = guard
    if change == "callback":
        provider.before_attempt = lambda: None
    elif change == "other_counter":
        policy.counter = AttemptLimit(tmp_path / "fresh_counter.jsonl")
    elif change == "counter_subclass":
        class Unlimited(AttemptLimit):
            def claim(self):
                pass
        policy.counter = Unlimited(counter.path)
    elif change == "different_day_guard":
        guard.before_dispatch = live.FreeQuota(50).check_dispatch_day
    elif change == "no_day_guard":
        guard.before_dispatch = None
    elif change == "other_money_ledger":
        guard.ledger = BudgetLedger(tmp_path / "new_budget.jsonl", "0")
    if change is None:
        run._validate_live_transport(provider)  # Validation only; no HTTP.
        assert counter.snapshot()["reserved_attempts"] == 0
    else:
        with pytest.raises(ValueError, match="durable.*attempt"):
            run._validate_live_transport(provider)


@pytest.mark.parametrize("limit", [None, True, False, 0, 9, 11, "10", 10.0])
def test_live_rejects_missing_or_changed_cap_before_account_request(tmp_path, monkeypatch, limit):
    config = dict(free_only=True, live_execution_enabled=True,
                  account_preflight_enabled=True, paid_calls_authorized=False,
                  authorized_spend_cap=0, maximum_inference_attempts=limit)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.setattr(live, "free_account_preflight", lambda: pytest.fail("No account request allowed"))
    with pytest.raises(live.ExecutionSuspended, match="fixed_ten_attempt_limit_required"):
        live.run_free(path, "smoke", tmp_path / "runs/smoke")


def owner(tmp_path):
    runs_root = tmp_path / "runs"
    session = runs_root / "_free_session"
    ledger = BudgetLedger(session / "budget.jsonl", "0")
    return runs_root, session, ledger


def test_shared_limit_survives_new_stage_and_unused_crash_reservations(tmp_path):
    runs_root, session, ledger = owner(tmp_path)
    first = live.open_attempt_limit(session, runs_root, ledger)
    for _ in range(10):
        first.claim()  # Crash before journal creation: all ten still remain used.
    reopened = live.open_attempt_limit(session, runs_root, ledger)
    assert reopened.snapshot()["remaining_attempts"] == 0
    with pytest.raises(AttemptLimitError, match="exhausted"):
        reopened.claim()


@pytest.mark.parametrize("evidence", ["calls", "manifest", "budget"])
def test_absent_counter_cannot_reset_earlier_evidence(tmp_path, evidence):
    runs_root, session, ledger = owner(tmp_path)
    if evidence == "budget":
        ledger.reserve("attempt-" + "1" * 32, "0")
    else:
        prior = runs_root / "old_stage"
        prior.mkdir()
        (prior / ("calls.jsonl" if evidence == "calls" else "manifest.json")).write_text("", encoding="utf-8")
    with pytest.raises(AttemptLimitError, match="history_missing"):
        live.open_attempt_limit(session, runs_root, ledger)
    assert not (session / "attempts.jsonl").exists()


def recorded_fixture(tmp_path, monkeypatch):
    runs_root, session, ledger = owner(tmp_path)
    counter = live.open_attempt_limit(session, runs_root, ledger)
    config, policy, provider = free_fixture()
    provider.before_attempt = counter.claim
    # Explicit test-only reporting seam; no HTTP, no research observations.
    monkeypatch.setattr(run, "_validate_live_transport", lambda _: None)
    directory = runs_root / "smoke"
    run.run_manifest(run.build_manifest("smoke"), directory, provider,
                     execution_config=config, synthetic=False, max_cells=1)
    return runs_root, session, ledger, counter, directory, policy.calls


def test_valid_raw_attempt_history_is_reconciled_without_mutation(tmp_path, monkeypatch):
    root, session, ledger, counter, directory, calls = recorded_fixture(tmp_path, monkeypatch)
    before = {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}
    reopened = live.open_attempt_limit(session, root, ledger)
    assert reopened.snapshot()["reserved_attempts"] == calls
    assert {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()} == before


@pytest.mark.parametrize("change", ["counter_removed", "counter_rolled_back", "trace_torn",
                                    "manifest_removed", "manifest_hash", "synthetic_label"])
def test_damaged_or_missing_history_blocks_restart(tmp_path, monkeypatch, change):
    root, session, ledger, counter, directory, _ = recorded_fixture(tmp_path, monkeypatch)
    if change == "counter_removed":
        counter.path.unlink()
    elif change == "counter_rolled_back":
        counter.path.write_bytes(counter.path.read_bytes().splitlines(keepends=True)[0])
    elif change == "trace_torn":
        trace = directory / "calls.jsonl"
        trace.write_bytes(trace.read_bytes()[:-1])
    elif change == "manifest_removed":
        (directory / "manifest.json").unlink()
    else:
        path = directory / "manifest.json"
        stored = json.loads(path.read_text())
        if change == "manifest_hash":
            stored["run_config_hash"] = "0" * 64
        else:
            stored["run_config"]["evidence_kind"] = "synthetic"
            stored["run_config_hash"] = run._hash({"plan": stored["plan"], "config": stored["run_config"]})
        path.write_text(json.dumps(stored), encoding="utf-8")
    with pytest.raises(AttemptLimitError):
        live.open_attempt_limit(session, root, ledger)


def test_money_reservation_without_trace_start_blocks(tmp_path):
    root, session, ledger = owner(tmp_path)
    counter = live.open_attempt_limit(session, root, ledger)
    counter.claim()
    ledger.reserve("attempt-" + "1" * 32, "0")
    with pytest.raises(AttemptLimitError, match="history_inconsistent"):
        live.open_attempt_limit(session, root, ledger)


def test_live_owner_applies_same_counter_before_every_attempt(tmp_path, monkeypatch):
    config = yaml.safe_load((run.ROOT / "configs/free.yaml").read_text())
    config.update(live_execution_enabled=True, account_preflight_enabled=True)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.setattr(live, "ROOT", tmp_path)
    monkeypatch.setattr(live, "free_account_preflight", lambda: {
        "zero_hard_limit": True, "free_model_daily_requests": {"used": 0, "limit": 50, "remaining": 50}})
    observed = []
    def stopped_before_transport(plan, output, provider, **kwargs):
        for _ in range(10):
            provider.before_attempt()
        observed.append(kwargs["execution_config"]["maximum_inference_attempts"])
        with pytest.raises(AttemptLimitError, match="exhausted"):
            provider.before_attempt()
        return {"test_only": True}
    monkeypatch.setattr(live, "run_manifest", stopped_before_transport)
    live.run_free(path, "smoke", tmp_path / "runs/smoke")
    def restart(plan, output, provider, **kwargs):
        with pytest.raises(AttemptLimitError, match="exhausted"):
            provider.before_attempt()
        return {"test_only": True}
    monkeypatch.setattr(live, "run_manifest", restart)
    live.run_free(path, "pilot", tmp_path / "runs/pilot")
    assert observed == [10]


def test_python_m_cli_uses_the_same_verified_policy_types(tmp_path, monkeypatch):
    from beyond_label import openrouter
    config = yaml.safe_load((run.ROOT / "configs/free.yaml").read_text())
    config.update(live_execution_enabled=True, account_preflight_enabled=True)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.setattr(run, "ROOT", tmp_path)
    monkeypatch.setattr(openrouter, "free_account_preflight", lambda: {
        "zero_hard_limit": True, "free_model_daily_requests": {"used": 0, "limit": 50, "remaining": 50}})
    validated = []
    def validate_only(plan, output, provider, **kwargs):
        run._validate_live_transport(provider)
        validated.append(True)
        return {"test_only": True, "inference_calls": 0}
    monkeypatch.setattr(run, "run_manifest", validate_only)
    monkeypatch.setattr("sys.argv", ["live", "--config", str(path), "--dataset", "smoke",
                                  "--output", str(tmp_path / "runs/smoke")])
    # runpy warns about the deliberately pre-imported module used by this test;
    # the exact same __main__ class-identity boundary occurs with python -m.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=RuntimeWarning, module="runpy")
        with pytest.raises(SystemExit) as exit_status:
            runpy.run_module("beyond_label.live", run_name="__main__")
    assert exit_status.value.code == 0
    assert validated == [True]
