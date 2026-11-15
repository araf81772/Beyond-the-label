"""The audit must notice a staged ledger that lost its last settlement line.

Uses read-only temporary copies of the retained staged ledger and journals; no
network, no credentials and no write to the retained session.
"""
import importlib.util
from pathlib import Path
import shutil

import pytest

from beyond_label.gates import STAGED_SESSION, STAGED_STAGES

REPOSITORY = Path(__file__).resolve().parents[1]


def _audit():
    path = REPOSITORY / "scripts" / "verify_audit.py"
    spec = importlib.util.spec_from_file_location("verify_audit_staged_ledger", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _copy(root: Path) -> Path:
    if not (REPOSITORY / STAGED_SESSION / "budget.jsonl").is_file():
        pytest.skip("no retained staged session in this checkout")
    for relative in [STAGED_SESSION, *(value[2] for value in STAGED_STAGES.values())]:
        if (REPOSITORY / relative).is_dir():
            shutil.copytree(REPOSITORY / relative, root / relative,
                            ignore=shutil.ignore_patterns("*.writer.lock"))
    return root


def test_retained_staged_ledger_matches_journals(tmp_path):
    result = _audit().validate_staged_ledger(_copy(tmp_path))
    assert result["journaled_attempts"] == result["known_receipts"] + result["held_reservations"]


def test_lost_final_settlement_line_fails_the_audit(tmp_path):
    root = _copy(tmp_path)
    ledger = root / STAGED_SESSION / "budget.jsonl"
    lines = ledger.read_bytes().splitlines(keepends=True)
    ledger.write_bytes(b"".join(lines[:-1]))
    with pytest.raises(ValueError, match="Staged ledger disagrees"):
        _audit().validate_staged_ledger(root)


def test_staged_runs_without_a_ledger_fail_the_audit(tmp_path):
    root = _copy(tmp_path)
    shutil.rmtree(root / STAGED_SESSION)
    with pytest.raises(ValueError, match="without its shared ledger"):
        _audit().validate_staged_ledger(root)
