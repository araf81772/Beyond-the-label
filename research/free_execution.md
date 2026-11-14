# Free-only execution preparation

On 14 November 2026, the user requested free inference and no paid calls. A read-only OpenRouter key-status request returned **HTTP 401**. No inference request was sent. The user then instructed: **“Finish offline work only.”** That is the current execution boundary. `configs/free.yaml` disables both real execution and account preflight. No key or account setting was changed; the key remains local to the ignored `.env`.

## Retained configuration

The free candidate is `nvidia/nemotron-3.5-super-vl:free`, routing slug `nvidia`, returned provider `Nvidia`. Current public endpoint metadata advertises zero input/output prices, context 1,000,000 tokens, max output 131,072, and tools, tool choice, temperature and reasoning controls. The study configuration fixes temperature 0, reasoning `enabled:false`, max output 512, parallel tools off, one concurrent request and no fallback. This is a pre-execution choice, not measured study performance. [Endpoint metadata](https://openrouter.ai/api/v1/models/nvidia/nemotron-3.5-super-vl:free/endpoints).

Native NVIDIA documentation supports parallel_tool_calls and reasoning disabled through reasoning_effort none. OpenRouter's model page supports disabling reasoning; its unified enabled:false mapping and strict-parameter forwarding still need a real smoke check. The gateway's supported-parameter list omits parallel_tool_calls. Preserve false and strict routing; do not silently drop the setting if delivery rejects it. [Native API reference](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3_5-super-vl-120b-a12b-infer), [OpenRouter model](https://openrouter.ai/nvidia/nemotron-3.5-super-vl:free).

The serialized request includes zero max_price for prompt, completion, request and image, one allowed provider and require_parameters:true. The HTTP adapter additionally rejects paid IDs, extra request features, server tools, non-text inputs and redirects. Provider metadata is requested and checked against the exact model/provider. No undocumented returned-model alias is accepted. [Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection).

OpenRouter documents a free limit of 20 requests/minute and daily tiers normally 50 or 1,000 requests. The actual daily used/limit/remaining counters must come from GET /api/v1/key, rather than an inference from is_free_tier. Our failed authentication established none of those account values. No purchase is authorized to obtain a higher tier. Provider TPM was not published in the reviewed sources; it remains null. The chosen local throttle is 10 RPM and 10,005,120 TPM, using a conservative whole-context-plus-512-output bound of 1,000,512 tokens per attempt. This is an operator throttle, not a claim about the provider's token limit. [Free model limits](https://openrouter.ai/collections/free-models), [Key status and limits](https://openrouter.ai/docs/api_reference/limits).

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

The following future commands are **blocked by the shipped configuration**. They are documented for renewed free-only authorization after the key is fixed; do not toggle flags merely because these commands exist.

```powershell
$env:PYTHONPATH = 'src'
python -m beyond_label.live --preflight
python -m beyond_label.live --dataset smoke --output runs/free_smoke_load2
python -m beyond_label.live --dataset pilot --output runs/free_pilot_load2
python -m beyond_label.pilot runs/free_pilot_load2
```

If the real pilot selects load-8, run its required four-world smoke before freezing. If NUMERIC is below 12/16, record the attempt and repeat the pilot with a separately pinned available free model; never route automatically or discard individual outcomes. No main command can pass without verified freeze evidence. Real quota may require multiple UTC days; each restart checks fresh account evidence and preserves completed cells.

The exact current blocker is rejected authentication plus the user's restored offline-only instruction. Minimum future actions: a valid OpenRouter key with a zero hard spending limit, renewed free-only execution authorization, and successful quota/delivery checks. Real smoke/pilot counts are zero, no load has been selected from observations, no humans performed H1-H5 review, and experimental API expenditure is USD 0.
