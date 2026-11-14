# Beyond the Label

**The Label Survived. Which Case Did the Agent Check?**

Offline engineering checkpoint, 14 November 2026 (Australia/Sydney). Milestones 1–3 are complete within the offline scope and delivered. Milestone 4 preparation now adds trace-derived pilot summaries, stricter execution prerequisite checks and a synthetic smoke/pilot/load-8 rehearsal. Milestones 4–6 remain explicitly blocked by the offline instruction and absent real experimental inputs; they are not claimed complete. The repository was empty at intake; the remote's initial Git attributes commit was subsequently preserved. No pre-existing experiment code or observations were found.

Current update: the free-only HTTP adapter, quota-aware manifest path, empirical pilot summaries and freeze verification are implemented for offline testing. One authorized read-only key-status request returned **HTTP 401**; no inference call occurred. The user then requested **offline work only**. Both execution and account preflight in [configs/free.yaml](configs/free.yaml) are disabled. See [free execution preparation and exact blockers](research/free_execution.md).

The contribution specified for this project is: “A fixed-report scope-binding swap with audited delivery and enacted verification under changing payoffs.” This is a planned study, not a claim supported by collected results.

- [Authoritative design](research/protocol.md): byte-for-byte archive of the supplied `final_design.txt`, all 581 lines reviewed. Its historical citation claims are not newly verified.
- [Audit and blockers](research/audit.md), [requirements map](research/requirements.csv), and [decision log](research/decisions.md).
- [Six-milestone status](research/milestones.json), [runtime baseline](research/baseline.json), and [source provenance](research/source_manifest.json).
- [Approved NUMERIC amendment and implementation conventions](research/amendments.md).
- [Oracle derivation](research/oracle_derivation.md) and [analytic reference table](evaluation/oracle_table.csv), neither empirical observations nor human-reviewed results.

## Run offline checks and regenerate inputs

From the repository root in PowerShell:

```powershell
python --version
uv --version
python scripts/verify_audit.py
python -m pytest -q
python -m pip check
$env:PYTHONPATH = 'src'
python -m beyond_label.generate --output data
python -m beyond_label.oracle --output evaluation/oracle_table.csv
git diff --check
git status --short
```

The audit script checks source integrity, requirement coverage, milestone records, and selected credential patterns without printing secrets. It does **not** replace the experiment test suite. Tests block network socket connections. Detailed acceptance outcomes and repair history are in `research/checks/` and the decision log.

The initial milestone-1 pytest attempt found no tests; that historical evidence remains intact. Current tests cover T1–T8, world integrity, deterministic rendering, exact oracle values, sandbox transitions, provider payloads/retries, interruption recovery, independent readback prefixes, paired analysis and evidence provenance. Synthetic fixtures and mock usage are excluded from empirical results.

## Synthetic offline pipeline

```powershell
python scripts/validate_offline.py --output evaluation/synthetic_main_load2_env
python scripts/reproduce_offline.py
```

The first command builds provisional manifests for both possible main loads, runs all 704 main-plan cells through a deterministic local fixture, checks immutable traces and duplicate-free resume, and regenerates scores, usage, analysis, figures, a worked matched trace and a numeric evidence map. It makes **zero real provider calls**. Every output is labelled synthetic. The fixture always inspects the first target, so its outcomes are a pipeline check, not evidence about an AI model. The chosen main load remains unset.

Each synthetic run contains `manifest.json`, `calls.jsonl`, `scores.csv`, `usage.csv`, and `analysis_manifest.json`, plus labelled analysis artifacts. Its manifest hashes source, prompts, configuration and data inputs; changed inputs block resume/replay. Use a new output directory for a new code version and preserve prior raw traces. A torn or ambiguous interrupted attempt is recorded or blocked explicitly rather than resampled. No valid/invalid decision is resampled, and each decision episode permits at most one exact no-tool re-prompt.

The second command tests a clean local Git clone against the same installed environment, without network or package installation; its result is separate from fresh-environment reproducibility. The pinned OpenRouter serializer has only an injected local transport. Public provider-field and pricing documentation has now been reviewed; real delivery, returned metadata, account limits and authentication remain unverified. The live transport and real-run configs are disabled.

Milestone-3 validation evidence remains preserved: [353-test suite](research/checks/milestone3_suite.json), [clean clone](research/checks/clean_clone.json) and [committed input hashes](research/checks/committed_inputs.json). The two earlier synthetic main runs retain their raw traces and original input snapshots. Continuing pre-freeze engineering uses a new synthetic run directory; none of these fixtures supplies empirical evidence.

`requirements.lock` pins 32 installed transitive packages for Python 3.14.7 on Windows; `research/environment.lock.json` records their metadata fingerprints. `python scripts/lock_environment.py` regenerates this offline snapshot. `uv lock --offline` failed because required index/wheel data is absent, so the design's permitted pip+lock alternative is used. `python -m pip check` passes. A fresh isolated package installation is **not verified**; offline reinstall requires a compatible wheelhouse via `python -m pip install --no-index --find-links <wheelhouse> -r requirements.lock`. No dependency was downloaded.

## Offline smoke and pilot rehearsal

```powershell
python scripts/rehearse_offline.py
$env:PYTHONPATH = 'src'
python -m beyond_label.pilot evaluation/synthetic_m4_rehearsal_env/synthetic_pilot_load2 --allow-synthetic
```

