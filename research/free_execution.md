# Free-only execution preparation

The user renewed authorization on the client date 15 November 2026: recheck the key, then continue milestones 4–6 using free calls only if the key hard limit is USD 0. The authenticated read-only check now succeeds, but reports **zero_hard_limit:false** and **50 of 50 free requests remaining**. This does not satisfy the condition, so no inference request was sent and both configuration execution flags remain disabled. Evidence: `research/checks/free_account_recheck.json`. The prior HTTP 401 and subsequent offline-only instruction remain historical records. No key or account setting was changed.

## Retained configuration

The free candidate is `nvidia/nemotron-3.5-super-vl:free`, routing slug `nvidia`, returned provider `Nvidia`. Current public endpoint metadata advertises zero input/output prices, context 1,000,000 tokens, max output 131,072, and tools, tool choice, temperature and reasoning controls. The study configuration fixes temperature 0, reasoning `enabled:false`, max output 512, parallel tools off, one concurrent request and no fallback. This is a pre-execution choice, not measured study performance. [Endpoint metadata](https://openrouter.ai/api/v1/models/nvidia/nemotron-3.5-super-vl:free/endpoints).

Native NVIDIA documentation supports parallel_tool_calls and reasoning disabled through reasoning_effort none. OpenRouter's model page supports disabling reasoning; its unified enabled:false mapping and strict-parameter forwarding still need a real smoke check. The gateway's supported-parameter list omits parallel_tool_calls. Preserve false and strict routing; do not silently drop the setting if delivery rejects it. [Native API reference](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3_5-super-vl-120b-a12b-infer), [OpenRouter model](https://openrouter.ai/nvidia/nemotron-3.5-super-vl:free).

The serialized request includes zero max_price for prompt, completion, request and image, one allowed provider and require_parameters:true. The HTTP adapter additionally rejects paid IDs, extra request features, server tools, non-text inputs and redirects. Provider metadata is requested and checked against the exact model/provider. No undocumented returned-model alias is accepted. [Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection).

OpenRouter documents a free limit of 20 requests/minute and daily tiers normally 50 or 1,000 requests. The actual daily used/limit/remaining counters must come from GET /api/v1/key, rather than an inference from is_free_tier. The latest successful check returned used 0, limit 50, remaining 50; it did not verify a zero hard spending limit. No purchase is authorized to obtain a higher tier. Provider TPM was not published in the reviewed sources; it remains null. The chosen local throttle is 10 RPM and 10,005,120 TPM, using a conservative whole-context-plus-512-output bound of 1,000,512 tokens per attempt. This is an operator throttle, not a claim about the provider's token limit. [Free model limits](https://openrouter.ai/collections/free-models), [Key status and limits](https://openrouter.ai/docs/api_reference/limits).

## Implementation and recovery

`openrouter.py` sends only to the fixed HTTPS origin, uses TLS verification, disables redirects and environment proxies, never logs credentials/headers, and leaves the three identical infrastructure retries to PinnedProvider. The account helper returns only the zero-hard-limit boolean and explicit daily request counters. A valid key must have a verified USD 0 hard ceiling before any free inference.

`live.py` holds a project-wide session lock across preflight and execution and shares a zero-dollar ledger across stages. Its constructed provider uses the budget/rate guard and account quota. No paid execution path is exposed. Unknown costs, accounting errors and incomplete reservations block restart until reconciled. Normal quota exhaustion suspends before a new attempt starts; a completed inspection can therefore resume its continuation without resampling. A UTC rollover after a rate wait stops before HTTP dispatch and retains a conservative pending reservation for explicit reconciliation.

The empirical harness validates the full deterministic manifest, pinned settings, execution gates and the concrete transport implementation. Stored provenance is a local execution assertion, not cryptographic proof of a provider response. Fixtures retain synthetic labels; tests of empirical reporting use explicit temporary mocks and are excluded from research outputs. Unmatched started attempts appear as unknown-cost rows. Total cost remains null when evidence is incomplete, with the known subtotal separately available.

Pilot summaries verify raw traces and derived artifacts before applying the unchanged 14/16 ceiling and 12/16 floor. Freeze preparation requires complete real gate traces, the chosen load, conditional load-8 smoke, unchanged current and committed input hashes, and the committed main manifest. Each free gate must also have complete zero-cost evidence without unknown charges or accounting errors. Verification checks the local tag against the commit and replays retained gate evidence. Preparation creates no tag or record; Git delivery and remote verification must still occur before main. No freeze was created in this checkpoint.

## Offline reproduction and future use

```powershell
python -m pytest -q
python scripts/verify_audit.py
python -m pytest -q tests/test_openrouter.py tests/test_free_provider.py tests/test_free_run.py tests/test_live.py tests/test_freeze.py
```

The following future commands are **blocked by the shipped configuration**. Conditional free-only authorization now exists, but the provider-side zero hard limit remains unmet; do not toggle flags merely because these commands exist.

```powershell
$env:PYTHONPATH = 'src'
python -m beyond_label.live --preflight
python -m beyond_label.live --dataset smoke --output runs/free_smoke_load2
python -m beyond_label.live --dataset pilot --output runs/free_pilot_load2
python -m beyond_label.pilot runs/free_pilot_load2
```

If the real pilot selects load-8, run its required four-world smoke before freezing. If NUMERIC is below 12/16, record the attempt and repeat the pilot with a separately pinned available free model; never route automatically or discard individual outcomes. No main command can pass without verified freeze evidence. Real quota may require multiple UTC days; each restart checks fresh account evidence and preserves completed cells.

The exact current blocker is the absence of a verified USD 0 hard limit on the authenticated key. Set that limit on the same OpenRouter key used by the ignored `.env`, then request a recheck. Free-only authorization need not be requested again. After that condition is satisfied, actual quota/delivery checks and real smoke/pilot gates remain required. The observed quota of 50 requests per day is smaller than the 80 initial cells in the full smoke manifest, so completion may require multiple quota windows; do not shrink the design or buy credits to bypass this constraint. Real smoke/pilot counts are zero, no load has been selected from observations, no humans performed H1-H5 review, and experimental API expenditure is USD 0.

## Historical recheck and initial 10-attempt allowance

The user now permits at most 10 aggregate free inference attempts, conditional on a verified USD 0 key hard limit. The latest check still returns `zero_hard_limit:false`, quota used 0 / limit 50 / remaining 50 (`research/checks/free_account_recheck_10_call_cap.json`). The loader uses the ignored project `.env`; no inherited OpenRouter key variable overrides it (`research/checks/free_key_source_10_call_cap.json`). No account setting or credential value was changed or disclosed.

Keep execution disabled. The 10-attempt allowance includes initial calls, retries, re-prompts and continuations across runs/resumes. Existing `max_cells` counts cells, and the in-memory daily quota resets on invocation; neither implements this new aggregate ceiling. Before enabling any future inference, enforce the remaining allowance against durable attempt history under the project lock. This checkpoint performs no inference and introduces no execution-input changes. Ten attempts cannot complete the 80 initial smoke cells; do not reduce the design or present a partial run as a passed smoke gate.

## Implemented durable allowance

The user explicitly requested implementation. Both the free CLI and lower-level real `run_manifest` now require the shared ten-attempt policy. `attempts.py` appends a hash-linked integer reservation, flushes and fsyncs it before `attempt_started`; it never refunds a claim. An interrupted pre-dispatch reservation consumes capacity but is not reported as a model call or financial charge. The counter is separate from the USD budget ledger. Process locks serialize claims, and the live owner also retains the project lock.

On restart, raw run manifests/journals and monetary reservations are reconciled with the counter. Missing counter history, altered caps, inconsistent counts, torn/corrupt records and failed durable writes block further dispatch. A completed resume consumes no extra slot. A new output directory or UTC day cannot reset the allowance. Model decisions and invalid outcomes are not resampled. This is local protection against execution errors, not protection against deliberate deletion of every evidence file.

The fixed configuration field is `maximum_inference_attempts: 10`. No larger allowance is authorized. Such a future change requires explicit user authorization and preservation/migration of existing attempt history; simply editing the cap is rejected. Current key evidence (`research/checks/durable_cap_account_preflight.json`) still reports authenticated but `zero_hard_limit:false` with 50 remaining free requests. Consequently no real attempt journal or smoke run was created, both execution flags remain disabled, and cost is USD 0.
