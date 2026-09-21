from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "Runtime"
REPORT = RUNTIME / "acceptance-report.json"


def _tcp(host: str, port: int, timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except Exception:
        return {}
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _safe_secret_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "api_key_present": False}
    present = False
    try:
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if line.startswith("API_KEY=") and line.split("=", 1)[1].strip():
                present = True
                break
    except OSError:
        pass
    return {"exists": True, "api_key_present": present}


def _binding_status() -> dict[str, Any]:
    mt5 = _read_json(RUNTIME / "mt5-binding.json")
    atas = _read_json(RUNTIME / "atas-binding.json")

    mt5_ex5_exists = False
    experts_path = str(mt5.get("experts_path", "") or "")
    if experts_path:
        try:
            mt5_ex5_exists = (Path(experts_path) / "GoldTradingGuardian.ex5").exists()
        except OSError:
            mt5_ex5_exists = False

    atas_dll_exists = False
    target_path = str(atas.get("target_path", "") or "")
    if target_path:
        try:
            atas_dll_exists = (Path(target_path) / "GoldTradingDataBridge.ATAS.dll").exists()
        except OSError:
            atas_dll_exists = False

    # Deliberately omit all machine paths from the support-safe report.
    return {
        "mt5": {
            "record_exists": bool(mt5),
            "source_deployed": bool(mt5.get("source_deployed", False)),
            "compile_attempted": bool(mt5.get("compile_attempted", False)),
            "ex5_compiled": bool(mt5.get("ex5_compiled", False)),
            "ex5_exists_now": mt5_ex5_exists,
        },
        "atas": {
            "record_exists": bool(atas),
            "deployed": bool(atas.get("deployed", False)),
            "target_framework": str(atas.get("target_framework", "") or ""),
            "bridge_dll_exists_now": atas_dll_exists,
        },
        "dotnet_sdk_available": shutil.which("dotnet") is not None,
    }


def _candidate_paths() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {"mt5_terminal": [], "metaeditor": [], "atas": []}
    if os.name != "nt":
        return found

    roots = [
        Path(os.environ.get("PROGRAMFILES", "C:/Program Files")),
        Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")),
        Path(os.environ.get("LOCALAPPDATA", "")),
    ]
    for base in roots:
        if not str(base):
            continue
        try:
            for p in base.rglob("terminal64.exe"):
                found["mt5_terminal"].append(str(p))
                if len(found["mt5_terminal"]) >= 8:
                    break
            for p in base.rglob("metaeditor64.exe"):
                found["metaeditor"].append(str(p))
                if len(found["metaeditor"]) >= 8:
                    break
        except (OSError, PermissionError):
            pass

    local = Path(os.environ.get("LOCALAPPDATA", ""))
    program_files = Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
    for p in [program_files / "ATAS", program_files / "ATAS Platform", local / "ATAS", local / "ATAS Platform", local / "Programs" / "ATAS"]:
        if p.exists():
            found["atas"].append(str(p))
    return found


def _probe_mt5() -> dict[str, Any]:
    result: dict[str, Any] = {
        "requested": True,
        "initialized": False,
        "account_present": False,
        "demo_account": None,
        "trade_allowed": None,
        "terminal_connected": None,
    }
    try:
        import MetaTrader5 as mt5
    except Exception as exc:
        result["error"] = f"MetaTrader5 import failed: {type(exc).__name__}"
        return result

    try:
        if not mt5.initialize():
            result["error"] = "mt5.initialize returned false"
            return result
        result["initialized"] = True
        term = mt5.terminal_info()
        account = mt5.account_info()
        if term is not None:
            result["terminal_connected"] = bool(getattr(term, "connected", False))
            result["trade_allowed"] = bool(getattr(term, "trade_allowed", False))
        if account is not None:
            result["account_present"] = True
            demo_const = getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", 0)
            result["demo_account"] = getattr(account, "trade_mode", None) == demo_const
    except Exception as exc:
        result["error"] = f"MT5 probe failed: {type(exc).__name__}"
    finally:
        try:
            mt5.shutdown()
        except Exception:
            pass
    return result


def run(probe_mt5: bool = False) -> dict[str, Any]:
    config = _read_yaml(ROOT / "Config" / "config.yaml")
    if not config:
        config = _read_yaml(ROOT / "Config" / "config.example.yaml")

    engine = config.get("engine", {}) if isinstance(config, dict) else {}
    atas = config.get("atas", {}) if isinstance(config, dict) else {}
    ui = config.get("ui", {}) if isinstance(config, dict) else {}

    ports = {
        "engine": int(engine.get("port", 17832)),
        "atas": int(atas.get("port", 17831)),
        "ui": int(ui.get("port", 17840)),
    }
    required = [
        "MT5/GoldTradingGuardian.mq5",
        "MT5/GuardianIPC.mqh",
        "MT5/GuardianState.mqh",
        "MT5/GuardianHUD.mqh",
        "Engine",
        "ATAS",
        "UI",
        "AI",
        "Config/config.example.yaml",
        "Version/version.json",
    ]

    report: dict[str, Any] = {
        "schema": 2,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "root_present": ROOT.exists(),
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "read_only": True,
        "required_files": {p: (ROOT / p).exists() for p in required},
        "python_modules": {
            name: importlib.util.find_spec(name) is not None
            for name in ("yaml", "httpx", "fastapi", "uvicorn", "MetaTrader5")
        },
        "secrets": _safe_secret_status(ROOT / "Config" / "secrets.local"),
        "platform_candidates": _candidate_paths(),
        "bindings": _binding_status(),
        "localhost": {name: _tcp("127.0.0.1", port) for name, port in ports.items()},
        "ports": ports,
    }
    if probe_mt5:
        report["mt5_probe"] = _probe_mt5()
    else:
        report["mt5_probe"] = {"requested": False}

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="GoldTradingSystem read-only local acceptance preflight")
    ap.add_argument("--probe-mt5", action="store_true", help="Initialize MT5 read-only and report demo/connectivity state. No orders are sent.")
    args = ap.parse_args()
    result = run(probe_mt5=args.probe_mt5)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nReport: {REPORT}")
    if not all(result["required_files"].values()):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
