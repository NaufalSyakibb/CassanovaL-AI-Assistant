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
    fake_out = {
        "entry_zone": "100-105", "exit_target": "120",
        "stop_loss": "95", "stop_loss_pct": 5.0,
        "time_horizon": "medium", "time_horizon_detail": "3 bulan",
        "position_size": "5%", "risk_reward_ratio": "1:3",
        "rationale": "test",
    }
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
