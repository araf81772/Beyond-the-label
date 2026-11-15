# Authorized paid smoke checkpoint

User authorization, 15 November 2026 (Australia/Sydney): USD 10 total for testing,
paid GPT-4.1 mini calls via OpenRouter/OpenAI allowed. Execute **one smoke only**,
stopping at **USD 1 or 200 total attempts**, including retries, re-prompts and
continuations. Stop and report before pilot or main. No purchase, alternate model,
additional run, pilot or main is enabled by this authorization.

Three authenticated read-only checks found the same nonreset USD 100 key limit, USD 100 remaining and zero usage. The latest check at 2026-11-15T00:39:57Z still fails the execution guard's USD 10 ceiling. The user acknowledged the request to reduce it, but the setting change is not yet evidenced. See `checks/paid_smoke_account_final_check.json` and the retained earlier checks. No inference has occurred. Set the existing key limit to USD 10 with no reset and request a fresh check; no new spending authorization is needed for this same smoke.

## Fixed run and settings

- Config: `configs/paid_smoke.yaml`.
- Output: `runs/paid_smoke_gpt41mini_20261115` only.
- Shared durable controls: `runs/_paid_testing_session`; never reset or delete.
- Four smoke seeds 1100–1103, load-2, schedule seed 271828: 80 initial cells,
  at most 64 planned continuations, 144 planned calls before permitted extras.
- Requested model `openai/gpt-4.1-mini`, upstream route `openai`, provider identity
  `OpenAI`; no fallback or automatic model switch.
- Temperature 0, reasoning omitted/not applicable, 512 maximum output tokens,
  automatic tool choice, parallel calls off, strict parameter support,
  concurrency 1. The one permitted no-tool re-prompt is unchanged.
- Up to three infrastructure retries after the initial attempt; no retries of
  invalid model decisions. Unknown charge evidence can suspend execution before
  a retry pending reconciliation.
- Price ceilings: USD 0.40/1.60 per million input/output tokens, no request/image
  fees. Exact documented snapshot identities may be returned; retain the actual
  identity in raw traces. No wildcard model aliases are accepted.

## Verified bounds and limits

The [OpenRouter endpoint record](https://openrouter.ai/api/v1/models/openai/gpt-4.1-mini/endpoints)
lists the named OpenAI route, 1,047,576 context tokens, 32,768 maximum completion
tokens, and USD 0.40/1.60 input/output prices per million tokens. The
[official OpenAI model page](https://developers.openai.com/api/docs/models/gpt-4.1-mini)
identifies snapshot `gpt-4.1-mini-2025-04-14` and no reasoning step. Public metadata
does not prove actual delivery or immutable upstream weights. The upstream model
is deprecated; this authorization does not permit replacing it.

Reserve the full advertised context as input plus all 512 allowed output tokens:
`(1047576 × 0.40 / 1000000 + 512 × 1.60 / 1000000) × 1.05 = USD 0.44084208` per attempt. The extra 5% covers OpenRouter's documented maximum BYOK fee if an account-connected upstream key is selected.
This intentionally overcounts any shared context allowance and does not rely on
an unverified character-to-token estimate. An explicitly identified ordinary OpenRouter charge releases the unused reservation. For BYOK, the accounted total includes the reported upstream charge plus OpenRouter fee. Missing billing-mode or cost evidence retains the reservation and stops further calls. The raw provider usage fields are preserved separately from the derived total.
Execution may stop below USD 1 if the remainder cannot cover the next bound.

The provider key must have a positive, nonreset hard limit at most USD 10 and
enough remaining budget for a reservation. The local shared ledger enforces the
separate USD 1 smoke subcap over total accounted charges. The initial key metadata has `include_byok_in_limit:false`; its provider-side limit alone would not cover upstream BYOK charges. The conservative local reservation and total-cost settlement are therefore required in either billing mode. [BYOK billing](https://openrouter.ai/docs/guides/overview/auth/byok) and [usage accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting) supply the mode/charge semantics. The later design rule based on three times actual
pilot projection cannot be evaluated before pilot and is not waived for main.
The [provider routing documentation](https://openrouter.ai/docs/guides/routing/provider-selection)
defines price ceilings and strict pinning; the
[limits documentation](https://openrouter.ai/docs/api_reference/limits) defines
key limits and remaining budget. Operator pacing is 10 requests/minute with a
10,480,880-token conservative allowance. Upstream request/token rate guarantees
are unpublished, not fabricated as equivalent to the operator throttle.

## Commands and evidence boundaries

After required tests and authenticated prerequisites pass, run from the project:

```powershell
$env:PYTHONPATH = 'src'
python -m beyond_label.paid_live
```

The entry point rejects pilot, main, a different output, changed spending limits,
changed provider/settings and inconsistent history. A completed resume must add
zero inference calls. Account checks do not count as inference attempts.

Smoke traces are engineering evidence, excluded from primary estimands, pilot
selection and main results. M4 cannot pass without the real pilot and freeze;
neither is authorized in this checkpoint. No H1-H5 human review is inferred.
The earlier report remains a pre-results archive tied to its source version;
its no-inference statements must not be regenerated as current after smoke.

Tests, observed outcomes, repairs and delivery are recorded in the decision log,
`milestones.json` and `checks/paid_smoke_*.json`. Preparation is not a passed smoke.

Integrated validation: **1201 offline tests passed in 339.56s**, including T1–T8 and the full mocked smoke/resume path. Integrity, dependency and diff checks passed. See `checks/paid_smoke_suite.json` and `checks/paid_smoke_validation.json`. Actual smoke attempts and inference cost remain **0 / USD 0**; no freeze was created.
