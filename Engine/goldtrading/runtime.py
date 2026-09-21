from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from .analysis_engine import AnalysisEngine
from .atas_client import AtasBridgeClient
from .config import Settings
from .database import Database
from .dashboard_client import DashboardClient
from .degradation import classify_degradation
from .guardian_server import GuardianServer
from .mt5_data import MT5DataProvider
from .orderflow import OrderFlowEngine
from .price_alignment import PriceAlignmentEngine
from .positions import PositionBook
from .retention import prune_rolling_data
from .review_scheduler import daily_review_loop
from .startup_checks import StartupChecker


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
        terminal_path = str(mt5.get("terminal_path", "")).strip() or None
        self.mt5_data = MT5DataProvider(terminal_path) if bool(mt5.get("python_data_adapter", True)) else None
        self.dashboard = DashboardClient(f"http://127.0.0.1:{int(settings.raw.get('ui',{}).get('port',17840))}")
        self.log = logging.getLogger("system")
        self.ai_status = "OFFLINE"
        self.analysis = AnalysisEngine(self)

    def logical_slot_active(self, slot: str) -> bool:
        if slot.upper() == "A": return self.guardian.state.slot_a_active
        if slot.upper() == "B": return self.guardian.state.slot_b_active
        raise KeyError(slot)

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
            payload = (self.atas.state.latest.get("payload") or {}) if self.atas.state.latest else {}
            raw_gc = payload.get("last", payload.get("price")) if isinstance(payload, dict) else None
            atas_fresh = self.atas.state.health.value == "HEALTHY" and self.atas.state.last_message_monotonic > 0 and (time.monotonic() - self.atas.state.last_message_monotonic) <= float(self.settings.raw.get("atas", {}).get("stale_seconds", 5))
            if raw_gc is not None and self.guardian.state.bid is not None and self.guardian.state.ask is not None and atas_fresh:
                mt5_mid = (self.guardian.state.bid + self.guardian.state.ask) / 2.0
                self.alignment.add(float(raw_gc), mt5_mid)
            estimate = self.alignment.estimate()
            degradation = classify_degradation(mt5_alive=self.guardian.heartbeat_fresh(), atas_health=self.atas.state.health.value if atas_fresh else "OFFLINE", ai_health=self.ai_status)
            await self.dashboard.push({
                "system": {
                    "mt5": "HEALTHY" if self.guardian.heartbeat_fresh() else "OFFLINE",
                    "atas": self.atas.state.health.value if atas_fresh else "OFFLINE",
                    "rithmic": "CONNECTED" if atas_fresh else "UNKNOWN",
                    "ai": self.ai_status,
                    "mapping": "HEALTHY" if estimate else "WARMING_UP",
                    "degradation_level": degradation.level,
                    "degradation_mode": degradation.name,
                },
                "market": {
                    "symbol": self.guardian.state.symbol,
                    "bid": self.guardian.state.bid,
                    "ask": self.guardian.state.ask,
                    "spread": self.guardian.state.spread_points,
                    "atas_contract": self.atas.state.instrument,
                    "gc_price": raw_gc,
                    "offset": estimate.offset if estimate else None,
                    "mapping_correlation": estimate.correlation if estimate else None,
                },
                "orderflow_assessment": assessment.label,
                "positions": {
                    "A": {"active": self.guardian.state.slot_a_active},
                    "B": {"active": self.guardian.state.slot_b_active},
                },
            })
            await asyncio.sleep(1.0)

    async def retention_loop(self) -> None:
        while True:
            deleted = prune_rolling_data(self.db, int(self.settings.raw.get("history", {}).get("rolling_days", 90)))
            if deleted:
                self.log.info("90-day rolling retention removed %d raw/detail rows", deleted)
            await asyncio.sleep(6 * 3600)

    async def _connect_mt5_data(self) -> None:
        if self.mt5_data is None:
            self.log.warning("MT5 Python data adapter disabled")
            return
        ok = await asyncio.to_thread(self.mt5_data.connect)
        if ok:
            account = await asyncio.to_thread(self.mt5_data.account)
            self.log.info("MT5 Python data adapter connected account=%s", None if account is None else account.get("login"))
        else:
            self.log.warning("MT5 Python data adapter unavailable; Guardian protection remains independent")

    async def run(self) -> None:
        checks = StartupChecker(self.settings).run_local_checks()
        for check in checks:
            (self.log.info if check.ok else self.log.warning)("startup check %s ok=%s critical=%s detail=%s", check.name, check.ok, check.critical, check.detail)
        if not StartupChecker.critical_ok(checks):
            raise RuntimeError("critical local startup checks failed")
        await self.guardian.start()
        await self._connect_mt5_data()
        tasks = [
            asyncio.create_task(self.guardian.serve_forever(), name="guardian"),
            asyncio.create_task(self.atas.run(), name="atas"),
            asyncio.create_task(self.status_loop(), name="status"),
            asyncio.create_task(self.retention_loop(), name="retention"),
            asyncio.create_task(daily_review_loop(self.db), name="daily_review"),
            asyncio.create_task(self.analysis.loop(), name="analysis"),
        ]
        try:
            await asyncio.gather(*tasks)
        finally:
            await self.atas.stop()
            await self.guardian.close()
            if self.mt5_data is not None:
                await asyncio.to_thread(self.mt5_data.shutdown)
