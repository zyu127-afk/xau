from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from .position_manager import SlotTelemetry


def slot_from_guardian_state(state, name: str) -> SlotTelemetry:
    prefix = 'slot_a_' if name.upper()=='A' else 'slot_b_'
    return SlotTelemetry(
        active=bool(getattr(state,prefix+'active',False)),
        side=str(getattr(state,prefix+'side','')),
        lot=float(getattr(state,prefix+'lot',0.0) or 0.0),
        entry_price=float(getattr(state,prefix+'entry_price',0.0) or 0.0),
        current_sl=float(getattr(state,prefix+'sl',0.0) or 0.0),
        current_tp=float(getattr(state,prefix+'tp',0.0) or 0.0),
        entry_time=int(getattr(state,prefix+'entry_time',0) or 0),
        mfe=float(getattr(state,prefix+'mfe',0.0) or 0.0),
        mae=float(getattr(state,prefix+'mae',0.0) or 0.0),
    )


def persist_guardian_slots(db, guardian_state) -> None:
    now=datetime.now(timezone.utc).isoformat()
    for name in ('A','B'):
        slot=slot_from_guardian_state(guardian_state,name)
        db.execute('INSERT INTO PositionEvents(ts,position_id,event_type,payload) VALUES(?,?,?,?)',
                   (now,name,'GUARDIAN_SNAPSHOT',json.dumps(asdict(slot),ensure_ascii=False)))
