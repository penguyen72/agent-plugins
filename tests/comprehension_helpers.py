import importlib.util
from pathlib import Path
from types import ModuleType


PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "plugins/comprehension-profile"


def load_plugin_module(name: str, relative_path: str) -> ModuleType:
    path = PLUGIN_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load plugin module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
