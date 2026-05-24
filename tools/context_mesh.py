"""
Context Mesh — Silent pre-agent life state injector.

Reads cross-domain personal data (tasks, budget, fitness, mood) and returns
a brief alert string when something notable is happening. Injected as a
SystemMessage into every agent conversation by router.py — invisible to the
user, visible to the agent.

Design principles:
- Pure JSON/file reads only — no LLM call, no network, < 50ms
- Silent when life is fine (returns "")
- Only surfaces actionable alerts, not full data dumps
"""

import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path

_TASKS_FILE  = Path("data/tasks.json")
_BUDGET_FILE = Path("data/budget.json")
_FOOD_FILE   = Path("data/food_log.json")

_NEGATIVE_MOODS = {
    "stressed", "stress", "anxious", "anxiety", "sad", "sedih", "lelah",
    "capek", "overwhelmed", "frustrated", "frustrasi", "burnout", "tired",
    "exhausted", "down", "depressed", "depresi", "worry", "khawatir",
}


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _task_alerts() -> list[str]:
    tasks = _load(_TASKS_FILE, [])
    today = date.today()
    overdue, due_today = 0, 0
    for t in tasks:
        if t.get("status") == "completed":
            continue
        raw = t.get("due_date", "").strip()[:10]
        if not raw:
            continue
        try:
            d = datetime.strptime(raw, "%Y-%m-%d").date()
            if d < today:
                overdue += 1
            elif d == today:
                due_today += 1
        except ValueError:
            pass
    alerts = []
    if overdue:
        alerts.append(f"{overdue} overdue task(s) — user has unfinished work past deadline")
    if due_today:
        alerts.append(f"{due_today} task(s) due today — user needs to complete these today")
    return alerts


def _budget_alerts() -> list[str]:
    budget = _load(_BUDGET_FILE, {})
    if not isinstance(budget, dict):
        return []

    today = date.today()
    month_str = today.strftime("%Y-%m")
    txns = budget.get("transactions", [])
    month_txns = [t for t in txns if t.get("date", "").startswith(month_str)]

    income  = sum(t["amount"] for t in month_txns if t.get("type") == "income")
    expense = sum(t["amount"] for t in month_txns if t.get("type") == "expense")

    alerts = []
    if income > 0 and expense > income:
        deficit = expense - income
        alerts.append(f"Budget deficit this month: Rp{deficit:,.0f} overspent vs income")

    # Check budget goals >80% consumed
    by_cat = {}
    for t in month_txns:
        if t.get("type") == "expense":
            cat = t.get("category", "other")
            by_cat[cat] = by_cat.get(cat, 0) + t["amount"]

    goals = budget.get("budget_goals", [])
    for g in goals:
        if not g.get("month", "").startswith(month_str[:7]):
            continue
        cat   = g.get("category", "")
        limit = g.get("monthly_limit", 0)
        if limit <= 0:
            continue
        actual = by_cat.get(cat, 0)
        pct = actual / limit * 100
        if pct >= 100:
            alerts.append(f"Budget goal exceeded: {cat} at {pct:.0f}% of monthly limit")
        elif pct >= 80:
            alerts.append(f"Budget goal warning: {cat} at {pct:.0f}% of monthly limit")

    return alerts


def _fitness_alerts() -> list[str]:
    food_log = _load(_FOOD_FILE, {})
    today = date.today()
    gap_days = 0
    for i in range(1, 5):  # check last 4 days
        ds = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        if not food_log.get(ds):
            gap_days += 1
    if gap_days >= 2:
        return [f"Fitness tracking gap: {gap_days} of last 4 days with no food log"]
    return []


def _mood_alerts() -> list[str]:
    vault = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    if not vault:
        return []
    jdir = Path(vault) / "Dostoyevsky Agent"
    if not jdir.exists():
        return []

    today = date.today()
    negative_count = 0
    checked = 0
    for i in range(3):
        d = today - timedelta(days=i)
        fname = jdir / f"Journal_{d.strftime('%Y-%m-%d')}.md"
        if not fname.exists():
            continue
        try:
            text = fname.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"^mood:\s*(.+)$", text, re.MULTILINE)
            if m:
                checked += 1
                mood_val = m.group(1).strip().lower()
                if any(neg in mood_val for neg in _NEGATIVE_MOODS):
                    negative_count += 1
        except Exception:
            pass

    if checked >= 2 and negative_count >= 2:
        return [f"Recent mood trend: negative ({negative_count}/{checked} recent journal entries)"]
    return []


def get_life_snapshot() -> str:
    """
    Returns a SystemMessage-ready string summarizing the user's current life state.
    Returns empty string if nothing notable — agent gets no extra context when
    everything is fine (keeps context clean and fast).
    """
    alerts: list[str] = []
    try:
        alerts += _task_alerts()
    except Exception:
        pass
    try:
        alerts += _budget_alerts()
    except Exception:
        pass
    try:
        alerts += _fitness_alerts()
    except Exception:
        pass
    try:
        alerts += _mood_alerts()
    except Exception:
        pass

    if not alerts:
        return ""

    lines = [
        "[LIFE CONTEXT — injected automatically, not visible to user]",
        f"Date: {date.today().strftime('%A, %d %B %Y')}",
        "Current alerts from user's personal data:",
    ]
    for a in alerts:
        lines.append(f"  • {a}")
    lines.append(
        "Use this context to give more relevant, personalized advice. "
        "Do not explicitly mention this system context unless directly relevant."
    )
    return "\n".join(lines)
