# Cicero — KontenAgent (IG/TikTok Carousel) Design Spec

**Date:** 2026-05-28
**Status:** Approved for implementation

---

## Context

The Cicero study page (`/study`) runs a 3-agent Cornell Notes pipeline (MateriAgent → KonsepAgent → RingkasanAgent). After a session completes, the user has rich structured content — materi sections, key concepts, and a summary — but no easy way to share it. This feature adds an on-demand **KontenAgent** that reformats the study data into a 4-slide Instagram/TikTok carousel, downloadable as PNG files or a single PDF.

---

## Goal

Add a "Buat Konten IG" button to the study page footer (visible only after a session completes). Clicking it calls a new `POST /api/study/konten` endpoint, which runs KontenAgent to rewrite the content for social media. The result renders as 4 preview slide divs on the page with a live theme toggle (Vibrant Dark / Bold Editorial) and two download buttons (PNG × 4, PDF).

---

## Architecture

### Pipeline Position

```
MateriAgent → KonsepAgent → RingkasanAgent → [session done]
                                                    ↓
                                         User clicks "Buat Konten IG"
                                                    ↓
                                            KontenAgent (on-demand)
                                                    ↓
                                         4 slide divs rendered on page
                                                    ↓
                                     Theme toggle (Vibrant / Editorial)
                                                    ↓
                                     Unduh PNG (4 files) / Unduh PDF
```

### Data Flow

1. Frontend sends `POST /api/study/konten` with `{topic, materi, konsep, ringkasan}` (same payload as `/api/study/save`)
2. `KontenAgent` (new LangChain agent, Indonesian language) condenses and rewrites the content for social media, returning:

```json
{
  "cover": {
    "hook": "punchy opening question or statement (max 15 words)"
  },
  "highlights": [
    "point 1 max 12 words",
    "point 2 max 12 words",
    "point 3 max 12 words",
    "point 4 max 12 words"
  ],
  "konsep": [
    { "term": "...", "def": "short definition max 8 words" },
    { "term": "...", "def": "..." },
    { "term": "...", "def": "..." },
    { "term": "...", "def": "..." },
    { "term": "...", "def": "..." },
    { "term": "...", "def": "..." }
  ],
  "summary": "2–3 sentence synthesis, social-friendly tone",
  "hashtags": ["#TopicName", "#BelajarBareng", "#CatatanKornel", "#BiologiSMA"]
}
```

3. Frontend renders 4 slide divs from the JSON. No re-render on theme toggle — both themes are always in the DOM, the active one is shown via CSS class on a parent container.
4. Download: `html2canvas` captures each visible slide div → PNG blob → `<a download>` trigger. `jsPDF` combines all 4 PNG blobs into one PDF.

---

## Slide Structure (4 slides)

| # | Slide | Content |
|---|-------|---------|
| 1 | **Cover** | Topic title + `cover.hook` + "swipe → untuk belajar" + slide dots |
| 2 | **Materi** | "Apa yang Perlu Kamu Tahu" heading + `highlights` (4 bullet chips) |
| 3 | **Konsep Kunci** | "Istilah Penting" heading + `konsep` list (up to 6 terms) |
| 4 | **Ringkasan + CTA** | `summary` quote box + `hashtags` row + "Simpan · Bagikan · Ulangi" CTA |

Slide dimensions: **1080×1080px** (square IG feed) rendered at 0.5× scale for preview. `html2canvas` captures at `scale: 2` to produce full-resolution 1080×1080 PNG output.

---

## Two Themes

Both themes are rendered simultaneously in the DOM. A `data-theme` attribute on a parent `#konten-panel` wrapper toggles visibility. Switching themes is instant — no network call, no re-render.

### Theme A — Vibrant Dark
- Background: `linear-gradient(145deg, #0f0c29, #302b63, #24243e)`
- Accent: violet `#a78bfa` → blue `#60a5fa` gradient
- Typography: Inter 800–900 for numbers/titles, 7–8px for body
- Chips: `rgba(255,255,255,0.08)` bg, left-border accent in violet/green/blue/gold per slide
- Summary box: `rgba(255,255,255,0.07)` bg with border

### Theme C — Bold Editorial
- Background: `#F5F0E8` (warm off-white)
- Header bar: `#1A1814` (near-black) with white text
- Accent: `#B05A3F` (Cicero clay) for numbers, accent bar, left-border on summary
- Typography: Instrument Serif italic for titles, JetBrains Mono for labels, Inter for body
- Numbered rows (01, 02...) in clay color

