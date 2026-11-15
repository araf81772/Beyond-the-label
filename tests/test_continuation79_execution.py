"""Synthetic integration proves the retained empirical cell is never dispatched."""
from copy import deepcopy
import csv
import json
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml

from beyond_label import continuation, continuation79, openrouter, paid_live, run
from beyond_label.budget import BudgetLedger
from beyond_label.cost_reconciliation import COVERAGE_PATH, build_cost_coverage_record
from test_paid_live import owner_fixture, write_config

REPO = Path(__file__).resolve().parents[1]
BASELINE_COMMIT = "de4b5080dcffbeadbc1ed1676ed384fbd5bce8fd"


@pytest.fixture(scope="module")
def controls():
    return {name: subprocess.run(["git", "show", f"{BASELINE_COMMIT}:runs/_paid_testing_session/{name}"],
        cwd=REPO, check=True, capture_output=True).stdout
        for name in ("authorization.json", "budget.jsonl", "attempts.jsonl")}


@pytest.fixture
def prepared79(tmp_path_factory, monkeypatch, controls):
    root = tmp_path_factory.mktemp("next79")
    live, runner, _, _, _ = owner_fixture(root, monkeypatch)
    config = yaml.safe_load((REPO / "configs/paid_smoke.yaml").read_text("utf-8"))
    path = write_config(root, config)
    (root / "research").mkdir()
    (root / live.MODEL_AMENDMENT).write_text(json.dumps(live.model_amendment_record()))
    segments = []
    for relative in (continuation.PAID_SMOKE_DIRECTORY, continuation.SEGMENT_DIRECTORY):
        target = root / relative
        target.mkdir(parents=True, exist_ok=True)
        for name in continuation.FILES:
            shutil.copyfile(REPO / relative / name, target / name)
        stored = json.loads((target / "manifest.json").read_text())
        segments.append({"directory":relative,"input_hashes":stored["run_config"]["input_hashes"]})
    session = root / "runs/_paid_testing_session"
    session.mkdir()
    for name, content in controls.items():
        (session/name).write_bytes(content)
    (root / COVERAGE_PATH).write_text(json.dumps(build_cost_coverage_record(root)))
    plan = runner.build_manifest("smoke", 2, 271828)
    record = {"record_hash":"a"*64,"active_source_commit":"b"*40,
        "active_directory":continuation79.SEGMENT_DIRECTORY,"plan":plan,
        "historical_segments":segments,"retained_cells":[continuation79.retained_cell_spec()],
        "dispatch_cell_ids":[c["cell_id"] for c in plan["cells"] if c["cell_id"] != continuation79.RETAINED_CELL_ID]}
    # Strict source/record verification is exercised in continuation79 tests.
    # This seam tests the real run/transport/accounting integration in isolation.
    monkeypatch.setattr(live,"load_continuation",lambda *a,**k:deepcopy(record))
    monkeypatch.setattr(continuation,"load_continuation",lambda *a,**k:deepcopy(record))
    fixture = runner.ScriptedPublicPolicy(config["model"],config["provider"])
    def request(method,url,*,payload,**kwargs):
        assert method == "POST"
        result = fixture(payload)
        result["openrouter_metadata"]={"endpoints":{"available":[{
            "model":"deepseek/deepseek-v4.1-flash-20261017","provider":config["provider"],"selected":True}]}}
        result["usage"].update(cost=.001,is_byok=False)
        return result
    monkeypatch.setattr(openrouter,"_request_json",request)
    return root,path,config,fixture,record


def original_bytes(root):
    return {p:p.read_bytes() for relative in (continuation.PAID_SMOKE_DIRECTORY,continuation.SEGMENT_DIRECTORY)
        for p in (root/relative).iterdir() if p.is_file() and not p.name.endswith(".writer.lock")}


def test_readiness79_is_read_only_and_preserves_shared_limits(prepared79):
    root,path,_,fixture,record=prepared79
    before={p:p.read_bytes() for p in (root/"runs").rglob("*") if p.is_file()}
    result=paid_live.check_smoke_readiness(path)
    assert result["ready"] and result["dispatchable_cells"]==79 and result["retained_terminal_cells"]==1
    assert result["attempts_consumed"]==2 and result["attempts_remaining"]==198
    assert result["known_settled_usd"]=="0.00005501216"
    assert result["retained_hold_usd"]=="0.44084208" and result["available_smoke_usd"]=="0.55910290784"
    assert fixture.calls==0 and not (root/record["active_directory"]).exists()
    assert all(p.read_bytes()==value for p,value in before.items())


