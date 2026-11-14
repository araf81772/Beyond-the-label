"""Durable attempt-cap tests using only local files and synthetic transports.

No fixture response, token count, cost or call is an empirical observation.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from beyond_label.attempts import AttemptLimit, AttemptLimitError, MAX_ATTEMPTS
from beyond_label.provider import PinnedProvider, ProviderSettings
from beyond_label.run import ScriptedPublicPolicy, build_manifest, run_manifest
from beyond_label.schemas import Request


def snapshot(reserved):
    return {"maximum_attempts": 10, "reserved_attempts": reserved, "remaining_attempts": 10 - reserved}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def rehash_records(path, records):
    """Keep semantic mutations while repairing hashes, so schema checks matter."""
    previous = "0" * 64
    encoded = []
    for event in records:
        event = {key: value for key, value in event.items() if key != "event_hash"}
        event["previous_hash"] = previous
        digest = hashlib.sha256(canonical(event)).hexdigest()
        event["event_hash"] = digest
        encoded.append(canonical(event) + b"\n")
        previous = digest
    path.write_bytes(b"".join(encoded))


def test_exact_cap_and_reserved_count_survive_reopen_and_cwd_change(tmp_path, monkeypatch):
    assert type(MAX_ATTEMPTS) is int and MAX_ATTEMPTS == 10
    monkeypatch.chdir(tmp_path)
    limit = AttemptLimit(Path("attempts.jsonl"))
    assert limit.snapshot() == snapshot(0)
    limit.claim()
    nested = tmp_path / "nested"
    nested.mkdir()
    monkeypatch.chdir(nested)
    limit.claim()
    reopened = AttemptLimit(tmp_path / "attempts.jsonl")
    assert reopened.snapshot() == snapshot(2)
    assert not (nested / "attempts.jsonl").exists()
    # Claims are reservations, not successful responses, and never disappear.
    reopened.claim()
    assert AttemptLimit(tmp_path / "attempts.jsonl").snapshot() == snapshot(3)


def test_attempt_eleven_never_appends_or_resets_on_restart(tmp_path):
    path = tmp_path / "attempts.jsonl"
    limit = AttemptLimit(path)
    for _ in range(10):
        assert limit.claim() is None
    before = path.read_bytes()
    for current in (limit, AttemptLimit(path)):
        with pytest.raises(AttemptLimitError):
            current.claim()
        assert current.snapshot() == snapshot(10)
        assert path.read_bytes() == before


@pytest.mark.parametrize("mutation", ["torn", "empty", "bad_hash", "duplicate_json_key",
                                     "changed_cap", "float_cap", "extra_field", "boolean_sequence"])
def test_corruption_or_rehashed_invalid_schema_is_preserved_and_rejected(tmp_path, mutation):
    path = tmp_path / "attempts.jsonl"
    limit = AttemptLimit(path)
    limit.claim()
    raw = path.read_bytes()
    records = [json.loads(line) for line in raw.splitlines()]
    if mutation == "torn":
        path.write_bytes(raw[:-1])
    elif mutation == "empty":
        path.write_bytes(b"")
    elif mutation == "bad_hash":
        records[-1]["event_hash"] = "f" * 64
        path.write_bytes(b"".join(canonical(record) + b"\n" for record in records))
    elif mutation == "duplicate_json_key":
        first, *rest = raw.splitlines()
        first = b'{"sequence":1,' + first[1:]
        path.write_bytes(b"\n".join([first, *rest]) + b"\n")
    else:
        if mutation in {"changed_cap", "float_cap"}:
            cap_fields = [key for key, value in records[0].items() if type(value) is int and value == 10]
            assert len(cap_fields) == 1
            records[0][cap_fields[0]] = 11 if mutation == "changed_cap" else 10.0
        elif mutation == "extra_field":
            records[-1]["unexpected"] = "synthetic-fixture-only"
        else:
            records[0]["sequence"] = True
        rehash_records(path, records)
    broken = path.read_bytes()
    with pytest.raises(AttemptLimitError):
        AttemptLimit(path)
    assert path.read_bytes() == broken


def test_fsync_failure_blocks_provider_dispatch_and_is_sticky(tmp_path, monkeypatch):
    path = tmp_path / "attempts.jsonl"
    limit = AttemptLimit(path)
    calls, events = [], []
    provider = PinnedProvider(ProviderSettings(model="fixture", provider="fixture"),
                              lambda payload: calls.append(payload), before_attempt=limit.claim)
    def failed_fsync(handle):
        raise OSError("synthetic-private-io-error")
    with monkeypatch.context() as context:
        context.setattr("beyond_label.attempts.os.fsync", failed_fsync)
        with pytest.raises(AttemptLimitError) as error:
            provider.request(Request(messages=[]), log_attempt=events.append)
        assert "synthetic-private-io-error" not in str(error.value)
    assert calls == [] and events == []
    durable = path.read_bytes()
    # Even if the append reached disk before fsync raised, no dispatch occurs.
    assert AttemptLimit(path).snapshot() == snapshot(1)
    with pytest.raises(AttemptLimitError):
        limit.claim()
    assert path.read_bytes() == durable


def test_concurrent_objects_cannot_claim_more_than_ten(tmp_path):
    path = tmp_path / "attempts.jsonl"
    objects = [AttemptLimit(path) for _ in range(4)]
    def claim(index):
        try:
            objects[index % len(objects)].claim()
            return True
        except AttemptLimitError:
            return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(claim, range(32)))
    current = AttemptLimit(path).snapshot()
    assert 0 < current["reserved_attempts"] <= 10
    assert current["reserved_attempts"] == sum(outcomes)
    # Lock contention may fail closed; completing the unused allowance is safe.
    remaining = current["remaining_attempts"]
    for _ in range(remaining):
        AttemptLimit(path).claim()
    assert AttemptLimit(path).snapshot() == snapshot(10)


def test_processes_share_one_durable_allowance(tmp_path):
    path = tmp_path / "attempts.jsonl"
    AttemptLimit(path)
    source = """
