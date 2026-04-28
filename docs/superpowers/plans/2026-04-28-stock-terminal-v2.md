# Stock Terminal v2 — Enhanced Agent Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 4 Bloomberg Terminal agents (Quant/Newsroom/Economist/Critic) with DeepResearch/NewsIntelligence/Strategy/FinalVerdict, adding a Trading Strategy section (entry/exit/stop loss) and a conviction score to the UI.

**Architecture:** Approach A — Incremental Replacement. Same SSE pipeline in `server.py`, same `static/stock/index.html` shell, same `agents/base.py`. Only 4 files change: `tools/stock_tools.py` (tool upgrades), `agents/stock_agents.py` (new prompts + run_* functions), `server.py` (new SSE event calls), `static/stock/index.html` (new tabs + conviction UI).

**Tech Stack:** yfinance, pandas, langchain-mistralai, LangGraph, FastAPI SSE, vanilla JS, Plotly.js

---

## File Map

| File | Change |
|------|--------|
| `tools/stock_tools.py` | Upgrade `get_market_data` (5yr financials + analyst targets), upgrade `get_news_sentiment` (15 articles + event_type + volume_anomaly), remove `get_macro_indicators` |
| `agents/stock_agents.py` | Rewrite 4 `run_*` functions + prompts; keep `_parse_json_output` and `_invoke_with_retry` unchanged |
| `server.py` | Update SSE endpoint: new agent imports/calls, 2 new SSE events (`strategy`, `verdict`), updated `report` dict |
| `static/stock/index.html` | Rename agent rows, add STRATEGY + VERDICT tabs, conviction bar, bull/bear case |
| `tests/test_stock_tools.py` | Update/add tests for upgraded tools, remove macro_indicators test |
| `tests/test_stock_agents.py` | New file — tests for new run_* functions |

---

## Task 1: Upgrade `get_market_data`

**Files:**
- Modify: `tools/stock_tools.py`
- Test: `tests/test_stock_tools.py`

- [ ] **Step 1: Write failing tests for new fields**

Add to `tests/test_stock_tools.py`:

```python
def _make_fake_financials():
    """Return a minimal fake yfinance financials DataFrame (rows=items, cols=dates)."""
    fake_dates = pd.to_datetime(["2023-12-31", "2022-12-31", "2021-12-31"])
    return pd.DataFrame({
        fake_dates[0]: [1_200_000, 140_000],
        fake_dates[1]: [1_100_000, 120_000],
        fake_dates[2]: [1_000_000, 100_000],
    }, index=["Total Revenue", "Net Income"])


def test_get_market_data_includes_new_fields():
    from tools.stock_tools import get_market_data
    fake_hist = _make_hist_df()
    fake_fin = _make_fake_financials()

    with patch("yfinance.Ticker") as MockTicker:
        inst = MockTicker.return_value
        inst.history.return_value = fake_hist
        inst.info = {}
        inst.financials = fake_fin
        inst.balance_sheet = pd.DataFrame()
        inst.cashflow = pd.DataFrame()
        inst.analyst_price_targets = {"mean": 115.0, "high": 130.0, "low": 95.0}
        inst.recommendations = pd.DataFrame()

        raw = get_market_data.invoke("BBCA.JK")
        data = json.loads(raw)

    assert "financials" in data
    assert "growth_trend" in data
    assert "analyst_consensus" in data


def test_get_market_data_analyst_consensus_price_target():
    from tools.stock_tools import get_market_data
    fake_hist = _make_hist_df()
    fake_fin = _make_fake_financials()

    with patch("yfinance.Ticker") as MockTicker:
        inst = MockTicker.return_value
        inst.history.return_value = fake_hist
        inst.info = {}
        inst.financials = fake_fin
        inst.balance_sheet = pd.DataFrame()
        inst.cashflow = pd.DataFrame()
        inst.analyst_price_targets = {"mean": 115.0, "high": 130.0, "low": 95.0}
        inst.recommendations = pd.DataFrame()

        raw = get_market_data.invoke("AAPL")
        data = json.loads(raw)

    assert data["analyst_consensus"].get("price_target_mean") == 115.0
    assert data["analyst_consensus"].get("price_target_high") == 130.0


def test_get_market_data_revenue_cagr_computed():
    from tools.stock_tools import get_market_data
    fake_hist = _make_hist_df()
    fake_fin = _make_fake_financials()

    with patch("yfinance.Ticker") as MockTicker:
        inst = MockTicker.return_value
        inst.history.return_value = fake_hist
        inst.info = {}
        inst.financials = fake_fin
        inst.balance_sheet = pd.DataFrame()
        inst.cashflow = pd.DataFrame()
        inst.analyst_price_targets = {}
        inst.recommendations = pd.DataFrame()

        raw = get_market_data.invoke("AAPL")
        data = json.loads(raw)

    # revenue grows 1.0M → 1.2M over 2 years: CAGR = (1.2/1.0)^(1/2) - 1 ≈ 9.54%
    cagr = data["growth_trend"].get("revenue_cagr_pct")
    assert cagr is not None
    assert 9.0 < cagr < 11.0
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_stock_tools.py::test_get_market_data_includes_new_fields tests/test_stock_tools.py::test_get_market_data_analyst_consensus_price_target tests/test_stock_tools.py::test_get_market_data_revenue_cagr_computed -v
```

Expected: `FAILED` — `KeyError` or `AssertionError` since the fields don't exist yet.

- [ ] **Step 3: Add `_classify_financials` helper + upgrade `get_market_data`**

In `tools/stock_tools.py`, add this helper after `_fetch_ddg` and before the `@tool` decorators:

