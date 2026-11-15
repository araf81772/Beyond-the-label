"""Package the completed approved main continuation using frozen analysis code.

Adds its actual operational provenance without modifying the scientific freeze,
parent source, child source or historical partial results. No inference occurs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from main_continuation_reporting import continuation_evidence  # noqa: E402

COMMAND = "python scripts/finalize_main_continuation.py --output BUNDLE_OUTPUT"


def finalize_continuation(root: Path = ROOT, output: Path | None = None) -> dict:
    root = Path(root).resolve()
    evidence = continuation_evidence(root)
    if evidence is None:
        raise ValueError("An approved main continuation is required")
    accounting = evidence["accounting"]
    if accounting["completed_cells"] != 704 or accounting["pending_cells"] != 0:
        raise ValueError("Cannot package an unfinished continuation as the completed main bundle")
    destination = (Path(output) if output is not None else root / "results/staged_main_complete").resolve()
    partial = root / "results/staged_main"
    if destination.is_relative_to(partial) or partial.is_relative_to(destination):
        raise ValueError("Output must not overlap retained partial results")
    for retained in (root / "runs", root / "continuations"):
        if destination.is_relative_to(retained) or retained.is_relative_to(destination):
            raise ValueError("Output must not overlap retained run evidence")
    from beyond_label.finalize import finalize_run, _files, _publish, _write_json

    with tempfile.TemporaryDirectory(prefix="btl-continuation-finalize-") as temporary:
        stage = Path(temporary) / "bundle"
        result = finalize_run(root / evidence["directory"], stage)
        _write_json(stage / "continuation_provenance.json", {
            "classification": "approved_operational_continuation_of_unchanged_scientific_sample",
            "parent_counted_once": True, "original_scientific_freeze_unchanged": True,
            "old_unknown_holds_released": False, "human_review_claimed": False,
            **evidence,
        })
        claims = stage / "analysis/claim_evidence.csv"
        with claims.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            fields, rows = reader.fieldnames, list(reader)
        for row in rows:
            row["regenerate_command"] = COMMAND
        with claims.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        result["continuation_provenance"] = evidence
        result["reproduction"] = {"script": "scripts/finalize_main_continuation.py",
                                  "arguments": ["--output", str(destination)],
                                  "command_template": COMMAND, "placeholders": ["BUNDLE_OUTPUT"]}
        result["artifact_hashes"] = {name: hashlib.sha256(raw).hexdigest()
                                     for name, raw in _files(stage).items() if name != "bundle_manifest.json"}
        _write_json(stage / "bundle_manifest.json", result)
        if continuation_evidence(root) != evidence:
            raise ValueError("Continuation evidence changed during offline finalization")
        _publish(stage, destination)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/staged_main_complete")
    args = parser.parse_args(argv)
    result = finalize_continuation(ROOT, args.output)
    print(json.dumps({"output": str(args.output), "completeness": result["completeness"],
                      "milestone_6_complete": False, "publication_performed": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
