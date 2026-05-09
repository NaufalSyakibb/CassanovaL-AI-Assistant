import json
import uuid
import os
from datetime import datetime
from langchain.tools import tool

FLASHCARD_FILE = "data/flashcards.json"


def _load() -> dict:
    try:
        with open(FLASHCARD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"sets": []}


def _save(data: dict):
    os.makedirs(os.path.dirname(FLASHCARD_FILE), exist_ok=True)
    with open(FLASHCARD_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _find_set(data: dict, set_id: str) -> dict | None:
    return next((s for s in data["sets"] if s["id"] == set_id), None)


@tool
def create_flashcard_set(title: str, course: str, cards_json: str) -> str:
    """
    Create a new flashcard set with a list of Q&A cards.
    Args:
        title: Name of the flashcard set (e.g. 'Sorting Algorithms').
        course: Course/subject tag (e.g. 'strukdat', 'kalkulus', 'jarkom').
        cards_json: JSON array string of cards, each with 'q' (question) and 'a' (answer).
                    Example: '[{"q": "What is O(n log n)?", "a": "Merge sort complexity"}]'
    """
    try:
        cards = json.loads(cards_json)
        if not isinstance(cards, list) or not cards:
            return "cards_json harus berupa JSON array yang tidak kosong."
        for i, card in enumerate(cards):
            if "q" not in card or "a" not in card:
                return f"Kartu ke-{i+1} tidak memiliki field 'q' dan 'a'."
    except json.JSONDecodeError as e:
        return f"Format cards_json tidak valid: {e}"

    data = _load()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_set = {
        "id": str(uuid.uuid4())[:8],
        "title": title,
        "course": course.lower().strip(),
        "created_at": now,
        "updated_at": now,
        "cards": cards,
    }
    data["sets"].append(new_set)
    _save(data)
    return (
        f"Set flashcard dibuat!\n"
        f"ID: {new_set['id']} | \"{title}\" | Mata kuliah: {course}\n"
        f"Jumlah kartu: {len(cards)}"
    )


@tool
def list_flashcard_sets(course: str = "") -> str:
    """
    List all flashcard sets, optionally filtered by course.
    Args:
        course: Filter by course name (leave empty to list all sets).
    """
    data = _load()
    sets = data["sets"]
    if course:
        sets = [s for s in sets if course.lower() in s["course"]]
    if not sets:
        msg = f"Belum ada set flashcard" + (f" untuk mata kuliah '{course}'." if course else ".")
        return msg
    lines = []
    for s in sets:
        lines.append(
            f"ID:{s['id']} | {s['title']} | {s['course']} | {len(s['cards'])} kartu | {s['updated_at']}"
        )
    header = f"Set flashcard" + (f" ({course})" if course else "") + f" — {len(sets)} set:"
    return header + "\n" + "\n".join(lines)


@tool
def get_flashcard_set(set_id: str) -> str:
    """
    Retrieve all cards in a flashcard set for studying.
    Returns all questions and answers formatted for review.
    Args:
        set_id: The 8-character ID of the flashcard set.
    """
    data = _load()
    s = _find_set(data, set_id)
    if not s:
        return f"Set flashcard ID '{set_id}' tidak ditemukan."
    lines = [f"**{s['title']}** [{s['course']}] — {len(s['cards'])} kartu\n"]
    for i, card in enumerate(s["cards"], 1):
        lines.append(f"Kartu {i}:\n  Q: {card['q']}\n  A: {card['a']}")
    return "\n".join(lines)


@tool
def add_cards_to_set(set_id: str, cards_json: str) -> str:
    """
    Add new Q&A cards to an existing flashcard set.
    Args:
        set_id: The 8-character ID of the target flashcard set.
        cards_json: JSON array of new cards, each with 'q' and 'a' fields.
                    Example: '[{"q": "New question?", "a": "Answer here"}]'
    """
    try:
        new_cards = json.loads(cards_json)
        if not isinstance(new_cards, list) or not new_cards:
            return "cards_json harus berupa JSON array yang tidak kosong."
        for i, card in enumerate(new_cards):
            if "q" not in card or "a" not in card:
                return f"Kartu ke-{i+1} tidak memiliki field 'q' dan 'a'."
    except json.JSONDecodeError as e:
        return f"Format cards_json tidak valid: {e}"

    data = _load()
    s = _find_set(data, set_id)
    if not s:
        return f"Set flashcard ID '{set_id}' tidak ditemukan."
    s["cards"].extend(new_cards)
    s["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _save(data)
    return (
        f"Ditambahkan {len(new_cards)} kartu ke \"{s['title']}\".\n"
        f"Total sekarang: {len(s['cards'])} kartu."
    )


@tool
def delete_flashcard_set(set_id: str) -> str:
    """
    Delete a flashcard set by its ID.
    Args:
        set_id: The 8-character ID of the flashcard set to delete.
    """
    data = _load()
    before = len(data["sets"])
    target = _find_set(data, set_id)
    if not target:
        return f"Set flashcard ID '{set_id}' tidak ditemukan."
    title = target["title"]
    data["sets"] = [s for s in data["sets"] if s["id"] != set_id]
    _save(data)
    return f"Set flashcard \"{title}\" (ID:{set_id}) dihapus."


@tool
def search_flashcards(query: str) -> str:
    """
    Search across all flashcard sets for cards matching a keyword.
    Searches both questions and answers.
    Args:
        query: Keyword to search for.
    """
    data = _load()
    query_lower = query.lower()
    results = []
    for s in data["sets"]:
        for i, card in enumerate(s["cards"], 1):
            if query_lower in card["q"].lower() or query_lower in card["a"].lower():
                results.append(
                    f"[{s['title']} | {s['course']} | Kartu {i}]\n"
                    f"  Q: {card['q']}\n"
                    f"  A: {card['a']}"
                )
    if not results:
        return f"Tidak ada flashcard yang cocok dengan '{query}'."
    return f"Ditemukan {len(results)} kartu untuk '{query}':\n\n" + "\n\n".join(results)


FLASHCARD_TOOLS = [
    create_flashcard_set,
    list_flashcard_sets,
    get_flashcard_set,
    add_cards_to_set,
    delete_flashcard_set,
    search_flashcards,
]
