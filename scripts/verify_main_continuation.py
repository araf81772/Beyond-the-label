"""Verify the stopped main baseline and describe its remaining schedule offline.

This standard-library-only utility never imports the experiment, loads secrets,
creates a ledger/lock, makes requests, reconciles costs or authorizes dispatch.
The retained baseline is intentionally fixed. New main events or control
suffixes invalidate this proposal until separately reviewed; they are never
silently accepted as part of the original 52-cell continuation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = "runs/staged_main"
SESSION = "runs/_paid_staged_session"
COLLECTION_SOURCE = "d007585cff100f4fc6ce61c2b61452d830e3ffe9"
FREEZE_SHA256 = "ab1fa4f553be65df5cf14910e6e8bb0e241f50445be04f5ee300542c27e992db"
FREEZE_RECORD_HASH = "4feb8fd870dc62ffd260b682d1249d6fc70c401d33f98a9a1eb7ce1189ef2081"
AUTHORIZATION_SHA256 = "ec54d9173dedc8fffbfc485b6fb10578eb68aef8fe7cf23a5e02e608a1583e4b"
MAIN_FILES = {
    "manifest.json": (173481, "38a5b1be160756382c43b342d77f88f8ec17f36dc34c3772067a662917f1d859"),
    "calls.jsonl": (17615533, "05d33f55fc30274fd9c20c0574360d7a9446c3665a2b4a6271c44dc233509753"),
    "scores.csv": (95195, "44b5a3f1f15f6e786083aed16c52f7b5bd716583f3eec77c2b52fde181248150"),
    "usage.csv": (322106, "3ecd0beaba57e0ecafb110ce897880e205dcee8aa332d6f7aaafac01a34bfe9c"),
    "analysis_manifest.json": (127132, "206cdd95f56f568be2bbc9c6cc3f5dd20824ce7cf80a388b85bbb6d7bd0b4df3"),
}
CONTROL_PREFIXES = {
    "budget.jsonl": (1047363, "03b85248217ae077341e363b5efc90762431bf1d01de1b26e3d8c31284b0316c", 3123),
    "attempts.jsonl": (346169, "cc7b993a5d6602bf31f05a455bdd975a9f1c2f2b3fa3968fd367dc2531297856", 1562),
}
PENDING = "main-2061-readback-MAIN-inline-b"
TERMINAL = "main-2013-decision-HIGH-STAKES-inline-a"


class ContinuationVerificationError(ValueError):
    """Fixed reason codes; no credentials or arbitrary file contents."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ContinuationVerificationError(reason)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value, *, ascii_only: bool = False) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=ascii_only, allow_nan=False).encode("utf-8")


def _read(root: Path, relative: str) -> bytes:
    path = root / relative
    _require(path.resolve().is_relative_to(root), "evidence_path_outside_root")
    try:
        return path.read_bytes()
    except OSError:
        raise ContinuationVerificationError("required_evidence_unavailable") from None


