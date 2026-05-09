# Stock Terminal — Bloomberg-Style Multi-Agent Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Bloomberg-style stock analysis page at `/stock` backed by a 4-agent SSE-streaming pipeline integrated into the existing FastAPI server.

**Architecture:** User enters a ticker → SSE stream opens → Phase 1: TheQuant fetches+cleans yfinance data → Phase 2: TheNewsroom + TheEconomist run in parallel → Phase 3: TheCritic synthesizes a final report with Plotly charts + copyable Python code. All output in Bahasa Indonesia.

**Tech Stack:** Python (yfinance, pandas, plotly, langchain-mistralai, fastapi StreamingResponse), Vanilla JS + inline CSS (Bloomberg terminal aesthetic), Plotly.js CDN.

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `tools/stock_tools.py` | yfinance + search wrappers, Pandas cleaning, Plotly JSON builders |
| Create | `agents/stock_agents.py` | 4 LangChain agents: TheQuant, TheNewsroom, TheEconomist, TheCritic |
| Create | `static/stock/index.html` | Standalone Bloomberg terminal frontend |
| Create | `tests/test_stock_tools.py` | Unit tests for tools (mocked external calls) |
| Modify | `server.py` | Add SSE endpoint + `/stock` static mount |
| Modify | `requirements.txt` | Add yfinance, pandas, plotly |

---

## Task 1: Add Dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add missing packages**

Open `requirements.txt` and append these three lines at the end:

```
yfinance
pandas
plotly
```

- [ ] **Step 2: Install**

```bash
pip install yfinance pandas plotly
```

Expected: All three install without error. `import yfinance as yf` in a Python shell returns no error.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "deps: add yfinance, pandas, plotly for stock terminal"
```

---

## Task 2: Stock Tools (`tools/stock_tools.py`)

**Files:**
- Create: `tools/stock_tools.py`
- Create: `tests/test_stock_tools.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_stock_tools.py`:

```python
import json
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd


# ── get_market_data ───────────────────────────────────────────

def _make_hist_df():
    """Return a minimal fake yfinance history DataFrame."""
    import numpy as np
    dates = pd.date_range("2024-01-01", periods=10, freq="B")
    return pd.DataFrame({
        "Open":   [100.0] * 10,
        "High":   [105.0] * 10,
        "Low":    [98.0]  * 10,
        "Close":  [102.0] * 10,
        "Volume": [1_000_000] * 10,
    }, index=dates)


def test_get_market_data_returns_valid_dict():
    from tools.stock_tools import get_market_data
    fake_hist = _make_hist_df()
    fake_info = {"trailingPE": 14.2, "returnOnEquity": 0.18, "debtToEquity": 0.5, "marketCap": 5e12}

    with patch("yfinance.Ticker") as MockTicker:
        inst = MockTicker.return_value
        inst.history.return_value = fake_hist
        inst.info = fake_info

        raw = get_market_data.invoke("BBCA.JK")
        data = json.loads(raw)

    assert data["ticker"] == "BBCA.JK"
    assert data["current_price"] == 102.0
    assert data["pe_ratio"] == 14.2
    assert "ohlcv" in data
    assert len(data["ohlcv"]["dates"]) == 10


def test_get_market_data_empty_ticker_returns_error():
    from tools.stock_tools import get_market_data
    with patch("yfinance.Ticker") as MockTicker:
        inst = MockTicker.return_value
        inst.history.return_value = pd.DataFrame()
        inst.info = {}

        raw = get_market_data.invoke("INVALID999")
        data = json.loads(raw)

    assert "error" in data


# ── get_news_sentiment ────────────────────────────────────────

def test_get_news_sentiment_uses_serper_when_available():
    from tools.stock_tools import get_news_sentiment
    fake_serper_resp = MagicMock()
    fake_serper_resp.status_code = 200
    fake_serper_resp.json.return_value = {
        "news": [{"title": "BBCA naik", "source": "Kompas", "snippet": "Saham naik", "date": "2025-01-01"}]
    }

    with patch("os.getenv", return_value="FAKE_SERPER_KEY"), \
         patch("requests.post", return_value=fake_serper_resp):
        raw = get_news_sentiment.invoke("BBCA Bank Central Asia")
        articles = json.loads(raw)

    assert isinstance(articles, list)
    assert articles[0]["title"] == "BBCA naik"


def test_get_news_sentiment_falls_back_to_ddg():
    from tools.stock_tools import get_news_sentiment
    fake_ddg_result = [{"title": "DDG news", "source": "Bloomberg", "body": "snippet", "date": "2025-01-01"}]

    with patch("os.getenv", return_value=""), \
         patch("duckduckgo_search.DDGS") as MockDDGS:
        MockDDGS.return_value.__enter__.return_value.news.return_value = fake_ddg_result
        raw = get_news_sentiment.invoke("BBCA")
        articles = json.loads(raw)

    assert isinstance(articles, list)


# ── get_macro_indicators ──────────────────────────────────────

def test_get_macro_indicators_returns_four_symbols():
    from tools.stock_tools import get_macro_indicators
    fake_hist = _make_hist_df()

    with patch("yfinance.Ticker") as MockTicker:
        MockTicker.return_value.history.return_value = fake_hist
        raw = get_macro_indicators.invoke("")
        data = json.loads(raw)

    assert "SP500" in data
    assert "Gold" in data
    assert "Oil_WTI" in data
    assert "US_tbill_rate_3m" in data
    for key in data:
        assert "change_30d_pct" in data[key]


# ── Plotly builder helpers ────────────────────────────────────

def test_build_candlestick_json_structure():
    from tools.stock_tools import build_candlestick_json
    ohlcv = {
        "dates": ["2024-01-01", "2024-01-02"],
        "open":  [100.0, 101.0],
        "high":  [105.0, 106.0],
        "low":   [98.0,  99.0],
        "close": [102.0, 103.0],
        "volume":[1000,  2000],
    }
    result = build_candlestick_json("BBCA.JK", ohlcv)
    assert "data" in result
    assert result["data"][0]["type"] == "candlestick"
    assert "layout" in result
    assert result["layout"]["paper_bgcolor"] == "#0a0a0f"


