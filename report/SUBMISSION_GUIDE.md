# Submission guide

Written 15 November 2026 (AEDT) by Claude (AI) after checking the live sprint page that day. This is a checklist and a list of facts. It is **not** report text: the official template strongly encourages the team to write the final report themselves, and a judge may decline to score a report they cannot follow.

Deadline: **Monday 16 November 2026, 22:59 AEDT** (Sunday 23:59 AoE, Monday 11:59 UTC). The design's own target is Monday 20:00 AEDT. Resubmitting with the same title replaces the earlier submission.

## 1. What the judges score

Each dimension is scored 1 to 5, the same for every track.

| Dimension | What a 3 needs | What a 4 needs |
|---|---|---|
| Impact and innovation | Clear problem, reasonable approach, some novelty | Important problem, original approach, something others can build on. Judges check it is new and not a replication |
| Execution quality | Technically solid for the time, interpretable results, limitations acknowledged | Thorough method, convincing validation, results clearly support the conclusions |
| Presentation and clarity | Problem, method, findings and limitations all present and understandable | Easy to follow, well structured, right level of detail |

Without results, Execution cannot rise above about 2. The single highest-value action is to run the pilot and main stages ([runbook](../research/staged_execution.md)).

## 2. Hard requirements (checked against the live page)

- [ ] PDF made from the official template linked on the Guidelines tab (`official_template.docx` here is an export of it)
- [ ] At most 8 pages, not counting references and appendices. The template suggests about 4
- [ ] Title, and an abstract of 150 to 250 words written last
- [ ] Author names and affiliations
- [ ] Appendix titled exactly **Limitations and Dual-Use / Ethical Considerations**, covering: what the result does and does not establish; how the tool or findings could be used to manipulate people instead of informing them; how personal data was handled (none is used)
- [ ] LLM Usage Statement that is accurate (section 6 below)
- [ ] Work done before the sprint identified in the report and the README
- [ ] All template guidance text and the info box deleted
- [ ] Every number and reference checked by a person. Made-up results or references can disqualify
- [ ] Submitted through the form on the sprint page; confirmation email received with the right PDF

## 3. Statements in the pre-results draft that are no longer true

`manuscript.md` and `pre_results.pdf` are a dated pre-results artifact. Do not submit them. If their text is reused, these must change:

| Where | Draft says | Fact now |
|---|---|---|
| Header, section 4, LLM statement | No real smoke, pilot or main observation exists | 54 real smoke observations exist (93 accepted calls, USD 0.0125 known cost) in `runs/paid_smoke_gpt41mini_20261115/segments/deepseek_primeintellect_v3`. More will exist after the staged runs |
| Section 3.5 | Candidate model `nvidia/nemotron-3.5-super-vl:free`, route `nvidia` | Never used. The model is `deepseek/deepseek-v4.1-flash-1017` through OpenRouter route `primeintellect` (provider PrimeIntellect), temperature 0, reasoning effort none, 512 output tokens, automatic tool choice, parallel tool calls off, no fallback |
| Authors | Tonmoy; Araf; affiliations pending | Full names and real affiliations, plus the template's "With Apart Research" line and sprint footnote |
| Reference 2 | `Bissyand'e, Tegawend'e F.` | `Bissyandé, Tegawendé F.` |
| LLM statement | Names Codex only | Also name Claude (repository review and staged execution path) |
| Folder name | — | The run folder is called `paid_smoke_gpt41mini_…` but holds DeepSeek data: the first attempt used GPT-4.1 mini, returned HTTP 404 and no reply, and the team switched model before any observation |

## 4. Worth saying under "what was tried and did not work"

The template asks for this in Methods. All of it is in the repository:

- One GPT-4.1 mini attempt returned HTTP 404 with no model reply. Public metadata did not confirm the parallel-tool control for that endpoint, so the model was changed before any observation.
- The first DeepSeek reply was rejected because the router reported the dated endpoint name (`…-20261017`) for the requested model (`…-1017`). The cell is kept as missing and was never re-asked.
- A cost guard stopped the first smoke after one timeout with no billing receipt, with 25 cells untouched.
- Three first replies hit the 512-token output limit without a tool call; each received the single fixed re-prompt.

## 5. Where each report element comes from after the runs

Nothing below exists until the stages are executed. Do not write a number that is not in one of these files.

