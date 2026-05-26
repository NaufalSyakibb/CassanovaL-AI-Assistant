# Cicero Study Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone `/study` page where the user types a topic and a 3-agent Mistral pipeline generates a Cornell Notes-style study guide (full material, key concepts, summary) that streams progressively into a paper-and-ink layout.

**Architecture:** Three sequential agents (`MateriAgent → KonsepAgent → RingkasanAgent`) run in a FastAPI SSE endpoint at `/api/study/generate`. Each agent feeds its output as text context to the next. The frontend is a single-file HTML page at `static/study/index.html` using EventSource to render each output as it arrives. A `POST /api/study/save` endpoint appends the full session to `data/notes.json` without touching existing notes.

**Tech Stack:** Python (LangChain `build_agent`, Mistral `mistral-large-latest`), FastAPI SSE (`StreamingResponse`), vanilla JS with `EventSource`, `Inter` + `Instrument Serif` + `JetBrains Mono` fonts, no build step.

---

## File Map

| File | Action |
|------|--------|
| `agents/study_agents.py` | CREATE — 3 agent functions + prompts + shared helpers |
| `tests/test_study_agents.py` | CREATE — TDD tests for all 3 functions |
| `server.py` | MODIFY — add `GET /study`, `GET /api/study/generate` (SSE), `POST /api/study/save` |
| `static/study/index.html` | CREATE — full standalone Cornell Notes page |
| `static/index/data.jsx` | MODIFY — add `url: '/study'` to Cicero agent entry |

---

## Task 1: Study agent functions (TDD)

**Files:**
- Create: `agents/study_agents.py`
- Create: `tests/test_study_agents.py`

- [ ] **Step 1: Write failing tests in `tests/test_study_agents.py`**

```python
import json
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage


def _fake_agent_result(output_dict: dict):
    return {"messages": [AIMessage(content=json.dumps(output_dict))]}


# ── run_materi_agent ───────────────────────────────────────────

def test_run_materi_agent_returns_sections():
    from agents.study_agents import run_materi_agent
    fake_out = {
        "sections": [
            {"title": "Pengertian Fotosintesis", "content": "Fotosintesis adalah proses..."},
            {"title": "Reaksi Kimia", "content": "Persamaan: 6CO2 + 6H2O..."},
        ]
    }
    with patch("agents.study_agents.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(fake_out)
        mock_build.return_value = mock_agent
        result = run_materi_agent("Fotosintesis")

    assert "sections" in result
    assert isinstance(result["sections"], list)
    assert len(result["sections"]) > 0
    assert "title" in result["sections"][0]
    assert "content" in result["sections"][0]


# ── run_konsep_agent ───────────────────────────────────────────

def test_run_konsep_agent_returns_concepts():
    from agents.study_agents import run_konsep_agent
    fake_out = {
        "concepts": [
            {"term": "Fotosintesis", "definition": "Proses mengubah CO2 dan H2O menjadi glukosa."},
            {"term": "Klorofil", "definition": "Pigmen hijau yang menyerap cahaya matahari."},
        ]
    }
    with patch("agents.study_agents.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(fake_out)
        mock_build.return_value = mock_agent
        result = run_konsep_agent("Fotosintesis", "materi tentang fotosintesis...")

    assert "concepts" in result
    assert isinstance(result["concepts"], list)
    assert len(result["concepts"]) > 0
    assert "term" in result["concepts"][0]
    assert "definition" in result["concepts"][0]


# ── run_ringkasan_agent ────────────────────────────────────────

def test_run_ringkasan_agent_returns_summary():
    from agents.study_agents import run_ringkasan_agent
    fake_out = {"summary": "Fotosintesis adalah proses biokimia fundamental yang dilakukan tumbuhan."}
    with patch("agents.study_agents.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(fake_out)
        mock_build.return_value = mock_agent
        result = run_ringkasan_agent("Fotosintesis", "materi...", "- Fotosintesis: proses...")

    assert "summary" in result
    assert isinstance(result["summary"], str)
    assert len(result["summary"]) > 10
```

