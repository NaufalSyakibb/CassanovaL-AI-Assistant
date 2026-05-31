import json
import os
import uuid
from datetime import datetime
from langchain.tools import tool

ALFRED_NOTES_FILE = "data/alfred_notes.json"


def _load_alfred() -> list:
    try:
        with open(ALFRED_NOTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_alfred(data: list):
    os.makedirs(os.path.dirname(ALFRED_NOTES_FILE), exist_ok=True)
    with open(ALFRED_NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


@tool
def add_alfred_note(title: str, content: str, tags: str = "") -> str:
    """
    Create a new personal note.
    Args:
        title: Note title.
        content: Note body/content.
        tags: Comma-separated tags (e.g. 'meeting,project-x,reference').
    """
    notes = _load_alfred()
    note = {
        "id": str(uuid.uuid4())[:8],
        "title": title,
        "content": content,
        "tags": [t.strip() for t in tags.split(",") if t.strip()],
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    notes.append(note)
    _save_alfred(notes)
    return f"Note saved! ID:{note['id']} | \"{title}\" | Tags:{tags or 'none'}"


@tool
def list_alfred_notes(tag_filter: str = "") -> str:
    """
    List all personal notes, optionally filtered by tag.
    Args:
        tag_filter: Filter notes by this tag (leave empty to list all).
    """
    notes = _load_alfred()
    if tag_filter:
        notes = [n for n in notes if tag_filter.lower() in [t.lower() for t in n.get("tags", [])]]
    if not notes:
        return "No notes found."
    lines = []
    for n in notes:
        tags = ", ".join(n.get("tags", [])) or "no tags"
        preview = n["content"][:80] + "..." if len(n["content"]) > 80 else n["content"]
        lines.append(f"ID:{n['id']} | {n['title']} | [{tags}]\n  {preview}")
    return "\n\n".join(lines)


@tool
def read_alfred_note(note_id: str) -> str:
    """Read the full content of a personal note by its ID."""
    notes = _load_alfred()
    for n in notes:
        if n["id"] == note_id:
            tags = ", ".join(n.get("tags", [])) or "none"
            return f"Title: {n['title']}\nTags: {tags}\nCreated: {n['created_at']}\n\n{n['content']}"
    return f"Note ID {note_id} not found."


@tool
def search_alfred_notes(query: str) -> str:
    """Search personal notes by keyword in title or content."""
    notes = _load_alfred()
    query_lower = query.lower()
    results = [
        n for n in notes
        if query_lower in n["title"].lower() or query_lower in n["content"].lower()
    ]
    if not results:
        return f"No notes matching '{query}'."
    lines = []
    for n in results:
        preview = n["content"][:80] + "..." if len(n["content"]) > 80 else n["content"]
        lines.append(f"ID:{n['id']} | {n['title']}\n  {preview}")
    return "\n\n".join(lines)


@tool
def update_alfred_note(note_id: str, title: str = "", content: str = "", tags: str = "") -> str:
    """Update an existing personal note's title, content, or tags by its ID."""
    notes = _load_alfred()
    for n in notes:
        if n["id"] == note_id:
            if title:
                n["title"] = title
            if content:
                n["content"] = content
            if tags:
                n["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
            n["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            _save_alfred(notes)
            return f"Note {note_id} updated: \"{n['title']}\""
    return f"Note ID {note_id} not found."


@tool
def delete_alfred_note(note_id: str) -> str:
    """Delete a personal note by its ID."""
    notes = _load_alfred()
    new = [n for n in notes if n["id"] != note_id]
    if len(new) == len(notes):
        return f"Note ID {note_id} not found."
    _save_alfred(new)
    return f"Note {note_id} deleted."


ALFRED_NOTES_TOOLS = [
    add_alfred_note, list_alfred_notes, read_alfred_note,
    search_alfred_notes, update_alfred_note, delete_alfred_note,
]
