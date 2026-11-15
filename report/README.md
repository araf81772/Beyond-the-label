# Pre-results report and evidence packaging

The manuscript is a **pre-results draft**, with authors **Tonmoy and Araf** and affiliations pending. No real smoke, pilot or main observations exist. The primary effect, interval, sign test, observed regret, readback/control performance and recognition-action gap are unavailable. Oracle references are analytic, and synthetic fixtures are software checks.

`manuscript.md` supplies the scientific text. `official_template.docx` is the immutable export of the official Apart Research template. Its source and hash are recorded in `research/checks/report_preparation_sources.json`; earlier failed public-access attempts remain in the historical verification record. `artifact.md` records template inspection and permitted changes. `scripts/build_report.py` creates the pre-results document; `report_manifest.json` records actual generation and rendering checks. Exports must not be described as submission-ready until empirical evidence, author details and required review are complete.

The supplied design remains byte-preserved in `research/protocol.md`. User-approved NUMERIC amendment A1 and fixed analysis conventions A2 are separate in `research/amendments.md`. The draft includes the required **Limitations and Dual-Use / Ethical Considerations** appendix, explicit no-human-review disclosure, AI-use statement and verified primary references. No H1-H5 review, submission or publication is claimed.

## Offline evidence bundle

From the repository root:

```powershell
$env:PYTHONPATH = 'src'
python -m beyond_label.finalize --planned --output results/planned
```

Planned mode records 704 unexecuted main cells, zero observed infrastructure misses, and null empirical statistics. It produces no simulated result figures or matched trace. It is not a partially completed run.

For a future real main run:

```powershell
python -m beyond_label.finalize --run runs/MAIN_RUN_ID --output results/MAIN_RUN_ID
```

Replace the placeholder with the actual run directory. Finalization validates the five required files and replays raw evidence in a disposable snapshot. It preserves source bytes, enforces the frozen bootstrap plan, and packages derived tables, figures, matched trace, evidence map and artifact hashes. It does not perform inference, create a freeze, submit the paper or mark M6 complete. Partial empirical runs retain their explicit denominators and missingness.

Synthetic validation requires an explicit opt-in and a separate output:

```powershell
python -m beyond_label.finalize --run evaluation/synthetic_main_load2_preresults --output evaluation/synthetic_report_bundle --allow-synthetic
```

The main result section must eventually be replaced using verified trace-derived evidence. The markers `BTL_EMPIRICAL_RESULTS_START` and `BTL_EMPIRICAL_RESULTS_END` delimit the pending section. `claim_to_evidence.csv` distinguishes methods, analytic references, external sources and pending empirical claims; the empirical finalizer generates a separate numeric evidence map. Neither file authorizes unsupported prose or automatic publication.

## Remaining gates

1. Settle the budget and attempt allowance, recheck required account conditions, and complete real smoke and pilot with exact threshold decisions.
2. Create and verify the execution freeze, then collect the frozen main sample.
3. Finalize stored evidence, populate and review the paper, confirm affiliations and actual human participation, regenerate exports and verify every page and claim.

The current ten-attempt ceiling cannot complete the 80 initial smoke cells. Paid calls remain forbidden; the user's promise of a later budget is not authorization to spend now. See `research/offline_completion.md` for the complete handoff.
