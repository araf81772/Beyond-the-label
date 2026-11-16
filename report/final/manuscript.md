# THE LABEL SURVIVED. WHICH CASE DID THE AGENT CHECK?

Tonmoy Sarker, Araf Akhter and Abidur Rahaman

## Abstract

Provenance labels can remain intact during an agent handoff without determining what the receiving agent verifies. We test whether a model uses report-level scope to allocate one priced inspection. In matched synthetic worlds, two archived reports retain their facts, identifiers, order and payoffs while their tested-configuration labels exchange places. An analytic expected-loss oracle identifies the optimal action. The frozen main experiment evaluated DeepSeek V4.1 Flash through OpenRouter/PrimeIntellect in 704 cells: 448 decision episodes and 256 independent-context readbacks across 64 worlds, with payoff and information controls on 16 worlds. The mean paired allocation effect was 0.9375 in separate layout (95% world-bootstrap interval 0.875 to 0.984375) and 0.921875 inline (0.859375 to 0.984375); the oracle reference is 1. Readback was correct in every branch. The results meet the predeclared, bounded "no gap here" criterion, but do not imply perfect action: fully correct twin pairs numbered 57/64 and 55/64, and high-stakes optimality was 52/64. Sixteen invalid continuations and one missing continuation remain in the evidence. Withheld-scope interpretation is limited by first-reply truncation in 21/32 cells. The study contributes an auditable scope-binding intervention and shows strong scope-sensitive verification under explicit reliabilities, alongside residual payoff and execution failures.

## 1. Introduction

Trust infrastructure preserves information about where evidence applies. Its practical value also depends on whether the receiving agent uses that information when deciding what to check. A readable scope label is therefore an intermediate property, not evidence of a good verification decision.

Beyond the Label tests this distinction with a narrowly controlled intervention. Two archived reports are held fixed while their scope assignments are exchanged. The optimal inspection changes, and the agent must enact its choice through a tool call that has a stated price. Separate readbacks measure whether the labels can be recovered without entering the decision context. Fee and stakes controls test whether apparent success reflects useful verification rather than unconditional checking.

The contribution is a fixed-report scope-binding swap with audited delivery and enacted verification under changing payoffs. In this experiment, the pinned model generally followed reassigned scope. The informative failures concern incomplete twin-pair success, asymmetric stakes and execution constraints. We report the favorable primary result and these limitations together.

## 2. Related work

Nakayashiki [1] studies stale inherited constraints and scarce verification. Forced reassignment to a critical provenance path uses experimenter knowledge and is a diagnostic intervention, not a deployable scheduler. Our intervention exchanges report-to-scope bindings while preserving report facts, with priced verification judged against an exact oracle.

Fan et al. [2] show how supported facts and visible rule boundaries can coexist with scope misapplication in adversarial retrieval-augmented generation. Explicit probes can recognize inapplicability despite default misuse. Our readbacks similarly separate recognition from action, but are independent branches and do not establish a causal pathway from recognition to a particular decision.

Chu and Huang [3] distinguish evidence sensitivity from appropriate reliance on imperfect partners using sequential decisions and analytically evaluable consequences. We use a smaller environment to isolate scope reassignment and one inspection opportunity. These studies motivate the components; we do not claim an exhaustive novelty search or generalize their empirical rates to our task.

## 3. Methods

### 3.1 Task and intervention

An agent must RELEASE or HOLD two lots. RELEASE is correct for a true PASS state; HOLD for FAIL. Each lot has an archived binary report. A report tested under the current configuration has stated accuracy 0.90; another configuration has accuracy 0.60. Exactly one target report is in scope. The agent may call inspect(lot_id) once, paying the stated fee for that lot's exact state, then commit dispositions for both targets. Its sole stated objective is to minimize expected points lost.

Twin A makes the first-displayed target out of scope; twin B reverses the assignments. Only the two tested_configuration values change in the model-visible handoff. Report results, record and lot IDs, report order, current configuration, penalties and fees remain fixed. Separate layout puts scope in a record-ID-keyed metadata table; inline places it beside each report. The selected load includes two targets and six non-target records. Deterministic code renders the handoff; no generative relay intervenes.

Seeded draws generate hidden states with the stated reliabilities. Reusing draws across twins couples realised outcomes while preserving each assignment's distribution. Hidden states, draws, seeds and answer keys stay outside model requests. Inspection reveals only the inspected state. NUMERIC supplies its prescribed first-action losses as the sole oracle-information exception.

### 3.2 Oracle and controls

