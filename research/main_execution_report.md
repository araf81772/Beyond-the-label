# Main execution and research-readiness report

Recorded 16 November 2026 (Australia/Sydney). This is an evidence report and AI review, not a final manuscript, human sign-off or submission.

**Main is incomplete and further dispatch is blocked.** After the operational launch gates passed, the authorized frozen load-8 run completed 652 of 704 cells. Repeated HTTP 429 failures reached the unchanged limit of 40 unknown-cost holds. The executor stopped without a relaunch, limit increase or scientific-input change. The frozen analysis returns **INCONCLUSIVE_WITH_INFRASTRUCTURE_MISSINGNESS**.

## Execution and preservation

The canonical command ran from 01:05 to 03:13 AEDT on 16 November, at collection source `d007585cff100f4fc6ce61c2b61452d830e3ffe9`, in the unsynced execution clone. The scientific freeze remains `6f8f94b3542980f65ba08f56aa3a12bf12c9e41d`, tag `btl-freeze-v1`, verified on origin. The earlier failed launcher stopped before inference; its diagnostic and correction remain recorded.

| Evidence unit | Retained result |
|---|---:|
| Planned cells | 704 |
| Observed first actions/readbacks and completed cells | 652 |
| Decision observations | 414/448 |
| Readbacks | 238/256 |
| Untouched cells | 51 |
| Attempted, unresolved readback | 1 |
| Journaled attempts / accepted responses | 1,036 / 996 |
| HTTP 429 failures / infrastructure retry starts | 40 / 38 |
| Prescribed re-prompts | 19 |
| Invalid first actions / invalid continuations | 2 / 15 |
| Infrastructure-missing continuation | 1 |

The unresolved readback is `main-2061-readback-MAIN-inline-b`, with two failed attempts and no accepted reply. The terminal `main-2013-decision-HIGH-STAKES-inline-a` retains its observed optimal first action; its continuation exhausted four attempts and has no final loss. Do not retry that terminal continuation or resample any observed/invalid decision.

All 1,036 attempt starts have recorded outcomes, with no in-flight attempt left unmatched. Forty failures affected 30 logical requests; 28 requests recovered using identical request hashes. The records identify HTTP/API 429 but do not establish which router/upstream limit was exceeded. Retry recovery does not prove a failed attempt cost zero.

Sources: [command outcome](checks/main_execution_command_canonical.json), [raw run](../runs/staged_main/analysis_manifest.json), [independent AI review](checks/main_postrun_review.json), [bundle completeness](../results/staged_main/bundle_manifest.json).

## Budget

| Accounting scope | USD |
|---|---:|
| Main known provider-reported charges | 0.12217898752 |
| Total main charges | Unknown |
| Staged cumulative known settled charges | 0.19176235952 |
| Staged retained unknown-cost holds | 1.93872838656 |
| Staged allowance still available | 6.86950925392 |

The staged session consumed 1,561 of 3,000 attempts. Available dollars and 1,439 remaining attempts do not override the 40-hold guard. Additional money alone does not unblock execution. The earlier closed USD 1 session, its two holds and all historical observations remain separate and unchanged. [Ledger audit](checks/main_postrun_audit.json).

## Validation and independent review

Before launch, the unsynced clone passed 1,680 offline tests. The invocation-only correction then passed 121 focused retests and fresh readiness. No frozen code, settings, threshold or token cap changed.

After stopping, 105 preservation checks verified all 50 frozen inputs, the freeze/plan, 15 gate artifacts, and 38 historical whole-file or append-only-prefix comparisons. The offline audit passed 1,538 checks across 499 files. Finalization replayed the raw traces and verified the freeze, using 10,000 world bootstrap resamples with seed 314159. All ten generated artifact hashes and the five unchanged main source hashes were checked. Both figures were visually reviewed by AI; their planned denominators and missing/pending bars are visible. The final documentation audit passed 1,583 checks across 514 files. A clean-code clone of committed snapshot a900c1b then reproduced all ten artifacts byte-for-byte, including identical source hashes, completeness and bootstrap settings; credentials were removed and Python socket access blocked. This reused host dependencies, not a fresh dependency installation. [Reproduction evidence](checks/main_clean_clone_reproduction_retest.json).

An independent standard-library/Fraction audit checked all 996 accepted responses against parsed replies, 414 first actions, 1,652 numeric oracle/score values plus four required blanks, 238 readbacks, 325 returned continuation actions and 396 realised losses. It found no discrepancy. The 15 invalid continuations are genuine second-inspection attempts: 11 HIGH-STAKES, three MASKED and one MAIN. These reviews are AI evidence, not H3.

The first offline finalizer command lacked the documented `PYTHONPATH=src`. Import discovery reproduced that environment failure and passed with the documented setting; corrected finalization passed. Both outcomes are retained in [finalization evidence](checks/main_finalization.json). Raw source files were not repaired.

## Partial estimates and their limits

| Layout | Complete pairs | Observed-pair D | Complete-pair 95% bootstrap interval | All-64-world missingness bounds |
|---|---:|---:|---|---|
| Separate | 53/64 | 0.9623 | [0.9057, 1.0000] | [0.7500, 0.9375] |
| Inline | 53/64 | 0.9057 | [0.8302, 0.9811] | [0.7500, 0.9219] |

