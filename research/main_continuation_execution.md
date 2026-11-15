# Approved main continuation

The user explicitly approved retaining the 40 existing full holds, continuing only the 52 pending cells within USD 9 / 3,000 total attempts, and stopping on any new unknown charge. The exact approval and identities are in `main_continuation_approval.json`. This is an operational exception, not a billing receipt or release of funds.

The immutable parent is `runs/staged_main` (652 completed cells). The child is `continuations/staged_main_52_20261116`; its journal starts with the exact parent prefix and appends only the eligible suffix. The pending readback resumes at attempt 3 of 4. Completed/invalid cells and the terminal exhausted HIGH-STAKES continuation remain closed. The original partial analysis stays in `results/staged_main`.

The scientific freeze `btl-freeze-v1` and all 50 frozen inputs remain unchanged. The separate operational freeze `research/main_continuation_operational_freeze.json` binds approved source, tests and approval to tag `btl-main52-operations-v1`. The child manifest clearly separates the inherited scientific replay contract from the effective operational exception. Audit, status and finalization count inherited main data once.

Only `scripts/execute_main_continuation.py` may dispatch this continuation, from `C:/Users/tonmo/CodexRuns/beyond-the-label-v1-main-20261116`. The new path checks the immutable parent and control prefixes, original scientific gates, both source/tag proofs, current route/account evidence, exact canonical transport, and shared limits. All original 40 reservation identities and amounts must remain intact. Every additional unresolved charge stops the next attempt. Extra pacing enforces at least 15 seconds between inference POSTs and at least 60 seconds after rate limiting, honoring longer Retry-After.

Commands, after source/tests are committed and the operational freeze/tag is prepared and delivered:

```powershell
python scripts/execute_main_continuation.py check-ready
python scripts/execute_main_continuation.py execute
python scripts/sync_execution_status.py
python scripts/verify_audit.py
```

Preparation, source binding, fresh readiness and actual execution outcomes must be recorded before claiming completion. `check-ready` does not authorize new scope or spending. Do not run the old staged executor to evade its original 40-hold stop. Do not repeat a cell or reset a retry count to recover from a stop.

After all 704 cells are terminal, `python scripts/finalize_main_continuation.py` creates a separately named bundle in `results/staged_main_complete` with frozen analysis (10,000 bootstrap resamples, seed 314159), actual continuation provenance and guarded reproduction commands. It does not remove remaining missing outcomes, invent receipts, complete human H3/H4, or authorize submission.

Current checkpoint: implementation validated (1,771 tests and 1,664 audit checks passed); pending committed operational freeze/tag and fresh readiness. No continuation inference has occurred yet. See `checks/main52_preparation_validation.json`.
