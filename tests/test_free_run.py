"""Free execution plumbing exercised only with explicitly synthetic fixtures."""
import json
import pytest

from beyond_label.provider import PinnedProvider, ProviderSettings
from beyond_label.run import ScriptedPublicPolicy, build_manifest, rebuild_outputs, run_manifest


def free_config():
    return dict(live_execution_enabled=True, free_only=True, paid_calls_authorized=False,
        authorized_spend_cap=0, maximum_inference_attempts=10, currency="USD", routing_service="OpenRouter",
        model="vendor/fixed:free", provider="Vendor", provider_route="vendor",
        provider_identity_source="openrouter_metadata", require_parameters=True,
        temperature=0, temperature_setting_verified=True, reasoning={"enabled": False},
        reasoning_mode="configured", reasoning_setting_verified=True, max_output_tokens=512,
        concurrency=1, parallel_tool_calls=False, allow_fallbacks=False, provider_docs_verified=True,
        provider_requests_per_minute=20, provider_request_limit_verified=True,
        operator_requests_per_minute=10, operator_tokens_per_minute=100000,
        provider_tokens_per_minute=None, provider_token_limit_status="not_published",
        key_hard_limit_usd=0, key_hard_limit_verified=True, load=2, schedule_seed=271828)


def free_fixture():
    config = free_config()
    settings = ProviderSettings(**{key: config[key] for key in
        ("model", "provider", "provider_route", "provider_identity_source", "require_parameters",
         "free_only", "temperature", "reasoning", "max_output_tokens")})
    policy = ScriptedPublicPolicy(settings.model, settings.provider)
    def transport(payload):
        raw = policy(payload)
        raw["openrouter_metadata"] = {"endpoints": {"available": [
            {"model": settings.model, "provider": settings.provider, "selected": True}]}}
        return raw
    return config, policy, PinnedProvider(settings, transport)


def test_free_execution_contract_rehearsal_stays_synthetic_and_resumes(tmp_path):
    config, policy, provider = free_fixture()
    plan = build_manifest("smoke")
    first = run_manifest(plan, tmp_path, provider, execution_config=config, max_cells=2)
    assert first["evidence_kind"] == "synthetic" and first["empirical_observations"] == 0
    assert first["completed_cells"] == 2
    assert rebuild_outputs(tmp_path) == first
    count = policy.calls
    run_manifest(plan, tmp_path, provider, execution_config=config, max_cells=0)
    assert policy.calls == count


def test_injected_fixture_cannot_be_declared_real(tmp_path):
    config, policy, provider = free_fixture()
    with pytest.raises(ValueError, match="fixtures remain synthetic"):
        run_manifest(build_manifest("smoke"), tmp_path / "absent", provider,
                     synthetic=False, execution_config=config)
    assert policy.calls == 0 and not (tmp_path / "absent").exists()


def test_execution_config_provider_mismatch_precedes_artifact_creation(tmp_path):
    config, policy, provider = free_fixture()
    config["provider"] = "Different"
    with pytest.raises(ValueError, match="differ from pinned"):
        run_manifest(build_manifest("smoke"), tmp_path / "absent", provider, execution_config=config)
    assert policy.calls == 0 and not (tmp_path / "absent").exists()


def test_relabeling_synthetic_artifacts_does_not_establish_empirical_provenance(tmp_path):
    config, _, provider = free_fixture()
    run_manifest(build_manifest("smoke"), tmp_path, provider, execution_config=config, max_cells=1)
    path = tmp_path / "manifest.json"
    stored = json.loads(path.read_text("utf-8"))
    stored["run_config"]["evidence_kind"] = "empirical"
    from beyond_label.run import _hash
    stored["run_config_hash"] = _hash({"plan": stored["plan"], "config": stored["run_config"]})
    path.write_text(json.dumps(stored), encoding="utf-8")
    with pytest.raises(ValueError, match="Empirical transport provenance"):
        rebuild_outputs(tmp_path)


def test_mocked_empirical_reporting_counts_unmatched_start_as_unknown(tmp_path, monkeypatch):
    # Explicit test-only seam: no HTTP occurs; temporary artifacts test reporting
    # semantics and are never included in research results.
    from beyond_label import run
    config, policy, provider = free_fixture()
    monkeypatch.setattr(run, "_validate_live_transport", lambda _: None)
    def interrupted(payload):
        raise KeyboardInterrupt
    provider.transport = interrupted
    with pytest.raises(KeyboardInterrupt):
        run_manifest(build_manifest("smoke"), tmp_path, provider, execution_config=config,
                     synthetic=False, max_cells=1)
    summary = json.loads((tmp_path / "analysis_manifest.json").read_text("utf-8"))
    assert summary["spend_evidence_complete"] is False
    assert summary["unknown_cost_attempts"] == 1
    assert summary["experimental_provider_spend"] is None
    assert summary["known_provider_spend_usd"] == 0
    import csv
    with (tmp_path / "usage.csv").open(encoding="utf-8",newline="") as stream:
        usage = list(csv.DictReader(stream))
    assert len(usage) == 1 and usage[0]["cost_usd"] == ""
    assert usage[0]["error"] == "ambiguous_infrastructure_attempt"
    assert policy.calls == 0


def test_overriding_http_adapter_subclass_cannot_claim_real_origin(tmp_path):
    from beyond_label.openrouter import OpenRouterFreeTransport
    from beyond_label.controls import GuardedTransport, AttemptBound
    from beyond_label.budget import BudgetLedger
    from beyond_label.rate_limit import RateLimiter
    from beyond_label.run import _validate_live_transport
    config, _, provider = free_fixture()
    class FixtureTransport(OpenRouterFreeTransport):
        def __call__(self, payload):
            raise AssertionError("Test fixture must never dispatch")
    provider.transport = GuardedTransport(FixtureTransport(config["model"],config["provider_route"]),
        BudgetLedger(tmp_path / "budget.jsonl","0"), RateLimiter(10,10000),lambda p:AttemptBound("0",100))
    with pytest.raises(ValueError, match="fixtures remain synthetic"):
        _validate_live_transport(provider)
