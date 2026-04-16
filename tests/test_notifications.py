"""Phase 4: notifications dispatch logic (backends are stubbed)."""
from __future__ import annotations

from datetime import date

from desktop_planner import notifications
from desktop_planner.models import Task


def test_notify_tasks_due_today_filters(monkeypatch):
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        notifications, "notify", lambda summary, body="": (sent.append((summary, body)) or True)
    )

    tasks = [
        Task(id=1, title="due today", due_date=date(2026, 4, 16)),
        Task(id=2, title="done today", due_date=date(2026, 4, 16), completed=True),
        Task(id=3, title="tomorrow", due_date=date(2026, 4, 17)),
        Task(id=4, title="no date"),
    ]
    count = notifications.notify_tasks_due_today(tasks, today=date(2026, 4, 16))
    assert count == 1
    assert sent == [("Task due today", "due today")]


def test_notify_returns_false_when_no_backends(monkeypatch):
    monkeypatch.setattr(notifications, "_try_gi_notify", lambda *_: False)
    monkeypatch.setattr(notifications, "_try_notify_send", lambda *_: False)
    assert notifications.notify("hi", "body") is False
