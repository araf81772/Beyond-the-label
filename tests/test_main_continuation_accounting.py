"""Offline accounting fixtures; all mutations stay in isolated temporary trees.

Inherited observations remain historical empirical evidence. Fabricated suffix
events below are synthetic test fixtures, never collection or billing evidence.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from beyond_label.budget import BudgetLedger
from beyond_label.run import Journal
from beyond_label.staged import StagedAttemptLimit
from scripts.verify_main_continuation import CONTROL_PREFIXES


REPO = Path(__file__).resolve().parents[1]
SESSION = "runs/_paid_staged_session"
CHILD = "continuations/staged_main_52_20261116"
QUOTE = "0.048468209664"
NEW_ID = "attempt-" + "f" * 32


def accounting():
    path = REPO / "scripts/main_continuation_accounting.py"
    assert path.is_file(), "The approved continuation accounting guard is not implemented"
    spec = importlib.util.spec_from_file_location("continuation_accounting_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def retained(tmp_path):
    freeze = json.loads((REPO / "research/execution_freeze.json").read_bytes())
    paths = set(freeze["input_hashes"])
    paths.update(("research/execution_freeze.json", "research/main_continuation_approval.json",
                  freeze["main_manifest_path"]))
    for gate in freeze["gate_evidence"].values():
        paths.update(gate["directory"] + "/" + name for name in gate["files"])
    paths.update("runs/staged_main/" + name for name in (
        "manifest.json", "calls.jsonl", "scores.csv", "usage.csv", "analysis_manifest.json"))
    paths.update(SESSION + "/" + name for name in ("authorization.json", "budget.jsonl", "attempts.jsonl"))
    for relative in paths:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        raw = (REPO / relative).read_bytes()
        name = Path(relative).name
        if relative.startswith(SESSION + "/") and name in CONTROL_PREFIXES:
            length, digest, _ = CONTROL_PREFIXES[name]
            assert len(raw) >= length and hashlib.sha256(raw[:length]).hexdigest() == digest
            raw = raw[:length]
        destination.write_bytes(raw)
    return tmp_path


def controls(root):
    return (BudgetLedger(root / SESSION / "budget.jsonl", "9"),
            StagedAttemptLimit(root / SESSION / "attempts.jsonl"))


def child(root):
    target = root / CHILD
    target.mkdir(parents=True)
    stored = json.loads((root / "runs/staged_main/manifest.json").read_bytes())
    approval_raw = (root / "research/main_continuation_approval.json").read_bytes()
    stored["continuation"] = {
        "continuation_id": "staged-main-52-20261116",
        "approval_sha256": hashlib.sha256(approval_raw).hexdigest(),
        "parent_directory": "runs/staged_main",
        "effective_policy": "review_exact_40_holds_stop_on_any_new_unknown",
        "base_contract_scope": "scientific_replay_only_operational_exception_governs_dispatch",
    }
    (target / "manifest.json").write_text(json.dumps(stored), encoding="utf-8")
    (target / "calls.jsonl").write_bytes((root / "runs/staged_main/calls.jsonl").read_bytes())
    return target


def append_failed_attempt(root, *, outcome=True, settlement=True):
    directory = child(root) if not (root / CHILD).exists() else root / CHILD
    journal = Journal(directory / "calls.jsonl")
    start = deepcopy(next(e for e in reversed(journal.events) if e["event"] == "attempt_started"))
    failed = deepcopy(journal.events[-1])
    for event in (start, failed):
        for key in ("sequence", "previous_hash", "event_hash"):
            event.pop(key)
        event["attempt"] = 3
    ledger, counter = controls(root)
    counter.claim()
    journal.append(start)
    ledger.reserve(NEW_ID, QUOTE, request_hash=start["request_hash"])
    if settlement:
        ledger.settle(NEW_ID, None, currency="USD")
    if outcome:
        journal.append(failed)
    return ledger, counter


def test_approval_and_baseline_match_exact_retained_evidence(retained):
    module = accounting()
    approval = module.load_approval(retained)
    baseline = module.verify_baseline(retained)
    assert approval["approved"] is True
    assert len(baseline["approved_holds"]) == 40
    assert len(baseline["eligible_cell_ids"]) == 52
    assert baseline["eligible_cell_ids"][0] == "main-2061-readback-MAIN-inline-b"


@pytest.mark.parametrize("field,value", [
    ("approved", False), ("budget_cap_usd", "10"), ("maximum_additional_attempts", 479),
    ("stop_on_any_new_unknown_or_stranded_pending", False),
    ("completed_cells_may_be_resampled", True),
])
def test_approval_cannot_broaden_scope(retained, field, value):
    module = accounting()
    path = retained / "research/main_continuation_approval.json"
    record = json.loads(path.read_bytes())
    record[field] = value
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(module.ContinuationAccountingError):
        module.load_approval(retained)


def test_approval_cannot_substitute_hold_identity(retained):
    module = accounting()
    path = retained / "research/main_continuation_approval.json"
    record = json.loads(path.read_bytes())
    record["approved_holds"][0]["attempt_id"] = NEW_ID
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(module.ContinuationAccountingError):
        module.load_approval(retained)


def test_baseline_allows_append_but_rejects_rewritten_prefix(retained):
    module = accounting()
    _, counter = controls(retained)
    counter.claim()
    module.verify_baseline(retained)
    path = retained / SESSION / "attempts.jsonl"
    raw = path.read_bytes()
    path.write_bytes(b" " + raw[1:])
    with pytest.raises(module.ContinuationAccountingError):
        module.verify_baseline(retained)


@pytest.mark.parametrize("relative", ["prompts/reprompt_no_tool.txt", "runs/staged_main/calls.jsonl"])
def test_baseline_rejects_frozen_input_or_parent_mutation(retained, relative):
    module = accounting()
    path = retained / relative
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(module.ContinuationAccountingError):
        module.verify_baseline(retained)


def test_policy_check_is_readonly_and_call_claims_one_original_counter_slot(retained):
    module = accounting()
    ledger, counter = controls(retained)
    policy = module.ApprovedHoldsPolicy(counter, ledger, maximum_cost=QUOTE)
    before = (ledger.path.read_bytes(), counter.path.read_bytes())
    policy.check()
    assert (ledger.path.read_bytes(), counter.path.read_bytes()) == before
    policy()
    assert counter.snapshot()["reserved_attempts"] == 1562
    assert ledger.path.read_bytes() == before[0]


@pytest.mark.parametrize("settle", [False, True], ids=["new_pending", "new_unknown"])
def test_policy_stops_before_claim_for_any_new_unresolved_charge(retained, settle):
    module = accounting()
    ledger, counter = controls(retained)
    policy = module.ApprovedHoldsPolicy(counter, ledger, maximum_cost=QUOTE)
    ledger.reserve(NEW_ID, QUOTE, request_hash="f" * 64)
    if settle:
        ledger.settle(NEW_ID, None, currency="USD")
    before = counter.path.read_bytes()
    with pytest.raises(module.ContinuationAccountingError):
        policy()
    assert counter.path.read_bytes() == before
    assert ledger.snapshot()["held"] == "1.987196596224"


def test_policy_rejects_release_of_an_approved_hold(retained):
    module = accounting()
    ledger, counter = controls(retained)
    policy = module.ApprovedHoldsPolicy(counter, ledger, maximum_cost=QUOTE)
    old = module.load_approval(retained)["approved_holds"][0]["attempt_id"]
    ledger.settle(old, "0", currency="USD")
    with pytest.raises(module.ContinuationAccountingError):
        policy.check()
    assert counter.snapshot()["reserved_attempts"] == 1561


def test_policy_stops_when_less_than_one_full_reservation_remains(retained):
    module = accounting()
    ledger, counter = controls(retained)
    policy = module.ApprovedHoldsPolicy(counter, ledger, maximum_cost=QUOTE)
    ledger.reserve(NEW_ID, "6.85", request_hash="f" * 64)
    ledger.settle(NEW_ID, "6.85", currency="USD")
    with pytest.raises(module.ContinuationAccountingError):
        policy()
    assert counter.snapshot()["reserved_attempts"] == 1561
    policy.check(for_dispatch=False)


def test_policy_enforces_continuation_attempt_cap_without_refunding_history(retained):
    module = accounting()
    ledger, counter = controls(retained)
    policy = module.ApprovedHoldsPolicy(counter, ledger, maximum_cost=QUOTE)
    for _ in range(478):
        counter.claim()
    with pytest.raises(module.ContinuationAccountingError):
        policy()
    assert counter.snapshot()["reserved_attempts"] == 2039
    policy.check(for_dispatch=False)


@pytest.mark.parametrize("ledger_cost,matches", [("0", True), ("0.0001", False)])
def test_receipt_cost_is_matched_numerically_without_inventing_a_charge(retained, ledger_cost, matches):
    from beyond_label.provider import ProviderSettings, parse_response

    module = accounting()
    directory = child(retained)
    journal = Journal(directory / "calls.jsonl")
    start = deepcopy(next(e for e in reversed(journal.events) if e["event"] == "attempt_started"))
    for key in ("sequence", "previous_hash", "event_hash"):
        start.pop(key)
    start["attempt"] = 3
    raw = deepcopy(next(e["result"]["raw_response"] for e in journal.events
                        if e["event"] == "attempt_succeeded" and e["phase"] == "readback"))
    raw["id"] = "gen-synthetic-main52-accounting"
    raw["usage"]["cost"] = 0.0
    stored = json.loads((directory / "manifest.json").read_bytes())
    settings = ProviderSettings.model_validate(stored["run_config"]["provider_settings"])
    result = parse_response(raw, start["payload"], settings, 0.0)
    ledger, counter = controls(retained)
    counter.claim()
    journal.append(start)
    ledger.reserve(NEW_ID, QUOTE, request_hash=start["request_hash"])
    ledger.settle(NEW_ID, ledger_cost, currency="USD")
    journal.append({**start, "event": "attempt_succeeded", "usage": result.usage,
                    "result": result.model_dump(mode="json")})
    if not matches:
        with pytest.raises(module.ContinuationAccountingError, match="receipt_mismatch"):
            module.reconcile_composite(retained, ledger, counter)
        return
    proof = module.reconcile_composite(retained, ledger, counter)
    assert proof["known_receipts"] == 1522
    assert proof["held_reservations"] == 40


@pytest.mark.parametrize("has_child", [False, True])
def test_composite_counts_inherited_main_once(retained, has_child):
    module = accounting()
    if has_child:
        child(retained)
    ledger, counter = controls(retained)
    result = module.reconcile_composite(retained, ledger, counter)
    assert result["journaled_attempts"] == result["reserved_attempts"] == 1561
    assert result["known_receipts"] == 1521 and result["held_reservations"] == 40
    assert result["inherited_main_attempts"] == 1036 and result["new_main_attempts"] == 0
    assert result["completed_cells"] == 652 and result["pending_cells"] == 52
    assert result["settled_cost_usd"] == "0.19176235952"


@pytest.mark.parametrize("outcome,settlement", [(False, False), (False, True), (True, True)])
def test_composite_accounts_for_crash_and_unknown_outcomes_without_settlement(retained, outcome, settlement):
    module = accounting()
    ledger, counter = append_failed_attempt(retained, outcome=outcome, settlement=settlement)
    before = ledger.path.read_bytes()
    result = module.reconcile_composite(retained, ledger, counter)
    assert result["journaled_attempts"] == result["reserved_attempts"] == 1562
    assert result["held_reservations"] == 41 and result["new_main_attempts"] == 1
    assert ledger.path.read_bytes() == before
    with pytest.raises(module.ContinuationAccountingError):
        module.ApprovedHoldsPolicy(counter, ledger, maximum_cost=QUOTE).check()


def test_composite_rejects_missing_unknown_settlement_after_outcome(retained):
    module = accounting()
    ledger, counter = append_failed_attempt(retained, outcome=True, settlement=False)
    with pytest.raises(module.ContinuationAccountingError):
        module.reconcile_composite(retained, ledger, counter)


@pytest.mark.parametrize("fault", ["prefix", "completed", "out_of_order", "duplicate"])
def test_child_cannot_rewrite_parent_or_expand_cell_schedule(retained, fault):
    module = accounting()
    directory = child(retained)
    journal = Journal(directory / "calls.jsonl")
    if fault == "prefix":
        path = directory / "calls.jsonl"
        raw = path.read_bytes()
        path.write_bytes(b" " + raw[1:])
    else:
        plan = json.loads((retained / "runs/staged_main/manifest.json").read_bytes())["plan"]
        chosen = plan["cells"][0 if fault == "completed" else 653 if fault == "out_of_order" else 652]["cell_id"]
        body = {"event": "cell_completed", "cell_id": chosen,
                "first_missing_reason": "synthetic_test_only", "continuation_status": "not_applicable"}
        journal.append(body)
        if fault == "duplicate":
            journal.append(body)
    ledger, counter = controls(retained)
    with pytest.raises(module.ContinuationAccountingError):
        module.reconcile_composite(retained, ledger, counter)


def test_unregistered_empirical_directory_is_rejected(retained):
    module = accounting()
    directory = retained / "continuations/unreviewed"
    directory.mkdir(parents=True)
    for name in ("manifest.json", "calls.jsonl"):
        (directory / name).write_bytes((retained / "runs/staged_main" / name).read_bytes())
    ledger, counter = controls(retained)
    with pytest.raises(module.ContinuationAccountingError):
        module.reconcile_composite(retained, ledger, counter)


def test_readonly_audit_creates_no_original_locks_or_mutations(retained):
    module = accounting()
    before = {str(p.relative_to(retained)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in retained.rglob("*") if p.is_file()}
    result = module.reconcile_readonly(retained)
    after = {str(p.relative_to(retained)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in retained.rglob("*") if p.is_file()}
    assert result["held_reservations"] == 40
    assert after == before
