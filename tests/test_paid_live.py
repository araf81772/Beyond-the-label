"""Paid-smoke authorization tests use only local fixtures, never a real key."""
import copy
import json

import pytest
import yaml

from beyond_label.gates import ExecutionBlocked, require_real_execution


def paid_config():
    return dict(authorization_id="paid-smoke-usd1-200-v1", execution_scope="smoke_only",
        authorized_dataset="smoke", run_directory="runs/paid_smoke_gpt41mini_20261115",
        live_execution_enabled=True, account_preflight_enabled=True, paid_calls_authorized=True,
        free_only=False, authorized_total_testing_cap=10, authorized_spend_cap=1,
        maximum_inference_attempts=200, currency="USD", routing_service="OpenRouter",
        model="openai/gpt-4.1-mini", provider="OpenAI", provider_route="openai",
        provider_identity_source="openrouter_metadata", require_parameters=True,
        accepted_returned_models=["openai/gpt-4.1-mini-2025-04-14", "gpt-4.1-mini-2025-04-14"],
        max_price=dict(prompt=.4, completion=1.6, request=0, image=0),
        temperature=0, temperature_setting_verified=True, reasoning=None,
        reasoning_mode="not_applicable", reasoning_setting_verified=True, max_output_tokens=512,
        concurrency=1, parallel_tool_calls=False, allow_fallbacks=False, provider_docs_verified=True,
        provider_requests_per_minute=None, provider_request_limit_status="not_published",
        operator_requests_per_minute=10, operator_tokens_per_minute=10480880,
        provider_tokens_per_minute=None, provider_token_limit_status="not_published",
        total_token_bound=1048088, total_token_bound_verified=True,
        tool_choice="auto", no_tool_reprompts=1, no_tool_reprompt="Respond with exactly one tool call.",
        infrastructure_retries_after_initial=3,
        key_hard_limit_usd=10, key_hard_limit_verified=True, load=2, schedule_seed=271828)


def test_paid_smoke_gate_accepts_only_current_authorized_stage():
    require_real_execution(paid_config(), stage="smoke")
    for stage in ("pilot", "main", "other"):
        with pytest.raises(ExecutionBlocked):
            require_real_execution(paid_config(), stage=stage)


@pytest.mark.parametrize("field,value", [
    ("authorized_spend_cap", 1.01), ("authorized_spend_cap", True),
    ("authorized_total_testing_cap", 11), ("maximum_inference_attempts", 201),
    ("maximum_inference_attempts", 200.0), ("model", "openai/gpt-4.1"),
    ("provider_route", "auto"), ("provider", "Other"), ("reasoning", {}),
    ("allow_fallbacks", True), ("parallel_tool_calls", True), ("load", 8),
    ("schedule_seed", 0), ("temperature", .1), ("max_output_tokens", 513),
    ("currency", "AUD"), ("key_hard_limit_usd", None), ("key_hard_limit_usd", 11),
    ("key_hard_limit_verified", False), ("paid_calls_authorized", False),
    ("run_directory", "runs/another"), ("operator_requests_per_minute", 11),
])
def test_paid_smoke_gate_rejects_changed_scope_or_settings(field, value):
    config = paid_config()
    config[field] = value
    with pytest.raises(ExecutionBlocked):
        require_real_execution(config, stage="smoke")


def write_config(root, config=None):
    path = root / "configs/paid_smoke.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(config or paid_config()), encoding="utf-8")
    return path


@pytest.mark.parametrize("change", ["pilot", "main", "path", "config_path", "cap", "load", "route"])
def test_paid_entry_rejects_scope_before_account_or_artifacts(tmp_path, monkeypatch, change):
    from beyond_label import paid_live
    monkeypatch.setattr(paid_live, "ROOT", tmp_path)
    monkeypatch.setattr(paid_live, "paid_account_preflight", lambda: pytest.fail("Account must not be contacted"))
    config = paid_config()
    dataset, output = "smoke", tmp_path / config["run_directory"]
    if change in {"pilot", "main"}:
        dataset = change
    elif change == "cap":
        config["authorized_spend_cap"] = 2
    elif change == "load":
        config["load"] = 8
    elif change == "route":
        config["provider_route"] = "auto"
    elif change == "path":
        output = tmp_path / "runs/another"
    path = write_config(tmp_path, config)
    if change == "config_path":
        other = path.with_name("other.yaml")
        other.write_bytes(path.read_bytes())
        path = other
    with pytest.raises((paid_live.ExecutionSuspended, ExecutionBlocked)):
        paid_live.run_paid_smoke(path, dataset, output)
    assert not (tmp_path / "runs").exists()


