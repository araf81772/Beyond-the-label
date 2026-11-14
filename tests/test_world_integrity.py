import json
import pytest
from pydantic import ValidationError
from beyond_label.generate import SEEDS, generate_world, generate_worlds, make_case, write_worlds
from beyond_label.schemas import Case, PublicCase, World


@pytest.mark.parametrize("dataset", SEEDS)
def test_seedsets_deterministic_and_independent_research_state(dataset, tmp_path):
    worlds = generate_worlds(dataset)
    assert [w.seed for w in worlds] == list(SEEDS[dataset])
    assert worlds == generate_worlds(dataset)
    for w in worlds:
        assert len(set(w.draws)) == 2
        assert len(w.records) == 8
        assert len({r.lot_id for r in w.records}) == 8
        for twin in ("a", "b"):
            c = make_case(w, twin)
            assert sum(r.tested_configuration == c.public.current_configuration for r in c.public.records) == 1
            for i, report in enumerate(c.public.records):
                q = .9 if (twin == "a" and i == 1) or (twin == "b" and i == 0) else .6
                expected = report.result if w.draws[i] < q else ("PASS" if report.result == "FAIL" else "FAIL")
                assert c.hidden_states[report.lot_id] == expected
            assert "draws" not in c.public.model_dump_json()
        assert World.model_validate_json(w.model_dump_json()) == w
    first = write_worlds(tmp_path)
    assert write_worlds(tmp_path) == first
    for name, entry in first["files"].items():
        import hashlib
        raw = (tmp_path / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry["sha256"]
        assert len(raw.splitlines()) == entry["worlds"]
        assert all(json.loads(line)["dataset"] in SEEDS for line in raw.splitlines())


@pytest.mark.parametrize("u, expected_a, expected_b", [(0.59, True, True), (.6, False, True), (.899, False, True), (.9, False, False)])
def test_shared_draw_boundary_for_lot1(u, expected_a, expected_b):
    w = generate_world(2000).model_copy(update={"draws": (u, .2)})
    lot = w.records[0]
    assert (make_case(w, "a").hidden_states[lot.lot_id] == lot.result) == expected_a
    assert (make_case(w, "b").hidden_states[lot.lot_id] == lot.result) == expected_b


def test_reject_inconsistent_worlds_and_case_factors():
    w = generate_world(2000)
    invalid = w.model_dump()
    invalid["draws"] = [1.0, .5]
    with pytest.raises(ValidationError):
        World.model_validate(invalid)
    for kwargs in ({"twin": "x"}, {"load": 3}, {"layout": "other"}, {"condition": "OTHER"}):
        with pytest.raises(ValueError):
            make_case(w, **kwargs)
    with pytest.raises(ValueError):
        generate_world(9999)


@pytest.mark.parametrize("mutation", ["targets", "metadata", "load", "states", "dataset", "polarity"])
def test_reject_compound_schema_inconsistency(mutation):
    world = generate_world(2001)
    case = make_case(world)
    if mutation in ("targets", "metadata"):
        data = case.public.model_dump()
        if mutation == "targets":
            data["targets"] = (data["targets"][0], data["targets"][0])
        else:
            data["metadata_order"] = ()
        model = PublicCase
    elif mutation in ("load", "states"):
        data = case.model_dump()
        data["load" if mutation == "load" else "hidden_states"] = 8 if mutation == "load" else {}
        model = Case
    else:
        data = world.model_dump()
        data["dataset" if mutation == "dataset" else "polarity"] = "pilot" if mutation == "dataset" else ("PASS", "PASS")
        model = World
    with pytest.raises(ValidationError):
        model.model_validate(data)
