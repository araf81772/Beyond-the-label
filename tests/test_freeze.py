"""Offline freeze verification with synthetic, explicitly mocked evidence.

These temporary fixtures exercise empirical-contract validation. They are not
real smoke/pilot observations, and no Git tag or execution freeze is created.
"""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace

import pytest

from beyond_label import freeze
from beyond_label.gates import pilot_thresholds
from beyond_label.run import build_manifest


COMMIT = "a" * 40
TAG = "fixture-freeze-only"


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(freeze, "ROOT", tmp_path)
    source = tmp_path / "src/beyond_label/fixture.py"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"# synthetic test source only\n")
    inputs = {"src/beyond_label/fixture.py": hashlib.sha256(source.read_bytes()).hexdigest()}
    monkeypatch.setattr(freeze, "_inputs", lambda: deepcopy(inputs))
    settings = {"model": "fixture/fixed:free", "provider": "Fixture Provider", "provider_route": "fixture",
                "provider_identity_source": "openrouter_metadata", "require_parameters": True,
                "temperature": 0.0, "reasoning": None, "max_output_tokens": 512, "free_only": True}
    raw_runs, summaries = {}, {}

    def add_run(name, dataset, load=2):
        directory = tmp_path / "runs" / name
        directory.mkdir(parents=True)
        plan = build_manifest(dataset, load)
        config = {"evidence_kind": "empirical", "provider_settings": deepcopy(settings),
                  "input_hashes": deepcopy(inputs), "execution_config": {"free_only": True}}
        stored = {"plan": plan, "run_config": config, "run_config_hash": freeze._hash({"plan": plan, "config": config}),
                  "fixture_classification": "SYNTHETIC UNIT TEST; REPLAY IS MOCKED"}
        files = {"manifest.json": (json.dumps(stored) + "\n").encode(),
                 "calls.jsonl": b'{"fixture":"synthetic mock; no model call occurred"}\n',
                 "scores.csv": b"fixture,synthetic_mock\n", "usage.csv": b"fixture,no_real_usage\n",
                 "analysis_manifest.json": b'{"fixture":"synthetic_mock"}\n'}
        for filename, content in files.items():
            (directory / filename).write_bytes(content)
        summary = {"evidence_kind": "empirical", "planned_cells": len(plan["cells"]),
                   "completed_cells": len(plan["cells"]), "pending_cells": 0,
                   "first_action_or_readback_missing": 0, "missingness": [], "successful_calls": len(plan["cells"]),
                   "invalid_first_actions": 3, "spend_evidence_complete": True,
                   "unknown_cost_attempts": 0, "accounting_error_attempts": 0,
                   "nonzero_cost_attempts": 0, "experimental_provider_spend": 0,
                   "cells": [{"cell_id": cell["cell_id"], "status": "completed", "missing_reason": None,
                              "continuation_status": "invalid:fixture" if index == 0 else "not_applicable"}
                             for index, cell in enumerate(plan["cells"])]}
        raw_runs[(dataset, load)] = files
        summaries[(dataset, load)] = summary
        return directory

    smoke = add_run("smoke-fixture", "smoke")
    pilot = add_run("pilot-fixture", "pilot")
    pilot_summary = {"evidence_kind": "empirical", "actual_pilot_verified": True,
                     "pilot_observations_complete": True, "actual_selected_load": 2,
                     "actual_model_change_decided": False, "freeze_eligible": False,
                     "human_review_verified": False, "provider_settings": deepcopy(settings),
                     "provenance": {name: hashlib.sha256(data).hexdigest()
                                    for name, data in raw_runs[("pilot", 2)].items()},
                     "counts": {"fully_correct_main_pairs": 13, "optimal_numeric_calls": 12,
                                "planned_main_pairs": 16, "complete_main_pairs": 16,
                                "planned_numeric_calls": 16, "observed_numeric_calls": 16},
                     "actual_threshold_evaluation": {**pilot_thresholds(13, 12), "actual_pilot_verified": True}}

    def replay(directory):
        stored = json.loads((directory / "manifest.json").read_bytes())
        key = (stored["plan"]["dataset"], stored["plan"]["load"])
        for filename in ("scores.csv", "usage.csv", "analysis_manifest.json"):
            (directory / filename).write_bytes(raw_runs[key][filename])
        return deepcopy(summaries[key])

    monkeypatch.setattr(freeze, "rebuild_outputs", replay)
    monkeypatch.setattr(freeze, "summarize_pilot", lambda directory: deepcopy(pilot_summary))
    plans = tmp_path / "data/plans"
    plans.mkdir(parents=True)
    for load in (2, 8):
        (plans / f"main_load{load}.json").write_text(json.dumps(build_manifest("main", load)), encoding="utf-8")

    def resolver(ref, path=None):
        if path is None:
            return COMMIT
        return (tmp_path / path).read_bytes()

    return {"root": tmp_path, "smoke": smoke, "pilot": pilot, "add_run": add_run,
            "settings": settings, "inputs": inputs, "summaries": summaries,
            "pilot_summary": pilot_summary, "resolver": resolver}


