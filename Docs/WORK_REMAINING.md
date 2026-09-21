# Work remaining

As of the current `main`, no known mandatory V1 software component is still intentionally unimplemented in the repository. Core Python, MT5 Guardian, ATAS bridge/core + SDK binding project, AI client, Dashboard, persistence, packaging, installer, diagnostics and CI coverage are present.

What remains is evidence that cannot be manufactured by GitHub CI because it depends on the user's actual Windows terminals, broker/feed permissions, credentials and trading session state.

## Machine-only acceptance still required

- Compile the MT5 Guardian with the user's installed MetaEditor and confirm the EX5 is loaded on the intended Demo chart.
- Verify actual Demo OPEN/CLOSE/MODIFY/CANCEL behavior, broker stop-level rules and real server-side SL persistence.
- Verify both Hedging and Netting account semantics if both modes are available.
- Compile/load `GoldTradingDataBridge.ATAS` against the installed ATAS assemblies and confirm the current GC chart emits real data on `127.0.0.1:17831`.
- Confirm the Rithmic Paper entitlement's actual MBO capability. Keep MBO disabled unless the official ATAS subscription succeeds.
- Observe a real ATAS contract/instrument switch and confirm GC↔MT5 mapping reset/re-warm.
- Configure the user's DeepSeek/OpenAI-compatible endpoint locally and verify success, timeout and STALE rejection without exposing the key.
- Perform MT5/ATAS/Rithmic/AI/Python disconnect and restart fault injection while positions are protected.
- Verify Friday session-based weekend flatten on the actual broker symbol/session schedule.
- Copy the whole root to a different Windows path and repeat install/preflight/start to prove portability.
- Run long enough to audit Dashboard/HUD, SQLite, logs, MFE/MAE, NO TRADE and review records against real Paper/Demo events.

## Evidence collection

Run `Start/本机验收.bat` first. It is read-only and does not submit orders. It writes `Runtime/acceptance-report.json` with sanitized binding/dependency/port state. MT5 and ATAS deployment scripts separately write `Runtime/mt5-binding.json` and `Runtime/atas-binding.json`; those machine-local files are gitignored.

A repository CI pass is necessary but not sufficient for real-account release. V1 remains `paper-integration-pending` until the LOCAL items in `Docs/ACCEPTANCE.md` are observed and recorded on the actual MT5 Demo + ATAS/Rithmic Paper environment.
