from collections import Counter
import copy

import pytest

from beyond_label.run import build_manifest, case_for_cell, run_manifest, ScriptedPublicPolicy
from beyond_label.provider import PinnedProvider, ProviderSettings


@pytest.mark.parametrize("dataset,count,continuations,total", [("main", 704, 448, 1152), ("pilot", 160, 128, 288), ("smoke", 80, 64, 144)])
@pytest.mark.parametrize("load", [2, 8])
def test_complete_manifest_counts(dataset, count, continuations, total, load):
    manifest = build_manifest(dataset, load)
    assert len(manifest["cells"]) == manifest["initial_calls"] == count
    assert manifest["maximum_continuations"] == continuations
    assert manifest["maximum_planned_calls"] == total
    assert len({cell["cell_id"] for cell in manifest["cells"]}) == count
    assert manifest["classification"] == "planned_not_frozen"
    assert manifest["approved_for_execution"] is False


def test_main_exact_factors_and_control_subset():
    manifest = build_manifest()
    assert manifest["seeds"] == list(range(2000, 2064))
    assert manifest["counts"] == {"MAIN": 256, "READBACK": 256, "HIGH-FEE": 64, "HIGH-STAKES": 64, "MASKED": 32, "NUMERIC": 32}
    for cell in manifest["cells"]:
        if cell["condition"] != "MAIN":
            assert 2000 <= cell["world_seed"] <= 2015
        if cell["condition"] == "NUMERIC":
            assert cell["layout"] == "separate"
        if cell["condition"] == "MASKED":
            assert cell["twin"] is None
    counts = Counter((c["world_seed"], c["purpose"]) for c in manifest["cells"] if c["condition"] == "MAIN")
    assert set(counts.values()) == {4}


def test_schedule_is_reproducible_and_seed_changes_only_order():
    first = build_manifest(schedule_seed=271828)
    second = build_manifest(schedule_seed=314159)
    assert first == build_manifest(schedule_seed=271828)
    assert first["cells"] != second["cells"]
    assert sorted(first["cells"], key=lambda c: c["cell_id"]) == sorted(second["cells"], key=lambda c: c["cell_id"])
    assert any(first["cells"][i]["world_seed"] != first["cells"][i + 1]["world_seed"] for i in range(len(first["cells"]) - 1))


@pytest.mark.parametrize("dataset", ["main", "pilot", "smoke"])
def test_masked_latent_scope_balanced_without_extra_twin_cells(dataset):
    manifest = build_manifest(dataset)
    counts = Counter(case_for_cell(c, manifest).twin for c in manifest["cells"] if c["condition"] == "MASKED")
    assert counts["a"] == counts["b"]
    for cell in manifest["cells"]:
        if cell["condition"] == "MASKED":
            case = case_for_cell(cell, manifest)
            assert [r.tested_configuration for r in case.public.records[:2]] == ["[withheld]", "[withheld]"]


def test_missing_or_duplicate_manifest_cell_is_rejected_before_calls(tmp_path):
    fixture = ScriptedPublicPolicy()
    provider = PinnedProvider(ProviderSettings(model=fixture.model, provider=fixture.provider), fixture)
    for mutate in (lambda cells: cells.pop(), lambda cells: cells.append(cells[0])):
        manifest = copy.deepcopy(build_manifest("smoke"))
        mutate(manifest["cells"])
        with pytest.raises(ValueError, match="complete deterministic design"):
            run_manifest(manifest, tmp_path, provider)
    assert fixture.calls == 0


def test_live_execution_is_disabled_before_any_side_effect(tmp_path):
    fixture = ScriptedPublicPolicy()
    provider = PinnedProvider(ProviderSettings(model=fixture.model, provider=fixture.provider), fixture)
    target = tmp_path / "live"
    with pytest.raises(ValueError, match="Live execution is disabled"):
        run_manifest(build_manifest(), target, provider, synthetic=False)
    assert not target.exists() and fixture.calls == 0