```python
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
                    n = len(vals) - 1
                    growth["revenue_cagr_pct"] = round(
                        ((vals[0] / vals[-1]) ** (1 / n) - 1) * 100, 2
                    )

            if ni_row is not None and rev_row is not None:
                nis = ni_row[cols].dropna()
                fin_summary["net_income_3yr"] = {str(k.date()): int(v) for k, v in nis.items()}
                margins = []
                for col in cols:
                    if col in rev_row.index and col in ni_row.index:
                        r = float(rev_row.get(col) or 0)
                        n = float(ni_row.get(col) or 0)
                        if r != 0:
                            margins.append(round(n / r * 100, 2))
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
                eq_v   = float(eq_row.get(c0) or 1)
                debt_v = float(debt_row.get(c0) or 0)
                bal_summary["debt_to_equity_computed"] = round(debt_v / eq_v, 3) if eq_v != 0 else None
    except Exception:
        pass

    try:
        cf = tk.cashflow
        if cf is not None and not cf.empty:
            cols = cf.columns[:3]
            fcf_row = next(
                (cf.loc[k] for k in ("Free Cash Flow", "Capital Expenditure") if k in cf.index),
                None
            )
            if fcf_row is not None:
                cf_summary["fcf_3yr"] = {str(k.date()): int(v) for k, v in fcf_row[cols].dropna().items()}
    except Exception:
        pass

    return fin_summary, bal_summary, cf_summary, growth
```

Then replace the `get_market_data` function body (keep the `@tool` decorator and docstring, replace from `try:` to the end):

```python
@tool
def get_market_data(ticker: str, period: str = "1y") -> str:
    """
    Fetch historical OHLCV, key financial ratios, 5-year financial statements,
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
                col = latest_recs.columns[0] if not latest_recs.empty else None
                if col:
                    counts = latest_recs[col].value_counts().to_dict()
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
            "financials":       fin_summary,
            "balance_sheet":    bal_summary,
            "cashflow":         cf_summary,
            "growth_trend":     growth,
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
```

- [ ] **Step 4: Run the new tests to verify they pass**

```
pytest tests/test_stock_tools.py::test_get_market_data_includes_new_fields tests/test_stock_tools.py::test_get_market_data_analyst_consensus_price_target tests/test_stock_tools.py::test_get_market_data_revenue_cagr_computed -v
```

Expected: `PASSED`

- [ ] **Step 5: Verify existing tests still pass**

```
pytest tests/test_stock_tools.py::test_get_market_data_returns_valid_dict tests/test_stock_tools.py::test_get_market_data_empty_ticker_returns_error -v
```

Note: These tests mock `inst.history` but don't set `inst.financials` etc. The new code wraps each financials call in `try/except`, so AttributeError is silently caught and those fields return `{}`. Tests should still pass.

If they fail with `AttributeError: Mock object has no attribute 'financials'`, update the test's `with patch` block:

```python
inst.financials = pd.DataFrame()
inst.balance_sheet = pd.DataFrame()
inst.cashflow = pd.DataFrame()
inst.analyst_price_targets = {}
inst.recommendations = pd.DataFrame()
```

- [ ] **Step 6: Commit**

```bash
git add tools/stock_tools.py tests/test_stock_tools.py
git commit -m "feat(stock): upgrade get_market_data — 5yr financials, analyst targets, CAGR trends"
```

---

## Task 2: Upgrade `get_news_sentiment` + remove `get_macro_indicators`

**Files:**
- Modify: `tools/stock_tools.py`
- Test: `tests/test_stock_tools.py`

- [ ] **Step 1: Write failing tests for the upgraded news sentiment**

Add to `tests/test_stock_tools.py`:

```python
def test_get_news_sentiment_returns_dict_with_articles_and_anomaly():
    from tools.stock_tools import get_news_sentiment
    fake_serper_resp = MagicMock()
    fake_serper_resp.status_code = 200
    fake_serper_resp.json.return_value = {
        "news": [
            {"title": "BBCA naik", "source": "Kompas", "snippet": "Saham naik setelah earnings", "date": "2 hours ago"},
            {"title": "Merger deal", "source": "Bloomberg", "snippet": "acquisition talks", "date": "1 hour ago"},
        ]
    }

    with patch("os.getenv", return_value="FAKE_KEY"), \
         patch("requests.post", return_value=fake_serper_resp):
        raw = get_news_sentiment.invoke("BBCA")
        result = json.loads(raw)

    assert "articles" in result
    assert "volume_anomaly" in result
    assert isinstance(result["articles"], list)
    assert isinstance(result["volume_anomaly"], bool)


def test_get_news_sentiment_classifies_event_type():
    from tools.stock_tools import get_news_sentiment
    fake_serper_resp = MagicMock()
    fake_serper_resp.status_code = 200
    fake_serper_resp.json.return_value = {
        "news": [
            {"title": "Quarterly earnings beat expectations", "source": "Reuters",
             "snippet": "revenue and EPS exceeded estimates", "date": "3 hours ago"},
        ]
    }

    with patch("os.getenv", return_value="FAKE_KEY"), \
         patch("requests.post", return_value=fake_serper_resp):
        raw = get_news_sentiment.invoke("AAPL earnings")
        result = json.loads(raw)

    article = result["articles"][0]
    assert article["event_type"] == "earnings"


def test_get_news_sentiment_volume_anomaly_true_when_many_recent():
    from tools.stock_tools import get_news_sentiment
    fake_serper_resp = MagicMock()
    fake_serper_resp.status_code = 200
    # 6 articles from within the last hour → anomaly
    fake_serper_resp.json.return_value = {
        "news": [
            {"title": f"News {i}", "source": "X", "snippet": "snippet", "date": "30 minutes ago"}
            for i in range(6)
        ]
    }

    with patch("os.getenv", return_value="FAKE_KEY"), \
         patch("requests.post", return_value=fake_serper_resp):
        raw = get_news_sentiment.invoke("BBCA")
        result = json.loads(raw)

    assert result["volume_anomaly"] is True


def test_get_macro_indicators_removed_from_stock_tools():
    from tools import stock_tools
    assert not hasattr(stock_tools, "get_macro_indicators") or \
           "get_macro_indicators" not in [t.name for t in stock_tools.STOCK_TOOLS]
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_stock_tools.py::test_get_news_sentiment_returns_dict_with_articles_and_anomaly tests/test_stock_tools.py::test_get_news_sentiment_classifies_event_type tests/test_stock_tools.py::test_get_news_sentiment_volume_anomaly_true_when_many_recent tests/test_stock_tools.py::test_get_macro_indicators_removed_from_stock_tools -v
```

