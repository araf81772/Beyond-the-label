"""Explicitly approved 52-cell continuation; the scientific freeze is immutable.

The parent is an immutable snapshot. A child copies its journal prefix once and
appends only the eligible suffix. Its original run_config is a scientific replay
contract; explicit top-level metadata identifies the effective operational rule.
Nothing executes on import. Only the ``execute`` command permits inference.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from beyond_label import run as frozen_run
from beyond_label import staged
from beyond_label.attempts import ExecutionSuspended
from beyond_label.budget import BudgetLedger
from beyond_label.capabilities import check_paid_smoke_capabilities
from beyond_label.controls import GuardedTransport
from beyond_label.environment import CREDENTIAL_NAMES, load_local_credentials
from beyond_label.openrouter import OpenRouterPaidTransport, paid_account_preflight
from beyond_label.paid_controls import PaidSmokeQuote, paid_observed_cost
from beyond_label.paid_profile import get_paid_profile
from beyond_label.provider import PinnedProvider
from beyond_label.rate_limit import RateLimiter
from continuation_pacing import InferencePacer, paced_openrouter_clients
from main_continuation_accounting import (ApprovedHoldsPolicy, load_approval,
                                         reconcile_composite, verify_baseline)

CHILD = "continuations/staged_main_52_20261116"
APPROVAL = "research/main_continuation_approval.json"
OPERATIONAL_FREEZE = "research/main_continuation_operational_freeze.json"
OPERATIONAL_TAG = "btl-main52-operations-v1"
POLICY = "review_exact_40_holds_stop_on_any_new_unknown"
EXECUTION_ROOT = Path("C:/Users/tonmo/CodexRuns/beyond-the-label-v1-main-20261116")


def _require(condition, reason):
    if not condition:
        raise ExecutionSuspended(reason)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _git(root, *args):
    return staged._git(root, *args)


def _read_json(path):
    from beyond_label.budget import _unique_object
    return json.loads(path.read_bytes(), object_pairs_hook=_unique_object)


def _operation_inputs(root):
    paths = [*root.glob("scripts/*.py"), *root.glob("tests/*.py"), root / APPROVAL]
    return {p.relative_to(root).as_posix(): _sha(p.read_bytes()) for p in sorted(paths)}


def _committed_inputs(root, commit, hashes):
    """Read blobs in one Git process; never inherit credentials into Git."""
    environment = {k: v for k, v in os.environ.items() if k not in CREDENTIAL_NAMES}
    environment.update(GIT_TERMINAL_PROMPT="0", GIT_NO_LAZY_FETCH="1")
    names = sorted(hashes)
    query = "".join(f"{commit}:{name}\n" for name in names).encode("ascii")
    try:
        result = subprocess.run(["git", "cat-file", "--batch"], input=query,
                                cwd=root, env=environment, capture_output=True, timeout=90)
        _require(result.returncode == 0, "operational_committed_inputs_unavailable")
        offset = 0
        for name in names:
            end = result.stdout.index(b"\n", offset)
            header = result.stdout[offset:end].split()
            _require(len(header) == 3 and header[1] == b"blob", "operational_committed_input_missing")
            length = int(header[2]); offset = end + 1
            raw = result.stdout[offset:offset + length]
            _require(len(raw) == length and result.stdout[offset + length:offset + length + 1] == b"\n"
                     and _sha(raw) == hashes[name], "operational_committed_input_changed")
            offset += length + 1
        _require(offset == len(result.stdout), "operational_git_response_invalid")
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        raise ExecutionSuspended("operational_committed_inputs_unavailable") from None


def prepare_operational_freeze(commit, tag):
    """Return a new operational proof, without writing a file or creating a tag."""
    root = ROOT.resolve()
    _require(re.fullmatch(r"[0-9a-f]{40}", commit or "") is not None
             and tag == OPERATIONAL_TAG, "invalid_operational_freeze_identity")
    approval = load_approval(root)
    verify_baseline(root)
    _require(not (root / CHILD).exists(), "continuation_already_initialized")
    hashes = _operation_inputs(root)
    _committed_inputs(root, commit, hashes)
    record = {"schema_version": 1, "classification": "approved_operational_continuation_freeze",
              "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
              "source_commit": commit, "tag": tag, "input_hashes": hashes,
              "approval_sha256": _sha((root / APPROVAL).read_bytes()),
              "scientific_freeze_record_hash": approval["scientific_freeze_record_hash"],
              "baseline_boundary_report_hash": approval["baseline_boundary_report_hash"],
              "child_directory": CHILD, "continuation_id": approval["continuation_id"],
              "effective_policy": POLICY, "scientific_design_changed": False}
    record["record_hash"] = frozen_run._hash(record)
    return record


def verify_operational_freeze(root, require_remote=False):
    root = Path(root).resolve()
    approval = load_approval(root)
    record = _read_json(root / OPERATIONAL_FREEZE)
    _require(record.get("record_hash") == frozen_run._hash({k: v for k, v in record.items() if k != "record_hash"}),
             "operational_freeze_hash_mismatch")
    _require(record.get("schema_version") == 1
             and record.get("classification") == "approved_operational_continuation_freeze"
             and record.get("tag") == OPERATIONAL_TAG
             and re.fullmatch(r"[0-9a-f]{40}", record.get("source_commit", "")) is not None
             and record.get("child_directory") == CHILD
             and record.get("continuation_id") == approval["continuation_id"]
             and record.get("effective_policy") == POLICY
             and record.get("scientific_design_changed") is False
             and record.get("scientific_freeze_record_hash") == approval["scientific_freeze_record_hash"]
             and record.get("baseline_boundary_report_hash") == approval["baseline_boundary_report_hash"]
             and record.get("approval_sha256") == _sha((root / APPROVAL).read_bytes())
             and record.get("input_hashes") == _operation_inputs(root), "operational_freeze_contract_changed")
    _committed_inputs(root, record["source_commit"], record["input_hashes"])
    _require(_git(root, "rev-parse", record["tag"] + "^{commit}").strip() == record["source_commit"],
             "operational_freeze_tag_mismatch")
    if require_remote:
        listing = _git(root, "ls-remote", "--tags", "origin", "refs/tags/" + record["tag"],
                       "refs/tags/" + record["tag"] + "^{}")
        _require(record["source_commit"] in {line.split("\t")[0] for line in listing.splitlines()},
                 "operational_freeze_tag_not_on_origin")
    return record


def _child_metadata(root, record):
    from verify_main_continuation import MAIN_FILES
    return {"continuation_id": record["continuation_id"], "approval_sha256": record["approval_sha256"],
            "operational_freeze_record_hash": record["record_hash"],
            "operational_source_commit": record["source_commit"], "parent_directory": "runs/staged_main",
            "parent_artifact_sha256": {name: value[1] for name, value in MAIN_FILES.items()},
            "inherited_journal_bytes": MAIN_FILES["calls.jsonl"][0], "inherited_journal_events": 4461,
            "inherited_journal_sha256": MAIN_FILES["calls.jsonl"][1], "effective_policy": POLICY,
            "base_contract_scope": "scientific_replay_only_operational_exception_governs_dispatch"}


def verify_child_metadata(root, record=None):
    root = Path(root).resolve()
    record = record or verify_operational_freeze(root)
    parent = _read_json(root / "runs/staged_main/manifest.json")
    stored = _read_json(root / CHILD / "manifest.json")
    expected = {**parent, "continuation": _child_metadata(root, record)}
    _require(stored == expected, "continuation_manifest_metadata_changed")
    return stored


def _initialize_child(root, record):
    child = root / CHILD
    if child.exists():
        return verify_child_metadata(root, record)
    parent = root / "runs/staged_main"
    stored = {**_read_json(parent / "manifest.json"), "continuation": _child_metadata(root, record)}
    # An interrupted initialization is not automatically repaired or overwritten.
    child.mkdir(parents=True, exist_ok=False)
    for name, raw in (("manifest.json", (json.dumps(stored, indent=2) + "\n").encode()),
                      ("calls.jsonl", (parent / "calls.jsonl").read_bytes())):
        with (child / name).open("xb") as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return stored


def execute_pending(plan, journal, provider, eligible_cell_ids, max_cells=None):
    """Execute the approved suffix with frozen task logic; never resample cells."""
    _require(max_cells is None or type(max_cells) is int and max_cells >= 0, "invalid_max_cells")
    planned = [c["cell_id"] for c in plan["cells"]]
    _require(eligible_cell_ids == planned[652:] and len(eligible_cell_ids) == 52,
             "continuation_eligible_schedule_changed")
    completed = {e["cell_id"] for e in journal.events if e["event"] == "cell_completed"}
    _require(set(planned[:652]) <= completed, "continuation_parent_completion_missing")
    count = 0
    for cell in plan["cells"][652:]:
        if cell["cell_id"] in completed:
            continue
        if max_cells is not None and count >= max_cells:
            break
        before = len(journal.events)
        frozen_run._execute_cell(cell, plan, journal, provider)
        count += 1
        _require(not any(e.get("accounting_error") for e in journal.events[before:]),
                 "continuation_accounting_reconciliation_required")
        if type(provider.before_attempt) is ApprovedHoldsPolicy:
            provider.before_attempt.check(for_dispatch=False)
    return count


def _verify_live(provider, root, profile):
    guard, policy = provider.transport, provider.before_attempt
    session = root / staged.STAGED_SESSION
    _require(type(provider) is PinnedProvider and type(guard) is GuardedTransport
             and type(guard.transport) is OpenRouterPaidTransport and guard.transport._transport is None
             and guard.transport.model == provider.settings.model
             and guard.transport.provider_route == provider.settings.provider_route
             and provider.settings.free_only is False, "continuation_requires_canonical_paid_transport")
    _require(type(policy) is ApprovedHoldsPolicy and type(policy.counter) is staged.StagedAttemptLimit
             and type(guard.ledger) is BudgetLedger and policy.ledger is guard.ledger
             and guard.ledger.path == session / "budget.jsonl" and str(guard.ledger.cap) == "9"
             and guard.ledger.currency == "USD" and policy.counter.path == session / "attempts.jsonl"
             and type(guard.quote) is PaidSmokeQuote and guard.before_dispatch is None
             and guard.cost_reader is paid_observed_cost and type(guard.limiter) is RateLimiter
             and guard.limiter.requests_per_minute == 10
             and guard.limiter.tokens_per_minute == profile["token_bound"] * 10
             and guard.limiter.cold_start is True and policy.maximum_cost == profile["maximum_cost"],
             "continuation_requires_canonical_shared_controls")


def execute(max_cells=None, preflight_only=False):
    root = ROOT.resolve()
    _require(root == EXECUTION_ROOT.resolve(), "continuation_requires_designated_execution_clone")
    _require(frozen_run.ROOT.resolve() == root, "continuation_source_checkout_mismatch")
    _require(type(preflight_only) is bool and (max_cells is None or type(max_cells) is int and max_cells >= 0),
             "invalid_continuation_request")
    approval = load_approval(root)
    verify_baseline(root)
    record = verify_operational_freeze(root, require_remote=True)
    parent = _read_json(root / "runs/staged_main/manifest.json")
    plan, base = parent["plan"], parent["run_config"]
    config = staged.load_staged_config(root, dataset="main")
    settings = staged._settings(config)
    _require(settings.model_dump(mode="json") == base["provider_settings"], "continuation_provider_settings_changed")
    staged.stage_prerequisites(root, "main", plan=plan, settings=settings, freeze_record=base["freeze"])
    staged.require_remote_freeze_tag(root, base["freeze"])
    profile = get_paid_profile(settings.model, settings.provider_route)
    session = root / staged.STAGED_SESSION
    with frozen_run._writer_lock(session):
        ledger = BudgetLedger(session / "budget.jsonl", "9", "USD")
        counter = staged.StagedAttemptLimit(session / "attempts.jsonl")
        policy = ApprovedHoldsPolicy(counter, ledger, maximum_cost=profile["maximum_cost"])
        reconciliation = reconcile_composite(root, ledger, counter)
        policy.check()
        if (root / CHILD).exists():
            verify_child_metadata(root, record)
        _require(check_paid_smoke_capabilities(config).get("compatible") is True,
                 "continuation_public_route_not_verified")
        account = paid_account_preflight()
        staged.account_configuration(config, account)
        if preflight_only:
            return {"status": "ready_for_approved_continuation_not_executed", "inference_calls": 0,
                    "reconciliation": reconciliation, "account": account,
                    "operational_freeze_record_hash": record["record_hash"]}
        stored = _initialize_child(root, record)
        child = root / CHILD
        preflight = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
                     "classification": "account_preflight_not_inference", "evidence": account}
        with (child / "preflights.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(preflight, sort_keys=True) + "\n"); stream.flush(); os.fsync(stream.fileno())
        guard = GuardedTransport(OpenRouterPaidTransport(settings.model, settings.provider_route), ledger,
                                 RateLimiter(10, profile["token_bound"] * 10), PaidSmokeQuote(),
                                 cost_reader=paid_observed_cost)
        provider = PinnedProvider(settings, guard, sleep=time.sleep, before_attempt=policy)
        _verify_live(provider, root, profile)
        journal = frozen_run.Journal(child / "calls.jsonl")
        frozen_run._validate_journal(journal, plan, stored["run_config"])
        try:
            with paced_openrouter_clients(InferencePacer()):
                execute_pending(plan, journal, provider, approval["eligible_cell_ids"], max_cells)
        finally:
            frozen_run.rebuild_outputs(child)
        final = reconcile_composite(root, ledger, counter)
        policy.check(for_dispatch=False)
        return {"status": "continuation_completed" if len({e['cell_id'] for e in journal.events
                    if e['event'] == 'cell_completed'}) == 704 else "continuation_partial",
                "directory": CHILD, "reconciliation": final,
                "analysis_manifest": _read_json(child / "analysis_manifest.json")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare-freeze"); prepare.add_argument("--commit", required=True)
    prepare.add_argument("--tag", default=OPERATIONAL_TAG)
    sub.add_parser("check-ready")
    execute_parser = sub.add_parser("execute"); execute_parser.add_argument("--max-cells", type=int)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare-freeze":
            result = prepare_operational_freeze(args.commit, args.tag)
            with (ROOT / OPERATIONAL_FREEZE).open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(result, indent=2) + "\n")
        else:
            load_local_credentials()
            result = execute(max_cells=getattr(args, "max_cells", None), preflight_only=args.command == "check-ready")
        print(json.dumps(result, indent=2, sort_keys=True)); return 0
    except ExecutionSuspended as error:
        print(json.dumps({"status": "blocked", "reason": str(error)})); return 2


if __name__ == "__main__":
    raise SystemExit(main())
