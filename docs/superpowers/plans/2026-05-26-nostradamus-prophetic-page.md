# Nostradamus Prophetic Intelligence Page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone `/nostradamus` page with a 3-phase SSE pipeline — news gathering, 5 parallel prediction agents, and a council verdict — all streaming live to the browser.

**Architecture:** Phase 1 runs a NewsGatherer agent (uses `get_recent_news` tool), Phase 2 runs 5 Predictor agents in parallel via `asyncio.as_completed` so cards appear as each finishes, Phase 3 runs a Council agent that selects the most accurate prediction and auto-saves to vault. All follow the exact LangChain SSE pattern used in `/davinci`.

**Tech Stack:** Python/FastAPI SSE, LangChain (`build_agent` + `_invoke_with_retry`), `asyncio.as_completed`, vanilla JS with G-namespace pattern, paper-and-ink CSS tokens matching `static/index/styles.css`.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `tools/nostradamus_tools.py` | CREATE | `save_prophecy` LangChain tool — writes verdict to `AI Data/Nostradamus Agent/` |
| `agents/nostradamus_pipeline.py` | CREATE | `PREDICTORS` config, `run_news_gatherer`, `run_predictor`, `run_council` |
| `tests/test_nostradamus_pipeline.py` | CREATE | 5 TDD tests (mock `build_agent`, use `AIMessage`) |
| `server.py` | MODIFY (3 places) | API endpoints, mkdir, page route |
| `static/nostradamus/index.html` | CREATE | Full 3-phase streaming page (main-site design tokens + dark mode) |
| `static/index/data.jsx` | MODIFY | Add `nostradamus` agent entry + `AGENT_ORDER` |
| `static/index/styles.css` | MODIFY | Add `--hue-nostradamus` to both light and dark token blocks |

---

## Task 1: Pipeline Agents (TDD)

**Files:**
- Create: `tools/nostradamus_tools.py`
- Create: `agents/nostradamus_pipeline.py`
- Create: `tests/test_nostradamus_pipeline.py`

### Step 1 — Write the 5 failing tests

Create `tests/test_nostradamus_pipeline.py`:

```python
import json
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage


def _fake_result(output_dict: dict):
    return {"messages": [AIMessage(content=json.dumps(output_dict))]}


def test_run_news_gatherer_returns_news():
    from agents.nostradamus_pipeline import run_news_gatherer
    fake = {"news": [{"headline": "Test headline", "source": "BBC", "date": "2026-05-26", "summary": "A test."}]}
    with patch("agents.nostradamus_pipeline.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_result(fake)
        mock_build.return_value = mock_agent
        result = run_news_gatherer("US-China trade war")
    assert "news" in result
    assert isinstance(result["news"], list)
    assert result["news"][0]["headline"] == "Test headline"


def test_run_predictor_returns_prediction_keys():
    from agents.nostradamus_pipeline import run_predictor, PREDICTORS
    fake = {
        "agent_id": "trend", "agent_name": "Trend Analyst",
        "prediction_title": "Escalation likely",
        "prediction": "Tariffs will increase.", "confidence": 72,
        "reasoning": "Current momentum points to further escalation."
    }
    with patch("agents.nostradamus_pipeline.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_result(fake)
        mock_build.return_value = mock_agent
        result = run_predictor(PREDICTORS[0], "US-China trade war", "News summary here.")
    for key in ("agent_id", "agent_name", "prediction_title", "prediction", "confidence", "reasoning"):
        assert key in result


def test_run_council_returns_verdict_keys():
    from agents.nostradamus_pipeline import run_council
    fake = {
        "verdict_title": "Trade war intensifies",
        "verdict_detail": "Based on all evidence, escalation is most probable.",
        "confidence": 75, "endorsed_agent": "Trend Analyst",
        "dissenting_view": "Risk Assessor sees a chance of sudden de-escalation."
    }
    predictions = [{"agent_name": "Trend Analyst", "prediction_title": "Escalation", "prediction": "...", "confidence": 72}]
    with patch("agents.nostradamus_pipeline.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_result(fake)
        mock_build.return_value = mock_agent
        result = run_council("US-China trade war", predictions)
    for key in ("verdict_title", "verdict_detail", "confidence", "endorsed_agent", "dissenting_view"):
        assert key in result


def test_run_predictor_handles_unparseable_response():
    from agents.nostradamus_pipeline import run_predictor, PREDICTORS
    with patch("agents.nostradamus_pipeline.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": [MagicMock(content="Maaf, tidak bisa memproses ini.")]}
        mock_build.return_value = mock_agent
        result = run_predictor(PREDICTORS[0], "test event", "test news")
    assert "error" in result


def test_run_council_handles_unparseable_response():
    from agents.nostradamus_pipeline import run_council
    with patch("agents.nostradamus_pipeline.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": [MagicMock(content="Tidak bisa memproses prediksi.")]}
        mock_build.return_value = mock_agent
        result = run_council("test event", [])
    assert "error" in result
```

- [ ] **Step 2 — Run tests to confirm all 5 fail**