import json, sys, time
from beyond_label.attempts import AttemptLimit, AttemptLimitError
successes = 0
for _ in range(14):
    try:
        AttemptLimit(sys.argv[1]).claim()
        successes += 1
    except AttemptLimitError:
        pass
    time.sleep(0.005)
print(json.dumps({'successes': successes}))
"""
    environment = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
                   "PYTHONDONTWRITEBYTECODE": "1"}
    children = [subprocess.Popen([sys.executable, "-B", "-c", source, str(path)], env=environment,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
    try:
        observed = []
        for child in children:
            out, err = child.communicate(timeout=30)
            assert child.returncode == 0, "Local attempt-limit child process failed"
            observed.append(json.loads(out)["successes"])
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
                child.communicate(timeout=10)
    reserved = AttemptLimit(path).snapshot()["reserved_attempts"]
    assert reserved == sum(observed)
    assert 0 < reserved <= 10


def first_decision_plan():
    return next(build_manifest("smoke", schedule_seed=seed) for seed in range(100)
                if build_manifest("smoke", schedule_seed=seed)["cells"][0]["purpose"] == "decision")


def synthetic_provider(policy, limit, transport=None):
    return PinnedProvider(ProviderSettings(model=policy.model, provider=policy.provider),
                          policy if transport is None else transport, before_attempt=limit.claim)


def test_ninth_prior_claim_leaves_one_call_then_pauses_continuation_without_resampling(tmp_path):
    limit = AttemptLimit(tmp_path / "attempts.jsonl")
    for _ in range(9):
        limit.claim()
    policy = ScriptedPublicPolicy()
    provider = synthetic_provider(policy, limit)
    output, plan = tmp_path / "synthetic-smoke", first_decision_plan()
    with pytest.raises(AttemptLimitError):
        run_manifest(plan, output, provider, max_cells=1)
    raw = (output / "calls.jsonl").read_bytes()
    assert policy.calls == 1 and limit.snapshot() == snapshot(10)
    assert raw.count(b'"event":"attempt_started"') == 1
    assert b'"phase":"continuation"' in raw
    provider.before_attempt = AttemptLimit(tmp_path / "attempts.jsonl").claim
    with pytest.raises(AttemptLimitError):
        run_manifest(plan, output, provider, max_cells=1)
    assert policy.calls == 1
    assert (output / "calls.jsonl").read_bytes() == raw


def test_retry_after_tenth_claim_is_blocked_before_new_attempt_started(tmp_path):
    limit = AttemptLimit(tmp_path / "attempts.jsonl")
    for _ in range(9):
        limit.claim()
    calls, events = [], []
    def timeout(payload):
        calls.append(payload)
        raise TimeoutError("synthetic timeout")
    provider = PinnedProvider(ProviderSettings(model="fixture", provider="fixture"), timeout,
                              before_attempt=limit.claim)
    with pytest.raises(AttemptLimitError):
        provider.request(Request(messages=[]), log_attempt=events.append)
    assert len(calls) == 1 and limit.snapshot() == snapshot(10)
    assert [event["event"] for event in events] == ["attempt_started", "attempt_failed"]
    assert events[-1]["infrastructure"] is True


def test_reprompt_and_continuation_each_consume_durable_claim(tmp_path):
    limit = AttemptLimit(tmp_path / "attempts.jsonl")
    policy = ScriptedPublicPolicy()
    calls = []
    def transport(payload):
        assert limit.snapshot()["reserved_attempts"] == len(calls) + 1
        calls.append(payload)
        raw = policy(payload)
        if len(calls) == 1:
            raw["choices"][0]["message"] = {"role": "assistant", "content": "Need a tool response"}
            raw["choices"][0]["finish_reason"] = "stop"
        return raw
    result = run_manifest(first_decision_plan(), tmp_path / "synthetic-smoke",
                           synthetic_provider(policy, limit, transport), max_cells=1)
    assert len(calls) == 3 and limit.snapshot() == snapshot(3)
    assert result["permitted_reprompts"] == 1 and result["continuations"] == 1
    assert result["completed_cells"] == 1


def test_completed_synthetic_run_resume_makes_no_claim_or_additional_calls(tmp_path):
    # Populate a completed *synthetic* fixture first, never empirical evidence.
    policy = ScriptedPublicPolicy()
    provider = PinnedProvider(ProviderSettings(model=policy.model, provider=policy.provider), policy)
    output, plan = tmp_path / "synthetic-complete", build_manifest("smoke")
    completed = run_manifest(plan, output, provider)
    previous_calls = policy.calls
    before = (output / "calls.jsonl").read_bytes()
    limit = AttemptLimit(tmp_path / "attempts.jsonl")
    for _ in range(10):
        limit.claim()
    provider.before_attempt = limit.claim
    resumed = run_manifest(plan, output, provider)
    assert resumed == completed
    assert policy.calls == previous_calls and limit.snapshot() == snapshot(10)
    assert (output / "calls.jsonl").read_bytes() == before
