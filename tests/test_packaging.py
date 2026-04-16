"""Phase 5: distribution artefacts are present and well-formed."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_desktop_entry_present_and_valid():
    p = ROOT / "packaging" / "org.example.DesktopPlanner.desktop"
    assert p.exists()
    text = p.read_text()
    assert "[Desktop Entry]" in text
    assert "Exec=desktop-planner" in text
    assert "Icon=org.example.DesktopPlanner" in text
    assert "Type=Application" in text


def test_icon_is_svg():
    p = ROOT / "packaging" / "org.example.DesktopPlanner.svg"
    assert p.exists()
    assert p.read_text().lstrip().startswith("<?xml")


def test_meson_build_lists_sources():
    text = (ROOT / "meson.build").read_text()
    for src in ("database.py", "ui.py", "models.py", "__main__.py"):
        assert src in text


def test_appimage_script_executable():
    p = ROOT / "packaging" / "build_appimage.sh"
    assert p.exists()
    assert p.stat().st_mode & 0o111  # any execute bit set


def test_flatpak_manifest_present():
    p = ROOT / "packaging" / "org.example.DesktopPlanner.flatpak.yml"
    assert p.exists()
    text = p.read_text()
    assert "app-id: org.example.DesktopPlanner" in text
    assert "command: desktop-planner" in text
