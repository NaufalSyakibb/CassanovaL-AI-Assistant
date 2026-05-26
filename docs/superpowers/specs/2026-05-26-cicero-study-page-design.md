# Cicero Study Page — Design Spec

**Date:** 2026-05-26  
**Status:** Approved

---

## Goal

A dedicated study page at `/study` where the user types a topic and a 3-agent Mistral pipeline generates a complete Cornell Notes-style study guide: full material, key concepts, and summary — displayed simultaneously in a paper-and-ink layout.

---

## Architecture

### Pipeline (Sequential SSE)

```
User types topic → POST /api/study/generate (SSE)
        ↓
Phase 1 — MateriAgent(topic)
        → mistral-large-latest
        → generates comprehensive material in titled sections
        → emits SSE: step(MateriAgent, running/done), materi(data)
        ↓
Phase 2 — KonsepAgent(topic, materi_text)
        → mistral-large-latest
        → extracts key concepts FROM the generated material
        → emits SSE: step(KonsepAgent, running/done), konsep(data)
        ↓
Phase 3 — RingkasanAgent(topic, materi_text, konsep_text)
        → mistral-large-latest
        → writes a concise summary synthesizing material + concepts
        → emits SSE: step(RingkasanAgent, running/done), ringkasan(data)
        ↓
        complete
```

### Agent Output Schemas

```json
// MateriAgent
{
  "sections": [
    { "title": "string", "content": "string (markdown prose)" }
  ]
}

// KonsepAgent
{
  "concepts": [
    { "term": "string", "definition": "string (1–2 sentences)" }
  ]
}

// RingkasanAgent
{
  "summary": "string (3–5 sentences, italic serif prose)"
}
```

### SSE Events

| Event | Payload | When |
|-------|---------|------|
| `step` | `{agent, status: running\|done}` | On each phase transition |
| `log` | `{text}` | Progress messages |
| `materi` | `{sections: [...]}` | After Phase 1 |
| `konsep` | `{concepts: [...]}` | After Phase 2 |
| `ringkasan` | `{summary: "..."}` | After Phase 3 |
| `error` | `{message}` | On failure |

---

## UI Layout — Cornell Classic

```
┌─────────────────────────────────────────────────────────────┐
│  HEADER: "Cicero · STUDY"  [dark bar]       ← CassanovaL   │
├─────────────────────────────────────────────────────────────┤
│  INPUT BAR: [topic text input]              [BELAJAR →]     │
├─────────────────────────────────────────────────────────────┤
│  AGENT STRIP: ● MateriAgent → ● KonsepAgent → ● RingkasanAgent │
├──────────────────┬──────────────────────────────────────────┤
│  KONSEP KUNCI    │  MATERI LENGKAP                          │
│  (Agent 2)       │  (Agent 1)                               │
│  ~280px fixed    │  flex: 1                                 │
│                  │                                          │
│  term: def       │  ## Section Title                        │
│  term: def       │  Prose content...                        │
│  term: def       │                                          │
├──────────────────┴──────────────────────────────────────────┤
│  RINGKASAN  (Agent 3) — full width, italic serif            │
├─────────────────────────────────────────────────────────────┤
│                              [Simpan ke Catatan]            │
└─────────────────────────────────────────────────────────────┘
```

**Column mapping:**
- Left cue column (280px) ← KonsepAgent output (fills in during Phase 2)
- Right notes column (flex) ← MateriAgent output (fills in during Phase 1)
- Bottom summary bar ← RingkasanAgent output (fills in during Phase 3)

---

## Design System

Matches `static/finance/index.html` — "Paper & Ink" aesthetic:

| Token | Value |
|-------|-------|
| Background | `#EDE8DF` |
| Surface / paper | `#F3EEE5` |
| White card | `#FFFFFF` |
| Ink (primary text) | `#17171A` |
| Ink 2 (secondary) | `#3B3B3F` |
| Gold accent | `#A68A3E` |
| Clay / CTA | `#CC785C` |
| Green (done) | `#5E8A6A` |
| Border | `#C8C0B2` |
| Fonts | `Instrument Serif` (headings), `Inter` (body), `JetBrains Mono` (badges) |

