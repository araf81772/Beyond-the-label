"""Offline figures and allocation tables derived solely from analyzed rows."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Mapping

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .analyze import INVALID, PAIR_CATEGORIES, analyze_run
from .generate import generate_world

ALLOCATION_ACTIONS = ("COMMIT", "INSPECT_1", "INSPECT_2", "INVALID", "MISSING")


def allocation_table(analysis: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Agent and analytic oracle allocations, each using the planned denominator."""
    rows = []
    for condition in ("MAIN", "HIGH-FEE", "HIGH-STAKES"):
        cells = [row for row in analysis["cells"] if row["purpose"] == "decision" and row["condition"] == condition]
        observed = {action: 0 for action in ALLOCATION_ACTIONS}
        reference = {action: 0 for action in ALLOCATION_ACTIONS}
        for cell in cells:
            category = "MISSING" if not cell["observed"] else "INVALID" if cell["category"] in INVALID else cell["category"]
            observed[category] += 1
            if condition == "HIGH-FEE":
                optimal = "COMMIT"
            elif condition == "HIGH-STAKES":
                optimal = f"INSPECT_{generate_world(cell['world_seed']).high_stakes_index + 1}"
            else:
                optimal = "INSPECT_1" if cell["twin"] == "a" else "INSPECT_2"
            reference[optimal] += 1
        for action in ALLOCATION_ACTIONS:
            rows.append({"artifact_label": analysis["artifact_label"], "condition": condition, "action": action,
                         "planned_denominator": len(cells), "agent_count": observed[action],
                         "agent_fraction": observed[action]/len(cells) if cells else None,
                         "oracle_reference_count": reference[action],
                         "oracle_reference_fraction": reference[action]/len(cells) if cells else None,
                         "oracle_evidence_kind": "analytic_reference_not_observation"})
    return rows


def write_figures(analysis: Mapping[str, Any], output: Path | str, *, allow_synthetic: bool = False) -> list[Path]:
    if analysis["evidence_kind"] == "synthetic" and not allow_synthetic:
        raise ValueError("Synthetic figures require explicit opt-in")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    label = analysis["artifact_label"]
    allocations = allocation_table(analysis)
    table_path = output / "allocation.csv"
    with table_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(allocations[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(allocations)

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.8), sharey=True, layout="constrained")
    for ax, condition in zip(axes, ("MAIN", "HIGH-FEE", "HIGH-STAKES")):
        rows = [row for row in allocations if row["condition"] == condition]
        x = np.arange(len(ALLOCATION_ACTIONS))
        agent = [row["agent_fraction"] or 0 for row in rows]
        oracle = [row["oracle_reference_fraction"] or 0 for row in rows]
        observed_label = "Scripted fixture outcomes" if analysis["evidence_kind"] == "synthetic" else "Agent observations"
        ax.bar(x - .19, agent, .38, label=observed_label, color="#197487")
        ax.bar(x + .19, oracle, .38, label="Analytic oracle reference", color="#d89832")
        ax.set_xticks(x, ["Commit", "Inspect 1", "Inspect 2", "Invalid", "Missing"], rotation=28, ha="right")
        ax.set_title(f"{condition}\nPlanned cells: {rows[0]['planned_denominator']}")
        ax.set_ylim(0, 1.05)
        ax.grid(axis="y", alpha=.2)
        if not rows[0]["planned_denominator"]:
            ax.text(.5, .45, "No planned cells", transform=ax.transAxes, ha="center")
    axes[0].set_ylabel("Fraction of planned decision cells")
    axes[-1].legend(loc="upper right", fontsize=8)
    fig.suptitle(f"{label}\nAgent allocation versus oracle", fontsize=13)
    allocation_path = output / "agent_allocation_vs_oracle.png"
    fig.savefig(allocation_path, dpi=160, metadata={"Description": label})
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), sharey=True, layout="constrained")
    labels = ["Correct\nswitch", "Reverse\nswitch", "Same\ntarget", "No\ncheck", "Invalid", "Missing /\npending"]
    for ax, layout in zip(axes, ("separate", "inline")):
        summary = analysis["main_by_layout"][layout]
        counts = [summary["pair_category_counts"][key] for key in PAIR_CATEGORIES] + [summary["missing_worlds"]]
        x = np.arange(len(counts))
        bars = ax.bar(x, counts, color=["#197487", "#b45744", "#7a6f94", "#aa925c", "#6f7478", "#c8ccce"])
        ax.set_xticks(x, labels)
        ax.set_title(f"{layout.title()} • planned worlds: {summary['planned_worlds']}")
        ax.bar_label(bars, labels=[str(count) for count in counts], padding=3)
        ax.set_ylim(0, max(1, summary["planned_worlds"]) * 1.15)
        ax.grid(axis="y", alpha=.2)
    axes[0].set_ylabel("Matched worlds")
    fig.suptitle(f"{label}\nMAIN pair-switch categories", fontsize=13)
    pair_path = output / "pair_switch_categories.png"
    fig.savefig(pair_path, dpi=160, metadata={"Description": label})
    plt.close(fig)
    return [table_path, allocation_path, pair_path]


def figures_for_run(run_dir: Path | str, *, allow_synthetic: bool = False,
                    bootstrap_seed: int = 314159, n_resamples: int = 10000) -> list[Path]:
    run_dir = Path(run_dir)
    analysis = analyze_run(run_dir, allow_synthetic=allow_synthetic,
                           bootstrap_seed=bootstrap_seed, n_resamples=n_resamples)
    return write_figures(analysis, run_dir / "analysis" / "figures", allow_synthetic=allow_synthetic)


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate trace-derived figures offline")
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--allow-synthetic", action="store_true")
    args = parser.parse_args()
    files = figures_for_run(args.run_dir, allow_synthetic=args.allow_synthetic)
    print(json.dumps({"generated": [str(path) for path in files]}, indent=2))


if __name__ == "__main__":
    main()