def prepare(evidence, **kwargs):
    return freeze.prepare_freeze(evidence["smoke"], evidence["pilot"], commit=COMMIT, tag=TAG,
                                 git_resolver=evidence["resolver"], **kwargs)


def test_prepare_and_verify_preserve_gate_artifacts_and_do_not_create_tag(evidence):
    before = {str(path): path.read_bytes() for path in evidence["root"].rglob("*") if path.is_file()}
    record = prepare(evidence)
    assert record["selected_load"] == 2
    assert record["real_smoke_passed"] is record["real_pilot_passed"] is True
    assert record["human_review_verified"] is False
    assert record["classification"] == "prepared_execution_freeze"
    verified = freeze.verify_freeze(record, build_manifest("main", 2), evidence["settings"],
                                    git_resolver=evidence["resolver"])
    assert verified["verified"] is True
    after = {str(path): path.read_bytes() for path in evidence["root"].rglob("*") if path.is_file()}
    assert before == after
    assert not (evidence["root"] / ".git").exists()


@pytest.mark.parametrize("field,value", [("pending_cells", 1), ("first_action_or_readback_missing", 1),
                                         ("completed_cells", 79), ("evidence_kind", "synthetic")])
def test_incomplete_or_synthetic_smoke_cannot_prepare_freeze(evidence, field, value):
    evidence["summaries"][("smoke", 2)][field] = value
    with pytest.raises(freeze.FreezeError):
        prepare(evidence)


@pytest.mark.parametrize("status", ["pending", "missing:timeout", "unexpected"])
def test_missing_smoke_continuation_blocks_but_observed_invalid_does_not(evidence, status):
    evidence["summaries"][("smoke", 2)]["cells"][0]["continuation_status"] = status
    with pytest.raises(freeze.FreezeError):
        prepare(evidence)


@pytest.mark.parametrize("change", ["floor", "incomplete", "wrong_selection", "model_change"])
def test_pilot_requires_complete_denominators_and_exact_threshold_decision(evidence, change):
    summary = evidence["pilot_summary"]
    if change == "floor": summary["counts"]["optimal_numeric_calls"] = 11
    elif change == "incomplete": summary["pilot_observations_complete"] = False
    elif change == "wrong_selection": summary["actual_selected_load"] = 8
    else: summary["actual_model_change_decided"] = True
    with pytest.raises(freeze.FreezeError):
        prepare(evidence)


def test_load8_selection_requires_matching_additional_real_smoke(evidence):
    summary = evidence["pilot_summary"]
    summary["counts"]["fully_correct_main_pairs"] = 14
    summary["actual_selected_load"] = 8
    summary["actual_threshold_evaluation"] = {**pilot_thresholds(14, 12), "actual_pilot_verified": True}
    with pytest.raises(freeze.FreezeError, match="load8"):
        prepare(evidence)
    extra = evidence["add_run"]("smoke8-fixture", "smoke", 8)
    record = prepare(evidence, smoke8_dir=extra)
    assert record["selected_load"] == 8
    freeze.verify_freeze(record, build_manifest("main", 8), evidence["settings"], git_resolver=evidence["resolver"])


