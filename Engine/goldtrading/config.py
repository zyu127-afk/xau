from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class Paths:
    root: Path
    data: Path
    logs: Path
    backup: Path
    runtime: Path


@dataclass(frozen=True, slots=True)
class Settings:
    raw: dict[str, Any]
    paths: Paths
    api_key: str

    @property
    def default_lot(self) -> float:
        return float(self.raw.get("trading", {}).get("default_lot", 0.01))

    @property
    def max_position_logics(self) -> int:
        return int(self.raw.get("system", {}).get("max_position_logics", 2))


def _resolve(root: Path, value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (root / p).resolve()


def _read_secrets(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def load_settings(config_path: Path | None = None) -> Settings:
    config_path = config_path or PROJECT_ROOT / "Config" / "config.yaml"
    if not config_path.exists():
        example = PROJECT_ROOT / "Config" / "config.example.yaml"
        if not example.exists():
            raise FileNotFoundError("Config/config.yaml and config.example.yaml are both missing")
        config_path = example
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    p = raw.get("paths", {})
    paths = Paths(
        root=PROJECT_ROOT,
        data=_resolve(PROJECT_ROOT, str(p.get("data", "./Data"))),
        logs=_resolve(PROJECT_ROOT, str(p.get("logs", "./Logs"))),
        backup=_resolve(PROJECT_ROOT, str(p.get("backup", "./Backup"))),
        runtime=_resolve(PROJECT_ROOT, str(p.get("runtime", "./Runtime"))),
    )
    for folder in (paths.data, paths.logs, paths.backup, paths.runtime):
        folder.mkdir(parents=True, exist_ok=True)
    secret_file = raw.get("ai", {}).get("secrets_file", "./Config/secrets.local")
    secrets = _read_secrets(_resolve(PROJECT_ROOT, str(secret_file)))
    api_key = os.environ.get("GOLDTRADING_API_KEY") or secrets.get("API_KEY", "")
    return Settings(raw=raw, paths=paths, api_key=api_key)