- [ ] **Step 2: Run tests to confirm they fail**

```powershell
cd "c:\Users\muham\OneDrive\Dokumen\Python\ai_python"
$env:PYTHONUTF8=1; pytest tests/test_study_agents.py -v
```
Expected: `ImportError: No module named 'agents.study_agents'`

- [ ] **Step 3: Create `agents/study_agents.py`**

```python
import json
import re
import time
from agents.base import build_agent


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


_MATERI_PROMPT = """Kamu adalah MateriAgent — ahli pendidikan yang membuat materi belajar komprehensif dan mendalam.
Kamu menerima topik pelajaran dari pengguna dan menghasilkan konten edukasi yang lengkap dalam Bahasa Indonesia.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "sections": [
    {
      "title": "judul bagian (mis. Pengertian Dasar / Proses / Contoh / Aplikasi)",
      "content": "penjelasan mendalam 100-200 kata, informatif dan terstruktur"
    }
  ]
}

Buat 3-5 section yang logis dan berurutan. Setiap section harus:
- Memiliki judul yang jelas dan deskriptif
- Berisi penjelasan mendalam dengan contoh konkret
- Menggunakan bahasa formal namun mudah dipahami mahasiswa
- Membangun pemahaman secara progresif dari konsep dasar ke lanjutan
"""

_KONSEP_PROMPT = """Kamu adalah KonsepAgent — analis konsep yang membaca materi pembelajaran dan mengekstrak poin-poin esensial.
Kamu menerima topik DAN teks materi lengkap yang sudah dibuat oleh MateriAgent.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "concepts": [
    {
      "term": "nama konsep atau istilah kunci",
      "definition": "penjelasan singkat 1-2 kalimat yang tepat dan informatif"
    }
  ]
}

Buat 6-12 konsep kunci yang berasal LANGSUNG dari materi yang diberikan. Jangan mengarang konsep yang tidak ada di materi.
Prioritaskan: definisi utama, rumus/formula, hubungan antar konsep, dan istilah teknis penting.
"""

_RINGKASAN_PROMPT = """Kamu adalah RingkasanAgent — editor akademik yang menulis ringkasan komprehensif dari materi pembelajaran.
Kamu menerima topik, materi lengkap dari MateriAgent, dan konsep kunci dari KonsepAgent.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "summary": "ringkasan 3-5 kalimat yang mencakup semua poin penting dari materi"
}

Ringkasan harus:
- Mencakup semua konsep kunci secara singkat
- Menggunakan bahasa formal dan akademis
- Mengalir sebagai paragraf yang kohesif, bukan daftar
- Panjang ideal: 80-120 kata
"""


def run_materi_agent(topic: str) -> dict:
    agent = build_agent(_MATERI_PROMPT, [])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Buat materi belajar lengkap tentang: {topic}"}]
    })
    return _parse_json_output(result)


def run_konsep_agent(topic: str, materi_text: str) -> dict:
    agent = build_agent(_KONSEP_PROMPT, [])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Topik: {topic}\n\nMateri:\n{materi_text}"}]
    })
    return _parse_json_output(result)


def run_ringkasan_agent(topic: str, materi_text: str, konsep_text: str) -> dict:
    agent = build_agent(_RINGKASAN_PROMPT, [])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Topik: {topic}\n\nMateri:\n{materi_text}\n\nKonsep Kunci:\n{konsep_text}"}]
    })
    return _parse_json_output(result)
```

- [ ] **Step 4: Run tests to confirm they pass**

```powershell
$env:PYTHONUTF8=1; pytest tests/test_study_agents.py -v
```
Expected: `3 passed`

- [ ] **Step 5: Commit**

```powershell
git add agents/study_agents.py tests/test_study_agents.py
git commit -m "feat(study): add MateriAgent, KonsepAgent, RingkasanAgent with TDD"
```

---

## Task 2: Server routes

**Files:**
- Modify: `server.py`

Read `server.py` before editing to confirm exact line numbers. The changes go in two locations:
1. **API endpoints** — add after the existing stock analyze endpoint (around line 1400+)
2. **Page routes** — add near `/fitness` and `/finance` routes (around line 1900+)