def test_build_heatmap_json_structure():
    from tools.stock_tools import build_heatmap_json
    corr = {"SP500": 0.72, "Gold": -0.15, "Oil_WTI": 0.33, "US_tbill_rate_3m": -0.41}
    result = build_heatmap_json("BBCA.JK", corr)
    assert result["data"][0]["type"] == "heatmap"
    assert result["data"][0]["zmin"] == -1
    assert result["data"][0]["zmax"] == 1


def test_build_python_code_is_runnable_string():
    from tools.stock_tools import build_python_code
    ohlcv = {
        "dates": ["2024-01-01"],
        "open": [100.0], "high": [105.0],
        "low": [98.0], "close": [102.0], "volume": [1000],
    }
    corr = {"SP500": 0.7}
    code = build_python_code("BBCA.JK", ohlcv, corr)
    assert "import plotly.graph_objects" in code
    assert "Candlestick" in code
    assert "Heatmap" in code
    assert "BBCA.JK" in code
```

- [ ] **Step 2: Run tests — verify all fail**

```bash
python -m pytest tests/test_stock_tools.py -v
```

Expected: All tests fail with `ModuleNotFoundError: No module named 'tools.stock_tools'`.

- [ ] **Step 3: Create `tools/stock_tools.py`**

```python
import os
import json
import re
import requests
import pandas as pd
import yfinance as yf
from langchain.tools import tool


# ── Internal helpers ──────────────────────────────────────────────────────────

def _fetch_serper(query: str, max_results: int) -> list:
    api_key = os.getenv("SERPER_API_KEY", "")
    if not api_key:
        return []
    try:
        resp = requests.post(
            "https://google.serper.dev/news",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": max_results},
            timeout=10,
        )
        if resp.status_code != 200:
            return []
        items = resp.json().get("news", [])
        return [
            {
                "title": i.get("title", ""),
                "source": i.get("source", ""),
                "snippet": i.get("snippet", ""),
                "date": i.get("date", ""),
            }
            for i in items
        ]
    except Exception:
        return []


def _fetch_ddg(query: str, max_results: int) -> list:
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.news(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "source": r.get("source", ""),
                    "snippet": r.get("body", ""),
                    "date": r.get("date", ""),
                })
        return results
    except Exception:
        return []


# ── LangChain tools ───────────────────────────────────────────────────────────

@tool
def get_market_data(ticker: str) -> str:
    """
    Fetch 1-year historical OHLCV + key financial ratios for a stock ticker.
    Args:
        ticker: Stock ticker symbol (e.g. 'BBCA.JK', 'AAPL').
    Returns:
        JSON string with market data summary and OHLCV for charting.
    """
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="1y")
        if hist.empty:
            return json.dumps({"error": f"No data found for ticker '{ticker}'"})

        hist = hist.dropna()
        latest = hist.iloc[-1]
        info = tk.info or {}

        # Correlation: daily returns vs macro indices
        macro_symbols = {"^GSPC": "SP500", "GC=F": "Gold", "CL=F": "Oil_WTI", "^IRX": "US_tbill_rate_3m"}
        returns_df = pd.DataFrame()
        returns_df[ticker] = hist["Close"].pct_change().dropna()
        for symbol, name in macro_symbols.items():
            try:
                mhist = yf.Ticker(symbol).history(period="1y")
                if not mhist.empty:
                    returns_df[name] = mhist["Close"].pct_change().dropna()
            except Exception:
                pass

        corr = {}
        if ticker in returns_df.columns and len(returns_df.columns) > 1:
            corr = returns_df.corr()[ticker].drop(ticker).round(3).to_dict()

        summary = {
            "ticker": ticker,
            "current_price": round(float(latest["Close"]), 2),
            "52w_high": round(float(hist["High"].max()), 2),
            "52w_low": round(float(hist["Low"].min()), 2),
            "avg_volume_30d": int(hist["Volume"].tail(30).mean()),
            "pe_ratio": info.get("trailingPE"),
            "roe": info.get("returnOnEquity"),
            "debt_to_equity": info.get("debtToEquity"),
            "market_cap": info.get("marketCap"),
            "price_change_1y_pct": round(
                (float(latest["Close"]) - float(hist.iloc[0]["Close"])) / float(hist.iloc[0]["Close"]) * 100, 2
            ),
            "macro_correlation": corr,
            "ohlcv": {
                "dates": hist.index.strftime("%Y-%m-%d").tolist(),
                "open":  hist["Open"].round(2).tolist(),
                "high":  hist["High"].round(2).tolist(),
                "low":   hist["Low"].round(2).tolist(),
                "close": hist["Close"].round(2).tolist(),
                "volume": hist["Volume"].tolist(),
            },
        }
        return json.dumps(summary)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_news_sentiment(query: str) -> str:
    """
    Search recent financial news about a stock or topic.
    Args:
        query: Search query (e.g. 'BBCA Bank Central Asia saham 2025').
    Returns:
        JSON string — list of {title, source, snippet, date}.
    """
    try:
        articles = _fetch_serper(query, 10)
        if not articles:
            articles = _fetch_ddg(query, 10)
        return json.dumps(articles[:10])
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_macro_indicators(_: str = "") -> str:
    """
    Fetch macro economic indicators: US T-bill rate, S&P 500, Gold, Oil — 30-day change %.
    Returns:
        JSON string with macro indicator data.
    """
    indicators = {
        "^IRX":  "US_tbill_rate_3m",
        "^GSPC": "SP500",
        "GC=F":  "Gold",
        "CL=F":  "Oil_WTI",
    }
    result = {}
    for symbol, name in indicators.items():
        try:
            hist = yf.Ticker(symbol).history(period="35d")
            if len(hist) >= 2:
                start_price = float(hist.iloc[0]["Close"])
                end_price   = float(hist.iloc[-1]["Close"])
                change_pct  = round((end_price - start_price) / start_price * 100, 2)
                result[name] = {
                    "symbol":        symbol,
                    "current":       round(end_price, 2),
                    "change_30d_pct": change_pct,
                }
            else:
                result[name] = {"error": "insufficient data"}
        except Exception:
            result[name] = {"error": "fetch failed"}
    return json.dumps(result)


STOCK_TOOLS = [get_market_data, get_news_sentiment, get_macro_indicators]


# ── Plotly JSON builders (called by server.py, not agents) ───────────────────

