# Nostradamus — Prophetic Intelligence
## Design Spec

**Date:** 2026-05-26  
**Status:** Approved for implementation

---

## Context

CassanovaL has standalone pipeline pages for several agents (`/davinci`, `/study`, `/fitness`). This adds a new multi-agent prophetic pipeline at `/nostradamus`: the user describes a current world event, a NewsGatherer agent collects recent news, five Predictor agents each reason from a distinct methodology in parallel, and a Council agent delivers a single verdict with confidence score, endorsement, and dissenting view.

---

## Goal

Build a standalone `/nostradamus` page with a 3-phase SSE pipeline:

1. **Phase 1 — NewsGatherer:** Collects 5–8 recent news items about the user's event via `get_recent_news` tool, streaming headlines live.
2. **Phase 2 — 5 Predictors:** Run in parallel (`asyncio.as_completed`), each reasoning from a distinct methodology. Cards fill in real time as each predictor finishes.
3. **Phase 3 — Council:** Reviews all 5 predictions, delivers verdict + confidence + dissent, auto-saves to `AI Data/Nostradamus Agent/`.

---

## Architecture

### Pipeline (LangChain SSE — same pattern as `/davinci`)

```
User types event → clicks PROPHESY
    ↓
GET /api/nostradamus/prophesy?event=...  (EventSource)
    ↓
Phase 1 — NewsGatherer (build_agent, get_recent_news tool)
    Searches recent news on the event (5–8 items)
    Output: {"news": [{"headline", "source", "date", "summary"}, ...]}
    → emits "news_item" per headline
    → emits "news_done"
    ↓
Phase 2 — 5 Predictors (asyncio.as_completed — streams as each finishes)
    All receive same news_summary + event in their messages
    Each outputs: {agent_id, agent_name, prediction_title, prediction, confidence (0-100), reasoning}
    → emits "prediction" as each predictor completes
    → emits "predictions_done"
    ↓
Phase 3 — Council (runs after all 5 done)
    Receives all 5 predictions as formatted context
    Tools: save_prophecy (auto-saves to AI Data/Nostradamus Agent/)
    Output: {verdict_title, verdict_detail, confidence, endorsed_agent, dissenting_view}
    → emits "verdict"
    → emits "prophesy_done"
```

### The 5 Predictors

| ID | Name | Reasoning Focus |
|----|------|----------------|
| `trend` | Trend Analyst | Momentum + directional probability — where is this heading? |
| `risk` | Risk Assessor | Worst-case scenarios, tail risks, what could go wrong |
| `optimist` | Optimist | Best-case catalysts, opportunity windows |
| `history` | Historical Analogist | Historical parallels — "this happened before in [year]" |
| `systems` | Systems Thinker | Second-order effects, cascading consequences |

### SSE Events

| Event | Payload | When |
|-------|---------|------|
| `news_item` | `{headline, source, date, summary}` | Phase 1, per item |
| `news_done` | `{count}` | After all news |
| `prediction` | `{agent_id, agent_name, prediction_title, prediction, confidence, reasoning}` | Phase 2, per predictor as it finishes |
| `predictions_done` | `{count}` | After all 5 |
| `verdict` | `{verdict_title, verdict_detail, confidence, endorsed_agent, dissenting_view}` | Phase 3 |
| `prophesy_done` | `{}` | After verdict |
| `error` | `{message}` | On failure |

---

## Components

### 1. `agents/nostradamus_pipeline.py` (NEW)

Follows exact pattern from `agents/davinci_pipeline.py`: copy `_invoke_with_retry` and `_parse_json_output` helpers directly (do not import from davinci — separate module).

**`PREDICTORS: list[dict]`** — 5 predictor configurations, each with `id`, `name`, `prompt`:

