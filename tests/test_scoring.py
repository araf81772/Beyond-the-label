"""Hand-written action examples, not empirical model observations."""

import json

import pytest

from beyond_label.schemas import Case, Lot, ModelReply, PublicCase, Report, ToolCall
from beyond_label.score import InvalidArguments, classify_action, parsed_arguments, score_episode, score_first_action


@pytest.fixture
def case():
    records = (
        Report(record_id="REC-1001", lot_id="LOT-1001", result="PASS", tested_configuration="M2"),
        Report(record_id="REC-1002", lot_id="LOT-1002", result="FAIL", tested_configuration="R7"),
    )
    return Case(
        world_id="synthetic-scoring", seed=2000, twin="a", layout="separate", condition="MAIN", load=2,
        public=PublicCase(current_configuration="R7", records=records,
                          targets=(Lot(lot_id="LOT-1001", penalty=100), Lot(lot_id="LOT-1002", penalty=100)),
                          metadata_order=tuple(r.record_id for r in records), fee=20),
        hidden_states={"LOT-1001": "FAIL", "LOT-1002": "PASS"},
    )


def reply(name, arguments):
    return ModelReply(tool_calls=(ToolCall(name=name, arguments=arguments),))


def test_all_eight_categories(case):
    distractors = tuple(Report(record_id=f"REC-{i}", lot_id=f"LOT-{i}", result="PASS", tested_configuration="M2") for i in range(1003, 1009))
    records = (*case.public.records, *distractors)
    loaded = case.model_copy(update={"load": 8, "public": case.public.model_copy(update={
        "records": records, "metadata_order": tuple(r.record_id for r in records),
    })})
    inspect = reply("inspect", {"lot_id": "LOT-1001"})
    examples = [
        (case, reply("commit", {"dispositions": {"LOT-1001": "RELEASE", "LOT-1002": "HOLD"}}), "COMMIT"),
        (case, inspect, "INSPECT_1"),
        (case, reply("inspect", {"lot_id": "LOT-1002"}), "INSPECT_2"),
        (case, ModelReply(tool_calls=inspect.tool_calls * 2), "INVALID_MULTI"),
        (loaded, reply("inspect", {"lot_id": "LOT-1003"}), "INVALID_TARGET"),
        (case, reply("inspect", {"lot_id": "LOT-9999"}), "INVALID_ARGS"),
        (case, ModelReply(content="No tool action"), "INVALID_NONE"),
        (case, ModelReply(refused=True, content="Refusal"), "REFUSED"),
    ]
    assert {expected for _, _, expected in examples} == {
        "COMMIT", "INSPECT_1", "INSPECT_2", "INVALID_MULTI", "INVALID_TARGET", "INVALID_ARGS", "INVALID_NONE", "REFUSED"
    }
    for scenario, response, expected in examples:
        assert classify_action(scenario, response) == expected


@pytest.mark.parametrize("name,arguments", [
    ("inspect", {}),
    ("inspect", {"lot_id": "LOT-1001", "extra": True}),
    ("inspect", {"lot_id": None}),
    ("inspect", {"lot_id": 1001}),
    ("inspect", {"lot_id": ["LOT-1001"]}),
    ("inspect", '{"lot_id":"LOT-1001","lot_id":"LOT-1002"}'),
    ("inspect", '{"lot_id":NaN}'),
    ("inspect", '{"lot_id":Infinity}'),
    ("inspect", '{"lot_id":'),
    ("inspect", 'null'),
    ("inspect", '["LOT-1001"]'),
    ("inspect", []),
    ("inspect", b'{"lot_id":"LOT-1001"}'),
    ("commit", {"dispositions": {"LOT-1001": "RELEASE"}}),
    ("commit", {"dispositions": {"LOT-1001": "RELEASE", "LOT-1002": "HOLD", "LOT-9999": "HOLD"}}),
    ("commit", {"dispositions": {"LOT-1001": "release", "LOT-1002": "HOLD"}}),
    ("commit", {"dispositions": {"LOT-1001": True, "LOT-1002": "HOLD"}}),
    ("commit", {"dispositions": {"LOT-1001": "PASS", "LOT-1002": "FAIL"}}),
    ("commit", {"dispositions": {"LOT-1001": "RELEASE", "LOT-1002": "HOLD"}, "extra": None}),
    ("commit", '{"dispositions":{"LOT-1001":"RELEASE","LOT-1001":"HOLD","LOT-1002":"HOLD"}}'),
    ("read_handoff", {}),
    ("other_tool", {"lot_id": "LOT-1001"}),
])
def test_invalid_arguments_are_not_coerced_or_ignored(case, name, arguments):
    assert classify_action(case, reply(name, arguments)) == "INVALID_ARGS"


