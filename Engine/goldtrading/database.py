from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS MarketSnapshots(
  id TEXT PRIMARY KEY, ts TEXT NOT NULL, payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS OrderFlowEvents(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, event_type TEXT NOT NULL,
  gc_price REAL, mt5_price REAL, strength REAL, payload TEXT
);
CREATE TABLE IF NOT EXISTS PriceMapping(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, a REAL, b REAL,
  correlation REAL, latency_ms REAL, payload TEXT
);
CREATE TABLE IF NOT EXISTS AIAnalysis(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, snapshot_id TEXT,
  status TEXT NOT NULL, payload TEXT
);
CREATE TABLE IF NOT EXISTS NoTradeEvents(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, reason TEXT NOT NULL, payload TEXT
);
CREATE TABLE IF NOT EXISTS Trades(
  id TEXT PRIMARY KEY, entry_time TEXT NOT NULL, exit_time TEXT,
  side TEXT NOT NULL, lot REAL NOT NULL, entry_price REAL NOT NULL, exit_price REAL,
  original_sl REAL NOT NULL, current_sl REAL, current_tp REAL,
  mfe REAL DEFAULT 0, mae REAL DEFAULT 0, pnl REAL,
  entry_reason TEXT, exit_reason TEXT, market_regime TEXT,
  orderflow_state TEXT, ai_snapshot TEXT, payload TEXT
);
CREATE TABLE IF NOT EXISTS PositionEvents(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, position_id TEXT NOT NULL,
  event_type TEXT NOT NULL, payload TEXT
);
CREATE TABLE IF NOT EXISTS SystemEvents(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, level TEXT NOT NULL,
  component TEXT NOT NULL, event TEXT NOT NULL, payload TEXT
);
CREATE TABLE IF NOT EXISTS DailyReviews(
  day TEXT PRIMARY KEY, payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS Versions(
  version TEXT PRIMARY KEY, build_date TEXT, payload TEXT
);
CREATE INDEX IF NOT EXISTS idx_market_ts ON MarketSnapshots(ts);
CREATE INDEX IF NOT EXISTS idx_orderflow_ts ON OrderFlowEvents(ts);
CREATE INDEX IF NOT EXISTS idx_mapping_ts ON PriceMapping(ts);
CREATE INDEX IF NOT EXISTS idx_ai_ts ON AIAnalysis(ts);
CREATE INDEX IF NOT EXISTS idx_notrade_ts ON NoTradeEvents(ts);
CREATE INDEX IF NOT EXISTS idx_position_ts ON PositionEvents(ts);
CREATE INDEX IF NOT EXISTS idx_system_ts ON SystemEvents(ts);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        finally:
            db.close()

    def execute(self, sql: str, params: tuple = ()) -> None:
        with self.connect() as db:
            db.execute(sql, params)

    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self.connect() as db:
            return list(db.execute(sql, params).fetchall())