def build_candlestick_json(ticker: str, ohlcv: dict) -> dict:
    """Return a Plotly figure dict for a dark-theme candlestick chart."""
    return {
        "data": [{
            "type": "candlestick",
            "x":     ohlcv.get("dates", []),
            "open":  ohlcv.get("open",  []),
            "high":  ohlcv.get("high",  []),
            "low":   ohlcv.get("low",   []),
            "close": ohlcv.get("close", []),
            "name":  ticker,
            "increasing": {"line": {"color": "#00ff88"}},
            "decreasing": {"line": {"color": "#ff4444"}},
        }],
        "layout": {
            "paper_bgcolor": "#0a0a0f",
            "plot_bgcolor":  "#0d0d14",
            "font":   {"color": "#c0c0d0", "family": "JetBrains Mono, monospace", "size": 11},
            "xaxis":  {"gridcolor": "#1e1e2e", "color": "#8080a0", "rangeslider": {"visible": False}},
            "yaxis":  {"gridcolor": "#1e1e2e", "color": "#8080a0", "title": "Price"},
            "title":  {"text": f"{ticker} — Harga 1 Tahun", "font": {"color": "#00ff88", "size": 14}},
            "margin": {"t": 50, "b": 40, "l": 70, "r": 20},
        },
    }


def build_heatmap_json(ticker: str, corr: dict) -> dict:
    """Return a Plotly figure dict for a macro-correlation heatmap."""
    label_map = {
        "SP500": "S&P 500", "Gold": "Emas", "Oil_WTI": "Minyak (WTI)", "US_tbill_rate_3m": "T-Bill 3M"
    }
    labels = [label_map.get(k, k) for k in corr]
    values = [round(float(v), 3) for v in corr.values()]
    text   = [[f"{v:+.2f}" for v in values]]
    return {
        "data": [{
            "type": "heatmap",
            "z":    [values],
            "x":    labels,
            "y":    [ticker],
            "colorscale": [[0, "#ff4444"], [0.5, "#1e1e2e"], [1, "#00ff88"]],
            "zmin": -1,
            "zmax":  1,
            "text":         text,
            "texttemplate": "%{text}",
            "textfont":     {"color": "#ffffff"},
            "showscale":    True,
        }],
        "layout": {
            "paper_bgcolor": "#0a0a0f",
            "plot_bgcolor":  "#0d0d14",
            "font":   {"color": "#c0c0d0", "family": "JetBrains Mono, monospace", "size": 11},
            "xaxis":  {"color": "#8080a0"},
            "yaxis":  {"color": "#8080a0"},
            "title":  {"text": f"{ticker} — Korelasi vs Indikator Makro (1 Tahun)", "font": {"color": "#00ff88", "size": 14}},
            "margin": {"t": 50, "b": 60, "l": 90, "r": 20},
        },
    }


def build_python_code(ticker: str, ohlcv: dict, corr: dict) -> str:
    """Return a self-contained Python script that reproduces both charts."""
    label_map = {
        "SP500": "S&P 500", "Gold": "Emas", "Oil_WTI": "Minyak (WTI)", "US_tbill_rate_3m": "T-Bill 3M"
    }
    corr_labels = [label_map.get(k, k) for k in corr]
    corr_values = [round(float(v), 3) for v in corr.values()]
    return f"""import plotly.graph_objects as go

# ── Data {ticker} ──────────────────────────────────────────────
dates  = {json.dumps(ohlcv.get('dates', []))}
open_  = {json.dumps(ohlcv.get('open',  []))}
high   = {json.dumps(ohlcv.get('high',  []))}
low    = {json.dumps(ohlcv.get('low',   []))}
close  = {json.dumps(ohlcv.get('close', []))}

# ── Candlestick Chart ──────────────────────────────────────────
fig1 = go.Figure(data=[go.Candlestick(
    x=dates, open=open_, high=high, low=low, close=close,
    name="{ticker}",
    increasing_line_color="#00ff88",
    decreasing_line_color="#ff4444",
)])
fig1.update_layout(
    title="{ticker} — Harga 1 Tahun",
    template="plotly_dark",
    xaxis_title="Tanggal",
    yaxis_title="Harga",
    xaxis_rangeslider_visible=False,
)
fig1.show()

# ── Correlation Heatmap ────────────────────────────────────────
corr_labels = {json.dumps(corr_labels)}
corr_values = {json.dumps(corr_values)}

fig2 = go.Figure(data=go.Heatmap(
    z=[corr_values],
    x=corr_labels,
    y=["{ticker}"],
    colorscale=[[0, "#ff4444"], [0.5, "#333340"], [1, "#00ff88"]],
    zmin=-1, zmax=1,
    text=[[f"{{v:+.2f}}" for v in corr_values]],
    texttemplate="%{{text}}",
))
fig2.update_layout(
    title="{ticker} — Korelasi vs Indikator Makro (1 Tahun)",
    template="plotly_dark",
)
fig2.show()
"""
```

- [ ] **Step 4: Run tests — verify all pass**

```bash
python -m pytest tests/test_stock_tools.py -v
```

Expected: All 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tools/stock_tools.py tests/test_stock_tools.py
git commit -m "feat(stock): add stock tools — yfinance, news, macro, Plotly builders"
```

---

## Task 3: Stock Agents (`agents/stock_agents.py`)

**Files:**
- Create: `agents/stock_agents.py`

- [ ] **Step 1: Write failing test for `_parse_json_output`**

Append to `tests/test_stock_tools.py`:

```python
# ── _parse_json_output ────────────────────────────────────────

def test_parse_json_output_extracts_json_from_message():
    from agents.stock_agents import _parse_json_output
    from langchain_core.messages import AIMessage

    fake_result = {
        "messages": [
            AIMessage(content='Some text before {"verdict": "BUY", "risk": "low"} after text')
        ]
    }
    parsed = _parse_json_output(fake_result)
    assert parsed["verdict"] == "BUY"
    assert parsed["risk"] == "low"


def test_parse_json_output_returns_error_on_no_json():
    from agents.stock_agents import _parse_json_output
    from langchain_core.messages import AIMessage

    fake_result = {"messages": [AIMessage(content="No JSON here at all")]}
    parsed = _parse_json_output(fake_result)
    assert "error" in parsed
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
python -m pytest tests/test_stock_tools.py::test_parse_json_output_extracts_json_from_message tests/test_stock_tools.py::test_parse_json_output_returns_error_on_no_json -v
```

