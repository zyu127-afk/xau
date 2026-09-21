from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from .structure import Bar


@dataclass(frozen=True, slots=True)
class SymbolSpec:
    symbol: str
    volume_min: float
    volume_max: float
    volume_step: float
    point: float
    tick_size: float
    tick_value: float
    digits: int
    stops_level: int
    contract_size: float
    trade_mode: int


class MT5DataProvider:
    """Optional Windows data adapter. Guardian remains the only execution authority."""

    def __init__(self, terminal_path: str | None = None) -> None:
        self.terminal_path = terminal_path or None
        self.mt5: Any = None
        self.connected = False

    def connect(self) -> bool:
        try:
            import MetaTrader5 as mt5
        except ImportError:
            self.connected = False
            return False
        self.mt5 = mt5
        kwargs = {"path": self.terminal_path} if self.terminal_path else {}
        self.connected = bool(mt5.initialize(**kwargs))
        return self.connected

    def shutdown(self) -> None:
        if self.mt5 is not None and self.connected:
            self.mt5.shutdown()
        self.connected = False

    def account(self) -> dict[str, Any] | None:
        if not self.connected:
            return None
        info = self.mt5.account_info()
        return None if info is None else info._asdict()

    def tick(self, symbol: str) -> dict[str, Any] | None:
        if not self.connected:
            return None
        tick = self.mt5.symbol_info_tick(symbol)
        return None if tick is None else tick._asdict()

    def symbol_spec(self, symbol: str) -> SymbolSpec | None:
        if not self.connected:
            return None
        info = self.mt5.symbol_info(symbol)
        if info is None:
            return None
        return SymbolSpec(
            symbol=symbol,
            volume_min=float(info.volume_min), volume_max=float(info.volume_max), volume_step=float(info.volume_step),
            point=float(info.point), tick_size=float(info.trade_tick_size), tick_value=float(info.trade_tick_value),
            digits=int(info.digits), stops_level=int(info.trade_stops_level), contract_size=float(info.trade_contract_size),
            trade_mode=int(info.trade_mode),
        )

    def bars(self, symbol: str, timeframe: str, count: int = 300) -> list[Bar]:
        if not self.connected:
            return []
        tf_map = {
            "D1": self.mt5.TIMEFRAME_D1, "H4": self.mt5.TIMEFRAME_H4, "H1": self.mt5.TIMEFRAME_H1,
            "M30": self.mt5.TIMEFRAME_M30, "M15": self.mt5.TIMEFRAME_M15,
            "M5": self.mt5.TIMEFRAME_M5, "M1": self.mt5.TIMEFRAME_M1,
        }
        tf = tf_map.get(timeframe)
        if tf is None:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        rates = self.mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None:
            return []
        return [Bar(str(int(r["time"])), float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), float(r["tick_volume"])) for r in rates]

    def positions(self, symbol: str) -> list[dict[str, Any]]:
        if not self.connected:
            return []
        rows = self.mt5.positions_get(symbol=symbol) or []
        return [x._asdict() for x in rows]

    def orders(self, symbol: str) -> list[dict[str, Any]]:
        if not self.connected:
            return []
        rows = self.mt5.orders_get(symbol=symbol) or []
        return [x._asdict() for x in rows]
