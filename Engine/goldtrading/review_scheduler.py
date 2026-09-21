from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from .database import Database
from .review import build_daily_review, build_weekly_review, build_monthly_review


async def review_loop(db: Database) -> None:
    log = logging.getLogger("system")
    last_daily = None
    last_weekly = None
    last_monthly = None
    while True:
        now = datetime.now(timezone.utc)
        completed_day = (now - timedelta(days=1)).date()
        completed_week_day = (now.date() - timedelta(days=7))
        previous_month_anchor = (now.date().replace(day=1) - timedelta(days=1))

        if last_daily != completed_day:
            try:
                r = build_daily_review(db, completed_day)
                log.info("daily review generated day=%s trades=%s net=%s", completed_day, r["total_trades"], r["net_profit"])
                last_daily = completed_day
            except Exception:
                logging.getLogger("errors").exception("daily review generation failed")

        week_key = completed_week_day.isocalendar()[:2]
        if last_weekly != week_key:
            try:
                r = build_weekly_review(db, completed_week_day)
                log.info("weekly review generated key=%s trades=%s net=%s", r["review_key"], r["total_trades"], r["net_profit"])
                last_weekly = week_key
            except Exception:
                logging.getLogger("errors").exception("weekly review generation failed")

        month_key = (previous_month_anchor.year, previous_month_anchor.month)
        if last_monthly != month_key:
            try:
                r = build_monthly_review(db, previous_month_anchor)
                log.info("monthly review generated key=%s trades=%s net=%s", r["review_key"], r["total_trades"], r["net_profit"])
                last_monthly = month_key
            except Exception:
                logging.getLogger("errors").exception("monthly review generation failed")

        await asyncio.sleep(300)


async def daily_review_loop(db: Database) -> None:
    """Backward-compatible alias for older launchers/tests."""
    await review_loop(db)
