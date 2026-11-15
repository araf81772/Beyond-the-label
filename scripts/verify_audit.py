"""Verify source integrity and audit evidence as milestones advance.

Historical M1 absence claims are checked against its retained baseline. Live
status is checked against present files rather than freezing the project at M1.
"""

from __future__ import annotations

from collections import Counter
import csv
from decimal import Decimal
import hashlib
import io
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


def require_continuation_binding(stored: dict, record: dict) -> None:
    """An active child retains its exact prepared source and retained outcomes."""
    config = stored.get("run_config", {})
    execution = config.get("execution_config", {})
    if (stored.get("plan") != record["plan"]
            or config.get("input_hashes") != record["active_input_sha256"]
            or config.get("transport_provenance") != "openrouter_paid_https_v1"
            or config.get("provider_settings", {}).get("free_only") is not False
            or execution.get("continuation_record_hash") != record["record_hash"]
            or execution.get("continuation_source_commit") != record["active_source_commit"]):
        raise ValueError("Smoke continuation metadata differs from its prepared source")
    if ("retained_cells" in record
            and (execution.get("retained_terminal_cells") != record["retained_cells"]
                 or execution.get("continuation_dispatch_cell_ids") != record["dispatch_cell_ids"])):
        raise ValueError("Smoke continuation retained outcomes differ from its prepared source")


def require_retained_terminal_evidence(stored: dict, record: dict, raw: dict, summary: dict) -> None:
    """A carried-forward terminal failure is missing data, never an active sample."""
    from beyond_label.budget import _unique_object

    require_continuation_binding(stored, record)
    retained = {item["cell_id"]: item for item in record["retained_cells"]}
    dispatch = set(record["dispatch_cell_ids"])
    if (len(retained) != len(record["retained_cells"]) or retained.keys() & dispatch
            or len(dispatch) != len(record["dispatch_cell_ids"])):
        raise ValueError("Smoke retained and dispatch identities overlap or repeat")
    events = [json.loads(line, object_pairs_hook=_unique_object)
              for line in raw["calls.jsonl"].splitlines()]
    if any(event.get("cell_id") in retained for event in events):
        raise ValueError("An active event resamples a retained terminal cell")
    if any(event.get("cell_id") not in dispatch for event in events):
        raise ValueError("An active event is outside the prepared dispatch identities")
    rows = list(csv.DictReader(io.StringIO(raw["scores.csv"].decode("utf-8"), newline="")))
    by_id = {row["cell_id"]: row for row in rows}
    if len(by_id) != len(rows) or set(by_id) != retained.keys() | dispatch:
        raise ValueError("Smoke scores must retain each planned cell exactly once")
    unobserved = ("readback_correct", "category", "expected_loss", "oracle_loss", "regret",
                  "regret_with_invalids", "realised_loss", "inspected_lot", "post_inspection_correct",
                  "report_contradiction")
    for cell_id, source in retained.items():
        row = by_id[cell_id]
        if (row.get("cell_status") != "retained_terminal"
                or row.get("missing_reason") != source["missing_reason"]
                or row.get("continuation_status") != source["continuation_status"]
                or row.get("retained_source_directory") != source["source_directory"]
                or row.get("retained_source_trace_sha256") != source["source_artifact_sha256"]["calls.jsonl"]
                or any(row.get(field, "") != "" for field in unobserved)):
            raise ValueError("A retained terminal row changed its missing observation")
    if (type(summary.get("retained_terminal_cells")) is not int
            or summary["retained_terminal_cells"] != len(retained)
            or type(summary.get("completed_cells")) is not int
            or not 0 <= summary["completed_cells"] <= len(dispatch)
            or type(summary.get("pending_cells")) is not int
            or summary["pending_cells"] != len(dispatch) - summary["completed_cells"]):
        raise ValueError("Smoke summary double-counts or loses retained terminal cells")


def require_historical_segment_binding(stored: dict, raw: dict, descriptor: dict,
                                       replay: dict | None = None) -> None:
    """Historical segments use their own committed code and immutable artifacts."""
    if (stored.get("run_config", {}).get("input_hashes") != descriptor["input_hashes"]
            or set(raw) != set(descriptor["artifact_sha256"])
            or any(hashlib.sha256(data).hexdigest() != descriptor["artifact_sha256"][name]
                   for name, data in raw.items())
            or (replay is not None and replay.get("source_commit") != descriptor["source_commit"])):
        raise ValueError("Historical smoke source or artifact identity changed")


