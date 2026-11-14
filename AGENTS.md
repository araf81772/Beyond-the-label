# Beyond the Label: research rules

## Authority and scope

Follow the user's current instructions. `research/protocol.md` is a byte-preserved copy of the supplied authoritative `final_design.txt`; `research/source_manifest.json` records its hash. Record conflicts and unresolved details in `research/decisions.md`. Do not silently substitute a prior study or change design numbers. The latest request for this checkpoint is milestone 1 only.

The design's “frozen for build” header is not an execution freeze. A validated smoke/pilot, freeze commit, tag, and hashes are still required before any main call. After an execution freeze, material changes require explicit approval, a deviation record, a new run ID, and a new freeze.

## Roles and evidence

Codex performs engineering, execution, and machine checks. Independent agent review must be labelled AI review. Claude has no assigned or completed role in this checkout; use it only if subsequently authorized. Neither agent substitutes for the human checks in design Section 10. Record real participants and never invent initials, participation, results, costs, citations, or completed checks.

## Execution

- Preserve existing user changes. Review intended files before each milestone commit.
- Keep smoke, pilot, main, synthetic test data, analytic oracle references, and missing observations distinguishable.
- Keep hidden states, random draws, answer keys, and research-only oracle values out of model-visible material. NUMERIC intentionally supplies only its specified first-action losses; document this narrow exception.
- Use one pinned model and named provider, no fallback, fresh cell contexts, one sample per cell, and exact recorded settings.
- Infrastructure retries are distinct from model samples. Never retry invalid model decisions. Freeze the single no-tool re-prompt verbatim.
- Do not make paid calls until spending authorization, credentials, provider settings, limits, and required offline tests are established. Credits and price estimates are not authorization.
- Never print, write, or commit credential values or authorization headers. Credentials come from environment variables; report presence only.
- Retain every planned condition and case, including MASKED and final-outcome analyses; the current user instruction supersedes the source's time-pressure cut order.
- Routine milestone commits and pushes to the verified intended repository are authorized. No force-push, protected-branch merge, new public remote, visibility change, publication, or submission without the required approval.

## Milestone cycle

Exactly six milestones: audit; implementation; validation; smoke/pilot/freeze; main execution; analysis/report/reproduction. For each, complete work, run relevant checks, repair and retest, review diff/artifacts/secrets/claims, update `research/decisions.md` and `research/milestones.json`, then commit and push to a verified destination. Record failed/skipped checks and blocked pushes accurately; continue independent authorized work. Avoid empty commits.

For the audit checkpoint run `python scripts/verify_audit.py` and `git diff --check`. These are audit checks only; T1–T8 are absent, not passed. Future implementation must supply the mapped tests in `research/requirements.csv` and a pinned dependency environment.