Expected: Fail with `ModuleNotFoundError: No module named 'agents.stock_agents'`.

- [ ] **Step 3: Create `agents/stock_agents.py`**

```python
import json
import re
from agents.base import build_agent
from tools.stock_tools import get_market_data, get_news_sentiment, get_macro_indicators

_QUANT_PROMPT = """Kamu adalah The Quant — analis kuantitatif yang presisi dan berbasis data.
Tugasmu: Gunakan tool get_market_data untuk mengambil data saham yang diminta, lalu hasilkan
ringkasan fundamental dan teknikal dalam Bahasa Indonesia profesional.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "summary": "ringkasan 3-4 kalimat kondisi fundamental dan teknikal",
  "current_price": 0.0,
  "pe_ratio": "nilai atau N/A",
  "roe": "nilai atau N/A",
  "debt_to_equity": "nilai atau N/A",
  "price_change_1y": "nilai% atau N/A",
  "technical_trend": "bullish/bearish/sideways — alasan singkat 1 kalimat",
  "ohlcv": {},
  "macro_correlation": {}
}
"""

_NEWSROOM_PROMPT = """Kamu adalah The Newsroom — jurnalis investigatif finansial yang kritis.
Tugasmu: Gunakan tool get_news_sentiment untuk mencari 10 berita terbaru tentang ticker yang diberikan,
lalu analisis sentimen pasar dalam Bahasa Indonesia profesional.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "summary": "ringkasan sentimen pasar 3-4 kalimat",
  "sentiment_score": 0.0,
  "key_themes": ["tema1", "tema2", "tema3"],
  "risk_signals": ["isu atau rumor negatif"],
  "positive_signals": ["katalis positif atau peluang"]
}

sentiment_score: -1.0 (sangat negatif) hingga +1.0 (sangat positif).
"""

_ECONOMIST_PROMPT = """Kamu adalah The Economist — macro strategist yang melihat big picture.
Tugasmu: Gunakan tool get_macro_indicators untuk mengambil data makro, lalu analisis bagaimana
kondisi makroekonomi mempengaruhi saham target dalam Bahasa Indonesia profesional.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "summary": "konteks makro 3-4 kalimat relevan ke saham target",
  "interest_rate_impact": "dampak suku bunga saat ini terhadap saham ini",
  "commodity_impact": "dampak harga komoditas (jika relevan)",
  "market_correlation": "korelasi saham ini dengan pasar global",
  "macro_verdict": "favorable/neutral/unfavorable"
}
"""

_CRITIC_PROMPT = """Kamu adalah The Critic — quality controller dan devil's advocate investasi.
Kamu menerima output dari tiga analis (Quant, Newsroom, Economist) sebagai konteks dalam pesan.
Tugasmu: Gabungkan semua insight, tantang asumsi yang lemah, lalu susun laporan investasi final
dalam Bahasa Indonesia profesional yang objektif.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "executive_summary": "2-3 kalimat kondisi saham saat ini secara menyeluruh",
  "fundamental_analysis": "paragraph analisis fundamental dan teknikal yang tajam",
  "sentiment_macro": "paragraph gabungan sentimen berita dan konteks makro",
  "risk_assessment": "3-5 risiko utama yang bisa membatalkan tesis investasi ini",
  "counter_arguments": "1-2 argumen devil's advocate — apa yang bisa membuat tesis ini salah",
  "verdict": "BUY",
  "verdict_reasoning": "1 kalimat alasan verdict yang jelas dan tegas"
}

verdict hanya boleh: BUY, HOLD, atau SELL.
"""


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


def run_quant(ticker: str) -> dict:
    agent = build_agent(_QUANT_PROMPT, [get_market_data])
    result = agent.invoke({"messages": [{"role": "user", "content": f"Analisis saham: {ticker}"}]})
    data = _parse_json_output(result)
    # Preserve ohlcv + macro_correlation for charting even if parsing is partial
    return data


def run_newsroom(ticker: str) -> dict:
    agent = build_agent(_NEWSROOM_PROMPT, [get_news_sentiment])
    result = agent.invoke({
        "messages": [{"role": "user", "content": f"Cari berita dan analisis sentimen pasar untuk: {ticker}"}]
    })
    return _parse_json_output(result)


def run_economist(quant_output: dict) -> dict:
    agent = build_agent(_ECONOMIST_PROMPT, [get_macro_indicators])
    context = json.dumps({k: v for k, v in quant_output.items() if k != "ohlcv"}, ensure_ascii=False)
    result = agent.invoke({
        "messages": [{"role": "user", "content": f"Analisis konteks makro. Data saham: {context}"}]
    })
    return _parse_json_output(result)


def run_critic(ticker: str, quant: dict, newsroom: dict, economist: dict) -> dict:
    agent = build_agent(_CRITIC_PROMPT, [])
    combined = json.dumps({
        "ticker":    ticker,
        "quant":     {k: v for k, v in quant.items() if k != "ohlcv"},
        "newsroom":  newsroom,
        "economist": economist,
    }, ensure_ascii=False)
    result = agent.invoke({
        "messages": [{"role": "user", "content": f"Buat laporan investasi final: {combined}"}]
    })
    return _parse_json_output(result)
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
python -m pytest tests/test_stock_tools.py::test_parse_json_output_extracts_json_from_message tests/test_stock_tools.py::test_parse_json_output_returns_error_on_no_json -v
```

Expected: Both pass.

- [ ] **Step 5: Commit**

```bash
git add agents/stock_agents.py tests/test_stock_tools.py
git commit -m "feat(stock): add 4 LangChain stock agents — Quant, Newsroom, Economist, Critic"
```

---

## Task 4: SSE Endpoint + Static Route (`server.py`)

**Files:**
- Modify: `server.py`

- [ ] **Step 1: Write failing test for the endpoint**

Create `tests/test_stock_endpoint.py`:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
import json


@pytest.fixture
def client():
    from server import app
    return TestClient(app)


def test_stock_analyze_missing_ticker(client):
    resp = client.get("/api/stock/analyze")
    assert resp.status_code == 422  # FastAPI validation: missing required query param


def test_stock_analyze_invalid_ticker_too_long(client):
    resp = client.get("/api/stock/analyze?ticker=" + "X" * 21)
    assert resp.status_code == 400


