# Stock Recommender — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a ★ PICKS tab to the existing stock terminal that auto-scans curated watchlists of underrated/undervalued stocks per region (US / Asia / IDX) and surfaces the top 8 ranked by conviction score — without altering any existing feature.

**Architecture:** A new `run_pick_screener(ticker)` agent (1 LLM call + 2 tool calls per stock) runs in background SSE batches of 3 when the terminal loads. Results stream into a ranked table inside a new PICKS tab. Clicking "ANALYZE →" auto-fills the ticker and triggers the existing 6-agent deep pipeline.

**Tech Stack:** Python (LangChain `build_agent`, `get_market_data`, `get_technical_indicators`, `asyncio.gather`), FastAPI SSE (`StreamingResponse`), vanilla JS (`EventSource`, `G` namespace pattern already in terminal).

---

## File Map

| File | Action |
|------|--------|
| `agents/stock_screener.py` | CREATE — `run_pick_screener` + `WATCHLISTS` dict + shared helpers |
| `tests/test_stock_screener.py` | CREATE — 2 TDD tests |
| `server.py` | MODIFY — add `GET /api/stock/picks` SSE endpoint after line 1489 |
| `static/CassanovaL Terminal v2.html` | MODIFY — CSS, tab button, tab panel, TABS array, G.loadPicks JS, auto-trigger |

---

## Task 1: StockScreener agent (TDD)

**Files:**
- Create: `agents/stock_screener.py`
- Create: `tests/test_stock_screener.py`

- [ ] **Step 1: Write failing tests in `tests/test_stock_screener.py`**

```python
import json
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage


def _fake_agent_result(output_dict: dict):
    return {"messages": [AIMessage(content=json.dumps(output_dict))]}


def test_run_pick_screener_returns_expected_keys():
    from agents.stock_screener import run_pick_screener
    fake_out = {
        "verdict": "BUY",
        "conviction_score": 8,
        "rationale": "Saham ini undervalued dengan P/E rendah.",
        "key_catalyst": "Permintaan baja meningkat.",
        "risk_factor": "Siklus komoditas.",
        "pe_ratio": 11.2,
        "rsi": 42.1,
    }
    with patch("agents.stock_screener.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(fake_out)
        mock_build.return_value = mock_agent
        result = run_pick_screener("NUE")

    assert result["verdict"] in ("BUY", "WATCH", "SKIP")
    assert "conviction_score" in result
    assert "rationale" in result
    assert "key_catalyst" in result
    assert "risk_factor" in result
    assert "pe_ratio" in result
    assert "rsi" in result
    assert result["ticker"] == "NUE"


def test_run_pick_screener_injects_ticker_into_result():
    from agents.stock_screener import run_pick_screener
    fake_out = {
        "verdict": "WATCH",
        "conviction_score": 6,
        "rationale": "Valuasi menarik tapi tunggu.",
        "key_catalyst": "Ekspansi pasar.",
        "risk_factor": "Kompetisi tinggi.",
        "pe_ratio": 14.5,
        "rsi": 55.0,
    }
    with patch("agents.stock_screener.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(fake_out)
        mock_build.return_value = mock_agent
        result = run_pick_screener("DVN")

    assert result["ticker"] == "DVN"
```

- [ ] **Step 2: Run tests to confirm they fail**

```powershell
$env:PYTHONUTF8=1; pytest tests/test_stock_screener.py -v
```
Expected: `ImportError: No module named 'agents.stock_screener'`

- [ ] **Step 3: Create `agents/stock_screener.py`**

