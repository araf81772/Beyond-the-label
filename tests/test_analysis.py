"""Scientific estimands tested on explicitly synthetic scored fixtures."""

import copy
import csv
import json
from pathlib import Path

import pytest

from beyond_label.analyze import analyze_rows, analyze_run, exact_sign_test, pair_category, paired_estimate
from beyond_label.generate import generate_world, make_case
from beyond_label.oracle import optimal_dispositions
from beyond_label.schemas import ModelReply, ToolCall
from beyond_label.score import score_first_action


def fixture_run(seeds=(2000, 2001, 2002, 2003), include_controls=True):
    cells, rows = [], []
    for seed in seeds:
        for layout in ("separate", "inline"):
            for twin in ("a", "b"):
                conditions = ("MAIN", "HIGH-FEE", "HIGH-STAKES") if include_controls else ("MAIN",)
                for condition in conditions:
                    cell = {"cell_id": f"{seed}-{layout}-{twin}-{condition}", "world_seed": seed,
                            "purpose": "decision", "condition": condition, "layout": layout, "twin": twin}
                    cells.append(cell)
                    rows.append(decision_row(cell))
                probe = {"cell_id": f"{seed}-{layout}-{twin}-READBACK", "world_seed": seed,
                         "purpose": "readback", "condition": "MAIN", "layout": layout, "twin": twin}
                cells.append(probe)
                rows.append({**probe, "evidence_kind": "synthetic", "readback_correct": True})
            if include_controls:
                masked = {"cell_id": f"{seed}-{layout}-MASKED", "world_seed": seed,
                          "purpose": "decision", "condition": "MASKED", "layout": layout, "twin": None}
                cells.append(masked)
                rows.append(decision_row(masked))
        if include_controls:
            for twin in ("a", "b"):
                numeric = {"cell_id": f"{seed}-{twin}-NUMERIC", "world_seed": seed,
                           "purpose": "decision", "condition": "NUMERIC", "layout": "separate", "twin": twin}
                cells.append(numeric)
                rows.append(decision_row(numeric))
    return {"dataset": "main", "load": 2, "evidence_kind": "synthetic", "cells": cells}, rows


def decision_row(cell, category=None):
    world = generate_world(cell["world_seed"])
    case = make_case(world, twin=cell["twin"] or "a", layout=cell["layout"], condition=cell["condition"])
    if category is None:
        category = "COMMIT" if cell["condition"] == "HIGH-FEE" else f"INSPECT_{world.high_stakes_index+1}" if cell["condition"] == "HIGH-STAKES" else "INSPECT_1" if cell["twin"] in ("a", None) else "INSPECT_2"
    if category == "COMMIT":
        reply = ModelReply(tool_calls=(ToolCall(name="commit", arguments={"dispositions": optimal_dispositions(case)}),))
    elif category.startswith("INSPECT_"):
        reply = ModelReply(tool_calls=(ToolCall(name="inspect", arguments={"lot_id": case.public.target_ids[int(category[-1])-1]}),))
    else:
        reply = ModelReply()
    score = score_first_action(cell["cell_id"], case, reply).model_dump()
    return {**cell, **score, "evidence_kind": "synthetic"}


def analyze(manifest, rows, **kwargs):
    return analyze_rows(rows, manifest, allow_synthetic=True, **kwargs)


def test_oracle_fixture_has_expected_primary_controls_and_synthetic_guard():
    manifest, rows = fixture_run()
    with pytest.raises(ValueError, match="Synthetic"):
        analyze_rows(rows, manifest)
    result = analyze(manifest, rows)
    assert result["primary"]["estimate"]["mean"] == 1
    assert result["primary"]["estimate"]["ci95"] == [1, 1]
    assert result["primary"]["estimate"]["worlds"] == 4
    assert result["primary"]["sign_test"]["p_value"] == .125
    assert result["layout_interaction"]["estimate"]["mean"] == 0
    assert result["primary"]["all_planned_missingness_bounds"] == [1, 1]
    for condition in ("MAIN", "HIGH-FEE", "HIGH-STAKES", "MASKED", "NUMERIC"):
        assert result["conditions"][condition]["optimal"]["rate"] == 1
        assert result["conditions"][condition]["regret_valid_only"]["mean"] == 0
    assert result["conditions"]["HIGH-FEE"]["commit_without_check"]["rate"] == 1
    assert result["conditions"]["HIGH-STAKES"]["inspect_high_stakes_lot"]["rate"] == 1
    assert result["conditions"]["MASKED"]["inspect"]["rate"] == 1
    assert result["readback"]["separate"]["recognition_action_gap"]["rate"] == 0
    assert result["interpretation"]["threshold_checks_for_validation"]["no_gap_here"] is True
    assert result["interpretation"]["conclusion"] == "SYNTHETIC_VALIDATION_ONLY_NO_EMPIRICAL_CONCLUSION"
    assert result["main_expected_loss_reference_policies"]["oracle"] == 30
    assert result["main_expected_loss_reference_policies"]["always_commit_follow_reports"] == 50
    assert result["main_expected_loss_reference_policies"]["uniform_random_single_inspection"] == 45