- [ ] **Step 1: Add `StudySaveRequest` Pydantic model and the 3 endpoints**

Find the line in `server.py` where `class StudySaveRequest` or any similar Pydantic model is defined near the API area. If there's no good anchor, find the line `@app.get("/api/stock/analyze")` and add the new code AFTER the closing brace of that endpoint (after the `return StreamingResponse(...)` line).

Add this block after the stock analyze endpoint:

```python
# ── Study Pipeline ─────────────────────────────────────────────────────────────

@app.get("/api/study/generate")
async def study_generate(topic: str):
    if not topic or not topic.strip():
        raise HTTPException(status_code=400, detail="Topic is required")
    if len(topic) > 200:
        raise HTTPException(status_code=400, detail="Topic too long (max 200 chars)")
    topic = topic.strip()

    async def generate():
        yield _sse({"event": "log", "text": f"Memulai pipeline untuk: {topic}..."})
        try:
            from agents.study_agents import run_materi_agent, run_konsep_agent, run_ringkasan_agent
            loop = asyncio.get_running_loop()

            # Phase 1: MateriAgent
            yield _sse({"event": "step", "agent": "MateriAgent", "status": "running"})
            materi_data = await _run_agent(loop, run_materi_agent, topic)
            yield _sse({"event": "materi", "data": materi_data})
            yield _sse({"event": "step", "agent": "MateriAgent", "status": "done"})

            sections = materi_data.get("sections", [])
            materi_text = "\n\n".join(
                f"{s.get('title', '')}\n{s.get('content', '')}" for s in sections
            )

            # Phase 2: KonsepAgent
            yield _sse({"event": "step", "agent": "KonsepAgent", "status": "running"})
            konsep_data = await _run_agent(loop, run_konsep_agent, topic, materi_text)
            yield _sse({"event": "konsep", "data": konsep_data})
            yield _sse({"event": "step", "agent": "KonsepAgent", "status": "done"})

            concepts = konsep_data.get("concepts", [])
            konsep_text = "\n".join(
                f"- {c.get('term', '')}: {c.get('definition', '')}" for c in concepts
            )

            # Phase 3: RingkasanAgent
            yield _sse({"event": "step", "agent": "RingkasanAgent", "status": "running"})
            ringkasan_data = await _run_agent(loop, run_ringkasan_agent, topic, materi_text, konsep_text)
            yield _sse({"event": "ringkasan", "data": ringkasan_data})
            yield _sse({"event": "step", "agent": "RingkasanAgent", "status": "done"})

            yield _sse({"event": "done"})

        except Exception as e:
            yield _sse({"event": "error", "message": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class StudySaveRequest(BaseModel):
    topic: str
    materi: dict
    konsep: dict
    ringkasan: dict


@app.post("/api/study/save")
async def study_save(req: StudySaveRequest):
    notes_path = Path("data/notes.json")
    try:
        notes = json.loads(notes_path.read_text(encoding="utf-8")) if notes_path.exists() else []
    except Exception:
        notes = []

    sections = req.materi.get("sections", [])
    concepts = req.konsep.get("concepts", [])
    summary = req.ringkasan.get("summary", "")

    lines = [f"# {req.topic}\n\n## Materi Lengkap\n"]
    for s in sections:
        lines.append(f"### {s.get('title', '')}\n{s.get('content', '')}\n")
    lines.append("\n## Konsep Kunci\n")
    for c in concepts:
        lines.append(f"**{c.get('term', '')}:** {c.get('definition', '')}")
    lines.append(f"\n## Ringkasan\n{summary}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    note = {
        "id": uuid.uuid4().hex[:8],
        "title": req.topic,
        "content": "\n".join(lines),
        "tags": ["study", "cicero"],
        "created_at": now,
        "updated_at": now,
    }
    notes.append(note)
    notes_path.write_text(json.dumps(notes, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"id": note["id"], "title": note["title"]}
```

- [ ] **Step 2: Add `GET /study` page route**

