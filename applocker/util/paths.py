"""Path utilities for Aegis.

Centralizes where the application stores its data, config, logs and cache.
Uses a single versioned application-data directory so upgrades and
uninstalls behave predictably. All paths are per-user (LOCALAPPDATA) so the
app does not need to write to Program Files.
"""

from __future__ import annotations

import os
import sys

from applocker.version import APP_NAME


def get_platform_data_dir() -> str:
    """Return the per-user application data directory (versioned)."""
    appdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    base = os.path.join(appdata, APP_NAME, "Data")
    os.makedirs(base, exist_ok=True)
    return base


def get_log_dir() -> str:
    base = os.path.join(get_platform_data_dir(), "logs")
    os.makedirs(base, exist_ok=True)
    return base


def get_cache_dir() -> str:
    base = os.path.join(get_platform_data_dir(), "cache")
    os.makedirs(base, exist_ok=True)
    return base


def get_icon_cache_dir() -> str:
    base = os.path.join(get_cache_dir(), "icons")
    os.makedirs(base, exist_ok=True)
    return base


def get_db_path() -> str:
    return os.path.join(get_platform_data_dir(), "applocker.db")


def get_secrets_path() -> str:
    return os.path.join(get_platform_data_dir(), "secrets.bin")


def get_config_path() -> str:
    return os.path.join(get_platform_data_dir(), "config.json")


def resource_path(relative: str) -> str:
    """Return an absolute path to a resource, working under PyInstaller.

    When frozen, bundled files live under ``_MEIPASS``.
    """
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        return os.path.join(base, relative)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), relative)
