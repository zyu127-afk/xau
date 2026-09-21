from __future__ import annotations

from datetime import datetime, timezone
import json
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
        self._recover_open_trades()

    def _recover_open_trades(self) -> None:
        rows = self.db.fetchall("SELECT id,payload FROM Trades WHERE exit_time IS NULL ORDER BY entry_time")
        for row in rows:
            try:
                payload = json.loads(row["payload"] or "{}")
            except json.JSONDecodeError:
                payload = {}
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
        payload = {"slot": slot, "reason": reason, "exit_price": exit_price, "pnl": pnl, **(broker_payload or {})}
        self.db.execute(
            "INSERT INTO PositionEvents(ts,position_id,event_type,payload) VALUES(?,?,?,?)",
            (now, trade_id, "BROKER_CLOSE", json.dumps(payload, ensure_ascii=False)),
        )
        self.trade_by_slot.pop(slot, None)
        self.pending_open_by_slot.pop(slot, None)
        self.exit_reason_by_slot.pop(slot, None)
        return True

    def _register_from_guardian(self, slot: str, state) -> str | None:
        if not state.active or state.entry_price <= 0 or state.lot <= 0 or state.original_sl <= 0:
            return None
        pending = self.pending_open_by_slot.pop(slot, None) or {}
        trade_id = str(pending.get("trade_id") or f"recovered-{slot}-{state.entry_time or int(datetime.now(timezone.utc).timestamp())}")
        side = str(state.side or pending.get("side") or "").upper()
        if side not in {"BUY", "SELL"}:
            return None
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
            payload={"recovered": not bool(pending), **dict(pending.get("payload") or {})},
        )
        return trade_id

    def sync(self, guardian_state) -> None:
        now = datetime.now(timezone.utc).isoformat()
        for slot in ("A", "B"):
            state = slot_from_guardian_state(guardian_state, slot)
            trade_id = self.trade_by_slot.get(slot)
            if state.active and not trade_id:
                trade_id = self._register_from_guardian(slot, state)
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
