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
    assert estimate.rmse < 1e-10
    assert engine.quality_ok(min_correlation=0.99, max_residual=0.01, stale_seconds=5)
    assert abs(engine.map_gc_to_mt5(100.0) - 107.7) < 1e-9


def test_alignment_waits_for_warmup():
    engine = PriceAlignmentEngine(min_samples=5)
    for x in range(4):
        engine.add(x + 1, x + 2)
    assert engine.estimate() is None
    assert engine.quality_reason() == "WARMING_UP"


def test_contract_change_resets_mapping():
    engine = PriceAlignmentEngine(min_samples=3)
    engine.set_instrument("GCZ6")
    for x in range(3): engine.add(2000+x, 2100+x)
    assert engine.estimate() is not None
    assert engine.set_instrument("GCG7") is True
    assert engine.estimate() is None
    assert engine.instrument == "GCG7"


def test_extreme_single_outlier_is_ignored_after_warmup():
    engine = PriceAlignmentEngine(min_samples=5)
    for x in range(10): engine.add(2000+x, 2100+x)
    before = engine.estimate(); assert before is not None
    engine.add(2010, 9999)
    after = engine.estimate(); assert after is not None
    assert after.samples == before.samples
