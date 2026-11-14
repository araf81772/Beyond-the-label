"""Offline financial guard fixtures: no authorization, provider or real costs."""
from concurrent.futures import ThreadPoolExecutor
from decimal import localcontext
import hashlib
import json
import threading

import pytest

from beyond_label.budget import BudgetError, BudgetLedger, _lock


def attempt(index):
    return f"attempt-{index:032x}"


def ledger(tmp_path, cap="1", currency="USD"):
    return BudgetLedger(tmp_path / "budget.jsonl", cap, currency)


def test_decimal_boundary_and_actual_cost_release(tmp_path):
    book = ledger(tmp_path, "0.3")
    book.reserve(attempt(1), "0.2", request_hash="a" * 64)
    state = book.snapshot()
    assert state["held"] == "0.2" and state["available"] == "0.1"
    assert state["attempts"][attempt(1)]["request_hash"] == "a" * 64
    book.settle(attempt(1), "0.1", currency="USD")
    book.reserve(attempt(2), "0.2")
    book.settle(attempt(2), "0.2", currency="USD")
    state = book.snapshot()
    assert state["settled_cost"] == "0.3" and state["available"] == "0"
    before = book.path.read_bytes()
    with pytest.raises(BudgetError, match="cap_would"):
        book.reserve(attempt(3), "0.000000000000000000000000000001")
    assert book.path.read_bytes() == before


def test_exact_accounting_ignores_ambient_decimal_precision(tmp_path):
    with localcontext() as context:
        context.prec = 2
        book = ledger(tmp_path, "0.123456789012345678901234567890123456789")
        book.reserve(attempt(1), "0.023456789012345678901234567890123456789")
        book.settle(attempt(1), "0.023456789012345678901234567890123456789", currency="USD")
        assert book.snapshot()["available"] == "0.1"


def test_ledger_identity_is_independent_of_later_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    book = BudgetLedger("budget.jsonl", "1")
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    book.reserve(attempt(1), "0.1")
    assert book.path == tmp_path / "budget.jsonl"
    assert book.snapshot()["held"] == "0.1"
    assert not (other / "budget.jsonl").exists()


@pytest.mark.parametrize("value", [None, True, 1, 0.1, "-1", "NaN", "Infinity", "1e1000000", "", "1 " , "0." ])
def test_invalid_amounts_never_create_a_ledger(tmp_path, value):
    with pytest.raises(BudgetError, match="invalid_decimal"):
        ledger(tmp_path, value)
    assert not (tmp_path / "budget.jsonl").exists()


@pytest.mark.parametrize("value", ["usd", "US", "", None, True, "USD\n"])
def test_currency_requires_explicit_three_letter_identity(tmp_path, value):
    with pytest.raises(BudgetError, match="invalid_currency"):
        ledger(tmp_path, currency=value)


def test_zero_cap_allows_only_evidenced_zero_cost(tmp_path):
    book = ledger(tmp_path, "0")
    with pytest.raises(BudgetError, match="cap_would"):
        book.reserve(attempt(1), "0.01")
    book.reserve(attempt(1), "0")
    book.settle(attempt(1), "0", currency="USD")
    assert book.snapshot()["settled_cost"] == "0"


def test_interrupted_pending_attempt_is_held_and_cannot_be_reissued(tmp_path):
    book = ledger(tmp_path)
    book.reserve(attempt(1), "0.4")
    reopened = ledger(tmp_path)
    state = reopened.snapshot()
    assert state["held"] == "0.4" and state["available"] == "0.6"
    assert state["uncertain"] and state["pending_attempts"] == 1 and not state["blocked"]
    before = reopened.path.read_bytes()
    with pytest.raises(BudgetError, match="duplicate_budget_attempt"):
        reopened.reserve(attempt(1), "0.4")
    with pytest.raises(BudgetError, match="cap_would"):
        reopened.reserve(attempt(2), "0.7")
    assert reopened.path.read_bytes() == before
    reopened.settle(attempt(1), "0.25", currency="USD")
    assert reopened.snapshot()["available"] == "0.75"


