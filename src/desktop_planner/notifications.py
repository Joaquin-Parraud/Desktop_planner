"""Desktop notifications via libnotify (with notify-send fallback)."""
from __future__ import annotations

import shutil
import subprocess
from datetime import date
from typing import Iterable

from .models import Task

_GI_AVAILABLE: bool | None = None


def _try_gi_notify(summary: str, body: str) -> bool:
    """Send via Notify GI binding. Returns True on success."""
    global _GI_AVAILABLE
    if _GI_AVAILABLE is False:
        return False
    try:
        import gi  # type: ignore

        gi.require_version("Notify", "0.7")
        from gi.repository import Notify  # type: ignore
    except (ImportError, ValueError):
        _GI_AVAILABLE = False
        return False
    try:
        if not Notify.is_initted():
            Notify.init("Desktop Planner")
        notification = Notify.Notification.new(summary, body, "appointment-soon")
        notification.show()
        _GI_AVAILABLE = True
        return True
    except Exception:
        return False


def _try_notify_send(summary: str, body: str) -> bool:
    if shutil.which("notify-send") is None:
        return False
    try:
        subprocess.run(
            ["notify-send", "-i", "appointment-soon", summary, body],
            check=False,
            timeout=3,
        )
        return True
    except (subprocess.SubprocessError, OSError):
        return False


def notify(summary: str, body: str = "") -> bool:
    """Best-effort notification. Returns True if any backend accepted it."""
    return _try_gi_notify(summary, body) or _try_notify_send(summary, body)


def notify_tasks_due_today(tasks: Iterable[Task], *, today: date | None = None) -> int:
    """Send one notification per pending task due today. Returns count sent."""
    today = today or date.today()
    count = 0
    for task in tasks:
        if task.completed:
            continue
        if task.due_date != today:
            continue
        if notify("Task due today", task.title):
            count += 1
    return count
