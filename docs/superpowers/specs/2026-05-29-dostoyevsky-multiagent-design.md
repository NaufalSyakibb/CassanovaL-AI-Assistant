# Dostoyevsky — Multi-Agent Journaling + Emotion Dashboard Design Spec

**Date:** 2026-05-29
**Status:** Approved for implementation

---

## Context

Dostoyevsky is the CassanovaL journaling agent ("Reflecta") — a warm, empathetic AI companion that guides users through daily journaling via the main chat interface. It already saves entries to `AI Data/Dostoyevsky Agent/Journal_YYYY-MM-DD.md` and the `/journal` page at `static/journal/index.html` already displays entries and a basic mood calendar via `GET /api/journal/dashboard`.

This feature upgrades Dostoyevsky in two directions:

1. **Tighter conversational style** — Agent 1 (Dostoyevsky) is modified so every follow-up question is ≤10 words, keeping the session focused.
2. **Emotion analysis pipeline** — A new Agent 2 (EmotionAgent) automatically analyzes the day's journal after each save and stores a structured emotion snapshot. The `/journal` page gains a **Dashboard tab** showing today's emotion breakdown, what happened, and a 30-day mood calendar.

---

## Goal

After each journal entry is saved by Dostoyevsky, EmotionAgent silently reads the full day's journal and writes an `Emotion_YYYY-MM-DD.json` file with a breakdown of up to 5 detected emotions (with 0–100 intensity scores), a dominant mood label, a "what happened today" factual summary, and a 2-sentence emotional narrative. The `/journal` page Dashboard tab surfaces this data alongside a 30-day mood calendar.

---

## Architecture

### Pipeline

```
User chats with Dostoyevsky (Agent 1)
    ↓
Dostoyevsky calls write_journal_entry()
    ↓
Tool saves Journal_YYYY-MM-DD.md
    ↓ (fire-and-forget daemon thread)
run_emotion_agent(date, journal_content)
    ↓
EmotionAgent (Agent 2) → JSON
    ↓
Emotion_YYYY-MM-DD.json saved alongside journal file
```

### Data Flow

- **Trigger**: `write_journal_entry` tool spawns `threading.Thread(target=_run_emotion_bg, daemon=True)` immediately after saving. The chat response returns without waiting.
- **EmotionAgent input**: full journal file content for the day (read from disk, passed as string)
- **EmotionAgent output**: JSON written to `{JOURNAL_FOLDER}/Emotion_{date}.json`
- **Dashboard API**: `GET /api/journal/dashboard` is extended to merge emotion JSON data into each entry object and return a separate `emotion_today` field
- **Frontend**: `/journal` page gets two tabs — "Entries" (existing) and "Dashboard" (new) — toggled via CSS + JS, no page reload

---

## Agent 1 — Dostoyevsky (Modified)

**File:** `agents/dostyevsky_agent.py`

**Change:** Add one constraint to the existing `SYSTEM_PROMPT`:

```
Question length rule: Every follow-up question you ask must be 10 words or fewer.
The response body before the question has no length limit — be as warm and
thorough as needed. Only the question itself must be concise.
```

The warm, empathetic Reflecta personality, all journaling phases, habit detection, and autoresearch integration remain unchanged.

---

## Agent 2 — EmotionAgent (New)

**File:** `agents/emotion_agent.py`

### Prompt

```
You are EmotionAgent — a precise emotional analyst. You receive the full text of a
personal journal entry and return a structured JSON analysis of the emotional content.

Analyze the journal and identify:
1. The dominant mood (single word: e.g. "anxious", "grateful", "content", "sad")
2. mood_cat: "positive" | "negative" | "neutral"
3. Up to 5 specific emotions present, each with an intensity score 0–100
4. what_happened: 1–2 sentences describing the factual events of the day (objective)
5. summary: 2 sentences describing the overall emotional arc of the day (interpretive)

Return ONLY valid JSON:
{
  "dominant_mood": "...",
  "mood_cat": "positive|negative|neutral",
  "emotions": [
    {"name": "...", "intensity": 0-100},
    ...
  ],
  "what_happened": "...",
  "summary": "..."
}

Rules:
- dominant_mood and emotion names must be lowercase single words
- Limit to the 5 most prominent emotions
- what_happened is factual — no interpretation
- summary is interpretive — describe the emotional journey
- Return ONLY the JSON object, nothing else
```

