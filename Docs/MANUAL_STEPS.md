# Manual integration steps

Only tasks that require the user's local MT5/ATAS/Rithmic/Windows environment belong here.

## MT5
1. Compile `MT5/GoldTradingGuardian.mq5` in MetaEditor.
2. Attach the EA to the broker gold chart that will actually be traded. The EA uses `_Symbol`.
3. Enable Algo Trading.
4. Allow localhost `127.0.0.1` / the configured Engine port in the MT5 Expert Advisors network/socket permissions.
5. Use a demo account for acceptance testing.
6. Confirm a real broker/server-side SL is visible on every system position.

## ATAS / Rithmic
1. Open ATAS and connect the Rithmic Paper account.
2. Open the active GC futures contract chart.
3. Build/install the project under `ATAS/` against the actual ATAS SDK assemblies on the machine.
4. Start the DataBridge on localhost port 17831.
5. If MBO is not exposed by the account, keep `require_mbo: false`; MBO-only fields remain null and are never fabricated.

## AI
1. Copy `Config/secrets.local.example` to `Config/secrets.local`.
2. Put the real API key only in that local file.
3. Set `ai.base_url` and `ai.model` in `Config/config.yaml`.

## Final acceptance
Run `Start/启动系统.bat`, then execute `Docs/ACCEPTANCE.md` on demo/paper only. CI success does not prove broker/ATAS integration; those items require the actual local terminals and feeds.
