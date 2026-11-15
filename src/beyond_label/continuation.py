"""One explicitly recorded pre-freeze source continuation of the same smoke.

Preparation is pure: it never creates a run, claims an attempt, settles money,
loads credentials or contacts a provider. Original artifacts stay immutable.
The repaired request is a source-version reissue, never an identical retry.
Only the observed one-error/no-model-output historical state is eligible.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess

from .environment import CREDENTIAL_NAMES
from .gates import PAID_SMOKE_AUTHORIZATION, PAID_SMOKE_DIRECTORY
from .run import Journal, _hash, build_manifest, case_for_cell
from .render import readback_request


CONTINUATION_RECORD = "research/smoke_continuation.json"
SEGMENT_DIRECTORY = PAID_SMOKE_DIRECTORY + "/segments/deepseek_primeintellect_v2"
FILES = ("manifest.json", "calls.jsonl", "scores.csv", "usage.csv", "analysis_manifest.json")
_REPAIR_INPUTS = {f"src/beyond_label/{name}.py" for name in (
    "provider", "openrouter", "paid_controls", "paid_live", "run", "capabilities",
    "attempts", "budget", "controls", "continuation", "cost_reconciliation", "paid_profile", "gates",
)} | {"configs/paid_smoke.yaml"}


class ContinuationError(ValueError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ContinuationError("ambiguous_continuation_json")
        value[key] = item
    return value


def _reject_constant(value):
    raise ContinuationError("nonfinite_continuation_json")


def _read(path: Path):
    try:
        return json.loads(path.read_bytes(), object_pairs_hook=_unique, parse_constant=_reject_constant)
    except (OSError, ValueError, TypeError, RecursionError):
        raise ContinuationError("continuation_record_unavailable_or_invalid") from None


def _allowed_input(name: str) -> bool:
    if not isinstance(name, str) or "\\" in name or ":" in name:
        return False
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return False
    return bool(re.fullmatch(
        r"(?:src/beyond_label/[A-Za-z0-9_]+\.py|prompts/[A-Za-z0-9_]+\.txt|"
        r"configs/[A-Za-z0-9_]+\.yaml|data/worlds_[A-Za-z0-9_]+\.jsonl|"
        r"research/(?:protocol|amendments)\.md|data/manifest\.json|pyproject\.toml|requirements\.lock)", name))


def _valid_inputs(inputs: object) -> bool:
    return (isinstance(inputs, dict) and bool(inputs)
            and all(_allowed_input(name) and isinstance(digest, str)
                    and re.fullmatch(r"[0-9a-f]{64}", digest) for name, digest in inputs.items()))


def _verify_committed_inputs(root: Path, commit: str, inputs: dict) -> None:
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit) or not _valid_inputs(inputs):
        raise ContinuationError("committed_source_identity_invalid")
    env = {key: value for key, value in os.environ.items() if key not in CREDENTIAL_NAMES}
    env.update(GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0", GIT_NO_REPLACE_OBJECTS="1")

    def git(*args):
        try:
            result = subprocess.run(["git", *args], cwd=root, env=env, capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            raise ContinuationError("committed_source_unavailable") from None
        if result.returncode:
            raise ContinuationError("committed_source_unavailable")
        return result.stdout

    try:
        names = git("ls-tree", "-r", "--name-only", commit).decode("utf-8").splitlines()
    except UnicodeError:
        raise ContinuationError("committed_source_paths_invalid") from None
    if {name for name in names if _allowed_input(name)} != set(inputs):
        raise ContinuationError("committed_source_input_set_mismatch")
    if any(_sha(git("show", f"{commit}:{name}")) != digest for name, digest in inputs.items()):
        raise ContinuationError("committed_source_input_hash_mismatch")


def historical_smoke(root: Path) -> dict:
    """Read the hash-bound original failure without using a newer serializer."""
    root = Path(root).resolve()
    directory = root / PAID_SMOKE_DIRECTORY
    if directory.resolve() != directory or not directory.is_relative_to(root / "runs"):
        raise ContinuationError("historical_smoke_path_invalid")
    try:
        index = _read(root / "research/run_sources.json")
        binding = index["runs"][PAID_SMOKE_DIRECTORY]
        commit, hashes = binding["source_commit"], binding["files"]
        if (type(index.get("schema_version")) is not int or index["schema_version"] != 1
                or not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit)
                or not isinstance(hashes, dict) or set(hashes) != set(FILES)):
            raise ContinuationError("historical_source_binding_invalid")
        if any((directory / name).resolve().parent != directory for name in FILES):
            raise ContinuationError("historical_artifact_path_invalid")
        raw = {name: (directory / name).read_bytes() for name in FILES}
        if any(_sha(raw[name]) != hashes[name] for name in FILES):
            raise ContinuationError("historical_artifact_hash_changed")
        stored = _read(directory / "manifest.json")
        plan, config = stored["plan"], stored["run_config"]
        if (plan != build_manifest("smoke", 2, 271828)
                or stored["run_config_hash"] != _hash({"plan": plan, "config": config})
                or config.get("evidence_kind") != "empirical"
                or config.get("transport_provenance") != "openrouter_paid_https_v1"
                or not _valid_inputs(config.get("input_hashes"))):
            raise ContinuationError("historical_smoke_manifest_invalid")
        events = Journal(directory / "calls.jsonl").events
        if [event["event"] for event in events] != ["phase_defined", "attempt_started", "attempt_failed"]:
            raise ContinuationError("historical_smoke_has_observations_or_other_attempts")
        definition, start, failed = events
        first = plan["cells"][0]
        expected_request = readback_request(case_for_cell(first, plan)).model_dump(mode="json")
        # This exception is for the recorded GPT-4.1 mini failure only. Validate
        # its original wire contract directly; never serialize it with the new
        # provider or silently normalize saved payloads into a different request.
        expected_payload = {"model": "openai/gpt-4.1-mini", "messages": expected_request["messages"],
            "provider": {"only": ["openai"], "allow_fallbacks": False, "require_parameters": True,
                         "max_price": {"prompt": .4, "completion": 1.6, "request": 0, "image": 0}},
            "max_tokens": 512, "temperature": 0, "parallel_tool_calls": False}
        if (first["purpose"] != "readback"
                or any(event.get("cell_id") != first["cell_id"] or event.get("phase") != "readback" for event in events)
                or definition.get("request") != expected_request
                or definition.get("logical_request_hash") != _hash(expected_request)
                or any(type(event.get("attempt")) is not int or event["attempt"] != 1 for event in (start, failed))
                or failed.get("reason") != "http_error" or type(failed.get("http_status")) is not int
                or failed["http_status"] != 404 or failed.get("infrastructure") is not True
                or failed.get("retryable") is not True
                or any(event.get("usage") != {} or "raw_response" in event or "result" in event for event in (start, failed))
                or start.get("payload") != expected_payload or failed.get("payload") != expected_payload
                or any(event.get("request_hash") != _hash(event.get("payload")) for event in (start, failed))):
            raise ContinuationError("historical_smoke_is_not_the_no_response_http404")
        summary = _read(directory / "analysis_manifest.json")
        expected = {"attempted_calls": 1, "successful_calls": 0, "completed_cells": 0,
                    "planned_cells": 80, "pending_cells": 80, "empirical_observations": 0}
        if any(type(summary.get(key)) is not int or summary[key] != value for key, value in expected.items()):
            raise ContinuationError("historical_smoke_summary_invalid")
        if any((directory / name).read_bytes() != content for name, content in raw.items()):
            raise ContinuationError("historical_artifacts_changed_during_read")
        return {"stored": stored, "events": events, "source_commit": commit,
                "artifact_sha256": dict(hashes), "summary": summary,
                "historical_directory": PAID_SMOKE_DIRECTORY}
    except (OSError, KeyError, TypeError, ValueError) as error:
        if isinstance(error, ContinuationError):
            raise
        raise ContinuationError("historical_smoke_evidence_invalid") from None


def _record(history: dict, source_commit: str, inputs: dict) -> dict:
    old = history["stored"]["run_config"]["input_hashes"]
    changed = sorted(name for name in set(old) | set(inputs) if old.get(name) != inputs.get(name))
    if set(changed) - _REPAIR_INPUTS:
        raise ContinuationError("scientific_inputs_changed")
    value = {"schema_version": 1, "classification": "prepared_source_version_not_execution",
             "continuation_id": "deepseek_primeintellect_v2", "authorization_id": PAID_SMOKE_AUTHORIZATION,
             "historical_directory": PAID_SMOKE_DIRECTORY, "active_directory": SEGMENT_DIRECTORY,
             "shared_session": "runs/_paid_testing_session", "historical_source_commit": history["source_commit"],
             "historical_artifact_sha256": history["artifact_sha256"],
             "historical_recorded_attempts": 1, "historical_successful_calls": 0,
             "unique_planned_cells": 80, "plan": history["stored"]["plan"],
             "active_source_commit": source_commit, "active_input_sha256": dict(inputs),
             "changed_input_paths": changed, "historical_replay_verified": True,
             "attempt_policy": "changed_request_is_source_version_reissue_not_identical_retry",
             "sample_policy": "same_80_logical_cells_no_prior_model_observation_to_resample",
             "allowance_policy": "shared_usd1_200_attempts_including_historical_attempt_no_reset"}
    return {**value, "record_hash": _hash(value)}


def _segment_path(root: Path) -> Path:
    path = root / SEGMENT_DIRECTORY
    if path.resolve() != path or not path.is_relative_to(root / "runs"):
        raise ContinuationError("continuation_segment_path_invalid")
    return path


def build_continuation_record(root: Path, *, source_commit: str, input_hashes: dict, replay_proof: dict) -> dict:
    """Prepare metadata only after exact historical replay and a code commit."""
    root = Path(root).resolve()
    if _segment_path(root).exists():
        raise ContinuationError("continuation_segment_already_exists")
    history = historical_smoke(root)
    if (not isinstance(replay_proof, dict)
            or any(replay_proof.get(key) is not True for key in
                   ("original_files_unchanged", "network_blocked", "credentials_removed"))
            or replay_proof.get("source_commit") != history["source_commit"]
            or replay_proof.get("artifact_sha256") != history["artifact_sha256"]
            or replay_proof.get("summary") != history["summary"]
            or replay_proof.get("input_hashes_verified") != len(history["stored"]["run_config"]["input_hashes"])):
        raise ContinuationError("historical_source_replay_not_verified")
    _verify_committed_inputs(root, source_commit, input_hashes)
    _verify_committed_inputs(root, history["source_commit"], history["stored"]["run_config"]["input_hashes"])
    return _record(history, source_commit, input_hashes)


def load_continuation(root: Path, *, input_hashes: dict) -> dict | None:
    """Validate the fixed preparation; absence never grants an alternate path."""
    root = Path(root).resolve()
    segment = _segment_path(root)
    path = root / CONTINUATION_RECORD
    if not path.exists():
        if segment.exists():
            raise ContinuationError("orphan_continuation_segment")
        return None
    if path.resolve() != path:
        raise ContinuationError("continuation_record_path_invalid")
    record = _read(path)
    if not isinstance(record, dict) or record.get("active_input_sha256") != input_hashes:
        raise ContinuationError("continuation_source_changed")
    if record.get("record_hash") != _hash({k: v for k, v in record.items() if k != "record_hash"}):
        raise ContinuationError("continuation_record_changed")
    history = historical_smoke(root)
    _verify_committed_inputs(root, record.get("active_source_commit"), input_hashes)
    _verify_committed_inputs(root, history["source_commit"], history["stored"]["run_config"]["input_hashes"])
    expected = _record(history, record["active_source_commit"], input_hashes)
    if record != expected:
        raise ContinuationError("continuation_record_changed")
    return record


def effective_smoke_directory(root: Path, *, input_hashes: dict) -> Path:
    root = Path(root).resolve()
    record = load_continuation(root, input_hashes=input_hashes)
    return _segment_path(root) if record else root / PAID_SMOKE_DIRECTORY
