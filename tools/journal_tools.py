"""
Journaling tools for Dostoyevsky agent.
Saves all entries to Obsidian Vault at: AI Data/Dostoyevsky Agent/
One file per day: Journal_YYYY-MM-DD.md
"""
import os
import re
from pathlib import Path
from datetime import datetime
from langchain.tools import tool

JOURNAL_FOLDER = "Dostoyevsky Agent"


def _vault() -> Path:
    path = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    if not path:
        raise EnvironmentError(
            "OBSIDIAN_VAULT_PATH tidak di-set di .env.\n"
            "Tambahkan: OBSIDIAN_VAULT_PATH=C:/Users/muham/OneDrive/Dokumen/Obsidian Vault"
        )
    vault = Path(path)
    if not vault.exists():
        raise FileNotFoundError(f"Vault tidak ditemukan di: {vault}")
    return vault


def _journal_dir() -> Path:
    d = _vault() / JOURNAL_FOLDER
    d.mkdir(parents=True, exist_ok=True)
    return d


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _time_str() -> str:
    return datetime.now().strftime("%H:%M")


@tool
def write_journal_entry(
    content: str,
    title: str = "",
    mood: str = "",
    tags: str = "",
) -> str:
    """
    Write or append a journal entry for today to the Obsidian vault.
    Args:
        content: The journal entry content (thoughts, reflections, feelings, etc.)
        title: Optional section title (e.g. 'Morning Reflection', 'Gratitude', 'Dream Log')
        mood: Current mood descriptor (e.g. 'happy', 'anxious', 'contemplative', 'grateful')
        tags: Comma-separated tags (e.g. 'gratitude,work,reflection')
    """
    try:
        journal_dir = _journal_dir()
        today = _today()
        ts = _time_str()
        filename = f"Journal_{today}.md"
        filepath = journal_dir / filename

        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

        if not filepath.exists():
            mood_str = mood or "unspecified"
            frontmatter = (
                f"---\n"
                f"date: {today}\n"
                f"mood: {mood_str}\n"
                f"tags: [{', '.join(tag_list)}]\n"
                f"---\n\n"
                f"# Jurnal — {today}\n\n"
            )
            filepath.write_text(frontmatter, encoding="utf-8")
        elif mood:
            # Update mood in frontmatter if this is a later entry in the same day
            raw = filepath.read_text(encoding="utf-8")
            raw = re.sub(r"^mood:.*$", f"mood: {mood}", raw, flags=re.MULTILINE)
            if tag_list:
                all_tags = set(tag_list)
                tag_match = re.search(r"^tags:\s*\[([^\]]*)\]", raw, re.MULTILINE)
                if tag_match:
                    existing = [t.strip() for t in tag_match.group(1).split(",") if t.strip()]
                    all_tags.update(existing)
                raw = re.sub(
                    r"^tags:\s*\[.*?\]",
                    f"tags: [{', '.join(sorted(all_tags))}]",
                    raw,
                    flags=re.MULTILINE,
                )
            filepath.write_text(raw, encoding="utf-8")

        # Build section header
        section_title = title if title else ts
        mood_note = f" · *Mood: {mood}*" if mood else ""
        section = f"## {section_title}{mood_note}"

        entry_text = f"\n{section}\n\n{content}\n\n---\n"

        with filepath.open("a", encoding="utf-8") as f:
            f.write(entry_text)

        return (
            f"✓ Entri jurnal disimpan → {JOURNAL_FOLDER}/{filename}\n"
            f"  Bagian: '{section_title}'"
            + (f" | Mood: {mood}" if mood else "")
        )
    except Exception as e:
        return f"[write_journal_entry error] {e}"