@pytest.mark.parametrize("mutation", ["raw", "score", "inputs", "settings", "main_plan", "record_hash", "tag_commit", "commit_blob"])
def test_verify_rejects_changes_to_evidence_or_frozen_identity(evidence, mutation):
    record = prepare(evidence)
    plan, settings, resolver = build_manifest("main", 2), deepcopy(evidence["settings"]), evidence["resolver"]
    if mutation == "raw": (evidence["smoke"] / "calls.jsonl").write_bytes(b"changed\n")
    elif mutation == "score": (evidence["pilot"] / "scores.csv").write_bytes(b"changed\n")
    elif mutation == "inputs": evidence["inputs"]["src/beyond_label/fixture.py"] = "b" * 64
    elif mutation == "settings": settings["temperature"] = 0.1
    elif mutation == "main_plan": plan["cells"].pop()
    elif mutation == "record_hash": record["selected_load"] = 8
    elif mutation == "tag_commit": resolver = lambda ref, path=None: "b" * 40 if path is None else evidence["resolver"](ref, path)
    else: resolver = lambda ref, path=None: COMMIT if path is None else b"wrong committed bytes"
    with pytest.raises(freeze.FreezeError):
        freeze.verify_freeze(record, plan, settings, git_resolver=resolver)


def test_prefreeze_main_calls_block_preparation_but_not_verification_after_freeze(evidence):
    record = prepare(evidence)
    main = evidence["add_run"]("main-fixture", "main")
    with pytest.raises(freeze.FreezeError, match="main"):
        prepare(evidence)
    freeze.verify_freeze(record, build_manifest("main", 2), evidence["settings"], git_resolver=evidence["resolver"])
    assert (main / "calls.jsonl").is_file()


@pytest.mark.parametrize("commit,tag", [("abc", TAG), ("A" * 40, TAG), (COMMIT, "../escape"),
                                       (COMMIT, "x.lock"), (COMMIT, "x@{1}"), (COMMIT, "bad tag")])
def test_invalid_commit_or_tag_rejected_before_git_resolution(evidence, commit, tag):
    called = []
    with pytest.raises(freeze.FreezeError):
        freeze.prepare_freeze(evidence["smoke"], evidence["pilot"], commit=commit, tag=tag,
                              git_resolver=lambda *args: called.append(args))
    assert called == []


def test_synthetic_manifest_is_rejected_even_if_replay_was_forged_empirical(evidence):
    manifest_path = evidence["smoke"] / "manifest.json"
    stored = json.loads(manifest_path.read_bytes())
    stored["run_config"]["evidence_kind"] = "synthetic"
    manifest_path.write_text(json.dumps(stored), encoding="utf-8")
    with pytest.raises(freeze.FreezeError, match="empirical"):
        prepare(evidence)


@pytest.mark.parametrize("name", freeze.REQUIRED_FILES)
def test_all_five_gate_artifacts_are_required(evidence, name):
    (evidence["smoke"] / name).unlink()
    with pytest.raises(freeze.FreezeError):
        prepare(evidence)


def test_same_model_provider_and_sampling_settings_required_across_gate_runs(evidence):
    path = evidence["smoke"] / "manifest.json"
    stored = json.loads(path.read_bytes())
    stored["run_config"]["provider_settings"]["temperature"] = 0.5
    stored["run_config_hash"] = freeze._hash({"plan": stored["plan"], "config": stored["run_config"]})
    path.write_text(json.dumps(stored), encoding="utf-8")
    with pytest.raises(freeze.FreezeError, match="provider_settings"):
        prepare(evidence)


def test_preparation_rejects_uncommitted_input_or_main_manifest(evidence):
    with pytest.raises(freeze.FreezeError, match="committed"):
        freeze.prepare_freeze(evidence["smoke"], evidence["pilot"], commit=COMMIT, tag=TAG,
                              git_resolver=lambda ref, path=None: b"old committed source")


@pytest.mark.parametrize("field,value", [("schema_version", True), ("selected_load", 2.0),
                                         ("schedule_seed", True), ("human_review_verified", True),
                                         ("prepared_at_utc", "2026-11-14T12:00:00")])
