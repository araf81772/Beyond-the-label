"""Manifest-driven execution with durable, replayable journals.

Synthetic fixtures exercise infrastructure; they are never empirical model
observations. Real execution requires the separate, verified free-only path.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import random
import re
from typing import Any

from .generate import SEEDS, canonical_json, generate_world, make_case
from .provider import PinnedProvider, ProviderFailure, ProviderResult, ProviderSettings, parse_response, serialize_request
from .render import decision_request, expected_readback, prompt_text, readback_request
from .sandbox import Sandbox
from .schemas import Case, ModelReply, Request, ScoreRow
from .score import classify_action, score_episode, score_first_action
from .gates import require_real_execution

ROOT = Path(__file__).resolve().parents[2]
PHASES = {"first", "first_reprompt", "continuation", "continuation_reprompt", "readback"}


def _hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def build_manifest(dataset: str = "main", load: int = 2, schedule_seed: int = 271828) -> dict[str, Any]:
    if dataset not in SEEDS or load not in (2, 8) or type(schedule_seed) is not int:
        raise ValueError("Invalid manifest factors")
    cells = []

    def add(seed: int, condition: str, layout: str, twin: str | None, purpose: str = "decision") -> None:
        cells.append({"cell_id": f"{dataset}-{seed}-{purpose}-{condition}-{layout}-{twin or 'masked'}",
                      "world_seed": seed, "purpose": purpose, "condition": condition, "layout": layout, "twin": twin})

    for seed in SEEDS[dataset]:
        for layout in ("separate", "inline"):
            for twin in ("a", "b"):
                add(seed, "MAIN", layout, twin)
                add(seed, "MAIN", layout, twin, "readback")
        if dataset != "main" or seed < 2016:
            for condition in ("HIGH-FEE", "HIGH-STAKES"):
                for layout in ("separate", "inline"):
                    for twin in ("a", "b"):
                        add(seed, condition, layout, twin)
            for layout in ("separate", "inline"):
                add(seed, "MASKED", layout, None)
            for twin in ("a", "b"):
                add(seed, "NUMERIC", "separate", twin)
    random.Random(schedule_seed).shuffle(cells)
    counts = {"READBACK": sum(c["purpose"] == "readback" for c in cells)}
    counts.update({condition: sum(c["purpose"] == "decision" and c["condition"] == condition for c in cells)
                   for condition in ("MAIN", "HIGH-FEE", "HIGH-STAKES", "MASKED", "NUMERIC")})
    decisions = sum(c["purpose"] == "decision" for c in cells)
    return {"manifest_version": 1, "dataset": dataset, "load": load, "schedule_seed": schedule_seed,
            "classification": "planned_not_frozen", "approved_for_execution": False,
            "seeds": list(SEEDS[dataset]), "counts": counts, "initial_calls": len(cells),
            "maximum_continuations": decisions, "maximum_planned_calls": len(cells) + decisions,
            "additional_calls_accounted_separately": ["infrastructure_retries", "permitted_no_tool_reprompts"],
            "cells": cells}


def _validate_manifest(manifest: dict[str, Any]) -> None:
    try:
        expected = build_manifest(manifest["dataset"], manifest["load"], manifest["schedule_seed"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("Invalid execution manifest") from None
    if manifest != expected:
        raise ValueError("Manifest differs from the complete deterministic design")


def case_for_cell(cell: dict[str, Any], manifest: dict[str, Any]) -> Case:
    world = generate_world(cell["world_seed"], manifest["dataset"])
    twin = cell["twin"]
    if cell["condition"] == "MASKED":
        assignment = (world.index // 8) % 2 if manifest["dataset"] == "main" else world.index % 2
        twin = "a" if assignment == 0 else "b"
    return make_case(world, twin=twin, layout=cell["layout"], condition=cell["condition"], load=manifest["load"])


def _inputs() -> dict[str, str]:
    files = sorted((ROOT / "src/beyond_label").glob("*.py")) + sorted((ROOT / "prompts").glob("*.txt"))
    files += [ROOT / "research/protocol.md", ROOT / "research/amendments.md"]
    files += sorted((ROOT / "configs").glob("*.yaml"))
    files += sorted((ROOT / "data").glob("worlds_*.jsonl"))
    files += [path for path in (ROOT / "data/manifest.json", ROOT / "pyproject.toml", ROOT / "requirements.lock") if path.exists()]
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}


class JournalIntegrityError(ValueError):
    pass


@contextmanager
def _writer_lock(run_dir: Path):
    """Nonblocking OS lock, automatically released if a process dies.

    Keep the lock file in place: deleting it after unlock would let concurrent
    open handles lock different inodes. The file holds no scientific data.
    """
    handle = (run_dir / ".writer.lock").open("a+b")
    acquired = False
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            raise JournalIntegrityError("run_already_locked_by_writer") from None
        yield
    finally:
        if acquired:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


class Journal:
    """Append-only SHA-256-linked JSONL; each event is flushed and fsynced."""

    def __init__(self, path: Path):
        self.path = path
        self.events: list[dict[str, Any]] = []
        previous = "0" * 64
        raw = path.read_bytes() if path.exists() else b""
        if raw and not raw.endswith(b"\n"):
            raise JournalIntegrityError("torn_final_journal_record")
        for line in raw.splitlines():
            try:
                event = json.loads(line)
                digest = event.pop("event_hash")
                if event["sequence"] != len(self.events) + 1 or event["previous_hash"] != previous or _hash(event) != digest:
                    raise ValueError
                event["event_hash"] = digest
            except (ValueError, KeyError, TypeError, AttributeError):
                raise JournalIntegrityError("invalid_journal_hash_or_sequence") from None
            self.events.append(event)
            previous = digest

    def append(self, event: dict[str, Any]) -> None:
        if set(event) & {"sequence", "previous_hash", "event_hash"}:
            raise JournalIntegrityError("reserved_journal_fields")
        saved = copy.deepcopy(event)
        saved.update(sequence=len(self.events) + 1,
                     previous_hash=self.events[-1]["event_hash"] if self.events else "0" * 64)
        saved["event_hash"] = _hash(saved)
        raw = (canonical_json(saved) + "\n").encode("utf-8")
        with self.path.open("ab") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        self.events.append(saved)


def _cell_events(journal: Journal, cell_id: str) -> list[dict[str, Any]]:
    return [event for event in journal.events if event.get("cell_id") == cell_id]


def _phase_result(events: list[dict[str, Any]], phase: str) -> ProviderResult | None:
    successes = [e for e in events if e.get("phase") == phase and e["event"] == "attempt_succeeded"]
    if len(successes) > 1:
        raise JournalIntegrityError("duplicate_successful_phase")
    try:
        return ProviderResult.model_validate(successes[0]["result"]) if successes else None
    except (ValueError, KeyError):
        raise JournalIntegrityError("invalid_saved_provider_result") from None


def _phase(journal: Journal, provider: PinnedProvider, cell_id: str, phase: str, request: Request) -> tuple[ProviderResult | None, str | None]:
    events = [event for event in _cell_events(journal, cell_id) if event.get("phase") == phase]
    digest = _hash(request.model_dump(mode="json"))
    definitions = [event for event in events if event["event"] == "phase_defined"]
    if len(definitions) > 1 or (definitions and definitions[0]["logical_request_hash"] != digest):
        raise JournalIntegrityError("changed_logical_request")
    try:
        expected_payload = serialize_request(request, provider.settings)
    except ProviderFailure as failure:
        # Validate before writing phase_defined: rejected secrets/headers must
        # never enter the durable request log, even on a failing request.
        return None, failure.reason
    for event in events:
        if event["event"].startswith("attempt_"):
            if event.get("payload") != expected_payload or event.get("request_hash") != _hash(expected_payload):
                raise JournalIntegrityError("saved_request_payload_mismatch")
            if event["event"] == "attempt_succeeded" and event["result"].get("payload") != expected_payload:
                raise JournalIntegrityError("saved_result_payload_mismatch")
    successful = _phase_result(events, phase)
    if successful is not None:
        return successful, None
    starts = [e for e in events if e["event"] == "attempt_started"]
    terminals = [e for e in events if e["event"] in {"attempt_succeeded", "attempt_failed"}]
    if len(starts) != len(terminals):
        return None, "ambiguous_infrastructure_attempt"
    failures = [e for e in terminals if e["event"] == "attempt_failed"]
    if failures and not failures[-1].get("retryable", False):
        prefix = "infrastructure_exhausted:" if failures[-1].get("infrastructure") else ""
        return None, prefix + failures[-1]["reason"]
    if not definitions:
        journal.append({"event": "phase_defined", "cell_id": cell_id, "phase": phase,
                        "logical_request_hash": digest, "request": request.model_dump(mode="json")})

    def log_attempt(event: dict[str, Any]) -> None:
        journal.append({**event, "cell_id": cell_id, "phase": phase})

    try:
        return provider.request(request, log_attempt=log_attempt, start_attempt=len(failures) + 1), None
    except ProviderFailure as failure:
        return None, failure.reason


def _assistant(reply: ModelReply) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": reply.content}
    if reply.tool_calls:
        message["tool_calls"] = [{"id": call.id, "type": "function", "function": {
            "name": call.name, "arguments": call.arguments if isinstance(call.arguments, str) else canonical_json(call.arguments),
        }} for call in reply.tool_calls]
    return message


def _no_tool(reply: ModelReply) -> bool:
    return not reply.tool_calls and not reply.refused


def _reprompt(request: Request, reply: ModelReply) -> Request:
    return request.model_copy(update={"messages": [*copy.deepcopy(request.messages), _assistant(reply),
                                                   {"role": "user", "content": prompt_text("reprompt_no_tool.txt")}]})


def _record_tool(journal: Journal, cell_id: str, phase: str, sandbox: Sandbox) -> None:
    event = {"event": "tool_applied", "cell_id": cell_id, "phase": phase, "transition": sandbox.events[-1]}
    previous = [e for e in _cell_events(journal, cell_id) if e["event"] == "tool_applied" and e.get("phase") == phase]
    if previous:
        if len(previous) != 1 or previous[0]["transition"] != event["transition"]:
            raise JournalIntegrityError("tool_transition_mismatch")
        return
    journal.append(event)


def _execute_cell(cell: dict[str, Any], manifest: dict[str, Any], journal: Journal, provider: PinnedProvider) -> None:
    cell_id = cell["cell_id"]
    case = case_for_cell(cell, manifest)
    completion: dict[str, Any] = {"event": "cell_completed", "cell_id": cell_id,
                                  "first_missing_reason": None, "continuation_status": "not_applicable"}
    if cell["purpose"] == "readback":
        _, reason = _phase(journal, provider, cell_id, "readback", readback_request(case))
        completion["first_missing_reason"] = reason
        journal.append(completion)
        return
    request = decision_request(case)
    result, reason = _phase(journal, provider, cell_id, "first", request)
    reprompt_used = False
    if result is not None and _no_tool(result.reply):
        request = _reprompt(request, result.reply)
        result, reason = _phase(journal, provider, cell_id, "first_reprompt", request)
        reprompt_used = True
    if result is None:
        completion["first_missing_reason"] = reason
        journal.append(completion)
        return
    first = result.reply
    sandbox = Sandbox(case)
    tool_result = sandbox.apply_reply(first)
    _record_tool(journal, cell_id, "first", sandbox)
    if classify_action(case, first) in {"INSPECT_1", "INSPECT_2"}:
        request = request.model_copy(update={"messages": [*copy.deepcopy(request.messages), _assistant(first),
            {"role": "tool", "tool_call_id": first.tool_calls[0].id, "content": canonical_json(tool_result)}]})
        result, reason = _phase(journal, provider, cell_id, "continuation", request)
        if result is not None and _no_tool(result.reply) and not reprompt_used:
            request = _reprompt(request, result.reply)
            result, reason = _phase(journal, provider, cell_id, "continuation_reprompt", request)
        if result is None:
            completion["continuation_status"] = f"missing:{reason}"
        else:
            final = sandbox.apply_reply(result.reply)
            _record_tool(journal, cell_id, "continuation", sandbox)
            completion["continuation_status"] = "committed" if sandbox.dispositions is not None else f"invalid:{final['error']['code']}"
    journal.append(completion)


def _readback_correct(case: Case, reply: ModelReply) -> bool:
    if reply.tool_calls or reply.refused:
        return False
    try:
        rows = json.loads(reply.content or "")
        if not isinstance(rows, list) or len(rows) != 2:
            return False
        if any(not isinstance(r, dict) or set(r) != {"lot_id", "tested_configuration", "matches_current"}
               or type(r["matches_current"]) is not bool for r in rows):
            return False
        if len({r["lot_id"] for r in rows}) != 2:
            return False
        return sorted(rows, key=lambda r: r["lot_id"]) == sorted(expected_readback(case), key=lambda r: r["lot_id"])
    except (ValueError, TypeError, KeyError):
        return False


def _score_cell(cell: dict[str, Any], manifest: dict[str, Any], journal: Journal) -> dict[str, Any]:
    events = _cell_events(journal, cell["cell_id"])
    completed = [e for e in events if e["event"] == "cell_completed"]
    if len(completed) > 1:
        raise JournalIntegrityError("duplicate_completed_cell")
    terminal = completed[0] if completed else {}
    case = case_for_cell(cell, manifest)
    base = {**cell, "evidence_kind": "synthetic", "readback_correct": None,
            "continuation_status": terminal.get("continuation_status", "pending"), "report_contradiction": None,
            "cell_status": "completed" if completed else "pending"}
    score = ScoreRow(cell_id=cell["cell_id"], missing_reason=terminal.get("first_missing_reason") or "not_executed_yet")
    if cell["purpose"] == "readback":
        if any(e["event"] == "tool_applied" for e in events):
            raise JournalIntegrityError("readback_contains_tool_transition")
        result = _phase_result(events, "readback")
        if result:
            score = ScoreRow(cell_id=cell["cell_id"])
            base["readback_correct"] = _readback_correct(case, result.reply)
        return {**base, **score.model_dump()}
    result = _phase_result(events, "first")
    reprompt_used = bool(result and _no_tool(result.reply))
    if reprompt_used:
        result = _phase_result(events, "first_reprompt")
    if result is None:
        if any(e["event"] == "tool_applied" for e in events):
            raise JournalIntegrityError("tool_transition_without_decision")
        return {**base, **score.model_dump()}
    first = result.reply
    sandbox = Sandbox(case)
    sandbox.apply_reply(first)
    score = score_first_action(cell["cell_id"], case, first)
    if sandbox.inspected_lot:
        report = next(r for r in case.public.records if r.lot_id == sandbox.inspected_lot)
        base["report_contradiction"] = case.hidden_states[sandbox.inspected_lot] != report.result
        continuation = _phase_result(events, "continuation")
        if continuation and _no_tool(continuation.reply) and not reprompt_used:
            continuation = _phase_result(events, "continuation_reprompt")
        if continuation:
            sandbox.apply_reply(continuation.reply)
    score = score_episode(cell["cell_id"], case, first, sandbox)
    transitions = [e["transition"] for e in events if e["event"] == "tool_applied"]
    if transitions != sandbox.events[:len(transitions)] or (completed and len(transitions) != len(sandbox.events)):
        raise JournalIntegrityError("stored_tool_transition_disagrees_with_replay")
    return {**base, **score.model_dump()}


def _validate_execution_config(config: dict[str, Any], settings: ProviderSettings, manifest: dict[str, Any],
                               freeze: dict[str, Any] | None = None) -> None:
    from .provider import _sanitized, canonical_json as provider_json
    if not isinstance(config, dict) or provider_json(_sanitized(config)) != provider_json(config):
        raise ValueError("Invalid or sensitive execution configuration")
    if config.get("free_only") is not True or settings.free_only is not True:
        raise ValueError("Only free execution is authorized")
    require_real_execution(config, stage=manifest["dataset"], freeze=freeze)
    for key in ("model", "provider", "provider_route", "provider_identity_source", "temperature",
                "reasoning", "max_output_tokens", "require_parameters"):
        if key not in config or config[key] != getattr(settings, key):
            raise ValueError("Execution settings differ from pinned provider")
    if config.get("load") != manifest["load"] or config.get("schedule_seed") != manifest["schedule_seed"]:
        raise ValueError("Execution manifest factors differ from configuration")
    if manifest["dataset"] == "main":
        from .freeze import verify_freeze
        verify_freeze(freeze, manifest, settings)


def _validate_live_transport(provider: PinnedProvider) -> None:
    from .attempts import AttemptLimit, CappedFreeAttempts, FreeQuota
    from .controls import GuardedTransport
    from .live import open_attempt_limit, reconcile_ledger
    from .openrouter import OpenRouterFreeTransport
    guard = provider.transport
    if (type(provider) is not PinnedProvider or type(guard) is not GuardedTransport
            or guard.ledger.cap != 0 or guard.ledger.currency != "USD"
            or type(guard.transport) is not OpenRouterFreeTransport
            or guard.transport._transport is not None
            or guard.transport.model != provider.settings.model
            or guard.transport.provider_route != provider.settings.provider_route):
        raise ValueError("Live execution requires the guarded free HTTPS transport; fixtures remain synthetic")
    policy = provider.before_attempt
    session = (ROOT / "runs/_free_session").resolve()
    if (type(policy) is not CappedFreeAttempts
            or type(policy.counter) is not AttemptLimit or type(policy.quota) is not FreeQuota
            or policy.counter.path != session / "attempts.jsonl"
            or guard.ledger.path != session / "budget.jsonl"
            or getattr(guard.before_dispatch, "__self__", None) is not policy.quota
            or getattr(guard.before_dispatch, "__func__", None) is not FreeQuota.check_dispatch_day):
        raise ValueError("Live execution requires the shared durable ten-attempt policy")
    reconcile_ledger(guard.ledger, ROOT / "runs")
    open_attempt_limit(session, ROOT / "runs", guard.ledger)


def _csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: ("true" if value is True else "false" if value is False else value)
                             for key, value in row.items()})


def _validate_journal(journal: Journal, manifest: dict[str, Any], config: dict[str, Any]) -> None:
    allowed_ids = {c["cell_id"] for c in manifest["cells"]}
    cells = {c["cell_id"]: c for c in manifest["cells"]}
    settings = ProviderSettings.model_validate(config["provider_settings"])
    completed = set()
    starts: set[tuple[str, str, int]] = set()
    finished: set[tuple[str, str, int]] = set()
    definitions: dict[tuple[str, str], dict[str, Any]] = {}
    last_attempt: dict[tuple[str, str], int] = {}
    succeeded: set[tuple[str, str]] = set()
    request_ids: dict[str, str] = {}
    for e in journal.events:
        cell_id = e.get("cell_id")
        if cell_id not in allowed_ids:
            raise JournalIntegrityError("unknown_cell_id")
        if e.get("phase") is not None and e["phase"] not in PHASES:
            raise JournalIntegrityError("unknown_phase")
        if cell_id in completed:
            raise JournalIntegrityError("event_after_completed_cell")
        if e["event"] == "cell_completed":
            completed.add(cell_id)
        elif e["event"] == "phase_defined":
            key = (cell_id, e["phase"])
            if key in definitions or _hash(e["request"]) != e["logical_request_hash"]:
                raise JournalIntegrityError("invalid_or_duplicate_phase_definition")
            if (cells[cell_id]["purpose"] == "readback") != (e["phase"] == "readback"):
                raise JournalIntegrityError("phase_purpose_mismatch")
            request = Request.model_validate(e["request"])
            if e["phase"] in {"first", "readback"}:
                case = case_for_cell(cells[cell_id], manifest)
                expected = readback_request(case) if e["phase"] == "readback" else decision_request(case)
                if request != expected:
                    raise JournalIntegrityError("decision_or_readback_prefix_mismatch")
            definitions[key] = serialize_request(request, settings)
        elif e["event"] in {"attempt_started", "attempt_succeeded", "attempt_failed"}:
            key = (cell_id, e["phase"], e["attempt"])
            phase_key = (cell_id, e["phase"])
            if phase_key not in definitions or e.get("payload") != definitions[phase_key] or e.get("request_hash") != _hash(e["payload"]):
                raise JournalIntegrityError("attempt_request_hash_or_payload_mismatch")
            if type(e["attempt"]) is not int or not 1 <= e["attempt"] <= 4:
                raise JournalIntegrityError("invalid_attempt_number")
            if e["event"] == "attempt_started":
                previous = last_attempt.get(phase_key, 0)
                if key in starts or phase_key in succeeded or e["attempt"] != previous + 1 or (previous and (*phase_key, previous) not in finished):
                    raise JournalIntegrityError("duplicate_nonsequential_or_late_attempt")
                starts.add(key)
                last_attempt[phase_key] = e["attempt"]
            else:
                if key not in starts or key in finished:
                    raise JournalIntegrityError("unmatched_attempt_outcome")
                finished.add(key)
                if e["event"] == "attempt_succeeded":
                    result = ProviderResult.model_validate(e["result"])
                    if result.payload != e["payload"] or result.usage != e["usage"] or result.latency_seconds != e["latency_seconds"] or result.returned_model != settings.model or result.returned_provider != settings.provider:
                        raise JournalIntegrityError("provider_result_reconciliation_failed")
                    try:
                        reparsed = parse_response(result.raw_response, result.payload, settings, result.latency_seconds)
                    except ProviderFailure:
                        raise JournalIntegrityError("saved_raw_response_invalid") from None
                    if reparsed != result:
                        raise JournalIntegrityError("saved_parsing_disagrees_with_raw_response")
                    if result.request_id is not None:
                        if result.request_id in request_ids and request_ids[result.request_id] != e["request_hash"]:
                            raise JournalIntegrityError("request_id_reused_for_different_payload")
                        request_ids[result.request_id] = e["request_hash"]
                    succeeded.add(phase_key)
        elif e["event"] != "tool_applied":
            raise JournalIntegrityError("unknown_event")
    for cell in manifest["cells"]:
        events = _cell_events(journal, cell["cell_id"])
        for phase in PHASES:
            _phase_result(events, phase)


def rebuild_outputs(run_dir: Path | str) -> dict[str, Any]:
    """Regenerate derived CSVs and denominators from stored traces; no provider."""
    run_dir = Path(run_dir)
    stored = json.loads((run_dir / "manifest.json").read_text("utf-8"))
    manifest = stored["plan"]
    _validate_manifest(manifest)
    if stored["run_config_hash"] != _hash({"plan": manifest, "config": stored["run_config"]}):
        raise JournalIntegrityError("run_configuration_hash_mismatch")
    if stored["run_config"]["input_hashes"] != _inputs():
        raise JournalIntegrityError("input_hashes_changed")
    run_config = stored["run_config"]
    kind = run_config.get("evidence_kind")
    if kind not in {"synthetic", "empirical"}:
        raise JournalIntegrityError("invalid_evidence_kind")
    if kind == "empirical":
        if run_config.get("transport_provenance") != "openrouter_free_https_v1":
            raise JournalIntegrityError("Empirical transport provenance is missing")
        _validate_execution_config(run_config.get("execution_config"),
            ProviderSettings.model_validate(run_config["provider_settings"]), manifest, run_config.get("freeze"))
    journal = Journal(run_dir / "calls.jsonl")
    _validate_journal(journal, manifest, stored["run_config"])
    scores = [_score_cell(cell, manifest, journal) for cell in manifest["cells"]]
    for row in scores:
        row["evidence_kind"] = kind
    fields = list(scores[0])
    _csv(run_dir / "scores.csv", scores, fields)
    usage = []
    for e in journal.events:
        if e["event"] not in {"attempt_succeeded", "attempt_failed"}:
            continue
        metrics = e.get("usage", {})
        result = e.get("result", {})
        usage.append({"cell_id": e["cell_id"], "phase": e["phase"], "attempt": e["attempt"],
                      "success": e["event"] == "attempt_succeeded", "request_hash": e["request_hash"],
                      "request_id": result.get("request_id"), "model": result.get("returned_model"),
                      "provider": result.get("returned_provider"), "finish_reason": result.get("finish_reason"),
                      "latency_seconds": e.get("latency_seconds"), "prompt_tokens": metrics.get("prompt_tokens"),
                      "completion_tokens": metrics.get("completion_tokens"), "total_tokens": metrics.get("total_tokens"),
                      "cost_usd": metrics.get("cost"), "cost_evidence": ("synthetic_fixture_not_billed" if kind == "synthetic" else "provider_usage_cost_usd") if "cost" in metrics else "unavailable",
                      "error": e.get("reason"), "evidence_kind": kind})
    if kind == "empirical":
        finished = {(row["cell_id"], row["phase"], row["attempt"]) for row in usage}
        starts = [e for e in journal.events if e["event"] == "attempt_started"]
        order = {(e["cell_id"], e["phase"], e["attempt"]): i for i, e in enumerate(starts)}
        for e in starts:
            if (e["cell_id"], e["phase"], e["attempt"]) not in finished:
                usage.append({"cell_id": e["cell_id"], "phase": e["phase"], "attempt": e["attempt"],
                    "success": False, "request_hash": e["request_hash"], "request_id": None,
                    "model": None, "provider": None, "finish_reason": None, "latency_seconds": None,
                    "prompt_tokens": None, "completion_tokens": None, "total_tokens": None,
                    "cost_usd": None, "cost_evidence": "unavailable",
                    "error": "ambiguous_infrastructure_attempt", "evidence_kind": kind})
        usage.sort(key=lambda row: order[(row["cell_id"], row["phase"], row["attempt"])])
    usage_fields = ["cell_id", "phase", "attempt", "success", "request_hash", "request_id", "model", "provider", "finish_reason",
                    "latency_seconds", "prompt_tokens", "completion_tokens", "total_tokens", "cost_usd", "cost_evidence", "error", "evidence_kind"]
    _csv(run_dir / "usage.csv", usage, usage_fields)
    summary = {
        "evidence_kind": kind,
        "empirical_observations": sum(not row["missing_reason"] for row in scores) if kind == "empirical" else 0,
        "experimental_provider_spend": sum(row["cost_usd"] for row in usage if row["cost_usd"] is not None) if kind == "empirical" else 0,
        "run_config_hash": stored["run_config_hash"], "planned_cells": len(scores),
        "completed_cells": sum(row["cell_status"] == "completed" for row in scores),
        "pending_cells": sum(row["cell_status"] != "completed" for row in scores),
        "first_action_or_readback_missing": sum(bool(row["missing_reason"]) for row in scores),
        "successful_calls": sum(e["event"] == "attempt_succeeded" for e in journal.events),
        "attempted_calls": sum(e["event"] == "attempt_started" for e in journal.events),
        "infrastructure_retries": sum(e["event"] == "attempt_started" and e["attempt"] > 1 for e in journal.events),
        "permitted_reprompts": sum(e["event"] == "phase_defined" and e["phase"].endswith("_reprompt") for e in journal.events),
        "continuations": sum(e["event"] == "phase_defined" and e["phase"] == "continuation" for e in journal.events),
        "invalid_first_actions": sum(bool(row["category"] and (row["category"].startswith("INVALID_") or row["category"] == "REFUSED")) for row in scores),
        "missingness": [{"cell_id": row["cell_id"], "reason": row["missing_reason"]} for row in scores if row["missing_reason"]],
        "cells": [{"cell_id": row["cell_id"], "status": row["cell_status"], "missing_reason": row["missing_reason"],
                   "continuation_status": row["continuation_status"]} for row in scores],
    }
    if kind == "empirical":
        summary["spend_evidence_complete"] = all(row["cost_usd"] is not None for row in usage)
        summary["known_provider_spend_usd"] = summary["experimental_provider_spend"]
        if not summary["spend_evidence_complete"]:
            summary["experimental_provider_spend"] = None
        summary["unknown_cost_attempts"] = sum(row["cost_usd"] is None for row in usage)
        summary["accounting_error_attempts"] = sum(bool(e.get("accounting_error")) for e in journal.events)
        summary["nonzero_cost_attempts"] = sum(row["cost_usd"] is not None and row["cost_usd"] != 0 for row in usage)
    (run_dir / "analysis_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    return summary


def _run_manifest_locked(manifest: dict[str, Any], run_dir: Path | str, provider: PinnedProvider, *,
                         synthetic: bool = True, max_cells: int | None = None,
                         execution_config: dict[str, Any] | None = None,
                         freeze: dict[str, Any] | None = None) -> dict[str, Any]:
    if not synthetic and execution_config is None:
        raise ValueError("Live execution is disabled by the offline instruction")
    if max_cells is not None and (type(max_cells) is not int or max_cells < 0):
        raise ValueError("Invalid max_cells")
    _validate_manifest(manifest)
    # Provider settings also enter manifest.json, so reject sensitive values
    # before making any run-directory or manifest side effect.
    serialize_request(Request(messages=[]), provider.settings)
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    kind = "synthetic" if synthetic else "empirical"
    config = {"evidence_kind": kind, "provider_settings": provider.settings.model_dump(mode="json"),
              "input_hashes": _inputs(), "reprompt_limit_per_episode": 1,
              "ambiguous_attempt_policy": "explicit_missing_no_resampling"}
    if execution_config is not None:
        config["execution_config"] = copy.deepcopy(execution_config)
        config["transport_provenance"] = "injected_fixture" if synthetic else "openrouter_free_https_v1"
        if freeze is not None:
            config["freeze"] = copy.deepcopy(freeze)
    stored = {"plan": manifest, "run_config": config, "run_config_hash": _hash({"plan": manifest, "config": config})}
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        if json.loads(manifest_path.read_text("utf-8")) != stored:
            raise JournalIntegrityError("run_manifest_or_configuration_changed")
    else:
        if (run_dir / "calls.jsonl").exists():
            raise JournalIntegrityError("journal_without_manifest")
        manifest_path.write_text(json.dumps(stored, indent=2) + "\n", encoding="utf-8", newline="\n")
    (run_dir / "calls.jsonl").touch(exist_ok=True)
    try:
        journal = Journal(run_dir / "calls.jsonl")
        _validate_journal(journal, manifest, config)
    except JournalIntegrityError as error:
        raw = (run_dir / "calls.jsonl").read_bytes()
        blocker = {"status": "blocked", "reason": str(error), "raw_trace_sha256": hashlib.sha256(raw).hexdigest(),
                   "raw_trace_preserved": True, "evidence_kind": kind, "action": "Inspect preserved journal; do not resample ambiguous attempts"}
        (run_dir / "recovery_blocker.json").write_text(json.dumps(blocker, indent=2) + "\n", encoding="utf-8", newline="\n")
        raise
    complete = {e["cell_id"] for e in journal.events if e["event"] == "cell_completed"}
    if not synthetic and any(e.get("accounting_error") for e in journal.events):
        raise JournalIntegrityError("accounting_reconciliation_required_before_resume")
    processed = 0
    try:
        for cell in manifest["cells"]:
            if cell["cell_id"] in complete:
                continue
            if max_cells is not None and processed >= max_cells:
                break
            _execute_cell(cell, manifest, journal, provider)
            processed += 1
            if not synthetic:
                # Stop on infrastructure/protocol/accounting failures. Invalid
                # model actions remain completed observations and are not retried.
                events = _cell_events(journal, cell["cell_id"])
                if any(e.get("accounting_error") or e["event"] == "attempt_failed" for e in events):
                    break
    finally:
        # Successful replies already fsynced remain scoreable after interruption.
        rebuild_outputs(run_dir)
    return rebuild_outputs(run_dir)


def run_manifest(manifest: dict[str, Any], run_dir: Path | str, provider: PinnedProvider, *,
                 synthetic: bool = True, max_cells: int | None = None,
                 execution_config: dict[str, Any] | None = None,
                 freeze: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute or resume under an exclusive per-run writer lock."""
    if type(synthetic) is not bool:
        raise ValueError("Evidence mode must be explicit")
    if not synthetic and execution_config is None:
        raise ValueError("Live execution is disabled by the offline instruction")
    if max_cells is not None and (type(max_cells) is not int or max_cells < 0):
        raise ValueError("Invalid max_cells")
    _validate_manifest(manifest)
    serialize_request(Request(messages=[]), provider.settings)
    if execution_config is not None:
        _validate_execution_config(execution_config, provider.settings, manifest, freeze)
    if not synthetic:
        _validate_live_transport(provider)
        from .attempts import MAX_ATTEMPTS
        if (type(execution_config.get("maximum_inference_attempts")) is not int
                or execution_config["maximum_inference_attempts"] != MAX_ATTEMPTS):
            raise ValueError("Live execution requires the fixed ten-attempt allowance")
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    with _writer_lock(run_dir):
        return _run_manifest_locked(manifest, run_dir, provider, synthetic=synthetic, max_cells=max_cells,
                                    execution_config=execution_config, freeze=freeze)


