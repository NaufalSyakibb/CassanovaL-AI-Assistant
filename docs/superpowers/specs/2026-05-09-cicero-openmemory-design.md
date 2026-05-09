# Cicero × OpenMemory — Persistent Learning Memory
**Date:** 2026-05-09
**Status:** Approved

---

## Overview

Add OpenMemory as a persistent cognitive memory layer to Cicero (the study assistant agent). After each session Cicero automatically summarises what was studied, what the student mastered, where they still struggle, and any learning-style signals. These summaries are stored in a local SQLite database and recalled at the start of every subsequent session, injecting personalised context directly into Cicero's system prompt.

A **Memory tab** is added to the RightPanel (visible only when Cicero is active) so the user can read and delete their stored session memories.

---

## Architecture

```
Session Start (user sends first message to Cicero)
  └─ server.py calls create_notes_agent(last_message=first_user_msg)
  └─ notes_agent.py calls get_memories(topic=last_message) internally
  └─ Top-5 memories fetched from OpenMemory (Gemini semantic search)
  └─ Injected into Cicero system prompt as "## Ingatan Sesi Sebelumnya"

During Session
  └─ Normal LangChain chat — no memory tool calls during conversation

Session End (user switches agent / reloads / closes tab)
  └─ Frontend: POST /api/memory/cicero/save  { messages: [...last 20 msgs] }
       Guard: skip if user turn count < 3
  └─ Server: Mistral-small generates 1-paragraph structured summary
  └─ OpenMemory.add(summary, sector="episodic", user_id="cicero_naufal", tags=[...])

RightPanel Memory Tab (agKey === 'notes' only)
  └─ GET /api/memory/cicero       → list all memories, newest first
  └─ DELETE /api/memory/cicero    → wipe all memories for this user
```

---

## Data Model

Each session produces **one** OpenMemory entry:

```python
memory.add(
    content=(
        "Sesi {date} | Mata kuliah: {course}\n"
        "Topik: {topics covered}\n"
        "Dikuasai: {correct answers / understood concepts}\n"
        "Masih lemah: {struggles / wrong answers}\n"
        "Gaya belajar: {preference signals observed}\n"
        "Catatan: {anything else notable}"
    ),
    user_id="cicero_naufal",
    sector="episodic",
    tags=[course_tag, date_str],
    metadata={"date": date_str, "course": course_tag}
)
```

**Summary prompt** (sent to `mistral-small-latest`):
```
Buat ringkasan sesi belajar ini dalam format:
Sesi {date} | Mata kuliah: {detected_course}
Topik: {topics}
Dikuasai: {strengths}
Masih lemah: {weaknesses}
Gaya belajar: {preferences observed}
Catatan: {other}

Percakapan:
{last_20_messages}
```

**Recall injection** (prepended to Cicero system prompt when memories exist):
```
## Ingatan Sesi Sebelumnya
[{date} | {course}] {summary_line_1}
[{date} | {course}] {summary_line_2}
...
(maksimal 5 sesi terbaru)
```

If no memories exist (new user), the block is omitted entirely — system prompt stays unchanged.

---

## New Files

### `tools/memory_tools.py` (new)

Thin synchronous wrapper around the async OpenMemory SDK:

```python
def get_memories(topic: str, limit: int = 5) -> list[str]:
    """Semantic search — returns list of summary strings for system prompt injection."""

def store_memory(summary: str, course: str, date: str) -> None:
    """Store one session summary as episodic memory."""

def delete_all_memories() -> None:
    """Wipe all memories for cicero_naufal."""

def list_all_memories() -> list[dict]:
    """Return all memories as dicts for the API endpoint."""
```

Initialisation:
```python
from openmemory.client import Memory
import asyncio, os

_mem = Memory(
    path=os.getenv("OM_DB_PATH", "data/openmemory.db"),
    embeddings=os.getenv("OM_EMBEDDINGS", "gemini"),
    tier="smart",
)
```

**Fallback**: If `openmemory` is not installed or `GEMINI_API_KEY` is absent, all functions return gracefully (empty list / no-op) and log a one-time warning. Cicero continues working without memory.

---

## Modified Files

### `agents/notes_agent.py`

`create_notes_agent()` calls `get_memories(topic="")` before building the agent and prepends the recall block to `SYSTEM_PROMPT` if results are non-empty:

```python
def create_notes_agent(last_topic: str = ""):
    recall = get_memories(last_topic)
    prompt = SYSTEM_PROMPT
    if recall:
        block = "## Ingatan Sesi Sebelumnya\n" + "\n".join(recall)
        prompt = block + "\n\n" + SYSTEM_PROMPT
    return build_agent(prompt, NOTES_AGENT_TOOLS, model="mistral-small-latest", max_tokens=1536)
```

### `server.py`

