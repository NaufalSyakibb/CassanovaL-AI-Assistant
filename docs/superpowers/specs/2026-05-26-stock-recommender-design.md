# Stock Recommender — Design Spec

**Date:** 2026-05-26  
**Status:** Approved

---

## Goal

Add a **★ PICKS** tab to the existing CassanovaL stock terminal (`/stock`) that automatically scans curated watchlists of underrated/undervalued stocks per region (US / Asia / IDX) and surfaces the top 8 ranked by conviction score — without removing or altering any existing terminal feature.

---

## Architecture

### Pipeline

```
Terminal page loads
    ↓
JS: auto-trigger GET /api/stock/picks?region=us  (EventSource, background)
    ↓
Server: iterate WATCHLISTS["us"] (~15 tickers) in asyncio batches of 3
    For each ticker:
        run_pick_screener(ticker)
            → get_market_data(ticker)           — real P/E, ROE, revenue growth, financials
            → get_technical_indicators(ticker)  — RSI, MACD, support/resistance
            → LLM: score as underrated buy/watch/skip
        → emit SSE: pick_result {ticker, verdict, conviction_score, rationale, ...}
    ↓
Frontend: table fills live, re-sorts by conviction after each result
Top 8 BUY + WATCH shown (SKIP hidden)
    ↓
User clicks "ANALYZE →" → auto-fills ticker input → triggers existing 6-agent pipeline
```

### Why a dedicated screener agent, not the full 6-agent pipeline

Running all 6 agents per stock × 15 stocks = 90 LLM calls (~30 min, high cost). The screener agent uses the same real data tools (`get_market_data` + `get_technical_indicators`) as the first phases of the full pipeline, delivers data-grounded scores in ~40-60 seconds total, and routes the user to the full deep analysis for any pick they care about.

---

## Agent

### `run_pick_screener(ticker: str) -> dict`

**File:** `agents/stock_screener.py`

**Tools:** `get_market_data`, `get_technical_indicators`

**System prompt (Indonesian):**
> Kamu adalah analis saham yang mencari saham underrated dan undervalued dengan fundamental kuat yang diabaikan pasar. Kamu menerima data fundamental dan teknikal dari tools, lalu menilai apakah saham ini layak dibeli berdasarkan valuasi, momentum, dan katalis pertumbuhan. Fokus pada saham yang BUKAN mega-cap terkenal — cari hidden gems dengan P/E rendah, pertumbuhan stabil, dan potensi apresiasi tinggi.

**Output schema:**
```json
{
  "verdict": "BUY | WATCH | SKIP",
  "conviction_score": 8,
  "rationale": "1-2 kalimat mengapa saham ini underrated dan layak beli",
  "key_catalyst": "faktor utama yang bisa mendorong kenaikan harga",
  "risk_factor": "risiko utama yang perlu diperhatikan",
  "pe_ratio": 11.2,
  "rsi": 42.1
}
```

### Watchlists (curated, underrated focus — no mega-caps)

```python
WATCHLISTS = {
    "us": [
        "NUE", "DVN", "JAZZ", "OXY", "SLB",
        "CROX", "MTB", "GXO", "URI", "FHN",
        "CELH", "EXAS", "PERI", "TRIP", "ADMA"
    ],
    "asia": [
        "6501.T", "000270.KS", "6902.T", "INFY", "HDB",
        "2303.TW", "005380.KS", "JD", "BIDU", "9984.T"
    ],
    "idx": [
        "ITMG.JK", "MDKA.JK", "SIDO.JK", "CPIN.JK", "MAPI.JK",
        "ACES.JK", "SMGR.JK", "KLBF.JK", "ICBP.JK", "BBNI.JK",
        "BMRI.JK", "PTBA.JK", "ERAA.JK", "INDF.JK", "EMTK.JK"
    ],
}
```

---

## API Endpoint

### `GET /api/stock/picks?region=us|asia|idx`

SSE stream. Auto-triggered by the frontend on page load (default region: `us`). Also triggered when user switches region tabs.

**Validation:**
- Unknown region → emit `error`, close stream
- Empty watchlist → emit `error`, close stream

**Execution:**
- Runs `run_pick_screener` for each ticker in `WATCHLISTS[region]`
- Batches of 3 concurrent tickers via `asyncio.gather` to stay within Mistral rate limits
- Individual ticker failure → emit `pick_result` with `verdict: "ERROR"`, continue
- After all tickers processed → emit `picks_done`

### SSE Events

