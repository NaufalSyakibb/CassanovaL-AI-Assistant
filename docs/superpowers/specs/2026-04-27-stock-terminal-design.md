# Stock Terminal — Bloomberg-Style Multi-Agent Analysis
**Date:** 2026-04-27  
**Status:** Approved

---

## Overview

A separate web page (`/stock`) integrated into the existing CassanovaL FastAPI server that performs comprehensive stock analysis using a 4-agent pipeline. Users enter a ticker symbol, trigger a streaming analysis, and receive a structured report in Bahasa Indonesia — with live Plotly charts embedded and a copyable Python code block for reproducing the charts locally.

---

## Architecture

### Flow

```
User (browser: /stock)
    │  ketik ticker (e.g. "BBCA.JK") → klik Analyze
    ▼
GET /api/stock/analyze?ticker=BBCA.JK   ← SSE endpoint (text/event-stream)
    │
    ├── [event: step]  "Quant mengambil data pasar..."
    │       TheQuant Agent — sequential (Phase 1)
    │       └── yfinance: OHLCV 1Y, P/E, ROE, Debt/Equity, market cap, 52w high/low
    │       └── Pandas: clean + summarize → ringkas ke <2k token
    │
    ├── [event: step]  "Newsroom + Economist berjalan paralel..."
    │       TheNewsroom Agent — Phase 2, parallel via asyncio.gather
    │       └── Serper (fallback DuckDuckGo): 10 berita terbaru
    │       └── LLM: sentiment score + key themes
    │
    │       TheEconomist Agent — Phase 2, parallel
    │       └── yfinance: ^IRX, ^GSPC, GC=F, CL=F — 30d change %
    │       └── LLM: korelasi makro dengan saham target
    │
    └── [event: step]  "Critic menyusun laporan final..."
            TheCritic Agent — sequential (Phase 3)
            └── Gabung output Quant + Newsroom + Economist
            └── LLM: devil's advocate + verdict Buy/Hold/Sell
            └── Generate Plotly JSON + Python code
```

### Files

| File | Role |
|------|------|
| `agents/stock_agents.py` | 4 LangChain agents (TheQuant, TheNewsroom, TheEconomist, TheCritic) |
| `tools/stock_tools.py` | yfinance + search wrappers, Pandas cleaning |
| `static/stock/index.html` | Standalone Bloomberg-style frontend |
| `server.py` | +1 SSE endpoint: `GET /api/stock/analyze` |

---

## Backend

### Tools (`tools/stock_tools.py`)

| Tool | Library | Output |
|------|---------|--------|
| `get_market_data(ticker, period="1y")` | yfinance + Pandas | Dict: OHLCV summary, P/E, ROE, Debt/Equity, market cap, 52w high/low |
| `get_news_sentiment(query, max_results=10)` | Serper → DuckDuckGo fallback | List of `{title, source, snippet, date}` |
| `get_macro_indicators()` | yfinance | Dict: ^IRX, ^GSPC, GC=F, CL=F — 30d change % each |

Pandas is used inside `get_market_data` to clean raw yfinance DataFrame and produce a token-efficient summary dict before passing to the LLM. Raw DataFrames are never sent to the LLM.

### Agents (`agents/stock_agents.py`)

All agents use `mistral-large-latest`, consistent with existing project convention.

| Agent | Persona | Input | Output (Bahasa Indonesia) |
|-------|---------|-------|--------------------------|
| `TheQuant` | Dingin, angka saja, kuantitatif | market_data dict | Fundamental + technical summary |
| `TheNewsroom` | Jurnalis investigatif | news list + ticker | Sentiment analysis + key themes |
| `TheEconomist` | Macro strategist | macro_indicators + quant_output | Big picture context |
| `TheCritic` | Devil's advocate, quality controller | semua output di atas | Executive summary + Risk + Verdict |

### SSE Endpoint (`server.py`)

```
GET /api/stock/analyze?ticker={ticker}
Content-Type: text/event-stream
```

