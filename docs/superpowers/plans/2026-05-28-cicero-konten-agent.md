# Cicero KontenAgent — IG/TikTok Carousel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an on-demand KontenAgent button to the Cicero study page that generates a 4-slide Instagram/TikTok carousel, lets the user toggle between two visual themes, and download as 4 PNG files or a single PDF.

**Architecture:** A new `agents/konten_agent.py` (LangChain, `build_agent`, no tools) rewrites study data into a social-friendly JSON payload. A new `POST /api/study/konten` endpoint wraps it async. The study page renders two theme variants for each slide simultaneously in the DOM; CSS driven by `data-konten-theme` on `#konten-panel` hides the inactive theme — no re-render on toggle. `html2canvas` and `jsPDF` (both loaded from CDN) handle download.

**Tech Stack:** Python/LangChain (mistral-large-latest), FastAPI, vanilla JS, html2canvas 1.4.1, jsPDF 2.5.1

---

## File Map

| File | Action |
|------|--------|
| `agents/konten_agent.py` | CREATE — `_KONTEN_PROMPT`, `_invoke_with_retry`, `_parse_json_output`, `run_konten_agent` |
| `tests/test_konten_agent.py` | CREATE — 3 TDD tests (mock `build_agent`) |
| `server.py` | MODIFY — add `KontenRequest` model + `POST /api/study/konten` after line 1488 |
| `static/study/index.html` | MODIFY — CDN `<script>` in `<head>`, CSS, `#konten-panel` HTML, JS functions, footer button |

---

### Task 1: konten_agent.py + tests (TDD)

**Files:**
- Create: `tests/test_konten_agent.py`
- Create: `agents/konten_agent.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_konten_agent.py`:

```python
import json
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage


def _fake_agent_result(output_dict: dict):
    return {"messages": [AIMessage(content=json.dumps(output_dict))]}


_VALID_OUTPUT = {
    "cover": {"hook": "Why do plants literally eat sunlight?"},
    "highlights": [
        "Chlorophyll absorbs light energy from the sun",
        "Water and CO2 combine to form glucose",
        "Oxygen is released as a byproduct",
        "Two stages: light reactions and Calvin cycle",
    ],
    "concepts": [
        {"term": "Chlorophyll", "def": "Green pigment absorbing solar energy"},
        {"term": "ATP", "def": "Energy currency produced in light reactions"},
        {"term": "Stroma", "def": "Site of the Calvin cycle in chloroplasts"},
        {"term": "NADPH", "def": "Electron carrier from light reactions"},
        {"term": "Glucose", "def": "Sugar produced by the Calvin cycle"},
        {"term": "Stomata", "def": "Pores that let CO2 enter the leaf"},
    ],
    "summary": "Photosynthesis converts light into chemical energy stored as glucose. It has two stages: light reactions produce ATP and NADPH, while the Calvin cycle uses them to fix CO2 into sugar.",
    "hashtags": ["#Photosynthesis", "#StudyTok", "#LearnWithMe", "#CornellNotes"],
}


def test_run_konten_agent_returns_required_keys():
    from agents.konten_agent import run_konten_agent
    with patch("agents.konten_agent.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(_VALID_OUTPUT)
        mock_build.return_value = mock_agent
        result = run_konten_agent(
            "Photosynthesis",
            {"sections": [{"title": "Overview", "content": "..."}]},
            {"concepts": [{"term": "Chlorophyll", "definition": "..."}]},
            {"summary": "Photosynthesis is..."},
        )
    for key in ("cover", "highlights", "concepts", "summary", "hashtags"):
        assert key in result, f"Missing key: {key}"
    assert "hook" in result["cover"]


def test_run_konten_agent_highlights_count():
    from agents.konten_agent import run_konten_agent
    with patch("agents.konten_agent.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(_VALID_OUTPUT)
        mock_build.return_value = mock_agent
        result = run_konten_agent("Photosynthesis", {}, {}, {})
    assert isinstance(result["highlights"], list)
    assert len(result["highlights"]) == 4


def test_run_konten_agent_handles_parse_error():
    from agents.konten_agent import run_konten_agent
    with patch("agents.konten_agent.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "messages": [AIMessage(content="Sorry, I cannot process that.")]
        }
        mock_build.return_value = mock_agent
        result = run_konten_agent("Photosynthesis", {}, {}, {})
    assert "error" in result
```

