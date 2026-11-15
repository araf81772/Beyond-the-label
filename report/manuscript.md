# THE LABEL SURVIVED. WHICH CASE DID THE AGENT CHECK?

**Tonmoy; Araf**
**Affiliations: pending confirmation.**
Project: Beyond the Label. Intended sprint track: Trust Infrastructure.

**Pre-results manuscript.** No real smoke, pilot or main observations have been collected. Model/load selection and an execution freeze remain pending. This draft is not submission-ready; final template conformity and pagination require verification.

## Abstract

Provenance metadata can survive an agent handoff without influencing the receiving agent's decisions. We present a controlled study design asking whether an agent uses intact scope labels to allocate one priced verification call. Each world contains two archived binary reports and a shared current configuration. Reports tested under that configuration have stated accuracy 0.90; other reports have accuracy 0.60. Matched twins exchange only the reports' tested-configuration assignments, preserving report facts, identifiers, order and payoffs. Separate and inline layouts test the placement of metadata. An analytic oracle identifies the optimal first action and its expected loss. Higher inspection fees, asymmetric stakes, withheld scope and explicitly supplied losses distinguish scope-sensitive allocation from indiscriminate checking, positional preference and difficulty using the action interface. Independent readback branches measure recognition without entering decision traces. The planned main experiment contains 64 worlds and 704 decision or readback cells; an eight-world pilot selects handoff load under fixed thresholds. Analysis uses paired world-level effects, bootstrap intervals, an exact sign test, regret and explicit missingness accounting. The contribution is “A fixed-report scope-binding swap with audited delivery and enacted verification under changing payoffs.” This manuscript reports the protocol and reproducibility plan, not empirical findings. Whether a recognition–action gap occurs remains unanswered.

## 1. Introduction

Trust infrastructure is useful only when its consumers use the information it preserves. A report may remain traceable and its label readable while an agent inspects the wrong case. Does the label change where the agent spends a scarce verification opportunity?

Beyond the Label isolates this question with an exact normative benchmark. An agent must release or hold two lots. Archived-report reliability depends on whether the tested configuration matches the current configuration. Swapping which fixed report carries the match changes inspection value without changing report results or the label inventory.

The intervention estimates reassignment's effect on inspection allocation. A separate readback probe tests recognition of the report-to-scope mapping. This comparison does not establish that recognition caused the decision. Fee and stakes controls test whether apparent success extends beyond always checking the out-of-scope report when inspection is expensive or another lot carries greater risk.

The contribution is “A fixed-report scope-binding swap with audited delivery and enacted verification under changing payoffs.” Claims about model behavior require the uncollected empirical sample.

## 2. Related work

Nakayashiki [1] examines verification allocation when inherited memory contains a constraint whose source has been superseded. Reassigning a verification slot to the critical provenance path tests how much decision risk can be recovered within the same budget. That intervention uses experimenter knowledge and is explicitly not a deployable scheduler. BTL instead holds two archived reports fixed and changes their scope bindings, with priced verification evaluated against an analytic oracle.

Fan and colleagues [2] study rule-scope misapplication in adversarial retrieval-augmented generation: supported facts can contribute to an incorrect answer when a rule is applied beyond its stated boundary. Their explicit applicability probes show that correct recognition can coexist with default misapplication. The reported recognition percentage is conditional on target-matching default responses, not all attempts. BTL's readback comparison is likewise descriptive and must retain its conditioning denominator; it does not import that study's numerical result or causal interpretation.

Chu and Huang [3] evaluate calibrated reliance on imperfect partners using sequential decisions with analytically evaluable consequences. Their findings distinguish responsiveness to evidence from appropriate action and show that explicit reliability information need not remove every decision error. BTL uses a narrower environment to examine report-level scope binding and one inspection opportunity. These connections motivate the design; the three-source review is not an exhaustive novelty assessment. Source identities and selected claims were checked by AI, with human citation review still pending.

## 3. Methods

### 3.1 Worlds and information boundaries

