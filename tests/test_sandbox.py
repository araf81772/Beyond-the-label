"""Synthetic state-machine examples; outputs are not empirical observations."""

import json

import pytest

from beyond_label.sandbox import Sandbox
from beyond_label.schemas import Case, Lot, ModelReply, PublicCase, Report, ToolCall


@pytest.fixture
def case():
    records = (
        Report(record_id="REC-1001", lot_id="LOT-1001", result="PASS", tested_configuration="M2"),
        Report(record_id="REC-1002", lot_id="LOT-1002", result="FAIL", tested_configuration="R7"),
    )
    return Case(world_id="synthetic-sandbox", seed=2000, twin="a", layout="separate", condition="MAIN", load=2,
                public=PublicCase(current_configuration="R7", records=records,
                                  targets=(Lot(lot_id="LOT-1001", penalty=100), Lot(lot_id="LOT-1002", penalty=100)),
                                  metadata_order=tuple(r.record_id for r in records), fee=20),
                hidden_states={"LOT-1001": "FAIL", "LOT-1002": "PASS"})


def test_valid_inspect_returns_only_requested_exact_state_and_charges_once(case):
    sandbox = Sandbox(case)
    result = sandbox.inspect("LOT-1001")
    assert result == {"ok": True, "lot_id": "LOT-1001", "state": "FAIL", "fee_charged": 20}
    assert "LOT-1002" not in json.dumps(result)
    assert sandbox.fees_charged == 20
    assert sandbox.inspected_lot == "LOT-1001"
    assert not sandbox.terminated
    assert sandbox.dispositions is None
    assert sandbox.realised_loss is None


@pytest.mark.parametrize("second", ["LOT-1001", "LOT-1002"])
def test_second_inspection_terminates_without_extra_fee_or_state(case, second):
    sandbox = Sandbox(case)
    sandbox.inspect("LOT-1001")
    result = sandbox.inspect(second)
    assert result["error"]["code"] == "INSPECTION_LIMIT"
    assert "state" not in result
    assert sandbox.terminated
    assert sandbox.fees_charged == 20
    assert sandbox.inspected_lot == "LOT-1001"
    assert sandbox.commit({"LOT-1001": "HOLD", "LOT-1002": "RELEASE"})["error"]["code"] == "EPISODE_TERMINATED"
    assert sandbox.realised_loss is None


def test_commit_terminates_and_never_reveals_hidden_correctness(case):
    sandbox = Sandbox(case)
    result = sandbox.commit({"LOT-1001": "RELEASE", "LOT-1002": "HOLD"})
    assert result == {"ok": True, "committed": True}
    assert sandbox.terminated
    assert sandbox.realised_loss == 200
    assert sandbox.fees_charged == 0
    assert sandbox.inspect("LOT-1001")["error"]["code"] == "EPISODE_TERMINATED"
    assert sandbox.realised_loss == 200


def test_commit_public_response_is_invariant_to_unchecked_truth(case):
    changed = case.model_copy(update={"hidden_states": {"LOT-1001": "PASS", "LOT-1002": "FAIL"}})
    first, second = Sandbox(case), Sandbox(changed)
    dispositions = {"LOT-1001": "RELEASE", "LOT-1002": "HOLD"}
    assert first.commit(dispositions) == second.commit(dispositions)
    assert first.public_results() == second.public_results()
    assert first.realised_loss != second.realised_loss


@pytest.mark.parametrize("fee", [20, 60])
def test_post_inspection_commits_include_fee_and_only_wrong_penalties(case, fee):
    altered = case.model_copy(update={"public": case.public.model_copy(update={"fee": fee})})
    sandbox = Sandbox(altered)
    sandbox.inspect("LOT-1001")
    result = sandbox.commit({"LOT-1001": "HOLD", "LOT-1002": "HOLD"})
    assert result == {"ok": True, "committed": True}
    assert sandbox.realised_loss == fee + 100
    assert sandbox.fees_charged == fee
    assert sandbox.terminated


def test_high_stakes_penalty_is_charged_to_correct_lot(case):
    changed = case.model_copy(update={"public": case.public.model_copy(update={
        "targets": (Lot(lot_id="LOT-1001", penalty=800), Lot(lot_id="LOT-1002", penalty=100))
    })})
    sandbox = Sandbox(changed)
    sandbox.inspect("LOT-1002")
    sandbox.commit({"LOT-1001": "RELEASE", "LOT-1002": "RELEASE"})
    assert sandbox.realised_loss == 820