Expected: `FAILED`

- [ ] **Step 3: Add `_EVENT_KEYWORDS` constant + `_classify_event` helper**

In `tools/stock_tools.py`, add after `_fetch_ddg` and before `_summarize_financials`:

```python
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
```

- [ ] **Step 4: Replace `get_news_sentiment` function + remove `get_macro_indicators`**

Replace the `get_news_sentiment` function in `tools/stock_tools.py`:

```python
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
```

Then delete the entire `get_macro_indicators` function (lines starting with `@tool` and `def get_macro_indicators`).

Update `STOCK_TOOLS` at the bottom:

```python
STOCK_TOOLS = [get_market_data, get_news_sentiment]
```

- [ ] **Step 5: Remove the test for `get_macro_indicators` + update existing news tests**

In `tests/test_stock_tools.py`:

1. Delete the entire `test_get_macro_indicators_returns_four_symbols` test function.

2. Update `test_get_news_sentiment_uses_serper_when_available` to match new structure:

```python
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
        result = json.loads(raw)

    assert "articles" in result
    assert result["articles"][0]["title"] == "BBCA naik"


def test_get_news_sentiment_falls_back_to_ddg():
    from tools.stock_tools import get_news_sentiment
    fake_ddg_result = [{"title": "DDG news", "source": "Bloomberg", "body": "snippet", "date": "2025-01-01"}]

    with patch("os.getenv", return_value=""), \
         patch("duckduckgo_search.DDGS") as MockDDGS:
        MockDDGS.return_value.__enter__.return_value.news.return_value = fake_ddg_result
        raw = get_news_sentiment.invoke("BBCA")
        result = json.loads(raw)

    assert "articles" in result
    assert isinstance(result["articles"], list)
```

- [ ] **Step 6: Run all news tests to verify they pass**

```
pytest tests/test_stock_tools.py -k "news_sentiment or macro_indicators" -v
```

Expected: all new tests `PASSED`, `test_get_macro_indicators_returns_four_symbols` no longer exists.

- [ ] **Step 7: Run all stock tool tests to confirm nothing regressed**

```
pytest tests/test_stock_tools.py -v
```

Expected: all `PASSED`

- [ ] **Step 8: Commit**

```bash
git add tools/stock_tools.py tests/test_stock_tools.py
git commit -m "feat(stock): upgrade get_news_sentiment (event_type + volume_anomaly), remove get_macro_indicators"
```

---

## Task 3: Rewrite `agents/stock_agents.py`

**Files:**
- Rewrite: `agents/stock_agents.py`
- Create: `tests/test_stock_agents.py`

- [ ] **Step 1: Create `tests/test_stock_agents.py` with failing tests**

```python
import json
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage


def _fake_agent_result(output_dict: dict):
    return {"messages": [AIMessage(content=json.dumps(output_dict))]}


# ── run_deep_research ──────────────────────────────────────────

def test_run_deep_research_returns_expected_keys():
    from agents.stock_agents import run_deep_research
    fake_out = {
        "summary": "fundamental solid",
        "valuation": "P/E 14x",
        "growth_trend": "CAGR 18%",
        "financial_health": "debt rendah",
        "analyst_consensus": "target 110",
        "macro_context": "favorable",
        "current_price": 100.0,
        "ohlcv": {},
        "macro_correlation": {},
    }
    with patch("agents.stock_agents.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(fake_out)
        mock_build.return_value = mock_agent
        result = run_deep_research("BBCA.JK")

    assert result["current_price"] == 100.0
    assert "growth_trend" in result
    assert "analyst_consensus" in result


# ── run_news_intelligence ──────────────────────────────────────

def test_run_news_intelligence_returns_expected_keys():
    from agents.stock_agents import run_news_intelligence
    fake_out = {
        "summary": "sentimen positif",
        "sentiment_score": 0.6,
        "event_type": "earnings",
        "key_events": ["Laba Q1 naik 20%"],
        "risk_signals": [],
        "catalyst_signals": ["Ekspansi pasar baru"],
        "anomaly_detected": False,
    }
    with patch("agents.stock_agents.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(fake_out)
        mock_build.return_value = mock_agent
        result = run_news_intelligence("BBCA.JK")

    assert result["sentiment_score"] == 0.6
    assert "event_type" in result
    assert "anomaly_detected" in result


# ── run_strategy ───────────────────────────────────────────────

def test_run_strategy_returns_expected_keys():
    from agents.stock_agents import run_strategy
    fake_out = {
        "entry_zone": "9500-9800",
        "exit_target": "11000",
        "stop_loss": "9000",
        "stop_loss_pct": 5.0,
        "time_horizon": "medium",
        "time_horizon_detail": "3-6 bulan",
        "position_size": "5%",
        "risk_reward_ratio": "1:3.0",
        "rationale": "Support kuat di 9500",
    }
    dr = {"summary": "ok", "ohlcv": {}, "current_price": 9700.0}
    ni = {"summary": "ok", "sentiment_score": 0.5}

    with patch("agents.stock_agents.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(fake_out)
        mock_build.return_value = mock_agent
        result = run_strategy(dr, ni)

    assert "entry_zone" in result
    assert "exit_target" in result
    assert "stop_loss" in result
    assert "risk_reward_ratio" in result


def test_run_strategy_strips_ohlcv_from_context():
    """Strategy agent must NOT receive raw ohlcv data (token efficiency)."""
    from agents.stock_agents import run_strategy
    fake_out = {"entry_zone": "100-105", "exit_target": "120",
                "stop_loss": "95", "stop_loss_pct": 5.0,
                "time_horizon": "medium", "time_horizon_detail": "3 bulan",
                "position_size": "5%", "risk_reward_ratio": "1:3",
                "rationale": "test"}
    dr = {"summary": "ok", "ohlcv": {"dates": ["2024-01-01"] * 250, "close": [100.0] * 250}}
    ni = {"summary": "ok"}

    captured_content = []

    def capture_invoke(messages):
        captured_content.append(messages["messages"][0]["content"])
        return _fake_agent_result(fake_out)

    with patch("agents.stock_agents.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.side_effect = capture_invoke
        mock_build.return_value = mock_agent
        run_strategy(dr, ni)

    assert "ohlcv" not in captured_content[0]


# ── run_final_verdict ──────────────────────────────────────────

def test_run_final_verdict_returns_expected_keys():
    from agents.stock_agents import run_final_verdict
    fake_out = {
        "executive_summary": "saham menarik",
        "fundamental_analysis": "fundamental solid",
        "sentiment_macro": "berita positif",
        "risk_assessment": ["Risiko 1", "Risiko 2"],
        "counter_arguments": "valuasi sudah mahal",
        "bull_case": ["Pertumbuhan kuat"],
        "bear_case": ["Tekanan margin"],
        "verdict": "BUY",
        "conviction_score": 7,
        "risk_reward": "1:3.5",
        "investment_memo": "Tesis investasi solid",
    }
    dr = {"summary": "ok", "ohlcv": {}}
    ni = {"summary": "ok", "sentiment_score": 0.5}
    st = {"entry_zone": "100-105", "exit_target": "120"}

    with patch("agents.stock_agents.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(fake_out)
        mock_build.return_value = mock_agent
        result = run_final_verdict("BBCA.JK", dr, ni, st)

    assert result["verdict"] in ("BUY", "HOLD", "SELL")
    assert isinstance(result["conviction_score"], int)
    assert "bull_case" in result
    assert "bear_case" in result
    assert "investment_memo" in result
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_stock_agents.py -v
```