```powershell
$env:PYTHONUTF8=1; pytest tests/test_nostradamus_pipeline.py -v
```
Expected: 5 errors (`ModuleNotFoundError: No module named 'agents.nostradamus_pipeline'`)

- [ ] **Step 3 — Create `tools/nostradamus_tools.py`**

```python
from langchain.tools import tool
from pathlib import Path
from datetime import datetime


@tool
def save_prophecy(topic: str, verdict: str) -> str:
    """Save Nostradamus prophecy verdict to AI Data/Nostradamus Agent/ vault.
    Args:
        topic: The event or topic that was analyzed.
        verdict: The council verdict text to save.
    """
    vault = Path("AI Data/Nostradamus Agent")
    vault.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    fname = vault / f"prophecy_{ts}.md"
    fname.write_text(
        f"# Nostradamus Prophecy\n\n**Topik:** {topic}\n\n**Vonis:**\n{verdict}\n\n**Tanggal:** {ts}\n",
        encoding="utf-8"
    )
    return f"Saved to {fname}"
```

- [ ] **Step 4 — Create `agents/nostradamus_pipeline.py`**

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


PREDICTORS = [
    {
        "id": "trend",
        "name": "Trend Analyst",
        "prompt": """Kamu adalah Analis Tren — pakar yang membaca momentum dan arah pergerakan dari pola data terkini.
Berdasarkan berita yang diberikan, prediksi ke mana peristiwa ini akan berkembang berdasarkan tren saat ini.

Kembalikan HANYA JSON (tanpa teks lain):
{
  "agent_id": "trend",
  "agent_name": "Trend Analyst",
  "prediction_title": "judul prediksi singkat (max 8 kata)",
  "prediction": "prediksi konkret 2-3 kalimat",
  "confidence": 72,
  "reasoning": "penjelasan singkat mengapa ini yang paling mungkin"
}""",
    },
    {
        "id": "risk",
        "name": "Risk Assessor",
        "prompt": """Kamu adalah Penilai Risiko — pessimist yang mengidentifikasi skenario terburuk dan risiko ekor (tail risks).
Berdasarkan berita yang diberikan, identifikasi apa yang bisa salah dan skenario paling berbahaya.

Kembalikan HANYA JSON (tanpa teks lain):
{
  "agent_id": "risk",
  "agent_name": "Risk Assessor",
  "prediction_title": "judul prediksi singkat (max 8 kata)",
  "prediction": "prediksi konkret 2-3 kalimat tentang risiko",
  "confidence": 60,
  "reasoning": "mengapa risiko ini nyata dan perlu diwaspadai"
}""",
    },
    {
        "id": "optimist",
        "name": "Optimist",
        "prompt": """Kamu adalah Optimis — analis yang mengidentifikasi katalis positif dan jendela peluang terbaik.
Berdasarkan berita yang diberikan, prediksi skenario terbaik yang realistis dan bisa terjadi.

Kembalikan HANYA JSON (tanpa teks lain):
{
  "agent_id": "optimist",
  "agent_name": "Optimist",
  "prediction_title": "judul prediksi singkat (max 8 kata)",
  "prediction": "prediksi konkret 2-3 kalimat tentang peluang terbaik",
  "confidence": 65,
  "reasoning": "katalis apa yang bisa mendorong skenario positif ini"
}""",
    },
    {
        "id": "history",
        "name": "Historical Analogist",
        "prompt": """Kamu adalah Analis Sejarah — pakar yang menemukan analog historis dan pola siklus berulang.
Berdasarkan berita yang diberikan, temukan peristiwa serupa dari sejarah dan prediksi berdasarkan preseden tersebut.

Kembalikan HANYA JSON (tanpa teks lain):
{
  "agent_id": "history",
  "agent_name": "Historical Analogist",
  "prediction_title": "judul prediksi singkat (max 8 kata)",
  "prediction": "prediksi konkret 2-3 kalimat, sebutkan preseden historis yang relevan",
  "confidence": 70,
  "reasoning": "analog historis mana yang paling relevan dan mengapa polanya berulang"
}""",
    },
    {
        "id": "systems",
        "name": "Systems Thinker",
        "prompt": """Kamu adalah Pemikir Sistem — analis yang memetakan efek lanjutan (second-order effects) dan konsekuensi berantai yang sering terlewat.
Berdasarkan berita yang diberikan, prediksi dampak tidak langsung yang akan terasa di luar bidang utama.

Kembalikan HANYA JSON (tanpa teks lain):
{
  "agent_id": "systems",
  "agent_name": "Systems Thinker",
  "prediction_title": "judul prediksi singkat (max 8 kata)",
  "prediction": "prediksi konkret 2-3 kalimat tentang efek lanjutan yang tidak terduga",
  "confidence": 68,
  "reasoning": "mekanisme sebab-akibat yang menghasilkan efek lanjutan ini"
}""",
    },
]

_GATHERER_PROMPT = """Kamu adalah NewsGatherer — analis berita yang mengumpulkan berita terkini dari berbagai sumber global.
Gunakan tool get_recent_news untuk mencari berita tentang topik yang diberikan.

Kembalikan HANYA JSON (tanpa teks lain):
{
  "news": [
    {
      "headline": "judul berita",
      "source": "nama media",
      "date": "tanggal/waktu",
      "summary": "ringkasan 1-2 kalimat"
    }
  ]
}

Kumpulkan 5-8 berita terbaru. Jika tool tidak menemukan hasil, kembalikan {"news": []}.
"""

