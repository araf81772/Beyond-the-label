# Beyond the Label

**The Label Survived. Which Case Did the Agent Check?**

Offline engineering checkpoint, 14 November 2026 (Australia/Sydney). Milestone 1 is delivered; milestone 2 implements deterministic worlds, rendering, analytic scoring, and the tool sandbox. The repository was empty at intake; the remote's initial Git attributes commit was subsequently preserved. No pre-existing experiment code or observations were found.

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

The initial milestone-1 pytest attempt found no tests; that historical evidence remains intact. Current tests cover world integrity, T1–T6 core behavior, deterministic rendering, readback prefixes, exact oracle values, sandbox transitions, and outcome accounting. Full provider/harness validation T7–T8 belongs to milestone 3.

`requirements.lock` pins 32 installed transitive packages for Python 3.14.7 on Windows; `research/environment.lock.json` records their metadata fingerprints. `python scripts/lock_environment.py` regenerates this offline snapshot. `uv lock --offline` failed because required index/wheel data is absent, so the design's permitted pip+lock alternative is used. `python -m pip check` passes. A fresh isolated package installation is **not verified**; offline reinstall requires a compatible wheelhouse via `python -m pip install --no-index --find-links <wheelhouse> -r requirements.lock`. No dependency was downloaded.

## Execution prerequisites

OpenRouter is specified as the routing service. The model, upstream provider, reasoning setting, output-token limit, numeric spending cap, and provider rate/concurrency limits are not selected. No checked provider credential is present in the current process environment. The design's “under US$20” is a planning estimate, not authorization or measured expenditure. No paid calls were made during this audit.

Delivery uses the user-supplied existing repository, [araf81772/Beyond-the-label](https://github.com/araf81772/Beyond-the-label), on `main`. No GitHub repository was created or visibility changed. NUMERIC's information-sufficiency ambiguity was resolved by explicit user approval of amendment A1: retain report facts alongside the prescribed losses.

The user requires offline research execution. Git delivery is the requested exception. There is no execution freeze, model observation, effect estimate, confidence interval, observed regret, pilot decision, human trace review, or empirical report. Synthetic world inputs and analytic references must not be counted as model results.