For accuracy q_i, error penalty P_i and fee f, following both archived reports costs (1 - q_1)P_1 + (1 - q_2)P_2 in expectation. Inspecting lot i and continuing optimally costs f plus the other lot's expected error penalty. Contrary unchecked dispositions instead incur q_i P_i. Table 1 gives analytic references, not observations. Expected first-action regret is the chosen action's expected loss under optimal continuation minus the minimum feasible loss.

Table 1. Analytic expected losses in points. X denotes the first-displayed lot, except H denotes the high-penalty lot in HIGH-STAKES. The smaller inspection loss is optimal in MAIN and HIGH-STAKES; commitment is optimal in HIGH-FEE. Both MASKED inspections are optimal.

| Condition and assignment | Penalties; fee | Commit with reports | Inspect X or H | Inspect other |
|---|---|---:|---:|---:|
| MAIN, X out of scope | 100/100; 20 | 50 | 30 | 60 |
| MAIN, X in scope | 100/100; 20 | 50 | 60 | 30 |
| HIGH-FEE, X out of scope | 100/100; 60 | 50 | 70 | 100 |
| HIGH-FEE, X in scope | 100/100; 60 | 50 | 100 | 70 |
| HIGH-STAKES, H out of scope | 800/100; 20 | 330 | 30 | 340 |
| HIGH-STAKES, H in scope | 800/100; 20 | 120 | 60 | 100 |
| MASKED, scope identity withheld | 100/100; 20 | 50 | 45 | 45 |

HIGH-FEE tests whether checking stops when its price exceeds its value. HIGH-STAKES makes the high-penalty lot optimal to inspect regardless of scope. MASKED withholds scope while stating that exactly one report is in scope. NUMERIC supplies MAIN losses directly, retaining report facts and IDs under the documented amendment so dispositions remain possible. MAIN reference losses are 30 for the oracle, 50 for immediate report-following commitment and 45 for uniformly choosing one inspection, assuming optimal continuation.

### 3.3 Sample and execution

The main sample has 64 worlds: 256 MAIN decisions and 256 separate-context readbacks. The first 16 worlds supply 64 HIGH-FEE, 64 HIGH-STAKES, 32 MASKED and 32 NUMERIC cells. Thus 704 cells comprise 448 decisions and 256 probes, not 704 independent decisions. Primary uncertainty is clustered by world. Counterbalancing covers report order and polarity; control worlds balance the high-stakes lot's position.

An eight-world load-2 pilot produced 15/16 fully correct MAIN pairs and 15/16 optimal NUMERIC decisions. The unchanged ceiling rule selects load-8 at 14/16 pairs; the floor requires at least 12/16 NUMERIC successes. Complete load-2 and load-8 smokes validated the pipeline. Smoke and pilot observations are excluded from main estimates.

The requested and top-level returned model ID was deepseek/deepseek-v4.1-flash-1017 through OpenRouter, pinned to PrimeIntellect with no fallback: temperature 0, reasoning effort none, maximum output 512 tokens, automatic tool choice and parallel tools disabled. Every cell started in a fresh context; readbacks had no tools and received neither action nor inspection result. Seeded interleaving used 271828. At most one fixed re-prompt was allowed across a decision episode: after a no-tool first response or, if unused, a no-tool continuation, never both. Its exact text was "Respond with exactly one tool call." Readbacks and refusals were not re-prompted. Invalid decisions were retained, not resampled. Infrastructure errors allowed three retries after the initial attempt; these preserved the request and were separate from decision sampling.

The scientific freeze preceded main collection. An operational continuation later completed the remaining cells with unchanged scientific inputs, retaining earlier observations and conservative billing holds. Appendix A reports timing deviations and Appendix B gives provenance and recovery details. We do not describe the study as perfectly preregistered.

### 3.4 Analysis and decision rules

The primary paired estimand in separate-layout MAIN is D_w = 1[inspect lot_1 in twin A] - 1[inspect lot_1 in twin B]. The oracle reference is +1. Invalid/refused first actions contribute zero to the inspection indicator, with an invalid-exclusion sensitivity reported separately. D is not the fully-correct-pair fraction: a pair can have D = +1 if twin A inspects lot_1 and twin B commits without inspection.

We use 10,000 whole-world bootstrap resamples, seed 314159, percentile 95% intervals, and an exact two-sided sign test on nonzero paired differences. The layout interaction is D_inline - D_separate. The frozen "no gap here" criterion requires lower D bounds of at least 0.80 in both layouts and pooled optimality of at least 0.80 in both payoff controls. "Gap found" requires readback and NUMERIC rates at least 0.90 and an upper separate-layout D bound below 0.80. A layout-benefit claim additionally requires a positive interaction lower bound, lower inline regret and no increase in HIGH-FEE checking. Thresholds did not change after freeze.

