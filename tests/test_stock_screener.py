import json
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage


def _fake_agent_result(output_dict: dict):
    return {"messages": [AIMessage(content=json.dumps(output_dict))]}


def test_run_pick_screener_returns_expected_keys():
    from agents.stock_screener import run_pick_screener
    fake_out = {
        "verdict": "BUY",
        "conviction_score": 8,
        "rationale": "Saham ini undervalued dengan P/E rendah.",
        "key_catalyst": "Permintaan baja meningkat.",
        "risk_factor": "Siklus komoditas.",
        "pe_ratio": 11.2,
        "rsi": 42.1,
    }
    with patch("agents.stock_screener.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(fake_out)
        mock_build.return_value = mock_agent
        result = run_pick_screener("NUE")

    assert result["verdict"] in ("BUY", "WATCH", "SKIP")
    assert "conviction_score" in result
    assert "rationale" in result
    assert "key_catalyst" in result
    assert "risk_factor" in result
    assert "pe_ratio" in result
    assert "rsi" in result
    assert result["ticker"] == "NUE"


def test_run_pick_screener_injects_ticker_into_result():
    from agents.stock_screener import run_pick_screener
    fake_out = {
        "verdict": "WATCH",
        "conviction_score": 6,
        "rationale": "Valuasi menarik tapi tunggu.",
        "key_catalyst": "Ekspansi pasar.",
        "risk_factor": "Kompetisi tinggi.",
        "pe_ratio": 14.5,
        "rsi": 55.0,
    }
    with patch("agents.stock_screener.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(fake_out)
        mock_build.return_value = mock_agent
        result = run_pick_screener("DVN")

    assert result["ticker"] == "DVN"