def test_rehashed_record_cannot_invent_claims_or_invalid_identity_fields(evidence, field, value):
    record = prepare(evidence)
    record[field] = value
    record["record_hash"] = freeze._hash({key: value for key, value in record.items() if key != "record_hash"})
    with pytest.raises(freeze.FreezeError):
        freeze.verify_freeze(record, build_manifest("main", 2), evidence["settings"], git_resolver=evidence["resolver"])


def test_default_git_resolver_is_read_only_and_disables_implicit_fetch(monkeypatch):
    calls = []
    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=(COMMIT + "\n").encode())
    monkeypatch.setattr(freeze.subprocess, "run", fake_run)
    assert freeze._git_resolve("refs/tags/fixture") == COMMIT
    assert calls[0][0] == ["git", "rev-parse", "--verify", "refs/tags/fixture^{commit}"]
    assert calls[0][1]["env"]["GIT_NO_LAZY_FETCH"] == "1"
    assert calls[0][1]["env"]["GIT_TERMINAL_PROMPT"] == "0"
    calls.clear()
    assert freeze._git_resolve(COMMIT, "data/plans/main_load2.json") == (COMMIT + "\n").encode()
    assert calls[0][0] == ["git", "show", f"{COMMIT}:data/plans/main_load2.json"]


@pytest.mark.parametrize("dataset", ["smoke", "pilot"])
@pytest.mark.parametrize("field,value", [("spend_evidence_complete", False), ("spend_evidence_complete", 1),
                                         ("unknown_cost_attempts", 1), ("accounting_error_attempts", 1),
                                         ("nonzero_cost_attempts", 1), ("experimental_provider_spend", None),
                                         ("experimental_provider_spend", 0.001),
                                         ("experimental_provider_spend", False)])
def test_free_freeze_rejects_unknown_nonzero_or_failed_accounting(evidence, dataset, field, value):
    evidence["summaries"][(dataset, 2)][field] = value
    with pytest.raises(freeze.FreezeError, match="cost|accounting"):
        prepare(evidence)


@pytest.mark.parametrize("field", ["spend_evidence_complete", "unknown_cost_attempts",
                                   "accounting_error_attempts", "nonzero_cost_attempts", "experimental_provider_spend"])
def test_free_freeze_cannot_default_missing_cost_evidence_to_zero(evidence, field):
    evidence["summaries"][("smoke", 2)].pop(field)
    with pytest.raises(freeze.FreezeError, match="cost|accounting"):
        prepare(evidence)


@pytest.mark.parametrize("field", ["unknown_cost_attempts", "accounting_error_attempts", "nonzero_cost_attempts"])
@pytest.mark.parametrize("value", [False, "0", -1])
def test_cost_accounting_denominators_must_be_exact_nonnegative_integers(evidence, field, value):
    evidence["summaries"][("smoke", 2)][field] = value
    with pytest.raises(freeze.FreezeError, match="cost|accounting"):
        prepare(evidence)


@pytest.mark.parametrize("free_flag", [False, None])
def test_captured_provider_settings_must_explicitly_pin_free_only(evidence, free_flag):
    path = evidence["smoke"] / "manifest.json"
    stored = json.loads(path.read_bytes())
    if free_flag is None:
        stored["run_config"]["provider_settings"].pop("free_only")
    else:
        stored["run_config"]["provider_settings"]["free_only"] = free_flag
    stored["run_config_hash"] = freeze._hash({"plan": stored["plan"], "config": stored["run_config"]})
    path.write_text(json.dumps(stored), encoding="utf-8")
    with pytest.raises(freeze.FreezeError, match="free"):
        freeze._verified_run(evidence["smoke"], "smoke", 2, evidence["inputs"])


def test_load8_smoke_requires_the_same_zero_cost_evidence(evidence):
    summary = evidence["pilot_summary"]
    summary["counts"]["fully_correct_main_pairs"] = 14
    summary["actual_selected_load"] = 8
    summary["actual_threshold_evaluation"] = {**pilot_thresholds(14, 12), "actual_pilot_verified": True}
    extra = evidence["add_run"]("smoke8-fixture", "smoke", 8)
    evidence["summaries"][("smoke", 8)]["unknown_cost_attempts"] = 1
    with pytest.raises(freeze.FreezeError, match="cost|accounting"):
        prepare(evidence, smoke8_dir=extra)
