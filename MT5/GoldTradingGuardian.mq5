#property strict
#property version   "0.11"
#property description "GoldTradingSystem Guardian - final local execution and risk authority"
#property description "IPC requires the local engine address to be allowed in MT5 Expert Advisors network settings."

#include <Trade/Trade.mqh>

input long   InpMagicNumber              = 26092101;
input double InpDefaultLot               = 0.01;
input int    InpMaxLogicalPositions      = 2;
input double InpMaxSpreadPoints          = 80.0;
input int    InpWeekendFlattenMinutes    = 30;
input int    InpTimerMilliseconds        = 250;
input bool   InpAllowNewTrades           = true;

CTrade g_trade;
bool   g_weekend_protection=false;
string g_symbol="";

string SlotKey(const string slot)
{
   return StringFormat("GTS_%I64d_%s_%s",AccountInfoInteger(ACCOUNT_LOGIN),g_symbol,slot);
}

bool SlotActive(const string slot)
{
   string key=SlotKey(slot);
   return GlobalVariableCheck(key) && GlobalVariableGet(key)>0.5;
}

void SetSlotActive(const string slot,const bool active)
{
   string key=SlotKey(slot);
   if(active) GlobalVariableSet(key,1.0);
   else if(GlobalVariableCheck(key)) GlobalVariableDel(key);
}

int ActiveLogicalSlots()
{
   int n=0;
   if(SlotActive("A")) n++;
   if(SlotActive("B")) n++;
   return n;
}

bool IsSystemPositionByIndex(const int index,ulong &ticket)
{
   ticket=PositionGetTicket(index);
   if(ticket==0 || !PositionSelectByTicket(ticket)) return false;
   if(PositionGetString(POSITION_SYMBOL)!=g_symbol) return false;
   if((long)PositionGetInteger(POSITION_MAGIC)!=InpMagicNumber) return false;
   return true;
}

bool IsSystemOrderByIndex(const int index,ulong &ticket)
{
   ticket=OrderGetTicket(index);
   if(ticket==0 || !OrderSelect(ticket)) return false;
   if(OrderGetString(ORDER_SYMBOL)!=g_symbol) return false;
   if((long)OrderGetInteger(ORDER_MAGIC)!=InpMagicNumber) return false;
   return true;
}

double NormalizeLot(const double requested)
{
   double min_lot=SymbolInfoDouble(g_symbol,SYMBOL_VOLUME_MIN);
   double max_lot=SymbolInfoDouble(g_symbol,SYMBOL_VOLUME_MAX);
   double step=SymbolInfoDouble(g_symbol,SYMBOL_VOLUME_STEP);
   if(step<=0) return 0.0;
   double v=MathRound(requested/step)*step;
   v=MathMax(min_lot,MathMin(max_lot,v));
   int digits=0;
   double s=step;
   while(s<1.0 && digits<8){ s*=10.0; digits++; }
   return NormalizeDouble(v,digits);
}

bool LotIsLegal(const double lot)
{
   double min_lot=SymbolInfoDouble(g_symbol,SYMBOL_VOLUME_MIN);
   double max_lot=SymbolInfoDouble(g_symbol,SYMBOL_VOLUME_MAX);
   double step=SymbolInfoDouble(g_symbol,SYMBOL_VOLUME_STEP);
   if(lot<min_lot || lot>max_lot || step<=0) return false;
   double n=lot/step;
   return MathAbs(n-MathRound(n))<1e-7;
}

bool SpreadIsHealthy()
{
   MqlTick tick;
   if(!SymbolInfoTick(g_symbol,tick)) return false;
   double point=SymbolInfoDouble(g_symbol,SYMBOL_POINT);
   if(point<=0) return false;
   return ((tick.ask-tick.bid)/point)<=InpMaxSpreadPoints;
}

bool HasMargin(const ENUM_ORDER_TYPE type,const double lot)
{
   MqlTick tick;
   if(!SymbolInfoTick(g_symbol,tick)) return false;
   double price=(type==ORDER_TYPE_BUY ? tick.ask : tick.bid);
   double margin=0.0;
   if(!OrderCalcMargin(type,g_symbol,lot,price,margin)) return false;
   return AccountInfoDouble(ACCOUNT_MARGIN_FREE)>=margin;
}

int SecondsOfDay(const datetime value)
{
   MqlDateTime x;
   TimeToStruct(value,x);
   return x.hour*3600+x.min*60+x.sec;
}