def test_stock_page_served(client):
    resp = client.get("/stock")
    # Either 200 (file exists) or redirect — not 404 or 500
    assert resp.status_code in (200, 307, 308)
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
python -m pytest tests/test_stock_endpoint.py -v
```

Expected: `test_stock_analyze_missing_ticker` and `test_stock_analyze_invalid_ticker_too_long` fail (endpoint doesn't exist yet).

- [ ] **Step 3: Add imports to `server.py`**

At the top of `server.py`, after the existing imports, add:

```python
import asyncio
```

(Check if `asyncio` is already imported — if so, skip this step.)

- [ ] **Step 4: Add Plotly helper import + SSE helper to `server.py`**

Find the line in `server.py`:

```python
# ─── CrewAI Multi-Agent Endpoints ────────────────────────────────────────────
```

Insert the following block **above** that line:

```python
# ─── Stock Terminal ───────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/api/stock/analyze")
async def stock_analyze(ticker: str):
    if not ticker or len(ticker) > 20:
        raise HTTPException(status_code=400, detail="Invalid ticker symbol")

    async def generate():
        try:
            from agents.stock_agents import run_quant, run_newsroom, run_economist, run_critic
            from tools.stock_tools import build_candlestick_json, build_heatmap_json, build_python_code
            loop = asyncio.get_event_loop()

            # ── Phase 1: Quant (sequential) ───────────────────────────
            yield _sse({"event": "step", "agent": "Quant", "status": "running"})
            quant_data = await loop.run_in_executor(None, run_quant, ticker)
            price   = quant_data.get("current_price", "N/A")
            pe      = quant_data.get("pe_ratio", "N/A")
            change  = quant_data.get("price_change_1y", "N/A")
            trend   = quant_data.get("technical_trend", "N/A")
            yield _sse({"event": "log", "text": f"Harga: {price} | P/E: {pe} | Perubahan 1Y: {change}"})
            yield _sse({"event": "log", "text": f"Tren Teknikal: {trend}"})
            yield _sse({"event": "step", "agent": "Quant", "status": "done"})

            # ── Phase 2: Newsroom + Economist (parallel) ───────────────
            yield _sse({"event": "step", "agent": "Newsroom", "status": "running"})
            yield _sse({"event": "step", "agent": "Economist", "status": "running"})
            newsroom_data, economist_data = await asyncio.gather(
                loop.run_in_executor(None, run_newsroom, ticker),
                loop.run_in_executor(None, run_economist, quant_data),
            )
            sentiment = newsroom_data.get("sentiment_score", "N/A")
            macro_v   = economist_data.get("macro_verdict", "N/A")
            yield _sse({"event": "log", "text": f"Skor Sentimen: {sentiment} | Makro: {macro_v}"})
            yield _sse({"event": "step", "agent": "Newsroom",  "status": "done"})
            yield _sse({"event": "step", "agent": "Economist", "status": "done"})

            # ── Phase 3: Critic (sequential) ───────────────────────────
            yield _sse({"event": "step", "agent": "Critic", "status": "running"})
            critic_data = await loop.run_in_executor(
                None, run_critic, ticker, quant_data, newsroom_data, economist_data
            )
            yield _sse({"event": "step", "agent": "Critic", "status": "done"})

            # ── Charts + code ──────────────────────────────────────────
            ohlcv = quant_data.get("ohlcv", {})
            corr  = quant_data.get("macro_correlation", {})
            candlestick_json = build_candlestick_json(ticker, ohlcv)
            heatmap_json     = build_heatmap_json(ticker, corr)
            python_code      = build_python_code(ticker, ohlcv, corr)

            yield _sse({"event": "chart", "candlestick": candlestick_json, "heatmap": heatmap_json})
            yield _sse({"event": "code",  "python": python_code})

            # ── Final report ───────────────────────────────────────────
            report = {
                "executive_summary": critic_data.get("executive_summary", ""),
                "fundamental":       quant_data.get("summary",    "") + "\n\n" + critic_data.get("fundamental_analysis", ""),
                "sentiment":         newsroom_data.get("summary", "") + "\n\n" + economist_data.get("summary", "") + "\n\n" + critic_data.get("sentiment_macro", ""),
                "risk":              critic_data.get("risk_assessment", "") + "\n\n" + critic_data.get("counter_arguments", ""),
                "verdict":          critic_data.get("verdict", "HOLD"),
                "verdict_reasoning": critic_data.get("verdict_reasoning", ""),
            }
            yield _sse({"event": "done", "report": report})

        except Exception as e:
            yield _sse({"event": "error", "message": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

```

- [ ] **Step 5: Add `/stock` static route**

Find the line near the bottom of `server.py` that mounts static files. Look for:

```python
app.mount("/", StaticFiles(directory="static/index", html=True), name="static")
```

**Insert** the following line **before** that mount (order matters — more specific paths first):

```python
app.mount("/stock", StaticFiles(directory="static/stock", html=True), name="stock")
```

Also create the directory so FastAPI doesn't error on startup:

```bash
mkdir -p static/stock
```

- [ ] **Step 6: Run tests — verify they pass**

```bash
python -m pytest tests/test_stock_endpoint.py -v
```

Expected: All 3 tests pass. (`test_stock_page_served` returns 404 until Task 5 adds the HTML — that's acceptable; change its assertion to `assert resp.status_code != 500` if needed.)

- [ ] **Step 7: Commit**

```bash
git add server.py tests/test_stock_endpoint.py
git commit -m "feat(stock): add SSE /api/stock/analyze endpoint + /stock static mount"
```

---

## Task 5: Frontend (`static/stock/index.html`)

**Files:**
- Create: `static/stock/index.html`

No automated tests — this is a UI. Manual verification steps are at the end.

- [ ] **Step 1: Create the Bloomberg terminal page**

Create `static/stock/index.html`:

```html
<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CassanovaL Terminal — Stock Analysis</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:       #0a0a0f;
    --bg2:      #0d0d14;
    --bg3:      #12121a;
    --border:   #1e1e2e;
    --text:     #c0c0d0;
    --text-dim: #606080;
    --green:    #00ff88;
    --red:      #ff4444;
    --yellow:   #ffcc00;
    --blue:     #4488ff;
    --font:     'JetBrains Mono', monospace;
  }

  html, body { height: 100%; overflow: hidden; background: var(--bg); color: var(--text); font-family: var(--font); font-size: 13px; }

  /* ── Header ── */
  #header {
    display: flex; align-items: center; gap: 16px;
    padding: 10px 20px;
    background: var(--bg2); border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  #header .brand { color: var(--green); font-weight: 700; font-size: 14px; letter-spacing: 2px; }
  #header .sep   { color: var(--border); font-size: 18px; }
  #header .title { color: var(--text-dim); font-size: 12px; letter-spacing: 1px; }
  #header .spacer { flex: 1; }
  #live-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--text-dim); transition: background 0.3s; }
  #live-dot.active { background: var(--green); box-shadow: 0 0 6px var(--green); }
  #live-label { color: var(--text-dim); font-size: 11px; }

  /* ── Ticker Bar ── */
  #ticker-bar {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 20px;
    background: var(--bg3); border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  #ticker-bar label { color: var(--text-dim); font-size: 11px; letter-spacing: 1px; }
  #ticker-input {
    background: var(--bg2); border: 1px solid var(--border); color: var(--green);
    font-family: var(--font); font-size: 14px; font-weight: 700;
    padding: 6px 12px; width: 200px; outline: none; letter-spacing: 2px;
    text-transform: uppercase;
  }
  #ticker-input:focus { border-color: var(--green); }
  #analyze-btn {
    background: var(--green); color: #000; border: none;
    font-family: var(--font); font-size: 12px; font-weight: 700;
    padding: 7px 18px; cursor: pointer; letter-spacing: 1px;
    transition: opacity 0.2s;
  }
  #analyze-btn:hover { opacity: 0.85; }
  #analyze-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  #back-link { color: var(--text-dim); font-size: 11px; text-decoration: none; margin-left: auto; }
  #back-link:hover { color: var(--text); }

  /* ── Main Layout ── */
  #main {
    display: flex; height: calc(100vh - 86px); overflow: hidden;
  }

  /* ── Agent Feed (left 35%) ── */
  #feed-panel {
    width: 35%; min-width: 280px; max-width: 420px;
    border-right: 1px solid var(--border);
    display: flex; flex-direction: column;
    background: var(--bg2);
  }
  #feed-header {
    padding: 10px 16px; border-bottom: 1px solid var(--border);
    color: var(--text-dim); font-size: 11px; letter-spacing: 2px;
  }
  #agent-status { padding: 12px 16px; border-bottom: 1px solid var(--border); }
  .agent-row {
    display: flex; align-items: center; gap: 8px;
    padding: 5px 0; font-size: 12px; color: var(--text-dim);
  }
  .agent-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--border); flex-shrink: 0; transition: all 0.3s;
  }
  .agent-row.running .agent-dot { background: var(--yellow); box-shadow: 0 0 6px var(--yellow); animation: pulse 1s infinite; }
  .agent-row.done    .agent-dot { background: var(--green); }
  .agent-row.error   .agent-dot { background: var(--red); }
  .agent-row.running .agent-name { color: var(--yellow); }
  .agent-row.done    .agent-name { color: var(--green); }
  .agent-tick { margin-left: auto; font-size: 11px; }
  .agent-row.done .agent-tick::before    { content: "✓"; color: var(--green); }
  .agent-row.running .agent-tick::before { content: "⟳"; color: var(--yellow); }

  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }

  #log-stream {
    flex: 1; overflow-y: auto; padding: 10px 16px;
    font-size: 11px; line-height: 1.7;
  }
  #log-stream .log-line { color: var(--text-dim); }
  #log-stream .log-line::before { content: "> "; color: var(--green); }
  #log-stream .log-error { color: var(--red); }
  #log-stream .log-error::before { content: "✗ "; }

  /* ── Report Panel (right 65%) ── */
  #report-panel {
    flex: 1; display: flex; flex-direction: column; overflow: hidden;
    background: var(--bg);
  }
  #tab-bar {
    display: flex; border-bottom: 1px solid var(--border);
    background: var(--bg2); flex-shrink: 0;
  }
  .tab-btn {
    padding: 10px 20px; background: none; border: none;
    color: var(--text-dim); font-family: var(--font); font-size: 11px;
    letter-spacing: 1px; cursor: pointer; border-bottom: 2px solid transparent;
    transition: all 0.2s;
  }
  .tab-btn:hover   { color: var(--text); }
  .tab-btn.active  { color: var(--green); border-bottom-color: var(--green); }

  .tab-content { display: none; flex: 1; overflow-y: auto; padding: 20px; }
  .tab-content.active { display: block; }

  /* ── Summary Tab ── */
  .report-section { margin-bottom: 24px; }
  .report-section h3 {
    color: var(--text-dim); font-size: 10px; letter-spacing: 2px;
    text-transform: uppercase; margin-bottom: 8px;
    padding-bottom: 6px; border-bottom: 1px solid var(--border);
  }
  .report-section p { line-height: 1.8; color: var(--text); white-space: pre-wrap; }

  #verdict-box {
    margin-top: 8px; padding: 16px 24px;
    border: 1px solid var(--border); display: inline-block;
    font-size: 11px; letter-spacing: 1px;
  }
  #verdict-box .verdict-label { color: var(--text-dim); font-size: 10px; }
  #verdict-box .verdict-value { font-size: 28px; font-weight: 700; margin: 4px 0; }
  #verdict-box .verdict-reason { color: var(--text-dim); font-size: 11px; }
  #verdict-box.buy  { border-color: var(--green); }
  #verdict-box.buy  .verdict-value { color: var(--green); }
  #verdict-box.sell { border-color: var(--red); }
  #verdict-box.sell .verdict-value { color: var(--red); }
  #verdict-box.hold { border-color: var(--yellow); }
  #verdict-box.hold .verdict-value { color: var(--yellow); }

  #placeholder {
    height: 100%; display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    color: var(--text-dim); text-align: center; gap: 12px;
  }
  #placeholder .big { font-size: 32px; opacity: 0.3; }
  #placeholder p { font-size: 11px; letter-spacing: 1px; }

  /* ── Charts Tab ── */
  #chart-candlestick, #chart-heatmap {
    width: 100%; margin-bottom: 20px;
    background: var(--bg2); border: 1px solid var(--border);
  }

  /* ── Code Tab ── */
  #code-container { position: relative; }
  #copy-btn {
    position: absolute; top: 8px; right: 8px;
    background: var(--bg3); border: 1px solid var(--border);
    color: var(--text-dim); font-family: var(--font); font-size: 11px;
    padding: 4px 10px; cursor: pointer; letter-spacing: 1px;
    transition: all 0.2s;
  }
  #copy-btn:hover { border-color: var(--green); color: var(--green); }
  #copy-btn.copied { border-color: var(--green); color: var(--green); }
  #code-block {
    background: var(--bg2); border: 1px solid var(--border);
    padding: 20px 16px; overflow-x: auto;
    font-size: 12px; line-height: 1.7; white-space: pre; color: var(--text);
  }
  /* Minimal syntax highlighting via spans */
  .kw  { color: #c792ea; }
  .str { color: #c3e88d; }
  .cm  { color: var(--text-dim); font-style: italic; }
  .num { color: var(--yellow); }
</style>
</head>
<body>

<!-- ── Header ── -->
<div id="header">
  <span class="brand">CASSANOVAL</span>
  <span class="sep">|</span>
  <span class="title">STOCK ANALYSIS TERMINAL</span>
  <span class="spacer"></span>
  <div id="live-dot"></div>
  <span id="live-label">STANDBY</span>
</div>

<!-- ── Ticker Bar ── -->
<div id="ticker-bar">
  <label>TICKER</label>
  <input id="ticker-input" type="text" placeholder="BBCA.JK" maxlength="20" spellcheck="false">
  <button id="analyze-btn">▶ ANALYZE</button>
  <a href="/" id="back-link">← Kembali ke CassanovaL</a>
</div>

<!-- ── Main ── -->
<div id="main">

  <!-- Left: Agent Feed -->
  <div id="feed-panel">
    <div id="feed-header">AGENT FEED</div>
    <div id="agent-status">
      <div class="agent-row" id="row-Quant">
        <div class="agent-dot"></div>
        <span class="agent-name">The Quant</span>
        <span class="agent-tick"></span>
      </div>
      <div class="agent-row" id="row-Newsroom">
        <div class="agent-dot"></div>
        <span class="agent-name">The Newsroom</span>
        <span class="agent-tick"></span>
      </div>
      <div class="agent-row" id="row-Economist">
        <div class="agent-dot"></div>
        <span class="agent-name">The Economist</span>
        <span class="agent-tick"></span>
      </div>
      <div class="agent-row" id="row-Critic">
        <div class="agent-dot"></div>
        <span class="agent-name">The Critic</span>
        <span class="agent-tick"></span>
      </div>
    </div>
    <div id="log-stream"></div>
  </div>

  <!-- Right: Report Panel -->
  <div id="report-panel">
    <div id="tab-bar">
      <button class="tab-btn active" data-tab="summary">SUMMARY</button>
      <button class="tab-btn" data-tab="charts">CHARTS</button>
      <button class="tab-btn" data-tab="code">CODE</button>
    </div>

    <!-- Summary Tab -->
    <div id="tab-summary" class="tab-content active">
      <div id="placeholder">
        <div class="big">▶</div>
        <p>MASUKKAN TICKER DAN KLIK ANALYZE</p>
        <p style="opacity:0.5">Contoh: BBCA.JK, AAPL, TLKM.JK</p>
      </div>
      <div id="report-body" style="display:none">
        <div class="report-section" id="sec-executive">
          <h3>Executive Summary</h3>
          <p id="txt-executive"></p>
        </div>
        <div class="report-section" id="sec-fundamental">
          <h3>Fundamental &amp; Technical Deep Dive</h3>
          <p id="txt-fundamental"></p>
        </div>
        <div class="report-section" id="sec-sentiment">
          <h3>Sentiment &amp; Macro Context</h3>
          <p id="txt-sentiment"></p>
        </div>
        <div class="report-section" id="sec-risk">
          <h3>Risk Assessment</h3>
          <p id="txt-risk"></p>
        </div>
        <div class="report-section">
          <h3>Final Verdict</h3>
          <div id="verdict-box">
            <div class="verdict-label">REKOMENDASI</div>
            <div class="verdict-value" id="txt-verdict">—</div>
            <div class="verdict-reason" id="txt-verdict-reason"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Charts Tab -->
    <div id="tab-charts" class="tab-content">
      <div id="chart-candlestick" style="height:380px"></div>
      <div id="chart-heatmap" style="height:200px"></div>
    </div>

    <!-- Code Tab -->
    <div id="tab-code" class="tab-content">
      <div id="code-container">
        <button id="copy-btn">COPY</button>
        <pre id="code-block"><span style="color:var(--text-dim)">// Kode Python akan muncul setelah analisis selesai</span></pre>
      </div>
    </div>

  </div><!-- /report-panel -->
</div><!-- /main -->

<script>
// ── Tab switching ─────────────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
  });
});