```python
PREDICTORS = [
    {
        "id": "trend",
        "name": "Trend Analyst",
        "prompt": """Kamu adalah Analis Tren — pakar yang membaca momentum dan arah pergerakan dari pola data terkini.
Berdasarkan berita yang diberikan, prediksi ke mana peristiwa ini akan berkembang.

Kembalikan HANYA JSON (tanpa teks lain):
{
  "agent_id": "trend",
  "agent_name": "Trend Analyst",
  "prediction_title": "judul prediksi singkat (max 8 kata)",
  "prediction": "prediksi konkret 2-3 kalimat",
  "confidence": 75,
  "reasoning": "penjelasan singkat mengapa ini yang paling mungkin"
}"""
    },
    {
        "id": "risk",
        "name": "Risk Assessor",
        "prompt": """Kamu adalah Penilai Risiko — pessimist yang mengidentifikasi skenario terburuk dan risiko ekor (tail risks).
Berdasarkan berita yang diberikan, identifikasi apa yang bisa salah.

Kembalikan HANYA JSON (tanpa teks lain):
{
  "agent_id": "risk",
  "agent_name": "Risk Assessor",
  "prediction_title": "judul prediksi singkat (max 8 kata)",
  "prediction": "prediksi konkret 2-3 kalimat",
  "confidence": 60,
  "reasoning": "penjelasan singkat mengapa ini yang paling mungkin"
}"""
    },
    {
        "id": "optimist",
        "name": "Optimist",
        "prompt": """Kamu adalah Optimis — analis yang mengidentifikasi katalis positif dan jendela peluang.
Berdasarkan berita yang diberikan, prediksi skenario terbaik yang realistis.

Kembalikan HANYA JSON (tanpa teks lain):
{
  "agent_id": "optimist",
  "agent_name": "Optimist",
  "prediction_title": "judul prediksi singkat (max 8 kata)",
  "prediction": "prediksi konkret 2-3 kalimat",
  "confidence": 65,
  "reasoning": "penjelasan singkat mengapa ini yang paling mungkin"
}"""
    },
    {
        "id": "history",
        "name": "Historical Analogist",
        "prompt": """Kamu adalah Analis Sejarah — pakar yang menemukan analog historis dan pola siklus.
Berdasarkan berita yang diberikan, temukan peristiwa serupa dari sejarah dan prediksi berdasarkan preseden tersebut.

Kembalikan HANYA JSON (tanpa teks lain):
{
  "agent_id": "history",
  "agent_name": "Historical Analogist",
  "prediction_title": "judul prediksi singkat (max 8 kata)",
  "prediction": "prediksi konkret 2-3 kalimat, sebutkan preseden historis",
  "confidence": 70,
  "reasoning": "analog historis mana yang paling relevan dan mengapa"
}"""
    },
    {
        "id": "systems",
        "name": "Systems Thinker",
        "prompt": """Kamu adalah Pemikir Sistem — analis yang memetakan efek lanjutan (second-order effects) dan konsekuensi berantai.
Berdasarkan berita yang diberikan, prediksi dampak tidak langsung yang sering terlewat.

Kembalikan HANYA JSON (tanpa teks lain):
{
  "agent_id": "systems",
  "agent_name": "Systems Thinker",
  "prediction_title": "judul prediksi singkat (max 8 kata)",
  "prediction": "prediksi konkret 2-3 kalimat tentang efek lanjutan",
  "confidence": 68,
  "reasoning": "mekanisme sebab-akibat yang menjelaskan prediksi ini"
}"""
    },
]
```

**`run_news_gatherer(event: str) -> dict`**
- Tools: `get_recent_news` from `tools/news_tools.py`
- System prompt: Indonesian news analyst, collects 5–8 recent news items
- User message: `f"Cari berita terkini tentang: {event}"`
- Output: `{"news": [{"headline": ..., "source": ..., "date": ..., "summary": ...}]}`

```python
_GATHERER_PROMPT = """Kamu adalah NewsGatherer — analis berita yang mengumpulkan berita terkini dari berbagai sumber.
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
```

