"""Date utilities — relative date parsing and formatting."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

_RELATIVE = {
    "today": 0,
    "tomorrow": 1,
    "yesterday": -1,
}


def parse_relative(text: str, *, today: Optional[date] = None) -> Optional[date]:
    """Parse 'today', 'tomorrow', 'yesterday' or an ISO date.

    Returns ``None`` for empty input. Raises ``ValueError`` on invalid text.
    """
    if text is None:
        return None
    text = text.strip().lower()
    if not text:
        return None
    base = today or date.today()
    if text in _RELATIVE:
        return base + timedelta(days=_RELATIVE[text])
    return date.fromisoformat(text)


def format_relative(value: Optional[date], *, today: Optional[date] = None) -> str:
    """Human-friendly label for a date (or '' if none)."""
    if value is None:
        return ""
    base = today or date.today()
    delta = (value - base).days
    if delta == 0:
        return "Today"
    if delta == 1:
        return "Tomorrow"
    if delta == -1:
        return "Yesterday"
    return value.isoformat()
