# futucli

CLI for [Futu OpenAPI](https://openapi.futunn.com/) — market data and trading from the terminal.

## Prerequisites

- [FutuOpenD](https://www.futunn.com/download/openAPI) running locally (default: `127.0.0.1:11111`)
- Python 3.10+

## Install

```bash
pip install futucli
```

Or from source:

```bash
git clone https://github.com/cocolord/futucli.git
cd futucli
pip install -e .
```

Upgrade a `uv tool` installation from GitHub:

```bash
futucli upgrade
```

## Quick Start

```bash
# Check that FutuOpenD is reachable
futucli connect

# Check connectivity again
futucli status

# Get a market snapshot
futucli quote snapshot HK.00700 US.AAPL

# Get order book
futucli quote orderbook HK.00700

# Get K-line data
futucli quote kline HK.00700 --ktype K_DAY --count 50

# Get real-time ticker
futucli quote ticker HK.00700

# Limit ticker output to the five most recent trades
futucli quote ticker HK.00700 --count 5

# View account info
futucli trade account --market US

# List positions
futucli trade positions --market US

# Place a normal/limit order (simulated by default)
futucli trade order HK.00700 100 350.0 --side BUY
futucli trade order US.AMD 10 150.0 --side BUY

# Place a market order
futucli trade order HK.00700 100 0 --side BUY --order-type MARKET

# List orders
futucli trade orders --market US

# Read historical fills (read-only; Futu supports REAL accounts only)
futucli trade history-deals --market US --env REAL --start 2026-09-01 --end 2026-09-30 --json

# Cancel an order
futucli trade cancel <order-id> --market US

```

Each market-data or trading command opens its own FutuOpenD connection and
closes it before exiting. `connect` and `status` are connectivity checks; they
do not create a persistent background session. Orders derive the account market
from the market-qualified stock code, select a matching account, and display the
trading environment, market, and account type before submission. Account,
position, order-list, and cancel commands accept `--market` and default to HK.
All trade commands accept `--acc-id` to select a specific account within that
market and environment. If multiple accounts match, the command lists their IDs
and stops until one is selected; it never silently chooses the first account.

## Historical fills

`trade history-deals` reads executed fills through Futu's
[`history_deal_list_query`](https://openapi.futunn.com/futu-api-doc/en/trade/get-history-order-fill-list.html).
It does not unlock trading, place orders, or change your configured environment.
Futu only supports this endpoint for **REAL** accounts. With the default
SIMULATE configuration, pass `--env REAL` for this read; SIMULATE is rejected
before connecting, rather than reported as an empty history.

```bash
# Read all fills in the selected account and market, for inclusive calendar dates
futucli trade history-deals --market HK --env REAL --start 2026-09-01 --end 2026-09-30

# Select an account and instrument; save machine-readable data for a workbench
futucli trade history-deals --market HK --env REAL --acc-id 123456 --code HK.00700 \
  --start 2026-09-01 --end 2026-09-30 --json > fills.json

# Export a spreadsheet-friendly table
futucli trade history-deals --market US --env REAL --acc-id 123456 \
  --start 2026-09-01 --end 2026-09-30 --csv > fills.csv
```

`--market` is required and filters both the eligible accounts and the returned
fills, including multi-market accounts. Use HK, US, or HKCC (Stock Connect).
`--code`, if supplied, must match that market. Account selection follows the
same `--acc-id` rules as other trade commands. The example account ID is fictional.
Dates select the interval from the first date's midnight up to, but excluding,
midnight after the last date, in the Futu endpoint's time convention. The Python
SDK accepts whole-second query bounds: we query through that next midnight and
filter by `create_time` locally, retaining fills in the last fractional second
without including the next day. Timestamps are preserved without timezone
conversion. This command makes one history request and preserves the SDK's row
order. Futu documents a limit of 10 history requests per account per 30 seconds;
broker restrictions and errors are reported without automatic retries.

The default output is a table. `--json` returns an object with `schema_version`,
`acc_id`, `trd_env`, `market`, `start`, `end`, `end_exclusive`, `code`, `retrieved_at_utc`, `count`,
and `deals`. `--csv` includes `acc_id`, `trd_env`, and `market` on every row.
Both formats retain the deal/order IDs, instrument, side, quantity, price,
creation time, execution market, status, counterparty broker and Japanese
account type where the SDK supplies them. IDs are strings; unavailable or
non-finite values become JSON null / empty CSV cells. An empty successful query
returns `count: 0, deals: []` or a CSV header. Errors go to stderr with a nonzero
exit status and no data on stdout.

Each record is a fill, so partial executions of one order remain separate.
Preserve `status` when importing cancellations or corrections. This endpoint
does not provide a complete fee, cash-flow or corporate-action ledger; the
command does not infer fees, currencies, profits, or a full account return.

## Configuration

By default, `futucli` connects to `127.0.0.1:11111` in simulated trading mode.

Override via environment variables:

```bash
export FUTU_HOST=192.168.1.100
export FUTU_PORT=11111
export FUTU_TRADE_ENV=REAL
export FUTUCLI_SDK_HOME=/path/to/writable/runtime-dir
```

`FUTUCLI_SDK_HOME` is optional. It controls the root where the Futu Python SDK
writes runtime logs. By default, `futucli` uses a per-user directory under the
system temporary directory so that read-only or sandboxed agents do not need
write access to `~/.com.futunn.FutuOpenD/Log`.

Or create `~/.config/futucli/config.toml`:

```toml
host = "127.0.0.1"
port = 11111
trade_env = "SIMULATE"
```

## Commands

| Command | Description |
|---------|-------------|
| `futucli connect` | Check FutuOpenD connectivity |
| `futucli status` | Check FutuOpenD connectivity |
| `futucli config` | Show current configuration |
| `futucli upgrade` | Upgrade from the GitHub repository using `uv` |
| `futucli quote snapshot CODES...` | Real-time market snapshot |
| `futucli quote orderbook CODE` | Order book (bid/ask) |
| `futucli quote kline CODE` | Historical K-line data |
| `futucli quote ticker CODE` | Real-time ticker |
| `futucli trade account [--market MARKET]` | Account info and funds |
| `futucli trade positions [--market MARKET]` | Current positions |
| `futucli trade order CODE QTY PRICE` | Place an order |
| `futucli trade orders [--market MARKET]` | List today's orders |
| `futucli trade history-deals --market MARKET --start DATE --end DATE` | Read historical fills; supports `--env REAL`, `--acc-id`, `--code`, `--json` or `--csv` |
| `futucli trade cancel ORDER_ID [--market MARKET]` | Cancel an order |

## License

MIT
