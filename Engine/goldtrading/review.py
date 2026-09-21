from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from .database import Database


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _safe_json(payload: str | None) -> dict:
    if not payload:
        return {}
    try:
        value = json.loads(payload)
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _duration_seconds(entry: str | None, exit_: str | None) -> float | None:
    if not entry or not exit_:
        return None
    try:
        a = datetime.fromisoformat(entry.replace("Z", "+00:00"))
        b = datetime.fromisoformat(exit_.replace("Z", "+00:00"))
        return max(0.0, (b - a).total_seconds())
    except ValueError:
        return None


def _realized_move(row) -> float | None:
    if row["exit_price"] is None:
        return None
    entry = float(row["entry_price"])
    exit_price = float(row["exit_price"])
    side = str(row["side"] or "").upper()
    if side == "BUY":
        return exit_price - entry
    if side == "SELL":
        return entry - exit_price
    return None


def build_period_review(db: Database, start: datetime, end: datetime, period: str, review_key: str) -> dict:
    start_s, end_s = _iso(start), _iso(end)
    entered = db.fetchall("SELECT * FROM Trades WHERE entry_time>=? AND entry_time<? ORDER BY entry_time", (start_s, end_s))
    closed = db.fetchall("SELECT * FROM Trades WHERE exit_time>=? AND exit_time<? ORDER BY exit_time", (start_s, end_s))
    no_trade = db.fetchall("SELECT reason FROM NoTradeEvents WHERE ts>=? AND ts<?", (start_s, end_s))
    ai_rows = db.fetchall("SELECT status,payload FROM AIAnalysis WHERE ts>=? AND ts<?", (start_s, end_s))
    errors = db.fetchall("SELECT level,component,event FROM SystemEvents WHERE ts>=? AND ts<? AND upper(level) IN ('ERROR','CRITICAL')", (start_s, end_s))

    known_closed = [r for r in closed if r["pnl"] is not None]
    unknown_closed = [r for r in closed if r["pnl"] is None]
    pnls = [float(r["pnl"]) for r in known_closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    durations = [x for x in (_duration_seconds(r["entry_time"], r["exit_time"]) for r in closed) if x is not None]
    mfe = [float(r["mfe"] or 0.0) for r in closed]
    mae = [float(r["mae"] or 0.0) for r in closed]
    givebacks: list[float] = []
    for row in closed:
        move = _realized_move(row)
        if move is not None:
            givebacks.append(max(0.0, float(row["mfe"] or 0.0) - max(move, 0.0)))

    mode_count = Counter()
    for r in entered:
        reason = str(r["entry_reason"] or "").lower()
        mode = "其他"
        if "trend_pullback" in reason or "趋势回调" in reason:
            mode = "趋势回调"
        elif "breakout" in reason or "突破" in reason:
            mode = "突破回踩"
        elif "reversal" in reason or "反转" in reason:
            mode = "极值反转"
        mode_count[mode] += 1

    mode_profit = Counter()
    mode_unknown = Counter()
    atas_confirmed_pnls: list[float] = []
    atas_confirmed_unknown = 0
    for r in closed:
        reason = str(r["entry_reason"] or "").lower()
        mode = "其他"
        if "trend_pullback" in reason or "趋势回调" in reason:
            mode = "趋势回调"
        elif "breakout" in reason or "突破" in reason:
            mode = "突破回踩"
        elif "reversal" in reason or "反转" in reason:
            mode = "极值反转"
        if r["pnl"] is None:
            mode_unknown[mode] += 1
        else:
            mode_profit[mode] += float(r["pnl"])
        if str(r["orderflow_state"] or "").strip():
            if r["pnl"] is None:
                atas_confirmed_unknown += 1
            else:
                atas_confirmed_pnls.append(float(r["pnl"]))

    latencies: list[float] = []
    stale = 0
    for row in ai_rows:
        payload = _safe_json(row["payload"])
        raw = payload.get("latency_ms")
        if isinstance(raw, (int, float)):
            latencies.append(float(raw))
    for row in no_trade:
        if "AI_SIGNAL_STALE" in str(row["reason"]):
            stale += 1

    profit_complete = len(unknown_closed) == 0
    known_net = sum(pnls)
    known_expectancy = (known_net / len(known_closed)) if known_closed else 0.0
    review = {
        "review_key": review_key,
        "period": period,
        "start": start_s,
        "end": end_s,
        "entered_trades": len(entered),
        "total_trades": len(entered),
        "closed_trades": len(closed),
        "open_from_period": sum(1 for r in entered if r["exit_time"] is None),
        "realized_pnl_known_count": len(known_closed),
        "realized_pnl_unknown_count": len(unknown_closed),
        "profit_complete": profit_complete,
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "gross_profit": sum(wins) if profit_complete else None,
        "gross_loss": sum(losses) if profit_complete else None,
        "net_profit": known_net if profit_complete else None,
        "expectancy": known_expectancy if profit_complete else None,
        "known_gross_profit": sum(wins),
        "known_gross_loss": sum(losses),
        "known_net_profit": known_net,
        "known_expectancy": known_expectancy,
        "max_trade_profit": max(pnls) if pnls else None,
        "max_trade_loss": min(pnls) if pnls else None,
        "max_mfe": max(mfe, default=0.0),
        "max_mae": max(mae, default=0.0),
        "max_mfe_giveback_price": max(givebacks, default=0.0),
        "average_holding_seconds": sum(durations) / len(durations) if durations else 0.0,
        "long_entries": sum(1 for r in entered if str(r["side"]).upper() == "BUY"),
        "short_entries": sum(1 for r in entered if str(r["side"]).upper() == "SELL"),
        "long_count": sum(1 for r in entered if str(r["side"]).upper() == "BUY"),
        "short_count": sum(1 for r in entered if str(r["side"]).upper() == "SELL"),
        "mode_count": dict(mode_count),
        "mode_known_net_profit": dict(mode_profit),
        "mode_unknown_pnl_count": dict(mode_unknown),
        "atas_confirmed_closed_count": len(atas_confirmed_pnls) + atas_confirmed_unknown,
        "atas_confirmed_known_net_profit": sum(atas_confirmed_pnls),
        "atas_confirmed_unknown_pnl_count": atas_confirmed_unknown,
        "ai_average_latency_ms": sum(latencies) / len(latencies) if latencies else None,
        "ai_stale_signal_count": stale,
        "ai_status": dict(Counter(r["status"] for r in ai_rows)),
        "no_trade_reasons": dict(Counter(r["reason"] for r in no_trade)),
        "system_error_count": len(errors),
        "optimization_focus": ["总利润", "期望收益", "大亏损控制", "MFE利用率", "MAE", "利润回吐", "平均每笔收益", "不同交易模式收益"],
    }
    encoded = json.dumps(review, ensure_ascii=False)
    db.execute(
        "INSERT OR REPLACE INTO ReviewSummaries(review_key,period,start_ts,end_ts,payload) VALUES(?,?,?,?,?)",
        (review_key, period, start_s, end_s, encoded),
    )
    return review


def build_daily_review(db: Database, day: date) -> dict:
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    review = build_period_review(db, start, end, "daily", f"day:{day.isoformat()}")
    db.execute("INSERT OR REPLACE INTO DailyReviews(day,payload) VALUES(?,?)", (day.isoformat(), json.dumps(review, ensure_ascii=False)))
    return review


def build_weekly_review(db: Database, day_in_week: date) -> dict:
    monday = day_in_week - timedelta(days=day_in_week.weekday())
    start = datetime.combine(monday, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=7)
    iso = monday.isocalendar()
    return build_period_review(db, start, end, "weekly", f"week:{iso.year}-W{iso.week:02d}")


def build_monthly_review(db: Database, day_in_month: date) -> dict:
    first = day_in_month.replace(day=1)
    if first.month == 12:
        next_first = first.replace(year=first.year + 1, month=1)
    else:
        next_first = first.replace(month=first.month + 1)
    start = datetime.combine(first, time.min, tzinfo=timezone.utc)
    end = datetime.combine(next_first, time.min, tzinfo=timezone.utc)
    return build_period_review(db, start, end, "monthly", f"month:{first.year:04d}-{first.month:02d}")