def good_evidence():
    return dict(key_hard_limit_usd=10, key_limit_remaining_usd=10, key_usage_usd=0,
                key_limit_reset=None, budgets=None, effective_budget=None)


@pytest.mark.parametrize("field,value", [
    ("key_hard_limit_usd", None), ("key_hard_limit_usd", 0), ("key_hard_limit_usd", 11),
    ("key_hard_limit_usd", True), ("key_limit_remaining_usd", .4),
    ("key_limit_remaining_usd", -1), ("key_limit_remaining_usd", 11),
    ("key_limit_reset", "monthly"), ("key_usage_usd", None),
    ("effective_budget", {"remaining_usd": .1}),
])
def test_paid_account_gate_blocks_missing_resetting_excessive_or_exhausted_limits(field, value):
    from beyond_label.paid_live import account_configuration, ExecutionSuspended
    evidence = good_evidence()
    evidence[field] = value
    with pytest.raises(ExecutionSuspended):
        account_configuration(paid_config(), evidence)


def test_paid_account_verified_copy_keeps_dynamic_balance_out_of_manifest():
    from beyond_label.paid_live import account_configuration
    base = paid_config()
    base["key_hard_limit_verified"] = False
    result = account_configuration(base, good_evidence())
    assert result["key_hard_limit_verified"] is True
    assert base["key_hard_limit_verified"] is False
    assert "key_limit_remaining_usd" not in result


def owner_fixture(tmp_path, monkeypatch):
    """Synthetic HTTP seam in a temporary tree, never research observations."""
    from beyond_label import openrouter, paid_live, run
    from beyond_label.rate_limit import RateLimiter
    monkeypatch.setattr(paid_live, "ROOT", tmp_path)
    monkeypatch.setattr(run, "ROOT", tmp_path)
    monkeypatch.setattr(run, "_inputs", lambda: {})
    monkeypatch.setattr(paid_live, "paid_account_preflight", good_evidence)
    monkeypatch.setattr(RateLimiter, "acquire", lambda self, bound: None)
    config = paid_config()
    path = write_config(tmp_path, config)
    fixture = run.ScriptedPublicPolicy(config["model"], config["provider"])
    def synthetic_request(method, url, *, payload, **kwargs):
        assert method == "POST"
        result = fixture(payload)
        result["model"] = "gpt-4.1-mini-2025-04-14"
        result["openrouter_metadata"] = {"endpoints": {"available": [
            {"model": config["model"], "provider": config["provider"], "selected": True}]}}
        result["usage"]["cost"] = .001
        result["usage"]["is_byok"] = False
        return result
    monkeypatch.setattr(openrouter, "_request_json", synthetic_request)
    return paid_live, run, path, tmp_path / config["run_directory"], fixture


def test_paid_owner_local_fixture_reconciles_resumes_and_never_repeats_completed_cells(tmp_path, monkeypatch):
    live, run, config, output, fixture = owner_fixture(tmp_path, monkeypatch)
    first = live.run_paid_smoke(config, "smoke", output, max_cells=2)
    assert first["completed_cells"] == 2
    count = fixture.calls
    raw = (output / "calls.jsonl").read_bytes()
    second = live.run_paid_smoke(config, "smoke", output, max_cells=0)
    assert first == second and fixture.calls == count
    assert (output / "calls.jsonl").read_bytes() == raw
    continued = live.run_paid_smoke(config, "smoke", output, max_cells=2)
    assert continued["completed_cells"] == 4
    assert (output / "calls.jsonl").read_bytes().startswith(raw)
    assert run.rebuild_outputs(output) == continued
    session = tmp_path / "runs/_paid_testing_session"
    from beyond_label.attempts import PaidAttemptLimit
    from beyond_label.budget import BudgetLedger
    counter = PaidAttemptLimit(session / "attempts.jsonl")
    ledger = BudgetLedger(session / "budget.jsonl", "1")
    assert counter.snapshot()["reserved_attempts"] == fixture.calls
    assert len(ledger.snapshot()["attempts"]) == fixture.calls
    assert (tmp_path / "runs/_free_session").exists() is False


