"""Staged USD 9 allowance: offline fixtures only, never a real key or call.

The integration test drives smoke -> pilot -> load-8 smoke -> freeze -> main
through the real run, transport-guard, ledger and freeze code with a scripted
local policy. Its outputs are synthetic engineering evidence in a temporary
tree and say nothing about any model.
"""
from copy import deepcopy
import json
from pathlib import Path
import re
import shutil

import httpx
import pytest
import yaml

from beyond_label import freeze, gates, openrouter, run, staged
from beyond_label.attempts import AttemptLimitError, ExecutionSuspended
from beyond_label.budget import BudgetLedger
from beyond_label.gates import ExecutionBlocked, require_real_execution, require_staged_configuration
from beyond_label.generate import canonical_json
from beyond_label.rate_limit import RateLimiter

REPO = Path(__file__).resolve().parents[1]
COMMIT = "c" * 40
TAG = "fixture-staged-freeze"
RESERVATION = "0.048468209664"


def file_config():
    return yaml.safe_load((REPO / "configs/staged.yaml").read_text("utf-8"))


def runtime_config(stage="smoke", load=2):
    config = file_config()
    config.update(key_hard_limit_usd=10, key_hard_limit_verified=True, staged_stage=stage, load=load,
                  run_directory=gates.STAGED_STAGES[stage][2])
    return config


def good_evidence():
    return dict(key_hard_limit_usd=10, key_limit_remaining_usd=9.5, key_usage_usd=.5,
                key_limit_reset=None, budgets=None, effective_budget=None)


def test_canonical_file_passes_static_pins_for_every_dataset():
    for dataset in ("smoke", "pilot", "main"):
        require_staged_configuration(file_config(), stage=dataset, account_verified=False)
    with pytest.raises(ExecutionBlocked):
        require_staged_configuration(file_config(), stage="other", account_verified=False)


@pytest.mark.parametrize("field,value", [
    ("authorized_spend_cap", 9.01), ("authorized_spend_cap", 10), ("authorized_spend_cap", True),
    ("authorized_total_testing_cap", 11), ("maximum_inference_attempts", 3001),
    ("maximum_unknown_cost_holds", 41), ("unknown_cost_policy", "assume_zero"),
    ("model", "openai/gpt-4.1-mini"), ("provider_route", "auto"), ("provider", "Other"),
    ("reasoning", {}), ("allow_fallbacks", True), ("parallel_tool_calls", True),
    ("temperature", .1), ("max_output_tokens", 513), ("currency", "AUD"),
    ("paid_calls_authorized", False), ("operator_requests_per_minute", 11),
    ("schedule_seed", 0), ("bootstrap_seed", 1), ("bootstrap_resamples", 100),
    ("authorization_id", "paid-smoke-usd1-200-v1"), ("session_directory", "runs/elsewhere"),
    ("accepted_endpoint_models", []), ("infrastructure_retries_after_initial", 4),
])
def test_static_pins_reject_any_changed_scope_or_setting(field, value):
    config = file_config()
    config[field] = value
    with pytest.raises(ExecutionBlocked):
        require_staged_configuration(config, stage="smoke", account_verified=False)


def test_runtime_gate_binds_stage_load_directory_and_freeze():
    require_real_execution(runtime_config("smoke", 2), stage="smoke")
    require_real_execution(runtime_config("pilot", 2), stage="pilot")
    require_real_execution(runtime_config("smoke8", 8), stage="smoke")
    for stage, load, dataset in (("smoke", 8, "smoke"), ("pilot", 8, "pilot"), ("smoke8", 2, "smoke"),
                                 ("pilot", 2, "smoke"), ("smoke", 2, "pilot"), ("main", 4, "main")):
        with pytest.raises(ExecutionBlocked):
            require_real_execution(runtime_config(stage, load), stage=dataset)
    moved = runtime_config("smoke", 2)
    moved["run_directory"] = "runs/another"
    unverified = runtime_config("smoke", 2)
    unverified["key_hard_limit_usd"] = 11
    for config in (moved, unverified):
        with pytest.raises(ExecutionBlocked):
            require_real_execution(config, stage="smoke")
    # Main needs a freeze naming the same load; gate stages may not carry one.
    record = dict(real_smoke_passed=True, real_pilot_passed=True, hashes_verified=True,
                  commit=COMMIT, tag=TAG, selected_load=8)
    require_real_execution(runtime_config("main", 8), stage="main", freeze=record)
    for bad in (None, {**record, "selected_load": 2}, {**record, "real_pilot_passed": False},
                {**record, "tag": ""}):
        with pytest.raises(ExecutionBlocked):
            require_real_execution(runtime_config("main", 8), stage="main", freeze=bad)
    with pytest.raises(ExecutionBlocked):
        require_real_execution(runtime_config("smoke", 2), stage="smoke", freeze=record)


