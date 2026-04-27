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
