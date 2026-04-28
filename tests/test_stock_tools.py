import json
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd


# ── get_market_data ───────────────────────────────────────────

def _make_hist_df():
    """Return a minimal fake yfinance history DataFrame."""
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
