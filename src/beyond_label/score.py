"""Deterministic first-action and final-episode scoring; no model judge."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from .oracle import action_losses, expected_commit_loss, oracle_loss, worst_valid_loss
from .schemas import Case, Category, CommitArgs, InspectArgs, ModelReply, ScoreRow, ToolCall

if TYPE_CHECKING:
    from .sandbox import Sandbox


class InvalidArguments(ValueError):
    """Input-independent error safe for conversion to a model-visible message."""

    def __init__(self) -> None:
        super().__init__("Invalid tool arguments.")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InvalidArguments()
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise InvalidArguments()


def parsed_arguments(call: ToolCall) -> dict[str, Any]:
    """Parse exactly the advertised tool schema without exposing validation input.

    Duplicate JSON keys are rejected, including nested disposition keys. No
    permissive coercion, ignored extra keys, or exception text is returned.
    """

    try:
        raw = call.arguments
        if isinstance(raw, str):
            raw = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        if type(raw) is not dict:
            raise InvalidArguments()
        if call.name == "inspect":
            return InspectArgs.model_validate(raw, strict=True).model_dump()
        if call.name == "commit":
            return CommitArgs.model_validate(raw, strict=True).model_dump()
        raise InvalidArguments()
    except (ValueError, TypeError, RecursionError, ValidationError):
        raise InvalidArguments() from None


def classify_action(case: Case, reply: ModelReply) -> Category:
    """Classify a final decision reply after any permitted no-tool re-prompt.

    Multiple calls have precedence even if refusal is also marked. An explicit
    provider refusal then takes precedence over a missing or single call.
    This function does not retry, re-prompt, or mutate an episode.
    """

    if len(reply.tool_calls) > 1:
        return "INVALID_MULTI"
    if reply.refused:
        return "REFUSED"
    if not reply.tool_calls:
        return "INVALID_NONE"
    call = reply.tool_calls[0]
    try:
        args = parsed_arguments(call)
    except InvalidArguments:
        return "INVALID_ARGS"
    target_ids = case.public.target_ids
    if call.name == "inspect":
        lot_id = args["lot_id"]
        if lot_id == target_ids[0]:
            return "INSPECT_1"
        if lot_id == target_ids[1]:
            return "INSPECT_2"
        if case.load == 8 and lot_id in {r.lot_id for r in case.public.records}:
            return "INVALID_TARGET"
        return "INVALID_ARGS"
    if set(args["dispositions"]) != set(target_ids):
        return "INVALID_ARGS"
    return "COMMIT"


def _realised_commit_loss(case: Case, dispositions: dict[str, str], fee: int = 0) -> float:
    return float(fee + sum(
        lot.penalty
        for lot in case.public.targets
        if dispositions[lot.lot_id] != ("RELEASE" if case.hidden_states[lot.lot_id] == "PASS" else "HOLD")
    ))


def score_first_action(cell_id: str, case: Case, reply: ModelReply) -> ScoreRow:
    """Research-only score of the chosen first action, not its continuation."""

    category = classify_action(case, reply)
    minimum = oracle_loss(case)
    if category not in {"COMMIT", "INSPECT_1", "INSPECT_2"}:
        return ScoreRow(
            cell_id=cell_id,
            category=category,
            oracle_loss=minimum,
            regret_with_invalids=worst_valid_loss(case) - minimum,
        )
    if category == "COMMIT":
        dispositions = parsed_arguments(reply.tool_calls[0])["dispositions"]
        loss = expected_commit_loss(case, dispositions)
        realised = _realised_commit_loss(case, dispositions)
        inspected_lot = None
    else:
        loss = action_losses(case)[category]
        realised = None
        inspected_lot = case.public.target_ids[0 if category == "INSPECT_1" else 1]
    return ScoreRow(
        cell_id=cell_id,
        category=category,
        expected_loss=loss,
        oracle_loss=minimum,
        regret=loss - minimum,
        regret_with_invalids=loss - minimum,
        realised_loss=realised,
        inspected_lot=inspected_lot,
    )


def score_episode(cell_id: str, case: Case, first_reply: ModelReply, sandbox: Sandbox) -> ScoreRow:
    """Attach actual final outcomes without changing the first-action estimand.

    Failed/missing continuations have no invented dispositions or realised
    outcome. The harness separately records the continuation error/missingness.
    """

    if sandbox.case != case:
        raise ValueError("Sandbox case does not match scoring case.")
    first = score_first_action(cell_id, case, first_reply)
    if sandbox.dispositions is None:
        return first.model_copy(update={"realised_loss": None, "post_inspection_correct": None})
    correct = None
    if sandbox.inspected_lot is not None:
        actual = case.hidden_states[sandbox.inspected_lot]
        correct = sandbox.dispositions[sandbox.inspected_lot] == ("RELEASE" if actual == "PASS" else "HOLD")
    return first.model_copy(update={
        "realised_loss": sandbox.realised_loss,
        "post_inspection_correct": correct,
    })
