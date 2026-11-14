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


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=Path("research/checks/env_clean_clone.json"))
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    head=subprocess.run(["git","rev-parse","HEAD"],cwd=root,capture_output=True,text=True,check=True).stdout.strip()
    checks=[]
    with tempfile.TemporaryDirectory(prefix="btl-offline-clone-") as directory:
        clone=Path(directory)/"repo"
        commands=[
            (["git","-c","core.autocrlf=true","clone","--local","--no-hardlinks",str(root),str(clone)],root),
            ([sys.executable,"-m","pytest","-q"],clone),
            ([sys.executable,"scripts/verify_audit.py"],clone),
            (["git","diff","--exit-code"],clone),
        ]
        for cmd,cwd in commands:
            env=os.environ.copy()
            env["PYTHONPATH"]=str(clone/"src")
            p=subprocess.run(cmd,cwd=cwd,env=env,capture_output=True,text=True,timeout=240)
            checks.append({"command":cmd,"exit_code":p.returncode,"stdout":p.stdout.strip(),"stderr":p.stderr.strip()})
            if p.returncode:
                break
    record={"classification":"offline_code_reproduction_not_empirical_execution","commit":head,
            "recorded_at_utc":datetime.now(timezone.utc).isoformat(),"network_used":False,
            "fresh_dependency_install":False,"same_host_environment":True,"checks":checks,
            "passed":all(c["exit_code"]==0 for c in checks) and len(checks)==4}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({"passed":record["passed"],"commit":head,"checks":len(checks),"fresh_dependency_install":False}))
    return 0 if record["passed"] else 1


if __name__=="__main__":
    raise SystemExit(main())
