from __future__ import annotations

import json
from collections import Counter
from datetime import date
from .database import Database


def build_daily_review(db: Database, day: date) -> dict:
    prefix = day.isoformat()
    trades = db.fetchall("SELECT * FROM Trades WHERE substr(entry_time,1,10)=?", (prefix,))
    no_trade = db.fetchall("SELECT reason FROM NoTradeEvents WHERE substr(ts,1,10)=?", (prefix,))
    ai_rows = db.fetchall("SELECT status,payload FROM AIAnalysis WHERE substr(ts,1,10)=?", (prefix,))
    pnls = [float(r["pnl"] or 0.0) for r in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    long_rows = [r for r in trades if str(r["side"]).upper() == "BUY"]
    short_rows = [r for r in trades if str(r["side"]).upper() == "SELL"]
    review = {
        "day": prefix,
        "total_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "gross_profit": sum(wins),
        "gross_loss": sum(losses),
        "net_profit": sum(pnls),
        "max_trade_profit": max(pnls, default=0.0),
        "max_trade_loss": min(pnls, default=0.0),
        "max_mfe_giveback": max((float(r["mfe"] or 0.0) - max(float(r["pnl"] or 0.0), 0.0) for r in trades), default=0.0),
        "long_count": len(long_rows),
        "short_count": len(short_rows),
        "no_trade_reasons": Counter(r["reason"] for r in no_trade),
        "ai_status": Counter(r["status"] for r in ai_rows),
        "optimization_focus": ["总利润", "期望收益", "大亏损控制", "MFE利用率", "MAE", "利润回吐", "平均每笔收益", "不同交易模式收益"],
    }
    db.execute("INSERT OR REPLACE INTO DailyReviews(day,payload) VALUES(?,?)", (prefix, json.dumps(review, ensure_ascii=False, default=dict)))
    return review
