# Beyond the Label: research rules

## Authority and scope

Follow the user's current instructions. `research/protocol.md` is a byte-preserved copy of the supplied authoritative `final_design.txt`; `research/source_manifest.json` records its hash. Record conflicts and unresolved details in `research/decisions.md`. Do not silently substitute a prior study or change design numbers. The user subsequently authorized only the79untouched smoke cells under existingcaps and required stop/report beforepilot/main. That continuation has now stopped on an unknown-cost continuation timeout. Preserve the partial sample and both unknown-cost holds; do not retry or broaden cost coverage implicitly. The USD 10 total testing / USD 1 smoke / 200 aggregate-attempt limits, including both prior attempts and the retained hold, remain unchanged. Stop before pilot or main. Continue test → fix → test → commit → push cycles. Git delivery to the verified remote is authorized. The explicit NUMERIC amendment is in `research/amendments.md`.

The design's “frozen for build” header is not an execution freeze. A validated smoke/pilot, freeze commit, tag, and hashes are still required before any main call. After an execution freeze, material changes require explicit approval, a deviation record, a new run ID, and a new freeze.

## Roles and evidence

Codex performs engineering, execution, and machine checks. Independent agent review must be labelled AI review. Claude (Anthropic) was authorized by Araf on 15 November 2026 to review the repository against the sprint rules and to implement branch `v1`: the staged execution path, its tests and documentation. That work is AI engineering and AI review, recorded in `research/decisions.md`. Neither agent substitutes for the human checks in design Section 10. Record real participants and never invent initials, participation, results, costs, citations, or completed checks.

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

The original paid authorization covered GPT-4.1 mini/OpenAI and one smoke capped at USD 1 or 200 total attempts, including retries, re-prompts and continuations, within USD 10 total testing. The user subsequently approved `deepseek/deepseek-v4.1-flash-1017` through OpenRouter route `primeintellect`, returned provider `PrimeIntellect`, then authorized the recorded attempt that stopped on endpoint identity validation. The latest79-cell smoke execution was authorized and has stopped; no pilot/main execution or new allowance is authorized. No credit purchase, further model/provider substitution, additional smoke allowance, pilot, main, freeze or publication is authorized.

Use `configs/paid_smoke.yaml`; preserve the canonical parent `runs/paid_smoke_gpt41mini_20261115`, its `segments/deepseek_primeintellect_v2` child and all original artifacts. Preserve `research/smoke_continuation.json`; do not rebuild or overwrite the v2 record. The new `research/smoke_continuation_79.json` must bind a tested, committed repair to a future `segments/deepseek_primeintellect_v3` child. Preparation must not create that execution directory. The shared `runs/_paid_testing_session` retains immutable authorization, budget and attempt history: 96 attempts consumed,104 remaining. Never delete, reset, refund or relocate it to acquire allowance. Keep the historical free config disabled. Future execution still requires fresh evidence of a positive nonreset hard key limit at most USD 10 and enough remaining for the reservation.

The prepared profile fixes temperature 0, reasoning `{"effort":"none"}`, 512 maximum output tokens, automatic tool choice, parallel tools disabled, strict supported parameters and no fallback. Top-level model identity remains exactly `deepseek/deepseek-v4.1-flash-1017`; `accepted_returned_models` stays empty. The new `accepted_endpoint_models` field explicitly permits `deepseek/deepseek-v4.1-flash-20261017` only in selected endpoint metadata for that exact DeepSeek/PrimeIntellect profile and fixed settings. It is not a top-level alias or fallback and does not change outbound request bytes. Historical absent/empty endpoint settings still reject the old reply. Routing ceilings are USD 0.04368/0.70 per million input/output tokens and zero request/image fees. Optional fee metadata remains unknown; explicit router ceilings enforce admissibility. The full 1,048,576-token input context plus 512 output tokens and 5% margin yields USD 0.048468209664 per attempt. Operator limits are 10 requests/minute and 10,490,880 bounded tokens/minute; upstream guarantees remain unpublished.