## 4. Results

### 4.1 Scope-sensitive allocation

All 704 first decisions/readbacks were observed. Separate-layout D was 0.9375 (95% interval [0.875, 0.984375]); inline D was 0.921875 [0.859375, 0.984375]. Separate pairs had 60 positive, zero negative and four tied differences (exact sign-test p = 1.73 x 10^-18). The interaction was -0.015625 [-0.109375, 0.078125], providing no demonstrated inline benefit. MAIN expected regret was 1.25 points separate and 1.40625 inline.

The frozen classification is "no gap here under these conditions." This is a threshold-based result, not a claim of zero error. All 256 readbacks were correct, yet seven separate and nine inline pairs were not fully correct (Table 2). Because probes ran in independent contexts, these are descriptive recognition-action comparisons rather than evidence that a particular decision was made after recognizing its scope correctly.

Table 2. MAIN twin-pair categories. Each layout contains 64 matched worlds; categories are mutually exclusive. A no-check pair has at least one immediate commitment. Allocation-effect D and complete-pair success measure different properties.

| Pair category | Separate | Inline |
|---|---:|---:|
| Both inspections correct | 57 | 55 |
| At least one commitment without inspection | 7 | 9 |
| Reversed / same-target / invalid / missing | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |

[[FIGURE1]]

Figure 1. First-action allocation versus the analytic oracle, pooled across layouts. Bars use all planned decisions in MAIN (n = 256), HIGH-FEE (n = 64) and HIGH-STAKES (n = 64). Lot 1 and Lot 2 denote displayed target positions; matching aggregate bars would not establish cell-level optimality. These three conditions had no invalid or infrastructure-missing first actions.

### 4.2 Payoff controls and residual failures

Optimal first actions occurred in 239/256 MAIN decisions, 63/64 HIGH-FEE decisions, 52/64 HIGH-STAKES decisions and 32/32 NUMERIC decisions. HIGH-STAKES pooled optimality, 81.25%, passed the threshold narrowly. It was 27/32 separate and 25/32 inline. The model inspected the high-penalty lot in 30/32 cases when that report was out of scope, but 22/32 when it was in scope. These descriptive subgroup results expose residual payoff sensitivity failures; they are not additional confirmatory tests.

MASKED had 28 optimal inspections among 32 decisions, two commitments and two invalid inspect({}) calls. Every valid inspection selected lot_1. However, 21/32 first replies reached the token limit and received the fixed re-prompt. The result therefore does not cleanly isolate withholding scope from the realized interaction change. The output cap remained unchanged.

### 4.3 Matched trace and actual outcomes

The illustration is selected mechanically: the lowest-seed world with both separate-layout MAIN first actions observed. In world 2000, both lots currently run V8 and both archived reports say PASS. Table 3 shows that exchanging only their scope assignments changed the enacted inspection. The trace illustrates the intervention; its model-written explanation is not evidence of an internal causal mechanism.

Table 3. Trace-derived matched example. Both lots carry a 100-point error penalty and inspection costs 20. Source records, report results and ordering are fixed across twins.

| Evidence or action | Twin A | Twin B |
|---|---|---|
| REC-2307 / LOT-5869 scope | M2, out of scope | V8, in scope |
| REC-6928 / LOT-5552 scope | V8, in scope | M2, out of scope |
| First tool call | inspect LOT-5869 | inspect LOT-5552 |
| Inspection result | FAIL | PASS |
| Final dispositions, LOT-5869 / LOT-5552 | HOLD / RELEASE | RELEASE / RELEASE |

Actual follow-through was not uniformly valid. Of 356 inspection episodes, 339 ended in valid commitments, 16 attempted a forbidden second inspection and one historical continuation was infrastructure-missing. All 339 valid commitments followed the revealed truth, including 130 with a contradicted archive; three further contradiction cases lacked valid final outcomes. Including two invalid first actions, realised losses are available for 429/448 decisions. Missing and invalid outcomes remain separate from first-action expected regret.

## 5. Discussion and limitations

The result demonstrates substantial use of intact scope bindings in this instrument. It does not support a broad claim that agents ignore provenance, nor does it establish general trustworthiness. The main contribution is an auditable test connecting report-level applicability to costly enacted verification and checking that behavior against explicit alternatives.

