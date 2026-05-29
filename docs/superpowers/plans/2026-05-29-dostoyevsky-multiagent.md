# Dostoyevsky Multi-Agent + Emotion Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Dostoyevsky with concise ≤10-word questions, an auto-triggered EmotionAgent that analyzes each journal entry in a background thread, and a Dashboard tab on the /journal page showing emotion breakdowns, daily narratives, and a 30-day mood calendar.

**Architecture:** Agent 1 (Dostoyevsky) gets a single prompt constraint added. After every `write_journal_entry` tool call, a daemon thread fires `run_emotion_agent(date, content)` which saves `Emotion_YYYY-MM-DD.json` alongside the journal file. The `/api/journal/dashboard` endpoint merges emotion JSON data into each entry and adds `emotion_today`. The /journal page gains a tab bar toggling between Entries (existing) and Dashboard (new) views.

**Tech Stack:** Python/LangChain (mistral-large-latest), FastAPI, threading, vanilla JS (ES5 style already used in the file)

---

## File Map

| File | Action |
|------|--------|
| `agents/emotion_agent.py` | CREATE — `_EMOTION_PROMPT`, `_invoke_with_retry`, `_parse_json_output`, `run_emotion_agent` |
| `tests/test_emotion_agent.py` | CREATE — 3 TDD tests |
| `tools/journal_tools.py` | MODIFY — add `_run_emotion_bg`, spawn thread in `write_journal_entry` |
| `agents/dostyevsky_agent.py` | MODIFY — add ≤10 word question constraint to `SYSTEM_PROMPT` |
| `server.py` | MODIFY — merge emotion JSON data in `get_journal_dashboard` |
| `static/journal/index.html` | MODIFY — tab bar, Dashboard view, JS rendering functions |

---

### Task 1: EmotionAgent + TDD tests

**Files:**
- Create: `tests/test_emotion_agent.py`
- Create: `agents/emotion_agent.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_emotion_agent.py`:

```python
import json
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage


def _fake_agent_result(output_dict: dict):
    return {"messages": [AIMessage(content=json.dumps(output_dict))]}


_VALID_OUTPUT = {
    "dominant_mood": "anxious",
    "mood_cat": "negative",
    "emotions": [
        {"name": "anxiety",   "intensity": 72},
        {"name": "fatigue",   "intensity": 58},
        {"name": "hope",      "intensity": 45},
        {"name": "gratitude", "intensity": 30},
    ],
    "what_happened": "Stressful meeting with manager. Called a friend after, felt lighter.",
    "summary": "Anxiety dominated most of the day. A thread of hope surfaced through social connection.",
}


def test_run_emotion_agent_returns_required_keys():
    from agents.emotion_agent import run_emotion_agent
    with patch("agents.emotion_agent.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(_VALID_OUTPUT)
        mock_build.return_value = mock_agent
        result = run_emotion_agent("2026-05-29", "Today was hard. I had a tough meeting...")
    for key in ("dominant_mood", "mood_cat", "emotions", "what_happened", "summary"):
        assert key in result, f"Missing key: {key}"
    assert isinstance(result["emotions"], list)
    assert len(result["emotions"]) > 0
    assert "name" in result["emotions"][0]
    assert "intensity" in result["emotions"][0]


def test_run_emotion_agent_emotions_structure():
    from agents.emotion_agent import run_emotion_agent
    with patch("agents.emotion_agent.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(_VALID_OUTPUT)
        mock_build.return_value = mock_agent
        result = run_emotion_agent("2026-05-29", "some journal text")
    for em in result["emotions"]:
        assert isinstance(em["name"], str)
        assert isinstance(em["intensity"], int)
        assert 0 <= em["intensity"] <= 100


def test_run_emotion_agent_handles_parse_error():
    from agents.emotion_agent import run_emotion_agent
    with patch("agents.emotion_agent.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "messages": [AIMessage(content="I cannot analyze this.")]
        }
        mock_build.return_value = mock_agent
        result = run_emotion_agent("2026-05-29", "some text")
    assert "error" in result
```

- [ ] **Step 2: Run tests to confirm they fail**

```powershell
$env:PYTHONUTF8=1; pytest tests/test_emotion_agent.py -v
```

Expected: `ModuleNotFoundError: No module named 'agents.emotion_agent'`

- [ ] **Step 3: Create `agents/emotion_agent.py`**

