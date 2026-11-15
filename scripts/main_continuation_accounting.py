"""Accounting for the explicitly approved, narrowly scoped main continuation.

No import or verification dispatches inference or settles a reservation. The
launcher separately verifies its operational freeze, exact child metadata,
provider/account readiness and single-owner lock before using this policy.
"""
from __future__ import annotations

from pathlib import Path
import tempfile

try:
    from scripts import verify_main_continuation as baseline
except ModuleNotFoundError:
    import verify_main_continuation as baseline

from beyond_label.attempts import AttemptLimitError, ExecutionSuspended
from beyond_label.budget import BudgetError, BudgetLedger, _amount
from beyond_label.gates import STAGED_SESSION, STAGED_STAGES
from beyond_label.paid_controls import paid_observed_cost
from beyond_label.run import Journal, _validate_journal, _validate_manifest
from beyond_label.staged import StagedAttemptLimit, _staged_history


ROOT = Path(__file__).resolve().parents[1]
APPROVAL = "research/main_continuation_approval.json"
CHILD = "continuations/staged_main_52_20261116"
CONTINUATION_ID = "staged-main-52-20261116"
MAXIMUM_COST = "0.048468209664"
BASE_ATTEMPTS = 1561
ADDITIONAL_ATTEMPTS = 478
BOUNDARY_HASH = "f9836bc495bb80c84ed3e4543e403dacfa473ff44aaaf6f6a7c210405d2c0677"
BASE_SCOPE = "scientific_replay_only_operational_exception_governs_dispatch"
EFFECTIVE_POLICY = "review_exact_40_holds_stop_on_any_new_unknown"


class ContinuationAccountingError(ExecutionSuspended):
    """Fixed reasons only; a suspension never creates a model observation."""


def _require(condition, reason):
    if not condition:
        raise ContinuationAccountingError(reason)


def _read(root, relative):
    try:
        return baseline._read(root, relative)
    except (OSError, ValueError):
        raise ContinuationAccountingError("continuation_evidence_unavailable") from None


def _json(raw):
    try:
        value = baseline._json(raw)
        _require(isinstance(value, dict), "continuation_record_invalid")
        return value
    except (ValueError, TypeError):
        raise ContinuationAccountingError("continuation_record_invalid") from None


def _chain(raw, *, ascii_only=False):
    try:
        return baseline._chain(raw, ascii_only=ascii_only)
    except (ValueError, TypeError, KeyError):
        raise ContinuationAccountingError("continuation_journal_invalid") from None


def _control_prefixes(root):
    result = {}
    for name, (length, digest, count) in baseline.CONTROL_PREFIXES.items():
        raw = _read(root, STAGED_SESSION + "/" + name)
        _require(len(raw) >= length and baseline._sha(raw[:length]) == digest,
                 "continuation_control_prefix_changed")
        records = _chain(raw, ascii_only=True)
        result[name] = {"bytes": length, "sha256": digest, "events": count,
                        "appended_events": len(records) - count,
                        "baseline_records": records[:count]}
    return result


