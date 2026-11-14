"""Generate provisional plans and exercise the full pipeline with a local fixture."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from beyond_label.analyze import analyze_run
from beyond_label.evidence import export_evidence
from beyond_label.figures import figures_for_run
from beyond_label.provider import PinnedProvider, ProviderSettings
from beyond_label.run import ScriptedPublicPolicy, build_manifest, rebuild_outputs, run_manifest


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('evaluation/synthetic_main_load2_final'))
    args=parser.parse_args()
    plans=ROOT/'data/plans';plans.mkdir(parents=True,exist_ok=True)
    for dataset,load in [('main',2),('main',8),('pilot',2),('smoke',2),('smoke',8)]:
        (plans/f'{dataset}_load{load}.json').write_text(json.dumps(build_manifest(dataset,load),indent=2)+'\n',encoding='utf-8',newline='\n')
    fixture=ScriptedPublicPolicy()
    provider=PinnedProvider(ProviderSettings(model=fixture.model,provider=fixture.provider),fixture)
    run_dir=args.output
    summary=run_manifest(build_manifest('main',2),run_dir,provider)
    raw_before=hashlib.sha256((run_dir/'calls.jsonl').read_bytes()).hexdigest()
    derived_before={name:hashlib.sha256((run_dir/name).read_bytes()).hexdigest()
                    for name in ('scores.csv','usage.csv','analysis_manifest.json')}
    rebuild_outputs(run_dir)
    assert derived_before=={name:hashlib.sha256((run_dir/name).read_bytes()).hexdigest() for name in derived_before}
    previous_calls=fixture.calls
    resumed=run_manifest(build_manifest('main',2),run_dir,provider)
    assert fixture.calls==previous_calls and resumed==summary
    assert hashlib.sha256((run_dir/'calls.jsonl').read_bytes()).hexdigest()==raw_before
    analysis=analyze_run(run_dir,allow_synthetic=True)
    figures=figures_for_run(run_dir,allow_synthetic=True)
    evidence=export_evidence(run_dir,allow_synthetic=True)
    assert analysis['evidence_kind']=='synthetic'
    record={'classification':'SYNTHETIC VALIDATION ONLY — NOT EMPIRICAL RESULTS',
            'empirical_observations':0,'actual_experimental_api_calls':0,'actual_experimental_api_spend':0,
            'planned_cells':summary['planned_cells'],'completed_cells':summary['completed_cells'],
            'synthetic_successful_calls':summary['successful_calls'],'synthetic_retries':summary['infrastructure_retries'],
            'synthetic_invalid_first_actions':summary['invalid_first_actions'],'synthetic_missing_cells':summary['first_action_or_readback_missing'],
            'resume_issued_no_duplicate_calls':True,'offline_regeneration_byte_identical':True,
            'raw_trace_preserved':True,'raw_trace_sha256':raw_before,'synthetic_provider':provider.settings.model_dump(mode='json'),
            'figures':[str(p) for p in figures],'evidence':evidence}
    (run_dir/'offline_validation.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