```python
import json
import re
import time
from agents.base import build_agent
from tools.stock_tools import get_market_data, get_technical_indicators


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


WATCHLISTS = {
    "us": [
        "NUE", "DVN", "JAZZ", "OXY", "SLB",
        "CROX", "MTB", "GXO", "URI", "FHN",
        "CELH", "EXAS", "PERI", "TRIP", "ADMA",
    ],
    "asia": [
        "6501.T", "000270.KS", "6902.T", "INFY", "HDB",
        "2303.TW", "005380.KS", "JD", "BIDU", "9984.T",
    ],
    "idx": [
        "ITMG.JK", "MDKA.JK", "SIDO.JK", "CPIN.JK", "MAPI.JK",
        "ACES.JK", "SMGR.JK", "KLBF.JK", "ICBP.JK", "BBNI.JK",
        "BMRI.JK", "PTBA.JK", "ERAA.JK", "INDF.JK", "EMTK.JK",
    ],
}

_SCREENER_PROMPT = """Kamu adalah StockScreener Agent — analis saham yang mencari saham underrated dan undervalued dengan fundamental kuat yang diabaikan pasar.

Gunakan tool get_market_data dan get_technical_indicators untuk mengambil data saham yang diberikan. Kemudian nilai apakah saham ini layak dibeli sebagai underrated pick.

Fokus pada:
- Valuasi rendah vs fundamental (P/E rendah, P/B rendah, FCF positif)
- Pertumbuhan pendapatan stabil tapi saham masih murah
- Momentum teknikal yang belum overbought (RSI < 65 ideal)
- Bukan mega-cap yang sudah dikenal semua orang

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "verdict": "BUY atau WATCH atau SKIP",
  "conviction_score": 7,
  "rationale": "1-2 kalimat mengapa saham ini underrated dan layak beli atau diperhatikan",
  "key_catalyst": "faktor utama yang bisa mendorong kenaikan harga",
  "risk_factor": "risiko utama yang perlu diperhatikan",
  "pe_ratio": 11.2,
  "rsi": 42.1
}

verdict: BUY = sangat layak beli sekarang, WATCH = menarik tapi tunggu entry lebih baik, SKIP = tidak menarik saat ini.
conviction_score: 1-10 (10 = paling yakin).
pe_ratio dan rsi: ambil langsung dari data tool. Jika tidak tersedia, gunakan 0.
"""


def run_pick_screener(ticker: str) -> dict:
    agent = build_agent(_SCREENER_PROMPT, [get_market_data, get_technical_indicators])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Analisis saham: {ticker}"}]
    })
    parsed = _parse_json_output(result)
    parsed["ticker"] = ticker
    return parsed
```

- [ ] **Step 4: Run tests to confirm they pass**

```powershell
$env:PYTHONUTF8=1; pytest tests/test_stock_screener.py -v
```
Expected: `2 passed`

- [ ] **Step 5: Commit**

```powershell
git add agents/stock_screener.py tests/test_stock_screener.py
git commit -m "feat(picks): add StockScreener agent — underrated stock picker with TDD"
```

---

## Task 2: Server endpoint

**Files:**
- Modify: `server.py` (insert after line 1489, before `# ─── Najwa News Feed ──`)

- [ ] **Step 1: Read `server.py` lines 1487–1494 to confirm anchor**

```powershell
$env:PYTHONUTF8=1; python -c "
lines = open('server.py', encoding='utf-8').readlines()
for i, l in enumerate(lines[1485:1496], 1486):
    print(i, repr(l[:80]))
"
```
Expected: line 1489 ends the study_save function, line 1491 has `# ─── Najwa News Feed`.

- [ ] **Step 2: Insert the picks endpoint**

Find this exact text in `server.py`:

```python


# ─── Najwa News Feed ──────────────────────────────────────────────────────────
```

Replace it with:

```python


# ── Stock Picks Screener ───────────────────────────────────────────────────────

_VALID_PICK_REGIONS = {"us", "asia", "idx"}

@app.get("/api/stock/picks")
async def stock_picks(region: str = "us"):
    region = region.lower()
    if region not in _VALID_PICK_REGIONS:
        raise HTTPException(status_code=400, detail=f"Unknown region: {region}. Valid: us, asia, idx")

    async def generate():
        from agents.stock_screener import run_pick_screener, WATCHLISTS
        tickers = WATCHLISTS.get(region, [])
        if not tickers:
            yield _sse({"event": "error", "message": f"No watchlist for region: {region}"})
            return

        yield _sse({"event": "picks_start", "region": region, "total": len(tickers)})
        loop = asyncio.get_running_loop()
        count = 0

        for i in range(0, len(tickers), 3):
            batch = tickers[i:i + 3]
            tasks = [_run_agent(loop, run_pick_screener, t) for t in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for ticker, result in zip(batch, results):
                if isinstance(result, Exception):
                    yield _sse({"event": "pick_result", "ticker": ticker, "verdict": "ERROR",
                                "conviction_score": 0, "rationale": str(result)[:120],
                                "key_catalyst": "", "risk_factor": "", "pe_ratio": 0, "rsi": 0})
                else:
                    result["ticker"] = ticker
                    yield _sse({"event": "pick_result", **result})
                count += 1

        yield _sse({"event": "picks_done", "region": region, "count": count})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ─── Najwa News Feed ──────────────────────────────────────────────────────────
```

