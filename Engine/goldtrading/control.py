from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import os
import tempfile


@dataclass(slots=True)
class ControlState:
    ai_sleep: bool = False
    pause_new_entries: bool = False
    stop_system: bool = False
    emergency_close_request: str = ""


class ControlFile:
    """Small local control plane shared by Dashboard and Engine.

    It contains no secrets and grants no direct execution authority: emergency close is still
    submitted through Guardian. Normal shutdown never implies flattening positions.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.write(ControlState())

    def read(self) -> ControlState:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return ControlState()
            return ControlState(
                ai_sleep=bool(raw.get("ai_sleep", False)),
                pause_new_entries=bool(raw.get("pause_new_entries", False)),
                stop_system=bool(raw.get("stop_system", False)),
                emergency_close_request=str(raw.get("emergency_close_request", "") or ""),
            )
        except (OSError, json.JSONDecodeError):
            return ControlState()

    def write(self, state: ControlState) -> None:
        payload = json.dumps(asdict(state), ensure_ascii=False, indent=2)
        fd, tmp = tempfile.mkstemp(prefix="gts-control-", suffix=".json", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
            os.replace(tmp, self.path)
        finally:
            try:
                if os.path.exists(tmp): os.unlink(tmp)
            except OSError:
                pass

    def patch(self, **changes) -> ControlState:
        state = self.read()
        for key, value in changes.items():
            if hasattr(state, key): setattr(state, key, value)
        self.write(state)
        return state
