"""Synthetic audit contracts retain a missing cell; no model calls or new data."""
from copy import deepcopy
import csv
import hashlib
import io
import json

import pytest

from beyond_label.continuation import PAID_SMOKE_DIRECTORY, SEGMENT_DIRECTORY
from test_continuation79_execution import controls, prepared79
from test_execution_audit import audit


ACTIVE = PAID_SMOKE_DIRECTORY + "/segments/deepseek_primeintellect_v3"
RETAINED = "smoke-1100-readback-MAIN-inline-b"


def fixture_record():
    return {
        "historical_directory": PAID_SMOKE_DIRECTORY, "active_directory": ACTIVE,
        "historical_segments": [{"directory": PAID_SMOKE_DIRECTORY}, {"directory": SEGMENT_DIRECTORY}],
        "retained_cells": [{"cell_id": RETAINED, "missing_reason": "model_mismatch",
                            "continuation_status": "not_applicable", "source_directory": SEGMENT_DIRECTORY,
                            "source_artifact_sha256": {"calls.jsonl": "d" * 64}}],
        "dispatch_cell_ids": [f"synthetic-cell-{i}" for i in range(79)],
        "record_hash": "a" * 64, "active_source_commit": "b" * 40,
        "active_input_sha256": {"src/beyond_label/provider.py": "c" * 64},
        "plan": {"fixture": "exact 80-cell plan validated by continuation loader"},
    }


def fixture_entries(active_completed=2):
    return [
        dict(directory=PAID_SMOKE_DIRECTORY, dataset="smoke", attempted_calls=1, successful_calls=0,
             completed_cells=0, pending_cells=80, planned_cells=80, infrastructure_retries=0,
             unknown_cost_attempts=1, accounting_error_attempts=0, known_provider_spend_usd=0),
        dict(directory=SEGMENT_DIRECTORY, dataset="smoke", attempted_calls=1, successful_calls=0,
             completed_cells=1, pending_cells=79, planned_cells=80, infrastructure_retries=0,
             unknown_cost_attempts=0, accounting_error_attempts=0, known_provider_spend_usd="0.00005501216"),
        dict(directory=ACTIVE, dataset="smoke", attempted_calls=active_completed, successful_calls=active_completed,
             completed_cells=active_completed, retained_terminal_cells=1, pending_cells=79-active_completed,
             planned_cells=80, infrastructure_retries=0, unknown_cost_attempts=0,
             accounting_error_attempts=0, known_provider_spend_usd="0.0002" if active_completed else "0"),
    ]


def active_artifacts():
    record = fixture_record()
    stored = {"plan": deepcopy(record["plan"]), "run_config": {
        "input_hashes": deepcopy(record["active_input_sha256"]),
        "transport_provenance": "openrouter_paid_https_v1", "provider_settings": {"free_only": False},
        "execution_config": {"continuation_record_hash": record["record_hash"],
                             "continuation_source_commit": record["active_source_commit"],
                             "retained_terminal_cells": deepcopy(record["retained_cells"]),
                             "continuation_dispatch_cell_ids": list(record["dispatch_cell_ids"])}}}
    rows = [{"cell_id": RETAINED, "cell_status": "retained_terminal", "missing_reason": "model_mismatch",
             "continuation_status": "not_applicable", "readback_correct": "", "category": "", "regret": "",
             "retained_source_directory": SEGMENT_DIRECTORY, "retained_source_trace_sha256": "d" * 64}]
    rows += [{"cell_id": cell, "cell_status": "pending", "missing_reason": "not_executed_yet",
              "continuation_status": "pending", "readback_correct": "", "category": "", "regret": ""}
             for cell in record["dispatch_cell_ids"]]
    return record, stored, rows


def raw_artifacts(rows, events=()):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return {"scores.csv": buffer.getvalue().encode(),
            "calls.jsonl": b"".join((json.dumps(event)+"\n").encode() for event in events)}


def summary(completed=0):
    return {"retained_terminal_cells": 1, "completed_cells": completed, "pending_cells": 79-completed}


