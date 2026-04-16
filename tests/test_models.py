"""Models: dataclasses, parsing of dates/times, ISO conversion."""
from __future__ import annotations

from datetime import date, time

from desktop_planner.models import Group, Task


def test_task_due_date_string_is_parsed():
    t = Task(id=None, title="x", due_date="2026-04-20")
    assert t.due_date == date(2026, 4, 20)


def test_task_due_time_string_is_parsed():
    t = Task(id=None, title="x", due_time="07:15")
    assert t.due_time == time(7, 15)


def test_task_iso_properties():
    t = Task(
        id=None,
        title="x",
        due_date=date(2026, 4, 20),
        due_time=time(9, 5),
    )
    assert t.due_date_iso == "2026-04-20"
    assert t.due_time_iso == "09:05"

    empty = Task(id=None, title="x")
    assert empty.due_date_iso is None
    assert empty.due_time_iso is None


def test_task_description_default_empty():
    t = Task(id=None, title="x")
    assert t.description == ""


def test_group_defaults():
    g = Group(id=None, name="Inbox")
    assert g.color.startswith("#")
    assert g.description == ""
