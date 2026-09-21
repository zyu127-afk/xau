#ifndef __GOLDTRADING_GUARDIAN_STATE_MQH__
#define __GOLDTRADING_GUARDIAN_STATE_MQH__

struct LogicalSlotState
{
   bool active;
   string side;
   double lot;
   double entry_price;
   double original_sl;
   double current_sl;
   double current_tp;
   datetime entry_time;
   double mfe;
   double mae;
};

LogicalSlotState g_slot_a;
LogicalSlotState g_slot_b;

string StateKey(const string slot,const string field)
{
   return StringFormat("GTS_STATE_%I64d_%s_%s_%s",AccountInfoInteger(ACCOUNT_LOGIN),g_symbol,slot,field);
}

void SlotReset(LogicalSlotState &s)
{
   s.active=false; s.side=""; s.lot=0.0; s.entry_price=0.0; s.original_sl=0.0;
   s.current_sl=0.0; s.current_tp=0.0; s.entry_time=0; s.mfe=0.0; s.mae=0.0;
}

LogicalSlotState &SlotRef(const string slot)
{
   if(slot=="A") return g_slot_a;
   return g_slot_b;
}

void SaveSlot(const string slot)
{
   LogicalSlotState &s=SlotRef(slot);
   GlobalVariableSet(StateKey(slot,"active"),s.active?1.0:0.0);
   GlobalVariableSet(StateKey(slot,"lot"),s.lot);
   GlobalVariableSet(StateKey(slot,"entry"),s.entry_price);
   GlobalVariableSet(StateKey(slot,"osl"),s.original_sl);
   GlobalVariableSet(StateKey(slot,"sl"),s.current_sl);
   GlobalVariableSet(StateKey(slot,"tp"),s.current_tp);
   GlobalVariableSet(StateKey(slot,"time"),(double)s.entry_time);
   GlobalVariableSet(StateKey(slot,"mfe"),s.mfe);
   GlobalVariableSet(StateKey(slot,"mae"),s.mae);
   GlobalVariableSet(StateKey(slot,"side"),(s.side=="BUY"?1.0:(s.side=="SELL"?-1.0:0.0)));
   SetSlotActive(slot,s.active);
}

void LoadSlot(const string slot)
{
   LogicalSlotState &s=SlotRef(slot);
   SlotReset(s);
   if(!GlobalVariableCheck(StateKey(slot,"active"))) return;
   s.active=GlobalVariableGet(StateKey(slot,"active"))>0.5;
   s.lot=GlobalVariableGet(StateKey(slot,"lot"));
   s.entry_price=GlobalVariableGet(StateKey(slot,"entry"));
   s.original_sl=GlobalVariableGet(StateKey(slot,"osl"));
   s.current_sl=GlobalVariableGet(StateKey(slot,"sl"));
   s.current_tp=GlobalVariableGet(StateKey(slot,"tp"));
   s.entry_time=(datetime)(long)GlobalVariableGet(StateKey(slot,"time"));
   s.mfe=GlobalVariableGet(StateKey(slot,"mfe"));
   s.mae=GlobalVariableGet(StateKey(slot,"mae"));
   double raw_side=GlobalVariableGet(StateKey(slot,"side"));
   s.side=(raw_side>0.5?"BUY":(raw_side<-0.5?"SELL":""));
   SetSlotActive(slot,s.active);
}

void LoadLogicalState()
{
   LoadSlot("A");
   LoadSlot("B");
}

ulong GuardianHashCommand(const string value)
{
   ulong h=1469598103934665603;
   for(int i=0;i<StringLen(value);i++)
   {
      h^=(ulong)StringGetCharacter(value,i);
      h*=1099511628211;
   }
   return h;
}

string CommandKey(const string id)
{
   return StringFormat("GTS_CMD_%I64d_%s_%I64u",AccountInfoInteger(ACCOUNT_LOGIN),g_symbol,GuardianHashCommand(id));
}

bool CommandAlreadyProcessed(const string id)
{
   return GlobalVariableCheck(CommandKey(id));
}

void MarkCommandProcessed(const string id,const bool ok)
{
   GlobalVariableSet(CommandKey(id),ok?1.0:-1.0);
}