@pytest.mark.parametrize("removed", ["attempts.jsonl", "budget.jsonl", "authorization.json", "both"])
def test_paid_missing_shared_history_fails_before_account(tmp_path, monkeypatch, removed):
    live, _, config, output, _ = owner_fixture(tmp_path, monkeypatch)
    live.run_paid_smoke(config, "smoke", output, max_cells=0)
    session = tmp_path / "runs/_paid_testing_session"
    names = ["attempts.jsonl", "budget.jsonl"] if removed == "both" else [removed]
    for name in names:
        (session / name).unlink()
    monkeypatch.setattr(live, "paid_account_preflight", lambda: pytest.fail("No account call after history loss"))
    with pytest.raises(live.ExecutionSuspended):
        live.run_paid_smoke(config, "smoke", output, max_cells=1)


def test_paid_deleted_controls_cannot_reset_unused_reservations(tmp_path, monkeypatch):
    live, _, config, output, _ = owner_fixture(tmp_path, monkeypatch)
    # Authentication rejection leaves durable allowance files but no model run.
    monkeypatch.setattr(live, "paid_account_preflight", lambda: {**good_evidence(), "key_hard_limit_usd": 0})
    with pytest.raises(live.ExecutionSuspended):
        live.run_paid_smoke(config, "smoke", output)
    session = tmp_path / "runs/_paid_testing_session"
    from beyond_label.attempts import PaidAttemptLimit
    PaidAttemptLimit(session / "attempts.jsonl").claim()
    (session / "attempts.jsonl").unlink()
    (session / "budget.jsonl").unlink()
    monkeypatch.setattr(live, "paid_account_preflight", lambda: pytest.fail("No account call after history loss"))
    with pytest.raises(live.ExecutionSuspended, match="history_missing"):
        live.run_paid_smoke(config, "smoke", output)


def test_paid_direct_fixture_cannot_claim_empirical_provenance(tmp_path, monkeypatch):
    from beyond_label import run
    from beyond_label.provider import PinnedProvider, ProviderSettings
    monkeypatch.setattr(run, "ROOT", tmp_path)
    config = paid_config()
    settings = ProviderSettings(**{key: config[key] for key in (
        "model", "provider", "provider_route", "provider_identity_source", "require_parameters",
        "free_only", "temperature", "reasoning", "max_output_tokens", "max_price", "accepted_returned_models")})
    fixture = run.ScriptedPublicPolicy(settings.model, settings.provider)
    provider = PinnedProvider(settings, fixture)
    output = tmp_path / config["run_directory"]
    with pytest.raises(ValueError, match="fixtures remain synthetic"):
        run.run_manifest(run.build_manifest("smoke"), output, provider, synthetic=False, execution_config=config)
    assert fixture.calls == 0 and not output.exists()


def test_paid_all_80_cells_and_completed_resume_have_one_sample_each(tmp_path, monkeypatch):
    live, _, config, output, fixture = owner_fixture(tmp_path, monkeypatch)
    result = live.run_paid_smoke(config, "smoke", output)
    assert result["planned_cells"] == result["completed_cells"] == 80
    assert result["attempted_calls"] == result["successful_calls"] == fixture.calls == 144
    assert result["infrastructure_retries"] == 0
    assert result["pending_cells"] == 0
    count = fixture.calls
    assert live.run_paid_smoke(config, "smoke", output) == result
    assert fixture.calls == count


def test_failed_response_usage_retains_returned_identity_without_resampling(tmp_path, monkeypatch):
    import csv
    from beyond_label import openrouter
    live, _, config, output, fixture = owner_fixture(tmp_path, monkeypatch)
    original = openrouter._request_json
    def wrong_model(*args, **kwargs):
        raw = original(*args, **kwargs)
        raw["model"] = "unexpected-returned-model"
        return raw
    monkeypatch.setattr(openrouter, "_request_json", wrong_model)
    summary = live.run_paid_smoke(config, "smoke", output)
    assert fixture.calls == summary["attempted_calls"] == 1
    assert summary["successful_calls"] == 0
    with (output / "usage.csv").open(encoding="utf-8", newline="") as stream:
        usage = list(csv.DictReader(stream))
    assert usage[0]["model"] == "unexpected-returned-model"
    assert usage[0]["provider"] == "OpenAI"
    assert usage[0]["request_id"]