Expected: `FAILED` — `ImportError: cannot import name 'run_deep_research'`

- [ ] **Step 3: Rewrite `agents/stock_agents.py`**

Replace the entire file content:

```python
import json
import re
import time
from agents.base import build_agent
from tools.stock_tools import get_market_data, get_news_sentiment


def _invoke_with_retry(agent, messages: dict, max_retries: int = 5) -> dict:
    """Invoke a LangGraph agent with exponential backoff on 429 rate-limit errors."""
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


_DEEP_RESEARCH_PROMPT = """Kamu adalah DeepResearch Agent — analis fundamental mendalam yang menggabungkan analisis kuantitatif dan konteks makroekonomi.
Tugasmu: Gunakan tool get_market_data untuk mengambil data lengkap saham target, termasuk laporan keuangan 5 tahun, target analis, dan korelasi makro. Hasilkan analisis komprehensif dalam Bahasa Indonesia profesional.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "summary": "ringkasan 3-4 kalimat kondisi fundamental, valuasi, dan konteks makro",
  "valuation": "analisis P/E, P/B, atau EV/EBITDA vs peers — mahal/murah/wajar",
  "growth_trend": "CAGR revenue 3 tahun terakhir dan tren margin (naik/stabil/turun)",
  "financial_health": "kondisi hutang, free cash flow, dan neraca keuangan",
  "analyst_consensus": "rata-rata target price analis dan distribusi rekomendasi",
  "macro_context": "dampak kondisi makro saat ini terhadap saham ini",
  "current_price": 0.0,
  "ohlcv": {},
  "macro_correlation": {}
}
"""

_NEWS_INTELLIGENCE_PROMPT = """Kamu adalah NewsIntelligence Agent — analis berita finansial yang cerdas dengan kemampuan deteksi sinyal tersembunyi.
Tugasmu: Gunakan tool get_news_sentiment untuk mengambil 15 berita terbaru tentang ticker yang diberikan. Analisis sentimen, klasifikasi event, dan deteksi anomali dalam Bahasa Indonesia profesional.

Data dari tool berisi field: articles (list dengan event_type per artikel) dan volume_anomaly (boolean).

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "summary": "ringkasan sentimen pasar 3-4 kalimat",
  "sentiment_score": 0.0,
  "event_type": "jenis event dominan: earnings/M&A/management/regulatory/macro/other",
  "key_events": ["event penting 1", "event penting 2"],
  "risk_signals": ["sinyal negatif atau risiko"],
  "catalyst_signals": ["katalis positif atau peluang"],
  "anomaly_detected": false
}

sentiment_score: -1.0 (sangat negatif) hingga +1.0 (sangat positif).
anomaly_detected: true jika volume_anomaly dari tool adalah true atau ada event major.
"""

_STRATEGY_PROMPT = """Kamu adalah Strategy Agent — ahli strategi trading yang terinspirasi dari metodologi ValueCell.
Kamu menerima output dari DeepResearch dan NewsIntelligence sebagai konteks dalam pesan.
Tugasmu: Berdasarkan analisis fundamental, teknikal, dan sentimen, susun strategi trading yang konkret dan actionable dalam Bahasa Indonesia profesional.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "entry_zone": "zona harga entry yang disarankan (mis. 9500-9800)",
  "exit_target": "target harga keluar berdasarkan resistance dan target analis",
  "stop_loss": "level stop loss yang disarankan",
  "stop_loss_pct": 0.0,
  "time_horizon": "short|medium|long",
  "time_horizon_detail": "estimasi durasi investasi (mis. 3-6 bulan)",
  "position_size": "rekomendasi % portofolio (mis. 5%)",
  "risk_reward_ratio": "rasio risk/reward (mis. 1:3.5)",
  "rationale": "1-2 kalimat alasan strategi ini berdasarkan data"
}

time_horizon: gunakan short (< 1 bulan), medium (1-6 bulan), atau long (> 6 bulan).
stop_loss_pct: persentase penurunan dari entry price sebagai stop loss (angka positif).
"""

_FINAL_VERDICT_PROMPT = """Kamu adalah FinalVerdict Agent — investment committee chairman yang bertindak sebagai devil's advocate.
Kamu menerima output dari DeepResearch, NewsIntelligence, dan Strategy sebagai konteks dalam pesan.
Tugasmu: Gabungkan semua insight, tantang setiap asumsi yang lemah, lalu susun laporan investasi final profesional dalam Bahasa Indonesia.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "executive_summary": "2-3 kalimat kondisi saham menyeluruh yang objektif",
  "fundamental_analysis": "paragraph analisis fundamental dan teknikal yang tajam",
  "sentiment_macro": "paragraph gabungan sentimen berita dan konteks makro",
  "risk_assessment": ["risiko utama 1", "risiko utama 2", "risiko utama 3"],
  "counter_arguments": "devil's advocate — 1-2 argumen mengapa tesis ini bisa salah",
  "bull_case": ["skenario positif 1", "skenario positif 2", "skenario positif 3"],
  "bear_case": ["skenario negatif 1", "skenario negatif 2", "skenario negatif 3"],
  "verdict": "BUY",
  "conviction_score": 7,
  "risk_reward": "1:3.5",
  "investment_memo": "memo investasi profesional 3-4 kalimat yang berisi tesis lengkap"
}

verdict hanya boleh: BUY, HOLD, atau SELL.
conviction_score: integer 1 (sangat tidak yakin) hingga 10 (sangat yakin).
"""


def run_deep_research(ticker: str) -> dict:
    agent = build_agent(_DEEP_RESEARCH_PROMPT, [get_market_data])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Lakukan analisis mendalam saham: {ticker}"}]
    })
    return _parse_json_output(result)


def run_news_intelligence(ticker: str) -> dict:
    agent = build_agent(_NEWS_INTELLIGENCE_PROMPT, [get_news_sentiment])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Analisis berita dan sentimen untuk saham: {ticker}"}]
    })
    return _parse_json_output(result)


def run_strategy(deep_research: dict, news_intelligence: dict) -> dict:
    agent = build_agent(_STRATEGY_PROMPT, [])
    context = json.dumps({
        "deep_research":    {k: v for k, v in deep_research.items() if k != "ohlcv"},
        "news_intelligence": news_intelligence,
    }, ensure_ascii=False)
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Susun strategi trading berdasarkan data ini: {context}"}]
    })
    return _parse_json_output(result)


def run_final_verdict(ticker: str, deep_research: dict, news_intelligence: dict, strategy: dict) -> dict:
    agent = build_agent(_FINAL_VERDICT_PROMPT, [])
    combined = json.dumps({
        "ticker":          ticker,
        "deep_research":   {k: v for k, v in deep_research.items() if k != "ohlcv"},
        "news_intelligence": news_intelligence,
        "strategy":        strategy,
    }, ensure_ascii=False)
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Buat laporan investasi final: {combined}"}]
    })
    return _parse_json_output(result)
```

