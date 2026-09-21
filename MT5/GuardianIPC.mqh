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
   for(int i=0;i<PositionsTotal();i++)
   {
      ulong ticket=0;
      if(IsSystemPositionByIndex(i,ticket)) n++;
   }
   return n;
}

int GuardianSystemOrderCount()
{
   int n=0;
   for(int i=0;i<OrdersTotal();i++)
   {
      ulong ticket=0;
      if(IsSystemOrderByIndex(i,ticket)) n++;
   }
   return n;
}

bool GuardianIpcSend(const string text)
{
   if(g_ipc_socket==INVALID_HANDLE || !SocketIsConnected(g_ipc_socket) || !SocketIsWritable(g_ipc_socket)) return false;
   uchar data[];
   int copied=StringToCharArray(text,data,0,StringLen(text),CP_UTF8);
   if(copied<=0) return false;
   int sent=SocketSend(g_ipc_socket,data,(uint)copied);
   return sent==copied;
}

void GuardianIpcClose()
{
   if(g_ipc_socket!=INVALID_HANDLE)
   {
      SocketClose(g_ipc_socket);
      g_ipc_socket=INVALID_HANDLE;
   }
   g_ipc_buffer="";
}

bool GuardianIpcConnect()
{
   if(!InpIpcEnabled) return false;
   if(g_ipc_socket!=INVALID_HANDLE && SocketIsConnected(g_ipc_socket)) return true;
   GuardianIpcClose();
   ResetLastError();
   g_ipc_socket=SocketCreate();
   if(g_ipc_socket==INVALID_HANDLE)
   {
      PrintFormat("GUARDIAN IPC SocketCreate failed error=%d",GetLastError());
      return false;
   }
   if(!SocketConnect(g_ipc_socket,InpEngineHost,InpEnginePort,InpConnectTimeoutMs))
   {
      int err=GetLastError();
      PrintFormat("GUARDIAN IPC connect failed %s:%u error=%d. Ensure localhost is allowed in MT5 Expert Advisors settings.",InpEngineHost,InpEnginePort,err);
      GuardianIpcClose();
      return false;
   }
   SocketTimeouts(g_ipc_socket,50,50);
   string hello=StringFormat("HELLO|%I64d|%s|%s|0.10\n",AccountInfoInteger(ACCOUNT_LOGIN),g_symbol,GuardianAccountMode());
   GuardianIpcSend(hello);
   PrintFormat("GUARDIAN IPC connected to %s:%u",InpEngineHost,InpEnginePort);
   return true;
}

void GuardianIpcAck(const string command_id,const bool ok,const string reason)
{
   string clean=reason;
   StringReplace(clean,"|","/");
   StringReplace(clean,"\r"," ");
   StringReplace(clean,"\n"," ");
   GuardianIpcSend(StringFormat("ACK|%s|%s|%s\n",command_id,(ok ? "OK" : "REJECT"),clean));
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

void GuardianHandleCommand(const string line)
{
   string p[];
   ushort sep=(ushort)StringGetCharacter("|",0);
   int n=StringSplit(line,sep,p);
   if(n<3 || p[0]!="GTS1") return;
   string id=p[1];
   string action=p[2];
   if(action=="CLOSE_ALL")
   {
      CancelAllSystemOrders();
      CloseAllSystemPositions();
      GuardianIpcAck(id,true,"closed all system exposure");
      return;
   }
   if(n<12)
   {
      GuardianIpcAck(id,false,"malformed command");
      return;
   }
   string slot=p[3],side=p[4];
   double lot=StringToDouble(p[5]);
   double sl=StringToDouble(p[6]);
   double tp=(p[7]=="" ? 0.0 : StringToDouble(p[7]));
   double zone_low=StringToDouble(p[8]);
   double zone_high=StringToDouble(p[9]);
   datetime valid_until=(datetime)(long)StringToInteger(p[10]);
   string reason=p[11];
   if(action=="OPEN")
   {
      bool ok=OpenMarket(slot,side,lot,sl,tp,zone_low,zone_high,valid_until,reason);
      GuardianIpcAck(id,ok,(ok ? "open accepted" : "open rejected by local checks"));
      return;
   }
   if(action=="MODIFY_SL")
   {
      if(TimeTradeServer()>valid_until){ GuardianIpcAck(id,false,"command expired"); return; }
      ulong ticket=GuardianFindPositionTicket(slot);
      if(ticket==0){ GuardianIpcAck(id,false,"position not found"); return; }
      bool ok=ModifyPositionStops(ticket,sl,tp);
      GuardianIpcAck(id,ok,(ok ? "stops modified" : "stop modification rejected"));
      return;
   }
   GuardianIpcAck(id,false,"unsupported action");
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
   double spread=(point>0 ? (tick.ask-tick.bid)/point : 0.0);
   GuardianIpcSend(StringFormat("HB|%I64d|%.10f|%.10f|%.2f|%d|%d|%d\n",
      (long)TimeTradeServer(),tick.bid,tick.ask,spread,GuardianSystemPositionCount(),GuardianSystemOrderCount(),(g_weekend_protection ? 1 : 0)));
}

void GuardianIpcPoll()
{
   if(!InpIpcEnabled) return;
   if(!GuardianIpcConnect()) return;
   GuardianIpcRead();
   GuardianIpcHeartbeat();
}

#endif
