# Main continuation recovery — 16 November 2026

Status: operational preparation; no new inference. This is AI engineering/review, not completion of H3 or H4.

The user's current request is: “fix the billing holds and rate limit issue, test it, then finish the remaining 52 cells under the same budget. dont change the frozen design or rerun completed cells”. Engineering, testing and eligible continuation are authorized. Releasing unsupported charges, changing the scientific design and resampling remain prohibited.

## Verified state

- 704 planned cells; 652 completed; 52 pending (34 decisions and 18 readbacks).
- 51 pending cells are untouched. `main-2061-readback-MAIN-inline-b` has two failed retryable attempts and may next use attempt 3, within the original maximum of 4.
- `main-2013-decision-HIGH-STAKES-inline-a` is completed with an exhausted missing continuation. It remains closed, as do invalid decisions and all other completed cells.
- The staged allowance remains USD 9 and 3,000 aggregate attempts. At this checkpoint: 1,561 used, 1,439 remaining; known cost USD 0.19176235952; unknown holds USD 1.93872838656; available USD 6.86950925392.
- All 40 holds are unknown settlements, not pending ledger writes. No individual receipt was found for any of them. No hold was released or rewritten.
- The fresh read-only account response reported a non-resetting USD 10 hard key limit and USD 9.795727132 remaining. This aggregate balance is not a receipt for any failed attempt. The browser activity page required sign-in, so authenticated logs were unavailable.

The 40 individual checks and their attempt/reservation mapping are recorded in `checks/main_continuation_billing_review.json`. Original raw observations, scientific freeze, source hashes, historical closed smoke session, and partial analysis bundle remain unchanged.

## Diagnosis

The current stop is the explicitly recorded 40-unknown-charge limit. Ordinary pending-receipt recovery cannot fix it: the ledger has no pending reservations, and all failed attempts lack attributable cost receipts. Request hashes repeat across retries and cannot identify a single billable attempt on their own. The existing staged reconciler also compares known ledger costs directly with original journal costs; later external receipts require supplemental provenance-aware reconciliation, not an unreviewed ledger append.

The rate limiter enforces a sliding 10-per-minute ceiling but allows bursts. Infrastructure retries wait only 1, 2 and 4 seconds, and retained failure events omit Retry-After. The evidence cannot establish whether OpenRouter or its provider imposed each limit. Official OpenRouter documentation recommends honoring Retry-After; an error code 429 may also occur inside an HTTP 200 response. Therefore, HTTP status alone is not evidence of zero billing. Sources: [errors and debugging](https://openrouter.ai/docs/api_reference/errors-and-debugging), [limits](https://openrouter.ai/docs/api_reference/limits).

## Prepared repairs

`scripts/continuation_pacing.py` is an inactive, separately tested operational helper. Its intended behavior is at least 15 seconds between inference POSTs, including retries, re-prompts and continuations, with at least a 60-second cooldown after rate limiting and any longer Retry-After respected. It preserves request bodies and provider settings. It does not modify the frozen limiter, policy, budget or stage gates. Installing the helper into a live continuation requires explicit operational provenance; helper tests alone do not establish a ready live executor.

`scripts/verify_main_continuation.py` independently checks the exact remaining-cell boundary against the retained main files, frozen input hashes and shared control history. It is a read-only proposal verifier, not an inference launcher or permission to bypass the hold stop.

The first full regression run returned **1,716 passed, 1 failed** in 562.34 seconds. `test_lost_final_settlement_line_fails_the_audit` exposed a latent audit gap: the final retained attempt has unknown cost, so removing its settlement changes it from unknown to pending while preserving its full held amount. The old check merged those states and missed the lost event. This failure is retained in `checks/main_continuation_regression.json`.

The repair belongs in the nonfrozen read-only audit: a pending reservation must match a genuinely unfinished journal attempt; a terminal attempt requires its durable settlement. It must not release a hold, change the frozen executor, or reject legitimate unresolved in-flight evidence as though it were a settled charge. Repair and retest evidence will be recorded separately; these utilities remain preparation, not a successful live continuation.

## Concrete billing decision still needed

The recorded authorization states: “Dispatch stops when 40 such holds exist”. It also prohibits weakening safeguards without explicit approval. Continuing while those charges remain unknown would change that specific operational safeguard; it is not billing reconciliation.

The smallest proposed exception is:

> Accept only the exact 40 enumerated existing unknown charges as reviewed, retain their full USD 1.93872838656 reservation against the unchanged USD 9 cap, permit only the exact 52 pending cells, and stop on any additional unknown or pending charge. Do not release or relabel any hold.

This proposal is pending approval. It does not create an allowance, change an authorization file, or enable dispatch. It permits no additional dollar budget and no retries beyond the original four-attempt maximum. An alternative is to obtain attributable provider billing records and reconcile them with separately verified supplemental evidence.

If approved, the operational continuation needs a distinct run/segment ID, explicit amended execution provenance and a separately committed operational freeze. Keep `btl-freeze-v1` and `research/execution_freeze.json` unchanged. The parent observations must remain immutable, and parent/child accounting must be checked exactly once. No runtime substitution may merely suppress existing guard failures.

The worst-case remaining workload is 120 logical phase requests, including optional prescribed re-prompts, and 478 transport attempts after crediting the pending readback's two consumed attempts. This bound is not permission to spend USD 23: the USD 9 ledger and full per-attempt reservation remain controlling. Completion is not guaranteed if rate limits persist or a new unknown charge triggers the proposed stop.

## Research consequences

No threshold, 14-of-16 rule, model/provider, 512-token cap, load, seed, prompt or sample is changed. The accepted MASKED truncation limitation remains; changing its token cap would require repeating smoke and pilot and a new approved freeze. Preserve partial results as historical artifacts. Any eventual final analysis must use the unchanged 10,000 world-level bootstrap resamples and seed 314159 and disclose the collection interruption and any remaining missingness.

Human H3 and H4 remain pending. The current user leads H3, each team member still performs an independent H3 audit, and Araf leads H4. This recovery work does not satisfy those human checks or authorize publication/submission.

## Final preparation validation

The complete retest passed **1,719 tests in 607.41 seconds**. The repaired audit passed **1,625 checks across 528 files**. All six reviewed code/test files match the tested snapshot, all 50 frozen inputs and original empirical/control files are unchanged, and `git diff --check` passed. Evidence: `checks/main_continuation_regression_retest.json`, `checks/main_continuation_audit_retest.json`, `checks/main_continuation_AI_review.json` and `checks/main_continuation_validation.json`. The earlier failed run is preserved.

The offline audit fix is complete. The pacing helper and exact-cell verifier are tested preparation. The live continuation executor and proposed billing exception are not implemented or approved; no new inference or settlement occurred. Main remains 652/704 completed with 52 pending. The current user authorization to finish those cells remains subject to resolving the specific retained 40-hold stop.
