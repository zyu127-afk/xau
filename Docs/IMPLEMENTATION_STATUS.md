# Implementation status

This file separates repository-complete work from environment-dependent validation.

## Implemented in repository

- Portable single-root layout, relative config, migration/install/start tooling and machine-local secrets.
- Windows Dev/Portable packaging; Portable includes embedded Python and CI verifies imports after unpacking.
- Python Engine runtime, SQLite WAL storage, logging, 90-day raw retention, permanent trades/reviews, daily/weekly/monthly review scheduling.
- MT5 Guardian execution/risk authority using current `_Symbol`, localhost IPC, command idempotency, server-SL enforcement, local weekend protection, persistent logical Position A/B state and restart reconciliation.
- Hedging/Netting logical model, fail-safe Netting server stop, local per-slot TP, dynamic position management, MFE/MAE and exit-reason audit.
- MT5 deployment script that copies all Guardian sources, invokes the selected MetaEditor when available and records verified EX5 status in `Runtime/mt5-binding.json`.
- ATAS/Rithmic DataBridge core: contracts, localhost JSONL publisher, health, current instrument, BBO/trades/DOM, order-flow event detector and fast-event outcome tracking.
- ATAS official-SDK binding project using installed `ATAS.Indicators.dll` / `ATAS.DataFeedsCore.dll`, .NET 8/10 targets, current chart instrument and live trade/BBO/depth/MBO callbacks.
- ATAS deployment script that builds against the user's installed SDK and deploys only after a successful local compile; result is recorded in `Runtime/atas-binding.json`.
- MBO defaults off. MBO data is emitted only after a real ATAS subscription succeeds; unavailable MBO-specific fields remain null/absent.
- GC↔MT5 rolling alignment with instrument-reset, correlation/residual/staleness quality gates and persistent mapping metrics.
- D1/H4/H1/M30/M15/M5/M1 structure, market regime, support/resistance, potential zones, breakout/retest/reversal modes and order-flow aggregation.
- OpenAI-compatible/DeepSeek client with local secret loading, strict JSON schema/type/range validation, asynchronous timeout handling, Snapshot/STALE revalidation and degradation behavior.
- Actual Guardian-telemetry trade registration, restart recovery, MT5 deal-history realized-P&L reconciliation, ambiguity-safe Netting handling, NO TRADE audit and dedupe.
- Chinese Dashboard + MT5 HUD, local authentication token, AI Sleep, pause-new-entry and emergency controls.
- Read-only `Start/本机验收.bat`, support-safe `acceptance-report.json` and redacted diagnostics ZIP.
- CI for Python core/security/protocol/preflight tests, ATAS SDK-independent core build and Windows Dev/Portable delivery packages.

## Requires real local environment

The remaining items cannot be truthfully proved by GitHub CI because they depend on the user's installed terminals, broker/feed entitlement, credentials or live session state:

- MetaEditor compile verification against the installed MT5 build and actual Demo execution/fill/stop-level behavior.
- Hedging and Netting behavior against real broker Demo account modes.
- ATAS SDK-bound project compile/load against the installed ATAS build and Rithmic Paper live stream.
- Verification of whether that Rithmic Paper entitlement exposes MBO; default remains non-MBO until proven.
- Current GC contract rollover/instrument-change behavior using live ATAS data.
- Real DeepSeek/OpenAI-compatible endpoint call with the user's local key/Base URL/Model.
- MT5/ATAS/Python/AI disconnect/reconnect fault injection, server-SL survival and Friday session/weekend flatten behavior.
- End-to-end Windows migration/path-change test on the actual target installation.

These environment-dependent items must not be marked PASS until observed on the user's machine. Repository completion is not equivalent to real-money release approval; the final V1 release gate remains MT5 Demo + ATAS/Rithmic Paper acceptance.
