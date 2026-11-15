# Beyond the Label: research rules

## Authority and scope

Follow the user's current instructions. `research/protocol.md` is a byte-preserved copy of the supplied authoritative `final_design.txt`; `research/source_manifest.json` records its hash. Record conflicts and unresolved details in `research/decisions.md`. Do not silently substitute a prior study or change design numbers. The latest user instruction explicitly authorizes running the prepared smoke now, then stopping and reporting before pilot or main. The user approved preparing the dated DeepSeek/PrimeIntellect replacement under the existing USD 10 total testing / USD 1 smoke / 200 aggregate-attempt caps. The subsequent execution request authorizes smoke calls under the same shared caps, including the original attempt and retained hold; see research/paid_smoke_execution_authorization.json. Stop before pilot or main. Continue test → fix → test → commit → push cycles. Git delivery to the verified remote is authorized. The explicit NUMERIC amendment is in `research/amendments.md`.

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

The original paid authorization covered GPT-4.1 mini/OpenAI and one smoke capped at USD 1 or 200 total attempts, including retries, re-prompts and continuations, within USD 10 total testing. The user subsequently approved preparing `deepseek/deepseek-v4.1-flash-1017` through OpenRouter route `primeintellect`, returned provider `PrimeIntellect`, with those same aggregate limits. The subsequent user request authorizes smoke execution now; retain the original preparation record as history. No credit purchase, further model/provider substitution, additional smoke allowance, pilot, main, freeze or publication is authorized.

Use `configs/paid_smoke.yaml`; preserve the canonical parent `runs/paid_smoke_gpt41mini_20261115` and all original files. A separately recorded source version may use its `segments/deepseek_primeintellect_v2` child for the same 80 planned cells. The shared `runs/_paid_testing_session` retains immutable authorization, budget and attempt history: two attempts consumed, 198 remaining. Never delete, reset, refund or relocate it to acquire allowance. Keep the historical free config disabled. Fresh authenticated account evidence must show a positive nonreset hard key limit at most USD 10 with enough remaining for the conservative reservation. Config flags and account credits are insufficient evidence.

The prepared profile fixes temperature 0, reasoning `{"effort":"none"}`, 512 maximum output tokens, automatic tool choice, parallel tools disabled, strict supported parameters and no fallback. No returned-model aliases are enabled for DeepSeek. Routing ceilings are USD 0.04368/0.70 per million input/output tokens and zero request/image fees. Optional fee metadata remains unknown; the explicit router ceilings enforce admissibility without inventing zero observed fees. The full 1,048,576-token input context plus 512 output tokens and 5% margin yields USD 0.048468209664 per attempt. Operator limits are 10 requests/minute and 10,490,880 bounded tokens/minute; upstream guarantees remain unpublished.

Keep the exact historical HTTP404 hold of USD 0.44084208, plus USD 0.00005501216 newly settled cost, leaving USD 0.55910290784 available under the unchanged USD 1 cap. The fixed cost-coverage review permits only this already-covered uncertainty; it is not a receipt, refund, settlement or assertion of actual zero cost. Any new unknown/pending charge or inconsistent history still stops dispatch. Never recalculate the old hold using the new cheaper profile.

Complete and record required offline tests before inference. Preserve all smoke observations, even invalids and infrastructure failures; never resample a successful or invalid decision. Scope or infrastructure fixes must retain prior raw evidence and compatible source provenance. Smoke can validate the future M5 harness but does not provide main scientific findings. No execution freeze exists yet, so pre-freeze repairs are allowed within the unchanged design.

## Reporting and historical state

Earlier free-key failures, free-only caps and offline preparation remain historical in `research/decisions.md` and the check records. The USD 20 proposal remains unapproved. `research/paid_smoke.md` preserves the historical GPT checkpoint; `research/smoke_readiness.md` describes the current preparation. Do not confuse historical assertions, configuration flags or preparation approval with permission to execute now.

Tonmoy and Araf are confirmed author names; affiliations and H1-H5 participation remain unconfirmed. Pre-results exports are historical artifacts tied to their recorded source version. Once empirical smoke exists, do not regenerate a manuscript claiming no inference occurred. Report tests use isolated pre-results fixtures while the production guard remains strict. Empirical analysis must use the fixed 10,000 bootstrap resamples and seed 314159. Historical authoritative protocol bytes remain unchanged.


## Partial smoke evidence

Historical authenticated evidence verified the nonreset USD 10 key limit. One real GPT request in the canonical smoke returned HTTP404 with no model reply; the guard stopped before retry. Preserve that attempt and unknown-cost hold. GPT's public endpoint metadata does not verify the required parallel-tool control; the approved replacement's metadata does. Metadata does not prove live delivery. Do not invent a zero-cost receipt, reset the session, edit the historical manifest, or relabel the original attempt as DeepSeek. Pilot/main remain outside scope.

The original five run files are bound to collection source `0ad2562` in `research/run_sources.json`. Offline audit may use `scripts/replay_history.py` to verify that exact source in a credential-free, network-blocked snapshot; live source-hash checks remain strict. Future repairs must leave the raw trace unchanged. `scripts/smoke_diagnostics.py` reports the corrected one-failed/79-untouched distinction separately from original collection-version scores. The historical account check reported zero usage; per-attempt billing remains unknown and its conservative reservation remains held.

## Preparation and execution boundary

Readback has no tools: omit `tools`, `tool_choice` and `parallel_tool_calls` from its wire payload. Decisions and post-inspection continuations must still send `parallel_tool_calls:false`, automatic tool choice and the exact approved provider pin. This follows the original no-tools readback design.

After tests and a source commit, `python scripts/prepare_smoke.py --source-commit COMMIT` prepares source-continuation, exact-cost-coverage and model-amendment records under `research/`, outside raw runs. It performs no inference or account call and must leave historical runs/controls unchanged. The new segment retains the same 80-cell manifest; reissuing the previously failed cell under changed source/model is explicitly versioned, never an identical retry or a second completed sample. That preparation predates the new raw reply. The current terminal missing readback must not be resampled; any future source-version continuation must preserve it and dispatch only the 79 untouched cells.

`python -m beyond_label.paid_live` and `--check-ready` perform read-only public/account GET checks after local verification. They do not start a smoke, claim attempts or create empirical output. Only `--execute` selects inference. The latest explicit user request authorizes smoke now, subject to all live guards and shared caps; stop before pilot or main. Passing offline tests or readiness checks does not establish a passed smoke, pilot, freeze, or main run.


## Latest smoke stop

The authorized DeepSeek smoke stopped after its first raw reply failed selected-endpoint model identity validation (`1017` requested/top-level versus `20261017` selected metadata). Retain that terminal missing readback without retry or resampling. There are2aggregateattempts,198remaining, known costUSD0.00005501216 and the unchangedUSD0.44084208historical unknown-cost hold.79cells remain untouched. Current results are in research/deepseek_smoke.md. Before future continuation, repair and validate explicit endpoint identity mapping and source provenance while preserving all terminal cells and raw artifacts. Do not treat exit0 or a prior readiness check as a passed smoke. Stop before pilot/main; no freeze exists.
