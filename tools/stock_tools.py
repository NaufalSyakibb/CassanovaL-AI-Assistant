import os
import json
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
def get_market_data(ticker: str, period: str = "1y") -> str:
    """
    Fetch historical OHLCV + key financial ratios for a stock ticker.
    Args:
        ticker: Stock ticker symbol (e.g. 'BBCA.JK', 'AAPL').
        period: History period (default '1y'). Options: 1mo, 3mo, 6mo, 1y, 2y, 5y.
    Returns:
        JSON string with market data summary and OHLCV for charting.
    """
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period=period)
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
                mhist = yf.Ticker(symbol).history(period=period)
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
def get_news_sentiment(query: str, max_results: int = 10) -> str:
    """
    Search recent financial news about a stock or topic.
    Args:
        query: Search query (e.g. 'BBCA Bank Central Asia saham 2025').
        max_results: Maximum number of articles to return (default 10).
    Returns:
        JSON string — list of {title, source, snippet, date}.
    """
    try:
        articles = _fetch_serper(query, max_results)
        if not articles:
            articles = _fetch_ddg(query, max_results)
        return json.dumps(articles[:max_results])
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
