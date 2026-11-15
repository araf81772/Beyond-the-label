# Unapproved replacement smoke candidate

This is a read-only planning record. The user's active authorization names
GPT-4.1 mini / OpenAI. No replacement is enabled, no candidate call was made,
and no main or pilot execution is authorized.

Candidate: `deepseek/deepseek-v4.1-flash-1017`, OpenRouter route `primeintellect`,
expected provider identity `PrimeIntellect`. The dated model ID avoids a
`latest` router. Its [public endpoint record](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash-1017/endpoints)
lists available status, 1,048,576 context tokens, 131,072 maximum completion
tokens, and the required temperature, max_tokens, tools, tool_choice and
parallel_tool_calls controls. The direct DeepSeek route omits the last control;
it is not the proposed route.

Proposed settings, subject to approval and validation: temperature0,
max_tokens512, tool_choice `auto`, parallel_tool_calls `false`,
reasoning `{"enabled":false}`, strict parameter enforcement and no fallback.
The [model catalog](https://openrouter.ai/api/v1/models) declares optional
reasoning; [OpenRouter documents the toggle](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).
[DeepSeek's thinking guide](https://api-docs.deepseek.com/guides/thinking_mode/)
explains that temperature is ignored while thinking, so effective reasoning
disablement must be verified before interpreting a run as temperature0.

Listed token prices are USD0.04368 per million input tokens and USD0.70 per
million output tokens. A full-context-plus512-output calculation with an extra
5% is USD0.048468209664. **That is a conditional token-price calculation, not a
verified all-fees reservation.** Request and image prices are absent, not
explicit zero. The [official OpenAPI schema](https://openrouter.ai/openapi.json)
makes those fields optional and supplies no default-zero rule. Full billing
readiness, actual delivery, returned identity, effective reasoning setting,
quantization and hosting implementation remain unverified.

Changing the model/provider pin requires the user's decision. Before any
replacement call, resolve all readiness gaps, test the revised integration,
record a distinct pre-freeze execution version, and carry forward the consumed
attempt and retained cost reservation. Do not reset either allowance, repeat
successful/invalid model decisions, or relabel the failed GPT-4.1 mini request.
