"""One authorized paid smoke; pilot and main have no execution entry here.

The USD 1 smoke allowance is a subset of the user's USD 10 testing cap. One
fixed output, a shared durable ledger, and 200 irrevocable reservations prevent
new directories or resumes from acquiring another allowance.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import time

import httpx
import yaml

from .attempts import (AttemptLimitError, CappedPaidAttempts, ExecutionSuspended,
                       PaidAttemptLimit)
from .budget import BudgetError, BudgetLedger, _unique_object
from .capabilities import check_paid_smoke_capabilities
from .continuation import CONTINUATION_RECORD, historical_smoke, load_continuation
from .cost_reconciliation import COVERAGE_PATH, load_cost_coverage
from .controls import GuardedTransport
from .gates import (ExecutionBlocked, PAID_SMOKE_AUTHORIZATION, PAID_SMOKE_DIRECTORY,
                    _finite_number, require_paid_smoke_configuration)
from .openrouter import OpenRouterPaidTransport, paid_account_preflight
from .paid_controls import PAID_MAXIMUM_COST, PaidSmokeQuote, paid_observed_cost
from .paid_profile import get_paid_profile
from .provider import PinnedProvider, ProviderFailure, ProviderSettings
from .rate_limit import RateLimiter
from .run import (ROOT, Journal, JournalIntegrityError, _hash, _validate_journal,
                  _validate_manifest, _writer_lock, build_manifest, run_manifest)
from . import run as execution_run


PROVENANCE = "openrouter_paid_https_v1"
MODEL_AMENDMENT = "research/paid_smoke_authorization_amendment.json"


def model_amendment_record() -> dict:
    """The user's explicit model change keeps the original aggregate limits."""
    body = {"schema_version": 1, "authorization_id": PAID_SMOKE_AUTHORIZATION,
            "classification": "user_approved_model_change_preparation_not_execution",
            "original_authorization": authorization_record(),
            "model": "deepseek/deepseek-v4.1-flash-1017", "provider_route": "primeintellect",
            "provider": "PrimeIntellect", "reasoning": {"effort": "none"},
            "total_testing_usd": "10", "smoke_usd": "1", "total_attempts": 200,
            "user_decision": "Prepare DeepSeek/PrimeIntellect (recommended)",
            "historical_attempt_and_hold_preserved": True, "run_now": False}
    return {**body, "record_hash": _hash(body)}


def require_model_amendment(root: Path, model: str) -> None:
    if model == "openai/gpt-4.1-mini":
        return
    try:
        actual = json.loads((root / MODEL_AMENDMENT).read_text("utf-8"), object_pairs_hook=_unique_object)
        if (not isinstance(actual, dict)
                or actual.get("record_hash") != _hash({k: v for k, v in actual.items() if k != "record_hash"})
                or actual != model_amendment_record() or actual["model"] != model):
            raise ExecutionSuspended("paid_model_amendment_changed")
    except (OSError, ValueError, BudgetError):
        raise ExecutionSuspended("paid_model_amendment_required") from None


def _continuation(root: Path) -> dict | None:
    return load_continuation(root, input_hashes=execution_run._inputs())


def _coverage(root: Path, ledger: BudgetLedger):
    return load_cost_coverage(root, ledger) if (root / COVERAGE_PATH).exists() else None


def authorization_record() -> dict:
    return {"authorization_id": PAID_SMOKE_AUTHORIZATION, "execution_scope": "smoke_only",
            "authorized_total_testing_usd": "10", "authorized_smoke_usd": "1",
            "maximum_inference_attempts": 200, "run_directory": PAID_SMOKE_DIRECTORY,
            "model": "openai/gpt-4.1-mini", "provider_route": "openai", "provider": "OpenAI",
            "stop_before": ["pilot", "main"], "attempts_include": ["initial", "retries", "reprompts", "continuations"]}


def _write_authorization(session: Path, *, initialize: bool) -> None:
    path = session / "authorization.json"
    expected = authorization_record()
    try:
        if path.exists():
            if json.loads(path.read_text("utf-8"), object_pairs_hook=_unique_object) != expected:
                raise ExecutionSuspended("paid_authorization_history_changed")
        elif not initialize:
            raise ExecutionSuspended("paid_authorization_history_missing")
        else:
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(expected, indent=2) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
    except (OSError, ValueError, BudgetError):
        raise ExecutionSuspended("paid_authorization_history_unavailable") from None


