"""Offline test fixtures exercise empirical-summary guards; no live observations.

Every run in this module is temporary and uses an injected scripted transport.
No fixture here is a completed real pilot or evidence of human review.
"""
import json

import pytest

from beyond_label.pilot import REQUIRED_FILES, _summarize_verified, summarize_pilot
from beyond_label.run import build_manifest
from test_pilot_summary import threshold_fixture


@pytest.mark.parametrize("pairs,numeric,load,repeat", [
    (14, 12, 8, False), (13, 12, 2, False), (16, 11, None, True),
])
def test_empirical_threshold_contract_with_explicit_offline_fixture(pairs, numeric, load, repeat):
    analysis, replay = threshold_fixture(pairs, numeric, invalid=True)
    result = _summarize_verified(analysis, replay, evidence_kind="empirical")
    assert result["evidence_kind"] == "empirical"
    assert result["empirical_observations"] == 160
    assert result["actual_pilot_verified"] is True
    assert result["actual_selected_load"] == load
    assert result["actual_model_change_decided"] is repeat
    assert result["actual_threshold_evaluation"]["selected_load"] == load
    assert result["actual_threshold_evaluation"]["repeat_pilot_with_different_model"] is repeat
    assert result["hypothetical_threshold_evaluation"] is None
    assert result["counts"]["fully_correct_main_pairs"] == pairs
    assert result["counts"]["optimal_numeric_calls"] == numeric
    assert result["counts"]["invalid_main_pairs"] == 16 - pairs
    assert result["counts"]["invalid_numeric_calls"] == 16 - numeric
    assert result["freeze_eligible"] is result["human_review_verified"] is False
    assert "SYNTHETIC" not in result["artifact_label"]


@pytest.mark.parametrize("missing", ["condition", "continuation", "pending", "main_pair", "numeric"])
def test_incomplete_empirical_fixture_does_not_select_or_change_model(missing):
    analysis, replay = threshold_fixture(14, 11)
    if missing == "condition":
        analysis["missing_cells"] = 1
        analysis["observed_cells"] -= 1
        analysis["missing_reasons"] = {"infrastructure_exhausted:timeout": 1}
    elif missing == "continuation":
        analysis["cells"][0]["continuation_status"] = "missing:ambiguous_infrastructure_attempt"
    elif missing == "pending":
        replay["pending_cells"] = 1
    elif missing == "main_pair":
        analysis["main_by_layout"]["separate"]["pairs"][0]["complete"] = False
    else:
        analysis["conditions"]["NUMERIC"]["observed"] = 15
    result = _summarize_verified(analysis, replay, evidence_kind="empirical")
    assert result["actual_pilot_verified"] is result["pilot_observations_complete"] is False
    assert result["actual_selected_load"] is result["actual_threshold_evaluation"] is None
    assert result["actual_model_change_decided"] is False
    assert result["hypothetical_threshold_evaluation"] is None
    assert result["threshold_status"] == "blocked_incomplete_pilot"
    assert result["counts"]["planned_cells"] == 160
    assert result["counts"]["planned_main_pairs"] == result["counts"]["planned_numeric_calls"] == 16
    assert result["freeze_eligible"] is result["human_review_verified"] is False


@pytest.mark.parametrize("execution_config,free_only", [
    (None, True), ({}, True), ([], True), ({"test_fixture_only": True}, False),
    ({"test_fixture_only": True}, "true"),
])
def test_empirical_provenance_guard_rejects_absent_configuration(tmp_path, execution_config, free_only):
    # Intentionally invalid metadata: it must fail before replay can trust it.
    stored = {"plan": build_manifest("pilot"), "run_config": {
        "evidence_kind": "empirical", "provider_settings": {"free_only": free_only},
        "execution_config": execution_config,
    }}
    for name in REQUIRED_FILES:
        (tmp_path / name).write_text("", encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps(stored), encoding="utf-8")
    with pytest.raises(ValueError, match="provenance"):
        summarize_pilot(tmp_path)


def test_unknown_evidence_kind_is_not_interpreted_as_empirical(tmp_path):
    stored = {"plan": build_manifest("pilot"), "run_config": {"evidence_kind": "unknown"}}
    for name in REQUIRED_FILES:
        (tmp_path / name).write_text("", encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps(stored), encoding="utf-8")
    with pytest.raises(ValueError, match="provenance"):
        summarize_pilot(tmp_path)