def verify_baseline(root=ROOT):
    """Verify immutable scientific/parent evidence and original control prefixes.

Control appends are permitted here, never rewritten prefixes. This function
reads bytes only and does not instantiate ledger/counter objects or their locks.
"""
    root = Path(root).resolve()
    freeze_raw = _read(root, "research/execution_freeze.json")
    _require(baseline._sha(freeze_raw) == baseline.FREEZE_SHA256, "continuation_freeze_changed")
    freeze = _json(freeze_raw)
    inputs = freeze["input_hashes"]
    _require(len(inputs) == 50 and baseline._frozen_input_paths(root) == set(inputs),
             "continuation_frozen_input_set_changed")
    for path, digest in inputs.items():
        _require(baseline._sha(_read(root, path)) == digest, "continuation_frozen_input_changed")
    _require(baseline._sha(_read(root, freeze["main_manifest_path"])) == freeze["main_manifest_file_sha256"],
             "continuation_plan_changed")
    for gate in freeze["gate_evidence"].values():
        for name, digest in gate["files"].items():
            _require(baseline._sha(_read(root, gate["directory"] + "/" + name)) == digest,
                     "continuation_frozen_gate_changed")
    raw_main = {}
    for name, (length, digest) in baseline.MAIN_FILES.items():
        raw = _read(root, baseline.MAIN + "/" + name)
        _require(len(raw) == length and baseline._sha(raw) == digest, "continuation_parent_changed")
        raw_main[name] = raw
    _require(baseline._sha(_read(root, STAGED_SESSION + "/authorization.json")) == baseline.AUTHORIZATION_SHA256,
             "continuation_base_authorization_changed")
    controls = _control_prefixes(root)
    reservations = {}
    for event in controls["budget.jsonl"]["baseline_records"]:
        if event["event"] == "reserved":
            reservations[event["attempt_id"]] = {
                "request_hash": event["request_hash"], "maximum_cost": event["maximum_cost"],
                "actual_cost": None, "status": "pending"}
        elif event["event"] == "settled":
            reservations[event["attempt_id"]].update(
                actual_cost=event["actual_cost"], status="unknown" if event["actual_cost"] is None else "settled")
    holds = {key: value for key, value in reservations.items() if value["status"] == "unknown"}
    _require(len(holds) == 40, "continuation_baseline_holds_invalid")
    stored = _json(raw_main["manifest.json"])
    return {"freeze": freeze, "stored": stored, "plan": stored["plan"],
            "parent_events": _chain(raw_main["calls.jsonl"]),
            "eligible_cell_ids": [cell["cell_id"] for cell in stored["plan"]["cells"][652:]],
            "approved_holds": holds,
            "control_prefixes": {name: {key: value for key, value in item.items() if key != "baseline_records"}
                                 for name, item in controls.items()}}


def _load_approval(root, proof):
    record = _json(_read(root, APPROVAL))
    exact = {
        "schema_version": 1, "classification": "explicit_user_authorized_operational_exception",
        "continuation_id": CONTINUATION_ID, "approved": True,
        "user_answer_verbatim": "Approve retained holds and stop on any new unknown charge",
        "parent_directory": baseline.MAIN, "directory": CHILD,
        "scientific_freeze_record_hash": baseline.FREEZE_RECORD_HASH,
        "baseline_boundary_report_hash": BOUNDARY_HASH, "baseline_completed_cells": 652,
        "baseline_reserved_attempts": BASE_ATTEMPTS, "maximum_additional_attempts": ADDITIONAL_ATTEMPTS,
        "maximum_aggregate_attempts": 3000, "budget_cap_usd": "9",
        "per_attempt_reservation_usd": MAXIMUM_COST, "approved_hold_total_usd": "1.93872838656",
        "stop_on_any_new_unknown_or_stranded_pending": True, "retry_limit_per_phase": 4,
        "pending_readback_next_attempt": 3, "pacing_minimum_interval_seconds": 15,
        "rate_limit_minimum_cooldown_seconds": 60, "original_scientific_design_changed": False,
        "completed_cells_may_be_resampled": False,
    }
    for key, value in exact.items():
        _require(type(record.get(key)) is type(value) and record[key] == value,
                 "continuation_approval_scope_changed")
    notes = {"recorded_at_utc", "question_verbatim", "authorization_note"}
    _require(set(record) == set(exact) | notes | {"eligible_cell_ids", "approved_holds"}
             and all(type(record.get(key)) is str and record[key].strip() for key in notes),
             "continuation_approval_schema_changed")
    _require(record["eligible_cell_ids"] == proof["eligible_cell_ids"], "continuation_approval_schedule_changed")
    expected = [{"attempt_id": key, **value} for key, value in proof["approved_holds"].items()]
    _require(record["approved_holds"] == expected, "continuation_approval_holds_changed")
    return record


def load_approval(root=ROOT):
    root = Path(root).resolve()
    return _load_approval(root, verify_baseline(root))


def _validate_controls(root, ledger, counter):
    session = root / STAGED_SESSION
    _require(type(ledger) is BudgetLedger and ledger.path == session / "budget.jsonl"
             and ledger.cap == _amount("9") and ledger.currency == "USD"
             and type(counter) is StagedAttemptLimit and counter.path == session / "attempts.jsonl",
             "continuation_shared_controls_required")


def _retained_holds(state, approved):
    _require(all(state["attempts"].get(key) == value for key, value in approved.items()),
             "continuation_approved_hold_changed")


