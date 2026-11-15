# M4 and M5 readiness: remaining paid-execution work

This is a code/protocol readiness review with a verified partial smoke outcome,
not a passed milestone or a new execution authorization. The user authorized
only the **79 untouched smoke cells** under the existing shared
**USD 1 / 200-attempt** limits, including earlier attempts and the retained cost
hold, then stop and report before pilot or main. The continuation has now
**stopped before retry with `paid_cost_reconciliation_required`**. The
[execution record](checks/smoke79_execution.json) records exit code 2 at
2026-11-15 03:36:21 UTC. Pilot and main remain unstarted; smoke has not passed.

The authoritative [protocol](protocol.md) remains unchanged. The retained
[DeepSeek failure](deepseek_smoke.md), original GPT failure and both versions of
their raw artifacts remain evidence. The prepared continuation retains the
terminal missing readback and dispatches only the other 79 cells; it does not
resample or retrospectively accept that rejected reply.

## Verified partial outcome and immediate blocker

An independent read-only AI review reconciled the v3 trace, scores, usage,
attempt journal and budget journal. It found:

| Measure | Retained evidence |
| --- | --- |
| New attempts / accepted successful replies | 94 / 93 |
| New infrastructure failures | One continuation timeout |
| New completed cells | 53 |
| Observed first actions or readbacks | 54 |
| Retained terminal missing cells | 1 |
| Pending cells | 26: 25 untouched and one with an observed first action but an incomplete continuation |
| Missing first actions or readbacks | 26: the 25 untouched cells and the retained terminal readback |
| Re-prompts / continuation attempts / infrastructure retries | 3 / 37 / 0 |
| Invalid first actions | 0 |
| Aggregate attempts consumed / remaining | 96 / 104 |
| Known provider-reported cost, new v3 segment | USD 0.01245631104 |
| Known settled cost across all three segments | USD 0.01251132320 |
| Historical unknown-cost hold | USD 0.44084208 |
| New timeout's unknown-cost hold | USD 0.048468209664 |
| Total retained holds | USD 0.489310289664 |
| Available under the shared smoke cap | USD 0.498178387136 |

The timeout occurred during the continuation of
`smoke-1102-decision-HIGH-STAKES-inline-b`. Its failure record is retryable but
contains no response, usage or request-ID billing receipt. The existing
conservative review covers only the original GPT HTTP404, so it does not cover
this new unknown charge. The accounting guard correctly stopped before any
retry despite the remaining dollars and attempts. Further dispatch requires
an evidence-backed resolution of this exact charge under the accounting rules;
do not assume it was free, release its hold, extend the old exception silently,
reset the session or resample the observed first action.

All 80 score IDs are unique, and no v3 event targets the retained terminal cell.
The two historical segments' ten artifact hashes still match their records;
all 48 collection input hashes match source
`eebba9de7a9923d2a81d17f7631d41371a35ef5e`. Budget and attempt hash chains verify,
their historical prefixes remain intact, and raw known/unknown request-cost
multisets match the ledger. All 94 cumulative known-cost attempts report
`is_byok:false`; two attempts have unknown costs. Costs above were independently
summed with decimal arithmetic, without rewriting stored artifacts.

Retained holds are conservative accounting bounds, not actual charges.
Aggregate actual cost remains incomplete. These observations are smoke
engineering evidence excluded from main results; they do not supply a main
effect, confidence interval or a passed M4 gate. The implementation and
authorization gaps below remain unresolved.

## What is reusable

The deterministic worlds, oracle, rendering, sandbox, scoring, manifest
generation, retry/re-prompt handling, journal recovery and paired analysis are
implemented and have offline test coverage. The main manifest retains all
64 worlds and 704 initial cells: 256 MAIN, 256 READBACK, 64 HIGH-FEE,
64 HIGH-STAKES, 32 MASKED and 32 NUMERIC. It permits up to 448 continuations,
giving 1,152 planned calls before additional retries or permitted re-prompts.

The offline analysis implements whole-world pairing, 10,000 bootstrap resamples
with seed 314159, the sign test, controls and missingness. Synthetic rehearsals
exercise this machinery and are excluded from empirical results. These are
reusable implementation components; they do not establish a working paid
pilot-to-freeze-to-main execution path, actual smoke acceptance or main results.