Keep the exact historical HTTP404 hold of USD0.44084208 and the new timeout hold of USD0.048468209664. Current known settled cost is USD0.0125113232; totalheldUSD0.489310289664 and availableUSD0.498178387136 under the unchangedUSD1cap. The fixed cost-coverage review permits only this already-covered uncertainty; it is not a receipt, refund, settlement or assertion of actual zero cost. Any new unknown/pending charge or inconsistent history still stops dispatch. Never recalculate the old hold using the new cheaper profile.

Complete and record required offline tests before inference. Preserve all smoke observations, even invalids and infrastructure failures; never resample a successful or invalid decision. Scope or infrastructure fixes must retain prior raw evidence and compatible source provenance. Smoke can validate the future M5 harness but does not provide main scientific findings. No execution freeze exists yet, so pre-freeze repairs are allowed within the unchanged design.

## Reporting and historical state

Earlier free-key failures, free-only caps and offline preparation remain historical in `research/decisions.md` and the check records. The USD 20 proposal remains unapproved. `research/paid_smoke.md` preserves the GPT checkpoint; `research/smoke_readiness.md` preserves the preceding readiness checkpoint; `research/deepseek_smoke.md` preserves the v2 identity failure. Current repair preparation is in `research/smoke_continuation79.md`. Do not confuse historical assertions, configuration flags or preparation approval with permission to execute now.

Tonmoy and Araf are confirmed author names; affiliations remain unconfirmed. The user reports H1/H2/H5 completion by themselves and Araf; record this as user-attested, not directly observed or AI-completed human verification. H1 was completed late. On 16 November the user assigned themselves H3 lead and Araf H4 lead; each team member's independent H3 audit remains required. H3/H4 completion remains pending and the late D4 assignment after freeze is disclosed. See `research/human_verification.json`. Pre-results exports are historical artifacts tied to their recorded source version. Once empirical smoke exists, do not regenerate a manuscript claiming no inference occurred. Report tests use isolated pre-results fixtures while the production guard remains strict. Empirical analysis must use the fixed 10,000 bootstrap resamples and seed 314159. Historical authoritative protocol bytes remain unchanged.


## Partial smoke evidence

Historical authenticated evidence verified the nonreset USD 10 key limit. One real GPT request in the canonical smoke returned HTTP404 with no model reply; the guard stopped before retry. Preserve that attempt and unknown-cost hold. GPT's public endpoint metadata does not verify the required parallel-tool control; the approved replacement's metadata does. Metadata does not prove live delivery. Do not invent a zero-cost receipt, reset the session, edit the historical manifest, or relabel the original attempt as DeepSeek. Pilot/main remain outside scope.

The original five run files are bound to collection source `0ad2562` in `research/run_sources.json`. Offline audit may use `scripts/replay_history.py` to verify that exact source in a credential-free, network-blocked snapshot; live source-hash checks remain strict. Future repairs must leave the raw trace unchanged. `scripts/smoke_diagnostics.py` reports the corrected one-failed/79-untouched distinction separately from original collection-version scores. The historical account check reported zero usage; per-attempt billing remains unknown and its conservative reservation remains held.

## Preparation and execution boundary

Readback has no tools: omit `tools`, `tool_choice` and `parallel_tool_calls` from its wire payload. Decisions and post-inspection continuations must still send `parallel_tool_calls:false`, automatic tool choice and the exact approved provider pin. This follows the original no-tools readback design.

The repair passed1634offline tests and source `eebba9de7a9923d2a81d17f7631d41371a35ef5e` is committed/pushed. `research/smoke_continuation_79.json` has been prepared and strictly verified after both historical collection-version replays. Do not rerun its exclusive preparation CLI or overwrite it. Verify existing metadata with `python scripts/verify_audit.py`; preserve the v2 record, either raw run and shared controls. Current preparation evidence is `research/checks/endpoint_repair_preparation.json`; its readiness exercise used historical account/route evidence, not fresh live calls. All48execution inputs remain bound to the tested source.

