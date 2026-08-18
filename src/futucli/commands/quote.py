"""Quote / market data commands."""

from enum import Enum

import typer
from rich.console import Console
from rich.table import Table

from .. import futu
from ..connection import quote_context

console = Console()
quote_app = typer.Typer(help="Market data commands")


class KlineType(str, Enum):
    K_1M = "K_1M"
    K_5M = "K_5M"
    K_15M = "K_15M"
    K_30M = "K_30M"
    K_60M = "K_60M"
    K_DAY = "K_DAY"
    K_WEEK = "K_WEEK"
    K_MON = "K_MON"
    K_YEAR = "K_YEAR"


@quote_app.command()
def snapshot(codes: list[str] = typer.Argument(..., help="Stock codes, e.g. HK.00700 US.AAPL")):
    """Get real-time market snapshot for one or more stocks."""
    with quote_context() as quote:
        ret, data = quote.get_market_snapshot(codes)
    if ret != 0:
        console.print(f"[red]Error: {data}[/red]")
        raise typer.Exit(1)

    table = Table(title="Market Snapshot")
    table.add_column("Code")
    table.add_column("Name")
    table.add_column("Price")
    table.add_column("Change %")
    table.add_column("Volume")
    table.add_column("High")
    table.add_column("Low")

    for _, row in data.iterrows():
        table.add_row(
            row["code"],
            str(row.get("name", "")),
            f"{row.get('last_price', '-'):.3f}" if row.get("last_price") else "-",
            f"{row.get('change_rate', 0):.2f}%",
            f"{row.get('volume', 0):,}",
            f"{row.get('high_price', '-'):.3f}" if row.get("high_price") else "-",
            f"{row.get('low_price', '-'):.3f}" if row.get("low_price") else "-",
        )
    console.print(table)


@quote_app.command()
def orderbook(code: str = typer.Argument(..., help="Stock code, e.g. HK.00700")):
    """Get order book (bid/ask) for a stock."""
    with quote_context() as quote:
        ret, data = quote.get_order_book(code)
    if ret != 0:
        console.print(f"[red]Error: {data}[/red]")
        raise typer.Exit(1)

    ask_table = Table(title=f"Ask — {code}")
    ask_table.add_column("Price", style="red")
    ask_table.add_column("Volume", style="red")
    ask_table.add_column("Orders", style="red")

    bid_table = Table(title=f"Bid — {code}")
    bid_table.add_column("Price", style="green")
    bid_table.add_column("Volume", style="green")
    bid_table.add_column("Orders", style="green")

    for price, volume, order_count, *_ in data.get("Ask", []):
        ask_table.add_row(f"{price:.3f}", f"{volume:,}", str(order_count))

    for price, volume, order_count, *_ in data.get("Bid", []):
        bid_table.add_row(f"{price:.3f}", f"{volume:,}", str(order_count))

    console.print(ask_table)
    console.print(bid_table)


@quote_app.command()
def kline(
    code: str = typer.Argument(..., help="Stock code, e.g. HK.00700"),
    ktype: KlineType = typer.Option(KlineType.K_DAY, help="K-line type"),
    count: int = typer.Option(100, help="Number of bars"),
):
    """Get historical K-line data."""
    sdk_ktype = getattr(futu.KLType, ktype.value)
    with quote_context() as quote:
        ret, data, _ = quote.request_history_kline(
            code,
            ktype=sdk_ktype,
            max_count=count,
        )
    if ret != 0:
        console.print(f"[red]Error: {data}[/red]")
        raise typer.Exit(1)

    table = Table(title=f"K-line — {code} ({ktype.value})")
    table.add_column("Date")
    table.add_column("Open")
    table.add_column("High")
    table.add_column("Low")
    table.add_column("Close")
    table.add_column("Volume")

    for _, row in data.iterrows():
        table.add_row(
            str(row["time_key"]),
            f"{row['open']:.3f}",
            f"{row['high']:.3f}",
            f"{row['low']:.3f}",
            f"{row['close']:.3f}",
            f"{row['volume']:,}",
        )
    console.print(table)


@quote_app.command()
def ticker(
    code: str = typer.Argument(..., help="Stock code, e.g. HK.00700"),
    count: int = typer.Option(
        20,
        min=1,
        max=1000,
        help="Number of recent trades",
    ),
):
    """Get real-time ticker (price, change, turnover)."""
    with quote_context() as quote:
        ret, data = quote.subscribe(
            [code],
            [futu.SubType.TICKER],
            subscribe_push=False,
        )
        if ret != 0:
            console.print(f"[red]Error: {data}[/red]")
            raise typer.Exit(1)
        ret, data = quote.get_rt_ticker(code, num=count)
    if ret != 0:
        console.print(f"[red]Error: {data}[/red]")
        raise typer.Exit(1)

    table = Table(title=f"Ticker — {code}")
    table.add_column("Time")
    table.add_column("Price")
    table.add_column("Volume")
    table.add_column("Turnover")
    table.add_column("Direction")

    for _, row in data.iterrows():
        table.add_row(
            str(row.get("time", "")),
            f"{row.get('price', 0):.3f}",
            f"{row.get('volume', 0):,}",
            f"{row.get('turnover', 0):.2f}",
            str(row.get("ticker_direction", "")),
        )
    console.print(table)
