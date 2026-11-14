# Related-work verification status

Read-only public-source verification was performed by Codex (AI review) on 2026-11-14 UTC / 2026-11-15 AEDT. The evidence record is [checks/source_verification.json](checks/source_verification.json). This establishes the identities and limited claims below, not an exhaustive literature review or a novelty finding. External papers' results are not Beyond the Label observations. No credentials or inference calls were used for this review. Human citation review H5 has not occurred.

## Requested primary sources

### Nakayashiki: inherited memory and verification allocation

Kazuki Nakayashiki, *When Stale Constraints Go Unchecked: Budgeted Verification Failures in Inherited Agent Memory*, [arXiv:2608.25553v3](https://arxiv.org/html/2608.25553v3).

The abstract verifies a six-memory scenario with a two-record inspection budget and an intervention that assigns a slot to the critical provenance path. It distinguishes available provenance from the agent's allocation of verification effort. The forced-critical intervention explicitly uses experimenter knowledge; it is an oracle intervention, not a deployable scheduler. This supports motivation for measuring verification allocation, without establishing equivalence to BTL's fixed-report scope swap.

### Fan and colleagues: scope recognition and application

Kaisheng Fan, Yishu Gao, Xunzhu Tang, Tegawend'e F. Bissyand'e, and Weizhe Zhang, *Right Facts, Wrong Rule: Scope-Transfer Poisoning of Retrieval-Augmented Generation*, [arXiv:2609.35155v2](https://arxiv.org/html/2609.35155v2).

The abstract verifies rule-scope misapplication despite factually supported evidence and explicit scope boundaries. Its 76.2% recognition result is conditional on target-matching default responses: under an explicit probe, the same model judged the rule inapplicable. It is not a rate over all attempts, a BTL observation, or evidence that BTL's separate readback branch causally determines action. The paper concerns adversarial RAG document construction; it does not by itself establish BTL's novelty.

### Chu and Huang: calibrated reliance and decision utility

Mengdi Chu and Jintao Huang, *Can LLMs Trust Appropriately? Evaluating Calibrated Reliance on Imperfect Partners*, [arXiv:2610.34107v1](https://arxiv.org/html/2610.34107v1).

The abstract describes 324 scenarios across 23 collaboration categories, three sequential decisions, and analytic evaluation against expected consequences. It reports seven evaluated models and 36 controlled-history probes. It supports distinguishing sensitivity to partner evidence from appropriate reliance decisions; explicit posterior information has heterogeneous effects. These benchmark counts and findings belong to the cited study, not BTL.

## Submission requirements and template

The [official AI x Epistemics Sprint guidelines](https://apartresearch.com/sprints/ai-x-epistemics-research-sprint-2026-11-13-to-2026-11-15) identify Track 2 as Trust Infrastructure and link the [official report template](https://docs.google.com/document/d/17b3JWki-ZkaqdmqGI5d0gof-HwlGuWU9Mc1_klNZXKs/copy?usp=sharing). They require a PDF report, at most eight body pages excluding references and appendices, a 150–250-word abstract, authors and affiliations, and a Limitations and Dual-Use / Ethical Considerations appendix. The guidelines' template link takes precedence over older acceptance-email templates. The copy link redirected to Google sign-in; public edit and text-export attempts were inaccessible. Only the official link and guidelines were verified: the template's contents, formatting and local reproduction remain unverified. No submission or publication occurred.

## Remaining limits

The unchanged source design's Section 17 records that Fan and colleagues and Chu and Huang were not located by its earlier search. That is a historical status, superseded by the checks above; the authoritative source archive is preserved unchanged. Other Section 17 citations and claims remain pending. AgentDojo and tau-bench remain citation targets only, not installed dependencies. Any later report must omit unsupported claims and verify each additional citation against its source. The checks above do not substitute for human H5 review or authorize publication.
