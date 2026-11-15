"""Source-version continuation preparation is offline and does not resample."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from beyond_label import continuation


ROOT = Path(__file__).resolve().parents[1]


def fixture(tmp_path, monkeypatch):
    original = ROOT / continuation.PAID_SMOKE_DIRECTORY
    target = tmp_path / continuation.PAID_SMOKE_DIRECTORY
    target.mkdir(parents=True)
    for name in continuation.FILES:
        (target / name).write_bytes((original / name).read_bytes())
    (tmp_path / "research").mkdir()
    (tmp_path / "research/run_sources.json").write_bytes((ROOT / "research/run_sources.json").read_bytes())
    history = continuation.historical_smoke(tmp_path)
    inputs = deepcopy(history["stored"]["run_config"]["input_hashes"])
    inputs["src/beyond_label/provider.py"] = "1" * 64
    inputs["src/beyond_label/continuation.py"] = "2" * 64
    proof = {"source_commit": history["source_commit"], "artifact_sha256": history["artifact_sha256"],
             "input_hashes_verified": len(history["stored"]["run_config"]["input_hashes"]),
             "original_files_unchanged": True, "network_blocked": True, "credentials_removed": True,
             "summary": history["summary"]}
    monkeypatch.setattr(continuation, "_verify_committed_inputs", lambda *args: None)
    return history, inputs, proof


def prepare(tmp_path, monkeypatch):
    history, inputs, proof = fixture(tmp_path, monkeypatch)
    record = continuation.build_continuation_record(tmp_path, source_commit="a" * 40,
                                                   input_hashes=inputs, replay_proof=proof)
    return history, inputs, proof, record


def save(tmp_path, record):
    path = tmp_path / continuation.CONTINUATION_RECORD
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def test_preparation_binds_one_80_cell_smoke_without_creating_execution_segment(tmp_path, monkeypatch):
    history, inputs, _, record = prepare(tmp_path, monkeypatch)
    assert record["plan"] == history["stored"]["plan"]
    assert record["unique_planned_cells"] == record["plan"]["initial_calls"] == 80
    assert record["historical_recorded_attempts"] == 1
    assert record["historical_successful_calls"] == 0
    assert record["active_input_sha256"] == inputs
    assert record["attempt_policy"] == "changed_request_is_source_version_reissue_not_identical_retry"
    assert not (tmp_path / continuation.SEGMENT_DIRECTORY).exists()
    assert not (tmp_path / "runs/_paid_testing_session").exists()
    save(tmp_path, record)
    assert continuation.load_continuation(tmp_path, input_hashes=inputs) == record
    assert continuation.effective_smoke_directory(tmp_path, input_hashes=inputs) == tmp_path / continuation.SEGMENT_DIRECTORY
    assert all(hashlib.sha256((tmp_path / continuation.PAID_SMOKE_DIRECTORY / name).read_bytes()).hexdigest() == digest
               for name, digest in history["artifact_sha256"].items())


@pytest.mark.parametrize("field,value", [
    ("active_directory", "runs/another"), ("active_directory", "../escape"),
    ("unique_planned_cells", 160), ("historical_recorded_attempts", 0),
    ("historical_successful_calls", 1), ("active_source_commit", "HEAD"),
    ("attempt_policy", "identical_retry"), ("record_hash", "0" * 64),
])
def test_tampered_preparation_cannot_select_another_sample_or_reset_attempt(tmp_path, monkeypatch, field, value):
    _, inputs, _, record = prepare(tmp_path, monkeypatch)
    record[field] = value
    save(tmp_path, record)
    with pytest.raises(continuation.ContinuationError):
        continuation.load_continuation(tmp_path, input_hashes=inputs)
    assert not (tmp_path / continuation.SEGMENT_DIRECTORY).exists()


def test_source_changes_after_preparation_require_another_review(tmp_path, monkeypatch):
    _, inputs, _, record = prepare(tmp_path, monkeypatch)
    save(tmp_path, record)
    inputs["src/beyond_label/provider.py"] = "3" * 64
    with pytest.raises(continuation.ContinuationError, match="source"):
        continuation.load_continuation(tmp_path, input_hashes=inputs)


@pytest.mark.parametrize("name", ["src/beyond_label/score.py", "prompts/agent_system.txt",
    "data/worlds_smoke.jsonl", "research/protocol.md", "configs/main.yaml"])
def test_scientific_input_changes_are_not_infrastructure_continuations(tmp_path, monkeypatch, name):
    _, inputs, proof = fixture(tmp_path, monkeypatch)
    inputs[name] = "3" * 64
    with pytest.raises(continuation.ContinuationError, match="scientific"):
        continuation.build_continuation_record(tmp_path, source_commit="a" * 40,
                                               input_hashes=inputs, replay_proof=proof)


@pytest.mark.parametrize("field", ["network_blocked", "credentials_removed", "original_files_unchanged"])
def test_unverified_original_replay_cannot_prepare_continuation(tmp_path, monkeypatch, field):
    _, inputs, proof = fixture(tmp_path, monkeypatch)
    proof[field] = False
    with pytest.raises(continuation.ContinuationError, match="replay"):
        continuation.build_continuation_record(tmp_path, source_commit="a" * 40,
                                               input_hashes=inputs, replay_proof=proof)


@pytest.mark.parametrize("name", continuation.FILES)
def test_changed_original_artifacts_always_block(tmp_path, monkeypatch, name):
    _, inputs, _, record = prepare(tmp_path, monkeypatch)
    save(tmp_path, record)
    path = tmp_path / continuation.PAID_SMOKE_DIRECTORY / name
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(continuation.ContinuationError, match="historical"):
        continuation.load_continuation(tmp_path, input_hashes=inputs)


@pytest.mark.parametrize("mutation", ["successful_response", "error_with_model_reply", "changed_payload"])
def test_even_rehashed_history_cannot_hide_model_observations_or_change_delivery(tmp_path, monkeypatch, mutation):
    history, _, _ = fixture(tmp_path, monkeypatch)
    events = deepcopy(history["events"])
    if mutation == "successful_response":
        events[-1]["event"] = "attempt_succeeded"
    elif mutation == "error_with_model_reply":
        events[-1]["raw_response"] = {"choices": [{"message": {"content": "synthetic reply"}}]}
    else:
        for event in events[1:]:
            event["payload"]["messages"][0]["content"] = "changed synthetic handoff"
            event["request_hash"] = continuation._hash(event["payload"])
    previous, lines = "0" * 64, []
    for event in events:
        event.pop("event_hash")
        event["previous_hash"] = previous
        event["event_hash"] = previous = continuation._hash(event)
        lines.append(json.dumps(event) + "\n")
    path = tmp_path / continuation.PAID_SMOKE_DIRECTORY / "calls.jsonl"
    path.write_text("".join(lines), encoding="utf-8")
    index_path = tmp_path / "research/run_sources.json"
    index = json.loads(index_path.read_text())
    index["runs"][continuation.PAID_SMOKE_DIRECTORY]["files"]["calls.jsonl"] = hashlib.sha256(path.read_bytes()).hexdigest()
    index_path.write_text(json.dumps(index), encoding="utf-8")
    with pytest.raises(continuation.ContinuationError, match="historical"):
        continuation.historical_smoke(tmp_path)


def test_no_record_keeps_original_path_and_orphan_segment_blocks(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("v2")
    assert continuation.load_continuation(tmp_path, input_hashes={}) is None
    assert continuation.effective_smoke_directory(tmp_path, input_hashes={}) == tmp_path / continuation.PAID_SMOKE_DIRECTORY
    (tmp_path / continuation.SEGMENT_DIRECTORY).mkdir(parents=True)
    with pytest.raises(continuation.ContinuationError, match="orphan"):
        continuation.load_continuation(tmp_path, input_hashes={})


def test_existing_segment_cannot_be_reprepared_or_reset(tmp_path_factory, monkeypatch):
    tmp_path = tmp_path_factory.mktemp("v2")
    _, inputs, proof = fixture(tmp_path, monkeypatch)
    (tmp_path / continuation.SEGMENT_DIRECTORY).mkdir(parents=True)
    with pytest.raises(continuation.ContinuationError, match="already"):
        continuation.build_continuation_record(tmp_path, source_commit="a" * 40,
                                               input_hashes=inputs, replay_proof=proof)


def test_resolved_segment_cannot_escape_the_canonical_run(tmp_path, monkeypatch):
    original_resolve = Path.resolve
    selected = tmp_path / continuation.SEGMENT_DIRECTORY
    def resolve(path, *args, **kwargs):
        return tmp_path / "outside" if path == selected else original_resolve(path, *args, **kwargs)
    monkeypatch.setattr(Path, "resolve", resolve)
    with pytest.raises(continuation.ContinuationError, match="path"):
        continuation.effective_smoke_directory(tmp_path, input_hashes={})


def test_committed_source_verification_reads_exact_local_git_blobs(tmp_path):
    source = tmp_path / "src/beyond_label/provider.py"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"# local fixture\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "add", "src/beyond_label/provider.py"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                    "commit", "-qm", "fixture"], cwd=tmp_path, check=True, capture_output=True)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True, capture_output=True, text=True).stdout.strip()
    inputs = {"src/beyond_label/provider.py": hashlib.sha256(source.read_bytes()).hexdigest()}
    continuation._verify_committed_inputs(tmp_path, commit, inputs)
    with pytest.raises(continuation.ContinuationError, match="committed"):
        continuation._verify_committed_inputs(tmp_path, commit, {**inputs, "src/beyond_label/missing.py": "a" * 64})
    with pytest.raises(continuation.ContinuationError, match="committed"):
        continuation._verify_committed_inputs(tmp_path, commit, {"src/beyond_label/provider.py": "a" * 64})


@pytest.mark.parametrize("name", [".env", "../.env", "src/beyond_label/../../.env", "C:/key", "src\\beyond_label\\run.py"])
def test_source_snapshot_cannot_include_credentials_or_escaping_paths(name):
    assert not continuation._allowed_input(name)


def test_boolean_alias_cannot_retain_a_stale_record_hash(tmp_path, monkeypatch):
    _, inputs, _, record = prepare(tmp_path, monkeypatch)
    record['historical_recorded_attempts'] = True
    save(tmp_path, record)
    with pytest.raises(continuation.ContinuationError, match='record_changed'):
        continuation.load_continuation(tmp_path, input_hashes=inputs)
