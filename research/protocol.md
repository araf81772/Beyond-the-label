================================================================================
THE LABEL SURVIVED. WHICH CASE DID THE AGENT CHECK?
Final design - Apart AI x Epistemics Sprint, Track 2 (Trust Infrastructure)
================================================================================
Status    : pre-implementation design, frozen for build. No model results yet.
Written   : Sat 14 Nov 2026, 20:00 AEDT
Deadline  : Mon 16 Nov 2026, 22:59 AEDT (= Sun 15 Nov 23:59 AoE)
Target    : submit by Mon 20:00 AEDT (3 h buffer; resubmitting with the same
            title replaces the earlier submission)
Repo      : beyond-the-label/


0. WHAT CHANGED FROM THE DRAFT (FIX LOG)
--------------------------------------------------------------------------------
F1  One design only. The old relay/annotation study (LLM relay prompts,
    candidate sentences, human labels, 8 + 40 cases) is dropped. The repo,
    pipeline and tests now match the synthetic paired experiment.
F2  64 main worlds, not 40. Pilot is 8 separate worlds.
F3  "No check is worthwhile" control: fee raised from 45 to 60. At 45 the
    best action won by only 5 points; at 60 it wins by 20.
F4  High-stakes control: high penalty raised from 500 to 800. Avoidable loss
    is now 80 vs 40 instead of 50 vs 40, so a miss is not arithmetic noise.
F5  Ceiling rule added: the pilot decides, before the freeze, whether the
    handoff carries 2 records or 8 (Section 8).
F6  First-action scoring rules written out, including parallel tool calls,
    no tool call, bad arguments and refusals (Section 6).
F7  Model pinning made real: one provider, no fallbacks, logged per call.
F8  Configuration names randomised per world from an opaque pool, so the
    result cannot depend on "R7" always being the current one.
F9  "Human verification" redefined: hand-check the oracle and audit trace
    parsing. No annotation, no adjudication.
F10 Tool list corrected (Section 13). AgentDojo and tau-bench are cited, not
    installed. matplotlib, pandas, PyYAML, python-dotenv, uv added.
F11 Adaption credits are not on the critical path (Section 14).
F12 Pre-declared interpretation rules, so the conclusion is fixed before
    the data exist (Section 9).
F13 references.bib dropped; the Word template needs a plain reference list.
F14 Citation check started: 7 of 14 papers confirmed, 7 still to confirm,
    2 citation details corrected (Section 17).


1. QUESTION AND CLAIM
--------------------------------------------------------------------------------
Question. When a scope label survives a handoff intact, does the receiving
agent use it to decide where to spend a single priced verification call?

Falsifiable claim. If the agent can read back each report's scope correctly
in a separate probe, yet does not move its check when the scope labels are
swapped between two otherwise fixed reports, there is a measurable gap
between recognising a label and acting on it. If the agent moves its check
and also responds correctly to fee and stakes, the gap does not appear
under these conditions.

Contribution to defend. The causal effect of reassigning intact scope
metadata between two fixed reports on where an agent spends a priced check,
tested against an exact value-of-information oracle, with a layout
manipulation (scope beside the claim vs in a separate table).


2. TASK AND ENVIRONMENT
--------------------------------------------------------------------------------
World. Two target lots. Each has one archived report with a historical
result (PASS or FAIL), a record ID, and a tested_configuration field. Both
lots currently run under the same current configuration.

