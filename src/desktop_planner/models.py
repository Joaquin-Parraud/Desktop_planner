"""Plain dataclass models. UI- and DB-agnostic."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


def _parse_date(value: Optional[str | date]) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


@dataclass
class Group:
    id: Optional[int]
    name: str
    color: str = "#3584e4"  # GNOME blue default

    @classmethod
    def from_row(cls, row) -> "Group":
        return cls(id=row["id"], name=row["name"], color=row["color"])


@dataclass
class Task:
    id: Optional[int]
    title: str
    group_id: Optional[int] = None
    due_date: Optional[date] = None
    completed: bool = False
    created_at: Optional[datetime] = field(default=None)

    def __post_init__(self) -> None:
        if isinstance(self.due_date, str):
            self.due_date = _parse_date(self.due_date)

    @classmethod
    def from_row(cls, row) -> "Task":
        created = row["created_at"]
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created)
            except ValueError:
                created = None
        return cls(
            id=row["id"],
            title=row["title"],
            group_id=row["group_id"],
            due_date=_parse_date(row["due_date"]),
            completed=bool(row["completed"]),
            created_at=created,
        )

    @property
    def due_date_iso(self) -> Optional[str]:
        return self.due_date.isoformat() if self.due_date else None
