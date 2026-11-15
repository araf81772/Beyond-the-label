# Staged execution runbook: smoke, pilot, freeze, main

Prepared 15 November 2026 (AEDT) on branch `v1`. Every paid stage starts only when a person runs its `execute` command.

**State on 16 November 2026:** M4 gates and the unchanged load-8 freeze are verified. The authorized main ran and stopped at 652/704 completed cells after reaching the fixed 40 unknown-cost-hold limit from HTTP 429 failures. There are 51 untouched cells, one pending readback and one missing continuation in an otherwise observed episode. Do not relaunch, release holds or change limits implicitly. The partial analysis is inconclusive with infrastructure missingness. See [execution report](main_execution_report.md), [command outcome](checks/main_execution_command_canonical.json) and [post-run review](checks/main_postrun_review.json).

**Human-check update:** [human_verification.json](human_verification.json) records H1/H2/H5 complete on the current user's attestation for themselves and Araf. H1 was late; the existing thresholds and MASKED limitation are accepted unchanged. The current user now leads H3, and Araf leads H4. Each team member must still independently complete the H3 audit; H3/H4 remain pending until their later protocol stages. D4's assignment after freeze is a disclosed timing deviation. A token-cap change would invalidate the existing gates and require repeating smoke and pilot (and load-8 smoke if selected again).

**Single execution location:** `C:/Users/tonmo/CodexRuns/beyond-the-label-v1-main-20261116` is the unsynced main execution clone. The original OneDrive checkout is for documentation and delivery, and must not dispatch main concurrently or independently. Collection is stopped. Preserve every scientific input, raw trace and the full retained ledgers; the remaining dollars and attempts do not override the hold-count blocker.

Authorization: `paid-staged-usd9-v1`, recorded in [staged_authorization.json](staged_authorization.json). Settings: [configs/staged.yaml](../configs/staged.yaml). Code: [staged.py](../src/beyond_label/staged.py). The protocol in [protocol.md](protocol.md) is unchanged.

## What the stages are

| Order | Stage | Command name | Cells | Planned calls | Output directory | Needs first |
|---|---|---|---:|---:|---|---|
| 1 | Smoke, load-2 (pipeline check, never analysed) | `smoke` | 80 | up to 144 | `runs/staged_smoke_load2` | offline tests pass |
| 2 | Pilot, load-2 (selects load, checks the floor) | `pilot` | 160 | up to 288 | `runs/staged_pilot_load2` | complete smoke on the same inputs |
| 3 | Smoke, load-8 (only if the pilot selects load-8) | `smoke8` | 80 | up to 144 | `runs/staged_smoke_load8` | pilot that selected load-8 |
| 4 | Freeze (record, tag, push) | `freeze` | – | 0 | `research/execution_freeze.json` | all gates above |
| 5 | Main | `main` | 704 | up to 1,152 | `runs/staged_main` | verified freeze, tag on origin |

Expected cost, from the retained smoke's mean of USD 0.000134 per call: about **USD 0.25** for all 1,728 planned calls. The cap is USD 9 and each attempt first reserves USD 0.0485.

Expected time at the fixed 10 requests per minute: smoke about 15 minutes, pilot about 30, load-8 smoke about 15, main about 2 hours.

## Before the first paid call

1. The OpenRouter key must have a **hard limit of at most USD 10 that does not reset**. Without one the readiness check stops with `staged_nonreset_key_limit_at_most_usd10_required`.
2. Work in a clone that is **not inside a OneDrive, Dropbox or other syncing folder**. The ledgers are fsynced and file-locked on every attempt; a sync client holding a file can cause a local accounting error that stops the run.
3. Offline checks pass:

```powershell
$env:PYTHONPATH = 'src'
python -m pytest -q
python scripts/verify_audit.py
```

4. The working tree is committed. The freeze later compares every input file with the committed copy, so do not edit anything under `src/beyond_label/`, `prompts/`, `configs/`, `data/`, `research/protocol.md`, `research/amendments.md`, `pyproject.toml` or `requirements.lock` between the smoke and the end of the main analysis. A changed input invalidates the smoke and pilot as freeze gates.

## Commands

**Execution invocation correction (16 November):** use the canonical-import execute command below. The `python -m beyond_label.staged` execute form loads its policy classes as `__main__`, while the live verifier imports the canonical module and rejects the duplicate types before dispatch. A network-blocked diagnostic reproduced that rejection and confirmed canonical import passes the unchanged strict guard. No frozen source, settings or gate was changed; see [invocation diagnostic](checks/main_invocation_diagnostic.json). The original failed main command and its account preflight are retained, with zero inference attempts. Readiness/status do not traverse that failing dispatch type check.

Read-only readiness check for a stage (public metadata and key-limit GET only, no inference):

```powershell
python -m beyond_label.staged check-ready --stage smoke
```

