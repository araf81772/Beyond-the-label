"""Rehearse smoke/pilot/load-8 delivery using only the local scripted fixture.

These artifacts are synthetic infrastructure checks. They cannot satisfy a
real smoke or pilot gate, select the experimental load, or create a freeze.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from beyond_label.pilot import summarize_pilot
from beyond_label.provider import PinnedProvider, ProviderSettings
from beyond_label.run import ScriptedPublicPolicy, build_manifest, rebuild_outputs, run_manifest


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_fixture_result(result: dict, plan: dict) -> None:
    if result["completed_cells"] != plan["initial_calls"]:
        raise ValueError("Synthetic rehearsal did not complete the planned matrix")
    zero_fields = ("pending_cells", "first_action_or_readback_missing", "invalid_first_actions",
                   "infrastructure_retries", "permitted_reprompts")
    if any(result[name] != 0 for name in zero_fields):
        raise ValueError("Deterministic fixture has missing, invalid or unexpected retry/re-prompt outcomes")
    if (result["successful_calls"] != plan["maximum_planned_calls"]
            or result["continuations"] != plan["maximum_continuations"]):
        raise ValueError("Deterministic fixture call counts differ from the expected inspect/commit path")
    if any(cell["continuation_status"] not in {"committed", "not_applicable"}
           for cell in result["cells"]):
        raise ValueError("Deterministic fixture continuation is missing or invalid")


def rehearse(output: Path) -> dict:
    stages = []
    for dataset, load in (("smoke", 2), ("pilot", 2), ("smoke", 8)):
        name = f"synthetic_{dataset}_load{load}"
        directory = output / name
        fixture = ScriptedPublicPolicy()
        provider = PinnedProvider(
            ProviderSettings(model=fixture.model, provider=fixture.provider), fixture
        )
        plan = build_manifest(dataset, load)
        result = run_manifest(plan, directory, provider)
        files = ("manifest.json", "calls.jsonl", "scores.csv", "usage.csv", "analysis_manifest.json")
        before = {name: file_hash(directory / name) for name in files}
        replayed = rebuild_outputs(directory)
        if replayed != result or before != {name: file_hash(directory / name) for name in files}:
            raise ValueError("Synthetic rehearsal replay changed stored evidence")
        calls_before_resume = fixture.calls
        resumed = run_manifest(plan, directory, provider)
        if resumed != result or fixture.calls != calls_before_resume:
            raise ValueError("Completed synthetic rehearsal was resampled")
        if before != {name: file_hash(directory / name) for name in files}:
            raise ValueError("Completed synthetic rehearsal resume changed stored evidence")
        validate_fixture_result(result, plan)
        stages.append({
            "run_directory": name,
            "dataset": dataset,
            "load": load,
            "world_seeds": plan["seeds"],
            "counts": plan["counts"],
            "summary": result,
            "file_hashes": before,
            "raw_trace_preserved": True,
            "offline_regeneration_byte_identical": True,
            "completed_resume_added_calls": 0,
        })
    pilot = summarize_pilot(output / "synthetic_pilot_load2", allow_synthetic=True)
    record = {
        "classification": "SYNTHETIC INFRASTRUCTURE REHEARSAL — NOT A REAL SMOKE OR PILOT",
        "actual_experimental_provider_calls": 0,
        "actual_experimental_api_spend": 0,
        "empirical_observations": 0,
        "actual_selected_load": None,
        "real_smoke_passed": False,
        "real_pilot_passed": False,
        "freeze_created": False,
        "human_trace_review": False,
        "load8_reason": "Unconditional offline coverage of the alternate load; not a pilot selection",
        "stages": stages,
        "pilot_summary": pilot,
        "remaining_blockers": [
            "Synthetic fixtures cannot establish real smoke or pilot completion",
            "Live execution separately requires current authorization and verified provider/account gates",
            "Actual model/load selection and freeze require retained empirical gate evidence",
            "This rehearsal supplies no human-review participation or empirical observations",
        ],
    }
    (output / "rehearsal.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("evaluation/synthetic_m4_rehearsal_env"))
    args = parser.parse_args()
    record = rehearse(args.output)
    print(json.dumps({
        "classification": record["classification"],
        "stage_count": len(record["stages"]),
        "completed_fixture_cells": sum(s["summary"]["completed_cells"] for s in record["stages"]),
        "successful_fixture_calls": sum(s["summary"]["successful_calls"] for s in record["stages"]),
        "actual_experimental_provider_calls": 0,
        "actual_selected_load": None,
        "freeze_created": False,
        "evidence": str(args.output / "rehearsal.json"),
    }, indent=2))


if __name__ == "__main__":
    main()
