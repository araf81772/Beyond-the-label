"""Conservatively cover one retained failed attempt without inventing its cost.

The historical HTTP404 has no billing receipt. Its entire verified upper-bound
reservation remains in the unchanged budget ledger and counts against USD1.
This specific review permits that already-covered uncertainty, not a new charge,
refund, settlement or generic bypass. Any later unknown/pending cost still stops.
All helpers are read-only; no credentials, network, dispatch or record writes.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from .budget import BudgetError, BudgetLedger, _canonical, _unique_object


COVERAGE_PATH = "research/paid_smoke_cost_coverage.json"
ORIGINAL_RUN = "runs/paid_smoke_gpt41mini_20261115"
COLLECTION_SOURCE = "0ad25621f3b730065b1a71b92aafc1fd0a2863a1"
HISTORICAL_ATTEMPT_ID = "attempt-2bd7653078634557b3fa8a2c2f516be0"
HISTORICAL_REQUEST_HASH = "0ff45575e0be2980780f1273020e6c9aecf9aa13e2ecf14251643b1846c4884e"
HISTORICAL_MAXIMUM_COST = "0.44084208"
ORIGINAL_FILES = {
    "manifest.json": "4f2aedf6c2776f40789f7658317c57b23ff914c5d24920b4f4add4100f517780",
    "calls.jsonl": "35c967b3a8154533ce159a807e1f2820b45d2a673436612405888dcbdd6fa442",
    "scores.csv": "5f9dc50f09b968c2406e0fbbccaebff2841a3622bdd8ce12df9947d46386a938",
    "usage.csv": "a77586cf465966bcc623a32c71534dd194a1392acbd6119729f8bb1e025f8d06",
    "analysis_manifest.json": "ffb58862c78feae7ad4c75055101d66a5fed4ea46d62d467aa42f7784f5aa382",
}
_PREFIXES = {
    "budget.jsonl": (890, "d44b93b21837614d35694cbf53e8a01349122b5a6b41e3fb4ed16a63a0da4044"),
    "attempts.jsonl": (496, "f68143ae6f2aae95a30435f512e6f14724c42860af41fedaa9b2e9e4fe96d81b"),
}
# These fixed identities deliberately restrict the review to the already
# observed request. A newly generated self-hashed record cannot approve another
# attempt, reduced hold, changed raw evidence, or a later unknown charge.


class CostCoverageError(BudgetError):
    """Fixed reason codes; never provider text, credentials or arbitrary paths."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _safe_bytes(root: Path, relative: str) -> bytes:
    path = root / relative
    if path.resolve() != path or not path.resolve().is_relative_to(root) or not path.is_file():
        raise CostCoverageError("reviewed_cost_evidence_unavailable")
    return path.read_bytes()