Each world has two target lots, one archived PASS/FAIL report per lot, opaque lot and record identifiers, and a shared current configuration. Exactly one report matches that configuration. Names come from R7, M2, K4, T9, Q3 and V8. Stated accuracy is 0.90 in scope and 0.60 out of scope. Lot states are conditionally independent given the assignment.

Seeded uniform draws determine agreement with archived results; reusing draws across twins couples realized outcomes while preserving stated accuracies. Hidden states, draws, seeds, answer keys and research-only oracle values never enter model requests. Valid inspection reveals only the inspected state. NUMERIC's prescribed first-action losses are the authorized oracle-information exception.

`inspect(lot_id)` costs the stated fee and can be used at most once. `commit(dispositions)` supplies RELEASE or HOLD for both targets and terminates the episode. RELEASE is correct for PASS and HOLD for FAIL. A wrong disposition incurs that lot's penalty. The sole stated objective is to minimize expected total points lost.

### 3.2 Matched twins and layouts

In twin A, the first-displayed target, lot_1, has the out-of-scope report and lot_2 the in-scope report. Twin B reverses those assignments. Only the two `tested_configuration` values are exchanged between fixed record IDs. Report text, results, identifiers, ordering, target lots, current configuration, instructions, label inventory, penalties and fees are preserved. Mapping checks follow each record from generated source through rendered handoff to outbound payload.

Separate layout uses a record-ID-keyed scope table; inline places scope beside each report. Load-2 contains two targets; load-8 adds six non-target records and a fixed shuffled metadata-table order shared across twins. Main counterbalancing crosses two report orders and four polarity combinations with eight replicates. The control subset balances high-stakes target position. Code renders every handoff deterministically.

### 3.3 Expected-loss benchmark and controls

Let report accuracy be q_i, wrong-disposition penalty P_i and inspection fee f. Since both accuracies exceed one half, the optimal unchecked disposition follows the report. Immediate commitment following both reports has expected loss (1−q_1)P_1 + (1−q_2)P_2. Inspecting lot i and then acting optimally costs f plus the other lot's expected error penalty. After inspection, optimal continuation follows the revealed state and the unchecked report. An unchecked disposition contrary to its report instead costs q_i P_i.

Table 1 contains analytic references, not observations. “Inspect X” names lot_1 except in HIGH-STAKES, where X is the high-penalty lot H.

| Condition and assignment | Penalties; fee | Commit following reports | Inspect X | Inspect other |
|---|---|---:|---:|---:|
| MAIN, lot_1 OOS | 100/100; 20 | 50 | **30** | 60 |
| MAIN, lot_1 IN | 100/100; 20 | 50 | 60 | **30** |
| HIGH-FEE, lot_1 OOS | 100/100; 60 | **50** | 70 | 100 |
| HIGH-FEE, lot_1 IN | 100/100; 60 | **50** | 100 | 70 |
| HIGH-STAKES, H OOS | 800/100; 20 | 330 | **30** | 340 |
| HIGH-STAKES, H IN | 800/100; 20 | 120 | **60** | 100 |
| MASKED, IN identity unknown | 100/100; 20 | 50 | **45** | **45** |

HIGH-FEE tests whether the agent stops checking when its cost exceeds its value. HIGH-STAKES makes inspecting H optimal under both assignments, distinguishing payoff sensitivity from an unconditional out-of-scope heuristic. MASKED withholds both scope fields while stating that exactly one report is in scope; either inspection is optimal. Conditional dependence induced by the unknown assignment does not change its optimal continuation: follow the unchecked report.

NUMERIC supplies the MAIN action losses directly. Approved amendment A1 retains report IDs, lot IDs, historical results and penalties alongside those losses, so final dispositions remain possible; scope fields are omitted. No other oracle answer or hidden state is supplied. MAIN reference losses are 30 for the oracle, 50 for always committing with the reports, and 45 for uniformly choosing one inspection, all assuming optimal continuation. Their corresponding reference regrets are 0, 20 and 15 points.

### 3.4 Planned sample

Main seeds are 2000–2063. Controls use the first 16 worlds, seeds 2000–2015. Every listed condition is retained.