def test_closed_smoke_authorization_still_cannot_run_pilot_or_main():
    from test_paid_live import paid_config
    for stage in ("pilot", "main"):
        with pytest.raises(ExecutionBlocked):
            require_real_execution(paid_config(), stage=stage)


def _controls(tmp_path):
    session = tmp_path / "runs/_paid_staged_session"
    session.mkdir(parents=True)
    ledger = BudgetLedger(session / "budget.jsonl", "9")
    counter = staged.StagedAttemptLimit(session / "attempts.jsonl", initialize=True)
    return ledger, counter


def _hold(ledger, index, cost=None):
    attempt = f"attempt-{index:032x}"
    ledger.reserve(attempt, RESERVATION, request_hash=f"{index:064x}")
    ledger.settle(attempt, cost, currency="USD")


def test_unknown_costs_keep_full_holds_and_stop_at_forty(tmp_path):
    ledger, counter = _controls(tmp_path)
    policy = staged.CappedStagedAttempts(counter, ledger, maximum_cost=RESERVATION)
    for index in range(39):
        _hold(ledger, index)
    state = ledger.snapshot()
    assert state["unknown_cost_attempts"] == 39 and state["settled_cost"] == "0"
    # Nothing is assumed free: 39 full reservations stay off the allowance.
    assert state["held"] == "1.890260176896" and state["available"] == "7.109739823104"
    policy()
    assert counter.snapshot()["reserved_attempts"] == 1
    _hold(ledger, 39)
    with pytest.raises(ExecutionSuspended, match="staged_unknown_cost_hold_limit_reached"):
        policy()
    assert counter.snapshot()["reserved_attempts"] == 1


def test_policy_stops_below_one_reservation_and_cap_never_exceeds_nine(tmp_path):
    ledger, counter = _controls(tmp_path)
    policy = staged.CappedStagedAttempts(counter, ledger, maximum_cost=RESERVATION)
    ledger.reserve("attempt-" + "a" * 32, "8.96", request_hash="a" * 64)
    ledger.settle("attempt-" + "a" * 32, "8.96", currency="USD")
    with pytest.raises(ExecutionSuspended, match="staged_budget_exhausted"):
        policy()
    from beyond_label.budget import BudgetError
    with pytest.raises(BudgetError):
        ledger.reserve("attempt-" + "b" * 32, "0.05", request_hash="b" * 64)
    assert counter.snapshot()["reserved_attempts"] == 0


def test_policy_and_counter_reject_other_allowances(tmp_path):
    ledger, counter = _controls(tmp_path)
    smoke_ledger = BudgetLedger(tmp_path / "other.jsonl", "1")
    from beyond_label.attempts import PaidAttemptLimit
    old_counter = PaidAttemptLimit(tmp_path / "old_attempts.jsonl", initialize=True)
    for bad_counter, bad_ledger in ((counter, smoke_ledger), (old_counter, ledger)):
        with pytest.raises(AttemptLimitError):
            staged.CappedStagedAttempts(bad_counter, bad_ledger, maximum_cost=RESERVATION)
    assert counter.snapshot()["maximum_attempts"] == 3000
    # A paid-smoke journal can never be reopened as the staged allowance.
    with pytest.raises(AttemptLimitError):
        staged.StagedAttemptLimit(tmp_path / "old_attempts.jsonl")
    with pytest.raises(AttemptLimitError):
        staged.StagedAttemptLimit(tmp_path / "absent.jsonl")


@pytest.mark.parametrize("field,value", [
    ("key_hard_limit_usd", None), ("key_hard_limit_usd", 11), ("key_hard_limit_usd", 0),
    ("key_limit_remaining_usd", .04), ("key_limit_remaining_usd", 11), ("key_limit_reset", "monthly"),
    ("effective_budget", {"remaining_usd": .01}),
])
def test_account_evidence_requires_a_nonreset_limit_of_at_most_ten(field, value):
    evidence = good_evidence()
    evidence[field] = value
    with pytest.raises(ExecutionSuspended):
        staged.account_configuration(file_config(), evidence)
    assert staged.account_configuration(file_config(), good_evidence()) == {
        "key_hard_limit_usd": 10, "key_hard_limit_verified": True}


