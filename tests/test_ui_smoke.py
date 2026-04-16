"""Phase 1 + Phase 3 smoke test: import UI module and instantiate the app.

Skipped automatically on systems without GTK4 / Libadwaita installed.
"""
from __future__ import annotations

import pytest

gtk_missing = False
try:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gtk  # noqa: F401
except (ImportError, ValueError):
    gtk_missing = True

pytestmark = pytest.mark.skipif(
    gtk_missing, reason="GTK4 / Libadwaita not available on this system"
)


def test_can_import_ui_module():
    from desktop_planner import ui  # noqa: F401


def test_can_construct_app(db):
    from desktop_planner.ui import PlannerApp

    app = PlannerApp(db=db)
    assert app.get_application_id() == "org.example.DesktopPlanner"


def test_main_window_renders_tasks(db):
    from desktop_planner.ui import MainWindow, PlannerApp

    g = db.create_group("Work")
    db.create_task("Write tests", group_id=g.id, due_date="2026-04-20")
    db.create_task("Ship it")

    app = PlannerApp(db=db)
    win = MainWindow(app, db)
    # Sidebar = "All Tasks" + 1 group = 2 rows
    assert win.sidebar.get_row_at_index(0) is not None
    assert win.sidebar.get_row_at_index(1) is not None
    assert win.sidebar.get_row_at_index(2) is None
    # Task list shows both tasks
    assert win.task_list.get_row_at_index(0) is not None
    assert win.task_list.get_row_at_index(1) is not None