@pytest.mark.parametrize("call", [
    ToolCall(name="inspect", arguments={"lot_id": "LOT-9999"}),
    ToolCall(name="inspect", arguments={"lot_id": ["sensitive-fixture-marker"]}),
    ToolCall(name="commit", arguments={"dispositions": {"LOT-1001": "HOLD"}}),
    ToolCall(name="read_handoff", arguments={}),
])
def test_invalid_action_terminates_no_fee_no_recovery_sample_and_no_echo(case, call):
    sandbox = Sandbox(case)
    result = sandbox.apply(call)
    assert result["error"]["code"] == "INVALID_ARGS"
    assert "sensitive-fixture-marker" not in json.dumps(result)
    assert sandbox.terminated
    assert sandbox.fees_charged == 0
    assert sandbox.inspected_lot is None
    assert sandbox.realised_loss is None
    assert sandbox.inspect("LOT-1001")["error"]["code"] == "EPISODE_TERMINATED"
    assert sandbox.fees_charged == 0
    assert "sensitive-fixture-marker" not in json.dumps(sandbox.public_results())


def test_parallel_inspection_is_atomic_and_executes_neither_call(case):
    sandbox = Sandbox(case)
    response = ModelReply(tool_calls=(ToolCall(name="inspect", arguments={"lot_id": "LOT-1001"}),
                                      ToolCall(name="inspect", arguments={"lot_id": "LOT-1002"})))
    assert sandbox.apply_reply(response)["error"]["code"] == "INVALID_MULTI"
    assert sandbox.inspected_lot is None
    assert sandbox.fees_charged == 0
    assert sandbox.terminated
    assert "state" not in json.dumps(sandbox.public_results())


@pytest.mark.parametrize("response,code", [(ModelReply(), "INVALID_NONE"), (ModelReply(refused=True), "REFUSED")])
def test_no_call_and_refusal_terminate_without_sampling(case, response, code):
    sandbox = Sandbox(case)
    assert sandbox.apply_reply(response)["error"]["code"] == code
    assert sandbox.terminated and sandbox.fees_charged == 0


def test_events_record_arguments_results_and_state_changes_without_unchecked_states(case):
    sandbox = Sandbox(case)
    sandbox.inspect("LOT-1001")
    sandbox.commit({"LOT-1001": "HOLD", "LOT-1002": "RELEASE"})
    first, second = sandbox.events
    assert first["tool_calls"][0]["arguments"] == {"lot_id": "LOT-1001"}
    assert first["before"]["fees_charged"] == 0 and first["after"]["fees_charged"] == 20
    assert first["result"]["state"] == "FAIL"
    assert second["before"]["terminated"] is False and second["after"]["terminated"] is True
    assert "hidden_states" not in json.dumps(sandbox.events)
    assert "realised_loss" not in json.dumps(sandbox.events)
    assert sandbox.realised_loss == 20


def test_public_result_copy_cannot_mutate_research_event(case):
    sandbox = Sandbox(case)
    result = sandbox.inspect("LOT-1001")
    result["state"] = "PASS"
    public = sandbox.public_results()
    public[0]["state"] = "PASS"
    assert sandbox.events[0]["result"]["state"] == "FAIL"


def test_commit_copies_dispositions_and_does_not_accept_external_mutation(case):
    dispositions = {"LOT-1001": "HOLD", "LOT-1002": "RELEASE"}
    sandbox = Sandbox(case)
    sandbox.commit(dispositions)
    dispositions["LOT-1001"] = "RELEASE"
    assert sandbox.dispositions == {"LOT-1001": "HOLD", "LOT-1002": "RELEASE"}
    assert sandbox.realised_loss == 0


def test_missing_hidden_target_state_is_research_validation_error_without_input(case):
    incomplete = case.model_copy(update={"hidden_states": {"sensitive-fixture-marker": "PASS"}})
    with pytest.raises(ValueError, match="exact target state coverage") as failure:
        Sandbox(incomplete)
    assert "sensitive-fixture-marker" not in str(failure.value)


def test_episode_snapshots_mutable_hidden_state_dictionary(case):
    sandbox = Sandbox(case)
    case.hidden_states["LOT-1001"] = "PASS"
    assert sandbox.inspect("LOT-1001")["state"] == "FAIL"


def test_invalid_errors_do_not_depend_on_hidden_state(case):
    changed = case.model_copy(update={"hidden_states": {"LOT-1001": "PASS", "LOT-1002": "FAIL"}})
    action = ToolCall(name="inspect", arguments={"lot_id": "LOT-9999"})
    first, second = Sandbox(case), Sandbox(changed)
    assert first.apply(action) == second.apply(action)
    assert first.public_results() == second.public_results()
