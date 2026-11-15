"""Clean-clone orchestration is mocked; no package installation or network."""
import json
import subprocess
import sys

import pytest

from test_execution_audit import script


reproduce = script("reproduce_offline")


@pytest.mark.parametrize("timeout", [False, True])
def test_driver_removes_credentials_and_records_timeout(tmp_path, monkeypatch, timeout):
    output = tmp_path / "reproduction.json"
    monkeypatch.setattr(sys, "argv", ["reproduce_offline.py", "--output", str(output)])
    monkeypatch.setenv("OPENROUTER_API_KEY", "fixture-value-must-not-enter-child")
    commands = []
    def command(cmd, **kwargs):
        assert "OPENROUTER_API_KEY" not in kwargs["env"]
        assert kwargs["timeout"] == 600
        commands.append(cmd)
        if cmd[:3] == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(cmd, 0, "1" * 40 + "\n", "")
        if timeout and "pytest" in cmd:
            raise subprocess.TimeoutExpired(cmd, 600, output="do not save arbitrary timeout output")
        return subprocess.CompletedProcess(cmd, 0, "fixture command passed", "")
    monkeypatch.setattr(reproduce.subprocess, "run", command)
    assert reproduce.main() == (1 if timeout else 0)
    record = json.loads(output.read_text("utf-8"))
    assert record["passed"] is not timeout
    assert record["child_credentials_removed"] is True
    assert record["subprocess_timeout_seconds"] == 600
    if timeout:
        assert record["checks"][-1]["timed_out"] is True
        assert record["checks"][-1]["exit_code"] is None
        assert len(commands) == 3
    assert "fixture-value" not in output.read_text("utf-8")
    assert "arbitrary timeout output" not in output.read_text("utf-8")
