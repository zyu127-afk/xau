#ifndef __GOLDTRADING_GUARDIAN_IPC_MQH__
#define __GOLDTRADING_GUARDIAN_IPC_MQH__

input bool   InpIpcEnabled       = true;
input string InpEngineHost       = "127.0.0.1";
input uint   InpEnginePort       = 17832;
input uint   InpConnectTimeoutMs = 250;

int    g_ipc_socket=INVALID_HANDLE;
string g_ipc_buffer="";
long   g_last_heartbeat_ms=0;

string GuardianAccountMode()
{
   ENUM_ACCOUNT_MARGIN_MODE mode=(ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   if(mode==ACCOUNT_MARGIN_MODE_RETAIL_HEDGING) return "HEDGING";
   return "NETTING";
}

int GuardianSystemPositionCount()
{
   int n=0;
   for(int i=0;i<PositionsTotal();i++){ ulong ticket=0; if(IsSystemPositionByIndex(i,ticket)) n++; }
   return n;
}

int GuardianSystemOrderCount()
{
   int n=0;
   for(int i=0;i<OrdersTotal();i++){ ulong ticket=0; if(IsSystemOrderByIndex(i,ticket)) n++; }
   return n;
}

bool GuardianIpcSend(const string text)
{
   if(g_ipc_socket==INVALID_HANDLE || !SocketIsConnected(g_ipc_socket) || !SocketIsWritable(g_ipc_socket)) return false;
   uchar data[];
   int copied=StringToCharArray(text,data,0,StringLen(text),CP_UTF8);
   if(copied<=0) return false;
   return SocketSend(g_ipc_socket,data,(uint)copied)==copied;
}

void GuardianIpcClose()
{
   if(g_ipc_socket!=INVALID_HANDLE){ SocketClose(g_ipc_socket); g_ipc_socket=INVALID_HANDLE; }
   g_ipc_buffer="";
}

bool GuardianIpcConnect()
{
   if(!InpIpcEnabled) return false;
   if(g_ipc_socket!=INVALID_HANDLE && SocketIsConnected(g_ipc_socket)) return true;
   GuardianIpcClose();
   ResetLastError();
   g_ipc_socket=SocketCreate();
   if(g_ipc_socket==INVALID_HANDLE){ PrintFormat("GUARDIAN IPC SocketCreate failed error=%d",GetLastError()); return false; }
   if(!SocketConnect(g_ipc_socket,InpEngineHost,InpEnginePort,InpConnectTimeoutMs))
   {
      int err=GetLastError();
      PrintFormat("GUARDIAN IPC connect failed %s:%u error=%d. Allow localhost in MT5 Expert Advisors network settings.",InpEngineHost,InpEnginePort,err);
      GuardianIpcClose(); return false;
   }
   SocketTimeouts(g_ipc_socket,50,50);
   GuardianIpcSend(StringFormat("HELLO|%I64d|%s|%s|0.21\n",AccountInfoInteger(ACCOUNT_LOGIN),g_symbol,GuardianAccountMode()));
   PrintFormat("GUARDIAN IPC connected to %s:%u",InpEngineHost,InpEnginePort);
   return true;
}

void GuardianIpcAck(const string command_id,const bool ok,const string reason)
{
   string clean=reason;
   StringReplace(clean,"|","/"); StringReplace(clean,"\r"," "); StringReplace(clean,"\n"," ");
   GuardianIpcSend(StringFormat("ACK|%s|%s|%s\n",command_id,(ok?"OK":"REJECT"),clean));
}

ulong GuardianFindPositionTicket(const string slot)
{
   ENUM_ACCOUNT_MARGIN_MODE mode=(ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   for(int i=0;i<PositionsTotal();i++)
   {
      ulong ticket=0;
      if(!IsSystemPositionByIndex(i,ticket)) continue;
      if(mode!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING) return ticket;
      if(PositionSelectByTicket(ticket) && PositionGetString(POSITION_COMMENT)==StringFormat("GTS-%s",slot)) return ticket;
   }
   return 0;
}

void GuardianFinishCommand(const string id,const bool ok,const string reason)
{
   MarkCommandProcessed(id,ok);
   GuardianIpcAck(id,ok,reason);
}

void GuardianHandleCommand(const string line)
{
   string p[];
   int n=StringSplit(line,(ushort)StringGetCharacter("|",0),p);
   if(n>=1 && p[0]=="STATUS")
   {
      GuardianHudApply(p);
      return;
   }
   if(n<3 || p[0]!="GTS1") return;
   string id=p[1],action=p[2];
   if(id=="") return;
   if(CommandAlreadyProcessed(id))
   {
      GuardianIpcAck(id,true,"duplicate command already processed");
      return;
   }
   if(action=="CLOSE_ALL")
   {
      CancelAllSystemOrders(); CloseAllSystemPositions(); ReconcileSlotStateWithBroker();
      GuardianFinishCommand(id,true,"closed all system exposure"); return;
   }
   if(action=="CANCEL_ALL")
   {
      CancelAllSystemOrders(); GuardianFinishCommand(id,true,"cancelled all system orders"); return;
   }
   if(n<12){ GuardianFinishCommand(id,false,"malformed command"); return; }
   string slot=p[3],side=p[4];
   double lot=StringToDouble(p[5]),sl=StringToDouble(p[6]);
   double tp=(p[7]==""?0.0:StringToDouble(p[7]));
   double zone_low=StringToDouble(p[8]),zone_high=StringToDouble(p[9]);
   datetime valid_until=(datetime)(long)StringToInteger(p[10]);
   string reason=p[11];
   if(TimeTradeServer()>valid_until){ GuardianFinishCommand(id,false,"command expired"); return; }
   if(action=="OPEN")
   {
      bool ok=OpenMarket(slot,side,lot,sl,tp,zone_low,zone_high,valid_until,reason);
      GuardianFinishCommand(id,ok,(ok?"open accepted":"open rejected by local checks")); return;
   }
   if(action=="CLOSE")
   {
      bool ok=CloseLogicalSlot(slot,reason);
      GuardianFinishCommand(id,ok,(ok?"slot closed":"slot close failed")); return;
   }
   if(action=="MODIFY_SL" || action=="MODIFY_STOPS")
   {
      bool ok=ModifyLogicalStops(slot,sl,tp);
      GuardianFinishCommand(id,ok,(ok?"stops modified":"stop modification rejected")); return;
   }
   if(action=="MODIFY_TP")
   {
      int i=SlotIndex(slot);
      if(i<0 || !g_slot_active[i]){ GuardianFinishCommand(id,false,"position not found"); return; }
      bool ok=ModifyLogicalStops(slot,g_slot_sl[i],tp);
      GuardianFinishCommand(id,ok,(ok?"take profit modified":"take profit modification rejected")); return;
   }
   GuardianFinishCommand(id,false,"unsupported action");
}

void GuardianIpcRead()
{
   if(g_ipc_socket==INVALID_HANDLE || !SocketIsConnected(g_ipc_socket)) return;
   uint available=SocketIsReadable(g_ipc_socket);
   while(available>0)
   {
      uint want=(uint)MathMin((long)available,4096);
      uchar data[];
      int got=SocketRead(g_ipc_socket,data,want,1);
      if(got<=0) break;
      g_ipc_buffer+=CharArrayToString(data,0,got,CP_UTF8);
      while(true)
      {
         int pos=StringFind(g_ipc_buffer,"\n");
         if(pos<0) break;
         string line=StringSubstr(g_ipc_buffer,0,pos);
         StringReplace(line,"\r","");
         g_ipc_buffer=StringSubstr(g_ipc_buffer,pos+1);
         if(StringLen(line)>0) GuardianHandleCommand(line);
      }
      available=SocketIsReadable(g_ipc_socket);
   }
}

void GuardianIpcHeartbeat()
{
   long now_ms=(long)GetTickCount64();
   if(now_ms-g_last_heartbeat_ms<1000) return;
   g_last_heartbeat_ms=now_ms;
   MqlTick tick;
   if(!SymbolInfoTick(g_symbol,tick)) return;
   double point=SymbolInfoDouble(g_symbol,SYMBOL_POINT);
   double spread=(point>0?(tick.ask-tick.bid)/point:0.0);
   string text=StringFormat("HB|%I64d|%.10f|%.10f|%.2f|%d|%d|%d|%s|%s\n",
      (long)TimeTradeServer(),tick.bid,tick.ask,spread,GuardianSystemPositionCount(),GuardianSystemOrderCount(),
      (g_weekend_protection?1:0),SlotWire("A"),SlotWire("B"));
   GuardianIpcSend(text);
}

void GuardianIpcPoll()
{
   if(!InpIpcEnabled) return;
   if(!GuardianIpcConnect()) return;
   GuardianIpcRead(); GuardianIpcHeartbeat();
}

#endif
