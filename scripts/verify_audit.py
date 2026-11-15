"""Verify source integrity and audit evidence as milestones advance.

Historical M1 absence claims are checked against its retained baseline. Live
status is checked against present files rather than freezing the project at M1.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from beyond_label.environment import CredentialLoadError, load_local_credentials
from replay_history import replay_historical
SOURCE_SHA256 = "f732a0d815ae7f6f42e9eacb4e311b53ed8187abf9e3c48b79c476dfc202838b"


def validate_execution_evidence(root: Path, milestones: dict) -> dict:
    """Reconcile status with retained raw evidence without changing run files.

    experimental_calls means recorded request attempts, not confirmed HTTP
    deliveries. Pre-dispatch allowance reservations are a different quantity.
    Synthetic directories never contribute to empirical counts or completion.
    """
    from beyond_label.budget import _unique_object
    from beyond_label.freeze import verify_freeze
    from beyond_label.run import build_manifest, rebuild_outputs, _inputs

    root = root.resolve()
    runs_root = root / "runs"
    if not runs_root.resolve().is_relative_to(root):
        raise ValueError("Execution inventory must stay inside the repository")
    manifests = sorted(runs_root.glob("**/manifest.json"))
    calls = sorted(runs_root.glob("**/calls.jsonl"))
    if {p.parent for p in manifests} != {p.parent for p in calls}:
        raise ValueError("Execution inventory has unmatched manifests or journals")
    inventory = {"recorded_request_attempts": 0, "successful_calls": 0,
                 "infrastructure_retries": 0, "empirical_runs": [],
                 "synthetic_run_directories": [], "freeze": None,
                 "call_count_scope": "recorded attempt_started events; not confirmed HTTP deliveries"}
    trace_hashes = set()
    main_freeze_hashes = set()
    required = ("manifest.json", "calls.jsonl", "scores.csv", "usage.csv", "analysis_manifest.json")
    for path in manifests:
        directory = path.parent
        if not directory.resolve().is_relative_to(runs_root.resolve()):
            raise ValueError("Execution evidence escapes repository runs")
        if any(not (directory / name).is_file()
               or (directory / name).resolve().parent != directory.resolve() for name in required):
            raise ValueError("Execution audit requires all five retained run artifacts")
        raw = {name: (directory / name).read_bytes() for name in required}
        stored = json.loads(raw["manifest.json"], object_pairs_hook=_unique_object)
        if not isinstance(stored, dict) or not isinstance(stored.get("run_config"), dict):
            raise ValueError("Execution inventory requires a wrapped run manifest")
        kind = stored.get("run_config", {}).get("evidence_kind")
        relative = directory.relative_to(root).as_posix()
        if kind not in {"empirical", "synthetic"}:
            raise ValueError("Execution inventory requires explicit evidence labels")
        digest = hashlib.sha256(raw["calls.jsonl"]).hexdigest()
        if kind == "empirical" and raw["calls.jsonl"] and digest in trace_hashes:
            raise ValueError("Duplicate empirical journal cannot count as another run")
        historical = None
        if stored["run_config"].get("input_hashes") != _inputs():
            historical = replay_historical(root, directory)
            summary = historical["summary"]
        else:
            with tempfile.TemporaryDirectory(prefix="btl-audit-replay-") as temporary:
                replay = Path(temporary)
                for name in ("manifest.json", "calls.jsonl"):
                    (replay / name).write_bytes(raw[name])
                summary = rebuild_outputs(replay)
                if any((replay / name).read_bytes() != raw[name]
                       for name in ("scores.csv", "usage.csv", "analysis_manifest.json")):
                    raise ValueError("Execution outputs disagree with raw-journal replay")
        if any((directory / name).read_bytes() != data for name, data in raw.items()):
            raise ValueError("Execution evidence changed during audit")
        if kind == "synthetic":
            inventory["synthetic_run_directories"].append(relative)
            continue
        trace_hashes.add(digest)
        dataset = stored["plan"]["dataset"]
        if dataset == "main":
            main_freeze_hashes.add(stored["run_config"].get("freeze", {}).get("record_hash"))
        inventory["empirical_runs"].append({"directory": relative, "dataset": dataset,
            "raw_trace_sha256": digest,
            "replay_source_commit": historical["source_commit"] if historical else None,
            **{key: summary[key] for key in ("attempted_calls", "successful_calls", "infrastructure_retries",
                "empirical_observations", "planned_cells", "completed_cells", "pending_cells",
                "first_action_or_readback_missing", "unknown_cost_attempts", "accounting_error_attempts")}})
        inventory["recorded_request_attempts"] += summary["attempted_calls"]
        inventory["successful_calls"] += summary["successful_calls"]
        inventory["infrastructure_retries"] += summary["infrastructure_retries"]
    claimed = milestones.get("experimental_calls")
    if type(claimed) is not int or claimed < 0 or claimed != inventory["recorded_request_attempts"]:
        raise ValueError("Experimental call count disagrees with retained request attempts")
    record = milestones.get("execution_freeze")
    if isinstance(record, str):
        path = (root / record).resolve()
        if Path(record).is_absolute() or not path.is_relative_to(root):
            raise ValueError("Freeze record path must stay inside the repository")
        record = json.loads(path.read_bytes(), object_pairs_hook=_unique_object)
    if record is not None:
        if (not isinstance(record, dict)
                or not {"selected_load", "schedule_seed", "provider_settings"} <= set(record)):
            raise ValueError("Execution freeze requires a complete verifiable record")
        plan = build_manifest("main", record["selected_load"], record["schedule_seed"])
        inventory["freeze"] = verify_freeze(record, plan, record["provider_settings"])
    if main_freeze_hashes and (record is None or main_freeze_hashes != {record.get("record_hash")}):
        raise ValueError("Empirical main evidence must match the recorded verified freeze")
    states = {item["number"]: item["status"] for item in milestones["milestones"]}
    if states.get(4) == "complete" and inventory["freeze"] is None:
        raise ValueError("Milestone 4 completion requires a verified execution freeze")
    if states.get(5) == "complete":
        main_runs = [entry for entry in inventory["empirical_runs"] if entry["dataset"] == "main"]
        if (states.get(4) != "complete" or inventory["freeze"] is None
                or not main_runs or any(entry["pending_cells"] for entry in main_runs)):
            raise ValueError("Milestone 5 completion requires frozen main evidence without pending cells")
    if states.get(6) == "complete" and states.get(5) != "complete":
        raise ValueError("Milestone 6 completion requires completed empirical execution")
    return inventory


def main() -> int:
    # Load silently so the exact local key is included in leak checks; ignored
    # .env contents are never scanned, printed, hashed or copied into evidence.
    load_local_credentials()
    failures: list[str] = []
    checks: list[str] = []

    def check(condition: bool, name: str) -> None:
        (checks if condition else failures).append(name)

    expected_files = [
        ".gitattributes", ".gitignore", "README.md", "AGENTS.md",
        "research/protocol.md", "research/source_manifest.json",
        "research/audit.md", "research/requirements.csv",
        "research/decisions.md", "research/baseline.json",
        "research/milestones.json", "scripts/verify_audit.py",
    ]
    for relative in expected_files:
        check((ROOT / relative).is_file(), f"artifact exists: {relative}")
    if failures:
        print(json.dumps({"status": "failed", "failures": failures}, indent=2))
        return 1

    provenance = json.loads((ROOT / "research/source_manifest.json").read_text("utf-8"))
    raw = (ROOT / "research/protocol.md").read_bytes()
    check(hashlib.sha256(raw).hexdigest() == SOURCE_SHA256 == provenance["sha256"],
          "authoritative design SHA-256")
    check(len(raw) == 27751 == provenance["size_bytes"], "authoritative design byte count")
    check(len(raw.splitlines()) == 581 == provenance["line_count"], "authoritative design line count")
    check(provenance["archive_path"] == "research/protocol.md", "source archive path")
    check(provenance["execution_freeze"] is False, "source is not an execution freeze")
    attributes = subprocess.run(
        ["git", "check-attr", "text", "--", "research/protocol.md"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()
    check(attributes == "research/protocol.md: text: unset", "source Git byte preservation")

    with (ROOT / "research/requirements.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    ids = [row["id"] for row in rows]
    check(len(ids) == len(set(ids)), "unique requirement IDs")
    check(all(f"T{i}" in ids for i in range(1, 9)), "T1-T8 mapped")
    check(set(row["milestone"] for row in rows) == set("123456"), "all six milestones mapped")
    check(all(row["status"] in {"existing", "missing", "incorrect", "blocked"} for row in rows),
          "explicit requirement status vocabulary")
    check(all(set(row) == {"id", "source", "requirement", "status", "implementation",
                          "acceptance_check", "milestone", "notes"} and all(row.values())
              for row in rows), "complete and well-formed requirement rows")
    for row in rows:
        if row["id"] in {f"T{i}" for i in range(1, 9)} and row["status"] == "existing":
            check((ROOT / row["acceptance_check"]).is_file(), f"implemented test exists: {row['id']}")

    milestones = json.loads((ROOT / "research/milestones.json").read_text("utf-8"))
    check([item["number"] for item in milestones["milestones"]] == list(range(1, 7)),
          "exactly six ordered milestone records")
    for item in milestones["milestones"][1:]:
        if item["status"] == "complete":
            checks_recorded = item.get("validation", [])
            check(bool(checks_recorded) and all(c["exit_code"] == 0 for c in checks_recorded),
                  f"milestone {item['number']} has passing acceptance evidence")
    execution_inventory = validate_execution_evidence(ROOT, milestones)
    check(True, "execution status reconciled with retained raw evidence and verified freeze")

    baseline = json.loads((ROOT / "research/baseline.json").read_text("utf-8"))
    check(all(value == "absent; not run or passed" for value in baseline["required_experiment_tests"].values()),
          "historical M1 experiment-test absence preserved")
    check(baseline["pytest_baseline"]["process_exit_code"] == 5,
          "pytest no-tests result recorded as non-passing")
    check(baseline["spending"]["authorized_cap"] is None,
          "planning estimate not spending authorization")
    check(all(isinstance(value, bool) for value in baseline["credential_presence_only"].values()),
          "credential evidence limited to presence booleans")

    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, capture_output=True, check=True,
    )
    paths = sorted(set(p.decode("utf-8") for p in result.stdout.split(b"\0") if p))
    forbidden_names = {".env", "credentials.json", "credentials.yaml"}
    token_patterns = [
        re.compile(rb"sk-(?:or-v1-)?[A-Za-z0-9_-]{20,}"),
        re.compile(rb"(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}"),
        re.compile(rb"Bearer\s+[A-Za-z0-9._-]{15,}", re.IGNORECASE),
        re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ]
    credential_names = ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ADAPTION_API_KEY")
    for relative in paths:
        path = ROOT / relative
        check(path.name not in forbidden_names and not (path.name.startswith(".env.") and path.name != ".env.example"),
              f"no credential file staged or unignored: {relative}")
        if not path.is_file():
            continue
        content = path.read_bytes()
        check(not any(pattern.search(content) for pattern in token_patterns),
              f"no selected credential patterns: {relative}")
        for name in credential_names:
            value = os.environ.get(name)
            if value:
                check(value.encode() not in content, f"no current credential value: {relative}")

    print(json.dumps({
        "status": "failed" if failures else "passed",
        "scope": "audit evidence and source integrity; experiment tests are separately recorded",
        "checks_passed": len(checks), "requirements_mapped": len(rows),
        "files_scanned": len(paths), "source_sha256": SOURCE_SHA256,
        "execution_inventory": execution_inventory,
        "secret_scan_limit": "Selected token patterns, credential filenames, and checked current environment values; manual diff review also required.",
        "failures": failures,
    }, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, CredentialLoadError, subprocess.CalledProcessError) as exc:
        # Error class only: exception content could contain sensitive file contents.
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}))
        sys.exit(1)