Find the `@app.get("/fitness"` route in `server.py`. Add the `/study` route immediately BEFORE it:

```python
@app.get("/study", include_in_schema=False)
@app.get("/study/", include_in_schema=False)
async def serve_study():
    p = Path("static/study/index.html")
    if p.exists():
        return FileResponse(str(p), headers={"Cache-Control": "no-cache"})
    return JSONResponse({"error": "Study page not found"}, status_code=404)
```

Also add `Path("static/study").mkdir(exist_ok=True)` near where `Path("static/stock").mkdir(exist_ok=True)` appears (around line 1695).

- [ ] **Step 3: Verify server loads without error**

```powershell
$env:PYTHONUTF8=1; python -c "import server; print('server imports OK')"
```
Expected: `server imports OK`

- [ ] **Step 4: Commit**

```powershell
git add server.py
git commit -m "feat(study): add /study route, /api/study/generate SSE, /api/study/save endpoints"
```

---

## Task 3: Frontend — `static/study/index.html`

**Files:**
- Create: `static/study/index.html`

This is a single-file HTML page. No build step. Write the entire file at once.

- [ ] **Step 1: Create `static/study/` directory and write `index.html`**

```powershell
New-Item -ItemType Directory -Force "c:\Users\muham\OneDrive\Dokumen\Python\ai_python\static\study"
```

Write `static/study/index.html` with this complete content:

