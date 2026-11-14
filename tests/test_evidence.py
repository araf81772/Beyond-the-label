import csv
import json
import pytest
from beyond_label.evidence import export_evidence
from beyond_label.provider import PinnedProvider, ProviderSettings
from beyond_label.run import ScriptedPublicPolicy, build_manifest, run_manifest


def test_evidence_maps_numeric_values_to_trace_derived_analysis(tmp_path):
    fixture=ScriptedPublicPolicy()
    provider=PinnedProvider(ProviderSettings(model=fixture.model,provider=fixture.provider),fixture)
    run_manifest(build_manifest('smoke'),tmp_path,provider)
    with pytest.raises(ValueError,match='Synthetic'):
        export_evidence(tmp_path)
    result=export_evidence(tmp_path,allow_synthetic=True)
    assert 'SYNTHETIC' in result['artifact_label']
    worked=json.loads((tmp_path/'analysis/matched_trace.json').read_text('utf-8'))
    assert worked['world_seed']==1100
    assert len(worked['twins'])==2 and worked['human_review'] is False
    analysis=json.loads((tmp_path/'analysis/analysis.json').read_text('utf-8'))
    with (tmp_path/'analysis/claim_evidence.csv').open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
    assert rows and all('SYNTHETIC' in row['artifact_label'] for row in rows)
    references=[row for row in rows if row['json_pointer'].endswith('/oracle_reference_D')]
    assert references and all(row['evidence_kind']=='analytic_reference_not_observation' for row in references)
    assert all(row['evidence_kind']=='design_or_configuration_metadata' for row in rows if row['json_pointer'].endswith('/bootstrap_seed'))
    for row in rows:
        value=analysis
        for token in row['json_pointer'].split('/')[1:]:
            token=token.replace('~1','/').replace('~0','~')
            value=value[int(token)] if isinstance(value,list) else value[token]
        assert float(row['value'])==value
        assert len(row['raw_trace_sha256'])==64
