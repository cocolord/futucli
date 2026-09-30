from contextlib import nullcontext
from unittest.mock import MagicMock, patch

import pytest

from futucli import connection, futu


def test_quote_context_opens_and_closes_for_one_command():
    with (
        patch.object(connection.config, "get_host", return_value="quote-host"),
        patch.object(connection.config, "get_port", return_value=12345),
        patch.object(connection.config, "get_timeout_seconds", return_value=8),
        patch.object(connection.futu, "OpenQuoteContext", autospec=True) as context_class,
    ):
        context = context_class.return_value

        with connection.quote_context() as opened:
            assert opened is context

        context_class.assert_called_once_with(
            host="quote-host",
            port=12345,
            is_async_connect=True,
        )
        context.set_sync_query_connect_timeout.assert_called_once_with(8)
        assert context._query_timeout == 8
        context.close.assert_called_once_with()


def test_quote_context_closes_when_command_raises():
    with (
        patch.object(connection.config, "get_timeout_seconds", return_value=8),
        patch.object(
            connection,
            "futu",
            autospec=True,
        ) as futu_module,
    ):
        context = futu_module.OpenQuoteContext.return_value

        with pytest.raises(RuntimeError, match="command failed"):
            with connection.quote_context():
                raise RuntimeError("command failed")

        context.close.assert_called_once_with()


def test_quote_context_validates_timeout_before_opening_sdk_context():
    with (
        patch.object(
            connection.config,
            "get_timeout_seconds",
            side_effect=ValueError("invalid timeout"),
        ),
        patch.object(connection.futu, "OpenQuoteContext") as context_class,
    ):
        with pytest.raises(ValueError, match="invalid timeout"):
            with connection.quote_context():
                pass

    context_class.assert_not_called()


def test_trade_context_opens_and_closes_for_one_command():
    with (
        patch.object(connection.config, "get_host", return_value="trade-host"),
        patch.object(connection.config, "get_port", return_value=23456),
        patch.object(connection.config, "get_timeout_seconds", return_value=8),
        patch.object(connection.futu, "OpenSecTradeContext", autospec=True) as context_class,
    ):
        context = context_class.return_value

        with connection.trade_context() as opened:
            assert opened is context

        context_class.assert_called_once_with(
            filter_trdmarket=futu.TrdMarket.HK,
            host="trade-host",
            port=23456,
            security_firm=futu.SecurityFirm.FUTUSECURITIES,
        )
        context.set_sync_query_connect_timeout.assert_called_once_with(8)
        assert context._query_timeout == 8
        context.close.assert_called_once_with()


def test_check_connections_probes_quote_context_before_reporting_success():
    quote = MagicMock()
    quote.get_global_state.return_value = (0, {})
    trade = MagicMock()

    with (
        patch.object(
            connection,
            "quote_context",
            return_value=nullcontext(quote),
        ),
        patch.object(
            connection,
            "trade_context",
            return_value=nullcontext(trade),
        ),
    ):
        result = connection.check_connections()

    assert result["quote_reachable"] is True
    assert result["trade_reachable"] is True
    quote.get_global_state.assert_called_once_with()


def test_check_connections_rejects_unreachable_quote_context():
    quote = MagicMock()
    quote.get_global_state.return_value = (1, "Connect timeout")

    with (
        patch.object(
            connection,
            "quote_context",
            return_value=nullcontext(quote),
        ),
        patch.object(connection, "trade_context") as trade_context_factory,
    ):
        with pytest.raises(ConnectionError, match="Connect timeout"):
            connection.check_connections()

    trade_context_factory.assert_not_called()


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        pytest.param("REAL", futu.TrdEnv.REAL, id="real"),
        pytest.param("simulate", futu.TrdEnv.SIMULATE, id="simulate_case_insensitive"),
    ],
)
def test_get_trade_env_accepts_supported_values(configured, expected):
    with patch.object(connection.config, "get_trade_env", return_value=configured):
        assert connection.get_trade_env() == expected


def test_get_trade_env_rejects_unknown_value():
    with patch.object(connection.config, "get_trade_env", return_value="paper"):
        with pytest.raises(ValueError, match="expected REAL or SIMULATE"):
            connection.get_trade_env()


@pytest.mark.parametrize(
    ("code", "trd_env", "expected"),
    [
        pytest.param("US.AMD", futu.TrdEnv.SIMULATE, futu.TrdMarket.US, id="us"),
        pytest.param("HK.00700", futu.TrdEnv.SIMULATE, futu.TrdMarket.HK, id="hk"),
        pytest.param("SH.600000", futu.TrdEnv.SIMULATE, futu.TrdMarket.CN, id="cn_simulate"),
        pytest.param("SZ.000001", futu.TrdEnv.REAL, futu.TrdMarket.HKCC, id="cn_real"),
    ],
)
def test_get_trade_market_routes_market_qualified_codes(code, trd_env, expected):
    assert connection.get_trade_market(code, trd_env) == expected


@pytest.mark.parametrize("code", ["AMD", "SG.D05", "US."])
def test_get_trade_market_rejects_unroutable_codes(code):
    with pytest.raises(ValueError):
        connection.get_trade_market(code, futu.TrdEnv.SIMULATE)