```html
<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cicero — Study Mode</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:       #EDE8DF;
    --surface:  #F3EEE5;
    --paper:    #FAF6EE;
    --white:    #FFFFFF;
    --ink:      #17171A;
    --ink2:     #3B3B3F;
    --dim:      #6B6355;
    --gold:     #A68A3E;
    --clay:     #CC785C;
    --green:    #5E8A6A;
    --red:      #A65046;
    --border:   #C8C0B2;
    --border2:  #D4CCBC;
    --shadow:   rgba(23,23,26,0.06);
  }

  body {
    background: var(--bg);
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    color: var(--ink);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  /* ── Header ── */
  .header {
    background: var(--ink);
    color: var(--paper);
    padding: 0 28px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
  }
  .header-brand { display: flex; align-items: center; gap: 10px; }
  .header-logo {
    font-family: 'Instrument Serif', serif;
    font-size: 20px;
    color: var(--paper);
    letter-spacing: 0.02em;
  }
  .header-tag {
    font-size: 10px;
    font-family: 'JetBrains Mono', monospace;
    background: var(--gold);
    color: #fff;
    padding: 2px 8px;
    border-radius: 20px;
    letter-spacing: 0.1em;
    font-weight: 500;
  }
  .header-back {
    font-size: 11px;
    color: #888;
    cursor: pointer;
    letter-spacing: 0.05em;
    text-decoration: none;
  }
  .header-back:hover { color: var(--paper); }

  /* ── Input bar ── */
  .input-bar {
    background: var(--surface);
    border-bottom: 1px solid var(--border2);
    padding: 16px 28px;
    display: flex;
    gap: 10px;
    align-items: flex-end;
    flex-shrink: 0;
  }
  .input-wrap { flex: 1; display: flex; flex-direction: column; gap: 5px; }
  .input-label {
    font-size: 10px;
    font-weight: 600;
    color: var(--gold);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    font-family: 'JetBrains Mono', monospace;
  }
  #topic-input {
    width: 100%;
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 14px;
    font-family: 'Inter', sans-serif;
    color: var(--ink);
    outline: none;
    transition: border-color 0.2s;
  }
  #topic-input::placeholder { color: #A89F93; }
  #topic-input:focus { border-color: var(--gold); }
  #btn-generate {
    background: var(--clay);
    color: #fff;
    border: none;
    border-radius: 6px;
    padding: 10px 22px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    letter-spacing: 0.05em;
    white-space: nowrap;
    transition: opacity 0.2s;
  }
  #btn-generate:hover { opacity: 0.88; }
  #btn-generate:disabled { opacity: 0.45; cursor: not-allowed; }

  /* ── Agent strip ── */
  .agent-strip {
    background: var(--surface);
    border-bottom: 1px solid var(--border2);
    padding: 8px 28px;
    display: flex;
    gap: 22px;
    align-items: center;
    flex-shrink: 0;
  }
  .agent-pill { display: flex; align-items: center; gap: 7px; font-size: 11px; }
  .dot {
    width: 7px; height: 7px;
    border-radius: 50%;
    background: var(--border);
    flex-shrink: 0;
    transition: background 0.3s;
  }
  .dot.running {
    background: var(--gold);
    animation: pulse 1s ease-in-out infinite;
  }
  .dot.done { background: var(--green); }
  @keyframes pulse { 0%,100%{opacity:1}50%{opacity:0.3} }
  .agent-pname { font-weight: 600; color: var(--ink2); font-size: 11px; }
  .agent-pstatus { color: var(--border); font-size: 10px; }
  .agent-pstatus.running { color: var(--gold); }
  .agent-pstatus.done { color: var(--green); }
  .arrow { color: var(--border); font-size: 11px; }

  /* ── Main layout ── */
  .main-wrap {
    flex: 1;
    padding: 20px 28px 28px;
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .cornell-top {
    display: grid;
    grid-template-columns: 280px 1fr;
    border: 1px solid var(--border);
    border-bottom: none;
    border-radius: 8px 8px 0 0;
    overflow: hidden;
    min-height: 360px;
  }

  /* Left: Cue column */
  .col-cue {
    background: var(--paper);
    border-right: 1px solid var(--border);
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 0;
  }
  .col-header {
    font-size: 10px;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border2);
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .agent-badge {
    font-size: 9px;
    padding: 1px 6px;
    border-radius: 10px;
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
  }
  .badge-konsep { background: rgba(94,138,106,0.12); color: var(--green); }
  .badge-materi { background: rgba(166,138,62,0.12); color: var(--gold); }
  .badge-ringkasan { background: rgba(204,120,92,0.12); color: var(--clay); }

  .cue-list { flex: 1; display: flex; flex-direction: column; gap: 0; }
  .cue-item {
    padding: 10px 0;
    border-bottom: 1px dashed var(--border2);
  }
  .cue-item:last-child { border-bottom: none; }
  .cue-term {
    font-size: 12px;
    font-weight: 600;
    color: var(--ink2);
    margin-bottom: 3px;
    font-family: 'Instrument Serif', serif;
  }
  .cue-def {
    font-size: 11px;
    color: var(--dim);
    line-height: 1.55;
  }

  /* Right: Notes column */
  .col-notes {
    background: var(--white);
    padding: 16px 20px;
    overflow-y: auto;
  }
  .notes-section { margin-bottom: 18px; }
  .notes-section:last-child { margin-bottom: 0; }
  .notes-title {
    font-family: 'Instrument Serif', serif;
    font-size: 16px;
    color: var(--ink);
    margin-bottom: 6px;
  }
  .notes-content {
    font-size: 12px;
    color: var(--ink2);
    line-height: 1.8;
    white-space: pre-wrap;
  }

  /* Bottom: Summary */
  .col-summary {
    background: var(--surface);
    border: 1px solid var(--border);
    border-top: 2px solid var(--gold);
    border-radius: 0 0 8px 8px;
    padding: 14px 20px;
    display: flex;
    gap: 16px;
    align-items: flex-start;
    min-height: 60px;
  }
  .summary-label {
    font-size: 10px;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.1em;
    color: var(--clay);
    text-transform: uppercase;
    white-space: nowrap;
    padding-top: 2px;
    min-width: 80px;
  }
  #ringkasan-text {
    font-family: 'Instrument Serif', serif;
    font-size: 14px;
    font-style: italic;
    color: var(--dim);
    line-height: 1.75;
    flex: 1;
  }
  #ringkasan-text.filled { color: var(--ink2); font-style: italic; }

  /* Save bar */
  .save-bar {
    padding: 12px 0 0 0;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 10px;
  }
  #btn-save {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--dim);
    border-radius: 6px;
    padding: 7px 18px;
    font-size: 12px;
    cursor: pointer;
    transition: background 0.2s;
    display: none;
  }
  #btn-save:hover { background: var(--border2); }

  /* Placeholder */
  .ph {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--border);
    font-size: 11px;
    letter-spacing: 0.08em;
    font-style: italic;
    min-height: 120px;
  }

  /* Toast */
  #toast {
    position: fixed;
    bottom: 28px;
    right: 28px;
    background: var(--ink);
    color: var(--paper);
    padding: 10px 18px;
    border-radius: 6px;
    font-size: 12px;
    opacity: 0;
    transition: opacity 0.3s;
    pointer-events: none;
    z-index: 999;
  }
  #toast.show { opacity: 1; }
</style>
</head>
<body>

<div class="header">
  <div class="header-brand">
    <span class="header-logo">Cicero</span>
    <span class="header-tag">STUDY</span>
  </div>
  <a class="header-back" href="/">← Kembali ke CassanovaL</a>
</div>

<div class="input-bar">
  <div class="input-wrap">
    <div class="input-label">Topik Pelajaran</div>
    <input id="topic-input" type="text" placeholder="mis. Fotosintesis, Revolusi Industri, Hukum Newton..." />
  </div>
  <button id="btn-generate">BELAJAR →</button>
</div>

<div class="agent-strip">
  <div class="agent-pill">
    <div class="dot" id="dot-MateriAgent"></div>
    <span class="agent-pname">MateriAgent</span>
    <span class="agent-pstatus" id="st-MateriAgent">IDLE</span>
  </div>
  <span class="arrow">→</span>
  <div class="agent-pill">
    <div class="dot" id="dot-KonsepAgent"></div>
    <span class="agent-pname">KonsepAgent</span>
    <span class="agent-pstatus" id="st-KonsepAgent">IDLE</span>
  </div>
  <span class="arrow">→</span>
  <div class="agent-pill">
    <div class="dot" id="dot-RingkasanAgent"></div>
    <span class="agent-pname">RingkasanAgent</span>
    <span class="agent-pstatus" id="st-RingkasanAgent">IDLE</span>
  </div>
</div>

<div class="main-wrap">
  <div class="cornell-top">
    <!-- Left: Key Concepts -->
    <div class="col-cue">
      <div class="col-header" style="color:var(--green)">
        KONSEP KUNCI
        <span class="agent-badge badge-konsep">AGENT 2</span>
      </div>
      <div class="cue-list" id="cue-list">
        <div class="ph">Menunggu KonsepAgent...</div>
      </div>
    </div>
    <!-- Right: Full Material -->
    <div class="col-notes">
      <div class="col-header" style="color:var(--gold)">
        MATERI LENGKAP
        <span class="agent-badge badge-materi">AGENT 1</span>
      </div>
      <div id="notes-body">
        <div class="ph">Masukkan topik dan klik BELAJAR untuk memulai.</div>
      </div>
    </div>
  </div>

  <!-- Bottom: Summary -->
  <div class="col-summary">
    <div class="summary-label">
      RINGKASAN<br>
      <span style="font-size:8px;color:var(--border);font-family:'JetBrains Mono',monospace">AGENT 3</span>
    </div>
    <div id="ringkasan-text">Ringkasan akan muncul setelah semua agent selesai...</div>
  </div>

  <div class="save-bar">
    <button id="btn-save">💾 Simpan ke Catatan</button>
  </div>
</div>

<div id="toast"></div>

<script>
  var G = {
    es: null,
    state: { materi: {}, konsep: {}, ringkasan: {} },

    $: function(id) { return document.getElementById(id); },

    toast: function(msg, dur) {
      var t = G.$('toast');
      t.textContent = msg;
      t.classList.add('show');
      setTimeout(function(){ t.classList.remove('show'); }, dur || 2500);
    },

    setAgent: function(name, status) {
      var dot = G.$('dot-' + name);
      var st  = G.$('st-' + name);
      if (!dot || !st) return;
      dot.className = 'dot ' + status;
      st.className  = 'agent-pstatus ' + status;
      var labels = { running: 'Berjalan...', done: '✓ Selesai', idle: 'IDLE' };
      st.textContent = labels[status] || status;
    },

    reset: function() {
      ['MateriAgent','KonsepAgent','RingkasanAgent'].forEach(function(n){ G.setAgent(n,''); });
      G.$('notes-body').innerHTML = '<div class="ph">Memproses...</div>';
      G.$('cue-list').innerHTML   = '<div class="ph">Menunggu KonsepAgent...</div>';
      G.$('ringkasan-text').textContent = 'Ringkasan akan muncul setelah semua agent selesai...';
      G.$('ringkasan-text').classList.remove('filled');
      G.$('btn-save').style.display = 'none';
      G.state = { materi: {}, konsep: {}, ringkasan: {} };
    },

    renderMateri: function(data) {
      G.state.materi = data;
      var sections = data.sections || [];
      if (!sections.length) {
        G.$('notes-body').innerHTML = '<div class="ph">Tidak ada konten.</div>';
        return;
      }
      var html = sections.map(function(s) {
        return '<div class="notes-section">'
          + '<div class="notes-title">' + esc(s.title || '') + '</div>'
          + '<div class="notes-content">' + esc(s.content || '') + '</div>'
          + '</div>';
      }).join('');
      G.$('notes-body').innerHTML = html;
    },

    renderKonsep: function(data) {
      G.state.konsep = data;
      var concepts = data.concepts || [];
      if (!concepts.length) {
        G.$('cue-list').innerHTML = '<div class="ph">Tidak ada konsep.</div>';
        return;
      }
      var html = concepts.map(function(c) {
        return '<div class="cue-item">'
          + '<div class="cue-term">' + esc(c.term || '') + '</div>'
          + '<div class="cue-def">'  + esc(c.definition || '') + '</div>'
          + '</div>';
      }).join('');
      G.$('cue-list').innerHTML = html;
    },

    renderRingkasan: function(data) {
      G.state.ringkasan = data;
      var t = G.$('ringkasan-text');
      t.textContent = data.summary || '—';
      t.classList.add('filled');
      G.$('btn-save').style.display = '';
    },

    start: function(topic) {
      if (G.es) { G.es.close(); G.es = null; }
      G.reset();
      G.$('btn-generate').disabled = true;

      var url = '/api/study/generate?topic=' + encodeURIComponent(topic);
      G.es = new EventSource(url);

      G.es.onmessage = function(e) {
        var msg;
        try { msg = JSON.parse(e.data); } catch(err) { return; }

        switch (msg.event) {
          case 'step':
            G.setAgent(msg.agent, msg.status);
            break;
          case 'materi':
            G.renderMateri(msg.data || {});
            break;
          case 'konsep':
            G.renderKonsep(msg.data || {});
            break;
          case 'ringkasan':
            G.renderRingkasan(msg.data || {});
            break;
          case 'done':
            G.es.close();
            G.es = null;
            G.$('btn-generate').disabled = false;
            break;
          case 'error':
            G.toast('Error: ' + (msg.message || 'Terjadi kesalahan'), 4000);
            G.es.close();
            G.es = null;
            G.$('btn-generate').disabled = false;
            break;
        }
      };

      G.es.onerror = function() {
        G.toast('Koneksi terputus.', 3000);
        G.$('btn-generate').disabled = false;
        if (G.es) { G.es.close(); G.es = null; }
      };
    },

    save: function() {
      var topic = G.$('topic-input').value.trim();
      if (!topic) return;
      G.$('btn-save').disabled = true;
      fetch('/api/study/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic:     topic,
          materi:    G.state.materi,
          konsep:    G.state.konsep,
          ringkasan: G.state.ringkasan,
        }),
      })
      .then(function(r){ return r.json(); })
      .then(function(d){
        G.toast('Tersimpan: ' + (d.title || topic));
        G.$('btn-save').disabled = false;
      })
      .catch(function(){
        G.toast('Gagal menyimpan. Coba lagi.', 3500);
        G.$('btn-save').disabled = false;
      });
    },
  };

  function esc(str) {
    return String(str)
      .replace(/&/g,'&amp;')
      .replace(/</g,'&lt;')
      .replace(/>/g,'&gt;')
      .replace(/"/g,'&quot;');
  }

  document.getElementById('btn-generate').addEventListener('click', function() {
    var topic = document.getElementById('topic-input').value.trim();
    if (!topic) { G.toast('Masukkan topik terlebih dahulu.'); return; }
    G.start(topic);
  });

  document.getElementById('topic-input').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') document.getElementById('btn-generate').click();
  });

  document.getElementById('btn-save').addEventListener('click', G.save);
</script>
</body>
</html>
```

