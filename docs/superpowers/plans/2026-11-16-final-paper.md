# Final submission paper implementation plan

Goal: produce the complete empirical paper in the official template, preserving the frozen design, evidence and historical reports.

Architecture: new report/final manuscript, deterministic template-derived DOCX builder, numeric claim map, rendered PDF and verification manifest. Use completed704-cell evidence and independently rechecked sources. Never invoke inference or edit scientific/operational frozen inputs.

Specification: research/protocol.md Sections9,10,16; official sprint guidelines; user request to recheck and write the final paper.

- [x] Recheck independent statistics, all raw classifications/outcomes, frozen provenance, rules and existing references.
- [x] Record new human completion only as user attestation in a separate file; retain missing worksheet and final-artifact scope honestly.
- [x] Confirm author affiliations and prior-work disclosure; do not invent either.
- [x] Write final manuscript with exact methods, bounded no-gap interpretation, matched trace, oracle and empirical figures/tables; map each numeric claim to file/command evidence.
- [x] Build new DOCX from retained template without altering its styles/fonts/page geometry; retain official branding/footnote and accurately disclose AI drafting.
- [x] Render using packaged renderer if available; otherwise document Windows blocker and use existing isolated hidden Word read-only export. Inspect every page, ensure abstract150-250words and body<=8pages, repair and rerender.
- [x] Verify deterministic document/evidence build, unchanged frozen artifacts, final audit and diff; update current status and deliver through verifiedv1. No submission or publication.

Delivery: final-paper artifact commit f50deef507651d8850a5c9d011602cea7d775e99 pushed to verified origin/v1. All 1,771 tests, 1,899 audit checks, 104 paper claims, deterministic clean-snapshot reproduction and full visual QA passed. Final author review and submission are separate; neither is claimed complete.
