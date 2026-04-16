"""Phase 2 + Phase 4: SQLite persistence, CRUD, filtering, sorting."""
from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from desktop_planner.database import Database


def test_schema_creates_tables(db: Database):
    cur = db._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {row["name"] for row in cur.fetchall()}
    assert {"groups", "tasks"}.issubset(tables)


def test_group_crud(db: Database):
    g = db.create_group("Work", "#ff0000")
    assert g.id is not None
    assert db.get_group(g.id).name == "Work"

    g.name = "Work 2"
    g.color = "#00ff00"
    db.update_group(g)
    assert db.get_group(g.id).name == "Work 2"
    assert db.get_group(g.id).color == "#00ff00"

    db.delete_group(g.id)
    assert db.get_group(g.id) is None


def test_group_unique_name(db: Database):
    db.create_group("Inbox")
    with pytest.raises(sqlite3.IntegrityError):
        db.create_group("Inbox")


def test_task_crud_and_completion(db: Database):
    g = db.create_group("Home")
    t = db.create_task("Buy milk", group_id=g.id, due_date="2026-04-20")
    assert t.id is not None
    assert t.due_date == date(2026, 4, 20)
    assert t.completed is False

    db.set_task_completed(t.id, True)
    assert db.get_task(t.id).completed is True

    t = db.get_task(t.id)
    t.title = "Buy oat milk"
    t.due_date = date(2026, 4, 21)
    db.update_task(t)
    fresh = db.get_task(t.id)
    assert fresh.title == "Buy oat milk"
    assert fresh.due_date == date(2026, 4, 21)

    db.delete_task(t.id)
    assert db.get_task(t.id) is None


def test_filter_by_group(db: Database):
    work = db.create_group("Work")
    home = db.create_group("Home")
    db.create_task("Email", group_id=work.id)
    db.create_task("Slides", group_id=work.id)
    db.create_task("Dishes", group_id=home.id)

    assert {t.title for t in db.list_tasks(group_id=work.id)} == {"Email", "Slides"}
    assert [t.title for t in db.list_tasks(group_id=home.id)] == ["Dishes"]
    assert len(db.list_tasks()) == 3


def test_sort_by_date_nulls_last(db: Database):
    db.create_task("late", due_date="2026-12-01")
    db.create_task("none")
    db.create_task("soon", due_date="2026-04-20")

    titles = [t.title for t in db.list_tasks(sort_by_date=True)]
    assert titles == ["soon", "late", "none"]


def test_tasks_due_on(db: Database):
    db.create_task("today1", due_date="2026-04-16")
    db.create_task("today2", due_date="2026-04-16")
    db.create_task("other", due_date="2026-04-17")

    todays = db.tasks_due_on(date(2026, 4, 16))
    assert {t.title for t in todays} == {"today1", "today2"}


def test_deleting_group_nullifies_task_group(db: Database):
    g = db.create_group("Temp")
    t = db.create_task("orphan-me", group_id=g.id)
    db.delete_group(g.id)
    assert db.get_task(t.id).group_id is None


def test_persistence_across_reopens(tmp_path):
    path = tmp_path / "persist.db"
    with Database(path) as db1:
        g = db1.create_group("Persisted")
        db1.create_task("survive reboot", group_id=g.id, due_date="2026-05-01")
    # Reopen
    with Database(path) as db2:
        groups = db2.list_groups()
        tasks = db2.list_tasks()
        assert [g.name for g in groups] == ["Persisted"]
        assert [t.title for t in tasks] == ["survive reboot"]
        assert tasks[0].due_date == date(2026, 5, 1)


def test_invalid_due_date_rejected(db: Database):
    with pytest.raises(ValueError):
        db.create_task("bad", due_date="not-a-date")
