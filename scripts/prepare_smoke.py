"""Prepare the approved source version and conservative coverage without calls."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from replay_history import replay_historical
from beyond_label.continuation import CONTINUATION_RECORD, build_continuation_record
from beyond_label.cost_reconciliation import COVERAGE_PATH, build_cost_coverage_record
from beyond_label.paid_live import MODEL_AMENDMENT, model_amendment_record
from beyond_label.run import _inputs


def prepare(source_commit: str) -> dict:
    root = ROOT
    original = {p:p.read_bytes() for p in (root/'runs').rglob('*')
                if p.is_file() and not p.name.endswith('.writer.lock')}
    proof = replay_historical(root,root/'runs/paid_smoke_gpt41mini_20261115')
    record = build_continuation_record(root,source_commit=source_commit,
                                       input_hashes=_inputs(),replay_proof=proof)
    artifacts = {CONTINUATION_RECORD:record,COVERAGE_PATH:build_cost_coverage_record(root),
                 MODEL_AMENDMENT:model_amendment_record()}
    for name,value in artifacts.items():
        path=root/name
        if path.exists() and json.loads(path.read_text('utf-8')) != value:
            raise ValueError('Prepared record differs; preserve its history before preparing another version')
    for name,value in artifacts.items():
        path=root/name
        if not path.exists():
            with path.open('x',encoding='utf-8',newline='\n') as stream:
                stream.write(json.dumps(value,indent=2)+'\n')
    if any(p.read_bytes()!=data for p,data in original.items()):
        raise ValueError('Historical run or shared control changed during preparation')
    return {'status':'prepared_not_executed','active_source_commit':source_commit,
            'active_directory':record['active_directory'],'unique_planned_cells':80,
            'record_sha256':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in artifacts},
            'original_run_and_controls_unchanged':True,'inference_calls':0,'account_checks':0}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-commit',required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.source_commit),indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