class ScriptedPublicPolicy:
    """Deterministic test fixture using only outbound public payloads.

    Always inspects the first target, then follows the inspection and the other
    report. It is deliberately not an empirical model or an oracle policy.
    """
    def __init__(self, model: str = "synthetic-public-policy-v1", provider: str = "synthetic-local"):
        self.model, self.provider, self.calls = model, provider, 0

    def __call__(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        messages = payload["messages"]
        handoff = messages[3]["content"]
        records = re.findall(r"(REC-\d{4}) \| (LOT-\d{4}) \| result: (PASS|FAIL)(?: \| tested_configuration: (\S+))?", handoff)
        reports = {lot: result for _, lot, result, _ in records}
        targets = re.findall(r"(LOT-\d{4}) \| penalty if wrong: \d+", handoff)
        if not payload.get("tools"):
            current = re.search(r"test configuration (\S+)\.", messages[0]["content"]).group(1)
            configs = dict(re.findall(r"(REC-\d{4}) \| tested_configuration: (\S+)", handoff))
            configs.update({rid: scope for rid, _, _, scope in records if scope})
            rows = [{"lot_id": lot, "tested_configuration": configs[rid], "matches_current": configs[rid] == current}
                    for rid, lot, _, _ in records if lot in targets]
            message = {"role": "assistant", "content": canonical_json(rows)}
            finish = "stop"
        else:
            result_messages = [m for m in messages[4:] if m["role"] == "tool"]
            if result_messages:
                inspected = json.loads(result_messages[-1]["content"])
                dispositions = {lot: "RELEASE" if reports[lot] == "PASS" else "HOLD" for lot in targets}
                dispositions[inspected["lot_id"]] = "RELEASE" if inspected["state"] == "PASS" else "HOLD"
                name, arguments = "commit", {"dispositions": dispositions}
            else:
                name, arguments = "inspect", {"lot_id": targets[0]}
            message = {"role": "assistant", "content": None, "tool_calls": [{"id": "synthetic_call", "type": "function",
                         "function": {"name": name, "arguments": canonical_json(arguments)}}]}
            finish = "tool_calls"
        return {"id": f"synthetic-request-{_hash(payload)}", "model": self.model, "provider": self.provider,
                "choices": [{"message": message, "finish_reason": finish}],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost": 0.0}}


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline synthetic harness; no empirical provider execution")
    parser.add_argument("--synthetic", action="store_true", required=True)
    parser.add_argument("--dataset", choices=list(SEEDS), default="main")
    parser.add_argument("--load", type=int, choices=(2, 8), default=2)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-cells", type=int)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    if args.rebuild:
        result = rebuild_outputs(args.output)
    else:
        fixture = ScriptedPublicPolicy()
        provider = PinnedProvider(ProviderSettings(model=fixture.model, provider=fixture.provider), fixture)
        result = run_manifest(build_manifest(args.dataset, args.load), args.output, provider, max_cells=args.max_cells)
    print(json.dumps({key: value for key, value in result.items() if key not in {"cells", "missingness"}}, indent=2))


if __name__ == "__main__":
    main()
