# Smoke preparation without execution

The user approved preparing dated DeepSeek/PrimeIntellect and explicitly said
not to run smoke yet. The implementation supports that preparation; this page
does not claim the full validation cycle, committed preparation records, live
delivery or smoke completion has occurred. Those outcomes must be recorded
with their actual evidence in `decisions.md`, `milestones.json` and `checks/`.
Pilot, main and execution freeze remain unstarted and outside this checkpoint.

## Prepared model and limits

| Setting | Fixed value |
| --- | --- |
| Routing service | OpenRouter |
| Model | `deepseek/deepseek-v4.1-flash-1017` |
| Provider route / expected identity | `primeintellect` / `PrimeIntellect` |
| Temperature / reasoning | `0` / `{"effort":"none"}` |
| Maximum output | 512 tokens |
| Decision tool controls | Automatic tool choice; parallel tools disabled |
| Strict support / fallback | `require_parameters:true`; `allow_fallbacks:false` |
| Returned-model aliases | None |
| Input/output ceilings | USD 0.04368 / 0.70 per million tokens |
| Request/image ceilings | USD 0 / 0 per unit |
| Total testing / smoke caps | USD 10 / USD 1 |
| Aggregate attempt cap | 200, including retries, re-prompts and continuations |
| Historical consumed / remaining attempts | 1 / 199 |
| Operator throttle | 10 requests and 10,490,880 bounded tokens per minute |

The public route metadata supports the required controls; the safe anonymous
check is in [smoke_route_readiness.json](checks/smoke_route_readiness.json).
The [approved route explanation](model_route_candidate.md) links the primary
sources. These checks do not establish actual delivery, returned identity or
effective reasoning behavior. Provider rate guarantees remain unpublished.
Tool-free readback omits tool-only fields; its prefix remains exactly the
decision prefix. Experimental worlds, payoffs, controls and analysis rules are
unchanged.

## Cost coverage without inventing a receipt

The original GPT request returned HTTP404 without a model reply. Its actual
cost remains unknown. The full USD 0.44084208 reservation remains held against
the USD 1 smoke cap, leaving USD 0.55915792 available. Historical account usage
of zero is not a per-attempt receipt. No money or attempt is refunded, no
settlement is fabricated and no original journal is rewritten.

A fixed review recognizes only that exact historical attempt as conservatively
covered by its existing hold. It verifies the original artifacts, collection
source, request identity and journal prefixes. This allows the remaining
unreserved cap to be evaluated without pretending the old uncertainty vanished.
Any later unknown/pending charge, changed hold or inconsistent history still
stops dispatch.

The new attempt reservation is:

`(1048576 × 0.04368 / 1000000 + 512 × 0.70 / 1000000) × 1.05 = USD 0.048468209664`.

This covers the full advertised input context plus 512 output tokens and a 5%
margin. It is a conservative bound, not a predicted or actual charge. Missing
optional request/image prices stay unknown; the explicit router ceilings
enforce their zero admissibility limits. Known successful costs may release
unused reservation under the existing ledger rules. Execution stops if the
remaining cap cannot cover another full bound, even below USD 1. Fresh account
evidence must still verify a positive, nonreset hard key cap at most USD 10 and
enough available balance for the next reservation.

## Versioned continuation of the same plan

Keep `runs/paid_smoke_gpt41mini_20261115` and its five original artifacts
immutable. They belong to collection source
`0ad25621f3b730065b1a71b92aafc1fd0a2863a1`. The original evidence remains one
failed request, 79 untouched cells, zero completed cells and zero model replies.

The prepared child location is
`runs/paid_smoke_gpt41mini_20261115/segments/deepseek_primeintellect_v2`.
It retains the same 80 planned cell IDs, smoke seeds 1100–1103, load 2 and
schedule seed 271828. It adds no new experimental cases or spending allowance.
The changed source/model reissue is explicitly versioned; it is not an identical
retry and cannot overwrite or normalize the original failed request. There is
no successful or invalid model decision to resample. Shared budget and attempt
history remain in `runs/_paid_testing_session`.

After tests pass and the implementation is committed, prepare records offline:

```powershell
$env:PYTHONPATH = 'src'
python scripts/prepare_smoke.py --source-commit VERIFIED_SOURCE_COMMIT
```

Use the actual validated source commit, not an uncommitted tree or an invented
identifier. The script replays historical evidence without credentials or
network access and creates three records outside raw runs:

- `research/smoke_continuation.json`: source, input hashes and manifest mapping.
- `research/paid_smoke_cost_coverage.json`: coverage of the exact retained hold.
- `research/paid_smoke_authorization_amendment.json`: approved model preparation
  under the unchanged limits, explicitly `run_now:false`.

The script does not call the account/provider, claim an attempt or create the
empirical child segment. It refuses to silently replace differing prepared
records. Record hashes can be committed separately after the source commit,
avoiding a circular dependency on their own commit ID. Preparation is neither
an execution freeze nor permission to begin inference.

## Checks and the execution boundary

Run the required offline checks and repair failures before preparing delivery:

```powershell
python -m pytest -q
python scripts/verify_audit.py
python scripts/replay_history.py --run runs/paid_smoke_gpt41mini_20261115
git diff --check
```

The tests block network and isolate credentials. Record actual outcomes; do not
reuse a historical test count as validation of changed source. Preserve all
historical raw files and control journals during the check cycle.

After preparation records exist, this command performs public metadata and
authenticated account GET checks only:

```powershell
python -m beyond_label.paid_live --check-ready
```

The default `python -m beyond_label.paid_live` also checks readiness only. It
does not construct an inference transport, dispatch a completion, claim an
attempt, settle a cost or create empirical run outputs. A ready result means
the checked prerequisites permit a later smoke attempt; it does not verify
live inference behavior. Account/public checks are network reads, not offline
tests or model calls.

Only `--execute` selects inference, and it must not be used under the current
preparation-only instruction. A later explicit user request to run smoke must
still pass source, route, account, cost and attempt guards. Stop and report
before pilot or main, regardless of smoke outcome. No new human review or
research participation is implied by these engineering checks.
