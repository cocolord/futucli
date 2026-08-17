import builtins
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch


def test_config_imports_tomli_when_tomllib_is_unavailable():
    config_path = Path(__file__).parents[1] / "src" / "futucli" / "config.py"
    spec = importlib.util.spec_from_file_location("futucli_config_py310", config_path)
    module = importlib.util.module_from_spec(spec)
    real_import = builtins.__import__

    def import_without_tomllib(name, *args, **kwargs):
        if name == "tomllib":
            raise ModuleNotFoundError("No module named 'tomllib'")
        return real_import(name, *args, **kwargs)

    with (
        patch.object(builtins, "__import__", side_effect=import_without_tomllib),
        patch.dict(sys.modules, {"tomli": sys.modules["tomllib"]}),
    ):
        spec.loader.exec_module(module)

    assert module.tomllib is sys.modules["tomllib"]