### Function signature

```python
def run_emotion_agent(date: str, journal_content: str) -> dict:
    """
    Analyzes journal content and saves Emotion_{date}.json.
    Returns the parsed dict or {"error": "..."} on failure.
    """
```

### Background trigger (in `tools/journal_tools.py`)

```python
import threading
from agents.emotion_agent import run_emotion_agent

def _run_emotion_bg(date: str, content: str, journal_dir: Path) -> None:
    result = run_emotion_agent(date, content)
    if "error" not in result:
        out = journal_dir / f"Emotion_{date}.json"
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

# Inside write_journal_entry, after writing the file:
threading.Thread(
    target=_run_emotion_bg,
    args=(today, filepath.read_text(encoding="utf-8"), journal_dir),
    daemon=True
).start()
```

Uses `_invoke_with_retry` and `_parse_json_output` (same pattern as `konten_agent.py`).

---

## Storage

Emotion JSON files live alongside journal entries:

```
AI Data/Dostoyevsky Agent/
  Journal_2026-05-29.md
  Emotion_2026-05-29.json    ← new
  Journal_2026-05-28.md
  Emotion_2026-05-28.json
  ...
```

### Emotion JSON schema

```json
{
  "dominant_mood": "anxious",
  "mood_cat": "negative",
  "emotions": [
    {"name": "anxiety",   "intensity": 72},
    {"name": "fatigue",   "intensity": 58},
    {"name": "hope",      "intensity": 45},
    {"name": "gratitude", "intensity": 30}
  ],
  "what_happened": "Stressful meeting with manager about deadlines. Called a friend in the evening.",
  "summary": "Anxiety dominated most of the day, driven by work pressure. A thread of hope surfaced by end of day through social connection."
}
```

---

## Server Changes

**File:** `server.py`

Modify `GET /api/journal/dashboard` to:

1. For each journal entry, check if `Emotion_{date}.json` exists alongside it. If it does, merge its fields into the entry object as `emotion` key.
2. Add a top-level `emotion_today` field: the emotion data for today's date (or `null` if not yet analyzed).

New response shape (additions only — existing fields unchanged):

```json
{
  "entries": [
    {
      "date": "2026-05-29",
      "mood": "anxious",
      "mood_cat": "negative",
      "emotion": {
        "dominant_mood": "anxious",
        "mood_cat": "negative",
        "emotions": [...],
        "what_happened": "...",
        "summary": "..."
      },
      ...existing fields...
    }
  ],
  "emotion_today": { ...same shape or null... },
  ...existing top-level fields unchanged...
}
```

