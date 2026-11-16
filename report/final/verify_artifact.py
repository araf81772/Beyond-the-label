"""Read-only final-paper verification. Run with bundled document Python/pypdf."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    manifest = json.loads((HERE / "build_manifest.json").read_text())
    assert manifest["classification"] == "empirical_final_paper"
    for key, path in [("docx_sha256", "beyond_the_label.docx"),
                      ("manuscript_sha256", "manuscript.md"),
                      ("metadata_sha256", "author_metadata.json"),
                      ("builder_sha256", "build_submission.py"),
                      ("figure_sha256", "figures/allocation.png")]:
        assert manifest[key] == sha(HERE / path), key
    freeze_counts = {}
    for name in ["execution_freeze.json", "main_continuation_operational_freeze.json"]:
        data = json.loads((ROOT / "research" / name).read_text())
        for path, digest in data["input_hashes"].items():
            assert sha(ROOT / path) == digest, path
        freeze_counts[name] = len(data["input_hashes"])
    with ZipFile(ROOT / "report/official_template.docx") as z, ZipFile(HERE / "beyond_the_label.docx") as out:
        for name in manifest["template_parts_preserved"]:
            assert z.read(name) == out.read(name), name
        xml = ET.fromstring(out.read("word/document.xml"))
    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    doc_text = "\n".join(t.text or "" for t in xml.iter(w+"t"))
    spec = importlib.util.spec_from_file_location("builder", HERE / "build_submission.py")
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    metadata = json.loads((HERE / "author_metadata.json").read_text())
    source = (HERE / "manuscript.md").read_text(encoding="utf8").replace("[[PRIOR_WORK_DISCLOSURE]]", metadata["prior_work_disclosure"])
    blocks = builder.helper.parse_manuscript(source)
    content_checks = 0
    for block in blocks:
        if block["kind"] == "table":
            values = [v for row in block["rows"] for v in row]
        else:
            values = [block["text"]]
        for value in values:
            if value in {"[[FIGURE1]]", "Tonmoy Sarker, Araf Akhter and Abidur Rahaman"}:
                continue
            assert value in doc_text, value[:90]
            content_checks += 1
    pdf = HERE / "beyond_the_label.pdf"
    reader = PdfReader(pdf)
    pages = [p.extract_text() for p in reader.pages]
    reference_page = next(i+1 for i,p in enumerate(pages) if p.lstrip().startswith("References"))
    assert reference_page-1 <= 8
    assert len(pages) == 11
    assert pdf.stat().st_size <= 25_000_000
    full = "\n".join(pages)
    for forbidden in ["[[", "Affiliation to confirm", "PROJECT TITLE", "Summarize your project", "Author name 1"]:
        assert forbidden not in full, forbidden
    for author in metadata["authors"]:
        assert author["name"] in full
        assert author["affiliation"] in full
    assert "Limitations and Dual-Use / Ethical Considerations" in full
    assert "LLM Usage Statement" in full
    assert "no preexisting code" in full.lower()
    claims = subprocess.run([sys.executable, str(HERE / "verify_claims.py")], capture_output=True, text=True, check=True)
    claim_result = json.loads(claims.stdout)
    visual = json.loads((ROOT / "evaluation/final_paper_qa/v2/visual_verification.json").read_text())
    assert visual["docx_sha256"] == sha(HERE / "beyond_the_label.docx")
    assert visual["pdf_sha256"] == sha(pdf)
    assert visual["all_pages_visually_reviewed_by_AI"] is True
    for name, digest in visual["page_png_sha256"].items():
        assert sha(ROOT / "evaluation/final_paper_qa/v2" / name) == digest
    print(json.dumps({"status": "passed", "scope": "AI artifact verification, not human approval or submission",
          "frozen_input_counts": freeze_counts, "docx_text_checks": content_checks,
          "template_preserved_parts": len(manifest["template_parts_preserved"]),
          "pdf_sha256": sha(pdf), "docx_sha256": sha(HERE / "beyond_the_label.docx"),
          "pdf_bytes": pdf.stat().st_size, "total_pages": len(pages), "body_pages": reference_page-1,
          "abstract_words": manifest["abstract_word_count"], "claims": claim_result,
          "all_pages_visually_reviewed_by_AI": True, "human_final_approval_claimed": False}, indent=2))

if __name__ == "__main__":
    main()
