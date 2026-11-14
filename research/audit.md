# Milestone 1 — repository audit and execution baseline

Audit date: 14 November 2026, Australia/Sydney. Scope: the user's final instruction, “Execute 1st milestone.” All six milestones remain represented; this checkpoint does not start implementation or real experiments.

## Intake evidence

The workspace `C:\Users\tonmo\OneDrive\Documents\ChatGPT\beyond-the-label` contained only `.git` when inspected, including hidden entries. `git status --porcelain=v1 -uall` and `git ls-files` were empty. The branch was unborn `master`; `git log -6 --oneline` failed because no commits exist. No Git remote or upstream was configured. `git fsck --full` found no corrupt objects. No working-tree changes existed to preserve. Ancestor `AGENTS.md` files from the drive root through the repository were checked; none was present.

The requested README, AGENTS, protocol, decisions, configurations, prompts, source, data, tests, evaluation, runs, results, and report files were all absent. No incomplete run or existing experimental output was found. This is an initialization audit, not a repair of an existing implementation. The source's Section 0 statement that repository/pipeline/tests “now match” the design is not true of this checkout.

The connected GitHub installed-repository search for `beyond-the-label` returned zero repositories. This does not establish that no remote exists elsewhere. An intended existing URL and branch were requested; none has yet been verified. No remote was guessed or created.

## Authoritative source

The complete supplied `C:\Users\tonmo\Downloads\final_design.txt` was read in bounded sections covering lines 1–581. The 27,751-byte original is archived without content changes as `research/protocol.md`; SHA-256 is `f732a0d815ae7f6f42e9eacb4e311b53ed8187abf9e3c48b79c476dfc202838b`. `.gitattributes` disables text normalization for this file. Its “frozen for build” wording is preserved but does not establish a later execution freeze.

An independent AI reviewer also read all 581 lines and checked the numeric design. No human oracle calculation, trace audit, citation review, or participation was observed. Source Section 17's citation status is an unverified historical assertion, not this audit's result. Citation retrieval and the official submission template are pending milestone 6; no citation claim is adopted as independently confirmed here.

## Runtime and baseline checks

`research/baseline.json` records tool/package versions, credential **presence only**, and exact check outcomes. Python 3.14.7 satisfies the source's Python 3.11+ requirement. Git 2.55.0.windows.5 and uv 0.12.5 are present. No project dependency specification or lock exists. Installed libraries must not be mistaken for a pinned or fully tested environment.

The baseline pytest invocation found no tests; no T1–T8 acceptance claim is made. The import check is separate from scientific validation. `gh` is unavailable on PATH; Git itself and the connected GitHub tools are available. LibreOffice/soffice and pandoc were not found on PATH; Microsoft Word availability was not assessed. Export capability remains to be established before the report milestone.

Reproduce the audit artifact checks with `python scripts/verify_audit.py` and `git diff --check`. Reproduce the test-discovery baseline with `python -m pytest -q`; until experiment tests exist, a no-tests result is expected and is not a passing suite. Setup for later milestones requires creating `pyproject.toml`, resolving a compatible pinned environment with `uv.lock`, and recording installation commands; none is represented as completed here.

## Requirements and analytic checks

`research/requirements.csv` maps design/user requirements to intended files, tests, status, and milestone. “Missing” means no implementation exists; “blocked” identifies required external inputs or unresolved specifications. Test filenames in that map are planned, not present.

For following both reports, expected loss is `(1-q1)*P1 + (1-q2)*P2`. Inspecting lot i with optimal continuation costs `fee + (1-qj)*Pj`. Against-report commits cost `qi*Pi` for that unchecked lot. Exact rational arithmetic agrees with every Section 4 entry:

| Condition / assignment | Commit | Inspect first named lot | Inspect other |
|---|---:|---:|---:|
| MAIN, lot_1 OOS | 50 | 30 | 60 |
| MAIN, lot_1 IN | 50 | 60 | 30 |
| HIGH-FEE, lot_1 OOS | 50 | 70 | 100 |
| HIGH-FEE, lot_1 IN | 50 | 100 | 70 |
| HIGH-STAKES, H OOS | 330 | 30 | 340 |
| HIGH-STAKES, H IN | 120 | 60 | 100 |
| MASKED, identity unknown | 50 | 45 | 45 |

