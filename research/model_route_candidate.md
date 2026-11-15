# Approved replacement preparation

The user approved preparing `deepseek/deepseek-v4.1-flash-1017` through
OpenRouter route `primeintellect`, expected provider identity `PrimeIntellect`,
under the unchanged USD 10 total testing / USD 1 smoke / 200 aggregate-attempt
caps. **Preparation only: no inference now.** The original candidate was
unapproved when first documented; this explicit decision changes that status.
It does not authorize pilot, main, another smoke allowance or publication.

The exact dated ID is pinned in `configs/paid_smoke.yaml`, with no returned-model
aliases or fallback. The [public endpoint record](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash-1017/endpoints)
lists the PrimeIntellect endpoint, 1,048,576 context tokens, 131,072 maximum
completion tokens, automatic tool choice and every requested decision control.
The anonymous profile check returned HTTP 200 and compatible metadata. This is
route evidence, not a successful model call or verification of effective
behavior, hosted weights, quantization or actual returned identity. The safe
evidence is [smoke_route_readiness.json](checks/smoke_route_readiness.json).

The prepared settings are temperature 0, maximum output 512, automatic tool
choice, `parallel_tool_calls:false`, strict parameter support and no fallback.
Reasoning is explicitly `{"effort":"none"}`. The
[model catalog](https://openrouter.ai/api/v1/models) reports reasoning as optional,
enabled by default, and accepting `none`; the
[reasoning documentation](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)
defines that effort as disabled. Omitting reasoning would not express the
chosen setting. Tool-free readback omits all tool-only fields while preserving
the same decision prefix and fixed model settings.

The exact endpoint lists USD 0.04368 per million input tokens and USD 0.70 per
million output tokens. Reserving the full advertised input context plus 512
output tokens, with a 5% margin, gives USD 0.048468209664. Request/image prices
are absent and remain unknown. Explicit router `max_price` ceilings of zero
for those fees enforce admissibility; the absence is not treated as observed
zero billing. [Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection)
documents these ceilings. Unknown new billing still retains its reservation
and stops further dispatch.

The old GPT request remains one consumed attempt with no model reply and a
USD 0.44084208 hold. A distinct pre-freeze source-continuation record must bind
the repaired code/model to the same 80-cell plan, preserving that failed trace
and the shared limits. Its reissued cell is not an identical retry or a
replacement of a completed decision. [Current preparation procedure](smoke_readiness.md)
explains conservative coverage, source records, validation and the no-execution
boundary. No smoke or full-suite pass is claimed by this route document.
