"""futucli — CLI for Futu OpenAPI."""

import logging
import os
import tempfile
from pathlib import Path


def _import_futu_with_writable_log_home():
    user_suffix = str(os.getuid()) if hasattr(os, "getuid") else "user"
    sdk_home = Path(
        os.environ.get(
            "FUTUCLI_SDK_HOME",
            Path(tempfile.gettempdir()) / f"futucli-sdk-{user_suffix}",
        )
    )
    sdk_log_dir = sdk_home / ".com.futunn.FutuOpenD" / "Log"
    sdk_log_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    original_home = os.environ.get("HOME")
    os.environ["HOME"] = str(sdk_home)
    try:
        import futu
    finally:
        if original_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = original_home

    return futu


futu = _import_futu_with_writable_log_home()
futu.SysConfig.enable_console_log(False)

from futu.common.ft_logger import logger

logger.console_logger.addHandler(logging.NullHandler())
