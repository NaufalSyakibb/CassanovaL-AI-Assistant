import json
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage


def _fake_agent_result(output_dict: dict):
    return {"messages": [AIMessage(content=json.dumps(output_dict))]}


# ── run_materi_agent ───────────────────────────────────────────

def test_run_materi_agent_returns_sections():
    from agents.study_agents import run_materi_agent
    fake_out = {
        "sections": [
            {"title": "Pengertian Fotosintesis", "content": "Fotosintesis adalah proses..."},
            {"title": "Reaksi Kimia", "content": "Persamaan: 6CO2 + 6H2O..."},
        ]
    }
    with patch("agents.study_agents.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(fake_out)
        mock_build.return_value = mock_agent
        result = run_materi_agent("Fotosintesis")

    assert "sections" in result
    assert isinstance(result["sections"], list)
    assert len(result["sections"]) > 0
    assert "title" in result["sections"][0]
    assert "content" in result["sections"][0]


# ── run_konsep_agent ───────────────────────────────────────────

def test_run_konsep_agent_returns_concepts():
    from agents.study_agents import run_konsep_agent
    fake_out = {
        "concepts": [
            {"term": "Fotosintesis", "definition": "Proses mengubah CO2 dan H2O menjadi glukosa."},
            {"term": "Klorofil", "definition": "Pigmen hijau yang menyerap cahaya matahari."},
        ]
    }
    with patch("agents.study_agents.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(fake_out)
        mock_build.return_value = mock_agent
        result = run_konsep_agent("Fotosintesis", "materi tentang fotosintesis...")

    assert "concepts" in result
    assert isinstance(result["concepts"], list)
    assert len(result["concepts"]) > 0
    assert "term" in result["concepts"][0]
    assert "definition" in result["concepts"][0]


# ── run_ringkasan_agent ────────────────────────────────────────

def test_run_ringkasan_agent_returns_summary():
    from agents.study_agents import run_ringkasan_agent
    fake_out = {"summary": "Fotosintesis adalah proses biokimia fundamental yang dilakukan tumbuhan."}
    with patch("agents.study_agents.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(fake_out)
        mock_build.return_value = mock_agent
        result = run_ringkasan_agent("Fotosintesis", "materi...", "- Fotosintesis: proses...")

    assert "summary" in result
    assert isinstance(result["summary"], str)
    assert len(result["summary"]) > 10
