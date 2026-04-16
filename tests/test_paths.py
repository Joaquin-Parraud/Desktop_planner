"""Phase 1: XDG-compliant path resolution."""
from __future__ import annotations

from pathlib import Path

from desktop_planner import paths


def test_xdg_data_home_respects_env(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert paths.xdg_data_home() == tmp_path


def test_xdg_data_home_default_when_unset(monkeypatch):
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert paths.xdg_data_home() == Path.home() / ".local" / "share"


def test_app_data_dir_creates(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    d = paths.app_data_dir("desktop-planner-test")
    assert d.exists() and d.is_dir()
    assert d == tmp_path / "desktop-planner-test"


def test_database_path_under_app_data(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    p = paths.database_path("desktop-planner-test")
    assert p.parent.exists()
    assert p.name == "planner.db"