// ── Copy button ───────────────────────────────────────────────────────────────
document.getElementById('copy-btn').addEventListener('click', () => {
  const code = document.getElementById('code-block').innerText;
  navigator.clipboard.writeText(code).then(() => {
    const btn = document.getElementById('copy-btn');
    btn.textContent = 'COPIED ✓';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = 'COPY'; btn.classList.remove('copied'); }, 2000);
  });
});

// ── SSE helpers ───────────────────────────────────────────────────────────────
let currentES = null;

function setLive(active) {
  document.getElementById('live-dot').classList.toggle('active', active);
  document.getElementById('live-label').textContent = active ? 'LIVE' : 'STANDBY';
}

function setAgentStatus(agent, status) {
  const row = document.getElementById('row-' + agent);
  if (!row) return;
  row.className = 'agent-row ' + status;
}

function appendLog(text, isError = false) {
  const el = document.createElement('div');
  el.className = isError ? 'log-error' : 'log-line';
  el.textContent = text;
  const stream = document.getElementById('log-stream');
  stream.appendChild(el);
  stream.scrollTop = stream.scrollHeight;
}

function resetUI() {
  ['Quant','Newsroom','Economist','Critic'].forEach(a => setAgentStatus(a, ''));
  document.getElementById('log-stream').innerHTML = '';
  document.getElementById('placeholder').style.display = 'flex';
  document.getElementById('report-body').style.display = 'none';
  document.getElementById('code-block').innerHTML =
    '<span style="color:var(--text-dim)">// Kode Python akan muncul setelah analisis selesai</span>';
  document.getElementById('chart-candlestick').innerHTML = '';
  document.getElementById('chart-heatmap').innerHTML = '';
}

