"""Offline preservation checks on isolated copies of retained empirical evidence.

The copies remain empirical historical fixtures; generated suffix events below
are deliberately synthetic and are never written to the repository's runs.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys

import pytest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/verify_main_continuation.py"
PENDING = "main-2061-readback-MAIN-inline-b"
TERMINAL = "main-2013-decision-HIGH-STAKES-inline-a"


def verifier():
    assert SCRIPT.is_file(), "The read-only continuation verifier is not implemented"
    spec = importlib.util.spec_from_file_location("main_continuation_verifier", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def stopped_copy(tmp_path):
    freeze = json.loads((REPO / "research/execution_freeze.json").read_bytes())
    paths = set(freeze["input_hashes"])
    paths.add("research/execution_freeze.json")
    paths.add(freeze["main_manifest_path"])
    for gate in freeze["gate_evidence"].values():
        paths.update(gate["directory"] + "/" + name for name in gate["files"])
    paths.update("runs/staged_main/" + name for name in (
        "manifest.json", "calls.jsonl", "scores.csv", "usage.csv", "analysis_manifest.json"))
    paths.update("runs/_paid_staged_session/" + name for name in (
        "authorization.json", "budget.jsonl", "attempts.jsonl"))
    for relative in paths:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / relative, destination)
    return tmp_path


def file_hashes(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file()}


def append_synthetic_event(path, body):
    previous = json.loads(path.read_bytes().splitlines()[-1])
    event = {**body, "sequence": previous["sequence"] + 1,
             "previous_hash": previous["event_hash"]}
    encoded = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    event["event_hash"] = hashlib.sha256(encoded).hexdigest()
    with path.open("ab") as stream:
        stream.write(json.dumps(event, sort_keys=True, separators=(",", ":"),
                                ensure_ascii=False).encode() + b"\n")


def test_exact_remaining_schedule_is_reported_without_writes_or_network(stopped_copy, monkeypatch):
    module = verifier()
    before = file_hashes(stopped_copy)

    def no_network(*args, **kwargs):
        raise AssertionError("Offline verification attempted network access")

    monkeypatch.setattr(socket, "socket", no_network)
    result = module.verify_continuation(stopped_copy)
    assert file_hashes(stopped_copy) == before
    assert result["classification"] == "offline_continuation_proposal_not_execution_authorization"
    assert result["dispatch_allowed"] is False
    assert result["blocking_reason"] == "staged_unknown_cost_hold_limit_reached"
    assert "fewer_than_40_unresolved_holds_within_unchanged_caps" in result["current_policy_requirements"]
    alternative = result["operational_amendment_alternative"]
    assert alternative["status"] == "proposed_not_approved_not_implemented"
    assert alternative["dispatch_allowed"] is False
    assert alternative["requires_explicit_approval"] is True
    assert result["frozen_inputs_verified"] == 50
    assert result["main"]["completed_cells"] == 652
    assert result["main"]["eligible_cells"] == 52
    assert result["main"]["untouched_cells"] == 51
    ids = result["main"]["eligible_cell_ids"]
    plan = json.loads((stopped_copy / "data/plans/main_load8.json").read_bytes())
    assert ids == [cell["cell_id"] for cell in plan["cells"][652:]]
    assert ids[:4] == [PENDING, "main-2012-decision-MAIN-separate-a",
                       "main-2019-decision-MAIN-inline-a", "main-2002-decision-MAIN-separate-b"]
    assert TERMINAL not in ids
    retry = result["main"]["pending_retry"]
    assert retry["cell_id"] == PENDING
    assert retry["completed_failed_attempts"] == [1, 2]
    assert retry["next_attempt"] == 3 and retry["maximum_attempt"] == 4
    assert result["main"]["forbidden_terminal_retry"]["cell_id"] == TERMINAL
    assert result["budget"]["unknown_cost_holds"] == 40
    assert result["budget"]["held_usd"] == "1.93872838656"
    assert result["budget"]["known_settled_usd"] == "0.19176235952"
    assert result["attempts"]["consumed"] == 1561
    assert result["attempts"]["remaining"] == 1439
    assert result["control_prefixes"]["budget.jsonl"]["events"] == 3123
    assert result["control_prefixes"]["attempts.jsonl"]["events"] == 1562


@pytest.mark.parametrize("relative", [
    "runs/staged_main/scores.csv", "runs/staged_main/usage.csv",
    "runs/staged_main/manifest.json", "runs/staged_main/analysis_manifest.json",
])
def test_changed_stopped_artifact_is_rejected(stopped_copy, relative):
    module = verifier()
    path = stopped_copy / relative
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(module.ContinuationVerificationError, match="stopped_main_artifact_changed"):
        module.verify_continuation(stopped_copy)


def test_new_completed_event_cannot_reuse_stale_52_cell_proposal(stopped_copy):
    module = verifier()
    append_synthetic_event(stopped_copy / "runs/staged_main/calls.jsonl", {
        "event": "cell_completed", "cell_id": PENDING,
        "first_missing_reason": "synthetic_test_only", "continuation_status": "not_applicable"})
    with pytest.raises(module.ContinuationVerificationError, match="stopped_main_artifact_changed"):
        module.verify_continuation(stopped_copy)


@pytest.mark.parametrize("name", ["budget.jsonl", "attempts.jsonl"])
def test_rewritten_control_prefix_is_rejected(stopped_copy, name):
    module = verifier()
    path = stopped_copy / "runs/_paid_staged_session" / name
    raw = path.read_bytes()
    path.write_bytes(b" " + raw[1:])
    with pytest.raises(module.ContinuationVerificationError, match="staged_control_prefix_changed"):
        module.verify_continuation(stopped_copy)


@pytest.mark.parametrize("name,body", [
    ("budget.jsonl", {"event": "settled", "attempt_id": "attempt-725442b9c41c40a5a16f386363f411bf",
                       "actual_cost": "0", "currency": "USD"}),
    ("attempts.jsonl", {"event": "attempt_reserved", "ordinal": 1562}),
])
def test_new_control_events_require_review_even_when_prefix_and_chain_survive(stopped_copy, name, body):
    module = verifier()
    append_synthetic_event(stopped_copy / "runs/_paid_staged_session" / name, body)
    with pytest.raises(module.ContinuationVerificationError, match="staged_control_append_requires_review"):
        module.verify_continuation(stopped_copy)


def test_changed_frozen_input_is_rejected(stopped_copy):
    module = verifier()
    path = stopped_copy / "prompts/reprompt_no_tool.txt"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(module.ContinuationVerificationError, match="frozen_input_changed"):
        module.verify_continuation(stopped_copy)


def test_added_experiment_module_is_rejected(stopped_copy):
    module = verifier()
    (stopped_copy / "src/beyond_label/injected.py").write_text("# synthetic test only\n")
    with pytest.raises(module.ContinuationVerificationError, match="frozen_input_set_changed"):
        module.verify_continuation(stopped_copy)


def test_modified_freeze_and_gate_evidence_are_rejected(stopped_copy):
    module = verifier()
    path = stopped_copy / "research/execution_freeze.json"
    original = path.read_bytes()
    path.write_bytes(original + b" ")
    with pytest.raises(module.ContinuationVerificationError, match="execution_freeze_changed"):
        module.verify_continuation(stopped_copy)
    path.write_bytes(original)
    gate = stopped_copy / "runs/staged_smoke_load2/usage.csv"
    gate.write_bytes(gate.read_bytes() + b" ")
    with pytest.raises(module.ContinuationVerificationError, match="frozen_gate_artifact_changed"):
        module.verify_continuation(stopped_copy)


def test_cli_only_writes_explicit_exclusive_report_output(stopped_copy):
    verifier()
    before = file_hashes(stopped_copy)
    command = [sys.executable, str(SCRIPT), "--root", str(stopped_copy)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["dispatch_allowed"] is False
    assert file_hashes(stopped_copy) == before
    report = stopped_copy / "proposal.json"
    written = subprocess.run(command + ["--output", str(report)], capture_output=True, text=True, check=False)
    assert written.returncode == 0, written.stderr
    assert json.loads(report.read_bytes())["main"]["eligible_cells"] == 52
    previous = report.read_bytes()
    refused = subprocess.run(command + ["--output", str(report)], capture_output=True, text=True, check=False)
    assert refused.returncode == 2
    assert report.read_bytes() == previous
