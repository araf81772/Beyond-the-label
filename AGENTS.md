# Beyond the Label: research rules

## Authority and scope

Follow the user's current instructions. `research/protocol.md` is a byte-preserved copy of the supplied authoritative `final_design.txt`; `research/source_manifest.json` records its hash. Record conflicts and unresolved details in `research/decisions.md`. Do not silently substitute a prior study or change design numbers. The latest instruction is to fix endpoint identity handling and prepare only the 79 untouched smoke cells, with no paid calls now. Preserve the prior execution authorization as history; it does not override this repair-only checkpoint. The USD 10 total testing / USD 1 smoke / 200 aggregate-attempt limits, including both prior attempts and the retained hold, remain unchanged. Stop before pilot or main. Continue test → fix → test → commit → push cycles. Git delivery to the verified remote is authorized. The explicit NUMERIC amendment is in `research/amendments.md`.

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

## Current smoke preparation and retained authorization

The original paid authorization covered GPT-4.1 mini/OpenAI and one smoke capped at USD 1 or 200 total attempts, including retries, re-prompts and continuations, within USD 10 total testing. The user subsequently approved `deepseek/deepseek-v4.1-flash-1017` through OpenRouter route `primeintellect`, returned provider `PrimeIntellect`, then authorized the recorded attempt that stopped on endpoint identity validation. The current instruction permits repair and preparation only, with no paid calls. No credit purchase, further model/provider substitution, additional smoke allowance, pilot, main, freeze or publication is authorized.

Use `configs/paid_smoke.yaml`; preserve the canonical parent `runs/paid_smoke_gpt41mini_20261115`, its `segments/deepseek_primeintellect_v2` child and all original artifacts. Preserve `research/smoke_continuation.json`; do not rebuild or overwrite the v2 record. The new `research/smoke_continuation_79.json` must bind a tested, committed repair to a future `segments/deepseek_primeintellect_v3` child. Preparation must not create that execution directory. The shared `runs/_paid_testing_session` retains immutable authorization, budget and attempt history: two attempts consumed, 198 remaining. Never delete, reset, refund or relocate it to acquire allowance. Keep the historical free config disabled. Future execution still requires fresh evidence of a positive nonreset hard key limit at most USD 10 and enough remaining for the reservation.

The prepared profile fixes temperature 0, reasoning `{"effort":"none"}`, 512 maximum output tokens, automatic tool choice, parallel tools disabled, strict supported parameters and no fallback. Top-level model identity remains exactly `deepseek/deepseek-v4.1-flash-1017`; `accepted_returned_models` stays empty. The new `accepted_endpoint_models` field explicitly permits `deepseek/deepseek-v4.1-flash-20261017` only in selected endpoint metadata for that exact DeepSeek/PrimeIntellect profile and fixed settings. It is not a top-level alias or fallback and does not change outbound request bytes. Historical absent/empty endpoint settings still reject the old reply. Routing ceilings are USD 0.04368/0.70 per million input/output tokens and zero request/image fees. Optional fee metadata remains unknown; explicit router ceilings enforce admissibility. The full 1,048,576-token input context plus 512 output tokens and 5% margin yields USD 0.048468209664 per attempt. Operator limits are 10 requests/minute and 10,490,880 bounded tokens/minute; upstream guarantees remain unpublished.

Keep the exact historical HTTP404 hold of USD 0.44084208, plus USD 0.00005501216 newly settled cost, leaving USD 0.55910290784 available under the unchanged USD 1 cap. The fixed cost-coverage review permits only this already-covered uncertainty; it is not a receipt, refund, settlement or assertion of actual zero cost. Any new unknown/pending charge or inconsistent history still stops dispatch. Never recalculate the old hold using the new cheaper profile.

Complete and record required offline tests before inference. Preserve all smoke observations, even invalids and infrastructure failures; never resample a successful or invalid decision. Scope or infrastructure fixes must retain prior raw evidence and compatible source provenance. Smoke can validate the future M5 harness but does not provide main scientific findings. No execution freeze exists yet, so pre-freeze repairs are allowed within the unchanged design.

## Reporting and historical state

