# Stock Terminal v2 — Enhanced Agent Suite Design Spec

**Date:** 2026-04-28
**Sub-project:** 1 of 4 (Enhanced Agent Suite)
**Approach:** A — Incremental Replacement
**Status:** Approved

---

## 1. Overview

Replace the existing 4-agent Bloomberg Terminal pipeline (Quant, Newsroom, Economist, Critic) with a new ValueCell-inspired lean lineup: **DeepResearch → NewsIntelligence → Strategy → FinalVerdict**. The SSE streaming architecture, Bloomberg dark theme, Plotly charts, and Python code tab are unchanged. The new agents are deeper, more actionable, and expose a new "Trading Strategy" section (entry/exit/stop loss) and a conviction score.

---

## 2. Agent Lineup

### 2.1 DeepResearch (replaces Quant + Economist)

**Purpose:** Consolidated fundamental + macro analysis in one agent.

**Tools used:** `get_market_data(ticker, period="1y")` (upgraded)

**Data fetched by the tool:**
- Income statement, balance sheet, cash flow — last 5 years (`ticker.financials`, `ticker.balance_sheet`, `ticker.cashflow`)
- Analyst price targets (`ticker.analyst_price_targets`)
- Analyst recommendations (`ticker.recommendations`)
- OHLCV 1-year history (existing)
- Macro correlation (existing)
- Computed trends: ROE trend, profit margin trend, revenue CAGR (Pandas, not LLM)

**Output JSON:**
```json
{
  "summary": "3-4 kalimat kondisi fundamental",
  "valuation": "P/E, P/B, EV/EBITDA atau N/A",
  "growth_trend": "CAGR revenue + margin trend 3 tahun",
  "financial_health": "debt/equity, current ratio, free cash flow",
  "analyst_consensus": "rata-rata target price + % buy/hold/sell",
  "macro_context": "dampak makro terhadap saham ini",
  "current_price": 0.0,
  "ohlcv": {},
  "macro_correlation": {}
}
```

---

### 2.2 NewsIntelligence (replaces Newsroom)

**Purpose:** Smarter news analysis with per-article classification and anomaly detection.

**Tools used:** `get_news_sentiment(query, max_results=15)` (upgraded from 10)

**Enhancements:**
- Fetch 15 articles (up from 10)
- Classify each article by event type: `earnings` / `M&A` / `management` / `regulatory` / `macro` / `other`
- Sentiment score per article (not only aggregate)
- Anomaly flag: unusual volume spike + news spike correlation

**Output JSON:**
```json
{
  "summary": "3-4 kalimat sentimen pasar",
  "sentiment_score": 0.0,
  "event_type": "earnings|M&A|management|regulatory|macro|other",
  "key_events": ["event1", "event2"],
  "risk_signals": ["sinyal negatif"],
  "catalyst_signals": ["katalis positif"],
  "anomaly_detected": false
}
```

---

### 2.3 Strategy (new — inspired by ValueCell)

**Purpose:** Generate actionable trading strategy from DeepResearch + NewsIntelligence output.

**Tools used:** none (pure LLM reasoning on structured input)

**Input:** DeepResearch output (strips `ohlcv`) + NewsIntelligence output

**Output JSON:**
```json
{
  "entry_zone": "harga bawah–atas zona entry (support level)",
  "exit_target": "target harga keluar (resistance + analyst target)",
  "stop_loss": "level stop loss",
  "stop_loss_pct": 0.0,
  "time_horizon": "short|medium|long",
  "time_horizon_detail": "estimasi durasi (mis. 3-6 bulan)",
  "position_size": "% portfolio yang disarankan",
  "risk_reward_ratio": "1:X",
  "rationale": "1-2 kalimat alasan strategi ini"
}
```

---

### 2.4 FinalVerdict (replaces Critic)

**Purpose:** Devil's advocate synthesis with conviction score, bull/bear case, and investment memo.

**Tools used:** none (pure LLM reasoning on all 3 agent outputs)

**Input:** DeepResearch (strips `ohlcv`) + NewsIntelligence + Strategy

**Output JSON:**
```json
{
  "executive_summary": "2-3 kalimat kondisi saham menyeluruh",
  "fundamental_analysis": "paragraph analisis fundamental tajam",
  "sentiment_macro": "paragraph gabungan sentimen + makro",
  "risk_assessment": ["risiko 1", "risiko 2", "risiko 3"],
  "counter_arguments": "devil's advocate — apa yang bisa membuat tesis ini salah",
  "bull_case": ["skenario positif 1", "skenario positif 2"],
  "bear_case": ["skenario negatif 1", "skenario negatif 2"],
  "verdict": "BUY|HOLD|SELL",
  "conviction_score": 7,
  "risk_reward": "1:3.8",
  "investment_memo": "memo investasi profesional 3-4 kalimat"
}
```

`conviction_score`: integer 1–10. `verdict` only: BUY, HOLD, or SELL.

---

## 3. Pipeline Flow

```
Ticker Input
    │
    ▼
DeepResearch (~30s)   ←── get_market_data (yfinance, upgraded)
    │
    ▼ [5s gap]
NewsIntelligence (~20s) ←── get_news_sentiment (Serper/DDG, upgraded)
    │
    ▼ [5s gap]
Strategy (~20s)         ←── input: DeepResearch + NewsIntelligence
    │
    ▼ [5s gap]
FinalVerdict (~25s)     ←── input: all 3 agents above
    │
    ▼
SSE done event → frontend renders full report
```

