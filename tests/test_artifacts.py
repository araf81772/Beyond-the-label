import hashlib
import json
from pathlib import Path
import subprocess


def test_committed_input_artifacts_match_manifest_and_checkout_rules():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "data/manifest.json").read_text("utf-8"))
    for name, entry in manifest["files"].items():
        assert hashlib.sha256((root / "data" / name).read_bytes()).hexdigest() == entry["sha256"]
        result = subprocess.run(["git", "check-attr", "eol", "--", f"data/{name}"], cwd=root,
                                capture_output=True, text=True, check=True)
        assert result.stdout.strip().endswith(": eol: lf")