These are analytic references checked by agents, not human-reviewed values, model observations, or a test of nonexistent `oracle.py`. MAIN reference-policy losses are oracle 30, always-commit 50, and random single check 45.

Main manifest requirements sum to 704 initial cells: MAIN 256, READBACK 256, HIGH-FEE 64, HIGH-STAKES 64, MASKED 32, NUMERIC 32. There are 448 decision cells and at most 448 continuations: 1,152 planned calls before retries/re-prompts. Pilot full matrix: 160 initial cells and at most 128 continuations, total 288. Smoke contains four worlds; its exact cell matrix is not specified. These counts have been checked arithmetically; no execution manifest has been built.

## Conflicts and open implementation details

1. **NUMERIC information sufficiency (Sections 4, 7):** literal replacement of the entire handoff with three first-action losses removes historical PASS/FAIL facts needed for informed final dispositions. The target choice is evaluable, but full optimal continuation needs missing facts. Clarification is required before implementing this renderer; no information was silently added.
2. **Twin-diff test scope (Sections 5, 7, 12):** scope-only byte differences apply to scope-bearing twins. NUMERIC deliberately exchanges expected-loss x/y values; MASKED has no paired twin cells. Document condition-specific test expectations explicitly.
3. **Leakage rule and NUMERIC (Sections 4, 7, 12):** NUMERIC deliberately displays its three expected losses. Restrict any exception to those prescribed values; hidden states, draws, and answer keys remain prohibited. Inspection state becomes visible only following a valid inspect on that lot.
4. **Source cut order versus user request:** Section 15 allows cutting S8 and MASKED under time pressure. The current user requires retaining all planned cases and final outcomes; follow the user, without changing the archived source.
5. **Public freeze versus publication permissions:** the source expects a public tag/repository. The user does not authorize creating a public remote, changing visibility, or publication/submission. Verify the existing destination; do not infer permission from the document.
6. **Human checks:** Section 10 requests two humans. The user allows proceeding with honest disclosure when unavailable. No H1–H5 participation is assigned or completed. Automated checks must be labelled separately.
7. **Freeze details still to fix:** bootstrap count is 10,000 but its seed and interval method are not specified; schedule/interleaving and human-audit seeds, primary invalid/missing denominator rules, continuation failure handling, refusal/no-tool precedence, and smoke cell coverage need explicit pre-freeze definitions. Routine implementation choices can be recorded without altering design thresholds. Resolve material ambiguities before dependent work.
8. **Schedule text:** Section 15 lists main “then controls,” while Sections 5 and the user require seeded interleaving. The execution manifest must use seeded interleaving; the wall-clock schedule is not authority to change sampling.

## Paid-call prerequisites and blockers

The routing service is OpenRouter (Sections 8, 13–14). No model ID, named upstream provider, reasoning setting, numeric output-token limit, actual supported temperature/default, concurrency, rate limits, or pricing evidence exists. Fixed settings required by the design are: no fallback; temperature 0 where supported, otherwise a recorded fixed default; parallel tool calls off; model-selected tools; one no-tool re-prompt exactly `Respond with exactly one tool call.`; infrastructure errors retried up to three times with identical requests (initial attempt plus up to three retries), separate accounting, and no resampling successful/invalid model decisions.

No `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `ADAPTION_API_KEY` was present in the checked process environment. No `.env` existed. This does not claim that no credentials exist in any other credential store. No credential values, headers, account balances, or private configuration were read into artifacts.

The “under US$20” statement is explicitly an estimate, not a spending authorization. A cap and currency must be supplied before paid calls. The source's proposed key limit of three times the pilot projection must remain inside that authorization; exceeding it requires approval. Adaption credits neither fund this design by default nor authorize expenditure. No paid calls or provider charges were incurred by this audit; no provider billing statement was queried.

Local milestone checks can finish. Push is blocked until the intended existing remote and branch are known. Later paid execution additionally requires budget, credential setup, pinned provider/model/settings, provider-limit verification, passing T1–T8, and the applicable smoke/pilot/freeze gates. NUMERIC clarification blocks only its dependent implementation, not independent offline components.