bool ExistingNettingSideCompatible(const string side)
{
   ENUM_ACCOUNT_MARGIN_MODE mode=(ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   if(mode==ACCOUNT_MARGIN_MODE_RETAIL_HEDGING) return true;
   if(g_slot_a.active && g_slot_a.side!="" && g_slot_a.side!=side) return false;
   if(g_slot_b.active && g_slot_b.side!="" && g_slot_b.side!=side) return false;
   return true;
}

void CaptureSlotAfterOpen(const string slot,const string side,const double requested_lot,const double requested_sl,const double requested_tp)
{
   LogicalSlotState &s=SlotRef(slot);
   SlotReset(s);
   s.active=true;
   s.side=side;
   s.lot=requested_lot;
   s.original_sl=requested_sl;
   s.current_sl=requested_sl;
   s.current_tp=requested_tp;
   s.entry_time=TimeTradeServer();
   MqlTick tick;
   if(SymbolInfoTick(g_symbol,tick)) s.entry_price=(side=="BUY"?tick.ask:tick.bid);
   SaveSlot(slot);
}

void UpdateSlotExcursions()
{
   MqlTick tick;
   if(!SymbolInfoTick(g_symbol,tick)) return;
   string slots[2]={"A","B"};
   for(int i=0;i<2;i++)
   {
      LogicalSlotState &s=SlotRef(slots[i]);
      if(!s.active || s.entry_price<=0.0) continue;
      double px=(s.side=="BUY"?tick.bid:tick.ask);
      double move=(s.side=="BUY"?px-s.entry_price:s.entry_price-px);
      if(move>s.mfe) s.mfe=move;
      if(-move>s.mae) s.mae=-move;
      SaveSlot(slots[i]);
   }
}

bool GuardianNettingReduce(const string side,const double lot)
{
   if(lot<=0.0) return false;
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFillingBySymbol(g_symbol);
   bool basic=(side=="BUY")
      ? g_trade.Sell(lot,g_symbol,0.0,0.0,0.0,"GTS-REDUCE")
      : g_trade.Buy(lot,g_symbol,0.0,0.0,0.0,"GTS-REDUCE");
   uint ret=g_trade.ResultRetcode();
   return basic && (ret==TRADE_RETCODE_DONE || ret==TRADE_RETCODE_DONE_PARTIAL);
}

bool CloseLogicalSlot(const string slot,const string reason)
{
   if(slot!="A" && slot!="B") return false;
   LogicalSlotState &s=SlotRef(slot);
   if(!s.active) return true;
   ENUM_ACCOUNT_MARGIN_MODE mode=(ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   bool ok=false;
   if(mode==ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
   {
      ulong ticket=GuardianFindPositionTicket(slot);
      if(ticket>0)
      {
         bool basic=g_trade.PositionClose(ticket);
         uint ret=g_trade.ResultRetcode();
         ok=basic && (ret==TRADE_RETCODE_DONE || ret==TRADE_RETCODE_DONE_PARTIAL);
      }
   }
   else
   {
      ulong ticket=GuardianFindPositionTicket(slot);
      if(ticket==0) ok=true;
      else if(PositionSelectByTicket(ticket))
      {
         double volume=PositionGetDouble(POSITION_VOLUME);
         if(s.lot>=volume-1e-8)
         {
            bool basic=g_trade.PositionClose(ticket);
            uint ret=g_trade.ResultRetcode();
            ok=basic && (ret==TRADE_RETCODE_DONE || ret==TRADE_RETCODE_DONE_PARTIAL);
         }
         else ok=GuardianNettingReduce(s.side,s.lot);
      }
   }
   if(ok)
   {
      PrintFormat("GUARDIAN CLOSE slot=%s reason=%s mfe=%.5f mae=%.5f",slot,reason,s.mfe,s.mae);
      SlotReset(s);
      SaveSlot(slot);
   }
   return ok;
}

bool ModifyLogicalStops(const string slot,const double new_sl,const double new_tp)
{
   LogicalSlotState &s=SlotRef(slot);
   if(!s.active || new_sl<=0.0) return false;
   if(s.current_sl>0.0)
   {
      if(s.side=="BUY" && new_sl<s.current_sl) return false;
      if(s.side=="SELL" && new_sl>s.current_sl) return false;
   }
   s.current_sl=new_sl;
   s.current_tp=new_tp;
   SaveSlot(slot);
   ENUM_ACCOUNT_MARGIN_MODE mode=(ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   if(mode==ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
   {
      ulong ticket=GuardianFindPositionTicket(slot);
      return ticket>0 && ModifyPositionStops(ticket,new_sl,new_tp);
   }
   ulong ticket=GuardianFindPositionTicket(slot);
   if(ticket==0 || !PositionSelectByTicket(ticket)) return false;
   double hard_sl=new_sl;
   if(g_slot_a.active && g_slot_b.active)
   {
      if(s.side=="BUY") hard_sl=MathMin(g_slot_a.current_sl,g_slot_b.current_sl);
      else hard_sl=MathMax(g_slot_a.current_sl,g_slot_b.current_sl);
   }
   return ModifyPositionStops(ticket,hard_sl,0.0);
}

void EnforceLogicalStops()
{
   MqlTick tick;
   if(!SymbolInfoTick(g_symbol,tick)) return;
   string slots[2]={"A","B"};
   for(int i=0;i<2;i++)
   {
      LogicalSlotState &s=SlotRef(slots[i]);
      if(!s.active || s.current_sl<=0.0) continue;
      double px=(s.side=="BUY"?tick.bid:tick.ask);
      bool hit=(s.side=="BUY"?px<=s.current_sl:px>=s.current_sl);
      if(hit) CloseLogicalSlot(slots[i],"logical stop hit");
   }
}

void ReconcileSlotStateWithBroker()
{
   ENUM_ACCOUNT_MARGIN_MODE mode=(ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   if(mode==ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
   {
      string slots[2]={"A","B"};
      for(int i=0;i<2;i++)
      {
         LogicalSlotState &s=SlotRef(slots[i]);
         ulong ticket=GuardianFindPositionTicket(slots[i]);
         if(ticket==0 && s.active)
         {
            SlotReset(s);
            SaveSlot(slots[i]);
         }
      }
   }
   else
   {
      bool has=false;
      for(int i=0;i<PositionsTotal();i++)
      {
         ulong ticket=0;
         if(IsSystemPositionByIndex(i,ticket)){ has=true; break; }
      }
      if(!has)
      {
         SlotReset(g_slot_a); SlotReset(g_slot_b);
         SaveSlot("A"); SaveSlot("B");
      }
   }
}

string SlotWire(const string slot)
{
   LogicalSlotState &s=SlotRef(slot);
   return StringFormat("%d|%s|%.8f|%.10f|%.10f|%.10f|%I64d|%.10f|%.10f",
      (s.active?1:0),s.side,s.lot,s.entry_price,s.current_sl,s.current_tp,(long)s.entry_time,s.mfe,s.mae);
}

#endif
