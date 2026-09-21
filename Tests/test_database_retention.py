from datetime import datetime, timedelta, timezone
from Engine.goldtrading.database import Database
from Engine.goldtrading.retention import prune_rolling_data


def test_rolling_prune_does_not_delete_trades(tmp_path):
    db=Database(tmp_path/'test.db')
    old=(datetime.now(timezone.utc)-timedelta(days=120)).isoformat()
    db.execute("INSERT INTO MarketSnapshots(id,ts,payload) VALUES(?,?,?)",('s1',old,'{}'))
    db.execute("INSERT INTO Trades(id,entry_time,side,lot,entry_price,original_sl) VALUES(?,?,?,?,?,?)",('t1',old,'BUY',0.01,2500,2490))
    deleted=prune_rolling_data(db,90)
    assert deleted == 1
    assert len(db.fetchall("SELECT * FROM MarketSnapshots")) == 0
    assert len(db.fetchall("SELECT * FROM Trades")) == 1
