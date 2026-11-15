"""Portable offline checks for the pre-results report; no Office or inference."""
import csv
import importlib.util
import io
import json
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("btl_report_builder", ROOT / "scripts/build_report.py")
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


@pytest.fixture
def pre_results_root(tmp_path):
    """A pre-results project fixture remains valid after real smoke is recorded.

    Production state checks stay enabled: empirical repositories must still
    reject generation of a manuscript claiming that no inference occurred.
    """
    root = tmp_path / "pre_results_fixture"
    paths = {
        "report/official_template.docx", "report/manuscript.md", "report/artifact.md",
        "scripts/build_report.py", "research/protocol.md", "research/amendments.md",
        "research/checks/source_verification.json", "research/oracle_derivation.md",
        "evaluation/oracle_table.csv", "configs/free.yaml",
        "research/checks/report_preparation_sources.json", "research/audit.md",
        "README.md", "research/decisions.md", "scripts/validate_offline.py",
        "src/beyond_label/analyze.py", "src/beyond_label/evidence.py",
        "prompts/agent_system.txt", "prompts/probe_readback.txt",
    }
    for name in paths:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    (root / "research/milestones.json").write_text(json.dumps({
        "experimental_calls": 0, "execution_freeze": None,
        "classification": "synthetic_pre_results_project_fixture",
        "authors": {"names": ["Tonmoy", "Araf"]},
    }), encoding="utf-8")
    return root


def test_build_is_deterministic_and_preserves_official_package(tmp_path, pre_results_root):
    template = (pre_results_root / "report/official_template.docx").read_bytes()
    first = report.build_report(root=pre_results_root, output_dir=tmp_path / "first")
    second = report.build_report(root=pre_results_root, output_dir=tmp_path / "second")
    assert first == second
    for name in ("pre_results.docx", "claim_to_evidence.csv", "report_manifest.json"):
        assert (tmp_path / "first" / name).read_bytes() == (tmp_path / "second" / name).read_bytes()
    assert template == (pre_results_root / "report/official_template.docx").read_bytes()
    with ZipFile(io.BytesIO(template)) as original, ZipFile(tmp_path / "first/pre_results.docx") as generated:
        assert original.namelist() == generated.namelist()
        for name in original.namelist():
            if name not in report.EDITABLE_PARTS:
                assert original.read(name) == generated.read(name)
        old_section = ET.fromstring(original.read("word/document.xml")).find("w:body/w:sectPr", report.NS)
        new_root = ET.fromstring(generated.read("word/document.xml"))
        for cell in new_root.iter(report.tag("tc")):
            assert list(cell)[-1].tag == report.tag("p"), "Word requires a final paragraph after a nested table"
        new_section = new_root.find("w:body/w:sectPr", report.NS)
        assert ET.tostring(old_section) == ET.tostring(new_section)
        text = report.text_of(new_root)
        for unwanted in ("PROJECT TITLE", "Author name 1", "How to use this template", "WithApart Research"):
            assert unwanted not in text
        for heading in report.REQUIRED_HEADINGS:
            assert heading in text
        assert "Tonmoy" in text and "Araf" in text and "Affiliation pending" in text
        assert "No empirical results are available." in text
        assert "Research conducted at" not in report.text_of(ET.fromstring(generated.read("word/footnotes.xml")))
    assert 150 <= first["abstract_word_count"] <= 250
    assert first["empirical_observations"] == 0
    assert first["execution_freeze"] is None
    assert first["human_review_verified"] is first["submission_ready"] is False
    assert first["render_verification"]["status"] == "pending"


