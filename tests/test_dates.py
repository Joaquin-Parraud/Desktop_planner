"""Phase 4: relative date parsing/formatting."""
from __future__ import annotations

from datetime import date

import pytest

from desktop_planner import dates


REF = date(2026, 4, 16)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("today", REF),
        ("Tomorrow", date(2026, 4, 17)),
        ("YESTERDAY", date(2026, 4, 15)),
        ("2026-12-31", date(2026, 12, 31)),
        ("", None),
        ("   ", None),
    ],
)
def test_parse_relative(text, expected):
    assert dates.parse_relative(text, today=REF) == expected


def test_parse_relative_invalid_raises():
    with pytest.raises(ValueError):
        dates.parse_relative("not a date", today=REF)


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, ""),
        (REF, "Today"),
        (date(2026, 4, 17), "Tomorrow"),
        (date(2026, 4, 15), "Yesterday"),
        (date(2027, 1, 1), "2027-01-01"),
    ],
)
def test_format_relative(value, expected):
    assert dates.format_relative(value, today=REF) == expected