- [ ] **Step 3: Verify server imports OK**

```powershell
$env:PYTHONUTF8=1; python -c "import server; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```powershell
git add server.py
git commit -m "feat(picks): add /api/stock/picks SSE endpoint — 3-region screener pipeline"
```

---

## Task 3: PICKS tab in the stock terminal

**Files:**
- Modify: `static/CassanovaL Terminal v2.html`

This task has 5 distinct edits in sequence. Read the file before each edit.

### Edit A — CSS (after the `/* ── CODE TAB ── */` block, around line 272)

Find this exact line in the `<style>` block:

```css
.kw{color:#c792ea}.str{color:#c3e88d}.cm{color:var(--border2);font-style:italic}.num{color:var(--yellow)}
```

Replace it with:

```css
.kw{color:#c792ea}.str{color:#c3e88d}.cm{color:var(--border2);font-style:italic}.num{color:var(--yellow)}

/* ── PICKS TAB ── */
#tc-picks{flex-direction:column;gap:0;padding:0}
.picks-bar{display:flex;align-items:center;gap:6px;padding:8px 12px;border-bottom:1px solid var(--border);flex-shrink:0}
.picks-region-btn{background:var(--panel);border:1px solid var(--border2);color:var(--gray);border-radius:3px;padding:3px 10px;font-size:10px;font-family:var(--mono);letter-spacing:0.08em;cursor:pointer;transition:all .15s}
.picks-region-btn.on{background:var(--orange);border-color:var(--orange);color:var(--black);font-weight:700}
.picks-status{margin-left:auto;font-size:10px;color:var(--gray);letter-spacing:0.05em}
.picks-table-wrap{flex:1;overflow-y:auto}
table.picks-tbl{width:100%;border-collapse:collapse;font-size:11px}
table.picks-tbl th{padding:5px 8px;text-align:left;color:var(--gray);font-size:9px;letter-spacing:0.1em;border-bottom:1px solid var(--border);position:sticky;top:0;background:var(--bg);z-index:1}
table.picks-tbl td{padding:5px 8px;border-bottom:1px solid var(--border2);vertical-align:middle}
.picks-tbl tr.pick-buy{background:rgba(74,140,74,0.06)}
.picks-tbl tr.pick-watch{background:rgba(200,140,50,0.06)}
.picks-verdict{font-size:9px;font-weight:700;padding:1px 6px;border-radius:2px;letter-spacing:0.06em}
.picks-verdict.BUY{background:rgba(74,140,74,0.2);color:#4CAF50}
.picks-verdict.WATCH{background:rgba(200,140,50,0.2);color:#FFC107}
.picks-analyze-btn{background:var(--orange);color:var(--black);border:none;border-radius:3px;padding:3px 8px;font-size:10px;font-weight:700;cursor:pointer;white-space:nowrap}
.picks-analyze-btn:hover{opacity:0.85}
#picks-ph{flex:1;display:flex;align-items:center;justify-content:center;color:var(--border2);font-size:11px;letter-spacing:1px}
```

### Edit B — Tab button (line 448, after CODE tab button)

Find this exact line:

```html
      <button class="tbtn" data-t="code">F5 CODE<span class="tdot" id="d-code"></span></button>
```

Replace it with:

```html
      <button class="tbtn" data-t="code">F5 CODE<span class="tdot" id="d-code"></span></button>
      <button class="tbtn" data-t="picks">★ PICKS<span class="tdot" id="d-picks"></span></button>
```

### Edit C — Tab panel HTML (after CODE tab panel, line 713)

Find this exact text:

```html
    </div><!-- /rpan -->
```

Replace it with:

```html
    <!-- PICKS -->
    <div class="tc" id="tc-picks">
      <div class="picks-bar">
        <button class="picks-region-btn on" data-r="us" onclick="G.loadPicks('us')">US</button>
        <button class="picks-region-btn" data-r="asia" onclick="G.loadPicks('asia')">ASIA</button>
        <button class="picks-region-btn" data-r="idx" onclick="G.loadPicks('idx')">IDX</button>
        <button class="picks-region-btn" onclick="G.refreshPicks()" style="margin-left:6px">↻</button>
        <span id="picks-status" class="picks-status">Memuat US picks...</span>
      </div>
      <div class="picks-table-wrap">
        <div id="picks-ph">PICKS TAB — AUTO-LOADING US STOCKS</div>
        <table class="picks-tbl" id="picks-table" style="display:none">
          <thead>
            <tr>
              <th>#</th><th>TICKER</th><th>VERDICT</th><th>RATIONALE</th>
              <th style="text-align:center">CONV.</th><th style="text-align:center">P/E</th>
              <th style="text-align:center">RSI</th><th></th>
            </tr>
          </thead>
          <tbody id="picks-tbody"></tbody>
        </table>
      </div>
    </div>

    </div><!-- /rpan -->
```

### Edit D — Update TABS array (line 742)

Find this exact line:

```javascript
var TABS=['summary','strategy','technicals','charts','verdict','code'];
```

Replace it with:

```javascript
var TABS=['summary','strategy','technicals','charts','verdict','code','picks'];
```

### Edit E — Add G.loadPicks JS and auto-trigger

Find this exact text (the copy button handler near the end of the `<script>` block):

```javascript
document.getElementById('copybtn').addEventListener('click',function(){
```

Insert the following block **immediately before** it:

```javascript
// ── PICKS TAB ──────────────────────────────────────────────────────────────
function _escPicks(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
G.picksCache={};G.picksES=null;G.picksRegion='us';
G.loadPicks=function(region){
  region=region||'us';G.picksRegion=region;
  document.querySelectorAll('.picks-region-btn').forEach(function(b){b.classList.toggle('on',b.dataset.r===region)});
  if(G.picksCache[region]){G.renderPicksFromCache(region);return}
  G.$('picks-tbody').innerHTML='';
  G.$('picks-ph').style.display='flex';G.$('picks-table').style.display='none';
  G.$('picks-status').textContent='Memuat '+region.toUpperCase()+' picks...';
  if(G.picksES){G.picksES.close();G.picksES=null}
  var cache=[];
  var es=new EventSource('/api/stock/picks?region='+region);G.picksES=es;
  es.onmessage=function(e){
    var msg;try{msg=JSON.parse(e.data)}catch(err){return}
    switch(msg.event){
      case 'picks_start':
        G.$('picks-status').textContent='Menganalisis 0/'+msg.total+'...';
        break;
      case 'pick_result':
        if(msg.verdict==='ERROR'||msg.verdict==='SKIP')break;
        cache.push(msg);
        cache.sort(function(a,b){return(b.conviction_score||0)-(a.conviction_score||0)});
        G.renderPicksRows(cache.slice(0,8));
        G.$('picks-status').textContent='Menganalisis '+cache.length+'...';
        break;
      case 'picks_done':
        G.picksCache[region]=cache;
        G.$('picks-status').textContent=cache.slice(0,8).length+' picks · '+region.toUpperCase();
        es.close();G.picksES=null;
        break;
      case 'error':
        G.$('picks-status').textContent='Error: '+(msg.message||'Gagal');
        es.close();G.picksES=null;
        break;
    }
  };
  es.onerror=function(){
    G.$('picks-status').textContent='Koneksi terputus.';
    if(G.picksES){G.picksES.close();G.picksES=null}
  };
};
G.renderPicksRows=function(rows){
  G.$('picks-ph').style.display='none';G.$('picks-table').style.display='';
  G.$('picks-tbody').innerHTML=rows.map(function(p,i){
    var cls=p.verdict==='BUY'?'pick-buy':'pick-watch';
    var pe=p.pe_ratio?parseFloat(p.pe_ratio).toFixed(1)+'x':'—';
    var rsi=p.rsi?parseFloat(p.rsi).toFixed(1):'—';
    var rat=p.rationale?p.rationale.substring(0,70)+(p.rationale.length>70?'…':''):'—';
    return '<tr class="'+cls+'">'
      +'<td style="color:var(--gray)">'+(i+1)+'</td>'
      +'<td style="font-weight:700;color:var(--white)">'+_escPicks(p.ticker||'')+'</td>'
      +'<td><span class="picks-verdict '+p.verdict+'">'+p.verdict+'</span></td>'
      +'<td style="color:var(--gray);max-width:220px">'+_escPicks(rat)+'</td>'
      +'<td style="text-align:center;color:var(--white)">'+(p.conviction_score||'—')+'/10</td>'
      +'<td style="text-align:center;color:var(--gray)">'+pe+'</td>'
      +'<td style="text-align:center;color:var(--gray)">'+rsi+'</td>'
      +'<td><button class="picks-analyze-btn" onclick="G.analyzePickTicker(\''+_escPicks(p.ticker||'')+'\')">ANALYZE →</button></td>'
      +'</tr>';
  }).join('');
};
G.renderPicksFromCache=function(region){
  var rows=(G.picksCache[region]||[]).slice(0,8);
  G.renderPicksRows(rows);
  G.$('picks-status').textContent=rows.length+' picks · '+region.toUpperCase()+' (cached)';
};
G.analyzePickTicker=function(ticker){
  G.$('cmdinput').value=ticker;
  switchTab('summary');
  document.getElementById('abtn').click();
};
G.refreshPicks=function(){
  delete G.picksCache[G.picksRegion];
  G.loadPicks(G.picksRegion);
};
// Auto-trigger US picks on load
document.addEventListener('DOMContentLoaded',function(){G.loadPicks('us')});

```

- [ ] **Step 1: Apply Edit A — CSS**
- [ ] **Step 2: Apply Edit B — Tab button**
- [ ] **Step 3: Apply Edit C — Tab panel HTML**
- [ ] **Step 4: Apply Edit D — TABS array**
- [ ] **Step 5: Apply Edit E — JS + auto-trigger**

- [ ] **Step 6: Verify server loads and page is reachable**

```powershell
$env:PYTHONUTF8=1; python -c "import server; print('OK')"
```
Expected: `OK`

- [ ] **Step 7: Commit**

```powershell
git add "static/CassanovaL Terminal v2.html"
git commit -m "feat(picks): add PICKS tab — region filters, ranked table, auto-load, analyze button"
```

---

## Final Verification

```powershell
# 1. All screener tests pass
$env:PYTHONUTF8=1; pytest tests/test_stock_screener.py -v
# Expected: 2 passed

# 2. Full regression — no existing tests broken
$env:PYTHONUTF8=1; pytest tests/test_stock_tools.py tests/test_stock_agents.py tests/test_study_agents.py tests/test_stock_screener.py -v
# Expected: 27 passed

# 3. Server imports
$env:PYTHONUTF8=1; python -c "import server; print('OK')"

# 4. End-to-end smoke test
$env:PYTHONUTF8=1; python server.py
# Open http://localhost:8000/stock
# Verify: ★ PICKS tab appears alongside existing 6 tabs
# Verify: US picks start loading automatically (status "Menganalisis...")
# Verify: rows stream in and sort by conviction score descending
# Verify: only BUY and WATCH rows visible (SKIP hidden)
# Verify: switching to ASIA or IDX triggers new analysis
# Verify: ↻ refresh button clears cache and re-fetches
# Verify: clicking ANALYZE → fills ticker input and triggers 6-agent pipeline
# Verify: existing tabs (SUMMARY, STRATEGY, TECHNICALS, CHARTS, VERDICT, CODE) unaffected
```