- [ ] **Step 4: Run all agent tests**

```
pytest tests/test_stock_agents.py -v
```

Expected: all `PASSED`

- [ ] **Step 5: Confirm `_parse_json_output` tests still pass**

```
pytest tests/test_stock_tools.py::test_parse_json_output_extracts_json_from_message tests/test_stock_tools.py::test_parse_json_output_returns_error_on_no_json -v
```

Expected: `PASSED`

- [ ] **Step 6: Commit**

```bash
git add agents/stock_agents.py tests/test_stock_agents.py
git commit -m "feat(stock): replace 4 agents with DeepResearch/NewsIntelligence/Strategy/FinalVerdict"
```

---

## Task 4: Update `server.py` SSE endpoint

**Files:**
- Modify: `server.py:271-343`
- Test: `tests/test_stock_endpoint.py` (verify existing tests still pass)

- [ ] **Step 1: Replace the SSE `generate()` body in `server.py`**

Locate the `async def stock_analyze(ticker: str):` function (line ~271) and replace the entire `generate()` inner function with:

```python
    async def generate():
        try:
            from agents.stock_agents import (
                run_deep_research, run_news_intelligence,
                run_strategy, run_final_verdict,
            )
            from tools.stock_tools import build_candlestick_json, build_heatmap_json, build_python_code
            loop = asyncio.get_running_loop()

            # ── Phase 1: DeepResearch ─────────────────────────────────────
            yield _sse({"event": "step", "agent": "DeepResearch", "status": "running"})
            deep_research_data = await _run_agent(loop, run_deep_research, ticker)
            price  = deep_research_data.get("current_price", "N/A")
            growth = deep_research_data.get("growth_trend", "N/A")
            yield _sse({"event": "log", "text": f"Harga: {price} | Growth: {growth}"})
            yield _sse({"event": "step", "agent": "DeepResearch", "status": "done"})

            await asyncio.sleep(5)

            # ── Phase 2: NewsIntelligence ─────────────────────────────────
            yield _sse({"event": "step", "agent": "NewsIntelligence", "status": "running"})
            news_data = await _run_agent(loop, run_news_intelligence, ticker)
            sentiment  = news_data.get("sentiment_score", "N/A")
            event_type = news_data.get("event_type", "N/A")
            yield _sse({"event": "log", "text": f"Sentimen: {sentiment} | Event: {event_type}"})
            yield _sse({"event": "step", "agent": "NewsIntelligence", "status": "done"})

            await asyncio.sleep(5)

            # ── Phase 3: Strategy ─────────────────────────────────────────
            yield _sse({"event": "step", "agent": "Strategy", "status": "running"})
            strategy_data = await _run_agent(loop, run_strategy, deep_research_data, news_data)
            entry = strategy_data.get("entry_zone", "N/A")
            rr    = strategy_data.get("risk_reward_ratio", "N/A")
            yield _sse({"event": "strategy", "data": strategy_data})
            yield _sse({"event": "log", "text": f"Entry: {entry} | R/R: {rr}"})
            yield _sse({"event": "step", "agent": "Strategy", "status": "done"})

            await asyncio.sleep(5)

            # ── Phase 4: FinalVerdict ─────────────────────────────────────
            yield _sse({"event": "step", "agent": "FinalVerdict", "status": "running"})
            verdict_data = await _run_agent(
                loop, run_final_verdict, ticker, deep_research_data, news_data, strategy_data
            )
            yield _sse({"event": "verdict", "data": verdict_data})
            yield _sse({"event": "step", "agent": "FinalVerdict", "status": "done"})

            # ── Charts + code ─────────────────────────────────────────────
            ohlcv = deep_research_data.get("ohlcv", {})
            corr  = deep_research_data.get("macro_correlation", {})
            yield _sse({"event": "chart",
                        "candlestick": build_candlestick_json(ticker, ohlcv),
                        "heatmap":     build_heatmap_json(ticker, corr)})
            yield _sse({"event": "code", "python": build_python_code(ticker, ohlcv, corr)})

            # ── Final report ──────────────────────────────────────────────
            risk_list = verdict_data.get("risk_assessment", [])
            risk_text = "\n".join(risk_list) if isinstance(risk_list, list) else str(risk_list)
            report = {
                "executive_summary": verdict_data.get("executive_summary", ""),
                "fundamental":       deep_research_data.get("summary", "") + "\n\n" + verdict_data.get("fundamental_analysis", ""),
                "sentiment":         news_data.get("summary", "") + "\n\n" + verdict_data.get("sentiment_macro", ""),
                "risk":              risk_text + "\n\n" + verdict_data.get("counter_arguments", ""),
                "verdict":           verdict_data.get("verdict", "HOLD"),
                "conviction_score":  verdict_data.get("conviction_score", 5),
                "risk_reward":       verdict_data.get("risk_reward", ""),
                "bull_case":         verdict_data.get("bull_case", []),
                "bear_case":         verdict_data.get("bear_case", []),
                "investment_memo":   verdict_data.get("investment_memo", ""),
            }
            yield _sse({"event": "done", "report": report})

        except Exception as e:
            yield _sse({"event": "error", "message": str(e)})
```

