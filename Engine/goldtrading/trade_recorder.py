from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import time
from typing import Any

from .recovery import slot_from_guardian_state


class TradeRecorder:
    """Permanent trade lifecycle recorder keyed to logical Position A/B.

    A Guardian ACK proves the command was accepted, but the durable trade row is created
    from the following Guardian slot telemetry so entry price/lot/SL reflect the actual
    broker-visible position rather than the requested values. Realized PnL remains NULL
    until a broker/MT5 source supplies a verified amount; unknown profit is never written as 0.
    """

    def __init__(self, db) -> None:
        self.db = db
        self.trade_by_slot: dict[str, str] = {}
        self.exit_reason_by_slot: dict[str, str] = {}
        self.pending_open_by_slot: dict[str, dict[str, Any]] = {}
        self._last_pnl_reconcile = 0.0
        self._recover_open_trades()

    @staticmethod
    def _json_dict(raw: str | None) -> dict[str, Any]:
        try:
            value = json.loads(raw or "{}")
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}

    def _recover_open_trades(self) -> None:
        rows = self.db.fetchall("SELECT id,payload FROM Trades WHERE exit_time IS NULL ORDER BY entry_time")
        for row in rows:
            payload = self._json_dict(row["payload"])
            slot = str(payload.get("slot", ""))
            if slot in {"A", "B"}:
                self.trade_by_slot[slot] = str(row["id"])

    def note_open_ack(
        self,
        *,
        slot: str,
        trade_id: str,
        side: str,
        entry_reason: str,
        market_regime: str,
        orderflow_state: str,
        ai_snapshot: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if slot not in {"A", "B"}:
            raise ValueError("slot must be A or B")
        self.pending_open_by_slot[slot] = {
            "trade_id": trade_id,
            "side": side,
            "entry_reason": entry_reason,
            "market_regime": market_regime,
            "orderflow_state": orderflow_state,
            "ai_snapshot": ai_snapshot,
            "payload": payload or {},
        }

    @staticmethod
    def _entry_time_iso(epoch_seconds: int) -> str:
        if epoch_seconds > 0:
            return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).isoformat()
        return datetime.now(timezone.utc).isoformat()

    def register_open(
        self,
        *,
        slot: str,
        trade_id: str,
        side: str,
        lot: float,
        entry_price: float,
        original_sl: float,
        current_tp: float | None,
        entry_reason: str,
        market_regime: str,
        orderflow_state: str,
        ai_snapshot: str,
        entry_time: int = 0,
        payload: dict[str, Any] | None = None,
    ) -> None:
        ts = self._entry_time_iso(entry_time)
        detail = {"slot": slot, **(payload or {})}
        self.db.execute(
            """INSERT OR REPLACE INTO Trades(
               id,entry_time,side,lot,entry_price,original_sl,current_sl,current_tp,mfe,mae,pnl,
               entry_reason,market_regime,orderflow_state,ai_snapshot,payload)
               VALUES(?,?,?,?,?,?,?,?,0,0,NULL,?,?,?,?,?)""",
            (
                trade_id,
                ts,
                side,
                lot,
                entry_price,
                original_sl,
                original_sl,
                current_tp,
                entry_reason,
                market_regime,
                orderflow_state,
                ai_snapshot,
                json.dumps(detail, ensure_ascii=False),
            ),
        )
        self.trade_by_slot[slot] = trade_id
        self.db.execute(
            "INSERT INTO PositionEvents(ts,position_id,event_type,payload) VALUES(?,?,?,?)",
            (ts, trade_id, "OPEN", json.dumps(detail, ensure_ascii=False)),
        )

    def note_exit_reason(self, slot: str, reason: str) -> None:
        if slot in {"A", "B"} and reason:
            self.exit_reason_by_slot[slot] = reason

    def _merge_trade_payload(self, trade_id: str, fields: dict[str, Any]) -> None:
        rows = self.db.fetchall("SELECT payload FROM Trades WHERE id=?", (trade_id,))
        if not rows:
            return
        payload = self._json_dict(rows[0]["payload"])
        payload.update(fields)
        self.db.execute("UPDATE Trades SET payload=? WHERE id=?", (json.dumps(payload, ensure_ascii=False), trade_id))

    def note_realized_close(
        self,
        slot: str,
        *,
        pnl: float,
        exit_price: float,
        reason: str,
        broker_payload: dict[str, Any] | None = None,
    ) -> bool:
        """Finalize a logical trade only from a verified broker/MT5 realized-PnL source."""
        trade_id = self.trade_by_slot.get(slot)
        if not trade_id:
            return False
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            "UPDATE Trades SET exit_time=?,exit_price=?,pnl=?,exit_reason=? WHERE id=? AND exit_time IS NULL",
            (now, exit_price, pnl, reason, trade_id),
        )
        if broker_payload:
            self._merge_trade_payload(trade_id, broker_payload)
        payload = {"slot": slot, "reason": reason, "exit_price": exit_price, "pnl": pnl, **(broker_payload or {})}
        self.db.execute(
            "INSERT INTO PositionEvents(ts,position_id,event_type,payload) VALUES(?,?,?,?)",
            (now, trade_id, "BROKER_CLOSE", json.dumps(payload, ensure_ascii=False)),
        )
        self.trade_by_slot.pop(slot, None)
        self.pending_open_by_slot.pop(slot, None)
        self.exit_reason_by_slot.pop(slot, None)
        return True

    def _register_from_guardian(self, slot: str, state, guardian_state) -> str | None:
        if not state.active or state.entry_price <= 0 or state.lot <= 0 or state.original_sl <= 0:
            return None
        pending = self.pending_open_by_slot.pop(slot, None) or {}
        trade_id = str(pending.get("trade_id") or f"recovered-{slot}-{state.entry_time or int(datetime.now(timezone.utc).timestamp())}")
        side = str(state.side or pending.get("side") or "").upper()
        if side not in {"BUY", "SELL"}:
            return None
        context = {
            "recovered": not bool(pending),
            "account": str(getattr(guardian_state, "account", "") or ""),
            "symbol": str(getattr(guardian_state, "symbol", "") or ""),
            **dict(pending.get("payload") or {}),
        }
        self.register_open(
            slot=slot,
            trade_id=trade_id,
            side=side,
            lot=state.lot,
            entry_price=state.entry_price,
            original_sl=state.original_sl,
            current_tp=state.current_tp or None,
            entry_reason=str(pending.get("entry_reason") or "recovered from Guardian telemetry"),
            market_regime=str(pending.get("market_regime") or "UNKNOWN"),
            orderflow_state=str(pending.get("orderflow_state") or "UNKNOWN"),
            ai_snapshot=str(pending.get("ai_snapshot") or ""),
            entry_time=state.entry_time,
            payload=context,
        )
        return trade_id

    @staticmethod
    def _deal_value(deal: Any, name: str, default: Any = None) -> Any:
        if isinstance(deal, dict):
            return deal.get(name, default)
        return getattr(deal, name, default)

    @classmethod
    def _deal_int(cls, deal: Any, name: str, default: int = -1) -> int:
        raw = cls._deal_value(deal, name, default)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    def _used_close_deals(self) -> set[int]:
        used: set[int] = set()
        rows = self.db.fetchall("SELECT payload FROM Trades WHERE payload IS NOT NULL")
        for row in rows:
            payload = self._json_dict(row["payload"])
            raw = payload.get("broker_close_deal")
            try:
                if raw is not None:
                    used.add(int(raw))
            except (TypeError, ValueError):
                pass
        return used

    def _verify_mt5_pnl(self, trade_id: str, symbol_hint: str = "") -> bool:
        """Resolve one closed trade from MT5 history only when a unique close deal matches its logical volume.

        This intentionally leaves ambiguous shared-netting closes unresolved instead of inventing an allocation.
        """
        rows = self.db.fetchall("SELECT * FROM Trades WHERE id=? AND exit_time IS NOT NULL AND pnl IS NULL", (trade_id,))
        if not rows:
            return False
        row = rows[0]
        payload = self._json_dict(row["payload"])
        slot = str(payload.get("slot", ""))
        if slot not in {"A", "B"}:
            return False
        symbol = str(payload.get("symbol") or symbol_hint or "")
        if not symbol:
            return False
        try:
            import MetaTrader5 as mt5
        except ImportError:
            return False
        try:
            entry_dt = datetime.fromisoformat(str(row["entry_time"]).replace("Z", "+00:00")).astimezone(timezone.utc)
            exit_dt = datetime.fromisoformat(str(row["exit_time"]).replace("Z", "+00:00")).astimezone(timezone.utc)
        except (TypeError, ValueError):
            return False
        try:
            deals = mt5.history_deals_get(entry_dt - timedelta(minutes=2), exit_dt + timedelta(minutes=2)) or []
        except Exception:
            return False
        relevant = [d for d in deals if str(self._deal_value(d, "symbol", "")) == symbol]
        if not relevant:
            return False
        entry_candidates = []
        expected_comment = f"GTS-{slot}"
        entry_epoch = entry_dt.timestamp()
        for deal in relevant:
            comment = str(self._deal_value(deal, "comment", ""))
            entry_kind = self._deal_int(deal, "entry", -1)
            if comment != expected_comment or entry_kind not in {0, 2}:
                continue
            t = float(self._deal_value(deal, "time", 0) or 0)
            volume = float(self._deal_value(deal, "volume", 0.0) or 0.0)
            volume_penalty = abs(volume - float(row["lot"])) * 1000.0
            entry_candidates.append((abs(t - entry_epoch) + volume_penalty, deal))
        if not entry_candidates:
            return False
        entry_deal = min(entry_candidates, key=lambda x: x[0])[1]
        position_id = self._deal_int(entry_deal, "position_id", 0)
        if position_id <= 0:
            return False
        used = self._used_close_deals()
        exit_epoch = exit_dt.timestamp()
        close_candidates = []
        for deal in relevant:
            if self._deal_int(deal, "position_id", 0) != position_id:
                continue
            entry_kind = self._deal_int(deal, "entry", -1)
            if entry_kind not in {1, 3}:
                continue
            ticket = self._deal_int(deal, "ticket", 0)
            if ticket <= 0 or ticket in used:
                continue
            volume = float(self._deal_value(deal, "volume", 0.0) or 0.0)
            if abs(volume - float(row["lot"])) > max(1e-8, float(row["lot"]) * 1e-6):
                continue
            t = float(self._deal_value(deal, "time", 0) or 0)
            if abs(t - exit_epoch) > 180.0:
                continue
            close_candidates.append((abs(t - exit_epoch), deal))
        if not close_candidates:
            return False
        close_deal = min(close_candidates, key=lambda x: x[0])[1]
        close_ticket = self._deal_int(close_deal, "ticket", 0)
        exit_price = float(self._deal_value(close_deal, "price", 0.0) or 0.0)
        if close_ticket <= 0 or exit_price <= 0:
            return False
        realized = 0.0
        for deal in (entry_deal, close_deal):
            for field in ("profit", "commission", "swap", "fee"):
                try:
                    realized += float(self._deal_value(deal, field, 0.0) or 0.0)
                except (TypeError, ValueError):
                    return False
        close_epoch = int(float(self._deal_value(close_deal, "time", exit_epoch) or exit_epoch))
        close_time = datetime.fromtimestamp(close_epoch, tz=timezone.utc).isoformat()
        self.db.execute(
            "UPDATE Trades SET exit_time=?,exit_price=?,pnl=? WHERE id=? AND pnl IS NULL",
            (close_time, exit_price, realized, trade_id),
        )
        self._merge_trade_payload(
            trade_id,
            {
                "pnl_verified": "MT5_HISTORY_DEALS",
                "broker_position_id": position_id,
                "broker_entry_deal": self._deal_int(entry_deal, "ticket", 0),
                "broker_close_deal": close_ticket,
            },
        )
        self.db.execute(
            "INSERT INTO PositionEvents(ts,position_id,event_type,payload) VALUES(?,?,?,?)",
            (
                close_time,
                trade_id,
                "PNL_VERIFIED",
                json.dumps({"source": "MT5_HISTORY_DEALS", "pnl": realized, "exit_price": exit_price, "deal": close_ticket}, ensure_ascii=False),
            ),
        )
        return True

    def reconcile_unresolved_pnl(self, symbol_hint: str = "", limit: int = 20) -> int:
        now = time.monotonic()
        if now - self._last_pnl_reconcile < 5.0:
            return 0
        self._last_pnl_reconcile = now
        rows = self.db.fetchall(
            "SELECT id FROM Trades WHERE exit_time IS NOT NULL AND pnl IS NULL ORDER BY exit_time DESC LIMIT ?",
            (limit,),
        )
        resolved = 0
        for row in rows:
            if self._verify_mt5_pnl(str(row["id"]), symbol_hint):
                resolved += 1
        return resolved

    def sync(self, guardian_state) -> None:
        now = datetime.now(timezone.utc).isoformat()
        symbol_hint = str(getattr(guardian_state, "symbol", "") or "")
        for slot in ("A", "B"):
            state = slot_from_guardian_state(guardian_state, slot)
            trade_id = self.trade_by_slot.get(slot)
            if state.active and not trade_id:
                trade_id = self._register_from_guardian(slot, state, guardian_state)
            if state.active and trade_id:
                self.db.execute(
                    "UPDATE Trades SET current_sl=?,current_tp=?,mfe=?,mae=? WHERE id=? AND exit_time IS NULL",
                    (state.current_sl, state.current_tp or None, state.mfe, state.mae, trade_id),
                )
            elif not state.active and trade_id:
                exit_price = 0.0
                rows = self.db.fetchall("SELECT side FROM Trades WHERE id=?", (trade_id,))
                if rows:
                    side = str(rows[0]["side"] or "")
                    if side.upper() == "BUY" and getattr(guardian_state, "bid", None) is not None:
                        exit_price = float(guardian_state.bid)
                    elif side.upper() == "SELL" and getattr(guardian_state, "ask", None) is not None:
                        exit_price = float(guardian_state.ask)
                reason = self.exit_reason_by_slot.pop(slot, "broker/Guardian closure reconciled; realized PnL pending broker verification")
                self.db.execute(
                    "UPDATE Trades SET exit_time=?,exit_price=?,exit_reason=? WHERE id=? AND exit_time IS NULL",
                    (now, exit_price or None, reason, trade_id),
                )
                self.db.execute(
                    "INSERT INTO PositionEvents(ts,position_id,event_type,payload) VALUES(?,?,?,?)",
                    (now, trade_id, "CLOSE_PENDING_PNL", json.dumps({"slot": slot, "reason": reason, "exit_price": exit_price}, ensure_ascii=False)),
                )
                self.trade_by_slot.pop(slot, None)
                self.pending_open_by_slot.pop(slot, None)
                self._verify_mt5_pnl(trade_id, symbol_hint)
        self.reconcile_unresolved_pnl(symbol_hint)
