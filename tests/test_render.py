"""Rendering, tool-contract and separate readback-branch acceptance checks."""

from copy import deepcopy

import pytest

from beyond_label.generate import generate_world, generate_worlds, make_case
from beyond_label.render import (
    HANDOFF_CALL_ID, INITIAL_USER, RenderError, decision_request,
    expected_readback, prompt_text, readback_request, render_handoff,
)


@pytest.mark.parametrize("layout", ["separate", "inline"])
@pytest.mark.parametrize("load", [2, 8])
def test_exact_conversation_shape_and_tool_contract(layout, load):
    case = make_case(generate_world(2000), layout=layout, load=load)
    request = decision_request(case)
    assert [m["role"] for m in request.messages] == ["system", "user", "assistant", "tool"]
    assert request.messages[1]["content"] == INITIAL_USER
    call = request.messages[2]["tool_calls"][0]
    assert call == {"id": HANDOFF_CALL_ID, "type": "function", "function": {"name": "read_handoff", "arguments": "{}"}}
    assert request.messages[3] == {"role": "tool", "tool_call_id": HANDOFF_CALL_ID, "content": render_handoff(case)}
    assert request.tool_choice == "auto"
    assert request.parallel_tool_calls is False
    functions = {tool["function"]["name"]: tool["function"] for tool in request.tools}
    assert set(functions) == {"inspect", "commit"}
    ids = list(case.public.target_ids)
    assert functions["inspect"]["parameters"]["properties"]["lot_id"]["enum"] == ids
    dispositions = functions["commit"]["parameters"]["properties"]["dispositions"]
    assert dispositions["required"] == ids
    assert dispositions["additionalProperties"] is False
    assert all(prop["enum"] == ["RELEASE", "HOLD"] for prop in dispositions["properties"].values())
    assert all(function["strict"] is True and function["parameters"]["additionalProperties"] is False for function in functions.values())
    assert len([line for line in render_handoff(case).splitlines() if " | result:" in line]) == load


@pytest.mark.parametrize("dataset", ["pilot", "smoke", "main"])
def test_readback_uses_exact_fresh_prefix_without_contaminating_decision(dataset):
    for world in generate_worlds(dataset):
        for load in (2, 8):
            for layout in ("separate", "inline"):
                for twin in ("a", "b"):
                    case = make_case(world, twin=twin, load=load, layout=layout)
                    decision = decision_request(case)
                    before = deepcopy(decision.model_dump())
                    probe = readback_request(case)
                    assert probe.messages[:-1] == decision.messages
                    assert probe.tools == [] and probe.tool_choice is None
                    assert probe.messages[-1] == {"role": "user", "content": prompt_text("probe_readback.txt")}
                    assert all(prompt_text("probe_readback.txt") not in str(message.get("content", "")) for message in decision.messages)
                    assert all("Answer only with JSON:" not in str(message.get("content", "")) for message in decision.messages)
                    probe.messages[0]["content"] = "synthetic mutation"
                    assert decision.model_dump() == before
                    expected = expected_readback(case)
                    assert [row["lot_id"] for row in expected] == list(case.public.target_ids)
                    assert sum(row["matches_current"] for row in expected) == 1


@pytest.mark.parametrize("layout", ["separate", "inline"])
@pytest.mark.parametrize("load", [2, 8])
def test_masked_scope_is_withheld_at_last_boundary(layout, load):
    case = make_case(generate_world(2003), condition="MASKED", layout=layout, load=load)
    handoff = render_handoff(case)
    assert handoff.count("[withheld]") == 2
    assert prompt_text("control_masked.txt") in decision_request(case).messages[0]["content"]
    with pytest.raises(RenderError, match="Readback answer unavailable for masked scope"):
        expected_readback(case)


@pytest.mark.parametrize("twin,expected", [("a", (30, 60)), ("b", (60, 30))])
def test_numeric_amendment_retains_facts_but_no_scope_metadata(twin, expected):
    case = make_case(generate_world(2000), twin=twin, condition="NUMERIC")
    text = render_handoff(case)
    assert "tested_configuration" not in text
    assert "REPORT METADATA" not in text
    assert "LOTS TO DISPOSITION" in text
    for record in case.public.records[:2]:
        assert f"{record.record_id} | {record.lot_id} | result: {record.result}" in text
    assert f"Inspect {case.public.target_ids[0]}, then commit: {expected[0]}." in text
    assert f"Inspect {case.public.target_ids[1]}, then\ncommit: {expected[1]}." in text
    assert text.count("Expected points lost") == 1
    assert "commit now: 50." in text


def test_exact_no_tool_reprompt_and_public_validation_error():
    assert prompt_text("reprompt_no_tool.txt") == "Respond with exactly one tool call."
    case = make_case(generate_world(2000))
    broken_public = case.public.model_copy(update={"metadata_order": ("research-secret-marker",)})
    broken = case.model_copy(update={"public": broken_public})
    with pytest.raises(RenderError) as exc:
        decision_request(broken)
    assert str(exc.value) == "Invalid public case"
    assert "research-secret-marker" not in str(exc.value)
    with pytest.raises(RenderError, match="Unknown prompt"):
        prompt_text("../research/protocol.md")