def audit_continuations(root: Path, input_hashes: dict) -> tuple[dict | None, dict | None]:
    """Audit old evidence before a new source is prepared without relaxing live gates."""
    from beyond_label.continuation import ContinuationError, _read, load_continuation, load_legacy_continuation
    from beyond_label.continuation79 import RECORD_PATH, load_continuation79, segment_path

    legacy = load_legacy_continuation(root)
    if not ((root / RECORD_PATH).exists() or segment_path(root).exists()):
        return legacy, legacy
    record = _read(root / RECORD_PATH) if (root / RECORD_PATH).exists() else None
    recorded = record.get("active_input_sha256") if isinstance(record, dict) else None
    if recorded is not None and recorded != input_hashes:
        # Later source (the staged USD 9 path) makes the 79-cell smoke a closed
        # historical segment. Its record is still verified in full against its
        # own committed source, exactly as the retained v2 record is; its run
        # is then replayed with that source instead of the current code.
        if not isinstance(recorded, dict):
            raise ContinuationError("continuation79_record_changed")
        return legacy, load_continuation79(root, input_hashes=recorded)
    return legacy, load_continuation(root, input_hashes=input_hashes)


def _segment_costs(segments: list[dict]) -> dict:
    known = Decimal(0)
    for entry in segments:
        value = Decimal(str(entry.get("known_provider_spend_usd", 0)))
        if not value.is_finite() or value < 0:
            raise ValueError("Smoke segment cost evidence is invalid")
        known += value
    return {"known_provider_spend_usd": format(known, "f"),
            "aggregate_actual_cost_complete": not any(
                entry["unknown_cost_attempts"] or entry.get("accounting_error_attempts", 0)
                for entry in segments)}


def _retained_smoke_group(smoke: list[dict], record: dict) -> tuple[dict, set[str]]:
    """Count v2's one terminal failure once while v3 dispatches only 79 cells."""
    history = [item["directory"] for item in record["historical_segments"]]
    active_path = record["active_directory"]
    retained = record["retained_cells"]
    if (len(history) != 2 or len(set(history)) != 2 or active_path in history
            or history[0] != record["historical_directory"] or len(retained) != 1
            or retained[0]["source_directory"] != history[1]
            or len(record["dispatch_cell_ids"]) != 79):
        raise ValueError("Invalid historical smoke continuation identities")
    old = []
    for name in history:
        matching = [entry for entry in smoke if entry["directory"] == name]
        if len(matching) != 1:
            raise ValueError("Every historical smoke segment must remain available once")
        old.extend(matching)
    for index, entry in enumerate(old):
        expected = {"attempted_calls": 1, "successful_calls": 0, "completed_cells": index,
                    "pending_cells": 80-index, "planned_cells": 80, "infrastructure_retries": 0}
        if any(type(entry.get(key)) is not int or entry[key] != value for key, value in expected.items()):
            raise ValueError("Historical smoke observations cannot be changed or resampled")
    active = [entry for entry in smoke if entry["directory"] == active_path]
    if len(active) > 1:
        raise ValueError("An active smoke segment cannot be counted twice")
    if active:
        current = active[0]
        if (type(current.get("completed_cells")) is not int or not 0 <= current["completed_cells"] <= 79
                or type(current.get("retained_terminal_cells")) is not int or current["retained_terminal_cells"] != 1
                or type(current.get("planned_cells")) is not int or current["planned_cells"] != 80
                or type(current.get("pending_cells")) is not int or current["pending_cells"] != 79-current["completed_cells"]):
            raise ValueError("Active smoke counts double-count or lose retained cells")
    segments = [*old, *active]
    completed = 1 + (active[0]["completed_cells"] if active else 0)
    return ({"logical_run_directory": history[0],
        "classification": "same_smoke_sample_across_pre_freeze_source_versions",
        "independent_smoke_samples": 1, "unique_planned_cells": 80,
        "completed_cells": completed, "retained_terminal_cells": 1, "pending_cells": 80-completed,
        "segment_directories": [entry["directory"] for entry in segments],
        "active_directory": active_path, "active_segment_initialized": bool(active),
        "active_segment_started": bool(active and active[0]["attempted_calls"]),
        "recorded_request_attempts": sum(entry["attempted_calls"] for entry in segments),
        "successful_calls": sum(entry["successful_calls"] for entry in segments),
        "infrastructure_retries": sum(entry["infrastructure_retries"] for entry in segments),
        # Only v2 reissued the previously failed cell. V3 has disjoint dispatch.
        "source_version_reissues": 1,
        "unknown_cost_attempts": sum(entry["unknown_cost_attempts"] for entry in segments),
        **_segment_costs(segments)}, {*history, active_path})


