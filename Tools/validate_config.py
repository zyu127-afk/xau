from __future__ import annotations

from pathlib import Path
import yaml

from Engine.goldtrading.config import ConfigValidationError, validate_raw_config


ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "Config" / "config.yaml"
EXAMPLE = ROOT / "Config" / "config.example.yaml"


def fail(msg: str) -> None:
    print("ERROR:", msg)
    raise SystemExit(2)


def main() -> None:
    path = CFG if CFG.exists() else EXAMPLE
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    try:
        validate_raw_config(data)
    except ConfigValidationError as exc:
        fail(str(exc))
    secrets = ROOT / "Config" / "secrets.local"
    if secrets.exists() and secrets.stat().st_size > 0:
        print("OK: local secrets file present and gitignored")
    else:
        print("WARN: Config/secrets.local is absent; AI will remain offline")
    print("OK: V1 safety configuration validated:", path)


if __name__ == "__main__":
    main()