The full plan remains 80 cells in the same seeded order. Retain `smoke-1100-readback-MAIN-inline-b` as `cell_status:retained_terminal`, missing reason `model_mismatch`, with no valid observation and no new phase/attempt/completion events for that row. Only the 79 untouched cell IDs may dispatch, in their original relative order. Never resample or retroactively accept the v2 reply. Offline diagnostic parsing under repaired settings must remain separate from empirical scores and the historical rejection.

`python -m beyond_label.paid_live` and `--check-ready` perform read-only public/account GET checks after local verification. They do not start smoke, claim attempts or create empirical output. A fresh GET-only readiness check is a later prerequisite, not a paid call or proof of live success. Only `--execute` selects inference; the latest run stopped on cost reconciliation, so do not invoke it again until that blocker is resolved and further execution is explicitly requested. Passing offline tests or readiness checks does not establish a passed smoke, pilot, freeze or main run.


## Historical v2 identity stop

The authorized DeepSeek smoke stopped after its first raw reply failed selected-endpoint model identity validation (`1017` requested/top-level versus `20261017` selected metadata). Retain that terminal missing readback without retry or resampling. At that historical checkpoint there were2aggregate attempts,198remaining, knownUSD0.00005501216 and heldUSD0.44084208, leavingUSD0.55910290784;79cells were then untouched. Current balances and the later partial continuation are recorded below. Historical results stay in `research/deepseek_smoke.md`. The endpoint-only repair and new source provenance must pass current checks before any future continuation. Do not treat exit zero, offline diagnostic parsing or prior readiness as a passed smoke. Pilot/main remain unrun; no freeze exists.

## Current stopped continuation and M5 readiness

V3sourceeebba9d retained94newattempts/93acceptedcalls,53completed episodes and54first observations. One continuation timedout without a receipt;25cells remain untouched and the old terminal missing readback is still preserved. Aggregate96attempts/104remaining; knownUSD0.0125113232, heldUSD0.489310289664 (old0.44084208+new0.048468209664), availableUSD0.498178387136. The coverage-aware policy is blocked despite the unused balance. Never treat ledger blocked:false as permission to dispatch. Keep all5v3files immutable; their source binding is in research/run_sources.json. Research-only status is in research/checks/smoke79_outcome.json and research/m4_m5_readiness.md.

M4is incomplete andM5is not ready: paidpilot/main support, paidfreeze evidence, complete frozen reproduction and smoke acceptance require work before further stages. Existing pilot/main configs remain disabled. Do not relax the80-nonmissing smoke guard silently, claim pilot/load selection, fabricate human participation or create a freeze before verified gates. The current user request required stop/report beforepilot/main.

## Staged USD 9 allowance (branch `v1`, supersedes the smoke-only boundary for new work)

The sections above describe the closed `paid-smoke-usd1-200-v1` authorization. Keep that history, its session `runs/_paid_testing_session` and all three smoke directories byte-for-byte. Do not resume, reset or extend it; `scripts/verify_audit.py` replays it against its own source commits.

On 15 November 2026 Araf set "budget cap usd 9" and asked for the project to be made ready for a smoke test and the final run, without spending until explicitly approved. That allowance is `paid-staged-usd9-v1`: see `research/staged_authorization.json`, `configs/staged.yaml`, `src/beyond_label/staged.py` and the runbook `research/staged_execution.md`.