def test_missing_cost_never_becomes_zero_and_later_evidence_is_append_only(tmp_path):
    book = ledger(tmp_path)
    book.reserve(attempt(1), "0.7")
    book.settle(attempt(1), None, currency="USD")
    prefix = book.path.read_bytes()
    state = ledger(tmp_path).snapshot()
    assert state["held"] == "0.7" and state["settled_cost"] == "0"
    assert state["unknown_cost_attempts"] == 1 and not state["blocked"]
    with pytest.raises(BudgetError, match="cap_would"):
        book.reserve(attempt(2), "0.4")
    book.settle(attempt(1), "0.5", currency="USD")
    assert book.path.read_bytes().startswith(prefix)
    assert not book.snapshot()["blocked"]
    assert book.snapshot()["available"] == "0.5"
    book.reserve(attempt(2), "0.5")


def test_distinct_infrastructure_retries_keep_every_unknown_charge_reserved(tmp_path):
    book = ledger(tmp_path)
    for index in range(1, 5):
        book.reserve(attempt(index), "0.25", request_hash="a" * 64)
        book.settle(attempt(index), None, currency="USD")
    state = book.snapshot()
    assert state["unknown_cost_attempts"] == 4
    assert state["held"] == "1" and state["available"] == "0"
    assert state["uncertain"] and not state["blocked"]
    with pytest.raises(BudgetError, match="cap_would"):
        book.reserve(attempt(5), "0.25", request_hash="a" * 64)
    assert len(book.snapshot()["attempts"]) == 4


@pytest.mark.parametrize("cost,cap_exceeded", [("0.7", False), ("1.1", True)])
def test_quote_overrun_is_recorded_before_future_dispatch_is_blocked(tmp_path, cost, cap_exceeded):
    book = ledger(tmp_path)
    book.reserve(attempt(1), "0.5")
    book.settle(attempt(1), cost, currency="USD")
    state = ledger(tmp_path).snapshot()
    assert state["settled_cost"] == cost and state["reservation_exceeded"]
    assert state["cap_exceeded"] is cap_exceeded and state["blocked"]
    assert state["attempts"][attempt(1)]["actual_cost"] == cost
    with pytest.raises(BudgetError, match="reconciliation"):
        book.reserve(attempt(2), "0")


def test_duplicates_and_currency_mismatches_leave_evidence_unchanged(tmp_path):
    book = ledger(tmp_path)
    with pytest.raises(BudgetError, match="unknown_budget_attempt"):
        book.settle(attempt(1), "0", currency="USD")
    book.reserve(attempt(1), "0.3")
    before = book.path.read_bytes()
    with pytest.raises(BudgetError, match="currency_mismatch"):
        book.settle(attempt(1), "0.1", currency="AUD")
    assert book.path.read_bytes() == before
    book.settle(attempt(1), None, currency="USD")
    with pytest.raises(BudgetError, match="duplicate_budget_settlement"):
        book.settle(attempt(1), None, currency="USD")
    book.settle(attempt(1), "0.1", currency="USD")
    before = book.path.read_bytes()
    for value in (None, "0.1", "0.2"):
        with pytest.raises(BudgetError, match="duplicate_budget_settlement"):
            book.settle(attempt(1), value, currency="USD")
    assert book.path.read_bytes() == before


@pytest.mark.parametrize("kwargs", [{"cap": "2"}, {"currency": "AUD"}])
def test_reopen_cannot_change_budget_or_currency(tmp_path, kwargs):
    book = ledger(tmp_path)
    before = book.path.read_bytes()
    with pytest.raises(BudgetError, match="configuration_changed"):
        ledger(tmp_path, **kwargs)
    assert book.path.read_bytes() == before


