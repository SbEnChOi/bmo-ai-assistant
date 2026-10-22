"""Load server-side keys from the environment or a local, untracked config file."""
import importlib
import os


def api_key(name):
    try:
        private_config = importlib.import_module(".private_config", __package__)
    except ModuleNotFoundError as exc:
        if exc.name != __package__ + ".private_config":
            raise
        return os.environ.get(name, "").strip()
    return getattr(private_config, name, "").strip() or os.environ.get(name, "").strip()
