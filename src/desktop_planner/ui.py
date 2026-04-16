"""GTK4 + Libadwaita UI for the Desktop Planner."""
from __future__ import annotations

from datetime import date, time
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, GObject, Gio, Gtk  # noqa: E402

from . import APP_ID
from .database import Database
from .dates import format_relative
from .models import Group, Task
from .notifications import notify_tasks_due_today


SIDEBAR_ALL_ID = -1  # synthetic "All Tasks" id used by sidebar headers


# ---------------------------------------------------------------------------
# Drag-and-drop helpers
# ---------------------------------------------------------------------------
DND_TASK_KEY = "x-desktop-planner-task-id"


def _make_task_drag_source(task: Task) -> Gtk.DragSource:
    src = Gtk.DragSource()
    src.set_actions(Gdk.DragAction.MOVE)

    def _prepare(_source, _x, _y):
        value = GObject.Value()
        value.init(GObject.TYPE_INT64)
        value.set_int64(task.id or 0)
        return Gdk.ContentProvider.new_for_value(value)

    src.connect("prepare", _prepare)
    return src


def _make_group_drop_target(target_group_id: Optional[int], on_drop) -> Gtk.DropTarget:
    target = Gtk.DropTarget.new(GObject.TYPE_INT64, Gdk.DragAction.MOVE)

    def _on_drop(_target, value, _x, _y):
        try:
            tid = int(value)
        except (TypeError, ValueError):
            return False
        if tid <= 0:
            return False
        on_drop(tid, target_group_id)
        return True

    target.connect("drop", _on_drop)
    return target


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------
def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    v = value.lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    r = int(v[0:2], 16) / 255
    g = int(v[2:4], 16) / 255
    b = int(v[4:6], 16) / 255
    return r, g, b


def _hex_to_rgba(hex_color: str) -> Gdk.RGBA:
    r, g, b = _hex_to_rgb(hex_color)
    rgba = Gdk.RGBA()
    rgba.red = r
    rgba.green = g
    rgba.blue = b
    rgba.alpha = 1.0
    return rgba


def _rgba_to_hex(rgba: Gdk.RGBA) -> str:
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, int(round(rgba.red * 255)))),
        max(0, min(255, int(round(rgba.green * 255)))),
        max(0, min(255, int(round(rgba.blue * 255)))),
    )


def _make_color_draw(hex_color: str, *, shape: str = "circle"):
    r, g, b = _hex_to_rgb(hex_color)

    def draw(_area, cr, w, h):
        cr.set_source_rgb(r, g, b)
        if shape == "square":
            cr.rectangle(0, 0, w, h)
            cr.fill()
        else:
            cr.arc(w / 2, h / 2, min(w, h) / 2, 0, 6.283185307)
            cr.fill()

    return draw


