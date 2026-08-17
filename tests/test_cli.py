from unittest.mock import patch

from typer.testing import CliRunner

from futucli.cli import app

runner = CliRunner()


def test_connect_is_a_bounded_connectivity_check():
    with patch(
        "futucli.cli.check_connections",
        return_value={
            "host": "127.0.0.1",
            "port": 11111,
            "quote_reachable": True,
            "trade_reachable": True,
        },
    ) as check_connections:
        result = runner.invoke(app, ["connect"])

    assert result.exit_code == 0
    assert "FutuOpenD Connectivity" in result.stdout
    assert "quote_reachable" in result.stdout
    assert "trade_reachable" in result.stdout
    check_connections.assert_called_once_with()


def test_root_help_does_not_claim_persistent_disconnect():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "disconnect" not in result.stdout
