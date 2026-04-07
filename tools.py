import json
import uuid
from datetime import datetime
from langchain.tools import tool

TASKS_FILE = "tasks.json"


def _load_tasks() -> list:
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_tasks(tasks: list):
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)


@tool
def add_task(title: str, priority: str = "medium", due_date: str = "") -> str:
    """
    Add a new task to the task list.
    Args:
        title: The task description.
        priority: Task priority — 'high', 'medium', or 'low'. Defaults to 'medium'.
        due_date: Optional due date in YYYY-MM-DD format.
    Returns a confirmation message with the new task ID.
    """
    tasks = _load_tasks()
    task = {
        "id": str(uuid.uuid4())[:8],
        "title": title,
        "priority": priority.lower(),
        "due_date": due_date,
        "status": "pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    tasks.append(task)
    _save_tasks(tasks)
    return f"Task added! ID: {task['id']} | \"{title}\" | Priority: {priority} | Due: {due_date or 'not set'}"


@tool
def list_tasks(filter_status: str = "all", filter_priority: str = "all") -> str:
    """
    List all tasks. Optionally filter by status or priority.
    Args:
        filter_status: Filter by status — 'all', 'pending', or 'completed'. Defaults to 'all'.
        filter_priority: Filter by priority — 'all', 'high', 'medium', or 'low'. Defaults to 'all'.
    Returns a formatted list of tasks.
    """
    tasks = _load_tasks()

    if filter_status != "all":
        tasks = [t for t in tasks if t["status"] == filter_status]
    if filter_priority != "all":
        tasks = [t for t in tasks if t["priority"] == filter_priority]

    if not tasks:
        return "No tasks found."

    lines = []
    for t in tasks:
        status_icon = "✓" if t["status"] == "completed" else "○"
        due = f" | Due: {t['due_date']}" if t.get("due_date") else ""
        lines.append(
            f"[{status_icon}] ID:{t['id']} | {t['title']} | Priority: {t['priority']}{due}"
        )
    return "\n".join(lines)


@tool
def complete_task(task_id: str) -> str:
    """
    Mark a task as completed by its ID.
    Args:
        task_id: The short ID of the task to complete.
    Returns a confirmation message.
    """
    tasks = _load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            if task["status"] == "completed":
                return f"Task {task_id} is already completed."
            task["status"] = "completed"
            _save_tasks(tasks)
            return f"Task {task_id} \"{task['title']}\" marked as completed!"
    return f"Task with ID {task_id} not found."


@tool
def delete_task(task_id: str) -> str:
    """
    Delete a task permanently by its ID.
    Args:
        task_id: The short ID of the task to delete.
    Returns a confirmation message.
    """
    tasks = _load_tasks()
    new_tasks = [t for t in tasks if t["id"] != task_id]
    if len(new_tasks) == len(tasks):
        return f"Task with ID {task_id} not found."
    _save_tasks(new_tasks)
    return f"Task {task_id} deleted successfully."


@tool
def update_task(task_id: str, title: str = "", priority: str = "", due_date: str = "") -> str:
    """
    Update an existing task's title, priority, or due date.
    Args:
        task_id: The short ID of the task to update.
        title: New task title (leave empty to keep current).
        priority: New priority — 'high', 'medium', or 'low' (leave empty to keep current).
        due_date: New due date in YYYY-MM-DD format (leave empty to keep current).
    Returns a confirmation message.
    """
    tasks = _load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            if title:
                task["title"] = title
            if priority:
                task["priority"] = priority.lower()
            if due_date:
                task["due_date"] = due_date
            _save_tasks(tasks)
            return f"Task {task_id} updated: \"{task['title']}\" | Priority: {task['priority']} | Due: {task.get('due_date') or 'not set'}"
    return f"Task with ID {task_id} not found."


ALL_TOOLS = [add_task, list_tasks, complete_task, delete_task, update_task]
