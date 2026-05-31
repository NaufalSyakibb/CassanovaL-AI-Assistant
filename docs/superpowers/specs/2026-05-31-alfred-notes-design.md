# Alfred Notes — Design Spec

**Date:** 2026-05-31
**Status:** Approved for implementation

---

## Context

Alfred (TaskCore) is CassanovaL's task management agent. Cicero handles academic/study notes.
There is no general-purpose notepad — things like meeting notes, material references, quick captures,
and personal reminders have nowhere to land.

This feature adds a private note-taking toolkit directly to Alfred, with its own isolated data store
(`data/alfred_notes.json`) separate from Cicero's `data/notes.json`. The router is updated so that
general note-taking requests ("save a note", "write this down", "keep a note about X") are routed to
Alfred instead of Cicero.

---

## Goal

After this change:
- Alfred can create, list, read, search, update, and delete personal notes.
- Alfred's notes live in `data/alfred_notes.json` — completely separate from Cicero's academic notes.
- The router correctly sends general note requests to Alfred and keeps academic/study requests with Cicero.

---

## Changes

### 1. New file — `tools/alfred_notes_tools.py`

Six LangChain tools mirroring the pattern in `tools/notes_tools.py`, but pointing to
`data/alfred_notes.json` instead of `data/notes.json`.

Note schema (same as Cicero's):
```json
{
  "id": "<8-char UUID>",
  "title": "...",
  "content": "...",
  "tags": ["tag1", "tag2"],
  "created_at": "ISO timestamp",
  "updated_at": "ISO timestamp"
}
```

Tools:
| Tool | Signature | Purpose |
|------|-----------|---------|
| `add_alfred_note` | `(title, content, tags="")` | Create a new note |
| `list_alfred_notes` | `(tag_filter="")` | List all notes, optional tag filter |
| `read_alfred_note` | `(note_id)` | Read full content of one note |
| `search_alfred_notes` | `(query)` | Keyword search across title + content |
| `update_alfred_note` | `(note_id, title="", content="", tags="")` | Modify a note |
| `delete_alfred_note` | `(note_id)` | Remove a note |

Internal helpers:
- `ALFRED_NOTES_FILE = "data/alfred_notes.json"`
- `_load_alfred() -> list` — reads file, returns `[]` on missing/corrupt
- `_save_alfred(data: list)` — writes with `ensure_ascii=False`, `indent=2`

`tags` param is a comma-separated string on input; stored as a list internally.

---

### 2. Modify `agents/task_agent.py`

**Import:** Add `from tools.alfred_notes_tools import ALFRED_NOTES_TOOLS`

**Tools list:** Append `ALFRED_NOTES_TOOLS` to `TASK_AGENT_TOOLS`.

**SYSTEM_PROMPT:** Add a `## NOTES` section after the existing sections, before the
`## CONFIDENTIALITY & SCOPE` section:

```
## NOTES

You have a personal notepad. Use it to save anything that doesn't fit as a task:
materials, references, meeting summaries, quotes, research snippets, quick captures.

- add_alfred_note: Save a new note. Always search first to avoid duplicates.
- list_alfred_notes: Browse notes, optionally filtered by tag.
- read_alfred_note: Read a specific note by ID.
- search_alfred_notes: Find notes by keyword before creating a new one.
- update_alfred_note: Edit an existing note's title, content, or tags.
- delete_alfred_note: Remove a note the user explicitly asks to delete.

Tags: use lowercase, comma-separated (e.g. 'meeting,project-x,reference').
After saving, confirm: "Saved note: [title] (ID: [id])".
```

---

### 3. Modify `router.py`

Update the `"task"` entry in `AGENT_REGISTRY` to include note-taking intents:

```python
# Before:
"task": "Managing to-do lists, tasks, reminders, and deadlines"

# After:
"task": "Managing to-do lists, tasks, reminders, deadlines, and personal notes — save note, write this down, jot down, keep a note, note about, remember this, material reference, meeting notes, quick capture"
```

The `"notes"` entry stays unchanged — it already scopes to academic/study use only.

---

## Data File

`data/alfred_notes.json` — created automatically on first write, starts as `[]`.
This file is protected by the project data-safety rule: never delete or overwrite existing data.

---

## Files to Create / Modify

| File | Action |
|------|--------|
| `tools/alfred_notes_tools.py` | CREATE — 6 tools + helpers |
| `agents/task_agent.py` | MODIFY — import, tools list, SYSTEM_PROMPT |
| `router.py` | MODIFY — expand "task" registry entry |

No new agent file. No schema migration. No frontend changes.

---

## Tests

**File:** `tests/test_alfred_notes_tools.py`

3 unit tests (same mock pattern as `test_konten_agent.py` and `test_emotion_agent.py`):

```python
def test_add_alfred_note_creates_note():
    # call add_alfred_note, read back data/alfred_notes.json, assert note present

def test_search_alfred_notes_finds_by_keyword():
    # seed one note, call search_alfred_notes("keyword"), assert it's returned

def test_list_alfred_notes_tag_filter():
    # seed two notes with different tags, filter by one tag, assert only matching returned
```

Use `tmp_path` (pytest fixture) or patch `ALFRED_NOTES_FILE` to avoid touching real data.

---

## Verification

```powershell
# 1. Unit tests
$env:PYTHONUTF8=1; pytest tests/test_alfred_notes_tools.py -v

# 2. Regression
$env:PYTHONUTF8=1; pytest tests/ -v
# Expected: all existing tests still pass

# 3. Server import
$env:PYTHONUTF8=1; python -c "import server; print('OK')"

# 4. End-to-end
# Start: $env:PYTHONUTF8=1; python server.py
# Chat: "Save a note about the Mansa agent architecture"
#   → Alfred should call add_alfred_note, confirm with title + ID
# Chat: "Show me my notes"
#   → Alfred calls list_alfred_notes, returns the saved note
# Chat: "Search my notes for Mansa"
#   → Alfred calls search_alfred_notes("Mansa"), returns the note
# Verify: data/alfred_notes.json exists with correct schema
# Verify: data/notes.json unchanged (Cicero's notes untouched)
```