```python
import json
import re
import time
from agents.base import build_agent

_EMOTION_PROMPT = """You are EmotionAgent — a precise emotional analyst. You receive the full text of a personal journal entry and return a structured JSON analysis of the emotional content.

Analyze the journal and identify:
1. The dominant mood (single lowercase word: e.g. "anxious", "grateful", "content", "sad")
2. mood_cat: "positive" | "negative" | "neutral"
3. Up to 5 specific emotions present, each with an intensity score 0–100
4. what_happened: 1–2 sentences describing the factual events of the day (objective, no interpretation)
5. summary: 2 sentences describing the overall emotional arc of the day (interpretive)

Return ONLY valid JSON — no other text:
{
  "dominant_mood": "...",
  "mood_cat": "positive|negative|neutral",
  "emotions": [
    {"name": "...", "intensity": 0},
    {"name": "...", "intensity": 0}
  ],
  "what_happened": "...",
  "summary": "..."
}

Rules:
- dominant_mood and all emotion names must be lowercase single words
- Limit to the 5 most prominent emotions
- what_happened is factual only — no emotional interpretation
- summary describes the emotional journey
- Return ONLY the JSON object, nothing else"""


def _invoke_with_retry(agent, messages: dict, max_retries: int = 5) -> dict:
    delay = 20
    last_exc: Exception = RuntimeError("no retry attempts made")
    for attempt in range(max_retries):
        try:
            return agent.invoke(messages)
        except Exception as e:
            last_exc = e
            if "429" in str(e) or "rate" in str(e).lower():
                time.sleep(delay)
                delay = min(delay * 2, 120)
            else:
                raise
    raise last_exc


def _parse_json_output(agent_result: dict) -> dict:
    messages = agent_result.get("messages", [])
    for msg in reversed(messages):
        content = getattr(msg, "content", "")
        if not content:
            continue
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue
    raw = str(messages[-1]) if messages else "no messages"
    return {"error": "Could not parse agent output", "raw": raw[:500]}


def run_emotion_agent(date: str, journal_content: str) -> dict:
    agent = build_agent(_EMOTION_PROMPT, [])
    user_msg = f"Date: {date}\n\nJournal:\n{journal_content}"
    result = _invoke_with_retry(agent, {"messages": [("human", user_msg)]})
    return _parse_json_output(result)
```

- [ ] **Step 4: Run tests — confirm 3 pass**

```powershell
$env:PYTHONUTF8=1; pytest tests/test_emotion_agent.py -v
```

Expected: 3 passed

- [ ] **Step 5: Run full test suite to confirm no regressions**

```powershell
$env:PYTHONUTF8=1; pytest tests/ -v
```

Expected: all existing tests pass

- [ ] **Step 6: Commit**

```powershell
git add agents/emotion_agent.py tests/test_emotion_agent.py
git commit -m "feat(dostoyevsky): add EmotionAgent with TDD tests"
```

---

### Task 2: Auto-trigger EmotionAgent after journal save

**Files:**
- Modify: `tools/journal_tools.py`

- [ ] **Step 1: Add imports at top of `tools/journal_tools.py`**

Find the existing imports block at the top of the file:
```python
import os
import re
from pathlib import Path
from datetime import datetime
from langchain.tools import tool
```

Replace with:
```python
import json
import os
import re
import threading
from pathlib import Path
from datetime import datetime
from langchain.tools import tool
```

- [ ] **Step 2: Add `_run_emotion_bg` function**

Find the line `JOURNAL_TOOLS = [` near the bottom of the file. Insert this function immediately **before** it:

```python
def _run_emotion_bg(date: str, content: str, journal_dir: Path) -> None:
    try:
        from agents.emotion_agent import run_emotion_agent
        result = run_emotion_agent(date, content)
        if "error" not in result:
            out = journal_dir / f"Emotion_{date}.json"
            out.write_text(
                json.dumps(result, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
    except Exception:
        pass


```

- [ ] **Step 3: Spawn thread at the end of `write_journal_entry`**

In the `write_journal_entry` function, find the return statement:
```python
        return (
            f"✓ Entri jurnal disimpan → {JOURNAL_FOLDER}/{filename}\n"
            f"  Bagian: '{section_title}'"
            + (f" | Mood: {mood}" if mood else "")
        )
```

Insert the thread spawn immediately **before** the `return` statement:

