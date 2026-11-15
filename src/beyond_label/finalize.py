"""Offline, trace-verified main-run packaging; never publication or completion.

The five source run files are read into an immutable snapshot. Existing replay,
scoring, analysis, empirical provenance and execution-freeze checks run against
a disposable copy; source runs are never repaired or written. Synthetic bundles
require explicit opt-in and retain their labels. Planned mode has no observations
and emits neither result figures nor invented matched traces.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any

from .analyze import BOOTSTRAP_SEED, analyze_run
from .evidence import export_evidence
from .figures import write_figures
from .oracle import reference_rows
from .run import Journal, build_manifest


SOURCE_FILES = ("manifest.json", "calls.jsonl", "scores.csv", "usage.csv", "analysis_manifest.json")
BUNDLE_FILE = "bundle_manifest.json"
REPRODUCE_TEMPLATE = "python -m beyond_label.finalize --run SOURCE_RUN --output BUNDLE_OUTPUT"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def _files(directory: Path) -> dict[str, bytes]:
    return {path.relative_to(directory).as_posix(): path.read_bytes()
            for path in sorted(directory.rglob("*")) if path.is_file()}


def _read_sources(directory: Path) -> dict[str, bytes]:
    if any(not (directory / name).is_file() or (directory / name).is_symlink() for name in SOURCE_FILES):
        raise ValueError("All five required regular source run files must be present")
    return {name: (directory / name).read_bytes() for name in SOURCE_FILES}


def _destination(output: Path | str, source: Path | None = None) -> Path:
    candidate = Path(output)
    if candidate.is_symlink():
        raise ValueError("Bundle output must not be a symbolic link")
    target = candidate.resolve()
    if source is not None and (target.is_relative_to(source) or source.is_relative_to(target)):
        raise ValueError("Bundle output must not overlap the source run")
    return target


def _publish(stage: Path, output: Path) -> None:
    """Accept an empty target or an identical existing bundle; never overwrite."""
    expected = _files(stage)
    if output.exists():
        if not output.is_dir() or any(path.is_symlink() for path in output.rglob("*")):
            raise ValueError("Existing bundle output is not a regular directory")
        existing = _files(output)
        if existing:
            if existing != expected:
                raise ValueError("Existing output differs; choose a new bundle output directory")
            return
    output.mkdir(parents=True, exist_ok=True)
    for relative, raw in expected.items():
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation also protects against another writer appearing
        # after the preceding destination check.
        with destination.open("xb") as stream:
            stream.write(raw)


def _bundle(stage: Path, *, evidence_kind: str, source_hashes: dict[str, str], **details: Any) -> dict[str, Any]:
    result = {"schema_version": 1, "evidence_kind": evidence_kind, "source_hashes": source_hashes,
              "artifact_hashes": {name: _sha(raw) for name, raw in _files(stage).items()},
              "artifact_hash_scope": "All generated files except bundle_manifest.json, avoiding a circular self-hash",
              "milestone_6_complete": False, "publication_performed": False,
              "scope": "Offline artifact packaging only; paper, human review and submission are not claimed",
              **details}
    _write_json(stage / BUNDLE_FILE, result)
    return result


def _claim_commands(path: Path, *, synthetic: bool) -> None:
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    command = REPRODUCE_TEMPLATE + (" --allow-synthetic" if synthetic else "")
    for row in rows:
        row["regenerate_command"] = command
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _completeness(analysis: dict, execution: dict, journal: Journal) -> dict:
    attempted = {event["cell_id"] for event in journal.events if event["event"] == "attempt_started"}
    missing = [row for row in analysis["cells"] if not row["observed"]]
    # A terminal pre-dispatch configuration failure is missing evidence, even
    # though the guard correctly prevented attempt_started and HTTP dispatch.
    infrastructure = sum(row.get("cell_status") == "completed" for row in missing)
    pending = [row for row in missing if row.get("cell_status") != "completed"]
    unexecuted = sum(row["cell_id"] not in attempted for row in pending)
    unresolved = len(pending) - unexecuted
    continuation_missing = sum(str(row.get("continuation_status", "")).startswith("missing:") for row in analysis["cells"])
    return {"planned_cells": analysis["planned_cells"], "observed_first_action_or_readback_cells": analysis["observed_cells"],
            "completed_cells": execution["completed_cells"], "pending_cells": execution["pending_cells"],
            "unexecuted_cells": unexecuted, "unresolved_attempt_cells": unresolved,
            "infrastructure_missing_cells": infrastructure, "continuation_missing_cells": continuation_missing,
            "missing_first_action_or_readback_cells": len(missing), "missing_reasons": analysis["missing_reasons"],
            "all_cells_terminal": execution["completed_cells"] == analysis["planned_cells"],
            "all_observations_available": not missing and not continuation_missing and execution["pending_cells"] == 0}


def _execution_summary(execution: dict, label: str) -> dict:
    """Carry validated journal accounting into the bundle without new claims."""
    empirical = execution["evidence_kind"] == "empirical"
    complete = execution.get("spend_evidence_complete") if empirical else None
    unknown = execution.get("unknown_cost_attempts") if empirical else None
    total = execution.get("experimental_provider_spend") if empirical and complete is True and unknown == 0 else None
    return {"artifact_label": label, "evidence_kind": execution["evidence_kind"],
            **{key: execution[key] for key in ("attempted_calls", "successful_calls", "infrastructure_retries",
                                               "permitted_reprompts", "continuations", "invalid_first_actions")},
            "confirmed_http_deliveries": None,
            "count_definitions": {
                "attempted_calls": "Journaled attempt starts; do not prove HTTP dispatch",
                "successful_calls": "Responses accepted by the pinned parser; includes invalid model actions and is synthetic when labelled synthetic",
                "confirmed_http_deliveries": "No separate transport-delivery census is reconstructed from attempt-start markers",
                "permitted_reprompts": "Defined re-prompt phases, not necessarily dispatched HTTP calls",
                "continuations": "Defined continuation phases, not necessarily dispatched HTTP calls"},
            "cost": {"evidence_kind": "provider_usage_cost_usd" if empirical else "synthetic_fixture_not_billed",
                     "total_provider_spend_usd": total,
                     "known_provider_spend_usd": execution.get("known_provider_spend_usd") if empirical else None,
                     "spend_evidence_complete": complete, "unknown_cost_attempts": unknown,
                     "accounting_error_attempts": execution.get("accounting_error_attempts") if empirical else None,
                     "nonzero_cost_attempts": execution.get("nonzero_cost_attempts") if empirical else None,
                     "scope": "Provider usage evidence only; unknown totals remain null and synthetic usage is not billed evidence"}}


def finalize_run(run_dir: Path | str, output: Path | str, *, allow_synthetic: bool = False) -> dict[str, Any]:
    """Package a stored MAIN run after existing raw replay and freeze checks.

    Defaults accept empirical run provenance only; the existing replay layer
    verifies the retained freeze rather than trusting a caller's success flag.
    ``SOURCE_RUN`` and ``BUNDLE_OUTPUT`` in CSV commands are explicit path
    placeholders; the bundle manifest records the exact CLI argument list.
    """
    if type(allow_synthetic) is not bool:
        raise ValueError("Synthetic opt-in must be an explicit boolean")
    source = Path(run_dir).resolve()
    destination = _destination(output, source)
    snapshot = _read_sources(source)
    stored = json.loads(snapshot["manifest.json"])
    if not isinstance(stored, dict) or stored.get("plan", {}).get("dataset") != "main":
        raise ValueError("Only a stored main run may be packaged as main results")
    config = stored.get("run_config", {})
    source_kind = config.get("evidence_kind")
    if source_kind == "synthetic" and not allow_synthetic:
        raise ValueError("Synthetic packaging requires --allow-synthetic and cannot produce empirical results")
    if source_kind not in {"synthetic", "empirical"}:
        raise ValueError("Stored main run requires explicit empirical or synthetic provenance")
    with tempfile.TemporaryDirectory(prefix="btl-finalize-") as temporary:
        workspace = Path(temporary)
        copied = workspace / "source"
        copied.mkdir()
        for name, raw in snapshot.items():
            (copied / name).write_bytes(raw)
        analysis = analyze_run(copied, allow_synthetic=allow_synthetic,
                               bootstrap_seed=BOOTSTRAP_SEED, n_resamples=10000)
        if analysis["trace_verification"] != "raw_journal_integrity_and_derived_outputs_verified":
            raise ValueError("Finalization requires raw trace and derived-output verification")
        if source_kind == "synthetic" and analysis["evidence_kind"] != "synthetic":
            raise ValueError("Synthetic source evidence was relabelled")
        if source_kind == "empirical" and analysis["evidence_kind"] not in {"empirical", "unobserved"}:
            raise ValueError("Empirical source contains non-empirical observations")
        export_evidence(copied, allow_synthetic=allow_synthetic)
        write_figures(analysis, copied / "analysis/figures", allow_synthetic=allow_synthetic)
        _claim_commands(copied / "analysis/claim_evidence.csv", synthetic=source_kind == "synthetic")
        stage = workspace / "bundle"
        stage.mkdir()
        shutil.copytree(copied / "analysis", stage / "analysis")
        execution = json.loads(snapshot["analysis_manifest.json"])
        execution_summary = _execution_summary(execution, analysis["artifact_label"])
        _write_json(stage / "execution_summary.json", execution_summary)
        journal = Journal(copied / "calls.jsonl")
        arguments = ["--run", str(source), "--output", str(destination)]
        if allow_synthetic:
            arguments.append("--allow-synthetic")
        freeze = config.get("freeze") or {}
        result = _bundle(stage, evidence_kind=analysis["evidence_kind"],
            source_hashes={name: _sha(raw) for name, raw in snapshot.items()},
            source_run=str(source), source_execution_evidence_kind=source_kind,
            artifact_label=analysis["artifact_label"], trace_verification=analysis["trace_verification"],
            empirical_observations=analysis["observed_cells"] if source_kind == "empirical" else 0,
            completeness=_completeness(analysis, execution, journal),
            execution_summary=execution_summary,
            bootstrap={"seed": BOOTSTRAP_SEED, "resamples": 10000, "unit": "world"},
            freeze_verification="existing_empirical_replay_and_freeze_checks_passed" if source_kind == "empirical" else "not_applicable_synthetic_validation",
            freeze_identity={key: freeze.get(key) for key in ("commit", "tag", "record_hash")} if source_kind == "empirical" else None,
            human_review_claimed=False,
            reproduction={"module": "beyond_label.finalize", "arguments": arguments,
                          "command_template": REPRODUCE_TEMPLATE + (" --allow-synthetic" if source_kind == "synthetic" else ""),
                          "placeholders": ["SOURCE_RUN", "BUNDLE_OUTPUT"]})
        if _read_sources(source) != snapshot:
            raise ValueError("Source run changed during offline finalization")
        _publish(stage, destination)
    return result


def finalize_planned(output: Path | str) -> dict[str, Any]:
    """Write a status-only package: unexecuted cells are not infrastructure loss."""
    destination = _destination(output)
    plan = build_manifest("main")
    main_oracle = next(row for row in reference_rows() if row["condition"] == "MAIN")
    references = {"evidence_kind": "analytic_reference_not_observation", "primary_D": 1.0,
                  "expected_loss_oracle": min(main_oracle[key] for key in ("commit_follow_reports", "inspect_first_named_lot", "inspect_other")),
                  "expected_loss_always_commit_follow_reports": main_oracle["commit_follow_reports"],
                  "expected_loss_uniform_random_single_inspection": (main_oracle["inspect_first_named_lot"] + main_oracle["inspect_other"]) / 2}
    status = {"schema_version": 1, "evidence_kind": "unexecuted", "artifact_label": "PLANNED ONLY — NO OBSERVATIONS",
              "dataset": "main", "planned_cells": plan["initial_calls"], "counts": plan["counts"],
              "seeds": plan["seeds"], "load": plan["load"], "load_status": "planning_default_not_pilot_selected",
              "schedule_seed": plan["schedule_seed"], "execution_freeze_verified": False,
              "maximum_continuations": plan["maximum_continuations"], "maximum_planned_calls": plan["maximum_planned_calls"],
              "additional_calls_accounted_separately": plan["additional_calls_accounted_separately"],
              "observed_cells": 0, "unexecuted_cells": plan["initial_calls"], "infrastructure_missing_cells": 0,
              "primary_effect": None, "ci95": None, "sign_test_p_value": None, "observed_regret": None,
              "oracle_references": references,
              "interpretation": "No empirical or synthetic outcomes supplied; unexecuted planned cells are not observed failures"}
    with tempfile.TemporaryDirectory(prefix="btl-finalize-planned-") as temporary:
        stage = Path(temporary)
        _write_json(stage / "planned_status.json", status)
        with (stage / "status.csv").open("w", encoding="utf-8", newline="") as stream:
            fields = ["artifact_label", "condition", "planned_cells", "observed_cells", "unexecuted_cells", "infrastructure_missing_cells", "status"]
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            for condition, count in plan["counts"].items():
                writer.writerow({"artifact_label": status["artifact_label"], "condition": condition,
                                 "planned_cells": count, "observed_cells": 0, "unexecuted_cells": count,
                                 "infrastructure_missing_cells": 0, "status": "unexecuted"})
        result = _bundle(stage, evidence_kind="unexecuted", source_hashes={}, artifact_label=status["artifact_label"],
                         empirical_observations=0, completeness={"planned_cells": plan["initial_calls"], "completed_cells": 0,
                         "unexecuted_cells": plan["initial_calls"], "infrastructure_missing_cells": 0,
                         "all_cells_terminal": False, "all_observations_available": False},
                         reproduction={"module": "beyond_label.finalize", "arguments": ["--planned", "--output", str(destination)]})
        _publish(stage, destination)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline main-run bundle or planned-only status; no provider calls")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--run", type=Path)
    modes.add_argument("--planned", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-synthetic", action="store_true")
    args = parser.parse_args(argv)
    if args.planned and args.allow_synthetic:
        parser.error("--allow-synthetic is only meaningful with --run")
    result = finalize_planned(args.output) if args.planned else finalize_run(args.run, args.output, allow_synthetic=args.allow_synthetic)
    print(json.dumps({"evidence_kind": result["evidence_kind"], "artifact_label": result["artifact_label"],
                      "bundle_manifest": str(args.output / BUNDLE_FILE), "milestone_6_complete": False,
                      "publication_performed": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