# ---------------------------------------------------------------------------
# Task row
# ---------------------------------------------------------------------------
class TaskRow(Gtk.ListBoxRow):
    """A task row: checkbox + title (strikethrough when done) + date/time +
    collapsible description (default collapsed) + delete."""

    def __init__(self, task: Task, on_toggle, on_delete):
        super().__init__()
        self.task = task

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        outer.set_margin_top(6)
        outer.set_margin_bottom(6)
        outer.set_margin_start(12)
        outer.set_margin_end(12)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        self.check = Gtk.CheckButton()
        self.check.set_active(task.completed)
        self.check.connect("toggled", lambda btn: on_toggle(task, btn.get_active()))
        top.append(self.check)

        title_text = GLib.markup_escape_text(task.title)
        if task.completed:
            title_text = f"<s>{title_text}</s>"
        title = Gtk.Label(xalign=0)
        title.set_markup(title_text)
        title.set_hexpand(True)
        title.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        if task.completed:
            title.add_css_class("dim-label")
        top.append(title)

        # Date stacked above time
        if task.due_date is not None or task.due_time is not None:
            stack = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            stack.set_valign(Gtk.Align.CENTER)
            rel = format_relative(task.due_date) if task.due_date else ""
            if rel:
                d_lbl = Gtk.Label(label=rel, xalign=1)
                d_lbl.add_css_class("caption")
                d_lbl.add_css_class("dim-label")
                stack.append(d_lbl)
            if task.due_time is not None:
                t_lbl = Gtk.Label(label=task.due_time.strftime("%H:%M"), xalign=1)
                t_lbl.add_css_class("caption")
                t_lbl.add_css_class("dim-label")
                stack.append(t_lbl)
            top.append(stack)

        # Description revealer (default collapsed)
        self.desc_revealer: Optional[Gtk.Revealer] = None
        self.expand_btn: Optional[Gtk.ToggleButton] = None
        if task.description:
            self.desc_revealer = Gtk.Revealer()
            self.desc_revealer.set_reveal_child(False)
            self.desc_revealer.set_transition_type(
                Gtk.RevealerTransitionType.SLIDE_DOWN
            )
            desc_lbl = Gtk.Label(label=task.description, xalign=0)
            desc_lbl.set_wrap(True)
            desc_lbl.add_css_class("caption")
            desc_lbl.add_css_class("dim-label")
            desc_lbl.set_margin_start(34)
            desc_lbl.set_margin_top(2)
            desc_lbl.set_margin_bottom(2)
            self.desc_revealer.set_child(desc_lbl)

            self.expand_btn = Gtk.ToggleButton(icon_name="pan-end-symbolic")
            self.expand_btn.add_css_class("flat")
            self.expand_btn.set_tooltip_text("Toggle description")

            def _on_expand_toggled(btn):
                shown = btn.get_active()
                self.desc_revealer.set_reveal_child(shown)
                btn.set_icon_name("pan-down-symbolic" if shown else "pan-end-symbolic")

            self.expand_btn.connect("toggled", _on_expand_toggled)
            top.append(self.expand_btn)

        delete_btn = Gtk.Button(icon_name="user-trash-symbolic")
        delete_btn.add_css_class("flat")
        delete_btn.set_tooltip_text("Delete task")
        delete_btn.connect("clicked", lambda *_: on_delete(task))
        top.append(delete_btn)

        outer.append(top)
        if self.desc_revealer is not None:
            outer.append(self.desc_revealer)
        self.set_child(outer)

        if task.id is not None:
            self.add_controller(_make_task_drag_source(task))


# ---------------------------------------------------------------------------
# Sidebar: collapsible groups
# ---------------------------------------------------------------------------
class SidebarHeaderRow(Gtk.ListBoxRow):
    """A clickable row (filter by group) with optional disclosure triangle.

    Right-click on a group header opens a new-task editor pre-filled with that
    group.
    """

    def __init__(
        self,
        *,
        group_id: int,
        name: str,
        color: Optional[str] = None,
        description: str = "",
        collapsible: bool,
        on_toggle_collapse=None,
        on_edit=None,
        on_drop_task=None,
        on_request_add=None,
    ):
        super().__init__()
        self.group_id = group_id
        self.expanded = True

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(8)
        box.set_margin_end(8)

        self.triangle = Gtk.Image.new_from_icon_name("pan-down-symbolic")
        if not collapsible:
            self.triangle.set_opacity(0.0)
        box.append(self.triangle)

        if color:
            swatch = Gtk.DrawingArea()
            swatch.set_content_width(12)
            swatch.set_content_height(12)
            swatch.set_draw_func(_make_color_draw(color))
            box.append(swatch)

        self.label = Gtk.Label(label=name, xalign=0)
        self.label.set_hexpand(True)
        if description:
            self.set_tooltip_text(description)
        box.append(self.label)

        if on_edit is not None:
            edit_btn = Gtk.Button(icon_name="document-edit-symbolic")
            edit_btn.add_css_class("flat")
            edit_btn.set_tooltip_text("Edit group")
            edit_btn.connect("clicked", lambda *_: on_edit(group_id))
            box.append(edit_btn)

        self.set_child(box)

        if collapsible and on_toggle_collapse is not None:
            click = Gtk.GestureClick()
            click.set_button(1)

            def _on_pressed(gesture, _n_press, x, _y):
                if x <= 24:
                    self._set_expanded(not self.expanded)
                    on_toggle_collapse(group_id, self.expanded)
                    gesture.set_state(Gtk.EventSequenceState.CLAIMED)

            click.connect("pressed", _on_pressed)
            self.triangle.add_controller(click)

        if on_drop_task is not None:
            self.add_controller(
                _make_group_drop_target(
                    None if group_id == SIDEBAR_ALL_ID else group_id, on_drop_task
                )
            )

        if on_request_add is not None:
            rclick = Gtk.GestureClick()
            rclick.set_button(3)
            payload_gid = None if group_id == SIDEBAR_ALL_ID else group_id

            def _on_right_pressed(gesture, _n, _x, _y):
                on_request_add(payload_gid)
                gesture.set_state(Gtk.EventSequenceState.CLAIMED)

            rclick.connect("pressed", _on_right_pressed)
            self.add_controller(rclick)

    def _set_expanded(self, expanded: bool) -> None:
        self.expanded = expanded
        self.triangle.set_from_icon_name(
            "pan-down-symbolic" if expanded else "pan-end-symbolic"
        )