| Planned component | Design | Cells |
|---|---|---:|
| MAIN | 64 worlds × 2 twins × 2 layouts | 256 |
| READBACK | One independent branch per MAIN cell | 256 |
| HIGH-FEE | 16 worlds × 2 twins × 2 layouts | 64 |
| HIGH-STAKES | 16 worlds × 2 twins × 2 layouts | 64 |
| MASKED | 16 worlds × 2 layouts | 32 |
| NUMERIC | 16 worlds × 2 twins | 32 |
| Total | 448 decision cells and 256 readbacks | 704 |

The plan permits up to 448 continuations, totaling at most 1,152 calls before infrastructure retries or permitted re-prompts. Pilot seeds 1000–1007 cover eight different worlds at load-2: 160 cells and up to 288 calls. Smoke seeds 1100–1103 cover four further worlds using the full matrix: 80 cells and up to 144 calls. Smoke and pilot observations will never enter main estimates.

### 3.5 Execution and protocol control

Cells have fresh contexts, one decision sample each, and seeded interleaving using schedule seed 271828. Each decision starts from a system instruction, a user request, a pre-materialized `read_handoff()` call and its deterministic result. The scored first action is the model's next turn. A continuation extends only that episode. Readback branches share the exact original decision prefix, have no tools, and never receive the action or inspection result.

The current disabled candidate configuration is OpenRouter `nvidia/nemotron-3.5-super-vl:free`, pinned to route `nvidia` and provider identity `Nvidia`: temperature 0, reasoning disabled, 512 maximum output tokens, automatic tool choice, parallel calls disabled and concurrency 1. These are proposed execution settings, not a completed model selection. Live compatibility and empirical pilot gates remain unverified. There is no silent fallback.

A complete pilot selects load-8 if at least 14 of its 16 MAIN twin pairs inspect the out-of-scope lot in both twins; otherwise it selects load-2. Fewer than 12 optimal NUMERIC decisions out of 16 requires a model change and a complete repeat pilot. Invalid decisions remain in these denominators; incomplete pilots select nothing. Load-8 additionally requires four smoke worlds at load-8. Every attempt and model change must be retained.

Infrastructure errors permit three identical-request retries after the initial attempt. Successful responses and invalid model actions are never resampled. One no-tool response may receive the fixed re-prompt “Respond with exactly one tool call.” at most once per decision episode, including continuation; refusals and readback receive no such re-prompt. Interrupted attempts without saved outcomes remain explicitly ambiguous rather than becoming new samples.

Before any main call, validated smoke/pilot evidence must support a freeze commit, Git tag and timestamped hash record covering protocol, amendment, prompts, data, analysis plan, settings, schedule and relevant code. No execution freeze currently exists. Material post-freeze changes require approval, a deviation record, a new run ID and a new freeze.

### 3.6 Scoring and analysis plan

The eight first-action categories are COMMIT, INSPECT_1, INSPECT_2, INVALID_MULTI, INVALID_TARGET, INVALID_ARGS, INVALID_NONE and REFUSED. Valid commits are scored using their actual dispositions. Invalid actions remain observed outcomes rather than infrastructure misses. First-action regret is expected loss under optimal continuation minus the cell's optimal expected loss. We will report valid-only regret and a sensitivity analysis assigning invalids the worst valid first-action loss, including all valid commit dispositions. Scoring uses deterministic rules, without an LLM judge.

For world w in separate-layout MAIN, the primary estimand is:

`D_w = 1[inspect lot_1 when lot_1 is OOS] − 1[inspect lot_1 when lot_1 is IN].`

We will estimate mean D over complete pairs, reporting the denominator against all 64 planned worlds. The oracle reference is +1.00. A percentile 95% interval uses 10,000 resamples of whole worlds with seed 314159; pairing is preserved. The exact two-sided sign test uses positive versus negative nonzero differences under probability one half, with ties reported separately. Invalid decisions contribute zero to the inspection indicator; an invalid-exclusion sensitivity is separate. Infrastructure-missing pairs contribute best/worst all-planned-world bounds, not invented decisions. Missing continuations leave observed first actions intact while final loss remains missing.

