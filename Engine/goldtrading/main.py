from __future__ import annotations

import asyncio
import logging
from .config import load_settings
from .database import Database
from .logging_setup import configure_logging
from .runtime import Runtime


async def run() -> None:
    settings = load_settings()
    configure_logging(settings.paths.logs, settings.api_key)
    log = logging.getLogger("system")
    db = Database(settings.paths.data / "goldtrading.db")
    log.info("GoldTradingSystem engine starting")
    log.info("Database ready: %s", db.path)
    runtime = Runtime(settings, db)
    await runtime.run()


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
