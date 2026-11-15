"""Frozen analysis settings cannot be changed by the empirical CLI/API."""
import pytest

from beyond_label import run
from beyond_label.analyze import analyze_run
from test_free_run import free_fixture


@pytest.mark.parametrize("seed,resamples", [(1, 10000), (314159, 9999), (True, 10000), (314159, 10000.0)])
def test_empirical_fixture_rejects_nonfrozen_analysis_before_writing(tmp_path, monkeypatch, seed, resamples):
    config, _, provider = free_fixture()
    monkeypatch.setattr(run, "_validate_live_transport", lambda _: None)
    run.run_manifest(run.build_manifest("smoke"), tmp_path, provider,
                     execution_config=config, synthetic=False, max_cells=1)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    with pytest.raises(ValueError, match="frozen bootstrap seed"):
        analyze_run(tmp_path, bootstrap_seed=seed, n_resamples=resamples)
    assert not (tmp_path / "analysis").exists()
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}


def test_synthetic_fixture_retains_explicit_sensitivity_settings(tmp_path):
    policy = run.ScriptedPublicPolicy()
    from beyond_label.provider import PinnedProvider, ProviderSettings
    provider = PinnedProvider(ProviderSettings(model=policy.model, provider=policy.provider), policy)
    run.run_manifest(run.build_manifest("smoke"), tmp_path, provider, max_cells=1)
    result = analyze_run(tmp_path, allow_synthetic=True, bootstrap_seed=7, n_resamples=19)
    assert result["primary"]["estimate"]["bootstrap_seed"] == 7
    assert result["primary"]["estimate"]["bootstrap_resamples"] == 19
