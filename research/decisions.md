# Decision log

## 2026-11-14 — M1: audit scope and source authority

- Follow the final request to execute milestone 1. Keep the six-milestone plan, with milestones 2–6 not started.
- Read all 581 lines of the supplied design before any implementation. Archive it byte-for-byte as `research/protocol.md`; keep provenance/hash in `research/source_manifest.json` and do not rewrite historical claims.
- Preserve the empty intake state as evidence: unborn `master`, no files/commits/remotes/upstream. No earlier implementation or user edits were found. No pre-sprint project code is attributed to this checkout.
- Use the design's numbers and pilot/interpretation thresholds unchanged. Source Section 18's invitation to revisit thresholds is not permission to redesign them under the current user request.
- Treat independent agent arithmetic review as AI review only. It agrees with Section 4 and the main/pilot call counts; no human checks or citation verification have occurred.

## 2026-11-14 — M1: conflicts and prerequisites

- Record NUMERIC's missing disposition facts as unresolved before dependent rendering. Do not silently enrich the loss-only handoff.
- Scope twin-diff checks to relevant conditions and explicitly allow only the deliberate NUMERIC first-action losses; never hidden state or draws.
- Retain MASKED, S8, and every planned case despite the source's cut order. Use seeded interleaving despite the coarse schedule's “then controls” wording.
- Do not choose a model/provider fallback or mistake “under US$20” for authorization. OpenRouter is specified, but upstream provider/model, settings, credential, authorized cap, pricing, rate/concurrency limits, and hard-key-limit evidence are absent.
- At initial intake, do not invent a remote destination or create/publish a repository. A connected repository search returned no match; the intended existing URL/branch was requested. Configuring a local remote for a subsequently supplied existing repository is authorized.
- Record unassigned human review, official template, citation verification, smoke matrix, analysis seeds/method, and failure/denominator conventions as pending at their relevant stages. No execution freeze exists.

## 2026-11-14 — M1: checks and checkpoint

Exact commands/outcomes are in `research/baseline.json`. Initial checks included Git status/tree/history/remotes, ancestor instructions, complete design read/hash, runtime versions, package metadata/imports, credential presence only, and baseline pytest discovery. No experiment tests exist; no T1–T8 pass is claimed. No paid calls were attempted.

Audit acceptance uses `python scripts/verify_audit.py` plus `git diff --check`; the script validates source integrity, mapping/status completeness, and selected credential patterns. Review covers the intended diff, all generated audit files, scientific wording, and secret exposure. The milestone record distinguishes local audit completion from a blocked remote push. Commit identity is recoverable from Git history instead of being embedded circularly in the files it hashes.

Independent AI review identified three mapping omissions, repaired before acceptance: core T3/T4/T6 checks belong in milestone 2 with provider/harness revalidation in milestone 3; world integrity explicitly includes .90/.60 accuracy, conditional independence, shared twin draws and exactly one IN report; deterministic rendering includes the prescribed pre-materialized conversation prefix. These repairs change audit coverage, not the experiment design.

## 2026-11-14 — M1: local commit and blocked delivery

Local milestone commit: `762ff8a3b0bb1257636dfdf704e3e3c8de58ad16` on `master`. All 55 audit checks passed across 37 mapped requirements and 12 intended files; staged whitespace checks passed. The committed source blob matches the original SHA-256. Experiment tests remain absent (pytest process exit 5), and no human review or paid execution occurred.

`git push` returned exit 128: `fatal: No configured push destination.` No remote branch exists to compare. The local commit is preserved; the minimum delivery action is to provide the intended existing repository URL and branch. A follow-up status commit records this outcome without circular commit hashes. Milestone 1 is locally complete but its push step is blocked; milestones 2–6 remain not started.

## 2026-11-14 — M1: user-supplied destination and history integration

The user supplied `https://github.com/araf81772/Beyond-the-label`. GitHub metadata confirms this existing repository is public, grants push access, and uses the unprotected default branch `main`. Read-only Git ref inspection independently confirmed `main` at `661f3750f648cff25fbf88857b8fef430f461483`. Its only file is an initial `.gitattributes`; the original empty-local-checkout finding remains accurate.

