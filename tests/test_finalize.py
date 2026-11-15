"""Offline packaging must preserve raw evidence and never invent observations."""
import csv
import hashlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from beyond_label.finalize import finalize_planned, finalize_run, main
from beyond_label.provider import PinnedProvider, ProviderSettings
from beyond_label.run import ScriptedPublicPolicy, build_manifest, run_manifest


def snapshot(directory):
    return {path.relative_to(directory).as_posix(): path.read_bytes()
            for path in directory.rglob("*") if path.is_file()}


@pytest.fixture(scope="module")
def stored_main(tmp_path_factory):
    directory = tmp_path_factory.mktemp("finalize-source")
    fixture = ScriptedPublicPolicy()
    provider = PinnedProvider(ProviderSettings(model=fixture.model, provider=fixture.provider), fixture)
    # Find a deterministic schedule whose small prefix contains a worked pair;
    # never alter the prescribed manifest or select empirical observations.
    for seed in range(1000):
        manifest = build_manifest("main", schedule_seed=seed)
        pairs = {}
        for cell in manifest["cells"][:16]:
            if cell["purpose"] == "decision" and cell["condition"] == "MAIN" and cell["layout"] == "separate":
                pairs.setdefault(cell["world_seed"], set()).add(cell["twin"])
        if any(twins == {"a", "b"} for twins in pairs.values()):
            break
    else:
        pytest.fail("Synthetic fixture schedule not found")
    run_manifest(manifest, directory, provider, max_cells=16)
    return directory