bool FridayLastSessionEndSeconds(int &seconds_out)
{
   seconds_out=-1;
   datetime from=0,to=0;
   for(uint i=0;i<32;i++)
   {
      if(!SymbolInfoSessionTrade(g_symbol,FRIDAY,i,from,to)) break;
      int sec=SecondsOfDay(to);
      if(sec==0) sec=24*3600;
      if(sec>seconds_out) seconds_out=sec;
   }
   return seconds_out>0;
}

bool WeekendProtectionShouldBeActive()
{
   datetime now=TimeTradeServer();
   MqlDateTime dt;
   TimeToStruct(now,dt);
   if(dt.day_of_week==0 || dt.day_of_week==6) return true;
   if(dt.day_of_week!=5) return false;
   int end_sec=0;
   if(!FridayLastSessionEndSeconds(end_sec)) return true;
   int now_sec=dt.hour*3600+dt.min*60+dt.sec;
   return now_sec>=end_sec-InpWeekendFlattenMinutes*60;
}

void CancelAllSystemOrders()
{
   for(int i=OrdersTotal()-1;i>=0;i--)
   {
      ulong ticket=0;
      if(!IsSystemOrderByIndex(i,ticket)) continue;
      bool basic=g_trade.OrderDelete(ticket);
      if(!basic || g_trade.ResultRetcode()!=TRADE_RETCODE_DONE)
         PrintFormat("GUARDIAN cancel failed ticket=%I64u ret=%u %s",ticket,g_trade.ResultRetcode(),g_trade.ResultRetcodeDescription());
   }
}

void CloseAllSystemPositions()
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong ticket=0;
      if(!IsSystemPositionByIndex(i,ticket)) continue;
      bool basic=g_trade.PositionClose(ticket);
      if(!basic || (g_trade.ResultRetcode()!=TRADE_RETCODE_DONE && g_trade.ResultRetcode()!=TRADE_RETCODE_DONE_PARTIAL))
         PrintFormat("GUARDIAN close failed ticket=%I64u ret=%u %s",ticket,g_trade.ResultRetcode(),g_trade.ResultRetcodeDescription());
   }
   bool any=false;
   for(int i=0;i<PositionsTotal();i++)
   {
      ulong ticket=0;
      if(IsSystemPositionByIndex(i,ticket)){ any=true; break; }
   }
   if(!any){ SetSlotActive("A",false); SetSlotActive("B",false); }
}

void EnforceWeekendProtection()
{
   g_weekend_protection=WeekendProtectionShouldBeActive();
   if(!g_weekend_protection) return;
   CancelAllSystemOrders();
   CloseAllSystemPositions();
}

bool PriceInsideZone(const double price,const double zone_low,const double zone_high)
{
   return zone_low<=zone_high && price>=zone_low && price<=zone_high;
}

bool ValidateNewOrder(const string slot,const ENUM_ORDER_TYPE type,const double lot,const double sl,
                      const double zone_low,const double zone_high,const datetime valid_until,string &why)
{
   if(!InpAllowNewTrades){ why="new trading disabled"; return false; }
   if(g_weekend_protection || WeekendProtectionShouldBeActive()){ why="weekend protection"; return false; }
   if(slot!="A" && slot!="B"){ why="invalid logical slot"; return false; }
   if(SlotActive(slot)){ why="logical slot already active"; return false; }
   if(ActiveLogicalSlots()>=InpMaxLogicalPositions){ why="max logical positions"; return false; }
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED)){ why="terminal trading disabled"; return false; }
   long mode=SymbolInfoInteger(g_symbol,SYMBOL_TRADE_MODE);
   if(mode==SYMBOL_TRADE_MODE_DISABLED || mode==SYMBOL_TRADE_MODE_CLOSEONLY){ why="symbol cannot open new trades"; return false; }
   if(!LotIsLegal(lot)){ why="illegal lot"; return false; }
   if(!SpreadIsHealthy()){ why="spread abnormal"; return false; }
   if(!HasMargin(type,lot)){ why="insufficient margin"; return false; }
   if(sl<=0.0){ why="real server SL required"; return false; }
   if(TimeTradeServer()>valid_until){ why="command expired"; return false; }
   MqlTick tick;
   if(!SymbolInfoTick(g_symbol,tick)){ why="no current tick"; return false; }
   double price=(type==ORDER_TYPE_BUY ? tick.ask : tick.bid);
   if(!PriceInsideZone(price,zone_low,zone_high)){ why="price outside valid zone"; return false; }
   int stops=(int)SymbolInfoInteger(g_symbol,SYMBOL_TRADE_STOPS_LEVEL);
   double point=SymbolInfoDouble(g_symbol,SYMBOL_POINT);
   if(type==ORDER_TYPE_BUY && sl>=price-stops*point){ why="SL violates stops level"; return false; }
   if(type==ORDER_TYPE_SELL && sl<=price+stops*point){ why="SL violates stops level"; return false; }
   why="OK";
   return true;
}