_COUNCIL_PROMPT = """Kamu adalah Dewan Peramal — majelis hakim yang menimbang 5 prediksi dari perspektif berbeda dan menetapkan vonis akhir.
Gunakan tool save_prophecy untuk menyimpan vonis ke vault sebelum mengembalikan JSON.

Kembalikan HANYA JSON (tanpa teks lain):
{
  "verdict_title": "judul vonis singkat (max 8 kata)",
  "verdict_detail": "vonis konkret 3-4 kalimat — prediksi paling mungkin dan alasannya",
  "confidence": 75,
  "endorsed_agent": "nama agen yang prediksinya paling akurat",
  "dissenting_view": "1 kalimat sudut pandang berbeda yang patut dipertimbangkan"
}
"""


def run_news_gatherer(event: str) -> dict:
    from tools.news_tools import get_recent_news
    agent = build_agent(_GATHERER_PROMPT, [get_recent_news])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Cari berita terkini tentang: {event}"}]
    })
    parsed = _parse_json_output(result)
    if "news" not in parsed:
        return {"news": []}
    return parsed


def run_predictor(predictor: dict, event: str, news_summary: str) -> dict:
    agent = build_agent(predictor["prompt"], [])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Topik: {event}\n\nBerita terkini:\n{news_summary}\n\nBerikan prediksimu."}]
    })
    return _parse_json_output(result)


def run_council(event: str, predictions: list) -> dict:
    from tools.nostradamus_tools import save_prophecy
    agent = build_agent(_COUNCIL_PROMPT, [save_prophecy])
    preds_text = "\n\n".join(
        f"[{p.get('agent_name', '?')}]\n"
        f"Prediksi: {p.get('prediction_title', '')}\n"
        f"{p.get('prediction', '')}\n"
        f"Kepercayaan: {p.get('confidence', '?')}%"
        for p in predictions
    )
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Topik: {event}\n\n5 Prediksi:\n\n{preds_text}\n\nTetapkan vonis dan simpan ke vault."}]
    })
    return _parse_json_output(result)
```

- [ ] **Step 5 — Run tests to confirm all 5 pass**

```powershell
$env:PYTHONUTF8=1; pytest tests/test_nostradamus_pipeline.py -v
```
Expected: `5 passed`

- [ ] **Step 6 — Run regression tests**

```powershell
$env:PYTHONUTF8=1; pytest tests/test_davinci_pipeline.py tests/test_study_agents.py -v
```
Expected: all pass

- [ ] **Step 7 — Commit**

```powershell
git add tools/nostradamus_tools.py agents/nostradamus_pipeline.py tests/test_nostradamus_pipeline.py
git commit -m "feat(nostradamus): add pipeline agents + TDD tests — NewsGatherer, 5 Predictors, Council"
```

---

## Task 2: Server Endpoints

**Files:**
- Modify: `server.py` (3 insertion points)

- [ ] **Step 1 — Add API endpoints block**

In `server.py`, find the line:

```python
# ─── Najwa News Feed ──────────────────────────────────────────────────────────
```
(currently at line ~1625, immediately after the `return {"saved": len(req.expansions)}` line of `davinci_save`)

Insert the following block **before** that Najwa comment:

```python

# ── Nostradamus Prophetic Page ────────────────────────────────────────────────

@app.get("/api/nostradamus/prophesy")
async def nostradamus_prophesy(event: str = ""):
    event = event.strip()
    if not event:
        raise HTTPException(status_code=400, detail="Event required")
    if len(event) > 200:
        raise HTTPException(status_code=400, detail="Event too long (max 200 chars)")

    async def generate():
        try:
            from agents.nostradamus_pipeline import run_news_gatherer, run_predictor, run_council, PREDICTORS
            loop = asyncio.get_running_loop()

            # Phase 1 — News gathering
            news_result = await _run_agent(loop, run_news_gatherer, event)
            news_items = news_result.get("news", [])
            news_summary = "\n".join(
                f"- {n.get('headline', '')} ({n.get('source', '')}, {n.get('date', '')}): {n.get('summary', '')}"
                for n in news_items
            )
            for item in news_items:
                yield _sse({"event": "news_item", **item})
            yield _sse({"event": "news_done", "count": len(news_items)})

            # Phase 2 — Parallel predictions, stream as each finishes
            async def safe_predict(predictor):
                try:
                    return await _run_agent(loop, run_predictor, predictor, event, news_summary)
                except Exception as exc:
                    return {"agent_id": predictor["id"], "agent_name": predictor["name"],
                            "error": str(exc)[:120]}

            tasks = [asyncio.create_task(safe_predict(p)) for p in PREDICTORS]
            predictions = []
            for coro in asyncio.as_completed(tasks):
                result = await coro
                if "error" not in result:
                    predictions.append(result)
                yield _sse({"event": "prediction", **result})
            yield _sse({"event": "predictions_done", "count": len(PREDICTORS)})

            # Phase 3 — Council verdict
            verdict = await _run_agent(loop, run_council, event, predictions)
            yield _sse({"event": "verdict", **verdict})
            yield _sse({"event": "prophesy_done"})

        except Exception as exc:
            yield _sse({"event": "error", "message": str(exc)})

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class NostradamusSaveRequest(BaseModel):
    event: str
    verdict: dict


