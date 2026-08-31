"""FutuOpenD connection lifecycle."""

from contextlib import contextmanager

from . import futu
from . import config


def _configure_context(context, timeout):
    context.set_sync_query_connect_timeout(timeout)
    context._query_timeout = timeout
    return context


@contextmanager
def quote_context():
    """Open a quote connection for one CLI command."""
    timeout = config.get_timeout_seconds()
    context = _configure_context(
        futu.OpenQuoteContext(
            host=config.get_host(),
            port=config.get_port(),
            is_async_connect=True,
        ),
        timeout,
    )
    try:
        yield context
    finally:
        context.close()


@contextmanager
def trade_context():
    """Open a trade connection for one CLI command."""
    timeout = config.get_timeout_seconds()
    context = _configure_context(
        futu.OpenSecTradeContext(
            host=config.get_host(),
            port=config.get_port(),
            security_firm=futu.SecurityFirm.FUTUSECURITIES,
        ),
        timeout,
    )
    try:
        yield context
    finally:
        context.close()


def check_connections() -> dict:
    """Verify quote and trade connectivity, closing both before returning."""
    with quote_context() as quote:
        ret, data = quote.get_global_state()
        if ret != 0:
            raise ConnectionError(f"Quote connection failed: {data}")
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
