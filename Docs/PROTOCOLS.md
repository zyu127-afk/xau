# Local IPC protocols

All core local communications bind to `127.0.0.1`/loopback. They are not public network APIs.

## Python → MT5 Guardian

TCP port default: `17832`.

### Command

`GTS1|command_id|action|slot|side|lot|sl|tp|zone_low|zone_high|valid_until_unix|reason`

Supported actions in the current Guardian are `OPEN`, `CLOSE`, `MODIFY_SL`, `MODIFY_TP`, `MODIFY_STOPS`, `CLOSE_ALL` and `CANCEL_ALL`. `CLOSE_ALL` and `CANCEL_ALL` are emergency/global actions and do not require the remaining position fields.

Guardian acknowledgement:

`ACK|command_id|OK|reason`

or

`ACK|command_id|REJECT|reason`

Command IDs are persisted by the Guardian so retries are idempotent. `reason` is sanitized so it cannot inject protocol separators or new lines.

### Guardian hello

`HELLO|account|symbol|account_mode|ea_version`

The account value is used only inside the local runtime and must not be copied into support diagnostics.

### Guardian heartbeat

Current format contains base telemetry followed by two 10-field logical-slot records:

`HB|unix_time|bid|ask|spread_points|positions|orders|weekend_protection|<slot_A_10_fields>|<slot_B_10_fields>`

Each slot record is:

`active|side|lot|entry_price|original_sl|current_sl|tp|entry_time|mfe|mae`

Therefore the current heartbeat has 28 pipe-delimited fields in total. Python retains parsers for older heartbeat shapes only for migration/restart compatibility.

### Python HUD status → Guardian

`STATUS|regime|bias|support|resistance|long_zone|short_zone|orderflow|ai_state|api_latency|system_state`

The Guardian treats this as display-only data. If Python stops updating it, the MT5 HUD switches to `PYTHON OFFLINE / GUARDIAN LOCAL`; the Guardian continues local position protection independently.

AI output is never sent directly to the execution channel. Python first performs schema validation, Snapshot/STALE validation and decision arbitration; Guardian then independently repeats final local execution/risk checks.

## ATAS → Python

TCP JSON Lines on port `17831`. Every normalized object carries:

- `type`
- `ts_utc`
- `instrument`
- `mbo_available`
- `payload`

The active ATAS chart contract is the source of truth. `instrument_changed` resets order-flow state and forces the GC↔MT5 mapping to warm up again.

MBO-dependent fields must remain absent/null when the connected Rithmic/ATAS entitlement does not provide MBO. The bridge must never invent queue IDs, order IDs, replenishment counts or similar order-level fields.
