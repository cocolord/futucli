"""Trade commands."""

import csv
from datetime import date, datetime, timedelta, timezone
from enum import Enum
import json
import math
import sys

import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

from .. import futu
from ..connection import get_trade_env, get_trade_market, trade_context

console = Console()
trade_app = typer.Typer(help="Trading commands")


class TradeSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class TradeOrderType(str, Enum):
    NORMAL = "NORMAL"
    MARKET = "MARKET"


class TradeMarket(str, Enum):
    HK = "HK"
    US = "US"
    CN = "CN"
    HKCC = "HKCC"


class TradeEnvironment(str, Enum):
    REAL = "REAL"
    SIMULATE = "SIMULATE"


HISTORY_DEAL_FIELDS = (
    "deal_id", "order_id", "code", "stock_name", "deal_market", "trd_side",
    "qty", "price", "create_time", "status", "counter_broker_id",
    "counter_broker_name", "jp_acc_type",
)


def _sdk_trade_market(market):
    return getattr(futu.TrdMarket, market.value)


def _select_stock_account(accounts, trd_env, acc_id=None):
    required_columns = {"acc_id", "trd_env", "acc_type"}
    if not hasattr(accounts, "columns") or not required_columns.issubset(
        accounts.columns
    ):
        raise ValueError("Futu returned an invalid account list.")

    candidates = accounts[accounts["trd_env"] == trd_env]
    if trd_env == futu.TrdEnv.SIMULATE:
        if "sim_acc_type" not in candidates.columns:
            raise ValueError("Futu did not identify the simulated account type.")
        candidates = candidates[
            candidates["sim_acc_type"].isin(
                {futu.SimAccType.STOCK, futu.SimAccType.STOCK_AND_OPTION}
            )
        ]

    if acc_id is not None:
        candidates = candidates[candidates["acc_id"] == acc_id]

    if candidates.empty:
        raise ValueError(
            f"No stock trading account is available for environment {trd_env}."
            + (f" Requested account: {acc_id}." if acc_id is not None else "")
        )
    if len(candidates) != 1:
        account_ids = ", ".join(str(value) for value in candidates["acc_id"])
        raise ValueError(
            f"Multiple matching accounts ({account_ids}); select one with --acc-id."
        )
    return candidates.iloc[0]


def _get_stock_account(trade, trd_env, acc_id=None):
    ret, accounts = trade.get_acc_list()
    if ret != 0:
        raise ValueError(f"Unable to query accounts: {accounts}")
    return _select_stock_account(accounts, trd_env, acc_id)


@trade_app.command()
def account(
    market: TradeMarket = typer.Option(TradeMarket.HK, help="Trading account market"),
    acc_id: int | None = typer.Option(None, min=1, help="Select a trading account ID"),
):
    """Show account info and funds."""
    trd_env = get_trade_env()
    with trade_context(filter_trdmarket=_sdk_trade_market(market)) as trade:
        try:
            selected_account = _get_stock_account(trade, trd_env, acc_id)
        except ValueError as error:
            console.print(f"[red]Error: {error}[/red]")
            raise typer.Exit(1) from error
        ret, data = trade.accinfo_query(
            trd_env=trd_env, acc_id=int(selected_account["acc_id"])
        )
    if ret != 0:
        console.print(f"[red]Error: {data}[/red]")
        raise typer.Exit(1)

    table = Table(title=f"Account Info ({trd_env})")
    table.add_column("Field")
    table.add_column("Value")

    if not data.empty:
        for field, value in data.iloc[0].items():
            table.add_row(str(field), str(value))
    console.print(table)


@trade_app.command()
def positions(
    market: TradeMarket = typer.Option(TradeMarket.HK, help="Trading account market"),
    acc_id: int | None = typer.Option(None, min=1, help="Select a trading account ID"),
):
    """List current positions."""
    trd_env = get_trade_env()
    with trade_context(filter_trdmarket=_sdk_trade_market(market)) as trade:
        try:
            selected_account = _get_stock_account(trade, trd_env, acc_id)
        except ValueError as error:
            console.print(f"[red]Error: {error}[/red]")
            raise typer.Exit(1) from error
        ret, data = trade.position_list_query(
            trd_env=trd_env, acc_id=int(selected_account["acc_id"])
        )
    if ret != 0:
        console.print(f"[red]Error: {data}[/red]")
        raise typer.Exit(1)

    table = Table(title=f"Positions ({trd_env})")
    table.add_column("Code")
    table.add_column("Name")
    table.add_column("Qty")
    table.add_column("Cost")
    table.add_column("Price")
    table.add_column("P/L")

    for _, row in data.iterrows():
        table.add_row(
            row["code"],
            str(row.get("stock_name", "")),
            f"{row['qty']:,}",
            f"{row.get('cost_price', 0):.3f}",
            f"{row.get('nominal_price', 0):.3f}",
            f"{row.get('pl_val', 0):.2f}",
        )
    console.print(table)


