from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="GoldTradingSystem 中文驾驶舱")
ROOT = Path(__file__).resolve().parent

STATE = {
    "system": {"mt5": "OFFLINE", "atas": "OFFLINE", "rithmic": "UNKNOWN", "ai": "OFFLINE", "mapping": "WARMING_UP"},
    "market": {"symbol": "", "bid": None, "ask": None, "spread": None, "atas_contract": "", "gc_price": None, "offset": None},
    "regime": "UNKNOWN",
    "bias": "NEUTRAL",
    "supports": [],
    "resistances": [],
    "zones": [],
    "orderflow_assessment": "数据不足",
    "long_plan": {},
    "short_plan": {},
    "why_no_trade": ["系统启动中"],
    "positions": {"A": None, "B": None},
}

@app.get("/api/state")
def state():
    return STATE

@app.put("/api/state")
def update_state(payload: dict):
    STATE.update(payload)
    return {"ok": True}

@app.get("/", response_class=HTMLResponse)
def index():
    return (ROOT / "static" / "index.html").read_text(encoding="utf-8")
