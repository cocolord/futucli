"""futucli — CLI for Futu OpenAPI."""

import os

import typer
from rich.console import Console
from rich.table import Table

from . import config as cfg
from .commands.quote import quote_app
from .commands.trade import trade_app
from .connection import check_connections

app = typer.Typer(
    name="futucli",
    help="CLI for Futu OpenAPI — market data and trading from the terminal.",
)
app.add_typer(quote_app, name="quote")
app.add_typer(trade_app, name="trade")

console = Console()


@app.command()
def connect():
    """Check connectivity to FutuOpenD."""
    try:
        info = check_connections()
        table = Table(title="FutuOpenD Connectivity")
        table.add_column("Key")
        table.add_column("Value")
        for key, value in info.items():
            table.add_row(key, str(value))
        console.print(table)
    except Exception as error:
        console.print(f"[red]Connection failed: {error}[/red]")
        raise typer.Exit(1) from error


@app.command()
def status():
    """Check FutuOpenD connectivity."""
    connect()


@app.command()
def config():
    """Show current configuration."""
    table = Table(title="Configuration")
    table.add_column("Key")
    table.add_column("Value")
    table.add_column("Source")

    host_src = "env" if os.environ.get("FUTU_HOST") else "default"
    port_src = "env" if os.environ.get("FUTU_PORT") else "default"
    env_src = "env" if os.environ.get("FUTU_TRADE_ENV") else "default"

    table.add_row("host", cfg.get_host(), host_src)
    table.add_row("port", str(cfg.get_port()), port_src)
    table.add_row("trade_env", cfg.get_trade_env(), env_src)
    console.print(table)


if __name__ == "__main__":
    app()