def build_cost_coverage_record(root: Path) -> dict:
    """Build the deterministic review of this exact original failed attempt.

    This is cap accounting, not a provider receipt. The source/trace/controls
    identities are deliberately fixed; future reviews require their own audited
    implementation. Additional known-cost history may append to the controls.
    """
    root = Path(root).resolve()
    try:
        raw = {name: _safe_bytes(root, f"{ORIGINAL_RUN}/{name}") for name in ORIGINAL_FILES}
        if any(_sha(raw[name]) != digest for name, digest in ORIGINAL_FILES.items()):
            raise CostCoverageError("reviewed_original_artifacts_changed")
        manifest = json.loads(raw["manifest.json"], object_pairs_hook=_unique_object)
        if manifest.get("run_config", {}).get("evidence_kind") != "empirical":
            raise CostCoverageError("reviewed_original_artifacts_changed")
        events = [json.loads(line, object_pairs_hook=_unique_object) for line in raw["calls.jsonl"].splitlines()]
        if ([event.get("event") for event in events] != ["phase_defined", "attempt_started", "attempt_failed"]
                or events[-1].get("http_status") != 404 or events[-1].get("infrastructure") is not True
                or events[-1].get("usage") != {} or events[-1].get("request_hash") != HISTORICAL_REQUEST_HASH):
            raise CostCoverageError("reviewed_original_attempt_changed")
        prefixes = {}
        for name, (length, digest) in _PREFIXES.items():
            content = _safe_bytes(root, "runs/_paid_testing_session/" + name)
            if len(content) < length or _sha(content[:length]) != digest or not content.endswith(b"\n"):
                raise CostCoverageError("reviewed_control_prefix_changed")
            prefixes[name] = {"bytes": length, "sha256": digest}
        body = {
            "schema_version": 1,
            "classification": "reviewed_conservative_hold_not_billing_receipt",
            "authorization_id": "paid-smoke-usd1-200-v1",
            "run_directory": ORIGINAL_RUN, "collection_source_commit": COLLECTION_SOURCE,
            "original_artifact_sha256": dict(ORIGINAL_FILES), "control_prefixes": prefixes,
            "currency": "USD", "aggregate_smoke_cap": "1", "maximum_aggregate_attempts": 200,
            "actual_cost_verified": False,
            "covered_attempts": [{"attempt_id": HISTORICAL_ATTEMPT_ID,
                "request_hash": HISTORICAL_REQUEST_HASH, "maximum_cost": HISTORICAL_MAXIMUM_COST,
                "actual_cost": None, "status": "unknown", "attempt_ordinal": 1,
                "cell_id": events[-1]["cell_id"], "phase": "readback", "http_status": 404,
                "basis": "entire_prior_reservation_remains_held_against_unchanged_cap"}],
        }
        return {**body, "record_hash": _sha(_canonical(body))}
    except CostCoverageError:
        raise
    except (OSError, ValueError, TypeError, KeyError, BudgetError):
        raise CostCoverageError("reviewed_cost_evidence_unavailable") from None


@dataclass(frozen=True)
class ReviewedCostCoverage:
    """Concrete validated review, bound to the canonical root and live ledger."""

    root: Path
    ledger: BudgetLedger
    record_hash: str

    @property
    def ledger_path(self) -> Path:
        return self.root / "runs/_paid_testing_session/budget.jsonl"

    @property
    def counter_path(self) -> Path:
        return self.root / "runs/_paid_testing_session/attempts.jsonl"

    def validate(self, state: dict | None = None) -> dict[str, dict]:
        try:
            if (type(self.ledger) is not BudgetLedger or self.ledger.path != self.ledger_path
                    or self.ledger.cap != 1 or self.ledger.currency != "USD"):
                raise CostCoverageError("reviewed_cost_ledger_mismatch")
            expected = build_cost_coverage_record(self.root)
            saved = json.loads(_safe_bytes(self.root, COVERAGE_PATH), object_pairs_hook=_unique_object)
            if (type(saved) is not dict or saved != expected
                    or saved.get("record_hash") != self.record_hash
                    or _sha(_canonical({key: value for key, value in saved.items() if key != "record_hash"})) != self.record_hash):
                raise CostCoverageError("reviewed_cost_record_changed")
            actual = self.ledger.snapshot()
            if state is not None and state != actual:
                raise CostCoverageError("reviewed_cost_snapshot_mismatch")
            if actual["blocked"]:
                raise CostCoverageError("reviewed_cost_budget_blocked")
            original = actual["attempts"].get(HISTORICAL_ATTEMPT_ID)
            required = {"maximum_cost": HISTORICAL_MAXIMUM_COST, "actual_cost": None,
                        "status": "unknown", "request_hash": HISTORICAL_REQUEST_HASH}
            if original != required:
                raise CostCoverageError("reviewed_cost_hold_changed")
            if any(value["actual_cost"] is None for key, value in actual["attempts"].items()
                   if key != HISTORICAL_ATTEMPT_ID):
                raise CostCoverageError("unreviewed_cost_uncertainty")
            return {HISTORICAL_ATTEMPT_ID: dict(required)}
        except CostCoverageError:
            raise
        except (OSError, ValueError, TypeError, KeyError, BudgetError):
            raise CostCoverageError("reviewed_cost_evidence_unavailable") from None


def load_cost_coverage(root: Path, ledger: BudgetLedger) -> ReviewedCostCoverage:
    """Load and validate a previously prepared record without writing anything."""
    root = Path(root).resolve()
    expected = build_cost_coverage_record(root)
    review = ReviewedCostCoverage(root, ledger, expected["record_hash"])
    review.validate()
    return review
