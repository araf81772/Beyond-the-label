# Milestone 4: proposed settings and remaining prerequisites

Historical paid-model proposal. The user later requested a free route and then returned to offline-only work following an HTTP 401 key preflight. See `research/free_execution.md` for the current configuration and blockers. No paid proposal was activated.

Recorded 14 November 2026. The user delegated future configuration choices and authorized read-only public documentation/pricing research. This does not authorize inference, account requests using the key, credit purchases or spending. No model response or experimental cost was observed. Active pilot/main configs remain disabled and unset; `configs/proposed_m4.yaml` is a planning record only.

## Proposed choice

Use OpenRouter model `openai/gpt-4.1-mini`, routing slug `openai`, expected returned provider `OpenAI`, temperature 0, reasoning omitted/not applicable, 512 maximum output tokens, tool choice `auto`, parallel tool calls off, provider fallbacks off, strict parameter support and concurrency 1. These choices favor inexpensive, non-reasoning tool use with explicit sampling control for this protocol. They are an engineering judgment, not evidence of performance on this study.

The public [endpoint record](https://openrouter.ai/api/v1/models/openai/gpt-4.1-mini/endpoints) advertises the OpenAI route at USD 0.40 per million input tokens, 1.60 per million output tokens and 0.10 per million cached input tokens. It lists tools, tool choice, temperature and max_tokens support; its endpoint name references `gpt-4.1-mini-2025-04-14`, while the canonical model ID remains `openai/gpt-4.1-mini`. Neither the endpoint label nor a returned alias proves immutable upstream weights.

OpenAI lists this snapshot and GPT-4.1 as deprecated, with upstream shutdown scheduled for **14 January 2027**. This limits future replication; recheck availability before an authorized run. It is not a separately verified OpenRouter shutdown announcement. [Official deprecations](https://developers.openai.com/api/docs/deprecations).

If the prescribed NUMERIC floor fails, the proposed repeat-pilot candidate is `openai/gpt-4.1`, pinned to the same named provider, with the same sampling settings. Its listed input/output prices are USD 2/8 per million tokens. This is a new recorded pilot attempt subject to the remaining cap, never an automatic routing fallback or a way to discard unfavorable outcomes. [GPT-4.1 endpoint record](https://openrouter.ai/api/v1/models/openai/gpt-4.1/endpoints).

The public GPT-5.4-mini endpoint is a newer alternative, but its advertised supported parameters omit temperature; applying the design's fixed-default exception would need a separate verified setting contract. The current proposal prioritizes explicit temperature support; it does not claim GPT-4.1 mini is the most capable model. [GPT-5.4-mini endpoint record](https://openrouter.ai/api/v1/models/openai/gpt-5.4-mini/endpoints).

## Budget proposal and billing evidence

Propose **USD 20 total inference expenditure for milestone 4**, shared across smoke, pilot, conditional load-8 smoke, retries, permitted re-prompts and any required repeat pilot. This ceiling is not an estimate of actual cost, not approved spending, and excludes main execution and credit purchases. Active `authorized_spend_cap` stays null. Stop before another attempt when the remaining cap cannot cover its verified conservative bound; request any increase separately.

The initial smoke and pilot plan allows 432 calls, or 576 with conditional load-8 smoke, before extra retries/re-prompts/repeat pilots. Actual prompt lengths and failures determine expenditure. Do not count unused credits as authorization. OpenRouter documents `usage.cost` as charged credits and credits as USD-denominated; no separate response currency field is assumed. Credit purchase fees are separate from inference usage and must not be presented as included without account evidence. [Usage accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting), [USD credit system](https://openrouter.ai/support/).

Design Section 14 requires a hard key spend limit based on three times the pilot projection. The real projection is unavailable until authorized pilot evidence exists. Before pilot, a dedicated key must have a hard ceiling within the authorized M4 cap; before main, reconcile the real pilot projection and its three-times limit with a separately authorized remaining budget. Do not silently raise the authorized cap to satisfy that calculation.

## Verified documentation and unresolved delivery

Provider routing uses `only: [openai]`, `allow_fallbacks: false` and `require_parameters: true`. Strict parameter support rejects unsupported requests rather than silently dropping controls. [Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection).

The selected endpoint's supported-parameter list omits `parallel_tool_calls`, although the general API documents that field. Preserve `parallel_tool_calls: false` and strict parameter support; do not assert this combination has passed live delivery. Public documentation alone does not resolve the omission. Real smoke must verify it once paid calls are explicitly authorized. [API parameters](https://openrouter.ai/docs/api_reference/parameters).

Routing identity is requested through the noncredential `X-OpenRouter-Metadata: enabled` header. The response schema documents `openrouter_metadata.endpoints.available` entries containing provider, model and a selected flag. The adapter requires exactly one selected entry with matching model/provider, and rejects missing or contradictory evidence. A top-level provider field is not assumed to be guaranteed. Current tests use locally constructed schema fixtures. No HTTP transport exists yet. [Chat completion schema](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion).

The API describes max_tokens as deprecated in favor of max_completion_tokens, while the chosen endpoint still lists max_tokens. The current serializer preserves its existing max_tokens field. Reasoning is omitted for this non-reasoning proposal; a model with reasoning would need explicit supported settings and a total output/reasoning budget. Usage is returned automatically; a deprecated usage-inclusion flag is unnecessary. [Chat completion schema](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion), [Usage accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting).

## Offline safeguards and remaining work

`budget.py` supplies an append-only, hash-linked, process-locked decimal ledger. Reservations precede dispatch, unknown costs retain their full bounds, and known overruns stop further dispatch without intentionally resampling the response. `rate_limit.py` reserves requests and total token bounds over a sliding minute. `controls.py` combines them around an injected transport and enforces one in-flight call. These components do not authorize calls or establish provider-side charge limits.

Before live execution, implement and mock-test the HTTP adapter and its integration with the manifest runner, durable attempt reconciliation, verified token/cost bounds and execution gates. The existing real-execution gate still expects a reasoning mapping and a scalar rate; it must explicitly handle this non-reasoning mode and separate request/token limits. Do not bypass it with fabricated values. Preserve raw returned decisions even if local accounting fails, stop subsequent dispatch, and reconcile the failed accounting before any restart.

Account-specific limits and key hard-limit evidence remain unknown. The rate limiter is local to one process; it cannot account for other applications using the same key. A live owner must enforce a dedicated key and single process or add shared rate ownership. A ledger cannot prevent an upstream charge above the quoted bound, so provider-side limits and conservative verified bounds remain necessary.

The only credential needed for the proposed route is `OPENROUTER_API_KEY` in the user's ignored project-root `.env` (or process environment). Presence was checked locally; authentication is unverified. No additional secret belongs in configs, prompts or logs. No human H1-H5 review has occurred. Model/load selection based on actual pilot outcomes, execution freeze, main observations and an empirical report remain absent.