class ScopeAwarePolicy(run.ScriptedPublicPolicy):
    """Public-payload fixture that inspects the out-of-scope target.

    It exists only so the synthetic pilot passes the floor and selects load-8,
    exercising every stage. It is not a model and not the research oracle.
    """

    def __call__(self, payload):
        response = super().__call__(payload)
        calls = response["choices"][0]["message"].get("tool_calls")
        if not calls or calls[0]["function"]["name"] != "inspect":
            return response
        messages = payload["messages"]
        handoff = messages[3]["content"]
        targets = re.findall(r"(LOT-\d{4}) \| penalty if wrong: \d+", handoff)
        numeric = re.search(r"Inspect (LOT-\d{4}), then\s+commit: (\d+)\. Inspect (LOT-\d{4}), then\s+commit: (\d+)", handoff)
        lot = targets[0] if targets else None
        if numeric:
            lot = numeric.group(1) if int(numeric.group(2)) <= int(numeric.group(4)) else numeric.group(3)
        else:
            current = re.search(r"test configuration (\S+)\.", messages[0]["content"]).group(1)
            records = re.findall(r"(REC-\d{4}) \| (LOT-\d{4}) \| result: (?:PASS|FAIL)(?: \| tested_configuration: (\S+))?", handoff)
            scopes = dict(re.findall(r"(REC-\d{4}) \| tested_configuration: (\S+)", handoff))
            scopes.update({record: scope for record, _, scope in records if scope})
            out = [lot_id for record, lot_id, _ in records
                   if lot_id in targets and scopes.get(record) not in (None, current, "[withheld]")]
            if len(out) == 1:
                lot = out[0]
        calls[0]["function"]["arguments"] = canonical_json({"lot_id": lot})
        return response


@pytest.fixture
def staged_root(tmp_path, monkeypatch):
    """Temporary repository root with the real config and a scripted HTTP seam."""
    monkeypatch.setattr(run, "ROOT", tmp_path)
    monkeypatch.setattr(freeze, "ROOT", tmp_path)
    monkeypatch.setattr(run, "_inputs", lambda: {})
    monkeypatch.setattr(freeze, "_inputs", lambda: {})
    monkeypatch.setattr(staged, "paid_account_preflight", good_evidence)
    monkeypatch.setattr(staged, "check_paid_smoke_capabilities", lambda config: {
        "compatible": True, "classification": "synthetic_public_capability_fixture"})
    monkeypatch.setattr(RateLimiter, "acquire", lambda self, bound: None)
    monkeypatch.setattr(staged.time, "sleep", lambda seconds: None)
    (tmp_path / "configs").mkdir()
    shutil.copyfile(REPO / "configs/staged.yaml", tmp_path / "configs/staged.yaml")
    (tmp_path / "data/plans").mkdir(parents=True)
    for name in ("main_load2.json", "main_load8.json"):
        shutil.copyfile(REPO / "data/plans" / name, tmp_path / "data/plans" / name)
    (tmp_path / "research").mkdir()
    config = file_config()
    fixture = ScopeAwarePolicy(config["model"], config["provider"])
    state = {"timeouts": 0, "remote_tag": True}

    def request(method, url, *, payload, **kwargs):
        assert method == "POST"
        if state["timeouts"]:
            state["timeouts"] -= 1
            raise httpx.ReadTimeout("synthetic timeout without receipt")
        result = fixture(payload)
        result["openrouter_metadata"] = {"endpoints": {"available": [{
            "model": "deepseek/deepseek-v4.1-flash-20261017", "provider": config["provider"], "selected": True}]}}
        result["usage"].update(cost=.001, is_byok=False)
        return result

    def git(root, *args, timeout=60):
        if args[0] == "rev-parse":
            return COMMIT + "\n"
        assert args[0] == "ls-remote"
        return f"{COMMIT}\trefs/tags/{TAG}\n" if state["remote_tag"] else ""

    def resolve(ref, path=None):
        return COMMIT if path is None else (tmp_path / path).read_bytes()

    monkeypatch.setattr(openrouter, "_request_json", request)
    monkeypatch.setattr(staged, "_git", git)
    monkeypatch.setattr(freeze, "_git_resolve", resolve)
    return tmp_path, fixture, state


