"""Offline, standard-library verification of the final paper's numeric claims.

Run from any directory. --write creates only the adjacent claim_evidence.csv.
Without --write the saved map must equal the independently checked map exactly.
This supplements, and does not replace, frozen replay or human H4 review.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from collections import Counter
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "report/final/manuscript.md"
MAP = ROOT / "report/final/claim_evidence.csv"
COMMAND = "python report/final/verify_claims.py"
A = "results/staged_main_complete/analysis/analysis.json"
B = "results/staged_main_complete/bundle_manifest.json"
F = "research/execution_freeze.json"
O = "research/main_continuation_operational_freeze.json"
T = "results/staged_main_complete/analysis/matched_trace.json"
J = "continuations/staged_main_52_20261116/calls.jsonl"
S = "continuations/staged_main_52_20261116/scores.csv"
PLAN = "data/plans/main_load8.json"
OUT = "research/checks/main52_outcome.json"
PROTOCOL = "research/protocol.md"
AMEND = "research/amendments.md"
REVIEW = "research/checks/final_paper_AI_review.json"


@lru_cache(None)
def raw(path):
    return (ROOT / path).read_bytes()


@lru_cache(None)
def document(path):
    return json.loads(raw(path).decode("utf-8"))


def pointer(value, path):
    for part in path.strip("/").split("/") if path else []:
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@lru_cache(None)
def derived():
    events = [json.loads(line) for line in raw(J).decode("utf-8").splitlines()]
    scores = list(csv.DictReader(io.StringIO(raw(S).decode("utf-8"))))
    decisions = [r for r in scores if r["purpose"] == "decision"]
    replies = [e for e in events if e["event"] == "attempt_succeeded"]
    masked = [e for e in replies if e["phase"] == "first" and "-MASKED-" in e["cell_id"]]
    trunc = [e for e in masked if e["result"]["finish_reason"] == "length"]
    committed = [r for r in decisions if r["continuation_status"] == "committed"]
    invalid = [r for r in decisions if r["continuation_status"].startswith("invalid:")]
    missing = [r for r in decisions if r["continuation_status"].startswith("missing:")]
    control_seeds = sorted({c["world_seed"] for c in document(PLAN)["cells"] if c["condition"] != "MAIN"})
    event_counts = Counter(e["event"] for e in events)
    metrics = {
        "sample": [len(scores), len(decisions), len(scores) - len(decisions), len(document(PLAN)["seeds"]), len(control_seeds)],
        "main_counts": [document(PLAN)["counts"][c] for c in ["MAIN", "READBACK", "HIGH-FEE", "HIGH-STAKES", "MASKED", "NUMERIC"]],
        "controls_seed_range": [min(control_seeds), max(control_seeds)],
        "raw_census": [event_counts["attempt_started"], event_counts["attempt_succeeded"], event_counts["attempt_failed"], event_counts["cell_completed"]],
        "masked_truncation": [len(trunc), len(masked), sum("-separate-" in e["cell_id"] for e in trunc), sum("-inline-" in e["cell_id"] for e in trunc)],
        "outcomes": [sum(r["category"].startswith("INSPECT_") for r in decisions), len(committed), len(invalid), len(missing), sum(r["post_inspection_correct"] == "true" for r in committed), sum(r["report_contradiction"] == "true" for r in committed), sum(r["report_contradiction"] == "true" and r["continuation_status"] != "committed" for r in decisions), sum(r["category"].startswith("INVALID") for r in decisions), sum(bool(r["realised_loss"]) for r in decisions), len(decisions)],
        "invalid_continuation_conditions": [sum(r["condition"] == c for r in invalid) for c in ["HIGH-STAKES", "MASKED", "MAIN"]],
        "missing_continuation_conditions": [r["condition"] for r in missing],
        "known_main_cost": str(sum(Decimal(str(e["result"]["usage"]["cost"])) for e in replies)),
        "frozen_input_count": len(document(F)["input_hashes"]),
        "bundle_counts": [len(document(B)["artifact_hashes"]), len(document(B)["source_hashes"])],
        "payload_settings": sorted({(e["payload"]["model"], e["payload"]["temperature"], e["payload"]["max_tokens"]) for e in replies}),
        "no_missing_firsts": sum(r["cell_status"] != "completed" for r in scores),
    }
    # These values are taken from the selected trace's structured calls and results.
    twins = document(T)["twins"]
    targets = len(re.findall(r"LOT-\d+ \| penalty if wrong:", twins[0]["decision_prefix"][3]["content"]))
    metrics["load_structure"] = [document(F)["selected_load"], targets, document(F)["selected_load"] - targets]
    metrics["trace_actions"] = [json.loads(t["responses"][0]["reply"]["tool_calls"][0]["arguments"])["lot_id"] for t in twins]
    metrics["trace_states"] = [t["tool_transitions"][0]["result"]["state"] for t in twins]
    metrics["trace_dispositions"] = [[json.loads(t["responses"][1]["reply"]["tool_calls"][0]["arguments"])["dispositions"][lot] for lot in ["LOT-5869", "LOT-5552"]] for t in twins]
    metrics["trace_fees"] = [t["tool_transitions"][0]["result"]["fee_charged"] for t in twins]
    for condition in ["MAIN", "HIGH-FEE", "HIGH-STAKES", "MASKED", "NUMERIC"]:
        r = document(A)["conditions"][condition]
        metrics["tableB1_" + condition] = [r["optimal"]["successes"], r["planned"], r["regret_valid_only"]["mean"], r["realised_loss"]["denominator"], r["realised_loss"]["mean"]]
    return metrics


def source_value(sources, query):
    kind, selector = query["kind"], query["selector"]
    if kind == "json":
        return [pointer(document(sources[0]), q) for q in selector]
    if kind == "text":
        text = raw(sources[0]).decode("utf-8")
        assert all(s in text for s in selector), (sources[0], selector)
        return selector
    if kind == "metric":
        return derived()[selector]
    if kind == "csv":
        rows = list(csv.DictReader(io.StringIO(raw(sources[0]).decode("utf-8"))))
        return [float(rows[selector[0]][c]) for c in selector[1:]]
    raise ValueError(kind)


def specifications():
    rows = []

    def add(name, locators, displays, sources, kind, selector, expected, note=""):
        rows.append(dict(claim_id=name, manuscript_locators=locators if isinstance(locators, list) else [locators], display_values=displays if isinstance(displays, list) else [displays], sources=sources if isinstance(sources, list) else [sources], source_query=dict(kind=kind, selector=selector), expected_value=expected, note=note))

    def j(name, loc, display, source, paths, values, note=""):
        add(name, loc, display, source, "json", paths, values, note)

    def m(name, loc, display, sources, metric, value, note=""):
        add(name, loc, display, sources, "metric", metric, value, note)

    def t(name, loc, display, source, excerpts, note=""):
        add(name, loc, display, source, "text", excerpts, excerpts, note)

    abstract = "Provenance labels can remain intact"
    sample = "The main sample has 64 worlds"
    analysis = "We use 10,000 whole-world"
    effects = "All 704 first decisions/readbacks"
    pilot = "An eight-world load-2 pilot"
    settings = "The requested and top-level returned model ID was"
    outcome = "Actual follow-through was not uniformly valid"
    accounting = "Known main-only usage cost is"
    provenance = "The main scientific freeze is commit"
    reproduc = "The analysis tables and figures come from"
    seeds = "The repository includes the exact prompts"
    control = "Optimal first actions occurred in"
    masked = "MASKED had 28 optimal inspections"
    append_masked = "MASKED truncation affected"

    m("sample_dimensions", [abstract, sample, effects], ["704", "448", "256", "64", "16"], [PLAN, S], "sample", [704, 448, 256, 64, 16])
    m("condition_dimensions", [sample, "Figure 1. First-action allocation"], ["256", "64", "32"], PLAN, "main_counts", [256, 256, 64, 64, 32, 32])
    j("primary_effect", [abstract, effects], ["0.9375", "0.875", "0.984375"], A, ["/primary/estimate/mean", "/primary/estimate/ci95"], [0.9375, [0.875, 0.984375]])
    j("inline_effect", [abstract, effects], ["0.921875", "0.859375", "0.984375"], A, ["/main_by_layout/inline/estimate/mean", "/main_by_layout/inline/estimate/ci95"], [0.921875, [0.859375, 0.984375]])
    j("oracle_D", [abstract, "The primary paired estimand"], ["1", "+1"], A, ["/primary/oracle_reference_D"], [1.0])
    j("fully_correct_pairs", [abstract, "| Both inspections correct |"], ["57", "55", "64"], A, ["/primary/pair_category_counts/fully_correct", "/main_by_layout/inline/pair_category_counts/fully_correct", "/primary/planned_worlds"], [57, 55, 64])
    j("readback_correct", [abstract, 'The frozen classification is'], ["256", "every branch"], A, ["/readback/overall/accuracy/successes", "/readback/overall/accuracy/denominator"], [256, 256])
    j("no_check_pairs", ['The frozen classification is', "| At least one commitment"], ["7", "9", "seven", "nine"], A, ["/primary/pair_category_counts/no_check", "/main_by_layout/inline/pair_category_counts/no_check"], [7, 9])
    j("zero_pair_categories", "| Reversed / same-target", "0", A, ["/primary/pair_category_counts/reversed", "/primary/pair_category_counts/same_target", "/primary/pair_category_counts/invalid", "/primary/missing_worlds", "/main_by_layout/inline/pair_category_counts/reversed", "/main_by_layout/inline/pair_category_counts/same_target", "/main_by_layout/inline/pair_category_counts/invalid", "/main_by_layout/inline/missing_worlds"], [0] * 8)
    j("pair_denominators", "Table 2. MAIN twin-pair categories", "64", A, ["/primary/planned_worlds", "/main_by_layout/inline/planned_worlds"], [64, 64])
    j("interaction", effects, ["-0.015625", "-0.109375", "0.078125"], A, ["/layout_interaction/estimate/mean", "/layout_interaction/estimate/ci95"], [-0.015625, [-0.109375, 0.078125]])
    j("sign_test", effects, ["60", "zero", "four", "1.73 x 10^-18"], A, ["/primary/sign_test/positive", "/primary/sign_test/negative", "/primary/sign_test/ties", "/primary/sign_test/p_value"], [60, 0, 4, 1.734723475976807e-18], "P value rounded to three significant figures.")
    j("layout_regret", effects, ["1.25", "1.40625"], A, ["/conditions_by_layout/MAIN/separate/regret_valid_only/mean", "/conditions_by_layout/MAIN/inline/regret_valid_only/mean"], [1.25, 1.40625])
    j("bootstrap", [abstract, analysis, effects, seeds], ["10,000", "314159", "95%"], A, ["/primary/estimate/bootstrap_resamples", "/primary/estimate/bootstrap_seed", "/primary/estimate/interval_method"], [10000, 314159, "percentile_linear_quantile"])
    t("interval_probability", [abstract, analysis, effects], "95%", AMEND, ["a percentile 95% interval"])
    t("interpretation_thresholds", analysis, ["0.80", "0.90"], PROTOCOL, ['probe accuracy >= 90% AND numeric control >= 90% optimal', 'AND the upper 95% bound of D is below 0.80', 'lower 95% bound of D >= 0.80 in both layouts AND both', 'payoff controls >= 80% optimal'])
    j("interpretation_result", [abstract, 'The frozen classification is'], ["no gap here", "no gap here under these conditions"], A, ["/interpretation/conclusion"], ["NO_GAP_HERE_UNDER_THESE_CONDITIONS"])

    t("task_reliabilities_and_inspection", "An agent must RELEASE", ["two", "both", "one", "0.90", "0.60", "once"], "prompts/agent_system.txt", ["90% accuracy", "60% accuracy", "inspect(lot_id) at most once"])
    m("load8_structure", ["Twin A makes the first-displayed", append_masked], ["two", "six", "load-8"], [F, T], "load_structure", [8, 2, 6], "Load=8; selected trace's public handoff contains two target penalties; six other records remain.")
    t("scope_swap_and_target_count", [abstract, "Beyond the Label tests", "Twin A makes the first-displayed"], ["two", "one"], PROTOCOL, ["World. Two target lots.", "Twin (the intervention). Within a world, two versions differ in exactly one", "thing: which of the two target reports carries the current configuration."], "Exact intervention is additionally enforced by frozen tests and replay.")
    t("loss_formula", "For accuracy q_i", ["1", "q_1", "P_1", "q_2", "P_2"], "src/beyond_label/oracle.py", ["((1 - q) if follows_report else q) * lot.penalty", "case.public.fee + (1 - accuracies[second.lot_id]) * second.penalty"])
    t("estimand_definition", "The primary paired estimand", ["1", "+1", "zero", "lot_1"], PROTOCOL, ["D_w = 1[inspect lot_1 | lot_1 OOS] - 1[inspect lot_1 | lot_1 IN]", "Oracle value: +1.00."])
    conditions = ["MAIN", "MAIN", "HIGH-FEE", "HIGH-FEE", "HIGH-STAKES", "HIGH-STAKES", "MASKED"]
    assignments = ["X out of scope", "X in scope", "X out of scope", "X in scope", "H out of scope", "H in scope", "scope identity withheld"]
    losses = [[50, 30, 60], [50, 60, 30], [50, 70, 100], [50, 100, 70], [330, 30, 340], [120, 60, 100], [50, 45, 45]]
    penalties = [[100, 100, 20], [100, 100, 20], [100, 100, 60], [100, 100, 60], [800, 100, 20], [800, 100, 20], [100, 100, 20]]
    oracle_names = ["lot_1 OOS", "lot_1 IN", "lot_1 OOS", "lot_1 IN", "H OOS", "H IN", "identity unknown"]
    for i, (c, assignment, values, pen, oracle_name) in enumerate(zip(conditions, assignments, losses, penalties, oracle_names)):
        loc = "| " + c + ", " + assignment + " |"
        add("analytic_table_loss_" + str(i), loc, [str(n) for n in values], "evaluation/oracle_table.csv", "csv", [i, "commit_follow_reports", "inspect_first_named_lot", "inspect_other"], values, "Analytic reference, not model observation.")
        t("analytic_table_parameters_" + str(i), loc, [str(n) for n in pen], "src/beyond_label/oracle.py", ['("' + c + '", "' + oracle_name + '"', ", " + ", ".join(map(str, pen)) + "),"])
    j("analytic_reference_policies", "HIGH-FEE tests whether checking stops", ["30", "50", "45"], A, ["/main_expected_loss_reference_policies/oracle", "/main_expected_loss_reference_policies/always_commit_follow_reports", "/main_expected_loss_reference_policies/uniform_random_single_inspection"], [30.0, 50.0, 45.0])
    j("pilot_result", pilot, ["15/16", "load-8"], F, ["/pilot_decision/fully_correct_main_pairs", "/pilot_decision/optimal_numeric_calls", "/pilot_decision/main_pairs", "/pilot_decision/numeric_calls", "/selected_load"], [15, 15, 16, 16, 8])
    j("pilot_and_smoke_loads", pilot, ["eight", "load-2", "load-8"], F, ["/gate_evidence/pilot/load", "/gate_evidence/smoke/load", "/gate_evidence/smoke8/load", "/real_smoke_passed", "/real_pilot_passed"], [2, 2, 8, True, True])
    j("pilot_world_count", pilot, "eight-world", "data/manifest.json", ["/files/worlds_pilot.jsonl/worlds"], [8])
    t("pilot_thresholds", pilot, ["14/16", "12/16"], PROTOCOL, ["14 or more of 16 fully correct", "fewer than 12 of 16 pilot"])
    j("settings", [settings, abstract, append_masked], ["deepseek/deepseek-v4.1-flash-1017", "V4.1", "0", "512"], F, ["/provider_settings/model", "/provider_settings/provider", "/provider_settings/temperature", "/provider_settings/reasoning/effort", "/provider_settings/max_output_tokens"], ["deepseek/deepseek-v4.1-flash-1017", "PrimeIntellect", 0.0, "none", 512])
    j("schedule", [settings, seeds], "271828", F, ["/schedule_seed"], [271828])
    t("reprompt", [settings, masked, append_masked], ["one", "exactly one tool call"], "prompts/reprompt_no_tool.txt", ["Respond with exactly one tool call."])
    t("retry_and_reprompt_limits", settings, ["three retries", "one fixed re-prompt"], "configs/staged.yaml", ["infrastructure_retries_after_initial: 3", "no_tool_reprompts: 1"])
    t("single_sample", ["Accurate metadata, supplied reliabilities", "The instrument assumes authentic metadata"], "one sample per cell", PROTOCOL, ["one sample per cell."])
    j("single_model_temperature", ["Accurate metadata, supplied reliabilities", "The instrument assumes authentic metadata"], ["One model/provider", "one pinned model/provider", "temperature zero"], F, ["/provider_settings/model", "/provider_settings/temperature"], ["deepseek/deepseek-v4.1-flash-1017", 0.0])
    t("one_inspection_opportunity", [abstract, "Chu and Huang [3]", "HIGH-FEE tests whether checking stops"], "one", "prompts/agent_system.txt", ["inspect(lot_id) at most once"])

    for c, count, n in [("MAIN", 239, 256), ("HIGH-FEE", 63, 64), ("HIGH-STAKES", 52, 64), ("NUMERIC", 32, 32)]:
        locs = [control, abstract] if c == "HIGH-STAKES" else [control]
        j("optimal_" + c, locs, [str(count) + "/" + str(n)], A, ["/conditions/" + c + "/optimal/successes", "/conditions/" + c + "/optimal/denominator"], [count, n])
    j("stakes_rate", control, "81.25%", A, ["/conditions/HIGH-STAKES/optimal/rate"], [0.8125], "Displayed as percentage.")
    j("stakes_layout", control, ["27/32", "25/32"], A, ["/conditions_by_layout/HIGH-STAKES/separate/optimal/successes", "/conditions_by_layout/HIGH-STAKES/inline/optimal/successes", "/conditions_by_layout/HIGH-STAKES/separate/optimal/denominator", "/conditions_by_layout/HIGH-STAKES/inline/optimal/denominator"], [27, 25, 32, 32])
    j("stakes_assignments", control, ["30/32", "22/32"], A, ["/conditions/HIGH-STAKES/by_scope_assignment/H_OOS/successes", "/conditions/HIGH-STAKES/by_scope_assignment/H_IN/successes", "/conditions/HIGH-STAKES/by_scope_assignment/H_OOS/denominator", "/conditions/HIGH-STAKES/by_scope_assignment/H_IN/denominator"], [30, 22, 32, 32])
    j("masked_actions", masked, ["28", "32", "two", "lot_1"], A, ["/conditions/MASKED/optimal/successes", "/conditions/MASKED/planned", "/conditions/MASKED/category_counts/COMMIT", "/conditions/MASKED/category_counts/INVALID_ARGS", "/conditions/MASKED/lot_1_among_inspections/successes", "/conditions/MASKED/lot_1_among_inspections/denominator"], [28, 32, 2, 2, 28, 28])
    m("masked_truncations", [abstract, masked, append_masked], ["21/32", "11", "10"], J, "masked_truncation", [21, 32, 11, 10])
    m("continuation_and_outcome_counts", [abstract, outcome], ["356", "339", "16", "Sixteen", "one", "130", "three", "two", "429/448"], [J, S], "outcomes", [356, 339, 16, 1, 339, 130, 3, 2, 429, 448])

    j("trace_selection", "The illustration is selected mechanically", "2000", T, ["/selection_rule", "/twins/0/cell_id", "/twins/1/cell_id"], ["lowest world seed with both MAIN separate-layout first actions observed", "main-2000-decision-MAIN-separate-a", "main-2000-decision-MAIN-separate-b"])
    t("trace_reports", ["The illustration is selected mechanically", "| REC-2307 / LOT-5869 scope |", "| REC-6928 / LOT-5552 scope |", "| Final dispositions, LOT-5869 / LOT-5552 |"], ["V8", "M2", "REC-2307", "LOT-5869", "REC-6928", "LOT-5552", "both"], T, ["REC-2307 | LOT-5869 | result: PASS", "REC-6928 | LOT-5552 | result: PASS", "REC-2307 | tested_configuration: M2", "REC-2307 | tested_configuration: V8", "REC-6928 | tested_configuration: V8", "REC-6928 | tested_configuration: M2", "configuration V8"])
    m("trace_inspections", "| First tool call |", ["LOT-5869", "LOT-5552"], T, "trace_actions", ["LOT-5869", "LOT-5552"])
    m("trace_inspection_states", "| Inspection result |", ["FAIL", "PASS"], T, "trace_states", ["FAIL", "PASS"])
    m("trace_final_dispositions", "| Final dispositions, LOT-5869 / LOT-5552 |", ["HOLD / RELEASE", "RELEASE / RELEASE"], T, "trace_dispositions", [["HOLD", "RELEASE"], ["RELEASE", "RELEASE"]])
    m("trace_fees", "Table 3. Trace-derived matched example", "20", T, "trace_fees", [20, 20])
    t("trace_penalties", "Table 3. Trace-derived matched example", "100", T, ["LOT-5869 | penalty if wrong: 100", "LOT-5552 | penalty if wrong: 100"])

    j("release_source", "Repository: https://github.com", ["0bc1ceaf199c5bd0ec19de175040662e1a170270", "v1"], REVIEW, ["/reviewed_commit"], ["0bc1ceaf199c5bd0ec19de175040662e1a170270"])
    j("scientific_freeze", [provenance, "Repository: https://github.com"], ["6f8f94b3542980f65ba08f56aa3a12bf12c9e41d", "btl-freeze-v1"], F, ["/commit", "/tag"], ["6f8f94b3542980f65ba08f56aa3a12bf12c9e41d", "btl-freeze-v1"])
    j("operational_freeze", [provenance, "Repository: https://github.com"], ["cc7c81dbfda50aefada5c4e62f1ffd8702601939", "btl-main52-operations-v1"], O, ["/source_commit", "/tag"], ["cc7c81dbfda50aefada5c4e62f1ffd8702601939", "btl-main52-operations-v1"])
    m("scientific_input_count", provenance, "50", F, "frozen_input_count", 50)
    j("parent_stop", provenance, ["652", "40", "52"], "research/checks/main_continuation_boundary.json", ["/main/completed_cells", "/main/eligible_cells", "/budget/unknown_cost_holds"], [652, 52, 40])
    j("selected_endpoint_identity", provenance, "deepseek/deepseek-v4.1-flash-20261017", F, ["/provider_settings/accepted_endpoint_models"], [["deepseek/deepseek-v4.1-flash-20261017"]])
    t("http429", provenance, "429", J, ['"http_status":429'], "Raw error fields, not inferred transport success.")
    j("new_continuation", "The continuation produced 84 accepted calls", ["84", "no new"], OUT, ["/new_accepted_calls", "/new_failed_attempts", "/new_unknown_charges"], [84, 0, 0])
    m("main_attempt_census", "The continuation produced 84 accepted calls", ["1,120", "1,080"], J, "raw_census", [1120, 1080, 40, 704])
    j("retry_reprompt_census", "The continuation produced 84 accepted calls", ["39", "21"], "results/staged_main_complete/execution_summary.json", ["/infrastructure_retries", "/permitted_reprompts"], [39, 21])
    m("main_known_cost", accounting, "0.13275084448", J, "known_main_cost", "0.13275084448")
    j("staged_accounting", accounting, ["1.93872838656", "40", "0.20233421648", "6.85893739696", "1,645"], OUT, ["/reconciliation/held_usd", "/reconciliation/held_reservations", "/reconciliation/settled_cost_usd", "/reconciliation/available_usd", "/reconciliation/journaled_attempts"], ["1.93872838656", 40, "0.20233421648", "6.85893739696", 1645])
    j("staged_limits", accounting, ["9", "3,000"], "research/staged_authorization.json", ["/limits/ledger_cap_usd", "/limits/maximum_inference_attempts"], ["9", 3000])
    t("pacing", accounting, "15-second", "scripts/continuation_pacing.py", ["self._next_start = self._now() + 15.0", "self._next_start = now + 15.0"], "Code-backed interval; per-POST wall times were not logged.")
    values = {"MAIN": [239,256,1.328125,255,26.901960784313726], "HIGH-FEE": [63,64,0.3125,64,57.1875], "HIGH-STAKES": [52,64,17.5,51,95.29411764705883], "MASKED": [28,32,0.3333333333333333,27,62.96296296296296], "NUMERIC": [32,32,0.0,32,29.375]}
    display = {"MAIN": ["239/256","1.328125","255/256","26.901961"], "HIGH-FEE": ["63/64","0.3125","64/64","57.1875"], "HIGH-STAKES": ["52/64","17.5","51/64","95.294118"], "MASKED": ["28/32","0.333333","27/32","62.962963"], "NUMERIC": ["32/32","0","29.375"]}
    for c in values:
        m("full_condition_table_" + c, "| " + c + " |", display[c], A, "tableB1_" + c, values[c], "Means displayed at up to six decimal places; exact machine values retained.")
    j("masked_regret_denominator", "MASKED's valid-only regret denominator", ["30", "two"], A, ["/conditions/MASKED/regret_valid_only/denominator", "/conditions/MASKED/invalid"], [30, 2])
    j("masked_invalid_sensitivity", "MASKED's valid-only regret denominator", ["6.875", "32"], A, ["/conditions/MASKED/regret_invalid_worst_valid/mean", "/conditions/MASKED/regret_invalid_worst_valid/denominator"], [6.875, 32])
    m("invalid_continuations_by_condition", "MASKED's valid-only regret denominator", ["16", "12", "three", "one"], S, "invalid_continuation_conditions", [12, 3, 1])
    m("missing_continuation_condition", "MASKED's valid-only regret denominator", "HIGH-STAKES", S, "missing_continuation_conditions", ["HIGH-STAKES"])
    m("no_first_missingness", ["MASKED's valid-only regret denominator", "Figure 1. First-action allocation"], ["No", "no invalid"], S, "no_missing_firsts", 0)
    for dataset, start, end in [("main", 2000, 2063), ("pilot", 1000, 1007), ("smoke", 1100, 1103)]:
        j("seed_range_" + dataset, seeds, str(start) + "-" + str(end), "data/manifest.json", ["/files/worlds_" + dataset + ".jsonl/seed_start", "/files/worlds_" + dataset + ".jsonl/seed_end"], [start, end])
    m("control_seed_range", seeds, "2000-2015", PLAN, "controls_seed_range", [2000, 2015])
    t("human_audit_seed", seeds, "161803", AMEND, ["Future human audit seed: 161803"], "Sampling convention, not evidence that human worksheets exist.")
    m("reproduction_file_counts", reproduc, ["11", "five"], B, "bundle_counts", [11, 5])
    j("clean_reproduction", reproduc, ["11", "five"], "research/checks/main52_clean_clone_reproduction.json", ["/artifact_count", "/comparisons/source_hashes", "/comparisons/bootstrap", "/comparisons/completeness", "/comparisons/continuation_provenance", "/python_socket_network_blocked", "/credential_file_absent"], [11, True, True, True, True, True, True])
    t("precontinuation_tests", reproduc, "1,771", "research/checks/main52_implementation_tests.json", ["1771 passed in 1051.20s"])
    j("independent_AI_review_counts", reproduc, ["448", "256", "429", "1,788", "823"], REVIEW, ["/reviews/paper_validity/raw_first_actions_checked", "/reviews/paper_validity/readbacks_checked", "/reviews/paper_validity/realised_losses_checked", "/reviews/paper_validity/Fraction_numeric_fields_checked", "/reviews/paper_validity/claim_map_entries_checked", "/reviews/paper_validity/discrepancies"], [448,256,429,1788,823,0], "AI review scope only; not human completion.")
    j("raw_source_directory", reproduc, "staged_main_52_20261116", B, ["/continuation_provenance/directory"], ["continuations/staged_main_52_20261116"])
    for i, code, version, locator in [(0,"2608.25553",3,"1. Nakayashiki,"),(1,"2609.35155",2,"2. Fan,"),(2,"2610.34107",1,"3. Chu,")]:
        j("reference_identifier_" + str(i+1), locator, ["2026", code + "v" + str(version)], "research/checks/report_preparation_sources.json", ["/primary_sources_rechecked/" + str(i) + "/url"], ["https://arxiv.org/html/" + code + "v" + str(version)], "2026 is the year encoded in the arXiv identifier; citation index is a structural label.")
    j("authors", "Tonmoy Sarker, Araf Akhter and Abidur Rahaman", ["Tonmoy Sarker", "Araf Akhter", "Abidur Rahaman"], "report/final/author_metadata.json", ["/authors/0/name", "/authors/1/name", "/authors/2/name"], ["Tonmoy Sarker", "Araf Akhter", "Abidur Rahaman"], "User-confirmed names; this is not inferred H3 participation.")
    j("prior_work_disclosure", "The initial idea and local design draft", ["13 November 2026", "All three authors"], "report/final/author_metadata.json", ["/prior_work_disclosure"], ["The initial idea and local design draft predated the sprint opening on 13 November 2026; Tonmoy Sarker and Araf Akhter developed them. No preexisting code is included in this repository. Abidur Rahaman contributed code during the sprint. Sprint work comprised completing and validating the instrument, controlled execution and provenance checks, smoke and pilot stages, the scientific freeze, main collection and its bounded continuation, analysis and reporting. The earlier idea and draft are acknowledged as prior work. All three authors reviewed the study data."], "Build-time expansion of [[PRIOR_WORK_DISCLOSURE]] from user-confirmed metadata. The latest clarification supersedes the earlier ambiguous code statement; these are attested history and roles, not independently observed facts.")
    return rows


def numeric_tokens(text):
    text = re.sub(r"\[\d+\]", "", text)  # citation labels
    text = re.sub(r"(?:Table|Figure)\s+[A-Z]?\d+", "", text)
    text = re.sub(r"Lot [12]", "", text)  # displayed-position labels
    text = re.sub(r"https?://\S+", "", text)  # URL identifiers, not quantities
    text = re.sub(r"^\d+\.\s+", "", text)  # bibliography label
    return set(re.findall(r"(?<![A-Za-z_])\d+(?:[.,]\d+)*", text))


def build_map():
    text = PAPER.read_text(encoding="utf-8")
    text = text.replace("[[PRIOR_WORK_DISCLOSURE]]", document("report/final/author_metadata.json")["prior_work_disclosure"])
    lines = text.splitlines()
    specs = specifications()
    output, covered = [], {}
    failures = []
    for spec in specs:
        try:
            actual = source_value(spec["sources"], spec["source_query"])
            assert actual == spec["expected_value"], (spec["claim_id"], actual, spec["expected_value"])
            locations = []
            for locator in spec["manuscript_locators"]:
                hits = [i for i, line in enumerate(lines, 1) if locator in line]
                assert len(hits) == 1, ("locator must match one paragraph", locator, hits)
                line_no = hits[0]
                locations.append(line_no)
                covered.setdefault(line_no, set()).update(numeric_tokens(" ".join(spec["display_values"])))
            # A display can occur in one of several repeated claim locations.
            joined = " ".join(lines[n-1] for n in locations)
            assert all(d in joined for d in spec["display_values"]), ("display missing", spec["claim_id"], spec["display_values"])
            hashes = {s: hashlib.sha256(raw(s)).hexdigest() for s in spec["sources"]}
            output.append({"claim_id":spec["claim_id"], "manuscript_lines":dumps(locations), "manuscript_locators":dumps(spec["manuscript_locators"]), "display_values":dumps(spec["display_values"]), "expected_value":dumps(spec["expected_value"]), "source_files":dumps(spec["sources"]), "source_sha256":dumps(hashes), "source_selector":dumps(spec["source_query"]), "reproduction_command":COMMAND, "note":spec["note"]})
        except (AssertionError, KeyError, ValueError, IndexError) as exc:
            failures.append(f"{spec['claim_id']}: {exc}")
    for n, line in enumerate(lines, 1):
        if not line or line.startswith(("#", "    ", "[[")) or re.fullmatch(r"[| :\-]+", line):
            continue
        # Formula subscripts, section/check names, and publication/platform IDs
        # are either mapped explicitly above or structural (not sample claims).
        tokens = numeric_tokens(line)
        if tokens:
            missing = tokens - covered.get(n, set())
            if missing:
                failures.append(f"Unmapped numeric tokens on manuscript line {n}: {sorted(missing)}")
    assert not failures, "\n".join(failures)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write the verified CSV map")
    args = parser.parse_args()
    rows = build_map()
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    expected = buffer.getvalue().encode("utf-8")
    if args.write:
        MAP.write_bytes(expected)
    else:
        assert MAP.read_bytes() == expected, "Claim map is stale: review changes, then regenerate with --write."
    print(json.dumps({"status":"passed", "claim_rows":len(rows), "manuscript_sha256":hashlib.sha256(PAPER.read_bytes()).hexdigest(), "map_sha256":hashlib.sha256(expected).hexdigest(), "source_files":len({s for r in rows for s in json.loads(r['source_files'])}), "scope":"offline numeric evidence check; not human H4 or publication", "unmapped_numeric_paragraphs":0}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
