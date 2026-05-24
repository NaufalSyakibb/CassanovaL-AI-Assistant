"""
Sentinel tools for Alfred — cross-domain life monitoring.

Reads data from all other agents' storage (tasks, budget, food_log, journal)
to generate proactive daily briefs without the user needing to ask.

Tools:
  get_overdue_tasks()   — overdue + due-today task alerts
  get_budget_status()   — monthly surplus/deficit, goal alerts, upcoming bills
  get_fitness_gaps()    — food log gaps + today's calorie count
  get_mood_trend()      — last 7 days mood from journal frontmatter
  get_morning_brief()   — full daily digest across all domains (auto-saved)
"""
import json
import os
import re
from pathlib import Path
from datetime import datetime, date, timedelta
from langchain.tools import tool

_TASKS_FILE  = Path("data/tasks.json")
_BUDGET_FILE = Path("data/budget.json")
_FOOD_FILE   = Path("data/food_log.json")
_NOTIF_FILE  = Path("data/notifications.json")


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _journal_dir() -> Path | None:
    vault = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    if not vault:
        return None
    p = Path(vault) / "Dostoyevsky Agent"
    return p if p.exists() else None


# ── Raw functions (called directly by get_morning_brief) ─────────────────────

def _overdue_tasks() -> str:
    tasks = _load_json(_TASKS_FILE, [])
    today = date.today()

    overdue, due_today = [], []
    for t in tasks:
        if t.get("status") == "completed":
            continue
        raw = t.get("due_date", "").strip()[:10]
        if not raw:
            continue
        try:
            d = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            continue
        label = f"[{t.get('priority', 'medium').upper()}] {t['title']}"
        if d < today:
            overdue.append(f"  - {label} ({(today - d).days}d late)")
        elif d == today:
            due_today.append(f"  - {label}")

    total_pending = sum(1 for t in tasks if t.get("status") != "completed")
    parts = []
    if overdue:
        parts.append(f"OVERDUE ({len(overdue)}):\n" + "\n".join(overdue))
    if due_today:
        parts.append(f"DUE TODAY ({len(due_today)}):\n" + "\n".join(due_today))
    parts.append(f"Total pending: {total_pending}")
    return "\n\n".join(parts)


def _budget_status() -> str:
    budget = _load_json(_BUDGET_FILE, {})
    if not isinstance(budget, dict):
        return "Budget data unavailable."

    today = date.today()
    month_str = today.strftime("%Y-%m")

    txns = budget.get("transactions", [])
    month_txns = [t for t in txns if t.get("date", "").startswith(month_str)]

    income  = sum(t["amount"] for t in month_txns if t.get("type") == "income")
    expense = sum(t["amount"] for t in month_txns if t.get("type") == "expense")
    surplus = income - expense

    by_cat = {}
    for t in month_txns:
        if t.get("type") == "expense":
            cat = t.get("category", "other")
            by_cat[cat] = by_cat.get(cat, 0) + t["amount"]

    goals = budget.get("budget_goals", [])
    month_goals = [g for g in goals if g.get("month", "").startswith(month_str[:7])]
    alerts = []
    for g in month_goals:
        cat, limit = g.get("category", ""), g.get("monthly_limit", 0)
        actual = by_cat.get(cat, 0)
        pct = (actual / limit * 100) if limit > 0 else 0
        if pct >= 80:
            status = "OVER" if pct >= 100 else "WARNING"
            alerts.append(f"  - [{status}] {cat}: Rp{actual:,.0f} / Rp{limit:,.0f} ({pct:.0f}%)")

    recurring = budget.get("recurring", [])
    upcoming = []
    for r in recurring:
        nxt = r.get("next_date", "")[:10]
        if nxt:
            try:
                nd = datetime.strptime(nxt, "%Y-%m-%d").date()
                if today <= nd <= today + timedelta(days=7):
                    upcoming.append(f"  - {r.get('description', '?')} Rp{r.get('amount', 0):,.0f} on {nxt}")
            except ValueError:
                pass

    lines = [
        f"BUDGET — {today.strftime('%B %Y')}:",
        f"  Income:  Rp{income:,.0f}",
        f"  Expense: Rp{expense:,.0f}",
        f"  {'Surplus' if surplus >= 0 else 'DEFICIT'}: Rp{abs(surplus):,.0f}",
    ]
    if alerts:
        lines.append(f"\nGOAL ALERTS ({len(alerts)}):")
        lines.extend(alerts)
    if upcoming:
        lines.append(f"\nUPCOMING BILLS (next 7 days):")
        lines.extend(upcoming)
    return "\n".join(lines)


