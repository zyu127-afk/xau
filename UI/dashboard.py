from __future__ import annotations

from pathlib import Path
from threading import RLock
import json
import os
import secrets
import tempfile
import uuid
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse

app = FastAPI(title="GoldTradingSystem 中文驾驶舱")
ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
RUNTIME = PROJECT_ROOT / "Runtime"
RUNTIME.mkdir(parents=True, exist_ok=True)
CONTROL_FILE = RUNTIME / "control.json"
TOKEN_FILE = RUNTIME / "dashboard.token"
LOCK = RLock()


def _ensure_token() -> str:
    if TOKEN_FILE.exists():
        value = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if value:
            return value
    value = secrets.token_urlsafe(32)
    TOKEN_FILE.write_text(value, encoding="utf-8")
    try:
        os.chmod(TOKEN_FILE, 0o600)
    except OSError:
        pass
    return value


TOKEN = _ensure_token()

STATE = {
    "system": {"mt5": "OFFLINE", "atas": "OFFLINE", "rithmic": "UNKNOWN", "ai": "OFFLINE", "mapping": "WARMING_UP", "degradation_level": 4},
    "market": {"symbol": "", "bid": None, "ask": None, "spread": None, "atas_contract": "", "gc_price": None, "offset": None},
    "regime": "UNKNOWN", "bias": "NEUTRAL",
    "structures": {}, "supports": [], "resistances": [], "zones": [],
    "breakout": {"verdict": "NONE", "reason": "等待行情"}, "trade_modes": [],
    "orderflow_assessment": "数据不足", "ai_analysis": {},
    "long_plan": {}, "short_plan": {},
    "why_no_trade": ["系统启动中"], "positions": {"A": None, "B": None},
}


def _read_control() -> dict:
    base = {"ai_sleep": False, "pause_new_entries": False, "stop_system": False, "emergency_close_request": ""}
    try:
        raw = json.loads(CONTROL_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            base.update({k: raw.get(k, v) for k, v in base.items()})
    except (OSError, json.JSONDecodeError):
        pass
    return base


def _write_control(data: dict) -> None:
    fd, tmp = tempfile.mkstemp(prefix="gts-dashboard-", suffix=".json", dir=str(RUNTIME))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONTROL_FILE)
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except OSError:
            pass


def _require_token(value: str | None) -> None:
    if not value or not secrets.compare_digest(value, TOKEN):
        raise HTTPException(status_code=403, detail="invalid local dashboard token")


@app.get("/api/state")
def state():
    with LOCK:
        return {**STATE, "control": _read_control()}


@app.put("/api/state")
def update_state(payload: dict, x_gts_token: str | None = Header(default=None)):
    # Only the authenticated local Engine publisher may mutate displayed state.
    _require_token(x_gts_token)
    with LOCK:
        STATE.update(payload)
    return {"ok": True}


@app.get("/api/control-token")
def control_token():
    # Same-origin dashboard JavaScript can read this; cross-origin web pages cannot.
    return {"token": TOKEN}


@app.get("/api/control")
def control():
    return _read_control()


@app.post("/api/control/ai-sleep")
def ai_sleep(payload: dict, x_gts_token: str | None = Header(default=None)):
    _require_token(x_gts_token)
    data = _read_control()
    data["ai_sleep"] = bool(payload.get("enabled", True))
    _write_control(data)
    return data


@app.post("/api/control/pause-new-entries")
def pause_new_entries(payload: dict, x_gts_token: str | None = Header(default=None)):
    _require_token(x_gts_token)
    data = _read_control()
    data["pause_new_entries"] = bool(payload.get("enabled", True))
    _write_control(data)
    return data


@app.post("/api/control/emergency-close")
def emergency_close(x_gts_token: str | None = Header(default=None)):
    _require_token(x_gts_token)
    data = _read_control()
    data["emergency_close_request"] = str(uuid.uuid4())
    _write_control(data)
    return {"ok": True, "request_id": data["emergency_close_request"]}


@app.post("/api/control/stop-system")
def stop_system(x_gts_token: str | None = Header(default=None)):
    _require_token(x_gts_token)
    data = _read_control()
    data["stop_system"] = True
    _write_control(data)
    return {"ok": True, "note": "Engine will stop without flattening positions; Guardian remains local protection."}


@app.post("/api/control/reset")
def reset_controls(x_gts_token: str | None = Header(default=None)):
    _require_token(x_gts_token)
    data = {"ai_sleep": False, "pause_new_entries": False, "stop_system": False, "emergency_close_request": ""}
    _write_control(data)
    return data


@app.get("/", response_class=HTMLResponse)
def index():
    return (ROOT / "static" / "index.html").read_text(encoding="utf-8")
