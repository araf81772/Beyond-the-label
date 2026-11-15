# Prepare the 79 untouched smoke cells

The current user instruction is to repair endpoint identity handling and
prepare continuation of the 79 untouched smoke cells, with **no paid calls**.
This document describes the repair and required preparation procedure. It does
not claim a new full-suite pass, source commit, prepared continuation record or
live execution. Actual validation and delivery outcomes must be recorded in
the decision log, milestone status and check artifacts after they occur.

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
Preparation must not create that directory or any empirical events. A separate
`research/smoke_continuation_79.json` will bind the repaired committed source,
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

## Validate, commit and prepare without calls

Run the required relevant offline suite and audit, fix failures and retest:

```powershell
$env:PYTHONPATH = 'src'
python -m pytest -q
python scripts/verify_audit.py
git diff --check
```

Record actual outcomes, review the diff and commit the validated source. The
previous 1511-test preparation and 1515-test post-run passes describe earlier
source versions; they do not validate this repair. Use the exact 40-character
new source commit in the offline preparation command:

```powershell
python scripts/prepare_smoke79.py --source-commit VERIFIED_SOURCE_COMMIT
```

The script replays both historical collection sources with credentials removed
and network blocked, checks immutable artifacts and the unchanged scientific
inputs, and exclusively creates `research/smoke_continuation_79.json`. It makes
no provider/account calls, changes no shared journals and creates no v3 run
directory. It refuses to overwrite an existing new record or started segment.
Commit the generated record separately after its hashes are verified, avoiding
a circular source-commit dependency. Do not recreate or replace the v2 record.

Once preparation is verified, a future fresh GET-only readiness check is:

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
