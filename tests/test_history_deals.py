import csv
from datetime import datetime
from io import StringIO
import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from typer.testing import CliRunner

from futucli import futu
from futucli.cli import app
from futucli.commands.trade import HISTORY_DEAL_FIELDS


runner = CliRunner()
ACCOUNT_ID = 281756457888247915
ARGS = [
    "trade", "history-deals", "--market", "US", "--env", "REAL",
    "--start", "2026-09-01", "--end", "2026-09-30",
]


@pytest.fixture
def sdk():
    with patch("futucli.connection.futu.OpenSecTradeContext", autospec=True) as factory:
        trade = factory.return_value
        trade.get_acc_list.return_value = (0, pd.DataFrame([
            {"acc_id": ACCOUNT_ID, "trd_env": "REAL", "acc_type": "MARGIN"},
            {"acc_id": 123456, "trd_env": "SIMULATE", "acc_type": "MARGIN"},
        ]))
        trade.history_deal_list_query.return_value = (0, pd.DataFrame([
            {
                "deal_id": "449150869556176742",
                "order_id": "6664320708369556828",
                "code": "US.AAPL", "stock_name": "Apple", "trd_side": "BUY",
                "qty": 0.125, "price": 123.456789,
                "create_time": "2026-09-29 15:59:59.019",
                "deal_market": "US", "status": "OK",
            },
            {
                "deal_id": "449150869556176743",
                "order_id": "6664320708369556828",
                "code": "US.AAPL", "stock_name": "Apple", "trd_side": "BUY",
                "qty": 0.25, "price": 123.456789,
                "create_time": "2026-09-29 15:59:59.020",
                "deal_market": "US", "status": "CANCELLED",
            },
        ]))
        yield factory, trade


def assert_read_only(trade):
    trade.place_order.assert_not_called()
    trade.modify_order.assert_not_called()
    trade.unlock_trade.assert_not_called()
    trade.order_list_query.assert_not_called()
    trade.history_order_list_query.assert_not_called()
    trade.close.assert_called_once()


