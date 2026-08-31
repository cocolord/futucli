from contextlib import contextmanager
import csv
import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
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
                    "overnight_price": 349.8,
                    "prev_close_price": 345.0,
                    "volume": 1000,
                    "high_price": 355.0,
                    "low_price": 345.0,
                }
            ]
        ),
    )
    quote.get_market_state.return_value = (
        0,
        pd.DataFrame(
            [
                {
                    "code": "HK.00700",
                    "market_state": "MORNING",
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
    assert "350.200" in result.stdout
    assert "349.800" in result.stdout
    assert "345.000" in result.stdout
    assert "1.51%" in result.stdout
    assert "Last Price" in result.stdout
    assert "Overnight Price" in result.stdout
    assert "Snapshot Metadata" in result.stdout
    assert "SDK Update Time" in result.stdout
    assert "Snapshot Freshness" not in result.stdout
    assert "MORNING" in result.stdout
    context_factory.assert_called_once_with()
    quote.get_market_snapshot.assert_called_once_with(["HK.00700"])
    quote.get_market_state.assert_called_once_with(["HK.00700"])


def test_snapshot_shows_unknown_change_when_prev_close_is_missing():
    quote = MagicMock(spec=futu.OpenQuoteContext)
    quote.get_market_snapshot.return_value = (
        0,
        pd.DataFrame(
            [
                {
                    "code": "HK.00700",
                    "name": "Tencent",
                    "last_price": 350.2,
                    "volume": 1000,
                    "high_price": 355.0,
                    "low_price": 345.0,
                }
            ]
        ),
    )
    quote.get_market_state.return_value = (1, "market state unavailable")

    with patch(
        "futucli.commands.quote.quote_context",
        return_value=quote_context_for(quote),
    ):
        result = runner.invoke(app, ["quote", "snapshot", "HK.00700"])

    assert result.exit_code == 0
    assert "0.00%" not in result.stdout
    assert "350.200" in result.stdout
    assert "Snapshot Metadata" in result.stdout


def test_snapshot_json_outputs_machine_readable_records():
    quote = MagicMock(spec=futu.OpenQuoteContext)
    quote.get_market_snapshot.return_value = (
        0,
        pd.DataFrame(
            [
                {
                    "code": "US.MU",
                    "name": "Micron",
                    "update_time": "2026-08-24 03:55:00",
                    "last_price": 932.86,
                    "overnight_price": 919.79,
                    "prev_close_price": 974.33,
                    "volume": 1000,
                    "high_price": 989.96,
                    "low_price": 958.2,
                }
            ]
        ),
    )
    quote.get_market_state.return_value = (
        0,
        pd.DataFrame([{"code": "US.MU", "market_state": "OVERNIGHT"}]),
    )

    with (
        patch(
            "futucli.commands.quote.quote_context",
            return_value=quote_context_for(quote),
        ),
        patch("futucli.commands.quote.futu.SysConfig.enable_console_log") as disable_logs,
    ):
        result = runner.invoke(app, ["quote", "snapshot", "US.MU", "--json"])

    assert result.exit_code == 0
    [record] = json.loads(result.stdout)
    assert record == {
        "code": "US.MU",
        "name": "Micron",
        "update_time": "2026-08-24 03:55:00",
        "market_state": "OVERNIGHT",
        "currency": "USD",
        "last_price": 932.86,
        "overnight_price": 919.79,
        "prev_close_price": 974.33,
        "change_rate": record["change_rate"],
        "volume": 1000,
        "high_price": 989.96,
        "low_price": 958.2,
    }
    assert record["change_rate"] == pytest.approx(
        (932.86 - 974.33) / 974.33 * 100
    )
    disable_logs.assert_called_once_with(False)


def test_snapshot_csv_outputs_fixed_columns():
    quote = MagicMock(spec=futu.OpenQuoteContext)
    quote.get_market_snapshot.return_value = (
        0,
        pd.DataFrame(
            [
                {
                    "code": "SH.510300",
                    "name": "CSI 300 ETF",
                    "update_time": "2026-08-24 15:00:00",
                    "last_price": 4.62,
                    "overnight_price": pd.NA,
                    "prev_close_price": 4.68,
                    "volume": 1000,
                    "high_price": 4.692,
                    "low_price": 4.593,
                }
            ]
        ),
    )
    quote.get_market_state.return_value = (
        0,
        pd.DataFrame(
            [{"code": "SH.510300", "market_state": "ASHARE_AFTER_HOURS_END"}]
        ),
    )

    with (
        patch(
            "futucli.commands.quote.quote_context",
            return_value=quote_context_for(quote),
        ),
        patch("futucli.commands.quote.futu.SysConfig.enable_console_log"),
    ):
        result = runner.invoke(app, ["quote", "snapshot", "SH.510300", "--csv"])

    assert result.exit_code == 0
    rows = list(csv.DictReader(result.stdout.splitlines()))
    assert rows == [
        {
            "code": "SH.510300",
            "name": "CSI 300 ETF",
            "update_time": "2026-08-24 15:00:00",
            "market_state": "ASHARE_AFTER_HOURS_END",
            "currency": "CNY",
            "last_price": "4.62",
            "overnight_price": "",
            "prev_close_price": "4.68",
            "change_rate": str((4.62 - 4.68) / 4.68 * 100),
            "volume": "1000",
            "high_price": "4.692",
            "low_price": "4.593",
        }
    ]


def test_snapshot_rejects_combined_json_and_csv_options():
    result = runner.invoke(
        app,
        ["quote", "snapshot", "HK.00700", "--json", "--csv"],
    )

    assert result.exit_code == 2
    assert "Choose either --json or --csv" in result.stdout


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
    quote.subscribe.return_value = (0, None)
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
    quote.subscribe.assert_called_once_with(
        ["HK.00700"],
        [futu.SubType.TICKER],
        subscribe_push=False,
    )
    quote.get_rt_ticker.assert_called_once_with("HK.00700", num=20)


def test_ticker_stops_when_subscription_fails():
    quote = MagicMock(spec=futu.OpenQuoteContext)
    quote.subscribe.return_value = (1, "subscription denied")

    with patch(
        "futucli.commands.quote.quote_context",
        return_value=quote_context_for(quote),
    ):
        result = runner.invoke(app, ["quote", "ticker", "HK.00700"])

    assert result.exit_code == 1
    assert "subscription denied" in result.stdout
    quote.get_rt_ticker.assert_not_called()


def test_ticker_passes_requested_count():
    quote = MagicMock(spec=futu.OpenQuoteContext)
    quote.subscribe.return_value = (0, None)
    quote.get_rt_ticker.return_value = (0, pd.DataFrame())

    with patch(
        "futucli.commands.quote.quote_context",
        return_value=quote_context_for(quote),
    ):
        result = runner.invoke(
            app,
            ["quote", "ticker", "HK.00700", "--count", "5"],
        )

    assert result.exit_code == 0
    quote.get_rt_ticker.assert_called_once_with("HK.00700", num=5)


def test_kline_rejects_unknown_type_before_opening_connection():
    with patch("futucli.commands.quote.quote_context") as context_factory:
        result = runner.invoke(
            app,
            ["quote", "kline", "HK.00700", "--ktype", "K_UNKNOWN"],
        )

    assert result.exit_code == 2
    assert "Invalid value" in result.stderr
    context_factory.assert_not_called()


def test_kline_defaults_to_30_bars():
    quote = MagicMock(spec=futu.OpenQuoteContext)
    quote.subscribe.return_value = (0, None)
    quote.get_cur_kline.return_value = (0, pd.DataFrame())

    with patch(
        "futucli.commands.quote.quote_context",
        return_value=quote_context_for(quote),
    ):
        result = runner.invoke(app, ["quote", "kline", "HK.00700"])

    assert result.exit_code == 0
    quote.subscribe.assert_called_once_with(
        ["HK.00700"],
        [futu.SubType.K_DAY],
        subscribe_push=False,
    )
    quote.get_cur_kline.assert_called_once_with(
        "HK.00700",
        30,
        ktype=futu.KLType.K_DAY,
    )


def test_kline_stops_when_subscription_fails():
    quote = MagicMock(spec=futu.OpenQuoteContext)
    quote.subscribe.return_value = (1, "subscription denied")

    with patch(
        "futucli.commands.quote.quote_context",
        return_value=quote_context_for(quote),
    ):
        result = runner.invoke(app, ["quote", "kline", "HK.00700"])

    assert result.exit_code == 1
    assert "subscription denied" in result.stdout
    quote.get_cur_kline.assert_not_called()


def test_kline_passes_valid_sdk_type():
    quote = MagicMock(spec=futu.OpenQuoteContext)
    quote.subscribe.return_value = (0, None)
    quote.get_cur_kline.return_value = (
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
    quote.subscribe.assert_called_once_with(
        ["HK.00700"],
        [futu.SubType.K_DAY],
        subscribe_push=False,
    )
    quote.get_cur_kline.assert_called_once_with(
        "HK.00700",
        1,
        ktype=futu.KLType.K_DAY,
    )
