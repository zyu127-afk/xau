from __future__ import annotations

import json
from pathlib import Path

import yaml

from Tools import preflight

ROOT = Path(__file__).resolve().parents[1]


def test_preflight_required_repository_files_exist(monkeypatch, tmp_path):
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


def test_binding_status_exposes_no_machine_paths(monkeypatch, tmp_path):
    runtime = tmp_path / "Runtime"
    runtime.mkdir()
    experts = tmp_path / "secret-user-path" / "MQL5" / "Experts" / "GoldTradingSystem"
    experts.mkdir(parents=True)
    (experts / "GoldTradingGuardian.ex5").write_bytes(b"ex5")
    atas_target = tmp_path / "another-private-path" / "Indicators"
    atas_target.mkdir(parents=True)
    (atas_target / "GoldTradingDataBridge.ATAS.dll").write_bytes(b"dll")

    (runtime / "mt5-binding.json").write_text(json.dumps({
        "source_deployed": True,
        "compile_attempted": True,
        "ex5_compiled": True,
        "experts_path": str(experts),
        "metaeditor_path": "C:/private/metaeditor64.exe",
    }), encoding="utf-8")
    (runtime / "atas-binding.json").write_text(json.dumps({
        "deployed": True,
        "target_framework": "net8.0-windows",
        "target_path": str(atas_target),
        "sdk_path": "C:/private/ATAS",
    }), encoding="utf-8")

    monkeypatch.setattr(preflight, "RUNTIME", runtime)
    result = preflight._binding_status()
    encoded = json.dumps(result)
    assert result["mt5"]["record_exists"] is True
    assert result["mt5"]["ex5_exists_now"] is True
    assert result["atas"]["bridge_dll_exists_now"] is True
    assert result["atas"]["target_framework"] == "net8.0-windows"
    assert "secret-user-path" not in encoded
    assert "another-private-path" not in encoded
    assert "metaeditor" not in encoded.lower()
    assert "sdk_path" not in encoded