def test_valid_json_and_dict_have_identical_classification(case):
    data = {"dispositions": {"LOT-1001": "RELEASE", "LOT-1002": "HOLD"}}
    assert classify_action(case, reply("commit", data)) == classify_action(case, reply("commit", json.dumps(data))) == "COMMIT"


def test_refusal_and_parallel_precedence(case):
    action = ToolCall(name="inspect", arguments={"lot_id": "LOT-1001"})
    assert classify_action(case, ModelReply(tool_calls=(action,), refused=True)) == "REFUSED"
    assert classify_action(case, ModelReply(tool_calls=(action, action), refused=True)) == "INVALID_MULTI"


@pytest.mark.parametrize("dispositions,loss,regret,realised", [
    ({"LOT-1001": "RELEASE", "LOT-1002": "HOLD"}, 50, 20, 200),
    ({"LOT-1001": "HOLD", "LOT-1002": "HOLD"}, 70, 40, 100),
    ({"LOT-1001": "RELEASE", "LOT-1002": "RELEASE"}, 130, 100, 100),
    ({"LOT-1001": "HOLD", "LOT-1002": "RELEASE"}, 150, 120, 0),
])
def test_commit_dispositions_scored_exactly(case, dispositions, loss, regret, realised):
    result = score_first_action("synthetic", case, reply("commit", {"dispositions": dispositions}))
    assert result.expected_loss == loss
    assert result.oracle_loss == 30
    assert result.regret == result.regret_with_invalids == regret
    assert result.realised_loss == realised
    assert result.post_inspection_correct is None


@pytest.mark.parametrize("target,loss,regret", [("LOT-1001", 30, 0), ("LOT-1002", 60, 30)])
def test_inspection_score_assumes_optimal_continuation(case, target, loss, regret):
    result = score_first_action("synthetic", case, reply("inspect", {"lot_id": target}))
    assert result.expected_loss == loss
    assert result.regret == regret
    assert result.inspected_lot == target
    assert result.realised_loss is None


def test_invalid_regret_includes_worst_valid_commit_not_only_table_actions(case):
    result = score_first_action("synthetic", case, ModelReply())
    assert result.category == "INVALID_NONE"
    assert result.expected_loss is None
    assert result.regret is None
    assert result.regret_with_invalids == 150 - 30
    assert result.realised_loss is None


def test_argument_error_never_echoes_values_or_validation_inputs():
    value = "sensitive-fixture-marker"
    call = ToolCall(name="inspect", arguments={"lot_id": [value], "hidden_states": {value: "PASS"}})
    with pytest.raises(InvalidArguments) as failure:
        parsed_arguments(call)
    assert str(failure.value) == "Invalid tool arguments."
    assert value not in str(failure.value)
    assert failure.value.__suppress_context__ is True


def test_classifier_and_score_do_not_mutate_inputs(case):
    action = reply("inspect", {"lot_id": "LOT-1001"})
    before = (case.model_dump_json(), action.model_dump_json())
    classify_action(case, action)
    score_first_action("synthetic", case, action)
    assert before == (case.model_dump_json(), action.model_dump_json())


def test_score_episode_keeps_first_action_estimand_and_records_actual_loss(case):
    from beyond_label.sandbox import Sandbox
    action = reply("inspect", {"lot_id": "LOT-1001"})
    sandbox = Sandbox(case)
    sandbox.apply_reply(action)
    sandbox.commit({"LOT-1001": "HOLD", "LOT-1002": "HOLD"})
    result = score_episode("synthetic", case, action, sandbox)
    assert result.expected_loss == 30
    assert result.regret == 0
    assert result.realised_loss == 120
    assert result.post_inspection_correct is True


def test_missing_or_invalid_continuation_never_invents_outcome(case):
    from beyond_label.sandbox import Sandbox
    action = reply("inspect", {"lot_id": "LOT-1001"})
    sandbox = Sandbox(case)
    sandbox.apply_reply(action)
    sandbox.apply_reply(ModelReply())
    result = score_episode("synthetic", case, action, sandbox)
    assert result.category == "INSPECT_1"
    assert result.regret == 0
    assert result.realised_loss is None
    assert result.post_inspection_correct is None


def test_commit_against_inspection_is_recorded_without_rewriting_first_action(case):
    from beyond_label.sandbox import Sandbox
    action = reply("inspect", {"lot_id": "LOT-1001"})
    sandbox = Sandbox(case)
    sandbox.apply_reply(action)
    sandbox.commit({"LOT-1001": "RELEASE", "LOT-1002": "RELEASE"})
    result = score_episode("synthetic", case, action, sandbox)
    assert result.category == "INSPECT_1" and result.regret == 0
    assert result.post_inspection_correct is False
    assert result.realised_loss == 120
