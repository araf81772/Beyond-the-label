import csv
import pytest

from beyond_label.analyze import analyze_rows
from beyond_label.figures import allocation_table, figures_for_run, write_figures
from test_analysis import fixture_run, write_fixture_run


def test_allocation_includes_planned_missing_and_analytic_reference():
    manifest, rows = fixture_run(seeds=(2000,))
    rows = [row for row in rows if row["cell_id"] != "2000-separate-a-MAIN"]
    result = analyze_rows(rows, manifest, allow_synthetic=True)
    table = allocation_table(result)
    main = {row["action"]: row for row in table if row["condition"] == "MAIN"}
    assert main["MISSING"]["agent_count"] == 1
    assert main["MISSING"]["agent_fraction"] == .25
    assert main["INSPECT_1"]["oracle_reference_count"] == 2
    assert main["INSPECT_2"]["oracle_reference_count"] == 2
    assert sum(row["agent_count"] for row in main.values()) == 4


def test_synthetic_figures_guard_and_png_artifacts(tmp_path):
    manifest, rows = fixture_run(seeds=(2000, 2001))
    result = analyze_rows(rows, manifest, allow_synthetic=True)
    with pytest.raises(ValueError, match="Synthetic"):
        write_figures(result, tmp_path)
    outputs = write_figures(result, tmp_path, allow_synthetic=True)
    assert len(outputs) == 3
    for path in outputs:
        raw = path.read_bytes()
        assert len(raw) > 500
        assert b"SYNTHETIC" in raw
        if path.suffix == ".png":
            assert raw.startswith(b"\x89PNG\r\n\x1a\n")
    with (tmp_path / "allocation.csv").open(encoding="utf-8", newline="") as stream:
        table = list(csv.DictReader(stream))
        assert len(table) == 15
        assert all(row["oracle_evidence_kind"] == "analytic_reference_not_observation" for row in table)


def test_run_figure_regeneration_uses_saved_scores(tmp_path):
    manifest, rows = fixture_run(seeds=(2000,))
    write_fixture_run(tmp_path, manifest, rows)
    outputs = figures_for_run(tmp_path, allow_synthetic=True)
    assert all(path.is_file() for path in outputs)
    first = {path.name: path.read_bytes() for path in outputs}
    outputs = figures_for_run(tmp_path, allow_synthetic=True)
    assert {path.name: path.read_bytes() for path in outputs} == first
