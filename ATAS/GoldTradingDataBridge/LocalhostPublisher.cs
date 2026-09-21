using System.Net;
using System.Net.Sockets;
using System.Text.Json;
using System.Threading.Channels;

namespace GoldTradingDataBridge;

public sealed class LocalhostPublisher : IAsyncDisposable
{
    private readonly TcpListener _listener;
    private readonly Channel<BridgeMessage> _messages = Channel.CreateBounded<BridgeMessage>(
        new BoundedChannelOptions(10000) { FullMode = BoundedChannelFullMode.DropOldest });
    private readonly CancellationTokenSource _cts = new();
    private readonly List<TcpClient> _clients = new();

    public LocalhostPublisher(int port)
    {
        _listener = new TcpListener(IPAddress.Loopback, port);
    }

    public void Publish(BridgeMessage message) => _messages.Writer.TryWrite(message);

    public async Task RunAsync()
    {
        _listener.Start();
        var accept = AcceptLoopAsync(_cts.Token);
        var broadcast = BroadcastLoopAsync(_cts.Token);
        await Task.WhenAll(accept, broadcast);
    }

    private async Task AcceptLoopAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            var client = await _listener.AcceptTcpClientAsync(ct);
            lock (_clients) _clients.Add(client);
        }
    }

    private async Task BroadcastLoopAsync(CancellationToken ct)
    {
        await foreach (var message in _messages.Reader.ReadAllAsync(ct))
        {
            var bytes = JsonSerializer.SerializeToUtf8Bytes(message);
            byte[] line = new byte[bytes.Length + 1];
            Buffer.BlockCopy(bytes, 0, line, 0, bytes.Length);
            line[^1] = (byte)'\n';
            List<TcpClient> clients;
            lock (_clients) clients = _clients.ToList();
            foreach (var client in clients)
            {
                try { await client.GetStream().WriteAsync(line, ct); }
                catch
                {
                    lock (_clients) _clients.Remove(client);
                    client.Dispose();
                }
            }
        }
    }

    public async ValueTask DisposeAsync()
    {
        _cts.Cancel();
        _listener.Stop();
        List<TcpClient> clients;
        lock (_clients) clients = _clients.ToList();
        foreach (var client in clients) client.Dispose();
        _cts.Dispose();
        await Task.CompletedTask;
    }
}
