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
futucli trade account

# List positions
futucli trade positions

# Place a normal/limit order (simulated by default)
futucli trade order HK.00700 100 350.0 --side BUY

# Place a market order
futucli trade order HK.00700 100 0 --side BUY --order-type MARKET

# List orders
futucli trade orders

# Cancel an order
futucli trade cancel <order-id>

```

Each market-data or trading command opens its own FutuOpenD connection and
closes it before exiting. `connect` and `status` are connectivity checks; they
do not create a persistent background session.

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
| `futucli quote snapshot CODES...` | Real-time market snapshot |
| `futucli quote orderbook CODE` | Order book (bid/ask) |
| `futucli quote kline CODE` | Historical K-line data |
| `futucli quote ticker CODE` | Real-time ticker |
| `futucli trade account` | Account info and funds |
| `futucli trade positions` | Current positions |
| `futucli trade order CODE QTY PRICE` | Place an order |
| `futucli trade orders` | List today's orders |
| `futucli trade cancel ORDER_ID` | Cancel an order |

## License

MIT
