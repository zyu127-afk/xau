#ifndef __GOLDTRADING_GUARDIAN_STATE_MQH__
#define __GOLDTRADING_GUARDIAN_STATE_MQH__

bool     g_slot_active[2];
string   g_slot_side[2];
double   g_slot_lot[2];
double   g_slot_entry[2];
double   g_slot_original_sl[2];
double   g_slot_sl[2];
double   g_slot_tp[2];
datetime g_slot_time[2];
double   g_slot_mfe[2];
double   g_slot_mae[2];

int SlotIndex(const string slot){ if(slot=="A") return 0; if(slot=="B") return 1; return -1; }
string SlotName(const int i){ return i==0?"A":"B"; }
string StateKey(const string slot,const string field){ return StringFormat("GTS_STATE_%I64d_%s_%s_%s",AccountInfoInteger(ACCOUNT_LOGIN),g_symbol,slot,field); }

void ResetSlotIndex(const int i)
{
   if(i<0 || i>1) return;
   g_slot_active[i]=false; g_slot_side[i]=""; g_slot_lot[i]=0.0; g_slot_entry[i]=0.0;
   g_slot_original_sl[i]=0.0; g_slot_sl[i]=0.0; g_slot_tp[i]=0.0; g_slot_time[i]=0;
   g_slot_mfe[i]=0.0; g_slot_mae[i]=0.0;
}

void SaveSlot(const string slot)
{
   int i=SlotIndex(slot); if(i<0) return;
   GlobalVariableSet(StateKey(slot,"active"),g_slot_active[i]?1.0:0.0);
   GlobalVariableSet(StateKey(slot,"lot"),g_slot_lot[i]);
   GlobalVariableSet(StateKey(slot,"entry"),g_slot_entry[i]);
   GlobalVariableSet(StateKey(slot,"osl"),g_slot_original_sl[i]);
   GlobalVariableSet(StateKey(slot,"sl"),g_slot_sl[i]);
   GlobalVariableSet(StateKey(slot,"tp"),g_slot_tp[i]);
   GlobalVariableSet(StateKey(slot,"time"),(double)g_slot_time[i]);
   GlobalVariableSet(StateKey(slot,"mfe"),g_slot_mfe[i]);
   GlobalVariableSet(StateKey(slot,"mae"),g_slot_mae[i]);
   GlobalVariableSet(StateKey(slot,"side"),(g_slot_side[i]=="BUY"?1.0:(g_slot_side[i]=="SELL"?-1.0:0.0)));
   SetSlotActive(slot,g_slot_active[i]);
}

void LoadSlot(const string slot)
{
   int i=SlotIndex(slot); if(i<0) return;
   ResetSlotIndex(i);
   if(!GlobalVariableCheck(StateKey(slot,"active"))) return;
   g_slot_active[i]=GlobalVariableGet(StateKey(slot,"active"))>0.5;
   g_slot_lot[i]=GlobalVariableGet(StateKey(slot,"lot"));
   g_slot_entry[i]=GlobalVariableGet(StateKey(slot,"entry"));
   g_slot_original_sl[i]=GlobalVariableGet(StateKey(slot,"osl"));
   g_slot_sl[i]=GlobalVariableGet(StateKey(slot,"sl"));
   g_slot_tp[i]=GlobalVariableGet(StateKey(slot,"tp"));
   g_slot_time[i]=(datetime)(long)GlobalVariableGet(StateKey(slot,"time"));
   g_slot_mfe[i]=GlobalVariableGet(StateKey(slot,"mfe"));
   g_slot_mae[i]=GlobalVariableGet(StateKey(slot,"mae"));
   double raw_side=GlobalVariableGet(StateKey(slot,"side"));
   g_slot_side[i]=(raw_side>0.5?"BUY":(raw_side<-0.5?"SELL":""));
   SetSlotActive(slot,g_slot_active[i]);
}

