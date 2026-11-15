"""Synthetic interrupted-attempt regressions; never real model observations."""

import csv

import httpx
import pytest

from beyond_label.attempts import ExecutionSuspended
from beyond_label.provider import PinnedProvider, ProviderSettings
from beyond_label.run import (
    Journal, ScriptedPublicPolicy, build_manifest, rebuild_outputs, run_manifest,
)


def manifest_starting_with(purpose):
    for schedule_seed in range(100):
        manifest = build_manifest("smoke", schedule_seed=schedule_seed)
        if manifest["cells"][0]["purpose"] == purpose:
            return manifest
    raise AssertionError("No matching synthetic schedule")


def read_scores(directory):
    with (directory / "scores.csv").open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def fixture_http_404():
    request = httpx.Request("POST", "https://fixture.invalid/unused")
    return httpx.HTTPStatusError(
        "Synthetic HTTP404; no network", request=request,
        response=httpx.Response(404, request=request),
    )


@pytest.mark.parametrize("purpose", ["readback", "decision"])
def test_pending_http_failure_is_distinct_from_79_unattempted_cells(tmp_path, purpose):
    attempts = 0

    def stop_before_retry():
        nonlocal attempts
        attempts += 1
        if attempts > 1:
            raise ExecutionSuspended("fixture_unknown_cost_blocks_retry")

    def failing_transport(payload):
        raise fixture_http_404()

    provider = PinnedProvider(
        ProviderSettings(model="fixture", provider="fixture"),
        failing_transport, before_attempt=stop_before_retry,
    )
    manifest = manifest_starting_with(purpose)
    with pytest.raises(ExecutionSuspended, match="unknown_cost"):
        run_manifest(manifest, tmp_path, provider, max_cells=1)

    original_trace = (tmp_path / "calls.jsonl").read_bytes()
    rows = read_scores(tmp_path)
    assert len(rows) == 80
    assert rows[0]["cell_id"] == manifest["cells"][0]["cell_id"]
    assert rows[0]["cell_status"] == "pending"
    assert rows[0]["missing_reason"] == "pending_after_infrastructure_failure"
    assert all(row["missing_reason"] == "not_executed_yet" for row in rows[1:])
    events = Journal(tmp_path / "calls.jsonl").events
    failures = [event for event in events if event["event"] == "attempt_failed"]
    assert len(failures) == 1 and failures[0]["http_status"] == 404
    assert failures[0]["infrastructure"] is True
    assert not any(event["event"] == "cell_completed" for event in events)
    summary = rebuild_outputs(tmp_path)
    assert summary["attempted_calls"] == 1
    assert summary["successful_calls"] == summary["infrastructure_retries"] == 0
    assert summary["completed_cells"] == 0 and summary["pending_cells"] == 80
    assert (tmp_path / "calls.jsonl").read_bytes() == original_trace


def test_completed_infrastructure_failure_keeps_terminal_reason(tmp_path):
    def failing_transport(payload):
        raise fixture_http_404()

    provider = PinnedProvider(
        ProviderSettings(model="fixture", provider="fixture"), failing_transport,
    )
    summary = run_manifest(manifest_starting_with("readback"), tmp_path, provider, max_cells=1)
    first = read_scores(tmp_path)[0]
    assert first["cell_status"] == "completed"
    assert first["missing_reason"] == "infrastructure_exhausted:http_error"
    assert summary["attempted_calls"] == 4 and summary["infrastructure_retries"] == 3


def test_interrupted_continuation_preserves_observed_first_action(tmp_path):
    fixture = ScriptedPublicPolicy()
    attempts = 0

    def stop_before_retry():
        nonlocal attempts
        attempts += 1
        if attempts > 2:
            raise ExecutionSuspended("fixture_unknown_cost_blocks_retry")

    def partial_transport(payload):
        if attempts == 1:
            return fixture(payload)
        raise fixture_http_404()

    provider = PinnedProvider(
        ProviderSettings(model=fixture.model, provider=fixture.provider),
        partial_transport, before_attempt=stop_before_retry,
    )
    with pytest.raises(ExecutionSuspended, match="unknown_cost"):
        run_manifest(manifest_starting_with("decision"), tmp_path, provider, max_cells=1)
    first = read_scores(tmp_path)[0]
    assert first["cell_status"] == first["continuation_status"] == "pending"
    assert first["category"] == "INSPECT_1"
    assert first["expected_loss"] and first["regret"]
    assert first["missing_reason"] == ""
    assert first["realised_loss"] == first["post_inspection_correct"] == ""
    summary = rebuild_outputs(tmp_path)
    assert summary["attempted_calls"] == 2 and summary["successful_calls"] == 1