def test_three_versions_count_one_sample_and_retained_terminal_once():
    source = fixture_entries()
    before = deepcopy(source)
    group, = audit.logical_smoke_groups(source, fixture_record())
    assert source == before
    assert group["unique_planned_cells"] == 80 and group["independent_smoke_samples"] == 1
    assert group["completed_cells"] == 3 and group["pending_cells"] == 77
    assert group["retained_terminal_cells"] == 1
    assert group["recorded_request_attempts"] == 4 and group["successful_calls"] == 2
    assert group["known_provider_spend_usd"] == "0.00025501216"
    assert group["aggregate_actual_cost_complete"] is False
    assert group["unknown_cost_attempts"] == 1
    assert group["source_version_reissues"] == 1
    assert group["segment_directories"] == [PAID_SMOKE_DIRECTORY, SEGMENT_DIRECTORY, ACTIVE]


@pytest.mark.parametrize("active_exists", [False, True])
def test_prepared_or_empty_active_segment_does_not_erase_prior_terminal(active_exists):
    entries = fixture_entries(0)
    if not active_exists:
        entries.pop()
    group, = audit.logical_smoke_groups(entries, fixture_record())
    assert group["completed_cells"] == 1 and group["pending_cells"] == 79
    assert group["recorded_request_attempts"] == 2
    assert group["known_provider_spend_usd"] == "0.00005501216"
    assert group["active_segment_initialized"] is active_exists
    assert group["active_segment_started"] is False


@pytest.mark.parametrize("index,field,value", [
    (0, "completed_cells", 1), (1, "attempted_calls", 2), (1, "successful_calls", 1),
    (1, "completed_cells", 2), (1, "pending_cells", 78), (2, "completed_cells", 80),
    (2, "retained_terminal_cells", 0), (2, "retained_terminal_cells", True), (2, "pending_cells", 78),
])
def test_segment_counts_cannot_resample_or_double_count_retained_observations(index, field, value):
    entries = fixture_entries()
    entries[index][field] = value
    with pytest.raises(ValueError):
        audit.logical_smoke_groups(entries, fixture_record())


@pytest.mark.parametrize("field", ["retained_terminal_cells", "continuation_dispatch_cell_ids"])
def test_active_binding_requires_exact_retained_terminal_record(field):
    record, stored, _ = active_artifacts()
    audit.require_continuation_binding(stored, record)
    stored["run_config"]["execution_config"][field] = []
    with pytest.raises(ValueError, match="continuation"):
        audit.require_continuation_binding(stored, record)


def test_retained_terminal_row_stays_missing_without_an_active_event():
    record, stored, rows = active_artifacts()
    audit.require_retained_terminal_evidence(stored, record, raw_artifacts(rows), summary())


@pytest.mark.parametrize("event", ["phase_defined", "attempt_started", "attempt_succeeded", "cell_completed"])
def test_any_active_event_for_the_retained_cell_is_rejected(event):
    record, stored, rows = active_artifacts()
    with pytest.raises(ValueError, match="retained"):
        audit.require_retained_terminal_evidence(
            stored, record, raw_artifacts(rows, [{"cell_id": RETAINED, "event": event}]), summary())


@pytest.mark.parametrize("field,value", [
    ("cell_status", "completed"), ("missing_reason", ""), ("readback_correct", "True"),
    ("regret", "0"), ("category", "correct"), ("continuation_status", "pending"),
    ("retained_source_directory", "other"), ("retained_source_trace_sha256", "e" * 64),
])
def test_retained_row_cannot_become_an_observation_or_change_its_reason(field, value):
    record, stored, rows = active_artifacts()
    rows[0][field] = value
    with pytest.raises(ValueError, match="retained"):
        audit.require_retained_terminal_evidence(stored, record, raw_artifacts(rows), summary())


@pytest.mark.parametrize("damage", ["duplicate", "absent", "extra", "summary"])
def test_retained_and_dispatch_rows_cover_the_full_plan_once(damage):
    record, stored, rows = active_artifacts()
    report = summary()
    if damage == "duplicate": rows.append(dict(rows[0]))
    elif damage == "absent": rows.pop(0)
    elif damage == "extra": rows[1]["cell_id"] = "unplanned-cell"
    else: report["retained_terminal_cells"] = 0
    with pytest.raises(ValueError):
        audit.require_retained_terminal_evidence(stored, record, raw_artifacts(rows), report)


