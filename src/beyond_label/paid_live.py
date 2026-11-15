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
from .controls import GuardedTransport
from .gates import (ExecutionBlocked, PAID_SMOKE_AUTHORIZATION, PAID_SMOKE_DIRECTORY,
                    _finite_number, require_paid_smoke_configuration)
from .openrouter import OpenRouterPaidTransport, paid_account_preflight
from .paid_controls import PAID_MAXIMUM_COST, PaidSmokeQuote, paid_observed_cost
from .provider import PinnedProvider, ProviderFailure, ProviderSettings
from .rate_limit import RateLimiter
from .run import (ROOT, Journal, JournalIntegrityError, _hash, _validate_journal,
                  _validate_manifest, _writer_lock, build_manifest, run_manifest)


PROVENANCE = "openrouter_paid_https_v1"


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
    if Decimal(str(remaining)) < Decimal(PAID_MAXIMUM_COST):
        raise ExecutionSuspended("paid_key_remaining_below_reservation")
    # Organization/user budgets can be stricter than the key's own limit.
    effective = evidence.get("effective_budget")
    if effective is not None:
        available = effective.get("remaining_usd") if isinstance(effective, dict) else None
        if not _finite_number(available) or Decimal(str(available)) < Decimal(PAID_MAXIMUM_COST):
            raise ExecutionSuspended("paid_effective_budget_below_reservation")
    verified = copy.deepcopy(config)
    verified.update(key_hard_limit_usd=cap, key_hard_limit_verified=True)
    require_paid_smoke_configuration(verified, stage="smoke")
    return verified


def _paid_history(runs_root: Path) -> list[Path]:
    """Discover all paid evidence; no alternate output can gain a fresh cap."""
    expected = (runs_root.parent / PAID_SMOKE_DIRECTORY).resolve()
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
            if path.parent.resolve() != expected or config.get("transport_provenance") != PROVENANCE:
                raise ExecutionSuspended("unaccounted_paid_run_history")
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
    paths = _paid_history(runs_root)
    state = ledger.snapshot()
    if state["blocked"] or state["uncertain"]:
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
            journal = Journal(path.parent / "calls.jsonl")
            _validate_journal(journal, plan, config)
            if any(event.get("accounting_error") for event in journal.events):
                raise ExecutionSuspended("paid_accounting_reconciliation_required")
            starts += [event for event in journal.events if event["event"] == "attempt_started"]
            outcomes += [event for event in journal.events
                         if event["event"] in {"attempt_succeeded", "attempt_failed"}]
        except (OSError, ValueError, KeyError, TypeError, BudgetError):
            raise ExecutionSuspended("paid_run_history_invalid") from None
    reserved = counter.snapshot()["reserved_attempts"]
    if len(state["attempts"]) != len(starts) or len(starts) > reserved:
        raise ExecutionSuspended("paid_attempt_history_inconsistent")
    expected_costs = Counter()
    for event in outcomes:
        cost = paid_observed_cost({"usage": event.get("usage", {})})
        if cost is None:
            raise ExecutionSuspended("paid_cost_history_inconsistent")
        expected_costs[(event["request_hash"], Decimal(cost))] += 1
    actual_costs = Counter()
    for attempt in state["attempts"].values():
        if not attempt["request_hash"] or attempt["actual_cost"] is None:
            raise ExecutionSuspended("paid_money_history_inconsistent")
        actual_costs[(attempt["request_hash"], Decimal(attempt["actual_cost"]))] += 1
    if actual_costs != expected_costs:
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
    if output != (ROOT / PAID_SMOKE_DIRECTORY).resolve():
        raise ExecutionSuspended("paid_canonical_smoke_directory_required")
    if max_cells is not None and (type(max_cells) is not int or max_cells < 0):
        raise ExecutionSuspended("invalid_max_cells")
    plan = build_manifest("smoke", 2, 271828)
    runs_root, session = ROOT / "runs", ROOT / "runs/_paid_testing_session"
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
        policy = CappedPaidAttempts(counter, ledger)
        if counter.snapshot()["remaining_attempts"] == 0:
            raise ExecutionSuspended("paid_authorized_attempt_limit_exhausted")
        if Decimal(ledger.snapshot()["available"]) < Decimal(PAID_MAXIMUM_COST):
            raise ExecutionSuspended("paid_smoke_budget_exhausted")
        capabilities = check_paid_smoke_capabilities(config)
        if capabilities.get("compatible") is not True:
            raise ExecutionSuspended("paid_public_capabilities_not_verified")
        evidence = paid_account_preflight()
        _record_preflight(session, evidence)
        config = account_configuration(config, evidence)
        settings = ProviderSettings(**{key: config[key] for key in (
            "model", "provider", "provider_route", "provider_identity_source", "require_parameters",
            "free_only", "temperature", "reasoning", "max_output_tokens", "max_price", "accepted_returned_models")})
        transport = OpenRouterPaidTransport(settings.model, settings.provider_route)
        limiter = RateLimiter(config["operator_requests_per_minute"], config["operator_tokens_per_minute"])
        guard = GuardedTransport(transport, ledger, limiter, PaidSmokeQuote(), cost_reader=paid_observed_cost)
        provider = PinnedProvider(settings, guard, sleep=time.sleep, before_attempt=policy)
        return run_manifest(plan, output, provider, synthetic=False, max_cells=max_cells, execution_config=config)


def main() -> int:
    parser = argparse.ArgumentParser(description="Authorized USD1/200-attempt smoke only; never pilot/main")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/paid_smoke.yaml")
    parser.add_argument("--dataset", choices=("smoke", "pilot", "main"), default="smoke")
    parser.add_argument("--output", type=Path, default=ROOT / PAID_SMOKE_DIRECTORY)
    parser.add_argument("--max-cells", type=int)
    args = parser.parse_args()
    try:
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
