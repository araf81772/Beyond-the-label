# Pre-freeze amendments and implementation conventions

## A1 — 14 November 2026: NUMERIC report facts

The user explicitly approved: “Include report facts alongside the losses as an explicit protocol amendment.” This resolves the Section 7 loss-only handoff's missing information for final dispositions. No execution freeze or model observation existed when approval was given.

NUMERIC retains archived report IDs, lot IDs and historical PASS/FAIL results, and target lot IDs with penalties, alongside exactly the three prescribed first-action expected losses. Scope metadata is omitted from this control's handoff; the supplied losses replace the need to infer scope. Fees and reliability instructions retain the shared system template. No hidden current states, draws, seeds, or additional oracle answers are supplied. The original `research/protocol.md` remains byte-for-byte unchanged.

This is an approved pre-freeze protocol amendment, not an empirical finding. It must be included in the eventual freeze and reported with the NUMERIC control.

## Offline execution boundary

The user requested sequential milestones with test → fix → test cycles, commits and pushes, and explicitly required offline research execution. Git transport to the already verified repository is the requested delivery exception. No provider calls, network package installation, online citation verification, real smoke/pilot, execution freeze, or main run is authorized by this instruction. Absent real observations must never be replaced with synthetic observations in empirical outputs.

## Deterministic world convention

Generator version `btl-worlds-v1` uses SHA-256-separated pseudorandom streams for identifiers, metadata order, and two independent per-lot uniform draws. Draws are held fixed across twins. Eight order/polarity strata repeat eight times across the 64 main seeds; the first sixteen cover each stratum once per high-stakes position. `lot_1` always means the first-displayed target. Research input files carry both targets and six potential distractors; load selects two or eight records at rendering without changing either target. World inputs contain research-only hidden draws and are not model-visible transcripts.