Event stream format:
```
data: {"event": "step",  "agent": "Quant",    "status": "running"}
data: {"event": "log",   "text": "P/E Ratio: 14.2x — di bawah rata-rata sektor"}
data: {"event": "step",  "agent": "Quant",    "status": "done"}
data: {"event": "step",  "agent": "Newsroom", "status": "running"}
data: {"event": "step",  "agent": "Economist","status": "running"}
data: {"event": "step",  "agent": "Newsroom", "status": "done"}
data: {"event": "step",  "agent": "Economist","status": "done"}
data: {"event": "step",  "agent": "Critic",   "status": "running"}
data: {"event": "chart", "candlestick": {...plotly json...}, "heatmap": {...plotly json...}}
data: {"event": "code",  "python": "import plotly.graph_objects as go\n..."}
data: {"event": "done",  "report": {"executive_summary": "...", "fundamental": "...", "sentiment": "...", "risk": "...", "verdict": "BUY"}}
data: {"event": "error", "message": "..."}
```

---

## Frontend (`static/stock/index.html`)

Standalone single-file HTML — no JSX, no React, no build step. Vanilla JS + inline CSS.

### Visual Style

- Background: `#0a0a0f` (near-black terminal)
- Accent: `#00ff88` (green = positive), `#ff4444` (red = negative), `#ffcc00` (yellow = neutral/hold)
- Font: `JetBrains Mono` (Google Fonts CDN), monospace fallback
- All data values styled as terminal readouts

### Layout (two-column)

```
┌─────────────────────────────────────────────────────────────┐
│  CASSANOVAL TERMINAL  ●  STOCK ANALYSIS         [dark bg]   │
├─────────────────────────────────────────────────────────────┤
│  Ticker: [__BBCA.JK__________]  [▶ ANALYZE]   [●LIVE]      │
├────────────────────┬────────────────────────────────────────┤
│  AGENT FEED        │  REPORT PANEL                          │
│  (kiri, 35%)       │  (kanan, 65%)                          │
│                    │                                        │
│  ● Quant      ✓    │  [TAB: Summary | Charts | Code]        │
│  ● Newsroom   ✓    │                                        │
│  ● Economist  ✓    │  Executive Summary ─────────────────   │
│  ● Critic     ⟳    │  Fundamental & Technical Deep Dive ──  │
│                    │  Sentiment & Macro Context ──────────   │
│  [log stream]      │  Risk Assessment ────────────────────   │
│  > Mengambil       │                                        │
│    data BBCA...    │  ┌─────────────────────────┐           │
│  > P/E: 14.2x      │  │  FINAL VERDICT: BUY ▲   │           │
│  > Sentiment: +0.7 │  └─────────────────────────┘           │
└────────────────────┴────────────────────────────────────────┘
```

### Tabs (Report Panel)

- **Summary** — structured report sections rendered as formatted text blocks
- **Charts** — Plotly candlestick (OHLC 1Y) + correlation heatmap rendered via `Plotly.newPlot()` from backend JSON
- **Code** — syntax-highlighted Python code block with Copy button to reproduce charts locally

### Navigation

Accessible from the main CassanovaL app via a link/button, served at route `/stock` (FastAPI mounts `static/stock/` directory and returns `index.html`).

---

## Data Flow Summary

1. User enters ticker → EventSource opens SSE connection
2. Backend: Quant runs, streams `log` events with key data points
3. Backend: Newsroom + Economist run in parallel, stream their own `log` events
4. Backend: Critic synthesizes, generates Plotly JSON + Python code
5. Backend: streams `chart`, `code`, `done` events
6. Frontend: renders report sections, activates Charts tab, shows Copy button on Code tab
7. On error: streams `error` event, frontend shows error message in feed panel

---

## Constraints & Decisions

- **No new LLM provider** — uses existing `mistral-large-latest` via `MISTRAL_API_KEY`
- **No new search provider** — uses existing Serper → DuckDuckGo fallback pattern
- **Token efficiency** — Pandas summarization in tools layer, never raw DataFrames to LLM
- **Output language** — all LLM output in Bahasa Indonesia profesional
- **Chart output** — both Plotly HTML embed (interactive) AND copyable Python code
- **Frontend** — standalone HTML, no build toolchain, consistent with existing `/static` pattern
