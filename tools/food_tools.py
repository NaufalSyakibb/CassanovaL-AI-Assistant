"""
Daily food / nutrition logging tools for Lavoiser fitness agent.

Data is stored in data/food_log.json with dates (YYYY-MM-DD) as top-level keys.
Each entry records one food item with macro breakdown (protein, carbs, fiber, fat, calories).
"""
import json
import uuid
import os
from datetime import datetime, date, timedelta
from langchain.tools import tool
from tools.obsidian_tools import mirror_to_obsidian

FOOD_LOG_FILE = "data/food_log.json"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load() -> dict:
    try:
        with open(FOOD_LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(data: dict):
    os.makedirs(os.path.dirname(FOOD_LOG_FILE), exist_ok=True)
    with open(FOOD_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    try:
        _mirror(data)
    except Exception:
        pass  # Obsidian sync failure must never break the save


def _mirror(data: dict) -> None:
    """Mirror each day's food log to Obsidian AI Data/Food Log/YYYY-MM-DD.md"""
    for day, entries in data.items():
        if not entries:
            continue
        total_cal  = sum(e.get("calories", 0)  for e in entries)
        total_pro  = sum(e.get("protein_g", 0) for e in entries)
        total_carb = sum(e.get("carbs_g", 0)   for e in entries)
        total_fib  = sum(e.get("fiber_g", 0)   for e in entries)
        total_fat  = sum(e.get("fat_g", 0)     for e in entries)

        lines = [
            "---",
            f"date: {day}",
            f"calories: {round(total_cal)}",
            f"protein_g: {round(total_pro, 1)}",
            f"carbs_g: {round(total_carb, 1)}",
            f"fiber_g: {round(total_fib, 1)}",
            f"fat_g: {round(total_fat, 1)}",
            "---",
            "",
            f"# Food Log — {day}",
            "",
        ]

        # Group by meal_time
        groups: dict[str, list] = {}
        for e in entries:
            groups.setdefault((e.get("meal_time") or "lainnya").capitalize(), []).append(e)

        for meal, items in groups.items():
            lines += [
                f"## 🍽️ {meal}",
                "| Makanan | Porsi | Protein | Karbo | Serat | Lemak | Kalori |",
                "|---------|-------|---------|-------|-------|-------|--------|",
            ]
            for e in items:
                lines.append(
                    f"| {e['food']} | {e.get('amount','?')} | {e.get('protein_g',0)}g | "
                    f"{e.get('carbs_g',0)}g | {e.get('fiber_g',0)}g | "
                    f"{e.get('fat_g',0)}g | {e.get('calories',0)} kkal |"
                )
            lines.append("")

        lines += [
            "## 📊 Total Harian",
            "| Protein | Karbo | Serat | Lemak | Kalori |",
            "|---------|-------|-------|-------|--------|",
            f"| {round(total_pro,1)}g | {round(total_carb,1)}g | {round(total_fib,1)}g | {round(total_fat,1)}g | {round(total_cal)} kkal |",
        ]
        mirror_to_obsidian("AI Data/Food Log", f"{day}.md", "\n".join(lines))


def _today() -> str:
    return date.today().strftime("%Y-%m-%d")


def _format_log_table(entries: list, date_label: str) -> str:
    """Format a list of food entries as a readable text table."""
    if not entries:
        return f"Belum ada makanan yang dicatat untuk {date_label}."

    # Totals
    total_cal  = sum(e.get("calories", 0)  for e in entries)
    total_pro  = sum(e.get("protein_g", 0) for e in entries)
    total_carb = sum(e.get("carbs_g", 0)   for e in entries)
    total_fib  = sum(e.get("fiber_g", 0)   for e in entries)
    total_fat  = sum(e.get("fat_g", 0)     for e in entries)

    # Group by meal_time
    groups: dict[str, list] = {}
    for e in entries:
        meal = (e.get("meal_time") or "lainnya").capitalize()
        groups.setdefault(meal, []).append(e)

    lines = [f"📅 Log Makan — {date_label}", "─" * 46]
    for meal, items in groups.items():
        lines.append(f"\n🍽️  {meal}")
        for e in items:
            pro  = e.get("protein_g", 0)
            carb = e.get("carbs_g", 0)
            fib  = e.get("fiber_g", 0)
            fat  = e.get("fat_g", 0)
            cal  = e.get("calories", 0)
            lines.append(
                f"  [{e['id']}] {e['food']} ({e.get('amount','?')})\n"
                f"        🔴 Protein {pro}g  🟡 Karbo {carb}g  🟢 Serat {fib}g  ⚪ Lemak {fat}g  🔥 {cal} kkal"
            )

    lines.append("\n" + "─" * 46)
    lines.append("📊 TOTAL HARI INI")
    lines.append(f"  🔴 Protein  : {round(total_pro, 1)} g")
    lines.append(f"  🟡 Karbo    : {round(total_carb, 1)} g")
    lines.append(f"  🟢 Serat    : {round(total_fib, 1)} g")
    lines.append(f"  ⚪ Lemak    : {round(total_fat, 1)} g")
    lines.append(f"  🔥 Kalori   : {round(total_cal)} kkal")
    return "\n".join(lines)


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def log_food(
    food: str,
    amount: str,
    calories: float,
    protein_g: float,
    carbs_g: float,
    fiber_g: float,
    fat_g: float = 0.0,
    meal_time: str = "lainnya",
) -> str:
    """
    Log satu makanan ke catatan harian hari ini.

    Args:
        food      : Nama makanan (e.g. 'Nasi putih', 'Dada ayam panggang').
        amount    : Porsi / berat (e.g. '200g', '1 piring', '2 butir').
        calories  : Total kalori (kkal).
        protein_g : Kandungan protein dalam gram.
        carbs_g   : Kandungan karbohidrat dalam gram.
        fiber_g   : Kandungan serat dalam gram.
        fat_g     : Kandungan lemak dalam gram (default 0).
        meal_time : Waktu makan — 'sarapan', 'makan siang', 'makan malam',
                    'snack', atau 'pre-workout' / 'post-workout' (default 'lainnya').
    """
    data = _load()
    today = _today()
    data.setdefault(today, [])

    entry = {
        "id":         str(uuid.uuid4())[:6],
        "food":       str(food),
        "amount":     str(amount),
        "calories":   round(float(calories), 1),
        "protein_g":  round(float(protein_g), 1),
        "carbs_g":    round(float(carbs_g), 1),
        "fiber_g":    round(float(fiber_g), 1),
        "fat_g":      round(float(fat_g), 1),
        "meal_time":  (meal_time or "lainnya").lower(),
        "logged_at":  datetime.now().strftime("%H:%M"),
    }
    data[today].append(entry)
    _save(data)

    return (
        f"✅ Dicatat [{entry['id']}]: **{food}** ({amount}) — {meal_time}\n"
        f"   🔴 Protein {protein_g}g · 🟡 Karbo {carbs_g}g · "
        f"🟢 Serat {fiber_g}g · 🔥 {calories} kkal"
    )


@tool
def get_daily_log(date_str: str = "") -> str:
    """
    Tampilkan semua makanan yang dicatat pada tanggal tertentu, dikelompokkan
    per waktu makan, beserta total makro harian.

    Args:
        date_str: Tanggal format YYYY-MM-DD. Kosongkan untuk hari ini.
    """
    data = _load()
    target = date_str.strip() if date_str.strip() else _today()

    try:
        datetime.strptime(target, "%Y-%m-%d")
    except ValueError:
        return "Format tanggal tidak valid. Gunakan YYYY-MM-DD (contoh: 2026-04-08)."

    entries = data.get(target, [])
    label = "Hari Ini" if target == _today() else target
    return _format_log_table(entries, label)


@tool
def get_daily_summary(date_str: str = "") -> str:
    """
    Tampilkan ringkasan makro per kategori (Protein / Karbo / Serat / Lemak / Kalori)
    untuk satu hari, termasuk breakdown persentase kontribusi setiap makanan.

    Args:
        date_str: Tanggal format YYYY-MM-DD. Kosongkan untuk hari ini.
    """
    data = _load()
    target = date_str.strip() if date_str.strip() else _today()
    entries = data.get(target, [])

    if not entries:
        label = "hari ini" if target == _today() else target
        return f"Belum ada data makanan untuk {label}."

    total_cal  = sum(e.get("calories", 0)  for e in entries)
    total_pro  = sum(e.get("protein_g", 0) for e in entries)
    total_carb = sum(e.get("carbs_g", 0)   for e in entries)
    total_fib  = sum(e.get("fiber_g", 0)   for e in entries)
    total_fat  = sum(e.get("fat_g", 0)     for e in entries)
    total_macro = total_pro + total_carb + total_fat or 1  # avoid div/0

    label = "Hari Ini" if target == _today() else target
    lines = [
        f"📊 Ringkasan Nutrisi — {label}",
        "─" * 40,
        f"🔴 PROTEIN   : {round(total_pro,1):>6} g   ({round(total_pro*100/total_macro)}% dari total makro)",
        f"🟡 KARBO     : {round(total_carb,1):>6} g   ({round(total_carb*100/total_macro)}% dari total makro)",
        f"🟢 SERAT     : {round(total_fib,1):>6} g",
        f"⚪ LEMAK     : {round(total_fat,1):>6} g   ({round(total_fat*100/total_macro)}% dari total makro)",
        f"🔥 KALORI    : {round(total_cal):>6} kkal",
        "",
        "📌 Breakdown per makanan:",
    ]

    # Sort by protein contribution descending
    for e in sorted(entries, key=lambda x: x.get("protein_g", 0), reverse=True):
        lines.append(
            f"  • {e['food']} ({e.get('amount','?')}) — "
            f"P:{e.get('protein_g',0)}g  C:{e.get('carbs_g',0)}g  "
            f"F:{e.get('fiber_g',0)}g  🔥{e.get('calories',0)}kkal"
        )

    return "\n".join(lines)


@tool
def delete_food_entry(entry_id: str, date_str: str = "") -> str:
    """
    Hapus satu entri makanan berdasarkan ID-nya.

    Args:
        entry_id : ID 6-karakter yang terlihat di log (contoh: 'a3f9c1').
        date_str : Tanggal format YYYY-MM-DD. Kosongkan untuk hari ini.
    """
    data = _load()
    target = date_str.strip() if date_str.strip() else _today()
    entries = data.get(target, [])
    original_len = len(entries)

    new_entries = [e for e in entries if e["id"] != entry_id]
    if len(new_entries) == original_len:
        return f"Entri ID '{entry_id}' tidak ditemukan pada {target}."

    data[target] = new_entries
    _save(data)
    return f"🗑️ Entri [{entry_id}] dihapus dari log {target}."


@tool
def get_weekly_overview() -> str:
    """
    Tampilkan ringkasan 7 hari terakhir: total kalori dan makro per hari
    beserta rata-rata hariannya.
    """
    data = _load()
    today_dt = date.today()
    days = [(today_dt - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]

    lines = ["📆 Overview 7 Hari Terakhir", "─" * 50]
    totals = {"calories": 0, "protein_g": 0, "carbs_g": 0, "fiber_g": 0, "fat_g": 0}
    days_with_data = 0

    for d in days:
        entries = data.get(d, [])
        if not entries:
            lines.append(f"  {d}  —  (tidak ada data)")
            continue
        days_with_data += 1
        cal  = sum(e.get("calories", 0)  for e in entries)
        pro  = sum(e.get("protein_g", 0) for e in entries)
        carb = sum(e.get("carbs_g", 0)   for e in entries)
        fib  = sum(e.get("fiber_g", 0)   for e in entries)
        fat  = sum(e.get("fat_g", 0)     for e in entries)
        for k, v in [("calories",cal),("protein_g",pro),("carbs_g",carb),("fiber_g",fib),("fat_g",fat)]:
            totals[k] += v
        lines.append(
            f"  {d}  🔥{round(cal)}kkal  "
            f"P:{round(pro,1)}g  C:{round(carb,1)}g  F:{round(fib,1)}g"
        )

    if days_with_data:
        n = days_with_data
        lines += [
            "",
            "─" * 50,
            f"📊 Rata-rata harian ({n} hari ada data):",
            f"  🔥 Kalori  : {round(totals['calories']/n)} kkal",
            f"  🔴 Protein : {round(totals['protein_g']/n, 1)} g",
            f"  🟡 Karbo   : {round(totals['carbs_g']/n, 1)} g",
            f"  🟢 Serat   : {round(totals['fiber_g']/n, 1)} g",
            f"  ⚪ Lemak   : {round(totals['fat_g']/n, 1)} g",
        ]

    return "\n".join(lines)


FOOD_TOOLS = [
    log_food,
    get_daily_log,
    get_daily_summary,
    delete_food_entry,
    get_weekly_overview,
]
