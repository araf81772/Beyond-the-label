import csv
import json

import pytest

from beyond_label.provider import PinnedProvider, ProviderFailure, ProviderSettings
from beyond_label.schemas import Request
from beyond_label.run import Journal, ScriptedPublicPolicy, build_manifest, rebuild_outputs, run_manifest


def first_decision_manifest():
    for seed in range(100):
        manifest = build_manifest("smoke", schedule_seed=seed)
        if manifest["cells"][0]["purpose"] == "decision":
            return manifest
    raise AssertionError


def response(fixture, *, content=None, tool_calls=None, refused=False):
    fixture.calls += 1
    message = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    if refused:
        message["refusal"] = "Synthetic explicit refusal"
    return {"model": fixture.model, "provider": fixture.provider, "id": f"fixture-reply-{fixture.calls}",
            "choices": [{"message": message, "finish_reason": "stop"}], "usage": {}}


def test_complete_offline_matrix_replays_to_identical_scores_and_usage(tmp_path):
    fixture = ScriptedPublicPolicy()
    provider = PinnedProvider(ProviderSettings(model=fixture.model, provider=fixture.provider), fixture)
    result = run_manifest(build_manifest("main"), tmp_path, provider)
    assert result["planned_cells"] == result["completed_cells"] == 704
    assert result["successful_calls"] == fixture.calls == 1152
    assert result["continuations"] == 448
    assert result["first_action_or_readback_missing"] == result["invalid_first_actions"] == 0
    assert result["empirical_observations"] == result["experimental_provider_spend"] == 0
    before = {name: (tmp_path / name).read_bytes() for name in ("calls.jsonl", "scores.csv", "usage.csv", "analysis_manifest.json")}
    assert rebuild_outputs(tmp_path) == result
    assert all((tmp_path / name).read_bytes() == data for name, data in before.items())
    assert b"\r\n" not in before["scores.csv"]
    with (tmp_path / "scores.csv").open(encoding="utf-8", newline="") as handle:
        scores = list(csv.DictReader(handle))
    assert {row["evidence_kind"] for row in scores} == {"synthetic"}
    assert {row["readback_correct"] for row in scores if row["purpose"] == "readback"} == {"true"}


def test_one_reprompt_per_episode_not_one_per_turn(tmp_path):
    fixture = ScriptedPublicPolicy()
    calls = []

    def transport(payload):
        calls.append(payload)
        if len(calls) in (1, 3):
            return response(fixture, content="Synthetic no-tool response")
        return fixture(payload)

    provider = PinnedProvider(ProviderSettings(model=fixture.model, provider=fixture.provider), transport)
    result = run_manifest(first_decision_manifest(), tmp_path, provider, max_cells=1)
    assert len(calls) == 3
    assert result["permitted_reprompts"] == 1
    phases = [e["phase"] for e in Journal(tmp_path / "calls.jsonl").events if e["event"] == "phase_defined"]
    assert phases == ["first", "first_reprompt", "continuation"]
    with (tmp_path / "scores.csv").open(encoding="utf-8", newline="") as handle:
        first = next(csv.DictReader(handle))
    assert first["category"] == "INSPECT_1"
    assert first["continuation_status"] == "invalid:INVALID_NONE"
    assert first["realised_loss"] == "" and first["missing_reason"] == ""


def test_continuation_may_use_the_single_unused_reprompt(tmp_path):
    fixture = ScriptedPublicPolicy()
    calls = []

    def transport(payload):
        calls.append(payload)
        return response(fixture, content="Synthetic no-tool") if len(calls) == 2 else fixture(payload)

    provider = PinnedProvider(ProviderSettings(model=fixture.model, provider=fixture.provider), transport)
    result = run_manifest(first_decision_manifest(), tmp_path, provider, max_cells=1)
    assert len(calls) == 3 and result["permitted_reprompts"] == 1
    phases = [e["phase"] for e in Journal(tmp_path / "calls.jsonl").events if e["event"] == "phase_defined"]
    assert phases == ["first", "continuation", "continuation_reprompt"]


@pytest.mark.parametrize("refused", [False, True])
def test_invalid_action_or_refusal_is_not_resampled(tmp_path, refused):
    fixture = ScriptedPublicPolicy()
    calls = []

    def transport(payload):
        calls.append(payload)
        if refused:
            return response(fixture, refused=True)
        return response(fixture, tool_calls=[{"id": "bad", "type": "function", "function": {"name": "inspect", "arguments": '{"lot_id":"LOT-0000"}'}}])

    provider = PinnedProvider(ProviderSettings(model=fixture.model, provider=fixture.provider), transport)
    result = run_manifest(first_decision_manifest(), tmp_path, provider, max_cells=1)
    assert len(calls) == 1
    assert result["invalid_first_actions"] == 1
    assert result["permitted_reprompts"] == result["infrastructure_retries"] == 0


def test_continuation_infrastructure_failure_preserves_first_action(tmp_path):
    fixture = ScriptedPublicPolicy()
    count = 0

    def transport(payload):
        nonlocal count
        count += 1
        if count > 1:
            raise TimeoutError("synthetic")
        return fixture(payload)

    provider = PinnedProvider(ProviderSettings(model=fixture.model, provider=fixture.provider), transport)
    result = run_manifest(first_decision_manifest(), tmp_path, provider, max_cells=1)
    assert count == 5 and result["infrastructure_retries"] == 3
    with (tmp_path / "scores.csv").open(encoding="utf-8", newline="") as handle:
        first = next(csv.DictReader(handle))
    assert first["category"] == "INSPECT_1" and first["missing_reason"] == ""
    assert first["continuation_status"] == "missing:infrastructure_exhausted:timeout"
    assert first["realised_loss"] == ""


def test_sensitive_request_rejected_before_any_request_journal_entry(tmp_path, monkeypatch):
    import beyond_label.run as harness
    sentinel = "synthetic-credential-sentinel-do-not-save"
    monkeypatch.setenv("OPENROUTER_API_KEY", sentinel)
    monkeypatch.setattr(harness, "decision_request", lambda case: Request(messages=[{"role": "system", "content": sentinel}]))
    fixture = ScriptedPublicPolicy()
    provider = PinnedProvider(ProviderSettings(model=fixture.model, provider=fixture.provider), fixture)
    result = run_manifest(first_decision_manifest(), tmp_path, provider, max_cells=1)
    assert fixture.calls == 0 and result["completed_cells"] == 1
    assert all(sentinel.encode() not in path.read_bytes() for path in tmp_path.rglob("*") if path.is_file())
    events = Journal(tmp_path / "calls.jsonl").events
    assert [e["event"] for e in events] == ["cell_completed"]
    assert events[0]["first_missing_reason"] == "credential_or_header_in_request"


def test_sensitive_provider_settings_rejected_before_manifest_write(tmp_path, monkeypatch):
    sentinel = "synthetic-credential-setting-do-not-save"
    monkeypatch.setenv("OPENROUTER_API_KEY", sentinel)
    fixture = ScriptedPublicPolicy()
    provider = PinnedProvider(ProviderSettings(model=sentinel, provider=fixture.provider), fixture)
    output = tmp_path / "rejected"
    with pytest.raises(ProviderFailure, match="credential_or_header_in_request"):
        run_manifest(build_manifest("smoke"), output, provider, max_cells=1)
    assert not output.exists() and fixture.calls == 0
