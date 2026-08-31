"""Quote / market data commands."""

import csv
from enum import Enum
import json
import sys

import pandas as pd
import typer
from rich import box
from rich.console import Console
from rich.table import Table

from .. import futu
from ..connection import quote_context

console = Console(width=200)
quote_app = typer.Typer(help="Market data commands")
SNAPSHOT_FIELDS = (
    "code",
    "name",
    "update_time",
    "market_state",
    "currency",
    "last_price",
    "overnight_price",
    "prev_close_price",
    "change_rate",
    "volume",
    "high_price",
    "low_price",
)
CURRENCY_BY_MARKET = {
    "HK": "HKD",
    "US": "USD",
    "SH": "CNY",
    "SZ": "CNY",
    "BJ": "CNY",
    "SG": "SGD",
    "JP": "JPY",
    "MY": "MYR",
}


def _table(title: str):
    return Table(
        title=title,
        box=box.SIMPLE,
        show_lines=False,
        collapse_padding=True,
        pad_edge=False,
    )


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


def _optional_value(value):
    if value is None or value == "N/A" or pd.isna(value):
        return None
    return value.item() if hasattr(value, "item") else value


def _snapshot_records(data, market_states: dict) -> list[dict]:
    records = []
    for _, row in data.iterrows():
        code = str(row["code"])
        last_price = _optional_value(row.get("last_price"))
        prev_close_price = _optional_value(row.get("prev_close_price"))
        change_rate = (
            (last_price - prev_close_price) / prev_close_price * 100
            if last_price is not None
            and prev_close_price not in (None, 0)
            else None
        )
        records.append(
            {
                "code": code,
                "name": _optional_value(row.get("name")),
                "update_time": _optional_value(row.get("update_time")),
                "market_state": market_states.get(code),
                "currency": CURRENCY_BY_MARKET.get(code.partition(".")[0]),
                "last_price": last_price,
                "overnight_price": _optional_value(row.get("overnight_price")),
                "prev_close_price": prev_close_price,
                "change_rate": change_rate,
                "volume": _optional_value(row.get("volume")),
                "high_price": _optional_value(row.get("high_price")),
                "low_price": _optional_value(row.get("low_price")),
            }
        )
    return records


def _print_snapshot_table(records: list[dict]):
    table = _table("Market Snapshot")
    table.add_column("Code", no_wrap=True)
    table.add_column("Name", no_wrap=True)
    table.add_column("Last Price")
    table.add_column("Overnight Price")
    table.add_column("Prev Close")
    table.add_column("Change %")
    table.add_column("Volume")
    table.add_column("High")
    table.add_column("Low")

    for record in records:
        table.add_row(
            record["code"],
            str(record["name"] or ""),
            f"{record['last_price']:.3f}" if record["last_price"] is not None else "-",
            (
                f"{record['overnight_price']:.3f}"
                if record["overnight_price"] is not None
                else "-"
            ),
            (
                f"{record['prev_close_price']:.3f}"
                if record["prev_close_price"] is not None
                else "-"
            ),
            f"{record['change_rate']:.2f}%" if record["change_rate"] is not None else "-",
            f"{record['volume']:,}" if record["volume"] is not None else "-",
            f"{record['high_price']:.3f}" if record["high_price"] is not None else "-",
            f"{record['low_price']:.3f}" if record["low_price"] is not None else "-",
        )
    console.print(table)

    metadata_table = _table("Snapshot Metadata")
    metadata_table.add_column("Code", no_wrap=True)
    metadata_table.add_column("SDK Update Time", no_wrap=True)
    metadata_table.add_column("Market State", no_wrap=True)

    for record in records:
        metadata_table.add_row(
            record["code"],
            str(record["update_time"] or "-"),
            str(record["market_state"] or "-"),
        )
    console.print(metadata_table)