- [ ] **Step 2: Run the existing endpoint tests**

```
pytest tests/test_stock_endpoint.py -v
```

Expected: `PASSED` — the tests only check 422 (missing ticker) and 400 (ticker too long), both unchanged.

- [ ] **Step 3: Commit**

```bash
git add server.py
git commit -m "feat(stock): update SSE endpoint — new agent calls, strategy/verdict events"
```

---

## Task 5: Update `static/stock/index.html` frontend

**Files:**
- Modify: `static/stock/index.html`

- [ ] **Step 1: Replace agent rows in HTML**

Find and replace the `<div id="agent-status">` block (lines ~222–243):

```html
    <div id="agent-status">
      <div class="agent-row" id="row-DeepResearch">
        <div class="agent-dot"></div>
        <span class="agent-name">DeepResearch</span>
        <span class="agent-tick"></span>
      </div>
      <div class="agent-row" id="row-NewsIntelligence">
        <div class="agent-dot"></div>
        <span class="agent-name">NewsIntelligence</span>
        <span class="agent-tick"></span>
      </div>
      <div class="agent-row" id="row-Strategy">
        <div class="agent-dot"></div>
        <span class="agent-name">Strategy</span>
        <span class="agent-tick"></span>
      </div>
      <div class="agent-row" id="row-FinalVerdict">
        <div class="agent-dot"></div>
        <span class="agent-name">FinalVerdict</span>
        <span class="agent-tick"></span>
      </div>
    </div>
```

- [ ] **Step 2: Add CSS for conviction bar, strategy cards, bull/bear case**

In the `<style>` block, after the `.cm { ... }` rule at the end, add:

```css
  /* ── Conviction bar ── */
  #conviction-bar {
    display: flex; gap: 3px; margin-top: 6px;
  }
  .conviction-block {
    width: 14px; height: 14px; border-radius: 2px;
    background: var(--border); transition: background 0.3s;
  }
  .conviction-block.filled-buy  { background: var(--green); }
  .conviction-block.filled-hold { background: var(--yellow); }
  .conviction-block.filled-sell { background: var(--red); }
  #conviction-label { color: var(--text-dim); font-size: 11px; margin-top: 4px; }

  /* ── Strategy tab ── */
  .strategy-cards {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px;
  }
  .strategy-card {
    padding: 14px; border: 1px solid var(--border); border-radius: 2px; text-align: center;
  }
  .strategy-card .card-label { color: var(--text-dim); font-size: 10px; letter-spacing: 1px; margin-bottom: 6px; }
  .strategy-card .card-value { font-size: 18px; font-weight: 700; }
  .strategy-card.entry  { border-color: var(--green); }
  .strategy-card.entry  .card-value { color: var(--green); }
  .strategy-card.exit   { border-color: var(--yellow); }
  .strategy-card.exit   .card-value { color: var(--yellow); }
  .strategy-card.stop   { border-color: var(--red); }
  .strategy-card.stop   .card-value { color: var(--red); }
  .strategy-meta {
    display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px;
  }
  .strategy-meta-item {
    background: var(--bg2); border: 1px solid var(--border); padding: 10px; border-radius: 2px;
  }
  .strategy-meta-item .meta-label { color: var(--text-dim); font-size: 10px; letter-spacing: 1px; margin-bottom: 4px; }
  .strategy-meta-item .meta-value { color: var(--text); font-size: 13px; }
  .position-bar-wrap { margin-top: 10px; background: var(--bg2); border: 1px solid var(--border); padding: 10px; border-radius: 2px; }
  .position-bar-track { height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; margin-top: 6px; }
  .position-bar-fill  { height: 100%; background: var(--yellow); border-radius: 3px; transition: width 0.5s; }

  /* ── Bull/Bear case ── */
  .bull-bear-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px; }
  .case-box { padding: 12px; border: 1px solid var(--border); border-radius: 2px; }
  .case-box.bull { border-color: #1a3a1a; background: #0d1a0d; }
  .case-box.bear { border-color: #3a1a1a; background: #1a0d0d; }
  .case-box h4 { font-size: 10px; letter-spacing: 1px; margin-bottom: 8px; }
  .case-box.bull h4 { color: var(--green); }
  .case-box.bear h4 { color: var(--red); }
  .case-box ul { padding-left: 14px; color: var(--text-dim); font-size: 11px; line-height: 1.8; }
  .investment-memo { padding: 12px; background: var(--bg2); border: 1px solid var(--border); border-radius: 2px; font-size: 12px; line-height: 1.7; color: var(--text); }
```

