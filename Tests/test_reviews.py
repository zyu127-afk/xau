from datetime import date

from Engine.goldtrading.database import Database
from Engine.goldtrading.review import build_daily_review, build_weekly_review, build_monthly_review


def insert_trade(db, *, trade_id, entry_time, exit_time, pnl):
    db.execute(
        "INSERT INTO Trades(id,entry_time,exit_time,side,lot,entry_price,exit_price,original_sl,current_sl,current_tp,mfe,mae,pnl,entry_reason,exit_reason,market_regime,orderflow_state,ai_snapshot,payload) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            trade_id,
            entry_time,
            exit_time,
            "BUY",
            0.01,
            2500,
            2510 if exit_time else None,
            2490,
            2500,
            None,
            12,
            3,
            pnl,
            "TREND_PULLBACK",
            "target" if exit_time else None,
            "TREND",
            "买方增强",
            "s1",
            "{}",
        ),
    )


def test_review_summaries_are_persisted(tmp_path):
    db = Database(tmp_path / "gts.db")
    insert_trade(
        db,
        trade_id="t1",
        entry_time="2026-09-20T10:00:00+00:00",
        exit_time="2026-09-20T10:30:00+00:00",
        pnl=10,
    )
    d = build_daily_review(db, date(2026, 9, 20))
    w = build_weekly_review(db, date(2026, 9, 20))
    m = build_monthly_review(db, date(2026, 9, 20))
    assert d["total_trades"] == 1 and d["net_profit"] == 10
    assert d["closed_trades"] == 1 and d["profit_complete"] is True
    assert w["total_trades"] == 1
    assert m["total_trades"] == 1
    rows = db.fetchall("SELECT period FROM ReviewSummaries ORDER BY period")
    assert {r["period"] for r in rows} == {"daily", "weekly", "monthly"}


def test_daily_profit_is_booked_on_exit_day_for_overnight_trade(tmp_path):
    db = Database(tmp_path / "gts.db")
    insert_trade(
        db,
        trade_id="overnight",
        entry_time="2026-09-20T23:55:00+00:00",
        exit_time="2026-09-21T00:15:00+00:00",
        pnl=7.5,
    )

    entry_day = build_daily_review(db, date(2026, 9, 20))
    exit_day = build_daily_review(db, date(2026, 9, 21))

    assert entry_day["entered_trades"] == 1
    assert entry_day["closed_trades"] == 0
    assert entry_day["net_profit"] == 0
    assert exit_day["entered_trades"] == 0
    assert exit_day["closed_trades"] == 1
    assert exit_day["net_profit"] == 7.5


def test_unknown_realized_pnl_is_not_silently_counted_as_zero(tmp_path):
    db = Database(tmp_path / "gts.db")
    insert_trade(
        db,
        trade_id="unknown-pnl",
        entry_time="2026-09-20T10:00:00+00:00",
        exit_time="2026-09-20T10:30:00+00:00",
        pnl=None,
    )

    review = build_daily_review(db, date(2026, 9, 20))

    assert review["profit_complete"] is False
    assert review["realized_pnl_unknown_count"] == 1
    assert review["net_profit"] is None
    assert review["expectancy"] is None
    assert review["known_net_profit"] == 0
