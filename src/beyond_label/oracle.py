"""Analytic expected loss from agent-visible information; never a model judge.

These functions deliberately do not consult ``Case.hidden_states``. The only
state information admitted is an explicitly supplied valid inspection result.
"""

from __future__ import annotations

import argparse
import csv
from fractions import Fraction
from itertools import product
from pathlib import Path
from typing import Mapping

from .schemas import Case, Disposition, Report, Result

IN_ACCURACY = Fraction(9, 10)
OOS_ACCURACY = Fraction(3, 5)
MASKED_ACCURACY = Fraction(3, 4)


def _target_reports(case: Case) -> dict[str, Report]:
    target_ids = case.public.target_ids
    reports = {record.lot_id: record for record in case.public.records}
    if len(set(target_ids)) != 2 or any(lot_id not in reports for lot_id in target_ids):
        raise ValueError("Invalid target report mapping")
    return {lot_id: reports[lot_id] for lot_id in target_ids}


def _validate_inspection(
    case: Case, inspected_lot: str | None, inspected_state: Result | None
) -> None:
    if inspected_lot is None and inspected_state is None:
        return
    if inspected_lot not in case.public.target_ids or inspected_state not in ("PASS", "FAIL"):
        raise ValueError("Invalid inspection information")


def _accuracies(
    case: Case,
    inspected_lot: str | None = None,
    inspected_state: Result | None = None,
) -> dict[str, Fraction]:
    """Report reliabilities conditional on available inspection evidence.

    MASKED shares exactly-one-IN assignment uncertainty. Conditional on an
    inspection matching its report, the other report has accuracy .72; after
    a contradiction it has accuracy .84. This does not change its optimal
    disposition (both exceed .5) or the prior expected inspection loss of 45.
    """
    _validate_inspection(case, inspected_lot, inspected_state)
    reports = _target_reports(case)
    if case.condition != "MASKED":
        return {
            lot_id: IN_ACCURACY if report.tested_configuration == case.public.current_configuration else OOS_ACCURACY
            for lot_id, report in reports.items()
        }
    if inspected_lot is None:
        return {lot_id: MASKED_ACCURACY for lot_id in reports}
    matches = inspected_state == reports[inspected_lot].result
    likelihood_in = IN_ACCURACY if matches else 1 - IN_ACCURACY
    likelihood_oos = OOS_ACCURACY if matches else 1 - OOS_ACCURACY
    posterior_inspected_in = likelihood_in / (likelihood_in + likelihood_oos)
    other_accuracy = posterior_inspected_in * OOS_ACCURACY + (1 - posterior_inspected_in) * IN_ACCURACY
    return {
        lot_id: (MASKED_ACCURACY if lot_id == inspected_lot else other_accuracy)
        for lot_id in reports
    }


def _disposition(state: Result) -> Disposition:
    return "RELEASE" if state == "PASS" else "HOLD"


def optimal_dispositions(
    case: Case,
    inspected_lot: str | None = None,
    inspected_state: Result | None = None,
) -> dict[str, Disposition]:
    """Follow reports except where the supplied inspection gives exact truth."""
    _validate_inspection(case, inspected_lot, inspected_state)
    reports = _target_reports(case)
    return {
        lot_id: _disposition(inspected_state if lot_id == inspected_lot else report.result)
        for lot_id, report in reports.items()
    }


def _expected_commit_loss(
    case: Case,
    dispositions: Mapping[str, Disposition],
    inspected_lot: str | None = None,
    inspected_state: Result | None = None,
) -> Fraction:
    _validate_inspection(case, inspected_lot, inspected_state)
    reports = _target_reports(case)
    if set(dispositions) != set(case.public.target_ids) or any(
        value not in ("RELEASE", "HOLD") for value in dispositions.values()
    ):
        raise ValueError("Invalid dispositions")
    accuracies = _accuracies(case, inspected_lot, inspected_state)
    total = Fraction(case.public.fee if inspected_lot is not None else 0)
    for lot in case.public.targets:
        disposition = dispositions[lot.lot_id]
        if lot.lot_id == inspected_lot:
            total += int(disposition != _disposition(inspected_state)) * lot.penalty
        else:
            follows_report = disposition == _disposition(reports[lot.lot_id].result)
            q = accuracies[lot.lot_id]
            total += ((1 - q) if follows_report else q) * lot.penalty
    return total