def logical_smoke_groups(entries: list[dict], record: dict | None) -> list[dict]:
    """Keep infrastructure segments while counting the same planned 80 cells once."""
    smoke = [entry for entry in entries if entry["dataset"] == "smoke"]
    groups = []
    grouped = set()
    if record is not None and "retained_cells" in record:
        group, grouped = _retained_smoke_group(smoke, record)
        groups.append(group)
    elif record is not None:
        old_path, active_path = record["historical_directory"], record["active_directory"]
        old = [entry for entry in smoke if entry["directory"] == old_path]
        active = [entry for entry in smoke if entry["directory"] == active_path]
        if (len(old) != 1 or len(active) > 1 or old[0]["attempted_calls"] != 1
                or old[0]["successful_calls"] != 0 or old[0]["completed_cells"] != 0
                or old[0]["planned_cells"] != 80 or any(entry["planned_cells"] != 80 for entry in active)):
            raise ValueError("historical smoke observations cannot be resampled by a continuation")
        segments = [*old, *active]
        completed = active[0]["completed_cells"] if active else 0
        groups.append({"logical_run_directory": old_path,
            "classification": "same_smoke_sample_across_pre_freeze_source_versions",
            "independent_smoke_samples": 1, "unique_planned_cells": 80,
            "completed_cells": completed, "pending_cells": 80 - completed,
            "segment_directories": [entry["directory"] for entry in segments],
            "active_directory": active_path, "active_segment_initialized": bool(active),
            "active_segment_started": bool(active and active[0]["attempted_calls"]),
            "recorded_request_attempts": sum(entry["attempted_calls"] for entry in segments),
            "successful_calls": sum(entry["successful_calls"] for entry in segments),
            "infrastructure_retries": sum(entry["infrastructure_retries"] for entry in segments),
            "source_version_reissues": int(bool(active and active[0]["attempted_calls"])),
            "unknown_cost_attempts": sum(entry["unknown_cost_attempts"] for entry in segments),
            **_segment_costs(segments)})
        grouped.update((old_path, active_path))
    for entry in smoke:
        if entry["directory"] in grouped:
            continue
        groups.append({"logical_run_directory": entry["directory"],
            "classification": "single_source_smoke", "independent_smoke_samples": 1,
            "unique_planned_cells": entry["planned_cells"], "completed_cells": entry["completed_cells"],
            "pending_cells": entry["pending_cells"], "segment_directories": [entry["directory"]],
            "active_directory": entry["directory"], "active_segment_initialized": True,
            "active_segment_started": bool(entry["attempted_calls"]),
            "recorded_request_attempts": entry["attempted_calls"], "successful_calls": entry["successful_calls"],
            "infrastructure_retries": entry["infrastructure_retries"], "source_version_reissues": 0,
            "unknown_cost_attempts": entry["unknown_cost_attempts"], **_segment_costs([entry])})
    return groups


def validate_execution_evidence(root: Path, milestones: dict) -> dict:
    """Reconcile status with retained raw evidence without changing run files.

    experimental_calls means recorded request attempts, not confirmed HTTP
    deliveries. Pre-dispatch allowance reservations are a different quantity.
    Synthetic directories never contribute to empirical counts or completion.
    """
    from beyond_label.budget import _unique_object
    from beyond_label.freeze import verify_freeze
    from beyond_label.run import build_manifest, rebuild_outputs, _inputs
    from beyond_label.continuation import SEGMENT_DIRECTORY
    from beyond_label.continuation79 import SEGMENT_DIRECTORY as RETAINED_SEGMENT_DIRECTORY

    root = root.resolve()
    runs_root = root / "runs"
    if not runs_root.resolve().is_relative_to(root):
        raise ValueError("Execution inventory must stay inside the repository")
    current_inputs = _inputs()
    legacy, continuation = audit_continuations(root, current_inputs)
    historical_segments = {item["directory"]: item for item in continuation.get("historical_segments", [])} if continuation else {}
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
        if relative == SEGMENT_DIRECTORY:
            if legacy is None or kind != "empirical":
                raise ValueError("Smoke continuation requires its verified preparation")
            require_continuation_binding(stored, legacy)
        if relative == RETAINED_SEGMENT_DIRECTORY:
            if continuation is None or "retained_cells" not in continuation or kind != "empirical":
                raise ValueError("Retained smoke continuation requires its verified preparation")
            require_continuation_binding(stored, continuation)
        descriptor = historical_segments.get(relative)
        if descriptor is not None:
            require_historical_segment_binding(stored, raw, descriptor)
        if kind not in {"empirical", "synthetic"}:
            raise ValueError("Execution inventory requires explicit evidence labels")
        digest = hashlib.sha256(raw["calls.jsonl"]).hexdigest()
        if kind == "empirical" and raw["calls.jsonl"] and digest in trace_hashes:
            raise ValueError("Duplicate empirical journal cannot count as another run")
        historical = None
        if stored["run_config"].get("input_hashes") != current_inputs or descriptor is not None:
            historical = replay_historical(root, directory)
            summary = historical["summary"]
            if descriptor is not None:
                require_historical_segment_binding(stored, raw, descriptor, historical)
        else:
            with tempfile.TemporaryDirectory(prefix="btl-audit-replay-") as temporary:
                replay = Path(temporary)
                for name in ("manifest.json", "calls.jsonl"):
                    (replay / name).write_bytes(raw[name])
                summary = rebuild_outputs(replay)
                if any((replay / name).read_bytes() != raw[name]
                       for name in ("scores.csv", "usage.csv", "analysis_manifest.json")):
                    raise ValueError("Execution outputs disagree with raw-journal replay")
        if relative == RETAINED_SEGMENT_DIRECTORY:
            require_retained_terminal_evidence(stored, continuation, raw, summary)
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
            "retained_terminal_cells": summary.get("retained_terminal_cells", 0),
            "known_provider_spend_usd": summary["known_provider_spend_usd"],
            **{key: summary[key] for key in ("attempted_calls", "successful_calls", "infrastructure_retries",
                "empirical_observations", "planned_cells", "completed_cells", "pending_cells",
                "first_action_or_readback_missing", "unknown_cost_attempts", "accounting_error_attempts")}})
        inventory["recorded_request_attempts"] += summary["attempted_calls"]
        inventory["successful_calls"] += summary["successful_calls"]
        inventory["infrastructure_retries"] += summary["infrastructure_retries"]
    inventory["logical_smoke_runs"] = logical_smoke_groups(inventory["empirical_runs"], continuation)
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


