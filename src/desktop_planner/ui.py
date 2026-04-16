"""GTK4 + Libadwaita UI for the Desktop Planner.

This module imports GTK lazily on first use so unit tests for the data
layer can run on systems without GTK4 installed.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gio, Gtk  # noqa: E402

from . import APP_ID
from .database import Database
from .dates import format_relative
from .models import Group, Task
from .notifications import notify_tasks_due_today


SIDEBAR_ALL_ID = -1  # synthetic "All Tasks" row id


class TaskRow(Gtk.ListBoxRow):
    """A row showing checkbox + title + due-date pill."""

    def __init__(self, task: Task, on_toggle):
        super().__init__()
        self.task = task

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(12)
        box.set_margin_end(12)

        self.check = Gtk.CheckButton()
        self.check.set_active(task.completed)
        self.check.connect("toggled", lambda btn: on_toggle(task, btn.get_active()))
        box.append(self.check)

        title = Gtk.Label(label=task.title, xalign=0)
        title.set_hexpand(True)
        title.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        if task.completed:
            title.add_css_class("dim-label")
        box.append(title)

        due_text = format_relative(task.due_date)
        if due_text:
            pill = Gtk.Label(label=due_text)
            pill.add_css_class("caption")
            pill.add_css_class("dim-label")
            box.append(pill)

        self.set_child(box)


class GroupRow(Gtk.ListBoxRow):
    def __init__(self, group_id: int, name: str, color: Optional[str] = None):
        super().__init__()
        self.group_id = group_id

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(12)
        box.set_margin_end(12)

        if color:
            swatch = Gtk.DrawingArea()
            swatch.set_content_width(12)
            swatch.set_content_height(12)
            swatch.set_draw_func(_make_color_draw(color))
            box.append(swatch)

        label = Gtk.Label(label=name, xalign=0)
        label.set_hexpand(True)
        box.append(label)

        self.set_child(box)


def _make_color_draw(hex_color: str):
    r, g, b = _hex_to_rgb(hex_color)

    def draw(_area, cr, w, h):
        cr.set_source_rgb(r, g, b)
        cr.arc(w / 2, h / 2, min(w, h) / 2, 0, 6.283185307)
        cr.fill()

    return draw


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    v = value.lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    r = int(v[0:2], 16) / 255
    g = int(v[2:4], 16) / 255
    b = int(v[4:6], 16) / 255
    return r, g, b


class TaskEditor(Adw.Window):
    """Modal dialog: title entry + Gtk.Calendar + group dropdown."""

    def __init__(self, parent: Gtk.Window, db: Database, task: Optional[Task] = None,
                 default_group_id: Optional[int] = None):
        super().__init__(transient_for=parent, modal=True)
        self.set_title("Edit Task" if task else "New Task")
        self.set_default_size(420, 520)
        self.db = db
        self.task = task
        self.saved = False

        header = Adw.HeaderBar()
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda *_: self.close())
        header.pack_start(cancel_btn)
        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save)
        header.pack_end(save_btn)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        self.title_entry = Gtk.Entry()
        self.title_entry.set_placeholder_text("Task title")
        if task:
            self.title_entry.set_text(task.title)
        content.append(_labelled("Title", self.title_entry))

        self.calendar = Gtk.Calendar()
        if task and task.due_date:
            self._set_calendar_date(task.due_date)
        content.append(_labelled("Due date", self.calendar))

        no_date_btn = Gtk.CheckButton(label="No due date")
        self.no_date_btn = no_date_btn
        no_date_btn.set_active(task is not None and task.due_date is None)
        content.append(no_date_btn)

        self.groups = db.list_groups()
        self.group_dropdown = Gtk.DropDown.new_from_strings(
            ["(no group)"] + [g.name for g in self.groups]
        )
        selected_idx = 0
        target_gid = task.group_id if task else default_group_id
        if target_gid is not None:
            for i, g in enumerate(self.groups, start=1):
                if g.id == target_gid:
                    selected_idx = i
                    break
        self.group_dropdown.set_selected(selected_idx)
        content.append(_labelled("Group", self.group_dropdown))

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(header)
        outer.append(content)
        self.set_content(outer)

        self.title_entry.grab_focus()

    def _set_calendar_date(self, value: date) -> None:
        glib_dt = GLib.DateTime.new_local(value.year, value.month, value.day, 0, 0, 0)
        self.calendar.select_day(glib_dt)

    def _read_calendar_date(self) -> Optional[date]:
        if self.no_date_btn.get_active():
            return None
        gdate = self.calendar.get_date()
        return date(gdate.get_year(), gdate.get_month(), gdate.get_day_of_month())

    def _selected_group_id(self) -> Optional[int]:
        idx = self.group_dropdown.get_selected()
        if idx == 0:
            return None
        return self.groups[idx - 1].id

    def _on_save(self, *_):
        title = self.title_entry.get_text().strip()
        if not title:
            self.title_entry.grab_focus()
            return
        due = self._read_calendar_date()
        gid = self._selected_group_id()
        if self.task is None:
            self.db.create_task(title=title, group_id=gid, due_date=due)
        else:
            self.task.title = title
            self.task.due_date = due
            self.task.group_id = gid
            self.db.update_task(self.task)
        self.saved = True
        self.close()


def _labelled(label: str, child: Gtk.Widget) -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    lbl = Gtk.Label(label=label, xalign=0)
    lbl.add_css_class("dim-label")
    lbl.add_css_class("caption")
    box.append(lbl)
    box.append(child)
    return box


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, db: Database):
        super().__init__(application=app)
        self.db = db
        self.set_title("Desktop Planner")
        self.set_default_size(900, 600)
        self.selected_group_id: Optional[int] = None  # None = all
        self.sort_by_date = False

        # Header bar with actions
        header = Adw.HeaderBar()
        add_btn = Gtk.Button(icon_name="list-add-symbolic")
        add_btn.set_tooltip_text("New task (Ctrl+N)")
        add_btn.connect("clicked", lambda *_: self.open_task_editor())
        header.pack_start(add_btn)

        new_group_btn = Gtk.Button(icon_name="folder-new-symbolic")
        new_group_btn.set_tooltip_text("New group")
        new_group_btn.connect("clicked", lambda *_: self.open_new_group_dialog())
        header.pack_start(new_group_btn)

        self.sort_toggle = Gtk.ToggleButton(icon_name="view-sort-ascending-symbolic")
        self.sort_toggle.set_tooltip_text("Sort by due date")
        self.sort_toggle.connect("toggled", self._on_sort_toggled)
        header.pack_end(self.sort_toggle)

        # Layout: sidebar + tasks
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(220)
        paned.set_vexpand(True)

        # Sidebar
        sidebar_scroll = Gtk.ScrolledWindow()
        self.sidebar = Gtk.ListBox()
        self.sidebar.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.sidebar.connect("row-selected", self._on_sidebar_selected)
        sidebar_scroll.set_child(self.sidebar)
        paned.set_start_child(sidebar_scroll)

        # Task list
        list_scroll = Gtk.ScrolledWindow()
        list_scroll.set_hexpand(True)
        self.task_list = Gtk.ListBox()
        self.task_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.task_list.connect("row-activated", self._on_task_activated)
        self.empty_status = Adw.StatusPage(
            icon_name="checkbox-checked-symbolic",
            title="No tasks",
            description="Press the + button to add a task.",
        )
        self.task_stack = Gtk.Stack()
        self.task_stack.add_named(list_scroll, "list")
        self.task_stack.add_named(self.empty_status, "empty")
        list_scroll.set_child(self.task_list)
        paned.set_end_child(self.task_stack)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(header)
        outer.append(paned)
        self.set_content(outer)

        # Keyboard: Ctrl+N for new task
        controller = Gtk.ShortcutController()
        shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control>n"),
            Gtk.CallbackAction.new(lambda *_: (self.open_task_editor(), True)[1]),
        )
        controller.add_shortcut(shortcut)
        self.add_controller(controller)

        self.refresh_sidebar()
        self.refresh_tasks()

    # ----- data refresh -------------------------------------------------
    def refresh_sidebar(self) -> None:
        self.sidebar.remove_all()
        all_row = GroupRow(SIDEBAR_ALL_ID, "All Tasks")
        self.sidebar.append(all_row)
        for g in self.db.list_groups():
            self.sidebar.append(GroupRow(g.id, g.name, g.color))
        # restore selection
        target = SIDEBAR_ALL_ID if self.selected_group_id is None else self.selected_group_id
        i = 0
        while True:
            row = self.sidebar.get_row_at_index(i)
            if row is None:
                break
            if isinstance(row, GroupRow) and row.group_id == target:
                self.sidebar.select_row(row)
                break
            i += 1
        if self.sidebar.get_selected_row() is None:
            self.sidebar.select_row(all_row)

    def refresh_tasks(self) -> None:
        self.task_list.remove_all()
        tasks = self.db.list_tasks(
            group_id=self.selected_group_id, sort_by_date=self.sort_by_date
        )
        for t in tasks:
            self.task_list.append(TaskRow(t, self._on_task_toggle))
        self.task_stack.set_visible_child_name("list" if tasks else "empty")

    # ----- handlers -----------------------------------------------------
    def _on_sidebar_selected(self, _box, row):
        if row is None:
            return
        self.selected_group_id = None if row.group_id == SIDEBAR_ALL_ID else row.group_id
        self.refresh_tasks()

    def _on_sort_toggled(self, btn: Gtk.ToggleButton) -> None:
        self.sort_by_date = btn.get_active()
        self.refresh_tasks()

    def _on_task_toggle(self, task: Task, completed: bool) -> None:
        self.db.set_task_completed(task.id, completed)
        self.refresh_tasks()

    def _on_task_activated(self, _box, row: TaskRow) -> None:
        self.open_task_editor(row.task)

    def open_task_editor(self, task: Optional[Task] = None) -> None:
        editor = TaskEditor(
            self, self.db, task=task, default_group_id=self.selected_group_id
        )
        editor.connect("close-request", lambda *_: (self.refresh_tasks(), False)[1])
        editor.present()

    def open_new_group_dialog(self) -> None:
        dlg = Adw.Window(transient_for=self, modal=True)
        dlg.set_title("New Group")
        dlg.set_default_size(320, 160)

        header = Adw.HeaderBar()
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda *_: dlg.close())
        save = Gtk.Button(label="Create")
        save.add_css_class("suggested-action")
        header.pack_start(cancel)
        header.pack_end(save)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        body.set_margin_top(12)
        body.set_margin_bottom(12)
        body.set_margin_start(12)
        body.set_margin_end(12)
        entry = Gtk.Entry(placeholder_text="Group name")
        body.append(entry)
        color_entry = Gtk.Entry(text="#3584e4")
        body.append(_labelled("Color (hex)", color_entry))

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(header)
        outer.append(body)
        dlg.set_content(outer)

        def do_save(*_):
            name = entry.get_text().strip()
            if not name:
                entry.grab_focus()
                return
            try:
                self.db.create_group(name, color_entry.get_text().strip() or "#3584e4")
            except Exception:
                entry.grab_focus()
                return
            self.refresh_sidebar()
            dlg.close()

        save.connect("clicked", do_save)
        entry.connect("activate", do_save)
        dlg.present()


class PlannerApp(Adw.Application):
    def __init__(self, db: Optional[Database] = None):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self._injected_db = db
        self._db: Optional[Database] = None
        self._window: Optional[MainWindow] = None

    def do_activate(self):
        if self._db is None:
            self._db = self._injected_db or Database()
        if self._window is None:
            self._window = MainWindow(self, self._db)
        self._window.present()
        # Fire today's notifications once at startup
        try:
            notify_tasks_due_today(self._db.tasks_due_on(date.today()))
        except Exception:
            pass

    def do_shutdown(self):
        if self._db is not None:
            self._db.close()
        Adw.Application.do_shutdown(self)
