# Security boundaries

- All service listeners bind to loopback only unless a future reviewed design says otherwise.
- `Config/secrets.local` is the only supported local API-key file and is gitignored.
- AI output is data, not authority. It is parsed, schema-checked, freshness-checked, locally gated, then sent as a narrow Guardian command.
- Guardian re-checks symbol, spread, trade mode, lot legality, free margin, validity window, valid price zone and real SL before execution.
- Guardian remains responsible for local weekend protection when Engine/AI/ATAS are offline.
- Never log API keys, authorization headers or full secret files.
- Demo/Paper acceptance is mandatory before any real account is considered.
