# MT5 localhost network setup

Guardian IPC uses MQL5 socket functions and connects only to the local Python engine. MetaTrader requires network addresses used by socket functions to be permitted in the terminal settings; add the local engine address (normally `127.0.0.1`) in the Expert Advisors allowed-address configuration before enabling IPC.

The Guardian's hard protections do not depend on Python being online: the broker/server SL and Friday session protection stay local to MT5.