The `mood` and `mood_cat` fields in each entry are already computed from the frontmatter. If an emotion JSON exists, `mood_cat` from the emotion JSON takes precedence (it's more accurate — EmotionAgent has full context vs. a single keyword from the frontmatter).

---

## Frontend Changes

**File:** `static/journal/index.html`

### Tab system

Add two tabs to the existing page header area:

```html
<div id="tab-bar">
  <button id="tab-entries" class="tab active" onclick="G.showTab('entries')">Entries</button>
  <button id="tab-dashboard" class="tab" onclick="G.showTab('dashboard')">Dashboard</button>
</div>
```

`G.showTab(tab)` sets `display:none/block` on `#view-entries` and `#view-dashboard`.

The existing entries view is wrapped in `<div id="view-entries">`. The new dashboard is `<div id="view-dashboard" style="display:none">`.

### Dashboard view layout

```
┌─────────────────────────────────────┐
│  Streak · This month · Avg mood     │  ← stats row (3 cards)
├──────────────────┬──────────────────┤
│  Emotion bars    │  What happened   │  ← today's analysis (2 cols)
│  + dominant mood │  + summary       │
├─────────────────────────────────────┤
│  30-day mood calendar (colored dots)│
├─────────────────────────────────────┤
│  Recent 7-day mood trend list       │
└─────────────────────────────────────┘
```

**Emotion bars:** for each emotion in `emotion_today.emotions`, render a labeled bar with the intensity as percentage width. Positive emotions (hope, gratitude, joy, calm, content, excited, happy) use green accent; all others use clay (`#B05A3F`).

**Mood calendar:** existing calendar logic already works — it reads `mood_cat` per date. No change needed if the API returns the corrected `mood_cat`.

**"No analysis yet" state:** if `emotion_today` is `null`, show a subtle message: *"Analysis will appear automatically after your next journal entry."*

### JS additions to `G` object

```javascript
G.showTab = function(tab) { /* toggle display on #view-entries / #view-dashboard */ };
G.renderDashboard = function(data) { /* render emotion_today bars + narrative + calendar */ };
G.renderEmotionBars = function(emotions) { /* build bar HTML from emotions array */ };
```

`G.renderDashboard` is called from `G.loadDashboard` (already fetches `/api/journal/dashboard`) after existing rendering, passing `data.emotion_today`.

---

## Tests

**File:** `tests/test_emotion_agent.py`

3 TDD tests (same mock pattern as `test_konten_agent.py`):

```python
def test_run_emotion_agent_returns_required_keys():
    # mock returns valid JSON → assert dominant_mood, mood_cat, emotions, what_happened, summary all present

def test_run_emotion_agent_emotions_list():
    # emotions must be a list, each item has "name" (str) and "intensity" (int 0–100)

def test_run_emotion_agent_handles_parse_error():
    # mock returns non-JSON → assert "error" in result
```

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| EmotionAgent LLM returns unparseable JSON | `{"error": "..."}` — JSON file not written, dashboard shows null |
| Emotion JSON file missing for a date | Entry returned without `emotion` key, `emotion_today` is `null` |
| Rate limit (429) in background thread | `_invoke_with_retry` backs off — no user impact, analysis may be delayed |
| Journal file not found when thread starts | Thread exits silently, no crash |

---

## Files to Create / Modify

| File | Action |
|------|--------|
| `agents/emotion_agent.py` | CREATE — `_EMOTION_PROMPT`, `_invoke_with_retry`, `_parse_json_output`, `run_emotion_agent` |
| `tests/test_emotion_agent.py` | CREATE — 3 TDD tests |
| `tools/journal_tools.py` | MODIFY — spawn background thread in `write_journal_entry` after file save |
| `agents/dostyevsky_agent.py` | MODIFY — add ≤10 word question constraint to `SYSTEM_PROMPT` |
| `server.py` | MODIFY — extend `GET /api/journal/dashboard` to merge emotion JSON data |
| `static/journal/index.html` | MODIFY — add tab bar, Dashboard view with emotion bars + calendar |

---

## Verification

```powershell
# 1. Unit tests
$env:PYTHONUTF8=1; pytest tests/test_emotion_agent.py -v
# Expected: 3 passed

# 2. Regression
$env:PYTHONUTF8=1; pytest tests/ -v
# Expected: all existing tests still pass

# 3. Server import
$env:PYTHONUTF8=1; python -c "import server; print('OK')"

# 4. End-to-end
$env:PYTHONUTF8=1; python server.py
# Open http://localhost:8000 → chat with Dostoyevsky
# Write a journal entry → verify agent asks ≤10-word questions
# After save: check AI Data/Dostoyevsky Agent/ for Emotion_YYYY-MM-DD.json
# Open http://localhost:8000/journal → click "Dashboard" tab
# Verify emotion bars, what_happened, summary, mood calendar all render
# Verify "Entries" tab still works as before
```
