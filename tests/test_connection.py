from unittest.mock import patch

import pytest

from futucli import connection, futu


def test_quote_context_opens_and_closes_for_one_command():
    with (
        patch.object(connection.config, "get_host", return_value="quote-host"),
        patch.object(connection.config, "get_port", return_value=12345),
        patch.object(connection.futu, "OpenQuoteContext", autospec=True) as context_class,
    ):
        context = context_class.return_value

        with connection.quote_context() as opened:
            assert opened is context

        context_class.assert_called_once_with(host="quote-host", port=12345)
        context.close.assert_called_once_with()


def test_quote_context_closes_when_command_raises():
    with patch.object(
        connection,
        "futu",
        autospec=True,
    ) as futu_module:
        context = futu_module.OpenQuoteContext.return_value

        with pytest.raises(RuntimeError, match="command failed"):
            with connection.quote_context():
                raise RuntimeError("command failed")

        context.close.assert_called_once_with()


def test_trade_context_opens_and_closes_for_one_command():
    with (
        patch.object(connection.config, "get_host", return_value="trade-host"),
        patch.object(connection.config, "get_port", return_value=23456),
        patch.object(connection.futu, "OpenSecTradeContext", autospec=True) as context_class,
    ):
        context = context_class.return_value

        with connection.trade_context() as opened:
            assert opened is context

        context_class.assert_called_once_with(
            host="trade-host",
            port=23456,
            security_firm=futu.SecurityFirm.FUTUSECURITIES,
        )
        context.close.assert_called_once_with()


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
