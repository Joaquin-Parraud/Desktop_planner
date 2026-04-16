"""SQLite persistence layer. CRUD for tasks and groups.

Data is stored at ``$XDG_DATA_HOME/desktop-planner/planner.db`` (typically
``~/.local/share/desktop-planner/planner.db``) and survives reboots.

All write operations commit immediately so data is auto-saved on every
modification.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Iterable, Iterator, Optional

from .models import Group, Task
from .paths import database_path


SCHEMA = """
CREATE TABLE IF NOT EXISTS groups (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL UNIQUE,
    color TEXT NOT NULL DEFAULT '#3584e4'
);

CREATE TABLE IF NOT EXISTS tasks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    group_id   INTEGER REFERENCES groups(id) ON DELETE SET NULL,
    due_date   TEXT,                  -- ISO 8601 (YYYY-MM-DD) or NULL
    completed  INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tasks_group    ON tasks(group_id);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
"""


class Database:
    """Thin wrapper around a sqlite3.Connection providing typed CRUD."""

    def __init__(self, path: Optional[Path | str] = None):
        self.path = Path(path) if path is not None else database_path()
        # Ensure parent dir exists for non-default paths too.
        if self.path != Path(":memory:"):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self.path), detect_types=sqlite3.PARSE_DECLTYPES, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._init_schema()

    # ----- lifecycle ----------------------------------------------------
    def _init_schema(self) -> None:
        # executescript() manages its own transaction in autocommit mode,
        # so we call it directly rather than wrapping in _tx().
        self._conn.executescript(SCHEMA)

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
    def create_group(self, name: str, color: str = "#3584e4") -> Group:
        with self._tx() as cur:
            cur.execute(
                "INSERT INTO groups (name, color) VALUES (?, ?)", (name, color)
            )
            gid = cur.lastrowid
        return Group(id=gid, name=name, color=color)

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
                "UPDATE groups SET name = ?, color = ? WHERE id = ?",
                (group.name, group.color, group.id),
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
        completed: bool = False,
    ) -> Task:
        iso = _date_to_iso(due_date)
        with self._tx() as cur:
            cur.execute(
                "INSERT INTO tasks (title, group_id, due_date, completed) "
                "VALUES (?, ?, ?, ?)",
                (title, group_id, iso, int(completed)),
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
        """List tasks. Filtering/sorting performed in SQL.

        ``group_id``: when provided, restrict to that group.
        ``due_on``:   when provided, only tasks with that exact due_date.
        ``sort_by_date``: order by due_date ascending (NULLs last), then title.
        """
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
                "ORDER BY (due_date IS NULL), due_date ASC, title COLLATE NOCASE ASC"
            )
        else:
            order = "ORDER BY completed ASC, id DESC"
        sql = f"SELECT * FROM tasks {where} {order}"
        cur = self._conn.execute(sql, params)
        return [Task.from_row(r) for r in cur.fetchall()]

    def update_task(self, task: Task) -> None:
        if task.id is None:
            raise ValueError("task.id required for update")
        with self._tx() as cur:
            cur.execute(
                "UPDATE tasks SET title = ?, group_id = ?, due_date = ?, "
                "completed = ? WHERE id = ?",
                (
                    task.title,
                    task.group_id,
                    _date_to_iso(task.due_date),
                    int(task.completed),
                    task.id,
                ),
            )

    def set_task_completed(self, task_id: int, completed: bool) -> None:
        with self._tx() as cur:
            cur.execute(
                "UPDATE tasks SET completed = ? WHERE id = ?",
                (int(completed), task_id),
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
    # Validate by round-tripping
    return date.fromisoformat(value).isoformat()
