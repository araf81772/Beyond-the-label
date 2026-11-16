# Beyond the Label

**The Label Survived. Which Case Did the Agent Check?**

Apart Research AI x Epistemics Sprint, November 2026. Track 2 (Trust Infrastructure). Authors: Tonmoy Sarker, Araf Akhter and Abidur Rahaman (Independent researchers).

## The question

Provenance metadata can survive a handoff between agents and still change nothing. When a scope label reaches the receiving agent intact, does the agent use it to decide **where to spend its one priced verification call**?

## The experiment in five lines

1. An agent must release or hold two lots. Each lot has one archived PASS/FAIL report. A report tested under the current configuration is 90% accurate; any other report is 60% accurate.
2. The agent may pay to inspect one lot, then commits. The stated goal is to minimise expected points lost.
3. **Matched twins** differ in exactly one thing: which of the two fixed reports carries the in-scope label. Report text, results, IDs, order, fees and penalties are identical.
4. An exact expected-loss oracle gives the best first action in every cell, so scoring needs no model judge. The scope swap should move the inspection; the oracle's paired effect is +1.00.
5. Controls separate real scope use from shortcuts: a fee too high to justify checking, an 800-point lot that should be checked whatever its scope, withheld scope labels, and losses stated outright. A separate no-tools readback probe measures whether the agent can read the labels at all.

Design: [research/protocol.md](research/protocol.md) (byte-preserved, interpretation thresholds in section 9; timing deviations disclosed). Oracle: [research/oracle_derivation.md](research/oracle_derivation.md).

## Current status: completed main and final paper

The main collection is complete: **704/704 terminal cells**, comprising 448 decision episodes and 256 readbacks. The frozen result is **NO_GAP_HERE_UNDER_THESE_CONDITIONS**. Separate-layout D is 0.9375, with a 95% world-bootstrap interval [0.875, 0.984375]. This is a bounded threshold result, not perfect performance or demonstrated equivalence between layouts.

- [Final PDF](report/final/beyond_the_label.pdf) and [editable DOCX](report/final/beyond_the_label.docx): official template, seven body pages, 192-word abstract, required limitations/ethics appendix and accurate AI disclosure.
- [Completed evidence bundle](results/staged_main_complete/bundle_manifest.json), [paper-specific numeric map](report/final/claim_evidence.csv), and [build/review instructions](report/final/README.md).
- H1/H2/H5 remain user-attested in their historical scope. H3 is now user-attested for all three authors; Araf-led H4 is user-attested for the completed evidence available at confirmation time. [Post-main attestation](research/post_main_human_verification.json). No initials or human worksheets were invented. Final approval of the newly generated paper remains an author responsibility.
- The approved 52-cell continuation made 84 accepted calls, with no new unknown charge and no completed-cell resampling. Staged accounting: USD 0.20233421648 known, USD 1.93872838656 still held, USD 6.85893739696 available; 1,645/3,000 attempts. Holds are not receipts.
- Two invalid first actions, sixteen invalid continuations, one missing continuation and MASKED truncation in 21/32 first replies remain disclosed. All scientific and operational freezes are unchanged. No additional inference or submission was performed for paper preparation.

The stopped 652-cell checkpoint below is retained as history. Its partial conclusion and pending-review statements are superseded by this section and the linked completed evidence.

## Historical checkpoint: main stopped at 652/704 cells

| Stage | State |
|---|---|
| Offline tests and audit | **Passed in the unsynced execution clone:** 1,680 tests; integrity audit and dependency checks; 121 focused retests and fresh readiness after an invocation-only correction. Post-run audit passed 1,583 checks; clean-code reproduction matched all ten partial-bundle artifacts. The earlier Windows fixture failure remains historical. [Launch validation](research/checks/main_execution_preparation.json) |
| Earlier smoke, USD 1 allowance | **Partial and closed.** 54 real observations from DeepSeek V4.1 Flash via OpenRouter/PrimeIntellect on 4 smoke worlds. Smoke is a pipeline check and is never analysed as a result |
| New smoke, pilot, load-8 smoke (USD 9 allowance) | **Executed.** Smoke 80/80 cells, pilot 160/160 (15 of 16 MAIN pairs fully correct, 15 of 16 NUMERIC optimal: load-8 selected), load-8 smoke 80/80. 525 pre-main calls, USD 0.0696 known charges. Smoke is never analysed; the pilot only selects the load |
| Human checks and decisions | **H1/H2/H5 complete, user-attested.** H1 was late; thresholds and MASKED limitation accepted unchanged. D4 leads are now assigned: current user for H3, Araf for H4. Each member's H3 audit remains required; H3/H4 remain pending. The assignment after freeze is disclosed. [Attestation and scope](research/human_verification.json) |
| Freeze and main (USD 9 allowance) | **Partial main, blocked.** 652/704 cells completed; 51 untouched and one pending readback. The unchanged guard stopped after 40 HTTP 429 unknown-cost holds. No relaunch or limit change. [Execution report](research/main_execution_report.md) |
| Execution freeze | [research/execution_freeze.json](research/execution_freeze.json): commit `6f8f94b3542980f65ba08f56aa3a12bf12c9e41d`, load-8, tag `btl-freeze-v1`, verified on `origin` |
| Main effect, intervals, controls | [Partial empirical bundle](results/staged_main/bundle_manifest.json) verified. Frozen conclusion: **INCONCLUSIVE_WITH_INFRASTRUCTURE_MISSINGNESS**. Observed-pair estimates do not establish a completed 64-world result |

