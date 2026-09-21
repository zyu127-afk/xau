import json
import sys
from types import SimpleNamespace

from Engine.goldtrading.database import Database
from Engine.goldtrading.trade_recorder import TradeRecorder


def guardian_state(*, active=True, bid=2605.0, ask=2605.2):
    base = {
        "account": "123456",
        "symbol": "XAUUSD",
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
    assert row["pnl"] is None
    payload = json.loads(row["payload"])
    assert payload["symbol"] == "XAUUSD"
    assert payload["account"] == "123456"


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


def test_sync_closes_recovered_trade_without_inventing_pnl(tmp_path):
    db = Database(tmp_path / "trades.db")
    recorder = TradeRecorder(db)
    recorder.sync(guardian_state())
    recorder.note_exit_reason("A", "dynamic exit")
    recorder.sync(guardian_state(active=False, bid=2607.0, ask=2607.2))

    rows = db.fetchall("SELECT exit_time,exit_price,exit_reason,pnl FROM Trades")
    assert rows[0]["exit_time"] is not None
    assert rows[0]["exit_price"] == 2607.0
    assert rows[0]["exit_reason"] == "dynamic exit"
    assert rows[0]["pnl"] is None


def _closed_trade(db, trade_id="verified"):
    recorder = TradeRecorder(db)
    recorder.register_open(
        slot="A",
        trade_id=trade_id,
        side="BUY",
        lot=0.10,
        entry_price=2600.0,
        original_sl=2595.0,
        current_tp=2610.0,
        entry_reason="TREND_PULLBACK",
        market_regime="TREND",
        orderflow_state="买方增强",
        ai_snapshot="snap",
        entry_time=1_790_000_000,
        payload={"symbol": "XAUUSD"},
    )
    db.execute(
        "UPDATE Trades SET exit_time=?,exit_price=? WHERE id=?",
        (recorder._entry_time_iso(1_790_000_060), 2605.0, trade_id),
    )
    return recorder


def test_mt5_history_deals_verify_realized_pnl(monkeypatch, tmp_path):
    db = Database(tmp_path / "trades.db")
    recorder = _closed_trade(db)
    entry = SimpleNamespace(
        ticket=101,
        position_id=9001,
        entry=0,
        symbol="XAUUSD",
        comment="GTS-A",
        volume=0.10,
        time=1_790_000_000,
        price=2600.0,
        profit=0.0,
        commission=-0.50,
        swap=0.0,
        fee=0.0,
    )
    close = SimpleNamespace(
        ticket=102,
        position_id=9001,
        entry=1,
        symbol="XAUUSD",
        comment="",
        volume=0.10,
        time=1_790_000_060,
        price=2605.0,
        profit=50.0,
        commission=-0.50,
        swap=-0.10,
        fee=0.0,
    )
    fake_mt5 = SimpleNamespace(history_deals_get=lambda *_args, **_kwargs: [entry, close])
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake_mt5)

    assert recorder._verify_mt5_pnl("verified", "XAUUSD") is True

    row = db.fetchall("SELECT pnl,exit_price,payload FROM Trades WHERE id='verified'")[0]
    assert row["pnl"] == 48.9
    assert row["exit_price"] == 2605.0
    payload = json.loads(row["payload"])
    assert payload["pnl_verified"] == "MT5_HISTORY_DEALS"
    assert payload["broker_entry_deal"] == 101
    assert payload["broker_close_deal"] == 102


def test_mt5_history_deals_leave_ambiguous_shared_netting_close_unresolved(monkeypatch, tmp_path):
    db = Database(tmp_path / "trades.db")
    recorder = _closed_trade(db, "ambiguous")
    entry = SimpleNamespace(
        ticket=201,
        position_id=9002,
        entry=0,
        symbol="XAUUSD",
        comment="GTS-A",
        volume=0.10,
        time=1_790_000_000,
        price=2600.0,
        profit=0.0,
        commission=-0.50,
        swap=0.0,
        fee=0.0,
    )
    # One 0.20 close could represent A+B on a netting account. Do not guess A's share.
    shared_close = SimpleNamespace(
        ticket=202,
        position_id=9002,
        entry=1,
        symbol="XAUUSD",
        comment="",
        volume=0.20,
        time=1_790_000_060,
        price=2605.0,
        profit=100.0,
        commission=-1.0,
        swap=0.0,
        fee=0.0,
    )
    fake_mt5 = SimpleNamespace(history_deals_get=lambda *_args, **_kwargs: [entry, shared_close])
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake_mt5)

    assert recorder._verify_mt5_pnl("ambiguous", "XAUUSD") is False
    row = db.fetchall("SELECT pnl,payload FROM Trades WHERE id='ambiguous'")[0]
    assert row["pnl"] is None
    assert "broker_close_deal" not in json.loads(row["payload"])