@app.post("/api/nostradamus/save")
async def nostradamus_save(req: NostradamusSaveRequest):
    notes_path = Path("data/notes.json")
    try:
        notes = json.loads(notes_path.read_text(encoding="utf-8"))
    except Exception:
        notes = []
    v = req.verdict
    content = (
        f"## {v.get('verdict_title', req.event)}\n\n"
        f"{v.get('verdict_detail', '')}\n\n"
        f"**Kepercayaan:** {v.get('confidence', '?')}%  \n"
        f"**Didukung:** {v.get('endorsed_agent', '')}  \n"
        f"**Dissent:** {v.get('dissenting_view', '')}"
    )
    notes.append({
        "id": str(uuid.uuid4()),
        "title": v.get("verdict_title", req.event),
        "content": content,
        "tags": ["nostradamus", "prediction", req.event[:30]],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    })
    notes_path.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"saved": 1}

```

- [ ] **Step 2 — Add mkdir**

Find the line (currently at ~line 1932):
```python
Path("static/davinci").mkdir(exist_ok=True)
```

Add immediately after it:
```python
Path("static/nostradamus").mkdir(exist_ok=True)
```

- [ ] **Step 3 — Add page route**

Find the block (currently ending at ~line 1969):
```python
@app.get("/davinci", include_in_schema=False)
@app.get("/davinci/", include_in_schema=False)
async def serve_davinci():
    p = Path("static/davinci/index.html")
    if p.exists():
        return FileResponse(str(p), headers={"Cache-Control": "no-cache"})
    return JSONResponse({"error": "Da Vinci page not found"}, status_code=404)
```

Add immediately after that block (before the `/fitness` route):
```python

@app.get("/nostradamus", include_in_schema=False)
@app.get("/nostradamus/", include_in_schema=False)
async def serve_nostradamus():
    p = Path("static/nostradamus/index.html")
    if p.exists():
        return FileResponse(str(p), headers={"Cache-Control": "no-cache"})
    return JSONResponse({"error": "Nostradamus page not found"}, status_code=404)
```

- [ ] **Step 4 — Verify server imports OK**

```powershell
$env:PYTHONUTF8=1; python -c "import server; print('OK')"
```
Expected: `OK` (no errors)

- [ ] **Step 5 — Commit**

```powershell
git add server.py
git commit -m "feat(nostradamus): add /api/nostradamus/prophesy SSE + /api/nostradamus/save + page route"
```

---

## Task 3: Frontend Page

**Files:**
- Create: `static/nostradamus/index.html`

- [ ] **Step 1 — Create `static/nostradamus/index.html`**

Create the file with the following complete content:

```html
<!DOCTYPE html>
<html lang="id" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Nostradamus — Prophetic Intelligence</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --paper: #F3EEE5; --paper-2: #ECE6DA; --paper-3: #E4DDCD;
  --surface: #FAF6EE; --surface-2: #FFFFFF;
  --ink: #17171A; --ink-2: #3B3B3F; --ink-3: #6B6A6E; --ink-4: #9B9A9E;
  --rule: rgba(23,23,26,0.12); --rule-soft: rgba(23,23,26,0.06);
  --hover: rgba(23,23,26,0.04);
  --clay: #CC785C; --clay-soft: rgba(204,120,92,0.10);
  --hue-nostradamus: #8B5A9E;
  --shadow-1: 0 1px 0 rgba(23,23,26,0.04);
  --shadow-2: 0 4px 24px rgba(23,23,26,0.06);
}
[data-theme="dark"] {
  --paper: #17171A; --paper-2: #1E1E22; --paper-3: #24242A;
  --surface: #1A1A1E; --surface-2: #222227;
  --ink: #F2EDE3; --ink-2: #CEC9BE; --ink-3: #9B9890; --ink-4: #6D6B67;
  --rule: rgba(242,237,227,0.14); --rule-soft: rgba(242,237,227,0.07);
  --hover: rgba(242,237,227,0.05);
  --clay: #E59A7F; --clay-soft: rgba(229,154,127,0.12);
  --hue-nostradamus: #B8A0D4;
  --shadow-1: 0 1px 0 rgba(0,0,0,0.3); --shadow-2: 0 4px 24px rgba(0,0,0,0.4);
}

html, body { min-height: 100vh; }
body { background: var(--paper); color: var(--ink); font-family: 'Inter', sans-serif; font-size: 14px; line-height: 1.55; -webkit-font-smoothing: antialiased; }

