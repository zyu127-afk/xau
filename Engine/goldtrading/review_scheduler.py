from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from .database import Database
from .review import build_daily_review


async def daily_review_loop(db: Database) -> None:
    log = logging.getLogger("system")
    last_day = None
    while True:
        now = datetime.now(timezone.utc)
        completed_day = (now - timedelta(days=1)).date()
        if now.hour >= 0 and last_day != completed_day:
            try:
                review = build_daily_review(db, completed_day)
                log.info("daily review generated day=%s trades=%s net=%s", completed_day, review["total_trades"], review["net_profit"])
                last_day = completed_day
            except Exception:
                logging.getLogger("errors").exception("daily review generation failed")
        await asyncio.sleep(300)
