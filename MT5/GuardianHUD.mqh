#ifndef __GOLDTRADING_GUARDIAN_HUD_MQH__
#define __GOLDTRADING_GUARDIAN_HUD_MQH__

string g_hud_regime="UNKNOWN";
string g_hud_bias="NEUTRAL";
string g_hud_support="-";
string g_hud_resistance="-";
string g_hud_long_zone="-";
string g_hud_short_zone="-";
string g_hud_orderflow="数据不足";
string g_hud_ai="OFFLINE";
string g_hud_latency="-";
string g_hud_system="STARTING";
ulong  g_hud_last_update_ms=0;

void GuardianHudApply(string &p[])
{
   if(ArraySize(p)<11) return;
   g_hud_regime=p[1];
   g_hud_bias=p[2];
   g_hud_support=p[3];
   g_hud_resistance=p[4];
   g_hud_long_zone=p[5];
   g_hud_short_zone=p[6];
   g_hud_orderflow=p[7];
   g_hud_ai=p[8];
   g_hud_latency=p[9];
   g_hud_system=p[10];
   g_hud_last_update_ms=GetTickCount64();
}

double GuardianTotalFloatingProfit()
{
   double total=0.0;
   for(int i=0;i<PositionsTotal();i++)
   {
      ulong ticket=0;
      if(!IsSystemPositionByIndex(i,ticket) || !PositionSelectByTicket(ticket)) continue;
      total+=PositionGetDouble(POSITION_PROFIT);
   }
   return total;
}

void GuardianHudRender()
{
   if(!InpShowHud)
   {
      Comment("");
      return;
   }
   MqlTick tick;
   SymbolInfoTick(g_symbol,tick);
   double point=SymbolInfoDouble(g_symbol,SYMBOL_POINT);
   double spread=(point>0.0 ? (tick.ask-tick.bid)/point : 0.0);
   ulong now_ms=GetTickCount64();
   bool python_fresh=(g_hud_last_update_ms>0 && now_ms-g_hud_last_update_ms<=3500);
   string system_state=python_fresh ? g_hud_system : "PYTHON OFFLINE / GUARDIAN LOCAL";
   if(g_weekend_protection) system_state="WEEKEND PROTECTION";
   string text=StringFormat(
      "GoldTradingSystem Guardian v0.21\n"
      "%s  Bid %.5f  Ask %.5f  Spread %.1f\n"
      "市场状态: %s   偏向: %s\n"
      "强支撑: %s   强阻力: %s\n"
      "潜在多区: %s\n潜在空区: %s\n"
      "ATAS: %s   AI: %s   API: %s\n"
      "持仓: %d/2   浮盈亏: %.2f\n"
      "系统: %s",
      g_symbol,tick.bid,tick.ask,spread,g_hud_regime,g_hud_bias,
      g_hud_support,g_hud_resistance,g_hud_long_zone,g_hud_short_zone,
      g_hud_orderflow,g_hud_ai,g_hud_latency,ActiveLogicalSlots(),GuardianTotalFloatingProfit(),system_state);
   Comment(text);
}

void GuardianHudClear()
{
   Comment("");
}

#endif