- Preparation is not execution. Run `python -m beyond_label.staged execute --stage …` only when a user explicitly asks for that stage in the current conversation. `status` and `check-ready` are always allowed.
- Stage order is fixed: smoke, pilot, load-8 smoke only if the pilot selects load-8, freeze, main. The code enforces it; never bypass a gate, edit a gate's run files or hand-write a freeze record.
- Limits: USD 9 ledger, 3,000 attempts, USD 0.048468209664 reserved per attempt, same model/provider/settings as the retained smoke. An unknown charge keeps its full hold and the run continues (user decision, verbatim in the authorization record); stop at 40 holds.
- From the first staged smoke call until the main analysis is finished, do not change any hashed input: `src/beyond_label/*.py`, `prompts/`, `configs/*.yaml`, `data/`, `research/protocol.md`, `research/amendments.md`, `pyproject.toml`, `requirements.lock`. A changed input invalidates the gates.
- Never interrupt a running stage. Use `--max-cells` to run in pieces.
- After each stage: `python scripts/sync_execution_status.py`, `python scripts/verify_audit.py`, update `research/decisions.md` and the milestone statuses, commit. Before main: the freeze tag must be pushed to `origin`.
- Smoke observations are never analysed. Pilot observations select the load and are reported separately. Only the frozen main run supplies results.
- The report is written by the team in the official template. `report/manuscript.md` is a dated pre-results artifact; do not regenerate it or present it as the submission. `report/SUBMISSION_GUIDE.md` lists what must be true before submitting.

## Historical human confirmation update (15 November 2026)

The user authorized updating `v1` with their H1/H2/H5 completion confirmations, unchanged D3 rules and accepted MASKED truncation limitation. Preserve H1's late completion and the late D3/D4 decision record. No exact Fan et al. recognition percentage is cleared for quotation: the cited v2 contains both 76.2% and 281/376 (74.7%); the current manuscript uses only the supported qualitative claim. D4 still needs explicit future H3 responsibilities and an H4 owner. H3/H4 completion comes after main and is not a pre-freeze requirement. This update does not authorize creating a freeze/tag or running main; the user explicitly said not to run main yet. All 50 experimental inputs and all empirical artifacts must remain unchanged.

On 15 November 2026 (late) Araf explicitly requested the freeze and the main readiness check. `research/execution_freeze.json` was written by `python -m beyond_label.staged freeze --tag btl-freeze-v1` for commit `6f8f94b3542980f65ba08f56aa3a12bf12c9e41d` (load-8). Never edit or regenerate that record. The tag exists only where it was created until someone pushes it; main stays blocked until `btl-freeze-v1` is visible on `origin` and `check-ready --stage main` passes. Main still needs its own explicit request. From now until the main analysis is finished, the hashed inputs must not change.

## Main authorization and execution location (16 November 2026)

The user explicitly instructed: "me h3, araf h4. so fix all 4 and test fix test and final run". The current user leads H3 and Araf leads H4; the protocol still requires each human's independent H3 audit. H3/H4 are pending, and assigning leads after freeze remains a documented timing deviation. This instruction authorizes the frozen main run under the unchanged USD 9 staged allowance after the operational prerequisites, required validation and fresh main readiness check pass. It does not authorize changing scientific inputs, exceeding caps, resampling decisions, publication or submission.

Tag `btl-freeze-v1` is now pushed and verified on `origin` at exactly `6f8f94b3542980f65ba08f56aa3a12bf12c9e41d`. Launch validation and fresh main readiness passed in the unsynced clone: 1,680 tests and the integrity/dependency checks. M4 is complete; main has not started at this preparation checkpoint. See research/checks/main_execution_preparation.json. Do not infer M5 completion. Use only `C:/Users/tonmo/CodexRuns/beyond-the-label-v1-main-20261116` for main execution. This original OneDrive checkout must not dispatch main concurrently or independently. Preserve the existing freeze record, all 50 experimental inputs and every retained run/session artifact.

**Canonical execution entry point:** the first main launch using `python -m beyond_label.staged execute --stage main` stopped before dispatch because duplicate `__main__`/canonical policy classes failed the strict type guard. Preserve that failed command/preflight record. Use `python -c "from beyond_label.staged import main; raise SystemExit(main())" execute --stage main` for the authorized relaunch. The offline diagnostic confirms the existing strict verifier passes under canonical import; do not weaken it or edit any frozen input. This invocation-only correction preserves the existing freeze.