class ApprovedHoldsPolicy:
    """Accept only the enumerated old uncertainty; claim through the old counter."""

    def __init__(self, counter, ledger, maximum_cost):
        _require(type(ledger) is BudgetLedger, "continuation_shared_controls_required")
        self.root = ledger.path.parents[2]
        _validate_controls(self.root, ledger, counter)
        _require(type(maximum_cost) is str and maximum_cost == MAXIMUM_COST,
                 "continuation_reservation_changed")
        self.approval = load_approval(self.root)
        self._approval_sha256 = baseline._sha(_read(self.root, APPROVAL))
        self.approved_holds = {row["attempt_id"]: {k: v for k, v in row.items() if k != "attempt_id"}
                               for row in self.approval["approved_holds"]}
        self.counter, self.ledger, self.maximum_cost = counter, ledger, maximum_cost

    def check(self, *, for_dispatch=True):
        _require(type(for_dispatch) is bool, "continuation_invalid_policy_check")
        _require(baseline._sha(_read(self.root, APPROVAL)) == self._approval_sha256,
                 "continuation_approval_changed_during_run")
        _control_prefixes(self.root)
        try:
            state, attempts = self.ledger.snapshot(), self.counter.snapshot()
            _retained_holds(state, self.approved_holds)
            unresolved = {key for key, value in state["attempts"].items() if value["actual_cost"] is None}
            _require(unresolved == set(self.approved_holds) and state["pending_attempts"] == 0,
                     "continuation_new_unknown_or_pending_charge")
            _require(not state["blocked"]
                     and (not for_dispatch or _amount(state["available"]) >= _amount(self.maximum_cost)),
                     "continuation_budget_exhausted_or_blocked")
            _require(attempts["maximum_attempts"] == 3000
                     and BASE_ATTEMPTS <= attempts["reserved_attempts"] <= BASE_ATTEMPTS + ADDITIONAL_ATTEMPTS
                     and (not for_dispatch or (attempts["reserved_attempts"] < BASE_ATTEMPTS + ADDITIONAL_ATTEMPTS
                                               and attempts["remaining_attempts"] > 0)),
                     "continuation_attempt_limit_reached")
        except (OSError, BudgetError, AttemptLimitError):
            raise ContinuationAccountingError("continuation_control_evidence_unavailable") from None
        return state

    def __call__(self):
        self.check()
        self.counter.claim()


def _history(root, proof, approval):
    try:
        history = _staged_history(root)
        _require(set(history) == set(STAGED_STAGES), "continuation_staged_history_incomplete")
        continuation_root = root / "continuations"
        manifests = {p.parent.resolve() for p in continuation_root.rglob("manifest.json")}
        calls = {p.parent.resolve() for p in continuation_root.rglob("calls.jsonl")}
        allowed = (root / CHILD).resolve()
        _require(manifests == calls and manifests <= {allowed}, "continuation_unaccounted_run_history")
        if allowed.exists():
            _require(manifests == {allowed}, "continuation_child_incomplete")
            stored = _json(_read(root, CHILD + "/manifest.json"))
            parent = proof["stored"]
            _require(all(stored.get(key) == parent[key] for key in ("plan", "run_config", "run_config_hash")),
                     "continuation_child_base_contract_changed")
            metadata = stored.get("continuation", {})
            _require(type(metadata) is dict and metadata.get("continuation_id") == CONTINUATION_ID
                     and metadata.get("approval_sha256") == baseline._sha(_read(root, APPROVAL))
                     and metadata.get("parent_directory") == baseline.MAIN
                     and metadata.get("effective_policy") == EFFECTIVE_POLICY
                     and metadata.get("base_contract_scope") == BASE_SCOPE,
                     "continuation_child_approval_binding_invalid")
            raw = _read(root, CHILD + "/calls.jsonl")
            length, digest = baseline.MAIN_FILES["calls.jsonl"]
            _require(len(raw) >= length and baseline._sha(raw[:length]) == digest,
                     "continuation_inherited_journal_changed")
            events = _chain(raw)
            index = 0
            for event in events[len(proof["parent_events"]):]:
                _require(index < len(approval["eligible_cell_ids"])
                         and event.get("cell_id") == approval["eligible_cell_ids"][index],
                         "continuation_suffix_cell_order_changed")
                if event["event"] == "cell_completed":
                    index += 1
            history["main"] = allowed
        return history
    except (OSError, ValueError, KeyError, TypeError) as error:
        if isinstance(error, ContinuationAccountingError):
            raise
        raise ContinuationAccountingError("continuation_run_history_invalid") from None


