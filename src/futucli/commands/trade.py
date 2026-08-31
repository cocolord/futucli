"""Trade commands."""

from enum import Enum

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


def _sdk_trade_market(market):
    return getattr(futu.TrdMarket, market.value)


def _select_stock_account(accounts, trd_env):
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

    if candidates.empty:
        raise ValueError(
            f"No stock trading account is available for environment {trd_env}."
        )
    return candidates.iloc[0]


def _get_stock_account(trade, trd_env):
    ret, accounts = trade.get_acc_list()
    if ret != 0:
        raise ValueError(f"Unable to query accounts: {accounts}")
    return _select_stock_account(accounts, trd_env)


@trade_app.command()
def account(
    market: TradeMarket = typer.Option(TradeMarket.HK, help="Trading account market"),
):
    """Show account info and funds."""
    trd_env = get_trade_env()
    with trade_context(filter_trdmarket=_sdk_trade_market(market)) as trade:
        try:
            selected_account = _get_stock_account(trade, trd_env)
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
):
    """List current positions."""
    trd_env = get_trade_env()
    with trade_context(filter_trdmarket=_sdk_trade_market(market)) as trade:
        try:
            selected_account = _get_stock_account(trade, trd_env)
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
            account = _get_stock_account(trade, trd_env)
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
):
    """Cancel an order by ID."""
    trd_env = get_trade_env()
    with trade_context(filter_trdmarket=_sdk_trade_market(market)) as trade:
        try:
            selected_account = _get_stock_account(trade, trd_env)
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
):
    """List today's orders."""
    trd_env = get_trade_env()
    with trade_context(filter_trdmarket=_sdk_trade_market(market)) as trade:
        try:
            selected_account = _get_stock_account(trade, trd_env)
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