| Report element | Source | Command |
|---|---|---|
| Model, settings, freeze tag and commit | `research/execution_freeze.json`, `runs/staged_main/manifest.json` | `python -m beyond_label.staged status` |
| Pilot counts and the load decision | pilot summary | `python -m beyond_label.pilot runs/staged_pilot_load2` |
| Primary effect D, 95% interval, sign test, layout interaction | `results/staged_main/analysis/` | `python -m beyond_label.finalize --run runs/staged_main --output results/staged_main` |
| Figure 1 (allocation against the oracle), pair-category table, one matched trace | `results/staged_main/analysis/figures/` and tables | same command |
| Control results, regret, readback accuracy, missingness | `results/staged_main/analysis/` | same command |
| Calls, retries, re-prompts, cost | `results/staged_main/execution_summary.json` | same command |
| Every number's file and command (protocol H4) | `results/staged_main/analysis/claim_evidence.csv` | same command |

Smoke results are a pipeline check and are **not** reported as findings. Pilot results chose the load and must be reported as such, separately from main. The protocol's three interpretation rules (section 9) decide the wording of the conclusion; anything outside them is "inconclusive".

**If the main run does not finish in time:** report what exists, labelled for what it is. A complete pilot is 8 worlds chosen before any data and can be described as exploratory, with its exact denominators, and with a plain statement that the pre-registered main sample was not collected. That is a deviation from the plan and should be called one. Unfinished work with honest limits is explicitly welcome under the sprint rules.

## 6. LLM Usage Statement: facts to state

- OpenAI Codex wrote most of the code, tests, engineering records and the pre-results draft, directed by the team.
- Claude (Anthropic) reviewed the repository against the sprint rules and implemented the staged execution path, its tests and this guide.
- The model under study is DeepSeek V4.1 Flash. No LLM judges or scores any decision; scoring is deterministic code.
- State which parts of the final report text the team wrote, and confirm that the team checked every claim and number.

## 7. Human checks the protocol asks for (section 10)

The current user confirmed that they and Araf completed H1, H2/P2 and H5. These are **user-attested completions**, recorded in [human_verification.json](../research/human_verification.json); no worksheets, initials or exact completion times were supplied. H1 was completed after the pilot and must remain a disclosed timing deviation. AI checks are recorded separately. H3/H4 remain pending; D4 still needs their explicit responsibility record.

- [x] H1 (user-attested; late): each person independently hand-computes protocol section 4 and all eight pilot worlds and compares with the oracle. Retain the timing deviation
- [x] H2/P2 (user-attested): both read every pilot trace against the parser's categories
- [ ] H3: each audits 30 main traces drawn with seed 161803, plus every invalid and refused trace; record in `evaluation/trace_audit.csv`
- [ ] H4: every number in the paper has a row in `claim_evidence.csv`
- [x] H5 (user-attested by the current user for themselves and Araf): the three references and associated claims in the current manuscript were checked. Any new or changed citation requires review

## 8. Related work

The draft cites three 2026 arXiv papers. Claude opened all three on 15 November and the titles, authors and summaries match (AI check, not H5). Two gaps a judge is likely to notice:

Later Codex AI review checked the relevant methods/results as well as metadata. The current qualitative attributions are supported. Fan et al. v2 section 4.4 and PDF page 7 contain both 76.2% and 281/376 (74.7%), with no clear reconciliation. Do not quote an exact recognition percentage as verified; the current manuscript avoids it. The historical source records remain unchanged. Human H5 completion is separately user-attested above.

1. **Novelty against Nakayashiki (2026).** That paper already tests budgeted verification of stale provenance on sixteen models. The report needs one clear paragraph on what this design isolates that theirs does not: the labels are unchanged, only the report-to-scope binding is swapped between fixed reports, and the best action is known exactly.
2. **The sprint's own reading list.** None of it is cited. Items close to this work: Ren et al., MASK (arXiv:2503.03750); Fanous et al., SycEval (arXiv:2502.08177); Kalai et al., "Why Language Models Hallucinate" (arXiv:2509.04664); the C2PA specification v2.4; Cotton-Barratt and Finnveden, "AI for AI for Epistemics" (Forethought, 2026); Finnveden, "What's Important in 'AI for Epistemics'?" (2024). Cite only what a team member has opened and read.

Track 2's guiding question that this project answers directly: "When an AI system uses a reliability or provenance tool, do its behaviour and accuracy actually improve?"
