from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from Engine.goldtrading.config import ConfigValidationError, validate_raw_config

ROOT = Path(__file__).resolve().parents[1]
START_PS = (ROOT / "Tools" / "start_system.ps1").read_text(encoding="utf-8")
STOP_PS = (ROOT / "Tools" / "stop_system.ps1").read_text(encoding="utf-8")
START_BAT = (ROOT / "Start" / "启动系统.bat").read_text(encoding="utf-8")
STOP_BAT = (ROOT / "Start" / "停止系统.bat").read_text(encoding="utf-8")


def test_windows_launcher_tracks_only_its_own_processes():
    assert "Start-Process" in START_PS
    assert "-PassThru" in START_PS
    assert "Runtime\\processes.json" not in START_PS  # path is assembled under Runtime, not hard-coded outside root
    assert "processes.json" in START_PS
    assert "started_at_utc" in START_PS
    assert "executable=$py" in START_PS
    assert "Test-TrackedProcess" in START_PS


def test_normal_stop_is_pid_scoped_and_cannot_inherit_emergency_close():
    lowered = STOP_PS.lower()
    assert "taskkill" not in lowered
    assert "stop-process -id" in lowered
    assert "get-process -id" in lowered
    assert "started_at_utc" in STOP_PS
    assert "stop_system=$true" in STOP_PS
    assert "emergency_close_request=''" in STOP_PS
    assert "$state.emergency_close_request=[string]$existing.emergency_close_request" not in STOP_PS


def test_batch_entry_points_use_safe_process_manager():
    assert 'Tools\\start_system.ps1' in START_BAT
    assert 'Tools\\stop_system.ps1' in STOP_BAT
    assert "taskkill" not in (START_BAT + STOP_BAT).lower()


def test_runtime_process_registry_is_private_and_not_packaged():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    release = (ROOT / "Tools" / "build_release.ps1").read_text(encoding="utf-8")
    assert "Runtime/processes.json" in ignore
    assert "Runtime\\processes.json" in release


def test_dashboard_host_is_canonical_ipv4_loopback():
    cfg = yaml.safe_load((ROOT / "Config" / "config.example.yaml").read_text(encoding="utf-8"))
    assert cfg["ui"]["host"] == "127.0.0.1"
    validate_raw_config(cfg)
    changed = deepcopy(cfg)
    changed["ui"]["host"] = "localhost"
    with pytest.raises(ConfigValidationError, match=r"ui\.host=127\.0\.0\.1"):
        validate_raw_config(changed)
