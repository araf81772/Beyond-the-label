"""Produce engineering diagnostics from retained smoke evidence without calls.

Original five-file run artifacts stay unchanged. This versioned report applies
the current missingness repair after exact collection-version replay succeeds.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay_history import FILES, replay_historical
from beyond_label.run import Journal, _inputs, _score_cell


def diagnose(root: Path, run_dir: Path) -> dict:
    root, run_dir = root.resolve(), run_dir.resolve()
    proof = replay_historical(root, run_dir)
    raw = {name: (run_dir / name).read_bytes() for name in FILES}
    if any(hashlib.sha256(raw[name]).hexdigest() != proof["artifact_sha256"][name] for name in FILES):
        raise ValueError("Historical evidence changed after source replay")
    manifest = json.loads(raw["manifest.json"])
    if manifest["plan"]["dataset"] != "smoke":
        raise ValueError("Smoke engineering diagnostics require smoke evidence")
    # These are the only implementation changes being applied in this report.
    # Any changed stimuli, scientific scoring, world data or settings require a
    # separately reviewed diagnostic version, never an implicit reinterpretation.
    prior = manifest["run_config"]["input_hashes"]
    current = _inputs()
    allowed = {f"src/beyond_label/{name}.py" for name in
               ("run", "provider", "openrouter", "capabilities", "paid_live", "paid_controls")}
    changed = {name for name in set(prior) | set(current) if prior.get(name) != current.get(name)}
    if changed - allowed:
        raise ValueError("Scientific inputs changed beyond the diagnostic repair")
    # The collection-version replay above already validates every saved payload
    # against its original serializer. Current serialization intentionally differs
    # for no-tool readback; never rewrite old payloads or weaken live validation.
    journal = Journal(run_dir / "calls.jsonl")
    starts = [event for event in journal.events if event["event"] == "attempt_started"]
    failures = [event for event in journal.events if event["event"] == "attempt_failed"]
    corrected = [_score_cell(cell, manifest["plan"], journal) for cell in manifest["plan"]["cells"]]
    attempted = {event["cell_id"] for event in starts}
    if any((run_dir / name).read_bytes() != content for name, content in raw.items()):
        raise ValueError("Historical evidence changed during diagnostics")
    return {"classification": "smoke_engineering_diagnostics_not_main_analysis",
            "collection_source_commit": proof["source_commit"],
            "raw_trace_sha256": proof["raw_trace_sha256"],
            "scorer_sha256": hashlib.sha256((root / "src/beyond_label/run.py").read_bytes()).hexdigest(),
            "changed_implementation_paths": sorted(changed),
            "historical_replay_verified": True, "original_files_unchanged": True,
            "planned_cells": len(corrected), "attempted_cells": len(attempted),
            "never_attempted_cells": len(corrected) - len(attempted),
            "attempts": len(starts), "successful_calls": proof["summary"]["successful_calls"],
            "completed_cells": proof["summary"]["completed_cells"],
            "pending_cells": proof["summary"]["pending_cells"],
            "corrected_missingness_counts": dict(Counter(row["missing_reason"] for row in corrected)),
            "observed_failures": [{key: event.get(key) for key in
                ("cell_id", "phase", "attempt", "reason", "http_status")} for event in failures],
            "latency_interpretation": "end-to-end guarded attempt; includes operator pacing wait",
            "known_router_and_upstream_cost_usd": proof["summary"]["known_provider_spend_usd"],
            "cost_evidence_complete": proof["summary"]["spend_evidence_complete"],
            "unknown_cost_attempts": proof["summary"]["unknown_cost_attempts"],
            "empirical_observations": proof["summary"]["empirical_observations"],
            "regenerate_command": "python scripts/smoke_diagnostics.py --run " + run_dir.relative_to(root).as_posix()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "research/checks/paid_smoke_failure_audit.json")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to((ROOT / "runs").resolve()):
        raise ValueError("Diagnostics must not overwrite original run evidence")
    result = diagnose(ROOT, args.run)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
