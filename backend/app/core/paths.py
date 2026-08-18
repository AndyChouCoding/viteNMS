"""Base directory for persistent runtime state (DB, logs, encrypted
credential store).

In dev this is the backend/ package directory, same as the previous
__file__-relative paths in db.py/logging.py/credential_store.py. When
frozen by PyInstaller (onefile mode, see backend/pyinstaller/backend.spec),
__file__ resolves inside that run's temp extraction directory instead of a
stable location — anything written there is gone the moment the process
exits, silently wiping accounts/logs/credentials on every restart. Frozen
builds instead use the OS's per-user local app data directory, which
persists across runs.
"""

import os
import sys
from pathlib import Path

_APP_DIR_NAME = "open-vision-vite"


def _app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / _APP_DIR_NAME
        return Path.home() / f".{_APP_DIR_NAME}"
    return Path(__file__).resolve().parent.parent.parent


BASE_DIR = _app_base_dir()
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
