# Official template execution contract

Reference: `C:/Users/tonmo/OneDrive/Documents/ChatGPT/beyond-the-label/report/official_template.docx`, SHA-256 `21ebc0bcea8f9760c64c9c0eb163bbaaab0a34465722f86e4e3feecf6849de59`, 302828 bytes. The reference remains unchanged. Its five Word-rendered pages were reviewed in `evaluation/report_qa/template_reference/page-1.png` through `page-5.png`. The canonical skill renderer fails because this Windows bundle has no `soffice.exe`; isolated hidden Microsoft Word COM read-only export works with sandbox elevation. Poppler from the dependency bundle rasterizes the resulting PDF. The template itself wraps its six author placeholders awkwardly; two confirmed authors require a readable adaptation of that editable slot.

## Page and typography system

One portrait Letter section, 12240 × 15840 twips; all margins 1440 twips; header/footer distances 720 twips; page numbering starts at 1. No headers, footers, images, drawings, content controls, TOC or page fields exist. Preserve the section XML exactly. Embedded Old Standard TT regular/bold/italic fonts, theme, styles, settings, numbering and relationships are preserve-only.

The document default is Arial 11 pt / 1.15 line spacing, but all actual body text directly selects Old Standard TT. Use the source body paragraph and run properties: 11 pt inherited, Old Standard TT, 1.15 lines, black. Title is the named Title style with source direct formatting: centered bold Old Standard TT 20 pt, single lines, 10 pt after. Main sections are source Heading2 paragraphs: underlying style 16 pt, actual source direct override 14 pt bold, 10 pt before, 0 after and 1.5 lines. Subsections clone Heading3: direct 13 pt bold black, 10 pt before. Keep headings with following content. Body guidance italics are removed when replacing instructions with manuscript prose; paragraph spacing is 8 pt instead of repeated empty template paragraphs, a documented content-flow adaptation. New scientific table text is 10 pt for compact multi-column comparison. Title punctuation and the source's table borders follow the authoritative title/template rather than generic skill styling.

## Slot map and content flow

- `word/document.xml / w:body / w:tbl[1]`: retained title/author/abstract container, width 9360 twips. Preserve its title rows and source cell border rules. Replace Title paragraph text with the exact manuscript title, retaining footnote anchor 0.
- Nested author table in that container: six placeholder paragraphs inside a narrow three-column/two-row table. This is an editable author capacity slot, not an immutable layout element. Replace it with two equal 3120-twip cells in one row, using cloned author cell/paragraph formatting, centered names Tonmoy and Araf and explicit affiliation pending. Remove unused author slots and the unsupported “With Apart Research” text. Preserve outer container and align the author block centrally. This intentional geometry adjustment prevents the reference's word wrapping defect with the actual author count.
- Abstract heading and nested one-cell abstract table: preserve position, 7095-twip width, indents, margins and alignment; replace guidance with the manuscript's 150–250-word abstract, plain rather than instruction italics/underlining.
- `w:body / w:tbl[2]`: remove the yellow instruction box as directed by the template.
- Body after the title table: replace all guidance paragraphs with the manuscript's ordered sections, using source Heading2/Heading3/body patterns. Preserve manuscript tables as actual numerical/status tables; widths follow available 9360 twips, repeated header, no fixed row heights. New scientific table components use the template's Old Standard typography and deliberately specified light borders/padding.
- References and Appendix A begin on new pages so the body page count can be checked independently. Code examples use 9 pt monospace only for commands/JSON; this content role has no source equivalent and is recorded as an explicit reproducibility adaptation. Preserve their text exactly and allow wrapping, never clipping.
- `word/footnotes.xml / w:footnote[@w:id='0']`: retain anchor/style and source hyperlink relation; replace the unsupported completed-research assertion with an explicit pre-results description. All other footnote structures and relationships remain unchanged.