**Total estimated time:** 95–120 seconds. Sequential with 5s gaps between agents (rate limit guard). Retry: inner `time.sleep` exponential backoff in `stock_agents.py` (max 5 retries, 20→40→80→120s), outer `asyncio.sleep(5)` gap in `server.py`.

---

## 4. Tools Layer Changes (`tools/stock_tools.py`)

### `get_market_data(ticker, period="1y")` — UPGRADE

Add to existing function:
- Fetch `ticker.financials`, `ticker.balance_sheet`, `ticker.cashflow` → summarize last 5 years with Pandas (never send raw DataFrame to LLM)
- Fetch `ticker.analyst_price_targets`, `ticker.recommendations` → clean to dict
- Compute with Pandas: revenue CAGR (3yr), ROE trend (3 data points), net margin trend (3 data points)
- Return all above in the tool output dict alongside existing OHLCV + macro_correlation

### `get_news_sentiment(query, max_results=15)` — UPGRADE

- Increase default `max_results` from 10 to 15
- Add `event_type` field to each article dict: classify using keyword heuristics in the tool layer (not LLM)
  - `earnings`: keywords → "earnings", "revenue", "profit", "EPS", "quarterly"
  - `M&A`: keywords → "merger", "acquisition", "takeover", "buyout"
  - `management`: keywords → "CEO", "CFO", "director", "resign", "appoint"
  - `regulatory`: keywords → "SEC", "regulation", "fine", "lawsuit", "probe"
  - `macro`: keywords → "Fed", "interest rate", "inflation", "GDP", "central bank"
  - default: `other`
- Add `volume_anomaly` boolean to tool output: `True` if more than 10 news articles about the ticker were found in the last 24 hours (proxy for unusual media attention spike). The LLM uses this to set `anomaly_detected` in its output JSON.

### `get_macro_indicators()` — REMOVE

Macro context is now generated by DeepResearch's LLM reasoning on the financial + price data already fetched. The separate `get_macro_indicators` tool is no longer needed. Remove from `STOCK_TOOLS` export.

---

## 5. Server Changes (`server.py`)

### New SSE events

| Event | Payload | When sent |
|-------|---------|-----------|
| `strategy` | Strategy agent JSON output | After Strategy agent completes |
| `verdict` | FinalVerdict agent JSON output | After FinalVerdict agent completes |

Existing events (`step`, `log`, `chart`, `code`, `done`, `error`) are unchanged.

### Agent runner function names in SSE endpoint

Replace calls: `run_quant` → `run_deep_research`, `run_newsroom` → `run_news_intelligence`, add `run_strategy`, `run_final_verdict`. Remove `run_economist`.

---

## 6. Frontend Changes (`static/stock/index.html`)

### Agent Feed panel

- Rename agent rows: The Quant → DeepResearch, The Newsroom → NewsIntelligence, The Economist → Strategy, The Critic → FinalVerdict
- Add left-border accent color per agent (existing color scheme: green/blue/yellow/orange)
- Verdict box: add **Conviction Score** bar (10 blocks, filled = conviction_score value) below verdict

### Tab structure (Report Panel)

Old: `SUMMARY | CHARTS | CODE`
New: `SUMMARY | STRATEGY | CHARTS | VERDICT | CODE`

### Tab: STRATEGY (new)

Renders Strategy agent output with three metric cards:
- Entry Zone (green accent)
- Exit Target (yellow accent)
- Stop Loss (red accent)

Below cards: Risk/Reward ratio, Time Horizon, Position Sizing bar (% of 100).

Frontend listens for SSE `strategy` event to populate this tab.

### Tab: VERDICT (upgrade)

Existing verdict content (executive summary, fundamental analysis, etc.) now also renders:
- Bull Case list (green)
- Bear Case list (red)
- Investment Memo paragraph

Frontend listens for SSE `verdict` event.

### Tab: SUMMARY

Unchanged — renders DeepResearch + NewsIntelligence key fields (existing renderReport logic updated for new field names).

---

## 7. Files Changed

| File | Change type |
|------|------------|
| `tools/stock_tools.py` | Modify — upgrade `get_market_data`, upgrade `get_news_sentiment`, remove `get_macro_indicators` |
| `agents/stock_agents.py` | Rewrite — replace 4 run_* functions + prompts |
| `server.py` | Modify — update SSE endpoint: new agent calls, 2 new SSE events |
| `static/stock/index.html` | Modify — new tab STRATEGY, verdict upgrade, conviction bar, agent name rename |

No new files required.

---

## 8. What Stays the Same

- Bloomberg dark theme (`#0a0a0f`, `--green: #00ff88`, `--red: #ff4444`, `--yellow: #ffcc00`)
- SSE streaming architecture (EventSource, `_sse()` helper, StreamingResponse)
- `agents/base.py` — `build_agent()` unchanged
- Plotly candlestick + correlation heatmap (CHARTS tab)
- Python code tab
- `_parse_json_output()` and `_invoke_with_retry()` helpers
- 429 rate limit double-layer retry strategy
- `default=float` guard in `json.dumps` for numpy.float64
- Explicit `@app.get("/stock")` route before catchall
- All existing chat agents and CrewAI pipelines — untouched

---

## 9. Out of Scope (Future Sub-projects)

- Sub-project 2: OpenBB unified data layer
- Sub-project 3: Backtesting + Walk-Forward + Monte Carlo validation
- Sub-project 4: PDF annual report parsing (Document Analysis)
