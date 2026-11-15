# Prepared79-cell continuation: historical preparation and partial execution

This document preserves the completed no-call preparation checkpoint. The user
subsequently authorized the79-cell continuation, which stopped on an unknown-cost
continuation timeout. See the [current outcome](checks/smoke79_outcome.json) and
[M4/M5 readiness review](m4_m5_readiness.md). All figures below describing the
preparation baseline are historical, not current remaining balances.
The repair passed **1634 offline tests** and is committed and pushed as
`eebba9de7a9923d2a81d17f7631d41371a35ef5e`. The continuation record is prepared and
strictly verified against that source and both historical runs. No new inference
or account call occurred. [Validation evidence](checks/endpoint_repair_suite.json)
and [preparation evidence](checks/endpoint_repair_preparation.json) preserve the
actual checks, including the initial failed test and its repair.

The [v2 smoke outcome](deepseek_smoke.md) remains unchanged: one raw reply was
rejected as `model_mismatch`, no valid observation exists, and the smoke gate
has not passed. Pilot, main and execution freeze remain unrun and outside scope.

## Exact endpoint mapping

The requested and top-level returned model remain strictly
`deepseek/deepseek-v4.1-flash-1017`. `accepted_returned_models` stays empty.
The new, separate `accepted_endpoint_models` setting contains only
`deepseek/deepseek-v4.1-flash-20261017`, for the selected endpoint metadata of
the exact `PrimeIntellect` provider and `primeintellect` route.

The mapping is tied to the approved profile: strict parameter support, no
fallback, nonfree billing mode, temperature 0, reasoning `{"effort":"none"}`,
512 output tokens and unchanged price ceilings. It does not admit another
top-level model, provider, arbitrary alias or snapshot. No mapping field is
sent to the model; serialized requests remain unchanged. Public source evidence
and the focused regression cycle are in
[endpoint_identity_sources.json](checks/endpoint_identity_sources.json).

Historical settings default to an empty endpoint mapping. Replaying the v2
reply with those settings still produces `model_mismatch`. A separate read-only
diagnostic can parse its identity with the repaired mapping, but must not write
new scores, alter raw evidence or create an observation. The historical
collection record and its failed classification remain authoritative for v2.

## Preserve 80 planned cells, dispatch 79

The original plan remains all 80 cell IDs, the same worlds and conditions,
smoke seeds 1100–1103, load 2 and seeded order. Preserve
`smoke-1100-readback-MAIN-inline-b` as the terminal missing cell. In the new
version's derived view it has `cell_status: retained_terminal`, missing reason
`model_mismatch` and no valid observation. Its provenance points to the v2
artifacts; it gets no new phase, attempt or completion events.

Only the other 79 IDs may dispatch, in their original relative order. Do not
remove the retained row from denominators, count it as a successful completion,
resample it or fill its missing observation from the diagnostic replay. A later
resume must skip both the retained row and any new terminal cells.

Keep these historical artifacts unchanged:

- `runs/paid_smoke_gpt41mini_20261115`: the original GPT request and five-file run.
- `runs/paid_smoke_gpt41mini_20261115/segments/deepseek_primeintellect_v2`: the
  rejected DeepSeek reply and five-file run.
- `research/smoke_continuation.json`: the original v2 preparation record.
- `runs/_paid_testing_session`: cumulative authorization, attempts and costs.

The future execution location is
`runs/paid_smoke_gpt41mini_20261115/segments/deepseek_primeintellect_v3`.
Preparation must not create that directory or any empirical events. The separate
`research/smoke_continuation_79.json` binds the repaired committed source,
both historical replays, full plan, retained row and ordered dispatch list.

## Unchanged allowance and uncertainty

| Measure | Preserved value |
| --- | --- |
| Total testing / smoke caps | USD 10 / USD 1 |
| Aggregate attempt cap | 200, including retries, re-prompts and continuations |
| Attempts consumed / remaining | 2 / 198 |
| Known settled v2 charge | USD 0.00005501216 |
| Historical GPT unknown-cost hold | USD 0.44084208 |
| Available smoke allowance | USD 0.55910290784 |
| Next-attempt conservative bound | USD 0.048468209664 |

No preparation step refunds an attempt, settles an invented charge or resets
the cap. The exact old hold remains conservative coverage of an unknown actual
cost, not a billing receipt. Any new unknown/pending charge still stops
dispatch. Aggregate actual cost remains incomplete. Fresh account evidence is
still required before a later execution; neither available credit nor a
configuration flag supplies authorization.

## Verification and recorded preparation

Run the required relevant offline suite and audit, fix failures and retest:

```powershell
$env:PYTHONPATH = 'src'
python -m pytest -q
python scripts/verify_audit.py
git diff --check
```

The current source passed 1634 tests after a narrow diagnostic guard repair.
The earlier 1511-test and 1515-test passes remain historical. The following
one-time preparation command already completed successfully:

```powershell
python scripts/prepare_smoke79.py --source-commit eebba9de7a9923d2a81d17f7631d41371a35ef5e
```

The script replays both historical collection sources with credentials removed
and network blocked, checks immutable artifacts and the unchanged scientific
inputs, and exclusively creates `research/smoke_continuation_79.json`. It makes
no provider/account calls, changes no shared journals and creates no v3 run
directory. It refuses to overwrite an existing new record or started segment.
The generated record is delivered in a separate metadata commit, avoiding a
circular source dependency. Do not rerun preparation against this existing
record or recreate the v2 record. `python scripts/verify_audit.py` validates the
existing preparation and independently replays its historical evidence.

Preparation is verified offline. A future fresh GET-only readiness check is:

```powershell
python -m beyond_label.paid_live --check-ready
```

This is a network metadata/account check, not an offline test or an inference
call. The default entry point also checks readiness only. It must preserve the
terminal row, cumulative accounting and absent v3 execution directory. A ready
status does not establish that a future response will pass every live check.

Do not use `--execute` during this repair/preparation instruction. Further
inference needs a later explicit user request and all current source, route,
account, cost and attempt guards. No pilot, main, freeze, model substitution or
publication is included. No new human participation is inferred from the
engineering review.

Record body hash: `7fd60a8e009e3b65945321806b7cc24ca3037b722298a12a5a1781e95f59878c`. Record file SHA256: `35210961e64d0a11823cf5dde13c03b9c9e0afcf0d5c2f687714600c7da9e8bf`. All 48 tested execution inputs, 14 historical run/session files and four historical research records remained unchanged during preparation. The offline readiness exercise used recorded account/route evidence and does not verify current live availability.
