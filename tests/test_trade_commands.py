from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pandas as pd
from typer.testing import CliRunner

from futucli import futu
from futucli.cli import app

runner = CliRunner()


@contextmanager
def trade_context_for(trade):
    yield trade


def stock_simulation_accounts(acc_id=987654):
    return (
        0,
        pd.DataFrame(
            [
                {
                    "acc_id": acc_id,
                    "trd_env": futu.TrdEnv.SIMULATE,
                    "acc_type": futu.TrdAccType.MARGIN,
                    "sim_acc_type": futu.SimAccType.STOCK,
                }
            ]
        ),
    )


def test_account_renders_wide_account_row_as_field_value_pairs():
    trade = MagicMock(spec=futu.OpenSecTradeContext)
    trade.get_acc_list.return_value = stock_simulation_accounts()
    trade.accinfo_query.return_value = (
        0,
        pd.DataFrame(
            [
                {
                    "power": 100000.0,
                    "cash": 80000.0,
                    "market_val": 20000.0,
                    "currency": "HKD",
                }
            ]
        ),
    )

    with (
        patch(
            "futucli.commands.trade.get_trade_env",
            return_value=futu.TrdEnv.SIMULATE,
        ),
        patch(
            "futucli.commands.trade.trade_context",
            return_value=trade_context_for(trade),
        ) as context_factory,
    ):
        result = runner.invoke(app, ["trade", "account"])

    assert result.exit_code == 0
    assert "power" in result.stdout
    assert "100000.0" in result.stdout
    assert "cash" in result.stdout
    assert "80000.0" in result.stdout
    assert "market_val" in result.stdout
    context_factory.assert_called_once_with(filter_trdmarket=futu.TrdMarket.HK)
    trade.accinfo_query.assert_called_once_with(
        trd_env=futu.TrdEnv.SIMULATE, acc_id=987654
    )


def test_order_passes_explicit_valid_enums_to_sdk():
    trade = MagicMock(spec=futu.OpenSecTradeContext)
    trade.get_acc_list.return_value = stock_simulation_accounts()
    trade.place_order.return_value = (0, pd.DataFrame([{"order_id": "123"}]))

    with (
        patch(
            "futucli.commands.trade.get_trade_env",
            return_value=futu.TrdEnv.SIMULATE,
        ),
        patch(
            "futucli.commands.trade.trade_context",
            return_value=trade_context_for(trade),
        ) as context_factory,
    ):
        result = runner.invoke(
            app,
            [
                "trade",
                "order",
                "US.AMD",
                "100",
                "350.0",
                "--side",
                "SELL",
                "--order-type",
                "MARKET",
            ],
        )

    assert result.exit_code == 0
    assert "SIMULATE + US + account type=MARGIN" in result.stdout
    assert "sim account type=STOCK" in result.stdout
    context_factory.assert_called_once_with(filter_trdmarket=futu.TrdMarket.US)
    trade.get_acc_list.assert_called_once_with()
    trade.place_order.assert_called_once_with(
        price=350.0,
        qty=100,
        code="US.AMD",
        trd_side=futu.TrdSide.SELL,
        order_type=futu.OrderType.MARKET,
        trd_env=futu.TrdEnv.SIMULATE,
        acc_id=987654,
    )


def test_order_does_not_submit_without_a_stock_simulation_account():
    trade = MagicMock(spec=futu.OpenSecTradeContext)
    trade.get_acc_list.return_value = (
        0,
        pd.DataFrame(
            [
                {
                    "acc_id": 123456,
                    "trd_env": futu.TrdEnv.SIMULATE,
                    "acc_type": futu.TrdAccType.MARGIN,
                    "sim_acc_type": futu.SimAccType.OPTION,
                }
            ]
        ),
    )

    with (
        patch(
            "futucli.commands.trade.get_trade_env",
            return_value=futu.TrdEnv.SIMULATE,
        ),
        patch(
            "futucli.commands.trade.trade_context",
            return_value=trade_context_for(trade),
        ) as context_factory,
    ):
        result = runner.invoke(
            app, ["trade", "order", "US.AMD", "100", "100.0"]
        )

    assert result.exit_code == 1
    assert "No stock trading account is available" in result.stdout
    trade.place_order.assert_not_called()


def test_order_rejects_invalid_side_before_opening_connection():
    with patch("futucli.commands.trade.trade_context") as context_factory:
        result = runner.invoke(
            app,
            [
                "trade",
                "order",
                "HK.00700",
                "100",
                "350.0",
                "--side",
                "BUE",
            ],
        )

    assert result.exit_code == 2
    assert "Invalid value" in result.stderr
    context_factory.assert_not_called()