- [ ] **Step 2: Run tests to confirm they fail**

```powershell
$env:PYTHONUTF8=1; pytest tests/test_konten_agent.py -v
```

Expected: `ModuleNotFoundError: No module named 'agents.konten_agent'`

- [ ] **Step 3: Create `agents/konten_agent.py`**

```python
import json
import re
import time
from agents.base import build_agent

_KONTEN_PROMPT = """You are KontenAgent — a social media content specialist who transforms study notes into engaging Instagram/TikTok carousel content.

You receive: a topic, material sections (3–5), key concepts (6–12 terms), and a summary.

Your task:
- Rewrite content for a young audience (high school / college), casual but informative tone
- Write a punchy opening hook that sparks curiosity (max 15 words)
- Pick the 4 most important points from the material (max 12 words each)
- Pick the 6 most essential concepts, shorten definitions (max 8 words each)
- Summarize the core insight in 2–3 sentences with a social-media-friendly tone
- Write 4 relevant hashtags (mix of topic-specific and study-community tags)

Return ONLY valid JSON (no other text):
{
  "cover": { "hook": "..." },
  "highlights": ["...", "...", "...", "..."],
  "concepts": [
    {"term": "...", "def": "..."},
    {"term": "...", "def": "..."},
    {"term": "...", "def": "..."},
    {"term": "...", "def": "..."},
    {"term": "...", "def": "..."},
    {"term": "...", "def": "..."}
  ],
  "summary": "...",
  "hashtags": ["#...", "#...", "#...", "#..."]
}"""


def _invoke_with_retry(agent, messages: dict, max_retries: int = 5) -> dict:
    delay = 20
    last_exc = None
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


def run_konten_agent(topic: str, materi: dict, konsep: dict, ringkasan: dict) -> dict:
    sections = materi.get("sections", [])
    concepts = konsep.get("concepts", [])
    summary = ringkasan.get("summary", "")

    materi_text = "\n".join(
        f"Section: {s.get('title','')}\n{s.get('content','')}" for s in sections
    )
    konsep_text = "\n".join(
        f"- {c.get('term','')}: {c.get('definition','')}" for c in concepts
    )

    user_msg = (
        f"Topic: {topic}\n\n"
        f"Material:\n{materi_text}\n\n"
        f"Key Concepts:\n{konsep_text}\n\n"
        f"Summary:\n{summary}"
    )

    agent = build_agent(_KONTEN_PROMPT, [])
    result = _invoke_with_retry(agent, {"messages": [("human", user_msg)]})
    return _parse_json_output(result)
```

- [ ] **Step 4: Run tests — confirm 3 pass**

```powershell
$env:PYTHONUTF8=1; pytest tests/test_konten_agent.py -v
```

Expected:
```
PASSED tests/test_konten_agent.py::test_run_konten_agent_returns_required_keys
PASSED tests/test_konten_agent.py::test_run_konten_agent_highlights_count
PASSED tests/test_konten_agent.py::test_run_konten_agent_handles_parse_error
3 passed
```

- [ ] **Step 5: Run existing study tests to confirm no regressions**

```powershell
$env:PYTHONUTF8=1; pytest tests/test_study_agents.py -v
```

Expected: 3 passed (same as before)

- [ ] **Step 6: Commit**

```powershell
git add agents/konten_agent.py tests/test_konten_agent.py
git commit -m "feat(cicero): add KontenAgent — carousel content generator with TDD tests"
```