Historical command reference only; current main dispatch is blocked. Run or resume a stage only after its blocker is resolved and continuation scope is explicitly reviewed:

```powershell
python -c "from beyond_label.staged import main; raise SystemExit(main())" execute --stage smoke
```

Offline summary of everything retained so far (no network):

```powershell
python -m beyond_label.staged status
```

Then, in order:

```powershell
python -c "from beyond_label.staged import main; raise SystemExit(main())" execute --stage pilot
python -m beyond_label.pilot runs/staged_pilot_load2
```

The second command prints the trace-derived counts and the selected load. The rule is the protocol's: at least 14 of 16 fully correct MAIN pairs selects load-8, otherwise load-2; fewer than 12 of 16 optimal NUMERIC decisions means the model must change and the pilot must be repeated (not supported by this allowance without a new decision).

Only if load-8 was selected:

```powershell
python -c "from beyond_label.staged import main; raise SystemExit(main())" execute --stage smoke8
```

Freeze. Commit the gate runs first, then:

```powershell
python -m beyond_label.staged freeze --tag btl-freeze-v1
```

This verifies the gates by replaying their raw traces, checks every input against `HEAD`, and writes `research/execution_freeze.json`. It creates no tag. It prints the two git commands to run next (`git tag …` and `git push origin …`). Record the decision in `research/decisions.md`, commit the record, then:

```powershell
python scripts/sync_execution_status.py
python -m beyond_label.staged check-ready --stage main
python -c "from beyond_label.staged import main; raise SystemExit(main())" execute --stage main
```

The main stage refuses to start unless the tag is visible on `origin` and resolves to the frozen commit (protocol section 8).

After main:

```powershell
python -m beyond_label.finalize --run runs/staged_main --output results/staged_main
python scripts/sync_execution_status.py
python scripts/verify_audit.py
```

## While a stage runs

- **Do not press Ctrl-C or close the terminal mid-run.** An attempt interrupted between dispatch and reply is recorded as ambiguous and is never repeated, which leaves that cell missing for good. To run in pieces, use `--max-cells N`; the stage stops cleanly after N cells and resumes with the same command.
- Re-running `execute` for a finished stage does nothing: completed cells are never dispatched again.
- A timeout is retried up to three times with the identical request, as the protocol specifies. Its unknown charge keeps a full USD 0.0485 hold and the run continues.

## If a stage stops

The command prints `{"status": "blocked", "reason": …}`. Nothing is lost; observed replies are already on disk.

| Reason | Meaning | What to do |
|---|---|---|
| `staged_nonreset_key_limit_at_most_usd10_required` | The key has no hard limit, a limit above USD 10, or a resetting limit | Set a non-resetting limit of at most USD 10 on the key in OpenRouter |
| `staged_unknown_cost_hold_limit_reached` | 40 attempts have unknown charges | Stop. Check OpenRouter Logs; decide with the team before any further spend |
| `staged_budget_exhausted` | Less than one worst-case attempt left under USD 9 | Stop. A larger cap needs a new explicit authorization |
| `staged_stage_requires_complete_smoke_on_current_inputs` | Smoke is incomplete, has a missing cell, or an input file changed since | Finish the smoke; if an input changed, restore it |
| `staged_pilot_floor_requires_model_change` | Fewer than 12 of 16 NUMERIC decisions were optimal | Protocol floor rule. Stop and decide; a model change needs a new authorization |
| `staged_freeze_tag_not_pushed_to_origin` | The freeze tag is not on the public remote | `git push origin <tag>` |
| `unaccounted_paid_run_history` | A paid run exists outside the four fixed directories | Remove the stray copy; never move real evidence |
| `account_http_error` | OpenRouter rejected the key check | Check the key in `.env` |

A gate stage (smoke, pilot, load-8 smoke) that ends with a missing first action or readback cannot support the freeze. The protocol does not say what to do then, and this code does not decide it: stop and record a team decision.

## What is different from the closed USD 1 smoke

| Topic | Closed smoke (`paid-smoke-usd1-200-v1`) | Staged (`paid-staged-usd9-v1`) |
|---|---|---|
| Cap and attempts | USD 1, 200 | USD 9, 3,000 |
| Stages | smoke only | smoke, pilot, load-8 smoke, main |
| Unknown charge | stop all dispatch | keep the full hold, continue; stop at 40 holds |
| Model, provider, request settings | DeepSeek V4.1 Flash via PrimeIntellect | identical |
| Per-attempt reservation | USD 0.0485 | identical |
| History | `runs/_paid_testing_session`, kept byte-for-byte | `runs/_paid_staged_session`, new and separate |

The earlier partial smoke (54 observations) stays in the repository as retained evidence. It is replayed against its own source commit by `scripts/verify_audit.py` and is never pooled with the new smoke.