## Verified implementation gaps

| Area | Current code behavior | Smallest necessary engineering change |
| --- | --- | --- |
| Paid stage execution | `paid_live.py:run_paid_smoke`, `gates.py:require_paid_smoke_configuration` and `run.py` restrict paid execution to the canonical smoke output and current smoke authorization. `live.py` is free-only. | Add an explicitly authorized paid-stage path for pilot, any required load-8 smoke, and frozen main execution. Keep the present smoke authorization narrow and preserve its canonical history. |
| Stage and total limits | `CappedPaidAttempts`, the live transport validator and paid history reconciliation enforce the fixed USD 1 / 200 smoke allowance. They do not implement separately approved paid pilot/main allowances under a cumulative total. | Add durable, reconciled stage and total guards that include all relevant prior charges and holds, count every attempted request, and stop at either limit. Do not reset, refund, overwrite or relocate the existing session to acquire allowance. |
| Paid pilot summaries | `pilot.py:summarize_pilot` explicitly requires free-only settings for empirical pilot evidence. | Validate paid transport/source provenance and accounting, then reuse the existing exact threshold calculations and denominators. |
| Paid freeze evidence | `freeze.py:_verified_run` explicitly requires free-only settings, complete zero-cost receipts and zero nonzero-cost attempts. | Add paid evidence validation that distinguishes provider-reported costs, retained unknown holds and accounting failures. Never convert unknown costs into zero or silently bypass an accounting guard. |
| Source transitions | Freeze currently requires every gate run's input hashes to equal the current full input set. `_inputs()` includes all source modules and all YAML configurations. | Record and verify any approved pre-freeze transition between collection code/configuration and the final frozen inputs. Preserve each collection version and the scientific inputs; never rewrite old manifests to make their hashes match. |
| Main configurations | `configs/pilot.yaml` and `configs/main.yaml` are disabled templates with unset model and budget; main load is unset. | Prepare concrete stage settings after the relevant authorization and pilot decisions. Keep dispatch disabled until required evidence exists. |
| Main reproduction | `analyze_run` replays with current code. `replay_history.py` reconstructs source and the selected run, but does not currently reconstruct the frozen gate artifacts, main-plan file and Git tag evidence needed by main freeze verification. | Verify offline reproduction from a complete frozen checkout or build a complete provenance-checked reproduction bundle. Preserve raw artifacts and compare regenerated outputs in temporary locations. |

The generic paid branch in `gates.py:require_real_execution` also expects a
positive `provider_rate_limit`; this is not a working alternate paid main path.
The current paid profile honestly records upstream rate guarantees as
unpublished and uses an operator throttle. Future stage support must retain
that distinction instead of inventing an upstream guarantee.

## Unresolved smoke acceptance mismatch

Protocol Section 5 describes the four-world smoke as **“pipeline check only,
never analysed.”** Section 8 requires an additional four-world load-8 smoke
when selected, to confirm the pipeline. The source does not specify the
implementation's exact 80/80 nonmissing smoke criterion.

In contrast, `freeze.py:_verified_run` requires every planned smoke cell to be
completed with no first-action/readback missingness. The current continuation
deliberately preserves one terminal missing readback. Even if all 79 untouched
cells subsequently succeed, that stricter implementation gate will still fail.
This is a known unresolved code/design mismatch, not permission to discard the
failure or relax the gate during the running smoke.

Before freeze engineering is finalized, an explicit, recorded acceptance
decision is needed: define evidence that establishes the design's pipeline
check while retaining all missingness, or obtain authorization for a separate
diagnostic run if the stronger requirement is retained. Any implementation
change must preserve the terminal classification, historical raw bytes and
cost/attempt history. No such gate change is made or authorized by this review.

## Required M4 sequence before M5 execution

1. Finish the currently authorized continuation or preserve its exact partial
   sample if a guard stops it. Reconcile traces, scores, usage, immutable
   historical artifacts and cumulative limits. Report the smoke outcome and
   stop before pilot or main.
