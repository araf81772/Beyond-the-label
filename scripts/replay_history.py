"""Verify an immutable historical run with its exact committed source, offline.

This is archival reproduction, never permission to resume with changed inputs.
Only a separately recorded run/source binding can select a historical version.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ("manifest.json", "calls.jsonl", "scores.csv", "usage.csv", "analysis_manifest.json")
CREDENTIALS = ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ADAPTION_API_KEY")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Historical evidence has duplicate fields")
        result[key] = value
    return result


def _read_json(data: bytes):
    return json.loads(data, object_pairs_hook=_unique)


def _allowed_input(name: str) -> bool:
    if not isinstance(name, str) or "\\" in name or ":" in name:
        return False
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return False
    return bool(re.fullmatch(
        r"(?:src/beyond_label/[A-Za-z0-9_]+\.py|prompts/[A-Za-z0-9_]+\.txt|"
        r"configs/[A-Za-z0-9_]+\.yaml|data/worlds_[A-Za-z0-9_]+\.jsonl|"
        r"research/(?:protocol|amendments)\.md|data/manifest\.json|pyproject\.toml|requirements\.lock)", name))


def _child_environment(snapshot: Path) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in CREDENTIALS}
    env.update(PYTHONPATH=str(snapshot / "src"), PYTHONDONTWRITEBYTECODE="1",
               GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0")
    return env


def _git_blob(root: Path, commit: str, name: str) -> bytes:
    completed = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=root,
                               env=_child_environment(root), capture_output=True, timeout=30)
    if completed.returncode:
        raise ValueError("Historical source blob is unavailable locally")
    return completed.stdout


def _git_source_paths(root: Path, commit: str) -> set[str]:
    completed = subprocess.run(["git", "ls-tree", "-r", "--name-only", commit], cwd=root,
                               env=_child_environment(root), capture_output=True, timeout=30)
    if completed.returncode:
        raise ValueError("Historical source tree is unavailable locally")
    return {name for name in completed.stdout.decode("utf-8").splitlines() if _allowed_input(name)}


def replay_historical(root: Path, run_dir: Path) -> dict:
    root, run_dir = Path(root).resolve(), Path(run_dir).resolve()
    if not run_dir.is_relative_to(root / "runs"):
        raise ValueError("Historical run must remain inside repository runs")
    index_path = root / "research/run_sources.json"
    if not index_path.is_file():
        raise ValueError("Historical run/source binding is missing")
    index = _read_json(index_path.read_bytes())
    relative = run_dir.relative_to(root).as_posix()
    if not isinstance(index, dict) or not isinstance(index.get("runs"), dict):
        raise ValueError("Historical run/source binding is missing or invalid")
    record = index["runs"].get(relative)
    if type(index.get("schema_version")) is not int or index["schema_version"] != 1 or not isinstance(record, dict):
        raise ValueError("Historical run/source binding is missing or invalid")
    commit = record.get("source_commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Historical source must name one exact commit")
    hashes = record.get("files")
    if not isinstance(hashes, dict) or set(hashes) != set(FILES):
        raise ValueError("Historical run binding requires all five file hashes")
    if any(not (run_dir / name).is_file() or (run_dir / name).resolve().parent != run_dir for name in FILES):
        raise ValueError("Historical run files are missing or escape the run")
    raw = {name: (run_dir / name).read_bytes() for name in FILES}
    if any(_sha(raw[name]) != hashes[name] for name in FILES):
        raise ValueError("Historical run bytes changed")
    manifest = _read_json(raw["manifest.json"])
    inputs = manifest.get("run_config", {}).get("input_hashes")
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError("Historical input hashes are missing")
    if any(not _allowed_input(name) or not isinstance(digest, str)
           or not re.fullmatch(r"[0-9a-f]{64}", digest) for name, digest in inputs.items()):
        raise ValueError("Historical source path or digest is invalid")
    if set(inputs) != _git_source_paths(root, commit):
        raise ValueError("Historical input set differs from the committed source tree")
    # Every executable source blob must agree with the original manifest before
    # any snapshot code is run. Git objects are read locally with lazy fetch off.
    blobs = {name: _git_blob(root, commit, name) for name in inputs}
    if any(_sha(blobs[name]) != digest for name, digest in inputs.items()):
        raise ValueError("Historical commit does not match collected input hashes")
    with tempfile.TemporaryDirectory(prefix="btl-source-replay-") as temporary:
        snapshot = Path(temporary).resolve()
        for name, content in blobs.items():
            target = (snapshot / name).resolve()
            if not target.is_relative_to(snapshot):
                raise ValueError("Historical source escapes temporary snapshot")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        replay = snapshot / "retained_run"
        replay.mkdir()
        for name in ("manifest.json", "calls.jsonl"):
            (replay / name).write_bytes(raw[name])
        program = """
import socket
from pathlib import Path
def forbidden(*args, **kwargs):
    raise RuntimeError('Network forbidden during historical replay')
socket.socket.connect = forbidden
socket.create_connection = forbidden
from beyond_label import environment
environment.ENV_PATH = Path('absent-credentials.env')
from beyond_label.run import rebuild_outputs
rebuild_outputs(Path('retained_run'))
"""
        child = subprocess.run([sys.executable, "-c", program], cwd=snapshot,
                               env=_child_environment(snapshot), capture_output=True, timeout=120)
        if child.returncode:
            # Do not serialize arbitrary old-code output or exception contexts.
            raise ValueError("Historical source replay failed")
        if any((replay / name).read_bytes() != raw[name] for name in FILES):
            raise ValueError("Historical outputs disagree with retained raw-journal replay")
        summary = _read_json((replay / "analysis_manifest.json").read_bytes())
    if any((run_dir / name).read_bytes() != content for name, content in raw.items()):
        raise ValueError("Original historical evidence changed during replay")
    return {"summary": summary, "source_commit": commit, "input_hashes_verified": len(inputs),
            "original_files_unchanged": True, "network_blocked": True,
            "credentials_removed": True, "raw_trace_sha256": hashes["calls.jsonl"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    result = replay_historical(ROOT, args.run)
    print(json.dumps({key: value for key, value in result.items() if key != "summary"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
