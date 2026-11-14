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
