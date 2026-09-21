from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from .control import ControlFile
from .guardian_protocol import GuardianCommand


async def control_loop(runtime) -> None:
    """Watch Runtime/control.json without blocking data/risk tasks.

    Normal full-stop never means flatten. Emergency close is explicit and still goes through Guardian.
    """
    control = ControlFile(runtime.settings.paths.runtime / "control.json")
    log = logging.getLogger("system")
    last_emergency = ""
    while True:
        state = control.read()
        runtime.ai_sleep = state.ai_sleep
        runtime.allow_new_entries = not state.pause_new_entries
        if state.emergency_close_request and state.emergency_close_request != last_emergency:
            last_emergency = state.emergency_close_request
            runtime.trade_recorder.note_exit_reason("A", "dashboard emergency close")
            runtime.trade_recorder.note_exit_reason("B", "dashboard emergency close")
            now = datetime.now(timezone.utc)
            command = GuardianCommand(
                command_id=f"emergency-{state.emergency_close_request}", action="CLOSE_ALL",
                slot="A", side="BUY", lot=0.0, stop_loss=1.0, take_profit=None,
                zone_low=-1e12, zone_high=1e12, valid_until=now + timedelta(seconds=10),
                reason="dashboard emergency close",
            )
            ok, reason = await runtime.guardian.submit(command, timeout=5.0)
            log.warning("emergency close requested accepted=%s reason=%s", ok, reason)
        if state.stop_system:
            log.warning("normal system stop requested; existing MT5 positions are NOT flattened")
            return
        await asyncio.sleep(0.25)