```python
        threading.Thread(
            target=_run_emotion_bg,
            args=(today, filepath.read_text(encoding="utf-8"), journal_dir),
            daemon=True,
        ).start()

        return (
            f"✓ Entri jurnal disimpan → {JOURNAL_FOLDER}/{filename}\n"
            f"  Bagian: '{section_title}'"
            + (f" | Mood: {mood}" if mood else "")
        )
```

- [ ] **Step 4: Verify server imports cleanly**

```powershell
$env:PYTHONUTF8=1; python -c "import server; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```powershell
git add tools/journal_tools.py
git commit -m "feat(dostoyevsky): auto-trigger EmotionAgent after journal save"
```

---

### Task 3: Add ≤10-word question constraint to Dostoyevsky

**Files:**
- Modify: `agents/dostyevsky_agent.py`

- [ ] **Step 1: Add constraint to SYSTEM_PROMPT**

In `agents/dostyevsky_agent.py`, find the `SYSTEM_PROMPT` string. Find this section:

```
Gaya Bahasa & Nada
```

Insert the following block immediately **before** that section (after the closing of the "Teknik Prompt Jurnal" section):

```
Question Length Rule
Every follow-up question you ask the user must be 10 words or fewer. Count carefully.
The response body before the question has no length limit — be as warm, empathetic,
and thorough as the moment calls for. Only the question itself must be concise.
Examples of compliant questions (≤10 words):
  "What does that heaviness feel like right now?"  (9 words) ✓
  "How long have you been carrying it?"  (8 words) ✓
  "Is there a moment it started?"  (7 words) ✓
  "Who else knows about this?"  (5 words) ✓

```

- [ ] **Step 2: Verify server imports cleanly**

```powershell
$env:PYTHONUTF8=1; python -c "import server; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```powershell
git add agents/dostyevsky_agent.py
git commit -m "feat(dostoyevsky): constrain follow-up questions to 10 words or fewer"
```

---

### Task 4: Extend /api/journal/dashboard with emotion data

**Files:**
- Modify: `server.py` (function `get_journal_dashboard`, around line 539)

- [ ] **Step 1: Merge emotion JSON into each entry**

In `server.py`, find the `get_journal_dashboard` function. Locate this block inside the `for f in files:` loop:

```python
        cat = mood_cat(mood)
        entries.append({"date":date_str,"date_label":date_label,"day_name":day_name,"mood":mood,"mood_cat":cat,"word_count":wc,"preview":preview,"content":body})
        mood_history.append({"date":date_str,"mood":mood,"mood_cat":cat})
```

Replace with:

```python
        cat = mood_cat(mood)
        # Load emotion analysis JSON if available
        emotion_data = None
        emotion_path = journal_dir / f"Emotion_{date_str}.json"
        if emotion_path.exists():
            try:
                emotion_data = json.loads(emotion_path.read_text(encoding="utf-8"))
                if emotion_data.get("mood_cat") in ("positive", "negative", "neutral"):
                    cat = emotion_data["mood_cat"]
            except Exception:
                emotion_data = None
        entries.append({"date":date_str,"date_label":date_label,"day_name":day_name,"mood":mood,"mood_cat":cat,"word_count":wc,"preview":preview,"content":body,"emotion":emotion_data})
        mood_history.append({"date":date_str,"mood":mood,"mood_cat":cat})
