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


REPEAT_CHOICES: list[str] = ["daily", "weekly", "monthly", "yearly"]


@dataclass
class Task:
    id: Optional[int]
    title: str
    group_id: Optional[int] = None
    due_date: Optional[date] = None
    due_time: Optional[time] = None
    completed: bool = False
    important: bool = False
    description: str = ""
    repeat: Optional[str] = None  # "daily" | "weekly" | "monthly" | "yearly" | None
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
        try:
            important = bool(row["important"])
        except (IndexError, KeyError):
            important = False
        try:
            repeat = row["repeat"] or None
        except (IndexError, KeyError):
            repeat = None
        return cls(
            id=row["id"],
            title=row["title"],
            group_id=row["group_id"],
            due_date=_parse_date(row["due_date"]),
            due_time=_parse_time(tval),
            completed=bool(row["completed"]),
            important=important,
            description=desc,
            repeat=repeat,
            created_at=created,
        )

    @property
    def due_date_iso(self) -> Optional[str]:
        return self.due_date.isoformat() if self.due_date else None

    @property
    def due_time_iso(self) -> Optional[str]:
        return self.due_time.strftime("%H:%M") if self.due_time else None

    def next_repeat_date(self) -> Optional[date]:
        """Return the next due date after applying the repeat rule, or None."""
        if self.due_date is None or not self.repeat:
            return None
        from calendar import monthrange
        from datetime import timedelta
        d = self.due_date
        if self.repeat == "daily":
            return d + timedelta(days=1)
        if self.repeat == "weekly":
            return d + timedelta(weeks=1)
        if self.repeat == "monthly":
            y, m = d.year, d.month + 1
            if m > 12:
                y, m = y + 1, 1
            return d.replace(year=y, month=m, day=min(d.day, monthrange(y, m)[1]))
        if self.repeat == "yearly":
            return d.replace(year=d.year + 1)
        return None
