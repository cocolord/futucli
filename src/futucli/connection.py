"""FutuOpenD connection lifecycle."""

from contextlib import contextmanager

from . import futu
from . import config


@contextmanager
def quote_context():
    """Open a quote connection for one CLI command."""
    context = futu.OpenQuoteContext(host=config.get_host(), port=config.get_port())
    try:
        yield context
    finally:
        context.close()


@contextmanager
def trade_context():
    """Open a trade connection for one CLI command."""
    context = futu.OpenSecTradeContext(
        host=config.get_host(),
        port=config.get_port(),
        security_firm=futu.SecurityFirm.FUTUSECURITIES,
    )
    try:
        yield context
    finally:
        context.close()


def check_connections() -> dict:
    """Verify quote and trade connectivity, closing both before returning."""
    with quote_context():
        with trade_context():
            return {
                "host": config.get_host(),
                "port": config.get_port(),
                "quote_reachable": True,
                "trade_reachable": True,
            }


def get_trade_env():
    env = config.get_trade_env().upper()
    if env == "REAL":
        return futu.TrdEnv.REAL
    if env == "SIMULATE":
        return futu.TrdEnv.SIMULATE
    raise ValueError(
        f"Invalid trade_env {env!r}; expected REAL or SIMULATE."
    )