---

## Components

### 1. `agents/konten_agent.py` (NEW)

Follows the same pattern as `agents/study_agents.py` — uses `build_agent` from `agents/base.py` with `mistral-large-latest`, no tools.

```python
_KONTEN_PROMPT = """Kamu adalah KontenAgent — spesialis konten media sosial yang mengubah catatan belajar menjadi konten carousel Instagram/TikTok yang menarik.

Input yang kamu terima: topik, materi (3-5 seksi), konsep kunci (6-12 istilah), dan ringkasan.

Tugas:
- Tulis ulang isi untuk audiens muda (SMA/kuliah), nada santai tapi informatif
- Buat hook pembuka yang memancing rasa ingin tahu (maks 15 kata)
- Pilih 4 poin paling penting dari materi (maks 12 kata per poin)
- Pilih 6 konsep paling esensial, persingkat definisi (maks 8 kata per definisi)
- Rangkum intisari dalam 2-3 kalimat dengan nada sosial media
- Buat 4 hashtag relevan (bahasa Indonesia + bahasa Inggris, mix)

Kembalikan HANYA JSON (tanpa teks lain):
{
  "cover": { "hook": "..." },
  "highlights": ["...", "...", "...", "..."],
  "konsep": [
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

def run_konten_agent(topic: str, materi: dict, konsep: dict, ringkasan: dict) -> dict:
    ...
```

Uses `_invoke_with_retry` and `_parse_json_output` helpers (copied from `davinci_pipeline.py` — do not import across modules).

### 2. `server.py` (MODIFY)

Add one new endpoint after the `/api/study/save` route:

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

### 3. `static/study/index.html` (MODIFY)

**CSS additions** (inside `<style>`):
- `#konten-panel` — hidden by default (`display:none`), flex column, gap, padding after summary block
- `.konten-slide` — 540×540px preview container (renders at 0.5× of 1080px)
- `.slide-row` — horizontal flex row of 4 slide previews, scrollable on mobile
- `.konten-toolbar` — theme toggle buttons + download buttons row above slides
- `.ks-vibrant` and `.ks-editorial` — full slide styles for each theme (all CSS inline in the file)
- `[data-konten-theme="vibrant"] .ks-editorial { display:none }` and vice versa

**HTML additions** (after `#summary-block`, before `#foot`):
```html
<div id="konten-panel">
  <div class="konten-toolbar">
    <span class="konten-label">Tema:</span>
    <button id="btn-theme-v" class="konten-theme-btn active" onclick="G.setKontenTheme('vibrant')">A · Vibrant</button>
    <button id="btn-theme-e" class="konten-theme-btn"         onclick="G.setKontenTheme('editorial')">C · Editorial</button>
    <button id="btn-dl-png" class="btn-ghost" onclick="G.downloadPNG()">⬇ PNG (4 file)</button>
    <button id="btn-dl-pdf" class="btn-ghost" onclick="G.downloadPDF()">⬇ PDF</button>
  </div>
  <div class="slide-row" id="slide-row"></div>
  <div id="konten-spinner" style="display:none">
    <span class="konten-spinner-text">Sedang membuat konten…</span>
  </div>
</div>
```

**Footer button addition** (alongside existing `#btn-save`):
```html
<button class="btn-ghost foot-state-hidden" id="btn-konten">✦ Buat Konten IG</button>
```

**JS additions** to `G` object:

