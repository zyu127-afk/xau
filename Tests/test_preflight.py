from __future__ import annotations

from pathlib import Path

import yaml

from Tools import preflight

ROOT = Path(__file__).resolve().parents[1]


def test_preflight_required_repository_files_exist(monkeypatch, tmp_path):
    # Use the real repository root but redirect the generated report so CI remains clean.
    monkeypatch.setattr(preflight, "REPORT", tmp_path / "acceptance-report.json")
    report = preflight.run(probe_mt5=False)
    assert report["required_files"]
    assert all(report["required_files"].values())
    assert "MT5/GoldTradingGuardian.mq5" in report["required_files"]
    assert "MT5/GuardianIPC.mqh" in report["required_files"]


def test_preflight_ports_follow_config_example(monkeypatch, tmp_path):
    monkeypatch.setattr(preflight, "REPORT", tmp_path / "acceptance-report.json")
    report = preflight.run(probe_mt5=False)
    cfg = yaml.safe_load((ROOT / "Config" / "config.example.yaml").read_text(encoding="utf-8"))
    assert report["ports"]["engine"] == cfg["engine"]["port"]
    assert report["ports"]["atas"] == cfg["atas"]["port"]
    assert report["ports"]["ui"] == cfg["ui"]["port"]
    assert report["read_only"] is True
    assert report["mt5_probe"] == {"requested": False}
