import json
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage


def _fake_result(output_dict: dict):
    return {"messages": [AIMessage(content=json.dumps(output_dict))]}


def test_run_news_gatherer_returns_news():
    from agents.nostradamus_pipeline import run_news_gatherer
    fake = {"news": [{"headline": "Test headline", "source": "BBC", "date": "2026-05-26", "summary": "A test."}]}
    with patch("agents.nostradamus_pipeline.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_result(fake)
        mock_build.return_value = mock_agent
        result = run_news_gatherer("US-China trade war")
    assert "news" in result
    assert isinstance(result["news"], list)
    assert result["news"][0]["headline"] == "Test headline"


def test_run_predictor_returns_prediction_keys():
    from agents.nostradamus_pipeline import run_predictor, PREDICTORS
    fake = {
        "agent_id": "trend", "agent_name": "Trend Analyst",
        "prediction_title": "Escalation likely",
        "prediction": "Tariffs will increase.", "confidence": 72,
        "reasoning": "Current momentum points to further escalation."
    }
    with patch("agents.nostradamus_pipeline.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_result(fake)
        mock_build.return_value = mock_agent
        result = run_predictor(PREDICTORS[0], "US-China trade war", "News summary here.")
    for key in ("agent_id", "agent_name", "prediction_title", "prediction", "confidence", "reasoning"):
        assert key in result


def test_run_council_returns_verdict_keys():
    from agents.nostradamus_pipeline import run_council
    fake = {
        "verdict_title": "Trade war intensifies",
        "verdict_detail": "Based on all evidence, escalation is most probable.",
        "confidence": 75, "endorsed_agent": "Trend Analyst",
        "dissenting_view": "Risk Assessor sees a chance of sudden de-escalation."
    }
    predictions = [{"agent_name": "Trend Analyst", "prediction_title": "Escalation", "prediction": "...", "confidence": 72}]
    with patch("agents.nostradamus_pipeline.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_result(fake)
        mock_build.return_value = mock_agent
        result = run_council("US-China trade war", predictions)
    for key in ("verdict_title", "verdict_detail", "confidence", "endorsed_agent", "dissenting_view"):
        assert key in result


def test_run_predictor_handles_unparseable_response():
    from agents.nostradamus_pipeline import run_predictor, PREDICTORS
    with patch("agents.nostradamus_pipeline.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": [MagicMock(content="Maaf, tidak bisa memproses ini.")]}
        mock_build.return_value = mock_agent
        result = run_predictor(PREDICTORS[0], "test event", "test news")
    assert "error" in result


def test_run_council_handles_unparseable_response():
    from agents.nostradamus_pipeline import run_council
    with patch("agents.nostradamus_pipeline.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": [MagicMock(content="Tidak bisa memproses prediksi.")]}
        mock_build.return_value = mock_agent
        result = run_council("test event", [])
    assert "error" in result
