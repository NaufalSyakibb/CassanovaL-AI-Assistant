"""
Behavioral Pattern Engine — Mines accumulated personal data for cross-domain
behavioral correlations. Requires ≥14 days of overlapping data to be meaningful.

Correlations computed:
  1. Task completion rate by calorie bucket (under/in-range/over target)
  2. Average daily spending on negative-mood days vs other days
  3. Pearson correlation between food-log presence and task completions that day

Uses scipy.stats.pearsonr (already in requirements.txt).
"""

import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from langchain.tools import tool

_TASKS_FILE  = Path("data/tasks.json")
_BUDGET_FILE = Path("data/budget.json")
_FOOD_FILE   = Path("data/food_log.json")

_NEGATIVE_MOODS = {
    "stressed", "stress", "anxious", "sad", "sedih", "lelah", "capek",
    "overwhelmed", "frustrated", "frustrasi", "burnout", "tired",
    "exhausted", "down", "depressed", "worry", "khawatir",
}
_CALORIE_TARGET = 2000


def _load(path: Path, default):
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


def _get_mood_map(days: int) -> dict[str, bool]:
    """Returns {date_str: is_negative} for available journal entries."""
    jdir = _journal_dir()
    if not jdir:
        return {}
    today = date.today()
    mood_map: dict[str, bool] = {}
    for i in range(days):
        d = today - timedelta(days=i + 1)
        fname = jdir / f"Journal_{d.strftime('%Y-%m-%d')}.md"
        if not fname.exists():
            continue
        try:
            text = fname.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"^mood:\s*(.+)$", text, re.MULTILINE)
            if m:
                mood_val = m.group(1).strip().lower()
                is_negative = any(neg in mood_val for neg in _NEGATIVE_MOODS)
                mood_map[d.strftime("%Y-%m-%d")] = is_negative
        except Exception:
            pass
    return mood_map


