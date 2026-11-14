"""Verify source integrity and audit evidence as milestones advance.

Historical M1 absence claims are checked against its retained baseline. Live
status is checked against present files rather than freezing the project at M1.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from beyond_label.environment import CredentialLoadError, load_local_credentials
SOURCE_SHA256 = "f732a0d815ae7f6f42e9eacb4e311b53ed8187abf9e3c48b79c476dfc202838b"


def main() -> int:
    # Load silently so the exact local key is included in leak checks; ignored
    # .env contents are never scanned, printed, hashed or copied into evidence.
    load_local_credentials()
    failures: list[str] = []
    checks: list[str] = []

    def check(condition: bool, name: str) -> None:
        (checks if condition else failures).append(name)

    expected_files = [
        ".gitattributes", ".gitignore", "README.md", "AGENTS.md",
        "research/protocol.md", "research/source_manifest.json",
        "research/audit.md", "research/requirements.csv",
        "research/decisions.md", "research/baseline.json",
        "research/milestones.json", "scripts/verify_audit.py",
    ]
    for relative in expected_files:
        check((ROOT / relative).is_file(), f"artifact exists: {relative}")
    if failures:
        print(json.dumps({"status": "failed", "failures": failures}, indent=2))
        return 1

    provenance = json.loads((ROOT / "research/source_manifest.json").read_text("utf-8"))
    raw = (ROOT / "research/protocol.md").read_bytes()
    check(hashlib.sha256(raw).hexdigest() == SOURCE_SHA256 == provenance["sha256"],
          "authoritative design SHA-256")
    check(len(raw) == 27751 == provenance["size_bytes"], "authoritative design byte count")
    check(len(raw.splitlines()) == 581 == provenance["line_count"], "authoritative design line count")
    check(provenance["archive_path"] == "research/protocol.md", "source archive path")
    check(provenance["execution_freeze"] is False, "source is not an execution freeze")
    attributes = subprocess.run(
        ["git", "check-attr", "text", "--", "research/protocol.md"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()
    check(attributes == "research/protocol.md: text: unset", "source Git byte preservation")

    with (ROOT / "research/requirements.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    ids = [row["id"] for row in rows]
    check(len(ids) == len(set(ids)), "unique requirement IDs")
    check(all(f"T{i}" in ids for i in range(1, 9)), "T1-T8 mapped")
    check(set(row["milestone"] for row in rows) == set("123456"), "all six milestones mapped")
    check(all(row["status"] in {"existing", "missing", "incorrect", "blocked"} for row in rows),
          "explicit requirement status vocabulary")
    check(all(set(row) == {"id", "source", "requirement", "status", "implementation",
                          "acceptance_check", "milestone", "notes"} and all(row.values())
              for row in rows), "complete and well-formed requirement rows")
    for row in rows:
        if row["id"] in {f"T{i}" for i in range(1, 9)} and row["status"] == "existing":
            check((ROOT / row["acceptance_check"]).is_file(), f"implemented test exists: {row['id']}")

    milestones = json.loads((ROOT / "research/milestones.json").read_text("utf-8"))
    check([item["number"] for item in milestones["milestones"]] == list(range(1, 7)),
          "exactly six ordered milestone records")
    for item in milestones["milestones"][1:]:
        if item["status"] == "complete":
            checks_recorded = item.get("validation", [])
            check(bool(checks_recorded) and all(c["exit_code"] == 0 for c in checks_recorded),
                  f"milestone {item['number']} has passing acceptance evidence")
    check(milestones["execution_freeze"] is None, "no invented freeze tag")
    check(milestones["experimental_calls"] == 0, "no invented experimental calls")

    baseline = json.loads((ROOT / "research/baseline.json").read_text("utf-8"))
    check(all(value == "absent; not run or passed" for value in baseline["required_experiment_tests"].values()),
          "historical M1 experiment-test absence preserved")
    check(baseline["pytest_baseline"]["process_exit_code"] == 5,
          "pytest no-tests result recorded as non-passing")
    check(baseline["spending"]["authorized_cap"] is None,
          "planning estimate not spending authorization")
    check(all(isinstance(value, bool) for value in baseline["credential_presence_only"].values()),
          "credential evidence limited to presence booleans")

    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, capture_output=True, check=True,
    )
    paths = sorted(set(p.decode("utf-8") for p in result.stdout.split(b"\0") if p))
    forbidden_names = {".env", "credentials.json", "credentials.yaml"}
    token_patterns = [
        re.compile(rb"sk-(?:or-v1-)?[A-Za-z0-9_-]{20,}"),
        re.compile(rb"(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}"),
        re.compile(rb"Bearer\s+[A-Za-z0-9._-]{15,}", re.IGNORECASE),
        re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ]
    credential_names = ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ADAPTION_API_KEY")
    for relative in paths:
        path = ROOT / relative
        check(path.name not in forbidden_names and not (path.name.startswith(".env.") and path.name != ".env.example"),
              f"no credential file staged or unignored: {relative}")
        if not path.is_file():
            continue
        content = path.read_bytes()
        check(not any(pattern.search(content) for pattern in token_patterns),
              f"no selected credential patterns: {relative}")
        for name in credential_names:
            value = os.environ.get(name)
            if value:
                check(value.encode() not in content, f"no current credential value: {relative}")

    print(json.dumps({
        "status": "failed" if failures else "passed",
        "scope": "audit evidence and source integrity; experiment tests are separately recorded",
        "checks_passed": len(checks), "requirements_mapped": len(rows),
        "files_scanned": len(paths), "source_sha256": SOURCE_SHA256,
        "secret_scan_limit": "Selected token patterns, credential filenames, and checked current environment values; manual diff review also required.",
        "failures": failures,
    }, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, CredentialLoadError, subprocess.CalledProcessError) as exc:
        # Error class only: exception content could contain sensitive file contents.
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}))
        sys.exit(1)
