# Completed main continuation

All 52 approved remaining cells completed: the composite main contains 704/704 terminal cells and 704 observed first decisions/readbacks. The continuation added 84 accepted calls, no infrastructure failures and no new unknown charges. The original 652 completed rows, five parent files, journal prefix, scientific freeze and 50 scientific inputs remain unchanged. The interrupted readback resumed at attempt 3; the historically exhausted HIGH-STAKES continuation stayed closed.

The operational source is cc7c81dbfda50aefada5c4e62f1ffd8702601939, bound by btl-main52-operations-v1. The scientific freeze remains btl-freeze-v1. Execution ran from the designated unsynced clone from 2026-11-15 23:02:06 to 23:25:06 UTC. The approved exception retained the exact original 40 holds and would stop further dispatch on any new unknown charge. No receipts, refunds, new allowance or completed-cell resampling were invented.

| Budget item | USD |
|---|---:|
| Incremental known continuation cost | 0.01057185696 |
| Total known staged cost | 0.20233421648 |
| Exact 40 historical holds retained | 1.93872838656 |
| Available under unchanged USD 9 staged cap | 6.85893739696 |

There are 1,645 aggregate staged attempts out of 3,000. Known main-only cost is USD 0.13275084448; actual total main/staged costs remain unknown because the historical holds are not receipts. The older closed USD 1 testing session remains separate and unchanged. No extra budget was needed for this continuation.

## Verification and evidence

The implementation passed 1,771 tests before dispatch and the pre-dispatch audit passed 1,664 checks. Fresh GET-only account/route checks passed. Independent AI accounting review verified all 1,645 journal/reservation pairs, original holds, control prefixes, frozen inputs and frozen journal replay with no discrepancies.

The primary agent separately checked all 84 new raw replies against saved parser fields and wire settings, all 52 new rows, 18 readbacks, 34 first decisions, 30 continuations, 136 exact Fraction expected-loss/oracle/regret fields and 33 available realised outcomes. Every original completed row is identical. Per-cell checks are in [the AI trace review](checks/main52_trace_oracle_AI_review.json); no discrepancy was found. Two additional post-run reviewers stopped at service usage limits, so their unfinished reviews are not credited. AI work does not complete human H3 or H4.

Pacing is bound to the tested source: at least 15 seconds between inference POSTs and at least 60 seconds after rate limiting, honoring longer Retry-After. No rate limiting occurred in this continuation. The journal lacks per-POST wall timestamps, so this report does not claim independently measured spacing for every POST.

The [completed bundle](../results/staged_main_complete/bundle_manifest.json) is separate from the retained historical partial bundle. Its 11 artifact hashes and both rendered figures were checked. Reproduce offline with:

    python scripts/finalize_main_continuation.py --output BUNDLE_OUTPUT

Clean-code reproduction passed from committed source 0501b95c1f6d2a142c589a72627e68979ac22fbd: all 11 artifact hashes, five source hashes, completeness, bootstrap and continuation provenance matched. Credentials were absent, Python networking was blocked, and the clone had no tracked changes. This used the same installed dependencies, not a fresh dependency installation. The post-run audit passed 1,180 checks across 569 files; a separate known-credential-value scan checked 570 tracked files with no findings. See [reproduction evidence](checks/main52_clean_clone_reproduction.json). Human review and submission are not claimed.

## Scientific result and limits

The frozen interpretation is **NO_GAP_HERE_UNDER_THESE_CONDITIONS**. Separate-layout D is 0.9375, with 95% world-bootstrap interval [0.875, 0.984375]; inline D is 0.921875 [0.859375, 0.984375]. The inline-minus-separate interaction is -0.015625 [-0.109375, 0.078125]. All use the unchanged 10,000 world bootstrap resamples and seed 314159 across 64 complete worlds.

Readback was correct in 256/256 branches. NUMERIC optimality was 32/32, HIGH-FEE 63/64, and HIGH-STAKES 52/64. MAIN fully correct twin pairs were 57/64 separate and 55/64 inline. This supports a bounded result about this model, task and frozen setup. Separate readback branches do not demonstrate that recognition caused action; nonsignificance is not proof of no layout effect.

Completed collection does not mean every final outcome is available. The 448 decision rows retain two invalid first actions, 16 invalid continuations (second-inspection violations) and one historical infrastructure-missing continuation. There are 429 realised outcomes. Do not describe conditional 100% correctness among valid post-inspection commits as unconditional follow-through.

MASKED first replies truncated in 21/32 cells. This accepted limitation remains material: actions often follow the fixed re-prompt, so withholding scope cannot be separated cleanly from the changed realized interaction. The cap remains 512 tokens. Changing it requires repeating smoke and pilot, plus load-8 smoke if selected; after freeze it also requires an approved deviation, new run ID and new freeze.

D3 thresholds, the 14-of-16 load-selection rule and the 12-of-16 floor remain unchanged. Late H1 completion, post-pilot D3 acceptance and late D4 assignments remain disclosed; successful execution does not erase those deviations.

## Remaining submission work

M5 collection is complete. M6 remains pending: each human team member must complete H3 (the current user leads; 30 action-stratified traces using seed 161803 plus every INVALID/REFUSED trace), and Araf leads H4 checking final-paper numbers against file/command evidence. H1/H2/H5 remain user-attested work in their documented scope. New or changed citations require review.

The defensible paper centers the complete, reproducible bounded result and the payoff-sensitive failures, with transparent truncation and operational limitations. Final writing, confirmed affiliations, human checks and final-paper reproduction remain. No publication or submission was performed. No further model calls are needed to finish the approved 52-cell scope.
