"""Prepare the remaining 79 smoke cells offline; this script cannot dispatch."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from beyond_label import continuation79
from beyond_label.continuation import ContinuationError, PAID_SMOKE_DIRECTORY, SEGMENT_DIRECTORY
from beyond_label.run import _inputs
from replay_history import replay_historical


def prepare_smoke79(root: Path, *, source_commit: str) -> dict:
    """Write one new research record only after both collection sources replay."""
    root = Path(root).resolve()
    target = root / continuation79.RECORD_PATH
    if target.resolve() != target:
        raise ContinuationError("continuation79_record_path_invalid")
    if target.exists() or continuation79.segment_path(root).exists():
        raise ContinuationError("continuation79_already_prepared_or_started")
    proofs = {directory: replay_historical(root, root / directory)
              for directory in (PAID_SMOKE_DIRECTORY, SEGMENT_DIRECTORY)}
    record = continuation79.build_continuation79_record(root, source_commit=source_commit,
                                                       input_hashes=_inputs(), replay_proofs=proofs)
    # Exclusive creation makes repeated preparation fail without overwriting
    # either metadata or any execution evidence. No run directory is created.
    with target.open("xb") as handle:
        handle.write((json.dumps(record, indent=2, allow_nan=False) + "\n").encode("utf-8"))
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True, help="Exact tested 40-character committed source")
    args = parser.parse_args()
    record = prepare_smoke79(ROOT, source_commit=args.source_commit)
    print(json.dumps({"classification": record["classification"], "record": continuation79.RECORD_PATH,
                      "record_hash": record["record_hash"], "active_source_commit": record["active_source_commit"],
                      "unique_planned_cells":80, "retained_terminal_cells":1, "dispatchable_cells":79,
                      "execution_started":False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
