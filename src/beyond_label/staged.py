"""Staged paid execution: smoke, pilot, optional load-8 smoke, freeze, main.

This is the second, separately authorized paid allowance (USD 9 in total, at
most 3,000 attempts). It never reopens, resets or borrows from the closed
USD 1 smoke session; that history stays immutable and is audited separately.

Design rules kept from the protocol and the earlier authorization:

* one pinned model/provider, no fallback, fixed settings (``gates.py``);
* every attempt is reserved durably before dispatch at the profile's
  whole-context worst-case cost and is never refunded as an attempt;
* stages run in order. Pilot needs a complete smoke on the current inputs,
  load-8 smoke needs a pilot that selected load-8, and main needs a verified
  freeze whose tag is visible on the public remote;
* successful or invalid model replies are never resampled.

One rule differs, by explicit user decision recorded in
``research/staged_authorization.json``: an attempt whose charge is unknown
(for example a timeout without a receipt) keeps its entire reservation held
against the cap and execution continues. It is never treated as free. The
run stops when 40 such holds exist or the remaining allowance is below one
worst-case attempt.

Nothing here runs on import. ``status`` is offline. ``check-ready`` performs
only public-metadata and current-key GET requests. Only ``execute`` dispatches
inference, and only for the named stage.
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
import subprocess
import time

import httpx
import yaml

from . import run as execution_run
from .attempts import AttemptLimit, AttemptLimitError, ExecutionSuspended
from .budget import BudgetError, BudgetLedger, _amount, _unique_object
from .capabilities import check_paid_smoke_capabilities
from .controls import GuardedTransport
from .environment import CREDENTIAL_NAMES
from .gates import (ExecutionBlocked, PAID_SMOKE_AUTHORIZATION, PAID_SMOKE_DIRECTORY,
                    STAGED_AUTHORIZATION, STAGED_CONFIG, STAGED_FREEZE_RECORD,
                    STAGED_MAX_ATTEMPTS, STAGED_MAX_UNKNOWN_HOLDS, STAGED_SESSION,
                    STAGED_STAGES, STAGED_UNKNOWN_COST_POLICY, _finite_number,
                    require_staged_configuration)
from .openrouter import OpenRouterPaidTransport, paid_account_preflight
from .paid_controls import PaidSmokeQuote, paid_observed_cost
from .paid_profile import get_paid_profile
from .provider import PinnedProvider, ProviderFailure, ProviderSettings
from .rate_limit import RateLimiter
from .run import (Journal, JournalIntegrityError, _hash, _validate_journal, _validate_manifest,
                  _writer_lock, build_manifest, run_manifest)


PROVENANCE = "openrouter_paid_https_v1"
STAGED_CAP = "9"
SCHEDULE_SEED = 271828
# Closed USD 1 authorization: retained evidence, never part of this allowance.
HISTORICAL_PAID_DIRECTORIES = frozenset({
    PAID_SMOKE_DIRECTORY,
    PAID_SMOKE_DIRECTORY + "/segments/deepseek_primeintellect_v2",
    PAID_SMOKE_DIRECTORY + "/segments/deepseek_primeintellect_v3",
})
_CONTROL_FILES = ("authorization.json", "budget.jsonl", "attempts.jsonl")


class StagedAttemptLimit(AttemptLimit):
    """Irrevocable 3,000-attempt allowance shared by every staged run."""

    _maximum_attempts = STAGED_MAX_ATTEMPTS
    _authorization_id = STAGED_AUTHORIZATION

    def __init__(self, path: Path | str, *, initialize: bool = False):
        if type(initialize) is not bool:
            raise AttemptLimitError("invalid_staged_attempt_initialization")
        self._initialize_new = initialize
        super().__init__(path)

    def _allow_initialize(self) -> bool:
        return self._initialize_new


class CappedStagedAttempts:
    """Pre-attempt callback: cap, hold count and attempt allowance.

    Unknown and still-pending charges keep their full reservation in the
    ledger, so ``available`` already excludes them. Reaching the hold limit or
    having less than one worst-case attempt left suspends before any new
    ``attempt_started`` event, which keeps the cell resumable.
    """

    def __init__(self, counter: StagedAttemptLimit, ledger: BudgetLedger, *, maximum_cost: str):
        if (type(counter) is not StagedAttemptLimit or type(ledger) is not BudgetLedger
                or ledger.cap != _amount(STAGED_CAP) or ledger.currency != "USD"
                or type(maximum_cost) is not str):
            raise AttemptLimitError("invalid_staged_attempt_policy")
        _amount(maximum_cost)
        self.counter, self.ledger, self.maximum_cost = counter, ledger, maximum_cost

    def __call__(self) -> None:
        try:
            state = self.ledger.snapshot()
            if state["blocked"]:
                raise ExecutionSuspended("staged_budget_reconciliation_required")
            if state["pending_attempts"] + state["unknown_cost_attempts"] >= STAGED_MAX_UNKNOWN_HOLDS:
                raise ExecutionSuspended("staged_unknown_cost_hold_limit_reached")
            if _amount(state["available"]) < _amount(self.maximum_cost):
                raise ExecutionSuspended("staged_budget_exhausted")
        except (OSError, ValueError, BudgetError):
            raise ExecutionSuspended("staged_cost_evidence_unavailable") from None
        self.counter.claim()


def authorization_record() -> dict:
    """Fixed description of the allowance; written once into the session."""
    profile = get_paid_profile("deepseek/deepseek-v4.1-flash-1017", "primeintellect")
    return {"authorization_id": STAGED_AUTHORIZATION, "execution_scope": "smoke_pilot_freeze_main",
            "authorized_spend_usd": STAGED_CAP, "authorized_total_testing_usd": "10",
            "maximum_inference_attempts": STAGED_MAX_ATTEMPTS,
            "unknown_cost_policy": STAGED_UNKNOWN_COST_POLICY,
            "maximum_unknown_cost_holds": STAGED_MAX_UNKNOWN_HOLDS,
            "per_attempt_reservation_usd": profile["maximum_cost"],
            "model": profile["model"], "provider_route": profile["provider_route"],
            "provider": profile["provider"], "session_directory": STAGED_SESSION,
            "stage_directories": {stage: value[2] for stage, value in STAGED_STAGES.items()},
            "separate_from_closed_authorization": PAID_SMOKE_AUTHORIZATION,
            "attempts_include": ["initial", "retries", "reprompts", "continuations"]}


def _write_authorization(session: Path, *, initialize: bool) -> None:
    path = session / "authorization.json"
    expected = authorization_record()
    try:
        if path.exists():
            if json.loads(path.read_text("utf-8"), object_pairs_hook=_unique_object) != expected:
                raise ExecutionSuspended("staged_authorization_history_changed")
        elif not initialize:
            raise ExecutionSuspended("staged_authorization_history_missing")
        else:
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(expected, indent=2) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
    except (OSError, ValueError, BudgetError):
        raise ExecutionSuspended("staged_authorization_history_unavailable") from None


def load_staged_config(root: Path, *, dataset: str) -> dict:
    """Read the one canonical file and apply the static pins."""
    path = (root / STAGED_CONFIG).resolve()
    try:
        config = yaml.safe_load(path.read_text("utf-8"))
    except (OSError, ValueError, yaml.YAMLError):
        raise ExecutionSuspended("staged_configuration_unavailable") from None
    try:
        require_staged_configuration(config, stage=dataset, account_verified=False)
    except ExecutionBlocked:
        raise ExecutionSuspended("staged_configuration_changed") from None
    return config


def _staged_history(root: Path) -> dict[str, Path]:
    """Find every staged run; any other paid evidence is unaccounted."""
    runs_root = root / "runs"
    manifests = list(runs_root.rglob("manifest.json")) if runs_root.exists() else []
    calls = list(runs_root.rglob("calls.jsonl")) if runs_root.exists() else []
    if {path.parent for path in calls} != {path.parent for path in manifests}:
        raise ExecutionSuspended("staged_run_history_incomplete")
    directories = {value[2]: stage for stage, value in STAGED_STAGES.items()}
    found: dict[str, Path] = {}
    for path in manifests:
        try:
            relative = path.parent.resolve().relative_to(root.resolve()).as_posix()
            stored = json.loads(path.read_text("utf-8"), object_pairs_hook=_unique_object)
            config = stored["run_config"]
            kind = config.get("evidence_kind")
            if kind == "synthetic":
                if relative in directories:
                    raise ExecutionSuspended("synthetic_evidence_in_staged_directory")
                continue
            if kind != "empirical":
                raise ExecutionSuspended("staged_run_history_invalid")
            if relative in HISTORICAL_PAID_DIRECTORIES:
                continue
            if config.get("provider_settings", {}).get("free_only") is True:
                if config.get("transport_provenance") != "openrouter_free_https_v1" or relative in directories:
                    raise ExecutionSuspended("staged_run_history_invalid")
                continue
            if (relative not in directories or config.get("transport_provenance") != PROVENANCE
                    or config.get("execution_config", {}).get("authorization_id") != STAGED_AUTHORIZATION):
                raise ExecutionSuspended("unaccounted_paid_run_history")
            found[directories[relative]] = path.parent
        except (OSError, ValueError, KeyError, TypeError, AttributeError, BudgetError):
            raise ExecutionSuspended("staged_run_history_invalid") from None
    return found


def reconcile_staged_history(root: Path, ledger: BudgetLedger, counter: StagedAttemptLimit) -> dict:
    """Journals, money and attempts must tell the same story before dispatch.

    Every provider-reported cost in a journal must appear exactly once in the
    ledger. Every held reservation must belong to a journaled attempt that has
    no receipt. Attempt starts can never exceed the irrevocable allowance.
    """
    session = (root / STAGED_SESSION).resolve()
    if (type(ledger) is not BudgetLedger or ledger.path != session / "budget.jsonl"
            or ledger.cap != _amount(STAGED_CAP) or ledger.currency != "USD"
            or type(counter) is not StagedAttemptLimit or counter.path != session / "attempts.jsonl"):
        raise ExecutionSuspended("staged_shared_controls_required")
    _write_authorization(session, initialize=False)
    starts = 0
    known: Counter = Counter()
    without_receipt: Counter = Counter()
    for stage, directory in _staged_history(root).items():
        dataset, load, _ = STAGED_STAGES[stage]
        try:
            stored = json.loads((directory / "manifest.json").read_text("utf-8"), object_pairs_hook=_unique_object)
            plan, config = stored["plan"], stored["run_config"]
            if (stored["run_config_hash"] != _hash({"plan": plan, "config": config})
                    or plan.get("dataset") != dataset or (load is not None and plan.get("load") != load)
                    or plan.get("schedule_seed") != SCHEDULE_SEED
                    or config["execution_config"].get("staged_stage") != stage):
                raise ExecutionSuspended("staged_run_history_invalid")
            _validate_manifest(plan)
            journal = Journal(directory / "calls.jsonl")
            _validate_journal(journal, plan, config)
        except (OSError, ValueError, KeyError, TypeError, BudgetError):
            raise ExecutionSuspended("staged_run_history_invalid") from None
        open_attempts: dict[tuple, str] = {}
        for event in journal.events:
            if event.get("accounting_error"):
                raise ExecutionSuspended("staged_accounting_reconciliation_required")
            if event["event"] == "attempt_started":
                starts += 1
                open_attempts[(event["cell_id"], event["phase"], event["attempt"])] = event["request_hash"]
            elif event["event"] in {"attempt_succeeded", "attempt_failed"}:
                open_attempts.pop((event["cell_id"], event["phase"], event["attempt"]), None)
                cost = paid_observed_cost({"usage": event.get("usage", {})})
                if cost is None:
                    without_receipt[event["request_hash"]] += 1
                else:
                    known[(event["request_hash"], Decimal(cost))] += 1
        for digest in open_attempts.values():
            without_receipt[digest] += 1
    state = ledger.snapshot()
    if state["blocked"]:
        raise ExecutionSuspended("staged_budget_reconciliation_required")
    ledger_known: Counter = Counter()
    ledger_held: Counter = Counter()
    for attempt in state["attempts"].values():
        if not attempt["request_hash"]:
            raise ExecutionSuspended("staged_money_history_inconsistent")
        if attempt["actual_cost"] is None:
            ledger_held[attempt["request_hash"]] += 1
        else:
            ledger_known[(attempt["request_hash"], Decimal(attempt["actual_cost"]))] += 1
    if ledger_known != known or ledger_held - without_receipt:
        raise ExecutionSuspended("staged_cost_history_inconsistent")
    reserved = counter.snapshot()["reserved_attempts"]
    if starts > reserved or len(state["attempts"]) > starts:
        raise ExecutionSuspended("staged_attempt_history_inconsistent")
    return {"journaled_attempts": starts, "reserved_attempts": reserved,
            "known_receipts": sum(known.values()), "held_reservations": sum(ledger_held.values())}


def _git(root: Path, *args: str, timeout: int = 60) -> str:
    environment = {key: value for key, value in os.environ.items() if key not in CREDENTIAL_NAMES}
    environment.update(GIT_TERMINAL_PROMPT="0", GIT_NO_LAZY_FETCH="1")
    try:
        result = subprocess.run(["git", *args], cwd=root, env=environment, capture_output=True,
                                timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        raise ExecutionSuspended("staged_git_evidence_unavailable") from None
    if result.returncode:
        raise ExecutionSuspended("staged_git_evidence_unavailable")
    try:
        return result.stdout.decode("ascii")
    except UnicodeError:
        raise ExecutionSuspended("staged_git_evidence_unavailable") from None


def require_remote_freeze_tag(root: Path, record: dict) -> None:
    """Protocol section 8: the freeze tag is pushed before any main call."""
    tag, commit = record["tag"], record["commit"]
    listing = _git(root, "ls-remote", "--tags", "origin", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}")
    if commit not in {line.split("\t")[0] for line in listing.splitlines() if line.strip()}:
        raise ExecutionSuspended("staged_freeze_tag_not_pushed_to_origin")


def load_freeze_record(root: Path) -> dict:
    path = root / STAGED_FREEZE_RECORD
    try:
        record = json.loads(path.read_bytes(), object_pairs_hook=_unique_object)
    except (OSError, ValueError, BudgetError):
        raise ExecutionSuspended("staged_main_requires_execution_freeze_record") from None
    if (not isinstance(record, dict) or type(record.get("selected_load")) is not int
            or record["selected_load"] not in (2, 8)):
        raise ExecutionSuspended("staged_execution_freeze_record_invalid")
    return record


def pilot_decision(root: Path) -> dict:
    """Trace-derived ceiling/floor decision of the complete staged pilot."""
    from .pilot import summarize_pilot
    try:
        summary = summarize_pilot(root / STAGED_STAGES["pilot"][2])
    except (OSError, ValueError, KeyError, TypeError):
        raise ExecutionSuspended("staged_pilot_not_verified") from None
    if summary.get("actual_pilot_verified") is not True:
        raise ExecutionSuspended("staged_pilot_incomplete")
    if summary.get("actual_model_change_decided") is not False:
        raise ExecutionSuspended("staged_pilot_floor_requires_model_change")
    return {"selected_load": summary["actual_selected_load"],
            "fully_correct_main_pairs": summary["counts"]["fully_correct_main_pairs"],
            "optimal_numeric_calls": summary["counts"]["optimal_numeric_calls"]}


def stage_prerequisites(root: Path, stage: str, *, plan: dict, settings: ProviderSettings,
                        freeze_record: dict | None) -> dict:
    """Gates in protocol order; each is recomputed from retained raw traces."""
    from .freeze import FreezeError, _verified_run, verify_freeze
    if stage == "smoke":
        return {"required": "none; first stage"}
    try:
        smoke = _verified_run(root / STAGED_STAGES["smoke"][2], "smoke", 2, execution_run._inputs())
    except (FreezeError, OSError):
        raise ExecutionSuspended("staged_stage_requires_complete_smoke_on_current_inputs") from None
    if stage == "pilot":
        return {"smoke_completed_cells": smoke["completed_cells"]}
    decision = pilot_decision(root)
    if stage == "smoke8":
        if decision["selected_load"] != 8:
            raise ExecutionSuspended("staged_load8_smoke_requires_pilot_selecting_load8")
        return {"pilot_decision": decision}
    if freeze_record is None:
        raise ExecutionSuspended("staged_main_requires_execution_freeze_record")
    try:
        proof = verify_freeze(freeze_record, plan, settings)
    except FreezeError as error:
        raise ExecutionSuspended("staged_freeze_verification_failed:" + str(error)) from None
    if freeze_record["selected_load"] != decision["selected_load"]:
        raise ExecutionSuspended("staged_freeze_load_differs_from_pilot")
    return {"pilot_decision": decision, "freeze": proof}


def _settings(config: dict) -> ProviderSettings:
    return ProviderSettings(**{key: config[key] for key in (
        "model", "provider", "provider_route", "provider_identity_source", "require_parameters",
        "free_only", "temperature", "reasoning", "max_output_tokens", "max_price", "accepted_returned_models")},
        accepted_endpoint_models=config.get("accepted_endpoint_models", []))


def account_configuration(config: dict, evidence: dict) -> dict:
    """Safe current-key summary only: a nonreset hard limit of at most USD 10."""
    cap, remaining = evidence.get("key_hard_limit_usd"), evidence.get("key_limit_remaining_usd")
    usage = evidence.get("key_usage_usd")
    if (not _finite_number(cap) or not 0 < cap <= 10
            or not _finite_number(remaining) or remaining < 0 or remaining > cap
            or not _finite_number(usage) or usage < 0
            or "key_limit_reset" not in evidence or evidence["key_limit_reset"] is not None):
        raise ExecutionSuspended("staged_nonreset_key_limit_at_most_usd10_required")
    maximum_cost = get_paid_profile(config["model"], config["provider_route"])["maximum_cost"]
    if Decimal(str(remaining)) < Decimal(maximum_cost):
        raise ExecutionSuspended("staged_key_remaining_below_reservation")
    effective = evidence.get("effective_budget")
    if effective is not None:
        available = effective.get("remaining_usd") if isinstance(effective, dict) else None
        if not _finite_number(available) or Decimal(str(available)) < Decimal(maximum_cost):
            raise ExecutionSuspended("staged_effective_budget_below_reservation")
    return {"key_hard_limit_usd": cap, "key_hard_limit_verified": True}


def _runtime_config(config: dict, stage: str, load: int, account: dict) -> dict:
    """File pins plus the stage identity; identical on every resume."""
    runtime = copy.deepcopy(config)
    runtime.update(account, staged_stage=stage, load=load, run_directory=STAGED_STAGES[stage][2],
                   authorization_record_hash=_hash(authorization_record()))
    try:
        require_staged_configuration(runtime, stage=STAGED_STAGES[stage][0])
    except ExecutionBlocked:
        raise ExecutionSuspended("staged_configuration_changed") from None
    return runtime


def validate_staged_live(provider: PinnedProvider, run_dir: Path, execution_config: dict, manifest: dict) -> None:
    """Called by ``run_manifest`` before any staged dispatch or resume."""
    root = execution_run.ROOT
    stage = execution_config.get("staged_stage")
    if stage not in STAGED_STAGES:
        raise ValueError("Staged execution requires a fixed stage")
    dataset, _, directory = STAGED_STAGES[stage]
    require_staged_configuration(execution_config, stage=manifest["dataset"])
    if (manifest["dataset"] != dataset or manifest["load"] != execution_config["load"]
            or manifest["schedule_seed"] != SCHEDULE_SEED
            or Path(run_dir).resolve() != (root / directory).resolve()
            or execution_config.get("authorization_record_hash") != _hash(authorization_record())):
        raise ValueError("Staged execution requires its fixed plan and output directory")
    guard, policy = provider.transport, provider.before_attempt
    session = (root / STAGED_SESSION).resolve()
    profile = get_paid_profile(provider.settings.model, provider.settings.provider_route)
    if (type(provider) is not PinnedProvider or provider.settings.free_only is not False
            or type(guard) is not GuardedTransport
            or type(guard.transport) is not OpenRouterPaidTransport
            or guard.transport._transport is not None
            or guard.transport.model != provider.settings.model
            or guard.transport.provider_route != provider.settings.provider_route):
        raise ValueError("Staged execution requires the guarded paid HTTPS transport; fixtures remain synthetic")
    if (type(policy) is not CappedStagedAttempts or type(policy.counter) is not StagedAttemptLimit
            or type(guard.ledger) is not BudgetLedger or policy.ledger is not guard.ledger
            or guard.ledger.path != session / "budget.jsonl" or guard.ledger.cap != _amount(STAGED_CAP)
            or guard.ledger.currency != "USD" or policy.counter.path != session / "attempts.jsonl"
            or type(guard.quote) is not PaidSmokeQuote or guard.before_dispatch is not None
            or guard.cost_reader is not paid_observed_cost
            or type(guard.limiter) is not RateLimiter or guard.limiter.requests_per_minute != 10
            or guard.limiter.tokens_per_minute != profile["token_bound"] * 10
            or guard.limiter.cold_start is not True or policy.maximum_cost != profile["maximum_cost"]):
        raise ValueError("Staged execution requires the shared durable budget, attempt, quote and rate policy")
    reconcile_staged_history(root, guard.ledger, policy.counter)


def _record_preflight(session: Path, stage: str, evidence: dict) -> None:
    record = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "stage": stage,
              "classification": "account_preflight_not_inference", "evidence": evidence}
    with (session / "preflights.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _completed(directory: Path) -> int:
    path = directory / "calls.jsonl"
    if not path.exists():
        return 0
    return sum(event["event"] == "cell_completed" for event in Journal(path).events)


def _plan_for(root: Path, stage: str) -> tuple[dict, dict | None]:
    dataset, load, _ = STAGED_STAGES[stage]
    record = load_freeze_record(root) if stage == "main" else None
    return build_manifest(dataset, record["selected_load"] if record else load, SCHEDULE_SEED), record


def _money(state: dict) -> dict:
    return {"cap_usd": state["cap"], "known_settled_usd": state["settled_cost"],
            "held_for_unknown_or_pending_usd": state["held"], "available_usd": state["available"],
            "unknown_cost_holds": state["unknown_cost_attempts"] + state["pending_attempts"],
            "maximum_unknown_cost_holds": STAGED_MAX_UNKNOWN_HOLDS, "blocked": state["blocked"]}


def execute_stage(stage: str, *, max_cells: int | None = None) -> dict:
    """Run or resume one stage. Local checks precede every network request."""
    if stage not in STAGED_STAGES:
        raise ExecutionSuspended("staged_unknown_stage")
    if max_cells is not None and (type(max_cells) is not int or max_cells < 0):
        raise ExecutionSuspended("invalid_max_cells")
    root = execution_run.ROOT
    dataset, _, directory = STAGED_STAGES[stage]
    config = load_staged_config(root, dataset=dataset)
    plan, freeze_record = _plan_for(root, stage)
    settings = _settings(config)
    session = root / STAGED_SESSION
    history = _staged_history(root)
    prior = any((session / name).exists() for name in _CONTROL_FILES)
    if (history or prior) and not all((session / name).is_file() for name in _CONTROL_FILES):
        raise ExecutionSuspended("staged_control_history_missing")
    session.mkdir(parents=True, exist_ok=True)
    output = root / directory
    with _writer_lock(session):
        _write_authorization(session, initialize=not prior)
        ledger = BudgetLedger(session / "budget.jsonl", STAGED_CAP, "USD")
        counter = StagedAttemptLimit(session / "attempts.jsonl", initialize=not prior)
        reconcile_staged_history(root, ledger, counter)
        prerequisites = stage_prerequisites(root, stage, plan=plan, settings=settings, freeze_record=freeze_record)
        maximum_cost = get_paid_profile(config["model"], config["provider_route"])["maximum_cost"]
        policy = CappedStagedAttempts(counter, ledger, maximum_cost=maximum_cost)
        if counter.snapshot()["remaining_attempts"] == 0:
            raise ExecutionSuspended("staged_attempt_limit_exhausted")
        if Decimal(ledger.snapshot()["available"]) < Decimal(maximum_cost):
            raise ExecutionSuspended("staged_budget_exhausted")
        if check_paid_smoke_capabilities(config).get("compatible") is not True:
            raise ExecutionSuspended("staged_public_capabilities_not_verified")
        if freeze_record is not None:
            require_remote_freeze_tag(root, freeze_record)
        evidence = paid_account_preflight()
        _record_preflight(session, stage, evidence)
        runtime = _runtime_config(config, stage, plan["load"], account_configuration(config, evidence))
        transport = OpenRouterPaidTransport(settings.model, settings.provider_route)
        limiter = RateLimiter(config["operator_requests_per_minute"], config["operator_tokens_per_minute"])
        guard = GuardedTransport(transport, ledger, limiter, PaidSmokeQuote(), cost_reader=paid_observed_cost)
        provider = PinnedProvider(settings, guard, sleep=time.sleep, before_attempt=policy)
        start = _completed(output)
        while True:
            # run_manifest stops after any cell that logged a failed attempt.
            # Resuming is safe: completed cells are skipped, nothing resampled.
            before = _completed(output)
            allowance = None if max_cells is None else max_cells - (before - start)
            if allowance is not None and allowance <= 0 and before != start:
                break
            result = run_manifest(plan, output, provider, synthetic=False, max_cells=allowance,
                                  execution_config=runtime, freeze=freeze_record)
            if result["pending_cells"] == 0 or result["completed_cells"] == before:
                break
        summary = {key: result[key] for key in (
            "planned_cells", "completed_cells", "pending_cells", "first_action_or_readback_missing",
            "attempted_calls", "successful_calls", "infrastructure_retries", "permitted_reprompts",
            "invalid_first_actions", "known_provider_spend_usd", "unknown_cost_attempts")}
        return {"stage": stage, "directory": directory, "load": plan["load"], **summary,
                "prerequisites": {key: value for key, value in prerequisites.items() if key != "freeze"},
                "money": _money(ledger.snapshot()), "attempts": counter.snapshot()}


def check_ready(stage: str, *, capability_evidence: dict | None = None,
                account_evidence: dict | None = None) -> dict:
    """Read-only readiness. Creates no run, reservation or settlement.

    Without injected evidence this makes one anonymous public-metadata GET and
    one current-key GET (plus ``git ls-remote`` for main). No inference.
    """
    if stage not in STAGED_STAGES:
        raise ExecutionSuspended("staged_unknown_stage")
    root = execution_run.ROOT
    dataset, _, directory = STAGED_STAGES[stage]
    config = load_staged_config(root, dataset=dataset)
    plan, freeze_record = _plan_for(root, stage)
    settings = _settings(config)
    session = root / STAGED_SESSION
    history = _staged_history(root)
    prior = any((session / name).exists() for name in _CONTROL_FILES)
    profile = get_paid_profile(config["model"], config["provider_route"])
    if prior:
        if not all((session / name).is_file() for name in _CONTROL_FILES):
            raise ExecutionSuspended("staged_control_history_missing")
        ledger = BudgetLedger(session / "budget.jsonl", STAGED_CAP, "USD")
        counter = StagedAttemptLimit(session / "attempts.jsonl")
        reconcile_staged_history(root, ledger, counter)
        money, attempts = _money(ledger.snapshot()), counter.snapshot()
    elif history:
        raise ExecutionSuspended("staged_control_history_missing")
    else:
        money = {"cap_usd": STAGED_CAP, "known_settled_usd": "0", "held_for_unknown_or_pending_usd": "0",
                 "available_usd": STAGED_CAP, "unknown_cost_holds": 0,
                 "maximum_unknown_cost_holds": STAGED_MAX_UNKNOWN_HOLDS, "blocked": False}
        attempts = {"maximum_attempts": STAGED_MAX_ATTEMPTS, "reserved_attempts": 0,
                    "remaining_attempts": STAGED_MAX_ATTEMPTS}
    prerequisites = stage_prerequisites(root, stage, plan=plan, settings=settings, freeze_record=freeze_record)
    capabilities = capability_evidence if capability_evidence is not None else check_paid_smoke_capabilities(config)
    if freeze_record is not None:
        require_remote_freeze_tag(root, freeze_record)
    evidence = account_evidence if account_evidence is not None else paid_account_preflight()
    _runtime_config(config, stage, plan["load"], account_configuration(config, evidence))
    output = root / directory
    budget_ready = (not money["blocked"] and Decimal(money["available_usd"]) >= Decimal(profile["maximum_cost"])
                    and money["unknown_cost_holds"] < STAGED_MAX_UNKNOWN_HOLDS)
    ready = capabilities.get("compatible") is True and budget_ready and attempts["remaining_attempts"] > 0
    return {"status": f"ready_for_{stage}_not_executed" if ready else "blocked", "ready": ready,
            "stage": stage, "directory": directory, "dataset": dataset, "load": plan["load"],
            "planned_cells": len(plan["cells"]), "maximum_planned_calls": plan["maximum_planned_calls"],
            "already_completed_cells": _completed(output),
            "model": config["model"], "provider": config["provider"], "reasoning": config["reasoning"],
            "model_route_metadata_verified": capabilities.get("compatible") is True,
            "money": money, "attempts": attempts,
            "next_attempt_upper_bound_usd": profile["maximum_cost"],
            "prerequisites": {key: value for key, value in prerequisites.items() if key != "freeze"},
            "freeze_verified": "freeze" in prerequisites,
            "key_hard_limit_usd": evidence.get("key_hard_limit_usd"),
            "key_limit_remaining_usd": evidence.get("key_limit_remaining_usd"),
            "inference_calls": 0, "execution_started": False}


def status() -> dict:
    """Offline summary of retained staged evidence. No network, no writes."""
    root = execution_run.ROOT
    session = root / STAGED_SESSION
    stages = {}
    for stage, (dataset, load, directory) in STAGED_STAGES.items():
        summary_path = root / directory / "analysis_manifest.json"
        if not summary_path.is_file():
            stages[stage] = {"directory": directory, "state": "not_started"}
            continue
        summary = json.loads(summary_path.read_text("utf-8"))
        stages[stage] = {"directory": directory,
                         "state": "complete" if summary["pending_cells"] == 0 else "partial",
                         **{key: summary.get(key) for key in (
                             "planned_cells", "completed_cells", "pending_cells",
                             "first_action_or_readback_missing", "attempted_calls", "successful_calls",
                             "infrastructure_retries", "invalid_first_actions",
                             "known_provider_spend_usd", "unknown_cost_attempts")}}
    result: dict = {"authorization_id": STAGED_AUTHORIZATION, "stages": stages,
                    "freeze_record_present": (root / STAGED_FREEZE_RECORD).is_file()}
    if all((session / name).is_file() for name in _CONTROL_FILES):
        result["money"] = _money(BudgetLedger(session / "budget.jsonl", STAGED_CAP, "USD").snapshot())
        result["attempts"] = StagedAttemptLimit(session / "attempts.jsonl").snapshot()
    else:
        result["money"] = "session_not_started"
    try:
        result["pilot_decision"] = pilot_decision(root)
    except ExecutionSuspended as error:
        result["pilot_decision"] = str(error)
    return result


def write_freeze_record(tag: str) -> dict:
    """Verify gates and write the freeze record for the current HEAD commit.

    Creates no tag and pushes nothing. The record sits outside the hashed
    inputs, so committing it afterwards does not disturb the freeze.
    """
    from .freeze import FreezeError, prepare_freeze
    root = execution_run.ROOT
    path = root / STAGED_FREEZE_RECORD
    if path.exists():
        raise ExecutionSuspended("staged_execution_freeze_record_already_exists")
    decision = pilot_decision(root)
    commit = _git(root, "rev-parse", "--verify", "HEAD^{commit}").strip()
    smoke8 = root / STAGED_STAGES["smoke8"][2]
    if decision["selected_load"] != 8 or not (smoke8 / "manifest.json").is_file():
        # prepare_freeze then demands the load-8 smoke exactly when selected.
        smoke8 = None
    try:
        record = prepare_freeze(root / STAGED_STAGES["smoke"][2], root / STAGED_STAGES["pilot"][2],
                                smoke8_dir=smoke8, commit=commit, tag=tag)
    except FreezeError as error:
        raise ExecutionSuspended("staged_freeze_preparation_failed:" + str(error)) from None
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return {"status": "freeze_record_written_tag_not_created", "record": STAGED_FREEZE_RECORD,
            "commit": commit, "tag": tag, "selected_load": record["selected_load"],
            "record_hash": record["record_hash"],
            "next_steps": [f"git tag {tag} {commit}", f"git push origin {tag}",
                           "commit and push research/execution_freeze.json and the gate runs",
                           "python -m beyond_label.staged check-ready --stage main"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Staged USD 9 smoke/pilot/freeze/main. Only 'execute' performs inference.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="Offline summary; no network")
    ready = commands.add_parser("check-ready", help="Read-only checks (public metadata and key GET only)")
    ready.add_argument("--stage", choices=list(STAGED_STAGES), required=True)
    execute = commands.add_parser("execute", help="Dispatch paid inference for one stage, or resume it")
    execute.add_argument("--stage", choices=list(STAGED_STAGES), required=True)
    execute.add_argument("--max-cells", type=int)
    freeze = commands.add_parser("freeze", help="Verify gates and write the freeze record for HEAD")
    freeze.add_argument("--tag", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            result = status()
        elif args.command == "check-ready":
            result = check_ready(args.stage)
        elif args.command == "freeze":
            result = write_freeze_record(args.tag)
        else:
            result = {"status": "stage_stopped", **execute_stage(args.stage, max_cells=args.max_cells)}
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0 if result.get("ready", True) else 2
    except httpx.HTTPStatusError as error:
        print(json.dumps({"status": "blocked", "reason": "account_http_error",
                          "http_status": error.response.status_code}))
    except (ExecutionSuspended, AttemptLimitError, ProviderFailure) as error:
        print(json.dumps({"status": "blocked", "reason": str(error)}))
    except (ExecutionBlocked, BudgetError, JournalIntegrityError):
        print(json.dumps({"status": "blocked", "reason": "staged_validation_failed"}))
    except Exception as error:
        print(json.dumps({"status": "blocked", "reason": type(error).__name__}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
