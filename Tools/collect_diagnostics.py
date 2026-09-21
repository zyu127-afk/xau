from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "Runtime"
OUT = RUNTIME / "diagnostics"

_PATTERNS = [
    (re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s\"']+"), r"\1***REDACTED***"),
    (re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)[^\s\"']+"), r"\1***REDACTED***"),
    (re.compile(r"(?i)(secret\s*[=:]\s*)[^\s\"']+"), r"\1***REDACTED***"),
    (re.compile(r"(?i)(token\s*[=:]\s*)[^\s\"']+"), r"\1***REDACTED***"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"), "***REDACTED***"),
]


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _copy_text(src: Path, dst: Path) -> None:
    try:
        text = src.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(redact(text), encoding="utf-8")


def build(max_log_bytes: int = 1_000_000) -> Path:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = OUT / f"GoldTradingSystem_Diagnostics_{stamp}.zip"

    with tempfile.TemporaryDirectory(prefix="gts-diag-") as tmp:
        stage = Path(tmp) / "GoldTradingSystem_Diagnostics"
        stage.mkdir(parents=True)

        safe_files = [
            ROOT / "Version" / "version.json",
            ROOT / "Config" / "config.example.yaml",
            ROOT / "Config" / "paths.yaml",
            RUNTIME / "acceptance-report.json",
        ]
        for src in safe_files:
            if src.exists() and src.name not in {"secrets.local", ".env"}:
                _copy_text(src, stage / src.relative_to(ROOT))

        log_dir = ROOT / "Logs"
        if log_dir.exists():
            logs = sorted((p for p in log_dir.rglob("*") if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)[:20]
            for src in logs:
                try:
                    if src.stat().st_size > max_log_bytes:
                        text = src.read_text(encoding="utf-8", errors="replace")[-max_log_bytes:]
                        dst = stage / "Logs" / src.name
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        dst.write_text(redact(text), encoding="utf-8")
                    else:
                        _copy_text(src, stage / "Logs" / src.name)
                except OSError:
                    pass

        manifest = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "redacted": True,
            "excluded": ["Config/secrets.local", ".env", "API keys/tokens", "Data/*.db", "Backup/*"],
            "note": "This archive is for support diagnostics. It intentionally excludes credentials and trading databases.",
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in stage.rglob("*"):
                if p.is_file():
                    zf.write(p, p.relative_to(stage))
    return target


def main() -> int:
    ap = argparse.ArgumentParser(description="Create a redacted GoldTradingSystem diagnostics ZIP")
    ap.add_argument("--max-log-bytes", type=int, default=1_000_000)
    args = ap.parse_args()
    path = build(max_log_bytes=max(1_000, args.max_log_bytes))
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
