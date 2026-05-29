import json
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage


def _fake_agent_result(output_dict: dict):
    return {"messages": [AIMessage(content=json.dumps(output_dict))]}


_VALID_OUTPUT = {
    "dominant_mood": "anxious",
    "mood_cat": "negative",
    "emotions": [
        {"name": "anxiety",   "intensity": 72},
        {"name": "fatigue",   "intensity": 58},
        {"name": "hope",      "intensity": 45},
        {"name": "gratitude", "intensity": 30},
    ],
    "what_happened": "Stressful meeting with manager. Called a friend after, felt lighter.",
    "summary": "Anxiety dominated most of the day. A thread of hope surfaced through social connection.",
}


def test_run_emotion_agent_returns_required_keys():
    from agents.emotion_agent import run_emotion_agent
    with patch("agents.emotion_agent.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(_VALID_OUTPUT)
        mock_build.return_value = mock_agent
        result = run_emotion_agent("2026-05-29", "Today was hard. I had a tough meeting...")
    for key in ("dominant_mood", "mood_cat", "emotions", "what_happened", "summary"):
        assert key in result, f"Missing key: {key}"
    assert isinstance(result["emotions"], list)
    assert len(result["emotions"]) > 0
    assert "name" in result["emotions"][0]
    assert "intensity" in result["emotions"][0]


def test_run_emotion_agent_emotions_structure():
    from agents.emotion_agent import run_emotion_agent
    with patch("agents.emotion_agent.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(_VALID_OUTPUT)
        mock_build.return_value = mock_agent
        result = run_emotion_agent("2026-05-29", "some journal text")
    for em in result["emotions"]:
        assert isinstance(em["name"], str)
        assert isinstance(em["intensity"], int)
        assert 0 <= em["intensity"] <= 100


def test_run_emotion_agent_handles_parse_error():
    from agents.emotion_agent import run_emotion_agent
    with patch("agents.emotion_agent.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "messages": [AIMessage(content="I cannot analyze this.")]
        }
        mock_build.return_value = mock_agent
        result = run_emotion_agent("2026-05-29", "some text")
    assert "error" in result
