from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from .atas_client import AtasBridgeClient
from .config import Settings
from .database import Database
from .dashboard_client import DashboardClient
from .guardian_server import GuardianServer
from .orderflow import OrderFlowEngine
from .price_alignment import PriceAlignmentEngine
from .positions import PositionBook
from .retention import prune_rolling_data


class Runtime:
    def __init__(self, settings: Settings, db: Database) -> None:
        self.settings = settings
        self.db = db
        self.orderflow = OrderFlowEngine()
        pm = settings.raw.get("price_mapping", {})
        self.alignment = PriceAlignmentEngine(int(pm.get("rolling_window", 300)), int(pm.get("min_samples", 30)))
        self.positions = PositionBook(settings.max_position_logics)
        mt5 = settings.raw.get("mt5", {})
        atas = settings.raw.get("atas", {})
        self.guardian = GuardianServer(str(mt5.get("host", "127.0.0.1")), int(mt5.get("port", 17832)), self._on_guardian)
        self.atas = AtasBridgeClient(str(atas.get("host", "127.0.0.1")), int(atas.get("port", 17831)), self._on_atas)
        self.dashboard = DashboardClient(f"http://127.0.0.1:{int(settings.raw.get('ui',{}).get('port',17840))}")
        self.log = logging.getLogger("system")

    async def _on_guardian(self, parts: list[str]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute("INSERT INTO SystemEvents(ts,level,component,event,payload) VALUES(?,?,?,?,?)",
                        (now, "INFO", "MT5", parts[0] if parts else "UNKNOWN", json.dumps(parts, ensure_ascii=False)))

    async def _on_atas(self, event: dict) -> None:
        self.orderflow.ingest(event)
        now = str(event.get("ts_utc") or datetime.now(timezone.utc).isoformat())
        payload = event.get("payload") or {}
        gc_price = payload.get("price") or payload.get("last")
        strength = payload.get("strength")
        self.db.execute("INSERT INTO OrderFlowEvents(ts,event_type,gc_price,mt5_price,strength,payload) VALUES(?,?,?,?,?,?)",
                        (now, str(event.get("type", "unknown")), gc_price, None, strength, json.dumps(event, ensure_ascii=False)))

    async def status_loop(self) -> None:
        while True:
            assessment = self.orderflow.assess()
            await self.dashboard.push({
                "system": {
                    "mt5": "HEALTHY" if self.guardian.heartbeat_fresh() else "OFFLINE",
                    "atas": self.atas.state.health.value,
                    "rithmic": "CONNECTED" if self.atas.state.health.value == "HEALTHY" else "UNKNOWN",
                    "ai": "OFFLINE",
                    "mapping": "HEALTHY" if self.alignment.estimate() else "WARMING_UP",
                },
                "market": {
                    "symbol": self.guardian.state.symbol,
                    "bid": self.guardian.state.bid,
                    "ask": self.guardian.state.ask,
                    "spread": self.guardian.state.spread_points,
                    "atas_contract": self.atas.state.instrument,
                    "gc_price": (self.atas.state.latest.get("payload") or {}).get("last") if self.atas.state.latest else None,
                    "offset": self.alignment.estimate().offset if self.alignment.estimate() else None,
                },
                "orderflow_assessment": assessment.label,
            })
            await asyncio.sleep(1.0)

    async def retention_loop(self) -> None:
        while True:
            deleted = prune_rolling_data(self.db, int(self.settings.raw.get("history", {}).get("rolling_days", 90)))
            if deleted:
                self.log.info("90-day rolling retention removed %d raw/detail rows", deleted)
            await asyncio.sleep(6 * 3600)

    async def run(self) -> None:
        await self.guardian.start()
        tasks = [
            asyncio.create_task(self.guardian.serve_forever(), name="guardian"),
            asyncio.create_task(self.atas.run(), name="atas"),
            asyncio.create_task(self.status_loop(), name="status"),
            asyncio.create_task(self.retention_loop(), name="retention"),
        ]
        try:
            await asyncio.gather(*tasks)
        finally:
            await self.atas.stop()
            await self.guardian.close()
