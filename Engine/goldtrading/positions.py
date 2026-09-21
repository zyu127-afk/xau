from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Optional
from .models import PositionState


class PositionBook:
    """Keeps Position A/B as independent logical entries even on netting accounts."""

    def __init__(self, max_positions: int = 2) -> None:
        if max_positions != 2:
            raise ValueError("V1 requires exactly two logical position slots")
        self.slots: dict[str, Optional[PositionState]] = {"A": None, "B": None}

    def open(self, slot: str, position: PositionState) -> None:
        if slot not in self.slots:
            raise KeyError(slot)
        if self.slots[slot] is not None:
            raise RuntimeError(f"Position {slot} already occupied")
        if position.original_sl <= 0:
            raise ValueError("A real server stop loss is mandatory")
        self.slots[slot] = position

    def update_market(self, current_price: float, pnl_by_slot: dict[str, float]) -> None:
        for slot, pos in self.slots.items():
            if pos is None:
                continue
            move = current_price - pos.entry_price
            favorable = move if pos.side.upper() == "BUY" else -move
            adverse = -favorable
            pos.mfe = max(pos.mfe, favorable)
            pos.mae = max(pos.mae, adverse)
            pos.current_pnl = float(pnl_by_slot.get(slot, pos.current_pnl))

    def close(self, slot: str, reason: str) -> PositionState:
        pos = self.slots.get(slot)
        if pos is None:
            raise RuntimeError(f"Position {slot} is empty")
        pos.exit_reason = reason
        self.slots[slot] = None
        return pos

    def occupied(self) -> int:
        return sum(1 for x in self.slots.values() if x is not None)

    def fingerprint(self) -> str:
        parts = []
        for slot in ("A", "B"):
            pos = self.slots[slot]
            parts.append(f"{slot}:EMPTY" if pos is None else f"{slot}:{pos.entry_id}:{pos.side}:{pos.lot}:{pos.current_sl}")
        return "|".join(parts)

    def snapshot(self) -> dict:
        return {slot: None if pos is None else asdict(pos) for slot, pos in self.slots.items()}