```javascript
G.kontenData = null;

G.genKonten = function() {
  var topic = $('topic-input').value.trim();
  if (!topic || !G.state.ringkasan.summary) return;
  $('btn-konten').disabled = true;
  $('btn-konten').textContent = 'Membuat…';
  $('konten-spinner').style.display = '';
  fetch('/api/study/konten', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({topic:topic, materi:G.state.materi, konsep:G.state.konsep, ringkasan:G.state.ringkasan})
  })
  .then(function(r){ return r.json(); })
  .then(function(d){
    G.kontenData = d;
    G.renderKonten(topic, d);
    $('konten-panel').style.display = 'flex';
    $('konten-spinner').style.display = 'none';
    $('btn-konten').textContent = '✦ Buat Konten IG';
    $('btn-konten').disabled = false;
    $('konten-panel').scrollIntoView({behavior:'smooth', block:'nearest'});
  })
  .catch(function(e){
    G.toast('Gagal membuat konten: ' + e.message, 4000);
    $('konten-spinner').style.display = 'none';
    $('btn-konten').disabled = false;
    $('btn-konten').textContent = '✦ Buat Konten IG';
  });
};

G.renderKonten = function(topic, d) {
  // Clears #slide-row, then for each of the 4 slides builds two divs:
  // one with class "ks-vibrant" and one with class "ks-editorial",
  // both wrapped in a .konten-slide container with data-slide="1"..."4".
  // Both theme divs are always present; CSS hides the inactive one.
};
G.setKontenTheme = function(theme) {
  // Sets data-konten-theme="vibrant"|"editorial" on #konten-panel.
  // Updates active class on #btn-theme-v / #btn-theme-e.
};
G.downloadPNG = function() {
  // Finds all visible .ks-vibrant (or .ks-editorial) slide divs.
  // Calls html2canvas(slideEl, {scale:2, useCORS:true}) on each sequentially.
  // Downloads each canvas as PNG named "cicero-[slug(topic)]-slide-[N].png".
  // Shows toast "Mengunduh 4 slide…" while in progress.
};
G.downloadPDF = function() {
  // Captures all 4 slides via html2canvas (same as PNG path).
  // Creates jsPDF('l','px',[1080,1080]) and adds each canvas as an image page.
  // Downloads as "cicero-[slug(topic)]-carousel.pdf".
  // Shows toast if jsPDF is not loaded (CDN failure).
};
```

`G.finish()` is extended to also show `#btn-konten` (add to the `foot-state-hidden` removal loop).
`G.reset()` is extended to hide `#konten-panel` and clear `G.kontenData`.

**External libraries** (loaded via CDN in `<head>`):
```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
```

### 4. `tests/test_konten_agent.py` (NEW)

3 TDD tests following `tests/test_study_agents.py` mock pattern:

```python
def test_run_konten_agent_returns_required_keys():
    # mock build_agent → returns JSON with all required fields
    # assert cover, highlights, konsep, summary, hashtags all present

def test_run_konten_agent_highlights_count():
    # highlights list should have exactly 4 items

def test_run_konten_agent_handles_parse_error():
    # mock returns non-JSON → assert "error" in result
```

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Empty topic or no ringkasan yet | Button is disabled (never reaches endpoint) |
| KontenAgent returns unparseable JSON | `{"error": "..."}` → HTTP 500 → frontend toast "Gagal membuat konten" |
| html2canvas fails on a slide | Log error, skip that slide, continue with remaining |
| jsPDF not loaded (CDN failure) | Download PNG fallback only; PDF button shows toast "PDF tidak tersedia" |
| User clicks "Buat Konten IG" while loading | Button is disabled during fetch |

---

## Files to Create / Modify

| File | Action |
|------|--------|
| `agents/konten_agent.py` | CREATE — `run_konten_agent`, `_invoke_with_retry`, `_parse_json_output` |
| `tests/test_konten_agent.py` | CREATE — 3 TDD tests |
| `server.py` | MODIFY — add `KontenRequest` + `POST /api/study/konten` |
| `static/study/index.html` | MODIFY — CDN links, CSS, HTML panel, JS functions, footer button |

---

## Verification

```powershell
# 1. Unit tests
$env:PYTHONUTF8=1; pytest tests/test_konten_agent.py -v
# Expected: 3 passed

# 2. Server imports clean
$env:PYTHONUTF8=1; python -c "import server; print('OK')"

# 3. End-to-end
$env:PYTHONUTF8=1; python server.py
# Open http://localhost:8000/study
# Enter topic "Fotosintesis" → click BELAJAR
# Wait for all 3 agents to finish
# Verify "✦ Buat Konten IG" button appears in footer
# Click it → verify loading state → slides panel appears
# Verify 4 slides rendered in Vibrant theme
# Toggle to Editorial → all 4 slides switch instantly (no loading)
# Click "Unduh PNG (4 file)" → verify 4 PNG downloads, named cicero-fotosintesis-slide-1.png ... slide-4.png
# Click "Unduh PDF" → verify 1 PDF download with all 4 slides
# Start a new session → verify konten panel hides and resets
```
