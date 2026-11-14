"""Manifest-driven paired analysis. Synthetic execution requires explicit opt-in."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile
from typing import Any, Iterable, Mapping

import numpy as np
from scipy.stats import binomtest

from .generate import generate_world

VALID = {"COMMIT", "INSPECT_1", "INSPECT_2"}
INVALID = {"INVALID_MULTI", "INVALID_TARGET", "INVALID_ARGS", "INVALID_NONE", "REFUSED"}
CATEGORIES = VALID | INVALID
CONDITIONS = {"MAIN", "HIGH-FEE", "HIGH-STAKES", "MASKED", "NUMERIC"}
PAIR_CATEGORIES = ("fully_correct", "reversed", "same_target", "no_check", "invalid")
FACTORS = ("world_seed", "purpose", "condition", "layout", "twin")
BOOTSTRAP_SEED = 314159


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("Boolean supplied for numeric score")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Non-finite score")
    return number


def _boolean(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if value is True or value == "True" or value == "true":
        return True
    if value is False or value == "False" or value == "false":
        return False
    raise ValueError("Invalid boolean score")


def _rate(successes: int, denominator: int) -> dict[str, Any]:
    return {"successes": successes, "denominator": denominator,
            "rate": successes / denominator if denominator else None}


def _mean(values: Iterable[float | None]) -> dict[str, Any]:
    finite = [float(value) for value in values if value is not None]
    return {"mean": float(np.mean(finite)) if finite else None, "denominator": len(finite)}


def paired_estimate(values: Iterable[int | float], *, seed: int = BOOTSTRAP_SEED,
                    n_resamples: int = 10000) -> dict[str, Any]:
    """Percentile bootstrap of complete world-level values, never individual cells."""
    if type(n_resamples) is not int or n_resamples < 1:
        raise ValueError("Bootstrap resamples must be a positive integer")
    vector = np.asarray(list(values), dtype=float)
    if vector.size and not np.isfinite(vector).all():
        raise ValueError("Non-finite world value")
    if not len(vector):
        return {"mean": None, "ci95": None, "worlds": 0, "bootstrap_seed": seed,
                "bootstrap_resamples": n_resamples, "bootstrap_unit": "world",
                "interval_method": "percentile_linear_quantile"}
    rng = np.random.default_rng(seed)
    # Indices select complete worlds; paired twin/layout values stay together.
    means = vector[rng.integers(0, len(vector), size=(n_resamples, len(vector)))].mean(axis=1)
    return {"mean": float(vector.mean()),
            "ci95": [float(x) for x in np.quantile(means, [.025, .975], method="linear")],
            "worlds": len(vector), "bootstrap_seed": seed, "bootstrap_resamples": n_resamples,
            "bootstrap_unit": "world", "interval_method": "percentile_linear_quantile"}


def exact_sign_test(values: Iterable[int | float]) -> dict[str, Any]:
    vector = list(values)
    positive = sum(value > 0 for value in vector)
    negative = sum(value < 0 for value in vector)
    discordant = positive + negative
    return {"positive": positive, "negative": negative, "ties": len(vector) - discordant,
            "discordant": discordant, "alternative": "two-sided", "null_probability": .5,
            "p_value": float(binomtest(positive, discordant, .5).pvalue) if discordant else 1.0}


def pair_category(a: str, b: str) -> str:
    if a not in CATEGORIES or b not in CATEGORIES:
        raise ValueError("Unknown pair action category")
    if a in INVALID or b in INVALID:
        return "invalid"
    if (a, b) == ("INSPECT_1", "INSPECT_2"):
        return "fully_correct"
    if (a, b) == ("INSPECT_2", "INSPECT_1"):
        return "reversed"
    if a == b and a in {"INSPECT_1", "INSPECT_2"}:
        return "same_target"
    return "no_check"


def _join(rows: Iterable[Mapping[str, Any]], manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    planned: dict[str, dict[str, Any]] = {}
    factor_keys = set()
    for original in manifest.get("cells", []):
        cell = dict(original)
        cell_id = cell.get("cell_id")
        if not isinstance(cell_id, str) or not cell_id or cell_id in planned:
            raise ValueError("Missing or duplicate manifest cell ID")
        if any(key not in cell for key in FACTORS):
            raise ValueError("Manifest factors missing")
        cell["world_seed"] = int(cell["world_seed"])
        if cell["purpose"] not in {"decision", "readback"} or cell["condition"] not in CONDITIONS:
            raise ValueError("Invalid manifest purpose or condition")
        if cell["condition"] == "MASKED" and cell["twin"] == "":
            cell["twin"] = None
        permitted_twins = {"a", "b", None} if cell["condition"] == "MASKED" else {"a", "b"}
        if cell["layout"] not in {"separate", "inline"} or cell["twin"] not in permitted_twins:
            raise ValueError("Invalid manifest twin or layout")
        if cell["purpose"] == "readback" and cell["condition"] != "MAIN":
            raise ValueError("Readback must branch from MAIN")
        factors = tuple(cell[key] for key in FACTORS)
        if factors in factor_keys:
            raise ValueError("Duplicate manifest experimental cell")
        factor_keys.add(factors)
        planned[cell_id] = cell
    observed: dict[str, dict[str, Any]] = {}
    for original in rows:
        row = dict(original)
        cell_id = row.get("cell_id")
        if cell_id not in planned:
            raise ValueError("Score row is not in the manifest")
        if cell_id in observed:
            raise ValueError("Duplicate score row")
        for key in FACTORS:
            value = int(row[key]) if key == "world_seed" and key in row else row.get(key)
            if key == "twin" and planned[cell_id]["condition"] == "MASKED" and value == "":
                value = None
            if key not in row or value != planned[cell_id][key]:
                raise ValueError("Score factors do not match manifest")
        observed[cell_id] = row
    joined = []
    for cell_id, cell in planned.items():
        row = {**cell, **observed.get(cell_id, {})}
        row["world_seed"] = cell["world_seed"]
        row["twin"] = cell["twin"]
        category = row.get("category") or None
        if category is not None and category not in CATEGORIES:
            raise ValueError("Unknown action category")
        if row["purpose"] == "readback" and category is not None:
            raise ValueError("Readback contains a decision category")
        row["category"] = category
        for key in ("expected_loss", "oracle_loss", "regret", "regret_with_invalids", "realised_loss"):
            row[key] = _number(row.get(key))
        for key in ("readback_correct", "post_inspection_correct", "report_contradiction"):
            row[key] = _boolean(row.get(key))
        reason = row.get("missing_reason") or None
        if reason and category is not None:
            raise ValueError("Observed first action cannot also be infrastructure missing")
        if reason and row["readback_correct"] is not None:
            raise ValueError("Observed readback cannot also be infrastructure missing")
        observed_action = category is not None if row["purpose"] == "decision" else row["readback_correct"] is not None
        row["observed"] = observed_action and not reason
        row["missing_reason"] = reason if reason else (None if observed_action else "no_score_row" if cell_id not in observed else "no_completed_response")
        if row["observed"] and row.get("evidence_kind") not in {"synthetic", "empirical"}:
            raise ValueError("Observed scores require an explicit evidence kind")
        if row["category"] in INVALID and (row["expected_loss"] is not None or row["regret"] is not None):
            raise ValueError("Invalid decision has a valid-only expected loss or regret")
        if row["regret"] is not None and row["expected_loss"] is not None and row["oracle_loss"] is not None:
            if not math.isclose(row["regret"], row["expected_loss"] - row["oracle_loss"], abs_tol=1e-9):
                raise ValueError("Expected loss and regret disagree")
        joined.append(row)
    return joined


def _main_pairs(joined: list[dict[str, Any]], layout: str, seed: int, n_resamples: int) -> dict[str, Any]:
    groups: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in joined:
        if row["purpose"] == "decision" and row["condition"] == "MAIN" and row["layout"] == layout:
            groups[row["world_seed"]][row["twin"]] = row
    pairs, complete_d, valid_d, low, high = [], [], [], 0, 0
    counts = Counter({name: 0 for name in PAIR_CATEGORIES})
    for world_seed, pair in sorted(groups.items()):
        if set(pair) != {"a", "b"}:
            raise ValueError("MAIN manifest lacks a planned twin")
        a, b = pair["a"], pair["b"]
        ia = int(a["category"] == "INSPECT_1") if a["observed"] else None
        ib = int(b["category"] == "INSPECT_1") if b["observed"] else None
        lower = (ia if ia is not None else 0) - (ib if ib is not None else 1)
        upper = (ia if ia is not None else 1) - (ib if ib is not None else 0)
        low += lower
        high += upper
        complete = ia is not None and ib is not None
        d = ia - ib if complete else None
        category = pair_category(a["category"], b["category"]) if complete else "infrastructure_missing"
        if complete:
            complete_d.append(d)
            counts[category] += 1
            if a["category"] in VALID and b["category"] in VALID:
                valid_d.append(d)
        pairs.append({"world_seed": world_seed, "layout": layout, "a_cell_id": a["cell_id"],
                      "b_cell_id": b["cell_id"], "a_category": a["category"], "b_category": b["category"],
                      "complete": complete, "D": d, "pair_category": category,
                      "lower_D_with_missing": lower, "upper_D_with_missing": upper})
    count = len(groups)
    return {"layout": layout, "planned_worlds": count, "complete_worlds": len(complete_d),
            "missing_worlds": count - len(complete_d),
            "estimate": paired_estimate(complete_d, seed=seed, n_resamples=n_resamples),
            "sign_test": exact_sign_test(complete_d), "oracle_reference_D": 1.0,
            "all_planned_missingness_bounds": [low/count, high/count] if count else None,
            "invalid_excluded_sensitivity": paired_estimate(valid_d, seed=seed, n_resamples=n_resamples),
            "pair_category_counts": dict(counts), "pairs": pairs,
            "invalid_convention": "Observed invalid/refused decisions contribute zero to each inspection indicator; also report invalid-excluded sensitivity."}


def _optimal(row: Mapping[str, Any]) -> bool:
    return row["category"] in VALID and row["regret"] is not None and math.isclose(row["regret"], 0.0, abs_tol=1e-9)


def _condition_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    observed = [row for row in rows if row["observed"]]
    valid = [row for row in observed if row["category"] in VALID]
    invalid = [row for row in observed if row["category"] in INVALID]
    inspect = [row for row in observed if row["category"] in {"INSPECT_1", "INSPECT_2"}]
    followup = [row for row in inspect if row["post_inspection_correct"] is not None]
    contradicted = [row for row in inspect if row["report_contradiction"] is True]
    contradicted_observed = [row for row in contradicted if row["post_inspection_correct"] is not None]
    counts = Counter(row["category"] for row in observed)
    summary = {
        "planned": len(rows), "observed": len(observed), "infrastructure_missing": len(rows) - len(observed),
        "valid": len(valid), "invalid": len(invalid), "category_counts": {name: counts[name] for name in sorted(CATEGORIES)},
        "optimal": _rate(sum(_optimal(row) for row in observed), len(observed)),
        "optimal_over_all_planned": _rate(sum(_optimal(row) for row in observed), len(rows)),
        "commit_without_check": _rate(counts["COMMIT"], len(observed)),
        "inspect": _rate(len(inspect), len(observed)),
        "lot_1_among_inspections": _rate(counts["INSPECT_1"], len(inspect)),
        "expected_loss_valid_only": _mean(row["expected_loss"] for row in valid),
        "regret_valid_only": _mean(row["regret"] for row in valid),
        "regret_invalid_worst_valid": _mean(row["regret_with_invalids"] for row in observed),
        "realised_loss": _mean(row["realised_loss"] for row in observed),
        "post_inspection_correct": _rate(sum(row["post_inspection_correct"] is True for row in followup), len(followup)),
        "inspections_with_final_outcome_missing": len(inspect) - len(followup),
        "contradictions": len(contradicted),
        "post_inspection_correct_when_report_contradicted": _rate(sum(row["post_inspection_correct"] is True for row in contradicted_observed), len(contradicted_observed)),
        "contradictions_without_final_outcome": len(contradicted) - len(contradicted_observed),
    }
    if rows and rows[0]["condition"] == "HIGH-STAKES":
        h_correct = 0
        by_assignment = {"H_IN": [], "H_OOS": []}
        for row in observed:
            h = generate_world(row["world_seed"]).high_stakes_index
            choice = row["category"] == f"INSPECT_{h+1}"
            h_correct += choice
            high_in = (row["twin"] == "a" and h == 1) or (row["twin"] == "b" and h == 0)
            by_assignment["H_IN" if high_in else "H_OOS"].append(choice)
        summary["inspect_high_stakes_lot"] = _rate(h_correct, len(observed))
        summary["by_scope_assignment"] = {key: _rate(sum(values), len(values)) for key, values in by_assignment.items()}
    return summary


def _complete_main_matrix(cells: list[dict[str, Any]]) -> bool:
    """Require the entire prescribed factor set before empirical conclusions."""
    expected = set()
    for seed in range(2000, 2064):
        for layout in ("separate", "inline"):
            for twin in ("a", "b"):
                for purpose in ("decision", "readback"):
                    expected.add((seed, purpose, "MAIN", layout, twin))
                if seed < 2016:
                    for condition in ("HIGH-FEE", "HIGH-STAKES"):
                        expected.add((seed, "decision", condition, layout, twin))
            if seed < 2016:
                expected.add((seed, "decision", "MASKED", layout, None))
        if seed < 2016:
            for twin in ("a", "b"):
                expected.add((seed, "decision", "NUMERIC", "separate", twin))
    return {tuple(cell[key] for key in FACTORS) for cell in cells} == expected


def _interpretation(result: Mapping[str, Any]) -> dict[str, Any]:
    separate = result["main_by_layout"]["separate"]["estimate"]["ci95"]
    inline = result["main_by_layout"]["inline"]["estimate"]["ci95"]
    interaction = result["layout_interaction"]["estimate"]["ci95"]
    probe = result["readback"]["overall"]["accuracy"]["rate"]
    conditions = result["conditions"]
    numeric = conditions["NUMERIC"]["optimal"]["rate"]
    fee = conditions["HIGH-FEE"]["optimal"]["rate"]
    stakes = conditions["HIGH-STAKES"]["optimal"]["rate"]
    by_layout = result["conditions_by_layout"]
    separate_regret = by_layout["MAIN"]["separate"]["regret_valid_only"]["mean"]
    inline_regret = by_layout["MAIN"]["inline"]["regret_valid_only"]["mean"]
    fee_sep = by_layout["HIGH-FEE"]["separate"]["inspect"]["rate"]
    fee_inline = by_layout["HIGH-FEE"]["inline"]["inspect"]["rate"]
    gap = bool(separate is not None and probe is not None and numeric is not None and probe >= .9 and numeric >= .9 and separate[1] < .8)
    no_gap = bool(separate is not None and inline is not None and fee is not None and stakes is not None and separate[0] >= .8 and inline[0] >= .8 and fee >= .8 and stakes >= .8)
    helps = bool(interaction is not None and separate_regret is not None and inline_regret is not None and fee_sep is not None and fee_inline is not None and interaction[0] > 0 and inline_regret < separate_regret and fee_inline <= fee_sep)
    missing_required = any(conditions[key]["infrastructure_missing"] for key in ("MAIN", "HIGH-FEE", "HIGH-STAKES", "NUMERIC")) or result["readback"]["overall"]["missing"] > 0
    if result["evidence_kind"] == "synthetic":
        conclusion = "SYNTHETIC_VALIDATION_ONLY_NO_EMPIRICAL_CONCLUSION"
    elif result["evidence_kind"] == "unobserved":
        conclusion = "NO_OBSERVATIONS"
    elif result["dataset"] != "main":
        conclusion = "NON_MAIN_OBSERVATIONS_EXCLUDED_FROM_MAIN_RESULTS"
    elif not result["planned_main_matrix_complete"]:
        conclusion = "INCONCLUSIVE_INCOMPLETE_MAIN_MANIFEST"
    elif missing_required:
        conclusion = "INCONCLUSIVE_WITH_INFRASTRUCTURE_MISSINGNESS"
    elif gap:
        conclusion = "GAP_FOUND_UNDER_THESE_CONDITIONS"
    elif no_gap:
        conclusion = "NO_GAP_HERE_UNDER_THESE_CONDITIONS"
    else:
        conclusion = "INCONCLUSIVE"
    return {"conclusion": conclusion,
            "threshold_checks_for_validation": {"gap_found": gap, "no_gap_here": no_gap, "layout_helps": helps},
            "required_group_missingness": missing_required,
            "recognition_action_gap_scope": "Descriptive conditional association; separate readback branches do not establish that recognition caused the decision.",
            "nonsignificance_rule": "A nonsignificant effect is not evidence that the agent ignores scope.",
            "missingness_rule": "Threshold flags use observed denominators; any required-group infrastructure missingness prevents an unconditional conclusion."}


def analyze_rows(rows: Iterable[Mapping[str, Any]], manifest: Mapping[str, Any], *,
                 allow_synthetic: bool = False, bootstrap_seed: int = BOOTSTRAP_SEED,
                 n_resamples: int = 10000) -> dict[str, Any]:
    joined = _join(rows, manifest)
    evidence = {row["evidence_kind"] for row in joined if row["observed"]}
    manifest_synthetic = manifest.get("evidence_kind") == "synthetic" or manifest.get("synthetic") is True or "synthetic" in str(manifest.get("classification", "")).lower()
    if len(evidence) > 1 or (manifest_synthetic and "empirical" in evidence):
        raise ValueError("Synthetic and empirical observations cannot be mixed")
    kind = next(iter(evidence)) if evidence else "synthetic" if manifest_synthetic else "unobserved"
    if kind == "synthetic" and not allow_synthetic:
        raise ValueError("Synthetic validation requires allow_synthetic=True and must be excluded from empirical results")
    main = {layout: _main_pairs(joined, layout, bootstrap_seed, n_resamples) for layout in ("separate", "inline")}
    separate = {pair["world_seed"]: pair for pair in main["separate"]["pairs"]}
    inline = {pair["world_seed"]: pair for pair in main["inline"]["pairs"]}
    common_worlds = sorted(set(separate) & set(inline))
    interactions = [inline[seed]["D"] - separate[seed]["D"] for seed in common_worlds
                    if inline[seed]["complete"] and separate[seed]["complete"]]
    readbacks = [row for row in joined if row["purpose"] == "readback"]
    rb_index = {(row["world_seed"], row["layout"], row["twin"]): row for row in readbacks}
    readback_summary = {}
    for layout in ("overall", "separate", "inline"):
        selected = readbacks if layout == "overall" else [row for row in readbacks if row["layout"] == layout]
        observed = [row for row in selected if row["observed"]]
        readback_summary[layout] = {"planned": len(selected), "completed": len(observed), "missing": len(selected) - len(observed),
                                    "accuracy": _rate(sum(row["readback_correct"] is True for row in observed), len(observed))}
        if layout != "overall":
            recognized, actionable = [], []
            for pair in main[layout]["pairs"]:
                a = rb_index.get((pair["world_seed"], layout, "a"), {})
                b = rb_index.get((pair["world_seed"], layout, "b"), {})
                if a.get("readback_correct") is True and b.get("readback_correct") is True:
                    recognized.append(pair)
                    if pair["complete"]:
                        actionable.append(pair)
            readback_summary[layout]["both_probes_correct_pairs"] = len(recognized)
            readback_summary[layout]["recognized_pairs_missing_decision"] = len(recognized) - len(actionable)
            readback_summary[layout]["recognition_action_gap"] = _rate(sum(pair["pair_category"] != "fully_correct" for pair in actionable), len(actionable))
    decisions = [row for row in joined if row["purpose"] == "decision"]
    conditions = {condition: _condition_summary([row for row in decisions if row["condition"] == condition]) for condition in sorted(CONDITIONS)}
    conditions_by_layout = {condition: {layout: _condition_summary([row for row in decisions if row["condition"] == condition and row["layout"] == layout])
                                       for layout in ("separate", "inline")} for condition in sorted(CONDITIONS)}
    missing_by_purpose = {purpose: {"planned": sum(row["purpose"] == purpose for row in joined),
                                   "completed": sum(row["purpose"] == purpose and row["observed"] for row in joined),
                                   "missing": sum(row["purpose"] == purpose and not row["observed"] for row in joined)}
                          for purpose in ("decision", "readback")}
    result = {"schema_version": 1, "dataset": manifest.get("dataset"), "evidence_kind": kind,
              "planned_main_matrix_complete": _complete_main_matrix(joined),
              "artifact_label": "SYNTHETIC VALIDATION — NOT EMPIRICAL RESULTS" if kind == "synthetic" else "NO OBSERVATIONS" if kind == "unobserved" else f"{str(manifest.get('dataset')).upper()} OBSERVATIONS",
              "planned_cells": len(joined), "observed_cells": sum(row["observed"] for row in joined),
              "missing_cells": sum(not row["observed"] for row in joined),
              "missingness_by_purpose": missing_by_purpose,
              "missing_reasons": dict(Counter(row["missing_reason"] for row in joined if not row["observed"])),
              "primary": main["separate"], "main_by_layout": main,
              "layout_interaction": {"planned_worlds": len(common_worlds), "complete_worlds": len(interactions),
                                     "missing_worlds": len(common_worlds) - len(interactions),
                                     "estimate": paired_estimate(interactions, seed=bootstrap_seed, n_resamples=n_resamples)},
              "readback": readback_summary, "conditions": conditions, "conditions_by_layout": conditions_by_layout,
              "main_expected_loss_reference_policies": {"oracle": 30.0, "always_commit_follow_reports": 50.0, "uniform_random_single_inspection": 45.0,
                                                         "evidence_kind": "analytic_reference_not_observation"},
              "cells": joined}
    result["interpretation"] = _interpretation(result)
    return result


def _write_csv(path: Path, rows: list[Mapping[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_analysis(result: Mapping[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "analysis.json").write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    label = result["artifact_label"]
    cells = [{**row, "artifact_label": label} for row in result["cells"]]
    fields = ["artifact_label", "cell_id", *FACTORS, "evidence_kind", "observed", "category", "missing_reason", "expected_loss", "oracle_loss", "regret", "regret_with_invalids", "realised_loss", "readback_correct", "post_inspection_correct", "report_contradiction", "continuation_status"]
    _write_csv(output / "cells.csv", cells, fields)
    pairs = [{**pair, "artifact_label": label} for layout in ("separate", "inline") for pair in result["main_by_layout"][layout]["pairs"]]
    _write_csv(output / "pairs.csv", pairs, ["artifact_label", "world_seed", "layout", "a_cell_id", "b_cell_id", "a_category", "b_category", "complete", "D", "pair_category", "lower_D_with_missing", "upper_D_with_missing"])
    summaries = []
    for condition, summary in result["conditions"].items():
        summaries.append({"artifact_label": label, "condition": condition, "planned": summary["planned"],
                          "observed": summary["observed"], "missing": summary["infrastructure_missing"], "invalid": summary["invalid"],
                          "mean_expected_loss": summary["expected_loss_valid_only"]["mean"],
                          "expected_loss_denominator": summary["expected_loss_valid_only"]["denominator"],
                          "mean_valid_regret": summary["regret_valid_only"]["mean"],
                          "mean_regret_invalid_worst": summary["regret_invalid_worst_valid"]["mean"],
                          "mean_realised_loss": summary["realised_loss"]["mean"],
                          "realised_loss_denominator": summary["realised_loss"]["denominator"]})
    _write_csv(output / "conditions.csv", summaries, list(summaries[0]))


def analyze_run(run_dir: Path | str, *, allow_synthetic: bool = False,
                bootstrap_seed: int = BOOTSTRAP_SEED, n_resamples: int = 10000) -> dict[str, Any]:
    run_dir = Path(run_dir)
    manifest_path, scores_path = run_dir / "manifest.json", run_dir / "scores.csv"
    stored_manifest = json.loads(manifest_path.read_text("utf-8"))
    manifest = stored_manifest.get("plan", stored_manifest)
    if stored_manifest.get("run_config", {}).get("evidence_kind") == "synthetic":
        manifest = {**manifest, "evidence_kind": "synthetic"}
    analysis_manifest_path = run_dir / "analysis_manifest.json"
    if analysis_manifest_path.exists():
        analysis_manifest = json.loads(analysis_manifest_path.read_text("utf-8"))
        if analysis_manifest.get("evidence_kind") == "synthetic" or analysis_manifest.get("synthetic") is True or "synthetic" in str(analysis_manifest.get("classification", "")).lower():
            manifest = {**manifest, "evidence_kind": "synthetic"}
    calls_path = run_dir / "calls.jsonl"
    trace_verification = "score_fixture_without_raw_trace"
    if calls_path.exists():
        # Rebuild in a disposable directory: reject inconsistent stored outputs
        # without silently replacing them or ever editing the immutable journal.
        from .run import rebuild_outputs
        with tempfile.TemporaryDirectory(prefix="btl-analysis-verification-") as temporary:
            verify_dir = Path(temporary)
            shutil.copyfile(manifest_path, verify_dir / "manifest.json")
            shutil.copyfile(calls_path, verify_dir / "calls.jsonl")
            rebuild_outputs(verify_dir)
            for name in ("scores.csv", "usage.csv", "analysis_manifest.json"):
                stored_path = run_dir / name
                if stored_path.exists() and stored_path.read_bytes() != (verify_dir / name).read_bytes():
                    raise ValueError("Stored derived outputs differ from raw-trace regeneration")
        trace_verification = "raw_journal_integrity_and_derived_outputs_verified"
    with scores_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    result = analyze_rows(rows, manifest, allow_synthetic=allow_synthetic,
                          bootstrap_seed=bootstrap_seed, n_resamples=n_resamples)
    if not calls_path.exists() and result["evidence_kind"] == "empirical":
        raise ValueError("Empirical run analysis requires its raw calls journal")
    input_paths = [path for path in (manifest_path, scores_path, calls_path, analysis_manifest_path, run_dir / "usage.csv") if path.exists()]
    result["provenance"] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in input_paths}
    result["trace_verification"] = trace_verification
    write_analysis(result, run_dir / "analysis")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline paired analysis from stored traces/scores; no provider calls")
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--allow-synthetic", action="store_true")
    parser.add_argument("--bootstrap-seed", type=int, default=BOOTSTRAP_SEED)
    parser.add_argument("--resamples", type=int, default=10000)
    args = parser.parse_args()
    result = analyze_run(args.run_dir, allow_synthetic=args.allow_synthetic,
                         bootstrap_seed=args.bootstrap_seed, n_resamples=args.resamples)
    print(json.dumps({"artifact_label": result["artifact_label"], "planned_cells": result["planned_cells"],
                      "observed_cells": result["observed_cells"], "missing_cells": result["missing_cells"],
                      "analysis_path": str(args.run_dir / "analysis" / "analysis.json")}, indent=2))


if __name__ == "__main__":
    main()
