"""Trace-derived matched example and numeric evidence map, with evidence labels."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from .analyze import analyze_run
from .run import Journal


def _scalars(value, pointer=""):
    if type(value) in (int, float):
        yield pointer, value
    elif isinstance(value, dict):
        for key, item in value.items():
            if key not in ("pairs", "cells"):
                yield from _scalars(item, pointer + "/" + str(key).replace("~", "~0").replace("/", "~1"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _scalars(item, pointer + "/" + str(index))


def export_evidence(run_dir: Path | str, *, allow_synthetic: bool = False) -> dict:
    run_dir=Path(run_dir)
    analysis=analyze_run(run_dir,allow_synthetic=allow_synthetic)
    journal=Journal(run_dir/"calls.jsonl")
    candidates=[pair for pair in analysis["primary"]["pairs"] if pair["complete"]]
    example={"artifact_label":analysis["artifact_label"],"evidence_kind":analysis["evidence_kind"],
             "selection_rule":"lowest world seed with both MAIN separate-layout first actions observed",
             "human_review":False,"status":"no_complete_pair","twins":[]}
    if candidates:
        pair=min(candidates,key=lambda row:row["world_seed"])
        example.update(status="trace_derived",world_seed=pair["world_seed"],pair_category=pair["pair_category"])
        for twin in ("a","b"):
            cell_id=pair[f"{twin}_cell_id"]
            events=[event for event in journal.events if event["cell_id"]==cell_id]
            prefix=next(event["request"]["messages"] for event in events
                        if event["event"]=="phase_defined" and event["phase"]=="first")
            example["twins"].append({"twin":twin,"cell_id":cell_id,"decision_prefix":prefix,
                "responses":[{"phase":event["phase"],"reply":event["result"]["reply"]}
                             for event in events if event["event"]=="attempt_succeeded"],
                "tool_transitions":[event["transition"] for event in events if event["event"]=="tool_applied"]})
    output=run_dir/"analysis"
    (output/"matched_trace.json").write_text(json.dumps(example,indent=2)+'\n',encoding='utf-8',newline='\n')
    analysis_path=output/"analysis.json"
    analysis_hash=hashlib.sha256(analysis_path.read_bytes()).hexdigest()
    raw_hash=hashlib.sha256((run_dir/"calls.jsonl").read_bytes()).hexdigest()
    fields=["artifact_label","json_pointer","value","evidence_kind","source_file","source_sha256","raw_trace_sha256","regenerate_command"]
    with (output/"claim_evidence.csv").open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');writer.writeheader()
        for pointer,value in _scalars(analysis):
            if pointer.startswith('/main_expected_loss_reference_policies') or pointer.endswith('/oracle_reference_D'):
                kind="analytic_reference_not_observation"
            elif pointer.rsplit('/',1)[-1] in {'schema_version','bootstrap_seed','bootstrap_resamples','planned_cells','planned_worlds','planned','planned_denominator','null_probability'}:
                kind="design_or_configuration_metadata"
            else:
                kind=analysis["evidence_kind"]
            writer.writerow({"artifact_label":analysis["artifact_label"],"json_pointer":pointer,"value":value,
                "evidence_kind":kind,"source_file":"analysis/analysis.json","source_sha256":analysis_hash,
                "raw_trace_sha256":raw_hash,"regenerate_command":f'python -m beyond_label.evidence "{run_dir.as_posix()}"'+(' --allow-synthetic' if kind=='synthetic' or analysis['evidence_kind']=='synthetic' else '')})
    return {"artifact_label":analysis["artifact_label"],"matched_trace_status":example["status"],"output":str(output)}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('run_dir',type=Path);parser.add_argument('--allow-synthetic',action='store_true')
    args=parser.parse_args();print(json.dumps(export_evidence(args.run_dir,allow_synthetic=args.allow_synthetic)))


if __name__=='__main__':main()
