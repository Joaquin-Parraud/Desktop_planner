"""MCP server exposing Desktop Planner task and group management to AI agents.

Run with:
    python -m desktop_planner.mcp_server
or via the installed script:
    desktop-planner-mcp
"""
from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from .database import Database

mcp = FastMCP("Desktop Planner")


def _db() -> Database:
    return Database()


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def _task_dict(t) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "group_id": t.group_id,
        "due_date": t.due_date_iso,
        "due_time": t.due_time_iso,
        "completed": t.completed,
        "important": t.important,
        "repeat": t.repeat,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


@mcp.tool()
def list_tasks(
    group_id: Optional[int] = None,
    due_date: Optional[str] = None,
    sort_by_date: bool = False,
) -> list[dict]:
    """Return all tasks, optionally filtered by group or due date (YYYY-MM-DD)."""
    with _db() as db:
        tasks = db.list_tasks(
            group_id=group_id,
            due_on=due_date,
            sort_by_date=sort_by_date,
        )
    return [_task_dict(t) for t in tasks]


@mcp.tool()
def get_task(task_id: int) -> dict:
    """Return a single task by its ID. Raises ValueError if not found."""
    with _db() as db:
        task = db.get_task(task_id)
    if task is None:
        raise ValueError(f"Task {task_id} not found")
    return _task_dict(task)


@mcp.tool()
def create_task(
    title: str,
    description: str = "",
    group_id: Optional[int] = None,
    due_date: Optional[str] = None,
    due_time: Optional[str] = None,
    important: bool = False,
    repeat: Optional[str] = None,
) -> dict:
    """Create a new task. Returns the created task with its assigned ID.

    Args:
        title: Task title (required).
        description: Optional longer notes.
        group_id: ID of an existing group to assign the task to.
        due_date: ISO date string YYYY-MM-DD, e.g. "2025-06-01".
        due_time: 24-hour time string HH:MM, e.g. "14:30".
        important: Mark the task as important (starred).
        repeat: Recurrence rule — "daily", "weekly", "monthly", or "yearly".
    """
    with _db() as db:
        task = db.create_task(
            title=title,
            description=description,
            group_id=group_id,
            due_date=due_date,
            due_time=due_time,
            important=important,
            repeat=repeat,
        )
    return _task_dict(task)


@mcp.tool()
def update_task(
    task_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    group_id: Optional[int] = None,
    due_date: Optional[str] = None,
    due_time: Optional[str] = None,
    completed: Optional[bool] = None,
    important: Optional[bool] = None,
    repeat: Optional[str] = None,
) -> dict:
    """Update one or more fields of an existing task. Only provided fields are changed.

    Pass due_date="" or due_time="" to clear those fields.
    Pass group_id=0 to remove the task from its group.
    Pass repeat="" to clear the repeat rule.
    """
    import datetime as _dt
    with _db() as db:
        task = db.get_task(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")
        if title is not None:
            task.title = title
        if description is not None:
            task.description = description
        if group_id is not None:
            task.group_id = group_id if group_id != 0 else None
        if due_date is not None:
            task.due_date = None if due_date == "" else _dt.date.fromisoformat(due_date)
        if due_time is not None:
            task.due_time = None if due_time == "" else _dt.time.fromisoformat(due_time)
        if completed is not None:
            task.completed = completed
        if important is not None:
            task.important = important
        if repeat is not None:
            task.repeat = repeat or None
        db.update_task(task)
    return get_task(task_id)


@mcp.tool()
def complete_task(task_id: int, completed: bool = True) -> dict:
    """Mark a task as completed or incomplete. Returns the updated task."""
    with _db() as db:
        if db.get_task(task_id) is None:
            raise ValueError(f"Task {task_id} not found")
        db.set_task_completed(task_id, completed)
    return get_task(task_id)


@mcp.tool()
def set_task_important(task_id: int, important: bool = True) -> dict:
    """Mark a task as important (starred) or not. Returns the updated task."""
    with _db() as db:
        if db.get_task(task_id) is None:
            raise ValueError(f"Task {task_id} not found")
        db.set_task_important(task_id, important)
    return get_task(task_id)


@mcp.tool()
def delete_task(task_id: int) -> dict:
    """Permanently delete a task by ID. Returns a confirmation message."""
    with _db() as db:
        if db.get_task(task_id) is None:
            raise ValueError(f"Task {task_id} not found")
        db.delete_task(task_id)
    return {"deleted": True, "task_id": task_id}


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------

@mcp.tool()
def list_groups() -> list[dict]:
    """Return all task groups sorted alphabetically."""
    with _db() as db:
        groups = db.list_groups()
    return [
        {"id": g.id, "name": g.name, "color": g.color, "description": g.description}
        for g in groups
    ]


@mcp.tool()
def get_group(group_id: int) -> dict:
    """Return a single group by its ID. Raises ValueError if not found."""
    with _db() as db:
        group = db.get_group(group_id)
    if group is None:
        raise ValueError(f"Group {group_id} not found")
    return {"id": group.id, "name": group.name, "color": group.color, "description": group.description}


@mcp.tool()
def create_group(
    name: str,
    color: str = "#3584e4",
    description: str = "",
) -> dict:
    """Create a new group. Returns the created group with its assigned ID.

    Args:
        name: Unique group name (required).
        color: Hex color string, e.g. "#ff5733".
        description: Optional notes about the group.
    """
    with _db() as db:
        group = db.create_group(name=name, color=color, description=description)
    return {"id": group.id, "name": group.name, "color": group.color, "description": group.description}


@mcp.tool()
def update_group(
    group_id: int,
    name: Optional[str] = None,
    color: Optional[str] = None,
    description: Optional[str] = None,
) -> dict:
    """Update one or more fields of an existing group. Only provided fields are changed."""
    with _db() as db:
        group = db.get_group(group_id)
        if group is None:
            raise ValueError(f"Group {group_id} not found")
        if name is not None:
            group.name = name
        if color is not None:
            group.color = color
        if description is not None:
            group.description = description
        db.update_group(group)
    return get_group(group_id)


@mcp.tool()
def delete_group(group_id: int) -> dict:
    """Permanently delete a group. Tasks in the group become ungrouped. Returns confirmation."""
    with _db() as db:
        if db.get_group(group_id) is None:
            raise ValueError(f"Group {group_id} not found")
        db.delete_group(group_id)
    return {"deleted": True, "group_id": group_id}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