The rehearsal covers four smoke worlds at load-2, all eight pilot worlds, and the four smoke worlds at load-8: 320 fixture cells and 576 successful local fixture calls. Each stage verifies trace-derived scoring, usage, byte-identical regeneration and zero additional calls on completed resume. Load-8 is exercised unconditionally for offline coverage; it is not an actual pilot selection.

The pilot summary verifies the complete plan, raw journal and all derived files before computing the 16 paired MAIN outcomes and 16 NUMERIC outcomes. Altered scores, duplicate events and empirical relabeling fail verification. Invalid observations remain in the denominators; incomplete observations block threshold evaluation. The fixed first-target fixture produces 0/16 fully correct MAIN pairs and 8/16 optimal NUMERIC calls, which exercises the hypothetical floor-rule branch. It cannot decide an actual model change, select a load or authorize a freeze.

Evidence: [rehearsal](evaluation/synthetic_m4_rehearsal/rehearsal.json), [gate regression cycle](research/checks/m4_gate_regression.json), [434-test integration suite](research/checks/m4_suite_final.json), and [renewed main-matrix validation](evaluation/synthetic_main_load2_m4prep/offline_validation.json). The [pre-loader clean-clone check](research/checks/m4_clean_clone.json) also passed all 434 tests; [all committed input hashes](research/checks/m4_committed_inputs.json) match. Necessary execution fields now reject non-finite caps/rates, malformed settings and truthy strings used as verification flags; those field checks do not authenticate real authorization or experimental evidence.

## Execution prerequisites

OpenRouter is specified as the routing service. The [proposed M4 configuration](configs/proposed_m4.yaml) selects `openai/gpt-4.1-mini` through the `openai` route, temperature 0, reasoning omitted, 512 output tokens and concurrency 1. The proposed USD 20 M4 ceiling is **not spending authorization**. Active configs stay disabled; account limits and real compatibility remain unverified. [Readiness and sources](research/execution_readiness.md) records prices, the upstream January 2027 retirement schedule, limitations and remaining work. A local credential loads automatically from the ignored project-root `.env`; presence does not verify authentication or authorize spending. The design's “under US$20” remains a historical estimate. No paid calls were made.

That paid-model proposal is retained as historical planning. The subsequent free-only candidate is `nvidia/nemotron-3.5-super-vl:free`, pinned to `nvidia`/`Nvidia`, with zero request price ceilings. Its settings are retained in a separate disabled configuration. The local key was rejected by authentication; replacing it does not by itself revoke the user's restored offline instruction.

Delivery uses the user-supplied existing repository, [araf81772/Beyond-the-label](https://github.com/araf81772/Beyond-the-label), on `main`. No GitHub repository was created or visibility changed. NUMERIC's information-sufficiency ambiguity was resolved by explicit user approval of amendment A1: retain report facts alongside the prescribed losses.

The user requires offline research execution. Git delivery and read-only public provider documentation/pricing research are the requested exceptions. There is no execution freeze, model observation, effect estimate, confidence interval, observed regret, pilot decision, human trace review, or empirical report. Synthetic world inputs and analytic references must not be counted as model results.


## Local credential loading

The provider loads known credential names from the project-root `.env` automatically when checking presence, constructing a provider, serializing a request or parsing a response. Existing process values take precedence, including explicit empty values. Other `.env` settings are ignored, interpolation is disabled, and importing a module does not load credentials. The user-authorized local `.env` is Git-ignored and never included in run manifests or input snapshots.

Check presence only, without contacting a provider:

```powershell
$env:PYTHONPATH = 'src'
python -m beyond_label.environment
```

The command emits booleans and fixed error codes only. Do not print the file or environment values. Both real execution guards remain disabled; a detected key is not a budget, model choice or permission to spend. Tests use temporary fake credentials and cannot read the user's real `.env`.

Adding the loader changes source hashes. The earlier four synthetic runs retain their original bytes and are tied to commit `34c9438`; their 29 original inputs are archived in `evaluation/input_snapshots/34c9438_before_env_loading.zip` without credentials. Current commands use new output directories for future validation instead of rewriting historical traces. The full test suite exercises fresh synthetic runs under the current source.

Credential-loading validation: [453-test suite](research/checks/env_loading_suite_final.json), [safe regression summaries](research/checks/env_loading_regressions.json), and [presence-only check](research/checks/env_presence.json). The key was detected locally; this does not establish online authentication. No paid calls were made.

## Offline budget, rate and provider safeguards

The current checkpoint passes [607 tests](research/checks/m4_safeguards_suite.json). [Regression evidence](research/checks/m4_safeguards_regressions.json) records failures and repairs for ledger paths, provider identity, response preservation after settlement errors, and rate checks after slow durable writes. All use local fixtures.

```powershell
python -m pytest -q tests/test_budget.py tests/test_rate_limit.py tests/test_controls.py tests/test_provider.py
python -m pytest -q
python scripts/verify_audit.py
```

The helpers reserve funds and rate capacity for each attempt, retain unknown costs, and preserve returned decisions when local settlement fails. Live HTTP/runner integration, verified cost/token bounds, restart reconciliation, account limits and spending authorization remain required. See the [readiness record](research/execution_readiness.md); no live command is provided or enabled.

## Current free-only engineering validation

The stabilized full suite passed [901 tests](research/checks/free_engineering_suite.json); [regression records](research/checks/free_engineering_regressions.json) retain failures and repairs. The HTTP adapter uses local mocks in tests, and the full suite receives no real credentials. Both free execution and account preflight are disabled. Real smoke/pilot/main observations remain absent, with HTTP 401 authentication and the restored offline instruction recorded as blockers.