def _ledger(root):
    return BudgetLedger(root / "runs/_paid_staged_session/budget.jsonl", "9").snapshot()


def test_stages_are_ordered_and_readiness_is_read_only(staged_root):
    root, fixture, _ = staged_root
    ready = staged.check_ready("smoke")
    assert ready["ready"] and ready["status"] == "ready_for_smoke_not_executed"
    assert ready["planned_cells"] == 80 and ready["money"]["available_usd"] == "9"
    assert ready["attempts"]["remaining_attempts"] == 3000 and ready["inference_calls"] == 0
    assert fixture.calls == 0 and not (root / "runs").exists()
    for stage, reason in (("pilot", "staged_stage_requires_complete_smoke_on_current_inputs"),
                          ("smoke8", "staged_stage_requires_complete_smoke_on_current_inputs"),
                          ("main", "staged_main_requires_execution_freeze_record")):
        with pytest.raises(ExecutionSuspended, match=reason):
            staged.execute_stage(stage)
        with pytest.raises(ExecutionSuspended, match=reason):
            staged.check_ready(stage)
    assert fixture.calls == 0
    assert not any(path.name == "calls.jsonl" for path in root.rglob("*"))


def test_partial_smoke_does_not_unlock_pilot_and_resume_never_repeats(staged_root):
    root, fixture, _ = staged_root
    first = staged.execute_stage("smoke", max_cells=3)
    assert first["completed_cells"] == 3 and first["pending_cells"] == 77
    count = fixture.calls
    raw = (root / "runs/staged_smoke_load2/calls.jsonl").read_bytes()
    with pytest.raises(ExecutionSuspended, match="requires_complete_smoke"):
        staged.execute_stage("pilot")
    again = staged.execute_stage("smoke", max_cells=0)
    assert again["completed_cells"] == 3 and fixture.calls == count
    assert (root / "runs/staged_smoke_load2/calls.jsonl").read_bytes() == raw
    state = _ledger(root)
    assert len(state["attempts"]) == count and state["unknown_cost_attempts"] == 0
    assert staged.StagedAttemptLimit(root / "runs/_paid_staged_session/attempts.jsonl").snapshot()["reserved_attempts"] == count


def test_timeout_keeps_a_full_hold_and_the_stage_still_completes(staged_root):
    root, fixture, state = staged_root
    state["timeouts"] = 1
    result = staged.execute_stage("smoke", max_cells=4)
    assert result["completed_cells"] == 4 and result["infrastructure_retries"] == 1
    # The only missing observations are the 76 cells not yet started.
    assert result["unknown_cost_attempts"] == 1 and result["first_action_or_readback_missing"] == 76
    money = result["money"]
    assert money["unknown_cost_holds"] == 1 and money["held_for_unknown_or_pending_usd"] == RESERVATION
    # One extra reserved attempt: the timeout is counted, held and never free.
    assert result["attempts"]["reserved_attempts"] == fixture.calls + 1
    journal = run.Journal(root / "runs/staged_smoke_load2/calls.jsonl")
    failed = [event for event in journal.events if event["event"] == "attempt_failed"]
    assert len(failed) == 1 and failed[0]["reason"] == "timeout" and failed[0]["retryable"] is True
    retried = [event for event in journal.events if event["event"] == "attempt_succeeded"
               and event["cell_id"] == failed[0]["cell_id"] and event["phase"] == failed[0]["phase"]]
    assert len(retried) == 1 and retried[0]["attempt"] == 2
    assert retried[0]["request_hash"] == failed[0]["request_hash"]


def test_unaccounted_or_tampered_history_blocks_before_any_call(staged_root):
    root, fixture, _ = staged_root
    staged.execute_stage("smoke", max_cells=1)
    count = fixture.calls
    session = root / "runs/_paid_staged_session"
    # A paid run outside the four fixed directories cannot gain an allowance.
    stray = root / "runs/staged_extra"
    shutil.copytree(root / "runs/staged_smoke_load2", stray)
    with pytest.raises(ExecutionSuspended, match="unaccounted_paid_run_history"):
        staged.execute_stage("smoke", max_cells=1)
    shutil.rmtree(stray)
    # Deleting the money or attempt history never resets the allowance.
    for name in ("budget.jsonl", "attempts.jsonl", "authorization.json"):
        saved = (session / name).read_bytes()
        (session / name).unlink()
        with pytest.raises(ExecutionSuspended):
            staged.execute_stage("smoke", max_cells=1)
        (session / name).write_bytes(saved)
    changed = json.loads((session / "authorization.json").read_text())
    changed["authorized_spend_usd"] = "90"
    saved = (session / "authorization.json").read_bytes()
    (session / "authorization.json").write_text(json.dumps(changed))
    with pytest.raises(ExecutionSuspended, match="staged_authorization_history_changed"):
        staged.execute_stage("smoke", max_cells=1)
    (session / "authorization.json").write_bytes(saved)
    assert fixture.calls == count
    assert staged.execute_stage("smoke", max_cells=1)["completed_cells"] == 2


