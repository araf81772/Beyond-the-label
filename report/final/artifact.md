# Final empirical paper: official-template contract

The unchanged reference is `report/official_template.docx`, SHA-256
`21ebc0bcea8f9760c64c9c0eb163bbaaab0a34465722f86e4e3feecf6849de59`.
Its five retained rendered pages were inspected before final-paper production.
This contract describes the new empirical document; the historical pre-results
contract and artifacts remain unchanged.

## Preserved template

Preserve the exact Letter section XML: 12240 by 15840 twips, one-inch margins,
720-twip header/footer distances. Preserve the embedded Old Standard TT fonts,
styles, settings, numbering, theme and original sprint footnote. Retain the
title container, its rules, the abstract table and the With Apart Research line.
The source's actual body font is Old Standard TT 11 pt with 1.15 spacing;
main headings are 14 pt and subsections 13 pt. No new header/footer is added.

Replace the editable six-author placeholder table with three equal cells in
7185 twips, retaining its wrapper. Names and Independent researcher affiliations
are explicitly user-confirmed in author_metadata.json. Delete all template
instructions. Replace the body with the final empirical manuscript. References
and both appendices start new pages. Tables use 10 pt type, repeated headers,
light borders, explicit column widths and unsplittable rows. Commands use 9 pt
monospace. Appendix paragraphs have 4 pt after-spacing; body paragraphs 8 pt.
Figure 1 is a 300-dpi, 6.5-inch scientific replot of the unchanged allocation CSV.
Its zero invalid/missing categories are disclosed in the caption; no data or
estimand changes. The figure has alt text and remains with its caption.

Only word/document.xml, its relationship part and [Content_Types].xml are
modified template parts; a single new image part is added. Every other template
part, including footnotes, is byte-preserved. Section XML equality and text
coverage are asserted by the builder. Fixed ZIP timestamps make the DOCX
deterministically rebuildable. Word-exported PDF metadata may vary.

## Evidence and authorship boundary

Use only the completed empirical bundle results/staged_main_complete. The
builder checks all eleven artifact hashes and 704 terminal / zero pending
counts. It never invokes the historical pre-results build or its state guard.
Frozen scientific inputs, operational scripts/tests and original evidence stay
unchanged. The final paper has a separate 104-row numeric source map and offline
verifier. Human completion is user-attested; AI review and visual checks do not
fabricate worksheets, initials or final-author approval.

## Build and rendering

The system scientific Python environment provides Matplotlib; generate only the
figure with `python report/final/build_submission.py --figure-only`. The bundled
document Python environment then creates the DOCX with
`report/final/build_submission.py --reuse-figure`, checking the figure/source/
builder hashes. Normal final builds reject missing author affiliations or prior
work disclosure. Explicit --draft is for internal layout checks only.

Bundled Python used:
`C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1112-611-0_26.1112.611.0_x64__3k8sg7r9htsxt/dependencies/python/python.exe`.

The canonical documents renderer was attempted and failed because the bundled
Windows environment has no soffice.exe. Its failure is retained in
evaluation/final_paper_qa/canonical/failure.txt. The fallback
`report/final/render_submission.ps1` uses a hidden isolated Word COM application,
aborts if it contains any user documents, opens this DOCX read-only, exports the
PDF, closes only its own document/application and verifies unchanged DOCX bytes.
Bundled Poppler rasterizes every page at 120 dpi. Use a new QA directory for each
render; earlier renders remain available locally.

The second render was inspected in full at native image size: 11 pages, with
7 body pages, References on page 8, Appendix A on page 9 and Appendix B on
pages 10-11. The abstract has 192 words. No clipped text, split table rows,
missing glyphs, overlapping labels, placeholders or trailing orphan page remain.
This is AI visual QA, not human signoff. The final validation record binds the
review to exact DOCX, PDF and all page-image hashes.
