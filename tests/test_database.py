"""Phase 2 + Phase 4 + update_1: SQLite persistence, CRUD, filter/sort, new fields."""
from __future__ import annotations

import sqlite3
from datetime import date, time

import pytest

from desktop_planner.database import Database


def test_schema_creates_tables(db: Database):
    cur = db._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {row["name"] for row in cur.fetchall()}
    assert {"groups", "tasks"}.issubset(tables)


def test_group_crud_with_description(db: Database):
    g = db.create_group("Work", "#ff0000", description="Office tasks")
    assert g.id is not None
    fresh = db.get_group(g.id)
    assert fresh.name == "Work"
    assert fresh.description == "Office tasks"

    g.name = "Work 2"
    g.color = "#00ff00"
    g.description = "Updated"
    db.update_group(g)
    fresh = db.get_group(g.id)
    assert fresh.name == "Work 2"
    assert fresh.color == "#00ff00"
    assert fresh.description == "Updated"

    db.delete_group(g.id)
    assert db.get_group(g.id) is None


def test_group_unique_name(db: Database):
    db.create_group("Inbox")
    with pytest.raises(sqlite3.IntegrityError):
        db.create_group("Inbox")


def test_task_crud_completion_description_time(db: Database):
    g = db.create_group("Home")
    t = db.create_task(
        "Buy milk",
        group_id=g.id,
        due_date="2026-04-20",
        due_time="09:30",
        description="2L oat",
    )
    assert t.id is not None
    assert t.due_date == date(2026, 4, 20)
    assert t.due_time == time(9, 30)
    assert t.description == "2L oat"
    assert t.completed is False

    db.set_task_completed(t.id, True)
    assert db.get_task(t.id).completed is True

    t = db.get_task(t.id)
    t.title = "Buy oat milk"
    t.due_date = date(2026, 4, 21)
    t.due_time = time(18, 0)
    t.description = ""
    db.update_task(t)
    fresh = db.get_task(t.id)
    assert fresh.title == "Buy oat milk"
    assert fresh.due_date == date(2026, 4, 21)
    assert fresh.due_time == time(18, 0)
    assert fresh.description == ""

    db.delete_task(t.id)
    assert db.get_task(t.id) is None


def test_task_delete_only(db: Database):
    t = db.create_task("ephemeral")
    assert db.get_task(t.id) is not None
    db.delete_task(t.id)
    assert db.get_task(t.id) is None


def test_set_task_group_moves_task(db: Database):
    src = db.create_group("Src")
    dst = db.create_group("Dst")
    t = db.create_task("move me", group_id=src.id)
    db.set_task_group(t.id, dst.id)
    assert db.get_task(t.id).group_id == dst.id
    db.set_task_group(t.id, None)
    assert db.get_task(t.id).group_id is None


def test_filter_by_group(db: Database):
    work = db.create_group("Work")
    home = db.create_group("Home")
    db.create_task("Email", group_id=work.id)
    db.create_task("Slides", group_id=work.id)
    db.create_task("Dishes", group_id=home.id)

    assert {t.title for t in db.list_tasks(group_id=work.id)} == {"Email", "Slides"}
    assert [t.title for t in db.list_tasks(group_id=home.id)] == ["Dishes"]
    assert len(db.list_tasks()) == 3


def test_sort_by_date_then_time_nulls_last(db: Database):
    db.create_task("late", due_date="2026-12-01")
    db.create_task("none")
    db.create_task("soon-late", due_date="2026-04-20", due_time="18:00")
    db.create_task("soon-early", due_date="2026-04-20", due_time="08:00")

    titles = [t.title for t in db.list_tasks(sort_by_date=True)]
    assert titles == ["soon-early", "soon-late", "late", "none"]


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
        g = db1.create_group("Persisted", description="keep")
        db1.create_task(
            "survive reboot",
            group_id=g.id,
            due_date="2026-05-01",
            due_time="07:15",
            description="with notes",
        )
    with Database(path) as db2:
        groups = db2.list_groups()
        tasks = db2.list_tasks()
        assert [g.name for g in groups] == ["Persisted"]
        assert groups[0].description == "keep"
        assert [t.title for t in tasks] == ["survive reboot"]
        assert tasks[0].due_date == date(2026, 5, 1)
        assert tasks[0].due_time == time(7, 15)
        assert tasks[0].description == "with notes"


def test_invalid_due_date_rejected(db: Database):
    with pytest.raises(ValueError):
        db.create_task("bad", due_date="not-a-date")


def test_invalid_due_time_rejected(db: Database):
    with pytest.raises(ValueError):
        db.create_task("bad", due_time="not-a-time")


def test_migration_adds_new_columns_to_legacy_db(tmp_path):
    """A pre-update_1 database (only old columns) should auto-migrate."""
    path = tmp_path / "legacy.db"
    legacy = sqlite3.connect(str(path))
    legacy.executescript(
        """
        CREATE TABLE groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT NOT NULL DEFAULT '#3584e4'
        );
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            group_id INTEGER REFERENCES groups(id) ON DELETE SET NULL,
            due_date TEXT,
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT INTO groups(name) VALUES ('legacy-group');
        INSERT INTO tasks(title, group_id, due_date) VALUES ('old', 1, '2026-04-20');
        """
    )
    legacy.commit()
    legacy.close()

    with Database(path) as db:
        # New columns now exist:
        cols = {row["name"] for row in db._conn.execute("PRAGMA table_info(tasks)")}
        assert {"description", "due_time", "important", "repeat"}.issubset(cols)
        gcols = {row["name"] for row in db._conn.execute("PRAGMA table_info(groups)")}
        assert "description" in gcols
        # Legacy data still readable + defaults applied:
        t = db.list_tasks()[0]
        assert t.title == "old"
        assert t.description == ""
        assert t.due_time is None
        assert t.important is False
        assert t.repeat is None
        g = db.list_groups()[0]
        assert g.description == ""


def test_important_flag_crud(db: Database):
    t = db.create_task("star me")
    assert t.important is False

    db.set_task_important(t.id, True)
    assert db.get_task(t.id).important is True

    db.set_task_important(t.id, False)
    assert db.get_task(t.id).important is False


def test_important_tasks_sort_before_normal(db: Database):
    db.create_task("normal")
    imp = db.create_task("important")
    db.set_task_important(imp.id, True)

    titles = [t.title for t in db.list_tasks()]
    assert titles.index("important") < titles.index("normal")


def test_completed_tasks_sort_to_bottom(db: Database):
    db.create_task("first")
    done = db.create_task("done")
    db.set_task_completed(done.id, True)
    db.create_task("second")

    titles = [t.title for t in db.list_tasks()]
    assert titles[-1] == "done"


def test_repeat_field_persists(db: Database):
    t = db.create_task("daily standup", repeat="daily", due_date="2026-04-20")
    assert t.repeat == "daily"
    fresh = db.get_task(t.id)
    assert fresh.repeat == "daily"

    fresh.repeat = "weekly"
    db.update_task(fresh)
    assert db.get_task(t.id).repeat == "weekly"

    fresh.repeat = None
    db.update_task(fresh)
    assert db.get_task(t.id).repeat is None
