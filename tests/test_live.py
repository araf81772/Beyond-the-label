"""Local free-run orchestration fixtures. No real account or model calls."""
from pathlib import Path
import json
import pytest

from beyond_label.live import ExecutionSuspended, FreeQuota, account_configuration, reconcile_ledger
from beyond_label.budget import BudgetLedger
from beyond_label.provider import PinnedProvider, ProviderSettings
from beyond_label.run import ScriptedPublicPolicy, build_manifest, run_manifest


def test_account_401_or_unverified_key_never_enables_execution():
    for evidence in ({}, {"zero_hard_limit":False,"free_model_daily_requests":{"used":0,"limit":50,"remaining":50}}):
        with pytest.raises(ExecutionSuspended):
            account_configuration({}, evidence)


def test_key_evidence_updates_copy_without_claiming_unknown_limits():
    base = {"key_hard_limit_verified":False}
    result = account_configuration(base, {"zero_hard_limit":True,"free_model_daily_requests":{"used":1,"limit":50,"remaining":49}})
    assert result["key_hard_limit_verified"] is True and result["key_hard_limit_usd"] == 0
    assert base == {"key_hard_limit_verified":False}
    assert "provider_tokens_per_minute" not in result


def test_free_quota_stops_at_zero_and_before_next_utc_day():
    today = ["2026-11-14"]
    quota = FreeQuota(2, utc_day=lambda:today[0])
    quota.claim(); quota.claim()
    with pytest.raises(ExecutionSuspended, match="free_daily_quota_exhausted"):
        quota.claim()
    quota = FreeQuota(2, utc_day=lambda:today[0])
    today[0] = "2026-11-15"
    with pytest.raises(ExecutionSuspended, match="free_quota_day_changed"):
        quota.claim()


def test_quota_pause_retains_partial_inspection_and_resumes_without_resampling(tmp_path):
    policy = ScriptedPublicPolicy()
    quota = FreeQuota(1)
    provider = PinnedProvider(ProviderSettings(model=policy.model,provider=policy.provider),policy,before_attempt=quota.claim)
    plan = next(build_manifest("smoke",schedule_seed=s) for s in range(100)
                if build_manifest("smoke",schedule_seed=s)["cells"][0]["purpose"] == "decision")
    with pytest.raises(ExecutionSuspended):
        run_manifest(plan,tmp_path,provider,max_cells=1)
    assert policy.calls == 1
    raw = (tmp_path / "calls.jsonl").read_bytes()
    assert raw.count(b'"event":"attempt_started"') == 1
    provider.before_attempt = FreeQuota(1).claim
    result = run_manifest(plan,tmp_path,provider,max_cells=1)
    assert policy.calls == 2 and result["completed_cells"] == 1
    assert (tmp_path / "calls.jsonl").read_bytes().startswith(raw)


def test_restart_blocks_unsettled_ledger_and_prior_accounting_errors(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.jsonl","0")
    reconcile_ledger(ledger,tmp_path / "runs")
    ledger.reserve("attempt-"+"0"*32,"0",request_hash="a"*64)
    with pytest.raises(ExecutionSuspended, match="ledger_reconciliation_required"):
        reconcile_ledger(ledger,tmp_path / "runs")
    ledger.settle("attempt-"+"0"*32,"0",currency="USD")
    run_dir = tmp_path / "runs" / "smoke"
    run_dir.mkdir(parents=True)
    (run_dir / "calls.jsonl").write_text(json.dumps({"accounting_error":"budget_settlement_failed"})+'\n',encoding='utf-8')
    with pytest.raises(ExecutionSuspended, match="accounting_reconciliation_required"):
        reconcile_ledger(ledger,tmp_path / "runs")


def test_rate_wait_crossing_midnight_never_dispatches_with_old_quota(tmp_path):
    from beyond_label.controls import AttemptBound, ControlError, GuardedTransport
    today = ["2026-11-14"]
    quota = FreeQuota(2, utc_day=lambda:today[0])
    quota.claim()
    class WaitingLimiter:
        def acquire(self, tokens):
            today[0] = "2026-11-15"
    calls = []
    ledger = BudgetLedger(tmp_path / "budget.jsonl","0")
    guard = GuardedTransport(lambda payload:calls.append(payload), ledger, WaitingLimiter(),
                             lambda p:AttemptBound("0",100), before_dispatch=quota.check_dispatch_day)
    with pytest.raises(ControlError, match="free_quota_day_changed_before_dispatch"):
        guard({"messages":[]})
    assert calls == []
    # This unusual after-reservation cancellation remains explicit; no missing
    # response is invented and the pending hold needs reconciliation on restart.
    assert ledger.snapshot()["pending_attempts"] == 1


def test_disabled_config_precedes_any_account_request(tmp_path, monkeypatch):
    from beyond_label import live
    config = tmp_path / "disabled.yaml"
    config.write_text("free_only: true\nlive_execution_enabled: false\naccount_preflight_enabled: false\npaid_calls_authorized: false\nauthorized_spend_cap: 0\nload: 2\nschedule_seed: 271828\n",encoding="utf-8")
    def forbidden():
        raise AssertionError("Offline configuration must not contact an account")
    monkeypatch.setattr(live,"free_account_preflight",forbidden)
    monkeypatch.setattr(live,"ROOT",tmp_path)
    with pytest.raises(ExecutionSuspended,match="offline_execution_disabled"):
        live.run_free(config,"smoke",tmp_path / "runs" / "output")
    monkeypatch.setattr("sys.argv",["live","--config",str(config),"--preflight"])
    assert live.main() == 2