```

- [ ] **Step 2: Add `emotion_today` to the return value**

Find the `return {` at the end of `get_journal_dashboard`:

```python
    return {
        "entries": entries,
        "today": next((e for e in entries if e["date"]==today_str), None),
        "streak": streak,
        "total_entries": len(entries),
        "mood_history": mood_history,
        "tags": sorted(all_tags),
        "this_month_count": sum(1 for e in entries if e["date"].startswith(cur_month)),
        "current_month_label": f"{MONTH_NAMES[now.month-1]} {now.year}",
    }
```

Replace with:

```python
    emotion_today = next(
        (e.get("emotion") for e in entries if e["date"] == today_str and e.get("emotion")),
        None,
    )
    return {
        "entries": entries,
        "today": next((e for e in entries if e["date"]==today_str), None),
        "streak": streak,
        "total_entries": len(entries),
        "mood_history": mood_history,
        "tags": sorted(all_tags),
        "this_month_count": sum(1 for e in entries if e["date"].startswith(cur_month)),
        "current_month_label": f"{MONTH_NAMES[now.month-1]} {now.year}",
        "emotion_today": emotion_today,
    }
```

- [ ] **Step 3: Verify server imports cleanly**

```powershell
$env:PYTHONUTF8=1; python -c "import server; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```powershell
git add server.py
git commit -m "feat(dostoyevsky): extend dashboard API with emotion breakdown data"
```

---

### Task 5: Journal page — tab bar + Dashboard view

**Files:**
- Modify: `static/journal/index.html`

This task has 5 sub-edits. Apply them in order.

#### 5a — Tab CSS

- [ ] **Step 1: Add tab CSS inside `<style>`**

Find the line (near the end of the `<style>` block, before `</style>`):
```css
.chat-drawer {
```

Insert before it:

```css
/* ── Dashboard tabs ── */
.tab-bar {
  display: flex;
  border-bottom: 1px solid var(--rule);
  background: var(--surface);
  flex-shrink: 0;
}
.tab-btn {
  padding: 10px 20px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-4);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  transition: color .15s, border-color .15s;
}
.tab-btn.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}
/* ── Dashboard view ── */
#view-dashboard {
  flex: 1;
  overflow-y: auto;
  padding: 24px 28px;
  display: none;
}
.dash-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 20px;
}
.dash-stat {
  background: var(--surface);
  border: 1px solid var(--rule);
  border-radius: 8px;
  padding: 14px 16px;
}
.dash-stat-lbl {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 8px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-4);
  margin-bottom: 6px;
}
.dash-stat-val {
  font-family: 'Instrument Serif', serif;
  font-size: 22px;
  font-style: italic;
  color: var(--ink);
}
.dash-section-lbl {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink-4);
  margin-bottom: 12px;
}
.dash-today {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 20px;
}
@media (max-width: 600px) { .dash-today { grid-template-columns: 1fr; } .dash-stats { grid-template-columns: 1fr; } }
.dash-card {
  background: var(--surface);
  border: 1px solid var(--rule);
  border-radius: 8px;
  padding: 16px 18px;
}
.dash-dominant {
  font-family: 'Instrument Serif', serif;
  font-size: 20px;
  font-style: italic;
  color: var(--accent);
  margin-bottom: 12px;
}
.emo-bar-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 5px 0;
}
.emo-bar-name {
  font-size: 10px;
  color: var(--ink-3);
  width: 72px;
  flex-shrink: 0;
  text-transform: capitalize;
}
.emo-bar-track {
  flex: 1;
  height: 5px;
  background: var(--rule);
  border-radius: 3px;
  overflow: hidden;
}
.emo-bar-fill {
  height: 100%;
  border-radius: 3px;
  background: var(--negative);
}
.emo-bar-fill.positive { background: var(--positive); }
.emo-bar-pct {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  color: var(--ink-4);
  width: 26px;
  text-align: right;
}
.dash-narrative-section { margin-bottom: 10px; }
.dash-narrative-lbl {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 8px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-4);
  margin-bottom: 4px;
}
.dash-narrative-text {
  font-size: 12px;
  line-height: 1.65;
  color: var(--ink-2);
}
.dash-empty {
  font-size: 12px;
  color: var(--ink-4);
  font-style: italic;
  padding: 20px 0;
}
.dash-calendar {
  background: var(--surface);
  border: 1px solid var(--rule);
  border-radius: 8px;
  padding: 16px 18px;
  margin-bottom: 20px;
}
.cal-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 10px;
}
.cal-cell {
  width: 22px;
  height: 22px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 8px;
  color: var(--ink-4);
  cursor: default;
}
.cal-cell.has-entry { color: rgba(255,255,255,0.85); }
.cal-cell.mood-positive { background: var(--positive); }
.cal-cell.mood-negative { background: var(--negative); }
.cal-cell.mood-neutral  { background: var(--neutral); }
.cal-cell.mood-none     { background: var(--paper-3); }
.cal-cell.no-entry      { background: var(--paper-2); }
.cal-legend {
  display: flex;
  gap: 14px;
  margin-top: 10px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  color: var(--ink-4);
}
.cal-legend-dot { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 4px; vertical-align: middle; }
.dash-trend {
  background: var(--surface);
  border: 1px solid var(--rule);
  border-radius: 8px;
  padding: 16px 18px;
}
.trend-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 5px 0;
  border-bottom: 1px solid var(--rule-soft);
}
.trend-row:last-child { border-bottom: none; }
.trend-date {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  color: var(--ink-4);
  width: 72px;
  flex-shrink: 0;
}
.trend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--ink-5);
}
.trend-dot.positive { background: var(--positive); }
.trend-dot.negative { background: var(--negative); }
.trend-dot.neutral  { background: var(--neutral); }
.trend-mood {
  font-size: 11px;
  color: var(--ink-2);
  font-style: italic;
}
```

#### 5b — Tab bar HTML + wrap entries view

- [ ] **Step 2: Add tab bar and wrap page-scroll in `#view-entries`**

