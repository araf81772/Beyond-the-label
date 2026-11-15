"""Settle staged reservations that are still pending although a receipt exists.

A reservation is written before dispatch and settled after the reply. If the
settlement line never reached the ledger (for example a file-sync client
reverting an append), the ledger keeps the full hold while the run journal
holds the provider-reported cost for that exact request hash.

This script closes only that case. A pending reservation is settled when,
and only when, its request hash has exactly one journaled successful reply
whose cost is not yet matched by a settled ledger entry. The cost written is
the journaled provider-reported value. Reservations without such a receipt
stay held; nothing is ever set to zero, removed or rewritten, and the journal
is not touched. The ledger is append-only, so the correction is itself a
visible, hash-chained event.

No network and no credentials. Use ``--check`` to report without writing.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from beyond_label.budget import BudgetLedger  # noqa: E402
from beyond_label.gates import STAGED_SESSION, STAGED_STAGES  # noqa: E402
from beyond_label.paid_controls import paid_observed_cost  # noqa: E402
from beyond_label.run import Journal  # noqa: E402


def plan(root: Path) -> tuple[BudgetLedger, list[dict]]:
    ledger = BudgetLedger(root / STAGED_SESSION / "budget.jsonl", "9", "USD")
    state = ledger.snapshot()
    receipts: dict[str, list[dict]] = defaultdict(list)
    for stage, (_, _, directory) in STAGED_STAGES.items():
        path = root / directory / "calls.jsonl"
        if not path.is_file():
            continue
        for event in Journal(path).events:
            if event["event"] != "attempt_succeeded":
                continue
            cost = paid_observed_cost({"usage": event.get("usage", {})})
            if cost is not None:
                receipts[event["request_hash"]].append({
                    "stage": stage, "cell_id": event["cell_id"], "phase": event["phase"],
                    "attempt": event["attempt"], "cost": cost,
                    "request_id": event.get("result", {}).get("request_id")})
    settled = Counter((attempt["request_hash"], Decimal(attempt["actual_cost"]))
                      for attempt in state["attempts"].values() if attempt["actual_cost"] is not None)
    actions = []
    for attempt_id, attempt in state["attempts"].items():
        if attempt["status"] != "pending":
            continue
        unmatched = []
        remaining = Counter(settled)
        for receipt in receipts.get(attempt["request_hash"], []):
            key = (attempt["request_hash"], Decimal(receipt["cost"]))
            if remaining[key]:
                remaining[key] -= 1
            else:
                unmatched.append(receipt)
        if len(unmatched) == 1:
            actions.append({"attempt_id": attempt_id, "request_hash": attempt["request_hash"],
                            "reserved_usd": attempt["maximum_cost"], **unmatched[0]})
    return ledger, actions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Report only; write nothing")
    args = parser.parse_args()
    ledger, actions = plan(ROOT)
    before = ledger.snapshot()
    if not args.check:
        for action in actions:
            ledger.settle(action["attempt_id"], action["cost"], currency="USD")
    after = ledger.snapshot()
    summary = lambda state: {key: state[key] for key in (
        "settled_cost", "held", "available", "pending_attempts", "unknown_cost_attempts", "blocked")}
    print(json.dumps({"classification": "pending_reservation_settled_from_journaled_provider_receipt",
                      "written": bool(actions) and not args.check, "settlements": actions,
                      "ledger_before": summary(before), "ledger_after": summary(after)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
