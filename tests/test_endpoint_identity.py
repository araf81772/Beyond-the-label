"""Offline identity repair: synthetic responses and read-only retained replay.

The retained-response check is engineering replay, not a new observation or
retroactive acceptance of the terminal empirical cell. No files are rewritten.
"""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from beyond_label.generate import generate_world, make_case
from beyond_label.paid_profile import get_paid_profile
from beyond_label.provider import ProviderFailure, ProviderSettings, parse_response, serialize_request
from beyond_label.render import readback_request


MODEL = "deepseek/deepseek-v4.1-flash-1017"
ENDPOINT = "deepseek/deepseek-v4.1-flash-20261017"


def settings(mapped=True, **changes):
    p = get_paid_profile(MODEL)
    values = dict(model=MODEL, provider="PrimeIntellect", provider_route="primeintellect",
        provider_identity_source="openrouter_metadata", require_parameters=True,
        reasoning={"effort": "none"}, temperature=0, max_output_tokens=512,
        max_price=p["max_price"], accepted_endpoint_models=(ENDPOINT,) if mapped else ())
    values.update(changes)
    return ProviderSettings(**values)


def response():
    return {"model": MODEL, "provider": "PrimeIntellect", "id": "synthetic-endpoint-mapping",
        "choices": [{"message": {"content": "synthetic readback"}, "finish_reason": "stop"}],
        "usage": {"cost": .0001, "is_byok": False},
        "openrouter_metadata": {"requested": MODEL, "endpoints": {"available": [
            {"model": ENDPOINT, "provider": "PrimeIntellect", "selected": True}]}}}


def request_payload(configured):
    return serialize_request(readback_request(make_case(generate_world(1100))), configured)


def test_endpoint_mapping_changes_validation_only_not_wire_or_raw_identity():
    old, repaired = settings(False), settings()
    original_payload = request_payload(old)
    assert request_payload(repaired) == original_payload
    assert "accepted_endpoint_models" not in original_payload
    raw = response()
    before = deepcopy(raw)
    with pytest.raises(ProviderFailure, match="model_mismatch"):
        parse_response(raw, original_payload, old)
    result = parse_response(raw, original_payload, repaired)
    assert result.returned_model == MODEL
    assert result.raw_response["openrouter_metadata"]["endpoints"]["available"][0]["model"] == ENDPOINT
    assert raw == before


def test_endpoint_mapping_never_allows_the_alias_as_top_level_response_model():
    configured = settings()
    raw = response()
    raw["model"] = ENDPOINT
    with pytest.raises(ProviderFailure, match="model_mismatch"):
        parse_response(raw, request_payload(configured), configured)


@pytest.mark.parametrize("change", [
    {"model": "deepseek/deepseek-v4.1-flash"},
    {"provider": "DeepSeek"}, {"provider_route": "deepseek"},
    {"provider_identity_source": "provider"}, {"require_parameters": False},
    {"free_only": True}, {"reasoning": None}, {"reasoning": {"effort": "high"}},
    {"temperature": .1}, {"max_output_tokens": 513}, {"max_price": None},
    {"max_price": {"prompt": .4, "completion": 1.6, "request": 0, "image": 0}},
    {"accepted_endpoint_models": ("arbitrary/model",)},
    {"accepted_endpoint_models": (ENDPOINT, ENDPOINT)},
    {"accepted_endpoint_models": (ENDPOINT, "another/model")},
])
def test_mapping_requires_exact_documented_profile_and_settings(change):
    with pytest.raises(ProviderFailure):
        request_payload(settings(**change))


@pytest.mark.parametrize("field,value,reason", [
    ("model", "deepseek/deepseek-v4.1-flash-20260910", "model_mismatch"),
    ("model", ENDPOINT + ":free", "model_mismatch"),
    ("provider", "DeepSeek", "provider_mismatch"),
    ("selected", False, "protocol_invalid_provider_metadata"),
    ("selected", "true", "protocol_invalid_provider_metadata"),
])
def test_mapped_endpoint_still_rejects_wrong_or_ambiguous_metadata(field, value, reason):
    configured = settings()
    raw = response()
    raw["openrouter_metadata"]["endpoints"]["available"][0][field] = value
    with pytest.raises(ProviderFailure, match=reason):
        parse_response(raw, request_payload(configured), configured)


def test_default_absent_mapping_preserves_historical_rejection():
    values = settings(False).model_dump()
    values.pop("accepted_endpoint_models")
    historical = ProviderSettings(**values)
    assert historical.accepted_endpoint_models == ()
    with pytest.raises(ProviderFailure, match="model_mismatch"):
        parse_response(response(), request_payload(historical), historical)


def test_retained_response_replay_preserves_terminal_classification_and_all_files():
    root = Path(__file__).resolve().parents[1]
    directory = root / "runs/paid_smoke_gpt41mini_20261115/segments/deepseek_primeintellect_v2"
    names = ("manifest.json", "calls.jsonl", "scores.csv", "usage.csv", "analysis_manifest.json")
    before = {name: (directory / name).read_bytes() for name in names}
    manifest = json.loads(before["manifest.json"])
    events = [json.loads(line) for line in before["calls.jsonl"].splitlines()]
    failed = next(event for event in events if event["event"] == "attempt_failed")
    assert failed["reason"] == "model_mismatch" and failed["retryable"] is False
    old = ProviderSettings(**manifest["run_config"]["provider_settings"])
    assert old.accepted_endpoint_models == ()
    with pytest.raises(ProviderFailure, match="model_mismatch"):
        parse_response(failed["raw_response"], failed["payload"], old)
    repaired = old.model_copy(update={"accepted_endpoint_models": (ENDPOINT,)})
    replayed = parse_response(failed["raw_response"], failed["payload"], repaired)
    assert replayed.returned_model == MODEL and replayed.returned_provider == "PrimeIntellect"
    assert events[-1]["event"] == "cell_completed" and events[-1]["first_missing_reason"] == "model_mismatch"
    assert {name: (directory / name).read_bytes() for name in names} == before
