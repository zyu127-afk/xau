from types import SimpleNamespace

from Engine.goldtrading.database import Database
from Engine.goldtrading.trade_recorder import TradeRecorder


def guardian_state(*, active=True, bid=2605.0, ask=2605.2):
    base = {
        "bid": bid,
        "ask": ask,
        "slot_a_active": active,
        "slot_a_side": "BUY" if active else "",
        "slot_a_lot": 0.10 if active else 0.0,
        "slot_a_entry_price": 2600.0 if active else 0.0,
        "slot_a_original_sl": 2595.0 if active else 0.0,
        "slot_a_sl": 2598.0 if active else 0.0,
        "slot_a_tp": 2610.0 if active else 0.0,
        "slot_a_entry_time": 1_790_000_000 if active else 0,
        "slot_a_mfe": 5.0 if active else 0.0,
        "slot_a_mae": 1.0 if active else 0.0,
        "slot_b_active": False,
        "slot_b_side": "",
        "slot_b_lot": 0.0,
        "slot_b_entry_price": 0.0,
        "slot_b_original_sl": 0.0,
        "slot_b_sl": 0.0,
        "slot_b_tp": 0.0,
        "slot_b_entry_time": 0,
        "slot_b_mfe": 0.0,
        "slot_b_mae": 0.0,
    }
    return SimpleNamespace(**base)


def test_sync_recovers_missing_open_trade_from_guardian(tmp_path):
    db = Database(tmp_path / "trades.db")
    recorder = TradeRecorder(db)

    recorder.sync(guardian_state())

    rows = db.fetchall("SELECT * FROM Trades WHERE exit_time IS NULL")
    assert len(rows) == 1
    row = rows[0]
    assert row["side"] == "BUY"
    assert row["lot"] == 0.10
    assert row["entry_price"] == 2600.0
    assert row["original_sl"] == 2595.0
    assert row["current_sl"] == 2598.0
    assert row["mfe"] == 5.0
    assert row["mae"] == 1.0


def test_pending_open_context_is_bound_to_actual_guardian_fill(tmp_path):
    db = Database(tmp_path / "trades.db")
    recorder = TradeRecorder(db)
    recorder.note_open_ack(
        slot="A",
        trade_id="snap-123-BUY",
        side="BUY",
        entry_reason="TREND_PULLBACK: confirmed",
        market_regime="TREND",
        orderflow_state="买方增强",
        ai_snapshot="snap-123",
        payload={"mode": "TREND_PULLBACK"},
    )

    recorder.sync(guardian_state())

    rows = db.fetchall("SELECT * FROM Trades WHERE id=?", ("snap-123-BUY",))
    assert len(rows) == 1
    assert rows[0]["entry_price"] == 2600.0
    assert rows[0]["entry_reason"] == "TREND_PULLBACK: confirmed"
    assert rows[0]["market_regime"] == "TREND"
    assert rows[0]["orderflow_state"] == "买方增强"
    assert rows[0]["ai_snapshot"] == "snap-123"


def test_sync_closes_recovered_trade_when_guardian_slot_disappears(tmp_path):
    db = Database(tmp_path / "trades.db")
    recorder = TradeRecorder(db)
    recorder.sync(guardian_state())
    recorder.note_exit_reason("A", "dynamic exit")
    recorder.sync(guardian_state(active=False, bid=2607.0, ask=2607.2))

    rows = db.fetchall("SELECT exit_time,exit_price,exit_reason FROM Trades")
    assert rows[0]["exit_time"] is not None
    assert rows[0]["exit_price"] == 2607.0
    assert rows[0]["exit_reason"] == "dynamic exit"