@pytest.mark.parametrize("a,b,expected,category", [("INSPECT_2", "INSPECT_1", -1, "reversed"),
                                                   ("INSPECT_1", "INSPECT_1", 0, "same_target"),
                                                   ("COMMIT", "COMMIT", 0, "no_check")])
def test_primary_reverse_same_target_and_no_check(a, b, expected, category):
    manifest, rows = fixture_run()
    rows = [decision_row(row, a if row["twin"] == "a" else b) if row["purpose"] == "decision" and row["condition"] == "MAIN" else row for row in rows]
    result = analyze(manifest, rows)
    assert result["primary"]["estimate"]["mean"] == expected
    assert result["primary"]["estimate"]["ci95"] == [expected, expected]
    assert result["primary"]["pair_category_counts"][category] == 4
    assert result["readback"]["separate"]["recognition_action_gap"] == {"successes": 4, "denominator": 4, "rate": 1}
    assert result["interpretation"]["threshold_checks_for_validation"]["gap_found"] is True
    assert "Descriptive" in result["interpretation"]["recognition_action_gap_scope"]


def test_missing_twin_uses_all_planned_tight_bounds_without_inventing_zero():
    manifest, rows = fixture_run(seeds=(2000, 2001))
    missing_id = "2001-separate-a-MAIN"
    rows = [row for row in rows if row["cell_id"] != missing_id]
    result = analyze(manifest, rows)
    primary = result["primary"]
    assert primary["planned_worlds"] == 2
    assert primary["complete_worlds"] == 1
    assert primary["estimate"]["mean"] == 1
    assert primary["all_planned_missingness_bounds"] == [.5, 1]
    assert result["missing_cells"] == 1
    assert result["missingness_by_purpose"]["decision"]["missing"] == 1
    assert result["missing_reasons"] == {"no_score_row": 1}
    assert result["readback"]["separate"]["recognized_pairs_missing_decision"] == 1
    assert result["interpretation"]["required_group_missingness"] is True
    both_missing = [row for row in rows if row["cell_id"] != "2001-separate-b-MAIN"]
    assert analyze(manifest, both_missing)["primary"]["all_planned_missingness_bounds"] == [0, 1]


def test_invalid_decision_is_observed_with_zero_inspection_indicator():
    manifest, rows = fixture_run(seeds=(2000, 2001))
    rows = [decision_row(row, "INVALID_NONE") if row["cell_id"] == "2001-separate-a-MAIN" else row for row in rows]
    result = analyze(manifest, rows)
    assert result["missing_cells"] == 0
    assert result["primary"]["complete_worlds"] == 2
    assert result["primary"]["estimate"]["mean"] == .5
    assert result["primary"]["invalid_excluded_sensitivity"]["worlds"] == 1
    assert result["primary"]["invalid_excluded_sensitivity"]["mean"] == 1
    assert result["primary"]["pair_category_counts"]["invalid"] == 1
    assert result["conditions"]["MAIN"]["invalid"] == 1
    assert result["conditions"]["MAIN"]["regret_valid_only"]["denominator"] == 7
    assert result["conditions"]["MAIN"]["regret_invalid_worst_valid"]["mean"] == 120/8


def test_world_bootstrap_layout_pairing_is_preserved():
    manifest, rows = fixture_run(seeds=(2000, 2001))
    edited = []
    for row in rows:
        if row["purpose"] == "decision" and row["condition"] == "MAIN":
            reverse = (row["world_seed"] == 2000 and row["layout"] == "inline") or (row["world_seed"] == 2001 and row["layout"] == "separate")
            if reverse:
                row = decision_row(row, "INSPECT_2" if row["twin"] == "a" else "INSPECT_1")
        edited.append(row)
    result = analyze(manifest, edited)
    assert result["layout_interaction"]["estimate"]["worlds"] == 2
    assert result["layout_interaction"]["estimate"]["mean"] == 0
    assert result["layout_interaction"]["estimate"]["ci95"] == [-2, 2]
    assert analyze(manifest, edited) == result
    assert paired_estimate([1, -1, 0], seed=314159) == paired_estimate([1, -1, 0], seed=314159)
    assert paired_estimate([])["mean"] is None
    assert paired_estimate([1])["bootstrap_resamples"] == 10000