def test_claim_map_cannot_be_mistaken_for_empirical_scores(tmp_path, pre_results_root):
    report.build_report(root=pre_results_root, output_dir=tmp_path / "out")
    with (tmp_path / "out/claim_to_evidence.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows and len({row["claim_id"] for row in rows}) == len(rows)
    classes = {row["classification"] for row in rows}
    assert {"analytic_reference_not_observation", "pending_empirical_result", "verified_external_citation"} <= classes
    for row in rows:
        assert row["empirical_evidence"] == row["human_review_claimed"] == "false"
        for name, expected in json.loads(row["source_sha256"]).items():
            assert report.sha((pre_results_root / name).read_bytes()) == expected


def test_template_change_requires_new_distillation(tmp_path, monkeypatch, pre_results_root):
    monkeypatch.setattr(report, "TEMPLATE_SHA256", "unverified")
    with pytest.raises(ValueError, match="template hash mismatch"):
        report.build_report(root=pre_results_root, output_dir=tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_completed_smoke_blocks_pre_results_regeneration(pre_results_root, tmp_path):
    state_path = pre_results_root / "research/milestones.json"
    state = json.loads(state_path.read_text("utf-8"))
    state["experimental_calls"] = 1
    state_path.write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(ValueError, match="pre-results state"):
        report.build_report(root=pre_results_root, output_dir=tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("old,new", [
    ("No empirical results are available.", "Results were observed."),
    ("No execution freeze currently exists.", "Frozen."),
    ("**Tonmoy; Araf**", "**Unconfirmed Author**"),
    ("<!-- BTL_EMPIRICAL_RESULTS_START -->", ""),
])
def test_pre_results_contract_rejects_unsupported_claim_changes(old, new):
    text = (ROOT / "report/manuscript.md").read_text("utf-8").replace(old, new)
    with pytest.raises(ValueError):
        report.manuscript_contract(text, report.parse_manuscript(text))


def test_report_preserves_verbatim_prompt_blocks():
    blocks = report.parse_manuscript((ROOT / "report/manuscript.md").read_text("utf-8"))
    code = [b["text"] for b in blocks if b["kind"] == "code"]
    assert (ROOT / "prompts/agent_system.txt").read_text("utf-8").strip() in code
    assert (ROOT / "prompts/probe_readback.txt").read_text("utf-8").strip() in code


def test_references_stay_separate_readable_records():
    blocks = report.parse_manuscript((ROOT / "report/manuscript.md").read_text("utf-8"))
    index = next(i for i, b in enumerate(blocks) if b.get("text") == "References")
    assert [b['text'].split()[0] for b in blocks[index + 1:index + 4]] == ['1.', '2.', '3.']


@pytest.mark.parametrize("state", [
    {"experimental_calls": 1, "execution_freeze": None},
    {"experimental_calls": 0, "execution_freeze": {"tag": "fixture-freeze"}},
    {"experimental_calls": False, "execution_freeze": None},
    {"execution_freeze": None},
    {"experimental_calls": 0},
])
def test_pre_results_builder_rejects_stale_or_unknown_project_state(tmp_path, state):
    (tmp_path / "research").mkdir()
    (tmp_path / "research/milestones.json").write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(ValueError, match="pre-results state"):
        report.build_report(root=tmp_path, output_dir=tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("manifest", [
    {"run_config": {"evidence_kind": "empirical"}},
    {"run_config": {"evidence_kind": "unknown"}},
    {},
    "malformed-json",
])
def test_pre_results_rejects_empirical_or_unclassified_runs(tmp_path, manifest):
    (tmp_path / "research").mkdir()
    (tmp_path / "research/milestones.json").write_text(
        json.dumps({"experimental_calls": 0, "execution_freeze": None}), encoding="utf-8")
    target = tmp_path / "runs/fixture/manifest.json"
    target.parent.mkdir(parents=True)
    target.write_text(manifest if isinstance(manifest, str) else json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="pre-results state"):
        report.build_report(root=tmp_path, output_dir=tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_claim_sources_match_prompts_authors_amendment_and_absence():
    blocks = report.parse_manuscript((ROOT / "report/manuscript.md").read_text("utf-8"))
    rows = report.evidence_rows(blocks, ROOT)
    for path in ("prompts/agent_system.txt", "prompts/probe_readback.txt"):
        text = (ROOT / path).read_text("utf-8").strip()
        row = next(row for row in rows if row["claim_text"] == text)
        assert path in json.loads(row["source_files"])
        assert row["classification"] == "verbatim_prompt_not_observation"
    authors = next(row for row in rows if "Tonmoy; Araf" in row["claim_text"])
    assert "research/milestones.json" in json.loads(authors["source_files"])
    amendment = next(row for row in rows if row["location"].startswith("3.3") and "A1" in row["claim_text"])
    assert "research/amendments.md" in json.loads(amendment["source_files"])
    for row in rows:
        if "No execution freeze currently exists." in row["claim_text"] or "No real smoke" in row["claim_text"]:
            assert "research/milestones.json" in json.loads(row["source_files"])


def test_pre_results_rejects_orphan_run_journal(tmp_path):
    (tmp_path / "research").mkdir()
    (tmp_path / "research/milestones.json").write_text(
        json.dumps({"experimental_calls": 0, "execution_freeze": None}), encoding="utf-8")
    journal = tmp_path / "runs/orphan/calls.jsonl"
    journal.parent.mkdir(parents=True)
    journal.write_text('{}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="pre-results state"):
        report.build_report(root=tmp_path, output_dir=tmp_path / "out")