def validate_staged_ledger(root: Path) -> dict | None:
    """Reconcile the staged USD 9 ledger with the staged journals, offline.

    The ledger hash chain cannot show that its last line is missing. Every
    journaled provider receipt must therefore appear exactly once in the ledger
    and every hold must belong to a journaled attempt without a receipt. The
    check runs on a temporary copy, so the session directory is never written.
    """
    from beyond_label.budget import BudgetLedger
    from beyond_label.gates import STAGED_SESSION, STAGED_STAGES
    from beyond_label.attempts import ExecutionSuspended
    from beyond_label.run import Journal
    from beyond_label.staged import STAGED_CAP, StagedAttemptLimit, reconcile_staged_history

    session = root / STAGED_SESSION
    directories = [value[2] for value in STAGED_STAGES.values() if (root / value[2] / "manifest.json").is_file()]
    if not session.exists():
        if directories:
            raise ValueError("Staged run evidence exists without its shared ledger")
        return None
    with tempfile.TemporaryDirectory(prefix="btl-audit-ledger-") as temporary:
        copy = Path(temporary).resolve()
        for relative in directories:
            (copy / relative).mkdir(parents=True)
            for name in ("manifest.json", "calls.jsonl"):
                (copy / relative / name).write_bytes((root / relative / name).read_bytes())
        (copy / STAGED_SESSION).mkdir(parents=True)
        for name in ("authorization.json", "budget.jsonl", "attempts.jsonl"):
            (copy / STAGED_SESSION / name).write_bytes((session / name).read_bytes())
        try:
            ledger = BudgetLedger(copy / STAGED_SESSION / "budget.jsonl", STAGED_CAP, "USD")
            result = reconcile_staged_history(copy, ledger, StagedAttemptLimit(copy / STAGED_SESSION / "attempts.jsonl"))
            state = ledger.snapshot()
            open_starts = Counter()
            for relative in directories:
                unfinished = {}
                for event in Journal(copy / relative / "calls.jsonl").events:
                    if event["event"] == "attempt_started":
                        unfinished[(event["cell_id"], event["phase"], event["attempt"])] = event["request_hash"]
                    elif event["event"] in {"attempt_succeeded", "attempt_failed"}:
                        unfinished.pop((event["cell_id"], event["phase"], event["attempt"]), None)
                open_starts.update(unfinished.values())
            # Settlement precedes the journaled outcome, even for unknown cost.
            # Pending reservations therefore need unmatched starts; a terminal
            # outcome cannot explain a lost settled(null) ledger append.
            pending = Counter(attempt["request_hash"] for attempt in state["attempts"].values()
                              if attempt["status"] == "pending")
            if pending - open_starts:
                raise ExecutionSuspended("staged_pending_reservation_without_open_attempt")
        except ExecutionSuspended as exc:
            raise ValueError(f"Staged ledger disagrees with staged journals: {exc}") from None
    return {**result, "settled_cost_usd": state["settled_cost"], "held_usd": state["held"],
            "available_usd": state["available"]}


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
    staged_ledger = validate_staged_ledger(ROOT)
    check(True, "staged ledger reconciled with staged journals")

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
        "staged_ledger": staged_ledger,
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