def compute_patterns(days: int = 30) -> dict:
    """
    Compute behavioral patterns from the last N days of personal data.

    Returns a dict with:
      - task_completion_by_calorie_bucket: avg completion rate per calorie range
      - spend_on_negative_mood_days: avg daily spend on bad mood vs other days
      - fitness_task_correlation: Pearson r between food_log presence and tasks done
      - data_coverage: days with overlapping multi-domain data
      - insights: list of plain-language insight strings (empty if < 14 days coverage)
    """
    today = date.today()
    tasks  = _load(_TASKS_FILE, [])
    budget = _load(_BUDGET_FILE, {})
    food   = _load(_FOOD_FILE, {})
    mood_map = _get_mood_map(days)

    txns = budget.get("transactions", []) if isinstance(budget, dict) else []

    # ── Build per-day records ─────────────────────────────────────────────────
    day_records: list[dict] = []
    for i in range(1, days + 1):
        d = today - timedelta(days=i)
        ds = d.strftime("%Y-%m-%d")

        # Food
        food_entries = food.get(ds, [])
        calories = sum(e.get("calories", 0) for e in food_entries)
        has_food_log = len(food_entries) > 0

        # Tasks completed on this day
        tasks_done = sum(
            1 for t in tasks
            if t.get("status") == "completed"
            and t.get("due_date", "").startswith(ds)
        )
        # Tasks pending at start of day (rough: all tasks created before this date)
        tasks_pending = sum(
            1 for t in tasks
            if t.get("status") != "completed"
            or t.get("due_date", "").startswith(ds)
        )
        completion_rate = (tasks_done / tasks_pending) if tasks_pending > 0 else None

        # Daily spending
        daily_spend = sum(
            t.get("amount", 0) for t in txns
            if t.get("type") == "expense" and t.get("date", "").startswith(ds)
        )

        # Mood
        is_negative_mood = mood_map.get(ds)  # None = no entry

        day_records.append({
            "date":           ds,
            "calories":       calories,
            "has_food_log":   has_food_log,
            "tasks_done":     tasks_done,
            "completion_rate": completion_rate,
            "daily_spend":    daily_spend,
            "is_negative_mood": is_negative_mood,
        })

    # ── 1. Task completion rate by calorie bucket ─────────────────────────────
    buckets: dict[str, list[float]] = {
        "under_1500": [], "1500_2000": [], "over_2000": []
    }
    for r in day_records:
        if r["completion_rate"] is None or not r["has_food_log"]:
            continue
        cal = r["calories"]
        if cal < 1500:
            buckets["under_1500"].append(r["completion_rate"])
        elif cal <= 2000:
            buckets["1500_2000"].append(r["completion_rate"])
        else:
            buckets["over_2000"].append(r["completion_rate"])

    task_by_cal = {
        k: round(sum(v) / len(v) * 100, 1) if v else None
        for k, v in buckets.items()
    }

    # ── 2. Spending on negative mood days vs other days ───────────────────────
    neg_spends  = [r["daily_spend"] for r in day_records if r["is_negative_mood"] is True  and r["daily_spend"] > 0]
    pos_spends  = [r["daily_spend"] for r in day_records if r["is_negative_mood"] is False and r["daily_spend"] > 0]
    avg_neg_spend = round(sum(neg_spends) / len(neg_spends), 0) if neg_spends else None
    avg_pos_spend = round(sum(pos_spends) / len(pos_spends), 0) if pos_spends else None

    # ── 3. Fitness-task correlation ───────────────────────────────────────────
    fitness_task_r = None
    paired = [(r["has_food_log"], r["tasks_done"]) for r in day_records]
    if len(paired) >= 10:
        try:
            from scipy.stats import pearsonr
            xs = [float(p[0]) for p in paired]
            ys = [float(p[1]) for p in paired]
            if len(set(xs)) > 1 and len(set(ys)) > 1:
                r_val, _ = pearsonr(xs, ys)
                fitness_task_r = round(float(r_val), 3)
        except Exception:
            pass

    # ── Data coverage ─────────────────────────────────────────────────────────
    multi_domain_days = sum(
        1 for r in day_records
        if r["has_food_log"] and (r["tasks_done"] > 0 or r["completion_rate"] is not None)
    )

    # ── Insights (only when sufficient data) ──────────────────────────────────
    insights: list[str] = []
    if multi_domain_days < 14:
        days_needed = 14 - multi_domain_days
        insights.append(
            f"Not enough overlapping data yet — need {days_needed} more days with "
            f"both food logs and task activity to surface meaningful patterns."
        )
    else:
        # Task completion by calorie
        if task_by_cal.get("under_1500") is not None and task_by_cal.get("1500_2000") is not None:
            diff = task_by_cal["1500_2000"] - task_by_cal["under_1500"]
            if abs(diff) >= 10:
                direction = "higher" if diff > 0 else "lower"
                insights.append(
                    f"Nutrition-productivity link: task completion is {abs(diff):.0f}% {direction} "
                    f"on days with 1500–2000 kcal vs under-1500 kcal days."
                )

        # Mood-spending correlation
        if avg_neg_spend is not None and avg_pos_spend is not None:
            diff = avg_neg_spend - avg_pos_spend
            if abs(diff) > 20_000:
                direction = "more" if diff > 0 else "less"
                insights.append(
                    f"Mood-spending pattern: you spend Rp{abs(diff):,.0f} {direction} per day "
                    f"on stressed/negative days (Rp{avg_neg_spend:,.0f}) vs positive days (Rp{avg_pos_spend:,.0f})."
                )

        # Fitness-task correlation
        if fitness_task_r is not None and abs(fitness_task_r) >= 0.25:
            strength = "strong" if abs(fitness_task_r) >= 0.5 else "moderate"
            direction = "positive" if fitness_task_r > 0 else "negative"
            insights.append(
                f"Habit link ({strength} {direction} correlation r={fitness_task_r}): "
                f"days when you log food tend to {'also have more' if fitness_task_r > 0 else 'have fewer'} "
                f"task completions — tracking fitness and productivity reinforce each other."
            )

    return {
        "task_completion_by_calorie_bucket": task_by_cal,
        "avg_spend_negative_mood_days":      avg_neg_spend,
        "avg_spend_positive_mood_days":      avg_pos_spend,
        "fitness_task_correlation":          fitness_task_r,
        "data_coverage_days":                multi_domain_days,
        "insights":                          insights,
        "days_analyzed":                     days,
    }


@tool
def get_behavioral_patterns(days: int = 30) -> str:
    """
    Analyze behavioral patterns from the last N days of personal data.
    Finds correlations between nutrition, task productivity, mood, and spending.
    Requires at least 14 days of overlapping data to surface meaningful insights.
    """
    result = compute_patterns(days)
    lines = [f"Behavioral Pattern Analysis — last {days} days\n"]

    insights = result.get("insights", [])
    if insights:
        lines.append("INSIGHTS:")
        for ins in insights:
            lines.append(f"  • {ins}")
    else:
        lines.append("No insights yet (insufficient overlapping data).")

    lines.append("\nRAW METRICS:")
    cal_buckets = result.get("task_completion_by_calorie_bucket", {})
    if any(v is not None for v in cal_buckets.values()):
        lines.append("  Task completion by calorie intake:")
        for k, v in cal_buckets.items():
            label = k.replace("_", " ").replace("under", "<").replace("over", ">")
            lines.append(f"    {label} kcal: {v}% completion" if v is not None else f"    {label} kcal: no data")

    neg = result.get("avg_spend_negative_mood_days")
    pos = result.get("avg_spend_positive_mood_days")
    if neg is not None or pos is not None:
        lines.append(f"  Avg daily spend — negative mood: Rp{neg:,.0f}" if neg else "  Avg daily spend — negative mood: no data")
        lines.append(f"  Avg daily spend — positive mood: Rp{pos:,.0f}" if pos else "  Avg daily spend — positive mood: no data")

    r_val = result.get("fitness_task_correlation")
    lines.append(f"  Fitness-task correlation (Pearson r): {r_val}" if r_val is not None else "  Fitness-task correlation: insufficient data")
    lines.append(f"  Data coverage: {result.get('data_coverage_days', 0)} days with multi-domain overlap")

    return "\n".join(lines)