def account_configuration(config: dict, evidence: dict) -> dict:
    """Use only safe authenticated account summaries, never account credits."""
    cap, remaining = evidence.get("key_hard_limit_usd"), evidence.get("key_limit_remaining_usd")
    usage = evidence.get("key_usage_usd")
    if (not _finite_number(cap) or not 0 < cap <= 10
            or not _finite_number(remaining) or remaining < 0 or remaining > cap
            or not _finite_number(usage) or usage < 0
            or "key_limit_reset" not in evidence or evidence["key_limit_reset"] is not None):
        raise ExecutionSuspended("paid_nonreset_key_limit_at_most_usd10_required")
    maximum_cost = get_paid_profile(config["model"], config["provider_route"])["maximum_cost"]
    if Decimal(str(remaining)) < Decimal(maximum_cost):
        raise ExecutionSuspended("paid_key_remaining_below_reservation")
    # Organization/user budgets can be stricter than the key's own limit.
    effective = evidence.get("effective_budget")
    if effective is not None:
        available = effective.get("remaining_usd") if isinstance(effective, dict) else None
        if not _finite_number(available) or Decimal(str(available)) < Decimal(maximum_cost):
            raise ExecutionSuspended("paid_effective_budget_below_reservation")
    verified = copy.deepcopy(config)
    verified.update(key_hard_limit_usd=cap, key_hard_limit_verified=True)
    require_paid_smoke_configuration(verified, stage="smoke")
    return verified


def _paid_history(runs_root: Path) -> list[Path]:
    """Discover all paid evidence; no alternate output can gain a fresh cap."""
    expected = (runs_root.parent / PAID_SMOKE_DIRECTORY).resolve()
    continuation = _continuation(runs_root.parent)
    active = (runs_root.parent / continuation["active_directory"]).resolve() if continuation else expected
    historical = {(runs_root.parent / item["directory"]).resolve(): item
                  for item in (continuation or {}).get("historical_segments", [])}
    manifests = list(runs_root.rglob("manifest.json")) if runs_root.exists() else []
    calls = list(runs_root.rglob("calls.jsonl")) if runs_root.exists() else []
    if {path.parent for path in calls} != {path.parent for path in manifests}:
        raise ExecutionSuspended("paid_run_history_incomplete")
    paid = []
    for path in manifests:
        try:
            stored = json.loads(path.read_text("utf-8"), object_pairs_hook=_unique_object)
            config = stored["run_config"]
            if config.get("evidence_kind") == "synthetic":
                continue
            if config.get("evidence_kind") != "empirical":
                raise ExecutionSuspended("paid_run_history_invalid")
            if config.get("provider_settings", {}).get("free_only") is True:
                if config.get("transport_provenance") != "openrouter_free_https_v1":
                    raise ExecutionSuspended("paid_run_history_invalid")
                continue
            if path.parent.resolve() not in {expected, active, *historical} or config.get("transport_provenance") != PROVENANCE:
                raise ExecutionSuspended("unaccounted_paid_run_history")
            if path.parent.resolve() in historical:
                # The continuation loader has verified every immutable artifact
                # and the exact collection source for these prior segments.
                if config.get("input_hashes") != historical[path.parent.resolve()]["input_hashes"]:
                    raise ExecutionSuspended("paid_historical_source_changed")
            elif path.parent.resolve() != expected:
                execution = config.get("execution_config", {})
                if (execution.get("continuation_record_hash") != continuation["record_hash"]
                        or execution.get("continuation_source_commit") != continuation["active_source_commit"]):
                    raise ExecutionSuspended("paid_continuation_history_changed")
                if "retained_cells" in continuation and (
                        execution.get("retained_terminal_cells") != continuation["retained_cells"]
                        or execution.get("continuation_dispatch_cell_ids") != continuation["dispatch_cell_ids"]):
                    raise ExecutionSuspended("paid_retained_terminal_history_changed")
            paid.append(path)
        except (OSError, ValueError, KeyError, TypeError, BudgetError):
            raise ExecutionSuspended("paid_run_history_invalid") from None
    return paid


