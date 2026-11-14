"""Explicit free-only execution; no import-time network or paid execution path."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Any

import httpx
import yaml

from .attempts import (AttemptLimit, AttemptLimitError, MAX_ATTEMPTS,
                       CappedFreeAttempts, ExecutionSuspended, FreeQuota)
from .budget import BudgetError, BudgetLedger, _unique_object
from .controls import AttemptBound, GuardedTransport
from .gates import require_real_execution
from .openrouter import OpenRouterFreeTransport, free_account_preflight
from .provider import PinnedProvider, ProviderFailure, ProviderSettings
from .rate_limit import RateLimiter
from .run import (ROOT, Journal, _hash, _validate_journal, _validate_manifest,
                  _writer_lock, build_manifest, run_manifest)


def account_configuration(config: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(evidence, dict) or evidence.get("zero_hard_limit") is not True:
        raise ExecutionSuspended("zero_key_spending_limit_required")
    counts = evidence.get("free_model_daily_requests")
    if (not isinstance(counts, dict) or any(type(counts.get(k)) is not int or counts[k] < 0
            for k in ("used", "limit", "remaining"))
            or counts["used"] + counts["remaining"] != counts["limit"]):
        raise ExecutionSuspended("invalid_free_quota_evidence")
    if counts["remaining"] == 0:
        raise ExecutionSuspended("free_daily_quota_exhausted")
    result = deepcopy(config)
    result.update(key_hard_limit_usd=0, key_hard_limit_verified=True)
    return result


def reconcile_ledger(ledger: BudgetLedger, runs_root: Path) -> None:
    state = ledger.snapshot()
    if ledger.cap != 0 or ledger.currency != "USD" or state["blocked"] or state["uncertain"]:
        raise ExecutionSuspended("ledger_reconciliation_required")
    # A failed post-write fsync can leave a complete settlement on disk. The
    # separate trace marker must still stop restart until evidence is reviewed.
    for path in runs_root.glob("**/calls.jsonl"):
        try:
            for line in path.read_text("utf-8").splitlines():
                if json.loads(line).get("accounting_error"):
                    raise ExecutionSuspended("accounting_reconciliation_required")
        except (OSError, ValueError, AttributeError):
            raise ExecutionSuspended("run_evidence_unreadable") from None


def _record_preflight(session_dir: Path, evidence: dict[str, Any]) -> None:
    record = {"recorded_at_utc": datetime.now(timezone.utc).isoformat(),
              "classification": "account_preflight_not_inference", **evidence}
    with (session_dir / "preflights.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def open_attempt_limit(session: Path, runs_root: Path, ledger: BudgetLedger) -> AttemptLimit:
    """Reconcile the shared counter under the caller's project ownership lock.

    A missing counter cannot silently reset an earlier run's allowance. Extra
    reservations are valid after a crash before attempt_started; they stay used.
    Trace starts and monetary reservations are cross-checks, not additive counts.
    """
    path = session / "attempts.jsonl"
    try:
        calls = sorted(runs_root.glob("**/calls.jsonl"))
        manifests = sorted(runs_root.glob("**/manifest.json"))
        money_attempts = len(ledger.snapshot()["attempts"])
        if not path.exists() and (calls or manifests or money_attempts):
            raise AttemptLimitError("attempt_limit_history_missing")
        counter = AttemptLimit(path)
        if {p.parent for p in calls} != {p.parent for p in manifests}:
            raise AttemptLimitError("attempt_limit_history_inconsistent")
        starts = 0
        for trace in calls:
            stored = json.loads((trace.parent / "manifest.json").read_text("utf-8"),
                                object_pairs_hook=_unique_object)
            plan, config = stored["plan"], stored["run_config"]
            if (stored["run_config_hash"] != _hash({"plan": plan, "config": config})
                    or config.get("evidence_kind") != "empirical"
                    or config.get("transport_provenance") != "openrouter_free_https_v1"):
                raise AttemptLimitError("attempt_limit_history_inconsistent")
            _validate_manifest(plan)
            journal = Journal(trace)
            _validate_journal(journal, plan, config)
            starts += sum(event["event"] == "attempt_started" for event in journal.events)
        if money_attempts > starts or starts > counter.snapshot()["reserved_attempts"]:
            raise AttemptLimitError("attempt_limit_history_inconsistent")
        return counter
    except (OSError, ValueError, KeyError, TypeError, AttributeError, BudgetError):
        raise AttemptLimitError("attempt_limit_history_unreadable") from None


def run_free(config_path: Path, dataset: str, output: Path, *, load: int | None = None,
             freeze_path: Path | None = None, max_cells: int | None = None) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text("utf-8"))
    if not isinstance(config, dict) or config.get("free_only") is not True:
        raise ExecutionSuspended("free_only_configuration_required")
    if config.get("live_execution_enabled") is not True or config.get("account_preflight_enabled") is not True:
        raise ExecutionSuspended("offline_execution_disabled")
    if config.get("paid_calls_authorized") is not False or config.get("authorized_spend_cap") != 0:
        raise ExecutionSuspended("paid_execution_forbidden")
    if (type(config.get("maximum_inference_attempts")) is not int
            or config["maximum_inference_attempts"] != MAX_ATTEMPTS):
        raise ExecutionSuspended("fixed_ten_attempt_limit_required")
    runs_root = (ROOT / "runs").resolve()
    output = output.resolve()
    try:
        output.relative_to(runs_root)
    except ValueError:
        raise ExecutionSuspended("real_runs_must_be_inside_repository_runs") from None
    if output == runs_root or output == runs_root / "_free_session":
        raise ExecutionSuspended("invalid_real_run_directory")
    if load is not None:
        config["load"] = load
    plan = build_manifest(dataset, config["load"], config["schedule_seed"])
    freeze = json.loads(freeze_path.read_text("utf-8")) if freeze_path is not None else None
    session = runs_root / "_free_session"
    session.mkdir(parents=True, exist_ok=True)
    # One project owner shares rate/budget protection across smoke/pilot/main.
    # Other applications must not concurrently use the dedicated experiment key.
    with _writer_lock(session):
        evidence = free_account_preflight()
        _record_preflight(session, evidence)
        config = account_configuration(config, evidence)
        require_real_execution(config, stage=dataset, freeze=freeze)
        ledger = BudgetLedger(session / "budget.jsonl", "0", "USD")
        reconcile_ledger(ledger, runs_root)
        attempt_limit = open_attempt_limit(session, runs_root, ledger)
        fields = ("model", "provider", "provider_route", "provider_identity_source", "require_parameters",
                  "free_only", "temperature", "reasoning", "max_output_tokens")
        settings = ProviderSettings(**{field: config[field] for field in fields})
        token_bound = config.get("total_token_bound")
        if type(token_bound) is not int or token_bound <= 0 or config.get("token_bound_verified") is not True:
            raise ExecutionSuspended("verified_token_bound_required")
        limiter = RateLimiter(config["operator_requests_per_minute"], config["operator_tokens_per_minute"])
        transport = OpenRouterFreeTransport(settings.model, settings.provider_route)
        quota = FreeQuota(evidence["free_model_daily_requests"]["remaining"])
        policy = CappedFreeAttempts(attempt_limit, quota)
        guard = GuardedTransport(transport, ledger, limiter, lambda payload: AttemptBound("0", token_bound),
                                 before_dispatch=quota.check_dispatch_day)
        provider = PinnedProvider(settings, guard, sleep=time.sleep, before_attempt=policy)
        return run_manifest(plan, output, provider, synthetic=False, max_cells=max_cells,
                            execution_config=config, freeze=freeze)


def main() -> int:
    parser = argparse.ArgumentParser(description="Authorized free-only BTL execution; paid requests are forbidden")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/free.yaml")
    parser.add_argument("--dataset", choices=("smoke", "pilot", "main"), default="smoke")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--load", type=int, choices=(2, 8))
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--max-cells", type=int)
    parser.add_argument("--preflight", action="store_true", help="Read key status only; no model calls")
    args = parser.parse_args()
    try:
        if args.preflight:
            config = yaml.safe_load(args.config.read_text("utf-8"))
            if not isinstance(config, dict) or config.get("account_preflight_enabled") is not True:
                raise ExecutionSuspended("offline_account_preflight_disabled")
            result = {"status": "verified", "classification": "account_preflight_not_inference",
                      "evidence": free_account_preflight(), "inference_calls": 0}
        else:
            if args.output is None:
                parser.error("--output is required for execution")
            result = run_free(args.config, args.dataset, args.output, load=args.load,
                              freeze_path=args.freeze, max_cells=args.max_cells)
    except httpx.HTTPStatusError as error:
        result = {"status": "blocked", "reason": "openrouter_http_error", "http_status": error.response.status_code}
    except (ExecutionSuspended, ProviderFailure, AttemptLimitError) as error:
        result = {"status": "blocked", "reason": str(error)}
    except Exception as error:
        # Never print arbitrary config values, credential material or HTTP context.
        result = {"status": "blocked", "reason": "preflight_or_execution_failed", "error_class": type(error).__name__}
    print(json.dumps(result, indent=2, allow_nan=False))
    return 2 if result.get("status") == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