/* Header */
.header { background: var(--ink); color: var(--paper); padding: 0 28px; height: 48px; display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 10; }
.header-brand { display: flex; align-items: center; gap: 10px; }
.header-logo { font-family: 'Instrument Serif', serif; font-size: 20px; letter-spacing: -0.02em; color: var(--paper); }
.header-tag { font-family: 'JetBrains Mono', monospace; font-size: 9px; letter-spacing: 0.14em; text-transform: uppercase; background: var(--hue-nostradamus); color: #fff; padding: 2px 9px; border-radius: 20px; }
.header-actions { display: flex; align-items: center; gap: 16px; }
.theme-btn { background: none; border: none; color: var(--paper); cursor: pointer; font-size: 14px; opacity: 0.6; padding: 4px; line-height: 1; }
.theme-btn:hover { opacity: 1; }
.back-link { font-family: 'JetBrains Mono', monospace; font-size: 10px; letter-spacing: 0.08em; color: rgba(242,237,227,0.45); text-decoration: none; }
.back-link:hover { color: var(--paper); }

/* Input bar */
.input-bar { background: var(--paper-2); border-bottom: 1px solid var(--rule); padding: 16px 28px; }
.input-wrap { display: flex; gap: 10px; max-width: 800px; }
.event-input { flex: 1; background: var(--surface); border: 1px solid var(--rule); border-radius: 6px; padding: 10px 14px; font-family: 'Inter', sans-serif; font-size: 14px; color: var(--ink); outline: none; transition: border-color 0.15s; }
.event-input::placeholder { color: var(--ink-4); }
.event-input:focus { border-color: var(--hue-nostradamus); }
.prophesy-btn { background: var(--ink); color: var(--paper); border: none; border-radius: 6px; padding: 10px 22px; font-family: 'JetBrains Mono', monospace; font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; cursor: pointer; transition: background 0.15s, opacity 0.15s; white-space: nowrap; }
.prophesy-btn:hover:not(:disabled) { background: var(--hue-nostradamus); }
.prophesy-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* Main */
.main { max-width: 1000px; margin: 0 auto; padding: 32px 28px 80px; }
.section { margin-bottom: 40px; animation: fadeIn 0.3s ease; }
.section.hidden { display: none; }
.section-label { font-family: 'JetBrains Mono', monospace; font-size: 10.5px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--ink-4); margin-bottom: 14px; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

/* News feed */
.news-chip { display: flex; align-items: baseline; gap: 8px; padding: 9px 0; border-bottom: 1px solid var(--rule-soft); animation: fadeIn 0.25s ease; }
.news-dot { color: var(--hue-nostradamus); font-size: 8px; flex-shrink: 0; margin-top: 2px; }
.news-headline { color: var(--ink); font-size: 13.5px; flex: 1; }
.news-meta { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: var(--ink-4); white-space: nowrap; }

/* Predictions grid */
.predictions-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
@media (max-width: 740px) { .predictions-grid { grid-template-columns: 1fr 1fr; } }
@media (max-width: 480px) { .predictions-grid { grid-template-columns: 1fr; } }

/* Prediction card */
.pred-card { background: var(--surface); border: 1px solid var(--rule); border-top: 3px solid var(--card-accent, var(--rule)); border-radius: 6px; padding: 16px; animation: fadeIn 0.4s ease; }
.pred-skeleton { animation: none; }
.pred-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.pred-label { font-family: 'JetBrains Mono', monospace; font-size: 9px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--card-accent, var(--ink-3)); }
.pred-confidence { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: var(--ink-4); }
.pred-bar { height: 2px; background: var(--rule); border-radius: 1px; margin-bottom: 12px; }
.pred-bar-fill { height: 100%; background: var(--card-accent, var(--clay)); border-radius: 1px; transition: width 0.6s ease; }
.pred-title { font-family: 'Instrument Serif', serif; font-size: 15px; color: var(--ink); margin-bottom: 8px; line-height: 1.3; }
.pred-body { font-size: 12.5px; color: var(--ink-2); line-height: 1.6; margin-bottom: 8px; }
.pred-reasoning { font-size: 11.5px; color: var(--ink-4); font-style: italic; line-height: 1.5; }
.pred-error-msg { font-size: 12px; color: var(--clay); margin-top: 6px; }

/* Skeleton shimmer */
@keyframes shimmer { from { background-position: 200% 0; } to { background-position: -200% 0; } }
.skel-bar { height: 10px; border-radius: 3px; background: linear-gradient(90deg, var(--rule) 25%, var(--hover) 50%, var(--rule) 75%); background-size: 200% 100%; animation: shimmer 1.4s infinite; margin-bottom: 10px; width: 55%; }
.skel-line { height: 9px; border-radius: 3px; background: linear-gradient(90deg, var(--rule) 25%, var(--hover) 50%, var(--rule) 75%); background-size: 200% 100%; animation: shimmer 1.4s infinite; margin-bottom: 7px; }
.skel-line.short { width: 72%; }

