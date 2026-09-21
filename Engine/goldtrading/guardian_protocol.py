from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass(frozen=True, slots=True)
class GuardianCommand:
    command_id: str
    action: str
    slot: str
    side: str
    lot: float
    stop_loss: float
    take_profit: Optional[float]
    zone_low: float
    zone_high: float
    valid_until: datetime
    reason: str

    def to_wire(self) -> str:
        """Localhost IPC wire format. AI JSON is never forwarded directly to MT5."""
        tp = "" if self.take_profit is None else f"{self.take_profit:.10f}"
        clean_reason = self.reason.replace("|", "/").replace("\n", " ")
        return "|".join([
            "GTS1", self.command_id, self.action.upper(), self.slot.upper(), self.side.upper(),
            f"{self.lot:.8f}", f"{self.stop_loss:.10f}", tp,
            f"{self.zone_low:.10f}", f"{self.zone_high:.10f}",
            str(int(self.valid_until.astimezone(timezone.utc).timestamp())), clean_reason,
        ]) + "\n"
