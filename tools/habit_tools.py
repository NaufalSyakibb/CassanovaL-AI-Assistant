import json
from pathlib import Path
from datetime import datetime, timedelta, date
from langchain.tools import tool

_HABITS_FILE = Path("data/habits.json")


def _load() -> dict:
    if not _HABITS_FILE.exists():
        return {"habits": []}
    try:
        return json.loads(_HABITS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"habits": []}


def _save(data: dict) -> None:
    _HABITS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _HABITS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _calc_streak(completions: list, frequency: str) -> int:
    """Calculate current streak from sorted ISO date list."""
    if not completions:
        return 0
    dates = sorted(set(completions))
    if frequency == "daily":
        streak = 1
        for i in range(len(dates) - 1, 0, -1):
            a = date.fromisoformat(dates[i])
            b = date.fromisoformat(dates[i - 1])
            if (a - b).days == 1:
                streak += 1
            else:
                break
        return streak
    elif frequency == "weekly":
        def week_key(d):
            iso = date.fromisoformat(d).isocalendar()
            return (iso[0], iso[1])
        weeks = sorted(set(week_key(d) for d in dates))
        streak = 1
        for i in range(len(weeks) - 1, 0, -1):
            y1, w1 = weeks[i]
            y2, w2 = weeks[i - 1]
            d1 = date.fromisocalendar(y1, w1, 1)
            d2 = date.fromisocalendar(y2, w2, 1)
            if (d1 - d2).days == 7:
                streak += 1
            else:
                break
        return streak
    return 0  # occasional


@tool
def detect_habits_from_journal(entry_date: str, journal_text: str) -> str:
    """
    Analyze a journal entry to detect completed habits and log them to habits.json.
    Call this automatically after every journal save.
    Args:
        entry_date: ISO date string (YYYY-MM-DD) of the journal entry
        journal_text: Full text of the journal entry to analyze
    """
    from langchain_mistralai import ChatMistralAI
    from langchain_core.messages import HumanMessage

    prompt = f"""Analisis entri jurnal berikut dan identifikasi kebiasaan atau rutinitas yang SUDAH DILAKUKAN hari ini.

Hanya sertakan kebiasaan yang benar-benar diselesaikan, bukan yang direncanakan atau gagal.
Untuk setiap kebiasaan, tentukan frekuensi yang tersirat dari konteks:
- "daily" jika disebutkan sebagai rutinitas setiap hari
- "weekly" jika mingguan
- "occasional" jika tidak ada pola frekuensi yang jelas

Kembalikan HANYA JSON array. Contoh:
[{{"name": "exercise", "display_name": "Olahraga", "frequency": "daily"}}]

Jika tidak ada kebiasaan yang terdeteksi, kembalikan: []

Tanggal: {entry_date}
Entri jurnal:
{journal_text}"""

    try:
        response = ChatMistralAI(model="mistral-small-latest", temperature=0.0).invoke(
            [HumanMessage(content=prompt)]
        ).content.strip()
        start = response.find("[")
        end = response.rfind("]") + 1
        if start == -1 or end == 0:
            return "Tidak ada kebiasaan yang terdeteksi."
        detected = json.loads(response[start:end])
    except Exception:
        return "Gagal menganalisis kebiasaan dari jurnal."

    if not detected:
        return "Tidak ada kebiasaan yang terdeteksi dari entri ini."

    data = _load()
    habits = {h["name"]: h for h in data["habits"]}
    updated = []

    for item in detected:
        name = item.get("name", "").lower().strip()
        if not name:
            continue
        if name not in habits:
            habits[name] = {
                "name": name,
                "display_name": item.get("display_name", name.title()),
                "frequency": item.get("frequency", "daily"),
                "completions": [],
                "streak": 0,
                "longest_streak": 0,
                "last_detected": None,
            }
        h = habits[name]
        if entry_date not in h["completions"]:
            h["completions"].append(entry_date)
            h["completions"].sort()
        h["last_detected"] = entry_date
        h["streak"] = _calc_streak(h["completions"], h["frequency"])
        h["longest_streak"] = max(h.get("longest_streak", 0), h["streak"])
        updated.append(h["display_name"])

    data["habits"] = list(habits.values())
    _save(data)

    names = ", ".join(updated)
    return f"Kebiasaan terdeteksi: {names} ✓"


@tool
def get_habit_summary(days: int = 30) -> str:
    """
    Return a text summary of all tracked habits for the last N days.
    Shows completion rate, current streak, and longest streak per habit.
    Args:
        days: Number of days to look back (default 30)
    """
    data = _load()
    habits = data.get("habits", [])
    if not habits:
        return "Belum ada kebiasaan yang dilacak. Mulai menulis jurnal dan kebiasaanmu akan terdeteksi otomatis!"

    cutoff = (date.today() - timedelta(days=days)).isoformat()
    lines = [f"\U0001f4ca Habit Tracker — {days} hari terakhir\n"]
    for h in sorted(habits, key=lambda x: -len(x.get("completions", []))):
        recent = [c for c in h.get("completions", []) if c >= cutoff]
        rate = len(recent)
        bar_filled = min(int(rate / max(days, 1) * 12), 12)
        bar = "█" * bar_filled + "░" * (12 - bar_filled)
        freq = h.get("frequency", "daily")
        freq_label = {
            "daily": f"{rate}/{days} hari",
            "weekly": f"{rate} minggu",
            "occasional": f"{rate}x",
        }.get(freq, f"{rate}x")
        lines.append(f"{h['display_name']:<16} {bar}  {freq_label}  streak: {h.get('streak', 0)}")
    return "\n".join(lines)


@tool
def list_habits() -> str:
    """List all currently tracked habits with their frequency and streak."""
    data = _load()
    habits = data.get("habits", [])
    if not habits:
        return "Belum ada kebiasaan yang dilacak."
    lines = ["Kebiasaan yang dilacak:\n"]
    for h in habits:
        lines.append(
            f"• {h['display_name']} ({h.get('frequency', 'daily')}) "
            f"— streak: {h.get('streak', 0)}, terpanjang: {h.get('longest_streak', 0)}"
        )
    return "\n".join(lines)


HABIT_TOOLS = [detect_habits_from_journal, get_habit_summary, list_habits]