def test_exact_sign_test_discards_ties_and_handles_no_discordance():
    assert exact_sign_test([1, 1, 1, 1, 0])["p_value"] == .125
    assert exact_sign_test([1, 1, -1, -1])["p_value"] == 1
    assert exact_sign_test([0, 0])["p_value"] == 1
    assert exact_sign_test([])["p_value"] == 1
    assert exact_sign_test([1, 0, -1])["discordant"] == 2


def test_interpretation_exact_threshold_boundaries_without_causal_overclaim():
    from beyond_label.analyze import _interpretation
    manifest, rows = fixture_run()
    result = analyze(manifest, rows)
    result["primary"]["estimate"]["ci95"] = [.1, .799]
    result["readback"]["overall"]["accuracy"]["rate"] = .90
    result["conditions"]["NUMERIC"]["optimal"]["rate"] = .90
    assert _interpretation(result)["threshold_checks_for_validation"]["gap_found"] is True
    result["primary"]["estimate"]["ci95"][1] = .80
    assert _interpretation(result)["threshold_checks_for_validation"]["gap_found"] is False
    result["primary"]["estimate"]["ci95"][1] = .79
    result["readback"]["overall"]["accuracy"]["rate"] = .8999
    assert _interpretation(result)["threshold_checks_for_validation"]["gap_found"] is False
    result["readback"]["overall"]["accuracy"]["rate"] = .90
    result["conditions"]["NUMERIC"]["optimal"]["rate"] = .8999
    assert _interpretation(result)["threshold_checks_for_validation"]["gap_found"] is False
    result["primary"]["estimate"]["ci95"] = [.80, .99]
    result["main_by_layout"]["inline"]["estimate"]["ci95"] = [.80, 1]
    result["conditions"]["HIGH-FEE"]["optimal"]["rate"] = .80
    result["conditions"]["HIGH-STAKES"]["optimal"]["rate"] = .80
    assert _interpretation(result)["threshold_checks_for_validation"]["no_gap_here"] is True
    result["conditions"]["HIGH-FEE"]["optimal"]["rate"] = .7999
    assert _interpretation(result)["threshold_checks_for_validation"]["no_gap_here"] is False
    result["layout_interaction"]["estimate"]["ci95"] = [.01, .2]
    result["conditions_by_layout"]["MAIN"]["separate"]["regret_valid_only"]["mean"] = 10
    result["conditions_by_layout"]["MAIN"]["inline"]["regret_valid_only"]["mean"] = 5
    assert _interpretation(result)["threshold_checks_for_validation"]["layout_helps"] is True
    result["layout_interaction"]["estimate"]["ci95"][0] = 0
    assert _interpretation(result)["threshold_checks_for_validation"]["layout_helps"] is False
    result["layout_interaction"]["estimate"]["ci95"][0] = .01
    result["conditions_by_layout"]["HIGH-FEE"]["inline"]["inspect"]["rate"] = .01
    assert _interpretation(result)["threshold_checks_for_validation"]["layout_helps"] is False


def test_final_outcome_denominators_do_not_treat_missing_continuations_as_zero():
    manifest, rows = fixture_run(seeds=(2000,))
    for row in rows:
        if row["purpose"] == "decision" and row["condition"] == "MAIN":
            row["report_contradiction"] = True
            row["continuation_status"] = "missing:timeout"
    row = next(row for row in rows if row["cell_id"] == "2000-separate-a-MAIN")
    row.update(post_inspection_correct=True, realised_loss=20, continuation_status="complete")
    result = analyze(manifest, rows)
    summary = result["conditions"]["MAIN"]
    assert result["missing_cells"] == 0
    assert summary["realised_loss"] == {"mean": 20, "denominator": 1}
    assert summary["post_inspection_correct"]["rate"] == 1
    assert summary["contradictions_without_final_outcome"] == 3
    assert summary["inspections_with_final_outcome_missing"] == 3


def test_denominators_and_errors_are_manifest_driven():
    manifest, rows = fixture_run(seeds=(2000,))
    with pytest.raises(ValueError, match="Duplicate score"):
        analyze(manifest, rows + [rows[0]])
    changed = copy.deepcopy(rows)
    changed[0]["twin"] = "b"
    with pytest.raises(ValueError, match="factors"):
        analyze(manifest, changed)
    changed = copy.deepcopy(rows)
    changed[0]["category"] = "INVENTED"
    with pytest.raises(ValueError, match="Unknown action"):
        analyze(manifest, changed)
    changed = copy.deepcopy(rows)
    changed[0]["evidence_kind"] = "empirical"
    with pytest.raises(ValueError, match="cannot be mixed"):
        analyze(manifest, changed)
    changed = copy.deepcopy(manifest)
    changed["cells"].append(changed["cells"][0])
    with pytest.raises(ValueError, match="duplicate manifest"):
        analyze(changed, rows)
    changed = copy.deepcopy(rows)
    changed[0]["missing_reason"] = "timeout"
    with pytest.raises(ValueError, match="cannot also"):
        analyze(manifest, changed)
    empty = analyze(manifest, [])
    assert empty["planned_cells"] == len(manifest["cells"])
    assert empty["missing_cells"] == len(manifest["cells"])
    assert empty["primary"]["estimate"]["mean"] is None
    assert empty["primary"]["all_planned_missingness_bounds"] == [-1, 1]