---

### Task 2: server.py — add POST /api/study/konten

**Files:**
- Modify: `server.py` (after line 1488, before `# ── Stock Picks Screener`)

- [ ] **Step 1: Add endpoint after line 1488**

Open `server.py`. Find the block ending at line 1488:
```python
    notes_path.write_text(json.dumps(notes, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"id": note["id"], "title": note["title"]}
```

Insert the following immediately after (before the `# ── Stock Picks Screener` comment):

```python

class KontenRequest(BaseModel):
    topic: str
    materi: dict
    konsep: dict
    ringkasan: dict


@app.post("/api/study/konten")
async def study_konten(req: KontenRequest):
    from agents.konten_agent import run_konten_agent
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, run_konten_agent,
        req.topic, req.materi, req.konsep, req.ringkasan
    )
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result
```

- [ ] **Step 2: Verify server imports cleanly**

```powershell
$env:PYTHONUTF8=1; python -c "import server; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```powershell
git add server.py
git commit -m "feat(cicero): add POST /api/study/konten endpoint"
```

---

### Task 3: static/study/index.html — carousel UI

**Files:**
- Modify: `static/study/index.html`

This task has 5 sub-steps applied sequentially to the same file.

#### 3a — CDN script tags in `<head>`

- [ ] **Step 1: Add CDN scripts before `</head>`**

Find the line `<style>` (line 10) — insert the two CDN `<script>` tags immediately **before** the opening `<style>` tag:

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
```

#### 3b — CSS for konten panel

- [ ] **Step 2: Add CSS block inside `<style>`**

Find `#toast.show {` and the rule block that follows it. After the closing `}` of `#toast.show`, insert:

