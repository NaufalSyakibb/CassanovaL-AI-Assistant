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


# ── Event classification ──────────────────────────────────────────────────────

_EVENT_KEYWORDS: dict[str, set[str]] = {
    "earnings":   {"earnings", "revenue", "profit", "eps", "quarterly", "results"},
    "M&A":        {"merger", "acquisition", "acquire", "takeover", "buyout"},
    "management": {"ceo", "cfo", "director", "resign", "appoint", "executive"},
    "regulatory": {"sec", "regulation", "fine", "lawsuit", "probe", "penalty"},
    "macro":      {"fed", "interest rate", "inflation", "gdp", "central bank"},
}


def _classify_event(title: str, snippet: str) -> str:
    """Classify a news article into an event type using keyword heuristics."""
    text = (title + " " + snippet).lower()
    for event_type, keywords in _EVENT_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return event_type
    return "other"


# ── LangChain tools ───────────────────────────────────────────────────────────

def _summarize_financials(tk) -> tuple[dict, dict, dict, dict]:
    """Extract financials/balance/cashflow summaries and compute growth trends."""
    fin_summary = {}
    bal_summary = {}
    cf_summary = {}
    growth = {}

    try:
        fin = tk.financials
        if fin is not None and not fin.empty:
            cols = fin.columns[:3]
            rev_row = fin.loc["Total Revenue"] if "Total Revenue" in fin.index else None
            ni_row  = fin.loc["Net Income"]    if "Net Income"    in fin.index else None

            if rev_row is not None:
                revs = rev_row[cols].dropna()
                fin_summary["revenue_3yr"] = {str(k.date()): int(v) for k, v in revs.items()}
                vals = revs.tolist()
                if len(vals) >= 2 and vals[-1] not in (0, None):
                    n_years = len(vals) - 1
                    growth["revenue_cagr_pct"] = round(
                        ((vals[0] / vals[-1]) ** (1 / n_years) - 1) * 100, 2
                    )

            if ni_row is not None and rev_row is not None:
                nis = ni_row[cols].dropna()
                fin_summary["net_income_3yr"] = {str(k.date()): int(v) for k, v in nis.items()}
                margins = []
                for col in cols:
                    if col in rev_row.index and col in ni_row.index:
                        r = float(rev_row.get(col) or 0)
                        ni_val = float(ni_row.get(col) or 0)
                        if r != 0:
                            margins.append(round(ni_val / r * 100, 2))
                growth["net_margin_trend_pct"] = margins
    except Exception:
        pass

    try:
        bs = tk.balance_sheet
        if bs is not None and not bs.empty:
            cols = bs.columns[:3]
            eq_row = next(
                (bs.loc[k] for k in ("Stockholders Equity", "Total Stockholder Equity", "Common Stock Equity") if k in bs.index),
                None
            )
            ni_row_bs = None
            try:
                f = tk.financials
                if f is not None and not f.empty and "Net Income" in f.index:
                    ni_row_bs = f.loc["Net Income"]
            except Exception:
                pass

            if eq_row is not None and ni_row_bs is not None:
                roe_list = []
                for col in cols:
                    eq  = float(eq_row.get(col) or 0)
                    ni_ = float(ni_row_bs.get(col) if col in ni_row_bs.index else 0 or 0)
                    if eq != 0:
                        roe_list.append(round(ni_ / eq * 100, 2))
                growth["roe_trend_pct"] = roe_list

            debt_row = next(
                (bs.loc[k] for k in ("Total Debt", "Long Term Debt And Capital Lease Obligation") if k in bs.index),
                None
            )
            if debt_row is not None and eq_row is not None:
                c0 = cols[0]
                eq_v   = float(eq_row.get(c0) or 0)
                debt_v = float(debt_row.get(c0) or 0)
                bal_summary["debt_to_equity_computed"] = round(debt_v / eq_v, 3) if eq_v != 0 else None
    except Exception:
        pass

    try:
        cf = tk.cashflow
        if cf is not None and not cf.empty:
            cols = cf.columns[:3]
            if "Free Cash Flow" in cf.index:
                fcf_row = cf.loc["Free Cash Flow"]
                cf_summary["fcf_3yr"] = {str(k.date()): int(v) for k, v in fcf_row[cols].dropna().items()}
    except Exception:
        pass

    return fin_summary, bal_summary, cf_summary, growth


