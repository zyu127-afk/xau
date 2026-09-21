from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import sqlite3
from .config import Settings


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    ok: bool
    critical: bool
    detail: str


class StartupChecker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run_local_checks(self) -> list[CheckResult]:
        results: list[CheckResult] = []
        config_dir = self.settings.paths.root / "Config"
        results.append(CheckResult("Config", config_dir.exists(), True, str(config_dir)))
        for name, path in (("Data", self.settings.paths.data), ("Logs", self.settings.paths.logs), ("Backup", self.settings.paths.backup), ("Runtime", self.settings.paths.runtime)):
            try:
                path.mkdir(parents=True, exist_ok=True)
                probe = path / ".gts_write_test"
                probe.write_text("ok", encoding="utf-8"); probe.unlink(missing_ok=True)
                results.append(CheckResult(name, True, True, f"writable: {path}"))
            except OSError as exc:
                results.append(CheckResult(name, False, True, str(exc)))
        try:
            sqlite3.connect(":memory:").execute("SELECT 1").fetchone()
            results.append(CheckResult("SQLite", True, True, "available"))
        except sqlite3.Error as exc:
            results.append(CheckResult("SQLite", False, True, str(exc)))
        ai = self.settings.raw.get("ai", {})
        ai_cfg = bool(ai.get("base_url") and ai.get("model") and self.settings.api_key)
        results.append(CheckResult("AI config", ai_cfg, False, "configured" if ai_cfg else "not configured; AI starts OFFLINE"))
        return results

    @staticmethod
    def serialize(results: list[CheckResult]) -> str:
        return json.dumps([asdict(x) for x in results], ensure_ascii=False)

    @staticmethod
    def critical_ok(results: list[CheckResult]) -> bool:
        return all(x.ok for x in results if x.critical)
