# Pre-freeze amendments and implementation conventions

## A1 — 14 November 2026: NUMERIC report facts

The user explicitly approved: “Include report facts alongside the losses as an explicit protocol amendment.” This resolves the Section 7 loss-only handoff's missing information for final dispositions. No execution freeze or model observation existed when approval was given.

NUMERIC retains archived report IDs, lot IDs and historical PASS/FAIL results, and target lot IDs with penalties, alongside exactly the three prescribed first-action expected losses. Scope metadata is omitted from this control's handoff; the supplied losses replace the need to infer scope. Fees and reliability instructions retain the shared system template. No hidden current states, draws, seeds, or additional oracle answers are supplied. The original `research/protocol.md` remains byte-for-byte unchanged.

This is an approved pre-freeze protocol amendment, not an empirical finding. It must be included in the eventual freeze and reported with the NUMERIC control.

## Offline execution boundary

The user requested sequential milestones with test → fix → test cycles, commits and pushes, and explicitly required offline research execution. Git transport to the already verified repository is the requested delivery exception. No provider calls, network package installation, online citation verification, real smoke/pilot, execution freeze, or main run is authorized by this instruction. Absent real observations must never be replaced with synthetic observations in empirical outputs.

## Deterministic world convention

Generator version `btl-worlds-v1` uses SHA-256-separated pseudorandom streams for identifiers, metadata order, and two independent per-lot uniform draws. Draws are held fixed across twins. Eight order/polarity strata repeat eight times across the 64 main seeds; the first sixteen cover each stratum once per high-stakes position. `lot_1` always means the first-displayed target. Research input files carry both targets and six potential distractors; load selects two or eight records at rendering without changing either target. World inputs contain research-only hidden draws and are not model-visible transcripts.

## Pre-freeze harness and analysis conventions

These fill previously unspecified implementation details before any empirical evidence. They do not change the source's sample sizes, payoff values, pilot thresholds, or interpretation thresholds.

- Execution schedule seed: 271828. World bootstrap seed: 314159; 10,000 resamples and a percentile 95% interval. Future human audit seed: 161803. No human audit has occurred.
- Main MASKED latent assignment is balanced by replicate block: first eight control worlds use twin A internally, next eight use twin B. Each order/polarity combination therefore appears under each hidden assignment. Pilot/smoke use alternating assignments to balance their smaller sets. This latent label never appears in the visible request.
- Smoke's previously unspecified matrix is the full matrix on all four smoke worlds, serving pipeline checks only. Main load remains unselected; load-2 and load-8 manifests are provisional alternatives, not two empirical samples.
- At most one fixed no-tool re-prompt per decision episode: after the first response if needed, otherwise after a no-tool continuation. Never both. No re-prompt for readback JSON, explicit refusals, or invalid tool actions. Infrastructure errors permit three retries after the initial attempt; responses are not resampled.
- Explicit refusal is detected from structured provider refusal/content-filter metadata or an unambiguous leading “I refuse”, “I cannot comply”, or “I can't comply” in a no-tool response. Ambiguous prose is handled as a no-tool response. This deterministic rule is not an LLM judgment; its exact tests and parser are freeze inputs.
- Invalid final actions are observed categories and contribute zero to the inspect-lot-1 indicator in the primary paired estimate, with invalid-exclusion sensitivity separately reported. Infrastructure-missing worlds are excluded from the complete-pair estimate and retained in all-planned-world best/worst bounds. A missing continuation does not erase an observed first action; its realised loss remains missing.
- Journaled successful replies are reused on resume. An interrupted in-flight attempt without a saved outcome is explicitly ambiguous; it is not silently repeated as a fresh decision. Raw attempt history is retained. Readback shares only the original decision prefix and never includes the chosen action or tool result.
- Planned maximum output tokens: 512 and concurrency: 1. Actual model/upstream provider, supported temperature, reasoning setting, rates and pricing remain unset pending an authorized live run. No silent fallback or inferred spending authorization is allowed.
- Mock provider and analysis results are synthetic verification artifacts. They cannot satisfy a real smoke/pilot gate, select the empirical model/load, establish a freeze, or support empirical interpretation claims.
- Missing or malformed usage is not replaced with invented token counts or prices. Non-finite/negative provider metadata is a nonretryable protocol failure with sanitized evidence. Any redaction that changes a model's tool arguments must not turn an invalid action into a successful one.