class SidebarTasksRow(Gtk.ListBoxRow):
    """A non-selectable row holding the collapsible task list of a group."""

    def __init__(self, tasks: list[Task], on_task_activated):
        super().__init__()
        self.set_selectable(False)
        self.set_activatable(False)
        self.revealer = Gtk.Revealer()
        self.revealer.set_reveal_child(True)
        self.revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_start(36)
        box.set_margin_end(8)
        box.set_margin_bottom(4)
        for t in tasks:
            btn = Gtk.Button(label=t.title)
            btn.add_css_class("flat")
            btn.set_halign(Gtk.Align.START)
            if t.completed:
                btn.add_css_class("dim-label")
            btn.connect("clicked", lambda _b, task=t: on_task_activated(task))
            box.append(btn)
        if not tasks:
            empty = Gtk.Label(label="(empty)", xalign=0)
            empty.add_css_class("caption")
            empty.add_css_class("dim-label")
            box.append(empty)

        self.revealer.set_child(box)
        self.set_child(self.revealer)

    def set_revealed(self, revealed: bool) -> None:
        self.revealer.set_reveal_child(revealed)


# ---------------------------------------------------------------------------
# Calendar view (custom grid; default collapsed via popover)
# ---------------------------------------------------------------------------
class CalendarView(Gtk.Box):
    """Month grid that highlights days with tasks via per-group colored squares."""

    WEEKDAY_LABELS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    MAX_SQUARES = 5

    def __init__(self, db: Database):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.db = db
        today = date.today()
        self.current = today.replace(day=1)
        self.set_margin_top(8)
        self.set_margin_bottom(8)
        self.set_margin_start(8)
        self.set_margin_end(8)

        nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        prev = Gtk.Button(icon_name="pan-start-symbolic")
        prev.add_css_class("flat")
        prev.connect("clicked", lambda *_: self._shift(-1))
        self.month_label = Gtk.Label()
        self.month_label.set_hexpand(True)
        self.month_label.add_css_class("heading")
        nxt = Gtk.Button(icon_name="pan-end-symbolic")
        nxt.add_css_class("flat")
        nxt.connect("clicked", lambda *_: self._shift(1))
        nav.append(prev)
        nav.append(self.month_label)
        nav.append(nxt)
        self.append(nav)

        self.grid = Gtk.Grid()
        self.grid.set_row_spacing(2)
        self.grid.set_column_spacing(2)
        self.append(self.grid)

        self.refresh()

    def _shift(self, months: int) -> None:
        y, m = self.current.year, self.current.month + months
        while m > 12:
            y += 1
            m -= 12
        while m < 1:
            y -= 1
            m += 12
        self.current = date(y, m, 1)
        self.refresh()

    def refresh(self) -> None:
        # Clear existing children
        child = self.grid.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.grid.remove(child)
            child = nxt

        self.month_label.set_text(self.current.strftime("%B %Y"))

        for i, name in enumerate(self.WEEKDAY_LABELS):
            lbl = Gtk.Label(label=name)
            lbl.add_css_class("caption")
            lbl.add_css_class("dim-label")
            self.grid.attach(lbl, i, 0, 1, 1)

        groups = {g.id: g for g in self.db.list_groups()}
        first = self.current
        weekday = first.weekday()  # Mon=0
        if first.month == 12:
            next_month = first.replace(year=first.year + 1, month=1)
        else:
            next_month = first.replace(month=first.month + 1)
        days_in_month = (next_month - first).days

        day_colors: dict[int, list[str]] = {}
        for d in range(1, days_in_month + 1):
            tasks_today = self.db.tasks_due_on(first.replace(day=d))
            colors: list[str] = []
            seen_gids: set[int] = set()
            for t in tasks_today:
                if t.group_id is None or t.group_id in seen_gids:
                    continue
                g = groups.get(t.group_id)
                if g is not None:
                    colors.append(g.color)
                    seen_gids.add(t.group_id)
            if colors:
                day_colors[d] = colors

        today = date.today()
        row = 1
        col = weekday
        for d in range(1, days_in_month + 1):
            cell_date = first.replace(day=d)
            cell = self._make_day_cell(
                d,
                day_colors.get(d, []),
                is_today=(cell_date == today),
            )
            self.grid.attach(cell, col, row, 1, 1)
            col += 1
            if col == 7:
                col = 0
                row += 1

    def _make_day_cell(self, day: int, colors: list[str], *, is_today: bool):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_size_request(36, 40)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        lbl = Gtk.Label(label=str(day))
        lbl.add_css_class("caption")
        if is_today:
            lbl.add_css_class("accent")
            lbl.add_css_class("heading")
        box.append(lbl)
        if colors:
            swatches = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
            swatches.set_halign(Gtk.Align.CENTER)
            for c in colors[: self.MAX_SQUARES]:
                area = Gtk.DrawingArea()
                area.set_content_width(6)
                area.set_content_height(6)
                area.set_draw_func(_make_color_draw(c, shape="square"))
                swatches.append(area)
            box.append(swatches)
        return box


