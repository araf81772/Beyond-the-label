"""Read-only pilot verification and exact, trace-derived threshold decisions.

Synthetic rehearsals remain explicitly hypothetical. Empirical summaries require
the free-only execution configuration and full raw-journal replay. Neither kind
of summary establishes human participation or independently authorizes a freeze.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any

from .analyze import analyze_rows
from .gates import pilot_thresholds
from .run import build_manifest, rebuild_outputs

REQUIRED_FILES = ("manifest.json", "calls.jsonl", "scores.csv", "usage.csv", "analysis_manifest.json")


def _summarize_verified(analysis: dict[str, Any], replay: dict[str, Any], *,
                        evidence_kind: str = "synthetic") -> dict[str, Any]:
    """Aggregate verified scores; callers must establish provenance by replay."""
    if evidence_kind not in {"synthetic", "empirical"}:
        raise ValueError("Pilot evidence provenance must be synthetic or empirical")
    empirical = evidence_kind == "empirical"
    layouts = analysis["main_by_layout"]
    pairs = [pair for layout in ("separate", "inline") for pair in layouts[layout]["pairs"]]
    numeric = analysis["conditions"]["NUMERIC"]
    if len(pairs) != 16 or numeric["planned"] != 16:
        raise ValueError("Pilot requires 16 MAIN pairs and 16 NUMERIC calls")
    complete_pairs = sum(pair["complete"] for pair in pairs)
    correct_pairs = sum(pair["pair_category"] == "fully_correct" for pair in pairs)
    numeric_optimal = numeric["optimal_over_all_planned"]["successes"]
    continuation_missing = sum(str(row.get("continuation_status", "")).startswith("missing:")
                               for row in analysis["cells"])
    complete = (analysis["missing_cells"] == 0 and replay["pending_cells"] == 0
                and continuation_missing == 0 and complete_pairs == 16 and numeric["observed"] == 16)
    thresholds = pilot_thresholds(correct_pairs, numeric_optimal) if complete else None
    return {
        "schema_version": 1,
        "artifact_label": ("EMPIRICAL PILOT OBSERVATIONS — EXCLUDED FROM MAIN RESULTS" if empirical
                           else "SYNTHETIC PILOT REHEARSAL — NOT A REAL PILOT OR LOAD DECISION"),
        "dataset": "pilot", "load": 2, "seeds": list(range(1000, 1008)),
        "evidence_kind": evidence_kind,
        "empirical_observations": analysis["observed_cells"] if empirical else 0,
        "actual_pilot_verified": empirical and complete,
        "actual_selected_load": thresholds["selected_load"] if empirical and complete else None,
        "actual_model_change_decided": bool(empirical and complete and thresholds["repeat_pilot_with_different_model"]),
        "freeze_eligible": False,
        "verification_scope": "Raw traces and derived counts only; smoke, human review and freeze requirements are separate.",
        "human_review_verified": False,
        "human_review_scope": "No H1/H2 participation is inferred from trace replay or this summary.",
        "counts": {
            "planned_cells": analysis["planned_cells"], "observed_cells": analysis["observed_cells"],
            "missing_cells": analysis["missing_cells"], "pending_cells": replay["pending_cells"],
            "continuation_missing_cells": continuation_missing,
            "invalid_first_actions": replay["invalid_first_actions"],
            "planned_main_pairs": 16, "complete_main_pairs": complete_pairs,
            "fully_correct_main_pairs": correct_pairs,
            "invalid_main_pairs": sum(pair["pair_category"] == "invalid" for pair in pairs),
            "planned_numeric_calls": 16, "observed_numeric_calls": numeric["observed"],
            "optimal_numeric_calls": numeric_optimal, "invalid_numeric_calls": numeric["invalid"],
        },
        "missing_reasons": analysis["missing_reasons"],
        "pilot_observations_complete": complete,
        "hypothetical_threshold_evaluation": thresholds if not empirical else None,
        "actual_threshold_evaluation": ({**thresholds, "actual_pilot_verified": True}
                                        if empirical and complete else None),
        "threshold_status": ("empirical_thresholds_verified" if empirical else "synthetic_hypothetical_only")
                            if complete else "blocked_incomplete_pilot",
        "threshold_note": "Exact 14/16 ceiling and 12/16 floor; invalid actions remain in denominators. "
                          "Incomplete pilots do not select a load or decide a model change.",
    }


def summarize_pilot(run_dir: Path | str, *, allow_synthetic: bool = False) -> dict[str, Any]:
    """Verify all stored inputs/outputs and summarize a pilot without editing it.

    Missing observations are retained and reported, while malformed plans,
    fabricated scores, duplicate journal events and missing evidence files fail.
    """
    run_dir = Path(run_dir)
    missing_files = [name for name in REQUIRED_FILES if not (run_dir / name).is_file()]
    if missing_files:
        raise ValueError("Pilot summary requires all five run artifacts: " + ", ".join(missing_files))
    # Read one consistent byte snapshot, then verify that snapshot in isolation.
    raw = {name: (run_dir / name).read_bytes() for name in REQUIRED_FILES}
    stored = json.loads(raw["manifest.json"])
    plan = stored.get("plan", {})
    if plan.get("dataset") != "pilot" or plan.get("load") != 2:
        raise ValueError("Pilot summary requires the eight-world load-2 pilot manifest")
    if plan != build_manifest("pilot", 2, plan.get("schedule_seed")):
        raise ValueError("Pilot manifest differs from the complete deterministic design")
    config = stored.get("run_config", {})
    evidence_kind = config.get("evidence_kind")
    if evidence_kind == "empirical":
        execution_config = config.get("execution_config")
        provider_settings = config.get("provider_settings")
        if (not isinstance(execution_config, dict) or not execution_config
                or not isinstance(provider_settings, dict) or provider_settings.get("free_only") is not True):
            raise ValueError("Empirical pilot provenance requires a free-only execution configuration")
        # rebuild_outputs below validates the captured execution gates, settings,
        # journal and hashes; these metadata checks alone do not establish it.
    elif evidence_kind != "synthetic":
        raise ValueError("Pilot evidence provenance must be synthetic or empirical")
    if evidence_kind == "synthetic" and not allow_synthetic:
        raise ValueError("Synthetic pilot rehearsal requires explicit allow_synthetic=True")
    with tempfile.TemporaryDirectory(prefix="btl-pilot-verification-") as temporary:
        verification = Path(temporary)
        for name in ("manifest.json", "calls.jsonl"):
            (verification / name).write_bytes(raw[name])
        replay = rebuild_outputs(verification)
        for name in ("scores.csv", "usage.csv", "analysis_manifest.json"):
            if raw[name] != (verification / name).read_bytes():
                raise ValueError("Stored pilot outputs differ from raw-trace regeneration")
        with (verification / "scores.csv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        analysis = analyze_rows(rows, {**plan, "evidence_kind": evidence_kind}, allow_synthetic=allow_synthetic)
    if any((run_dir / name).read_bytes() != data for name, data in raw.items()):
        raise ValueError("Pilot artifacts changed during verification")
    result = _summarize_verified(analysis, replay, evidence_kind=evidence_kind)
    result["trace_verification"] = "raw_journal_integrity_and_all_derived_outputs_verified"
    result["provenance"] = {name: hashlib.sha256(data).hexdigest() for name, data in raw.items()}
    result["run_config_hash"] = stored["run_config_hash"]
    result["provider_settings"] = stored["run_config"]["provider_settings"]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only offline pilot summary; no provider calls or freeze")
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--allow-synthetic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(summarize_pilot(args.run_dir, allow_synthetic=args.allow_synthetic), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