@trade_app.command()
def order(
    code: str = typer.Argument(..., help="Stock code, e.g. HK.00700"),
    qty: int = typer.Argument(..., help="Order quantity"),
    price: float = typer.Argument(..., help="Order price"),
    side: TradeSide = typer.Option(TradeSide.BUY, help="BUY or SELL"),
    order_type: TradeOrderType = typer.Option(
        TradeOrderType.NORMAL,
        help="NORMAL (limit/regular) or MARKET",
    ),
    acc_id: int | None = typer.Option(None, min=1, help="Select a trading account ID"),
):
    """Place an order."""
    trd_env = get_trade_env()
    try:
        trd_market = get_trade_market(code, trd_env)
    except ValueError as error:
        console.print(f"[red]Error: {error}[/red]")
        raise typer.Exit(1) from error
    trd_side = getattr(futu.TrdSide, side.value)
    sdk_order_type = getattr(futu.OrderType, order_type.value)

    with trade_context(filter_trdmarket=trd_market) as trade:
        try:
            account = _get_stock_account(trade, trd_env, acc_id)
        except ValueError as error:
            console.print(f"[red]Error: {error}[/red]")
            raise typer.Exit(1) from error

        acc_type = account["acc_type"]
        sim_acc_type = account.get("sim_acc_type", futu.SimAccType.NONE)
        route = f"{trd_env} + {trd_market} + account type={acc_type}"
        if sim_acc_type != futu.SimAccType.NONE:
            route += f" + sim account type={sim_acc_type}"
        console.print(f"[yellow]Pre-submit: {route}[/yellow]")

        ret, data = trade.place_order(
            price=price,
            qty=qty,
            code=code,
            trd_side=trd_side,
            order_type=sdk_order_type,
            trd_env=trd_env,
            acc_id=int(account["acc_id"]),
        )
    if ret != 0:
        console.print(f"[red]Error: {data}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Order placed: {data}[/green]")


@trade_app.command()
def cancel(
    order_id: str = typer.Argument(..., help="Order ID to cancel"),
    market: TradeMarket = typer.Option(TradeMarket.HK, help="Order account market"),
    acc_id: int | None = typer.Option(None, min=1, help="Select a trading account ID"),
):
    """Cancel an order by ID."""
    trd_env = get_trade_env()
    with trade_context(filter_trdmarket=_sdk_trade_market(market)) as trade:
        try:
            selected_account = _get_stock_account(trade, trd_env, acc_id)
        except ValueError as error:
            console.print(f"[red]Error: {error}[/red]")
            raise typer.Exit(1) from error
        ret, data = trade.modify_order(
            modify_order_op=futu.ModifyOrderOp.CANCEL,
            order_id=order_id,
            qty=0,
            price=0,
            trd_env=trd_env,
            acc_id=int(selected_account["acc_id"]),
        )
    if ret != 0:
        console.print(f"[red]Error: {data}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Order {order_id} cancelled.[/green]")


@trade_app.command()
def orders(
    market: TradeMarket = typer.Option(TradeMarket.HK, help="Order account market"),
    acc_id: int | None = typer.Option(None, min=1, help="Select a trading account ID"),
):
    """List today's orders."""
    trd_env = get_trade_env()
    with trade_context(filter_trdmarket=_sdk_trade_market(market)) as trade:
        try:
            selected_account = _get_stock_account(trade, trd_env, acc_id)
        except ValueError as error:
            console.print(f"[red]Error: {error}[/red]")
            raise typer.Exit(1) from error
        ret, data = trade.order_list_query(
            trd_env=trd_env, acc_id=int(selected_account["acc_id"])
        )
    if ret != 0:
        console.print(f"[red]Error: {data}[/red]")
        raise typer.Exit(1)

    table = Table(title=f"Orders ({trd_env})")
    table.add_column("Order ID")
    table.add_column("Code")
    table.add_column("Side")
    table.add_column("Qty")
    table.add_column("Price")
    table.add_column("Status")

    for _, row in data.iterrows():
        table.add_row(
            str(row.get("order_id", "")),
            row["code"],
            str(row.get("trd_side", "")),
            f"{row['qty']:,}",
            f"{row.get('price', 0):.3f}",
            str(row.get("order_status", "")),
        )
    console.print(table)


def _history_date(value, option):
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError("non-canonical date")
        return parsed
    except ValueError as error:
        raise ValueError(f"{option} must be a valid YYYY-MM-DD date.") from error


