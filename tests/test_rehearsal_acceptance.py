"""Completed terminal failures must not pass the deterministic rehearsal."""
from pathlib import Path
import runpy

import pytest

validate = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/rehearse_offline.py"))["validate_fixture_result"]


def fixture_result():
    return {"completed_cells": 2, "pending_cells": 0,
            "first_action_or_readback_missing": 0, "invalid_first_actions": 0,
            "successful_calls": 3, "continuations": 1,
            "infrastructure_retries": 0, "permitted_reprompts": 0,
            "cells": [{"continuation_status": "not_applicable"},
                      {"continuation_status": "committed"}]}


PLAN = {"initial_calls": 2, "maximum_planned_calls": 3, "maximum_continuations": 1}


@pytest.mark.parametrize("field,value", [
    ("first_action_or_readback_missing", 1), ("invalid_first_actions", 1),
    ("successful_calls", 2), ("continuations", 0), ("pending_cells", 1),
    ("infrastructure_retries", 1), ("permitted_reprompts", 1),
])
def test_completed_but_defective_fixture_fails_acceptance(field, value):
    result = fixture_result()
    result[field] = value
    with pytest.raises(ValueError):
        validate(result, PLAN)


@pytest.mark.parametrize("status", ["missing:timeout", "invalid:INVALID_NONE", "not_started"])
def test_completed_but_defective_continuation_fails_acceptance(status):
    result = fixture_result()
    result["cells"][1]["continuation_status"] = status
    with pytest.raises(ValueError):
        validate(result, PLAN)


def test_successful_fixed_fixture_passes_acceptance():
    assert validate(fixture_result(), PLAN) is None
