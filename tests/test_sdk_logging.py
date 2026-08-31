import os
import subprocess
import sys
from pathlib import Path


def test_sdk_logs_do_not_require_writable_user_home(tmp_path):
    blocked_home = tmp_path / "blocked-home"
    blocked_home.write_text("not a directory")
    sdk_home = tmp_path / "sdk-home"
    source_root = Path(__file__).parents[1] / "src"

    env = os.environ.copy()
    env["HOME"] = str(blocked_home)
    env["FUTUCLI_SDK_HOME"] = str(sdk_home)
    env["PYTHONPATH"] = str(source_root)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os; "
                "from futucli import futu; "
                "from futucli.cli import app; "
                "print(os.environ['HOME']); "
                "print(app.info.name); "
                "print(futu.SysConfig.enable_console_log)"
            ),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert str(blocked_home) in result.stdout
    assert "futucli" in result.stdout
    assert list((sdk_home / ".com.futunn.FutuOpenD" / "Log").glob("py_*.log"))
