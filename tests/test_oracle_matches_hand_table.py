"""T1: literal hand values and an independent finite-outcome calculation."""

from __future__ import annotations

import csv
from fractions import Fraction as F
from itertools import product
from pathlib import Path

import pytest

from beyond_label.oracle import (
    action_losses, expected_commit_loss, optimal_dispositions, oracle_loss,
    reference_rows, worst_valid_loss, write_reference_table,
)
from beyond_label.schemas import Case, Lot, PublicCase, Report


def hand_case(condition="MAIN", twin="a", results=("PASS", "FAIL"), high_index=0):
    configs = ("M2", "R7") if twin == "a" else ("R7", "M2")
    if condition == "MASKED":
        configs = ("[withheld]", "[withheld]")
    records = tuple(
        Report(record_id=f"REC-{i+1000}", lot_id=f"LOT-{i+2000}", result=result,
               tested_configuration=config)
        for i, (result, config) in enumerate(zip(results, configs))
    )
    targets = tuple(Lot(lot_id=record.lot_id,
                        penalty=800 if condition == "HIGH-STAKES" and i == high_index else 100)
                    for i, record in enumerate(records))
    return Case(world_id="hand-reference", seed=0, twin=twin, layout="separate",
                condition=condition, load=2,
                public=PublicCase(current_configuration="R7", records=records, targets=targets,
                                  metadata_order=tuple(record.record_id for record in records),
                                  fee=60 if condition == "HIGH-FEE" else 20),
                hidden_states={record.lot_id: record.result for record in records})


@pytest.mark.parametrize("condition,twin,expected", [
    ("MAIN", "a", (50, 30, 60)), ("MAIN", "b", (50, 60, 30)),
    ("HIGH-FEE", "a", (50, 70, 100)), ("HIGH-FEE", "b", (50, 100, 70)),
    ("HIGH-STAKES", "a", (330, 30, 340)), ("HIGH-STAKES", "b", (120, 60, 100)),
    ("MASKED", "a", (50, 45, 45)), ("MASKED", "b", (50, 45, 45)),
    ("NUMERIC", "a", (50, 30, 60)), ("NUMERIC", "b", (50, 60, 30)),
])
def test_literal_hand_table(condition, twin, expected):
    case = hand_case(condition, twin)
    assert action_losses(case) == dict(zip(("COMMIT", "INSPECT_1", "INSPECT_2"), expected))
    assert oracle_loss(case) == min(expected)


@pytest.mark.parametrize("twin,expected", [("a", (120, 100, 60)), ("b", (330, 340, 30))])
def test_high_stakes_second_target(twin, expected):
    assert tuple(action_losses(hand_case("HIGH-STAKES", twin, high_index=1)).values()) == expected


@pytest.mark.parametrize("results", list(product(("PASS", "FAIL"), repeat=2)))
@pytest.mark.parametrize("condition", ["MAIN", "HIGH-FEE", "HIGH-STAKES", "MASKED", "NUMERIC"])
@pytest.mark.parametrize("twin", ["a", "b"])
def test_all_valid_commits_against_independent_enumeration(results, condition, twin):
    case = hand_case(condition, twin, results)
    ids = case.public.target_ids
    if condition == "MASKED":
        # A 50/50 mixture of the two scope assignments, not independent .75 states.
        assignments = [(F(1, 2), (F(3, 5), F(9, 10))), (F(1, 2), (F(9, 10), F(3, 5)))]
    else:
        assignments = [(F(1), (F(3, 5), F(9, 10)) if twin == "a" else (F(9, 10), F(3, 5)))]
    for choices in product(("RELEASE", "HOLD"), repeat=2):
        expectation = F(0)
        for prior, accuracies in assignments:
            for matches in product((False, True), repeat=2):
                probability = prior
                loss = 0
                for index, match in enumerate(matches):
                    q = accuracies[index]
                    probability *= q if match else 1-q
                    state = results[index] if match else ("FAIL" if results[index] == "PASS" else "PASS")
                    correct = "RELEASE" if state == "PASS" else "HOLD"
                    if choices[index] != correct:
                        loss += case.public.targets[index].penalty
                expectation += probability * loss
        assert expected_commit_loss(case, dict(zip(ids, choices))) == float(expectation)


@pytest.mark.parametrize("condition", ["MAIN", "HIGH-FEE", "HIGH-STAKES", "NUMERIC"])
@pytest.mark.parametrize("twin", ["a", "b"])
@pytest.mark.parametrize("inspected_index,state", list(product((0, 1), ("PASS", "FAIL"))))
def test_known_scope_optimal_continuation_and_wrong_inspected_commit(condition, twin, inspected_index, state):
    case = hand_case(condition, twin)
    inspected = case.public.target_ids[inspected_index]
    dispositions = optimal_dispositions(case, inspected, state)
    expected = action_losses(case)[f"INSPECT_{inspected_index+1}"]
    assert expected_commit_loss(case, dispositions, inspected, state) == expected
    assert dispositions[inspected] == ("RELEASE" if state == "PASS" else "HOLD")
    dispositions[inspected] = "HOLD" if state == "PASS" else "RELEASE"
    assert expected_commit_loss(case, dispositions, inspected, state) == expected + case.public.targets[inspected_index].penalty


