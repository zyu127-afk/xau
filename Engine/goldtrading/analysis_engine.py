from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any

from .ai_client import OpenAICompatibleClient
from .breakout import assess_breakout
from .degradation import classify_degradation
from .guardian_protocol import GuardianCommand
from .models import Bias, MarketRegime, TradeIntent
from .potential_zones import rank_potential_zones
from .snapshot_builder import build_snapshot
from .stale import validate_intent
from .structure import classify_market
from .trade_modes import assess_modes
from .trade_planner import actual_space_is_worthwhile, build_plans
from .zones import build_zones, PriceZone


class AnalysisEngine:
    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime
        self.settings = runtime.settings
        self.db = runtime.db
        self.log = logging.getLogger("trading")
        ai_cfg = self.settings.raw.get("ai", {})
        self.ai = OpenAICompatibleClient(ai_cfg, self.settings.api_key)
        prompt_path = self.settings.paths.root / "AI" / "system_prompt.md"
        self.system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
        self.last_ai_at: datetime | None = None
        self.ai_interval = float(ai_cfg.get("minimum_interval_seconds", 15))
        self.min_ai_confidence = float(ai_cfg.get("min_confidence", 0.60))

    @staticmethod
    def _zone_dict(z: PriceZone) -> dict:
        return asdict(z)

    def _orderflow_fingerprint(self) -> str:
        a = self.runtime.orderflow.assess()
        age = time.monotonic() - self.runtime.atas.state.last_message_monotonic if self.runtime.atas.state.last_message_monotonic else 999999.0
        bucket = int(max(0.0, min(age, 9999.0)))
        return f"{a.label}|{a.score:.4f}|{a.raw.get('events',0)}|age{bucket}"

    def _ai_plan_to_intent(self, snapshot, payload: dict, side: str) -> TradeIntent | None:
        key = "entry_plan_long" if side == "BUY" else "entry_plan_short"
        plan = payload.get(key)
        if not isinstance(plan, dict) or str(plan.get("action", "WAIT")).upper() != "OPEN":
            return None
        try:
            valid_seconds = max(1, min(120, int(plan.get("valid_for_seconds", 20))))
            lot_raw = plan.get("lot")
            lot = self.settings.default_lot if lot_raw in (None, "") else float(lot_raw)
            zone_low = float(plan["zone_low"]); zone_high = float(plan["zone_high"]); stop_loss = float(plan["stop_loss"])
            if zone_low > zone_high or stop_loss <= 0 or lot <= 0:
                return None
            return TradeIntent(
                intent_id=f"{snapshot.snapshot_id}-{side}", action="OPEN", side=side,
                lot=lot, snapshot_id=snapshot.snapshot_id,
                reason=str(plan.get("reason", payload.get("reasoning_summary", "AI plan"))),
                valid_until=datetime.now(timezone.utc) + timedelta(seconds=valid_seconds),
                zone_low=zone_low, zone_high=zone_high, stop_loss=stop_loss,
                take_profit=None if plan.get("take_profit") in (None, "") else float(plan["take_profit"]),
                metadata={"confidence": payload.get("confidence", 0), "mode": payload.get("market_regime")},
            )
        except (KeyError, TypeError, ValueError):
            return None

    async def _fresh_structures(self, provider, symbol: str, names: tuple[str, ...]) -> dict:
        return {tf: await asyncio.to_thread(provider.bars, symbol, tf, 300) for tf in names}

    @staticmethod
    def _build_zones(bars_by_tf: dict) -> list[PriceZone]:
        zones: list[PriceZone] = []
        for tf in ("H4", "H1", "M30", "M15"):
            if tf in bars_by_tf:
                zones.extend(build_zones(tf, bars_by_tf[tf], max_each=3))
        return zones

    async def run_once(self) -> None:
        if not self.runtime.guardian.heartbeat_fresh() or not self.runtime.guardian.state.symbol:
            return
        symbol = self.runtime.guardian.state.symbol
        provider = self.runtime.mt5_data
        if provider is None or not provider.connected:
            return
        names = ("D1", "H4", "H1", "M30", "M15", "M5", "M1")
        bars_by_tf = await self._fresh_structures(provider, symbol, names)
        if any(len(bars_by_tf[tf]) < 30 for tf in ("H1", "M15", "M5", "M1")):
            return
        tick = await asyncio.to_thread(provider.tick, symbol)
        if not tick:
            return
        bid, ask = float(tick["bid"]), float(tick["ask"])
        mid = (bid + ask) / 2.0
        structure = classify_market(bars_by_tf)
        zones = self._build_zones(bars_by_tf)
        atr_ref = structure.structures.get("M15").atr if structure.structures.get("M15") else 0.0
        potentials = rank_potential_zones(mid, zones, atr_ref, 3)
        breakout = assess_breakout(bars_by_tf["M5"], zones)
        orderflow = self.runtime.orderflow.assess()
        orderflow_fp = self._orderflow_fingerprint()
        modes = assess_modes(structure, potentials, breakout, orderflow)
        long_plan, short_plan = build_plans(mid, structure, zones, orderflow)
        positions = await asyncio.to_thread(provider.positions, symbol)
        gc_price = None
        if self.runtime.atas.state.latest:
            payload0 = self.runtime.atas.state.latest.get("payload") or {}
            raw_gc = payload0.get("last", payload0.get("price"))
            if raw_gc is not None:
                gc_price = float(raw_gc)
        mapping = self.runtime.alignment.estimate()
        dynamic = {
            "mt5": {"symbol": symbol, "bid": bid, "ask": ask, "mid": mid, "positions": positions},
            "structure": {"regime": structure.regime.value, "bias": structure.bias.value,
                          "state_id": structure.state_id, "reasons": structure.reasons,
                          "timeframes": {k: asdict(v) for k, v in structure.structures.items()}},
            "zones": [self._zone_dict(z) for z in zones],
            "potential_zones": [asdict(x) for x in potentials],
            "breakout": asdict(breakout),
            "trade_modes": [asdict(x) for x in modes],
            "orderflow": {"label": orderflow.label, "score": orderflow.score, "evidence": orderflow.evidence, "raw": orderflow.raw,
                          "freshness_fingerprint": orderflow_fp},
            "local_plans": {"long": asdict(long_plan), "short": asdict(short_plan)},
            "price_mapping": asdict(mapping) if mapping else None,
            "atas": {"health": self.runtime.atas.state.health.value, "instrument": self.runtime.atas.state.instrument,
                     "mbo_available": self.runtime.atas.state.mbo_available, "gc_price": gc_price},
        }
        snapshot = build_snapshot(mid, gc_price, structure.state_id, positions, orderflow_fp, dynamic)
        self.db.execute("INSERT OR REPLACE INTO MarketSnapshots(id,ts,payload) VALUES(?,?,?)",
                        (snapshot.snapshot_id, snapshot.snapshot_time.isoformat(), json.dumps(dynamic, ensure_ascii=False, default=str)))
        why: list[str] = []
        if structure.regime is MarketRegime.TRANSITION: why.append("市场处于转换状态")
        if self.runtime.atas.state.health.value != "HEALTHY": why.append("ATAS订单流不是HEALTHY")
        if not mapping: why.append("GC↔MT5映射仍在预热")
        if not any(x.ready for x in modes): why.append("三种核心交易模式均未完成本地确认")
        await self.runtime.dashboard.push({
            "regime": structure.regime.value, "bias": structure.bias.value,
            "supports": [self._zone_dict(z) for z in zones if z.kind == "SUPPORT"][:3],
            "resistances": [self._zone_dict(z) for z in zones if z.kind == "RESISTANCE"][:3],
            "zones": [asdict(x) for x in potentials],
            "breakout": asdict(breakout), "trade_modes": [asdict(x) for x in modes],
            "long_plan": asdict(long_plan), "short_plan": asdict(short_plan),
            "why_no_trade": why or ["等待AI/执行确认"],
        })
        if not self.settings.api_key or not self.system_prompt:
            self.runtime.ai_status = "OFFLINE"
            return
        atas_fresh = self.runtime.atas.state.health.value == "HEALTHY" and (time.monotonic() - self.runtime.atas.state.last_message_monotonic) <= float(self.settings.raw.get("atas", {}).get("stale_seconds", 5))
        min_corr = float(self.settings.raw.get("price_mapping", {}).get("min_correlation", 0.80))
        mapping_ok = mapping is not None and abs(mapping.correlation) >= min_corr
        if not atas_fresh or not mapping_ok:
            reason = "ATAS数据不新鲜" if not atas_fresh else "GC↔MT5映射质量不足"
            self.db.execute("INSERT INTO NoTradeEvents(ts,reason,payload) VALUES(?,?,?)",
                            (datetime.now(timezone.utc).isoformat(), reason, "{}"))
            return
        now = datetime.now(timezone.utc)
        if self.last_ai_at and (now - self.last_ai_at).total_seconds() < self.ai_interval:
            return
        self.last_ai_at = now
        result = await self.ai.analyze(self.system_prompt, {"snapshot_id": snapshot.snapshot_id, **dynamic})
        self.runtime.ai_status = result.status
        self.runtime.ai_latency_ms = result.latency_ms
        self.db.execute("INSERT INTO AIAnalysis(ts,snapshot_id,status,payload) VALUES(?,?,?,?)",
                        (datetime.now(timezone.utc).isoformat(), snapshot.snapshot_id, result.status,
                         json.dumps({"payload": result.payload, "error": result.error, "latency_ms": result.latency_ms}, ensure_ascii=False)))
        degradation = classify_degradation(mt5_alive=self.runtime.guardian.heartbeat_fresh(), atas_health=self.runtime.atas.state.health.value, ai_health=result.status)
        if not degradation.allow_new_ai_trades or not result.payload or result.status not in {"HEALTHY", "SLOW"}:
            return
        if float(result.payload.get("confidence", 0.0)) < self.min_ai_confidence:
            self.db.execute("INSERT INTO NoTradeEvents(ts,reason,payload) VALUES(?,?,?)",
                            (datetime.now(timezone.utc).isoformat(), "AI confidence below local threshold", json.dumps(result.payload, ensure_ascii=False)))
            return
        tick2 = await asyncio.to_thread(provider.tick, symbol)
        positions2 = await asyncio.to_thread(provider.positions, symbol)
        bars2 = await self._fresh_structures(provider, symbol, ("H1", "M15", "M5", "M1"))
        if not tick2 or any(len(v) < 30 for v in bars2.values()):
            return
        combined = dict(bars_by_tf); combined.update(bars2)
        structure2 = classify_market(combined)
        zones2 = self._build_zones(combined)
        mid2 = (float(tick2["bid"]) + float(tick2["ask"])) / 2.0
        atr2 = structure2.structures.get("M15").atr if structure2.structures.get("M15") else 0.0
        potentials2 = rank_potential_zones(mid2, zones2, atr2, 3)
        breakout2 = assess_breakout(combined["M5"], zones2)
        current_of = self.runtime.orderflow.assess()
        modes2 = assess_modes(structure2, potentials2, breakout2, current_of)
        current = build_snapshot(mid2, gc_price, structure2.state_id, positions2, self._orderflow_fingerprint(), dynamic)
        current.snapshot_id = snapshot.snapshot_id
        for side in ("BUY", "SELL"):
            intent = self._ai_plan_to_intent(snapshot, result.payload, side)
            if intent is None:
                continue
            validity = result.payload.get("validity") if isinstance(result.payload.get("validity"), dict) else {}
            max_move = float(validity.get("max_price_move", max(1.0, abs(ask - bid) * 10)))
            ok, stale_reason = validate_intent(intent, snapshot, current, max_move)
            if not ok:
                self.db.execute("INSERT INTO NoTradeEvents(ts,reason,payload) VALUES(?,?,?)",
                                (datetime.now(timezone.utc).isoformat(), stale_reason, "{}")); continue
            ready_modes = [m for m in modes2 if m.ready and m.side == side]
            if not ready_modes:
                self.db.execute("INSERT INTO NoTradeEvents(ts,reason,payload) VALUES(?,?,?)",
                                (datetime.now(timezone.utc).isoformat(), f"{side}没有满足趋势回调/突破回踩/极值反转模式", "{}")); continue
            if structure2.regime in {MarketRegime.TREND, MarketRegime.EXTREME_TREND}:
                if side == "BUY" and structure2.bias is not Bias.LONG: continue
                if side == "SELL" and structure2.bias is not Bias.SHORT: continue
            if side == "BUY" and current_of.score < 0.45: continue
            if side == "SELL" and current_of.score > -0.45: continue
            if self.runtime.logical_slot_active("A") and self.runtime.logical_slot_active("B"):
                self.db.execute("INSERT INTO NoTradeEvents(ts,reason,payload) VALUES(?,?,?)",
                                (datetime.now(timezone.utc).isoformat(), "Position A/B already occupied", "{}")); return
            est_sl = abs(mid2 - intent.stop_loss)
            worthwhile, reason = actual_space_is_worthwhile(mid2, side, zones2, abs(float(tick2["ask"]) - float(tick2["bid"])), est_sl)
            if not worthwhile:
                self.db.execute("INSERT INTO NoTradeEvents(ts,reason,payload) VALUES(?,?,?)",
                                (datetime.now(timezone.utc).isoformat(), reason, "{}")); continue
            slot = "A" if not self.runtime.logical_slot_active("A") else "B"
            mode_names = ",".join(m.mode.value for m in ready_modes)
            command = GuardianCommand(intent.intent_id, "OPEN", slot, side, intent.lot, intent.stop_loss, intent.take_profit,
                                      intent.zone_low, intent.zone_high, intent.valid_until, f"{mode_names}: {intent.reason}")
            accepted, guardian_reason = await self.runtime.guardian.submit(command)
            self.db.execute("INSERT INTO SystemEvents(ts,level,component,event,payload) VALUES(?,?,?,?,?)",
                            (datetime.now(timezone.utc).isoformat(), "INFO" if accepted else "WARNING", "Guardian", "OPEN_ACK",
                             json.dumps({"accepted": accepted, "reason": guardian_reason, "slot": slot, "side": side, "modes": mode_names}, ensure_ascii=False)))
            break

    async def loop(self) -> None:
        while True:
            try:
                await self.run_once()
            except Exception:
                logging.getLogger("errors").exception("analysis loop failed")
            await asyncio.sleep(1.0)
