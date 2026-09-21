using ATAS.DataFeedsCore;
using ATAS.Indicators;
using GoldTradingDataBridge;

namespace GoldTradingDataBridge.ATAS;

/// <summary>
/// ATAS chart indicator that forwards the active chart's live market data to the
/// SDK-independent GoldTradingDataBridge core. It never submits orders.
/// </summary>
public sealed class GoldTradingBridgeIndicator : Indicator
{
    private readonly AtasAdapterTemplate _adapter = new();
    private BridgeHost? _host;
    private string _instrument = string.Empty;
    private decimal _bid;
    private decimal _ask;
    private decimal _last;
    private bool _mboActive;

    public int BridgePort { get; set; } = 17831;

    /// <summary>
    /// Default is false. Enable only when the connected Rithmic/ATAS entitlement
    /// actually provides Market By Order. Failed subscription stays non-MBO.
    /// </summary>
    public bool EnableMbo { get; set; } = false;

    protected override async void OnInitialize()
    {
        base.OnInitialize();
        RefreshInstrument(false);
        _host = new BridgeHost(_adapter, BridgePort);
        _host.Start();

        if (!EnableMbo)
            return;

        try
        {
            // Official ATAS API: the task completes when the MBO subscription is active.
            await SubscribeMarketByOrderData();
            _mboActive = true;
            RefreshInstrument(true);
            EmitMboSnapshot(MarketByOrders);
        }
        catch
        {
            // Lack of MBO entitlement must degrade capability, never fabricate MBO data.
            _mboActive = false;
            RefreshInstrument(true);
        }
    }

    protected override void OnCalculate(int bar, decimal value)
    {
        // OnCalculate also runs on the live bar. Re-reading InstrumentInfo makes chart
        // contract changes visible without hard-coding any GC month.
        RefreshInstrument(false);
    }

    protected override void OnNewTrade(MarketDataArg trade)
    {
        _last = trade.Price;
        _adapter.OnTrade(new TradeEvent(
            (double)trade.Price,
            (double)trade.Volume,
            trade.Direction.ToString().ToUpperInvariant()));
        EmitBboIfReady();
    }

    protected override void OnBestBidAskChanged(MarketDataArg depth)
    {
        if (depth.IsBid)
            _bid = depth.Price;
        if (depth.IsAsk)
            _ask = depth.Price;
        EmitBboIfReady();
    }

    protected override void MarketDepthsChanged(IEnumerable<MarketDataArg> depths)
    {
        var levels = new List<DomLevel>();
        foreach (var depth in depths)
        {
            var bidSize = depth.IsBid ? (double)depth.Volume : 0.0;
            var askSize = depth.IsAsk ? (double)depth.Volume : 0.0;
            levels.Add(new DomLevel((double)depth.Price, bidSize, askSize, null));
        }
        if (levels.Count > 0)
            _adapter.OnDepth(levels);
    }

    protected override void OnMarketByOrdersChanged(IEnumerable<MarketByOrder> values)
    {
        if (!_mboActive)
            return;
        EmitMboSnapshot(values);
    }

    protected override void OnDispose()
    {
        var host = _host;
        _host = null;
        if (host is not null)
        {
            try { host.DisposeAsync().AsTask().GetAwaiter().GetResult(); }
            catch { /* ATAS shutdown must not be blocked by bridge cleanup errors. */ }
        }
        base.OnDispose();
    }

    private void RefreshInstrument(bool force)
    {
        var current = InstrumentInfo?.Instrument ?? string.Empty;
        if (!force && string.Equals(current, _instrument, StringComparison.Ordinal))
            return;
        _instrument = current;
        if (!string.IsNullOrWhiteSpace(current))
            _adapter.OnInstrumentChanged(current, _mboActive);
    }

    private void EmitBboIfReady()
    {
        if (_bid <= 0 || _ask <= 0)
            return;
        _adapter.OnBestBidAsk(new BestBidAsk((double)_bid, (double)_ask, (double)_last));
    }

    private void EmitMboSnapshot(IEnumerable<MarketByOrder> values)
    {
        if (!_mboActive)
            return;
        foreach (var item in values)
        {
            _adapter.Emit("mbo", new
            {
                event_type = item.Type.ToString(),
                side = item.Side.ToString(),
                price = (double)item.Price,
                volume = (double)item.Volume,
                priority = item.Priority,
                exchange_order_id = item.ExchangeOrderId,
                time = item.Time,
            });
        }
    }
}