# ---------------------------------------------------------------------------
# Task editor
# ---------------------------------------------------------------------------
class TaskEditor(Adw.Window):
    def __init__(
        self,
        parent: Gtk.Window,
        db: Database,
        task: Optional[Task] = None,
        default_group_id: Optional[int] = None,
    ):
        super().__init__(transient_for=parent, modal=True)
        self.set_title("Edit Task" if task else "New Task")
        self.set_default_size(460, 640)
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

        self.desc_view = Gtk.TextView()
        self.desc_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.desc_view.set_top_margin(6)
        self.desc_view.set_bottom_margin(6)
        self.desc_view.set_left_margin(6)
        self.desc_view.set_right_margin(6)
        if task and task.description:
            self.desc_view.get_buffer().set_text(task.description)
        desc_scroll = Gtk.ScrolledWindow()
        desc_scroll.set_min_content_height(120)
        desc_scroll.set_child(self.desc_view)
        desc_scroll.add_css_class("card")
        content.append(_labelled("Description", desc_scroll))

        self.calendar = Gtk.Calendar()
        if task and task.due_date:
            self._set_calendar_date(task.due_date)
        content.append(_labelled("Due date", self.calendar))

        time_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.no_date_btn = Gtk.CheckButton(label="No due date")
        self.no_date_btn.set_active(task is not None and task.due_date is None)
        time_row.append(self.no_date_btn)
        time_row.append(Gtk.Label(label="Time:"))
        self.time_entry = Gtk.Entry()
        self.time_entry.set_placeholder_text("HH:MM")
        self.time_entry.set_max_width_chars(7)
        if task and task.due_time:
            self.time_entry.set_text(task.due_time.strftime("%H:%M"))
        time_row.append(self.time_entry)
        content.append(time_row)

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

    def _read_time(self) -> Optional[time]:
        text = self.time_entry.get_text().strip()
        if not text:
            return None
        try:
            return time.fromisoformat(text)
        except ValueError:
            return None

    def _selected_group_id(self) -> Optional[int]:
        idx = self.group_dropdown.get_selected()
        if idx == 0:
            return None
        return self.groups[idx - 1].id

    def _read_description(self) -> str:
        buf = self.desc_view.get_buffer()
        start, end = buf.get_bounds()
        return buf.get_text(start, end, False).strip()

    def _on_save(self, *_):
        title = self.title_entry.get_text().strip()
        if not title:
            self.title_entry.grab_focus()
            return
        due = self._read_calendar_date()
        gid = self._selected_group_id()
        t = self._read_time()
        desc = self._read_description()
        if self.task is None:
            self.db.create_task(
                title=title,
                group_id=gid,
                due_date=due,
                due_time=t,
                description=desc,
            )
        else:
            self.task.title = title
            self.task.due_date = due
            self.task.due_time = t
            self.task.group_id = gid
            self.task.description = desc
            self.db.update_task(self.task)
        self.saved = True
        self.close()


