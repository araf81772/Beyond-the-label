"""Pilot thresholds and provenance tested with explicitly synthetic fixtures."""
import hashlib
import json
import shutil

import pytest

from beyond_label.analyze import analyze_rows
from beyond_label.pilot import REQUIRED_FILES, _summarize_verified, summarize_pilot
from beyond_label.provider import PinnedProvider, ProviderSettings
from beyond_label.run import Journal, ScriptedPublicPolicy, build_manifest, case_for_cell, run_manifest
from beyond_label.schemas import ModelReply, ToolCall
from beyond_label.score import score_first_action


def threshold_fixture(correct_pairs=14, optimal_numeric=12, invalid=False):
    plan = build_manifest("pilot")
    pair_order = [(seed, layout) for seed in range(1000, 1008) for layout in ("separate", "inline")]
    numeric_order = [(seed, twin) for seed in range(1000, 1008) for twin in ("a", "b")]
    rows = []
    for cell in plan["cells"]:
        if cell["purpose"] == "readback":
            rows.append({**cell, "evidence_kind": "synthetic", "readback_correct": True})
            continue
        case = case_for_cell(cell, plan)
        choice = 0
        correct = True
        if cell["condition"] == "MAIN":
            correct = pair_order.index((cell["world_seed"], cell["layout"])) < correct_pairs
            choice = 0 if cell["twin"] == "a" else 1
        if cell["condition"] == "NUMERIC":
            correct = numeric_order.index((cell["world_seed"], cell["twin"])) < optimal_numeric
            choice = 0 if cell["twin"] == "a" else 1
        if not correct:
            choice = 1 - choice
        reply = ModelReply(tool_calls=(ToolCall(name="inspect", arguments={"lot_id": case.public.target_ids[choice]}),))
        if invalid and not correct:
            reply = ModelReply(refused=True)
        rows.append({**cell, **score_first_action(cell["cell_id"], case, reply).model_dump(),
                     "evidence_kind": "synthetic", "continuation_status": "completed"})
    analysis = analyze_rows(rows, {**plan, "evidence_kind": "synthetic"}, allow_synthetic=True)
    replay = {"pending_cells": 0, "invalid_first_actions": sum(row.get("category") == "REFUSED" for row in rows)}
    return analysis, replay


@pytest.mark.parametrize("pairs,numeric,load,repeat", [(14,12,8,False), (13,12,2,False), (16,11,None,True)])
def test_exact_boundaries_from_scored_synthetic_cells(pairs,numeric,load,repeat):
    analysis, replay = threshold_fixture(pairs,numeric)
    result = _summarize_verified(analysis,replay)
    assert result["counts"]["fully_correct_main_pairs"] == pairs
    assert result["counts"]["optimal_numeric_calls"] == numeric
    hypothetical = result["hypothetical_threshold_evaluation"]
    assert hypothetical["selected_load"] == load
    assert hypothetical["repeat_pilot_with_different_model"] is repeat
    assert result["actual_selected_load"] is None
    assert result["actual_model_change_decided"] is False
    assert result["actual_pilot_verified"] is result["freeze_eligible"] is False


def test_invalid_decisions_stay_in_prescribed_denominators():
    analysis,replay = threshold_fixture(14,12,invalid=True)
    result = _summarize_verified(analysis,replay)
    assert result["counts"]["invalid_main_pairs"] == 2
    assert result["counts"]["invalid_numeric_calls"] == 4
    assert result["counts"]["planned_main_pairs"] == result["counts"]["planned_numeric_calls"] == 16
    assert result["hypothetical_threshold_evaluation"]["selected_load"] == 8


@pytest.mark.parametrize("missing", ["other_condition", "continuation", "pending"])
def test_incomplete_pilot_cannot_make_threshold_decision(missing):
    analysis,replay = threshold_fixture()
    if missing == "other_condition":
        analysis["missing_cells"] = 1
        analysis["missing_reasons"] = {"infrastructure_exhausted:timeout": 1}
    elif missing == "continuation":
        analysis["cells"][0]["continuation_status"] = "missing:ambiguous_infrastructure_attempt"
    else:
        replay["pending_cells"] = 1
    result = _summarize_verified(analysis,replay)
    assert result["hypothetical_threshold_evaluation"] is None
    assert result["threshold_status"] == "blocked_incomplete_pilot"
    assert result["actual_selected_load"] is None


