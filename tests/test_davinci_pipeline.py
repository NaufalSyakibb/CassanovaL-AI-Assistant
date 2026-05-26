import json
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage


def _fake_agent_result(output_dict: dict):
    return {"messages": [AIMessage(content=json.dumps(output_dict))]}


def test_run_idea_generator_returns_ideas():
    from agents.davinci_pipeline import run_idea_generator
    fake_out = {
        "ideas": [
            {"id": 1, "title": "Gamifikasi Belajar", "tagline": "Jadikan setiap ujian seperti level game.", "spectrum": "Konvensional"},
            {"id": 2, "title": "AI Tutor Emosional", "tagline": "AI yang merespon suasana hati pelajar.", "spectrum": "Inovatif"},
            {"id": 3, "title": "Mimpi Sebagai Kurikulum", "tagline": "Gunakan analisis mimpi untuk menentukan minat.", "spectrum": "Liar"},
        ]
    }
    with patch("agents.davinci_pipeline.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(fake_out)
        mock_build.return_value = mock_agent
        result = run_idea_generator("cara baru belajar matematika")

    assert "ideas" in result
    assert isinstance(result["ideas"], list)
    assert len(result["ideas"]) > 0
    first = result["ideas"][0]
    assert "id" in first
    assert "title" in first
    assert "tagline" in first
    assert "spectrum" in first


def test_run_idea_expander_returns_expansion_keys():
    from agents.davinci_pipeline import run_idea_expander
    fake_out = {
        "title": "Gamifikasi Belajar",
        "use_cases": "Platform edukasi online; Kelas tatap muka; Pelatihan karyawan",
        "steps": "Rancang sistem poin; Tambahkan leaderboard; Buat badge pencapaian; Uji dengan pengguna",
        "example": "Duolingo — aplikasi bahasa yang menggunakan streak dan XP untuk memotivasi pengguna.",
        "impact": "Meningkatkan engagement belajar hingga 3x dan menurunkan dropout rate."
    }
    with patch("agents.davinci_pipeline.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(fake_out)
        mock_build.return_value = mock_agent
        result = run_idea_expander("Gamifikasi Belajar", "Jadikan setiap ujian seperti level game.")

    assert "use_cases" in result
    assert "steps" in result
    assert "example" in result
    assert "impact" in result


def test_run_idea_expander_handles_unparseable_response():
    from agents.davinci_pipeline import run_idea_expander
    with patch("agents.davinci_pipeline.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "messages": [MagicMock(content="Maaf, saya tidak bisa memproses permintaan ini.")]
        }
        mock_build.return_value = mock_agent
        result = run_idea_expander("Judul Test", "Tagline test.")

    assert "error" in result
