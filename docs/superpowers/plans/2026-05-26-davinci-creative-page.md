# Da Vinci Creative Page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone `/davinci` page with a 2-agent pipeline: IdeaGenerator streams 6 ideas live, user selects 1–4, parallel IdeaExpander agents deep-dive each chosen idea and auto-save to vault.

**Architecture:** LangChain SSE pattern identical to `/study` and `/stock`. Phase 1 — `GET /api/davinci/generate?topic=...` (IdeaGenerator, pure LLM, streams `idea` events). Phase 2 — `GET /api/davinci/expand?ideas=<json>` (parallel IdeaExpanders via `asyncio.gather`, each auto-saves via `save_idea` tool). Save to Cicero notes via `POST /api/davinci/save`.

**Tech Stack:** Python / FastAPI / LangChain (LangGraph) / Mistral / `build_agent` from `agents/base.py` / `save_idea` tool from `tools/davinci_tools.py` / Vanilla JS + paper-and-ink CSS design system

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `agents/davinci_pipeline.py` | CREATE | `run_idea_generator` + `run_idea_expander` + shared helpers |
| `tests/test_davinci_pipeline.py` | CREATE | 3 TDD tests (mock `build_agent`) |
| `server.py` | MODIFY (3 locations) | 4 new endpoints + mkdir + `/davinci` route |
| `static/davinci/index.html` | CREATE | Split canvas page (ideas left, expansion right) |
| `static/index/data.jsx` | MODIFY (1 line) | Add `url: '/davinci'` to Da Vinci agent entry |

**Key existing functions to reuse:**
- `agents/base.py` → `build_agent(prompt, tools)` — builds LangGraph agent
- `tools/davinci_tools.py` → `save_idea` tool — auto-saves ideas to `AI Data/Da Vinci Agent/`
- `server.py:1235` → `_run_agent(loop, fn, *args)` — runs sync agent in executor
- `server.py:1231` → `_sse(data: dict)` — formats SSE data line
- `agents/study_agents.py:7-38` — exact pattern for `_invoke_with_retry` + `_parse_json_output`

---

## Task 1: Da Vinci Pipeline Agents

**Files:**
- Create: `agents/davinci_pipeline.py`
- Create: `tests/test_davinci_pipeline.py`

- [ ] **Step 1: Write 3 failing tests in `tests/test_davinci_pipeline.py`**

```python
import json
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage


def _fake_agent_result(output_dict: dict):
    return {"messages": [AIMessage(content=json.dumps(output_dict))]}


def test_run_idea_generator_returns_ideas():
    from agents.davinci_pipeline import run_idea_generator
    fake_out = {
        "ideas": [
            {"id": 1, "title": "Gamifikasi Belajar", "tagline": "Jadikan setiap ujian seperti level game.", "spectrum": "Konvensional"},
            {"id": 2, "title": "AI Tutor Emosional", "tagline": "AI yang merespon suasana hati pelajar.", "spectrum": "Inovatif"},
            {"id": 3, "title": "Mimpi Sebagai Kurikulum", "tagline": "Gunakan analisis mimpi untuk menentukan minat.", "spectrum": "Liar"},
        ]
    }
    with patch("agents.davinci_pipeline.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(fake_out)
        mock_build.return_value = mock_agent
        result = run_idea_generator("cara baru belajar matematika")

    assert "ideas" in result
    assert isinstance(result["ideas"], list)
    assert len(result["ideas"]) > 0
    first = result["ideas"][0]
    assert "id" in first
    assert "title" in first
    assert "tagline" in first
    assert "spectrum" in first


def test_run_idea_expander_returns_expansion_keys():
    from agents.davinci_pipeline import run_idea_expander
    fake_out = {
        "title": "Gamifikasi Belajar",
        "use_cases": "Platform edukasi online; Kelas tatap muka; Pelatihan karyawan",
        "steps": "Rancang sistem poin; Tambahkan leaderboard; Buat badge pencapaian; Uji dengan pengguna",
        "example": "Duolingo — aplikasi bahasa yang menggunakan streak dan XP untuk memotivasi pengguna.",
        "impact": "Meningkatkan engagement belajar hingga 3x dan menurunkan dropout rate."
    }
    with patch("agents.davinci_pipeline.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(fake_out)
        mock_build.return_value = mock_agent
        result = run_idea_expander("Gamifikasi Belajar", "Jadikan setiap ujian seperti level game.")

    assert "use_cases" in result
    assert "steps" in result
    assert "example" in result
    assert "impact" in result


def test_run_idea_expander_handles_unparseable_response():
    from agents.davinci_pipeline import run_idea_expander
    with patch("agents.davinci_pipeline.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "messages": [MagicMock(content="Maaf, saya tidak bisa memproses permintaan ini.")]
        }
        mock_build.return_value = mock_agent
        result = run_idea_expander("Judul Test", "Tagline test.")

    assert "error" in result
```

