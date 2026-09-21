from __future__ import annotations

import re
import subprocess
from pathlib import Path

from Tools.collect_diagnostics import redact

ROOT = Path(__file__).resolve().parents[1]


def _tracked_files() -> list[str]:
    try:
        out = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
    except Exception:
        return []
    return [x.strip() for x in out.splitlines() if x.strip()]


def test_diagnostics_redacts_common_credentials():
    text = "Authorization: Bearer abcDEF123\nAPI_KEY=supersecret\ntoken: xyz987\nsk-test_1234567890"
    out = redact(text)
    assert "abcDEF123" not in out
    assert "supersecret" not in out
    assert "xyz987" not in out
    assert "sk-test_1234567890" not in out
    assert "REDACTED" in out


def test_sensitive_runtime_files_are_gitignored():
    content = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for item in (
        "Config/secrets.local",
        "Config/config.yaml",
        "Config/paths.yaml",
        "Runtime/dashboard.token",
        "Runtime/acceptance-report.json",
        "Runtime/diagnostics/",
        ".env",
    ):
        assert item in content


def test_no_local_secret_files_are_tracked():
    tracked = set(_tracked_files())
    forbidden = {
        "Config/secrets.local",
        "Config/config.yaml",
        "Config/paths.yaml",
        ".env",
        "Runtime/dashboard.token",
        "Runtime/acceptance-report.json",
    }
    assert not (tracked & forbidden)


def test_no_obvious_live_api_key_literal_in_tracked_text():
    key_patterns = [
        re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
        re.compile(r"(?im)^\s*API_KEY\s*=\s*[^\s#][^\r\n]*$"),
    ]
    allowed_examples = {"Config/secrets.local.example"}
    hits: list[str] = []
    for rel in _tracked_files():
        if rel in allowed_examples:
            continue
        path = ROOT / rel
        try:
            if not path.is_file() or path.stat().st_size > 2_000_000:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(p.search(text) for p in key_patterns):
            hits.append(rel)
    assert not hits, f"possible credential literals found in tracked files: {hits}"
