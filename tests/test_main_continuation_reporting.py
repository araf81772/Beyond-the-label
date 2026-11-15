"""Offline reporting contracts; modified journals exist only in test directories."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest

from beyond_label import freeze, run


REPO = Path(__file__).resolve().parents[1]
CHILD = "continuations/staged_main_52_20261116"
PARENT = "runs/staged_main"


def script(name):
    path = REPO / "scripts" / (name + ".py")
    assert path.is_file(), "Continuation reporting is not implemented"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_absent_child_does_not_select_an_operational_continuation(tmp_path):
    assert script("main_continuation_reporting").continuation_evidence(tmp_path) is None


def test_unrecognized_child_is_rejected_even_without_canonical_child(tmp_path):
    directory = tmp_path / "continuations/unapproved"
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text("{}")
    with pytest.raises(ValueError, match="Unrecognized main continuation"):
        script("main_continuation_reporting").continuation_evidence(tmp_path)


def test_existing_child_cannot_skip_operational_validation(tmp_path, monkeypatch):
    (tmp_path / CHILD).mkdir(parents=True)
    def reject(*args, **kwargs):
        raise ValueError("synthetic missing operational approval")
    monkeypatch.setitem(sys.modules, "execute_main_continuation", SimpleNamespace(
        verify_operational_freeze=reject, verify_child_metadata=reject))
    with pytest.raises(ValueError, match="missing operational approval"):
        script("main_continuation_reporting").continuation_evidence(tmp_path)


@pytest.fixture
def composite_copy(tmp_path, monkeypatch):
    """Copied empirical prefix plus explicitly simulated test-only suffix."""
    parent, child = tmp_path / PARENT, tmp_path / CHILD
    parent.parent.mkdir(parents=True)
    shutil.copytree(REPO / PARENT, parent, ignore=shutil.ignore_patterns("*.writer.lock"))
    child.parent.mkdir(parents=True)
    shutil.copytree(parent, child)
    stored = json.loads((child / "manifest.json").read_bytes())
    stored["continuation"] = {"classification": "synthetic_operational_metadata_contract_fixture"}
    (child / "manifest.json").write_text(json.dumps(stored), encoding="utf-8")
    monkeypatch.setattr(freeze, "verify_freeze", lambda *args, **kwargs: {"verified": True})
    evidence = {
        "directory": CHILD, "parent_directory": PARENT,
        "operational_freeze": {"record_hash": "synthetic-operational-freeze", "source_commit": "fixture"},
        "metadata": stored["continuation"],
        "accounting": {"source_directory": CHILD, "journaled_attempts": 1561,
                       "inherited_main_attempts": 1036, "new_main_attempts": 0,
                       "completed_cells": 652, "pending_cells": 52,
                       "known_receipts": 1521, "held_reservations": 40,
                       "held_usd": "1.93872838656", "available_usd": "6.86950925392"},
    }
    return tmp_path, parent, child, evidence


def test_sync_counts_composite_main_once_and_retains_parent(composite_copy, monkeypatch):
    root, parent, child, evidence = composite_copy
    sync = script("sync_execution_status")
    monkeypatch.setattr(sync, "continuation_evidence", lambda _: evidence)
    before = (parent / "calls.jsonl").read_bytes()
    counts = sync.count_attempts(root)
    assert counts == {CHILD: 1036}
    assert (parent / "calls.jsonl").read_bytes() == before


def test_audit_replays_both_snapshots_but_counts_one_logical_main(composite_copy, monkeypatch):
    root, parent, child, evidence = composite_copy
    audit = script("verify_audit")
    monkeypatch.setattr(audit, "continuation_evidence", lambda _: evidence)
    journal = run.Journal(child / "calls.jsonl")
    previous = journal.events[-1]
    # Simulate one additional failed infrastructure attempt, only in this fixture.
    start = {key: previous[key] for key in ("cell_id", "phase", "request_hash", "payload")}
    journal.append({**start, "event": "attempt_started", "attempt": 3, "usage": {}, "latency_seconds": 0.0})
    failed = {key: value for key, value in previous.items()
              if key not in {"sequence", "previous_hash", "event_hash"}}
    journal.append({**failed, "attempt": 3})
    run.rebuild_outputs(child)
    evidence["accounting"].update(journaled_attempts=1562, new_main_attempts=1)
    milestones = {"experimental_calls": 1037,
                  "execution_freeze": json.loads((REPO / "research/execution_freeze.json").read_bytes()),
                  "milestones": [{"number": n, "status": "in_progress"} for n in range(1, 7)]}
    before = {name: (parent / name).read_bytes() for name in run_artifacts()}
    result = audit.validate_execution_evidence(root, milestones)
    assert result["recorded_request_attempts"] == 1037
    mains = [entry for entry in result["empirical_runs"] if entry["dataset"] == "main"]
    assert len(mains) == 1 and mains[0]["directory"] == CHILD
    assert mains[0]["continuation_provenance"] == evidence
    assert result["historical_main_snapshots"][0]["directory"] == PARENT
    assert result["historical_main_snapshots"][0]["attempted_calls"] == 1036
    assert before == {name: (parent / name).read_bytes() for name in run_artifacts()}


def run_artifacts():
    return ("manifest.json", "calls.jsonl", "scores.csv", "usage.csv", "analysis_manifest.json")


def test_finalizer_blocks_unfinished_child_without_creating_results(composite_copy, monkeypatch):
    root, _, _, evidence = composite_copy
    wrapper = script("finalize_main_continuation")
    monkeypatch.setattr(wrapper, "continuation_evidence", lambda _: evidence)
    with pytest.raises(ValueError, match="unfinished"):
        wrapper.finalize_continuation(root)
    assert not (root / "results").exists()


def test_finalizer_publishes_operational_provenance_without_overwriting_partial_results(composite_copy, monkeypatch):
    root, parent, child, evidence = composite_copy
    wrapper = script("finalize_main_continuation")
    monkeypatch.setattr(wrapper, "continuation_evidence", lambda _: evidence)
    stored = json.loads((child / "manifest.json").read_bytes())
    journal = run.Journal(child / "calls.jsonl")
    # Test-only terminal missingness fixtures exercise packaging without inference.
    for cell in stored["plan"]["cells"][652:]:
        journal.append({"event": "cell_completed", "cell_id": cell["cell_id"],
                        "first_missing_reason": "synthetic_test_only_missing_observation",
                        "continuation_status": "not_applicable"})
    run.rebuild_outputs(child)
    evidence["accounting"].update(completed_cells=704, pending_cells=0)
    partial = root / "results/staged_main"
    partial.mkdir(parents=True)
    (partial / "preserve.txt").write_text("retained partial bundle")
    before = {name: (parent / name).read_bytes() for name in run_artifacts()}
    result = wrapper.finalize_continuation(root)
    output = root / "results/staged_main_complete"
    assert (partial / "preserve.txt").read_text() == "retained partial bundle"
    assert before == {name: (parent / name).read_bytes() for name in run_artifacts()}
    assert result["continuation_provenance"]["directory"] == CHILD
    assert result["completeness"]["completed_cells"] == 704
    assert result["completeness"]["all_observations_available"] is False
    assert result["execution_summary"]["cost"]["total_provider_spend_usd"] is None
    assert result["reproduction"]["script"] == "scripts/finalize_main_continuation.py"
    for name, digest in result["artifact_hashes"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest
    assert "continuation_provenance.json" in result["artifact_hashes"]
    with (output / "analysis/claim_evidence.csv").open(encoding="utf-8", newline="") as stream:
        assert all("finalize_main_continuation.py" in row["regenerate_command"] for row in csv.DictReader(stream))
    assert wrapper.finalize_continuation(root) == result
    with pytest.raises(ValueError, match="partial"):
        wrapper.finalize_continuation(root, partial)
