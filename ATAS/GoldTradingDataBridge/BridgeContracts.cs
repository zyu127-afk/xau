using System.Text.Json.Serialization;

namespace GoldTradingDataBridge;

public sealed record BridgeMessage(
    [property: JsonPropertyName("type")] string Type,
    [property: JsonPropertyName("ts_utc")] DateTimeOffset TimestampUtc,
    [property: JsonPropertyName("instrument")] string Instrument,
    [property: JsonPropertyName("mbo_available")] bool MboAvailable,
    [property: JsonPropertyName("payload")] object Payload);

public sealed record BestBidAsk(double Bid, double Ask, double Last);
public sealed record TradeEvent(double Price, double Volume, string AggressorSide);
public sealed record DomLevel(double Price, double BidSize, double AskSize, int? OrderCount);
public sealed record OrderFlowSignal(string EventType, double Price, double Strength, string Detail);

public interface IAtasMarketSource
{
    string CurrentInstrument { get; }
    bool MboAvailable { get; }
    event Action<BridgeMessage>? Message;
    void Start();
    void Stop();
}