**`run_predictor(predictor: dict, event: str, news_summary: str) -> dict`**
- Tools: none (pure LLM reasoning)
- System prompt: `predictor["prompt"]`
- User message: includes event + formatted news_summary

```python
def run_predictor(predictor: dict, event: str, news_summary: str) -> dict:
    agent = build_agent(predictor["prompt"], [])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Topik: {event}\n\nBerita terkini:\n{news_summary}\n\nBerikan prediksimu."}]
    })
    return _parse_json_output(result)
```

**`run_council(event: str, predictions: list) -> dict`**
- Tools: `save_prophecy` from `tools/nostradamus_tools.py`
- System prompt: council/judge persona
- User message: formatted string with all 5 predictions + event

```python
_COUNCIL_PROMPT = """Kamu adalah Dewan Peramal — majelis hakim yang menimbang 5 prediksi dari perspektif berbeda dan menetapkan vonis.
Gunakan tool save_prophecy untuk menyimpan vonis ke vault.

Kembalikan HANYA JSON (tanpa teks lain):
{
  "verdict_title": "judul vonis singkat (max 8 kata)",
  "verdict_detail": "vonis konkret 3-4 kalimat — prediksi paling mungkin dan alasannya",
  "confidence": 75,
  "endorsed_agent": "nama agen yang prediksinya paling akurat",
  "dissenting_view": "1 kalimat tentang sudut pandang yang berbeda yang patut dipertimbangkan"
}
"""

def run_council(event: str, predictions: list) -> dict:
    from tools.nostradamus_tools import save_prophecy
    agent = build_agent(_COUNCIL_PROMPT, [save_prophecy])
    preds_text = "\n\n".join(
        f"[{p.get('agent_name', '?')}]\nPrediksi: {p.get('prediction_title', '')}\n{p.get('prediction', '')}\nKepercayaan: {p.get('confidence', '?')}%"
        for p in predictions
    )
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Topik: {event}\n\n5 Prediksi:\n\n{preds_text}\n\nTetapkan vonis dan simpan ke vault."}]
    })
    return _parse_json_output(result)
```

### 2. `tools/nostradamus_tools.py` (NEW)

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
    content = f"# Nostradamus Prophecy\n\n**Topik:** {topic}\n\n**Vonis:**\n{verdict}\n\n**Tanggal:** {ts}\n"
    fname.write_text(content, encoding="utf-8")
    return f"Saved to {fname}"
```

### 3. `tests/test_nostradamus_pipeline.py` (NEW)

5 TDD tests following `tests/test_davinci_pipeline.py` mock pattern (patches `agents.nostradamus_pipeline.build_agent`):

```python
from unittest.mock import patch, MagicMock
from agents.nostradamus_pipeline import run_news_gatherer, run_predictor, run_council, PREDICTORS
import json

def _mock_agent(response_json: dict):
    """Build a mock agent that returns a single AI message with JSON content."""
    msg = MagicMock()
    msg.content = json.dumps(response_json)
    agent = MagicMock()
    agent.invoke.return_value = {"messages": [msg]}
    return agent

def test_run_news_gatherer_returns_news():
    expected = {"news": [{"headline": "Test", "source": "BBC", "date": "2026-05-26", "summary": "Summary"}]}
    with patch("agents.nostradamus_pipeline.build_agent", return_value=_mock_agent(expected)):
        result = run_news_gatherer("US-China trade war")
    assert "news" in result
    assert isinstance(result["news"], list)
    assert result["news"][0]["headline"] == "Test"

def test_run_predictor_returns_prediction_keys():
    expected = {
        "agent_id": "trend", "agent_name": "Trend Analyst",
        "prediction_title": "Trade tensions escalate",
        "prediction": "Tariffs will increase.", "confidence": 72, "reasoning": "Pattern analysis"
    }
    with patch("agents.nostradamus_pipeline.build_agent", return_value=_mock_agent(expected)):
        result = run_predictor(PREDICTORS[0], "US-China trade war", "News summary here")
    for key in ("agent_id", "agent_name", "prediction_title", "prediction", "confidence", "reasoning"):
        assert key in result

