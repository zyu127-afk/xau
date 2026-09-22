using System.Net;
using System.Net.Sockets;
using System.Text.Json;
using GoldTradingDataBridge;

static int ReservePort()
{
    var listener = new TcpListener(IPAddress.Loopback, 0);
    listener.Start();
    var port = ((IPEndPoint)listener.LocalEndpoint).Port;
    listener.Stop();
    return port;
}

var port = ReservePort();
var source = new SmokeSource("GC.TEST");
await using var host = new BridgeHost(source, port);
host.Start();

using var client = new TcpClient();
using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(8));
await client.ConnectAsync(IPAddress.Loopback, port, timeout.Token);
using var reader = new StreamReader(client.GetStream());

var sawHello = false;
var sawHeartbeat = false;
for (var i = 0; i < 6 && !sawHeartbeat; i++)
{
    var line = await reader.ReadLineAsync(timeout.Token);
    if (string.IsNullOrWhiteSpace(line))
        continue;

    using var doc = JsonDocument.Parse(line);
    var root = doc.RootElement;
    var type = root.GetProperty("type").GetString();
    var instrument = root.GetProperty("instrument").GetString() ?? string.Empty;

    if (type == "transport_hello")
        sawHello = true;
    if (type == "heartbeat" && instrument == "GC.TEST")
        sawHeartbeat = true;
}

if (!sawHello)
    throw new InvalidOperationException("ATAS bridge did not emit immediate transport_hello after TCP connect.");
if (!sawHeartbeat)
    throw new InvalidOperationException("ATAS bridge did not emit periodic heartbeat with current instrument.");

Console.WriteLine("ATAS TCP SMOKE OK");

sealed class SmokeSource : IAtasMarketSource
{
    public SmokeSource(string instrument) => CurrentInstrument = instrument;
    public string CurrentInstrument { get; }
    public bool MboAvailable => false;
    public event Action<BridgeMessage>? Message;
    public void Start()
    {
        Message?.Invoke(new BridgeMessage(
            "instrument_changed",
            DateTimeOffset.UtcNow,
            CurrentInstrument,
            false,
            new { instrument = CurrentInstrument, mbo_available = false }));
    }
    public void Stop() { }
}
