"""T4: counterfactual secret changes must never affect the visible prefix."""

import json

import pytest
from pydantic import ValidationError

from beyond_label.generate import generate_worlds, make_case
from beyond_label.render import RenderError, decision_request, readback_request
from beyond_label.schemas import PublicCase


@pytest.mark.parametrize("dataset", ["pilot", "smoke", "main"])
def test_research_fields_and_hidden_state_are_never_serialized(dataset):
    forbidden = {"world_id", "seed", "draws", "hidden_states", "oracle_loss", "expected_readback", "current_state"}
    for world in generate_worlds(dataset):
        for load in (2, 8):
            for layout in ("separate", "inline"):
                for condition in ("MAIN", "HIGH-FEE", "HIGH-STAKES", "MASKED", "NUMERIC"):
                    for twin in ("a", "b"):
                        case = make_case(world, twin=twin, load=load, layout=layout, condition=condition)
                        altered = case.model_copy(update={
                            "seed": -999999, "world_id": "private-world-sentinel",
                            "hidden_states": {"private-state-sentinel": "hidden-answer-sentinel"},
                        })
                        decision = decision_request(case).model_dump_json()
                        probe = readback_request(case).model_dump_json()
                        assert decision_request(altered).model_dump_json() == decision
                        assert readback_request(altered).model_dump_json() == probe
                        assert all(f'"{key}"' not in decision and f'"{key}"' not in probe for key in forbidden)
                        assert "private-" not in decision and "hidden-answer" not in decision
                        for draw in world.draws:
                            assert repr(draw) not in decision and repr(draw) not in probe
                        assert world.world_id not in decision
                        if condition != "NUMERIC":
                            assert "Expected points lost for each first action:" not in decision
                        assert all("current_state" not in message for message in json.loads(decision)["messages"])


def test_public_schema_rejects_research_state_and_does_not_echo_it():
    public = make_case(generate_worlds("pilot")[0]).public
    data = public.model_dump()
    data["hidden_states"] = {"secret": "private-sentinel"}
    with pytest.raises(ValidationError) as exc:
        PublicCase.model_validate(data)
    assert "private-sentinel" not in str(exc.value)


def test_renderer_error_does_not_log_research_envelope(caplog, capsys):
    case = make_case(generate_worlds("pilot")[0])
    invalid_public = case.public.model_copy(update={"metadata_order": ("private-sentinel",)})
    altered = case.model_copy(update={"public": invalid_public, "hidden_states": {"private": "secret"}})
    with pytest.raises(RenderError) as exc:
        decision_request(altered)
    assert str(exc.value) == "Invalid public case"
    assert "private" not in caplog.text
    assert capsys.readouterr().out == ""