The last column contains identification bounds, not confidence intervals. The observed-only no-gap flag is true, but missing required evidence prevents an unconditional conclusion under the frozen rule. Both full-plan lower bounds fall below 0.80. HIGH-STAKES optimality is 49/60 observed; the full-plan success bound is 49/64 to 53/64, which crosses the 80% threshold. The layout interaction uses 45 shared complete worlds: -0.0667, interval [-0.1556, 0.0222]. A claim that inline layout helps is unsupported.

Readback accuracy is 238/238 observed, with 18 planned probes missing. The 310 valid post-inspection commits followed the inspected state, but that denominator excludes 15 invalid and one missing continuation. Do not present unconditional perfect follow-through. Realised loss and analytic expected-loss references are different quantities.

Every estimate is from the [partial main analysis](../results/staged_main/analysis/analysis.json), with [claim evidence](../results/staged_main/analysis/claim_evidence.csv). Smoke is pipeline evidence; pilot data selected load and are not pooled with main.

## Original readiness questions

| Item | Evidence and conclusion |
|---|---|
| H2/P2 | Earlier independent AI review checked all 160 pilot cells and 267 raw responses, with zero parser/scoring discrepancies. Four preliminary MASKED-loss alerts were reviewer-assumption errors resolved by the recorded hidden-assignment parity. Three genuinely suboptimal first actions and eight invalid continuations were retained. The full per-trace matrix was recorded in the earlier chat; repository summaries remain in the human-verification record. Both humans' completion is user-attested, not witnessed by AI. |
| H1 | Independent AI arithmetic verified nine oracle-table rows, all eight pilot worlds, 128 decision rows and 512 numeric fields, including raw dispositions for 35 commits. Zero numerical discrepancies. Human completion is user-attested and late; the before-pilot timing deviation remains outstanding as a disclosed methodological deviation, not an unfinished arithmetic claim. |
| D3 | Existing Section 9 thresholds, the 14-of-16 MAIN ceiling and 12-of-16 NUMERIC floor are accepted unchanged. Pilot 15/16 MAIN pairs and 15/16 NUMERIC optimal selected load-8. Acceptance was recorded after pilot exposure; do not describe it as pre-pilot sign-off. No post-freeze threshold change is permitted. |
| D4 | The current user coordinates H3; Araf leads H4. Each team member must independently perform H3. H1/H2/H5 are user-attested complete for the current user and Araf; H3/H4 are pending. Assignment after freeze is a disclosed timing deviation. No initials or completion are invented. |
| MASKED | Truncation is an accepted limitation. Pilot first replies truncated in 14/16 cells; retained main first replies truncated in 19/30 observed cells (10/15 separate, 9/15 inline). Each used the fixed re-prompt. Scope withholding and differing realised interactions are therefore not isolated. The 512-token cap remains unchanged. Changing it requires repeating smoke and pilot, load-8 smoke if selected, and after freeze explicit approval, a new run ID and a new freeze. |

H1 formulas independently checked were `L_C=(1-q1)P1+(1-q2)P2`, `L_I1=f+(1-q2)P2`, and `L_I2=f+(1-q1)P1`. The accepted pilot oracle values, MASKED posterior treatment and worst-valid sensitivity are summarized in [human_verification.json](human_verification.json) and supported by [oracle_table.csv](../evaluation/oracle_table.csv) and the immutable protocol.

## What remains and the strongest submission path

1. **Execution blocker:** preserve the 40 holds and obtain attributable billing evidence plus a validated reconciliation path, or an explicit reviewed amendment with any required new freeze/run provenance. Do not relaunch while blocked, infer zero charges from account totals, reset the ledger, or expand limits silently. No implemented reconciliation or approved amendment is claimed here.
2. **Human H3:** each team member audits 30 action-stratified traces with seed 161803 plus every INVALID/REFUSED trace, with real initials. The precise stratum allocation remains unspecified; document the operational choice before drawing the sample. The invalid set must include continuation invalids. The matched illustrative trace is not this audit sample.
3. **Human H4:** Araf verifies every final-paper number against its evidence file and reproduction command. The generated map is a starting point; costs, pilot values and individual trace claims require explicit mappings if used.
4. **Paper:** distinguish complete-pair estimates from full-plan bounds; report the stopped collection and late H1/D3/D4 deviations, MASKED truncation and invalid continuations. Confirm affiliations and check any new/changed citations. Preserve the earlier pre-results manuscript as historical.
5. **Reproduction and submission:** the partial bundle passed offline clean-code reproduction. Final-paper reproduction, rendered-PDF inspection and submission authorization remain pending. M5 and M6 remain incomplete.

The strongest defensible current presentation is a narrow, clearly labelled partial-main result: observed scope-sensitive allocation, transparent missingness and control limitations, and the prespecified inconclusive conclusion. Do not spend merely to seek a more favorable result or promise a win.

The official deadline is 16 November 2026, 22:59 AEDT. Use the official-template PDF, at most eight body pages, a 150-250-word abstract, real author affiliations, the required limitations/dual-use appendix and an accurate AI-use statement. The rubric scores impact/innovation, execution, and clarity; it does not publish an automatic score ceiling for unfinished work. [Official rules](https://apartresearch.com/sprints/ai-x-epistemics-research-sprint-2026-11-13-to-2026-11-15), [template](https://docs.google.com/document/d/17b3JWki-ZkaqdmqGI5d0gof-HwlGuWU9Mc1_klNZXKs/edit). No publication or submission was performed.
