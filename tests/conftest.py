"""Shared pytest fixtures."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from desktop_planner.database import Database  # noqa: E402


@pytest.fixture()
def db(tmp_path) -> Database:
    """An isolated, file-backed database under a tmp dir."""
    path = tmp_path / "planner.db"
    database = Database(path)
    yield database
    database.close()
