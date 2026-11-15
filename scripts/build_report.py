"""Build the pre-results DOCX by patching the retained official template.

Standard-library only. No network, provider imports, credentials, Office calls,
or empirically inferred values. Rendering is a separate, explicitly recorded QA
step; a successful build never certifies visual quality or empirical completion.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_SHA256 = "21ebc0bcea8f9760c64c9c0eb163bbaaab0a34465722f86e4e3feecf6849de59"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
EDITABLE_PARTS = {"word/document.xml", "word/footnotes.xml"}
REQUIRED_HEADINGS = ("1. Introduction", "2. Related work", "3. Methods", "4. Results: NOT RUN",
                     "5. Discussion and Limitations", "6. Conclusion", "Code and Data", "References",
                     "Appendix A. Limitations and Dual-Use / Ethical Considerations", "LLM Usage Statement")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tag(name: str) -> str:
    return f"{{{W}}}{name}"


def text_of(node: ET.Element) -> str:
    return "".join(t.text or "" for t in node.iter(tag("t")))


def plain(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    return text.replace("**", "").replace("`", "").replace("*", "")


def parse_manuscript(text: str) -> list[dict]:
    blocks, paragraph, lines = [], [], text.splitlines()

    def flush():
        if paragraph:
            blocks.append({"kind": "paragraph", "text": plain(" ".join(paragraph))})
            paragraph.clear()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("<!--"):
            flush()
        elif line.startswith("```"):
            flush()
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            if i == len(lines):
                raise ValueError("Unclosed manuscript code block")
            blocks.append({"kind": "code", "text": "\n".join(code)})
        elif line.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                row = [plain(x.strip()) for x in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", x) for x in row):
                    rows.append(row)
                i += 1
            if not rows or any(len(row) != len(rows[0]) for row in rows):
                raise ValueError("Malformed manuscript table")
            blocks.append({"kind": "table", "rows": rows})
            i -= 1
        elif line.startswith("#"):
            flush()
            match = re.fullmatch(r"(#{1,3})\s+(.+)", line)
            if not match:
                raise ValueError("Unsupported manuscript heading")
            blocks.append({"kind": "heading", "level": len(match[1]), "text": plain(match[2])})
        elif line.startswith("- "):
            flush()
            blocks.append({"kind": "bullet", "text": plain(line[2:])})
        elif re.match(r"^\d+\.\s", line):
            flush()
            blocks.append({"kind": "paragraph", "text": plain(line)})
        elif not line:
            flush()
        else:
            paragraph.append(line.strip())
        i += 1
    flush()
    return blocks


def manuscript_contract(text: str, blocks: list[dict]) -> dict:
    headings = [b["text"] for b in blocks if b["kind"] == "heading"]
    if any(h not in headings for h in REQUIRED_HEADINGS):
        raise ValueError("Required report section missing")
    if "**Tonmoy; Araf**" not in text or "Affiliations: pending confirmation" not in text:
        raise ValueError("Confirmed author/pending affiliation contract changed")
    abstract_index = next(i for i, b in enumerate(blocks) if b.get("text") == "Abstract")
    abstract = blocks[abstract_index + 1]
    if abstract["kind"] != "paragraph" or not 150 <= len(abstract["text"].split()) <= 250:
        raise ValueError("Abstract must contain 150-250 words")
    if "No empirical results are available." not in text or "No execution freeze currently exists." not in text:
        raise ValueError("This builder requires an explicitly pre-results manuscript")
    if text.count("<!-- BTL_EMPIRICAL_RESULTS_START -->") != 1 or text.count("<!-- BTL_EMPIRICAL_RESULTS_END -->") != 1:
        raise ValueError("Results provenance markers missing or duplicated")
    return {"abstract_index": abstract_index, "abstract": abstract["text"],
            "abstract_word_count": len(abstract["text"].split()),
            "body_word_count_including_tables_and_frontmatter": len(text.split("## References", 1)[0].split())}


def pre_results_state(root: Path) -> dict:
    """Reject stale no-run prose before creating or replacing any artifact."""
    path = root / "research/milestones.json"
    try:
        raw = path.read_bytes()
        state = json.loads(raw)
    except (OSError, ValueError) as error:
        raise ValueError("Cannot verify pre-results state from milestone record") from error
    if (not isinstance(state, dict)
            or type(state.get("experimental_calls")) is not int
            or state["experimental_calls"] != 0
            or "execution_freeze" not in state or state["execution_freeze"] is not None):
        raise ValueError("Invalid pre-results state: experimental calls or freeze are present or unknown")
    checked = {}
    for journal in (root / "runs").rglob("calls.jsonl"):
        if not journal.with_name("manifest.json").is_file():
            raise ValueError("Orphan run journal contradicts verified pre-results state")
    for manifest_path in sorted((root / "runs").rglob("manifest.json")):
        try:
            data = manifest_path.read_bytes()
            manifest = json.loads(data)
            kind = manifest["run_config"]["evidence_kind"]
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise ValueError("Unknown run manifest in pre-results state") from error
        if kind != "synthetic":
            raise ValueError("Empirical or unclassified run contradicts pre-results state")
        checked[manifest_path.relative_to(root).as_posix()] = sha(data)
    return {"experimental_calls": 0, "execution_freeze": None,
            "milestone_sha256": sha(raw), "run_manifest_sha256": checked,
            "scope": "research/milestones.json, all runs/**/manifest.json and orphan run journals"}


def register_namespaces(xml: bytes) -> None:
    for _, (prefix, uri) in ET.iterparse(io.BytesIO(xml), events=("start-ns",)):
        if not re.fullmatch(r"ns\d+", prefix):
            ET.register_namespace(prefix, uri)


def serialize_with_original_root(tree: ET.Element, original: bytes) -> bytes:
    """Keep all source root namespace declarations, including mc prefix names."""
    register_namespaces(original)
    source = original.decode("utf-8")
    start = re.search(r"<(w:document|w:footnotes)\b[^>]*>", source)
    if start is None:
        raise ValueError("Unexpected source XML root")
    root_name = start[1]
    children = "".join(ET.tostring(child, encoding="unicode") for child in tree)
    return (source[:start.end()] + children + f"</{root_name}>").encode("utf-8")


def set_prop(parent: ET.Element, name: str, attrs: dict[str, str]) -> ET.Element:
    child = parent.find(tag(name))
    if child is None:
        child = ET.SubElement(parent, tag(name))
    for key, value in attrs.items():
        child.set(tag(key), str(value))
    return child


def paragraph_from(sample: ET.Element, text: str, *, code=False, bullet=False,
                   page_break=False, size: str | None = None, bold=False, compact=False) -> ET.Element:
    p = ET.Element(tag("p"))
    ppr = deepcopy(sample.find(tag("pPr")))
    if ppr is None:
        ppr = ET.Element(tag("pPr"))
    p.append(ppr)
    for n in list(ppr):
        if n.tag in {tag("numPr"), tag("sectPr")}:
            ppr.remove(n)
    if page_break:
        set_prop(ppr, "pageBreakBefore", {"val": "1"})
    if bullet:
        set_prop(ppr, "ind", {"left": "360", "hanging": "180"})
        text = "- " + text
    if code:
        set_prop(ppr, "spacing", {"before": "0", "after": "80", "line": "240", "lineRule": "auto"})
        set_prop(ppr, "keepLines", {"val": "1"})
    elif ppr.find(tag("pStyle")) is None:
        set_prop(ppr, "spacing", {"after": "80" if compact else "160", "line": "276", "lineRule": "auto"})
    rpr_source = sample.find("w:r/w:rPr", NS)
    rpr = deepcopy(rpr_source) if rpr_source is not None else ET.Element(tag("rPr"))
    for n in list(rpr):
        if n.tag in {tag("i"), tag("iCs"), tag("u")}:
            rpr.remove(n)
    if code:
        set_prop(rpr, "rFonts", {"ascii": "Courier New", "hAnsi": "Courier New", "cs": "Courier New", "eastAsia": "Courier New"})
        size = "18"
    if size:
        set_prop(rpr, "sz", {"val": size})
        set_prop(rpr, "szCs", {"val": size})
    if bold:
        set_prop(rpr, "b", {"val": "1"})
    run = ET.SubElement(p, tag("r"))
    run.append(rpr)
    for index, line in enumerate(text.split("\n")):
        if index:
            ET.SubElement(run, tag("br"))
        node = ET.SubElement(run, tag("t"), {"{http://www.w3.org/XML/1998/namespace}space": "preserve"})
        node.text = line
    return p


def table_from(rows: list[list[str]], body_sample: ET.Element) -> ET.Element:
    count = len(rows[0])
    widths = {2: [3400, 5960], 3: [2400, 5560, 1400], 5: [2750, 1450, 1900, 1630, 1630]}.get(count)
    if widths is None:
        raise ValueError("Unsupported manuscript table column count")
    table = ET.Element(tag("tbl"))
    props = ET.SubElement(table, tag("tblPr"))
    set_prop(props, "tblW", {"w": "9360", "type": "dxa"})
    set_prop(props, "tblLayout", {"type": "fixed"})
    set_prop(props, "jc", {"val": "center"})
    borders = ET.SubElement(props, tag("tblBorders"))
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        set_prop(borders, edge, {"val": "single", "sz": "4", "color": "D9D9D9"})
    grid = ET.SubElement(table, tag("tblGrid"))
    for width in widths:
        ET.SubElement(grid, tag("gridCol"), {tag("w"): str(width)})
    for index, row in enumerate(rows):
        tr = ET.SubElement(table, tag("tr"))
        trpr = ET.SubElement(tr, tag("trPr"))
        set_prop(trpr, "cantSplit", {"val": "1"})
        if index == 0:
            set_prop(trpr, "tblHeader", {"val": "1"})
        for col, value in enumerate(row):
            tc = ET.SubElement(tr, tag("tc"))
            tcpr = ET.SubElement(tc, tag("tcPr"))
            set_prop(tcpr, "tcW", {"w": widths[col], "type": "dxa"})
            set_prop(tcpr, "vAlign", {"val": "center"})
            margin = ET.SubElement(tcpr, tag("tcMar"))
            for edge in ("top", "bottom", "left", "right"):
                set_prop(margin, edge, {"w": "90", "type": "dxa"})
            if index == 0:
                set_prop(tcpr, "shd", {"fill": "EEEEEE", "val": "clear"})
            p = paragraph_from(body_sample, value, size="20", bold=index == 0)
            set_prop(p.find(tag("pPr")), "spacing", {"after": "0", "line": "240", "lineRule": "auto"})
            if col > 1:
                set_prop(p.find(tag("pPr")), "jc", {"val": "center"})
            tc.append(p)
    return table


def make_document(parts: dict[str, bytes], blocks: list[dict], contract: dict) -> dict[str, bytes]:
    root = ET.fromstring(parts["word/document.xml"])
    body = root.find(tag("body"))
    paragraphs = list(root.iter(tag("p")))
    by_text = {text_of(p): p for p in paragraphs if text_of(p)}
    heading_sample = by_text["1. Introduction"]
    subheading_sample = by_text["Limitations"]
    body_sample = next(p for p in paragraphs if text_of(p).startswith("What problem are you addressing"))
    first_table = body.find(tag("tbl"))
    title = next(p for p in first_table.iter(tag("p")) if text_of(p) == "PROJECT TITLE")
    title.find("w:r/w:t", NS).text = blocks[0]["text"]
    author_table = next(t for t in first_table.iter(tag("tbl"))
                        if any(text_of(p).startswith("Author name 1") for p in t.findall("w:tr/w:tc/w:p", NS)))
    sample_row = author_table.find(tag("tr"))
    source_cell = sample_row.find(tag("tc"))
    for child in list(author_table):
        if child.tag in {tag("tblGrid"), tag("tr")}:
            author_table.remove(child)
    width = author_table.find("w:tblPr/w:tblW", NS)
    width.set(tag("w"), "6240")
    grid = ET.SubElement(author_table, tag("tblGrid"))
    for _ in range(2):
        ET.SubElement(grid, tag("gridCol"), {tag("w"): "3120"})
    row = ET.SubElement(author_table, tag("tr"))
    for name in ("Tonmoy", "Araf"):
        cell = ET.SubElement(row, tag("tc"))
        properties = deepcopy(source_cell.find(tag("tcPr")))
        set_prop(properties, "tcW", {"w": "3120", "type": "dxa"})
        cell.append(properties)
        p = paragraph_from(source_cell.find(tag("p")), f"{name}\nAffiliation pending")
        set_prop(p.find(tag("pPr")), "spacing", {"after": "120", "line": "240", "lineRule": "auto"})
        cell.append(p)
    # Preserve source author wrapper geometry but give its editable content
    # cell adequate width; the original narrow cell caused placeholder wrapping.
    for parent in first_table.iter():
        for child in list(parent):
            if child.tag == tag("p") and text_of(child) == "WithApart Research":
                # Word requires the containing cell to end in a paragraph,
                # even when its final visible component is a nested table.
                parent.insert(list(parent).index(child), paragraph_from(child, ""))
                parent.remove(child)
    for table in first_table.iter(tag("tbl")):
        if author_table in list(table.iter(tag("tbl"))) and table is not first_table and table is not author_table:
            grid = table.find(tag("tblGrid"))
            for child in list(grid):
                grid.remove(child)
            ET.SubElement(grid, tag("gridCol"), {tag("w"): "7185"})
            for props in table.findall("w:tr/w:tc/w:tcPr", NS):
                set_prop(props, "tcW", {"w": "7185", "type": "dxa"})
    abstract_p = next(p for p in first_table.iter(tag("p")) if text_of(p).startswith("Summarize your project"))
    abstract_new = paragraph_from(abstract_p, contract["abstract"])
    # The abstract uses its source table/indents and single line rhythm.
    set_prop(abstract_new.find(tag("pPr")), "spacing", {"after": "160", "line": "240", "lineRule": "auto"})
    for parent in first_table.iter():
        if abstract_p in list(parent):
            parent.insert(list(parent).index(abstract_p), abstract_new)
            parent.remove(abstract_p)
            break
    section = deepcopy(body.find(tag("sectPr")))
    for child in list(body):
        body.remove(child)
    body.append(first_table)
    body.append(paragraph_from(body_sample, "Pre-results manuscript. No empirical smoke, pilot or main observations. Affiliations and human review remain pending.", bold=True))
    body.append(paragraph_from(body_sample, "Project: Beyond the Label. Intended sprint track: Trust Infrastructure."))
    in_appendix = False
    for block in blocks[contract["abstract_index"] + 2:]:
        kind = block["kind"]
        if kind == "heading":
            in_appendix = in_appendix or block["text"].startswith("Appendix")
            style = heading_sample if block["level"] == 2 else subheading_sample
            body.append(paragraph_from(style, block["text"], page_break=block["text"] in {"References", "Appendix A. Limitations and Dual-Use / Ethical Considerations"}))
        elif kind == "table":
            body.append(table_from(block["rows"], body_sample))
            body.append(paragraph_from(body_sample, ""))
        else:
            body.append(paragraph_from(body_sample, block["text"], code=kind == "code", bullet=kind == "bullet", compact=in_appendix))
    body.append(section)
    foot = ET.fromstring(parts["word/footnotes.xml"])
    nodes = list(foot.iter(tag("t")))
    nodes[0].text = " Pre-results study for the "
    nodes[-1].text = ", November 2026. No empirical observations are reported."
    result = dict(parts)
    result["word/document.xml"] = serialize_with_original_root(root, parts["word/document.xml"])
    result["word/footnotes.xml"] = serialize_with_original_root(foot, parts["word/footnotes.xml"])
    return result


def evidence_rows(blocks: list[dict], root: Path) -> list[dict]:
    """Map substantive blocks, including every numeric token, to source classes."""
    rows, location = [], "Front matter"
    prompt_texts = {(root / p).read_text("utf-8").strip(): p
                    for p in ("prompts/agent_system.txt", "prompts/probe_readback.txt")}
    for index, block in enumerate(blocks):
        if block["kind"] == "heading":
            location = block["text"]
            continue
        texts = [" | ".join(row) for row in block["rows"]] if block["kind"] == "table" else [block["text"]]
        for row_index, text in enumerate(texts):
            classification = "design_or_method"
            sources = ["research/protocol.md", "research/amendments.md"]
            if "Related work" in location or location == "References":
                classification, sources = "verified_external_citation", ["research/checks/source_verification.json"]
            elif location.startswith("3.3"):
                classification, sources = "analytic_reference_not_observation", ["research/oracle_derivation.md", "evaluation/oracle_table.csv"]
            elif location.startswith("4. Results"):
                classification, sources = "pending_empirical_result", ["research/milestones.json", "report/manuscript.md"]
            elif "candidate configuration" in text:
                classification, sources = "proposed_not_frozen_settings", ["configs/free.yaml"]
            elif "template" in text and "guidelines" in text:
                classification, sources = "verified_submission_requirements", ["research/checks/report_preparation_sources.json"]
            elif location == "Code and Data":
                classification, sources = "repository_provenance", ["research/audit.md", "README.md"]
            elif "LLM Usage" in location or "No human H1" in text:
                classification, sources = "participation_disclosure_not_review", ["report/manuscript.md", "research/decisions.md"]
            elif block["kind"] == "code" or location.startswith("B.3"):
                classification, sources = "reproduction_instruction_not_execution", ["README.md", "scripts/validate_offline.py", "src/beyond_label/analyze.py", "src/beyond_label/evidence.py"]
            if block["kind"] == "code" and text in prompt_texts:
                classification, sources = "verbatim_prompt_not_observation", [prompt_texts[text]]
            if "Tonmoy; Araf" in text or text.startswith("Affiliations:"):
                classification, sources = "confirmed_authors_pending_affiliations", ["research/milestones.json"]
            if "A1" in text and "research/amendments.md" not in sources:
                sources.append("research/amendments.md")
            if any(phrase in text for phrase in ("No real smoke", "No empirical", "No execution freeze",
                                                 "No model inference observations", "No human H1")):
                sources = list(dict.fromkeys(sources + ["research/milestones.json", "research/audit.md"]))
            rows.append({"claim_id": f"p{index:03d}-{row_index}", "location": location, "classification": classification,
                         "claim_text": text, "numeric_tokens": json.dumps(re.findall(r"(?<![A-Za-z])\d+(?:[.,]\d+)?", text)),
                         "source_files": json.dumps(sources),
                         "source_sha256": json.dumps({p: sha((root / p).read_bytes()) for p in sources}),
                         "regenerate_command": "python scripts/build_report.py",
                         "empirical_evidence": "false", "human_review_claimed": "false"})
    return rows


def build_report(root: Path = ROOT, output_dir: Path | None = None) -> dict:
    state = pre_results_state(root)
    output = output_dir or root / "report"
    template = root / "report/official_template.docx"
    template_bytes = template.read_bytes()
    if sha(template_bytes) != TEMPLATE_SHA256:
        raise ValueError("Official template hash mismatch; re-distillation required")
    manuscript = (root / "report/manuscript.md").read_text(encoding="utf-8")
    blocks = parse_manuscript(manuscript)
    contract = manuscript_contract(manuscript, blocks)
    with ZipFile(io.BytesIO(template_bytes)) as archive:
        names = archive.namelist()
        parts = {name: archive.read(name) for name in names}
    built = make_document(parts, blocks, contract)
    if set(built) != set(parts) or any(built[n] != parts[n] for n in names if n not in EDITABLE_PARTS):
        raise ValueError("Preserve-only template part changed")
    original_section = ET.fromstring(parts["word/document.xml"]).find("w:body/w:sectPr", NS)
    new_section = ET.fromstring(built["word/document.xml"]).find("w:body/w:sectPr", NS)
    if ET.tostring(original_section) != ET.tostring(new_section):
        raise ValueError("Template page geometry changed")
    output.mkdir(parents=True, exist_ok=True)
    docx = output / "pre_results.docx"
    with ZipFile(docx, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name in names:
            info = ZipInfo(name, date_time=(2026, 11, 14, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, built[name], compresslevel=9)
    claims = evidence_rows(blocks, root)
    claim_path = output / "claim_to_evidence.csv"
    with claim_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(claims[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(claims)
    inputs = ["report/official_template.docx", "report/manuscript.md", "report/artifact.md", "scripts/build_report.py"]
    manifest = {
        "schema_version": 1, "classification": "pre_results_report_not_empirical_findings",
        "empirical_observations": 0, "empirical_run_started": False, "execution_freeze": None,
        "pre_results_state": state,
        "authors": ["Tonmoy", "Araf"], "affiliations": "pending_confirmation", "human_review_verified": False,
        "abstract_word_count": contract["abstract_word_count"],
        "body_word_count_including_tables_and_frontmatter": contract["body_word_count_including_tables_and_frontmatter"],
        "input_sha256": {p: sha((root / p).read_bytes()) for p in inputs},
        "outputs": {"pre_results.docx": sha(docx.read_bytes()), "claim_to_evidence.csv": sha(claim_path.read_bytes())},
        "template_parts": [{"path": n, "size": len(parts[n]), "sha256": sha(parts[n]),
                            "policy": "editable" if n in EDITABLE_PARTS else "preserve_only"} for n in names],
        "preserved_parts_verified": True, "page_geometry_preserved": True,
        "template_reference_render": {"renderer": "Microsoft Word COM read-only export", "pages": 5,
                                      "visual_review": "AI reviewed all five reference pages"},
        "render_verification": {"status": "pending", "pdf_available": False, "all_pages_visually_reviewed": False,
                                "body_page_limit_verified": False},
        "submission_ready": False,
        "limitations": ["No empirical results, execution freeze, confirmed affiliations or human H1-H5 review.",
                        "DOCX build success does not establish rendered page count or visual correctness.",
                        "The claim map records design, analytic, citation and pending evidence; it is not a main-run result map."],
        "regenerate_command": "python scripts/build_report.py",
    }
    old_path = output / "report_manifest.json"
    if old_path.is_file():
        previous = json.loads(old_path.read_text("utf-8"))
        qa = previous.get("render_verification", {})
        pdf_path = output / "pre_results.pdf"
        if (previous.get("outputs", {}).get("pre_results.docx") == manifest["outputs"]["pre_results.docx"]
                and qa.get("docx_sha256") == manifest["outputs"]["pre_results.docx"]
                and pdf_path.is_file() and qa.get("pdf_sha256") == sha(pdf_path.read_bytes())):
            manifest["render_verification"] = qa
            manifest["outputs"]["pre_results.pdf"] = sha(pdf_path.read_bytes())
    old_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Alternative artifact directory; reference/manuscript remain unchanged")
    args = parser.parse_args()
    result = build_report(output_dir=args.output)
    print(json.dumps({"classification": result["classification"], "abstract_words": result["abstract_word_count"],
                      "preserved_parts_verified": result["preserved_parts_verified"],
                      "render_status": result["render_verification"]["status"]}))


if __name__ == "__main__":
    main()
