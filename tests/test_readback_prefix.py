import json

import pytest

from beyond_label.render import decision_request, prompt_text, readback_request
from beyond_label.run import Journal, ScriptedPublicPolicy, build_manifest, case_for_cell, run_manifest
from beyond_label.provider import PinnedProvider, ProviderSettings, serialize_request


@pytest.mark.parametrize("load", [2, 8])
def test_exact_decision_prefix_and_absent_probe_for_all_main_readbacks(load):
    manifest = build_manifest("main", load)
    settings = ProviderSettings(model="fixture", provider="fixture")
    probe = prompt_text("probe_readback.txt")
    for cell in manifest["cells"]:
        if cell["purpose"] != "readback":
            continue
        case = case_for_cell(cell, manifest)
        decision = decision_request(case)
        readback = readback_request(case)
        d_payload, r_payload = serialize_request(decision, settings), serialize_request(readback, settings)
        assert d_payload["messages"] == r_payload["messages"][:4]
        assert probe not in json.dumps(d_payload, ensure_ascii=False)
        assert r_payload["messages"][4] == {"role": "user", "content": probe}
        assert "tools" not in r_payload and len(d_payload["tools"]) == 2
        assert decision.messages is not readback.messages


def test_probe_never_enters_stored_decision_trace(tmp_path):
    fixture = ScriptedPublicPolicy()
    provider = PinnedProvider(ProviderSettings(model=fixture.model, provider=fixture.provider), fixture)
    manifest = build_manifest("smoke")
    run_manifest(manifest, tmp_path, provider)
    purposes = {cell["cell_id"]: cell["purpose"] for cell in manifest["cells"]}
    probe = prompt_text("probe_readback.txt")
    for event in Journal(tmp_path / "calls.jsonl").events:
        if purposes[event["cell_id"]] == "decision":
            assert probe not in json.dumps(event, ensure_ascii=False)