def test_order_rejects_unsupported_limit_alias_before_opening_connection():
    with patch("futucli.commands.trade.trade_context") as context_factory:
        result = runner.invoke(
            app,
            [
                "trade",
                "order",
                "HK.00700",
                "100",
                "350.0",
                "--order-type",
                "LIMIT",
            ],
        )

    assert result.exit_code == 2
    assert "Invalid value" in result.stderr
    assert "NORMAL" in result.stderr
    assert "MARKET" in result.stderr
    context_factory.assert_not_called()


def test_order_help_documents_normal_as_limit_order():
    result = runner.invoke(app, ["trade", "order", "--help"])

    assert result.exit_code == 0
    assert "NORMAL (limit/regular) or MARKET" in result.stdout


def test_positions_renders_position_rows():
    trade = MagicMock(spec=futu.OpenSecTradeContext)
    trade.get_acc_list.return_value = stock_simulation_accounts()
    trade.position_list_query.return_value = (
        0,
        pd.DataFrame(
            [
                {
                    "code": "HK.00700",
                    "stock_name": "Tencent",
                    "qty": 100,
                    "cost_price": 340.0,
                    "nominal_price": 350.0,
                    "pl_val": 1000.0,
                }
            ]
        ),
    )

    with (
        patch(
            "futucli.commands.trade.get_trade_env",
            return_value=futu.TrdEnv.SIMULATE,
        ),
        patch(
            "futucli.commands.trade.trade_context",
            return_value=trade_context_for(trade),
        ) as context_factory,
    ):
        result = runner.invoke(app, ["trade", "positions"])

    assert result.exit_code == 0
    assert "HK.00700" in result.stdout
    assert "Tencent" in result.stdout
    assert "1000.00" in result.stdout
    context_factory.assert_called_once_with(filter_trdmarket=futu.TrdMarket.HK)
    trade.position_list_query.assert_called_once_with(
        trd_env=futu.TrdEnv.SIMULATE, acc_id=987654
    )


def test_cancel_passes_sdk_cancel_enum():
    trade = MagicMock(spec=futu.OpenSecTradeContext)
    trade.get_acc_list.return_value = stock_simulation_accounts()
    trade.modify_order.return_value = (0, pd.DataFrame())

    with (
        patch(
            "futucli.commands.trade.get_trade_env",
            return_value=futu.TrdEnv.SIMULATE,
        ),
        patch(
            "futucli.commands.trade.trade_context",
            return_value=trade_context_for(trade),
        ) as context_factory,
    ):
        result = runner.invoke(app, ["trade", "cancel", "order-123"])

    assert result.exit_code == 0
    assert "order-123" in result.stdout
    context_factory.assert_called_once_with(filter_trdmarket=futu.TrdMarket.HK)
    trade.modify_order.assert_called_once_with(
        modify_order_op=futu.ModifyOrderOp.CANCEL,
        order_id="order-123",
        qty=0,
        price=0,
        trd_env=futu.TrdEnv.SIMULATE,
        acc_id=987654,
    )


def test_orders_renders_today_orders():
    trade = MagicMock(spec=futu.OpenSecTradeContext)
    trade.get_acc_list.return_value = stock_simulation_accounts()
    trade.order_list_query.return_value = (
        0,
        pd.DataFrame(
            [
                {
                    "order_id": "order-123",
                    "code": "HK.00700",
                    "trd_side": "BUY",
                    "qty": 100,
                    "price": 350.0,
                    "order_status": "SUBMITTED",
                }
            ]
        ),
    )

    with (
        patch(
            "futucli.commands.trade.get_trade_env",
            return_value=futu.TrdEnv.SIMULATE,
        ),
        patch(
            "futucli.commands.trade.trade_context",
            return_value=trade_context_for(trade),
        ) as context_factory,
    ):
        result = runner.invoke(app, ["trade", "orders"])

    assert result.exit_code == 0
    assert "order-123" in result.stdout
    assert "HK.00700" in result.stdout
    assert "SUBMITTED" in result.stdout
    context_factory.assert_called_once_with(filter_trdmarket=futu.TrdMarket.HK)
    trade.order_list_query.assert_called_once_with(
        trd_env=futu.TrdEnv.SIMULATE, acc_id=987654
    )


def test_orders_opens_requested_us_market_context():
    trade = MagicMock(spec=futu.OpenSecTradeContext)
    trade.get_acc_list.return_value = stock_simulation_accounts()
    trade.order_list_query.return_value = (0, pd.DataFrame())

    with (
        patch(
            "futucli.commands.trade.get_trade_env",
            return_value=futu.TrdEnv.SIMULATE,
        ),
        patch(
            "futucli.commands.trade.trade_context",
            return_value=trade_context_for(trade),
        ) as context_factory,
    ):
        result = runner.invoke(app, ["trade", "orders", "--market", "US"])

    assert result.exit_code == 0
    context_factory.assert_called_once_with(filter_trdmarket=futu.TrdMarket.US)
