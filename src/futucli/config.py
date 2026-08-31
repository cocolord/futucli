"""Configuration management — env vars and config file."""

import os
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 11111
DEFAULT_TRADE_ENV = "SIMULATE"
DEFAULT_TIMEOUT_SECONDS = 10

CONFIG_DIR = Path.home() / ".config" / "futucli"
CONFIG_FILE = CONFIG_DIR / "config.toml"


def _load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "rb") as f:
            return tomllib.load(f)
    return {}


def get_host() -> str:
    return os.environ.get("FUTU_HOST") or _load_config().get("host", DEFAULT_HOST)


def get_port() -> int:
    val = os.environ.get("FUTU_PORT")
    if val:
        return int(val)
    return _load_config().get("port", DEFAULT_PORT)


def get_trade_env() -> str:
    return os.environ.get("FUTU_TRADE_ENV") or _load_config().get("trade_env", DEFAULT_TRADE_ENV)


def get_timeout_seconds() -> int:
    value = os.environ.get("FUTU_TIMEOUT_SECONDS")
    if value is None:
        value = _load_config().get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)

    try:
        timeout = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Invalid timeout_seconds {value!r}; expected a positive integer."
        ) from error
    if timeout <= 0:
        raise ValueError(
            f"Invalid timeout_seconds {value!r}; expected a positive integer."
        )
    return timeout


def get_trade_password() -> Optional[str]:
    return os.environ.get("FUTU_TRADE_PASSWORD") or _load_config().get("trade_password")


def get_trade_password_md5() -> Optional[str]:
    return os.environ.get("FUTU_TRADE_PASSWORD_MD5") or _load_config().get("trade_password_md5")