def reconcile_paid_history(session: Path, runs_root: Path, ledger: BudgetLedger,
                           *, initialize: bool = False) -> PaidAttemptLimit:
    """Reconcile counter, actual dispatch journal, and retained money holds."""
    session = session.resolve()
    if (session != (runs_root / "_paid_testing_session").resolve()
            or ledger.path != session / "budget.jsonl" or ledger.cap != 1 or ledger.currency != "USD"):
        raise ExecutionSuspended("paid_shared_budget_required")
    _write_authorization(session, initialize=False)
    continuation = _continuation(runs_root.parent)
    paths = _paid_history(runs_root)
    state = ledger.snapshot()
    coverage = _coverage(runs_root.parent, ledger)
    covered = coverage.validate(state) if coverage is not None else {}
    if state["blocked"] or (state["uncertain"] and not covered):
        raise ExecutionSuspended("paid_budget_reconciliation_required")
    counter_path = session / "attempts.jsonl"
    if not counter_path.exists() and (paths or state["attempts"] or not initialize):
        raise ExecutionSuspended("paid_attempt_history_missing")
    counter = PaidAttemptLimit(counter_path, initialize=initialize)
    starts, outcomes = [], []
    for path in paths:
        try:
            stored = json.loads(path.read_text("utf-8"), object_pairs_hook=_unique_object)
            plan, config = stored["plan"], stored["run_config"]
            if (stored["run_config_hash"] != _hash({"plan": plan, "config": config})
                    or plan != build_manifest("smoke", 2, 271828)):
                raise ExecutionSuspended("paid_run_history_invalid")
            _validate_manifest(plan)
            historical_paths = {(runs_root.parent / item["directory"]).resolve()
                                for item in (continuation or {}).get("historical_segments", [])}
            legacy = continuation is not None and path.parent.resolve() in {
                (runs_root.parent / PAID_SMOKE_DIRECTORY).resolve(), *historical_paths}
            if legacy:
                # This exact hash-bound failed request belongs to its original
                # serializer. It is never normalized or resumed as a new retry.
                events = (Journal(path.parent / "calls.jsonl").events if historical_paths
                          else historical_smoke(runs_root.parent)["events"])
            else:
                journal = Journal(path.parent / "calls.jsonl")
                _validate_journal(journal, plan, config)
                events = journal.events
            if any(event.get("accounting_error") for event in events):
                raise ExecutionSuspended("paid_accounting_reconciliation_required")
            starts += [event for event in events if event["event"] == "attempt_started"]
            outcomes += [(legacy, event) for event in events
                         if event["event"] in {"attempt_succeeded", "attempt_failed"}]
        except (OSError, ValueError, KeyError, TypeError, BudgetError):
            raise ExecutionSuspended("paid_run_history_invalid") from None
    reserved = counter.snapshot()["reserved_attempts"]
    if len(state["attempts"]) != len(starts) or len(starts) > reserved:
        raise ExecutionSuspended("paid_attempt_history_inconsistent")
    expected_costs = Counter()
    reviewed_unknown = Counter(value["request_hash"] for value in covered.values())
    expected_unknown = Counter()
    for legacy, event in outcomes:
        cost = paid_observed_cost({"usage": event.get("usage", {})})
        if cost is None:
            if not legacy:
                raise ExecutionSuspended("paid_cost_history_inconsistent")
            expected_unknown[event["request_hash"]] += 1
        else:
            expected_costs[(event["request_hash"], Decimal(cost))] += 1
    actual_costs = Counter()
    actual_unknown = Counter()
    for attempt_id, attempt in state["attempts"].items():
        if attempt["actual_cost"] is None and attempt_id in covered:
            actual_unknown[attempt["request_hash"]] += 1
            continue
        if not attempt["request_hash"] or attempt["actual_cost"] is None:
            raise ExecutionSuspended("paid_money_history_inconsistent")
        actual_costs[(attempt["request_hash"], Decimal(attempt["actual_cost"]))] += 1
    if actual_costs != expected_costs or expected_unknown != reviewed_unknown or actual_unknown != reviewed_unknown:
        raise ExecutionSuspended("paid_cost_history_inconsistent")
    return counter