Content order: title/authors, abstract, explicit pre-results status, Introduction, Related Work, Methods, Results NOT RUN, Discussion and Limitations, Conclusion, Code and Data, References, required Appendix A, Appendix B, LLM Usage Statement. Unsupported author contributions are omitted. Pending affiliations, empirical results and human reviews remain explicit rather than invented.

## Package preservation and evidence

The builder records every template ZIP part's name, size and SHA-256 in `report_manifest.json`. Only `word/document.xml` and `word/footnotes.xml` are editable; all other ZIP entry contents must be byte-identical. No template relationship may be removed. The package has no media/header/footer parts; embedded fonts are preserved. ZIP timestamps are fixed for deterministic regeneration. The builder does not contact a provider or read credentials.

Appendix prose uses 4 pt paragraph-after spacing, retaining the same font and line spacing, to reduce trailing-page imbalance. Code blocks are kept together; numbered references remain separate paragraphs. Synthetic example directory names are short enough to retain full command tokens on each line. These content-flow adjustments were prompted by the first actual Word render.

Required gates: original template hash; exact preserved-part comparison; section equality; complete manuscript text coverage; no leftover guidance or invented affiliation/research claims; abstract 150–250 words; all actual references resolve to the verified primary-source record; no empirical numbers presented as observations; deterministic DOCX/evidence-map rebuild. PDF page count, body page limit and visual review are only marked verified after real Word export and inspection of every final page. The manifest must distinguish an unrendered draft from a visually verified artifact. No report status constitutes an execution freeze or empirical milestone completion.

The pre-results builder also requires an explicit zero experimental-call count and no execution freeze in the milestone record. It rejects empirical, unknown or malformed manifests under `runs`, and orphan run journals. A real run therefore requires a new evidence-backed report workflow instead of regenerating stale no-results assertions.

## Reproduction and rendering

From the repository root, `python scripts/build_report.py` rebuilds the DOCX, source-specific claim map and manifest using only the Python standard library. The DOCX bytes are deterministic. On this machine document authoring uses the bundled interpreter:

```powershell
& 'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1112-611-0_26.1112.611.0_x64__3k8sg7r9htsxt/dependencies/python/python.exe' scripts/build_report.py
```

The canonical rendering command was attempted and failed because LibreOffice is absent:

```powershell
& 'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1112-611-0_26.1112.611.0_x64__3k8sg7r9htsxt/dependencies/python/python.exe' 'C:/Users/tonmo/.codex/plugins/cache/openai-primary-runtime/documents/26.1112.11011/skills/documents/render_docx.py' report/pre_results.docx --output_dir evaluation/report_qa/canonical --emit_pdf
```

The retained Windows fallback is repeatable with Microsoft Word installed and local COM access permitted:

```powershell
& ./scripts/render_report.ps1 -QaDirectory evaluation/report_qa/new_render
```

Use a new QA directory to retain earlier renders. This exports `report/pre_results.pdf` from a hidden, isolated Word instance with the DOCX opened read-only, checks the DOCX hash, and rasterizes every page at 96 dpi. It aborts if the acquired Word instance contains any existing documents; it closes only its own document and application. The default Poppler executable is `C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1112-611-0_26.1112.611.0_x64__3k8sg7r9htsxt/dependencies/native/poppler/Library/bin/pdftoppm.exe`; another local installation can be supplied with `-Poppler`. Sandbox COM access failed with `E_ACCESSDENIED`; the same isolated operation succeeded with approved elevation.

The exporter writes machine-only page hashes and leaves visual checks false. Inspect every PNG at native size, verify body pages independently of references/appendices, and record actual review against the DOCX/PDF hashes in `report_manifest.json`. Exported PDF bytes can vary with Word version and metadata; do not describe the PDF as byte-deterministic. A source rebuild preserves the recorded visual result only when both DOCX and PDF hashes still match. Changes to either require another render and review. This is AI layout QA, not human H1–H5 review or submission approval.