```css
/* ── KontenAgent carousel ── */
#konten-panel {
  display: none;
  flex-direction: column;
  gap: 16px;
  padding: 24px 28px 28px;
  border-top: 1px solid var(--rule);
}
.konten-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.konten-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--dim);
}
.konten-theme-btn {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  padding: 5px 12px;
  border: 1px solid var(--rule-2);
  border-radius: 4px;
  background: var(--paper);
  color: var(--dim);
  cursor: pointer;
  transition: border-color .15s, color .15s;
}
.konten-theme-btn.active {
  border-color: var(--margin);
  color: var(--margin);
}
.slide-row {
  display: flex;
  gap: 16px;
  overflow-x: auto;
  padding-bottom: 8px;
}
.konten-slide {
  width: 540px;
  height: 540px;
  flex-shrink: 0;
  border-radius: 8px;
  overflow: hidden;
  position: relative;
}
/* ── Vibrant Dark theme ── */
.ks-vibrant {
  width: 540px; height: 540px;
  background: linear-gradient(145deg, #0f0c29, #302b63, #24243e);
  color: #fff;
  font-family: 'Inter', sans-serif;
  padding: 48px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  position: relative;
  box-sizing: border-box;
}
.ks-v-eyebrow {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  opacity: 0.5;
}
.ks-v-num {
  font-size: 80px;
  font-weight: 900;
  line-height: 1;
  background: linear-gradient(90deg, #a78bfa, #60a5fa);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.ks-v-title {
  font-size: 32px;
  font-weight: 800;
  line-height: 1.2;
}
.ks-v-hook {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.4;
  color: #e0d9ff;
}
.ks-v-divider {
  width: 56px;
  height: 3px;
  background: linear-gradient(90deg, #a78bfa, #60a5fa);
  border-radius: 2px;
}
.ks-v-heading {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #a78bfa;
}
.ks-v-chip {
  background: rgba(255,255,255,0.08);
  border-left: 3px solid #a78bfa;
  border-radius: 0 6px 6px 0;
  padding: 10px 14px;
  font-size: 15px;
  line-height: 1.4;
}
.ks-v-chip:nth-child(2) { border-color: #60a5fa; }
.ks-v-chip:nth-child(3) { border-color: #34d399; }
.ks-v-chip:nth-child(4) { border-color: #fbbf24; }
.ks-v-concept-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}
.ks-v-concept-row .ks-v-term {
  color: #c4b5fd;
  font-weight: 700;
  font-size: 14px;
  flex-shrink: 0;
  width: 140px;
}
.ks-v-concept-row .ks-v-def {
  font-size: 13px;
  color: rgba(255,255,255,0.75);
  line-height: 1.4;
}
.ks-v-summary-box {
  background: rgba(255,255,255,0.07);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 8px;
  padding: 20px;
  font-size: 15px;
  line-height: 1.65;
  color: #e0d9ff;
  font-style: italic;
}
.ks-v-hashtags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.ks-v-hashtag {
  background: rgba(167,139,250,0.15);
  color: #a78bfa;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 4px;
}
.ks-v-cta {
  margin-top: auto;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: rgba(255,255,255,0.45);
  font-family: 'JetBrains Mono', monospace;
}
.ks-v-swipe {
  margin-top: auto;
  font-size: 12px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: rgba(255,255,255,0.35);
  font-family: 'JetBrains Mono', monospace;
}
.ks-v-dots {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}
.ks-v-dots span {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: rgba(255,255,255,0.25);
}
.ks-v-dots span.active { background: #a78bfa; }

/* ── Bold Editorial theme ── */
.ks-editorial {
  width: 540px; height: 540px;
  background: #F5F0E8;
  color: #1A1814;
  font-family: 'Inter', sans-serif;
  display: flex;
  flex-direction: column;
  position: relative;
  box-sizing: border-box;
  overflow: hidden;
}
.ks-e-header {
  background: #1A1814;
  padding: 36px 44px 28px;
  color: white;
  flex-shrink: 0;
}
.ks-e-eyebrow {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  opacity: 0.45;
}
.ks-e-title {
  font-family: 'Instrument Serif', serif;
  font-size: 36px;
  font-style: italic;
  line-height: 1.2;
  margin-top: 8px;
}
.ks-e-hook {
  font-size: 18px;
  font-style: italic;
  line-height: 1.4;
  color: rgba(255,255,255,0.8);
  margin-top: 10px;
}
.ks-e-body {
  padding: 28px 44px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 14px;
  overflow: hidden;
}
.ks-e-tag {
  display: inline-flex;
  background: #1A1814;
  color: white;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  padding: 4px 10px;
  border-radius: 2px;
  align-self: flex-start;
}
.ks-e-accent {
  width: 36px;
  height: 4px;
  background: #B05A3F;
  border-radius: 2px;
}
.ks-e-chip {
  font-size: 15px;
  line-height: 1.5;
  color: #2d2d2d;
  padding: 8px 0;
  border-bottom: 1px solid #E8E1D2;
}
.ks-e-concept-row {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}
.ks-e-num {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  color: #B05A3F;
  font-weight: 600;
  flex-shrink: 0;
  padding-top: 1px;
  width: 28px;
}
.ks-e-term { font-size: 15px; font-weight: 700; color: #1A1814; }
.ks-e-def  { font-size: 13px; color: #6E6450; line-height: 1.4; }
.ks-e-summary-box {
  border-left: 3px solid #B05A3F;
  padding: 14px 18px;
  font-size: 14px;
  line-height: 1.65;
  color: #2d2d2d;
  background: rgba(176,90,63,0.06);
}
.ks-e-hashtags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.ks-e-hashtag {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #B05A3F;
}
.ks-e-footer {
  padding: 14px 44px 20px;
  border-top: 2px solid #1A1814;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #6E6450;
  display: flex;
  justify-content: space-between;
  flex-shrink: 0;
}
.ks-e-swipe {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #9B9078;
}
.ks-e-cta {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #6E6450;
}

/* Theme visibility toggle */
[data-konten-theme="vibrant"] .ks-editorial { display: none; }
[data-konten-theme="editorial"] .ks-vibrant  { display: none; }
```