@pytest.mark.parametrize("inspected_index", [0, 1])
def test_masked_posterior_continuation_is_48_or_36_and_prior_is_45(inspected_index):
    case = hand_case("MASKED")
    inspected = case.public.target_ids[inspected_index]
    report_result = case.public.records[inspected_index].result
    opposite = "FAIL" if report_result == "PASS" else "PASS"
    matching = optimal_dispositions(case, inspected, report_result)
    contradicting = optimal_dispositions(case, inspected, opposite)
    assert expected_commit_loss(case, matching, inspected, report_result) == 48
    assert expected_commit_loss(case, contradicting, inspected, opposite) == 36
    assert F(3, 4)*48 + F(1, 4)*36 == action_losses(case)[f"INSPECT_{inspected_index+1}"] == 45
    other = case.public.target_ids[1-inspected_index]
    matching[other] = "HOLD" if matching[other] == "RELEASE" else "RELEASE"
    contradicting[other] = "HOLD" if contradicting[other] == "RELEASE" else "RELEASE"
    assert expected_commit_loss(case, matching, inspected, report_result) == 92
    assert expected_commit_loss(case, contradicting, inspected, opposite) == 104


@pytest.mark.parametrize("condition,twin,expected", [
    ("MAIN", "a", 150), ("MAIN", "b", 150),
    ("HIGH-FEE", "a", 150), ("HIGH-FEE", "b", 150),
    ("HIGH-STAKES", "a", 570), ("HIGH-STAKES", "b", 780),
    ("MASKED", "a", 150), ("NUMERIC", "a", 150),
])
def test_worst_valid_includes_exact_commit_dispositions(condition, twin, expected):
    assert worst_valid_loss(hand_case(condition, twin)) == expected


def test_oracle_never_uses_unrevealed_hidden_state():
    for condition in ("MAIN", "HIGH-FEE", "HIGH-STAKES", "MASKED", "NUMERIC"):
        original = hand_case(condition)
        changed = original.model_copy(update={"hidden_states": {lot_id: "FAIL" if state == "PASS" else "PASS"
                                                                 for lot_id, state in original.hidden_states.items()}})
        assert action_losses(original) == action_losses(changed)
        assert optimal_dispositions(original) == optimal_dispositions(changed)
        assert expected_commit_loss(original, optimal_dispositions(original)) == expected_commit_loss(changed, optimal_dispositions(changed))


@pytest.mark.parametrize("inspected_lot,inspected_state", [("LOT-2000", None), (None, "PASS"), ("LOT-9999", "PASS"), ("LOT-2000", "UNKNOWN")])
def test_invalid_inspection_evidence_rejected(inspected_lot, inspected_state):
    case = hand_case()
    with pytest.raises(ValueError, match="Invalid inspection information"):
        expected_commit_loss(case, optimal_dispositions(case), inspected_lot, inspected_state)
    with pytest.raises(ValueError, match="Invalid inspection information"):
        optimal_dispositions(case, inspected_lot, inspected_state)


@pytest.mark.parametrize("dispositions", [{}, {"LOT-2000": "RELEASE"}, {"LOT-2000": "PASS", "LOT-2001": "HOLD"}, {"LOT-2000": "RELEASE", "LOT-9999": "HOLD"}])
def test_invalid_commit_not_scored_as_valid(dispositions):
    with pytest.raises(ValueError, match="Invalid dispositions"):
        expected_commit_loss(hand_case(), dispositions)


def test_generated_reference_table_matches_literal_source_and_is_reproducible(tmp_path):
    expected = [(50, 30, 60), (50, 60, 30), (50, 70, 100), (50, 100, 70),
                (330, 30, 340), (120, 60, 100), (50, 45, 45), (50, 30, 60), (50, 60, 30)]
    for row, losses in zip(reference_rows(), expected, strict=True):
        assert tuple(row[key] for key in ("commit_follow_reports", "inspect_first_named_lot", "inspect_other")) == losses
        assert row["human_review"] == "not_performed"
        assert row["evidence_kind"] == "analytic_reference_not_observation"
    output = tmp_path / "oracle.csv"
    write_reference_table(output)
    expected_file = Path(__file__).parents[1] / "evaluation" / "oracle_table.csv"
    assert output.read_bytes() == expected_file.read_bytes()
    with output.open(encoding="utf-8", newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 9


def test_all_planned_worlds_layouts_loads_and_conditions_match_hand_table():
    from beyond_label.generate import generate_worlds, make_case

    count = 0
    for dataset in ("pilot", "smoke", "main"):
        for world in generate_worlds(dataset):
            for twin, layout, load, condition in product(("a", "b"), ("separate", "inline"), (2, 8),
                                                        ("MAIN", "HIGH-FEE", "HIGH-STAKES", "MASKED", "NUMERIC")):
                case = make_case(world, twin=twin, layout=layout, condition=condition, load=load)
                if condition in ("MAIN", "NUMERIC"):
                    expected = (50, 30, 60) if twin == "a" else (50, 60, 30)
                elif condition == "HIGH-FEE":
                    expected = (50, 70, 100) if twin == "a" else (50, 100, 70)
                elif condition == "MASKED":
                    expected = (50, 45, 45)
                elif world.high_stakes_index == 0:
                    expected = (330, 30, 340) if twin == "a" else (120, 60, 100)
                else:
                    expected = (120, 100, 60) if twin == "a" else (330, 340, 30)
                assert tuple(action_losses(case).values()) == expected
                assert oracle_loss(case) == min(expected)
                count += 1
    assert count == (8+4+64)*2*2*2*5
