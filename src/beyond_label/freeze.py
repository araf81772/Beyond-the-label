"""Read-only execution-freeze preparation and verification.

This module never calls a provider, creates a Git commit/tag, writes a freeze
record, or claims human review. Raw gate artifacts are replayed in temporary
directories; source traces remain untouched. A prepared record is not a pushed
tag. The caller must perform and record the separately authorized Git delivery.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any

from .gates import STAGED_AUTHORIZATION, pilot_thresholds
from .pilot import REQUIRED_FILES, summarize_pilot
from .provider import ProviderSettings
from .run import ROOT, _hash, _inputs, build_manifest, rebuild_outputs


class FreezeError(ValueError):
    """Fixed reasons only; never copy raw evidence or process exception text."""


GitResolver = Callable[[str, str | None], str | bytes]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _identity(commit: Any, tag: Any) -> None:
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise FreezeError("freeze_commit_must_be_full_lowercase_sha1")
    if (not isinstance(tag, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", tag)
            or ".." in tag or "//" in tag or tag.endswith(("/", "."))
            or any(part.startswith(".") or part.endswith(".lock") for part in tag.split("/"))):
        raise FreezeError("invalid_freeze_tag")


def _repo_path(value: Path | str, *, under_runs: bool = False) -> tuple[Path, str]:
    path = Path(value)
    path = (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    try:
        relative = path.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        raise FreezeError("freeze_evidence_must_stay_inside_repository") from None
    if under_runs and not relative.startswith("runs/"):
        raise FreezeError("gate_evidence_must_be_under_repository_runs")
    return path, relative


def _git_resolve(ref: str, path: str | None = None) -> str | bytes:
    """Read only: dereference a local tag/commit or read one committed blob."""
    command = (["git", "rev-parse", "--verify", f"{ref}^{{commit}}"] if path is None
               else ["git", "show", f"{ref}:{path}"])
    try:
        environment = {**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0"}
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=30, check=False, env=environment)
    except (OSError, subprocess.SubprocessError):
        raise FreezeError("local_git_evidence_unavailable") from None
    if result.returncode:
        raise FreezeError("local_git_evidence_unavailable")
    if path is not None:
        return result.stdout
    try:
        return result.stdout.decode("ascii").strip()
    except UnicodeError:
        raise FreezeError("invalid_local_git_identity") from None


def _settings(value: Any) -> dict:
    try:
        return (value if isinstance(value, ProviderSettings) else ProviderSettings.model_validate(value)).model_dump(mode="json")
    except (TypeError, ValueError):
        raise FreezeError("invalid_frozen_provider_settings") from None


def _read_artifacts(directory: Path) -> dict[str, bytes]:
    raw = {}
    for name in REQUIRED_FILES:
        file = directory / name
        if not file.is_file() or file.resolve().parent != directory.resolve():
            raise FreezeError("gate_requires_five_local_run_artifacts")
        raw[name] = file.read_bytes()
    return raw


def _verified_run(directory: Path | str, dataset: str, load: int, inputs: dict) -> dict:
    directory, relative = _repo_path(directory, under_runs=True)
    raw = _read_artifacts(directory)
    try:
        stored = json.loads(raw["manifest.json"])
        plan, config = stored["plan"], stored["run_config"]
    except (ValueError, KeyError, TypeError):
        raise FreezeError("invalid_gate_manifest") from None
    if not isinstance(config, dict) or config.get("evidence_kind") != "empirical":
        raise FreezeError("freeze_requires_empirical_gate_evidence")
    if not isinstance(config.get("execution_config"), dict) or not config["execution_config"]:
        raise FreezeError("gate_execution_provenance_missing")
    settings = _settings(config.get("provider_settings"))
    # Paid gate evidence is accepted only under the separately authorized
    # staged allowance; every other empirical gate must still be free-only.
    staged = config["execution_config"].get("authorization_id") == STAGED_AUTHORIZATION
    if staged:
        if (settings.get("free_only") is not False or config["execution_config"].get("free_only") is not False
                or config.get("transport_provenance") != "openrouter_paid_https_v1"):
            raise FreezeError("staged_freeze_requires_captured_paid_settings")
    elif settings.get("free_only") is not True or config["execution_config"].get("free_only") is not True:
        raise FreezeError("free_freeze_requires_captured_free_only_settings")
    if config.get("input_hashes") != inputs:
        raise FreezeError("gate_input_hashes_changed")
    if (not isinstance(plan, dict) or plan.get("dataset") != dataset or plan.get("load") != load
            or plan != build_manifest(dataset, load, plan.get("schedule_seed"))):
        raise FreezeError("gate_manifest_differs_from_complete_design")
    if stored.get("run_config_hash") != _hash({"plan": plan, "config": config}):
        raise FreezeError("gate_configuration_hash_mismatch")
    if not raw["calls.jsonl"]:
        raise FreezeError("gate_has_no_raw_calls")
    with tempfile.TemporaryDirectory(prefix="btl-freeze-replay-") as temporary:
        replay_dir = Path(temporary)
        for name in ("manifest.json", "calls.jsonl"):
            (replay_dir / name).write_bytes(raw[name])
        try:
            replay = rebuild_outputs(replay_dir)
        except (OSError, TypeError, ValueError):
            raise FreezeError("gate_raw_trace_replay_failed") from None
        for name in ("scores.csv", "usage.csv", "analysis_manifest.json"):
            if raw[name] != (replay_dir / name).read_bytes():
                raise FreezeError("gate_derived_outputs_disagree_with_raw_trace")
    count = len(plan["cells"])
    if (replay.get("evidence_kind") != "empirical" or replay.get("planned_cells") != count
            or replay.get("completed_cells") != count or replay.get("pending_cells") != 0
            or replay.get("first_action_or_readback_missing") != 0 or replay.get("missingness")
            or type(replay.get("successful_calls")) is not int or replay["successful_calls"] <= 0):
        raise FreezeError("gate_has_incomplete_empirical_observations")
    # A zero quote or free suffix is not observed billing evidence. Unmatched
    # attempts, missing receipts and local accounting failures must be resolved
    # before a free-only gate can support an execution freeze.
    accounting_counts = ("unknown_cost_attempts", "accounting_error_attempts", "nonzero_cost_attempts")
    spend = replay.get("experimental_provider_spend")
    if staged:
        # Paid costs are provider-reported and nonzero. An attempt whose charge
        # is unknown (for example a retried timeout) stays an explicit unknown:
        # it is counted here, kept as a full hold by the staged ledger, and is
        # never converted into zero. Local accounting failures still block.
        known = replay.get("known_provider_spend_usd")
        if (type(replay.get("accounting_error_attempts")) is not int or replay["accounting_error_attempts"] != 0
                or type(replay.get("unknown_cost_attempts")) is not int or replay["unknown_cost_attempts"] < 0
                or type(replay.get("nonzero_cost_attempts")) is not int
                or type(known) not in (int, float) or known < 0
                or type(replay.get("spend_evidence_complete")) is not bool):
            raise FreezeError("paid_gate_cost_or_accounting_evidence_incomplete")
    elif (replay.get("spend_evidence_complete") is not True
            or any(type(replay.get(key)) is not int or replay[key] != 0 for key in accounting_counts)
            or type(spend) not in (int, float) or spend != 0):
        raise FreezeError("free_gate_cost_or_accounting_evidence_incomplete")
    cells = replay.get("cells")
    if (not isinstance(cells, list) or len(cells) != count
            or {cell.get("cell_id") for cell in cells} != {cell["cell_id"] for cell in plan["cells"]}):
        raise FreezeError("gate_cell_denominators_disagree")
    for cell in cells:
        continuation = cell.get("continuation_status")
        observed = isinstance(continuation, str) and (continuation in {"not_applicable", "committed"}
                                                      or continuation.startswith("invalid:"))
        if cell.get("status") != "completed" or cell.get("missing_reason") or not observed:
            raise FreezeError("gate_has_missing_continuation_or_cell")
    if _read_artifacts(directory) != raw:
        raise FreezeError("gate_evidence_changed_during_verification")
    return {"directory": relative, "dataset": dataset, "load": load,
            "files": {name: _sha(data) for name, data in raw.items()},
            "run_config_hash": stored["run_config_hash"], "plan_hash": _hash(plan),
            "schedule_seed": plan["schedule_seed"], "provider_settings": settings,
            "planned_cells": count, "completed_cells": count,
            "invalid_first_actions": replay.get("invalid_first_actions"),
            "cost_evidence": {key: replay[key] for key in
                              ("spend_evidence_complete", *accounting_counts, "experimental_provider_spend",
                               *(("known_provider_spend_usd",) if staged else ()))}}


def _pilot_decision(directory: Path | str, proof: dict) -> dict:
    try:
        summary = summarize_pilot(directory)
    except (OSError, TypeError, ValueError):
        raise FreezeError("pilot_summary_verification_failed") from None
    if (summary.get("evidence_kind") != "empirical" or summary.get("actual_pilot_verified") is not True
            or summary.get("pilot_observations_complete") is not True
            or summary.get("actual_model_change_decided") is not False):
        raise FreezeError("pilot_is_incomplete_or_requires_model_change")
    counts = summary.get("counts", {})
    required = ("planned_main_pairs", "complete_main_pairs", "planned_numeric_calls", "observed_numeric_calls")
    if any(type(counts.get(key)) is not int or counts[key] != 16 for key in required):
        raise FreezeError("pilot_denominators_must_be_sixteen")
    try:
        decision = pilot_thresholds(counts["fully_correct_main_pairs"], counts["optimal_numeric_calls"])
    except (KeyError, TypeError, ValueError):
        raise FreezeError("invalid_pilot_threshold_counts") from None
    if (decision["repeat_pilot_with_different_model"] or summary.get("actual_selected_load") != decision["selected_load"]
            or summary.get("actual_threshold_evaluation") != {**decision, "actual_pilot_verified": True}):
        raise FreezeError("pilot_floor_or_load_decision_failed")
    if _settings(summary.get("provider_settings")) != proof["provider_settings"]:
        raise FreezeError("pilot_summary_provider_mismatch")
    if summary.get("provenance") != proof["files"]:
        raise FreezeError("pilot_summary_evidence_mismatch")
    return {"fully_correct_main_pairs": counts["fully_correct_main_pairs"],
            "optimal_numeric_calls": counts["optimal_numeric_calls"], "main_pairs": 16, "numeric_calls": 16,
            "selected_load": decision["selected_load"], "load8_smoke_required": decision["load8_smoke_required"]}


def _no_prefreeze_main_calls() -> None:
    for path in (ROOT / "runs").glob("**/manifest.json"):
        try:
            stored = json.loads(path.read_bytes())
        except (OSError, ValueError):
            raise FreezeError("cannot_audit_existing_run_manifest") from None
        if (isinstance(stored, dict) and stored.get("plan", {}).get("dataset") == "main"
                and stored.get("run_config", {}).get("evidence_kind") == "empirical"):
            calls = path.parent / "calls.jsonl"
            if calls.exists() and calls.stat().st_size:
                raise FreezeError("empirical_main_calls_exist_before_freeze")


def _committed_inputs(commit: str, inputs: dict, manifest_path: str, manifest_bytes: bytes,
                      resolver: GitResolver) -> None:
    for path, digest in {**inputs, manifest_path: _sha(manifest_bytes)}.items():
        _repo_path(path)
        try:
            blob = resolver(commit, path)
        except Exception:
            raise FreezeError("committed_freeze_input_unavailable") from None
        if not isinstance(blob, bytes) or _sha(blob) != digest:
            raise FreezeError("committed_freeze_input_hash_mismatch")


def _main_plan(load: int, schedule_seed: int, main_manifest: dict | None,
               main_manifest_path: Path | str | None) -> tuple[dict, str, bytes]:
    expected = build_manifest("main", load, schedule_seed)
    if main_manifest is not None and main_manifest != expected:
        raise FreezeError("main_manifest_differs_from_selected_frozen_design")
    path, relative = _repo_path(main_manifest_path or f"data/plans/main_load{load}.json")
    try:
        raw = path.read_bytes()
        if json.loads(raw) != expected:
            raise FreezeError("stored_main_manifest_differs_from_frozen_design")
    except (OSError, ValueError):
        raise FreezeError("stored_main_manifest_missing_or_mismatched") from None
    return expected, relative, raw


def prepare_freeze(smoke_dir: Path | str, pilot_dir: Path | str, *, smoke8_dir: Path | str | None = None,
                   commit: str, tag: str, main_manifest: dict | None = None,
                   main_manifest_path: Path | str | None = None, git_resolver: GitResolver | None = None) -> dict:
    """Return proof after gate replay and committed-input checks; create nothing.

    The supplied commit must already contain the final inputs/main manifest.
    The record belongs outside the input hash set, avoiding a circular commit
    dependency. A tag need not exist yet; verify_freeze requires it before main.
    """
    _identity(commit, tag)
    _no_prefreeze_main_calls()
    inputs = _inputs()
    smoke = _verified_run(smoke_dir, "smoke", 2, inputs)
    pilot = _verified_run(pilot_dir, "pilot", 2, inputs)
    decision = _pilot_decision(pilot_dir, pilot)
    gates = {"smoke": smoke, "pilot": pilot}
    if decision["selected_load"] == 8:
        if smoke8_dir is None:
            raise FreezeError("selected_load8_requires_additional_real_smoke")
        gates["smoke8"] = _verified_run(smoke8_dir, "smoke", 8, inputs)
    elif smoke8_dir is not None:
        raise FreezeError("unexpected_load8_smoke_for_selected_load2")
    if any(proof["provider_settings"] != pilot["provider_settings"] for proof in gates.values()):
        raise FreezeError("smoke_and_pilot_provider_settings_must_match")
    plan, plan_path, plan_raw = _main_plan(decision["selected_load"], pilot["schedule_seed"],
                                         main_manifest, main_manifest_path)
    _committed_inputs(commit, inputs, plan_path, plan_raw, git_resolver or _git_resolve)
    if _inputs() != inputs:
        raise FreezeError("inputs_changed_during_freeze_preparation")
    for proof in gates.values():
        if {name: _sha(data) for name, data in _read_artifacts(ROOT / proof["directory"]).items()} != proof["files"]:
            raise FreezeError("gate_evidence_changed_during_freeze_preparation")
    _no_prefreeze_main_calls()
    record = {"schema_version": 1, "classification": "prepared_execution_freeze",
              "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
              "commit": commit, "tag": tag, "input_hashes": inputs,
              "main_manifest_path": plan_path, "main_manifest_file_sha256": _sha(plan_raw),
              "main_manifest_hash": _hash(plan), "schedule_seed": plan["schedule_seed"],
              "provider_settings": pilot["provider_settings"], "selected_load": decision["selected_load"],
              "pilot_decision": decision, "gate_evidence": gates,
              "real_smoke_passed": True, "real_pilot_passed": True, "hashes_verified": True,
              "no_main_calls_before_preparation": True, "main_call_audit_scope": "repository runs/**/manifest.json",
              "human_review_verified": False, "human_review_scope": "No human H1/H2 participation inferred or recorded.",
              "tag_delivery_status": "not_created_or_pushed_by_this_function"}
    record["record_hash"] = _hash(record)
    return record


def verify_freeze(record: Mapping, main_manifest: dict, settings: ProviderSettings | Mapping, *,
                  git_resolver: GitResolver | None = None) -> dict:
    """Revalidate inputs, complete retained gate traces, selected plan and tag.

    Existing main artifacts are allowed here for legitimate resume. The main
    runner separately binds each main run to this immutable record hash.
    """
    if not isinstance(record, Mapping):
        raise FreezeError("invalid_freeze_record")
    record = dict(record)
    if record.get("record_hash") != _hash({key: value for key, value in record.items() if key != "record_hash"}):
        raise FreezeError("freeze_record_hash_mismatch")
    _identity(record.get("commit"), record.get("tag"))
    if (type(record.get("schema_version")) is not int or record["schema_version"] != 1
            or record.get("classification") != "prepared_execution_freeze"
            or type(record.get("selected_load")) is not int or record["selected_load"] not in (2, 8)
            or type(record.get("schedule_seed")) is not int
            or any(record.get(key) is not True for key in ("real_smoke_passed", "real_pilot_passed", "hashes_verified",
                                                          "no_main_calls_before_preparation"))
            or record.get("human_review_verified") is not False):
        raise FreezeError("freeze_record_claims_not_supported")
    try:
        prepared = datetime.fromisoformat(record.get("prepared_at_utc", ""))
        if prepared.tzinfo is None or prepared.utcoffset().total_seconds() != 0:
            raise ValueError
    except (TypeError, ValueError):
        raise FreezeError("freeze_timestamp_must_be_explicit_utc") from None
    inputs = _inputs()
    if inputs != record.get("input_hashes"):
        raise FreezeError("frozen_input_hashes_changed")
    if _settings(settings) != record.get("provider_settings"):
        raise FreezeError("frozen_provider_settings_changed")
    try:
        plan, path, raw = _main_plan(record["selected_load"], record["schedule_seed"], main_manifest,
                                    record["main_manifest_path"])
        if _hash(plan) != record["main_manifest_hash"] or _sha(raw) != record["main_manifest_file_sha256"]:
            raise FreezeError("frozen_main_manifest_hash_mismatch")
        gates = record["gate_evidence"]
        required = {"smoke", "pilot", "smoke8"} if record["selected_load"] == 8 else {"smoke", "pilot"}
        if not isinstance(gates, dict) or set(gates) != required:
            raise FreezeError("frozen_gate_evidence_missing")
        actual = {}
        for name in required:
            actual[name] = _verified_run(gates[name]["directory"], "pilot" if name == "pilot" else "smoke",
                                         8 if name == "smoke8" else 2, inputs)
        if actual != gates or any(proof["provider_settings"] != record["provider_settings"] for proof in actual.values()):
            raise FreezeError("frozen_gate_evidence_changed")
        if _pilot_decision(ROOT / actual["pilot"]["directory"], actual["pilot"]) != record["pilot_decision"]:
            raise FreezeError("frozen_pilot_decision_changed")
    except (KeyError, TypeError):
        raise FreezeError("invalid_freeze_record_structure") from None
    resolver = git_resolver or _git_resolve
    try:
        tagged = resolver(f"refs/tags/{record['tag']}", None)
    except Exception:
        raise FreezeError("freeze_tag_unavailable") from None
    if tagged != record["commit"]:
        raise FreezeError("freeze_tag_commit_mismatch")
    _committed_inputs(record["commit"], inputs, path, raw, resolver)
    if _inputs() != inputs:
        raise FreezeError("inputs_changed_during_freeze_verification")
    return {"verified": True, "commit": record["commit"], "tag": record["tag"], "record_hash": record["record_hash"],
            "scope": "local tag, current/committed inputs, selected main plan and retained empirical gate traces"}