- [ ] **Step 3: Update tab bar HTML (add STRATEGY and VERDICT tabs)**

Replace the `<div id="tab-bar">` block:

```html
    <div id="tab-bar">
      <button class="tab-btn active" data-tab="summary">SUMMARY</button>
      <button class="tab-btn" data-tab="strategy">STRATEGY</button>
      <button class="tab-btn" data-tab="charts">CHARTS</button>
      <button class="tab-btn" data-tab="verdict">VERDICT</button>
      <button class="tab-btn" data-tab="code">CODE</button>
    </div>
```

- [ ] **Step 4: Add STRATEGY tab content + upgrade SUMMARY verdict box + add VERDICT tab**

After the `<!-- Summary Tab -->` section's closing `</div>` (right before `<!-- Charts Tab -->`), insert:

```html
    <!-- Strategy Tab -->
    <div id="tab-strategy" class="tab-content">
      <div id="strategy-placeholder" style="padding:40px;text-align:center;color:var(--text-dim);font-size:11px">
        Strategi akan muncul setelah Strategy agent selesai...
      </div>
      <div id="strategy-body" style="display:none">
        <div class="strategy-cards">
          <div class="strategy-card entry">
            <div class="card-label">ENTRY ZONE</div>
            <div class="card-value" id="st-entry">—</div>
          </div>
          <div class="strategy-card exit">
            <div class="card-label">EXIT TARGET</div>
            <div class="card-value" id="st-exit">—</div>
          </div>
          <div class="strategy-card stop">
            <div class="card-label">STOP LOSS</div>
            <div class="card-value" id="st-stop">—</div>
          </div>
        </div>
        <div class="strategy-meta">
          <div class="strategy-meta-item">
            <div class="meta-label">RISK / REWARD</div>
            <div class="meta-value" id="st-rr">—</div>
          </div>
          <div class="strategy-meta-item">
            <div class="meta-label">TIME HORIZON</div>
            <div class="meta-value" id="st-horizon">—</div>
          </div>
        </div>
        <div class="position-bar-wrap">
          <div class="meta-label">POSITION SIZING</div>
          <div class="position-bar-track">
            <div class="position-bar-fill" id="st-pos-bar" style="width:0%"></div>
          </div>
          <div style="color:var(--yellow);font-size:12px;margin-top:4px" id="st-pos-label">—</div>
        </div>
        <div class="report-section" style="margin-top:16px">
          <h3>Rationale</h3>
          <p id="st-rationale"></p>
        </div>
      </div>
    </div>
```

In the SUMMARY tab, update the `#verdict-box` to add conviction bar. Replace the `<div id="verdict-box">` block:

```html
          <div id="verdict-box">
            <div class="verdict-label">REKOMENDASI</div>
            <div class="verdict-value" id="txt-verdict">&#8212;</div>
            <div id="conviction-bar">
              <div class="conviction-block" id="cb-1"></div>
              <div class="conviction-block" id="cb-2"></div>
              <div class="conviction-block" id="cb-3"></div>
              <div class="conviction-block" id="cb-4"></div>
              <div class="conviction-block" id="cb-5"></div>
              <div class="conviction-block" id="cb-6"></div>
              <div class="conviction-block" id="cb-7"></div>
              <div class="conviction-block" id="cb-8"></div>
              <div class="conviction-block" id="cb-9"></div>
              <div class="conviction-block" id="cb-10"></div>
            </div>
            <div id="conviction-label"></div>
            <div class="verdict-reason" id="txt-verdict-reason"></div>
          </div>
```

After the `<!-- Charts Tab -->` closing `</div>` and before `<!-- Code Tab -->`, insert:

```html
    <!-- Verdict Tab -->
    <div id="tab-verdict" class="tab-content">
      <div id="verdict-placeholder" style="padding:40px;text-align:center;color:var(--text-dim);font-size:11px">
        Verdict lengkap akan muncul setelah FinalVerdict agent selesai...
      </div>
      <div id="verdict-body" style="display:none">
        <div class="bull-bear-grid">
          <div class="case-box bull">
            <h4>BULL CASE</h4>
            <ul id="bull-case-list"></ul>
          </div>
          <div class="case-box bear">
            <h4>BEAR CASE</h4>
            <ul id="bear-case-list"></ul>
          </div>
        </div>
        <div class="report-section">
          <h3>Investment Memo</h3>
          <div class="investment-memo" id="investment-memo"></div>
        </div>
        <div class="report-section">
          <h3>Counter Arguments</h3>
          <p id="counter-arguments"></p>
        </div>
      </div>
    </div>
```

- [ ] **Step 5: Update the JavaScript**

Replace the entire `<script>` block with:

