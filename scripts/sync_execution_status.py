"""Bring two bookkeeping fields in research/milestones.json up to date.

``experimental_calls`` is set to the number of journaled ``attempt_started``
events across retained empirical runs, counting an approved composite main only
once while keeping its original prefix as a historical snapshot.
``execution_freeze`` points at the staged scientific freeze record once it
exists. The child also requires its separately verified operational freeze.
Both bookkeeping fields are then checked by
``scripts/verify_audit.py`` against the raw evidence, so this script cannot make
an incorrect claim pass: it only saves typing the count by hand.

No network, no credentials, no change to any run file. Milestone statuses are
left for a person to update.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from beyond_label.gates import STAGED_FREEZE_RECORD  # noqa: E402
from main_continuation_reporting import continuation_evidence  # noqa: E402


def count_attempts(root: Path) -> dict[str, int]:
    counts = {}
    continuation = continuation_evidence(root)
    manifests = sorted((root / "runs").glob("**/manifest.json"))
    if continuation is not None:
        manifests.append(root / continuation["directory"] / "manifest.json")
    for manifest in manifests:
        relative = manifest.parent.relative_to(root).as_posix()
        if continuation is not None and relative == continuation["parent_directory"]:
            continue
        stored = json.loads(manifest.read_text("utf-8"))
        if stored.get("run_config", {}).get("evidence_kind") != "empirical":
            continue
        journal = manifest.parent / "calls.jsonl"
        starts = 0
        for line in journal.read_bytes().splitlines():
            starts += json.loads(line).get("event") == "attempt_started"
        counts[relative] = starts
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Report only; write nothing")
    args = parser.parse_args()
    path = ROOT / "research/milestones.json"
    milestones = json.loads(path.read_text("utf-8"))
    counts = count_attempts(ROOT)
    total = sum(counts.values())
    freeze = STAGED_FREEZE_RECORD if (ROOT / STAGED_FREEZE_RECORD).is_file() else milestones.get("execution_freeze")
    changed = milestones.get("experimental_calls") != total or milestones.get("execution_freeze") != freeze
    report = {"attempts_by_run": counts, "experimental_calls": total, "execution_freeze": freeze,
              "previous_experimental_calls": milestones.get("experimental_calls"),
              "previous_execution_freeze": milestones.get("execution_freeze"),
              "written": bool(changed and not args.check)}
    if "continuations/staged_main_52_20261116" in counts:
        report["main_counting_scope"] = "approved composite counted once; immutable parent prefix excluded from the sum"
        report["historical_main_snapshot"] = "runs/staged_main"
    if changed and not args.check:
        milestones["experimental_calls"] = total
        milestones["execution_freeze"] = freeze
        path.write_text(json.dumps(milestones, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
