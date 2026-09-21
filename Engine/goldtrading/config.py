from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


class ConfigValidationError(ValueError):
    pass


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


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool):
        raise ConfigValidationError(f"{path} must be numeric")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigValidationError(f"{path} must be numeric") from exc


def _integer(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigValidationError(f"{path} must be an integer")
    return value


def _port(section: dict[str, Any], name: str) -> None:
    port = _integer(section.get("port"), f"{name}.port")
    if not 1 <= port <= 65535:
        raise ConfigValidationError(f"{name}.port must be 1..65535")


def _loopback(section: dict[str, Any], name: str) -> None:
    host = str(section.get("host", "")).strip().lower()
    if host not in LOOPBACK_HOSTS:
        raise ConfigValidationError(f"{name}.host must remain loopback-only")
    _port(section, name)


def validate_raw_config(raw: dict[str, Any]) -> None:
    if not isinstance(raw, dict):
        raise ConfigValidationError("config root must be a mapping")
    for name in ("system", "paths", "engine", "trading", "position_management", "mt5", "atas", "price_mapping", "ai", "history", "ui"):
        if not isinstance(raw.get(name), dict):
            raise ConfigValidationError(f"missing or invalid config section: {name}")

    system = raw["system"]
    if _integer(system.get("max_position_logics"), "system.max_position_logics") != 2:
        raise ConfigValidationError("V1 requires system.max_position_logics=2")

    trading = raw["trading"]
    if _number(trading.get("default_lot"), "trading.default_lot") <= 0:
        raise ConfigValidationError("trading.default_lot must be positive")
    if trading.get("weekend_protection") is not True:
        raise ConfigValidationError("V1 requires trading.weekend_protection=true")
    if trading.get("require_server_sl") is not True:
        raise ConfigValidationError("V1 requires trading.require_server_sl=true")
    flatten = _integer(trading.get("weekend_flatten_minutes"), "trading.weekend_flatten_minutes")
    if not 0 <= flatten <= 24 * 60:
        raise ConfigValidationError("trading.weekend_flatten_minutes must be 0..1440")
    if _number(trading.get("max_spread_points"), "trading.max_spread_points") <= 0:
        raise ConfigValidationError("trading.max_spread_points must be positive")

    for name in ("engine", "mt5", "atas", "ui"):
        _loopback(raw[name], name)
    # The current Dashboard publisher/client pair intentionally uses one canonical IPv4
    # loopback endpoint. Reject aliases here instead of accepting a value the runtime
    # would silently ignore and then failing later at startup.
    if str(raw["ui"].get("host", "")).strip() != "127.0.0.1":
        raise ConfigValidationError("V1 requires ui.host=127.0.0.1")
    if raw["atas"].get("require_mbo") not in (True, False):
        raise ConfigValidationError("atas.require_mbo must be boolean")
    if raw["mt5"].get("python_data_adapter") not in (True, False):
        raise ConfigValidationError("mt5.python_data_adapter must be boolean")

    engine = raw["engine"]
    if _number(engine.get("analysis_interval_seconds"), "engine.analysis_interval_seconds") <= 0:
        raise ConfigValidationError("engine.analysis_interval_seconds must be positive")
    if _number(engine.get("control_poll_seconds"), "engine.control_poll_seconds") <= 0:
        raise ConfigValidationError("engine.control_poll_seconds must be positive")

    mapping = raw["price_mapping"]
    window = _integer(mapping.get("rolling_window"), "price_mapping.rolling_window")
    minimum = _integer(mapping.get("min_samples"), "price_mapping.min_samples")
    if minimum < 2 or window < minimum:
        raise ConfigValidationError("price_mapping requires rolling_window >= min_samples >= 2")
    corr = _number(mapping.get("min_correlation"), "price_mapping.min_correlation")
    if not 0 <= corr <= 1:
        raise ConfigValidationError("price_mapping.min_correlation must be 0..1")
    if _number(mapping.get("max_residual"), "price_mapping.max_residual") <= 0:
        raise ConfigValidationError("price_mapping.max_residual must be positive")
    if _number(mapping.get("stale_seconds"), "price_mapping.stale_seconds") <= 0:
        raise ConfigValidationError("price_mapping.stale_seconds must be positive")

    atas = raw["atas"]
    if _number(atas.get("stale_seconds"), "atas.stale_seconds") <= 0:
        raise ConfigValidationError("atas.stale_seconds must be positive")

    ai = raw["ai"]
    if _number(ai.get("timeout_seconds"), "ai.timeout_seconds") <= 0:
        raise ConfigValidationError("ai.timeout_seconds must be positive")
    retry = _integer(ai.get("retry"), "ai.retry")
    if not 0 <= retry <= 10:
        raise ConfigValidationError("ai.retry must be 0..10")
    if _integer(ai.get("max_tokens"), "ai.max_tokens") <= 0:
        raise ConfigValidationError("ai.max_tokens must be positive")
    temperature = _number(ai.get("temperature"), "ai.temperature")
    if not 0 <= temperature <= 2:
        raise ConfigValidationError("ai.temperature must be 0..2")
    if _number(ai.get("minimum_interval_seconds"), "ai.minimum_interval_seconds") <= 0:
        raise ConfigValidationError("ai.minimum_interval_seconds must be positive")
    confidence = _number(ai.get("min_confidence"), "ai.min_confidence")
    if not 0 <= confidence <= 1:
        raise ConfigValidationError("ai.min_confidence must be 0..1")

    history = raw["history"]
    if _integer(history.get("rolling_days"), "history.rolling_days") < 90:
        raise ConfigValidationError("history.rolling_days must be at least 90")
    dedupe = _number(history.get("no_trade_dedupe_seconds", 15), "history.no_trade_dedupe_seconds")
    if not 0 <= dedupe <= 3600:
        raise ConfigValidationError("history.no_trade_dedupe_seconds must be 0..3600")


def load_settings(config_path: Path | None = None) -> Settings:
    config_path = config_path or PROJECT_ROOT / "Config" / "config.yaml"
    if not config_path.exists():
        example = PROJECT_ROOT / "Config" / "config.example.yaml"
        if not example.exists():
            raise FileNotFoundError("Config/config.yaml and config.example.yaml are both missing")
        config_path = example
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    validate_raw_config(raw)
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