def test_planned_bundle_has_only_unexecuted_status_and_null_observed_metrics(tmp_path, monkeypatch):
    def no_observational_work(*args, **kwargs):
        pytest.fail("Planned mode must not analyze observations or invent figures/traces")
    for name in ("analyze_run", "export_evidence", "write_figures"):
        monkeypatch.setattr("beyond_label.finalize." + name, no_observational_work)
    result = finalize_planned(tmp_path / "planned")
    planned = json.loads((tmp_path / "planned/planned_status.json").read_text("utf-8"))
    assert planned["planned_cells"] == 704 and planned["unexecuted_cells"] == 704
    assert planned["observed_cells"] == planned["infrastructure_missing_cells"] == 0
    assert planned["counts"] == {"MAIN": 256, "READBACK": 256, "HIGH-FEE": 64,
                                 "HIGH-STAKES": 64, "MASKED": 32, "NUMERIC": 32}
    assert planned["primary_effect"] is None and planned["ci95"] is None
    assert planned["sign_test_p_value"] is None and planned["observed_regret"] is None
    assert planned["execution_freeze_verified"] is False and "execution_freeze_exists" not in planned
    assert planned["oracle_references"]["evidence_kind"] == "analytic_reference_not_observation"
    assert planned["oracle_references"]["primary_D"] == 1.0
    assert result["milestone_6_complete"] is False and result["publication_performed"] is False
    assert set(snapshot(tmp_path / "planned")) == {"planned_status.json", "status.csv", "bundle_manifest.json"}
    with (tmp_path / "planned/status.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 6 and all(row["status"] == "unexecuted" for row in rows)


def test_synthetic_packaging_requires_explicit_opt_in_and_rejects_output_overlap(stored_main, tmp_path):
    before = snapshot(stored_main)
    with pytest.raises(ValueError, match="Synthetic"):
        finalize_run(stored_main, tmp_path / "default")
    assert not (tmp_path / "default").exists()
    for output in (stored_main, stored_main / "analysis", stored_main.parent):
        with pytest.raises(ValueError, match="overlap"):
            finalize_run(stored_main, output, allow_synthetic=True)
    assert snapshot(stored_main) == before


def test_stored_main_bundle_is_labelled_trace_derived_and_source_immutable(stored_main, tmp_path):
    before = snapshot(stored_main)
    output = tmp_path / "bundle"
    result = finalize_run(stored_main, output, allow_synthetic=True)
    assert snapshot(stored_main) == before
    assert result["evidence_kind"] == "synthetic" and result["empirical_observations"] == 0
    assert result["completeness"]["planned_cells"] == 704
    assert result["completeness"]["completed_cells"] == 16
    assert result["completeness"]["all_cells_terminal"] is False
    assert result["milestone_6_complete"] is False and result["publication_performed"] is False
    summary = json.loads((output / "execution_summary.json").read_text("utf-8"))
    source_summary = json.loads(before["analysis_manifest.json"])
    assert summary == result["execution_summary"]
    assert summary["attempted_calls"] == source_summary["attempted_calls"]
    assert summary["successful_calls"] == source_summary["successful_calls"]
    assert summary["infrastructure_retries"] == source_summary["infrastructure_retries"]
    assert summary["cost"]["evidence_kind"] == "synthetic_fixture_not_billed"
    assert summary["cost"]["total_provider_spend_usd"] is None
    for filename, digest in result["source_hashes"].items():
        assert hashlib.sha256(before[filename]).hexdigest() == digest
    generated = snapshot(output)
    assert set(result["artifact_hashes"]) == set(generated) - {"bundle_manifest.json"}
    for filename, digest in result["artifact_hashes"].items():
        assert hashlib.sha256(generated[filename]).hexdigest() == digest
    analysis = json.loads((output / "analysis/analysis.json").read_text("utf-8"))
    assert analysis["primary"]["estimate"]["bootstrap_seed"] == 314159
    assert analysis["primary"]["estimate"]["bootstrap_resamples"] == 10000
    worked = json.loads((output / "analysis/matched_trace.json").read_text("utf-8"))
    assert worked["status"] == "trace_derived" and len(worked["twins"]) == 2
    assert worked["human_review"] is False and "SYNTHETIC" in worked["artifact_label"]
    assert b"SYNTHETIC" in (output / "analysis/figures/agent_allocation_vs_oracle.png").read_bytes()
    with (output / "analysis/claim_evidence.csv").open(encoding="utf-8", newline="") as stream:
        claims = list(csv.DictReader(stream))
    assert claims and all("beyond_label.finalize" in row["regenerate_command"] for row in claims)
    assert all("btl-finalize-" not in row["regenerate_command"] for row in claims)
    # Reproduction is idempotent and verifies, rather than overwrites, outputs.
    assert finalize_run(stored_main, output, allow_synthetic=True) == result
    assert snapshot(output) == generated and snapshot(stored_main) == before


@pytest.mark.parametrize("filename", ["calls.jsonl", "scores.csv", "usage.csv"])
def test_tampered_raw_or_derived_evidence_is_rejected_without_source_repair(stored_main, tmp_path, filename):
    source = tmp_path / "source"
    shutil.copytree(stored_main, source)
    target = source / filename
    if filename == "calls.jsonl":
        target.write_bytes(target.read_bytes().replace(b'"event":"phase_defined"', b'"event":"phase_tampered"', 1))
    else:
        target.write_bytes(target.read_bytes() + b"tampered\n")
    before = snapshot(source)
    with pytest.raises(ValueError):
        finalize_run(source, tmp_path / "bundle", allow_synthetic=True)
    assert snapshot(source) == before and not (tmp_path / "bundle").exists()


@pytest.mark.parametrize("dataset", ["smoke", "pilot"])
def test_non_main_runs_cannot_be_packaged_as_main(stored_main, tmp_path, dataset):
    source = tmp_path / "source"
    shutil.copytree(stored_main, source)
    path = source / "manifest.json"
    stored = json.loads(path.read_text("utf-8"))
    stored["plan"]["dataset"] = dataset
    path.write_text(json.dumps(stored), encoding="utf-8")
    with pytest.raises(ValueError, match="main"):
        finalize_run(source, tmp_path / "bundle", allow_synthetic=True)


def test_empirical_relabel_does_not_bypass_existing_provenance_and_freeze_checks(stored_main, tmp_path):
    source = tmp_path / "source"
    shutil.copytree(stored_main, source)
    path = source / "manifest.json"
    stored = json.loads(path.read_text("utf-8"))
    stored["run_config"]["evidence_kind"] = "empirical"
    stored["run_config"]["transport_provenance"] = "openrouter_free_https_v1"
    from beyond_label.run import _hash
    stored["run_config_hash"] = _hash({"plan": stored["plan"], "config": stored["run_config"]})
    path.write_text(json.dumps(stored), encoding="utf-8")
    with pytest.raises(ValueError):
        finalize_run(source, tmp_path / "bundle")
    assert not (tmp_path / "bundle").exists()


def test_missing_required_source_and_existing_output_are_not_silently_repaired(stored_main, tmp_path):
    source = tmp_path / "source"
    shutil.copytree(stored_main, source)
    (source / "usage.csv").unlink()
    with pytest.raises(ValueError, match="required"):
        finalize_run(source, tmp_path / "bundle", allow_synthetic=True)
    existing = tmp_path / "existing"
    existing.mkdir()
    (existing / "user.txt").write_text("preserve me", encoding="utf-8")
    before = snapshot(existing)
    with pytest.raises(ValueError, match="output"):
        finalize_planned(existing)
    assert snapshot(existing) == before


@pytest.mark.parametrize("flags", [[], ["--planned", "--run", "missing"], ["--planned", "--allow-synthetic"]])
def test_cli_rejects_mode_confusion_without_creating_artifacts(tmp_path, flags):
    output = tmp_path / "bundle"
    with pytest.raises(SystemExit) as error:
        main([*flags, "--output", str(output)])
    assert error.value.code == 2 and not output.exists()


def test_planned_cli_is_offline_and_reproducible(tmp_path, capsys):
    output = tmp_path / "bundle"
    assert main(["--planned", "--output", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["evidence_kind"] == "unexecuted"
    before = snapshot(output)
    assert finalize_planned(output)["evidence_kind"] == "unexecuted"
    assert snapshot(output) == before


def test_terminal_predispatch_failure_is_missing_not_unexecuted():
    from beyond_label.finalize import _completeness
    analysis = {"planned_cells": 3, "observed_cells": 0,
                "missing_reasons": {"credential_or_header_in_request": 1, "not_executed_yet": 2},
                "cells": [{"cell_id": "terminal", "observed": False, "cell_status": "completed", "continuation_status": "not_applicable"},
                          {"cell_id": "pending", "observed": False, "cell_status": "pending"},
                          {"cell_id": "interrupted", "observed": False, "cell_status": "pending"}]}
    execution = {"completed_cells": 1, "pending_cells": 2}
    journal = SimpleNamespace(events=[{"event": "attempt_started", "cell_id": "interrupted"}])
    counts = _completeness(analysis, execution, journal)
    assert counts["infrastructure_missing_cells"] == 1
    assert counts["unexecuted_cells"] == 1 and counts["unresolved_attempt_cells"] == 1
    assert counts["missing_first_action_or_readback_cells"] == 3


@pytest.mark.parametrize("unknown", [0, 1])
def test_execution_summary_preserves_cost_unknowns_and_does_not_claim_http_deliveries(unknown):
    from beyond_label.finalize import _execution_summary
    # Fabricated unit-test inputs only; no empirical bundle or trace is created.
    source = {"evidence_kind": "empirical", "attempted_calls": 2, "successful_calls": 1,
              "infrastructure_retries": 1, "permitted_reprompts": 0, "continuations": 0,
              "invalid_first_actions": 0, "spend_evidence_complete": unknown == 0,
              "known_provider_spend_usd": 0.001, "experimental_provider_spend": 0.001,
              "unknown_cost_attempts": unknown, "accounting_error_attempts": 0, "nonzero_cost_attempts": 1}
    summary = _execution_summary(source, "UNIT TEST INPUT ONLY")
    assert summary["cost"]["total_provider_spend_usd"] == (None if unknown else 0.001)
    assert summary["cost"]["known_provider_spend_usd"] == 0.001
    assert summary["cost"]["unknown_cost_attempts"] == unknown
    assert summary["confirmed_http_deliveries"] is None
    assert "do not prove HTTP dispatch" in summary["count_definitions"]["attempted_calls"]
