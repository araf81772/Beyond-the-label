"""T3: reconstruct report/lot/scope mapping from serialized model requests."""

import json
import re

import pytest

from beyond_label.generate import generate_worlds, make_case
from beyond_label.render import decision_request

REPORT = re.compile(r"^(REC-\d{4}) \| (LOT-\d{4}) \| result: (PASS|FAIL)(?: \| tested_configuration: (\S+))?$")
META = re.compile(r"^(REC-\d{4}) \| tested_configuration: (\S+)$")


@pytest.mark.parametrize("dataset", ["pilot", "smoke", "main"])
def test_record_mapping_survives_json_serialization_all_worlds(dataset):
    for world in generate_worlds(dataset):
        for load in (2, 8):
            for layout in ("separate", "inline"):
                for condition in ("MAIN", "HIGH-FEE", "HIGH-STAKES", "MASKED", "NUMERIC"):
                    for twin in ("a", "b"):
                        case = make_case(world, twin=twin, layout=layout, load=load, condition=condition)
                        payload = json.loads(decision_request(case).model_dump_json())
                        lines = payload["messages"][3]["content"].splitlines()
                        reports, metadata = {}, {}
                        for line in lines:
                            match = REPORT.match(line)
                            if match:
                                rid, lid, result, config = match.groups()
                                reports[rid] = (lid, result)
                                if config is not None:
                                    metadata[rid] = config
                            match = META.match(line)
                            if match:
                                metadata[match[1]] = match[2]
                        assert list(reports) == [record.record_id for record in case.public.records]
                        for record in case.public.records:
                            assert reports[record.record_id] == (record.lot_id, record.result)
                            if condition == "NUMERIC":
                                assert record.record_id not in metadata
                            else:
                                expected = "[withheld]" if condition == "MASKED" and record.lot_id in case.public.target_ids else record.tested_configuration
                                assert metadata[record.record_id] == expected
                        dispositions = lines[lines.index("LOTS TO DISPOSITION") + 1:][:2]
                        assert dispositions == [f"{lot.lot_id} | penalty if wrong: {lot.penalty}" for lot in case.public.targets]
