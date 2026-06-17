"""
cli_lavoisier.py — Dedicated Lavoisier (food & nutrition) CLI.

Usage:
    $env:PYTHONUTF8=1; python cli_lavoisier.py

Chat naturally:
    "log white rice 200g for lunch"
    "I just ate 2 fried eggs and 100g tofu"
    "how much protein have I had today?"
    "what's the nutritional value of an avocado?"

Data is saved permanently to data/food_log.json.
"""

import sys
import io
import json
from pathlib import Path
from datetime import date, datetime

# Fix Windows terminal encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

_BASE = Path(__file__).resolve().parent
_FOOD_LOG = _BASE / "data" / "food_log.json"


BANNER = """
╔══════════════════════════════════════════════════════════╗
║  🥗  Lavoisier — Nutrition & Food Tracker CLI            ║
╠══════════════════════════════════════════════════════════╣
║  Tell me what you ate and I'll log it with full macros.  ║
║  Ask about nutrition, calories, or review your day.      ║
║                                                          ║
║  Examples:                                               ║
║   "log white rice 200g for lunch"                        ║
║   "I ate 2 fried eggs this morning"                      ║
║   "how many calories have I had today?"                  ║
║   "what macros does chicken breast have?"                ║
║   "show today's log"                                     ║
║                                                          ║
║  Type 'quit' or 'exit' to stop.                          ║
╚══════════════════════════════════════════════════════════╝
"""


def _load_log() -> dict:
    try:
        return json.loads(_FOOD_LOG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _show_today_summary():
    raw = _load_log()
    today = date.today().strftime("%Y-%m-%d")
    entries = raw.get(today, [])

    if not entries:
        print("\n  📋 Today's log is empty — tell me what you ate!\n")
        return

    cal   = sum(e.get("calories",  0) for e in entries)
    pro   = sum(e.get("protein_g", 0) for e in entries)
    carb  = sum(e.get("carbs_g",   0) for e in entries)
    fat   = sum(e.get("fat_g",     0) for e in entries)
    fib   = sum(e.get("fiber_g",   0) for e in entries)

    print(f"\n  📅 Today's Food Log — {today}")
    print("  " + "─" * 44)

    groups: dict = {}
    for e in entries:
        m = (e.get("meal_time") or "lainnya").capitalize()
        groups.setdefault(m, []).append(e)

    for meal, items in groups.items():
        print(f"\n  🍽️  {meal}")
        for e in items:
            print(f"     • {e['food']} ({e.get('amount','?')})  🔥{e.get('calories',0)} kcal")

    print(f"\n  " + "─" * 44)
    print(f"  🔥 Calories : {round(cal)} kcal")
    print(f"  🔴 Protein  : {round(pro, 1)} g")
    print(f"  🟡 Carbs    : {round(carb, 1)} g")
    print(f"  ⚪ Fat      : {round(fat, 1)} g")
    print(f"  🟢 Fiber    : {round(fib, 1)} g")
    print()


def main():
    print(BANNER)
    _show_today_summary()

    try:
        from router import SupervisorRouter
        router = SupervisorRouter()
    except ValueError as e:
        print(f"  Error loading agent: {e}")
        sys.exit(1)

    print("  Lavoisier is ready. What did you eat?\n")

    while True:
        try:
            user_input = input("  You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye! Stay healthy! 🥗")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "keluar", "bye"):
            print("  Goodbye! Stay healthy! 🥗")
            break

        if user_input.lower() in ("log", "today", "summary"):
            _show_today_summary()
            continue

        try:
            _, response = router.chat_direct("fitness", user_input)
            print(f"\n  [ LAVOISIER ]\n  {response}\n")
        except Exception as e:
            print(f"\n  Error: {e}\n")


if __name__ == "__main__":
    main()
