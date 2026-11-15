"""Offline provenance fixtures retain the real terminal failure without reruns."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil

import pytest

from beyond_label import continuation as legacy, continuation79 as repair


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def prepared_inputs(tmp_path_factory, monkeypatch):
    root = tmp_path_factory.mktemp("v3")
    for relative in (legacy.PAID_SMOKE_DIRECTORY, legacy.SEGMENT_DIRECTORY):
        target = root / relative
        target.mkdir(parents=True)
        for name in legacy.FILES:
            shutil.copyfile(ROOT / relative / name, target / name)
    (root / "research").mkdir()
    for name in ("run_sources.json", "smoke_continuation.json"):
        shutil.copyfile(ROOT / "research" / name, root / "research" / name)
    monkeypatch.setattr(legacy, "_verify_committed_inputs", lambda *args: None)
    histories = repair._histories(root)
    inputs = deepcopy(histories[-1]["stored"]["run_config"]["input_hashes"])
    inputs["src/beyond_label/continuation79.py"] = "a" * 64
    inputs["src/beyond_label/provider.py"] = "b" * 64
    proofs = {item["historical_directory"]: {
        "source_commit": item["source_commit"], "artifact_sha256": item["artifact_sha256"],
        "summary": item["summary"], "input_hashes_verified": len(item["stored"]["run_config"]["input_hashes"]),
        "original_files_unchanged": True, "network_blocked": True, "credentials_removed": True,
    } for item in histories}
    return root, inputs, proofs


def build(prepared_inputs):
    root, inputs, proofs = prepared_inputs
    return repair.build_continuation79_record(root, source_commit="c" * 40,
                                              input_hashes=inputs, replay_proofs=proofs)


def save(root, record):
    (root / repair.RECORD_PATH).write_text(json.dumps(record), encoding="utf-8")


def test_pure_retention_spec_never_reads_files_or_changes_with_callers(monkeypatch):
    monkeypatch.setattr(Path, "read_bytes", lambda *a, **k: pytest.fail("pure helper read a file"))
    spec = repair.retained_cell_spec()
    assert spec["cell_id"] == repair.RETAINED_CELL_ID
    assert spec["missing_reason"] == "model_mismatch"
    assert spec["continuation_status"] == "not_applicable"
    assert spec["source_directory"] == legacy.SEGMENT_DIRECTORY
    assert set(spec["source_artifact_sha256"]) == set(legacy.FILES)
    spec["source_artifact_sha256"]["calls.jsonl"] = "changed"
    assert repair.retained_cell_spec()["source_artifact_sha256"]["calls.jsonl"] != "changed"


def test_prepare_retains_terminal_cell_and_only_79_untouched_dispatches(prepared_inputs):
    root, inputs, _ = prepared_inputs
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    record = build(prepared_inputs)
    assert record["retained_cells"] == [repair.retained_cell_spec()]
    assert record["unique_planned_cells"] == len(record["plan"]["cells"]) == 80
    assert record["dispatch_cell_ids"] == [cell["cell_id"] for cell in record["plan"]["cells"][1:]]
    assert len(record["dispatch_cell_ids"]) == len(set(record["dispatch_cell_ids"])) == 79
    assert repair.RETAINED_CELL_ID not in record["dispatch_cell_ids"]
    assert record["historical_recorded_attempts"] == 2 and record["historical_terminal_cells"] == 1
    assert record["historical_directory"] == legacy.PAID_SMOKE_DIRECTORY
    assert record["historical_segments"] == repair.historical_segments(root)
    assert all(path.read_bytes() == raw for path, raw in before.items())
    assert not (root / repair.SEGMENT_DIRECTORY).exists()
    assert not (root / "runs/_paid_testing_session").exists()
    save(root, record)
    assert legacy.load_continuation(root, input_hashes=inputs) == record
    assert legacy.effective_smoke_directory(root, input_hashes=inputs) == root / repair.SEGMENT_DIRECTORY


@pytest.mark.parametrize("mutation", ["resample", "drop", "reverse", "duplicate", "retained", "source", "cap", "boolean"])
def test_even_rehashed_record_cannot_change_retention_dispatch_or_allowance(prepared_inputs, mutation):
    root, inputs, _ = prepared_inputs
    record = build(prepared_inputs)
    if mutation == "resample":
        record["dispatch_cell_ids"].append(repair.RETAINED_CELL_ID)
    elif mutation == "drop":
        record["dispatch_cell_ids"].pop()
    elif mutation == "reverse":
        record["dispatch_cell_ids"].reverse()
    elif mutation == "duplicate":
        record["dispatch_cell_ids"][1] = record["dispatch_cell_ids"][0]
    elif mutation == "retained":
        record["retained_cells"][0]["missing_reason"] = None
    elif mutation == "source":
        record["historical_segments"][1]["source_commit"] = "d" * 40
    elif mutation == "boolean":
        record["schema_version"] = True
    else:
        record["allowance_policy"] = "reset_after_repair"
    record["record_hash"] = legacy._hash({k: v for k, v in record.items() if k != "record_hash"})
    save(root, record)
    with pytest.raises(legacy.ContinuationError, match="record_changed"):
        legacy.load_continuation(root, input_hashes=inputs)


@pytest.mark.parametrize("relative", [legacy.PAID_SMOKE_DIRECTORY, legacy.SEGMENT_DIRECTORY])
@pytest.mark.parametrize("name", legacy.FILES)
def test_any_historical_file_change_blocks_new_source(prepared_inputs, relative, name):
    root, inputs, _ = prepared_inputs
    record = build(prepared_inputs)
    save(root, record)
    path = root / relative / name
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(legacy.ContinuationError, match="historical|terminal"):
        legacy.load_continuation(root, input_hashes=inputs)


@pytest.mark.parametrize("relative", [legacy.PAID_SMOKE_DIRECTORY, legacy.SEGMENT_DIRECTORY])
@pytest.mark.parametrize("field", ["network_blocked", "credentials_removed", "original_files_unchanged", "summary"])
def test_both_historical_replays_are_mandatory(prepared_inputs, relative, field):
    root, inputs, proofs = prepared_inputs
    proofs[relative][field] = False
    with pytest.raises(legacy.ContinuationError, match="replay"):
        repair.build_continuation79_record(root, source_commit="c" * 40, input_hashes=inputs, replay_proofs=proofs)


@pytest.mark.parametrize("name", ["src/beyond_label/score.py", "prompts/agent_system.txt", "research/protocol.md", "data/worlds_smoke.jsonl"])
def test_repair_may_not_change_scientific_inputs(prepared_inputs, name):
    _, inputs, _ = prepared_inputs
    inputs[name] = "e" * 64
    with pytest.raises(legacy.ContinuationError, match="scientific"):
        build(prepared_inputs)


def test_legacy_uses_its_recorded_source_while_active_loader_stays_strict(prepared_inputs):
    root, inputs, _ = prepared_inputs
    prior = legacy.load_legacy_continuation(root)
    assert prior["active_source_commit"] == repair.TERMINAL_SOURCE_COMMIT
    assert prior["active_input_sha256"] != inputs
    with pytest.raises(legacy.ContinuationError, match="source_changed"):
        legacy.load_continuation(root, input_hashes=inputs)


@pytest.mark.parametrize("existing", ["record", "segment"])
def test_preparation_cannot_overwrite_or_reset_a_version(prepared_inputs, existing):
    root, _, _ = prepared_inputs
    if existing == "record":
        save(root, build(prepared_inputs))
    else:
        (root / repair.SEGMENT_DIRECTORY).mkdir()
    with pytest.raises(legacy.ContinuationError, match="already"):
        build(prepared_inputs)


def test_orphan_v3_never_falls_back_to_legacy(prepared_inputs):
    root, inputs, _ = prepared_inputs
    (root / repair.SEGMENT_DIRECTORY).mkdir()
    with pytest.raises(legacy.ContinuationError, match="orphan"):
        legacy.load_continuation(root, input_hashes=inputs)


def test_source_commit_verifier_receives_all_three_exact_versions(prepared_inputs, monkeypatch):
    root, inputs, _ = prepared_inputs
    checks = []
    monkeypatch.setattr(legacy, "_verify_committed_inputs", lambda *a: checks.append(a))
    record = build(prepared_inputs)
    expected = {(record["active_source_commit"], tuple(sorted(inputs.items())))}
    expected.update((item["source_commit"], tuple(sorted(item["input_hashes"].items())))
                    for item in record["historical_segments"])
    assert expected.issubset({(commit, tuple(sorted(hashes.items()))) for _, commit, hashes in checks})


def test_preparation_cli_writes_research_only_without_starting_a_run(prepared_inputs, monkeypatch):
    root, inputs, proofs = prepared_inputs
    spec = importlib.util.spec_from_file_location("prepare_smoke79_fixture", ROOT / "scripts/prepare_smoke79.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_inputs", lambda: inputs)
    monkeypatch.setattr(module, "replay_historical", lambda _, directory: proofs[directory.relative_to(root).as_posix()])
    before = {p: p.read_bytes() for p in (root / "runs").rglob("*") if p.is_file()}
    result = module.prepare_smoke79(root, source_commit="c" * 40)
    assert result == legacy.load_continuation(root, input_hashes=inputs)
    assert (root / repair.RECORD_PATH).is_file()
    assert all(path.read_bytes() == raw for path, raw in before.items())
    assert not (root / repair.SEGMENT_DIRECTORY).exists()
    assert not (root / "runs/_paid_testing_session").exists()
    with pytest.raises(legacy.ContinuationError, match="already"):
        module.prepare_smoke79(root, source_commit="c" * 40)