def test_run_council_returns_verdict_keys():
    expected = {
        "verdict_title": "Trade war intensifies",
        "verdict_detail": "Council verdict here.", "confidence": 75,
        "endorsed_agent": "Trend Analyst", "dissenting_view": "Risk Assessor disagrees."
    }
    with patch("agents.nostradamus_pipeline.build_agent", return_value=_mock_agent(expected)):
        result = run_council("US-China trade war", [{"agent_name": "Trend Analyst", "prediction_title": "test", "prediction": "test", "confidence": 70}])
    for key in ("verdict_title", "verdict_detail", "confidence", "endorsed_agent", "dissenting_view"):
        assert key in result

def test_run_predictor_handles_unparseable_response():
    msg = MagicMock()
    msg.content = "Maaf, saya tidak bisa memproses ini."
    agent = MagicMock()
    agent.invoke.return_value = {"messages": [msg]}
    with patch("agents.nostradamus_pipeline.build_agent", return_value=agent):
        result = run_predictor(PREDICTORS[0], "test event", "test news")
    assert "error" in result

def test_run_council_handles_unparseable_response():
    msg = MagicMock()
    msg.content = "Tidak bisa memproses prediksi."
    agent = MagicMock()
    agent.invoke.return_value = {"messages": [msg]}
    with patch("agents.nostradamus_pipeline.build_agent", return_value=agent):
        result = run_council("test event", [])
    assert "error" in result
```

### 4. `server.py` (MODIFY)

**3 changes:**

1. Add `Path("static/nostradamus").mkdir(exist_ok=True)` near the static dir setup (after the `static/davinci` line).

2. Insert `/nostradamus` page route (after the Da Vinci page route, before Najwa):

```python
# ── Nostradamus Prophetic Page ────────────────────────────────────────────────

@app.get("/nostradamus")
@app.get("/nostradamus/")
async def nostradamus_page():
    return FileResponse("static/nostradamus/index.html", headers={"Cache-Control": "no-cache"})

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
                except Exception as e:
                    return {"agent_id": predictor["id"], "agent_name": predictor["name"],
                            "error": str(e)[:120]}

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

        except Exception as e:
            yield _sse({"event": "error", "message": str(e)})

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

class NostradamusSaveRequest(BaseModel):
    event: str
    verdict: dict  # {verdict_title, verdict_detail, confidence, endorsed_agent, dissenting_view}

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

3. Add `Path("static/nostradamus").mkdir(exist_ok=True)` in the static dir setup block.

### 5. `static/nostradamus/index.html` (NEW)

**Design:** Matches the main website (`static/index/styles.css`) exactly — NOT the simplified standalone-page tokens used by `/davinci` and `/study`. The page defines both `:root` (light) and `[data-theme="dark"]` CSS variable blocks in its own `<style>`, mirroring the exact token names and values from `static/index/styles.css`.

**CSS token set to include:**
```css
:root {
  --paper: #F3EEE5; --paper-2: #ECE6DA; --paper-3: #E4DDCD;
  --surface: #FAF6EE; --surface-2: #FFFFFF;
  --ink: #17171A; --ink-2: #3B3B3F; --ink-3: #6B6A6E; --ink-4: #9B9A9E;
  --rule: rgba(23,23,26,0.12); --rule-soft: rgba(23,23,26,0.06);
  --hover: rgba(23,23,26,0.04);
  --clay: #CC785C; --clay-soft: rgba(204,120,92,0.10);
  --hue-nostradamus: #8B5A9E;   /* deep violet */
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
  --hue-nostradamus: #A890D4;   /* soft violet — same chroma as dark hues */
  --shadow-1: 0 1px 0 rgba(0,0,0,0.3); --shadow-2: 0 4px 24px rgba(0,0,0,0.4);
}
```

**Fonts:** Same Google Fonts link as main site — `Inter:wght@400;500;600`, `Instrument+Serif:ital@0;1`, `JetBrains+Mono:wght@400;500`.

