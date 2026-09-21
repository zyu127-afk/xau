from datetime import date
from Engine.goldtrading.database import Database
from Engine.goldtrading.review import build_daily_review, build_weekly_review, build_monthly_review


def test_review_summaries_are_persisted(tmp_path):
    db=Database(tmp_path/'gts.db')
    db.execute("INSERT INTO Trades(id,entry_time,exit_time,side,lot,entry_price,exit_price,original_sl,current_sl,current_tp,mfe,mae,pnl,entry_reason,exit_reason,market_regime,orderflow_state,ai_snapshot,payload) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               ('t1','2026-09-20T10:00:00+00:00','2026-09-20T10:30:00+00:00','BUY',0.01,2500,2510,2490,2500,None,12,3,10,'TREND_PULLBACK','target','TREND','买方增强','s1','{}'))
    d=build_daily_review(db,date(2026,9,20))
    w=build_weekly_review(db,date(2026,9,20))
    m=build_monthly_review(db,date(2026,9,20))
    assert d['total_trades']==1 and d['net_profit']==10
    assert w['total_trades']==1
    assert m['total_trades']==1
    rows=db.fetchall('SELECT period FROM ReviewSummaries ORDER BY period')
    assert {r['period'] for r in rows}=={'daily','weekly','monthly'}
