"""Deterministic public handoffs, model requests, and separate readback branches.

No function serializes the research envelope. NUMERIC is the sole explicit
exception to withholding oracle-like quantities: its three prescribed losses
are derived from public report scope. The user-approved pre-freeze amendment
retains the report facts needed for subsequent dispositions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .schemas import Case, PublicCase, Request

PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"
HANDOFF_CALL_ID = "read_handoff_1"
INITIAL_USER = "Handle today's dispositions. Read the handoff first."


class RenderError(ValueError):
    """Safe fixed-message error; never includes input or research state."""


def prompt_text(name: str) -> str:
    allowed = {
        "agent_system.txt", "probe_readback.txt", "control_masked.txt",
        "control_numeric.txt", "reprompt_no_tool.txt",
    }
    if name not in allowed:
        raise RenderError("Unknown prompt")
    try:
        return (PROMPT_DIR / name).read_text(encoding="utf-8").strip()
    except OSError:
        raise RenderError("Prompt unavailable") from None


def _public(case: Case) -> PublicCase:
    """Validate public references without ever echoing invalid input."""
    try:
        public = case.public
        if len(public.records) != case.load:
            raise ValueError
        record_ids = [record.record_id for record in public.records]
        lot_ids = [record.lot_id for record in public.records]
        if len(set(record_ids)) != len(record_ids) or len(set(lot_ids)) != len(lot_ids):
            raise ValueError
        if list(public.target_ids) != lot_ids[:2]:
            raise ValueError
        if len(public.metadata_order) != len(record_ids) or set(public.metadata_order) != set(record_ids):
            raise ValueError
        if case.layout not in {"separate", "inline"}:
            raise ValueError
        return public
    except (AttributeError, TypeError, ValueError):
        raise RenderError("Invalid public case") from None


def render_handoff(case: Case) -> str:
    public = _public(case)
    records = {record.record_id: record for record in public.records}
    targets = set(public.target_ids)

    def scope(record_id: str) -> str:
        record = records[record_id]
        # Mask again at the last visibility boundary: a research envelope
        # cannot accidentally reveal target scope through a malformed view.
        if case.condition == "MASKED" and record.lot_id in targets:
            return "[withheld]"
        return record.tested_configuration

    lines = ["ARCHIVED REPORTS"]
    for record in public.records:
        row = f"{record.record_id} | {record.lot_id} | result: {record.result}"
        if case.layout == "inline" and case.condition != "NUMERIC":
            row += f" | tested_configuration: {scope(record.record_id)}"
        lines.append(row)
    if case.layout == "separate" and case.condition != "NUMERIC":
        lines.extend(["", "REPORT METADATA"])
        lines.extend(
            f"{record_id} | tested_configuration: {scope(record_id)}"
            for record_id in public.metadata_order
        )
    lines.extend(["", "LOTS TO DISPOSITION"])
    lines.extend(f"{lot.lot_id} | penalty if wrong: {lot.penalty}" for lot in public.targets)

    if case.condition == "NUMERIC":
        # This control supplies precisely the Section 4 MAIN action losses.
        first, second = public.records[:2]
        in_scope = [r.tested_configuration == public.current_configuration for r in (first, second)]
        if sum(in_scope) != 1 or public.fee != 20 or any(lot.penalty != 100 for lot in public.targets):
            raise RenderError("Invalid NUMERIC public case")
        x, y = (60, 30) if in_scope[0] else (30, 60)
        lines.extend(["", prompt_text("control_numeric.txt").format(
            LOT_1=public.target_ids[0], LOT_2=public.target_ids[1], x=x, y=y,
        )])
    return "\n".join(lines)


def _tools(public: PublicCase) -> list[dict[str, Any]]:
    lot_ids = list(public.target_ids)
    disposition_properties = {
        lot_id: {"type": "string", "enum": ["RELEASE", "HOLD"]}
        for lot_id in lot_ids
    }
    return [
        {
            "type": "function",
            "function": {
                "name": "inspect",
                "description": "Inspect one target lot's exact current state. At most once; the stated inspection fee is charged.",
                "strict": True,
                "parameters": {
                    "type": "object", "properties": {"lot_id": {"type": "string", "enum": lot_ids}},
                    "required": ["lot_id"], "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "commit",
                "description": "Record a disposition for both target lots and end the episode.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {"dispositions": {
                        "type": "object", "properties": disposition_properties,
                        "required": lot_ids, "additionalProperties": False,
                    }},
                    "required": ["dispositions"], "additionalProperties": False,
                },
            },
        },
    ]


def decision_request(case: Case) -> Request:
    public = _public(case)
    system = prompt_text("agent_system.txt").format(CURRENT=public.current_configuration, FEE=public.fee)
    if case.condition == "MASKED":
        system += "\n\n" + prompt_text("control_masked.txt")
    return Request(messages=[
        {"role": "system", "content": system},
        {"role": "user", "content": INITIAL_USER},
        {"role": "assistant", "content": None, "tool_calls": [{
            "id": HANDOFF_CALL_ID, "type": "function",
            "function": {"name": "read_handoff", "arguments": "{}"},
        }]},
        {"role": "tool", "tool_call_id": HANDOFF_CALL_ID, "content": render_handoff(case)},
    ], tools=_tools(public), tool_choice="auto", parallel_tool_calls=False)


def readback_request(case: Case) -> Request:
    # Rebuild a fresh prefix rather than mutating or branching a used decision.
    prefix = decision_request(case).messages
    return Request(
        messages=[*prefix, {"role": "user", "content": prompt_text("probe_readback.txt")}],
        tools=[], tool_choice=None, parallel_tool_calls=False,
    )


def expected_readback(case: Case) -> list[dict[str, Any]]:
    """Research-only scoring answer. Never add this return value to a request."""
    public = _public(case)
    if case.condition == "MASKED":
        raise RenderError("Readback answer unavailable for masked scope")
    reports = {record.lot_id: record for record in public.records}
    return [
        {"lot_id": lot_id, "tested_configuration": reports[lot_id].tested_configuration,
         "matches_current": reports[lot_id].tested_configuration == public.current_configuration}
        for lot_id in public.target_ids
    ]
