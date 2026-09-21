namespace GoldTradingDataBridge;

/// <summary>
/// Wires an ATAS market source to the loopback publisher and emits health heartbeats.
/// The ATAS-specific plugin/indicator only needs to construct this host with its adapter.
/// </summary>
public sealed class BridgeHost : IAsyncDisposable
{
    private readonly IAtasMarketSource _source;
    private readonly LocalhostPublisher _publisher;
    private readonly CancellationTokenSource _cts = new();
    private Task? _publisherTask;
    private Task? _heartbeatTask;

    public BridgeHost(IAtasMarketSource source, int port = 17831)
    {
        _source = source;
        _publisher = new LocalhostPublisher(port);
        _source.Message += OnMessage;
    }

    public void Start()
    {
        _publisherTask = _publisher.RunAsync();
        _source.Start();
        _heartbeatTask = HeartbeatLoopAsync(_cts.Token);
    }

    private void OnMessage(BridgeMessage message) => _publisher.Publish(message);

    private async Task HeartbeatLoopAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            _publisher.Publish(new BridgeMessage(
                "heartbeat", DateTimeOffset.UtcNow, _source.CurrentInstrument, _source.MboAvailable,
                new { health = string.IsNullOrWhiteSpace(_source.CurrentInstrument) ? "WARMING_UP" : "HEALTHY" }));
            try { await Task.Delay(TimeSpan.FromSeconds(1), ct); }
            catch (OperationCanceledException) when (ct.IsCancellationRequested) { break; }
        }
    }

    public async ValueTask DisposeAsync()
    {
        _cts.Cancel();
        _source.Stop();
        _source.Message -= OnMessage;
        if (_heartbeatTask is not null)
        {
            try { await _heartbeatTask; } catch (OperationCanceledException) { }
        }
        await _publisher.DisposeAsync();
        _cts.Dispose();
    }
}
