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
    reconnects: int = 0
    malformed_messages: int = 0


class AtasBridgeClient:
    def __init__(self, host: str, port: int, on_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
                 require_mbo: bool = False) -> None:
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("ATAS bridge client must remain loopback-only")
        self.host = host
        self.port = port
        self.on_event = on_event
        self.require_mbo = require_mbo
        self.state = AtasState()
        self._stop = asyncio.Event()

    async def stop(self) -> None:
        self._stop.set()

    def _apply_health(self, msg: dict[str, Any]) -> None:
        payload = msg.get("payload") or {}
        advertised = str(payload.get("health", "")).upper() if isinstance(payload, dict) else ""
        if self.require_mbo and not self.state.mbo_available:
            self.state.health = Health.DEGRADED
        elif advertised in {h.value for h in Health}:
            self.state.health = Health(advertised)
        else:
            self.state.health = Health.HEALTHY

    async def run(self) -> None:
        backoff = 0.5
        while not self._stop.is_set():
            writer: asyncio.StreamWriter | None = None
            try:
                self.state.health = Health.WARMING_UP
                reader, writer = await asyncio.open_connection(self.host, self.port)
                self.state.health = Health.WARMING_UP
                backoff = 0.5
                while not self._stop.is_set():
                    line = await asyncio.wait_for(reader.readline(), timeout=5.0)
                    if not line:
                        raise ConnectionError("ATAS bridge closed")
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        self.state.malformed_messages += 1
                        if self.state.malformed_messages >= 3:
                            self.state.health = Health.DEGRADED
                        continue
                    if not isinstance(msg, dict):
                        self.state.malformed_messages += 1
                        continue
                    self.state.last_message_monotonic = time.monotonic()
                    instrument = str(msg.get("instrument", self.state.instrument) or "")
                    if instrument:
                        self.state.instrument = instrument
                    self.state.mbo_available = bool(msg.get("mbo_available", False))
                    self.state.latest = msg
                    self._apply_health(msg)
                    if self.on_event:
                        await self.on_event(msg)
            except asyncio.TimeoutError:
                self.state.health = Health.DEGRADED
            except (OSError, ConnectionError):
                self.state.health = Health.OFFLINE
            finally:
                if writer is not None:
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except (ConnectionError, OSError):
                        pass
            if not self._stop.is_set():
                self.state.reconnects += 1
                await asyncio.sleep(backoff)
                backoff = min(5.0, backoff * 1.7)