Configured local `origin` to the supplied URL and renamed local `master` to match `main`. Integrated the independent initial GitHub commit without rewriting either history. Resolved the add/add `.gitattributes` conflict by retaining the remote's explanatory comment and shared normalization rule alongside the audited file-type rules and the exact-byte protocol exception. No repository or visibility was created/changed. The initial sandbox DNS restriction was resolved by the authorized network escalation. Delivery will use a normal non-force push followed by exact remote-head comparison.

## 2026-11-14 — M1: remote delivery verified

`git push -u origin main` succeeded (exit 0), advancing the existing remote from `661f3750f648cff25fbf88857b8fef430f461483` to audit integration commit `57a440b1dd9aa6caa7b90194d6980246efb1dee7`. `git ls-remote origin refs/heads/main` returned that exact SHA, matching `git rev-parse HEAD`; both previous local audit commits and the remote's initial commit are ancestors. The working tree was clean at verification. This resolves the missing-destination blocker and completes milestone 1. A subsequent status-record commit documents the observed success and is delivered by the same normal-push procedure; its own hash is obtained from Git to avoid circular provenance.

The original failed-push and empty-local-intake records remain historical evidence. No experimental configuration, source-design bytes, freeze state, model calls, human-review claim, or milestone 2–6 status changed.

## 2026-11-14 — M2: sequential offline implementation and approved amendment

The user authorized continuing milestones one at a time, each with tests, repairs, retests, records, commit and push, while keeping research execution offline. Git delivery to the existing verified remote remains authorized. No real smoke/pilot/main execution or network dependency installation is permitted. Milestone 1 remains complete; its historical baseline is preserved.

The user explicitly approved retaining report facts in NUMERIC alongside the specified losses. Amendment A1 in `research/amendments.md` supplies the minimal historical results/IDs and target penalties without scope metadata, hidden states, or extra oracle answers. The original source remains unchanged. This resolves the previously documented NUMERIC ambiguity before dependent implementation.

Implemented `schemas.py`, `generate.py`, `oracle.py`, `render.py`, `sandbox.py`, and `score.py`, prompt files, the three exact seed sets, manifests, analytic hand-table references, and core T1–T6 tests. Two per-lot hidden draws use a deterministic stream separate from identifiers/metadata and are held fixed across twins. Exactly two target scope assignments change; report identities/results/order and labels remain fixed. Request bodies are explicit public projections and never dumps of research envelopes. Both load levels are implemented; no main load is selected before a real pilot.

Scoring precedence is multiple tool calls, then explicit provider refusal, then no-call, then argument/target validation. Refusal is a terminal model outcome; the once-only no-tool re-prompt will apply to non-refusal no-tool responses in the harness. Invalid tools terminate without successful-decision resampling. Valid inspect fees charge exactly once. Commit responses do not reveal unchecked correctness or realised loss. First-action regret values optimal continuation; actual continuation outcomes remain separate. Invalid sensitivity uses the worst among **all** valid first actions, including against-report commits (MAIN loss150, regret120), as documented in the oracle derivation.

Independent AI review found compound schema gaps: duplicate targets, incomplete metadata permutations, load/state coverage mismatch, and inconsistent seed/dataset/index/polarity fields. Added compound validators and six regression cases; the focused world suite then passed15 tests. Earlier core world tests passed9; renderer tests passed31, then passed31 again after strengthening a probe-contamination assertion; oracle tests passed105 twice; sandbox/scoring tests passed55, then58 after mutation-isolation and outcome regressions. These are automated synthetic checks, not human review or model observations.

`uv lock --offline` first encountered a sandbox cache write error; retry with a workspace cache completed but could not resolve uncached httpx. No network workaround was used. The design explicitly permits pip+lock, so `requirements.lock` pins32 currently installed transitive versions, with metadata fingerprints in `research/environment.lock.json`; `python -m pip check` passes. Fresh isolated package installation remains unverified without an offline wheelhouse. Audit-verifier assumptions tied to the initial M1 state now check the preserved baseline, while current implemented test paths and completed milestone evidence are checked separately; no experiment assertion was weakened.

Full current acceptance commands and actual outputs are recorded in `research/checks/milestone2.json`. Generated files are labelled research-only synthetic inputs; the oracle table is analytic, not empirical. No real calls, cost, pilot selection, freeze, or human participation occurred.

