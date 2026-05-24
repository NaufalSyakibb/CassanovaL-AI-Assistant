"""
Contradiction Detector — Background guardian that catches logical conflicts
across life domains that no single agent would notice.

Conflicts detected:
  1. Recurring bills > budget goal for same category
  2. Total monthly obligations > average monthly income (can't save target)
  3. 7-day calorie average deviates >30% from default 2000 kcal target
  4. High-priority tasks due soon but budget shows financial stress simultaneously
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

_BUDGET_FILE = Path("data/budget.json")
_FOOD_FILE   = Path("data/food_log.json")
_TASKS_FILE  = Path("data/tasks.json")
_CALORIE_TARGET = 2000  # kcal/day default


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def check_budget_conflicts() -> list[str]:
    """Detect when recurring bill amounts exceed budget goals for same category."""
    budget = _load(_BUDGET_FILE, {})
    if not isinstance(budget, dict):
        return []

    today = date.today()
    month_str = today.strftime("%Y-%m")

    recurring = budget.get("recurring", [])
    goals     = budget.get("budget_goals", [])
    month_goals = {g["category"]: g["monthly_limit"] for g in goals
                   if g.get("month", "").startswith(month_str[:7]) and g.get("monthly_limit", 0) > 0}

    # Group recurring by category
    recurring_by_cat: dict[str, float] = {}
    for r in recurring:
        cat = r.get("category", "other")
        recurring_by_cat[cat] = recurring_by_cat.get(cat, 0) + r.get("amount", 0)

    conflicts = []
    for cat, goal_limit in month_goals.items():
        rec_total = recurring_by_cat.get(cat, 0)
        if rec_total > goal_limit:
            conflicts.append(
                f"CONFLICT: Recurring '{cat}' bills = Rp{rec_total:,.0f}/mo "
                f"exceeds budget goal of Rp{goal_limit:,.0f}/mo — goal is unreachable"
            )
    return conflicts


def check_income_vs_obligations() -> list[str]:
    """Detect when total recurring obligations > average monthly income."""
    budget = _load(_BUDGET_FILE, {})
    if not isinstance(budget, dict):
        return []

    txns = budget.get("transactions", [])
    recurring = budget.get("recurring", [])

    # Average monthly income over last 3 months
    today = date.today()
    monthly_income: dict[str, float] = {}
    for t in txns:
        if t.get("type") != "income":
            continue
        m = t.get("date", "")[:7]
        if not m:
            continue
        monthly_income[m] = monthly_income.get(m, 0) + t.get("amount", 0)

    if not monthly_income:
        return []

    # Use last 3 months only
    sorted_months = sorted(monthly_income.keys(), reverse=True)[:3]
    avg_income = sum(monthly_income[m] for m in sorted_months) / len(sorted_months)

    total_recurring = sum(r.get("amount", 0) for r in recurring)

    if total_recurring > avg_income * 0.8:
        pct = total_recurring / avg_income * 100
        return [
            f"CONFLICT: Monthly recurring obligations = Rp{total_recurring:,.0f} "
            f"({pct:.0f}% of avg income Rp{avg_income:,.0f}) — "
            f"leaves only Rp{avg_income - total_recurring:,.0f} for variable spending + savings"
        ]
    return []


def check_calorie_consistency() -> list[str]:
    """Detect when 7-day average calories deviates significantly from 2000 kcal target."""
    food_log = _load(_FOOD_FILE, {})
    today = date.today()

    daily_cals = []
    for i in range(1, 8):
        ds = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        entries = food_log.get(ds, [])
        if entries:
            total = sum(e.get("calories", 0) for e in entries)
            daily_cals.append(total)

    if len(daily_cals) < 3:
        return []

    avg = sum(daily_cals) / len(daily_cals)
    deviation_pct = abs(avg - _CALORIE_TARGET) / _CALORIE_TARGET * 100

    if deviation_pct > 30:
        direction = "under" if avg < _CALORIE_TARGET else "over"
        return [
            f"CONFLICT: 7-day avg calories = {avg:.0f} kcal "
            f"({deviation_pct:.0f}% {direction} the {_CALORIE_TARGET} kcal target) — "
            f"{'risk of under-fueling' if direction == 'under' else 'excess caloric intake'}"
        ]
    return []


def check_deadline_pressure() -> list[str]:
    """Detect high-priority tasks due within 2 days alongside budget stress."""
    tasks  = _load(_TASKS_FILE, [])
    budget = _load(_BUDGET_FILE, {})
    today  = date.today()

    urgent_tasks = []
    for t in tasks:
        if t.get("status") == "completed":
            continue
        if t.get("priority") not in ("high", "critical"):
            continue
        raw = t.get("due_date", "").strip()[:10]
        if not raw:
            continue
        try:
            d = datetime.strptime(raw, "%Y-%m-%d").date()
            if d <= today + timedelta(days=2):
                urgent_tasks.append(t["title"])
        except ValueError:
            pass

    if not urgent_tasks:
        return []

    # Check if budget is also stressed this month
    month_str = today.strftime("%Y-%m")
    txns = budget.get("transactions", []) if isinstance(budget, dict) else []
    month_txns = [t for t in txns if t.get("date", "").startswith(month_str)]
    income  = sum(t["amount"] for t in month_txns if t.get("type") == "income")
    expense = sum(t["amount"] for t in month_txns if t.get("type") == "expense")

    conflicts = []
    if income > 0 and expense > income * 0.9:
        task_list = ", ".join(f'"{t}"' for t in urgent_tasks[:3])
        conflicts.append(
            f"CONFLICT: {len(urgent_tasks)} urgent task(s) due within 2 days "
            f"({task_list}) while budget is under pressure this month — "
            f"high stress load detected"
        )
    return conflicts


def get_all_contradictions() -> list[str]:
    """Run all conflict detectors and return the combined list of conflicts."""
    conflicts: list[str] = []
    for fn in (check_budget_conflicts, check_income_vs_obligations,
               check_calorie_consistency, check_deadline_pressure):
        try:
            conflicts.extend(fn())
        except Exception:
            pass
    return conflicts