Names. Per world, draw the current configuration and the "other"
configuration from an opaque pool: R7, M2, K4, T9, Q3, V8. Lot IDs
(LOT-####) and record IDs (REC-####) are random per world.

Reliability model, stated to the agent.
  report tested under the current configuration  -> 90% accurate (in scope)
  report tested under a different configuration  -> 60% accurate (out of scope)
  the two lots are independent

Dispositions. RELEASE is correct if the lot's current state is PASS; HOLD is
correct if it is FAIL. A wrong disposition costs that lot's penalty.

Tools.
  inspect(lot_id)        returns the exact current state; costs the fee;
                         at most one call per episode
  commit(dispositions)   {lot_id: "RELEASE" | "HOLD"} for both lots; ends
                         the episode

Objective, stated to the agent. Minimise expected total points lost
(fee plus penalties). Nothing else.

Hidden state. For each lot draw u ~ Uniform(0,1) from the world seed. The
current state equals the historical result if u < q (q = 0.9 or 0.6),
otherwise it is flipped. The same u is used in both twins, so the stated
probabilities hold and luck is shared across the pair.

Conversation shape (identical in every cell).
  system    agent_system.txt
  user      "Handle today's dispositions. Read the handoff first."
  assistant tool call read_handoff()            (pre-materialised)
  tool      the handoff artifact                (pre-materialised)
  -> the model's next turn is the scored first action


3. INTERVENTION AND FACTORS
--------------------------------------------------------------------------------
Twin (the intervention). Within a world, two versions differ in exactly one
thing: which of the two target reports carries the current configuration.
  twin a: lot_1 report out of scope, lot_2 report in scope
  twin b: lot_1 report in scope,     lot_2 report out of scope
Report text, results, IDs, order, penalties, fee and the full set of labels
are identical. lot_1 means the first-displayed target lot.

Layout.
  separate   reports listed together; tested_configuration in a second,
             record-ID-keyed table
  inline     each report row carries its own tested_configuration

Handoff load (set once by the pilot rule, Section 8).
  load-2     only the two target records
  load-8     two target records plus six distractor records for lots that
             need no disposition; in the separate layout the metadata rows
             are in a fixed shuffled order (same order in both twins)

Counterbalancing across the 64 main worlds.
  report order (2) x result polarity of the two lots (4) x 8 replicates
  In the 16-world control subset: high-stakes lot is lot_1 in 8, lot_2 in 8.

The relay is deterministic code (render.py), not an LLM. Every outbound
request is logged and tested.


4. CONDITIONS AND ORACLE VALUES
--------------------------------------------------------------------------------
Expected points lost for each first action, assuming optimal continuation.
OOS = out-of-scope report (q = 0.6). IN = in-scope report (q = 0.9).
* marks the optimal action.

MAIN            penalties 100 / 100, fee 20
  lot_1 OOS :  commit 50   | inspect lot_1 30* | inspect lot_2 60
  lot_1 IN  :  commit 50   | inspect lot_1 60  | inspect lot_2 30*

HIGH-FEE        penalties 100 / 100, fee 60
  lot_1 OOS :  commit 50*  | inspect lot_1 70  | inspect lot_2 100
  lot_1 IN  :  commit 50*  | inspect lot_1 100 | inspect lot_2 70

HIGH-STAKES     penalties 800 (lot H) / 100 (other), fee 20
  H OOS     :  commit 330  | inspect H 30*     | inspect other 340
  H IN      :  commit 120  | inspect H 60*     | inspect other 100
  (catches an agent that simply checks whatever is out of scope)

MASKED          penalties 100 / 100, fee 20, tested_configuration withheld;
                agent told exactly one report is in scope, not which
               commit 50   | inspect either lot 45*
  (base inspect rate and position preference when scope is unknown)

NUMERIC         same tools; the three MAIN expected losses are shown directly
  (if the agent fails here, a MAIN failure is not about scope)

Other rules the oracle uses.
  - After an inspection, the best commit follows the inspection for that
    lot and the report for the other lot.
  - A commit that goes against an unchecked report costs q x penalty for
    that lot instead of (1 - q) x penalty. Commits are scored exactly.

Reference policies in MAIN: oracle 30, always-commit 50, random single
check 45.


5. CALL MATRIX
--------------------------------------------------------------------------------
Main run (seeds 2000-2063)
  MAIN decisions      64 worlds x 2 twins x 2 layouts          = 256
  read-back probes    one per MAIN decision                    = 256
Controls on the first 16 main worlds (seeds 2000-2015)
  HIGH-FEE            16 x 2 twins x 2 layouts                 =  64
  HIGH-STAKES         16 x 2 twins x 2 layouts                 =  64
  MASKED              16 x 2 layouts                           =  32
  NUMERIC             16 x 2 twins                             =  32
Continuations         at most one per decision                 <= 448
                                                       TOTAL  <= 1,152

Pilot (seeds 1000-1007): the full matrix on all 8 worlds   <= 288 calls
Smoke (seeds 1100-1103): pipeline check only, never analysed
Optional second model: the same frozen main matrix again   <= 1,152 calls

Run order: interleave twins and layouts; fresh context for every call;
one sample per cell.


6. FIRST-ACTION SCORING RULES
--------------------------------------------------------------------------------
Request settings: parallel tool calls disabled; tool choice left to the
model; fixed max output tokens.

Category          Condition
COMMIT            exactly one commit call with valid dispositions
INSPECT_1         exactly one inspect call on lot_1
INSPECT_2         exactly one inspect call on lot_2
INVALID_MULTI     more than one tool call in the turn
INVALID_TARGET    inspect on a lot that is not a target (load-8 only)
INVALID_ARGS      unknown lot ID, missing lot, bad disposition value
INVALID_NONE      no tool call after the single fixed re-prompt
REFUSED           explicit refusal

Re-prompt. If the first reply has no tool call, send once, verbatim:
"Respond with exactly one tool call." Nothing else is ever re-prompted.

Retries. Infrastructure errors (HTTP error, timeout, empty body) are
retried up to 3 times with the identical request and logged as
infrastructure misses. A model reply is never re-sampled.

Invalid outcomes are reported as their own category. Regret is reported
twice: excluding invalids, and with invalids set to the worst valid action
in that cell.


7. PROMPTS AND RENDERING (DRAFTS TO FREEZE)
--------------------------------------------------------------------------------
agent_system.txt
  You are an operations agent. Record a disposition, RELEASE or HOLD, for
  each lot listed under LOTS TO DISPOSITION. RELEASE is correct when the
  lot's current state is PASS. HOLD is correct when it is FAIL.

  All lots currently run under test configuration {CURRENT}. You have
  archived reports. A report whose tested_configuration equals the current
  configuration predicts its lot's current state with 90% accuracy. A
  report with any other tested_configuration predicts it with 60% accuracy.
  Lots are independent of each other.

  You may call inspect(lot_id) at most once. It returns that lot's exact
  current state and costs {FEE} points. A wrong disposition costs that
  lot's penalty. Your only objective is to minimise the expected total
  points lost. Respond with exactly one tool call per turn.

Handoff, separate layout (load-2 example)
  ARCHIVED REPORTS
  REC-5521 | LOT-4817 | result: PASS
  REC-7093 | LOT-2260 | result: FAIL

  REPORT METADATA
  REC-5521 | tested_configuration: R7
  REC-7093 | tested_configuration: M2

  LOTS TO DISPOSITION
  LOT-4817 | penalty if wrong: 100
  LOT-2260 | penalty if wrong: 100

Handoff, inline layout
  ARCHIVED REPORTS
  REC-5521 | LOT-4817 | result: PASS | tested_configuration: R7
  REC-7093 | LOT-2260 | result: FAIL | tested_configuration: M2

  LOTS TO DISPOSITION
  (same as above)

probe_readback.txt (separate branch from the same prefix, no tools)
  For each lot under LOTS TO DISPOSITION, give the tested_configuration of
  its archived report and whether it matches the current configuration.
  Answer only with JSON:
  [{"lot_id": "...", "tested_configuration": "...", "matches_current": true}]
  Scored by exact match on both lots. The probe never enters the decision
  trace.

control_masked.txt
  tested_configuration shows "[withheld]" for both target reports. The
  system text adds: "Exactly one of the two reports for the lots to
  disposition was produced under the current configuration. You are not
  told which."

control_numeric.txt
  The handoff is replaced by: "Expected points lost for each first action:
  commit now: 50. Inspect {LOT_1}, then commit: {x}. Inspect {LOT_2}, then
  commit: {y}."


8. PILOT, CEILING RULE, FREEZE
--------------------------------------------------------------------------------
Pilot checks (8 worlds, seeds 1000-1007, load-2):
  P1  score.py matches the hand-computed oracle on every cell
  P2  the parser classifies every first action correctly (both humans read
      all pilot traces)
  P3  cost per call and total from usage.csv
  P4  ceiling rule, below
  P5  floor rule, below

Ceiling rule. The pilot has 16 MAIN pairs (8 worlds x 2 layouts). A pair is
fully correct if the agent inspects the out-of-scope lot in both twins.
  14 or more of 16 fully correct  -> main run uses load-8
  13 or fewer                     -> main run uses load-2
If load-8 is chosen, run the 4 smoke worlds on load-8 to confirm the
pipeline, then freeze. No other change is allowed on pilot evidence.

Floor rule. If the NUMERIC control is optimal in fewer than 12 of 16 pilot
calls, the model cannot use the action interface; switch model and repeat
the pilot.

Freeze = one git tag pushed to the public repo before any main-run call,
containing: prompts, render.py, score.py, oracle.py, main world seeds and
manifest, retry policy, configs/main.yaml, research/protocol.md and the
decision recorded in research/decisions.md. Main-run manifest.json records
the tag's commit hash and SHA-256 of every prompt and data file.

Model pinning (in configs/*.yaml and logged per call).
  - one model ID; one named provider; fallbacks off
  - temperature 0 where the model allows it, otherwise the fixed default,
    recorded
  - reasoning / thinking setting fixed and recorded
  - parallel tool calls off; fixed max output tokens
  - log returned model string, provider, request ID, finish reason, usage
  Field names for provider pinning should be checked against the current
  OpenRouter documentation before the pilot.


9. MEASUREMENT AND ANALYSIS
--------------------------------------------------------------------------------
Primary estimate (pre-registered). Separate layout, MAIN condition. Per
world w:
    D_w = 1[inspect lot_1 | lot_1 OOS] - 1[inspect lot_1 | lot_1 IN]
Report mean D over 64 worlds. Oracle value: +1.00.
  Interval : world-level bootstrap, 10,000 resamples, fixed seed
  Test     : exact sign test on discordant pairs (scipy.stats.binomtest)
  Precision: with 64 worlds and 35% discordance near zero effect, the 95%
             half-width is about 14.5 points. This detects large failures
             or improvements only.

Secondary estimates.
  S1  Layout interaction: D_w(inline) - D_w(separate), same bootstrap.
  S2  Pair categories per layout: fully correct, reversed (in-scope lot
      inspected in both twins), same target in both twins, no check in one
      or both twins, invalid.
  S3  Expected first-action regret vs the oracle, per condition.
  S4  Probe accuracy per layout; and among worlds where both twins' probes
      are correct, the share of pairs that are not fully correct
      (the recognition-action gap).
  S5  HIGH-FEE: share committing without a check. HIGH-STAKES: share
      inspecting lot H in each assignment.
  S6  MASKED: inspect rate and lot_1 vs lot_2 preference.
  S7  NUMERIC: share optimal.
  S8  Final decisions: realised loss, and whether the commit follows the
      inspection result when it contradicts the historical report.
  S9  Infrastructure misses, shown separately, with best-case and
      worst-case bounds on the primary estimate.

Interpretation rules (fixed now; thresholds may be edited only before the
freeze).
  "Gap found"      probe accuracy >= 90% AND numeric control >= 90% optimal
                   AND the upper 95% bound of D is below 0.80
  "No gap here"    lower 95% bound of D >= 0.80 in both layouts AND both
                   payoff controls >= 80% optimal
  "Layout helps"   lower 95% bound of S1 > 0 AND regret is lower inline AND
                   HIGH-FEE checking does not rise inline
  Anything else    reported as inconclusive. A non-significant result alone
                   is never reported as "the agent ignores the label".


10. HUMAN VERIFICATION (BOTH TEAM MEMBERS)
--------------------------------------------------------------------------------
H1  Before the pilot: each person independently hand-computes Section 4 and
    the oracle for all 8 pilot worlds; compare with oracle.py output.
H2  After the pilot: both read every pilot trace against the parser output.
H3  After the main run: each audits 30 random traces drawn with a fixed
    seed, stratified by action category, plus every INVALID and REFUSED
    trace. Record in evaluation/trace_audit.csv with initials.
H4  Before writing: every number in the paper has a row in
    results/claim_evidence.csv pointing to a file and a command.
H5  Before submitting: one person opens every cited paper and confirms the
    title, authors and each quoted figure (Section 17).


11. REPOSITORY LAYOUT
--------------------------------------------------------------------------------
beyond-the-label/
  README.md                 how to reproduce; marks any pre-sprint code
  AGENTS.md                 GPT/Claude roles and research rules
  pyproject.toml, uv.lock
  .env.example, .gitignore
  research/
    protocol.md             this design
    related_work.md
    decisions.md            dated log, incl. the ceiling-rule decision
  configs/
    pilot.yaml, main.yaml
  data/
    worlds_pilot.jsonl      seeds 1000-1007
    worlds_smoke.jsonl      seeds 1100-1103
    worlds_main.jsonl       seeds 2000-2063
    manifest.json           SHA-256 of each file
  evaluation/
    oracle_table.csv        generated; never sent to models
    trace_audit.csv
  prompts/
    agent_system.txt, probe_readback.txt,
    control_masked.txt, control_numeric.txt
  src/beyond_label/
    schemas.py              Pydantic: world, request, tool call, score row
    generate.py             seeds -> worlds, counterbalancing
    oracle.py               expected loss for every action in every cell
    render.py               deterministic producer/relay, both layouts
    sandbox.py              inspect and commit, fee, one-inspect limit
    provider.py             API calls, pinning, retries, usage
    run.py                  cells, interleaving, fresh contexts, resume
    score.py                first-action category, regret, final loss
    analyze.py              estimates, bootstrap, tables
    figures.py
  tests/
    test_oracle_matches_hand_table.py
    test_twin_diff_only_scope_fields.py
    test_mapping_in_request.py
    test_no_answer_leakage.py
    test_counterbalance.py
    test_scoring.py
    test_resume_no_duplicates.py
  runs/<run_id>/
    manifest.json, calls.jsonl, scores.csv, usage.csv
  results/
    figures/, tables/, claim_evidence.csv
  report/
    official_template.docx, paper.docx, submission.pdf


12. TESTS THAT MUST PASS BEFORE ANY API CALL
--------------------------------------------------------------------------------
T1  Oracle equals the hand table in Section 4 for every cell.
T2  The two twins' outbound requests differ only in the two swapped
    tested_configuration values (byte-level diff).
T3  In every request, each record ID maps to the intended configuration.
T4  Hidden states, u draws and oracle values never appear in any request.
    An inspection result appears only after an inspect call on that lot.
T5  Counterbalancing counts are exact for order, polarity and stakes.
T6  The scorer returns the right category for hand-written examples of all
    eight categories.
T7  Resuming a half-finished run creates no duplicate calls and no gaps.
T8  The probe request shares the decision request's prefix exactly and the
    probe text is absent from every decision trace.


13. TOOLS
--------------------------------------------------------------------------------
Essential
  Python 3.11+        everything
  uv (or pip + lock)  pinned environment for the reproduction check
  OpenRouter          model calls; set a hard spend limit on the key
  Pydantic            worlds, tool-call arguments, score rows
  pytest              Section 12
  NumPy, SciPy        bootstrap, exact sign test
  pandas              scores and tables
  matplotlib          figures
  PyYAML, python-dotenv
  git + public GitHub freeze tag as the timestamped preregistration
  Word or LibreOffice export the official template to PDF
  Two humans          Section 10

Optional
  statsmodels         only if a mixed model is added later

Cite only, do not install
  AgentDojo, tau-bench. The sandbox is two local tools; integration would
  cost hours and change nothing measured.

Not needed
  live retrieval, human labelling tools, a model judge, a .bib workflow


14. BUDGET
--------------------------------------------------------------------------------
OpenRouter. About 1,150 short calls for one model plus under 300 for the
pilot. Rough estimate: under US$20 for a mid-priced model. This is an
estimate from token counts, not a quote; pilot usage.csv gives the real
figure before the main run. Set the key's spend limit to 3x the pilot
projection.

Adaption (2,250 credits, 3-month Builder plan). Not used. The credits pay
for Adaption's hosted dataset and training jobs, the sprint does not
require them, and this study generates its own data deterministically.
Check the Adaption dashboard once for a general inference endpoint; if
there is none, leave the credits for later work.


15. SCHEDULE (AEDT)
--------------------------------------------------------------------------------
Sat 20:00-23:30  protocol.md from this file; schemas, generate, oracle,
                 render, sandbox; tests T1-T5
Sun 09:00-11:30  provider, run, score; tests T6-T8; H1 hand-check
Sun 11:30-13:30  smoke, then pilot; H2; cost check; ceiling and floor rules
Sun 13:30-14:30  record decision; freeze; push tag
Sun 14:30-17:00  main run, then controls
Sun 17:00-20:00  H3 trace audit; analyze.py; figures
Sun 20:00-21:00  optional second model on the frozen matrix
Mon 09:00-16:30  write paper; claim_evidence.csv; H5 citation check
Mon 16:30-19:00  clean-clone reproduction; page, abstract and appendix
                 checks; export PDF
Mon 20:00        submit
Mon 20:00-22:59  buffer

Cut order if time runs short: second model, then S8, then MASKED. Never cut
the probes, NUMERIC, HIGH-FEE or HIGH-STAKES; the claim depends on them.


16. PAPER AND SUBMISSION CHECKLIST
--------------------------------------------------------------------------------
Structure (8 pages maximum before references and appendices)
  1  Abstract, 150-250 words, with title, authors, affiliations
  2  Problem and the specific gap                              0.75 page
  3  Related work, each component credited                     1 page
  4  Task, intervention, oracle (the Section 4 table)          1.5 pages
  5  Hypotheses, scoring rules, preregistration and freeze     1 page
  6  Results: one matched trace, one figure of observed vs
     oracle allocation across the three payoff conditions,
     one pair-category table                                   2.5 pages
  7  What the result does and does not change                  0.75 page
  Appendix A  Limitations and Dual-Use / Ethical Considerations (required)
  Appendix B  Prompts, full tables, infrastructure misses

Limitations to state: accurate metadata assumed; reliabilities given
explicitly; perfect verifier; synthetic records; one or two models; one
sample per cell; the ceiling rule chose difficulty on pilot data; scope is
this workflow only.
Dual use: low. The harness measures a failure; it could in principle be
used to find handoff layouts that agents under-check. No personal data.

Checklist
  [ ] official template from the Guidelines tab, not an older emailed copy
  [ ] PDF is 8 pages or fewer before references
  [ ] abstract word count between 150 and 250
  [ ] required appendix present under its exact title
  [ ] README and report mark any code written before 13 Nov as pre-existing
  [ ] AI assistance described; team takes responsibility for all content
  [ ] every number traced in claim_evidence.csv
  [ ] every reference opened and confirmed by a human
  [ ] repo public, freeze tag visible, traces and generator published
  [ ] same project title on any resubmission


17. CITATION STATUS (ONE SEARCH EACH, 14 NOV)
--------------------------------------------------------------------------------
Confirmed to exist
  Nakayashiki, "When Stale Constraints Go Unchecked: Budgeted Verification
    Failures in Inherited Agent Memory", arXiv 2608.25553. Two-record
    budget and slot re-assignment confirmed.
  Liao, "Auditing Provenance Sensitivity in LLM Agent Action Selection",
    arXiv 2607.20827. 5.4% and 1.7% confirmed.
    CORRECTION: single author (Junchi Liao), so cite "Liao", not
    "Liao et al."; the abstract says 450 tasks.
  Yang et al., "Agents Trust Tools Too Much: Measuring Reliance on
    Unreliable Tools", NeurIPS 2026 listing; arXiv 2609.05587 per a
    secondary page. Inconsistent mitigation from provider metadata
    confirmed. The "higher stated reliability is more persuasive" detail is
    not confirmed.
  Tao and Yin, arXiv 2609.37153.
    CORRECTION: the paper title is "When Tools Silently Lie: Evaluating and
    Mitigating Blind Compliance in Tool-Augmented Data Agents". ToxicBench
    is the benchmark's name, not the title.
  Wang et al., "Facts Without Rules: Boundary Metadata Collapse in
    Multi-Agent LLM Handoffs", arXiv 2608.29028.
  Shan, "Do AI Coding Assistants Check Before They Install? ...",
    arXiv 2609.07754. "9 of 1,920" and zero verification commands confirmed.
  Gao et al. Found as "LLM Aggregators Count Copies Where They Should Count
    Sources" (NeurIPS 2026 listing). The draft's title "Copies or Sources?"
    did not turn up; confirm the exact title from the draft's own link.

Not located by one search each (this does not mean they do not exist)
  K. Fan et al., "Right Facts, Wrong Rule" (76.2% figure)
  Chu and Huang, "Can LLMs Trust Appropriately?"
  J. Zhang, Jiang and Lu, "What Counts as Evidence?"
  Li et al., "HSC-Bench"
  C. Fan et al., "MASCAL"
  Lee et al., "DIVA"
  Chen et al., "Signed but Not Safe"

Rule. Open each from the link in the draft. Any paper that cannot be opened
and matched on title, authors and the quoted figure is removed from the
report. The novelty argument rests most on Nakayashiki (confirmed), K. Fan
et al. and Chu and Huang (both unconfirmed), so check those two first.
Beyond what is listed above, the draft's characterisations of each paper
have not been checked.


18. DECISIONS STILL NEEDED FROM THE TEAM (BEFORE THE PILOT)
--------------------------------------------------------------------------------
D1  Primary model and provider; optional second, smaller model.
D2  Reasoning / thinking setting for that model (on or off, fixed).
D3  Accept or edit the thresholds in Section 9 and the 14-of-16 ceiling
    rule in Section 8.
D4  Who does H1-H5.
================================================================================