#### 3c — `#konten-panel` HTML

- [ ] **Step 3: Insert `#konten-panel` after `#main-wrap`**

Find `    </div><!-- /#main-wrap -->` and insert immediately after it (before `<!-- Footer -->`):

```html
    <!-- KontenAgent carousel panel -->
    <div id="konten-panel" data-konten-theme="vibrant">
      <div class="konten-toolbar">
        <span class="konten-label">Theme:</span>
        <button id="btn-theme-v" class="konten-theme-btn active" onclick="G.setKontenTheme('vibrant')">A · Vibrant</button>
        <button id="btn-theme-e" class="konten-theme-btn"        onclick="G.setKontenTheme('editorial')">C · Editorial</button>
        <button id="btn-dl-png" class="btn-ghost" onclick="G.downloadPNG()">&#8675; Download PNG (4 files)</button>
        <button id="btn-dl-pdf" class="btn-ghost" onclick="G.downloadPDF()">&#8675; Download PDF</button>
      </div>
      <div class="slide-row" id="slide-row"></div>
    </div>
```

#### 3d — footer `#btn-konten`

- [ ] **Step 4: Add button to footer**

Find:
```html
        <button class="btn-ghost foot-state-hidden" id="btn-save">Simpan ke Catatan</button>
```

Replace with:
```html
        <button class="btn-ghost foot-state-hidden" id="btn-save">Simpan ke Catatan</button>
        <button class="btn-ghost foot-state-hidden" id="btn-konten">&#10022; Create IG Content</button>
```

#### 3e — JavaScript

- [ ] **Step 5: Add `G.kontenData` property**

Find `G.es.onerror` handler closing brace and the line `    save: function(){`. Just before `save: function(){`, add a blank line and:

```javascript
    kontenData: null,

    genKonten: function(){
      var topic = $('topic-input').value.trim();
      if (!topic || !G.state.ringkasan.summary) return;
      $('btn-konten').disabled = true;
      $('btn-konten').textContent = 'Generating…';
      fetch('/api/study/konten', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({topic: topic, materi: G.state.materi, konsep: G.state.konsep, ringkasan: G.state.ringkasan})
      })
      .then(function(r){ return r.json(); })
      .then(function(d){
        G.kontenData = d;
        G.renderKonten(topic, d);
        $('konten-panel').style.display = 'flex';
        $('btn-konten').textContent = '✦ Create IG Content';
        $('btn-konten').disabled = false;
        $('konten-panel').scrollIntoView({behavior: 'smooth', block: 'nearest'});
      })
      .catch(function(e){
        G.toast('Failed to generate content: ' + e.message, 4000);
        $('btn-konten').disabled = false;
        $('btn-konten').textContent = '✦ Create IG Content';
      });
    },

    renderKonten: function(topic, d){
      var row = $('slide-row');
      row.innerHTML = '';
      var slides = [
        G._buildSlide1(topic, d),
        G._buildSlide2(d),
        G._buildSlide3(d),
        G._buildSlide4(d),
      ];
      slides.forEach(function(pair, i){
        var wrap = document.createElement('div');
        wrap.className = 'konten-slide';
        wrap.setAttribute('data-slide', String(i + 1));
        wrap.innerHTML = pair;
        row.appendChild(wrap);
      });
    },

    _buildSlide1: function(topic, d){
      var hook = esc(d.cover && d.cover.hook ? d.cover.hook : '');
      var dots = [1,2,3,4].map(function(n){
        return '<span' + (n===1?' class="active"':'') + '></span>';
      }).join('');
      var vibrant =
        '<div class="ks-vibrant">' +
          '<div class="ks-v-eyebrow">Cicero &middot; 1 / 4</div>' +
          '<div class="ks-v-num">01</div>' +
          '<div class="ks-v-title">' + esc(topic) + '</div>' +
          '<div class="ks-v-divider"></div>' +
          '<div class="ks-v-hook">' + hook + '</div>' +
          '<div class="ks-v-swipe">swipe &rarr; to learn</div>' +
          '<div class="ks-v-dots">' + dots + '</div>' +
        '</div>';
      var editorial =
        '<div class="ks-editorial">' +
          '<div class="ks-e-header">' +
            '<div class="ks-e-eyebrow">Cicero &middot; 1 / 4</div>' +
            '<div class="ks-e-title">' + esc(topic) + '</div>' +
            '<div class="ks-e-hook">' + hook + '</div>' +
          '</div>' +
          '<div class="ks-e-body">' +
            '<div class="ks-e-tag">Study Notes</div>' +
            '<div class="ks-e-accent"></div>' +
            '<div class="ks-e-swipe">swipe &rarr; to learn</div>' +
          '</div>' +
          '<div class="ks-e-footer"><span>Cicero Study</span><span>1 / 4</span></div>' +
        '</div>';
      return vibrant + editorial;
    },

    _buildSlide2: function(d){
      var highlights = (d.highlights || []).slice(0, 4);
      var vChips = highlights.map(function(h){
        return '<div class="ks-v-chip">' + esc(h) + '</div>';
      }).join('');
      var eChips = highlights.map(function(h){
        return '<div class="ks-e-chip">' + esc(h) + '</div>';
      }).join('');
      var vibrant =
        '<div class="ks-vibrant">' +
          '<div class="ks-v-eyebrow">Cicero &middot; 2 / 4</div>' +
          '<div class="ks-v-heading">What You Need to Know</div>' +
          '<div class="ks-v-divider"></div>' +
          vChips +
        '</div>';
      var editorial =
        '<div class="ks-editorial">' +
          '<div class="ks-e-header">' +
            '<div class="ks-e-eyebrow">Cicero &middot; 2 / 4</div>' +
            '<div class="ks-e-title">Key Material</div>' +
          '</div>' +
          '<div class="ks-e-body">' +
            '<div class="ks-e-tag">What You Need to Know</div>' +
            '<div class="ks-e-accent"></div>' +
            eChips +
          '</div>' +
          '<div class="ks-e-footer"><span>Cicero Study</span><span>2 / 4</span></div>' +
        '</div>';
      return vibrant + editorial;
    },

    _buildSlide3: function(d){
      var concepts = (d.concepts || []).slice(0, 6);
      var vRows = concepts.map(function(c){
        return '<div class="ks-v-concept-row">' +
          '<div class="ks-v-term">' + esc(c.term||'') + '</div>' +
          '<div class="ks-v-def">' + esc(c.def||'') + '</div>' +
        '</div>';
      }).join('');
      var eRows = concepts.map(function(c, i){
        return '<div class="ks-e-concept-row">' +
          '<div class="ks-e-num">' + String(i+1).padStart(2,'0') + '</div>' +
          '<div><div class="ks-e-term">' + esc(c.term||'') + '</div>' +
          '<div class="ks-e-def">' + esc(c.def||'') + '</div></div>' +
        '</div>';
      }).join('');
      var vibrant =
        '<div class="ks-vibrant">' +
          '<div class="ks-v-eyebrow">Cicero &middot; 3 / 4</div>' +
          '<div class="ks-v-heading">Important Terms</div>' +
          '<div class="ks-v-divider"></div>' +
          vRows +
        '</div>';
      var editorial =
        '<div class="ks-editorial">' +
          '<div class="ks-e-header">' +
            '<div class="ks-e-eyebrow">Cicero &middot; 3 / 4</div>' +
            '<div class="ks-e-title">Key Concepts</div>' +
          '</div>' +
          '<div class="ks-e-body">' +
            '<div class="ks-e-tag">Important Terms</div>' +
            '<div class="ks-e-accent"></div>' +
            eRows +
          '</div>' +
          '<div class="ks-e-footer"><span>Cicero Study</span><span>3 / 4</span></div>' +
        '</div>';
      return vibrant + editorial;
    },

    _buildSlide4: function(d){
      var summary = esc(d.summary || '');
      var hashtags = (d.hashtags || []);
      var vTags = hashtags.map(function(h){ return '<span class="ks-v-hashtag">' + esc(h) + '</span>'; }).join('');
      var eTags = hashtags.map(function(h){ return '<span class="ks-e-hashtag">' + esc(h) + '</span>'; }).join('');
      var vibrant =
        '<div class="ks-vibrant">' +
          '<div class="ks-v-eyebrow">Cicero &middot; 4 / 4</div>' +
          '<div class="ks-v-heading">The Core Insight</div>' +
          '<div class="ks-v-divider"></div>' +
          '<div class="ks-v-summary-box">' + summary + '</div>' +
          '<div class="ks-v-hashtags">' + vTags + '</div>' +
          '<div class="ks-v-cta">Save &middot; Share &middot; Repeat</div>' +
        '</div>';
      var editorial =
        '<div class="ks-editorial">' +
          '<div class="ks-e-header">' +
            '<div class="ks-e-eyebrow">Cicero &middot; 4 / 4</div>' +
            '<div class="ks-e-title">Summary</div>' +
          '</div>' +
          '<div class="ks-e-body">' +
            '<div class="ks-e-tag">The Core Insight</div>' +
            '<div class="ks-e-accent"></div>' +
            '<div class="ks-e-summary-box">' + summary + '</div>' +
            '<div class="ks-e-hashtags">' + eTags + '</div>' +
            '<div class="ks-e-cta">Save &middot; Share &middot; Repeat</div>' +
          '</div>' +
          '<div class="ks-e-footer"><span>Cicero Study</span><span>4 / 4</span></div>' +
        '</div>';
      return vibrant + editorial;
    },

    setKontenTheme: function(theme){
      $('konten-panel').setAttribute('data-konten-theme', theme);
      $('btn-theme-v').classList.toggle('active', theme === 'vibrant');
      $('btn-theme-e').classList.toggle('active', theme === 'editorial');
    },

    downloadPNG: function(){
      var theme = $('konten-panel').getAttribute('data-konten-theme') || 'vibrant';
      var cls = theme === 'vibrant' ? 'ks-vibrant' : 'ks-editorial';
      var slides = document.querySelectorAll('#slide-row .konten-slide');
      if (!slides.length) return;
      G.toast('Downloading 4 slides…');
      var topic = $('topic-input').value.trim();
      var slug = topic.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g,'') || 'cicero';
      var idx = 0;
      function next(){
        if (idx >= slides.length) return;
        var slide = slides[idx];
        var el = slide.querySelector('.' + cls);
        if (!el) { idx++; next(); return; }
        var n = idx + 1;
        idx++;
        html2canvas(el, {scale: 2, useCORS: true, logging: false})
          .then(function(canvas){
            var a = document.createElement('a');
            a.download = 'cicero-' + slug + '-slide-' + n + '.png';
            a.href = canvas.toDataURL('image/png');
            a.click();
            next();
          })
          .catch(function(e){
            console.error('html2canvas slide ' + n + ':', e);
            next();
          });
      }
      next();
    },

    downloadPDF: function(){
      if (typeof jspdf === 'undefined' || !jspdf.jsPDF) {
        G.toast('PDF unavailable — jsPDF not loaded', 4000);
        return;
      }
      var theme = $('konten-panel').getAttribute('data-konten-theme') || 'vibrant';
      var cls = theme === 'vibrant' ? 'ks-vibrant' : 'ks-editorial';
      var slides = document.querySelectorAll('#slide-row .konten-slide');
      if (!slides.length) return;
      G.toast('Building PDF…');
      var topic = $('topic-input').value.trim();
      var slug = topic.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g,'') || 'cicero';
      var els = [];
      slides.forEach(function(slide){
        var el = slide.querySelector('.' + cls);
        if (el) els.push(el);
      });
      var pdf = new jspdf.jsPDF('p', 'px', [1080, 1080]);
      var idx = 0;
      function addPage(){
        if (idx >= els.length){
          pdf.save('cicero-' + slug + '-carousel.pdf');
          return;
        }
        var el = els[idx];
        var pageNum = idx;
        idx++;
        html2canvas(el, {scale: 2, useCORS: true, logging: false})
          .then(function(canvas){
            if (pageNum > 0) pdf.addPage([1080, 1080], 'p');
            pdf.addImage(canvas.toDataURL('image/png'), 'PNG', 0, 0, 1080, 1080);
            addPage();
          })
          .catch(function(e){
            console.error('PDF slide ' + pageNum + ':', e);
            addPage();
          });
      }
      addPage();
    },
```

