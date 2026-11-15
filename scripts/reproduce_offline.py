"""Check a clean local clone without network or package installation.

Uses the installed, separately fingerprinted environment. This is a clean-code
reproduction, not a fresh dependency installation or an empirical rerun.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


SUBPROCESS_TIMEOUT_SECONDS = 600
CREDENTIAL_NAMES = ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ADAPTION_API_KEY")


def _child_environment(clone: Path) -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if key not in CREDENTIAL_NAMES}
    environment.update(PYTHONPATH=str(clone / "src"), GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0")
    return environment


def _command(command: list[str], cwd: Path, environment: dict[str, str]) -> dict:
    try:
        completed = subprocess.run(command, cwd=cwd, env=environment, capture_output=True,
                                   text=True, timeout=SUBPROCESS_TIMEOUT_SECONDS)
        return {"command": command, "exit_code": completed.returncode,
                "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip(), "timed_out": False}
    except subprocess.TimeoutExpired:
        # Do not serialize exception text or partial output; a failed check is
        # retained even when the test command never returns a process result.
        return {"command": command, "exit_code": None, "stdout": "", "stderr": "",
                "timed_out": True, "error_class": "TimeoutExpired"}


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=Path("research/checks/env_clean_clone.json"))
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    head_result = _command(["git", "rev-parse", "HEAD"], root, _child_environment(root))
    head = head_result["stdout"] if head_result["exit_code"] == 0 else None
    checks=[]
    if head is None:
        checks.append(head_result)
    else:
        with tempfile.TemporaryDirectory(prefix="btl-offline-clone-") as directory:
            clone=Path(directory)/"repo"
            commands=[
                (["git","-c","core.autocrlf=true","clone","--local","--no-hardlinks",str(root),str(clone)],root),
                ([sys.executable,"-m","pytest","-q"],clone),
                ([sys.executable,"scripts/verify_audit.py"],clone),
                (["git","diff","--exit-code"],clone),
            ]
            for cmd,cwd in commands:
                result = _command(cmd, cwd, _child_environment(clone))
                checks.append(result)
                if result["exit_code"] != 0:
                    break
    record={"classification":"offline_code_reproduction_not_empirical_execution","commit":head,
            "recorded_at_utc":datetime.now(timezone.utc).isoformat(),"network_used":False,
            "fresh_dependency_install":False,"same_host_environment":True,"checks":checks,
            "child_credentials_removed":True,"subprocess_timeout_seconds":SUBPROCESS_TIMEOUT_SECONDS,
            "passed":head is not None and all(c["exit_code"]==0 for c in checks) and len(checks)==4}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({"passed":record["passed"],"commit":head,"checks":len(checks),"fresh_dependency_install":False}))
    return 0 if record["passed"] else 1


if __name__=="__main__":
    raise SystemExit(main())
