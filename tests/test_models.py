"""Models: dataclasses, parsing of dates/times, ISO conversion."""
from __future__ import annotations

from datetime import date, time

import pytest

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


def test_task_important_default_false():
    t = Task(id=None, title="x")
    assert t.important is False


def test_task_repeat_default_none():
    t = Task(id=None, title="x")
    assert t.repeat is None


@pytest.mark.parametrize("repeat,base,expected", [
    ("daily",   date(2026, 4, 20), date(2026, 4, 21)),
    ("weekly",  date(2026, 4, 20), date(2026, 4, 27)),
    ("monthly", date(2026, 1, 31), date(2026, 2, 28)),  # clamped to Feb end
    ("monthly", date(2026, 3, 15), date(2026, 4, 15)),
    ("yearly",  date(2026, 4, 20), date(2027, 4, 20)),
])
def test_next_repeat_date(repeat, base, expected):
    t = Task(id=None, title="x", due_date=base, repeat=repeat)
    assert t.next_repeat_date() == expected


def test_next_repeat_date_no_due_date_returns_none():
    t = Task(id=None, title="x", repeat="daily")
    assert t.next_repeat_date() is None


def test_next_repeat_date_no_repeat_returns_none():
    t = Task(id=None, title="x", due_date=date(2026, 4, 20))
    assert t.next_repeat_date() is None
