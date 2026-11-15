# Beyond the Label

**The Label Survived. Which Case Did the Agent Check?**

“A fixed-report scope-binding swap with audited delivery and enacted verification under changing payoffs.”

Checkpoint: 15 November 2026, Australia/Sydney. Milestones 1-3 are complete within the offline engineering scope. M4 real smoke/pilot/freeze and M5 main execution have not occurred. Independent M6 analysis/report/reproduction preparation is available; empirical findings and the final paper remain pending. No model inference was made, no execution freeze exists, and synthetic tests are excluded from empirical evidence.

The latest user instruction defers smoke until a budget update. Paid calls remain forbidden. The durable ceiling is still **10 aggregate free inference attempts** across stages, retries, re-prompts and continuations; it cannot complete the required 80 initial smoke cells. The latest historical key check authenticated but did not verify the required USD 0 hard spending limit. Both execution flags remain disabled; this checkpoint performs no account recheck. [Remaining gates and handoff](research/offline_completion.md).

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

Do not print keys or authorization headers. Presence does not verify authentication, quota, a hard limit, budget or permission to spend. [Credential-loading evidence](research/checks/env_presence.json) is historical; [latest account evidence](research/checks/durable_cap_account_preflight.json) reports authentication with `zero_hard_limit:false`.

The disabled free candidate is OpenRouter `nvidia/nemotron-3.5-super-vl:free`, pinned to route `nvidia` and identity `Nvidia`, temperature 0, reasoning disabled, 512 output tokens, automatic tool choice, parallel tools disabled and concurrency 1. Real wire compatibility and pilot selection remain unverified. [Free execution settings and sources](research/free_execution.md), [configuration](configs/free.yaml).

`attempts.py` reserves each authorized attempt durably before dispatch, shares the ceiling across stages/restarts, and never refunds a reservation. An interrupted pre-dispatch reservation consumes allowance but is not a confirmed provider call or charge. Never reset `runs/_free_session/attempts.jsonl`. The budget ledger separately preserves known and unknown costs. Paid requests, silent fallback and unverified execution settings are rejected.

The earlier paid-model/configuration proposal, including its suggested USD 20 ceiling, remains **unapproved** planning in [readiness](research/execution_readiness.md). An announced future budget does not authorize spending now. After budget/attempt authorization and required account checks, real smoke and the full pilot must precede the freeze and main run. No main call may start before verified freeze evidence; material post-freeze changes require approval and a new run/freeze.

Routine delivery uses the user-supplied existing repository [araf81772/Beyond-the-label](https://github.com/araf81772/Beyond-the-label), branch `main`. No repository creation, visibility change, force-push, publication or submission is part of this checkpoint.
