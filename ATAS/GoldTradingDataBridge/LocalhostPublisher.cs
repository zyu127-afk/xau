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
        await Task.WhenAll(accept, broadcast).ConfigureAwait(false);
    }

    private async Task AcceptLoopAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            TcpClient client;
            try
            {
                client = await _listener.AcceptTcpClientAsync(ct).ConfigureAwait(false);
            }
            catch (OperationCanceledException) when (ct.IsCancellationRequested)
            {
                break;
            }
            catch (ObjectDisposedException) when (ct.IsCancellationRequested)
            {
                break;
            }

            client.NoDelay = true;
            lock (_clients) _clients.Add(client);

            // Prove the transport is alive immediately after connect. Do not wait for
            // market callbacks or the next periodic heartbeat before sending data.
            var hello = new BridgeMessage(
                "transport_hello",
                DateTimeOffset.UtcNow,
                string.Empty,
                false,
                new { health = "WARMING_UP" });
            if (!await TryWriteAsync(client, hello, ct).ConfigureAwait(false))
                RemoveClient(client);
        }
    }

    private async Task BroadcastLoopAsync(CancellationToken ct)
    {
        try
        {
            await foreach (var message in _messages.Reader.ReadAllAsync(ct).ConfigureAwait(false))
            {
                List<TcpClient> clients;
                lock (_clients) clients = _clients.ToList();
                foreach (var client in clients)
                {
                    if (!await TryWriteAsync(client, message, ct).ConfigureAwait(false))
                        RemoveClient(client);
                }
            }
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested)
        {
        }
    }

    private static async Task<bool> TryWriteAsync(TcpClient client, BridgeMessage message, CancellationToken ct)
    {
        try
        {
            var bytes = JsonSerializer.SerializeToUtf8Bytes(message);
            var line = new byte[bytes.Length + 1];
            Buffer.BlockCopy(bytes, 0, line, 0, bytes.Length);
            line[^1] = (byte)'\n';
            await client.GetStream().WriteAsync(line.AsMemory(), ct).ConfigureAwait(false);
            await client.GetStream().FlushAsync(ct).ConfigureAwait(false);
            return true;
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested)
        {
            return false;
        }
        catch (Exception) when (!ct.IsCancellationRequested)
        {
            // A bad/disconnected client must never terminate the publisher loop.
            return false;
        }
    }

    private void RemoveClient(TcpClient client)
    {
        lock (_clients) _clients.Remove(client);
        try { client.Dispose(); } catch { }
    }

    public async ValueTask DisposeAsync()
    {
        _cts.Cancel();
        _messages.Writer.TryComplete();
        _listener.Stop();
        List<TcpClient> clients;
        lock (_clients) clients = _clients.ToList();
        foreach (var client in clients) RemoveClient(client);
        _cts.Dispose();
        await Task.CompletedTask;
    }
}