Earlier free-key failures, free-only caps and offline preparation remain historical in `research/decisions.md` and the check records. The USD 20 proposal remains unapproved. `research/paid_smoke.md` preserves the GPT checkpoint; `research/smoke_readiness.md` preserves the preceding readiness checkpoint; `research/deepseek_smoke.md` preserves the v2 identity failure. Current repair preparation is in `research/smoke_continuation79.md`. Do not confuse historical assertions, configuration flags or preparation approval with permission to execute now.

Tonmoy and Araf are confirmed author names; affiliations and H1-H5 participation remain unconfirmed. Pre-results exports are historical artifacts tied to their recorded source version. Once empirical smoke exists, do not regenerate a manuscript claiming no inference occurred. Report tests use isolated pre-results fixtures while the production guard remains strict. Empirical analysis must use the fixed 10,000 bootstrap resamples and seed 314159. Historical authoritative protocol bytes remain unchanged.


## Partial smoke evidence

Historical authenticated evidence verified the nonreset USD 10 key limit. One real GPT request in the canonical smoke returned HTTP404 with no model reply; the guard stopped before retry. Preserve that attempt and unknown-cost hold. GPT's public endpoint metadata does not verify the required parallel-tool control; the approved replacement's metadata does. Metadata does not prove live delivery. Do not invent a zero-cost receipt, reset the session, edit the historical manifest, or relabel the original attempt as DeepSeek. Pilot/main remain outside scope.

The original five run files are bound to collection source `0ad2562` in `research/run_sources.json`. Offline audit may use `scripts/replay_history.py` to verify that exact source in a credential-free, network-blocked snapshot; live source-hash checks remain strict. Future repairs must leave the raw trace unchanged. `scripts/smoke_diagnostics.py` reports the corrected one-failed/79-untouched distinction separately from original collection-version scores. The historical account check reported zero usage; per-attempt billing remains unknown and its conservative reservation remains held.

## Preparation and execution boundary

Readback has no tools: omit `tools`, `tool_choice` and `parallel_tool_calls` from its wire payload. Decisions and post-inspection continuations must still send `parallel_tool_calls:false`, automatic tool choice and the exact approved provider pin. This follows the original no-tools readback design.

After the full relevant tests pass and the repaired source is committed, run `python scripts/prepare_smoke79.py --source-commit COMMIT` with that exact 40-character commit. It must replay both historical collection versions offline, verify their artifacts and write only the new `research/smoke_continuation_79.json`. It must not modify the v2 record, either raw run or shared controls. Do not claim this record is prepared until the script succeeds and its hashes are recorded.

The full plan remains 80 cells in the same seeded order. Retain `smoke-1100-readback-MAIN-inline-b` as `cell_status:retained_terminal`, missing reason `model_mismatch`, with no valid observation and no new phase/attempt/completion events for that row. Only the 79 untouched cell IDs may dispatch, in their original relative order. Never resample or retroactively accept the v2 reply. Offline diagnostic parsing under repaired settings must remain separate from empirical scores and the historical rejection.

`python -m beyond_label.paid_live` and `--check-ready` perform read-only public/account GET checks after local verification. They do not start smoke, claim attempts or create empirical output. A fresh GET-only readiness check is a later prerequisite, not a paid call or proof of live success. Only `--execute` selects inference; do not use it during the current repair/preparation instruction. Passing offline tests or readiness checks does not establish a passed smoke, pilot, freeze or main run.


## Latest smoke stop

The authorized DeepSeek smoke stopped after its first raw reply failed selected-endpoint model identity validation (`1017` requested/top-level versus `20261017` selected metadata). Retain that terminal missing readback without retry or resampling. There are two aggregate attempts, 198 remaining, known cost USD 0.00005501216 and the unchanged USD 0.44084208 historical unknown-cost hold; USD 0.55910290784 remains available. The 79 other cells remain untouched. Historical results stay in `research/deepseek_smoke.md`. The endpoint-only repair and new source provenance must pass current checks before any future continuation. Do not treat exit zero, offline diagnostic parsing or prior readiness as a passed smoke. Pilot/main remain unrun; no freeze exists.
