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
from .control_runtime import control_loop
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
from .review_scheduler import review_loop
from .startup_checks import StartupChecker
from .trade_recorder import TradeRecorder


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
        self.atas = AtasBridgeClient(
            str(atas.get("host", "127.0.0.1")), int(atas.get("port", 17831)), self._on_atas,
            require_mbo=bool(atas.get("require_mbo", False)),
        )
        terminal_path = str(mt5.get("terminal_path", "")).strip() or None
        self.mt5_data = MT5DataProvider(terminal_path) if bool(mt5.get("python_data_adapter", True)) else None
        self.dashboard = DashboardClient(f"http://127.0.0.1:{int(settings.raw.get('ui',{}).get('port',17840))}")
        self.log = logging.getLogger("system")
        self.ai_status = "OFFLINE"
        self.ai_latency_ms: float | None = None
        self.ai_sleep = False
        self.allow_new_entries = True
        self.analysis = AnalysisEngine(self)
        self.trade_recorder = TradeRecorder(db)
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
        mapped = None
        if gc_price is not None:
            try: mapped = self.alignment.map_gc_to_mt5(float(gc_price))
            except (TypeError, ValueError): mapped = None
        strength = payload.get("strength")
        self.db.execute("INSERT INTO OrderFlowEvents(ts,event_type,gc_price,mt5_price,strength,payload) VALUES(?,?,?,?,?,?)",
                        (now, str(event.get("type", "unknown")), gc_price, mapped, strength, json.dumps(event, ensure_ascii=False)))

    def _slot_dashboard(self, name: str) -> dict:
        slot = asdict(slot_from_guardian_state(self.guardian.state, name))
        slot["current_price"] = self.guardian.state.bid if slot.get("side") == "BUY" else self.guardian.state.ask
        return slot

    @staticmethod
    def _zone_text(items: object) -> str:
        if not isinstance(items, list) or not items:
            return "-"
        item = items[0]
        if not isinstance(item, dict):
            return "-"
        zone = item.get("zone") if isinstance(item.get("zone"), dict) else item
        try:
            return f"{float(zone['low']):.2f}-{float(zone['high']):.2f}"
        except (KeyError, TypeError, ValueError):
            return "-"

    @staticmethod
    def _potential_text(items: object, side: str) -> str:
        if not isinstance(items, list):
            return "-"
        for item in items:
            if not isinstance(item, dict) or str(item.get("side", "")).upper() != side:
                continue
            zone = item.get("zone") if isinstance(item.get("zone"), dict) else {}
            try:
                return f"{float(zone['low']):.2f}-{float(zone['high']):.2f} {item.get('status','')}"
            except (KeyError, TypeError, ValueError):
                return "-"
        return "-"

    async def _publish_mt5_hud(self, degradation_name: str) -> None:
        d = self.dashboard.state
        system = d.get("system", {}) if isinstance(d.get("system"), dict) else {}
        fields = [
            d.get("regime", "UNKNOWN"),
            d.get("bias", "NEUTRAL"),
            self._zone_text(d.get("supports")),
            self._zone_text(d.get("resistances")),
            self._potential_text(d.get("zones"), "BUY"),
            self._potential_text(d.get("zones"), "SELL"),
            d.get("orderflow_assessment", "数据不足"),
            system.get("ai", self.ai_status),
            "-" if self.ai_latency_ms is None else f"{self.ai_latency_ms:.0f}ms",
            degradation_name,
        ]
        await self.guardian.publish_status(fields)

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
                    "ai": "SLEEP" if self.ai_sleep else self.ai_status,
                    "ai_latency_ms": self.ai_latency_ms,
                    "mapping": "HEALTHY" if mapping_ok else mapping_reason,
                    "degradation_level": degradation.level,
                    "degradation_mode": degradation.name,
                    "new_entries": "PAUSED" if not self.allow_new_entries else "ENABLED",
                    "data_updated_at": datetime.now(timezone.utc).isoformat(),
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
            await self._publish_mt5_hud(degradation.name)
            self.trade_recorder.sync(self.guardian.state)
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
                    assessment = self.orderflow.assess()
                    for name in ("A", "B"):
                        slot = slot_from_guardian_state(self.guardian.state, name)
                        if not slot.active:
                            continue
                        price = float(self.guardian.state.bid if slot.side.upper() == "BUY" else self.guardian.state.ask)
                        decision = self.position_manager.evaluate(slot, price)
                        if decision.action == "HOLD" and slot.mfe > 0:
                            if slot.side.upper() == "BUY" and assessment.score <= -1.5:
                                decision.action, decision.reason = "CLOSE", "strong opposing order flow"
                            elif slot.side.upper() == "SELL" and assessment.score >= 1.5:
                                decision.action, decision.reason = "CLOSE", "strong opposing order flow"
                        if decision.action == "HOLD" or now - self._last_management_action[name] < 2.0:
                            continue
                        if decision.action == "CLOSE": self.trade_recorder.note_exit_reason(name, decision.reason)
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
        workers = [
            asyncio.create_task(self.guardian.serve_forever(), name="guardian"),
            asyncio.create_task(self.atas.run(), name="atas"),
            asyncio.create_task(self.status_loop(), name="status"),
            asyncio.create_task(self.position_management_loop(), name="position_management"),
            asyncio.create_task(self.retention_loop(), name="retention"),
            asyncio.create_task(review_loop(self.db), name="reviews"),
            asyncio.create_task(self.analysis.loop(), name="analysis"),
        ]
        controls = asyncio.create_task(control_loop(self), name="controls")
        try:
            done, _ = await asyncio.wait([controls, *workers], return_when=asyncio.FIRST_COMPLETED)
            if controls not in done:
                for task in done:
                    if task.exception() is not None:
                        raise task.exception()
        finally:
            for task in [controls, *workers]:
                if not task.done(): task.cancel()
            await asyncio.gather(controls, *workers, return_exceptions=True)
            await self.atas.stop()
            await self.guardian.close()
            if self.mt5_data is not None:
                await asyncio.to_thread(self.mt5_data.shutdown)
