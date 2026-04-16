"""Plain dataclass models. UI- and DB-agnostic."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Optional


def _parse_date(value: Optional[str | date]) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(value)


def _parse_time(value: Optional[str | time]) -> Optional[time]:
    if value is None or value == "":
        return None
    if isinstance(value, time):
        return value
    # Accept "HH:MM" or "HH:MM:SS"
    return time.fromisoformat(value)


@dataclass
class Group:
    id: Optional[int]
    name: str
    color: str = "#3584e4"  # GNOME blue default
    description: str = ""

    @classmethod
    def from_row(cls, row) -> "Group":
        # description column may not exist in pre-migration rows; defensively
        # fall back to "" via dict-like access.
        try:
            desc = row["description"] or ""
        except (IndexError, KeyError):
            desc = ""
        return cls(id=row["id"], name=row["name"], color=row["color"], description=desc)


@dataclass
class Task:
    id: Optional[int]
    title: str
    group_id: Optional[int] = None
    due_date: Optional[date] = None
    due_time: Optional[time] = None
    completed: bool = False
    description: str = ""
    created_at: Optional[datetime] = field(default=None)

    def __post_init__(self) -> None:
        if isinstance(self.due_date, str):
            self.due_date = _parse_date(self.due_date)
        if isinstance(self.due_time, str):
            self.due_time = _parse_time(self.due_time)

    @classmethod
    def from_row(cls, row) -> "Task":
        created = row["created_at"]
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created)
            except ValueError:
                created = None
        try:
            desc = row["description"] or ""
        except (IndexError, KeyError):
            desc = ""
        try:
            tval = row["due_time"]
        except (IndexError, KeyError):
            tval = None
        return cls(
            id=row["id"],
            title=row["title"],
            group_id=row["group_id"],
            due_date=_parse_date(row["due_date"]),
            due_time=_parse_time(tval),
            completed=bool(row["completed"]),
            description=desc,
            created_at=created,
        )

    @property
    def due_date_iso(self) -> Optional[str]:
        return self.due_date.isoformat() if self.due_date else None

    @property
    def due_time_iso(self) -> Optional[str]:
        return self.due_time.strftime("%H:%M") if self.due_time else None
