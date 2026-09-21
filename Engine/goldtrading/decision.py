from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from .models import TradeIntent


@dataclass(frozen=True, slots=True)
class GuardianView:
    trading_allowed: bool
    weekend_protection_active: bool
    position_logic_count: int
    max_position_logics: int
    spread_ok: bool
    data_fresh: bool
    margin_ok: bool
    lot_ok: bool
    duplicate_order: bool
    conflicting_instruction: bool


def local_preflight(view: GuardianView) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    checks = [
        (view.trading_allowed, "market/trading permission unavailable"),
        (not view.weekend_protection_active, "weekend protection active"),
        (view.position_logic_count < view.max_position_logics, "max position logics reached"),
        (view.spread_ok, "spread abnormal"),
        (view.data_fresh, "data stale"),
        (view.margin_ok, "insufficient margin"),
        (view.lot_ok, "illegal lot"),
        (not view.duplicate_order, "duplicate order"),
        (not view.conflicting_instruction, "conflicting instruction"),
    ]
    for ok, reason in checks:
        if not ok:
            reasons.append(reason)
    return not reasons, reasons


def select_intent(intents: Iterable[TradeIntent], now: datetime) -> TradeIntent | None:
    """Only return one still-valid intent; local Guardian performs final checks again."""
    valid = [x for x in intents if x.valid_until >= now and x.action.upper() in {"OPEN", "CLOSE", "MODIFY_SL", "MODIFY_TP", "CANCEL"}]
    if not valid:
        return None
    return sorted(valid, key=lambda x: x.valid_until)[0]