- [ ] **Step 2: Start server and verify page loads**

```powershell
$env:PYTHONUTF8=1; python server.py
```
Open `http://localhost:8000/study` in browser.
Expected: Paper-and-ink page with header "Cicero · STUDY", topic input, 3 agent dots, Cornell Notes layout. No JS console errors.

- [ ] **Step 3: Commit**

```powershell
git add static/study/index.html
git commit -m "feat(study): Cornell Notes frontend — paper-and-ink design, SSE streaming"
```

---

## Task 4: Add Study Mode link for Cicero in dashboard

**Files:**
- Modify: `static/index/data.jsx` (line 13–18, the `notes` agent entry)

- [ ] **Step 1: Add `url` field to Cicero entry**

Find the `notes:` entry in `static/index/data.jsx`:

```javascript
  notes: {
    name: 'Cicero', sub: 'Study Assistant', hue: 'var(--hue-cicero)',
    issue: 'II.', cluster: 'academic',
    tagline: 'Your personal tutor — explains concepts, builds quizzes, creates flashcards, and prepares you for exams.',
    greeting: 'Apa yang ingin kita pelajari hari ini? Aku bisa jelaskan konsep, buatkan soal latihan, atau bantu persiapan ujian.',
    Ico: () => { const {IcoFeather} = window.Icons; return <IcoFeather/>; },
  },
```

