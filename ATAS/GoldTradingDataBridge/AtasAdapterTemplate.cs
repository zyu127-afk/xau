namespace GoldTradingDataBridge;

/// <summary>
/// Vendor boundary for the ATAS SDK. Keep every ATAS-specific reference in this file/project layer.
/// The production adapter must bind CurrentInstrument to the instrument loaded on the active ATAS chart,
/// emit Trades/Tick/Bid/Ask/DOM/Cumulative Trades/Delta/CVD/Footprint/Imbalance/Volume and derived
/// large-trade, sweep, absorption, exhaustion, liquidity pull/stack, iceberg and anomaly events.
/// It must publish null/absence for MBO-only fields when the connected Rithmic entitlement does not expose MBO.
/// </summary>
public sealed class AtasAdapterTemplate : IAtasMarketSource
{
    public string CurrentInstrument { get; private set; } = string.Empty;
    public bool MboAvailable { get; private set; }
    public event Action<BridgeMessage>? Message;

    public void Start()
    {
        // Bind ATAS SDK callbacks here after adding the SDK references from the installed ATAS instance.
        // Do not hard-code GC month contracts: read the active chart instrument on every change.
    }

    public void Stop() { }

    public void OnInstrumentChanged(string instrument, bool mboAvailable)
    {
        CurrentInstrument = instrument;
        MboAvailable = mboAvailable;
        Message?.Invoke(new BridgeMessage("instrument_changed", DateTimeOffset.UtcNow, instrument, mboAvailable,
            new { instrument }));
    }

    public void Emit(string type, object payload)
    {
        Message?.Invoke(new BridgeMessage(type, DateTimeOffset.UtcNow, CurrentInstrument, MboAvailable, payload));
    }
}
