from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Awaitable, Callable
from .guardian_protocol import GuardianCommand


@dataclass(slots=True)
class GuardianConnectionState:
    connected: bool = False
    account: str = ""
    symbol: str = ""
    account_mode: str = ""
    ea_version: str = ""
    last_heartbeat: float = 0.0
    server_time: int = 0
    bid: float | None = None
    ask: float | None = None
    spread_points: float | None = None
    positions: int = 0
    orders: int = 0
    weekend_protection: bool = False
    slot_a_active: bool = False
    slot_a_side: str = ""
    slot_a_lot: float = 0.0
    slot_a_entry_price: float = 0.0
    slot_a_sl: float = 0.0
    slot_a_tp: float = 0.0
    slot_a_entry_time: int = 0
    slot_a_mfe: float = 0.0
    slot_a_mae: float = 0.0
    slot_b_active: bool = False
    slot_b_side: str = ""
    slot_b_lot: float = 0.0
    slot_b_entry_price: float = 0.0
    slot_b_sl: float = 0.0
    slot_b_tp: float = 0.0
    slot_b_entry_time: int = 0
    slot_b_mfe: float = 0.0
    slot_b_mae: float = 0.0


class GuardianServer:
    """Loopback-only command channel. The EA repeats every final safety check locally."""

    def __init__(self, host: str = "127.0.0.1", port: int = 17832,
                 on_event: Callable[[list[str]], Awaitable[None]] | None = None) -> None:
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Guardian server must remain loopback-only")
        self.host = host
        self.port = port
        self.on_event = on_event
        self.state = GuardianConnectionState()
        self._server: asyncio.AbstractServer | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._write_lock = asyncio.Lock()
        self._acks: dict[str, asyncio.Future[tuple[bool, str]]] = {}

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle_client, self.host, self.port)

    async def serve_forever(self) -> None:
        if self._server is None:
            await self.start()
        assert self._server is not None
        async with self._server:
            await self._server.serve_forever()

    async def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except ConnectionError:
                pass
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        self.state.connected = False

    def _parse_slot(self, parts: list[str], start: int, prefix: str) -> None:
        # active, side, lot, entry, sl, tp, entry_time, mfe, mae
        if len(parts) < start + 9:
            return
        try:
            setattr(self.state, prefix + "active", parts[start] == "1")
            setattr(self.state, prefix + "side", parts[start + 1])
            setattr(self.state, prefix + "lot", float(parts[start + 2] or 0))
            setattr(self.state, prefix + "entry_price", float(parts[start + 3] or 0))
            setattr(self.state, prefix + "sl", float(parts[start + 4] or 0))
            setattr(self.state, prefix + "tp", float(parts[start + 5] or 0))
            setattr(self.state, prefix + "entry_time", int(float(parts[start + 6] or 0)))
            setattr(self.state, prefix + "mfe", float(parts[start + 7] or 0))
            setattr(self.state, prefix + "mae", float(parts[start + 8] or 0))
        except (TypeError, ValueError):
            return

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        if peer and peer[0] not in {"127.0.0.1", "::1"}:
            writer.close(); await writer.wait_closed(); return
        if self._writer is not None and not self._writer.is_closing():
            self._writer.close()
        self._writer = writer
        self.state.connected = True
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip("\r\n")
                parts = text.split("|")
                if not parts:
                    continue
                kind = parts[0].upper()
                if kind == "HELLO" and len(parts) >= 5:
                    self.state.account, self.state.symbol, self.state.account_mode, self.state.ea_version = parts[1:5]
                elif kind == "HB" and len(parts) >= 8:
                    try:
                        self.state.last_heartbeat = time.monotonic()
                        self.state.server_time = int(float(parts[1]))
                        self.state.bid = float(parts[2]); self.state.ask = float(parts[3]); self.state.spread_points = float(parts[4])
                        self.state.positions = int(parts[5]); self.state.orders = int(parts[6]); self.state.weekend_protection = parts[7] == "1"
                    except (TypeError, ValueError):
                        continue
                    # v0.20 full slot payload: base fields 0..7, A=8..16, B=17..25.
                    if len(parts) >= 26:
                        self._parse_slot(parts, 8, "slot_a_")
                        self._parse_slot(parts, 17, "slot_b_")
                    elif len(parts) >= 10:  # legacy heartbeat
                        self.state.slot_a_active = parts[8] == "1"
                        self.state.slot_b_active = parts[9] == "1"
                elif kind == "ACK" and len(parts) >= 4:
                    fut = self._acks.pop(parts[1], None)
                    if fut and not fut.done():
                        fut.set_result((parts[2].upper() == "OK", "|".join(parts[3:])))
                if self.on_event:
                    await self.on_event(parts)
        finally:
            if self._writer is writer:
                self._writer = None
            self.state.connected = False
            for fut in list(self._acks.values()):
                if not fut.done():
                    fut.set_result((False, "Guardian disconnected"))
            self._acks.clear()
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass

    async def submit(self, command: GuardianCommand, timeout: float = 3.0) -> tuple[bool, str]:
        writer = self._writer
        if writer is None or writer.is_closing() or not self.state.connected:
            return False, "Guardian offline"
        if command.command_id in self._acks:
            return False, "duplicate command id already pending"
        loop = asyncio.get_running_loop()
        future: asyncio.Future[tuple[bool, str]] = loop.create_future()
        self._acks[command.command_id] = future
        try:
            async with self._write_lock:
                writer.write(command.to_wire().encode("utf-8"))
                await writer.drain()
            return await asyncio.wait_for(future, timeout=timeout)
        except (asyncio.TimeoutError, ConnectionError):
            self._acks.pop(command.command_id, None)
            return False, "Guardian ACK timeout"

    def heartbeat_fresh(self, max_age_seconds: float = 2.0) -> bool:
        return self.state.connected and (time.monotonic() - self.state.last_heartbeat) <= max_age_seconds
