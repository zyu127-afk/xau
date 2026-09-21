from types import SimpleNamespace

from Engine.goldtrading.analysis_engine import AnalysisEngine
from Engine.goldtrading.database import Database


def make_engine(tmp_path, dedupe_seconds=15.0):
    db = Database(tmp_path / "audit.db")
    settings = SimpleNamespace(
        raw={"ai": {}, "history": {"no_trade_dedupe_seconds": dedupe_seconds}},
        api_key="",
        paths=SimpleNamespace(root=tmp_path),
    )
    runtime = SimpleNamespace(settings=settings, db=db)
    return AnalysisEngine(runtime), db


def test_same_no_trade_reason_and_payload_is_deduped(tmp_path):
    engine, db = make_engine(tmp_path)

    engine._record_no_trade("ATAS数据不新鲜", {"health": "OFFLINE"})
    engine._record_no_trade("ATAS数据不新鲜", {"health": "OFFLINE"})

    rows = db.fetchall("SELECT reason,payload FROM NoTradeEvents")
    assert len(rows) == 1
    assert rows[0]["reason"] == "ATAS数据不新鲜"


def test_distinct_no_trade_payloads_are_preserved(tmp_path):
    engine, db = make_engine(tmp_path)

    engine._record_no_trade("映射质量不足", {"reason": "LOW_CORRELATION"})
    engine._record_no_trade("映射质量不足", {"reason": "STALE"})

    rows = db.fetchall("SELECT reason,payload FROM NoTradeEvents ORDER BY id")
    assert len(rows) == 2
    assert "LOW_CORRELATION" in rows[0]["payload"]
    assert "STALE" in rows[1]["payload"]


def test_no_trade_event_can_be_recorded_again_after_dedupe_window(tmp_path):
    engine, db = make_engine(tmp_path, dedupe_seconds=10.0)
    engine._record_no_trade("等待确认")

    fingerprint = next(iter(engine._last_no_trade))
    engine._last_no_trade[fingerprint] -= 11.0
    engine._record_no_trade("等待确认")

    rows = db.fetchall("SELECT id FROM NoTradeEvents")
    assert len(rows) == 2