function renderReport(report) {
  document.getElementById('placeholder').style.display = 'none';
  document.getElementById('report-body').style.display = 'block';
  document.getElementById('txt-executive').textContent    = report.executive_summary || '';
  document.getElementById('txt-fundamental').textContent  = report.fundamental || '';
  document.getElementById('txt-sentiment').textContent    = report.sentiment || '';
  document.getElementById('txt-risk').textContent         = report.risk || '';

  const verdict = (report.verdict || 'HOLD').toUpperCase();
  const box = document.getElementById('verdict-box');
  box.className = verdict.toLowerCase();
  document.getElementById('txt-verdict').textContent        = verdict;
  document.getElementById('txt-verdict-reason').textContent = report.verdict_reasoning || '';
}

function renderCharts(candlestick, heatmap) {
  if (candlestick && candlestick.data) {
    Plotly.newPlot('chart-candlestick', candlestick.data, candlestick.layout, {responsive: true, displayModeBar: false});
  }
  if (heatmap && heatmap.data) {
    Plotly.newPlot('chart-heatmap', heatmap.data, heatmap.layout, {responsive: true, displayModeBar: false});
  }
}

function highlightCode(raw) {
  return raw
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/(#[^\n]*)/g, '<span class="cm">$1</span>')
    .replace(/\b(import|from|as|def|return|for|in|if|not|and|or|True|False|None|with)\b/g, '<span class="kw">$1</span>')
    .replace(/"([^"]*)"/g, '<span class="str">"$1"</span>')
    .replace(/'([^']*)'/g, '<span class="str">\'$1\'</span>')
    .replace(/\b(-?\d+\.?\d*)\b/g, '<span class="num">$1</span>');
}

