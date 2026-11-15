"""Synthetic continuation suffixes in isolated copies; never inference.

The retained empirical prefix stays byte-for-byte historical. Responses added
by these tests come only from ScriptedPublicPolicy through HTTPX MockTransport.
"""
import importlib.util
import hashlib
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import httpx
import pytest

from beyond_label import run as frozen_run
from beyond_label.attempts import ExecutionSuspended
from beyond_label.openrouter import OpenRouterPaidTransport
from beyond_label.provider import PinnedProvider, ProviderSettings, canonical_json
from test_main_continuation import stopped_copy


REPO = Path(__file__).resolve().parents[1]
PENDING = "main-2061-readback-MAIN-inline-b"
TERMINAL = "main-2013-decision-HIGH-STAKES-inline-a"


def load_executor(monkeypatch):
    path = REPO / "scripts/execute_main_continuation.py"
    assert path.is_file(), "The approved operational continuation executor is not implemented"
    monkeypatch.syspath_prepend(str(REPO / "scripts"))
    spec = importlib.util.spec_from_file_location("execute_main_continuation_test", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def trial_fixture(root, module, monkeypatch, *, fail=False, policy=None, receipt=True):
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-continuation-http-only")
    monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(frozen_run, "ROOT", root)
    approval = json.loads((REPO / "research/main_continuation_approval.json").read_bytes())
    shutil.copyfile(REPO / "research/main_continuation_approval.json",
                    root / "research/main_continuation_approval.json")
    source = root / "runs/staged_main"
    child = root / module.CHILD
    child.mkdir(parents=True, exist_ok=True)
    for path in source.iterdir():
        if path.is_file():
            shutil.copyfile(path, child / path.name)
    stored = json.loads((child / "manifest.json").read_bytes())
    settings = ProviderSettings.model_validate(stored["run_config"]["provider_settings"])
    scripted = frozen_run.ScriptedPublicPolicy(settings.model, settings.provider)
    clock, sent = Clock(), []

    def handler(request):
        sent.append((clock.now, request.content))
        if fail:
            return httpx.Response(429, json={"error": {"code": 429}})
        response = scripted(json.loads(request.content))
        response["openrouter_metadata"] = {"endpoints": {"available": [{
            "model": "deepseek/deepseek-v4.1-flash-20261017",
            "provider": "PrimeIntellect", "selected": True}]}}
        response["usage"].update(cost=.001, is_byok=False)
        if not receipt:
            response["usage"].pop("cost")
        return httpx.Response(200, json=response)

    transport = OpenRouterPaidTransport(settings.model, settings.provider_route,
                                        transport=httpx.MockTransport(handler))
    provider = PinnedProvider(settings, transport, sleep=clock.sleep, before_attempt=policy)
    return {"plan": stored["plan"], "journal": frozen_run.Journal(child / "calls.jsonl"),
            "eligible": approval["eligible_cell_ids"], "provider": provider,
            "sent": sent, "clock": clock, "child": child, "source": source,
            "settings": settings, "transport": transport}


def suffix_events(fixture, prefix):
    raw = (fixture["child"] / "calls.jsonl").read_bytes()
    assert raw.startswith(prefix)
    return [json.loads(line) for line in raw[len(prefix):].splitlines()]


def test_dispatcher_resumes_only_whitelist_and_preserves_parent(stopped_copy, monkeypatch):
    module = load_executor(monkeypatch)
    fixture = trial_fixture(stopped_copy, module, monkeypatch)
    parent = {p.name: p.read_bytes() for p in fixture["source"].iterdir() if p.is_file()}
    prefix = parent["calls.jsonl"]
    module.execute_pending(fixture["plan"], fixture["journal"], fixture["provider"],
                           fixture["eligible"], max_cells=3)
    events = suffix_events(fixture, prefix)
    starts = [e for e in events if e["event"] == "attempt_started"]
    completed = [e["cell_id"] for e in events if e["event"] == "cell_completed"]
    assert completed == fixture["eligible"][:3]
    assert starts[0]["cell_id"] == PENDING and starts[0]["attempt"] == 3
    assert {e["cell_id"] for e in events} == set(fixture["eligible"][:3])
    assert TERMINAL not in {e["cell_id"] for e in events}
    assert parent == {p.name: p.read_bytes() for p in fixture["source"].iterdir() if p.is_file()}
    original_completed = {json.loads(line)["cell_id"] for line in prefix.splitlines()
                          if json.loads(line)["event"] == "cell_completed"}
    assert len(original_completed) == 652
    assert not original_completed.intersection(e["cell_id"] for e in starts)
    assert len(fixture["sent"]) == len(starts)
    for (_, wire), start in zip(fixture["sent"], starts):
        assert wire == canonical_json(start["payload"]).encode("utf-8")
        payload = json.loads(wire)
        assert payload["model"] == "deepseek/deepseek-v4.1-flash-1017"
        assert payload["temperature"] == 0 and payload["max_tokens"] == 512
        assert payload["reasoning"] == {"effort": "none"}
        assert payload["provider"]["only"] == ["primeintellect"]
        assert payload["provider"]["allow_fallbacks"] is False
        if start["phase"] == "readback":
            assert not {"tools", "tool_choice", "parallel_tool_calls"} & payload.keys()
        else:
            assert payload["tool_choice"] == "auto" and payload["parallel_tool_calls"] is False


def test_max_cells_resume_skips_child_completed_cells(stopped_copy, monkeypatch):
    module = load_executor(monkeypatch)
    fixture = trial_fixture(stopped_copy, module, monkeypatch)
    prefix = (fixture["child"] / "calls.jsonl").read_bytes()
    module.execute_pending(fixture["plan"], fixture["journal"], fixture["provider"],
                           fixture["eligible"], max_cells=2)
    first = (fixture["child"] / "calls.jsonl").read_bytes()
    restarted = frozen_run.Journal(fixture["child"] / "calls.jsonl")
    module.execute_pending(fixture["plan"], restarted, fixture["provider"],
                           fixture["eligible"], max_cells=1)
    assert (fixture["child"] / "calls.jsonl").read_bytes().startswith(first)
    events = suffix_events(fixture, prefix)
    completed = [e["cell_id"] for e in events if e["event"] == "cell_completed"]
    assert completed == fixture["eligible"][:3]
    successes = [(e["cell_id"], e["phase"]) for e in events if e["event"] == "attempt_succeeded"]
    assert len(successes) == len(set(successes))


def test_pending_phase_preserves_cumulative_four_attempt_limit(stopped_copy, monkeypatch):
    module = load_executor(monkeypatch)
    fixture = trial_fixture(stopped_copy, module, monkeypatch, fail=True)
    prefix = (fixture["child"] / "calls.jsonl").read_bytes()
    module.execute_pending(fixture["plan"], fixture["journal"], fixture["provider"],
                           fixture["eligible"], max_cells=1)
    events = suffix_events(fixture, prefix)
    assert [e["attempt"] for e in events if e["event"] == "attempt_started"] == [3, 4]
    assert [e["retryable"] for e in events if e["event"] == "attempt_failed"] == [True, False]
    assert len(fixture["sent"]) == 2
    assert fixture["sent"][0][1] == fixture["sent"][1][1]
    assert events[-1]["event"] == "cell_completed"
    assert events[-1]["first_missing_reason"] == "infrastructure_exhausted:http_error"


def test_zero_cells_neither_dispatches_nor_appends(stopped_copy, monkeypatch):
    module = load_executor(monkeypatch)
    fixture = trial_fixture(stopped_copy, module, monkeypatch)
    prefix = (fixture["child"] / "calls.jsonl").read_bytes()
    module.execute_pending(fixture["plan"], fixture["journal"], fixture["provider"],
                           fixture["eligible"], max_cells=0)
    assert fixture["sent"] == []
    assert (fixture["child"] / "calls.jsonl").read_bytes() == prefix


def test_all_suffix_posts_receive_operational_pacing(stopped_copy, monkeypatch):
    module = load_executor(monkeypatch)
    from continuation_pacing import InferencePacer, paced_openrouter_clients
    fixture = trial_fixture(stopped_copy, module, monkeypatch)
    clock = fixture["clock"]
    pacer = InferencePacer(clock=clock.monotonic, sleep=clock.sleep)
    with paced_openrouter_clients(pacer):
        module.execute_pending(fixture["plan"], fixture["journal"], fixture["provider"],
                               fixture["eligible"], max_cells=3)
    times = [time for time, _ in fixture["sent"]]
    assert len(times) >= 3 and times[0] >= 15
    assert all(b - a >= 15 for a, b in zip(times, times[1:]))


@pytest.mark.parametrize("failed_http", [True, False])
def test_new_unknown_charge_stops_before_retry_or_next_cell(stopped_copy, monkeypatch, failed_http):
    module = load_executor(monkeypatch)
    from beyond_label.budget import BudgetLedger
    from beyond_label.controls import GuardedTransport
    from beyond_label.paid_controls import PaidSmokeQuote, paid_observed_cost
    from beyond_label.rate_limit import RateLimiter
    from beyond_label.staged import StagedAttemptLimit

    fixture = trial_fixture(stopped_copy, module, monkeypatch, fail=failed_http, receipt=False)
    session = stopped_copy / "runs/_paid_staged_session"
    ledger = BudgetLedger(session / "budget.jsonl", "9", "USD")
    counter = StagedAttemptLimit(session / "attempts.jsonl")
    policy = module.ApprovedHoldsPolicy(counter, ledger, maximum_cost="0.048468209664")
    clock = fixture["clock"]
    limiter = RateLimiter(10, 10490880, clock=clock.monotonic, sleep=clock.sleep)
    guard = GuardedTransport(fixture["transport"], ledger, limiter, PaidSmokeQuote(),
                             cost_reader=paid_observed_cost)
    provider = PinnedProvider(fixture["settings"], guard, sleep=clock.sleep, before_attempt=policy)
    prefix = (fixture["child"] / "calls.jsonl").read_bytes()
    before = ledger.snapshot()
    with pytest.raises(ExecutionSuspended, match="unknown|pending"):
        module.execute_pending(fixture["plan"], fixture["journal"], provider,
                               fixture["eligible"], max_cells=2)
    events = suffix_events(fixture, prefix)
    starts = [e for e in events if e["event"] == "attempt_started"]
    assert [(e["cell_id"], e["attempt"]) for e in starts] == [(PENDING, 3)]
    assert len(fixture["sent"]) == 1
    after = ledger.snapshot()
    assert after["unknown_cost_attempts"] == 41
    assert after["held"] == "1.987196596224"
    assert counter.snapshot()["reserved_attempts"] == 1562
    for attempt_id, original in before["attempts"].items():
        assert after["attempts"][attempt_id] == original
    if failed_http:
        assert not any(e["event"] == "cell_completed" for e in events)
        assert [e["retryable"] for e in events if e["event"] == "attempt_failed"] == [True]
    else:
        assert [e["event"] for e in events].count("attempt_succeeded") == 1
        assert [e["cell_id"] for e in events if e["event"] == "cell_completed"] == [PENDING]
    with pytest.raises(ExecutionSuspended, match="unknown|pending"):
        module.execute_pending(fixture["plan"], frozen_run.Journal(fixture["child"] / "calls.jsonl"),
                               provider, fixture["eligible"], max_cells=1)
    assert len(fixture["sent"]) == 1


def test_live_entry_without_operational_freeze_stops_before_network(stopped_copy, monkeypatch):
    module = load_executor(monkeypatch)
    monkeypatch.setattr(module, "ROOT", stopped_copy)
    monkeypatch.setattr(module, "EXECUTION_ROOT", stopped_copy)
    monkeypatch.setattr(frozen_run, "ROOT", stopped_copy)
    shutil.copyfile(REPO / "research/main_continuation_approval.json",
                    stopped_copy / "research/main_continuation_approval.json")
    before = {name: (stopped_copy / "runs/_paid_staged_session" / name).read_bytes()
              for name in ("budget.jsonl", "attempts.jsonl")}

    def forbidden(*args, **kwargs):
        pytest.fail("Missing operational freeze reached a network/preflight boundary")

    monkeypatch.setattr(module, "paid_account_preflight", forbidden)
    monkeypatch.setattr(module, "check_paid_smoke_capabilities", forbidden)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    with pytest.raises((ValueError, ExecutionSuspended, FileNotFoundError)):
        module.execute(max_cells=1)
    assert not (stopped_copy / module.CHILD).exists()
    assert before == {name: (stopped_copy / "runs/_paid_staged_session" / name).read_bytes()
                      for name in before}


def operational_fixture(root, module, monkeypatch):
    """A synthetic committed Git snapshot, with real blob parsing/validation."""
    monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(module, "EXECUTION_ROOT", root)
    monkeypatch.setattr(frozen_run, "ROOT", root)
    for pattern in ("scripts/*.py", "tests/*.py"):
        for source in REPO.glob(pattern):
            destination = root / source.relative_to(REPO)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
    shutil.copyfile(REPO / module.APPROVAL, root / module.APPROVAL)
    snapshot = {p.relative_to(root).as_posix(): p.read_bytes()
                for pattern in ("scripts/*.py", "tests/*.py") for p in root.glob(pattern)}
    snapshot[module.APPROVAL] = (root / module.APPROVAL).read_bytes()
    commit = "c" * 40

    def git_process(command, *, input, cwd, **kwargs):
        assert command == ["git", "cat-file", "--batch"]
        assert Path(cwd).resolve() == root.resolve()
        response = b""
        for spec in input.decode("ascii").splitlines():
            revision, name = spec.split(":", 1)
            assert revision == commit
            raw = snapshot[name]
            digest = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            response += f"{digest} blob {len(raw)}\n".encode() + raw + b"\n"
        return SimpleNamespace(returncode=0, stdout=response, stderr=b"")

    def git_identity(path, *args):
        assert Path(path).resolve() == root.resolve()
        if args[0] == "rev-parse":
            return commit
        assert args[0] == "ls-remote"
        return commit + "\trefs/tags/" + module.OPERATIONAL_TAG + "\n"

    monkeypatch.setattr(module.subprocess, "run", git_process)
    monkeypatch.setattr(module, "_git", git_identity)
    record = module.prepare_operational_freeze(commit, module.OPERATIONAL_TAG)
    (root / module.OPERATIONAL_FREEZE).write_text(json.dumps(record), encoding="utf-8")
    return record, snapshot


def test_operational_freeze_and_child_metadata_bind_exact_source(stopped_copy, monkeypatch):
    module = load_executor(monkeypatch)
    record, snapshot = operational_fixture(stopped_copy, module, monkeypatch)
    assert module.verify_operational_freeze(stopped_copy, require_remote=True) == record
    original = {p.name: p.read_bytes() for p in (stopped_copy / "runs/staged_main").iterdir() if p.is_file()}
    module._initialize_child(stopped_copy, record)
    child = module.verify_child_metadata(stopped_copy, record)
    metadata = child["continuation"]
    assert metadata["operational_source_commit"] == "c" * 40
    assert metadata["operational_freeze_record_hash"] == record["record_hash"]
    assert metadata["inherited_journal_bytes"] == len(original["calls.jsonl"])
    assert (stopped_copy / module.CHILD / "calls.jsonl").read_bytes() == original["calls.jsonl"]
    assert original == {p.name: p.read_bytes() for p in (stopped_copy / "runs/staged_main").iterdir() if p.is_file()}
    # A valid local hash is insufficient when the committed blob differs.
    snapshot["scripts/continuation_pacing.py"] += b"# synthetic differing commit\n"
    with pytest.raises(ExecutionSuspended, match="committed_input"):
        module.verify_operational_freeze(stopped_copy)


@pytest.mark.parametrize("mutation", ["approval", "freeze", "source", "child_source"])
def test_tampered_operational_provenance_stops_before_post(stopped_copy, monkeypatch, mutation):
    module = load_executor(monkeypatch)
    record, _ = operational_fixture(stopped_copy, module, monkeypatch)
    if mutation == "approval":
        path = stopped_copy / module.APPROVAL
        data = json.loads(path.read_bytes())
        data["approved"] = False
        path.write_text(json.dumps(data), encoding="utf-8")
    elif mutation == "freeze":
        path = stopped_copy / module.OPERATIONAL_FREEZE
        data = json.loads(path.read_bytes())
        data["source_commit"] = "d" * 40
        path.write_text(json.dumps(data), encoding="utf-8")
    elif mutation == "source":
        path = stopped_copy / "scripts/continuation_pacing.py"
        path.write_bytes(path.read_bytes() + b"# synthetic unreviewed edit\n")
    else:
        module._initialize_child(stopped_copy, record)
        path = stopped_copy / module.CHILD / "manifest.json"
        data = json.loads(path.read_bytes())
        data["continuation"]["operational_source_commit"] = "d" * 40
        path.write_text(json.dumps(data), encoding="utf-8")

    def forbidden(*args, **kwargs):
        pytest.fail("Tampered operational provenance reached network dispatch")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(module, "paid_account_preflight", forbidden)
    monkeypatch.setattr(module, "check_paid_smoke_capabilities", forbidden)
    if mutation == "child_source":
        with pytest.raises(ExecutionSuspended, match="metadata_changed"):
            module.verify_child_metadata(stopped_copy, record)
    else:
        with pytest.raises((ValueError, ExecutionSuspended)):
            module.execute(max_cells=1)


def test_wrong_execution_checkout_is_rejected_before_any_preflight(tmp_path, monkeypatch):
    module = load_executor(monkeypatch)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(frozen_run, "ROOT", tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("The wrong execution checkout reached evidence or network checks")

    monkeypatch.setattr(module, "load_approval", forbidden)
    monkeypatch.setattr(module, "paid_account_preflight", forbidden)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    with pytest.raises(ExecutionSuspended, match="execution.*(root|checkout)|designated"):
        module.execute(max_cells=1)


def test_full_execute_uses_real_guards_and_stores_one_synthetic_suffix_cell(stopped_copy, monkeypatch):
    """Only Git/account/network boundaries and clocks are synthetic here."""
    module = load_executor(monkeypatch)
    from beyond_label import freeze
    record, _ = operational_fixture(stopped_copy, module, monkeypatch)
    monkeypatch.setattr(freeze, "ROOT", stopped_copy)
    scientific = json.loads((stopped_copy / "research/execution_freeze.json").read_bytes())
    git_snapshot = {name: (stopped_copy / name).read_bytes() for name in scientific["input_hashes"]}
    git_snapshot[scientific["main_manifest_path"]] = (
        stopped_copy / scientific["main_manifest_path"]).read_bytes()

    def scientific_git(ref, path=None):
        assert ref in (scientific["tag"], "refs/tags/" + scientific["tag"], scientific["commit"])
        return scientific["commit"] if path is None else git_snapshot[path]

    def remote_identity(root, *args, **kwargs):
        assert Path(root).resolve() == stopped_copy.resolve()
        assert args[0] == "ls-remote"
        return scientific["commit"] + "\trefs/tags/" + scientific["tag"] + "\n"

    monkeypatch.setattr(freeze, "_git_resolve", scientific_git)
    monkeypatch.setattr(module.staged, "_git", remote_identity)
    monkeypatch.setattr(module, "check_paid_smoke_capabilities", lambda config: {"compatible": True})
    monkeypatch.setattr(module, "paid_account_preflight", lambda: {
        "key_hard_limit_usd": 10, "key_limit_remaining_usd": 9.5,
        "key_usage_usd": .5, "key_limit_reset": None, "budgets": None, "effective_budget": None})
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-full-continuation")
    clock, sent = Clock(), []
    rate_init = module.RateLimiter.__init__
    pace_init = module.InferencePacer.__init__

    def rate_clock(self, rpm, tpm, **kwargs):
        return rate_init(self, rpm, tpm, **{**kwargs, "clock": clock.monotonic, "sleep": clock.sleep})

    def pace_clock(self, **kwargs):
        return pace_init(self, **{**kwargs, "clock": clock.monotonic, "sleep": clock.sleep})

    monkeypatch.setattr(module.RateLimiter, "__init__", rate_clock)
    monkeypatch.setattr(module.InferencePacer, "__init__", pace_clock)
    monkeypatch.setattr(module, "time", SimpleNamespace(sleep=clock.sleep))
    scripted = frozen_run.ScriptedPublicPolicy("deepseek/deepseek-v4.1-flash-1017", "PrimeIntellect")

    def local_http(self, request):
        assert request.method == "POST"
        sent.append((clock.now, request.content))
        result = scripted(json.loads(request.content))
        result["openrouter_metadata"] = {"endpoints": {"available": [{
            "model": "deepseek/deepseek-v4.1-flash-20261017", "provider": "PrimeIntellect", "selected": True}]}}
        result["usage"].update(cost=.001, is_byok=False)
        return httpx.Response(200, json=result)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", local_http)
    original_client = httpx.Client
    parent = {p.name: p.read_bytes() for p in (stopped_copy / "runs/staged_main").iterdir() if p.is_file()}
    session = stopped_copy / "runs/_paid_staged_session"
    controls = {name: (session / name).read_bytes() for name in ("budget.jsonl", "attempts.jsonl")}
    result = module.execute(max_cells=1)
    assert result["status"] == "continuation_partial"
    assert len(sent) == 1 and sent[0][0] >= 60  # Original cold start remains active.
    assert httpx.Client is original_client
    child = stopped_copy / module.CHILD
    events = [json.loads(line) for line in (child / "calls.jsonl").read_bytes()[len(parent["calls.jsonl"]):].splitlines()]
    assert [(e["cell_id"], e["attempt"]) for e in events if e["event"] == "attempt_started"] == [(PENDING, 3)]
    assert [e["cell_id"] for e in events if e["event"] == "cell_completed"] == [PENDING]
    assert module.verify_child_metadata(stopped_copy, record)["continuation"]["operational_freeze_record_hash"] == record["record_hash"]
    assert parent == {p.name: p.read_bytes() for p in (stopped_copy / "runs/staged_main").iterdir() if p.is_file()}
    assert all((session / name).read_bytes().startswith(raw) for name, raw in controls.items())
    assert result["reconciliation"]["reserved_attempts"] == 1562
    assert result["reconciliation"]["held_reservations"] == 40
    assert result["reconciliation"]["settled_cost_usd"] == "0.19276235952"