/* Verdict */
.verdict-card { background: var(--surface-2); border: 1px solid var(--rule); border-left: 3px solid var(--hue-nostradamus); border-radius: 6px; padding: 24px; margin-bottom: 16px; animation: fadeIn 0.4s ease; }
.verdict-title { font-family: 'Instrument Serif', serif; font-size: 22px; color: var(--ink); margin-bottom: 12px; line-height: 1.2; }
.verdict-detail { font-size: 14px; color: var(--ink-2); line-height: 1.7; margin-bottom: 16px; }
.verdict-meta { display: flex; gap: 16px; font-family: 'JetBrains Mono', monospace; font-size: 10.5px; color: var(--ink-3); margin-bottom: 10px; flex-wrap: wrap; }
.verdict-sep { color: var(--rule); }
.verdict-dissent { font-size: 12.5px; color: var(--ink-4); font-style: italic; border-top: 1px solid var(--rule-soft); padding-top: 12px; }
.save-btn { background: var(--clay); color: #fff; border: none; border-radius: 6px; padding: 10px 20px; font-family: 'JetBrains Mono', monospace; font-size: 10.5px; letter-spacing: 0.10em; text-transform: uppercase; cursor: pointer; transition: opacity 0.15s; }
.save-btn:hover:not(:disabled) { opacity: 0.85; }
.save-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.save-btn.hidden { display: none; }

/* Toast */
.toast { position: fixed; bottom: 24px; right: 24px; background: var(--ink); color: var(--paper); font-family: 'JetBrains Mono', monospace; font-size: 11px; padding: 10px 16px; border-radius: 6px; z-index: 100; animation: fadeIn 0.2s ease; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--rule); border-radius: 4px; }
</style>
</head>
<body>

<header class="header">
  <div class="header-brand">
    <span class="header-logo">Nostradamus</span>
    <span class="header-tag">Prophetic Intelligence</span>
  </div>
  <div class="header-actions">
    <button id="theme-toggle" class="theme-btn" onclick="G.toggleTheme()" title="Toggle theme">☀</button>
    <a href="/" class="back-link">← home</a>
  </div>
</header>

<div class="input-bar">
  <div class="input-wrap">
    <input id="event-input" class="event-input" type="text"
           placeholder="Peristiwa atau topik yang sedang terjadi..." maxlength="200">
    <button id="prophesy-btn" class="prophesy-btn" onclick="G.prophesy()">Prophesy</button>
  </div>
</div>

<main class="main">
  <section id="news-section" class="section hidden">
    <div class="section-label">Berita Terkini</div>
    <div id="news-feed"></div>
  </section>

  <section id="predictions-section" class="section hidden">
    <div class="section-label">Prediksi — 5 Perspektif</div>
    <div id="predictions-grid" class="predictions-grid"></div>
  </section>

  <section id="verdict-section" class="section hidden">
    <div class="section-label">Vonis Dewan</div>
    <div id="verdict-content"></div>
    <button id="save-btn" class="save-btn hidden" onclick="G.saveToNotes()">📝 Simpan ke Notes</button>
  </section>
</main>

<script>
const G = {};

G._esc = s => String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

// ── Theme ──────────────────────────────────────────────────────────────────────
G.toggleTheme = () => {
  const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('nstrd-theme', next);
  document.getElementById('theme-toggle').textContent = next === 'dark' ? '☀' : '🌙';
};
(function () {
  const t = localStorage.getItem('nstrd-theme') || 'light';
  document.documentElement.setAttribute('data-theme', t);
  document.getElementById('theme-toggle').textContent = t === 'dark' ? '☀' : '🌙';
})();

// ── Predictor config ───────────────────────────────────────────────────────────
const PREDICTOR_ORDER = ['trend','risk','optimist','history','systems'];
const PREDICTOR_ACCENTS = {
  trend:    { light: '#A68A3E', dark: '#D4B86A' },
  risk:     { light: '#A65046', dark: '#D48278' },
  optimist: { light: '#5E8A7D', dark: '#8FBDAF' },
  history:  { light: '#5E7A8A', dark: '#8FAEBE' },
  systems:  { light: '#8B5A9E', dark: '#B8A0D4' },
};
G._accent = id => {
  const theme = document.documentElement.getAttribute('data-theme') || 'light';
  return (PREDICTOR_ACCENTS[id] || {})[theme] || 'var(--clay)';
};

// ── State ──────────────────────────────────────────────────────────────────────
G.lastEvent  = '';
G.lastVerdict = null;
G.currentES  = null;

// ── Main flow ──────────────────────────────────────────────────────────────────
G.prophesy = () => {
  const event = document.getElementById('event-input').value.trim();
  if (!event) return;
  if (G.currentES) { G.currentES.close(); G.currentES = null; }
  G.lastEvent = event;
  G.lastVerdict = null;

  ['news-section','predictions-section','verdict-section'].forEach(id =>
    document.getElementById(id).classList.add('hidden'));
  document.getElementById('news-feed').innerHTML = '';
  document.getElementById('predictions-grid').innerHTML = '';
  document.getElementById('verdict-content').innerHTML = '';
  document.getElementById('save-btn').classList.add('hidden');

  const btn = document.getElementById('prophesy-btn');
  btn.disabled = true; btn.textContent = 'Reading…';

  const es = new EventSource('/api/nostradamus/prophesy?event=' + encodeURIComponent(event));
  G.currentES = es;

  es.onmessage = e => {
    try {
      const d = JSON.parse(e.data);
      const ev = d.event;
      if      (ev === 'news_item')      G.renderNewsItem(d);
      else if (ev === 'news_done')      G.onNewsDone();
      else if (ev === 'prediction')     G.renderPrediction(d);
      else if (ev === 'verdict')        G.renderVerdict(d);
      else if (ev === 'prophesy_done')  G.onDone();
      else if (ev === 'error')          G.onError(d.message);
    } catch (_) {}
  };
  es.onerror = () => { G.onError('Koneksi terputus.'); es.close(); G.currentES = null; };
};

