"""Reviewed historical uncertainty stays fully held; no provider calls."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from beyond_label.attempts import CappedPaidAttempts, ExecutionSuspended, PaidAttemptLimit
from beyond_label.budget import BudgetLedger
from beyond_label.cost_reconciliation import (
    CostCoverageError, COVERAGE_PATH, ORIGINAL_RUN, HISTORICAL_ATTEMPT_ID, HISTORICAL_MAXIMUM_COST,
    build_cost_coverage_record, load_cost_coverage,
)
from beyond_label.paid_controls import PAID_MAXIMUM_COST

ROOT = Path(__file__).resolve().parents[1]


def historical_fixture(tmp_path):
    for name in ("manifest.json", "calls.jsonl", "scores.csv", "usage.csv", "analysis_manifest.json"):
        target = tmp_path / ORIGINAL_RUN / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / ORIGINAL_RUN / name).read_bytes())
    session = tmp_path / "runs/_paid_testing_session"
    session.mkdir()
    for name in ("budget.jsonl", "attempts.jsonl", "authorization.json"):
        (session / name).write_bytes((ROOT / "runs/_paid_testing_session" / name).read_bytes())
    record = build_cost_coverage_record(tmp_path)
    path = tmp_path / COVERAGE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record), encoding="utf-8")
    ledger = BudgetLedger(session / "budget.jsonl", "1")
    counter = PaidAttemptLimit(session / "attempts.jsonl")
    return session, record, ledger, counter


def test_coverage_is_not_a_receipt_or_refund_and_keeps_original_bytes(tmp_path):
    session, record, ledger, counter = historical_fixture(tmp_path)
    before = {p: p.read_bytes() for p in (tmp_path / "runs").rglob("*") if p.is_file() and not p.name.endswith(".writer.lock")}
    coverage = load_cost_coverage(tmp_path, ledger)
    state = ledger.snapshot()
    covered = coverage.validate(state)
    assert record["classification"] == "reviewed_conservative_hold_not_billing_receipt"
    assert record["actual_cost_verified"] is False
    assert covered[HISTORICAL_ATTEMPT_ID]["actual_cost"] is None
    assert covered[HISTORICAL_ATTEMPT_ID]["maximum_cost"] == HISTORICAL_MAXIMUM_COST == "0.44084208"
    assert state["uncertain"] and state["held"] == HISTORICAL_MAXIMUM_COST
    assert state["settled_cost"] == "0" and state["available"] == "0.55915792"
    assert counter.snapshot()["reserved_attempts"] == 1
    assert all(path.read_bytes() == raw for path, raw in before.items())


def test_reviewed_hold_allows_a_slot_without_releasing_money(tmp_path):
    session, _, ledger, counter = historical_fixture(tmp_path)
    money = ledger.path.read_bytes()
    callback = CappedPaidAttempts(counter, ledger, coverage=load_cost_coverage(tmp_path, ledger))
    callback()
    assert counter.snapshot()["reserved_attempts"] == 2
    assert ledger.path.read_bytes() == money
    assert ledger.snapshot()["available"] == "0.55915792"


@pytest.mark.parametrize("status", ["pending", "unknown"])
def test_any_new_uncertainty_still_blocks_and_consumes_no_slot(tmp_path, status):
    _, _, ledger, counter = historical_fixture(tmp_path)
    coverage = load_cost_coverage(tmp_path, ledger)
    later = "attempt-" + "a" * 32
    ledger.reserve(later, PAID_MAXIMUM_COST, request_hash="a" * 64)
    if status == "unknown":
        ledger.settle(later, None, currency="USD")
    before = counter.snapshot()
    with pytest.raises(ExecutionSuspended, match="paid_cost_reconciliation_required"):
        CappedPaidAttempts(counter, ledger, coverage=coverage)()
    assert counter.snapshot() == before


def test_known_new_costs_count_alongside_full_historical_hold(tmp_path):
    _, _, ledger, counter = historical_fixture(tmp_path)
    coverage = load_cost_coverage(tmp_path, ledger)
    later = "attempt-" + "a" * 32
    ledger.reserve(later, PAID_MAXIMUM_COST, request_hash="a" * 64)
    ledger.settle(later, "0.12", currency="USD")
    before = counter.snapshot()
    with pytest.raises(ExecutionSuspended, match="paid_smoke_budget_exhausted"):
        CappedPaidAttempts(counter, ledger, coverage=coverage)()
    assert ledger.snapshot()["held"] == PAID_MAXIMUM_COST
    assert ledger.snapshot()["available"] == "0.43915792"
    assert counter.snapshot() == before


@pytest.mark.parametrize("change", ["actual_cost", "maximum_cost", "request_hash", "attempt_id", "record_hash"])
def test_tampered_review_cannot_self_assert_or_reduce_coverage(tmp_path, change):
    _, record, ledger, _ = historical_fixture(tmp_path)
    if change == "record_hash":
        record[change] = "a" * 64
    else:
        values = {"actual_cost": "0", "maximum_cost": "0", "request_hash": "a" * 64, "attempt_id": "attempt-" + "a" * 32}
        record["covered_attempts"][0][change] = values[change]
        body = {key: value for key, value in record.items() if key != "record_hash"}
        record["record_hash"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    (tmp_path / COVERAGE_PATH).write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(CostCoverageError):
        load_cost_coverage(tmp_path, ledger)


@pytest.mark.parametrize("name", ["calls.jsonl", "manifest.json", "scores.csv", "usage.csv", "analysis_manifest.json"])
def test_changed_original_evidence_invalidates_review(tmp_path, name):
    _, _, ledger, _ = historical_fixture(tmp_path)
    path = tmp_path / ORIGINAL_RUN / name
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(CostCoverageError):
        load_cost_coverage(tmp_path, ledger)


def test_coverage_is_revalidated_before_each_attempt(tmp_path):
    _, _, ledger, counter = historical_fixture(tmp_path)
    coverage = load_cost_coverage(tmp_path, ledger)
    (tmp_path / COVERAGE_PATH).unlink()
    with pytest.raises(ExecutionSuspended, match="paid_cost_reconciliation_required"):
        CappedPaidAttempts(counter, ledger, coverage=coverage)()
    assert counter.snapshot()["reserved_attempts"] == 1


def test_fabricated_ledger_snapshot_and_changed_actual_cost_are_rejected(tmp_path):
    _, _, ledger, _ = historical_fixture(tmp_path)
    coverage = load_cost_coverage(tmp_path, ledger)
    fake = deepcopy(ledger.snapshot())
    fake["available"] = "1"
    with pytest.raises(CostCoverageError):
        coverage.validate(fake)
    ledger.settle(HISTORICAL_ATTEMPT_ID, "0", currency="USD")
    with pytest.raises(CostCoverageError):
        coverage.validate(ledger.snapshot())


def test_no_record_leaves_the_existing_unknown_stop_in_place(tmp_path):
    _, _, ledger, counter = historical_fixture(tmp_path)
    with pytest.raises(ExecutionSuspended, match="paid_cost_reconciliation_required"):
        CappedPaidAttempts(counter, ledger)()
    assert counter.snapshot()["reserved_attempts"] == 1


@pytest.mark.parametrize("name", ["budget.jsonl", "attempts.jsonl"])
def test_changed_or_truncated_control_prefix_cannot_be_covered(tmp_path, name):
    session, _, ledger, _ = historical_fixture(tmp_path)
    coverage = load_cost_coverage(tmp_path, ledger)
    path = session / name
    path.write_bytes(path.read_bytes()[:-1])
    with pytest.raises(CostCoverageError):
        coverage.validate()


def test_overrun_still_blocks_even_with_the_historical_coverage(tmp_path):
    _, _, ledger, counter = historical_fixture(tmp_path)
    coverage = load_cost_coverage(tmp_path, ledger)
    later = "attempt-" + "a" * 32
    ledger.reserve(later, PAID_MAXIMUM_COST, request_hash="a" * 64)
    ledger.settle(later, "0.5", currency="USD")
    with pytest.raises(ExecutionSuspended, match="paid_cost_reconciliation_required"):
        CappedPaidAttempts(counter, ledger, coverage=coverage)()
    assert counter.snapshot()["reserved_attempts"] == 1


def test_review_cannot_be_reused_with_another_counter_or_ledger(tmp_path):
    from beyond_label.attempts import AttemptLimitError
    _, _, ledger, counter = historical_fixture(tmp_path)
    coverage = load_cost_coverage(tmp_path, ledger)
    other_counter = PaidAttemptLimit(tmp_path / "another_counter.jsonl", initialize=True)
    other_ledger = BudgetLedger(tmp_path / "another_budget.jsonl", "1")
    for selected_counter, selected_ledger in ((other_counter, ledger), (counter, other_ledger)):
        with pytest.raises(AttemptLimitError, match="invalid_paid_attempt_policy"):
            CappedPaidAttempts(selected_counter, selected_ledger, coverage=coverage)


def test_approved_smaller_future_bound_never_reduces_historical_hold(tmp_path):
    _, _, ledger, counter = historical_fixture(tmp_path)
    coverage = load_cost_coverage(tmp_path, ledger)
    later = "attempt-" + "a" * 32
    ledger.reserve(later, HISTORICAL_MAXIMUM_COST, request_hash="a" * 64)
    ledger.settle(later, "0.12", currency="USD")
    callback = CappedPaidAttempts(counter, ledger, coverage=coverage, maximum_cost="0.048468209664")
    assert callback.maximum_cost == "0.048468209664"
    callback()
    assert counter.snapshot()["reserved_attempts"] == 2
    assert ledger.snapshot()["held"] == HISTORICAL_MAXIMUM_COST
    assert ledger.snapshot()["available"] == "0.43915792"
    assert build_cost_coverage_record(tmp_path)["covered_attempts"][0]["maximum_cost"] == HISTORICAL_MAXIMUM_COST


@pytest.mark.parametrize("maximum", ["0", "0.01", "1", ".048468209664", 0.048468209664, True])
def test_arbitrary_smaller_or_unverified_quote_bounds_are_rejected(tmp_path, maximum):
    from beyond_label.attempts import AttemptLimitError
    _, _, ledger, counter = historical_fixture(tmp_path)
    with pytest.raises(AttemptLimitError, match="invalid_paid_attempt_policy"):
        CappedPaidAttempts(counter, ledger, maximum_cost=maximum)


@pytest.mark.parametrize("field", ["schema_version", "attempt_ordinal"])
def test_boolean_integer_aliases_do_not_preserve_review_hash(tmp_path, field):
    _, record, ledger, _ = historical_fixture(tmp_path)
    if field == "schema_version":
        record[field] = True
    else:
        record["covered_attempts"][0][field] = True
    (tmp_path / COVERAGE_PATH).write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(CostCoverageError, match="reviewed_cost_record_changed"):
        load_cost_coverage(tmp_path, ledger)