def _record_preflight(session: Path, evidence: dict) -> None:
    record = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "classification": "account_preflight_not_inference", "evidence": evidence}
    with (session / "preflights.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def run_paid_smoke(config_path: Path, dataset: str, output: Path, *, max_cells: int | None = None) -> dict:
    """Static authorization checks precede even the read-only account call."""
    config_path, output = Path(config_path).resolve(), Path(output).resolve()
    if config_path != (ROOT / "configs/paid_smoke.yaml").resolve():
        raise ExecutionSuspended("paid_canonical_configuration_required")
    config = yaml.safe_load(config_path.read_text("utf-8"))
    require_paid_smoke_configuration(config, stage=dataset, account_verified=False)
    require_model_amendment(ROOT, config["model"])
    if output != (ROOT / PAID_SMOKE_DIRECTORY).resolve():
        raise ExecutionSuspended("paid_canonical_smoke_directory_required")
    if max_cells is not None and (type(max_cells) is not int or max_cells < 0):
        raise ExecutionSuspended("invalid_max_cells")
    plan = build_manifest("smoke", 2, 271828)
    runs_root, session = ROOT / "runs", ROOT / "runs/_paid_testing_session"
    continuation = _continuation(ROOT)
    active_output = ROOT / continuation["active_directory"] if continuation else output
    history = _paid_history(runs_root)
    prior_controls = any((session / name).exists() for name in ("budget.jsonl", "attempts.jsonl"))
    prior_authorization = (session / "authorization.json").exists()
    session.mkdir(parents=True, exist_ok=True)
    with _writer_lock(session):
        _write_authorization(session, initialize=not history and not prior_controls)
        if not (session / "budget.jsonl").exists() and (history or prior_controls or prior_authorization):
            raise ExecutionSuspended("paid_budget_history_missing")
        ledger = BudgetLedger(session / "budget.jsonl", "1", "USD")
        counter = reconcile_paid_history(session, runs_root, ledger,
                                         initialize=not history and not prior_controls and not prior_authorization)
        # Never repeat an account request merely to discover that local cap is exhausted.
        maximum_cost = get_paid_profile(config["model"], config["provider_route"])["maximum_cost"]
        policy = CappedPaidAttempts(counter, ledger, coverage=_coverage(ROOT, ledger), maximum_cost=maximum_cost)
        if counter.snapshot()["remaining_attempts"] == 0:
            raise ExecutionSuspended("paid_authorized_attempt_limit_exhausted")
        if Decimal(ledger.snapshot()["available"]) < Decimal(maximum_cost):
            raise ExecutionSuspended("paid_smoke_budget_exhausted")
        capabilities = check_paid_smoke_capabilities(config)
        if capabilities.get("compatible") is not True:
            raise ExecutionSuspended("paid_public_capabilities_not_verified")
        evidence = paid_account_preflight()
        _record_preflight(session, evidence)
        config = account_configuration(config, evidence)
        if config["model"] != "openai/gpt-4.1-mini":
            config["model_authorization_amendment_hash"] = model_amendment_record()["record_hash"]
        if continuation is not None:
            config.update(continuation_record_hash=continuation["record_hash"],
                          continuation_source_commit=continuation["active_source_commit"])
            if "retained_cells" in continuation:
                config.update(retained_terminal_cells=copy.deepcopy(continuation["retained_cells"]),
                              continuation_dispatch_cell_ids=list(continuation["dispatch_cell_ids"]))
        settings = ProviderSettings(**{key: config[key] for key in (
            "model", "provider", "provider_route", "provider_identity_source", "require_parameters",
            "free_only", "temperature", "reasoning", "max_output_tokens", "max_price", "accepted_returned_models")},
            accepted_endpoint_models=config.get("accepted_endpoint_models", []))
        transport = OpenRouterPaidTransport(settings.model, settings.provider_route)
        limiter = RateLimiter(config["operator_requests_per_minute"], config["operator_tokens_per_minute"])
        guard = GuardedTransport(transport, ledger, limiter, PaidSmokeQuote(), cost_reader=paid_observed_cost)
        provider = PinnedProvider(settings, guard, sleep=time.sleep, before_attempt=policy)
        return run_manifest(plan, active_output, provider, synthetic=False, max_cells=max_cells, execution_config=config)


def check_smoke_readiness(config_path: Path, *, capability_evidence: dict | None = None,
                          account_evidence: dict | None = None) -> dict:
    """Read-only readiness; never constructs a model transport or run segment.

    Explicit evidence injection supports offline tests. Otherwise only public
    metadata and current-key GET requests occur, after local history validation.
    No attempts, budget settlements or empirical output files are created.
    """
    config_path = Path(config_path).resolve()
    if config_path != (ROOT / "configs/paid_smoke.yaml").resolve():
        raise ExecutionSuspended("paid_canonical_configuration_required")
    config = yaml.safe_load(config_path.read_text("utf-8"))
    require_paid_smoke_configuration(config, stage="smoke", account_verified=False)
    require_model_amendment(ROOT, config["model"])
    continuation = _continuation(ROOT)
    session = ROOT / "runs/_paid_testing_session"
    if not all((session / name).is_file() for name in ("authorization.json", "budget.jsonl", "attempts.jsonl")):
        raise ExecutionSuspended("paid_shared_history_not_prepared")
    ledger = BudgetLedger(session / "budget.jsonl", "1", "USD")
    counter = reconcile_paid_history(session, ROOT / "runs", ledger)
    state, attempts = ledger.snapshot(), counter.snapshot()
    profile = get_paid_profile(config["model"], config["provider_route"])
    capabilities = capability_evidence if capability_evidence is not None else check_paid_smoke_capabilities(config)
    evidence = account_evidence if account_evidence is not None else paid_account_preflight()
    account_configuration(config, evidence)
    budget_ready = not state["blocked"] and Decimal(state["available"]) >= Decimal(profile["maximum_cost"])
    ready = capabilities.get("compatible") is True and budget_ready and attempts["remaining_attempts"] > 0
    return {"status": "ready_for_smoke_not_executed" if ready else "blocked", "ready": ready,
            "model": config["model"], "provider": config["provider"], "reasoning": config["reasoning"],
            "model_route_metadata_verified": capabilities.get("compatible") is True,
            "live_delivery_verified": False, "budget_ready": budget_ready,
            "actual_cost_evidence_complete": not state["uncertain"],
            "known_settled_usd": state["settled_cost"], "retained_hold_usd": state["held"],
            "available_smoke_usd": state["available"], "next_attempt_upper_bound_usd": profile["maximum_cost"],
            "attempts_consumed": attempts["reserved_attempts"], "attempts_remaining": attempts["remaining_attempts"],
            "continuation_record_hash": continuation["record_hash"] if continuation else None,
            "active_source_commit": continuation["active_source_commit"] if continuation else None,
            "active_directory": continuation["active_directory"] if continuation else PAID_SMOKE_DIRECTORY,
            "unique_planned_cells": 80, "inference_calls": 0, "execution_started": False,
            "retained_terminal_cells": len((continuation or {}).get("retained_cells", [])),
            "dispatchable_cells": len((continuation or {}).get("dispatch_cell_ids", range(80))),
            "account_evidence": evidence, "capability_evidence": capabilities}


def main() -> int:
    parser = argparse.ArgumentParser(description="Authorized USD1/200-attempt smoke only; never pilot/main")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/paid_smoke.yaml")
    parser.add_argument("--dataset", choices=("smoke", "pilot", "main"), default="smoke")
    parser.add_argument("--output", type=Path, default=ROOT / PAID_SMOKE_DIRECTORY)
    parser.add_argument("--max-cells", type=int)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-ready", action="store_true", help="Read-only checks; this is the default")
    mode.add_argument("--execute", action="store_true", help="Explicitly execute the authorized smoke")
    args = parser.parse_args()
    if args.max_cells is not None and not args.execute:
        parser.error("--max-cells requires --execute")
    try:
        if not args.execute:
            if args.dataset != "smoke" or args.output.resolve() != (ROOT / PAID_SMOKE_DIRECTORY).resolve():
                raise ExecutionSuspended("paid_readiness_scope_changed")
            result = check_smoke_readiness(args.config)
            print(json.dumps(result, sort_keys=True, allow_nan=False))
            return 0 if result["ready"] else 2
        result = run_paid_smoke(args.config, args.dataset, args.output, max_cells=args.max_cells)
        print(json.dumps({"status": "smoke_stopped_before_pilot", **result}, sort_keys=True, allow_nan=False))
        return 0
    except httpx.HTTPStatusError as error:
        print(json.dumps({"status": "blocked", "reason": "account_http_error",
                          "http_status": error.response.status_code}))
    except (ExecutionSuspended, AttemptLimitError, ProviderFailure) as error:
        print(json.dumps({"status": "blocked", "reason": str(error)}))
    except (ExecutionBlocked, BudgetError, JournalIntegrityError):
        print(json.dumps({"status": "blocked", "reason": "paid_smoke_validation_failed"}))
    except Exception as error:
        print(json.dumps({"status": "blocked", "reason": type(error).__name__}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