**Header:** dark strip (`background: var(--ink); color: var(--paper)`) with brand mark in Instrument Serif, `DA VINCI` → `NOSTRADAMUS` tag in `--hue-nostradamus`, dark mode toggle (sun/moon emoji or inline SVG), and `← home` link. Identical structure to `/davinci` header but using main-site tokens.

**Body:** `background: var(--paper)`, `color: var(--ink)`, `font-family: Inter`.

**Borders:** `1px solid var(--rule)`.

**Card backgrounds:** `var(--surface)` for cards, `var(--paper-2)` for subtler panels.

**Page sections (top to bottom):**

```
┌─────────────────────────────────────────────────────────────────┐
│  NOSTRADAMUS  Prophetic Intelligence    [☀/🌙]   [← home]      │  ← ink header
├─────────────────────────────────────────────────────────────────┤
│  [ Peristiwa atau topik yang sedang terjadi... ] [ PROPHESY ]   │  ← paper-2 bg, clay button
├────────────────── BERITA TERKINI ───────────────────────────────┤
│  ● "China imposes new tariffs..."  (Reuters, May 26)            │
│  ● "EU responds with counter-measures..."  (BBC)                │
├────────────────── PREDIKSI ─────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │  ← surface cards, rule borders
│  │ TREND        │  │ RISK         │  │ OPTIMIST     │          │
│  │ ANALYST      │  │ ASSESSOR     │  │              │          │
│  │  ████ 72%    │  │  ████ 60%    │  │  ████ 65%    │          │
│  │ "Escalation" │  │ "Recession"  │  │ "Resolution" │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  ┌──────────────┐  ┌──────────────┐                            │
│  │ HISTORICAL   │  │ SYSTEMS      │                            │
│  │ ANALOGIST    │  │ THINKER      │                            │
│  └──────────────┘  └──────────────┘                            │
├──────────── VONIS DEWAN ────────────────────────────────────────┤
│  "Trade war enters cold-war phase"                              │
│  [verdict detail — 3 sentences]                                 │
│  Kepercayaan: 75%  |  Didukung: Trend Analyst                  │
│  Dissent: Risk Assessor melihat risiko lebih besar.             │
│                              [ 📝 Simpan ke Notes ]             │  ← clay button
└─────────────────────────────────────────────────────────────────┘
```

**Predictor card accent colors** — muted, same chroma as main-site agent hues:

| Agent | Light color | Dark color |
|-------|-------------|------------|
| Trend Analyst | `#A68A3E` (mustard, same as `--hue-mansa`) | `#D4B86A` |
| Risk Assessor | `#A65046` (clay red, same as `--hue-lavoiser`) | `#D48278` |
| Optimist | `#5E8A7D` (teal-moss, same as `--hue-miyamoto`) | `#8FBDAF` |
| Historical Analogist | `#5E7A8A` (slate, same as `--hue-cicero`) | `#8FAEBE` |
| Systems Thinker | `#8B5A9E` → `var(--hue-nostradamus)` | `#A890D4` |

Use these as per-card `--card-accent` CSS custom properties set inline (`style="--card-accent: #A68A3E"`). The card's top border, agent label, and confidence bar use `var(--card-accent)`.

**JS namespace (`G`):**
- `G._esc(s)` — XSS escaping (same as `/davinci`: `replace /& < > "/g`)
- `G.prophesy(event)` — opens EventSource to `/api/nostradamus/prophesy?event=...`; drives all 3 phases
- `G.renderNewsItem(data)` — appends news chip to `#news-feed`
- `G.renderPrediction(data)` — finds/creates card by `data.agent_id`, fills content
- `G.renderVerdict(data)` — fills `#verdict-content`, reveals `#save-btn`; stores `G.lastVerdict`
- `G.saveToNotes()` — POST `/api/nostradamus/save` with event + `G.lastVerdict`

