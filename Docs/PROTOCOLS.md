# Local IPC protocols

All core local communications bind to `127.0.0.1`/loopback. They are not public network APIs.

## Python → MT5 Guardian

TCP port default: `17832`.

Command line:

`GTS1|command_id|action|slot|side|lot|sl|tp|zone_low|zone_high|valid_until_unix|reason`

Guardian acknowledgement:

`ACK|command_id|OK|reason`

or

`ACK|command_id|REJECT|reason`

EA hello:

`HELLO|account|symbol|account_mode|ea_version`

EA heartbeat:

`HB|unix_time|bid|ask|spread_points|positions|orders|weekend_protection`

AI output is never sent directly to this channel. Python first performs Snapshot/STALE and decision arbitration; Guardian then independently repeats local execution checks.

## ATAS → Python

TCP JSON Lines on port `17831`. Each object carries `type`, `ts_utc`, `instrument`, `mbo_available`, and `payload`.

MBO-dependent fields must remain absent/null when the connected data entitlement does not provide MBO. The bridge must never invent queue/order identifiers.
