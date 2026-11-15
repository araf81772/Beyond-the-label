"""Historical HTTP failure is replayed read-only; no model sample is generated."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("btl_replay_history", ROOT / "scripts/replay_history.py")
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)


def test_retained_partial_smoke_replays_with_exact_source_and_no_dispatch():
    result = history.replay_historical(ROOT, ROOT / "runs/paid_smoke_gpt41mini_20261115")
    assert result["summary"]["attempted_calls"] == 1
    assert result["summary"]["successful_calls"] == 0
    assert result["original_files_unchanged"] and result["network_blocked"]
    assert result["credentials_removed"] and result["input_hashes_verified"] == 43


def test_missing_binding_never_falls_back_to_current_source(tmp_path):
    with pytest.raises(ValueError, match="binding is missing"):
        history.replay_historical(tmp_path, tmp_path / "runs/example")


@pytest.mark.parametrize("name", ["../.env", ".env", "src/beyond_label/../../.env",
    "C:/credentials", "src\\beyond_label\\run.py", "research/decisions.md", ".git/config"])
def test_credentials_and_escaping_paths_are_never_snapshot_inputs(name):
    assert not history._allowed_input(name)


@pytest.mark.parametrize("change", ["raw", "commit", "source_digest"])
def test_changed_historical_evidence_is_rejected_before_execution(tmp_path, monkeypatch, change):
    relative = "runs/paid_smoke_gpt41mini_20261115"
    (tmp_path / relative).mkdir(parents=True)
    (tmp_path / "research").mkdir()
    for name in history.FILES:
        (tmp_path / relative / name).write_bytes((ROOT / relative / name).read_bytes())
    index = json.loads((ROOT / "research/run_sources.json").read_text("utf-8"))
    record = index["runs"][relative]
    if change == "raw":
        (tmp_path / relative / "calls.jsonl").write_text("tampered", encoding="utf-8")
    elif change == "commit":
        record["source_commit"] = "HEAD"
    else:
        monkeypatch.setattr(history, "_git_blob", lambda *args: b"wrong source")
        saved = json.loads((tmp_path / relative / "manifest.json").read_text("utf-8"))
        monkeypatch.setattr(history, "_git_source_paths", lambda *args: set(saved["run_config"]["input_hashes"]))
    (tmp_path / "research/run_sources.json").write_text(json.dumps(index), encoding="utf-8")
    with pytest.raises(ValueError, match="changed|exact commit|input hashes"):
        history.replay_historical(tmp_path, tmp_path / relative)


def test_replay_child_environment_drops_credentials(monkeypatch, tmp_path):
    for name in history.CREDENTIALS:
        monkeypatch.setenv(name, "fixture-only-private-value")
    env = history._child_environment(tmp_path)
    assert not set(history.CREDENTIALS) & set(env)
    assert env["PYTHONDONTWRITEBYTECODE"] == env["GIT_NO_LAZY_FETCH"] == "1"


def test_corrected_smoke_diagnostics_keep_one_failure_distinct_from_untouched():
    spec = importlib.util.spec_from_file_location("btl_smoke_diagnostics", ROOT / "scripts/smoke_diagnostics.py")
    diagnostics = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(diagnostics)
    result = diagnostics.diagnose(ROOT, ROOT / "runs/paid_smoke_gpt41mini_20261115")
    assert result["attempted_cells"] == 1 and result["never_attempted_cells"] == 79
    assert result["corrected_missingness_counts"] == {
        "pending_after_infrastructure_failure": 1, "not_executed_yet": 79}
    assert result["unknown_cost_attempts"] == 1 and not result["cost_evidence_complete"]
    assert result["completed_cells"] == result["empirical_observations"] == 0