Staged accounting after main: 1,561 attempts, USD 0.19176235952 known charges, USD 1.93872838656 retained holds, USD 6.86950925392 available. Main alone has USD 0.12217898752 known charges; its total cost is unknown. Extra funds do not clear the hold-count blocker. The earlier closed USD 1 session is separate and unchanged.

Synthetic fixtures under `evaluation/` exercise the software only. They are labelled synthetic and are excluded from every empirical count.

`report/manuscript.md` and `report/pre_results.pdf` are the **pre-results draft from an earlier checkpoint**. They were written before any model call and still say that no observation exists and name a free model that was never used. They are kept as a dated artifact and are not the submission; see [report/SUBMISSION_GUIDE.md](report/SUBMISSION_GUIDE.md).

## Run it

Python 3.11 or newer. The lockfile was produced on 3.14.7 and also installs on 3.12.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock
$env:PYTHONPATH = 'src'
python -m pytest -q
python scripts/verify_audit.py
```

No test contacts a network or reads a real key. Paid stages need `OPENROUTER_API_KEY` in a git-ignored `.env` (template: `.env.example`) and a key hard limit of at most USD 10:

```powershell
python -m beyond_label.staged status
python -m beyond_label.staged check-ready --stage smoke
python -c "from beyond_label.staged import main; raise SystemExit(main())" execute --stage smoke
```

`status` is offline. `check-ready` makes read-only requests only. `execute` is the only command that spends money.

## What was done during the sprint

The initial idea and local design draft predated the sprint opening on 13 November 2026; Tonmoy Sarker and Araf Akhter developed them. The user clarified that **no preexisting code is included**. Abidur Rahaman contributed code during the sprint. Sprint work comprised completing and validating the instrument, controlled execution and provenance checks, smoke and pilot stages, the scientific freeze, main collection and its bounded continuation, analysis and reporting. All three authors reviewed the study data. Git commit dates alone were not used to infer when the idea or draft originated. [Confirmed disclosure](report/final/author_metadata.json).

AI assistance: OpenAI Codex assisted implementation, tests, execution controls, evidence verification and final-report drafting. Claude (Anthropic) reviewed the repository and implemented the staged execution path on v1. No LLM judges experimental decisions. Human checks are user-attested and documented separately; the late H1/D3/D4 timing and absent individual worksheets remain disclosed.

## Repository map

| Path | Contents |
|---|---|
| `research/protocol.md`, `research/amendments.md` | Authoritative design and its one approved amendment |
| `src/beyond_label/` | Worlds, oracle, rendering, sandbox, scoring, analysis, execution controls |
| `prompts/`, `data/`, `configs/` | Frozen prompts, seeded worlds and plans, pinned settings |
| `tests/` | Offline tests, including T1-T8 from the protocol |
| `runs/` | Real model traces: the closed partial smoke; staged runs appear here |
| `evaluation/` | Analytic oracle table and synthetic software fixtures |
| `research/decisions.md`, `research/checks/` | Dated decision log and check records |
| `report/` | Official template, pre-results draft, submission guide |

---

# Engineering record

The sections below are the detailed engineering log up to the closed USD 1 smoke. They are kept for provenance. Where they say paid execution is smoke-only or that pilot and main have no entry point, that describes the closed authorization; the staged path above supersedes it.

Checkpoint: 15 November 2026, Australia/Sydney. **M4 is incomplete and M5 is not ready.** The authorized continuation accepted 93 calls and completed 53 new smoke cells, then stopped on a continuation timeout whose charge is unknown. The original rejected readback was never rerun. Across the 80 planned cells: 53 completed episodes, one partial episode with an observed first action, 25 untouched cells and one retained terminal missing readback. There are 54 first-action/readback observations; smoke observations are excluded from main results. Pilot, main and freeze have not started.

The endpoint-ID repair is working in the accepted calls. The remaining immediate blocker is `paid_cost_reconciliation_required`: the new unknown charge retains its full USD 0.048468209664 bound. Known cumulative charges are **USD 0.0125113232**; total holds are **USD 0.489310289664**, including the unchanged historical USD 0.44084208 hold. **USD 0.498178387136 and 104 attempts remain** under the same USD 1 / 200-attempt smoke limits. Spare allowance does not resolve missing billing evidence. No hold was refunded and no successful decision was resampled.

[Partial smoke outcome](research/checks/smoke79_outcome.json), [execution record](research/checks/smoke79_execution.json), [M4/M5 readiness gaps](research/m4_m5_readiness.md), and [prepared source provenance](research/smoke_continuation79.md). The paid pilot/main path, paid-evidence freeze verification and retained-missing smoke acceptance still need work. The current instruction required stopping and reporting before pilot/main. All 48 execution inputs remain at tested source `eebba9de7a9923d2a81d17f7631d41371a35ef5e`; no production source changed during collection. Post-run validation passed **1634 tests**, 1383 audit checks and byte-identical offline replay. These checks validate the retained partial evidence; they do not complete M4.

The [pre-results manuscript](report/manuscript.md) names **Tonmoy and Araf**, with affiliations pending. It includes methods, analytic references, NOT RUN results and the required ethical/limitations appendix. The official template has been retrieved and retained. [Report artifacts and reproduction](report/README.md). No H1-H5 human review, author contribution, submission or publication is inferred from the confirmed names.

## Design and evidence

- [Authoritative design](research/protocol.md): byte-preserved archive of the supplied `final_design.txt`, all 581 lines reviewed. [Source hash and provenance](research/source_manifest.json).
- [Approved NUMERIC amendment and fixed analysis conventions](research/amendments.md). The archive remains unchanged.
- [Requirement map](research/requirements.csv), [decisions](research/decisions.md), [exactly six milestone records](research/milestones.json), and [initial audit](research/audit.md).
- [Oracle derivation](research/oracle_derivation.md) and [analytic table](evaluation/oracle_table.csv). MAIN reference losses are oracle 30, always-commit 50 and random single inspection 45; oracle D is +1.00. These are not model observations.
- [Verified primary references](research/related_work.md) and [official-template provenance](research/checks/report_preparation_sources.json). Citation verification was AI review, not human H5 review.

The initial audit found no pre-existing experiment implementation or observations in this checkout. The remote's initial Git attributes commit was preserved. Earlier proposal and citation-access statuses remain historical in the decision and check records.

## Setup and offline tests

The project requires Python >=3.11. `requirements.lock` and `research/environment.lock.json` record the tested Python 3.14.7 Windows environment and 32 installed packages. No dependency was downloaded during offline preparation. A same-host clean clone does not establish a fresh installation; offline installation requires compatible wheels:

```powershell
python -m pip install --no-index --find-links PATH_TO_WHEELHOUSE -r requirements.lock
```

With dependencies installed, run from the repository root:

```powershell
$env:PYTHONPATH = 'src'
python -m pytest -q
python scripts/verify_audit.py
python -m pip check
git diff --check
```

The suite blocks network connections and substitutes temporary credentials. Tests cover T1-T8, sandbox transitions, post-inspection scoring, provider serialization/retries, usage, hashes, missingness, resume, controls, analysis and evidence packaging. The audit checks source integrity, selected secret patterns and consistency between milestone claims and raw evidence; it does not replace the experiment tests. Historical failed checks and repairs are preserved in `research/checks/` and the decision log.

## Reproduce without model calls

```powershell
python scripts/validate_offline.py --output evaluation/synthetic_main_load2_preresults
python scripts/rehearse_offline.py --output evaluation/synthetic_m4_preresults
python -m beyond_label.finalize --planned --output results/planned
python -m beyond_label.finalize --run evaluation/synthetic_main_load2_preresults --output evaluation/synthetic_report_bundle --allow-synthetic
python scripts/reproduce_offline.py --output research/checks/preresults_clean_clone.json
```

The main fixture exercises 704 cells and at most 1152 planned local calls. Smoke/pilot rehearsal exercises 320 fixture cells and 576 local calls, including load-8 unconditionally for coverage. These fixtures cannot select a real load or model or satisfy the empirical gates. Each run retains `manifest.json`, `calls.jsonl`, `scores.csv`, `usage.csv` and `analysis_manifest.json`; offline replay checks byte-identical regeneration and duplicate-free completed resume.

Choose a new output directory after source hashes change and preserve previous traces. The planned bundle has null empirical statistics and 704 unexecuted cells, not 704 observed infrastructure failures. The finalizer validates a stored main run in a disposable snapshot, preserves original evidence, and packages trace-derived tables, figures, a matched trace and claim-evidence hashes. Synthetic input requires explicit opt-in. For an eventual real run, omit `--allow-synthetic`; packaging itself never marks M6 complete or submits a paper.

Clean-clone reproduction uses local Git objects and the same installed dependencies, strips known credential variables, performs no package installation and records timeouts as failures. Historical runs tied to earlier inputs need their compatible source snapshot for replay. `evaluation/input_snapshots/` retains the earlier archive; do not rewrite historical data to pass a newer replay check.

## Credentials and execution controls

The ignored project-root `.env` can supply `OPENROUTER_API_KEY`. Existing process values take precedence; unrelated variables are ignored and interpolation is disabled. The file is never included in manifests or input snapshots. Presence only can be checked offline:

```powershell
python -m beyond_label.environment
```

Do not print keys or authorization headers. Presence does not verify authentication, quota, a hard limit, budget or permission to spend. [Credential-loading evidence](research/checks/env_presence.json) is historical; [paid account evidence](research/checks/paid_smoke_ready_preflight.json) records only safe limit/usage fields, never the key or headers.

The disabled free candidate is OpenRouter `nvidia/nemotron-3.5-super-vl:free`, pinned to route `nvidia` and identity `Nvidia`, temperature 0, reasoning disabled, 512 output tokens, automatic tool choice, parallel tools disabled and concurrency 1. Real wire compatibility and pilot selection remain unverified. [Free execution settings and sources](research/free_execution.md), [configuration](configs/free.yaml).

`attempts.py` reserves each authorized attempt durably before dispatch, shares the ceiling across stages/restarts, and never refunds a reservation. An interrupted pre-dispatch reservation consumes allowance but is not a confirmed provider call or charge. Never reset `runs/_free_session/attempts.jsonl`. The budget ledger separately preserves known and unknown costs. The separate paid counter permits at most 200 attempts for the one authorized smoke and never changes the historical free counter. Silent fallback, pilot/main and unverified execution settings are rejected.

The earlier USD 20 proposal remains unapproved historical planning in [readiness](research/execution_readiness.md). The current [paid smoke config](configs/paid_smoke.yaml) adds only the explicit selected-endpoint identity mapping for the approved DeepSeek/PrimeIntellect route. Top-level identity, fixed settings and shared limits remain strict. Both historical attempts, the known charge and the original hold carry forward without reset. Real smoke and the separately authorized full pilot must precede freeze and main execution. No main call may start before verified freeze evidence; material post-freeze changes require approval and a new run/freeze.

The 79-cell continuation has been prepared with the following one-time command. It is recorded here for provenance; do not rerun it against the existing record. Verify the prepared record with `python scripts/verify_audit.py`. The v2 preparation record remains unchanged:

```powershell
python scripts/prepare_smoke79.py --source-commit eebba9de7a9923d2a81d17f7631d41371a35ef5e
```

This writes `research/smoke_continuation_79.json` after replaying both historical runs; it creates no execution directory and makes no provider/account calls. A later fresh readiness check uses public/account GET requests only:

```powershell
python -m beyond_label.paid_live --check-ready
```

The default invocation also checks readiness only. `--execute` is outside the current no-paid-calls repair instruction. A future v3 segment retains all 80 planned cells, with the historical failure marked `retained_terminal`, no new events or observation for that row, and only 79 dispatchable cells. Shared attempts and costs remain cumulative. [Current preparation procedure](research/smoke_continuation79.md); [historical v2 readiness](research/smoke_readiness.md).

Routine delivery uses the user-supplied existing repository [araf81772/Beyond-the-label](https://github.com/araf81772/Beyond-the-label), branch `main`. No repository creation, visibility change, force-push, publication or submission is part of this checkpoint.


## Reproduce the partial smoke without calls

```powershell
python scripts/replay_history.py --run runs/paid_smoke_gpt41mini_20261115
python scripts/smoke_diagnostics.py --run runs/paid_smoke_gpt41mini_20261115
python scripts/verify_audit.py
```

Historical replay verifies the exact committed source and all original input/file hashes, strips credentials, blocks network connections and compares regenerated outputs byte-for-byte. The corrected diagnostic report distinguishes the one attempted failure from 79 untouched cells without overwriting collection-version scores. A separately prepared source-continuation record binds the approved repair to its own committed inputs; both historical replay and ordinary resume retain strict hash checks. A changed request is never recorded as an identical infrastructure retry. Historical replay does not authorize execution.