Milestone-2 delivery first reached `d3e9325564016636c711e4f6a803c288f9cb626d`, verified against remote `main`. A staged whitespace check reported two trailing blank lines, but its shell status was incorrectly masked by a later successful command. This review-process defect is explicitly recorded: removed the blank lines, switched acceptance command execution to individually checked exit codes, and retested before closing the milestone. Also fixed `.gitattributes` to preserve LF for JSONL, prompts, TOML and lockfiles so Windows checkouts do not invalidate data hashes. The source protocol retains its byte-preserving exception. A corrective checkpoint will close milestone 2 before milestone 3 starts.

Milestone 2 closed at corrective commit `07973dfbb2037d7a5e2c358749620d7da07a7d8b`; local and remote `main` matched exactly. Its full retest passed210 tests. Only then did milestone 3 implementation begin.

## 2026-11-14 — M3: offline provider, execution and analysis

Implemented an injected-transport provider contract, complete deterministic manifests, durable hash-linked call journals, manifest-driven resume/replay, analysis, figures, matched-trace export and numeric claim-evidence export. No network transport is available. Real OpenRouter documentation/field compatibility, model/upstream provider selection, rate limits and pricing are explicitly unverified offline. Settings for the local synthetic fixture are pinned separately and cannot be mistaken for an approved empirical model.

The provider fixes request settings and records raw safe response evidence, request IDs, returned model/provider, finish reason, numeric usage, latency, errors and exact request hashes. It permits four infrastructure attempts total with identical payloads and no successful-decision resampling. Review repairs prevent negative/non-finite usage from corrupting logs, prevent redaction from converting invalid arguments into valid actions, and classify only explicit deterministic refusal forms. Provider validation progressed30 →49 →61 →63 passing tests as coverage and repairs were added. These are mock transports, not wire verification.

The harness reuses durable successful responses, preserves retry budgets, allows one frozen no-tool re-prompt per decision episode, and records ambiguous in-flight outcomes as missing. It reconciles raw responses with parsed replies, requests with settings and hashes, tool state transitions with replay, and scores/usage with raw traces. Credential/header checks occur before logging a request or storing provider settings. Unknown/torn journal content is preserved with an explicit recovery blocker rather than silently repaired or resampled.

Independent review reproduced corruption from a reentrant second writer to the same run directory. Added a nonblocking operating-system lock held through execution and replay; the OS releases it on process death. Tests confirm a second writer fails before another fixture call or journal mutation. Two full-matrix test attempts also stopped on `input_hashes_changed` while other agents edited source files; these were real validation failures caused by concurrent editing. Source was held stable, and the formerly failing full-matrix case plus writer-lock regression both passed. The hash guard was retained without relaxation.

Analysis uses the exact paired estimand, whole-world percentile bootstrap (10,000 resamples; seed314159), exact two-sided sign test, planned denominators, explicit missingness bounds and invalid-action sensitivity. It covers readback/recognition-action association, all controls, regret, post-inspection decisions and realised loss. Synthetic interpretation is always suppressed. Review found and repaired two further evidence errors: oracle D=+1.00 references were mislabeled as run outcomes in the evidence map; and direct analysis of a truncated empirically tagged main manifest could otherwise emit a definitive interpretation. Oracle references/configuration quantities now carry their own evidence labels, and unconditional main interpretation requires the full prescribed factor set. The focused analysis/figures/evidence retest passed25 tests.

The final integration suite and full persistent synthetic pipeline operate on fixed source files. All artifacts are under `evaluation/synthetic_main_load2`, explicitly synthetic. The fixture deterministically inspects the first target and is neither an AI model nor an oracle policy. Source/config/data hashes, immutable raw journal, duplicate-free completed resume, exact offline score/usage regeneration, figures, matched trace and claim-evidence mapping are checked. This does not satisfy real smoke/pilot gates or justify a freeze. Clean-code clone reproduction uses the same installed host environment; a fresh dependency install remains unverified without a wheelhouse.

The integrated suite passed353 tests; the first persistent synthetic validation completed704 cells and1,152 local fixture calls with no retry/invalid/missing cells. Its completed resume made zero further fixture calls and derived outputs regenerated byte-for-byte. Final whitespace review then found two extra EOF blank lines in configuration files. Before removing them, preserved every original run input in `evaluation/synthetic_main_load2/input_snapshot.zip` and left its raw journal unchanged. The corrected inputs are validated in a **new synthetic run ID**, `evaluation/synthetic_main_load2_final`; the earlier run is explicitly marked superseded. No empirical sample was collected or resampled.
