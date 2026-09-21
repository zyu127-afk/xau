from Engine.goldtrading.position_manager import DynamicPositionManager, SlotTelemetry


def slot():
    return SlotTelemetry(
        active=True, side="BUY", lot=0.01, entry_price=2500.0,
        original_sl=2490.0, current_sl=2490.0, current_tp=0.0,
        entry_time=0, mfe=0.0, mae=0.0,
    )


def test_break_even_after_one_r():
    m = DynamicPositionManager(); s = slot(); d = m.evaluate(s, 2510.5)
    assert d.action == "MODIFY_SL" and d.stop_loss == 2500.0


def test_profit_lock_after_one_point_five_r():
    m = DynamicPositionManager(); s = slot(); d = m.evaluate(s, 2516.0)
    assert d.action == "MODIFY_SL" and d.stop_loss == 2505.0


def test_original_r_survives_current_stop_move():
    m = DynamicPositionManager(); s = slot(); s.current_sl = 2500.0
    d = m.evaluate(s, 2516.0)
    assert d.action == "MODIFY_SL" and d.stop_loss == 2505.0


def test_mfe_giveback_closes():
    m = DynamicPositionManager(); s = slot(); s.mfe = 25.0; d = m.evaluate(s, 2508.0)
    assert d.action == "CLOSE"