@quote_app.command()
def snapshot(
    codes: list[str] = typer.Argument(..., help="Stock codes, e.g. HK.00700 US.AAPL"),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output JSON records; currency is inferred from the stock-code market prefix",
    ),
    csv_output: bool = typer.Option(
        False,
        "--csv",
        help="Output CSV records; currency is inferred from the stock-code market prefix",
    ),
):
    """Get real-time market snapshot for one or more stocks."""
    if json_output and csv_output:
        console.print("[red]Choose either --json or --csv, not both.[/red]")
        raise typer.Exit(2)

    if json_output or csv_output:
        futu.SysConfig.enable_console_log(False)
    with quote_context() as quote:
        ret, data = quote.get_market_snapshot(codes)
        if ret != 0:
            console.print(f"[red]Error: {data}[/red]")
            raise typer.Exit(1)
        market_state_ret, market_state_data = quote.get_market_state(codes)
    market_states = (
        {
            row["code"]: row["market_state"]
            for _, row in market_state_data.iterrows()
        }
        if market_state_ret == 0
        else {}
    )
    records = _snapshot_records(data, market_states)

    if json_output:
        typer.echo(json.dumps(records, ensure_ascii=False, allow_nan=False))
    elif csv_output:
        writer = csv.DictWriter(sys.stdout, fieldnames=SNAPSHOT_FIELDS)
        writer.writeheader()
        writer.writerows(records)
    else:
        _print_snapshot_table(records)


@quote_app.command()
def orderbook(code: str = typer.Argument(..., help="Stock code, e.g. HK.00700")):
    """Get order book (bid/ask) for a stock."""
    with quote_context() as quote:
        ret, data = quote.get_order_book(code)
    if ret != 0:
        console.print(f"[red]Error: {data}[/red]")
        raise typer.Exit(1)

    ask_table = _table(f"Ask — {code}")
    ask_table.add_column("Price", style="red", no_wrap=True)
    ask_table.add_column("Volume", style="red", no_wrap=True)
    ask_table.add_column("Orders", style="red", no_wrap=True)

    bid_table = _table(f"Bid — {code}")
    bid_table.add_column("Price", style="green", no_wrap=True)
    bid_table.add_column("Volume", style="green", no_wrap=True)
    bid_table.add_column("Orders", style="green", no_wrap=True)

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
    count: int = typer.Option(
        30,
        help="Number of bars (defaults to about 30 trading days for K_DAY)",
    ),
):
    """Get the most recent K-line data."""
    sdk_ktype = getattr(futu.KLType, ktype.value)
    sdk_subtype = getattr(futu.SubType, ktype.value)
    with quote_context() as quote:
        ret, data = quote.subscribe(
            [code],
            [sdk_subtype],
            subscribe_push=False,
        )
        if ret != 0:
            console.print(f"[red]Error: {data}[/red]")
            raise typer.Exit(1)
        ret, data = quote.get_cur_kline(code, count, ktype=sdk_ktype)
    if ret != 0:
        console.print(f"[red]Error: {data}[/red]")
        raise typer.Exit(1)

    table = _table(f"K-line — {code} ({ktype.value})")
    table.add_column("Date", no_wrap=True)
    table.add_column("Open", no_wrap=True)
    table.add_column("High", no_wrap=True)
    table.add_column("Low", no_wrap=True)
    table.add_column("Close", no_wrap=True)
    table.add_column("Volume", no_wrap=True)

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

    table = _table(f"Ticker — {code}")
    table.add_column("Time", no_wrap=True)
    table.add_column("Price", no_wrap=True)
    table.add_column("Volume", no_wrap=True)
    table.add_column("Turnover", no_wrap=True)
    table.add_column("Direction", no_wrap=True)

    for _, row in data.iterrows():
        table.add_row(
            str(row.get("time", "")),
            f"{row.get('price', 0):.3f}",
            f"{row.get('volume', 0):,}",
            f"{row.get('turnover', 0):.2f}",
            str(row.get("ticker_direction", "")),
        )
    console.print(table)