@tool
def read_journal_entry(date_str: str = "") -> str:
    """
    Read a journal entry for a specific date.
    Args:
        date_str: Date in YYYY-MM-DD format. Leave empty to read today's entry.
    """
    try:
        journal_dir = _journal_dir()
        date = date_str.strip() if date_str.strip() else _today()
        filepath = journal_dir / f"Journal_{date}.md"

        if not filepath.exists():
            return f"Tidak ada entri jurnal untuk {date}. Mau mulai menulis sekarang?"

        content = filepath.read_text(encoding="utf-8")
        return f"[JURNAL: {date}]\n\n{content}"
    except Exception as e:
        return f"[read_journal_entry error] {e}"


@tool
def list_journal_entries(days: int = 7) -> str:
    """
    List recent journal entries with date, mood, and word count.
    Args:
        days: How many recent days to show (default: 7, max: 30)
    """
    try:
        journal_dir = _journal_dir()
        files = sorted(journal_dir.glob("Journal_*.md"), reverse=True)[: min(days, 30)]

        if not files:
            return "Belum ada entri jurnal sama sekali. Yuk mulai menulis hari ini! 📔"

        lines = []
        for f in files:
            date = f.stem.replace("Journal_", "")
            try:
                content = f.read_text(encoding="utf-8")
            except Exception:
                continue
            mood_match = re.search(r"^mood:\s*(.+)$", content, re.MULTILINE)
            mood = mood_match.group(1).strip() if mood_match else "—"
            body = re.sub(r"---.*?---", "", content, flags=re.DOTALL).strip()
            word_count = len(body.split())
            lines.append(f"📔 {date}  |  Mood: {mood}  |  {word_count} kata")

        return f"Jurnal tersimpan ({len(files)} entri):\n\n" + "\n".join(lines)
    except Exception as e:
        return f"[list_journal_entries error] {e}"


@tool
def search_journal(query: str) -> str:
    """
    Search across all journal entries for a keyword or phrase.
    Args:
        query: Keyword or phrase to search in journal entries.
    """
    try:
        journal_dir = _journal_dir()
        query_lower = query.lower()
        results = []

        for filepath in sorted(journal_dir.glob("Journal_*.md"), reverse=True):
            try:
                content = filepath.read_text(encoding="utf-8")
            except Exception:
                continue
            if query_lower in content.lower():
                date = filepath.stem.replace("Journal_", "")
                idx = content.lower().find(query_lower)
                start = max(0, idx - 100)
                snippet = re.sub(r"\n+", " ", content[start: idx + 200].strip())
                results.append(f"📔 {date}\n   ...{snippet}...")

        if not results:
            return f"Tidak ada entri jurnal yang mengandung '{query}'."
        return (
            f"Ditemukan {len(results)} entri untuk '{query}':\n\n"
            + "\n\n".join(results[:8])
        )
    except Exception as e:
        return f"[search_journal error] {e}"


@tool
def get_mood_history(days: int = 14) -> str:
    """
    Get a timeline of moods from recent journal entries to spot patterns.
    Args:
        days: How many recent days to check (default: 14)
    """
    try:
        journal_dir = _journal_dir()
        files = sorted(journal_dir.glob("Journal_*.md"), reverse=True)[: min(days, 30)]

        if not files:
            return "Belum ada riwayat mood. Mulai menulis jurnal untuk mulai melacak perasaanmu!"

        moods = []
        for f in files:
            try:
                content = f.read_text(encoding="utf-8")
            except Exception:
                continue
            date = f.stem.replace("Journal_", "")
            mood_match = re.search(r"^mood:\s*(.+)$", content, re.MULTILINE)
            mood = mood_match.group(1).strip() if mood_match else "unspecified"
            moods.append(f"  {date}  →  {mood}")

        return f"Riwayat Mood ({len(moods)} hari):\n\n" + "\n".join(moods)
    except Exception as e:
        return f"[get_mood_history error] {e}"


JOURNAL_TOOLS = [
    write_journal_entry,
    read_journal_entry,
    list_journal_entries,
    search_journal,
    get_mood_history,
]
