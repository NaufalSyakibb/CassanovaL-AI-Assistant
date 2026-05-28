import json
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage


def _fake_agent_result(output_dict: dict):
    return {"messages": [AIMessage(content=json.dumps(output_dict))]}


_VALID_OUTPUT = {
    "cover": {"hook": "Why do plants literally eat sunlight?"},
    "highlights": [
        "Chlorophyll absorbs light energy from the sun",
        "Water and CO2 combine to form glucose",
        "Oxygen is released as a byproduct",
        "Two stages: light reactions and Calvin cycle",
    ],
    "concepts": [
        {"term": "Chlorophyll", "def": "Green pigment absorbing solar energy"},
        {"term": "ATP", "def": "Energy currency produced in light reactions"},
        {"term": "Stroma", "def": "Site of the Calvin cycle in chloroplasts"},
        {"term": "NADPH", "def": "Electron carrier from light reactions"},
        {"term": "Glucose", "def": "Sugar produced by the Calvin cycle"},
        {"term": "Stomata", "def": "Pores that let CO2 enter the leaf"},
    ],
    "summary": "Photosynthesis converts light into chemical energy stored as glucose. It has two stages: light reactions produce ATP and NADPH, while the Calvin cycle uses them to fix CO2 into sugar.",
    "hashtags": ["#Photosynthesis", "#StudyTok", "#LearnWithMe", "#CornellNotes"],
}


def test_run_konten_agent_returns_required_keys():
    from agents.konten_agent import run_konten_agent
    with patch("agents.konten_agent.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(_VALID_OUTPUT)
        mock_build.return_value = mock_agent
        result = run_konten_agent(
            "Photosynthesis",
            {"sections": [{"title": "Overview", "content": "..."}]},
            {"concepts": [{"term": "Chlorophyll", "definition": "..."}]},
            {"summary": "Photosynthesis is..."},
        )
    for key in ("cover", "highlights", "concepts", "summary", "hashtags"):
        assert key in result, f"Missing key: {key}"
    assert "hook" in result["cover"]


def test_run_konten_agent_highlights_count():
    from agents.konten_agent import run_konten_agent
    with patch("agents.konten_agent.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(_VALID_OUTPUT)
        mock_build.return_value = mock_agent
        result = run_konten_agent("Photosynthesis", {}, {}, {})
    assert isinstance(result["highlights"], list)
    assert len(result["highlights"]) == 4


def test_run_konten_agent_handles_parse_error():
    from agents.konten_agent import run_konten_agent
    with patch("agents.konten_agent.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "messages": [AIMessage(content="Sorry, I cannot process that.")]
        }
        mock_build.return_value = mock_agent
        result = run_konten_agent("Photosynthesis", {}, {}, {})
    assert "error" in result