# ---------------------------------------------------------------------------
# Group editor (create + edit) with native color picker
# ---------------------------------------------------------------------------
class GroupEditor(Adw.Window):
    def __init__(self, parent: Gtk.Window, db: Database, group: Optional[Group] = None):
        super().__init__(transient_for=parent, modal=True)
        self.set_title("Edit Group" if group else "New Group")
        self.set_default_size(360, 320)
        self.db = db
        self.group = group
        self.saved = False
        self.deleted = False

        header = Adw.HeaderBar()
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda *_: self.close())
        header.pack_start(cancel)
        save = Gtk.Button(label="Save" if group else "Create")
        save.add_css_class("suggested-action")
        save.connect("clicked", self._on_save)
        header.pack_end(save)

        if group is not None:
            del_btn = Gtk.Button(icon_name="user-trash-symbolic")
            del_btn.add_css_class("destructive-action")
            del_btn.set_tooltip_text("Delete group")
            del_btn.connect("clicked", self._on_delete)
            header.pack_end(del_btn)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        body.set_margin_top(12)
        body.set_margin_bottom(12)
        body.set_margin_start(12)
        body.set_margin_end(12)

        self.name_entry = Gtk.Entry(placeholder_text="Group name")
        if group:
            self.name_entry.set_text(group.name)
        body.append(_labelled("Name", self.name_entry))

        self.color_btn = _make_color_chooser(group.color if group else "#3584e4")
        body.append(_labelled("Color", self.color_btn))

        self.desc_view = Gtk.TextView()
        self.desc_view.set_wrap_mode(Gtk.WrapMode.WORD)
        if group and group.description:
            self.desc_view.get_buffer().set_text(group.description)
        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(80)
        scroll.set_child(self.desc_view)
        scroll.add_css_class("card")
        body.append(_labelled("Description", scroll))

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(header)
        outer.append(body)
        self.set_content(outer)
        self.name_entry.grab_focus()

    def _read_description(self) -> str:
        buf = self.desc_view.get_buffer()
        start, end = buf.get_bounds()
        return buf.get_text(start, end, False).strip()

    def _read_color(self) -> str:
        return _rgba_to_hex(self.color_btn.get_rgba())

    def _on_save(self, *_):
        name = self.name_entry.get_text().strip()
        if not name:
            self.name_entry.grab_focus()
            return
        color = self._read_color()
        desc = self._read_description()
        try:
            if self.group is None:
                self.db.create_group(name, color, desc)
            else:
                self.group.name = name
                self.group.color = color
                self.group.description = desc
                self.db.update_group(self.group)
        except Exception:
            self.name_entry.grab_focus()
            return
        self.saved = True
        self.close()

    def _on_delete(self, *_):
        if self.group is None or self.group.id is None:
            return
        self.db.delete_group(self.group.id)
        self.deleted = True
        self.close()


def _make_color_chooser(initial_hex: str) -> Gtk.Widget:
    """Return a color-picker widget with .get_rgba() / .set_rgba() (Gtk 4.10+
    ColorDialogButton, falling back to ColorButton on older Gtk)."""
    rgba = _hex_to_rgba(initial_hex)
    if hasattr(Gtk, "ColorDialogButton"):
        dialog = Gtk.ColorDialog()
        dialog.set_with_alpha(False)
        btn = Gtk.ColorDialogButton.new(dialog)
        btn.set_rgba(rgba)
    else:
        btn = Gtk.ColorButton()
        btn.set_rgba(rgba)
    btn.set_halign(Gtk.Align.START)
    return btn


