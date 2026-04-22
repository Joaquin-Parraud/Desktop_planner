"""SQLite persistence layer. CRUD for tasks and groups.

Data is stored at ``$XDG_DATA_HOME/desktop-planner/planner.db`` (typically
``~/.local/share/desktop-planner/planner.db``) and survives reboots.

All write operations commit immediately so data is auto-saved on every
modification.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, time
from pathlib import Path
from typing import Iterator, Optional

from .models import Group, Task
from .paths import database_path


SCHEMA = """
CREATE TABLE IF NOT EXISTS groups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    color       TEXT NOT NULL DEFAULT '#3584e4',
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    group_id    INTEGER REFERENCES groups(id) ON DELETE SET NULL,
    due_date    TEXT,                  -- ISO 8601 (YYYY-MM-DD) or NULL
    due_time    TEXT,                  -- 'HH:MM' or NULL
    completed   INTEGER NOT NULL DEFAULT 0,
    important   INTEGER NOT NULL DEFAULT 0,
    repeat      TEXT,                  -- 'daily'|'weekly'|'monthly'|'yearly' or NULL
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tasks_group    ON tasks(group_id);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
"""

# Columns added after the initial schema; applied with ALTER TABLE on
# pre-existing databases.
MIGRATIONS: list[tuple[str, str, str]] = [
    ("groups", "description", "TEXT NOT NULL DEFAULT ''"),
    ("tasks", "description", "TEXT NOT NULL DEFAULT ''"),
    ("tasks", "due_time", "TEXT"),
    ("tasks", "important", "INTEGER NOT NULL DEFAULT 0"),
    ("tasks", "repeat", "TEXT"),
]


class Database:
    """Thin wrapper around a sqlite3.Connection providing typed CRUD."""

    def __init__(self, path: Optional[Path | str] = None):
        self.path = Path(path) if path is not None else database_path()
        if self.path != Path(":memory:"):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self.path), detect_types=sqlite3.PARSE_DECLTYPES, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._init_schema()
        self._migrate()

    # ----- lifecycle ----------------------------------------------------
    def _init_schema(self) -> None:
        # executescript() manages its own transaction in autocommit mode.
        self._conn.executescript(SCHEMA)

    def _migrate(self) -> None:
        for table, column, decl in MIGRATIONS:
            if not self._column_exists(table, column):
                self._conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {decl}"
                )

    def _column_exists(self, table: str, column: str) -> bool:
        cur = self._conn.execute(f"PRAGMA table_info({table})")
        return any(row["name"] == column for row in cur.fetchall())

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Cursor]:
        cur = self._conn.cursor()
        try:
            cur.execute("BEGIN")
            yield cur
            cur.execute("COMMIT")
        except Exception:
            cur.execute("ROLLBACK")
            raise
        finally:
            cur.close()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ----- groups -------------------------------------------------------
    def create_group(
        self, name: str, color: str = "#3584e4", description: str = ""
    ) -> Group:
        with self._tx() as cur:
            cur.execute(
                "INSERT INTO groups (name, color, description) VALUES (?, ?, ?)",
                (name, color, description),
            )
            gid = cur.lastrowid
        return Group(id=gid, name=name, color=color, description=description)

    def list_groups(self) -> list[Group]:
        cur = self._conn.execute("SELECT * FROM groups ORDER BY name COLLATE NOCASE")
        return [Group.from_row(r) for r in cur.fetchall()]

    def get_group(self, group_id: int) -> Optional[Group]:
        cur = self._conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,))
        row = cur.fetchone()
        return Group.from_row(row) if row else None

    def update_group(self, group: Group) -> None:
        if group.id is None:
            raise ValueError("group.id required for update")
        with self._tx() as cur:
            cur.execute(
                "UPDATE groups SET name = ?, color = ?, description = ? WHERE id = ?",
                (group.name, group.color, group.description, group.id),
            )

    def delete_group(self, group_id: int) -> None:
        with self._tx() as cur:
            cur.execute("DELETE FROM groups WHERE id = ?", (group_id,))

    # ----- tasks --------------------------------------------------------
    def create_task(
        self,
        title: str,
        group_id: Optional[int] = None,
        due_date: Optional[date | str] = None,
        due_time: Optional[time | str] = None,
        completed: bool = False,
        important: bool = False,
        description: str = "",
        repeat: Optional[str] = None,
    ) -> Task:
        iso_d = _date_to_iso(due_date)
        iso_t = _time_to_iso(due_time)
        with self._tx() as cur:
            cur.execute(
                "INSERT INTO tasks "
                "(title, description, group_id, due_date, due_time, completed, important, repeat) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (title, description, group_id, iso_d, iso_t, int(completed), int(important), repeat),
            )
            tid = cur.lastrowid
            row = cur.execute("SELECT * FROM tasks WHERE id = ?", (tid,)).fetchone()
        return Task.from_row(row)

    def get_task(self, task_id: int) -> Optional[Task]:
        cur = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cur.fetchone()
        return Task.from_row(row) if row else None

    def list_tasks(
        self,
        *,
        group_id: Optional[int] = None,
        due_on: Optional[date | str] = None,
        sort_by_date: bool = False,
    ) -> list[Task]:
        """List tasks. Filtering/sorting performed in SQL."""
        clauses: list[str] = []
        params: list = []
        if group_id is not None:
            clauses.append("group_id = ?")
            params.append(group_id)
        if due_on is not None:
            clauses.append("due_date = ?")
            params.append(_date_to_iso(due_on))
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        if sort_by_date:
            order = (
                "ORDER BY completed ASC, (due_date IS NULL), due_date ASC, "
                "(due_time IS NULL), due_time ASC, title COLLATE NOCASE ASC"
            )
        else:
            order = "ORDER BY completed ASC, important DESC, id DESC"
        sql = f"SELECT * FROM tasks {where} {order}"
        cur = self._conn.execute(sql, params)
        return [Task.from_row(r) for r in cur.fetchall()]

    def update_task(self, task: Task) -> None:
        if task.id is None:
            raise ValueError("task.id required for update")
        with self._tx() as cur:
            cur.execute(
                "UPDATE tasks SET title = ?, description = ?, group_id = ?, "
                "due_date = ?, due_time = ?, completed = ?, important = ?, repeat = ? "
                "WHERE id = ?",
                (
                    task.title,
                    task.description,
                    task.group_id,
                    _date_to_iso(task.due_date),
                    _time_to_iso(task.due_time),
                    int(task.completed),
                    int(task.important),
                    task.repeat,
                    task.id,
                ),
            )

    def set_task_completed(self, task_id: int, completed: bool) -> None:
        with self._tx() as cur:
            cur.execute(
                "UPDATE tasks SET completed = ? WHERE id = ?",
                (int(completed), task_id),
            )

    def set_task_important(self, task_id: int, important: bool) -> None:
        with self._tx() as cur:
            cur.execute(
                "UPDATE tasks SET important = ? WHERE id = ?",
                (int(important), task_id),
            )

    def set_task_group(self, task_id: int, group_id: Optional[int]) -> None:
        with self._tx() as cur:
            cur.execute(
                "UPDATE tasks SET group_id = ? WHERE id = ?", (group_id, task_id)
            )

    def delete_task(self, task_id: int) -> None:
        with self._tx() as cur:
            cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    def tasks_due_on(self, when: date) -> list[Task]:
        return self.list_tasks(due_on=when, sort_by_date=True)


def _date_to_iso(value: Optional[date | str]) -> Optional[str]:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value.isoformat()
    return date.fromisoformat(value).isoformat()


def _time_to_iso(value: Optional[time | str]) -> Optional[str]:
    if value is None or value == "":
        return None
    if isinstance(value, time):
        return value.strftime("%H:%M")
    # Validate by round-tripping
    return time.fromisoformat(value).strftime("%H:%M")
