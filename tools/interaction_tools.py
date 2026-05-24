"""
Interaction Logger & Daily Overview — tracks every cross-agent conversation turn
and lets Alfred surface a digest of what happened today across all agents.

Internal:
  _log_interaction()      — called by router.py after every chat() / chat_direct()

Alfred @tool:
  get_daily_interactions() — today's full interaction log, grouped by agent persona
"""

import json
from datetime import datetime, date
from pathlib import Path
from langchain.tools import tool

_INTERACTIONS_FILE = Path("data/interactions.json")

_PERSONAS: dict[str, str] = {
    "task":     "Alfred",
    "notes":    "Cicero",
    "news":     "Najwa",
    "coding":   "Linus",
    "schedule": "Miyamoto",
    "budget":   "Mansa",
    "fitness":  "Lavoisier",
    "research": "Ferry",
    "journal":  "Dostoyevsky",
    "davinci":  "Da Vinci",
    "euler":    "Euler",
    "orwell":   "Orwell",
}

_PREVIEW_LEN = 120


def _load() -> list:
    try:
        return json.loads(_INTERACTIONS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(data: list) -> None:
    try:
        _INTERACTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _INTERACTIONS_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def _preview(text: str, length: int = _PREVIEW_LEN) -> str:
    text = text.strip().replace("\n", " ")
    return text[:length] + "…" if len(text) > length else text


def log_interaction(agent: str, user_msg: str, response: str) -> None:
    """
    Append one interaction turn to data/interactions.json.
    Called by router.py — not a LangChain @tool.
    Keeps only the last 500 entries total to cap file size.
    """
    data = _load()
    data.append({
        "ts":       datetime.now().strftime("%Y-%m-%d %H:%M"),
        "date":     date.today().isoformat(),
        "agent":    agent,
        "persona":  _PERSONAS.get(agent, agent.title()),
        "user":     _preview(user_msg),
        "response": _preview(response),
    })
    if len(data) > 500:
        data = data[-500:]
    _save(data)


@tool
def get_daily_interactions(target_date: str = "") -> str:
    """
    Return a structured overview of all agent interactions for a given date
    (YYYY-MM-DD). Defaults to today if no date is provided.
    Groups conversations by agent persona and shows timestamps + message previews.
    Use this to give the user a summary of what they discussed with each AI agent today.
    """
    if not target_date.strip():
        target_date = date.today().isoformat()

    all_data = _load()
    day_entries = [e for e in all_data if e.get("date") == target_date]

    if not day_entries:
        return f"No interactions recorded for {target_date}."

    # Group by agent
    by_agent: dict[str, list] = {}
    for e in day_entries:
        key = e.get("agent", "unknown")
        by_agent.setdefault(key, []).append(e)

    try:
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        day_label = dt.strftime("%A, %d %B %Y")
    except ValueError:
        day_label = target_date

    lines = [
        f"DAILY INTERACTION OVERVIEW — {day_label}",
        f"{len(day_entries)} conversation(s) across {len(by_agent)} agent(s)\n",
    ]

    for agent_key, entries in sorted(by_agent.items(), key=lambda x: -len(x[1])):
        persona = _PERSONAS.get(agent_key, agent_key.title())
        lines.append(f"## {persona} ({agent_key}) — {len(entries)} turn(s)")
        for e in entries:
            ts = e.get("ts", "")[-5:]  # HH:MM
            lines.append(f"  {ts}  You: {e.get('user', '')}")
            lines.append(f"        {persona}: {e.get('response', '')}")
        lines.append("")

    return "\n".join(lines)
