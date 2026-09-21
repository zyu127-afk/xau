from __future__ import annotations

from datetime import datetime, timedelta, timezone
from .database import Database


ROLLING_TABLES = (
    "MarketSnapshots", "OrderFlowEvents", "PriceMapping", "AIAnalysis", "NoTradeEvents", "PositionEvents"
)


def prune_rolling_data(db: Database, days: int = 90) -> int:
    """Delete only rolling raw/detail data. Trades, reviews, versions and major system history stay permanent."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    deleted = 0
    with db.connect() as conn:
        for table in ROLLING_TABLES:
            cur = conn.execute(f"DELETE FROM {table} WHERE ts < ?", (cutoff,))
            deleted += max(0, cur.rowcount)
    return deleted