Three new endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/memory/cicero` | List all memories (newest first) — for Memory tab UI |
| `POST` | `/api/memory/cicero/save` | Generate summary + store memory |
| `DELETE` | `/api/memory/cicero` | Delete all memories |

Note: Memory **recall** (injecting into system prompt) happens entirely server-side inside `create_notes_agent()` — there is no recall HTTP endpoint. The frontend only uses GET (display) and POST (save) and DELETE (wipe).

`POST /api/memory/cicero/save` body:
```json
{ "messages": [{"role": "user"|"assistant", "content": "..."}] }
```

Guard: if `len([m for m in messages if m.role == "user"]) < 3`, return 204 (skip).

### `static/index/views.jsx`

Memory tab added to `RightPanel`. Tab only renders when `agKey === 'notes'`:

```
[Overview] [Notes] [Tasks] [Memory]   ← new tab, Cicero-only
```

Memory card layout (one per session):
```
┌──────────────────────────────────────┐
│ 09 Mei 2026 · Struktur Data          │
│ Topik: Binary Search Tree            │
│ ✓ Dikuasai: insert, search           │  ← --hue-miyamoto color
│ ✗ Masih lemah: deletion              │  ← --hue-lavoiser color
│ 💡 Suka contoh kode Python           │
└──────────────────────────────────────┘
```

Uses existing CSS variables (`--paper-2`, `--clay`, `--ink-3`, `--hue-miyamoto`, `--hue-lavoiser`). Auto-adapts to dark/light theme with zero extra CSS variables.

Fetch: lazy — only on tab click. Shows loading skeleton while fetching.

Tombol "Hapus semua memori" at the bottom — prompts inline confirmation before calling `DELETE /api/memory/cicero`.

### `static/index/app.jsx`

When `setActive(k)` is called and the outgoing agent was `'notes'`, fire:
```javascript
fetch('/api/memory/cicero/save', {
  method: 'POST',
  body: JSON.stringify({ messages: history['notes'] ?? [] })
})
// fire-and-forget — do not await, do not block navigation
```

Same trigger on `window.beforeunload` if active agent is `'notes'`.

### `static/index/data.jsx`

Add `memoryCiceroAPI` helper function alongside existing API helpers.

### `requirements.txt`

Add `openmemory-py`.

---

## API Endpoint Details

### GET /api/memory/cicero
```json
{
  "memories": [
    {
      "id": "abc123",
      "date": "2026-05-09",
      "course": "strukdat",
      "content": "Sesi 2026-05-09 | Mata kuliah: Struktur Data\nTopik: ...",
      "tags": ["strukdat", "2026-05-09"]
    }
  ],
  "total": 2
}
```

### POST /api/memory/cicero/save
- Body: `{ "messages": [{role, content}, ...] }`
- Response 200: `{ "stored": true, "summary": "..." }`
- Response 204: skipped (< 3 user turns)
- Response 500: `{ "error": "..." }`

### DELETE /api/memory/cicero
- Response 200: `{ "deleted": N }`

---

## Error Handling

| Scenario | Handling |
|----------|----------|
| `GEMINI_API_KEY` absent | Auto-fallback to `synthetic` embeddings — system works, lower accuracy. One-time startup warning. |
| `openmemory-py` not installed | `ImportError` caught in `memory_tools.py` — all functions return empty/no-op. Cicero runs normally. |
| `POST /api/memory/cicero/save` fails | Frontend retry once, then silent fail. Session continues unaffected. |
| Session too short (< 3 user turns) | Skip summary generation — 204 response. |
| OpenMemory DB corrupt | Recreate empty DB on next access. Log error, do not crash server. |
| Recall returns 0 memories | Cicero runs with unmodified system prompt. No injection. |
| User deletes all memories | Wipe SQLite entries for `user_id="cicero_naufal"`. UI confirms before execution. |

---

## Setup (One-time)

```bash
pip install openmemory-py
```

Add to `.env`:
```env
GEMINI_API_KEY=your_key    # already present if using Gemma4
OM_DB_PATH=data/openmemory.db   # optional — this is the default
OM_EMBEDDINGS=gemini            # optional — gemini is default when key present
```

`data/openmemory.db` is created automatically on first run. Add to `.gitignore`.

---

## Files Changed Summary

| File | Type | Change |
|------|------|--------|
| `tools/memory_tools.py` | New | OpenMemory wrapper — init, get, store, delete, list |
| `agents/notes_agent.py` | Modified | Inject recalled memories into system prompt |
| `server.py` | Modified | 3 new endpoints: GET/POST/DELETE `/api/memory/cicero` |
| `static/index/views.jsx` | Modified | Memory tab in RightPanel (Cicero-only) |
| `static/index/app.jsx` | Modified | Fire-and-forget save on agent switch + beforeunload |
| `static/index/data.jsx` | Modified | `memoryCiceroAPI` helper |
| `static/index/styles.css` | Modified | Memory card styles (uses existing CSS vars) |
| `requirements.txt` | Modified | Add `openmemory-py` |

---

## Dependencies

All existing — no new packages beyond `openmemory-py`:
- `langchain langchain-mistralai` — agent framework (unchanged)
- `fastapi` — server (unchanged)
- `openmemory-py` — **new**