def _fitness_gaps() -> str:
    food_log = _load_json(_FOOD_FILE, {})
    today = date.today()

    gaps = []
    for i in range(1, 8):
        ds = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        if not food_log.get(ds):
            gaps.append(ds)

    today_entries = food_log.get(today.strftime("%Y-%m-%d"), [])
    today_cals = sum(e.get("calories", 0) for e in today_entries)

    lines = []
    if gaps:
        lines.append(f"FOOD LOG GAPS: {len(gaps)} day(s) missing in last 7 days")
        lines.append("  Missing: " + ", ".join(gaps[:5]))
    else:
        lines.append("Food log: complete for last 7 days")
    lines.append(f"Today: {len(today_entries)} entries, {today_cals:.0f} kcal logged")
    return "\n".join(lines)


def _mood_trend() -> str:
    jdir = _journal_dir()
    if not jdir:
        return "Journal unavailable (OBSIDIAN_VAULT_PATH not set)."

    today = date.today()
    moods = []
    for i in range(7):
        d = today - timedelta(days=i)
        fname = jdir / f"Journal_{d.strftime('%Y-%m-%d')}.md"
        if not fname.exists():
            continue
        try:
            text = fname.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"^mood:\s*(.+)$", text, re.MULTILINE)
            if m:
                moods.append(f"  {d.strftime('%Y-%m-%d')}: {m.group(1).strip()}")
        except Exception:
            pass

    if not moods:
        return "No journal entries found in last 7 days."
    return f"MOOD TREND ({len(moods)} entries):\n" + "\n".join(moods)


def _save_notification(brief: str) -> None:
    """Persist the morning brief to data/notifications.json."""
    try:
        data = _load_json(_NOTIF_FILE, {"notifications": []})
        if not isinstance(data, dict):
            data = {"notifications": []}
        today_str = date.today().strftime("%Y-%m-%d")
        data["notifications"] = [n for n in data["notifications"] if n.get("date") != today_str]
        data["notifications"].insert(0, {
            "id": f"brief-{today_str}",
            "date": today_str,
            "type": "morning_brief",
            "brief": brief,
            "read": False,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        data["notifications"] = data["notifications"][:30]
        _NOTIF_FILE.parent.mkdir(parents=True, exist_ok=True)
        _NOTIF_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


# ── LangChain @tool wrappers ──────────────────────────────────────────────────

@tool
def get_overdue_tasks() -> str:
    """Check for overdue and due-today tasks. Returns a priority-sorted alert list."""
    return _overdue_tasks()


@tool
def get_budget_status() -> str:
    """Check current month's budget health: surplus/deficit, goal adherence, and upcoming recurring bills."""
    return _budget_status()


@tool
def get_fitness_gaps() -> str:
    """Check food log gaps from the last 7 days and today's calorie tracking status."""
    return _fitness_gaps()


@tool
def get_mood_trend() -> str:
    """Check recent mood trend from Dostoyevsky journal entries over the last 7 days."""
    return _mood_trend()


@tool
def get_morning_brief() -> str:
    """
    Generate Alfred's morning brief: a synthesized daily digest across all life domains
    (tasks, budget, fitness, mood, conflicts, behavioral patterns).
    Automatically saved to notifications for the bell indicator.
    Call this to give the user a complete picture of where things stand.
    """
    day_str = datetime.now().strftime("%A, %d %B %Y")

    sections = [
        f"# Morning Brief — {day_str}\n",
        f"## Tasks\n{_overdue_tasks()}",
        f"## Budget\n{_budget_status()}",
        f"## Fitness\n{_fitness_gaps()}",
        f"## Mood\n{_mood_trend()}",
    ]

    # Contradiction Detector — add Conflicts section if any found
    try:
        from tools.contradiction_tools import get_all_contradictions
        conflicts = get_all_contradictions()
        if conflicts:
            sections.append("## Conflicts\n" + "\n".join(f"  {c}" for c in conflicts))
    except Exception:
        pass

    # Behavioral Pattern Engine — add Patterns section if insights exist
    try:
        from tools.pattern_tools import compute_patterns
        result = compute_patterns(30)
        insights = result.get("insights", [])
        coverage = result.get("data_coverage_days", 0)
        if insights and coverage >= 14:
            sections.append("## Patterns\n" + "\n".join(f"  {ins}" for ins in insights))
    except Exception:
        pass

    brief = "\n\n".join(sections)
    _save_notification(brief)
    return brief


SENTINEL_TOOLS = [get_overdue_tasks, get_budget_status, get_fitness_gaps, get_mood_trend, get_morning_brief]
