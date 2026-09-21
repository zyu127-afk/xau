from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class SecretRedactionFilter(logging.Filter):
    def __init__(self, secrets: list[str]) -> None:
        super().__init__()
        self.secrets = [s for s in secrets if s]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for secret in self.secrets:
            message = message.replace(secret, "***REDACTED***")
        record.msg = message
        record.args = ()
        return True


def configure_logging(log_dir: Path, api_key: str = "") -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)
    for name in ("system", "trading", "ai", "atas", "errors", "deployment"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        handler = RotatingFileHandler(log_dir / f"{name}.log", maxBytes=10_000_000, backupCount=10, encoding="utf-8")
        handler.setFormatter(formatter)
        handler.addFilter(SecretRedactionFilter([api_key]))
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.propagate = False
