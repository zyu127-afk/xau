from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from typing import Any
from .recovery import slot_from_guardian_state


class TradeRecorder:
    """Permanent trade lifecycle recorder keyed to logical Position A/B.

    Raw/detail retention may delete snapshots after 90 days, but Trades are never pruned.
    """

    def __init__(self, db) -> None:
        self.db = db
        self.trade_by_slot: dict[str, str] = {}
        self.exit_reason_by_slot: dict[str, str] = {}
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

    def register_open(self, *, slot: str, trade_id: str, side: str, lot: float, entry_price: float,
                      original_sl: float, current_tp: float | None, entry_reason: str,
                      market_regime: str, orderflow_state: str, ai_snapshot: str,
                      payload: dict[str, Any] | None = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        detail = {"slot": slot, **(payload or {})}
        self.db.execute(
            """INSERT OR REPLACE INTO Trades(
               id,entry_time,side,lot,entry_price,original_sl,current_sl,current_tp,mfe,mae,pnl,
               entry_reason,market_regime,orderflow_state,ai_snapshot,payload)
               VALUES(?,?,?,?,?,?,?,?,0,0,0,?,?,?,?,?)""",
            (trade_id, now, side, lot, entry_price, original_sl, original_sl, current_tp,
             entry_reason, market_regime, orderflow_state, ai_snapshot,
             json.dumps(detail, ensure_ascii=False)),
        )
        self.trade_by_slot[slot] = trade_id
        self.db.execute("INSERT INTO PositionEvents(ts,position_id,event_type,payload) VALUES(?,?,?,?)",
                        (now, trade_id, "OPEN", json.dumps(detail, ensure_ascii=False)))

    def note_exit_reason(self, slot: str, reason: str) -> None:
        if slot in {"A", "B"} and reason:
            self.exit_reason_by_slot[slot] = reason

    def sync(self, guardian_state) -> None:
        now = datetime.now(timezone.utc).isoformat()
        for slot in ("A", "B"):
            state = slot_from_guardian_state(guardian_state, slot)
            trade_id = self.trade_by_slot.get(slot)
            if state.active and trade_id:
                current_pnl = float(getattr(state, "current_pnl", 0.0) or 0.0)
                self.db.execute(
                    "UPDATE Trades SET current_sl=?,current_tp=?,mfe=?,mae=?,pnl=? WHERE id=? AND exit_time IS NULL",
                    (state.current_sl, state.current_tp or None, state.mfe, state.mae, current_pnl, trade_id),
                )
            elif not state.active and trade_id:
                exit_price = 0.0
                side = ""
                rows = self.db.fetchall("SELECT side,entry_price,payload FROM Trades WHERE id=?", (trade_id,))
                if rows:
                    side = str(rows[0]["side"] or "")
                    if side.upper() == "BUY" and getattr(guardian_state, "bid", None) is not None:
                        exit_price = float(guardian_state.bid)
                    elif side.upper() == "SELL" and getattr(guardian_state, "ask", None) is not None:
                        exit_price = float(guardian_state.ask)
                reason = self.exit_reason_by_slot.pop(slot, "broker/Guardian closure reconciled")
                self.db.execute(
                    "UPDATE Trades SET exit_time=?,exit_price=?,exit_reason=? WHERE id=? AND exit_time IS NULL",
                    (now, exit_price or None, reason, trade_id),
                )
                self.db.execute("INSERT INTO PositionEvents(ts,position_id,event_type,payload) VALUES(?,?,?,?)",
                                (now, trade_id, "CLOSE", json.dumps({"slot": slot, "reason": reason, "exit_price": exit_price}, ensure_ascii=False)))
                self.trade_by_slot.pop(slot, None)
