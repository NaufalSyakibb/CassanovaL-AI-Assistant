import json
import uuid
import re
import os
import requests
from datetime import datetime
from langchain.tools import tool
from tools.obsidian_tools import create_clipping

NOTES_FILE = "data/notes.json"


def _load() -> list:
    try:
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save(data: list):
    os.makedirs(os.path.dirname(NOTES_FILE), exist_ok=True)
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


@tool
def create_note(title: str, content: str, tags: str = "") -> str:
    """
    Create a new note with a title and content.
    Args:
        title: Note title.
        content: Note body/content.
        tags: Comma-separated tags (e.g. 'work,research,python').
    """
    notes = _load()
    note = {
        "id": str(uuid.uuid4())[:8],
        "title": title,
        "content": content,
        "tags": [t.strip() for t in tags.split(",") if t.strip()],
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    notes.append(note)
    _save(notes)
    return f"Note created! ID:{note['id']} | \"{title}\" | Tags:{tags or 'none'}"


@tool
def list_notes(tag_filter: str = "") -> str:
    """
    List all notes, optionally filtered by tag.
    Args:
        tag_filter: Filter notes by this tag (leave empty to list all).
    """
    notes = _load()
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
def read_note(note_id: str) -> str:
    """Read the full content of a note by its ID."""
    notes = _load()
    for n in notes:
        if n["id"] == note_id:
            tags = ", ".join(n.get("tags", [])) or "none"
            return f"Title: {n['title']}\nTags: {tags}\nCreated: {n['created_at']}\n\n{n['content']}"
    return f"Note ID {note_id} not found."


@tool
def search_notes(query: str) -> str:
    """Search notes by keyword in title or content."""
    notes = _load()
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
def update_note(note_id: str, title: str = "", content: str = "", tags: str = "") -> str:
    """Update an existing note's title, content, or tags by its ID."""
    notes = _load()
    for n in notes:
        if n["id"] == note_id:
            if title:
                n["title"] = title
            if content:
                n["content"] = content
            if tags:
                n["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
            n["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            _save(notes)
            return f"Note {note_id} updated: \"{n['title']}\""
    return f"Note ID {note_id} not found."


@tool
def delete_note(note_id: str) -> str:
    """Delete a note by its ID."""
    notes = _load()
    new = [n for n in notes if n["id"] != note_id]
    if len(new) == len(notes):
        return f"Note ID {note_id} not found."
    _save(new)
    return f"Note {note_id} deleted."


@tool
def fetch_and_summarize_url(url: str) -> str:
    """
    Fetch a web page and return its text content for summarization.
    Also auto-saves a Clipping to the Obsidian vault (Clippings/ folder).
    Args:
        url: The URL to fetch content from.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        text = re.sub(r"<[^>]+>", " ", response.text)
        text = re.sub(r"\s+", " ", text).strip()

        # Extract a rough title from <title> tag if present
        title_match = re.search(r"<title[^>]*>(.*?)</title>", response.text, re.IGNORECASE | re.DOTALL)
        page_title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else url

        # Auto-save to Obsidian Clippings (silent if vault not configured)
        create_clipping(url=url, title=page_title, body=text[:5000], tags=["clipping"])

        return text[:3000] + ("..." if len(text) > 3000 else "")
    except Exception as e:
        return f"Failed to fetch URL: {e}"


NOTES_TOOLS = [create_note, list_notes, read_note, search_notes, update_note, delete_note, fetch_and_summarize_url]
