# Implementation status

This file separates repository-complete work from environment-dependent validation.

## Implemented in repository
- Portable folder layout and config templates
- Python Engine runtime, SQLite WAL database, logging, retention, review scaffolding
- MT5 Guardian execution/risk authority with localhost IPC and weekend protection
- AI OpenAI-compatible client, schema validation, snapshot/stale checks, failure degradation
- Multi-timeframe market structure, zones, breakout/mode logic, order-flow aggregation
- GC↔MT5 rolling alignment core
- Position A/B logical model and deterministic dynamic position management
- Chinese dashboard service and startup/tooling scaffolding
- CI for Python core and ATAS/.NET bridge core

## Requires real local environment
- MetaEditor compile of the Guardian against the installed MT5 build
- Broker demo execution validation (fills, stop-levels, netting/hedging semantics)
- ATAS SDK binding and Rithmic Paper live stream validation
- Verification of whether the user's Rithmic Paper entitlement includes MBO
- GC contract rollover/instrument-change live validation
- End-to-end Windows startup, disconnect/reconnect, weekend-session and migration tests

These environment-dependent items must not be marked passed until observed on the user's machine.
