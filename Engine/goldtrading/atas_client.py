from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable
from .models import Health


@dataclass(slots=True)
class AtasState:
    health: Health = Health.OFFLINE
    instrument: str = ""
    last_message_monotonic: float = 0.0
    mbo_available: bool = False
    latest: dict[str, Any] = field(default_factory=dict)


class AtasBridgeClient:
    def __init__(self, host: str, port: int, on_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None) -> None:
        self.host = host
        self.port = port
        self.on_event = on_event
        self.state = AtasState()
        self._stop = asyncio.Event()

    async def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        while not self._stop.is_set():
            try:
                self.state.health = Health.WARMING_UP
                reader, writer = await asyncio.open_connection(self.host, self.port)
                self.state.health = Health.HEALTHY
                while not self._stop.is_set():
                    line = await asyncio.wait_for(reader.readline(), timeout=5.0)
                    if not line:
                        raise ConnectionError("ATAS bridge closed")
                    msg = json.loads(line)
                    self.state.last_message_monotonic = time.monotonic()
                    self.state.instrument = str(msg.get("instrument", self.state.instrument))
                    self.state.mbo_available = bool(msg.get("mbo_available", False))
                    self.state.latest = msg
                    if self.on_event:
                        await self.on_event(msg)
                writer.close()
                await writer.wait_closed()
            except asyncio.TimeoutError:
                self.state.health = Health.DEGRADED
            except (OSError, ConnectionError, json.JSONDecodeError):
                self.state.health = Health.OFFLINE
            if not self._stop.is_set():
                await asyncio.sleep(1.0)