// ── Renderers ──────────────────────────────────────────────────────────────────
G.renderNewsItem = d => {
  document.getElementById('news-section').classList.remove('hidden');
  document.getElementById('news-feed').insertAdjacentHTML('beforeend',
    `<div class="news-chip">
      <span class="news-dot">&#9679;</span>
      <span class="news-headline">${G._esc(d.headline)}</span>
      <span class="news-meta">${G._esc(d.source||'')}${d.date?' &middot; '+G._esc(d.date):''}</span>
    </div>`
  );
};

G.onNewsDone = () => {
  document.getElementById('predictions-section').classList.remove('hidden');
  const grid = document.getElementById('predictions-grid');
  PREDICTOR_ORDER.forEach(id => {
    if (document.getElementById('card-' + id)) return;
    const skel = document.createElement('div');
    skel.id = 'card-' + id;
    skel.className = 'pred-card pred-skeleton';
    skel.innerHTML = '<div class="skel-bar"></div><div class="skel-line"></div><div class="skel-line short"></div>';
    grid.appendChild(skel);
  });
};

G.renderPrediction = d => {
  document.getElementById('predictions-section').classList.remove('hidden');
  const accent = G._accent(d.agent_id || '');
  const pct = Math.min(100, Math.max(0, parseInt(d.confidence) || 0));
  const el = document.getElementById('card-' + (d.agent_id || ''));
  const target = el || document.createElement('div');
  if (!el) { target.id = 'card-' + (d.agent_id || ''); document.getElementById('predictions-grid').appendChild(target); }
  target.style.setProperty('--card-accent', accent);

  if (d.error) {
    target.className = 'pred-card';
    target.innerHTML =
      `<div class="pred-header"><span class="pred-label">${G._esc(d.agent_name||d.agent_id||'')}</span></div>
       <div class="pred-error-msg">${G._esc(d.error)}</div>`;
  } else {
    target.className = 'pred-card';
    target.innerHTML =
      `<div class="pred-header">
         <span class="pred-label">${G._esc(d.agent_name||'')}</span>
         <span class="pred-confidence">${pct}%</span>
       </div>
       <div class="pred-bar"><div class="pred-bar-fill" style="width:${pct}%"></div></div>
       <div class="pred-title">${G._esc(d.prediction_title||'')}</div>
       <div class="pred-body">${G._esc(d.prediction||'')}</div>
       <div class="pred-reasoning">${G._esc(d.reasoning||'')}</div>`;
  }
};

G.renderVerdict = d => {
  G.lastVerdict = d;
  document.getElementById('verdict-section').classList.remove('hidden');
  const pct = Math.min(100, Math.max(0, parseInt(d.confidence) || 0));
  document.getElementById('verdict-content').innerHTML =
    `<div class="verdict-card">
       <div class="verdict-title">${G._esc(d.verdict_title||'')}</div>
       <div class="verdict-detail">${G._esc(d.verdict_detail||'')}</div>
       <div class="verdict-meta">
         <span>Kepercayaan: ${pct}%</span>
         <span class="verdict-sep">&middot;</span>
         <span>Didukung: ${G._esc(d.endorsed_agent||'')}</span>
       </div>
       <div class="verdict-dissent">Dissent: ${G._esc(d.dissenting_view||'')}</div>
     </div>`;
};

G.onDone = () => {
  const btn = document.getElementById('prophesy-btn');
  btn.disabled = false; btn.textContent = 'Prophesy';
  if (G.lastVerdict) document.getElementById('save-btn').classList.remove('hidden');
  if (G.currentES) { G.currentES.close(); G.currentES = null; }
};

G.onError = msg => {
  G.onDone();
  const t = document.createElement('div');
  t.className = 'toast';
  t.textContent = 'Error: ' + G._esc(msg);
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 4000);
};

// ── Save to Notes ──────────────────────────────────────────────────────────────
G.saveToNotes = () => {
  if (!G.lastVerdict) return;
  const btn = document.getElementById('save-btn');
  btn.disabled = true; btn.textContent = 'Menyimpan…';
  fetch('/api/nostradamus/save', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({event: G.lastEvent, verdict: G.lastVerdict})
  })
  .then(r => r.json())
  .then(() => { btn.textContent = '✓ Tersimpan'; })
  .catch(() => { btn.textContent = 'Gagal'; btn.disabled = false; });
};

