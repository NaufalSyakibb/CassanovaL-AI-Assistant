import json
import pytest
from unittest.mock import patch
from tools.alfred_notes_tools import add_alfred_note, search_alfred_notes, list_alfred_notes


def test_add_alfred_note_creates_note(tmp_path):
    fake_file = str(tmp_path / "alfred_notes.json")
    with patch("tools.alfred_notes_tools.ALFRED_NOTES_FILE", fake_file):
        result = add_alfred_note.invoke({"title": "Test Note", "content": "Test content", "tags": "test"})
    assert "Test Note" in result
    with open(fake_file, encoding="utf-8") as f:
        notes = json.load(f)
    assert len(notes) == 1
    assert notes[0]["title"] == "Test Note"
    assert "test" in notes[0]["tags"]


def test_search_alfred_notes_finds_by_keyword(tmp_path):
    fake_file = str(tmp_path / "alfred_notes.json")
    seed = [{
        "id": "abc12345", "title": "Meeting Summary",
        "content": "discussed Mansa agent", "tags": [],
        "created_at": "2026-05-31 10:00", "updated_at": "2026-05-31 10:00",
    }]
    with open(fake_file, "w", encoding="utf-8") as f:
        json.dump(seed, f)
    with patch("tools.alfred_notes_tools.ALFRED_NOTES_FILE", fake_file):
        result = search_alfred_notes.invoke({"query": "Mansa"})
    assert "Meeting Summary" in result


def test_list_alfred_notes_tag_filter(tmp_path):
    fake_file = str(tmp_path / "alfred_notes.json")
    seed = [
        {"id": "aaa11111", "title": "Work Note", "content": "work content",
         "tags": ["work"], "created_at": "2026-05-31 10:00", "updated_at": "2026-05-31 10:00"},
        {"id": "bbb22222", "title": "Personal Note", "content": "personal content",
         "tags": ["personal"], "created_at": "2026-05-31 10:00", "updated_at": "2026-05-31 10:00"},
    ]
    with open(fake_file, "w", encoding="utf-8") as f:
        json.dump(seed, f)
    with patch("tools.alfred_notes_tools.ALFRED_NOTES_FILE", fake_file):
        result = list_alfred_notes.invoke({"tag_filter": "work"})
    assert "Work Note" in result
    assert "Personal Note" not in result