def _labelled(label: str, child: Gtk.Widget) -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    lbl = Gtk.Label(label=label, xalign=0)
    lbl.add_css_class("dim-label")
    lbl.add_css_class("caption")
    box.append(lbl)
    box.append(child)
    return box


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, db: Database):
        super().__init__(application=app)
        self.db = db
        self.set_title("Desktop Planner")
        self.set_default_size(960, 640)
        self.selected_group_id: Optional[int] = None  # None = all
        self.sort_by_date = False
        self._collapsed_groups: set[int] = set()
        self._tasks_rows: dict[int, SidebarTasksRow] = {}

        # Header bar
        header = Adw.HeaderBar()
        add_btn = Gtk.Button(icon_name="list-add-symbolic")
        add_btn.set_tooltip_text("New task (Ctrl+N)")
        add_btn.connect("clicked", lambda *_: self.open_task_editor())
        header.pack_start(add_btn)

        new_group_btn = Gtk.Button(icon_name="folder-new-symbolic")
        new_group_btn.set_tooltip_text("New group")
        new_group_btn.connect("clicked", lambda *_: self.open_group_editor(None))
        header.pack_start(new_group_btn)

        # Calendar popover (default collapsed; opens next to the group button)
        self.calendar_view = CalendarView(db)
        calendar_popover = Gtk.Popover()
        calendar_popover.set_child(self.calendar_view)
        calendar_btn = Gtk.MenuButton(icon_name="x-office-calendar-symbolic")
        calendar_btn.set_tooltip_text("Calendar view")
        calendar_btn.set_popover(calendar_popover)
        header.pack_start(calendar_btn)
        self._calendar_popover = calendar_popover

        self.sort_toggle = Gtk.ToggleButton(icon_name="view-sort-ascending-symbolic")
        self.sort_toggle.set_tooltip_text("Sort by due date")
        self.sort_toggle.connect("toggled", self._on_sort_toggled)
        header.pack_end(self.sort_toggle)

        # Layout: sidebar + tasks
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(260)
        paned.set_vexpand(True)

        sidebar_scroll = Gtk.ScrolledWindow()
        self.sidebar = Gtk.ListBox()
        self.sidebar.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.sidebar.connect("row-selected", self._on_sidebar_selected)
        sidebar_scroll.set_child(self.sidebar)
        paned.set_start_child(sidebar_scroll)

        list_scroll = Gtk.ScrolledWindow()
        list_scroll.set_hexpand(True)
        self.task_list = Gtk.ListBox()
        self.task_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.task_list.connect("row-activated", self._on_task_activated)
        list_scroll.set_child(self.task_list)

        self.empty_status = Adw.StatusPage(
            icon_name="checkbox-checked-symbolic",
            title="No tasks",
            description="Press the + button to add a task.",
        )
        self.task_stack = Gtk.Stack()
        self.task_stack.add_named(list_scroll, "list")
        self.task_stack.add_named(self.empty_status, "empty")
        paned.set_end_child(self.task_stack)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(header)
        outer.append(paned)
        self.set_content(outer)

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
        self._tasks_rows.clear()

        all_row = SidebarHeaderRow(
            group_id=SIDEBAR_ALL_ID,
            name="All Tasks",
            collapsible=False,
            on_drop_task=self._on_drop_task,
            on_request_add=self._on_request_add_task,
        )
        self.sidebar.append(all_row)

        for g in self.db.list_groups():
            tasks = self.db.list_tasks(group_id=g.id, sort_by_date=self.sort_by_date)
            header = SidebarHeaderRow(
                group_id=g.id,
                name=g.name,
                color=g.color,
                description=g.description,
                collapsible=True,
                on_toggle_collapse=self._on_toggle_collapse,
                on_edit=lambda gid=g.id: self.open_group_editor(gid),
                on_drop_task=self._on_drop_task,
                on_request_add=self._on_request_add_task,
            )
            tasks_row = SidebarTasksRow(tasks, on_task_activated=self._on_sidebar_task)
            self._tasks_rows[g.id] = tasks_row
            self.sidebar.append(header)
            self.sidebar.append(tasks_row)
            if g.id in self._collapsed_groups:
                header._set_expanded(False)
                tasks_row.set_revealed(False)

        target = (
            SIDEBAR_ALL_ID if self.selected_group_id is None else self.selected_group_id
        )
        i = 0
        while True:
            row = self.sidebar.get_row_at_index(i)
            if row is None:
                break
            if isinstance(row, SidebarHeaderRow) and row.group_id == target:
                self.sidebar.select_row(row)
                break
            i += 1
        if self.sidebar.get_selected_row() is None:
            self.sidebar.select_row(all_row)

        self.calendar_view.refresh()

    def refresh_tasks(self) -> None:
        self.task_list.remove_all()
        tasks = self.db.list_tasks(
            group_id=self.selected_group_id, sort_by_date=self.sort_by_date
        )
        for t in tasks:
            self.task_list.append(
                TaskRow(t, self._on_task_toggle, self._on_task_delete)
            )
        self.task_stack.set_visible_child_name("list" if tasks else "empty")

    def _on_sidebar_selected(self, _box, row):
        if row is None or not isinstance(row, SidebarHeaderRow):
            return
        self.selected_group_id = (
            None if row.group_id == SIDEBAR_ALL_ID else row.group_id
        )
        self.refresh_tasks()

    def _on_toggle_collapse(self, group_id: int, expanded: bool) -> None:
        if expanded:
            self._collapsed_groups.discard(group_id)
        else:
            self._collapsed_groups.add(group_id)
        tasks_row = self._tasks_rows.get(group_id)
        if tasks_row is not None:
            tasks_row.set_revealed(expanded)

    def _on_sort_toggled(self, btn: Gtk.ToggleButton) -> None:
        self.sort_by_date = btn.get_active()
        self.refresh_tasks()
        self.refresh_sidebar()

    def _on_task_toggle(self, task: Task, completed: bool) -> None:
        self.db.set_task_completed(task.id, completed)
        self.refresh_tasks()
        self.refresh_sidebar()

    def _on_task_delete(self, task: Task) -> None:
        self.db.delete_task(task.id)
        self.refresh_tasks()
        self.refresh_sidebar()

    def _on_task_activated(self, _box, row: TaskRow) -> None:
        self.open_task_editor(row.task)

    def _on_sidebar_task(self, task: Task) -> None:
        self.open_task_editor(task)

    def _on_drop_task(self, task_id: int, target_group_id: Optional[int]) -> None:
        self.db.set_task_group(task_id, target_group_id)
        self.refresh_sidebar()
        self.refresh_tasks()

    def _on_request_add_task(self, group_id: Optional[int]) -> None:
        prev_selected = self.selected_group_id
        self.selected_group_id = group_id
        try:
            self.open_task_editor()
        finally:
            self.selected_group_id = prev_selected

    def open_task_editor(self, task: Optional[Task] = None) -> None:
        editor = TaskEditor(
            self, self.db, task=task, default_group_id=self.selected_group_id
        )

        def _on_close(*_):
            self.refresh_sidebar()
            self.refresh_tasks()
            return False

        editor.connect("close-request", _on_close)
        editor.present()

    def open_group_editor(self, group_id: Optional[int]) -> None:
        group = self.db.get_group(group_id) if group_id is not None else None
        editor = GroupEditor(self, self.db, group=group)

        def _on_close(*_):
            if editor.deleted and self.selected_group_id == group_id:
                self.selected_group_id = None
            self.refresh_sidebar()
            self.refresh_tasks()
            return False

        editor.connect("close-request", _on_close)
        editor.present()


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
        try:
            notify_tasks_due_today(self._db.tasks_due_on(date.today()))
        except Exception:
            pass

    def do_shutdown(self):
        if self._db is not None:
            self._db.close()
        Adw.Application.do_shutdown(self)