def _history_records(data, start, end):
    required = {"deal_id", "order_id", "code", "trd_side", "qty", "price", "create_time"}
    if not required.issubset(data.columns):
        raise ValueError("Futu returned an invalid historical fill table.")
    records = []
    for row in data.to_dict(orient="records"):
        created_at = datetime.fromisoformat(str(row["create_time"]))
        if not start <= created_at < end:
            continue
        record = {}
        for field in HISTORY_DEAL_FIELDS:
            value = row.get(field)
            if value is None or pd.isna(value) or (isinstance(value, str) and value == "N/A"):
                value = None
            else:
                value = value.item() if hasattr(value, "item") else value
                if isinstance(value, float) and not math.isfinite(value):
                    value = None
                elif field in {"deal_id", "order_id", "counter_broker_id"}:
                    # SDK IDs are opaque; JSON numbers can lose precision in JS clients.
                    value = str(value)
            record[field] = value
        records.append(record)
    return records


@trade_app.command("history-deals")
def history_deals(
    start: str = typer.Option(..., help="First date, inclusive (YYYY-MM-DD)"),
    end: str = typer.Option(..., help="Last date, inclusive (YYYY-MM-DD)"),
    market: TradeMarket = typer.Option(..., help="Account and execution market"),
    acc_id: int | None = typer.Option(None, min=1, help="Select a trading account ID"),
    env: TradeEnvironment | None = typer.Option(None, help="Override environment for this read only"),
    code: str = typer.Option("", help="Optional market-qualified symbol, e.g. HK.00700"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON with account and query metadata"),
    csv_output: bool = typer.Option(False, "--csv", help="Output CSV with account and environment columns"),
):
    """Read historical fills. Futu supports REAL accounts only; no orders are submitted."""
    try:
        if json_output and csv_output:
            raise ValueError("Choose either --json or --csv, not both.")
        first_date = _history_date(start, "--start")
        last_date = _history_date(end, "--end")
        if first_date > last_date:
            raise ValueError("--start must not be after --end.")
        # The Python SDK accepts whole seconds only. Query through next midnight
        # and exclude that boundary locally to retain the last fractional second.
        query_start = f"{first_date.isoformat()} 00:00:00"
        query_end = f"{(last_date + timedelta(days=1)).isoformat()} 00:00:00"
        trd_env = getattr(futu.TrdEnv, env.value) if env is not None else get_trade_env()
        if trd_env != futu.TrdEnv.REAL:
            raise ValueError(
                "Futu historical fills do not support SIMULATE. "
                "Use --env REAL to read a real account; this does not enable order submission."
            )
        if market == TradeMarket.CN:
            raise ValueError("CN is a simulated market; use HKCC for real Stock Connect history.")
        sdk_market = _sdk_trade_market(market)
        code = code.strip().upper()
        if code and get_trade_market(code, trd_env) != sdk_market:
            raise ValueError("--code must belong to the selected --market.")
    except (ValueError, OverflowError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(2) from error

    try:
        with trade_context(filter_trdmarket=sdk_market) as trade:
            account = _get_stock_account(trade, trd_env, acc_id)
            selected_id = int(account["acc_id"])
            ret, data = trade.history_deal_list_query(
                code=code,
                start=query_start,
                end=query_end,
                trd_env=trd_env,
                acc_id=selected_id,
                deal_market=sdk_market,
            )
            if ret != futu.RET_OK:
                raise ValueError(f"Unable to query historical fills: {data}")
            records = _history_records(
                data, datetime.fromisoformat(query_start), datetime.fromisoformat(query_end)
            )
    except Exception as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    identity = {"acc_id": str(selected_id), "trd_env": trd_env, "market": market.value}
    if json_output:
        payload = {
            "schema_version": 1,
            **identity,
            "start": query_start,
            "end": query_end,
            "end_exclusive": True,
            "code": code,
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "count": len(records),
            "deals": records,
        }
        typer.echo(json.dumps(payload, ensure_ascii=False, allow_nan=False))
    elif csv_output:
        writer = csv.DictWriter(sys.stdout, fieldnames=(*identity, *HISTORY_DEAL_FIELDS))
        writer.writeheader()
        writer.writerows({**identity, **record} for record in records)
    else:
        table = Table(title=f"Historical fills ({trd_env}, {market.value}, account {selected_id})")
        fields = ("deal_id", "code", "trd_side", "qty", "price", "create_time", "status")
        for field in fields:
            table.add_column(field)
        for record in records:
            table.add_row(*(str(record[field]) if record[field] is not None else "-" for field in fields))
        console.print(table)
