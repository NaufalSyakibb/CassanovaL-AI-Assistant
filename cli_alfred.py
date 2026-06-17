"""
cli_alfred.py — Dedicated Alfred (task & schedule) CLI.

Usage:
    $env:PYTHONUTF8=1; python cli_alfred.py

Chat naturally:
    "add task buy books tomorrow, high priority"
    "show my pending tasks"
    "what's on my schedule today?"
    "create meeting tomorrow 10am-11am"
    "mark task abc123 done"

Data is saved permanently to data/tasks.json.
Requires Google Calendar credentials for schedule features.
"""

import sys
import io
import json
from pathlib import Path
from datetime import date, datetime

# Fix Windows terminal encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

_BASE  = Path(__file__).resolve().parent
_TASKS = _BASE / "data" / "tasks.json"


BANNER = """
╔══════════════════════════════════════════════════════════╗
║  📋  Alfred — Task & Schedule Manager CLI                ║
╠══════════════════════════════════════════════════════════╣
║  Manage your tasks and Google Calendar from the terminal ║
║                                                          ║
║  Examples:                                               ║
║   "add task buy book tomorrow, high priority"            ║
║   "show my pending tasks"                                ║
║   "what do I need to get done today?"                    ║
║   "create meeting tomorrow 10am-11am"                    ║
║   "mark task [id] done"                                  ║
║   "what's on my schedule this week?"                     ║
║                                                          ║
║  Type 'tasks' to see pending tasks at any time.          ║
║  Type 'quit' or 'exit' to stop.                          ║
╚══════════════════════════════════════════════════════════╝
"""


def _load_tasks() -> list:
    try:
        return json.loads(_TASKS.read_text(encoding="utf-8"))
    except Exception:
        return []


def _show_pending_tasks():
    tasks = _load_tasks()
    pending = [t for t in tasks if t.get("status") not in ("done", "completed")]
    done    = [t for t in tasks if t.get("status") in ("done", "completed")]

    print(f"\n  📋 Tasks — {len(pending)} pending / {len(done)} done")
    print("  " + "─" * 50)

    if not pending:
        print("  ✅ No pending tasks — you're all caught up!\n")
        return

    PRIORITY_ICON = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    order = {"high": 0, "medium": 1, "low": 2}
    sorted_tasks = sorted(pending, key=lambda t: order.get(t.get("priority", "medium"), 1))

    today = date.today().strftime("%Y-%m-%d")
    for t in sorted_tasks:
        icon     = PRIORITY_ICON.get(t.get("priority", "medium"), "🔵")
        due      = t.get("due_date", "")
        overdue  = " ⚠️ OVERDUE" if due and due < today else ""
        due_str  = f"  due {due}{overdue}" if due else ""
        tid      = t.get("id", "")[:6]
        print(f"  {icon} [{tid}] {t.get('title','?')}{due_str}")

    print()


def main():
    print(BANNER)
    _show_pending_tasks()

    try:
        from router import SupervisorRouter
        router = SupervisorRouter()
    except ValueError as e:
        print(f"  Error loading agent: {e}")
        sys.exit(1)

    print("  Alfred is ready. How can I help you today?\n")

    while True:
        try:
            user_input = input("  You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye! Stay organised! 📋")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "keluar", "bye"):
            print("  Goodbye! Stay organised! 📋")
            break

        if user_input.lower() in ("tasks", "list", "pending", "todo"):
            _show_pending_tasks()
            continue

        try:
            _, response = router.chat_direct("task", user_input)
            print(f"\n  [ ALFRED ]\n  {response}\n")
        except Exception as e:
            print(f"\n  Error: {e}\n")


if __name__ == "__main__":
    main()
