"""Deterministic research-only worlds, public projections, and file manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random

from .schemas import Case, Condition, Dataset, Layout, Lot, PublicCase, Report, Twin, World

CONFIGURATIONS = ("R7", "M2", "K4", "T9", "Q3", "V8")
SEEDS = {"pilot": range(1000, 1008), "smoke": range(1100, 1104), "main": range(2000, 2064)}
POLARITIES = (("PASS", "PASS"), ("PASS", "FAIL"), ("FAIL", "PASS"), ("FAIL", "FAIL"))
GENERATOR_VERSION = "btl-worlds-v1"


def _rng(seed: int, namespace: str) -> random.Random:
    digest = hashlib.sha256(f"{GENERATOR_VERSION}:{seed}:{namespace}".encode()).digest()
    return random.Random(int.from_bytes(digest, "big"))


def generate_world(seed: int, dataset: Dataset | None = None) -> World:
    if dataset is None:
        dataset = next((name for name, seeds in SEEDS.items() if seed in seeds), None)
    if dataset not in SEEDS or seed not in SEEDS[dataset]:
        raise ValueError("Seed is outside the specified dataset")
    index = seed - SEEDS[dataset].start
    order = (index % 8) // 4
    polarity = POLARITIES[index % 4]
    names = _rng(seed, "identifiers")
    current, other = names.sample(CONFIGURATIONS, 2)
    lot_ids = [f"LOT-{n:04d}" for n in names.sample(range(1000, 10000), 8)]
    record_ids = [f"REC-{n:04d}" for n in names.sample(range(1000, 10000), 8)]
    canonical = [(record_ids[i], lot_ids[i], polarity[i]) for i in range(2)]
    if order:
        canonical.reverse()
    records = [Report(record_id=rid, lot_id=lid, result=result,
                      tested_configuration=(other if i == 0 else current))
               for i, (rid, lid, result) in enumerate(canonical)]
    for i in range(2, 8):
        records.append(Report(record_id=record_ids[i], lot_id=lot_ids[i],
                              result=names.choice(("PASS", "FAIL")),
                              tested_configuration=names.choice(CONFIGURATIONS)))
    metadata_order = [record.record_id for record in records]
    _rng(seed, "metadata").shuffle(metadata_order)
    hidden_rng = _rng(seed, "hidden-state")
    return World(world_id=f"{dataset}-{seed}", seed=seed, dataset=dataset, index=index,
                 report_order=order, polarity=polarity, current_configuration=current,
                 other_configuration=other, records=tuple(records),
                 metadata_order=tuple(metadata_order), high_stakes_index=(index // 8 + index % 2) % 2,
                 draws=(hidden_rng.random(), hidden_rng.random()))


def generate_worlds(dataset: Dataset) -> list[World]:
    return [generate_world(seed, dataset) for seed in SEEDS[dataset]]


def make_case(world: World, twin: Twin = "a", layout: Layout = "separate",
              condition: Condition = "MAIN", load: int = 2) -> Case:
    if twin not in ("a", "b") or layout not in ("separate", "inline") or load not in (2, 8):
        raise ValueError("Invalid case factors")
    if condition not in ("MAIN", "HIGH-FEE", "HIGH-STAKES", "MASKED", "NUMERIC"):
        raise ValueError("Invalid condition")
    scope = (world.other_configuration, world.current_configuration)
    if twin == "b":
        scope = tuple(reversed(scope))
    records = list(world.records[:load])
    states = {}
    for i in range(2):
        q = .9 if scope[i] == world.current_configuration else .6
        report = records[i]
        states[report.lot_id] = (report.result if world.draws[i] < q
                                 else ("FAIL" if report.result == "PASS" else "PASS"))
        records[i] = report.model_copy(update={"tested_configuration":
                                              "[withheld]" if condition == "MASKED" else scope[i]})
    ids = {r.record_id for r in records}
    public = PublicCase(
        current_configuration=world.current_configuration, records=tuple(records),
        targets=tuple(Lot(lot_id=records[i].lot_id,
                          penalty=800 if condition == "HIGH-STAKES" and i == world.high_stakes_index else 100)
                      for i in range(2)),
        metadata_order=tuple(rid for rid in world.metadata_order if rid in ids),
        fee=60 if condition == "HIGH-FEE" else 20,
    )
    return Case(world_id=world.world_id, seed=world.seed, twin=twin, layout=layout,
                condition=condition, load=load, public=public, hidden_states=states)


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def write_worlds(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    files = {}
    for dataset in SEEDS:
        name = f"worlds_{dataset}.jsonl"
        content = "".join(canonical_json(w.model_dump(mode="json")) + "\n" for w in generate_worlds(dataset))
        raw = content.encode("utf-8")
        (output / name).write_bytes(raw)
        files[name] = {"sha256": hashlib.sha256(raw).hexdigest(), "worlds": len(SEEDS[dataset]),
                       "seed_start": SEEDS[dataset].start, "seed_end": SEEDS[dataset].stop - 1}
    manifest = {"generator_version": GENERATOR_VERSION,
                "classification": "research_only_synthetic_world_inputs_not_empirical_observations",
                "contains_hidden_draws": True, "model_visible": False, "files": files}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data"))
    args = parser.parse_args()
    print(json.dumps(write_worlds(args.output), indent=2))


if __name__ == "__main__":
    main()