def test_all79_fixture_cells_run_without_dispatching_rejected_cell_and_resume_is_noop(prepared79):
    root,path,config,fixture,record=prepared79
    before=original_bytes(root)
    result=paid_live.run_paid_smoke(path,"smoke",root/config["run_directory"])
    assert result["completed_cells"]==79 and result["retained_terminal_cells"]==1 and result["pending_cells"]==0
    assert result["planned_cells"]==80 and result["first_action_or_readback_missing"]==1
    active=root/record["active_directory"]
    journal=run.Journal(active/"calls.jsonl")
    assert continuation79.RETAINED_CELL_ID not in {e["cell_id"] for e in journal.events}
    starts=[e for e in journal.events if e["event"]=="attempt_started"]
    assert {e["cell_id"] for e in starts}==set(record["dispatch_cell_ids"])
    definitions=[e["cell_id"] for e in journal.events if e["event"]=="phase_defined" and e["phase"] in {"first","readback"}]
    assert definitions==record["dispatch_cell_ids"]
    with (active/"scores.csv").open(newline="") as stream: rows=list(csv.DictReader(stream))
    retained=next(r for r in rows if r["cell_id"]==continuation79.RETAINED_CELL_ID)
    assert len(rows)==80 and retained["cell_status"]=="retained_terminal" and retained["missing_reason"]=="model_mismatch"
    assert not retained["readback_correct"] and not retained["regret"]
    assert all(p.read_bytes()==data for p,data in before.items())
    count=fixture.calls
    assert paid_live.run_paid_smoke(path,"smoke",root/config["run_directory"])==result and fixture.calls==count
    state=BudgetLedger(root/"runs/_paid_testing_session/budget.jsonl","1").snapshot()
    assert state["held"]=="0.44084208" and len(state["attempts"])==2+count


def test_zero_cell_initialization_and_interrupted_resume_never_touch_retained_cell(prepared79):
    root,path,config,fixture,record=prepared79
    first=paid_live.run_paid_smoke(path,"smoke",root/config["run_directory"],max_cells=0)
    assert first["completed_cells"]==0 and first["pending_cells"]==79 and first["retained_terminal_cells"]==1
    assert fixture.calls==0
    second=paid_live.run_paid_smoke(path,"smoke",root/config["run_directory"],max_cells=1)
    assert second["completed_cells"]==1 and second["pending_cells"]==78
    events=run.Journal(root/record["active_directory"]/"calls.jsonl").events
    assert {e["cell_id"] for e in events}=={record["dispatch_cell_ids"][0]}


@pytest.mark.parametrize("mutation",["drop","id","reason","hash","dispatch","duplicate"])
def test_invalid_embedded_retention_is_rejected(prepared79,mutation):
    _,_,_,_,record=prepared79
    execution={"retained_terminal_cells":deepcopy(record["retained_cells"]),
        "continuation_dispatch_cell_ids":list(record["dispatch_cell_ids"]),
        "continuation_record_hash":record["record_hash"],"continuation_source_commit":record["active_source_commit"]}
    if mutation=="drop": execution["retained_terminal_cells"]=[]
    elif mutation=="id": execution["retained_terminal_cells"][0]["cell_id"]=record["dispatch_cell_ids"][0]
    elif mutation=="reason": execution["retained_terminal_cells"][0]["missing_reason"]=None
    elif mutation=="hash": execution["retained_terminal_cells"][0]["source_artifact_sha256"]["calls.jsonl"]="0"*64
    elif mutation=="dispatch": execution["continuation_dispatch_cell_ids"].append(continuation79.RETAINED_CELL_ID)
    else: execution["retained_terminal_cells"]*=2
    with pytest.raises(run.JournalIntegrityError):
        run._retained_terminal_cells({"execution_config":execution},record["plan"])


def test_journal_rejects_even_a_phase_event_for_retained_cell(prepared79):
    root,path,config,_,record=prepared79
    paid_live.run_paid_smoke(path,"smoke",root/config["run_directory"],max_cells=0)
    active=root/record["active_directory"]
    journal=run.Journal(active/"calls.jsonl")
    journal.append({"event":"cell_completed","cell_id":continuation79.RETAINED_CELL_ID})
    stored=json.loads((active/"manifest.json").read_text())
    with pytest.raises(run.JournalIntegrityError,match="event_for_retained"):
        run._validate_journal(journal,stored["plan"],stored["run_config"])


def test_new_unknown_cost_still_stops79_continuation_without_reset(prepared79, monkeypatch):
    root,path,config,fixture,record=prepared79
    original=openrouter._request_json
    def missing_cost(*args,**kwargs):
        response=original(*args,**kwargs)
        response["usage"].pop("is_byok")
        return response
    monkeypatch.setattr(openrouter,"_request_json",missing_cost)
    with pytest.raises(paid_live.ExecutionSuspended):
        paid_live.run_paid_smoke(path,"smoke",root/config["run_directory"],max_cells=2)
    assert fixture.calls==1
    ledger=BudgetLedger(root/"runs/_paid_testing_session/budget.jsonl","1").snapshot()
    assert ledger["unknown_cost_attempts"]==2 and len(ledger["attempts"])==3
    journal=run.Journal(root/record["active_directory"]/"calls.jsonl")
    assert all(e["cell_id"]!=continuation79.RETAINED_CELL_ID for e in journal.events)
