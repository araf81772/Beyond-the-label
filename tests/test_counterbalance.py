from collections import Counter
from beyond_label.generate import CONFIGURATIONS, POLARITIES, generate_worlds, make_case


def test_exact_main_factorial_counts_and_control_stakes():
    worlds = generate_worlds("main")
    assert Counter((w.report_order, w.polarity) for w in worlds) == {
        (order, polarity): 8 for order in (0, 1) for polarity in POLARITIES}
    assert Counter(w.high_stakes_index for w in worlds[:16]) == {0: 8, 1: 8}
    assert Counter((w.report_order, w.polarity, w.high_stakes_index) for w in worlds[:16]) == {
        (order, polarity, high): 1 for order in (0, 1) for polarity in POLARITIES for high in (0, 1)}
    assert {w.current_configuration for w in worlds} == set(CONFIGURATIONS)
    assert len({w.target_ids for w in worlds}) == 64
    for w in worlds:
        expected_results = w.polarity if not w.report_order else tuple(reversed(w.polarity))
        assert tuple(r.result for r in w.records[:2]) == expected_results
        for load in (2, 8):
            a, b = make_case(w, "a", load=load), make_case(w, "b", load=load)
            assert a.public.target_ids == b.public.target_ids == w.target_ids
            assert a.public.metadata_order == b.public.metadata_order
            assert Counter(r.tested_configuration for r in a.public.records) == Counter(r.tested_configuration for r in b.public.records)