- [ ] **Step 2: Run tests — verify all 3 fail**

```powershell
$env:PYTHONUTF8=1; pytest tests/test_davinci_pipeline.py -v
```

Expected: `ImportError: cannot import name 'run_idea_generator' from 'agents.davinci_pipeline'` (or ModuleNotFoundError if file doesn't exist yet)

- [ ] **Step 3: Create `agents/davinci_pipeline.py`**

```python
import json
import re
import time
from agents.base import build_agent
from tools.davinci_tools import save_idea


def _invoke_with_retry(agent, messages: dict, max_retries: int = 5) -> dict:
    """Invoke a LangGraph agent with exponential backoff on 429 rate-limit errors."""
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
    """Extract last AI message content and parse the first JSON object found."""
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


_GENERATOR_PROMPT = """Kamu adalah IdeaGenerator — seorang kreatif polymath seperti Leonardo da Vinci yang merentang dari yang konvensional hingga yang radikal.
Kamu menerima topik atau pertanyaan kreatif dari pengguna dan menghasilkan 6 ide yang beragam.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "ideas": [
    {
      "id": 1,
      "title": "judul singkat ide (max 5 kata)",
      "tagline": "deskripsi satu kalimat yang tajam dan menggugah",
      "spectrum": "Konvensional"
    }
  ]
}

Buat tepat 6 ide dengan distribusi spectrum:
- Ide 1-2: "Konvensional" — pendekatan yang terbukti, mudah diimplementasi
- Ide 3-4: "Inovatif" — pendekatan segar yang realistis namun belum umum
- Ide 5-6: "Liar" — pendekatan radikal, tidak biasa, bisa mengubah paradigma

Setiap ide harus:
- Memiliki judul yang singkat dan memukau (bukan generik)
- Tagline yang spesifik dan memancing rasa ingin tahu
- Berbeda satu sama lain — tidak ada tumpang tindih konsep
"""

_EXPANDER_PROMPT = """Kamu adalah IdeaExpander — ahli strategi kreatif yang mengembangkan ide menjadi rencana yang konkret dan actionable.
Kamu menerima judul dan tagline sebuah ide kreatif dan mengembangkannya secara mendalam.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "title": "judul ide (sama dengan input)",
  "use_cases": "3-4 kasus penggunaan spesifik, dipisahkan titik koma",
  "steps": "4-5 langkah implementasi konkret, dipisahkan titik koma",
  "example": "satu contoh nyata atau analogi yang memperjelas ide",
  "impact": "dampak potensial jika ide ini berhasil diimplementasi"
}

Semua konten dalam Bahasa Indonesia. Konkret, spesifik, actionable — bukan abstrak.
"""


def run_idea_generator(topic: str) -> dict:
    agent = build_agent(_GENERATOR_PROMPT, [])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Hasilkan 6 ide kreatif untuk topik: {topic}"}]
    })
    parsed = _parse_json_output(result)
    if "ideas" not in parsed:
        return {"ideas": []}
    return parsed


def run_idea_expander(idea_title: str, idea_tagline: str) -> dict:
    agent = build_agent(_EXPANDER_PROMPT, [save_idea])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Kembangkan ide ini:\nJudul: {idea_title}\nTagline: {idea_tagline}"}]
    })
    return _parse_json_output(result)
```

- [ ] **Step 4: Run tests — verify all 3 pass**

```powershell
$env:PYTHONUTF8=1; pytest tests/test_davinci_pipeline.py -v
```

Expected:
```
test_run_idea_generator_returns_ideas PASSED
test_run_idea_expander_returns_expansion_keys PASSED
test_run_idea_expander_handles_unparseable_response PASSED
3 passed
```

- [ ] **Step 5: Run regression tests**

```powershell
$env:PYTHONUTF8=1; pytest tests/test_stock_screener.py tests/test_study_agents.py -v
```

Expected: all existing tests still pass (6 total)

- [ ] **Step 6: Commit**

```powershell
git add agents/davinci_pipeline.py tests/test_davinci_pipeline.py
git commit -m "feat(davinci): add IdeaGenerator + IdeaExpander pipeline agents (TDD)"
```

---

## Task 2: Server Endpoints

**Files:**
- Modify: `server.py` (3 locations — lines 1535, 1843, and after line 1871)

- [ ] **Step 1: Insert Da Vinci endpoints block after line 1535 (between stock picks and Najwa)**

Find the exact anchor text `# ─── Najwa News Feed` (line 1537) and insert **before** it:

```python
# ── Da Vinci Creative Page ─────────────────────────────────────────────────────

@app.get("/api/davinci/generate")
async def davinci_generate(topic: str = ""):
    topic = topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic required")
    if len(topic) > 200:
        raise HTTPException(status_code=400, detail="Topic too long (max 200 chars)")

    async def generate():
        try:
            from agents.davinci_pipeline import run_idea_generator
            loop = asyncio.get_running_loop()
            result = await _run_agent(loop, run_idea_generator, topic)
            ideas = result.get("ideas", [])
            for idea in ideas:
                yield _sse({"event": "idea", **idea})
            yield _sse({"event": "ideas_done", "count": len(ideas)})
        except Exception as e:
            yield _sse({"event": "error", "message": str(e)})

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/davinci/expand")
async def davinci_expand(ideas: str = ""):
    try:
        ideas_list = json.loads(ideas)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ideas param — must be JSON array")
    if not ideas_list:
        raise HTTPException(status_code=400, detail="No ideas provided")

    async def generate():
        try:
            from agents.davinci_pipeline import run_idea_expander
            loop = asyncio.get_running_loop()
            tasks = [_run_agent(loop, run_idea_expander, idea["title"], idea.get("tagline", ""))
                     for idea in ideas_list]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            count = 0
            for idea, result in zip(ideas_list, results):
                if isinstance(result, Exception):
                    yield _sse({"event": "expansion", "title": idea["title"],
                                "error": str(result)[:120]})
                else:
                    yield _sse({"event": "expansion", **result})
                count += 1
            yield _sse({"event": "expand_done", "count": count})
        except Exception as e:
            yield _sse({"event": "error", "message": str(e)})

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class DaVinciSaveRequest(BaseModel):
    topic: str
    expansions: list[dict]


@app.post("/api/davinci/save")
async def davinci_save(req: DaVinciSaveRequest):
    notes_path = Path("data/notes.json")
    try:
        notes = json.loads(notes_path.read_text(encoding="utf-8"))
    except Exception:
        notes = []
    for exp in req.expansions:
        content = f"## {exp.get('title', '')}\n\n"
        content += f"**Use Cases:** {exp.get('use_cases', '')}\n\n"
        content += f"**Steps:** {exp.get('steps', '')}\n\n"
        content += f"**Example:** {exp.get('example', '')}\n\n"
        content += f"**Impact:** {exp.get('impact', '')}"
        notes.append({
            "id": str(uuid.uuid4()),
            "title": exp.get("title", req.topic),
            "content": content,
            "tags": ["da-vinci", "brainstorming", req.topic[:30]],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        })
    notes_path.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"saved": len(req.expansions)}


```

- [ ] **Step 2: Add `static/davinci` mkdir at line 1843**

Find:
```python
Path("static/study").mkdir(exist_ok=True)
```

Replace with:
```python
Path("static/study").mkdir(exist_ok=True)
Path("static/davinci").mkdir(exist_ok=True)
```

- [ ] **Step 3: Add `/davinci` route after the `/study` route (after line 1871)**

Find:
```python
@app.get("/fitness", include_in_schema=False)
@app.get("/fitness/", include_in_schema=False)
async def serve_fitness():
```

Insert **before** it:
```python
@app.get("/davinci", include_in_schema=False)
@app.get("/davinci/", include_in_schema=False)
async def serve_davinci():
    p = Path("static/davinci/index.html")
    if p.exists():
        return FileResponse(str(p), headers={"Cache-Control": "no-cache"})
    return JSONResponse({"error": "Da Vinci page not found"}, status_code=404)


```

- [ ] **Step 4: Verify server imports cleanly**

```powershell
$env:PYTHONUTF8=1; python -c "import server; print('OK')"
```

Expected: `OK` with no errors

- [ ] **Step 5: Commit**

```powershell
git add server.py
git commit -m "feat(davinci): add /api/davinci/generate, /api/davinci/expand, /api/davinci/save endpoints"
```

---

## Task 3: Frontend Split Canvas Page

**Files:**
- Create: `static/davinci/index.html`

- [ ] **Step 1: Create `static/davinci/index.html`**

```html
<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Da Vinci — Ideas Lab</title>
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
    background: var(--gold);
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

  /* ── Canvas ── */
  .canvas {
    flex: 1;
    display: grid;
    grid-template-columns: 320px 1fr;
    min-height: 0;
    overflow: hidden;
  }

  /* ── Left: Ideas panel ── */
  .ideas-panel {
    background: var(--paper);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .panel-header {
    padding: 12px 16px;
    border-bottom: 1px solid var(--border2);
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
  }
  .panel-label {
    font-size: 10px;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--dim);
  }
  .selection-count {
    font-size: 10px;
    color: var(--dim);
    font-family: 'JetBrains Mono', monospace;
  }
  #ideas-list {
    flex: 1;
    overflow-y: auto;
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .idea-card {
    background: var(--white);
    border: 1px solid var(--border2);
    border-radius: 6px;
    padding: 10px 12px;
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
    position: relative;
  }
  .idea-card:hover { border-color: var(--gold); }
  .idea-card.selected {
    border-color: var(--gold);
    background: rgba(166,138,62,0.05);
  }
  .idea-card.selected::before {
    content: '✓';
    position: absolute;
    top: 8px;
    right: 10px;
    color: var(--gold);
    font-size: 12px;
    font-weight: 700;
  }
  .idea-title {
    font-family: 'Instrument Serif', serif;
    font-size: 14px;
    color: var(--ink);
    margin-bottom: 3px;
    padding-right: 18px;
  }
  .idea-tagline {
    font-size: 11px;
    color: var(--dim);
    line-height: 1.5;
    margin-bottom: 6px;
  }
  .spectrum-badge {
    display: inline-block;
    font-size: 9px;
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
    padding: 2px 7px;
    border-radius: 10px;
    letter-spacing: 0.06em;
  }
  .spectrum-Konvensional { background: rgba(94,138,106,0.12); color: var(--green); }
  .spectrum-Inovatif { background: rgba(166,138,62,0.12); color: var(--gold); }
  .spectrum-Liar { background: rgba(204,120,92,0.18); color: var(--clay); }

  .idea-skeleton {
    background: var(--surface);
    border: 1px dashed var(--border2);
    border-radius: 6px;
    padding: 10px 12px;
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--dim);
    font-size: 11px;
    font-style: italic;
  }
  .dot-pulse {
    width: 7px; height: 7px;
    border-radius: 50%;
    background: var(--gold);
    animation: pulse 1s ease-in-out infinite;
    flex-shrink: 0;
  }
  @keyframes pulse { 0%,100%{opacity:1}50%{opacity:0.3} }

  .expand-bar {
    padding: 10px;
    border-top: 1px solid var(--border2);
    flex-shrink: 0;
  }
  #btn-expand {
    width: 100%;
    background: var(--clay);
    color: #fff;
    border: none;
    border-radius: 6px;
    padding: 10px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    letter-spacing: 0.05em;
    transition: opacity 0.2s;
  }
  #btn-expand:hover { opacity: 0.88; }
  #btn-expand:disabled { opacity: 0.35; cursor: not-allowed; }

  /* ── Right: Expansion panel ── */
  .expansion-panel {
    background: var(--white);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .exp-header {
    padding: 12px 20px;
    border-bottom: 1px solid var(--border2);
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
  }
  #exp-list {
    flex: 1;
    overflow-y: auto;
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .exp-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-top: 2px solid var(--gold);
    border-radius: 6px;
    padding: 14px 16px;
  }
  .exp-title {
    font-family: 'Instrument Serif', serif;
    font-size: 17px;
    color: var(--ink);
    margin-bottom: 10px;
  }
  .exp-row { display: flex; gap: 8px; margin-bottom: 8px; align-items: flex-start; }
  .exp-icon { font-size: 14px; flex-shrink: 0; margin-top: 1px; }
  .exp-label {
    font-size: 10px;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.08em;
    color: var(--dim);
    text-transform: uppercase;
    min-width: 70px;
    margin-top: 2px;
  }
  .exp-value {
    font-size: 12px;
    color: var(--ink2);
    line-height: 1.65;
  }
  .exp-streaming {
    background: var(--surface);
    border: 1px dashed var(--border2);
    border-radius: 6px;
    padding: 14px 16px;
    display: flex;
    align-items: center;
    gap: 10px;
    color: var(--dim);
    font-size: 12px;
    font-style: italic;
  }

  .btn-action {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--dim);
    border-radius: 6px;
    padding: 7px 14px;
    font-size: 11px;
    cursor: pointer;
    transition: background 0.2s;
    font-family: 'Inter', sans-serif;
  }
  .btn-action:hover { background: var(--bg); }
  .btn-action.saved { border-color: var(--green); color: var(--green); background: rgba(94,138,106,0.06); }

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
    text-align: center;
    padding: 20px;
    flex-direction: column;
    gap: 8px;
  }
  .ph-icon { font-size: 28px; opacity: 0.5; }

  /* Toast */
  #toast {
    position: fixed;
    bottom: 28px;
    right: 28px;
    background: var(--ink);
    color: var(--paper);
    padding: 10px 16px;
    border-radius: 6px;
    font-size: 12px;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.3s;
    z-index: 1000;
  }
  #toast.show { opacity: 1; }
</style>
</head>
<body>

<header class="header">
  <div class="header-brand">
    <span class="header-logo">✦ Da Vinci</span>
    <span class="header-tag">IDEAS LAB</span>
  </div>
  <a href="/" class="header-back">← kembali</a>
</header>

<div class="input-bar">
  <div class="input-wrap">
    <div class="input-label">Topik atau pertanyaan kreatif</div>
    <input type="text" id="topic-input" placeholder="Contoh: cara baru belajar matematika, aplikasi untuk petani, solusi macet Jakarta...">
  </div>
  <button id="btn-generate">GENERATE</button>
</div>

<div class="canvas">

  <!-- Left: Ideas -->
  <div class="ideas-panel">
    <div class="panel-header">
      <span class="panel-label">Ide — klik untuk pilih</span>
      <span class="selection-count" id="sel-count">0 / 4 dipilih</span>
    </div>
    <div id="ideas-list">
      <div class="ph">
        <div class="ph-icon">✦</div>
        <div>Masukkan topik dan klik GENERATE<br>untuk menghasilkan 6 ide kreatif</div>
      </div>
    </div>
    <div class="expand-bar">
      <button id="btn-expand" disabled>EKSPANSI IDE →</button>
    </div>
  </div>

  <!-- Right: Expansion -->
  <div class="expansion-panel">
    <div class="exp-header">
      <span class="panel-label">Ekspansi</span>
      <button class="btn-action" id="btn-save-notes" style="display:none;" onclick="G.saveToNotes()">📝 Tambah ke Notes</button>
    </div>
    <div id="exp-list">
      <div class="ph">
        <div class="ph-icon">◎</div>
        <div>Pilih 1–4 ide di kiri<br>lalu klik EKSPANSI IDE</div>
      </div>
    </div>
  </div>

</div>

<div id="toast"></div>

<script>
var G = {};

G.es = null;
G.expandEs = null;
G.ideas = [];
G.selected = {};
G.expansions = [];

G.$ = function(id){ return document.getElementById(id); };

G._esc = function(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
};

G.toast = function(msg) {
  var el = G.$('toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(function(){ el.classList.remove('show'); }, 2500);
};

G.updateSelCount = function() {
  var n = Object.keys(G.selected).length;
  G.$('sel-count').textContent = n + ' / 4 dipilih';
  G.$('btn-expand').disabled = n === 0;
};

G.renderIdea = function(data) {
  var list = G.$('ideas-list');
  var ph = list.querySelector('.ph');
  if (ph) ph.remove();
  var sk = list.querySelector('.idea-skeleton');
  if (sk) sk.remove();

  G.ideas.push(data);
  var div = document.createElement('div');
  div.className = 'idea-card';
  div.dataset.id = data.id;
  div.innerHTML =
    '<div class="idea-title">' + G._esc(data.title) + '</div>' +
    '<div class="idea-tagline">' + G._esc(data.tagline) + '</div>' +
    '<span class="spectrum-badge spectrum-' + G._esc(data.spectrum) + '">' + G._esc(data.spectrum) + '</span>';
  div.addEventListener('click', function(){ G.selectIdea(div, data); });
  list.appendChild(div);
};

G.selectIdea = function(card, data) {
  var id = data.id;
  if (G.selected[id]) {
    delete G.selected[id];
    card.classList.remove('selected');
  } else {
    if (Object.keys(G.selected).length >= 4) {
      G.toast('Maksimal 4 ide yang bisa dipilih.');
      return;
    }
    G.selected[id] = true;
    card.classList.add('selected');
  }
  G.updateSelCount();
};

G.addSkeleton = function() {
  var list = G.$('ideas-list');
  var sk = document.createElement('div');
  sk.className = 'idea-skeleton';
  sk.innerHTML = '<div class="dot-pulse"></div><span>Menghasilkan ide...</span>';
  list.appendChild(sk);
};

G.generate = function(topic) {
  if (G.es) { G.es.close(); G.es = null; }
  G.ideas = [];
  G.selected = {};
  G.expansions = [];
  G.$('ideas-list').innerHTML = '';
  G.$('exp-list').innerHTML = '<div class="ph"><div class="ph-icon">◎</div><div>Pilih 1–4 ide di kiri<br>lalu klik EKSPANSI IDE</div></div>';
  G.$('btn-expand').disabled = true;
  G.$('btn-save-notes').style.display = 'none';
  G.$('btn-generate').disabled = true;
  G.$('btn-generate').textContent = 'GENERATING...';
  G.updateSelCount();
  G.addSkeleton();

  var url = '/api/davinci/generate?topic=' + encodeURIComponent(topic);
  G.es = new EventSource(url);

  G.es.onmessage = function(e) {
    try {
      var msg = JSON.parse(e.data);
      if (msg.event === 'idea') {
        G.renderIdea(msg);
        G.addSkeleton();
      } else if (msg.event === 'ideas_done') {
        G.es.close(); G.es = null;
        G.$('btn-generate').disabled = false;
        G.$('btn-generate').textContent = 'GENERATE';
        var sk = G.$('ideas-list').querySelector('.idea-skeleton');
        if (sk) sk.remove();
      } else if (msg.event === 'error') {
        G.es.close(); G.es = null;
        G.$('btn-generate').disabled = false;
        G.$('btn-generate').textContent = 'GENERATE';
        G.toast('Error: ' + msg.message);
        var sk = G.$('ideas-list').querySelector('.idea-skeleton');
        if (sk) sk.remove();
      }
    } catch(err) {}
  };

  G.es.onerror = function() {
    G.es.close(); G.es = null;
    G.$('btn-generate').disabled = false;
    G.$('btn-generate').textContent = 'GENERATE';
    G.toast('Koneksi terputus. Coba lagi.');
    var sk = G.$('ideas-list').querySelector('.idea-skeleton');
    if (sk) sk.remove();
  };
};

G.renderExpansion = function(data) {
  var list = G.$('exp-list');
  var ph = list.querySelector('.ph');
  if (ph) ph.remove();
  list.querySelectorAll('.exp-streaming').forEach(function(sk){
    if (sk.dataset.title === data.title) sk.remove();
  });

  G.expansions.push(data);
  var div = document.createElement('div');
  div.className = 'exp-card';

  if (data.error) {
    div.innerHTML =
      '<div class="exp-title">' + G._esc(data.title) + '</div>' +
      '<div style="color:var(--red);font-size:12px">Gagal mengembangkan ide ini: ' + G._esc(data.error) + '</div>';
    list.appendChild(div);
    return;
  }

  div.innerHTML =
    '<div class="exp-title">' + G._esc(data.title) + '</div>' +
    '<div class="exp-row"><span class="exp-icon">🎯</span><span class="exp-label">Use Cases</span><span class="exp-value">' + G._esc(data.use_cases||'') + '</span></div>' +
    '<div class="exp-row"><span class="exp-icon">⚡</span><span class="exp-label">Langkah</span><span class="exp-value">' + G._esc(data.steps||'') + '</span></div>' +
    '<div class="exp-row"><span class="exp-icon">💡</span><span class="exp-label">Contoh</span><span class="exp-value">' + G._esc(data.example||'') + '</span></div>' +
    '<div class="exp-row"><span class="exp-icon">🔥</span><span class="exp-label">Dampak</span><span class="exp-value">' + G._esc(data.impact||'') + '</span></div>';
  list.appendChild(div);
};

G.expand = function() {
  if (G.expandEs) { G.expandEs.close(); G.expandEs = null; }
  var selectedIdeas = G.ideas.filter(function(i){ return G.selected[i.id]; });
  if (!selectedIdeas.length) return;

  var list = G.$('exp-list');
  list.innerHTML = '';
  G.expansions = [];
  G.$('btn-save-notes').style.display = 'none';
  G.$('btn-expand').disabled = true;
  G.$('btn-expand').textContent = 'EXPANDING...';

  selectedIdeas.forEach(function(idea) {
    var sk = document.createElement('div');
    sk.className = 'exp-streaming';
    sk.dataset.title = idea.title;
    sk.innerHTML = '<div class="dot-pulse"></div><span>Mengembangkan: ' + G._esc(idea.title) + '...</span>';
    list.appendChild(sk);
  });

  var param = encodeURIComponent(JSON.stringify(selectedIdeas.map(function(i){
    return {title: i.title, tagline: i.tagline};
  })));
  var url = '/api/davinci/expand?ideas=' + param;
  G.expandEs = new EventSource(url);

  G.expandEs.onmessage = function(e) {
    try {
      var msg = JSON.parse(e.data);
      if (msg.event === 'expansion') {
        G.renderExpansion(msg);
      } else if (msg.event === 'expand_done') {
        G.expandEs.close(); G.expandEs = null;
        G.$('btn-expand').disabled = false;
        G.$('btn-expand').textContent = 'EKSPANSI IDE →';
        G.$('exp-list').querySelectorAll('.exp-streaming').forEach(function(sk){ sk.remove(); });
        if (G.expansions.length > 0) G.$('btn-save-notes').style.display = '';
      } else if (msg.event === 'error') {
        G.expandEs.close(); G.expandEs = null;
        G.$('btn-expand').disabled = false;
        G.$('btn-expand').textContent = 'EKSPANSI IDE →';
        G.toast('Error: ' + msg.message);
      }
    } catch(err) {}
  };

  G.expandEs.onerror = function() {
    G.expandEs.close(); G.expandEs = null;
    G.$('btn-expand').disabled = false;
    G.$('btn-expand').textContent = 'EKSPANSI IDE →';
    G.toast('Koneksi terputus. Coba lagi.');
  };
};

G.saveToNotes = function() {
  var topic = G.$('topic-input').value.trim();
  var validExpansions = G.expansions.filter(function(e){ return !e.error; });
  if (!validExpansions.length) return;

  fetch('/api/davinci/save', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({topic: topic, expansions: validExpansions})
  })
  .then(function(r){ return r.json(); })
  .then(function(data){
    G.toast('Disimpan ke Notes (' + data.saved + ' ide)');
    var btn = G.$('btn-save-notes');
    btn.textContent = '✓ Tersimpan';
    btn.classList.add('saved');
  })
  .catch(function(){
    G.toast('Gagal menyimpan ke Notes.');
  });
};

document.addEventListener('DOMContentLoaded', function() {
  G.$('btn-generate').addEventListener('click', function() {
    var topic = G.$('topic-input').value.trim();
    if (!topic) { G.toast('Masukkan topik terlebih dahulu.'); return; }
    G.generate(topic);
  });

  G.$('topic-input').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') G.$('btn-generate').click();
  });

  G.$('btn-expand').addEventListener('click', function() {
    G.expand();
  });
});
</script>
</body>
</html>
```

- [ ] **Step 2: Start server and open page in browser**

```powershell
$env:PYTHONUTF8=1; python server.py
```

Open `http://localhost:8000/davinci` and verify:
- Page loads with paper-and-ink design (beige background, dark header)
- Input bar with topic field and GENERATE button
- Left panel: "Ide — klik untuk pilih" with placeholder
- Right panel: "Ekspansi" with placeholder
- EKSPANSI IDE button is disabled

- [ ] **Step 3: Test idea generation**

Type "cara baru belajar matematika" → click GENERATE. Verify:
- Button shows "GENERATING..."
- Animated skeleton (pulsing dot) visible in left panel
- Idea cards stream in one by one (each with title, tagline, spectrum badge)
- Spectrum badge colors: green for Konvensional, gold for Inovatif, clay for Liar
- EKSPANSI IDE button enables after clicking any card

- [ ] **Step 4: Test expansion**

Select 2 idea cards → click EKSPANSI IDE. Verify:
- Right panel shows streaming skeletons ("Mengembangkan: [title]...")
- Expansion cards appear as they complete (gold top border)
- Each card shows: Use Cases, Langkah, Contoh, Dampak sections
- "Tambah ke Notes" button appears after expand_done
- `AI Data/Da Vinci Agent/` directory now has new `.md` files (auto-saved by expander)

- [ ] **Step 5: Test save to notes**

Click "Tambah ke Notes" → button shows "✓ Tersimpan". Verify:
- `data/notes.json` has new entries with tags `["da-vinci", "brainstorming", ...]`
- Existing notes in `data/notes.json` are intact (not deleted)

- [ ] **Step 6: Commit**

```powershell
git add static/davinci/index.html
git commit -m "feat(davinci): add split canvas frontend — ideas left, expansion right"
```

---

## Task 4: Nav Link

**Files:**
- Modify: `static/index/data.jsx` (line 65)

- [ ] **Step 1: Add `url: '/davinci'` to the Da Vinci agent entry**

Find in `static/index/data.jsx` (around line 63–68):
```javascript
  davinci: {
    name: 'Da Vinci', sub: 'Ideas Lab', hue: 'var(--hue-davinci)',
    issue: 'IX.', cluster: 'personal',
```

Replace with:
```javascript
  davinci: {
    name: 'Da Vinci', sub: 'Ideas Lab', hue: 'var(--hue-davinci)',
    issue: 'IX.', cluster: 'personal', url: '/davinci',
```

- [ ] **Step 2: Verify the nav link works**

Open `http://localhost:8000` → find Da Vinci agent card → verify it has a link/button to `/davinci` (same pattern as Cicero → `/study`)

- [ ] **Step 3: Commit**

```powershell
git add static/index/data.jsx
git commit -m "feat(davinci): add /davinci url to agent nav entry"
```

---

## Verification Checklist

```powershell
# 1. All unit tests pass
$env:PYTHONUTF8=1; pytest tests/test_davinci_pipeline.py tests/test_stock_screener.py tests/test_study_agents.py -v
# Expected: 9 passed

# 2. Server imports cleanly
$env:PYTHONUTF8=1; python -c "import server; print('OK')"
# Expected: OK

# 3. Data safety — notes.json only changes when save button clicked
# Verify data/notes.json unchanged after generate + expand without clicking "Tambah ke Notes"

# 4. Max 4 selection limit
# Try clicking a 5th idea card — verify toast "Maksimal 4 ide yang bisa dipilih."

# 5. Empty topic guard
# Click GENERATE with empty input — verify toast "Masukkan topik terlebih dahulu."

# 6. Retry with new topic clears previous results
# Generate topic A, then generate topic B — verify left panel shows only topic B's ideas
```
