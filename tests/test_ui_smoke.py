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
    from desktop_planner.ui import (
        MainWindow,
        PlannerApp,
        SidebarHeaderRow,
        SidebarTasksRow,
    )

    g = db.create_group("Work")
    db.create_task("Write tests", group_id=g.id, due_date="2026-04-20")
    db.create_task("Ship it")

    app = PlannerApp(db=db)
    win = MainWindow(app, db)
    # Sidebar layout: All-Tasks header, then per group (header + tasks-row).
    rows = []
    i = 0
    while True:
        r = win.sidebar.get_row_at_index(i)
        if r is None:
            break
        rows.append(r)
        i += 1
    assert isinstance(rows[0], SidebarHeaderRow)
    assert rows[0].group_id == -1  # SIDEBAR_ALL_ID
    assert isinstance(rows[1], SidebarHeaderRow)
    assert rows[1].group_id == g.id
    assert isinstance(rows[2], SidebarTasksRow)
    # Task list shows both tasks
    assert win.task_list.get_row_at_index(0) is not None
    assert win.task_list.get_row_at_index(1) is not None
    assert win.task_list.get_row_at_index(2) is None


def test_collapse_toggle_hides_tasks_row(db):
    from desktop_planner.ui import MainWindow, PlannerApp

    g = db.create_group("G1")
    db.create_task("t", group_id=g.id)
    app = PlannerApp(db=db)
    win = MainWindow(app, db)

    tasks_row = win._tasks_rows[g.id]
    assert tasks_row.revealer.get_reveal_child() is True

    win._on_toggle_collapse(g.id, expanded=False)
    assert tasks_row.revealer.get_reveal_child() is False
    assert g.id in win._collapsed_groups

    win._on_toggle_collapse(g.id, expanded=True)
    assert tasks_row.revealer.get_reveal_child() is True
    assert g.id not in win._collapsed_groups


def test_drop_handler_moves_task_between_groups(db):
    from desktop_planner.ui import MainWindow, PlannerApp

    src = db.create_group("Src")
    dst = db.create_group("Dst")
    t = db.create_task("move me", group_id=src.id)
    app = PlannerApp(db=db)
    win = MainWindow(app, db)

    win._on_drop_task(t.id, dst.id)
    assert db.get_task(t.id).group_id == dst.id

    win._on_drop_task(t.id, None)
    assert db.get_task(t.id).group_id is None


def test_delete_handler_removes_task(db):
    from desktop_planner.ui import MainWindow, PlannerApp

    t = db.create_task("delete me")
    app = PlannerApp(db=db)
    win = MainWindow(app, db)
    win._on_task_delete(t)
    assert db.get_task(t.id) is None
    assert win.task_list.get_row_at_index(0) is None


def test_task_row_description_default_collapsed(db):
    from desktop_planner.ui import MainWindow, PlannerApp, TaskRow

    db.create_task("with notes", description="hidden by default")
    app = PlannerApp(db=db)
    win = MainWindow(app, db)
    row = win.task_list.get_row_at_index(0)
    assert isinstance(row, TaskRow)
    assert row.desc_revealer is not None
    assert row.desc_revealer.get_reveal_child() is False
    assert row.expand_btn is not None
    row.expand_btn.set_active(True)
    assert row.desc_revealer.get_reveal_child() is True


def test_task_row_no_revealer_when_no_description(db):
    from desktop_planner.ui import MainWindow, PlannerApp, TaskRow

    db.create_task("plain")
    app = PlannerApp(db=db)
    win = MainWindow(app, db)
    row = win.task_list.get_row_at_index(0)
    assert isinstance(row, TaskRow)
    assert row.desc_revealer is None
    assert row.expand_btn is None


def test_request_add_task_targets_group(db, monkeypatch):
    from desktop_planner.ui import MainWindow, PlannerApp

    g = db.create_group("Work")
    app = PlannerApp(db=db)
    win = MainWindow(app, db)

    captured = {}

    def fake_open_task_editor(*_args, **_kwargs):
        captured["selected"] = win.selected_group_id

    monkeypatch.setattr(win, "open_task_editor", fake_open_task_editor)
    win.selected_group_id = None
    win._on_request_add_task(g.id)
    assert captured["selected"] == g.id
    # selection restored after the call
    assert win.selected_group_id is None


def test_calendar_view_marks_days_with_group_colors(db):
    from datetime import date as _date

    from desktop_planner.ui import CalendarView

    g1 = db.create_group("A", color="#ff0000")
    g2 = db.create_group("B", color="#00ff00")
    target = _date(2026, 4, 16)
    db.create_task("a-task", group_id=g1.id, due_date=target)
    db.create_task("b-task", group_id=g2.id, due_date=target)
    db.create_task("dup", group_id=g1.id, due_date=target)
    db.create_task("ungrouped", due_date=target)
    db.create_task("other-day", group_id=g1.id, due_date=_date(2026, 4, 18))

    cal = CalendarView(db)
    cal.current = target.replace(day=1)
    cal.refresh()
    # The grid should contain a label for "April 2026"
    assert "April" in cal.month_label.get_text()
    assert "2026" in cal.month_label.get_text()
