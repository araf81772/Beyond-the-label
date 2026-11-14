# Beyond the Label: research rules

## Authority and scope

Follow the user's current instructions. `research/protocol.md` is a byte-preserved copy of the supplied authoritative `final_design.txt`; `research/source_manifest.json` records its hash. Record conflicts and unresolved details in `research/decisions.md`. Do not silently substitute a prior study or change design numbers. The latest user instruction authorizes proceeding through milestones sequentially with free-only real execution conditional on a verified USD 0 hard key limit, and test → fix → test → commit → push cycles. Git delivery to the verified remote is authorized. The explicit NUMERIC amendment is in `research/amendments.md`.

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
- Never print, write, or commit credential values or authorization headers. Credentials come from environment variables; the user-authorized, Git-ignored project-root `.env` may populate known credential names without overriding existing process values. Never display or commit `.env`; report presence only. Loading credentials does not authorize paid calls.
- Retain every planned condition and case, including MASKED and final-outcome analyses; the current user instruction supersedes the source's time-pressure cut order.
- Routine milestone commits and pushes to the verified intended repository are authorized. No force-push, protected-branch merge, new public remote, visibility change, publication, or submission without the required approval.

## Milestone cycle

Exactly six milestones: audit; implementation; validation; smoke/pilot/freeze; main execution; analysis/report/reproduction. For each, complete work, run relevant checks, repair and retest, review diff/artifacts/secrets/claims, update `research/decisions.md` and `research/milestones.json`, then commit and push to a verified destination. Record failed/skipped checks and blocked pushes accurately; continue independent authorized work. Avoid empty commits.

Run `python scripts/verify_audit.py`, `python -m pytest -q`, and `git diff --check` for the current implementation. The audit script checks evidence consistency and source integrity; it does not substitute for experiment tests. Preserve historical M1 baseline facts when updating the live requirements/status records. Read-only provider account checks and public source research are authorized. Model inference requires the latest user condition: a verified USD 0 hard key limit, free-only routing and all protocol gates. Paid calls and purchases remain unauthorized.

Future model/budget choices in `configs/proposed_m4.yaml` are proposals only. Keep active run configurations disabled until execution prerequisites are satisfied. Budget/rate helpers require verified bounds and limits and are not themselves proof of live readiness or spending authorization; see `research/execution_readiness.md`.

The earlier HTTP 401 and offline-only instruction are historical. On the client date 15 November 2026, the user renewed authorization to check the key and proceed through milestones 4–6 with free calls only if the hard limit is USD 0. The latest authenticated check succeeded but reported `zero_hard_limit:false` with 50 free requests remaining. Therefore no inference is authorized by the unmet condition. `configs/free.yaml` retains both execution flags disabled. Do not mistake a zero local budget, remaining free quota or a detected key for the required provider-side zero hard limit. Local fixture tests remain synthetic and cannot satisfy real gates.