def test_json_binds_account_market_and_dates_and_preserves_fills(sdk):
    factory, trade = sdk
    result = runner.invoke(app, ARGS + ["--acc-id", str(ACCOUNT_ID), "--code", "us.aapl", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == 1
    assert payload["acc_id"] == str(ACCOUNT_ID)
    assert payload["trd_env"] == "REAL"
    assert payload["market"] == "US"
    assert payload["code"] == "US.AAPL"
    assert payload["count"] == 2
    assert len(payload["deals"]) == 2
    first, second = payload["deals"]
    assert first["deal_id"] == "449150869556176742"
    assert first["order_id"] == second["order_id"] == "6664320708369556828"
    assert first["qty"] == 0.125
    assert first["price"] == 123.456789
    assert first["create_time"] == "2026-09-29 15:59:59.019"
    assert second["status"] == "CANCELLED"
    assert datetime.fromisoformat(payload["retrieved_at_utc"]).utcoffset().total_seconds() == 0
    assert factory.call_args.kwargs["filter_trdmarket"] == futu.TrdMarket.US
    trade.history_deal_list_query.assert_called_once_with(
        code="US.AAPL", start="2026-09-01 00:00:00", end="2026-10-01 00:00:00",
        trd_env=futu.TrdEnv.REAL, acc_id=ACCOUNT_ID, deal_market=futu.TrdMarket.US,
    )
    assert payload["start"] == "2026-09-01 00:00:00"
    assert payload["end"] == "2026-10-01 00:00:00"
    assert payload["end_exclusive"] is True
    assert result.stderr == ""
    assert_read_only(trade)


@pytest.mark.parametrize("code,market", [("HK.00700", "HK"), ("SH.600000", "HKCC")])
def test_other_markets_use_matching_account_and_fill_filters(sdk, code, market):
    factory, trade = sdk
    args = ARGS.copy()
    args[3] = market
    result = runner.invoke(app, args + ["--code", code, "--json"])
    assert result.exit_code == 0, result.output
    assert factory.call_args.kwargs["filter_trdmarket"] == market
    assert trade.history_deal_list_query.call_args.kwargs["deal_market"] == market
    assert trade.history_deal_list_query.call_args.kwargs["code"] == code


def test_csv_preserves_ids_and_quotes_broker_text(sdk):
    _, trade = sdk
    data = trade.history_deal_list_query.return_value[1]
    data["counter_broker_name"] = 'Broker, "Test"\nDesk'
    result = runner.invoke(app, ARGS + ["--csv"])
    assert result.exit_code == 0, result.output
    records = list(csv.DictReader(StringIO(result.stdout)))
    assert len(records) == 2
    assert records[0]["acc_id"] == str(ACCOUNT_ID)
    assert records[0]["deal_id"] == "449150869556176742"
    assert records[0]["counter_broker_name"] == 'Broker, "Test"\nDesk'
    assert records[0]["trd_env"] == "REAL"
    assert records[0]["market"] == "US"
    assert_read_only(trade)


def test_inclusive_dates_cover_last_fractional_second_using_real_sdk_date_parser(sdk):
    from futu.common.utils import normalize_start_end_date

    _, trade = sdk
    template = trade.history_deal_list_query.return_value[1].iloc[0].to_dict()
    times = ["2026-09-01 00:00:00", "2026-09-30 23:59:59.999", "2026-10-01 00:00:00"]

    def sdk_query(**kwargs):
        ret, error, start, end = normalize_start_end_date(kwargs["start"], kwargs["end"], 90)
        assert ret == futu.RET_OK, error
        assert start == "2026-09-01 00:00:00"
        assert end == "2026-10-01 00:00:00"
        return 0, pd.DataFrame([{**template, "create_time": t} for t in times])

    trade.history_deal_list_query.side_effect = sdk_query
    result = runner.invoke(app, ARGS + ["--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["count"] == 2
    assert [row["create_time"] for row in payload["deals"]] == times[:2]


def test_unavailable_numeric_values_do_not_become_nan_or_zero(sdk):
    _, trade = sdk
    data = trade.history_deal_list_query.return_value[1]
    data["price"] = [float("nan"), float("inf")]
    data["counter_broker_id"] = pd.NA
    result = runner.invoke(app, ARGS + ["--json"])
    assert result.exit_code == 0, result.output
    records = json.loads(result.stdout)["deals"]
    assert all(record["price"] is None for record in records)
    assert all(record["counter_broker_id"] is None for record in records)
    assert "NaN" not in result.stdout
    assert "Infinity" not in result.stdout


@pytest.mark.parametrize("output", ["--json", "--csv"])
def test_empty_history_is_successful_with_account_context(sdk, output):
    _, trade = sdk
    trade.history_deal_list_query.return_value = (0, pd.DataFrame(columns=HISTORY_DEAL_FIELDS))
    result = runner.invoke(app, ARGS + [output])
    assert result.exit_code == 0, result.output
    if output == "--json":
        payload = json.loads(result.stdout)
        assert payload["count"] == 0
        assert payload["deals"] == []
        assert payload["acc_id"] == str(ACCOUNT_ID)
    else:
        reader = csv.DictReader(StringIO(result.stdout))
        assert "acc_id" in reader.fieldnames
        assert "deal_id" in reader.fieldnames
        assert list(reader) == []


@pytest.mark.parametrize("extra", [
    ["--env", "SIMULATE"], ["--start", "2026-02-30"],
    ["--start", "20260901"], ["--start", "2026-10-01"],
    ["--code", "HK.00700"], ["--code", "AAPL"], ["--market", "CN"],
    ["--json", "--csv"], ["--acc-id", "0"],
])
def test_invalid_requests_do_not_open_a_connection(sdk, extra):
    factory, _ = sdk
    result = runner.invoke(app, ARGS + extra)
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr
    factory.assert_not_called()


def test_configured_simulation_is_not_silently_changed(sdk):
    factory, _ = sdk
    args = ARGS.copy()
    del args[4:6]
    with patch("futucli.commands.trade.get_trade_env", return_value=futu.TrdEnv.SIMULATE):
        result = runner.invoke(app, args)
    assert result.exit_code == 2
    assert "--env REAL" in result.stderr
    factory.assert_not_called()


@pytest.mark.parametrize("failure", ["account_error", "wrong_account", "ambiguous", "sdk_error", "exception"])
def test_failures_do_not_emit_empty_success_and_close_the_context(sdk, failure):
    _, trade = sdk
    args = ARGS + ["--json"]
    if failure == "account_error":
        trade.get_acc_list.return_value = (-1, "account lookup failed")
    elif failure == "wrong_account":
        args += ["--acc-id", "123456"]
    elif failure == "ambiguous":
        accounts = trade.get_acc_list.return_value[1]
        other = accounts.iloc[[0]].copy()
        other["acc_id"] = 999999
        trade.get_acc_list.return_value = (0, pd.concat([accounts, other]))
    elif failure == "sdk_error":
        trade.history_deal_list_query.return_value = (-1, "rate limited")
    else:
        trade.history_deal_list_query.side_effect = ConnectionError("connection lost")
    result = runner.invoke(app, args)
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr
    if failure in {"account_error", "wrong_account", "ambiguous"}:
        trade.history_deal_list_query.assert_not_called()
    else:
        trade.history_deal_list_query.assert_called_once()
    assert_read_only(trade)


def test_default_output_is_a_table(sdk):
    result = runner.invoke(app, ARGS)
    assert result.exit_code == 0, result.output
    assert "Historical fills" in result.stdout
    assert "US.AAPL" in result.stdout
