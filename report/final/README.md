# Final empirical paper

Use [the PDF](beyond_the_label.pdf) for submission after author approval. The
[editable DOCX](beyond_the_label.docx) uses the retained official template.
This package contains seven body pages, a 192-word abstract, references, the
required limitations/ethics appendix, reproduction details, prior-work and AI
disclosures. It was prepared from the completed 704-cell evidence, not the
historical stopped-parent bundle or pre-results manuscript.

Tonmoy Sarker, Araf Akhter and Abidur Rahaman confirmed their names and
Independent researcher affiliations through the team representative. The idea
and local design draft predated the sprint; the latest clarification says no
preexisting code is included. Exact confirmations and their correction are in
[author_metadata.json](author_metadata.json).

The bounded result is **no gap here under these conditions**. It is not perfect
performance or evidence that the layouts are equivalent. Payoff failures,
invalid actions, one missing continuation, MASKED truncation and late review
timing remain in the paper. Human H3/H4 completion is user-attested, with its
scope in [the post-main record](../../research/post_main_human_verification.json).
AI checks do not supply missing human worksheets or approval of this new PDF.

## Evidence and checks

- [Manuscript](manuscript.md), [numeric source map](claim_evidence.csv), and
  [offline verifier](verify_claims.py): 104 evidence rows across 26 source files.
- [Completed empirical bundle](../../results/staged_main_complete/bundle_manifest.json):
  704 terminal cells, 448 decisions and 256 readbacks; all frozen analysis inputs
  and original observations retained.
- [Build manifest](build_manifest.json), [template contract](artifact.md), and
  [final validation](../../research/checks/final_paper_validation.json).
- [Independent AI reviews](../../research/checks/final_paper_AI_review.json).

Run `python report/final/verify_claims.py` to check the saved map. It recomputes
source values offline and rejects unmapped numeric paragraphs. `--write` is only
for regenerating the map after reviewing intentional manuscript/source changes.
It does not perform inference. This machine verification supplements human H4. Run the bundled Python on `report/final/verify_artifact.py` to check document text, frozen hashes, PDF constraints and the current visual-review hashes.

## Build and reproduce

From the repository root:

```powershell
python report/final/build_submission.py --figure-only
# Run the next command with the bundled document Python (see artifact.md).
python report/final/build_submission.py --reuse-figure
python report/final/verify_claims.py
```

The first command uses Matplotlib to replot unchanged analysis fractions; the
second uses only the standard library and verifies the figure/source hashes.
Final builds reject missing affiliations or prior-work disclosure. The DOCX
must rebuild byte-identically. The historic pre-results builder is deliberately
not invoked and its empirical-state guard remains unchanged.

The canonical DOCX renderer was attempted but this Windows bundle has no
LibreOffice. Render locally with installed Microsoft Word and bundled Poppler:

```powershell
./report/final/render_submission.ps1 -QaDirectory evaluation/final_paper_qa/new_render
```

Choose a new QA directory. The helper opens only the final DOCX read-only in an
isolated hidden Word instance, exports the PDF, checks the DOCX hash and renders
every page. It refuses an instance containing user documents. Exported PDF
metadata can vary with the renderer; PDF byte reproducibility is not claimed.
Inspect every rendered page after any change before replacing the final artifact.

The empirical bundle has separately reproduced all eleven artifact hashes in a
credential-free, network-blocked clean checkout. To reproduce it offline, set
PYTHONPATH to src and run:

```powershell
python scripts/finalize_main_continuation.py --output reproduced_bundle
```

Do not rerun collection. Do not edit frozen scripts, scientific inputs or raw
evidence to change the manuscript's result. The final PDF has not been submitted;
all named authors must approve the new artifact and submission terms before
upload through the official sprint page.

A clean staged Git snapshot reproduced the DOCX, build manifest and claim map byte-for-byte, with credentials absent and Python networking blocked. All 620 snapshot files remained unchanged. The original reviewed PDF was verified rather than re-exported; no PDF byte-determinism is claimed. Evidence: [clean snapshot record](../../research/checks/final_paper_clean_snapshot.json).
