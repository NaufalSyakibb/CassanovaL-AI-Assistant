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
        from ddgs import DDGS
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
        if hist.empty and "." not in ticker:
            ticker = ticker + ".JK"
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

        # volume_anomaly uses date-string heuristics tuned for Serper ("2 hours ago").
        # DDG returns ISO dates; anomaly will always be False with DDG fallback.
        recent_count = sum(
            1 for a in articles
            if any(k in a.get("date", "").lower() for k in ("hour", "min", "second"))
        )
        volume_anomaly = recent_count >= 5

        return json.dumps({"articles": articles, "volume_anomaly": volume_anomaly})
    except Exception as e:
        return json.dumps({"articles": [], "volume_anomaly": False, "error": str(e)})


@tool
def get_technical_indicators(ticker: str) -> str:
    """
    Compute technical analysis indicators: RSI(14), MACD(12,26,9), Bollinger Bands(20),
    Moving Averages (MA20/50/200), support/resistance, and volume trend.
    Args:
        ticker: Stock ticker symbol (e.g. 'BBCA.JK', 'AAPL').
    Returns:
        JSON with all indicator values, status labels, and cross signals.
    """
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="1y")
        if (hist.empty or len(hist) < 30) and "." not in ticker:
            ticker = ticker + ".JK"
            tk = yf.Ticker(ticker)
            hist = tk.history(period="1y")
        if hist.empty or len(hist) < 30:
            return json.dumps({"error": f"Not enough data for '{ticker}'"})

        hist = hist.dropna()
        close = hist["Close"]
        vol   = hist["Volume"]
        current_price = float(close.iloc[-1])

        # ── RSI(14) via EWM ───────────────────────────────────────────────────
        delta     = close.diff()
        avg_gain  = delta.where(delta > 0, 0.0).ewm(com=13, adjust=False).mean()
        avg_loss  = (-delta.where(delta < 0, 0.0)).ewm(com=13, adjust=False).mean()
        rs        = avg_gain / avg_loss.replace(0, float("nan"))
        rsi_val   = round(float((100 - 100 / (1 + rs)).iloc[-1]), 2)
        if rsi_val < 30:        rsi_status = "oversold"
        elif rsi_val > 70:      rsi_status = "overbought"
        elif rsi_val < 45:      rsi_status = "approaching_oversold"
        elif rsi_val > 55:      rsi_status = "approaching_overbought"
        else:                   rsi_status = "neutral"

        # ── MACD(12, 26, 9) ───────────────────────────────────────────────────
        macd_line   = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram   = macd_line - signal_line
        hist_now, hist_prev = float(histogram.iloc[-1]), float(histogram.iloc[-2])
        if hist_prev < 0 <= hist_now:           macd_signal = "bullish_crossover"
        elif hist_prev > 0 >= hist_now:         macd_signal = "bearish_crossover"
        elif hist_now > 0 and hist_now > hist_prev: macd_signal = "bullish_accelerating"
        elif hist_now > 0:                      macd_signal = "bullish_decelerating"
        elif hist_now < 0 and hist_now < hist_prev: macd_signal = "bearish_accelerating"
        else:                                   macd_signal = "bearish_decelerating"

        # ── Bollinger Bands(20, ±2σ) ──────────────────────────────────────────
        bb_mid = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        bb_up  = round(float((bb_mid + 2 * bb_std).iloc[-1]), 2)
        bb_mid_val = round(float(bb_mid.iloc[-1]), 2)
        bb_lo  = round(float((bb_mid - 2 * bb_std).iloc[-1]), 2)
        bb_pct = (current_price - bb_lo) / (bb_up - bb_lo) if bb_up != bb_lo else 0.5
        if bb_pct < 0.10:      bb_position = "at_lower_band"
        elif bb_pct < 0.30:    bb_position = "near_lower_band"
        elif bb_pct > 0.90:    bb_position = "at_upper_band"
        elif bb_pct > 0.70:    bb_position = "near_upper_band"
        else:                  bb_position = "mid_range"

        # ── Moving Averages ───────────────────────────────────────────────────
        def _ma(n):
            return round(float(close.rolling(n).mean().iloc[-1]), 2) if len(close) >= n else None

        ma20, ma50, ma200 = _ma(20), _ma(50), _ma(200)

        def _vs(ma):
            if ma is None: return "n/a"
            pct = (current_price - ma) / ma * 100
            if pct > 3:   return f"above +{round(pct,1)}%"
            if pct < -3:  return f"below {round(pct,1)}%"
            return f"near {round(pct,1)}%"

        # Golden / Death cross
        cross_signal = None
        if ma50 and ma200 and len(close) >= 202:
            ma50_p  = float(close.rolling(50).mean().iloc[-2])
            ma200_p = float(close.rolling(200).mean().iloc[-2])
            if ma50 > ma200 and ma50_p <= ma200_p:   cross_signal = "golden_cross"
            elif ma50 < ma200 and ma50_p >= ma200_p: cross_signal = "death_cross"

        # ── Support / Resistance (60-session range) ───────────────────────────
        recent = hist.tail(60)
        support    = round(float(recent["Low"].min()), 2)
        resistance = round(float(recent["High"].max()), 2)

        # ── Volume trend ──────────────────────────────────────────────────────
        vol_ratio = round(float(vol.tail(5).mean()) / float(vol.tail(20).mean()), 2)
        if vol_ratio > 1.3:   volume_trend = "expanding"
        elif vol_ratio < 0.7: volume_trend = "contracting"
        else:                 volume_trend = "neutral"

        return json.dumps({
            "ticker":           ticker,
            "current_price":    round(current_price, 2),
            "rsi_14":           rsi_val,
            "rsi_status":       rsi_status,
            "macd_line":        round(float(macd_line.iloc[-1]), 4),
            "macd_signal_line": round(float(signal_line.iloc[-1]), 4),
            "macd_histogram":   round(hist_now, 4),
            "macd_signal":      macd_signal,
            "bb_upper":         bb_up,
            "bb_mid":           bb_mid_val,
            "bb_lower":         bb_lo,
            "bb_position":      bb_position,
            "ma20":             ma20,
            "ma50":             ma50,
            "ma200":            ma200,
            "price_vs_ma20":    _vs(ma20),
            "price_vs_ma50":    _vs(ma50),
            "price_vs_ma200":   _vs(ma200),
            "cross_signal":     cross_signal,
            "support_60d":      support,
            "resistance_60d":   resistance,
            "volume_trend":     volume_trend,
            "volume_ratio":     vol_ratio,
            "pct_above_52w_low": round((current_price / float(hist["Low"].min()) - 1) * 100, 1),
            "pct_below_52w_high": round((1 - current_price / float(hist["High"].max())) * 100, 1),
        }, default=float)
    except Exception as e:
        return json.dumps({"error": str(e)})


STOCK_TOOLS = [get_market_data, get_news_sentiment, get_technical_indicators]


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