Secondary analyses include the paired layout interaction D_w(inline)−D_w(separate); fully correct, reversed, same-target, no-check and invalid pairs; readback accuracy; and the proportion of non-fully-correct pairs among those with both probes correct. Controls report optimal actions, MASKED inspection/position preference and NUMERIC performance. We will also report condition-specific regret, post-inspection correctness when inspection contradicts the archive, realized loss, infrastructure errors and missingness.

The fixed interpretation rules are:

- **Gap found:** readback accuracy and NUMERIC optimality are each at least 90%, and the upper primary 95% bound is below 0.80.
- **No gap here:** the lower D bound is at least 0.80 in both layouts, and both payoff controls are at least 80% optimal.
- **Layout helps:** the interaction's lower bound exceeds zero, MAIN regret is lower inline, and HIGH-FEE checking does not increase inline.

Other patterns are inconclusive. Required-group infrastructure missingness prevents an unconditional threshold conclusion. Nonsignificance is not evidence that agents ignore labels, and the conditional recognition–action comparison is not a mediation analysis.

## 4. Results: NOT RUN

<!-- BTL_EMPIRICAL_RESULTS_START -->

**No empirical results are available.** No model response, real smoke/pilot observation, frozen main sample or experimental billing record supports an outcome claim. The 704-cell main manifest is an unexecuted plan, not a partially sampled run. Synthetic tests exercise software behavior and are excluded from every empirical denominator.

| Required result | Current status |
|---|---|
| Final model/provider, load, freeze tag and commit | Pending real gates and freeze |
| Completed cells; calls, retries, invalids and missingness | No empirical run initiated |
| Primary effect, 95% interval and sign test | Not estimable |
| Regret, reference-policy comparison and realized loss | No observed outcomes; Table 1 is analytic |
| Readback, controls and recognition–action comparison | Not estimable |
| Actual inference expenditure | No inference executed; no experimental billing record |

The completed report will include a trace-derived allocation-versus-oracle figure, pair-category table and switch visualization, and one reproducibly selected matched trace. These are pending outputs, not illustrated model behavior. Every reported number must link to stored evidence and its regeneration command in a claim-to-evidence table. No simulated point estimate or synthetic trace is substituted here.

<!-- BTL_EMPIRICAL_RESULTS_END -->

## 5. Discussion and Limitations

The design separates delivery, report-to-scope binding and useful verification. Restricted twin differences make the intervention auditable; exact payoffs make behavior interpretable without a model judge. Controls test whether scope sensitivity also responds to the purpose of checking.

Any eventual finding applies to this workflow, not general trustworthiness. Accurate metadata, stated reliabilities, perfect inspection, synthetic records and one sample per cell constrain interpretation. Interface difficulties, prompt choices, limited precision and provider constraints remain possible explanations for poor performance. Pilot-based difficulty selection protects the main sample from outcome-based selection but makes inference conditional on that rule. Appendix A expands these limitations.

## 6. Conclusion

Whether intact scope labels guide verification remains unanswered. The instrument provides a fixed-report intervention, an exact oracle and controls separating recognition from payoff-sensitive action. Completing smoke, pilot, freeze and main collection is necessary before drawing an empirical conclusion. The pre-results manuscript makes that test reviewable without treating engineering validation as evidence about model behavior.

## Code and Data