def test_full_offline_rehearsal_smoke_pilot_load8_freeze_main(staged_root):
    root, fixture, state = staged_root
    smoke = staged.execute_stage("smoke")
    assert smoke["completed_cells"] == 80 and smoke["pending_cells"] == 0
    assert smoke["first_action_or_readback_missing"] == 0
    assert staged.check_ready("pilot")["ready"]
    pilot = staged.execute_stage("pilot")
    assert pilot["completed_cells"] == 160 and pilot["pending_cells"] == 0
    decision = staged.pilot_decision(root)
    assert decision == {"selected_load": 8, "fully_correct_main_pairs": 16, "optimal_numeric_calls": 16}
    # Load-8 was selected, so freezing needs the additional load-8 smoke.
    with pytest.raises(ExecutionSuspended, match="selected_load8_requires_additional_real_smoke"):
        staged.write_freeze_record(TAG)
    assert not (root / "research/execution_freeze.json").exists()
    smoke8 = staged.execute_stage("smoke8")
    assert smoke8["completed_cells"] == 80 and smoke8["load"] == 8
    with pytest.raises(ExecutionSuspended, match="staged_main_requires_execution_freeze_record"):
        staged.execute_stage("main", max_cells=1)
    written = staged.write_freeze_record(TAG)
    assert written["selected_load"] == 8 and written["commit"] == COMMIT
    record = json.loads((root / "research/execution_freeze.json").read_text())
    assert set(record["gate_evidence"]) == {"smoke", "pilot", "smoke8"}
    assert all(proof["cost_evidence"]["accounting_error_attempts"] == 0
               and proof["cost_evidence"]["known_provider_spend_usd"] > 0
               for proof in record["gate_evidence"].values())
    with pytest.raises(ExecutionSuspended, match="already_exists"):
        staged.write_freeze_record(TAG)
    # Protocol: the tag must be visible on the public remote before main.
    before = fixture.calls
    state["remote_tag"] = False
    for action in (lambda: staged.execute_stage("main", max_cells=1), lambda: staged.check_ready("main")):
        with pytest.raises(ExecutionSuspended, match="staged_freeze_tag_not_pushed_to_origin"):
            action()
    assert fixture.calls == before and not (root / "runs/staged_main").exists()
    state["remote_tag"] = True
    ready = staged.check_ready("main")
    assert ready["ready"] and ready["load"] == 8 and ready["planned_cells"] == 704 and ready["freeze_verified"]
    main = staged.execute_stage("main", max_cells=6)
    assert main["completed_cells"] == 6 and main["pending_cells"] == 698 and main["load"] == 8
    stored = json.loads((root / "runs/staged_main/manifest.json").read_text())
    assert stored["run_config"]["freeze"]["record_hash"] == record["record_hash"]
    assert stored["run_config"]["execution_config"]["authorization_id"] == "paid-staged-usd9-v1"
    # A changed gate trace invalidates the freeze for any further main call.
    target = root / "runs/staged_pilot_load2/scores.csv"
    saved = target.read_bytes()
    target.write_bytes(saved + b"\n")
    count = fixture.calls
    with pytest.raises(Exception):
        staged.execute_stage("main", max_cells=1)
    target.write_bytes(saved)
    assert fixture.calls == count
    # Money and attempts reconcile exactly with every scripted response.
    money = _ledger(root)
    assert len(money["attempts"]) == fixture.calls and money["unknown_cost_attempts"] == 0
    assert money["settled_cost"] == str(deepcopy(fixture.calls) / 1000).rstrip("0")
    status = staged.status()
    assert status["stages"]["smoke"]["state"] == "complete" and status["stages"]["main"]["state"] == "partial"
    assert status["freeze_record_present"] and status["pilot_decision"]["selected_load"] == 8