2. Complete the scoped offline paid-stage and freeze work above. Develop it
   against a separately recorded source version so it does not invalidate or
   silently replace the prepared/running smoke source. Bind any later source
   transition explicitly before using its gate evidence.
3. Obtain authorization for any next paid stage, including its spending and
   attempt limits. Existing testing authorization and account credits do not
   themselves authorize pilot or main. No budget decision is requested by this
   document. The smoke's 200-attempt allowance cannot cover the main manifest's
   704 initial cells.
4. Run the full eight-world load-2 pilot, seeds 1000–1007, with 160 initial cells
   and up to 128 continuations. Preserve every outcome and record actual usage.
   At least 14 fully correct MAIN pairs out of 16 selects load-8; otherwise
   select load-2. Fewer than 12 optimal NUMERIC decisions out of 16 requires the
   specified model change and repeated pilot, with each attempt documented.
5. If load-8 is selected, perform the required four-world load-8 pipeline smoke
   under explicit authorization. Record actual human oracle/trace checks where
   available and disclose missing participation; AI checks cannot supply human
   initials or reviews.
6. Finalize the selected main settings and unchanged scientific analysis plan;
   verify gate evidence, committed hashes, complete main manifest and retry
   rules. Create and verify the freeze commit, timestamped record and tag before
   any main call. Record tag delivery. Material changes after that freeze require
   the prescribed approval, deviation record, new run ID and new freeze.

The source budget rule uses measured pilot usage to project main cost and sets
the key limit relative to that projection. It must be reconciled with the user's
eventual authorized caps; it is neither a price quote nor permission to increase
the current hard limit. Main execution remains blocked until authorization,
paid-stage implementation and verified M4 evidence are all present.

## Offline acceptance work for the next implementation

Extend the existing `test_empirical_pilot.py`, `test_freeze.py`,
`test_execution_audit.py` and paid accounting tests. Add a dedicated paid-stage
integration test covering an explicitly synthetic/mocked pilot, exact load/floor
decisions, freeze verification, the complete main manifest, interruption/resume,
offline scoring and analysis, and reproduction without a provider call.

The tests must reject unapproved stages, alternate output directories, changed
model/provider pins, missing or exhausted caps, new unknown charges, changed
frozen inputs/tags, duplicate completed cells, retained-cell resampling, and
synthetic evidence offered as empirical gate evidence. Costs must reconcile
across historical and current stages without weakening the existing smoke
guards. Load-8 selection and model-floor repetition need their own gate tests.

No new stage tests have been run or claimed by this review. Existing offline
passes remain tied to their recorded source versions. Passing this future test
package would establish engineering readiness; actual pilot evidence, final
authorization and the execution freeze would still be required before M5.

## Completed post-run verification

The full offline suite passed **1634tests in421.51s**; the evidence audit passed1383checks. All5v3files replay byte-for-byte, all48collection inputs and10priorrunfiles remain unchanged, and accounting prefixes are preserved. See [suite](checks/smoke79_suite.json), [audit](checks/smoke79_audit.json) and [replay/accounting](checks/smoke79_verification.json). No additional model/account requests were made during validation. These results do not pass the incomplete M4gates.

For the immediate billing blocker, the documented [generation lookup](https://openrouter.ai/docs/api/api-reference/generations/get-request-&-usage-metadata-for-a-generation) requires anID, which the timeout did not return. [OpenRouter Logs](https://openrouter.ai/docs/guides/features/logs) exposes generationIDs and cost details. Recover a uniquely matched provider record for the timed-out continuation (15November2026, approximately14:35–14:36AEDT) or obtain an explicitly reviewed conservative-coverage policy; keep the reservation and rawtrace unchanged until reconciliation is validated. No billing receipt or zero charge has been inferred.

The current paid-history validator also compares ledger charges with raw-outcome receipts. A later provider receipt needs a provenance-aware reconciliation path; changing the ledger alone would fail validation. Do not rewrite the recorded timeout or turn an unknown charge into zero. This implementation gap is separate from the ability to locate billing evidence. Final staged audit:1395checks;57input/artifact/control hashes verified.
