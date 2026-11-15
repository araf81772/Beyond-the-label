# Historical v2 DeepSeek smoke: identity check stopped execution

This document preserves the v2 collection outcome and its original rejection.
The user has since requested an endpoint-only repair and preparation of the
79 untouched cells, with no paid calls. See [the current preparation](smoke_continuation79.md).
The repaired mapping does not change any v2 trace, score, terminal status or
cost below. In particular, offline diagnostic parsing under new settings does
not turn the old reply into an accepted empirical observation.

After the user authorized smoke execution, the canonical `paid_live --execute`
entry point ran once using source commit
`89de9c8202c8cfa9720f49e495ecbb8ea662f3aa`. It stopped after the first response
with `model_mismatch`. **Smoke has not passed.** Pilot, main and execution
freeze remain unstarted. No main effect, interval, regret or recognition-action
finding can be estimated from this partial engineering run.

Evidence: [outcome](checks/deepseek_smoke_outcome.json) and
[execution record](checks/deepseek_smoke_execution.json). The latter records
the authorized invocation on 15 November 2026 from 13:27:29 to 13:29:01 AEDT (02:27:29–02:29:01 UTC). Its zero
process exit code means the harness returned a controlled partial-stop report;
it is not a scientific or smoke-gate pass.

## What failed

The first cell was `smoke-1100-readback-MAIN-inline-b`. Its top-level returned
model matched the requested `deepseek/deepseek-v4.1-flash-1017`, and the returned
provider matched `PrimeIntellect`. OpenRouter's selected-endpoint metadata used
`deepseek/deepseek-v4.1-flash-20261017`. The configured accepted-alias set was
empty, so the strict identity check rejected that endpoint identity.

This is an observed identity-validation failure. It does not establish that
the provider used a different underlying model, and it does not justify
silently treating the two identities as equivalent. The original response and
identity fields remain intact for an explicit evidence-backed repair.

## Sample and accounting

| Measure | Retained evidence |
| --- | --- |
| New attempts / raw model replies | 1 / 1 |
| Accepted successful calls / valid observations | 0 / 0 |
| Planned cells | 80 |
| Terminal cells with a missing observation | 1 |
| Pending cells | 79 |
| Missing observations | 80 |
| Retries / re-prompts / continuations | 0 / 0 / 0 |
| Invalid first actions | 0 |
| Aggregate attempts consumed / remaining | 2 / 198 |
| Known settled cost of the new call | USD 0.00005501216 |
| Historical unknown-cost hold | USD 0.44084208 |
| Available smoke allowance | USD 0.55910290784 |

The terminal status closes the failed cell for resume purposes; it is not a
successful or valid completed observation. The new raw reply is not counted as
an accepted call or an invalid model action. Its usage reports 362 input tokens,
56 output tokens, zero reasoning tokens and ordinary OpenRouter billing
(`is_byok:false`). These fields establish the recorded new-call charge; they do
not resolve the earlier GPT request's unknown cost. Aggregate actual cost
therefore remains incomplete. The original USD 10 total testing / USD 1 smoke /
200-attempt limits are unchanged, and no attempt was refunded.

The run artifacts are under
`runs/paid_smoke_gpt41mini_20261115/segments/deepseek_primeintellect_v2`:

- `manifest.json`: the same 80 planned cells and collection settings.
- `calls.jsonl`: immutable request, response and failure evidence.
- `scores.csv`: terminal missingness plus the 79 untouched cases.
- `usage.csv`: retained usage and the known new-call charge.
- `analysis_manifest.json`: partial-run counts and explicit missingness.

The outcome record preserves each artifact's SHA-256. Collection inputs, the
original GPT five-file run and historical control prefixes remain unchanged.
Both attempts remain in the shared accounting history. No human review was
performed or inferred from these machine checks.

## Offline review and next repair

Safe checks that do not make provider or account calls:

```powershell
$env:PYTHONPATH = 'src'
python -m pytest -q
python scripts/verify_audit.py
python scripts/replay_history.py --run runs/paid_smoke_gpt41mini_20261115
git diff --check
Get-Content research/checks/deepseek_smoke_outcome.json
```

The replay command above verifies the historical GPT parent using its exact
collection source; it does not reinterpret or overwrite the DeepSeek child.
Post-run validation passed **1515 offline tests in 376.64 seconds**, with network blocked and credentials isolated; [suite evidence](checks/deepseek_smoke_suite.json). This follows a fixture-only repair that verifies the historical ledger prefixes and adds four mutation/truncation regressions. Production source and empirical artifacts remain unchanged. This result is separate from the preceding 1511-test preparation pass. Do not call `paid_live --execute` merely to inspect
or reproduce this evidence. `--check-ready` performs network GET checks and is
not an offline reproduction command.

The following were the next repair requirements recorded at the stop; their
current implementation and preparation status are tracked separately in
[smoke_continuation79.md](smoke_continuation79.md).

Before any further execution, verify and implement an explicit mapping between
the requested model and the documented selected-endpoint identity. Keep exact
provider restrictions and reject arbitrary aliases or fallback. Add regressions
for the observed response shape, mismatched identities and offline replay, then
record the repaired source and its provenance without altering the collection
version or raw traces.

Preserve the current terminal cell without resampling it. Do not turn the
rejected reply into a successful observation silently, retry the same completed
cell, erase the failed attempt, reset its allowance or reinterpret a changed
request as an identical retry. Any versioned continuation must retain the
original 80-cell plan, explicit missingness and shared cost/attempt history.
Stop before pilot or main; this partial smoke supplies engineering evidence
only.