def test_paid_cli_reports_only_numeric_account_http_status(monkeypatch, capsys):
    import httpx
    from beyond_label import paid_live
    def rejected(*args, **kwargs):
        request = httpx.Request("GET", "https://example.invalid", headers={"Authorization": "sensitive-fixture"})
        response = httpx.Response(401, request=request, text="sensitive-response-fixture")
        raise httpx.HTTPStatusError("sensitive-exception-fixture", request=request, response=response)
    monkeypatch.setattr(paid_live, "run_paid_smoke", rejected)
    monkeypatch.setattr("sys.argv", ["paid_live"])
    assert paid_live.main() == 2
    printed = capsys.readouterr().out
    assert json.loads(printed)["http_status"] == 401
    assert "sensitive" not in printed


def test_paid_valid_prefix_money_rollback_cannot_erase_actual_spend(tmp_path, monkeypatch):
    live, _, config, output, _ = owner_fixture(tmp_path, monkeypatch)
    live.run_paid_smoke(config, "smoke", output, max_cells=2)
    budget = tmp_path / "runs/_paid_testing_session/budget.jsonl"
    budget.write_bytes(budget.read_bytes().splitlines(keepends=True)[0])
    monkeypatch.setattr(live, "paid_account_preflight", lambda: pytest.fail("No account request after money rollback"))
    with pytest.raises(live.ExecutionSuspended, match="history_inconsistent"):
        live.run_paid_smoke(config, "smoke", output)


def test_paid_byok_usage_and_ledger_include_external_upstream_cost(tmp_path, monkeypatch):
    import csv
    from decimal import Decimal
    from beyond_label import openrouter
    from beyond_label.budget import BudgetLedger
    live, run, config, output, fixture = owner_fixture(tmp_path, monkeypatch)
    original = openrouter._request_json
    def byok(*args, **kwargs):
        raw = original(*args, **kwargs)
        raw["usage"].update(is_byok=True, cost_details={"upstream_inference_cost": .002})
        return raw
    monkeypatch.setattr(openrouter, "_request_json", byok)
    result = live.run_paid_smoke(config, "smoke", output, max_cells=2)
    assert result["spend_evidence_complete"] is True
    assert result["experimental_provider_spend"] == pytest.approx(.003 * fixture.calls)
    with (output / "usage.csv").open(encoding="utf-8", newline="") as stream:
        usage = list(csv.DictReader(stream))
    assert all(row["router_cost_usd"] == "0.001" and row["byok_upstream_cost_usd"] == "0.002"
               and row["cost_usd"] == "0.003" and row["is_byok"] == "true" for row in usage)
    ledger = BudgetLedger(tmp_path / "runs/_paid_testing_session/budget.jsonl", "1")
    assert Decimal(ledger.snapshot()["settled_cost"]) == Decimal(".003") * fixture.calls
    assert live.run_paid_smoke(config, "smoke", output, max_cells=0) == result
    # Raw provider cost remains exactly as supplied, distinct from total.
    journal = run.Journal(output / "calls.jsonl")
    successes = [event for event in journal.events if event["event"] == "attempt_succeeded"]
    assert all(event["usage"]["cost"] == .001 for event in successes)


def test_paid_unknown_billing_mode_holds_bound_and_stops_before_second_attempt(tmp_path, monkeypatch):
    from beyond_label import openrouter
    from beyond_label.budget import BudgetLedger
    live, run, config, output, fixture = owner_fixture(tmp_path, monkeypatch)
    original = openrouter._request_json
    def unknown_mode(*args, **kwargs):
        raw = original(*args, **kwargs)
        raw["usage"].pop("is_byok")
        return raw
    monkeypatch.setattr(openrouter, "_request_json", unknown_mode)
    with pytest.raises(live.ExecutionSuspended, match="cost_reconciliation"):
        live.run_paid_smoke(config, "smoke", output)
    result = run.rebuild_outputs(output)
    assert fixture.calls == result["attempted_calls"] == result["successful_calls"] == 1
    assert result["experimental_provider_spend"] is None
    assert result["spend_evidence_complete"] is False and result["unknown_cost_attempts"] == 1
    ledger = BudgetLedger(tmp_path / "runs/_paid_testing_session/budget.jsonl", "1")
    assert ledger.snapshot()["uncertain"] is True