Find in the HTML:
```html
    <div class="page-scroll" id="page-scroll">
```

Replace with:
```html
    <div class="tab-bar">
      <button id="tab-entries" class="tab-btn active" onclick="showTab('entries')">Entries</button>
      <button id="tab-dashboard" class="tab-btn" onclick="showTab('dashboard')">Dashboard</button>
    </div>

    <div id="view-entries">
    <div class="page-scroll" id="page-scroll">
```

Then find the closing tag that ends the page-scroll section:
```html
    </div>

    <div class="composer">
```

Replace with:
```html
    </div>
    </div><!-- /#view-entries -->

    <div id="view-dashboard"></div>

    <div class="composer">
```

#### 5c — JS: `showTab` function

- [ ] **Step 3: Add `showTab` function**

Find in the `<script>` section the line:
```javascript
function localDateStr(d) {
```

Insert immediately before it:

```javascript
/* ══ Tabs ══ */
function showTab(tab) {
  var isEntries = tab === 'entries';
  document.getElementById('view-entries').style.display  = isEntries ? '' : 'none';
  document.getElementById('view-dashboard').style.display = isEntries ? 'none' : '';
  document.getElementById('tab-entries').classList.toggle('active', isEntries);
  document.getElementById('tab-dashboard').classList.toggle('active', !isEntries);
  if (!isEntries && _data) renderDashboard(_data);
}

```

#### 5d — JS: `renderDashboard`, `renderEmotionBars` functions

- [ ] **Step 4: Add dashboard rendering functions**

Find the line:
```javascript
/* ══ Sidebar ══ */
```

Insert immediately before it:

