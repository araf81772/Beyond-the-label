"""In-memory synthetic segment summaries check audit denominators; no runs."""
from copy import deepcopy

import pytest

from beyond_label.continuation import PAID_SMOKE_DIRECTORY, SEGMENT_DIRECTORY
from test_execution_audit import audit


def entries():
    return [dict(directory=PAID_SMOKE_DIRECTORY, dataset="smoke", attempted_calls=1,
                 successful_calls=0, completed_cells=0, pending_cells=80, planned_cells=80,
                 infrastructure_retries=0, unknown_cost_attempts=1),
            dict(directory=SEGMENT_DIRECTORY, dataset="smoke", attempted_calls=3,
                 successful_calls=3, completed_cells=2, pending_cells=78, planned_cells=80,
                 infrastructure_retries=0, unknown_cost_attempts=0)]


def record():
    return dict(active_directory=SEGMENT_DIRECTORY, historical_directory=PAID_SMOKE_DIRECTORY,
                record_hash="a" * 64, active_source_commit="b" * 40,
                active_input_sha256={"src/beyond_label/provider.py": "c" * 64},
                plan={"fixture": "full 80-cell plan checked separately"})


def test_source_segments_count_as_one_80_cell_sample_and_keep_original_attempt():
    original = entries()
    before = deepcopy(original)
    groups = audit.logical_smoke_groups(original, record())
    assert original == before
    assert len(groups) == 1
    group = groups[0]
    assert group["unique_planned_cells"] == 80
    assert group["independent_smoke_samples"] == 1
    assert group["completed_cells"] == 2 and group["pending_cells"] == 78
    assert group["recorded_request_attempts"] == 4
    assert group["unknown_cost_attempts"] == 1
    assert group["infrastructure_retries"] == 0
    assert group["source_version_reissues"] == 1
    assert group["segment_directories"] == [PAID_SMOKE_DIRECTORY, SEGMENT_DIRECTORY]
    prepared = audit.logical_smoke_groups(original[:1], record())[0]
    assert prepared["recorded_request_attempts"] == 1
    assert prepared["completed_cells"] == prepared["source_version_reissues"] == 0
    empty = deepcopy(original)
    empty[1].update(attempted_calls=0, successful_calls=0, completed_cells=0, pending_cells=80)
    initialized = audit.logical_smoke_groups(empty, record())[0]
    assert initialized["active_segment_initialized"] is True
    assert initialized["active_segment_started"] is False


@pytest.mark.parametrize("field,value", [("successful_calls", 1), ("completed_cells", 1), ("attempted_calls", 2)])
def test_parent_observations_cannot_be_hidden_in_a_continuation_group(field, value):
    source = entries()
    source[0][field] = value
    with pytest.raises(ValueError, match="historical"):
        audit.logical_smoke_groups(source, record())


@pytest.mark.parametrize("mutation", ["hash", "commit", "inputs", "plan", "free", "provenance"])
def test_segment_binding_requires_exact_prepared_source_and_paid_provenance(mutation):
    expected = record()
    config = {"input_hashes": expected["active_input_sha256"],
              "provider_settings": {"free_only": False}, "transport_provenance": "openrouter_paid_https_v1",
              "execution_config": {"continuation_record_hash": expected["record_hash"],
                                   "continuation_source_commit": expected["active_source_commit"]}}
    stored = {"plan": expected["plan"], "run_config": config}
    audit.require_continuation_binding(stored, expected)
    if mutation == "hash":
        config["execution_config"]["continuation_record_hash"] = "other"
    elif mutation == "commit":
        config["execution_config"]["continuation_source_commit"] = "HEAD"
    elif mutation == "inputs":
        config["input_hashes"] = {}
    elif mutation == "plan":
        stored["plan"] = {}
    elif mutation == "free":
        config["provider_settings"]["free_only"] = True
    else:
        config["transport_provenance"] = "injected_fixture"
    with pytest.raises(ValueError, match="continuation"):
        audit.require_continuation_binding(stored, expected)
