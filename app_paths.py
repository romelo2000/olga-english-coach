"""Resource path helpers for both development and PyInstaller builds.

In development: resources live next to this file (Contents/Resources).
In PyInstaller bundle: resources are extracted to sys._MEIPASS.
"""

from __future__ import annotations

import sys
from pathlib import Path


def get_resources_dir() -> Path:
    """Return the directory containing bundled resources."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def get_app_dir() -> Path:
    """Return the .app directory (or project root in development)."""
    resources = get_resources_dir()
    # In development: Resources/ → Contents/ → .app/
    if resources.name == "Resources":
        return resources.parent.parent
    return resources.parent


def get_user_data_dir() -> Path:
    """Return the per-user data directory."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "OlgaEnglishCoach"
    else:
        base = Path.home() / ".OlgaEnglishCoach"
    base.mkdir(parents=True, exist_ok=True)
    return base
