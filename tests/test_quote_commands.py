from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pandas as pd
from typer.testing import CliRunner

from futucli import futu
from futucli.cli import app

runner = CliRunner()


@contextmanager
def quote_context_for(quote):
    yield quote


def test_snapshot_opens_command_scoped_connection_and_renders_data():
    quote = MagicMock(spec=futu.OpenQuoteContext)
    quote.get_market_snapshot.return_value = (
        0,
        pd.DataFrame(
            [
                {
                    "code": "HK.00700",
                    "name": "Tencent",
                    "last_price": 350.2,
                    "change_rate": 1.25,
                    "volume": 1000,
                    "high_price": 355.0,
                    "low_price": 345.0,
                }
            ]
        ),
    )

    with patch(
        "futucli.commands.quote.quote_context",
        return_value=quote_context_for(quote),
    ) as context_factory:
        result = runner.invoke(app, ["quote", "snapshot", "HK.00700"])

    assert result.exit_code == 0
    assert "HK.00700" in result.stdout
    assert "Tencent" in result.stdout
    assert "350.200" in result.stdout
    context_factory.assert_called_once_with()
    quote.get_market_snapshot.assert_called_once_with(["HK.00700"])


def test_orderbook_renders_futu_dictionary_structure():
    quote = MagicMock(spec=futu.OpenQuoteContext)
    quote.get_order_book.return_value = (
        0,
        {
            "code": "HK.00700",
            "Ask": [(351.2, 2000, 4, {"ask-1": 2000})],
            "Bid": [(350.8, 1800, 3, {"bid-1": 1800})],
        },
    )

    with patch(
        "futucli.commands.quote.quote_context",
        return_value=quote_context_for(quote),
    ):
        result = runner.invoke(app, ["quote", "orderbook", "HK.00700"])

    assert result.exit_code == 0
    assert "351.200" in result.stdout
    assert "2,000" in result.stdout
    assert "350.800" in result.stdout
    assert "1,800" in result.stdout


def test_ticker_renders_trade_fields():
    quote = MagicMock(spec=futu.OpenQuoteContext)
    quote.get_rt_ticker.return_value = (
        0,
        pd.DataFrame(
            [
                {
                    "code": "HK.00700",
                    "name": "Tencent",
                    "time": "10:01:02",
                    "price": 350.6,
                    "volume": 500,
                    "turnover": 175300.0,
                    "ticker_direction": "BUY",
                }
            ]
        ),
    )

    with patch(
        "futucli.commands.quote.quote_context",
        return_value=quote_context_for(quote),
    ):
        result = runner.invoke(app, ["quote", "ticker", "HK.00700"])

    assert result.exit_code == 0
    assert "10:01:02" in result.stdout
    assert "350.600" in result.stdout
    assert "175300.00" in result.stdout
    assert "BUY" in result.stdout


def test_kline_rejects_unknown_type_before_opening_connection():
    with patch("futucli.commands.quote.quote_context") as context_factory:
        result = runner.invoke(
            app,
            ["quote", "kline", "HK.00700", "--ktype", "K_UNKNOWN"],
        )

    assert result.exit_code == 2
    assert "Invalid value" in result.stderr
    context_factory.assert_not_called()


def test_kline_passes_valid_sdk_type():
    quote = MagicMock(spec=futu.OpenQuoteContext)
    quote.request_history_kline.return_value = (
        0,
        pd.DataFrame(
            [
                {
                    "time_key": "2026-08-14",
                    "open": 345.0,
                    "high": 355.0,
                    "low": 344.0,
                    "close": 350.0,
                    "volume": 10000,
                }
            ]
        ),
        None,
    )

    with patch(
        "futucli.commands.quote.quote_context",
        return_value=quote_context_for(quote),
    ):
        result = runner.invoke(
            app,
            ["quote", "kline", "HK.00700", "--ktype", "K_DAY", "--count", "1"],
        )

    assert result.exit_code == 0
    quote.request_history_kline.assert_called_once_with(
        "HK.00700",
        ktype=futu.KLType.K_DAY,
        max_count=1,
    )
