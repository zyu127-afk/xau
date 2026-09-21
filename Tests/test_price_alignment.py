from Engine.goldtrading.price_alignment import PriceAlignmentEngine


def test_alignment_recovers_linear_mapping():
    engine = PriceAlignmentEngine(window=100, min_samples=30)
    for x in range(1, 61):
        engine.add(float(x), 1.002 * x + 7.5)
    estimate = engine.estimate()
    assert estimate is not None
    assert abs(estimate.a - 1.002) < 1e-10
    assert abs(estimate.b - 7.5) < 1e-10
    assert estimate.correlation > 0.999999
    assert abs(engine.map_gc_to_mt5(100.0) - 107.7) < 1e-9


def test_alignment_waits_for_warmup():
    engine = PriceAlignmentEngine(min_samples=5)
    for x in range(4):
        engine.add(x + 1, x + 2)
    assert engine.estimate() is None
