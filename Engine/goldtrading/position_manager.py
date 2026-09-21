from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from .guardian_protocol import GuardianCommand

@dataclass(slots=True)
class SlotTelemetry:
    active: bool=False; side: str=""; lot: float=0.0; entry_price: float=0.0
    current_sl: float=0.0; current_tp: float=0.0; entry_time: int=0; mfe: float=0.0; mae: float=0.0

@dataclass(slots=True)
class ManagementDecision:
    action: str
    stop_loss: float | None=None
    reason: str=""

class DynamicPositionManager:
    def __init__(self, break_even_r:float=1.0, lock_r:float=1.5, lock_fraction_r:float=0.5,
                 giveback_trigger_r:float=2.0, max_giveback_fraction:float=0.55)->None:
        self.break_even_r=break_even_r; self.lock_r=lock_r; self.lock_fraction_r=lock_fraction_r
        self.giveback_trigger_r=giveback_trigger_r; self.max_giveback_fraction=max_giveback_fraction

    def evaluate(self, slot:SlotTelemetry, market_price:float)->ManagementDecision:
        if not slot.active or slot.entry_price<=0 or slot.current_sl<=0: return ManagementDecision("HOLD")
        side=slot.side.upper(); initial_r=abs(slot.entry_price-slot.current_sl)
        if initial_r<=0: return ManagementDecision("HOLD")
        favorable=market_price-slot.entry_price if side=="BUY" else slot.entry_price-market_price
        r_now=favorable/initial_r; mfe_r=slot.mfe/initial_r
        if mfe_r>=self.giveback_trigger_r and slot.mfe>0:
            giveback=max(0.0,slot.mfe-favorable)/slot.mfe
            if giveback>=self.max_giveback_fraction: return ManagementDecision("CLOSE",reason=f"MFE giveback {giveback:.0%}")
        candidate=slot.current_sl
        if r_now>=self.lock_r:
            locked=slot.entry_price+self.lock_fraction_r*initial_r if side=="BUY" else slot.entry_price-self.lock_fraction_r*initial_r
            candidate=max(candidate,locked) if side=="BUY" else min(candidate,locked)
        elif r_now>=self.break_even_r:
            candidate=max(candidate,slot.entry_price) if side=="BUY" else min(candidate,slot.entry_price)
        if abs(candidate-slot.current_sl)>1e-9: return ManagementDecision("MODIFY_SL",candidate,"profit protection")
        return ManagementDecision("HOLD")

    @staticmethod
    def command(slot_name:str, slot:SlotTelemetry, decision:ManagementDecision, price:float)->GuardianCommand:
        now=datetime.now(timezone.utc)
        return GuardianCommand(command_id=f"pm-{slot_name}-{int(now.timestamp()*1000)}",
            action="CLOSE" if decision.action=="CLOSE" else "MODIFY_SL",slot=slot_name,side=slot.side,lot=slot.lot,
            stop_loss=decision.stop_loss or slot.current_sl,take_profit=slot.current_tp or None,zone_low=price-1e9,zone_high=price+1e9,
            valid_until=now+timedelta(seconds=3),reason=decision.reason or decision.action)
