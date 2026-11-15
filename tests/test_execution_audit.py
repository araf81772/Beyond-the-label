"""Execution-status audit tests use temporary local fixtures, never observations."""
import importlib.util
import json
from pathlib import Path
import shutil

import pytest

from beyond_label import run
from test_free_run import free_fixture


def script(name):
    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = script("verify_audit")


def status(calls=0, freeze=None):
    return {"experimental_calls": calls, "execution_freeze": freeze,
            "milestones": [{"number": i, "status": "complete" if i < 4 else "blocked"}
                           for i in range(1, 7)]}


def empirical_fixture(root, monkeypatch):
    # Explicit test-only seam exercising empirical labels; no HTTP exists here.
    config, _, provider = free_fixture()
    monkeypatch.setattr(run, "_validate_live_transport", lambda _: None)
    directory = root / "runs" / "smoke_fixture"
    result = run.run_manifest(run.build_manifest("smoke"), directory, provider,
                              execution_config=config, synthetic=False, max_cells=2)
    return directory, result


def test_empty_inventory_accepts_only_zero_calls_and_no_freeze(tmp_path):
    result = audit.validate_execution_evidence(tmp_path, status())
    assert result["recorded_request_attempts"] == 0
    assert result["freeze"] is None and result["empirical_runs"] == []
    with pytest.raises(ValueError, match="count"):
        audit.validate_execution_evidence(tmp_path, status(calls=1))
    with pytest.raises(ValueError):
        audit.validate_execution_evidence(tmp_path, status(calls=True))


def test_verified_partial_fixture_reconciles_counts_without_modifying_artifacts(tmp_path, monkeypatch):
    directory, summary = empirical_fixture(tmp_path, monkeypatch)
    before = {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}
    result = audit.validate_execution_evidence(tmp_path, status(summary["attempted_calls"]))
    assert result["successful_calls"] == summary["successful_calls"]
    assert result["empirical_runs"][0]["dataset"] == "smoke"
    assert result["empirical_runs"][0]["pending_cells"] == 78
    assert before == {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}


@pytest.mark.parametrize("damage", ["missing_usage", "altered_scores", "missing_manifest", "duplicate_run"])
def test_incomplete_tampered_or_duplicated_evidence_cannot_validate_status(tmp_path, monkeypatch, damage):
    directory, summary = empirical_fixture(tmp_path, monkeypatch)
    if damage == "missing_usage":
        (directory / "usage.csv").unlink()
    elif damage == "altered_scores":
        with (directory / "scores.csv").open("ab") as stream:
            stream.write(b"unexpected\n")
    elif damage == "missing_manifest":
        (directory / "manifest.json").unlink()
    else:
        shutil.copytree(directory, directory.with_name("copied_fixture"))
    claimed = summary["attempted_calls"] * (2 if damage == "duplicate_run" else 1)
    with pytest.raises(ValueError):
        audit.validate_execution_evidence(tmp_path, status(claimed))


def test_synthetic_fixture_is_separate_and_does_not_count_as_empirical(tmp_path):
    policy = run.ScriptedPublicPolicy()
    from beyond_label.provider import PinnedProvider, ProviderSettings
    provider = PinnedProvider(ProviderSettings(model=policy.model, provider=policy.provider), policy)
    run.run_manifest(run.build_manifest("smoke"), tmp_path / "runs/synthetic_fixture", provider, max_cells=1)
    result = audit.validate_execution_evidence(tmp_path, status())
    assert result["recorded_request_attempts"] == 0
    assert result["synthetic_run_directories"] == ["runs/synthetic_fixture"]


def test_changing_only_evidence_label_cannot_hide_recorded_attempts(tmp_path, monkeypatch):
    directory, _ = empirical_fixture(tmp_path, monkeypatch)
    path = directory / "manifest.json"
    stored = json.loads(path.read_text("utf-8"))
    stored["run_config"]["evidence_kind"] = "synthetic"
    path.write_text(json.dumps(stored), encoding="utf-8")
    with pytest.raises(ValueError):
        audit.validate_execution_evidence(tmp_path, status())


@pytest.mark.parametrize("milestone", [4, 5, 6])
def test_completion_without_required_empirical_evidence_is_rejected(tmp_path, milestone):
    record = status()
    record["milestones"][milestone - 1]["status"] = "complete"
    with pytest.raises(ValueError):
        audit.validate_execution_evidence(tmp_path, record)


def test_nonnull_freeze_requires_full_verification_not_a_tag_string(tmp_path, monkeypatch):
    from beyond_label import freeze
    calls = []
    def reject(record, plan, settings):
        calls.append((record, plan, settings))
        raise ValueError("fixture freeze rejected")
    monkeypatch.setattr(freeze, "verify_freeze", reject)
    record = {"selected_load": 2, "schedule_seed": 271828,
              "provider_settings": {}, "record_hash": "unverified"}
    with pytest.raises(ValueError):
        audit.validate_execution_evidence(tmp_path, status(freeze=record))
    assert len(calls) == 1
    path = tmp_path / "research/freeze.json"
    path.parent.mkdir()
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError):
        audit.validate_execution_evidence(tmp_path, status(freeze="research/freeze.json"))
    assert len(calls) == 2
    with pytest.raises(ValueError):
        audit.validate_execution_evidence(tmp_path, status(freeze="../outside.json"))
    assert len(calls) == 2


def test_verified_freeze_allows_m4_but_does_not_invent_completed_main(tmp_path, monkeypatch):
    # Isolated verifier contract fixture; no actual freeze or tag is created.
    from beyond_label import freeze
    record = {"selected_load": 2, "schedule_seed": 271828,
              "provider_settings": {}, "record_hash": "fixture-only"}
    proof = {"verified": True, "record_hash": "fixture-only"}
    monkeypatch.setattr(freeze, "verify_freeze", lambda *_: proof)
    milestones = status(freeze=record)
    milestones["milestones"][3]["status"] = "complete"
    assert audit.validate_execution_evidence(tmp_path, milestones)["freeze"] == proof
    milestones["milestones"][4]["status"] = "complete"
    with pytest.raises(ValueError, match="main evidence"):
        audit.validate_execution_evidence(tmp_path, milestones)