Replace with:

```javascript
  notes: {
    name: 'Cicero', sub: 'Study Assistant', hue: 'var(--hue-cicero)',
    issue: 'II.', cluster: 'academic', url: '/study',
    tagline: 'Your personal tutor — explains concepts, builds quizzes, creates flashcards, and prepares you for exams.',
    greeting: 'Apa yang ingin kita pelajari hari ini? Aku bisa jelaskan konsep, buatkan soal latihan, atau bantu persiapan ujian.',
    Ico: () => { const {IcoFeather} = window.Icons; return <IcoFeather/>; },
  },
```

- [ ] **Step 2: Verify the link appears in the dashboard**

```powershell
$env:PYTHONUTF8=1; python server.py
```
Open `http://localhost:8000`, select Cicero agent in sidebar. Verify a link/button to `/study` is visible.

- [ ] **Step 3: Commit**

```powershell
git add static/index/data.jsx
git commit -m "feat(study): add Study Mode link to Cicero agent in dashboard"
```

---

## Final Verification

```powershell
# 1. All study agent tests pass
$env:PYTHONUTF8=1; pytest tests/test_study_agents.py -v
# Expected: 3 passed

# 2. All existing tests still pass (no regressions)
$env:PYTHONUTF8=1; pytest tests/test_stock_tools.py tests/test_stock_agents.py tests/test_study_agents.py -v
# Expected: 25 passed

# 3. Server imports OK
$env:PYTHONUTF8=1; python -c "import server; print('OK')"

# 4. End-to-end smoke test
$env:PYTHONUTF8=1; python server.py
# Open http://localhost:8000/study
# Type "Fotosintesis" → click BELAJAR
# Verify:
#   - MateriAgent dot turns amber → green, right column fills with sections
#   - KonsepAgent dot turns amber → green, left column fills with term/def pairs
#   - RingkasanAgent dot turns amber → green, bottom bar fills with summary
#   - "Simpan ke Catatan" button appears after all 3 done
#   - Click save → toast "Tersimpan: Fotosintesis"
#   - Check data/notes.json — new entry appended (existing entries untouched)
```
