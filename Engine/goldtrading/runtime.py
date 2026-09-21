from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict
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
from .position_manager import DynamicPositionManager
from .positions import PositionBook
from .price_alignment import PriceAlignmentEngine
from .recovery import persist_guardian_slots, slot_from_guardian_state
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
        self.ai_latency_ms: float | None = None
        self.analysis = AnalysisEngine(self)
        mgmt = settings.raw.get("position_management", {})
        self.position_manager = DynamicPositionManager(
            break_even_r=float(mgmt.get("break_even_r", 1.0)),
            lock_r=float(mgmt.get("lock_r", 1.5)),
            lock_fraction_r=float(mgmt.get("lock_fraction_r", 0.5)),
            giveback_trigger_r=float(mgmt.get("giveback_trigger_r", 2.0)),
            max_giveback_fraction=float(mgmt.get("max_giveback_fraction", 0.55)),
        )
        self._last_management_action: dict[str, float] = {"A": 0.0, "B": 0.0}
        self._last_slot_persist = 0.0
        self._last_mapping_persist = 0.0
        self._last_atas_instrument = ""

    def logical_slot_active(self, slot: str) -> bool:
        if slot.upper() == "A": return self.guardian.state.slot_a_active
        if slot.upper() == "B": return self.guardian.state.slot_b_active
        raise KeyError(slot)

    def mapping_quality(self) -> tuple[bool, str]:
        cfg = self.settings.raw.get("price_mapping", {})
        reason = self.alignment.quality_reason(
            min_correlation=float(cfg.get("min_correlation", 0.80)),
            max_residual=float(cfg.get("max_residual", 2.50)),
            stale_seconds=float(cfg.get("stale_seconds", 5.0)),
        )
        return reason == "HEALTHY", reason

    async def _on_guardian(self, parts: list[str]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        kind = parts[0] if parts else "UNKNOWN"
        if kind != "HB":
            self.db.execute("INSERT INTO SystemEvents(ts,level,component,event,payload) VALUES(?,?,?,?,?)",
                            (now, "INFO", "MT5", kind, json.dumps(parts, ensure_ascii=False)))

    async def _on_atas(self, event: dict) -> None:
        now = str(event.get("ts_utc") or datetime.now(timezone.utc).isoformat())
        instrument = str(event.get("instrument") or "")
        if instrument:
            changed = self.alignment.set_instrument(instrument)
            if changed:
                self.orderflow.reset()
                self.db.execute("INSERT INTO SystemEvents(ts,level,component,event,payload) VALUES(?,?,?,?,?)",
                                (now, "WARNING", "ATAS", "INSTRUMENT_CHANGED",
                                 json.dumps({"from": self._last_atas_instrument, "to": instrument, "mapping": "RESET"}, ensure_ascii=False)))
            self._last_atas_instrument = instrument
        self.orderflow.ingest(event)
        payload = event.get("payload") or {}
        gc_price = payload.get("price") or payload.get("last")
        strength = payload.get("strength")
        self.db.execute("INSERT INTO OrderFlowEvents(ts,event_type,gc_price,mt5_price,strength,payload) VALUES(?,?,?,?,?,?)",
                        (now, str(event.get("type", "unknown")), gc_price, None, strength, json.dumps(event, ensure_ascii=False)))

    def _slot_dashboard(self, name: str) -> dict:
        return asdict(slot_from_guardian_state(self.guardian.state, name))

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
            mapping_ok, mapping_reason = self.mapping_quality()
            degradation = classify_degradation(mt5_alive=self.guardian.heartbeat_fresh(), atas_health=self.atas.state.health.value if atas_fresh else "OFFLINE", ai_health=self.ai_status)
            await self.dashboard.push({
                "system": {
                    "mt5": "HEALTHY" if self.guardian.heartbeat_fresh() else "OFFLINE",
                    "atas": self.atas.state.health.value if atas_fresh else "OFFLINE",
                    "rithmic": "CONNECTED" if atas_fresh else "UNKNOWN",
                    "ai": self.ai_status,
                    "ai_latency_ms": self.ai_latency_ms,
                    "mapping": "HEALTHY" if mapping_ok else mapping_reason,
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
                    "mapping_rmse": estimate.rmse if estimate else None,
                    "mapping_age_seconds": estimate.age_seconds if estimate else None,
                },
                "orderflow_assessment": assessment.label,
                "positions": {"A": self._slot_dashboard("A"), "B": self._slot_dashboard("B")},
            })
            now_mono = time.monotonic()
            if self.guardian.heartbeat_fresh() and now_mono - self._last_slot_persist >= 10.0:
                persist_guardian_slots(self.db, self.guardian.state)
                self._last_slot_persist = now_mono
            if estimate is not None and now_mono - self._last_mapping_persist >= 10.0:
                self.db.execute("INSERT INTO PriceMapping(ts,a,b,correlation,latency_ms,payload) VALUES(?,?,?,?,?,?)",
                                (datetime.now(timezone.utc).isoformat(), estimate.a, estimate.b, estimate.correlation, None,
                                 json.dumps({"instrument": self.alignment.instrument, "rmse": estimate.rmse,
                                             "max_abs_residual": estimate.max_abs_residual, "age_seconds": estimate.age_seconds,
                                             "quality": mapping_reason}, ensure_ascii=False)))
                self._last_mapping_persist = now_mono
            await asyncio.sleep(1.0)

    async def position_management_loop(self) -> None:
        while True:
            try:
                if self.guardian.heartbeat_fresh() and self.guardian.state.bid is not None and self.guardian.state.ask is not None:
                    now = time.monotonic()
                    for name in ("A", "B"):
                        slot = slot_from_guardian_state(self.guardian.state, name)
                        if not slot.active:
                            continue
                        price = float(self.guardian.state.bid if slot.side.upper() == "BUY" else self.guardian.state.ask)
                        decision = self.position_manager.evaluate(slot, price)
                        if decision.action == "HOLD" or now - self._last_management_action[name] < 2.0:
                            continue
                        command = self.position_manager.command(name, slot, decision, price)
                        ok, reason = await self.guardian.submit(command)
                        self._last_management_action[name] = now
                        self.db.execute("INSERT INTO PositionEvents(ts,position_id,event_type,payload) VALUES(?,?,?,?)",
                                        (datetime.now(timezone.utc).isoformat(), name, f"MANAGE_{decision.action}",
                                         json.dumps({"accepted": ok, "guardian_reason": reason, "decision": asdict(decision), "slot": asdict(slot)}, ensure_ascii=False)))
            except Exception:
                logging.getLogger("errors").exception("position management loop failed")
            await asyncio.sleep(0.5)

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
        checker = StartupChecker(self.settings)
        checks = checker.run_local_checks()
        for check in checks:
            (self.log.info if check.ok else self.log.warning)("startup check %s ok=%s critical=%s detail=%s", check.name, check.ok, check.critical, check.detail)
        if not checker.critical_ok(checks):
            raise RuntimeError("critical local startup checks failed")
        await self.guardian.start()
        await self._connect_mt5_data()
        tasks = [
            asyncio.create_task(self.guardian.serve_forever(), name="guardian"),
            asyncio.create_task(self.atas.run(), name="atas"),
            asyncio.create_task(self.status_loop(), name="status"),
            asyncio.create_task(self.position_management_loop(), name="position_management"),
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
