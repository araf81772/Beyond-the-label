# Offline completion checkpoint

The user requested finishing independent work through milestone 6 while deferring smoke until a budget update. This checkpoint makes no inference calls or account rechecks. Paid calls remain unauthorized. The current durable ten-attempt ceiling and disabled execution flags are unchanged.

| Milestone | Current scope |
|---|---|
| 1 Audit | Complete; historical baseline preserved |
| 2 Implementation | Complete offline; world, oracle, mapping, tools and scoring tested |
| 3 Validation | Complete offline; live provider compatibility remains unobserved |
| 4 Smoke / pilot / freeze | Offline safeguards and rehearsal available; real gates and freeze pending |
| 5 Main execution | Harness and validation available; 704 planned cells unexecuted |
| 6 Analysis / report / reproduction | Analysis, evidence packaging and pre-results manuscript prepared; empirical results and final paper pending |

No overall milestone is advanced by a synthetic fixture, an empty planned-result table or a report draft. No execution freeze, main estimate, confidence interval or real performance claim exists. Historical account evidence authenticated but did not satisfy the required USD 0 hard limit. That evidence is not a current recheck.

## Reproduce independent work

Use the repository's documented Python dependencies and run from its root:

```powershell
$env:PYTHONPATH = 'src'
python -m pytest -q
python scripts/verify_audit.py
python -m pip check
git diff --check
python scripts/validate_offline.py --output evaluation/synthetic_main_load2_preresults
python scripts/rehearse_offline.py --output evaluation/synthetic_m4_preresults
python -m beyond_label.finalize --planned --output results/planned
python -m beyond_label.finalize --run evaluation/synthetic_main_load2_preresults --output evaluation/synthetic_report_bundle --allow-synthetic
python scripts/reproduce_offline.py --output research/checks/preresults_clean_clone.json
```

Use a new synthetic directory when source hashes change; preserve previous raw traces. The full test suite denies network connections and substitutes temporary credentials. Clean-clone reproduction uses the installed host environment without fetching dependencies; a fresh installation remains unverified without a compatible offline wheelhouse. Report creation and rendering are documented separately in `report/artifact.md` and the report manifest.

The finalizer refuses synthetic input unless explicitly requested, validates source evidence before output, and preserves original run files. Its planned mode emits null estimates rather than treating not-run cells as observed infrastructure errors. Empirical analysis requires 10,000 world bootstrap resamples and seed 314159. Audit status is reconciled against actual retained attempt events and verified freezes rather than a hardcoded zero-call assumption. Replay requires matching input hashes. If future retained runs span code/configuration versions, replay each in its recorded compatible source snapshot before aggregate validation; the current audit fails closed on incompatible historical inputs. It must not be bypassed by rewriting traces or deleting old attempts.

## Resume empirical work later

The next user update must settle the allowed budget and total inference-attempt allowance. The current limit is ten attempts across all stages, retries, re-prompts and continuations; it cannot complete the required 80 initial smoke cells. Increasing it requires explicit authorization and preserving any durable history. The paid-model USD 20 proposal is not authorization. A paid path, if later authorized, would need its own implementation and validation; the current live entry point rejects paid execution.

For the current free-only path, the same key must have its USD 0 hard limit verified, with fresh quota evidence. Confirm the pinned endpoint's availability and required settings without silent substitutions. Only then enable the authorized configuration and run smoke. Real wire support, usage/cost reconciliation and resume must pass before pilot.

The pilot keeps all eight worlds and all cases. At least 14/16 fully correct MAIN pairs selects load-8, otherwise load-2; NUMERIC below 12/16 requires a separately pinned model and complete repeat pilot. Load-8 requires its four-world smoke. Retain every attempt, cost and decision. No observed outcomes may be discarded to improve performance.

After complete real gate evidence, commit the final inputs and main manifest. `prepare_freeze` verifies them and returns a record referencing that commit; the record stays outside the input hash set to avoid a circular dependency. Create the named Git tag on the input commit, retain the timestamped record in a subsequent checkpoint, push both and verify their remote identities. `verify_freeze` must pass before the first main call. An ordinary offline-preparation commit is not an execution freeze.

Execute the frozen 64-world plan with seeded interleaving, fresh contexts and one sample per cell. Retain all five required artifacts. Resume completed evidence without resampling; record infrastructure missingness separately from invalid decisions. Material protocol changes after freeze need explicit approval, a deviation record, a new run ID and a new freeze.

Run offline finalization only on retained evidence. Populate the report's pending results with linked tables/figures, review interpretation thresholds and denominators, and complete the required human-review disclosure. Tonmoy and Araf are confirmed names; affiliations and individual contributions remain pending. No H1-H5 human review is recorded. Final formatting, citation review and clean-clone regeneration must be repeated against the actual empirical paper before submission. Submission/publication requires separate approval.
