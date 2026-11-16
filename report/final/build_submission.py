"""Offline final empirical-paper builder; never changes a frozen input.

Run with the bundled document runtime. --draft permits explicit missing metadata
for layout work only; final builds reject those placeholders. No credentials,
provider clients or inference entry points are imported.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TEMPLATE = ROOT / "report/official_template.docx"
BUNDLE = ROOT / "results/staged_main_complete"
spec = importlib.util.spec_from_file_location("template_helpers", ROOT / "scripts/build_report.py")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
tag, text_of, set_prop = helper.tag, helper.text_of, helper.set_prop
pfrom = helper.paragraph_from
NS = helper.NS

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def allocation_figure():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    rows = list(csv.DictReader((BUNDLE / "analysis/figures/allocation.csv").open(newline="")))
    plt.rcParams.update({"font.family": "DejaVu Serif", "font.size": 8.5,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 3, figsize=(6.5, 2.25), sharey=True)
    for ax, condition in zip(axes, ["MAIN", "HIGH-FEE", "HIGH-STAKES"]):
        subset = [r for r in rows if r["condition"] == condition]
        assert all(int(r["agent_count"]) == 0 for r in subset if r["action"] in {"INVALID", "MISSING"})
        subset = subset[:3]
        agent = [float(r["agent_fraction"]) for r in subset]
        oracle = [float(r["oracle_reference_fraction"]) for r in subset]
        ax.bar([x-.18 for x in range(3)], agent, width=.36, color="#356780", label="Agent")
        ax.bar([x+.18 for x in range(3)], oracle, width=.36, color="#d5d5d5", edgecolor="#666666", linewidth=.5, label="Oracle")
        ax.set_xticks(range(3), ["Commit", "Lot 1", "Lot 2"])
        ax.set_title(condition, fontsize=9, fontweight="bold")
        ax.set_ylim(0, 1.08)
        ax.set_yticks([0, .5, 1])
        ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        ax.grid(axis="y", alpha=.17)
        ax.set_axisbelow(True)
        ax.tick_params(axis="both", length=2)
    axes[0].set_ylabel("Share of planned decisions")
    axes[1].set_xlabel("First action (lot positions refer to inspection)", labelpad=9)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="upper center", ncol=2, frameon=False,
               bbox_to_anchor=(.53, 1.04))
    fig.subplots_adjust(left=.095, right=.99, bottom=.23, top=.78, wspace=.16)
    destination = HERE / "figures/allocation.png"
    destination.parent.mkdir(exist_ok=True)
    fig.savefig(destination, dpi=300, metadata={"Software": "Beyond the Label final-paper presentation"})
    plt.close(fig)
    (HERE / "figures/source.json").write_text(json.dumps({
        "source": "results/staged_main_complete/analysis/figures/allocation.csv",
        "source_sha256": sha(BUNDLE / "analysis/figures/allocation.csv"),
        "figure_sha256": sha(destination), "builder_sha256": sha(__file__),
        "purpose": "Presentation-only replot of unchanged frozen analysis fractions"
    }, indent=2)+"\n", encoding="utf-8", newline="\n")
    return destination

def table(rows, sample):
    widths = ([4450, 2455, 2455] if len(rows[0]) == 3 else
              [2700, 1580, 1700, 1630, 1750])
    tbl = ET.Element(tag("tbl")); props = ET.SubElement(tbl, tag("tblPr"))
    set_prop(props, "tblW", {"w": "9360", "type": "dxa"})
    set_prop(props, "tblLayout", {"type": "fixed"})
    borders = ET.SubElement(props, tag("tblBorders"))
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        set_prop(borders, edge, {"val": "single", "sz": "4", "color": "D9D9D9"})
    grid = ET.SubElement(tbl, tag("tblGrid"))
    for width in widths:
        ET.SubElement(grid, tag("gridCol"), {tag("w"): str(width)})
    for ri, values in enumerate(rows):
        tr = ET.SubElement(tbl, tag("tr")); trpr = ET.SubElement(tr, tag("trPr"))
        set_prop(trpr, "cantSplit", {"val": "1"})
        if ri == 0:
            set_prop(trpr, "tblHeader", {"val": "1"})
        for ci, value in enumerate(values):
            tc = ET.SubElement(tr, tag("tc")); tcpr = ET.SubElement(tc, tag("tcPr"))
            set_prop(tcpr, "tcW", {"w": str(widths[ci]), "type": "dxa"})
            set_prop(tcpr, "vAlign", {"val": "center"})
            margins = ET.SubElement(tcpr, tag("tcMar"))
            for edge in ("top", "bottom", "left", "right"):
                set_prop(margins, edge, {"w": "70", "type": "dxa"})
            if ri == 0:
                set_prop(tcpr, "shd", {"fill": "EEEEEE", "val": "clear"})
            p = pfrom(sample, value, size="20", bold=ri == 0)
            ppr = p.find(tag("pPr"))
            set_prop(ppr, "spacing", {"after": "0", "line": "240", "lineRule": "auto"})
            if ci:
                set_prop(ppr, "jc", {"val": "center"})
            tc.append(p)
    return tbl

def image_paragraph(sample):
    p = pfrom(sample, "")
    set_prop(p.find(tag("pPr")), "keepNext", {"val": "1"})
    set_prop(p.find(tag("pPr")), "spacing", {"before": "120", "after": "160"})
    drawing = ET.fromstring('''<w:drawing xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
      xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
      xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
      xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"
      xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
      <wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="5943600" cy="2057400"/>
      <wp:docPr id="101" name="Figure 1" descr="Agent and oracle first-action allocation for MAIN, HIGH-FEE and HIGH-STAKES; values from the completed frozen analysis."/>
      <wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>
      <a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic>
      <pic:nvPicPr><pic:cNvPr id="101" name="allocation.png"/><pic:cNvPicPr/></pic:nvPicPr>
      <pic:blipFill><a:blip r:embed="rIdFinalAllocation"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
      <pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="5943600" cy="2057400"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>
      </pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing>''')
    ET.SubElement(p, tag("r")).append(drawing)
    return p

def build(draft=False, reuse_figure=False):
    assert sha(TEMPLATE) == helper.TEMPLATE_SHA256
    manifest = json.loads((BUNDLE / "bundle_manifest.json").read_text())
    assert manifest["completeness"]["completed_cells"] == 704
    assert manifest["completeness"]["pending_cells"] == 0
    for name, digest in manifest["artifact_hashes"].items():
        assert sha(BUNDLE / name) == digest, name
    metadata = json.loads((HERE / "author_metadata.json").read_text())
    if not draft:
        assert all(a["affiliation"] for a in metadata["authors"]), "Unconfirmed affiliations"
        assert metadata["prior_work_disclosure"], "Unspecified prior work"
    text = (HERE / "manuscript.md").read_text(encoding="utf-8")
    disclosure = metadata["prior_work_disclosure"] or "[Prior-work details awaiting author confirmation.]"
    text = text.replace("[[PRIOR_WORK_DISCLOSURE]]", disclosure)
    if metadata["contributions"]:
        text = text.replace(disclosure, disclosure + "\n\n" + metadata["contributions"])
    blocks = helper.parse_manuscript(text)
    abstract_index = next(i for i, b in enumerate(blocks) if b.get("text") == "Abstract")
    abstract = blocks[abstract_index+1]["text"]
    assert 150 <= len(abstract.split()) <= 250
    with ZipFile(TEMPLATE) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    original = dict(parts)
    root = ET.fromstring(parts["word/document.xml"])
    body = root.find(tag("body")); paragraphs = list(root.iter(tag("p")))
    by_text = {text_of(p): p for p in paragraphs if text_of(p)}
    hs, ss = by_text["1. Introduction"], by_text["Limitations"]
    sample = next(p for p in paragraphs if text_of(p).startswith("What problem are you addressing"))
    front = body.find(tag("tbl"))
    title = next(p for p in front.iter(tag("p")) if text_of(p) == "PROJECT TITLE")
    title.find("w:r/w:t", NS).text = blocks[0]["text"]
    authors = next(t for t in front.iter(tag("tbl")) if any(text_of(p).startswith("Author name 1") for p in t.findall("w:tr/w:tc/w:p", NS)))
    source_cell = deepcopy(authors.find("w:tr/w:tc", NS))
    for child in list(authors):
        if child.tag in {tag("tblGrid"), tag("tr")}:
            authors.remove(child)
    set_prop(authors.find(tag("tblPr")), "tblW", {"w": "7185", "type": "dxa"})
    grid = ET.SubElement(authors, tag("tblGrid")); row = ET.SubElement(authors, tag("tr"))
    for author in metadata["authors"]:
        ET.SubElement(grid, tag("gridCol"), {tag("w"): "2395"})
        cell = ET.SubElement(row, tag("tc")); props = deepcopy(source_cell.find(tag("tcPr")))
        set_prop(props, "tcW", {"w": "2395", "type": "dxa"}); cell.append(props)
        p = pfrom(source_cell.find(tag("p")), author["name"] + "\n" + (author["affiliation"] or "[Affiliation to confirm]"))
        set_prop(p.find(tag("pPr")), "spacing", {"after": "120", "line": "240", "lineRule": "auto"})
        cell.append(p)
    for tbl in front.iter(tag("tbl")):
        if authors in list(tbl.iter(tag("tbl"))) and tbl is not front and tbl is not authors:
            grid = tbl.find(tag("tblGrid"))
            for c in list(grid): grid.remove(c)
            ET.SubElement(grid, tag("gridCol"), {tag("w"): "7185"})
            for props in tbl.findall("w:tr/w:tc/w:tcPr", NS):
                set_prop(props, "tcW", {"w": "7185", "type": "dxa"})
    ap = next(p for p in front.iter(tag("p")) if text_of(p).startswith("Summarize your project"))
    replacement = pfrom(ap, abstract)
    set_prop(replacement.find(tag("pPr")), "spacing", {"after": "160", "line": "240", "lineRule": "auto"})
    for parent in front.iter():
        if ap in list(parent): parent.insert(list(parent).index(ap), replacement); parent.remove(ap); break
    section = deepcopy(body.find(tag("sectPr")))
    for child in list(body): body.remove(child)
    body.append(front)
    appendix = False
    previous_table = False
    for block in blocks[abstract_index+2:]:
        kind = block["kind"]
        if kind == "heading":
            appendix = appendix or block["text"].startswith("Appendix")
            p = pfrom(hs if block["level"] == 2 else ss, block["text"],
                      page_break=block["text"] == "References" or block["text"].startswith("Appendix"))
            set_prop(p.find(tag("pPr")), "keepNext", {"val": "1"}); body.append(p)
        elif kind == "table":
            body.append(table(block["rows"], sample))
        elif block["text"] == "[[FIGURE1]]": body.append(image_paragraph(sample))
        else:
            p = pfrom(sample, block["text"], code=kind == "code", compact=appendix)
            if previous_table:
                set_prop(p.find(tag("pPr")), "spacing", {"before": "80"})
            if re.match(r"Table (\d|B\d)", block["text"]):
                set_prop(p.find(tag("pPr")), "keepNext", {"val": "1"})
            body.append(p)
        previous_table = kind == "table"
    body.append(section)
    parts["word/document.xml"] = helper.serialize_with_original_root(root, original["word/document.xml"])
    assert ET.tostring(section) == ET.tostring(ET.fromstring(original["word/document.xml"]).find("w:body/w:sectPr", NS))
    if reuse_figure:
        figure = HERE / "figures/allocation.png"
        figure_manifest = json.loads((HERE / "figures/source.json").read_text())
        assert figure_manifest["source_sha256"] == sha(BUNDLE / "analysis/figures/allocation.csv")
        assert figure_manifest["figure_sha256"] == sha(figure)
        assert figure_manifest["builder_sha256"] == sha(__file__)
    else:
        figure = allocation_figure()
    parts["word/media/final_allocation.png"] = figure.read_bytes()
    relns = "http://schemas.openxmlformats.org/package/2006/relationships"
    rels = ET.fromstring(parts["word/_rels/document.xml.rels"])
    ET.SubElement(rels, "{"+relns+"}Relationship", {"Id": "rIdFinalAllocation", "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image", "Target": "media/final_allocation.png"})
    parts["word/_rels/document.xml.rels"] = ET.tostring(rels, encoding="utf-8", xml_declaration=True)
    types = ET.fromstring(parts["[Content_Types].xml"])
    ET.SubElement(types, "{http://schemas.openxmlformats.org/package/2006/content-types}Default", {"Extension": "png", "ContentType": "image/png"})
    parts["[Content_Types].xml"] = ET.tostring(types, encoding="utf-8", xml_declaration=True)
    edited = {"word/document.xml", "word/_rels/document.xml.rels", "[Content_Types].xml"}
    for name in original:
        if name not in edited: assert parts[name] == original[name], name
    output = HERE / "beyond_the_label.docx"
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as z:
        for name, content in parts.items():
            info = ZipInfo(name, (2026, 11, 16, 0, 0, 0)); info.compress_type = ZIP_DEFLATED
            z.writestr(info, content)
    paper_text = "\n".join(t.text or "" for t in root.iter(tag("t")))
    for block in blocks[abstract_index+2:]:
        if block["kind"] != "table" and block.get("text") != "[[FIGURE1]]":
            assert block["text"] in paper_text, block["text"][:70]
    report = {"classification": "layout_draft_metadata_pending" if draft else "empirical_final_paper",
              "template_sha256": sha(TEMPLATE), "bundle_manifest_sha256": sha(BUNDLE/"bundle_manifest.json"),
              "manuscript_sha256": sha(HERE/"manuscript.md"), "metadata_sha256": sha(HERE/"author_metadata.json"),
              "builder_sha256": sha(__file__), "docx_sha256": sha(output), "figure_sha256": sha(figure),
              "abstract_word_count": len(abstract.split()), "body_word_count_including_frontmatter_tables": len(text.split("## References")[0].split()),
              "template_parts_preserved": [n for n in original if n not in edited],
              "template_parts_changed": sorted(edited), "section_xml_preserved": True,
              "source_artifacts_verified": len(manifest["artifact_hashes"]), "visual_review": "requires_current_PDF_and_all_page_review",
              "human_final_artifact_approval_claimed": False}
    (HERE/"build_manifest.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8", newline="\n")
    print(json.dumps({k:v for k,v in report.items() if k not in {"template_parts_preserved"}}, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft", action="store_true")
    parser.add_argument("--figure-only", action="store_true")
    parser.add_argument("--reuse-figure", action="store_true")
    args = parser.parse_args()
    if args.figure_only:
        print(allocation_figure())
    else:
        build(args.draft, args.reuse_figure)