// ── Enter key ──────────────────────────────────────────────────────────────────
document.getElementById('event-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') G.prophesy();
});
</script>
</body>
</html>
```

- [ ] **Step 2 — Verify file exists**

```powershell
Test-Path "static/nostradamus/index.html"
```
Expected: `True`

- [ ] **Step 3 — Start server and open page**

```powershell
$env:PYTHONUTF8=1; python server.py
```

Open `http://localhost:8000/nostradamus` in browser. Verify:
- Header renders with "Nostradamus" serif logo and violet "PROPHETIC INTELLIGENCE" tag
- Input field and PROPHESY button visible
- Dark mode toggle works (click ☀ → page goes dark, click 🌙 → returns to light)
- Theme persists on page reload (check localStorage `nstrd-theme`)

- [ ] **Step 4 — Commit**

```powershell
git add static/nostradamus/index.html
git commit -m "feat(nostradamus): add standalone page — 3-phase UI, dark mode, paper-and-ink tokens"
```

---

## Task 4: Sidebar Integration

**Files:**
- Modify: `static/index/styles.css` (2 insertions)
- Modify: `static/index/data.jsx` (2 insertions)

- [ ] **Step 1 — Add `--hue-nostradamus` to light theme in `styles.css`**

Find line (currently line 40):
```css
  --hue-orwell:   #8A7058;   /* warm sepia */
```

Add immediately after it:
```css
  --hue-nostradamus: #8B5A9E;   /* deep violet */
```

- [ ] **Step 2 — Add `--hue-nostradamus` to dark theme in `styles.css`**

Find line (currently line 75):
```css
  --hue-orwell:   #BEAA90;   /* warm sepia light */
```

Add immediately after it:
```css
  --hue-nostradamus: #B8A0D4;   /* soft violet */
```

- [ ] **Step 3 — Add `nostradamus` agent entry in `data.jsx`**

Find in `static/index/data.jsx` (currently ending near line 83):
```javascript
  orwell: {
    name: 'Orwell', sub: 'Writing Coach', hue: 'var(--hue-orwell)',
    issue: 'XI.', cluster: 'academic',
    tagline: 'Clear prose, sharp arguments — essays, reports, emails, or creative writing.',
    greeting: 'Apa yang perlu ditulis? Dari awal, atau ada draft yang perlu dipertajam?',
    Ico: () => { const {IcoFeather} = window.Icons; return <IcoFeather/>; },
  },
};
```

Replace with:
```javascript
  orwell: {
    name: 'Orwell', sub: 'Writing Coach', hue: 'var(--hue-orwell)',
    issue: 'XI.', cluster: 'academic',
    tagline: 'Clear prose, sharp arguments — essays, reports, emails, or creative writing.',
    greeting: 'Apa yang perlu ditulis? Dari awal, atau ada draft yang perlu dipertajam?',
    Ico: () => { const {IcoFeather} = window.Icons; return <IcoFeather/>; },
  },
  nostradamus: {
    name: 'Nostradamus', sub: 'Prophetic Intelligence', hue: 'var(--hue-nostradamus)',
    issue: 'XII.', cluster: 'research', url: '/nostradamus',
    tagline: 'Five minds, one verdict — predicting what current events foretell.',
    greeting: 'Name the event. Five prophets will read the signs.',
    Ico: () => { const {IcoSparkle} = window.Icons; return <IcoSparkle/>; },
  },
};
```

- [ ] **Step 4 — Add `'nostradamus'` to `AGENT_ORDER`**

Find (currently line 85):
```javascript
const AGENT_ORDER = ['task','notes','news','coding','schedule','budget','fitness','journal','davinci','euler','orwell'];
```

Replace with:
```javascript
const AGENT_ORDER = ['task','notes','news','coding','schedule','budget','fitness','journal','davinci','euler','orwell','nostradamus'];
```

- [ ] **Step 5 — Verify main site still loads**

With server running, open `http://localhost:8000`. Verify:
- Nostradamus appears in sidebar under "Research" cluster
- Clicking Nostradamus navigates to `/nostradamus`
- Other agents unaffected

- [ ] **Step 6 — Commit**

```powershell
git add static/index/styles.css static/index/data.jsx
git commit -m "feat(nostradamus): add sidebar entry (XII. Research) + hue tokens to styles.css"
```

---

## Verification

```powershell
# 1. All 5 pipeline tests pass
$env:PYTHONUTF8=1; pytest tests/test_nostradamus_pipeline.py -v
# Expected: 5 passed

# 2. Regression — existing tests unaffected
$env:PYTHONUTF8=1; pytest tests/test_davinci_pipeline.py tests/test_study_agents.py tests/test_stock_screener.py -v

# 3. Server imports clean
$env:PYTHONUTF8=1; python -c "import server; print('OK')"

# 4. End-to-end
$env:PYTHONUTF8=1; python server.py
# http://localhost:8000/nostradamus
# Type "US-China trade war" → Enter
# Phase 1: news chips stream in under "Berita Terkini"
# Phase 2: 5 skeleton cards appear, fill in one by one as each predictor finishes
# Phase 3: Council verdict appears with confidence + endorsed agent + dissent
# Click "Simpan ke Notes" → success message "✓ Tersimpan"
# Verify note appears at http://localhost:8000/study
# Verify vault file created at AI Data/Nostradamus Agent/prophecy_*.md
# http://localhost:8000 → Nostradamus visible in sidebar → click navigates to /nostradamus
# Toggle dark mode → all sections render correctly in dark theme
```
