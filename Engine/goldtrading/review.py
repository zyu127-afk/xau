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


def build_period_review(db: Database, start: datetime, end: datetime, period: str, review_key: str) -> dict:
    start_s, end_s = _iso(start), _iso(end)
    trades = db.fetchall("SELECT * FROM Trades WHERE entry_time>=? AND entry_time<? ORDER BY entry_time", (start_s, end_s))
    no_trade = db.fetchall("SELECT reason FROM NoTradeEvents WHERE ts>=? AND ts<?", (start_s, end_s))
    ai_rows = db.fetchall("SELECT status,payload FROM AIAnalysis WHERE ts>=? AND ts<?", (start_s, end_s))
    errors = db.fetchall("SELECT level,component,event FROM SystemEvents WHERE ts>=? AND ts<? AND upper(level) IN ('ERROR','CRITICAL')", (start_s, end_s))

    pnls = [float(r["pnl"] or 0.0) for r in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    durations = [x for x in (_duration_seconds(r["entry_time"], r["exit_time"]) for r in trades) if x is not None]
    mfe = [float(r["mfe"] or 0.0) for r in trades]
    mae = [float(r["mae"] or 0.0) for r in trades]
    givebacks = [max(0.0, float(r["mfe"] or 0.0) - max(float(r["pnl"] or 0.0), 0.0)) for r in trades]

    mode_profit = Counter()
    mode_count = Counter()
    atas_confirmed = []
    for r in trades:
        reason = str(r["entry_reason"] or "").lower()
        mode = "其他"
        if "trend_pullback" in reason or "趋势回调" in reason: mode = "趋势回调"
        elif "breakout" in reason or "突破" in reason: mode = "突破回踩"
        elif "reversal" in reason or "反转" in reason: mode = "极值反转"
        mode_count[mode] += 1
        mode_profit[mode] += float(r["pnl"] or 0.0)
        if str(r["orderflow_state"] or "").strip():
            atas_confirmed.append(float(r["pnl"] or 0.0))

    latencies: list[float] = []
    stale = 0
    for row in ai_rows:
        payload = _safe_json(row["payload"])
        raw = payload.get("latency_ms")
        if isinstance(raw, (int, float)):
            latencies.append(float(raw))
    for row in no_trade:
        if "AI_SIGNAL_STALE" in str(row["reason"]): stale += 1

    expectancy = (sum(pnls) / len(pnls)) if pnls else 0.0
    review = {
        "review_key": review_key,
        "period": period,
        "start": start_s,
        "end": end_s,
        "total_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "gross_profit": sum(wins),
        "gross_loss": sum(losses),
        "net_profit": sum(pnls),
        "expectancy": expectancy,
        "max_trade_profit": max(pnls, default=0.0),
        "max_trade_loss": min(pnls, default=0.0),
        "max_mfe": max(mfe, default=0.0),
        "max_mae": max(mae, default=0.0),
        "max_mfe_giveback": max(givebacks, default=0.0),
        "average_holding_seconds": sum(durations) / len(durations) if durations else 0.0,
        "long_count": sum(1 for r in trades if str(r["side"]).upper() == "BUY"),
        "short_count": sum(1 for r in trades if str(r["side"]).upper() == "SELL"),
        "mode_count": dict(mode_count),
        "mode_net_profit": dict(mode_profit),
        "atas_confirmed_count": len(atas_confirmed),
        "atas_confirmed_net_profit": sum(atas_confirmed),
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
