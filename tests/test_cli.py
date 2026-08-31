import subprocess
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from futucli.cli import APP_VERSION, GITHUB_REPOSITORY, app

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


def test_no_arguments_shows_root_help():
    result = runner.invoke(app, [])

    assert result.exit_code == 2
    assert "Usage:" in result.stdout
    assert "quote" in result.stdout
    assert "trade" in result.stdout


def test_version_reports_installed_package_version():
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout == f"futucli {APP_VERSION}\n"


def test_upgrade_installs_latest_github_version_with_uv():
    completed_process = subprocess.CompletedProcess([], 0)

    with (
        patch("futucli.cli.shutil.which", return_value="/usr/local/bin/uv"),
        patch(
            "futucli.cli.subprocess.run",
            return_value=completed_process,
        ) as run,
    ):
        result = runner.invoke(app, ["upgrade"])

    assert result.exit_code == 0
    run.assert_called_once_with(
        [
            "/usr/local/bin/uv",
            "tool",
            "install",
            "--force",
            GITHUB_REPOSITORY,
        ],
        check=False,
    )
    assert "Upgrade complete" in result.stdout


def test_upgrade_exits_with_install_instructions_without_uv():
    with patch("futucli.cli.shutil.which", return_value=None):
        result = runner.invoke(app, ["upgrade"])

    assert result.exit_code == 1
    assert "requires uv" in result.stdout
    assert "uv tool install --force" in result.stdout


def test_upgrade_propagates_uv_failure():
    completed_process = subprocess.CompletedProcess([], 2)

    with (
        patch("futucli.cli.shutil.which", return_value="/usr/local/bin/uv"),
        patch("futucli.cli.subprocess.run", return_value=completed_process),
    ):
        result = runner.invoke(app, ["upgrade"])

    assert result.exit_code == 2
    assert "Upgrade failed" in result.stdout


def test_market_commands_fail_fast_for_invalid_timeout(monkeypatch):
    monkeypatch.setenv("FUTU_TIMEOUT_SECONDS", "not-a-number")

    result = runner.invoke(app, ["quote", "snapshot", "SH.510300"])

    assert result.exit_code == 2
    assert "Configuration error" in result.stdout
    assert "positive\ninteger" in result.stdout
    assert "Traceback" not in result.stdout


@pytest.mark.parametrize(
    "arguments",
    [
        ["quote", "--help"],
        ["quote", "snapshot", "--help"],
        ["trade", "--help"],
        ["trade", "order", "--help"],
    ],
)
def test_subcommand_help_ignores_invalid_runtime_timeout(monkeypatch, arguments):
    monkeypatch.setenv("FUTU_TIMEOUT_SECONDS", "not-a-number")

    result = runner.invoke(app, arguments)

    assert result.exit_code == 0
    assert "Usage:" in result.stdout