```javascript
/* ══ Dashboard ══ */
var POSITIVE_EMOTIONS = new Set(['hope','gratitude','joy','calm','content','excited','happy','relief','pride','love','inspired','peaceful','energized','satisfied']);

function renderEmotionBars(emotions) {
  if (!emotions || !emotions.length) return '<div class="dash-empty">No emotion data.</div>';
  return emotions.map(function(em) {
    var isPosClass = POSITIVE_EMOTIONS.has(em.name) ? ' positive' : '';
    return '<div class="emo-bar-row">' +
      '<div class="emo-bar-name">' + esc(em.name) + '</div>' +
      '<div class="emo-bar-track"><div class="emo-bar-fill' + isPosClass + '" style="width:' + Math.min(100, em.intensity||0) + '%"></div></div>' +
      '<div class="emo-bar-pct">' + (em.intensity||0) + '%</div>' +
    '</div>';
  }).join('');
}

function renderDashboard(data) {
  var dash = document.getElementById('view-dashboard');
  if (!dash) return;
  var em = data.emotion_today;
  var todayHTML = em
    ? '<div class="dash-today">' +
        '<div class="dash-card">' +
          '<div class="dash-section-lbl">Emotion Breakdown</div>' +
          '<div class="dash-dominant">' + esc(em.dominant_mood||'—') + '</div>' +
          renderEmotionBars(em.emotions) +
        '</div>' +
        '<div class="dash-card">' +
          '<div class="dash-narrative-section">' +
            '<div class="dash-narrative-lbl">What happened</div>' +
            '<div class="dash-narrative-text">' + esc(em.what_happened||'—') + '</div>' +
          '</div>' +
          '<div class="dash-narrative-section">' +
            '<div class="dash-narrative-lbl">Emotional summary</div>' +
            '<div class="dash-narrative-text">' + esc(em.summary||'—') + '</div>' +
          '</div>' +
        '</div>' +
      '</div>'
    : '<div class="dash-empty">Analysis will appear automatically after your next journal entry.</div>';

  // Build 30-day calendar
  var moodMap = {};
  (data.mood_history||[]).forEach(function(m){ moodMap[m.date] = m.mood_cat; });
  var entrySet = new Set((data.entries||[]).map(function(e){ return e.date; }));
  var today = new Date();
  var calCells = '';
  for (var i = 29; i >= 0; i--) {
    var d = new Date(today); d.setDate(today.getDate() - i);
    var ds = d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
    var hasEntry = entrySet.has(ds);
    var mc = hasEntry ? (moodMap[ds]||'none') : '';
    var cls = hasEntry ? ('cal-cell has-entry mood-' + mc) : 'cal-cell no-entry';
    calCells += '<div class="' + cls + '" title="' + ds + '">' + d.getDate() + '</div>';
  }

  // 7-day trend
  var trendRows = '';
  var MN = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  for (var j = 0; j < Math.min(7, (data.entries||[]).length); j++) {
    var en = data.entries[j];
    var dt = new Date(en.date + 'T00:00:00');
    var dlbl = dt.getDate() + ' ' + MN[dt.getMonth()];
    trendRows += '<div class="trend-row">' +
      '<div class="trend-date">' + dlbl + '</div>' +
      '<div class="trend-dot ' + (en.mood_cat||'') + '"></div>' +
      '<div class="trend-mood">' + esc(en.mood||'—') + '</div>' +
    '</div>';
  }

  dash.innerHTML =
    '<div class="dash-stats">' +
      '<div class="dash-stat"><div class="dash-stat-lbl">Streak</div><div class="dash-stat-val">' + (data.streak||0) + ' days</div></div>' +
      '<div class="dash-stat"><div class="dash-stat-lbl">This month</div><div class="dash-stat-val">' + (data.this_month_count||0) + ' entries</div></div>' +
      '<div class="dash-stat"><div class="dash-stat-lbl">Total</div><div class="dash-stat-val">' + (data.total_entries||0) + '</div></div>' +
    '</div>' +
    '<div class="dash-section-lbl">Today\'s Analysis</div>' +
    todayHTML +
    '<div class="dash-calendar">' +
      '<div class="dash-section-lbl">30-day mood history</div>' +
      '<div class="cal-grid">' + calCells + '</div>' +
      '<div class="cal-legend">' +
        '<span><span class="cal-legend-dot" style="background:var(--positive)"></span>Positive</span>' +
        '<span><span class="cal-legend-dot" style="background:var(--neutral)"></span>Neutral</span>' +
        '<span><span class="cal-legend-dot" style="background:var(--negative)"></span>Negative</span>' +
        '<span><span class="cal-legend-dot" style="background:var(--paper-3)"></span>No data</span>' +
        '<span><span class="cal-legend-dot" style="background:var(--paper-2)"></span>No entry</span>' +
      '</div>' +
    '</div>' +
    '<div class="dash-trend">' +
      '<div class="dash-section-lbl" style="margin-bottom:8px">Recent mood trend</div>' +
      trendRows +
    '</div>';
}

```

#### 5e — Wire dashboard render into loadJournal

- [ ] **Step 5: Call `renderDashboard` from `loadJournal`**

Find in the `loadJournal` function:
```javascript
    renderSidebar();
    renderWeekStrip();
```

Replace with:
```javascript
    renderSidebar();
    renderWeekStrip();
    renderDashboard(data);
```

- [ ] **Step 6: Commit**

```powershell
git add static/journal/index.html
git commit -m "feat(dostoyevsky): add Dashboard tab with emotion breakdown and mood calendar"
```

---

### Task 6: Verification

- [ ] **Step 1: Run all tests**

```powershell
$env:PYTHONUTF8=1; pytest tests/ -v
```

Expected: all tests pass including 3 new emotion_agent tests

- [ ] **Step 2: Server import check**

```powershell
$env:PYTHONUTF8=1; python -c "import server; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Manual end-to-end**

```powershell
$env:PYTHONUTF8=1; python server.py
```

Checklist:
- Open `http://localhost:8000` → chat with Dostoyevsky
- Write a few messages → Reflecta should respond with follow-up questions ≤10 words
- Ask Dostoyevsky to save the journal entry ("Simpan entri jurnal hari ini")
- Check `AI Data/Dostoyevsky Agent/` for `Emotion_YYYY-MM-DD.json` (may take ~15-30s to appear)
- Open `http://localhost:8000/journal` → verify "Entries" tab shows existing view unchanged
- Click "Dashboard" tab → verify stats row, today's emotion bars, what happened, summary, 30-day calendar, trend list all render
- Verify "Entries" tab still works correctly after switching back
- If no emotion JSON exists yet, Dashboard shows "Analysis will appear automatically…" message