def _reconcile(root, state, attempts):
    proof = verify_baseline(root)
    approval = _load_approval(root, proof)
    history = _history(root, proof, approval)
    _retained_holds(state, proof["approved_holds"])
    starts, outcomes = [], {}
    main_events = []
    try:
        for stage in STAGED_STAGES:
            directory = history[stage]
            stored = _json((directory / "manifest.json").read_bytes())
            journal = Journal(directory / "calls.jsonl")
            _validate_manifest(stored["plan"])
            _validate_journal(journal, stored["plan"], stored["run_config"])
            if stage == "main":
                main_events = journal.events
            for event in journal.events:
                _require(not event.get("accounting_error"), "continuation_accounting_error_recorded")
                if event["event"] in {"attempt_started", "attempt_succeeded", "attempt_failed"}:
                    identity = (stage, event["cell_id"], event["phase"], event["attempt"])
                    if event["event"] == "attempt_started":
                        starts.append((identity, event["request_hash"]))
                    else:
                        outcomes[identity] = event
    except (OSError, ValueError, KeyError, TypeError):
        raise ContinuationAccountingError("continuation_run_history_invalid") from None
    _require(not state["blocked"], "continuation_budget_reconciliation_required")
    _require(len(state["attempts"]) == len(starts)
             and len(starts) <= attempts["reserved_attempts"] <= BASE_ATTEMPTS + ADDITIONAL_ATTEMPTS
             and attempts["maximum_attempts"] == 3000, "continuation_attempt_history_inconsistent")
    known = held = 0
    for ((identity, digest), (_, reservation)) in zip(starts, state["attempts"].items()):
        _require(reservation["request_hash"] == digest, "continuation_reservation_order_mismatch")
        outcome = outcomes.get(identity)
        cost = paid_observed_cost({"usage": outcome.get("usage", {})}) if outcome is not None else None
        actual = reservation["actual_cost"]
        _require((actual is None and cost is None)
                 or (actual is not None and cost is not None and _amount(actual) == _amount(cost)),
                 "continuation_receipt_mismatch")
        if outcome is not None:
            _require(reservation["status"] != "pending", "continuation_pending_reservation_has_outcome")
        if cost is None:
            held += 1
        else:
            known += 1
    completed = sum(event["event"] == "cell_completed" for event in main_events)
    new_attempts = sum(event["event"] == "attempt_started" for event in main_events) - 1036
    return {"journaled_attempts": len(starts), "reserved_attempts": attempts["reserved_attempts"],
            "known_receipts": known, "held_reservations": held,
            "source_directory": history["main"].relative_to(root).as_posix(),
            "inherited_main_attempts": 1036, "new_main_attempts": new_attempts,
            "completed_cells": completed, "pending_cells": 704 - completed,
            "settled_cost_usd": state["settled_cost"], "held_usd": state["held"],
            "available_usd": state["available"]}


def reconcile_composite(root, ledger, counter):
    """Validate actual shared controls against one deduplicated staged history."""
    root = Path(root).resolve()
    _validate_controls(root, ledger, counter)
    return _reconcile(root, ledger.snapshot(), counter.snapshot())


def reconcile_readonly(root=ROOT):
    """Audit copied accounting controls; never create locks in the real session."""
    root = Path(root).resolve()
    raw = {name: _read(root, STAGED_SESSION + "/" + name) for name in ("budget.jsonl", "attempts.jsonl")}
    with tempfile.TemporaryDirectory(prefix="btl-continuation-accounting-") as temporary:
        session = Path(temporary) / STAGED_SESSION
        session.mkdir(parents=True)
        for name, content in raw.items():
            (session / name).write_bytes(content)
        ledger = BudgetLedger(session / "budget.jsonl", "9")
        counter = StagedAttemptLimit(session / "attempts.jsonl")
        result = _reconcile(root, ledger.snapshot(), counter.snapshot())
    _require(all(_read(root, STAGED_SESSION + "/" + name) == content for name, content in raw.items()),
             "continuation_controls_changed_during_audit")
    return result


audit_composite = reconcile_readonly