def _unique(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def _json(raw: bytes):
    try:
        return json.loads(raw, object_pairs_hook=_unique)
    except (ValueError, UnicodeError):
        raise ContinuationVerificationError("invalid_json_evidence") from None


def _chain(raw: bytes, *, ascii_only: bool = False) -> list[dict]:
    _require(bool(raw) and raw.endswith(b"\n"), "incomplete_event_journal")
    events, previous = [], "0" * 64
    for line in raw.splitlines():
        event = _json(line)
        _require(isinstance(event, dict), "invalid_event_chain")
        body = {key: value for key, value in event.items() if key != "event_hash"}
        _require(type(event.get("sequence")) is int and event["sequence"] == len(events) + 1
                 and event.get("previous_hash") == previous
                 and event.get("event_hash") == _sha(_canonical(body, ascii_only=ascii_only)),
                 "invalid_event_chain")
        previous = event["event_hash"]
        events.append(event)
    return events


def _frozen_input_paths(root: Path) -> set[str]:
    files = list((root / "src/beyond_label").glob("*.py"))
    files += list((root / "prompts").glob("*.txt"))
    files += list((root / "configs").glob("*.yaml"))
    files += list((root / "data").glob("worlds_*.jsonl"))
    files += [root / name for name in ("research/protocol.md", "research/amendments.md",
                                      "data/manifest.json", "pyproject.toml", "requirements.lock")]
    return {path.relative_to(root).as_posix() for path in files}


def _text(amount: Decimal) -> str:
    result = format(amount, "f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def verify_continuation(root: Path | str = ROOT) -> dict:
    """Return a bound, blocked proposal; fail closed on any baseline change."""
    root = Path(root).resolve()
    freeze_raw = _read(root, "research/execution_freeze.json")
    _require(_sha(freeze_raw) == FREEZE_SHA256, "execution_freeze_changed")
    freeze = _json(freeze_raw)
    _require(freeze["record_hash"] == FREEZE_RECORD_HASH
             and _sha(_canonical({k: v for k, v in freeze.items() if k != "record_hash"})) == FREEZE_RECORD_HASH,
             "execution_freeze_record_hash_invalid")
    inputs = freeze["input_hashes"]
    _require(len(inputs) == 50 and _frozen_input_paths(root) == set(inputs), "frozen_input_set_changed")
    for path, digest in inputs.items():
        _require(_sha(_read(root, path)) == digest, "frozen_input_changed")
    _require(_sha(_read(root, freeze["main_manifest_path"])) == freeze["main_manifest_file_sha256"],
             "frozen_main_plan_changed")
    for gate in freeze["gate_evidence"].values():
        for name, digest in gate["files"].items():
            _require(_sha(_read(root, gate["directory"] + "/" + name)) == digest,
                     "frozen_gate_artifact_changed")

    raw_main = {}
    for name, (length, digest) in MAIN_FILES.items():
        raw_main[name] = _read(root, MAIN + "/" + name)
        _require(len(raw_main[name]) == length and _sha(raw_main[name]) == digest,
                 "stopped_main_artifact_changed")
    stored = _json(raw_main["manifest.json"])
    plan, config = stored["plan"], stored["run_config"]
    _require(stored["run_config_hash"] == _sha(_canonical({"plan": plan, "config": config}))
             and config["input_hashes"] == inputs and config["freeze"] == freeze
             and config["evidence_kind"] == "empirical"
             and _sha(_canonical(plan)) == freeze["main_manifest_hash"], "stopped_main_binding_invalid")
    events = _chain(raw_main["calls.jsonl"])
    plan_ids = [cell["cell_id"] for cell in plan["cells"]]
    completed = [e["cell_id"] for e in events if e["event"] == "cell_completed"]
    _require(len(plan_ids) == len(set(plan_ids)) == 704 and completed == plan_ids[:652],
             "completed_main_prefix_changed")
    eligible = plan_ids[652:]
    attempted = {e["cell_id"] for e in events if e["event"] == "attempt_started"}
    _require(len(eligible) == 52 and eligible[0] == PENDING
             and attempted.intersection(eligible) == {PENDING}, "eligible_main_schedule_changed")
    pending_events = [e for e in events if e["cell_id"] == PENDING]
    pending_failed = [e for e in pending_events if e["event"] == "attempt_failed"]
    _require([e["event"] for e in pending_events] == ["phase_defined", "attempt_started", "attempt_failed",
                                                    "attempt_started", "attempt_failed"]
             and [e["attempt"] for e in pending_failed] == [1, 2]
             and all(e["phase"] == "readback" and e["retryable"] is True
                     and e["infrastructure"] is True and e["http_status"] == 429 for e in pending_failed),
             "pending_readback_retry_changed")
    terminal = [e for e in events if e["event"] == "cell_completed" and e["cell_id"] == TERMINAL]
    _require(len(terminal) == 1 and TERMINAL not in eligible
             and terminal[0]["continuation_status"] == "missing:infrastructure_exhausted:http_error",
             "retained_terminal_continuation_changed")
    kinds = Counter(e["event"] for e in events)
    _require(len(events) == 4461 and kinds["attempt_started"] == 1036
             and kinds["attempt_succeeded"] == 996 and kinds["attempt_failed"] == 40,
             "stopped_main_attempt_counts_changed")

    _require(_sha(_read(root, SESSION + "/authorization.json")) == AUTHORIZATION_SHA256,
             "staged_authorization_changed")
    controls, prefix_report = {}, {}
    for name, (length, digest, count) in CONTROL_PREFIXES.items():
        raw = _read(root, SESSION + "/" + name)
        _require(len(raw) >= length and _sha(raw[:length]) == digest, "staged_control_prefix_changed")
        records = _chain(raw, ascii_only=True)
        _require(len(raw) == length and len(records) == count, "staged_control_append_requires_review")
        controls[name] = records
        prefix_report[name] = {"bytes": length, "sha256": digest, "events": count,
                               "last_event_hash": records[-1]["event_hash"], "appended_events": 0}
    budget_events, counter_events = controls["budget.jsonl"], controls["attempts.jsonl"]
    _require(budget_events[0]["cap"] == "9" and budget_events[0]["currency"] == "USD"
             and counter_events[0]["maximum_attempts"] == 3000
             and counter_events[0]["authorization_id"] == "paid-staged-usd9-v1",
             "staged_allowance_changed")
    reserved = {e["attempt_id"]: e for e in budget_events if e["event"] == "reserved"}
    settlements = {e["attempt_id"]: e for e in budget_events if e["event"] == "settled"}
    _require(len(reserved) == len(settlements) == 1561 and set(reserved) == set(settlements)
             and [e["ordinal"] for e in counter_events[1:]] == list(range(1, 1562)),
             "staged_attempt_counts_changed")
    held_ids = [key for key, event in settlements.items() if event["actual_cost"] is None]
    held = sum((Decimal(reserved[key]["maximum_cost"]) for key in held_ids), Decimal(0))
    known = sum((Decimal(event["actual_cost"]) for event in settlements.values()
                 if event["actual_cost"] is not None), Decimal(0))
    _require(len(held_ids) == 40 and held == Decimal("1.93872838656")
             and known == Decimal("0.19176235952"), "staged_cost_baseline_changed")
    report = {
        "schema_version": 1,
        "classification": "offline_continuation_proposal_not_execution_authorization",
        "verification_status": "verified_stopped_baseline",
        "dispatch_allowed": False, "blocking_reason": "staged_unknown_cost_hold_limit_reached",
        "inference_calls": 0, "billing_receipts_added": 0, "ledger_changes": 0,
        "collection_source_commit": COLLECTION_SOURCE,
        "freeze": {"commit": freeze["commit"], "tag": freeze["tag"],
                   "record_hash": FREEZE_RECORD_HASH, "file_sha256": FREEZE_SHA256,
                   "remote_tag_freshly_verified": False},
        "frozen_inputs_verified": len(inputs), "frozen_gate_artifacts_verified": 15,
        "main_artifacts": {name: {"bytes": length, "sha256": digest}
                           for name, (length, digest) in MAIN_FILES.items()},
        "main": {"planned_cells": 704, "completed_cells": len(completed),
                 "completed_prefix_cell_ids_sha256": _sha(_canonical(completed)),
                 "completed_prefix_last_cell": completed[-1],
                 "eligible_cells": len(eligible), "eligible_cell_ids": eligible, "untouched_cells": 51,
                 "journal_events": len(events), "journal_last_event_hash": events[-1]["event_hash"],
                 "attempts": 1036, "accepted_replies": 996, "http429_failures": 40,
                 "pending_retry": {"cell_id": PENDING, "phase": "readback",
                                   "completed_failed_attempts": [1, 2], "next_attempt": 3, "maximum_attempt": 4,
                                   "request_hash": pending_failed[-1]["request_hash"],
                                   "logical_request_hash": pending_events[0]["logical_request_hash"]},
                 "forbidden_terminal_retry": {"cell_id": TERMINAL, "phase": "continuation",
                                              "reason": terminal[0]["continuation_status"]}},
        "control_prefixes": prefix_report,
        "budget": {"cap_usd": "9", "known_settled_usd": _text(known), "held_usd": _text(held),
                   "available_usd": _text(Decimal(9) - known - held), "unknown_cost_holds": len(held_ids),
                   "maximum_unknown_cost_holds": 40, "held_attempt_ids": held_ids},
        "attempts": {"maximum": 3000, "consumed": 1561, "remaining": 1439},
        "current_policy_requirements": ["attributable_billing_evidence_and_validated_reconciliation",
                                        "fewer_than_40_unresolved_holds_within_unchanged_caps"],
        "operational_amendment_alternative": {
            "status": "proposed_not_approved_not_implemented", "dispatch_allowed": False,
            "requires_explicit_approval": True,
            "proposal": "fixed_retained_40_hold_exception_with_full_reservations_and_stop_on_any_new_unknown",
            "requires": ["reviewed_amendment_and_new_operational_provenance",
                         "tested_continuation_path_preserving_scientific_freeze_and_shared_caps"],
            "changes_cost_evidence": False, "settles_or_refunds_holds": False,
        },
        "shared_requirements_before_dispatch": ["reviewed_operational_continuation_provenance",
                                                "fresh_main_account_route_and_remote_freeze_tag_readiness"],
    }
    report["report_hash"] = _sha(_canonical(report))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, help="Explicit new report file; existing files are never overwritten")
    args = parser.parse_args(argv)
    try:
        report = verify_continuation(args.root)
        text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output is not None:
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
        print(text, end="")
        return 0
    except (ContinuationVerificationError, OSError) as error:
        reason = str(error) if isinstance(error, ContinuationVerificationError) else "report_output_unavailable"
        print(json.dumps({"verification_status": "blocked", "dispatch_allowed": False, "reason": reason}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
