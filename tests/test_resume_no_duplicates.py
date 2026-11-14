import csv
import json

import pytest

from beyond_label.provider import PinnedProvider, ProviderSettings
from beyond_label.run import Journal, JournalIntegrityError, ScriptedPublicPolicy, build_manifest, rebuild_outputs, run_manifest


def setup_provider():
    fixture = ScriptedPublicPolicy()
    return fixture, PinnedProvider(ProviderSettings(model=fixture.model, provider=fixture.provider), fixture)


def first_purpose(purpose):
    for seed in range(100):
        manifest = build_manifest("smoke", schedule_seed=seed)
        if manifest["cells"][0]["purpose"] == purpose:
            return manifest
    raise AssertionError("Fixture schedule unavailable")


def rows(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_half_run_resume_has_no_duplicate_completed_cells_or_successes(tmp_path):
    fixture, provider = setup_provider()
    manifest = build_manifest("smoke")
    first = run_manifest(manifest, tmp_path, provider, max_cells=40)
    assert first["completed_cells"] == 40 and first["pending_cells"] == 40
    raw_prefix = (tmp_path / "calls.jsonl").read_bytes()
    final = run_manifest(manifest, tmp_path, provider)
    assert final["completed_cells"] == 80 and final["pending_cells"] == 0
    assert final["successful_calls"] == fixture.calls == 144
    assert (tmp_path / "calls.jsonl").read_bytes().startswith(raw_prefix)
    events = Journal(tmp_path / "calls.jsonl").events
    completed = [e["cell_id"] for e in events if e["event"] == "cell_completed"]
    successes = [(e["cell_id"], e["phase"]) for e in events if e["event"] == "attempt_succeeded"]
    assert len(completed) == len(set(completed)) == 80
    assert len(successes) == len(set(successes)) == 144
    count = fixture.calls
    assert run_manifest(manifest, tmp_path, provider) == final
    assert fixture.calls == count


def test_success_fsynced_before_completion_is_reused_not_resampled(tmp_path, monkeypatch):
    fixture, provider = setup_provider()
    manifest = first_purpose("readback")
    original = Journal.append

    def interrupted(self, event):
        original(self, event)
        if event["event"] == "attempt_succeeded":
            raise KeyboardInterrupt

    monkeypatch.setattr(Journal, "append", interrupted)
    with pytest.raises(KeyboardInterrupt):
        run_manifest(manifest, tmp_path, provider, max_cells=1)
    assert fixture.calls == 1
    monkeypatch.setattr(Journal, "append", original)
    final = run_manifest(manifest, tmp_path, provider, max_cells=1)
    assert final["completed_cells"] == 1
    assert fixture.calls == 1


def test_uncertain_started_call_is_missing_and_never_resampled(tmp_path, monkeypatch):
    fixture, provider = setup_provider()
    manifest = first_purpose("readback")
    original = Journal.append

    def interrupted(self, event):
        original(self, event)
        if event["event"] == "attempt_started":
            raise KeyboardInterrupt

    monkeypatch.setattr(Journal, "append", interrupted)
    with pytest.raises(KeyboardInterrupt):
        run_manifest(manifest, tmp_path, provider, max_cells=1)
    monkeypatch.setattr(Journal, "append", original)
    final = run_manifest(manifest, tmp_path, provider, max_cells=1)
    assert final["completed_cells"] == 1 and fixture.calls == 0
    assert rows(tmp_path / "scores.csv")[0]["missing_reason"] == "ambiguous_infrastructure_attempt"


def test_failure_before_interrupt_resumes_next_attempt_without_resetting_budget(tmp_path, monkeypatch):
    fixture, _ = setup_provider()
    attempts = []

    def transport(payload):
        attempts.append(payload)
        if len(attempts) == 1:
            raise TimeoutError("fixture timeout")
        return fixture(payload)

    provider = PinnedProvider(ProviderSettings(model=fixture.model, provider=fixture.provider), transport)
    original = Journal.append

    def interrupted(self, event):
        original(self, event)
        if event["event"] == "attempt_failed":
            raise KeyboardInterrupt

    monkeypatch.setattr(Journal, "append", interrupted)
    manifest = first_purpose("readback")
    with pytest.raises(KeyboardInterrupt):
        run_manifest(manifest, tmp_path, provider, max_cells=1)
    monkeypatch.setattr(Journal, "append", original)
    final = run_manifest(manifest, tmp_path, provider, max_cells=1)
    assert final["completed_cells"] == 1
    assert final["infrastructure_retries"] == 1
    assert attempts[0] == attempts[1]
    assert [e["attempt"] for e in Journal(tmp_path / "calls.jsonl").events if e["event"] == "attempt_started"] == [1, 2]


def test_exhausted_infrastructure_is_missing_not_invalid(tmp_path):
    calls = []

    def timeout(payload):
        calls.append(payload)
        raise TimeoutError("fixture")

    provider = PinnedProvider(ProviderSettings(model="fixture", provider="fixture"), timeout)
    manifest = first_purpose("decision")
    final = run_manifest(manifest, tmp_path, provider, max_cells=1)
    assert len(calls) == 4 and all(p == calls[0] for p in calls)
    assert final["infrastructure_retries"] == 3 and final["invalid_first_actions"] == 0
    score = rows(tmp_path / "scores.csv")[0]
    assert score["category"] == "" and score["missing_reason"] == "infrastructure_exhausted:timeout"
    run_manifest(manifest, tmp_path, provider, max_cells=0)
    assert len(calls) == 4


def test_changed_settings_rejected_on_resume(tmp_path):
    fixture, provider = setup_provider()
    manifest = build_manifest("smoke")
    run_manifest(manifest, tmp_path, provider, max_cells=1)
    other = PinnedProvider(provider.settings.model_copy(update={"max_output_tokens": 513}), fixture)
    with pytest.raises(JournalIntegrityError, match="configuration_changed"):
        run_manifest(manifest, tmp_path, other)


def test_torn_final_journal_preserved_and_explicitly_blocked(tmp_path):
    fixture, provider = setup_provider()
    manifest = build_manifest("smoke")
    run_manifest(manifest, tmp_path, provider, max_cells=1)
    path = tmp_path / "calls.jsonl"
    with path.open("ab") as handle:
        handle.write(b'{"event":')
    before, calls = path.read_bytes(), fixture.calls
    with pytest.raises(JournalIntegrityError, match="torn_final"):
        run_manifest(manifest, tmp_path, provider)
    assert path.read_bytes() == before and fixture.calls == calls
    assert json.loads((tmp_path / "recovery_blocker.json").read_text())["raw_trace_preserved"] is True


def test_trace_hash_tampering_rejected(tmp_path):
    fixture, provider = setup_provider()
    run_manifest(build_manifest("smoke"), tmp_path, provider, max_cells=1)
    path = tmp_path / "calls.jsonl"
    content = path.read_text()
    path.write_text(content.replace('"phase_defined"', '"changed_phase"', 1), encoding="utf-8")
    with pytest.raises(JournalIntegrityError):
        rebuild_outputs(tmp_path)


def test_configuration_digest_tampering_rejected_during_offline_rebuild(tmp_path):
    fixture, provider = setup_provider()
    run_manifest(build_manifest("smoke"), tmp_path, provider, max_cells=0)
    path = tmp_path / "manifest.json"
    data = json.loads(path.read_text())
    data["run_config"]["reprompt_limit_per_episode"] = 2
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(JournalIntegrityError, match="configuration_hash"):
        rebuild_outputs(tmp_path)


def test_event_after_completion_rejected_even_with_valid_hash_chain(tmp_path):
    fixture, provider = setup_provider()
    manifest = first_purpose("readback")
    run_manifest(manifest, tmp_path, provider, max_cells=1)
    journal = Journal(tmp_path / "calls.jsonl")
    journal.append({"event": "tool_applied", "cell_id": manifest["cells"][0]["cell_id"], "phase": "readback", "transition": {}})
    with pytest.raises(JournalIntegrityError, match="after_completed"):
        rebuild_outputs(tmp_path)


def test_empty_run_has_all_required_artifacts_and_explicit_pending_cells(tmp_path):
    _, provider = setup_provider()
    summary = run_manifest(build_manifest("main"), tmp_path, provider, max_cells=0)
    assert {"manifest.json", "calls.jsonl", "scores.csv", "usage.csv", "analysis_manifest.json"} <= {p.name for p in tmp_path.iterdir()}
    assert summary["pending_cells"] == summary["planned_cells"] == 704
    assert {row["missing_reason"] for row in rows(tmp_path / "scores.csv")} == {"not_executed_yet"}


def test_fresh_fixture_on_resume_preserves_unique_deterministic_request_ids(tmp_path):
    fixture, provider = setup_provider()
    manifest = build_manifest("smoke")
    run_manifest(manifest, tmp_path, provider, max_cells=40)
    _, replacement = setup_provider()
    run_manifest(manifest, tmp_path, replacement)
    successes = [e for e in Journal(tmp_path / "calls.jsonl").events if e["event"] == "attempt_succeeded"]
    ids = [e["result"]["request_id"] for e in successes]
    assert len(ids) == len(set(ids)) == 144


@pytest.mark.parametrize("mutation,reason", [
    (lambda e: e.update(request_hash="wrong"), "request_hash_or_payload"),
    (lambda e: e["result"].update(returned_provider="wrong"), "reconciliation"),
    (lambda e: e["result"]["payload"].update(max_tokens=1), "reconciliation"),
    (lambda e: e["result"]["reply"].update(content="wrong parsed reply"), "parsing_disagrees"),
])
def test_rehashed_but_inconsistent_trace_is_rejected(tmp_path, mutation, reason):
    fixture, provider = setup_provider()
    run_manifest(first_purpose("readback"), tmp_path, provider, max_cells=1)
    path = tmp_path / "calls.jsonl"
    events = Journal(path).events
    success = next(e for e in events if e["event"] == "attempt_succeeded")
    mutation(success)
    # Deliberate corruption fixture: even a newly valid chain cannot conceal
    # mismatched payloads, settings, or raw-response/parsed-reply pairs.
    path.write_bytes(b"")
    replacement = Journal(path)
    for event in events:
        replacement.append({k: v for k, v in event.items() if k not in {"sequence", "previous_hash", "event_hash"}})
    with pytest.raises(JournalIntegrityError, match=reason):
        rebuild_outputs(tmp_path)


def test_input_manifest_binds_data_configuration_and_dependency_pins(tmp_path):
    _, provider = setup_provider()
    run_manifest(build_manifest("main"), tmp_path, provider, max_cells=0)
    data = json.loads((tmp_path / "manifest.json").read_text())
    hashes = data["run_config"]["input_hashes"]
    assert {"configs/main.yaml", "configs/pilot.yaml", "data/manifest.json", "data/worlds_main.jsonl", "data/worlds_pilot.jsonl", "data/worlds_smoke.jsonl", "pyproject.toml", "requirements.lock"} <= set(hashes)


def test_reentrant_writer_is_rejected_before_second_provider_call(tmp_path):
    fixture, _ = setup_provider()
    manifest = first_purpose("readback")
    nested_rejections = []
    provider = None

    def transport(payload):
        with pytest.raises(JournalIntegrityError, match="already_locked") as rejection:
            run_manifest(manifest, tmp_path, provider, max_cells=1)
        nested_rejections.append(str(rejection.value))
        return fixture(payload)

    provider = PinnedProvider(ProviderSettings(model=fixture.model, provider=fixture.provider), transport)
    summary = run_manifest(manifest, tmp_path, provider, max_cells=1)
    assert fixture.calls == len(nested_rejections) == summary["successful_calls"] == 1
    assert summary["completed_cells"] == 1
    assert rebuild_outputs(tmp_path) == summary
    # Leaving a lock-file inode behind does not leave an active/stale lock.
    assert run_manifest(manifest, tmp_path, provider, max_cells=0) == summary