@tool
def get_market_data(ticker: str, period: str = "1y") -> str:
    """
    Fetch historical OHLCV, key financial ratios, 3-year financial statements,
    analyst price targets, and macro correlations for a stock ticker.
    Args:
        ticker: Stock ticker symbol (e.g. 'BBCA.JK', 'AAPL').
        period: History period (default '1y'). Options: 1mo, 3mo, 6mo, 1y, 2y, 5y.
    Returns:
        JSON string with market data, fundamentals, and OHLCV for charting.
    """
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period=period)
        if hist.empty:
            return json.dumps({"error": f"No data found for ticker '{ticker}'"})

        hist = hist.dropna()
        latest = hist.iloc[-1]
        info = tk.info or {}

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

        fin_summary, bal_summary, cf_summary, growth = _summarize_financials(tk)

        analyst_data = {}
        try:
            targets = tk.analyst_price_targets
            if isinstance(targets, dict):
                analyst_data["price_target_mean"] = round(float(targets.get("mean") or 0), 2)
                analyst_data["price_target_high"] = round(float(targets.get("high") or 0), 2)
                analyst_data["price_target_low"]  = round(float(targets.get("low")  or 0), 2)
        except Exception:
            pass

        try:
            recs = tk.recommendations
            if recs is not None and not recs.empty:
                latest_recs = recs.tail(10)
                grade_col = "To Grade" if "To Grade" in latest_recs.columns else (latest_recs.columns[0] if not latest_recs.empty else None)
                if grade_col:
                    counts = latest_recs[grade_col].value_counts().to_dict()
                    analyst_data["recommendation_counts"] = {str(k): int(v) for k, v in counts.items()}
        except Exception:
            pass

        summary = {
            "ticker": ticker,
            "current_price": round(float(latest["Close"]), 2),
            "52w_high": round(float(hist["High"].max()), 2),
            "52w_low":  round(float(hist["Low"].min()),  2),
            "avg_volume_30d": int(hist["Volume"].tail(30).mean()),
            "pe_ratio":       info.get("trailingPE"),
            "roe":            info.get("returnOnEquity"),
            "debt_to_equity": info.get("debtToEquity"),
            "market_cap":     info.get("marketCap"),
            "price_change_1y_pct": round(
                (float(latest["Close"]) - float(hist.iloc[0]["Close"])) / float(hist.iloc[0]["Close"]) * 100, 2
            ) if float(hist.iloc[0]["Close"]) != 0 else None,
            "financials":        fin_summary,
            "balance_sheet":     bal_summary,
            "cashflow":          cf_summary,
            "growth_trend":      growth,
            "analyst_consensus": analyst_data,
            "macro_correlation": corr,
            "ohlcv": {
                "dates":  hist.index.strftime("%Y-%m-%d").tolist(),
                "open":   hist["Open"].round(2).tolist(),
                "high":   hist["High"].round(2).tolist(),
                "low":    hist["Low"].round(2).tolist(),
                "close":  hist["Close"].round(2).tolist(),
                "volume": hist["Volume"].tolist(),
            },
        }
        return json.dumps(summary, default=float)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_news_sentiment(query: str, max_results: int = 15) -> str:
    """
    Search recent financial news about a stock, classify by event type, and detect volume anomalies.
    Args:
        query: Search query (e.g. 'BBCA Bank Central Asia saham 2025').
        max_results: Maximum number of articles to return (default 15).
    Returns:
        JSON string — {"articles": [...], "volume_anomaly": bool}.
        Each article has: title, source, snippet, date, event_type.
    """
    try:
        articles = _fetch_serper(query, max_results)
        if not articles:
            articles = _fetch_ddg(query, max_results)

        articles = articles[:max_results]

        for article in articles:
            article["event_type"] = _classify_event(
                article.get("title", ""), article.get("snippet", "")
            )

        recent_count = sum(
            1 for a in articles
            if any(k in a.get("date", "").lower() for k in ("hour", "min", "second"))
        )
        volume_anomaly = recent_count >= 5

        return json.dumps({"articles": articles, "volume_anomaly": volume_anomaly})
    except Exception as e:
        return json.dumps({"error": str(e)})


STOCK_TOOLS = [get_market_data, get_news_sentiment]


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
    if not corr:
        return {"data": [], "layout": {"paper_bgcolor": "#0a0a0f", "title": {"text": "Korelasi tidak tersedia"}}}
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
    safe_ticker = ticker.replace('"', '').replace("'", '').replace(';', '').replace('\n', '')[:20]
    return f"""import plotly.graph_objects as go

# ── Data {safe_ticker} ──────────────────────────────────────────────
dates  = {json.dumps(ohlcv.get('dates', []))}
open_  = {json.dumps(ohlcv.get('open',  []))}
high   = {json.dumps(ohlcv.get('high',  []))}
low    = {json.dumps(ohlcv.get('low',   []))}
close  = {json.dumps(ohlcv.get('close', []))}

# ── Candlestick Chart ──────────────────────────────────────────
fig1 = go.Figure(data=[go.Candlestick(
    x=dates, open=open_, high=high, low=low, close=close,
    name="{safe_ticker}",
    increasing_line_color="#00ff88",
    decreasing_line_color="#ff4444",
)])
fig1.update_layout(
    title="{safe_ticker} — Harga 1 Tahun",
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
    y=["{safe_ticker}"],
    colorscale=[[0, "#ff4444"], [0.5, "#333340"], [1, "#00ff88"]],
    zmin=-1, zmax=1,
    text=[[f"{{v:+.2f}}" for v in corr_values]],
    texttemplate="%{{text}}",
))
fig2.update_layout(
    title="{safe_ticker} — Korelasi vs Indikator Makro (1 Tahun)",
    template="plotly_dark",
)
fig2.show()
"""