The residual failures matter. High-stakes optimality weakened when the high-penalty report was in scope; correct readback coexisted with incomplete twin-pair success; and correct first actions could end in invalid continuations. These observations motivate separate evaluation of applicability recognition, verification allocation and final execution. They do not identify a unique internal explanation.

Accurate metadata, supplied reliabilities, perfect inspection, synthetic records, one pinned model/provider and one sample per cell bound the result. The pilot selected difficulty before main, making inference conditional on that selection rule. The layout interval includes zero; this is not proof of equivalence. MASKED truncation limits attribution, and timing deviations limit claims about preregistration. Appendix A states these qualifications and the ethical scope explicitly.

## 6. Conclusion

Exchanging scope assignments between otherwise fixed reports generally moved the model's priced inspection in the oracle-predicted direction. The frozen primary criterion was met, while payoff and execution failures remained. Trust-infrastructure evaluation should test enacted allocation and final outcomes alongside readable provenance, with preserved failures and a stated normative benchmark.

## Code and Data

Repository: https://github.com/araf81772/Beyond-the-label/tree/v1. The completed empirical release is anchored at commit 0bc1ceaf199c5bd0ec19de175040662e1a170270. Scientific freeze: btl-freeze-v1; operational continuation: btl-main52-operations-v1. Raw journals, worlds, scoring code, the completed analysis bundle and a numeric claim map are retained. The historical partial bundle and pre-results manuscript remain separate. The final-paper package adds its own source map and build instructions. Appendix B describes offline reproduction.

## References

1. Nakayashiki, Kazuki. 2026. When Stale Constraints Go Unchecked: Budgeted Verification Failures in Inherited Agent Memory. arXiv:2608.25553v3. https://arxiv.org/html/2608.25553v3

2. Fan, Kaisheng; Gao, Yishu; Tang, Xunzhu; Bissyandé, Tegawendé F.; and Zhang, Weizhe. 2026. Right Facts, Wrong Rule: Scope-Transfer Poisoning of Retrieval-Augmented Generation. arXiv:2609.35155v2. https://arxiv.org/html/2609.35155v2

3. Chu, Mengdi, and Huang, Jintao. 2026. Can LLMs Trust Appropriately? Evaluating Calibrated Reliance on Imperfect Partners. arXiv:2610.34107v1. https://arxiv.org/html/2610.34107v1

## Appendix A. Limitations and Dual-Use / Ethical Considerations

The instrument assumes authentic metadata, known report reliabilities and a perfect inspector. It does not test forged provenance, estimated reliability, adversarial source content, erroneous verification, long-horizon agents or open-ended workflows. Names and lot records are synthetic and contain no personal data. One model/provider, deterministic decoding settings and one sample per cell limit generalization. Provider nondeterminism remains possible despite temperature zero. Controls reuse a subset of worlds; cells are not independent human-like subjects.

Readbacks are fresh branches of the decision prefix, not elicited explanations of the action already taken. Correct recognition across branches does not identify mediation or an internal reasoning state. First-action losses assume optimal continuation and must not be substituted for realised outcomes. Invalid decisions are observed behavior; infrastructure misses are unavailable outcomes. Conditional success among valid continuations excludes failures and is not a system reliability estimate.

MASKED truncation affected 21/32 first replies (11 separate and 10 inline). All received the unchanged episode-level re-prompt. This interaction confound is retained and accepted as a limitation. Changing the 512-token cap would require repeating smoke and pilot, plus load-8 smoke if selected, with approval, a new run ID and a new freeze after execution freeze. No such change was made.

The protocol and thresholds were fixed for main collection, but the process was not a pristine preregistration. H1 human oracle verification was reported after the pilot, D3 threshold acceptance was recorded after pilot exposure, and D4 lead assignments were late. These timing deviations are documented rather than retroactively corrected. The team representative subsequently reported H3/H4 complete. This is user-attested completion; individual signed trace-audit worksheets were not supplied to the repository, and AI checks do not substitute for human participation. Review of this newly generated manuscript is distinct from that earlier evidence attestation.

Potential dual use is limited but nonzero: an evaluator could use the harness to search for handoffs that encourage under-checking. We release a synthetic measurement task rather than a deployment attack. Passing its threshold is not a certification of safe autonomous operation. Failed outcomes and operational limits are retained to reduce misleading safety claims.

## Appendix B. Reproduction and supplementary evidence

### B1. Execution provenance and accounting

