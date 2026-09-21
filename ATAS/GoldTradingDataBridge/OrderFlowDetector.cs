using System.Collections.Concurrent;

namespace GoldTradingDataBridge;

/// <summary>
/// SDK-independent order-flow detector. ATAS callbacks feed normalized trades/depth into this class.
/// It intentionally does not invent MBO fields when the feed only provides market-by-price depth.
/// </summary>
public sealed class OrderFlowDetector
{
    private readonly Queue<TradeEvent> _trades = new();
    private readonly int _maxTrades;
    private readonly double _largeTradeVolume;
    private readonly double _sweepVolume;
    private readonly int _sweepMinLevels;
    private readonly object _gate = new();
    private double _cvd;
    private double _lastBid;
    private double _lastAsk;
    private IReadOnlyList<DomLevel> _lastBook = Array.Empty<DomLevel>();

    public OrderFlowDetector(int maxTrades = 2000, double largeTradeVolume = 50, double sweepVolume = 100, int sweepMinLevels = 3)
    {
        _maxTrades = Math.Max(100, maxTrades);
        _largeTradeVolume = Math.Max(0, largeTradeVolume);
        _sweepVolume = Math.Max(0, sweepVolume);
        _sweepMinLevels = Math.Max(2, sweepMinLevels);
    }

    public double Cvd { get { lock (_gate) return _cvd; } }

    public IReadOnlyList<OrderFlowSignal> OnTrade(TradeEvent trade)
    {
        var output = new List<OrderFlowSignal>();
        lock (_gate)
        {
            _trades.Enqueue(trade);
            while (_trades.Count > _maxTrades) _trades.Dequeue();
            if (trade.AggressorSide.Equals("BUY", StringComparison.OrdinalIgnoreCase)) _cvd += trade.Volume;
            else if (trade.AggressorSide.Equals("SELL", StringComparison.OrdinalIgnoreCase)) _cvd -= trade.Volume;

            if (trade.Volume >= _largeTradeVolume)
                output.Add(new("large_trade", trade.Price, Strength(trade.Volume, _largeTradeVolume), trade.AggressorSide.ToUpperInvariant()));

            var side = trade.AggressorSide.ToUpperInvariant();
            var recent = _trades.Reverse().Take(12).Where(x => x.AggressorSide.Equals(side, StringComparison.OrdinalIgnoreCase)).ToArray();
            if (recent.Length >= _sweepMinLevels)
            {
                var distinctPrices = recent.Select(x => x.Price).Distinct().Count();
                var volume = recent.Sum(x => x.Volume);
                if (distinctPrices >= _sweepMinLevels && volume >= _sweepVolume)
                    output.Add(new("sweep", trade.Price, Strength(volume, _sweepVolume), side == "BUY" ? "up" : "down"));
            }
        }
        return output;
    }

    public IReadOnlyList<OrderFlowSignal> OnBestBidAsk(BestBidAsk bbo)
    {
        lock (_gate)
        {
            _lastBid = bbo.Bid;
            _lastAsk = bbo.Ask;
        }
        return Array.Empty<OrderFlowSignal>();
    }

    public IReadOnlyList<OrderFlowSignal> OnDepth(IReadOnlyList<DomLevel> levels)
    {
        var output = new List<OrderFlowSignal>();
        lock (_gate)
        {
            if (_lastBook.Count > 0 && levels.Count > 0)
            {
                var previous = _lastBook.ToDictionary(x => x.Price);
                foreach (var level in levels)
                {
                    if (!previous.TryGetValue(level.Price, out var before)) continue;
                    var bidDelta = level.BidSize - before.BidSize;
                    var askDelta = level.AskSize - before.AskSize;
                    var scale = Math.Max(1.0, Math.Max(Math.Abs(before.BidSize), Math.Abs(before.AskSize)));
                    if (bidDelta > scale * 0.5) output.Add(new("liquidity_stack", level.Price, Math.Min(3, bidDelta / scale), "bid_stack"));
                    if (askDelta > scale * 0.5) output.Add(new("liquidity_stack", level.Price, Math.Min(3, askDelta / scale), "ask_stack"));
                    if (bidDelta < -scale * 0.5) output.Add(new("liquidity_pull", level.Price, Math.Min(3, -bidDelta / scale), "bid_pull"));
                    if (askDelta < -scale * 0.5) output.Add(new("liquidity_pull", level.Price, Math.Min(3, -askDelta / scale), "ask_pull"));
                }
            }
            _lastBook = levels.ToArray();
        }
        return output;
    }

    public OrderFlowSignal? DetectAbsorption(double price, double aggressiveVolume, double priceProgress, string aggressorSide)
    {
        if (aggressiveVolume <= 0) return null;
        var normalizedProgress = Math.Abs(priceProgress) / Math.Max(1.0, aggressiveVolume);
        if (normalizedProgress > 0.02) return null;
        var side = aggressorSide.ToUpperInvariant();
        return new("absorption", price, Math.Min(3, aggressiveVolume / Math.Max(1.0, _largeTradeVolume)),
            side == "SELL" ? "sell_absorption_lower" : "buy_absorption_upper");
    }

    public OrderFlowSignal? DetectExhaustion(double price, double previousAggressiveVolume, double currentAggressiveVolume, string side)
    {
        if (previousAggressiveVolume <= 0 || currentAggressiveVolume < 0) return null;
        var ratio = currentAggressiveVolume / previousAggressiveVolume;
        if (ratio > 0.35) return null;
        var normalized = side.ToUpperInvariant();
        return new("exhaustion", price, Math.Min(3, (1.0 - ratio) * 2.0), normalized == "SELL" ? "seller_exhaustion" : "buyer_exhaustion");
    }

    private static double Strength(double value, double threshold)
        => threshold <= 0 ? 1.0 : Math.Clamp(value / threshold, 0.1, 3.0);
}
