"""Select the approved composite main only after read-only provenance checks."""
from __future__ import annotations

from pathlib import Path


CHILD = "continuations/staged_main_52_20261116"
PARENT = "runs/staged_main"


def continuation_evidence(root: Path) -> dict | None:
    """No child means ordinary inventory; a present child must validate fully.

The composite contains the original journal prefix. It replaces the parent in
counts, while the parent remains a separately reported immutable snapshot.
No inference, cost reconciliation writes or live-session lock files occur.
"""
    root = Path(root).resolve()
    child = root / CHILD
    area = root / "continuations"
    for filename in ("manifest.json", "calls.jsonl"):
        for path in area.rglob(filename):
            if path.parent != child:
                raise ValueError("Unrecognized main continuation evidence")
    if not child.exists():
        return None
    if child.is_symlink() or not child.resolve().is_relative_to(root):
        raise ValueError("Main continuation must remain inside the repository")
    from execute_main_continuation import verify_child_metadata, verify_operational_freeze

    operational = verify_operational_freeze(root, require_remote=False)
    stored = verify_child_metadata(root, record=operational)
    from main_continuation_accounting import reconcile_readonly
    accounting = reconcile_readonly(root)
    if accounting.get("source_directory") != CHILD:
        raise ValueError("Main continuation accounting selected a different source")
    return {"directory": CHILD, "parent_directory": PARENT,
            "operational_freeze": operational, "metadata": stored["continuation"], "accounting": accounting}