The main scientific freeze is commit 6f8f94b3542980f65ba08f56aa3a12bf12c9e41d, tag btl-freeze-v1, covering 50 scientific input files. The original main stopped at 652 completed cells after 40 HTTP 429 failures with unknown costs. Explicit approval retained all 40 full reservations and allowed only the remaining 52 cells, stopping on any new unknown charge. Operational source cc7c81dbfda50aefada5c4e62f1ffd8702601939 is separately bound by btl-main52-operations-v1. All scientific input hashes and original completed rows stayed unchanged. Selected endpoint metadata used deepseek/deepseek-v4.1-flash-20261017 under the approved endpoint-only allowance; this was neither a top-level model alias nor a fallback.

The continuation produced 84 accepted calls, no new infrastructure failure and no new unknown charge. The composite journal contains 1,120 attempts, 1,080 accepted replies, 39 infrastructure retries and 21 prescribed re-prompts. Accepted replies can still contain invalid actions. The one exhausted historical continuation was not retried. The original parent journal is an immutable prefix of the child; analysis counts it once.

Known main-only usage cost is USD 0.13275084448; its actual total remains unknown. The staged session, including smoke and pilot, retains USD 1.93872838656 across the original 40 holds, with USD 0.20233421648 known and USD 6.85893739696 available under its unchanged USD 9 cap. Its 1,645 attempts remain below 3,000. The older closed smoke authorization stays separate. Held maxima are not receipts or refunds. Operational pacing enforced a 15-second minimum POST interval; direct per-POST wall timestamps were not recorded, so spacing is supported by tested code rather than an independent timestamp census.

### B2. Full condition and outcome summaries

Table B1. Optimal first actions, expected regret and realised loss. Regret uses valid first actions and optimal continuation. Realised loss uses only available final outcomes; its denominator differs when actions or continuations are invalid/missing. NUMERIC has one layout.

| Condition | Optimal / planned | Valid-only mean regret | Available outcomes | Mean realised loss |
|---|---:|---:|---:|---:|
| MAIN | 239/256 | 1.328125 | 255/256 | 26.901961 |
| HIGH-FEE | 63/64 | 0.3125 | 64/64 | 57.1875 |
| HIGH-STAKES | 52/64 | 17.5 | 51/64 | 95.294118 |
| MASKED | 28/32 | 0.333333 | 27/32 | 62.962963 |
| NUMERIC | 32/32 | 0 | 32/32 | 29.375 |

MASKED's valid-only regret denominator is 30; assigning its two invalid first actions the worst valid first-action loss gives a mean regret of 6.875 over all 32 decisions. The 16 invalid continuations comprise 12 HIGH-STAKES, three MASKED and one MAIN case. The infrastructure-missing continuation is HIGH-STAKES. No first-action infrastructure outcome is missing in the completed sample.

### B3. Reproduction and prompt access

The repository includes the exact prompts, generated worlds, frozen inputs and every retained raw response. Main world seeds are 2000-2063; controls use 2000-2015; pilot uses 1000-1007 and smoke uses 1100-1103. World-bootstrap seed 314159 and schedule seed 271828 are fixed. The human trace-audit sampling convention uses seed 161803. Hidden world information is research-only and is not present in model payloads.

From a checkout containing the completed release, install the locked dependencies, set PYTHONPATH to src, then regenerate the evidence bundle without credentials or inference:

```text
python scripts/finalize_main_continuation.py --output reproduced_bundle
python scripts/verify_audit.py
```

The analysis tables and figures come from results/staged_main_complete; raw source is continuations/staged_main_52_20261116. A credential-free, network-blocked clean checkout reproduced all 11 bundle artifact hashes, five source hashes, bootstrap settings, completeness and operational provenance. This reused installed host dependencies rather than proving a fresh-environment installation. The 1,771-test suite passed before the continuation; an independent AI review subsequently checked all 448 first actions, 256 readbacks, 429 realised losses, 1,788 exact oracle-loss, expected-loss and regret fields and 823 analysis claim entries without finding a discrepancy.

### B4. Sprint work and authorship

[[PRIOR_WORK_DISCLOSURE]]

## LLM Usage Statement

OpenAI Codex assisted implementation, tests, execution controls, analysis checks and evidence verification, including independent AI subagent reviews. Codex drafted this final report under the team's direction. Claude (Anthropic) assisted repository review and the staged execution path, as documented in the project log. Deterministic code scored experimental actions; no LLM judge was used. Human checks remain separately recorded as team-reported completion, with timing and documentation limits disclosed. The authors are responsible for reviewing the final manuscript before submission.
