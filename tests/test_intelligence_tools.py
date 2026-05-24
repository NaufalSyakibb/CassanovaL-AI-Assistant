# tests/test_intelligence_tools.py
import pytest
from pathlib import Path
import sys, os
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_parse_experiment_log_counts_verdicts(tmp_path):
    log = tmp_path / "experiment_log.md"
    log.write_text(
        "---\nagent: task\n---\n\n"
        "## [2026-05-01 09:00] H-001\n**Verdict:** KEEP\n**Confidence:** HIGH\n\n"
        "## [2026-05-02 10:00] H-002\n**Verdict:** DISCARD\n**Confidence:** MEDIUM\n\n"
        "## [2026-05-03 11:00] H-003\n**Verdict:** KEEP\n**Confidence:** LOW\n\n"
        "## [2026-05-04 12:00] H-004\n**Verdict:** INCONCLUSIVE\n**Confidence:** LOW\n",
        encoding="utf-8",
    )
    from tools.intelligence_tools import _parse_experiment_log
    result = _parse_experiment_log(log)
    assert result == {"KEEP": 2, "DISCARD": 1, "INCONCLUSIVE": 1, "total": 4}


def test_parse_experiment_log_missing_file(tmp_path):
    from tools.intelligence_tools import _parse_experiment_log
    result = _parse_experiment_log(tmp_path / "nonexistent.md")
    assert result == {"KEEP": 0, "DISCARD": 0, "INCONCLUSIVE": 0, "total": 0}


def test_parse_program_md_extracts_hypothesis(tmp_path):
    prog = tmp_path / "program.md"
    prog.write_text(
        "---\nagent: task\nupdated: 2026-05-20\n---\n\n"
        "# Autoresearch Program\n\n"
        "## Current Hypothesis\nUser prefers bullet lists over prose.\n\n"
        "## Metric\nTask acceptance rate.\n",
        encoding="utf-8",
    )
    from tools.intelligence_tools import _parse_program_md
    result = _parse_program_md(prog)
    assert result["hypothesis"] == "User prefers bullet lists over prose."
    assert result["updated"] == "2026-05-20"


def test_parse_program_md_missing_file(tmp_path):
    from tools.intelligence_tools import _parse_program_md
    result = _parse_program_md(tmp_path / "nonexistent.md")
    assert result == {"hypothesis": None, "updated": None}


def test_parse_program_md_no_hypothesis_section(tmp_path):
    prog = tmp_path / "program.md"
    prog.write_text("---\nagent: task\n---\n\n# Autoresearch Program\n\n## Metric\nSomething.\n", encoding="utf-8")
    from tools.intelligence_tools import _parse_program_md
    result = _parse_program_md(prog)
    assert result["hypothesis"] is None