Agent status dots: grey = idle, amber pulse = running, green = done.

---

## Files to Create / Modify

| File | Action |
|------|--------|
| `agents/study_agents.py` | CREATE — 3 agent functions + prompts |
| `static/study/index.html` | CREATE — full standalone page |
| `server.py` | MODIFY — add `GET /study`, `GET /api/study/generate` (SSE), `POST /api/study/save` |
| `tests/test_study_agents.py` | CREATE — tests for all 3 functions |

---

## Agent Prompts (Bahasa Indonesia)

### MateriAgent
- Role: Ahli pendidikan yang membuat materi belajar komprehensif
- Input: topic string in user message
- Output: JSON `{sections: [{title, content}]}` — 3–5 sections, each 100–200 words
- Style: Jelas, terstruktur, dengan contoh konkret dan konteks

### KonsepAgent
- Role: Analis konsep yang membaca materi dan mengekstrak poin penting
- Input: topic + full materi text
- Output: JSON `{concepts: [{term, definition}]}` — 6–12 concepts
- Rule: Semua konsep HARUS berasal dari materi yang diberikan, tidak mengarang

### RingkasanAgent
- Role: Editor akademik yang menulis ringkasan komprehensif
- Input: topic + materi text + konsep list
- Output: JSON `{summary: "..."}` — 3–5 kalimat, mencakup semua poin penting
- Style: Mengalir, informatif, bahasa Indonesia formal

---

## API Endpoints

### `GET /study`
Serves `static/study/index.html` with `Cache-Control: no-cache`.

### `GET /api/study/generate?topic=<topic>`
SSE stream. Opens EventSource in the browser. Runs the 3-agent pipeline sequentially.

**Error handling:**
- Empty topic → immediately emit `error` event, close stream
- Agent failure → emit `error` event, continue remaining agents with empty context (`{}`)
- Individual section graceful degradation: failed agent emits empty data, page shows "—"

### `POST /api/study/save`
Body: `{topic, materi, konsep, ringkasan}`  
Action: Creates a new note in `data/notes.json` with title = topic, content = formatted Cornell Notes text, tags = `["study", "cicero"]`.  
**Never overwrites existing notes** — always appends a new entry with a new UUID.  
Returns: `{id, title}` of the saved note.

---

## Navigation Integration

- `static/index/data.jsx` — add "Study Mode" button in the Cicero agent panel (links to `/study`)  
- OR: the existing chat with Cicero can suggest `/study` when a study topic is detected

Simplest approach: add a small "Study Mode →" link in the main dashboard sidebar entry for Cicero agent. No routing changes needed beyond adding the link.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Empty topic submitted | Frontend blocks submission, shows inline error |
| MateriAgent fails | Materi section shows "Gagal memuat materi", KonsepAgent + RingkasanAgent proceed with empty context |
| KonsepAgent fails | Konsep column shows "—", RingkasanAgent still runs with materi only |
| RingkasanAgent fails | Summary bar shows "Gagal membuat ringkasan" |
| Save fails | Toast error message, data NOT lost (still visible on page) |

---

## Verification

```powershell
# 1. Unit tests
$env:PYTHONUTF8=1; pytest tests/test_study_agents.py -v

# 2. Server loads
$env:PYTHONUTF8=1; python -c "import server; print('OK')"

# 3. Manual smoke test
$env:PYTHONUTF8=1; python server.py
# Open http://localhost:8000/study
# Type "Fotosintesis" → click BELAJAR
# Verify: 3 agents animate through running → done states
# Verify: Materi fills right column, Konsep fills left, Ringkasan fills bottom
# Verify: Save button creates note in data/notes.json

# 4. Resilience
# Submit empty topic → button should be disabled / show error
```
