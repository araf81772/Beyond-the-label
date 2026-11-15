# Beyond the Label: research rules

## Authority and scope

Follow the user's current instructions. `research/protocol.md` is a byte-preserved copy of the supplied authoritative `final_design.txt`; `research/source_manifest.json` records its hash. Record conflicts and unresolved details in `research/decisions.md`. Do not silently substitute a prior study or change design numbers. The current user instruction authorizes USD 10 total testing expenditure on GPT-4.1 mini via OpenRouter/OpenAI, but only one smoke run may execute now, stopping at USD 1 or 200 aggregate attempts. Stop and report before pilot or main. Continue test → fix → test → commit → push cycles. Git delivery to the verified remote is authorized. The explicit NUMERIC amendment is in `research/amendments.md`.

The design's “frozen for build” header is not an execution freeze. A validated smoke/pilot, freeze commit, tag, and hashes are still required before any main call. After an execution freeze, material changes require explicit approval, a deviation record, a new run ID, and a new freeze.

## Roles and evidence

Codex performs engineering, execution, and machine checks. Independent agent review must be labelled AI review. Claude has no assigned or completed role in this checkout; use it only if subsequently authorized. Neither agent substitutes for the human checks in design Section 10. Record real participants and never invent initials, participation, results, costs, citations, or completed checks.

## Execution

- Preserve existing user changes. Review intended files before each milestone commit.
- Keep smoke, pilot, main, synthetic test data, analytic oracle references, and missing observations distinguishable.
- Keep hidden states, random draws, answer keys, and research-only oracle values out of model-visible material. NUMERIC intentionally supplies only its specified first-action losses; document this narrow exception.
- Use one pinned model and named provider, no fallback, fresh cell contexts, one sample per cell, and exact recorded settings.
- Infrastructure retries are distinct from model samples. Never retry invalid model decisions. Freeze the single no-tool re-prompt verbatim.
- Do not make paid calls until spending authorization, credentials, provider settings, limits, and required offline tests are established. Credits and price estimates are not authorization.
- Never print, write, or commit credential values or authorization headers. Credentials come from environment variables; the user-authorized, Git-ignored project-root `.env` may populate known credential names without overriding existing process values. Never display or commit `.env`; report presence only. Loading credentials does not authorize paid calls.
- Retain every planned condition and case, including MASKED and final-outcome analyses; the current user instruction supersedes the source's time-pressure cut order.
- Routine milestone commits and pushes to the verified intended repository are authorized. No force-push, protected-branch merge, new public remote, visibility change, publication, or submission without the required approval.

## Milestone cycle

Exactly six milestones: audit; implementation; validation; smoke/pilot/freeze; main execution; analysis/report/reproduction. For each, complete work, run relevant checks, repair and retest, review diff/artifacts/secrets/claims, update `research/decisions.md` and `research/milestones.json`, then commit and push to a verified destination. Record failed/skipped checks and blocked pushes accurately; continue independent authorized work. Avoid empty commits.

Run `python scripts/verify_audit.py`, `python -m pytest -q`, and `git diff --check` for the current implementation. The audit script checks evidence consistency and source integrity; it does not substitute for experiment tests. Preserve historical M1 baseline facts when updating the live requirements/status records. Read-only provider account checks and public source research are authorized.

## Current smoke authorization

The user explicitly authorized USD 10 total testing, paid calls on `openai/gpt-4.1-mini` through OpenRouter's `openai` route (returned provider `OpenAI`), and **smoke only** capped at **USD 1 or 200 total attempts**, including retries, re-prompts and continuations. Stop and report before pilot or main. This supersedes the earlier offline/free-only prohibition and ten-free-attempt allowance for this paid smoke only. No credit purchase, alternate model/provider, repeated new smoke, pilot, main, freeze or publication is authorized by this checkpoint.

Use `configs/paid_smoke.yaml` and the single canonical output `runs/paid_smoke_gpt41mini_20261115`. The shared `runs/_paid_testing_session` stores immutable authorization, budget and attempt history. Never delete, reset, refund or relocate it to acquire more allowance. Keep the historical free config disabled. Fresh authenticated account evidence must show a positive nonreset hard key limit at most USD 10 with enough remaining for the conservative reservation. Config flags or account credits are insufficient evidence. Unknown charges or inconsistent history suspend dispatch pending reconciliation.

The paid serializer pins temperature 0, omitted reasoning, 512 maximum output tokens, automatic tool choice, parallel tools disabled, strict supported parameters and no fallback. Exact documented snapshot aliases may be accepted while the actual returned identity is retained. Price ceilings are USD 0.40/1.60 per million input/output tokens with zero request/image fees. The conservative reservation covers the full advertised context plus maximum output; it may stop before the dollar cap when the remainder cannot cover another bound. Provider rate guarantees remain unpublished; 10 requests/minute is an operator throttle, not an upstream guarantee.

Complete and record required offline tests before inference. Preserve all smoke observations, even invalids and infrastructure failures; never resample a successful or invalid decision. Scope or infrastructure fixes must retain prior raw evidence and compatible source provenance. Smoke can validate the future M5 harness but does not provide main scientific findings. No execution freeze exists yet, so pre-freeze repairs are allowed within the unchanged design.

## Reporting and historical state

Earlier free-key failures, free-only caps and offline preparation remain historical in `research/decisions.md` and the check records. The USD 20 proposal remains unapproved. The current authorization and account check are recorded in `research/paid_smoke.md`; do not confuse historical assertions with current execution permission.

Tonmoy and Araf are confirmed author names; affiliations and H1-H5 participation remain unconfirmed. Pre-results exports are historical artifacts tied to their recorded source version. Once empirical smoke exists, do not regenerate a manuscript claiming no inference occurred. Report tests use isolated pre-results fixtures while the production guard remains strict. Empirical analysis must use the fixed 10,000 bootstrap resamples and seed 314159. Historical authoritative protocol bytes remain unchanged.


## Partial smoke evidence and current stop

The nonreset USD10 key limit is now verified. One real request in the canonical smoke returned HTTP404 with no model reply; the guard stopped before retry. Preserve the one attempt and unknown-cost hold. Current public metadata does not verify the strict pinned endpoint's required parallel-tool control. Do not substitute a model/provider, relax controls, invent a zero-cost receipt, reset the session, or edit the historical manifest to resume. Pilot/main remain outside scope.

The original five run files are bound to collection source0ad2562 in `research/run_sources.json`. Offline audit may use `scripts/replay_history.py` to verify that exact source in a credential-free, network-blocked snapshot; live source-hash checks remain strict. Future repairs must leave the raw trace unchanged. `scripts/smoke_diagnostics.py` reports the corrected one-failed/79-untouched distinction separately from original collection-version scores. Account usage reports0; per-attempt billing is still unknown and its conservative reservation remains held.

## Current repair-only instruction

The latest user instruction is to fix the failure without running smoke. This checkpoint permits offline implementation/tests and routine Git delivery only; no inference or account recheck is needed. Readback has no tools: omit tools, tool_choice and parallel_tool_calls from its wire payload. Decisions and post-inspection continuations must still send parallel_tool_calls:false, automatic tool choice and the unchanged strict provider pin. This follows the original no-tools readback design, not a relaxation of decision controls. Preserve the unknown-cost hold, consumed attempt and collection-version artifacts. A code repair alone does not establish live route compatibility or authorize replaying a changed request as an identical retry.
