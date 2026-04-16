"""XDG-compliant path resolution for application data."""
from __future__ import annotations

import os
from pathlib import Path


def xdg_data_home() -> Path:
    raw = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(raw)


def app_data_dir(app_name: str = "desktop-planner") -> Path:
    path = xdg_data_home() / app_name
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path(app_name: str = "desktop-planner") -> Path:
    return app_data_dir(app_name) / "planner.db"
