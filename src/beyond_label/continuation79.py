"""Prepare only the 79 untouched cells; retain the terminal v2 response forever.

Historical request/response bytes and their collection-version classifications
are immutable. This module performs local provenance checks, never dispatch.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from . import continuation as legacy


RECORD_PATH = "research/smoke_continuation_79.json"
SEGMENT_DIRECTORY = legacy.PAID_SMOKE_DIRECTORY + "/segments/deepseek_primeintellect_v3"
RETAINED_CELL_ID = "smoke-1100-readback-MAIN-inline-b"
TERMINAL_SOURCE_COMMIT = "89de9c8202c8cfa9720f49e495ecbb8ea662f3aa"
_TERMINAL_FILES = {
    "manifest.json": "ab9fd94b54d54c4cab1381e490990347d7ab13e2cadbd0d4400e4ee08ee90958",
    "calls.jsonl": "8518852b1cd3b6406b7a0417b090547083480ff2b4ff02360d179a281a17a899",
    "scores.csv": "758ab64bd0c800005c83a51c255a4765bbb49b1b8c47ddf87a7218665b4ffce4",
    "usage.csv": "d10d8d2b60520204caf302b525915363ee1bcd356143dbff6a71624df4191cce",
    "analysis_manifest.json": "cdfe09cb249b056a062848774a034b8ef54daab834824992cc38c4a1da85d856",
}


def retained_cell_spec() -> dict:
    """Pure archival replay contract: no filesystem or credential access."""
    return {"cell_id": RETAINED_CELL_ID, "missing_reason": "model_mismatch",
            "continuation_status": "not_applicable", "source_directory": legacy.SEGMENT_DIRECTORY,
            "source_artifact_sha256": dict(_TERMINAL_FILES)}


def segment_path(root: Path) -> Path:
    root = Path(root).resolve()
    path = root / SEGMENT_DIRECTORY
    if path.resolve() != path or not path.is_relative_to(root / "runs"):
        raise legacy.ContinuationError("continuation79_segment_path_invalid")
    return path


def historical_terminal_smoke(root: Path) -> dict:
    """Read exactly the retained 89de identity rejection; never reinterpret it."""
    root = Path(root).resolve()
    directory = root / legacy.SEGMENT_DIRECTORY
    if directory.resolve() != directory or not directory.is_relative_to(root / "runs"):
        raise legacy.ContinuationError("terminal_smoke_path_invalid")
    prior = legacy.load_legacy_continuation(root)
    if prior is None or prior["active_source_commit"] != TERMINAL_SOURCE_COMMIT:
        raise legacy.ContinuationError("terminal_smoke_preparation_invalid")
    try:
        index = legacy._read(root / "research/run_sources.json")
        binding = index["runs"][legacy.SEGMENT_DIRECTORY]
        if (type(index.get("schema_version")) is not int or index["schema_version"] != 1
                or binding.get("source_commit") != TERMINAL_SOURCE_COMMIT
                or binding.get("files") != _TERMINAL_FILES):
            raise legacy.ContinuationError("terminal_smoke_source_binding_invalid")
        if any((directory / name).resolve().parent != directory for name in legacy.FILES):
            raise legacy.ContinuationError("terminal_smoke_artifact_path_invalid")
        raw = {name: (directory / name).read_bytes() for name in legacy.FILES}
        if any(legacy._sha(raw[name]) != _TERMINAL_FILES[name] for name in legacy.FILES):
            raise legacy.ContinuationError("terminal_smoke_artifact_changed")
        stored = legacy._read(directory / "manifest.json")
        plan, config = stored["plan"], stored["run_config"]
        execution = config.get("execution_config", {})
        if (plan != prior["plan"]
                or stored["run_config_hash"] != legacy._hash({"plan": plan, "config": config})
                or config.get("input_hashes") != prior["active_input_sha256"]
                or config.get("evidence_kind") != "empirical"
                or config.get("transport_provenance") != "openrouter_paid_https_v1"
                or execution.get("continuation_record_hash") != prior["record_hash"]
                or execution.get("continuation_source_commit") != TERMINAL_SOURCE_COMMIT):
            raise legacy.ContinuationError("terminal_smoke_manifest_invalid")
        events = legacy.Journal(directory / "calls.jsonl").events
        if ([event["event"] for event in events] !=
                ["phase_defined", "attempt_started", "attempt_failed", "cell_completed"]
                or any(event.get("cell_id") != RETAINED_CELL_ID for event in events)):
            raise legacy.ContinuationError("terminal_smoke_has_other_observations")
        definition, start, failure, completed = events
        response = failure.get("raw_response")
        selected = [endpoint for endpoint in response.get("openrouter_metadata", {}).get("endpoints", {}).get("available", [])
                    if endpoint.get("selected") is True] if isinstance(response, dict) else []
        if (definition.get("phase") != "readback" or start.get("phase") != "readback"
                or failure.get("phase") != "readback"
                or any(type(event.get("attempt")) is not int or event["attempt"] != 1 for event in (start, failure))
                or failure.get("reason") != "model_mismatch"
                or failure.get("infrastructure") is not False or failure.get("retryable") is not False
                or not isinstance(response, dict) or not response.get("choices")
                or response.get("model") != "deepseek/deepseek-v4.1-flash-1017"
                or len(selected) != 1 or selected[0].get("model") != "deepseek/deepseek-v4.1-flash-20261017"
                or selected[0].get("provider") != "PrimeIntellect"
                or completed.get("first_missing_reason") != "model_mismatch"
                or completed.get("continuation_status") != "not_applicable"):
            raise legacy.ContinuationError("terminal_smoke_is_not_the_recorded_identity_failure")
        summary = legacy._read(directory / "analysis_manifest.json")
        expected = {"attempted_calls": 1, "successful_calls": 0, "completed_cells": 1,
                    "planned_cells": 80, "pending_cells": 79, "empirical_observations": 0,
                    "first_action_or_readback_missing": 80, "unknown_cost_attempts": 0,
                    "accounting_error_attempts": 0, "infrastructure_retries": 0,
                    "continuations": 0, "permitted_reprompts": 0}
        if any(type(summary.get(key)) is not int or summary[key] != value for key, value in expected.items()):
            raise legacy.ContinuationError("terminal_smoke_summary_invalid")
        if any((directory / name).read_bytes() != data for name, data in raw.items()):
            raise legacy.ContinuationError("terminal_smoke_changed_during_read")
        return {"stored": stored, "events": events, "source_commit": TERMINAL_SOURCE_COMMIT,
                "artifact_sha256": dict(_TERMINAL_FILES), "summary": summary,
                "historical_directory": legacy.SEGMENT_DIRECTORY}
    except (OSError, KeyError, TypeError, ValueError, AttributeError) as error:
        if isinstance(error, legacy.ContinuationError):
            raise
        raise legacy.ContinuationError("terminal_smoke_evidence_invalid") from None


def _histories(root: Path) -> list[dict]:
    return [legacy.historical_smoke(root), historical_terminal_smoke(root)]


def _descriptors(histories: list[dict]) -> list[dict]:
    return [{"directory": item["historical_directory"], "source_commit": item["source_commit"],
             "input_hashes": dict(item["stored"]["run_config"]["input_hashes"]),
             "artifact_sha256": dict(item["artifact_sha256"])} for item in histories]


def historical_segments(root: Path) -> list[dict]:
    """Describe both fixed, independently replayable historical versions."""
    return _descriptors(_histories(Path(root).resolve()))


def _record(histories: list[dict], source_commit: str, inputs: dict) -> dict:
    old = histories[-1]["stored"]["run_config"]["input_hashes"]
    changed = sorted(name for name in set(old) | set(inputs) if old.get(name) != inputs.get(name))
    if set(changed) - legacy._REPAIR_INPUTS:
        raise legacy.ContinuationError("scientific_inputs_changed")
    plan = deepcopy(histories[-1]["stored"]["plan"])
    if plan != histories[0]["stored"]["plan"] or plan["cells"][0]["cell_id"] != RETAINED_CELL_ID:
        raise legacy.ContinuationError("continuation79_plan_changed")
    dispatch = [cell["cell_id"] for cell in plan["cells"] if cell["cell_id"] != RETAINED_CELL_ID]
    if len(dispatch) != 79 or len(set(dispatch)) != 79:
        raise legacy.ContinuationError("continuation79_dispatch_invalid")
    value = {"schema_version": 1, "classification": "prepared_source_version_not_execution",
             "continuation_id": "deepseek_primeintellect_v3", "authorization_id": legacy.PAID_SMOKE_AUTHORIZATION,
             "historical_directory": legacy.PAID_SMOKE_DIRECTORY,
             "active_directory": SEGMENT_DIRECTORY, "shared_session": "runs/_paid_testing_session",
             "historical_segments": _descriptors(histories), "historical_recorded_attempts": 2,
             "historical_successful_calls": 0, "historical_terminal_cells": 1,
             "unique_planned_cells": 80, "plan": plan, "retained_cells": [retained_cell_spec()],
             "dispatch_cell_ids": dispatch, "active_source_commit": source_commit,
             "active_input_sha256": dict(inputs), "changed_input_paths": changed,
             "historical_replay_verified": True,
             "attempt_policy": "new_source_dispatch_only_untouched_cells_not_identical_retry",
             "sample_policy": "same_80_logical_cells_one_terminal_missing_retained_79_untouched",
             "allowance_policy": "shared_usd1_200_attempts_including_both_historical_attempts_no_reset",
             "cost_policy": "preserve_original_unknown_hold_and_known_terminal_response_charge"}
    return {**value, "record_hash": legacy._hash(value)}


def _verify_replays(histories: list[dict], proofs: dict) -> None:
    if not isinstance(proofs, dict) or set(proofs) != {item["historical_directory"] for item in histories}:
        raise legacy.ContinuationError("continuation79_replay_set_invalid")
    for item in histories:
        proof = proofs[item["historical_directory"]]
        if (not isinstance(proof, dict)
                or any(proof.get(key) is not True for key in
                       ("original_files_unchanged", "network_blocked", "credentials_removed"))
                or proof.get("source_commit") != item["source_commit"]
                or proof.get("artifact_sha256") != item["artifact_sha256"]
                or proof.get("summary") != item["summary"]
                or type(proof.get("input_hashes_verified")) is not int
                or proof["input_hashes_verified"] != len(item["stored"]["run_config"]["input_hashes"])):
            raise legacy.ContinuationError("continuation79_historical_replay_not_verified")


def build_continuation79_record(root: Path, *, source_commit: str, input_hashes: dict, replay_proofs: dict) -> dict:
    """Build research metadata only, after both immutable histories replay."""
    root = Path(root).resolve()
    if segment_path(root).exists() or (root / RECORD_PATH).exists():
        raise legacy.ContinuationError("continuation79_already_prepared_or_started")
    histories = _histories(root)
    _verify_replays(histories, replay_proofs)
    legacy._verify_committed_inputs(root, source_commit, input_hashes)
    for item in histories:
        legacy._verify_committed_inputs(root, item["source_commit"], item["stored"]["run_config"]["input_hashes"])
    return _record(histories, source_commit, input_hashes)


def load_continuation79(root: Path, *, input_hashes: dict) -> dict:
    """Validate active source, both histories and the exact retained cell set."""
    root = Path(root).resolve()
    segment_path(root)
    path = root / RECORD_PATH
    if path.resolve() != path:
        raise legacy.ContinuationError("continuation79_record_path_invalid")
    record = legacy._read(path)
    if not isinstance(record, dict) or record.get("active_input_sha256") != input_hashes:
        raise legacy.ContinuationError("continuation79_source_changed")
    if record.get("record_hash") != legacy._hash({k: v for k, v in record.items() if k != "record_hash"}):
        raise legacy.ContinuationError("continuation79_record_changed")
    histories = _histories(root)
    legacy._verify_committed_inputs(root, record.get("active_source_commit"), input_hashes)
    for item in histories:
        legacy._verify_committed_inputs(root, item["source_commit"], item["stored"]["run_config"]["input_hashes"])
    expected = _record(histories, record["active_source_commit"], input_hashes)
    if record != expected:
        raise legacy.ContinuationError("continuation79_record_changed")
    return record
