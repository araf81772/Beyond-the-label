# Beyond the Label

**The Label Survived. Which Case Did the Agent Check?**

Milestone 1 audit checkpoint, 14 November 2026 (Australia/Sydney). The repository was empty at intake: an unborn `master` branch, no commits, no remote, and no project files. No pre-existing project code or experimental observations were found in this checkout.

The contribution specified for this project is: “A fixed-report scope-binding swap with audited delivery and enacted verification under changing payoffs.” This is a planned study, not a claim supported by collected results.

- [Authoritative design](research/protocol.md): byte-for-byte archive of the supplied `final_design.txt`, all 581 lines reviewed. Its historical citation claims are not newly verified.
- [Audit and blockers](research/audit.md), [requirements map](research/requirements.csv), and [decision log](research/decisions.md).
- [Six-milestone status](research/milestones.json), [runtime baseline](research/baseline.json), and [source provenance](research/source_manifest.json).

## Verify this checkpoint

From the repository root in PowerShell:

```powershell
python --version
uv --version
python scripts/verify_audit.py
git diff --check
git status --short
```

The verification script uses the Python standard library only. It checks source integrity, requirement coverage, milestone records, and selected credential patterns without printing secrets. It does **not** validate the experiment or replace required tests T1–T8.

The initial `python -m pytest -q` attempt found no tests. No experiment, package definition, dependency lock, provider adapter, or run harness exists yet. Installed package versions in `research/baseline.json` are an observed host snapshot, not a reproducible project environment. A pinned environment and experiment tests belong to implementation/validation; do not infer that the host package imports establish scientific correctness.

## Execution prerequisites

OpenRouter is specified as the routing service. The model, upstream provider, reasoning setting, output-token limit, numeric spending cap, and provider rate/concurrency limits are not selected. No checked provider credential is present in the current process environment. The design's “under US$20” is a planning estimate, not authorization or measured expenditure. No paid calls were made during this audit.

Milestone 1 is complete and delivered to the user-supplied existing repository, [araf81772/Beyond-the-label](https://github.com/araf81772/Beyond-the-label), on `main`. The initial GitHub commit and local audit history are both preserved; the pushed audit commit was verified against the remote head. Delivery evidence is in `research/baseline.json` and `research/milestones.json`. Local `origin` was configured; no GitHub repository was created and no visibility was changed. NUMERIC's information-sufficiency ambiguity remains recorded for clarification before implementing its renderer. Offline work on independent components can continue.

Milestones 2–6 have not started in this checkpoint. There is no execution freeze, model result, effect estimate, confidence interval, observed regret, pilot decision, human trace review, or report yet.
