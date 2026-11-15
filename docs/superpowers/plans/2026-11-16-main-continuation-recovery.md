# Main continuation recovery implementation plan

> **For agentic workers:** Use independent implementation and review for the two isolated utilities below; root integrates and runs repository validation. Do not dispatch inference from these utilities.

**Goal:** Prepare and verify an exact 52-cell recovery without changing the scientific freeze, releasing unknown costs, or resampling completed cells.

**Architecture:** Preserve the existing 50 frozen inputs and all empirical records. Add a read-only continuation verifier and an inactive HTTPX pacing helper outside the frozen input set. The billing decision is a separate explicit operational decision: receipts are currently absent, and the existing 40-hold stop remains effective.

**Tech stack:** Python, pytest, standard library, existing HTTPX dependency.

**Spec:** Current user request; `research/staged_authorization.json`; `research/execution_freeze.json`; retained main journal; `AGENTS.md`.

## Global constraints

- USD 9 staged ledger and 3,000 aggregate attempts remain unchanged.
- Retain all 40 unknown charges at USD 1.93872838656; no inferred zero-cost settlement.
- Preserve the original scientific freeze and 50 input hashes, raw evidence, closed smoke session, and prior partial analysis bundle.
- Exactly 652 completed cells remain closed. Only the 52 remaining cells in frozen order are eligible.
- `main-2061-readback-MAIN-inline-b` resumes at infrastructure attempt 3, maximum 4; `main-2013-decision-HIGH-STAKES-inline-a` is terminal and stays closed.
- Preserve prompts, model/provider, output cap 512, sampling settings, design thresholds, seeds, and outgoing payload bytes.
- No inference until the billing stop has a valid resolution and operational provenance is reviewed. A pacing helper alone is not an execution authorization or gate override.

## Review focus

- All inference POSTs, including retries, re-prompts, and continuations, must pass the pacing hook.
- HTTP 200 responses containing error code 429 require the same cooldown as HTTP 429.
- Retry-After must accept seconds and HTTP dates without shortening the minimum cooldown.
- Duplicate/stale/mutated histories must fail closed; a completed invalid decision is still completed.
- Aggregate account balance is not an attributable receipt; no ledger amount is changed by these tools.

## Task 1: Pacing preparation

Files: `scripts/continuation_pacing.py`, `tests/test_continuation_pacing.py`.

- [x] Write and run failing behavioral tests using HTTPX MockTransport and controlled clocks.
- [x] Implement at least 15 seconds between inference POST starts, including a conservative initial wait, and minimum 60 seconds after rate limiting; honor longer Retry-After.
- [x] Provide an explicit, scoped client-factory context; restore the original factory on exit. Do not patch policy, counters, reconciliation, or stage validation.
- [x] Verify byte-identical payloads, unchanged pins, unpaced GETs, retries, exception cleanup, and no implicit execution.

## Task 2: Exact resume verification

Files: `scripts/verify_main_continuation.py`, `tests/test_main_continuation.py`.

- [x] Write and run failing tests for stale or modified histories and completed-cell exclusion.
- [x] Bind the five stopped-main files, original freeze, all 50 frozen inputs, and control history prefixes.
- [x] Report the exact pending list, next retry number, terminal exclusion, budget and attempt state; do not change files unless an explicit report output is requested.
- [x] Validate against retained evidence and isolated synthetic fixtures.

## Additional repair found by full regression

Files: `scripts/verify_audit.py`, `tests/test_staged_ledger_audit.py`.

- [x] Reproduce missing final unknown settlement escaping the old audit.
- [x] Require pending reservations to match unfinished journal attempts by request hash and multiplicity, preserving legitimate crash windows.
- [x] Run five focused tests and independent AI review; preserve all frozen inputs and actual ledgers.
- [x] Rerun the complete suite and audit; preserve the original failure record.

## Task 3: Billing decision and integration

Files: `research/main_continuation_recovery.md`, check records, `research/decisions.md`, `research/milestones.json`.

- [x] Record unavailable per-attempt receipts and authenticated-log access status accurately.
- [x] Preserve the stop-at-40 policy. Present a concrete alternative: accept only the enumerated existing 40 full holds, retain them against USD 9, and stop on any additional unknown charge. This is an operational exception, not a refund or a receipt.
- [ ] Obtain explicit approval for that exception or attributable receipts before implementing a live billing-policy change. The existing authorization specifically prohibits weakening safeguards without explicit approval.
- [ ] If approved, implement and test a separately versioned operational continuation with its own ID and provenance/freeze, retaining the original scientific freeze and raw segment. Do not disguise runtime overrides as unchanged execution.
- [ ] Run focused tests, `python -m pytest -q`, `python scripts/verify_audit.py`, and `git diff --check`; independent AI review; review intended diff/claims/secrets and commit/push to verified v1.
- [ ] Before inference: exact remaining-cell verification, fresh account/route evidence, reviewed operational source and provenance. After inference: preserve partial bundle and create a separately named final bundle, verify all original prefixes, report remaining missingness honestly.