| Event | Payload | When |
|-------|---------|------|
| `picks_start` | `{region, total}` | Before first batch |
| `pick_result` | `{ticker, verdict, conviction_score, rationale, key_catalyst, risk_factor, pe_ratio, rsi}` | After each ticker |
| `picks_done` | `{region, count}` | After all tickers |
| `error` | `{message}` | On failure |

---

## Frontend Changes

**File:** `static/stock/CassanovaL Terminal v2.html`

### 1. New PICKS tab button

Add `<button class="tbtn" data-t="picks">★ PICKS</button>` alongside existing tab buttons (Summary, Strategy, Technicals, Charts, Verdict, Code).

### 2. PICKS tab content panel (`id="tc-picks"`)

```
┌─────────────────────────────────────────────────────┐
│  REGION: [US] [ASIA] [IDX]           ↻ refresh      │
├─────────────────────────────────────────────────────┤
│  #  TICKER  SECTOR  RATIONALE  CONV.  P/E  RSI  [→] │
├─────────────────────────────────────────────────────┤
│  1  DVN     Energy  Low P/E... 9/10   8.7  42   →   │  ← BUY (green tint)
│  2  NUE     Steel   Underval.. 8/10   11.2 38   →   │  ← BUY (green tint)
│  3  JAZZ    Health  Cheap va.. 7/10   7.1  55   →   │  ← WATCH (amber tint)
│     ...streaming...                                  │
└─────────────────────────────────────────────────────┘
```

**Table behavior:**
- Rows stream in as each `pick_result` SSE event arrives
- Table re-sorts by `conviction_score` descending after each new row
- Only `BUY` and `WATCH` verdicts shown (max 8 rows); `SKIP` and `ERROR` hidden
- `BUY` rows: dark green tint background; `WATCH` rows: dark amber tint
- While analyzing: a subtle "Menganalisis N/M saham..." status line below the table

### 3. "ANALYZE →" button behavior

Clicking the button in any row:
1. Sets the ticker input value (top of terminal) to that row's ticker
2. Programmatically clicks the existing ANALYZE button
3. Switches to the SUMMARY tab so the user sees the pipeline start

### 4. Auto-trigger on page load

```javascript
// On DOMContentLoaded — start US picks in background
G.loadPicks('us');
```

`G.loadPicks(region)`:
- Opens `EventSource('/api/stock/picks?region=' + region)`
- Caches results in `G.picksCache[region]`
- If region already cached, renders from cache (no new request)
- Region toggle buttons trigger `G.loadPicks(region)` if not cached

### 5. Refresh button

Force-clears `G.picksCache[region]` and re-opens the SSE stream for the current region.

---

## Files to Create / Modify

| File | Action |
|------|--------|
| `agents/stock_screener.py` | CREATE — `run_pick_screener` + `WATCHLISTS` dict + shared helpers |
| `tests/test_stock_screener.py` | CREATE — TDD test for `run_pick_screener` |
| `server.py` | MODIFY — add `GET /api/stock/picks` SSE endpoint |
| `static/stock/CassanovaL Terminal v2.html` | MODIFY — PICKS tab button, tab panel, auto-trigger, SSE handlers |

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Unknown region | Emit `error` event, close stream |
| Individual ticker failure | Emit `pick_result` with `verdict: "ERROR"`, skip in UI, continue |
| All tickers return SKIP | Table shows "Tidak ada rekomendasi saat ini untuk region ini." |
| SSE connection drops | Frontend shows "Koneksi terputus." with retry button |
| `get_market_data` returns error dict | Screener agent receives it, likely outputs SKIP — graceful |

---

## Verification

```powershell
# 1. Unit test
$env:PYTHONUTF8=1; pytest tests/test_stock_screener.py -v

# 2. Server imports OK
$env:PYTHONUTF8=1; python -c "import server; print('OK')"

# 3. Smoke test — screener agent standalone
$env:PYTHONUTF8=1; python -c "
from agents.stock_screener import run_pick_screener
import json
result = run_pick_screener('DVN')
print(json.dumps(result, indent=2, ensure_ascii=False))
"

# 4. End-to-end
$env:PYTHONUTF8=1; python server.py
# Open http://localhost:8000/stock
# Verify PICKS tab appears alongside existing tabs
# Verify US picks start loading automatically on page open
# Verify table rows stream in and sort by conviction
# Verify clicking ANALYZE → fills ticker and triggers pipeline
# Verify switching region (ASIA, IDX) triggers new analysis
# Verify refresh button re-fetches

# 5. Regression — all existing tests still pass
$env:PYTHONUTF8=1; pytest tests/test_stock_tools.py tests/test_stock_agents.py tests/test_study_agents.py -v
```
