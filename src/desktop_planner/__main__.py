"""Entry point: ``python -m desktop_planner``."""
from __future__ import annotations

import sys


def main() -> int:
    # Imported here so ``--help`` / unit tests don't need GTK installed.
    from .ui import PlannerApp

    app = PlannerApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
