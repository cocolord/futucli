"""futucli — CLI for Futu OpenAPI."""

from importlib.metadata import PackageNotFoundError, version
import os
import shutil
import subprocess

import typer
from rich.console import Console
from rich.table import Table
from typer.core import TyperGroup

from . import config as cfg
from .commands.quote import quote_app
from .commands.trade import trade_app
from .connection import check_connections

class FutucliGroup(TyperGroup):
    def invoke(self, context):
        try:
            return super().invoke(context)
        except cfg.ConfigurationError as error:
            console.print(f"[red]Configuration error: {error}[/red]")
            raise typer.Exit(2) from error


app = typer.Typer(
    name="futucli",
    help="CLI for Futu OpenAPI — market data and trading from the terminal.",
    cls=FutucliGroup,
    invoke_without_command=True,
)
app.add_typer(quote_app, name="quote")
app.add_typer(trade_app, name="trade")

console = Console()
GITHUB_REPOSITORY = "git+https://github.com/cocolord/futucli.git"
try:
    APP_VERSION = version("futucli")
except PackageNotFoundError:
    APP_VERSION = "unknown"


@app.callback()
def main(
    show_version: bool = typer.Option(
        False,
        "--version",
        help="Show version and exit.",
        is_eager=True,
    ),
):
    """Futu OpenAPI command-line interface."""
    if show_version:
        typer.echo(f"futucli {APP_VERSION}")
        raise typer.Exit()


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
    except cfg.ConfigurationError:
        raise
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


@app.command()
def upgrade():
    """Upgrade futucli from the GitHub repository."""
    uv_path = shutil.which("uv")
    command = ["uv", "tool", "install", "--force", GITHUB_REPOSITORY]

    if uv_path is None:
        console.print("[red]Upgrade requires uv, but it was not found on PATH.[/red]")
        console.print(f"Run manually: {' '.join(command)}")
        raise typer.Exit(1)

    command[0] = uv_path
    console.print(f"Upgrading futucli from {GITHUB_REPOSITORY}...")
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        console.print("[red]Upgrade failed.[/red]")
        console.print(f"Retry manually: {' '.join(command)}")
        raise typer.Exit(result.returncode)

    console.print("[green]Upgrade complete. Run futucli again to use the new version.[/green]")


if __name__ == "__main__":
    app()