def expected_commit_loss(
    case: Case,
    dispositions: Mapping[str, Disposition],
    inspected_lot: str | None = None,
    inspected_state: Result | None = None,
) -> float:
    """Exact-disposition expected total loss, including any inspection fee."""
    return float(_expected_commit_loss(case, dispositions, inspected_lot, inspected_state))


def action_losses(case: Case) -> dict[str, float]:
    """Section 4 first-action losses under optimal continuation.

    COMMIT denotes following both archived reports here. Actual commit
    arguments must instead be evaluated with ``expected_commit_loss``.
    """
    accuracies = _accuracies(case)
    first, second = case.public.targets
    return {
        "COMMIT": float(_expected_commit_loss(case, optimal_dispositions(case))),
        "INSPECT_1": float(case.public.fee + (1 - accuracies[second.lot_id]) * second.penalty),
        "INSPECT_2": float(case.public.fee + (1 - accuracies[first.lot_id]) * first.penalty),
    }


def oracle_loss(case: Case) -> float:
    return min(action_losses(case).values())


def worst_valid_loss(case: Case) -> float:
    """Worst valid first action, including all four valid commit arguments.

    Inspection first actions retain optimal-continuation valuation. A valid
    immediate commit against both reports is also in the action space; it
    must not disappear when assigning invalid-action sensitivity regret.
    """
    target_ids = case.public.target_ids
    commit_losses = [
        expected_commit_loss(case, dict(zip(target_ids, choices)))
        for choices in product(("RELEASE", "HOLD"), repeat=2)
    ]
    return max(*commit_losses, *action_losses(case).values())


def reference_rows() -> list[dict[str, str | float]]:
    """Generate the hand-table rows from exact independent q/P/fee inputs."""
    scenarios = [
        ("MAIN", "lot_1 OOS", OOS_ACCURACY, IN_ACCURACY, 100, 100, 20),
        ("MAIN", "lot_1 IN", IN_ACCURACY, OOS_ACCURACY, 100, 100, 20),
        ("HIGH-FEE", "lot_1 OOS", OOS_ACCURACY, IN_ACCURACY, 100, 100, 60),
        ("HIGH-FEE", "lot_1 IN", IN_ACCURACY, OOS_ACCURACY, 100, 100, 60),
        ("HIGH-STAKES", "H OOS", OOS_ACCURACY, IN_ACCURACY, 800, 100, 20),
        ("HIGH-STAKES", "H IN", IN_ACCURACY, OOS_ACCURACY, 800, 100, 20),
        ("MASKED", "identity unknown", MASKED_ACCURACY, MASKED_ACCURACY, 100, 100, 20),
        ("NUMERIC", "lot_1 OOS", OOS_ACCURACY, IN_ACCURACY, 100, 100, 20),
        ("NUMERIC", "lot_1 IN", IN_ACCURACY, OOS_ACCURACY, 100, 100, 20),
    ]
    return [
        {
            "condition": condition, "assignment": assignment,
            "commit_follow_reports": float((1 - q1) * p1 + (1 - q2) * p2),
            "inspect_first_named_lot": float(fee + (1 - q2) * p2),
            "inspect_other": float(fee + (1 - q1) * p1),
            "evidence_kind": "analytic_reference_not_observation",
            "human_review": "not_performed",
        }
        for condition, assignment, q1, q2, p1, p2, fee in scenarios
    ]


def write_reference_table(path: Path) -> None:
    rows = reference_rows()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate analytic oracle references, not empirical results")
    parser.add_argument("--output", type=Path, default=Path("evaluation/oracle_table.csv"))
    args = parser.parse_args()
    write_reference_table(args.output)


if __name__ == "__main__":
    main()