// ── Analyze ───────────────────────────────────────────────────────────────────
document.getElementById('analyze-btn').addEventListener('click', () => {
  const ticker = document.getElementById('ticker-input').value.trim().toUpperCase();
  if (!ticker) { appendLog('Masukkan ticker terlebih dahulu', true); return; }
  if (currentES) currentES.close();
  resetUI();
  document.getElementById('analyze-btn').disabled = true;
  setLive(true);
  appendLog(`Memulai analisis: ${ticker}...`);

  currentES = new EventSource(`/api/stock/analyze?ticker=${encodeURIComponent(ticker)}`);

  currentES.onmessage = (e) => {
    let msg;
    try { msg = JSON.parse(e.data); } catch { return; }

    switch (msg.event) {
      case 'step':
        setAgentStatus(msg.agent, msg.status);
        if (msg.status === 'running') appendLog(`${msg.agent} sedang bekerja...`);
        break;

      case 'log':
        appendLog(msg.text);
        break;

      case 'chart':
        renderCharts(msg.candlestick, msg.heatmap);
        break;

      case 'code':
        document.getElementById('code-block').innerHTML = highlightCode(msg.python || '');
        break;

      case 'done':
        renderReport(msg.report || {});
        document.getElementById('analyze-btn').disabled = false;
        setLive(false);
        currentES.close(); currentES = null;
        appendLog('Analisis selesai.');
        break;

      case 'error':
        appendLog(msg.message || 'Terjadi kesalahan', true);
        document.getElementById('analyze-btn').disabled = false;
        setLive(false);
        currentES.close(); currentES = null;
        break;
    }
  };

  currentES.onerror = () => {
    appendLog('Koneksi terputus.', true);
    document.getElementById('analyze-btn').disabled = false;
    setLive(false);
    if (currentES) { currentES.close(); currentES = null; }
  };
});

// Submit on Enter key
document.getElementById('ticker-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') document.getElementById('analyze-btn').click();
});
</script>
</body>
</html>
```

- [ ] **Step 2: Manual verification — start the server**

```bash
$env:PYTHONUTF8=1; python server.py
```

Open `http://localhost:8000/stock` in a browser.

Expected checklist:
- [ ] Page loads without console errors
- [ ] Black terminal background, green accents, monospace font visible
- [ ] Header shows "CASSANOVAL TERMINAL — STOCK ANALYSIS"
- [ ] Ticker input field and ANALYZE button are visible
- [ ] Three tabs (SUMMARY, CHARTS, CODE) visible on right panel
- [ ] "Kembali ke CassanovaL" link navigates to `/`

- [ ] **Step 3: Manual verification — run a real analysis**

Type `BBCA.JK` in the ticker input and click ANALYZE.

Expected checklist:
- [ ] LIVE dot turns green
- [ ] Agent Feed shows each agent progressing (yellow dot while running, green checkmark when done)
- [ ] Log lines appear in the feed as agents finish
- [ ] After ~30–90 seconds, Summary tab populates with Bahasa Indonesia text
- [ ] FINAL VERDICT box appears with BUY/HOLD/SELL in matching color
- [ ] Charts tab shows candlestick chart and heatmap
- [ ] Code tab shows Python code with syntax highlighting
- [ ] Copy button copies code to clipboard

- [ ] **Step 4: Test with a US ticker**

Type `AAPL` and click ANALYZE. Verify same flow completes without error.

- [ ] **Step 5: Test error case**

Type `INVALIDXYZ999` and click ANALYZE. Verify an error message appears in the feed without crashing.

- [ ] **Step 6: Commit**

```bash
git add static/stock/index.html
git commit -m "feat(stock): add Bloomberg terminal frontend — SSE-driven, dark theme, Plotly charts"
```

---

## Task 6: Final Integration Check

- [ ] **Step 1: Run all tests together**

```bash
python -m pytest tests/test_stock_tools.py tests/test_stock_endpoint.py -v
```

Expected: All tests pass.

- [ ] **Step 2: Verify server mounts order in `server.py`**

Check that `static/stock` mount appears **before** the root `static/index` mount. If the root mount catches `/stock` first, the page won't load.

Correct order (bottom of `server.py`):
```python
app.mount("/stock", StaticFiles(directory="static/stock", html=True), name="stock")
app.mount("/", StaticFiles(directory="static/index", html=True), name="static")
```

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat(stock): Bloomberg-style stock terminal — 4-agent SSE pipeline complete"
```
