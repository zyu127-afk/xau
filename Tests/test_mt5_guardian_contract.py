from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "MT5" / "GoldTradingGuardian.mq5").read_text(encoding="utf-8")
IPC = (ROOT / "MT5" / "GuardianIPC.mqh").read_text(encoding="utf-8")
STATE = (ROOT / "MT5" / "GuardianState.mqh").read_text(encoding="utf-8")


def test_guardian_uses_current_chart_symbol_and_exactly_two_logical_slots():
    assert "g_symbol=_Symbol;" in MAIN
    assert "XAUUSD" not in MAIN
    assert "InpMaxLogicalPositions      = 2" in MAIN
    assert "if(InpMaxLogicalPositions!=2)" in MAIN
    assert 'SlotActive("A")' in MAIN
    assert 'SlotActive("B")' in MAIN


def test_weekend_protection_uses_real_friday_symbol_session_and_flattens_system_exposure():
    assert "SymbolInfoSessionTrade(g_symbol,FRIDAY" in MAIN
    assert "WeekendProtectionShouldBeActive" in MAIN
    assert "InpWeekendFlattenMinutes" in MAIN
    weekend = MAIN.split("void EnforceWeekendProtection()", 1)[1].split("bool PriceInsideZone", 1)[0]
    assert "CancelAllSystemOrders();" in weekend
    assert "CloseAllSystemPositions();" in weekend
    assert "EnforceWeekendProtection();" in MAIN.split("void OnTimer()", 1)[1]


def test_open_requires_server_sl_and_hard_closes_if_server_protection_cannot_be_verified():
    assert 'if(sl<=0.0){ why="real server SL required"; return false; }' in MAIN
    open_market = MAIN.split("bool OpenMarket(", 1)[1].split("bool ModifyPositionStops", 1)[0]
    assert "PositionHasServerStopForSlot(slot)" in open_market
    assert "ModifyLogicalStops(slot,sl,tp)" in open_market
    assert 'CloseLogicalSlot(slot,"server SL verification failed")' in open_market


def test_stop_modification_never_widens_existing_protection():
    modify = MAIN.split("bool ModifyPositionStops(", 1)[1].split('#include "GuardianState.mqh"', 1)[0]
    assert "type==POSITION_TYPE_BUY && new_sl<old_sl" in modify
    assert "type==POSITION_TYPE_SELL && new_sl>old_sl" in modify
    logical = STATE.split("bool ModifyLogicalStops(", 1)[1].split("void EnforceLogicalStops", 1)[0]
    assert 'g_slot_side[i]=="BUY" && new_sl<g_slot_sl[i]' in logical
    assert 'g_slot_side[i]=="SELL" && new_sl>g_slot_sl[i]' in logical


def test_guardian_ipc_is_loopback_by_default_and_reports_both_logical_slots():
    assert 'InpEngineHost       = "127.0.0.1"' in IPC
    assert "InpEnginePort       = 17832" in IPC
    assert 'StringFormat("HELLO|%I64d|%s|%s|0.21\\n"' in IPC
    assert 'SlotWire("A")' in IPC
    assert 'SlotWire("B")' in IPC
    assert '"HB|%I64d|' in IPC
