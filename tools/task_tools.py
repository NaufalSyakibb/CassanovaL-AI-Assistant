import json
import uuid
from datetime import datetime
from langchain.tools import tool

TASKS_FILE = "data/tasks.json"


def _load() -> list:
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save(data: list):
    import os
    os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


@tool
def add_task(title: str, priority: str = "medium", due_date: str = "") -> str:
    """Add a new task. Args: title, priority ('high'/'medium'/'low'), due_date (YYYY-MM-DD)."""
    tasks = _load()
    task = {
        "id": str(uuid.uuid4())[:8],
        "title": title,
        "priority": priority.lower(),
        "due_date": due_date,
        "status": "pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    tasks.append(task)
    _save(tasks)
    return f"Task added! ID:{task['id']} | \"{title}\" | Priority:{priority} | Due:{due_date or 'not set'}"


@tool
def list_tasks(filter_status: str = "all", filter_priority: str = "all") -> str:
    """List tasks. filter_status: 'all'/'pending'/'completed'. filter_priority: 'all'/'high'/'medium'/'low'."""
    tasks = _load()
    if filter_status != "all":
        tasks = [t for t in tasks if t["status"] == filter_status]
    if filter_priority != "all":
        tasks = [t for t in tasks if t["priority"] == filter_priority]
    if not tasks:
        return "No tasks found."
    lines = []
    for t in tasks:
        icon = "✓" if t["status"] == "completed" else "○"
        due = f" | Due:{t['due_date']}" if t.get("due_date") else ""
        lines.append(f"[{icon}] ID:{t['id']} | {t['title']} | {t['priority']}{due}")
    return "\n".join(lines)


@tool
def complete_task(task_id: str) -> str:
    """Mark a task as completed by its ID."""
    tasks = _load()
    for t in tasks:
        if t["id"] == task_id:
            t["status"] = "completed"
            _save(tasks)
            return f"Task {task_id} \"{t['title']}\" marked as completed!"
    return f"Task ID {task_id} not found."


@tool
def delete_task(task_id: str) -> str:
    """Delete a task by its ID."""
    tasks = _load()
    new = [t for t in tasks if t["id"] != task_id]
    if len(new) == len(tasks):
        return f"Task ID {task_id} not found."
    _save(new)
    return f"Task {task_id} deleted."


@tool
def update_task(task_id: str, title: str = "", priority: str = "", due_date: str = "") -> str:
    """Update a task's title, priority, or due date by its ID."""
    tasks = _load()
    for t in tasks:
        if t["id"] == task_id:
            if title:
                t["title"] = title
            if priority:
                t["priority"] = priority.lower()
            if due_date:
                t["due_date"] = due_date
            _save(tasks)
            return f"Task {task_id} updated: \"{t['title']}\" | {t['priority']} | Due:{t.get('due_date') or 'not set'}"
    return f"Task ID {task_id} not found."


TASK_TOOLS = [add_task, list_tasks, complete_task, delete_task, update_task]