- [ ] **Step 6: Extend `G.finish()` to show `#btn-konten`**

Find:
```javascript
      ['btn-copy','btn-print','btn-save'].forEach(function(id){ $(id).classList.remove('foot-state-hidden'); });
```

Replace with:
```javascript
      ['btn-copy','btn-print','btn-save','btn-konten'].forEach(function(id){ $(id).classList.remove('foot-state-hidden'); });
```

- [ ] **Step 7: Extend `G.reset()` to hide carousel and clear state**

Find:
```javascript
      ['btn-copy','btn-print','btn-save'].forEach(function(id){ $(id).classList.add('foot-state-hidden'); });
```

Replace with:
```javascript
      ['btn-copy','btn-print','btn-save','btn-konten'].forEach(function(id){ $(id).classList.add('foot-state-hidden'); });
      $('konten-panel').style.display = 'none';
      G.kontenData = null;
```

- [ ] **Step 8: Wire `#btn-konten` click event**

Find the `$('btn-save').addEventListener` call or the save button setup in the page. Look for the section where `btn-copy`, `btn-print`, and `btn-save` get their click handlers wired up after the `G` object definition. Add alongside them:

```javascript
  $('btn-konten').addEventListener('click', function(){ G.genKonten(); });
```

- [ ] **Step 9: Commit**