def test_unprepared_changed_source_audits_legacy_without_relaxing_live_loader(tmp_path, monkeypatch):
    from beyond_label import continuation
    expected = {"active_input_sha256": {"historical.py": "old"}}
    monkeypatch.setattr(continuation, "load_legacy_continuation", lambda root: expected)
    def reject_live(*args, **kwargs):
        raise AssertionError("Current-source live validation must not reinterpret old evidence")
    monkeypatch.setattr(continuation, "load_continuation", reject_live)
    assert audit.audit_continuations(tmp_path, {"current.py": "new"}) == (expected, expected)


def test_prepared_v3_audit_validates_current_source_and_keeps_legacy_binding(tmp_path, monkeypatch):
    from beyond_label import continuation, continuation79
    expected = {"version": "legacy"}
    active = fixture_record()
    inputs = {"current.py": "new"}
    record_path = tmp_path / continuation79.RECORD_PATH
    record_path.parent.mkdir()
    record_path.write_text("{}")
    seen = []
    monkeypatch.setattr(continuation, "load_legacy_continuation", lambda root: expected)
    def load(root, *, input_hashes):
        seen.append((root, input_hashes))
        return active
    monkeypatch.setattr(continuation, "load_continuation", load)
    assert audit.audit_continuations(tmp_path, inputs) == (expected, active)
    assert seen == [(tmp_path, inputs)]


def test_orphan_v3_cannot_hide_behind_historical_audit(tmp_path_factory):
    from beyond_label import continuation79
    tmp_path = tmp_path_factory.mktemp("a79")
    (tmp_path / continuation79.SEGMENT_DIRECTORY).mkdir(parents=True)
    with pytest.raises(ValueError, match="orphan"):
        audit.audit_continuations(tmp_path, {})


@pytest.mark.parametrize("damage", [None, "source", "inputs", "raw", "files"])
def test_historical_segment_keeps_its_exact_bytes_and_replay_source(damage):
    raw = {name: name.encode() for name in ("manifest.json", "calls.jsonl", "scores.csv", "usage.csv", "analysis_manifest.json")}
    stored = {"run_config": {"input_hashes": {"old.py": "a" * 64}}}
    descriptor = {"input_hashes": deepcopy(stored["run_config"]["input_hashes"]), "source_commit": "b" * 40,
                  "artifact_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in raw.items()}}
    replay = {"source_commit": descriptor["source_commit"]}
    if damage == "source": replay["source_commit"] = "c" * 40
    elif damage == "inputs": stored["run_config"]["input_hashes"] = {"new.py": "a" * 64}
    elif damage == "raw": raw["calls.jsonl"] += b"changed"
    elif damage == "files": raw.pop("usage.csv")
    if damage:
        with pytest.raises(ValueError, match="Historical"):
            audit.require_historical_segment_binding(stored, raw, descriptor, replay)
    else:
        audit.require_historical_segment_binding(stored, raw, descriptor, replay)


def test_audit_accepts_actual_offline_harness_retention_and_rejects_changed_source(prepared79):
    from beyond_label import paid_live
    root, path, config, fixture, record = prepared79
    result = paid_live.run_paid_smoke(path, "smoke", root/config["run_directory"], max_cells=1)
    active = root/record["active_directory"]
    raw = {name: (active/name).read_bytes() for name in (
        "manifest.json", "calls.jsonl", "scores.csv", "usage.csv", "analysis_manifest.json")}
    stored = json.loads(raw["manifest.json"])
    expected = {**record, "active_input_sha256": stored["run_config"]["input_hashes"]}
    audit.require_retained_terminal_evidence(stored, expected, raw, result)
    assert fixture.calls > 0 and result["completed_cells"] == 1 and result["pending_cells"] == 78
    assert result["retained_terminal_cells"] == 1
    changed = deepcopy(stored)
    changed["run_config"]["input_hashes"] = {"src/beyond_label/provider.py": "0" * 64}
    with pytest.raises(ValueError, match="continuation"):
        audit.require_retained_terminal_evidence(changed, expected, raw, result)