**Section visibility:** News section hidden until first `news_item` event. Predictions section hidden until first `prediction` event. Verdict section hidden until `verdict` event. Sections revealed with CSS class toggle (no `display:none` inline).

**Skeleton cards:** Show 5 pulsing skeleton placeholders in the predictions grid as soon as `news_done` fires. Replace each skeleton with the real content when its `prediction` event arrives.

### 6. `static/index/data.jsx` (MODIFY)

Add `nostradamus` as a new entry in the `AGENTS` object:

```javascript
nostradamus: {
  name: 'Nostradamus', sub: 'Prophetic Intelligence', hue: 'var(--hue-nostradamus)',
  issue: 'XII.', cluster: 'research', url: '/nostradamus',
  tagline: 'Five minds, one verdict — predicting what current events foretell.',
  greeting: 'Name the event. Five prophets will read the signs.',
  Ico: () => { const {IcoSparkle} = window.Icons; return <IcoSparkle/>; },
},
```

Add `'nostradamus'` to `AGENT_ORDER` after `'orwell'`.

Add `--hue-nostradamus: #8B5A9E;` to the CSS variables in `static/index/styles.css` (near the other `--hue-*` lines).

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Empty event | HTTP 400 before stream opens |
| Event > 200 chars | HTTP 400 |
| NewsGatherer fails to parse | `{"news": []}` fallback, `news_done` with count 0, predictors still run with empty summary |
| Individual predictor fails | `safe_predict` wrapper catches, emits `prediction` with `error` key, others continue |
| All predictors fail | Council receives empty list, may produce fallback verdict |
| Council parse failure | `_parse_json_output` returns `{"error": ...}`, emitted as `verdict` event, frontend shows error state |
| SSE drop | Frontend shows "Koneksi terputus." — user can retry |
| `save_prophecy` failure inside Council | Non-fatal — tool errors don't stop the agent |

---

## Files to Create / Modify

| File | Action |
|------|--------|
| `agents/nostradamus_pipeline.py` | CREATE — `PREDICTORS`, `run_news_gatherer`, `run_predictor`, `run_council` |
| `tools/nostradamus_tools.py` | CREATE — `save_prophecy` tool |
| `tests/test_nostradamus_pipeline.py` | CREATE — 5 TDD tests |
| `server.py` | MODIFY — `/nostradamus` route, `/api/nostradamus/prophesy`, `/api/nostradamus/save`, mkdir |
| `static/nostradamus/index.html` | CREATE — 3-phase UI |
| `static/index/data.jsx` | MODIFY — add `nostradamus` entry + `AGENT_ORDER` |
| `static/index/styles.css` | MODIFY — add `--hue-nostradamus` CSS variable |

---

## Verification

```powershell
# 1. Unit tests
$env:PYTHONUTF8=1; pytest tests/test_nostradamus_pipeline.py -v
# Expected: 5 passed

# 2. Regression — existing tests still pass
$env:PYTHONUTF8=1; pytest tests/test_stock_screener.py tests/test_study_agents.py tests/test_davinci_pipeline.py -v

# 3. Server imports OK
$env:PYTHONUTF8=1; python -c "import server; print('OK')"

# 4. End-to-end
$env:PYTHONUTF8=1; python server.py
# Open http://localhost:8000/nostradamus
# Type "US-China trade war" → PROPHESY
# Phase 1: verify 5-8 news chips stream in
# Phase 2: verify 5 skeleton cards appear, fill in as each predictor finishes (not all at once)
# Phase 3: verify Council verdict appears, confidence + endorsed agent + dissent shown
# Click "Simpan ke Notes" → verify note in Cicero (http://localhost:8000/study)
# Open http://localhost:8000 → verify Nostradamus appears in sidebar under Research cluster
# Click Nostradamus in sidebar → verify /nostradamus page opens

# 5. Check vault save
# After a run, verify AI Data/Nostradamus Agent/prophecy_YYYY-MM-DD_HH-MM.md created
```