```powershell
git add static/study/index.html
git commit -m "feat(cicero): add KontenAgent carousel UI — dual themes, PNG + PDF download"
```

---

### Task 4: Verification

- [ ] **Step 1: Run all konten tests**

```powershell
$env:PYTHONUTF8=1; pytest tests/test_konten_agent.py -v
```

Expected: 3 passed

- [ ] **Step 2: Run study regression tests**

```powershell
$env:PYTHONUTF8=1; pytest tests/test_study_agents.py -v
```

Expected: 3 passed

- [ ] **Step 3: Verify server import**

```powershell
$env:PYTHONUTF8=1; python -c "import server; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Manual end-to-end**

```powershell
$env:PYTHONUTF8=1; python server.py
```

Checklist:
- Open `http://localhost:8000/study`
- Enter topic "Photosynthesis" → click BELAJAR
- Wait for all 3 agents → verify "✦ Create IG Content" appears in footer
- Click it → verify "Generating…" loading state → 4 slides scroll into view
- Verify 4 slides rendered in Vibrant Dark by default
- Toggle to Editorial → instant switch, no spinner
- Toggle back to Vibrant → instant again
- Click "Download PNG (4 files)" → verify `cicero-photosynthesis-slide-1.png` through `slide-4.png` download
- Click "Download PDF" → verify `cicero-photosynthesis-carousel.pdf` downloads
- Start new topic → carousel panel hides and clears

- [ ] **Step 5: Final commit (if any cleanup)**

```powershell
git add -p
git commit -m "fix(cicero): konten carousel post-verification cleanup"
```