@pytest.mark.parametrize("bad", ["", "synthetic-private-credential", "attempt-" + "A" * 32, "attempt-" + "0" * 31, True])
def test_only_opaque_attempt_identifiers_enter_the_ledger(tmp_path, bad):
    book = ledger(tmp_path)
    before = book.path.read_bytes()
    with pytest.raises(BudgetError, match="invalid_attempt_id"):
        book.reserve(bad, "0.1")
    assert book.path.read_bytes() == before


@pytest.mark.parametrize("bad", ["", "secret", "A" * 64, True])
def test_invalid_request_hash_is_not_persisted(tmp_path, bad):
    book = ledger(tmp_path)
    before = book.path.read_bytes()
    with pytest.raises(BudgetError, match="invalid_request_hash"):
        book.reserve(attempt(1), "0.1", request_hash=bad)
    assert book.path.read_bytes() == before


def test_torn_or_tampered_journal_is_preserved(tmp_path):
    book = ledger(tmp_path)
    book.reserve(attempt(1), "0.1")
    raw = book.path.read_bytes()
    for broken in (raw[:-1], raw.replace(b'"maximum_cost":"0.1"', b'"maximum_cost":"0.2"'), b""):
        book.path.write_bytes(broken)
        with pytest.raises(BudgetError):
            ledger(tmp_path)
        assert book.path.read_bytes() == broken


def append_rehashed(path, body):
    prior = json.loads(path.read_bytes().splitlines()[-1])
    event = {**body, "sequence": prior["sequence"] + 1, "previous_hash": prior["event_hash"]}
    encode = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    event["event_hash"] = hashlib.sha256(encode(event)).hexdigest()
    with path.open("ab") as stream:
        stream.write(encode(event) + b"\n")


@pytest.mark.parametrize("body", [
    {"event": "settled", "attempt_id": attempt(99), "actual_cost": "0", "currency": "USD"},
    {"event": "reserved", "attempt_id": attempt(2), "maximum_cost": "0.6", "request_hash": None},
    {"event": "reserved", "attempt_id": attempt(1), "maximum_cost": "0.1", "request_hash": None},
    {"event": "reserved", "attempt_id": attempt(2), "maximum_cost": "0.1", "request_hash": None, "headers": {}},
])
def test_hash_valid_but_inconsistent_history_is_rejected(tmp_path, body):
    book = ledger(tmp_path)
    book.reserve(attempt(1), "0.6")
    append_rehashed(book.path, body)
    before = book.path.read_bytes()
    with pytest.raises(BudgetError):
        book.snapshot()
    assert book.path.read_bytes() == before


def test_lock_rejects_reentrant_writer_before_journal_change(tmp_path):
    book = ledger(tmp_path)
    before = book.path.read_bytes()
    with _lock(book.path):
        with pytest.raises(BudgetError, match="ledger_locked"):
            book.reserve(attempt(1), "0.6")
    assert book.path.read_bytes() == before
    book.reserve(attempt(1), "0.6")


def test_two_instances_cannot_overspend_in_a_race(tmp_path):
    first = ledger(tmp_path)
    second = ledger(tmp_path)
    barrier = threading.Barrier(2)

    def reserve(book, index):
        barrier.wait()
        try:
            book.reserve(attempt(index), "0.6")
            return "reserved"
        except BudgetError as error:
            return str(error)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(reserve, first, 1), pool.submit(reserve, second, 2)]
        outcomes = [future.result() for future in futures]
    assert outcomes.count("reserved") == 1
    assert first.snapshot()["held"] == "0.6"
    assert len(first.snapshot()["attempts"]) == 1


def test_fsync_failure_stops_reservation_return_and_preserves_any_written_hold(tmp_path, monkeypatch):
    book = ledger(tmp_path)
    def fail(_):
        raise OSError("synthetic disk failure")
    monkeypatch.setattr("beyond_label.budget.os.fsync", fail)
    with pytest.raises(OSError):
        book.reserve(attempt(1), "0.6")
    # Nothing may dispatch after reserve raises. If the bytes reached storage,
    # conservative replay keeps the reservation rather than treating it free.
    assert book.snapshot()["held"] == "0.6"
