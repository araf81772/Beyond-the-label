"""Readiness and version integration use local fixtures, never provider calls."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest
import yaml

from beyond_label import continuation, openrouter, paid_live, run
from beyond_label.budget import BudgetLedger
from beyond_label.cost_reconciliation import COVERAGE_PATH, build_cost_coverage_record
from beyond_label.paid_profile import get_paid_profile
from test_paid_live import owner_fixture, write_config

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def prepared(tmp_path_factory, monkeypatch):
    root = tmp_path_factory.mktemp('ready')
    live, runner, _, _, _ = owner_fixture(root, monkeypatch)
    config = yaml.safe_load((REPO / 'configs/paid_smoke.yaml').read_text())
    path = write_config(root, config)
    (root / live.MODEL_AMENDMENT).parent.mkdir(exist_ok=True)
    (root / live.MODEL_AMENDMENT).write_text(json.dumps(live.model_amendment_record()))
    for relative in ('runs/paid_smoke_gpt41mini_20261115', 'runs/_paid_testing_session'):
        target = root / relative
        target.mkdir(parents=True)
        for source in (REPO / relative).iterdir():
            if source.is_file() and not source.name.endswith('.writer.lock'):
                shutil.copyfile(source, target / source.name)
    shutil.copyfile(REPO / 'research/run_sources.json', root / 'research/run_sources.json')
    (root / COVERAGE_PATH).write_text(json.dumps(build_cost_coverage_record(root)))
    # Source/commit verification is separately exercised by continuation tests.
    # This seam tests the complete transport/accounting integration contract.
    record = {'record_hash':'a'*64,'active_source_commit':'b'*40,
              'active_directory':continuation.SEGMENT_DIRECTORY}
    monkeypatch.setattr(live, 'load_continuation', lambda *a, **k: deepcopy(record))
    monkeypatch.setattr(continuation, 'load_continuation', lambda *a, **k: deepcopy(record))
    fixture = runner.ScriptedPublicPolicy(config['model'], config['provider'])
    def mock_request(method, url, *, payload, **kwargs):
        assert method == 'POST'
        result = fixture(payload)
        result['openrouter_metadata'] = {'endpoints':{'available':[
            {'model':config['model'],'provider':config['provider'],'selected':True}]}}
        result['usage'].update(cost=.001, is_byok=False)
        return result
    monkeypatch.setattr(openrouter, '_request_json', mock_request)
    return root, path, config, fixture, record


def retained_bytes(root):
    return {p.relative_to(root).as_posix():p.read_bytes() for p in (root/'runs').rglob('*')
            if p.is_file() and not p.name.endswith('.writer.lock')}


def test_ready_check_is_read_only_and_keeps_unknown_actual_cost(prepared, monkeypatch):
    root, path, config, fixture, record = prepared
    before = retained_bytes(root)
    monkeypatch.setattr(paid_live, 'run_paid_smoke', lambda *a, **k: pytest.fail('readiness cannot run smoke'))
    result = paid_live.check_smoke_readiness(path)
    assert result['ready'] and not result['execution_started'] and result['inference_calls'] == 0
    assert result['retained_hold_usd'] == '0.44084208'
    assert result['available_smoke_usd'] == '0.55915792'
    assert not result['actual_cost_evidence_complete']
    assert result['attempts_consumed'] == 1 and result['attempts_remaining'] == 199
    assert result['next_attempt_upper_bound_usd'] == get_paid_profile(config['model'])['maximum_cost']
    assert fixture.calls == 0 and retained_bytes(root) == before
    assert not (root / record['active_directory']).exists()


def test_missing_route_support_cannot_be_labelled_ready(prepared):
    _, path, _, fixture, _ = prepared
    result = paid_live.check_smoke_readiness(path, capability_evidence={'compatible':False})
    assert result['ready'] is False and result['status'] == 'blocked'
    assert fixture.calls == 0


def test_versioned_mock_execution_preserves_old_sample_and_shared_caps(prepared):
    root, path, config, fixture, record = prepared
    old = root / config['run_directory']
    original = {p.name:p.read_bytes() for p in old.iterdir() if p.is_file()}
    result = paid_live.run_paid_smoke(path, 'smoke', old, max_cells=1)
    assert result['completed_cells'] == result['attempted_calls'] == fixture.calls == 1
    assert {p.name:p.read_bytes() for p in old.iterdir() if p.is_file()} == original
    state = BudgetLedger(root/'runs/_paid_testing_session/budget.jsonl', '1').snapshot()
    assert state['held'] == '0.44084208' and state['settled_cost'] == '0.001'
    assert state['unknown_cost_attempts'] == 1
    second = paid_live.run_paid_smoke(path, 'smoke', old, max_cells=0)
    assert second == result and fixture.calls == 1
    journal = run.Journal(root/record['active_directory']/'calls.jsonl')
    starts = [e for e in journal.events if e['event'] == 'attempt_started']
    assert len(starts) == 1 and starts[0]['attempt'] == 1
    saved = json.loads((root/record['active_directory']/'manifest.json').read_text())
    assert saved['run_config']['execution_config']['continuation_record_hash'] == record['record_hash']
    assert saved['run_config']['provider_settings']['model'] == config['model']


def test_new_unknown_charge_still_blocks_without_resetting_old_hold(prepared, monkeypatch):
    root, path, config, fixture, _ = prepared
    original = openrouter._request_json
    def unknown(*a, **k):
        response = original(*a, **k)
        response['usage'].pop('is_byok')
        return response
    monkeypatch.setattr(openrouter, '_request_json', unknown)
    with pytest.raises(paid_live.ExecutionSuspended):
        paid_live.run_paid_smoke(path, 'smoke', root/config['run_directory'], max_cells=2)
    assert fixture.calls == 1
    state = BudgetLedger(root/'runs/_paid_testing_session/budget.jsonl','1').snapshot()
    assert state['unknown_cost_attempts'] == 2
    assert state['attempts'][next(iter(state['attempts']))]['maximum_cost'] == '0.44084208'


@pytest.mark.parametrize('mutation', ['absent','model','cap','run_now','boolean_alias'])
def test_model_change_needs_exact_recorded_user_amendment(prepared, mutation):
    root, path, config, fixture, _ = prepared
    target = root/paid_live.MODEL_AMENDMENT
    if mutation == 'absent':
        target.unlink()
    else:
        record = json.loads(target.read_text())
        if mutation == 'boolean_alias':
            record['schema_version'] = True
        else:
            record[{'model':'model','cap':'smoke_usd','run_now':'run_now'}[mutation]] = 'changed'
        target.write_text(json.dumps(record))
    with pytest.raises(paid_live.ExecutionSuspended, match='amendment'):
        paid_live.check_smoke_readiness(path)
    assert fixture.calls == 0


@pytest.mark.parametrize('arguments', [[], ['--check-ready']])
def test_cli_defaults_to_readiness_without_execution(monkeypatch, arguments):
    monkeypatch.setattr('sys.argv', ['paid_live', *arguments])
    monkeypatch.setattr(paid_live, 'check_smoke_readiness', lambda path:{'ready':True,'inference_calls':0})
    monkeypatch.setattr(paid_live, 'run_paid_smoke', lambda *a, **k:pytest.fail('unexpected execution'))
    assert paid_live.main() == 0


def test_cli_execution_options_require_explicit_execute(monkeypatch):
    monkeypatch.setattr('sys.argv', ['paid_live', '--max-cells','1'])
    monkeypatch.setattr(paid_live, 'run_paid_smoke', lambda *a, **k:pytest.fail('unexpected execution'))
    with pytest.raises(SystemExit) as caught:
        paid_live.main()
    assert caught.value.code == 2
