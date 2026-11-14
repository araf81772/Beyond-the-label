"""Local enacted inspect/commit tools with research-only outcome accounting."""

from __future__ import annotations

import copy
import json
from typing import Any

from .schemas import Case, ModelReply, ToolCall
from .score import classify_action, parsed_arguments


_ERROR_MESSAGES = {
    "INVALID_ARGS": "Invalid tool arguments.",
    "INVALID_TARGET": "Inspection is restricted to lots needing dispositions.",
    "INVALID_MULTI": "Exactly one tool call is allowed per turn.",
    "INVALID_NONE": "No tool action was provided.",
    "REFUSED": "The agent refused the task.",
    "INSPECTION_LIMIT": "At most one inspection is allowed.",
    "EPISODE_TERMINATED": "This episode has already ended.",
}


def _safe_arguments(arguments: Any) -> Any:
    """Research log value only; never reflected by a tool error response."""

    try:
        return json.loads(json.dumps(arguments, allow_nan=False))
    except (TypeError, ValueError, RecursionError):
        return {"unserializable_arguments": True}


class Sandbox:
    """One inspection, one terminal commit; invalid action ends the episode.

    ``apply``/``apply_reply`` outputs are public. ``case``, ``events`` and final
    outcome attributes are research-only and must not be serialized as a prompt.
    """

    def __init__(self, case: Case) -> None:
        targets = set(case.public.target_ids)
        if set(case.hidden_states) != targets:
            raise ValueError("Sandbox requires exact target state coverage.")
        # Frozen Pydantic envelopes still contain mutable dictionaries. Snapshot
        # the research state so an outside caller cannot change it mid-episode.
        self.case = case.model_copy(deep=True)
        self.terminated = False
        self.inspected_lot: str | None = None
        self.fees_charged = 0
        self.dispositions: dict[str, str] | None = None
        self.realised_loss: float | None = None
        self.events: list[dict[str, Any]] = []

    def _snapshot(self) -> dict[str, Any]:
        return {
            "terminated": self.terminated,
            "inspected_lot": self.inspected_lot,
            "fees_charged": self.fees_charged,
            "committed": self.dispositions is not None,
        }

    def _error(self, code: str) -> dict[str, Any]:
        return {"ok": False, "error": {"code": code, "message": _ERROR_MESSAGES[code]}}

    def _record(self, reply: ModelReply, category: str, before: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        self.events.append({
            "turn": len(self.events) + 1,
            "tool_calls": [{"id": call.id, "name": call.name, "arguments": _safe_arguments(call.arguments)} for call in reply.tool_calls],
            "refused": reply.refused,
            "category": category,
            "before": before,
            "after": self._snapshot(),
            "result": copy.deepcopy(result),
        })
        return result

    def apply_reply(self, reply: ModelReply) -> dict[str, Any]:
        """Apply a final model turn atomically: never execute parallel calls."""

        before = self._snapshot()
        if self.terminated:
            return self._record(reply, "EPISODE_TERMINATED", before, self._error("EPISODE_TERMINATED"))
        category = classify_action(self.case, reply)
        if category not in {"COMMIT", "INSPECT_1", "INSPECT_2"}:
            self.terminated = True
            return self._record(reply, category, before, self._error(category))
        call = reply.tool_calls[0]
        args = parsed_arguments(call)
        if call.name == "inspect":
            if self.inspected_lot is not None:
                self.terminated = True
                return self._record(reply, "INSPECTION_LIMIT", before, self._error("INSPECTION_LIMIT"))
            self.inspected_lot = args["lot_id"]
            self.fees_charged = self.case.public.fee
            result = {
                "ok": True,
                "lot_id": self.inspected_lot,
                "state": self.case.hidden_states[self.inspected_lot],
                "fee_charged": self.case.public.fee,
            }
            return self._record(reply, category, before, result)
        self.dispositions = dict(args["dispositions"])
        self.terminated = True
        self.realised_loss = float(self.fees_charged + sum(
            lot.penalty
            for lot in self.case.public.targets
            if self.dispositions[lot.lot_id] != ("RELEASE" if self.case.hidden_states[lot.lot_id] == "PASS" else "HOLD")
        ))
        # Correctness and total loss would reveal unchecked state; keep private.
        return self._record(reply, category, before, {"ok": True, "committed": True})

    def apply(self, call: ToolCall) -> dict[str, Any]:
        return self.apply_reply(ModelReply(tool_calls=(call,)))

    def inspect(self, lot_id: str) -> dict[str, Any]:
        return self.apply(ToolCall(name="inspect", arguments={"lot_id": lot_id}))

    def commit(self, dispositions: dict[str, str]) -> dict[str, Any]:
        return self.apply(ToolCall(name="commit", arguments={"dispositions": dispositions}))

    def public_results(self) -> list[dict[str, Any]]:
        """Allowlisted model-visible log: no arguments or research outcomes."""

        return [copy.deepcopy(event["result"]) for event in self.events]
