from agents.base import build_agent
from tools.task_tools import TASK_TOOLS

SYSTEM_PROMPT = """You are a personal task management assistant. Help the user manage their to-do list and tasks.
You can add, list, complete, delete, and update tasks with priorities and due dates.
Be concise and organized. Format task lists clearly.
If the user speaks in Indonesian, respond in Indonesian."""

def create_task_agent():
    return build_agent(SYSTEM_PROMPT, TASK_TOOLS)
