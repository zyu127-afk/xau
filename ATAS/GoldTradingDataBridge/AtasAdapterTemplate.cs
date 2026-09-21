namespace GoldTradingDataBridge;

/// <summary>
/// Vendor boundary for the ATAS SDK. Keep every ATAS-specific reference in this file/project layer.
/// The final local binding reads the active chart instrument instead of hard-coding a GC month.
/// Normalized callbacks below are already complete; only the installed ATAS SDK event wiring remains machine-specific.
/// </summary>
public sealed class AtasAdapterTemplate : IAtasMarketSource
{
    private readonly OrderFlowDetector _detector = new();
    public string CurrentInstrument { get; private set; } = string.Empty;
    public bool MboAvailable { get; private set; }
    public event Action<BridgeMessage>? Message;

    public void Start()
    {
        // MACHINE-SPECIFIC: bind installed ATAS SDK callbacks to OnInstrumentChanged/OnBestBidAsk/OnTrade/OnDepth/etc.
        // Never hard-code GC month contracts. The active chart contract is the source of truth.
    }

    public void Stop() { }

    public void OnInstrumentChanged(string instrument, bool mboAvailable)
    {
        if (string.IsNullOrWhiteSpace(instrument)) return;
        CurrentInstrument = instrument;
        MboAvailable = mboAvailable;
        Message?.Invoke(new BridgeMessage("instrument_changed", DateTimeOffset.UtcNow, instrument, mboAvailable,
            new { instrument, mbo_available = mboAvailable }));
    }

    public void OnBestBidAsk(BestBidAsk bbo)
    {
        Emit("bbo", new { bid = bbo.Bid, ask = bbo.Ask, last = bbo.Last });
        foreach (var signal in _detector.OnBestBidAsk(bbo)) EmitSignal(signal);
    }

    public void OnTrade(TradeEvent trade)
    {
        Emit("trade", new { price = trade.Price, volume = trade.Volume, aggressor_side = trade.AggressorSide, cvd = _detector.Cvd });
        foreach (var signal in _detector.OnTrade(trade)) EmitSignal(signal);
    }

    public void OnDepth(IReadOnlyList<DomLevel> levels)
    {
        // OrderCount is nullable. When Rithmic Paper/ATAS does not expose MBO, it stays null by design.
        Emit("dom", new { levels = levels.Select(x => new { price = x.Price, bid_size = x.BidSize, ask_size = x.AskSize, order_count = MboAvailable ? x.OrderCount : null }).ToArray() });
        foreach (var signal in _detector.OnDepth(levels)) EmitSignal(signal);
    }

    public void OnDelta(double delta, double cvd)
        => Emit("delta", new { delta, cvd });

    public void OnFootprint(double price, double bidVolume, double askVolume)
    {
        var total = bidVolume + askVolume;
        var imbalance = total <= 0 ? 0.0 : (askVolume - bidVolume) / total;
        Emit("footprint", new { price, bid_volume = bidVolume, ask_volume = askVolume, imbalance });
    }

    public void OnAbsorptionCandidate(double price, double aggressiveVolume, double priceProgress, string aggressorSide)
    {
        var signal = _detector.DetectAbsorption(price, aggressiveVolume, priceProgress, aggressorSide);
        if (signal is not null) EmitSignal(signal);
    }

    public void OnExhaustionCandidate(double price, double previousAggressiveVolume, double currentAggressiveVolume, string side)
    {
        var signal = _detector.DetectExhaustion(price, previousAggressiveVolume, currentAggressiveVolume, side);
        if (signal is not null) EmitSignal(signal);
    }

    public void OnIceberg(double price, double strength, string side, long? replenishmentCount)
    {
        // replenishmentCount is MBO-specific and must remain null when MBO is unavailable.
        Emit("iceberg", new { price, strength, side, replenishment_count = MboAvailable ? replenishmentCount : null });
    }

    public void Emit(string type, object payload)
        => Message?.Invoke(new BridgeMessage(type, DateTimeOffset.UtcNow, CurrentInstrument, MboAvailable, payload));

    private void EmitSignal(OrderFlowSignal signal)
        => Emit(signal.EventType, new { event_type = signal.EventType, price = signal.Price, strength = signal.Strength, detail = signal.Detail });
}