bool OpenMarket(const string slot,const string side,const double requested_lot,const double sl,const double tp,
                const double zone_low,const double zone_high,const datetime valid_until,const string reason)
{
   if(side!="BUY" && side!="SELL"){ Print("GUARDIAN reject: invalid side"); return false; }
   double lot=NormalizeLot(requested_lot);
   ENUM_ORDER_TYPE type=(side=="BUY" ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   string why="";
   if(!ValidateNewOrder(slot,type,lot,sl,zone_low,zone_high,valid_until,why))
   {
      PrintFormat("GUARDIAN reject OPEN slot=%s reason=%s",slot,why);
      return false;
   }
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFillingBySymbol(g_symbol);
   string comment=StringFormat("GTS-%s",slot);
   bool basic=(type==ORDER_TYPE_BUY)
      ? g_trade.Buy(lot,g_symbol,0.0,sl,tp,comment)
      : g_trade.Sell(lot,g_symbol,0.0,sl,tp,comment);
   uint ret=g_trade.ResultRetcode();
   bool done=basic && (ret==TRADE_RETCODE_DONE || ret==TRADE_RETCODE_DONE_PARTIAL);
   if(done)
   {
      SetSlotActive(slot,true);
      PrintFormat("GUARDIAN OPEN accepted slot=%s side=%s lot=%.4f reason=%s",slot,side,lot,reason);
      return true;
   }
   PrintFormat("GUARDIAN OPEN failed slot=%s ret=%u %s",slot,ret,g_trade.ResultRetcodeDescription());
   return false;
}

bool ModifyPositionStops(const ulong ticket,const double new_sl,const double new_tp)
{
   if(!PositionSelectByTicket(ticket)) return false;
   if(PositionGetString(POSITION_SYMBOL)!=g_symbol) return false;
   if((long)PositionGetInteger(POSITION_MAGIC)!=InpMagicNumber) return false;
   double old_sl=PositionGetDouble(POSITION_SL);
   ENUM_POSITION_TYPE type=(ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   if(old_sl>0.0)
   {
      if(type==POSITION_TYPE_BUY && new_sl<old_sl) return false;
      if(type==POSITION_TYPE_SELL && new_sl>old_sl) return false;
   }
   if(new_sl<=0.0) return false;
   bool basic=g_trade.PositionModify(ticket,new_sl,new_tp);
   uint ret=g_trade.ResultRetcode();
   return basic && ret==TRADE_RETCODE_DONE;
}

#include "GuardianIPC.mqh"

void ReconcileHedgingSlots()
{
   ENUM_ACCOUNT_MARGIN_MODE mode=(ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   if(mode!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING) return;
   bool a=false,b=false;
   for(int i=0;i<PositionsTotal();i++)
   {
      ulong ticket=0;
      if(!IsSystemPositionByIndex(i,ticket) || !PositionSelectByTicket(ticket)) continue;
      string c=PositionGetString(POSITION_COMMENT);
      if(c=="GTS-A") a=true;
      if(c=="GTS-B") b=true;
   }
   SetSlotActive("A",a);
   SetSlotActive("B",b);
}

int OnInit()
{
   g_symbol=_Symbol;
   if(InpMaxLogicalPositions!=2)
   {
      Print("V1 requires exactly 2 logical position slots");
      return INIT_PARAMETERS_INCORRECT;
   }
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetMarginMode();
   g_trade.SetTypeFillingBySymbol(g_symbol);
   ReconcileHedgingSlots();
   EventSetMillisecondTimer(MathMax(100,InpTimerMilliseconds));
   PrintFormat("GoldTrading Guardian initialized account=%I64d symbol=%s",AccountInfoInteger(ACCOUNT_LOGIN),g_symbol);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   GuardianIpcClose();
   // Normal shutdown does not flatten positions. Existing server SL remains active.
}

void OnTimer()
{
   EnforceWeekendProtection();
   GuardianIpcPoll();
}

void OnTick()
{
   // No single local indicator may open a trade. Execution arrives only through the guarded IPC path.
}

void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)
{
   if(trans.symbol!=g_symbol) return;
   PrintFormat("GUARDIAN tx type=%d order=%I64u deal=%I64u ret=%u",trans.type,trans.order,trans.deal,result.retcode);
}