def write_fixture_run(path, manifest, rows):
    path.mkdir(parents=True, exist_ok=True)
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (path / "analysis_manifest.json").write_text(json.dumps({"evidence_kind": "synthetic"}), encoding="utf-8")
    fields = sorted(set().union(*(set(row) for row in rows)))
    with (path / "scores.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_analysis_csv_regeneration_is_reproducible_and_labelled(tmp_path):
    manifest, rows = fixture_run(seeds=(2000, 2001))
    write_fixture_run(tmp_path, manifest, rows)
    result = analyze_run(tmp_path, allow_synthetic=True)
    first = {path.name: path.read_bytes() for path in (tmp_path / "analysis").iterdir()}
    assert analyze_run(tmp_path, allow_synthetic=True) == result
    assert {path.name: path.read_bytes() for path in (tmp_path / "analysis").iterdir()} == first
    assert "manifest.json" in result["provenance"]
    assert all(b"SYNTHETIC" in content for content in first.values())


def test_wrapped_harness_manifest_and_masked_null_twin_roundtrip(tmp_path):
    manifest, rows = fixture_run(seeds=(2000,))
    write_fixture_run(tmp_path, manifest, rows)
    (tmp_path / "manifest.json").write_text(json.dumps({"plan": manifest, "run_config": {"evidence_kind": "synthetic"}}), encoding="utf-8")
    (tmp_path / "analysis_manifest.json").unlink()
    result = analyze_run(tmp_path, allow_synthetic=True)
    assert result["planned_cells"] == len(manifest["cells"])
    assert result["conditions"]["MASKED"]["observed"] == 2
    assert all(row["twin"] is None for row in result["cells"] if row["condition"] == "MASKED")


def test_trace_backed_analysis_rejects_changed_scores_without_overwriting_them(tmp_path):
    from beyond_label.provider import PinnedProvider, ProviderSettings
    from beyond_label.run import ScriptedPublicPolicy, build_manifest, run_manifest
    policy = ScriptedPublicPolicy()
    provider = PinnedProvider(ProviderSettings(model=policy.model, provider=policy.provider), policy)
    run_manifest(build_manifest("smoke"), tmp_path, provider, max_cells=2)
    result = analyze_run(tmp_path, allow_synthetic=True)
    assert result["trace_verification"] == "raw_journal_integrity_and_derived_outputs_verified"
    assert "calls.jsonl" in result["provenance"]
    before_calls = (tmp_path / "calls.jsonl").read_bytes()
    score_path = tmp_path / "scores.csv"
    tampered = score_path.read_bytes().replace(b"synthetic", b"empirical")
    score_path.write_bytes(tampered)
    with pytest.raises(ValueError, match="differ from raw-trace"):
        analyze_run(tmp_path, allow_synthetic=True)
    assert score_path.read_bytes() == tampered
    assert (tmp_path / "calls.jsonl").read_bytes() == before_calls


@pytest.mark.parametrize("a,b,category", [("INSPECT_1", "INSPECT_2", "fully_correct"),
                                         ("INSPECT_2", "INSPECT_1", "reversed"),
                                         ("INSPECT_2", "INSPECT_2", "same_target"),
                                         ("COMMIT", "INSPECT_1", "no_check"),
                                         ("REFUSED", "INSPECT_1", "invalid")])
def test_pair_categories(a, b, category):
    assert pair_category(a, b) == category


def test_truncated_empirical_tagged_fixture_cannot_support_main_conclusion():
    # This is an in-memory synthetic regression fixture exercising the label guard.
    manifest, rows = fixture_run(seeds=(2000,))
    manifest["evidence_kind"] = "empirical"
    for row in rows:
        row["evidence_kind"] = "empirical"
    result = analyze_rows(rows, manifest)
    assert result["planned_main_matrix_complete"] is False
    assert result["interpretation"]["conclusion"] == "INCONCLUSIVE_INCOMPLETE_MAIN_MANIFEST"


def test_complete_main_factor_set_is_required_independently_of_cell_ids():
    from beyond_label.run import build_manifest
    from beyond_label.analyze import _complete_main_matrix
    cells = build_manifest("main")["cells"]
    assert _complete_main_matrix(cells)
    assert not _complete_main_matrix(cells[:-1])
    changed = copy.deepcopy(cells)
    changed[0]["world_seed"] = 1000
    assert not _complete_main_matrix(changed)