void LoadLogicalState(){ LoadSlot("A"); LoadSlot("B"); }

ulong GuardianHashCommand(const string value)
{
   ulong h=1469598103934665603;
   for(int i=0;i<StringLen(value);i++){ h^=(ulong)StringGetCharacter(value,i); h*=1099511628211; }
   return h;
}
string CommandKey(const string id){ return StringFormat("GTS_CMD_%I64d_%s_%I64u",AccountInfoInteger(ACCOUNT_LOGIN),g_symbol,GuardianHashCommand(id)); }
bool CommandAlreadyProcessed(const string id){ return GlobalVariableCheck(CommandKey(id)); }
void MarkCommandProcessed(const string id,const bool ok){ GlobalVariableSet(CommandKey(id),ok?1.0:-1.0); }

bool ExistingNettingSideCompatible(const string side)
{
   ENUM_ACCOUNT_MARGIN_MODE mode=(ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   if(mode==ACCOUNT_MARGIN_MODE_RETAIL_HEDGING) return true;
   for(int i=0;i<2;i++) if(g_slot_active[i] && g_slot_side[i]!="" && g_slot_side[i]!=side) return false;
   return true;
}

void CaptureSlotAfterOpen(const string slot,const string side,const double lot,const double sl,const double tp)
{
   int i=SlotIndex(slot); if(i<0) return;
   ResetSlotIndex(i);
   g_slot_active[i]=true; g_slot_side[i]=side; g_slot_lot[i]=lot; g_slot_original_sl[i]=sl;
   g_slot_sl[i]=sl; g_slot_tp[i]=tp; g_slot_time[i]=TimeTradeServer();
   MqlTick tick; if(SymbolInfoTick(g_symbol,tick)) g_slot_entry[i]=(side=="BUY"?tick.ask:tick.bid);
   SaveSlot(slot);
}

void UpdateSlotExcursions()
{
   MqlTick tick; if(!SymbolInfoTick(g_symbol,tick)) return;
   for(int i=0;i<2;i++)
   {
      if(!g_slot_active[i] || g_slot_entry[i]<=0.0) continue;
      double px=(g_slot_side[i]=="BUY"?tick.bid:tick.ask);
      double move=(g_slot_side[i]=="BUY"?px-g_slot_entry[i]:g_slot_entry[i]-px);
      if(move>g_slot_mfe[i]) g_slot_mfe[i]=move;
      if(-move>g_slot_mae[i]) g_slot_mae[i]=-move;
      SaveSlot(SlotName(i));
   }
}

bool GuardianNettingReduce(const string side,const double lot)
{
   if(lot<=0.0) return false;
   g_trade.SetExpertMagicNumber(InpMagicNumber); g_trade.SetTypeFillingBySymbol(g_symbol);
   bool basic=(side=="BUY") ? g_trade.Sell(lot,g_symbol,0.0,0.0,0.0,"GTS-REDUCE") : g_trade.Buy(lot,g_symbol,0.0,0.0,0.0,"GTS-REDUCE");
   uint ret=g_trade.ResultRetcode();
   return basic && (ret==TRADE_RETCODE_DONE || ret==TRADE_RETCODE_DONE_PARTIAL);
}

bool CloseLogicalSlot(const string slot,const string reason)
{
   int i=SlotIndex(slot); if(i<0) return false;
   if(!g_slot_active[i]) return true;
   ENUM_ACCOUNT_MARGIN_MODE mode=(ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   bool ok=false;
   ulong ticket=GuardianFindPositionTicket(slot);
   if(mode==ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
   {
      if(ticket==0) ok=true;
      else { bool basic=g_trade.PositionClose(ticket); uint ret=g_trade.ResultRetcode(); ok=basic && (ret==TRADE_RETCODE_DONE || ret==TRADE_RETCODE_DONE_PARTIAL); }
   }
   else
   {
      if(ticket==0) ok=true;
      else if(PositionSelectByTicket(ticket))
      {
         double volume=PositionGetDouble(POSITION_VOLUME);
         if(g_slot_lot[i]>=volume-1e-8){ bool basic=g_trade.PositionClose(ticket); uint ret=g_trade.ResultRetcode(); ok=basic && (ret==TRADE_RETCODE_DONE || ret==TRADE_RETCODE_DONE_PARTIAL); }
         else ok=GuardianNettingReduce(g_slot_side[i],g_slot_lot[i]);
      }
   }
   if(ok)
   {
      PrintFormat("GUARDIAN CLOSE slot=%s reason=%s mfe=%.5f mae=%.5f",slot,reason,g_slot_mfe[i],g_slot_mae[i]);
      ResetSlotIndex(i); SaveSlot(slot);
   }
   return ok;
}

bool ModifyLogicalStops(const string slot,const double new_sl,const double new_tp)
{
   int i=SlotIndex(slot); if(i<0 || !g_slot_active[i] || new_sl<=0.0) return false;
   if(g_slot_sl[i]>0.0)
   {
      if(g_slot_side[i]=="BUY" && new_sl<g_slot_sl[i]) return false;
      if(g_slot_side[i]=="SELL" && new_sl>g_slot_sl[i]) return false;
   }
   g_slot_sl[i]=new_sl; g_slot_tp[i]=new_tp; SaveSlot(slot);
   ENUM_ACCOUNT_MARGIN_MODE mode=(ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   ulong ticket=GuardianFindPositionTicket(slot);
   if(ticket==0) return false;
   if(mode==ACCOUNT_MARGIN_MODE_RETAIL_HEDGING) return ModifyPositionStops(ticket,new_sl,new_tp);
   double hard_sl=new_sl;
   if(g_slot_active[0] && g_slot_active[1])
   {
      if(g_slot_side[i]=="BUY") hard_sl=MathMin(g_slot_sl[0],g_slot_sl[1]);
      else hard_sl=MathMax(g_slot_sl[0],g_slot_sl[1]);
   }
   return ModifyPositionStops(ticket,hard_sl,0.0);
}

void EnforceLogicalStops()
{
   MqlTick tick; if(!SymbolInfoTick(g_symbol,tick)) return;
   for(int i=0;i<2;i++)
   {
      if(!g_slot_active[i] || g_slot_sl[i]<=0.0) continue;
      double px=(g_slot_side[i]=="BUY"?tick.bid:tick.ask);
      bool hit=(g_slot_side[i]=="BUY"?px<=g_slot_sl[i]:px>=g_slot_sl[i]);
      if(hit) CloseLogicalSlot(SlotName(i),"logical stop hit");
   }
}

void ReconcileSlotStateWithBroker()
{
   ENUM_ACCOUNT_MARGIN_MODE mode=(ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   if(mode==ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
   {
      for(int i=0;i<2;i++) if(g_slot_active[i] && GuardianFindPositionTicket(SlotName(i))==0){ ResetSlotIndex(i); SaveSlot(SlotName(i)); }
   }
   else
   {
      bool has=false;
      for(int p=0;p<PositionsTotal();p++){ ulong ticket=0; if(IsSystemPositionByIndex(p,ticket)){ has=true; break; } }
      if(!has){ ResetSlotIndex(0); ResetSlotIndex(1); SaveSlot("A"); SaveSlot("B"); }
   }
}

string SlotWire(const string slot)
{
   int i=SlotIndex(slot); if(i<0) return "0||0|0|0|0|0|0|0|0";
   return StringFormat("%d|%s|%.8f|%.10f|%.10f|%.10f|%.10f|%I64d|%.10f|%.10f",
      (g_slot_active[i]?1:0),g_slot_side[i],g_slot_lot[i],g_slot_entry[i],g_slot_original_sl[i],g_slot_sl[i],g_slot_tp[i],(long)g_slot_time[i],g_slot_mfe[i],g_slot_mae[i]);
}

#endif
