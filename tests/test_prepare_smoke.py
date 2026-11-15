"""Preparation commits metadata only; tests never authorize a provider call."""
import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('prepare_smoke_test',ROOT/'scripts/prepare_smoke.py')
prepare=importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


@pytest.fixture
def prepared_tree(tmp_path,monkeypatch):
    (tmp_path/'research').mkdir()
    (tmp_path/'runs').mkdir()
    (tmp_path/'runs/raw.jsonl').write_bytes(b'original evidence\n')
    monkeypatch.setattr(prepare,'ROOT',tmp_path)
    monkeypatch.setattr(prepare,'_inputs',lambda:{'fixture':'hash'})
    monkeypatch.setattr(prepare,'replay_historical',lambda *a:{'verified':True})
    monkeypatch.setattr(prepare,'build_continuation_record',lambda *a,**k:{'active_directory':'runs/fixed/segment'})
    monkeypatch.setattr(prepare,'build_cost_coverage_record',lambda *a:{'actual_cost':None,'held':'0.44084208'})
    return tmp_path


def test_preparation_writes_only_records_and_is_idempotent(prepared_tree):
    first=prepare.prepare('a'*40)
    before={p.relative_to(prepared_tree).as_posix():p.read_bytes() for p in prepared_tree.rglob('*') if p.is_file()}
    assert prepare.prepare('a'*40)==first
    assert before=={p.relative_to(prepared_tree).as_posix():p.read_bytes() for p in prepared_tree.rglob('*') if p.is_file()}
    assert first['inference_calls']==first['account_checks']==0
    assert not (prepared_tree/'runs/fixed').exists()
    assert (prepared_tree/'runs/raw.jsonl').read_bytes()==b'original evidence\n'


def test_changed_existing_record_is_not_overwritten_or_partially_prepared(prepared_tree):
    path=prepared_tree/prepare.COVERAGE_PATH
    path.write_text(json.dumps({'tampered':True}))
    with pytest.raises(ValueError,match='differs'):
        prepare.prepare('a'*40)
    assert json.loads(path.read_text())=={'tampered':True}
    assert not (prepared_tree/prepare.CONTINUATION_RECORD).exists()
    assert not (prepared_tree/prepare.MODEL_AMENDMENT).exists()


def test_source_proof_failure_writes_nothing(prepared_tree,monkeypatch):
    def rejected(*args,**kwargs):
        raise ValueError('source mismatch')
    monkeypatch.setattr(prepare,'build_continuation_record',rejected)
    with pytest.raises(ValueError,match='source mismatch'):
        prepare.prepare('b'*40)
    assert list((prepared_tree/'research').iterdir())==[]
