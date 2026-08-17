"""Trade commands."""

from enum import Enum

import typer
from futu import ModifyOrderOp, OrderType, TrdSide
from rich.console import Console
from rich.table import Table

from ..connection import get_trade_env, trade_context

console = Console()
trade_app = typer.Typer(help="Trading commands")


class TradeSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class TradeOrderType(str, Enum):
    NORMAL = "NORMAL"
    MARKET = "MARKET"


@trade_app.command()
def account():
    """Show account info and funds."""
    trd_env = get_trade_env()
    with trade_context() as trade:
        ret, data = trade.accinfo_query(trd_env=trd_env)
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
def positions():
    """List current positions."""
    trd_env = get_trade_env()
    with trade_context() as trade:
        ret, data = trade.position_list_query(trd_env=trd_env)
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
    trd_side = getattr(TrdSide, side.value)
    sdk_order_type = getattr(OrderType, order_type.value)

    with trade_context() as trade:
        ret, data = trade.place_order(
            price=price,
            qty=qty,
            code=code,
            trd_side=trd_side,
            order_type=sdk_order_type,
            trd_env=trd_env,
        )
    if ret != 0:
        console.print(f"[red]Error: {data}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Order placed: {data}[/green]")


@trade_app.command()
def cancel(order_id: str = typer.Argument(..., help="Order ID to cancel")):
    """Cancel an order by ID."""
    trd_env = get_trade_env()
    with trade_context() as trade:
        ret, data = trade.modify_order(
            modify_order_op=ModifyOrderOp.CANCEL,
            order_id=order_id,
            qty=0,
            price=0,
            trd_env=trd_env,
        )
    if ret != 0:
        console.print(f"[red]Error: {data}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Order {order_id} cancelled.[/green]")


@trade_app.command()
def orders():
    """List today's orders."""
    trd_env = get_trade_env()
    with trade_context() as trade:
        ret, data = trade.order_list_query(trd_env=trd_env)
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