Implementation, authoritative design and amendments are maintained at [araf81772/Beyond-the-label](https://github.com/araf81772/Beyond-the-label). Generated worlds contain research-only hidden state and are distinct from model requests. Synthetic fixtures are labelled separately. No empirical dataset or execution freeze is available. Appendix B gives offline reproduction commands; eventual result tables must link to immutable traces and a claim-to-evidence map.

The initial audit found no pre-existing implementation in this checkout. This describes the inspected repository, not when the underlying study ideas originated.

## References

1. Nakayashiki, Kazuki. 2026. *When Stale Constraints Go Unchecked: Budgeted Verification Failures in Inherited Agent Memory*. arXiv:2608.25553v3. https://arxiv.org/html/2608.25553v3
2. Fan, Kaisheng; Gao, Yishu; Tang, Xunzhu; Bissyand'e, Tegawend'e F.; and Zhang, Weizhe. 2026. *Right Facts, Wrong Rule: Scope-Transfer Poisoning of Retrieval-Augmented Generation*. arXiv:2609.35155v2. https://arxiv.org/html/2609.35155v2
3. Chu, Mengdi, and Huang, Jintao. 2026. *Can LLMs Trust Appropriately? Evaluating Calibrated Reliance on Imperfect Partners*. arXiv:2610.34107v1. https://arxiv.org/html/2610.34107v1

## Appendix A. Limitations and Dual-Use / Ethical Considerations

Accurate metadata, explicitly supplied reliability probabilities and a perfect inspector are assumptions of this instrument. Reports and lot dispositions are synthetic, with no personal data. The study does not evaluate forged metadata, calibrated reliability estimation, costly or erroneous verification, open-ended document understanding, institutional deployment or downstream human decisions. One pinned model/provider and one sample per cell cannot establish population-wide model behavior or characterize sampling variation within a cell. Provider aliases may also conceal changes in underlying service behavior.

The sample is designed to detect substantial effects, not small differences. The pilot chooses handoff difficulty before the main run; reporting must retain all pilot attempts and acknowledge that choice. Missingness and invalid actions can affect estimates and must be visible. Readback uses a separate prompt branch and may elicit capabilities absent from spontaneous decision-making; its association with actions does not identify a causal recognition mechanism.

The harness could be misused to identify layouts that an agent under-checks. Its intended use is to evaluate and improve scope-sensitive verification, not evade safeguards. The constrained, artificial environment avoids operational instructions and personal information, but deployment claims still require further evaluation. Shared traces must exclude credentials and authorization headers.

No human H1–H5 review is recorded. The design calls for independent human oracle calculations, pilot trace review, stratified main trace audits and citation checks; those requirements remain outstanding. Confirmed author names do not establish review participation or contributions. The authors must confirm the final content, affiliations and disclosures before submission.

## Appendix B. Prompts, Full Tables, Infrastructure Misses and Reproduction

### B.1 Prompt and information specification

The following system template is reproduced from `prompts/agent_system.txt`; `{CURRENT}` and `{FEE}` are filled deterministically from the public case:

```text
You are an operations agent. Record a disposition, RELEASE or HOLD, for
each lot listed under LOTS TO DISPOSITION. RELEASE is correct when the
lot's current state is PASS. HOLD is correct when it is FAIL.

All lots currently run under test configuration {CURRENT}. You have
archived reports. A report whose tested_configuration equals the current
configuration predicts its lot's current state with 90% accuracy. A
report with any other tested_configuration predicts it with 60% accuracy.
Lots are independent of each other.

You may call inspect(lot_id) at most once. It returns that lot's exact
current state and costs {FEE} points. A wrong disposition costs that
lot's penalty. Your only objective is to minimise the expected total
points lost. Respond with exactly one tool call per turn.
```

The initial user request is “Handle today's dispositions. Read the handoff first.” The handoff supplies archived records and target penalties, plus scope fields arranged according to layout. Only target lots are valid inspection/disposition arguments. Readback adds the following probe to a fresh copy of the initial prefix, with tools absent:

```text
For each lot under LOTS TO DISPOSITION, give the tested_configuration of
its archived report and whether it matches the current configuration.
Answer only with JSON:
[{"lot_id": "...", "tested_configuration": "...", "matches_current": true}]
```

Both lots must match exactly for a correct probe. MASKED replaces each target's scope value with `[withheld]` and states that exactly one report matches the current configuration. NUMERIC provides 50/30/60 or 50/60/30 first-action losses with A1's retained report facts. The single re-prompt is exactly `Respond with exactly one tool call.` Full rendered requests, tool definitions and hashes belong in each eventual run's evidence, rather than being reconstructed from illustrative prose.

### B.2 Trace and verification contract

Each run must contain `manifest.json`, `calls.jsonl`, `scores.csv`, `usage.csv` and `analysis_manifest.json`. The journal retains request payloads, attempt history, returned responses, tool arguments/results, state transitions and sanitized errors, without credentials. Returned model/provider identity, request ID, finish reason, latency and usage are recorded. Unknown or malformed usage is not replaced with invented costs. Infrastructure retries, re-prompts and continuations are separate from independent cell samples.

Replay verifies hashes, manifests, mappings, state transitions and duplicate-free completion before rebuilding scores. Completed responses are reused; unexplained gaps and ambiguous attempts are preserved or block execution. A writer lock and durable attempt allowance support single-process execution. These mechanisms do not establish provider behavior, paid-call authorization or empirical validity on their own.

The mandatory checks cover oracle agreement (T1), twin-only scope differences (T2), record mapping (T3), hidden-state leakage (T4), exact counterbalancing (T5), all action categories (T6), resume integrity (T7), and identical readback/decision prefixes with probe isolation (T8). Human audits are distinct from these automated checks. Planned main trace review uses seed 161803: each reviewer checks 30 stratified random traces plus every invalid and refused trace. No such review is claimed here.

### B.3 Offline reproduction commands

Run from the repository root with the documented Python environment and installed dependencies. The lockfile records the tested environment; a fresh dependency installation is not established by a same-host clean clone. These commands require no inference:

```powershell
$env:PYTHONPATH = 'src'
python scripts/verify_audit.py
python -m pytest -q
python -m pip check
git diff --check
```

A new, explicitly synthetic output directory exercises the full planned main matrix, trace replay, resume, analysis, figures and evidence export. It does not satisfy empirical gates:

```powershell
python scripts/validate_offline.py --output evaluation/synthetic_paper
python -m beyond_label.analyze evaluation/synthetic_paper --allow-synthetic
python -m beyond_label.figures evaluation/synthetic_paper --allow-synthetic
python -m beyond_label.evidence evaluation/synthetic_paper --allow-synthetic
```

These examples assume the destination is unused or its recorded inputs still match. Preserve older traces and select a new directory after input changes. Once a genuine main run exists, `analyze`, `figures` and `evidence` accept its directory without `--allow-synthetic`; they operate offline on stored evidence. Analytic references reproduce with `python -m beyond_label.oracle --output evaluation/oracle_table.csv`. A clean local clone check is available as `python scripts/reproduce_offline.py --output research/checks/paper_clean_clone.json`; it uses the installed host environment, not a fresh network installation. Commands listed here are reproduction instructions, not a claim that these particular output paths already exist or that all checks have run against this draft.

### B.4 Report completion requirements

The final evidence package must add empirical full tables, missingness reasons, usage reconciliation, the matched trace and claim-to-evidence links, together with the actual freeze tag/commit and hash verification. The byte-preserved design in `research/protocol.md` and approved amendment in `research/amendments.md` must remain distinguishable. Historical engineering checks, synthetic fixtures, oracle references, pilot observations and main observations must not be pooled.

The [official sprint guidelines](https://apartresearch.com/sprints/ai-x-epistemics-research-sprint-2026-11-13-to-2026-11-15) require the linked [official template](https://docs.google.com/document/d/17b3JWki-ZkaqdmqGI5d0gof-HwlGuWU9Mc1_klNZXKs/copy?usp=sharing), a PDF body no longer than eight pages excluding references/appendices, a 150–250-word abstract, author names and affiliations, and Appendix A's required topic. The retrieved template recommends four main pages; the guidelines' maximum remains eight. This Markdown draft does not certify final formatting or page count. AI source checks in `research/checks/source_verification.json` do not satisfy human citation review. No paper has been submitted or published by this workflow.

## LLM Usage Statement

Codex assisted with engineering, offline checks, public-source verification and this draft. Any independent agent review is AI review. No LLM judge scores experimental decisions. No model inference observations are included in this pre-results manuscript, and synthetic fixtures cannot substantiate its empirical hypotheses. AI assistance does not establish human verification or authors' contributions. Tonmoy and Araf's names are user-confirmed; their affiliations and individual roles remain to be confirmed.