@pytest.fixture(scope="module")
def completed_pilot(tmp_path_factory):
    output = tmp_path_factory.mktemp("pilot-traces")
    fixture = ScriptedPublicPolicy()
    provider = PinnedProvider(ProviderSettings(model=fixture.model,provider=fixture.provider),fixture)
    run_manifest(build_manifest("pilot"), output, provider)
    return output


def copy_run(source, destination):
    destination.mkdir()
    for name in REQUIRED_FILES:
        shutil.copyfile(source/name,destination/name)
    return destination


def test_stored_pilot_verified_without_mutation(completed_pilot):
    before = {path.relative_to(completed_pilot): path.read_bytes()
              for path in completed_pilot.rglob("*") if path.is_file()}
    result = summarize_pilot(completed_pilot,allow_synthetic=True)
    after = {path.relative_to(completed_pilot): path.read_bytes()
             for path in completed_pilot.rglob("*") if path.is_file()}
    assert before == after
    assert result["counts"]["planned_cells"] == result["counts"]["observed_cells"] == 160
    assert result["counts"]["fully_correct_main_pairs"] == 0
    assert result["counts"]["optimal_numeric_calls"] == 8
    assert result["hypothetical_threshold_evaluation"]["repeat_pilot_with_different_model"] is True
    assert result["provenance"]["calls.jsonl"] == hashlib.sha256((completed_pilot/'calls.jsonl').read_bytes()).hexdigest()
    assert result["trace_verification"] == "raw_journal_integrity_and_all_derived_outputs_verified"
    assert result["human_review_verified"] is False
    assert result["empirical_observations"] == 0
    json.dumps(result,allow_nan=False)


def test_synthetic_requires_explicit_opt_in(completed_pilot):
    with pytest.raises(ValueError,match="explicit"):
        summarize_pilot(completed_pilot)


@pytest.mark.parametrize("name", REQUIRED_FILES)
def test_missing_evidence_file_rejected(completed_pilot,tmp_path,name):
    output = copy_run(completed_pilot,tmp_path/'copy')
    (output/name).unlink()
    with pytest.raises(ValueError,match="all five"):
        summarize_pilot(output,allow_synthetic=True)


@pytest.mark.parametrize("change", ["fabricated_score", "duplicate_score", "partial_plan", "wrong_dataset", "wrong_load", "empirical_relabel"])
def test_fabricated_or_wrong_pilot_rejected(completed_pilot,tmp_path,change):
    output = copy_run(completed_pilot,tmp_path/'copy')
    manifest = json.loads((output/'manifest.json').read_text('utf-8'))
    if change in {"fabricated_score", "duplicate_score"}:
        path = output/'scores.csv'
        lines = path.read_text('utf-8').splitlines()
        if change == "duplicate_score":
            lines.append(lines[1])
        else:
            lines[1] = lines[1].replace('synthetic','empirical')
        path.write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    else:
        if change == "partial_plan": manifest['plan']['cells'].pop()
        elif change == "wrong_dataset": manifest['plan']['dataset'] = 'main'
        elif change == "wrong_load": manifest['plan']['load'] = 8
        else: manifest['run_config']['evidence_kind'] = 'empirical'
        (output/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    with pytest.raises(ValueError):
        summarize_pilot(output,allow_synthetic=True)


def test_duplicate_hash_valid_completed_event_rejected(completed_pilot,tmp_path):
    output = copy_run(completed_pilot,tmp_path/'copy')
    journal = Journal(output/'calls.jsonl')
    event = next(e for e in journal.events if e['event']=='cell_completed')
    journal.append({key:value for key,value in event.items() if key not in {'sequence','previous_hash','event_hash'}})
    with pytest.raises(ValueError,match="event_after_completed_cell"):
        summarize_pilot(output,allow_synthetic=True)


def test_partial_run_preserves_missingness_and_disables_thresholds(tmp_path):
    fixture = ScriptedPublicPolicy()
    provider = PinnedProvider(ProviderSettings(model=fixture.model,provider=fixture.provider),fixture)
    run_manifest(build_manifest('pilot'),tmp_path,provider,max_cells=1)
    result = summarize_pilot(tmp_path,allow_synthetic=True)
    assert result['counts']['pending_cells'] == 159
    assert result['counts']['missing_cells'] == 159
    assert result['missing_reasons'] == {'not_executed_yet':159}
    assert result['hypothetical_threshold_evaluation'] is None