```html
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

function appendLog(text, isError) {
  const el = document.createElement('div');
  el.className = isError ? 'log-error' : 'log-line';
  el.textContent = text;
  const stream = document.getElementById('log-stream');
  stream.appendChild(el);
  stream.scrollTop = stream.scrollHeight;
}

function resetUI() {
  ['DeepResearch', 'NewsIntelligence', 'Strategy', 'FinalVerdict'].forEach(a => setAgentStatus(a, ''));
  document.getElementById('log-stream').innerHTML = '';
  document.getElementById('placeholder').style.display = 'flex';
  document.getElementById('report-body').style.display = 'none';
  document.getElementById('strategy-placeholder').style.display = 'block';
  document.getElementById('strategy-body').style.display = 'none';
  document.getElementById('verdict-placeholder').style.display = 'block';
  document.getElementById('verdict-body').style.display = 'none';
  document.getElementById('code-block').innerHTML =
    '<span style="color:var(--text-dim)">// Kode Python akan muncul setelah analisis selesai</span>';
  document.getElementById('chart-candlestick').innerHTML = '';
  document.getElementById('chart-heatmap').innerHTML = '';
  for (let i = 1; i <= 10; i++) {
    const cb = document.getElementById('cb-' + i);
    if (cb) cb.className = 'conviction-block';
  }
}

function renderReport(report) {
  document.getElementById('placeholder').style.display = 'none';
  document.getElementById('report-body').style.display = 'block';
  document.getElementById('txt-executive').textContent   = report.executive_summary || '';
  document.getElementById('txt-fundamental').textContent = report.fundamental || '';
  document.getElementById('txt-sentiment').textContent   = report.sentiment || '';
  document.getElementById('txt-risk').textContent        = report.risk || '';

  const verdict = (report.verdict || 'HOLD').toUpperCase();
  const score   = parseInt(report.conviction_score || 5, 10);
  const box     = document.getElementById('verdict-box');
  box.className = verdict.toLowerCase();
  document.getElementById('txt-verdict').textContent        = verdict;
  document.getElementById('txt-verdict-reason').textContent = report.investment_memo || '';

  const colorClass = verdict === 'BUY' ? 'filled-buy' : verdict === 'SELL' ? 'filled-sell' : 'filled-hold';
  for (let i = 1; i <= 10; i++) {
    const cb = document.getElementById('cb-' + i);
    if (cb) cb.className = 'conviction-block' + (i <= score ? ' ' + colorClass : '');
  }
  document.getElementById('conviction-label').textContent =
    score + '/10 — ' + (score >= 8 ? 'Very High Conviction' : score >= 6 ? 'High Conviction' : score >= 4 ? 'Moderate' : 'Low Conviction');
}

function renderStrategy(data) {
  document.getElementById('strategy-placeholder').style.display = 'none';
  document.getElementById('strategy-body').style.display = 'block';
  document.getElementById('st-entry').textContent   = data.entry_zone    || '—';
  document.getElementById('st-exit').textContent    = data.exit_target   || '—';
  document.getElementById('st-stop').textContent    = data.stop_loss     || '—';
  document.getElementById('st-rr').textContent      = data.risk_reward_ratio || '—';
  const horizonDetail = data.time_horizon_detail
    ? data.time_horizon + ' (' + data.time_horizon_detail + ')'
    : (data.time_horizon || '—');
  document.getElementById('st-horizon').textContent = horizonDetail;
  const pct = parseFloat(data.position_size) || 0;
  document.getElementById('st-pos-bar').style.width  = Math.min(pct, 100) + '%';
  document.getElementById('st-pos-label').textContent = data.position_size || '—';
  document.getElementById('st-rationale').textContent = data.rationale || '';
}

function renderVerdict(data) {
  document.getElementById('verdict-placeholder').style.display = 'none';
  document.getElementById('verdict-body').style.display = 'block';
  const bullList = document.getElementById('bull-case-list');
  const bearList = document.getElementById('bear-case-list');
  bullList.innerHTML = '';
  bearList.innerHTML = '';
  (data.bull_case || []).forEach(item => {
    const li = document.createElement('li'); li.textContent = item; bullList.appendChild(li);
  });
  (data.bear_case || []).forEach(item => {
    const li = document.createElement('li'); li.textContent = item; bearList.appendChild(li);
  });
  document.getElementById('investment-memo').textContent   = data.investment_memo   || '';
  document.getElementById('counter-arguments').textContent = data.counter_arguments || '';
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
    .replace(/'([^']*)'/g, "<span class=\"str\">'$1'</span>")
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
  appendLog('Memulai analisis: ' + ticker + '...');

  currentES = new EventSource('/api/stock/analyze?ticker=' + encodeURIComponent(ticker));

  currentES.onmessage = (e) => {
    let msg;
    try { msg = JSON.parse(e.data); } catch { return; }

    switch (msg.event) {
      case 'step':
        setAgentStatus(msg.agent, msg.status);
        if (msg.status === 'running') appendLog(msg.agent + ' sedang bekerja...');
        break;
      case 'log':
        appendLog(msg.text);
        break;
      case 'strategy':
        renderStrategy(msg.data || {});
        break;
      case 'verdict':
        renderVerdict(msg.data || {});
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

document.getElementById('ticker-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') document.getElementById('analyze-btn').click();
});
</script>
```

- [ ] **Step 6: Run all tests one final time**

```
pytest tests/ -v
```

Expected: all `PASSED`

- [ ] **Step 7: Commit**

```bash
git add static/stock/index.html
git commit -m "feat(stock): update Bloomberg UI — STRATEGY tab, conviction bar, bull/bear case, new agent names"
```

---

## Final Verification

- [ ] **Start the server and test manually**

```
$env:PYTHONUTF8=1; python server.py
```

Open `http://localhost:8000/stock`, enter `AAPL` or `BBCA.JK`, click ANALYZE.

Verify:
1. Agent Feed shows: DeepResearch → NewsIntelligence → Strategy → FinalVerdict (green dots as each completes)
2. STRATEGY tab populates with entry zone / exit target / stop loss cards
3. VERDICT tab populates with bull case / bear case / investment memo
4. SUMMARY tab shows verdict + conviction bar (colored blocks)
5. CHARTS tab shows candlestick + heatmap
6. CODE tab shows copyable Python code

- [ ] **Final commit (if any last fixes needed)**

```bash
git add -p
git commit -m "fix(stock): final adjustments after manual testing"
```
