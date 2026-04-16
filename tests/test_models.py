"""Models: dataclasses and date parsing edge cases."""
from __future__ import annotations

from datetime import date

from desktop_planner.models import Group, Task


def test_task_due_date_string_is_parsed():
    t = Task(id=None, title="x", due_date="2026-04-20")
    assert t.due_date == date(2026, 4, 20)


def test_task_due_date_iso_property():
    t = Task(id=None, title="x", due_date=date(2026, 4, 20))
    assert t.due_date_iso == "2026-04-20"
    assert Task(id=None, title="x").due_date_iso is None


def test_group_defaults_color():
    g = Group(id=None, name="Inbox")
    assert g.color.startswith("#")
