from __future__ import annotations

from pathlib import Path

from Tools.collect_diagnostics import redact

ROOT = Path(__file__).resolve().parents[1]


def test_diagnostics_redacts_account_and_login_identifiers():
    text = "account=12345678\nlogin: 87654321\naccount_login=11223344"
    out = redact(text)
    assert "12345678" not in out
    assert "87654321" not in out
    assert "11223344" not in out
    assert out.count("REDACTED") >= 3


def test_diagnostics_redacts_windows_absolute_paths():
    text = "terminal=C:\\Users\\ExampleUser\\AppData\\Roaming\\Terminal\\ABC\nproject=D:\\Trading\\GoldSystem\\Logs\\system.log"
    out = redact(text)
    assert "ExampleUser" not in out
    assert "D:\\Trading\\GoldSystem" not in out
    assert "LOCAL_PATH" in out


def test_diagnostics_source_does_not_package_machine_path_config():
    source = (ROOT / "Tools" / "collect_diagnostics.py").read_text(encoding="utf-8")
    safe_block = source.split("safe_files = [", 1)[1].split("]", 1)[0]
    assert '"paths.yaml"' not in safe_block
    assert '"processes.json"' not in safe_block
    assert '"mt5-binding.json"' not in safe_block
    assert '"atas-binding.json"' not in safe_block
