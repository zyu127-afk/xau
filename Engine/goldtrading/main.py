from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from .config import load_settings
from .database import Database
from .logging_setup import configure_logging
from .price_alignment import PriceAlignmentEngine
from .positions import PositionBook


async def run() -> None:
    settings = load_settings()
    configure_logging(settings.paths.logs, settings.api_key)
    log = logging.getLogger("system")
    db = Database(settings.paths.data / "goldtrading.db")
    alignment = PriceAlignmentEngine()
    positions = PositionBook(max_positions=settings.max_position_logics)
    log.info("GoldTradingSystem engine starting")
    log.info("Database ready: %s", db.path)
    log.info("Logical position slots: %s", positions.fingerprint())
    log.info("Price alignment warming up: %s samples", len(alignment.samples))
    # Connectors are isolated tasks. A failed enhancement connector must not stop local state/history services.
    while True:
        await asyncio.sleep(1.0)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
