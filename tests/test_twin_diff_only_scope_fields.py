"""T2: enforce byte-level request differences at the two scope bindings only."""

import json

import pytest

from beyond_label.generate import generate_worlds, make_case
from beyond_label.render import decision_request


@pytest.mark.parametrize("dataset", ["pilot", "smoke", "main"])
@pytest.mark.parametrize("condition", ["MAIN", "HIGH-FEE", "HIGH-STAKES"])
def test_twins_change_exactly_two_scope_fields_in_every_outbound_prefix(dataset, condition):
    for world in generate_worlds(dataset):
        for load in (2, 8):
            for layout in ("separate", "inline"):
                a = make_case(world, twin="a", condition=condition, layout=layout, load=load)
                b = make_case(world, twin="b", condition=condition, layout=layout, load=load)
                req_a, req_b = decision_request(a).model_dump(), decision_request(b).model_dump()
                assert req_a["messages"][:3] == req_b["messages"][:3]
                assert req_a["tools"] == req_b["tools"]
                lines_a = req_a["messages"][3]["content"].splitlines()
                lines_b = req_b["messages"][3]["content"].splitlines()
                assert len(lines_a) == len(lines_b)
                differences = [(i, left, right) for i, (left, right) in enumerate(zip(lines_a, lines_b)) if left != right]
                assert len(differences) == 2
                changed_records = set()
                for index, left, right in differences:
                    changed_records.add(left.split(" | ")[0])
                    left_prefix, left_scope = left.rsplit("tested_configuration: ", 1)
                    right_prefix, right_scope = right.rsplit("tested_configuration: ", 1)
                    assert left_prefix == right_prefix
                    assert {left_scope, right_scope} == {world.current_configuration, world.other_configuration}
                    lines_b[index] = left
                assert changed_records == {r.record_id for r in a.public.records[:2]}
                req_b["messages"][3]["content"] = "\n".join(lines_b)
                assert json.dumps(req_a, sort_keys=True).encode() == json.dumps(req_b, sort_keys=True).encode()
                assert sorted(r.tested_configuration for r in a.public.records) == sorted(r.tested_configuration for r in b.public.records)
                assert a.public.targets == b.public.targets
                for ra, rb in zip(a.public.records, b.public.records):
                    assert ra.model_dump(exclude={"tested_configuration"}) == rb.model_dump(exclude={"tested_configuration"})
